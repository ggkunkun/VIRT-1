# -*- coding: utf-8 -*-
"""bridges/tool_calling_specs.py — Standard Tool Calling Schemas for LLM Agents.

Provides:
- OpenAI / Claude compatible JSON Schema tool specifications for the 6 CAD/CAM applications.
- Automatic tool call execution dispatcher `execute_tool_call()`.
"""

import os
import sys
import json
from typing import Dict, Any, List

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from bridges.six_software_orchestrator import SixSoftwareOrchestrator

_ORCHESTRATOR = None


def get_orchestrator() -> SixSoftwareOrchestrator:
    global _ORCHESTRATOR
    if _ORCHESTRATOR is None:
        _ORCHESTRATOR = SixSoftwareOrchestrator()
    return _ORCHESTRATOR


CADCAM_TOOLS_DEFINITION = [
    {
        "type": "function",
        "function": {
            "name": "cadcam_preflight",
            "description": "系统预检诊断：全面探测 SOLIDWORKS 2021、斯沃数控仿真 7.2、CIMCO Edit 2026、AutoCAD 2026、VERICUT 9.6 与 NX 12.0 六大工业软件的桌面快捷方式、可执行文件路径、运行进程 PID 与 COM 注册状态。",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cadcam_solidworks_model",
            "description": "SOLIDWORKS 2021 三维参数化特征建模：通过 COM Automation / VBA 宏驱动特征树、方程式管理器 (EquationMgr) 生成零件，并导出 STEP 实体或工程图。",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["model_flange", "annotate_drawing", "create_parametric_part", "execute_vba", "connect"],
                        "description": "执行动作：model_flange（带颈法兰盘参数化建模）、annotate_drawing（在工程图上放视图并标注尺寸与尺寸细节）、create_parametric_part（基础参数化建模）或 execute_vba（直接执行VBA代码）"
                    },
                    "annotation": {
                        "type": "object",
                        "description": "仅 action=annotate_drawing 时使用：{'dimensions': [{'target': 'D_outer'}], 'notes': ['一句尺寸细节'], 'gb': {...}}。可标注对象 target 只有这些：D_outer、D_hub、D_bore、D_bolt、t_base、hub_height（轮毂段高=H_total-t_base）、H_total；notes 写尺寸细节（孔数×孔径与分布圆、孔口倒角、材料、标准号）。gb 里按中国机械制图国标给图面细节：scale（如 1:2，GB/T 14690）、center_marks（true，GB/T 4457.4 中心线）、surface_finish（[{'target':..., 'ra':...}]，GB/T 131 表面结构）、tolerances（[{'target':..., 'fit':..., 'min_mm':..., 'max_mm':...}]，GB/T 4458.5 与 GB/T 1800 公差带）、general_tolerance（未注公差等级，GB/T 1804）、projection（第一角画法，GB/T 17451）。等轴测视图不标注尺寸。执行器会把图面真实读回来的尺寸、中心标记数、表面结构符号数与公差类型逐项核对，不靠返回值判定成功。"
                    },
                    "part_name": {
                        "type": "string",
                        "description": "零件名称：请自己起一个能体现你所选标准的名字（例如把标准号与规格写进名字），不要沿用示例占位名"
                    },
                    "dimensions": {
                        "type": "object",
                        "description": "关键几何尺寸字典，必须由你按所选标准自己算出并填入，例如 {'d_outer': <mm>, 'd_inner': <mm>, 'overall_len': <mm>, 'material': '<钢号>'}。本描述不提供任何可照抄的数值。"
                    },
                    "vba_code": {
                        "type": "string",
                        "description": "原生 SolidWorks VBA 宏代码（当 action 为 execute_vba 时必填）"
                    }
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cadcam_nx_journal",
            "description": "Siemens NX 12.0 无头日志运行与参数化建模：调用 NXBIN/run_journal.exe 运行 Python NXOpen 脚本，或构建包含表达式集合的 .prt 零件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["run_journal", "create_parametric_model"],
                        "description": "执行动作：run_journal（执行现有脚本）或 create_parametric_model（生成NXOpen参数化脚本）"
                    },
                    "script_path": {
                        "type": "string",
                        "description": "需执行的 Python NXOpen 脚本绝对路径"
                    },
                    "part_name": {
                        "type": "string",
                        "description": "NX 零件名称"
                    },
                    "expressions": {
                        "type": "object",
                        "description": "NX ExpressionCollection 参数表达式字典，数值须由你按所选规格自行给出，如 {'D_OUTER': <mm>, 'LENGTH': <mm>}。本描述不提供任何可照抄的数值。"
                    }
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cadcam_autocad_draw",
            "description": "AutoCAD 2026 二维工程制图与无头 DXF 生成：通过 ActiveX COM 发送 AutoLISP 代码、通过 accoreconsole 执行无头批处理，或利用 ezdxf 生成分层几何/公差图纸。",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["send_lisp", "create_dxf", "run_headless_script"],
                        "description": "执行动作：send_lisp（向活跃AutoCAD发LISP命令）、create_dxf（无头生成DXF图纸）、run_headless_script（accoreconsole无头执行）"
                    },
                    "code": {
                        "type": "string",
                        "description": "AutoLISP 表达式代码"
                    },
                    "drawing_name": {
                        "type": "string",
                        "description": "图纸名称"
                    },
                    "entities": {
                        "type": "array",
                        "description": "几何图元列表（line, circle, text, dimension 等）"
                    },
                    "script_path": {
                        "type": "string",
                        "description": "AutoLISP/SCR 脚本路径（供 accoreconsole 无头执行）"
                    }
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cadcam_cimco_validate",
            "description": "CIMCO Edit 2026 数控程序校验与外送准备：解析 FANUC Macro B 变量逻辑（#100、#500、WHILE/DO/END 括号配对）、模态 G 代码一致性，并拉起 CIMCO 视窗。",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["validate_macro", "launch"],
                        "description": "执行动作：validate_macro（深度静态语法与逻辑校验）或 launch（在CIMCO Edit中打开NC文件）"
                    },
                    "code": {
                        "type": "string",
                        "description": "G代码 / FANUC Macro B 代码文本"
                    },
                    "nc_file_path": {
                        "type": "string",
                        "description": "待打开的 NC 文件路径"
                    }
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cadcam_vericut_simulate",
            "description": "VERICUT 9.6 机床动力学仿真与防碰撞检验：调用 vericut.bat -b 启动无头批处理仿真，执行 Auto-Diff 过切/欠切检查与干涉报警日志解析。",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["run_simulation", "check_collision"],
                        "description": "执行动作：run_simulation（无头批处理仿真）或 check_collision（解析仿真碰撞日志）"
                    },
                    "project_path": {
                        "type": "string",
                        "description": "VERICUT 项目工程文件 (.vcproject) 路径"
                    },
                    "log_path": {
                        "type": "string",
                        "description": "仿真输出日志路径（用于干涉过切分析）"
                    }
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cadcam_sscnc_control",
            "description": "斯沃数控仿真软件 7.2 (SSCNC) 虚拟加工配置：拉起数控系统、设置 G54 工件坐标系、计算刀具几何补偿与刀尖象限 (T1-T9)，触发循环启动加工走刀。",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["launch", "find_window", "calculate_offsets"],
                        "description": "执行动作：launch（启动斯沃）、find_window（检测主窗句柄）、calculate_offsets（计算车铣刀偏与象限）"
                    },
                    "tools": {
                        "type": "array",
                        "description": "刀具规格列表，包含 tool_num, type, x, z, r, quadrant"
                    }
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cadcam_extreme_chain",
            "description": "极限极速闭环CAD/CAE/CAM全生命周期引擎：将制造意图按【绘图(ezdxf/GB图层) -> 建模(体积守恒ΔV>0/特征树) -> 仿真(解析FEA应力FOS>=1.5 & G00快速下刀防撞) -> 加工(FANUC Macro B变量与主轴模态)】全流程毫秒级执行(<100ms)；严格践行【未到极限则自愈重试，到了极限则熔断回滚并输出RCFA报告】。",
            "parameters": {
                "type": "object",
                "properties": {
                    "wish": {
                        "type": "string",
                        "description": "非标零件或模具制造意图描述，包含材质、主要直径、孔径、长度、特殊形状要求"
                    },
                    "out_root": {
                        "type": "string",
                        "description": "输出工程产物根目录（默认 runs/extreme_chain）"
                    },
                    "max_attempts": {
                        "type": "integer",
                        "description": "熔断尝试预算上限（默认 3 次）"
                    },
                    "tier2_native": {
                        "type": "boolean",
                        "description": "是否在毫秒级自查通过后连带驱动桌面原生六大软件（默认 False，极速毫秒模式）"
                    }
                },
                "required": ["wish"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cadcam_run_full_chain",
            "description": "六大软件全流水线串行驱动：将制造意图（愿望）按识图→AutoCAD工程图→SOLIDWORKS三维建模→NX多轴CAM→CIMCO宏程序→VERICUT仿真→斯沃加工的全流程执行并汇总实测取证。",
            "parameters": {
                "type": "object",
                "properties": {
                    "wish": {
                        "type": "string",
                        "description": "非标零件或模具制造意图描述，包含材质、主要直径、孔径、长度、特殊形状要求"
                    },
                    "out_root": {
                        "type": "string",
                        "description": "输出工程产物根目录（默认 runs/full_chain）"
                    },
                    "skip": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "跳过阶段列表，可选 sw2021, nx12, acad2026, cimco2026, vericut96, sscnc72"
                    }
                },
                "required": ["wish"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cadcam_desktop_gui",
            "description": "桌面视觉感知与窗口控制：截取桌面或指定工业软件窗口、自动点掉遮挡弹窗，或发送键鼠交互指令。",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["capture", "focus", "click", "type_text", "hotkey", "inspect_window", "dismiss_dialogs"],
                        "description": "动作类型"
                    },
                    "software": {
                        "type": "string",
                        "description": "目标软件名称，如 solidworks, autocad, sscnc, cimco, vericut, nx"
                    },
                    "x": {"type": "integer", "description": "屏幕或窗口内横坐标"},
                    "y": {"type": "integer", "description": "屏幕或窗口内纵坐标"},
                    "output_path": {"type": "string", "description": "截图保存路径",
                },
                                        "button": {"type": "string", "enum": ["left", "right", "middle"], "description": "鼠标键，默认 left"},
                    "double": {"type": "boolean", "description": "是否双击"},
                    "text": {"type": "string", "description": "仅 action=type_text：输入原文，经 CF_UNICODETEXT 剪贴板贴入当前焦点，不经 shell"},
                    "keys": {"type": "string", "description": "仅 action=hotkey：逗号分隔组合键，如 ctrl,s / alt,f4 / f5；解析不到的 token 报错不发送"}},
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cadcam_visual_inspect",
            "description": "工业视觉与图纸智能检测：对 VERICUT 仿真过切/欠切频谱、工程图图纸标题栏/视图区域、CNC 机床面板报警与屏幕进行计算机视觉分析。",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "enum": ["autodiff_inspection", "blueprint_analysis", "cnc_screen_perception"],
                        "description": "视觉分析任务类型：autodiff_inspection（VERICUT色谱过切欠切分析）、blueprint_analysis（工程图纸分块与标题栏识别）、cnc_screen_perception（CNC机床屏幕与报警感知）"
                    },
                    "image_path": {
                        "type": "string",
                        "description": "待分析的图像或截图绝对路径"
                    }
                },
                "required": ["task", "image_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cadcam_universal_geometry",
            "description": "通用机械几何解析与跨平台生成引擎：支持轴类(Shaft)、法兰盘(Flange)、键槽(Keyway)、轴承座/支架(BearingBracket)、钣金折弯(SheetMetal)等多零件族。自动生成GB国标AutoCAD工程图(DXF)、SolidWorks参数化VBA宏、Siemens NX 12 Python Journal、FANUC数控宏程序G代码。",
            "parameters": {
                "type": "object",
                "properties": {
                    "wish": {
                        "type": "string",
                        "description": "自然语言机械零件制造或几何需求描述"
                    },
                    "part_type": {
                        "type": "string",
                        "enum": ["auto", "shaft", "flange", "keyway", "bearing_bracket", "sheet_metal"],
                        "description": "零件家族类型（默认 auto 自动语义推断）"
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "工程产物输出目录路径（默认 runs/universal_cad）"
                    }
                },
                "required": ["wish"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cadcam_cae_stress_analysis",
            "description": "通用解析结构强度分析与几何闭环自愈引擎：依据受力工况（轴向拉伸/弯曲、法兰内压Lamé厚壁圆筒、平板Timoshenko弯曲、轴承座螺栓剪切拉拔）计算von Mises等效应力与安全系数(FOS)；当 FOS < 1.5 时触发物理尺寸反向闭环自愈，自动重算最小安全壁厚/截面。",
            "parameters": {
                "type": "object",
                "properties": {
                    "spec": {
                        "type": "object",
                        "description": "零件几何规格字典（包含 dimensions 或关键截面尺寸）"
                    },
                    "material": {
                        "type": "string",
                        "description": "工程材料名称（如 45号钢, 304不锈钢, Q235, Cr12MoV, 6061铝合金）"
                    },
                    "pressure_mpa": {
                        "type": "number",
                        "description": "承受内压力 (MPa)"
                    },
                    "force_n": {
                        "type": "number",
                        "description": "承受拉伸或剪切载荷力 (N)"
                    },
                    "torque_nm": {
                        "type": "number",
                        "description": "承受扭矩 (N·m)"
                    },
                    "target_fos": {
                        "type": "number",
                        "description": "设计安全系数下限（默认 1.5）"
                    }
                },
                "required": ["spec"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cadcam_sheetmetal_nest",
            "description": "钣金与下料排样引擎 (2D True-Shape Nesting)：基于最低水平线与Bottom-Left-Fill (BLF)启发式几何算法，支持零件旋转(0/90/180/270度)、间隙(kerf/margin)、板材利用率评估，并输出排样排版DXF工程图。",
            "parameters": {
                "type": "object",
                "properties": {
                    "parts": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "width": {"type": "number"},
                                "height": {"type": "number"},
                                "quantity": {"type": "integer"},
                                "allow_rotation": {"type": "boolean"}
                            },
                            "required": ["name", "width", "height"]
                        },
                        "description": "下料零件清单"
                    },
                    "sheet_width": {
                        "type": "number",
                        "description": "板材基料宽度 (mm，默认 1000.0)"
                    },
                    "sheet_height": {
                        "type": "number",
                        "description": "板材基料高度 (mm，默认 1000.0)"
                    },
                    "margin": {
                        "type": "number",
                        "description": "零件与板边以及零件间割缝安全间隙 (mm，默认 5.0)"
                    },
                    "output_dxf": {
                        "type": "string",
                        "description": "排样图 DXF 输出路径（可选）"
                    }
                },
                "required": ["parts"]
            }
        }
    }
]


