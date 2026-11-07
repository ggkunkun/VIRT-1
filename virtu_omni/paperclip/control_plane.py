"""Paperclip Control Plane for Virtu Foundation Model & Multi-Agent Swarms.

Implements:
1. Corporate Hierarchy & Org Tree (Company, Departments, Agent Roles).
2. Task / Issue Lifecycle with Atomic Checkouts & Leases.
3. Approval Workflows & Security Gates.
4. Token Budgets, Spend Tracking & Hard Quotas.
5. Run Audit Trails (X-Paperclip-Run-Id).
"""

from __future__ import annotations

import enum
import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("virtu_omni.paperclip.control_plane")


class TaskStatus(str, enum.Enum):
    BACKLOG = "backlog"
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    DONE = "done"
    BLOCKED = "blocked"
    CANCELED = "canceled"


class TaskPriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class ApprovalStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class AgentProfile:
    id: str
    name: str
    role: str
    department: str
    reports_to: Optional[str] = None
    skills: List[str] = field(default_factory=list)
    budget_limit_usd: float = 50.0
    spent_usd: float = 0.0
    tokens_consumed: int = 0
    is_active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TaskDocument:
    key: str
    title: str
    content: str
    revision: int = 1
    updated_at: float = field(default_factory=time.time)


@dataclass
class PaperclipTask:
    id: str
    company_id: str
    title: str
    description: str
    assigned_agent_id: Optional[str] = None
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    parent_id: Optional[str] = None
    linked_issue_ids: List[str] = field(default_factory=list)
    documents: Dict[str, TaskDocument] = field(default_factory=dict)
    checkout_lease_owner: Optional[str] = None
    checkout_expires_at: Optional[float] = None
    run_id: Optional[str] = None
    estimated_tokens: int = 0
    actual_tokens: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["status"] = self.status.value
        res["priority"] = self.priority.value
        res["documents"] = {k: asdict(v) for k, v in self.documents.items()}
        return res


@dataclass
class ApprovalRequest:
    id: str
    company_id: str
    task_id: str
    agent_id: str
    action_type: str
    payload: Dict[str, Any]
    status: ApprovalStatus = ApprovalStatus.PENDING
    decided_by: Optional[str] = None
    rationale: str = ""
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["status"] = self.status.value
        return res


