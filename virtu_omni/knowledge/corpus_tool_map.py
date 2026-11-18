# -*- coding: utf-8 -*-
"""corpus_tool_map.py — 训练语料工具名 → 运行时工具面的唯一映射真源。

审计 §4-6 记录的问题：六软件语料用了 60 个 ``vendor.action`` 形式的工具名，
而运行时只暴露 33 个规范工具（六软件各 1 个 ``cadcam_*`` + 通用链/视觉/桌面），
此前只有 8 个语料名有别名，其余 52 个直接落到 ``Unknown tool name``。

本模块把 60 个名字逐一分类，只有两类结果：

* **EXECUTABLE**：存在语义对应的真实运行时工具，给出规范工具名与 action，
  参数由 ``adapt_arguments`` 从语料参数翻译过去；
* **KNOWLEDGE_ONLY**：当前没有任何运行时实现（GUI 专属、插件专属、或能力
  根本不在本仓库）。调用时返回结构化的 ``knowledge_only``，附上替代工具与
  原因，绝不伪造成功。

约束：本表只允许指向真实存在于 ``TOOL_SPECS``/dispatch 分支的工具。
``scripts/lint_corpus_tool_names.py`` 会用 `coverage()` 校验这一点。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# 1. 可执行映射：语料名 -> (规范工具, 规范 action)
# ---------------------------------------------------------------------------
EXECUTABLE: Dict[str, Tuple[str, str]] = {
    # ---- SOLIDWORKS 2021 ----
    "solidworks.create_parametric_part": ("cadcam_solidworks_model", "create_parametric_part"),
    "solidworks.create_drawing": ("cadcam_solidworks_model", "annotate_drawing"),
    "solidworks.run_macro": ("cadcam_solidworks_model", "execute_vba"),
    "solidworks.mass_properties_check": ("cadcam_solidworks_model", "mass_properties"),
    "solidworks.simulation_static_study": ("cadcam_cae_stress_analysis", ""),
    # ---- Siemens NX 12.0 ----
    "nx.create_nxopen_script": ("cadcam_nx_journal", "create_parametric_model"),
    "nx.run_journal_headless": ("cadcam_nx_journal", "run_journal"),
    # ---- AutoCAD 2026 ----
    "autocad.create_dxf": ("cadcam_autocad_draw", "create_dxf"),
    "autocad.draw_geometry": ("cadcam_autocad_draw", "create_dxf"),
    "autocad.setup_layers": ("cadcam_autocad_draw", "create_dxf"),
    "autocad.add_text": ("cadcam_autocad_draw", "create_dxf"),
    "autocad.add_dimension": ("cadcam_autocad_draw", "create_dxf"),
    "autocad.ezdxf_batch": ("cadcam_autocad_draw", "create_dxf"),
    "autocad.send_lisp": ("cadcam_autocad_draw", "send_lisp"),
    "autocad.accoreconsole_headless": ("cadcam_autocad_draw", "run_headless_script"),
    # ---- CIMCO Edit 2026 ----
    # create_macro_b 不在此处：桥层只有 validate_macro / launch，能校不能写，
    # 归入 KNOWLEDGE_ONLY（宏代码须由模型自己产出，工具只做校验）。
    "cimco.cycle_macro_validate": ("cadcam_cimco_validate", "validate_macro"),
    # ---- VERICUT 9.6 ----
    "vericut.parse_sim_log": ("cadcam_vericut_simulate", "check_collision"),
    "vericut.autodiff_check": ("cadcam_visual_inspect", "autodiff_inspection"),
    # ---- 斯沃 SSCNC 7.2 ----
    "sscnc.launch_simulator": ("cadcam_sscnc_control", "launch"),
    "sscnc.panel_set_mode": ("cadcam_sscnc_control", "press_panel_key"),
    "sscnc.panel_cycle_start": ("cadcam_sscnc_control", "press_panel_key"),
    "sscnc.tool_offset_define": ("cadcam_sscnc_control", "calculate_offsets"),
    "sscnc.tool_offset_calculate": ("cadcam_sscnc_control", "calculate_offsets"),
    "sscnc.crt_readout_check": ("cadcam_visual_inspect", "cnc_screen_perception"),
    # ---- 通用 ----
    "knowledge.lookup_module": ("web.search_technical_knowledge", ""),
    "cad.parse_wish_intent": ("cadcam_run_full_chain", ""),
}

#: action 为空表示该工具没有 action 维度，翻译时直接透传业务参数
ACTIONLESS_TOOLS = frozenset({
    "cadcam_cae_stress_analysis",
    "cadcam_sheetmetal_nest",
    "cadcam_universal_geometry",
    "web.search_technical_knowledge",
    "cadcam_run_full_chain",
})

#: 不写进对模型宣告面、但 execute_tool_call 可正常分派的内部入口。
#: 依据 virtu_eval/tool_schema.py：宣告面固定 16 项且每项必须有可判分用例，
#: 未补 holdout 用例前不得扩充宣告面，否则能力分无法归因。
DISPATCH_ONLY_TOOLS = frozenset({
    "web.search_technical_knowledge",
    "cadcam_knowledge_lookup",
    "cad.query_standard_parts_library",
})

# ---------------------------------------------------------------------------
# 2. 仅知识条目：没有运行时实现，调用即如实拒绝
# ---------------------------------------------------------------------------
KNOWLEDGE_ONLY: Dict[str, Dict[str, Any]] = {
    # SOLIDWORKS
    "solidworks.toolbox_insert_part": {
        "detail": "Toolbox 标准件插入需要 SOLIDWORKS 内部 Toolbox 插件交互，本仓库未实现（无 COM 装配调用）",
        "suggested_tools": ["cad.query_standard_parts_library"],
    },
    "solidworks.hole_wizard": {
        "detail": "异型孔向导（Hole Wizard）无 COM 落地实现；可用 feature_ops 的 cut 计划替代",
        "suggested_tools": ["cadcam_feature_ops"],
    },
    "solidworks.fillet_chamfer": {
        "detail": "圆角/倒角未封装为运行时工具（SolidWorks API 有 FeatureFillet3，但桥层未提供）",
        "suggested_tools": ["cadcam_solidworks_model"],
    },
    "solidworks.export_step": {
        "detail": "SOLIDWORKS 导出 STEP 未封装；反向链路（STEP→SLDPRT）可用 cadcam_step_reverse",
        "suggested_tools": ["cadcam_step_reverse"],
    },
    "solidworks.visualize_render": {
        "detail": "SOLIDWORKS Visualize 为独立渲染器，本仓库无接口",
        "suggested_tools": ["cadcam_visual_inspect"],
    },
    "solidworks.pcb_viewer_open": {
        "detail": "PCB Viewer 属 SOLIDWORKS PCB 插件，未安装且无自动化接口",
        "suggested_tools": [],
    },
    "solidworks.inspection_export": {
        "detail": "Inspection 尺寸报告导出未实现",
        "suggested_tools": ["cadcam_solidworks_model"],
    },
    "solidworks.cam_generate_toolpath": {
        "detail": "SOLIDWORKS CAM 刀路生成需要 CAMWorks 插件授权，本机未验证可用",
        "suggested_tools": ["cadcam_extreme_chain"],
    },
    # Siemens NX
    "nx.postbuilder_configure": {
        "detail": "NX Post Builder 为 GUI 工具，无 NXOpen 批处理入口",
        "suggested_tools": ["cadcam_nx_journal"],
    },
    "nx.cam_template_load": {
        "detail": "CAM 模板加载未通过 NXOpen 实现",
        "suggested_tools": ["cadcam_nx_journal"],
    },
    "nx.menu_customize": {
        "detail": "NX 菜单/UI 定制属交互配置，无运行时意义",
        "suggested_tools": [],
    },
    "nx.gc_toolkit_invoke": {
        "detail": "GRIP/GC Toolkit 需要编译期工具链，未接入",
        "suggested_tools": ["cadcam_nx_journal"],
    },
    "nx.block_ui_styler": {
        "detail": "Block UI Styler 为 UI 设计器，无运行时执行路径",
        "suggested_tools": [],
    },
    "nx.export_step": {
        "detail": "NX 导出 STEP 未封装（autocad 侧无对应；STEP 反向链路见 cadcam_step_reverse）",
        "suggested_tools": ["cadcam_step_reverse"],
    },
    # AutoCAD
    "autocad.express_tools_run": {
        "detail": "Express Tools 为交互命令集，无 headless 稳定入口",
        "suggested_tools": ["cadcam_autocad_draw"],
    },
    "autocad.dynamic_block_make": {
        "detail": "动态块构造未封装（ezdxf 不支持动态块参数）",
        "suggested_tools": ["cadcam_autocad_draw"],
    },
    "autocad.plot": {
        "detail": "打印/出图未封装（accoreconsole 出图需 .pc3 配置）",
        "suggested_tools": ["cadcam_autocad_draw"],
    },
    "autocad.arx_load": {
        "detail": "ARX 加载属原生扩展，无安全自动化通道",
        "suggested_tools": [],
    },
    "autocad.cuix_customize": {
        "detail": "CUIx 界面定制为交互配置",
        "suggested_tools": [],
    },
    # CIMCO Edit
    "cimco.create_macro_b": {
        "detail": "宏程序只能由模型自行编写；CIMCO 桥仅提供 validate_macro（校验）/ launch（启动），无生成能力，不得假装已代写",
        "suggested_tools": ["cadcam_cimco_validate"],
    },
    "cimco.dnc_template_configure": {
        "detail": "DNC 模板配置未实现（CIMCO 无公开自动化接口）",
        "suggested_tools": ["cadcam_cimco_validate"],
    },
    "cimco.postprocess_js": {
        "detail": "CIMCO 后处理器 JS 运行未接入",
        "suggested_tools": ["cadcam_cimco_validate"],
    },
    "cimco.backplot_verify": {
        "detail": "3D 实体仿真回放依赖 GUI；当前只能做 G00 下扎静态校验",
        "suggested_tools": ["cadcam_cimco_validate"],
    },
    "cimco.machine_type_load": {
        "detail": "机床类型加载为 GUI 操作",
        "suggested_tools": ["cadcam_cimco_validate"],
    },
    "cimco.tool_library_load": {
        "detail": "刀具库加载为 GUI 操作",
        "suggested_tools": ["cadcam_cimco_validate"],
    },
    "cimco.converter_translate": {
        "detail": "CIMCO Converter 批量翻译未封装",
        "suggested_tools": ["cadcam_cimco_validate"],
    },
    # VERICUT
    "vericut.launch_project": {
        "detail": "VERICUT 9.6 无 COM/IPC/批处理接口，只能走 GUI 通道 work/vericut-toolchain/vericut_link.py",
        "suggested_tools": ["cadcam_vericut_simulate"],
    },
    "vericut.play_simulation": {
        "detail": "仿真播放必须 GUI 驱动（vericut_link.play_simulation），非工具化能力",
        "suggested_tools": ["cadcam_vericut_simulate"],
    },
    "vericut.read_vcreview": {
        "detail": "VERICUT Review 报告读取未封装",
        "suggested_tools": ["cadcam_vericut_simulate"],
    },
    "vericut.toolman_define_tool": {
        "detail": "Tool Manager 建刀为 GUI 操作",
        "suggested_tools": ["cadcam_vericut_simulate"],
    },
    "vericut.optipath_config": {
        "detail": "OptiPath 优化配置未实现",
        "suggested_tools": ["cadcam_vericut_simulate"],
    },
    "vericut.converter_run": {
        "detail": "VERICUT Converter 未封装",
        "suggested_tools": ["cadcam_step_reverse"],
    },
    "vericut.create_project_config": {
        "detail": "工程配置依赖 GUI 向导；无头批处理在 9.6 上会空退出。"
                  "（此条同时覆盖旧的 legacy 别名：旧映射会把它当成 run_simulation，"
                  "属于误导性成功，这里改为如实拒绝）",
        "suggested_tools": ["cadcam_vericut_simulate"],
    },
    # SSCNC
    "sscnc.wcs_g54_setup": {
        "detail": "G54 写入需要面板/系统交互，本机自绘面板不可寻址",
        "suggested_tools": ["cadcam_sscnc_control"],
    },
    "sscnc.program_load": {
        "detail": "程序载入需 EDIT 模式 + 面板输入，自绘面板无法寻址",
        "suggested_tools": ["cadcam_sscnc_control"],
    },
}

#: 训练语料里实际出现过的全部工具名（用于 lint 覆盖率校验）
CORPUS_TOOL_NAMES: Tuple[str, ...] = tuple(sorted(set(EXECUTABLE) | set(KNOWLEDGE_ONLY)))


# ---------------------------------------------------------------------------
# 3. 参数翻译
# ---------------------------------------------------------------------------
def _first(args: Dict[str, Any], *keys: str, default: Any = "") -> Any:
    for k in keys:
        v = args.get(k)
        if v not in (None, "", [], {}):
            return v
    return default


def adapt_arguments(tool: str, action: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """把语料参数翻译成规范工具的参数。缺失必需参数时保持空值，由工具自身如实报错。"""
    a = args or {}

    if tool == "cadcam_solidworks_model":
        out = {
            "action": action,
            "part_name": _first(a, "part_name", "name", "part", default="part"),
            "dimensions": _first(a, "dimensions", "spec", "parameters", "params", default={}),
            "vba_code": _first(a, "vba_code", "code", "macro", "macro_code", default=""),
        }
        if action == "annotate_drawing":
            out["annotation"] = _first(a, "annotation", "annotations", default={})
        return out

    if tool == "cadcam_nx_journal":
        return {
            "action": action,
            "part_name": _first(a, "part_name", "name", default="nx_part"),
            "expressions": _first(a, "expressions", "spec", "parameters", default={}),
            "script_path": _first(a, "script_path", "journal_path", "path", default=""),
        }

    if tool == "cadcam_autocad_draw":
        return {
            "action": action,
            "code": _first(a, "code", "lisp", "script", default=""),
            "drawing_name": _first(a, "drawing_name", "name", default="drawing"),
            "entities": _first(a, "entities", "geometry", default=[]),
            "script_path": _first(a, "script_path", "script", "path", default=""),
        }

    if tool == "cadcam_cimco_validate":
        return {
            "action": action,
            "code": _first(a, "code", "macro_code", "gcode", "nc_code", default=""),
            "nc_file_path": _first(a, "nc_file_path", "file_path", "path", default=""),
        }

    if tool == "cadcam_vericut_simulate":
        return {
            "action": action,
            "project_path": _first(a, "project_path", "project", "vcproject", default=""),
            "log_path": _first(a, "log_path", "sim_log", "log", default=""),
        }

    if tool == "cadcam_sscnc_control":
        out = {"action": action, "tools": _first(a, "tools", "tool_list", default=[])}
        if action == "press_panel_key":
            out["key_label"] = _first(a, "key_label", "key", "label", "mode", default="")
        return out

    if tool == "cadcam_visual_inspect":
        return {
            "task": action,
            "image_path": _first(a, "image_path", "screenshot", "image", "path", default=""),
        }

    if tool == "cadcam_cae_stress_analysis":
        return {
            "spec": _first(a, "spec", "dimensions", default={}),
            "material": _first(a, "material", default=""),
            "pressure_mpa": a.get("pressure_mpa"),
            "force_n": a.get("force_n"),
            "torque_nm": a.get("torque_nm"),
            "target_fos": a.get("target_fos"),
        }

    if tool == "cadcam_knowledge_lookup":
        return {
            "query": _first(a, "query", "keyword", "module", "topic", default=""),
            "software": _first(a, "software", "software_name", default=""),
        }

    if tool == "web.search_technical_knowledge":
        return {"query": _first(a, "query", "keyword", "module", default="")}

    if tool == "cadcam_run_full_chain":
        return {
            "wish": _first(a, "wish", "intent", "prompt", default=""),
            "out_root": a.get("out_root"),
            "skip": tuple(a.get("skip", []) or []),
        }

    # 兜底：保留未知参数原样，只补 action
    out = dict(a)
    if action:
        out["action"] = action
    return out


# ---------------------------------------------------------------------------
# 4. 对外接口
# ---------------------------------------------------------------------------
def map_corpus_tool(name: str, args: Optional[Dict[str, Any]] = None):
    """返回 (canonical_tool, adapted_args)；不可执行返回 None。"""
    hit = EXECUTABLE.get(name)
    if not hit:
        return None
    tool, action = hit
    return tool, adapt_arguments(tool, action, args or {})


def knowledge_only_payload(name: str) -> Dict[str, Any]:
    """不可执行语料工具的诚实回执。"""
    meta = KNOWLEDGE_ONLY.get(name, {})
    return {
        "status": "knowledge_only",
        "verdict_code": "TOOL_NOT_EXECUTABLE",
        "tool": name,
        "detail": meta.get("detail") or "该工具名只在训练语料中出现，运行时无对应实现",
        "suggested_tools": meta.get("suggested_tools", []),
        "input_sent": False,
        "channel": "repo_execute_tool_call",
    }


def describe(name: str) -> Dict[str, Any]:
    """单条工具名的映射说明（lint/报告用）。"""
    hit = EXECUTABLE.get(name)
    if hit:
        return {"tool": name, "kind": "executable",
                "canonical_tool": hit[0], "canonical_action": hit[1]}
    if name in KNOWLEDGE_ONLY:
        meta = KNOWLEDGE_ONLY[name]
        return {"tool": name, "kind": "knowledge_only",
                "reason": meta.get("detail", ""),
                "suggested_tools": meta.get("suggested_tools", [])}
    return {"tool": name, "kind": "unmapped"}


def coverage(names: Optional[List[str]] = None) -> Dict[str, Any]:
    """覆盖率统计；unmapped 必须为空，否则语料仍会打到 Unknown tool。"""
    pool = names if names is not None else list(CORPUS_TOOL_NAMES)
    rows = [describe(n) for n in pool]
    unmapped = [r["tool"] for r in rows if r["kind"] == "unmapped"]
    return {
        "total": len(rows),
        "executable": sum(1 for r in rows if r["kind"] == "executable"),
        "knowledge_only": sum(1 for r in rows if r["kind"] == "knowledge_only"),
        "unmapped": unmapped,
        "rows": rows,
    }
