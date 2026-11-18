# -*- coding: utf-8 -*-
"""Role and output contracts for the Super Agent's eight industrial facets.

These contracts describe the proof each specialist must return. They keep the existing
method/delegate implementations, while making role identity and required result shape
explicit at the REACT tool boundary.
"""

from __future__ import annotations

from typing import Any


FACET_ROLES = {
    "architect": {
        "title": "Architect",
        "evidence": "parsed manufacturing intent and explicit assumptions",
    },
    "modeling": {
        "title": "Modeling",
        "evidence": "parametric feature tree and generated CAD artifact or explicit draft status",
    },
    "standards": {
        "title": "Standards",
        "evidence": "drawing specification, units, tolerances, and datum choices",
    },
    "machining": {
        "title": "Machining",
        "evidence": "NC program and deterministic CNC semantic/sandbox result",
    },
    "cae": {
        "title": "CAE",
        "evidence": "stress result, material basis, and safety factor verdict",
    },
    "auditor": {
        "title": "Auditor",
        "evidence": "measured gate results; missing evidence remains unverified",
    },
    "memory": {
        "title": "Memory",
        "evidence": "retrieval/commit record with source and run provenance",
    },
    "desktop": {
        "title": "Desktop",
        "evidence": "observed target and input_guard result for any input action",
    },
}

TOOL_ROLE = {
    "parse_intent": "architect",
    "generate_parametric_cad": "modeling",
    "generate_standards_drawing": "standards",
    "generate_cam_toolpath": "machining",
    "select_machine_and_stock": "machining",
    "coordinate_contract": "auditor",
    "audit_nc_capability": "auditor",
    "generate_validated_g71": "machining",
    "verify_cae_stress": "cae",
    "solve_lame_cylinder": "cae",
    "pinn_stress_surrogate": "cae",
    "audit_sandbox_simulation": "auditor",
    "verify_product_integrity": "auditor",
    "inspect_step_artifact": "auditor",
    "recall_hindsight_memory": "memory",
    "recall_vericut_training": "memory",
    "query_training_cases": "memory",
    "commit_experience": "memory",
    "trigger_sleep_cycle": "memory",
    "capability_lookup": "memory",
    "capability_guard": "auditor",
    "dispatch_modality": "desktop",
    "desktop_gui": "desktop",
    "mouse_control": "desktop",
    "keyboard_control": "desktop",
    "screen_control": "desktop",
    "agent_desktop": "desktop",
}

REQUIRED_RESULT_KEYS = {
    "parse_intent": ("parsed_spec",),
    "generate_parametric_cad": ("feature_tree", "solidworks_vba"),
    "generate_standards_drawing": ("drawing_spec",),
    "generate_cam_toolpath": ("macro_b_code",),
    "select_machine_and_stock": ("status", "requirements", "stock"),
    "coordinate_contract": ("status",),
    "audit_nc_capability": ("status", "program_release_allowed"),
    "verify_cae_stress": (
        "safety_factor_fos", "fos_passed", "calculation_verified", "evidence_basis"
    ),
    "audit_sandbox_simulation": ("passed",),
    "verify_product_integrity": ("passed", "verified"),
    "inspect_step_artifact": ("passed", "verified"),
    "solve_lame_cylinder": ("passed", "applicable"),
    "generate_validated_g71": ("passed", "applicable"),
}


def role_for_tool(tool_name: str) -> dict[str, Any]:
    role_id = TOOL_ROLE.get(tool_name, "")
    if not role_id:
        return {"id": "utility", "title": "Utility", "evidence": "tool-specific result"}
    return {"id": role_id, **FACET_ROLES[role_id]}


def validate_facet_result(tool_name: str, value: Any) -> dict[str, Any]:
    """Reject malformed specialist results; a domain gate returning FAIL stays valid."""
    role = role_for_tool(tool_name)
    required = REQUIRED_RESULT_KEYS.get(tool_name, ())
    if not required:
        return {"passed": True, "role": role, "issues": []}
    if not isinstance(value, dict):
        return {"passed": False, "role": role,
                "issues": ["result_must_be_object"]}
    missing = [key for key in required if key not in value]
    return {"passed": not missing, "role": role,
            "issues": [f"required_result_key_missing:{key}" for key in missing]}
