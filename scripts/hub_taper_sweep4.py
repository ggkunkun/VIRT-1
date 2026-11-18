# -*- coding: utf-8 -*-
"""tapered 轮毂第四轮：外段幂律轮廓，追求最省料。

形状族：
  内段 [a, r_knee]：等厚 h_bore
  外段 [r_knee, b]：h(r) = h_rim + (h_knee - h_rim) * ((b-r)/(b-r_knee))**p
    p=1 为线性；p>1 外段更快变薄（质量更靠内）；p<1 更慢变薄

判定口径（写死，不重复计入叶片载荷）：
  已把叶片离心力作为外缘 sigma_r 施加，故不再乘 K_BLADE。
  硬约束 FOS_bore >= 1.5 且 FOS_vm >= 1.5。
"""
import json
import math
import sys

import numpy as np

sys.path.insert(0, r"D:\Virtu模型\scripts")
from hub_stress_tapered import (  # noqa: E402
    RHO, SY, NU, KB, E_MOD, D2, D1T, D1H, Z_BLADES, TB, AXIAL_L,
    blade_rim_stress_pa, solve_var, ruler_bore_sigma, fos, PROJ,
)

N_RPM = 40300.5
BORE = 26.4
H_RIM = 4.0


def power_profile(h_bore, h_knee, p, r_knee_mm, bore):
    a = bore / 2.0 / 1000.0
    b = D2 / 2.0 / 1000.0
    rk = r_knee_mm / 1000.0
    span = b - rk

    def hf(r):
        if r <= rk:
            return h_bore
        t = (b - r) / span
        return H_RIM + (h_knee - H_RIM) * (t ** p)

    def dhf(r):
        if r <= rk:
            return 0.0
        t = (b - r) / span
        # d/dr of (t**p) = p * t**(p-1) * (-1/span)
        return (h_knee - H_RIM) * p * (t ** (p - 1.0)) * (-1.0 / span) / 1e3

    return hf, dhf


def vol_mm3(hf, bore):
    a, b = bore / 2.0, D2 / 2.0
    r = np.linspace(a, b, 4001)
    h = np.array([hf(x / 1000.0) for x in r])
    return float(np.trapezoid(2 * math.pi * r * h, r))


def evaluate(hf, dhf):
    sr_rim, _, _ = blade_rim_stress_pa(H_RIM)
    s0 = solve_var(D2, BORE, N_RPM, hf, dhf, rim_sigma=0.0)
    s1 = solve_var(D2, BORE, N_RPM, hf, dhf, rim_sigma=sr_rim)
    sig = max(s0["sigma_theta_bore_MPa"], s1["sigma_theta_bore_MPa"])
    vmm = max(s0["max_vm_MPa"], s1["max_vm_MPa"])
    v = vol_mm3(hf, BORE)
    return {"sigma_bore": round(sig, 1), "FOS_bore": round(fos(sig), 3),
            "max_vm": round(vmm, 1), "FOS_vm": round(fos(vmm), 3),
            "mass_kg": round(v * RHO * 1e-9, 3)}


def main():
    rows = []
    for h_bore in [16.0, 17.0, 18.0, 19.0, 20.0, 21.0, 22.0]:
        for h_knee in [10.0, 14.0, 18.0, 22.0]:
            if h_knee > h_bore:
                continue
            for p in [0.6, 0.8, 1.0, 1.3, 1.6, 2.0, 2.5]:
                for r_knee in [D1H / 2, 45.0, 55.0, 65.0]:
                    hf, dhf = power_profile(h_bore, h_knee, p, r_knee, BORE)
                    r = evaluate(hf, dhf)
                    rows.append({"h_bore": h_bore, "h_knee": h_knee, "p": p,
                                 "r_knee_mm": r_knee, **r})

    ok = [x for x in rows if x["FOS_bore"] >= 1.5 and x["FOS_vm"] >= 1.5]
    ok.sort(key=lambda x: x["mass_kg"])
    p = PROJ / "hub_taper_sweep4.json"
    p.write_text(json.dumps({"n_rows": len(rows), "n_feasible": len(ok),
                             "feasible_top": ok[:20], "all_rows": rows},
                            ensure_ascii=False, indent=2), encoding="utf-8")

    print("总 / 可行:", len(rows), "/", len(ok))
    print(f"{'h_bore':>7}{'h_knee':>7}{'p':>5}{'r_knee':>7}{'sig':>8}{'FOS':>7}{'maxVM':>8}{'mass_kg':>9}")
    for x in ok[:20]:
        print(f"{x['h_bore']:>7.1f}{x['h_knee']:>7.1f}{x['p']:>5.1f}{x['r_knee_mm']:>7.1f}"
              f"{x['sigma_bore']:>8.1f}{x['FOS_bore']:>7.3f}{x['max_vm']:>8.1f}{x['mass_kg']:>9.3f}")
    if ok:
        print("\n最优:", {k: ok[0][k] for k in
              ("h_bore", "h_knee", "p", "r_knee_mm", "sigma_bore", "FOS_bore", "mass_kg")})
    print("report ->", p)


if __name__ == "__main__":
    main()
