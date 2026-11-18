# -*- coding: utf-8 -*-
"""Virtu 多智能体分工运行时 (Swarm Orchestrator)。

把 AGENTS.md §4 中"规划中"的四项契约落成**真实可运行**代码：

1. **SWARM 层级委派**：``SwarmCommander`` 把任务分解为 DAG 子任务，派发给
   专业 worker 智能体（几何解析 / 标准可行性 / 工艺规划 / 刀路生成 / 仿真审计），
   worker 接到真实模块（surface_observability / stock_derivation /
   product_integrity_gate / design_web_self_correction / setup_vericut_simulation），
   而非 agent_team.py 里那些假引擎桩。

2. **Blackboard 写锁租约 (Write-Lock Lease)**：``Blackboard`` 用 ``threading.Condition``
   实现——任何 worker 修改共享键前必须先 ``acquire`` 租约（带 TTL 与审计日志），
   并行 worker 对同一键的写入被强制串行化，杜绝竞态。

3. **Meta-SOP 文档交接**：严格 ``PRD.md -> ARCHITECTURE.md -> TASKS.md -> CODE_MODEL
   -> VERIFICATION_REPORT.json`` 文档链，每阶段校验前置文档齐备后才放行下一阶段，
   所有文档落盘到 Blackboard 与本地目录（可复现、可审计）。

4. **AdversarialCritic 红蓝辩论**：红队对蓝队交付物做**可证伪**的缺陷狩猎
   （无几何证据却宣称成功 / 残料超差 / 成品门失败 / 假联网 / 毛坯非成品派生），
   门禁植入坏样本必须判红。

全程遵循测量宪法：任何 basis 取 measured / offline_kb / asserted，未实测不得宣称 success。
"""

from __future__ import annotations

import os
import sys
import io
import copy
import json
import time
import math
import contextlib
import inspect
import threading
import uuid
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from virtu_omni.memory.hindsight_adapter import (
        VirtuHindsightMemory,
        build_swarm_coordinate_contract,
    )
except Exception:  # pragma: no cover
    VirtuHindsightMemory = None
    build_swarm_coordinate_contract = None

logger = logging.getLogger("virtu_omni.agent.swarm_orchestrator")

WORKSPACE_DIR = Path(__file__).resolve().parent.parent.parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))


# ===========================================================================
# 1. Blackboard 共享内存 + 写锁租约 (Write-Lock Lease)
# ===========================================================================
@dataclass
class Lease:
    lease_id: str
    holder: str
    key: str
    acquired_at: float
    expires_at: float


class Blackboard:
    """多智能体共享黑板。写共享键前必须持有该键的写锁租约；并行写入被串行化。

    读不需要锁（读者不阻塞）。租约有 TTL，超时自动失效，避免死锁；持有方可续租。
    所有 acquire / write / release 进入审计日志，便于复现与证伪。
    """

    def __init__(self, lease_ttl_s: float = 30.0):
        self._store: Dict[str, Any] = {}
        self._meta: Dict[str, Dict[str, Any]] = {}
        self._lease: Dict[str, Lease] = {}          # key -> 当前持有者租约
        self._ttl = lease_ttl_ttl = lease_ttl_s
        self._cond = threading.Condition()
        self._audit: List[Dict[str, Any]] = []
        self._lock = self._cond  # 语义别名

    # ---- 写锁租约 ----
    def acquire(self, holder: str, key: str, timeout_s: float = 10.0) -> Lease:
        """获取 key 的写锁租约；若被他人持有且未超时则阻塞等待；超时抛 LeaseTimeout。"""
        deadline = time.time() + timeout_s
        with self._cond:
            while True:
                now = time.time()
                cur = self._lease.get(key)
                if cur is None or now >= cur.expires_at:
                    # 键空闲或租约已过期 -> 授予
                    lease = Lease(
                        lease_id=uuid.uuid4().hex[:12],
                        holder=holder, key=key,
                        acquired_at=now, expires_at=now + self._ttl,
                    )
                    self._lease[key] = lease
                    self._audit.append({"t": now, "op": "acquire", "holder": holder,
                                        "key": key, "lease_id": lease.lease_id})
                    return lease
                if now >= deadline:
                    raise LeaseTimeout(
                        f"worker={holder} 在 {timeout_s}s 内未能获取键 {key!r} 的写锁"
                        f"（当前持有者={cur.holder} 租约 {cur.lease_id}）")
                remain = min(cur.expires_at - now, deadline - now)
                self._cond.wait(remain)

    def write(self, lease: Lease, key: str, value: Any,
              basis: str = "asserted", evidence: Optional[str] = None) -> None:
        """在持有效租约的前提下写入共享键；否则抛 LeaseError。"""
        now = time.time()
        with self._cond:
            cur = self._lease.get(key)
            if cur is None or cur.lease_id != lease.lease_id or now >= cur.expires_at:
                raise LeaseError(
                    f"worker={lease.holder} 对键 {key!r} 的写操作被拒："
                    f"未持有有效租约（当前={cur.lease_id if cur else None}）")
            self._store[key] = value
            self._meta[key] = {
                "writer": lease.holder, "written_at": now,
                "basis": basis, "evidence": evidence,
            }
            self._audit.append({"t": now, "op": "write", "holder": lease.holder,
                                "key": key, "basis": basis})

    def release(self, lease: Lease) -> None:
        with self._cond:
            cur = self._lease.get(lease.key)
            if cur is not None and cur.lease_id == lease.lease_id:
                del self._lease[lease.key]
                self._audit.append({"t": time.time(), "op": "release",
                                    "holder": lease.holder, "key": lease.key})
                # 释放即唤醒等待者：否则竞争者要睡满旧租约 TTL 才复查，
                # 短持有 + 长 TTL 时表现为"明明已释放却仍 LeaseTimeout"。
                self._cond.notify_all()

    def renew(self, lease: Lease, extra_s: float = 10.0) -> bool:
        with self._cond:
            cur = self._lease.get(lease.key)
            if cur is not None and cur.lease_id == lease.lease_id:
                cur.expires_at = time.time() + extra_s
                self._cond.notify_all()
                return True
            return False

    # ---- 读（无需锁）----
    def read(self, key: str) -> Any:
        # 返回深拷贝：读者拿到的是快照而非活引用，无法绕过写锁租约直接改共享态。
        # write 走"重新绑定"而非原地改值，故无锁拷贝仍是一致的（读者不阻塞）。
        return copy.deepcopy(self._store.get(key))

    def meta(self, key: str) -> Dict[str, Any]:
        return copy.deepcopy(self._meta.get(key, {}))

    def keys(self) -> List[str]:
        return list(self._store.keys())

    def snapshot(self) -> Dict[str, Any]:
        return {k: {"value": copy.deepcopy(v),
                    "meta": copy.deepcopy(self._meta.get(k, {}))}
                for k, v in list(self._store.items())}

    def audit_log(self) -> List[Dict[str, Any]]:
        return list(self._audit)


