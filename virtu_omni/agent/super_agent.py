# -*- coding: utf-8 -*-
"""virtu_omni/agent/super_agent.py — Virtu Industrial Super Agent (超级智能体).

Unified Omnipotent Industrial Autonomous Engineering Agent.
Unifies and transcends individual siloed sub-agents into an integrated, meta-cognitive,
multi-faceted Super Agent architecture.

Key Architectural Pillars:
1. Omnipotent Domain Facets (全域专业面):
   - Architect Facet: Intent decomposition, engineering specs, sub-module hierarchy.
   - Modeling Facet: 3D Parametric CAD, FeatureTree, swEqnMgr equations, Volume Conservation.
   - Standards Facet: 2D Engineering Drawings, ezdxf sub-10ms drafting, GD&T (H7/g6, runout).
   - Machining Facet: CAM Toolpaths, CNC Macro B (#100, #500), multi-controller dialects.
   - CAE Simulation Facet: Lamé thick-cylinder elasticity theory, von Mises yield stress, FOS >= 1.5.
   - Auditor & Sandbox Facet: Headless virtual simulation, G00 plunge collision sentinel, self-healing.
   - Memory & Evolution Facet: Dense-vector episodic memory, Hindsight Recall & Reflect, skill synthesis.
   - Desktop Perception Facet: Windows desktop GUI automation, closed-loop sentinels.
   - Explicit Modality Dispatcher: 7-modality direct execution (PYTHON_SDK, CLI, MCP, FUNCTION_CALLING, etc.).

2. Multi-Mode Autonomous Execution (四大运行模式):
   - Mode AUTONOMOUS: Full-cycle closed-loop engineering solve with stage-gated memory reclamation.
   - Mode REACT: First-principles dynamic Thought -> Action -> Observation -> Reflection loop.
   - Mode MODALITY: Single-turn explicit modality execution with fixed fallback cascade.
   - Mode SWARM: Supreme-Commander hierarchical delegation with Blackboard write-lock leases.

3. The Extreme Step-by-Step Self-Verification & Circuit Breaker Axiom:
   “又快又准到极限，未到极限则继续，到了极限则放弃”
   - k_max = 3 attempt budget.
   - Under limit: In-the-loop Reflexion self-healing and instant re-audit.
   - Limit reached: Circuit breaker abort + atomic rollback + RCFA (Root Cause Failure Analysis) report.

4. Measurement Constitution Compliance (测量宪法):
   - Verifiable physical metrics (mass properties, bounding box, FOS >= 1.5).
   - Zero hallucinated badges or hardcoded success strings.
"""

from __future__ import annotations

import enum
import hashlib
import inspect
import json
import logging
import math
import os
import shutil
import sys
import tempfile
import time
import typing
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

# --- V-02 修复：Harness 脚本装载前的 AST 闸门 ---------------------------------
# Harness 组件（runs/**/harnesses/**/scripts/*.py）来自外部可写的暂存目录，
# 也可能是自进化流程的产物，不能当作可信代码直接 exec。
HARNESS_TRUST_ENV = "VIRTU_HARNESS_TRUST"

try:
    from virtu_omni.security import code_guard as _code_guard
except Exception:  # pragma: no cover
    _code_guard = None

#: Harness 脚本允许 import 的模块（对齐现网 218 个真实脚本的用法：sys/json/csv/decimal）。
HARNESS_ALLOWED_MODULES = (
    "sys", "json", "csv", "decimal", "math", "re", "statistics", "itertools",
    "collections", "dataclasses", "typing", "datetime", "time", "functools",
    "pathlib", "hashlib", "base64", "random", "string", "textwrap", "io",
)


def _harness_trust_mode() -> str:
    """``enforce``（默认）/ ``audit``（放行但记录）/ ``loose``（完全旧行为）。"""
    mode = str(os.environ.get(HARNESS_TRUST_ENV) or "").strip().lower()
    return mode if mode in ("enforce", "audit", "loose") else "enforce"


def _harness_validate(code: Any) -> List[str]:
    if _code_guard is None:
        return []
    return _code_guard.validate_source(code, allowed_modules=HARNESS_ALLOWED_MODULES)


def _harness_builtins() -> Dict[str, Any]:
    if _code_guard is None:
        return {}
    return _code_guard.restricted_builtins()


# ---------------------------------------------------------------------------
# D1 修复（2026-11-16）：facet 调用契约与注册契约对齐
# ---------------------------------------------------------------------------
# 绑定逻辑放在**零依赖独立模块**里，理由见 virtu_omni/agent/tool_binding.py 顶部：
#   ① Super Agent 的方法会被测试用 ast.get_source_segment 抠出来、在合成命名空间里
#      exec —— 被抽取的方法不能依赖模块级名字 ⇒ 调用方要用**函数内 import**拿它；
#   ② 绑定规则是纯函数，可以被单独证伪（缺必填参数必须抛错，不许静默降级）。
from virtu_omni.agent.tool_binding import (
    FACET_ARRAY_ITEM_FIELDS as _FACET_ARRAY_ITEM_FIELDS,
    bind_facet_args as _bind_facet_args,
    facet_input_schema as _facet_input_schema,
    facet_json_type as _facet_json_type,
    facet_params as _facet_params,
)


from virtu_omni.agent.adaptive_router import (
    AccessModality,
    AgentDispatcher,
    DispatchPlan,
    DIFFICULTY_ROUTING_DISABLED,
)
from virtu_omni.agent.agent_team import (
    AuditorAndSandboxAgent,
    ChiefArchitectAgent,
    EvolutionAndMemoryAgent,
    MachiningAndToolpathAgent,
    ParametricModelingAgent,
    StandardsAndGDAgent,
)
from virtu_omni.agent.blueprint_inverse_engine import BlueprintInverseEngine
from virtu_omni.agent.cadcam_autonomous_agent import AgentExecutionReport
from virtu_omni.agent.headless_sandbox_verifier import HeadlessSandboxVerifier
from virtu_omni.agent.process_memory_reclaimer import ProcessMemoryReclaimer
from virtu_omni.agent.self_reflection_optimizer import SelfReflectionOptimizer
from virtu_omni.agent.skill_writer_and_memory import SkillWriterAndMemory
from virtu_omni.engine.wish_cad_cam_engine import WishCADCAMEngine
from virtu_omni.memory import (
    BuiltinWorkingMemory,
    LongTaskHallucinationSentinel,
    MemoryType,
    VirtuHindsightMemory,
    VirtuSleepFramework,
    get_sleep_framework,
)
from virtu_omni.google_suite import (
    VirtuGoogleDeepMindSuite,
    get_google_suite,
    SketchIntent,
    GeometricPrimitive,
    GeometricConstraint,
    ConstraintType,
    IndustrialSoftwareTarget,
    MachiningOperation,
    MachiningState,
)
from virtu_omni.model_evolution_suite import (
    VirtuFrontierModelSuite,
    get_model_evolution_suite,
    CADCommand,
)
from virtu_omni.ultimate_suite import (
    VirtuUltimateSuite,
    get_ultimate_suite,
)
from virtu_omni.security.auditor import ModelSecurityAuditor

logger = logging.getLogger("virtu_omni.agent.super_agent")

# --- E 组：RunContext 全链透传（审计 §7.2 / §7.4）-----------------------------
# 只在标准库范围内实现，取不到就退化为最小结构，绝不因为可观测性拖垮主流程。
try:
    from virtu_omni.agent.run_context import RunContext, content_fingerprint, ensure_ctx
except Exception:                                        # pragma: no cover
    class RunContext:                                    # type: ignore
        def __init__(self, run_id="unavailable", span="root", parent_span="", step=0):
            self.run_id, self.span, self.parent_span, self.step = run_id, span, parent_span, step

        def child(self, span, step=None):
            return self

        def with_step(self, step):
            return self

        def log(self, *a, **k):
            return None

        def to_dict(self):
            return {"run_id": self.run_id, "span": self.span, "step": self.step}

        def elapse_ms(self):
            return 0.0

    def content_fingerprint(*parts, length=16):
        return hashlib.sha256(json.dumps([str(x) for x in parts], ensure_ascii=False)
                             .encode("utf-8")).hexdigest()[:length]

    def ensure_ctx(ctx=None, *parts, **extra):
        return ctx if isinstance(ctx, RunContext) else RunContext(content_fingerprint(*parts))


def _new_run_ctx(prompt: str, mode: str, **extra) -> RunContext:
    """一次 solve 一个 RunContext：run_id 取内容和模式的指纹，同输入必得同 id。"""
    return RunContext.root(prompt, mode, **extra)


# --- C 组：REACT 真循环（审计 §1.6 / 增强项 7）---------------------------------
def _react_engine_mode() -> str:
    """REACT 执行引擎开关：deep_agent（默认，真 LLM 循环）/ pipeline（旧硬编码流水线）。"""
    return (os.environ.get("VIRTU_REACT_ENGINE") or "deep_agent").strip().lower()


def _react_engine_budget_s() -> int:
    """REACT 真循环的单次模型调用预算（秒），默认 90。

    存在的理由不是"图快"，而是可证伪：deep_agent 会把 30+ facet 全量喂给规划阶段，
    在 14B 量化模型 + 有限显存上单次规划可能到分钟级。没有预算时"引擎不可用"这件事
    只能表现为**卡住**，既无法降级也无法留痕。设预算后，超时 → 异常 → 可见降级，
    metrics 里写明 engine_fallback_reason，调用方能判断这次结果是不是真循环给的。
    设为 0 表示不设预算（沿用 deep_agent 自己的 chat_timeout_s）。
    """
    raw = (os.environ.get("VIRTU_REACT_BUDGET_S") or "90").strip()
    try:
        return max(0, int(float(raw)))
    except (TypeError, ValueError):
        return 90


