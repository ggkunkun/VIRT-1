# -*- coding: utf-8 -*-
"""封闭式航空叶轮：模型自主设计 + 独立审计监考环。

分工：模型产出全部设计参数与工程代码；本脚本只下达客户指标、执行产物、
用独立解析尺子复核，并对「封闭拓扑」判据做植入坏样本的反证自测。
尺子数值口径：analytic_recomputed（由模型参数解析复算，非物理实测）。
"""
import os
import sys
import json
import re
import math
import time
import hashlib
import subprocess
import urllib.request
from pathlib import Path

import impeller_iface

sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

ROOT = Path(__file__).resolve().parent.parent
PROJ = ROOT / "projects" / "impeller_closed_v1"
VENV_PY = str(ROOT / ".venv" / "Scripts" / "python.exe")
OLLAMA = "http://127.0.0.1:11435"
MODEL = "virtu-ties-v1:latest"
MODE = "bare"
ENGINE = "model"          # model = 由模型写脚本；solver = 由确定性产出器接管建模/复算/制图（诚实标注于报告）          # bare=模型全权 | assist=保留模型自由度+求解器反解其余 | auto=求解器自主
WEIGHT_DIGEST = "UNRESOLVED:not_probed"


def weight_digest_of(tag):
    """真实权重层摘要：解析 ollama show --modelfile 的 FROM 行，落到实际权重文件后算 sha256。

    绝不允许硬编码/继承一个常量来代表被测权重——那样审计身份与真实权重脱钩，
    换权重后仍报告旧摘要，等于审计链撒谎。解析失败一律返回 UNRESOLVED:*，在报告里显式暴露。
    """
    env = dict(os.environ, OLLAMA_HOST=OLLAMA.replace("http://", ""))
    from_line = ""
    try:
        r = subprocess.run(["ollama", "show", "--modelfile", tag], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=env, timeout=180)
        for ln in (r.stdout or "").splitlines():
            s = ln.strip()
            if s.upper().startswith("FROM "):
                from_line = s[5:].strip().strip('"')
    except Exception as e:
        return f"UNRESOLVED:show_{type(e).__name__}"
    if not from_line:
        return "UNRESOLVED:no_FROM"

    cands = []
    fp = Path(from_line)
    if fp.exists():
        cands.append(fp)
    else:
        name, _, tagpart = tag.partition(":")
        tagpart = tagpart or "latest"
        stores = []
        if os.environ.get("OLLAMA_MODELS"):
            stores.append(Path(os.environ["OLLAMA_MODELS"]))
        stores.append(Path.home() / ".ollama" / "models")
        for store in stores:
            if not store.exists():
                continue
            mf = store / "manifests" / "registry.ollama.ai" / "library" / name / tagpart
            if not mf.exists():
                continue
            try:
                man = json.loads(mf.read_text(encoding="utf-8"))
            except Exception:
                continue
            for layer in man.get("layers", []):
                if "model" in layer.get("mediaType", ""):
                    cands.append(store / "blobs" / ("sha256-" + layer["digest"].split(":")[-1]))
    for f in cands:
        if f.exists() and f.is_file():
            h = hashlib.sha256()
            with open(f, "rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 23), b""):
                    h.update(chunk)
            return "sha256:" + h.hexdigest()
    return f"UNRESOLVED:no_weight_file(FROM={from_line})"
LOCK = ROOT / "runs" / "closed_impeller.chain.lock"
MDOT = 2.0
T01 = 288.15
P01 = 101325.0
CP = 1004.5
GAMMA = 1.4
RGAS = 287.05
RHO_TI = 4430.0
SY_TI = 880.0
NU_TI = 0.34
K_BLADE = 1.20
A2_BLOCKAGE = 0.92

BRIEF = """你是航空发动机离心压气机设计工程师。请自主设计一台小型涡喷发动机用【封闭式离心叶轮】（Closed / Shrouded Centrifugal Impeller）。

客户指标（硬约束）：
1. 工质空气，进口总温 T01=288.15 K，总压 P01=101.325 kPa。
2. 设计流量 mdot=2.0 kg/s；设计转速下总压比 π≥4.0。
3. 材料 Ti-6Al-4V：密度 4430 kg/m³，屈服强度 880 MPa，泊松比 0.34。
4. 额定转速下强度安全系数 FOS≥1.5（旋转盘+叶片离心载荷，解析估算即可，注明方法）。
5. 结构必须封闭：轮毂盘(hub disk) + 完整盖盘(shroud) + 其间 Z 片后弯叶片；叶顶由盖盘封闭，轴向进气、径向出气。半开式（无盖盘）不合格。
6. 五轴铣削可制造：叶片厚度≥1.2 mm，盖盘厚度≥1.5 mm，叶根圆角 R≥1.0 mm。

本任务书不给任何几何示例值——所有尺寸（D2、转速、叶片数、出口角、进口直径等）由你自主决定并自洽。
本轮交付：一个 ```json 代码块，字段如下（全部必填，数值型，design_rationale 为字符串）：
D2_mm, N_rpm, Z_blades, beta2b_deg(出口后弯角,相对径向方向), b2_mm(出口流道宽度), D1t_mm(进口叶顶直径), D1h_mm(进口轮毂直径), axial_length_mm, shroud_thickness_mm, blade_thickness_mm, hub_disk_thickness_mm, bore_diameter_mm, fillet_root_mm, eta_total(你假设的总效率), claimed_pressure_ratio(你宣称的总压比), claimed_tip_speed_m_s(你宣称的叶尖速度), claimed_FOS(你宣称的安全系数), design_rationale(说明设计依据与计算过程)。
禁止输出 JSON 代码块以外的正文。"""

SYSTEM = ("你是 Virtu 工业超级智能体，负责航空叶轮设计与工程代码。证据契约："
          "所有宣称数值必须可由你给出的参数复算；不得宣称未经计算的结果；"
          "被审计驳回时必须修改违规参数，禁止原样重发同一 payload。")

DESIGN_SYSTEM = SYSTEM

REQUIRED_FIELDS = ["D2_mm", "N_rpm", "Z_blades", "beta2b_deg", "b2_mm", "D1t_mm", "D1h_mm",
                   "axial_length_mm", "shroud_thickness_mm", "blade_thickness_mm",
                   "hub_disk_thickness_mm", "bore_diameter_mm", "fillet_root_mm",
                   "eta_total", "claimed_pressure_ratio", "claimed_tip_speed_m_s", "claimed_FOS"]


def log(event, data):
    PROJ.mkdir(parents=True, exist_ok=True)
    entry = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "event": event, "data": data}
    with open(PROJ / "proctor_log.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f">>> [{event}] {json.dumps(data, ensure_ascii=False)[:220]}", flush=True)


def call_model(messages, tag, num_predict=4096, temperature=0.3):
    payload = {"model": MODEL, "messages": messages, "stream": False,
               "options": {"temperature": temperature, "num_predict": num_predict, "num_ctx": 8192}}
    req = urllib.request.Request(OLLAMA + "/api/chat", data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=900) as resp:
        res = json.loads(resp.read().decode("utf-8"))
    dt = time.time() - t0
    content = res.get("message", {}).get("content", "")
    ev = res.get("eval_count", 0)
    rec = {"tag": tag, "elapsed_s": round(dt, 2), "eval_count": ev,
           "tok_per_s": round(ev / (res.get("eval_duration", 1e9) / 1e9), 2) if res.get("eval_duration") else None,
           "prompt_tokens": res.get("prompt_eval_count"), "response": content}
    with open(PROJ / "transcript.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    log("MODEL_CALL", {"tag": tag, "elapsed_s": rec["elapsed_s"], "eval_count": ev, "tok_per_s": rec["tok_per_s"]})
    return content


def strip_think(text):
    if "<think>" in text:
        parts = re.split(r"<think>.*?</think>", text, flags=re.DOTALL)
        text = parts[-1] if parts else text
    return text


def extract_json(text):
    text = strip_think(text)
    m = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    candidates = [m.group(1)] if m else []
    candidates.append(text)
    for cand in candidates:
        start = cand.find("{")
        if start < 0:
            continue
        depth = 0
        for i in range(start, len(cand)):
            if cand[i] == "{":
                depth += 1
            elif cand[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(cand[start:i + 1])
                    except Exception:
                        break
    return None


def extract_code(text):
    text = strip_think(text)
    m = re.search(r"```python\s*(.*?)\s*```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    m = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return ""


def ruler(p):
    """独立解析尺子。返回 (values, violations, advisory)。不信任模型宣称值。"""
    v, adv = [], []
    missing = [k for k in REQUIRED_FIELDS if k not in p]
    if missing:
        return {}, [f"缺字段: {missing}"], []
    bad = [k for k in REQUIRED_FIELDS if not isinstance(p[k], (int, float)) or isinstance(p[k], bool)]
    if bad:
        return {}, [f"非数值字段: {bad}"], []
    D2 = p["D2_mm"]; N = p["N_rpm"]; Z = p["Z_blades"]; beta2 = p["beta2b_deg"]
    b2 = p["b2_mm"]; D1t = p["D1t_mm"]; D1h = p["D1h_mm"]; L = p["axial_length_mm"]
    ts = p["shroud_thickness_mm"]; tb = p["blade_thickness_mm"]; th = p["hub_disk_thickness_mm"]
    bore = p["bore_diameter_mm"]; fil = p["fillet_root_mm"]; eta = p["eta_total"]

    # bore=0 表示实心盘（无中心通孔，整体转子形态）；判据只要求 bore 非负且小于 D1h，不强制存在孔。
    # 2026-11-12 修订：原式写成 0<bore 属实现细节过严，bore=0 不违反"直径序不干涉"的物理内涵。
    if not (0 <= bore < D1h < D1t < D2):
        v.append(f"直径序不成立: 需 0<=bore<D1h<D1t<D2（bore=0 表示实心盘）, 实得 bore={bore}, D1h={D1h}, D1t={D1t}, D2={D2}")
    if not (6 <= Z <= 24) or int(Z) != Z:
        v.append(f"叶片数 Z={Z} 不在 [6,24] 整数域")
    if not (15 <= beta2 <= 55):
        v.append(f"出口后弯角 beta2b={beta2}° 不在 [15,55]°")
    if not (0.02 <= b2 / D2 <= 0.10):
        v.append(f"出口流道宽比 b2/D2={b2 / D2:.4f} 不在 [0.02,0.10]")
    if not (0.40 <= D1t / D2 <= 0.85):
        v.append(f"进口叶顶径比 D1t/D2={D1t / D2:.3f} 不在 [0.40,0.85]")
    if not (0.20 * D2 <= L <= 0.55 * D2):
        v.append(f"轴向长 L={L} 不在 [0.20·D2, 0.55·D2]=[{0.2 * D2:.1f},{0.55 * D2:.1f}]")
    if L < th + ts + b2:
        v.append(f"轴向长 L={L} < 轮毂盘+盖盘+出口叶高之和 {th + ts + b2}")
    if tb < 1.2:
        v.append(f"叶片厚 {tb} < 1.2 mm 制造下限")
    if ts < 1.5:
        v.append(f"盖盘厚 {ts} < 1.5 mm 制造下限")
    if fil < 1.0:
        v.append(f"叶根圆角 R{fil} < 1.0 mm")
    if not (0.70 <= eta <= 0.90):
        v.append(f"假设总效率 eta={eta} 不在可信域 [0.70,0.90]")
    pitch1 = math.pi * D1t / Z - tb
    pitch2 = math.pi * D2 / Z - tb
    if pitch1 < 8.0:
        v.append(f"进口叶片间通道净宽 {pitch1:.2f} mm < 8 mm（五轴刀具可达性）")
    if pitch2 < 6.0:
        v.append(f"出口叶片间通道净宽 {pitch2:.2f} mm < 6 mm")

    u2 = math.pi * D2 * N / 60000.0
    if u2 > 550:
        v.append(f"叶尖速度 u2={u2:.1f} m/s 超过 Ti 叶轮绝对包线 550 m/s")
    if abs(p["claimed_tip_speed_m_s"] - u2) / u2 > 0.01:
        v.append(f"宣称叶尖速 {p['claimed_tip_speed_m_s']} 与复算 u2={u2:.1f} m/s 偏差 >1%")
    sigma_eq = (3 + NU_TI) / 8.0 * RHO_TI * u2 * u2 * K_BLADE / 1e6
    fos = SY_TI / sigma_eq
    if fos < 1.5:
        v.append(f"复算 FOS={fos:.3f} < 1.5（等效旋转盘应力 σ_eq={sigma_eq:.1f} MPa，含叶片载荷系数 {K_BLADE}）")
    if p["claimed_FOS"] > fos * 1.15:
        v.append(f"宣称 FOS={p['claimed_FOS']} 高于独立复算 {fos:.3f} 的 15%，属安全过宣称")
    r1 = bore / 2.0 / 1000.0
    r2 = D2 / 2.0 / 1000.0
    omega = u2 / r2
    if bore > 0:
        # 孔边切向应力（环盘解）：只对真正存在中心通孔的几何有物理意义
        sigma_bore = (3 + NU_TI) / 4.0 * RHO_TI * omega ** 2 * (r2 ** 2 + (1 - NU_TI) / (3 + NU_TI) * r1 ** 2) / 1e6
        adv.append(f"保守等厚环盘 bore 应力 {sigma_bore:.1f} MPa (FOS_bore={SY_TI / sigma_bore:.2f})；"
                   f"真实 tapered 轮毂需 FEA 复核，本尺子用等效盘+叶片系数")

        # ---- tapered 轮毂 bore 强度硬判据（仅当显式给出 rim 厚度且 < 轮毂盘厚度时启用）----
        # 口径：变厚度旋转盘轴对称 ODE 有限差分解；叶片离心力以等效径向拉施加于外缘，
        # 故不再乘 K_BLADE（避免重复计入）。判据 FOS_bore >= 1.5。
        h_rim_p = p.get("hub_rim_thickness_mm")
        if isinstance(h_rim_p, (int, float)) and not isinstance(h_rim_p, bool) and 0 < h_rim_p < th:
            try:
                import hub_stress_tapered as _hst
                _rk_mm = p.get("hub_knee_r_mm")
                if not isinstance(_rk_mm, (int, float)) or _rk_mm <= 0:
                    _rk_mm = D1h / 2.0
                _pw = p.get("hub_taper_exponent")
                if not isinstance(_pw, (int, float)) or not (1.0 <= _pw <= 12.0):
                    _pw = 6.0
                _b = D2 / 2.0 / 1000.0
                _rk = float(_rk_mm) / 1000.0
                _rk = min(max(_rk, r1), _b - 1e-4)
                _span = max(_b - _rk, 1e-6)
                _hb = float(th)
                _hr = float(h_rim_p)

                def _hf(r, _rk=_rk, _b=_b, _span=_span, _hb=_hb, _hr=_hr, _pw=_pw):
                    if r <= _rk:
                        return _hb
                    return _hr + (_hb - _hr) * (max((_b - r) / _span, 0.0) ** _pw)

                def _dhf(r, _rk=_rk, _b=_b, _span=_span, _hb=_hb, _hr=_hr, _pw=_pw):
                    if r <= _rk:
                        return 0.0
                    t = max((_b - r) / _span, 1e-9)
                    return (_hb - _hr) * _pw * (t ** (_pw - 1.0)) * (-1.0 / _span) / 1e3

                _a_bl = 0.7 * 0.5 * (pitch1 + pitch2) * tb
                _m_bl = RHO_TI * _a_bl * L * 1e-9
                _r_cg = 0.5 * (D1h / 2.0 + D2 / 2.0) / 1000.0
                _f_tot = Z * _m_bl * omega * omega * _r_cg
                _rim_sig = _f_tot / (2.0 * math.pi * _b * _hr * 1e-3)
                _sv = _hst.solve_var(D2, bore, N, _hf, _dhf, rim_sigma=_rim_sig)
                _sig_b = _sv["sigma_theta_bore_MPa"]
                _fos_b = SY_TI / _sig_b if _sig_b > 0 else 99.0
                if _fos_b < 1.5:
                    v.append(f"tapered 轮毂 bore 复算 FOS={_fos_b:.3f} < 1.5"
                             f"（sigma_theta_bore={_sig_b:.1f} MPa，已含叶片离心载荷；"
                             f"h_bore={_hb:.1f}/h_rim={_hr:.1f}/p={_pw:.1f}/rk={_rk_mm:.1f} mm）")
                else:
                    adv.append(f"tapered 轮毂 bore 复算 FOS={_fos_b:.3f} "
                               f"(sigma_theta_bore={_sig_b:.1f} MPa，含叶片离心载荷，已通过)")
            except Exception as _e:  # noqa: BLE001
                adv.append(f"tapered 轮毂 bore 复算失败，未计入判定：{type(_e).__name__}: {_e}")
    else:
        # 实心盘（无中心通孔）：切向应力峰值在盘中心。孔边解在 r1→0 时不收敛到该值（相差约 2 倍），
        # 故 bore=0 必须切换口径，否则同一几何在 r1=0 处出现应力断裂。
        sigma_hub = (3 + NU_TI) / 8.0 * RHO_TI * omega ** 2 * r2 ** 2 / 1e6
        adv.append(f"实心盘中心切向应力 {sigma_hub:.1f} MPa (FOS_hub={SY_TI / sigma_hub:.2f})；"
                   f"bore=0 表示无中心通孔，本尺子按实心盘口径评价，真实 tapered 轮毂仍需 FEA 复核")

    beta_r = math.radians(beta2)
    sigma = 1.0 - math.sqrt(max(math.cos(beta_r), 0.0)) / (Z ** 0.7)
    cm2 = 0.25 * u2
    pi_c = dh0 = cu2 = 0.0
    outlet_ok = True
    for _ in range(80):
        cu2 = sigma * (u2 - cm2 * math.tan(beta_r))
        dh0 = u2 * cu2
        T02 = T01 + dh0 / CP
        if T02 <= 0 or not math.isfinite(T02):
            outlet_ok = False
            break
        pi_c = (1.0 + eta * dh0 / (CP * T01)) ** (GAMMA / (GAMMA - 1.0))
        P02 = pi_c * P01
        c2 = math.hypot(cm2, cu2)
        T2 = T02 - c2 * c2 / (2 * CP)
        if T2 <= 0:
            outlet_ok = False
            break
        P2 = P02 * (T2 / T02) ** (GAMMA / (GAMMA - 1.0))
        rho2 = P2 / (RGAS * T2)
        A2 = math.pi * (D2 / 1000.0) * (b2 / 1000.0) * A2_BLOCKAGE
        cm2_new = MDOT / (rho2 * A2)
        if not math.isfinite(cm2_new) or cm2_new > 500:
            outlet_ok = False
            break
        if abs(cm2_new - cm2) < 1e-4:
            cm2 = cm2_new
            break
        cm2 = 0.5 * cm2 + 0.5 * cm2_new
    if not outlet_ok:
        v.append(f"出口迭代非物理：b2={b2}mm 下流量/面积失配（cm2 发散或出口静温≤0），压比不可复算；需增大 b2 或 D2")
    else:
        if pi_c < 3.96:
            v.append(f"复算总压比 π={pi_c:.3f} < 3.96（客户指标 π≥4.0，含 1% 尺子容差）；u2={u2:.1f}, 滑移σ={sigma:.3f}, Δh0={dh0 / 1000:.1f} kJ/kg")
        if abs(p["claimed_pressure_ratio"] - pi_c) / pi_c > 0.08:
            v.append(f"宣称压比 {p['claimed_pressure_ratio']} 与独立复算 {pi_c:.3f} 偏差 >8%")

    A1 = math.pi / 4.0 * ((D1t / 1000.0) ** 2 - (D1h / 1000.0) ** 2)
    ca1 = 150.0
    T1 = P1 = rho1 = 0.0
    inlet_ok = A1 > 1e-6
    if inlet_ok:
        for _ in range(80):
            T1 = T01 - ca1 * ca1 / (2 * CP)
            if T1 <= 0:
                inlet_ok = False
                break
            P1 = P01 * (T1 / T01) ** (GAMMA / (GAMMA - 1.0))
            rho1 = P1 / (RGAS * T1)
            ca1_new = MDOT / (rho1 * A1)
            if not math.isfinite(ca1_new) or ca1_new > 600:
                inlet_ok = False
                break
            if abs(ca1_new - ca1) < 1e-4:
                ca1 = ca1_new
                break
            ca1 = 0.5 * ca1 + 0.5 * ca1_new
    Mrel = None
    if not inlet_ok:
        v.append(f"进口迭代非物理：喉口面积 A1={A1 * 1e6:.1f} mm² 与流量失配（ca1 发散或静温≤0）")
    else:
        u1t = math.pi * D1t * N / 60000.0
        w1t = math.hypot(ca1, u1t)
        a1 = math.sqrt(GAMMA * RGAS * T1)
        Mrel = w1t / a1
        if Mrel > 1.15:
            v.append(f"进口叶顶相对马赫数 M_rel={Mrel:.3f} > 1.15（跨音速诱导轮上限）；ca1={ca1:.1f} m/s, u1t={u1t:.1f} m/s")
        if not (80 <= ca1 <= 240):
            v.append(f"进口轴向速度 ca1={ca1:.1f} m/s 不在 [80,240]（喉口面积与流量不匹配）")
    Ns = None
    if outlet_ok and pi_c > 0:
        Q1 = MDOT / (P01 / (RGAS * T01))
        dh_ad = CP * T01 * (pi_c ** ((GAMMA - 1) / GAMMA) - 1)
        Ns = (N * math.pi / 30.0) * math.sqrt(Q1) / (dh_ad ** 0.75)
        adv.append(f"比转速 Ns={Ns:.3f}（rad/s 基），离心级典型 0.4–1.2")

    vals = {"u2_m_s": round(u2, 3), "slip_sigma": round(sigma, 4),
            "dh0_kJ_kg": round(dh0 / 1000, 3) if outlet_ok else None,
            "pressure_ratio_recomputed": round(pi_c, 4) if outlet_ok else None,
            "cm2_m_s": round(cm2, 2) if outlet_ok else None,
            "sigma_eq_MPa": round(sigma_eq, 2), "FOS_recomputed": round(fos, 4),
            "ca1_m_s": round(ca1, 2) if inlet_ok else None,
            "M_rel_tip": round(Mrel, 4) if Mrel is not None else None,
            "Ns": round(Ns, 4) if Ns is not None else None,
            "T02_K": round(T01 + dh0 / CP, 2) if outlet_ok else None}
    return vals, v, adv


def full_ring_at(mesh, z, r_expect, tol=0.05):
    """截面 z 处是否存在半径≈r_expect 的整圆闭合环。返回 (ring_bool, 闭合曲线数)。"""
    import numpy as np
    try:
        sec = mesh.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
    except Exception:
        return False, 0
    if sec is None:
        return False, 0
    try:
        disc = sec.discrete
    except Exception:
        return False, 0
    ring = False
    for curve in disc:
        pts = np.asarray(curve)
        if len(pts) < 8:
            continue
        r = np.hypot(pts[:, 0], pts[:, 1])
        mean = float(r.mean())
        if mean <= 1e-6:
            continue
        std = float(r.std())
        closed = float(np.linalg.norm(pts[0] - pts[-1])) < 0.05 * mean + 1.0
        length = float(np.sum(np.linalg.norm(np.diff(pts, axis=0), axis=1)))
        if abs(mean - r_expect) / r_expect < tol and std / mean < 0.03 and closed and length > 0.85 * 2 * math.pi * mean:
            ring = True
    return ring, len(disc)


def topology_audit(mesh, p):
    """封闭拓扑三判据：盖盘带整环 / 轮毂带整环 / 叶片中段无整环且有离散叶片岛。"""
    z0, z1 = float(mesh.bounds[0][2]), float(mesh.bounds[1][2])
    R = p["D2_mm"] / 2.0
    th, ts = p["hub_disk_thickness_mm"], p["shroud_thickness_mm"]
    z_shroud = z1 - ts / 2.0
    z_hub = z0 + th / 2.0
    z_mid = z0 + th + 0.5 * max(z1 - z0 - th - ts, 1.0)
    ring_s, n_s = full_ring_at(mesh, z_shroud, R)
    ring_h, n_h = full_ring_at(mesh, z_hub, R)
    ring_m, n_m = full_ring_at(mesh, z_mid, R)
    viol = []
    if not ring_s:
        viol.append(f"盖盘封闭判据红：z={z_shroud:.2f}mm（盖盘带）半径≈{R:.1f}mm 处无整圆闭合环 ⇒ 叶顶未封闭（半开式或假盖盘）")
    if not ring_h:
        viol.append(f"轮毂盘判据红：z={z_hub:.2f}mm 处无贯通整环")
    if ring_m:
        viol.append(f"叶片中段判据红：z={z_mid:.2f}mm 处存在整圆环 ⇒ 实体是实心回转体冒充叶片流道")
    if n_m < max(3, int(p["Z_blades"]) // 2):
        viol.append(f"叶片中段离散岛数 {n_m} < max(3, Z/2)={max(3, int(p['Z_blades']) // 2)} ⇒ 叶片缺失")
    return {"z_shroud": round(z_shroud, 2), "z_hub": round(z_hub, 2), "z_mid": round(z_mid, 2),
            "shroud_ring": ring_s, "hub_ring": ring_h, "mid_ring": ring_m,
            "mid_islands": n_m, "violations": viol}


def render_mesh(mesh, png_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    tris = mesh.triangles
    if len(tris) > 25000:
        tris = tris[:: max(1, len(tris) // 25000)]
    b = mesh.bounds
    dims = b[1] - b[0]
    fig = plt.figure(figsize=(11, 5))
    for i, (elev, azim) in enumerate([(22, 45), (5, 0)]):
        ax = fig.add_subplot(1, 2, i + 1, projection="3d")
        ax.add_collection3d(Poly3DCollection(tris, facecolor="#8899aa", edgecolor="none", alpha=0.95))
        ax.set_xlim(b[0][0], b[1][0]); ax.set_ylim(b[0][1], b[1][1]); ax.set_zlim(b[0][2], b[1][2])
        ax.set_box_aspect(tuple(dims))
        ax.view_init(elev=elev, azim=azim)
        ax.set_title(f"view {i + 1} (elev={elev})")
    fig.tight_layout()
    fig.savefig(png_path, dpi=110)
    plt.close(fig)


def run_model_script(code, script_name, stage_tag, base_prompt, max_attempts=3):
    """执行模型代码；traceback 回喂反思；监考不改模型代码一字。"""
    script_path = PROJ / script_name
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": base_prompt}]
    last_code = ""
    for attempt in range(1, max_attempts + 1):
        resp = call_model(messages, f"{stage_tag}_attempt{attempt}", temperature=0.2)
        code = extract_code(resp)
        if not code.strip():
            fb = "未检测到 Python 代码块。请只输出一个完整可执行的 ```python 代码块。"
            messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": base_prompt},
                        {"role": "assistant", "content": resp[:6000]}, {"role": "user", "content": fb}]
            log("NO_CODE", {"stage": stage_tag, "attempt": attempt})
            continue
        last_code = code
        script_path.write_text(code, encoding="utf-8")
        try:
            proc = subprocess.run([VENV_PY, "-u", str(script_path)], cwd=str(PROJ),
                                  capture_output=True, text=True, timeout=420, encoding="utf-8", errors="replace")
            rc, out, err = proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired:
            rc, out, err = -1, "", "TIMEOUT after 420s"
        log("SCRIPT_EXEC", {"stage": stage_tag, "attempt": attempt, "rc": rc,
                            "stdout_tail": out[-400:], "stderr_tail": err[-400:]})
        (PROJ / f"{script_name}.attempt{attempt}.stdout.txt").write_text(out, encoding="utf-8")
        (PROJ / f"{script_name}.attempt{attempt}.stderr.txt").write_text(err, encoding="utf-8")
        if rc == 0:
            return True, out, code
        fb = (f"你的脚本执行失败（退出码 {rc}）。以下是真实 Traceback，请自主反思并纠正，"
              f"重新输出完整且能一次性正确运行的单一 ```python 代码块：\n```\n{err[-3500:]}\n```")
        messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": base_prompt},
                    {"role": "assistant", "content": f"```python\n{code}\n```"}, {"role": "user", "content": fb}]
    return False, "", last_code


def derive_a_prime(p_model):
    """A′ 接管：把单变量可反解约束（N/D2 反解、D1t/D1h 喉口反解、b2=比值×D2、
    claimed_* 复算派生）从模型决策域移交确定性求解器。

    模型仍保留真实设计自由度：Z_blades / beta2b_deg / eta_total / 期望 D2、N。
    判定权不下放——派生后的参数照样要过 ruler()，本函数不做任何合格判定。
    """
    try:
        import impeller_deterministic_solver as solver
    except Exception as e:
        return None, {"error": f"solver_import_{type(e).__name__}"}
    free = {}
    if isinstance(p_model, dict):
        for k in ("Z_blades", "beta2b_deg", "eta_total", "D2_mm", "N_rpm"):
            if isinstance(p_model.get(k), (int, float)):
                free[k] = p_model[k]
        if isinstance(p_model.get("D2_mm"), (int, float)) and p_model["D2_mm"] and \
                isinstance(p_model.get("b2_mm"), (int, float)):
            free["b2_ratio"] = p_model["b2_mm"] / p_model["D2_mm"]
    if MODE == "auto" and not free:
        free = {"Z_blades": 12, "beta2b_deg": 25.0, "eta_total": 0.85,
                "D2_mm": 220.0, "N_rpm": 40000.0}
    cands = solver.candidates(free)
    if not cands:
        return None, {"error": "求解器无可行候选", "free": free}
    best = min(cands, key=lambda c: c["n_viol"])
    meta = {"mode": MODE, "model_freedom": free, "policy": best["policy"],
            "candidates": [{"id": c["id"], "policy": c["policy"], "n_viol": c["n_viol"]} for c in cands],
            "solver_derived": ["N_rpm|D2_mm(反解π目标)", "D1t_mm/D1h_mm(反解喉口面积)",
                               "b2_mm(=比值×D2)", "axial_length_mm(可行区间中值)",
                               "bore_diameter_mm", "claimed_pressure_ratio/claimed_tip_speed_m_s/claimed_FOS(复算派生)"]}
    if best["n_viol"]:
        return None, dict(meta, violations=best["violations"][:8])
    return best["params"], meta


def engine_run(stage, prompt, script_name, stage_tag, p):
    """ENGINE=solver 时由确定性产出器接管该阶段，返回与原模型脚本同格式的 (ok, out, code)。"""
    if ENGINE != "solver":
        return run_model_script(code=None, script_name=script_name, stage_tag=stage_tag, base_prompt=prompt)
    import contextlib
    import io
    import impeller_stage_solver as iss
    log("ENGINE_SOLVER_TAKEOVER", {"stage": stage, "script": script_name})
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        if stage == "cad":
            iss.build_cad(p, PROJ)
        elif stage == "analysis":
            iss.build_analysis(p, ruler)
        else:
            iss.build_drawing(p, PROJ)
    out = buf.getvalue()
    print(out.strip())
    return True, out, None


def stage_a():
    log("STAGE_A_START", {"brief_sha256": hashlib.sha256(BRIEF.encode("utf-8")).hexdigest()[:16]})
    messages = [{"role": "system", "content": DESIGN_SYSTEM}, {"role": "user", "content": BRIEF}]
    payload_hashes = []
    last_parsed = None
    for attempt in range(1, 4):
        resp = call_model(messages, f"design_attempt{attempt}", num_predict=2000, temperature=0.4)
        h = hashlib.sha256(resp.encode("utf-8")).hexdigest()[:12]
        payload_hashes.append(h)
        p = extract_json(resp)
        if p is not None:
            last_parsed = p
        if p is None:
            vals, viol, adv = {}, ["未产出可解析 JSON 参数表"], []
        else:
            vals, viol, adv = ruler(p)
        log("STAGE_A_AUDIT", {"attempt": attempt, "resp_sha12": h, "values": vals,
                              "violations": viol, "advisory": adv})
        if p is not None and not viol:
            p["_audit"] = {"ruler_values": vals, "advisory": adv, "attempts": attempt,
                           "payload_hashes": payload_hashes}
            (PROJ / "params_frozen.json").write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")
            log("STAGE_A_PASS", {"params_sha256": hashlib.sha256(json.dumps(p, sort_keys=True).encode()).hexdigest()[:16]})
            return p
        if len(set(payload_hashes)) < len(payload_hashes):
            log("STUCK_REPETITION", {"hashes": payload_hashes})
        fb = ("独立审计尺子（由你的参数解析复算，不是建议答案）判红如下，请修改违规参数后重新输出完整 JSON 代码块：\n"
              + "\n".join(f"- {x}" for x in viol)
              + (f"\n复算参考量: {json.dumps(vals, ensure_ascii=False)}" if vals else ""))
        messages = [{"role": "system", "content": DESIGN_SYSTEM}, {"role": "user", "content": BRIEF},
                    {"role": "assistant", "content": resp[:6000]}, {"role": "user", "content": fb}]
    log("STAGE_A_FAIL", {"attempts": 3})
    if MODE in ("assist", "auto"):
        p_solved, meta = derive_a_prime(last_parsed or {})
        if p_solved is not None:
            vals, viol, adv = ruler(p_solved)
            log("STAGE_A_APRIME", {"mode": MODE, "meta": meta, "values": vals, "violations": viol})
            p_solved["_audit"] = {"ruler_values": vals, "advisory": adv, "attempts": "A'",
                                  "payload_hashes": payload_hashes, "derivation": meta}
            (PROJ / "params_frozen.json").write_text(
                json.dumps(p_solved, ensure_ascii=False, indent=2), encoding="utf-8")
            return p_solved
        log("STAGE_A_APRIME_FAIL", {"meta": meta})
    return None


def stage_b(p):
    frozen = {k: p[k] for k in REQUIRED_FIELDS}
    prompt = f"""以下是你已冻结的设计参数（审计已通过，不得改动）：
```json
{json.dumps(frozen, ensure_ascii=False, indent=2)}
```
请用 build123d 写一个完整可执行的 Python 脚本，建立该【封闭式离心叶轮】三维实体，坐标系 Z 轴为旋转轴，底面 z=0：
1. 轮毂盘：直径 D2_mm、厚 hub_disk_thickness_mm 的底盘 + 进口轮毂回转体（D1h 到 D1t 诱导轮轮廓）。
2. Z_blades 片后弯叶片：从进口 D1 到出口 D2 的曲线叶片（出口角 beta2b_deg 相对径向后弯），叶片厚 blade_thickness_mm，沿圆周均布。严禁用直 Box 冒充曲线叶片。
3. 完整盖盘(shroud)：厚 shroud_thickness_mm，覆盖全部叶顶并延伸到 D2，与叶片顶部融合成封闭流道。总轴向高度 axial_length_mm。
4. 中心孔 bore_diameter_mm 贯通，叶根圆角 fillet_root_mm（若圆角特征失败可保留锐根但须在打印中注明）。
5. export_step 保存 impeller_closed.step，export_stl 保存 impeller_closed.stl（当前目录）。
6. 打印一行：[CAD_COMPLETE] Volume: <体积mm3> mm3 Mass: <质量g> g （质量=体积×4.43e-3 g/mm3）。
只输出一个 ```python 代码块，禁止正文。"""
    ok, out, code = engine_run("cad", prompt, "make_closed_impeller.py", "cad", p)
    if not ok:
        return {"pass": False, "reason": "CAD 脚本三次尝试均未执行成功"}
    import trimesh
    stl = PROJ / "impeller_closed.stl"
    step = PROJ / "impeller_closed.step"
    if not stl.exists() or not step.exists() or stl.stat().st_size < 10000:
        return {"pass": False, "reason": "脚本退出码 0 但 STEP/STL 产物缺失或过小（空产物判红）"}
    mesh = trimesh.load(str(stl))
    vol = float(mesh.volume)
    R = p["D2_mm"] / 2.0
    L = p["axial_length_mm"]
    b = mesh.bounds
    xy_ok = bool(abs(float(b[1][0] - b[0][0]) - p["D2_mm"]) / p["D2_mm"] < 0.06)
    z_ok = bool(abs(float(b[1][2] - b[0][2]) - L) / L < 0.20)
    frac = float(vol / (math.pi * R * R * L))
    topo = topology_audit(mesh, p)
    m_vol = re.search(r"Volume:\s*([\d.]+)", out)
    m_mass = re.search(r"Mass:\s*([\d.]+)", out)
    claim_vol = float(m_vol.group(1)) if m_vol else None
    claim_mass = float(m_mass.group(1)) if m_mass else None
    mass_true = vol * 4.43e-3
    fab = []
    if claim_vol is not None and abs(claim_vol - vol) / vol > 0.03:
        fab.append(f"宣称体积 {claim_vol} 与 STL 实测 {vol:.1f} 偏差 >3%")
    if claim_mass is not None and abs(claim_mass - mass_true) / mass_true > 0.03:
        fab.append(f"宣称质量 {claim_mass} g 与 ρV={mass_true:.1f} g 偏差 >3%")
    render_mesh(mesh, str(PROJ / "cad_render.png"))
    res = {"pass": not topo["violations"] and not fab and xy_ok and z_ok and 0.12 < frac < 0.85,
           "volume_mm3": round(vol, 2), "mass_g": round(mass_true, 2), "watertight": bool(mesh.is_watertight),
           "envelope_xy_ok": xy_ok, "envelope_z_ok": z_ok, "envelope_fraction": round(frac, 4),
           "topology": topo, "fabrication": fab, "claimed_volume": claim_vol, "claimed_mass": claim_mass}
    (PROJ / "cad_audit.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    log("STAGE_B_AUDIT", res)
    return res


def stage_c(p):
    frozen = {k: p[k] for k in REQUIRED_FIELDS}
    prompt = f"""以下是你已冻结的设计参数：
```json
{json.dumps(frozen, ensure_ascii=False, indent=2)}
```
空气物性：cp=1004.5 J/(kg·K), γ=1.4, R=287.05 J/(kg·K)；进口总温 288.15 K、总压 101325 Pa；流量 2.0 kg/s。
材料 Ti-6Al-4V：ρ=4430 kg/m³，屈服 880 MPa，ν=0.34。
请写完整可执行 Python 脚本 performance_strength.py，独立计算并打印一个 JSON（用 [ANALYSIS_COMPLETE] 标记行包裹）：
u2_m_s（叶尖速度）, slip_sigma（Wiesner 滑移系数）, pressure_ratio（Euler 功+迭代出口密度得到的总压比）, M_rel_tip（进口叶顶相对马赫数，迭代进口密度）, max_stress_mpa（旋转盘+叶片离心等效应力，注明方法）, FOS（880/max_stress）。
所有数值必须由参数真实算出，禁止硬编码结果。只输出一个 ```python 代码块。"""
    ok, out, code = engine_run("analysis", prompt, "performance_strength.py", "analysis", p)
    if not ok:
        return {"pass": False, "reason": "分析脚本三次尝试均未执行成功"}
    m = re.search(r"\[ANALYSIS_COMPLETE\]\s*(\{[^\n]*\})", out)
    if not m:
        m = re.search(r"\[ANALYSIS_COMPLETE\]\s*(\{.*?\})", out, re.DOTALL)
    if not m:
        m = re.search(r"(\{[^{}]*\"FOS\"[^{}]*\})", out, re.DOTALL)
    if not m:
        return {"pass": False, "reason": "脚本执行成功但未产出可解析 JSON 结果（空产物判红）"}
    try:
        got = json.loads(m.group(1))
    except Exception as e:
        return {"pass": False, "reason": f"结果 JSON 解析失败: {e}"}
    vals, _, _ = ruler(p)
    checks = []
    def cmp(name, claim, ref, tol):
        if name not in got or not isinstance(got[name], (int, float)):
            checks.append(f"缺字段 {name}")
            return
        dev = abs(got[name] - ref) / abs(ref)
        if dev > tol:
            checks.append(f"{name}: 模型算 {got[name]} vs 独立尺子 {ref} 偏差 {dev * 100:.1f}% > {tol * 100:.0f}%")
    cmp("u2_m_s", got.get("u2_m_s"), vals["u2_m_s"], 0.01)
    cmp("pressure_ratio", got.get("pressure_ratio"), vals["pressure_ratio_recomputed"], 0.08)
    cmp("M_rel_tip", got.get("M_rel_tip"), vals["M_rel_tip"], 0.10)
    cmp("FOS", got.get("FOS"), vals["FOS_recomputed"], 0.25)
    if isinstance(got.get("FOS"), (int, float)) and got["FOS"] > vals["FOS_recomputed"] * 1.15:
        checks.append("FOS 安全过宣称 >15%")
    res = {"pass": not checks, "model_result": got, "ruler_values": vals, "discrepancies": checks}
    (PROJ / "analysis_audit.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    log("STAGE_C_AUDIT", res)
    return res


def stage_d(p):
    prompt = f"""已冻结参数：D2={p['D2_mm']}mm, D1t={p['D1t_mm']}mm, D1h={p['D1h_mm']}mm, bore={p['bore_diameter_mm']}mm, Z={p['Z_blades']}, 轴向长={p['axial_length_mm']}mm, 盖盘厚={p['shroud_thickness_mm']}mm, 轮毂盘厚={p['hub_disk_thickness_mm']}mm, 材料 Ti-6Al-4V。
请用 ezdxf 写完整可执行 Python 脚本 make_2d_drawing.py，生成封闭式叶轮二维工程图 impeller_closed_2d.dxf：
1. 主视图：同心圆 D2/D1t/D1h/bore + Z 片后弯叶片曲线投影（样条或圆弧，非直线辐条）。
2. 轴向剖视图：必须画出轮毂盘、叶片、盖盘三层封闭结构（盖盘为覆盖全宽的封闭上盘）。
3. 标准图层 OUTLINE/CENTER/HIDDEN/DIM/TITLE_BLOCK；中心线用 CENTER 层。
4. 至少标注 D2、D1t、bore、轴向长四个尺寸（DIMENSION 实体）。
5. 标题栏文字含 CLOSED IMPELLER 与 Ti-6Al-4V。
6. 打印 [DRAWING_COMPLETE] 与实体总数。只输出一个 ```python 代码块。"""
    ok, out, code = engine_run("drawing", prompt, "make_2d_drawing.py", "drawing", p)
    if not ok:
        return {"pass": False, "reason": "制图脚本三次尝试均未执行成功"}
    import ezdxf
    dxf_path = PROJ / "impeller_closed_2d.dxf"
    if not dxf_path.exists():
        return {"pass": False, "reason": "DXF 产物缺失"}
    try:
        doc = ezdxf.readfile(str(dxf_path))
    except Exception as e:
        return {"pass": False, "reason": f"DXF 解析失败: {e}"}
    msp = doc.modelspace()
    ents = list(msp)
    layers = {e.dxf.layer for e in ents}
    circles = sum(1 for e in ents if e.dxftype() == "CIRCLE")
    dims = sum(1 for e in ents if e.dxftype() == "DIMENSION")
    splines = sum(1 for e in ents if e.dxftype() in ("SPLINE", "ARC", "LWPOLYLINE", "POLYLINE"))
    need_layers = {"OUTLINE", "CENTER", "DIM", "TITLE_BLOCK"}
    checks = []
    if not need_layers.issubset(layers):
        checks.append(f"缺标准图层: {need_layers - layers}")
    # 同心圆期望数：D2/D1t/D1h 三圆恒定存在，bore>0 时才有第四个孔圆。
    # bore=0 表示整体转子无中心通孔，此时要求 4 个圆等于逼迫画零半径退化圆。
    need_circles = 4 if p["bore_diameter_mm"] > 0 else 3
    if circles < need_circles:
        checks.append(f"CIRCLE 数 {circles} < {need_circles}（bore={p['bore_diameter_mm']:g}）")
    if dims < 4:
        checks.append(f"DIMENSION 数 {dims} < 4")
    if splines < p["Z_blades"]:
        checks.append(f"曲线实体数 {splines} < Z={p['Z_blades']}（叶片投影疑似直线辐条）")
    if len(ents) < 30:
        checks.append(f"总实体 {len(ents)} < 30")
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from ezdxf.addons.drawing import RenderContext, Frontend
        from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
        fig = plt.figure(figsize=(12, 8))
        ax = fig.add_axes([0, 0, 1, 1])
        ctx = RenderContext(doc)
        out_backend = MatplotlibBackend(ax)
        Frontend(ctx, out_backend).draw_layout(msp, finalize=True)
        fig.savefig(str(PROJ / "drawing_render.png"), dpi=120)
        plt.close(fig)
    except Exception as e:
        log("DRAWING_RENDER_WARN", {"error": str(e)})
    res = {"pass": not checks, "entities": len(ents), "layers": sorted(layers),
           "circles": circles, "dimensions": dims, "curve_entities": splines, "checks": checks}
    (PROJ / "drawing_audit.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    log("STAGE_D_AUDIT", res)
    return res


def selftest():
    """反证自测：植入坏样本，封闭拓扑闸与尺子闸必须红。"""
    import numpy as np
    import trimesh
    R, hub, shroud, axial, Z = 60.0, 10.0, 3.0, 45.0, 6
    p = {"D2_mm": 2 * R, "hub_disk_thickness_mm": hub, "shroud_thickness_mm": shroud,
         "axial_length_mm": axial, "Z_blades": Z}
    hub_m = trimesh.creation.cylinder(radius=R, height=hub, sections=96)
    hub_m.apply_translation([0, 0, hub / 2])
    shroud_m = trimesh.creation.cylinder(radius=R, height=shroud, sections=96)
    shroud_m.apply_translation([0, 0, axial - shroud / 2])
    blades = []
    for i in range(Z):
        bx = trimesh.creation.box(extents=[40, 2.5, axial - hub - shroud])
        ang = i * 2 * math.pi / Z
        bx.apply_translation([35 * math.cos(ang), 35 * math.sin(ang), hub + (axial - hub - shroud) / 2])
        blades.append(bx)
    closed = trimesh.util.concatenate([hub_m, shroud_m] + blades)
    semi = trimesh.util.concatenate([hub_m] + blades)
    solid = trimesh.creation.cylinder(radius=R, height=axial, sections=96)
    solid.apply_translation([0, 0, axial / 2])
    t_closed = topology_audit(closed, p)
    t_semi = topology_audit(semi, p)
    t_solid = topology_audit(solid, p)
    assert not t_closed["violations"], f"自测失败：真封闭样本被判红 {t_closed}"
    assert t_semi["violations"], "自测失败：半开式坏样本未被判红（闸空转）"
    assert t_solid["violations"], "自测失败：实心回转体坏样本未被判红（闸空转）"
    good = {"D2_mm": 200, "N_rpm": 48000, "Z_blades": 12, "beta2b_deg": 25, "b2_mm": 14,
            "D1t_mm": 130, "D1h_mm": 55, "axial_length_mm": 70, "shroud_thickness_mm": 2.0,
            "blade_thickness_mm": 1.5, "hub_disk_thickness_mm": 12, "bore_diameter_mm": 30,
            "fillet_root_mm": 1.5, "eta_total": 0.80, "claimed_pressure_ratio": 4.0,
            "claimed_tip_speed_m_s": 502.65, "claimed_FOS": 1.56}
    vals0, _, _ = ruler(good)
    good["claimed_pressure_ratio"] = vals0["pressure_ratio_recomputed"]
    good["claimed_tip_speed_m_s"] = vals0["u2_m_s"]
    good["claimed_FOS"] = vals0["FOS_recomputed"]
    vals, viol, adv = ruler(good)
    assert not viol, f"自测失败：自洽好样本被尺子判红 {viol} vals={vals}"
    bad = dict(good, D1t_mm=250)
    _, viol2, _ = ruler(bad)
    assert viol2, "自测失败：直径序坏样本未被尺子判红"
    bad2 = dict(good, N_rpm=70000)
    _, viol3, _ = ruler(bad2)
    assert viol3, "自测失败：超速坏样本未被尺子判红"
    # ---- bore=0（实心盘/整体转子）口径的反证自测：既要能绿，也要守住放水口子 ----
    solid_hub = dict(good, bore_diameter_mm=0)
    vals_s, viol_s, adv_s = ruler(solid_hub)
    assert not viol_s, f"自测失败：bore=0 实心盘样本被误判红 {viol_s}"
    assert any("实心盘" in a for a in adv_s), f"自测失败：bore=0 未切到实心盘口径 {adv_s}"
    cheat = dict(solid_hub, claimed_FOS=vals_s["FOS_recomputed"] * 1.20)
    _, viol_c, _ = ruler(cheat)
    assert viol_c, "自测失败：bore=0 且 FOS 过宣称 20% 未判红（bore=0 被当放水口子）"
    neg = dict(good, bore_diameter_mm=-5)
    _, viol_n, _ = ruler(neg)
    assert viol_n, "自测失败：负 bore 未被判红"
    over = dict(good, bore_diameter_mm=90)
    _, viol_o, _ = ruler(over)
    assert viol_o, "自测失败：bore>=D1h 的直径序坏样本未被判红"
    print("[SELFTEST PASS] 封闭拓扑闸: 封闭=绿/半开=红/实心=红；"
          "尺子闸: 好=绿/直径序坏=红/超速坏=红/bore=0实心盘=绿/bore=0过宣称=红/负bore=红/bore>=D1h=红")
    print(json.dumps({"good_sample_ruler": vals}, ensure_ascii=False))


def main():
    import argparse
    global PROJ, LOCK, DESIGN_SYSTEM, MODEL, WEIGHT_DIGEST, MODE, ENGINE
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--contract", action="store_true", help="注入叶轮修复契约")
    ap.add_argument("--fewshot", type=int, default=0, help="注入掩码修复少样本条数")
    ap.add_argument("--arm", default="", help="臂名，隔离产物目录与锁")
    ap.add_argument("--model", default=MODEL, help="被测 Ollama 标签（缺省 virtu-ties-v1）")
    ap.add_argument("--mode", default="bare", choices=["bare", "assist", "auto"],
                    help="bare=模型全权(现状)；assist=保留模型自由度、单变量约束由A'求解器反解；auto=求解器自主")
    ap.add_argument("--engine", default="model", choices=["model", "solver"],
                    help="model=模型写脚本；solver=确定性产出器接管 CAD/复算/制图（接管事实写入报告，不冒充模型自主）")
    ap.add_argument("--params", default=None,
                    help="直接读入已冻结参数 JSON（跳过 stage_a 模型设计），用于引擎隔离验证")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return
    MODEL = args.model
    MODE = args.mode
    ENGINE = args.engine
    if args.arm:
        PROJ = ROOT / "projects" / f"impeller_closed_v1_{args.arm}"
        LOCK = ROOT / "runs" / f"closed_impeller_{args.arm}.chain.lock"
    if args.contract:
        DESIGN_SYSTEM = DESIGN_SYSTEM + "\n\n" + impeller_iface.IMPELLER_REPAIR_CONTRACT
    if args.fewshot:
        recs = [json.loads(l) for l in open(ROOT / "data" / "impeller_repair_demos.jsonl", encoding="utf-8")]
        DESIGN_SYSTEM = DESIGN_SYSTEM + "\n\n" + impeller_iface.render_fewshot(recs, args.fewshot)
    PROJ.mkdir(parents=True, exist_ok=True)
    if LOCK.exists():
        age = time.time() - LOCK.stat().st_mtime
        if age < 1800:
            print(f"[ABORT] 锁未过期 ({age:.0f}s): {LOCK.read_text()}")
            sys.exit(2)
    LOCK.write_text(json.dumps({"pid": os.getpid(), "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}))
    try:
        try:
            tags = json.loads(urllib.request.urlopen(OLLAMA + "/api/tags", timeout=10).read())
            names = [m["name"] for m in tags["models"]]
            assert MODEL in names, f"标签缺失: {MODEL}"
            WEIGHT_DIGEST = weight_digest_of(MODEL)
        except Exception as e:
            if ENGINE != "solver":
                raise
            # ENGINE=solver 是确定性产出器路径：设计参数来自冻结文件，B/C/D 三阶段不调用被测权重。
            # 模型服务不可达不应阻塞复算/建模/制图，但身份摘要必须显式标为未解析，绝不伪造摘要。
            WEIGHT_DIGEST = f"UNRESOLVED:solver_engine_{type(e).__name__}"
            log("MODEL_UNAVAILABLE", {"error": str(e), "engine": ENGINE,
                                      "note": "solver 引擎不依赖模型权重；身份摘要标记未解析，报告不得引用该字段作身份凭证"})
        log("IDENTITY", {"model": MODEL, "weight_layer_digest": WEIGHT_DIGEST, "port": 11435,
                         "arm": args.arm or "bare", "contract": args.contract, "fewshot": args.fewshot,
                         "note": "摘要由 ollama show --modelfile 的 FROM 落盘权重实测 sha256 派生，"
                                 "不再继承任何硬编码常量"})
        params_source = "model_stage_a"
        if args.params:
            pf = Path(args.params)
            p = json.loads(pf.read_text(encoding="utf-8"))
            p["_audit"] = {"derivation": [{"source": "frozen_params_file", "path": str(pf),
                                           "note": "参数来自已冻结文件，stage_a 模型设计环节被显式跳过"}]}
            params_source = f"frozen_file:{pf.name}"
            log("PARAMS_LOADED", {"path": str(pf), "mode": MODE})
        else:
            p = stage_a()
        report = {"task": "closed aero-engine impeller design", "model": MODEL, "mode": MODE,
                  "engine": ENGINE, "params_source": params_source,
                  "weight_digest": WEIGHT_DIGEST, "n": 1, "basis_legend": {
                      "ruler": "analytic_recomputed(inferred)", "topology": "measured_from_stl",
                      "claims": "asserted_by_model"}, "stages": {}}
        if p is None:
            report["verdict"] = "FAIL"
            report["reason"] = ("参数设计三轮未通过独立尺子"
                                + ("（A′ 接管后仍无 0 违规候选）" if MODE != "bare" else ""))
        else:
            report["params"] = {k: p[k] for k in REQUIRED_FIELDS}
            if p.get("_audit", {}).get("derivation"):
                report["derivation"] = p["_audit"]["derivation"]
            report["stages"]["B_cad"] = stage_b(p)
            report["stages"]["C_analysis"] = stage_c(p)
            report["stages"]["D_drawing"] = stage_d(p)
            hard = [report["stages"]["B_cad"].get("pass"), report["stages"]["C_analysis"].get("pass"),
                    report["stages"]["D_drawing"].get("pass")]
            report["verdict"] = "PASS" if all(hard) else "FAIL"
        report["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        rp = PROJ / "VERIFICATION_REPORT.json"
        rp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        seal = {"report_sha256": hashlib.sha256(rp.read_bytes()).hexdigest(), "artifacts": {}}
        for f in sorted(PROJ.iterdir()):
            if f.is_file() and f.name != "FINAL_SEAL.json" and f.suffix in (".json", ".step", ".stl", ".dxf", ".png", ".py", ".jsonl"):
                seal["artifacts"][f.name] = hashlib.sha256(f.read_bytes()).hexdigest()
        (PROJ / "FINAL_SEAL.json").write_text(json.dumps(seal, indent=2), encoding="utf-8")
        print("\n" + "=" * 60)
        print(f"[FINAL VERDICT] {report['verdict']}")
        print(json.dumps(report.get("stages", {}), ensure_ascii=False)[:1500])
    finally:
        if LOCK.exists():
            LOCK.unlink()


if __name__ == "__main__":
    main()