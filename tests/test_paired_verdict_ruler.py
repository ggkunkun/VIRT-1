# -*- coding: utf-8 -*-
"""Regression pin for the paired ruler added on 2026-11-06.

The mistake this prevents: `delta_verdict`'s band = 1.96·σ·√(2/n) uses the *re-ask* σ of one
arm, which is not the dispersion of a two-arm paired mean difference. On real data tonight
that mistake turned a Δ̄ of −5.56 with paired σ(Δ)=26.38 into "净增益", because the re-ask band
(±4.47) is smaller than the correct paired CI (±9.44). Every claim of the form "arm B gains
X points" must clear BOTH the paired CI and the re-ask floor.
"""
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SPEC = importlib.util.spec_from_file_location("moe14b_ab_verdict",
                                              ROOT / "scripts" / "moe14b_ab_verdict.py")
verdict_mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verdict_mod)


# 8 对配对复测：7 对 Δ=0、1 对 Δ=25 ⇒ stdev(|Δ|) 正好 8.84，与今晚实测同量级
NOISE_RECORDS = ([{"case_id": f"knowledge-r{i}", "scores": [60.0, 60.0]} for i in range(7)]
                 + [{"case_id": "knowledge-r7", "scores": [100.0, 75.0]}])

REAL_A = ROOT / "runs" / "moe14b_ab_tools2" / "moe14b_gate_random"
REAL_B = ROOT / "runs" / "moe14b_ab_tools2" / "dense_merged_v2_p11435"


def write_run(dirpath, scores, served="model:placeholder", tools_requested=True):
    """scores: {case_id: score} on the toolcall dimension.

    `served` is written into every record because the verdict script takes the arm's identity
    from the per-response served_model, never from the directory name — that is the point.
    `tools_requested` mirrors the runner's record of whether the tools schema was actually sent;
    a toolcall dimension scored without it is a vacuous measurement (gate I4).
    """
    Path(dirpath).mkdir(parents=True, exist_ok=True)
    with open(Path(dirpath) / "raw.jsonl", "w", encoding="utf-8") as f:
        for cid, sc in scores.items():
            f.write(json.dumps({"case_id": cid, "dimension": "toolcall", "tier": "easy",
                                "score": sc, "verdict": "pass" if sc else "fail_all_criteria",
                                "max_tokens": 256,
                                "gen": {"completion_tokens": 100, "served_model": served,
                                        "tools_requested": tools_requested}}) + "\n")


def write_run_unnamed(dirpath, scores):
    """Same as write_run but with NO served_model — the state the 11-06 legs were actually in."""
    Path(dirpath).mkdir(parents=True, exist_ok=True)
    with open(Path(dirpath) / "raw.jsonl", "w", encoding="utf-8") as f:
        for cid, sc in scores.items():
            f.write(json.dumps({"case_id": cid, "dimension": "toolcall", "tier": "easy",
                                "score": sc, "verdict": "pass" if sc else "fail_all_criteria",
                                "max_tokens": 256, "gen": {"completion_tokens": 100}}) + "\n")


