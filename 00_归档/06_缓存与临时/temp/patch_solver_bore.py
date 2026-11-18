# -*- coding: utf-8 -*-
"""把 solver 里 tapered_hub_check 的经验折减因子替换为真实 FD 解，并让 build 反解轮毂盘厚度。"""
import io
import re
import shutil
from pathlib import Path

P = Path(r"D:\Virtu模型\scripts\impeller_deterministic_solver.py")
src = P.read_text(encoding="utf-8")
shutil.copy2(P, P.with_suffix(".py.bak_before_fd_bore"))

lines = src.splitlines(keepends=True)
# 定位函数区间
start = next(i for i, l in enumerate(lines) if l.startswith("def tapered_hub_check("))
# 找 return 块的结束 '}'（顶格 4 空格 + }）
end = None
for i in range(start, len(lines)):
    if lines[i].rstrip("\n") == "    }":
        end = i
        break
assert end is not None, "未找到 return 结束"

NEW = '''def _taper_profile(h_bore, h_rim, power, rk_m, b_m):
    """内段等厚 + 外段幂律变薄。返回 (h_mm(r_m), dh/dr 无量纲)。"""
    span = max(b_m - rk_m, 1e-6)

    def hf(r):
        if r <= rk_m:
            return h_bore
        return h_rim + (h_bore - h_rim) * (max((b_m - r) / span, 0.0) ** power)

    def dhf(r):
        if r <= rk_m:
            return 0.0
        t = max((b_m - r) / span, 1e-9)
        return (h_bore - h_rim) * power * (t ** (power - 1.0)) * (-1.0 / span) / 1e3

    return hf, dhf


def bore_fos_fd(p, h_bore=None, h_rim=None, power=None, rk_mm=None):
    """变厚度轮毂 bore 强度：轴对称变厚盘 ODE 有限差分解，叶片离心力并入外缘径向拉。

    口径：叶片载荷已显式施加，故不再乘 K_BLADE（避免重复计入）。
    """
    import hub_stress_tapered as _hst

    D2 = float(p.get("D2_mm", 220.0))
    bore = float(p.get("bore_diameter_mm", 26.4))
    N = float(p.get("N_rpm", 43266.0))
    Z = max(float(p.get("Z_blades", 12)), 1.0)
    tb = float(p.get("blade_thickness_mm", 1.8))
    D1t = float(p.get("D1t_mm", 0.66 * D2))
    D1h = float(p.get("D1h_mm", 0.83 * D2))
    L = float(p.get("axial_length_mm", 0.35 * D2))
    h_bore = float(h_bore if h_bore is not None else p.get("hub_disk_thickness_mm", 18.0))
    h_rim = float(h_rim if h_rim is not None else p.get("hub_rim_thickness_mm", 4.0))
    power = float(power if power is not None else p.get("hub_taper_exponent", 6.0))
    if rk_mm is None:
        rk_mm = p.get("hub_knee_r_mm") or (D1h / 2.0)
    a_m = max(bore / 2000.0, 0.005)
    b_m = D2 / 2000.0
    rk_m = min(max(float(rk_mm) / 1000.0, a_m), b_m - 1e-4)
    hf, dhf = _taper_profile(h_bore, h_rim, power, rk_m, b_m)
    omega = 2.0 * math.pi * N / 60.0
    c1 = math.pi * D1t / Z - tb
    c2 = math.pi * D2 / Z - tb
    a_bl = 0.7 * 0.5 * (c1 + c2) * tb
    m_bl = RHO * max(a_bl, 0.0) * L * 1e-9
    r_cg = 0.5 * (D1h / 2.0 + D2 / 2.0) / 1000.0
    f_tot = Z * m_bl * omega * omega * r_cg
    rim_sig = f_tot / (2.0 * math.pi * b_m * h_rim * 1e-3)
    sv = _hst.solve_var(D2, bore, N, hf, dhf, rim_sigma=rim_sig)
    sig = sv["sigma_theta_bore_MPa"]
    return {"sigma_theta_bore_MPa": sig, "FOS_bore": SY / max(sig, 1e-9),
            "max_vm_MPa": sv["max_vm_MPa"], "rim_blade_sigma_MPa": rim_sig / 1e6,
            "r_max_vm_mm": sv["r_max_vm_mm"], "h_bore_mm": h_bore,
            "h_rim_mm": h_rim, "power": power, "r_knee_mm": rk_mm}


def tapered_hub_check(p, h_bore_mm=None, h_rim_mm=H_RIM_MIN, power=HUB_TAPER_POWER, n_rings=600):
    """变厚旋转盘 bore 强度校核（真实 FD 解，无经验折减因子）。

    历史教训：早期版本用 reduction = 1/(1+0.22*ln(taper_ratio)*power**0.45) 估算
    根部加厚收益。该式无物理依据、默认 h_rim=3.5 低于 4 mm 制造下界，且结论与真实
    有限差分解相反——等厚 8 mm 真实 bore FOS=0.946（不通过），旧式却给出通过。
    v2 起改为直接求解轴对称变厚盘 ODE，判据 FOS_bore >= 1.5，载荷含叶片离心力。
    """
    D2 = float(p.get("D2_mm", 220.0))
    bore = float(p.get("bore_diameter_mm", 26.4))
    N = float(p.get("N_rpm", 43266.0))
    r1 = max(bore / 2000.0, 0.005)
    r2 = max(D2 / 2000.0, r1 + 0.01)
    omega = 2.0 * math.pi * N / 60.0
    sigma_bore_equal = ((3.0 + NU) / 4.0 * RHO * omega ** 2
                        * (r2 ** 2 + (1.0 - NU) / (3.0 + NU) * r1 ** 2) / 1e6)
    hb = h_bore_mm if h_bore_mm is not None else p.get("hub_disk_thickness_mm", 8.0)
    res = bore_fos_fd(p, h_bore=hb, h_rim=h_rim_mm, power=power)
    return {
        "h_bore_mm": round(res["h_bore_mm"], 2),
        "h_rim_mm": round(res["h_rim_mm"], 2),
        "power": res["power"],
        "r_knee_mm": round(float(res["r_knee_mm"]), 2),
        "n_rings": n_rings,
        "sigma_theta_bore_equal_MPa": round(sigma_bore_equal, 1),
        "sigma_theta_bore_tapered_MPa": round(res["sigma_theta_bore_MPa"], 1),
        "FOS_bore_tapered": round(res["FOS_bore"], 3),
        "FOS_bore_equal_no_blade": round(SY / max(sigma_bore_equal, 1e-9), 3),
        "rim_blade_sigma_MPa": round(res["rim_blade_sigma_MPa"], 2),
        "passed_bore_fos_1p5": res["FOS_bore"] >= 1.5,
    }


def solve_min_hub_thickness(p, h_rim=H_RIM_MIN, power=HUB_TAPER_POWER, lo=8.0, hi=40.0, step=0.5):
    """反解满足 bore FOS>=1.5 的最小轮毂盘厚度（内段等厚、外段幂律）。"""
    th = hi
    while th >= lo:
        r = bore_fos_fd(p, h_bore=th, h_rim=h_rim, power=power)
        if r["FOS_bore"] >= 1.5:
            return th, r
        th -= step
    return hi, bore_fos_fd(p, h_bore=hi, h_rim=h_rim, power=power)
'''
lines[start:end + 1] = [NEW]
src = "".join(lines)

# 常量注入
if "H_RIM_MIN" not in src.split("def ")[0]:
    src = src.replace("K_BLADE = ", "H_RIM_MIN = 4.0            # 轮毂外缘最小厚度（叶根过渡 + 密封面）\nHUB_TAPER_POWER = 6.0      # 外段幂律指数（内厚外薄，坡度越大 bore 应力越低）\nK_BLADE = ", 1)

P.write_text(src, encoding="utf-8")
print("replace done, lines:", len(src.splitlines()))
