# -*- coding: utf-8 -*-
"""tests/test_vericut_e_training_extractor.py — Regression & falsifiable gates for E:\\training extraction."""

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
SCRIPTS_DIR = ROOT / "scripts"
for _p in (str(ROOT), str(SCRIPTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import extract_e_training_vericut as ext  # noqa: E402
import gate_all90_dataset as g90  # noqa: E402
import train_dpo_all90 as dpo_mod  # noqa: E402
from corpus_unit_audit import scan as unit_scan  # noqa: E402
from virtu_eval.contamination_check import scan_corpus  # noqa: E402


E_TRAINING = Path(r"E:\training")
OUT_DIR = ROOT / "data" / "train" / "vericut_e_training_v1"
TRAIN_JSONL = OUT_DIR / "train" / "vericut_e_training_agent_sft.jsonl"
HOLDOUT_JSONL = OUT_DIR / "holdout" / "vericut_e_training_holdout.jsonl"
DPO_JSONL = OUT_DIR / "dpo" / "vericut_e_training_dpo.jsonl"
CATALOG_JSON = OUT_DIR / "catalog" / "e_training_catalog.json"


def test_discover_deduplicates_mixed_case_vcproject(tmp_path):
    """Windows NTFS mixed-case `.VcProject` and `.vcproject` must never be double-counted."""
    f1 = tmp_path / "sample_a.vcproject"
    f2 = tmp_path / "sample_b.VcProject"
    f1.write_text("<VcProject Version='9.6' Unit='millimeter'/>", encoding="utf-8")
    f2.write_text("<VcProject Version='9.6' Unit='inch'/>", encoding="utf-8")
    buckets = ext.discover_e_training_assets(tmp_path)
    assert len(buckets["projects"]) == 2
    names = sorted(p.name for p in buckets["projects"])
    assert names == ["sample_a.vcproject", "sample_b.VcProject"]


def test_parse_vcproject_preserves_units_and_autodiff(tmp_path):
    p = tmp_path / "demo_session_15m.vcproject"
    p.write_text(
        """<?xml version="1.0"?>
<VcProject Version="9.6" Unit="inch" ProductName="Vericut">
  <Log>demo.log</Log>
  <AutoDiff Method="solid" Type="gouge" Report="on">
    <Solid><Gouge Tol="0.002"/><Excess Tol="0.005"/></Solid>
  </AutoDiff>
  <Setup Name="1" Active="on">
    <Machine Up="Z+"><File>vmill.mch</File><Collision Detect="on"/><Travel Beyond="on" LogError="on"/></Machine>
    <Control><File>fanuc.ctl</File></Control>
    <ToolMan><Library>tools.tls</Library></ToolMan>
    <NCPrograms Type="gcode"><NCProgram Use="on"><File>part.mcd</File></NCProgram></NCPrograms>
  </Setup>
</VcProject>""",
        encoding="utf-8",
    )
    parsed = ext.parse_vcproject(p, tmp_path)
    assert parsed["unit"] == "inch"
    assert parsed["autodiff"]["gouge_tol"] == "0.002"
    assert parsed["autodiff"]["excess_tol"] == "0.005"
    assert parsed["inferred_session_group"] == "15"
    assert parsed["setups"][0]["machine_file"] == "vmill.mch"
    assert parsed["setups"][0]["nc_programs"] == [{"file": "part.mcd", "use": "on"}]


@pytest.mark.skipif(not E_TRAINING.exists(), reason="E:\\training not mounted")
def test_extracted_e_training_artifacts_complete_and_disjoint():
    assert CATALOG_JSON.exists(), "Run scripts/extract_e_training_vericut.py first"
    assert TRAIN_JSONL.exists() and HOLDOUT_JSONL.exists() and DPO_JSONL.exists()

    cat = json.loads(CATALOG_JSON.read_text(encoding="utf-8"))
    assert cat["counts"]["pdfs"] == 90
    assert cat["counts"]["projects"] == 80
    assert cat["counts"]["machines"] == 45
    assert cat["counts"]["controls"] == 31
    assert cat["counts"]["tool_libs"] == 65
    assert cat["counts"]["nc_programs"] >= 73

    units = {p["unit"] for p in cat["projects"]}
    assert units == {"inch", "millimeter"}

    train_rows = [json.loads(l) for l in TRAIN_JSONL.read_text(encoding="utf-8").splitlines() if l.strip()]
    hold_rows = [json.loads(l) for l in HOLDOUT_JSONL.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(train_rows) >= 400
    assert len(hold_rows) >= 80

    train_shas = {r["evidence_sha256"] for r in train_rows}
    hold_shas = {r["evidence_sha256"] for r in hold_rows}
    assert len(train_shas & hold_shas) == 0, "Zero shared evidence SHA256 allowed between train & holdout"

    train_prompts = {r["messages"][1]["content"] for r in train_rows}
    hold_prompts = {r["messages"][1]["content"] for r in hold_rows}
    assert len(train_prompts & hold_prompts) == 0


@pytest.mark.skipif(not TRAIN_JSONL.exists(), reason="Extracted train JSONL missing")
def test_extracted_datasets_pass_all_repo_gates():
    rep = g90.run_all_gates(
        TRAIN_JSONL,
        holdout_path=HOLDOUT_JSONL,
        require_provenance=True,
        max_derive_ratio=3,
        write_ledger=False,
    )
    assert rep["passed"] is True, json.dumps(rep, ensure_ascii=False, indent=2)
    assert rep["gates"]["gate_8_falsifiable_mutation_probe"]["mutated_probe_caught"] is True

    kb_hold = ROOT / "knowledge_base/six_software/training/datasets/vericut_holdout.jsonl"
    if kb_hold.exists():
        rep_kb = g90.run_all_gates(
            TRAIN_JSONL,
            holdout_path=kb_hold,
            require_provenance=True,
            max_derive_ratio=3,
            write_ledger=False,
        )
        assert rep_kb["passed"] is True

    assert scan_corpus(str(TRAIN_JSONL))["hard_leaks"] == 0
    assert scan_corpus(str(HOLDOUT_JSONL))["hard_leaks"] == 0
    assert unit_scan(str(TRAIN_JSONL))["bad_rows"] == 0
    assert unit_scan(str(HOLDOUT_JSONL))["bad_rows"] == 0

    pairs = dpo_mod.validate_dpo_pairs(DPO_JSONL)
    assert len(pairs) >= 80
    assert scan_corpus(str(DPO_JSONL))["hard_leaks"] == 0
    assert unit_scan(str(DPO_JSONL))["bad_rows"] == 0


def test_gate_catches_unknown_vericut_hallucinated_tool(tmp_path):
    """Falsifiable negative probe: inventing `vericut.run_com` must fail Gate 1."""
    bad = tmp_path / "bad_vericut.jsonl"
    row = {
        "software": "vericut",
        "source_run_id": "bad_1",
        "evidence_sha256": "a" * 64,
        "messages": [
            {"role": "system", "content": ext.SYS_VERICUT_AGENT},
            {"role": "user", "content": "运行 VERICUT COM"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "vericut.run_com", "arguments": "{}"}}],
            },
            {"role": "tool", "tool_call_id": "c1", "name": "vericut.run_com", "content": "{}"},
            {"role": "assistant", "content": "ok"},
        ],
    }
    bad.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
    rep = g90.run_all_gates(bad, require_provenance=True, write_ledger=False)
    assert rep["passed"] is False
    assert rep["gates"]["gate_1_schema_and_tools"]["passed"] is False


