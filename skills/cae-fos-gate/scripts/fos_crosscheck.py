#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CAE 安全系数独立复核：用闭式解重算 von Mises 与 FOS，并与仓内引擎对账。

只读，不改动任何产物。退出码 0=两者一致(相对偏差<=2%) 1=偏差超限或 FOS 不达标。
"""
import argparse, json, math, sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

YIELD_MPA = {"Steel45": 355.0, "45": 355.0, "45hao": 355.0, "SS304": 205.0,
             "Cr12MoV": 850.0, "AL7075-T6": 503.0, "Ti-6Al-4V": 880.0}


def lame(di, d_outer, p):
    ri, ro = di / 2.0, d_outer / 2.0
    denom = ro ** 2 - ri ** 2
    # Independent closed-end Lamé reference: include the longitudinal principal
    # stress from the end-cap pressure resultant before calculating 3D von Mises.
    sz = p * ri ** 2 / denom
    st = p * (ro ** 2 + ri ** 2) / denom
    sr = -p
    vm = math.sqrt(((st - sr) ** 2 + (sr - sz) ** 2 + (sz - st) ** 2) / 2.0)
    return vm, st


def flange_ring_bend(di, d_outer, t, pcd, n_bolts, p):
    thrust = p * math.pi * (di / 2.0) ** 2
    arm = (pcd - di) / 2.0
    moment = thrust * 1.5 * arm / (math.pi * d_outer)
    return 6.0 * moment / (t ** 2)


def bracket(h, t_base, w, t_rib, F):
    m = F * h
    eff = max(t_rib * 2.0, w * 0.4)
    sec = eff * h ** 2 / 6.0
    sb = m / sec
    tau = F / (eff * h)
    return math.sqrt(sb ** 2 + 3.0 * tau ** 2)


def sheet_fiber(E_gpa, t, r):
    return min(1.2 * 355.0, (E_gpa * 1e3 * (t / 2.0)) / (r + t / 2.0))


def independent(raw_family, spec, loads, mat_key):
    fam = str(raw_family).strip().lower()
    family = {"rotational_shaft": "rotational_shaft", "flange_plate": "flange_plate",
              "bearing_bracket": "bearing_bracket", "sheet_metal_bend": "sheet_metal"}.get(fam, fam)
    fy = YIELD_MPA.get(str(mat_key), 355.0)
    if family in ("rotational_shaft", "shaft"):
        vm, _ = lame(float(spec.get("d_inner", 14.0)), float(spec.get("d_outer", 53.0)),
                     float(loads.get("internal_pressure_mpa", 45.0)))
    elif family in ("flange_plate", "flange"):
        vm = flange_ring_bend(float(spec.get("d_inner", 40.0)), float(spec.get("d_outer", 120.0)),
                              float(spec.get("thickness", 18.0)), float(spec.get("pcd", 90.0)),
                              int(spec.get("bolt_hole_count", 4)), float(loads.get("fluid_pressure_mpa", 16.0)))
    elif family in ("bearing_bracket", "bracket"):
        vm = bracket(float(spec.get("center_height", 50.0)), float(spec.get("base_thickness", 14.0)),
                     float(spec.get("base_width", 60.0)), float(spec.get("rib_thickness", 8.0)),
                     float(loads.get("radial_load_n", 12000.0)))
    else:
        vm = sheet_fiber(206.0, float(spec.get("sheet_thickness", 2.0)), float(spec.get("inner_bend_radius", 2.0)))
    fos = fy / max(1.0, vm)
    return {"yield_used_mpa": fy, "von_mises_mpa": round(vm, 3), "fos": round(fos, 3)}


def wall_for_fos(di, p_outer_target, fos_needed, fy):
    p = 1.0
    ro = (di / 2.0) * math.sqrt((fy / fos_needed + p) / (fy / fos_needed - p))
    return round(2.0 * ro, 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--family", required=True)
    ap.add_argument("--spec", default="{}")
    ap.add_argument("--loads", default="{}")
    ap.add_argument("--material", default="Steel45")
    ap.add_argument("--target-fos", type=float, default=1.5)
    ap.add_argument("--engine", action="store_true", help="同时调用仓内 universal_cae_engine 对账")
    ap.add_argument("--json-out", default=None)
    a = ap.parse_args()
    spec = json.loads(a.spec)
    loads = json.loads(a.loads)
    mine = independent(a.family, spec, loads, a.material)
    rep = {"family": a.family, "spec": spec, "loads": loads, "material_arg": a.material,
           "independent": mine, "target_fos": a.target_fos}
    if a.engine:
        sys.path.insert(0, r"D:\Virtu模型")
        from virtu_omni.engine.universal_cae_engine import UniversalCAEEngine
        eng = UniversalCAEEngine().analyze_and_optimize(
            {"family": a.family, "spec": dict(spec, material=a.material)}, loads)
        rep["engine"] = {k: eng.get(k) for k in ("status", "verdict_code", "material",
                                                "yield_strength_mpa", "von_mises_stress_mpa",
                                                "initial_stress_mpa", "factor_of_safety",
                                                "optimized_spec", "verdict")}
        e_vm = float(eng.get("von_mises_stress_mpa") or eng.get("initial_stress_mpa") or 0.0)
        rep["rel_diff_vs_engine"] = round(abs(e_vm - mine["von_mises_mpa"]) / max(1e-9, mine["von_mises_mpa"]), 5)
        rep["engine_yield_matches_claim"] = float(eng.get("yield_strength_mpa") or 0.0) == mine["yield_used_mpa"]
    ok = mine["fos"] >= a.target_fos
    if a.engine:
        ok = ok and rep["rel_diff_vs_engine"] <= 0.02 and rep["engine_yield_matches_claim"]
    rep["verdict"] = "FOS_OK" if ok else "FOS_FAIL_OR_MISMATCH"
    if a.family == "rotational_shaft" and mine["fos"] < a.target_fos:
        rep["min_safe_outside_dia_for_target"] = wall_for_fos(float(spec.get("d_inner", 14.0)), 1.0,
                                                             a.target_fos, mine["yield_used_mpa"])
    txt = json.dumps(rep, ensure_ascii=False, indent=1)
    if a.json_out:
        open(a.json_out, "w", encoding="utf-8").write(txt)
    sys.stdout.write(txt + chr(10))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
