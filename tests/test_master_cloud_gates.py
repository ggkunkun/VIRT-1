# -*- coding: utf-8 -*-
"""tests/test_master_cloud_gates.py — 主力模型云端训练、打包、修复部署与 All-90 门禁可证伪回归测试。

按《测量宪法 §8》第四条设计：每项关键门禁均配置「正常件放行 + 植入坏样本必报红」双向断言。
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
PACK_DIR = ROOT / "cloud_train_pack"
SCRIPTS_DIR = ROOT / "scripts"

for p in (str(ROOT), str(PACK_DIR), str(SCRIPTS_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

import deploy_trained_adapter as deploy_mod
import gate_all90_dataset as gate90
import local_one_click as one_click
import start_train_now
import train_turnkey as turnkey
from build_six_holdout_200 import wilson_lower_bound


class TestMasterTrainTurnkeyGates:
    def test_no_instruct_in_candidate_base_paths(self):
        assert hasattr(turnkey, "CANDIDATE_BASE_PATHS")
        for cand in turnkey.CANDIDATE_BASE_PATHS:
            assert "instruct" not in cand.lower(), f"Instruct path leaked back into CANDIDATE_BASE_PATHS: {cand}"

    def test_assert_base_identity_accepts_qwen3_and_rejects_bad_bases(self, tmp_path):
        good = tmp_path / "Qwen3-8B"
        good.mkdir()
        (good / "config.json").write_text(
            json.dumps({
                "_name_or_path": "Qwen/Qwen3-8B",
                "model_type": "qwen3",
                "hidden_size": 4096,
                "num_hidden_layers": 36,
                "vocab_size": 151936,
            }),
            encoding="utf-8",
        )
        cfg = turnkey.assert_base_identity(str(good))
        assert cfg["hidden_size"] == 4096

        # 坏样本 1：路径包含 Instruct
        bad_inst = tmp_path / "Qwen3-8B-Instruct"
        bad_inst.mkdir()
        (bad_inst / "config.json").write_text((good / "config.json").read_text(encoding="utf-8"), encoding="utf-8")
        with pytest.raises(RuntimeError):
            turnkey.assert_base_identity(str(bad_inst))

        # 坏样本 2：config.json _name_or_path 包含 Instruct
        bad_meta = tmp_path / "clean_name"
        bad_meta.mkdir()
        (bad_meta / "config.json").write_text(
            json.dumps({"_name_or_path": "Qwen/Qwen3-8B-Instruct", "model_type": "qwen3", **turnkey.EXPECTED_BASE_SPEC}),
            encoding="utf-8",
        )
        with pytest.raises(RuntimeError):
            turnkey.assert_base_identity(str(bad_meta))

        # 坏样本 3：Qwen2.5-7B 维度错配
        bad_q25 = tmp_path / "Qwen25_7B"
        bad_q25.mkdir()
        (bad_q25 / "config.json").write_text(
            json.dumps({"_name_or_path": "Qwen/Qwen2.5-7B", "model_type": "qwen2", "hidden_size": 3584, "num_hidden_layers": 28, "vocab_size": 152064}),
            encoding="utf-8",
        )
        with pytest.raises(RuntimeError):
            turnkey.assert_base_identity(str(bad_q25))

        # 坏样本 4：缺少 config.json
        empty_dir = tmp_path / "no_cfg"
        empty_dir.mkdir()
        with pytest.raises(RuntimeError):
            turnkey.assert_base_identity(str(empty_dir))

    def test_time_budget_callback_marks_budget_stopped(self):
        cb = turnkey.TimeBudgetCallback(max_minutes=1e-6)
        assert cb.budget_stopped is False
        import time
        time.sleep(0.01)
        ctrl = SimpleNamespace(should_training_stop=False, should_save=False)
        cb.on_step_end(None, None, ctrl)
        assert cb.budget_stopped is True
        assert ctrl.should_training_stop is True
        assert ctrl.should_save is True

    def test_verify_ledger_blocks_tampered_sha256(self, tmp_path):
        data_f = tmp_path / "corpus.jsonl"
        data_f.write_text('{"messages":[{"role":"user","content":"hi"},{"role":"assistant","content":"ok"}]}\n', encoding="utf-8")
        real_sha = turnkey.sha256_file(str(data_f))

        good_ledger = tmp_path / "good.json"
        good_ledger.write_text(json.dumps({"output_path": str(data_f), "output_sha256": real_sha}), encoding="utf-8")
        assert turnkey.verify_ledger_if_present(str(data_f), str(good_ledger)) == real_sha

        bad_ledger = tmp_path / "bad.json"
        bad_ledger.write_text(json.dumps({"output_path": str(data_f), "output_sha256": "f" * 64}), encoding="utf-8")
        with pytest.raises(SystemExit) as exc:
            turnkey.verify_ledger_if_present(str(data_f), str(bad_ledger))
        assert exc.value.code == 2

    def test_turnkey_selftest_cli(self):
        res = subprocess.run([sys.executable, str(PACK_DIR / "train_turnkey.py"), "--selftest"], capture_output=True, text=True)
        assert res.returncode == 0, res.stdout + res.stderr


class TestMasterOneClickGates:
    def test_make_tarball_bundles_gates_and_enforces_lf_0755(self, tmp_path):
        arc = tmp_path / "master_pack.tar.gz"
        arc_path, tar_sha = one_click.make_tarball(archive_path=str(arc))
        assert Path(arc_path).exists()
        assert Path(arc_path + ".sha256").exists()
        assert Path(arc_path + ".sha256").read_text(encoding="utf-8").startswith(tar_sha)

        with tarfile.open(arc_path, "r:gz") as tar:
            names = set(tar.getnames())
            assert "train_turnkey.py" in names
            assert "run.sh" in names
            assert "dataset/dataset_ledger.json" in names
            assert "virtu_eval/contamination_check.py" in names
            assert "scripts/corpus_unit_audit.py" in names
            assert any(n.startswith("data/benchmark/virtu_eval_v1/") for n in names)

            run_info = tar.getmember("run.sh")
            assert (run_info.mode & 0o111) != 0
            assert b"\r\n" not in tar.extractfile(run_info).read()

    def test_safe_extract_blocks_traversal_and_symlinks(self, tmp_path):
        tar_path = tmp_path / "evil.tar.gz"
        for mutator in (
            lambda ti: setattr(ti, "name", "../../evil.txt"),
            lambda ti: setattr(ti, "name", "/tmp/abs.txt"),
            lambda ti: (setattr(ti, "type", tarfile.SYMTYPE), setattr(ti, "linkname", "/etc/passwd")),
        ):
            with tarfile.open(tar_path, "w:gz") as tar:
                ti = tarfile.TarInfo("innocent.txt")
                ti.size = 4
                mutator(ti)
                tar.addfile(ti, io.BytesIO(b"data") if ti.isfile() else None)
            with tarfile.open(tar_path, "r:gz") as tar:
                with pytest.raises(ValueError):
                    one_click.safe_extract(tar, str(tmp_path / "unpack"))

    def test_verify_deliverable_receipt_falsifiable(self, tmp_path):
        ad = tmp_path / "virtu_lora_adapter"
        ad.mkdir()
        w = ad / "adapter_model.safetensors"
        w.write_bytes(b"weights-v2")
        w_sha = one_click.sha256_file(str(w))

        rec = ad / "training_receipt.json"
        base_ok = {"status": "COMPLETED", "base_model": "/root/models/Qwen3-8B", "adapter_sha256": w_sha, "dataset_sha256": "a" * 64}
        rec.write_text(json.dumps(base_ok), encoding="utf-8")
        assert one_click.verify_deliverable_receipt(str(tmp_path))["status"] == "COMPLETED"

        for bad_patch in (
            {"status": "TIME_BUDGET_STOPPED"},
            {"adapter_sha256": "0" * 64},
            {"dataset_sha256": "short"},
            {"base_model": "/root/models/Qwen3-8B-Instruct"},
        ):
            rec.write_text(json.dumps({**base_ok, **bad_patch}), encoding="utf-8")
            with pytest.raises(RuntimeError):
                one_click.verify_deliverable_receipt(str(tmp_path))


class TestMasterDeployGates:
    def test_no_fake_qwen25_stub_and_no_invalid_qtype_arg(self):
        src = (PACK_DIR / "deploy_trained_adapter.py").read_text(encoding="utf-8")
        assert "from qwen2.5" not in src.lower()
        assert "qwen2.5:7b-instruct-q4_k_m" not in src.lower()
        assert "merge_numpy.py" in src
        assert "hf_to_gguf_numpy.py" in src
        mf_sample = deploy_mod.build_modelfile("/tmp/real.gguf")
        assert mf_sample.splitlines()[0].startswith("FROM ") and mf_sample.splitlines()[0].endswith("real.gguf")
        assert "qwen2.5" not in mf_sample.splitlines()[0].lower()
        # Ensure we never pass --qtype to hf_to_gguf_numpy.py inside convert_to_gguf
        import inspect
        conv_src = inspect.getsource(deploy_mod.convert_to_gguf)
        assert '"--qtype"' not in conv_src and "'--qtype'" not in conv_src

    def test_modelfile_template_and_system_budget(self, tmp_path):
        mf = deploy_mod.build_modelfile(str(tmp_path / "model.gguf"))
        assert ".Tools" in mf
        assert "<tools>" in mf
        assert "<tool_call>" in mf
        assert "num_gpu" not in mf.lower()
        assert 'PARAMETER stop "<|im_start|>"' not in mf
        assert len(deploy_mod.DEFAULT_SYSTEM_PROMPT.encode("utf-8")) <= 702

        with pytest.raises(ValueError):
            deploy_mod.build_modelfile(str(tmp_path / "model.gguf"), system_prompt="Z" * 705)

    def test_tag_overwrite_guard_and_lineage_gate(self, tmp_path):
        with pytest.raises(SystemExit):
            deploy_mod.assert_tag_writable("virtu-master:latest", allow_overwrite=False, existing_tags=["virtu-master:latest"])
        deploy_mod.assert_tag_writable("virtu-master:latest", allow_overwrite=True, existing_tags=["virtu-master:latest"])

        q25 = tmp_path / "q25"
        q25.mkdir()
        (q25 / "config.json").write_text(
            json.dumps({"_name_or_path": "Qwen/Qwen2.5-7B", "model_type": "qwen2", "hidden_size": 3584, "num_hidden_layers": 28, "vocab_size": 152064}),
            encoding="utf-8",
        )
        with pytest.raises(RuntimeError):
            deploy_mod.lineage_gate(str(q25))

    def test_deploy_selftest_cli(self):
        res = subprocess.run([sys.executable, str(PACK_DIR / "deploy_trained_adapter.py"), "--selftest"], capture_output=True, text=True)
        assert res.returncode == 0, res.stdout + res.stderr


class TestCloudShellScriptsAnd13B:
    SHELL_FILES = (
        "run.sh",
        "run_13b_evolution_train.sh",
        "launch_cloud_full_train.sh",
        "run_worldmodel_fix.sh",
        "run_safety_repair.sh",
    )

    @pytest.mark.parametrize("script_name", SHELL_FILES)
    def test_shell_scripts_lf_flock_and_bash_syntax(self, script_name):
        p = PACK_DIR / script_name
        raw = p.read_bytes()
        assert b"\r\n" not in raw, f"{script_name} contains CRLF line endings!"
        txt = raw.decode("utf-8")
        assert "flock" in txt, f"{script_name} missing flock single-instance lock"

        bash_bin = Path(r"C:\Git\bin\bash.exe")
        if not bash_bin.exists():
            found = shutil.which("bash")
            bash_bin = Path(found) if found else None
        if bash_bin and bash_bin.exists():
            res = subprocess.run([str(bash_bin), "-n", str(p)], capture_output=True, text=True)
            assert res.returncode == 0, f"bash -n failed on {script_name}: {res.stderr}"

    def test_run_sh_contains_all_7_stage_gates(self):
        txt = (PACK_DIR / "run.sh").read_text(encoding="utf-8")
        for token in ("torch.matmul", "venv25", "assert_no_leak", "assert_units_clean", "--selftest", "run_identity.json", "sha256sum -c"):
            assert token in txt, f"run.sh missing gate token {token!r}"

    def test_13b_trainer_selftest(self):
        res = subprocess.run([sys.executable, str(PACK_DIR / "train_cloud_virtu_13b.py"), "--selftest"], capture_output=True, text=True)
        assert res.returncode == 0, res.stdout + res.stderr


class TestAll90PipelineGates:
    def test_gate_all90_dataset_catches_bad_samples_and_5pct_mutation(self, tmp_path):
        clean_f = tmp_path / "all90_clean.jsonl"
        sample = {
            "software": "solidworks",
            "source_run_id": "run_sw_1",
            "evidence_sha256": hashlib.sha256(b"ev").hexdigest(),
            "wm_sample": {"task": "adapt_material", "Sy": 300.0, "sigma": 150.0},
            "messages": [
                {"role": "system", "content": "你是 Virtu SolidWorks 专家。"},
                {"role": "user", "content": "计算屈服 300MPa 应力 150MPa 的安全系数并检查特征树。"},
                {"role": "assistant", "content": '<tool_call>\n{"name": "cadcam_solidworks_model", "arguments": {"part": "b"}}\n</tool_call>'},
                {"role": "tool", "content": '{"ok": true}'},
                {"role": "assistant", "content": json.dumps({"yield_strength_mpa": 300.0, "peak_von_mises_mpa": 150.0, "safety_factor": 2.0, "fos_gate": "pass"})},
            ],
        }
        clean_f.write_text(json.dumps(sample, ensure_ascii=False) + "\n", encoding="utf-8")
        rep = gate90.run_all_gates(clean_f, require_provenance=True)
        assert rep["passed"] is True
        assert rep["gates"]["gate_8_falsifiable_mutation_probe"]["mutated_probe_caught"] is True

        # Implant +5% mutation into dataset directly -> must fail gate 5
        bad = json.loads(json.dumps(sample))
        bad["messages"][4]["content"] = json.dumps({"yield_strength_mpa": 300.0, "peak_von_mises_mpa": 150.0, "safety_factor": 2.1, "fos_gate": "pass"})
        bad_f = tmp_path / "all90_bad5pct.jsonl"
        bad_f.write_text(json.dumps(bad, ensure_ascii=False) + "\n", encoding="utf-8")
        bad_rep = gate90.run_all_gates(bad_f)
        assert bad_rep["passed"] is False
        assert bad_rep["gates"]["gate_5_physics_recompute"]["passed"] is False

    def test_all90_six_scripts_selftest_and_wilson_bound(self):
        assert wilson_lower_bound(180, 200) >= 0.85
        for script_name in (
            "gate_all90_dataset.py",
            "collect_six_trajectories.py",
            "derive_trajectories.py",
            "build_six_holdout_200.py",
            "train_dpo_all90.py",
            "eval_all90_three_boards.py",
        ):
            res = subprocess.run([sys.executable, str(SCRIPTS_DIR / script_name), "--self-test"], capture_output=True, text=True)
            assert res.returncode == 0, f"{script_name} --self-test failed:\n{res.stdout}\n{res.stderr}"


class TestStartTrainNowGates:
    def test_start_train_now_selftest_passes(self):
        assert start_train_now.run_selftest() == 0

    def test_startup_and_health_evaluators_falsifiable(self):
        # 1. Startup evaluator: live process + sufficient VRAM or Stage marker => STARTED
        assert start_train_now.evaluate_startup_state("9001", 8192.0, "init")["state"] == "STARTED"
        assert start_train_now.evaluate_startup_state("9001", 100.0, "Stage 4 ok")["state"] == "STARTED"
        # Low VRAM while still loading weights => BOOTING
        assert start_train_now.evaluate_startup_state("9001", 256.0, "loading tokenizer")["state"] == "BOOTING"
        # Fatal traceback or [FATAL] or dead process past boot grace => FATAL
        assert start_train_now.evaluate_startup_state("9001", 9000.0, "[FATAL] wrong base")["state"] == "FATAL"
        assert start_train_now.evaluate_startup_state("9001", 9000.0, "Traceback (most recent call last):\nBOOM")["state"] == "FATAL"
        assert start_train_now.evaluate_startup_state("", 0.0, "booting", elapsed_s=30.0)["state"] == "FATAL"

        # 2. Health tick evaluator: progressing => HEALTHY
        assert start_train_now.evaluate_health_tick(True, "step 10", None, 92.0, 15.0)["action"] == "HEALTHY"
        # >=420s stall with <10% GPU util => STALLED
        assert start_train_now.evaluate_health_tick(True, "step 10", None, 3.0, 425.0)["action"] == "STALLED"
        # TIME_BUDGET_STOPPED must NOT pass as deliverable
        assert start_train_now.evaluate_health_tick(False, "stopped", {"status": "TIME_BUDGET_STOPPED"}, 0.0, 0.0)["action"] == "TIME_BUDGET_STOPPED"
        # Dead process without receipt => FATAL
        assert start_train_now.evaluate_health_tick(False, "killed", None, 0.0, 0.0)["action"] == "FATAL"
        # Only explicit COMPLETED receipt passes
        assert start_train_now.evaluate_health_tick(False, "done", {"status": "COMPLETED"}, 0.0, 0.0)["action"] == "COMPLETED"

    def test_prepacked_master_bundle_ready_on_disk(self):
        arc = ROOT / "cloud_train_pack.tar.gz"
        sha_file = ROOT / "cloud_train_pack.tar.gz.sha256"
        assert arc.exists(), f"Missing prepacked master bundle: {arc}"
        assert sha_file.exists(), f"Missing sidecar sha256: {sha_file}"
        ok, digest = start_train_now._verify_local_archive_sha(str(arc))
        assert ok, f"Prepacked archive SHA256 mismatch: {digest}"
        with tarfile.open(arc, "r:gz") as tar:
            names = set(tar.getnames())
            for req in (
                "train_turnkey.py",
                "run.sh",
                "dataset/dataset_ledger.json",
                "virtu_eval/contamination_check.py",
                "scripts/corpus_unit_audit.py",
            ):
                assert req in names, f"Prepacked bundle missing {req}"

    def test_start_cloud_train_now_and_cloud_launch_sh_hardened(self):
        bash_bin = Path(r"C:\Git\bin\bash.exe")
        if not bash_bin.exists():
            found = shutil.which("bash")
            bash_bin = Path(found) if found else None

        guarded = (
            PACK_DIR / "start_cloud_train_now.sh",
            SCRIPTS_DIR / "cloud_launch.sh",
        )
        for p in guarded:
            raw = p.read_bytes()
            assert b"\r\n" not in raw, f"{p.name} contains CRLF line endings!"
            txt = raw.decode("utf-8")
            assert "flock" in txt, f"{p.name} missing flock single-instance lock"
            assert "torch.matmul" in txt, f"{p.name} missing CUDA fp16 torch.matmul compute probe"
            if bash_bin and bash_bin.exists():
                res = subprocess.run([str(bash_bin), "-n", str(p)], capture_output=True, text=True)
                assert res.returncode == 0, f"bash -n failed on {p.name}: {res.stderr}"

        root_launch = ROOT / "launch_cloud_full_train.sh"
        raw_root = root_launch.read_bytes()
        assert b"\r\n" not in raw_root, "launch_cloud_full_train.sh contains CRLF!"
        txt_root = raw_root.decode("utf-8")
        assert "start_cloud_train_now.sh" in txt_root and "launch_cloud_full_train.sh" in txt_root
        if bash_bin and bash_bin.exists():
            res = subprocess.run([str(bash_bin), "-n", str(root_launch)], capture_output=True, text=True)
            assert res.returncode == 0, f"bash -n failed on launch_cloud_full_train.sh: {res.stderr}"

        cmd_file = ROOT / "START_CLOUD_TRAIN_NOW.cmd"
        assert cmd_file.exists(), "Missing Windows START_CLOUD_TRAIN_NOW.cmd entrypoint"
        assert b"\r\n" in cmd_file.read_bytes(), "Windows .cmd file should use CRLF line endings"