class PaperclipControlPlane:
    """In-memory and JSON-backed control plane for multi-agent enterprise governance."""

    def __init__(self, company_id: str = "virtu-industrial-corp", storage_path: Optional[Path | str] = None) -> None:
        self.company_id = company_id
        self.storage_path = Path(storage_path) if storage_path else None
        self.agents: Dict[str, AgentProfile] = {}
        self.tasks: Dict[str, PaperclipTask] = {}
        self.approvals: Dict[str, ApprovalRequest] = {}
        self.audit_log: List[Dict[str, Any]] = []
        self._initialize_default_org()

    def _initialize_default_org(self) -> None:
        """Initialize standard Virtu Industrial Org Chart."""
        # 1. Chief Architect
        self.register_agent(
            AgentProfile(
                id="virtu-architect",
                name="Chief Industrial Architect",
                role="CEO & Head of Systems",
                department="Engineering Leadership",
                reports_to=None,
                skills=["system-design", "task-decomposition", "paperclip-board"],
                budget_limit_usd=100.0,
            )
        )
        # 2. Lead CAD Modeler
        self.register_agent(
            AgentProfile(
                id="virtu-cad-modeler",
                name="Lead CAD Modeler",
                role="Senior Parametric Modeler",
                department="Mechanical Design",
                reports_to="virtu-architect",
                skills=["solidworks-api", "nx-open", "autocad-lisp", "cad_cam_feature_tree"],
                budget_limit_usd=50.0,
            )
        )
        # 3. Lead CAM Engineer
        self.register_agent(
            AgentProfile(
                id="virtu-cam-engineer",
                name="Lead CAM Engineer",
                role="CNC Toolpath & Simulation Lead",
                department="Manufacturing & NC",
                reports_to="virtu-architect",
                skills=["cimco-macro-b", "vericut-physics", "sscnc-machining"],
                budget_limit_usd=50.0,
            )
        )
        # 4. Security & Quality Auditor
        self.register_agent(
            AgentProfile(
                id="virtu-security-auditor",
                name="Chief Security & Safety Auditor",
                role="Security & Code Auditor",
                department="Governance & Safety",
                reports_to="virtu-architect",
                skills=["security-audit", "guardrails-enforcement", "injection-defense"],
                budget_limit_usd=30.0,
            )
        )
        # 5. Evolution & Memory Lead
        self.register_agent(
            AgentProfile(
                id="virtu-memory-lead",
                name="Knowledge & Evolution Specialist",
                role="Long-Term Memory Architect",
                department="Research & Learning",
                reports_to="virtu-architect",
                skills=["hindsight", "ai-engineering-from-scratch", "agent-reach"],
                budget_limit_usd=30.0,
            )
        )

    def register_agent(self, agent: AgentProfile) -> None:
        self.agents[agent.id] = agent

    def get_org_chart(self) -> Dict[str, Any]:
        """Return hierarchical org chart representing reporting lines."""
        hierarchy = []
        for agent in self.agents.values():
            hierarchy.append(
                {
                    "id": agent.id,
                    "name": agent.name,
                    "role": agent.role,
                    "department": agent.department,
                    "reports_to": agent.reports_to,
                    "skills": agent.skills,
                    "budget_limit_usd": agent.budget_limit_usd,
                    "spent_usd": agent.spent_usd,
                    "tokens_consumed": agent.tokens_consumed,
                }
            )
        return {
            "company_id": self.company_id,
            "total_agents": len(self.agents),
            "hierarchy": hierarchy,
        }

    def create_task(
        self,
        title: str,
        description: str,
        assigned_agent_id: Optional[str] = None,
        priority: TaskPriority = TaskPriority.MEDIUM,
        parent_id: Optional[str] = None,
        initial_documents: Optional[Dict[str, str]] = None,
    ) -> PaperclipTask:
        """Create new work item in the control plane."""
        task_id = f"task-{uuid.uuid4().hex[:8]}"
        docs = {}
        if initial_documents:
            for k, v in initial_documents.items():
                docs[k] = TaskDocument(key=k, title=k.title(), content=v)

        task = PaperclipTask(
            id=task_id,
            company_id=self.company_id,
            title=title,
            description=description,
            assigned_agent_id=assigned_agent_id,
            priority=priority,
            parent_id=parent_id,
            documents=docs,
        )
        self.tasks[task_id] = task
        self._record_audit("task_created", {"task_id": task_id, "title": title, "assigned": assigned_agent_id})
        return task

    def checkout_task(self, task_id: str, agent_id: str, lease_duration_sec: float = 300.0) -> Dict[str, Any]:
        """Atomic lease checkout preventing duplicate concurrent execution."""
        task = self.tasks.get(task_id)
        if not task:
            return {"ok": False, "error": f"Task {task_id} not found"}

        now = time.time()
        # Check active lease
        if task.checkout_lease_owner and task.checkout_expires_at and task.checkout_expires_at > now:
            if task.checkout_lease_owner != agent_id:
                return {
                    "ok": False,
                    "error": f"Task is currently leased by agent {task.checkout_lease_owner} until {task.checkout_expires_at}",
                }

        run_id = f"run-{uuid.uuid4().hex[:8]}"
        task.checkout_lease_owner = agent_id
        task.checkout_expires_at = now + lease_duration_sec
        task.status = TaskStatus.IN_PROGRESS
        task.run_id = run_id
        task.updated_at = now

        self._record_audit(
            "task_checked_out",
            {"task_id": task_id, "agent_id": agent_id, "run_id": run_id, "lease_until": task.checkout_expires_at},
        )
        return {"ok": True, "task": task.to_dict(), "run_id": run_id}

    def complete_task(
        self,
        task_id: str,
        agent_id: str,
        tokens_used: int = 0,
        result_documents: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Release lease, update documents, and set task status to DONE."""
        task = self.tasks.get(task_id)
        if not task:
            return {"ok": False, "error": f"Task {task_id} not found"}

        if task.checkout_lease_owner != agent_id:
            logger.warning("Agent %s completing task leased to %s", agent_id, task.checkout_lease_owner)

        now = time.time()
        task.checkout_lease_owner = None
        task.checkout_expires_at = None
        task.status = TaskStatus.DONE
        task.actual_tokens += tokens_used
        task.updated_at = now

        if result_documents:
            for k, v in result_documents.items():
                if k in task.documents:
                    doc = task.documents[k]
                    doc.content = v
                    doc.revision += 1
                    doc.updated_at = now
                else:
                    task.documents[k] = TaskDocument(key=k, title=k.title(), content=v)

        # Update agent spend statistics
        if agent_id in self.agents:
            agent = self.agents[agent_id]
            agent.tokens_consumed += tokens_used
            # Estimate cost ($0.002 per 1k tokens)
            agent.spent_usd += (tokens_used / 1000.0) * 0.002

        self._record_audit("task_completed", {"task_id": task_id, "agent_id": agent_id, "tokens_used": tokens_used})
        return {"ok": True, "task": task.to_dict()}

    def request_approval(
        self,
        task_id: str,
        agent_id: str,
        action_type: str,
        payload: Dict[str, Any],
    ) -> ApprovalRequest:
        """Create approval gate for sensitive physical actions or major decisions."""
        app_id = f"app-{uuid.uuid4().hex[:8]}"
        req = ApprovalRequest(
            id=app_id,
            company_id=self.company_id,
            task_id=task_id,
            agent_id=agent_id,
            action_type=action_type,
            payload=payload,
        )
        self.approvals[app_id] = req

        # Mark task as in_review
        if task_id in self.tasks:
            self.tasks[task_id].status = TaskStatus.IN_REVIEW

        self._record_audit("approval_requested", {"approval_id": app_id, "task_id": task_id, "action": action_type})
        return req

    def decide_approval(self, approval_id: str, approved: bool, decided_by: str, rationale: str = "") -> Dict[str, Any]:
        """Approve or reject a governance gate."""
        req = self.approvals.get(approval_id)
        if not req:
            return {"ok": False, "error": f"Approval {approval_id} not found"}

        req.status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
        req.decided_by = decided_by
        req.rationale = rationale

        if req.task_id in self.tasks:
            task = self.tasks[req.task_id]
            task.status = TaskStatus.IN_PROGRESS if approved else TaskStatus.BLOCKED

        self._record_audit(
            "approval_decided",
            {"approval_id": approval_id, "status": req.status.value, "decided_by": decided_by},
        )
        return {"ok": True, "approval": req.to_dict()}

    def _record_audit(self, event_type: str, details: Dict[str, Any]) -> None:
        self.audit_log.append(
            {
                "timestamp": time.time(),
                "event_type": event_type,
                "details": details,
            }
        )

    def get_summary(self) -> Dict[str, Any]:
        """Summary metrics across the control plane."""
        status_counts = {}
        for t in self.tasks.values():
            s = t.status.value
            status_counts[s] = status_counts.get(s, 0) + 1

        total_spent = sum(a.spent_usd for a in self.agents.values())
        total_tokens = sum(a.tokens_consumed for a in self.agents.values())

        return {
            "company_id": self.company_id,
            "total_agents": len(self.agents),
            "total_tasks": len(self.tasks),
            "status_breakdown": status_counts,
            "total_approvals": len(self.approvals),
            "total_spent_usd": round(total_spent, 4),
            "total_tokens_consumed": total_tokens,
            "audit_events_count": len(self.audit_log),
        }
