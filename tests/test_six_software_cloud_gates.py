#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Falsifiable regression gates for the Six-Software cloud SFT + DPO training track."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PACK_DIR = ROOT / "cloud_train_pack"
SCRIPTS_DIR = ROOT / "scripts"

for p in (str(ROOT), str(PACK_DIR), str(SCRIPTS_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

import gate_all90_dataset as ga  # noqa: E402
import local_one_click  # noqa: E402
import start_train_now  # noqa: E402
import train_vericut_dpo as vdpo  # noqa: E402
from scripts.corpus_unit_audit import assert_units_clean  # noqa: E402
from virtu_eval.contamination_check import assert_no_leak, scan_corpus  # noqa: E402


def _find_git_bash() -> str | None:
    for cand in (r"C:\Git\bin\bash.exe", r"E:\dev\msys64\usr\bin\bash.exe"):
        if os.path.isfile(cand):
            return cand
    found = shutil.which("bash")
    if found and "system32" not in found.lower():
        return found
    return None


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_run_six_software_sh_lf_syntax_and_contracts() -> None:
    for rel in ("run_six_software_real.sh", "start_cloud_train_now.sh"):
        p = PACK_DIR / rel
        assert p.is_file(), f"Missing {p}"
        raw = p.read_bytes()
        assert b"\r" not in raw, f"{rel} must use pure LF line endings (found CR)"

    runner_txt = (PACK_DIR / "run_six_software_real.sh").read_text(encoding="utf-8")
    for marker in (
        "flock -n 9",
        "torch.matmul",
        "assert_base_identity",
        "assert_units_clean",
        "assert_no_leak",
        "train_turnkey.py",
        "train_vericut_dpo.py",
        "six_software_real_deliverable.tar.gz",
        "sha256sum -c",
    ):
        assert marker in runner_txt, f"Missing required gate marker {marker!r}"

    bash_exe = _find_git_bash()
    if bash_exe:
        for rel in ("run_six_software_real.sh", "start_cloud_train_now.sh"):
            r = subprocess.run([bash_exe, "-n", str(PACK_DIR / rel)], capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
            assert r.returncode == 0, f"bash -n failed for {rel}: {r.stderr}"


def test_train_vericut_dpo_selftest_and_rank_gate(tmp_path: Path) -> None:
    r = subprocess.run([sys.executable, str(PACK_DIR / "train_vericut_dpo.py"), "--selftest"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, f"DPO selftest failed: {r.stdout}\n{r.stderr}"
    assert "[DPO_SELFTEST] PASS" in r.stdout

    # Falsifiable: rank != (32, 64) and FAILED receipt must abort
    bad_sft = tmp_path / "bad_sft"
    bad_sft.mkdir()
    (bad_sft / "adapter_config.json").write_text(json.dumps({"r": 32, "lora_alpha": 64}), encoding="utf-8")
    (bad_sft / "training_receipt.json").write_text(json.dumps({"status": "FAILED"}), encoding="utf-8")
    with pytest.raises(SystemExit):
        vdpo._assert_sft_rank(bad_sft)


def test_six_software_corpus_and_dpo_gates_pass_and_falsifiable(tmp_path: Path) -> None:
    sft_path = PACK_DIR / "dataset" / "six_software_real_assets_sft.jsonl"
    dpo_path = PACK_DIR / "dataset" / "six_software_real_assets_dpo.jsonl"
    ledger_path = PACK_DIR / "dataset" / "six_software_real_assets_sft_ledger.json"
    holdout_path = ROOT / "data" / "sft" / "six_software_real_assets" / "six_software_holdout.jsonl"

    assert sft_path.is_file() and dpo_path.is_file() and ledger_path.is_file() and holdout_path.is_file()
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    sft_sha = _sha256_bytes(sft_path.read_bytes())
    dpo_sha = _sha256_bytes(dpo_path.read_bytes())
    assert ledger["files"]["six_software_real_assets_sft.jsonl"]["sha256"] == sft_sha
    assert ledger["files"]["six_software_real_assets_dpo.jsonl"]["sha256"] == dpo_sha

    sft_rows = [json.loads(ln) for ln in sft_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(sft_rows) == 850
    g1 = ga.gate_schema_and_tools(sft_rows)
    assert g1["passed"], f"gate_1 failed: {g1['errors']}"
    assert g1["tool_calls_checked"] >= 1700

    # Budget passes at 1024B and falsifiably rejects too-tight 512B cap
    g2_ok = ga.gate_system_prompt_budget_and_leak(sft_rows, max_bytes=1024)
    assert g2_ok["passed"] and g2_ok["max_bytes_seen"] <= 1024
    g2_fail = ga.gate_system_prompt_budget_and_leak(sft_rows, max_bytes=512)
    assert not g2_fail["passed"]

    # Falsifiable mutation: inject unknown tool name -> gate_schema_and_tools must fail
    mutated = json.loads(json.dumps(sft_rows[0]))
    mutated["messages"] = [
        {"role": "system", "content": "test"},
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": '<tool_call>\n{"name": "fake_tool_xyz", "arguments": {}}\n</tool_call>'},
    ]
    g1_mut = ga.gate_schema_and_tools([mutated])
    assert not g1_mut["passed"]

    assert_units_clean(str(sft_path))
    assert_units_clean(str(dpo_path))

    hold_dir = tmp_path / "holdout"
    hold_dir.mkdir()
    shutil.copy2(holdout_path, hold_dir / holdout_path.name)
    for ev_dir in (
        ROOT / "data" / "benchmark" / "virtu_eval_v1",
        ROOT / "data" / "benchmark" / "virtu_eval_phys_v1",
        ROOT / "data" / "benchmark" / "virtu_eval_cl_v1",
        hold_dir,
    ):
        assert_no_leak(str(sft_path), str(ev_dir))
        assert_no_leak(str(dpo_path), str(ev_dir))

    # Falsifiable leak probe: plant holdout prompt into SFT copy -> assert_no_leak must exit(2)
    first_hold = json.loads(holdout_path.read_text(encoding="utf-8").splitlines()[0])
    leak_file = tmp_path / "leaked.jsonl"
    leak_file.write_text(
        json.dumps({"messages": [{"role": "user", "content": first_hold["prompt"]}, {"role": "assistant", "content": "ok"}]}, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    assert scan_corpus(str(leak_file), str(hold_dir))["hard_leaks"] == 1
    with pytest.raises(SystemExit):
        assert_no_leak(str(leak_file), str(hold_dir))


def test_six_software_track_registered_and_bundle_sandbox_clean(tmp_path: Path) -> None:
    assert "six-software" in start_train_now.TRACKS
    assert start_train_now.run_selftest() == 0

    pack_info = start_train_now.prepare_track_bundle("six-software")
    bundle = Path(pack_info["bundle_path"])
    assert bundle.is_file() and Path(str(bundle) + ".sha256").is_file()

    unpack = tmp_path / "cloud_unpack"
    with tarfile.open(bundle, "r:gz") as tar:
        local_one_click.safe_extract(tar, str(unpack))

    for req in (
        "run_six_software_real.sh",
        "train_turnkey.py",
        "train_vericut_dpo.py",
        "deploy_trained_adapter.py",
        "dataset/six_software_real_assets_sft.jsonl",
        "dataset/six_software_real_assets_dpo.jsonl",
        "dataset/six_software_real_assets_sft_ledger.json",
        "dataset/six_software_holdout.jsonl",
        "scripts/gate_all90_dataset.py",
        "scripts/wm_verifier.py",
        "scripts/corpus_unit_audit.py",
        "bridges/tool_calling_specs.py",
        "virtu_eval/contamination_check.py",
        "virtu_eval/tool_schema.py",
        "data/benchmark/virtu_eval_v1",
    ):
        assert (unpack / req).exists(), f"Missing {req} inside six-software bundle"

    assert b"\r" not in (unpack / "run_six_software_real.sh").read_bytes()

    bash_exe = _find_git_bash()
    if bash_exe:
        env = os.environ.copy()
        env["VIRTU_PYTHON"] = sys.executable
        r = subprocess.run(
            [bash_exe, str(unpack / "run_six_software_real.sh"), "--selftest"],
            cwd=str(unpack),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert r.returncode == 0, f"Extracted bundle --selftest failed:\n{r.stdout}\n{r.stderr}"
        assert "[PASS] run_six_software_real.sh --selftest completed" in r.stdout


def test_six_software_deliverable_receipt_contract_falsifiable(tmp_path: Path) -> None:
    unpack = tmp_path / "deliv"
    adp = unpack / "virtu_lora_adapter"
    adp.mkdir(parents=True)
    weights = adp / "adapter_model.safetensors"
    weights.write_bytes(b"mock-safetensors-weights")
    receipt = {
        "status": "COMPLETED",
        "track": "six-software",
        "base_model": "Qwen/Qwen3-8B",
        "dataset_sha256": "a" * 64,
        "adapter_sha256": _sha256_bytes(b"mock-safetensors-weights"),
    }
    (adp / "training_receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
    parsed = local_one_click.verify_deliverable_receipt(str(unpack))
    assert parsed["status"] == "COMPLETED"

    # Tampered weights -> RuntimeError
    weights.write_bytes(b"tampered")
    with pytest.raises(RuntimeError):
        local_one_click.verify_deliverable_receipt(str(unpack))

    # Restore weights, flip status -> FAILED -> RuntimeError
    weights.write_bytes(b"mock-safetensors-weights")
    receipt["status"] = "FAILED"
    (adp / "training_receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(RuntimeError):
        local_one_click.verify_deliverable_receipt(str(unpack))

    # Instruct base model -> RuntimeError
    receipt["status"] = "COMPLETED"
    receipt["base_model"] = "Qwen/Qwen3-8B-Instruct"
    (adp / "training_receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(RuntimeError):
        local_one_click.verify_deliverable_receipt(str(unpack))


def test_six_software_pgrep_and_gpu_id_isolation() -> None:
    import io
    import re
    from unittest import mock

    pat = start_train_now.TRACKS["six-software"]["pgrep_pattern"]
    rx = re.compile(pat)
    assert rx.search("bash run_six_software_real.sh --max-hours 4.0 --gpu-id 1")
    assert rx.search("/usr/local/miniconda3/envs/py312/bin/python /root/autodl-tmp/virtu_six_software/train_turnkey.py --data dataset/six_software_real_assets_sft.jsonl")
    assert rx.search("/usr/local/miniconda3/envs/py312/bin/python /tmp/custom_dir/train_vericut_dpo.py --data /tmp/custom_dir/dataset/six_software_real_assets_dpo.jsonl")
    assert not rx.search("/usr/local/miniconda3/envs/py312/bin/python /root/autodl-tmp/virtu_vericut_e/train_turnkey.py --data /root/autodl-tmp/virtu_vericut_e/dataset/vericut_e_training_sft.jsonl --gpu-id 0")

    captured_cmds = []

    class _FakeClient:
        def exec_command(self, cmd: str):
            captured_cmds.append(cmd)
            return None, io.BytesIO(b"18432, 97\n"), io.BytesIO(b"")

    mem, util = start_train_now._query_remote_gpu_metrics(_FakeClient(), gpu_id="1")
    assert mem == 18432.0 and util == 97.0
    assert "-i 1 " in captured_cmds[0]

    runner_txt = (PACK_DIR / "run_six_software_real.sh").read_text(encoding="utf-8")
    assert 'export CUDA_VISIBLE_DEVICES="${GPU_ID}"' in runner_txt
    assert "${CUDA_VISIBLE_DEVICES:-${GPU_ID}}" not in runner_txt


def test_pull_and_optional_deploy_ignores_nonexistent_remote_base(tmp_path: Path) -> None:
    from unittest import mock

    arc = tmp_path / "six_software_real_deliverable.tar.gz"
    adp_dir = tmp_path / "pkg" / "virtu_lora_adapter"
    adp_dir.mkdir(parents=True)
    weights = adp_dir / "adapter_model.safetensors"
    weights.write_bytes(b"mock-weights")
    receipt = {
        "status": "COMPLETED",
        "track": "six-software",
        "base_model": "Qwen/Qwen3-8B",
        "dataset_sha256": "a" * 64,
        "adapter_sha256": _sha256_bytes(b"mock-weights"),
    }
    (adp_dir / "training_receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
    with tarfile.open(arc, "w:gz") as tf:
        tf.add(adp_dir, arcname="virtu_lora_adapter")
    (tmp_path / "six_software_real_deliverable.tar.gz.sha256").write_text(
        f"{_sha256_bytes(arc.read_bytes())}  {arc.name}\n",
        encoding="utf-8",
    )

    class _FakeSFTP:
        def get(self, src: str, dst: str) -> None:
            if src.endswith(".sha256"):
                shutil.copyfile(tmp_path / "six_software_real_deliverable.tar.gz.sha256", dst)
            else:
                shutil.copyfile(arc, dst)

        def close(self) -> None:
            pass

    class _FakeClient:
        def open_sftp(self):
            return _FakeSFTP()

    recorded_cmds = []

    def _fake_run(cmd, cwd=None, check=False):
        recorded_cmds.append(list(cmd))

    local_base = tmp_path / "local_base"
    local_base.mkdir()

    try:
        with mock.patch.object(start_train_now.subprocess, "run", side_effect=_fake_run):
            pulled1 = start_train_now.pull_and_optional_deploy(
                _FakeClient(),
                "six-software",
                "/remote/dir",
                auto_deploy=True,
                deploy_tag="virtu-six-software:v1",
                base_dir="/model/ModelScope/Qwen/Qwen3-8B",
            )
            pulled2 = start_train_now.pull_and_optional_deploy(
                _FakeClient(),
                "six-software",
                "/remote/dir",
                auto_deploy=True,
                deploy_tag="virtu-six-software:v1",
                base_dir=str(local_base),
            )
        assert "--base" not in recorded_cmds[0]
        assert "--base" in recorded_cmds[1] and str(local_base) in recorded_cmds[1]
    finally:
        for pulled in (locals().get("pulled1"), locals().get("pulled2")):
            if pulled:
                shutil.rmtree(Path(pulled).parent, ignore_errors=True)
