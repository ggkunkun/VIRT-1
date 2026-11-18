# -*- coding: utf-8 -*-
"""验证带状求解与既有基准值（545.6 MPa / FOS 1.613）一致，并测提速。"""
import sys
import time

sys.path.insert(0, r"D:\Virtu模型\scripts")
import hub_stress_tapered as HT  # noqa: E402
import impeller_deterministic_solver as S  # noqa: E402

p = {"D2_mm": 220.0, "N_rpm": 40300.5, "Z_blades": 12, "beta2b_deg": 25.0,
     "b2_mm": 19.8, "D1t_mm": 111.6, "D1h_mm": 76.5, "axial_length_mm": 75.0,
     "shroud_thickness_mm": 2.0, "blade_thickness_mm": 1.8,
     "hub_disk_thickness_mm": 12.25, "bore_diameter_mm": 26.4,
     "hub_rim_thickness_mm": 4.0, "hub_knee_r_mm": 38.25,
     "hub_taper_exponent": 6.0, "fillet_root_mm": 1.2, "eta_total": 0.85}

th = S.tapered_hub_check(p)
print("[基准复算] tapered_hub_check =", {k: (round(v, 3) if isinstance(v, float) else v)
                                   for k, v in th.items()})

t0 = time.time()
for _ in range(5):
    S.tapered_hub_check(p)
print(f"[速度] tapered_hub_check 单次 = {(time.time() - t0) / 5 * 1000:.1f} ms")

t0 = time.time()
pp, meta = S.build(220.0, 40300.5)
print(f"[速度] build 单次 = {time.time() - t0:.3f} s")
print("[build] th =", pp["hub_disk_thickness_mm"], "| taper =", meta["tapered_hub"])
