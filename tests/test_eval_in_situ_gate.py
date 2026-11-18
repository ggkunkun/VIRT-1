"""The in-situ acceptance report must not claim a veto metric it never measured.

Measured on 2026-11-05: `cloud_train_pack/eval_in_situ.py` published
`physics_compliance_rate = 1.0` straight from a literal (comment: 「靶向语料已包含 100%
物理守恒样本」 - that is about the corpus, not the model's outputs), printed three
fabricated historical physics figures (0.62/0.85/0.94) inline, presented
`HISTORICAL_BASELINES` as measured arms, threw away every response, and normalised the
weighted total over whatever dimensions happened to run. The downloaded copy of that
report is what sat in `checkpoints/COMPREHENSIVE_EVAL_REPORT.md` claiming a 100% veto pass.
"""
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# 测试临时产物必须落在系统 TEMP：宿主 safe-delete 垫片对仓库内路径的删除会
# 累计到 turn 级批量删除阈值，超阈值时抛 SystemExit，全仓连跑会把用例打成假红。
# 系统 TEMP 是垫片明确放行的目录，且清理不污染工作区。
TMP_ROOT = Path(tempfile.gettempdir()) / "virtu_eval_test_tmp"


def _tmp_root():
    # 按需创建，目录被清理也不会变成假红。
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    return str(TMP_ROOT)

sys.path.insert(0, str(ROOT))

SPEC = importlib.util.spec_from_file_location(
    "eval_in_situ", str(ROOT / "cloud_train_pack" / "eval_in_situ.py"))
eis = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(eis)

PHYS_DIR = ROOT / "data" / "benchmark" / "virtu_eval_phys_v1"


def _gold_by_prompt():
    from virtu_eval.runner import load_cases
    cases = load_cases(str(PHYS_DIR), dims=["physics"])
    table = {}
    for case in cases:
        gold = case.get("gold") or {}
        answer = gold.get("answer") or json.dumps(gold, ensure_ascii=False)
        table[case["prompt"]] = answer
    return cases, table


class FakeArm:
    """Returns a fixed answer per prompt; records the prompts it was actually asked."""

    def __init__(self, table, perturb=None):
        self.table = table
        self.perturb = perturb
        self.asked = []

    def generate(self, messages, max_tokens=512, temperature=0.0, **kw):
        prompt = messages[-1]["content"]
        self.asked.append(prompt)
        text = self.table.get(prompt, "")
        if self.perturb:
            text = self.perturb(text)
        return {"text": text, "prompt_tokens": 1, "completion_tokens": 1,
                "finish_reason": "stop", "elapsed_s": 0.01, "arm": "fake"}

    def unload(self):
        return None


def _double_numbers(text):
    """Perturb every numeric field so the solver recompute must disagree."""
    def _d(match):
        return str(float(match.group(0)) * 2)
    import re
    return re.sub(r"-?\d+\.\d+", _d, text)


class PhysicsGateIsMeasured(unittest.TestCase):
    def test_source_no_longer_asserts_compliance_literal(self):
        src = (ROOT / "cloud_train_pack" / "eval_in_situ.py").read_text(encoding="utf-8")
        self.assertNotIn("physics_compliance = 1.0", src)
        self.assertNotIn("'0.62'", src)

    def test_gate_refuses_to_report_without_an_arm(self):
        for arm, selftest, reason in ((None, True, "NO_ARM_GOLD_PLAYBACK"),
                                      (None, False, "NO_ARM")):
            gate = eis.measure_physics_gate(arm, selftest=selftest)
            self.assertFalse(gate["measured"], gate)
            self.assertIsNone(gate["compliance"])
            self.assertIn(reason, gate["reason"])

    @unittest.skipUnless((PHYS_DIR / "physics.jsonl").exists(), "physics set missing")
    def test_gate_can_reach_100_percent_on_gold_answers(self):
        cases, table = _gold_by_prompt()
        arm = FakeArm(table)
        gate = eis.measure_physics_gate(arm, selftest=False)
        self.assertTrue(gate["measured"])
        self.assertEqual(gate["n"], len(cases))
        self.assertEqual(gate["compliance"], 1.0, gate["failures"])
        self.assertEqual(len(arm.asked), len(cases), "the gate must actually ask every case")

    @unittest.skipUnless((PHYS_DIR / "physics.jsonl").exists(), "physics set missing")
    def test_gate_rejects_wrong_numbers(self):
        cases, table = _gold_by_prompt()
        gate = eis.measure_physics_gate(FakeArm(table, perturb=_double_numbers),
                                        selftest=False)
        self.assertTrue(gate["measured"])
        self.assertLess(gate["compliance"], 0.2, gate)


class ReportFailsClosed(unittest.TestCase):
    def run_selftest_report(self, limit=0):
        with tempfile.TemporaryDirectory(dir=_tmp_root()) as tmp:
            data = eis.run_evaluation(model_path="fake", adapter_path=None,
                                      out_dir=tmp, device="cpu", limit=limit,
                                      selftest=True)
            raw = Path(tmp) / "raw.jsonl"
            rows = []
            if raw.exists():
                with io.open(raw, encoding="utf-8") as f:
                    rows = [json.loads(l) for l in f if l.strip()]
            md = (Path(tmp) / "COMPREHENSIVE_EVAL_REPORT.md").read_text(encoding="utf-8") \
                if (Path(tmp) / "COMPREHENSIVE_EVAL_REPORT.md").exists() else ""
        return data, rows, md

    def test_selftest_veto_fails_closed_and_evidence_is_written(self):
        data, rows, md = self.run_selftest_report()
        self.assertFalse(data["all_dimensions_pass_90"])
        self.assertTrue(any(f.startswith("physics_gate (NOT MEASURED") for f in data["failed_dimensions"]),
                        data["failed_dimensions"])
        self.assertIsNone(data["physics_compliance_rate"])
        self.assertEqual(len(rows), 240, "responses must be kept as evidence")
        self.assertTrue(all(len(r["response"]) > 0 for r in rows))
        self.assertIn("NOT MEASURED", md)
        self.assertIn("不得引用为历史实测成绩", md)

    def test_partial_coverage_is_not_published_as_a_full_ruler(self):
        data, rows, md = self.run_selftest_report(limit=30)
        self.assertEqual(data["coverage"]["dims_covered"], ["boundary"])
        self.assertLess(data["coverage"]["weight_covered"], 0.2)
        self.assertTrue(any(f.startswith("coverage (") for f in data["failed_dimensions"]),
                        data["failed_dimensions"])
        # 100 = renormalised over the covered weight, and the report says so.
        self.assertEqual(data["weighted_total_score"], 100.0)


if __name__ == "__main__":
    unittest.main()
