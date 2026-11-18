"""`inertia_*_mm4` was a mm^5 number, and nothing was watching.

Measured 2026-11-05: `mass_props_csg` computed `volume x (h^2+w^2)/12` (mm^5) and the solver
published it as `inertia_ixx_mm4`; `mass_props` appears in **zero** cases of
`data/benchmark/virtu_eval_phys_v1`, so no ruler looked at it. The wrong targets reached the
shipped corpora - 255 rows of `data/sft/virtu_final_train.jsonl` (122 box / 133 cylinder),
example stored 1.7609e9 vs analytic 2.6065e7 (67.6x). Fixed the solver, added
`scripts/corpus_unit_audit.py` (report / repair), and pinned both here.

Both reference defects below are fixed; what remains is the drift hazard they exposed - a
reference that grows a field silently re-grades every case that shares it, so the gold-must-
score-100 invariant is asserted for all three case sets on every run.
"""
import importlib.util
import io
import json
import math
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.distill_local_solver import mass_props_csg  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "corpus_unit_audit", str(ROOT / "scripts" / "corpus_unit_audit.py"))
audit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(audit)

CORPUS = ROOT / "data" / "sft" / "virtu_final_train.jsonl"
FIXED = ROOT / "data" / "sft" / "virtu_final_train.units_fixed.jsonl"


class TestSolverUnits(unittest.TestCase):
    def test_box_inertia_is_a_second_moment_of_area(self):
        l, w, h = 120.0, 60.0, 20.0
        V, centroid, (Ix, Iy, Iz) = mass_props_csg("box", {"l": l, "w": w, "h": h}, 0.00785)
        self.assertAlmostEqual(Ix, w * h ** 3 / 12.0, places=6)
        self.assertAlmostEqual(Iz, l * w ** 3 / 12.0, places=6)
        self.assertAlmostEqual(V, l * w * h, places=6)
        # mm^4 for a mm section: nothing may scale with a third length
        self.assertLess(Ix / (w * h ** 3), 1.0)

    def test_cylinder_inertia_matches_pi_r4_over_4(self):
        r, h = 75.9, 56.9
        V, centroid, (Ix, Iy, Iz) = mass_props_csg("cylinder", {"r": r, "h": h}, 0.00785)
        # 轴线沿 z：绕直径轴 x/y 均为 pi*r^4/4，绕轴线 z 的极惯性矩为 pi*r^4/2。
        # 旧约定把 pi*r^4/2 挂在 Iy、Iz 拿直径轴值（小一倍），与 wm_schema 定律卡
        # inertia_izz_mm4=pi*r^4/2 冲突；2026-11-08 修正后三轴全部钉住。
        self.assertAlmostEqual(Ix, math.pi * r ** 4 / 4.0, places=2)
        self.assertAlmostEqual(Iy, math.pi * r ** 4 / 4.0, places=2)
        self.assertAlmostEqual(Iz, math.pi * r ** 4 / 2.0, places=2)
        # the old bug grew with h (mm^5); a true section moment must not
        V2, _, (Ix2, Iy2, Iz2) = mass_props_csg("cylinder", {"r": r, "h": h * 2}, 0.00785)
        self.assertAlmostEqual(Ix, Ix2, places=2, msg="Ixx 随高度变化说明它不是截面惯性矩")
        self.assertAlmostEqual(Iy, Iy2, places=2)
        self.assertAlmostEqual(Iz, Iz2, places=2)


class TestAuditIsNotVacuous(unittest.TestCase):
    @unittest.skipUnless(CORPUS.exists(), "corpus missing")
    def test_original_corpus_is_flagged_and_the_fix_is_verified(self):
        result = audit.scan(str(CORPUS))
        self.assertEqual(result["rows"], 3017)
        self.assertEqual(result["bad_rows"], 255, result["examples"][:1])
        self.assertEqual({e["reason"] for e in result["examples"]}, {"unit_mismatch"})

    @unittest.skipUnless(FIXED.exists(), "repaired corpus missing")
    def test_repaired_corpus_is_clean_row_for_row(self):
        result = audit.scan(str(FIXED))
        self.assertEqual(result["bad_rows"], 0, result["examples"][:1])
        with io.open(CORPUS, encoding="utf-8") as a, io.open(FIXED, encoding="utf-8") as b:
            for la, lb in zip(a, b):
                self.assertEqual(len(json.loads(la)), len(json.loads(lb)))
                self.assertEqual(json.loads(la)["messages"][0]["content"][:60],
                                 json.loads(lb)["messages"][0]["content"][:60],
                                 "repair must only touch the inertia numbers")

    @unittest.skipUnless(FIXED.exists(), "repaired corpus missing")
    def test_repair_does_not_break_escaping_or_json(self):
        """The fix is a regex substitution inside a JSON string value, so escaping is the risk."""
        with io.open(CORPUS, encoding="utf-8") as fa, io.open(FIXED, encoding="utf-8") as fb:
            checked = 0
            for index, (la, lb) in enumerate(zip(fa, fb), 1):
                if index > 1200:
                    break
                rec_b = json.loads(lb)  # outer document must still parse
                self.assertIn("messages", rec_b)
                if "inertia_ixx_mm4" not in lb:
                    continue
                self.assertEqual(la.count('\\"'), lb.count('\\"'),
                                 f"row {index}: 修复改变了转义层数，会破坏内层 JSON")
                self.assertIsNone(audit.row_issue(lb), f"row {index} 仍是错量纲")
                checked += 1
        self.assertGreaterEqual(checked, 50, "样本太少，等于没验")

    def test_audit_catches_a_deliberately_regressed_copy(self):
        """Mutant: take a clean row and write the old mm^5 formula back into it."""
        with io.open(FIXED, encoding="utf-8") as f:
            line = next(l for l in f if "inertia_ixx_mm4" in l)
        unescaped = line.replace('\\"', '"')
        cx, cy, cz = (float(x) for x in audit.WS_CENTROID.search(unescaped).groups())
        bad_value = (2 * cx) * (2 * cy) ** 3 / 12.0 * (2 * cz)  # volume x h^2/12 shape
        mutant = audit.WS_FIELD_RE.sub(
            lambda m: '"%s": %s' % (m.group(1), bad_value), unescaped)
        issue = audit.row_issue(mutant)
        self.assertTrue(issue, "变异体未被发现，说明审计是空转的")
        self.assertEqual(issue["reason"], "unit_mismatch")


