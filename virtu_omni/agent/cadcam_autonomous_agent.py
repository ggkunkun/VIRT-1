# -*- coding: utf-8 -*-
"""virtu_omni/agent/cadcam_autonomous_agent.py — CAD/CAM Agent with Explicit Modality Dispatch.

The caller must explicitly specify the access modality (e.g. PYTHON_SDK, CLI,
FUNCTION_CALLING, MCP, REST_API, DESKTOP_GUI, AGENT_CHAIN).
There is NO automatic difficulty-based routing — that rule was removed on 2026-10-31.

Equipped with:
- AgentDispatcher (Direct Modality Execution + fixed fallback cascade)
- IndustrialAgentTeam (Multi-Agent Collaborative Design)
- SixSoftwareOrchestrator (Hardware & Native App Bindings)
"""

from __future__ import annotations
import os
import sys
import time
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from virtu_omni.agent.adaptive_router import (
    AgentDispatcher,
    AccessModality,
    DispatchPlan,
    DIFFICULTY_ROUTING_DISABLED,
)
from virtu_omni.agent.agent_team import IndustrialAgentTeam


@dataclass
class AgentExecutionReport:
    task_prompt: str
    modality: str
    target_software: str
    action: str
    success: bool
    total_latency_sec: float
    result_data: Dict[str, Any]
    # 难度字段保留但恒为停用标记：难度自动选路规则已删除
    difficulty_level: str = DIFFICULTY_ROUTING_DISABLED
    complexity_score: float = 0.0
    executed_modality: Optional[str] = None
    routing_rationale: str = ""
    execution_attempts: List[Dict[str, Any]] = None

    def __post_init__(self):
        if self.execution_attempts is None:
            self.execution_attempts = []

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def summary_markdown(self) -> str:
        icon = "[PASS]" if self.success else "[FAIL]"
        return f"""### {icon} Agent 执行报告

- **任务意图**: `{self.task_prompt}`
- **接入方式**: `{self.modality}`
- **实际执行接入**: `{self.executed_modality or self.modality}`
- **目标软件**: `{self.target_software}`
- **操作**: `{self.action}`
- **难度自动选路**: `{self.difficulty_level}`（该规则已停用，接入方式由调用方显式指定）
- **端到端耗时**: `{self.total_latency_sec:.4f}s` (尝试次数: `{len(self.execution_attempts)}`)
"""


class CADCAMAutonomousAgent:
    """CAD/CAM Agent that executes tasks through an explicitly specified access modality.

    The caller must provide the modality directly; no automatic difficulty-based
    routing is performed.
    """

    def __init__(self):
        self.dispatcher = AgentDispatcher()
        self.agent_team = IndustrialAgentTeam()
        self._super_agent_instance = None

    @property
    def super_agent(self):
        """Bridge property returning the underlying Virtu Super Agent."""
        if self._super_agent_instance is None:
            from virtu_omni.agent.super_agent import VirtuSuperAgent
            self._super_agent_instance = VirtuSuperAgent()
        return self._super_agent_instance

    def solve(self, prompt: str, modality: str = "FUNCTION_CALLING",
              target_software: Optional[str] = None,
              action: Optional[str] = None,
              params: Optional[Dict[str, Any]] = None) -> AgentExecutionReport:
        """Execute a task through the specified access modality.

        Args:
            prompt: Task description or user manufacturing intent.
            modality: Access modality string (e.g. 'PYTHON_SDK', 'CLI', 'MCP',
                      'FUNCTION_CALLING', 'REST_API', 'DESKTOP_GUI', 'AGENT_CHAIN').
            target_software: Target software key (e.g. 'solidworks', 'autocad').
            action: Action name to perform.
            params: Additional parameters for the action.

        Returns:
            AgentExecutionReport with execution results.
        """
        try:
            mod = AccessModality(modality.upper())
        except ValueError:
            mod = AccessModality.FUNCTION_CALLING

        result = self.dispatcher.execute(
            modality=mod,
            prompt=prompt,
            target_software=target_software,
            action=action,
            params=params,
        )

        return AgentExecutionReport(
            task_prompt=prompt,
            modality=result["modality"],
            target_software=result["target_software"],
            action=result["action"],
            success=result["success"],
            total_latency_sec=result["latency_sec"],
            result_data=result["data"],
            difficulty_level=result["difficulty_level"],
            complexity_score=result["complexity_score"],
            executed_modality=result["executed_modality"],
            routing_rationale=result["routing_rationale"],
            execution_attempts=result["attempts"],
        )

    def analyze_task(self, prompt: str, modality: str = "FUNCTION_CALLING",
                     target_software: Optional[str] = None,
                     action: Optional[str] = None) -> DispatchPlan:
        """Produce the execution plan without running anything.

        保留该方法是为了兼容旧的 `/cadcam/agent/analyze` 调用方：
        现在返回的是「目标软件 + 动作 + 工具 + 容灾链」计划，不再含难度判定。
        """
        try:
            mod = AccessModality(modality.upper())
        except ValueError:
            mod = AccessModality.FUNCTION_CALLING
        return self.dispatcher.plan(mod, prompt, target_software, action)

    def explain_decision(self, prompt: str, modality: str = "FUNCTION_CALLING",
                         target_software: Optional[str] = None,
                         action: Optional[str] = None) -> str:
        """Human-readable explanation of the dispatch plan (no difficulty tiering)."""
        plan = self.analyze_task(prompt, modality, target_software, action)
        fallbacks_str = " -> ".join([m.value for m in plan.fallback_modalities]) or "（无）"
        return (
            f"【接入方式派发说明】\n"
            f"1. 接入方式: {plan.modality.value}（由调用方显式指定，非法值回落 FUNCTION_CALLING）\n"
            f"2. 目标软件: {plan.target_software or '未指定'}\n"
            f"3. 操作动作: {plan.action or '未指定'}\n"
            f"4. 标准工具: {plan.tool_name}\n"
            f"5. 备选容灾链条: {fallbacks_str}\n"
            f"6. 难度自动选路: 已停用（{DIFFICULTY_ROUTING_DISABLED}）\n"
            f"7. 决策依据: {plan.rationale}"
        )


if __name__ == "__main__":
    agent = CADCAMAutonomousAgent()
    print("Testing CADCAMAutonomousAgent (explicit modality)...")

    # Test: explicitly specify PYTHON_SDK for a preflight check
    rep = agent.solve(
        "系统健康预检与进程检查",
        modality="PYTHON_SDK",
        action="preflight",
    )
    print(rep.summary_markdown())
    print("Data:", json.dumps(rep.result_data, ensure_ascii=False, indent=2))
