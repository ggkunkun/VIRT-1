import importlib.util
import json
from pathlib import Path

import pytest

from virtu_eval.provenance import (
    RunIdentity,
    metrics_from_raw,
    seal_leg,
    verify_seal,
)

_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "eval_disciplined_ab", _ROOT / "scripts" / "eval_disciplined_ab.py")
ab = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ab)

EVALUATORS = [
    r"D:\V\Scripts\python.exe D:\V\virtu_eval\runner.py --arms-config a.json --arm b",
    r"C:\py\python.exe virtu_eval.py --arm bridge_deployed --out-dir _eval_disciplined_text",
    r"D:\V\Scripts\python.exe -u runs/eval/fullboard_20261105_0930/run_chain4.py",
]
NON_EVALUATORS = [
    'powershell -NoProfile -Command Get-CimInstance Win32_Process ... runner.py ...',
    r'D:\V\Scripts\python.exe -X utf8 -c "print(\'virtu_eval/runner.py\')"',
    r'C:\py\python.exe scripts\some_unrelated_tool.py --flag',
]


def test_quiet_gate_counts_every_evaluator_harness(tmp_path, monkeypatch):
    monkeypatch.setattr(ab, "_ps_lines", lambda: EVALUATORS + NON_EVALUATORS)
    hits = ab.foreign_activity("scripts/eval_disciplined_ab.py")
    assert len(hits) == len(EVALUATORS), hits
    assert not any("get-ciminstance" in h.lower() for h in hits)


def test_quiet_gate_is_not_always_red(monkeypatch):
    monkeypatch.setattr(ab, "_ps_lines", lambda: NON_EVALUATORS)
    assert ab.foreign_activity("scripts/eval_disciplined_ab.py") == []


def test_loaded_model_blocks_the_gate(monkeypatch):
    monkeypatch.setattr(ab, "_ps_lines", lambda: [])
    monkeypatch.setattr(ab, "loaded_models", lambda: ["virtu-comprehensive:latest"])
    quiet, why = ab.host_is_quiet("scripts/eval_disciplined_ab.py")
    assert quiet is False and "loaded model" in why
    monkeypatch.setattr(ab, "loaded_models", lambda: [])
    assert ab.host_is_quiet("scripts/eval_disciplined_ab.py")[0] is True


def _write_raw(path, rows):
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                    encoding="utf-8")


def test_seal_detects_a_rewrite(tmp_path):
    raw = tmp_path / "raw.jsonl"
    _write_raw(raw, [{"case_id": "a", "score": 100.0}])
    seal_leg(tmp_path, owner="test")
    assert verify_seal(tmp_path)["rows"] == 1
    _write_raw(raw, [{"case_id": "a", "score": 0.0}])
    with pytest.raises(ValueError, match="封缄后被改写"):
        verify_seal(tmp_path)


def test_metrics_refuse_rows_without_per_row_identity(tmp_path):
    raw = tmp_path / "raw.jsonl"
    _write_raw(raw, [
        {"case_id": "a", "dimension": "reasoning", "score": 100.0,
         "verdict": "ok", "gen": {}},
        {"case_id": "b", "dimension": "reasoning", "score": 100.0,
         "verdict": "ok", "gen": {}},
    ])
    with pytest.raises(ValueError, match="身份取证"):
        metrics_from_raw(raw, run_id="test", planned=2, require_row_identity=True)


def test_metrics_refuse_transport_failures(tmp_path):
    raw = tmp_path / "raw.jsonl"
    _write_raw(raw, [
        {"case_id": f"c{i}", "dimension": "reasoning", "score": 0.0,
         "verdict": "transport_error"} for i in range(5)
    ])
    with pytest.raises(ValueError, match="从未被模型答到"):
        metrics_from_raw(raw, run_id="test", planned=5, require_row_identity=False)


def test_run_identity_is_stable_for_same_inputs():
    first = RunIdentity.capture(model_ids=(), case_dirs=["data/benchmark/virtu_eval_v1"])
    second = RunIdentity.capture(model_ids=(), case_dirs=["data/benchmark/virtu_eval_v1"])
    assert first.run_id == second.run_id
    assert first.cases == second.cases
