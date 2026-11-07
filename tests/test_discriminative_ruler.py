# -*- coding: utf-8 -*-
"""Falsification pins for the discriminative-case lever (2026-11-06).

Two scripts are under test, and both must be *capable of going red*:

  scripts/moe14b_build_discriminative_cases.py  — per-slot criteria builder. Its P2 gate is the
      reason it exists: substring graders (regex_any/literal_all) give 100/100 to `flange_X`
      when gold is `flange`, so a "finer" criterion set built from them is fake granularity.
  scripts/moe14b_rescore_discriminative.py      — offline re-score. It must refuse when the
      case files are byte-identical (nothing was changed) or when both arms are the same model.
"""
import importlib.util
import hashlib
import json
import os
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load(name, relpath):
    spec = importlib.util.spec_from_file_location(name, ROOT / relpath)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


builder = _load("disc_builder", "scripts/moe14b_build_discriminative_cases.py")
rescore = _load("disc_rescore", "scripts/moe14b_rescore_discriminative.py")

GOLD_TOOL = "cadcam_solidworks_model"
GOLD_ARGS = {"action": "execute_vba", "part_name": "flange", "timeout_s": 40,
             "retries": 3, "dry_run": False}


def case(cid, criteria=None):
    return {"id": cid, "dimension": "toolcall", "tier": "medium", "language": "zh",
            "prompt": f"请调用工具完成 {cid}，输出 JSON。",
            "gold": {"answer": json.dumps({"tool": GOLD_TOOL, "arguments": GOLD_ARGS},
                                          ensure_ascii=False)},
            "criteria": criteria or [{"type": "json_object", "required_keys": ["tool", "arguments"],
                                      "key": "JSON"},
                                     {"type": "literal_all",
                                      "values": [GOLD_TOOL, "execute_vba"], "key": "要素"}]}


class TestBuilder(unittest.TestCase):
    def test_rebuilt_criteria_give_partial_credit_on_exact_value_change(self):
        c = case("x1")
        new, info = builder.build_one(c)
        self.assertIsNotNone(new, f"应能按槽拆分：{info}")
        self.assertGreaterEqual(len(new["criteria"]), builder.MIN_CRITERIA)
        self.assertTrue(all(v > 0 for v in new["discriminative"]["perturbation_scores"].values()))
        self.assertTrue(all(v < 100 for v in new["discriminative"]["perturbation_scores"].values()))

    def test_substring_grader_would_have_been_a_fake_granularity(self):
        """植入坏样本：用全文子串判据描述同一个槽 ⇒ 改值后仍满分 ⇒ P2 必须拦下。

        这正是本构造器第一版踩到的坑（regex_any + re.escape 匹配 flange_X 里的 flange）。
        """
        c = case("x2")
        c["criteria"] = [{"type": "regex_any", "patterns": ["flange"], "key": "参数:part_name"}]
        resp = json.dumps({"tool": GOLD_TOOL,
                           "arguments": dict(GOLD_ARGS, part_name="flange_X")}, ensure_ascii=False)
        from virtu_eval.graders import score_case
        self.assertEqual(score_case(resp, c["criteria"])["score"], 100.0,
                         "子串判据对改值给满分 —— 这条断言就是在证明『它不可用』")
        # 拆细版必须判红
        new, _ = builder.build_one(case("x2"))
        from virtu_eval.graders import score_case as sc
        self.assertLess(sc(resp, new["criteria"])["score"], 100.0,
                        "拆细后同一错误响应必须掉分，否则粒度是假的")

    def test_prompt_containing_gold_is_not_rebuilt(self):
        c = case("x3")
        c["prompt"] = "不要调用工具，输出 JSON：" + c["gold"]["answer"]
        new, info = builder.build_one(c)
        self.assertIsNone(new)
        self.assertTrue(info.get("leaky_by_design"))

    def test_non_toolcall_gold_is_skipped_not_guessed(self):
        c = case("x4")
        c["gold"]["answer"] = "答案是 42"
        new, info = builder.build_one(c)
        self.assertIsNone(new)
        self.assertIn("无法按槽拆分", info["why"])

    def test_end_to_end_refuses_empty_case_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "toolcall.jsonl"
            src.write_text("", encoding="utf-8")
            rc = subprocess.run([sys.executable, str(ROOT / "scripts"
                                                    / "moe14b_build_discriminative_cases.py"),
                                 "--in", str(src), "--out", str(Path(tmp) / "o.jsonl"),
                                 "--receipt", str(Path(tmp) / "r.json")],
                                capture_output=True, text=True, encoding="utf-8", errors="replace")
            self.assertNotEqual(rc.returncode, 0, "空用例文件不得算构造成功")


