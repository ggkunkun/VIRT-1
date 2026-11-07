"""Paperclip Heartbeat Execution Runner.

Executes discrete, non-continuous agent heartbeats triggered by timers,
task assignments, or governance approvals with atomic checkouts and audit trails.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from virtu_omni.paperclip.control_plane import (
    PaperclipControlPlane,
    PaperclipTask,
    TaskStatus,
)

logger = logging.getLogger("virtu_omni.paperclip.heartbeat")


@dataclass
class HeartbeatWakeContext:
    agent_id: str
    company_id: str
    wake_reason: str
    task_id: Optional[str] = None
    run_id: str = field(default_factory=lambda: f"run-{uuid.uuid4().hex[:8]}")
    timestamp: float = field(default_factory=time.time)

    def to_env(self) -> Dict[str, str]:
        env = {
            "PAPERCLIP_AGENT_ID": self.agent_id,
            "PAPERCLIP_COMPANY_ID": self.company_id,
            "PAPERCLIP_WAKE_REASON": self.wake_reason,
            "PAPERCLIP_RUN_ID": self.run_id,
        }
        if self.task_id:
            env["PAPERCLIP_TASK_ID"] = self.task_id
        return env


@dataclass
class HeartbeatExecutionResult:
    ok: bool
    run_id: str
    agent_id: str
    task_id: Optional[str]
    wake_reason: str
    tokens_consumed: int
    duration_sec: float
    output: str
    documents_generated: Dict[str, str] = field(default_factory=dict)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "run_id": self.run_id,
            "agent_id": self.agent_id,
            "task_id": self.task_id,
            "wake_reason": self.wake_reason,
            "tokens_consumed": self.tokens_consumed,
            "duration_sec": round(self.duration_sec, 3),
            "output": self.output,
            "documents_generated": self.documents_generated,
            "error": self.error,
        }


class PaperclipHeartbeatRunner:
    """Manages scheduled and event-triggered heartbeats across the agent fleet."""

    def __init__(self, control_plane: PaperclipControlPlane) -> None:
        self.control_plane = control_plane
        self.execution_history: List[HeartbeatExecutionResult] = []

    def trigger_heartbeat(
        self,
        agent_id: str,
        wake_reason: str = "scheduled_heartbeat",
        task_id: Optional[str] = None,
        executor_fn: Optional[Callable[[HeartbeatWakeContext, Optional[PaperclipTask]], Dict[str, Any]]] = None,
    ) -> HeartbeatExecutionResult:
        """Execute a single atomic heartbeat for the target agent."""
        start_time = time.time()
        context = HeartbeatWakeContext(
            agent_id=agent_id,
            company_id=self.control_plane.company_id,
            wake_reason=wake_reason,
            task_id=task_id,
        )

        # 1. Resolve task to work on
        target_task: Optional[PaperclipTask] = None
        if task_id:
            target_task = self.control_plane.tasks.get(task_id)
        else:
            # Pick first available task assigned to this agent in TODO status
            for t in self.control_plane.tasks.values():
                if t.assigned_agent_id == agent_id and t.status in (TaskStatus.TODO, TaskStatus.IN_PROGRESS):
                    target_task = t
                    context.task_id = t.id
                    break

        # 2. If task found, perform atomic checkout
        if target_task:
            chk = self.control_plane.checkout_task(target_task.id, agent_id=agent_id)
            if not chk.get("ok"):
                res = HeartbeatExecutionResult(
                    ok=False,
                    run_id=context.run_id,
                    agent_id=agent_id,
                    task_id=target_task.id,
                    wake_reason=wake_reason,
                    tokens_consumed=0,
                    duration_sec=time.time() - start_time,
                    output="",
                    error=chk.get("error", "Checkout failed"),
                )
                self.execution_history.append(res)
                return res

        # 3. Execute work
        output_text = ""
        tokens_used = 0
        docs_generated: Dict[str, str] = {}
        error_msg: Optional[str] = None
        success = True

        try:
            if executor_fn:
                exec_res = executor_fn(context, target_task)
                output_text = exec_res.get("output", "")
                tokens_used = int(exec_res.get("tokens_consumed", 250))
                docs_generated = exec_res.get("documents", {})
                success = bool(exec_res.get("ok", True))
            else:
                # Default mock executor
                output_text = f"Agent {agent_id} processed heartbeat for {target_task.title if target_task else 'routine check'}"
                tokens_used = 180
                if target_task:
                    docs_generated = {"status_report": f"Task {target_task.id} inspected and verified."}
        except Exception as err:
            success = False
            error_msg = str(err)
            output_text = f"Heartbeat error: {err}"
            logger.exception("Error executing heartbeat for agent %s", agent_id)

        # 4. Finalize task if completed successfully
        if target_task and success:
            self.control_plane.complete_task(
                task_id=target_task.id,
                agent_id=agent_id,
                tokens_used=tokens_used,
                result_documents=docs_generated,
            )

        elapsed = time.time() - start_time
        result = HeartbeatExecutionResult(
            ok=success,
            run_id=context.run_id,
            agent_id=agent_id,
            task_id=target_task.id if target_task else None,
            wake_reason=wake_reason,
            tokens_consumed=tokens_used,
            duration_sec=elapsed,
            output=output_text,
            documents_generated=docs_generated,
            error=error_msg,
        )
        self.execution_history.append(result)
        return result
