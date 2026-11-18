# -*- coding: utf-8 -*-
"""校验带状求解与稠密求解一致，并测 build 提速。"""
import sys
import time

import numpy as np

sys.path.insert(0, r"D:\Virtu模型\scripts")
import hub_stress_tapered as HT  # noqa: E402
import impeller_deterministic_solver as S  # noqa: E402

# --- 1) 数值一致性：直接复算同一 FD 系统 ---
orig = np.linalg.solve
cap = {}


def spy(M, r):
    cap["M"] = M.copy()
    cap["r"] = r.copy()
    return HT._solve_banded2(M, r, M.shape[0] - 1)


HT.np.linalg.solve = spy
HT.solve_var(220.0, 22.0, 40300.5, lambda x: 12.25, lambda x: 0.0, n=600)
HT.np.linalg.solve = orig

M, rr = cap["M"], cap["r"]
u_band = HT._solve_banded2(M, rr, 600)
u_dense = orig(M, rr)
err = float(np.max(np.abs(u_band - u_dense)) / np.max(np.abs(u_dense)))
print(f"[一致性] 带宽解 vs 稠密解 最大相对误差 = {err:.3e}")

# --- 2) 速度 ---
t0 = time.time()
for _ in range(5):
    HT.solve_var(220.0, 22.0, 40300.5, lambda x: 12.25, lambda x: 0.0, n=600)
print(f"[速度] solve_var 单次 = {(time.time() - t0) / 5 * 1000:.1f} ms")

t0 = time.time()
S.build(220.0, 40300.5)
print(f"[速度] build 单次 = {time.time() - t0:.2f} s")
