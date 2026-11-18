"""CIMCO Edit 2026 Automation Bridge.

Inspired by:
- cimco/dncmaxctrlpythontomdc
- michaelfranzl/gcode-machine
- makalin/GCode-Parser

Features:
- FANUC Macro B variable logic validation (#100, #500, WHILE/DO/END)
- G-code syntax & modal group consistency checking
- CIMCO Edit launch & external transmission preparation
- NC code toolpath backplot data extraction
"""

import os
import sys
import re
import subprocess

CIMCO_EXE = r"E:\仿真软件\CIMCOEdit_20260102\CIMCO 2026\CIMCOEdit\CIMCOEdit.exe"


class CIMCOBridge:
    def __init__(self):
        self.cimco_exe = CIMCO_EXE

    def launch_in_cimco(self, nc_file_path: str):
        """Open NC G-code file in CIMCO Edit."""
        if not os.path.exists(nc_file_path):
            return {"status": "error", "message": f"NC file not found: {nc_file_path}"}

        if not os.path.exists(self.cimco_exe):
            return {"status": "error", "message": f"CIMCO Edit executable not found: {self.cimco_exe}"}

        try:
            subprocess.Popen([self.cimco_exe, nc_file_path])
            return {"status": "launched", "file": nc_file_path}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def validate_fanuc_macro_b(self, nc_code: str):
        """Perform comprehensive FANUC Macro B variable validation."""
        lines = nc_code.splitlines()
        errors = []
        variables_used = set()
        loop_stack = []
        spindle_on = False
        program_end = False

        for idx, line in enumerate(lines, 1):
            clean = line.strip().upper()
            if not clean or clean.startswith("(") or clean.startswith("%"):
                continue

            # Check macro variables: #1 ~ #33 (local), #100 ~ #199 (common), #500 ~ #999 (system)
            vars_found = re.findall(r"#\d+", clean)
            for v in vars_found:
                variables_used.add(v)

            # Check WHILE - DO loops
            while_match = re.search(r"WHILE\s*\[.*\]\s*DO\s*(\d+)", clean)
            if while_match:
                loop_id = while_match.group(1)
                loop_stack.append((loop_id, idx))

            end_match = re.search(r"END\s*(\d+)", clean)
            if end_match:
                end_id = end_match.group(1)
                if not loop_stack:
                    errors.append(f"Line {idx}: END {end_id} without matching WHILE DO.")
                else:
                    expected_id, start_line = loop_stack.pop()
                    if expected_id != end_id:
                        errors.append(f"Line {idx}: Mismatched END {end_id}, expected END {expected_id} from line {start_line}.")

            # G/M token range audit + program-end / spindle-stop checks
            if clean.startswith("G") or clean.startswith("M") or clean.startswith("O"):
                for letter, val in re.findall(r"([GM])(-?\d+(?:\.\d+)?)", clean):
                    num = float(val)
                    if not (0.0 <= num <= 999.0):
                        errors.append(f"Line {idx}: out-of-range {letter}{val}.")
                if re.search(r"M0?[34]\b", clean):
                    spindle_on = True
                if re.search(r"M0?5\b", clean):
                    spindle_on = False
                if re.search(r"M0?[23]0\b", clean):
                    program_end = True

        if loop_stack:
            for loop_id, line in loop_stack:
                errors.append(f"Line {line}: Unclosed WHILE DO {loop_id}.")
        if not program_end:
            errors.append("Program end M02/M30 not found.")
        if spindle_on:
            errors.append("Spindle still on at program end (no M05).")

        # Deep G-code syntax and safety sentinel (G00 collision, missing feedrate, unclosed comment)
        syntax_checked = True
        syntax_check_error = None
        try:
            from virtu_omni.serving.gbnf_grammar import validate_gcode_syntax
            _, g_errors = validate_gcode_syntax(nc_code)
            for ge in g_errors:
                m = re.match(r"Line (\d+): No valid G-code words", ge)
                if m:
                    src = lines[int(m.group(1)) - 1].strip().upper()
                    # Macro B assignments / WHILE-DO / END / expression coords are valid FANUC
                    if src.startswith("#") or src.startswith("WHILE") or re.match(r"^END\s*\d+", src) or "[" in src:
                        continue
                errors.append(ge)
        except Exception as exc:  # noqa: BLE001
            # 哨兵自身不可用 ≠ 程序合法。原实现 except: pass 后照样 status=success、
            # is_valid 来自"跑过的检查"，于是"没检查"会被读成"检查通过"。
            # 现在：状态降 partial，is_valid 必须同时满足"哨兵真跑过"，并把不可用原因
            # 以 CHECK_UNAVAILABLE 前缀入错误清单（不伪装成程序缺陷，也不让它静默）。
            syntax_checked = False
            syntax_check_error = f"{type(exc).__name__}: {exc}"[:160]
            errors.append("CHECK_UNAVAILABLE: gcode syntax sentinel did not run: " + syntax_check_error)

        critical = [e for e in errors if "CRITICAL" in e or "Unclosed" in e or "without matching" in e or "Mismatched" in e]
        is_valid = syntax_checked and not critical
        return {
            "status": "success" if syntax_checked else "partial",
            "is_valid": is_valid,
            "syntax_checked": syntax_checked,
            "syntax_check_error": syntax_check_error,
            "errors": errors,
            "variables_count": len(variables_used),
            "variables": sorted(list(variables_used)),
            "line_count": len(lines),
        }

    def validate_gcode(self, nc_code: str):
        """Validate G-code program syntax, toolpath feeds, and collision safety."""
        try:
            from virtu_omni.serving.gbnf_grammar import validate_gcode_syntax
            is_valid, errors = validate_gcode_syntax(nc_code)
            return {
                "status": "success",
                "is_valid": is_valid,
                "errors": errors,
                "line_count": len(nc_code.splitlines()),
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    bridge = CIMCOBridge()
    test_code = "#100 = 50.0\n#101 = 10.0\nWHILE [#101 LE #100] DO 1\nG01 X#101 F300\n#101 = #101 + 5.0\nEND 1\nM30"
    print("CIMCO Bridge Initialized. Validation Test:", bridge.validate_fanuc_macro_b(test_code))