class TestRescore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.gold_resp = json.dumps({"tool": GOLD_TOOL, "arguments": GOLD_ARGS},
                                    ensure_ascii=False)
        self.bad_resp = json.dumps({"tool": GOLD_TOOL,
                                    "arguments": dict(GOLD_ARGS, part_name="wrong")},
                                   ensure_ascii=False)

    def tearDown(self):
        self.tmp.cleanup()

    def _leg(self, name, scores, responses, served):
        d = self.dir / name
        d.mkdir(parents=True, exist_ok=True)
        with open(d / "raw.jsonl", "w", encoding="utf-8") as f:
            for cid, sc in scores.items():
                f.write(json.dumps({"case_id": cid, "dimension": "toolcall", "score": sc,
                                    "response": responses[cid], "verdict": "pass" if sc else "fail",
                                    "max_tokens": 256,
                                    "gen": {"served_model": served, "tools_requested": True}}) + "\n")
        return str(d)

    def _case_files(self, cases_old, cases_new):
        po, pn = self.dir / "old.jsonl", self.dir / "new.jsonl"
        po.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in cases_old),
                      encoding="utf-8")
        pn.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in cases_new),
                      encoding="utf-8")
        return str(po), str(pn)

    def run_rescore(self, a, b, old, new):
        out = str(self.dir / "r.json")
        rc = subprocess.run([sys.executable, str(ROOT / "scripts" / "moe14b_rescore_discriminative.py"),
                             "--a", a, "--b", b, "--old", old, "--new", new,
                             "--dim", "toolcall", "--out", out],
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
        return rc, (json.load(open(out, encoding="utf-8")) if Path(out).exists() else None)

    def test_identical_case_files_are_rejected(self):
        cases = [case(f"c{i}") for i in range(8)]
        po, _ = self._case_files(cases, cases)
        scores = {c["id"]: 50.0 for c in cases}
        resp = {c["id"]: self.gold_resp for c in cases}
        a = self._leg("a", scores, resp, "arm-a:v1")
        b = self._leg("b", scores, resp, "arm-b:v1")
        rc, doc = self.run_rescore(a, b, po, po)
        self.assertEqual(rc.returncode, 4, f"新旧题面同字节时必须判红：{rc.stderr}")
        self.assertIn("Q4", rc.stderr)

    def test_same_served_model_arms_are_rejected(self):
        cases_old = [case(f"c{i}") for i in range(8)]
        cases_new = []
        for c in cases_old:
            n, _ = builder.build_one(c)
            cases_new.append(n or c)
        po, pn = self._case_files(cases_old, cases_new)
        scores = {c["id"]: 50.0 for c in cases_old}
        resp = {c["id"]: self.gold_resp for c in cases_old}
        a = self._leg("a", scores, resp, "same:model")
        b = self._leg("b", scores, resp, "same:model")
        rc, doc = self.run_rescore(a, b, po, pn)
        self.assertEqual(rc.returncode, 4, "两臂同一模型 ⇒ 配对无意义，必须判红")

    def test_toolsless_dim_is_refused_instead_of_reporting_perfect_agreement(self):
        """植入坏样本：两臂都从未发 tools ⇒ 必须判红，不得印成 σ(Δ)=0 的"完全一致"。

        旧版脚本就在这上面产出过一条假结论（knowledge 批腿的 toolcall 维 ±0.0）。
        """
        cases_old = [case(f"c{i}") for i in range(8)]
        cases_new = [builder.build_one(c)[0] or c for c in cases_old]
        po, pn = self._case_files(cases_old, cases_new)
        scores = {c["id"]: 100.0 for c in cases_old}
        resp = {c["id"]: self.gold_resp for c in cases_old}

        def leg(name):
            d = self.dir / name
            d.mkdir(parents=True, exist_ok=True)
            with open(d / "raw.jsonl", "w", encoding="utf-8") as f:
                for cid in scores:
                    f.write(json.dumps({"case_id": cid, "dimension": "toolcall",
                                        "score": scores[cid], "response": resp[cid],
                                        "verdict": "pass", "max_tokens": 256,
                                        "gen": {"served_model": name + ":v1",
                                                "tools_requested": False}}) + "\n")
            return str(d)

        rc, doc = self.run_rescore(leg("arm_a"), leg("arm_b"), po, pn)
        self.assertEqual(rc.returncode, 4, f"未发 tools 的 toolcall 维必须判红：{rc.stderr}")
        self.assertIn("Q5", rc.stderr)

    def test_unattributable_row_is_dropped_from_pairing(self):
        cases_old = [case(f"c{i}") for i in range(8)]
        cases_new = [builder.build_one(c)[0] or c for c in cases_old]
        po, pn = self._case_files(cases_old, cases_new)
        scores = {c["id"]: 50.0 for c in cases_old}
        resp = {c["id"]: self.gold_resp for c in cases_old}
        a = self._leg("a", scores, resp, "arm-a:v1")
        b = self._leg("b", scores, resp, "arm-b:v1")
        with open(Path(b) / "raw.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"case_id": "c0", "dimension": "toolcall", "score": 0.0,
                                "response": "", "verdict": "empty_response", "max_tokens": 256,
                                "gen": {"served_model": "", "tools_requested": True}}) + "\n")
        rc, doc = self.run_rescore(a, b, po, pn)
        self.assertEqual(rc.returncode, 0, rc.stdout + rc.stderr)
        self.assertIn("c0", doc["dropped_unattributable"]["B"])
        self.assertNotIn("c0", [r["case_id"] for r in doc["per_case"]],
                         "不可归因记录不得参与重打分")

    def test_rebuilt_criteria_change_scores_for_wrong_argument(self):
        """A/B 只差一个参数值：旧判据两边同分（σ 无信息），拆细后必须分出高下。"""
        cases_old = [case(f"c{i}") for i in range(8)]
        cases_new = [builder.build_one(c)[0] or c for c in cases_old]
        po, pn = self._case_files(cases_old, cases_new)
        resp_a = {c["id"]: self.gold_resp for c in cases_old}
        resp_b = {c["id"]: self.bad_resp for c in cases_old}
        # 旧腿的分数：子串判据下两者都算对 ⇒ 都记 100
        scores = {c["id"]: 100.0 for c in cases_old}
        a = self._leg("a", scores, resp_a, "arm-a:v1")
        b = self._leg("b", scores, resp_b, "arm-b:v1")
        rc, doc = self.run_rescore(a, b, po, pn)
        self.assertEqual(rc.returncode, 0, f"{rc.stdout}\n{rc.stderr}")
        self.assertEqual(doc["paired_old_criteria"]["discordant"], "0/8",
                         "旧判据下 B 的错误逃过检测")
        self.assertEqual(doc["paired_old_criteria"]["mean_delta"], 0.0,
                         "旧判据看不见 part_name 改值 ⇒ Δ̄ 必为 0（瞎）")
        self.assertLess(doc["paired_new_criteria"]["mean_delta"], 0.0,
                        "拆细后同一批响应必须量化出 B 的损失（Δ̄ 从 0 变成负）")
        self.assertEqual(doc["paired_new_criteria"]["sigma_delta"], 0.0,
                         "8 份同内容题的 Δ 全同 ⇒ σ(Δ)=0 是尺子完全可复现，不是失效")
        self.assertTrue(all(r["new_b"] < 100 for r in doc["per_case"] if r["rebuilt"]))

    def test_unrebuilt_case_keeps_its_score_verbatim(self):
        """没拆成功的题必须原样保留旧分数 —— 不许让"部分题被拆"伪装成全体变化。"""
        cases_old = [case(f"c{i}") for i in range(8)]
        cases_new = [dict(c, discriminative=None) for c in cases_old]   # 全未拆
        po, pn = self._case_files(cases_old, cases_new)
        scores = {c["id"]: 33.0 for c in cases_old}
        resp = {c["id"]: self.gold_resp for c in cases_old}
        a = self._leg("a", scores, resp, "arm-a:v1")
        b = self._leg("b", scores, resp, "arm-b:v1")
        rc, doc = self.run_rescore(a, b, po, pn)
        self.assertEqual(rc.returncode, 0, rc.stdout + rc.stderr)
        self.assertEqual(doc["paired_new_criteria"]["sigma_delta"], 0.0)
        self.assertEqual(doc["case_files"]["new"]["n_cases_rebuilt"], 0)
        self.assertNotIn("下降", doc["verdict"], "没拆成任何一题时不得输出『杠杆有效』的结论")
        self.assertEqual(doc["discordance_mechanism"]["discordant_cases"], 0)

    def test_verdict_does_not_claim_granularity_is_irrelevant_when_discords_are_unrebuilt(self):
        """机理护栏：分歧题全在"没被拆细"的题上时，σ(Δ) 不变不得被写成"粒度无关"。

        这是实测到的情形（随机门 vs 正交门带 tools：σ(Δ)=8.46 纹丝不动）。
        """
        cases_old = [case(f"c{i}") for i in range(8)]
        cases_new = []
        for i, c in enumerate(cases_old):
            if i < 4:
                n, _ = builder.build_one(c)
                cases_new.append(n or c)
            else:
                cases_new.append(c)      # 后 4 题不拆
        po, pn = self._case_files(cases_old, cases_new)
        resp_a = {c["id"]: self.gold_resp for c in cases_old}
        resp_b = {c["id"]: self.gold_resp for c in cases_old}
        # 让分歧只发生在"没拆"的题上：前 4 题两臂同分，后 4 题差 100
        scores_a = {c["id"]: 100.0 for c in cases_old}
        scores_b = dict(scores_a)
        for i in range(4, 8):
            scores_b[f"c{i}"] = 0.0
        a = self._leg("a", scores_a, resp_a, "arm-a:v1")
        b = self._leg("b", scores_b, resp_b, "arm-b:v1")
        rc, doc = self.run_rescore(a, b, po, pn)
        self.assertEqual(rc.returncode, 0, f"{rc.stdout}\n{rc.stderr}")
        m = doc["discordance_mechanism"]
        self.assertEqual(m["discordant_cases"], 4)
        self.assertEqual(m["discordant_among_rebuilt"], 0)
        self.assertIn("不构成", doc["verdict"])
        self.assertNotIn("粒度不是", doc["verdict"], "未检验到的东西不得写成否证")


