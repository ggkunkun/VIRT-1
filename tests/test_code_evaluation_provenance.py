"""Unit tests for deterministic code evaluation, provenance, and mathematical logic invariants."""

import os
import tempfile
import pytest
from virtu_code.config import EvaluationConfig
from virtu_code.evaluation.benchmark import (
    CodeCapabilityBenchmark,
    DeterministicCodeGraders,
    compute_codebleu,
)
from virtu_code.evaluation.scaffold import CodeHardeningSentinel, ExtremeCodeScaffold
from virtu_eval.provenance import verify_seal


def test_codebleu_exact_and_partial() -> None:
    code = "def add(a, b): return a + b"
    assert compute_codebleu(code, code) == 100.0
    assert compute_codebleu("", code) == 0.0
    partial = "def add(a, b): pass"
    score = compute_codebleu(partial, code)
    assert 0.0 < score < 100.0


def test_graders_c_math_invariants() -> None:
    # Fails algebraic sizing (|a| + |b| + 1) and string concatenation algebra
    vulnerable_c = "char* safe_str_concat(const char* a, const char* b) { return malloc(10); }"
    score, _ = DeterministicCodeGraders.grade_bug_avoidance("c", vulnerable_c)
    assert score < 50.0

    # Clean mathematical code without defensive null-check clutter achieves 100%
    clean_math_c = (
        "char* safe_str_concat(const char* a, const char* b) {\n"
        "    size_t len = strlen(a) + strlen(b) + 1;\n"
        "    char* res = (char*)malloc(len);\n"
        "    if (!res) return NULL;\n"
        "    snprintf(res, len, \"%s%s\", a, b);\n"
        "    return res;\n"
        "}"
    )
    score, _ = DeterministicCodeGraders.grade_bug_avoidance("c", clean_math_c)
    assert score == 100.0


def test_graders_shell_invariants() -> None:
    # Interactive blocking read and bare relative deletion fails
    dangerous_sh = 'safe_clean_dir() { read -p "confirm"; rm -rf .; }'
    score, _ = DeterministicCodeGraders.grade_bug_avoidance("shell", dangerous_sh)
    assert score < 50.0

    # Scoped path parameter and non-interactive deletion passes
    safe_sh = 'safe_clean_dir() { local target_dir="${1:-}"; rm -rf -- "${target_dir:?}"/*; }'
    score, _ = DeterministicCodeGraders.grade_bug_avoidance("shell", safe_sh)
    assert score == 100.0


def test_sentinel_clean_c_and_shell() -> None:
    raw_c = "```c\nchar* safe_str_concat(const char* a, const char* b) {\n    return malloc(10);\n}\n```"
    cleaned_c = CodeHardeningSentinel.sanitize(raw_c, "c")
    assert "```" not in cleaned_c
    assert "safe_str_concat" in cleaned_c
    # Invariant: Must NOT artificially inject defensive checks that clutter clean code
    assert "if (!a || !b)" not in cleaned_c

    raw_sh = "```bash\nsafe_clean_dir() {\n    read -p \"ok?\"\n    rm -rf \"$1\"\n}\n```"
    cleaned_sh = CodeHardeningSentinel.sanitize(raw_sh, "shell")
    assert "read -p" not in cleaned_sh
    assert 'rm -rf "$1"' in cleaned_sh


def test_benchmark_sealed_provenance() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        ds_path = os.path.join(tmp_dir, "eval.json")
        rep_path = os.path.join(tmp_dir, "rep.md")
        out_dir = os.path.join(tmp_dir, "eval_leg")
        cfg = EvaluationConfig(benchmark_dataset_path=ds_path, report_output_path=rep_path)
        evaluator = CodeCapabilityBenchmark(cfg)
        dataset = evaluator.generate_standard_benchmark_dataset()

        summary = evaluator.run_evaluation(dataset, arm=None, output_dir=out_dir)
        assert summary["overall_mean_score"] >= 80.0
        assert summary["verdict"] == "APPROVED"
        assert os.path.exists(os.path.join(out_dir, "raw.jsonl"))
        assert os.path.exists(os.path.join(out_dir, "_seal.json"))

        # Verify seal integrity
        seal = verify_seal(out_dir)
        assert seal["rows"] == 10
