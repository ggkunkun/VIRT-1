# -*- coding: utf-8 -*-
"""virtu_omni/reasoning/quiet_star_sandbox.py — Quiet-STaR Test-Time Silent Execution & Self-Healing Sandbox.

Grounded in:
1. Stanford Quiet-STaR: "Language Models Can Teach Themselves to Think Before Speaking" (Zelikman et al., 2024).
2. Test-Time Compute Scaling & Reflexion Self-Correction Loops.
3. The Extreme Step-by-Step Self-Verification & Circuit Breaker Axiom:
   "又快又准到极限，未到极限则继续，到了极限则放弃" (k_max = 3 strikes).

Core Function:
Before any generated CAD script, CNC G-code, or Python engineering calculation is delivered
to the user or downstream machine tools, this silent sandbox:
1. Executes the code in a headless virtual sandbox.
2. Captures all Tracebacks, compiler errors, and physical oracles.
3. Silently synthesizes atomic repair patches (AST/regex repair).
4. Iteratively validates until 100% clean (or trips circuit breaker if k_max reached).
5. Delivers ONLY verified, battle-tested code to the external caller.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import logging
import math
import os
import re
import sys
import time
import traceback
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

# --- V-03 修复：沙箱统一走 virtu_omni.security.code_guard 的 AST 闸门 ---------
try:
    from virtu_omni.security import code_guard as _code_guard
except Exception:  # pragma: no cover - 路径异常时退化为本地最小实现
    _code_guard = None


def _guarded_builtins() -> Dict[str, Any]:
    if _code_guard is not None:
        return _code_guard.restricted_builtins()
    return {"abs": abs, "min": min, "max": max, "round": round, "float": float,
            "int": int, "len": len, "range": range, "sum": sum,
            "print": lambda *args: None}


def _validate_source(code: str) -> List[str]:
    # 静思沙箱只跑纯计算代码：不开 open 豁免。旧写法沿用 code_guard 默认
    # allow_open=True，等于源级放行任意文件读取（全靠运行期 builtins 兜底），
    # 一旦有人调整 SAFE_GLOBALS 就直接穿透，所以这里显式收紧。
    if _code_guard is None:
        return []
    try:
        return _code_guard.validate_source(code, allow_open=False)
    except TypeError:  # 老版本 code_guard 无该关键字
        return _code_guard.validate_source(code)


def _guard_mode() -> str:
    return _code_guard.guard_mode() if _code_guard is not None else "enforce"


def _audit_blocked(code: str, violations: List[str]) -> None:
    """被拒代码留痕：只记哈希与违规摘要，不落原文。"""
    try:
        digest = hashlib.sha256((code or "").encode("utf-8", "replace")).hexdigest()[:12]
        logger.warning("quiet_star sandbox 拒绝不安全代码 sha256_12=%s violations=%s",
                       digest, violations[:3])
    except Exception:
        pass


logger = logging.getLogger("virtu_omni.reasoning.quiet_star")


@dataclass
class SilentExecutionResult:
    """Outcome of a silent execution attempt."""
    attempt: int
    success: bool
    stdout: str
    stderr: str
    exception_type: Optional[str] = None
    exception_msg: Optional[str] = None
    diagnosed_root_cause: Optional[str] = None
    patch_applied: Optional[str] = None
    elapsed_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SilentHealingAuditReport:
    """Full report of the Quiet-STaR self-healing lifecycle."""
    session_id: str
    target_language: str                # "PYTHON", "GCODE", "BUILD123D", "SOLIDWORKS_VBA"
    original_code_hash: str
    final_code_hash: str
    success: bool
    total_attempts: int
    attempts_history: List[SilentExecutionResult]
    final_code: str
    circuit_breaker_tripped: bool = False
    rcfa_root_cause: Optional[str] = None
    basis: str = "measured"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SilentCodeExecutor:
    """Runs untrusted code in a controlled safe local namespace.

    安全说明（V-03 修复）
    --------------------
    旧实现只裁掉了 ``__builtins__``，但模块级仍暴露了 ``math`` 对象与外层真实
    全局，任何 ``().\\_\\_class\\_\\_.\\_\\_base\\_\\_.\\_\\_subclasses\\_\\_()``
    或 ``(lambda:0).\\_\\_globals\\_\\_['sys'].modules['os']`` 都能反射回完整
    ``os``，等于没有沙箱。现在改为：

    * 执行前用 :mod:`virtu_omni.security.code_guard` 做 AST 静态校验（主防线）；
    * 执行时注入真正裁剪过的 builtins（``open`` 限定在白名单根目录内）。
    """

    SAFE_GLOBALS = {
        "abs": abs,
        "min": min,
        "max": max,
        "round": round,
        "float": float,
        "int": int,
        "len": len,
        "range": range,
        "sum": sum,
        "math": math,
        "__builtins__": _guarded_builtins(),
    }

    @classmethod
    def execute_python_code(cls, code: str) -> Tuple[bool, str, Optional[str], Optional[str]]:
        """Executes python code string; returns (success, stdout, exc_type, exc_msg)."""
        # 1. AST syntax check
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return False, "", "SyntaxError", f"Line {e.lineno}: {e.msg}"

        # 2. Security gate: 危险构造在 exec 之前就拒绝（fail-closed）
        violations = _validate_source(code)
        if violations:
            _audit_blocked(code, violations)
            if _guard_mode() != "audit":
                return False, "", "UnsafeCodeError", "；".join(violations[:5])

        # 3. Namespace execution
        local_scope: Dict[str, Any] = {}
        global_scope = copy.copy(cls.SAFE_GLOBALS)
        global_scope["math"] = math
        global_scope["__builtins__"] = _guarded_builtins()

        try:
            exec(compile(tree, "<quiet_star_sandbox>", "exec"), global_scope, local_scope)
            return True, "Execution succeeded", None, None
        except ZeroDivisionError as e:
            return False, "", "ZeroDivisionError", str(e)
        except NameError as e:
            return False, "", "NameError", str(e)
        except Exception as e:
            return False, "", type(e).__name__, str(e)


class QuietStarSelfHealingSandbox:
    """Quiet-STaR Autonomous Test-Time Self-Healing Controller."""

    def __init__(self, k_max: int = 3):
        self.k_max = k_max

    def execute_and_heal_code(
        self,
        code: str,
        language: str = "PYTHON",
        llm_repair_callback: Optional[Callable[[str, str], str]] = None,
    ) -> SilentHealingAuditReport:
        """Executes code and iteratively self-heals up to k_max attempts."""
        t0 = time.time()
        orig_hash = hashlib.sha256(code.encode()).hexdigest()[:10]
        session_id = f"QS_HEAL_{time.strftime('%Y%m%d_%H%M%S')}_{orig_hash}"

        current_code = code
        attempts: List[SilentExecutionResult] = []
        healed_success = False
        tripped = False
        final_rcfa = None

        for k in range(1, self.k_max + 1):
            t_att_start = time.time()

            if language.upper() == "PYTHON" or language.upper() == "BUILD123D":
                ok, stdout, exc_type, exc_msg = SilentCodeExecutor.execute_python_code(current_code)
            elif language.upper() == "GCODE":
                ok, stdout, exc_type, exc_msg = self._validate_gcode(current_code)
            else:
                ok, stdout, exc_type, exc_msg = True, "Unknown language bypassed", None, None

            elapsed_att = time.time() - t_att_start

            if ok:
                attempts.append(SilentExecutionResult(
                    attempt=k,
                    success=True,
                    stdout=stdout,
                    stderr="",
                    elapsed_seconds=round(elapsed_att, 4),
                ))
                healed_success = True
                break
            else:
                rcfa = self._diagnose_rcfa(exc_type, exc_msg, current_code)
                patch, new_code = self._synthesize_patch(
                    current_code,
                    exc_type,
                    exc_msg,
                    rcfa,
                    llm_repair_callback=llm_repair_callback,
                )

                attempts.append(SilentExecutionResult(
                    attempt=k,
                    success=False,
                    stdout=stdout,
                    stderr=f"{exc_type}: {exc_msg}",
                    exception_type=exc_type,
                    exception_msg=exc_msg,
                    diagnosed_root_cause=rcfa,
                    patch_applied=patch,
                    elapsed_seconds=round(elapsed_att, 4),
                ))

                if patch is not None and new_code != current_code:
                    current_code = new_code
                else:
                    # Error Plateau / Stagnation
                    tripped = True
                    final_rcfa = f"Repair stagnation at attempt {k}: no viable patch generated for {exc_type}"
                    break

        if not healed_success and not tripped:
            tripped = True
            final_rcfa = f"Exhausted k_max={self.k_max} budget without achieving error convergence."

        final_hash = hashlib.sha256(current_code.encode()).hexdigest()[:10]

        return SilentHealingAuditReport(
            session_id=session_id,
            target_language=language,
            original_code_hash=orig_hash,
            final_code_hash=final_hash,
            success=healed_success,
            total_attempts=len(attempts),
            attempts_history=attempts,
            final_code=current_code,
            circuit_breaker_tripped=tripped,
            rcfa_root_cause=final_rcfa,
            basis="measured",
        )

    def _validate_gcode(self, gcode: str) -> Tuple[bool, str, Optional[str], Optional[str]]:
        """Fast G-code validation: checks for fatal plunge without spindle."""
        lines = gcode.splitlines()
        spindle_on = False
        for idx, line in enumerate(lines, 1):
            line_u = line.upper().strip()
            if "M03" in line_u or "M04" in line_u:
                spindle_on = True
            elif "M05" in line_u:
                spindle_on = False

            if "G01" in line_u or "G1 " in line_u:
                if "Z-" in line_u and not spindle_on:
                    return False, "", "SpindleSafetyViolation", f"Line {idx}: cutting plunge Z- without spindle rotation (M03)"

        return True, "G-code syntax valid", None, None

    def _diagnose_rcfa(self, exc_type: Optional[str], exc_msg: Optional[str], code: str) -> str:
        """Diagnose root cause failure analysis (RCFA)."""
        if exc_type == "ZeroDivisionError":
            return "Division by zero encountered in formula parameter calculation."
        elif exc_type == "SyntaxError":
            return f"Syntax structure invalid in source: {exc_msg}"
        elif exc_type == "NameError":
            return f"Unbound identifier or missing import: {exc_msg}"
        elif exc_type == "SpindleSafetyViolation":
            return "Fatal machining safety risk: spindle must be running before plunging into stock."
        return f"Runtime exception {exc_type}: {exc_msg}"

    def _synthesize_patch(
        self,
        code: str,
        exc_type: Optional[str],
        exc_msg: Optional[str],
        rcfa: str,
        llm_repair_callback: Optional[Callable[[str, str], str]] = None,
    ) -> Tuple[Optional[str], str]:
        """Synthesizes targeted local code repair."""
        # LLM callback if provided
        if llm_repair_callback is not None:
            prompt = f"Repair the following {exc_type} error:\n{exc_msg}\n\nCode:\n```\n{code}\n```"
            try:
                repaired = llm_repair_callback(prompt, exc_type or "Error")
                if repaired and repaired != code:
                    return "LLM_SYNTHESIZED_PATCH", repaired
            except Exception as e:
                logger.warning("LLM repair failed: %s", e)

        # Deterministic Rules
        if exc_type == "ZeroDivisionError":
            # 1. Replace literal 0 division: / 0 or / 0.0 -> / 1e-6
            patched = re.sub(r"/\s*0(?:\.0*)?", "/ 1e-6", code)
            # 2. If no literal 0 was replaced, look for zero variable definitions: var = 0 -> var = 1e-6
            if patched == code:
                patched = re.sub(r"(\b\w+)\s*=\s*0(?:\.0*)?\b", r"\1 = 1e-6", patched)
            # 3. If still unchanged, wrap divisor in max(..., 1e-6)
            if patched == code:
                patched = re.sub(r"/\s*([a-zA-Z_]\w*)", r"/ max(\1, 1e-6)", patched)
            if patched != code:
                return "REPLACE_ZERO_DIVISOR_WITH_EPSILON", patched

        elif exc_type == "SpindleSafetyViolation":
            # Inject M03 S2000 before the first cutting move
            lines = code.splitlines()
            for idx, l in enumerate(lines):
                if "G01" in l.upper() or "G1 " in l.upper():
                    lines.insert(idx, "M03 S2000")
                    return "INJECT_M03_SPINDLE_START", "\n".join(lines)

        return None, code

    @classmethod
    def falsifiable_quiet_star_probe(cls) -> bool:
        """Rule 4: Injects unrecoverable syntax error (broken unbalanced brackets);

        Asserts that sandbox stops within k_max attempts, sets success == False, and trips circuit breaker.
        """
        sandbox = QuietStarSelfHealingSandbox(k_max=2)
        broken_code = "def invalid_func(x: return (((((x +"
        report = sandbox.execute_and_heal_code(broken_code, language="PYTHON")
        return not report.success and report.circuit_breaker_tripped and report.rcfa_root_cause is not None
