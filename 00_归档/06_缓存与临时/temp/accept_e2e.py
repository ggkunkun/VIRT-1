# -*- coding: utf-8 -*-
"""端到端验收：solver.build -> ruler 判定 -> bore 硬判据是否生效。"""
import json
import sys

sys.path.insert(0, r"D:\Virtu模型\scripts")
import impeller_deterministic_solver as S          # noqa: E402
import closed_impeller_proctor as CP               # noqa: E402

CASES = [(220.0, 40300.5), (220.0, 39000.0), (240.0, 37000.0)]
for D2, N in CASES:
    p, m = S.build(D2, N)
    if p is None:
        print(f"D2={D2} N={N} -> build 失败: {m}")
        continue
    rec, vio, adv = CP.ruler(p)
    print(f"=== D2={D2} N={N} ===")
    print(f"  th={p['hub_disk_thickness_mm']} h_rim={p['hub_rim_thickness_mm']} "
          f"p_exp={p['hub_taper_exponent']} rk={p['hub_knee_r_mm']} L={p['axial_length_mm']}")
    print(f"  pi={rec.get('pressure_ratio_recomputed')} u2={rec.get('u2_m_s')} "
          f"FOS_eq={rec.get('FOS_recomputed')}")
    print(f"  bore FOS={m['tapered_hub']['FOS_bore_tapered']} "
          f"sig={m['tapered_hub']['sigma_theta_bore_tapered_MPa']} MPa")
    print(f"  VIOL({len(vio)}): {vio}")
print("\n--- 反例：等厚 8mm（应判红）---")
bad = {"D2_mm": 220.0, "bore_diameter_mm": 26.4, "N_rpm": 40300.5, "Z_blades": 12,
       "blade_thickness_mm": 1.8, "D1t_mm": 166.03, "D1h_mm": 76.5,
       "axial_length_mm": 91.65, "hub_knee_r_mm": 38.25}
r = S.bore_fos_fd(bad, h_bore=8.0, h_rim=4.0, power=1.0)
print(f"等厚 8mm FOS={r['FOS_bore']:.3f} (期望 <1.5) -> {'判红 OK' if r['FOS_bore'] < 1.5 else '异常'}")
