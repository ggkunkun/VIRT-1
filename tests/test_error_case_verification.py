# -*- coding: utf-8 -*-
"""可证伪测试：错误案例复现核验。

反证目标：
* 日志里没有讲义点名的行号/碰撞对象 => 不得判 reproduced；
* 机床 Z 轴偏移为 0 但讲义要求 32.25" => 必须判复现；
* 讲义只说「值错误」而没有可独立计算的目标值 => 只能标 attested，不得标 fully_reproduced；
* 缺少日志 => unmeasured，不得补位成通过。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.verify_error_cases as vec

WORKSPACE = Path(__file__).resolve().parents[1]
SHIPPED = WORKSPACE / "knowledge_base" / "error_case_verification.json"
SHIPPED_INDEX = WORKSPACE / "knowledge_base" / "training_case_index.json"


def _fake_index(tmp_path: Path, case_id: str = "lathe_session_day1") -> Path:
    index = tmp_path / "index.json"
    index.write_text(json.dumps({
        "generated_at_utc": "2026-11-17T00:00:00+00:00",
        "cases": [{
            "case_id": case_id,
            "status": "error_demo",
            "required_capability": "turning",
            "path": f"{case_id}.vcproject",
            "sha256": "a" * 64,
            "machine": {"file": "m.mch"},
            "defect_evidence": [{"quote": "should be 32.25” from the machine origin",
                                 "session": "3L", "page": 1}],
        }],
        "standalone_programs": [],
    }, ensure_ascii=False), encoding="utf-8")
    return index


def test_good_log_reproduces_and_bad_log_does_not(tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()
    index = _fake_index(tmp_path)
    (logs / "lathe_session_day1.log").write_text(
        "*** 处理数控程序文件\n错误:在 23 行:N1100 Z-1.81 ,刀具 \"1\" 碰撞 \"Jaws\"\n",
        encoding="utf-8")
    report = vec.build_report(index, logs, tmp_path)
    entry = report["cases"][0]
    assert entry["reproduced"] is True
    assert "N1100 Z-1.81" in entry["observed"][0]

    (logs / "lathe_session_day1.log").write_text(
        "*** 处理数控程序文件\nEND-OF-FILE\n", encoding="utf-8")
    report = vec.build_report(index, logs, tmp_path)
    entry = report["cases"][0]
    assert entry["reproduced"] is False
    assert entry["missing_patterns"]


def test_missing_log_is_unmeasured_not_pass(tmp_path):
    index = _fake_index(tmp_path)
    report = vec.build_report(index, tmp_path / "no_logs", tmp_path)
    entry = report["cases"][0]
    assert entry["reproduced"] is None
    assert entry["confidence"] == "unmeasured"
    assert report["summary"]["not_reproduced_or_unmeasured"] == 1


def test_machine_offset_zero_matches_manual_required_offset(tmp_path):
    mch = tmp_path / "m.mch"
    mch.write_text(
        '<?xml version="1.0"?><VcMachine><Component Name="Z" Type="linear">'
        '<Position X="0" Y="0" Z="0"/></Component></VcMachine>',
        encoding="utf-8")
    case = {"machine": {"file": "m.mch"},
            "defect_evidence": [{"quote": "The Z axis Zero position should be 32.25” "
                                          "from the machine origin"}]}
    result = vec._verify_machine_offset(case, tmp_path)
    assert result["reproduced"] is True
    assert "32.25" in result["expected"]
    assert "Z': '0'" in result["observed"] or "'Z': '0'" in result["observed"]

    # 反过来：坐标已经改对 => 不得再判「复现」
    mch.write_text(
        '<?xml version="1.0"?><VcMachine><Component Name="Z" Type="linear">'
        '<Position X="0" Y="0" Z="32.25"/></Component></VcMachine>',
        encoding="utf-8")
    result = vec._verify_machine_offset(case, tmp_path)
    assert result["reproduced"] is False


def test_tool_optimization_defect_is_attested_not_measured(tmp_path):
    project = tmp_path / "p.vcproject"
    project.write_text(
        '<?xml version="1.0"?><VcProject><File>t.tls</File></VcProject>',
        encoding="utf-8")
    (tmp_path / "t.tls").write_text(
        "<CGTechToolLibrary><Optimization/><StockMaterialCuttingLimits/></CGTechToolLibrary>",
        encoding="utf-8")
    case = {"case_id": "lathe_session_254fl_optimization", "path": "p.vcproject",
            "defect_evidence": [{"quote": "Optimization values which are incorrect"}]}
    result = vec._verify_tool_optimization(case, tmp_path)
    assert result["reproduced"] == "attested"
    assert result["confidence"] == "manual_attestation"


def test_shipped_verification_contract():
    if not SHIPPED.is_file():
        pytest.skip("verification report not generated in this checkout")
    report = json.loads(SHIPPED.read_text(encoding="utf-8"))
    summary = report["summary"]
    assert summary["error_cases"] == 13
    assert summary["dynamic_vericut_cases"] == 5
    assert summary["not_reproduced_or_unmeasured"] == 0
    assert summary["fully_reproduced"] == 8
    assert summary["attested_by_manual"] == 3
    assert summary["partial_static"] == 1
    assert summary["inferred_only"] == 1
    for case in report["cases"]:
        if case["method"] == "dynamic_vericut_batch":
            assert case["log_path"] and (WORKSPACE / case["log_path"]).is_file()
            assert case["observed"]


def test_analysis_report_contains_all_error_cases_and_statuses():
    if not (SHIPPED.is_file() and SHIPPED_INDEX.is_file()):
        pytest.skip("index/verification report not generated in this checkout")
    import scripts.render_case_analysis_report as report

    index = json.loads(SHIPPED_INDEX.read_text(encoding="utf-8"))
    verification = json.loads(SHIPPED.read_text(encoding="utf-8"))
    text = report.render(index, verification)
    error_cases = [c for c in index["cases"] if c["status"] == "error_demo"]
    error_cases += [p for p in index.get("standalone_programs", [])
                    if p["status"] == "error_demo"]
    assert len(error_cases) == 13
    for case in error_cases:
        case_id = case.get("case_id") or case.get("file")
        assert case_id in text
    assert "| 案例总数 | 80 |" in text
    assert "已复现" in text and "仅推断" in text
    assert "## 5. 未能动态复现的部分（诚实边界）" in text

