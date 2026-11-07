# -*- coding: utf-8 -*-
"""build_incident_corpus.py — 生成“故障处置 + 六软件路由”增量 SFT 语料（确定性模板，无编造日志）。

来源事实（2026-11-01 本机实测）：
- SOLIDWORKS 已在运行但未注册 ROT，单实例守卫拒绝二次启动 → COM 附着超时；
- 该会话 SLDWORKS.exe 无 MainWindowTitle，GUI 焦点/截图不可用；
- AutoCAD / CIMCO / NX 离线通道可执行；VERICUT / SSCNC 需要工程或窗口。

输出：data/train/incident_v1/train/incident_sft_v1.jsonl
schema 与 data/train/virtu_fix_v1 一致：{"messages":[system,user,assistant], "_source": ...}
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "data", "train", "incident_v1")

SYS_EXEC = (
    "你是 Virtu 工业级 CAD/CAM 执行代理。只允许声称已执行，并给出可核验的产物路径或日志字段；"
    "当接入通道不可用时必须返回 blocked 状态、降级接入方式与不可执行原因，禁止编造成功。"
)
SYS_ROUTE = (
    "你是 Virtu 六软件调度器。根据制造意图输出唯一一条工具调用 JSON，"
    "字段为 software/action/params，software 只能是 solidworks/nx/autocad/vericut/cimco/sscnc。"
)

# ---------------------------------------------------------------- 故障处置样本
INCIDENTS = [
    {
        "ask": "帮我建一个法兰三维模型，SOLIDWORKS 已经开着了，直接连上去。",
        "status": "blocked",
        "software": "solidworks",
        "reason": "SLDWORKS.exe 已在运行但未在 ROT 注册，GetActiveObject 失败；单实例守卫禁止二次启动。",
        "fallback": "PYTHON_SDK",
        "next": "改用 create_parametric_part 生成 .swb 宏并保存到 runs/<id>/，由已运行的实例手动 RunMacro。",
    },
    {
        "ask": "SOLIDWORKS 里把孔切了，切完告诉我体积。",
        "status": "blocked",
        "software": "solidworks",
        "reason": "当前会话 SLDWORKS 无 MainWindowTitle，无法附着文档对象，CreateMassProperty 不可用。",
        "fallback": "MCP",
        "next": "先 cadcam_preflight 确认连接态；未连接时输出 blocked，不返回体积数值。",
    },
    {
        "ask": "再开一个 SOLIDWORKS 窗口跑第二个零件。",
        "status": "refused",
        "software": "solidworks",
        "reason": "单实例公理：本机只允许一个 SLDWORKS 进程，避免句柄与许可证争用。",
        "fallback": "PYTHON_SDK",
        "next": "复用现有实例串行执行，或保存宏后排队。",
    },
    {
        "ask": "把这张图在 AutoCAD 里量一下尺寸标注有没有重叠。",
        "status": "needs_input",
        "software": "autocad",
        "reason": "缺少待检查的 DWG/DXF 路径，无法确定目标文档。",
        "fallback": "CLI",
        "next": "请给出图纸路径；或先用 create_dxf 生成基准图再检查。",
    },
    {
        "ask": "NX 里按 80 外径 20 内孔 120 长度出个轴套，跑完告诉我重量。",
        "status": "blocked",
        "software": "nx",
        "reason": "journal 已生成但 run_journal 需要 NX 会话；当前无 ugraft 进程，执行通道不可用。",
        "fallback": "PYTHON_SDK",
        "next": "保留 .py journal 到 runs/，待 NX 启动后 run_journal 执行；重量由解析体积×密度给出并标注为理论值。",
    },
    {
        "ask": "用 VERICUT 跑一下这段 NC，看有没有过切。",
        "status": "needs_input",
        "software": "vericut",
        "reason": "缺少 .vcproject 工程，VERICUT 批处理无法建立毛坯与夹具上下文。",
        "fallback": "CLI",
        "next": "先提供工程路径；或退回 CIMCO 做 G00 快速下刀碰撞静态检查。",
    },
    {
        "ask": "CIMCO 打开这个程序并回放刀路。",
        "status": "blocked",
        "software": "cimco",
        "reason": "CIMCOEdit.exe 未运行，且回放依赖 GUI 会话；当前会话无可用窗口句柄。",
        "fallback": "CLI",
        "next": "先用 validate_fanuc_macro_b 做语法与变量检查，回放待有人值守时执行。",
    },
    {
        "ask": "斯沃仿真里对刀后直接跑循环。",
        "status": "blocked",
        "software": "sscnc",
        "reason": "CNCLogin.exe 未启动，虚拟 FANUC 0i 面板不存在，无 G54 读数可核验。",
        "fallback": "CLI",
        "next": "输出 SSCNC 装夹/对刀步骤单，待登录后按单执行，不声称已加工。",
    },
]

VARIANTS = [
    "（现场：{sw} 已运行但你连不上）",
    "（现场：{sw} 进程存在但窗口标题为空）",
    "（现场：{sw} 单实例守卫已拒绝二次启动）",
    "（现场：{sw} 可用，但无人值守、不能弹窗）",
    "（现场：{sw} 的 COM/GUI 句柄都拿不到，只有离线通道可用）",
]


def incident_samples():
    rows = []
    for i, inc in enumerate(INCIDENTS):
        for j, variant in enumerate(VARIANTS):
            ask = inc["ask"] + variant.format(sw=inc["software"]) if j else inc["ask"]
            payload = {
                "status": inc["status"],
                "software": inc["software"],
                "reason": inc["reason"],
                "fallback": inc["fallback"],
                "next_action": inc["next"],
            }
            answer = (
                "结论：本条不可执行，返回 blocked/refused，不伪造产物。\n"
                + json.dumps(payload, ensure_ascii=False, indent=2)
                + "\n核验要求：给出产物路径或日志字段后才能改判为 success。"
            )
            rows.append({
                "messages": [
                    {"role": "system", "content": SYS_EXEC},
                    {"role": "user", "content": ask},
                    {"role": "assistant", "content": answer},
                ],
                "_source": f"incident_{inc['software']}_{i}_{j}",
            })
    return rows


# ---------------------------------------------------------------- 路由样本
ROUTES = [
    ("solidworks", "connect", {}, ["连一下 SOLIDWORKS", "确认 SolidWorks 是否在线", "ping 一下 SW 连接"]),
    ("solidworks", "create_parametric_part", {"part_name": "guide_sleeve", "dimensions": {"D_Outer": 0.08, "D_Bore": 0.02, "Length": 0.12}}, ["新建轴套零件并建参数", "用方程式建导向套模型", "生成轴套参数化零件"]),
    ("solidworks", "execute_vba", {"code": "..."}, ["跑这段 VBA 宏", "执行我给的 SW 宏", "用宏改一下特征树"]),
    ("nx", "generate_parametric_model", {"part_name": "sleeve_nx", "expressions": {"D_Outer": 80.0, "D_Bore": 20.0}}, ["NX 里生成轴套建模脚本", "出 NX journal", "用 NXOpen 建轴套"]),
    ("nx", "run_journal", {"script_path": "runs/x_nx.py"}, ["执行这个 NX journal", "跑 NX 脚本", "把 journal 丢给 NX 跑"]),
    ("autocad", "create_dxf", {"drawing_name": "sleeve_gb", "entities": []}, ["出一张轴套二维图", "生成 DXF 工程图", "画个 GB 视图"]),
    ("autocad", "run_headless_script", {"script_path": "runs/x.lsp"}, ["用 accoreconsole 批量出图", "无界面跑 LISP", "脚本批处理图纸"]),
    ("cimco", "validate_macro", {"code": "#100=50\\nM30"}, ["校验这段 FANUC 宏", "看看宏变量有没有错", "检查 NC 程序语法"]),
    ("cimco", "launch", {"nc_file_path": "runs/x.nc"}, ["在 CIMCO 打开这个 NC", "回放刀路", "把程序拖进 CIMCO"]),
    ("vericut", "run_simulation", {"project_path": "runs/x.vcproject"}, ["VERICUT 仿真这段程序", "跑虚拟加工", "做过切检查"]),
    ("vericut", "check_collision", {"log_path": "runs/x.log"}, ["解析仿真日志有没有撞刀", "看 VERICUT 报告", "统计过切残料"]),
    ("sscnc", "launch", {}, ["启动斯沃仿真", "打开数控仿真软件", "起虚拟机床"]),
    ("sscnc", "calculate_offsets", {"tools": [{"T": 1, "diameter": 10}]}, ["算一下对刀偏置", "给 T1 算刀补", "算 G54 工件坐标"]),
    ("all", "preflight", {}, ["六软件都连没连上", "体检一下工具链", "看看哪几台软件就绪"]),
    ("extreme", "extreme_chain", {"wish": "..."}, ["走极限闭环全流程", "绘图建模仿真加工一把跑完", "跑极限 CAD/CAE/CAM 链"]),
]

CONTEXT = [
    "", "材料 45#钢。", "外径 80mm 内孔 20mm 长 120mm。", "交期紧，先出图后建模。", "现在是无人值守班次。",
]

CTX_LIMIT = 5


def route_samples():
    rows = []
    for i, (software, action, params, asks) in enumerate(ROUTES):
        for k, ask in enumerate(asks):
            for c, ctx in enumerate(CONTEXT):
                if c >= CTX_LIMIT:
                    continue
                user = ask + (ctx and " " + ctx or "")
                p = dict(params)
                if software in ("extreme", "all") and "wish" in p:
                    p["wish"] = "液压缸导向套 45#钢 外径80 内孔20 长120"
                answer = json.dumps({"software": software, "action": action, "params": p}, ensure_ascii=False)
                rows.append({
                    "messages": [
                        {"role": "system", "content": SYS_ROUTE},
                        {"role": "user", "content": user},
                        {"role": "assistant", "content": answer},
                    ],
                    "_source": f"route_{software}_{action}_{i}_{k}_{c}",
                })
    return rows


def main():
    rows = incident_samples() + route_samples()
    seen, kept = set(), []
    for r in rows:
        h = hashlib.sha1(r["messages"][1]["content"].strip().encode("utf-8")).hexdigest()
        if h in seen:
            continue
        seen.add(h)
        kept.append(r)

    os.makedirs(os.path.join(OUT_DIR, "train"), exist_ok=True)
    path = os.path.join(OUT_DIR, "train", "incident_sft_v1.jsonl")
    with open(path, "w", encoding="utf-8") as f:
        for r in kept:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    manifest = {
        "file": path,
        "total": len(kept),
        "incident": sum(1 for r in kept if r["_source"].startswith("incident")),
        "route": sum(1 for r in kept if r["_source"].startswith("route")),
        "dedup_removed": len(rows) - len(kept),
        "sha1": hashlib.sha1(open(path, "rb").read()).hexdigest(),
    }
    with open(os.path.join(OUT_DIR, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
