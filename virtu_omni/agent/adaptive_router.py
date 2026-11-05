# -*- coding: utf-8 -*-
"""virtu_omni/agent/adaptive_router.py — Access Modality Dispatcher.

设计说明（2026-10-31 变更）
---------------------------
本模块原先实现「Agent 按任务难度自动调用工具」这条规则：
``TaskDifficultyAnalyzer`` 用关键词把任务判成 L1~L5 难度等级，再据此自动挑选
PYTHON_SDK / FUNCTION_CALLING / MCP / CLI / REST_API / DESKTOP_GUI / AGENT_CHAIN。
**该规则已删除**，难度分级与按难度选路的关键词表全部移除。

现行规则：
1. **接入方式由调用方显式指定**（``modality`` 参数）。未指定时统一走标准工具
   调用链 ``FUNCTION_CALLING``（大模型标准结构化 tool_call），不再做任何按难度的推断。
2. 关键词仅用于识别「目标软件」与「操作动作」（工具调用必须有入参），
   不再用于推断难度等级，也不再用于挑选接入方式。
3. 主通道失败时沿**固定容灾链**降级（与任务难度无关），
   降级顺序见 ``MODALITY_FALLBACKS``。
"""

from __future__ import annotations
import os
import sys
import time
import json
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bridges.software_registry import normalize_software_key, SOFTWARE_SPECS
from bridges.toolchain_client import CADCAMToolchainClient
from bridges.six_software_orchestrator import SixSoftwareOrchestrator
from bridges.tool_calling_specs import execute_tool_call, get_cadcam_tool_definitions
from bridges.desktop_controller import DesktopController


# 难度自动选路已停用：报告中的难度字段统一写入该标记值。
DIFFICULTY_ROUTING_DISABLED = "DISABLED"


class AccessModality(str, Enum):
    """接入方式（只表示「怎么调」，与任务难度无关）。"""

    PYTHON_SDK = "PYTHON_SDK"              # 内存级直接调用（超低延迟）
    FUNCTION_CALLING = "FUNCTION_CALLING"  # 大模型标准结构化工具调用
    MCP = "MCP"                            # Model Context Protocol 标准协议
    CLI = "CLI"                            # 子进程命令行沙箱隔离（防假死）
    REST_API = "REST_API"                  # HTTP REST 远程服务
    DESKTOP_GUI = "DESKTOP_GUI"            # 桌面视觉感知与键鼠注入
    AGENT_CHAIN = "AGENT_CHAIN"            # 六阶段多智能体串行流水线


# 固定容灾链：主通道失败后按此顺序降级。静态定义，不依赖任何难度判断。
MODALITY_FALLBACKS: Dict[AccessModality, List[AccessModality]] = {
    AccessModality.FUNCTION_CALLING: [AccessModality.MCP, AccessModality.PYTHON_SDK, AccessModality.CLI],
    AccessModality.MCP:            [AccessModality.FUNCTION_CALLING, AccessModality.PYTHON_SDK, AccessModality.CLI],
    AccessModality.PYTHON_SDK:     [AccessModality.FUNCTION_CALLING, AccessModality.CLI],
    AccessModality.CLI:            [AccessModality.PYTHON_SDK, AccessModality.FUNCTION_CALLING],
    AccessModality.REST_API:       [AccessModality.FUNCTION_CALLING, AccessModality.PYTHON_SDK, AccessModality.CLI],
    AccessModality.DESKTOP_GUI:    [AccessModality.FUNCTION_CALLING, AccessModality.CLI],
    AccessModality.AGENT_CHAIN:    [AccessModality.FUNCTION_CALLING, AccessModality.CLI],
}

# 桌面交互类动作（走 cadcam_desktop_gui 工具）
GUI_ACTIONS = ("capture", "focus", "click", "type_text", "hotkey",
               "inspect_window", "dismiss_dialogs")

# 目标软件 → 标准工具名
SOFTWARE_TOOL: Dict[str, str] = {
    "solidworks": "cadcam_solidworks_model",
    "nx": "cadcam_nx_journal",
    "autocad": "cadcam_autocad_draw",
    "cimco": "cadcam_cimco_validate",
    "vericut": "cadcam_vericut_simulate",
    "sscnc": "cadcam_sscnc_control",
}


@dataclass
class DispatchPlan:
    """一次派发的执行计划（不含任何难度维度）。"""

    modality: AccessModality
    fallback_modalities: List[AccessModality]
    target_software: str
    action: str
    tool_name: str
    rationale: str

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["modality"] = self.modality.value
        d["fallback_modalities"] = [m.value for m in self.fallback_modalities]
        d["difficulty_level"] = DIFFICULTY_ROUTING_DISABLED
        d["complexity_score"] = 0.0
        return d


