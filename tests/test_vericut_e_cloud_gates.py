# -*- coding: utf-8 -*-
"""Falsifiable regression gates for the `--track vericut-e` cloud training pipeline."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
PACK_DIR = ROOT / "cloud_train_pack"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(PACK_DIR) not in sys.path:
    sys.path.insert(0, str(PACK_DIR))

from cloud_train_pack import deploy_trained_adapter, start_train_now  # noqa: E402

EXPECTED_SFT_SHA256 = "50f16388357b76ed19520fb2da7451792597f13c76871e3b9f0cd444fce6bdd4"
EXPECTED_DPO_SHA256 = "3bcc4d609e67d9861372492df10b392c827a8e3ba7ddc123f579ab5cc250645e"


def _find_usable_bash() -> str | None:
    """Locate a working bash (avoiding WSL System32\\bash.exe when unconfigured)."""
    candidates = [
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files\Git\usr\bin\bash.exe",
        r"C:\Git\bin\bash.exe",
        shutil.which("bash") or "",
    ]
    for cand in candidates:
        if not cand or not Path(cand).exists():
            continue
        if os.name == "nt" and "system32" in cand.lower():
            continue
        return cand
    return None


@pytest.mark.parametrize(
    "script_rel",
    [
        "cloud_train_pack/run_vericut_e_training.sh",
        "cloud_train_pack/start_cloud_train_now.sh",
    ],
)
def test_vericut_e_shell_scripts_lf_hardened_and_bash_syntax(script_rel: str) -> None:
    path = ROOT / script_rel
    assert path.exists(), f"Missing cloud script: {path}"
    raw = path.read_bytes()
    assert b"\r\n" not in raw, f"{script_rel} must use strict Unix LF (\\n), found CRLF"

    text = raw.decode("utf-8")
    assert text.startswith("#!/"), f"{script_rel} must start with a shebang"
    assert "flock" in text, f"{script_rel} must enforce flock single-instance locking"
    assert "torch.matmul" in text, f"{script_rel} must include CUDA fp16 torch.matmul probe"

    for pinned in (
        "transformers>=4.51.0,<5.0.0",
        "peft>=0.13.0,<0.16.0",
        "datasets>=2.18.0,<4.0.0",
    ):
        assert pinned in text, f"{script_rel} must pin {pinned}"

    bash_exe = _find_usable_bash()
    assert bash_exe is not None, "No usable non-WSL bash binary found for bash -n verification"
    proc = subprocess.run(
        [bash_exe, "-n", str(path).replace("\\", "/")],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"bash -n failed for {script_rel}: {proc.stderr}"


def test_start_cloud_train_now_routes_vericut_e() -> None:
    text = (PACK_DIR / "start_cloud_train_now.sh").read_text(encoding="utf-8")
    assert "vericut-e" in text
    assert "run_vericut_e_training.sh" in text


def test_tracks_vericut_e_contract_and_deploy_defaults() -> None:
    cfg = start_train_now.TRACKS["vericut-e"]
    assert cfg["runner_sh"] == "run_vericut_e_training.sh"
    assert cfg["remote_dir"] == "/root/autodl-tmp/virtu_vericut_e"
    assert cfg["receipt_rel"] == "output/virtu_vericut_e/training_receipt.json"
    assert cfg["deliverable_rel"] == "output/virtu_vericut_e/virtu_vericut_e_deliverable.tar.gz"
    assert cfg["background_self"] is True
    assert "run_vericut_e_training\\.sh" in cfg["pgrep_pattern"]
    assert Path(cfg["bundle_path"]).name == "virtu_vericut_e_bundle.tar.gz"

    assert deploy_trained_adapter._resolve_probe_profile("virtu-vericut-e:latest") == "vericut96"

    captured: dict[str, str] = {}

    def _fake_pull(client, track, remote_dir, *, auto_deploy=False, deploy_tag="", base_dir=None):
        captured["track"] = track
        captured["deploy_tag"] = deploy_tag
        return None

    with (
        mock.patch.object(sys, "argv", [
            "start_train_now.py",
            "--track", "vericut-e",
            "--host", "127.0.0.1",
            "--port", "22",
            "--password", "dummy",
            "--skip-selftest",
            "--follow",
            "--auto-deploy",
        ]),
        mock.patch.object(start_train_now, "prepare_track_bundle", return_value={
            "bundle_path": cfg["bundle_path"],
            "sha256": "0" * 64,
            "reused": True,
            "size_mb": 1.0,
        }),
        mock.patch.object(start_train_now, "wait_for_instance_online", return_value=(mock.MagicMock(), {})),
        mock.patch.object(start_train_now, "upload_and_launch_remote", return_value={"attached": False, "remote_dir": cfg["remote_dir"]}),
        mock.patch.object(start_train_now, "verify_training_started", return_value={"state": "STARTED"}),
        mock.patch.object(start_train_now, "watch_training_health", return_value={"status": "COMPLETED"}),
        mock.patch.object(start_train_now, "pull_and_optional_deploy", side_effect=_fake_pull),
    ):
        rc = start_train_now.main()
    assert rc == 0
    assert captured["track"] == "vericut-e"
    assert captured["deploy_tag"] == "virtu-vericut-e:latest"


def test_prepacked_vericut_e_bundle_integrity_and_sha_rejection(tmp_path: Path) -> None:
    bundle = Path(start_train_now.TRACKS["vericut-e"]["bundle_path"])
    assert bundle.exists(), f"Pre-packed bundle missing: {bundle}"
    ok, actual_sha = start_train_now._verify_local_archive_sha(str(bundle))
    assert ok, f"Bundle sidecar SHA256 verification failed: {actual_sha}"

    with tarfile.open(bundle, "r:gz") as tar:
        members = {m.name: m for m in tar.getmembers()}
        required_members = [
            "run_vericut_e_training.sh",
            "train_turnkey.py",
            "scripts/train_dpo_all90.py",
            "scripts/gate_all90_dataset.py",
            "virtu_eval/contamination_check.py",
            "scripts/corpus_unit_audit.py",
            "dataset/vericut_e_training_sft.jsonl",
            "dataset/vericut_e_training_dpo.jsonl",
            "dataset/vericut_e_training_sft_ledger.json",
            "data/sft/vericut_e_training/vericut_e_holdout.jsonl",
        ]
        for req in required_members:
            assert req in members, f"Missing tar member {req} in {bundle.name}"

        assert any(name.startswith("data/benchmark/virtu_eval_v1/") for name in members), "Missing virtu_eval_v1 benchmark files"
        assert any(name.startswith("data/benchmark/virtu_eval_phys_v1/") for name in members), "Missing virtu_eval_phys_v1 benchmark files"
        assert any(name.startswith("data/benchmark/virtu_eval_cl_v1/") for name in members), "Missing virtu_eval_cl_v1 benchmark files"

        runner_info = members["run_vericut_e_training.sh"]
        assert (runner_info.mode & 0o777) == 0o755, f"Expected 0o755 on run_vericut_e_training.sh, got {oct(runner_info.mode)}"
        runner_bytes = tar.extractfile(runner_info).read()  # type: ignore[union-attr]
        assert b"\r\n" not in runner_bytes, "Bundled run_vericut_e_training.sh contains CRLF"

        sft_bytes = tar.extractfile(members["dataset/vericut_e_training_sft.jsonl"]).read()  # type: ignore[union-attr]
        dpo_bytes = tar.extractfile(members["dataset/vericut_e_training_dpo.jsonl"]).read()  # type: ignore[union-attr]
        ledger_raw = tar.extractfile(members["dataset/vericut_e_training_sft_ledger.json"]).read()  # type: ignore[union-attr]

        assert hashlib.sha256(sft_bytes).hexdigest() == EXPECTED_SFT_SHA256
        assert hashlib.sha256(dpo_bytes).hexdigest() == EXPECTED_DPO_SHA256

        ledger = json.loads(ledger_raw.decode("utf-8"))
        assert ledger["files"]["vericut_e_training_sft.jsonl"]["sha256"] == EXPECTED_SFT_SHA256
        assert ledger["files"]["vericut_e_training_dpo.jsonl"]["sha256"] == EXPECTED_DPO_SHA256

    # Falsification 1: corrupted .sha256 sidecar MUST fail verification
    bad_bundle = tmp_path / bundle.name
    shutil.copy2(bundle, bad_bundle)
    (tmp_path / (bundle.name + ".sha256")).write_text("0" * 64 + f"  {bundle.name}\n", encoding="utf-8")
    bad_ok, _ = start_train_now._verify_local_archive_sha(str(bad_bundle))
    assert not bad_ok, "Corrupted .sha256 sidecar was falsely accepted"

    # Falsification 2: mismatched ledger vs dataset MUST fail _build_vericut_e_bundle
    fake_pack = tmp_path / "pack"
    (fake_pack / "dataset").mkdir(parents=True)
    shutil.copy2(PACK_DIR / "run_vericut_e_training.sh", fake_pack / "run_vericut_e_training.sh")
    (fake_pack / "dataset" / "vericut_e_training_sft.jsonl").write_text('{"messages":[]}\n', encoding="utf-8")
    (fake_pack / "dataset" / "vericut_e_training_dpo.jsonl").write_text('{"prompt":"p","chosen":"c","rejected":"r"}\n', encoding="utf-8")
    (fake_pack / "dataset" / "vericut_e_training_sft_ledger.json").write_text(
        json.dumps({
            "output_sha256": "f" * 64,
            "files": {
                "vericut_e_training_sft.jsonl": {"sha256": "f" * 64},
                "vericut_e_training_dpo.jsonl": {"sha256": "e" * 64},
            },
        }),
        encoding="utf-8",
    )
    with mock.patch.object(start_train_now, "PACK_DIR", str(fake_pack)):
        with pytest.raises(SystemExit):
            start_train_now._build_vericut_e_bundle(str(tmp_path / "tampered.tar.gz"))


def test_vericut_e_pgrep_isolation_from_other_tracks() -> None:
    import re

    pat = start_train_now.TRACKS["vericut-e"]["pgrep_pattern"]
    rx = re.compile(pat)
    assert rx.search("bash run_vericut_e_training.sh --fg --gpu-id 0")
    assert rx.search("/root/venv25/bin/python -u /root/autodl-tmp/virtu_vericut_e/train_turnkey.py --data dataset/vericut_e_training_sft.jsonl")
    assert rx.search("/root/venv25/bin/python -u /root/autodl-tmp/virtu_vericut_e/scripts/train_dpo_all90.py --data dataset/vericut_e_training_dpo.jsonl")
    assert not rx.search(
        "/root/venv25/bin/python -u /root/autodl-tmp/virtu_chain/vericut96-v2/train_turnkey.py "
        "--base /model/ModelScope/Qwen/Qwen3-8B --data dataset_v2/vericut96_v2_sft_mix.jsonl --gpu-id 1"
    )
    assert not rx.search("bash run_vericut96.sh --fg --gpu-id 1")


def test_autodiff_probe_multiline_heading_and_swapped_falsification() -> None:
    good_multiline = (
        "### ✅ **红色 (Red)**\n"
        "- **代表：Gouge（过切 / 刀具切入工件）**\n"
        "### ✅ **蓝色 (Blue)**\n"
        "- **代表：Excess（残料过多 / 刀具未切除足够材料）**\n"
        "### ✅ **绿色 (Green)**\n"
        "- **代表：In-tolerance（在公差内 / 合格）**\n"
        "发现红色时立即停止仿真并修正刀路。"
    )
    res_good = deploy_trained_adapter.evaluate_vericut_autodiff_probe(good_multiline)
    assert res_good["passed"] is True, res_good

    swapped_multiline = good_multiline.replace(
        "Excess（残料过多 / 刀具未切除足够材料）",
        "过切（Gouge）",
    )
    res_bad = deploy_trained_adapter.evaluate_vericut_autodiff_probe(swapped_multiline)
    assert res_bad["passed"] is False and "swapped_meaning:blue" in res_bad.get("reason", ""), res_bad