class LeaseTimeout(RuntimeError):
    pass


class LeaseError(RuntimeError):
    pass


# ===========================================================================
# 2. Meta-SOP 文档交接契约
# ===========================================================================
META_SOP_STAGES = ["PRD", "ARCHITECTURE", "TASKS", "CODE_MODEL", "VERIFICATION_REPORT"]


@dataclass
class MetaSOPDoc:
    stage: str
    author_agent: str
    basis: str                      # measured / offline_kb / asserted
    content: Dict[str, Any]
    requires_next: List[str] = field(default_factory=list)  # 下一阶段必须包含的字段

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage": self.stage, "author_agent": self.author_agent,
            "basis": self.basis, "content": self.content,
            "requires_next": self.requires_next,
        }


def meta_sop_key(stage: str) -> str:
    return f"meta_sop.{stage}"


def handoff_gate(bb: Blackboard, stage: str, prior_stage: Optional[str],
                 required_fields: List[str], content: Dict[str, Any],
                 author: str, basis: str) -> MetaSOPDoc:
    """文档交接门：前置文档齐备且含必需字段，才允许写下一阶段文档；否则抛 HandoffError。"""
    if prior_stage is not None:
        prior = bb.read(meta_sop_key(prior_stage))
        if prior is None:
            raise HandoffError(
                f"文档交接被拒：前置阶段 {prior_stage} 尚未产出，无法进入 {stage}")
        prior_content = prior.get("content") or {}

        def _satisfied(f: str) -> bool:
            # 仅"键存在"不够：值为 None / 空容器等于该字段没产出（空壳交接），
            # 必须判红。标量 0/False 是合法取值，不算空。
            if f not in prior_content:
                return False
            v = prior_content[f]
            if v is None:
                return False
            if isinstance(v, (list, dict, tuple, set, str)) and len(v) == 0:
                return False
            return True

        missing = [f for f in required_fields if not _satisfied(f)]
        if missing:
            raise HandoffError(
                f"文档交接被拒：{prior_stage} 缺少或空置下一阶段所需字段 {missing}，"
                f"无法进入 {stage}")
    doc = MetaSOPDoc(stage=stage, author_agent=author, basis=basis,
                     content=content)
    lease = bb.acquire(author, meta_sop_key(stage))
    try:
        bb.write(lease, meta_sop_key(stage), doc.to_dict(), basis=basis,
                 evidence=f"Meta-SOP 阶段 {stage} 由 {author} 产出")
    finally:
        bb.release(lease)
    return doc


class HandoffError(RuntimeError):
    pass


def _render_meta_sop_markdown(doc: Dict[str, Any]) -> str:
    lines = [
        f"# {doc.get('stage')}",
        "",
        f"- 作者 (author): `{doc.get('author_agent')}`",
        f"- 证据基础 (basis): `{doc.get('basis')}`",
        "",
    ]
    for key, val in (doc.get("content") or {}).items():
        if isinstance(val, (dict, list)):
            lines += [f"## {key}", "", "```json",
                      json.dumps(val, ensure_ascii=False, indent=2, default=str),
                      "```", ""]
        else:
            lines.append(f"- **{key}**: `{val}`")
    return "\n".join(lines) + "\n"


def materialize_meta_sop(bb: Blackboard, output_dir: str) -> List[str]:
    """把 Meta-SOP 文档落盘到 ``<output_dir>/meta_sop/``，返回写出路径列表。

    文档交接不能只活在内存黑板里——落盘才能被人工复审、被下游 agent 直接引用。
    """
    doc_dir = os.path.join(output_dir, "meta_sop")
    os.makedirs(doc_dir, exist_ok=True)
    written: List[str] = []
    for stage in META_SOP_STAGES:
        doc = bb.read(meta_sop_key(stage))
        if not doc:
            continue
        if stage == "VERIFICATION_REPORT":
            path = os.path.join(doc_dir, f"{stage}.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(doc.get("content", doc), fh, ensure_ascii=False,
                          indent=2, default=str)
        else:
            path = os.path.join(doc_dir, f"{stage}.md")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(_render_meta_sop_markdown(doc))
        written.append(path)
    return written


