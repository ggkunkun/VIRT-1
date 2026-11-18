"""架构解耦检验（AST 静态扫描 + 反证样本）与公共基础设施测试。"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import List, Tuple

import pytest
from fastapi.testclient import TestClient

from cam_autogen.common import TraceLogger, digest, load_trace, make_app, summarize_trace

PKG_ROOT = Path(__file__).resolve().parents[2] / "cam_autogen"
CORE_MODULES = ("process_recognition", "optimization", "program_generation", "machine_config")


def find_cross_imports(source: str, self_mod: str, forbidden: Tuple[str, ...] = CORE_MODULES) -> List[str]:
    tree = ast.parse(source)
    others = {m for m in forbidden if m != self_mod}
    hits: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for o in others:
                    if alias.name == f"cam_autogen.{o}" or alias.name.startswith(f"cam_autogen.{o}."):
                        hits.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom) and node.module:
            for o in others:
                if node.module == f"cam_autogen.{o}" or node.module.startswith(f"cam_autogen.{o}."):
                    hits.append(f"from {node.module} import ...")
    return hits


def test_four_core_modules_strictly_decoupled():
    violations: List[str] = []
    for mod in CORE_MODULES:
        mod_dir = PKG_ROOT / mod
        assert mod_dir.is_dir(), f"缺少核心模块目录 {mod_dir}"
        for py in mod_dir.rglob("*.py"):
            hits = find_cross_imports(py.read_text(encoding="utf-8"), mod)
            for h in hits:
                violations.append(f"{py.relative_to(PKG_ROOT)}: {h}")
    assert violations == [], f"检测到核心模块跨模块耦合: {violations}"


def test_cross_import_detector_falsifiable():
    bad1 = "from cam_autogen.optimization import optimize\n"
    bad2 = "import cam_autogen.machine_config.engine\n"
    good = "from cam_autogen.contracts import ProcessPlan\nfrom cam_autogen.common import make_app\n"
    assert find_cross_imports(bad1, "program_generation") != []
    assert find_cross_imports(bad2, "process_recognition") != []
    assert find_cross_imports(good, "program_generation") == []


def test_trace_logger_and_common_app(tmp_path):
    logger = TraceLogger(trace_id="test-trace-01", root=tmp_path, persist=True)
    with logger.stage("stage_a", inputs={"x": 1}) as ctx:
        ctx["output"] = {"y": 2}
    with pytest.raises(RuntimeError):
        with logger.stage("stage_b", inputs={"x": 2}):
            raise RuntimeError("boom")
    p = logger.write_artifact("note.txt", "hello")
    assert p and Path(p).read_text(encoding="utf-8") == "hello"
    pb = logger.write_artifact("bin.dat", b"\x00\x01")
    assert pb and Path(pb).read_bytes() == b"\x00\x01"
    records = load_trace(logger.path)
    statuses = [(r["stage"], r["status"]) for r in records]
    assert statuses == [("stage_a", "START"), ("stage_a", "OK"), ("stage_b", "START"), ("stage_b", "ERROR")]
    summary = summarize_trace(logger.path)
    assert summary["stage_count"] == 2
    assert summary["bottleneck_stage"] in ("stage_a", "stage_b")
    assert len(summary["errors"]) == 1 and summary["errors"][0]["stage"] == "stage_b"
    assert digest({"a": 1, "b": 2}) == digest({"b": 2, "a": 1})

    app = make_app("demo", "0.1.0")
    @app.get("/err")
    def _err():
        raise ValueError("bad input")
    c = TestClient(app)
    assert c.get("/health").json()["status"] == "ok"
    r = c.get("/err")
    assert r.status_code == 422 and r.json()["error"] == "VALUE_ERROR"
