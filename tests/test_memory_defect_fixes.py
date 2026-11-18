# -*- coding: utf-8 -*-
"""记忆模块缺陷 D1–D5 + 存储防覆写的反证测试（AGENTS.md §8.4：植入坏样本必须红）。

每个 test_planted_* 在修复前必须失败（证明判据能抓到缺陷），修复后转绿；
每个 test_guard_* 防止修复过度收窄（正常路径不得回归）。
"""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from virtu_omni.memory.working_memory import (
    BuiltinWorkingMemory,
    LongTaskHallucinationSentinel,
)
from virtu_omni.memory.hindsight_adapter import VirtuHindsightMemory
from virtu_omni.memory.remory_adapter import (
    Checkpoint,
    MemoryStore,
    TextClient,
    digest,
)


# ---------------------------------------------------------------------------
# D1: 错误/受阻工具回执不得把里程碑标成 COMPLETED，也不得入事实账本
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("bad_status", ["error", "blocked", "failed", "timeout"])
def test_planted_failed_receipt_must_not_complete_milestone(bad_status):
    wm = BuiltinWorkingMemory(session_id="d1")
    wm.set_task_goal("法兰加工", invariants={"outer_diameter": 60.0})
    wm.add_milestone("参数化建模")
    wm.auto_sync_from_messages([
        {"role": "user", "content": "法兰加工"},
        {"role": "tool", "name": "cadcam_solidworks_model",
         "content": json.dumps({"status": bad_status, "message": "COM connection failed",
                                 "volume_mm3": 999.0, "safety_factor": 9.9})},
    ])
    ms = wm.milestones[0]
    assert ms.status.value != "COMPLETED", f"status={bad_status} 的回执不得记为完成"
    assert ms.receipt is None
    assert wm.get_fact("rebuild_volume_mm3") is None, "失败回执的数值不得入事实账本"
    assert wm.get_fact("safety_factor") is None


def test_planted_success_false_receipt_must_not_complete_milestone():
    wm = BuiltinWorkingMemory(session_id="d1b")
    wm.add_milestone("有限元仿真")
    wm.auto_sync_from_messages([
        {"role": "tool", "name": "cadcam_cae_stress_analysis",
         "content": json.dumps({"success": False, "safety_factor": 0.2})},
    ])
    assert wm.milestones[0].status.value != "COMPLETED"
    assert wm.get_fact("safety_factor") is None


def test_guard_success_receipt_still_completes_milestone():
    wm = BuiltinWorkingMemory(session_id="d1g")
    wm.add_milestone("参数化建模")
    wm.auto_sync_from_messages([
        {"role": "tool", "name": "cadcam_solidworks_model",
         "content": json.dumps({"status": "executed", "volume_mm3": 15420.0})},
    ])
    assert wm.milestones[0].status.value == "COMPLETED"
    assert wm.get_fact("rebuild_volume_mm3") == 15420.0


def test_guard_receipt_without_status_still_completes():
    wm = BuiltinWorkingMemory(session_id="d1g2")
    wm.add_milestone("图纸导出")
    wm.auto_sync_from_messages([
        {"role": "tool", "name": "cadcam_dxf_export",
         "content": json.dumps({"output_file": "part.dxf"})},
    ])
    assert wm.milestones[0].status.value == "COMPLETED"


# ---------------------------------------------------------------------------
# D2: 单字符/拉丁别名不得在单词内部误报；修复不得改写无关文本；
#     真实矛盾仍必须被抓到；整数/小数两种写法都要能修复
# ---------------------------------------------------------------------------
def test_planted_single_char_alias_false_positive():
    wm = BuiltinWorkingMemory(session_id="d2")
    wm.record_fact("spindle_speed", 1200.0, verified=True)
    sent = LongTaskHallucinationSentinel(wm)
    assert sent.check_fact_contradictions("modeling depth 50 mm") == []


def test_planted_latin_alias_substring_false_positive():
    wm = BuiltinWorkingMemory(session_id="d2b")
    wm.record_fact("fillet_radius", 3.0, verified=True)
    sent = LongTaskHallucinationSentinel(wm)
    # "Turning" 内含字母 r，不得当成圆角 R 别名
    assert sent.check_fact_contradictions("Turning operation 50") == []


