#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""世界工程模型云端修复链的反证闸门（测量宪法 §4）。

每个新增门禁都必须「植入坏样本 ⇒ 红」：
  - 回收侧 verify_deliverable_receipt：预算停机/缺指纹/缺回执一律拒绝部署
  - 回收侧 safe_extract：路径穿越/链接成员一律拒绝解包
  - 云端 Stage 1 账本闸：sha 漂移 / repairloop=0 / 源缺失一律拒绝开训
  - 训练器 assert_base_identity：Instruct 错基座一律拒绝
  - TimeBudgetCallback：超预算必须置 budget_stopped（回执不得写 COMPLETED）
  - 语料构建器：repairloop 源缺失必须 fail-closed
  - Modelfile 审计：纯文本模板 / 硬编码 num_gpu 必须红

被测函数一律从源文件 AST 抽取执行（不复制实现），保证测的是真源码。
"""
from __future__ import annotations

import ast
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORCH = ROOT / "cloud_train_pack" / "local_one_click_worldmodel.py"
TRAINER = ROOT / "cloud_train_pack" / "train_turnkey_worldmodel.py"
SH = ROOT / "cloud_train_pack" / "run_worldmodel_fix.sh"
BUILDER = ROOT / "scripts" / "build_wm_cloud_fix_corpus.py"
AUDIT = ROOT / "scripts" / "wm_audit_full.py"
DATASET_DIR = ROOT / "cloud_train_pack" / "dataset"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _extract(path: Path, name: str, ns: dict):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    node = next(n for n in tree.body
                if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name == name)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), ns)
    return ns[name]


def _stage1_script() -> str:
    """从 run_worldmodel_fix.sh 抽取 Stage 1 账本闸 heredoc（单一真源，防复制漂移）。"""
    text = SH.read_text(encoding="utf-8")
    blocks = re.findall(r"<<'PY'\n(.*?)\nPY\n", text, re.S)
    hits = [b for b in blocks if "repairloop_kept_rows" in b]
    assert len(hits) == 1, f"Stage 1 heredoc 定位失败: {len(hits)} 个候选"
    return hits[0]


class ReceiptGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.orch = _load_module("wm_orch_under_test", ORCH)

    def _write_receipt(self, tmp: str, receipt: dict | None):
        d = os.path.join(tmp, "virtu_wm_lora_adapter")
        os.makedirs(d, exist_ok=True)
        if receipt is not None:
            with open(os.path.join(d, "training_receipt.json"), "w", encoding="utf-8") as f:
                json.dump(receipt, f)
        return tmp

    def test_missing_receipt_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_receipt(tmp, None)
            with self.assertRaises(RuntimeError):
                self.orch.verify_deliverable_receipt(tmp)

    def test_time_budget_stopped_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_receipt(tmp, {"status": "TIME_BUDGET_STOPPED",
                                      "adapter_sha256": "a" * 64, "dataset_sha256": "b" * 64})
            with self.assertRaises(RuntimeError):
                self.orch.verify_deliverable_receipt(tmp)

    def test_missing_fingerprints_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_receipt(tmp, {"status": "COMPLETED"})
            with self.assertRaises(RuntimeError):
                self.orch.verify_deliverable_receipt(tmp)

    def test_completed_with_fingerprints_green(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_receipt(tmp, {"status": "COMPLETED",
                                      "adapter_sha256": "a" * 64, "dataset_sha256": "b" * 64})
            r = self.orch.verify_deliverable_receipt(tmp)
            self.assertEqual(r["status"], "COMPLETED")


class SafeExtractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.orch = _load_module("wm_orch_under_test", ORCH)

    def _tar_with(self, member: tarfile.TarInfo, payload: bytes = b"x") -> tarfile.TarFile:
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as t:
            member.size = len(payload)
            t.addfile(member, io.BytesIO(payload))
        buf.seek(0)
        return tarfile.open(fileobj=buf, mode="r")

    def test_parent_traversal_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            tar = self._tar_with(tarfile.TarInfo("../evil.txt"))
            with self.assertRaises(RuntimeError):
                self.orch.safe_extract(tar, os.path.join(tmp, "dest"))
            self.assertFalse(os.path.exists(os.path.join(tmp, "evil.txt")))

    def test_absolute_path_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            tar = self._tar_with(tarfile.TarInfo("/tmp/evil_wm.txt"))
            with self.assertRaises(RuntimeError):
                self.orch.safe_extract(tar, os.path.join(tmp, "dest"))

    def test_symlink_member_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            m = tarfile.TarInfo("link")
            m.type = tarfile.SYMTYPE
            m.linkname = "../../etc/passwd"
            tar = self._tar_with(m, b"")
            with self.assertRaises(RuntimeError):
                self.orch.safe_extract(tar, os.path.join(tmp, "dest"))

    def test_clean_tar_green(self):
        with tempfile.TemporaryDirectory() as tmp:
            tar = self._tar_with(tarfile.TarInfo("adapter/ok.txt"), b"payload")
            dest = os.path.join(tmp, "dest")
            self.orch.safe_extract(tar, dest)
            self.assertEqual(Path(dest, "adapter", "ok.txt").read_bytes(), b"payload")


class Stage1LedgerGateTests(unittest.TestCase):
    """云端开训前账本闸：直接执行从 sh 抽取的真 heredoc。"""

    @classmethod
    def setUpClass(cls):
        cls.script = _stage1_script()
        cls.fixture = tempfile.mkdtemp(prefix="wm_stage1_")
        ds = os.path.join(cls.fixture, "dataset")
        os.makedirs(ds)
        for name in ("virtu_worldmodel_fix_sft.jsonl",
                     "virtu_worldmodel_fix_sft_ledger.json",
                     "virtu_impeller_repairloop_sft.jsonl",
                     "virtu_wm_repairloop_sft.jsonl"):
            shutil.copy2(DATASET_DIR / name, os.path.join(ds, name))
        cls.data = os.path.join(ds, "virtu_worldmodel_fix_sft.jsonl")
        cls.ledger = os.path.join(ds, "virtu_worldmodel_fix_sft_ledger.json")
        cls.rl = os.path.join(ds, "virtu_impeller_repairloop_sft.jsonl")
        cls.wm_rl = os.path.join(ds, "virtu_wm_repairloop_sft.jsonl")
        cls.orig_ledger = Path(cls.ledger).read_bytes()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.fixture, ignore_errors=True)

    def tearDown(self):
        Path(self.ledger).write_bytes(self.orig_ledger)
        for src, dst in (("virtu_impeller_repairloop_sft.jsonl", self.rl),
                         ("virtu_wm_repairloop_sft.jsonl", self.wm_rl)):
            if not os.path.exists(dst):
                shutil.copy2(DATASET_DIR / src, dst)

    def _run(self) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, "-", self.data, self.ledger],
                              input=self.script, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", cwd=self.fixture,
                              env={**os.environ, "PYTHONUTF8": "1"}, timeout=120)

    def _tamper(self, **fields):
        led = json.loads(self.orig_ledger)
        led.update(fields)
        Path(self.ledger).write_text(json.dumps(led, ensure_ascii=False), encoding="utf-8")

    def test_baseline_green(self):
        p = self._run()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("repairloop=420", p.stdout)

    def test_corpus_sha_drift_red(self):
        self._tamper(output_sha256="0" * 64)
        p = self._run()
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("sha256", (p.stdout + p.stderr))

    def test_repairloop_zero_rows_red(self):
        self._tamper(repairloop_kept_rows=0)
        p = self._run()
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("repairloop", (p.stdout + p.stderr))

    def test_repairloop_sha_drift_red(self):
        self._tamper(repairloop_sha256="f" * 64)
        p = self._run()
        self.assertNotEqual(p.returncode, 0)

    def test_repairloop_source_missing_red(self):
        os.remove(self.rl)
        p = self._run()
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("repairloop", (p.stdout + p.stderr))

    def test_wm_repairloop_source_missing_red(self):
        """2026-11-11 起闸门额外要求世界模型 repairloop 源语料；缺它同样必须拒开训。"""
        os.remove(self.wm_rl)
        p = self._run()
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("世界模型 repairloop", (p.stdout + p.stderr))


class BaseIdentityGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gate = staticmethod(_extract(TRAINER, "assert_base_identity", {"os": os, "json": json}))

    def _base(self, tmp: str, name_or_path: str, dirname: str = "Qwen3-8B") -> str:
        d = os.path.join(tmp, dirname)
        os.makedirs(d, exist_ok=True)
        Path(d, "config.json").write_text(
            json.dumps({"_name_or_path": name_or_path}), encoding="utf-8")
        return d

    def test_instruct_dirname_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = self._base(tmp, "Qwen/Qwen3-8B", dirname="Qwen3-8B-Instruct")
            with self.assertRaises(SystemExit):
                self.gate(d)

    def test_instruct_config_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = self._base(tmp, "Qwen/Qwen3-8B-Instruct")
            with self.assertRaises(SystemExit):
                self.gate(d)

    def test_true_base_green(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = self._base(tmp, "Qwen/Qwen3-8B")
            self.gate(d)


class TimeBudgetReceiptTests(unittest.TestCase):
    def test_over_budget_sets_flag_and_stop(self):
        cls = _extract(TRAINER, "TimeBudgetCallback",
                       {"TrainerCallback": object, "time": time})
        cb = cls(max_minutes=0.001)
        cb.start_time -= 60
        control = types.SimpleNamespace(should_training_stop=False, should_save=False)
        cb.on_step_end(None, None, control)
        self.assertTrue(cb.budget_stopped)
        self.assertTrue(control.should_training_stop)
        self.assertTrue(control.should_save)
        status = "TIME_BUDGET_STOPPED" if cb.budget_stopped else "COMPLETED"
        self.assertEqual(status, "TIME_BUDGET_STOPPED")

    def test_within_budget_keeps_completed(self):
        cls = _extract(TRAINER, "TimeBudgetCallback",
                       {"TrainerCallback": object, "time": time})
        cb = cls(max_minutes=60)
        control = types.SimpleNamespace(should_training_stop=False, should_save=False)
        cb.on_step_end(None, None, control)
        self.assertFalse(cb.budget_stopped)
        self.assertFalse(control.should_training_stop)


class BuilderRepairloopFailClosedTests(unittest.TestCase):
    def test_missing_repairloop_source_raises(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        builder = _load_module("wm_builder_under_test", BUILDER)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                builder.build_corpus(repairloop_path=os.path.join(tmp, "missing.jsonl"))


class ModelfileAuditCounterProofTests(unittest.TestCase):
    """审计闸反证：纯文本模板 / 硬编码 num_gpu 植入后必须红。"""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(ROOT / "scripts"))
        import wm_contract as C
        cls.t3 = (ROOT / "checkpoints" / "virtu-wm-v3.Modelfile").read_text(encoding="utf-8")
        cls.t1 = (ROOT / "modelfiles" / "virtu-13.63b.wm-v1.Modelfile").read_text(encoding="utf-8")
        cls.C = C

    def _audit(self, t3: str, t1: str):
        files = {"checkpoints/virtu-wm-v3.Modelfile": t3,
                 "modelfiles/virtu-13.63b.wm-v1.Modelfile": t1}
        ns = {"re": re, "read": lambda p: files[p], "C": self.C}
        fn = _extract(AUDIT, "modelfile_audit", ns)
        return fn()

    def test_current_modelfiles_green(self):
        ok, msg = self._audit(self.t3, self.t1)
        self.assertTrue(ok, msg)

    def test_plain_text_template_red(self):
        mutant = self.t3.replace("<|im_start|>", "").replace("<|im_end|>", "")
        ok, msg = self._audit(mutant, self.t1)
        self.assertFalse(ok)
        self.assertIn("ChatML", msg)

    def test_hardcoded_num_gpu_red(self):
        mutant = self.t1 + "\nPARAMETER num_gpu 30\n"
        ok, msg = self._audit(self.t3, mutant)
        self.assertFalse(ok)
        self.assertIn("num_gpu", msg)


if __name__ == "__main__":
    unittest.main(verbosity=2)