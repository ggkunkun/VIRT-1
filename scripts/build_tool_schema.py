#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_tool_schema.py — 导出 Virtu Phase 0 工具清单（OpenAI function-calling schema）

用途:
  - 训练侧: 写进 toolcall 数据集的 `tools` 字段，供 Qwen3 chat template 渲染
  - 推理侧: WorkBuddy 桥 / vLLM 用同一份 schema，避免训练-推理序列化不一致

输出: data/tools/tool_schema.json（8 个 Phase 0 工具）
"""

from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "tools", "tool_schema.json")

MATERIALS = [
    "Ti-6Al-4V", "AL7075-T6", "Cr12MoV", "Steel45", "SS304",
    "P20", "Inconel718", "CuC360", "20CrMnTi",
]

SPEC_PROPERTIES = {
    "wish": {"type": "string", "description": "原始制造意图全文"},
    "material": {"type": "string", "enum": MATERIALS, "description": "工件材料牌号"},
    "d_outer": {"type": "number", "description": "最大外径 mm"},
    "d_inner": {"type": "number", "description": "轴心通孔/内孔直径 mm，必须小于 d_outer"},
    "num_features": {"type": "integer", "minimum": 1, "maximum": 100, "description": "槽/叶片/阵列特征数量"},
    "fillet_r": {"type": "number", "description": "槽底圆角 R mm"},
    "overall_len": {"type": "number", "description": "总长 mm"},
    "sweep_angle": {"type": "number", "description": "摆角/螺旋角 deg"},
    "is_multiaxis": {"type": "boolean", "description": "是否需五轴联动"},
    "is_die_mold": {"type": "boolean", "description": "是否为模具类工件"},
}


def _fn(name: str, description: str, properties: dict, required: list) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


def build() -> list:
    tools = [
        _fn(
            "cad.parse_wish_intent",
            "将自然语言制造意图解析为结构化参数化 spec；任何代码生成前必须先调用本工具。",
            SPEC_PROPERTIES,
            ["wish", "material", "d_outer", "d_inner"],
        ),
    ]

    code_tools = [
        ("solidworks.create_parametric_part", "SOLIDWORKS 2021 VBA 全局变量参数化驱动宏"),
        ("nx.create_nxopen_script", "Siemens NX 12.0 NXOpen Python 表达式驱动脚本"),
        ("autocad.create_autolisp", "AutoCAD 2026 AutoLISP 参数化工程图绘制程序"),
        ("vericut.create_project_config", "Vericut 9.6 .opt 仿真工程与 Force 切削优化配置"),
        ("cimco.create_macro_b", "CIMCO Edit 2026 FANUC Macro B 参数化数控宏程序"),
        ("sscnc.create_setup_guide", "斯沃数控仿真 FANUC 0i-TF 装夹与 G54 对刀指南"),
    ]
    for name, desc in code_tools:
        tools.append(_fn(
            name,
            f"由 spec 生成{desc}。必须通过工具调用产出，不得在正文凭空输出代码。",
            {"spec": {"type": "object", "description": "cad.parse_wish_intent 返回的结构化参数（不含 wish 原文）"}},
            ["spec"],
        ))

    tools.append(_fn(
        "ontology.lookup_plugin",
        "查询指定工业软件的指定插件/模块的定位、能力、API 接口与工程应用场景。",
        {
            "software": {"type": "string", "description": "软件全称，如 SOLIDWORKS 2021"},
            "plugin": {"type": "string", "description": "插件/模块名称"},
        },
        ["software", "plugin"],
    ))
    return tools


def main() -> None:
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tools = build()
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(tools, f, ensure_ascii=False, indent=2)
    print(f"[schema] 导出 {len(tools)} 个工具 -> {OUT}")
    for t in tools:
        print("   -", t["function"]["name"])


if __name__ == "__main__":
    main()
