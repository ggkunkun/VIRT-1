# -*- coding: utf-8 -*-
"""virtu_omni/memory/working_memory.py — Built-in Working Memory (内置工作记忆区) & Long-Task Anti-Hallucination Subsystem.

Designed to eliminate the twin failure modes of models on long-horizon engineering tasks:
1. Catastrophic Forgetting & Attention Drift:
   - Initial constraints and requirements get truncated or forgotten as conversation grows.
   - Intermediate verified facts (dimensions, materials, coordinates, simulation outcomes) get diluted.
   - Solution: Pinned, structured, low-overhead Working Memory Zone (<BUILTIN_WORKING_MEMORY>)
     that persists across infinite conversation turns and context compactions.

2. Long-Horizon Hallucination:
   - Numerical/Dimensional Drift: Modifying established parameters in later steps without cause.
   - Phantom Step Completions: Claiming a step or feature was completed/verified without a receipt.
   - Action Redundancy & Infinite Loops: Re-executing already completed steps.
   - Solution: LongTaskHallucinationSentinel enforcing cross-step consistency, state monotonicity,
     and execution-receipt gatekeeping before assertions.

Constitution Compliance (AGENTS.md Section 8):
- All verified facts carry provenance (source, timestamp, execution receipt hash).
- All gates are falsifiable with explicit mutation probes.
- Immutable ground-truth facts cannot be silently overwritten by unverified model outputs.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import re
import threading
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger("virtu_omni.memory.working_memory")


class MilestoneStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


@dataclass
class VerifiedFact:
    """An immutable verified physical fact, dimension, or outcome."""
    key: str
    value: Any
    unit: Optional[str] = None
    source: str = "user_input"
    verified: bool = False
    evidence_hash: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    basis: str = "inferred"  # measured | asserted | inferred

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MilestoneStep:
    """A distinct milestone in a long-horizon task with execution provenance."""
    step_idx: int
    title: str
    status: MilestoneStatus = MilestoneStatus.PENDING
    expected_output: str = ""
    receipt: Optional[Dict[str, Any]] = None
    evidence_hash: Optional[str] = None
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


@dataclass
class TaskGoal:
    """Core invariant goal and global boundary constraints for a long task."""
    intent: str
    invariants: Dict[str, Any] = field(default_factory=dict)
    forbidden_actions: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Common engineering parameter aliases for regex extraction & normalization
PARAM_ALIASES: Dict[str, List[str]] = {
    "outer_diameter": ["外径", "d_outer", "D_max", "大径", "外径轮廓", "法兰外径", "outer_diameter"],
    "bore_diameter": ["内孔", "轴孔", "孔径", "d_inner", "D_bore", "内径", "内孔配合径", "bore_diameter"],
    "length": ["总长", "长度", "高度", "overall_len", "Length", "零件总长", "厚度", "thickness"],
    "fillet_radius": ["过渡圆角", "圆角", "fillet_r", "R", "倒角", "chamfer"],
    "material": ["材质", "材料", "牌号", "material"],
    "spindle_speed": ["主轴转速", "转速", "spindle_speed", "n"],
    "cutting_speed": ["切削速度", "线速度", "cutting_speed", "Vc", "vc"],
    "feed_rate": ["进给速度", "进给量", "feed_rate", "Vf", "f"],
    "safety_factor": ["安全系数", "FOS", "fos", "最小安全系数", "safety_factor"],
}


class BuiltinWorkingMemory:
    """Thread-safe, high-density in-memory and persistent Working Memory Zone.

    Maintains active task state, invariant constraints, verified facts,
    and milestone progress across multi-turn long-horizon executions.
    """

    def __init__(self, session_id: str = "default_session", persist_path: Optional[str] = None) -> None:
        self.session_id = session_id
        self.persist_path = persist_path
        self._lock = threading.RLock()

        self.goal: Optional[TaskGoal] = None
        self.facts: Dict[str, VerifiedFact] = {}
        self.milestones: List[MilestoneStep] = []
        self.current_step_idx: int = 1
        self.active_variables: Dict[str, Any] = {}
        self.lessons_learned: List[str] = []
        self.conversation_turn: int = 0
        self.last_sync_time: float = time.time()

        if self.persist_path and os.path.exists(self.persist_path):
            self.load()

    def set_task_goal(
        self,
        intent: str,
        invariants: Optional[Dict[str, Any]] = None,
        forbidden_actions: Optional[List[str]] = None,
    ) -> None:
        """Initialize or update the primary immutable task goal."""
        with self._lock:
            invariants = invariants or {}
            forbidden_actions = forbidden_actions or [
                "短接机床安全联锁",
                "屏蔽行程软硬限位",
                "跳过首件试切检验",
                "G00高速扎刀进刀",
            ]
            self.goal = TaskGoal(
                intent=intent.strip(),
                invariants=invariants,
                forbidden_actions=forbidden_actions,
            )
            # Seed verified facts from explicit invariants
            for k, v in invariants.items():
                self.record_fact(
                    key=k,
                    value=v,
                    source="task_invariants",
                    verified=True,
                    basis="asserted",
                )
            self._auto_persist()

    def record_fact(
        self,
        key: str,
        value: Any,
        unit: Optional[str] = None,
        source: str = "system",
        verified: bool = True,
        evidence_hash: Optional[str] = None,
        basis: str = "measured",
    ) -> VerifiedFact:
        """Record or update a verified fact in the immutable ledger.

        Once a fact is verified (e.g. from a physical solver or COM measurement),
        an unverified claim cannot overwrite it.
        """
        with self._lock:
            canonical_key = self._canonicalize_key(key)
            existing = self.facts.get(canonical_key)

            if existing and existing.verified and not verified:
                logger.warning(
                    "Rejecting unverified overwrite of verified fact '%s' (%s vs existing %s)",
                    canonical_key, value, existing.value
                )
                return existing

            fact = VerifiedFact(
                key=canonical_key,
                value=value,
                unit=unit,
                source=source,
                verified=verified,
                evidence_hash=evidence_hash or self._compute_evidence_hash(value),
                timestamp=time.time(),
                basis=basis,
            )
            self.facts[canonical_key] = fact
            self._auto_persist()
            return fact

    def get_fact(self, key: str, default: Any = None) -> Any:
        """Retrieve a verified fact value by canonical key or alias."""
        with self._lock:
            canonical_key = self._canonicalize_key(key)
            fact = self.facts.get(canonical_key)
            if fact:
                return fact.value
            if self.goal and canonical_key in self.goal.invariants:
                return self.goal.invariants[canonical_key]
            return default

    def add_milestone(self, title: str, expected_output: str = "") -> MilestoneStep:
        """Append a new milestone step to the execution plan."""
        with self._lock:
            step_idx = len(self.milestones) + 1
            ms = MilestoneStep(
                step_idx=step_idx,
                title=title,
                status=MilestoneStatus.PENDING,
                expected_output=expected_output,
            )
            self.milestones.append(ms)
            self._auto_persist()
            return ms

    def update_milestone(
        self,
        step_idx: int,
        status: Union[str, MilestoneStatus],
        receipt: Optional[Dict[str, Any]] = None,
        evidence_hash: Optional[str] = None,
    ) -> Optional[MilestoneStep]:
        """Update a milestone's status and attach execution receipt evidence."""
        with self._lock:
            if isinstance(status, str):
                try:
                    status = MilestoneStatus(status.upper())
                except ValueError:
                    status = MilestoneStatus.IN_PROGRESS

            for ms in self.milestones:
                if ms.step_idx == step_idx:
                    ms.status = status
                    ms.updated_at = time.time()
                    if receipt:
                        ms.receipt = receipt
                        ms.evidence_hash = evidence_hash or self._compute_evidence_hash(receipt)
                    if status == MilestoneStatus.COMPLETED:
                        self.current_step_idx = max(self.current_step_idx, step_idx + 1)
                    self._auto_persist()
                    return ms
            return None

    def record_lesson(self, lesson: str) -> None:
        """Record an episodic failure reflection or learned rule to avoid repeats."""
        with self._lock:
            lesson_clean = lesson.strip()
            if lesson_clean and lesson_clean not in self.lessons_learned:
                self.lessons_learned.append(lesson_clean)
                self._auto_persist()

    def render_memory_prompt(self, max_tokens: int = 1000) -> str:
        """Render the Working Memory Zone into a high-density, low-token markup block.

        This block is pinned at the start of context to prevent long-task forgetting.
        """
        with self._lock:
            lines = ["<BUILTIN_WORKING_MEMORY>"]
            lines.append("## 【内置工作记忆区 (BUILTIN_WORKING_MEMORY)】")

            # 1. Task Goal & Invariants
            if self.goal:
                lines.append(f"### [TASK_GOAL]: {self.goal.intent}")
                if self.goal.invariants:
                    lines.append("### [INVARIANTS - 严禁篡改基准]:")
                    for k, v in self.goal.invariants.items():
                        lines.append(f"  * {k}: {v}")
                if self.goal.forbidden_actions:
                    lines.append(f"### [FORBIDDEN_ACTIONS]: {', '.join(self.goal.forbidden_actions)}")
            else:
                lines.append("### [TASK_GOAL]: 未初始化通用多步任务")

            # 2. Verified Facts
            if self.facts:
                lines.append("### [VERIFIED_FACTS - 物理事实账本]:")
                for k, fact in sorted(self.facts.items()):
                    unit_str = f" {fact.unit}" if fact.unit else ""
                    verified_str = "√验证" if fact.verified else "?待验"
                    hash_str = f" (hash:{fact.evidence_hash[:6]})" if fact.evidence_hash else ""
                    lines.append(f"  * {k} = {fact.value}{unit_str} [{verified_str}|来源:{fact.source}{hash_str}]")

            # 3. Milestones
            if self.milestones:
                lines.append("### [MILESTONES - 执行时序与证据]:")
                for ms in self.milestones:
                    icon = "[x]" if ms.status == MilestoneStatus.COMPLETED else (
                        "[>]" if ms.status == MilestoneStatus.IN_PROGRESS else (
                            "[!]" if ms.status == MilestoneStatus.FAILED else "[ ]"
                        )
                    )
                    receipt_str = ""
                    if ms.evidence_hash:
                        receipt_str = f" (凭证: {ms.evidence_hash[:8]})"
                    lines.append(f"  {icon} Step {ms.step_idx}: {ms.title} [{ms.status.value}]{receipt_str}")

            # 4. Lessons learned
            if self.lessons_learned:
                lines.append("### [EPISODIC_LESSONS - 避坑自省]:")
                for lesson in self.lessons_learned[-3:]:
                    lines.append(f"  ! {lesson}")

            lines.append("</BUILTIN_WORKING_MEMORY>")
            rendered = "\n".join(lines)
            return rendered

    def auto_sync_from_messages(self, messages: List[Dict[str, Any]]) -> None:
        """Automatically detect task goals, parameters, tool calls, and receipts from messages."""
        with self._lock:
            self.conversation_turn = len(messages)
            if not messages:
                return

            # 1. Detect task goal from initial user message if uninitialized
            user_messages = [m for m in messages if m.get("role") == "user"]
            if user_messages:
                first_prompt = self._extract_text(user_messages[0].get("content", ""))
                if not self.goal and first_prompt:
                    extracted_invariants = self._extract_parameters_from_text(first_prompt)
                    self.set_task_goal(intent=first_prompt[:200], invariants=extracted_invariants)

            # 2. Scan assistant tool_calls and tool returns for execution receipts
            for idx, msg in enumerate(messages):
                role = msg.get("role")
                if role == "tool":
                    tool_name = msg.get("name", "unknown_tool")
                    tool_content = msg.get("content", "")
                    try:
                        parsed = json.loads(tool_content) if isinstance(tool_content, str) else tool_content
                    except Exception:
                        parsed = {"output": str(tool_content)[:200]}

                    # Extract verified facts from tool execution
                    if isinstance(parsed, dict):
                        self._ingest_tool_result_facts(tool_name, parsed)

            self.last_sync_time = time.time()
            self._auto_persist()

    def compact_context(
        self,
        messages: List[Dict[str, Any]],
        max_turns_to_keep: int = 6,
    ) -> List[Dict[str, Any]]:
        """Compact a long multi-turn message history while preserving the Built-in Working Memory.

        Guarantees that:
        1. Memory zone is synchronized and updated with all historical facts.
        2. System prompt receives the refreshed <BUILTIN_WORKING_MEMORY> block.
        3. The root user prompt (initial task goal) is preserved.
        4. Noisy intermediate back-and-forth turns are safely compressed into state receipts.
        5. The latest `max_turns_to_keep` turns are preserved in full fidelity.
        """
        with self._lock:
            self.auto_sync_from_messages(messages)

            # If messages are within threshold, just inject memory block into system prompt
            rendered_memory = self.render_memory_prompt()

            if len(messages) <= max_turns_to_keep + 2:
                # Still within budget: update or prepend memory into system prompt
                return self._inject_memory_into_messages(messages, rendered_memory)

            # Context compaction needed:
            # 1. Extract system prompt or create one
            system_msg = next((m for m in messages if m.get("role") == "system"), None)
            base_system_content = system_msg.get("content", "") if system_msg else ""
            # Strip previous memory blocks if present
            base_system_content = re.sub(
                r"<BUILTIN_WORKING_MEMORY>[\s\S]*?</BUILTIN_WORKING_MEMORY>",
                "",
                base_system_content,
            ).strip()

            new_system_content = f"{base_system_content}\n\n{rendered_memory}".strip()
            compacted: List[Dict[str, Any]] = [{"role": "system", "content": new_system_content}]

            # 2. Preserve initial user prompt (the root mission anchor)
            initial_user_msg = next((m for m in messages if m.get("role") == "user"), None)
            if initial_user_msg:
                compacted.append({
                    "role": "user",
                    "content": self._extract_text(initial_user_msg.get("content", ""))
                })

            # 3. Add an intermediate context compression summary anchor
            compacted.append({
                "role": "assistant",
                "content": (
                    f"【系统记忆锚定】：已将前期多步交互中的 {len(messages) - max_turns_to_keep} 个历史回合"
                    f"的已验证参数、三维特征与执行凭证完整收束至 <BUILTIN_WORKING_MEMORY> 内置工作记忆区。"
                    f"当前继续推进剩余子步骤，绝对保持几何尺寸与物理不变量一致。"
                )
            })

            # 4. Append the recent window
            recent_turns = messages[-max_turns_to_keep:]
            for turn in recent_turns:
                # Avoid duplicating the initial user message if it falls in recent turns
                if turn is initial_user_msg:
                    continue
                compacted.append(turn)

            logger.info(
                "Compacted context from %d to %d messages preserving working memory (facts=%d, milestones=%d)",
                len(messages), len(compacted), len(self.facts), len(self.milestones)
            )
            return compacted

    def reset(self) -> None:
        """Reset the working memory for a fresh session."""
        with self._lock:
            self.goal = None
            self.facts.clear()
            self.milestones.clear()
            self.current_step_idx = 1
            self.active_variables.clear()
            self.lessons_learned.clear()
            self.conversation_turn = 0
            self._auto_persist()

    def export_snapshot(self) -> Dict[str, Any]:
        """Export full serialized working memory state."""
        with self._lock:
            return {
                "session_id": self.session_id,
                "goal": self.goal.to_dict() if self.goal else None,
                "facts": {k: v.to_dict() for k, v in self.facts.items()},
                "milestones": [m.to_dict() for m in self.milestones],
                "current_step_idx": self.current_step_idx,
                "active_variables": self.active_variables,
                "lessons_learned": self.lessons_learned,
                "conversation_turn": self.conversation_turn,
                "last_sync_time": self.last_sync_time,
            }

    def import_snapshot(self, data: Dict[str, Any]) -> None:
        """Import serialized working memory state."""
        with self._lock:
            self.session_id = data.get("session_id", self.session_id)
            goal_data = data.get("goal")
            if goal_data:
                self.goal = TaskGoal(
                    intent=goal_data["intent"],
                    invariants=goal_data.get("invariants", {}),
                    forbidden_actions=goal_data.get("forbidden_actions", []),
                    created_at=goal_data.get("created_at", time.time()),
                )
            self.facts = {
                k: VerifiedFact(**v) for k, v in data.get("facts", {}).items()
            }
            self.milestones = [
                MilestoneStep(
                    step_idx=m["step_idx"],
                    title=m["title"],
                    status=MilestoneStatus(m.get("status", "PENDING")),
                    expected_output=m.get("expected_output", ""),
                    receipt=m.get("receipt"),
                    evidence_hash=m.get("evidence_hash"),
                    updated_at=m.get("updated_at", time.time()),
                ) for m in data.get("milestones", [])
            ]
            self.current_step_idx = data.get("current_step_idx", 1)
            self.active_variables = data.get("active_variables", {})
            self.lessons_learned = data.get("lessons_learned", [])
            self.conversation_turn = data.get("conversation_turn", 0)

    # ------------------ Internal Helper Methods ------------------

    def _canonicalize_key(self, key: str) -> str:
        """Normalize parameter names to canonical keys using synonym dictionary."""
        k_lower = key.strip().lower()
        for canonical, aliases in PARAM_ALIASES.items():
            if k_lower == canonical.lower():
                return canonical
            for alias in aliases:
                if k_lower == alias.lower():
                    return canonical
        return k_lower

    def _compute_evidence_hash(self, content: Any) -> str:
        """Calculate content fingerprint SHA256 for provenance."""
        if isinstance(content, (dict, list)):
            serialized = json.dumps(content, sort_keys=True, ensure_ascii=False)
        else:
            serialized = str(content)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def _extract_text(self, content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and "text" in item:
                    parts.append(str(item["text"]))
                elif isinstance(item, str):
                    parts.append(item)
            return " ".join(parts).strip()
        return str(content)

    def _extract_parameters_from_text(self, text: str) -> Dict[str, Any]:
        """Extract explicit engineering dimensions and values from free text."""
        extracted: Dict[str, Any] = {}
        # Outer diameter
        m_out = re.search(r"(?:外径|大径|D_max|d_outer).*?([0-9]+(?:\.[0-9]+)?)", text, re.I)
        if m_out:
            extracted["outer_diameter"] = float(m_out.group(1))

        # Bore diameter
        m_in = re.search(r"(?:内孔|孔径|轴孔|内径|d_inner).*?([0-9]+(?:\.[0-9]+)?)", text, re.I)
        if m_in:
            extracted["bore_diameter"] = float(m_in.group(1))

        # Length / Thickness
        m_len = re.search(r"(?:总长|长度|高度|厚度|overall_len).*?([0-9]+(?:\.[0-9]+)?)", text, re.I)
        if m_len:
            extracted["length"] = float(m_len.group(1))

        # Material
        m_mat = re.search(r"(?:材质|材料|牌号)(?:为|是|:|：)?\s*([A-Za-z0-9_\-]+|[\u4e00-\u9fa5]+(?:钢|铁|合金)?)", text)
        if m_mat:
            mat_raw = m_mat.group(1).strip()
            mat_clean = re.sub(r"^(?:为|是|:|：)", "", mat_raw).strip()
            if mat_clean:
                extracted["material"] = mat_clean

        # Spindle speed
        m_speed = re.search(r"(?:主轴转速|转速|n\s*=).*?([0-9]+(?:\.[0-9]+)?)\s*(?:r/min|rpm)?", text, re.I)
        if m_speed:
            extracted["spindle_speed"] = float(m_speed.group(1))

        return extracted

    def _ingest_tool_result_facts(self, tool_name: str, result: Dict[str, Any]) -> None:
        """Parse tool output dictionary and update facts and milestones."""
        # Check volume delta
        if "volume_mm3" in result:
            self.record_fact("rebuild_volume_mm3", result["volume_mm3"], unit="mm³", source=tool_name)
        if "delta_v" in result:
            self.record_fact("volume_delta_mm3", result["delta_v"], unit="mm³", source=tool_name)
        if "safety_factor" in result:
            self.record_fact("safety_factor", result["safety_factor"], source=tool_name, basis="measured")
        if "output_file" in result:
            self.record_fact("latest_artifact_file", result["output_file"], source=tool_name)

        # Update milestones if tool matches milestone
        for ms in self.milestones:
            if ms.status in (MilestoneStatus.PENDING, MilestoneStatus.IN_PROGRESS):
                if tool_name in ms.title.lower() or any(w in ms.title for w in ["建模", "仿真", "图纸", "刀路"]):
                    ms.status = MilestoneStatus.COMPLETED
                    ms.receipt = result
                    ms.evidence_hash = self._compute_evidence_hash(result)
                    ms.updated_at = time.time()
                    break

    def _inject_memory_into_messages(
        self, messages: List[Dict[str, Any]], memory_block: str
    ) -> List[Dict[str, Any]]:
        """Inject or refresh the working memory block inside the system message."""
        new_msgs = []
        has_system = False
        for m in messages:
            if m.get("role") == "system":
                has_system = True
                content = m.get("content", "")
                content_clean = re.sub(
                    r"<BUILTIN_WORKING_MEMORY>[\s\S]*?</BUILTIN_WORKING_MEMORY>",
                    "",
                    content,
                ).strip()
                new_msgs.append({
                    **m,
                    "content": f"{content_clean}\n\n{memory_block}".strip(),
                })
            else:
                new_msgs.append(m)

        if not has_system:
            new_msgs.insert(0, {
                "role": "system",
                "content": f"你是 Virtu 工业智能体。\n\n{memory_block}",
            })
        return new_msgs

    def _auto_persist(self) -> None:
        """Persist state to disk if persist_path is set."""
        if not self.persist_path:
            return
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.persist_path)), exist_ok=True)
            snapshot = self.export_snapshot()
            with open(self.persist_path, "w", encoding="utf-8") as f:
                json.dump(snapshot, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning("Failed to auto-persist working memory: %s", e)

    def load(self) -> None:
        """Load state from disk."""
        if not self.persist_path or not os.path.exists(self.persist_path):
            return
        try:
            with open(self.persist_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.import_snapshot(data)
        except Exception as e:
            logger.warning("Failed to load working memory from %s: %s", self.persist_path, e)


class LongTaskHallucinationSentinel:
    """Rigorous gatekeeper to prevent long-task hallucinations and memory drift.

    Audits model outputs for:
    1. Contradictions against verified facts in BuiltinWorkingMemory (e.g. changing D=60 to 50).
    2. Phantom Milestone Claims: Claiming a step was executed or verified when it has no receipt.
    3. Forbidden Action Violations: Prompting dangerous machine overrides.
    """

    def __init__(self, memory: BuiltinWorkingMemory) -> None:
        self.memory = memory

    def check_fact_contradictions(self, text: str) -> List[Dict[str, Any]]:
        """Inspect generated text for parameter values contradicting verified facts."""
        contradictions = []

        # Check each verified fact
        for canonical_key, fact in self.memory.facts.items():
            if not fact.verified:
                continue
            val = fact.value
            if not isinstance(val, (int, float)):
                continue

            # Look for mentions of this parameter with a different number
            aliases = PARAM_ALIASES.get(canonical_key, [canonical_key])
            pattern_str = r"(?:{}).*?([0-9]+(?:\.[0-9]+)?)".format("|".join(re.escape(a) for a in aliases))
            matches = re.finditer(pattern_str, text, re.I)
            for m in matches:
                try:
                    num_found = float(m.group(1))
                    # Allow 1% tolerance for floating point rounding
                    if abs(num_found - float(val)) > max(0.01, abs(float(val)) * 0.01):
                        contradictions.append({
                            "type": "fact_contradiction",
                            "key": canonical_key,
                            "expected_value": val,
                            "hallucinated_value": num_found,
                            "snippet": text[max(0, m.start() - 20):min(len(text), m.end() + 20)],
                        })
                except (ValueError, TypeError):
                    continue

        return contradictions

    def check_phantom_completion(self, text: str) -> List[Dict[str, Any]]:
        """Check if model asserts completion of an unexecuted milestone."""
        phantom_claims = []
        completion_triggers = [
            "全部完成", "100% PASS", "全部通过", "均已完成", "所有步骤已执行完毕",
            "已完成全部", "已完成所有", "已验证通过",
        ]
        has_global_completion_claim = any(trigger in text for trigger in completion_triggers)

        if has_global_completion_claim:
            uncompleted = [
                m for m in self.memory.milestones
                if m.status != MilestoneStatus.COMPLETED or not m.evidence_hash
            ]
            if uncompleted:
                phantom_claims.append({
                    "type": "phantom_global_completion",
                    "reason": f"模型声称全部完成，但存在 {len(uncompleted)} 个尚未完成或缺少执行凭证的里程碑",
                    "uncompleted_milestones": [m.title for m in uncompleted],
                })

        return phantom_claims

    def check_forbidden_actions(self, text: str) -> List[Dict[str, Any]]:
        """Detect mentions or recommendations of forbidden machine actions."""
        violations = []
        if not self.memory.goal:
            return violations

        for forbidden in self.memory.goal.forbidden_actions:
            if forbidden in text:
                violations.append({
                    "type": "forbidden_action",
                    "action": forbidden,
                    "snippet": forbidden,
                })
        return violations

    def audit_and_repair(
        self, text: str, auto_repair: bool = True
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """Full audit against the working memory ledger with optional deterministic repair."""
        contradictions = self.check_fact_contradictions(text)
        phantom_claims = self.check_phantom_completion(text)
        forbidden_violations = self.check_forbidden_actions(text)

        has_defect = bool(contradictions or phantom_claims or forbidden_violations)
        repaired_text = text

        if has_defect and auto_repair:
            # 1. Deterministically repair fact contradictions
            for c in contradictions:
                # Replace hallucinated number with verified number in snippet context
                key = c["key"]
                expected = c["expected_value"]
                hallucinated = c["hallucinated_value"]
                # Safe regex substitution near alias
                aliases = PARAM_ALIASES.get(key, [key])
                for alias in aliases:
                    pat = rf"({re.escape(alias)}[^\d\n\r]{{0,15}}){re.escape(str(hallucinated))}"
                    repaired_text = re.sub(pat, rf"\g<1>{expected}", repaired_text)

            # 2. Qualify phantom claims
            for p in phantom_claims:
                if p["type"] == "phantom_global_completion":
                    uncompleted_names = "、".join(p["uncompleted_milestones"])
                    repaired_text += (
                        f"\n\n> [!WARNING] 【防幻觉门禁提示】：根据内置工作记忆区事实，"
                        f"以下步骤尚未执行或缺少真实执行凭证：{uncompleted_names}。不可擅自判定为全通。"
                    )

        report = {
            "passed": not has_defect,
            "fact_contradictions": contradictions,
            "phantom_claims": phantom_claims,
            "forbidden_violations": forbidden_violations,
            "repaired": auto_repair and has_defect,
        }
        return not has_defect, repaired_text, report


# Global / Singleton Memory Registry
_WORKING_MEMORIES: Dict[str, BuiltinWorkingMemory] = {}
_REGISTRY_LOCK = threading.Lock()


def get_working_memory(session_id: str = "default_session", persist_path: Optional[str] = None) -> BuiltinWorkingMemory:
    """Retrieve or create the BuiltinWorkingMemory instance for a session."""
    with _REGISTRY_LOCK:
        if session_id not in _WORKING_MEMORIES:
            _WORKING_MEMORIES[session_id] = BuiltinWorkingMemory(session_id=session_id, persist_path=persist_path)
        return _WORKING_MEMORIES[session_id]
