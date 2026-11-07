# -*- coding: utf-8 -*-
"""virtu_omni/model_evolution_suite.py — Virtu Frontier Model Evolution & Reasoning Suite (V-FMERS).

Unifying the 4 Frontier Model Paradigms for Industrial Foundation Models:
1. RLVR + GRPO (DeepSeek-R1 / OpenAI o1): Group Relative Policy Optimization on deterministic physical environments.
2. DARE / TIES-Merging (MergeKit / Task Arithmetic): Interference-free weight space fusion across CAD, CAM, CAE, Standards.
3. PRM (Process-Supervised Reward Model): Step-by-step verification of G-code and CAD feature trees.
4. DeepCAD B-Rep Grammar DSL (MIT CSAIL): Manifold topological validation and constrained decoding.

Adheres strictly to RULE[d:\\Virtu模型\\AGENTS.md] Section 8 (Measurement Constitution):
- Content-addressed provenance IDs.
- Rule 4 falsifiable mutation gates for all 4 subsystems.
- Basis: "measured".
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

from virtu_omni.training.rlvr_grpo_engine import VirtuGRPOEngine, TrajectoryCandidate
from virtu_omni.models.task_arithmetic_merger import VirtuTaskArithmeticEngine, TaskVector, MergeProvenance
from virtu_omni.reasoning.process_reward_model import ProcessSupervisedRewardModel, PRMTrajectoryAudit
from virtu_omni.reasoning.brep_grammar_dsl import DeepCADBRepGrammarEngine, CADCommand, TopologyValidationReport

logger = logging.getLogger("virtu_omni.model_evolution_suite")


@dataclass
class FrontierProbesReport:
    """Consolidated health report for all 4 frontier model frameworks."""
    run_id: str
    timestamp: float
    rlvr_probe_passed: bool
    ties_probe_passed: bool
    prm_probe_passed: bool
    brep_probe_passed: bool
    all_probes_passed: bool
    basis: str = "measured"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class VirtuFrontierModelSuite:
    """Unified Facade for Virtu Frontier Model Evolution & Reasoning Suite."""

    _instance: Optional[VirtuFrontierModelSuite] = None

    def __init__(self):
        self.grpo_engine = VirtuGRPOEngine()
        self.ties_engine = VirtuTaskArithmeticEngine()
        self.prm_model = ProcessSupervisedRewardModel
        self.brep_engine = DeepCADBRepGrammarEngine

    @classmethod
    def get_instance(cls) -> VirtuFrontierModelSuite:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def run_all_frontier_probes(self) -> FrontierProbesReport:
        """Rule 4: Execute mutation probes across all four frontier model components."""
        t0 = time.time()
        p1 = self.grpo_engine.falsifiable_rlvr_probe()
        p2 = self.ties_engine.falsifiable_ties_probe()
        p3 = self.prm_model.falsifiable_prm_probe()
        p4 = self.brep_engine.falsifiable_brep_probe()

        all_ok = p1 and p2 and p3 and p4
        h = hashlib.sha256(f"{p1}_{p2}_{p3}_{p4}_{t0}".encode()).hexdigest()[:8]
        run_id = f"FMERS_PROBE_{time.strftime('%Y%m%d_%H%M%S')}_{h}"

        return FrontierProbesReport(
            run_id=run_id,
            timestamp=t0,
            rlvr_probe_passed=p1,
            ties_probe_passed=p2,
            prm_probe_passed=p3,
            brep_probe_passed=p4,
            all_probes_passed=all_ok,
            basis="measured",
        )

    # -------------------------------------------------------------------------
    # High-level Facet Shortcuts
    # -------------------------------------------------------------------------
    def evaluate_rlvr_group(
        self,
        prompt: str,
        candidate_outputs: List[str],
        context: Optional[Dict[str, Any]] = None,
    ) -> List[TrajectoryCandidate]:
        return self.grpo_engine.evaluate_group(prompt, candidate_outputs, context=context)

    def audit_gcode_prm(
        self,
        gcode: str,
        safe_plane_z: float = 5.0,
        stock_top_z: float = 0.0,
    ) -> PRMTrajectoryAudit:
        return self.prm_model.audit_gcode_steps(gcode, safe_plane_z=safe_plane_z, stock_top_z=stock_top_z)

    def validate_and_compile_brep(
        self,
        commands: List[CADCommand],
        part_name: str = "DeepCAD_Part",
    ) -> Tuple[Optional[str], TopologyValidationReport]:
        return self.brep_engine.validate_and_compile(commands, part_name=part_name)


def get_model_evolution_suite() -> VirtuFrontierModelSuite:
    return VirtuFrontierModelSuite.get_instance()
