# -*- coding: utf-8 -*-
"""A' 确定性约束求解器（与 closed_impeller_proctor 同源公式，本模块只反解，不做判定）。

被 impeller_design_workbench.py 以 --mode assist/auto 调用。
红线：任何“合格/不合格”的判定仍然只由 closed_impeller_proctor.ruler() 给出。
"""
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import closed_impeller_proctor as cp  # noqa: E402

CP_AIR, T01, P01, MDOT = cp.CP, cp.T01, cp.P01, cp.MDOT
GAMMA, RGAS = cp.GAMMA, cp.RGAS
SY, RHO, NU, K = cp.SY_TI, cp.RHO_TI, cp.NU_TI, cp.K_BLADE

# FOS=1.5 对应的叶尖速硬上限（由尺子公式反解，u2 超过它 FOS 必然 <1.5）
U2_LIMIT = math.sqrt(SY / 1.5 / ((3 + NU) / 8.0 * RHO * K / 1e6))
MREL_CAP = 1.08          # 相对马赫数设计裕度（尺子红线 1.15，此处主动留 0.07 裕度）
PI_TARGET = 4.01         # 压比反解目标（尺子红线 3.96）
H_RIM_MIN = 4.0          # 轮毂外缘最小厚度（叶根过渡 + 密封面下界）
HUB_TAPER_POWER = 6.0    # 外段幂律指数：内厚外薄，坡度越大 bore 应力越低
HUB_FOS_TARGET = 1.60    # 反解厚度时的设计目标（尺子红线 1.5，留约 7% 裕度）


def u2_of(D2, N):
    return math.pi * D2 * N / 60000.0


def area_for_ca1(ca1):
    """由 ca1 目标反解喉口面积（m^2），与尺子进口迭代同一套关系式。"""
    T1 = T01 - ca1 * ca1 / (2 * CP_AIR)
    P1 = P01 * (T1 / T01) ** (GAMMA / (GAMMA - 1.0))
    rho1 = P1 / (RGAS * T1)
    return MDOT / (rho1 * ca1)


def fill_claims(p):
    """宣称量由尺子复算派生（纯算术，不是设计决策）。"""
    vv, _, _ = cp.ruler(p)
    if vv.get("u2_m_s"):
        p["claimed_tip_speed_m_s"] = round(vv["u2_m_s"], 2)
    if vv.get("pressure_ratio_recomputed"):
        p["claimed_pressure_ratio"] = round(vv["pressure_ratio_recomputed"], 3)
    if vv.get("FOS_recomputed"):
        p["claimed_FOS"] = round(min(vv["FOS_recomputed"], 2.5), 3)
    return p


def _taper_profile(h_bore, h_rim, power, rk_m, b_m):
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


def solve_min_hub_thickness(p, h_rim=H_RIM_MIN, power=HUB_TAPER_POWER, lo=8.0, hi=40.0, step=0.25,
                           target=HUB_FOS_TARGET):
    """反解满足 bore FOS>=1.5 的最小轮毂盘厚度（内段等厚、外段幂律）。

    FOS 随 th 单调递增，故从下界向上递增扫描，返回第一个可行值。
    """
    th = lo
    while th <= hi + 1e-9:
        r = bore_fos_fd(p, h_bore=th, h_rim=h_rim, power=power)
        if r["FOS_bore"] >= target:
            return th, r
        th += step
    return hi, bore_fos_fd(p, h_bore=hi, h_rim=h_rim, power=power)


def inlet_geometry(D2, N, ca1_t, bore, Z=12, tb=1.8):
    """该 ca1 下可行的 D1t（取 M_rel 允许上界，喉口面积最大）与对应 D1h。"""
    u2 = u2_of(D2, N)
    A1 = area_for_ca1(ca1_t)
    need = 4.0 * A1 / math.pi * 1e6
    min_d1t_pitch = (8.1 + tb) * Z / math.pi
    low = max(math.sqrt(need + (1.6 * bore) ** 2), 0.40 * D2, min_d1t_pitch)
    T1 = T01 - ca1_t * ca1_t / (2 * CP_AIR)
    a1 = math.sqrt(GAMMA * RGAS * T1)
    wmax = MREL_CAP * a1
    if wmax <= ca1_t:
        return None
    u1t_max = math.sqrt(wmax ** 2 - ca1_t ** 2)
    high = min(u1t_max * D2 / u2, 0.85 * D2)
    if low > high:
        return None
    D1t = round(high, 2)
    inner = D1t ** 2 - need
    if inner <= (1.6 * bore) ** 2:
        return None
    D1h = math.sqrt(inner)
    if not (bore < D1h < D1t):
        return None
    return D1t, D1h


