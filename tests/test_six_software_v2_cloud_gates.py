# -*- coding: utf-8 -*-
"""Falsifiable offline & bundle gates for six-software-v2 cloud training & deploy track."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tarfile
from pathlib import Path
from typing import Any, Dict, List

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "cloud_train_pack") not in sys.path:
    sys.path.insert(0, str(ROOT / "cloud_train_pack"))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import build_six_software_v2_corpus as bv2
import start_train_now as stn
import train_vericut_dpo as tvd


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1 << 16):
            h.update(chunk)
    return h.hexdigest()


def test_six_software_v2_ledger_and_counts() -> None:
    ds_dir = ROOT / "cloud_train_pack" / "dataset"
    v1_sft = ds_dir / "six_software_real_assets_sft.jsonl"
    v1_dpo = ds_dir / "six_software_real_assets_dpo.jsonl"
    v2_sft = ds_dir / "six_software_v2_sft.jsonl"
    v2_dpo = ds_dir / "six_software_v2_dpo.jsonl"
    v2_ledger = ds_dir / "six_software_v2_sft_ledger.json"

    v1_sft_rows = [json.loads(ln) for ln in v1_sft.read_text(encoding="utf-8").splitlines() if ln.strip()]
    v1_dpo_rows = [json.loads(ln) for ln in v1_dpo.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(v1_sft_rows) == 850
    assert len(v1_dpo_rows) == 90

    v2_sft_rows = [json.loads(ln) for ln in v2_sft.read_text(encoding="utf-8").splitlines() if ln.strip()]
    v2_dpo_rows = [json.loads(ln) for ln in v2_dpo.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(v2_sft_rows) == 950
    assert len(v2_dpo_rows) == 164

    sft_sha = _sha256(v2_sft)
    dpo_sha = _sha256(v2_dpo)
    assert Path(str(v2_sft) + ".sha256").read_text(encoding="utf-8").split()[0].lower() == sft_sha
    assert Path(str(v2_dpo) + ".sha256").read_text(encoding="utf-8").split()[0].lower() == dpo_sha

    meta = json.loads(v2_ledger.read_text(encoding="utf-8"))
    assert meta["track"] == "six-software-v2"
    assert meta["output_sha256"] == sft_sha
    assert meta["files"]["six_software_v2_sft.jsonl"]["sha256"] == sft_sha
    assert meta["files"]["six_software_v2_dpo.jsonl"]["sha256"] == dpo_sha
    assert meta["files"]["six_software_v2_dpo.jsonl"]["rows"] == 164
    assert tvd._verify_dpo_ledger(v2_dpo, v2_ledger) == dpo_sha


def test_six_software_v2_anchors_and_zero_leak_to_deploy_probes() -> None:
    ds_dir = ROOT / "cloud_train_pack" / "dataset"
    v2_sft_rows = [json.loads(ln) for ln in (ds_dir / "six_software_v2_sft.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]
    v2_dpo_rows = [json.loads(ln) for ln in (ds_dir / "six_software_v2_dpo.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]

    bv2.assert_no_deploy_probe_overlap(v2_sft_rows, "six_software_v2_sft")
    bv2.assert_no_deploy_probe_overlap(v2_dpo_rows, "six_software_v2_dpo")

    # Falsifiable: synthetic leak of exact deploy probe must raise SystemExit
    with pytest.raises(SystemExit):
        bv2.assert_no_deploy_probe_overlap(
            [{"messages": [{"role": "user", "content": "Lamé 内径 Di=60 mm，外径 Do=120 mm，内压 Pi=20 MPa 求 σ_θ"}]}],
            "synthetic_lame_leak",
        )
    with pytest.raises(SystemExit):
        bv2.assert_no_deploy_probe_overlap(
            [{"messages": [{"role": "user", "content": "FANUC Ø60 棒料台阶 Ø38 长 20 mm 总长 45 mm G71 车削程序"}]}],
            "synthetic_fanuc_leak",
        )

    anchor_rows = [
        r
        for r in v2_sft_rows
        if (r.get("meta") or {}).get("task_type") == "v2_canonical_anti_regression"
        or "anti_regression" in str((r.get("meta") or {}).get("task_type") or "")
    ]
    anchor_families = {(r.get("meta") or {}).get("family") for r in anchor_rows}
    assert {"lame_closed_form", "fanuc_g71_safety", "autodiff_triage", "coordinate_unit_safety"}.issubset(anchor_families)

    # All v2 DPO pairs in our targeted categories must never contain unsafe G00 Z- plunges in chosen
    for idx, p in enumerate(v2_dpo_rows):
        if p.get("source") == "v2_anti_regression_dpo":
            assert p["chosen"].strip() != p["rejected"].strip(), f"DPO[{idx}] chosen==rejected"
            if p.get("category") == "fanuc_g71_safety_dpo":
                bv2._verify_nc_program_safe(p["chosen"])


def test_six_software_v2_track_registration_and_isolation() -> None:
    assert "six-software-v2" in stn.TRACKS
    cfg = stn.TRACKS["six-software-v2"]
    assert cfg["remote_dir"] == "/root/autodl-tmp/virtu_six_software_v2"
    assert cfg["deliverable_rel"] == "output/six_software_real/six_software_v2_deliverable.tar.gz"
    assert stn.default_deploy_tag("six-software-v2") == "virtu-six-software:v2"

    pat = re.compile(cfg["pgrep_pattern"])
    assert pat.search("bash /root/autodl-tmp/virtu_six_software_v2/run_six_software_real.sh --fg --qlora --track six-software-v2")
    assert pat.search("python train_turnkey.py --data dataset/six_software_v2_sft.jsonl")
    assert pat.search("python train_vericut_dpo.py --data dataset/six_software_v2_dpo.jsonl")

    # Must NOT collide with v1 or vericut tracks
    assert not pat.search("python /root/autodl-tmp/virtu_six_software/train_turnkey.py --data dataset/six_software_real_assets_sft.jsonl")
    assert not pat.search("bash /root/autodl-tmp/virtu_vericut_e/run_vericut_e_training.sh --fg --gpu-id 0")
    assert not pat.search("python /root/autodl-tmp/virtu_vericut96_v2/train_turnkey.py --data dataset/vericut96_v2_sft.jsonl")


def test_six_software_v2_bundle_contains_required_artifacts() -> None:
    bundle = Path(stn.TRACKS["six-software-v2"]["bundle_path"])
    assert bundle.is_file(), f"Missing v2 bundle: {bundle}"
    ok, detail = stn._verify_local_archive_sha(str(bundle))
    assert ok, detail

    with tarfile.open(bundle, "r:gz") as tar:
        names = set(tar.getnames())
        required = {
            "run_six_software_real.sh",
            "train_turnkey.py",
            "train_vericut_dpo.py",
            "deploy_trained_adapter.py",
            "dataset/six_software_v2_sft.jsonl",
            "dataset/six_software_v2_dpo.jsonl",
            "dataset/six_software_v2_sft_ledger.json",
        }
        missing = required - names
        assert not missing, f"v2 bundle missing files: {missing}"
        sh_member = tar.getmember("run_six_software_real.sh")
        sh_bytes = tar.extractfile(sh_member).read()
        assert b"\r" not in sh_bytes, "run_six_software_real.sh inside tarball must be pure LF"


def test_six_software_v2_upload_forwards_v2_cli_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    bundle = Path(stn.TRACKS["six-software-v2"]["bundle_path"])
    exec_cmds: List[str] = []
    uploaded: List[str] = []

    class _FakeOut:
        def read(self) -> bytes:
            return b""

    class _FakeSftp:
        def put(self, local_path: str, remote_path: str) -> None:
            uploaded.append(remote_path)

        def close(self) -> None:
            pass

    class _FakeClient:
        def exec_command(self, cmd: str, **kwargs: Any):
            exec_cmds.append(cmd)
            return None, _FakeOut(), _FakeOut()

        def open_sftp(self) -> _FakeSftp:
            return _FakeSftp()

    def _fake_exec_checked(client, cmd: str, desc: str) -> str:
        exec_cmds.append(cmd)
        return "LAUNCHED"

    monkeypatch.setattr(stn.local_one_click, "_exec_checked", _fake_exec_checked)
    meta = stn.upload_and_launch_remote(
        _FakeClient(),
        "six-software-v2",
        str(bundle),
        max_hours=3.5,
        epochs=3,
        lr="1.2e-4",
        qlora=True,
        gpu_id=1,
    )
    assert meta["attached"] is False
    joined = "\n".join(exec_cmds)
    assert "--sft-data dataset/six_software_v2_sft.jsonl" in joined
    assert "--dpo-data dataset/six_software_v2_dpo.jsonl" in joined
    assert "--ledger dataset/six_software_v2_sft_ledger.json" in joined
    assert "--deliverable-name six_software_v2_deliverable.tar.gz" in joined
    assert "--track six-software-v2" in joined
    assert "--gpu-id 1" in joined
    assert "--qlora" in joined
    assert any(p.endswith("/virtu_six_software_v2_bundle.tar.gz") for p in uploaded)


def test_controlled_dpo_sft_ref_and_shell_flags() -> None:
    sh_txt = (ROOT / "cloud_train_pack" / "run_six_software_real.sh").read_text(encoding="utf-8")
    assert "\r\n" not in sh_txt
    assert "--reuse-sft" in sh_txt
    assert "--dpo-grad-accum" in sh_txt
    assert "--dpo-ref-mode" in sh_txt
    assert 'DPO_EPOCHS="1"' in sh_txt
    assert 'DPO_LR="5e-6"' in sh_txt
    assert 'DPO_REF_MODE="sft"' in sh_txt
    assert 'CUDA_VISIBLE_DEVICES="${GPU_ID}" "${PY}" "${SCRIPT_DIR}/train_vericut_dpo.py"' in sh_txt

    dpo_txt = (ROOT / "cloud_train_pack" / "train_vericut_dpo.py").read_text(encoding="utf-8")
    assert 'adapter_name="sft_ref"' in dpo_txt
    assert 'delete_adapter("sft_ref")' in dpo_txt
    assert 'default="sft"' in dpo_txt


def test_run_six_software_real_fg_precedence_and_repair_gates() -> None:
    """Verify --fg beats trailing --bg during self-daemonize, and local repair commit/semantic gates hold."""
    sh_txt = (ROOT / "cloud_train_pack" / "run_six_software_real.sh").read_text(encoding="utf-8")
    assert "EXPLICIT_FG=0" in sh_txt
    assert "EXPLICIT_FG=1" in sh_txt
    assert 'if [[ "${EXPLICIT_FG}" -eq 0 ]]; then' in sh_txt

    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    import run_full_repair_v9 as r9
    import g71_semantic_check as g71sem

    assert r9.free_commit_mb() > 0
    r9_src = (ROOT / "scripts" / "run_full_repair_v9.py").read_text(encoding="utf-8")
    assert "HF_DEACTIVATE_ASYNC_LOAD" in r9_src
    assert "ProxyHandler({})" in r9_src
    assert "free_commit_mb" in r9_src

    # Falsification check on G71 semantic checker: good stepped shaft passes; wrong shoulder/depth fails
    good_nc = "\n".join([
        "%", "O0001", "G50 S1800", "G96 S150 M03", "T0101", "G00 X62.0 Z2.0",
        "G71 U1.5 R0.75", "G71 P10 Q20 U0.4 W0.1 F0.25",
        "N10 G00 X38.0", "G01 Z0.0 F0.2", "Z-20.0", "X60.0", "Z-45.0",
        "N20 X62.0", "G00 X100.0 Z80.0", "G70 P10 Q20 F0.15", "G00 X100.0 Z80.0", "M30", "%",
    ])
    assert g71sem.check_g71_step_shaft(good_nc)["passed"] is True

    bad_nc = good_nc.replace("Z-45.0", "Z-25.0").replace("G71 U1.5 R0.75", "G71 U-1.5 R0.75")
    bad_res = g71sem.check_g71_step_shaft(bad_nc)
    assert bad_res["passed"] is False
    assert "G71_first_block_negative_U" in bad_res["violations"]
    assert "profile_total_too_short(need Z~-45)" in bad_res["violations"]
