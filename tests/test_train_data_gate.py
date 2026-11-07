"""The leak gate must fire on a verbatim eval prompt and stay silent on a clean corpus.

Measured 2026-11-05: `data/sft/virtu_evolution_v5.jsonl` (3,963 rows) carries 157 hard
leaks against the 240-case board - including `prompt_hash=toolcall-e05` exact matches -
while `train_corpus_comprehensive.jsonl` (4,999 rows) has 0 hard leaks but 1,621 numeric
proxies. Treating those two classes alike made the gate either useless (25% false-positive
rate on generic values like 0.005/0202/2021) or blind (people skipped it because it always
failed). Hence: hard = blocking, numeric = warning, and a trainer that starts without the
gate is a bug.
"""
import io
import json
import os
import subprocess
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

from virtu_eval.contamination_check import assert_no_leak, scan_corpus  # noqa: E402

CASE_DIR = ROOT / "data" / "benchmark" / "virtu_eval_v1"


def _one_eval_case():
    with io.open(CASE_DIR / "toolcall.jsonl", encoding="utf-8") as f:
        return json.loads(f.readline())


def _write_jsonl(path, rows):
    with io.open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


class TestScanCorpus(unittest.TestCase):
    def test_verbatim_eval_prompt_is_a_hard_leak(self):
        case = _one_eval_case()
        with tempfile.TemporaryDirectory(dir=_tmp_root()) as tmp:
            train = os.path.join(tmp, "train.jsonl")
            _write_jsonl(train, [{"messages": [{"role": "user", "content": case["prompt"]},
                                               {"role": "assistant", "content": "ok"}]}])
            result = scan_corpus(train, eval_dir=str(CASE_DIR))
        self.assertGreaterEqual(result["hard_leaks"], 1, result)
        self.assertTrue(any("prompt_hash" in e for e in result["examples"]), result["examples"])

    def test_unrelated_corpus_is_clean(self):
        with tempfile.TemporaryDirectory(dir=_tmp_root()) as tmp:
            train = os.path.join(tmp, "train.jsonl")
            _write_jsonl(train, [{"messages": [{"role": "user",
                                                "content": "请说明硬质合金牌号 YG8 与 YT15 的适用工序差异"},
                                               {"role": "assistant", "content": "YG8 脆性大、韧性好，适合冲击切削；YT15 红硬性高，适合钢件精车。"}]}])
            result = scan_corpus(train, eval_dir=str(CASE_DIR))
        self.assertEqual(result["hard_leaks"], 0, result)

    def test_real_leaked_corpus_is_blocked_and_its_clean_copy_is_not(self):
        leaked = ROOT / "data" / "sft" / "virtu_evolution_v5.jsonl"
        cleaned = ROOT / "data" / "sft" / "virtu_evolution_v5.clean.jsonl"
        if not leaked.exists() or not cleaned.exists():
            self.skipTest("quarantined corpus pair not present")
        with io.open(cleaned, encoding="utf-8") as f:
            rows = sum(1 for _ in f)
        self.assertEqual(rows, 3806, "the de-leaked copy must be exactly 3,963 - 157 rows")


class TestAssertNoLeak(unittest.TestCase):
    def test_exit_code_two_on_hard_leak(self):
        case = _one_eval_case()
        with tempfile.TemporaryDirectory(dir=_tmp_root()) as tmp:
            train = os.path.join(tmp, "train.jsonl")
            _write_jsonl(train, [{"messages": [{"role": "user", "content": case["prompt"]},
                                               {"role": "assistant", "content": "ok"}]}])
            probe = ("import sys; sys.path.insert(0, r'%s'); "
                     "from virtu_eval.contamination_check import assert_no_leak; "
                     "assert_no_leak(r'%s', r'%s')" % (ROOT, train, CASE_DIR))
            proc = subprocess.run([sys.executable, "-c", probe],
                                  capture_output=True, text=True,
                                  env={**os.environ, "PYTHONUTF8": "1"})
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("拒绝开训", proc.stdout)

    def test_trainers_call_the_gate_before_touching_weights(self):
        for rel in ("scripts/train_qwen3_8b_qlora.py", "cloud_train_pack/train_turnkey.py"):
            text = io.open(ROOT / rel, encoding="utf-8", errors="ignore").read()
            self.assertIn("assert_no_leak", text, f"{rel} 未接泄漏闸")
            body = text[text.index("parse_args("):]  # everything after the CLI is read
            self.assertIn("assert_no_leak", body, f"{rel} 的闸不在 main 里")
            load_at = min((body.index(marker) for marker in
                           ("AutoTokenizer.from_pretrained", "find_or_download_base",
                            "load_dataset") if marker in body), default=None)
            self.assertIsNotNone(load_at, f"{rel} 找不到可比较的加载点")
            self.assertLess(body.index("assert_no_leak"), load_at,
                            f"{rel} 的闸在载权重/读语料之后，等于没有闸")

    def test_turnkey_refuses_silent_data_fallback(self):
        """A missing --data used to fall back to a different corpus and still label the
        artifact with the requested one."""
        text = io.open(ROOT / "cloud_train_pack" / "train_turnkey.py",
                       encoding="utf-8", errors="ignore").read()
        self.assertIn("拒绝自动回退", text)
        self.assertNotIn("自动回退探测到数据集", text)


if __name__ == "__main__":
    unittest.main()
