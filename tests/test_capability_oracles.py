# -*- coding: utf-8 -*-
"""tests/test_capability_oracles.py — P3 评测 oracle 与 GUI 成功诚实账本（可证伪）。"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from virtu_omni.eval.capability_oracles import (
    gui_success_ledger, nesting_oracle, post_dialect_oracle,
    fea_cross_check_oracle, run_all_oracles,
)


def test_all_measurable_oracles_pass():
    res = run_all_oracles()
    assert res["all_measurable_oracles_passed"] is True
    for key in ("nesting", "post_dialect", "fea_cross_check"):
        assert res["oracles"][key]["passed"] is True, key
        assert res["oracles"][key]["basis"] == "measured", key


def test_nesting_oracle_rejects_planted_overlap():
    o = nesting_oracle()
    assert o["good_layout_passed"] is True
    assert o["planted_overlap_rejected"] is True
    assert o["passed"] is True


def test_post_dialect_oracle_three_dialects():
    o = post_dialect_oracle()
    assert o["coord_consistency_passed"] is True
    for d in ("fanuc", "siemens", "heidenhain"):
        assert o["per_dialect"][d]["status"] == "passed"
        assert o["max_err_mm"][d] <= 1e-3


def test_fea_oracle_cross_check():
    o = fea_cross_check_oracle()
    assert o["cross_check_passed"] is True
    assert o["deflection_error_pct"] <= 2.0
    assert o["basis"] == "measured"


# ---------------------------------------------------------------------------
# GUI 成功账本：诚实边界（deny 不得冒充成功，任务成功永远 unmeasured）
# ---------------------------------------------------------------------------
def test_gui_ledger_real_log_unmeasured():
    led = gui_success_ledger()
    assert led["gui_task_success"] is None
    assert led["gui_task_success_basis"] == "unmeasured"
    assert led["input_gate_basis"] in ("measured", "unmeasured")


def test_gui_ledger_deny_never_success(tmp_path):
    log = tmp_path / "audit.jsonl"
    log.write_text("\n".join(json.dumps({"event": "deny", "verdict_code": "DESKTOP_INPUT_NOT_APPROVED"})
                             for _ in range(5)), encoding="utf-8")
    led = gui_success_ledger(str(log))
    assert led["input_gate_deny_count"] == 5
    assert led["input_gate_allow_count"] == 0
    assert led["gui_task_success"] is None
    assert led["gui_task_success_basis"] == "unmeasured"


def test_gui_ledger_planted_allow_still_unmeasured(tmp_path):
    """植入 allow 事件：输入门计数可测，但任务成功仍 unmeasured（批准≠完成）。"""
    log = tmp_path / "audit.jsonl"
    log.write_text(json.dumps({"event": "allow", "action": "click", "verdict_code": "OK"}),
                   encoding="utf-8")
    led = gui_success_ledger(str(log))
    assert led["input_gate_allow_count"] == 1
    assert led["gui_task_success"] is None
    assert led["gui_task_success_basis"] == "unmeasured"


def test_gui_ledger_missing_file_unmeasured(tmp_path):
    led = gui_success_ledger(str(tmp_path / "nonexistent.jsonl"))
    assert led["read_error"] is not None
    assert led["total_events"] == 0
    assert led["gui_task_success_basis"] == "unmeasured"
    assert led["input_gate_basis"] == "unmeasured"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q", "-o", "addopts=", "-p", "no:cacheprovider"]))