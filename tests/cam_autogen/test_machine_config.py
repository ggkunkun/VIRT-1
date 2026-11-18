"""M4 机床参数自动配置单元测试：>=20 台内置机床库、自定义新增、能力匹配与 REST API。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from cam_autogen.contracts import MachineSpec, OptimizationRequest, WorkpieceSpec
from cam_autogen.examples import EXAMPLES
from cam_autogen.machine_config import BUILTIN_MACHINES, MachineRegistry, configure_machine, extract_requirements
from cam_autogen.machine_config.api import app
from cam_autogen.optimization import optimize
from cam_autogen.process_recognition import recognize
from cam_autogen.program_generation import generate
from cam_autogen.stock_positioning import compute_stock_setup


def test_builtin_library_has_at_least_20_machines():
    assert len(BUILTIN_MACHINES) >= 20
    models = [m.model for m in BUILTIN_MACHINES]
    assert len(set(models)) == len(models)
    assert {"mill", "lathe", "turn_mill"} == {m.kind for m in BUILTIN_MACHINES}
    assert {"FANUC", "SIEMENS", "HUAZHONG"} == {m.dialect for m in BUILTIN_MACHINES}


@pytest.mark.parametrize("key,expected_kind", [
    ("shaft", "lathe"),
    ("keyed_shaft", "turn_mill"),
    ("block", "mill"),
    ("flange", "turn_mill"),
])
def test_machine_auto_configuration_matches_from_program_only(key, expected_kind):
    wp = WorkpieceSpec.model_validate(EXAMPLES[key])
    rec = recognize(wp)
    ss = compute_stock_setup(wp, rec.process_type)
    plan = optimize(OptimizationRequest(workpiece=wp, process_type=rec.process_type))
    prog = generate(plan, ss, dialect="FANUC")

    req = extract_requirements(prog)
    assert req.tools_count == len(prog.tool_table)
    setup = configure_machine(prog)
    assert setup.machine.kind == expected_kind
    assert setup.travel_check["within_limits"] is True
    assert len(setup.tool_pockets) == len(prog.tool_table)
    assert setup.post_profile.dialect == setup.machine.dialect


def test_custom_machine_registration_and_persistence(tmp_path):
    store = tmp_path / "custom_machines.json"
    reg = MachineRegistry(store_path=store)
    custom = MachineSpec(
        model="CUSTOM-SUPER-MILL-X1",
        vendor="CustomWorks",
        kind="mill",
        controller="SIEMENS 840D",
        dialect="SIEMENS",
        travel={"x": 900, "y": 600, "z": 500},
        max_rpm=24000,
        spindle_power_kw=25.0,
        max_feed_mm_min=24000,
        rapid_mm_min=48000,
        tool_capacity=40,
        max_tool_diameter=100,
        max_tool_length=300,
        has_y_axis=True,
    )
    reg.register(custom)
    assert reg.get("CUSTOM-SUPER-MILL-X1") is not None
    # 从文件重新加载
    reg2 = MachineRegistry(store_path=store)
    assert reg2.get("CUSTOM-SUPER-MILL-X1") is not None

    # 验证指定该自定义机床进行配置
    wp = WorkpieceSpec.model_validate(EXAMPLES["block"])
    plan = optimize(OptimizationRequest(workpiece=wp, process_type=recognize(wp).process_type))
    prog = generate(plan, compute_stock_setup(wp, recognize(wp).process_type))
    setup = configure_machine(prog, preferred_model="CUSTOM-SUPER-MILL-X1", registry=reg2)
    assert setup.machine.model == "CUSTOM-SUPER-MILL-X1"
    assert setup.post_profile.dialect == "SIEMENS"
    assert reg2.remove_custom("CUSTOM-SUPER-MILL-X1") is True


def test_machine_mismatch_rejected():
    wp = WorkpieceSpec.model_validate(EXAMPLES["keyed_shaft"])
    plan = optimize(OptimizationRequest(workpiece=wp, process_type=recognize(wp).process_type))
    prog = generate(plan, compute_stock_setup(wp, recognize(wp).process_type))
    with pytest.raises(ValueError):
        configure_machine(prog, preferred_model="SMTCL-CAK5085")  # 2轴车床无动力刀与C轴


def test_m4_rest_api():
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    machines = client.get("/v1/machines").json()
    assert machines["count"] >= 20

    wp = WorkpieceSpec.model_validate(EXAMPLES["shaft"])
    rec = recognize(wp)
    prog = generate(optimize(OptimizationRequest(workpiece=wp, process_type=rec.process_type)),
                    compute_stock_setup(wp, rec.process_type))
    r = client.post("/v1/configure", json={"program": prog.model_dump(mode="json")})
    assert r.status_code == 200 and r.json()["travel_check"]["within_limits"] is True
