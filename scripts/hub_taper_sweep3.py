# -*- coding: utf-8 -*-
"""tapered 轮毂第三轮：带制造下界的精细搜索，输出可交付轮廓。

约束（工程侧，用户给定 + 常规工艺下限）：
  h_rim >= 4.0 mm   轮毂外缘厚度（叶根过渡 + 密封面）
  h_bore <= 30 mm    bore 处最大盘厚（轴向 L=82.5 内需容纳 b2=19.8 + shroud 2.0）
  h 单调不增（内厚外薄，避免质量集中在外圈）
  bore 26.4 保持不变（轴径已定）

判定：
  硬约束 FOS_bore >= 1.5（显式计入叶片离心载荷的 FD 解）
  另附 K_BLADE 放大口径，供与 ruler 的 sigma_eq 口径对照
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, r"D:\Virtu模型\scripts")
from hub_stress_tapered import (  # noqa: E402
    RHO, SY, NU, KB, E_MOD, D2, D1T, D1H, Z_BLADES, TB, AXIAL_L,
    blade_rim_stress_pa, solve_var, ruler_bore_sigma, fos, PROJ,
)

N_RPM = 40300.5
BORE = 26.4
H_RIM_MIN = 4.0
H_BORE_MAX = 30.0


def two_seg(h_bore, h_knee, h_rim, r_knee_mm, bore):
    """0..r_knee 线性 h_bore->h_knee，r_knee..R2 线性 h_knee->h_rim。米制入参。"""
    a = bore / 2.0 / 1000.0
    b = D2 / 2.0 / 1000.0
    rk = r_knee_mm / 1000.0
    s1 = (h_knee - h_bore) / (rk - a)      # mm/m
    s2 = (h_rim - h_knee) / (b - rk)

    def hf(r):
        return h_bore + s1 * (r - a) if r <= rk else h_knee + s2 * (r - rk)

    def dhf(r):
        return s1 / 1e3 if r <= rk else s2 / 1e3

    return hf, dhf


def vol_mm3(hf, bore):
    a, b = bore / 2.0, D2 / 2.0
    r = np.linspace(a, b, 4001)
    h = np.array([hf(x / 1000.0) for x in r])
    return float(np.trapezoid(2 * math.pi * r * h, r))


def evaluate(hf, dhf, h_rim):
    sr_rim, _, _ = blade_rim_stress_pa(h_rim)
    s0 = solve_var(D2, BORE, N_RPM, hf, dhf, rim_sigma=0.0)
    s1 = solve_var(D2, BORE, N_RPM, hf, dhf, rim_sigma=sr_rim)
    sig = max(s0["sigma_theta_bore_MPa"], s1["sigma_theta_bore_MPa"])
    vmm = max(s0["max_vm_MPa"], s1["max_vm_MPa"])
    v = vol_mm3(hf, BORE)
    return {"sigma_theta_bore_MPa": round(sig, 1),
            "FOS_bore": round(fos(sig), 3),
            "max_vm_MPa": round(vmm, 1),
            "FOS_vm": round(fos(vmm), 3),
            "FOS_bore_Kblade": round(fos(sig, KB), 3),
            "hub_mass_kg": round(v * RHO * 1e-9, 3),
            "r_max_vm_mm": round(max(s0["r_max_vm_mm"], s1["r_max_vm_mm"]), 1)}


def main():
    ref = ruler_bore_sigma(D2, BORE, N_RPM)
    base_hf, base_dhf = two_seg(8.0, 8.0, 8.0, D1H / 2, BORE)
    base = evaluate(base_hf, base_dhf, 8.0)
    print("baseline 等厚 8mm:", base, "| ruler 闭式 bore:", round(ref, 1))

    rows = []
    for h_bore in [10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 22.0, 24.0, 26.0, 28.0]:
        for h_rim in [4.0, 5.0, 6.0, 8.0]:
            for r_knee in [D1H / 2, 60.0, 80.0]:
                if r_knee < BORE / 2 or r_knee > D2 / 2:
                    continue
                # 内段线性降到 h_rim（双段），保证单调不增
                hf, dhf = two_seg(h_bore, h_bore, h_rim, r_knee, BORE)
                r = evaluate(hf, dhf, h_rim)
                rows.append({"h_bore": h_bore, "h_rim": h_rim, "r_knee_mm": r_knee, **r})

    ok = [x for x in rows if x["FOS_bore"] >= 1.5 and x["FOS_vm"] >= 1.5]
    ok.sort(key=lambda x: x["hub_mass_kg"])
    ok_kb = [x for x in rows if x["FOS_bore_Kblade"] >= 1.5 and x["FOS_vm"] >= 1.5]
    ok_kb.sort(key=lambda x: x["hub_mass_kg"])

    out = {"baseline_flat8": base, "ruler_bore_closed_form_MPa": round(ref, 1),
           "constraints": {"h_rim_min_mm": H_RIM_MIN, "h_bore_max_mm": H_BORE_MAX,
                           "bore_mm": BORE, "monotone_non_increasing": True},
           "feasible_plain": ok[:15], "feasible_with_Kblade": ok_kb[:15],
           "n_rows": len(rows), "n_feasible_plain": len(ok), "n_feasible_Kblade": len(ok_kb),
           "all_rows": rows}
    p = PROJ / "hub_taper_sweep3.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    hdr = f"{'h_bore':>7}{'h_rim':>6}{'r_knee':>7}{'sig':>8}{'FOS':>7}{'FOS_KB':>8}{'maxVM':>8}{'mass_kg':>9}"
    print("\n" + hdr)
    for x in ok[:15]:
        print(f"{x['h_bore']:>7.1f}{x['h_rim']:>6.1f}{x['r_knee_mm']:>7.1f}"
              f"{x['sigma_theta_bore_MPa']:>8.1f}{x['FOS_bore']:>7.3f}{x['FOS_bore_Kblade']:>8.3f}"
              f"{x['max_vm_MPa']:>8.1f}{x['hub_mass_kg']:>9.3f}")
    print("\n可行(plain) / 可行(K_BLADE) / 总:", len(ok), "/", len(ok_kb), "/", len(rows))
    if ok_kb:
        print("含 K_BLADE 口径最省料:", {k: ok_kb[0][k] for k in
              ("h_bore", "h_rim", "r_knee_mm", "sigma_theta_bore_MPa", "FOS_bore",
               "FOS_bore_Kblade", "max_vm_MPa", "hub_mass_kg")})
    print("report ->", p)


if __name__ == "__main__":
    main()
