# -*- coding: utf-8 -*-
"""virtu_omni/affordance/saycan_grounding.py — Google SayCan / PaLM-E Physical Affordance Grounding.

Grounded in Google Research & Google DeepMind's seminal work:
"Do As I Can, Not As I Say: Grounding Language in Robotic Affordances"
(Ahn et al., arXiv:2204.01691 / Google Research)
and PaLM-E embodied grounding architectures.

Core Philosophy:
In industrial engineering software (SSCNC, SolidWorks, CIMCO, NX, AutoCAD, VERICUT),
an AI agent must NEVER execute an action purely based on language intent ("Say").
The action MUST be grounded in the machine/software physical affordance ("Can").

Joint Decision Rule:
    Score(action | state, goal) = P_LLM(action | goal, state) * P_Affordance(action | state)

If P_Affordance(action | state) == 0.0, the action is FATAL or IMPOSSIBLE in the current state.
The SayCan filter intercepts it, prevents software lockup / tool crash, and returns
the exact prerequisite remediation action.
"""

from __future__ import annotations

import enum
import logging
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

logger = logging.getLogger("virtu_omni.affordance.saycan")


class IndustrialSoftwareTarget(str, enum.Enum):
    SSCNC_7_2 = "SSCNC_7_2"                    # 斯沃数控仿真
    SOLIDWORKS_2021 = "SOLIDWORKS_2021"        # SolidWorks 3D CAD
    CIMCO_EDIT_2026 = "CIMCO_EDIT_2026"        # CIMCO CNC Editor
    AUTOCAD_2026 = "AUTOCAD_2026"              # AutoCAD 2D Drafting
    SIEMENS_NX_12 = "SIEMENS_NX_12"            # Siemens NX CAD/CAM
    VERICUT_9_6 = "VERICUT_9_6"                # CGTech VERICUT Simulation


@dataclass
class SoftwareStateSnapshot:
    """Snapshot of industrial software state captured via API/OCR/Window inspection."""
    software: IndustrialSoftwareTarget
    mode: str = "IDLE"                         # e.g., AUTO, EDIT, MDI, JOG for SSCNC
    active_document: Optional[str] = None
    has_active_sketch: bool = False
    sketch_is_closed: bool = False
    sketch_self_intersects: bool = False
    has_solid_body: bool = False
    selected_entities_count: int = 0
    alarm_active: bool = False
    alarm_code: Optional[str] = None
    door_closed: bool = True
    spindle_running: bool = False
    cycle_running: bool = False
    g00_rapid_collision_risk: bool = False
    syntax_errors_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AffordanceEvaluationResult:
    """Result of SayCan affordance evaluation on a candidate action."""
    action_name: str
    target_software: IndustrialSoftwareTarget
    p_llm: float                               # Prior probability from language model
    p_affordance: float                        # Feasibility probability [0.0, 1.0]
    joint_score: float                         # p_llm * p_affordance
    is_executable: bool                        # joint_score > threshold and p_affordance > 0
    veto_reason: Optional[str] = None
    remediation_action: Optional[str] = None   # Action required to enable affordance


