# -*- coding: utf-8 -*-
"""GBNF (GGML BNF) Grammar Specifications and Converters for Virtu Industrial Serving.

Provides constrained logit-level decoding grammars for llama.cpp / Ollama endpoints:
1. GCODE_GBNF: Strict ISO/FANUC NC block grammar enforcing valid G/M words, coordinates,
   feeds, spindle speeds, tool offsets, and macro variables.
2. TOOLCALL_GBNF: Strict JSON structure enforcing valid {"tool": "...", "arguments": {...}}
   where tool belongs to registered industrial CAD/CAM tools.
3. schema_to_gbnf: Automated compiler transforming JSON Schema / Pydantic schemas into GBNF.
4. validate_gcode_syntax: High-speed AST/lexer validator for NC safety.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

# 17 Registered Industrial CAD/CAM Tools in the Virtu Platform
REGISTERED_CADCAM_TOOLS = [
    "cadcam_preflight",
    "cadcam_solidworks_model",
    "cadcam_nx_journal",
    "cadcam_autocad_draw",
    "cadcam_cimco_validate",
    "cadcam_vericut_simulate",
    "cadcam_sscnc_control",
    "cadcam_extreme_chain",
    "cadcam_run_full_chain",
    "cadcam_desktop_gui",
    "cadcam_visual_inspect",
    "cadcam_universal_geometry",
    "cadcam_cae_stress_analysis",
    "cadcam_sheetmetal_nest",
    "cadcam_step_reverse",
    "cadcam_assembly_build",
    "cadcam_feature_ops",
]

# Strict ISO / FANUC CNC G-code GBNF Grammar
GCODE_GBNF = r"""root ::= (line "\n")* line?
line ::= ws? (block | comment)? ws?
block ::= (word ws?)+
word ::= [gG] digit+ ("." digit+)? | [mM] digit+ | [xXyYzZaAbBcCuUvVwW] signed_float | [iIjJkKrR] signed_float | [fFsS] float | [tTpPdDhHqQ] digit+ | [nN] digit+ | macro_assign
macro_assign ::= "#" digit+ ws? "=" ws? (signed_float | macro_expr)
macro_expr ::= "[" ws? signed_float ws? [+\-*/] ws? signed_float ws? "]"
float ::= digit+ ("." digit+)?
signed_float ::= ("+" | "-")? float
digit ::= [0-9]
ws ::= [ \t]+
comment ::= "(" [^)\n]* ")" | ";" [^\n]*
"""

# Generic JSON GBNF primitives
JSON_PRIMITIVES_GBNF = r"""value ::= object | array | string | number | ("true" | "false" | "null") ws
object ::= "{" ws (string ":" ws value ("," ws string ":" ws value)*)? "}" ws
array ::= "[" ws (value ("," ws value)*)? "]" ws
string ::= "\"" ([^"\\] | "\\" (["\\/bfnrt] | "u" [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F]))* "\"" ws
number ::= ("-"? ([0-9] | [1-9] [0-9]*)) ("." [0-9]+)? ([eE] [-+]? [0-9]+)? ws
ws ::= ([ \t\n\r]*)
"""


def build_toolcall_gbnf(tool_names: Optional[List[str]] = None) -> str:
    """Build a GBNF grammar strictly constraining output to a JSON tool call."""
    tools = tool_names or REGISTERED_CADCAM_TOOLS
    tool_literals = " | ".join(f'"\\"{t}\\""' for t in tools)

    return f"""root ::= "{{" ws "\\"tool\\"" ws ":" ws tool_name ws "," ws "\\"arguments\\"" ws ":" ws object ws "}}"
