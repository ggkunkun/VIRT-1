"""Shared isolation for the four SWARM integration test modules.

Keep geometry, stock derivation and verification real; replace only external
search/project export. A copied product mesh also isolates surface_obs renders.
"""
from dataclasses import dataclass
import json
from pathlib import Path
import shutil
from unittest.mock import Mock

import pytest


SOURCE_ROOT = Path(__file__).resolve().parent.parent
MESH_RELATIVE = Path("artifacts/aero_closed_impeller/AE_CLOSED_IMPELLER_NASA1975.stl")
EXPORT_DISABLED = "test isolation: VERICUT project export disabled"


@dataclass
class SwarmWorkspace:
    root: Path
    design_stl: Path
    exporter: Mock

    def assert_runs(self, expected_count: int) -> None:
        """Check persisted evidence, not synthetic exporter/simulation reports."""
        snapshots = list(self.root.rglob("blackboard_snapshot.json"))
        assert len(snapshots) == expected_count
        assert self.exporter.call_count == expected_count
        for path in snapshots:
            snapshot = json.loads(path.read_text(encoding="utf-8"))
            geometry = snapshot["geometry"]["value"]
            assert Path(geometry["mesh"]).resolve() == self.design_stl.resolve()
            assert geometry["evidence_status"] == "measured"
            for image in geometry["images"].values():
                image_path = Path(image).resolve()
                assert image_path.is_relative_to(self.design_stl.parent / "surface_obs")
                assert image_path.is_file()
            assert snapshot["process_plan"]["value"]["online"] is False
            toolpath = snapshot["toolpath"]
            assert_logical_toolpath(toolpath["value"])
            assert toolpath["meta"]["basis"] == "measured"
            assert toolpath["meta"]["writer"] == "ToolpathGenerationAgent"


def assert_logical_toolpath(toolpath: dict) -> None:
    assert toolpath["stock_source"] == "logical_only"
    assert toolpath["stock_basis"] == "measured_from_product_mesh"
    assert toolpath["project"] is None
    assert toolpath["vericut_report"] is None


@pytest.fixture
def swarm_workspace(tmp_path, monkeypatch, request):
    """Function-scoped fixture imported by all four modules, without conftest."""
    design_stl = tmp_path / MESH_RELATIVE
    design_stl.parent.mkdir(parents=True)
    shutil.copy2(SOURCE_ROOT / MESH_RELATIVE, design_stl)
    assert design_stl.read_bytes() == (SOURCE_ROOT / MESH_RELATIVE).read_bytes()

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("VIRTU_INTERNET", "off")
    monkeypatch.setenv("VIRTU_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("VIRTU_ROOT", str(tmp_path))
    monkeypatch.setenv("MPLCONFIGDIR", str(tmp_path / "matplotlib"))

    # SUPER_AGENT intentionally stays at its original source path. Entry AST
    # extraction happens later, using the patched ROOT as WORKSPACE_DIR.
    module = request.module
    for name, value in (("ROOT", tmp_path), ("DESIGN_STL", design_stl)):
        if hasattr(module, name):
            monkeypatch.setattr(module, name, value)
    if hasattr(module, "RUN_ROOT"):
        relative = module.RUN_ROOT.relative_to(SOURCE_ROOT)
        monkeypatch.setattr(module, "RUN_ROOT", tmp_path / relative)

    import virtu_omni.agent.swarm_orchestrator as so
    import scripts.setup_vericut_simulation as sv
    from design_web_self_correction import MockSearchProvider

    monkeypatch.setattr(so, "WORKSPACE_DIR", tmp_path)
    monkeypatch.setattr(so, "_get_search_provider", lambda: (MockSearchProvider(), False))
    # main() ignores the run directory and writes shared projects. Fail only
    # this I/O boundary, so toolpath_worker runs real derive_stock_from_product.
    exporter = Mock(name="disabled_vericut_export", side_effect=OSError(EXPORT_DISABLED))
    monkeypatch.setattr(sv, "main", exporter)
    monkeypatch.setattr(sv, "design_stl", design_stl)
    return SwarmWorkspace(tmp_path, design_stl, exporter)


def run_pytest_file(file: str) -> int:
    """Keep direct script execution on the same isolated path as pytest."""
    return pytest.main([
        str(Path(file).resolve()), "-q", "-o", "addopts=", "-p", "no:cacheprovider",
    ])