MULTI_DIR = ROOT / "data" / "benchmark" / "virtu_eval_v2_disc_multislot"
MULTI_CASES = ROOT / "runs" / "moe14b_synth_multislot_cases.json"


def _load_synth():
    spec = importlib.util.spec_from_file_location(
        "disc_synth", ROOT / "scripts" / "moe14b_synth_multislot_cases.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestSynthMultiSlot(unittest.TestCase):
    """合成题单的护栏。两条都是本轮真实踩过的坑，不是想象出来的。"""

    @unittest.skipUnless(MULTI_CASES.exists(), "需要先跑合成器")
    def test_output_file_name_is_harness_loadable(self):
        """坑：runner 的 load_cases 用**文件名**判 dimension。

        第一版把合成族写成 toolcall_multi.jsonl，同一目录立刻 ValueError 打崩脚手架；
        腿 pointed at that dir 会直接起不来。文件名必须是 <dim>.jsonl。
        """
        from virtu_eval.runner import load_cases
        cases = load_cases(str(MULTI_DIR), dims=["toolcall"])
        self.assertEqual(len(cases), json.load(open(MULTI_CASES, encoding="utf-8"))["n_cases"])
        self.assertTrue(all(c["dimension"] == "toolcall" for c in cases))
        self.assertTrue(all(len(c["criteria"]) >= 5 for c in cases),
                        "S2：不足 5 条判据的题不该进题单")

    def test_value_absent_from_prompt_is_rejected_as_unfair(self):
        """S3 公平性：gold 里某个参数值没写进题面 ⇒ 该值靠猜，必须拒收。"""
        synth = _load_synth()
        c = case("d-fair")
        c["prompt"] = "请调用工具完成操作，输出 JSON。"      # 故意不含任何参数值
        crit, why = synth._fit_and_check(
            c, GOLD_TOOL, "execute_vba", {}, [GOLD_TOOL, "cadcam_vericut_simulate"])
        self.assertIsNone(crit)
        self.assertIn("S3", why)

    def test_uniform_weights_are_rejected_by_routing_share_gate(self):
        """突变样本：把参数权重抬到与路由同级 ⇒ 路由不再占大头 ⇒ S5b 必须拦。"""
        synth = _load_synth()
        saved_p, saved_r = synth.PARAM_WEIGHT, synth.ROUTING_WEIGHT
        try:
            synth.PARAM_WEIGHT, synth.ROUTING_WEIGHT = 3.0, 3.0
            c = case("d-weight")
            crit, why = synth._fit_and_check(
                c, GOLD_TOOL, "execute_vba", {}, [GOLD_TOOL, "cadcam_vericut_simulate"])
            self.assertIsNone(crit, "路由判据占比 <0.5 时不得收题，否则误路由仍得高分")
            self.assertIn("不测路由", why)
        finally:
            synth.PARAM_WEIGHT, synth.ROUTING_WEIGHT = saved_p, saved_r

    def test_misroute_neighbour_must_lose_more_than_half(self):
        """整条路由走偏（换工具并用它自己的动作）必须掉进中间带，不是 83–90 分。

        题面用生产路径 make_case 生成，保证"值都写在题面"这条前提成立 —— 否则
        S3 会先把题拒掉，测不到中间带。
        """
        synth = _load_synth()
        rng = random.Random(synth.SEED)
        props = {"action": {"type": "string", "enum": ["execute_vba", "model_flange"]},
                 "part_name": {"type": "string"}, "timeout_s": {"type": "number"},
                 "retries": {"type": "integer"}, "dry_run": {"type": "boolean"}}
        c, info = synth.make_case(GOLD_TOOL, "execute_vba", props, rng, 1)
        self.assertIsNotNone(c, f"生产路径应能出题：{info}")
        crit, why = synth._fit_and_check(
            c, GOLD_TOOL, "execute_vba", props,
            [GOLD_TOOL, "cadcam_vericut_simulate", "cadcam_nx_journal"])
        self.assertIsNotNone(crit, f"该题应通过全部检查：{why}")
        vals = list(why["neigh"].values())
        self.assertTrue(vals, "没有近邻误路由样本 ⇒ 这道题没被测到中间带")
        for v in vals:
            self.assertLessEqual(v, synth.NEIGHBOUR_MAX_SCORE,
                                 f"误路由仍得 {v} 分：路由不是考点，题面在奖励转录")
            self.assertGreaterEqual(v, synth.NEIGHBOUR_MIN_SCORE)

    def test_receipt_sha_binds_the_case_file(self):
        """题单必须可归因：收据里的 out_sha256 要等于文件字节，否则下次跑的就不是这批题。"""
        rec = json.load(open(MULTI_CASES, encoding="utf-8"))
        path = Path(rec["out_file"])
        self.assertTrue(path.exists(), f"收据指向的题单不存在：{path}")
        self.assertEqual(_sha256(path), rec["out_sha256"])
        self.assertIn("arm_tools_sha256", rec, "S1：必须记录用的是哪个臂的工具面")


def _sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


if __name__ == "__main__":
    unittest.main(verbosity=2)
