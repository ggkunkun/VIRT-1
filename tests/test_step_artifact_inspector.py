"""STEP handoff measurements and falsifiable rejection cases."""

from __future__ import annotations

import ast
import json
import time
from pathlib import Path
from types import MethodType
from typing import Any, Callable, Dict, List, Tuple

import pytest

pytest.importorskip("build123d")
pytest.importorskip("OCP")

from build123d import Box, Circle, export_step  # noqa: E402

from virtu_omni.engine.step_artifact_inspector import inspect_step_artifact  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def test_valid_mm_step_reports_measured_geometry(tmp_path: Path) -> None:
    step_path = tmp_path / "box.step"
    export_step(Box(10, 20, 30), str(step_path))

    report = inspect_step_artifact(str(step_path))

    assert report["status"] == "PASS"
    assert report["verified"] is True
    assert report["evidence_status"] == "measured"
    assert len(report["file"]["sha256"]) == 64
    assert report["units"]["verified_millimetres"] is True
    assert report["geometry"]["valid_brep"] is True
    assert report["geometry"]["solid_count"] == 1
    assert report["geometry"]["volume_mm3"] == pytest.approx(6000.0)
    assert report["geometry"]["bbox_mm"] == pytest.approx({"x": 10.0, "y": 20.0, "z": 30.0})


def test_wire_only_step_is_red_even_when_its_brep_is_valid(tmp_path: Path) -> None:
    step_path = tmp_path / "wire.step"
    export_step(Circle(5), str(step_path))

    report = inspect_step_artifact(str(step_path))

    assert report["geometry"]["valid_brep"] is True
    assert report["geometry"]["solid_count"] == 0
    assert report["passed"] is False
    assert "NO_SOLID" in {failure["code"] for failure in report["failures"]}


def test_non_mm_step_fails_without_mislabelling_measurements(tmp_path: Path) -> None:
    step_path = tmp_path / "metre.step"
    export_step(Box(10, 20, 30), str(step_path))
    step_text = step_path.read_text(encoding="ascii")
    assert "SI_UNIT(.MILLI.,.METRE.)" in step_text
    step_path.write_text(
        step_text.replace("SI_UNIT(.MILLI.,.METRE.)", "SI_UNIT($,.METRE.)"),
        encoding="ascii",
    )

    report = inspect_step_artifact(str(step_path))

    assert report["passed"] is False
    assert report["units"]["source_length_units"] == ["metre"]
    assert report["geometry"]["volume_mm3"] is None
    assert report["geometry"]["bbox_mm"] is None
    assert "LENGTH_UNIT_NOT_MM" in {failure["code"] for failure in report["failures"]}


def test_tool_is_registered_on_the_super_agent_facet(tmp_path: Path) -> None:
    source = (ROOT / "virtu_omni" / "agent" / "super_agent.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    agent = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                 and node.name == "VirtuSuperAgent")
    register = next(node for node in agent.body if isinstance(node, ast.FunctionDef)
                    and node.name == "_register_default_tools")
    calls = [
        node for node in ast.walk(register)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "register_tool"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == "inspect_step_artifact"
    ]
    assert len(calls) == 1
    assert isinstance(calls[0].args[2], ast.Attribute)
    assert calls[0].args[2].attr == "facet_inspect_step_artifact"

    method = next(node for node in agent.body if isinstance(node, ast.FunctionDef)
                  and node.name == "facet_inspect_step_artifact")
    assert [arg.arg for arg in method.args.args] == ["self", "step_path"]
    assert "from virtu_omni.engine.step_artifact_inspector import inspect_step_artifact" in (
        ast.get_source_segment(source, method) or ""
    )

    from virtu_omni.agent.tool_binding import bind_facet_args, facet_input_schema, facet_params

    namespace: Dict[str, Any] = {
        "Any": Any,
        "Callable": Callable,
        "Dict": Dict,
        "List": List,
        "Tuple": Tuple,
        "_bind_facet_args": bind_facet_args,
        "_facet_input_schema": facet_input_schema,
        "_facet_params": facet_params,
        "json": json,
        "time": time,
    }
    isolated = ast.Module(body=[method], type_ignores=[])
    exec(compile(isolated, str(ROOT / "virtu_omni" / "agent" / "super_agent.py"), "exec"), namespace)
    adapter_node = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                        and node.name == "FacetToolAdapter")
    exec(compile(ast.Module(body=[adapter_node], type_ignores=[]),
                 str(ROOT / "virtu_omni" / "agent" / "super_agent.py"), "exec"), namespace)
    facet = MethodType(namespace["facet_inspect_step_artifact"], object())
    adapter = namespace["FacetToolAdapter"]({
        "inspect_step_artifact": ("inspect one STEP file", facet),
    })
    schema = adapter.schemas()[0]["inputSchema"]
    assert schema["required"] == ["payload"]
    assert schema["properties"]["payload"]["type"] == "string"

    step_path = tmp_path / "wiring_probe.step"
    export_step(Box(2, 3, 4), str(step_path))
    call = adapter.call("inspect_step_artifact", {"payload": str(step_path)})
    assert call["is_error"] is False, call
    report = json.loads(call["text"])
    assert report["passed"] is True
    assert report["geometry"]["volume_mm3"] == pytest.approx(24.0)
