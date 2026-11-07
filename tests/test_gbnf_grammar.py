# -*- coding: utf-8 -*-
import pytest
from virtu_omni.serving.gbnf_grammar import (
    GCODE_GBNF,
    REGISTERED_CADCAM_TOOLS,
    build_toolcall_gbnf,
    schema_to_gbnf,
    validate_gcode_syntax,
)


def test_gcode_gbnf_structure():
    assert "root ::=" in GCODE_GBNF
    assert "[gG] digit+" in GCODE_GBNF
    assert "macro_assign" in GCODE_GBNF
    assert "signed_float" in GCODE_GBNF


def test_build_toolcall_gbnf():
    grammar = build_toolcall_gbnf()
    assert "root ::=" in grammar
    assert r'"\"tool\""' in grammar
    assert r'"\"arguments\""' in grammar
    # Verify key industrial tools are present
    assert '"\\"cadcam_preflight\\""' in grammar
    assert '"\\"cadcam_solidworks_model\\""' in grammar
    assert '"\\"cadcam_cimco_validate\\""' in grammar
    assert '"\\"cadcam_desktop_gui\\""' in grammar


def test_build_toolcall_gbnf_custom_tools():
    custom = ["cad_draw", "cam_simulate"]
    grammar = build_toolcall_gbnf(custom)
    assert '"\\"cad_draw\\""' in grammar
    assert '"\\"cam_simulate\\""' in grammar
    assert '"\\"cadcam_preflight\\""' not in grammar


def test_schema_to_gbnf_compilation():
    schema = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["focus", "click", "type"]},
            "count": {"type": "integer"},
            "enabled": {"type": "boolean"},
            "tags": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["action", "count"],
    }
    gbnf = schema_to_gbnf(schema)
    assert "root ::=" in gbnf
    assert '"\\"focus\\""' in gbnf
    assert '"\\"click\\""' in gbnf
    assert "number" in gbnf
    assert '("true" | "false")' in gbnf


def test_validate_gcode_syntax_valid_program():
    program = """
    %
    O1001 (FLANGE TURNING)
    G21 G40 G97 G99
    T0101
    M03 S1500
    G00 X55.0 Z2.0
    G01 Z-20.0 F0.2
    G01 X60.0
    G00 X100.0 Z50.0
    M05
    M30
    %
    """
    valid, errors = validate_gcode_syntax(program)
    assert valid is True
    assert len(errors) == 0


def test_validate_gcode_syntax_unbalanced_parentheses():
    program = "G00 X10.0 (Unclosed comment\nG01 Z-1.0 F0.1"
    valid, errors = validate_gcode_syntax(program)
    assert valid is False
    assert any("Unbalanced comment" in e for e in errors)


def test_validate_gcode_syntax_cutting_without_feedrate():
    program = "G01 X25.0 Z-10.0\n"
    valid, errors = validate_gcode_syntax(program)
    assert any("without active feedrate" in e for e in errors)


def test_validate_gcode_syntax_rapid_plunge_sentinel():
    program = "G00 Z-5.0 (Crash into raw stock)\n"
    valid, errors = validate_gcode_syntax(program)
    assert valid is False
    assert any("CRITICAL SAFETY VIOLATION" in e for e in errors)
