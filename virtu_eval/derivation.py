"""Law registry: which physical law produces each field, and from which given symbols.

This exists to separate two skills that the plain numeric ruler conflates. Measured on
``_eval_phys_v3_*``: ``virtu-ties-v1`` passes the conservation/unit gate 29/30 but reproduces the
solver's numbers only 7/30 -- it obeys the format and misses the arithmetic. So the model declares
the law and the symbol bindings, the verifier does the multiplication, and the two scores are
reported apart.

Anti-drift contract: ``resolve(task, inputs)`` must reproduce ``wm_verifier.recompute`` field for
field, which ``tests/test_derivation_registry.py`` enforces for every family and every shipped
case. If the registry and the solver ever disagree, the registry loses -- nothing else here is
allowed to define physics.

Numbers are evaluated with ``virtu_eval.audit_case_arithmetic.eval_expr`` (the same parser that
already audits gold derivation chains); there is deliberately no second expression engine.
"""
from __future__ import annotations

import math
import re

from virtu_eval.audit_case_arithmetic import eval_expr

# field -> symbolic law, written with the scenario's own input key names.
# ``sum(L)`` / ``rss(L)`` expand over a list input at resolve time.
LAWS = {
    "removal": [
        ("material_removed_mm3", "doc*woc*L"),
        ("mrr_mm3_per_min", "doc*woc*vf"),
        ("removed_mass_g", "material_removed_mm3*rho"),
        ("resulting_mass_g", "stock_vol*rho-removed_mass_g"),
        ("delta_volume_mm3", "-material_removed_mm3"),
    ],
    "roughness": [("surface_roughness_ra_um", "1000*f^2/(8*r_eps)")],
    "fea_fos": [
        # 照抄量也是绑定：recompute 产出 yield_strength_mpa 参考值，注册表缺位
        # 时该字段无人判（test_registry_covers_every_numeric_reference_field）。
        ("yield_strength_mpa", "Sy"),
        ("peak_von_mises_mpa", "sigma"),
        ("safety_factor", "Sy/sigma"),
    ],
    "lame_cylinder_stress": [
        ("lame_axial_stress_mpa",
         "(pressure_inner_mpa*r_inner_mm^2-pressure_outer_mpa*r_outer_mm^2)/"
         "(r_outer_mm^2-r_inner_mm^2)"),
        ("lame_hoop_inner_mpa",
         "lame_axial_stress_mpa+(pressure_inner_mpa-pressure_outer_mpa)*"
         "r_outer_mm^2/(r_outer_mm^2-r_inner_mm^2)"),
        ("lame_radial_inner_mpa", "-pressure_inner_mpa"),
        ("lame_hoop_outer_mpa",
         "lame_axial_stress_mpa+(pressure_inner_mpa-pressure_outer_mpa)*"
         "r_inner_mm^2/(r_outer_mm^2-r_inner_mm^2)"),
        ("lame_radial_outer_mpa", "-pressure_outer_mpa"),
        ("von_mises_inner_mpa",
         "sqrt(((lame_hoop_inner_mpa-lame_radial_inner_mpa)^2+"
         "(lame_radial_inner_mpa-lame_axial_stress_mpa)^2+"
         "(lame_axial_stress_mpa-lame_hoop_inner_mpa)^2)/2)"),
        ("von_mises_outer_mpa",
         "sqrt(((lame_hoop_outer_mpa-lame_radial_outer_mpa)^2+"
         "(lame_radial_outer_mpa-lame_axial_stress_mpa)^2+"
         "(lame_axial_stress_mpa-lame_hoop_outer_mpa)^2)/2)"),
        # Closed-end thick cylinder: combine the three principal stresses at both
        # boundaries; the larger equivalent stress controls the safety factor.
        ("peak_von_mises_mpa",
         "max(von_mises_inner_mpa,von_mises_outer_mpa)"),
    ],
    "shaft_torsion": [
        ("torsional_shear_mpa",
         "abs(torque_nm*1000*r_outer_mm/"
         "(pi/2*(r_outer_mm^4-r_inner_mm^4)))"),
    ],
    "combined_vm_torsion": [
        ("combined_von_mises_mpa",
         "sqrt(base_von_mises_mpa^2+3*torsional_shear_mpa^2)"),
    ],
    "collision": [
        ("safe_plane_z_mm", "z_safe"),
        ("rapid_min_z_mm", "z_min_rapid"),
        ("stock_top_z_mm", "stock_top"),
    ],
    "tolerance": [
        ("closed_loop_worstcase_halfwidth_mm", "sum(tols)"),
        ("closed_loop_rss_halfwidth_mm", "rss(tols)"),
        ("fit_clearance_mm", "upper_dev-lower_dev"),
    ],
    "geom_delta": [
        ("feature_volume_mm3", "feature_vol"),
        ("delta_volume_mm3", "-feature_vol"),
        ("before_volume_mm3", "before"),
        ("after_volume_mm3", "before-feature_vol"),
    ],
    "design": [
        ("volume_mm3", "pi*(r_out^2-r_bore^2)*t-n_holes*pi*r_hole^2*t"),
        ("mass_g", "volume_mm3*rho"),
        ("mass_kg", "mass_g/1000"),
    ],
    "process": [
        ("spindle_rpm", "1000*vc/(pi*D)"),
        ("feed_rate_mm_per_min", "f*spindle_rpm"),
        ("mrr_mm3_per_min", "ap*f*vc*1000"),
        ("surface_roughness_ra_um", "1000*f^2/(8*r_eps)"),
        ("cut_time_min", "L/feed_rate_mm_per_min"),
    ],
    "adapt_material": [
        ("yield_strength_mpa", "Sy"),
        ("peak_von_mises_mpa", "sigma"),
        ("safety_factor", "Sy/sigma"),
    ],
    "adapt_machine": [
        ("required_spindle_rpm", "1000*vc/(pi*D)"),
        ("machine_max_rpm", "n_max"),
        ("recommended_vc_m_per_min", "vc"),
    ],
}