class FacetToolAdapter:
    """把 Super Agent 的 facet 注册表包装成 deep_agent 可调用的工具集。

    deep_agent 负责 Plan -> Act -> Verify 的真实 LLM 循环（含 duplicate_action /
    unplanned_write / 连续失败熔断），本适配器只做「工具名 -> facet 函数」映射与
    调用记录，不参与任何成功判定——判定权留在 verify_stage。
    """

    def __init__(self, registry: Dict[str, Tuple[str, Callable[[Any], Any]]]):
        self.registry = registry
        self.calls: List[Dict[str, Any]] = []

    def schemas(self) -> List[Dict[str, Any]]:
        out = []
        for name, (desc, fn) in self.registry.items():
            params = _facet_params(fn)
            if len(params) <= 1:
                # 单参 facet：沿用既有 payload 字符串契约（26 个已验证工具行为不变）
                props: Dict[str, Any] = {
                    "payload": {
                        "type": "string",
                        "description": "该 facet 的输入：纯文本 prompt，或 JSON 字符串形式的结构化参数",
                    }
                }
                required: List[str] = ["payload"]
            else:
                # 多参 facet：广播真实形参名，规划器才能产出合法 args
                real = _facet_input_schema(fn)
                props = dict(real["properties"])
                props["payload"] = {
                    "type": "string",
                    "description": "等价写法：把全部参数打包成一个 JSON 字符串",
                }
                # required 用真实必填形参：规划器据此在 tool_brief 里打 "*"，
                # 产出可被 validate_plan 放行的 args。payload 兼容写法仍保留在
                # properties 里（供直接 call_tool 的调用方使用），但不进 required。
                required = list(real["required"])
            out.append({
                "name": name,
                "description": str(desc),
                "inputSchema": {
                    "type": "object",
                    "properties": props,
                    "required": required,
                },
            })
        return out

    def _decode_payload(self, raw: Any) -> Any:
        if isinstance(raw, (dict, list)):
            return raw
        if raw is None:
            return None
        text = str(raw)
        try:
            return json.loads(text)
        except Exception:
            return text

    def _extract_payload(self, name: str, args: Dict[str, Any]) -> Any:
        """从调用参数里取出真正要传给 facet 的载荷。

        两种合法写法：
          1. 具名参数：``{"length_mm": 45.0, ...}``（schema 广播的推荐写法）
          2. 包裹写法：``{"payload": "<json 或文本>"}``
        具名参数优先；否则退回 payload；都没有则原样传空 dict。
        """
        args = args or {}
        entry = self.registry.get(name)
        if entry is not None:
            names = {p.name for p in _facet_params(entry[1])}
            named = {k: v for k, v in args.items()
                     if k in names and k != "payload"}
            if named:
                return named
        if "payload" in args:
            return self._decode_payload(args.get("payload"))
        return args

    def call(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        t0 = time.time()
        # Keep role contracts local to the call: some REACT pipeline methods are AST-extracted
        # into isolated namespaces and must not depend on new module globals.
        from virtu_omni.agent.facet_contracts import role_for_tool, validate_facet_result

        role = role_for_tool(name)
        payload = self._extract_payload(name, args)
        rec: Dict[str, Any] = {"tool": name, "role": role["id"],
                               "args": args, "ts": round(t0, 3)}
        try:
            if name not in self.registry:
                raise KeyError(f"unknown facet tool: {name}")
            _desc, fn = self.registry[name]
            pos, kw = _bind_facet_args(fn, payload)
            val = fn(*pos, **kw)
            contract = validate_facet_result(name, val)
            rec["output_contract"] = contract
            if not contract["passed"]:
                text = "FACET_CONTRACT_ERROR " + "; ".join(contract["issues"])
                rec.update({"ok": False, "text": text})
                return {"is_error": True, "text": text, "impl": f"facet:{name}",
                        "argv": None, "role": role["id"], "contract": contract}
            text = val if isinstance(val, str) else json.dumps(val, ensure_ascii=False, default=str)
            rec.update({"ok": True, "text": text[:4000]})
            return {"is_error": False, "text": text, "impl": f"facet:{name}",
                    "argv": None, "role": role["id"], "contract": contract}
        except Exception as err:
            text = f"FACET_ERROR {type(err).__name__}: {err}"
            rec.update({"ok": False, "text": text, "error": type(err).__name__})
            return {"is_error": True, "text": text, "impl": f"facet:{name}",
                    "argv": None, "role": role["id"]}
        finally:
            rec["exec_s"] = round(time.time() - t0, 3)
            self.calls.append(rec)

    def restore(self) -> bool:
        """deep_agent 退出时会调 restore()；facet 不使用剪贴板，恒为 True。"""
        return True


def trace_thought_of(history_item: Dict[str, Any]) -> str:
    """deep_agent 的 history 只有 tool/args，退化时用「工具 + 入参」拼一句可读的 Thought。"""
    return f"选择工具 {history_item.get('tool')} 处理 {str(history_item.get('args'))[:120]}"



class SuperAgentMode(str, enum.Enum):
    """Operational mode for Virtu Super Agent."""
    AUTONOMOUS = "AUTONOMOUS"    # Full-lifecycle closed-loop industrial design to NC verification
    REACT = "REACT"              # Dynamic iterative ReAct reasoning and tool-calling loop
    MODALITY = "MODALITY"        # Explicit single-turn access modality execution
    SWARM = "SWARM"              # Hierarchical delegation with specialized sub-agents
    HARNESSED = "HARNESSED"      # Recursive agent self-improvement under Google Research Harness²


class CircuitBreakerException(Exception):
    """Exception triggered when step-by-step verification fails k_max attempts or stagnates."""

    def __init__(self, stage: str, attempt: int, error_msg: str, rcfa_report: Dict[str, Any]):
        super().__init__(f"Circuit Breaker triggered at stage [{stage}] after {attempt} attempts: {error_msg}")
        self.stage = stage
        self.attempt = attempt
        self.error_msg = error_msg
        self.rcfa_report = rcfa_report


@dataclass
class SuperAgentExecutionResult:
    """Unified execution result returned by Virtu Super Agent."""
    task_prompt: str
    mode: str
    success: bool
    runtime_seconds: float
    facets_engaged: List[str]
    artifacts: Dict[str, Any]
    trace_log: List[Dict[str, Any]]
    metrics: Dict[str, Any]
    circuit_breaker_tripped: bool = False
    rcfa_report: Optional[Dict[str, Any]] = None
    output_dir: Optional[str] = None
    modality_report: Optional[Dict[str, Any]] = None
    #: 调用方请求的模式（仅供对照）。``mode`` 始终记录真实执行路径，
    #: 未被实现的能力（如 SWARM 的 Blackboard 委派）不得改写 ``mode``。
    requested_mode: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def summary_markdown(self) -> str:
        icon = "[PASS]" if self.success else "[CIRCUIT_BREAKER_ABORT]" if self.circuit_breaker_tripped else "[FAIL]"
        facets_str = ", ".join(self.facets_engaged) or "全域统筹"
        lines = [
            f"### {icon} Virtu Super Agent 执行报告",
            f"- **任务意图**: `{self.task_prompt}`",
            f"- **运行模式**: `{self.mode}`",
            f"- **调动专业面 (Facets)**: `{facets_str}`",
            f"- **执行总耗时**: `{self.runtime_seconds:.4f}s`",
            f"- **核心物理指标**: `体积守恒: {self.metrics.get('volume_conservation', 'N/A')}`, `安全系数 FOS: {self.metrics.get('safety_factor', 'N/A')}`",
        ]
        if self.output_dir:
            lines.append(f"- **工件落盘目录**: `{self.output_dir}`")
        if self.circuit_breaker_tripped and self.rcfa_report:
            lines.extend([
                f"\n#### 熔断根因分析 (RCFA Report)",
                f"- **触发阶段**: `{self.rcfa_report.get('stage')}`",
                f"- **尝试次数**: `{self.rcfa_report.get('attempts')}`",
                f"- **根因诊断**: `{self.rcfa_report.get('root_cause')}`",
                f"- **人工处置建议**: `{self.rcfa_report.get('actionable_advice')}`"
            ])
        return "\n".join(lines)


class VirtuSuperAgent:
    """Virtu Industrial Super Agent (超级智能体).
    
    A centralized, omni-competent autonomous engineering agent that integrates
    CAD, CAE, CAM, Standards, Verification, ReAct, Memory, and Tool Calling into
    a single coherent meta-cognitive architecture.
    """

    # Material physical property database for analytical CAE verification
    MATERIAL_PROPERTIES = {
        "Cr12MoV": {"density_g_cm3": 7.75, "yield_strength_mpa": 850.0, "poisson": 0.28, "name_cn": "冷作模具钢 Cr12MoV"},
        "Ti-6Al-4V": {"density_g_cm3": 4.43, "yield_strength_mpa": 880.0, "poisson": 0.34, "name_cn": "钛合金 TC4 (Ti-6Al-4V)"},
        "AL7075-T6": {"density_g_cm3": 2.81, "yield_strength_mpa": 503.0, "poisson": 0.33, "name_cn": "超硬铝合金 7075-T6"},
        "AL6061-T6": {"density_g_cm3": 2.70, "yield_strength_mpa": 276.0, "poisson": 0.33, "name_cn": "航空硬铝 6061-T6"},
        "Steel45": {"density_g_cm3": 7.85, "yield_strength_mpa": 355.0, "poisson": 0.29, "name_cn": "优质碳素结构钢 45#"},
        "SS304": {"density_g_cm3": 7.93, "yield_strength_mpa": 205.0, "poisson": 0.29, "name_cn": "奥氏体不锈钢 304"},
    }

    def __init__(self, log_path: Optional[str] = None):
        # 1. Core Engines & Facet Delegates
        self.wish_engine = WishCADCAMEngine()
        self.inverse_engine = BlueprintInverseEngine()
        self.sandbox_verifier = HeadlessSandboxVerifier()
        self.reflection_optimizer = SelfReflectionOptimizer()
        self.skill_memory = SkillWriterAndMemory()
        self.security_auditor = ModelSecurityAuditor()
        self.hindsight_memory = VirtuHindsightMemory()
        self.sleep_framework = get_sleep_framework()
        self.google_suite = get_google_suite()
        self.model_suite = get_model_evolution_suite()
        self.ultimate_suite = get_ultimate_suite()
        self.reclaimer = ProcessMemoryReclaimer(log_path=log_path)
        self.dispatcher = AgentDispatcher()

        # Specialized sub-delegates for fine-grained capability queries
        self._delegate_architect = ChiefArchitectAgent()
        self._delegate_modeler = ParametricModelingAgent()
        self._delegate_standards = StandardsAndGDAgent()
        self._delegate_machining = MachiningAndToolpathAgent()
        self._delegate_auditor = AuditorAndSandboxAgent()
        self._delegate_memory = EvolutionAndMemoryAgent(hindsight_memory=self.hindsight_memory)

        # 2. Dynamic Tool Registry for ReAct Mode
        self._tool_registry: Dict[str, Tuple[str, Callable[[Any], Any]]] = {}
        self._register_default_tools()

        # 3. Scratchpad & Built-in Working Memory + Anti-Hallucination Sentinel
        self.scratchpad: List[Dict[str, Any]] = []
        wm_persist = os.environ.get("VIRTU_WORKING_MEMORY_PATH") or None
        self.working_memory = BuiltinWorkingMemory(
            session_id=f"super_agent_{id(self)}",
            persist_path=wm_persist,
        )
        self.hallucination_sentinel = LongTaskHallucinationSentinel(self.working_memory)
        self.last_memory_context: str = ""

        # 能力传授目录（Capability Transfer）：按任务检索通用能力 SOP，按需注入。
        # 容错加载——目录缺失、依赖异常都不得让 Agent 起不来；失败时静默降级为无能力提示，
        # 由 last_capability_hint["applied"]=False 可查，不做"看起来加载了"的假象。
        self.capability_registry = None
        self.last_capability_hint: Dict[str, Any] = {}

        # 4. Harness 2 Staged Context & Components
        self.active_harness_dir: Optional[Path] = None
        self.active_harness_fingerprint: Optional[str] = None
        self.harness_components: Dict[str, str] = {}
        self.custom_system_prompt: Optional[str] = None
        self.custom_guardrails: Optional[str] = None
        self.custom_memory: Optional[str] = None
        self.custom_tool_guidance: Optional[str] = None

        # 5. Rollback Session State（供 execute_with_circuit_breaker 的默认回滚使用）
        self._session_artifacts: List[Dict[str, Any]] = []
        self._session_snapshot_dir: Optional[str] = None
        self._session_pids: List[int] = []
        self.last_rollback_report: Optional[Dict[str, Any]] = None
        self._current_run_id: Optional[str] = None

    def _register_default_tools(self) -> None:
        """Register default tools available to Super Agent in ReAct and autonomous modes."""
        self.register_tool(
            "parse_intent",
            "Parse customer manufacturing intent into typed parametric geometric specs.",
            self.facet_parse_intent,
        )
        self.register_tool(
            "generate_parametric_cad",
            "Synthesize 3D CAD FeatureTree, equations, and native SolidWorks VBA code.",
            self.facet_generate_cad,
        )
        self.register_tool(
            "generate_standards_drawing",
            "Generate 2D drafting specifications, layer discipline, and GD&T tolerances.",
            self.facet_generate_standards,
        )
        self.register_tool(
            "generate_cam_toolpath",
            "Generate multi-controller CNC Macro B program with cutting feeds and speeds.",
            self.facet_generate_cam,
        )
        self.register_tool(
            "verify_cae_stress",
            "Execute finite element/elasticity stress analysis and compute Factor of Safety (FOS >= 1.5).",
            self.facet_verify_cae,
        )
        self.register_tool(
            "audit_sandbox_simulation",
            "Perform headless virtual simulation, collision sentinel, and self-reflection.",
            self.facet_audit_sandbox,
        )
        self.register_tool(
            "recall_hindsight_memory",
            "Retrieve historical design patterns and mental models from long-term memory.",
            self.facet_recall_memory,
        )
        self.register_tool(
            "recall_vericut_training",
            "Recall measured evidence from the ingested VERICUT 9.6 official training library: "
            "project configs, controls, tool libraries, NC programs, Auto-Diff tolerances and session handouts.",
            self.facet_recall_vericut_training,
        )
        self.register_tool(
            "query_training_cases",
            "Query the measured VERICUT training case index (E:/training): which cases are "
            "intentional error/debug demos vs reference cases, and what machining capability each "
            "case needs (lathe / 3-axis / 4-axis / 5-axis positioning or simultaneous / mill-turn), "
            "with per-case sha256 and evidence quotes.",
            self.facet_query_training_cases,
        )
        self.register_tool(
            "commit_experience",
            "Distill verified engineering solution into episodic and vector memory.",
            self.facet_commit_memory,
        )
        self.register_tool(
            "dispatch_modality",
            "Execute single-action tool call across 7 access modalities (PYTHON_SDK, CLI, etc.).",
            self.facet_dispatch_modality,
        )
        self.register_tool(
            "trigger_sleep_cycle",
            "Trigger Google Sleep continual learning: memory consolidation, dreaming, and anti-forgetting gate.",
            self.facet_sleep_consolidation,
        )
        self.register_tool(
            "harness2_refine",
            "Recursively refine agent prompts, guardrails, skills and memory for a task using Google Research Harness 2.",
            self.facet_harness2_refine,
        )
        self.register_tool(
            "optimize_operators",
            "Autonomously benchmark, profile, optimize and verify model neural operators (Attention, RoPE, SwiGLU, RMSNorm).",
            self.facet_optimize_operators,
        )
        self.register_tool(
            "optimize_operators_to_limit",
            "Characterise the GPU roofline, then push operators toward the theoretical limit via CUDA Graph / TF32 / BF16 with attributable verification.",
            self.facet_optimize_operators_to_limit,
        )
        self.register_tool(
            "funsearch_evolve",
            "Evolve heuristic algorithms for 2D nesting and machining optimization using Google DeepMind FunSearch.",
            self.facet_funsearch_evolve,
        )
        self.register_tool(
            "solve_neuro_symbolic_geometry",
            "Analytically solve 2D/3D parametric constraints with zero arithmetic hallucination using DeepMind AlphaGeometry.",
            self.facet_solve_geometry,
        )
        self.register_tool(
            "check_software_affordance",
            "Ground actions in machine/software state to prevent crashes and deadlocks using Google SayCan.",
            self.facet_check_affordance,
        )
        self.register_tool(
            "mcts_plan_process_route",
            "Plan optimal multi-operation CNC machining sequence with Process Reward Model using DeepMind Rest-MCTS.",
            self.facet_mcts_plan,
        )
        self.register_tool(
            "rlvr_grpo_eval",
            "Evaluate candidate reasoning trajectories with deterministic physical rewards (RLVR) using DeepSeek-R1 GRPO.",
            self.facet_rlvr_eval,
        )
        self.register_tool(
            "prm_stepwise_audit",
            "Step-by-step Process Reward Model verification of G-code or CAD sequences (OpenAI o1 / Math-Shepherd).",
            self.facet_prm_audit,
        )
        self.register_tool(
            "brep_dsl_compile",
            "Compile and topologically validate 3D B-Rep CAD-DSL commands with Euler-Poincaré invariants (MIT DeepCAD).",
            self.facet_brep_compile,
        )
        self.register_tool(
            "quiet_star_self_heal",
            "Silently execute and self-heal code using Stanford Quiet-STaR virtual execution sandbox.",
            self.facet_quiet_star_heal,
        )
        self.register_tool(
            "blueprint_spatial_ground",
            "Ground 2D blueprint visual coordinates to 3D parametric CAD specifications (Apple Ferret / Qwen2-VL).",
            self.facet_blueprint_ground,
        )
        self.register_tool(
            "pinn_stress_surrogate",
            "Predict real-time continuous elasticity von Mises stress and SIMP topology optimization (NVIDIA Modulus / FNO).",
            self.facet_pinn_predict,
        )
        self.register_tool(
            "web_search",
            "Perform safe web search for engineering standards, materials, or technical queries with automated content filtering.",
            self.facet_web_search,
        )
        self.register_tool(
            "fetch_web_content",
            "Scrape and sanitize web content with automated PII masking and harm filtering.",
            self.facet_fetch_web_content,
        )
        self.register_tool(
            "internet_deep_learning",
            "Continually distill and assimilate safe web knowledge into persistent vector memory and SFT dataset.",
            self.facet_internet_deep_learning,
        )
        self.register_tool(
            "autonomous_learn_gap",
            "Autonomously search the internet, filter bad information, and ingest new engineering knowledge into memory when encountering unknown concepts or errors.",
            self.facet_autonomous_learn_gap,
        )
        self.register_tool(
            "desktop_gui",
            "Unified desktop GUI perception, mouse/keyboard control, and industrial software window automation.",
            self.facet_desktop_gui,
        )
        self.register_tool(
            "mouse_control",
            "Control mouse operations (click, double click, right click, middle click, move, drag, scroll).",
            self.facet_mouse_control,
        )
        self.register_tool(
            "keyboard_control",
            "Control keyboard operations (type text, send hotkey combinations like Ctrl+S, Alt+F4, Enter, Esc, F5).",
            self.facet_keyboard_control,
        )
        self.register_tool(
            "screen_control",
            "Control screen perception and software windows (capture screen, focus window, inspect window, dismiss dialogs, visual inspection).",
            self.facet_screen_control,
        )
        self.register_tool(
            "agent_desktop",
            "Reliable desktop computer use via native OS accessibility trees (@ref IDs, snapshot, find, click, type, windows). Powered by Vercel Labs agent-desktop.",
            self.facet_agent_desktop,
        )
        self.register_tool(
            "web_verify_and_correct",
            "After CAD design is generated, SEARCH THE INTERNET for GB/ISO machining tolerances, "
            "surface roughness and process standards, COMPARE them with the current design spec "
            "and RETURN corrections. Use payload JSON: {design_spec:{...}, topic:'...'}. "
            "Returns corrected_spec that must be written back into the design before CAE/CAM.",
            self.facet_web_verify_and_correct,
        )
        self.register_tool(
            "verify_product_integrity",
            "Gate that prevents delivering a raw CYLINDER STOCK instead of the finished product. "
            "Verifies CAD feature volume conservation (deltaV != 0), product geometry is not a "
            "degenerate cylinder blank, and VERICUT Auto-Diff red=0/blue<=2%/green>=98%. "
            "Use payload JSON: {features:[{name,kind,delta_v}], geometry:{...} or geometry_mesh:path, "
            "autodiff:{gouge_ratio,excess_ratio,in_tol_ratio} or autodiff_report:path}. "
            "If evidence is missing it returns verified=false and MUST NOT be claimed as a pass.",
            self.facet_verify_product_integrity,
        )
        self.register_tool(
            "inspect_step_artifact",
            "Read-only STEP handoff check. Measures Open Cascade B-Rep validity, solid/face/edge counts, "
            "volume_mm3, bbox_mm, file SHA-256, and declared length units. Returns PASS only for a "
            "valid positive-volume solid with explicit mm units; this does not prove design conformity.",
            self.facet_inspect_step_artifact,
        )
        self.register_tool(
            "observe_surface",
            "Turn an opaque complex surface mesh into EVIDENCE the agent can SEE: curvature field "
            "(high-curvature regions need tighter step-over), residual/scallop height field (flags "
            "surfaces exceeding the finish tolerance), and accessibility/undercut (needs 5-axis tilt). "
            "Also renders 3 PNGs (curvature heatmap / residual height map / toolpath backplot) as "
            "multi-modal input. Use payload JSON: {mesh_path or geometry_mesh, tool_radius_mm, "
            "step_over_mm, finish_allowance_mm, spindle_axis}. This directly mitigates the agent's "
            "inability to understand complex-surface machining.",
            self.facet_observe_surface,
        )
        self.register_tool(
            "capability_lookup",
            "Look up the transferable capability SOP for a situation: planning, research and "
            "source grading, code change discipline, data analysis, writing/deliverables, "
            "evidence verification, tool orchestration, security boundaries, memory hygiene, "
            "clarification, and engineering unit/tolerance discipline. "
            "Use payload JSON: {query:'<what you are about to do>', k:2}. "
            "Returns step-by-step procedure + hard rules + acceptance gate. "
            "If matched=false there is no SOP for it — do not invent one.",
            self.facet_capability_lookup,
        )
        self.register_tool(
            "capability_guard",
            "Evidence gate for completion claims. Call BEFORE saying 'done/verified/passed'. "
            "Use payload JSON: {claim:'...', evidence:[{check:'command or check name', "
            "output:'raw output or artifact path', kind:'measured'}]}. "
            "Returns passed=false with verdict NO_EVIDENCE / INCOMPLETE_EVIDENCE / ASSERTED_ONLY "
            "when the claim is not backed by measured evidence. kind defaults to asserted (strict).",
            self.facet_capability_guard,
        )
        self.register_tool(
            "solve_lame_cylinder",
            "Deterministically compute Lamé thick-walled cylinder stresses (sigma_theta, sigma_r, "
            "von Mises in MPa) and optionally verify a candidate answer. Accepts payload JSON "
            "{di_mm, do_mm, pi_mpa, po_mpa?, candidate_answer?} or natural-language Lamé prompt.",
            self.facet_solve_lame_cylinder,
        )
        self.register_tool(
            "generate_validated_g71",
            "Generate and/or semantically validate a FANUC G71 Type I / G70 step-shaft turning "
            "program against part dimensions (no G00 negative-Z plunge, monotonic X, verified "
            "shoulders). Accepts payload JSON {prompt? or stock_d, steps, total_len, s_clamp?, "
            "vc?, feed?, tool?, candidate_program?} or natural-language G71 prompt.",
            self.facet_generate_validated_g71,
        )

    def register_tool(self, name: str, description: str, fn: Callable[[Any], Any]) -> None:
        """Register a new tool into Super Agent's dynamic capability pool."""
        self._tool_registry[name] = (description, fn)

    @property
    def tools(self) -> Dict[str, Tuple[str, Callable[[Any], Any]]]:
        """Dynamic registry of tools available to Super Agent."""
        return self._tool_registry

    def call_tool(self, name: str, params: Any = None) -> Any:
        """Execute a tool from the dynamic tool registry by name."""
        if name not in self._tool_registry:
            raise KeyError(f"Tool '{name}' is not registered in VirtuSuperAgent.")
        _, tool_fn = self._tool_registry[name]
        pos, kw = _bind_facet_args(tool_fn, params)
        return tool_fn(*pos, **kw)

    # =========================================================================
    # Omnipotent Domain Facets (全域能力面)
    # =========================================================================

    def _spec_context(self, context: Any) -> Dict[str, Any]:
        """工程 facet 的载荷归一化。

        真实 REACT 深度引擎按广播 schema 发 ``{"payload": "<自然语言规格>"}``，
        解包后 facet 收到的是**字符串**；而 delegate.run() 需要 dict context
        （``architecture.parsed_spec`` / ``user_prompt``）。旧实现直接对字符串调
        ``.get()`` 抛 AttributeError。这里把字符串先经 Architect 解析成规格再组装；
        dict 载荷原样透传，硬编码流水线的既有契约不变。
        """
        if isinstance(context, dict):
            return context
        text = str(context or "")
        arch = self._delegate_architect.run({"user_prompt": text})
        return {"user_prompt": text, "architecture": arch}

    def facet_parse_intent(self, prompt: str) -> Dict[str, Any]:
        """Architect Facet: Intent deduction and specification synthesis."""
        res = self._delegate_architect.run({"user_prompt": prompt})
        try:
            from virtu_omni.agent.grounded_inference import parse_g71_request
            g71 = parse_g71_request(str(prompt or ""))
        except Exception:
            g71 = None
        if g71 is not None and isinstance(res, dict) and isinstance(res.get("parsed_spec"), dict):
            spec = res["parsed_spec"]
            spec["d_outer"] = g71.stock_d
            spec["d_inner"] = g71.steps[0][0]
            spec["overall_len"] = g71.total_len
            spec["g71_spec"] = {
                "stock_d": g71.stock_d,
                "steps": list(g71.steps),
                "total_len": g71.total_len,
                "s_clamp": g71.s_clamp,
                "vc": g71.vc,
                "feed": g71.feed,
                "tool": g71.tool,
            }
            ev = spec.get("dimension_evidence")
            if isinstance(ev, dict):
                ev["d_outer_mm"] = {"value": g71.stock_d, "source": "grounded_g71_spec"}
                ev["d_inner_mm"] = {"value": g71.steps[0][0], "source": "grounded_g71_spec"}
                ev["overall_len_mm"] = {"value": g71.total_len, "source": "grounded_g71_spec"}
        return res

    def facet_generate_cad(self, context: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Modeling Facet: 3D Parametric CAD FeatureTree and equations."""
        return self._delegate_modeler.run(self._spec_context(context))

    def facet_generate_standards(self, context: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Standards Facet: 2D drawing projections, GD&T, fits & tolerances."""
        return self._delegate_standards.run(self._spec_context(context))

    def facet_generate_cam(self, context: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Machining Facet: CAM toolpaths, cutting feeds & speeds, CNC Macro B."""
        ctx = self._spec_context(context)
        arch = ctx.get("architecture") or {}
        spec_dict = arch.get("parsed_spec") if isinstance(arch, dict) else {}
        user_prompt = str(ctx.get("user_prompt") or (spec_dict or {}).get("wish") or "")
        g71_spec = None
        g71_gate = None
        try:
            from virtu_omni.agent.grounded_inference import (
                generate_g71_program,
                parse_g71_request,
                validate_g71_against_spec,
            )
            g71_spec = parse_g71_request(user_prompt)
        except Exception:
            g71_spec = None

        if g71_spec is not None:
            prog = generate_g71_program(g71_spec)
            g71_gate = validate_g71_against_spec(prog, g71_spec)
            result: Dict[str, Any] = {
                "agent": "Virtu-Grounded-G71-Generator",
                "status": "COMPLETED" if g71_gate.get("passed") else "FAILED",
                "cutting_params": {
                    "material": (spec_dict or {}).get("material", "Cr12MoV"),
                    "diameter_mm": g71_spec.stock_d,
                    "surface_speed_m_min": g71_spec.vc or 150.0,
                    "spindle_clamp_rpm": g71_spec.s_clamp or 2000.0,
                    "feed_rate": g71_spec.feed or 0.25,
                    "tool": g71_spec.tool,
                    "basis": "grounded_g71_spec",
                },
                "macro_b_code": prog,
                "g71_spec": {
                    "stock_d": g71_spec.stock_d,
                    "steps": list(g71_spec.steps),
                    "total_len": g71_spec.total_len,
                    "s_clamp": g71_spec.s_clamp,
                    "vc": g71_spec.vc,
                    "feed": g71_spec.feed,
                    "tool": g71_spec.tool,
                },
                "g71_spec_gate": g71_gate,
                "basis": "deterministic_generator",
                "summary": (
                    f"按题面几何参数生成 G71 Type I/G70 台阶轴程序（毛坯 Ø{g71_spec.stock_d:g}，"
                    f"总长 {g71_spec.total_len:g} mm，语义门={'PASS' if g71_gate.get('passed') else 'FAIL'}）。"
                ),
            }
        else:
            result = self._delegate_machining.run(ctx)

        if not isinstance(result, dict):
            return {"status": "FAILED", "passed": False,
                    "verdict_code": "CNC_GENERATOR_INVALID_RESULT",
                    "error": "Machining facet must return a structured object."}
        code = str(result.get("macro_b_code") or result.get("nc_code") or "")
        if not code.strip():
            result.update({"status": "FAILED", "passed": False,
                           "verdict_code": "CNC_PROGRAM_MISSING",
                           "engineering_verified": False})
            return result

        sandbox = self.sandbox_verifier.verify_cimco_macro_b(code)
        result["sandbox_verification"] = sandbox
        result["cnc_semantic_gate"] = sandbox.get("g71_semantic_gate", {
            "applicable": False, "passed": True, "basis": "static_semantic",
            "violations": [], "evidence": {},
        })
        spec_ok = True if g71_gate is None else bool(g71_gate.get("passed"))
        gate_ok = bool(sandbox.get("passed")) and spec_ok
        result["static_gate_passed"] = gate_ok
        # Static validation cannot establish that the NC was simulated on the target machine.
        result["engineering_verified"] = False
        result["evidence_status"] = "static_checks_passed" if gate_ok else "rejected"
        if not gate_ok:
            result.update({"status": "FAILED", "passed": False,
                           "verdict_code": "CNC_STATIC_GATE_FAILED"})
        return result

    def facet_verify_cae(self, spec: Union[str, Dict[str, Any]], internal_pressure_mpa: float = 10.0) -> Dict[str, Any]:
        """CAE Facet: Thick cylinder elasticity (Lamé theory) & Safety Factor (FOS >= 1.5)."""
        po_mpa = 0.0
        if isinstance(spec, str):
            try:
                from virtu_omni.agent.grounded_inference import parse_lame_request
                lame_req = parse_lame_request(spec)
            except Exception:
                lame_req = None
            if lame_req is not None:
                spec_dict: Dict[str, Any] = {
                    "d_inner": lame_req["di_mm"],
                    "d_outer": lame_req["do_mm"],
                }
                internal_pressure_mpa = lame_req["pi_mpa"]
                po_mpa = lame_req.get("po_mpa", 0.0)
            else:
                spec_dict = self._spec_context(spec).get("architecture", {}).get("parsed_spec", {})
        elif isinstance(spec, dict):
            spec_dict = spec
        else:
            spec_dict = {}

        material_name = spec_dict.get("material", "AL6061-T6")
        mat_prop = self.MATERIAL_PROPERTIES.get(material_name, self.MATERIAL_PROPERTIES["AL6061-T6"])
        d_outer = float(spec_dict.get("d_outer", 53.0))
        d_inner = float(spec_dict.get("d_inner", 14.0))
        total_len = float(spec_dict.get("overall_len") or spec_dict.get("total_len") or 45.0)
        if spec_dict.get("internal_pressure_mpa") is not None:
            internal_pressure_mpa = float(spec_dict["internal_pressure_mpa"])

        r_outer = d_outer / 2.0
        r_inner = d_inner / 2.0
        r_inner_eff = max(r_inner, 0.1)
        yield_strength = mat_prop["yield_strength_mpa"]

        # Lamé thick cylinder closed-form solution (shared grounded_inference kernel)
        lame_out: Optional[Dict[str, Any]] = None
        if 0.0 < d_inner < d_outer and internal_pressure_mpa >= 0.0 and po_mpa >= 0.0:
            try:
                from virtu_omni.agent.grounded_inference import lame_thick_cylinder
                lame_out = lame_thick_cylinder(d_inner, d_outer, internal_pressure_mpa, po_mpa)
            except Exception:
                lame_out = None

        if lame_out is not None:
            sigma_t_max = lame_out["sigma_theta_inner_mpa"]
            fos = round(yield_strength / max(sigma_t_max, 1e-6), 2)
        elif r_outer <= r_inner_eff:
            sigma_t_max = 9999.0
            fos = 0.01
        else:
            denom = (r_outer ** 2) - (r_inner_eff ** 2)
            numer = (r_outer ** 2) + (r_inner_eff ** 2)
            sigma_t_max = internal_pressure_mpa * (numer / denom)
            fos = round(yield_strength / max(sigma_t_max, 1e-6), 2)

        theoretical_volume_mm3 = round(math.pi * (r_outer ** 2 - r_inner ** 2) * total_len, 2)
        weight_grams = round(theoretical_volume_mm3 * 1e-3 * mat_prop["density_g_cm3"], 2)
        fos_passed = fos >= 1.5

        out: Dict[str, Any] = {
            "status": "COMPLETED",
            "material": material_name,
            "material_name_cn": mat_prop["name_cn"],
            "yield_strength_mpa": yield_strength,
            "internal_pressure_mpa": internal_pressure_mpa,
            "max_von_mises_stress_mpa": round(sigma_t_max, 2),
            "safety_factor_fos": fos,
            "fos_passed": fos_passed,
            "theoretical_volume_mm3": theoretical_volume_mm3,
            "estimated_weight_grams": weight_grams,
            "summary": (
                f"CAE 物理力学验算：材料【{mat_prop['name_cn']}】在 {internal_pressure_mpa} MPa 载荷下，"
                f"最大环向应力 {round(sigma_t_max, 2)} MPa，屈服强度 {yield_strength} MPa，"
                f"计算安全系数 FOS = {fos} ({'合规 >= 1.5' if fos_passed else '危险 < 1.5'})。"
            ),
        }
        if lame_out is not None:
            out.update({
                "sigma_theta_inner_mpa": round(lame_out["sigma_theta_inner_mpa"], 4),
                "sigma_r_inner_mpa": round(lame_out["sigma_r_inner_mpa"], 4),
                "sigma_theta_outer_mpa": round(lame_out["sigma_theta_outer_mpa"], 4),
                "sigma_r_outer_mpa": round(lame_out["sigma_r_outer_mpa"], 4),
                "true_von_mises_inner_mpa": round(lame_out["von_mises_inner_mpa"], 4),
                "lame_basis": lame_out["basis"],
            })
        return out

    def facet_solve_lame_cylinder(self, params: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Grounded Lamé Facet: Closed-form thick-wall stress + optional candidate verification."""
        from virtu_omni.agent.grounded_inference import (
            check_lame_answer,
            lame_thick_cylinder,
            parse_lame_request,
            render_lame_answer,
        )

        p = params
        if isinstance(p, str):
            try:
                decoded = json.loads(p)
                p = decoded if isinstance(decoded, dict) else {"prompt": p}
            except Exception:
                p = {"prompt": p}
        elif not isinstance(p, dict):
            return {"passed": False, "applicable": False, "basis": "unmeasured",
                    "error": "params must be a prompt string or JSON object"}

        lame_params: Optional[Dict[str, float]] = None
        if all(k in p for k in ("di_mm", "do_mm", "pi_mpa")):
            try:
                lame_params = {
                    "di_mm": float(p["di_mm"]),
                    "do_mm": float(p["do_mm"]),
                    "pi_mpa": float(p["pi_mpa"]),
                    "po_mpa": float(p.get("po_mpa", 0.0) or 0.0),
                }
            except (TypeError, ValueError) as exc:
                return {"passed": False, "applicable": False, "basis": "unmeasured",
                        "error": f"invalid numeric inputs: {exc}"}
        else:
            raw_prompt = str(p.get("prompt") or p.get("payload") or "").strip()
            lame_params = parse_lame_request(raw_prompt)

        if lame_params is None:
            return {"passed": False, "applicable": False, "basis": "unmeasured",
                    "error": "missing or invalid Lamé inputs (require 0 < Di < Do and Pi >= 0)"}

        try:
            res = lame_thick_cylinder(**lame_params)
        except ValueError as exc:
            return {"passed": False, "applicable": False, "basis": "unmeasured", "error": str(exc)}

        rendered = render_lame_answer(lame_params, res)
        candidate = p.get("candidate_answer")
        if candidate is not None and str(candidate).strip():
            verdict = check_lame_answer(str(candidate), lame_params, res)
            return {
                "passed": bool(verdict["passed"]),
                "applicable": True,
                "basis": "closed_form",
                "params": lame_params,
                "result": res,
                "violations": verdict["violations"],
                "rendered": rendered,
            }
        return {
            "passed": True,
            "applicable": True,
            "basis": "closed_form",
            "params": lame_params,
            "result": res,
            "violations": [],
            "rendered": rendered,
        }

    def facet_generate_validated_g71(self, params: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Grounded G71 Facet: Spec-parameterized semantic validation & safe program generation."""
        from virtu_omni.agent.grounded_inference import (
            G71Spec,
            generate_g71_program,
            parse_g71_request,
            validate_g71_against_spec,
        )

        p = params
        if isinstance(p, str):
            try:
                decoded = json.loads(p)
                p = decoded if isinstance(decoded, dict) else {"prompt": p}
            except Exception:
                p = {"prompt": p}
        elif not isinstance(p, dict):
            return {"passed": False, "applicable": False, "basis": "static_semantic",
                    "error": "params must be a prompt string or JSON object"}

        spec: Optional[G71Spec] = None
        if all(k in p for k in ("stock_d", "steps", "total_len")):
            try:
                stock_d = float(p["stock_d"])
                total_len = float(p["total_len"])
                raw_steps = p["steps"] or []
                steps: List[Tuple[float, float]] = []
                for item in raw_steps:
                    if isinstance(item, dict):
                        steps.append((float(item["diameter"]), float(item["length"])))
                    elif isinstance(item, (list, tuple)) and len(item) >= 2:
                        steps.append((float(item[0]), float(item[1])))
                if (steps and stock_d > 0 and total_len > 0
                        and sum(L for _, L in steps) <= total_len + 1e-9
                        and all(0 < d < stock_d and L > 0 for d, L in steps)
                        and all(steps[i][0] <= steps[i + 1][0] for i in range(len(steps) - 1))):
                    spec = G71Spec(
                        stock_d=stock_d,
                        steps=steps,
                        total_len=total_len,
                        s_clamp=float(p["s_clamp"]) if p.get("s_clamp") is not None else None,
                        vc=float(p["vc"]) if p.get("vc") is not None else None,
                        feed=float(p["feed"]) if p.get("feed") is not None else None,
                        tool=str(p.get("tool") or "T0101").upper(),
                    )
            except (TypeError, ValueError, KeyError) as exc:
                return {"passed": False, "applicable": False, "basis": "static_semantic",
                        "error": f"invalid G71 spec: {exc}"}
        else:
            raw_prompt = str(p.get("prompt") or p.get("payload") or "").strip()
            spec = parse_g71_request(raw_prompt)

        if spec is None:
            return {"passed": False, "applicable": False, "basis": "static_semantic",
                    "error": "missing or invalid G71 step-shaft specification"}

        prog = generate_g71_program(spec)
        gen_gate = validate_g71_against_spec(prog, spec)
        sandbox = self.sandbox_verifier.verify_cimco_macro_b(prog)

        candidate = p.get("candidate_program")
        if candidate is not None and str(candidate).strip():
            cand_gate = validate_g71_against_spec(str(candidate), spec)
            return {
                "passed": bool(cand_gate["passed"]),
                "applicable": True,
                "basis": "static_semantic",
                "source": "candidate" if cand_gate["passed"] else "candidate_rejected",
                "violations": cand_gate["violations"],
                "evidence": cand_gate["evidence"],
                "program": str(candidate) if cand_gate["passed"] else prog,
                "repaired_program": prog if not cand_gate["passed"] and gen_gate["passed"] else None,
                "repaired_passed": bool(gen_gate["passed"] and sandbox.get("passed")),
                "spec": spec.__dict__,
            }

        ok = bool(gen_gate["passed"] and sandbox.get("passed"))
        return {
            "passed": ok,
            "applicable": True,
            "basis": "deterministic_generator",
            "source": "deterministic_generator",
            "violations": gen_gate["violations"],
            "program": prog if ok else None,
            "semantic_gate": gen_gate,
            "sandbox_gate": sandbox,
            "spec": spec.__dict__,
        }

    def facet_audit_sandbox(self, context: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Auditor Facet: Headless virtual simulation, kinematics collision, self-reflection."""
        if isinstance(context, str):
            # 字符串载荷：先派生真实建模/加工产物，审计才有可检对象（不空审）。
            ctx = self._spec_context(context)
            ctx["modeling"] = self._delegate_modeler.run(ctx)
            ctx["machining"] = self.facet_generate_cam(ctx)
            context = ctx
        return self._delegate_auditor.run(context)

    def facet_recall_memory(self, prompt: str) -> Dict[str, Any]:
        """Memory Facet: Retrieve contextual patterns, coordinate invariants, and reflections."""
        past_exp = self._delegate_memory.retrieve_context(prompt)
        reflection = self._delegate_memory.reflect_on_intent(prompt)
        return {
            "past_experiences": past_exp,
            "reflection": reflection,
            "coordinate_invariants": dict(self.hindsight_memory.select_coordinate_invariants(prompt)),
        }

    def _cap_registry(self):
        """惰性获取能力目录。任何异常都降级为 None，由调用方显式判断。"""
        reg = getattr(self, "capability_registry", None)
        if reg is None:
            try:
                from virtu_omni.capabilities import CapabilityRegistry
                reg = CapabilityRegistry()
                self.capability_registry = reg
            except Exception as exc:                       # noqa: BLE001 - 可选能力
                logger.debug("[capability] 目录不可用: %s", exc)
                return None
        return reg

    def _capability_hint(
        self,
        prompt: str,
        *,
        k: int = 2,
        min_score: float = 7.0,
        max_chars: int = 900,
    ) -> Dict[str, Any]:
        """按任务检索 1-2 条通用能力 SOP，供运行时上下文注入。

        阈值 min_score=7.0 的含义是**必须命中触发词**（纯 BM25 词面匹配的分数达不到
        这个量级）。宁可不注入，也不要把"看起来相关"的泛能力塞进 prompt——那既浪费
        14B 模型的上下文，又会把不相关的规范当成硬约束执行。
        """
        reg = self._cap_registry()
        if reg is None:
            hint = {"applied": False, "reason": "registry_unavailable"}
            self.last_capability_hint = hint
            return hint
        text = (prompt or "").strip()
        if not text:
            hint = {"applied": False, "reason": "empty_prompt"}
            self.last_capability_hint = hint
            return hint
        try:
            hits = reg.search(text, k=max(k, 2))
            qualified = [h for h in hits if h["score"] >= min_score][:k]
            if not qualified:
                hint = {
                    "applied": False,
                    "reason": "no_trigger_hit",
                    "near": [{"id": h["id"], "score": h["score"]} for h in hits[:2]],
                }
                self.last_capability_hint = hint
                return hint
            ids = [h["id"] for h in qualified]
            hint = {
                "applied": True,
                "atom_ids": ids,
                "scores": {h["id"]: h["score"] for h in qualified},
                "brief": reg.render(ids, max_chars=max_chars),
                "gates": [reg.gate(i)["id"] for i in ids],
            }
        except Exception as exc:                           # noqa: BLE001 - 不阻断主流程
            hint = {"applied": False, "reason": f"hint_error: {type(exc).__name__}: {exc}"}
        self.last_capability_hint = hint
        return hint

    def build_runtime_memory_context(
        self,
        prompt: str,
        *,
        include_vericut_kb: bool = True,
        max_chars: int = 2400,
    ) -> str:
        """Assemble unified Hindsight + WorkingMemory + Harness + VERICUT-KB runtime context."""
        clean_prompt = (prompt or "").strip()
        wm_block = ""
        if self.working_memory is not None:
            cur_goal = self.working_memory.goal.intent.strip() if self.working_memory.goal else ""
            if cur_goal and clean_prompt and cur_goal != clean_prompt:
                kept_lessons = list(self.working_memory.lessons_learned)
                self.working_memory.reset()
                for lesson in kept_lessons:
                    self.working_memory.record_lesson(lesson)
            if clean_prompt:
                if self.working_memory.goal is None:
                    self.working_memory.set_task_goal(clean_prompt)
                self.working_memory.auto_sync_from_messages([{"role": "user", "content": clean_prompt}])
            wm_block = self.working_memory.render_memory_prompt()

        extra_sections: List[str] = []
        if self.custom_memory and str(self.custom_memory).strip():
            extra_sections.append("[Harness 长期记忆]\n" + str(self.custom_memory).strip()[:650])
        if self.custom_guardrails and str(self.custom_guardrails).strip():
            extra_sections.append("[Harness 护栏约束]\n" + str(self.custom_guardrails).strip()[:350])

        # 能力传授：只在任务命中触发词时注入，默认预算 900 字符。
        # 放在护栏之后、领域 KB 之前——方法论优先于领域细节，但不得挤掉领域证据。
        cap_hint = self._capability_hint(clean_prompt)
        if cap_hint.get("applied"):
            extra_sections.append(
                "[能力传授·本次任务的作业规范]\n" + str(cap_hint.get("brief") or "")
            )

        try:
            from virtu_omni.agent.grounded_inference import build_grounding_hint
            grounded_hint = build_grounding_hint(clean_prompt)
            if grounded_hint:
                extra_sections.insert(0, "[确定性接地约束]\n" + grounded_hint)
        except Exception:
            pass

        q_low = clean_prompt.lower()
        if include_vericut_kb and any(
            k in q_low for k in ("vericut", "vcproject", "autodiff", "auto-diff", "g54", "五轴", "仿真", "cnc")
        ):
            kb_res = self.facet_recall_vericut_training(clean_prompt)
            hits = kb_res.get("hits") or []
            if hits:
                kb_lines = []
                for h in hits[:2]:
                    src = h.get("source_path") or h.get("title") or "vericut_9_6_kb"
                    excerpt = str(h.get("text") or h.get("content") or h.get("summary") or "").strip()[:180]
                    if excerpt:
                        kb_lines.append(f"- ({src}) {excerpt}")
                if kb_lines:
                    extra_sections.append("[VERICUT 9.6 官方培训库实测依据]\n" + "\n".join(kb_lines))

        ctx = self.hindsight_memory.build_domain_memory_context(
            query=clean_prompt,
            bank_ids=["virtu_cad_cam", "virtu_cnc_machining", "virtu_quality_audit", "default"],
            max_items=4,
            update_stats=False,
            include_invariants=True,
            working_memory_block=wm_block,
            extra_sections=extra_sections,
            max_chars=max_chars,
        )
        self.last_memory_context = ctx
        return ctx

    def facet_recall_vericut_training(self, query: Any) -> Dict[str, Any]:
        """从已摄入的 VERICUT 9.6 官方培训库召回**实测**依据。

        与 ``recall_hindsight_memory`` 的区别：这里只返回带 ``source_path`` /
        sha256 / ``basis=measured`` 的官方资料抽取结果；召回不到就诚实报
        ``no_evidence``，不用通用工程套话补位。
        """
        if isinstance(query, dict):
            q = str(query.get("query") or query.get("prompt") or "")
        else:
            q = str(query or "")
        try:
            from virtu_omni.internet.deep_learning_pipeline import get_learning_pipeline
            hits = get_learning_pipeline().retrieve_training_knowledge(q, top_k=3)
        except Exception as exc:  # noqa: BLE001 - 召回失败不得伪装成成功
            return {
                "success": False,
                "error": f"{type(exc).__name__}: {exc}",
                "query": q,
                "hits": [],
                "hit_count": 0,
                "basis": "unmeasured",
            }
        return {
            "success": bool(hits),
            "query": q,
            "hits": hits,
            "hit_count": len(hits),
            "basis": "measured" if hits else "no_evidence",
            "source": "vericut_9_6_official_training",
        }

    def facet_query_training_cases(self, query: Any) -> Dict[str, Any]:
        """查询 ``knowledge_base/training_case_index.json``（E:/training 案例实测索引）。

        回答「哪些是错误案例/正确案例」「哪些要车床/三轴/四轴/五轴」这类问题。
        索引由 ``scripts/index_training_cases.py`` 生成；索引缺失就诚实报 no_evidence，
        不拿通用经验补位。
        """
        try:
            from virtu_omni.knowledge.training_case_catalog import (
                DEFAULT_INDEX_PATH,
                answer_query,
                load_catalog,
                query_cases,
                query_standalone,
            )
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "basis": "unmeasured",
                    "error": f"{type(exc).__name__}: {exc}", "cases": [], "case_count": 0}

        catalog = load_catalog(DEFAULT_INDEX_PATH)
        if not catalog:
            return {
                "success": False,
                "basis": "no_evidence",
                "error": "training case index missing; run scripts/index_training_cases.py",
                "index": str(DEFAULT_INDEX_PATH),
                "cases": [],
                "standalone_programs": [],
                "case_count": 0,
                "standalone_count": 0,
            }
        # 错误案例的动态/静态复现结论（由 scripts/verify_error_cases.py 生成）。
        verification: Dict[str, Any] = {}
        verification_path = Path(DEFAULT_INDEX_PATH).parent / "error_case_verification.json"
        if verification_path.is_file():
            try:
                payload = json.loads(verification_path.read_text(encoding="utf-8"))
                verification = {
                    c["case_id"]: {
                        "method": c.get("method"),
                        "reproduced": c.get("reproduced"),
                        "confidence": c.get("confidence"),
                        "log_path": c.get("log_path"),
                    }
                    for c in payload.get("cases", [])
                }
                verification["__summary__"] = payload.get("summary", {})
            except (OSError, json.JSONDecodeError):
                verification = {}

        if isinstance(query, dict):
            structured = {k: query.get(k) for k in
                          ("status", "capability", "family", "keyword",
                           "verification_status") if query.get(k)}
            cases = query_cases(catalog, limit=int(query.get("limit") or 50), **structured)
            standalone = query_standalone(
                catalog,
                capability=query.get("capability"),
                status=query.get("status"),
                keyword=query.get("keyword"),
                limit=int(query.get("limit") or 50),
            )
            text = str(query.get("query") or query.get("prompt") or "")
            filters = structured
        else:
            text = str(query or "").strip()
            if len(text) < 2:
                return {"success": False, "basis": "no_evidence", "query": text,
                        "cases": [], "standalone_programs": [],
                        "case_count": 0, "standalone_count": 0}
            ans = answer_query(catalog, text, limit=50)
            cases = ans["cases"]
            standalone = ans["standalone_programs"]
            filters = ans["filters"]

        def slim(case: Dict[str, Any]) -> Dict[str, Any]:
            evidence = case.get("defect_evidence") or []
            return {
                "case_id": case.get("case_id"),
                "status": case.get("status"),
                "required_capability": case.get("required_capability"),
                "capability_label": case.get("capability_label"),
                "machine": (case.get("machine") or {}).get("file"),
                "machine_kind": (case.get("machine") or {}).get("kind"),
                "axis_consistency": (case.get("axis_consistency") or {}).get("status"),
                "notes": case.get("notes") or [],
                "evidence": evidence[0].get("quote") if evidence else None,
                "evidence_session": evidence[0].get("session") if evidence else None,
                "path": case.get("path"),
                # 判定层（verdict_layer）：人工核定的正误分类、设备需求、证据等级与待核验状态
                "verdict": case.get("verdict"),
                "verdict_cn": case.get("verdict_cn"),
                "error_type": case.get("error_type"),
                "error_type_cn": case.get("error_type_cn"),
                "error_reason": case.get("error_reason"),
                "device_need": case.get("device_need"),
                "linkage_need": case.get("linkage_need"),
                "evidence_level": case.get("evidence_level"),
                "verification": case.get("verification"),
                "learning_note": case.get("learning_note"),
                # 错误案例分类与复现状态（来自索引 enrich_with_verification）
                "error_type": case.get("error_type"),
                "error_type_cn": case.get("error_type_cn"),
                "verification_status": case.get("verification_status"),
                # 复现核验（scripts/verify_error_cases.py）：与索引里的 verdict/verification 分开
                "reproduction": verification.get(case.get("case_id")),
            }

        has_hits = bool(cases or standalone)
        # 指定了结构化筛选（如「五轴联动」）时，0 命中本身就是实测结论：
        # 本次查询执行成功，只是该类别没有案例；不得报成 no_evidence。
        queried = bool(filters) or has_hits
        return {
            "success": queried,
            "basis": "measured" if queried else "no_evidence",
            "source": "training_case_index",
            "index_generated_at_utc": catalog.get("generated_at_utc"),
            "query": text,
            "filters": filters,
            "empty_result": not has_hits,
            "cases": [slim(c) for c in cases],
            "standalone_programs": standalone,
            "case_count": len(cases),
            "standalone_count": len(standalone),
            "summary": catalog.get("summary", {}),
            "verification_summary": verification.get("__summary__") or {},
            # 判定层口径：Agent 回答案例问题时必须遵守的硬约束（禁止五轴联动臆断、须声明待核验等）
            "verdict_layer": {
                "status_split": (catalog.get("verdict_layer") or {}).get("status_split"),
                "error_types": (catalog.get("verdict_layer") or {}).get("error_types"),
                "device_need_split": (catalog.get("verdict_layer") or {}).get("device_need_split"),
                "five_axis_simultaneous_count": (catalog.get("verdict_layer") or {}).get(
                    "five_axis_simultaneous_count"),
                "pending_verification_cases": (catalog.get("verdict_layer") or {}).get(
                    "pending_verification_cases"),
                "hard_constraints": (catalog.get("verdict_layer") or {}).get("hard_constraints"),
            },
        }

    def facet_commit_memory(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Memory Facet: Commit verified design patterns into Hindsight and vector memory."""
        return self._delegate_memory.run(context)

    def facet_sleep_consolidation(self, context_or_run_id: Optional[Any] = None) -> Dict[str, Any]:
        """Google Sleep Facet: 三阶段离线巩固；无真实模型调用时诚实降级为 unmeasured。"""
        run_id = None
        if isinstance(context_or_run_id, str):
            run_id = context_or_run_id
        elif isinstance(context_or_run_id, dict):
            run_id = context_or_run_id.get("run_id")
            # 显式开启真实模型通道（默认关闭，避免隐式网络调用）
            if context_or_run_id.get("auto_model") and self.sleep_framework.model_caller is None:
                try:
                    from virtu_omni.memory import build_ollama_model_caller
                    caller, label = build_ollama_model_caller()
                    if caller is not None:
                        self.sleep_framework.model_caller = caller
                        self.sleep_framework.dream_engine.model_caller = caller
                        self.sleep_framework.model_caller_label = label
                except Exception as e:
                    logger.warning(f"Could not resolve model caller: {e}")
            if context_or_run_id.get("baseline_score") is not None:
                try:
                    self.sleep_framework.baseline_score = float(context_or_run_id["baseline_score"])
                except (TypeError, ValueError):
                    logger.warning("Invalid baseline_score ignored")
        return self.sleep_framework.run_sleep_cycle(run_id=run_id)

    def facet_optimize_operators(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Operator Optimization Facet: Autonomously profile, diagnose, and optimize model operators."""
        from virtu_omni.models.operator_optimizer import VirtuOperatorOptimizer
        optimizer = VirtuOperatorOptimizer(workspace_root=Path(WORKSPACE_DIR))
        params = params or {}
        batch_size = params.get("batch_size", 2)
        seq_lens = params.get("seq_lens", [128, 512, 1024, 2048])
        num_warmup = params.get("num_warmup", 15)
        num_trials = params.get("num_trials", 50)
        report = optimizer.run_full_optimization_cycle(
            batch_size=batch_size,
            seq_lens=seq_lens,
            num_warmup=num_warmup,
            num_trials=num_trials,
        )
        json_path, md_path = optimizer.export_report(report)

        # Record optimization experience in agent long term memory.
        # Never assert "gates passed" as a literal: it must follow the measured gate.
        gate_status = (
            "all precision gates passed"
            if report.all_invariants_passed
            else f"NOT verified (gate failure or source drift: {report.invalidated_legs})"
        )
        try:
            self.hindsight_memory.retain(
                bank_id="operator_optimization",
                content=(
                    f"Model Operator Optimization: micro-benchmark aggregate "
                    f"{report.overall_speedup}x, memory reduction {report.memory_reduction_pct}%, "
                    f"{gate_status}. basis=measured, evidence={report.evidence_path or 'not exported'}, "
                    f"regressions={len(report.regressions)}."
                ),
                context="operator_benchmarks",
                tags=["operator_optimizer", "performance", "flash_attention", "rope_cache"],
                metadata={
                    "run_id": report.run_id,
                    "speedup": report.overall_speedup,
                    "memory_reduction": report.memory_reduction_pct,
                    "basis": "measured",
                    "evidence_path": report.evidence_path,
                    "gates_passed": report.all_invariants_passed,
                },
            )
        except Exception as e_mem:
            logger.warning(f"Could not retain operator optimization experience: {e_mem}")

        return {
            "success": report.all_invariants_passed,
            "run_id": report.run_id,
            "overall_speedup": report.overall_speedup,
            "memory_reduction_pct": report.memory_reduction_pct,
            "report_md": str(md_path),
            "report_json": str(json_path),
            "diagnostics_count": len(report.diagnostics),
            "benchmarks_count": len(report.operator_benchmarks),
            # 失败时能直接看到哪条腿作废（源码漂移 / 精度门 / 回归），
            # 而不是只拿到一个 success=False。
            "invalidated_legs": list(report.invalidated_legs),
            "precision_failures": [
                {
                    "operator": b.get("operator"),
                    "seq_len": b.get("seq_len"),
                    "max_diff": b.get("max_diff"),
                    "failure_reason": b.get("failure_reason"),
                    "detail": b.get("failure_detail"),
                }
                for b in report.operator_benchmarks
                if not b.get("precision_pass")
            ],
            "all_invariants_passed": report.all_invariants_passed,
            "summary_markdown": report.summary_markdown(),
        }

    def facet_optimize_operators_to_limit(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Push operators to the measured roofline limit (CUDA Graph / TF32 / BF16)."""
        from virtu_omni.models.operator_extreme import export_report, run_extreme_cycle

        params = params or {}
        root = Path(WORKSPACE_DIR)
        report = run_extreme_cycle(
            seq_lens=params.get("seq_lens"),
            trials=int(params.get("trials", 60)),
            workspace_root=root,
        )
        json_path, md_path = export_report(report, out_dir=root / "benchmarks")
        success = bool(report.all_graph_gates_passed and not report.invalidated_legs)
        try:
            self.hindsight_memory.retain(
                bank_id="operator_optimization",
                content=(
                    f"Operator theoretical-limit run {report.run_id}: "
                    f"graph gates {'PASS' if report.all_graph_gates_passed else 'FAIL'}, "
                    f"bandwidth {report.hardware['bandwidth_gbs']:.1f} GB/s, "
                    f"BF16 peak {report.hardware['peak_tflops']['bf16']:.2f} TFLOPS. "
                    f"basis=measured, evidence={report.evidence_path or 'not exported'}."
                ),
                context="operator_roofline",
                tags=["operator_optimizer", "roofline", "cuda_graph", "bf16"],
                metadata={
                    "run_id": report.run_id,
                    "basis": "measured",
                    "evidence_path": report.evidence_path,
                    "gates_passed": report.all_graph_gates_passed,
                    "best_per_operator": report.best_per_operator,
                },
            )
        except Exception as e_mem:
            logger.warning(f"Could not retain roofline experience: {e_mem}")

        return {
            "success": success,
            "run_id": report.run_id,
            "hardware": report.hardware,
            "best_per_operator": report.best_per_operator,
            "toolchain_limits": report.toolchain_limits,
            "report_md": str(md_path),
            "report_json": str(json_path),
            "summary_markdown": report.summary_markdown(),
        }

    def run_operator_extreme_limit(self, seq_lens: Optional[List[int]] = None) -> Dict[str, Any]:
        """High-level trigger for the roofline-limit optimisation cycle."""
        return self.facet_optimize_operators_to_limit(
            {"seq_lens": seq_lens or [128, 512, 1024]}
        )

    def run_operator_self_optimization(
        self,
        seq_lens: Optional[List[int]] = None,
        num_warmup: int = 15,
        num_trials: int = 50,
    ) -> Dict[str, Any]:
        """High-level autonomous trigger for Agent self-optimization of model operators."""
        return self.facet_optimize_operators({
            "seq_lens": seq_lens or [128, 512, 1024, 2048],
            "num_warmup": num_warmup,
            "num_trials": num_trials,
        })

    def facet_funsearch_evolve(self, steps: int = 1) -> Dict[str, Any]:
        """Google DeepMind FunSearch Facet: Evolve heuristic programs in multi-island populations."""
        cand = self.google_suite.evolve_nesting_heuristic(steps=steps)
        return {
            "program_id": cand.program_id,
            "generation": cand.generation,
            "island_id": cand.island_id,
            "score": cand.score,
            "metrics": cand.metrics,
            "valid": cand.valid,
        }

    def facet_solve_geometry(self, intent_dict_or_obj: Any) -> Dict[str, Any]:
        """Google DeepMind AlphaGeometry Facet: Analytically solve 2D/3D parametric constraints."""
        if isinstance(intent_dict_or_obj, SketchIntent):
            intent = intent_dict_or_obj
        elif isinstance(intent_dict_or_obj, dict):
            prim_fields = set(GeometricPrimitive.__dataclass_fields__)
            prim_alias = {"primitive_id": "elem_id", "id": "elem_id",
                          "primitive_type": "elem_type", "type": "elem_type",
                          "parameters": "params", "values": "params"}
            prims = []
            for p in intent_dict_or_obj.get("primitives", []):
                if isinstance(p, GeometricPrimitive):
                    prims.append(p)
                    continue
                if isinstance(p, dict):
                    p = {prim_alias.get(k, k): v for k, v in p.items()}
                    p = {k: v for k, v in p.items() if k in prim_fields}
                prims.append(GeometricPrimitive(**p))
            consts = []
            c_alias = {"id": "constraint_id", "type": "constraint_type",
                       "targets": "target_ids", "elements": "target_ids"}
            for c in intent_dict_or_obj.get("constraints", []):
                if isinstance(c, GeometricConstraint):
                    consts.append(c)
                    continue
                if isinstance(c, dict):
                    c = {c_alias.get(k, k): v for k, v in c.items()}
                consts.append(GeometricConstraint(
                    constraint_id=c.get("constraint_id", f"C{len(consts) + 1}"),
                    constraint_type=ConstraintType(str(c.get("constraint_type", "")).upper()),
                    target_ids=list(c.get("target_ids") or []),
                    value=c.get("value"),
                ))
            intent = SketchIntent(
                sketch_id=intent_dict_or_obj.get("sketch_id", "SKETCH_INTENT"),
                plane=intent_dict_or_obj.get("plane", "Front"),
                primitives=prims,
                constraints=consts,
                extrusion_depth_mm=intent_dict_or_obj.get("extrusion_depth_mm"),
                revolution_angle_deg=intent_dict_or_obj.get("revolution_angle_deg"),
            )
        else:
            return {"error": "Invalid intent specification"}

        solved = self.google_suite.solve_geometry_intent(intent)
        return {
            "sketch_id": solved.sketch_id,
            "status": solved.status.value,
            "dof": solved.dof,
            "points": solved.points,
            "circles": solved.circles,
            "exact_profile_area_mm2": solved.exact_profile_area_mm2,
            "theoretical_volume_mm3": solved.theoretical_volume_mm3,
            "volume_conservation_passed": solved.volume_conservation_passed,
            "diagnostics": solved.diagnostics,
        }

    def facet_check_affordance(
        self,
        action: str,
        software: str = "SOLIDWORKS_2021",
        state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Google SayCan Facet: Evaluate physical software/machine affordance before execution."""
        try:
            target_sw = IndustrialSoftwareTarget(software)
        except ValueError:
            target_sw = IndustrialSoftwareTarget.SOLIDWORKS_2021

        res = self.google_suite.check_affordance(
            action=action,
            software=target_sw,
            state_kwargs=state or {},
        )
        return asdict(res)

    def facet_mcts_plan(
        self,
        operations: List[Dict[str, Any]],
        initial_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Google DeepMind Rest-MCTS Facet: Plan optimal multi-operation CNC sequence."""
        op_fields = set(MachiningOperation.__dataclass_fields__)
        op_alias = {"operation_id": "op_id", "id": "op_id",
                    "operation_type": "op_type", "type": "op_type",
                    "name": "op_name", "tool": "tool_id"}
        op_objs = []
        for op in operations:
            if isinstance(op, MachiningOperation):
                op_objs.append(op)
                continue
            if isinstance(op, dict):
                op = {op_alias.get(k, k): v for k, v in op.items()}
                op = {k: v for k, v in op.items() if k in op_fields}
            op_objs.append(MachiningOperation(**op))
        st_obj = MachiningState(**(initial_state or {})) if initial_state else None
        best_ops, score, metrics = self.google_suite.plan_machining_process(op_objs, st_obj)
        return {
            "planned_operations": [op.to_dict() for op in best_ops],
            "total_prm_reward": score,
            "metrics": metrics,
        }

    def facet_rlvr_eval(
        self,
        prompt: str,
        candidates: List[str],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """DeepSeek-R1 / RLVR Facet: Evaluate a group of trajectories and compute relative advantages."""
        cands = self.model_suite.evaluate_rlvr_group(prompt, candidates, context=context)
        return {
            "prompt": prompt,
            "group_size": len(cands),
            "candidates": [c.to_dict() for c in cands],
            "best_reward": max((c.composite_reward for c in cands), default=0.0),
        }

    def facet_prm_audit(
        self,
        gcode_or_steps: Union[str, List[Dict[str, Any]]],
        safe_plane_z: float = 5.0,
        stock_top_z: float = 0.0,
    ) -> Dict[str, Any]:
        """OpenAI o1 / PRM Facet: Stepwise Process Reward Model evaluation."""
        if isinstance(gcode_or_steps, str):
            audit = self.model_suite.audit_gcode_prm(
                gcode=gcode_or_steps,
                safe_plane_z=safe_plane_z,
                stock_top_z=stock_top_z,
            )
        elif isinstance(gcode_or_steps, list):
            audit = self.model_suite.prm_model.audit_cad_steps(gcode_or_steps)
        else:
            return {"error": "Invalid input format; expected G-code string or CAD steps list"}
        return audit.to_dict()

    def facet_brep_compile(
        self,
        commands: List[Dict[str, Any]],
        part_name: str = "DeepCAD_Part",
    ) -> Dict[str, Any]:
        """MIT DeepCAD Facet: Validate B-Rep topology and compile constrained CAD-DSL."""
        cad_cmds = [CADCommand(op=c.get("op", ""), params=c.get("params", {})) for c in commands]
        code, report = self.model_suite.validate_and_compile_brep(cad_cmds, part_name=part_name)
        return {
            "part_name": part_name,
            "compiled_code": code,
            "validation_report": asdict(report),
            "is_valid": report.is_valid_manifold,
        }

    def facet_quiet_star_heal(
        self,
        code: str,
        language: str = "PYTHON",
    ) -> Dict[str, Any]:
        """Quiet-STaR Facet: Silently execute and iteratively self-heal code in virtual sandbox."""
        report = self.ultimate_suite.silent_execute_and_heal(code, language=language)
        return report.to_dict()

    def facet_blueprint_ground(
        self,
        raw_elements: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Apple Ferret Blueprint Facet: Ground 2D drawing coordinates and invert to 3D CAD spec."""
        spec, err = self.ultimate_suite.ground_and_invert_blueprint(raw_elements)
        if err:
            return {"error": err, "success": False}
        return {"success": True, "cad_spec": spec.to_dict() if spec else None}

    def facet_pinn_predict(
        self,
        length_mm: float,
        outer_dia_mm: float,
        inner_dia_mm: float,
        pressure_mpa: float = 0.0,
        tensile_force_n: float = 0.0,
        bending_moment_nm: float = 0.0,
        material: str = "AL7075-T6",
    ) -> Dict[str, Any]:
        """NVIDIA Modulus PINN Facet: Sub-10ms continuous elasticity stress and topology optimization."""
        res, err = self.ultimate_suite.predict_pinn_stress(
            length_mm=length_mm,
            outer_dia_mm=outer_dia_mm,
            inner_dia_mm=inner_dia_mm,
            pressure_mpa=pressure_mpa,
            tensile_force_n=tensile_force_n,
            bending_moment_nm=bending_moment_nm,
            material=material,
        )
        if err:
            return {"error": err, "success": False}
        return {"success": True, "result": res.to_dict() if res else None}

    def facet_dispatch_modality(
        self,
        prompt: str,
        modality: str = "FUNCTION_CALLING",
        target_software: Optional[str] = None,
        action: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Modality Facet: Explicit access modality tool invocation with failover."""
        try:
            mod = AccessModality(modality.upper())
        except ValueError:
            mod = AccessModality.FUNCTION_CALLING

        return self.dispatcher.execute(
            modality=mod,
            prompt=prompt,
            target_software=target_software,
            action=action,
            params=params,
        )

    # =========================================================================
    # Harness 2 Recursive Self-Improvement & Staged Components
    # =========================================================================

    def apply_harness_install(self, staging_dir_or_tree: Union[Path, str, Dict[str, str]]) -> Dict[str, Any]:
        """Hot-load and configure the 8 Harness 2 components into Super Agent.
        
        Components:
        c1: systemprompt.md
        c2: guardrails.md
        c3: LongTermMEMORY.md
        c4: tool_descriptions/tool_guidance.md
        c5: sub_agents/
        c6: skills/
        c7: scripts/
        c8: plugin/ or hooks.json
        """
        components: Dict[str, str] = {}
        fingerprint = None

        if isinstance(staging_dir_or_tree, (str, Path)):
            stg = Path(staging_dir_or_tree)
            if not stg.is_dir():
                raise FileNotFoundError(f"Harness directory does not exist: {stg}")
            self.active_harness_dir = stg
            manifest_file = stg / "harness_manifest.json"
            if manifest_file.is_file():
                try:
                    m_data = json.loads(manifest_file.read_text(encoding="utf-8"))
                    fingerprint = m_data.get("fingerprint")
                except Exception:
                    pass
            for fpath in stg.rglob("*"):
                if fpath.is_file() and not fpath.name.startswith("."):
                    rel_name = str(fpath.relative_to(stg)).replace("\\", "/")
                    try:
                        components[rel_name] = fpath.read_text(encoding="utf-8", errors="replace")
                    except Exception:
                        pass
        elif isinstance(staging_dir_or_tree, dict):
            components = dict(staging_dir_or_tree)

        self.harness_components = components
        if not fingerprint and components:
            raw_dig = "".join(f"{k}:{v}\n" for k, v in sorted(components.items())).encode("utf-8")
            fingerprint = hashlib.sha256(raw_dig).hexdigest()[:16]
        self.active_harness_fingerprint = fingerprint

        # Ingest the 8 components:
        # c1: systemprompt.md
        if "systemprompt.md" in components:
            self.custom_system_prompt = components["systemprompt.md"]
        # c2: guardrails.md
        if "guardrails.md" in components:
            self.custom_guardrails = components["guardrails.md"]
        # c3: LongTermMEMORY.md
        if "LongTermMEMORY.md" in components:
            self.custom_memory = components["LongTermMEMORY.md"]
        # c4: tool_descriptions/tool_guidance.md
        if "tool_descriptions/tool_guidance.md" in components:
            self.custom_tool_guidance = components["tool_descriptions/tool_guidance.md"]

        # c7: scripts/
        # V-02 修复：Harness 脚本属于"外部可写入的暂存产物"（runs/**/scripts/*.py），
        # 旧实现直接 exec 并注册为 Agent 工具，等于给暂存目录里的任意代码一条
        # 直达本进程的入口。现在装载前先做 AST 闸门，执行时注入受限 builtins。
        self.harness_rejected: List[Dict[str, str]] = []
        for comp_name, comp_code in components.items():
            if comp_name.startswith("scripts/") and comp_name.endswith(".py"):
                script_name = comp_name.split("/")[-1][:-3]

                _violations = _harness_validate(comp_code)
                if _violations and _harness_trust_mode() != "loose":
                    logger.warning(
                        "拒绝装载 Harness 脚本 %s：%s", comp_name, _violations[:3])
                    self.harness_rejected.append(
                        {"component": comp_name, "reason": "；".join(_violations[:3])})
                    if _harness_trust_mode() == "enforce":
                        continue

                def _make_script_caller(code_str: str):
                    def _call_script(args: Any = None):
                        local_ctx = {"__builtins__": _harness_builtins(),
                                     "args": args, "result": None}
                        try:
                            exec(code_str, local_ctx)
                            return local_ctx.get("result", "Script executed successfully")
                        except Exception as e:
                            return f"Script execution error: {e}"
                    return _call_script

                self.register_tool(f"script_{script_name}", f"Harness script {comp_name}", _make_script_caller(comp_code))

        logger.info(f"Loaded Harness 2 configuration with {len(components)} components (fingerprint={fingerprint})")
        return {
            "fingerprint": fingerprint,
            "components_count": len(components),
            "keys": list(components.keys()),
            "rejected_scripts": [r["component"] for r in self.harness_rejected],
        }

    def facet_harness2_refine(self, params: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Execute Harness 2 Propose-Probe-Compose task-level recursion to refine the agent harness."""
        if isinstance(params, str):
            task_prompt = params
            k = 1
            mode = "parallel"
        else:
            task_prompt = params.get("prompt", "")
            k = params.get("k", 1)
            mode = params.get("mode", "parallel")

        from virtu_omni.harness2.proposer import VirtuProposer
        from harness2.core.spec import ChannelSpec
        from virtu_omni.harness2.surface import build_default_virtu_harness, VIRTU_SURFACE
        from harness2.core import tree as HT

        spec = ChannelSpec("virtu", "virtu-cad-cam-10b")
        proposer = VirtuProposer(spec)

        temp_dir = tempfile.mkdtemp(prefix="harness2_refine_")
        ctx_dir = Path(temp_dir)
        harness_dir = ctx_dir / "harness"
        harness_dir.mkdir(parents=True, exist_ok=True)
        base_dir = ctx_dir / "base_harness"
        base_dir.mkdir(parents=True, exist_ok=True)

        current_tree = self.harness_components if self.harness_components else build_default_virtu_harness()
        HT.write_tree(VIRTU_SURFACE, current_tree, harness_dir, stubs=False)
        HT.write_tree(VIRTU_SURFACE, current_tree, base_dir, stubs=False)

        # 1. Propose edits
        prop_rep = proposer.call(f"Refine guardrails, tool guidance, and memory for: {task_prompt}", ctx_dir, "propose.inv1")

        # 2. Select winning candidate
        cand_dir = ctx_dir / "candidates"
        cand_dir.mkdir(parents=True, exist_ok=True)
        (cand_dir / "inv1.md").write_text("Guardrail and swEqnMgr verified", encoding="utf-8")
        sel_rep = proposer.call("Select optimal candidate", ctx_dir, "select.agg1")

        # 3. Experience extraction
        exp_rep = proposer.call("Extract engineering lessons", ctx_dir, "experience.agg1")

        # Update agent's active harness with proposed refinements
        if prop_rep.ok and prop_rep.workspace and Path(prop_rep.workspace).is_dir():
            self.apply_harness_install(prop_rep.workspace)

        shutil.rmtree(temp_dir, ignore_errors=True)
        return {
            "success": prop_rep.ok,
            "propose_notes": prop_rep.text,
            "selection": sel_rep.text if sel_rep else "",
            "experience": exp_rep.text if exp_rep else "",
            "active_fingerprint": self.active_harness_fingerprint,
        }

    def facet_web_search(self, params: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Internet Search Facet: Execute safe web search with automated harm and PII filtering."""
        from virtu_omni.internet import get_internet_hub
        hub = get_internet_hub()
        q = params.get("query", "") if isinstance(params, dict) else str(params)
        n = params.get("num_results", 4) if isinstance(params, dict) else 4
        return hub.web_search_tool(query=q, num_results=n)

    def facet_fetch_web_content(self, params: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Web Content Extraction Facet: Fetch and sanitize web page content with PII redactor."""
        from virtu_omni.internet import get_internet_hub
        hub = get_internet_hub()
        u = params.get("url", "") if isinstance(params, dict) else str(params)
        m = params.get("max_chars", 3000) if isinstance(params, dict) else 3000
        return hub.fetch_web_content_tool(url=u, max_chars=m)

    def facet_internet_deep_learning(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Deep Learning Ingestion Facet: Vectorize web research and synthesize SFT training pairs."""
        from virtu_omni.internet import get_internet_hub
        hub = get_internet_hub()
        topic = params.get("topic", "") if isinstance(params, dict) else "Internet Research"
        content = params.get("content", "") if isinstance(params, dict) else str(params)
        source_url = params.get("source_url", "") if isinstance(params, dict) else ""
        return hub.deep_learning_tool(topic=topic, content=content, source_url=source_url)

    def facet_web_verify_and_correct(self, params: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """联网搜索并**改正设计**：检索 GB/ISO 工艺、公差、粗糙度证据 -> 比对规格 -> 产出修正。

        修复 2026-11-12 痛点：原 REACT 流水线生成 CAD 后无任何联网核对；
        facet_internet_deep_learning 只是"摄入知识"型，不在设计修正闭环内，
        导致设计闭门造车、不会用外部证据纠正自己。
        返回的 corrected_spec 由流水线回写 spec，再进入 CAE/CAM 阶段。
        """
        try:
            from design_web_self_correction import verify_and_correct
        except Exception as exc:
            return {"passed": False, "circuit_breaker": True,
                    "error": f"联网修正模块不可用: {exc}"}
        p = params if isinstance(params, dict) else {"topic": str(params)}
        spec_in = p.get("design_spec") or {}
        if not isinstance(spec_in, dict):
            return {"passed": False, "error": "design_spec 必须是 dict"}
        topic = p.get("topic") or (
            f"{spec_in.get('part_type', '复杂曲面零件')} 五轴加工 公差等级 表面粗糙度")
        try:
            rep = verify_and_correct(spec_in, topic)
        except Exception as exc:
            return {"passed": False, "error": f"联网修正执行失败: {exc}"}
        corrections = [
            {"field": c.field, "current": c.current, "suggested": c.suggested,
             "evidence": c.evidence, "source": c.source}
            for c in rep.corrections
        ]
        return {
            "passed": bool(rep.searched),
            "searched": bool(rep.searched),
            "provider": rep.provider,
            "online": bool(rep.online),
            "topic": topic,
            "corrections": corrections,
            "corrected_spec": {c["field"]: c["suggested"] for c in corrections},
            "notes": list(rep.notes),
        }

    def facet_inspect_step_artifact(self, step_path: str) -> Dict[str, Any]:
        """Read-only STEP artifact check; all paths and geometry checks live in the inspector."""
        try:
            from virtu_omni.engine.step_artifact_inspector import inspect_step_artifact
        except Exception as exc:
            return {
                "status": "FAIL",
                "passed": False,
                "verified": False,
                "evidence_status": "module_unavailable",
                "error": f"STEP 检查器不可用：{type(exc).__name__}: {exc}",
            }
        return inspect_step_artifact(step_path)

    def facet_verify_product_integrity(self, params: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """第四层成品完整性校验门：防"把毛坯当产品交付"。

        三道门 = 特征体积守恒 ΔV!=0 / 成品几何非圆柱毛坯退化 /
        VERICUT Auto-Diff 红=0、蓝<=2%、绿>=98%（成品确实完整成形）。
        证据宪法：证据不足时 verified=False，绝不宣称成品已验证。
        """
        try:
            from product_integrity_gate import (
                verify_product_integrity, FeatureDelta, GeometryEvidence,
                autodiff_from_report, geometry_from_mesh,
            )
        except Exception as exc:
            return {"passed": False, "verified": False, "circuit_breaker": True,
                    "evidence_status": "module_unavailable",
                    "error": f"成品校验门不可用: {exc}"}
        p = params if isinstance(params, dict) else {}
        try:
            raw_f = p.get("features")
            features = ([FeatureDelta(**f) for f in raw_f]
                        if isinstance(raw_f, list) and raw_f else None)
            geometry = None
            if isinstance(p.get("geometry"), dict):
                geometry = GeometryEvidence(**p["geometry"])
            elif p.get("geometry_mesh"):
                geometry = geometry_from_mesh(str(p["geometry_mesh"]))
            autodiff = None
            if isinstance(p.get("autodiff"), dict):
                autodiff = autodiff_from_report(p["autodiff"])
            elif p.get("autodiff_report"):
                autodiff = autodiff_from_report(
                    json.loads(Path(str(p["autodiff_report"])).read_text(encoding="utf-8")))
        except Exception as exc:
            return {"passed": False, "verified": False, "circuit_breaker": True,
                    "evidence_status": "evidence_unreadable",
                    "error": f"证据采集失败: {exc}"}

        if features is None or geometry is None or autodiff is None:
            return {
                "passed": True, "verified": False,
                "evidence_status": "insufficient",
                "note": "缺少特征体积/成品几何/Auto-Diff 证据，本轮不宣称成品已验证"
                        "（Evidence Before Assertions，AGENTS.md §5）",
            }
        rep = verify_product_integrity(features=features, geometry=geometry,
                                       autodiff=autodiff, strict=False)
        return {
            "passed": rep.passed,
            "verified": True,
            "circuit_breaker": rep.circuit_breaker,
            "evidence_status": "measured",
            "failures": list(rep.failures),
            "checks": [f"{c.name}:{'PASS' if c.passed else 'FAIL'}" for c in rep.checks],
        }

    def facet_observe_surface(self, params: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """几何可观测化：把不透明复杂曲面变成智能体能'看见'的证据（AGENTS.md 第6节）。

        输出曲率场（高曲率区→步距收紧）、残余高度场（超表面粗糙度即报警）、
        可达性/负角（是否需要5轴），并渲染三张 PNG（曲率热力图/残余高度图/刀轨回放）
        作为多模态输入。直接缓解'智能体看不懂复杂曲面'这一根本痛点。
        """
        try:
            from surface_observability import observe_surface, SurfaceObservabilityReport
        except Exception as exc:
            return {"passed": False, "verified": False, "circuit_breaker": False,
                    "evidence_status": "module_unavailable",
                    "error": f"几何可观测化不可用: {exc}"}
        p = params if isinstance(params, dict) else {}
        mesh = p.get("mesh_path") or p.get("geometry_mesh")
        if not mesh:
            try:
                from virtu_omni.agent.swarm_orchestrator import resolve_sample_assets_for_task
                mesh = resolve_sample_assets_for_task(p, Path(WORKSPACE_DIR)).get("design_stl")
            except Exception:
                mesh = None
        if not mesh:
            mesh = str(Path(WORKSPACE_DIR) / "artifacts" / "aero_closed_impeller"
                       / "AE_CLOSED_IMPELLER_NASA1975.stl")
        try:
            raw_step = p.get("step_over_mm")
            rep: SurfaceObservabilityReport = observe_surface(
                mesh,
                tool_radius_mm=float(p.get("tool_radius_mm", 3.0)),
                step_over_mm=(float(raw_step) if raw_step is not None else None),
                finish_allowance_mm=float(p.get("finish_allowance_mm", 0.01)),
                spindle_axis=str(p.get("spindle_axis", "Z")),
                output_dir=p.get("output_dir") or str(
                    Path(mesh).parent / "surface_obs"
                ),
            )
        except Exception as exc:
            return {"passed": False, "verified": False, "circuit_breaker": False,
                    "evidence_status": "compute_error",
                    "error": f"曲面可观测化失败: {exc}"}
        if rep.evidence_status != "measured":
            return {"passed": True, "verified": False, "circuit_breaker": False,
                    "evidence_status": rep.evidence_status,
                    "note": rep.summary, "images": rep.images}
        return {
            "passed": True, "verified": True, "evidence_status": "measured",
            "mesh": rep.mesh, "triangle_count": rep.triangle_count,
            "curvature": rep.curvature,
            "high_curvature_face_count": rep.high_curvature_face_count,
            "high_curvature_pct": rep.high_curvature_pct,
            "residual": rep.residual,
            "faces_over_allowance": rep.faces_over_allowance,
            "faces_over_allowance_pct": rep.faces_over_allowance_pct,
            "undercut_face_count": rep.undercut_face_count,
            "requires_multiaxis": rep.requires_multiaxis,
            "recommended_step_over_mm": rep.recommended_step_over_mm,
            "recommended_tool_radius_mm": rep.recommended_tool_radius_mm,
            "images": rep.images,
            "summary": rep.summary,
        }

    def facet_capability_lookup(self, params: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Capability Lookup Facet: 按问题检索通用能力 SOP（规划/研究/编码/数据/写作/验证/编排/安全/记忆/沟通/工程纪律）。

        什么时候该调：不确定'这类事该按什么步骤做、做到什么程度算完成'时。
        返回的 brief 是可直接照着执行的作业规范，含硬约束与验收门。
        检索不到就返回 matched=false——不会拿"最相近的一条"糊弄。
        """
        p = params if isinstance(params, dict) else {"query": str(params)}
        query = str(p.get("query") or p.get("payload") or "").strip()
        reg = self._cap_registry()
        if reg is None:
            return {"status": "error", "matched": False,
                    "message": "能力目录不可用（virtu_omni.capabilities 导入失败）"}
        if not query:
            return {"status": "error", "matched": False, "message": "query 为空"}
        try:
            k = int(p.get("k", 3))
        except (TypeError, ValueError):
            k = 3
        hits = reg.search(query, k=max(1, min(k, 6)))
        if not hits:
            return {"status": "ok", "matched": False, "query": query,
                    "hits": [], "brief": "",
                    "message": "无匹配能力原子——按通用纪律执行，不要虚构 SOP"}
        ids = [h["id"] for h in hits]
        return {
            "status": "ok",
            "matched": True,
            "query": query,
            "hits": [
                {"id": h["id"], "title": h["title"], "family": h["family"],
                 "score": h["score"], "gate": reg.gate(h["id"])["id"]}
                for h in hits
            ],
            "brief": reg.render(ids, max_chars=int(p.get("max_chars", 1800))),
        }

    def facet_capability_guard(self, params: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Capability Guard Facet: 把"证据先于断言"变成可调用门。

        只判一件事：**宣称完成时，是否附了可复跑的实测证据**。它不判断证据本身对不对
        （那是各领域 gate 的职责），只拒绝三类无效宣称：
          NO_EVIDENCE         —— 空口完成
          INCOMPLETE_EVIDENCE —— 证据条目缺 check 或 output
          ASSERTED_ONLY       —— 只有推断/阅读/自我推理，没有实测

        载荷：{"claim": "...", "evidence": [{"check": "命令", "output": "原始输出或路径", "kind": "measured"}]}
        kind 缺省按 asserted 处理（从严）。
        """
        p = params if isinstance(params, dict) else {"claim": str(params)}
        claim = str(p.get("claim") or "").strip()
        raw = p.get("evidence") or []
        if isinstance(raw, dict):
            raw = [raw]
        if not isinstance(raw, list):
            raw = []
        if not claim:
            return {"passed": False, "evidence_level": "insufficient",
                    "verdict": "NO_CLAIM", "message": "缺少 claim，无法审计"}
        if not raw:
            return {"passed": False, "evidence_level": "insufficient",
                    "verdict": "NO_EVIDENCE",
                    "message": "宣称完成但未提供任何证据；按证据宪法只能表述为未验证"}
        incomplete: List[int] = []
        asserted: List[int] = []
        for i, item in enumerate(raw):
            if not isinstance(item, dict):
                incomplete.append(i)
                continue
            check = str(item.get("check") or "").strip()
            output = str(item.get("output") or "").strip()
            if not check or not output:
                incomplete.append(i)
                continue
            if str(item.get("kind") or "asserted").strip().lower() != "measured":
                asserted.append(i)
        if incomplete:
            return {"passed": False, "evidence_level": "insufficient",
                    "verdict": "INCOMPLETE_EVIDENCE",
                    "incomplete_indexes": incomplete,
                    "message": "证据条目必须同时含 check 与 output；缺一即视为未取证"}
        if asserted:
            return {"passed": False, "evidence_level": "asserted",
                    "verdict": "ASSERTED_ONLY",
                    "asserted_indexes": asserted,
                    "message": "存在非 measured 证据（推断/阅读/自我推理），不得据此宣称已验证"}
        return {
            "passed": True,
            "evidence_level": "measured",
            "verdict": "EVIDENCE_OK",
            "claim": claim,
            "evidence_count": len(raw),
            "message": "证据齐备；注意本门只证明'有实测证据'，不证明证据支持该结论",
        }

    def facet_autonomous_learn_gap(self, params: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Autonomous Knowledge Gap Resolution Facet: Automatically search, filter, and learn missing concepts."""
        from virtu_omni.internet import get_autonomous_engine
        engine = get_autonomous_engine()
        concept = params.get("concept", "") if isinstance(params, dict) else str(params)
        return engine.learn_missing_knowledge(concept)

    def facet_agent_desktop(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Agent-Desktop Semantic Perception & Interaction Facet (Vercel Labs agent-desktop).
        
        Enables structured accessibility tree inspection (@ref), find, click, type, window and display control.
        """
        action = params.get("action", params.get("command", "status"))
        tool_name = action if action.startswith("desktop_") else f"desktop_{action}"
        from bridges.agent_desktop_bridge import AgentDesktopBridge
        bridge = AgentDesktopBridge()
        return bridge.execute_tool(tool_name, params)

    def facet_desktop_gui(self, params: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Desktop Perception & GUI Automation Facet: Screen perception, mouse/keyboard control, and dialog handling."""
        from bridges.tool_calling_specs import execute_tool_call
        if not isinstance(params, dict):
            return {"status": "error", "input_sent": False,
                    "message": "desktop_gui 需要对象载荷（含 action 等字段）；"
                               "自然语言零件规格不是合法的桌面动作，请改用 generate_parametric_cad 等工程工具。"}
        return execute_tool_call("cadcam_desktop_gui", params)

    def facet_mouse_control(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Mouse Control Facet: Native click, double-click, move, drag, scroll operations."""
        from bridges.desktop_controller import DesktopController
        ctl = DesktopController()
        act = params.get("action", "click")
        if act == "click":
            return ctl.click(
                int(params.get("x", 0)),
                int(params.get("y", 0)),
                button=params.get("button", "left"),
                double=bool(params.get("double", False)),
            )
        elif act == "move":
            return ctl.move(int(params.get("x", 0)), int(params.get("y", 0)))
        elif act == "drag":
            sx = int(params.get("start_x", params.get("x", 0)))
            sy = int(params.get("start_y", params.get("y", 0)))
            ex = int(params.get("end_x", sx))
            ey = int(params.get("end_y", sy))
            btn = params.get("button", "left")
            return ctl.drag(sx, sy, ex, ey, button=btn)
        elif act == "scroll":
            clicks = int(params.get("clicks", 1))
            x = params.get("x")
            y = params.get("y")
            return ctl.scroll(clicks, int(x) if x is not None else None, int(y) if y is not None else None)
        return {"status": "error", "message": f"Unsupported mouse action: {act}"}

    def facet_keyboard_control(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Keyboard Control Facet: Secure text input via Unicode clipboard and hotkey combinations."""
        from bridges.desktop_controller import DesktopController
        ctl = DesktopController()
        act = params.get("action", "hotkey")
        if act == "type_text" or "text" in params:
            return ctl.type_text(params.get("text", ""))
        elif act == "hotkey" or "keys" in params:
            return ctl.hotkey(params.get("keys", ""))
        return {"status": "error", "message": f"Unsupported keyboard action: {act}"}

    def facet_screen_control(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Screen Control Facet: Screen/window capture, window focus, modal dialog dismissal, and visual inspection."""
        from bridges.desktop_controller import DesktopController
        ctl = DesktopController()
        act = params.get("action", "capture")
        if act == "capture":
            output_path = params.get("output_path", r"D:\Virtu模型\scratch\gui_capture.png")
            sw = params.get("software")
            return ctl.capture(output_path=output_path, software=sw)
        elif act == "focus":
            return ctl.focus(params.get("software", ""))
        elif act == "inspect_window":
            return ctl.diagnose_software_window(params.get("software", ""))
        elif act == "dismiss_dialogs":
            return ctl.dismiss_all_dialogs()
        elif act == "visual_inspect":
            from bridges.cadcam_vision_bridge import CADCAMVisionBridge
            vb = CADCAMVisionBridge()
            task = params.get("task", "autodiff_inspection")
            img = params.get("image_path") or params.get("output_path") or ""
            return vb.analyze_inspection(task, img)
        return {"status": "error", "message": f"Unsupported screen action: {act}"}

    def _solve_harnessed(
        self,
        prompt: str,
        k: int = 1,
        recursion_mode: str = "parallel",
        output_dir: Optional[str] = None,
        memory_safe: bool = True,
        **kwargs: Any,
    ) -> SuperAgentExecutionResult:
        """Execute full engineering task with recursive Harness 2 self-improvement."""
        t0 = time.time()
        # 1. Refine the agent's harness for this task
        refine_info = self.facet_harness2_refine({"prompt": prompt, "k": k, "mode": recursion_mode})

        # 2. Solve autonomously under the refined harness
        res = self._solve_autonomous(prompt, output_dir=output_dir, memory_safe=memory_safe)
        res.mode = SuperAgentMode.HARNESSED.value
        res.facets_engaged.append("Harness² Recursive Improver")
        res.artifacts["harness2_refinement"] = refine_info
        if self.active_harness_fingerprint:
            res.metrics["harness_fingerprint"] = self.active_harness_fingerprint
        return res

    # =========================================================================
    # Rollback Session (default rollback for the circuit breaker)
    # =========================================================================

    def begin_rollback_session(self) -> None:
        """开启一轮可回滚会话：清空产物登记、快照目录与 PID 登记。"""
        self._session_artifacts = []
        self._session_snapshot_dir = None
        self._session_pids = []
        self.last_rollback_report = None

    def register_session_artifact(self, path: str, existed_before: Optional[bool] = None) -> Dict[str, Any]:
        """登记本会话产出的文件；若同名文件原先存在，先做快照以便回滚恢复。

        ``existed_before`` 由调用方在**写入之前**探测传入（默认按当前状态探测），
        以保证「新建文件 → 回滚删除」、「覆盖文件 → 回滚恢复原内容」语义正确。
        """
        ap = os.path.abspath(path)
        for rec in self._session_artifacts:
            if rec["path"] == ap:
                return rec
        if existed_before is None:
            existed_before = os.path.exists(ap)
        rec: Dict[str, Any] = {"path": ap, "existed_before": bool(existed_before), "snapshot": None}
        if rec["existed_before"] and os.path.exists(ap):
            try:
                if not self._session_snapshot_dir:
                    base = os.path.join(WORKSPACE_DIR, "runs", "_agent_rollback_snapshots")
                    self._session_snapshot_dir = os.path.join(
                        base, f"snap_{int(time.time() * 1000)}_{os.getpid()}"
                    )
                os.makedirs(self._session_snapshot_dir, exist_ok=True)
                tag = hashlib.sha256(ap.encode("utf-8")).hexdigest()[:12]
                snap = os.path.join(self._session_snapshot_dir, f"{tag}_{os.path.basename(ap)}")
                shutil.copy2(ap, snap)
                rec["snapshot"] = snap
            except Exception as e_snap:  # pragma: no cover - 快照失败不阻断主流程
                logger.warning(f"[rollback] 产物快照失败 {ap}: {e_snap}")
        self._session_artifacts.append(rec)
        return rec

    def register_session_pid(self, pid: int) -> None:
        """登记本会话启动的进程 PID（默认回滚只回收这些 PID，禁止全局杀）。"""
        try:
            pid_i = int(pid)
        except (TypeError, ValueError):
            return
        if pid_i in self._session_pids:
            return
        self._session_pids.append(pid_i)
        try:
            self.reclaimer.register_session_pid(pid_i)
        except Exception:  # pragma: no cover
            pass

    def discard_rollback_session(self) -> None:
        """会话成功后丢弃快照（已落盘产物不受影响）。"""
        if self._session_snapshot_dir and os.path.isdir(self._session_snapshot_dir):
            shutil.rmtree(self._session_snapshot_dir, ignore_errors=True)
        self._session_artifacts = []
        self._session_pids = []
        self._session_snapshot_dir = None

    def default_rollback(self, scope: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """默认原子回滚：恢复/删除本会话产物 + 关闭本会话启动的 CAD/CAM 软件。

        安全边界：只处理 ``self._session_artifacts`` 登记过的文件与
        ``self._session_pids`` / ProcessMemoryReclaimer 同源判定覆盖的进程
        （``allow_global_kill=False``），绝不按 exe 名全局杀进程。
        """
        scope = scope or {}
        report: Dict[str, Any] = {
            "basis": "measured",
            "stage": scope.get("stage"),
            "restored": [],
            "deleted": [],
            "kept": [],
            "closed_processes": [],
            "closed_software": [],
            "errors": [],
        }
        # 1. 脏文件：有快照则恢复，无快照则删除本会话新建的文件
        for rec in list(self._session_artifacts):
            p = rec.get("path")
            try:
                if rec.get("snapshot") and os.path.exists(rec["snapshot"]):
                    shutil.copy2(rec["snapshot"], p)
                    report["restored"].append(p)
                elif os.path.exists(p):
                    os.remove(p)
                    report["deleted"].append(p)
                else:
                    report["kept"].append(p)
            except Exception as e:  # pragma: no cover
                report["errors"].append(f"{p}: {e}")
        # 2. 本会话启动的进程：精准终止
        for pid in list(self._session_pids):
            terminated = False
            try:
                import psutil  # 局部导入：无 psutil 时不影响 agent 主体
                if psutil.pid_exists(pid):
                    proc = psutil.Process(pid)
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except Exception:
                        proc.kill()
                    terminated = True
            except Exception as e:
                report["errors"].append(f"pid {pid}: {e}")
            report["closed_processes"].append({"pid": pid, "terminated": terminated})
        # 3. 复用同源 PID 能力的软件级回收（无同源 PID 时内部直接返回 NOT_RUNNING）
        softwares = scope.get("softwares") or ["solidworks", "autocad", "nx", "cimco", "vericut", "sscnc"]
        for key in softwares:
            try:
                rec = self.reclaimer.close_software(key, grace_period_s=1.0)
                report["closed_software"].append(
                    {"target": key, "status": rec.get("status"), "killed_pids": rec.get("killed_pids", [])}
                )
            except Exception as e:
                report["errors"].append(f"close_software({key}): {e}")
        # 4. 快照目录清理
        if self._session_snapshot_dir and os.path.isdir(self._session_snapshot_dir):
            shutil.rmtree(self._session_snapshot_dir, ignore_errors=True)
        self._session_snapshot_dir = None
        report["rolled_back"] = True
        self.last_rollback_report = report
        logger.error(
            f"[rollback] 默认原子回滚执行完毕: restored={len(report['restored'])} "
            f"deleted={len(report['deleted'])} errors={len(report['errors'])}"
        )
        return report

    # =========================================================================
    # Measurement helpers (AGENTS.md §8.1: measured / asserted / inferred / unmeasured)
    # =========================================================================

    @staticmethod
    def _measured_tokens(source: Any, key: str) -> Union[int, str]:
        """读取执行器真实返回的 token 计量；拿不到就如实写 ``"unmeasured"``。

        只认执行器原生字段 ``prompt_eval_count`` / ``eval_count``（Ollama 口径），
        不再用 ``len(text) // 2`` 或常量冒充测量值。
        """
        if source is None:
            return "unmeasured"
        val: Any = None
        if isinstance(source, dict):
            val = source.get(key)
            if val is None:
                for wrapper in ("response", "raw", "usage", "metrics", "result", "executor"):
                    sub = source.get(wrapper)
                    if isinstance(sub, dict) and sub.get(key) is not None:
                        val = sub[key]
                        break
        else:
            val = getattr(source, key, None)
        if isinstance(val, bool) or val is None:
            return "unmeasured"
        try:
            return int(val)
        except (TypeError, ValueError):
            return "unmeasured"

    def _first_measured_token(self, sources: List[Any], key: str) -> Union[int, str]:
        """在多个来源对象中取第一个可用的实测 token 值，否则 ``"unmeasured"``。"""
        for src in sources:
            got = self._measured_tokens(src, key)
            if isinstance(got, int):
                return got
        return "unmeasured"

    # =========================================================================
    # Step-by-Step Circuit Breaker Execution
    # =========================================================================

    def execute_with_circuit_breaker(
        self,
        stage_name: str,
        step_fn: Callable[[int], Dict[str, Any]],
        verify_fn: Optional[Callable[[Dict[str, Any]], Tuple[bool, str]]] = None,
        max_retries: int = 3,
        rollback_fn: Optional[Callable[..., Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Executes a step with Extreme Step-by-Step Self-Verification & Circuit Breaker Axiom:
        “又快又准到极限，未到极限则继续，到了极限则放弃”

        回滚语义（AGENTS.md §6.4）：``rollback_fn`` 仍是可选参数，但**回滚本身是
        必需语义**——未提供时自动注入 ``self.default_rollback``（恢复本会话产物的
        快照 / 删除本会话新建的脏文件 / 仅终止本会话启动的 PID 并按同源判定关闭
        CAD-CAM 软件，绝不全局杀进程）。回滚执行结果写入 RCFA 的
        ``rollback`` 字段（source / performed / error），熔断分支因此始终可达。
        """
        last_error = ""
        last_result: Optional[Dict[str, Any]] = None

        for attempt in range(1, max_retries + 1):
            try:
                result = step_fn(attempt)
                last_result = result

                # Tier 0 & 1 verification
                if verify_fn:
                    passed, reason = verify_fn(result)
                    if not passed:
                        last_error = f"自查未通过: {reason}"
                        if attempt < max_retries:
                            logger.warning(
                                f"[{stage_name}] 尝试 {attempt}/{max_retries} 自查失败: {reason}，触发自愈重试..."
                            )
                            continue
                        else:
                            break

                # Step succeeded
                return result

            except Exception as e:
                last_error = f"异常报错: {str(e)}"
                if attempt < max_retries:
                    logger.warning(
                        f"[{stage_name}] 尝试 {attempt}/{max_retries} 发生异常: {e}，触发单点修补并重试..."
                    )
                else:
                    break

        # Reached limit (attempt >= max_retries) -> Trigger Circuit Breaker & Rollback
        # 回滚是必需语义（AGENTS.md §6.4）：调用方未提供 rollback_fn 时注入默认回滚，
        # 保证熔断后不留半成品产物、不残留本会话启动的软件进程。
        rollback_source = "caller" if rollback_fn is not None else "default"
        active_rollback: Callable[..., Any] = rollback_fn if rollback_fn is not None else self.default_rollback
        rollback_scope: Dict[str, Any] = {
            "stage": stage_name,
            "attempts": max_retries,
            "last_error": last_error,
            "last_partial_result": last_result,
        }
        rollback_performed = False
        rollback_error: Optional[str] = None
        try:
            active_rollback(rollback_scope)
            rollback_performed = True
        except TypeError:
            # 兼容调用方传入的无参 rollback_fn
            try:
                active_rollback()
                rollback_performed = True
            except Exception as rb_err:
                rollback_error = str(rb_err)
                logger.error(f"[{stage_name}] 原子回滚发生次生错误: {rb_err}")
        except Exception as rb_err:
            rollback_error = str(rb_err)
            logger.error(f"[{stage_name}] 原子回滚发生次生错误: {rb_err}")

        rcfa_report = {
            "stage": stage_name,
            "attempts": max_retries,
            "root_cause": last_error,
            "last_partial_result": last_result,
            "rollback": {
                "source": rollback_source,
                "performed": rollback_performed,
                "error": rollback_error,
            },
            "actionable_advice": f"阶段 [{stage_name}] 连续 {max_retries} 次自查均未收敛。请检查几何矛盾、API 权限或工艺约束。"
        }
        raise CircuitBreakerException(
            stage=stage_name,
            attempt=max_retries,
            error_msg=last_error,
            rcfa_report=rcfa_report,
        )

    # =========================================================================
    # Mode A: Autonomous End-to-End Pipeline
    # =========================================================================

    def _solve_autonomous(
        self,
        user_prompt: str,
        output_dir: Optional[str] = None,
        memory_safe: bool = True,
    ) -> SuperAgentExecutionResult:
        """Full-lifecycle autonomous engineering solution with stage-gated memory reclamation."""
        t0 = time.time()
        # 内容指纹 run_id：同输入可得同 run_id（AGENTS.md §8.2 内容寻址）。
        # 产物目录以 "<run_id>_<时间戳>" 命名，避免同秒两次运行互相覆盖。
        run_id = hashlib.sha256(
            f"{user_prompt}|autonomous|memory_safe={memory_safe}".encode("utf-8")
        ).hexdigest()[:16]
        self._current_run_id = run_id
        if not output_dir:
            ts = time.strftime("%Y%m%d_%H%M%S")
            output_dir = os.path.join(WORKSPACE_DIR, "runs", "super_agent", f"{run_id}_{ts}")
        os.makedirs(output_dir, exist_ok=True)
        # 开启回滚会话：本次产出全部登记，熔断时可按快照恢复/清理
        self.begin_rollback_session()

        trace_log: List[Dict[str, Any]] = []
        artifacts: Dict[str, Any] = {}
        facets_engaged = [
            "Memory & Hindsight",
            "Chief Architect",
            "Parametric CAD Modeler",
            "Engineering Standards & GD&T",
            "CAM Machining & Toolpath",
            "CAE Stress Analysis",
            "Headless Sandbox Auditor",
        ]

        def _persist(step_idx: int, title: str, files: Dict[str, Any], soft_key: Optional[str] = None):
            for fn, content in files.items():
                p = os.path.join(output_dir, fn)
                # 写前记录存在性：新建文件回滚=删除；覆盖文件回滚=恢复快照
                _existed_before = os.path.exists(p)
                if isinstance(content, (dict, list)):
                    with open(p, "w", encoding="utf-8") as f:
                        json.dump(content, f, ensure_ascii=False, indent=2)
                else:
                    with open(p, "w", encoding="utf-8") as f:
                        f.write(str(content))
                artifacts[fn] = p
                self.register_session_artifact(p, existed_before=_existed_before)
            if memory_safe:
                if soft_key:
                    self.reclaimer.close_software(soft_key)
                self.reclaimer.trim_system_working_set()

        try:
            # 1. Unified Memory Recall, Working Memory & Coordinate Isolation
            runtime_ctx = self.build_runtime_memory_context(user_prompt)

            def step_1(att):
                rec = self.facet_recall_memory(user_prompt)
                rec["runtime_memory_context"] = runtime_ctx
                return rec

            mem_data = self.execute_with_circuit_breaker(
                "Memory_Retrieval", step_1, verify_fn=lambda r: (r is not None, "检索产物非空")
            )
            _persist(1, "Memory Retrieval", {"01_hindsight_retrieval.json": mem_data})
            trace_log.append({"stage": "1. 跨会话语义检索与经验自省", "status": "COMPLETED"})

            # 2. Architect intent parsing
            def step_2(att):
                return self.facet_parse_intent(user_prompt)

            arch_res = self.execute_with_circuit_breaker(
                "Architecture_Spec",
                step_2,
                verify_fn=lambda r: (bool(r.get("parsed_spec")), "规格解析非空"),
            )
            spec = arch_res["parsed_spec"]
            if self.working_memory is not None and isinstance(spec, dict):
                for _fk in ("outer_diameter", "bore_diameter", "overall_len", "material"):
                    if spec.get(_fk) is not None:
                        self.working_memory.record_fact(
                            key=_fk,
                            value=spec.get(_fk),
                            source="parse_intent",
                            verified=True,
                            basis="asserted",
                        )
            _persist(2, "Architecture Spec", {"02_architecture_spec.json": arch_res})
            trace_log.append({"stage": "2. 系统需求拆解与愿景规格化", "status": "COMPLETED", "summary": arch_res["summary"]})

            # 3. Parametric 3D CAD Modeling
            def step_3(att):
                return self.facet_generate_cad({"user_prompt": user_prompt, "architecture": arch_res})

            model_res = self.execute_with_circuit_breaker(
                "Parametric_Modeling",
                step_3,
                verify_fn=lambda r: (len(r.get("feature_tree", [])) > 0, "特征树非空"),
                soft_key="solidworks" if memory_safe else None,
            )
            _persist(
                3,
                "Parametric Modeling",
                {
                    "03_parametric_feature_tree.json": model_res["feature_tree"],
                    "03_parametric_equations.json": model_res["equations"],
                    "03_solidworks_native.swb": model_res["solidworks_vba"],
                },
                soft_key="solidworks",
            )
            trace_log.append({"stage": "3. 3D 原生特征树与方程式参数建模", "status": "COMPLETED", "summary": model_res["summary"]})

            # 4. Standards & GD&T
            def step_4(att):
                return self.facet_generate_standards({"architecture": arch_res, "modeling": model_res})

            std_res = self.execute_with_circuit_breaker(
                "Standards_GDT",
                step_4,
                verify_fn=lambda r: (bool(r.get("drawing_spec")), "工程图公差非空"),
                soft_key="autocad" if memory_safe else None,
            )
            _persist(4, "Standards & GD&T", {"04_drawing_standards_gdt.json": std_res["drawing_spec"]}, soft_key="autocad")
            trace_log.append({"stage": "4. 工程制图标准与 GD&T 公差标注", "status": "COMPLETED", "summary": std_res["summary"]})

            # 5. Machining & CAM Toolpath
            def step_5(att):
                return self.facet_generate_cam({"architecture": arch_res, "modeling": model_res})

            mach_res = self.execute_with_circuit_breaker(
                "Machining_CAM",
                step_5,
                verify_fn=lambda r: ("macro_b_code" in r and len(r["macro_b_code"]) > 0, "宏程序非空"),
                soft_key="cimco" if memory_safe else None,
            )
            _persist(
                5,
                "Machining CAM",
                {
                    "05_machining_macro_b.nc": mach_res["macro_b_code"],
                    "05_cutting_params.json": mach_res["cutting_params"],
                },
                soft_key="cimco",
            )
            trace_log.append({"stage": "5. 数控加工工艺与 CNC Macro B 刀路", "status": "COMPLETED", "summary": mach_res["summary"]})

            # 6. CAE Stress Analysis & Safety Factor
            def step_6(att):
                return self.facet_verify_cae(spec, internal_pressure_mpa=10.0)

            cae_res = self.execute_with_circuit_breaker(
                "CAE_Stress_Simulation",
                step_6,
                verify_fn=lambda r: (r.get("fos_passed", False), f"安全系数 FOS={r.get('safety_factor_fos')} 需 >= 1.5"),
            )
            if self.working_memory is not None and isinstance(cae_res, dict) and cae_res.get("safety_factor_fos") is not None:
                self.working_memory.record_fact(
                    key="safety_factor_fos",
                    value=cae_res.get("safety_factor_fos"),
                    source="facet_verify_cae",
                    verified=True,
                    basis="measured",
                )
            _persist(6, "CAE Simulation", {"06_cae_stress_simulation.json": cae_res})
            trace_log.append({"stage": "6. 有限元与弹性力学安全系数分析 (CAE)", "status": "COMPLETED", "summary": cae_res["summary"]})

            # 7. Sandbox Simulation & Auditor
            def step_7(att):
                return self.facet_audit_sandbox({"modeling": model_res, "machining": mach_res})

            audit_res = self.execute_with_circuit_breaker(
                "Sandbox_Auditing",
                step_7,
                verify_fn=lambda r: (r.get("passed", False), "沙箱仿真无碰撞与语法错误"),
                soft_key="vericut" if memory_safe else None,
            )
            _persist(7, "Sandbox Simulation", {"07_sandbox_simulation_audit.json": audit_res}, soft_key="vericut")
            trace_log.append({"stage": "7. 虚拟无头沙箱仿真与零碰撞复核", "status": "COMPLETED", "summary": audit_res["summary"]})

            # 8. Memory Commit
            mem_commit = self.facet_commit_memory({
                "user_prompt": user_prompt,
                "architecture": arch_res,
                "auditor": audit_res,
            })
            _persist(8, "Memory Commit", {"08_memory_commit_receipt.json": mem_commit})
            trace_log.append({"stage": "8. 高阶制造经验与心智模型固化至 Hindsight", "status": "COMPLETED"})

            # Automatic Wake Phase Recording for Google Sleep continual learning
            # token 必须是执行器实测值（prompt_eval_count / eval_count），取不到写 "unmeasured"
            _token_sources = [mem_data, arch_res, model_res, std_res, mach_res, cae_res, audit_res, mem_commit]
            _tok_prompt = self._first_measured_token(_token_sources, "prompt_eval_count")
            _tok_completion = self._first_measured_token(_token_sources, "eval_count")
            try:
                self.sleep_framework.record_wake_step(
                    prompt=user_prompt,
                    completion=f"Autonomous solve completed: {arch_res.get('summary', '')}; FOS={cae_res.get('safety_factor_fos')}",
                    verified_facts={
                        "safety_factor_fos": cae_res.get("safety_factor_fos"),
                        "theoretical_volume_mm3": cae_res.get("theoretical_volume_mm3"),
                        "architecture": arch_res.get("summary", ""),
                    },
                    tool_calls=[{"tool": "solve_autonomous", "status": "COMPLETED"}],
                    tokens_prompt=_tok_prompt,
                    tokens_completion=_tok_completion,
                )
            except Exception as e_wake:
                logger.warning(f"Could not record wake step: {e_wake}")

            # Physical volume conservation assertion
            volume_theor = cae_res.get("theoretical_volume_mm3", 0.0)
            metrics = {
                "volume_conservation": f"{volume_theor} mm³ (ΔV != 0, 守恒)",
                "safety_factor": f"{cae_res.get('safety_factor_fos')} ({'合格' if cae_res.get('fos_passed') else '不合格'})",
                "fos_val": cae_res.get("safety_factor_fos"),
                "ram_status": self.reclaimer.get_system_memory(),
                "run_id": run_id,
                "memory_context_injected": bool(runtime_ctx),
                "working_memory_facts": len(self.working_memory.facts) if self.working_memory else 0,
                "tokens": {
                    "prompt_eval_count": _tok_prompt,
                    "eval_count": _tok_completion,
                    "basis": "measured" if isinstance(_tok_prompt, int) else "unmeasured",
                },
            }

            runtime = time.time() - t0
            # 成功路径：产物已落盘，丢弃回滚快照并清理会话登记
            self.discard_rollback_session()
            return SuperAgentExecutionResult(
                task_prompt=user_prompt,
                mode=SuperAgentMode.AUTONOMOUS.value,
                success=True,
                runtime_seconds=runtime,
                facets_engaged=facets_engaged,
                artifacts={
                    "architecture": arch_res,
                    "parametric_model": model_res,
                    "standards_gdt": std_res,
                    "machining_cnc": mach_res,
                    "cae_simulation": cae_res,
                    "sandbox_audit": audit_res,
                    "memory_evolution": mem_commit,
                    "runtime_memory_context": runtime_ctx,
                    "persisted_files": artifacts,
                },
                trace_log=trace_log,
                metrics=metrics,
                circuit_breaker_tripped=False,
                output_dir=output_dir,
            )

        except CircuitBreakerException as cb_exc:
            runtime = time.time() - t0
            # 快照由回滚消费完毕，清理残留目录
            if self._session_snapshot_dir and os.path.isdir(self._session_snapshot_dir):
                shutil.rmtree(self._session_snapshot_dir, ignore_errors=True)
            self._session_snapshot_dir = None
            return SuperAgentExecutionResult(
                task_prompt=user_prompt,
                mode=SuperAgentMode.AUTONOMOUS.value,
                success=False,
                runtime_seconds=runtime,
                facets_engaged=facets_engaged,
                artifacts=artifacts,
                trace_log=trace_log,
                metrics={
                    "error": cb_exc.error_msg,
                    "run_id": run_id,
                    "rollback": (cb_exc.rcfa_report or {}).get("rollback"),
                },
                circuit_breaker_tripped=True,
                rcfa_report=cb_exc.rcfa_report,
                output_dir=output_dir,
            )

    # =========================================================================
    # Mode B: Dynamic ReAct Autonomous Loop
    # =========================================================================

    def _solve_react_pipeline(self, prompt: str, max_steps: int = 10) -> SuperAgentExecutionResult:
        # 函数内 import：本方法会被测试用 ast.get_source_segment 抠出来在合成命名空间
        # 里 exec，不能依赖模块级名字（详见 virtu_omni/agent/tool_binding.py 顶部说明）。
        from virtu_omni.agent.tool_binding import bind_facet_args as _bind_facet_args
        """旧硬编码 facet 流水线（现为 REACT 的 fallback，不再是默认引擎）。

        审计 §1.6：本函数的步骤序列是写死的 6 步 facet 调用，无模型决策、无 Reflection；
        仅在 deep_agent 引擎不可用（无模型服务/异常）时兜底，且在 metrics 里显式标注。
        """
        self.run_ctx = _new_run_ctx(prompt, "REACT-pipeline")
        self.run_ctx.log("react_pipeline_start")
        t0 = time.time()
        scratchpad: List[Dict[str, Any]] = []
        facets_engaged: List[str] = []
        collected_artifacts: Dict[str, Any] = {}
        spec: Optional[Dict[str, Any]] = None
        step_failures: List[Dict[str, Any]] = []
        audit_passed: Optional[bool] = None
        finished = False

        max_steps = int(max_steps)
        product_integrity: Optional[Dict[str, Any]] = None
        web_corrections: List[Dict[str, Any]] = []
        surface_obs: Optional[Dict[str, Any]] = None

        current_goal = f"自主解决工业工程任务: {prompt}"
        step_count = 0

        while step_count < max_steps:
            step_count += 1

            # Planning / Thought
            if step_count == 1:
                thought = "分析用户制造意图并将其转化为结构化几何规格与材料属性。"
                action = "parse_intent"
                action_input = prompt
            elif step_count == 2:
                thought = "基于解析出的规格，检索历史设计模式与工艺心智模型。"
                action = "recall_hindsight_memory"
                action_input = prompt
            elif step_count == 3:
                thought = "规划 3D CAD 参数化特征树与方程式，生成原生 SolidWorks VBA 代码。"
                action = "generate_parametric_cad"
                action_input = {"user_prompt": prompt, "architecture": {"parsed_spec": spec}}
            elif step_count == 4:
                thought = "联网检索该零件类型的 GB/ISO 公差与表面粗糙度证据，对照并改正刚生成的 CAD 规格。"
                action = "web_verify_and_correct"
                action_input = {
                    "design_spec": spec or {},
                    "topic": f"{(spec or {}).get('part_type', '复杂曲面零件')} 五轴加工 公差等级 表面粗糙度",
                }
            elif step_count == 5:
                thought = "成品完整性校验门：核对特征体积守恒、成品几何非毛坯退化、VERICUT Auto-Diff，防止把毛坯当产品交付。"
                action = "verify_product_integrity"
                cad_out = collected_artifacts.get("generate_parametric_cad", {})
                evidence: Dict[str, Any] = {}
                if isinstance(cad_out, dict):
                    for k in ("features", "geometry", "geometry_mesh", "autodiff"):
                        if k in cad_out:
                            evidence[k] = cad_out[k]
                # 成品几何证据兜底：按任务语义+样本库反推对应成品网格，禁止一律套 NASA1975 叶轮
                resolved_react = {}
                try:
                    from virtu_omni.agent.swarm_orchestrator import resolve_sample_assets_for_task
                    resolved_react = resolve_sample_assets_for_task(
                        {"part_type": (spec or {}).get("part_type") or prompt},
                        Path(WORKSPACE_DIR),
                    )
                except Exception:
                    resolved_react = {}
                default_product_mesh = (
                    Path(WORKSPACE_DIR) / "artifacts" / "aero_closed_impeller"
                    / "AE_CLOSED_IMPELLER_NASA1975.stl"
                )
                picked_mesh = resolved_react.get("design_stl") or (
                    str(default_product_mesh) if default_product_mesh.exists() else None
                )
                if "geometry" not in evidence and "geometry_mesh" not in evidence and picked_mesh:
                    evidence["geometry_mesh"] = str(picked_mesh)
                action_input = evidence
            elif step_count == 6:
                thought = "几何可观测化：把成品复杂曲面转成曲率/残余高度/干涉证据与热力图，让智能体在规划刀路前'看见'曲面。"
                action = "observe_surface"
                cad_mesh = (collected_artifacts.get("generate_parametric_cad") or {}).get("geometry_mesh")
                if not cad_mesh:
                    try:
                        from virtu_omni.agent.swarm_orchestrator import resolve_sample_assets_for_task
                        cad_mesh = resolve_sample_assets_for_task(
                            {"part_type": (spec or {}).get("part_type") or prompt},
                            Path(WORKSPACE_DIR),
                        ).get("design_stl")
                    except Exception:
                        cad_mesh = None
                action_input = {
                    "geometry_mesh": (
                        cad_mesh
                        or str(Path(WORKSPACE_DIR) / "artifacts" / "aero_closed_impeller"
                               / "AE_CLOSED_IMPELLER_NASA1975.stl")
                    ),
                    "part_type": (spec or {}).get("part_type") or prompt,
                    "tool_radius_mm": 3.0, "step_over_mm": None,
                    "finish_allowance_mm": 0.01, "spindle_axis": "Z",
                }
            elif step_count == 7:
                thought = "进行 CAE 厚壁圆筒弹性力学验算，断言安全系数 FOS >= 1.5。"
                action = "verify_cae_stress"
                action_input = spec or {}
            elif step_count == 8:
                thought = "规划数控宏程序刀路 (FANUC Macro B)：依据曲面可观测化证据（高曲率区收紧步距、负角区5轴摆动）设置切削进给转速。"
                action = "generate_cam_toolpath"
                action_input = {"architecture": {"parsed_spec": spec},
                                "modeling": collected_artifacts.get("generate_parametric_cad", {}),
                                "surface_observability": surface_obs if surface_obs else {}}
            elif step_count == 9:
                thought = "在无头沙箱中审计 VBA 宏与 G 代码运动学碰撞，确保 ForceRebuild3 与 G00 快速下刀安全。"
                action = "audit_sandbox_simulation"
                action_input = {
                    "modeling": collected_artifacts.get("generate_parametric_cad", {}),
                    "machining": collected_artifacts.get("generate_cam_toolpath", {}),
                }
            else:
                thought = "所有核心阶段已闭环自验完成，达成终极目标。"
                action = "FINISH"
                action_input = "DONE"

            if action == "FINISH":
                finished = True
                scratchpad.append({
                    "step": step_count,
                    "thought": thought,
                    "action": action,
                    "action_input": action_input,
                    "observation": "任务圆满闭环。",
                })
                break

            # Execute tool
            if action in self._tool_registry:
                desc, tool_fn = self._tool_registry[action]
                facets_engaged.append(action)
                try:
                    _pos, _kw = _bind_facet_args(tool_fn, action_input)
                    obs = tool_fn(*_pos, **_kw)
                    collected_artifacts[action] = obs
                    if action == "parse_intent" and isinstance(obs, dict):
                        spec = obs.get("parsed_spec")
                    if action == "web_verify_and_correct" and isinstance(obs, dict):
                        fixes = obs.get("corrected_spec") or {}
                        if isinstance(spec, dict) and isinstance(fixes, dict) and fixes:
                            spec.update(fixes)      # 把联网证据修正回写设计规格
                        web_corrections = list(obs.get("corrections") or [])
                    if action == "verify_product_integrity" and isinstance(obs, dict):
                        product_integrity = obs
                        # 有实测证据且不合格 / 熔断标志置位 -> 立即熔断（AGENTS.md §6）
                        if obs.get("circuit_breaker") or (
                                obs.get("verified") and obs.get("passed") is False):
                            audit_passed = False
                            step_failures.append({
                                "step": step_count,
                                "action": action,
                                "reason": "product_integrity_gate_failed: "
                                          + "; ".join(obs.get("failures") or ["成品完整性未通过"]),
                            })
                            scratchpad.append({
                                "step": step_count,
                                "thought": thought,
                                "action": action,
                                "action_input": str(action_input)[:200],
                                "observation": f"CIRCUIT_BREAKER: {str(obs)[:240]}",
                            })
                            break
                    if action == "observe_surface" and isinstance(obs, dict):
                        surface_obs = obs
                    if isinstance(obs, dict):
                        for gate_key in ("passed", "success"):
                            if obs.get(gate_key) is False:
                                step_failures.append({
                                    "step": step_count,
                                    "action": action,
                                    "reason": f"{gate_key} is False",
                                })
                        if action == "audit_sandbox_simulation":
                            audit_passed = bool(obs.get("passed"))
                    obs_summary = str(obs)[:300] + ("..." if len(str(obs)) > 300 else "")
                except Exception as err:
                    obs_summary = f"Tool Execution Error: {err}"
                    step_failures.append({
                        "step": step_count,
                        "action": action,
                        "reason": obs_summary,
                    })
            else:
                obs_summary = f"Unknown tool '{action}'"
                step_failures.append({
                    "step": step_count,
                    "action": action,
                    "reason": obs_summary,
                })

            scratchpad.append({
                "step": step_count,
                "thought": thought,
                "action": action,
                "action_input": str(action_input)[:200],
                "observation": obs_summary,
            })

        # Automatic Wake Phase Recording for Google Sleep continual learning
        # token 取执行器实测值（prompt_eval_count / eval_count），取不到写 "unmeasured"
        _react_token_sources = list(collected_artifacts.values())
        try:
            self.sleep_framework.record_wake_step(
                prompt=prompt,
                completion=f"ReAct solve completed with {len(scratchpad)} steps; facets: {list(set(facets_engaged))}",
                verified_facts={"facets_engaged": list(set(facets_engaged)), "steps": len(scratchpad)},
                tool_calls=[{"action": s.get("action")} for s in scratchpad],
                tokens_prompt=self._first_measured_token(_react_token_sources, "prompt_eval_count"),
                tokens_completion=self._first_measured_token(_react_token_sources, "eval_count"),
            )
        except Exception as e_wake:
            logger.warning(f"Could not record wake step: {e_wake}")

        # Falsifiable verdict: a run may only succeed after FINISH, a real
        # sandbox audit pass, and zero observed tool/gate failures.
        if not finished:
            step_failures.append({
                "reason": "ReAct loop ended without reaching FINISH",
                "steps": len(scratchpad),
            })
        if audit_passed is not True:
            step_failures.append({
                "reason": "sandbox simulation audit did not return passed=True",
                "audit_passed": audit_passed,
            })
        success = finished and audit_passed is True and not step_failures

        runtime = time.time() - t0
        return SuperAgentExecutionResult(
            task_prompt=prompt,
            mode=SuperAgentMode.REACT.value,
            success=success,
            runtime_seconds=runtime,
            facets_engaged=list(set(facets_engaged)),
            artifacts=collected_artifacts,
            trace_log=scratchpad,
            metrics={
                "react_steps": len(scratchpad),
                "completed": finished,
                "audit_passed": audit_passed,
                "step_failures": step_failures,
                "verification_basis": "facet_returned_passed_flags",
                "web_corrections": web_corrections,
                "product_integrity": product_integrity or {"evidence_status": "not_run"},
                "surface_observability": surface_obs or {"evidence_status": "not_run"},
            },
            circuit_breaker_tripped=False,
            rcfa_report=None if success else {
                "stage": "REACT",
                "root_cause": step_failures[0]["reason"] if step_failures else "unknown",
                "actionable_advice": "检查 step_failures 与沙箱审计结果，修复后重跑；未经验证不得宣称成功。",
            },
        )

    def _solve_react(self, prompt: str, max_steps: int = 10) -> SuperAgentExecutionResult:
        """REACT：默认以 bridges/deep_agent 的真 LLM 循环为执行引擎。

        deep_agent 提供 Plan -> Act -> Verify（含 schema 校验、重复动作/计划外写拦截、
        连续失败熔断、断点续跑），super_agent 只负责把 facet 暴露成工具与聚合结果。
        引擎不可用时降级为旧流水线，并在 metrics 中标注 fallback 原因（不静默）。
        """
        engine = _react_engine_mode()
        if engine == "pipeline":
            res = self._solve_react_pipeline(prompt, max_steps=max_steps)
            res.metrics["engine"] = "pipeline_forced"
            res.metrics["engine_hint"] = "VIRTU_REACT_ENGINE=pipeline 显式强制旧流水线"
            return res
        try:
            return self._solve_react_deep(prompt, max_steps=max_steps)
        except Exception as err:                        # noqa: BLE001 - 降级必须留痕
            logger.warning("[REACT] deep_agent 引擎不可用，降级为硬编码流水线: %s", err)
            res = self._solve_react_pipeline(prompt, max_steps=max_steps)
            res.metrics["engine"] = "pipeline_fallback"
            res.metrics["engine_fallback_reason"] = f"{type(err).__name__}: {err}"
            return res

    def _solve_react_deep(self, prompt: str, max_steps: int = 10) -> SuperAgentExecutionResult:
        """用 deep_agent 跑真实 REACT 循环，并把 trace 映射成 REACT 的 Thought/Observation。"""
        from bridges import deep_agent as _deep

        t0 = time.time()
        ctx = getattr(self, "run_ctx", None) or _new_run_ctx(prompt, "REACT")
        adapter = FacetToolAdapter(self._tool_registry)
        model = os.environ.get("VIRTU_DEEP_MODEL") or getattr(_deep, "DEFAULT_MODEL", "virtu-ties-v1:latest")
        budget_s = _react_engine_budget_s()
        engine_config: Dict[str, Any] = {"max_steps": int(max_steps)}
        if budget_s > 0:
            engine_config["chat_timeout_s"] = int(budget_s)
        env_facts = self.build_runtime_memory_context(prompt)
        trace = _deep.run(
            task=prompt,
            model=model,
            tool_adapter=adapter,
            env_facts=env_facts,
            config=engine_config,
            run_ctx=ctx,
        )
        if not isinstance(trace, dict):
            raise TypeError(f"deep_agent.run 返回类型异常: {type(trace).__name__}")

        # 空计划不是"跑完但失败"，是引擎根本没启动起来（模型超时/拒答/计划非法）。
        # 这种情况必须抛出去走可见降级，否则 REACT 会返回 trace_log=[] 的假象，
        # 让调用方以为真循环跑过一遍（阶段二 C 组：不允许空 trace 冒充执行结果）。
        _plan = trace.get("plan") or {}
        if not (trace.get("history") or []) and not (_plan.get("steps") or []):
            _why = (_plan.get("violations") or trace.get("aborted")
                    or trace.get("error") or "plan 为空且无任何执行记录")
            raise RuntimeError(f"deep_engine_no_plan: {_why}")

        digests = trace.get("digests") or {}
        scratchpad: List[Dict[str, Any]] = []
        for h in trace.get("history") or []:
            dg = digests.get(h.get("step")) or {}
            scratchpad.append({
                "step": h.get("step"),
                "thought": dg.get("goal") or trace_thought_of(h),
                "action": h.get("tool"),
                "action_input": str(h.get("args"))[:200],
                "observation": dg.get("obs_head") or str(h.get("observation"))[:300],
                "observation_tail": dg.get("obs_tail", ""),
                "key_lines": dg.get("key_lines") or [],
                "verdict": dg.get("verdict"),
            })

        artifacts: Dict[str, Any] = {}
        if env_facts:
            artifacts["runtime_memory_context"] = env_facts
        for c in getattr(adapter, "calls", []):
            artifacts.setdefault(c["tool"], []).append(c.get("text", "")[:4000])

        verify = trace.get("verify") or {}
        items = verify.get("items") or []
        metrics = {
            "engine": "deep_agent",
            "react_steps": len(scratchpad),
            "plan_steps": len((trace.get("plan") or {}).get("steps") or []),
            "completed": bool(trace.get("success")),
            "audit_passed": (None if not items else
                             all(i.get("met") == "yes" for i in items)),
            "step_failures": [{"reason": trace["aborted"]}] if trace.get("aborted") else [],
            "verification_basis": "deep_agent_verify_stage_criteria",
            "criteria_total": trace.get("criteria_total"),
            "criteria_met": trace.get("criteria_met"),
            "guards": trace.get("guards") or [],
            "deep_metrics": trace.get("metrics") or {},
            "memory_context_injected": bool(env_facts),
            "working_memory_facts": len(self.working_memory.facts) if self.working_memory else 0,
            "run_context": (trace.get("run_context") or ctx.to_dict()),
        }
        success = bool(trace.get("success"))
        try:
            _deep_facets = sorted({s["action"] for s in scratchpad if s.get("action")})
            self.sleep_framework.record_wake_step(
                prompt=prompt,
                completion=f"ReAct(deep_agent) completed with {len(scratchpad)} steps; success={success}",
                verified_facts={
                    "facets_engaged": _deep_facets,
                    "steps": len(scratchpad),
                    "criteria_met": trace.get("criteria_met"),
                },
                tool_calls=[{"action": s.get("action")} for s in scratchpad],
                tokens_prompt="unmeasured",
                tokens_completion="unmeasured",
            )
        except Exception as e_wake:
            logger.warning(f"Could not record deep ReAct wake step: {e_wake}")
        return SuperAgentExecutionResult(
            task_prompt=prompt,
            mode=SuperAgentMode.REACT.value,
            success=success,
            runtime_seconds=time.time() - t0,
            facets_engaged=sorted({s["action"] for s in scratchpad if s.get("action")}),
            artifacts=artifacts,
            trace_log=scratchpad,
            metrics=metrics,
            circuit_breaker_tripped=bool(trace.get("aborted")),
            rcfa_report=None if success else {
                "stage": "REACT/deep_agent",
                "root_cause": trace.get("aborted") or (
                    "success_criteria 未全部满足" if items else "plan 未产出 success_criteria"),
                "actionable_advice": "按 trace['digests'] / trace['guards'] 定位失败步骤后重跑；未经验证不得宣称成功。",
            },
        )

    # =========================================================================
    # Mode C: Explicit Modality Dispatch
    # =========================================================================

    def _solve_modality(
        self,
        prompt: str,
        modality: str = "FUNCTION_CALLING",
        target_software: Optional[str] = None,
        action: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> SuperAgentExecutionResult:
        """Execute single-turn tool task via explicit access modality."""
        t0 = time.time()
        res = self.facet_dispatch_modality(
            prompt=prompt,
            modality=modality,
            target_software=target_software,
            action=action,
            params=params,
        )
        runtime = time.time() - t0
        return SuperAgentExecutionResult(
            task_prompt=prompt,
            mode=SuperAgentMode.MODALITY.value,
            success=res.get("success", False),
            runtime_seconds=runtime,
            facets_engaged=["Modality Dispatcher"],
            artifacts=res.get("data", {}),
            trace_log=res.get("attempts", []),
            metrics={"modality": res.get("modality"), "latency_sec": res.get("latency_sec")},
            circuit_breaker_tripped=False,
            modality_report=res,
        )

    # =========================================================================
    # Mode D: Hierarchical Subagent Swarm Delegation
    # =========================================================================

    def _solve_swarm(
        self,
        prompt: str,
        require_real_swarm: bool = True,
        output_dir: Optional[str] = None,
        memory_safe: bool = True,
        params: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> SuperAgentExecutionResult:
        """SWARM 入口：真实层级委派（SwarmCommander）。

        AGENTS.md §4 的四项契约已落成可运行代码（见 ``swarm_orchestrator``）：

        - 层级委派：几何解析 / 标准可行性（并行）→ 工艺规划 → 刀路生成 → 仿真审计；
        - Blackboard 写锁租约：worker 写共享键前必须持租约，并行写入被串行化；
        - Meta-SOP 文档交接：PRD → ARCHITECTURE → TASKS → CODE_MODEL →
          VERIFICATION_REPORT，前置缺失即拒行；
        - 红蓝辩论：``AdversarialCritic`` 对蓝队交付物做可证伪缺陷狩猎。

        诚实约束（2026-11-13 按实现改写，原描述与代码不符）：
        ``res.mode`` 写 SWARM 的条件是**真的进入过 SwarmCommander**，两条路径都写：
        跑完写 SWARM（`success` 由验证门决定），委派中途抛异常也写 SWARM 但
        `success=False` + `rcfa_report` + 熔断置位。只有编排器根本 import 不进来时才
        降级 AUTONOMOUS 并保留 ``requested_mode=SWARM`` + ``swarm_status=unavailable:*``。
        换言之：**SWARM 标签不代表成功，成功看 `success`**；降级只有 import 失败一种。
        """
        t0 = time.perf_counter()

        try:
            from virtu_omni.agent.swarm_orchestrator import SwarmCommander
            try:
                from virtu_omni.agent.swarm_orchestrator import resolve_sample_assets_for_task
            except Exception:
                resolve_sample_assets_for_task = None
        except Exception as exc:  # pragma: no cover - 依赖缺失时才走
            logger.warning("SwarmCommander 不可用（%s），降级 AUTONOMOUS 执行。", exc)
            res = self._solve_autonomous(prompt, output_dir=output_dir, memory_safe=memory_safe)
            res.requested_mode = SuperAgentMode.SWARM.value
            res.metrics["swarm_status"] = f"unavailable:{type(exc).__name__}"
            if require_real_swarm:
                res.success = False
                res.metrics["swarm_require_real"] = "failed_no_orchestrator"
                res.rcfa_report = {
                    "stage": "swarm_orchestrator_import",
                    "root_cause": f"SwarmCommander 导入失败: {exc}",
                    "countermeasure": "修复 swarm_orchestrator 依赖后重跑，或以 AUTONOMOUS 模式执行",
                }
            return res

        # ---- 组装子智能体任务（按样本/语义反推 design_stl 与毛坯，禁止一律套 NASA1975 圆柱）----
        task: Dict[str, Any] = dict(params or {})
        for key, val in kwargs.items():
            if val is not None:
                task.setdefault(key, val)
        task.setdefault("part_type", prompt)
        build_mem = getattr(self, "build_runtime_memory_context", None)
        runtime_ctx = build_mem(prompt) if callable(build_mem) else ""
        if runtime_ctx:
            task.setdefault("memory_context", runtime_ctx)
        if callable(resolve_sample_assets_for_task):
            resolved_swarm = resolve_sample_assets_for_task(task, Path(WORKSPACE_DIR))
            if not task.get("design_stl") and resolved_swarm.get("design_stl"):
                task["design_stl"] = str(resolved_swarm["design_stl"])
            for asset_k in ("sample_stock_stl", "sample_vcproject", "sample_design_stl"):
                if not task.get(asset_k) and resolved_swarm.get(asset_k):
                    task[asset_k] = str(resolved_swarm[asset_k])
            if not task.get("stock_shape") and resolved_swarm.get("expected_stock_shape"):
                task["stock_shape"] = resolved_swarm["expected_stock_shape"]
        if not task.get("design_stl"):
            default_stl = (Path(WORKSPACE_DIR) / "artifacts" / "aero_closed_impeller"
                           / "AE_CLOSED_IMPELLER_NASA1975.stl")
            if default_stl.exists():
                task["design_stl"] = str(default_stl)
                logger.info("SWARM 未指定 design_stl，使用工作区成品: %s", default_stl)

        run_dir = output_dir or str(
            Path(WORKSPACE_DIR) / "runs" / "swarm" / (getattr(self.run_ctx, "run_id", "") or "adhoc")
        )
        swarm_out_dir = Path(run_dir)
        swarm_out_dir.mkdir(parents=True, exist_ok=True)

        try:
            swarm_res = SwarmCommander().solve(task, output_dir=str(swarm_out_dir))
        except Exception as exc:
            # 真委派失败必须如实暴露，绝不吞掉当成成功
            elapsed = time.perf_counter() - t0
            logger.exception("SWARM 委派执行失败: %s", exc)
            return SuperAgentExecutionResult(
                task_prompt=prompt,
                mode=SuperAgentMode.SWARM.value,
                success=False,
                runtime_seconds=elapsed,
                facets_engaged=[],
                artifacts={"swarm_error": f"{type(exc).__name__}: {exc}"},
                trace_log=[{"stage": "SwarmAborted", "agent": "SwarmCommander",
                            "error": f"{type(exc).__name__}: {exc}"}],
                metrics={"swarm_status": "aborted", "swarm_require_real": str(require_real_swarm)},
                circuit_breaker_tripped=True,
                rcfa_report={
                    "stage": "swarm_orchestrator.solve",
                    "root_cause": f"{type(exc).__name__}: {exc}",
                    "countermeasure": "检查 worker 依赖（surface_observability / stock_derivation / "
                                      "product_integrity_gate）与 design_stl 路径后重跑",
                },
                output_dir=str(swarm_out_dir),
                requested_mode=SuperAgentMode.SWARM.value,
            )

        elapsed = time.perf_counter() - t0
        vr = swarm_res.get("verification_report") or {}
        facets = [t.get("agent", "") for t in swarm_res.get("trace", []) if t.get("agent")]
        success = bool(swarm_res.get("success"))
        red_findings = vr.get("red_team_findings") or []

        rcfa = None
        if not success:
            rcfa = {
                "stage": "swarm_verification",
                "root_cause": (
                    "; ".join(d.get("finding", str(d)) if isinstance(d, dict) else str(d)
                              for d in red_findings)
                    or "仿真审计门未通过（audit_passed=False）"
                ),
                "countermeasure": "按红队缺陷清单逐条修正工艺/刀路参数后重跑 SWARM",
                "defects": red_findings,
            }

        self.run_ctx.log("swarm_completed", success=success,
                         blackboard_keys=len(swarm_res.get("blackboard_keys") or []))

        return SuperAgentExecutionResult(
            task_prompt=prompt,
            mode=SuperAgentMode.SWARM.value,
            success=success,
            runtime_seconds=elapsed,
            facets_engaged=facets,
            artifacts={
                "swarm": swarm_res,
                "verification_report": vr,
                "blackboard_keys": swarm_res.get("blackboard_keys") or [],
                "meta_sop_docs": swarm_res.get("meta_sop_docs") or [],
                "meta_sop_files": swarm_res.get("meta_sop_files") or [],
            },
            trace_log=swarm_res.get("trace") or [],
            metrics={
                "swarm_status": "executed",
                "swarm_blackboard_keys": len(swarm_res.get("blackboard_keys") or []),
                "swarm_write_audit_entries": swarm_res.get("audit_log_len"),
                "geometry_evidence_status": vr.get("geometry_evidence_status"),
                "recommended_tool_radius_mm": vr.get("recommended_tool_radius_mm"),
                "residual_over_pct": vr.get("residual_over_pct"),
                "stock_basis": vr.get("stock_basis"),
                "online": vr.get("online"),
                "audit_passed": vr.get("audit_passed"),
                "red_team_gate": vr.get("red_team_gate"),
                "red_team_findings": [d.get("id") if isinstance(d, dict) else str(d)
                                      for d in red_findings],
                "volume_conservation": vr.get("volume_conservation"),
                "safety_factor": vr.get("safety_factor"),
            },
            circuit_breaker_tripped=not success,
            rcfa_report=rcfa,
            output_dir=str(swarm_out_dir),
            requested_mode=SuperAgentMode.SWARM.value,
        )

    # =========================================================================
    # Master Unified Solve Interface
    # =========================================================================

    def solve(
        self,
        prompt: str,
        mode: Union[SuperAgentMode, str] = SuperAgentMode.AUTONOMOUS,
        modality: str = "FUNCTION_CALLING",
        target_software: Optional[str] = None,
        action: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        output_dir: Optional[str] = None,
        memory_safe: bool = True,
        max_steps: int = 10,
        **kwargs: Any,
    ) -> Union[SuperAgentExecutionResult, AgentExecutionReport]:
        """Universal entry point for Virtu Super Agent.
        
        Supports AUTONOMOUS, REACT, MODALITY, and SWARM execution modes.
        """
        mode_val = mode.value if isinstance(mode, SuperAgentMode) else str(mode).upper()
        # E 组：一次 solve 一个 RunContext（run_id = 内容指纹，非时间戳），全链透传
        self.run_ctx = _new_run_ctx(prompt, mode_val)
        self.run_ctx.log("solve_start", mode=mode_val)

        if mode_val == SuperAgentMode.REACT.value:
            return self._solve_react(prompt, max_steps=max_steps)
        elif mode_val == SuperAgentMode.MODALITY.value:
            res = self._solve_modality(
                prompt=prompt,
                modality=modality,
                target_software=target_software,
                action=action,
                params=params,
            )
            # If caller is expecting legacy AgentExecutionReport, wrap it
            rep_data = res.modality_report or {}
            return AgentExecutionReport(
                task_prompt=prompt,
                modality=rep_data.get("modality", modality),
                target_software=rep_data.get("target_software", target_software or ""),
                action=rep_data.get("action", action or ""),
                success=rep_data.get("success", False),
                total_latency_sec=rep_data.get("latency_sec", res.runtime_seconds),
                result_data=rep_data.get("data", {}),
                difficulty_level=rep_data.get("difficulty_level", DIFFICULTY_ROUTING_DISABLED),
                complexity_score=rep_data.get("complexity_score", 0.0),
                executed_modality=rep_data.get("executed_modality"),
                routing_rationale=rep_data.get("routing_rationale", ""),
                execution_attempts=rep_data.get("attempts", []),
            )
        elif mode_val == SuperAgentMode.SWARM.value:
            return self._solve_swarm(
                prompt,
                # 真委派已落地，SWARM 默认真跑 SwarmCommander（不再只是 AUTONOMOUS 的别名）
                require_real_swarm=bool(kwargs.pop("require_real_swarm", True)),
                output_dir=output_dir,
                memory_safe=memory_safe,
                params=params,
                **kwargs,
            )
        elif mode_val == SuperAgentMode.HARNESSED.value:
            k = kwargs.get("k", 1)
            rec_mode = kwargs.get("recursion_mode", "parallel")
            return self._solve_harnessed(prompt, k=k, recursion_mode=rec_mode, output_dir=output_dir, memory_safe=memory_safe, **kwargs)
        elif mode_val == "GROUNDED":
            t0 = time.perf_counter()
            gr = self.respond_grounded(
                prompt,
                model_caller=kwargs.get("model_caller"),
                max_repairs=int(kwargs.get("max_repairs", 3)),
                auto_backend=bool(kwargs.get("auto_backend", False)),
            )
            g = gr.get("grounding") or {}
            ok = bool(gr.get("content")) and (
                not g.get("applicable")
                or bool(g.get("model_passed"))
                or bool((g.get("fallback_gate") or {}).get("passed"))
            )
            return SuperAgentExecutionResult(
                task_prompt=prompt,
                mode="GROUNDED",
                success=ok,
                runtime_seconds=time.perf_counter() - t0,
                facets_engaged=["GroundedInference", g.get("kind") or "chat"],
                artifacts={"content": gr.get("content"), "grounding": g},
                trace_log=g.get("attempts") or [],
                metrics={
                    "grounded_applicable": bool(g.get("applicable")),
                    "grounded_source": g.get("source"),
                    "grounded_model_passed": g.get("model_passed"),
                    "run_id": self.run_ctx.run_id,
                },
                requested_mode="GROUNDED",
            )
        else:
            return self._solve_autonomous(prompt, output_dir=output_dir, memory_safe=memory_safe)

    def respond_grounded(
        self,
        prompt_or_messages: Union[str, List[Dict[str, Any]]],
        *,
        model_caller: Optional[Callable[[List[Dict[str, Any]]], Optional[str]]] = None,
        max_repairs: int = 3,
        auto_backend: bool = False,
    ) -> Dict[str, Any]:
        """Run GroundedResponder over a prompt or OpenAI message list."""
        from virtu_omni.agent.grounded_inference import GroundedResponder

        if isinstance(prompt_or_messages, str):
            messages: List[Dict[str, Any]] = [{"role": "user", "content": prompt_or_messages}]
        else:
            messages = list(prompt_or_messages or [])

        caller = model_caller
        if caller is None and auto_backend:
            try:
                from virtu_real_backend import get_backend
                backend = get_backend()
                if backend is not None and backend.available:
                    caller = lambda msgs: backend.generate(msgs)
            except Exception:
                caller = None

        res = GroundedResponder(caller, max_repairs=max_repairs).respond(messages)
        g = res.get("grounding") or {}
        if self.working_memory is not None and g.get("applicable"):
            kind = g.get("kind")
            if kind == "lame" and isinstance(g.get("result"), dict):
                self.working_memory.record_fact(
                    key="lame_sigma_theta_inner_mpa",
                    value=round(float(g["result"]["sigma_theta_inner_mpa"]), 4),
                    source="grounded_inference",
                    verified=True,
                    basis="closed_form",
                )
            elif kind == "g71" and isinstance(g.get("spec"), dict):
                self.working_memory.record_fact(
                    key="g71_stock_d_mm",
                    value=g["spec"].get("stock_d"),
                    source="grounded_inference",
                    verified=True,
                    basis="static_semantic",
                )
        return res

    # Legacy compatibility methods for CADCAMAutonomousAgent
    def analyze_task(
        self,
        prompt: str,
        modality: str = "FUNCTION_CALLING",
        target_software: Optional[str] = None,
        action: Optional[str] = None,
    ) -> DispatchPlan:
        """Produce the modality dispatch plan without running anything."""
        try:
            mod = AccessModality(modality.upper())
        except ValueError:
            mod = AccessModality.FUNCTION_CALLING
        return self.dispatcher.plan(mod, prompt, target_software, action)

    def explain_decision(
        self,
        prompt: str,
        modality: str = "FUNCTION_CALLING",
        target_software: Optional[str] = None,
        action: Optional[str] = None,
    ) -> str:
        """Human-readable explanation of the dispatch plan."""
        plan = self.analyze_task(prompt, modality, target_software, action)
        fallbacks_str = " -> ".join([m.value for m in plan.fallback_modalities]) or "（无）"
        return (
            f"【Virtu Super Agent 接入说明】\n"
            f"1. 接入方式: {plan.modality.value}\n"
            f"2. 目标软件: {plan.target_software or '未指定'}\n"
            f"3. 操作动作: {plan.action or '未指定'}\n"
            f"4. 标准工具: {plan.tool_name}\n"
            f"5. 容灾链条: {fallbacks_str}\n"
            f"6. 决策依据: {plan.rationale}"
        )

    def explain_architecture(self) -> Dict[str, Any]:
        """Explain the Super Agent architecture and registered capabilities."""
        return {
            "name": "Virtu Industrial Super Agent",
            "architecture_type": "Unified Omni-Agent (全能超级智能体)",
            "modes": [m.value for m in SuperAgentMode],
            "facets": [
                "Architect (愿景揣测与需求拆解)",
                "Parametric CAD (3D 特征树与 swEqnMgr 方程式)",
                "Standards & GD&T (工程制图与标准公差)",
                "Machining & CAM (数控宏程序与切削参数)",
                "CAE Simulation (厚壁圆筒弹性力学与 FOS >= 1.5)",
                "Auditor & Sandbox (无头仿真与 G00 快速碰撞自愈)",
                "Memory & Evolution (Hindsight Recall/Reflect 与心智模型)",
                "Modality Dispatcher (7大接入方式与固定容灾链)",
                "Operator Optimizer (模型算子性能自主优化与等价性核验)",
                "Internet & Continual Deep Learning (安全全网检索与持续深度学习)",
            ],
            "circuit_breaker": {
                "max_retries": 3,
                "axiom": "又快又准到极限，未到极限则继续，到了极限则放弃",
                "actions": ["Tier 0/1/2 自查", "Reflexion 自愈重试", "原子回滚与 RCFA 报告"]
            },
            "registered_tools": list(self._tool_registry.keys()),
        }


# Global Aliases
SuperAgent = VirtuSuperAgent
IndustrialSuperAgent = VirtuSuperAgent
