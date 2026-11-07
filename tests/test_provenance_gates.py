"""The provenance gate must fire on every fabrication shape found today, or it is decoration.

Each test plants one of the 2026-11-05 incidents and asserts ``virtu_eval.provenance``
refuses it: a source literal published as a veto metric, a null standing in for a score,
an arm made entirely of transport errors recorded as completed, a tag re-pointed mid-leg,
a ruler swapped between legs, and a corpus row teaching mm^5 under an mm^4 field name.
"""
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = ROOT / "runs" / "eval" / "_test_tmp"


def _tmp_root():
    # scratch/ is a shared sweep target on this box (emptied 2026-11-05, taking
    # probe scripts with it); test temporaries live under runs/eval and are created
    # on demand so a cleaned directory cannot turn into a fake red.
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    return str(TMP_ROOT)

sys.path.insert(0, str(ROOT))

from virtu_eval.provenance import Metric, RunIdentity, artifact_identity, metrics_from_raw, \
    render_table, sha256_file  # noqa: E402

EVAL_RUN = ROOT / "runs" / "eval" / "fullboard_20261105_0930"
DEAD_ARM = ROOT / "runs" / "eval" / "comprehensive_20261105_012119" / "screening" / \
    "virtu-eval_delta5" / "raw.jsonl"
CORPUS_WITH_MM5 = ROOT / "data" / "sft" / "virtu_final_train.jsonl"


class TestMetricCannotLie(unittest.TestCase):
    def test_measured_metric_without_evidence_is_refused(self):
        m = Metric("physics_compliance_rate", 1.0, "measured", n=30, evidence=None, run_id="x")
        with self.assertRaises(ValueError):
            m.check()

    def test_asserted_metric_is_visible_not_silent(self):
        """The old `physics_compliance = 1.0` may still be written - as an assertion."""
        row = Metric("physics_compliance_rate", 1.0, "asserted").as_row()
        self.assertEqual(row[2], "断言(未测)")
        table = render_table([Metric("gate", 1.0, "asserted", note="源码字面量")])
        self.assertIn("断言(未测)", table)

    def test_none_value_never_prints_as_a_score(self):
        with self.assertRaises(ValueError):
            Metric("usage", None, "measured", n=10, evidence=__file__, run_id="r").check()

    def test_measured_metric_must_state_sample_size(self):
        with self.assertRaises(ValueError):
            Metric("reasoning", 54.74, "measured", n=0, evidence=__file__, run_id="r").check()


class TestBrokenRunHasNoMetrics(unittest.TestCase):
    @unittest.skipUnless(DEAD_ARM.exists(), "the 56x http_404 arm evidence is gone")
    def test_transport_only_arm_cannot_yield_a_number(self):
        rows = [json.loads(l) for l in io.open(DEAD_ARM, encoding="utf-8-sig") if l.strip()]
        self.assertEqual({r["verdict"] for r in rows}, {"transport_error"},
                         "该证据文件已不再是全 404 的样本，测试要换样本")
        with self.assertRaises(ValueError) as ctx:
            metrics_from_raw(DEAD_ARM, run_id="r")
        self.assertIn("从未被模型答到", str(ctx.exception))

    def test_good_leg_yields_one_metric_per_dimension(self):
        with tempfile.TemporaryDirectory(dir=_tmp_root()) as tmp:
            raw = Path(tmp) / "raw.jsonl"
            with io.open(raw, "w", encoding="utf-8") as f:
                f.write(json.dumps({"case_id": "a", "dimension": "reasoning",
                                    "verdict": "pass", "score": 100.0}) + "\n")
                f.write(json.dumps({"case_id": "b", "dimension": "reasoning",
                                    "verdict": "partial", "score": 40.0}) + "\n")
            metrics = metrics_from_raw(raw, run_id="deadbeef")
        self.assertEqual(len(metrics), 1)
        self.assertEqual(metrics[0].n, 2)
        self.assertEqual(metrics[0].value, 70.0)
        self.assertEqual(metrics[0].run_id, "deadbeef")


class TestIdentityIsByDigestNotByName(unittest.TestCase):
    def test_capture_pins_layers_and_ruler(self):
        ident = RunIdentity.capture(model_ids=["qwen3:8b"],
                                    case_dirs=["data/benchmark/virtu_eval_v1"])
        self.assertTrue(ident.artifacts["qwen3:8b"]["present"])
        self.assertTrue(ident.artifacts["qwen3:8b"]["model"].startswith("sha256:"))
        self.assertEqual(len(ident.cases), 8)
        self.assertEqual(len(ident.run_id), 16)

    def test_repointed_tag_changes_the_run_id(self):
        """Four names sharing one manifest is exactly what happened at 10:4x today."""
        before = RunIdentity.capture(model_ids=["qwen3:8b"], case_dirs=["data/benchmark/virtu_eval_v1"])
        pinned = dict(before.artifacts["qwen3:8b"])
        pinned["model"] = "sha256-" + "0" * 64
        after = RunIdentity.capture(model_ids=["qwen3:8b"], case_dirs=["data/benchmark/virtu_eval_v1"])
        self.assertNotEqual(after.run_id,
                            RunIdentity({"qwen3:8b": pinned}, after.cases, after.ruler).run_id)
        drift = RunIdentity({"qwen3:8b": pinned}, after.cases, after.ruler).drift()
        self.assertTrue(any("model 层从" in d for d in drift), drift)

    def test_swapped_grader_is_detected(self):
        ident = RunIdentity.capture(model_ids=[], case_dirs=[])
        tampered = dict(ident.ruler)
        tampered["virtu_eval/graders.py"] = "f" * 64
        drift = RunIdentity({}, {}, tampered).drift()
        self.assertTrue(any("判分器" in d for d in drift), drift)

    def test_round_trip_is_stable(self):
        ident = RunIdentity.capture(model_ids=["qwen3:8b"], case_dirs=[])
        with tempfile.TemporaryDirectory(dir=_tmp_root()) as tmp:
            path = Path(tmp) / "identity.json"
            ident.write(path)
            again = RunIdentity.read(path)
        self.assertEqual(again.run_id, ident.run_id)
        self.assertEqual(again.drift(), [], "同一份字节不该报漂移")