class TargetDetector:
    """从提示词/入参中识别「目标软件」与「操作动作」。

    注意：本类**不做难度分级**。它只负责补齐工具调用所需的入参，
    不参与、也不影响接入方式的选择。
    """

    SOFTWARE_SCAN_ORDER = ("solidworks", "sscnc", "cimco", "autocad", "vericut", "nx")

    # 动作识别关键词（按顺序匹配，先命中先算）
    ACTION_KEYWORDS: List[Tuple[str, Tuple[str, ...]]] = [
        ("dismiss_dialogs", ("弹窗", "对话框", "点掉", "遮挡", "dismiss")),
        ("capture", ("截屏", "截图", "截取屏幕", "看一眼", "capture", "screenshot")),
        ("focus", ("前台", "置顶", "focus")),
        ("click", ("点击按钮", "单击", "click")),
        ("type_text", ("打字", "键入", "输入文本", "输入文字", "敲入", "type_text")),
        ("hotkey", ("快捷键", "组合键", "hotkey")),
        ("inspect_window", ("窗口状态", "窗口句柄", "inspect_window")),
        ("run_chain", ("全流程", "端到端", "流水线", "完整制造", "从设计到加工", "成套",
                       "run_chain", "full_chain", "pipeline")),
        ("preflight", ("预检", "健康检查", "检查状态", "是否运行", "preflight")),
        ("validate_macro", ("宏程序", "语法校验", "变量提取", "括号配对", "validate_macro")),
        ("run_simulation", ("切削仿真", "动力学仿真", "碰撞", "过切", "干涉", "run_simulation")),
        ("run_journal", ("nxopen", "多轴cam", "多轴刀路", "run_journal", "复杂曲面")),
        ("create_parametric_part", ("三维建模", "特征树", "参数化建模", "create_parametric_part")),
        ("create_dxf", ("dxf", "工程图", "二维图", "工程制图", "create_dxf")),
        ("calculate_offsets", ("刀偏", "象限", "对刀", "calculate_offsets")),
    ]

    @classmethod
    def detect_software(cls, prompt: str, target_software: Optional[str] = None) -> str:
        """识别目标软件；显式入参优先，其次从提示词中匹配。"""
        if target_software:
            norm = normalize_software_key(target_software)
            if norm in SOFTWARE_SPECS:
                return norm
        p_lower = (prompt or "").lower()
        for sw in cls.SOFTWARE_SCAN_ORDER:
            if sw in p_lower or SOFTWARE_SPECS[sw]["display_name"].lower() in p_lower:
                return sw
        return ""

    @classmethod
    def detect_action(cls, prompt: str, action: Optional[str] = None) -> str:
        """识别操作动作；显式入参优先，其次从提示词中匹配。"""
        if action:
            return action.strip().lower()
        p_lower = (prompt or "").lower()
        for act, keywords in cls.ACTION_KEYWORDS:
            for kw in keywords:
                if kw.lower() in p_lower:
                    return act
        # 裸 G 代码 / Macro B 片段按宏程序校验处理
        if p_lower.startswith("#") or "g01" in p_lower or "g00" in p_lower:
            return "validate_macro"
        return ""

    @classmethod
    def resolve_tool_name(cls, software: str, action: str) -> str:
        """由目标软件 + 动作推出标准工具名。"""
        if action in GUI_ACTIONS:
            return "cadcam_desktop_gui"
        if action == "run_chain":
            return "cadcam_run_full_chain"
        if action == "preflight":
            return "cadcam_preflight"
        return SOFTWARE_TOOL.get(software, "cadcam_preflight")