class SayCanAffordanceEngine:
    """Evaluates and enforces physical affordances across industrial software packages."""

    @classmethod
    def evaluate_affordance(
        cls,
        action: str,
        state: SoftwareStateSnapshot,
        p_llm: float = 0.95,
    ) -> AffordanceEvaluationResult:
        """Computes P_Affordance(action | state) and joint SayCan score."""
        sw = state.software
        p_aff = 1.0
        veto: Optional[str] = None
        remediation: Optional[str] = None

        action_upper = action.upper().strip()

        # -------------------------------------------------------------
        # 1. SSCNC 7.2 (斯沃数控仿真)
        # -------------------------------------------------------------
        if sw == IndustrialSoftwareTarget.SSCNC_7_2:
            if "CYCLE_START" in action_upper:
                if state.alarm_active:
                    p_aff = 0.0
                    veto = f"SSCNC Alarm Active [{state.alarm_code}]; Cycle Start strictly prohibited"
                    remediation = "PRESS_RESET_OR_CLEAR_ALARM"
                elif not state.door_closed:
                    p_aff = 0.0
                    veto = "SSCNC Machine enclosure door is open; interlock safety prohibits Cycle Start"
                    remediation = "CLOSE_MACHINE_DOOR"
                elif state.mode not in ("AUTO", "MEM", "MDI"):
                    p_aff = 0.0
                    veto = f"SSCNC panel is in [{state.mode}] mode; Cycle Start requires [AUTO/MEM] mode"
                    remediation = "SWITCH_PANEL_MODE_TO_AUTO"

            elif "TOOL_CHANGE" in action_upper or "M06" in action_upper:
                if state.spindle_running:
                    p_aff = 0.0
                    veto = "Spindle is currently rotating; Tool Change (M06) forbidden without M05 spindle stop"
                    remediation = "COMMAND_M05_SPINDLE_STOP"

            elif "JOG" in action_upper:
                if state.mode not in ("JOG", "INC_FEED", "HANDLE"):
                    p_aff = 0.0
                    veto = f"Manual jog motion forbidden while panel is in [{state.mode}] mode"
                    remediation = "SWITCH_PANEL_MODE_TO_JOG"

        # -------------------------------------------------------------
        # 2. SOLIDWORKS 2021
        # -------------------------------------------------------------
        elif sw == IndustrialSoftwareTarget.SOLIDWORKS_2021:
            if "EXTRUDE_BOSS" in action_upper or "FEATURE_EXTRUDE" in action_upper:
                if not state.has_active_sketch:
                    p_aff = 0.0
                    veto = "No active sketch selected in SolidWorks FeatureManager"
                    remediation = "CREATE_OR_SELECT_SKETCH"
                elif not state.sketch_is_closed:
                    p_aff = 0.0
                    veto = "Active sketch contour is open/unclosed; cannot perform solid boss extrusion"
                    remediation = "CLOSE_SKETCH_CONTOUR"
                elif state.sketch_self_intersects:
                    p_aff = 0.0
                    veto = "Active sketch contains self-intersecting entities"
                    remediation = "REPAIR_SKETCH_SELF_INTERSECTION"

            elif "CUT_EXTRUDE" in action_upper:
                if not state.has_solid_body:
                    p_aff = 0.0
                    veto = "Cannot perform Cut-Extrude on document with 0 solid bodies"
                    remediation = "CREATE_BASE_FEATURE_FIRST"

            elif "FILLET" in action_upper or "CHAMFER" in action_upper:
                if state.selected_entities_count == 0:
                    p_aff = 0.0
                    veto = "Fillet/Chamfer requires at least 1 selected edge/face"
                    remediation = "SELECT_TARGET_EDGES"

        # -------------------------------------------------------------
        # 3. CIMCO EDIT 2026
        # -------------------------------------------------------------
        elif sw == IndustrialSoftwareTarget.CIMCO_EDIT_2026:
            if "TRANSMIT_DNC" in action_upper or "SEND_TO_CNC" in action_upper:
                if state.syntax_errors_count > 0:
                    p_aff = 0.0
                    veto = f"G-code contains {state.syntax_errors_count} syntax errors; transmission rejected"
                    remediation = "FIX_NC_SYNTAX_ERRORS"
                elif state.g00_rapid_collision_risk:
                    p_aff = 0.0
                    veto = "G00 Rapid Plunge Collision detected in stock material"
                    remediation = "ADD_APPROACH_LEAD_IN_PLANE"

        # -------------------------------------------------------------
        # 4. AUTOCAD 2026
        # -------------------------------------------------------------
        elif sw == IndustrialSoftwareTarget.AUTOCAD_2026:
            if "HATCH" in action_upper:
                if not state.sketch_is_closed:
                    p_aff = 0.0
                    veto = "AutoCAD hatch requires closed boundary geometry"
                    remediation = "CLOSE_BOUNDARY_POLYLINE"

        joint = p_llm * p_aff
        is_executable = (joint > 0.0) and (p_aff > 0.0)

        return AffordanceEvaluationResult(
            action_name=action,
            target_software=sw,
            p_llm=round(p_llm, 4),
            p_affordance=round(p_aff, 4),
            joint_score=round(joint, 4),
            is_executable=is_executable,
            veto_reason=veto,
            remediation_action=remediation,
        )

    @classmethod
    def filter_actions(
        cls,
        candidate_actions: List[Tuple[str, float]],
        state: SoftwareStateSnapshot,
    ) -> List[AffordanceEvaluationResult]:
        """Rank and filter multiple candidate actions according to joint SayCan scores."""
        results = [
            cls.evaluate_affordance(act, state, p_llm=p_prior)
            for act, p_prior in candidate_actions
        ]
        # Sort descending by joint score
        results.sort(key=lambda r: r.joint_score, reverse=True)
        return results

    @classmethod
    def falsifiable_affordance_probe(cls) -> bool:
        """Rule 4: Plant state with Emergency Stop / Alarm active in SSCNC; attempt Cycle Start.

        Must yield p_affordance == 0.0 and is_executable == False.
        """
        snapshot = SoftwareStateSnapshot(
            software=IndustrialSoftwareTarget.SSCNC_7_2,
            mode="AUTO",
            door_closed=True,
            alarm_active=True,
            alarm_code="EMG_STOP_ACTIVE",
        )
        res = cls.evaluate_affordance("CYCLE_START", snapshot, p_llm=0.99)
        return res.p_affordance == 0.0 and not res.is_executable and res.remediation_action is not None
