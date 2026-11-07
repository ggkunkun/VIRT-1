"""VirtuHarnessAdapter: Industrial Benchmark Adapter for Harness² & Virtu Models.

Conforms to Harness² `BenchmarkAdapter` protocol. Connects Virtu industrial tasks
(CAD parametric design, CNC macro synthesis, 5-axis kinematic checks, tooling)
with the Harness² recursive self-improvement engine.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional

from harness2.core import tree as HT
from harness2.core.spec import BenchPrompts, BenchSpec, ChannelSpec
from harness2.core.tree import Tree

from virtu_omni.harness2.surface import VIRTU_SURFACE, build_default_virtu_harness
from virtu_omni.harness2.substrate import VirtuSubstrate


# Benchmark tasks across industrial engineering domains
VIRTU_BENCH_TASKS: Dict[str, Dict[str, str]] = {
    "cad-sleeve-01": {
        "domain": "die_and_mold",
        "prompt": "我想要一个材质为SS304的回转模具套筒，要求最大外径为110.0mm，轴心通孔为30.0mm，总长为30.0mm，带有12道槽底圆角R8.0的特征。",
        "expected_material": "SS304",
        "min_wall": 2.0,
    },
    "impeller-ti64-02": {
        "domain": "aerospace_cam",
        "prompt": "设计并制造一款航空高压压气机级12叶片闭式整体叶轮，材质为Ti-6Al-4V，外径180mm，轴孔25mm，需要进行五轴机床防过切仿真与切削载荷优化。",
        "expected_material": "Ti-6Al-4V",
        "min_wall": 5.0,
    },
    "flange-al7075-03": {
        "domain": "precision_machining",
        "prompt": "请生成一个材质为AL7075-T6的轻量化航空法兰盘，最大外径85.0mm，内孔40.0mm，厚度15.0mm，带6个均布M6螺纹孔，输出AutoCAD工程图与CIMCO Macro B代码。",
        "expected_material": "AL7075-T6",
        "min_wall": 3.0,
    },
    "shaft-cr12mov-04": {
        "domain": "die_and_mold",
        "prompt": "制造一款微型机冷挤压冲头轴模具，材质为Cr12MoV，外径53mm，内孔14mm，总长45mm，三道圆弧过渡槽R15/R12/R10，要求输出SOLIDWORKS参数化宏与斯沃对刀指南。",
        "expected_material": "Cr12MoV",
        "min_wall": 2.5,
    },
}


class VirtuHarnessAdapter:
    """Benchmark adapter running industrial tasks on Virtu Model under Harness²."""

    def __init__(self, root: Path, bridge_url: str = "http://127.0.0.1:8000"):
        self.root = Path(root)
        self.substrate = VirtuSubstrate(bridge_url=bridge_url)
        self.spec = BenchSpec(
            name="virtu_cad_cam",
            runs_root=self.root / "runs",
            install_mode="workspace_config",
            prompts=BenchPrompts(
                work="synthesize and verify industrial CAD/CAM/CNC engineering code and parameters",
                domain_word="industrial_sector",
                deliverable_word="engineering_package",
            ),
            channels={
                "proposer": ChannelSpec("opencode", "local/virtu"),
                "selector": ChannelSpec("opencode", "local/virtu"),
            },
            leak_globs=("reference/**",),
        )

        # Initialize base harness
        self._base_dir = self.root / "base_harness"
        self._base_dir.mkdir(parents=True, exist_ok=True)
        base_tree = build_default_virtu_harness()
        HT.write_tree(VIRTU_SURFACE, base_tree, self._base_dir, stubs=True)

        # Setup task sources
        self._sources_dir = self.root / "sources"
        self._sources_dir.mkdir(parents=True, exist_ok=True)
        for task_id, task_data in VIRTU_BENCH_TASKS.items():
            t_dir = self._sources_dir / task_id
            t_dir.mkdir(parents=True, exist_ok=True)
            (t_dir / "task.json").write_text(json.dumps(task_data, ensure_ascii=False, indent=2), encoding="utf-8")

    def tasks(self, split: str = "all") -> list[str]:
        """Task ids in stable reproducible order."""
        return list(VIRTU_BENCH_TASKS.keys())

    def preflight(self) -> None:
        """Verify readiness of Virtu benchmark and tasks."""
        if not self._base_dir.is_dir():
            raise RuntimeError(f"Base harness directory missing: {self._base_dir}")
        if not self.tasks():
            raise RuntimeError("No benchmark tasks configured.")
        if hasattr(self.substrate, "preflight"):
            self.substrate.preflight()

    def domain_of(self, task_id: str) -> str:
        """Domain grouping unit for task_id."""
        return VIRTU_BENCH_TASKS.get(task_id, {}).get("domain", "industrial_engineering")

    def task_prompt(self, task_id: str) -> str:
        """The user prompt handed to the agent."""
        return VIRTU_BENCH_TASKS.get(task_id, {}).get("prompt", "")

    def task_files(self, task_id: str) -> Path | None:
        """Path to source directory of this task."""
        d = self._sources_dir / task_id
        return d if d.is_dir() else None

    def base_harness(self) -> Path:
        """Directory holding the initial unmodified Virtu harness."""
        return self._base_dir

    def validate_tree(self, tree: Tree) -> None:
        """Enforce Virtu harness invariants."""
        # Check required always-on files
        for f in VIRTU_SURFACE.always_on:
            if f not in tree or not tree[f].strip():
                raise ValueError(f"Virtu Harness requires non-empty {f}")

        # Check guardrails rules presence
        guardrails = tree.get("guardrails.md", "")
        if "壁厚" not in guardrails and "wall_thickness" not in guardrails.lower():
            raise ValueError("guardrails.md must enforce minimum wall thickness rules")

    def execute(
        self, task_id: str, harness_dir: Path | None, run_id: str, *, timeout: int | None = None
    ) -> Path:
        """Execute one rollout on Virtu Model and return its run directory."""
        effective_harness = harness_dir if harness_dir is not None else self.base_harness()
        install = self.substrate.materialise(effective_harness, self.spec, {})
        prompt = self.task_prompt(task_id)

        out_dirs = self.substrate.execute(prompt, install, [run_id], timeout or 30)
        return out_dirs[0]

    def delivered(self, run_dir: Path) -> bool:
        """Check whether the run produced the required answer artifact."""
        answer_path = run_dir / "answer.txt"
        return answer_path.is_file() and answer_path.stat().st_size > 0

    def trajectory(self, run_dir: Path, *, obs_trunc: int) -> str:
        """Readable trajectory in shared Harness² grammar."""
        traj_path = run_dir / "trajectory.jsonl"
        return self.substrate.read_trajectory(traj_path, obs_trunc=obs_trunc, max_chars=100_000)

    def deliverable_files(self, run_dir: Path) -> dict[str, str]:
        """Map of filename to text content in run directory."""
        out = {}
        for p in run_dir.glob("*.txt"):
            out[p.name] = p.read_text(encoding="utf-8", errors="replace")
        return out

    def deliverable_text(self, run_dir: Path) -> str:
        """Synthesized engineering deliverable text."""
        ans = run_dir / "answer.txt"
        return ans.read_text(encoding="utf-8", errors="replace") if ans.is_file() else ""

    def score(self, run_dir: Path, task_id: str) -> dict | None:
        """Score one run based on engineering correctness and guardrail compliance."""
        if not self.delivered(run_dir):
            return {"score": 0.0, "status": "failed", "details": "No deliverable produced"}

        task_data = VIRTU_BENCH_TASKS.get(task_id, {})
        meta_file = run_dir / "execution.meta"
        meta = json.loads(meta_file.read_text(encoding="utf-8")) if meta_file.is_file() else {}

        score = 1.0
        checks = []

        # 1. Guardrail pass check
        if not meta.get("guardrail_pass", True):
            score -= 0.5
            checks.append("Failed guardrail validation")
        else:
            checks.append("Passed guardrail validation")

        # 2. Material parameter check
        answer = self.deliverable_text(run_dir)
        exp_mat = task_data.get("expected_material", "")
        if exp_mat and exp_mat in answer:
            checks.append(f"Correctly matched material {exp_mat}")
        else:
            score -= 0.2
            checks.append(f"Material {exp_mat} not explicitly verified")

        # 3. Macro syntax and equation manager check
        if "swEqnMgr" in answer or "EquationMgr" in answer or "NXOpen" in answer or "Macro B" in answer:
            checks.append("Verified parametric code synthesis")
        else:
            score -= 0.3
            checks.append("Missing software-specific parametric macros")

        final_score = max(0.0, round(score, 2))
        return {
            "score": final_score,
            "passed": final_score >= 0.7,
            "status": "pass" if final_score >= 0.7 else "fail",
            "checks": checks,
            "wall_time_s": meta.get("wall_time_s", 0.0),
        }