def test_planted_repair_corrupts_unrelated_text():
    wm = BuiltinWorkingMemory(session_id="d2c")
    wm.record_fact("spindle_speed", 1200.0, verified=True)
    sent = LongTaskHallucinationSentinel(wm)
    text = "modeling depth 50 mm"
    ok, repaired, _ = sent.audit_and_repair(text, auto_repair=True)
    assert ok is True
    assert repaired == text, "无矛盾时 auto_repair 不得改写原文"


def test_planted_repair_integer_form():
    wm = BuiltinWorkingMemory(session_id="d2d")
    wm.set_task_goal("法兰加工", invariants={"outer_diameter": 60.0})
    sent = LongTaskHallucinationSentinel(wm)
    ok, repaired, _ = sent.audit_and_repair("当前外径为 50mm，继续。", auto_repair=True)
    assert ok is False
    assert "外径为 60mm" in repaired, "整数写法 50 必须能被修复为 60"


def test_guard_real_contradiction_still_detected():
    wm = BuiltinWorkingMemory(session_id="d2g")
    wm.record_fact("spindle_speed", 1200.0, verified=True)
    sent = LongTaskHallucinationSentinel(wm)
    hits = sent.check_fact_contradictions("主轴转速 500 r/min")
    assert len(hits) == 1
    assert hits[0]["hallucinated_value"] == 500.0


def test_guard_cjk_alias_and_decimal_repair_contract():
    wm = BuiltinWorkingMemory(session_id="d2g2")
    wm.set_task_goal("法兰加工", invariants={"outer_diameter": 60.0})
    sent = LongTaskHallucinationSentinel(wm)
    ok, repaired, _ = sent.audit_and_repair("当前步骤中零件外径为 50.0mm，开始下一步操作。",
                                            auto_repair=True)
    assert ok is False
    assert "外径为 60.0mm" in repaired, "小数位数必须保留（既有契约）"


def test_guard_cross_parameter_number_not_stolen():
    wm = BuiltinWorkingMemory(session_id="d2g3")
    wm.set_task_goal("法兰加工", invariants={"outer_diameter": 60.0})
    sent = LongTaskHallucinationSentinel(wm)
    # 外径合格，后面的 50 是内孔参数，不得被外径别名隔空抓走
    assert sent.check_fact_contradictions("外径合格，内孔 50 mm") == []


# ---------------------------------------------------------------------------
# D3: Remory 残差预算满后，新事实必须仍能入库（new-first）
# ---------------------------------------------------------------------------
def _compact_round(client, prefix, cp, text, summary):
    res = client.compact(prefix_messages=prefix,
                         removed_messages=[{"role": "user", "content": text}],
                         summary=summary, previous=cp)
    new_cp = Checkpoint(res["handle"], res["summary"], digest(prefix))
    return new_cp, client.store.load(new_cp.handle, client.session_id)["residual"]


def test_planted_remory_residual_drops_new_facts_when_full():
    import tempfile
    store = MemoryStore(os.path.join(tempfile.mkdtemp(), "m.sqlite"))
    client = TextClient(store, session_id="d3", residual_budget=4)
    prefix = [{"role": "system", "content": "sys"}]
    cp = None
    for i in range(3):
        cp, residual = _compact_round(client, prefix, cp,
                                      f"round{i} 外径 = {60 + i} mm 决定 采用", f"s{i}")
    assert any("62" in line for line in residual), "预算满后第 3 轮新事实被永久丢弃"
    assert len(residual) <= 4
    assert len(set(residual)) == len(residual)


def test_guard_remory_residual_keeps_task_anchor_priority():
    import tempfile
    store = MemoryStore(os.path.join(tempfile.mkdtemp(), "m2.sqlite"))
    client = TextClient(store, session_id="d3g", residual_budget=24)
    prefix = [{"role": "system", "content": "sys"}]
    cp, residual = _compact_round(client, prefix, None,
                                  "外径 = 60 mm 决定 采用", "s0")
    assert any("60" in line for line in residual)
    assert any(line.startswith("[task]") for line in residual)


# ---------------------------------------------------------------------------
# D4: prune/compact 不得淘汰 canonical 安全不变量
# ---------------------------------------------------------------------------
def _mem_with_canonical(tmp_path, name):
    m = VirtuHindsightMemory(storage_path=str(tmp_path / name))
    m.seed_canonical_invariants()
    return m


def _canonical_count(m):
    return sum(
        1 for b in m.banks.values() for u in b.get("units", {}).values()
        if "canonical_invariant" in (u.get("tags") or [])
    )


