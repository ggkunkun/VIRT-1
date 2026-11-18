"""端到端全链路与微服务 HTTP 解耦编排测试 + 日志溯源验证。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cam_autogen.common import load_trace
from cam_autogen.contracts import WorkpieceSpec
from cam_autogen.examples import EXAMPLES
from cam_autogen.machine_config.api import app as m4_app
from cam_autogen.optimization.api import app as m2_app
from cam_autogen.pipeline import PipelineRequest, run_pipeline
from cam_autogen.pipeline.api import app as pipe_app
from cam_autogen.process_recognition.api import app as m1_app
from cam_autogen.program_generation.api import app as m3_app
from cam_autogen.verification.api import app as verify_app


@pytest.mark.parametrize("key,dialect", [
    ("shaft", "FANUC"),
    ("keyed_shaft", "SIEMENS"),
    ("block", "HUAZHONG"),
    ("flange", "FANUC"),
])
def test_e2e_inprocess_produces_all_deliverables_and_trace(key, dialect, tmp_path):
    wp = WorkpieceSpec.model_validate(EXAMPLES[key])
    out_dir = tmp_path / "deliver"
    res = run_pipeline(
        PipelineRequest(workpiece=wp, preferred_dialect=dialect, output_dir=str(out_dir)),
        log_root=tmp_path / "logs",
    )
    assert res.status == "SUCCESS", f"端到端失败: {res.errors}"
    assert res.verification and res.verification.passed is True
    for k in ("nc_program", "machine_setup", "process_plan", "stock_setup", "verification_html", "verification_json", "trace_log"):
        p = Path(res.output_files[k])
        assert p.is_file() and p.stat().st_size > 0

    trace = load_trace(res.output_files["trace_log"])
    stages = {r["stage"] for r in trace}
    assert {"M1_process_recognition", "stock_positioning", "M2_optimization",
            "M3_program_generation_draft", "M4_machine_config", "M3_program_generation_final",
            "dual_verification"}.issubset(stages)


def test_e2e_low_confidence_blocked_and_fallback(tmp_path):
    amb = {
        "part_id": "AMB-E2E",
        "material": {"name": "C45"},
        "envelope": {"type": "prismatic", "x": 60, "y": 60, "z": 30},
        "stock": {"type": "bar", "diameter": 85, "length": 35},
        "features": [{"id": "F1", "type": "od_cylinder", "params": {"diameter": 40, "z_start": 0, "z_end": -10}}],
    }
    res = run_pipeline(
        PipelineRequest(workpiece=WorkpieceSpec.model_validate(amb), low_confidence_policy="halt"),
        log_root=tmp_path / "logs",
    )
    assert res.status == "BLOCKED"
    assert any("M1" in e for e in res.errors)


def test_e2e_http_microservice_mode(monkeypatch, tmp_path):
    """把编排器切到 transport='http'，将 HTTP POST 路由到四个独立 FastAPI 应用的 TestClient，验证真正契约级微服务互通。"""
    clients = {
        "http://m1": TestClient(m1_app),
        "http://m2": TestClient(m2_app),
        "http://m3": TestClient(m3_app),
        "http://m4": TestClient(m4_app),
        "http://verify": TestClient(verify_app),
    }

    def fake_http_post(url: str, payload: dict, timeout_s: float = 35.0):
        for prefix, cl in clients.items():
            if url.startswith(prefix):
                path = url[len(prefix):]
                resp = cl.post(path, json=payload)
                assert resp.status_code < 400, f"{url} -> {resp.status_code}: {resp.text}"
                return resp.json()
        raise AssertionError(f"未预期 URL: {url}")

    monkeypatch.setattr("cam_autogen.pipeline.orchestrator._http_post", fake_http_post)
    res = run_pipeline(
        PipelineRequest(
            workpiece=WorkpieceSpec.model_validate(EXAMPLES["shaft"]),
            transport="http",
            service_urls={"m1": "http://m1", "m2": "http://m2", "m3": "http://m3", "m4": "http://m4", "verify": "http://verify"},
            output_dir=str(tmp_path / "http_out"),
        ),
        log_root=tmp_path / "logs",
    )
    assert res.status == "SUCCESS"
    assert res.verification and res.verification.passed is True


def test_pipeline_rest_api_and_cli(tmp_path, monkeypatch, capsys):
    from cam_autogen.pipeline.__main__ import main

    c = TestClient(pipe_app)
    assert c.get("/health").status_code == 200
    assert "input_schema" in c.get("/v1/info").json()
    r = c.post("/v1/run", json={"workpiece": EXAMPLES["shaft"], "output_dir": str(tmp_path / "api_out")})
    assert r.status_code == 200 and r.json()["status"] == "SUCCESS"

    monkeypatch.setattr(sys, "argv", [
        "cam_autogen.pipeline", "--example", "shaft", "--dialect", "HUAZHONG",
        "--out", str(tmp_path / "cli_out"),
    ])
    main()
    captured = capsys.readouterr().out
    data = json.loads(captured)
    assert data["status"] == "SUCCESS" and data["verification_passed"] is True
