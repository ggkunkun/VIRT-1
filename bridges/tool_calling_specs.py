# -*- coding: utf-8 -*-

"""bridges/tool_calling_specs.py — Standard Tool Calling Schemas for LLM Agents.

Provides:

- OpenAI / Claude compatible JSON Schema tool specifications for the 6 CAD/CAM applications.

- Automatic tool call execution dispatcher `execute_tool_call()`.

"""

import os

import sys

import json

import hmac

import time

import threading

from typing import Dict, Any, List, Optional, Tuple

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
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
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
                        "enum": [
                            "model_flange",
                            "annotate_drawing",
                            "create_parametric_part",
                            "execute_vba",
                            "mass_properties",
                            "connect",
                        ],
                        "description": "执行动作：model_flange（带颈法兰盘参数化建模）、annotate_drawing（在工程图上放视图并标注尺寸与尺寸细节）、create_parametric_part（基础参数化建模）、execute_vba（直接执行VBA代码）或 mass_properties（回读当前活动零件的真实体积/质量/质心，非理论估算）",
                    },
                    "annotation": {
                        "type": "object",
                        "description": "仅 action=annotate_drawing 时使用：{'dimensions': [{'target': 'D_outer'}], 'notes': ['一句尺寸细节'], 'gb': {...}}。可标注对象 target 只有这些：D_outer、D_hub、D_bore、D_bolt、t_base、hub_height（轮毂段高=H_total-t_base）、H_total；notes 写尺寸细节（孔数×孔径与分布圆、孔口倒角、材料、标准号）。gb 里按中国机械制图国标给图面细节：scale（如 1:2，GB/T 14690）、center_marks（true，GB/T 4457.4 中心线）、surface_finish（[{'target':..., 'ra':...}]，GB/T 131 表面结构）、tolerances（[{'target':..., 'fit':..., 'min_mm':..., 'max_mm':...}]，GB/T 4458.5 与 GB/T 1800 公差带）、general_tolerance（未注公差等级，GB/T 1804）、projection（第一角画法，GB/T 17451）。等轴测视图不标注尺寸。执行器会把图面真实读回来的尺寸、中心标记数、表面结构符号数与公差类型逐项核对，不靠返回值判定成功。",
                    },
                    "part_name": {
                        "type": "string",
                        "description": "零件名称：请自己起一个能体现你所选标准的名字（例如把标准号与规格写进名字），不要沿用示例占位名",
                    },
                    "dimensions": {
                        "type": "object",
                        "description": "关键几何尺寸字典，必须由你按所选标准自己算出并填入，例如 {'d_outer': <mm>, 'd_inner': <mm>, 'overall_len': <mm>, 'material': '<钢号>'}。本描述不提供任何可照抄的数值。",
                    },
                    "vba_code": {
                        "type": "string",
                        "description": "原生 SolidWorks VBA 宏代码（当 action 为 execute_vba 时必填）",
                    },
                },
                "required": ["action"],
            },
        },
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
                        "description": "执行动作：run_journal（执行现有脚本）或 create_parametric_model（生成NXOpen参数化脚本）",
                    },
                    "script_path": {
                        "type": "string",
                        "description": "需执行的 Python NXOpen 脚本绝对路径",
                    },
                    "part_name": {"type": "string", "description": "NX 零件名称"},
                    "expressions": {
                        "type": "object",
                        "description": "NX ExpressionCollection 参数表达式字典，数值须由你按所选规格自行给出，如 {'D_OUTER': <mm>, 'LENGTH': <mm>}。本描述不提供任何可照抄的数值。",
                    },
                },
                "required": ["action"],
            },
        },
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
                        "description": "执行动作：send_lisp（向活跃AutoCAD发LISP命令）、create_dxf（无头生成DXF图纸）、run_headless_script（accoreconsole无头执行）",
                    },
                    "code": {"type": "string", "description": "AutoLISP 表达式代码"},
                    "drawing_name": {"type": "string", "description": "图纸名称"},
                    "entities": {
                        "type": "array",
                        "description": "几何图元列表（line, circle, text, dimension 等）",
                    },
                    "script_path": {
                        "type": "string",
                        "description": "AutoLISP/SCR 脚本路径（供 accoreconsole 无头执行）",
                    },
                },
                "required": ["action"],
            },
        },
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
                        "description": "执行动作：validate_macro（深度静态语法与逻辑校验）或 launch（在CIMCO Edit中打开NC文件）",
                    },
                    "code": {
                        "type": "string",
                        "description": "G代码 / FANUC Macro B 代码文本",
                    },
                    "nc_file_path": {
                        "type": "string",
                        "description": "待打开的 NC 文件路径",
                    },
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cadcam_vericut_simulate",
            "description": "VERICUT 9.6 机床仿真与防碰撞检验。能力边界（2026-10-30 逆向实测）：VERICUT 9.6 不提供 COM/IPC/批处理/UIA 接口，vericut.bat -b 会空退出，因此 run_simulation 会明确返回 unsupported_headless 并给出 GUI 驱动通道（work/vericut-toolchain/vericut_link.py 的 launch_via_bat + play_simulation）；check_collision 解析真实仿真日志（中英文）统计碰撞/过切与错误行。",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["run_simulation", "check_collision"],
                        "description": "执行动作：run_simulation（尝试无头仿真；9.6 实测不支持，返回 unsupported_headless + GUI 通道指引）或 check_collision（解析仿真日志，统计碰撞/过切/错误行）",
                    },
                    "project_path": {
                        "type": "string",
                        "description": "VERICUT 项目工程文件 (.vcproject) 路径",
                    },
                    "log_path": {
                        "type": "string",
                        "description": "仿真输出日志路径（用于干涉过切分析）",
                    },
                },
                "required": ["action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cadcam_sscnc_control",
            "description": "斯沃数控仿真软件 7.2 (SSCNC) 虚拟加工配置：拉起数控系统、设置 G54 工件坐标系、计算刀具几何补偿与刀尖象限 (T1-T9)。面板按键仅在可寻址控件存在时可用；自绘面板会明确返回 unsupported，不伪称已循环启动。",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["launch", "find_window", "calculate_offsets", "panel_capability", "press_panel_key"],
                        "description": "执行动作：launch（启动斯沃）、find_window（检测主窗句柄）、calculate_offsets（计算车铣刀偏与象限）、panel_capability（探测面板是否有可寻址按键控件）、press_panel_key（按文本点按面板键；自绘面板会明确返回 unsupported）",
                    },
                    "key_label": {
                        "type": "string",
                        "description": "仅 action=press_panel_key 时使用：面板按键文本，如 EDIT、AUTO、MDI、循环启动",
                    },
                    "tools": {
                        "type": "array",
                        "description": "刀具规格列表，包含 tool_num, type, x, z, r, quadrant",
                    },
                },
                "required": ["action"],
            },
        },
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
                        "description": "非标零件或模具制造意图描述，包含材质、主要直径、孔径、长度、特殊形状要求",
                    },
                    "out_root": {
                        "type": "string",
                        "description": "输出工程产物根目录（默认 runs/extreme_chain）",
                    },
                    "max_attempts": {
                        "type": "integer",
                        "description": "熔断尝试预算上限（默认 3 次）",
                    },
                    "tier2_native": {
                        "type": "boolean",
                        "description": "是否在毫秒级自查通过后连带驱动桌面原生六大软件（默认 False，极速毫秒模式）",
                    },
                    "dialect": {
                        "type": "string",
                        "enum": ["fanuc", "siemens", "heidenhain"],
                        "description": "加工阶段额外发射的控制器方言 NC（默认 fanuc）。siemens=840D CYCLE81/83/84+TRAORI(仅五轴)，heidenhain=TNC Klartext CYCL DEF 200/203/207。同一 CL 刀路经坐标一致性门取证。",
                    },
                },
                "required": ["wish"],
            },
        },
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
                        "description": "非标零件或模具制造意图描述，包含材质、主要直径、孔径、长度、特殊形状要求",
                    },
                    "out_root": {
                        "type": "string",
                        "description": "输出工程产物根目录（默认 runs/full_chain）",
                    },
                    "skip": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "跳过阶段列表，可选 sw2021, nx12, acad2026, cimco2026, vericut96, sscnc72",
                    },
                },
                "required": ["wish"],
            },
        },
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
                        "enum": [
                            "capture",
                            "focus",
                            "click",
                            "move",
                            "drag",
                            "scroll",
                            "type_text",
                            "hotkey",
                            "inspect_window",
                            "dismiss_dialogs",
                        ],
                        "description": "动作类型",
                    },
                    "software": {
                        "type": "string",
                        "description": "目标软件名称，如 solidworks, autocad, sscnc, cimco, vericut, nx",
                    },
                    "x": {"type": "integer", "description": "屏幕或窗口内横坐标"},
                    "y": {"type": "integer", "description": "屏幕或窗口内纵坐标"},
                    "output_path": {
                        "type": "string",
                        "description": "截图保存路径",
                    },
                    "button": {
                        "type": "string",
                        "enum": ["left", "right", "middle"],
                        "description": "鼠标键，默认 left",
                    },
                    "double": {"type": "boolean", "description": "是否双击"},
                    "start_x": {"type": "integer", "description": "拖拽起始横坐标"},
                    "start_y": {"type": "integer", "description": "拖拽起始纵坐标"},
                    "end_x": {"type": "integer", "description": "拖拽终点横坐标"},
                    "end_y": {"type": "integer", "description": "拖拽终点纵坐标"},
                    "clicks": {"type": "integer", "description": "滚轮滚动单位（正数向上，负数向下）"},
                    "text": {
                        "type": "string",
                        "description": "仅 action=type_text：输入原文，经 CF_UNICODETEXT 剪贴板贴入当前焦点，不经 shell",
                    },
                    "keys": {
                        "type": "string",
                        "description": "仅 action=hotkey：逗号分隔组合键，如 ctrl,s / alt,f4 / f5；解析不到的 token 报错不发送",
                    },
                },
                "required": ["action"],
            },
        },
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
                        "enum": [
                            "autodiff_inspection",
                            "blueprint_analysis",
                            "cnc_screen_perception",
                        ],
                        "description": "视觉分析任务类型：autodiff_inspection（VERICUT色谱过切欠切分析）、blueprint_analysis（工程图纸分块与标题栏识别）、cnc_screen_perception（CNC机床屏幕与报警感知）",
                    },
                    "image_path": {
                        "type": "string",
                        "description": "待分析的图像或截图绝对路径",
                    },
                },
                "required": ["task", "image_path"],
            },
        },
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
                        "description": "自然语言机械零件制造或几何需求描述",
                    },
                    "part_type": {
                        "type": "string",
                        "enum": [
                            "auto",
                            "shaft",
                            "flange",
                            "keyway",
                            "bearing_bracket",
                            "sheet_metal",
                        ],
                        "description": "零件家族类型（默认 auto 自动语义推断）",
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "工程产物输出目录路径（默认 runs/universal_cad）",
                    },
                },
                "required": ["wish"],
            },
        },
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
                        "description": "零件几何规格字典（包含 dimensions 或关键截面尺寸）",
                    },
                    "material": {
                        "type": "string",
                        "description": "工程材料名称（如 45号钢, 304不锈钢, Q235, Cr12MoV, 6061铝合金）",
                    },
                    "pressure_mpa": {
                        "type": "number",
                        "description": "承受内压力 (MPa)",
                    },
                    "force_n": {
                        "type": "number",
                        "description": "承受拉伸或剪切载荷力 (N)",
                    },
                    "torque_nm": {"type": "number", "description": "承受扭矩 (N·m)"},
                    "target_fos": {
                        "type": "number",
                        "description": "设计安全系数下限（默认 1.5）",
                    },
                    "solver": {
                        "type": "string",
                        "enum": ["analytic", "pynite"],
                        "description": "求解器（默认 analytic 解析）。pynite=真实梁单元 FEA（仅回转轴/梁族，悬臂挠度/弯矩与解析解交叉核验，不可用诚实返回 unmeasured）。",
                    },
                },
                "required": ["spec"],
            },
        },
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
                                "allow_rotation": {"type": "boolean"},
                                "contour": {
                                    "type": "array",
                                    "items": {
                                        "type": "array",
                                        "items": {"type": "number"},
                                        "minItems": 2,
                                        "maxItems": 2,
                                    },
                                    "description": "真形状轮廓多边形顶点 [[x,y],...] (mm)；提供时按真实轮廓排样，缺省退化为 width×height 矩形",
                                },
                            },
                            "required": ["name", "width", "height"],
                        },
                        "description": "下料零件清单",
                    },
                    "sheet_width": {
                        "type": "number",
                        "description": "板材基料宽度 (mm，默认 1000.0)",
                    },
                    "sheet_height": {
                        "type": "number",
                        "description": "板材基料高度 (mm，默认 1000.0)",
                    },
                    "margin": {
                        "type": "number",
                        "description": "零件与板边以及零件间割缝安全间隙 (mm，默认 5.0)",
                    },
                    "output_dxf": {
                        "type": "string",
                        "description": "排样图 DXF 输出路径（可选）",
                    },
                },
                "required": ["parts"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cadcam_step_reverse",
            "description": "STEP 几何逆向测量：直接解析 STEP AP203/AP214 文本，不打开 CAD 即可返回产品树、包围盒、圆柱面直径谱、锥面半角，并按 MANIFOLD_SOLID_BREP 拆出每个实体的面数/母线圆弧/偏心孔系，最后给出 rebuild_recipe（回转母线站位+孔分布）。用于从 .step 反求尺寸后自行决定参数化建模策略。【理解装配体首选 action=bom】：把 8000 行几何压成结构化装配树（零件名/层级/实体面数/摆放坐标/紧凑 DSL），返回 prompt_context 可直接注入大模型，解决领域模型读不懂装配体的问题。第一步可先用 action=list 找到工作区内的 STEP 文件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "analyze", "assembly", "features", "bom"],
                        "description": "bom=结构化装配树+prompt_context(理解装配体首选)；list=列出可用 STEP；analyze=几何逆向测量；assembly=装配位姿；features=特征树",
                    },
                    "step_path": {
                        "type": "string",
                        "description": "工作区内 .step 文件的绝对路径（action=analyze 时必填）",
                    },
                    "name_contains": {
                        "type": "string",
                        "description": "action=list 时按文件名子串过滤，可选",
                    },
                    "max_bodies": {
                        "type": "integer",
                        "description": "最多返回的实体明细数，默认 6",
                    },
                    "detail": {
                        "type": "boolean",
                        "description": "true=返回逐孔坐标等完整明细（体积较大）；默认 false 精简",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cadcam_assembly_build",
            "description": "逆向工程后的建模/拼装/出图执行器。understand=只理解：解析 BOM（含旋转位姿）、拆件、实测每件体积、推断共面/同轴配合候选；build_mated=在 SolidWorks 里逐件导入原生 SLDPRT、按 BOM 位姿插入、加真实配合（选面后核对曲面类型/半径，漂移即撤销），保存 .SLDASM 并重开核对组件位姿与配合；full_mated=understand+build_mated+GB 第一角三视图与等轴测 .SLDDRW，全部产出带门禁的 verification.json；model=按 STEP 母线剖面参数化重建回转件；assemble=导入 STEP 总成；drawing=仅出图；full=旧版三步。",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["model", "assemble", "drawing", "full",
                                 "understand", "build_mated", "full_mated"],
                        "description": "understand / build_mated / full_mated 为真实装配链路；model / assemble / drawing / full 为旧版导入链路",
                    },
                    "step_path": {
                        "type": "string",
                        "description": "工作区内 STEP 绝对路径；留空则用 assets/wheel_mold_P0.step",
                    },
                    "out_dir": {
                        "type": "string",
                        "description": "产物目录（必须位于工作区内）；留空用 runs/virtu_assembly",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cadcam_feature_ops",
            "description": "原子特征执行器：不提供任何一键策略，只按你自己给出的方案逐步执行。action=measure 返回 STEP 原始测量数据（母线闭合点列、直径谱、孔系、包围盒）；action=execute_plan 严格按 plan.ops 顺序执行，每个 op 后立即读质量属性形成证据链，不认识或缺参数的 op 如实报错、绝不自动补齐。",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["measure", "execute_plan", "single_case"], "description": "measure=读测量数据；execute_plan=按你的方案执行"},
                    "plan": {
                        "type": "object",
                        "description": "建模方案。格式 {'ops':[ ... ]}。可用 op 按你的方法自行排序：new_part；sketch_profile(source=step_meridian 或 points=[[x,r],...], plane)；revolve(angle_deg)；sketch_holes(pcd_mm,hole_dia_mm,count,angles_deg,plane)；cut(type=through_all)；save_part(name)；import_assembly(step_path)；save_assembly(name)；drawing(template,first_angle,isometric,model_path,name)；verify。特征顺序、参数、是否使用某步骤全由你决定。",
                        "properties": {
                            "ops": {"type": "array", "items": {"type": "object"}},
                            "method_reason": {"type": "string", "description": "你选择这套特征顺序与参数的理由"},
                            "expected_volume_mm3": {"type": "number", "description": "你预期最终体积，用于与实测对比"}
                        }
                    },
                    "step_path": {"type": "string", "description": "工作区内 STEP 绝对路径"},
                    "out_dir": {"type": "string", "description": "产物目录（工作区内）"}
                },
                "required": []
            }
        }
    },
]