def test_planted_prune_evicts_canonical_invariants(tmp_path):
    m = _mem_with_canonical(tmp_path, "prune_canon.json")
    before = _canonical_count(m)
    assert before >= 4
    for i in range(12):
        m.retain("virtu_cnc_machining", f"noise experience {i} about cutting")
    for _ in range(3):
        m.recall("virtu_cnc_machining", "noise experience cutting", max_results=12)
    m.prune(max_units=2, bank_id="virtu_cnc_machining")
    assert _canonical_count(m) == before, "容量压力不得淘汰 canonical 安全不变量"


def test_planted_global_prune_evicts_canonical(tmp_path):
    m = _mem_with_canonical(tmp_path, "prune_global.json")
    before = _canonical_count(m)
    for i in range(10):
        m.retain("default", f"global noise row {i}")
    m.prune(max_units=2)
    assert _canonical_count(m) == before


def test_planted_compact_evicts_expired_canonical(tmp_path):
    m = _mem_with_canonical(tmp_path, "compact_canon.json")
    before = _canonical_count(m)
    # 植入过期 canonical：compact 也不得淘汰安全不变量
    for b in m.banks.values():
        for u in b.get("units", {}).values():
            if "canonical_invariant" in (u.get("tags") or []):
                u["expires_at"] = 1.0
    m.compact()
    assert _canonical_count(m) == before


def test_guard_prune_still_evicts_noise(tmp_path):
    m = VirtuHindsightMemory(storage_path=str(tmp_path / "prune_noise.json"))
    for i in range(8):
        m.retain("bank", f"distinct row {i} gamma")
    removed = m.prune(max_units=3, bank_id="bank")
    assert removed == 5
    assert len(m.banks["bank"]["units"]) == 3


# ---------------------------------------------------------------------------
# D5: 中英混排实体边界（CJK 相邻可识别，拉丁子串不误识别）
# ---------------------------------------------------------------------------
def test_planted_entity_missed_in_cjk_context(tmp_path):
    m = VirtuHindsightMemory(storage_path=str(tmp_path / "ent.json"))
    assert "SOLIDWORKS" in m._extract_entities("用SOLIDWORKS建模")
    assert "FANUC" in m._extract_entities("基于FANUC系统的后处理")


def test_guard_entity_no_latin_substring_match(tmp_path):
    m = VirtuHindsightMemory(storage_path=str(tmp_path / "ent2.json"))
    assert "SW" not in m._extract_entities("SWISS machining")
    assert "SW" in m._extract_entities("SW 建模")
    assert "NXOpen" in m._extract_entities("调用NXOpen接口")


# ---------------------------------------------------------------------------
# 存储：读失败绝不覆写账本；正常落盘为原子写且产物合法
# ---------------------------------------------------------------------------
def test_planted_hindsight_load_failure_clobbers_ledger(tmp_path):
    p = tmp_path / "banks.json"
    corrupt = b'{"banks": {"broken": '  # 截断 JSON
    p.write_bytes(corrupt)
    m = VirtuHindsightMemory(storage_path=str(p))
    m.retain("default", "new experience after load failure")
    assert p.read_bytes() == corrupt, "读失败后不得用空账本覆写原文件"


def test_planted_working_memory_load_failure_clobbers_ledger(tmp_path):
    p = tmp_path / "wm.json"
    corrupt = b'{"goal": {"intent": '
    p.write_bytes(corrupt)
    wm = BuiltinWorkingMemory(session_id="store", persist_path=str(p))
    wm.record_fact("outer_diameter", 60.0)
    assert p.read_bytes() == corrupt, "读失败后不得覆写原工作记忆账本"


def test_guard_hindsight_atomic_save_valid(tmp_path):
    p = tmp_path / "banks_ok.json"
    m = VirtuHindsightMemory(storage_path=str(p))
    m.retain("default", "atomic save probe")
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["banks"]["default"]["units"]
    leftovers = [f for f in tmp_path.iterdir() if f.name != "banks_ok.json"]
    assert leftovers == [], f"原子写不得残留临时文件: {leftovers}"


def test_guard_working_memory_atomic_save_valid(tmp_path):
    p = tmp_path / "wm_ok.json"
    wm = BuiltinWorkingMemory(session_id="store_ok", persist_path=str(p))
    wm.record_fact("outer_diameter", 60.0)
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["facts"]["outer_diameter"]["value"] == 60.0
    leftovers = [f for f in tmp_path.iterdir() if f.name != "wm_ok.json"]
    assert leftovers == []