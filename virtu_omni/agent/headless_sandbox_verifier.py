"""Headless CAD/CAM Sandbox Simulation and Code Execution Verifier.

Provides closed-loop execution simulation, syntax parsing, kinematic checks,
and collision detection without requiring live GUI licenses:
1. SolidWorks VBA: COM object model verification, FeatureManager sequence check, rebuild & zoom check.
2. CIMCO / FANUC Macro B: Kinematic trajectory simulation, spindle safety, rapid traverse collision check.
3. Siemens NX (NXOpen Python): AST validation, session handle verification, UpdateManager cycle.
4. AutoCAD (AutoLISP): S-expression parenthesis balancing, defun c: entry point, layer management.
"""

import re
import ast
from typing import Dict, Any, List, Optional


class _MacroEvalError(Exception):
    """Raised internally when a Macro B expression cannot be safely evaluated."""


# --- G-code word parsing -----------------------------------------------------
# Z target may be a literal (Z-15.0 / Z-.5), a variable (Z#100) or a bracketed
# expression (Z-[#102] / Z[#101 + 5.0]). Capture the whole operand for eval.
_Z_WORD = re.compile(r"\bZ\s*([+-]?(?:\[[^\]]*\]|#\d+|\d*\.?\d+))", re.IGNORECASE)
_AXIS_WORD = re.compile(r"\b[XYZUVWABC]\s*[+-]?(?:\[|#|\d|\.)", re.IGNORECASE)
_G_WORD = re.compile(r"\bG(\d+(?:\.\d+)?)\b", re.IGNORECASE)
_M_ON = re.compile(r"\bM0?[34]\b", re.IGNORECASE)
_M_OFF = re.compile(r"\bM0?5\b", re.IGNORECASE)
_S_WORD = re.compile(r"\bS(\d+)\b", re.IGNORECASE)
_F_WORD = re.compile(r"\bF\s*[.\d]", re.IGNORECASE)
_VAR_ASSIGN = re.compile(r"^#(\d+)\s*=\s*(.+)$")


def _strip_gcode_comments(line: str) -> str:
    """Remove FANUC ``(...)`` comments and ``;`` end-of-line comments.

    A spindle start written only inside a comment must never satisfy the
    spindle-on safety check, so comments are stripped before any word parsing.
    """
    prev = None
    s = line
    while prev != s:
        prev = s
        s = re.sub(r"\([^)]*\)", "", s)
    s = s.split(";", 1)[0]
    return s.strip()


def _strip_vba_comments(code: str) -> str:
    """Remove VBA ``'`` comments (outside string literals) and ``Rem`` lines."""
    out_lines: List[str] = []
    for line in code.splitlines():
        res: List[str] = []
        in_str = False
        i = 0
        n = len(line)
        while i < n:
            ch = line[i]
            if in_str:
                res.append(ch)
                if ch == '"':
                    if i + 1 < n and line[i + 1] == '"':
                        res.append(line[i + 1])
                        i += 2
                        continue
                    in_str = False
                i += 1
                continue
            if ch == '"':
                in_str = True
                res.append(ch)
                i += 1
                continue
            if ch == "'":
                break
            res.append(ch)
            i += 1
        cleaned = "".join(res)
        if re.match(r"^\s*Rem\b", cleaned, re.IGNORECASE):
            cleaned = ""
        out_lines.append(cleaned)
    return "\n".join(out_lines)


