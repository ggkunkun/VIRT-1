# -*- coding: utf-8 -*-
import sys

sys.path.insert(0, r"D:\Virtu模型\scripts")
import impeller_deterministic_solver as S  # noqa: E402

base = {"D2_mm": 220.0, "bore_diameter_mm": 26.4, "N_rpm": 40300.5, "Z_blades": 12,
        "blade_thickness_mm": 1.8, "D1t_mm": 166.03, "D1h_mm": 76.5,
        "axial_length_mm": 91.65, "hub_knee_r_mm": 38.25}
print(f"{'th':>5}{'L':>8}{'FOS':>9}{'sig':>9}{'rim_sig':>9}")
for th in [8, 10, 12, 14, 16, 18, 20, 24, 30, 40]:
    for L in [77.0, 91.65]:
        b = dict(base, axial_length_mm=L)
        r = S.bore_fos_fd(b, h_bore=th, h_rim=4.0, power=6.0)
        print(f"{th:>5.0f}{L:>8.1f}{r['FOS_bore']:>9.3f}"
              f"{r['sigma_theta_bore_MPa']:>9.1f}{r['rim_blade_sigma_MPa']:>9.1f}")
print("\nsolve_min_hub_thickness on base:", S.solve_min_hub_thickness(base)[0])
