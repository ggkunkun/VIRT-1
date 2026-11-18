"""Guardrails for the capability SFT rebuild."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from scripts.build_capability_sft import (  # noqa: E402
    gold_numbers_consistent,
    gen_generation,
    gen_reasoning,
    rec,
)
from virtu_eval.contamination_check import check_sample, load_eval_cases  # noqa: E402
from virtu_eval.graders import score_case  # noqa: E402


def test_reasoning_numbers_match_formula():
    import random
    samples = gen_reasoning(random.Random(1), 40)
    assert len(samples) == 40
    for s in samples:
        user = s["messages"][1]["content"]
        asst = s["messages"][2]["content"]
        assert gold_numbers_consistent(user, asst)
        assert "r/min" in asst or "mm/min" in asst or "mm³" in asst or " s" in asst or "mm" in asst or "MPa" in asst


def test_gcode_samples_pass_grader():
    import random
    samples = gen_generation(random.Random(2), 80)
    gcodes = [s for s in samples if s["messages"][2]["content"].startswith("O")]
    assert len(gcodes) >= 10
    for s in gcodes[:15]:
        scored = score_case(
            s["messages"][2]["content"],
            [{"type": "gcode_structure", "weight": 1, "key": "gcode"}],
        )
        assert scored["score"] == 100.0, scored


def test_inconsistent_legacy_is_rejected():
    user = "工件为P20精密轴套(直径48.0mm, 长度40.0mm)"
    bad = "Workpiece: Cr12MoV | Envelope: D52.0 x 55.0mm"
    good = "P20 直径48.0mm 长度40.0mm"
    assert not gold_numbers_consistent(user, bad)
    assert gold_numbers_consistent(user, good)


def test_eval_prompt_is_flagged_as_contamination():
    cases = load_eval_cases(os.path.join(ROOT, "data", "benchmark", "virtu_eval_v1"))
    eval_prompt = None
    with open(os.path.join(ROOT, "data", "benchmark", "virtu_eval_v1", "reasoning.jsonl"), encoding="utf-8") as f:
        eval_prompt = json.loads(f.readline())["prompt"]
    s = rec(eval_prompt, "n = 2387.3 r/min", "S4")
    hits = check_sample(s, cases)
    assert hits, "copied eval prompt must be contamination"


def test_cli_emits_clean_jsonl(tmp_path=None):
    out = os.path.join(tempfile.gettempdir(), "virtu_sft_smoke.jsonl")
    cmd = [
        sys.executable, os.path.join(ROOT, "scripts", "build_capability_sft.py"),
        "--out", out,
        "--reasoning", "20", "--knowledge", "10", "--instruction", "10",
        "--generation", "20", "--boundary", "15", "--toolcall", "20",
        "--generalization", "5", "--legacy-limit", "0",
    ]
    subprocess.check_call(cmd, cwd=ROOT)
    n = sum(1 for _ in open(out, encoding="utf-8"))
    assert n >= 80
    chk = subprocess.run(
        [sys.executable, os.path.join(ROOT, "virtu_eval", "contamination_check.py"), out],
        cwd=ROOT,
    )
    assert chk.returncode == 0
