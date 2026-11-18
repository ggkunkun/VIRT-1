# -*- coding: utf-8 -*-
"""tapered 轮毂第五轮：等厚内段 + 幂律外段，内段厚度取最小可行值。

数学事实（本轮确认）：
  平面应力轴对称膜解中，h 只以 h'/h 出现，惯性项与刚度项同时含 h 且可约去。
  因此【等厚段的绝对厚度不影响 bore 应力，只增加质量】。
  降低 bore 应力的唯一杠杆是厚度坡度 h'/h（内厚外薄）。

由此得到设计原则：
  1) 内段取满足工艺/装配的最小等厚值（h_bore 下界 10 mm，bore=26.4 需足够轮毂壁）
  2) 外段用尽量大的下落坡度（幂律 p 大 → 外段更快变薄）
  3) h_rim 取下界 4 mm（叶根过渡 + 密封面）
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
H_BORE_MIN = 10.0


def prof(h0, p, r_knee_mm, bore):
    a = bore / 2.0 / 1000.0
    b = D2 / 2.0 / 1000.0
    rk = r_knee_mm / 1000.0
    span = b - rk

    def hf(r):
        if r <= rk:
            return h0
        t = max((b - r) / span, 0.0)
        return H_RIM + (h0 - H_RIM) * (t ** p)

    def dhf(r):
        if r <= rk:
            return 0.0
        t = max((b - r) / span, 1e-9)
        return (h0 - H_RIM) * p * (t ** (p - 1.0)) * (-1.0 / span) / 1e3

    return hf, dhf


def vol_mm3(hf, bore):
    a, b = bore / 2.0, D2 / 2.0
    r = np.linspace(a, b, 6001)
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
            "mass_kg": round(v * RHO * 1e-9, 3),
            "r_max_vm_mm": round(max(s0["r_max_vm_mm"], s1["r_max_vm_mm"]), 1)}


def main():
    rows = []
    for h0 in [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0]:
        for p in [2.0, 3.0, 4.0, 6.0, 8.0]:
            for r_knee in [D1H / 2, 30.0, 45.0, 55.0]:
                if r_knee < BORE / 2:
                    continue
                hf, dhf = prof(h0, p, r_knee, BORE)
                rows.append({"h0": h0, "p": p, "r_knee_mm": r_knee, **evaluate(hf, dhf)})

    ok = [x for x in rows if x["FOS_bore"] >= 1.5 and x["FOS_vm"] >= 1.5]
    ok.sort(key=lambda x: x["mass_kg"])
    out = {"n_rows": len(rows), "n_feasible": len(ok),
           "constraints": {"bore": BORE, "h_rim": H_RIM, "h_bore_min": H_BORE_MIN,
                           "ruler_bore_closed_form_MPa": round(ruler_bore_sigma(D2, BORE, N_RPM), 1)},
           "feasible_top": ok[:20], "all_rows": rows}
    p = PROJ / "hub_taper_sweep5.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print("总 / 可行:", len(rows), "/", len(ok))
    print(f"{'h0':>6}{'p':>5}{'r_knee':>7}{'sig':>8}{'FOS':>7}{'maxVM':>8}{'mass_kg':>9}{'r_vm':>7}")
    for x in ok[:20]:
        print(f"{x['h0']:>6.1f}{x['p']:>5.1f}{x['r_knee_mm']:>7.1f}{x['sigma_bore']:>8.1f}"
              f"{x['FOS_bore']:>7.3f}{x['max_vm']:>8.1f}{x['mass_kg']:>9.3f}{x['r_max_vm_mm']:>7.1f}")
    if ok:
        print("\n最优:", ok[0])
    print("report ->", p)


if __name__ == "__main__":
    main()