def _find_bash_exe() -> str | None:
    git_bash = Path(r"C:\Git\bin\bash.exe")
    if git_bash.exists():
        return str(git_bash)
    return shutil.which("bash")


def test_vericut96_cloud_datasets_clean_and_disjoint():
    pack_ds = ROOT / "cloud_train_pack" / "dataset"
    sft_p = pack_ds / "vericut96_sft_mix.jsonl"
    sft_led = pack_ds / "vericut96_sft_mix_ledger.json"
    dpo_p = pack_ds / "vericut96_dpo_mix.jsonl"
    dpo_led = pack_ds / "vericut96_dpo_mix_ledger.json"

    for p in (sft_p, sft_led, dpo_p, dpo_led):
        assert p.exists(), f"Missing cloud dataset artifact: {p}"

    sft_sha = hashlib.sha256(sft_p.read_bytes()).hexdigest()
    dpo_sha = hashlib.sha256(dpo_p.read_bytes()).hexdigest()
    assert json.loads(sft_led.read_text(encoding="utf-8"))["output_sha256"] == sft_sha
    assert json.loads(dpo_led.read_text(encoding="utf-8"))["output_sha256"] == dpo_sha

    sft_rows = [json.loads(ln) for ln in sft_p.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(sft_rows) == 2190
    assert scan_corpus(str(sft_p))["hard_leaks"] == 0
    assert scan_corpus(str(dpo_p))["hard_leaks"] == 0
    assert unit_scan(str(sft_p))["bad_rows"] == 0
    assert unit_scan(str(dpo_p))["bad_rows"] == 0

    pairs = dpo_mod.validate_dpo_pairs(dpo_p)
    assert len(pairs) == 162

    if HOLDOUT_JSONL.exists():
        hold_prompts = {
            json.loads(ln)["messages"][1]["content"]
            for ln in HOLDOUT_JSONL.read_text(encoding="utf-8").splitlines()
            if ln.strip()
        }
        sft_prompts = {r["messages"][1]["content"] for r in sft_rows}
        assert len(sft_prompts & hold_prompts) == 0


def test_vericut96_shell_scripts_lf_and_bash_syntax():
    bash_exe = _find_bash_exe()
    for rel in ("cloud_train_pack/run_vericut96.sh", "cloud_train_pack/start_cloud_train_now.sh"):
        p = ROOT / rel
        assert p.exists(), f"Missing script: {p}"
        raw = p.read_bytes()
        assert b"\r\n" not in raw, f"CRLF detected in {rel}"
        if bash_exe:
            proc = subprocess.run([bash_exe, "-n", str(p)], capture_output=True, text=True, encoding="utf-8")
            assert proc.returncode == 0, f"bash -n failed for {rel}: {proc.stderr}"


def test_vericut96_bundle_isolated_unpack_and_stage1_gates(tmp_path):
    pack_dir = str(ROOT / "cloud_train_pack")
    if pack_dir not in sys.path:
        sys.path.insert(0, pack_dir)
    import local_one_click
    import start_train_now

    assert "vericut96" in start_train_now.TRACKS
    cfg = start_train_now.TRACKS["vericut96"]
    assert cfg["runner_sh"] == "run_vericut96.sh"
    assert cfg["background_self"] is True
    assert cfg["receipt_rel"] == "output/virtu_vericut96/training_receipt.json"

    bundle = Path(cfg["bundle_path"])
    sha_file = Path(str(bundle) + ".sha256")
    assert bundle.exists() and sha_file.exists(), "Run start_train_now.py --prepare-only --track vericut96 first"
    ok, detail = start_train_now._verify_local_archive_sha(str(bundle))
    assert ok, f"Bundle SHA256 mismatch: {detail}"

    with tarfile.open(bundle, "r:gz") as tar:
        names = set(tar.getnames())
        for req in (
            "run_vericut96.sh",
            "train_turnkey.py",
            "dataset/vericut96_sft_mix.jsonl",
            "dataset/vericut96_sft_mix_ledger.json",
            "dataset/vericut96_dpo_mix.jsonl",
            "dataset/vericut96_dpo_mix_ledger.json",
            "scripts/train_dpo_all90.py",
            "scripts/gate_all90_dataset.py",
            "virtu_eval/contamination_check.py",
            "data/benchmark/virtu_eval_v1/boundary.jsonl",
            "data/benchmark/virtu_eval_phys_v1/physics.jsonl",
            "data/benchmark/virtu_eval_cl_v1/toolrouting.jsonl",
        ):
            assert req in names, f"Missing tar member: {req}"
        for m in tar.getmembers():
            if m.name.endswith(".sh"):
                assert (m.mode & 0o111) != 0, f"Script not executable in tar: {m.name} mode={oct(m.mode)}"
                data = tar.extractfile(m).read()
                assert b"\r\n" not in data, f"CRLF in tarball script: {m.name}"
        local_one_click.safe_extract(tar, str(tmp_path))

    env = dict(os.environ)
    env["PYTHONPATH"] = f"{tmp_path}{os.pathsep}{tmp_path / 'scripts'}"
    env["PYTHONUTF8"] = "1"

    stage1_probe = (
        "import os, json, hashlib; "
        "from virtu_eval.contamination_check import assert_no_leak; "
        "from corpus_unit_audit import assert_units_clean; "
        "from train_dpo_all90 import validate_dpo_pairs; "
        "sft='dataset/vericut96_sft_mix.jsonl'; dpo='dataset/vericut96_dpo_mix.jsonl'; "
        "assert hashlib.sha256(open(sft,'rb').read()).hexdigest() == json.load(open('dataset/vericut96_sft_mix_ledger.json'))['output_sha256']; "
        "assert hashlib.sha256(open(dpo,'rb').read()).hexdigest() == json.load(open('dataset/vericut96_dpo_mix_ledger.json'))['output_sha256']; "
        "[assert_no_leak(sft, os.path.join('data','benchmark',b)) for b in ('virtu_eval_v1','virtu_eval_phys_v1','virtu_eval_cl_v1')]; "
        "[assert_no_leak(dpo, os.path.join('data','benchmark',b)) for b in ('virtu_eval_v1','virtu_eval_phys_v1','virtu_eval_cl_v1')]; "
        "assert_units_clean(sft); assert_units_clean(dpo); "
        "assert len(validate_dpo_pairs(dpo)) == 162"
    )
    for cmd in (
        [sys.executable, "-c", stage1_probe],
        [sys.executable, "train_turnkey.py", "--selftest"],
        [sys.executable, "scripts/train_dpo_all90.py", "--self-test"],
        [sys.executable, "scripts/gate_all90_dataset.py", "--self-test"],
    ):
        proc = subprocess.run(cmd, cwd=tmp_path, env=env, capture_output=True, text=True, encoding="utf-8")
        assert proc.returncode == 0, f"Isolated command failed ({cmd}):\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