class AgentDispatcher:
    """按显式接入方式执行工业任务，失败时沿固定容灾链降级。

    不做任何基于任务难度的自动选路。
    """

    def __init__(self):
        self.detector = TargetDetector()
        self.orchestrator = SixSoftwareOrchestrator()
        self.sdk_client = CADCAMToolchainClient()
        self.gui_controller = DesktopController()

    def plan(self, modality: AccessModality, prompt: str,
             target_software: Optional[str] = None,
             action: Optional[str] = None) -> DispatchPlan:
        """产出执行计划：目标软件 + 动作 + 工具名 + 固定容灾链。"""
        sw = self.detector.detect_software(prompt, target_software)
        act = self.detector.detect_action(prompt, action)
        tool_name = self.detector.resolve_tool_name(sw, act)

        fallbacks = list(MODALITY_FALLBACKS.get(modality, []))
        # GUI / 全流水线类动作补上同能力通道，避免降级时失去语义
        if act in GUI_ACTIONS and AccessModality.DESKTOP_GUI not in fallbacks:
            fallbacks.append(AccessModality.DESKTOP_GUI)
        if act == "run_chain" and AccessModality.AGENT_CHAIN not in fallbacks:
            fallbacks.append(AccessModality.AGENT_CHAIN)

        rationale = (
            f"接入方式由调用方显式指定为 {modality.value}；"
            "难度自动分级选路规则已停用，不做任何按难度的推断。"
            f"目标软件={sw or '未指定'}，动作={act or '未指定'}，"
            f"标准工具={tool_name}，失败时沿固定容灾链降级。"
        )

        return DispatchPlan(
            modality=modality,
            fallback_modalities=fallbacks,
            target_software=sw,
            action=act,
            tool_name=tool_name,
            rationale=rationale,
        )

    def execute(self, modality: AccessModality, prompt: str,
                target_software: Optional[str] = None,
                action: Optional[str] = None,
                params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute an industrial task through the specified modality.

        Args:
            modality: The access modality to use (explicitly specified by caller).
            prompt: Task description or user intent.
            target_software: Target software key (e.g. 'solidworks', 'autocad', 'vericut').
            action: Action name to perform.
            params: Additional parameters for the action.

        Returns:
            Execution result dictionary with 'status' and other result-specific fields.
        """
        params = params or {}
        plan = self.plan(modality, prompt, target_software, action)
        sw = plan.target_software or "cimco"
        act = plan.action

        t0 = time.time()
        attempts: List[Dict[str, Any]] = []
        final_result = None
        executed_modality = None

        for mod in [plan.modality] + plan.fallback_modalities:
            sub_t0 = time.time()
            try:
                result = self._execute_under_modality(mod, sw, act, plan.tool_name, prompt, params)
                attempts.append({
                    "modality": mod.value,
                    "status": "SUCCESS" if result.get("status") not in ("error", "failed") else "FAILED",
                    "latency_sec": round(time.time() - sub_t0, 4),
                    "result_summary": str(result)[:180],
                })
                if result.get("status") not in ("error", "failed"):
                    final_result = result
                    executed_modality = mod
                    break
            except Exception as e:
                attempts.append({
                    "modality": mod.value,
                    "status": "EXCEPTION",
                    "error": str(e),
                    "latency_sec": round(time.time() - sub_t0, 4),
                })

        latency = round(time.time() - t0, 4)

        return {
            "success": executed_modality is not None,
            "modality": plan.modality.value,
            "executed_modality": executed_modality.value if executed_modality else None,
            "target_software": sw,
            "action": act,
            "tool_name": plan.tool_name,
            "routing_rationale": plan.rationale,
            "difficulty_level": DIFFICULTY_ROUTING_DISABLED,
            "complexity_score": 0.0,
            "latency_sec": latency,
            "attempts": attempts,
            "data": final_result or {"status": "error",
                                     "message": "All execution modalities in cascade failed."},
        }

    def _execute_under_modality(self, modality: AccessModality,
                                sw: str, act: str, tool_name: str,
                                prompt: str, params: Dict[str, Any]) -> Dict[str, Any]:
        # 1. PYTHON_SDK (In-process memory call)
        if modality == AccessModality.PYTHON_SDK:
            if act in ("preflight", "fast_in_process_validation") or "preflight" in prompt.lower():
                return self.sdk_client.preflight()
            if act in GUI_ACTIONS:
                return self._execute_gui(act, sw, params)
            if "cimco" in sw or "code" in params or "#" in prompt:
                code_text = params.get("code") or prompt
                return self.sdk_client.cimco.validate(code_text)
            if "sscnc" in sw or "tool" in act:
                tools = params.get("tools") or [{"tool_num": 1, "type": "turning_rough", "x": 100.0, "z": 50.0, "r": 0.8, "quadrant": 3}]
                return self.sdk_client.sscnc.calculate_offsets(tools)
            if "autocad" in sw or "dxf" in act:
                drawing_name = params.get("drawing_name", "part_dxf")
                entities = params.get("entities", [{"type": "circle", "center": (0, 0), "radius": 20.0}])
                return self.sdk_client.autocad.create_dxf(drawing_name, entities)
            return self.orchestrator.dispatch(sw, act, params)

        # 2. FUNCTION_CALLING (OpenAI/Claude schema tool call)
        elif modality == AccessModality.FUNCTION_CALLING:
            tool_args = dict(params)
            if "action" not in tool_args and act:
                tool_args["action"] = act
            if "code" not in tool_args and ("#" in prompt or "G0" in prompt):
                tool_args["code"] = prompt
            if tool_name == "cadcam_run_full_chain":
                tool_args.setdefault("wish", prompt)
            if tool_name == "cadcam_desktop_gui":
                tool_args.setdefault("software", sw if sw != "cimco" else None)
                tool_args.setdefault("output_path",
                                     params.get("output_path",
                                                os.path.join(ROOT, "scratch", "gui_perception.png")))
            return execute_tool_call(tool_name, tool_args)

        # 3. CLI (Isolated subprocess)
        elif modality == AccessModality.CLI:
            import subprocess
            if act == "run_chain":
                cmd = [sys.executable, os.path.join(ROOT, "cadcam_cli.py"), "chain", "-w", prompt]
                if params.get("out_root"):
                    cmd.extend(["-o", params["out_root"]])
            elif act in GUI_ACTIONS:
                cmd = [sys.executable, os.path.join(ROOT, "cadcam_cli.py"), "gui", act]
                if act == "capture":
                    cmd.extend(["-o", params.get("output_path",
                                                 os.path.join(ROOT, "scratch", "gui_perception.png"))])
                if sw and sw != "cimco":
                    cmd.extend(["-s", sw])
            else:
                cmd = [sys.executable, os.path.join(ROOT, "cadcam_cli.py"), "dispatch", "-s", sw, "-a", act]
                if params:
                    cmd.extend(["-p", json.dumps(params, ensure_ascii=False)])
                elif "#" in prompt or "G0" in prompt:
                    cmd.extend(["--code", prompt])

            res = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=ROOT)
            if res.returncode == 0:
                try:
                    return json.loads(res.stdout)
                except Exception:
                    return {"status": "success", "raw_output": res.stdout}
            else:
                return {"status": "failed", "stderr": res.stderr, "returncode": res.returncode}

        # 4. MCP (Stdio Tool Call)
        elif modality == AccessModality.MCP:
            from bridges.cadcam_mcp_server import handle_request
            mcp_args = dict(params)
            if "action" not in mcp_args and act:
                mcp_args["action"] = act
            if "code" not in mcp_args and ("#" in prompt or "G0" in prompt):
                mcp_args["code"] = prompt
            if tool_name == "cadcam_run_full_chain":
                mcp_args.setdefault("wish", prompt)
            mcp_call = {
                "jsonrpc": "2.0",
                "id": int(time.time()),
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": mcp_args or {"action": act, "code": prompt}
                }
            }
            resp = handle_request(mcp_call)
            if resp and "result" in resp:
                content = resp["result"].get("content", [{}])[0].get("text", "{}")
                try:
                    return json.loads(content)
                except Exception:
                    return {"status": "success", "text": content}
            return {"status": "error", "message": "MCP call failed"}

        # 5. REST_API (HTTP Web Service)
        elif modality == AccessModality.REST_API:
            from bridges.toolchain_client import CADCAMToolchainClient
            client = CADCAMToolchainClient(base_url="http://127.0.0.1:8000")
            if act == "run_chain":
                return client.run_chain(prompt, out_root=params.get("out_root"))
            return client.dispatch(sw, act, params)

        # 6. DESKTOP_GUI (Perception & Dialog Control)
        elif modality == AccessModality.DESKTOP_GUI:
            return self._execute_gui(act, sw, params)

        # 7. AGENT_CHAIN (Full 6-Stage Manufacturing Pipeline)
        elif modality == AccessModality.AGENT_CHAIN:
            return self.orchestrator.run_full_chain(
                wish=prompt,
                out_root=params.get("out_root"),
                skip=tuple(params.get("skip", ()))
            )

        return {"status": "error", "message": f"Unsupported modality: {modality}"}

    def _execute_gui(self, act: str, sw: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """桌面感知与键鼠交互一律经 execute_tool_call，好让 desktop_gate 对
        PYTHON_SDK / DESKTOP_GUI 两种接入方式同样生效；此处不再自己抓控制器。"""
        args = dict(params or {})
        args["action"] = act
        if sw and sw not in ("cimco", "desktop"):
            args.setdefault("software", sw)
        if act == "capture":
            args.setdefault("output_path", os.path.join(ROOT, "scratch", "gui_perception.png"))
        return execute_tool_call("cadcam_desktop_gui", args)