def build(D2, N, Z=12, beta2=25.0, eta=0.85, b2ratio=0.09, tb=1.8, ts=2.0, th=8.0):
    """按确定性规则拼出全套 17 字段。返回 (params, meta) 或 (None, 失败原因)。"""
    Z = int(min(max(round(Z), 6), 24))
    max_z_for_d2 = max(6, int((0.83 * D2 * math.pi) / (8.1 + tb)))
    if Z > max_z_for_d2:
        Z = max_z_for_d2
    bore = round(max(12.0, 0.12 * D2), 2)      # 盘厚 8mm 起 + bore 不薄于 D2 的 12%，避免 hub 盘薄壳化
    chosen = None
    for ca1_t in [x * 5.0 for x in range(18, 43)]:      # ca1 目标 90..210 m/s
        g = inlet_geometry(D2, N, ca1_t, bore, Z=Z, tb=tb)
        if g:
            chosen = (ca1_t, g[0], g[1])
            if ca1_t >= 100:
                break
    if not chosen:
        return None, "进口喉口面积/相对马赫数与 D2 不相容"
    ca1_t, D1t, D1h = chosen
    b2 = round(b2ratio * D2, 2)
    # ---- 由 bore 强度反解轮毂盘厚度（内段等厚 + 外段幂律），替代固定 8 mm ----
    # 依据：平面应力膜解中 h 只以 h'/h 出现，等厚段加厚不降 bore 应力、只增质量；
    # 故取"满足 FOS_bore>=1.5 的最小厚度"。L 与 th 互相依赖，迭代 3 次收敛。
    _pre = {"D2_mm": D2, "bore_diameter_mm": bore, "N_rpm": N, "Z_blades": int(Z),
            "blade_thickness_mm": tb, "D1t_mm": D1t, "D1h_mm": round(D1h, 2),
            "axial_length_mm": 0.35 * D2}
    _L_guess = 0.35 * D2
    for _ in range(3):
        _pre["axial_length_mm"] = _L_guess
        th, _bres = solve_min_hub_thickness(_pre)
        _lo = max(0.20 * D2, th + ts + b2 + 0.5)
        _hi = 0.55 * D2
        _L_guess = 0.5 * (_lo + _hi) if _lo <= _hi else _lo
    lo_L = max(0.20 * D2, th + ts + b2 + 0.5)
    hi_L = 0.55 * D2
    if lo_L > hi_L:
        return None, f"轴向长可行区间为空 [{lo_L:.1f},{hi_L:.1f}]"
    p = {"D2_mm": round(D2, 2), "N_rpm": round(N, 1), "Z_blades": int(Z),
         "beta2b_deg": beta2, "b2_mm": b2, "D1t_mm": D1t, "D1h_mm": round(D1h, 2),
         "axial_length_mm": round(0.5 * (lo_L + hi_L), 2),
         "shroud_thickness_mm": ts, "blade_thickness_mm": tb,
         "hub_disk_thickness_mm": round(th, 2), "bore_diameter_mm": bore,
         "hub_rim_thickness_mm": H_RIM_MIN, "hub_knee_r_mm": round(D1h / 2.0, 2),
         "hub_taper_exponent": HUB_TAPER_POWER,
         "fillet_root_mm": 1.2, "eta_total": eta,
         "claimed_pressure_ratio": 4.0,
         "claimed_tip_speed_m_s": u2_of(D2, N), "claimed_FOS": 2.5}
    fill_claims(p)
    return p, {"ca1_target": ca1_t, "tapered_hub": tapered_hub_check(p)}


def tune_N_for_pi(D2, Z=12, beta2=25.0, eta=0.85, b2ratio=0.09):
    """固定 D2，反解满足 π 目标的最小转速。"""
    lo, hi = 3000.0, 120000.0
    for _ in range(50):
        mid = 0.5 * (lo + hi)
        p, _ = build(D2, mid, Z, beta2, eta, b2ratio)
        if p is None:
            hi = mid
            continue
        pv = cp.ruler(p)[0].get("pressure_ratio_recomputed")
        if pv is None or pv < PI_TARGET:
            lo = mid
        else:
            hi = mid
    N = 0.5 * (lo + hi)
    p, _ = build(D2, N, Z, beta2, eta, b2ratio)
    return p, N