# 内部入口（不进对模型的宣告面，但仍可 dispatch、仍走同一套参数校验）
# ---------------------------------------------------------------------------
# 三个联网工具被降级的唯一理由是「结果不可复现」：检索命中的网页、正文长度、
# 抓取时刻的外部状态都不由本仓决定，无法给出确定性判据。判分面只允许放
# 「同一个调用在同一输入下必然得到同一个可判结果」的工具，否则分数里会混进
# 网络抖动（见 virtu_eval/tool_schema.py 与 COVERAGE.json 的同一条纪律）。
# 它们仍是真实能力：execute_tool_call 照常执行，旧语料名映射照常生效，
# 只是不再由模型自主选择、不参与能力分。
INTERNAL_TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "cadcam_web_search",
            "description": "互联网安全深度检索：对工业制造标准、材料性能、力学公式、前沿学术文献进行全网实时检索，严格自动过滤不良信息与恶意攻击，脱敏个人隐私与凭据。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "检索关键词或技术问题描述"},
                    "num_results": {"type": "integer", "description": "返回结果条数（默认4）"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cadcam_fetch_web_content",
            "description": "互联网网页正文抓取与清洗：提取目标网页主体正文并自动执行脚本净化、不良内容拦截与 PII 脱敏。",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "目标网页 URL"},
                    "max_chars": {"type": "integer", "description": "最大字符限制（默认3000）"}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cadcam_internet_deep_learning",
            "description": "互联网深度学习与语料内化：将检索到的经过安全过滤的工程资料向量化存入本地语义知识库，并自动合成高质量持续学习 SFT 训练数据对。",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "学习主题"},
                    "content": {"type": "string", "description": "技术正文内容"},
                    "source_url": {"type": "string", "description": "资料来源 URL"}
                },
                "required": ["topic", "content"]
            }
        }
    },
]

