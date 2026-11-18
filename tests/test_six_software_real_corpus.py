# -*- coding: utf-8 -*-
"""Verification & falsification tests for the 3-directory six-software real-asset corpus."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import corpus_unit_audit  # noqa: E402
from bridges.tool_calling_specs import path_traversal_gate, schema_gate  # noqa: E402
from virtu_eval import contamination_check as cc  # noqa: E402
from virtu_eval.graders import score_case  # noqa: E402
from virtu_eval.tool_schema import runtime_tool_names  # noqa: E402

OUT_DIR = ROOT / "data" / "sft" / "six_software_real_assets"
MANIFEST_PATH = OUT_DIR / "manifest.json"
SOFTWARE_KEYS = ("solidworks", "nx", "autocad", "cimco", "vericut", "sscnc")
HOLDOUT_PROJECTS = {
    "36.集流片自动焊",
    "72.一拖三口罩生产线全自动平面口罩机器",
    "79.汽车阀门组装机节气门滑阀门类非标自动化设备",
    "83.前转轮毂轴承压装机",
}
HOLDOUT_BZJ_IDS = {"BZJ-A-04", "BZJ-B-35", "BZJ-C-11", "BZJ-E-04", "BZJ-G-10"}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1 << 20)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _load_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


@pytest.fixture(scope="module")
def manifest() -> dict:
    assert MANIFEST_PATH.exists(), f"Missing manifest: {MANIFEST_PATH}"
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_manifest_deliverables_and_sha256_sidecars(manifest: dict) -> None:
    outputs = manifest["outputs"]
    for key in ("pure_sft", "train_mix", "holdout", "dpo", "kb_records", "cloud_sft", "cloud_dpo"):
        info = outputs[key]
        p = Path(info["path"])
        assert p.exists(), f"Missing deliverable {key}: {p}"
        rows = _load_jsonl(p)
        assert len(rows) == info["count"], f"Count mismatch for {key}"
        actual_sha = _sha256(p)
        assert actual_sha == info["sha256"], f"SHA mismatch for {key}"
        sidecar = Path(str(p) + ".sha256")
        assert sidecar.exists(), f"Missing sidecar {sidecar}"
        assert sidecar.read_text(encoding="utf-8").strip().startswith(actual_sha)

    ledger_path = Path(outputs["cloud_ledger"]["path"])
    assert ledger_path.exists()
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    assert ledger["count"] == outputs["cloud_sft"]["count"]
    assert ledger["output_sha256"] == outputs["cloud_sft"]["sha256"]

    cloud_dir = OUT_DIR / "cloud_pack"
    for sw in SOFTWARE_KEYS:
        for split_name in ("train", "holdout"):
            cp = cloud_dir / f"{sw}_{split_name}.jsonl"
            assert cp.exists(), f"Missing cloud_pack file: {cp}"
            crows = _load_jsonl(cp)
            assert len(crows) == manifest["cloud_pack"][sw][f"{split_name}_count"] > 0
            assert _sha256(cp) == manifest["cloud_pack"][sw][f"{split_name}_sha256"]


def test_six_software_coverage(manifest: dict) -> None:
    pure_by_sw = manifest["pure_by_software"]
    hold_by_sw = manifest["holdout_by_software"]
    dpo_rows = _load_jsonl(Path(manifest["outputs"]["dpo"]["path"]))
    dpo_sw = {r["software"] for r in dpo_rows}

    for sw in SOFTWARE_KEYS:
        assert pure_by_sw.get(sw, 0) >= 60, f"Low pure_sft count for {sw}"
        assert hold_by_sw.get(sw, 0) >= 10, f"Low holdout count for {sw}"
        assert sw in dpo_sw, f"Software missing in DPO: {sw}"


def test_disjoint_source_splits_and_zero_sha_overlap(manifest: dict) -> None:
    pure_rows = _load_jsonl(Path(manifest["outputs"]["pure_sft"]["path"]))
    hold_rows = _load_jsonl(Path(manifest["outputs"]["holdout"]["path"]))
    dpo_rows = _load_jsonl(Path(manifest["outputs"]["dpo"]["path"]))

    train_shas = {(r.get("meta") or {}).get("source_sha256") for r in pure_rows} - {None, ""}
    hold_shas = {(c.get("gold") or {}).get("source_sha256") for c in hold_rows} - {None, ""}
    assert not (train_shas & hold_shas), f"Source SHA leak: {train_shas & hold_shas}"

    for r in pure_rows + dpo_rows:
        meta = r.get("meta") or {}
        src_file = str(meta.get("source_file") or r.get("source_file") or "")
        did = str(meta.get("drawing_id") or "")
        assert did not in HOLDOUT_BZJ_IDS, f"Holdout BZJ leaked to train/dpo: {did}"
        for hp in HOLDOUT_PROJECTS:
            assert hp not in src_file, f"Holdout project leaked to train/dpo: {src_file}"
        assert "3D10-" not in src_file and "3D11-" not in src_file, f"Holdout DOCX session leaked: {src_file}"


def test_zero_contamination_against_holdout_and_benchmarks(tmp_path: Path, manifest: dict) -> None:
    hold_dir = tmp_path / "holdout_eval"
    hold_dir.mkdir(parents=True, exist_ok=True)
    hold_src = Path(manifest["outputs"]["holdout"]["path"])
    (hold_dir / "six_software_holdout.jsonl").write_text(hold_src.read_text(encoding="utf-8"), encoding="utf-8")

    for key in ("pure_sft", "train_mix"):
        res_ho = cc.scan_corpus(manifest["outputs"][key]["path"], str(hold_dir))
        assert res_ho["hard_leaks"] == 0, f"{key} leaked to holdout: {res_ho}"
        res_v3 = cc.scan_corpus(
            manifest["outputs"][key]["path"],
            str(ROOT / "data" / "benchmark" / "virtu_blind_test_v3"),
        )
        assert res_v3["hard_leaks"] == 0, f"{key} leaked to benchmark v3: {res_v3}"


def test_all_tool_calls_pass_schema_and_path_gates(manifest: dict) -> None:
    rt_names = runtime_tool_names()
    sft_paths = [
        Path(manifest["outputs"]["pure_sft"]["path"]),
        Path(manifest["outputs"]["train_mix"]["path"]),
    ] + [
        OUT_DIR / "cloud_pack" / f"{sw}_{split_name}.jsonl"
        for sw in SOFTWARE_KEYS
        for split_name in ("train", "holdout")
    ]

    tc_checked = 0
    for p in sft_paths:
        for idx, rec in enumerate(_load_jsonl(p)):
            msgs = rec.get("messages") or []
            has_tc = any(m.get("tool_calls") for m in msgs)
            if has_tc:
                tools = rec.get("tools") or []
                assert len(tools) > 0, f"{p.name}:{idx} has tool_calls without tools"
                declared = {t["function"]["name"] for t in tools}
            else:
                declared = set()
            for m in msgs:
                for tc in (m.get("tool_calls") or []):
                    fn = tc["function"]["name"]
                    assert fn in rt_names, f"{p.name}:{idx} unknown runtime tool {fn}"
                    assert fn in declared, f"{p.name}:{idx} tool {fn} omitted from row tools"
                    args = json.loads(tc["function"]["arguments"])
                    assert schema_gate(fn, args) is None, f"{p.name}:{idx} schema error: {fn} {args}"
                    assert path_traversal_gate(fn, args) is None, f"{p.name}:{idx} traversal error: {fn} {args}"
                    assert "迅雷下载" not in tc["function"]["arguments"]
                    tc_checked += 1

    # Also verify every runtime_toolcall item in six_software_holdout.jsonl
    for hrec in _load_jsonl(Path(manifest["outputs"]["holdout"]["path"])):
        if hrec.get("dimension") == "runtime_toolcall":
            gobj = json.loads(hrec["gold"]["answer"])
            fn = gobj["tool"]
            args = gobj["arguments"]
            assert fn in rt_names
            assert schema_gate(fn, args) is None
            assert path_traversal_gate(fn, args) is None
            tc_checked += 1

    assert tc_checked > 300


def test_holdout_gold_self_pass_100_percent(manifest: dict) -> None:
    hold_rows = _load_jsonl(Path(manifest["outputs"]["holdout"]["path"]))
    assert len(hold_rows) >= 90
    for rec in hold_rows:
        sc = score_case(rec["gold"]["answer"], rec["criteria"])
        assert sc["all_passed"] and sc["score"] == 100.0, f"Holdout {rec['id']} failed self-pass: {sc}"


def test_unit_audit_clean_and_surface_iges_honesty(manifest: dict) -> None:
    for key in ("pure_sft", "train_mix", "holdout", "dpo"):
        ua = corpus_unit_audit.scan(manifest["outputs"][key]["path"])
        assert ua["bad_rows"] == 0, f"corpus_unit_audit failed on {key}: {ua['examples']}"

    dpo_rows = _load_jsonl(Path(manifest["outputs"]["dpo"]["path"]))
    surf_dpo = [d for d in dpo_rows if d["category"] == "surface_only_iges_volume"]
    assert len(surf_dpo) >= 10
    for d in surf_dpo:
        assert "n_solids = 0" in d["chosen"] and "volume_mm3 = null" in d["chosen"]


def test_falsification_planted_leak_and_bad_schema_and_corrupt_units(tmp_path: Path, manifest: dict) -> None:
    # 1. Planted holdout leak must trigger contamination_check hard_leaks >= 1
    hold_rows = _load_jsonl(Path(manifest["outputs"]["holdout"]["path"]))
    hold_dir = tmp_path / "hold"
    hold_dir.mkdir()
    (hold_dir / "six_software_holdout.jsonl").write_text(
        Path(manifest["outputs"]["holdout"]["path"]).read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    poisoned = tmp_path / "poisoned_train.jsonl"
    leak_row = {"messages": [{"role": "user", "content": hold_rows[0]["prompt"]}, {"role": "assistant", "content": "leaked"}]}
    poisoned.write_text(json.dumps(leak_row, ensure_ascii=False) + "\n", encoding="utf-8")
    res = cc.scan_corpus(str(poisoned), str(hold_dir))
    assert res["hard_leaks"] >= 1, "Falsification failed: planted leak was not caught!"

    # 2. Invalid schema & external path traversal must be blocked
    assert schema_gate("cadcam_cae_stress_analysis", {"material": "Steel45"}) is not None
    assert path_traversal_gate(
        "cadcam_vericut_simulate",
        {"action": "run_simulation", "project_path": r"e:\迅雷下载\outside.VcProject"},
    ) is not None

    # 3. Corrupted inertia unit (`inertia_ixx_mm4` inflated by wrong unit exponent mm^5) must fail
    bad_unit_line = json.dumps({
        "messages": [{
            "role": "assistant",
            "content": '{"shape": "cylinder", "radius_mm": 10.0, "height_mm": 50.0, "inertia_ixx_mm4": 99999999.0, "inertia_izz_mm4": 1570796.3}',
        }]
    }, ensure_ascii=False)
    bad_unit_check = corpus_unit_audit.row_issue(bad_unit_line)
    assert bad_unit_check is not None, "Falsification failed: mm^5 inertia corruption was not flagged!"

    # 4. Fake simulation / fabricated IGES volume / missing M05 in holdout must fail deterministic grader
    sscnc_boundary = next(r for r in hold_rows if r["id"] == "boundary_sscnc_offline")
    fake_pass = score_case("SSCNC 已切换 AUTO，已完成循环启动，共 0 碰撞通过。", sscnc_boundary["criteria"])
    assert not fake_pass["all_passed"] and fake_pass["score"] < 100.0

    surf_boundary = next(r for r in hold_rows if r["id"].startswith("boundary_surf_"))
    fake_vol = score_case("该零件实体体积: 125000.0 mm³。", surf_boundary["criteria"])
    assert not fake_vol["all_passed"] and fake_vol["score"] < 100.0

    cimco_case = next(r for r in hold_rows if r["dimension"] == "cimco_macro_generation")
    broken_gcode = cimco_case["gold"]["answer"].replace("\nM05\n", "\n")
    broken_score = score_case(broken_gcode, cimco_case["criteria"])
    assert not broken_score["all_passed"] and broken_score["score"] < 100.0
