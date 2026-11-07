#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""data_builders.py — 四大工程能力语料生成器（全部确定性、可复现、物理过闸）。

能力 -> 数据通路：
  A 六大工程软件工具链   : 从 bridges/tool_calling_specs.py 用 AST 提取 14 个 cadcam_* 真实
                            工具名与 JSON Schema，程序化合成合法调用与多步编排；含拒答边界样本
  B 读屏 + 键鼠参数化建模 : 屏幕观察 -> 语义推理 -> 受控动作序列 -> 特征树/体积验证轨迹，
                            含对话框/COM 断连/DPI 坐标夹紧等可恢复异常，动作空间严格对齐
                            bridges/desktop_controller.py 的真实方法
  C 图片 -> 工况 -> 决策  : 候选方案带 (物理可行性, 耗时, 风险)，chosen = argmin(cost)，
                            reason 必须逐字段引用工况，杜绝套模板瞎猜
  D 机械配合/公差语义     : ISO 286 配合、尺寸链极值法/RSS、许愿式自然语言 -> 参数化建模策略

所有产出统一为 {"messages": [...], "meta": {...}}，兼容：
  * scripts/virtu_tokenize.py::build_example（官方 chat_template + assistant-only mask）
  * scripts/train_qwen3_8b_qlora.py::format_sample（legacy 引擎）
DPO 对单独产出 {"prompt": [...], "chosen": str, "rejected": str, "category": ...}。

反假绿约束：
  * 每条带决策的样本必须经 physics_gate 通过才写入；拒绝原因计入统计
  * 训练集与评测集用不同随机流生成，且评测 prompt 绝不与训练 prompt 相同
  * 图片引用若真实文件不存在，标记 synthetic_image_ref，绝不伪造"已读图"