# ===========================================================================
# 3. 真实 Worker 智能体（接到现有模块）
# ===========================================================================
def resolve_sample_assets_for_task(
    task: Dict[str, Any],
    workspace_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """根据任务语义与工作区样本库反推应绑定的 design_stl / 样本毛坯 / VERICUT 工程与毛坯形状约束。

    不再一律硬编码成 ``AE_CLOSED_IMPELLER_NASA1975.stl`` 圆柱！
    """
    root = Path(workspace_dir) if workspace_dir is not None else WORKSPACE_DIR
    t = task if isinstance(task, dict) else {}
    text = " ".join(str(t.get(k) or "") for k in ("part_type", "prompt", "wish", "stock_shape")).lower()
    explicit_design = t.get("design_stl")

    is_impeller = any(tok in text for tok in ("封闭式叶轮", "整体叶轮", "叶轮", "整体叶盘", "impeller", "blisk"))
    is_blade = any(tok in text for tok in ("涡轮叶片", "航空叶片", "工作叶片", "导向叶片", "叶片", "turbine_blade", "turbine blade", "airfoil", "榫头")) and not is_impeller
    wants_box = any(tok in text for tok in ("包容块", "方料", "方块", "矩形毛坯", "box", "block"))

    out: Dict[str, Any] = {
        "part_family": "generic",
        "stock_hint": str(t.get("stock_shape") or ""),
        "expected_stock_shape": "box" if wants_box else None,
        "design_stl": str(explicit_design) if explicit_design else None,
        "design_source": "explicit" if explicit_design else None,
        "sample_design_stl": None,
        "sample_stock_stl": str(t["sample_stock_stl"]) if t.get("sample_stock_stl") else None,
        "sample_vcproject": str(t["sample_vcproject"]) if t.get("sample_vcproject") else None,
        "nc_path": str(t["nc_path"]) if t.get("nc_path") else None,
    }

    if is_blade:
        out["part_family"] = "turbine_blade_5axis"
        out["stock_hint"] = "box"
        out["expected_stock_shape"] = "box"
        cand_design = root / "00_归档" / "01_历史备份" / "eval_archive" / "turbine_blade_design.stl"
        alt_design = root / "projects" / "turbine_blade_autonomous_v100" / "turbine_blade_3d_cad.stl"
        cand_stock = root / "00_归档" / "01_历史备份" / "eval_archive" / "turbine_blade_stock.stl"
        cand_vcp = root / "01_CAD交付件" / "turbine_blade_vericut.vcproject"
        cand_nc = root / "01_CAD交付件" / "turbine_blade_5axis.nc"
        if cand_design.exists():
            out["sample_design_stl"] = str(cand_design)
            if not out["design_stl"]:
                out["design_stl"] = str(cand_design)
                out["design_source"] = "sample_library"
        elif alt_design.exists() and not out["design_stl"]:
            out["design_stl"] = str(alt_design)
            out["design_source"] = "sample_library"
        if not out["sample_stock_stl"] and cand_stock.exists():
            out["sample_stock_stl"] = str(cand_stock)
        if not out["sample_vcproject"] and cand_vcp.exists():
            out["sample_vcproject"] = str(cand_vcp)
        if not out["nc_path"] and cand_nc.exists():
            out["nc_path"] = str(cand_nc)
    elif is_impeller and wants_box:
        out["part_family"] = "impeller_bounding_block_5axis"
        out["stock_hint"] = "box"
        out["expected_stock_shape"] = "box"
        cand_design = root / "work" / "impeller_box_stock" / "AE-CI-060_BOX_impeller.stl"
        cand_stock = root / "work" / "impeller_box_stock" / "AE-CI-060_BOX_stock_box.stl"
        cand_vcp = root / "work" / "impeller_box_stock" / "AE-CI-060_BOX_5axis.vcproject"
        cand_nc = root / "work" / "impeller_box_stock" / "AE-CI-060_BOX_5axis.nc"
        if cand_design.exists():
            out["sample_design_stl"] = str(cand_design)
            if not out["design_stl"]:
                out["design_stl"] = str(cand_design)
                out["design_source"] = "sample_library"
        if not out["sample_stock_stl"] and cand_stock.exists():
            out["sample_stock_stl"] = str(cand_stock)
        if not out["sample_vcproject"] and cand_vcp.exists():
            out["sample_vcproject"] = str(cand_vcp)
        if not out["nc_path"] and cand_nc.exists():
            out["nc_path"] = str(cand_nc)
    elif is_impeller:
        out["part_family"] = "impeller"

    if not out["design_stl"]:
        default_imp = root / "artifacts" / "aero_closed_impeller" / "AE_CLOSED_IMPELLER_NASA1975.stl"
        if default_imp.exists():
            out["design_stl"] = str(default_imp)
            out["design_source"] = "fallback_nasa1975"
    return out


def _call_compat(fn, **kw):
    """兼容旧版 0 参 stub 与新版多参函数/Mock，仅按签名传参。"""
    try:
        sig = inspect.signature(fn)
        has_kw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
        if has_kw:
            return fn(**kw)
        accepted = {k: v for k, v in kw.items() if k in sig.parameters}
        return fn(**accepted) if accepted else fn()
    except (ValueError, TypeError):
        return fn()


def _get_search_provider():
    """真实联网优先；bs4 缺失 / 无网时显式降级 Mock 知识库并标注 online=False。"""
    try:
        from design_web_self_correction import RealSearchProvider, MockSearchProvider
        try:
            prov = RealSearchProvider()
            return prov, prov.is_online
        except Exception:
            return MockSearchProvider(), False
    except Exception:
        # design_web_self_correction 自身不可用：退回纯离线 Mock
        from design_web_self_correction import MockSearchProvider
        return MockSearchProvider(), False


def geometry_worker(task: Dict[str, Any], bb: Blackboard) -> Dict[str, Any]:
    """几何解析 Agent：把不透明曲面转成智能体能"看见"的证据。"""
    from surface_observability import observe_surface
    resolved = resolve_sample_assets_for_task(task)
    mesh = task.get("design_stl") or resolved.get("design_stl")
    spindle = task.get("spindle_axis", "Z")
    rep = observe_surface(mesh, spindle_axis=spindle,
                          tool_radius_mm=task.get("tool_radius_mm", 3.0),
                          step_over_mm=None,  # None=在最佳可行步距下评估残料
                          finish_allowance_mm=task.get("allowance_mm", 0.01))
    payload = {
        "mesh": rep.mesh,
        "triangle_count": rep.triangle_count,
        "evidence_status": rep.evidence_status,
        "curvature_max": rep.curvature.get("max"),
        "high_curvature_face_count": rep.high_curvature_face_count,
        "high_curvature_pct": rep.high_curvature_pct,
        "faces_over_allowance": rep.faces_over_allowance,
        "faces_over_allowance_pct": rep.faces_over_allowance_pct,
        "undercut_face_count": rep.undercut_face_count,
        "requires_multiaxis": rep.requires_multiaxis,
        "recommended_step_over_mm": rep.recommended_step_over_mm,
        "recommended_tool_radius_mm": rep.recommended_tool_radius_mm,
        "faces_over_allowance_pct": rep.faces_over_allowance_pct,
        "images": {k: v for k, v in (rep.images or {}).items() if v},
        "summary": rep.summary,
    }
    lease = bb.acquire("GeometryParsingAgent", "geometry")
    try:
        bb.write(lease, "geometry", payload, basis=rep.evidence_status,
                 evidence=f"observe_surface 实测 {rep.triangle_count} 面")
    finally:
        bb.release(lease)
    return payload


def standards_worker(task: Dict[str, Any], bb: Blackboard) -> Dict[str, Any]:
    """标准可行性 Agent：校验材料 / 表面粗糙度 / 公差是否可由铣削实现（真实工艺边界）。"""
    material = task.get("material", "AL6061-T6")
    ra = task.get("surface_finish", "Ra1.6")
    tol = task.get("tolerance", "IT8")
    # 真实工程边界（铣削可达性，basis=offline_kb 领域常识）
    ra_val = _parse_ra(ra)
    ra_achievable = ra_val >= 0.2 and ra_val <= 6.3     # 铣削 Ra 0.2~6.3
    it_num = _parse_it(tol)
    it_achievable = it_num <= 10                          # 普通铣削 IT7~IT10 经济
    feasible = ra_achievable and it_achievable
    issues = []
    if not ra_achievable:
        issues.append(f"表面粗糙度 {ra} 超出铣削经济范围(Ra0.2~6.3)")
    if not it_achievable:
        issues.append(f"公差 {tol} 超出普通铣削经济等级(≤IT10)")
    payload = {
        "material": material, "surface_finish": ra, "tolerance": tol,
        "ra_achievable": ra_achievable, "it_achievable": it_achievable,
        "feasible": feasible, "issues": issues,
    }
    lease = bb.acquire("StandardsAgent", "standards")
    try:
        bb.write(lease, "standards", payload, basis="offline_kb",
                 evidence="铣削工艺边界常识（Ra0.2~6.3 / IT≤10）")
    finally:
        bb.release(lease)
    return payload


def planning_worker(task: Dict[str, Any], bb: Blackboard) -> Dict[str, Any]:
    """工艺规划 Agent：综合几何证据 + 联网修正，输出刀路策略参数。"""
    geom = bb.read("geometry") or {}
    stds = bb.read("standards") or {}
    design_spec = {
        "part_type": task.get("part_type", "复杂曲面零件"),
        "material": task.get("material", "AL6061-T6"),
        "surface_finish": task.get("surface_finish", "Ra1.6"),
        "tolerance": task.get("tolerance", "IT8"),
    }
    topic = f"{design_spec['part_type']} {design_spec['material']} 五轴铣削 表面粗糙度 公差"
    provider, online = _get_search_provider()
    corrections: List[Dict[str, Any]] = []
    searched = False
    try:
        from design_web_self_correction import verify_and_correct
        rep = verify_and_correct(design_spec, topic, provider=provider)
        searched = rep.searched
        online = bool(getattr(rep, "online", online))
        for c in rep.corrections:
            corrections.append({"field": c.field, "current": c.current,
                               "suggested": c.suggested, "evidence": c.evidence})
    except Exception as exc:
        logger.warning("工艺规划联网修正失败，跳过: %s", exc)

    # 几何推荐优先，联网修正覆盖
    coord_contract = bb.read("coordinate_contract") or {}
    mem_ctx = bb.read("memory_context") or {}
    rec_step = geom.get("recommended_step_over_mm") or 0.5
    rec_tool = geom.get("recommended_tool_radius_mm") or 3.0
    require_5axis = bool(geom.get("requires_multiaxis")) or \
        (geom.get("undercut_face_count", 0) > 0)
    resolved = resolve_sample_assets_for_task(task)
    payload = {
        "design_spec": design_spec,
        "part_family": resolved.get("part_family"),
        "stock_hint": resolved.get("stock_hint"),
        "expected_stock_shape": resolved.get("expected_stock_shape"),
        "recommended_step_over_mm": round(rec_step, 4),
        "recommended_tool_radius_mm": rec_tool,
        "requires_multiaxis": require_5axis,
        "searched": searched,
        "online": online,
        "corrections": corrections,
        "standards_feasible": stds.get("feasible", True),
        "cam_coordinate_system": coord_contract.get("cam_simulation_system", "VERICUT_9.6_NX_12_CNC_Z_UP"),
        "memory_guidance_applied": bool(mem_ctx.get("summary") or mem_ctx.get("hits")),
        "basis": "measured" if (geom.get("evidence_status") == "measured") else "asserted",
    }
    lease = bb.acquire("ProcessPlanningAgent", "process_plan")
    try:
        bb.write(lease, "process_plan", payload, basis=payload["basis"],
                 evidence=f"几何证据(ev={geom.get('evidence_status')})+联网(online={online})")
    finally:
        bb.release(lease)
    return payload


def toolpath_worker(task: Dict[str, Any], bb: Blackboard) -> Dict[str, Any]:
    """刀路生成 Agent：成品/样本反推派生毛坯 + 写出 VERICUT 工程（接到真实模块）。"""
    plan = bb.read("process_plan") or {}
    resolved = resolve_sample_assets_for_task(task)
    part_type = str(task.get("part_type") or "")
    stock_hint = str(resolved.get("stock_hint") or task.get("stock_shape") or "")
    design_mesh = task.get("design_stl") or resolved.get("design_stl")
    sample_stock_stl = resolved.get("sample_stock_stl")
    sample_design_stl = resolved.get("sample_design_stl")
    sample_vcproject = resolved.get("sample_vcproject")

    project_path = None
    stock_source = None
    stock_basis = None
    stock_shape = None
    stock_dims: Optional[Dict[str, Any]] = None
    inverse_ev: Dict[str, Any] = {}
    vericut_report: Optional[Dict[str, Any]] = None
    nc_file = resolved.get("nc_path")

    try:
        import scripts.setup_vericut_simulation as sv
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            r = _call_compat(
                sv.main,
                design_mesh=design_mesh,
                part_type=part_type,
                stock_hint=stock_hint,
                sample_stock_mesh=sample_stock_stl,
                sample_vcproject=sample_vcproject,
                sample_design_mesh=sample_design_stl,
            )
        project_path = r.get("project")
        stock_source = r.get("stock_source")
        raw_basis = r.get("stock_basis")
        stock_basis = "measured_from_product_mesh" if raw_basis in (
            "measured_from_product_mesh", "measured_from_sample_inverse_derivation"
        ) else raw_basis
        stock_shape = r.get("stock_shape")
        stock_dims = r.get("stock_dims")
        inverse_ev = r.get("inverse_sample_evidence") or {}
        if stock_basis and raw_basis and raw_basis != stock_basis:
            inverse_ev["derivation_mode"] = raw_basis
        nc_file = r.get("nc_file") or nc_file
        vericut_report = r
    except Exception as exc:
        logger.warning("VERICUT 工程写出失败，退回逻辑派生: %s", exc)
        try:
            import scripts.setup_vericut_simulation as sv
            spec, raw_basis = _call_compat(
                sv.derive_stock_from_product,
                design_mesh=Path(design_mesh) if design_mesh else None,
                part_type=part_type,
                stock_hint=stock_hint,
                sample_stock_mesh=Path(sample_stock_stl) if sample_stock_stl else None,
                sample_vcproject=Path(sample_vcproject) if sample_vcproject else None,
                sample_design_mesh=Path(sample_design_stl) if sample_design_stl else None,
            )
            project_path = None
            stock_source = "logical_only"
            stock_basis = "measured_from_product_mesh" if raw_basis in (
                "measured_from_product_mesh", "measured_from_sample_inverse_derivation"
            ) else raw_basis
            stock_shape = spec.shape
            stock_dims = dict(spec.dims)
            inverse_ev = dict(getattr(sv, "LAST_INVERSE_EVIDENCE", {}) or {})
        except Exception as exc2:
            logger.warning("毛坯逻辑派生也失败: %s", exc2)
            stock_source = "failed"
            stock_basis = "asserted"
    payload = {
        "project": project_path,
        "stock_source": stock_source,
        "stock_basis": stock_basis,
        "stock_shape": stock_shape,
        "stock_dims": stock_dims,
        "nc_file": nc_file,
        "sample_vcproject": sample_vcproject,
        "inverse_sample_evidence": inverse_ev,
        "step_over_mm": plan.get("recommended_step_over_mm"),
        "tool_radius_mm": plan.get("recommended_tool_radius_mm"),
        "requires_multiaxis": plan.get("requires_multiaxis", False),
        "vericut_report": vericut_report,
    }
    lease = bb.acquire("ToolpathGenerationAgent", "toolpath")
    try:
        bb.write(lease, "toolpath", payload, basis="measured" if stock_basis ==
                 "measured_from_product_mesh" else stock_basis or "asserted",
                 evidence=f"毛坯来源={stock_source}, 工程={project_path}")
    finally:
        bb.release(lease)
    return payload


def audit_worker(task: Dict[str, Any], bb: Blackboard) -> Dict[str, Any]:
    """仿真审计 Agent：成品完整性门 + VERICUT 偏差日志，产出可证伪审计结论。"""
    geom = bb.read("geometry") or {}
    tp = bb.read("toolpath") or {}
    mesh = task.get("design_stl")
    defects: List[str] = []
    gate_passed = True
    TOOL_CAP_MM = 12.0
    # 几何证据必须实测
    if geom.get("evidence_status") != "measured":
        defects.append(f"几何证据非实测(ev={geom.get('evidence_status')})，不得宣称成功")
        gate_passed = False
    # 规范可达性：是否存在 ≤ 上限的可行刀具（凹面需更大刀具压住残料）
    rec_tool = geom.get("recommended_tool_radius_mm")
    if rec_tool is None or (isinstance(rec_tool, float) and math.isinf(rec_tool)) or \
            (isinstance(rec_tool, (int, float)) and rec_tool > TOOL_CAP_MM):
        defects.append(f"当前规范(残料≤{task.get('allowance_mm', 0.01)}mm)不可达："
                       f"所需刀具半径={rec_tool}mm 超出可行上限 {TOOL_CAP_MM}mm")
        gate_passed = False
    # 毛坯必须来自成品/样本反推，且形状须与零件语义匹配（涡轮叶片/包容块要求不得套圆柱）
    if tp.get("stock_basis") not in (None, "measured_from_product_mesh", "measured_from_sample_inverse_derivation"):
        defects.append(f"毛坯非成品派生(basis={tp.get('stock_basis')})")
        gate_passed = False
    resolved = resolve_sample_assets_for_task(task)
    actual_shape = tp.get("stock_shape") or ((tp.get("vericut_report") or {}).get("stock_shape"))
    if resolved.get("expected_stock_shape") == "box" and actual_shape and actual_shape != "box":
        defects.append(f"要求包容块/涡轮叶片方料(box)，但实际毛坯形状为 {actual_shape!r}")
        gate_passed = False
    # 负角但规划未要求多轴
    if (geom.get("undercut_face_count", 0) or 0) > 0 and not tp.get("requires_multiaxis"):
        defects.append("存在负角但刀路未启用多轴")
        gate_passed = False

    # ---- Auto-Diff 真实偏差证据 ----
    # 此前这里完全没有 Auto-Diff（等于 §2E 的这道门在 Swarm 中被跳过）。
    # 现在：提供载荷 -> 用 triage 归一化后按红/蓝/绿判定；未提供 -> 如实标注未取证。
    autodiff: Dict[str, Any] = {"basis": "not_provided", "verdict": None}
    require_ad = bool(task.get("require_autodiff", False))
    payload_path = task.get("autodiff_payload")
    if payload_path:
        try:
            from vericut_autodiff_adapter import evidence_from_file
            ratios, info = evidence_from_file(str(payload_path), task.get("vericut_log"))
            autodiff = {
                "basis": "measured_payload",
                "verdict": info["verdict"],
                "evidence_sufficient": info["evidence_sufficient"],
                "accepted": info["accepted"],
                "codes": info["blocking_codes"],
                "ratios": ratios,
            }
            if not info["accepted"]:
                defects.append(
                    "Auto-Diff 未通过({}): 红={:.4f} 蓝={:.4f} 绿={:.4f} codes={}".format(
                        info["verdict"], ratios["gouge_ratio"],
                        ratios["excess_ratio"], ratios["in_tol_ratio"],
                        info["blocking_codes"]))
                gate_passed = False
        except Exception as exc:
            autodiff = {"basis": "payload_error",
                        "error": "{}: {}".format(type(exc).__name__, exc)}
            # §8.4：解析/读取失败一律判红。提供了载荷却读不出证据 = 证据链断裂，
            # 与 require_ad 无关——否则坏载荷在 require_ad=False 时被静默吞成"通过"。
            defects.append("Auto-Diff 载荷读取/解析失败（证据链断裂）: {}".format(exc))
            gate_passed = False
    elif require_ad:
        defects.append("require_autodiff=True 但未提供 Auto-Diff 载荷")
        gate_passed = False

    payload = {
        "passed": gate_passed,
        "defects": defects,
        "evidence_status": geom.get("evidence_status", "unmeasured"),
        "basis": "measured" if gate_passed else "asserted",
        "autodiff": autodiff,
    }
    lease = bb.acquire("SimulationAuditAgent", "audit")
    try:
        bb.write(lease, "audit", payload, basis=payload["basis"],
                 evidence="成品完整性门 + 残料/负角/毛坯来源校验")
    finally:
        bb.release(lease)
    return payload


def _parse_ra(ra: str) -> float:
    try:
        return float(str(ra).replace("Ra", "").strip())
    except Exception:
        return 1.6


def _parse_it(tol: str) -> int:
    try:
        return int(str(tol).upper().replace("IT", "").strip())
    except Exception:
        return 8


# ===========================================================================
# 4. AdversarialCritic 红蓝辩论（可证伪）
# ===========================================================================
class AdversarialCritic:
    """红队：对蓝队交付物（VERIFICATION_REPORT + Blackboard）做缺陷狩猎。

    门禁可证伪：植入坏交付物（success=True 但证据缺失 / 残料超差）必须判红。
    """

    def debate(self, deliverable: Dict[str, Any], bb: Blackboard) -> Dict[str, Any]:
        defects: List[Dict[str, Any]] = []
        geom = bb.read("geometry") or {}
        plan = bb.read("process_plan") or {}
        tp = bb.read("toolpath") or {}
        audit = bb.read("audit") or {}

        claimed_success = bool(deliverable.get("success"))

        # 红队逐项核查（每项都是可证伪断言）
        if claimed_success and geom.get("evidence_status") != "measured":
            defects.append({"id": "RED-NO-GEOM-EVIDENCE",
                            "severity": "fatal",
                            "finding": "蓝队宣称成功，但 Blackboard 几何证据非实测",
                            "evidence": f"geometry.evidence_status={geom.get('evidence_status')}"})
        if claimed_success:
            rec_tool = geom.get("recommended_tool_radius_mm")
            tool_inf = isinstance(rec_tool, float) and math.isinf(rec_tool)
            if rec_tool is None or tool_inf or (isinstance(rec_tool, (int, float)) and rec_tool > 12.0):
                defects.append({"id": "RED-SPEC-UNREACHABLE",
                                "severity": "fatal",
                                "finding": "蓝队宣称成功，但当前规范(残料允差)不可达：所需刀具半径超限",
                                "evidence": f"recommended_tool_radius_mm={rec_tool}"})
        if claimed_success and tp.get("stock_basis") not in (
            None, "measured_from_product_mesh", "measured_from_sample_inverse_derivation"
        ):
            defects.append({"id": "RED-STOCK-NOT-PRODUCT",
                            "severity": "fatal",
                            "finding": "蓝队宣称成功，但毛坯非成品派生（疑似超长圆柱）",
                            "evidence": f"stock_basis={tp.get('stock_basis')}"})
        prd_task = ((bb.read("meta_sop.PRD") or {}).get("content") or {}).get("task") or {}
        want_box = (
            plan.get("expected_stock_shape") == "box"
            or deliverable.get("expected_stock_shape") == "box"
            or resolve_sample_assets_for_task(prd_task).get("expected_stock_shape") == "box"
        )
        actual_shape = tp.get("stock_shape") or ((tp.get("vericut_report") or {}).get("stock_shape"))
        if want_box and actual_shape and actual_shape != "box":
            defects.append({"id": "RED-WRONG-STOCK-SHAPE",
                            "severity": "fatal",
                            "finding": "航空涡轮叶片/包容块任务却使用了圆柱等错误毛坯形状（未按样本反推 box 毛坯）",
                            "evidence": f"expected=box actual_shape={actual_shape} dims={tp.get('stock_dims')}"})
        if plan.get("online") is True and not plan.get("corrections"):
            defects.append({"id": "RED-FAKE-ONLINE",
                            "severity": "major",
                            "finding": "规划宣称已联网修正(online=True)却无任何修正证据（假联网）",
                            "evidence": f"online={plan.get('online')} corrections={plan.get('corrections')}"})
        # 审计门失败本身就是缺陷——不应因"蓝队没宣称成功"而放过，
        # 否则会出现 audit_passed=False 但 red_team_gate=True 的自相矛盾。
        if audit.get("passed") is False:
            defects.append({"id": "RED-AUDIT-FAILED",
                            "severity": "fatal",
                            "finding": "仿真审计门未通过",
                            "evidence": str(audit.get("defects"))})

        # Auto-Diff 证据链（§2E 红/蓝/绿偏差图）
        ad = audit.get("autodiff") or {}
        if ad.get("basis") == "measured_payload" and not ad.get("accepted"):
            defects.append({"id": "RED-AUTODIFF-REJECT",
                            "severity": "fatal",
                            "finding": "Auto-Diff 判定未通过（过切/残料/证据不足）",
                            "evidence": "verdict={} codes={} ratios={}".format(
                                ad.get("verdict"), ad.get("codes"), ad.get("ratios"))})
        if ad.get("basis") == "payload_error":
            defects.append({"id": "RED-AUTODIFF-ERROR",
                            "severity": "fatal",
                            "finding": "Auto-Diff 载荷读取/解析失败，偏差证据链断裂（§8.4 解析失败必判红）",
                            "evidence": str(ad.get("error"))})
        if claimed_success and ad.get("basis") == "not_provided":
            defects.append({"id": "RED-NO-AUTODIFF",
                            "severity": "major",
                            "finding": "宣称成功但未提供 Auto-Diff 偏差证据（该门未取证，非通过）",
                            "evidence": "audit.autodiff.basis=not_provided"})

        gate_passed = len([d for d in defects if d["severity"] == "fatal"]) == 0
        return {
            "red_team_findings": defects,
            "gate_passed": gate_passed,
            "severity_counts": {
                "fatal": len([d for d in defects if d["severity"] == "fatal"]),
                "major": len([d for d in defects if d["severity"] == "major"]),
            },
            "debate_rounds": 1,
            "summary": ("红蓝辩论通过：未发现致命缺陷" if gate_passed
                        else f"红蓝辩论拦截：{len(defects)} 项缺陷（含致命）"),
        }


# ===========================================================================
# 5. SwarmCommander 编排
# ===========================================================================
class SwarmCommander:
    """多智能体总指挥：层级委派 + Meta-SOP 文档交接 + 并行写锁 + 红蓝辩论。"""

    def __init__(self, lease_ttl_s: float = 30.0):
        self.bb = Blackboard(lease_ttl_s=lease_ttl_s)
        self.critic = AdversarialCritic()

    def _run_worker_threadsafe(self, fn, task, name) -> Tuple[Dict[str, Any], Optional[str]]:
        try:
            return fn(task, self.bb), None
        except Exception as exc:  # 单步自查：worker 失败即时捕获，不污染黑板上游
            logger.warning("worker %s 失败: %s", name, exc)
            return {"error": str(exc), "status": "FAILED"}, str(exc)

    def solve(self, task: Dict[str, Any], output_dir: Optional[str] = None) -> Dict[str, Any]:
        t0 = time.time()
        task = dict(task or {})
        if not output_dir:
            ts = time.strftime("%Y%m%d_%H%M%S")
            output_dir = str(WORKSPACE_DIR / "runs" / "swarm" / f"{ts}")
        os.makedirs(output_dir, exist_ok=True)

        # P0：先按任务规格生成真实 CAD（build123d BRep + 体积守恒断言），
        # 样本库仅作显式标注的兜底——CAD→CAM 链不再依赖样本回放。
        design_provenance: Dict[str, Any] = {}
        if not task.get("design_stl"):
            try:
                from virtu_omni.engine.parametric_cad_generator import generate_design_assets
                gen = generate_design_assets(task, os.path.join(output_dir, "cad"))
                if gen:
                    design_provenance = gen
                    task["design_stl"] = gen["design_stl"]
            except Exception as exc:
                logger.warning("参数化 CAD 生成失败，退回样本库: %s", exc)
                design_provenance = {"design_source": "generation_failed",
                                     "error": f"{type(exc).__name__}: {exc}"}

        resolved_assets = resolve_sample_assets_for_task(task)
        if not design_provenance:
            design_provenance = {
                "design_source": resolved_assets.get("design_source"),
                "design_stl": resolved_assets.get("design_stl"),
            }
        if not task.get("design_stl") and resolved_assets.get("design_stl"):
            task["design_stl"] = resolved_assets["design_stl"]
        for k in ("sample_stock_stl", "sample_vcproject", "sample_design_stl"):
            if not task.get(k) and resolved_assets.get(k):
                task[k] = resolved_assets[k]
        if not task.get("stock_shape") and resolved_assets.get("expected_stock_shape"):
            task["stock_shape"] = resolved_assets["expected_stock_shape"]

        trace: List[Dict[str, Any]] = []

        # ---- 只读召回 Hindsight 长期记忆 + 写入跨软件坐标系隔离契约 ----
        coord_contract = (
            build_swarm_coordinate_contract(task)
            if build_swarm_coordinate_contract is not None
            else {
                "cad_modeling_system": "SOLIDWORKS_2021_Y_UP",
                "cam_simulation_system": "VERICUT_9.6_NX_12_CNC_Z_UP",
            }
        )
        c_lease = self.bb.acquire("ChiefArchitectAgent", "coordinate_contract")
        try:
            self.bb.write(
                c_lease,
                "coordinate_contract",
                coord_contract,
                basis="offline_kb",
                evidence="SOLIDWORKS Y-up vs VERICUT/NX/CNC Z-up 隔离契约",
            )
        finally:
            self.bb.release(c_lease)

        d_lease = self.bb.acquire("ChiefArchitectAgent", "design_provenance")
        try:
            self.bb.write(
                d_lease, "design_provenance", design_provenance,
                basis=design_provenance.get("basis", "asserted"),
                evidence=f"design_source={design_provenance.get('design_source')}",
            )
        finally:
            self.bb.release(d_lease)

        mem_hits: List[Dict[str, Any]] = []
        mem_summary = str(task.get("memory_context") or "").strip()
        if VirtuHindsightMemory is not None:
            try:
                h_mem = VirtuHindsightMemory()
                q_text = " ".join(
                    str(v) for k, v in task.items()
                    if k in ("part_type", "material", "surface_finish", "tolerance", "wcs") and v
                ) or "VERICUT CNC 五轴 CAD 坐标系"
                mem_hits = h_mem.recall_all_banks(
                    query=q_text,
                    bank_ids=["virtu_cad_cam", "virtu_cnc_machining", "virtu_quality_audit", "default"],
                    max_results=4,
                    update_stats=False,
                )
                if not mem_summary:
                    mem_summary = h_mem.build_domain_memory_context(
                        query=q_text,
                        max_items=4,
                        update_stats=False,
                        include_invariants=True,
                        include_all_invariants_if_unmatched=True,
                    )
            except Exception as exc:
                logger.warning("Swarm Hindsight 只读召回失败，继续用基线契约: %s", exc)

        m_lease = self.bb.acquire("EvolutionAndMemoryAgent", "memory_context")
        try:
            self.bb.write(
                m_lease,
                "memory_context",
                {"summary": mem_summary, "hits": mem_hits, "read_only": True},
                basis="offline_kb",
                evidence=f"Hindsight 只读跨库召回 {len(mem_hits)} 条",
            )
        finally:
            self.bb.release(m_lease)
        trace.append({"stage": "MEMORY_COORD_INIT", "agent": "EvolutionAndMemoryAgent", "hits": len(mem_hits)})

        # ---- Meta-SOP: PRD（架构师分解任务）----
        prd = handoff_gate(
            self.bb, "PRD", None, [],
            {"task": task, "workers": ["GeometryParsing", "Standards", "ProcessPlanning",
                                       "ToolpathGeneration", "SimulationAudit"],
             "coordinate_contract": coord_contract,
             "expected_stock_shape": resolved_assets.get("expected_stock_shape"),
             "sample_assets": resolved_assets,
             "design_provenance": design_provenance,
             "memory_context_len": len(mem_summary),
             "goal": "基于规格生成 CAD 或真实样本/成品几何反推毛坯与五轴工艺（禁止乱设毛坯）"},
            author="ChiefArchitectAgent", basis="asserted")
        trace.append({"stage": "PRD", "agent": "ChiefArchitectAgent"})

        # ---- Meta-SOP: ARCHITECTURE（映射 worker->真实模块）----
        arch = handoff_gate(
            self.bb, "ARCHITECTURE", "PRD", ["workers"],
            {"mapping": {
                "ParametricCAD": "parametric_cad_generator.generate_design_assets (build123d BRep)",
                "GeometryParsing": "surface_observability.observe_surface",
                "Standards": "铣削工艺边界常识",
                "ProcessPlanning": "design_web_self_correction.verify_and_correct",
                "ToolpathGeneration": "stock_derivation + setup_vericut_simulation",
                "SimulationAudit": "audit_worker 自建可证伪门 + vericut_autodiff_adapter",
            }, "parallel_fan": ["GeometryParsing", "Standards"]},
            author="ChiefArchitectAgent", basis="asserted")
        trace.append({"stage": "ARCHITECTURE", "agent": "ChiefArchitectAgent"})

        # ---- Meta-SOP: TASKS（具体子任务）----
        tasks_doc = handoff_gate(
            self.bb, "TASKS", "ARCHITECTURE", ["mapping"],
            {"tasks": {
                "GeometryParsing": "读成品 STL 产出曲率/残料/负角证据",
                "Standards": "校验材料/粗糙度/公差可行性",
                "ProcessPlanning": "综合几何+联网修正定刀路参数",
                "ToolpathGeneration": "成品派生毛坯+写 VERICUT 工程",
                "SimulationAudit": "成品完整性门+残料/负角校验",
            }},
            author="ChiefArchitectAgent", basis="asserted")
        trace.append({"stage": "TASKS", "agent": "ChiefArchitectAgent"})

        # ---- DAG 并行扇出：几何解析 ‖ 标准可行性（两者独立，经写锁并发写黑板）----
        results: Dict[str, Dict[str, Any]] = {}
        errs: Dict[str, Optional[str]] = {}
        g_res, g_err = {}, None
        s_res, s_err = {}, None

        def _geo():
            nonlocal g_res, g_err
            g_res, g_err = self._run_worker_threadsafe(geometry_worker, task, "geometry")
        def _std():
            nonlocal s_res, s_err
            s_res, s_err = self._run_worker_threadsafe(standards_worker, task, "standards")

        th_g = threading.Thread(target=_geo, name="GeometryParsingAgent")
        th_s = threading.Thread(target=_std, name="StandardsAgent")
        th_g.start(); th_s.start(); th_g.join(); th_s.join()
        results["geometry"] = g_res; errs["geometry"] = g_err
        results["standards"] = s_res; errs["standards"] = s_err
        trace.append({"stage": "PARALLEL_FAN", "agents": ["GeometryParsingAgent", "StandardsAgent"],
                      "note": "两 worker 经 Blackboard 写锁并发写共享黑板"})

        # ---- 串行依赖：工艺规划 -> 刀路生成 -> 仿真审计 ----
        p_res, p_err = self._run_worker_threadsafe(planning_worker, task, "planning")
        results["process_plan"] = p_res; errs["planning"] = p_err
        trace.append({"stage": "ProcessPlanning", "agent": "ProcessPlanningAgent"})

        t_res, t_err = self._run_worker_threadsafe(toolpath_worker, task, "toolpath")
        results["toolpath"] = t_res; errs["toolpath"] = t_err
        trace.append({"stage": "ToolpathGeneration", "agent": "ToolpathGenerationAgent"})

        a_res, a_err = self._run_worker_threadsafe(audit_worker, task, "audit")
        results["audit"] = a_res; errs["audit"] = a_err
        trace.append({"stage": "SimulationAudit", "agent": "SimulationAuditAgent"})

        # ---- Meta-SOP: CODE_MODEL（汇总各 worker 真实产出的代码/模型产物）----
        geom_imgs = g_res.get("images", {}) or {}
        code_model = {
            "artifacts": {
                "design_stl": task.get("design_stl"),
                "design_source": design_provenance.get("design_source"),
                "geometry_evidence": geom_imgs,
                "vericut_project": t_res.get("project"),
                "stock_source": t_res.get("stock_source"),
                "stock_basis": t_res.get("stock_basis"),
                "stock_shape": t_res.get("stock_shape"),
                "stock_dims": t_res.get("stock_dims"),
                "nc_file": t_res.get("nc_file"),
                "inverse_sample_evidence": t_res.get("inverse_sample_evidence"),
                "process_plan": {k: p_res.get(k) for k in
                                 ("recommended_step_over_mm", "recommended_tool_radius_mm",
                                  "requires_multiaxis", "online", "corrections",
                                  "expected_stock_shape", "part_family")},
            },
            "standards_feasible": p_res.get("standards_feasible"),
            "audit_passed": a_res.get("passed"),
        }
        handoff_gate(self.bb, "CODE_MODEL", "TASKS", ["tasks"], code_model,
                     author="SwarmCommander", basis="measured")
        trace.append({"stage": "CODE_MODEL", "agent": "SwarmCommander"})

        # ---- 红蓝辩论：红队批判蓝队交付物 ----
        rec_tool = g_res.get("recommended_tool_radius_mm")
        tool_ok = not (rec_tool is None or (isinstance(rec_tool, float) and math.isinf(rec_tool))
                      or (isinstance(rec_tool, (int, float)) and rec_tool > 12.0))
        blue_deliverable = {
            "success": all(e is None for e in errs.values())
            and bool(a_res.get("passed")) and tool_ok,
            "expected_stock_shape": resolved_assets.get("expected_stock_shape"),
            "geometry": g_res, "process_plan": p_res, "toolpath": t_res, "audit": a_res,
        }
        debate = self.critic.debate(blue_deliverable, self.bb)
        trace.append({"stage": "RED_BLUE_DEBATE", "agent": "AdversarialCritic",
                      "gate_passed": debate["gate_passed"]})

        # ---- Meta-SOP: VERIFICATION_REPORT（汇总，诚实 basis）----
        any_fatal = debate["severity_counts"]["fatal"] > 0
        success = (all(e is None for e in errs.values())
                   and bool(a_res.get("passed")) and not any_fatal)
        verification = {
            "success": success,
            "mode": "SWARM",
            "design_source": design_provenance.get("design_source"),
            "cad_generation": {k: design_provenance.get(k) for k in
                               ("family", "volume_mm3", "analytic_volume_mm3",
                                "volume_error_pct", "bbox_mm")
                               if design_provenance.get(k) is not None},
            "workers_run": list(results.keys()),
            "worker_errors": {k: v for k, v in errs.items() if v},
            "geometry_evidence_status": g_res.get("evidence_status"),
            "residual_over_pct": g_res.get("faces_over_allowance_pct"),
            "recommended_tool_radius_mm": g_res.get("recommended_tool_radius_mm"),
            "stock_basis": t_res.get("stock_basis"),
            "stock_shape": t_res.get("stock_shape"),
            "stock_dims": t_res.get("stock_dims"),
            "nc_file": t_res.get("nc_file"),
            "inverse_sample_evidence": t_res.get("inverse_sample_evidence"),
            "online": p_res.get("online"),
            "corrections": p_res.get("corrections"),
            "audit_passed": a_res.get("passed"),
            "autodiff": a_res.get("autodiff"),
            "coordinate_contract": coord_contract,
            "memory_hits": len(mem_hits),
            "red_team_findings": debate["red_team_findings"],
            "red_team_gate": debate["gate_passed"],
            "evidence_basis": "measured" if success else "asserted",
        }
        handoff_gate(self.bb, "VERIFICATION_REPORT", "CODE_MODEL", ["artifacts"],
                     verification, author="SwarmCommander",
                     basis=verification["evidence_basis"])
        trace.append({"stage": "VERIFICATION_REPORT", "agent": "SwarmCommander"})

        # ---- 落盘 Blackboard 快照 + Meta-SOP 文档（文档交接材料化）----
        bb_path = os.path.join(output_dir, "blackboard_snapshot.json")
        with open(bb_path, "w", encoding="utf-8") as f:
            json.dump(self.bb.snapshot(), f, ensure_ascii=False, indent=2, default=str)
        vr_path = os.path.join(output_dir, "VERIFICATION_REPORT.json")
        with open(vr_path, "w", encoding="utf-8") as f:
            json.dump(verification, f, ensure_ascii=False, indent=2, default=str)
        meta_sop_files = materialize_meta_sop(self.bb, output_dir)

        return {
            "success": success,
            "mode": "SWARM",
            "requested_mode": "SWARM",
            "trace": trace,
            "results": results,
            "verification_report": verification,
            "debate": debate,
            "blackboard_keys": self.bb.keys(),
            "meta_sop_docs": [meta_sop_key(s) for s in META_SOP_STAGES],
            "audit_log_len": len(self.bb.audit_log()),
            "elapsed_s": round(time.time() - t0, 3),
            "artifact_blackboard": bb_path,
            "artifact_verification_report": vr_path,
            "meta_sop_files": meta_sop_files,
        }


# ===========================================================================
# 轻量自检（python virtu_omni/agent/swarm_orchestrator.py）
# ===========================================================================
def _self_test() -> None:
    # 1) Blackboard 写锁租约：并发计数竞争必须串行化
    bb = Blackboard(lease_ttl_s=2.0)
    counter_key = "counter"
    bb._store[counter_key] = {"v": 0}
    bb._meta[counter_key] = {"writer": "init", "written_at": 0, "basis": "asserted"}

    def racer():
        for _ in range(50):
            lease = bb.acquire("racer", counter_key, timeout_s=5.0)
            try:
                cur = bb.read(counter_key)
                v = cur["v"] + 1
                time.sleep(0.0005)  # 放大竞态窗口
                bb.write(lease, counter_key, {"v": v}, basis="measured")
            finally:
                bb.release(lease)

    threads = [threading.Thread(target=racer) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert bb.read(counter_key)["v"] == 200, f"写锁失效：计数={bb.read(counter_key)['v']} 应为 200"
    print("[OK] Blackboard 写锁租约：4 线程 ×50 = 200 次写入完整串行化")

    # 2) 无租约写必须被拒
    try:
        bb.write(Lease("x", "ghost", counter_key, 0, 1), counter_key, {"v": -1})
        raise AssertionError("无租约写竟被允许")
    except LeaseError:
        print("[OK] 写锁门禁：无有效租约写入被拒 (LeaseError)")

    # 3) Meta-SOP 文档交接门：缺前置文档必须被拒
    bb2 = Blackboard()
    try:
        handoff_gate(bb2, "ARCHITECTURE", "PRD", ["workers"], {}, "x", "asserted")
        raise AssertionError("缺 PRD 前置文档竟被放行")
    except HandoffError:
        print("[OK] Meta-SOP 交接门：缺前置文档被拒 (HandoffError)")

    print("[SELFTEST_DONE]")


if __name__ == "__main__":
    _self_test()
