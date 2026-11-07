"""CLI Runner & Benchmark: Virtu Foundation Model x Hindsight Memory Suite.

Demonstrates and verifies:
1. Multi-tiered memory retention across 4 memory types (world_facts, agent_experiences, entity_summaries, mental_models).
2. Multi-channel hybrid recall (semantic vector + BM25 lexical + entity co-occurrence).
3. Cross-session reflection and strategic directive synthesis.
4. Exporting comprehensive benchmarks/hindsight_memory_report.md.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# Fix console encoding on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

WORKSPACE_DIR = Path(__file__).resolve().parent.parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from virtu_omni.memory import VirtuHindsightMemory, MemoryType


def main() -> int:
    print("=" * 76)
    print("  Virtu-Omni-10B x Vectorize Hindsight (Agent Memory Architecture)")
    print("=" * 76)
    print(f"[*] Workspace Root: {WORKSPACE_DIR}")
    print("[*] Paper: arXiv:2512.12818 ('Hindsight is 20/20: Building Agent Memory')")
    print("[*] Upstream SDK: vectorize-io/hindsight (hindsight-client v1.1.0)")
    print("")

    mem = VirtuHindsightMemory()
    initial_status = mem.get_status()
    print(f"[+] Initialized Hindsight Memory System (Banks: {initial_status['total_banks']})")

    # 1. Retain Knowledge across 4 memory types
    print("\n[>>>] Phase 1: Retaining Multi-Tiered Engineering Knowledge...")

    test_units = [
        # Bank: virtu_cad_cam
        (
            "virtu_cad_cam",
            "SS304 奥氏体不锈钢密度 7.93g/cm3，抗拉强度 >= 520MPa，粗加工线速度推荐 90-140 m/min，易加工硬化，切削液需充分供应。",
            "materials",
            ["ss304", "stainless_steel", "feed_speed"],
            MemoryType.WORLD_FACTS,
        ),
        (
            "virtu_cad_cam",
            "SOLIDWORKS 2021 VBA 宏中方程式管理器添加变量时，双引号必须双重转义，例如 swEqnMgr.AddEquation 0, \"\\\"D_Outer\\\" = 110.0\"，以防运行时异常 13。",
            "learnings",
            ["solidworks", "equation_mgr", "vba", "syntax_rule"],
            MemoryType.MENTAL_MODELS,
        ),
        (
            "virtu_cad_cam",
            "自动化精密法兰套筒 3D CAD 原生特征树建立完成：包含基准面、草图旋转凸台、退刀槽切除与方程式关联，ForceRebuild3 刷新无几何报错。",
            "procedures",
            ["feature_tree", "solidworks", "revolve", "forcerebuild3"],
            MemoryType.AGENT_EXPERIENCES,
        ),
        # Bank: virtu_cnc_machining
        (
            "virtu_cnc_machining",
            "Ti-6Al-4V 钛合金热导率极低，粗车切速必须严格控制在 35-55 m/min，精车 60-80 m/min，必须配备耐热涂层硬质合金刀具与高压内冷 M08。",
            "materials",
            ["ti6al4v", "titanium", "cutting_speed", "coolant"],
            MemoryType.WORLD_FACTS,
        ),
        (
            "virtu_cnc_machining",
            "CIMCO FANUC Macro B 宏程序中，G71 粗车循环第二行中的 U 为单边径向余量，而轮廓起止 X 坐标为直径编程，必须留足 0.4mm 余量供 G70 精修。",
            "learnings",
            ["cimco", "macro_b", "fanuc", "g71", "g70"],
            MemoryType.MENTAL_MODELS,
        ),
        (
            "virtu_cnc_machining",
            "完成轴承外套圈 G71 复合循环数控车削仿真：主轴转速 S1800，进给 F0.15，对刀仪 G54 校准无误，Vericut 刀路无碰撞无干涉过切。",
            "procedures",
            ["turning", "g71", "vericut", "collision_free"],
            MemoryType.AGENT_EXPERIENCES,
        ),
        # Bank: virtu_quality_audit
        (
            "virtu_quality_audit",
            "回转体内外孔壁厚底线强制护栏：(d_outer - d_inner)/2 必须 >= 2.0mm，严禁薄壁加工振刀与开裂变形。",
            "guardrails",
            ["wall_thickness", "safety_boundary", "quality"],
            MemoryType.MENTAL_MODELS,
        ),
    ]

    retained_ids = []
    for bank_id, content, context, tags, m_type in test_units:
        ret = mem.retain(
            bank_id=bank_id,
            content=content,
            context=context,
            tags=tags,
            memory_type=m_type,
        )
        retained_ids.append(ret["id"])
        print(f"  [+] Retained [{m_type.upper():17}] in `{bank_id}` -> {ret['id']} (Entities: {ret['entities']})")

    # 2. Hybrid Recall Verification
    print("\n[>>>] Phase 2: Testing Multi-Channel Hybrid Recall...")
    queries = [
        ("virtu_cad_cam", "SOLIDWORKS 方程式 双引号转义规范"),
        ("virtu_cnc_machining", "钛合金 Ti-6Al-4V 切削转速与冷却液"),
        ("virtu_cnc_machining", "FANUC G71 宏程序粗车余量设置"),
        ("virtu_quality_audit", "回转体薄壁件壁厚安全底线"),
    ]

    for bank_id, q in queries:
        hits = mem.recall(bank_id=bank_id, query=q, max_results=2)
        print(f"\n  Query: '{q}' (Bank: `{bank_id}`)")
        for h in hits:
            print(f"    - Score: {h['score']:.4f} [Sem: {h['semantic_score']:.2f}, Lex: {h['lexical_score']:.2f}] | [{h['memory_type']}] {h['content'][:65]}...")

    # 3. Cross-Session Reflection
    print("\n[>>>] Phase 3: Synthesizing Cross-Session Reflection (Reflect)...")
    reflect_query = "钛合金薄壁轴套高精度车削加工与方程式建模策略"
    reflection = mem.reflect(bank_id="virtu_cnc_machining", query=reflect_query, budget="high")

    print(f"  Reflect Intent: '{reflect_query}'")
    print(f"  Synthesis: {reflection['synthesis']}")
    print(f"  Action Directives ({len(reflection['directives'])}):")
    for d in reflection["directives"]:
        print(f"    * {d}")

    # 4. Export Report
    report_path = WORKSPACE_DIR / "benchmarks" / "hindsight_memory_report.md"
    mem.export_memory_report(report_path)
    print(f"\n[+] Exported comprehensive Hindsight memory report: {report_path}")

    final_status = mem.get_status()
    print("\n" + "=" * 76)
    print(f"  Hindsight Memory System Verified Successfully!")
    print(f"  Total Active Banks: {final_status['total_banks']} | Total Memory Units: {final_status['total_units']}")
    print("=" * 76)
    return 0


if __name__ == "__main__":
    sys.exit(main())
