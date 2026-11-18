# -*- coding: utf-8 -*-
"""可证伪测试：VERICUT 培训案例索引（错误案例 / 加工能力 / 轴一致性）。

反证目标（坏样本必须红）：
* ``RotarySpin="on"`` 的主轴 C 不得被当成第四轴；
* ``_GET_A1`` / ``CYCL DEF 19.1 A+0`` 这类变量与循环参数不得被当成旋转轴运动；
* ``G70``（英寸模式）与 Haas ``G71`` 螺栓孔循环不得被判成车削；
* 单一旋转轴只能判四轴，两个旋转轴但只在 G0 定位只能判 5 轴定位，不得冒充五轴联动；
* 加密 ``.xmch`` 必须标 ``encrypted_unreadable``，不得臆造轴数；
* 索引缺失时必须 no_evidence，不得拿通用经验补位。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from virtu_omni.knowledge import training_case_catalog as tcc

WORKSPACE = Path(__file__).resolve().parents[1]
SHIPPED_INDEX = WORKSPACE / "knowledge_base" / "training_case_index.json"


def _machine(path: Path, comps) -> None:
    body = "".join(
        f'<Component Name="{name}" Type="{typ}"'
        + (f' RotarySpin="{spin}"' if spin else "")
        + "><Attach>Base</Attach></Component>"
        for name, typ, spin in comps
    )
    path.write_text(
        f'<?xml version="1.0"?><VcMachine Version="9.6"><Information/>'
        f"<Component Name=\"Base\" Type=\"base\"/>{body}</VcMachine>",
        encoding="utf-8",
    )


def _nc(path: Path, lines) -> None:
    path.write_text("%\n" + "\n".join(lines) + "\n", encoding="utf-8")


def _project(path: Path, files) -> None:
    refs = "".join(f"<File>{name}</File>" for name in files)
    path.write_text(
        f'<?xml version="1.0"?><VcProject Version="9.6" Unit="inch">'
        f"<Setup>{refs}</Setup></VcProject>",
        encoding="utf-8",
    )


def _case_of(catalog, case_id):
    for case in catalog["cases"]:
        if case["case_id"] == case_id:
            return case
    raise AssertionError(f"case not found: {case_id}")


# --------------------------------------------------------------------------- machine
def test_rotary_spin_is_spindle_not_fourth_axis(tmp_path):
    machines = tmp_path / "machines"
    machines.mkdir()
    m = machines / "vmc.mch"
    _machine(m, [("X", "linear", ""), ("Y", "linear", ""), ("Z", "linear", ""),
                 ("C", "rotary", "on"), ("Spindle", "spindle", "")])
    info = tcc.parse_machine(m)
    assert info["linear_axes"] == ["X", "Y", "Z"]
    assert info["rotary_axes"] == []          # 主轴自转不是第四轴
    assert info["kind"] == "mill"


def test_encrypted_machine_is_flagged_not_guessed(tmp_path):
    m = tmp_path / "okuma_multus_b300_w.xmch"
    m.write_bytes(b"CGTech encrypted file\n" + b"\x00\x01\x02" * 20)
    info = tcc.parse_machine(m)
    assert info["parse"] == "encrypted_unreadable"
    assert info["rotary_axes"] == []          # 读不出就是读不出
    assert info["kind"] == "mill_turn"        # 由名称推断，且 notes 说明
    assert any("加密" in n for n in info["notes"])


# --------------------------------------------------------------------------- NC
def test_axis_word_regex_ignores_variables_and_cycle_parameters(tmp_path):
    p = tmp_path / "probe.spf"
    p.write_text(
        "REPEAT _GET_A1 _GET_A2\n"
        "IF ($MC_MM_SYSTEM_FRAME_MASK B_AND 'B100000')\n"
        "CYCL DEF 19.1 A-90 B+0.0 C+270\n"
        ";C06.02.09 May 29, 2002\n"
        "N10 G0 X0 Y0 Z0\n",
        encoding="utf-8",
    )
    prof = tcc.profile_program(p)
    assert prof["rotary_axes"] == []
    assert prof["linear_blocks"] == 1


def test_g70_inch_mode_and_haas_g71_are_not_turning(tmp_path):
    p = tmp_path / "mill.nc"
    p.write_text(
        "%\nN0010 G40 G17 G90 G70\n"
        "N20 G71X0.Y0.I7.0J109.K45L8\n"
        "N30 G0 X1. Y1.\nN40 G1 X2. F10.\n",
        encoding="utf-8",
    )
    prof = tcc.profile_program(p)
    assert prof["turning_pq"] is False
    assert "G70" not in prof["turning_cycles"]
    assert "G71" in prof["turning_cycles"]     # 原始证据保留
    capability, _ = tcc._capability_of(None, [prof], "mill")
    assert capability == "milling_3axis"


def test_fanuc_g71_pq_is_turning(tmp_path):
    p = tmp_path / "turn.mcd"
    p.write_text("%\nN10 G0 X2.75 Z.16\nN20 G71 P30 Q40 U0.02 W0.03 D0.05\n"
                 "N30 G0 X1.\nN40 G1 Z-1.\n", encoding="utf-8")
    prof = tcc.profile_program(p)
    assert prof["turning_pq"] is True


# --------------------------------------------------------------------------- capability
def test_capability_matrix(tmp_path):
    root = tmp_path / "training"
    root.mkdir()
    _machine(root / "m3.mch", [("X", "linear", ""), ("Y", "linear", ""),
                               ("Z", "linear", ""), ("Spindle", "spindle", "")])
    _machine(root / "m4.mch", [("X", "linear", ""), ("Y", "linear", ""),
                               ("Z", "linear", ""), ("B", "rotary", ""),
                               ("Spindle", "spindle", "")])
    _machine(root / "m5.mch", [("X", "linear", ""), ("Y", "linear", ""),
                               ("Z", "linear", ""), ("A", "rotary", ""),
                               ("C", "rotary", ""), ("Spindle", "spindle", "")])
    _machine(root / "lt.mch", [("X", "linear", ""), ("Z", "linear", ""),
                               ("C", "rotary", ""), ("Turret", "turret", ""),
                               ("Spindle", "spindle", "")])
    _machine(root / "mt.mch", [("X", "linear", ""), ("Y", "linear", ""),
                               ("Z", "linear", ""), ("B", "rotary", ""),
                               ("C", "rotary", ""), ("Tool_Spindle", "spindle", ""),
                               ("Part_Spindle", "spindle", "")])

    _nc(root / "p3.mcd", ["N10 G0 X0 Y0 Z0", "N20 G1 X10. F100."])
    _nc(root / "p4.mcd", ["N10 G0 X0 Y0 B90.", "N20 G1 X10. F100."])
    _nc(root / "p5pos.mcd", ["N10 G0 A-90. C180.", "N20 G1 X10. F100."])
    _nc(root / "p5sim.mcd", ["N10 G1 X10. Y0 A10. C20. F100."])
    _nc(root / "pturn.mcd", ["N10 G0 X2. Z.1", "N20 G71 P30 Q40 U0.02 W0.03 D0.05",
                             "N30 G0 X1.", "N40 G1 Z-1."])
    _nc(root / "pmt.mcd", ["N10 G0 B0 C0", "N20 G1 X10. F100."])

    _project(root / "c3.vcproject", ["m3.mch", "p3.mcd"])
    _project(root / "c4.vcproject", ["m4.mch", "p4.mcd"])
    _project(root / "c5pos.vcproject", ["m5.mch", "p5pos.mcd"])
    _project(root / "c5sim.vcproject", ["m5.mch", "p5sim.mcd"])
    _project(root / "cturn.vcproject", ["lt.mch", "pturn.mcd"])
    _project(root / "cmt.vcproject", ["mt.mch", "pmt.mcd"])
    _project(root / "cmodels.vcproject", [])

    catalog = tcc.build_catalog(root, read_pdf=False)
    assert _case_of(catalog, "c3")["required_capability"] == "milling_3axis"
    assert _case_of(catalog, "c4")["required_capability"] == "milling_4axis"
    assert _case_of(catalog, "c5pos")["required_capability"] == "milling_5axis_positioning"
    assert _case_of(catalog, "c5sim")["required_capability"] == "milling_5axis_simultaneous"
    assert _case_of(catalog, "cturn")["required_capability"] == "turning"
    assert _case_of(catalog, "cmt")["required_capability"] == "mill_turn"
    assert _case_of(catalog, "cmodels")["required_capability"] == "models_only"

    # 单一旋转轴不得被算成五轴
    agg = catalog["summary"]["by_capability"]
    assert agg["milling_5axis_simultaneous"] == 1


def test_axis_mismatch_is_reported_not_hidden(tmp_path):
    root = tmp_path / "training"
    root.mkdir()
    _machine(root / "m3.mch", [("X", "linear", ""), ("Y", "linear", ""),
                               ("Z", "linear", ""), ("Spindle", "spindle", "")])
    _nc(root / "p.mcd", ["N10 G0 Z500. B180.", "N20 G1 X10. F100."])
    _project(root / "c.vcproject", ["m3.mch", "p.mcd"])
    catalog = tcc.build_catalog(root, read_pdf=False)
    case = _case_of(catalog, "c")
    assert case["axis_consistency"]["status"] == "nc_uses_axes_machine_lacks"
    assert case["axis_consistency"]["missing_in_machine"] == ["B"]
    assert any("不一致" in n for n in case["notes"])


# --------------------------------------------------------------------------- status
def test_status_mapping_and_pdf_scope_without_extractor(tmp_path, monkeypatch):
    root = tmp_path / "training"
    root.mkdir()
    _machine(root / "m3.mch", [("X", "linear", ""), ("Spindle", "spindle", "")])
    _nc(root / "p.mcd", ["N10 G1 X1. F10."])
    _project(root / "case_err.vcproject", ["m3.mch", "p.mcd"])
    _project(root / "case_ok.vcproject", ["m3.mch", "p.mcd"])
    (root / "Session 3L-Find and Detect Errors.pdf").write_bytes(b"%PDF-1.4\n")

    def fake_extract(pdf):
        opened = ["case_err.vcproject"] if "3L" in pdf.name else ["case_ok.vcproject"]
        defects = ([{"basis": "session_title", "page": 1,
                     "quote": "Find and Detect Errors"}] if "3L" in pdf.name else [])
        return opened, defects, True

    monkeypatch.setattr(tcc, "_extract_pdf", fake_extract)
    catalog = tcc.build_catalog(root, read_pdf=True)
    assert _case_of(catalog, "case_err")["status"] == "error_demo"
    assert _case_of(catalog, "case_ok")["status"] == "reference"
    assert _case_of(catalog, "case_err")["defect_evidence"][0]["quote"]


def test_additive_autodiff_deviation_is_not_error_demo():
    """Additive 课程的 AUTO-DIFF 偏差不是「故意错误」，AUTODIFF 课程才是。"""
    title_add = tcc._session_title("Session 20-Additive module.pdf")
    title_diff = tcc._session_title("Session 5L-Compare Cut Part to Design with AUTODIFF.pdf")
    pat = next(p for b, p, s in tcc.DEFECT_PATTERNS if "some errors" in p.pattern)

    def scoped(title):
        scope = next(s for b, p, s in tcc.DEFECT_PATTERNS if "some errors" in p.pattern)
        return bool(scope and scope.search(title))

    assert pat.search("some errors have been detected")
    assert scoped(title_add) is False
    assert scoped(title_diff) is True


def test_detect_collision_standalone_is_error_demo(tmp_path):
    root = tmp_path / "training"
    root.mkdir()
    _nc(root / "detect_collision.mcd", ["N10 G0 X0 Y0 A0 B-90.", "N20 G1 X3. F10."])
    catalog = tcc.build_catalog(root, read_pdf=False)
    assert any(p["file"] == "detect_collision.mcd" and p["status"] == "error_demo"
               for p in catalog["standalone_programs"])


# --------------------------------------------------------------------------- query
def test_query_filters_and_no_evidence(tmp_path):
    root = tmp_path / "training"
    root.mkdir()
    _machine(root / "m3.mch", [("X", "linear", ""), ("Spindle", "spindle", "")])
    _nc(root / "p.mcd", ["N10 G1 X1. F10."])
    _project(root / "c3.vcproject", ["m3.mch", "p.mcd"])
    catalog = tcc.build_catalog(root, read_pdf=False)

    assert [c["case_id"] for c in tcc.query_cases(catalog, capability="3axis")] == ["c3"]
    assert tcc.query_cases(catalog, capability="5axis") == []
    assert tcc.query_cases(catalog, status="error_demo") == []
    assert tcc.answer_query(catalog, "哪些需要五轴联动")["case_count"] == 0
    assert tcc.load_catalog(tmp_path / "missing.json") is None


def test_enrich_with_verification_marks_only_error_cases(tmp_path):
    catalog = {
        "cases": [
            {"case_id": "lathe_session_day1", "status": "error_demo"},
            {"case_id": "lathe_session_254fl_optimization", "status": "error_demo"},
            {"case_id": "VDAF_simulation_training_session", "status": "error_demo"},
            {"case_id": "detect_collision", "status": "error_demo"},
            {"case_id": "mill_session_16m_day_2_review", "status": "reference"},
        ],
        "standalone_programs": [],
        "summary": {},
    }
    report = tmp_path / "verify.json"
    report.write_text(json.dumps({
        "generated_at_utc": "2026-11-17T00:00:00+00:00",
        "cases": [
            {"case_id": "lathe_session_day1", "reproduced": True,
             "method": "dynamic_vericut_batch", "confidence": "measured",
             "log_path": "logs/a.log"},
            {"case_id": "lathe_session_254fl_optimization", "reproduced": "attested",
             "method": "static_manual_attestation", "confidence": "manual_attestation"},
            {"case_id": "VDAF_simulation_training_session", "reproduced": "partial",
             "method": "static_measured+manual_attestation", "confidence": "measured_partial"},
            {"case_id": "detect_collision", "reproduced": "inferred_only",
             "method": "static_asset", "confidence": "inferred"},
        ],
    }), encoding="utf-8")

    out = tcc.enrich_with_verification(catalog, report)
    by_id = {c["case_id"]: c for c in out["cases"]}
    assert by_id["lathe_session_day1"]["verification_status"] == "reproduced"
    assert by_id["lathe_session_day1"]["error_type"] == "nc_error_collision"
    assert by_id["lathe_session_day1"]["reproduction"]["log_path"] == "logs/a.log"
    assert by_id["lathe_session_254fl_optimization"]["verification_status"] == "attested"
    assert by_id["lathe_session_254fl_optimization"]["error_type"] == "data_defect"
    assert by_id["VDAF_simulation_training_session"]["verification_status"] == "partial"
    assert by_id["detect_collision"]["verification_status"] == "inferred"
    assert by_id["detect_collision"]["error_type"] == "collision_demo"
    assert "verification_status" not in by_id["mill_session_16m_day_2_review"]
    summary = out["summary"]["error_case_verification"]
    assert summary["total"] == 4
    assert summary["by_verification_status"] == {
        "reproduced": 1, "attested": 1, "partial": 1, "inferred": 1}
    assert [c["case_id"] for c in tcc.query_cases(
        out, verification_status="reproduced")] == ["lathe_session_day1"]
    assert tcc.answer_query(out, "哪些错误案例已复现")["case_count"] == 1


def test_enrich_without_report_is_honest(tmp_path):
    catalog = {"cases": [{"case_id": "lathe_session_day1", "status": "error_demo"}],
               "summary": {}}
    out = tcc.enrich_with_verification(catalog, tmp_path / "missing.json")
    assert "missing" in out["method"]["verification"]
    assert "verification_status" not in out["cases"][0]


# --------------------------------------------------------------------------- shipped index
def test_shipped_index_contract():
    if not SHIPPED_INDEX.is_file():
        pytest.skip("shipped training case index not generated in this checkout")
    catalog = json.loads(SHIPPED_INDEX.read_text(encoding="utf-8"))
    cases = catalog["cases"]
    assert len(cases) >= 70
    assert len(catalog["machines"]) >= 40
    assert len(catalog["sessions"]) >= 80
    assert "reference_cases_not_rerun_in_vericut" in catalog["method"]["verification"]
    assert all(len(c["sha256"]) == 64 and c["path"] for c in cases)
    assert all(c["required_capability"] in tcc.CAPABILITY_LABELS for c in cases)

    error_cases = [c for c in cases if c["status"] == "error_demo"]
    assert len(error_cases) >= 8
    assert "lathe_session_day1" in {c["case_id"] for c in error_cases}
    for case in error_cases:
        assert case["defect_evidence"], f"{case['case_id']} 缺少讲义证据"
        assert case["defect_evidence"][0]["quote"]
        assert case["error_type"] in tcc.ERROR_TYPE_LABELS
        assert case["verification_status"] in {
            "reproduced", "attested", "partial", "inferred",
            "not_reproduced", "unmeasured"}
        assert isinstance(case.get("reproduction"), dict)
    # 参考案例不得被写成「已验证复现」
    assert all("verification_status" not in c for c in cases if c["status"] != "error_demo")

    verify_summary = catalog["summary"]["error_case_verification"]
    assert verify_summary["total"] == 13
    assert verify_summary["by_verification_status"] == {
        "reproduced": 8, "attested": 3, "partial": 1, "inferred": 1}

    # 声称五轴联动的案例必须真的有「同一进给块 ≥2 旋转轴」的程序指标。
    for case in cases:
        if case["required_capability"] == "milling_5axis_simultaneous":
            assert any(p.get("max_rotary_axes_in_feed_block", 0) >= 2
                       for p in case["programs"])

    counts = catalog["summary"]["by_capability"]
    assert sum(counts.values()) == len(cases)


def test_infer_filters_distinguishes_5axis_modes():
    assert tcc._infer_filters("哪些需要五轴联动")["capability"] == "5axis_simultaneous"
    assert tcc._infer_filters("哪些需要五轴定位")["capability"] == "5axis_positioning"
    assert tcc._infer_filters("哪些需要五轴")["capability"] == "5axis"
    assert tcc._infer_filters("哪些是错误案例")["status"] == "error_demo"
    assert tcc._infer_filters("哪些需要车床")["capability"] == "turning"


def test_super_agent_exposes_case_query_tool():
    from virtu_omni.agent.super_agent import VirtuSuperAgent

    agent = VirtuSuperAgent()
    assert "query_training_cases" in agent._tool_registry
    res = agent.facet_query_training_cases("哪些是错误案例")
    if not SHIPPED_INDEX.is_file():
        assert res["basis"] == "no_evidence" and res["success"] is False
    else:
        assert res["success"] and res["basis"] == "measured"
        assert res["case_count"] >= 1
        assert all(c["status"] == "error_demo" for c in res["cases"])

        # 索引存在时，「五轴联动」0 命中是实测结论，不是证据缺失。
        sim = agent.facet_query_training_cases("哪些需要五轴联动")
        assert sim["filters"]["capability"] == "5axis_simultaneous"
        assert sim["basis"] == "measured"
        assert sim["empty_result"] is True
        assert sim["case_count"] == 0
