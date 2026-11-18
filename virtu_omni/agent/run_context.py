"""统一运行上下文（审计报告 §7.2 / §7.4：无 run_id / trace_id / span、日志无结构）。

设计约束：
  * 只用标准库（hashlib / json / logging / os / time / uuid），不引入新依赖；
  * run_id 是**内容指纹**，同输入必得同 id（审计 §8.2，不掺 time.time()）；
  * 允许显式传入 run_id 以便跨进程续跑（deep_agent run_id 会透传到 trace）；
  * logger 输出统一 key=value 结构，任何一行都能按 run_id 串起完整 trace。

用法：
    ctx = RunContext.root(task, model="...")
    child = ctx.child("plan")
    child.log("plan_done", steps=3, valid=True, duration_ms=812)
    # -> ... run_id=8f2c... span=root/plan stage=plan_done steps=3 valid=True duration_ms=812 pid=12345
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time

_LOGGER_NAME = "virtu_omni.agent.trace"


def content_fingerprint(*parts, length: int = 16) -> str:
    """纯内容指纹：入参相同则结果相同，绝不掺入时间戳/随机数。"""
    payload = json.dumps([p if isinstance(p, (str, int, float, bool, type(None)))
                          else json.dumps(p, sort_keys=True, ensure_ascii=False)
                          for p in parts], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:length]


class RunContext:
    """run_id（内容指纹）+ span 路径 + step 计数，全链透传的最小载体。"""

    __slots__ = ("run_id", "span", "parent_span", "step", "extra", "started_at", "_t0")

    def __init__(self, run_id: str, span: str = "root", parent_span: str = "",
                 step: int = 0, extra: dict | None = None):
        self.run_id = run_id
        self.span = span
        self.parent_span = parent_span
        self.step = int(step)
        self.extra = dict(extra or {})
        self.started_at = time.time()
        self._t0 = self.started_at

    # ---------------------------------------------------------------- factories
    @classmethod
    def root(cls, *fingerprint_parts, run_id: str | None = None, **extra) -> "RunContext":
        rid = run_id or content_fingerprint(*fingerprint_parts)
        return cls(rid, span="root", extra=extra)

    def child(self, span: str, step: int | None = None) -> "RunContext":
        return RunContext(self.run_id,
                          span=f"{self.span}/{span}",
                          parent_span=self.span,
                          step=self.step if step is None else step,
                          extra=self.extra)

    def with_step(self, step: int) -> "RunContext":
        c = self.child(self.span.rsplit("/", 1)[-1], step=step)
        c.span, c.parent_span = self.span, self.parent_span
        return c

    # ---------------------------------------------------------------- logging
    @staticmethod
    def logger() -> logging.Logger:
        return logging.getLogger(_LOGGER_NAME)

    def fields(self, **kw) -> dict:
        base = {"run_id": self.run_id, "span": self.span, "step": self.step,
                "pid": os.getpid()}
        if self.parent_span:
            base["parent_span"] = self.parent_span
        base.update({k: v for k, v in kw.items() if v is not None})
        return base

    def log(self, stage: str, level: int = logging.INFO, duration_ms: float | None = None,
            **kw) -> None:
        """结构化日志：一句话 + key=value，可直接被日志采集器切分。"""
        f = self.fields(stage=stage, duration_ms=(None if duration_ms is None
                                                  else round(duration_ms, 1)), **kw)
        self.logger().log(level, " ".join(f"{k}={v}" for k, v in f.items()))

    def elapse_ms(self) -> float:
        return (time.time() - self._t0) * 1000.0

    # ---------------------------------------------------------------- dunder
    def to_dict(self) -> dict:
        return {"run_id": self.run_id, "span": self.span, "parent_span": self.parent_span,
                "step": self.step, "pid": os.getpid(),
                "started_at": round(self.started_at, 3), **self.extra}

    def __repr__(self) -> str:  # pragma: no cover - 便于调试
        return f"RunContext(run_id={self.run_id}, span={self.span}, step={self.step})"


def ensure_ctx(ctx=None, *fingerprint_parts, **extra) -> RunContext:
    """拿到一个可用 ctx：已传则原样返回（保证透传），否则按内容指纹新建。"""
    if isinstance(ctx, RunContext):
        return ctx
    if isinstance(ctx, dict) and ctx.get("run_id"):
        return RunContext(ctx["run_id"], span=ctx.get("span", "root"),
                          parent_span=ctx.get("parent_span", ""),
                          step=ctx.get("step", 0))
    return RunContext.root(*fingerprint_parts, **extra)