class TestPairedRuler(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=str(ROOT / "runs" / "eval")
                                               if (ROOT / "runs" / "eval").exists() else str(ROOT))
        self.noise = Path(self.tmp.name) / "noise.json"
        self.noise.write_text(json.dumps({"records": NOISE_RECORDS}), encoding="utf-8")
        for tag in ("runs_a", "runs_b"):
            d = Path(self.tmp.name) / tag
            d.mkdir(exist_ok=True)
            (d / "manifest.json").write_text(json.dumps({"run_id": "fixture"}), encoding="utf-8")
        self.a = str(Path(self.tmp.name) / "runs_a")
        self.b = str(Path(self.tmp.name) / "runs_b")

    def tearDown(self):
        self.tmp.cleanup()

    def judge(self, a, b):
        out = str(Path(self.tmp.name) / "v.json")
        rc = subprocess.run([sys.executable, str(ROOT / "scripts" / "moe14b_ab_verdict.py"),
                             "--a", a, "--b", b, "--noise", str(self.noise), "--out", out,
                             "--label", "fixture"], capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(rc.returncode, 0, f"{rc.stdout}\n{rc.stderr}")
        return json.load(open(out, encoding="utf-8"))

    def test_all_identical_scores_is_flagged_as_no_information(self):
        write_run(self.a, {f"c{i}": 50.0 for i in range(30)}, served="arm-a:v1")
        write_run(self.b, {f"c{i}": 50.0 for i in range(30)}, served="arm-b:v1")
        v = self.judge(self.a, self.b)["per_dimension"][0]
        self.assertFalse(v["attributable"])
        self.assertEqual(v["discordant_cases"], "0/30")
        self.assertIn("不含任何判别信息", v["statement"])

    def test_unanimous_shift_is_attributable(self):
        write_run(self.a, {f"c{i}": 40.0 for i in range(30)}, served="arm-a:v1")
        write_run(self.b, {f"c{i}": 90.0 for i in range(30)}, served="arm-b:v1")
        v = self.judge(self.a, self.b)["per_dimension"][0]
        self.assertTrue(v["attributable"], "每题都同向移动 ⇒ σ(Δ)=0，这是真信号，不得判成噪声")
        self.assertIn("净胜", v["statement"])
        self.assertEqual(v["discordant_cases"], "30/30")

    def test_reask_band_alone_is_not_enough(self):
        # 复测地板 ±4.47；构造"只有 2/30 翻转但翻得很猛"的例子：Δ̄≈5.56 越过地板，
        # 而配对 σ(Δ)≈21 ⇒ CI ±7.6 含 0 —— 旧公式会把它判成"净增益"，正是今晚犯的错
        a = {f"c{i}": 0.0 for i in range(30)}
        b = dict(a)
        b["c0"] = 83.33
        b["c1"] = 83.33
        write_run(self.a, a, served="arm-a:v1")
        write_run(self.b, b, served="arm-b:v1")
        v = self.judge(self.a, self.b)["per_dimension"][0]
        self.assertGreater(abs(v["delta"]), v["band_reask"],
                           "此例必须满足 |Δ̄| > 复测地板，否则它测不出旧公式的错")
        self.assertLess(abs(v["delta"]), v["band_paired"])
        self.assertEqual(v["discordant_cases"], "2/30")
        self.assertFalse(v["attributable"],
                         "结论由 2/30 题驱动、配对 CI 含 0 ⇒ 不得称为增益")

    def test_missing_common_case_ids_fails_loud(self):
        write_run(self.a, {"x1": 50.0}, served="arm-a:v1")
        write_run(self.b, {"y9": 50.0}, served="arm-b:v1")
        out = str(Path(self.tmp.name) / "v2.json")
        rc = subprocess.run([sys.executable, str(ROOT / "scripts" / "moe14b_ab_verdict.py"),
                             "--a", self.a, "--b", self.b, "--noise", str(self.noise),
                             "--out", out, "--label", "fixture"],
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertNotEqual(rc.returncode, 0, "题 id 配不上时必须拒绝出判定，不能算成 Δ=0")
        self.assertNotIn("INVALID_IDENTITY", (Path(out).read_text(encoding="utf-8", errors="replace")
                                              if Path(out).exists() else ""))

    def test_missing_run_dir_refuses(self):
        with self.assertRaises(SystemExit):
            verdict_mod.load_run(str(Path(self.tmp.name) / "does_not_exist"))

    def test_transport_error_rows_are_not_scored(self):
        d = Path(self.tmp.name) / "runs_c"
        write_run(d, {"c1": 100.0})
        with open(d / "raw.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"case_id": "c2", "dimension": "toolcall", "score": 0.0,
                                "verdict": "transport_error", "max_tokens": 256, "gen": {}}) + "\n")
        loaded = verdict_mod.load_run(str(d))
        self.assertEqual(loaded["n"]["toolcall"], 1, "传输错误不得占样本位")

    # ---- 身份闸（I0–I2）的反证：坏样本必须红，且红的原因是身份而不是分数 ----
    def test_same_served_model_two_dirs_refuses_verdict(self):
        """复现 2026-11-06 事故：两个目录名不同、内容其实是同一个模型服务出来的腿。

        分数差异再大也不得出判定 —— 那天四个标签被重指到同一 manifest，配对消融当场作废。
        """
        write_run(self.a, {f"c{i}": 20.0 for i in range(30)}, served="virtu-master:q4_0")
        write_run(self.b, {f"c{i}": 95.0 for i in range(30)}, served="virtu-master:q4_0")
        out = str(Path(self.tmp.name) / "v3.json")
        rc = subprocess.run([sys.executable, str(ROOT / "scripts" / "moe14b_ab_verdict.py"),
                             "--a", self.a, "--b", self.b, "--noise", str(self.noise),
                             "--out", out, "--label", "fixture"], capture_output=True,
                            text=True, encoding="utf-8", errors="replace")
        self.assertEqual(rc.returncode, 4, f"同模型双目录必须 GATE_FAILED：\n{rc.stdout}\n{rc.stderr}")
        self.assertIn('I2_arms_are_different_models": false', (rc.stderr or "") + (rc.stdout or ""))
        doc = json.load(open(out, encoding="utf-8"))
        self.assertEqual(doc["verdict"], "INVALID_IDENTITY")
        self.assertNotIn("per_dimension", doc, "身份不成立时不得留下任何可被引用的判定体")

    def test_missing_served_model_field_is_red_not_unknown_ok(self):
        """记录里没有 served_model ⇒ 判红，不得退化成"按目录名当作身份"。"""
        write_run_unnamed(self.a, {f"c{i}": 20.0 for i in range(30)})
        write_run_unnamed(self.b, {f"c{i}": 95.0 for i in range(30)})
        ident = verdict_mod.build_identity(self.a, self.b, str(self.noise), ["toolcall"], {})
        self.assertFalse(ident["passed"])
        self.assertFalse(ident["identity_gates"]["I2_arms_are_different_models"],
                         "两侧都无身份时集合相等 ⇒ 必须判红")
        self.assertFalse(ident["identity_gates"]["I3_every_scored_row_attributable"])
        self.assertEqual(len(ident["unattributable_cases"]["A"]), 30)

    def test_unattributable_row_is_dropped_not_scored_as_failure(self):
        """一题响应空且无身份：默认零容忍判红；显式放宽后必须"剔除出配对"而不是记 0 分。

        2026-11-06 稠密臂 toolcall-m14 正是这种记录（当时该标签 manifest 缺失），
        它被当作能力失败计进了 Δ̄，这是配对数字里的方向性污染。
        """
        write_run(self.a, {f"c{i}": 60.0 for i in range(30)}, served="arm-a:v1")
        scores_b = {f"c{i}": 60.0 for i in range(30)}
        write_run(self.b, scores_b, served="arm-b:v1")
        with open(Path(self.b) / "raw.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"case_id": "c99", "dimension": "toolcall", "score": 0.0,
                                "verdict": "empty_response", "max_tokens": 256,
                                "gen": {"served_model": "", "content_was_empty": True}}) + "\n")
        # 同步给 A 加同一题（同分），确保"剔除"针对的是不可归因题而不是配不上的题
        with open(Path(self.a) / "raw.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"case_id": "c99", "dimension": "toolcall", "score": 60.0,
                                "verdict": "pass", "max_tokens": 256,
                                "gen": {"served_model": "arm-a:v1"}}) + "\n")

        strict = subprocess.run([sys.executable, str(ROOT / "scripts" / "moe14b_ab_verdict.py"),
                                 "--a", self.a, "--b", self.b, "--noise", str(self.noise),
                                 "--out", str(Path(self.tmp.name) / "v4.json"),
                                 "--label", "fixture"], capture_output=True, text=True,
                                encoding="utf-8", errors="replace")
        self.assertEqual(strict.returncode, 4, "有不可归因的计分题时默认必须判红")
        self.assertIn('I3_every_scored_row_attributable": false',
                      (strict.stderr or "") + (strict.stdout or ""))

        relaxed = subprocess.run([sys.executable, str(ROOT / "scripts" / "moe14b_ab_verdict.py"),
                                  "--a", self.a, "--b", self.b, "--noise", str(self.noise),
                                  "--out", str(Path(self.tmp.name) / "v5.json"),
                                  "--max-unattributed", "1", "--label", "fixture"],
                                 capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(relaxed.returncode, 0, relaxed.stdout + relaxed.stderr)
        doc = json.load(open(Path(self.tmp.name) / "v5.json", encoding="utf-8"))
        self.assertEqual(doc["basis"], "measured_degraded", "放宽必须在口径上留痕")
        self.assertEqual(doc["identity"]["unattributable_cases"]["B"], ["c99"])
        self.assertEqual(doc["per_dimension"][0]["n"], 30,
                         "不可归因题不得占样本位：n 必须回到 30 而不是 31")
        self.assertEqual(doc["per_dimension"][0]["delta"], 0.0,
                         "剔除后两臂同分 ⇒ Δ 必须为 0，不能因一条 0 分记录虚报损失")

    def test_toolsless_toolcall_dimension_is_excluded_not_reported_as_agreement(self):
        """两臂都没发 tools 的 toolcall 维必须被剔出判定，绝不能显示成 σ(Δ)=0 的"一致"。

        2026-11-06 早先的 knowledge 腿正是这种数据：它的 toolcall 维在旧回执里写成
        "Δ̄=+0.00、0/30 题不同分"，读起来像两臂完全等价，实际是那批腿根本没调用工具面。
        """
        write_run(self.a, {f"c{i}": 40.0 for i in range(30)}, served="arm-a:v1",
                  tools_requested=False)
        write_run(self.b, {f"c{i}": 90.0 for i in range(30)}, served="arm-b:v1",
                  tools_requested=False)
        out = str(Path(self.tmp.name) / "v6.json")
        rc = subprocess.run([sys.executable, str(ROOT / "scripts" / "moe14b_ab_verdict.py"),
                             "--a", self.a, "--b", self.b, "--noise", str(self.noise),
                             "--out", out, "--label", "fixture"], capture_output=True,
                            text=True, encoding="utf-8", errors="replace")
        self.assertEqual(rc.returncode, 4,
                         f"唯一维度是空转 toolcall 时必须拒绝出判定：\n{rc.stdout}\n{rc.stderr}")
        doc = json.load(open(out, encoding="utf-8"))
        self.assertEqual(doc["verdict"], "NO_EVALUABLE_DIMENSION")
        self.assertIn("toolcall", doc["identity"]["toolsless_toolcall_dimensions"])
        self.assertEqual(doc["identity"]["tools_requested_rate"]["A"]["toolcall"], 0.0)

    def test_run_id_binds_evidence_bytes(self):
        """run_id 必须随证据字节变化：改一题分数 ⇒ 指纹变，同输入重算 ⇒ 指纹不变。"""
        write_run(self.a, {f"c{i}": 20.0 for i in range(30)}, served="arm-a:v1")
        write_run(self.b, {f"c{i}": 95.0 for i in range(30)}, served="arm-b:v1")
        i1 = verdict_mod.build_identity(self.a, self.b, str(self.noise), ["toolcall"], {})
        self.assertTrue(i1["passed"], json.dumps(i1["identity_gates"]))
        i2 = verdict_mod.build_identity(self.a, self.b, str(self.noise), ["toolcall"], {})
        self.assertEqual(i1["run_id"], i2["run_id"], "同字节重算必须得到同一 run_id")
        write_run(self.b, {f"c{i}": 96.0 for i in range(30)}, served="arm-b:v1")
        i3 = verdict_mod.build_identity(self.a, self.b, str(self.noise), ["toolcall"], {})
        self.assertNotEqual(i1["run_id"], i3["run_id"], "证据字节变了而指纹不变 ⇒ 归因是假的")
        self.assertEqual(len(i1["run_id"]), 16)


@unittest.skipUnless(REAL_A.exists() and REAL_B.exists(), "需要今晚的真实腿")
class TestTonightFlipIsNotAttributable(unittest.TestCase):
    """The claim published at 21:5x and retracted at 22:1x must never come back as a verdict."""

    def test_moe_vs_dense_toolcall_is_not_attributable(self):
        out = str(ROOT / "runs" / "moe14b_ab_paired_recheck.json")
        rc = subprocess.run([sys.executable, str(ROOT / "scripts" / "moe14b_ab_verdict.py"),
                             "--a", str(REAL_A), "--b", str(REAL_B),
                             "--noise", str(ROOT / "runs" / "moe14b_noise_probe.json"),
                             "--max-unattributed", "1",
                             "--out", out, "--label", "recheck"], capture_output=True,
                            text=True, encoding="utf-8", errors="replace")
        self.assertEqual(rc.returncode, 0, f"{rc.stdout}\n{rc.stderr}")
        doc = json.load(open(out, encoding="utf-8"))
        v = doc["per_dimension"][0]
        # 教训 1：配对 CI 必须是复测地板的两倍量级，否则"越过地板"会被误读成增益
        self.assertGreater(v["band_paired"], 1.8 * v["band_reask"],
                           f"配对带 {v['band_paired']} 未显著超过复测地板 {v['band_reask']}")
        self.assertFalse(v["attributable"], f"今晚实测应为不可判：{v['statement']}")
        # 教训 2：证据里那条无法归因的空响应必须被识别并剔除，不能当成能力失败
        self.assertEqual(doc["identity"]["unattributable_cases"]["B"], ["toolcall-m14"])
        self.assertEqual(v["n"], 29, "不可归因题被剔除后 n 应为 29")
        self.assertEqual(doc["basis"], "measured_degraded", "放宽零容忍必须在口径上留痕")
        self.assertEqual(len(doc["run_id"]), 16, "判定必须可归因到字节")


if __name__ == "__main__":
    unittest.main(verbosity=2)