def get_cadcam_tool_definitions() -> List[Dict[str, Any]]:
    """Return OpenAI/Claude standard tool specifications."""
    return CADCAM_TOOLS_DEFINITION


def execute_tool_call(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Execute LLM Tool Call and return JSON serializable result payload.
    Supports both canonical 'cadcam_*' tools and legacy 'vendor.action' tools from training corpora.
    """
    orch = get_orchestrator()
    args = arguments or {}

    # Compatibility layer: Map legacy training corpora tool names and args to canonical tools
    legacy_aliases = {
        "solidworks.create_parametric_part": ("cadcam_solidworks_model", {
            "action": "create_parametric_part",
            "part_name": args.get("part_name", "part"),
            "dimensions": args.get("spec", args.get("dimensions", {})),
            "vba_code": args.get("vba_code", ""),
        }),
        "nx.create_nxopen_script": ("cadcam_nx_journal", {
            "action": "create_parametric_model",
            "part_name": args.get("part_name", "nx_part"),
            "expressions": args.get("spec", args.get("expressions", {})),
            "script_path": args.get("script_path", ""),
        }),
        "autocad.create_autolisp": ("cadcam_autocad_draw", {
            "action": "send_lisp",
            "code": args.get("code", ""),
            "drawing_name": args.get("drawing_name", "drawing"),
            "entities": args.get("entities", []),
            "script_path": args.get("script_path", ""),
        }),
        "cimco.create_macro_b": ("cadcam_cimco_validate", {
            "action": "validate_macro",
            "code": args.get("code", args.get("macro_code", "")),
            "nc_file_path": args.get("nc_file_path", ""),
        }),
        "vericut.create_project_config": ("cadcam_vericut_simulate", {
            "action": "run_simulation",
            "project_path": args.get("project_path", ""),
            "log_path": args.get("log_path", ""),
        }),
        "sscnc.create_setup_guide": ("cadcam_sscnc_control", {
            "action": "calculate_offsets",
            "tools": args.get("tools", []),
        }),
        "cad.parse_wish_intent": ("cadcam_run_full_chain", {
            "wish": args.get("wish", args.get("intent", "")),
            "out_root": args.get("out_root"),
            "skip": tuple(args.get("skip", [])),
        }),
    }

    if tool_name in legacy_aliases:
        canonical_name, adapted_args = legacy_aliases[tool_name]
        tool_name = canonical_name
        args = adapted_args

    if tool_name == "ontology.lookup_plugin":
        from virtu_omni.knowledge.industrial_toolbox import SOFTWARE_ONTOLOGY
        sw = args.get("software", "all")
        if sw in SOFTWARE_ONTOLOGY:
            return {"status": "ok", "software": sw, "ontology": SOFTWARE_ONTOLOGY[sw]}
        return {"status": "ok", "all_software": list(SOFTWARE_ONTOLOGY.keys())}

    if tool_name == "cadcam_preflight":
        return orch.preflight()

    elif tool_name == "cadcam_solidworks_model":
        action = args.get("action", "create_parametric_part")
        params = {
            "part_name": args.get("part_name", "part"),
            "dimensions": args.get("dimensions", {}),
            "code": args.get("vba_code", ""),
        }
        return orch.dispatch("solidworks", action, params)

    elif tool_name == "cadcam_nx_journal":
        action = args.get("action", "run_journal")
        params = {
            "script_path": args.get("script_path", ""),
            "part_name": args.get("part_name", "nx_part"),
            "expressions": args.get("expressions", {}),
        }
        return orch.dispatch("nx", action, params)

    elif tool_name == "cadcam_autocad_draw":
        action = args.get("action", "send_lisp")
        params = {
            "code": args.get("code", ""),
            "drawing_name": args.get("drawing_name", "drawing"),
            "entities": args.get("entities", []),
            "script_path": args.get("script_path", ""),
        }
        return orch.dispatch("autocad", action, params)

    elif tool_name == "cadcam_cimco_validate":
        action = args.get("action", "validate_macro")
        params = {
            "code": args.get("code", ""),
            "nc_file_path": args.get("nc_file_path", ""),
        }
        return orch.dispatch("cimco", action, params)

    elif tool_name == "cadcam_vericut_simulate":
        action = args.get("action", "run_simulation")
        params = {
            "project_path": args.get("project_path", ""),
            "log_path": args.get("log_path", ""),
        }
        return orch.dispatch("vericut", action, params)

    elif tool_name == "cadcam_sscnc_control":
        action = args.get("action", "calculate_offsets")
        params = {
            "tools": args.get("tools", []),
        }
        return orch.dispatch("sscnc", action, params)

    elif tool_name == "cadcam_extreme_chain":
        return orch.run_extreme_chain(
            wish=args.get("wish", ""),
            out_root=args.get("out_root"),
            max_attempts=int(args.get("max_attempts", 3)),
            tier2_native=bool(args.get("tier2_native", False)),
        )

    elif tool_name == "cadcam_run_full_chain":
        return orch.run_full_chain(
            wish=args.get("wish", ""),
            out_root=args.get("out_root"),
            skip=tuple(args.get("skip", [])),
        )

    elif tool_name == "cadcam_desktop_gui":
        act = args.get("action", "capture")
        from bridges.desktop_controller import DesktopController
        ctl = DesktopController()
        if act == "capture":
            img_path = args.get("output_path", r"D:\Virtu模型\scratch\gui_capture.png")
            sw = args.get("software")
            return ctl.capture(output_path=img_path, software=sw)
        elif act == "focus":
            return ctl.focus(args.get("software", ""))
        elif act == "click":
            return ctl.click(args.get("x", 0), args.get("y", 0),
                             button=args.get("button", "left"), double=bool(args.get("double", False)))
        elif act == "type_text":
            return ctl.type_text(args.get("text", ""))
        elif act == "hotkey":
            return ctl.hotkey(args.get("keys", ""))
        elif act == "inspect_window":
            return ctl.diagnose_software_window(args.get("software", ""))
        elif act == "dismiss_dialogs":
            return ctl.dismiss_all_dialogs()
        return {"status": "error", "message": f"Unknown GUI action: {act}"}

    elif tool_name == "cadcam_visual_inspect":
        task = args.get("task", "autodiff_inspection")
        img_path = args.get("image_path", "")
        from bridges.cadcam_vision_bridge import CADCAMVisionBridge
        vb = CADCAMVisionBridge()
        if task == "autodiff_inspection":
            return vb.inspect_vericut_autodiff(img_path)
        elif task == "blueprint_analysis":
            return vb.analyze_drawing_blueprint(img_path)
        elif task == "cnc_screen_perception":
            return vb.inspect_cnc_screen(img_path)
        return {"status": "error", "message": f"Unknown visual inspect task: {task}"}

    elif tool_name == "cadcam_universal_geometry":
        return orch.universal_geometry(
            wish=args.get("wish", ""),
            part_type=args.get("part_type", "auto"),
            output_dir=args.get("output_dir"),
        )

    elif tool_name == "cadcam_cae_stress_analysis":
        return orch.cae_stress_analysis(
            spec=args.get("spec", {}),
            material=args.get("material", "45号钢"),
            pressure_mpa=float(args.get("pressure_mpa", 0.0)),
            force_n=float(args.get("force_n", 0.0)),
            torque_nm=float(args.get("torque_nm", 0.0)),
            target_fos=float(args.get("target_fos", 1.5)),
        )

    elif tool_name == "cadcam_sheetmetal_nest":
        return orch.sheetmetal_nest(
            parts=args.get("parts", []),
            sheet_width=float(args.get("sheet_width", 1000.0)),
            sheet_height=float(args.get("sheet_height", 1000.0)),
            margin=float(args.get("margin", 5.0)),
            output_dxf=args.get("output_dxf"),
        )

    return {"status": "error", "message": f"Unknown tool name: {tool_name}"}


if __name__ == "__main__":
    tools = get_cadcam_tool_definitions()
    print(f"Tool Calling Specs Defined: {len(tools)} tools available.")
    test_call = execute_tool_call("cadcam_cimco_validate", {
        "action": "validate_macro",
        "code": "G00 X100.0 Z50.0\n#500=1\nM30"
    })
    print("Test Execution Result:", test_call)
