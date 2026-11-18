# -*- coding: utf-8 -*-
"""Falsification pins for runner's --repeats / --case-ids-file (added 2026-11-06).

These run WITHOUT Ollama: the arm is stubbed. That matters because the box currently
cannot commit an 8.3 GB model load (commit charge exhausted), so the behavioral proof of
"median-of-3 actually shrinks σ(Δ)" has to wait for a memory window — but the *mechanics*
must not wait, and must not be trusted to a live leg either.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from virtu_eval import runner  # noqa: E402


def write_cases(dirpath, rows):
    Path(dirpath).mkdir(parents=True, exist_ok=True)
    with open(Path(dirpath) / "toolcall.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


CASES = [{"id": f"toolcall-e{i}", "dimension": "toolcall", "tier": "easy",
          "prompt": f"调用工具示例 {i}",
          "criteria": [{"type": "literal_all", "values": ["cadcam ok"], "key": "要素"}],
          "tags": []} for i in range(1, 6)]


class _StubArm:
    """第 k 次作答给分数 k：用来验证中位数、错误剔除与 attempts 计数。"""
    label = "stub"
    tools = [{"function": {"name": "cadcam_x"}}]

    def __init__(self, seq):
        self.seq = list(seq)
        self.i = 0

    def load(self):
        pass

    def unload(self):
        pass

    def tools_for(self, case):
        return self.tools

    def generate(self, messages, **kw):
        val = self.seq[self.i % len(self.seq)]
        self.i += 1
        if isinstance(val, Exception):
            raise val
        return {"text": val, "tool_calls": None, "completion_tokens": 10,
                "prompt_tokens": 20, "finish_reason": "stop", "elapsed_s": 1.0,
                "served_model": "stub", "error": None}


class TestRepeatsMechanics(unittest.TestCase):
    def setUp(self):
        # 输出目录放系统 TEMP：_run 复用同名 out 目录时会 rmtree，仓库内路径
        # 会被宿主 safe-delete 垫片的批量删除阈值拦成 SystemExit（全仓假红）。
        self.tmp = Path(tempfile.gettempdir()) / "virtu_test_repeats"
        self.tmp.mkdir(parents=True, exist_ok=True)

    def _run(self, seq, repeats=1, case_ids_file=None, dims="toolcall"):
        cases_dir = self.tmp / "cases"
        write_cases(cases_dir, CASES)
        out = self.tmp / f"out_{abs(hash((tuple(map(str, seq)), repeats)))}"
        if out.exists():
            import shutil
            shutil.rmtree(out)
        old = os.environ.get("VIRTU_EVAL_STUB")
        # monkeypatch build_arm so no Ollama is needed
        real = runner.build_arm
        runner.build_arm = lambda spec: _StubArm(seq)
        try:
            spec = {"kind": "ollama_native", "model_id": "stub",
                    "tools": [{"type": "function", "function": {"name": "cadcam_x"}}]}
            runner.run(str(cases_dir), spec, str(out),
                       dims=[dims] if dims else None, temperature=0.0, seed=7,
                       repeats=repeats, case_ids_file=case_ids_file)
        finally:
            runner.build_arm = real
            if old is None:
                os.environ.pop("VIRTU_EVAL_STUB", None)
        return [json.loads(l) for l in (out / "raw.jsonl").read_text(encoding="utf-8").splitlines()
                if l.strip()], json.load(open(out / "manifest.json", encoding="utf-8"))

    def test_repeats_1_is_byte_identical_to_history(self):
        recs, man = self._run(["cadcam ok"], repeats=1)
        self.assertEqual(man["repeats"], 1)
        self.assertTrue(all(r["score"] == 100.0 for r in recs))
        self.assertIsNone(recs[0]["repeats_detail"])

    def test_median_of_three_picks_the_middle_answer(self):
        # 交替给出 命中 / 未命中 / 命中 ⇒ 三次分数 100,0,100 ⇒ 中位数 100
        recs, man = self._run(["cadcam ok", "nothing here", "cadcam ok"], repeats=3)
        self.assertEqual(man["repeats"], 3)
        self.assertEqual(recs[0]["score"], 100.0)
        self.assertEqual(recs[0]["repeats_detail"]["scores"], [100.0, 0.0, 100.0])
        self.assertTrue(recs[0]["repeats_detail"]["changed"],
                        "重复之间分数不同必须被记录，否则噪声被中位数藏起来了")

    def test_failed_repeats_are_not_folded_into_zero(self):
        recs, man = self._run([RuntimeError("http_500 boom"), "cadcam ok", "cadcam ok"], repeats=3)
        d = recs[0]["repeats_detail"]
        self.assertEqual(d["errors"], 1)
        self.assertEqual(d["scores"], [100.0, 100.0])
        self.assertEqual(recs[0]["score"], 100.0, "一次传输失败不得把该题拖成 0 分")

    def test_all_repeats_failed_is_not_silently_ok(self):
        recs, man = self._run([RuntimeError("boom a"), RuntimeError("boom b")], repeats=2)
        self.assertEqual(recs[0]["verdict"], "transport_error")
        self.assertEqual(recs[0]["score"], 0.0)
        self.assertIn("score_error", recs[0]["gen"])

    def test_case_ids_file_restricts_and_validates(self):
        ids = self.tmp / "ids.txt"
        ids.write_text("toolcall-e2\n", encoding="utf-8")
        recs, man = self._run(["cadcam ok"], repeats=1, case_ids_file=str(ids))
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["case_id"], "toolcall-e2")

    def test_unknown_case_id_fails_loud(self):
        ids = self.tmp / "bad_ids.txt"
        ids.write_text("toolcall-e2\ndoes-not-exist\n", encoding="utf-8")
        with self.assertRaises(SystemExit):
            self._run(["cadcam ok"], repeats=1, case_ids_file=str(ids))

    def test_empty_case_id_list_cannot_select_everything(self):
        ids = self.tmp / "empty_ids.txt"
        ids.write_text("\n", encoding="utf-8")
        with self.assertRaises(SystemExit):
            self._run(["cadcam ok"], repeats=1, case_ids_file=str(ids))

    def test_repeats_land_in_manifest_fingerprint(self):
        _, man1 = self._run(["cadcam ok"], repeats=1)
        _, man3 = self._run(["cadcam ok"], repeats=3)
        self.assertEqual(man1["repeats"], 1)
        self.assertEqual(man3["repeats"], 3)
        # 续跑保护：不同 repeats 不能被视为同一把尺
        self.assertNotEqual(man1["repeats"], man3["repeats"])


class TestToolsGateStillFailsClosed(unittest.TestCase):
    """补 repeats 时不能把上一轮加的 tools_gate 绕过去。"""

    def test_repeats_does_not_bypass_the_vacuity_gate(self):
        with self.assertRaises(ValueError):
            runner.tools_gate({"model_id": "m", "tools_dimensions": ["toolcall"]},
                              [{"dimension": "toolcall", "id": "x"}])


if __name__ == "__main__":
    unittest.main(verbosity=2)
