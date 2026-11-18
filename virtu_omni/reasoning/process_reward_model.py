# -*- coding: utf-8 -*-
"""virtu_omni/reasoning/process_reward_model.py — Process-Supervised Reward Model (PRM).

Grounded in:
1. OpenAI o1 Process Supervision: "Let's Verify Step by Step" (Lightman et al., 2023).
2. Math-Shepherd: "Verify and Reinforce from Process Supervision" (Yu et al., 2024).

Core Architecture:
In complex industrial engineering (multi-feature CAD FeatureTrees and multi-block CNC G-codes),
Outcome Reward Models (ORM) fail because a single flawed step (e.g., an unretracted G00 move or
an unclosed sketch) ruins an otherwise perfect 200-line solution.

PRM evaluates code and reasoning STEP BY STEP:
    s_0 --(r_1)--> s_1 --(r_2)--> ... --(r_N)--> s_N
If any step t has r_t == 0.0, PRM immediately halts execution, isolates the defective step,
and directs beam search / backtracking to repair the flaw locally.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import math
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

logger = logging.getLogger("virtu_omni.reasoning.prm")


@dataclass
class PRMStepResult:
    """Evaluation result for an atomic reasoning/code step."""
    step_index: int
    step_type: str                      # "CAD_FEATURE", "GCODE_BLOCK", "PHYSICS_DERIVATION"
    content: str
    reward: float                       # [0.0, 1.0]
    passed: bool
    veto_reason: Optional[str] = None
    accumulated_state: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PRMTrajectoryAudit:
    """Full-trajectory stepwise audit result."""
    trajectory_id: str
    total_steps: int
    steps: List[PRMStepResult]
    overall_score: float
    first_failure_step: Optional[int] = None
    all_steps_passed: bool = True
    fatal_error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ProcessSupervisedRewardModel:
    """Industrial Process-Supervised Reward Model for Stepwise Verification."""

    @classmethod
    def audit_gcode_steps(
        cls,
        gcode_text: str,
        safe_plane_z: float = 5.0,
        stock_top_z: float = 0.0,
    ) -> PRMTrajectoryAudit:
        """Step-by-step verification of G-code NC blocks."""
        lines = [line.strip() for line in gcode_text.splitlines() if line.strip() and not line.strip().startswith("(")]
        step_results: List[PRMStepResult] = []

        state: Dict[str, Any] = {
            "spindle_on": False,
            "spindle_rpm": 0.0,
            "current_z": safe_plane_z + 50.0,
            "coolant_on": False,
            "motion_mode": "G00",
            "active_tool": None,
        }

        all_ok = True
        first_fail: Optional[int] = None
        fatal_msg: Optional[str] = None

        for idx, line in enumerate(lines, 1):
            line_upper = line.upper()
            step_reward = 1.0
            veto = None

            # 1. Spindle checks
            if "M03" in line_upper or "M04" in line_upper:
                rpm_m = re.search(r"S(\d+(?:\.\d+)?)", line_upper)
                if rpm_m:
                    rpm = float(rpm_m.group(1))
                    if rpm < 100.0 or rpm > 15000.0:
                        step_reward = 0.4
                        veto = f"Unrealistic spindle RPM {rpm}"
                    state["spindle_rpm"] = rpm
                state["spindle_on"] = True
            elif "M05" in line_upper:
                state["spindle_on"] = False

            # 2. Tool checks
            if "T" in line_upper:
                tool_m = re.search(r"T(\d+)", line_upper)
                if tool_m:
                    state["active_tool"] = f"T{tool_m.group(1)}"

            # 3. Motion mode
            if "G00" in line_upper or "G0 " in line_upper:
                state["motion_mode"] = "G00"
            elif "G01" in line_upper or "G1 " in line_upper:
                state["motion_mode"] = "G01"
            elif "G02" in line_upper or "G03" in line_upper:
                state["motion_mode"] = "G02/G03"

            # 4. Z movement and Collision Check
            z_m = re.search(r"Z(-?\d+(?:\.\d+)?)", line_upper)
            if z_m:
                new_z = float(z_m.group(1))
                # Check for rapid plunge collision
                is_rapid = bool(re.search(r"\b(?:G00|G0)(?![0-9])", line_upper)) or (state["motion_mode"] == "G00" and "G01" not in line_upper)
                if is_rapid and new_z < stock_top_z:
                    step_reward = 0.0
                    veto = f"Fatal G00 rapid plunge into workpiece at Z={new_z} (stock top={stock_top_z})"
                    all_ok = False
                    if first_fail is None:
                        first_fail = idx
                        fatal_msg = veto

                # Check cutting without spindle
                if not is_rapid and new_z < stock_top_z and not state["spindle_on"]:
                    step_reward = 0.0
                    veto = "Cutting plunge motion into stock with spindle stopped (M05)"
                    all_ok = False
                    if first_fail is None:
                        first_fail = idx
                        fatal_msg = veto

                state["current_z"] = new_z

            step_res = PRMStepResult(
                step_index=idx,
                step_type="GCODE_BLOCK",
                content=line,
                reward=step_reward,
                passed=(step_reward > 0.0),
                veto_reason=veto,
                accumulated_state=copy.deepcopy(state),
            )
            step_results.append(step_res)

        overall = sum(s.reward for s in step_results) / max(1, len(step_results))
        traj_id = f"PRM_GCODE_{hashlib.sha256(gcode_text.encode()).hexdigest()[:8]}"

        return PRMTrajectoryAudit(
            trajectory_id=traj_id,
            total_steps=len(step_results),
            steps=step_results,
            overall_score=round(overall, 4),
            first_failure_step=first_fail,
            all_steps_passed=all_ok,
            fatal_error=fatal_msg,
        )

    @classmethod
    def audit_cad_steps(cls, steps: List[Dict[str, Any]]) -> PRMTrajectoryAudit:
        """Step-by-step verification of CAD feature tree generation."""
        step_results: List[PRMStepResult] = []
        state = {"has_solid_body": False, "features_count": 0, "active_sketch": None}
        all_ok = True
        first_fail = None
        fatal_msg = None

        for idx, step_data in enumerate(steps, 1):
            op = step_data.get("op", "").upper()
            reward = 1.0
            veto = None

            if op == "SKETCH":
                closed = step_data.get("closed", True)
                if not closed:
                    reward = 0.3
                    veto = "Sketch contour is open/unclosed"
                state["active_sketch"] = step_data.get("name", f"Sketch_{idx}")

            elif op == "EXTRUDE":
                depth = float(step_data.get("depth", 10.0))
                if depth <= 0.0:
                    reward = 0.0
                    veto = f"Extrude depth {depth} <= 0 violates Volume Conservation delta V > 0"
                    all_ok = False
                    if first_fail is None:
                        first_fail = idx
                        fatal_msg = veto
                else:
                    state["has_solid_body"] = True
                    state["features_count"] += 1

            elif op == "CUT_EXTRUDE":
                if not state["has_solid_body"]:
                    reward = 0.0
                    veto = "Cannot execute Cut-Extrude on document with 0 solid bodies"
                    all_ok = False
                    if first_fail is None:
                        first_fail = idx
                        fatal_msg = veto
                else:
                    state["features_count"] += 1

            elif op == "FILLET":
                radius = float(step_data.get("radius", 1.0))
                if radius <= 0.0:
                    reward = 0.0
                    veto = "Fillet radius must be strictly positive"
                    all_ok = False
                    if first_fail is None:
                        first_fail = idx
                        fatal_msg = veto

            step_res = PRMStepResult(
                step_index=idx,
                step_type="CAD_FEATURE",
                content=json.dumps(step_data, ensure_ascii=False),
                reward=reward,
                passed=(reward > 0.0),
                veto_reason=veto,
                accumulated_state=copy.deepcopy(state),
            )
            step_results.append(step_res)

        overall = sum(s.reward for s in step_results) / max(1, len(step_results))
        return PRMTrajectoryAudit(
            trajectory_id=f"PRM_CAD_{int(time.time()*1000)%100000}",
            total_steps=len(step_results),
            steps=step_results,
            overall_score=round(overall, 4),
            first_failure_step=first_fail,
            all_steps_passed=all_ok,
            fatal_error=fatal_msg,
        )

    @classmethod
    def audit_cot_steps(
        cls,
        raw_output: str,
        prompt: str = "",
        scenario: Optional[Dict[str, Any]] = None,
        require_think: bool = True,
    ) -> PRMTrajectoryAudit:
        """Step-by-step Process Supervision of <think> Chain-of-Thought and final answer faithfulness."""
        from virtu_omni.reasoning.chain_of_thought import StructuredCoTEngine

        rep = StructuredCoTEngine.verify_cot_faithfulness(
            raw_output=raw_output,
            prompt=prompt,
            scenario=scenario,
            require_think=require_think,
        )
        step_results: List[PRMStepResult] = []
        state: Dict[str, Any] = {
            "has_think_block": rep.has_think_block,
            "stages_covered": [],
            "derived_fields": {},
        }
        all_ok = True
        first_fail: Optional[int] = None
        fatal_msg: Optional[str] = None

        if not rep.steps:
            veto = "Missing or empty <think> reasoning steps" if require_think else None
            rw = 0.0 if require_think else 1.0
            if require_think:
                all_ok = False
                first_fail = 1
                fatal_msg = veto
            step_results.append(
                PRMStepResult(
                    step_index=1,
                    step_type="PHYSICS_DERIVATION",
                    content="<no_think_steps>",
                    reward=rw,
                    passed=(rw > 0.0),
                    veto_reason=veto,
                    accumulated_state=copy.deepcopy(state),
                )
            )
        else:
            for s in rep.steps:
                rw = 1.0
                veto = None
                if not s.grounding_valid or not s.arithmetic_valid:
                    rw = 0.0
                    veto = s.error_detail or "CoT step arithmetic or grounding failure"
                    all_ok = False
                    if first_fail is None:
                        first_fail = s.step_index
                        fatal_msg = veto
                if s.stage not in state["stages_covered"]:
                    state["stages_covered"].append(s.stage)
                if s.bound_field and s.evaluated_value is not None:
                    state["derived_fields"][s.bound_field] = s.evaluated_value
                step_results.append(
                    PRMStepResult(
                        step_index=s.step_index,
                        step_type="PHYSICS_DERIVATION",
                        content=s.content,
                        reward=rw,
                        passed=(rw > 0.0),
                        veto_reason=veto,
                        accumulated_state=copy.deepcopy(state),
                    )
                )

        # Final terminal step: check Thought-to-Answer faithfulness and gate violations
        if rep.faithfulness_conflicts or rep.gate_violations:
            term_idx = len(step_results) + 1
            reasons = rep.faithfulness_conflicts + rep.gate_violations
            veto = "; ".join(reasons)
            all_ok = False
            if first_fail is None:
                first_fail = term_idx
                fatal_msg = veto
            step_results.append(
                PRMStepResult(
                    step_index=term_idx,
                    step_type="PHYSICS_DERIVATION",
                    content="[FAITHFULNESS_AND_GATE_CHECK]",
                    reward=0.0,
                    passed=False,
                    veto_reason=veto,
                    accumulated_state=copy.deepcopy(state),
                )
            )

        overall = sum(s.reward for s in step_results) / max(1, len(step_results))
        if not all_ok:
            overall = min(overall, rep.overall_cot_score)
        traj_id = f"PRM_COT_{hashlib.sha256((raw_output or '').encode('utf-8', 'replace')).hexdigest()[:8]}"
        return PRMTrajectoryAudit(
            trajectory_id=traj_id,
            total_steps=len(step_results),
            steps=step_results,
            overall_score=round(overall, 4),
            first_failure_step=first_fail,
            all_steps_passed=all_ok,
            fatal_error=fatal_msg,
        )

    @classmethod
    def falsifiable_prm_probe(cls) -> bool:
        """Rule 4:
        1) Injects a 4-step G-code with Step 3 rapid plunge into stock Z=-5.0 -> Step 3 MUST get reward 0.0.
        2) Injects a 3-step CoT with Step 2 arithmetic hallucination (355/180 = 2.50) -> Step 2 MUST get reward 0.0.
        """
        gcode = """G90 G54 G21
M03 S2000
G00 Z-5.0
G01 X50.0 F200.0
"""
        audit_g = cls.audit_gcode_steps(gcode, safe_plane_z=5.0, stock_top_z=0.0)
        g_ok = (not audit_g.all_steps_passed and audit_g.first_failure_step == 3 and audit_g.steps[2].reward == 0.0)

        bad_cot = (
            "<think>\n"
            "[STAGE 1: INTENT_AND_GIVENS] Sy=355 MPa, sigma=180 MPa\n"
            "[STAGE 4: SYMBOLIC_DERIVATION] safety_factor = 355 / 180 = 2.50\n"
            "</think>\n"
            '{"world_state": {"safety_factor": 2.50, "fos_gate": "pass"}}'
        )
        audit_c = cls.audit_cot_steps(
            bad_cot,
            prompt="Sy=355 MPa, sigma=180 MPa",
            scenario={"task": "fea_fos", "inputs": {"Sy": 355.0, "sigma": 180.0}},
        )
        c_ok = (not audit_c.all_steps_passed and audit_c.first_failure_step == 2 and audit_c.steps[1].reward == 0.0)
        return g_ok and c_ok