# 说明（审计 §4-2/§4-6）：
# cad.query_standard_parts_library 与 web.search_technical_knowledge /
# cadcam_knowledge_lookup 都是「内部可调用入口」，刻意不写进上面的对模型宣告面。
# 原因见 virtu_eval/tool_schema.py 的说明：宣告面每项都必须有可判分用例；
# 在没补 holdout 用例前扩充宣告面，会让能力分出现无法归因的漂移。
# 这些入口仍可通过 execute_tool_call 正常调用（含旧语料名映射）。
# 2026-11-13：三个联网工具也按同一理由移入 INTERNAL_TOOL_DEFINITIONS，
# 宣告面 20 → 17；`cadcam_feature_ops` 补齐 4 条 toolrouting 用例后留在宣告面。


def get_cadcam_tool_definitions() -> List[Dict[str, Any]]:
    """Return OpenAI/Claude standard tool specifications."""
    try:
        from bridges.agent_desktop_bridge import get_agent_desktop_tool_definitions
        desktop_tools = get_agent_desktop_tool_definitions()
    except Exception:
        desktop_tools = []
    return CADCAM_TOOLS_DEFINITION + desktop_tools


# ============================================================================
# V-05：工具层风险分级与审批
# ============================================================================
# 旧实现的 execute_tool_call 只按名字硬编码分发 30+ 工具，除 cadcam_desktop_gui
# 外没有任何风险分级：模型只要吐出一个 "cadcam_run_full_chain" 或
# "cad.execute_solidworks_macro"，就会直接驱动 6 套工业软件、写盘、执行 VBA。
# 现在按"副作用强度"分三级，写盘/驱动/执行代码类默认要求显式授权。

TOOL_APPROVAL_ENV = "VIRTU_TOOL_APPROVAL"          # "1" = 全局授权；"0"/"off" = 关闭分级
TOOL_APPROVAL_FILE_ENV = "VIRTU_TOOL_APPROVAL_FILE"
TOOL_APPROVAL_TOKEN_ENV = "VIRTU_TOOL_APPROVAL_TOKEN"
TOOL_APPROVAL_TTL_ENV = "VIRTU_TOOL_APPROVAL_TTL_S"
TOOL_APPROVAL_AUDIT_ENV = "VIRTU_TOOL_APPROVAL_AUDIT_LOG"
DEFAULT_TOOL_APPROVAL_TTL_S = 900.0

RISK_READ = "read"      # 只读：查询/诊断/计算
RISK_WRITE = "write"    # 写盘/驱动 CAD 生成模型/跑仿真
RISK_SYSTEM = "system"  # 执行任意代码（VBA/宏/journal）或操作桌面键鼠

#: 只读工具白名单（其余一律视为 write，除非显式列为 system）
READ_ONLY_TOOLS = frozenset({
    "ontology.lookup_plugin", "cadcam_preflight", "cadcam_cimco_validate",
    "cadcam_sscnc_control", "cadcam_web_search", "web_search",
    "cadcam_knowledge_lookup", "web.search_technical_knowledge",
    "cadcam_fetch_web_content", "fetch_web_content",
    "cadcam_internet_deep_learning", "internet_deep_learning",
    "cad.infer_blueprint_feature_tree", "cad.infer_equipment_intent",
    "cad.decompose_automation_assembly", "cad.query_standard_parts_library",
    "cadcam_step_reverse.list", "cadcam_step_reverse.analyze",
    "cadcam_step_reverse.assembly", "cadcam_step_reverse.bom",
    "cadcam_step_reverse.features",
    "cadcam_autocad_draw.create_dxf",
    "cadcam_solidworks_model.mass_properties",
    "cadcam_desktop_gui.capture", "cadcam_desktop_gui.inspect_window",
    "cadcam_desktop_gui.move",
    "agent.verify_and_self_optimize",
    "memory.commit_long_term_experience",
    # 只读观测类桌面工具：查状态 / 列窗口 / 结构化感知不应需要审批，
    # 否则 Agent 连"先看一眼桌面有什么"都过不去。输入类（click/type/press/
    # focus_window/launch/batch）仍按 system 处理。
    "desktop_status", "desktop_list_displays", "desktop_list_apps",
    "desktop_list_windows", "desktop_snapshot", "desktop_find",
})

#: 会执行不可信代码或操作真实桌面输入的工具
SYSTEM_RISK_TOOLS = frozenset({
    "cadcam_desktop_gui", "cadcam_visual_inspect",
    "cad.execute_solidworks_macro", "cadcam_nx_journal", "cadcam_autocad_draw",
    "skill.synthesize_agent_skill",
})


def tool_risk_level(tool_name: str, args: Optional[Dict[str, Any]] = None) -> str:
    name = str(tool_name or "").strip()
    act = str((args or {}).get("action") or "").strip().lower()
    if name in READ_ONLY_TOOLS or (act and f"{name}.{act}" in READ_ONLY_TOOLS):
        return RISK_READ
    if name in SYSTEM_RISK_TOOLS:
        return RISK_SYSTEM
    if name.startswith("desktop_") or name.startswith("agent_desktop"):
        return RISK_SYSTEM
    if name.startswith("cadcam_") or name.startswith("cad.") or name.startswith("solidworks."):
        return RISK_WRITE
    if name.startswith("script_"):
        return RISK_SYSTEM
    # 未知工具按最高风险对待（fail-closed）
    return RISK_SYSTEM


def _approval_file_path() -> str:
    return os.environ.get(TOOL_APPROVAL_FILE_ENV) or os.path.join(
        _ROOT, "runs", "tool_approval", "approval.json")


def _approval_scope_allows(scope: Any, tool_name: str) -> bool:
    """审批文件里的 allow 可以是 ["*"] / ["cadcam_*"] / ["具体工具名"]。"""
    if isinstance(scope, str):
        scope = [scope]
    if not isinstance(scope, (list, tuple)):
        return False
    for entry in scope:
        token = str(entry or "").strip()
        if not token:
            continue
        if token in ("*", "all"):
            return True
        if token.endswith("*") and tool_name.startswith(token[:-1]):
            return True
        if token == tool_name:
            return True
    return False


def approval_granted(tool_name: str, args: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
    """返回 (是否授权, 依据说明)。默认拒绝，只有显式授权才放行。"""
    args = args or {}

    # 1) 调用参数里带一次性令牌（适合服务端逐次授权）
    expected_token = str(os.environ.get(TOOL_APPROVAL_TOKEN_ENV) or "").strip()
    if expected_token:
        supplied = str(args.get("_approval") or args.get("approval_token") or "").strip()
        if supplied and hmac.compare_digest(supplied, expected_token):
            return True, "approval_token"

    # 2) 环境变量全局授权（运维显式开关）
    env_flag = str(os.environ.get(TOOL_APPROVAL_ENV) or "").strip().lower()
    if env_flag in ("1", "true", "yes", "on"):
        return True, "env:%s" % TOOL_APPROVAL_ENV

    # 3) 审批文件（带 TTL，避免"授权一次永久生效"）
    path = _approval_file_path()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, ValueError):
        return False, "no_approval"
    if not isinstance(payload, dict):
        return False, "no_approval"
    try:
        ttl = float(os.environ.get(TOOL_APPROVAL_TTL_ENV) or
                    payload.get("ttl_s") or DEFAULT_TOOL_APPROVAL_TTL_S)
    except (TypeError, ValueError):
        ttl = DEFAULT_TOOL_APPROVAL_TTL_S
    try:
        granted_at = float(payload.get("granted_at") or 0)
    except (TypeError, ValueError):
        granted_at = 0
    if ttl > 0 and (time.time() - granted_at) > ttl:
        return False, "approval_expired"
    if _approval_scope_allows(payload.get("allow"), tool_name):
        return True, "approval_file"
    return False, "tool_not_in_approval_scope"


