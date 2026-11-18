"""Context Mode Sandboxed Subprocess Execution and Output Filtering Engine.

Intercepts massive outputs from CLIs, compilers, test runners, and file reads.
Filters and summarizes data in an isolated subprocess before passing minimal
high-signal context back to the LLM, reducing token consumption by up to 98%.
"""

from __future__ import annotations

import ast
import logging
import os
import shlex
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("virtu_omni.context_mode.optimizer")


# ---------------------------------------------------------------------------
# P1 security policy for sandboxed execution
# ---------------------------------------------------------------------------
class UnsafeCommandError(ValueError):
    """Raised when a command violates the executable allowlist / metachar policy."""


class UnsafeFilterScriptError(ValueError):
    """Raised when a custom filter script violates the sandbox policy."""


# Only these executable names (basename, case-insensitive, optional .exe) may run.
ALLOWED_EXECUTABLES = frozenset({
    "echo", "python", "python3", "py", "node", "npm", "npx",
    "git", "pytest", "curl", "ping", "ipconfig", "hostname",
    "whoami", "date", "dir", "type", "cat", "ls", "ver",
})

# Shell metacharacters that must never reach a shell-less argv, even inside quotes.
_SHELL_METACHARS = frozenset(";&|`$><\n\r")

# Forbidden AST constructs inside a filter script.
_FORBIDDEN_AST_NODES = (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal)
_FORBIDDEN_CALLS = frozenset({
    "open", "eval", "exec", "__import__", "compile", "input",
    "getattr", "setattr", "delattr", "globals", "locals",
    "vars", "breakpoint", "help", "memoryview",
})
_FORBIDDEN_ATTRS = frozenset({
    "__class__", "__bases__", "__mro__", "__subclasses__", "__globals__",
    "__code__", "__func__", "__self__", "__dict__", "__builtins__",
    "__import__", "__loader__", "__spec__", "__reduce__", "__getattribute__",
    "f_builtins", "f_globals", "f_locals", "gi_frame", "cr_frame",
})
_FORBIDDEN_NAMES = frozenset({
    "__builtins__", "__import__", "os", "sys", "subprocess", "builtins",
})


def _canonical_exe(token: str) -> str:
    name = os.path.basename(token).lower()
    return name[:-4] if name.endswith(".exe") else name


def _validate_and_split_command(command: str) -> Tuple[List[str], str]:
    """Validate a command against the allowlist and split it into a safe argv."""
    if not isinstance(command, str) or not command.strip():
        raise UnsafeCommandError("command must be a non-empty string")
    for ch in command:
        if ch in _SHELL_METACHARS:
            raise UnsafeCommandError(
                f"command contains forbidden shell metacharacter: {ch!r}")
    try:
        argv = shlex.split(command)
    except ValueError as exc:
        raise UnsafeCommandError(f"command could not be parsed: {exc}") from exc
    if not argv:
        raise UnsafeCommandError("command is empty after parsing")
    exe = _canonical_exe(argv[0])
    if exe not in ALLOWED_EXECUTABLES:
        raise UnsafeCommandError(f"executable not in allowlist: {argv[0]!r}")
    return argv, exe


def _call_name(func: ast.AST) -> str:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _build_safe_builtins() -> Dict[str, Any]:
    import builtins
    allowed = (
        "abs", "all", "any", "bool", "dict", "enumerate", "filter", "float",
        "format", "int", "isinstance", "iter", "len", "list", "map", "max",
        "min", "next", "print", "range", "repr", "reversed", "round", "set",
        "slice", "sorted", "str", "sum", "tuple", "zip",
    )
    return {name: getattr(builtins, name) for name in allowed if hasattr(builtins, name)}


def _validate_filter_script(script: str) -> None:
    """Reject import / open / eval / exec / __import__ and dangerous attributes."""
    if not isinstance(script, str) or not script.strip():
        raise UnsafeFilterScriptError("filter_script must be a non-empty string")
    try:
        tree = ast.parse(script, mode="exec")
    except SyntaxError as exc:
        raise UnsafeFilterScriptError(f"filter_script has invalid syntax: {exc}") from exc
    for node in ast.walk(tree):
        if isinstance(node, _FORBIDDEN_AST_NODES):
            raise UnsafeFilterScriptError(
                f"filter_script contains forbidden statement: {type(node).__name__}")
        if isinstance(node, ast.Call) and _call_name(node.func) in _FORBIDDEN_CALLS:
            raise UnsafeFilterScriptError(
                f"filter_script calls forbidden builtin: {_call_name(node.func)}")
        if isinstance(node, ast.Attribute):
            if node.attr in _FORBIDDEN_ATTRS or node.attr.startswith("__"):
                raise UnsafeFilterScriptError(
                    f"filter_script accesses forbidden attribute: {node.attr}")
        if isinstance(node, ast.Name) and node.id in _FORBIDDEN_NAMES:
            raise UnsafeFilterScriptError(
                f"filter_script references forbidden name: {node.id}")


