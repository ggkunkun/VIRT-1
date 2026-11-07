"""Falsification tests for the quiet-window gate (AGENTS.md §8.4).

A gate that can only say "go" is not a gate.  Each test plants a state that must be refused,
and the last one plants activity *after* the window opened to prove the gate closes again.
"""
from __future__ import annotations

import time

import pytest

from scripts.rsi_quiet_gate import (ROOT, busy_reasons, recent_writes, rsi_command, step,
                                    watch_paths)

OWN = "rsi_quiet_gate"


def test_a_foreign_evaluator_must_block_the_gate():
    lines = ["D:\\Virtu模型\\.venv\\Scripts\\python.exe -m virtu_eval.runner --arm base"]
    reasons = busy_reasons(lines, [], [], OWN, watched=3)
    assert reasons and "foreign runner" in reasons[0], reasons


def test_the_gate_must_not_count_itself_as_foreign():
    lines = ["D:\\Virtu模型\\.venv\\Scripts\\python.exe scripts/rsi_quiet_gate.py --limit 60"]
    assert busy_reasons(lines, [], [], OWN, watched=3) == []


def test_a_probe_that_merely_mentions_the_runner_is_not_an_evaluator():
    lines = ["powershell -NoProfile -Command Get-CimInstance Win32_Process "
             "-Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*virtu_eval*' }"]
    assert busy_reasons(lines, [], [], OWN, watched=3) == []


def test_a_loaded_model_must_block_the_gate():
    reasons = busy_reasons([], ["qwen3:8b"], [], OWN, watched=3)
    assert reasons and "ollama holds qwen3:8b" in reasons[0], reasons


def test_our_own_pinned_model_does_not_block_an_in_flight_run():
    assert busy_reasons([], ["virtu-disciplined:v1"], [], OWN,
                        allowed_models=("virtu-disciplined:v1",), watched=3) == []


def test_a_fresh_write_must_block_the_gate_even_with_no_recognisable_process(tmp_path):
    artifact = tmp_path / "raw.jsonl"
    artifact.write_text("{}\n", encoding="utf-8")
    writes = recent_writes([artifact], now=time.time(), horizon_s=150)
    assert writes, "a just-written artifact must register as activity"
    reasons = busy_reasons([], [], writes, OWN, watched=3)
    assert reasons and "recent write" in reasons[0], reasons


def test_a_stale_write_does_not_block(tmp_path):
    artifact = tmp_path / "raw.jsonl"
    artifact.write_text("{}\n", encoding="utf-8")
    writes = recent_writes([artifact], now=time.time() + 10_000, horizon_s=150)
    assert writes == []


def test_nothing_to_watch_is_a_red_gate_not_a_pass():
    """§8.4: an empty match set must never be read as quiet."""
    reasons = busy_reasons([], [], [], OWN, watched=0)
    assert reasons and "no measurement artifact" in reasons[0], reasons


def test_the_window_opens_only_after_the_hold_period():
    action, since = step(None, [], now=100.0, hold_s=150)
    assert action == "wait" and since == 100.0
    action, since = step(since, [], now=200.0, hold_s=150)
    assert action == "wait", "60s of quiet is not a 150s window"
    action, since = step(since, [], now=260.0, hold_s=150)
    assert action == "go" and since == 100.0


def test_activity_resuming_after_a_go_closes_the_window_again():
    _, since = step(None, [], now=100.0, hold_s=150)
    action, since = step(since, ["foreign runner: x"], now=120.0, hold_s=150)
    assert action == "wait" and since is None, "the window must restart from zero"
    action, since = step(since, [], now=130.0, hold_s=150)
    assert action == "wait" and since == 130.0


def test_the_watch_set_never_includes_our_own_rsi_output():
    """RSI writes receipt/audit under runs/rsi; counting it would deadlock the gate."""
    for path in watch_paths():
        rel = path.relative_to(ROOT).as_posix()
        # Prefix, not substring: stale fixtures nest their own ``runs/rsi`` deeper down.
        assert not rel.startswith("runs/rsi/"), rel


def test_the_launch_command_matches_the_validated_budget():
    class Args:
        case_dir = "data/benchmark/virtu_eval_phys_v1"
        dims = "physics,derivation"
        limit = 60
        min_validation = 24
        rounds = 2
        max_calls = 200
        max_seconds = 3600

    cmd = rsi_command(Args(), "virtu-disciplined:v1", "http://127.0.0.1:11434")
    joined = " ".join(cmd)
    assert "virtu_omni.rsi.cli run" in joined
    assert "--min-validation 24" in joined and "--limit 60" in joined
    assert "--max-seconds 3600" in joined
    # The case dir is ``.../virtu_eval_phys_v1``.  A bare "virtu_eval" marker would convict this
    # very line as a foreign leg and then terminate our own child; prove the judgement is narrow.
    assert busy_reasons([Args.case_dir], [], [], OWN, watched=3) == []


def test_a_second_rsi_run_is_a_competitor_too():
    """Two RSI runs on one card are the original failure mode.

    This line *is* foreign activity when another pid owns it; the gate avoids convicting its
    own child by excluding that pid in ``proc_lines``, not by weakening the marker.
    """
    lines = ["python.exe -m virtu_omni.rsi.cli run --model-id virtu-disciplined:v1"]
    reasons = busy_reasons(lines, [], [], OWN, watched=3)
    assert reasons and "foreign runner" in reasons[0], reasons
