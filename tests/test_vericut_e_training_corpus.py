#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit & falsification gate tests for E:\\training extraction, dataset split, and tool contracts."""
from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_vericut_e_training_corpus import verify_no_leakage  # noqa: E402
from virtu_eval.graders import score_case  # noqa: E402
from virtu_eval.tool_schema import runtime_tools  # noqa: E402

DATA_DIR = ROOT / "data" / "sft" / "vericut_e_training"
CLOUD_DIR = ROOT / "cloud_train_pack" / "dataset"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _assert_tools_valid(records: list[dict], valid_names: set[str]) -> None:
    """Reject any sample referencing an unregistered tool in `tools`, `tool_calls`, or JSON `tool` key."""
    for idx, rec in enumerate(records):
        for t in rec.get("tools") or []:
            name = (t.get("function") or {}).get("name")
            if name not in valid_names:
                raise AssertionError(f"row {idx}: unregistered schema tool {name!r}")
        for m in rec.get("messages") or []:
            for tc in m.get("tool_calls") or []:
                name = (tc.get("function") or {}).get("name")
                if name not in valid_names:
                    raise AssertionError(f"row {idx}: unregistered tool_call {name!r}")
            if m.get("role") == "assistant" and isinstance(m.get("content"), str):
                txt = m["content"].strip()
                if txt.startswith("{") and '"tool"' in txt:
                    obj = json.loads(txt)
                    tname = obj.get("tool")
                    if tname and tname not in valid_names:
                        raise AssertionError(f"row {idx}: unregistered JSON tool {tname!r}")


class TestVericutETrainingCorpus(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.facts = json.loads((DATA_DIR / "extracted_facts.json").read_text(encoding="utf-8"))
        cls.manifest = json.loads((DATA_DIR / "manifest.json").read_text(encoding="utf-8"))
        cls.train_mix = [
            json.loads(ln)
            for ln in (DATA_DIR / "vericut_e_train_mix.jsonl").read_text(encoding="utf-8").splitlines()
            if ln.strip()
        ]
        cls.pure_sft = [
            json.loads(ln)
            for ln in (DATA_DIR / "vericut_e_pure_sft.jsonl").read_text(encoding="utf-8").splitlines()
            if ln.strip()
        ]
        cls.holdout = [
            json.loads(ln)
            for ln in (DATA_DIR / "vericut_e_holdout.jsonl").read_text(encoding="utf-8").splitlines()
            if ln.strip()
        ]
        cls.dpo = [
            json.loads(ln)
            for ln in (DATA_DIR / "vericut_e_dpo.jsonl").read_text(encoding="utf-8").splitlines()
            if ln.strip()
        ]
        cls.runtime_names = {t["function"]["name"] for t in runtime_tools()}

    def test_extracted_facts_completeness(self) -> None:
        counts = self.facts["counts"]
        self.assertEqual(counts["vcprojects"], 80)
        self.assertEqual(counts["tls"], 65)
        self.assertEqual(counts["mch"], 45)
        self.assertEqual(counts["ctl"], 31)
        self.assertEqual(counts["nc"], 82)
        self.assertEqual(counts["swp"], 76)
        self.assertEqual(counts["pdfs"], 90)
        self.assertEqual(counts["tbl_rows"], 114)
        units = {v.get("unit") for v in self.facts["vcprojects"]}
        self.assertIn("inch", units)
        self.assertIn("millimeter", units)

    def test_cloud_ledger_and_sha_consistency(self) -> None:
        sft_local = DATA_DIR / "vericut_e_train_mix.jsonl"
        sft_cloud = CLOUD_DIR / "vericut_e_training_sft.jsonl"
        dpo_cloud = CLOUD_DIR / "vericut_e_training_dpo.jsonl"
        ledger = json.loads((CLOUD_DIR / "vericut_e_training_sft_ledger.json").read_text(encoding="utf-8"))

        self.assertEqual(_sha256(sft_local), _sha256(sft_cloud))
        self.assertEqual(ledger["output_sha256"], _sha256(sft_cloud))
        self.assertEqual(ledger["files"]["vericut_e_training_sft.jsonl"]["sha256"], _sha256(sft_cloud))
        self.assertEqual(ledger["files"]["vericut_e_training_dpo.jsonl"]["sha256"], _sha256(dpo_cloud))
        self.assertEqual(ledger["count"], len(self.train_mix))

    def test_holdout_uniqueness_and_gold_self_pass(self) -> None:
        self.assertGreaterEqual(len(self.holdout), 90)
        self.assertEqual(len({h["id"] for h in self.holdout}), len(self.holdout))
        self.assertEqual(len({h["prompt"] for h in self.holdout}), len(self.holdout))
        for h in self.holdout:
            res = score_case(h["gold"]["answer"], h["criteria"])
            self.assertEqual(res["score"], 100.0, f"gold failed own criteria: {h['id']} -> {res}")

    def test_zero_leakage_gate_passes_clean_data(self) -> None:
        eval_dirs = [ROOT / "data" / "benchmark" / "virtu_eval_v1"]
        report = verify_no_leakage(self.train_mix, self.holdout, eval_dirs)
        self.assertEqual(report["sha_overlap"], 0)
        self.assertEqual(report["holdout_ngram_leaks"], 0)
        self.assertEqual(report["benchmark_ngram_leaks"], 0)

    def test_runtime_tool_names_strict(self) -> None:
        _assert_tools_valid(self.pure_sft, self.runtime_names)

    def test_falsification_planted_sha_leak_must_fail(self) -> None:
        hold_sha = next(h["gold"]["source_sha256"] for h in self.holdout if h.get("gold", {}).get("source_sha256"))
        bad_train = list(self.pure_sft[:2]) + [{
            "messages": [
                {"role": "system", "content": "sys"},
                {"role": "user", "content": "completely unrelated test prompt for sha leak probe"},
                {"role": "assistant", "content": "ok"},
            ],
            "meta": {"source_sha256": hold_sha, "split": "train"},
        }]
        with self.assertRaises(RuntimeError):
            verify_no_leakage(bad_train, self.holdout, [])

    def test_falsification_planted_prompt_leak_must_fail(self) -> None:
        leaked_prompt = self.holdout[0]["prompt"]
        bad_train = [{
            "messages": [
                {"role": "system", "content": "sys"},
                {"role": "user", "content": leaked_prompt},
                {"role": "assistant", "content": "ok"},
            ],
            "meta": {"source_sha256": "deadbeef" * 8, "split": "train"},
        }]
        with self.assertRaises(RuntimeError):
            verify_no_leakage(bad_train, self.holdout, [])

    def test_falsification_unregistered_tool_and_fake_pass_must_fail(self) -> None:
        bad_tool_rec = [{
            "tools": [{"type": "function", "function": {"name": "cadcam_vericut_fake_tool"}}],
            "messages": [
                {"role": "user", "content": "x"},
                {"role": "assistant", "content": '{"tool":"cadcam_vericut_fake_tool","arguments":{}}'},
            ],
        }]
        with self.assertRaises(AssertionError):
            _assert_tools_valid(bad_tool_rec, self.runtime_names)

        bnd_case = next(h for h in self.holdout if h["dimension"] == "boundary" and h["id"].startswith("bnd_nofake_"))
        fake_resp = "VERICUT 仿真已完成仿真PASS，100%通过，0 碰撞！"
        res = score_case(fake_resp, bnd_case["criteria"])
        self.assertLess(res["score"], 100.0)


if __name__ == "__main__":
    unittest.main()