@unittest.skipUnless(CORPUS_WITH_MM5.exists(), "corpus absent")
class TestTargetValuesAreAuditable(unittest.TestCase):
    def test_unit_audit_fires_on_the_shipped_corpus(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "corpus_unit_audit", str(ROOT / "scripts" / "corpus_unit_audit.py"))
        audit = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(audit)
        result = audit.scan(str(CORPUS_WITH_MM5))
        self.assertEqual(result["bad_rows"], 255, result["examples"][:1])


class TestSealsAndRowIdentity(unittest.TestCase):
    """The two rewrite modes measured today: someone replaced a leg's file, and a leg whose
    rows predate per-row identity cannot be attributed to bytes at all."""

    def _leg(self, tmp, rows, planned=None):
        leg = Path(tmp) / "board7__x"
        leg.mkdir(parents=True, exist_ok=True)
        with io.open(leg / "raw.jsonl", "w", encoding="utf-8") as f:
            for record in rows:
                f.write(json.dumps(record) + "\n")
        if planned is not None:
            (leg / "manifest.json").write_text(json.dumps({"n_cases_selected": planned}),
                                               encoding="utf-8")
        return leg

    @staticmethod
    def _row(case_id, score, layers=None):
        return {"case_id": case_id, "dimension": "reasoning", "verdict": "pass",
                "score": score, "gen": ({"served_layers": layers} if layers else {})}

    def test_rewritten_evidence_is_refused_after_sealing(self):
        from virtu_eval.provenance import seal_leg, verify_seal
        with tempfile.TemporaryDirectory(dir=_tmp_root()) as tmp:
            leg = self._leg(tmp, [self._row("a", 100.0, {"model": "sha256:x"})])
            seal_leg(leg, owner="test")
            self.assertTrue(verify_seal(leg)["raw_sha256"])
            (leg / "raw.jsonl").write_text(json.dumps(self._row("a", 0.0, {"model": "sha256:x"}))
                                           + "\n", encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                verify_seal(leg)
            self.assertIn("被改写", str(ctx.exception))

    def test_appended_rows_are_also_a_broken_seal(self):
        from virtu_eval.provenance import seal_leg, verify_seal
        with tempfile.TemporaryDirectory(dir=_tmp_root()) as tmp:
            leg = self._leg(tmp, [self._row("a", 100.0, {"model": "sha256:x"})])
            seal_leg(leg, owner="test")
            with io.open(leg / "raw.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(self._row("b", 50.0, {"model": "sha256:x"})) + "\n")
            with self.assertRaises(ValueError):
                verify_seal(leg)

    def test_unsealed_leg_cannot_be_published(self):
        from virtu_eval.provenance import verify_seal
        with tempfile.TemporaryDirectory(dir=_tmp_root()) as tmp:
            leg = self._leg(tmp, [self._row("a", 100.0)])
            with self.assertRaises(ValueError) as ctx:
                verify_seal(leg)
            self.assertIn("未封缄", str(ctx.exception))

    def test_rows_without_identity_stamp_are_not_scores(self):
        with tempfile.TemporaryDirectory(dir=_tmp_root()) as tmp:
            leg = self._leg(tmp, [self._row("a", 100.0), self._row("b", 90.0)], planned=2)
            with self.assertRaises(ValueError) as ctx:
                metrics_from_raw(leg / "raw.jsonl", run_id="r", planned=2,
                                 require_row_identity=True)
            self.assertIn("身份取证", str(ctx.exception))
            self.assertEqual(len(metrics_from_raw(leg / "raw.jsonl", run_id="r")), 1)

    def test_short_dimension_is_labelled_partial_not_measured(self):
        rows = [self._row(f"reasoning-e0{i}", 100.0, {"model": "sha256:x"}) for i in (1, 2)]
        with tempfile.TemporaryDirectory(dir=_tmp_root()) as tmp:
            leg = self._leg(tmp, rows, planned=3)
            metrics = metrics_from_raw(leg / "raw.jsonl", run_id="r", planned=3,
                                       planned_by_dim={"reasoning": 3}, require_row_identity=True)
            # as_row() re-checks that the evidence file still exists, so assert in-block
            self.assertEqual(metrics[0].basis, "partial")
            self.assertIn("部分覆盖 2/3", metrics[0].as_row()[2])
        with self.assertRaises(ValueError):
            Metric("reasoning", 100.0, "measured", n=2, evidence=__file__, run_id="r",
                   planned=3).check()

    def test_partial_leg_is_not_a_dimension_score(self):
        with tempfile.TemporaryDirectory(dir=_tmp_root()) as tmp:
            leg = self._leg(tmp, [self._row("a", 100.0, {"model": "sha256:x"})], planned=30)
            with self.assertRaises(ValueError) as ctx:
                metrics_from_raw(leg / "raw.jsonl", run_id="r", planned=30,
                                 require_row_identity=True)
            self.assertIn("覆盖不全", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
