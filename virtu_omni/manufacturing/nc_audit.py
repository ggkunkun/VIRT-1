"""Static, fail-closed capability audit for CNC text.

This identifies motion words and structural candidates. It does not prove a controller
post, machine kinematics, collision-free motion, or production readiness.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Set

_COMMENT = re.compile(r"\([^()]*\)|;[^\r\n]*|//[^\r\n]*")
_WORD = re.compile(r"(?<![A-Z])([A-Z])\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))")
_VARIABLE_AXIS = re.compile(r"(?<![A-Z])([XYZABC])\s*(?=#)")
_MOTION = re.compile(r"(?<![A-Z0-9])G\s*0*([0-3])\b")
_TURNING_CYCLE = re.compile(r"(?<![A-Z0-9])G\s*(?:70|71|72|73|74|75|76)\b")


def audit_nc_capability(program: str, required_features: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    """Parse literal axis words and report conservative machining candidates.

    A feature match remains a static observation. ``program_release_allowed`` is always
    false because this parser has no exact controller, post, machine, or simulation proof.
    """
    text = str(program or "")
    if not text.strip():
        return {
            "status": "needs_input", "passed": False,
            "issues": ["nc_program_empty"], "program_release_allowed": False,
            "basis": "static_program_parse",
        }
    clean = _COMMENT.sub(" ", text).upper()
    modal_motion: Optional[int] = None
    observed_axes: Set[str] = set()
    feed_rotary_axes: Set[str] = set()
    index_rotary_axes: Set[str] = set()
    max_rotary_axes_in_feed_block = 0
    simultaneous_feed_blocks: List[Dict[str, List[str]]] = []
    turning_cycles = sorted(set(_TURNING_CYCLE.findall(clean)))
    unknown_axis_words: Set[str] = set()

    for raw_line in clean.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        motion_codes = [int(value) for value in _MOTION.findall(line)]
        if motion_codes:
            modal_motion = motion_codes[-1]
        words = {letter: float(value) for letter, value in _WORD.findall(line)
                 if letter in "XYZABC"}
        unknown_axis_words.update(_VARIABLE_AXIS.findall(line))
        if not words or modal_motion is None:
            continue
        linear_here = set(words) & {"X", "Y", "Z"}
        rotary_here = set(words) & {"A", "B", "C"}
        observed_axes.update(words)
        if modal_motion in (1, 2, 3):
            feed_rotary_axes.update(rotary_here)
            max_rotary_axes_in_feed_block = max(max_rotary_axes_in_feed_block, len(rotary_here))
            if len(linear_here) == 3 and rotary_here:
                simultaneous_feed_blocks.append({
                    "linear_axes": sorted(linear_here),
                    "rotary_axes": sorted(rotary_here),
                })
        elif modal_motion == 0:
            index_rotary_axes.update(rotary_here)

    rotary_axes = sorted(observed_axes & {"A", "B", "C"})
    feed_blocks = [block for block in simultaneous_feed_blocks
                   if block["rotary_axes"]]
    candidates: List[str] = []
    if turning_cycles:
        candidates.append("turning_cycle_observed")
    if set("XYZ").issubset(observed_axes) and not rotary_axes:
        candidates.append("milling_3axis_candidate")
    if len(rotary_axes) == 1:
        if any(len(block["rotary_axes"]) == 1 for block in feed_blocks):
            candidates.append("milling_4axis_simultaneous_candidate")
        elif index_rotary_axes:
            candidates.append("milling_4axis_indexing_candidate")
    if len(rotary_axes) >= 2:
        if any(len(block["rotary_axes"]) >= 2 for block in feed_blocks):
            candidates.append("milling_5axis_simultaneous_candidate")
        elif len(index_rotary_axes) >= 2:
            candidates.append("milling_5axis_positioning_candidate")
        else:
            candidates.append("multiple_rotary_axes_observed")
    mill_turn_candidate = bool(turning_cycles and "C" in feed_rotary_axes)
    if mill_turn_candidate:
        candidates.append("mill_turn_candidate_unverified")

    requested = [str(item) for item in (required_features or [])]
    supported_static = {
        "milling_3axis": "milling_3axis_candidate",
        "milling_4axis_indexed": "milling_4axis_indexing_candidate",
        "milling_4axis_simultaneous": "milling_4axis_simultaneous_candidate",
        "milling_5axis_3plus2": "milling_5axis_positioning_candidate",
        "milling_5axis_simultaneous": "milling_5axis_simultaneous_candidate",
        "turning": "turning_cycle_observed",
        "mill_turn_off_axis_milling": "mill_turn_candidate_unverified",
        "mill_turn_y_axis_milling": "mill_turn_candidate_unverified",
        "subspindle_transfer": "mill_turn_candidate_unverified",
    }
    unknown_features = sorted(set(requested) - set(supported_static))
    unmatched = [feature for feature in requested
                 if feature in supported_static and supported_static[feature] not in candidates]
    issues = []
    if unknown_features:
        issues.append("unknown_required_features:" + ",".join(unknown_features))
    if unmatched:
        issues.append("required_motion_not_observed:" + ",".join(unmatched))
    if "mill_turn_candidate_unverified" in candidates:
        issues.append("live_tooling_spindle_sync_and_transfer_require_controller_specific_review")
    if unknown_axis_words:
        issues.append("macro_variable_axis_values_not_resolved:" + ",".join(sorted(unknown_axis_words)))

    return {
        "status": "static_match" if not issues else "insufficient_evidence",
        "passed": not issues,
        "requested_features": requested,
        "feature_candidates": candidates,
        "observed_axes": sorted(observed_axes),
        "rotary_axes": rotary_axes,
        "feed_rotary_axes": sorted(feed_rotary_axes),
        "index_rotary_axes": sorted(index_rotary_axes),
        "max_rotary_axes_in_feed_block": max_rotary_axes_in_feed_block,
        "simultaneous_feed_blocks": feed_blocks,
        "turning_cycles": turning_cycles,
        "issues": issues,
        "program_release_allowed": False,
        "basis": "static_program_parse",
        "limitation": "Static text evidence only; exact controller/post, machine kinematics, tool orientation, collision, stock, and simulation remain unverified.",
    }