def _approval_audit(tool_name: str, args: Dict[str, Any], verdict: Dict[str, Any]) -> None:
    path = os.environ.get(TOOL_APPROVAL_AUDIT_ENV) or os.path.join(
        _ROOT, "runs", "tool_approval", "decisions.jsonl")
    rec = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "tool": tool_name,
        "risk": tool_risk_level(tool_name, args),
        "action": args.get("action"),
        "decision": verdict.get("status", "allowed"),
        "verdict_code": verdict.get("verdict_code"),
        "detail": verdict.get("detail"),
    }
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass


# --- V-08：入参体积上限 ------------------------------------------------------
# 旧实现把模型给的字符串原样塞进 VBA 宏 / 键鼠输入 / base64 图像，没有长度概念：
# 一个超大 vba_code 足以让 CAD 进程吃到 OOM，超长 type_text 则会向真实窗口
# 灌入巨量按键。这里按参数语义设上限，超限直接拒绝，不进入任何执行分支。
PAYLOAD_TEXT_MAX = 8 * 1024            # 键入文本 / 热键串
PAYLOAD_CODE_MAX = 256 * 1024          # VBA 宏 / journal / AutoLISP
PAYLOAD_STRING_MAX = 1 * 1024 * 1024   # 其余单个字符串参数
PAYLOAD_TOTAL_MAX = 4 * 1024 * 1024    # 整个参数集合

_TEXT_KEYS = ("text", "typed_text", "keys", "comment", "note")
_CODE_KEYS = ("vba_code", "macro", "code", "script", "journal", "lisp", "source")


def _payload_limit_for(key: str) -> int:
    low = key.lower()
    if low in _TEXT_KEYS or low.endswith("_text"):
        return PAYLOAD_TEXT_MAX
    if low in _CODE_KEYS or low.endswith("_code") or low.endswith("_script"):
        return PAYLOAD_CODE_MAX
    return PAYLOAD_STRING_MAX