tool_name ::= {tool_literals}
value ::= object | array | string | number | ("true" | "false" | "null") ws
object ::= "{{" ws (string ":" ws value ("," ws string ":" ws value)*)? "}}" ws
array ::= "[" ws (value ("," ws value)*)? "]" ws
string ::= "\\"" ([^"\\\\] | "\\\\" (["\\\\/bfnrt] | "u" [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F]))* "\\"" ws
number ::= ("-"? ([0-9] | [1-9] [0-9]*)) ("." [0-9]+)? ([eE] [-+]? [0-9]+)? ws
ws ::= ([ \\t\\n\\r]*)
"""


def schema_to_gbnf(schema: Dict[str, Any], root_name: str = "root") -> str:
    """Compile a JSON Schema dictionary into equivalent GBNF grammar rules.

    Supports:
    - type: "object", "array", "string", "number", "integer", "boolean"
    - enum: list of string or number constants
    - properties & required fields
    """
    rules: Dict[str, str] = {}
    rule_counter = [0]

    def _compile_node(node: Dict[str, Any], name: str) -> str:
        if "enum" in node:
            choices = []
            for item in node["enum"]:
                if isinstance(item, str):
                    escaped = item.replace('"', '\\"')
                    choices.append(f'"\\"{escaped}\\""')
                elif isinstance(item, bool):
                    choices.append(f'"{str(item).lower()}"')
                else:
                    choices.append(f'"{item}"')
            rule_body = " | ".join(choices)
            rules[name] = f"{rule_body} ws"
            return name

        ntype = node.get("type", "any")

        if ntype == "object":
            props = node.get("properties", {})
            required = set(node.get("required", []))
            if not props:
                rules[name] = '"{}" ws | "{" ws (string ":" ws value ("," ws string ":" ws value)*)? "}" ws'
                return name

            prop_rules = []
            for p_name, p_schema in props.items():
                rule_counter[0] += 1
                sub_name = f"{name}_{p_name}_{rule_counter[0]}"
                _compile_node(p_schema, sub_name)
                escaped_key = p_name.replace('"', '\\"')
                prop_rules.append(f'"\\"{escaped_key}\\"" ws ":" ws {sub_name}')

            # For ordered strict JSON object layout
            if required == set(props.keys()):
                # All required
                inner = ' "," ws '.join(prop_rules)
                rules[name] = f'"{{ " ws {inner} ws " }}" ws'
            else:
                rules[name] = '"{" ws (string ":" ws value ("," ws string ":" ws value)*)? "}" ws'
            return name

        elif ntype == "array":
            items = node.get("items", {})
            rule_counter[0] += 1
            item_name = f"{name}_item_{rule_counter[0]}"
            _compile_node(items if items else {"type": "any"}, item_name)
            rules[name] = f'"[" ws ({item_name} ("," ws {item_name})*)? "]" ws'
            return name

        elif ntype == "string":
            rules[name] = 'string'
            return name

        elif ntype in ("number", "integer"):
            rules[name] = 'number'
            return name

        elif ntype == "boolean":
            rules[name] = '("true" | "false") ws'
            return name

        rules[name] = 'value'
        return name

    _compile_node(schema, root_name)

    gbnf_lines = [f"{k} ::= {v}" for k, v in rules.items()]
    gbnf_lines.append(JSON_PRIMITIVES_GBNF.strip())
    return "\n".join(gbnf_lines) + "\n"


_GCODE_LINE_RE = re.compile(
    r"""
    ^
    (?P<linenum>[Nn]\d+\s+)?
    (?P<words>(?:[GgMmXxYyZzAaBbCcUuVvWwIiJjKkRrFfSsTtPpDdHhQq][+-]?\d+(?:\.\d+)?\s*)+)?
    (?P<comment>\([^\n]*\)|;[^\n]*)?
    $
    """,
    re.VERBOSE,
)

_WORD_EXTRACT_RE = re.compile(r"([A-Za-z])([+-]?\d+(?:\.\d+)?)")


def validate_gcode_syntax(code: str) -> Tuple[bool, List[str]]:
    """Validate G-code program syntax and industrial safety constraints.

    Returns:
        (is_valid, list_of_errors_or_warnings)
    """
    errors: List[str] = []
    lines = code.strip().splitlines()

    current_motion_modal: Optional[str] = None
    has_spindle_start = False
    active_feedrate: Optional[float] = None

    for idx, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("%"):
            continue

        # Check unclosed comment parentheses
        if line.count("(") != line.count(")"):
            errors.append(f"Line {idx}: Unbalanced comment parentheses: '{line}'")
            continue

        words = _WORD_EXTRACT_RE.findall(line)
        if not words and not (line.startswith("(") or line.startswith(";")):
            errors.append(f"Line {idx}: No valid G-code words found: '{line}'")
            continue

        line_words = {letter.upper(): float(val) for letter, val in words}

        # Track G-modal motion
        for letter, val in words:
            word_str = f"{letter.upper()}{int(float(val)):02d}"
            if word_str in ("G00", "G01", "G02", "G03", "G71", "G72", "G73", "G76", "G81", "G83"):
                current_motion_modal = word_str
            if word_str in ("M03", "M04"):
                has_spindle_start = True

        if "F" in line_words:
            active_feedrate = line_words["F"]

        # Check cutting move without feedrate
        if current_motion_modal in ("G01", "G02", "G03"):
            has_linear_motion = any(axis in line_words for axis in ("X", "Y", "Z", "U", "W"))
            if has_linear_motion and active_feedrate is None:
                errors.append(f"Line {idx}: Cutting move {current_motion_modal} without active feedrate (F)")

        # High-speed plunge sentinel: only a pure Z rapid is unambiguous.
        # A lathe block like "G42 G00 X[#102] Z-46" moves along the OD, not into stock.
        has_x = ("X" in line_words) or bool(re.search(r"[Xx]\s*[\[#]", raw_line))
        if current_motion_modal == "G00" and "Z" in line_words and line_words["Z"] < -0.01 and not has_x:
            errors.append(
                f"Line {idx}: CRITICAL SAFETY VIOLATION - Rapid plunge G00 into material (Z={line_words['Z']} < 0)"
            )

    is_valid = len([e for e in errors if "CRITICAL" in e or "Unbalanced" in e]) == 0
    return is_valid, errors
