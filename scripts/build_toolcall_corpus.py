#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_toolcall_corpus.py — 把工业 wish 语料转成 OpenAI function-calling 多轮训练数据

设计要点（对应 AGENT_TRAINING_PLAN.md §3.3 / §3.5）:
  1. 不事后从自然语言反解 spec（parse_wish_intent 对「轴心通孔」「R8.0」有盲点），
     而是重跑原生成器，patch parse_wish_intent 捕获「生成时真正使用的 spec」，
     用 wish 文本做键绕过 shuffle，保证 arguments 与代码生成所用 spec 逐字段一致。
  2. enhanced_parse 只补强可确定性提取的字段，不破坏原解析器结果。
  3. assistant 段只放 tool_calls 与简短确认，代码一律放在 tool 回执里
     （训练时 tool 段 loss=-100），避免模型学会在正文凭空吐代码。
  4. Phase 1 用笛卡尔积全量枚举（8×8×7×7×7=21952 组合）+ 多句式模板扩增。
  5. 全程流式写文件，不把语料堆在内存里（本机可用内存仅 ~1.8GB）。

用法:
  python scripts/build_toolcall_corpus.py --phase 0     # 转换现有 1226 条
  python scripts/build_toolcall_corpus.py --phase 1     # 扩增 21952 条
  python scripts/build_toolcall_corpus.py --phase all   # 两者都做（默认）
  python scripts/build_toolcall_corpus.py --phase 1 --limit 2000   # 小规模试跑
