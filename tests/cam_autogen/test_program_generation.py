"""M3 加工程序自动生成单元测试：三大控制系统方言、完整工艺指令与 REST API。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from cam_autogen.contracts import OptimizationRequest, WorkpieceSpec
from cam_autogen.examples import EXAMPLES
from cam_autogen.optimization import optimize
from cam_autogen.process_recognition import recognize
from cam_autogen.program_generation import generate
from cam_autogen.program_generation.api import app
from cam_autogen.stock_positioning import compute_stock_setup


@pytest.mark.parametrize("dialect", ["FANUC", "SIEMENS", "HUAZHONG"])
@pytest.mark.parametrize("example_key", ["shaft", "keyed_shaft", "block", "flange"])
def test_generate_all_dialects_and_required_elements(example_key, dialect):
    wp = WorkpieceSpec.model_validate(EXAMPLES[example_key])
    rec = recognize(wp)
    ss = compute_stock_setup(wp, rec.process_type)
    plan = optimize(OptimizationRequest(workpiece=wp, process_type=rec.process_type))
    prog = generate(plan, ss, dialect=dialect)

    txt = prog.program_text
    assert prog.dialect == dialect
    assert len(prog.ir) > 10
    assert len(prog.tool_table) >= 1
    assert "M30" in txt
    assert "M08" in txt and "M09" in txt
    assert "M05" in txt

    if dialect == "FANUC":
        assert txt.startswith("%") and "O0001" in txt
        assert ";" not in txt
        if example_key != "block":
            assert "G50 S" in txt
    elif dialect == "SIEMENS":
        assert txt.startswith("; %_N_O0001_MPF")
        assert "G71" in txt
        if example_key == "keyed_shaft":
            assert "G33 " in txt and "LIMS=" in txt
        if example_key == "block":
            assert "G331 " in txt and "SUPA" in txt
    else:  # HUAZHONG
        assert txt.startswith("%0001")
        if example_key in ("shaft", "keyed_shaft", "flange"):
            assert "G95" in txt
        if example_key == "keyed_shaft":
            assert "G46" in txt and "G32 " in txt


def test_pocket_corner_arc_and_contour_polygon():
    # corner_radius=8 > D/2 (EM12 R=6) 时应生成 G03 圆弧插补；并覆盖凸台轮廓铣削
    wp = WorkpieceSpec.model_validate({
        "part_id": "ARC-POCKET",
        "material": {"name": "6061-T6"},
        "envelope": {"type": "prismatic", "x": 100, "y": 80, "z": 25},
        "stock": {"type": "block", "x": 100, "y": 80, "z": 28},
        "features": [
            {"id": "F1", "type": "pocket", "params": {"x": 50, "y": 40, "length": 40, "width": 20, "depth": 6,
                                                       "corner_radius": 8}, "ra_um": 1.6, "tolerance_mm": 0.03},
            {"id": "F2", "type": "contour", "params": {"x": 50, "y": 40, "length": 80, "width": 60, "depth": 4},
             "ra_um": 1.6},
        ],
    })
    rec = recognize(wp)
    ss = compute_stock_setup(wp, rec.process_type)
    plan = optimize(OptimizationRequest(workpiece=wp, process_type=rec.process_type))
    prog = generate(plan, ss, dialect="FANUC")
    assert "G03 " in prog.program_text
    assert any(m.kind == "arc_ccw" for m in prog.ir)


def test_m3_rest_api():
    wp = WorkpieceSpec.model_validate(EXAMPLES["shaft"])
    ss = compute_stock_setup(wp, recognize(wp).process_type)
    plan = optimize(OptimizationRequest(workpiece=wp, process_type=recognize(wp).process_type))
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    assert "HUAZHONG" in client.get("/v1/info").json()["supported_dialects"]
    r = client.post("/v1/generate", json={
        "plan": plan.model_dump(mode="json"),
        "stock_setup": ss.model_dump(mode="json"),
        "dialect": "HUAZHONG",
    })
    assert r.status_code == 200
    assert r.json()["dialect"] == "HUAZHONG"
    assert "%0001" in r.json()["program_text"]