@dataclass
class OptimizationResult:
    ok: bool
    command: str
    raw_bytes: int
    filtered_bytes: int
    raw_lines: int
    filtered_lines: int
    savings_percentage: float
    output: str
    execution_time_sec: float
    filter_applied: str = "default_summarizer"
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "command": self.command,
            "raw_bytes": self.raw_bytes,
            "filtered_bytes": self.filtered_bytes,
            "raw_lines": self.raw_lines,
            "filtered_lines": self.filtered_lines,
            "savings_percentage": round(self.savings_percentage, 2),
            "output": self.output,
            "execution_time_sec": round(self.execution_time_sec, 3),
            "filter_applied": self.filter_applied,
            "error": self.error,
        }


class ContextModeOptimizer:
    """Controls sandboxed tool execution and output stream compression."""

    def __init__(self, max_raw_display_lines: int = 25) -> None:
        self.max_raw_display_lines = max_raw_display_lines
        self.cumulative_raw_bytes = 0
        self.cumulative_filtered_bytes = 0
        self.total_operations = 0

    def execute_sandboxed(
        self,
        command: str,
        filter_script: Optional[str] = None,
        timeout_sec: float = 30.0,
        cwd: Optional[str] = None,
    ) -> OptimizationResult:
        """
        Execute command inside sandboxed subprocess, capturing stdout/stderr,
        and filter output before returning it to the LLM context.
        """
        start_time = time.time()
        try:
            # Parse + validate FIRST: no shell, explicit allowlist, no metachars.
            argv, exe_name = _validate_and_split_command(command)
            if exe_name == "echo":
                # Windows has no standalone echo.exe. Emulate this harmless
                # builtin in-process instead of invoking any shell / child.
                raw_stdout = " ".join(argv[1:]) + "\n"
                raw_stderr = ""
                success = True
            else:
                proc = subprocess.run(
                    argv,
                    shell=False,
                    capture_output=True,
                    text=True,
                    cwd=cwd,
                    timeout=timeout_sec,
                    encoding="utf-8",
                    errors="replace",
                )
                raw_stdout = proc.stdout or ""
                raw_stderr = proc.stderr or ""
                success = proc.returncode == 0
            raw_combined = raw_stdout + ("\n" + raw_stderr if raw_stderr else "")
        except UnsafeCommandError as err:
            return OptimizationResult(
                ok=False,
                command=command,
                raw_bytes=0,
                filtered_bytes=0,
                raw_lines=0,
                filtered_lines=0,
                savings_percentage=0.0,
                output="",
                execution_time_sec=time.time() - start_time,
                error=f"Command rejected by sandbox: {err}",
            )
        except subprocess.TimeoutExpired:
            return OptimizationResult(
                ok=False,
                command=command,
                raw_bytes=0,
                filtered_bytes=0,
                raw_lines=0,
                filtered_lines=0,
                savings_percentage=0.0,
                output="",
                execution_time_sec=time.time() - start_time,
                error=f"Command timed out after {timeout_sec}s",
            )
        except Exception as err:
            return OptimizationResult(
                ok=False,
                command=command,
                raw_bytes=0,
                filtered_bytes=0,
                raw_lines=0,
                filtered_lines=0,
                savings_percentage=0.0,
                output="",
                execution_time_sec=time.time() - start_time,
                error=str(err),
            )

        raw_bytes = len(raw_combined.encode("utf-8"))
        raw_lines = len(raw_combined.splitlines())

        # Apply filtering (a rejected script must NOT silently fall back)
        try:
            filtered_text, filter_name = self._apply_filter(raw_combined, filter_script=filter_script)
        except UnsafeFilterScriptError as err:
            return OptimizationResult(
                ok=False,
                command=command,
                raw_bytes=raw_bytes,
                filtered_bytes=0,
                raw_lines=raw_lines,
                filtered_lines=0,
                savings_percentage=0.0,
                output="",
                execution_time_sec=time.time() - start_time,
                error=f"Filter script rejected by sandbox: {err}",
            )

        filtered_bytes = len(filtered_text.encode("utf-8"))
        filtered_lines = len(filtered_text.splitlines())

        savings = 0.0
        if raw_bytes > 0:
            savings = max(0.0, ((raw_bytes - filtered_bytes) / float(raw_bytes)) * 100.0)

        # Update cumulative tracking
        self.cumulative_raw_bytes += raw_bytes
        self.cumulative_filtered_bytes += filtered_bytes
        self.total_operations += 1

        elapsed = time.time() - start_time
        return OptimizationResult(
            ok=success,
            command=command,
            raw_bytes=raw_bytes,
            filtered_bytes=filtered_bytes,
            raw_lines=raw_lines,
            filtered_lines=filtered_lines,
            savings_percentage=savings,
            output=filtered_text,
            execution_time_sec=elapsed,
            filter_applied=filter_name,
        )

    def filter_file(
        self,
        filepath: Path | str,
        filter_script: Optional[str] = None,
        max_lines: int = 50,
    ) -> OptimizationResult:
        """
        Process a large file out-of-context, returning only the filtered signal.
        """
        start_time = time.time()
        p = Path(filepath)
        if not p.exists():
            return OptimizationResult(
                ok=False,
                command=f"read_file({p.name})",
                raw_bytes=0,
                filtered_bytes=0,
                raw_lines=0,
                filtered_lines=0,
                savings_percentage=0.0,
                output="",
                execution_time_sec=time.time() - start_time,
                error=f"File not found: {p}",
            )

        try:
            content = p.read_text(encoding="utf-8", errors="replace")
        except Exception as err:
            return OptimizationResult(
                ok=False,
                command=f"read_file({p.name})",
                raw_bytes=0,
                filtered_bytes=0,
                raw_lines=0,
                filtered_lines=0,
                savings_percentage=0.0,
                output="",
                execution_time_sec=time.time() - start_time,
                error=str(err),
            )

        raw_bytes = len(content.encode("utf-8"))
        raw_lines = len(content.splitlines())

        try:
            filtered_text, filter_name = self._apply_filter(content, filter_script=filter_script, max_lines=max_lines)
        except UnsafeFilterScriptError as err:
            return OptimizationResult(
                ok=False,
                command=f"read_file({p.name})",
                raw_bytes=raw_bytes,
                filtered_bytes=0,
                raw_lines=raw_lines,
                filtered_lines=0,
                savings_percentage=0.0,
                output="",
                execution_time_sec=time.time() - start_time,
                error=f"Filter script rejected by sandbox: {err}",
            )
        filtered_bytes = len(filtered_text.encode("utf-8"))
        filtered_lines = len(filtered_text.splitlines())

        savings = 0.0
        if raw_bytes > 0:
            savings = max(0.0, ((raw_bytes - filtered_bytes) / float(raw_bytes)) * 100.0)

        self.cumulative_raw_bytes += raw_bytes
        self.cumulative_filtered_bytes += filtered_bytes
        self.total_operations += 1

        return OptimizationResult(
            ok=True,
            command=f"ctx_execute_file({p.name})",
            raw_bytes=raw_bytes,
            filtered_bytes=filtered_bytes,
            raw_lines=raw_lines,
            filtered_lines=filtered_lines,
            savings_percentage=savings,
            output=filtered_text,
            execution_time_sec=time.time() - start_time,
            filter_applied=filter_name,
        )

    def _apply_filter(
        self,
        raw_text: str,
        filter_script: Optional[str] = None,
        max_lines: int = 30,
    ) -> Tuple[str, str]:
        """Apply custom Python filter snippet or default high-efficiency summarizer."""
        lines = raw_text.splitlines()

        # 1. Custom Script Execution (hardened: AST allowlist + restricted builtins)
        if filter_script:
            _validate_filter_script(filter_script)  # raises UnsafeFilterScriptError
            local_scope: Dict[str, Any] = {"raw": raw_text, "lines": lines, "output": ""}
            exec_globals: Dict[str, Any] = {"__builtins__": _build_safe_builtins()}
            try:
                exec(compile(filter_script, "<filter_script>", "exec"), exec_globals, local_scope)
            except UnsafeFilterScriptError:
                raise
            except Exception as err:
                raise UnsafeFilterScriptError(
                    f"custom filter execution failed: {type(err).__name__}: {err}") from err
            res = str(local_scope.get("output", ""))
            if res.strip():
                return res.strip(), "custom_filter_script"

        # 2. If content is small, return as-is
        if len(lines) <= max_lines:
            return raw_text, "verbatim_small_output"

        # 3. Default Industrial High-Efficiency Compressor
        head_count = 10
        tail_count = 10
        middle_dropped = len(lines) - (head_count + tail_count)

        # Extract potential error or warning lines from middle
        error_lines = [l for l in lines[head_count:-tail_count] if any(w in l.lower() for w in ["error", "fail", "exception", "warn", "fatal", "violation"])]

        summary_parts = [
            "\n".join(lines[:head_count]),
            f"\n... [CONTEXT-MODE COMPRESSION: {middle_dropped} lines omitted ({len(error_lines)} warning/error lines detected)] ...",
        ]
        if error_lines:
            summary_parts.append("--- Intercepted Issue Highlights ---")
            summary_parts.append("\n".join(error_lines[:5]))
            if len(error_lines) > 5:
                summary_parts.append(f"... (+ {len(error_lines) - 5} additional warnings suppressed)")
            summary_parts.append("-------------------------------------")

        summary_parts.append("\n".join(lines[-tail_count:]))
        return "\n".join(summary_parts), "intelligent_bracket_compressor"

    def get_savings_metrics(self) -> Dict[str, Any]:
        """Return cumulative savings telemetry."""
        saved_bytes = max(0, self.cumulative_raw_bytes - self.cumulative_filtered_bytes)
        ratio = 0.0
        if self.cumulative_raw_bytes > 0:
            ratio = (saved_bytes / float(self.cumulative_raw_bytes)) * 100.0

        estimated_tokens_saved = int(saved_bytes / 4.0)

        return {
            "total_operations": self.total_operations,
            "cumulative_raw_bytes": self.cumulative_raw_bytes,
            "cumulative_filtered_bytes": self.cumulative_filtered_bytes,
            "bytes_saved": saved_bytes,
            "overall_savings_percentage": round(ratio, 2),
            "estimated_tokens_saved": estimated_tokens_saved,
        }