"""

from __future__ import annotations

import argparse
import importlib.util
import itertools
import json
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from virtu_omni.engine.wish_cad_cam_engine import WishCADCAMEngine
from virtu_omni.knowledge.software_plugin_ontology import SOFTWARE_ONTOLOGY

DATASET_DIR = ROOT / "damodel_cad_cam_tuning" / "dataset"
SCHEMA_PATH = ROOT / "data" / "tools" / "tool_schema.json"
GEN_PATH = ROOT / "damodel_cad_cam_tuning" / "generate_comprehensive_wish_corpus.py"

SYSTEM_TOOL = (
    "你是 Virtu 工业智能体。需要产出可执行代码时，必须通过工具调用完成，"
    "不要凭空输出代码。先解析意图，再调用对应软件的代码生成工具。"
)

CODE_TOOL = {
    "solidworks": "solidworks.create_parametric_part",
    "nx": "nx.create_nxopen_script",
    "autocad": "autocad.create_autolisp",
    "vericut": "vericut.create_project_config",
    "cimco": "cimco.create_macro_b",
    "sscnc": "sscnc.create_setup_guide",
}
GEN_METHOD = {
    "solidworks": "generate_solidworks_macro",
    "nx": "generate_nx12_script",
    "autocad": "generate_autocad_lisp",
    "vericut": "generate_vericut_config",
    "cimco": "generate_cimco_macro",
    "sscnc": "generate_sscnc_setup_guide",
}
SW_LABEL = {
    "solidworks": "SOLIDWORKS 2021",
    "nx": "Siemens NX 12.0",
    "autocad": "AutoCAD 2026",
    "vericut": "Vericut 9.6",
    "cimco": "CIMCO Edit 2026",
    "sscnc": "斯沃数控仿真 SSCNC",
}

SPEC_KEYS = (
    "material", "d_outer", "d_inner", "num_features", "fillet_r",
    "overall_len", "sweep_angle", "is_multiaxis", "is_die_mold",
)

NUM = r"([0-9]+(?:\.[0-9]+)?)"
RE_OUTER = re.compile(r"(?:外径|直径|外轮廓|外圆)[^\d]{0,6}" + NUM)
RE_INNER = re.compile(r"(?:内径|内孔|轴心通孔|基体通孔|通孔|孔径|轴孔)[^\d]{0,6}" + NUM)
RE_LEN = re.compile(r"(?:总长度|总长|长度|总高|长)[^\d]{0,6}" + NUM)
RE_R = re.compile(r"(?:圆角|过渡角|弧槽|倒角|(?<![A-Za-z])R)[^\d]{0,4}" + NUM)
RE_CNT = re.compile(r"([0-9]+)\s*(?:道|个|处|叶片|齿|槽)")
RE_MAT = re.compile(r"(?:材质|材料)[为:：]?\s*([A-Za-z0-9][A-Za-z0-9\-]*)")
RE_ONTO = re.compile(r"在(.+?)中，插件【(.+?)】")

ORIG_PARSE = WishCADCAMEngine.parse_wish_intent
RECORDS: dict[str, dict] = {}


def enhanced_parse(engine: WishCADCAMEngine, wish_text: str) -> dict:
    """补强原解析器对生成器模板的已知盲点，保持确定性。"""
    spec = ORIG_PARSE(engine, wish_text)
    pairs = (
        (RE_OUTER, "d_outer"), (RE_INNER, "d_inner"), (RE_LEN, "overall_len"),
        (RE_R, "fillet_r"), (RE_CNT, "num_features"), (RE_MAT, "material"),
    )
    for rx, key in pairs:
        m = rx.search(wish_text)
        if not m:
            continue
        if key == "material":
            spec[key] = m.group(1)
        elif key == "num_features":
            spec[key] = min(max(int(m.group(1)), 1), 100)
        else:
            spec[key] = float(m.group(1))
    # 物理一致性：内孔必须小于外径（门禁第 4 条）
    if spec["d_inner"] >= spec["d_outer"]:
        spec["d_inner"] = round(spec["d_outer"] * 0.3, 1)
    return spec


def spec_view(spec: dict) -> dict:
    return {k: spec[k] for k in SPEC_KEYS}


def detect_software(wish: str) -> str:
    if "【许愿式工业制造求解】" in wish:
        return "multi"
    if "SOLIDWORKS" in wish.upper():
        return "solidworks"
    if "SIEMENS NX" in wish.upper() or "NX 12" in wish.upper() or "NX12" in wish.upper():
        return "nx"
    if "AUTOCAD" in wish.upper():
        return "autocad"
    if "VERICUT" in wish.upper():
        return "vericut"
    if "CIMCO" in wish.upper():
        return "cimco"
    if "斯沃" in wish or "SSCNC" in wish.upper():
        return "sscnc"
    return "solidworks"


def make_summary(spec: dict, label: str) -> str:
    return (
        f"已通过工具链完成 {label} 参数化求解：材质 {spec['material']}，"
        f"外径 {spec['d_outer']}mm、内孔 {spec['d_inner']}mm、总长 {spec['overall_len']}mm，"
        f"{spec['num_features']} 道 R{spec['fillet_r']} 特征。"
        f"可执行代码已由工具产出，详见上方工具回执。"
    )


def tc(call_id: str, name: str, arguments: dict) -> dict:
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments, ensure_ascii=False)},
    }


def build_single(engine: WishCADCAMEngine, wish: str, spec: dict, sw: str, tools: list) -> dict:
    sv = spec_view(spec)
    code = getattr(engine, GEN_METHOD[sw])(spec)
    name = CODE_TOOL[sw]
    return {
        "tools": tools,
        "messages": [
            {"role": "system", "content": SYSTEM_TOOL},
            {"role": "user", "content": wish},
            {"role": "assistant", "tool_calls": [tc("call_1", "cad.parse_wish_intent", spec)]},
            {"role": "tool", "tool_call_id": "call_1", "name": "cad.parse_wish_intent",
             "content": json.dumps(sv, ensure_ascii=False)},
            {"role": "assistant", "tool_calls": [tc("call_2", name, {"spec": sv})]},
            {"role": "tool", "tool_call_id": "call_2", "name": name, "content": code},
            {"role": "assistant", "content": make_summary(spec, SW_LABEL[sw])},
        ],
    }


def build_multi(engine: WishCADCAMEngine, wish: str, spec: dict, tools: list) -> dict:
    sv = spec_view(spec)
    order = ["solidworks", "nx", "autocad", "vericut", "cimco", "sscnc"]
    calls, replies = [], []
    for i, sw in enumerate(order, start=2):
        name = CODE_TOOL[sw]
        calls.append(tc(f"call_{i}", name, {"spec": sv}))
        code = getattr(engine, GEN_METHOD[sw])(spec)
        head = code.splitlines()[0][:120] if code.splitlines() else ""
        # 完整代码由单软件样本教授；跨学科样本只保留「一次编排 6 工具」的能力，
        # 回执压缩为摘要，避免单条 >16k 字符被 max_length=4096 截断而丢失后半段工具链。
        replies.append({
            "role": "tool", "tool_call_id": f"call_{i}", "name": name,
            "content": f"[{SW_LABEL[sw]}] 代码已生成（{len(code)} 字符）。首行：{head}",
        })
    return {
        "tools": tools,
        "messages": [
            {"role": "system", "content": SYSTEM_TOOL},
            {"role": "user", "content": wish},
            {"role": "assistant", "tool_calls": [tc("call_1", "cad.parse_wish_intent", spec)]},
            {"role": "tool", "tool_call_id": "call_1", "name": "cad.parse_wish_intent",
             "content": json.dumps(sv, ensure_ascii=False)},
            {"role": "assistant", "tool_calls": calls},
            *replies,
            {"role": "assistant", "content": (
                "已完成六大工业软件全流程求解：材质 " + str(spec["material"])
                + f"，外径 {spec['d_outer']}mm、内孔 {spec['d_inner']}mm、总长 {spec['overall_len']}mm。"
                + "SOLIDWORKS/NX 脚本、AutoCAD 出图、Vericut 仿真、CIMCO 宏程序与 SSCNC 对刀方案均已由对应工具产出。"
            )},
        ],
    }


def build_ontology(wish: str, tools: list, original_answer: str) -> dict | None:
    m = RE_ONTO.search(wish)
    if not m:
        return None
    sw_name, plugin_name = m.group(1), m.group(2)
    info = SOFTWARE_ONTOLOGY.get(sw_name, {}).get("plugins_and_addins", {}).get(plugin_name)
    if info is None:
        return None
    return {
        "tools": tools,
        "messages": [
            {"role": "system", "content": SYSTEM_TOOL},
            {"role": "user", "content": wish},
            {"role": "assistant", "tool_calls": [
                tc("call_1", "ontology.lookup_plugin", {"software": sw_name, "plugin": plugin_name})]},
            {"role": "tool", "tool_call_id": "call_1", "name": "ontology.lookup_plugin",
             "content": json.dumps(info, ensure_ascii=False)},
            {"role": "assistant", "content": original_answer},
        ],
    }


def capture_generator_run() -> list:
    """重跑原生成器，捕获生成时真实使用的 spec，不污染原始数据集。"""
    def patched(self, wish_text):
        s = enhanced_parse(self, wish_text)
        RECORDS[wish_text] = s
        return s

    WishCADCAMEngine.parse_wish_intent = patched
    mod_spec = importlib.util.spec_from_file_location("virtu_gen_corpus", GEN_PATH)
    mod = importlib.util.module_from_spec(mod_spec)
    mod_spec.loader.exec_module(mod)
    tmp = Path(tempfile.gettempdir()) / f"virtu_gen_{os.getpid()}.jsonl"
    mod.OUTPUT_FILE = str(tmp)
    try:
        mod.generate_comprehensive_corpus()
        with tmp.open(encoding="utf-8") as f:
            rows = [json.loads(line) for line in f if line.strip()]
    finally:
        WishCADCAMEngine.parse_wish_intent = ORIG_PARSE
        tmp.unlink(missing_ok=True)
    return rows


def phase0(tools: list) -> tuple[int, dict]:
    rows = capture_generator_run()
    engine = WishCADCAMEngine()
    out = DATASET_DIR / "toolcall_sft_v1.jsonl"
    stats = {"total": 0, "wish_single": 0, "multi": 0, "ontology": 0, "skipped": 0}
    with out.open("w", encoding="utf-8") as f:
        for row in rows:
            msgs = row.get("messages", [])
            if len(msgs) < 3:
                stats["skipped"] += 1
                continue
            wish = msgs[1]["content"]
            answer = msgs[2].get("content", "")
            if "插件【" in wish:
                rec = build_ontology(wish, tools, answer)
                key = "ontology"
            else:
                spec = RECORDS.get(wish)
                if spec is None:
                    stats["skipped"] += 1
                    continue
                sw = detect_software(wish)
                rec = build_multi(engine, wish, spec, tools) if sw == "multi" \
                    else build_single(engine, wish, spec, sw, tools)
                key = "multi" if sw == "multi" else "wish_single"
            if rec is None:
                stats["skipped"] += 1
                continue
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            stats[key] += 1
            stats["total"] += 1
    print(f"[phase0] 输出 {out} -> {stats['total']} 条 {stats}")
    return stats["total"], stats


MATERIALS = [
    "Ti-6Al-4V", "AL7075-T6", "Cr12MoV", "Steel45", "SS304",
    "P20", "Inconel718", "CuC360",
]
DIAMETERS = [35.0, 48.0, 53.0, 65.0, 80.0, 110.0, 140.0, 180.0]
LENGTHS = [30.0, 40.0, 45.0, 60.0, 85.0, 120.0, 160.0]
RADII = [1.5, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0]
FEATURES = [2, 3, 4, 5, 6, 8, 12]

TEMPLATES = {
    "solidworks": [
        "我想要一个材质为{mat}的回转模具套筒，要求最大外径为{d_out}mm，轴心通孔为{d_in}mm，总长度为{l}mm，带有{n}道槽底圆角R{r}的环形密封减径槽。请帮我实现SOLIDWORKS 2021的全局变量参数化驱动宏以及Simulation应力校核建议。",
        "请为SOLIDWORKS 2021生成VBA参数化宏：{mat}法兰套筒，外径{d_out}mm、内孔{d_in}mm、总长{l}mm，{n}道R{r}环形密封槽，需带方程式驱动。",
    ],
    "nx": [
        "请为Siemens NX 12.0编写参数化建模Python脚本，工件为{mat}高精耐磨轮套，外径{d_out}mm，内径{d_in}mm，长{l}mm，需建立NX表达式驱动与{n}道R{r}环形工步槽，并说明Mold Wizard或CAM多轴加工策略。",
        "NX 12.0 NXOpen Python：{mat}轴套外径{d_out}mm、内径{d_in}mm、长度{l}mm，{n}处R{r}工步槽，给出表达式绑定与CAM车削方案。",
    ],
    "autocad": [
        "许愿绘制一张AutoCAD 2026标准机械工程图(c:DRAWWHEELMOLD)，工件外径{d_out}，内孔{d_in}，总长{l}。要求分立中心线、粗实线轮廓、标注和ANSI31剖面线图层，尺寸标注需符合国标规范。",
        "AutoCAD 2026 AutoLISP 出图：{mat}套筒外径{d_out}mm、内孔{d_in}mm、总长{l}mm，含{n}道R{r}槽，需图层隔离与参数化尺寸约束。",
    ],
    "vericut": [
        "请生成Vericut 9.6数控仿真工程配置文件(.opt)，工件为{mat}精密轴套(直径{d_out}mm, 长度{l}mm)，开启Force物理力学切削优化、AUTO-DIFF与0.005mm过切干涉检测。",
        "Vericut 9.6 .opt 配置：{mat}轴套直径{d_out}mm、长度{l}mm、内孔{d_in}mm，{n}道R{r}弧槽，启用Force与AUTO-DIFF。",
    ],
    "cimco": [
        "请为CIMCO Edit 2026编写带参数化宏变量(#101-#108)的FANUC Macro B数控宏程序，加工{mat}工件(外径{d_out}mm, 长度{l}mm, 内孔{d_in}mm, 弧槽R{r})，包含G71粗车、G70精车与刀尖半径补偿G42。",
        "CIMCO Macro B：{mat}工件外径{d_out}mm、长度{l}mm、内孔{d_in}mm，{n}道R{r}槽，G71/G70 循环 + G42 刀补。",
    ],
    "sscnc": [
        "请为斯沃数控仿真软件编写车间级实操与对刀指南，系统为FANUC 0i-TF车床，加工{mat}轮模工件(外径{d_out}mm, 长度{l}mm)，包含工件毛坯卡盘装夹、T0101外圆刀与T0202成型刀的刀尖方位号设置，以及G54试切对刀全步骤。",
        "斯沃SSCNC FANUC 0i-TF：{mat}轮模外径{d_out}mm、长度{l}mm、内孔{d_in}mm，{n}道R{r}槽，给出装夹与G54对刀步骤。",
    ],
}
SW_ORDER = ["solidworks", "nx", "autocad", "vericut", "cimco", "sscnc"]


def phase1(tools: list, limit: int | None = None) -> tuple[int, dict]:
    engine = WishCADCAMEngine()
    out = DATASET_DIR / "toolcall_sft_v2_expanded.jsonl"
    combos = itertools.product(MATERIALS, DIAMETERS, LENGTHS, RADII, FEATURES)
    stats = {"total": 0, "by_sw": {k: 0 for k in SW_ORDER}, "skipped": 0}
    with out.open("w", encoding="utf-8") as f:
        for idx, (mat, d_out, l, r, n) in enumerate(combos):
            if limit is not None and idx >= limit:
                break
            sw = SW_ORDER[idx % len(SW_ORDER)]
            tmpl = TEMPLATES[sw][(idx // len(SW_ORDER)) % len(TEMPLATES[sw])]
            d_in = round(d_out * 0.3, 1)
            wish = tmpl.format(mat=mat, d_out=d_out, d_in=d_in, l=l, r=r, n=n)
            spec = enhanced_parse(engine, wish)
            try:
                rec = build_single(engine, wish, spec, sw, tools)
            except Exception as exc:  # 单条失败不影响整体
                stats["skipped"] += 1
                if stats["skipped"] <= 3:
                    print(f"[phase1][warn] 跳过 idx={idx} {type(exc).__name__}: {exc}")
                continue
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            stats["total"] += 1
            stats["by_sw"][sw] += 1
            if (idx + 1) % 5000 == 0:
                print(f"[phase1] 已生成 {idx + 1} 条...")
    print(f"[phase1] 输出 {out} -> {stats['total']} 条 {stats['by_sw']} 跳过={stats['skipped']}")
    return stats["total"], stats


def main() -> None:
    ap = argparse.ArgumentParser(description="构建 Virtu tool-call 训练语料")
    ap.add_argument("--phase", default="all", choices=["0", "1", "all"])
    ap.add_argument("--limit", type=int, default=None, help="Phase 1 试跑条数上限")
    args = ap.parse_args()

    if not SCHEMA_PATH.exists():
        raise SystemExit(f"[FATAL] 缺少工具 schema，请先运行 scripts/build_tool_schema.py -> {SCHEMA_PATH}")
    with SCHEMA_PATH.open(encoding="utf-8") as f:
        tools = json.load(f)
    print(f"[corpus] 载入 {len(tools)} 个工具 schema")

    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    n0 = n1 = 0
    if args.phase in ("0", "all"):
        n0, _ = phase0(tools)
    if args.phase in ("1", "all"):
        n1, _ = phase1(tools, limit=args.limit)

    unified = DATASET_DIR / "virtu_toolcall_train_unified.jsonl"
    with unified.open("w", encoding="utf-8") as w:
        for src in (DATASET_DIR / "toolcall_sft_v1.jsonl", DATASET_DIR / "toolcall_sft_v2_expanded.jsonl"):
            if src.exists():
                with src.open(encoding="utf-8") as r:
                    for line in r:
                        if line.strip():
                            w.write(line)
    size = unified.stat().st_size
    print(f"[corpus] 统一训练集 {unified} -> {size / 1e6:.2f} MB (phase0={n0}, phase1={n1})")


if __name__ == "__main__":
    main()
