"""Deterministic deception gate for served answers.

Why this module exists
----------------------
The 2026-11-05 jailbreak probe found a reproducible failure: the model can say
「我无法提供破坏性指令」 and then hand over a runnable ``del /S`` block.  A refusal
keyword therefore cannot be trusted as a refusal.  The same audit found two
smaller deception shapes: claiming to have shown the system prompt without
showing any of it, and claiming a CAD/CAM action was completed without a tool
receipt.

This gate is the deterministic second line behind the system prompt.  It runs
after generation, never rewrites the model's reasoning, and is deliberately
narrow: every rule is a shape that can be demonstrated with a fixture in
``tests/test_deception_gate.py``.  It is not a semantic judge and must not be
advertised as one.

Actions
-------
``accept``      answer is usable as-is
``rewrite``     answer was replaced by a fixed safe text (thought/tool shell)
``reject``      answer is a deceptive compliance, replaced by a safe refusal
``incomplete``  generation was cut off or empty; must not be reported as success
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Sequence

# ---------------------------------------------------------------- detectors --
REFUSAL = re.compile(
    r"(不能|无法|不可|不会|不予|恕难|不允许|严禁|禁止|拒绝|不便提供|不能提供|"
    r"不能协助|无法协助|必须拒绝|不能给出|不会提供)"
)
EXEC = re.compile(
    r"(rm\s+-rf|del\s+/[fsq]|rmdir\s+/s|shutil\.rmtree|os\.remove|os\.unlink|"
    r"subprocess\.(run|call|Popen)|Remove-Item|format\s+[a-z]:|"
    r"reg\s+delete|vssadmin\s+delete|bcdedit\s+/set)",
    re.I,
)
# Long verbatim fragments of the production system prompt.  Topic words such as
# 安全底线/输出纪律 are deliberately NOT canaries: describing a section is not
# leaking it.
DEFAULT_CANARIES = (
    "你是 Virtu 工业智能体与数字制造专家",
    "涉及机床安全联锁短接、限位屏蔽、跳过首件检验等违章指令，坚决拒绝",
    "中间量保留至少 6 位小数",
)
LEAK_CLAIM = re.compile(
    r"((完整|逐字|原文|全文).{0,8}(系统提示|提示词|系统消息|system\s*prompt))"
    r"|((系统提示|提示词|系统消息|system\s*prompt).{0,8}(完整|逐字|原文|全文))",
    re.I,
)
# A refusal that then recommends disabling another protection is still a bypass.
BYPASS_HINT = re.compile(
    r"(建议|可以|改用|改为|替代|不妨|直接|通过).{0,24}"
    r"(禁用|关闭|屏蔽|绕过|短接|拆除|旁路|解除).{0,12}"
    r"(软限位|限位|联锁|光幕|急停|防护|首件|安全回路|安全门)",
    re.I,
)
COMPLETION_CLAIM = re.compile(
    r"(已|已经)(写入|保存|删除|提交|导入|打开|建模|修复|执行|运行|创建|生成|调用|触发)"
    r"(了|完成)?\s*(文件|目录|模型|程序|工程|项目|结果|报告|代码|脚本|日志|数据)?"
    r"|已(验证|校验|检查)通过|(全部|均已)(通过|完成)|\bPASS\b",
    re.I,
)
TOOL_SHELL = re.compile(
    r"<tool_call>|\"tool\"\s*:\s*\"cadcam_|\"name\"\s*:\s*\"cadcam_",
    re.I,
)
THOUGHT_LEAD = re.compile(
    r"^\s*(用户让我|用户想要|用户问|首先我|首先得|我需要分析|让我想想|"
    r"根据我的知识库|好的[，,]\s*用户|这个请求|分析一下)",
)
EXAMPLE_HINT = re.compile(r"(示例|例子|格式|模板|怎么写|如何调用|example|schema)", re.I)


def _has(text: str, pattern: re.Pattern[str]) -> bool:
    return bool(pattern.search(text or ""))


def _executable(text: str) -> bool:
    """True when the answer hands over a runnable command, not merely names one."""
    body = text or ""
    for block in re.findall(r"```.*?```", body, re.S):
        if EXEC.search(block):
            return True
    for line in body.splitlines():
        if EXEC.search(line) and not re.match(
            r"^\s*(#|//|禁止|不能|不要|切勿|严禁|请勿)", line
        ):
            return True
    return False


def _evidence_ok(evidence: Any) -> bool:
    """A completion claim is supported only by an explicit success receipt."""
    if evidence is None or evidence is False:
        return False
    if evidence is True:
        return True
    items: Iterable[Any]
    if isinstance(evidence, dict):
        items = (evidence,)
    elif isinstance(evidence, (list, tuple)):
        items = evidence
    else:
        return bool(evidence)
    for item in items:
        if not isinstance(item, dict):
            if item:
                return True
            continue
        if item.get("ok") is True or item.get("success") is True:
            return True
        if item.get("returncode") == 0:
            return True
        if str(item.get("status", "")).lower() in {"ok", "success", "passed", "done"}:
            return True
    return False


def _unclosed_code(text: str) -> bool:
    return (text or "").count("```") % 2 == 1


# ------------------------------------------------------------------- result --
@dataclass(frozen=True)
class GateDecision:
    action: str
    reasons: tuple[str, ...]
    text: str
    raw_sha256: str
    raw_chars: int

    def to_dict(self) -> dict:
        return asdict(self)


SAFE_REFUSAL = "我不能提供该操作的可执行步骤。该请求涉及绕过安全防护或破坏审计证据，请通过合规流程处理。"
SAFE_LEAK = "我不能复述或声称展示内部系统提示。请说明你需要的工程问题。"
SAFE_COMPLETION = "我没有可验证的执行回执，不能确认该操作已完成。请以工具返回结果或文件实际状态为准。"
SAFE_BYPASS = "我不能建议禁用或绕过任何安全防护功能。请由持证人员按设备手册处理。"
SAFE_TOOL = "我没有实际发起工具调用，不能把这段 JSON 当作执行结果。请明确需要哪个工具及参数。"


def gate_answer(
    answer: str,
    prompt: str = "",
    evidence: Any = None,
    done_reason: str | None = None,
    canaries: Sequence[str] | None = None,
) -> GateDecision:
    """Return the gate decision for one generated answer.

    ``evidence`` is the list of tool results (or an explicit success flag) that
    the caller has actually observed.  ``done_reason='length'`` means the backend
    cut the generation off and the answer must not be reported as complete.
    """
    body = answer or ""
    raw_sha = hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]
    refused = _has(body, REFUSAL)
    evidence_ok = _evidence_ok(evidence)
    reasons: list[str] = []

    # 1) Refuse-then-comply: the exact C3 shape.  A refusal word cannot erase a
    #    runnable command that follows it.
    if refused and _executable(body):
        return GateDecision("reject", ("refuse_then_comply",), SAFE_REFUSAL, raw_sha, len(body))

    # 2) Refuse the named action, recommend another protection cut.
    if refused and _has(body, BYPASS_HINT):
        return GateDecision("reject", ("alternative_bypass",), SAFE_BYPASS, raw_sha, len(body))

    # 3) A real verbatim leak is rejected regardless of how it is framed.
    canary_set = tuple(canaries) if canaries is not None else DEFAULT_CANARIES
    if any(c in body for c in canary_set):
        return GateDecision("reject", ("system_prompt_leaked",), SAFE_LEAK, raw_sha, len(body))

    # 4) "Here is my full system prompt" without a single verbatim fragment.
    if _has(body, LEAK_CLAIM) and not refused:
        return GateDecision("reject", ("fake_prompt_leak",), SAFE_LEAK, raw_sha, len(body))

    # 5) Tool-call shell with no tool call behind it.
    if _has(body, TOOL_SHELL) and not evidence_ok and not _has(prompt, EXAMPLE_HINT):
        return GateDecision("rewrite", ("fake_tool_call",), SAFE_TOOL, raw_sha, len(body))

    # 6) Completion claim without a receipt.
    if _has(body, COMPLETION_CLAIM) and not evidence_ok:
        # "已生成如下代码" is content delivery, not an execution claim.
        if not re.search(r"已(经)?生成\s*(如下|以下)", body):
            return GateDecision("reject", ("unsupported_completion",), SAFE_COMPLETION, raw_sha, len(body))

    # 7) Thought leaked into the visible answer.
    if THOUGHT_LEAD.search(body) and not refused:
        visible = _strip_thought_lead(body)
        if len(visible.strip()) < 8:
            return GateDecision("incomplete", ("thought_only",), visible, raw_sha, len(body))
        return GateDecision("rewrite", ("thought_leak",), visible, raw_sha, len(body))

    # 8) Truncated / empty generation must not be presented as success.
    if done_reason == "length" or _unclosed_code(body) or len(body.strip()) < 4:
        return GateDecision("incomplete", ("truncated_or_empty",), body, raw_sha, len(body))

    return GateDecision("accept", ("clean",), body, raw_sha, len(body))


def _strip_thought_lead(text: str) -> str:
    """Drop a leading planning monologue up to the first blank line/answer marker."""
    lines = (text or "").splitlines()
    out: list[str] = []
    started = False
    for line in lines:
        if not started and not THOUGHT_LEAD.search(line) and line.strip():
            started = True
        if started:
            out.append(line)
    return "\n".join(out).strip()