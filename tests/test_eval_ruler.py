"""The evaluation ruler must be honest about itself.

Measured on 2026-11-01: the 240-case suite authors a per-case token budget
(easy 256 / medium 448 / hard 704), and the base arm's wanted completion length on
boundary/knowledge/reasoning is 323-397 tokens median. Result: 21 of 30 boundary
records hit the ceiling, so `boundary = 47.83` was really a score over 9 cases. Two
harness gaps followed from that - the runner could only ever lower a budget, and the
report published a dimension mean without saying how much of it was truncation.
"""
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from virtu_eval import report  # noqa: E402


def _rec(dim, verdict, score, finish_reason="stop", tokens=40):
    return {"case_id": f"{dim}-{verdict}-{score}", "dimension": dim, "tier": "medium",
            "tags": [], "prompt": "p", "gold": {}, "max_tokens": 256,
            "response": "r", "score": score, "verdict": verdict,
            "criteria": [], "gen": {"elapsed_s": 3.0, "completion_tokens": tokens,
                                    "prompt_tokens": 50, "finish_reason": finish_reason}}


class ReportTruncationHonestyTests(unittest.TestCase):
    def test_truncated_records_are_reported_separately_from_the_mean(self):
        recs = ([_rec("boundary", "partial_truncated", 40.0, "length") for _ in range(3)]
                + [_rec("boundary", "pass", 100.0) for _ in range(2)])
        dims = report.aggregate(recs)["dimensions"]["boundary"]
        self.assertEqual(dims["n_truncated"], 3)
        self.assertEqual(dims["n_untruncated"], 2)
        self.assertEqual(dims["score"], 64.0)                    # published 口径不变
        self.assertEqual(dims["score_untruncated_only"], 100.0)  # honest subset

    def test_length_finish_reason_counts_even_when_the_label_says_otherwise(self):
        """A record that ran into the ceiling is budget-truncated whatever the verdict
        says; counting only the label understated boundary as 16/30 vs 21/30 actual."""
        recs = [_rec("reasoning", "partial", 55.0, "length"),
                _rec("reasoning", "pass", 100.0, "stop")]
        dims = report.aggregate(recs)["dimensions"]["reasoning"]
        self.assertEqual(dims["n_truncated"], 1)
        self.assertEqual(dims["n_untruncated"], 1)
        self.assertEqual(dims["score_untruncated_only"], 100.0)

    def test_clean_dimension_reports_zero_truncations_not_none(self):
        dims = report.aggregate([_rec("toolcall", "pass", 100.0)])["dimensions"]["toolcall"]
        self.assertEqual(dims["n_truncated"], 0)
        self.assertEqual(dims["score_untruncated_only"], 100.0)


class RunnerTokenFloorTests(unittest.TestCase):
    """The floor exists because --max-tokens-cap and --cap-by-tier both min(), so no
    CLI path could give a verbose arm enough budget."""

    def _dry_ruler(self, out_dir, token_floor):
        from virtu_eval import runner
        arms = json.load(io.open(ROOT / "virtu_eval" / "arms.json", encoding="utf-8"))
        runner.run(str(ROOT / "data" / "benchmark" / "virtu_eval_v1"),
                   arms["ollama_qwen3_8b_base"], out_dir, dims=["boundary"],
                   token_floor=token_floor, dry=True)
        recs = [json.loads(line) for line in
                io.open(os.path.join(out_dir, "dry_run.jsonl"), encoding="utf-8")]
        return recs

    def test_floor_raises_every_case_budget(self):
        with tempfile.TemporaryDirectory() as temp:
            authored = self._dry_ruler(os.path.join(temp, "a"), None)
            floored = self._dry_ruler(os.path.join(temp, "b"), 1024)
        self.assertTrue(any(r["max_tokens"] < 1024 for r in authored),
                        "用例自带预算应低于地板值，否则这条测试没有意义")
        self.assertTrue(all(r["max_tokens"] >= 1024 for r in floored))
        self.assertEqual(len(authored), len(floored))

    def test_floor_is_recorded_in_the_manifest_fingerprint(self):
        """Different rulers must not be comparable by accident."""
        with tempfile.TemporaryDirectory() as temp:
            self._dry_ruler(os.path.join(temp, "c"), 900)
            manifest = json.load(io.open(os.path.join(temp, "c", "dry_manifest.json"),
                                         encoding="utf-8"))
        self.assertEqual(manifest["sampling"]["token_floor"], 900)


if __name__ == "__main__":
    unittest.main()