class TestTrainerWiring(unittest.TestCase):
    def test_trainers_gate_units_before_reading_data(self):
        for rel in (
            "scripts/train_qwen3_8b_qlora.py",
            "scripts/train_world_model_final.py",
            "cloud_train_pack/train_turnkey.py",
            "cloud_train_pack/train_turnkey_worldmodel.py",
        ):
            text = io.open(ROOT / rel, encoding="utf-8", errors="ignore").read()
            self.assertIn("corpus_unit_audit", text, f"{rel} 未接量纲闸")
            body = text[text.index("parse_args("):]
            load_at = min(
                (body.index(m) for m in ("load_dataset", "load_wm_dataset", "AutoTokenizer.from_pretrained")
                 if m in body),
                default=body.index("assert_units_clean") + 1,
            )
            self.assertLess(body.index("assert_units_clean"), load_at,
                            f"{rel} 的量纲闸在读语料之后")


class TestPhysicsReferenceHonest(unittest.TestCase):
    """The 1.5 gate must be a *graded* reference field, and the sets must score their own gold.

    Adding `fos_gate` to `recompute` (another session, 10:23) silently grew the comparable
    field set of every fea_fos row, so the derivation rows' own gold dropped to 62.5/100 -
    a model omitting an unasked predicate would have been charged a capability failure that
    was really a ruler defect. `min_compared: 2` on those three criteria pins the intent back:
    the derivation leg grades numeric laws, the physics leg grades the verdict.
    """

    def test_design_negative_volume_is_rejected_not_clamped(self):
        from scripts.wm_verifier import recompute
        scenario = {"task": "design", "r_out": 30.0, "r_bore": 20.0, "t": 10.0,
                    "n_holes": 40, "r_hole": 12.0, "rho": 0.00785}
        state = recompute(scenario)
        self.assertLess(state["volume_mm3"], 0.0,
                        "孔体积超过环形体积应给出负值，而不是被 max(V,1) 夹成 1.0")

    def test_fea_fos_reference_carries_the_gate_predicate(self):
        from scripts.wm_verifier import recompute
        state = recompute({"task": "fea_fos", "Sy": 355.0, "sigma": 300.0})
        self.assertIn("fos_gate", state,
                      "FOS>=1.5 的闸门谓词不在参照里，world_state_verified 就永远判不到它")
        # 字面以 wm_contract.KEY_SCHEMA 为唯一真源（pass/fail 短字面）；
        # 判分语义不变：FOS=235/198=1.187<1.5 必须判 fail。
        self.assertEqual(recompute({"task": "fea_fos", "Sy": 235.0, "sigma": 198.0})["fos_gate"],
                         "fail")

    def test_the_gate_predicate_is_actually_charged_when_wrong(self):
        from virtu_eval.graders import score_case
        from virtu_eval.runner import load_cases
        cases = {c["id"]: c for c in load_cases(
            str(ROOT / "data" / "benchmark" / "virtu_eval_phys_v1"), dims=["physics"])}
        case = cases["physics-e04"]
        self.assertEqual(score_case(case["gold"]["answer"], case["criteria"])["score"], 100.0)
        tampered = json.loads(case["gold"]["answer"])
        tampered["world_state"]["fos_gate"] = "FAIL"
        bad = score_case(json.dumps(tampered, ensure_ascii=False), case["criteria"])
        gate = [c for c in bad["criteria"] if c["key"] == "reproduced_by_solver"][0]
        self.assertFalse(gate["passed"], "改错闸门谓词仍然通过 ⇒ fos_gate 名义上 graded 实则无人判")

    def test_every_case_set_still_scores_its_own_gold(self):
        from virtu_eval.validate_cases import validate
        for case_dir in ("data/benchmark/virtu_eval_v1", "data/benchmark/virtu_eval_phys_v1",
                         "data/benchmark/virtu_eval_cl_v1"):
            problems, _ = validate(str(ROOT / case_dir))
            self.assertFalse(problems, f"{case_dir}: " + "; ".join(problems[:4]))


if __name__ == "__main__":
    unittest.main()
