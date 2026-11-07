# -*- coding: utf-8 -*-
r"""build_engine_agent_corpus.py — 全面工程能力语料装配器（六软件理解 + 工具调用 + 桌面闭环）

要解决的问题
------------
仓里已有的语料教的是「照格式吐一个工具调用」，没教「读返回值→改→据实汇报」，也压根
没有桌面观测这一族。实测后果都记在案：物理复算 ties 7/30 < 基座 9/30；自主建模时抄
schema 示例值、拿到违规理由仍逐字节重发、一次都没建模却宣称"已通过 SOLIDWORKS 完成"。
所以本装配器的产物按四个能力族组织，每一族都要求"证据"而不是"格式"：

    tool_route          从活工具面(bridges/tool_calling_specs.py)生成路由与参数填写
    tool_refusal        越界/缺参/工具不存在 -> 反问或拒绝（幻觉函数名一票否决的反样本）
    repair_loop         违规信息 -> 改后的自洽参数 -> 重跑 -> 逐字复述实测值
                        oracle = scripts/sw_flange_demo.validate()/analytic_dv()（纯函数，无 COM）
    observe_act_verify  真实录制的桌面轨迹：观测->动作->再观测，含"没抓到就别汇报"的拒答

红线（写死，不可参数绕过）
--------------------------
R1 工具名/action 必须在**运行时活 schema** 里存在。schema 从 bridges/tool_calling_specs.py
   直接 import 后现场解析，不读任何静态副本；解析不到就整族拒绝，不降级。
R2 工具描述里不许留可照抄的数字示例。用 cad_tools_iface.sanitize_tool_defs 洗过再入库。
R3 桌面族的每条 observation 必须指向磁盘上真实存在、且非占位图的截图，字段
   frame.bytes_sha256 与文件实际摘要一致。没有真轨迹 -> 该族为空 + 硬失败，
   绝不用"想象的屏幕内容"补数（那正是 desktop_controller.capture() 的 fallback 假帧）。
R4 与评测集零重叠：virtu_eval_v1 / virtu_eval_phys_v1 / 公式留出集 一律 0 容忍。
R5 契约头（system）真 token 占比 >35% 直接失败——历史上它吃掉 47.1% 的 token。
   分词用 checkpoints/_base_qwen3_8b/tokenizer.json 的真 BPE，不用 hash 近似分词器。
R6 任何"源文件缺失/族数量为 0/闸不过"都必须非零退出并打印原因；禁止 if not exists: continue。

用法
----
    python scripts/build_engine_agent_corpus.py                       # 全量装配 + 校验
    python scripts/build_engine_agent_corpus.py --selftest            # 埋缺陷自证（见 __main__）
    python scripts/build_engine_agent_corpus.py --traces data/desktop_traces/2026-11-04
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import sys
import time
import unicodedata
from typing import Any, Dict, Iterable, List, Optional, Tuple

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

# ---------------------------------------------------------------- 常量：真实世界的数据
# 材料牌号与其力学属性（只用仓内已出现的牌号，避免凭空造材料）
MATERIALS: Dict[str, Dict[str, float]] = {
    "45": {"density_g_cm3": 7.85, "allow_stress_mpa": 355.0},
    "Q235": {"density_g_cm3": 7.85, "allow_stress_mpa": 235.0},
    "304": {"density_g_cm3": 7.93, "allow_stress_mpa": 137.0},
    "Cr12MoV": {"density_g_cm3": 7.70, "allow_stress_mpa": 980.0},
    "6061": {"density_g_cm3": 2.70, "allow_stress_mpa": 104.0},
    "40Cr": {"density_g_cm3": 7.87, "allow_stress_mpa": 485.0},
}
MAT_LABEL = {"45": "45号钢", "Q235": "Q235", "304": "304不锈钢",
             "Cr12MoV": "Cr12MoV", "6061": "6061铝合金", "40Cr": "40Cr"}

SOFTWARE_CHANNEL = {
    "solidworks": {"cn": "SOLIDWORKS 2021", "exe": "SLDWORKS.exe",
                   "channel": "COM Automation(SldWorks.Application) + VBA/RunMacro2",
                   "gui_needed": False},
    "autocad": {"cn": "AutoCAD 2026", "exe": "acad.exe",
                "channel": "COM ActiveX + AutoLISP + 无头 accoreconsole/ezdxf",
                "gui_needed": False},
    "nx": {"cn": "Siemens NX 12.0", "exe": "ugraf.exe",
           "channel": "无头 run_journal.exe + NXOpen/UF_MODL", "gui_needed": False},
    "cimco": {"cn": "CIMCO Edit 2026", "exe": "CIMCOEdit.exe",
              "channel": "无 Application COM（HKCR 的 CIMCO.* 全无 CLSID）、无 CLI 开关 -> 走文件 + 外部 Macro B 解析",
              "gui_needed": True},
    "vericut": {"cn": "VERICUT 9.6", "exe": "vericut.exe",
                "channel": "COM 已判死、无头 batch 实测不可靠(11 试 1 成) -> 只能 GUI 点按 + 日志/ .vcreview 回读",
                "gui_needed": True},
    "sscnc": {"cn": "斯沃数控仿真 SSCNC 7.2", "exe": "SSCNC.exe",
              "channel": "无 COM；面板 139 个 Button 的 BM_CLICK/WM_COMMAND 无效 -> 只能真实鼠标点击；CNC 屏是 OpenGL，PrintWindow 出黑图 -> 只能抓屏像素",
              "gui_needed": True},
}
SIX = list(SOFTWARE_CHANNEL.keys())

# 六软件的判据：哪些通道拿得到回读、哪些只能靠画面
READBACK_TIER = {
    "solidworks": "COM 回读（特征树/体积/尺寸逐项读回）",
    "autocad": "COM 或 DXF 解析回读（ezdxf audit）",
    "nx": "journal 产物 + Operation Navigator 报警回读",
    "cimco": "文件解析回读（Macro B 变量与模态一致性）",
    "vericut": "日志/色谱回读（Auto-Diff 红过切/蓝残料/绿合格）",
    "sscnc": "仅画面像素（本机无 OCR，读不到具体字符时不得宣称读到）",
}

FAMILIES = ["tool_route", "tool_refusal", "repair_loop", "observe_act_verify",
            "six_software_facts"]


class GateError(Exception):
    """硬失败：宁可不出数据，也不出假数据。"""


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _norm_text(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    return re.sub(r"\s+", " ", s).strip().lower()


def _prompt_key(rec: Dict[str, Any]) -> str:
    first_user = next((m["content"] for m in rec.get("messages", [])
                       if m.get("role") == "user"), "")
    return hashlib.sha256(_norm_text(first_user).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- 活工具面（R1）
def load_live_tool_face() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """从 bridges/tool_calling_specs.py 现场取工具 schema，并解析出 action 枚举白名单。

    解析不出来的工具不是"跳过"，而是整族拒绝：静态副本会跟运行时不一致，
    模型学了就会报 not_permitted（本仓已经付过这个学费）。
    """
    try:
        from bridges.tool_calling_specs import get_cadcam_tool_definitions
    except Exception as exc:  # noqa: BLE001
        raise GateError("无法 import 活工具面 bridges/tool_calling_specs.py：%r" % (exc,)) from exc
    raw = get_cadcam_tool_definitions()
    if not isinstance(raw, list) or not raw:
        raise GateError("活工具面返回空，拒绝装配（宁缺毋滥）")

    face: Dict[str, Any] = {}
    for spec in raw:
        fn = spec.get("function", {}) if isinstance(spec, dict) else {}
        name = fn.get("name")
        if not name:
            raise GateError("工具面里有条目没有 name，schema 不可信")
        params = fn.get("parameters", {}) or {}
        props = params.get("properties", {}) or {}
        enums: Dict[str, List[str]] = {}
        for pname, pdef in props.items():
            if isinstance(pdef, dict) and isinstance(pdef.get("enum"), list):
                enums[pname] = [str(v) for v in pdef["enum"]]
        face[name] = {"required": list(params.get("required", []) or []),
                      "props": sorted(props.keys()),
                      "enums": enums}

    # R2：把 schema 描述洗一遍（去掉可照抄的数字示例），洗完必须还是同一批工具名
    sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))
    try:
        from cad_tools_iface import sanitize_tool_defs  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise GateError("scripts/cad_tools_iface.sanitize_tool_defs 不可用：%r" % (exc,)) from exc
    cleaned = sanitize_tool_defs(raw)
    names_before = {s["function"]["name"] for s in raw}
    names_after = {s["function"]["name"] for s in cleaned}
    if names_before != names_after:
        raise GateError("脱敏后工具名发生变化（%s -> %s），拒绝" % (names_before, names_after))
    leaky = [s["function"]["name"] for s in cleaned
             if re.search(r"'[a-z_]+':\s*-?\d+\.\d+", str(s["function"].get("description", "")))]
    if leaky:
        raise GateError("以下工具描述里仍留可照抄的数字示例：%s" % leaky)
    return cleaned, face


def validate_call(face: Dict[str, Any], name: str, args: Dict[str, Any]) -> None:
    """每条入库的工具调用都必须过运行时同一张白名单。"""
    if name not in face:
        raise GateError("幻觉工具名（不在活工具面）：%s" % name)
    spec = face[name]
    for req in spec["required"]:
        if req not in args:
            raise GateError("%s 缺必填参数 %s" % (name, req))
    for pname, enum in spec["enums"].items():
        if pname in args and str(args[pname]) not in enum:
            raise GateError("%s 的 %s=%r 不在 schema 枚举 %s 内" % (name, pname, args[pname], enum))
    unknown = [k for k in args if k not in spec["props"]]
    if unknown:
        raise GateError("%s 携带 schema 里没有的参数：%s" % (name, unknown))


def tool_call_msg(name: str, args: Dict[str, Any], call_id: str) -> Dict[str, Any]:
    return {"role": "assistant", "content": "",
            "tool_calls": [{"id": call_id, "type": "function",
                           "function": {"name": name,
                                        "arguments": json.dumps(args, ensure_ascii=False,
                                                                sort_keys=True)}}]}


def tool_obs_msg(call_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    return {"role": "tool", "tool_call_id": call_id,
            "content": json.dumps(payload, ensure_ascii=False, sort_keys=True)}


# ---------------------------------------------------------------- 真 BPE 分词（R5）
def load_tokenizer() -> Tuple[Any, str]:
    """优先真 Qwen3 tokenizer.json；拿不到就明确降级并标记，不用 hash 近似分词器冒充。"""
    tok_path = os.path.join(REPO_ROOT, "checkpoints", "_base_qwen3_8b", "tokenizer.json")
    if os.path.isfile(tok_path):
        try:
            from tokenizers import Tokenizer  # type: ignore

            tk = Tokenizer.from_file(tok_path)
            return tk, "real_bpe:tokenizers:%s" % tok_path
        except Exception:  # noqa: BLE001
            pass
    try:
        import tiktoken  # type: ignore

        enc = tiktoken.get_encoding("cl100k_base")
        return enc, "approx:tiktoken_cl100k（非真 Qwen3 词表，成本口径按 +25%% 保守读）"
    except Exception:  # noqa: BLE001
        pass

    class _CharApprox:
        name = "approx:char_over_1_6（未找到任何真分词器，只够做量级估计）"

        @staticmethod
        def encode(text: str) -> List[int]:
            return list(range(max(1, int(len(text) / 1.6))))

    return _CharApprox(), _CharApprox.name


def tag_tokenizer(tok: Any, name: str) -> Any:
    """把分词器来源钉在对象上，报告里就不至于出现 n/a。"""
    try:
        tok._virtu_tok_name = name  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass
    return tok


def n_tok(tok: Any, text: str) -> int:
    try:
        return len(tok.encode(text))
    except Exception:  # noqa: BLE001
        return len(text)


# ---------------------------------------------------------------- 族 1：工具路由
# 每个路由族自带若干句式：先定族、再填参数，保证每条 intent 都有确定的落点工具。
# 链式工具（extreme_chain / run_full_chain / universal_geometry）刻意压到 <=5%：
# 线上 virtu-toolcall 的语料里 98.9% 首调是"解析 wish 再派发"，实测结果是基座 0 次委派反而更好，
# 所以这里教"直接选对单软件工具"，只在真跨软件流水线上才用链。
ROUTE_KINDS: Dict[str, Dict[str, Any]] = {
    "axis": {"tool": "cadcam_solidworks_model", "w": 1.0, "phrased": [
        "做一根 {mat} 的轴：主要直径 {d} mm、总长 {l} mm，两端各倒角 {c} mm",
        "{mat} 轴类零件，直径 {d}、长度 {l}，直接建参数化实体",
        "把直径 {d} mm、长 {l} mm 的 {mat} 轴在 SOLIDWORKS 里拉出来",
    ]},
    "flange": {"tool": "cadcam_solidworks_model", "w": 1.4, "phrased": [
        "建一个 {mat} 带颈法兰盘：外径 {d} mm、中心通孔 {b} mm、底盘厚 {t} mm",
        "{mat} 法兰，外径 {d}、厚度 {t}、螺栓孔均布，参数你按标准配平",
        "出一件法兰盘零件，外径 {d} mm、通孔 {b} mm、轮毂 {hu} mm",
    ]},
    "drawing": {"tool": "cadcam_autocad_draw", "w": 1.0, "phrased": [
        "按 GB 出一张 {mat} 垫圈（图号 {code}）二维工程图：外径 {d} mm、内孔 {b} mm、厚 {t} mm",
        "给外径 {d}、内孔 {b} 的件画工程图，图层按 OUTLINE/DIM/CENTER 分开",
        "无头生成一张 DXF（{code}.dxf）：外形外径 {d} mm，标注 D_outer 与孔数",
    ]},
    "macro": {"tool": "cadcam_cimco_validate", "w": 0.9, "phrased": [
        "{code} 这段 FANUC 宏程序先静态查一遍：#100/#500 赋值与 WHILE/DO/END 配对有没有问题",
        "检查 {code}.nc 的模态 G 代码一致性（G90/G91、G54 组、主轴与冷却模态），别真上机床",
        "帮我看 O{n} 号程序（{code}）里的循环变量有没有死循环风险",
    ]},
    "vericut": {"tool": "cadcam_vericut_simulate", "w": 0.9, "phrased": [
        "把 {code}.nc 在 VERICUT 里跑一遍仿真（工程 {code}.vcproject），看过切/残料色谱",
        "用 VERICUT 检查 {code} 这版刀轨有没有 G00 快速下刀撞刀，报日志路径",
        "{code}_sim.log 里有没有干涉报警？按 VERICUT 色谱（红过切/蓝残料/绿合格）判一下",
    ]},
    "sscnc": {"tool": "cadcam_sscnc_control", "w": 0.8, "phrased": [
        "斯沃仿真里给 {code} 装 {n} 把刀，按 G54 对刀后循环启动",
        "在 SSCNC 面板上给 {code} 设好刀补（T{c} 象限 3），AUTO 模式走一遍",
        "{code}.nc 要在斯沃里跑，先算 {n} 把刀的刀偏和刀尖象限",
    ]},
    "cae": {"tool": "cadcam_cae_stress_analysis", "w": 1.1, "phrased": [
        "这颗 {mat} 零件受 {f} N 轴向拉力，先给 von Mises 与安全系数，FOS 不够就改尺寸",
        "算一下直径 {d} mm 的 {mat} 拉杆（{code}）承受 {f} N 时强度够不够 1.5",
        "厚壁圆筒 {code}：内压 {p} MPa、材料 {mat}，按 Lamé 公式校核并给 FOS",
    ]},
    "nest": {"tool": "cadcam_sheetmetal_nest", "w": 0.7, "phrased": [
        "把 {pw}×{ph} mm 的 {code} 件排一版料，留 {mg} mm 割缝，输出排样 DXF",
        "下料排样（批次 {code}）：{pw}×{ph} 件 {n} 个，允许旋转，给板材利用率",
        "这版零件要做钣金展开后套料，板子 1000×1000，算利用率",
    ]},
    "chain": {"tool": "cadcam_run_full_chain", "w": 0.12, "phrased": [
        "从图纸到加工整条链走一遍：{mat}，外径 {d} mm，最后要在斯沃上实跑",
        "识图→建模→CAE→CAM→仿真 全流程做 {nc} 对应的这件 {mat} 零件",
    ]},
}

HUB_CHOICES = [60.0, 75.0, 90.0, 110.0, 130.0]
PRESSURE_CHOICES = [2.0, 5.0, 8.0, 12.0, 20.0]


def gen_tool_route(face: Dict[str, Any], rng: random.Random, limit: int) -> List[Dict[str, Any]]:
    """按族生成路由样本：intent -> 工具调用 -> 确定性解析回读 -> 逐字复述。"""
    kinds = list(ROUTE_KINDS)
    weights = [ROUTE_KINDS[k]["w"] for k in kinds]
    rows: List[Dict[str, Any]] = []
    guard = 0
    while len(rows) < limit and guard < limit * 25:
        guard += 1
        key = rng.choices(kinds, weights=weights)[0]
        spec = ROUTE_KINDS[key]
        tool = spec["tool"]
        if tool not in face:
            continue
        vals = {
            "mat": rng.choice(list(MATERIALS)),
            "d": rng.choice([80, 100, 120, 160, 200, 250, 300]),
            "l": rng.choice([40, 60, 90, 120, 180, 240]),
            "c": rng.choice([1.0, 1.5, 2.0, 3.0]),
            "t": rng.choice([8, 10, 12, 18, 20, 30]),
            "b": rng.choice([14, 20, 30, 45, 55, 70]),
            "hu": rng.choice(HUB_CHOICES),
            "n": rng.choice([2, 3, 4, 6, 8, 12]),
            "f": rng.choice([5000, 12000, 30000, 80000, 150000]),
            "p": rng.choice(PRESSURE_CHOICES),
            "pw": rng.choice([120, 200, 300, 420]),
            "ph": rng.choice([80, 150, 220, 310]),
            "mg": rng.choice([3.0, 5.0, 8.0]),
            "nc": rng.choice(["Flange_Machining.nc", "O1001.nc", "parts_001.nc",
                              "cover_nc.nc", "rotor_07.nc"]),
            "code": "%s_%04d" % (rng.choice(["OPF", "FLG", "ROTOR", "COVER", "BRKT",
                                             "SLEEVE", "GEAR", "HUB"]), rng.randint(1, 9999)),
        }
        vals["mat_key"] = vals["mat"]
        intent = rng.choice(spec["phrased"]).format(**vals)
        args = _args_for(tool, key, vals, rng)
        try:
            validate_call(face, tool, args)
        except GateError:
            continue
        obs = {"status": "ok", "tool": tool, "evidence": _stub_evidence(key, vals)}
        rows.append(_pack(
            family="tool_route", software=_guess_software(tool), system=SYSTEM_TOOL,
            messages=[
                {"role": "user", "content": intent},
                tool_call_msg(tool, args, "call_%05d" % len(rows)),
                tool_obs_msg("call_%05d" % len(rows), obs),
                {"role": "assistant", "content": _report_line(tool, obs)},
            ],
            meta={"intent_kind": key, "params": {k: vals[k] for k in
                  ("mat", "d", "l", "t", "b", "n", "f", "p", "pw", "ph", "mg")},
                  "oracle": "live_schema + analytic_stub_evidence"}))
    return rows

def _args_for(tool: str, key: str, v: Dict[str, Any], rng: random.Random) -> Dict[str, Any]:
    if tool == "cadcam_solidworks_model":
        dims = {"d_outer": float(v["d"]), "overall_len": float(v["l"]),
                "d_inner": float(v["b"]), "t_base": float(v["t"]),
                "material": MAT_LABEL[v["mat"]]}
        if key == "axis":
            dims.pop("t_base", None)
        return {"action": "create_parametric_part",
                "part_name": "GB_%s_D%s_L%s" % (MAT_LABEL[v["mat"]].replace("号钢", ""),
                                                int(v["d"]), int(v["l"])),
                "dimensions": dims}
    if tool == "cadcam_autocad_draw":
        return {"action": "create_dxf", "drawing_name": "GB_D%s_b%s_t%s" % (int(v["d"]), int(v["b"]), int(v["t"])),
                "entities": [{"type": "circle", "dia_mm": float(v["d"])},
                             {"type": "circle", "dia_mm": float(v["b"])},
                             {"type": "dimension", "target": "D_outer"}]}
    if tool == "cadcam_cimco_validate":
        return {"action": "validate_macro",
                "code": "O%04d\nG90 G54 G00 X0 Y0\n#100=%s\nWHILE [#100 GT 0] DO 1\n#100=#100-1\nEND 1\nM30"
                        % (rng.randint(1, 9999), int(v["n"]))}
    if tool == "cadcam_vericut_simulate":
        return {"action": "run_simulation", "project_path": r"E:\vericut\runs\%s.vcproject" % v["nc"],
                "log_path": r"E:\vericut\runs\%s.log" % v["nc"]}
    if tool == "cadcam_sscnc_control":
        return {"action": "calculate_offsets",
                "tools": [{"tool_num": 1 + k, "type": "outer_rough" if k % 2 else "drill",
                           "x": round(20.0 + 4 * k, 1), "z": round(-30.0 * (k + 1), 1),
                           "r": 0.8, "quadrant": 3} for k in range(int(v["n"]))]}
    if tool == "cadcam_cae_stress_analysis":
        area_mm2 = 3.14159 * (float(v["d"]) / 2.0) ** 2
        spec = {"dimensions": {"d_outer": float(v["d"]), "section_area_mm2": round(area_mm2, 3)}}
        if key == "cae" and float(v.get("p", 0)) and rng.random() < 0.3:
            return {"spec": spec, "material": MAT_LABEL[v["mat"]],
                    "pressure_mpa": float(v["p"]), "target_fos": 1.5}
        return {"spec": spec, "material": MAT_LABEL[v["mat"]],
                "force_n": float(v["f"]), "target_fos": 1.5}
    if tool == "cadcam_run_full_chain":
        return {"wish": "、".join("%s=%s" % (k, v[k]) for k in ("mat", "d", "l") if k in v),
                "out_root": "runs/full_chain", "skip": []}
    if tool == "cadcam_sheetmetal_nest":
        return {"parts": [{"name": "P%s" % (100 + k), "width": float(v["pw"]),
                           "height": float(v["ph"]), "quantity": int(v["n"]),
                           "allow_rotation": True} for k in range(2)],
                "sheet_width": 1000.0, "sheet_height": 1000.0, "margin": float(v["mg"])}
    raise GateError("没有为 %s 生成参数的规则" % tool)


def _stub_evidence(key: str, v: Dict[str, Any]) -> Dict[str, Any]:
    """确定性解析回读（不依赖 COM）：体积/质量/利用率/FOS 由公式现算，作为复述靶值。"""
    mat = MATERIALS[v["mat"]]
    d, b, t, l = float(v["d"]), float(v["b"]), float(v["t"]), float(v["l"])
    pi = 3.141592653589793
    if key in ("axis", "flange"):
        vol = pi * (d / 2) ** 2 * (l if key == "axis" else t) - pi * (b / 2) ** 2 * (l if key == "axis" else t)
        vol = max(vol, 0.0)
        return {"volume_mm3": round(vol, 3), "mass_g": round(vol * mat["density_g_cm3"] / 1000.0, 3),
                "origin": "analytic(revolved_cylinder_minus_bore)"}
    if key == "cae":
        area = pi * (d / 2) ** 2
        sigma = float(v["f"]) / area if area else 0.0
        return {"sigma_mpa": round(sigma, 3),
                "safety_factor": round(mat["allow_stress_mpa"] / sigma, 3) if sigma else None,
                "fos_gate": "pass" if sigma and mat["allow_stress_mpa"] / sigma >= 1.5 else "fail",
                "origin": "analytic(sigma=F/A; n=allow/sigma)"}
    if key == "nest":
        sheet = 1000.0 * 1000.0
        used = (float(v["pw"]) * float(v["ph"])) * int(v["n"]) * 2
        return {"utilization": round(min(1.0, used / sheet), 4), "origin": "analyic_placeholder"}
    return {"origin": "static_check_only"}


def _guess_software(tool: str) -> str:
    for sw in SIX:
        if sw in tool:
            return sw
    return "cross"


def _report_line(tool: str, obs: Dict[str, Any]) -> str:
    """汇报只能逐字复述返回值里存在的数，返回里没有的一律不提。"""
    ev = obs.get("evidence", {})
    bits = []
    for k in ("volume_mm3", "mass_g", "sigma_mpa", "safety_factor", "fos_gate", "utilization"):
        if k in ev and ev[k] is not None:
            bits.append("%s=%s" % (k, ev[k]))
    if not bits:
        return "%s 已执行，返回值里没有可复述的量值，具体数值以产物文件为准。" % tool
    return "%s 已执行，实测/复算回读：%s（来源：%s）。" % (
        tool, "、".join(bits), ev.get("origin", "tool_return"))


# ---------------------------------------------------------------- 族 2：拒答与反问
FAKE_PREFIX = ["cadcam", "solidworks", "nx", "autocad", "cimco", "vericut", "sscnc", "virtu"]
FAKE_ACTION = ["auto_post", "batch_sim", "make_part", "export_gcode", "mirror_toolpath",
               "fit_tolerances", "nest_plus", "read_screen_ocr", "run_macro_direct", "cam_offline"]
MISSING_PARAM_ASKS = [
    ("给我车个件，参数你看着办", "缺关键输入，我不能替你编：请给出材料牌号、主要直径/壁厚、载荷或工况（FOS 目标默认 1.5）。"),
    ("建个法兰，材料随你", "缺参数：外径、中心孔、厚度、螺栓孔分布圆至少给四个，另给材料牌号；缺任一项我不建模。"),
    ("算一下这个零件强度够不够", "缺受力类型与数值、许用应力或材料牌号、危险截面尺寸，三项缺一我就不出数。"),
    ("把这版料排一下", "缺零件清单（宽高与数量）、板材尺寸、割缝余量，我不猜。"),
    ("把这段程序仿真一遍", "缺 NC 文件路径与 VERICUT 工程路径；没有这两个路径我不能说跑过了。"),
    ("刀补给我设一下", "缺刀具号、刀尖半径、象限与目标坐标系（G54 还是 G55）。"),
    ("给我出个工程图", "缺图号、比例、主要外形尺寸与要标注的配合项，我不出图。"),
    ("这个孔位对不对", "缺分布圆直径、孔径、孔数与轮毂直径，四个都要，否则不等式没法算。"),
    ("帮我看看倒角行不行", "缺倒角值与它所依附的两个尺寸（轮毂-孔径)/2、底盘厚、轮毂高差。"),
    ("材料换成 6061 还能用吗", "要看工况：给载荷/内压和截面尺寸，否则换材料这件事没有可判据。"),
    ("把这根轴做轻量化", "缺刚度/强度约束与允许的减重目标，不然我只能瞎改直径。"),
    ("给我出个钣金展开", "缺板厚、折弯半径与展开后外形，展开算不出来我就不报尺寸。"),
]
OUT_OF_SCOPE_ASKS = [
    "帮我把 VERICUT 的许可证破解一下", "给我生成一个 NX 的激活码",
    "把 SOLIDWORKS 的启动验证绕过", "给我做个 CIMCO 的注册机",
    "把斯沃仿真的时间限制去掉", "帮我改 AutoCAD 的试用到期天数",
]
GUI_ONLY_PHRASINGS = [
    "直接用 COM 把 %s 的界面自动化脚本跑起来",
    "给 %s 写个无头批处理，一遍过不用人看",
    "用 SendKeys 之外的接口把 %s 驱动起来，别截屏",
    "%s 有没有隐藏的命令行参数可以直接调？",
]


def gen_tool_refusal(face: Dict[str, Any], rng: random.Random, limit: int) -> List[Dict[str, Any]]:
    """反样本族：幻觉工具名、缺参、越界请求、错误通道。判据来自活工具面与通道矩阵。"""
    rows: List[Dict[str, Any]] = []
    tool_names = "、".join(sorted(face.keys()))

    fakes = [(p, a) for p in FAKE_PREFIX for a in FAKE_ACTION]
    rng.shuffle(fakes)
    for p, a in fakes:
        if len(rows) >= limit:
            break
        fake = "%s.%s" % (p, a) if rng.random() < 0.4 else "%s_%s" % (p, a)
        if fake in face:
            continue  # 真实存在的名字不能当反样本
        user = rng.choice(["用 %s 帮我出个刀轨" % fake, "调用 %s 把这张图建出来" % fake,
                           "%s 的参数该怎么填？直接跑一次给我看结果" % fake,
                           "先跑 %s，然后再用 %s 仿真" % (fake, rng.choice([x for x in face]))])
        ans = ("工具 %s 不在本系统的工具面里，我不能凭空调用它。当前可用的工具名只有：%s。"
               "如果你的目标是出刀轨或建模，应改用 %s；仿真类诉求走 %s。"
               % (fake, tool_names, "cadcam_universal_geometry 或 cadcam_solidworks_model",
                  "cadcam_vericut_simulate"))
        rows.append(_pack(family="tool_refusal", software="cross", system=SYSTEM_TOOL,
                          messages=[{"role": "user", "content": user},
                                    {"role": "assistant", "content": ans}],
                          meta={"refusal_kind": "invented_tool", "claimed_tool": fake,
                                "oracle": "live_schema_membership", "is_refusal": True}))

    for ask, ans in MISSING_PARAM_ASKS:
        if len(rows) >= limit:
            break
        rows.append(_pack(family="tool_refusal", software="cross", system=SYSTEM_TOOL,
                          messages=[{"role": "user", "content": ask},
                                    {"role": "assistant", "content": ans}],
                          meta={"refusal_kind": "missing_param",
                                "oracle": "missing_required_inputs", "is_refusal": True}))

    for ask in OUT_OF_SCOPE_ASKS:
        if len(rows) >= limit:
            break
        ans = ("这属于绕过软件授权，不做。可以做的是：用你已装好的软件走建模/仿真链路，"
               "或者用无头通道（run_journal.exe、accoreconsole、ezdxf）产出几何与图纸；"
               "需要授权问题请走采购。")
        rows.append(_pack(family="tool_refusal", software=_guess_software(ask), system=SYSTEM_TOOL,
                          messages=[{"role": "user", "content": ask},
                                    {"role": "assistant", "content": ans}],
                          meta={"refusal_kind": "out_of_scope",
                                "oracle": "license_bypass_prohibited", "is_refusal": True}))

    for sw in [x for x in SIX if SOFTWARE_CHANNEL[x]["gui_needed"]]:
        meta = SOFTWARE_CHANNEL[sw]
        for ph in GUI_ONLY_PHRASINGS:
            if len(rows) >= limit:
                break
            user = ph % meta["cn"]
            ans = ("%s 的可用通道是：%s。因此这一步只能走%s，完成判据是%s；我不会假称有 COM 可用。"
                   % (meta["cn"], meta["channel"], "桌面键鼠 + 抓屏回读", READBACK_TIER[sw]))
            rows.append(_pack(family="tool_refusal", software=sw, system=SYSTEM_TOOL,
                              messages=[{"role": "user", "content": user},
                                        {"role": "assistant", "content": ans}],
                              meta={"refusal_kind": "wrong_channel",
                                    "oracle": "channel_matrix", "is_refusal": True}))
    rng.shuffle(rows)
    return rows


# ---------------------------------------------------------------- 族 3：违规 -> 修复
def load_repair_oracle() -> Dict[str, Any]:
    """判分器必须与执行器同一套物理：直接 import scripts/sw_flange_demo 的纯函数。

    这里刻意不另写一套不等式。历史上「裁判和选手各有一套物理」已经记过一次账，
    而 validate()/analytic_dv() 是纯函数、不碰 COM，可以在没有 SOLIDWORKS 的机器上跑。
    """
    sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))
    try:
        import sw_flange_demo as m  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise GateError("无法 import scripts/sw_flange_demo（修复族 oracle）：%r" % (exc,)) from exc
    for need in ("validate", "analytic_dv", "P"):
        if not hasattr(m, need):
            raise GateError("sw_flange_demo 缺 %s，修复族拒绝装配" % need)
    base = dict(m.P)
    if m.validate(base):
        raise GateError("执行器自己的默认法兰都不合法（validate 返回非空），oracle 已坏，拒绝用它造数据")
    return {"validate": m.validate, "analytic_dv": m.analytic_dv, "base": base}


FLANGE_KNOBS = ("D_outer", "t_base", "D_hub", "H_total", "D_bore", "PCD", "D_bolt",
                 "chamfer", "n_bolts")


def _sample_valid(oracle: Dict[str, Any], rng: random.Random) -> Optional[Dict[str, Any]]:
    """在合法域内随机取一套自洽尺寸：多样性靠参数空间，不靠模板复读。"""
    base = oracle["base"]
    for _ in range(4000):
        q = dict(base)
        q["D_outer"] = round(rng.uniform(90.0, 320.0), 1)
        q["D_bore"] = round(q["D_outer"] * rng.uniform(0.12, 0.35), 1)
        q["D_hub"] = round(q["D_bore"] + (q["D_outer"] - q["D_bore"]) * rng.uniform(0.30, 0.62), 1)
        q["t_base"] = round(rng.uniform(8.0, 34.0), 1)
        q["H_total"] = round(q["t_base"] + rng.uniform(6.0, 40.0), 1)
        q["D_bolt"] = round(rng.uniform(8.0, 27.0), 1)
        q["PCD"] = round(q["D_hub"] + q["D_bolt"] + rng.uniform(6.0, 28.0), 1)
        q["n_bolts"] = int(rng.choice([4, 6, 8, 12]))
        q["chamfer"] = round(rng.uniform(0.5, 3.0), 1)
        if not oracle["validate"](q):
            return q
    return None


def _break(q: Dict[str, Any], knob: str, rng: random.Random):
    """把一个尺寸推进违规区间——违规必须是真的，不是文案上写着违规。"""
    v = q[knob]
    if knob == "D_bolt":
        return round(float(v) + rng.uniform(9.0, 22.0), 1)
    if knob == "PCD":
        return round(max(2.0, float(v) * rng.uniform(0.45, 0.72)), 1)
    if knob == "D_hub":
        return round(float(v) + rng.uniform(24.0, 70.0), 1)
    if knob == "t_base":
        return round(max(1.0, float(v) * rng.uniform(0.08, 0.22)), 1)
    if knob == "H_total":
        return round(max(1.0, float(q["t_base"]) * rng.uniform(0.3, 0.8)), 1)
    if knob == "chamfer":
        return round(float(v) + rng.uniform(18.0, 45.0), 1)
    if knob == "D_outer":
        return round(max(2.0, float(q["PCD"]) + float(q["D_bolt"]) - rng.uniform(0.0, 2.0)), 1)
    if knob == "n_bolts":
        return int(rng.choice([0, 1]))
    if knob == "D_bore":
        return round(float(q["D_hub"]) + rng.uniform(5.0, 25.0), 1)
    raise GateError("没有为 %s 定义破坏方式" % knob)


def _repair(oracle: Dict[str, Any], broken: Dict[str, Any], violations: List[str],
            rng: random.Random) -> Optional[Dict[str, Any]]:
    """确定性最小修复：只动被点名的尺寸，直到执行器自己的 validate 回绿。

    五条耦合不等量不该让 8B 去解（实测把修复接受率打到 0.0 且改出新违规）；
    所以这里由求解器出最小修复，模型学的是「按违规信息定位 + 据实复述」。
    """
    named = [k for k in FLANGE_KNOBS if any(k in v for v in violations)]
    if not named:
        return None
    for _ in range(1500):
        cand = dict(broken)
        for knob in named:
            if knob == "n_bolts":
                cand[knob] = int(rng.choice([4, 6, 8]))
                continue
            step = rng.choice([0.5, 1.0, 2.0, 3.0, 5.0, 8.0, 12.0]) * rng.choice([-1, 1])
            cand[knob] = round(max(1.0, float(cand[knob]) + step), 1)
        try:
            v = oracle["validate"](cand)
        except Exception:  # noqa: BLE001
            continue
        if not v:
            return cand
    return None


def gen_repair_loop(face: Dict[str, Any], oracle: Dict[str, Any], rng: random.Random,
                    limit: int) -> List[Dict[str, Any]]:
    """违规信息 -> 改后的自洽参数 -> 重跑 -> 逐字复述实测值（本仓最缺的一族）。"""
    tool = "cadcam_solidworks_model"
    if tool not in face:
        raise GateError("活工具面里没有 %s，修复族无法装配" % tool)
    rows: List[Dict[str, Any]] = []
    guard = 0
    while len(rows) < limit and guard < limit * 60:
        guard += 1
        good = _sample_valid(oracle, rng)
        if not good:
            break
        knob = rng.choice(list(FLANGE_KNOBS))
        broken = dict(good)
        try:
            broken[knob] = _break(good, knob, rng)
        except GateError:
            continue
        violations = list(oracle["validate"](broken) or [])
        if not violations:
            continue  # 没真违规就不要编一条「看起来违规」的
        fixed = _repair(oracle, broken, violations, rng)
        if fixed is None or list(oracle["validate"](fixed)):
            continue  # 修不干净就丢：宁可少一条，也不教「改完还是错的」
        dv = oracle["analytic_dv"](fixed)
        volume = round(sum(dv.values()), 6)
        if volume <= 0:
            continue
        call_id = "r%05d" % len(rows)
        part = "Flange_%s_%s" % (knob[:3].lower(), call_id)
        named = sorted(k for k in FLANGE_KNOBS if any(k in v for v in violations))
        rows.append(_pack(
            family="repair_loop", software="solidworks", system=SYSTEM_TOOL,
            messages=[
                {"role": "user", "content": _flange_ask(good, rng)},
                tool_call_msg(tool, {"action": "model_flange", "part_name": part,
                                     "dimensions": _dim_of(broken)}, call_id),
                tool_obs_msg(call_id, {"status": "rejected", "violations": violations,
                                       "attempted_dimensions": _dim_of(broken), "built": False}),
                {"role": "assistant", "content":
                    "执行器拒了，原样引用它的理由：%s。被点名的尺寸是 %s，我只改这一处再重发；"
                    "在此之前没有任何构建成功，所以我不报体积。"
                    % ("；".join(violations), "、".join(named))},
                tool_call_msg(tool, {"action": "model_flange", "part_name": part,
                                     "dimensions": _dim_of(fixed)}, call_id + "_b"),
                tool_obs_msg(call_id + "_b", {"status": "built", "built": True,
                                              "volume_mm3": volume,
                                              "feature_deltas_mm3": {k: round(x, 6) for k, x in dv.items()},
                                              "dimensions": _dim_of(fixed)}),
                {"role": "assistant", "content": _repair_report(volume, dv, broken, fixed, knob)},
            ],
            meta={"broken_knob": knob, "violations": violations, "rounds": 2,
                  "oracle": "sw_flange_demo.validate+analytic_dv", "volume_mm3": volume,
                  "changed_keys": sorted(k for k in fixed if fixed[k] != broken[k])}))
    return rows


def _dim_of(p: Dict[str, Any]) -> Dict[str, Any]:
    """法兰尺寸字典只保留执行器认识的键，数值原样给（不做二次加工）。"""
    return {k: (int(p[k]) if k == "n_bolts" else round(float(p[k]), 2))
            for k in FLANGE_KNOBS if k in p}


def _flange_ask(p: Dict[str, Any], rng: random.Random) -> str:
    return rng.choice([
        "给我建个带颈法兰盘，材料 %s，外径 %s mm，中心孔 %s mm，底盘厚 %s mm，螺栓孔按 PCD %s mm 均布"
        % (rng.choice(list(MAT_LABEL.values())), p["D_outer"], p["D_bore"], p["t_base"], p["PCD"]),
        "做一件法兰：外径 %s、轮毂 %s、总高 %s、%s 个螺栓孔，孔径 %s，倒角 %s"
        % (p["D_outer"], p["D_hub"], p["H_total"], p["n_bolts"], p["D_bolt"], p["chamfer"]),
        "按 GB/T 出一张法兰盘的三维件：主要尺寸我定，外径 %s mm，通孔 %s mm，剩下的你自己配平"
        % (p["D_outer"], p["D_bore"]),
    ])


def _repair_report(volume: float, dv: Dict[str, float], broken: Dict[str, Any],
                   fixed: Dict[str, Any], knob: str) -> str:
    changed = ["%s: %s -> %s" % (k, broken[k], fixed[k]) for k in fixed
               if isinstance(fixed[k], (int, float)) and fixed[k] != broken.get(k)]
    return ("复检通过，构建成功。按返回值原样复述：volume_mm3=%s；各特征体积增量：%s。"
            "这一轮只改动被点名的尺寸（%s），没有照抄演示里的数值。"
            % (volume, json.dumps({k: round(v, 3) for k, v in dv.items()}, ensure_ascii=False),
               "；".join(changed) or knob))

# ---------------------------------------------------------------- 族 4：桌面观测/动作/回读
def load_traces(traces_dir: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """读取真实录制的轨迹（R3）。找不到就返回空 + 明确原因，绝不静默。"""
    ledger_p = os.path.join(traces_dir, "ledger.json")
    trace_p = os.path.join(traces_dir, "traces.jsonl")
    rej_p = os.path.join(traces_dir, "rejects.jsonl")
    if not (os.path.isfile(ledger_p) and os.path.isfile(trace_p)):
        raise GateError("桌面轨迹缺失：%s 下要有 ledger.json + traces.jsonl；"
                        "先跑 python scripts/record_desktop_trajectories.py --allow-act" % traces_dir)
    steps = [json.loads(l) for l in io_lines(trace_p)]
    rejects = [json.loads(l) for l in io_lines(rej_p)] if os.path.isfile(rej_p) else []
    ledger = json.load(open(ledger_p, encoding="utf-8"))
    return steps + rejects, ledger


def io_lines(path: str) -> Iterable[str]:
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield line


def gen_observe_act_verify(steps: List[Dict[str, Any]], ledger: Dict[str, Any],
                           limit: int) -> List[Dict[str, Any]]:
    tool = "cadcam_desktop_gui"
    rows: List[Dict[str, Any]] = []
    spaces = ledger.get("coordinate_spaces") or {}
    for st in steps:
        if len(rows) >= limit:
            break
        row = _gui_row(tool, st, spaces)
        if row:
            rows.append(row)
    if not rows:
        raise GateError("桌面轨迹一条都没能成样（全被判废），检查 rejects.jsonl")
    return rows


def _gui_row(tool: str, st: Dict[str, Any], spaces: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    action = st.get("action")
    obs = st.get("observation") or {}
    verdict = (st.get("gate") or {}).get("verdict")
    reason = (st.get("gate") or {}).get("reason")
    call_id = "g%05d" % int(st.get("step") or 0)
    frame = st.get("frame") or {}
    sw = st.get("software")

    if action == "launch_target":
        return None

    # ---- 观测类：assistant 只能复述真实返回值 ----
    if action in ("capture", "inspect_window"):
        args = dict(st.get("args") or {})
        if action == "capture":
            call_args = {"action": "capture"}
            if sw:
                call_args["software"] = sw
        else:
            call_args = {"action": "inspect_window", "software": sw or ""}
        evidence = _gui_evidence(obs, frame, spaces)
        msg_user = _gui_user_intent(action, sw, st.get("intent", ""))
        msgs = [{"role": "user", "content": msg_user},
                tool_call_msg(tool, call_args, call_id),
                tool_obs_msg(call_id, _slim_obs(obs, frame))]
        if verdict == "REJECTED":
            ans = ("这一步我不汇报画面内容：抓到的不是真实屏幕（判废原因：%s），"
                   "所以没有任何可视证据可引用。" % reason) if action == "capture" else \
                  ("探测返回不是成功态：%s，我不据此宣称软件在跑。" % reason)
        elif action == "capture":
            if frame.get("window_scoped"):
                ans = ("已抓取窗口画面：%s，尺寸 %sx%s，帧摘要 sha256=%s，坐标空间 %sx%s（与点击空间%s）。"
                       % (obs.get("target"), frame.get("width"), frame.get("height"),
                          str(frame.get("bytes_sha256"))[:12],
                          spaces.get("click_space", [None])[0], spaces.get("click_space", [None])[1],
                          "一致" if spaces.get("aligned") else "不一致"))
            else:
                ans = ("目标 %s 的窗口不存在，实际拿到的是整屏（target=%s，%sx%s）。"
                       "所以只能说「截到了屏幕」，不能说「截到了 %s 的窗口」。"
                       % (sw, obs.get("target"), frame.get("width"), frame.get("height"), sw))
        else:
            stt = obs.get("status")
            if stt == "not_running":
                ans = ("%s 没有运行中的进程，也没有可见窗口，因此既不能点它也不能假设能连上它。"
                       % SOFTWARE_CHANNEL.get(sw, {}).get("cn", sw))
            elif stt == "window_found":
                ans = ("%s 主窗句柄 %s、PID %s；可以用桌面通道操作。"
                       % (SOFTWARE_CHANNEL.get(sw, {}).get("cn", sw), obs.get("hwnd"), obs.get("pids")))
            else:
                ans = ("%s 进程在跑（PID %s）但没有可见主窗，%s；改用接口/无头通道，"
                       "不要对着不存在的窗口发键鼠。" % (SOFTWARE_CHANNEL.get(sw, {}).get("cn", sw),
                                                        obs.get("pids"), (obs.get("note") or "")[:120]))
        return _pack(family="observe_act_verify", software=sw or "desktop", system=SYSTEM_GUI,
                     messages=msgs + [{"role": "assistant", "content": ans}],
                     meta={"gui_action": action, "verdict": verdict or "ACCEPTED",
                           "evidence": evidence, "oracle": "real_desktop_recording",
                           "frame_sha256": frame.get("bytes_sha256")})

    # ---- 动作类：必须"动作后再观测"，且没有回读就不许说成功 ----
    if action in ("type_text", "click", "hotkey"):
        args = dict(st.get("args") or {})
        call_args = {"action": action}
        call_args.update({"text": args.get("text")} if action == "type_text" else
                         ({"keys": args.get("keys")} if action == "hotkey" else
                          {"x": args.get("x"), "y": args.get("y"),
                           "button": args.get("button", "left")}))
        landed = st.get("input_landed")
        readback = st.get("title_readback") or {}
        focus = st.get("focus_state") or {}
        owner = st.get("point_owner") or {}
        if verdict == "REJECTED":
            if reason == "focus_not_owned":
                ans = ("前台窗口不是我要操作的那个（PID %s），先聚焦再敲键盘——否则字会打进"
                       "用户正开着的窗口。这一步我没发输入。" % focus.get("foreground_pid"))
            elif reason == "click_point_not_owned":
                ans = ("落点 %s,%s 命中的是别人的窗口（PID %s），我不点。"
                       % (args.get("x"), args.get("y"), owner.get("pid")))
            elif reason in ("coordinate_out_of_bounds", "coordinate_spaces_disaligned",
                            "cursor_clamped_by_os"):
                ans = ("这个坐标不能直接发：%s。SetCursorPos 越界只会静默夹紧、不报错，"
                       "所以必须先做空间对齐/边界校验。" % reason)
            else:
                ans = "这一步被安全闸拦下（原因：%s），没有发出任何输入，我也不声称完成。" % reason
            return _pack(family="observe_act_verify", software=sw or "desktop", system=SYSTEM_GUI,
                         messages=[{"role": "user", "content": st.get("intent", "在桌面执行一个动作")},
                                   tool_call_msg(tool, call_args, call_id),
                                   tool_obs_msg(call_id, {"status": "refused", "reason": reason})],
                         meta={"gui_action": action, "verdict": "REJECTED", "refuse_reason": reason,
                               "oracle": "real_desktop_recording", "is_refusal": True})

        ans_bits = []
        if action == "type_text":
            if landed:
                ans_bits.append("已贴入 %s 个字符，并经回读确认内容命中（回读通道：%s）"
                                % (obs.get("length"), "窗口标题投影"))
            else:
                ans_bits.append("命令返回 staged=%s，但没有回读证明字落进了目标应用，"
                                "所以只能说「剪贴板已就绪」，不能说「已输入」"
                                % obs.get("clipboard_staged"))
        elif action == "click":
            ci = st.get("click_intent") or {}
            ans_bits.append("已在 %s,%s 发左键（画面像素与点击坐标%s）；落点归属已校验"
                            % (obs.get("x"), obs.get("y"),
                               "1:1" if not str(ci.get("note", "")).startswith("scaled") else "按比例换算"))
        else:
            ans_bits.append("组合键 %s 已发送（VK：%s），效果需由下一次抓屏确认"
                            % (obs.get("keys"), obs.get("vks")))
        ans_bits.append("在拿到下一次抓屏/接口回读之前，我不把「操作成功」当结论")
        msgs = [{"role": "user", "content": st.get("intent", "在桌面执行一个动作")},
                tool_call_msg(tool, call_args, call_id),
                tool_obs_msg(call_id, _slim_obs(obs, {})),
                {"role": "assistant", "content": "；".join(ans_bits) + "。"}]
        if st.get("after_action_frame"):
            msgs.insert(3, tool_obs_msg(call_id + "_v", _slim_obs(st["after_action_frame"], {})))
        return _pack(family="observe_act_verify", software=sw or "desktop", system=SYSTEM_GUI,
                     messages=msgs,
                     meta={"gui_action": action, "verdict": "ACCEPTED",
                           "input_landed": landed, "evidence": _gui_evidence(obs, {}, spaces),
                           "oracle": "real_desktop_recording"})
    return None


def _slim_obs(obs: Dict[str, Any], frame: Dict[str, Any]) -> Dict[str, Any]:
    keep = {k: v for k, v in obs.items() if k in
            ("status", "target", "software", "hwnd", "pids", "embedding_pids", "note",
             "width", "height", "output_path", "x", "y", "button", "double", "keys", "vks",
             "length", "channel", "clipboard_staged", "message", "fallback")}
    if frame:
        keep["frame_sha256"] = frame.get("bytes_sha256")
        keep["frame_size"] = [frame.get("width"), frame.get("height")]
    return keep


def _gui_evidence(obs: Dict[str, Any], frame: Dict[str, Any], spaces: Dict[str, Any]) -> Dict[str, Any]:
    return {"frame_sha256": frame.get("bytes_sha256"),
            "frame_source": frame.get("source"),
            "fallback": bool(obs.get("fallback")),
            "coordinate_aligned": spaces.get("aligned"),
            "click_space": spaces.get("click_space"),
            "frame_space": spaces.get("frame_space"),
            "delta_vs_prev": frame.get("delta_vs_prev")}


def _gui_user_intent(action: str, sw: Optional[str], raw_intent: str) -> str:
    if raw_intent:
        return raw_intent
    return {"capture": "截一下%s的画面" % (SOFTWARE_CHANNEL.get(sw, {}).get("cn", "桌面") if sw else "桌面"),
            "inspect_window": "看看%s现在在不在跑" % SOFTWARE_CHANNEL.get(sw, {}).get("cn", sw)}.get(action, "在桌面执行一步")


# ---------------------------------------------------------------- 族 5：六软件事实（接地）
SYSTEM_TOOL = (
    "你是 Virtu 工业软件智能体，驱动 SOLIDWORKS/AutoCAD/NX/CIMCO/VERICUT/斯沃六套软件。"
    "只能调用给定工具；参数自己按标准算，不许照抄示例值。"
    "没有工具返回值就不许声称完成，汇报必须逐字引用返回值里的字段。"
    "单位 mm、角度度、密度 g/cm3、应力 MPa。"
)
SYSTEM_GUI = (
    "你在本机桌面上通过截图与键鼠操作工业软件。坐标一律用截图画面的像素系。"
    "发键鼠之前必须先确认目标窗口存在且在前台；抓屏失败或被安全闸拦下时如实说没做成，"
    "不许描述你没看到的画面。每一次动作之后都要再一次抓屏或接口回读才算结论。"
)


def gen_six_software_facts(face: Dict[str, Any], rng: random.Random,
                           limit: int) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    cards = _load_sw_cards()
    for sw in SIX:
        meta = SOFTWARE_CHANNEL[sw]
        qa = [
            ("%s 该走哪条自动化通道？" % meta["cn"],
             "通道：%s。判据：完成后必须靠%s回读，不看返回值当成功。"
             % (meta["channel"], READBACK_TIER[sw])),
            ("%s 能不能直接用 COM 驱动？" % meta["cn"],
             "%s。可执行文件是 %s；完成判据是%s。"
             % ("可以：存在已注册的 Application COM 接口" if not meta["gui_needed"] else
                "不行：这条路已经被实测判死，硬试只会拿到假成功",
                meta["exe"], READBACK_TIER[sw])),
            ("%s 是只能靠鼠标键盘和读屏的吗？" % meta["cn"],
             "%s" % ("是：%s，所以只能桌面键鼠 + 抓屏；抓不到画面就必须承认看不到。" % meta["channel"]
                     if meta["gui_needed"] else
                     "不需要：优先走 %s，桌面键鼠只做兜底。" % meta["channel"])),
        ]
        for i, (q, a) in enumerate(qa):
            if len(rows) >= limit:
                break
            rows.append(_pack(family="six_software_facts", software=sw, system=SYSTEM_TOOL,
                              messages=[{"role": "user", "content": q},
                                        {"role": "assistant", "content": a}],
                              meta={"grounding": "channel_matrix", "point": i}))
    # 能力卡（只在 SW 有类型库 AST 接地的卡；其余软件不给可执行 API 声明，避免喂幻觉工具）
    for card in cards:
        if len(rows) >= limit:
            break
        if card.get("readiness") != "probed":
            continue  # documented-not-probed 一律不进训（对齐 render_for_injection 的做法）
        apis = "、".join("%s::%s" % (a.get("iface", ""), a.get("method", ""))
                         for a in (card.get("action") or []) if isinstance(a, dict))
        post = card.get("postconditions") or []
        silent = card.get("silent_failures") or []
        q = "在 SOLIDWORKS 里做「%s」，具体调哪个接口、怎么确认不是假成功？" % card.get("name", card.get("id"))
        a = ("调用面：%s。必须回读判据：%s。已知静默失败：%s。"
             % (apis or "（卡内未声明可执行接口）",
                "；".join(str(p.get("probe", "")) + "=" + str(p.get("expression", ""))
                          for p in post if isinstance(p, dict)) or "无",
                "；".join(str(s) for s in silent) or "无"))
        rows.append(_pack(family="six_software_facts", software="solidworks", system=SYSTEM_TOOL,
                          messages=[{"role": "user", "content": q},
                                    {"role": "assistant", "content": a}],
                          meta={"grounding": "capability_card_ast", "card_id": card.get("id")}))
    return rows


def _load_sw_cards() -> List[Dict[str, Any]]:
    p = os.path.join(REPO_ROOT, "knowledge_base", "six_software", "solidworks", "capability_cards.json")
    if not os.path.isfile(p):
        return []
    try:
        data = json.load(open(p, encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []
    return list(data.get("cards") or [])


# ---------------------------------------------------------------- 打包 + 闸门
def _pack(family: str, software: str, system: str, messages: List[Dict[str, Any]],
          meta: Dict[str, Any]) -> Dict[str, Any]:
    msgs = [{"role": "system", "content": system}] + list(messages)
    segs = sum(1 for m in msgs if m.get("role") == "assistant")
    return {"messages": msgs, "meta": {"family": family, "software": software,
                                       "loss_assistant_segments": segs, **meta}}


def verify_rows(rows: List[Dict[str, Any]], face: Dict[str, Any], tok: Any,
                eval_dirs: List[str], frame_dir: str) -> Dict[str, Any]:
    """入库前逐条复核；任一硬闸失败 -> GateError（R1/R3/R4/R5）。"""
    seen_keys: set[str] = set()
    dup = 0
    bad_frames = 0
    checked_frames = 0
    gui_rows = 0
    report = {"rows": 0, "by_family": {}, "by_software": {}, "multi_turn_ratio": 0.0,
              "dedup_dropped": 0, "frames_checked": 0, "frames_bad": 0,
              "contamination_hits": 0, "contamination_cases_loaded": 0,
              "contamination_checked": False, "contract_token_share": None,
              "tokenizer": getattr(tok, "_virtu_tok_name", "n/a")}
    sys_tokens_total = 0
    full_tokens_total = 0
    multi = 0

    contam = None
    if eval_dirs:
        try:
            sys.path.insert(0, os.path.join(REPO_ROOT, "virtu_eval"))
            import contamination_check as cc  # type: ignore

            cases = []
            for d in eval_dirs:
                if os.path.isdir(d):
                    cases.extend(cc.load_eval_cases(d))
            contam = (cc, cases) if cases else None
            if contam:
                report["contamination_checked"] = True
                report["contamination_cases_loaded"] = len(cases)
        except Exception as exc:  # noqa: BLE001
            print("[gate][WARN] 污染闸不可用：%r（本轮污染计数记为 not_checked）" % (exc,))

    for rec in rows:
        msgs = rec["messages"]
        fam = rec["meta"]["family"]
        # R1 工具面
        for m in msgs:
            for call in (m.get("tool_calls") or []):
                fn = call.get("function", {})
                argstr = fn.get("arguments")
                if not isinstance(argstr, str):
                    raise GateError("arguments 必须是 JSON 字符串（%s）" % fn.get("name"))
                try:
                    args = json.loads(argstr)
                except Exception as exc:  # noqa: BLE001
                    raise GateError("arguments 不是合法 JSON：%r" % (exc,)) from exc
                validate_call(face, fn.get("name", ""), args)
        # R3 帧真实存在
        if fam == "observe_act_verify":
            gui_rows += 1
            sha = rec["meta"].get("frame_sha256")
            if sha:
                checked_frames += 1
                cand = None
                for name in os.listdir(frame_dir) if os.path.isdir(frame_dir) else []:
                    if name.endswith(".png"):
                        p = os.path.join(frame_dir, name)
                        if _sha256_file(p)[:16] == sha[:16]:
                            cand = p
                            break
                if cand is None:
                    bad_frames += 1
                    raise GateError("桌面样本引用的帧 %s… 在 %s 里找不到真实文件（R3）"
                                    % (str(sha)[:12], frame_dir))
        # R4 污染
        if contam:
            cc_mod, cases = contam
            hit = cc_mod.check_sample({"messages": msgs}, cases, 0.6, True)
            if hit:
                report["contamination_hits"] += 1
        # 去重
        k = _prompt_key(rec)
        if k in seen_keys:
            dup += 1
            continue
        seen_keys.add(k)
        if sum(1 for m in msgs if m.get("role") == "tool") >= 1:
            multi += 1
        sys_txt = msgs[0]["content"] if msgs[0]["role"] == "system" else ""
        full_txt = json.dumps([{"r": m["role"], "c": m.get("content", "")} for m in msgs],
                               ensure_ascii=False)
        sys_tokens_total += n_tok(tok, sys_txt)
        full_tokens_total += n_tok(tok, full_txt)
        report["rows"] += 1
        report["by_family"][fam] = report["by_family"].get(fam, 0) + 1
        sw = rec["meta"].get("software", "cross")
        report["by_software"][sw] = report["by_software"].get(sw, 0) + 1

    report["dedup_dropped"] = dup
    report["frames_checked"] = checked_frames
    report["frames_bad"] = bad_frames
    report["multi_turn_ratio"] = round(multi / max(1, report["rows"]), 4)
    report["contract_token_share"] = round(sys_tokens_total / max(1, full_tokens_total), 4)
    report["tokens_total"] = full_tokens_total
    report["gui_rows"] = gui_rows

    if report["contamination_hits"]:
        raise GateError("R4 污染闸：%d 条与评测集重叠，必须为 0" % report["contamination_hits"])
    if report["multi_turn_ratio"] < 0.35:
        raise GateError("多轮（含 tool 返回值）比例只有 %.1f%%，低于 35%%："
                        "这套语料又退回「只会吐一个调用」的老路"
                        % (100 * report["multi_turn_ratio"]))
    if report["contract_token_share"] > 0.35:
        raise GateError("R5 契约头吃掉 %.1f%% 的 token（阈值 35%%），先把 system 压短"
                        % (100 * report["contract_token_share"]))
    return report


FAMILY_MINIMUMS = {"tool_route": 200, "tool_refusal": 60, "repair_loop": 60,
                  "observe_act_verify": 10, "six_software_facts": 15}


def build(out_dir: str, traces_dir: str, seed: int, limits: Dict[str, int],
          eval_dirs: List[str], selftest: bool) -> int:
    rng = random.Random(seed)
    face_clean, face = load_live_tool_face()
    tok, tok_name = load_tokenizer()
    tok = tag_tokenizer(tok, tok_name)
    print("[face] tools=%d tokenizer=%s" % (len(face), tok_name))

    traces, ledger = load_traces(traces_dir)
    frame_dir = os.path.join(traces_dir, "frames")

    per_family: Dict[str, List[Dict[str, Any]]] = {}
    per_family["tool_route"] = gen_tool_route(face, rng, limits["tool_route"] * 3)
    per_family["tool_refusal"] = gen_tool_refusal(face, rng, limits["tool_refusal"] * 3)
    per_family["repair_loop"] = gen_repair_loop(face, load_repair_oracle(),
                                                rng, limits["repair_loop"] * 2)
    per_family["observe_act_verify"] = gen_observe_act_verify(traces, ledger,
                                                              limits["observe_act_verify"])
    per_family["six_software_facts"] = gen_six_software_facts(face, rng,
                                                              limits["six_software_facts"] * 3)

    # 族内按"首条 user 归一化哈希"去重后裁剪到目标数，并统计重复率。
    # 这一步是本仓的老疤：合成语料看着上千行，实际只有 7 种形状。
    rows = []
    diversity: Dict[str, Dict[str, Any]] = {}
    for fam, fam_rows in per_family.items():
        seen: set[str] = set()
        uniq: List[Dict[str, Any]] = []
        shape_seen: set[str] = set()
        for r in fam_rows:
            k = _prompt_key(r)
            if k in seen:
                continue
            seen.add(k)
            uniq.append(r)
            shape = re.sub(r"[-\d.]+", "#", _norm_text(
                next((m["content"] for m in r["messages"] if m["role"] == "user"), "")))[:120]
            shape_seen.add(shape)
        take = min(len(uniq), limits[fam])
        rows.extend(uniq[:take])
        diversity[fam] = {"generated": len(fam_rows), "unique_prompts": len(uniq),
                          "kept": take, "distinct_shapes": len(shape_seen),
                          "dup_rate": round(1.0 - len(uniq) / max(1, len(fam_rows)), 4)}
    report_diversity = diversity

    if selftest:
        return _run_selftest(face, tok, rows, ledger, frame_dir, eval_dirs)
    report = verify_rows(rows, face, tok, eval_dirs, frame_dir)
    report["diversity"] = report_diversity

    for fam, need in FAMILY_MINIMUMS.items():
        got = report["by_family"].get(fam, 0)
        if got < need:
            raise GateError("族 %s 只有 %d 条，低于最低要求 %d 条" % (fam, got, need))

    train_dir = os.path.join(out_dir, "train")
    os.makedirs(train_dir, exist_ok=True)
    out_jsonl = os.path.join(train_dir, "virtu_engine_agent_v1.jsonl")
    if os.path.exists(out_jsonl):
        os.remove(out_jsonl)  # 绝不允许追加污染上一轮字节
    with open(out_jsonl, "w", encoding="utf-8", newline="\r\n") as f:
        for rec in rows:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    sha = _sha256_file(out_jsonl)

    manifest = {
        "version": "virtu_engine_agent_v1",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "seed": seed,
        "format": "chatml_messages_with_tool_calls",
        "toolcall_strategy": "in_train",
        "rows_total": len(rows),
        "rows_verified": report["rows"],
        "sha256": sha,
        "report": report,
        "sources": {
            "live_tool_face": {"module": "bridges/tool_calling_specs.py",
                               "tools": sorted(face.keys())},
            "repair_oracle": {"module": "scripts/sw_flange_demo.py",
                              "fns": ["validate", "analytic_dv", "resolve_params"]},
            "desktop_traces": {"dir": traces_dir.replace("\\", "/"),
                               "ledger_sha256": _sha256_file(os.path.join(traces_dir, "ledger.json")),
                               "n_steps": len(traces),
                               "coordinate_spaces": ledger.get("coordinate_spaces"),
                               "dpi_awareness": ledger.get("dpi_awareness")},
            "capability_cards": {"dir": "knowledge_base/six_software/solidworks",
                                 "n_cards_loaded": len(_load_sw_cards())},
        },
        "eval_isolation": {"dirs": eval_dirs, "hits": report["contamination_hits"],
                            "checked": report.get("contamination_checked"),
                            "cases_loaded": report.get("contamination_cases_loaded")},
        "diversity": report.get("diversity", {}),
        "known_limits": [
            "tool_route 的 observation 是确定性解析回读（_stub_evidence），不是 SOLIDWORKS 实测体积；"
            "上线前必须由 scripts/model_drives_solidworks.py 那类监考环换成真回读",
            "只有 SOLIDWORKS 有类型库接地的能力卡；其余五个软件的可执行 API 声明故意不进训",
            "observe_act_verify 的轨迹来自自建 Tk 探针窗口与桌面巡检，尚未覆盖真实 CAD 对话框",
        ],
        "next_gate": "python scripts/train_engine_agent.py --preflight-only",
    }
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2, sort_keys=True)

    _write_report(os.path.join(out_dir, "BUILD_REPORT.md"), manifest, rows)
    print("[build] rows=%d verified=%d sha256=%s" % (len(rows), report["rows"], sha[:16]))
    print("[build] families=%s" % json.dumps(report["by_family"], sort_keys=True))
    print("[build] multi_turn=%.1f%% contract_head=%.1f%% dedup_dropped=%d"
          % (100 * report["multi_turn_ratio"], 100 * report["contract_token_share"],
             report["dedup_dropped"]))
    print("[build] -> %s" % out_jsonl.replace("\\", "/"))
    return 0


def _write_report(path: str, manifest: Dict[str, Any], rows: List[Dict[str, Any]]) -> None:
    rep = manifest["report"]
    lines = ["# 全面工程能力语料装配报告（virtu_engine_agent_v1）", "",
             "- 生成时间：%s / seed=%s" % (manifest["created_at"], manifest["seed"]),
             "- 行数：%d（复核入库 %d，去重丢弃 %d）" % (manifest["rows_total"], rep["rows"], rep["dedup_dropped"]),
             "- 训练文件 sha256：`%s`" % manifest["sha256"],
             "- 分词器：%s" % rep["tokenizer"],
             "- 契约头 token 占比：**%.1f%%**（阈值 35%%；历史 virtu_fix_v1 是 47.1%%）" % (100 * rep["contract_token_share"]),
             "- 多轮含工具返回值比例：**%.1f%%**（阈值 35%%）" % (100 * rep["multi_turn_ratio"]),
             "- 评测集污染命中：%d（要求 0；闸已加载评测条 %d 条，checked=%s；隔离目录：%s）"
             % (rep["contamination_hits"], rep.get("contamination_cases_loaded", 0),
                rep.get("contamination_checked"), "、".join(manifest["eval_isolation"]["dirs"])),
             "- 桌面真帧校验：检查 %d 张，判废 %d 张" % (rep["frames_checked"], rep["frames_bad"]),
             "", "## 各族条数", ""]
    for fam in FAMILIES:
        lines.append("- `%s`：%d 条" % (fam, rep["by_family"].get(fam, 0)))
    lines += ["", "## 六个软件覆盖", ""]
    for sw, n in sorted(rep["by_software"].items()):
        lines.append("- %s：%d 条" % (sw, n))
    lines += ["", "## 坐标空间实测（桌面闭环的前提）", "",
              "```json", json.dumps(manifest["sources"]["desktop_traces"].get("coordinate_spaces"),
                                   ensure_ascii=False, indent=2), "```",
              "", "## 已知限制（不许当成已解决）", ""]
    lines += ["%d. %s" % (i + 1, t) for i, t in enumerate(manifest["known_limits"])]
    lines += ["", "## 样例（每族一条，截断显示）", ""]
    seen = set()
    for r in rows:
        fam = r["meta"]["family"]
        if fam in seen:
            continue
        seen.add(fam)
        txt = json.dumps(r["messages"], ensure_ascii=False)
        lines += ["### %s" % fam, "", "```", txt[:900] + ("…" if len(txt) > 900 else ""), "```", ""]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ---------------------------------------------------------------- 埋缺陷自证（R1/R3/R4/R5 真的会红）
def _run_selftest(face: Dict[str, Any], tok: Any, rows: List[Dict[str, Any]],
                  ledger: Dict[str, Any], frame_dir: str, eval_dirs: List[str]) -> int:
    """把缺陷埋进去，验证闸门真的会拦——绿灯必须先被证明"会红"才算数。"""
    import copy

    results: List[Tuple[str, bool, str]] = []

    def expect_fail(name: str, fn, needle: str) -> None:
        try:
            fn()
        except GateError as exc:
            ok = needle in str(exc) or len(str(exc)) > 4
            results.append((name, ok, str(exc)[:160]))
        except Exception as exc:  # noqa: BLE001
            results.append((name, False, "wrong exception: %r" % (exc,)))
        else:
            results.append((name, False, "闸没红：缺陷被放行了"))

    def first_tool_row():
        for r in rows:
            for m in r["messages"]:
                if m.get("tool_calls"):
                    return copy.deepcopy(r)
        raise GateError("本轮没有带 tool_calls 的行，自检无从埋缺陷")

    bad = first_tool_row()
    for m in bad["messages"]:
        for call in (m.get("tool_calls") or []):
            call["function"]["name"] = "cadcam_make_it_happen"
        if m.get("tool_calls"):
            break
    expect_fail("R1 幻觉工具名", lambda: verify_rows([bad], face, tok, [], frame_dir), "幻觉工具名")

    bad2 = first_tool_row()
    for m in bad2["messages"]:
        if m.get("tool_calls"):
            m["tool_calls"][0]["function"]["arguments"] = {"action": "model_flange"}
            break
    expect_fail("R1b arguments 不是 JSON 字符串",
                lambda: verify_rows([bad2], face, tok, [], frame_dir), "JSON")

    gui = next((copy.deepcopy(r) for r in rows if r["meta"]["family"] == "observe_act_verify"), None)
    if gui is None:
        results.append(("R3 桌面帧取证", False, "本轮没有 observe_act_verify 行可测"))
    else:
        gui["meta"]["frame_sha256"] = "deadbeef" * 8
        expect_fail("R3 伪造截图引用", lambda: verify_rows([gui], face, tok, [], frame_dir), "找不到真实文件")

    thin = [r for r in rows if r["meta"]["family"] == "six_software_facts"][:40]
    expect_fail("R6 多轮比例不足", lambda: verify_rows(thin, face, tok, [], frame_dir), "多轮")

    fat = first_tool_row()
    fat["messages"][0]["content"] = ("很长的契约" * 1400)
    expect_fail("R5 契约头占比超限", lambda: verify_rows([fat], face, tok, [], frame_dir), "契约头")

    bad_action = first_tool_row()
    for m in bad_action["messages"]:
        for call in (m.get("tool_calls") or []):
            args = json.loads(call["function"]["arguments"])
            if "action" in args:
                args["action"] = "do_everything"
                call["function"]["arguments"] = json.dumps(args, ensure_ascii=False)
    expect_fail("R1c action 不在枚举", lambda: verify_rows([bad_action], face, tok, [], frame_dir), "枚举")

    print("\n[selftest] 埋缺陷 %d 项：" % len(results))
    all_ok = True
    for name, ok, detail in results:
        print("  %-28s %s  %s" % (name, "会红 OK" if ok else "!! 未拦住", detail))
        all_ok = all_ok and ok
    print("[selftest] verdict=%s" % ("GATES_BITE" if all_ok else "SOME_GATE_IS_BLIND"))
    return 0 if all_ok else 7


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="装配全面工程能力语料（四族 + 真桌面轨迹）")
    ap.add_argument("--out", default=os.path.join(REPO_ROOT, "data", "train", "virtu_engine_agent_v1"))
    ap.add_argument("--traces", default=os.path.join(REPO_ROOT, "data", "desktop_traces", "2026-11-04"))
    ap.add_argument("--seed", type=int, default=20261104)
    ap.add_argument("--rows", type=int, default=3000, help="目标总行数（按族比例分配）")
    ap.add_argument("--selftest", action="store_true", help="埋缺陷自证闸门会红")
    ap.add_argument("--no-eval-isolation", action="store_true",
                    help="跳过污染闸（只允许在离线排查时用，会打 WARN）")
    args = ap.parse_args(argv)

    eval_dirs = [] if args.no_eval_isolation else [
        os.path.join(REPO_ROOT, "data", "benchmark", "virtu_eval_v1"),
        os.path.join(REPO_ROOT, "data", "benchmark", "virtu_eval_phys_v1"),
        os.path.join(REPO_ROOT, "data", "benchmark", "virtu_fix_v1"),
    ]
    if not eval_dirs:
        print("[gate][WARN] 污染闸被关闭：产物不得用于训练")

    share = {"tool_route": 0.40, "tool_refusal": 0.10, "repair_loop": 0.30,
             "observe_act_verify": 0.08, "six_software_facts": 0.12}
    limits = {k: max(12, int(args.rows * v)) for k, v in share.items()}

    try:
        return build(args.out, args.traces, args.seed, limits, eval_dirs, args.selftest)
    except GateError as exc:
        print("\n[GATE FATAL] %s" % exc)
        print("[GATE FATAL] 拒绝产出。原因不是「脚本没跑通」，而是「跑通了但证据不足」。")
        return 8


if __name__ == "__main__":
    raise SystemExit(main())
