# -*- coding: utf-8 -*-
"""定位 workbench 卡点：逐段计时 solver 各步骤。"""
import sys
import time

sys.path.insert(0, r"D:\Virtu模型\scripts")
import impeller_deterministic_solver as S  # noqa: E402

free = {"Z_blades": 12, "beta2b_deg": 25.0, "eta_total": 0.85,
        "D2_mm": 220.0, "N_rpm": 40000.0, "b2_ratio": 0.09}


def tic(label, fn):
    t0 = time.time()
    fn()
    print(f"{label:>28}: {time.time() - t0:8.2f} s", flush=True)


tic("build(220, 40300.5)", lambda: S.build(220.0, 40300.5))

p, _ = S.build(220.0, 40300.5)
tic("tapered_hub_check(p)", lambda: S.tapered_hub_check(p))
tic("solve_min_hub_thickness(p)", lambda: S.solve_min_hub_thickness(p))
tic("tune_N_for_pi(220)", lambda: S.tune_N_for_pi(220.0, 12, 25.0, 0.85, 0.09))
tic("tune_D2_for_pi(40000)", lambda: S.tune_D2_for_pi(40000.0, 12, 25.0, 0.85, 0.09))
tic("candidates(free)", lambda: S.candidates(free))
print("done", flush=True)
