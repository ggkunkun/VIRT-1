"""The measured tool surface must equal the runtime tool surface, or say so out loud.

Measured 2026-11-05: `virtu_eval/arms.json` shipped 10 hand-copied `cadcam_*` schemas while
`bridges/tool_calling_specs.py` registers 14, and **no** gold or criterion in the 240-case
board mentioned the four newest tools (`cadcam_extreme_chain`, `cadcam_universal_geometry`,
`cadcam_cae_stress_analysis`, `cadcam_sheetmetal_nest`). The 0.18-weighted toolcall dimension
was therefore routing a tool list the product no longer offers. Widening the schema alone
would have moved the number without adding evidence, so `virtu_eval_cl_v1/toolrouting.jsonl`
came first and this gate pins both sides.

2026-11-13 (audit P1-1, option A): the declared surface was 20 while the graded surface was
16 and `arms.json` advertised 16. `cadcam_feature_ops` is real CAD capability and was given
four routing cases (board n 30 -> 34); the three internet tools were demoted to
`INTERNAL_TOOL_DEFINITIONS` because search/fetch/absorb results depend on the network at call
time and therefore have no deterministic oracle. Surface: 20 declared -> 17 declared ==
17 graded == 17 injected by `arms.json`.
"""
import io
import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from virtu_eval import tool_schema  # noqa: E402
from virtu_eval.validate_cases import expected_mix, validate  # noqa: E402

CL_DIR = ROOT / "data" / "benchmark" / "virtu_eval_cl_v1"
V1_DIR = ROOT / "data" / "benchmark" / "virtu_eval_v1"
ALLOWED_STATUS = {"measured", "partial", "routing_measured_result_unmeasurable"}


class TestRuntimeRegistryIsTheSource(unittest.TestCase):
    def test_registry_parses_without_importing_the_bridge(self):
        tools = tool_schema.runtime_tools()
        self.assertEqual(len(tools), 17, "运行时注册表条数变了，测评面要跟着改")
        for tool in tools:
            fn = tool["function"]
            self.assertTrue(fn["description"].strip(), fn["name"])
            self.assertEqual(fn["parameters"]["type"], "object", fn["name"])

    def test_harness_never_advertises_a_tool_the_runtime_lacks(self):
        runtime = set(tool_schema.runtime_tool_names())
        extra = tool_schema.eval_schema_tool_names() - runtime
        self.assertFalse(extra, f"评测 schema 里出现了运行时不存在的工具：{sorted(extra)}")

    def test_harness_advertises_the_whole_declared_surface(self):
        """反向缺口同样致命：板上有用例、臂里没 schema，等于结构性死分。"""
        runtime = set(tool_schema.runtime_tool_names())
        missing = runtime - tool_schema.eval_schema_tool_names()
        self.assertFalse(missing, f"运行时宣告了但 arms.json 没注入：{sorted(missing)}")

    def test_every_runtime_tool_is_gradable(self):
        self.assertEqual(tool_schema.uncovered_runtime_tools(), [],
                         "有运行时工具没有任何 gold/criterion 覆盖，能力分不得声称覆盖六软件")

    def test_gate_is_not_vacuous_without_the_new_cases(self):
        """Point the same detector at the old board only - it must go red on 7 tools."""
        uncovered = tool_schema.uncovered_runtime_tools(case_dirs=(V1_DIR,))
        self.assertEqual(len(uncovered), 7, uncovered)
        self.assertIn("cadcam_cae_stress_analysis", uncovered)
        self.assertIn("cadcam_step_reverse", uncovered)
        self.assertIn("cadcam_assembly_build", uncovered)
        self.assertIn("cadcam_feature_ops", uncovered)


class TestClosedLoopCaseSetIsValid(unittest.TestCase):
    def test_gold_answers_all_score_100_and_mix_is_legal(self):
        problems, summary = validate(str(CL_DIR))
        self.assertFalse(problems, problems)
        stats = summary["toolrouting"]
        self.assertEqual(stats["n"], 34)
        self.assertEqual(stats["easy"], 10)
        self.assertEqual(stats["medium"] + stats["hard"], 24)
        for tier, target in zip(("easy", "medium", "hard"), expected_mix(stats["n"])):
            self.assertLessEqual(abs(stats[tier] - target), 1, (tier, stats))

    def test_routing_cases_reach_all_six_previously_ungradeable_tools(self):
        text = (CL_DIR / "toolrouting.jsonl").read_text(encoding="utf-8")
        for tool in ("cadcam_extreme_chain", "cadcam_universal_geometry",
                     "cadcam_cae_stress_analysis", "cadcam_sheetmetal_nest",
                     "cadcam_step_reverse", "cadcam_assembly_build",
                     "cadcam_feature_ops"):
            self.assertGreaterEqual(text.count(tool), 4, f"{tool} 覆盖太薄")


class TestMeasurabilityLedger(unittest.TestCase):
    def test_every_closed_loop_stage_declares_a_ruler_or_an_absence(self):
        ledger = json.loads((CL_DIR / "COVERAGE.json").read_text(encoding="utf-8"))
        stages = ledger["stages"]
        self.assertGreaterEqual(len(stages), 8)
        for name, entry in stages.items():
            self.assertIn(entry["status"], ALLOWED_STATUS, name)
            self.assertTrue(entry.get("ruler"), name)
            self.assertTrue(entry.get("caveat"), f"{name} 没有说明这把尺量不到什么")

    def test_ledger_admits_what_cannot_be_measured(self):
        """A all-green ledger would be the false-green this file exists to prevent."""
        stages = json.loads((CL_DIR / "COVERAGE.json").read_text(encoding="utf-8"))["stages"]
        unmeasurable = [k for k, v in stages.items()
                        if v["status"] == "routing_measured_result_unmeasurable"]
        self.assertGreaterEqual(len(unmeasurable), 3, unmeasurable)
        for stage in ("sheet_metal_true_shape_nesting", "virtual_machining_autodiff",
                      "sscnc_panel_touch_off"):
            self.assertIn(stage, unmeasurable,
                          f"{stage} 的结果级判据已存在？没有就把状态改回 unmeasurable，别报能力分")


if __name__ == "__main__":
    unittest.main()
