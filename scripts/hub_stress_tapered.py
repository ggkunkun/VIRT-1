# -*- coding: utf-8 -*-
"""锥形 (tapered) 轮毂盘应力复核 —— 变厚度旋转盘轴对称 ODE 数值解。

为什么需要它：
  closed_impeller_proctor.ruler() 的 bore 应力和 FOS 用"等厚实心环盘"闭式解
      sigma_bore = (3+nu)/4 * rho * omega^2 * (r2^2 + (1-nu)/(3+nu)*r1^2)
  这是保守假设。真实轮毂做成内厚外薄的锥形后，外圈惯性质量下降、bore 处
  切向应力显著降低，等厚公式会误判为不达标。

本脚本求解变厚度盘的控制方程（Timoshenko, Theory of Elasticity §33）：
      d/dr(h*r*sigma_r) - h*sigma_theta + rho*omega^2*r^2*h = 0
  以径向位移 u(r) 为未知量的二阶 ODE：
      u'' + (1/r + h'/h) u' + (nu*h'/(h*r) - 1/r^2) u = -(1-nu^2)*rho*omega^2*r/E
  边界：内孔 sigma_r(a)=0；外缘 sigma_r(b)=rim_sigma（叶片离心力的等效径向拉）。

自校验：h=const 时必须复现 ruler() 的闭式解，否则不解。

判定权不变：本脚本只给应力/FOS 数值，合格与否仍由 ruler() 说。
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, r"D:\Virtu模型\scripts")
import closed_impeller_proctor as cp  # noqa: E402

RHO = cp.RHO_TI
SY = cp.SY_TI
NU = cp.NU_TI
KB = cp.K_BLADE
E_MOD = 113.8e9

PROJ = Path(r"D:\Virtu模型\projects\impeller_workbench_v1")

D2 = 220.0
BORE = 26.4
N_RPM = 40300.5
D1T = 166.03
D1H = 76.5
Z_BLADES = 12
TB = 1.8
AXIAL_L = 82.5


def blade_rim_stress_pa(h_rim_mm):
    """叶片离心力折算到轮毂外缘的等效径向拉应力（保守估算）。

    弦长沿半径 41.6 -> 55.8 mm 线性，厚度 1.8 mm，曲面系数 0.7，
    径向 D1h/2 -> D2/2，轴向长度 AXIAL_L。
    """
    c1 = math.pi * D1T / Z_BLADES - TB
    c2 = math.pi * D2 / Z_BLADES - TB
    a_bl = 0.7 * 0.5 * (c1 + c2) * TB
    m_bl = RHO * a_bl * AXIAL_L * 1e-9
    r_cg = 0.5 * (D1H / 2 + D2 / 2) / 1000.0
    om = 2 * math.pi * N_RPM / 60.0
    f_total = Z_BLADES * m_bl * om * om * r_cg
    r_b = D2 / 2 / 1000.0
    return f_total / (2 * math.pi * r_b * h_rim_mm * 1e-3), m_bl * 1e3, f_total


def _solve_banded2(M, rhs, n):
    """求解带宽 2 的带状线性系统（i±1、i±2），等价于 np.linalg.solve(M, rhs)。

    矩阵结构：i=0 行用 0/1/2 列，i=n 行用 n-2/n-1/n 列，内部行为标准三点格式。
    用 scipy.linalg.solve_banded 求解，复杂度 O(n·b²)，比稠密 LU 快约两个数量级。
    """
    ab = np.zeros((5, n + 1))
    for i in range(n + 1):
        j0 = max(0, i - 2)
        j1 = min(n + 1, i + 3)
        for j in range(j0, j1):
            ab[2 + i - j, j] = M[i, j]
    from scipy.linalg import solve_banded
    return solve_banded((2, 2), ab, rhs)


def solve_var(D2, bore, N, h_fn_mm, dh_fn, n=600, rim_sigma=0.0):
    """变厚度盘 FD 解。h_fn_mm(r_m)->mm，dh_fn(r_m)->(dh_mm/dr_mm)。"""
    a = bore / 2.0 / 1000.0
    b = D2 / 2.0 / 1000.0
    r = np.linspace(a, b, n + 1)
    dr = r[1] - r[0]
    h = np.array([h_fn_mm(x) for x in r]) * 1e-3          # m
    dh = np.array([dh_fn(x) for x in r])                  # m/m（无量纲）
    om = 2 * math.pi * N / 60.0
    c = (1 - NU ** 2) * RHO * om ** 2 / E_MOD

    M = np.zeros((n + 1, n + 1))
    rhs = np.zeros(n + 1)

    # i = 0：u'(a) + nu*u/a = 0（内孔自由）
    M[0, 0] = -3.0 / (2 * dr) + NU / a
    M[0, 1] = 4.0 / (2 * dr)
    M[0, 2] = -1.0 / (2 * dr)
    rhs[0] = 0.0

    # 内部点
    for i in range(1, n):
        ri, hi, dhi = r[i], h[i], dh[i]
        p = 1.0 / ri + dhi / hi
        q = NU * dhi / (hi * ri) - 1.0 / ri ** 2
        M[i, i - 1] = 1.0 / dr ** 2 - p / (2 * dr)
        M[i, i] = -2.0 / dr ** 2 + q
        M[i, i + 1] = 1.0 / dr ** 2 + p / (2 * dr)
        rhs[i] = -c * ri

    # i = n：u'(b) + nu*u/b = (1-nu^2)*rim_sigma/E
    M[n, n - 2] = 1.0 / (2 * dr)
    M[n, n - 1] = -4.0 / (2 * dr)
    M[n, n] = 3.0 / (2 * dr) + NU / b
    rhs[n] = (1 - NU ** 2) * rim_sigma / E_MOD

    # 带状（带宽 2）求解：矩阵仅在 i±1、i±2 有非零元，用稠密 solve 会慢约 60 倍。
    u = _solve_banded2(M, rhs, n)

    up = np.empty_like(u)
    up[1:-1] = (u[2:] - u[:-2]) / (2 * dr)
    up[0] = (-3 * u[0] + 4 * u[1] - u[2]) / (2 * dr)
    up[-1] = (3 * u[-1] - 4 * u[-2] + u[-3]) / (2 * dr)

    sr = E_MOD / (1 - NU ** 2) * (up + NU * u / r)
    st = E_MOD / (1 - NU ** 2) * (u / r + NU * up)
    vm = np.sqrt(np.maximum(sr ** 2 - sr * st + st ** 2, 0.0))
    sr[0] = 0.0
    return {
        "r_mm": (r * 1e3).tolist(),
        "h_mm": (h * 1e3).tolist(),
        "sigma_r_MPa": (sr / 1e6).tolist(),
        "sigma_theta_MPa": (st / 1e6).tolist(),
        "von_mises_MPa": (vm / 1e6).tolist(),
        "sigma_theta_bore_MPa": float(st[0] / 1e6),
        "sigma_r_rim_MPa": float(sr[-1] / 1e6),
        "max_vm_MPa": float(vm.max() / 1e6),
        "r_max_vm_mm": float(r[int(vm.argmax())] * 1e3),
    }


def ruler_bore_sigma(D2, bore, N):
    r1 = bore / 2.0 / 1000.0
    r2 = D2 / 2.0 / 1000.0
    u2 = math.pi * D2 * N / 60000.0
    om = u2 / r2
    return (3 + NU) / 4.0 * RHO * om ** 2 * (r2 ** 2 + (1 - NU) / (3 + NU) * r1 ** 2) / 1e6


def fos(sig, k=1.0):
    return SY / (k * sig) if sig > 0 else float("inf")


def linear_taper(h1, h2):
    a = BORE / 2 / 1000.0
    b = D2 / 2 / 1000.0
    slope = (h2 - h1) / ((b - a) * 1e3)

    def hf(x):
        return h1 + (h2 - h1) * (x - a) / (b - a)

    def dhf(_x):
        return slope

    return hf, dhf


def main():
    out = {"inputs": {"D2_mm": D2, "bore_mm": BORE, "N_rpm": N_RPM,
                      "material": "Ti-6Al-4V", "rho": RHO, "sy_MPa": SY,
                      "nu": NU, "E_Pa": E_MOD, "K_BLADE": KB}}

    # ---- 自校验：等厚 8 mm ----
    flat_hf, flat_dhf = linear_taper(8.0, 8.0)
    flat = solve_var(D2, BORE, N_RPM, flat_hf, flat_dhf, rim_sigma=0.0)
    ref = ruler_bore_sigma(D2, BORE, N_RPM)
    out["self_check"] = {
        "ruler_sigma_bore_MPa": round(ref, 2),
        "fd_sigma_bore_MPa": round(flat["sigma_theta_bore_MPa"], 2),
        "rel_err_pct": round(abs(flat["sigma_theta_bore_MPa"] - ref) / ref * 100, 3),
    }

    sr_rim8, m_bl, f_tot = blade_rim_stress_pa(8.0)
    out["blade_load_estimate"] = {
        "blade_mass_g": round(m_bl, 3),
        "total_centrifugal_kN": round(f_tot / 1e3, 2),
        "rim_sigma_at_h8_MPa": round(sr_rim8 / 1e6, 2),
    }

    rows = []
    for h1 in [8.0, 10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 24.0, 28.0]:
        for h2 in [3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0]:
            if h2 > h1 + 1e-9:
                continue
            hf, dhf = linear_taper(h1, h2)
            sr_rim, _, _ = blade_rim_stress_pa(h2)
            s0 = solve_var(D2, BORE, N_RPM, hf, dhf, rim_sigma=0.0)
            s1 = solve_var(D2, BORE, N_RPM, hf, dhf, rim_sigma=sr_rim)
            sig_bore = max(s0["sigma_theta_bore_MPa"], s1["sigma_theta_bore_MPa"])
            vm_max = max(s0["max_vm_MPa"], s1["max_vm_MPa"])
            rows.append({
                "h_bore_mm": h1,
                "h_rim_mm": h2,
                "sigma_theta_bore_MPa": round(sig_bore, 1),
                "FOS_bore_plain": round(fos(sig_bore), 3),
                "FOS_bore_with_Kblade": round(fos(sig_bore, KB), 3),
                "max_von_mises_MPa": round(vm_max, 1),
                "r_max_vm_mm": round(s1["r_max_vm_mm"], 1),
                "FOS_maxVM_with_Kblade": round(fos(vm_max, KB), 3),
                "hub_volume_proxy_mm3": round((h1 + h2) / 2 * (D2 - BORE) / 2 * math.pi * (D2 + BORE) / 2 * 0 + (h1 + h2) / 2 * math.pi * ((D2 / 2) ** 2 - (BORE / 2) ** 2), 0),
            })
    out["sweep"] = rows

    def pick(pred):
        ps = [x for x in rows if pred(x)]
        ps.sort(key=lambda x: (x["hub_volume_proxy_mm3"], x["h_bore_mm"]))
        return ps[:6]

    out["pass_Kblade"] = pick(lambda x: x["FOS_bore_with_Kblade"] >= 1.5 and x["FOS_maxVM_with_Kblade"] >= 1.5)
    out["pass_plain"] = pick(lambda x: x["FOS_bore_plain"] >= 1.5 and x["FOS_maxVM_with_Kblade"] >= 1.5)
    out["pass_simple_bore_only"] = pick(lambda x: x["FOS_bore_plain"] >= 1.5)
    out["any_pass_Kblade"] = bool(out["pass_Kblade"])
    out["any_pass_plain"] = bool(out["pass_plain"])

    PROJ.mkdir(parents=True, exist_ok=True)
    p = PROJ / "hub_tapered_stress_recheck.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print("== 自校验（等厚 8mm 应复现 ruler 闭式解）==")
    print(json.dumps(out["self_check"], ensure_ascii=False))
    print("== 叶片载荷估算 ==")
    print(json.dumps(out["blade_load_estimate"], ensure_ascii=False))
    print("== 扫描（sigma_bore 单位为 MPa，FOS 用 sigma_y=880）==")
    print(f"{'h1':>5}{'h2':>5}{'sig_bore':>10}{'FOS_bore':>10}{'FOS_KB':>8}{'maxVM':>9}{'FOS_VM_KB':>10}{'r_vm':>7}")
    for x in rows:
        print(f"{x['h_bore_mm']:>5.1f}{x['h_rim_mm']:>5.1f}{x['sigma_theta_bore_MPa']:>10.1f}"
              f"{x['FOS_bore_plain']:>10.3f}{x['FOS_bore_with_Kblade']:>8.3f}"
              f"{x['max_von_mises_MPa']:>9.1f}{x['FOS_maxVM_with_Kblade']:>10.3f}"
              f"{x['r_max_vm_mm']:>7.1f}")
    for key, lab in (("pass_plain", "无 K_BLADE 放大：bore FOS>=1.5 且 maxVM FOS>=1.5"),
                     ("pass_Kblade", "含 K_BLADE 放大：bore FOS>=1.5 且 maxVM FOS>=1.5")):
        print(f"== {lab} ==")
        if not out[key]:
            print("  （无满足方案）")
        for x in out[key]:
            print(" ", {k: x[k] for k in ("h_bore_mm", "h_rim_mm", "sigma_theta_bore_MPa",
                                          "FOS_bore_plain", "FOS_bore_with_Kblade",
                                          "max_von_mises_MPa", "FOS_maxVM_with_Kblade",
                                          "hub_volume_proxy_mm3")})
    print("report ->", p)


if __name__ == "__main__":
    main()
