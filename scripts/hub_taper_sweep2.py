# -*- coding: utf-8 -*-
"""tapered 轮毂第二轮扫描：bore 直径 × 单段/双段锥形 × 厚度配比。

沿用 hub_stress_tapered.py 的变厚度盘 FD 解法与自校验口径。
目的：找出满足 bore FOS>=1.5（显式计入叶片离心载荷）且增重最小的轮毂轮廓。
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, r"D:\Virtu模型\scripts")
import closed_impeller_proctor as cp  # noqa: E402
from hub_stress_tapered import (  # noqa: E402
    RHO, SY, NU, KB, E_MOD, D2, D1T, D1H, Z_BLADES, TB, AXIAL_L,
    blade_rim_stress_pa, solve_var, ruler_bore_sigma, fos, PROJ,
)

N_RPM = 40300.5
R_K = D1H / 2.0  # 双段锥形拐点半径 mm


def profile_single(h1, h2, bore):
    """a,b 用米，与 solve_var 的 h_fn 入参单位一致。

    注意：dh_fn 必须返回 dh_mm/dr_mm（无量纲）。r 为米、h 为毫米，
    故 f'(r)=s[mm/m] 需再除 1e3 才是无量纲斜率。
    """
    a, b = bore / 2.0 / 1000.0, D2 / 2.0 / 1000.0
    s = (h2 - h1) / (b - a)          # mm per m
    si = s / 1e3                      # 无量纲 dh_mm/dr_mm
    return (lambda r: h1 + s * (r - a)), (lambda r: si)


def profile_dual(h1, hk, h2, bore):
    """内段（bore -> D1h/2）等厚 h1，外段线性降到 h2。"""
    a, b = bore / 2.0 / 1000.0, D2 / 2.0 / 1000.0
    rk = R_K / 1000.0
    s2 = (h2 - hk) / (b - rk)        # mm per m
    s2i = s2 / 1e3                    # 无量纲

    def hf(r):
        return h1 if r <= rk else hk + s2 * (r - rk)

    def dhf(r):
        return 0.0 if r <= rk else s2i

    return hf, dhf


def vol_mm3(hf, bore):
    """轮毂盘体积（旋转体，2*pi*r*h 积分；r 用 mm，hf 期望米输入）。"""
    a, b = bore / 2.0, D2 / 2.0
    r = np.linspace(a, b, 4001)
    h = np.array([hf(x / 1000.0) for x in r])
    return float(np.trapezoid(2 * math.pi * r * h, r))


def main():
    rows = []
    base = solve_var(D2, 26.4, N_RPM, *profile_single(8.0, 8.0, 26.4), rim_sigma=0.0)
    ref = ruler_bore_sigma(D2, 26.4, N_RPM)
    print("自校验 err%:", round(abs(base["sigma_theta_bore_MPa"] - ref) / ref * 100, 3))

    for bore in [26.4, 32.0, 40.0, 50.0]:
        for kind in ("single", "dual"):
            for h1 in [16.0, 20.0, 24.0, 28.0]:
                for h2 in [3.0, 4.0, 5.0, 6.0]:
                    if h2 > h1:
                        continue
                    if kind == "single":
                        hf, dhf = profile_single(h1, h2, bore)
                    else:
                        hk = max(h2, 0.4 * h1 + 0.6 * h1)  # 拐点保持接近 h1
                        hk = h1
                        hf, dhf = profile_dual(h1, hk, h2, bore)
                    sr_rim, _, _ = blade_rim_stress_pa(h2)
                    s0 = solve_var(D2, bore, N_RPM, hf, dhf, rim_sigma=0.0)
                    s1 = solve_var(D2, bore, N_RPM, hf, dhf, rim_sigma=sr_rim)
                    sig_bore = max(s0["sigma_theta_bore_MPa"], s1["sigma_theta_bore_MPa"])
                    vm_max = max(s0["max_vm_MPa"], s1["max_vm_MPa"])
                    v = vol_mm3(hf, bore)
                    rows.append({
                        "bore_mm": bore, "profile": kind,
                        "h_bore_mm": h1, "h_rim_mm": h2,
                        "sigma_theta_bore_MPa": round(sig_bore, 1),
                        "FOS_bore": round(fos(sig_bore), 3),
                        "max_vm_MPa": round(vm_max, 1),
                        "FOS_vm": round(fos(vm_max), 3),
                        "hub_vol_mm3": round(v, 0),
                        "hub_mass_kg": round(v * RHO * 1e-9, 3),
                        "r_vm_mm": round(max(s0["r_max_vm_mm"], s1["r_max_vm_mm"]), 1),
                    })

    ok = [x for x in rows if x["FOS_bore"] >= 1.5 and x["FOS_vm"] >= 1.5]
    ok.sort(key=lambda x: x["hub_mass_kg"])
    out = {"self_check_err_pct": round(abs(base["sigma_theta_bore_MPa"] - ref) / ref * 100, 3),
           "baseline_flat8": {"sigma_bore_MPa": round(base["sigma_theta_bore_MPa"], 1),
                              "FOS": round(fos(base["sigma_theta_bore_MPa"]), 3),
                              "hub_mass_kg": round(vol_mm3(profile_single(8.0, 8.0, 26.4)[0], 26.4) * RHO * 1e-9, 3)},
           "rows": rows, "feasible_top": ok[:12], "n_rows": len(rows), "n_feasible": len(ok)}
    PROJ.mkdir(parents=True, exist_ok=True)
    p = PROJ / "hub_taper_sweep2.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print("baseline:", out["baseline_flat8"])
    print(f"{'bore':>6}{'prof':>8}{'h1':>6}{'h2':>6}{'sig':>8}{'FOS':>7}{'mass_kg':>9}")
    print("== 可行方案按质量升序 top12 ==")
    for x in ok[:12]:
        print(f"{x['bore_mm']:>6.1f}{x['profile']:>8}{x['h_bore_mm']:>6.1f}{x['h_rim_mm']:>6.1f}"
              f"{x['sigma_theta_bore_MPa']:>8.1f}{x['FOS_bore']:>7.3f}{x['hub_mass_kg']:>9.3f}")
    print("可行数 / 总数:", len(ok), "/", len(rows))
    print("report ->", p)


if __name__ == "__main__":
    main()