def payload_size_gate(tool_name: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """返回 None 表示体积合规；否则返回拒绝结果。"""
    if not isinstance(args, dict):
        return None
    total = 0
    for key, value in args.items():
        if isinstance(value, str):
            size = len(value.encode("utf-8", "replace"))
        elif isinstance(value, (bytes, bytearray)):
            size = len(value)
        else:
            continue
        total += size
        limit = _payload_limit_for(str(key))
        if size > limit:
            verdict = {
                "status": "blocked",
                "verdict_code": "PAYLOAD_TOO_LARGE",
                "detail": ("参数 '%s' 体积 %d 字节超过上限 %d 字节（工具 %s）"
                           % (key, size, limit, tool_name)),
                "channel": "repo_execute_tool_call",
                "input_sent": False,
            }
            _approval_audit(tool_name, args, verdict)
            return verdict
    if total > PAYLOAD_TOTAL_MAX:
        verdict = {
            "status": "blocked",
            "verdict_code": "PAYLOAD_TOO_LARGE",
            "detail": "参数总体积 %d 字节超过上限 %d 字节（工具 %s）"
                      % (total, PAYLOAD_TOTAL_MAX, tool_name),
            "channel": "repo_execute_tool_call",
            "input_sent": False,
        }
        _approval_audit(tool_name, args, verdict)
        return verdict
    return None


def path_traversal_gate(tool_name: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """路径穿越门：任一路径参数逃出授权工作区即拦截（返回 None 表示放行）。

    必须**先于审批门**执行：``out_root=C:/Windows/System32`` 这类明显越界属于攻击，
    若先走审批就会返回 ``TOOL_APPROVAL_REQUIRED``，把"已拦截"降级成"待批准"。
    """
    from bridges.bridge_security import path_allowed

    path_param_keys = (
        "script_path", "output_dir", "out_root", "nc_file_path", "project_path",
        "log_path", "output_path", "output_dxf", "file_path", "target_path",
        "step_path", "out_dir",
    )

    # 额外授权根（AGENT_CHAIN_RUNTIME.md 承诺的 VIRTU_ALLOWED_ROOTS 扩展位）
    extra_roots: List[str] = []
    for _seg in os.environ.get("VIRTU_ALLOWED_ROOTS", "").replace(";", os.pathsep).split(os.pathsep):
        _seg = _seg.strip()
        if _seg:
            try:
                extra_roots.append(os.path.realpath(os.path.abspath(_seg)))
            except OSError:
                pass

    for pk in path_param_keys:
        if pk in args and args[pk]:
            val = str(args[pk])
            allowed = path_allowed(val, _ROOT) or any(
                path_allowed(val, r) for r in extra_roots
            )
            if not allowed and pk == "step_path":
                import tempfile

                desktop = os.path.expanduser(r"~\Desktop")
                allowed = path_allowed(val, desktop) or path_allowed(
                    val, tempfile.gettempdir()
                )
            if not allowed:
                return {
                    "status": "blocked",
                    "verdict_code": "PATH_TRAVERSAL_BLOCKED",
                    "detail": f"Field '{pk}' with path '{val}' escapes authorized workspace '{_ROOT}'",
                    "allowed_roots": [_ROOT] + extra_roots,
                    "channel": "repo_execute_tool_call",
                    "input_sent": False,
                }
    return None


def security_audit_gate(tool_name: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """参数安全与代码注入审计（VBA Shell / AutoLISP startapp / 几何超差 / 撞机下刀）。

    与路径门同理，必须**先于审批门**执行：`Shell "cmd.exe /c whoami"` 这类攻击必须
    直接判 ``SECURITY_AUDIT_VIOLATION``，不能被"待审批"降级。
    """
    from virtu_omni.security.auditor import ModelSecurityAuditor

    sec_auditor = ModelSecurityAuditor(workspace_root=_ROOT)
    audit_res = sec_auditor.audit_tool_arguments(tool_name, args)
    if not audit_res["passed"]:
        return {
            "status": "blocked",
            "verdict_code": "SECURITY_AUDIT_VIOLATION",
            "violations": audit_res["violations"],
            "detail": "; ".join(audit_res["violations"]),
            "channel": "repo_execute_tool_call",
            "input_sent": False,
        }
    return None


def approval_gate(tool_name: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """拦截器：返回 None 表示放行；否则返回应直接回给调用方的拒绝结果。"""
    if tool_name == "cadcam_desktop_gui":
        # cadcam_desktop_gui 由专用 bridges/desktop_gate.py 强制执行（含只读放行、OPT_IN、焦点绑定与 HMAC 审计链）
        return None
    mode = str(os.environ.get(TOOL_APPROVAL_ENV) or "").strip().lower()
    if mode in ("0", "off", "loose"):
        return None
    risk = tool_risk_level(tool_name, args)
    if risk == RISK_READ:
        return None
    granted, basis = approval_granted(tool_name, args)
    if granted:
        return None
    verdict = {
        "status": "blocked",
        "verdict_code": "TOOL_APPROVAL_REQUIRED",
        "detail": ("工具 %s（风险等级 %s）需要显式授权：设置 %s=1、提供 %s 匹配的 "
                   "approval_token，或在 %s 写入 allow 列表（判定依据：%s）"
                   % (tool_name, risk, TOOL_APPROVAL_ENV, TOOL_APPROVAL_TOKEN_ENV,
                      _approval_file_path(), basis)),
        "risk": risk,
        "channel": "repo_execute_tool_call",
        "input_sent": False,
    }
    _approval_audit(tool_name, args, verdict)
    return verdict


# ---------------------------------------------------------------------------
# A 组：工具层三道闸 —— (1) jsonschema 参数校验 (2) 路径白名单双侧共用
#            (3) 统一超时/重试装饰（有界等待）
# 审计依据：§4.2（LLM 直调路径零校验）、增强项 3
# ---------------------------------------------------------------------------

TOOL_SCHEMA_MODE_ENV = "VIRTU_TOOL_SCHEMA_MODE"     # enforce（默认）/ warn / off
TOOL_TIMEOUT_ENV = "VIRTU_TOOL_TIMEOUT_S"           # 单次工具调用等待上限（秒）
TOOL_RETRY_ENV = "VIRTU_TOOL_RETRIES"               # 仅对异常重试，逻辑性错误不重试
DEFAULT_TOOL_TIMEOUT_S = 120.0
DEFAULT_TOOL_RETRIES = 1
_SCHEMA_CACHE: Dict[str, Any] = {}


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or str(raw).strip() == "":
        return float(default)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return float(default)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or str(raw).strip() == "":
        return int(default)
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return int(default)


def get_tool_parameter_schemas() -> Dict[str, Dict[str, Any]]:
    """工具名 -> JSON Schema parameters（宣告面 + 内部入口，二者同一套校验）。"""
    if _SCHEMA_CACHE:
        return _SCHEMA_CACHE
    try:
        # get_cadcam_tool_definitions() 已并入 13 个 desktop_* 工具定义；
        # 旧实现只取 CADCAM_TOOLS_DEFINITION，desktop_* 无 schema ⇒ 中央闸门空转（E7）。
        for item in list(get_cadcam_tool_definitions()) + list(INTERNAL_TOOL_DEFINITIONS):
            fn = item.get("function") or {}
            name = fn.get("name")
            params = fn.get("parameters")
            if name and isinstance(params, dict):
                _SCHEMA_CACHE[name] = params
    except Exception:
        pass
    return _SCHEMA_CACHE


def _scalar_type_ok(value: Any, expected: str) -> bool:
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        if isinstance(value, bool):
            return False
        return isinstance(value, int) or (isinstance(value, float) and float(value).is_integer())
    if expected == "number":
        return (not isinstance(value, bool)) and isinstance(value, (int, float))
    if expected == "array":
        return isinstance(value, (list, tuple))
    if expected == "object":
        return isinstance(value, dict)
    return True


def validate_tool_arguments(tool_name: str, args: Dict[str, Any]) -> List[Dict[str, Any]]:
    """返回结构化错误列表（空列表=通过）。每条含 field / reason / expected / actual。"""
    schemas = get_tool_parameter_schemas()
    schema = schemas.get(tool_name)
    if not schema:
        return []
    props = schema.get("properties") or {}
    errors: List[Dict[str, Any]] = []

    for field in schema.get("required") or []:
        if field not in args or args.get(field) in (None, ""):
            errors.append({"field": field, "reason": "required_missing",
                           "expected": "non-empty value", "actual": args.get(field)})

    for field, rule in props.items():
        if field not in args or not isinstance(rule, dict):
            continue
        value = args.get(field)
        if value is None:
            continue
        expected_type = rule.get("type")
        # 只对 JSON 标量做严格类型校验；object/array 允许调用方用 tuple/dict 等 Python 等价物
        if expected_type in ("string", "boolean", "integer", "number"):
            if not _scalar_type_ok(value, expected_type):
                errors.append({"field": field, "reason": "type_mismatch",
                               "expected": expected_type, "actual": type(value).__name__})
                continue
        enum_vals = rule.get("enum")
        if enum_vals and expected_type == "string" and isinstance(value, str) and value not in enum_vals:
            errors.append({"field": field, "reason": "enum_violation",
                           "expected": list(enum_vals), "actual": value})
            continue
        if expected_type in ("integer", "number") and isinstance(value, (int, float)) and not isinstance(value, bool):
            if "minimum" in rule and value < rule["minimum"]:
                errors.append({"field": field, "reason": "below_minimum",
                               "expected": rule["minimum"], "actual": value})
            if "maximum" in rule and value > rule["maximum"]:
                errors.append({"field": field, "reason": "above_maximum",
                               "expected": rule["maximum"], "actual": value})
    return errors


def schema_gate(tool_name: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """参数 Schema 闸门：enforce 拒绝、warn 放行但回显 schema_warnings、off 全关。"""
    mode = (os.environ.get(TOOL_SCHEMA_MODE_ENV) or "enforce").strip().lower()
    if mode in ("0", "off", "disabled"):
        return None
    try:
        errors = validate_tool_arguments(tool_name, args or {})
    except Exception as exc:  # 校验器自身异常不得放行非法调用
        errors = [{"field": "<validator>", "reason": "validator_error", "actual": str(exc)}]
    if not errors:
        return None
    if mode == "warn":
        return None
    return {
        "status": "invalid_arguments",
        "verdict_code": "TOOL_SCHEMA_VIOLATION",
        "tool": tool_name,
        "errors": errors,
        "detail": "; ".join(
            "{field}:{reason}".format(**e) for e in errors if isinstance(e, dict)
        ),
        "channel": "repo_execute_tool_call",
        "input_sent": False,
    }


def _invoke_with_budget(fn, tool_name: str) -> Dict[str, Any]:
    """有界等待 + 有限重试（仅对异常重试）。

    说明：Python 线程无法被强制终止，等待上限只保证 **调用方不再无界阻塞**；
    超时后底层调用可能仍在后台线程中继续，这一点在返回体 ``note`` 里如实披露。
    """
    timeout_s = _env_float(TOOL_TIMEOUT_ENV, DEFAULT_TOOL_TIMEOUT_S)
    retries = max(0, _env_int(TOOL_RETRY_ENV, DEFAULT_TOOL_RETRIES))
    attempts = 0
    last_error = None
    while attempts <= retries:
        attempts += 1
        box: Dict[str, Any] = {}

        def _runner():
            try:
                box["value"] = fn()
            except BaseException as exc:  # noqa: BLE001 - 需把异常转成结构化返回
                box["error"] = exc

        worker = threading.Thread(target=_runner, name=f"toolcall:{tool_name}", daemon=True)
        t0 = time.time()
        worker.start()
        worker.join(timeout_s)
        if worker.is_alive():
            return {
                "status": "timeout",
                "verdict_code": "TOOL_TIMEOUT",
                "tool": tool_name,
                "timeout_s": timeout_s,
                "attempts": attempts,
                "detail": f"tool '{tool_name}' 超过 {timeout_s}s 未返回，调用方已放弃等待",
                "note": "Python 线程不可强杀，底层调用可能仍在后台继续",
                "channel": "repo_execute_tool_call",
            }
        elapsed_ms = int((time.time() - t0) * 1000)
        if "error" in box:
            last_error = box["error"]
            if attempts <= retries:
                time.sleep(0.05 * attempts)
                continue
            return {
                "status": "error",
                "verdict_code": "TOOL_EXECUTION_ERROR",
                "tool": tool_name,
                "attempts": attempts,
                "elapsed_ms": elapsed_ms,
                "detail": f"{type(last_error).__name__}: {last_error}",
                "channel": "repo_execute_tool_call",
            }
        value = box.get("value")
        if isinstance(value, dict):
            return value
        return {"status": "ok", "tool": tool_name, "result": value,
                "elapsed_ms": elapsed_ms, "channel": "repo_execute_tool_call"}
    return {"status": "error", "verdict_code": "TOOL_EXECUTION_ERROR",
            "tool": tool_name, "detail": "unreachable", "channel": "repo_execute_tool_call"}


#: 统一响应信封字段（AGENT_TOOLCHAIN_INTERFACE.md §三.4）。
#: ``data`` 由业务字段聚合；信封自身与诊断字段不重复进 data。
_ENVELOPE_KEYS = frozenset({
    "status", "data", "execution_time_ms",
    "verdict_code", "detail", "note",
    "tool", "attempts", "elapsed_ms", "channel", "arg_remap",
})


#: 分发器实际支持的规范工具名（含 legacy 别名，见 _execute_tool_call_impl）。
#: 用于把"拼错工具名"诊断为 UNKNOWN_TOOL，而不是误报 TOOL_APPROVAL_REQUIRED。
_DISPATCHER_TOOL_NAMES = frozenset({
    "agent.verify_and_self_optimize",
    "cad.assemble_components_with_mates",
    "cad.decompose_automation_assembly",
    "cad.infer_blueprint_feature_tree",
    "cad.infer_equipment_intent",
    "cad.query_standard_parts_library",
    "cadcam_assembly_build",
    "cadcam_autocad_draw",
    "cadcam_cae_stress_analysis",
    "cadcam_cimco_validate",
    "cadcam_desktop_gui",
    "cadcam_extreme_chain",
    "cadcam_feature_ops",
    "cadcam_fetch_web_content",
    "cadcam_internet_deep_learning",
    "cadcam_knowledge_lookup",
    "cadcam_nx_journal",
    "cadcam_preflight",
    "cadcam_run_full_chain",
    "cadcam_sheetmetal_nest",
    "cadcam_solidworks_model",
    "cadcam_sscnc_control",
    "cadcam_step_reverse",
    "cadcam_universal_geometry",
    "cadcam_vericut_simulate",
    "cadcam_visual_inspect",
    "cadcam_web_search",
    "fetch_web_content",
    "internet_deep_learning",
    "memory.commit_long_term_experience",
    "ontology.lookup_plugin",
    "skill.synthesize_agent_skill",
    "software.dispatch_industrial_tool",
    "web.search_technical_knowledge",
    "web_search",
})

_KNOWN_TOOL_CACHE: Dict[str, Any] = {}


def known_tool_names() -> frozenset:
    """全部可调用工具名（分发器规范名 ∪ LLM 工具定义名），惰性缓存。"""
    cached = _KNOWN_TOOL_CACHE.get("names")
    if cached is not None:
        return cached
    names = set(_DISPATCHER_TOOL_NAMES)
    try:
        names.update(t["function"]["name"] for t in get_cadcam_tool_definitions())
    except Exception:
        pass
    _KNOWN_TOOL_CACHE["names"] = names
    return names


def unknown_tool_gate(tool_name: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """工具存在性门（最先执行）：名字不认识就是 UNKNOWN_TOOL。

    在此之前，拼错的工具名会一路走到审批门，被 fail-closed 的 RISK_SYSTEM 判成
    ``TOOL_APPROVAL_REQUIRED``——让人误以为「授权就能用」。工具名错误与授权是两件
    事，必须分开诊断。命名空间前缀（``desktop_*`` / ``agent_desktop*``）交给对应
    bridge 裁决，这里不拦。
    """
    name = str(tool_name or "").strip()
    if not name:
        return {
            "status": "error",
            "verdict_code": "UNKNOWN_TOOL",
            "detail": "工具名为空",
            "channel": "repo_execute_tool_call",
            "input_sent": False,
        }
    if name in known_tool_names() or name.startswith(("desktop_", "agent_desktop")):
        return None
    sample = ", ".join(sorted(known_tool_names())[:6])
    return {
        "status": "error",
        "verdict_code": "UNKNOWN_TOOL",
        "tool": name,
        "detail": f"未知工具名 '{name}'；可用工具示例：{sample} ...（共 {len(known_tool_names())} 个）",
        "channel": "repo_execute_tool_call",
        "input_sent": False,
    }


def execute_tool_call(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """对外唯一入口：Schema 闸门 + 有界等待 + arg_remap 回显。

    返回体带统一信封 ``status`` / ``data`` / ``execution_time_ms``，同时保留
    历史扁平业务字段（``is_valid`` / ``variables`` / ...），因此 REST、MCP、
    SDK、CLI 四种通道拿到的是同一套可解析结构，老调用方也不需要改。
    """
    diag: Dict[str, Any] = {}
    safe_args = dict(arguments or {})
    t0 = time.perf_counter()
    result = _invoke_with_budget(
        lambda: _execute_tool_call_impl(tool_name, safe_args, diag), tool_name
    )
    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 3)

    if not isinstance(result, dict):
        result = {"status": "ok", "result": result}
    if diag.get("arg_remap"):
        result.setdefault("arg_remap", diag["arg_remap"])

    # 部分工具（如 cadcam_preflight）直接回传 orchestrator 的业务字典，没有
    # status 字段。信封层在这里补齐，保证 5 种接入通道拿到的结构一致；
    # 判定不做美化：只有显式带 error 才算失败。
    if not result.get("status"):
        result["status"] = "error" if result.get("error") else "success"
    result.setdefault("execution_time_ms", elapsed_ms)
    if "data" not in result:
        result["data"] = {
            k: v for k, v in result.items() if k not in _ENVELOPE_KEYS
        }
    return result


def _execute_tool_call_impl(tool_name: str, arguments: Dict[str, Any],
                           _diag: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Execute LLM Tool Call and return JSON serializable result payload.

    Supports both canonical 'cadcam_*' tools and legacy 'vendor.action' tools from training corpora.

    """

    args = arguments or {}

    # Compatibility layer A（审计 §4-6）：语料工具名 → 运行时工具面。
    # 60 个 vendor.action 名字由 virtu_omni.knowledge.corpus_tool_map 统一裁决：
    # 有真实实现的翻译成规范工具；没有实现的一律 knowledge_only，不再落到
    # 「Unknown tool name」这种无法诊断的兜底分支。
    from virtu_omni.knowledge.corpus_tool_map import (
        KNOWLEDGE_ONLY,
        knowledge_only_payload,
        map_corpus_tool,
    )

    if tool_name in KNOWLEDGE_ONLY:
        return knowledge_only_payload(tool_name)

    _mapped = map_corpus_tool(tool_name, args)
    if _mapped is not None:
        _canonical, _adapted = _mapped
        if _diag is not None:
            _diag["arg_remap"] = {
                "from": tool_name,
                "to": _canonical,
                "arg_keys_in": sorted(str(k) for k in (args or {}).keys()),
                "arg_keys_out": sorted(str(k) for k in (_adapted or {}).keys()),
                "via": "corpus_tool_map",
            }
        tool_name, args = _canonical, _adapted

    # Compatibility layer B: Map legacy training corpora tool names and args to canonical tools

    legacy_aliases = {
        "solidworks.create_parametric_part": (
            "cadcam_solidworks_model",
            {
                "action": "create_parametric_part",
                "part_name": args.get("part_name", "part"),
                "dimensions": args.get("spec", args.get("dimensions", {})),
                "vba_code": args.get("vba_code", ""),
            },
        ),
        "nx.create_nxopen_script": (
            "cadcam_nx_journal",
            {
                "action": "create_parametric_model",
                "part_name": args.get("part_name", "nx_part"),
                "expressions": args.get("spec", args.get("expressions", {})),
                "script_path": args.get("script_path", ""),
            },
        ),
        "autocad.create_autolisp": (
            "cadcam_autocad_draw",
            {
                "action": "send_lisp",
                "code": args.get("code", ""),
                "drawing_name": args.get("drawing_name", "drawing"),
                "entities": args.get("entities", []),
                "script_path": args.get("script_path", ""),
            },
        ),
        "cimco.create_macro_b": (
            "cadcam_cimco_validate",
            {
                "action": "validate_macro",
                "code": args.get("code", args.get("macro_code", "")),
                "nc_file_path": args.get("nc_file_path", ""),
            },
        ),
        "vericut.create_project_config": (
            "cadcam_vericut_simulate",
            {
                "action": "run_simulation",
                "project_path": args.get("project_path", ""),
                "log_path": args.get("log_path", ""),
            },
        ),
        "sscnc.create_setup_guide": (
            "cadcam_sscnc_control",
            {
                "action": "calculate_offsets",
                "tools": args.get("tools", []),
            },
        ),
        "cad.parse_wish_intent": (
            "cadcam_run_full_chain",
            {
                "wish": args.get("wish", args.get("intent", "")),
                "out_root": args.get("out_root"),
                "skip": tuple(args.get("skip", [])),
            },
        ),
        "reverse_step_model": (
            "cadcam_step_reverse",
            {
                "action": args.get("action", "analyze"),
                "step_path": args.get("step_path", args.get("path", "")),
                "out_sldprt_path": args.get(
                    "out_sldprt_path", args.get("output_path", "")
                ),
            },
        ),
        "step_reverse": (
            "cadcam_step_reverse",
            {
                "action": args.get("action", "analyze"),
                "step_path": args.get("step_path", args.get("path", "")),
                "out_sldprt_path": args.get(
                    "out_sldprt_path", args.get("output_path", "")
                ),
            },
        ),
        "cadcam_reverse_engineering": (
            "cadcam_step_reverse",
            {
                "action": args.get("action", "analyze"),
                "step_path": args.get("step_path", args.get("path", "")),
                "out_sldprt_path": args.get(
                    "out_sldprt_path", args.get("output_path", "")
                ),
            },
        ),
        "desktop.capture_screen": (
            "cadcam_desktop_gui",
            {
                "action": "capture",
                "output_path": args.get(
                    "output_path", os.path.join(_ROOT, "scratch", "gui_capture.png")
                ),
                "software": args.get("window_title") or args.get("software"),
            },
        ),
        "desktop.click_element": (
            "cadcam_desktop_gui",
            {
                "action": "click",
                "x": args.get("x", 0),
                "y": args.get("y", 0),
                "button": args.get("button", "left"),
                "double": bool(args.get("clicks", 1) == 2 or args.get("double", False)),
            },
        ),
        "desktop.type_text": (
            "cadcam_desktop_gui",
            {
                "action": "type_text",
                "text": args.get("text", ""),
            },
        ),
        "desktop.press_hotkey": (
            "cadcam_desktop_gui",
            {
                "action": "hotkey",
                "keys": ",".join(args.get("keys", []))
                if isinstance(args.get("keys"), list)
                else args.get("keys", ""),
            },
        ),
        "desktop.focus_software": (
            "cadcam_desktop_gui",
            {
                "action": "focus",
                "software": args.get("software_name") or args.get("software", ""),
            },
        ),
        "cad.model_parametric_feature_part": (
            "cadcam_solidworks_model",
            {
                "action": "create_parametric_part",
                "part_name": args.get("part_name", "part"),
                "dimensions": args.get("dimensions", {}),
                "vba_code": args.get("vba_code", ""),
            },
        ),
        "cad.generate_engineering_drawing_annotation": (
            "cadcam_solidworks_model",
            {
                "action": "annotate_drawing",
                "annotation": args.get("annotation", {}),
                "part_name": args.get("part_name", "part"),
            },
        ),
        "cad.execute_solidworks_macro": (
            "cadcam_solidworks_model",
            {
                "action": "execute_vba",
                "vba_code": args.get("vba_code") or args.get("code", ""),
            },
        ),
        "cad.one_sentence_parametric_engine": (
            "cadcam_universal_geometry",
            {
                "wish": args.get("wish") or args.get("prompt", ""),
                "part_type": args.get("part_type", "auto"),
                "output_dir": args.get("output_dir"),
            },
        ),
        "assembly_build": (
            "cadcam_assembly_build",
            {
                "action": args.get("action", "full"),
                "step_path": args.get("step_path", ""),
                "out_dir": args.get("out_dir", ""),
            },
        ),
        "cad.assembly_build": (
            "cadcam_assembly_build",
            {
                "action": args.get("action", "full"),
                "step_path": args.get("step_path", ""),
                "out_dir": args.get("out_dir", ""),
            },
        ),
    }

    if tool_name in legacy_aliases:
        original_name = tool_name
        canonical_name, adapted_args = legacy_aliases[tool_name]

        # 审计 §4.3：别名映射不再"静默重组参数"，把重映射事实与键集合记进返回体
        if _diag is not None:
            _diag["arg_remap"] = {
                "from": original_name,
                "to": canonical_name,
                "arg_keys_in": sorted(str(k) for k in (args or {}).keys()),
                "arg_keys_out": sorted(str(k) for k in (adapted_args or {}).keys()),
            }

        tool_name = canonical_name

        args = adapted_args

    # -1. 工具存在性门（最先）：拼错的名字必须报 UNKNOWN_TOOL，不能拖到审批门
    #     再返回 TOOL_APPROVAL_REQUIRED —— 那会把「没有这个工具」误诊成「授权即可」。
    unknown_block = unknown_tool_gate(tool_name, args)
    if unknown_block is not None:
        return unknown_block

    # 0. 参数 Schema 闸门（审计 §4.2 / 增强项 3）：required/enum/type 不通过直接拒绝，
    #    禁止像旧实现那样靠 args.get(..., 默认值) 把非法入参静默降级后继续执行。
    schema_block = schema_gate(tool_name, args)
    if schema_block is not None:
        return schema_block

    # 0-a. 入参体积上限（V-08）：先卡体积，再谈授权，避免超大 payload 进内存
    size_block = payload_size_gate(tool_name, args)
    if size_block is not None:
        return size_block

    # 1. 桌面输入闸门排在最前：被拒绝的调用不得构造任何 bridge（零副作用拦截）
    if tool_name == "cadcam_desktop_gui":
        from bridges.desktop_gate import gate

        blocked = gate(tool_name, args)

        if blocked is not None:
            return blocked

    # 0-c. 安全类门必须先于审批门：越界路径 / 代码注入属于攻击，不能被"待审批"掩盖成放行前的等待
    traversal_block = path_traversal_gate(tool_name, args)
    if traversal_block is not None:
        return traversal_block

    security_block = security_audit_gate(tool_name, args)
    if security_block is not None:
        return security_block

    # 0-b. 风险分级 + 审批（V-05）：写盘/驱动 CAD/执行代码类工具默认需要显式授权。
    #    闸门必须在任何 bridge 构造之前判定，保证被拒绝的调用零副作用。
    approval_block = approval_gate(tool_name, args)
    if approval_block is not None:
        return approval_block

    # 2. 路径穿越防护：确保所有路径参数严格位于工作区内

    # 2. 路径穿越防护（二次校验；主拦截已前移到审批门之前，见 path_traversal_gate）
    traversal_block = path_traversal_gate(tool_name, args)
    if traversal_block is not None:
        return traversal_block

    # 3. 参数安全与代码注入审计已前移到审批门之前（见 security_audit_gate），此处直接派发

    orch = get_orchestrator()

    if tool_name == "ontology.lookup_plugin":
        from virtu_omni.knowledge.software_plugin_ontology import SOFTWARE_ONTOLOGY

        sw = args.get("software", "all")

        if sw in SOFTWARE_ONTOLOGY:
            return {"status": "ok", "software": sw, "ontology": SOFTWARE_ONTOLOGY[sw]}

        return {"status": "ok", "all_software": list(SOFTWARE_ONTOLOGY.keys())}

    if tool_name == "cadcam_preflight":
        return orch.preflight()

    elif tool_name == "cadcam_feature_ops":
        from bridges.feature_ops import feature_ops as _fops
        return _fops(
            action=args.get("action", "measure"),
            plan=args.get("plan"),
            step_path=args.get("step_path", ""),
            out_dir=args.get("out_dir", ""),
            workspace_root=_ROOT,
        )
    elif tool_name == "cadcam_assembly_build":
        if args.get("action", "full") in ("understand", "build_mated", "full_mated"):
            from bridges.assembly_pipeline import run_pipeline as _run_pipeline

            action = args.get("action", "full_mated")
            if action == "understand":
                from bridges.step_mates import face_inventory, infer_mates
                from bridges.step_bom import StepBOM

                sp = args.get("step_path") or os.path.join(_ROOT, "assets", "wheel_mold_P0.step")
                bom = StepBOM(sp)
                inv = face_inventory(sp)
                mates = infer_mates(inv)
                return {"status": "ok", "tool": "cadcam_assembly_build",
                        "action": "understand", "bom": bom.to_dict(),
                        "dsl": bom.to_dsl(),
                        "mate_candidates": mates["mates"],
                        "isolated_parts": mates["isolated_parts"]}
            res = _run_pipeline(
                step_path=args.get("step_path") or os.path.join(_ROOT, "assets", "wheel_mold_P0.step"),
                out_dir=args.get("out_dir", ""),
                with_drawing=(action == "full_mated"),
                workspace_root=_ROOT,
            )
            return res
        from bridges.assembly_build import build as _build_asm

        return _build_asm(
            step_path=args.get("step_path", ""),
            out_dir=args.get("out_dir", ""),
            action=args.get("action", "full"),
            workspace_root=_ROOT,
        )
    elif tool_name == "cadcam_step_reverse":
        act = args.get("action", "analyze")
        step_p = args.get("step_path") or args.get("file_path") or args.get("path", "")
        out_sldprt = args.get("out_sldprt_path") or args.get("output_path")
        if act in ("reconstruct_solidworks", "full"):
            return orch.step_reverse(
                step_path=step_p,
                action=act,
                out_sldprt_path=out_sldprt,
            )
        from bridges.step_reverse import reverse_step

        return reverse_step(
            step_path=step_p,
            action=act,
            workspace_root=_ROOT,
            max_bodies=int(args.get("max_bodies", 6)),
            name_contains=args.get("name_contains", ""),
            detail=bool(args.get("detail", False)),
        )

    elif tool_name == "cadcam_solidworks_model":
        action = args.get("action", "create_parametric_part")

        params = {
            "part_name": args.get("part_name", "part"),
            "dimensions": args.get("dimensions", {}),
            "code": args.get("vba_code", ""),
            # annotate_drawing 需要真实模型路径与产物目录；缺失时由桥层明确拒绝，
            # 不允许再靠 part_name 子串猜动作（审计发现的实际缺陷）。
            "model_path": args.get("model_path", args.get("out_path", "")),
            "out_dir": args.get("out_dir", ""),
            "annotation": args.get("annotation", {}),
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
            dialect=args.get("dialect", "fanuc"),
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
            return ctl.click(
                int(args["x"]),
                int(args["y"]),
                button=args.get("button", "left"),
                double=bool(args.get("double", False)),
            )

        elif act == "move":
            return ctl.move(int(args.get("x", 0)), int(args.get("y", 0)))

        elif act == "drag":
            sx = int(args.get("start_x", args.get("x", 0)))
            sy = int(args.get("start_y", args.get("y", 0)))
            ex = int(args.get("end_x", sx))
            ey = int(args.get("end_y", sy))
            btn = args.get("button", "left")
            return ctl.drag(sx, sy, ex, ey, button=btn)

        elif act == "scroll":
            clicks = int(args.get("clicks", 1))
            x = args.get("x")
            y = args.get("y")
            return ctl.scroll(clicks, int(x) if x is not None else None, int(y) if y is not None else None)

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

        # 收敛到单一分派入口，避免工具面与 bridge 方法各自漂移（审计 §4-3/§4-4）
        return vb.analyze_inspection(task, img_path)

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
            solver=args.get("solver", "analytic"),
        )

    elif tool_name == "cadcam_sheetmetal_nest":
        return orch.sheetmetal_nest(
            parts=args.get("parts", []),
            sheet_width=float(args.get("sheet_width", 1000.0)),
            sheet_height=float(args.get("sheet_height", 1000.0)),
            margin=float(args.get("margin", 5.0)),
            output_dxf=args.get("output_dxf"),
        )

    elif tool_name == "cad.infer_blueprint_feature_tree":
        from virtu_omni.agent.blueprint_inverse_engine import BlueprintInverseEngine

        bie = BlueprintInverseEngine()
        spec = {
            "drawing_name": args.get("drawing_name", "drawing"),
            "dimensions": args.get("dimensions", {}),
            "geometry_type": args.get("geometry_type", "revolving_shaft_sleeve"),
        }
        res = bie.infer_blueprint_features(spec)
        return {"status": "ok", "feature_tree": res}

    elif tool_name == "cad.assemble_components_with_mates":
        return {
            "status": "ok",
            "assembly_name": args.get("assembly_name", "assembly.SLDASM"),
            "mates_applied": len(args.get("mates", [])),
            "mates": args.get("mates", []),
        }

    elif tool_name == "agent.verify_and_self_optimize":
        from virtu_omni.agent.self_reflection_optimizer import SelfReflectionOptimizer

        optimizer = SelfReflectionOptimizer()
        code = args.get("code", "")
        lang = args.get("language", "solidworks")
        audit = optimizer.audit_code(code, lang)
        if not audit.get("passed"):
            opt_code, refl = optimizer.reflect_and_optimize(code, audit)
            return {
                "status": "optimized",
                "audit": audit,
                "optimized_code": opt_code,
                "reflection": refl,
            }
        return {"status": "ok", "audit": audit, "code": code}

    elif tool_name == "skill.synthesize_agent_skill":
        from virtu_omni.agent.skill_writer_and_memory import SkillWriterAndMemory

        writer = SkillWriterAndMemory()
        res = writer.synthesize_skill(
            skill_name=args.get("skill_name", "new_skill"),
            description=args.get("description", ""),
            # synthesize_skill() signature is instructions_md / scripts; the
            # former keywords raised TypeError on every invocation.
            instructions_md=args.get("instructions_md", args.get("instructions_markdown", "")),
            scripts=args.get("scripts", args.get("bundled_scripts", {})) or None,
        )
        if not res:
            return {"status": "error", "reason": "synthesize_skill 未返回产物路径"}
        return {"status": "ok", "skill_registered": res}

    elif tool_name == "memory.commit_long_term_experience":
        from virtu_omni.memory import VirtuHindsightMemory, MemoryType

        mem = VirtuHindsightMemory()
        # 原 commit_experience(...) 在 VirtuHindsightMemory 上并不存在，且
        # MemoryType.EPISODIC 也非合法常量 → 该路径必然 AttributeError。
        # 改为调用真实 retain API：4 个字段拼成 content，其余落 metadata，
        # 并返回 retain 的真实状态/id（禁止静默成功）。
        content = "\n".join(
            part for part in (
                args.get("task_signature", "task"),
                args.get("problem_summary", ""),
                args.get("solution_strategy", ""),
                " ".join(args.get("key_rules_learned") or []),
            ) if part
        )
        outcome = mem.retain(
            bank_id="default",
            content=content,
            context="learnings",
            memory_type=MemoryType.AGENT_EXPERIENCES,
            metadata={
                "task_signature": args.get("task_signature", "task"),
                "problem_summary": args.get("problem_summary", ""),
                "solution_strategy": args.get("solution_strategy", ""),
                "key_rules_learned": args.get("key_rules_learned") or [],
            },
        )
        return {"status": outcome.get("status", "ok"), "experience_id": outcome.get("id")}

    elif tool_name in ("web.search_technical_knowledge", "cadcam_knowledge_lookup"):
        from virtu_omni.knowledge.software_plugin_ontology import (
            SOFTWARE_ONTOLOGY,
            resolve_software,
        )

        query = str(args.get("query", "")).strip().lower()
        only = resolve_software(args.get("software", "")) if args.get("software") else None
        tokens = [t for t in query.replace("，", " ").replace(",", " ").split() if t]
        matched = {}
        for sw, info in SOFTWARE_ONTOLOGY.items():
            if only and sw != only:
                continue
            haystack = (sw + " " + json.dumps(info, ensure_ascii=False)).lower()
            if not tokens or any(q in haystack for q in tokens):
                matched[sw] = info
        return {
            "status": "ok" if matched else "not_found",
            "query": query,
            "software": only or args.get("software") or "all",
            "count": len(matched),
            "results": matched,
        }

    elif tool_name == "cad.infer_equipment_intent":
        from virtu_omni.agent.agent_team import ChiefArchitectAgent

        arch = ChiefArchitectAgent()
        prompt = args.get("equipment_type", "") + " " + args.get("target_product", "")
        spec = arch.run({"user_prompt": prompt})
        return {"status": "ok", "architecture_spec": spec}

    elif tool_name == "cad.decompose_automation_assembly":
        return {
            "status": "ok",
            "assembly_name": args.get("assembly_name", ""),
            "sub_modules": args.get("sub_modules", []),
            "module_count": len(args.get("sub_modules", [])),
        }

    elif tool_name == "cad.query_standard_parts_library":
        # 审计 §4-2 修复：旧实现写死 SOFTWARE_ONTOLOGY.get("SolidWorks_2021")
        # 且读不存在的 "standard_features" 字段，导致该工具恒返回空列表。
        # 现改为：优先查确定性标准件库 → 查不到/数据源缺失时回落本体目录，
        # 并把「数据源、是否降级、降级原因」全部显式回显，不再用空列表冒充成功。
        from virtu_omni.knowledge.software_plugin_ontology import (
            SOFTWARE_ONTOLOGY,
            resolve_software,
            standard_libraries,
        )

        software_arg = str(
            args.get("software") or args.get("software_name") or ""
        ).strip()
        category = str(args.get("category") or "all").strip()
        keyword = str(
            args.get("keyword")
            or args.get("standard_code")
            or args.get("query_part")
            or ""
        ).strip()
        try:
            limit = int(args.get("limit", 10) or 10)
        except (TypeError, ValueError):
            limit = 10

        db_items: List[Dict[str, Any]] = []
        db_error: Optional[str] = None
        try:
            from virtu_omni.knowledge.industrial_toolbox import IndustrialToolbox

            rows = IndustrialToolbox.get_instance().query_standard_part(
                keyword,
                None if category.lower() in ("", "all") else category,
                limit,
            )
            for row in rows or []:
                if isinstance(row, dict) and row.get("error"):
                    db_error = str(row["error"])
                elif isinstance(row, dict):
                    db_items.append(row)
        except Exception as exc:  # 数据源不可用不得导致工具崩溃
            db_error = f"{type(exc).__name__}: {exc}"

        resolved = resolve_software(software_arg) if software_arg else None
        catalog = standard_libraries(resolved or None)
        if category.lower() not in ("", "all"):
            needle = category.lower()
            catalog = [
                lib
                for lib in catalog
                if needle in lib["library"].lower()
                or any(needle in item.lower() for item in lib["items"])
            ] or catalog
        if keyword:
            needle = keyword.lower()
            narrowed = []
            for lib in catalog:
                hits = [i for i in lib["items"] if needle in i.lower()]
                if hits or needle in lib["library"].lower():
                    narrowed.append(dict(lib, items=hits or lib["items"]))
            catalog = narrowed

        catalog_items = [item for lib in catalog for item in lib["items"]]
        payload = db_items or catalog_items

        return {
            "status": "ok" if payload else "not_found",
            "software": resolved or software_arg or "all",
            "software_known": bool(resolved) or not software_arg,
            "category": category,
            "keyword": keyword,
            "data_source": (
                "standard_parts_taxonomy"
                if db_items
                else ("software_ontology" if catalog_items else None)
            ),
            "degraded": bool(db_error),
            "data_error": db_error,
            "standard_terms": {
                sw: sorted(
                    (SOFTWARE_ONTOLOGY.get(sw, {}).get("plugins_and_addins") or {}).keys()
                )
                for sw in ([resolved] if resolved else list(SOFTWARE_ONTOLOGY))
            },
            "libraries": catalog[:limit],
            # 兼容旧字段名（历史调用方/语料按 standard_parts 取值）
            "standard_parts": payload[:limit],
            "count": len(payload),
        }

    elif tool_name == "software.dispatch_industrial_tool":
        sw = args.get("software", "")
        act = args.get("action", "")
        params = args.get("parameters") or args.get("params") or {}
        return orch.dispatch(sw, act, params)

    # 3. 互联网安全检索与持续深度学习工具
    # 契约一致性（2026-11-13 复查）：其余工具统一回 status，这三支此前直出裸 payload，
    # 调用方 res.get("status") 恒为 None，无法区分成功/失败。此处补 status，
    # 保留原有全部字段（不破坏既有断言），error 非空即 error。
    elif tool_name in ("cadcam_web_search", "web_search"):
        from virtu_omni.internet import get_internet_hub
        hub = get_internet_hub()
        res = hub.web_search_tool(
            query=args.get("query", ""),
            num_results=int(args.get("num_results", 4)),
        )
        if isinstance(res, dict):
            res.setdefault("status", "error" if res.get("error") else "ok")
        return res

    elif tool_name in ("cadcam_fetch_web_content", "fetch_web_content"):
        from virtu_omni.internet import get_internet_hub
        hub = get_internet_hub()
        res = hub.fetch_web_content_tool(
            url=args.get("url", ""),
            max_chars=int(args.get("max_chars", 3000)),
        )
        if isinstance(res, dict):
            res.setdefault(
                "status",
                "error" if (res.get("error") or res.get("success") is False) else "ok",
            )
        return res

    elif tool_name in ("cadcam_internet_deep_learning", "internet_deep_learning"):
        from virtu_omni.internet import get_internet_hub
        hub = get_internet_hub()
        res = hub.deep_learning_tool(
            topic=args.get("topic", ""),
            content=args.get("content", ""),
            source_url=args.get("source_url", ""),
        )
        if isinstance(res, dict):
            res.setdefault(
                "status",
                "error" if (res.get("error") or res.get("success") is False) else "ok",
            )
        return res

    # 4. agent-desktop 原生桌面自动化与无障碍语义树工具
    elif tool_name.startswith("desktop_") or tool_name.startswith("agent_desktop_") or tool_name == "agent_desktop":
        from bridges.agent_desktop_bridge import AgentDesktopBridge
        bridge = AgentDesktopBridge()
        return bridge.execute_tool(tool_name, args)

    return {"status": "error", "message": f"Unknown tool name: {tool_name}"}


if __name__ == "__main__":
    tools = get_cadcam_tool_definitions()

    print(f"Tool Calling Specs Defined: {len(tools)} tools available.")

    test_call = execute_tool_call(
        "cadcam_cimco_validate",
        {"action": "validate_macro", "code": "G00 X100.0 Z50.0\n#500=1\nM30"},
    )

    print("Test Execution Result:", test_call)
