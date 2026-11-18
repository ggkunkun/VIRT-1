"""轮毂盘 / 中心孔孔边应力解析复核（Timoshenko 旋转空心圆盘, 自由-自由边界）。

目的：客户判据 ruler 只覆盖叶片等效应力 FOS，不覆盖轮毂中心孔孔边应力。
本脚本用解析解独立复核，输出 STRUCTURAL_REVIEW.json，不改动 proctor 任何判据。
"""
import json
import math
from pathlib import Path

PROJ = Path(r"D:\Virtu模型\projects\impeller_closed_v1_solver_v1")
OUT = PROJ / "STRUCTURAL_REVIEW.json"

p = json.loads((PROJ / "params_frozen.json").read_text(encoding="utf-8"))
D2 = p["D2_mm"] / 1000.0
b = D2 / 2.0
a = (p.get("bore_diameter_mm") or 24.0) / 1000.0
N = float(p["N_rpm"])
rho, nu = 4430.0, 0.34
w = 2 * math.pi * N / 60.0
K = (3 + nu) / 8.0

sigma_center_solid = K * rho * w**2 * b**2
# 空心盘孔边 (r=a): sigma_r=0, sigma_theta = K*rho*w^2*(2b^2 + 2(1-nu)/(3+nu)*a^2)
sigma_theta_bore = K * rho * w**2 * (2 * b**2 + 2 * (1 - nu) / (3 + nu) * a**2)
ratio = sigma_theta_bore / sigma_center_solid

pi0 = float(p.get("claimed_pressure_ratio") or 4.01)

MATERIALS = {
    "Ti-6Al-4V": 880e6,
    "Ti-6Al-2Sn-4Zr-2Mo": 900e6,
    "Inconel 718 (solution+aged)": 1034e6,
}
FS_REQ = 1.5

def pi_at(n_rpm):
    return 1.0 + (pi0 - 1.0) * (n_rpm / N) ** 2

schemes = []
schemes.append({
    "scheme": "A 现状：中心通孔 bore=%.1f mm + 盘厚 %.1f mm" % (a * 1000, p.get("hub_disk_thickness_mm", 8.0)),
    "sigma_theta_bore_MPa": round(sigma_theta_bore / 1e6, 1),
    "material": "Ti-6Al-4V",
    "FOS_bore": round(MATERIALS["Ti-6Al-4V"] / sigma_theta_bore, 2),
    "verdict": "不满足 FOS>=1.5" if MATERIALS["Ti-6Al-4V"] / sigma_theta_bore < FS_REQ else "满足",
    "note": "孔径对孔边切向应力影响极小（系数 (1+2(1-nu)/(3+nu)*(a/b)^2)=%.3f），缩小孔径无法解决" % ratio,
})
for name, sy in MATERIALS.items():
    if name == "Ti-6Al-4V":
        continue
    schemes.append({
        "scheme": "B 换材料：%s，几何不变" % name,
        "sigma_theta_bore_MPa": round(sigma_theta_bore / 1e6, 1),
        "material": name,
        "FOS_bore": round(sy / sigma_theta_bore, 2),
        "verdict": "不满足 FOS>=1.5" if sy / sigma_theta_bore < FS_REQ else "满足",
        "note": "材料升级只能把 FOS 提到 %.2f，仍低于 1.5" % (sy / sigma_theta_bore),
    })
schemes.append({
    "scheme": "C 取消中心通孔（实心盘 + 端面法兰/摩擦传扭）",
    "sigma_theta_bore_MPa": round(sigma_center_solid / 1e6, 1),
    "material": "Ti-6Al-4V",
    "FOS_bore": round(MATERIALS["Ti-6Al-4V"] / sigma_center_solid, 2),
    "verdict": "满足" if MATERIALS["Ti-6Al-4V"] / sigma_center_solid >= FS_REQ else "不满足 FOS>=1.5",
    "note": "盘体中心应力 %.1f MPa，FOS=%.2f；代价是连接方式变更，需客户确认轴系接口" % (
        sigma_center_solid / 1e6, MATERIALS["Ti-6Al-4V"] / sigma_center_solid),
})
n_max = N * math.sqrt(MATERIALS["Ti-6Al-4V"] / FS_REQ / sigma_theta_bore)
schemes.append({
    "scheme": "D 保留中心孔 + 降转速至满足 FOS=1.5",
    "N_rpm": round(n_max, 0),
    "u2_m_s": round(2 * math.pi * n_max / 60 * b, 1),
    "pressure_ratio": round(pi_at(n_max), 2),
    "material": "Ti-6Al-4V",
    "verdict": "压比 %.2f < 4.0，不满足客户指标" % pi_at(n_max),
    "note": "降速是唯一不改连接方式的路径，但直接击穿 pi>=4.0 指标",
})

doc = {
    "scope": "轮毂盘/中心孔孔边结构复核（客户判据 ruler 之外的自主动作，不影响 ruler 判定）",
    "method": "Timoshenko 旋转空心圆盘解析解（自由-自由边界），nu=0.34, rho=4430 kg/m3",
    "inputs": {
        "D2_mm": p["D2_mm"], "N_rpm": N, "bore_diameter_mm": p.get("bore_diameter_mm"),
        "hub_disk_thickness_mm": p.get("hub_disk_thickness_mm"),
        "u2_m_s": round(w * b, 1), "omega_rad_s": round(w, 1),
    },
    "results": {
        "sigma_center_solid_MPa": round(sigma_center_solid / 1e6, 1),
        "sigma_theta_bore_MPa": round(sigma_theta_bore / 1e6, 1),
        "bore_to_solid_ratio": round(ratio, 3),
        "FOS_bore_Ti64": round(MATERIALS["Ti-6Al-4V"] / sigma_theta_bore, 2),
        "FOS_required": FS_REQ,
    },
    "conclusion": "当前几何（中心通孔 + u2=%.1f m/s）在解析口径下孔边切向应力 %.0f MPa，"
                  "Ti-6Al-4V FOS=%.2f，低于 1.5；孔边应力约为实心盘中心的 %.2f 倍，且对孔径不敏感。"
                  "该风险位于客户判据(叶片等效应力 FOS)之外，需三维 FEA 与连接方式决策后才能关闭。"
                  % (w * b, sigma_theta_bore / 1e6, MATERIALS["Ti-6Al-4V"] / sigma_theta_bore, ratio),
    "schemes": schemes,
    "residual_risk": "客户 ruler 仍判 PASS（其判据不含孔边应力）；本文件只做披露与方案比选，不构成放宽或收紧。",
}
OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(doc["results"], ensure_ascii=False, indent=2))
for s in schemes:
    print("-", s["scheme"], "|", s.get("FOS_bore"), "|", s["verdict"])
print("written:", OUT)
