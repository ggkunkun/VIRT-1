# -*- coding: utf-8 -*-
"""Comprehensive falsifiable tests for cross-software coordinate isolation,
Hindsight/Working/Sleep/Custom memory integration, SWARM Blackboard contract,
WorkBuddy Bridge anchor injection, VERICUT-9.6 deployment probes, and SFT anti-regression anchors.

Enforces AGENTS.md Section 8 Measurement Constitution:
- Every test runs against isolated tmp_path stores (never mutating production hindsight_banks.json or sealed v1 datasets).
- Positive & negative (falsifiable) assertions for every evaluator and gate.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tarfile
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from swarm_test_support import swarm_workspace  # noqa: F401
from cloud_train_pack import deploy_trained_adapter as dta
from scripts import build_vericut96_cloud_datasets as bvcd
from scripts import workbuddy_virtu_bridge as bridge
from virtu_omni.agent import agent_team
from virtu_omni.agent.swarm_orchestrator import SwarmCommander
from virtu_omni.harness2.surface import DEFAULT_LONG_TERM_MEMORY
from virtu_omni.memory import hindsight_adapter
from virtu_omni.memory.hindsight_adapter import (
    CANONICAL_DOMAIN_INVARIANTS,
    VirtuHindsightMemory,
    build_swarm_coordinate_contract,
)
from virtu_omni.memory import sleep_framework
from virtu_omni.memory.sleep_framework import KnowledgeSeeder, WakeExperience


def _isolated_seeded_hindsight(tmp_path: Path, name: str = "hindsight.json") -> VirtuHindsightMemory:
    mem = VirtuHindsightMemory(storage_path=tmp_path / name)
    res = mem.seed_canonical_invariants()
    assert res["retained"] == len(CANONICAL_DOMAIN_INVARIANTS)
    return mem


def test_surface_default_long_term_memory_and_sleep_seeder(tmp_path: Path, monkeypatch):
    """Surface long-term memory and KnowledgeSeeder both encode isolated SW Y-up vs VERICUT/CNC Z-up + Lamé + G71."""
    assert "### 跨工业软件坐标系与理论公式隔离规范" in DEFAULT_LONG_TERM_MEMORY
    assert "SOLIDWORKS 2021" in DEFAULT_LONG_TERM_MEMORY
    assert "Front" in DEFAULT_LONG_TERM_MEMORY and "Top" in DEFAULT_LONG_TERM_MEMORY and "Right" in DEFAULT_LONG_TERM_MEMORY
    assert "VERICUT 9.6" in DEFAULT_LONG_TERM_MEMORY
    assert "Z-up" in DEFAULT_LONG_TERM_MEMORY and "Y-up" in DEFAULT_LONG_TERM_MEMORY
    assert "G71" in DEFAULT_LONG_TERM_MEMORY and "G70" in DEFAULT_LONG_TERM_MEMORY

    iso_mem = VirtuHindsightMemory(storage_path=tmp_path / "sleep_hs.json")
    monkeypatch.setattr(sleep_framework, "VirtuHindsightMemory", lambda *a, **kw: iso_mem)

    seeder = KnowledgeSeeder()
    exps = [
        WakeExperience(
            id="w1",
            prompt="SOLIDWORKS 2021 Front Plane / Top Plane 基准面法向校核",
            completion="ok",
            verified_facts={"cad": "solidworks_2021"},
        ),
        WakeExperience(
            id="w2",
            prompt="VERICUT 9.6 vcproject Auto-Diff 偏差分析",
            completion="ok",
            verified_facts={"unit": "inch"},
        ),
        WakeExperience(
            id="w3",
            prompt="FANUC G71 粗车 + G70 精车与 Lamé 厚壁圆筒校核",
            completion="ok",
            verified_facts={"Pi": 20.0, "Di": 60.0, "Do": 120.0},
        ),
    ]
    consolidated = seeder.consolidate(exps)
    keys = {c.rule_key: c for c in consolidated}
    assert {"sw_coordinate_y_up", "vericut_coordinate_z_up_autodiff", "fanuc_g71_turning_safety", "lame_thick_cylinder_fos"} <= set(keys)
    assert "Front=XY(+Z" in keys["sw_coordinate_y_up"].formula_or_invariant
    assert "Red=Gouge" in keys["vericut_coordinate_z_up_autodiff"].formula_or_invariant
    assert "G71 P_ Q_" in keys["fanuc_g71_turning_safety"].formula_or_invariant
    assert "k = (Do/Di)^2" in keys["lame_thick_cylinder_fos"].formula_or_invariant
    assert "sigma_t = Pi*(k+1)/(k-1)" in keys["lame_thick_cylinder_fos"].formula_or_invariant


def test_hindsight_invariants_read_only_recall_cross_bank_and_update(tmp_path: Path, monkeypatch):
    """Test canonical seeding idempotency, in-place update, read-only recall/reflect, and cross-bank retrieval."""
    monkeypatch.setenv("HINDSIGHT_API_URL", "")
    store = tmp_path / "hindsight.json"
    mem = VirtuHindsightMemory(storage_path=store)

    # Empty store starts clean before explicit seeding
    assert sum(len(b["units"]) for b in mem.banks.values()) == 0

    first = mem.seed_canonical_invariants()
    assert first["retained"] == len(CANONICAL_DOMAIN_INVARIANTS)
    assert first["updated"] == 0 and first["duplicate"] == 0

    second = mem.seed_canonical_invariants()
    assert second["retained"] == 0 and second["updated"] == 0
    assert second["duplicate"] == len(CANONICAL_DOMAIN_INVARIANTS)

    # Corrupt one canonical entry content in-memory -> seed_canonical_invariants updates it in-place without duplicating IDs
    first_id = first["ids"][0]
    first_bank = CANONICAL_DOMAIN_INVARIANTS[0]["bank_id"]
    mem.banks[first_bank]["units"][first_id]["content"] = "STALE_CORRUPTED_RULE"
    refreshed = mem.seed_canonical_invariants()
    assert refreshed["updated"] == 1
    assert refreshed["retained"] == 0
    assert mem.banks[first_bank]["units"][first_id]["content"] == CANONICAL_DOMAIN_INVARIANTS[0]["content"]

    before_bytes = store.read_bytes()
    before_counts = {
        uid: u["access_count"]
        for b in mem.banks.values()
        for uid, u in b["units"].items()
    }

    single = mem.recall("virtu_cad_cam", "SOLIDWORKS Front Top Right", update_stats=False)
    assert single and single[0].get("id")
    cross = mem.recall_all_banks("SOLIDWORKS Front VERICUT Auto-Diff G71 Lamé", max_results=6, update_stats=False)
    assert len({r.get("bank_id") for r in cross}) >= 2
    ref = mem.reflect("virtu_quality_audit", "Lamé 厚壁圆筒应力", update_stats=False)
    assert ref["status"] == "reflected"

    # Read-only guarantee: no file rewrite and zero access_count mutation
    after_counts = {
        uid: u["access_count"]
        for b in mem.banks.values()
        for uid, u in b["units"].items()
    }
    assert after_counts == before_counts
    assert store.read_bytes() == before_bytes

    matched_sw = VirtuHindsightMemory.select_coordinate_invariants("SOLIDWORKS Front 基准面")
    assert any(key == "solidworks" and "SOLIDWORKS" in txt for key, txt in matched_sw)
    unmatched = VirtuHindsightMemory.select_coordinate_invariants("无关寒暄", include_all_if_empty=False)
    assert unmatched == []
    fallback_all = VirtuHindsightMemory.select_coordinate_invariants("无关寒暄", include_all_if_empty=True)
    assert len(fallback_all) >= 2

    ctx = mem.build_domain_memory_context(
        "VERICUT Auto-Diff unit inch vs SOLIDWORKS Front Plane",
        working_memory_block="## WORKING_FACTS\n- unit=inch",
        max_chars=1600,
    )
    assert len(ctx) <= 1600
    assert "[跨软件坐标系与工程规范锚点]" in ctx
    assert "WORKING_FACTS" in ctx


def test_evolution_and_memory_agent_read_only_and_shared_instance(tmp_path: Path, monkeypatch):
    """EvolutionAndMemoryAgent supports injected VirtuHindsightMemory and cross-bank read-only recall."""
    monkeypatch.setenv("HINDSIGHT_API_URL", "")
    mem = _isolated_seeded_hindsight(tmp_path, "evo_hs.json")
    before_counts = {uid: u["access_count"] for b in mem.banks.values() for uid, u in b["units"].items()}

    evo = agent_team.EvolutionAndMemoryAgent(hindsight_memory=mem)
    assert evo.hindsight is mem

    ctx = evo.retrieve_context("VERICUT Auto-Diff Red Gouge SOLIDWORKS Front Top Right", update_stats=False)
    assert isinstance(ctx, list) and len(ctx) >= 1
    assert "bank_id" in ctx[0]

    ref = evo.reflect_on_intent("VERICUT G54 Z-up vs SOLIDWORKS Y-up", update_stats=False)
    assert ref["status"] == "reflected"
    assert "coordinate_invariants" in ref

    after_counts = {uid: u["access_count"] for b in mem.banks.values() for uid, u in b["units"].items()}
    assert after_counts == before_counts


def test_super_agent_memory_unification_and_runtime_wiring(tmp_path: Path, monkeypatch):
    """VirtuSuperAgent shares one Hindsight instance, injects runtime context & custom_memory into DeepReAct/Autonomous, and wakes Sleep."""
    monkeypatch.setenv("HINDSIGHT_API_URL", "")
    monkeypatch.setenv("VIRTU_WORKING_MEMORY_PATH", str(tmp_path / "working_memory.json"))
    iso_mem = _isolated_seeded_hindsight(tmp_path, "sa_hs.json")

    monkeypatch.setattr(hindsight_adapter, "VirtuHindsightMemory", lambda *a, **kw: iso_mem)
    monkeypatch.setattr(agent_team, "VirtuHindsightMemory", lambda *a, **kw: iso_mem)
    from virtu_omni.agent import super_agent as sa_mod
    monkeypatch.setattr(sa_mod, "VirtuHindsightMemory", lambda *a, **kw: iso_mem)

    agent = sa_mod.VirtuSuperAgent()
    agent.custom_memory = "CUSTOM_MEMORY_SENTINEL: STRICT_INCH_PRESERVATION"
    agent.custom_guardrails = "CUSTOM_GUARDRAIL_SENTINEL: DO_NOT_MIX_Y_UP_AND_Z_UP"
    assert agent.hindsight_memory is agent._delegate_memory.hindsight

    ctx = agent.build_runtime_memory_context("VERICUT 9.6 Auto-Diff SOLIDWORKS Front Plane")
    assert "CUSTOM_MEMORY_SENTINEL" in ctx
    assert "CUSTOM_GUARDRAIL_SENTINEL" in ctx
    assert "[跨软件坐标系与工程规范锚点]" in ctx

    from bridges import deep_agent as deep_mod
    captured = {}

    def fake_deep_run(task="", model=None, tool_adapter=None, env_facts="", config=None, run_ctx=None, **kw):
        captured["task"] = task
        captured["env_facts"] = env_facts
        return {
            "success": True,
            "plan": {"steps": [{"step": 1, "goal": "check coords"}]},
            "history": [{"step": 1, "tool": "facet_recall_memory", "args": {}, "observation": "VERIFIED"}],
            "digests": {1: {"goal": "check coords", "obs_head": "VERIFIED", "verdict": "ok"}},
            "verify": {"items": [{"met": "yes"}]},
            "criteria_total": 1,
            "criteria_met": 1,
            "guards": [],
            "metrics": {},
        }

    monkeypatch.setattr(deep_mod, "run", fake_deep_run)
    res = agent._solve_react_deep("检查 VERICUT 9.6 Z-up 与 SOLIDWORKS Front 基准面隔离")
    assert res.success is True
    assert res.metrics.get("memory_context_injected") is True
    assert "CUSTOM_MEMORY_SENTINEL" in captured["env_facts"]
    assert "CUSTOM_GUARDRAIL_SENTINEL" in captured["env_facts"]
    assert "[跨软件坐标系与工程规范锚点]" in captured["env_facts"]
    assert "CUSTOM_MEMORY_SENTINEL" in res.artifacts.get("runtime_memory_context", "")
    assert len(agent.sleep_framework.wake_buffer) >= 1
    recalled = agent.facet_recall_memory("VERICUT 9.6 Auto-Diff vs SOLIDWORKS Front Plane")
    assert "solidworks" in recalled["coordinate_invariants"]
    assert "vericut_cnc" in recalled["coordinate_invariants"]


def test_swarm_commander_blackboard_coordinate_contract_and_memory(swarm_workspace, tmp_path: Path, monkeypatch):
    """SwarmCommander writes coordinate_contract and read-only Hindsight memory_context onto Blackboard under leases."""
    monkeypatch.setenv("HINDSIGHT_API_URL", "")
    iso_mem = _isolated_seeded_hindsight(tmp_path, "swarm_hs.json")
    from virtu_omni.agent import swarm_orchestrator as so_mod
    monkeypatch.setattr(so_mod, "VirtuHindsightMemory", lambda *a, **kw: iso_mem)

    before_counts = {uid: u["access_count"] for b in iso_mem.banks.values() for uid, u in b["units"].items()}
    task = {
        "design_stl": str(swarm_workspace.design_stl),
        "spindle_axis": "Z",
        "part_type": "铝合金闭式叶轮",
        "material": "AL6061-T6",
        "surface_finish": "Ra1.6",
        "tolerance": "IT8",
        "tool_radius_mm": 3.0,
        "allowance_mm": 0.01,
    }
    out = str(swarm_workspace.root / "runs" / "swarm" / "test_coord_contract")
    res = SwarmCommander().solve(task, output_dir=out)
    assert res["success"] is True

    snap = json.loads(Path(res["artifact_blackboard"]).read_text(encoding="utf-8"))
    assert "coordinate_contract" in snap
    cc = snap["coordinate_contract"]["value"]
    assert cc["cad_modeling_system"] == "SOLIDWORKS_2021_Y_UP"
    assert cc["cam_simulation_system"] == "VERICUT_9.6_NX_12_CNC_Z_UP"
    assert cc["cad_plane_normals"]["Front"]["label"] == "+Z"
    assert "memory_context" in snap
    mc = snap["memory_context"]["value"]
    assert mc.get("read_only") is True
    assert mc.get("summary") and "[跨软件坐标系与工程规范锚点]" in mc["summary"]
    assert isinstance(mc.get("hits"), list) and len(mc["hits"]) >= 1

    after_counts = {uid: u["access_count"] for b in iso_mem.banks.values() for uid, u in b["units"].items()}
    assert after_counts == before_counts

    # Direct helper check
    c2 = build_swarm_coordinate_contract({"unit": "inch", "spindle_axis": "Z"})
    assert c2["cad_modeling_system"] == "SOLIDWORKS_2021_Y_UP"
    assert c2["cam_simulation_system"] == "VERICUT_9.6_NX_12_CNC_Z_UP"
    assert "unit" in c2["unit_policy"].lower() and "inch" in c2["unit_policy"].lower()


def test_workbuddy_bridge_injects_hindsight_anchor_read_only(tmp_path: Path, monkeypatch):
    """WorkBuddy bridge injects <HINDSIGHT_MEMORY_ANCHOR> cleanly without duplicating or mutating DB stats."""
    monkeypatch.setenv("HINDSIGHT_API_URL", "")
    store = tmp_path / "bridge_hs.json"
    mem = _isolated_seeded_hindsight(tmp_path, "bridge_hs.json")
    monkeypatch.setattr(bridge, "hindsight_memory", mem)

    before_bytes = store.read_bytes()
    before_counts = {uid: u["access_count"] for b in mem.banks.values() for uid, u in b["units"].items()}

    conv = [
        {"role": "system", "content": "BASE_SYSTEM_PROMPT"},
        {"role": "user", "content": "请说明 SOLIDWORKS Front/Top/Right 基准面和 VERICUT Z-up 隔离规则"},
    ]
    injected = bridge._inject_hindsight_anchor(conv, conv[1]["content"])
    assert len(injected) == 2
    assert injected[0]["role"] == "system"
    assert "BASE_SYSTEM_PROMPT" in injected[0]["content"]
    assert "<HINDSIGHT_MEMORY_ANCHOR>" in injected[0]["content"]

    # Idempotent if already anchored
    twice = bridge._inject_hindsight_anchor(injected, conv[1]["content"])
    assert twice[0]["content"].count("<HINDSIGHT_MEMORY_ANCHOR>") == 1

    # Inserts system message if none present
    no_sys = [{"role": "user", "content": "编写 FANUC G71 粗车程序"}]
    with_sys = bridge._inject_hindsight_anchor(no_sys, no_sys[0]["content"])
    assert with_sys[0]["role"] == "system" and "<HINDSIGHT_MEMORY_ANCHOR>" in with_sys[0]["content"]

    after_counts = {uid: u["access_count"] for b in mem.banks.values() for uid, u in b["units"].items()}
    assert after_counts == before_counts
    assert store.read_bytes() == before_bytes


def test_deploy_trained_adapter_vericut_probes_and_dual_track(tmp_path: Path, monkeypatch):
    """Falsifiable tests for VERICUT-9.6 probes, profile routing, and honest dual-track raw vs memory reporting."""
    assert dta._resolve_probe_profile("virtu-vericut96:v1", "auto") == "vericut96"
    assert dta._resolve_probe_profile("virtu-master-fixed:latest", "auto") == "general"
    assert dta._resolve_probe_profile("virtu-vericut96:v1", "all") == "all"

    # Auto-Diff positive (including intro + markdown headers + trailing red remediation section) & swapped negative
    good_ad = "VERICUT Auto-Diff 偏差图：红色代表过切(gouge)，需立即停机修正刀路；蓝色代表残料(excess)；绿色代表合格(in-tolerance)。"
    good_ad_md = (
        "在 Auto-Diff 中红色、蓝色、绿色含义如下：\n"
        "### **红色 (Red)**：表示过切 (gouge)。\n"
        "### **蓝色 (Blue)**：表示残料 (excess)。\n"
        "### **绿色 (Green)**：表示合格 (in-tolerance)。\n"
        "发现红色时应立即停机修正刀路。"
    )
    good_ad_table = (
        "| 颜色 | 含义 |\n"
        "| " + "-" * 180 + " | " + "-" * 40 + " |\n"
        "| **红色 (Red)** | 过切 (Gouge)，立即停机修正刀路 |\n"
        "| **蓝色 (Blue)** | 残料 (Excess) |\n"
        "| **绿色 (Green)** | 合格 (In-Tolerance) |\n"
    )
    bad_ad = "红色代表合格，蓝色代表过切，绿色代表残料。"
    assert dta.evaluate_vericut_autodiff_probe(good_ad)["passed"] is True
    assert dta.evaluate_vericut_autodiff_probe(good_ad_md)["passed"] is True
    import time as _time
    _t0 = _time.perf_counter()
    assert dta.evaluate_vericut_autodiff_probe(good_ad_table)["passed"] is True
    assert (_time.perf_counter() - _t0) < 0.25
    assert dta.evaluate_vericut_autodiff_probe(bad_ad)["passed"] is False

    # Unit & coordinate isolation positive (with negated phrase) & negative
    good_cu = "该 VERICUT 工程单位是 inch（而非使用毫米），主轴 Z-up (G54)，不可直接等价套用 SOLIDWORKS 2021 的 Y-up Front/Top/Right 基准面。"
    bad_cu = "单位为millimeter，两者坐标系一致，可直接等价套用。"
    assert dta.evaluate_vericut_coordinate_unit_probe(good_cu)["passed"] is True
    assert dta.evaluate_vericut_coordinate_unit_probe(bad_cu)["passed"] is False

    # Honest dual-track: raw fails while memory_augmented passes -> raw_all_passed stays False
    iso_mem = _isolated_seeded_hindsight(tmp_path, "dual_hs.json")
    monkeypatch.setattr(hindsight_adapter, "VirtuHindsightMemory", lambda *a, **kw: iso_mem)
    monkeypatch.setattr(
        dta.subprocess,
        "run",
        lambda *a, **kw: types.SimpleNamespace(stdout="TEMPLATE {{ .Tools }} <tool_call>", returncode=0),
    )

    def fake_probe_chat(tag, messages, num_predict=256, keep_alive="180s", tools=None, think=False):
        if tools:
            return {
                "message": {
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "cadcam_vericut_simulate",
                                "arguments": {"project_path": "demo.vcproject", "action": "run"},
                            }
                        }
                    ],
                }
            }
        sys_txt = messages[0]["content"] if messages and messages[0]["role"] == "system" else ""
        has_mem = "[跨软件坐标系与工程规范锚点]" in sys_txt
        user_txt = messages[-1]["content"]
        if "Auto-Diff" in user_txt:
            txt = good_ad
        elif "<Unit>inch</Unit>" in user_txt:
            # Fail raw intentionally to prove raw failure is never masked by memory
            txt = good_cu if has_mem else bad_cu
        elif "SOLIDWORKS 2021" in user_txt:
            txt = (
                "SOLIDWORKS 2021 是 Y-up 坐标系：Front=XY (+Z), Top=XZ (+Y), Right=YZ (+X)。"
                "注意各默认基准面严格区分。"
            )
        else:
            txt = "σ_θ = 33.33 MPa, σ_r = -20.00 MPa (Lamé 厚壁圆筒)。"
        return {"message": {"content": txt}}

    monkeypatch.setattr(dta, "_probe_chat", fake_probe_chat)
    dual = dta.verify_deployed_model_with_memory("virtu-vericut96:v1", probe_profile="vericut96")
    assert dual["probe_profile"] == "vericut96"
    assert dual["raw_all_passed"] is False
    assert dual["raw_probes"]["vericut_coordinate_unit_probe"]["passed"] is False
    assert dual["memory_augmented_all_passed"] is True
    assert dual["memory_augmented_probes"]["vericut_coordinate_unit_probe"]["passed"] is True
    assert dual["basis"] == "measured_dual_track"


def test_build_vericut96_cloud_datasets_anti_regression_anchors(tmp_path: Path):
    """Future dataset builder injects clean anti-regression anchors within <=702B system budget without touching sealed v1."""
    anchors = bvcd.build_canonical_anti_regression_rows(seed=7, limit=12)
    assert len(anchors) >= 4
    for row in anchors:
        sys_msg = row["messages"][0]
        assert sys_msg["role"] == "system"
        assert len(sys_msg["content"].encode("utf-8")) <= 702
        assert row["meta"]["source"] == "canonical_anchor"
        # Check leak + unit clean directly on an isolated tmp jsonl
    out_sft = tmp_path / "anchors_only.jsonl"
    with open(out_sft, "w", encoding="utf-8") as f:
        for r in anchors:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    bvcd.assert_no_leak(str(out_sft))
    bvcd.assert_units_clean(str(out_sft))
    assert bvcd.run_selftest() == 0


def test_hindsight_purge_sleep_noise_and_seeder_guard(tmp_path: Path, monkeypatch):
    """Sleep telemetry/DYNAMIC_GAP noise is blocked at consolidation time and purged cleanly from Hindsight."""
    noisy_store = tmp_path / "noisy_hs.json"
    mem = _isolated_seeded_hindsight(tmp_path, "noisy_hs.json")
    monkeypatch.setenv("VIRTU_HINDSIGHT_PATH", str(noisy_store))

    mem.retain(
        bank_id="default",
        content='【Sleep固化心智模型-task_verified_facts】{"facets_engaged": ["parse_intent"], "gap": "DYNAMIC_GAP"}',
        tags=["engineering_invariants", "task_verified_facts"],
    )
    mem.retain(
        bank_id="virtu_quality_audit",
        content='【Sleep固化心智模型-lame_thick_cylinder_fos】sigma_vm >= 1.5；工程参数：{"facets_engaged": ["verify_cae_stress"]}',
        tags=["cae_simulation", "lame_thick_cylinder_fos"],
    )
    mem.retain(
        bank_id="virtu_cnc_machining",
        content="FANUC 精车外圆程序应保证 G71 后跟随 G70 P_ Q_。",
        tags=["cnc_machining"],
    )
    assert any(mem.is_sleep_debug_noise(u) for b in mem.banks.values() for u in b["units"].values())

    removed = mem.purge_sleep_debug_noise()
    assert removed == 2
    assert sum(1 for b in mem.banks.values() for u in b["units"].values() if mem.is_sleep_debug_noise(u)) == 0
    assert any("canonical_invariant" in (u.get("tags") or []) for b in mem.banks.values() for u in b["units"].values())
    assert any("FANUC 精车外圆程序" in u.get("content", "") for u in mem.banks["virtu_cnc_machining"]["units"].values())

    # KnowledgeSeeder must refuse to emit/sync DYNAMIC_GAP or facets_engaged noise
    seeder = KnowledgeSeeder()
    bad_exp = WakeExperience(
        id="WAKE_NOISY_1",
        prompt="故障与知识补齐: 缺少未知切削刀具参数_DYNAMIC_GAP",
        completion="ok",
        verified_facts={"facets_engaged": ["parse_intent"], "architecture": "已完成需求解析"},
    )
    assert seeder.consolidate([bad_exp]) == []

    # Production hindsight store stays clean of Sleep debug noise and retains canonical invariants
    real_hs = ROOT / "data" / "memory" / "hindsight_banks.json"
    if real_hs.exists():
        real_raw = json.loads(real_hs.read_text(encoding="utf-8"))
        real_units = [u for b in real_raw.get("banks", {}).values() for u in b.get("units", {}).values()]
        assert not any(VirtuHindsightMemory.is_sleep_debug_noise(u) for u in real_units)
        assert sum(1 for u in real_units if "canonical_invariant" in (u.get("tags") or [])) >= 4


def test_build_vericut96_v2_dpo_anchors_and_bundle(tmp_path: Path):
    """v2 anti-regression DPO pairs + v2 dataset artifacts + tarball validate without touching sealed v1."""
    from cloud_train_pack import start_train_now
    from scripts import train_dpo_all90

    dpo_anchors = bvcd.build_canonical_anti_regression_dpo_rows(seed=7, limit=24)
    assert len(dpo_anchors) == 24
    families = {r["family"] for r in dpo_anchors}
    assert {"autodiff_triage", "coordinate_isolation", "unit_preservation", "lame_closed_form", "fanuc_g71_safety"} <= families

    tmp_dpo = tmp_path / "v2_anchors_dpo.jsonl"
    with open(tmp_dpo, "w", encoding="utf-8") as f:
        for r in dpo_anchors:
            assert r["chosen"] != r["rejected"]
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    assert len(train_dpo_all90.validate_dpo_pairs(tmp_dpo)) == 24
    bvcd.assert_no_leak(str(tmp_dpo))
    bvcd.assert_units_clean(str(tmp_dpo))

    # Falsifiable: SFT autodiff multi-color anchor must pass probe while swapped rejected fails
    sft_anchors = bvcd.build_canonical_anti_regression_rows(seed=7, limit=24)
    ad_sft = next(
        r["messages"][-1]["content"]
        for r in sft_anchors
        if (r.get("meta") or {}).get("family") == "autodiff_triage"
        and "Auto-Diff 颜色定义" in r["messages"][-1]["content"]
    )
    ad_dpo_rej = next(
        r["rejected"]
        for r in dpo_anchors
        if r.get("family") == "autodiff_triage" and "红色" in r.get("rejected", "")
    )
    assert dta.evaluate_vericut_autodiff_probe(ad_sft)["passed"] is True
    assert dta.evaluate_vericut_autodiff_probe(
        "红色代表过切(gouge)，需立即停机修刀路；蓝色代表残料(非过切)；绿色代表公差内合格。"
    )["passed"] is True
    assert dta.evaluate_vericut_autodiff_probe(ad_dpo_rej)["passed"] is False

    # Sealed v1 & v2 artifacts both exist and satisfy ledgers cleanly
    for label, ddir, prefix in (
        ("v1", ROOT / "cloud_train_pack" / "dataset", "vericut96"),
        ("v2", ROOT / "cloud_train_pack" / "dataset_v2", "vericut96_v2"),
    ):
        for kind in ("sft", "dpo"):
            jpath = ddir / f"{prefix}_{kind}_mix.jsonl"
            lpath = ddir / f"{prefix}_{kind}_mix_ledger.json"
            assert jpath.exists() and lpath.exists(), f"Missing {label} {kind}"
            ledger = json.loads(lpath.read_text(encoding="utf-8"))
            assert hashlib.sha256(jpath.read_bytes()).hexdigest() == ledger["output_sha256"]

    cfg_v2 = start_train_now.TRACKS["vericut96-v2"]
    assert cfg_v2["receipt_rel"] == "output/virtu_vericut96_v2/training_receipt.json"
    bundle_v2 = Path(cfg_v2["bundle_path"])
    assert bundle_v2.exists() and Path(str(bundle_v2) + ".sha256").exists()
    ok, detail = start_train_now._verify_local_archive_sha(str(bundle_v2))
    assert ok, detail

    with tarfile.open(bundle_v2, "r:gz") as tar:
        names = set(tar.getnames())
        for req in (
            "run_vericut96.sh",
            "start_cloud_train_now.sh",
            "onboot_cloud_train.sh",
            "train_turnkey.py",
            "dataset_v2/vericut96_v2_sft_mix.jsonl",
            "dataset_v2/vericut96_v2_sft_mix_ledger.json",
            "dataset_v2/vericut96_v2_dpo_mix.jsonl",
            "dataset_v2/vericut96_v2_dpo_mix_ledger.json",
        ):
            assert req in names, f"Missing {req} in v2 bundle"
        for m in tar.getmembers():
            if m.name.endswith(".sh"):
                assert (m.mode & 0o111) != 0
                raw_sh = tar.extractfile(m).read()
                assert b"\r\n" not in raw_sh
                if m.name == "run_vericut96.sh":
                    assert b"dataset_v2/vericut96_v2_sft_mix.jsonl" in raw_sh
                else:
                    assert b"vericut96-v2" in raw_sh


def test_build_vericut96_v3_dpo_repair_no_leak_and_falsifiable(tmp_path: Path):
    """v3 DPO repair builder must produce probe-passing chosen / failing rejected pairs with 0 leaks."""
    repair_rows = bvcd.build_vericut96_v3_dpo_repair_rows(seed=20261115, repeat=1)
    families = {r["family"] for r in repair_rows}
    assert families == {
        "autodiff_triage_repair",
        "coordinate_unit_isolation_repair",
        "lame_closed_form_repair",
        "sw_plane_notation_repair",
    }

    for row in repair_rows:
        fam = row["family"]
        chosen = row["chosen"]
        rejected = row["rejected"]
        user_txt = row["prompt"][-1]["content"]
        assert "Di=60" not in user_txt and "33.33" not in chosen

        if fam == "autodiff_triage_repair":
            assert dta.evaluate_vericut_autodiff_probe(chosen)["passed"] is True
            assert dta.evaluate_vericut_autodiff_probe(rejected)["passed"] is False
        elif fam == "coordinate_unit_isolation_repair":
            assert dta.evaluate_vericut_coordinate_unit_probe(chosen)["passed"] is True
            assert dta.evaluate_vericut_coordinate_unit_probe(rejected)["passed"] is False
        elif fam == "sw_plane_notation_repair":
            assert dta.evaluate_sw_coordinate_probe(chosen)["passed"] is True
            assert dta.evaluate_sw_coordinate_probe(rejected)["passed"] is False
        elif fam == "lame_closed_form_repair":
            assert "无量纲" in chosen
            assert "σ_r = -" in chosen
            assert "(k^2 + 1)" not in chosen
            assert "MPa" in rejected

    out_jsonl = tmp_path / "vericut96_v3_dpo_repair.jsonl"
    info = bvcd.build_vericut96_v3_dpo_repair_dataset(out_path=out_jsonl, repair_repeat=2, seed=20261115)
    assert out_jsonl.exists()
    assert Path(str(out_jsonl) + ".sha256").exists()
    ledger = json.loads(Path(info["ledger_path"]).read_text(encoding="utf-8"))
    assert ledger["output_sha256"] == info["sha256"]
    assert info["rows"] == ledger["base_dpo_rows"] + ledger["repair_rows"]

    disk_v3 = ROOT / "cloud_train_pack" / "dataset_v2" / "vericut96_v3_dpo_repair_ledger.json"
    if disk_v3.exists():
        disk_ledger = json.loads(disk_v3.read_text(encoding="utf-8"))
        disk_jsonl = Path(disk_ledger["output_path"])
        if disk_jsonl.exists():
            actual_sha = hashlib.sha256(disk_jsonl.read_bytes()).hexdigest()
            assert actual_sha == disk_ledger["output_sha256"]


