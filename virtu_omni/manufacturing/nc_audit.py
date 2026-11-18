"""Static, fail-closed capability and safety audit for multi-dialect CNC text.

Covers FANUC/ISO, Siemens Sinumerik 840D, and Heidenhain TNC across 3/4/5-axis milling,
turning, mill-turn (C-axis polar/cylindrical, Y-axis, B-axis head), and subspindle
transfer. Static text evidence never proves a machine post, kinematics, or simulation.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

_LINE_COMMENT = re.compile(r";[^\r\n]*|//[^\r\n]*")
_PAREN_OR_CALL = re.compile(
    r"\b(?:CYCLE\d+|SETMS|TRACYL|DC|ACP|ACN|IC)\s*\([^()]*\)|\([^()]*\)"
)


def _strip_comments(text: str) -> str:
    no_line = _LINE_COMMENT.sub(" ", str(text or "").upper())
    return _PAREN_OR_CALL.sub(
        lambda m: m.group(0) if m.group(0)[0] != "(" else " ",
        no_line,
    )
_ISO_WORD = re.compile(r"(?<![A-Z])([A-Z])\s*=?\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))")
_SIEMENS_ROT = re.compile(r"(?<![A-Z])([ABC])\s*=\s*(?:DC|ACP|ACN|IC)\(\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*\)")
_HEID_WORD = re.compile(r"(?<![A-Z])([XYZABCW])\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))")
_VARIABLE_AXIS = re.compile(r"(?<![A-Z])([XYZABCW])\s*=?\s*(?=#)")
_MOTION = re.compile(r"(?<![A-Z0-9])G\s*0*([0-3])\b")
_FANUC_TURNING_CYCLE = re.compile(r"(?<![A-Z0-9])G\s*(?:70|71|72|73|74|75|76)\b")
_SIEMENS_TURNING_CYCLE = re.compile(r"\bCYCLE95\d?\b|(?<![A-Z0-9])G\s*(?:72|73|74|75|76)\b")
_NON_MOTION_SETUP_RE = re.compile(
    r"^\s*(?:BEGIN\s+PGM|END\s+PGM|BLK\s+FORM|TOOL\s+CALL|CYCL\s+DEF|CYCL\s+CALL|"
    r"PLANE\s+SPATIAL|PLANE\s+RESET|FUNCTION\s+TCPM|FUNCTION\s+RESET|"
    r"FUNCTION\s+MODE|FUNCTION\s+POLAR|FUNCTION\s+CYLINDER|"
    r"CYCLE800|CYCLE8[134]|CYCLE95|G68\.2|G69|G53\.1|G10|G12\.1|G13\.1|"
    r"G0?7\.1|G28|G30|G53|TRAORI|TRAFOOF|TRANSMIT|TRACYL|SETMS|M10\b|M11\b)"
)


def _detect_dialect(clean: str) -> str:
    if re.search(r"\b(?:BEGIN\s+PGM|END\s+PGM|CYCL\s+DEF|PLANE\s+SPATIAL|FUNCTION\s+TCPM|TOOL\s+CALL)\b", clean):
        return "heidenhain"
    if re.search(r"\b(?:TRAORI|TRAFOOF|CYCLE800|CYCLE8[134]|CYCLE95|TRANSMIT|TRACYL|SETMS)\b", clean) or re.search(
        r"(?<![A-Z])[XYZABCW]\s*=", clean
    ):
        return "siemens"
    if re.search(r"(?:^%|(?<![A-Z])O\d{3,5}|\bG43\.[45]\b|\bG68\.2\b|\bG12\.1\b|\bG0?7\.1\b|\bG71\b|\bG0?[0-3]\b)", clean, re.M):
        return "fanuc"
    return "unknown"


def _paired_check(lines: List[str], open_pat: str, close_pat: str) -> Tuple[bool, bool, bool]:
    """Return (opened, closed_after_open, closed_before_open)."""
    open_idx = next((i for i, ln in enumerate(lines) if re.search(open_pat, ln)), None)
    if open_idx is None:
        return False, False, False
    close_after = any(re.search(close_pat, ln) for ln in lines[open_idx + 1:])
    return True, close_after, False


def _turning_cycles_in_line(line: str, dialect: str) -> List[str]:
    if dialect == "siemens":
        return _SIEMENS_TURNING_CYCLE.findall(line)
    if dialect == "heidenhain":
        return re.findall(r"\bCYCL\s+DEF\s+810\b|\bFUNCTION\s+MODE\s+TURN\b", line)
    # In ISO/FANUC, G70/G71 paired with G90+G17/G18/G54 (or Haas G71 I..J..K..L..) is not turning.
    if re.search(r"\bG7[01]\b", line):
        if re.search(r"\bG90\b", line) and re.search(r"\bG1[789]\b", line):
            return []
        if re.search(r"\bG71\b", line) and re.search(r"\bI[-+]?\d", line) and re.search(r"\bJ[-+]?\d", line):
            return []
    return _FANUC_TURNING_CYCLE.findall(line)


def audit_nc_capability(
    program: str,
    required_features: Optional[Iterable[str]] = None,
    *,
    strict_feature_check: bool = False,
) -> Dict[str, Any]:
    """Parse literal axis words and report conservative machining & safety candidates.

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
    clean = _strip_comments(text)
    dialect = _detect_dialect(clean)
    raw_lines = [ln.strip() for ln in re.split(r"[\r\n]+", clean) if ln.strip()]

    modal_motion: Optional[int] = None
    observed_axes: Set[str] = set()
    feed_rotary_axes: Set[str] = set()
    index_rotary_axes: Set[str] = set()
    max_rotary_axes_in_feed_block = 0
    simultaneous_feed_blocks: List[Dict[str, List[str]]] = []
    turning_cycles_set: Set[str] = set()
    unknown_axis_words: Set[str] = set()
    safety_issues: List[str] = []

    in_polar = False
    in_cylindrical = False
    polar_observed = False
    cylindrical_observed = False
    has_live_tool = False
    has_subspindle = False
    clamped_axes: Set[str] = set()
    last_rotary_seen: Set[str] = set()

    for raw_line in raw_lines:
        line = raw_line.strip()
        if not line:
            continue
        for tc in _turning_cycles_in_line(line, dialect):
            turning_cycles_set.add(tc.replace(" ", ""))
        unknown_axis_words.update(_VARIABLE_AXIS.findall(line))

        # Mode / interpolation / clamp / live-tool / subspindle markers
        if re.search(r"\bG12\.1\b|\bTRANSMIT\b|\bFUNCTION\s+POLAR\s+ON\b", line):
            in_polar = True
            polar_observed = True
        elif re.search(r"\bG13\.1\b|\bFUNCTION\s+POLAR\s+OFF\b", line):
            in_polar = False
        if re.search(r"\bG0?7\.1\s+C[1-9]\d*(?:\.\d+)?\b|\bTRACYL\(|\bFUNCTION\s+CYLINDER\s+R", line):
            in_cylindrical = True
            cylindrical_observed = True
        elif re.search(r"\bG0?7\.1\s+C0(?:\.0+)?\b|\bFUNCTION\s+CYLINDER\s+OFF\b", line):
            in_cylindrical = False
        if re.search(r"\bTRAFOOF\b", line):
            in_polar = False
            in_cylindrical = False
        if re.search(r"\b(?:M13[34]|M200|M201|SETMS\(2\))\b|\bFUNCTION\s+MODE\s+MILL\b", line) or re.search(r"\bP12\b", line) or re.search(r"\bSPOS\s*=", line):
            has_live_tool = True
        if re.search(r"\b(?:M268|M269|M203)\b", line):
            has_subspindle = True
        if re.search(r"\bM11\b", line):
            clamped_axes.clear()
        elif re.search(r"\bM10\b", line):
            clamped_axes.update(last_rotary_seen or {"A", "B", "C"})

        if _NON_MOTION_SETUP_RE.match(line) or re.match(r"^\s*Q\d+\s*=", line):
            continue

        # Determine motion mode (ISO/Siemens G0..3 or Heidenhain L ... FMAX/F..)
        if dialect == "heidenhain" and re.match(r"^L\s+", line):
            if re.search(r"\bFMAX\b", line):
                modal_motion = 0
            elif re.search(r"\bDR[+-]\b", line):
                modal_motion = 2
            elif re.search(r"\bF\s*\d", line):
                modal_motion = 1
            word_pairs = _HEID_WORD.findall(line)
        else:
            motion_codes = [int(value) for value in _MOTION.findall(line)]
            if motion_codes:
                modal_motion = motion_codes[-1]
            elif re.search(r"(?<![A-Z0-9])G\s*8[1-9]\b", line):
                # Canned cycles (G81-G89) are Group-01 cycle motion, never G00 rapid plunge.
                modal_motion = 1
            elif re.search(r"(?<![A-Z0-9])G\s*80\b", line):
                modal_motion = None
            word_pairs = _ISO_WORD.findall(line) + _SIEMENS_ROT.findall(line)

        words = {letter: float(value) for letter, value in word_pairs if letter in "XYZABCW"}
        if not words or modal_motion is None:
            continue

        if "W" in words:
            has_subspindle = True

        # Virtual Y inside Siemens TRANSMIT / Heidenhain FUNCTION POLAR maps to physical C-axis
        physical_words = dict(words)
        if in_polar and dialect in ("siemens", "heidenhain") and "Y" in physical_words:
            physical_words.pop("Y")
            physical_words.setdefault("C", words["Y"])

        linear_here = set(physical_words) & {"X", "Y", "Z"}
        rotary_here = set(physical_words) & {"A", "B", "C"}
        if rotary_here:
            last_rotary_seen = set(rotary_here)
        observed_axes.update(set(physical_words) & {"X", "Y", "Z", "A", "B", "C", "W"})

        if modal_motion == 0 and "Z" in physical_words and physical_words["Z"] < 0.0:
            safety_issues.append("unsafe_g00_negative_z_plunge")

        if modal_motion in (1, 2, 3):
            feed_rotary_axes.update(rotary_here)
            max_rotary_axes_in_feed_block = max(max_rotary_axes_in_feed_block, len(rotary_here))
            if rotary_here & clamped_axes:
                safety_issues.append("rotary_feed_while_clamped")
            linear_seen = observed_axes & {"X", "Y", "Z"}
            if rotary_here and (len(linear_here) == 3 or (linear_here and len(linear_seen) == 3)):
                simultaneous_feed_blocks.append({
                    "linear_axes": sorted(linear_here if len(linear_here) == 3 else linear_seen),
                    "rotary_axes": sorted(rotary_here),
                })
        elif modal_motion == 0:
            index_rotary_axes.update(rotary_here)

    # Kinematic / pairing checks across the program
    rtcp_fanuc_open, rtcp_fanuc_close, _ = _paired_check(raw_lines, r"\bG43\.[45]\b", r"\bG49\b")
    rtcp_siemens_open, rtcp_siemens_close, _ = _paired_check(raw_lines, r"\bTRAORI\b", r"\bTRAFOOF\b")
    rtcp_heid_open, rtcp_heid_close, _ = _paired_check(
        raw_lines, r"(?:FUNCTION\s+TCPM|\bM128\b)", r"(?:FUNCTION\s+RESET\s+TCPM|\bM129\b)"
    )
    has_rtcp_open = rtcp_fanuc_open or rtcp_siemens_open or rtcp_heid_open
    rtcp_properly_closed = (
        (not rtcp_fanuc_open or rtcp_fanuc_close)
        and (not rtcp_siemens_open or rtcp_siemens_close)
        and (not rtcp_heid_open or rtcp_heid_close)
    )
    if has_rtcp_open and not rtcp_properly_closed:
        safety_issues.append("rtcp_not_canceled")

    tilt_fanuc_open, tilt_fanuc_close, _ = _paired_check(raw_lines, r"\bG68\.2\b", r"\bG69\b")
    tilt_siemens_open, tilt_siemens_close, _ = _paired_check(raw_lines, r"CYCLE800\([^)]+\)", r"CYCLE800\(\s*\)")
    tilt_heid_open, tilt_heid_close, _ = _paired_check(raw_lines, r"PLANE\s+SPATIAL", r"PLANE\s+RESET")
    has_tilt_3plus2 = tilt_fanuc_open or tilt_siemens_open or tilt_heid_open
    if has_tilt_3plus2 and not (
        (not tilt_fanuc_open or tilt_fanuc_close)
        and (not tilt_siemens_open or tilt_siemens_close)
        and (not tilt_heid_open or tilt_heid_close)
    ):
        safety_issues.append("tilted_workplane_not_canceled")

    if polar_observed:
        po_f, pc_f, _ = _paired_check(raw_lines, r"\bG12\.1\b", r"\bG13\.1\b")
        po_s, pc_s, _ = _paired_check(raw_lines, r"\bTRANSMIT\b", r"\bTRAFOOF\b")
        po_h, pc_h, _ = _paired_check(raw_lines, r"\bFUNCTION\s+POLAR\s+ON\b", r"\bFUNCTION\s+POLAR\s+OFF\b")
        if (po_f and not pc_f) or (po_s and not pc_s) or (po_h and not pc_h):
            safety_issues.append("polar_interpolation_not_canceled")
    if cylindrical_observed:
        co_f, cc_f, _ = _paired_check(
            raw_lines, r"\bG0?7\.1\s+C[1-9]\d*(?:\.\d+)?\b", r"\bG0?7\.1\s+C0(?:\.0+)?\b"
        )
        co_s, cc_s, _ = _paired_check(raw_lines, r"TRACYL\(", r"\bTRAFOOF\b")
        co_h, cc_h, _ = _paired_check(raw_lines, r"\bFUNCTION\s+CYLINDER\s+R", r"\bFUNCTION\s+CYLINDER\s+OFF\b")
        if (co_f and not cc_f) or (co_s and not cc_s) or (co_h and not cc_h):
            safety_issues.append("cylindrical_interpolation_not_canceled")

    m268_idx = next((i for i, ln in enumerate(raw_lines) if re.search(r"\bM268\b", ln)), None)
    m69_idx = next((i for i, ln in enumerate(raw_lines) if re.search(r"\bM69\b", ln)), None)
    if m69_idx is not None and (m268_idx is None or m69_idx < m268_idx):
        safety_issues.append("subspindle_unclamp_before_clamp")

    turning_cycles = sorted(turning_cycles_set)
    rotary_axes = sorted(observed_axes & {"A", "B", "C"})
    feed_blocks = [block for block in simultaneous_feed_blocks if block["rotary_axes"]]

    candidates: List[str] = []
    if turning_cycles:
        candidates.append("turning_cycle_observed")
    requested = [str(item) for item in (required_features or [])]
    if set("XYZ").issubset(observed_axes) and not rotary_axes:
        if has_rtcp_open or (has_tilt_3plus2 and "milling_3axis" in requested):
            safety_issues.append("three_axis_multiaxis_token_misuse")
        elif not has_tilt_3plus2 and not turning_cycles and not has_live_tool and not has_subspindle:
            candidates.append("milling_3axis_candidate")

    is_mill_turn_like = bool(
        (turning_cycles and ("C" in feed_rotary_axes or has_live_tool or polar_observed or cylindrical_observed or has_subspindle))
        or (has_live_tool and (has_subspindle or "C" in observed_axes))
    )

    if len(rotary_axes) == 1 and not is_mill_turn_like:
        if any(len(block["rotary_axes"]) == 1 for block in feed_blocks):
            candidates.append("milling_4axis_simultaneous_candidate")
        elif index_rotary_axes:
            candidates.append("milling_4axis_indexing_candidate")
    if len(rotary_axes) >= 2 and not is_mill_turn_like:
        if any(len(block["rotary_axes"]) >= 2 for block in feed_blocks):
            candidates.append("milling_5axis_simultaneous_candidate")
            if not has_rtcp_open:
                safety_issues.append("five_axis_simultaneous_missing_rtcp")
        elif len(index_rotary_axes) >= 2 or has_tilt_3plus2:
            candidates.append("milling_5axis_positioning_candidate")
        else:
            candidates.append("multiple_rotary_axes_observed")
    elif has_tilt_3plus2 and "milling_5axis_positioning_candidate" not in candidates:
        candidates.append("milling_5axis_positioning_candidate")

    if has_rtcp_open and rtcp_properly_closed:
        candidates.append("rtcp_5axis_observed")
    if has_tilt_3plus2:
        candidates.append("tilted_workplane_3plus2_observed")
    if polar_observed:
        candidates.append("polar_interpolation_observed")
    if cylindrical_observed:
        candidates.append("cylindrical_interpolation_observed")

    if is_mill_turn_like:
        candidates.append("mill_turn_candidate_unverified")
        if "C" in observed_axes or polar_observed or cylindrical_observed:
            candidates.append("mill_turn_c_axis_candidate")
        if "Y" in observed_axes:
            candidates.append("mill_turn_y_axis_candidate")
        if "B" in observed_axes:
            candidates.append("mill_turn_b_axis_head_candidate")
    if has_subspindle:
        candidates.append("subspindle_transfer_candidate")

    supported_static = {
        "milling_3axis": "milling_3axis_candidate",
        "milling_4axis_indexed": "milling_4axis_indexing_candidate",
        "milling_4axis_simultaneous": "milling_4axis_simultaneous_candidate",
        "milling_5axis_3plus2": "milling_5axis_positioning_candidate",
        "milling_5axis_simultaneous": "milling_5axis_simultaneous_candidate",
        "turning": "turning_cycle_observed",
        "mill_turn_off_axis_milling": (
            "mill_turn_c_axis_candidate" if strict_feature_check else "mill_turn_candidate_unverified"
        ),
        "mill_turn_y_axis_milling": (
            "mill_turn_y_axis_candidate" if strict_feature_check else "mill_turn_candidate_unverified"
        ),
        "subspindle_transfer": (
            "subspindle_transfer_candidate" if strict_feature_check else "mill_turn_candidate_unverified"
        ),
    }
    unknown_features = sorted(set(requested) - set(supported_static))
    unmatched = [feature for feature in requested
                 if feature in supported_static and supported_static[feature] not in candidates]
    if strict_feature_check and "milling_5axis_simultaneous" in requested and "rtcp_5axis_observed" not in candidates:
        if "milling_5axis_simultaneous" not in unmatched:
            unmatched.append("milling_5axis_simultaneous")

    issues: List[str] = []
    if unknown_features:
        issues.append("unknown_required_features:" + ",".join(unknown_features))
    if unmatched:
        issues.append("required_motion_not_observed:" + ",".join(unmatched))
    if "mill_turn_candidate_unverified" in candidates and not strict_feature_check:
        issues.append("live_tooling_spindle_sync_and_transfer_require_controller_specific_review")
    safety_issues = list(dict.fromkeys(safety_issues))
    if strict_feature_check and safety_issues:
        issues.extend(safety_issues)
    if unknown_axis_words:
        issues.append("macro_variable_axis_values_not_resolved:" + ",".join(sorted(unknown_axis_words)))

    return {
        "status": "static_match" if not issues else "insufficient_evidence",
        "passed": not issues,
        "detected_dialect": dialect,
        "requested_features": requested,
        "feature_candidates": candidates,
        "observed_axes": sorted(observed_axes),
        "rotary_axes": rotary_axes,
        "feed_rotary_axes": sorted(feed_rotary_axes),
        "index_rotary_axes": sorted(index_rotary_axes),
        "max_rotary_axes_in_feed_block": max_rotary_axes_in_feed_block,
        "simultaneous_feed_blocks": feed_blocks,
        "turning_cycles": turning_cycles,
        "kinematic_markers": {
            "rtcp_opened": has_rtcp_open,
            "rtcp_closed": rtcp_properly_closed if has_rtcp_open else False,
            "tilted_workplane_3plus2": has_tilt_3plus2,
            "polar_interpolation": polar_observed,
            "cylindrical_interpolation": cylindrical_observed,
            "live_tooling_observed": has_live_tool,
            "subspindle_observed": has_subspindle,
        },
        "safety_issues": safety_issues,
        "issues": issues,
        "program_release_allowed": False,
        "basis": "static_program_parse",
        "limitation": "Static text evidence only; exact controller/post, machine kinematics, tool orientation, collision, stock, and simulation remain unverified.",
    }