# Verdict fields are predicates, not arithmetic: they stay with world_state_verified's exact match.
PREDICATE_FIELDS = {"collision_risk", "gouge", "autodiff", "within_limit", "volume_conservation",
                    "fos_gate", "tolerance_pass"}

_LIT_RE = re.compile(r"\d+(?:\.\d+)?")


def _fmt(value: float) -> str:
    """Exponent-free decimal text, because eval_expr's number regex has no ``1e-3`` form."""
    text = f"{float(value):.12f}".rstrip("0")
    return text[:-1] if text.endswith(".") else (text or "0")


def _expand(template: str, inputs: dict) -> str:
    """Replace sum(L) / rss(L) over a list input with explicit arithmetic."""
    for name, value in inputs.items():
        if not isinstance(value, (list, tuple)):
            continue
        if f"sum({name})" in template:
            body = "+".join(f"({_fmt(float(v))})" for v in value)
            template = template.replace(f"sum({name})", body)
        if f"rss({name})" in template:
            body = "sqrt(" + "+".join(f"({_fmt(float(v))})^2" for v in value) + ")"
            template = template.replace(f"rss({name})", body)
    return template


def _substitute(template: str, scope: dict) -> str:
    """Bind every symbol to its numeric text, longest name first so ``r_out`` beats ``r``."""
    for name in sorted(scope, key=len, reverse=True):
        if name in template:
            template = template.replace(name, f"({_fmt(scope[name])})")
    return template


def numeric_laws(task: str):
    return [(f, law) for f, law in LAWS.get(task, []) if f not in PREDICATE_FIELDS]


def resolve(task: str, inputs: dict) -> dict:
    """field -> numeric expression text with the given values already substituted.

    Earlier fields are usable symbols for later ones, which is how chained quantities
    (mass from volume, feed rate from spindle speed) stay expressible in one law per field.
    """
    if task not in LAWS:
        return {}
    scope = {k: v for k, v in inputs.items() if not isinstance(v, (list, tuple, dict))}
    out = {}
    for field, template in LAWS[task]:
        expr = _substitute(_expand(template, inputs), scope)
        parsed = eval_expr(expr)
        if parsed is None:
            raise ValueError(f"{task}.{field}: registry template does not evaluate: {expr!r}")
        out[field] = expr
        scope[field] = parsed[0]
    return out


def allowed_literals(expression: str) -> list:
    """Every decimal appearing in an expression, used as the set a lawful answer may draw numbers from."""
    return sorted(float(m.group(0)) for m in _LIT_RE.finditer(expression))


def check(task: str, field: str, expression: str, inputs: dict, tol: float = 0.01,
          own_values=()) -> dict:
    """Grade one declared derivation: right law+bindings, recomputed here, apart from its arithmetic.

    ``own_values`` carries the numbers the model produced for its *other* fields: the contract allows
    a chained step to reuse an intermediate it computed itself. A wrong intermediate still fails,
    because it changes what this expression evaluates to.
    """
    try:
        gold_map = resolve(task, inputs) if task in LAWS else {}
    except ValueError as exc:  # incomplete or non-numeric inputs: refuse, do not pretend to grade
        return {"ok": False, "reason": f"registry_cannot_resolve: {exc}"}
    if field not in gold_map:
        return {"ok": False, "reason": f"no registered law for {task}.{field}"}
    gold_expr = gold_map[field]
    # A number is legitimate if the problem gave it, any registered law of this task uses it, or the
    # model derived it in this same answer. Expanding a chained quantity back into its inputs
    # ("(2)*(5)*(100)*(0.00785)" instead of "(1000)*(0.00785)") is an equivalent rewrite, and
    # punishing it measures notation, not physics.
    allowed = set(allowed_literals(" ".join(gold_map.values())))
    for value in inputs.values():
        for scalar in (value if isinstance(value, (list, tuple)) else [value]):
            if isinstance(scalar, (int, float)) and not isinstance(scalar, bool):
                allowed.add(float(scalar))
    allowed.update(float(v) for v in own_values if isinstance(v, (int, float)))
    allowed.add(math.pi)
    allowed = {abs(v) for v in allowed}
    fabricated = []
    for lit in allowed_literals(expression):
        # literals are extracted without their sign, so magnitudes are what can be compared;
        # a wrong sign still fails the value check below
        if any(abs(abs(lit) - a) <= max(1e-9, 1e-4 * max(a, 1.0)) for a in allowed):
            continue
        if abs(lit - math.pi) <= 1e-3 * math.pi:
            continue
        fabricated.append(lit)
    parsed = eval_expr(expression)
    if parsed is None:
        return {"ok": False, "reason": "expression_unparsable", "expression": expression}
    value = parsed[0]
    gold_value = eval_expr(gold_expr)[0]
    rel = abs(value - gold_value) / max(abs(gold_value), 1e-9)
    return {
        "ok": not fabricated and rel <= tol,
        "fabricated_literals": fabricated,
        "evaluated": value,
        "reference": gold_value,
        "rel_err_vs_law": round(rel, 6),
        "expression": expression,
        "gold_expression": gold_expr,
    }