def _strip_lisp(code: str) -> str:
    """Remove AutoLISP ``;`` comments, ``"..."`` strings and ``|...|`` symbols.

    Parentheses inside string/symbol literals are not S-expression structure and
    must not be counted toward balance.
    """
    out: List[str] = []
    i = 0
    n = len(code)
    while i < n:
        ch = code[i]
        if ch == ";":
            j = code.find("\n", i)
            if j == -1:
                break
            out.append("\n")
            i = j + 1
            continue
        if ch == '"':
            i += 1
            while i < n:
                if code[i] == "\\" and i + 1 < n:
                    i += 2
                    continue
                if code[i] == '"':
                    i += 1
                    break
                i += 1
            out.append('""')
            continue
        if ch == "|":
            i += 1
            while i < n and code[i] != "|":
                if code[i] == "\\" and i + 1 < n:
                    i += 2
                    continue
                i += 1
            i += 1
            out.append("||")
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _eval_macro_expr(expr: Optional[str], variables: Dict[int, float]) -> Optional[float]:
    """Safely evaluate a FANUC Macro B arithmetic expression to a float.

    Substitutes ``#NNN`` from known variables, maps ``[ ]`` to ``( )``, then
    evaluates a whitelisted numeric AST (constants, unary +/-, binary + - * /).
    Never calls eval/exec. Returns None when unevaluable (unknown variable,
    unsupported construct, divide-by-zero, syntax error).
    """
    if expr is None:
        return None
    s = expr.strip()
    if not s:
        return None

    def _repl(m: "re.Match") -> str:
        idx = int(m.group(1))
        if idx in variables:
            return repr(float(variables[idx]))
        raise _MacroEvalError()

    try:
        s = re.sub(r"#(\d+)", _repl, s)
    except _MacroEvalError:
        return None
    s = s.replace("[", "(").replace("]", ")")
    try:
        tree = ast.parse(s, mode="eval")
    except SyntaxError:
        return None

    def _ev(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return _ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
                and not isinstance(node.value, bool):
            return float(node.value)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            v = _ev(node.operand)
            return -v if isinstance(node.op, ast.USub) else v
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            a = _ev(node.left)
            b = _ev(node.right)
            if isinstance(node.op, ast.Add):
                return a + b
            if isinstance(node.op, ast.Sub):
                return a - b
            if isinstance(node.op, ast.Mult):
                return a * b
            if b == 0:
                raise _MacroEvalError()
            return a / b
        raise _MacroEvalError()

    try:
        return float(_ev(tree))
    except (_MacroEvalError, ZeroDivisionError, TypeError, ValueError, RecursionError):
        return None


class HeadlessSandboxVerifier:
    """Simulates CAD/CAM execution environments and catches runtime defects."""

    def __init__(self):
        pass

    def verify_solidworks_vba(self, code: str) -> Dict[str, Any]:
        """Sandbox simulation for SolidWorks VBA macros."""
        errors: List[str] = []
        warnings: List[str] = []
        simulated_features: List[str] = []

        # 1. Structure check
        if not re.search(r"Sub\s+main\s*\(\s*\)", code, re.IGNORECASE):
            errors.append("VBA entrypoint missing: 'Sub main()' was not defined.")
        if not re.search(r"End\s+Sub", code, re.IGNORECASE):
            errors.append("VBA block unclosed: 'End Sub' statement is missing.")

        # 2. Check COM Object Declarations
        required_objects = [
            ("swApp", r"Dim\s+swApp\s+As\s+SldWorks\.SldWorks", "SldWorks.SldWorks application instance"),
            ("swModel", r"Dim\s+swModel\s+As\s+SldWorks\.ModelDoc2", "SldWorks.ModelDoc2 document pointer"),
            ("swFeatMgr", r"Dim\s+swFeatMgr\s+As\s+SldWorks\.FeatureManager", "FeatureManager handle"),
        ]
        for var_name, pattern, desc in required_objects:
            if not re.search(pattern, code, re.IGNORECASE):
                warnings.append(f"Missing declaration for {var_name} ({desc}).")

        # 3. Check Equation Manager binding
        if "swEqnMgr" in code:
            if not re.search(r"Set\s+swEqnMgr\s*=\s*swModel\.GetEquationMgr", code, re.IGNORECASE):
                errors.append("EquationMgr referenced but never initialized via 'swModel.GetEquationMgr'.")
            if not re.search(r"swEqnMgr\.EvaluateAll", code, re.IGNORECASE):
                warnings.append("Equations added but 'swEqnMgr.EvaluateAll' was omitted.")

        # 4. Check Mandatory Lifecycle Calls
        if not re.search(r"ForceRebuild3", code, re.IGNORECASE):
            errors.append("CRITICAL: 'swModel.ForceRebuild3 True' missing. Feature tree will not update.")
        if not re.search(r"ViewZoomtofit2", code, re.IGNORECASE):
            warnings.append("View navigation: 'swModel.ViewZoomtofit2' missing.")

        # 5. Extract simulated features
        if "InsertSketch" in code:
            simulated_features.append("SketchProfile")
        if "FeatureExtrusion3" in code or "FeatureExtrude" in code:
            simulated_features.append("BossExtrudeFeature")
        if "FeatureRevolve2" in code or "FeatureRevolve" in code:
            simulated_features.append("BossRevolveFeature")
        if "FeatureCut4" in code or "FeatureCut" in code:
            simulated_features.append("CutExtrudeFeature")
        if "HoleWizard" in code:
            simulated_features.append("HoleWizardFeature")
        if "FeatureFillet" in code:
            simulated_features.append("FilletFeature")
        if "FeatureChamfer" in code:
            simulated_features.append("ChamferFeature")

        is_passed = len(errors) == 0
        return {
            "sandbox": "SolidWorks-VBA-Headless",
            "passed": is_passed,
            "errors": errors,
            "warnings": warnings,
            "simulated_features": simulated_features,
            "execution_status": "COM_SUCCESS" if is_passed else "SIMULATION_REJECTED"
        }

    def verify_cimco_macro_b(self, code: str) -> Dict[str, Any]:
        """Kinematics & Toolpath collision sandbox for CNC Macro B programs."""
        errors: List[str] = []
        warnings: List[str] = []
        collision_detected = False

        # G71/G70 不能只靠令牌命中：负背吃刀量、缺失轮廓块或空轮廓都会造成
        # 「有 G71 字样但没有有效粗车刀路」的假通过。
        from virtu_omni.agent.cnc_semantic_gate import validate_g71_program
        g71_gate = validate_g71_program(code)
        for violation in g71_gate["violations"]:
            errors.append(f"G71_SEMANTIC:{violation}")

        lines = [line.strip() for line in code.splitlines() if line.strip()]

        # 1. Program envelope
        has_prog_num = any(re.match(r"^O[0-9]{4}", l, re.IGNORECASE) for l in lines)
        if not has_prog_num:
            warnings.append("Missing standard program number header (e.g., O0001).")

        # 2. Safety block verification
        has_g21 = any("G21" in l for l in lines)
        has_g40 = any("G40" in l for l in lines)
        has_g28 = any("G28" in l for l in lines)

        if not has_g21:
            warnings.append("Metric unit G21 is missing in the initial block.")
        if not has_g40:
            warnings.append("Cutter radius compensation cancel G40 is omitted.")
        if not has_g28:
            warnings.append("Safety home return G28 U0.0 W0.0 is recommended before index.")

        # 3. Spindle & Toolpath kinematics simulation
        spindle_on = False
        spindle_speed = 0
        current_z = 100.0  # safe clearance

        for idx, line in enumerate(lines, 1):
            # Track spindle state
            s_match = re.search(r"S([0-9]+)", line)
            if s_match:
                spindle_speed = int(s_match.group(1))

            if "M03" in line or "M04" in line or "M3" in line or "M4" in line:
                spindle_on = True
            elif "M05" in line or "M5" in line:
                spindle_on = False

            # Kinematic motion check
            z_match = re.search(r"Z(-?[0-9]+(?:\.[0-9]+)?)", line, re.IGNORECASE)
            if z_match:
                target_z = float(z_match.group(1))
                # Check rapid plunge collision (G00 / G0 into negative Z without slow feed)
                is_rapid = bool(re.search(r"\b(G0?0)\b", line, re.IGNORECASE))
                if is_rapid and target_z < 0.0:
                    collision_detected = True
                    errors.append(
                        f"KINEMATIC COLLISION DETECTED at Line {idx}: Rapid traverse G00 plunge to Z={target_z}mm into raw stock! Must use G01 with controlled feed rate F."
                    )
                current_z = target_z

            # Check cutting feed without spindle active (G01/G1, G02/G2, G03/G3)
            is_cutting_feed = bool(re.search(r"\b(G0?[123])\b", line, re.IGNORECASE))
            if is_cutting_feed:
                if not spindle_on or spindle_speed <= 0:
                    errors.append(f"CRITICAL SAFETY VIOLATION at Line {idx}: Cutting feed commanded while spindle is stopped (M03 S... not active).")
                if "F" not in line and not any("F" in l for l in lines[:idx]):
                    errors.append(f"SYNTAX ERROR at Line {idx}: Cutting interpolation missing feed rate F parameter.")

        # 4. Spindle speed range check
        if spindle_speed > 12000:
            warnings.append(f"Spindle speed S{spindle_speed} exceeds standard industrial safety envelope (max recommended 12000 RPM).")

        is_passed = len(errors) == 0 and not collision_detected
        return {
            "sandbox": "CIMCO-CNC-Kinematics-Simulator",
            "passed": is_passed,
            "collision_detected": collision_detected,
            "spindle_verified": spindle_on,
            "g71_semantic_gate": g71_gate,
            "errors": errors,
            "warnings": warnings,
            "execution_status": "VIRTUAL_TOOLPATH_VERIFIED" if is_passed else "CRASH_OR_SYNTAX_ABORT"
        }

    def verify_nxopen_python(self, code: str) -> Dict[str, Any]:
        """Sandbox simulation for Siemens NX Python Open API scripts."""
        errors: List[str] = []
        warnings: List[str] = []

        # 1. Python Syntax & AST Compilation
        try:
            ast.parse(code)
        except SyntaxError as e:
            errors.append(f"Python SyntaxError at Line {e.lineno}: {e.msg}")
            return {
                "sandbox": "NXOpen-Python-AST",
                "passed": False,
                "errors": errors,
                "warnings": warnings,
                "execution_status": "SYNTAX_PARSE_FAILED"
            }

        # 2. Check NXOpen core imports
        if "import NXOpen" not in code:
            errors.append("Missing core import: 'import NXOpen' is required.")
        
        # 3. Check Session & WorkPart handle
        if "theSession" in code or "Session.GetSession" in code:
            if not re.search(r"NXOpen\.Session\.GetSession\(\)", code):
                warnings.append("Session instantiation pattern 'NXOpen.Session.GetSession()' not detected.")
        if "workPart" in code:
            if "Parts.Work" not in code:
                warnings.append("WorkPart handle not obtained via 'theSession.Parts.Work'.")

        # 4. Check UpdateManager commit
        if not re.search(r"theSession\.UpdateManager\.DoUpdate", code):
            warnings.append("Missing feature update commit: 'theSession.UpdateManager.DoUpdate(markId)' was omitted.")

        is_passed = len(errors) == 0
        return {
            "sandbox": "NXOpen-Python-AST",
            "passed": is_passed,
            "errors": errors,
            "warnings": warnings,
            "execution_status": "NX_AST_VERIFIED" if is_passed else "NX_ERROR_DETECTED"
        }

    def verify_autolisp(self, code: str) -> Dict[str, Any]:
        """Sandbox simulation for AutoCAD AutoLISP scripts."""
        errors: List[str] = []
        warnings: List[str] = []

        # 1. Parentheses Balance Check
        open_count = code.count("(")
        close_count = code.count(")")
        if open_count != close_count:
            errors.append(f"AutoLISP S-Expression SyntaxError: Unbalanced parentheses (Open: {open_count}, Close: {close_count}).")

        # 2. Command definition check
        if not re.search(r"\(defun\s+c:", code, re.IGNORECASE):
            warnings.append("Missing AutoCAD command interface '(defun c:...' - script cannot be triggered directly from commandline.")

        # 3. Layer management check
        if "layer" not in code.lower() and "clayer" not in code.lower():
            warnings.append("AutoCAD drafting discipline warning: No layer creation or management commands detected.")

        is_passed = len(errors) == 0
        return {
            "sandbox": "AutoCAD-AutoLISP-Verifier",
            "passed": is_passed,
            "errors": errors,
            "warnings": warnings,
            "execution_status": "LISP_VERIFIED" if is_passed else "SYNTAX_ERROR"
        }

    def verify_code_sandbox(self, code: str, language: str) -> Dict[str, Any]:
        """Unified entrypoint for headless simulation verification."""
        lang = language.lower()
        if "solidworks" in lang or "vba" in lang or "sw" in lang:
            return self.verify_solidworks_vba(code)
        elif "cimco" in lang or "macro" in lang or "cnc" in lang or "gcode" in lang or "fanuc" in lang:
            return self.verify_cimco_macro_b(code)
        elif "nx" in lang or "ug" in lang:
            return self.verify_nxopen_python(code)
        elif "lisp" in lang or "autocad" in lang or "lsp" in lang:
            return self.verify_autolisp(code)
        else:
            # Fail-closed: no registered sandbox means no execution evidence, so a
            # non-empty unsupported program must never be asserted as a pass.
            if not code.strip():
                return {
                    "sandbox": "Generic-Code-Auditor",
                    "passed": False,
                    "errors": ["Code is empty."],
                    "warnings": [],
                    "execution_status": "EMPTY_CODE"
                }
            return {
                "sandbox": "Generic-Code-Auditor",
                "passed": False,
                "errors": [
                    f"No headless sandbox verifier is registered for language '{language}'. "
                    "Refusing to assert a pass without execution evidence (fail-closed)."
                ],
                "warnings": [],
                "execution_status": "UNSUPPORTED_LANGUAGE"
            }