def tune_D2_for_pi(N, Z=12, beta2=25.0, eta=0.85, b2ratio=0.09):
    """固定 N，反解满足 π 目标的最小 D2。D2 搜索上界由 u2 硬上限反解，避免被截断。"""
    lo = 60.0
    hi = min(1600.0, U2_LIMIT * 60000.0 / (math.pi * N) * 1.02)
    if hi <= lo:
        return None, 0.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        p, _ = build(mid, N, Z, beta2, eta, b2ratio)
        if p is None:
            lo = mid
            continue
        pv = cp.ruler(p)[0].get("pressure_ratio_recomputed")
        if pv is None or pv < PI_TARGET:
            lo = mid
        else:
            hi = mid
    D2 = 0.5 * (lo + hi)
    p, _ = build(D2, N, Z, beta2, eta, b2ratio)
    return p, D2


def candidates(free):
    """由模型给的自由度生成候选解。free 键：Z_blades / beta2b_deg / eta_total /
    b2_ratio（b2/D2 假设值）/ D2_mm（首选外径）/ N_rpm（首选转速）。
    返回 [{"id":"A","policy":"锁 D2 反解 N",...}, {"id":"B","policy":"锁 N 反解 D2",...}]"""
    Z = int(round(float(free.get("Z_blades") or 12)))
    Z = min(max(Z, 6), 24)
    beta2 = float(free.get("beta2b_deg") or 25.0)
    beta2 = min(max(beta2, 15.0), 55.0)
    eta = float(free.get("eta_total") or 0.85)
    if not (0.70 <= eta <= 0.90):
        eta = 0.85
    br = float(free.get("b2_ratio") or 0.09)
    br = min(max(br, 0.03), 0.09)
    D2_pref = float(free.get("D2_mm") or 220.0)
    N_pref = float(free.get("N_rpm") or 40000.0)
    if not (60.0 <= D2_pref <= 600.0):
        D2_pref = 220.0
    if not (3000.0 <= N_pref <= 120000.0):
        N_pref = 40000.0

    out = []
    pA, NA = tune_N_for_pi(D2_pref, Z, beta2, eta, br)
    if pA:
        out.append({"id": "A", "policy": f"锁 D2={D2_pref:.0f} mm，反解 N={NA:.0f} rpm",
                    "params": pA, "tapered_hub": tapered_hub_check(pA)})
    pB, D2B = tune_D2_for_pi(N_pref, Z, beta2, eta, br)
    if pB:
        out.append({"id": "B", "policy": f"锁 N={N_pref:.0f} rpm，反解 D2={D2B:.0f} mm",
                    "params": pB, "tapered_hub": tapered_hub_check(pB)})
    for c in out:
        _, v, _ = cp.ruler(c["params"])
        c["n_viol"] = len(v)
        c["violations"] = v
    return out


def from_model_params(p_model):
    """assist 模式：保留模型选的 Z/β2b/η 与 D2、N 的首选，其余全部反解。"""
    free = {"Z_blades": p_model.get("Z_blades", 12),
            "beta2b_deg": p_model.get("beta2b_deg", 25.0),
            "eta_total": p_model.get("eta_total", 0.85),
            "D2_mm": p_model.get("D2_mm", 220.0),
            "N_rpm": p_model.get("N_rpm", 40000.0)}
    D2m = p_model.get("D2_mm")
    if isinstance(D2m, (int, float)) and D2m > 0:
        free["b2_ratio"] = (p_model.get("b2_mm") or 0.09 * D2m) / D2m
    return candidates(free)


if __name__ == "__main__":
    print("u2_limit = %.1f m/s" % U2_LIMIT)
    for c in candidates({"D2_mm": 220, "N_rpm": 40000, "Z_blades": 12, "beta2b_deg": 25,
                         "eta_total": 0.85}):
        vv = cp.ruler(c["params"])[0]
        print(c["id"], c["policy"], "违规", c["n_viol"],
              "π=%.3f u2=%.1f FOS=%.2f FOS_bore_taper=%.2f" % (
                  vv["pressure_ratio_recomputed"], vv["u2_m_s"],
                  vv["FOS_recomputed"], c["tapered_hub"]["FOS_bore_tapered"]))
        for x in c["violations"]:
            print("   !", x)