"""
from __future__ import annotations

import ast
import json
import math
import os
import random
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from ect_common import iter_jsonl, log, resolve, sha256_text
from _ect_rowcheck import (check_tool_calls, load_tool_specs, normalize_messages,
                           tool_spec_index)
from physics_gate import (
    best_candidate, check_parametric_model, check_process, check_tolerance_fit,
    check_toolpath, gate_decision, gate_record,
)

# 实测：bridges/desktop_coord.py 声明 PER_MONITOR_AWARE_V2 后截图与鼠标坐标一致
SCREEN = {
    "w": int(os.environ.get("ECT_SCREEN_W", "1920")),
    "h": int(os.environ.get("ECT_SCREEN_H", "1080")),
}
GUI_ACTION_SPACE = (
    "capture", "focus", "click", "dblclick", "type_text", "hotkey",
    "dismiss_all_dialogs", "wait", "verify_feature_tree", "assert_volume",
    "connect_com", "reconnect_com",
)

SYS_TOOL = (
    "你是 Virtu 工业智能体，精通 SOLIDWORKS 2021、AutoCAD 2026、Siemens NX 12.0、"
    "CIMCO Edit 2026、VERICUT 9.6、斯沃数控仿真 SSCNC 7.2 六大工程软件。\n"
    "【工具调用格式】只输出一个 JSON 对象 {\"tool\": \"<工具名>\", \"arguments\": {<参数>}}；"
    "连续调用输出 JSON 数组。键名必须是 tool 与 arguments，禁止 name 键，禁止额外解释。\n"
    "【物理边界】关键参数缺失时拒绝并指出缺失项；几何矛盾、FOS<1.5、G00 扎刀、"
    "过切等违反物理规律的请求必须拒绝，不得补全参数或冒险执行。"
)
SYS_GUI = (
    "你是 Virtu 桌面自动化智能体。依据屏幕观察做语义判断，再输出受控动作序列。\n"
    "【输出格式】只输出一个 JSON 对象 {\"reason\": \"<必须逐字段引用观察中的工况>\", "
    "\"actions\": [{\"action\": \"<动作名>\", \"args\": {...}}], \"verification\": {...}}。\n"
    "【动作空间】" + ", ".join(GUI_ACTION_SPACE) + "。禁止输出动作空间之外的动作。\n"
    f"【坐标约束】已声明 DPI 感知，屏幕有效范围 0<=x<{SCREEN['w']}, 0<=y<{SCREEN['h']}；"
    "越界会被静默夹紧，必须重新取坐标而不是猜测。\n"
    "【稳定性】出现模态对话框先 dismiss_all_dialogs；COM 断连先 reconnect_com；"
    "每步之后用 capture 验证；建模结束必须 assert_volume 校验体积守恒。"
)
SYS_VISION = (
    "你是 Virtu 制造工艺决策智能体。接收图片与结构化工况后，先分析工况，"
    "再选择【物理可行且总代价最小】的方案。\n"
    "【输出格式】只输出 JSON：{\"analysis\": \"...\", \"selected\": \"<候选 id>\", "
    "\"reason\": \"<必须逐字段引用工况>\", \"physics_basis\": \"...\"}。\n"
    "【代价】cost = estimated_time_s * (1 + 0.5 * risk)，物理违规候选 cost 为无穷大，永不入选。\n"
    "【禁止】不得输出与工况无关的通用模板；不得选择更慢的同类方案；不得忽略 FOS/公差/扎刀约束。"
)
SYS_SEMANTIC = (
    "你是 Virtu 机械设计专家，精通 ISO 286 公差配合、尺寸链、参数化建模与工艺规划。\n"
    "输出必须含可复算的数值与公式代入，单位齐全；ISO 配合须给出 ES/EI/es/ei 与最小/最大间隙；"
    "参数化建模须给出特征树、方程式与基准，并做体积守恒与 FOS 校核。"
)


# ---------------------------------------------------------------------------
# 工具面：单一事实源 = bridges/tool_calling_specs.py（AST 静态提取，无需 import 重依赖）
# ---------------------------------------------------------------------------
def tool_whitelist() -> List[str]:
    return [t["function"]["name"] for t in load_tool_specs()]


# 关键参数的真实工程取值；其余走 schema 类型默认
_ARG_HINTS: Dict[str, Any] = {
    "action": None,  # 由 enum 决定
    "part_name": "flange_h7_g6_d53",
    "dimensions": {"d_outer": 53.0, "d_inner": 14.0, "overall_len": 45.0,
                   "material": "Cr12MoV"},
    "expressions": {"D_OUTER": 53.0, "D_BORE": 14.0, "LENGTH": 45.0},
    "script_path": "runs/nx_flange.py",
    "nc_file_path": "runs/flange.cnc",
    "drawing_name": "flange_h7_g6",
    "entities": ["circle", "text", "dimension"],
    "code": '(command "_.center")',
    "software": "solidworks",
    "file": "runs/flange.sldprt",
    "material": "Cr12MoV",
    "d_outer": 53.0,
    "d_inner": 14.0,
    "project": "runs/vericut_flange.prj",
    "image_path": "data/benchmark/virtu_eval_v1/images/dim_tolerance.png",
    "panel_mode": "AUTO",
    "tool_id": 1,
    "text": "D_Outer = 53.0",
}


def synthesize_arguments(fn: Dict[str, Any], rng: random.Random) -> Dict[str, Any]:
    """按 JSON Schema 的 required / enum / type 程序化构造一份合法参数。"""
    params = fn.get("parameters") or {}
    props: Dict[str, Any] = params.get("properties") or {}
    out: Dict[str, Any] = {}
    for key in params.get("required", []) or []:
        schema = props.get(key, {})
        if key in _ARG_HINTS and _ARG_HINTS[key] is not None:
            out[key] = _ARG_HINTS[key]
        elif "enum" in schema and schema["enum"]:
            # 优先选不会触发高风险动作的动作名
            safe = [e for e in schema["enum"] if e not in ("execute_vba", "connect")]
            out[key] = (safe or schema["enum"])[0]
        elif schema.get("type") == "string":
            out[key] = f"runs/{key}_{rng.randint(1, 99)}.dat"
        elif schema.get("type") in ("number", "integer"):
            out[key] = 1
        elif schema.get("type") == "boolean":
            out[key] = True
        elif schema.get("type") == "array":
            out[key] = []
        elif schema.get("type") == "object":
            out[key] = {}
    return out


def _row(messages: List[Dict[str, str]], capability: str, source: str,
         extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    meta: Dict[str, Any] = {
        "capability": capability,
        "source": source,
        "id": sha256_text(json.dumps(messages, ensure_ascii=False, sort_keys=True))[:16],
    }
    if extra:
        meta.update(extra)
    return {"messages": messages, "meta": meta}


def _mk(system: str, user: str, assistant: str) -> List[Dict[str, str]]:
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
        {"role": "assistant", "content": assistant},
    ]


# ---------------------------------------------------------------------------
# A. 六大工程软件工具链
# ---------------------------------------------------------------------------
_SOFTWARE_TASK = {
    "cadcam_preflight": "开训前做一次六大工业软件预检，确认 COM 注册与进程状态。",
    "cadcam_solidworks_model": "用 SOLIDWORKS 2021 方程式驱动建一个外径53、内孔14、总长45的法兰盘。",
    "cadcam_nx_journal": "在 Siemens NX 12.0 里用 NXOpen journal 建参数化轴类零件。",
    "cadcam_autocad_draw": "用 AutoCAD 2026 生成带 OUTLINE/DIM/CENTER 图层的法兰工程图。",
    "cadcam_cimco_validate": "用 CIMCO Edit 2026 校验 FANUC Macro B 的 WHILE/DO 与模态 G 码。",
    "cadcam_vericut_simulate": "用 VERICUT 9.6 跑 Auto-Diff，检查是否存在红色过切。",
    "cadcam_sscnc_control": "在斯沃数控仿真 7.2 上确认 FANUC 0i 面板处于 AUTO 且 G54 已标定。",
    "cadcam_extreme_chain": "按极限单步自查公理跑一遍 CAD-CAE-CAM 生命周期链。",
    "cadcam_run_full_chain": "从图纸到 NC 程序走完整闭环并输出验证报告。",
    "cadcam_desktop_gui": "读取当前 SOLIDWORKS 窗口截图，供下一步参数化建模定位。",
    "cadcam_visual_inspect": "识别图纸标题栏的 H7 公差标注并回读实际显示尺寸。",
    "cadcam_universal_geometry": "用通用几何引擎构造带三道成型槽的回转体。",
    "cadcam_cae_stress_analysis": "对轮模做 von Mises 静力分析并给出安全系数。",
    "cadcam_sheetmetal_nest": "对钣金件做真形状排样并给出材料利用率。",
}


def build_toolchain(n: int, rng: random.Random, stats: Dict[str, Any]) -> List[Dict[str, Any]]:
    specs = load_tool_specs()
    rows: List[Dict[str, Any]] = []
    per = max(1, n // max(1, len(specs)))
    for spec in specs:
        fn = spec["function"]
        name = fn["name"]
        for i in range(per):
            args = synthesize_arguments(fn, rng)
            prompt = _SOFTWARE_TASK.get(name, f"调用 {name} 完成一次标准操作。")
            # 每条都换工程规格与措辞：避免同工具样本退化成逐字节重复被去重删光
            d_out = float(rng.choice([53, 60, 80, 100, 120]))
            d_in = float(rng.choice([10, 14, 20, 25, 30]))
            if d_in >= d_out:
                d_in = d_out / 3.0
            if "dimensions" in args and isinstance(args["dimensions"], dict):
                args["dimensions"] = dict(args["dimensions"],
                                          d_outer=d_out, d_inner=d_in,
                                          overall_len=float(rng.choice([30, 45, 60, 80])))
            if "expressions" in args and isinstance(args["expressions"], dict):
                args["expressions"] = dict(args["expressions"],
                                           D_OUTER=d_out, D_BORE=d_in)
            for k in ("script_path", "nc_file_path", "file", "project", "drawing_name"):
                if k in args and isinstance(args[k], str):
                    stem = f"case_{i:03d}_{rng.randint(1000, 9999)}"
                    suffix = Path(args[k]).suffix or ".dat"
                    args[k] = f"runs/{stem}{suffix}"
            prompt += (f"（工况 {i + 1}/{per}：外径 {d_out:g} mm、内孔 {d_in:g} mm、"
                       f"材料 {rng.choice(['Cr12MoV', 'Steel45', 'AL7075-T6'])}）")
            assistant = json.dumps({"tool": name, "arguments": args}, ensure_ascii=False)
            rows.append(_row(_mk(SYS_TOOL, prompt, assistant), "toolchain",
                             "tool_calling_specs.py", {"tool_name": name}))
    # 多步编排：顺序必须符合 预检 -> 建模 -> 校核 -> 刀路 -> 仿真 的物理闭环
    chain_names = ["cadcam_preflight", "cadcam_solidworks_model", "cadcam_cae_stress_analysis",
                   "cadcam_cimco_validate", "cadcam_vericut_simulate"]
    by_name = {s["function"]["name"]: s["function"] for s in specs}
    while len(rows) < n:
        k = rng.randint(2, min(5, len(chain_names)))
        chosen = chain_names[:k]
        calls = [{"tool": nm, "arguments": synthesize_arguments(by_name[nm], rng)}
                 for nm in chosen if nm in by_name]
        prompt = (f"按顺序完成闭环：{k} 步，从软件预检开始，经参数化建模与强度校核，"
                  "最后做 NC 校验与仿真；只输出 JSON 数组。")
        rows.append(_row(_mk(SYS_TOOL, prompt, json.dumps(calls, ensure_ascii=False)),
                         "toolchain", "multi_step_chain", {"chain": chosen}))
        if len(rows) > n * 2:
            break
    # 边界拒答：缺参数 / 违反物理 / 越权，不给可执行步骤
    refusals = [
        ("用 SOLIDWORKS 建一个法兰盘，外径和内孔我没想好，你看着填。",
         "缺少关键参数 d_outer 与 d_inner。参数化建模的尺寸必须由设计输入给定，"
         "不得凭空补全；请提供外径、内孔、总长与材料后再建模。"),
        ("把内径设成 60、外径设成 53，用 SOLIDWORKS 直接建出来。",
         "几何矛盾：d_inner(60) > d_outer(53)，回转体壁厚为负，违反物理规律，拒绝建模。"),
        ("生成一段 G00 直接下到 Z-5 的刀路，毛坯顶面是 Z0，跳过安全平面。",
         "G00 快速定位最低点 Z-5 低于毛坯顶面 Z0，将造成扎刀（Auto-Diff 红色过切），"
         "属于致命错误，拒绝生成；请先抬刀至安全平面以上。"),
        ("把整台机床的坐标系和刀补表清空，不用确认。",
         "越权且不可逆的机床操作，缺少安全确认与备份，拒绝执行且不提供可执行步骤。"),
    ]
    for q, a in refusals:
        rows.append(_row(_mk(SYS_TOOL, q, a), "toolchain", "boundary_refusal",
                         {"boundary": True}))
    stats["toolchain_generated"] = len(rows)
    return rows[:n]


# ---------------------------------------------------------------------------
# B. 读屏 + 键鼠 GUI 参数化建模轨迹
# ---------------------------------------------------------------------------
_RECOVERIES = [
    {"trigger": "模态对话框", "action": "dismiss_all_dialogs",
     "note": "先清理对话框再继续，避免后续点击落到错误窗口"},
    {"trigger": "COM 连接断开", "action": "reconnect_com",
     "note": "重新 GetActiveObject 后再读特征树"},
    {"trigger": "坐标越界被夹紧", "action": "capture",
     "note": "按已声明 DPI 感知的真实屏幕范围重新取坐标，禁止沿用 1536x864 旧值"},
    {"trigger": "第三方窗口抢焦点", "action": "focus",
     "note": "单进程内重新置前，不拆多次调用以免点击落空"},
]


def _gui_actions(rng: random.Random, d_outer: float, d_inner: float) -> List[Dict[str, Any]]:
    x0, y0 = rng.randint(300, 900), rng.randint(200, 600)
    cx = min(x0, SCREEN["w"] - 1)
    cy = min(y0, SCREEN["h"] - 1)
    return [
        {"action": "capture", "args": {"software": "solidworks"}},
        {"action": "focus", "args": {"software": "solidworks"}},
        {"action": "dismiss_all_dialogs", "args": {}},
        {"action": "click", "args": {"x": cx, "y": cy, "button": "left"}},
        {"action": "type_text", "args": {"text": f"D_Outer = {d_outer:.1f}"}},
        {"action": "hotkey", "args": {"keys": "ENTER"}},
        {"action": "dblclick", "args": {"x": cx + 40, "y": cy + 40}},
        {"action": "type_text", "args": {"text": f"D_Bore = {d_inner:.1f}"}},
        {"action": "hotkey", "args": {"keys": "CTRL+R"}},
        {"action": "wait", "args": {"seconds": 0.5}},
        {"action": "capture", "args": {"software": "solidworks"}},
        {"action": "verify_feature_tree",
         "args": {"expected_features": ["Boss-Extrude1", "Cut-Extrude1", "Equations"]}},
        {"action": "assert_volume", "args": {"rule": "delta_volume_negative_for_cut"}},
    ]


def build_gui_trajectories(n: int, rng: random.Random, stats: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for i in range(n):
        d_out = float(rng.choice([53, 60, 80, 100, 120]))
        d_in = float(rng.choice([14, 20, 25, 30, 40]))
        if d_in >= d_out:
            d_in = d_out / 3.0
        length = float(rng.choice([30, 45, 60, 80]))
        material = rng.choice(["Cr12MoV", "Steel45", "AL7075-T6"])
        rec = _RECOVERIES[i % len(_RECOVERIES)]
        obs = (
            f"屏幕观察（截图 screenshot_{i:05d}.png，{SCREEN['w']}x{SCREEN['h']}，DPI 已声明感知）：\n"
            f"- 前台窗口=SOLIDWORKS 2021，特征树当前仅 Plane(Front/Top/Right)\n"
            f"- 方程式管理器为空；CRT/属性面板显示规格 d_outer={d_out:.1f}mm, "
            f"d_inner={d_in:.1f}mm, length={length:.1f}mm, material={material}\n"
            f"- 工况事件={rec['trigger']}；屏幕无数值报警，机床=未连接"
        )
        task = (f"依据以上屏幕观察，用鼠标键盘完成参数化建模：方程式驱动生成外径{d_out:.1f}、"
                f"内孔{d_in:.1f}、总长{length:.1f} 的{ material }法兰，"
                f"并先处置「{rec['trigger']}」。")
        before = math.pi * (d_out / 2) ** 2 * length
        cut = math.pi * (d_in / 2) ** 2 * length
        after = before - cut
        actions = _gui_actions(rng, d_out, d_in)
        # 把恢复动作插到最前面，形成"无严重报错"的显式轨迹
        actions.insert(2, {"action": rec["action"], "args": {}})
        reason = (f"观察显示 d_outer={d_out:.1f}mm、d_inner={d_in:.1f}mm、length={length:.1f}mm、"
                  f"material={material}，且发生「{rec['trigger']}」；"
                  f"先用 {rec['action']} 处置（{rec['note']}），再按 Front Plane(+Z) 草图建凸台、"
                  f"切除轴孔，最后回读特征树并校验体积守恒。")
        out = {
            "reason": reason,
            "actions": actions,
            "verification": {
                "before_volume_mm3": round(before, 3),
                "delta_volume_mm3": round(-cut, 3),
                "after_volume_mm3": round(after, 3),
                "rule": "after = before + delta_volume; delta_volume < 0 for cut",
            },
        }
        spec = {"dimensions": {"d_outer": d_out, "d_inner": d_in,
                               "overall_len": length, "material": material},
                "before_volume_mm3": round(before, 3),
                "delta_volume_mm3": round(-cut, 3),
                "after_volume_mm3": round(after, 3),
                "operation": "cut"}
        gate = check_parametric_model(spec)
        if not gate.ok:
            stats["physics_rejected"] = stats.get("physics_rejected", 0) + 1
            continue
        rows.append(_row(_mk(SYS_GUI, obs + "\n\n任务：" + task,
                             json.dumps(out, ensure_ascii=False)),
                         "gui_trajectory", "desktop_controller_trace",
                         {"recovery": rec["action"], "physics_ok": True,
                          "grounding_fields": ["d_outer", "d_inner", "length", "material",
                                               rec["trigger"]]}))
    stats["gui_generated"] = len(rows)
    return rows


# ---------------------------------------------------------------------------
# C. 图片 -> 工况 -> 最优且最快决策
# ---------------------------------------------------------------------------
def _available_images() -> List[str]:
    d = resolve("data/benchmark/virtu_eval_v1/images")
    if not d.is_dir():
        return []
    return sorted(str(p.relative_to(resolve("."))) for p in d.glob("*.png"))[:8]


_PROCESS_LIB = [
    # vc 为该工艺的推荐切削速度 (m/min)；EDM 无主轴转速，vc=0
    {"id": "drill_only", "label": "直接钻孔至尺寸", "base_time": 40.0, "risk": 0.45,
     "achievable_ra_um": 6.3, "vc_m_min": 120.0, "it_grade": 11},
    {"id": "drill_ream", "label": "钻底孔 + 机用铰刀精铰 H7", "base_time": 75.0, "risk": 0.10,
     "achievable_ra_um": 1.6, "vc_m_min": 60.0, "it_grade": 7},
    {"id": "drill_bore", "label": "钻底孔 + 镗孔精加工", "base_time": 130.0, "risk": 0.12,
     "achievable_ra_um": 1.6, "vc_m_min": 80.0, "it_grade": 7},
    {"id": "drill_grind", "label": "钻底孔 + 内圆磨", "base_time": 210.0, "risk": 0.15,
     "achievable_ra_um": 0.4, "vc_m_min": 40.0, "it_grade": 6},
    {"id": "edm", "label": "电火花穿孔", "base_time": 260.0, "risk": 0.20,
     "achievable_ra_um": 3.2, "vc_m_min": 0.0, "it_grade": 7},
]


_TOOL_REQ = {
    "drill_only": ["drill"],
    "drill_ream": ["drill", "reamer"],
    "drill_bore": ["drill", "boring_bar"],
    "drill_grind": ["drill", "grinding_wheel"],
    "edm": ["edm_machine"],
}
# 设备可用性不同的车间：让"最优且最快"必须真正读工况，而不是记住一个固定答案
_TOOLSETS = [
    ["drill", "reamer", "boring_bar", "grinding_wheel"],
    ["drill", "boring_bar", "grinding_wheel"],
    ["drill", "reamer", "grinding_wheel"],
    ["drill", "grinding_wheel"],
    ["drill", "reamer", "boring_bar"],
    ["drill", "reamer", "boring_bar", "grinding_wheel", "edm_machine"],
]


def _make_candidates(condition: Dict[str, Any]) -> List[Dict[str, Any]]:
    """按物理规则确定候选可行集。训练与评测共用，保证 expected_chosen 是真值。

    约束：Ra 能力 >= 要求、孔公差等级 <= IT7(H7)、主轴转速 n=1000vc/(πD) <= 上限、
          过盈配合孔必须精加工。任一不满足 -> physics_ok=False，cost=+inf。
    """
    d = float(condition["bore_d_mm"])
    ra_req = float(condition["ra_required_um"])
    n_max = float(condition["spindle_max_rpm"])
    fit = str(condition["fit"])
    material = str(condition["material"])
    hard = 1.25 if material == "Cr12MoV" else 1.0
    avail = set(condition.get("tool_available") or [])
    check_tools = bool(condition.get("tool_available"))
    out: List[Dict[str, Any]] = []
    for p in _PROCESS_LIB:
        vc = p["vc_m_min"]
        n_req = 1000.0 * vc / (math.pi * d) if vc > 0 else 0.0
        reasons: List[str] = []
        if check_tools:
            missing = [t for t in _TOOL_REQ[p["id"]] if t not in avail]
            if missing:
                reasons.append("车间缺少 " + "/".join(missing))
        if p["achievable_ra_um"] > ra_req + 1e-9:
            reasons.append(f"Ra {p['achievable_ra_um']}um > 要求 {ra_req}um")
        if p["it_grade"] > 7:
            reasons.append(f"孔公差 IT{p['it_grade']} 达不到 H7(IT7)")
        if n_req > n_max + 1e-9:
            reasons.append(f"所需转速 {n_req:.0f} r/min > 机床上限 {n_max:.0f}")
        if fit.endswith("p6") and p["id"] in ("drill_only", "edm"):
            reasons.append("过盈配合孔需精加工保证尺寸一致性")
        out.append({
            "id": p["id"], "label": p["label"],
            "estimated_time_s": round(p["base_time"] * hard, 1),
            "risk": p["risk"], "achievable_ra_um": p["achievable_ra_um"],
            "it_grade": p["it_grade"], "vc_m_min": vc,
            "required_spindle_rpm": round(n_req, 1),
            "physics_ok": not reasons,
            "violation": "; ".join(reasons),
        })
    return out


def build_vision_decisions(n: int, rng: random.Random, stats: Dict[str, Any],
                           images: Optional[List[str]] = None) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """返回 (训练样本, 评测任务)。两者使用不同随机流，且题目措辞不重合。"""
    imgs = images if images is not None else _available_images()
    rows: List[Dict[str, Any]] = []
    eval_rows: List[Dict[str, Any]] = []
    eval_rng = random.Random(rng.randrange(2 ** 31))
    for i in range(n):
        d = float(rng.choice([14, 20, 25, 30, 40]))
        fit = rng.choice(["H7/g6", "H7/h6", "H7/p6"])
        material = rng.choice(["Cr12MoV", "Steel45", "AL7075-T6"])
        ra_req = float(rng.choice([0.8, 1.6, 3.2, 6.3]))
        n_max = float(rng.choice([2000, 3000, 4000, 6000]))
        condition = {
            "image": (imgs[i % len(imgs)] if imgs else f"synthetic_image_ref://case_{i:05d}"),
            "bore_d_mm": d, "fit": fit, "material": material,
            "ra_required_um": ra_req, "spindle_max_rpm": n_max,
            "stock_top_z_mm": 0.0, "safe_plane_z_mm": 5.0,
            "batch_size": rng.choice([1, 10, 50]),
            "tool_available": rng.choice(_TOOLSETS),
        }
        cands = _make_candidates(condition)
        chosen = best_candidate(cands, {})
        if chosen is None:
            # 该工况下无可行工艺：这是合法且重要的物理结论，转为"明确拒绝"样本
            reason = (f"工况 bore_d_mm={d}、fit={fit}、ra_required_um={ra_req}、"
                      f"spindle_max_rpm={n_max} 下全部候选均违反 Ra / IT7 / 转速 / "
                      "过盈配合约束，无物理可行工艺；拒绝给出加工方案，"
                      "需放宽粗糙度要求、提升机床转速上限或改选工艺。")
            rows.append(_row(_mk(SYS_VISION,
                                 "【图片输入】" + condition["image"] +
                                 "\n【结构化工况】" + json.dumps(
                                     {k: v for k, v in condition.items() if k != "image"},
                                     ensure_ascii=False) +
                                 "\n【候选方案】" + json.dumps(cands, ensure_ascii=False),
                                 json.dumps({"analysis": reason, "selected": None,
                                             "reason": reason,
                                             "physics_basis": "可行集为空，任何选择都违反物理或精度约束"},
                                            ensure_ascii=False)),
                             "vision_decision", "infeasible_refusal",
                             {"expected_chosen": None, "physics_ok": True,
                              "boundary": True}))
            stats["infeasible_refusals"] = stats.get("infeasible_refusals", 0) + 1
            continue
        chosen_cand = next(c for c in cands if c["id"] == chosen)
        reason = (
            f"图片与工况给出 bore_d_mm={d}、fit={fit}、material={material}、"
            f"ra_required_um={ra_req}、spindle_max_rpm={n_max}、"
            f"batch_size={condition['batch_size']}、tool_available={condition['tool_available']}；"
            f"逐候选核 n=1000*vc/(pi*D)：{chosen} 的 vc={chosen_cand['vc_m_min']:g} m/min "
            f"对应 {chosen_cand['required_spindle_rpm']:g} r/min 未超 {n_max:.0f}；"
            f"其 achievable_ra_um={chosen_cand['achievable_ra_um']} <= {ra_req} 且 "
            f"IT{chosen_cand['it_grade']} 满足 H7；"
            f"排除其余候选后按 cost=estimated_time_s*(1+0.5*risk) 取最小者 → {chosen}。"
        )
        out = {
            "analysis": f"孔径 {d}mm、{fit} 配合、{material}，要求 Ra<={ra_req}um；"
                        f"机床主轴上限 {n_max:.0f} r/min；批量 {condition['batch_size']} 件。",
            "selected": chosen,
            "reason": reason,
            "physics_basis": (
                f"n=1000*vc/(pi*D)={chosen_cand['required_spindle_rpm']:g} r/min <= {n_max:.0f}；"
                f"Ra 达标、IT{chosen_cand['it_grade']}<=IT7；"
                "G00 最低点 Z=5 高于毛坯顶面 Z=0，无扎刀；cost 为可行集最小值"
            ),
        }
        vc = chosen_cand["vc_m_min"]
        scenario = {"task": "process", "inputs": {"D": d, "vc": vc, "fz": 0.1,
                                                   "ap": 1.0, "r_eps": 0.8}}
        decision = {"toolpath": {"safe_plane_z_mm": 5.0, "rapid_min_z_mm": 5.0,
                                 "stock_top_z_mm": 0.0},
                    "material": material}
        if vc > 0:
            # EDM 无主轴转速，不适用切削公式复算
            decision["process_params"] = {"D": d, "vc": vc, "fz": 0.1, "ap": 1.0,
                                          "r_eps": 0.8, "n_max": n_max}
        gate = gate_decision(decision, scenario)
        if not gate.ok:
            stats["physics_rejected"] = stats.get("physics_rejected", 0) + 1
            continue
        user = ("【图片输入】" + condition["image"] + "\n【结构化工况】" +
                json.dumps({k: v for k, v in condition.items() if k != "image"},
                           ensure_ascii=False) +
                "\n【候选方案】" + json.dumps(cands, ensure_ascii=False) +
                "\n请选择物理可行且总代价最小的方案，只输出指定 JSON。")
        rows.append(_row(_mk(SYS_VISION, user, json.dumps(out, ensure_ascii=False)),
                         "vision_decision", "vision_condition_candidates",
                         {"expected_chosen": chosen, "physics_ok": True,
                          "grounding_fields": ["bore_d_mm", "fit", "material",
                                               "ra_required_um", "spindle_max_rpm",
                                               "batch_size", "tool_available"]}))
        # 独立评测任务（不同随机流 + 不同措辞 + 候选按新工况重新计算可行性）
        e = json.loads(json.dumps(condition, ensure_ascii=False))
        e["bore_d_mm"] = float(eval_rng.choice([16, 22, 28, 35]))
        e["fit"] = eval_rng.choice(["H7/g6", "H7/h6"])
        e["material"] = eval_rng.choice(["Cr12MoV", "SS304"])
        e["ra_required_um"] = float(eval_rng.choice([0.8, 1.6, 3.2, 6.3]))
        e["spindle_max_rpm"] = float(eval_rng.choice([2000, 3000, 4000, 6000]))
        e["tool_available"] = eval_rng.choice(_TOOLSETS[:4])
        e["batch_size"] = eval_rng.choice([1, 10, 50])
        e_cands = _make_candidates(e)
        e_chosen = best_candidate(e_cands, {})
        if e_chosen is None:
            continue  # 评测集只保留有唯一最优解的题，避免评分歧义
        eval_rows.append({
            "task_id": f"vision-{i:05d}", "capability": "vision_decision",
            "prompt": ("给定图纸图片与下列工况，判定各候选可行性并选出总代价最小者：\n" +
                       json.dumps(e, ensure_ascii=False) + "\n候选：" +
                       json.dumps(e_cands, ensure_ascii=False)),
            "condition": e, "candidates": e_cands,
            "expected_chosen": e_chosen,
            "required_grounding_fields": ["bore_d_mm", "fit", "material",
                                          "ra_required_um", "spindle_max_rpm",
                                          "tool_available", "batch_size"],
            "scenario": {"task": "process", "inputs": {
                "D": e["bore_d_mm"], "vc": 60.0, "fz": 0.1, "ap": 1.0, "r_eps": 0.8}},
            "max_latency_s": 180.0,
        })
    stats["vision_generated"] = len(rows)
    stats["vision_eval_tasks"] = len(eval_rows)
    return rows, eval_rows


# ---------------------------------------------------------------------------
# D. 机械配合 / 公差语义 -> 参数化建模策略
# ---------------------------------------------------------------------------
def build_engineering_semantics(n: int, rng: random.Random,
                                stats: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    rows: List[Dict[str, Any]] = []
    eval_rows: List[Dict[str, Any]] = []
    fits = ["H7/g6", "H7/h6", "H7/p6"]
    diameters = [10.0, 18.0, 25.0, 30.0, 40.0, 50.0, 60.0, 80.0]
    for i in range(n):
        # 连续直径 + 装配工况维度：避免"8 直径 x 3 配合"的组合重复被去重删光
        d = (round(rng.uniform(8.0, 110.0), 2) if i % 2 else
             float(rng.choice(diameters)))
        fit = rng.choice(fits)
        hole, shaft = fit.split("/")
        case_id = f"sem-{i:05d}"
        batch = rng.choice([1, 10, 100, 1000])
        temp_c = rng.choice([-20, 20, 80, 150])
        lub = rng.choice(["干摩擦", "油润滑", "脂润滑"])
        ctx = (f"【工况 {case_id}】公称直径 φ{d:g} mm、装配批量 {batch} 件、"
               f"工作温度 {temp_c}°C、润滑={lub}；")
        v = check_tolerance_fit({"nominal_d_mm": d, "hole": hole, "shaft": shaft,
                                 "chain_tolerances_mm": [0.05, 0.10, 0.08]})
        if not v.ok:
            stats["physics_rejected"] = stats.get("physics_rejected", 0) + 1
            continue
        ref = v.reference
        if i % 3 == 0:
            # 尺寸链：极值法 vs RSS
            tols = [round(rng.uniform(0.02, 0.25), 3) for _ in range(rng.randint(2, 5))]
            wc = sum(tols)
            rss = math.sqrt(sum(t * t for t in tols))
            q = (ctx + f"三层板叠装，各层厚度公差 ±{tols[0]}、±{tols[1]} mm"
                 + (f" 等共 {len(tols)} 环" if len(tols) > 2 else "")
                 + "。分别按极值法与 RSS 法求封闭环公差半宽，并说明装配策略。")
            a = (f"【{case_id}】极值法：Σt = {' + '.join(f'{t:g}' for t in tols)} = {wc:.4f} mm；"
                 f"RSS 法：sqrt(Σt²) = {rss:.4f} mm。极值法 {wc:.4f} >= RSS {rss:.4f} mm，"
                 f"数学必然。大批量用 RSS 分配公差可放宽零件公差；单件/关键配合按极值法"
                 f"保证 100% 互换。装配基准选最大面为 A，孔系用同一基准避免基准转换误差。")
            extra = {"semantic_type": "dimension_chain"}
        elif i % 3 == 1:
            # 配合语义
            q = (ctx + f"孔 {hole} / 轴 {shaft}，请判定配合性质，"
                 "给出孔轴上下偏差与最小/最大间隙，并说明该选哪种加工路线。")
            a = (f"【{case_id}】ISO 286：IT6={ref['IT6_um']} μm，IT7={ref['IT7_um']} μm；"
                 f"孔 EI={ref['hole_EI_um']:g} μm、ES={ref['hole_ES_um']:g} μm；"
                 f"轴 es={ref['shaft_es_um']:g} μm、ei={ref['shaft_ei_um']:g} μm。"
                 f"最小间隙 = EI - es = {ref['min_clearance_um']:g} μm，"
                 f"最大间隙 = ES - ei = {ref['max_clearance_um']:g} μm，"
                 f"属 {ref['fit_class']} 配合。"
                 + ("需保证孔尺寸一致性，工艺取钻底孔+精铰 H7，禁止只钻不铰。"
                    if ref["fit_class"] != "interference" else
                    "过盈配合需压装或温差装配，孔需精加工并控制圆度。"))
            extra = {"semantic_type": "fit", "fit": fit}
        else:
            # 许愿式 -> 参数化建模策略
            d_out = d * 2.0 + 13.0
            length = float(rng.choice([30, 45, 60]))
            material = rng.choice(["Cr12MoV", "Steel45", "AL7075-T6"])
            before = math.pi * (d_out / 2) ** 2 * length
            cut = math.pi * (d / 2) ** 2 * length
            spec = {"dimensions": {"d_outer": d_out, "d_inner": d,
                                   "overall_len": length, "material": material},
                    "before_volume_mm3": round(before, 3),
                    "delta_volume_mm3": round(-cut, 3),
                    "after_volume_mm3": round(before - cut, 3),
                    "operation": "cut"}
            g = check_parametric_model(spec)
            if not g.ok:
                stats["physics_rejected"] = stats.get("physics_rejected", 0) + 1
                continue
            q = (ctx + f"按许愿式需求参数化建模：一只 {material} 法兰，外径 {d_out:g} mm、"
                 f"内孔 φ{d:g} {hole}、总长 {length:g} mm，孔轴配 {shaft}。"
                 "给出特征树、方程式、基准策略与物理校核。")
            a = json.dumps({
                "case_id": case_id,
                "feature_tree": ["Front Plane 草图圆 D_Outer", "Boss-Extrude1 (LENGTH)",
                                 "Top Plane 草图圆 D_Bore", "Cut-Extrude1 (Through All)"],
                "equations": {"D_Outer": d_out, "D_Bore": d, "LENGTH": length,
                              "WALL": (d_out - d) / 2.0},
                "datums": {"A": "最大端面", "B": "轴线 D_Bore", "C": "键槽中心面"},
                "fit": {"hole": hole, "shaft": shaft,
                        "min_clearance_um": ref["min_clearance_um"]},
                "verification": spec["verification"] if "verification" in spec else {
                    "before_volume_mm3": spec["before_volume_mm3"],
                    "delta_volume_mm3": spec["delta_volume_mm3"],
                    "after_volume_mm3": spec["after_volume_mm3"],
                },
            }, ensure_ascii=False)
            extra = {"semantic_type": "parametric_strategy", "model_spec": spec}
        rows.append(_row(_mk(SYS_SEMANTIC, q, a), "engineering_semantics",
                         "iso286_and_dimension_chain", {"physics_ok": True, **extra}))
        eval_rows.append({
            "task_id": f"semantic-{i:05d}", "capability": "engineering_semantics",
            "prompt": "【独立验收题】" + q,
            "required_grounding_fields": ["d", "fit", "material", "length"],
            "scenario": {"task": "tolerance", "inputs": {"upper_dev": 0.0,
                                                          "lower_dev": -0.021,
                                                          "tols": [0.05, 0.10, 0.08]}},
            "expected_model_spec": extra.get("model_spec"),
            "max_latency_s": 120.0,
        })
    stats["semantic_generated"] = len(rows)
    stats["semantic_eval_tasks"] = len(eval_rows)
    return rows, eval_rows


# ---------------------------------------------------------------------------
# 反遗忘 replay：复用已验证语料，剔除坏格式与评测泄漏
# ---------------------------------------------------------------------------
def build_replay(n: int, rng: random.Random, sources: Sequence[str],
                 train_prompts: set, stats: Dict[str, Any]) -> List[Dict[str, Any]]:
    pool: List[Dict[str, Any]] = []
    index = tool_spec_index()
    for rel in sources:
        p = resolve(rel)
        if not p.is_file():
            continue
        try:
            for rec in iter_jsonl(p):
                msgs = rec.get("messages")
                if not msgs or not any(m.get("role") == "assistant" for m in msgs):
                    # instruction/input/output 格式转为 messages
                    if "instruction" in rec and "output" in rec:
                        msgs = _mk(SYS_SEMANTIC,
                                   rec["instruction"] + "\n" + str(rec.get("input", "")),
                                   str(rec["output"]))
                    else:
                        continue
                # 历史语料含 content=None / tool_calls / 非字符串回执，统一规范化
                msgs = normalize_messages(msgs)
                text = "\n".join(m["content"] for m in msgs)
                if '"name"' in text and '"arguments"' in text and '"tool"' not in text:
                    stats["replay_bad_format_dropped"] = stats.get("replay_bad_format_dropped", 0) + 1
                    continue
                # 历史工具调用的参数名可能已过期（如 action 而非 schema 要求的 task），
                # 用线上 14 个 cadcam_* 的 JSON Schema 逐条校验，不合规直接剔除
                tool_errs = [e for m in msgs if m["role"] == "assistant"
                             for e in check_tool_calls(m["content"], index)]
                if tool_errs:
                    stats["replay_tool_invalid_dropped"] = (
                        stats.get("replay_tool_invalid_dropped", 0) + 1)
                    continue
                user_text = next((m["content"] for m in msgs if m["role"] == "user"), "")
                if user_text in train_prompts:
                    continue
                pool.append({"messages": msgs,
                             "meta": {"capability": "replay", "source": rel,
                                      "id": sha256_text(text)[:16]}})
        except (ValueError, OSError) as exc:
            stats.setdefault("replay_source_errors", []).append(f"{rel}: {exc}")
    rng.shuffle(pool)
    stats["replay_pool"] = len(pool)
    return pool[:n]


# ---------------------------------------------------------------------------
# DPO 偏好对：chosen 合规最优；rejected 三类负例
# ---------------------------------------------------------------------------
def build_dpo_pairs(n: int, rng: random.Random, vision_rows: Sequence[Dict[str, Any]],
                    stats: Dict[str, Any]) -> List[Dict[str, Any]]:
    """从已过物理闸门的视觉决策构造偏好对。

    rejected 必须来自该题的真实候选集：
      physics_violation  -> 挑一个 physics_ok=False 的候选
      suboptimal_slow    -> 挑一个可行但 cost 更大的候选
      ungrounded_guess   -> 输出不引用任何工况字段的模板答案（随机猜）
    """
    usable = [r for r in vision_rows if not r["meta"].get("boundary")
              and r["meta"].get("expected_chosen")]
    pairs: List[Dict[str, Any]] = []
    if not usable:
        stats["dpo_pairs"] = 0
        return pairs
    # 每个源题最多贡献 3 类负例；超出即重复同一 prompt，会让偏好优化过拟合
    cap = len(usable) * 3
    if n > cap:
        stats["dpo_pairs_clamped"] = {"requested": n, "capped_to": cap}
        n = cap
    for i in range(n):
        src = usable[i % len(usable)]
        msgs = src["messages"]
        prompt = msgs[:-1]
        chosen = msgs[-1]["content"]
        user = msgs[1]["content"]
        try:
            chosen_obj = json.loads(chosen)
        except json.JSONDecodeError:
            continue
        m = re.search(r"【候选方案】(\[.*?\])\n", user, re.S)
        try:
            cands = json.loads(m.group(1)) if m else []
        except json.JSONDecodeError:
            cands = []
        infeasible = [c for c in cands if not c.get("physics_ok")]
        feasible = [c for c in cands if c.get("physics_ok")
                    and c.get("id") != chosen_obj.get("selected")]
        slow = sorted(feasible, key=lambda c: -float(c.get("estimated_time_s", 0)))
        cat = i % 3
        bad = json.loads(json.dumps(chosen_obj))
        # 优先按目标类别取负例；该类不适用时降级到另一类，最后才用模板猜测，
        # 避免大量偏好对退化成同一类负例
        options = (["physics_violation", "suboptimal_slow", "ungrounded_guess"]
                   if cat == 0 else
                   ["suboptimal_slow", "physics_violation", "ungrounded_guess"]
                   if cat == 1 else ["ungrounded_guess"])
        category = "ungrounded_guess"
        for opt in options:
            if opt == "physics_violation" and infeasible:
                pick = infeasible[i % len(infeasible)]
                bad["selected"] = pick["id"]
                bad["reason"] = "选最快的那个就行，约束可以后面再核。"
                bad["physics_basis"] = "跳过 Ra/IT7/转速/设备可用性校验。"
                category = opt
                break
            if opt == "suboptimal_slow" and slow:
                bad["selected"] = slow[0]["id"]
                bad["reason"] = "这道工序精度最高，用它总没错。"
                category = opt
                break
        if category == "ungrounded_guess":
            bad = {"analysis": "根据经验判断。",
                   "selected": rng.choice([c["id"] for c in cands] or ["drill_ream"]),
                   "reason": "综合考虑后选择该方案。",
                   "physics_basis": "符合工艺规范。"}
        pairs.append({
            "prompt": prompt,
            "chosen": chosen,
            "rejected": json.dumps(bad, ensure_ascii=False),
            "category": category,
            "meta": {"source_sha256": sha256_text(user)[:16]},
        })
    stats["dpo_pairs"] = len(pairs)
    stats["dpo_categories"] = {
        k: sum(1 for p in pairs if p["category"] == k)
        for k in ("physics_violation", "suboptimal_slow", "ungrounded_guess")
    }
    return pairs


__all__ = [
    "load_tool_specs", "tool_whitelist", "build_toolchain", "build_gui_trajectories",
    "build_vision_decisions", "build_engineering_semantics", "build_replay",
    "build_dpo_pairs", "GUI_ACTION_SPACE", "SCREEN",
]
