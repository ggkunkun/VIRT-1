"""P0-B 反证测试：发布闸门必须能被坏样本证伪，且有一条合法样本能通过。

对应 AGENTS.md §8 第 4 条："新增任何判据或门禁，同时提交『植入坏样本 ⇒ 必须红』
的反证测试。空匹配集、解析失败一律判红。" 本文件覆盖：

* 无 run_id / 标签名当 run_id / n=0 / evidence 不存在 / basis=measured 却无证据
  => ``publish_metrics`` 必须拒绝，且非法数值绝不落盘（受控路径也一样）；
* 空匹配集、JSON 解析失败 => ``audit_paths`` / ``--check`` 必须判红（退出码非 0）；
* 一条合法 Metric 能通过发布，并能被 ``--check`` 审过；
* ``run_domain_ab`` 的精确槽位判分必须证伪 ``flange -> flange_X`` 子串假阳性，
  空匹配集必须判红，且 grader_version 已变更（与历史分不可混用）。

全程只用临时目录与本地文件，不依赖网络、Ollama 服务或 GPU。
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from virtu_eval import publish as pub  # noqa: E402
from virtu_eval.provenance import Metric  # noqa: E402

RUN_ID = "a1b2c3d4e5f60718"  # 合法的 16 位 hex 内容指纹


class PublishGateRefusesBadSamples(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.evidence = self.root / "raw.jsonl"
        self.evidence.write_text(
            json.dumps({"case_id": "a", "dimension": "reasoning",
                        "verdict": "pass", "score": 100.0}) + "\n",
            encoding="utf-8")

    def _metric(self, **kw):
        base = dict(name="reasoning", value=70.0, basis="measured", n=2,
                    evidence=str(self.evidence), run_id=RUN_ID)
        base.update(kw)
        return Metric(**base)

    def _publish(self, items, name="out.json"):
        return pub.publish_metrics(items, self.root / name)

    def test_one_valid_metric_passes_and_is_auditable(self):
        payload = self._publish([self._metric()])
        self.assertEqual(payload["basis"], "measured")
        self.assertEqual(payload["n"], 2)
        self.assertTrue((self.root / "out.json").exists())
        # 发布产物本身也要能被 --check 审计通过（闭环，而不是只验输入）。
        self.assertEqual(pub.audit_paths([str(self.root / "out.json")]), [])

    def test_missing_run_id_is_refused(self):
        with self.assertRaises(ValueError):
            self._publish([self._metric(run_id=None)])

    def test_tag_name_or_short_or_non_hex_run_id_is_refused(self):
        # 标签名字符串、12 位前缀、大写、非 hex、非字符串 —— 全都不是内容指纹。
        for bad in ("virtu-v3-all90", "virtu-comprehensive:latest",
                    "3546c40f3ce8", "A" * 16, "g" * 16, "deadbeef",
                    1234567890123456):
            with self.subTest(run_id=bad):
                with self.assertRaises(ValueError):
                    self._publish([self._metric(run_id=bad)])

    def test_n_zero_is_refused(self):
        with self.assertRaises(ValueError):
            self._publish([self._metric(n=0)])

    def test_nonexistent_evidence_is_refused(self):
        with self.assertRaises(ValueError):
            self._publish([self._metric(evidence=str(self.root / "missing.jsonl"))])

    def test_measured_without_evidence_is_refused(self):
        with self.assertRaises(ValueError):
            self._publish([self._metric(evidence=None)])

    def test_illegal_basis_is_refused(self):
        with self.assertRaises(ValueError):
            self._publish([{"name": "x", "value": 1.0, "basis": "guessed",
                            "n": 2, "evidence": str(self.evidence), "run_id": RUN_ID}])

    def test_null_value_is_refused(self):
        # 没测要写「未测」，不能用 null 或 None 冒充分数。
        with self.assertRaises(ValueError):
            self._publish([self._metric(value=None)])

    def test_empty_metric_set_is_refused(self):
        with self.assertRaises(ValueError):
            self._publish([])

    def test_illegal_metric_never_lands_on_disk(self):
        # 无论目标是否受控，非法数值都不得落半个文件。
        dest = self.root / "benchmarks" / "evil.json"
        with self.assertRaises(ValueError):
            self._publish([self._metric(run_id="tag-name")], "benchmarks/evil.json")
        self.assertFalse(dest.exists())

    def test_controlled_paths_are_recognised(self):
        self.assertTrue(pub.is_controlled(ROOT / "benchmarks" / "report.json"))
        self.assertTrue(pub.is_controlled(ROOT / "checkpoints" / "PROVENANCE.json"))
        self.assertTrue(pub.is_controlled(ROOT / "README.md"))
        self.assertFalse(pub.is_controlled(self.root / "scratch.json"))

    def test_parse_failure_is_red(self):
        broken = self.root / "broken.json"
        broken.write_text("{not-json", encoding="utf-8")
        violations = pub.audit_paths([str(broken)])
        self.assertTrue(any("解析失败" in v for v in violations), violations)

    def test_empty_match_set_is_red(self):
        violations = pub.audit_paths([str(self.root / "no_such_dir")])
        self.assertTrue(any("空匹配集" in v for v in violations), violations)

    def test_check_cli_returns_nonzero_on_violations(self):
        broken = self.root / "broken.json"
        broken.write_text("{{{", encoding="utf-8")
        self.assertEqual(pub.main(["--check", "--paths", str(broken)]), 1)

    def test_check_cli_returns_zero_on_clean_payload(self):
        good = self.root / "clean.json"
        self._publish([self._metric()], "clean.json")
        self.assertEqual(pub.main(["--check", "--paths", str(good)]), 0)


class DomainABGraderIsFalsifiable(unittest.TestCase):
    """run_domain_ab 的判分器变更也要有反证，不依赖网络/Ollama。"""

    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location(
            "run_domain_ab_gate_probe", str(ROOT / "scripts" / "run_domain_ab.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        cls.mod = mod

    def test_flange_x_no_longer_scores_full(self):
        # README §26/§28：旧版子串匹配对 flange -> flange_X 仍给满分。
        case = {"id": "flange_probe", "must": [["flange"]]}
        self.assertEqual(self.mod.score("flange_X", case)[0], 0.0)
        self.assertEqual(self.mod.score("flange", case)[0], 100.0)

    def test_empty_match_set_is_red(self):
        with self.assertRaises(ValueError):
            self.mod.score("anything", {"id": "empty_must", "must": []})
        with self.assertRaises(ValueError):
            self.mod.score("anything", {"id": "empty_group", "must": [[]]})

    def test_grader_version_changed(self):
        self.assertNotEqual(self.mod.GRADER_VERSION, self.mod.PREVIOUS_GRADER_VERSION)
        _, detail = self.mod.score("flange", {"id": "x", "must": [["flange"]]})
        self.assertEqual(detail["grader_version"], self.mod.GRADER_VERSION)


if __name__ == "__main__":
    unittest.main()
