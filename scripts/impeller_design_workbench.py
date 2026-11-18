# -*- coding: utf-8 -*-
"""叶轮自主设计工作台（推理期修复：不重训、不改尺子）。

口径分账：
  - 模型负责全部设计决策（几何量级、转速、叶片数、出口角、流道宽、进口尺寸、效率假设）。
  - 系统只做确定性三件事：算式求值（消除算术缺陷）、物理复算回喂（复用尺子独立复核）、
    格式归一与字段拼装（消除 JSON 损坏 / 单位字符串缺陷）。
  - 验收仍由 closed_impeller_proctor.ruler 判定，本工作台不参与判分。

反复读机制：连续两次参数指纹相同 -> 进入 field-patch 模式，只要求模型给 1~2 个违规字段新值。

用法：
  python impeller_design_workbench.py --model virtu-ties-v1:latest --rounds 10
"""
import argparse
import hashlib
import json
import math
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import closed_impeller_proctor as cp  # noqa: E402
import impeller_deterministic_solver as solver  # noqa: E402

DEFAULT_HOST = "http://127.0.0.1:11434"
OUT_BASE = ROOT / "projects" / "impeller_workbench_v1"

SAFE = {k: getattr(math, k) for k in ("pi", "sqrt", "sin", "cos", "tan", "radians", "degrees",
                                      "atan", "asin", "acos", "exp", "log", "log10", "hypot")}
SAFE.update({"abs": abs, "min": min, "max": max, "round": round})

METHOD_CARD = """【工程方法参考｜教科书口径，不含任何验收阈值或目标解】
- 叶尖速度定义：u2 = π·D2(mm)·N(rpm)/60000，单位 m/s。这是唯一正确的叶尖速定义。
- 压比与温升：T02/T01 = π_c^((γ-1)/γ)，γ=1.4；等熵温升 ΔT0s = T01·(π_c^((γ-1)/γ) − 1)。
- 实际温升：ΔT0 = ΔT0s / η_total。
- Euler 透平方程：ΔT0 = u2·cu2/cp，cp=1004.5 J/(kg·K)，cu2 = σ·(u2 − cm2·tanβ2b)。
- Wiesner 滑移：σ = 1 − sqrt(cosβ2b)/Z^0.7；出口径向分速 cm2 通常取 0.2~0.3·u2 量级。
- 由上面两条可反解必需叶尖速：
    u2 ≈ sqrt( cp·T01·(π_c^((γ-1)/γ) − 1) / ( η_total·σ·(1 − (cm2/u2)·tanβ2b) ) )
  给定目标压比先估出 u2 量级，再由 u2 = π·D2·N/60000 分配 D2 与 N（N 越高 D2 越小）。
- 质量连续：mdot = ρ1·A1·ca1 = ρ2·A2·cm2，A2 = π·D2·b2·(1 − 叶片阻塞率)。
  所以 b2 由 mdot、出口密度、cm2 决定；b2 过小必然流量/面积失配，压比无法复算。
- 进口喉口：A1 = π·(D1t² − D1h²)/4 ×(1−阻塞)，ca1 = mdot/(ρ1·A1)，
  u1t = π·D1t·N/60000，W1 = sqrt(ca1² + u1t²)，M_rel = W1/sqrt(γ·R·T1)。
- 旋转盘应力：σ_eq ≈ (3+ν)/8·ρ·u2²·K_blade（Pa），FOS = σ_y/σ_eq。
- 算术不要心算：任何乘除幂都交给 {"action":"calc","expr":"..."} 求值后填入。
【交互协议】每轮只输出一个 JSON，四选一：
  {"action":"calc","expr":"表达式，可用 pi/sqrt/tan/radians 等"}
  {"action":"check","params":{全部必填字段，值为纯数字}}
  {"action":"final","params":{同上}}
  {"action":"patch","patch":{"字段名":数值,...},"reason":"修正理由"}
"""

FIELDS = cp.REQUIRED_FIELDS
NUM_RE = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def http_json(url, payload, timeout=900):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def chat(host, model, messages, npred=1400, temp=0.2):
    t0 = time.time()
    res = http_json(host + "/api/chat", {
        "model": model, "messages": messages, "stream": False,
        "options": {"temperature": temp, "num_predict": npred, "num_ctx": 8192},
    })
    txt = res.get("message", {}).get("content", "")
    return txt, round(time.time() - t0, 1), res.get("eval_count")


def safe_eval(expr):
    if not isinstance(expr, str) or not expr.strip() or len(expr) > 300:
        return {"error": "expr 非法或过长"}
    if not re.fullmatch(r"[0-9A-Za-z_\.\+\-\*/\(\)\,\s]*", expr):
        return {"error": "expr 含非法字符"}
    names = set(re.findall(r"[A-Za-z_][A-Za-z_0-9]*", expr))
    bad = [n for n in names if n not in SAFE]
    if bad:
        return {"error": f"未知记号 {bad}"}
    try:
        val = eval(expr, {"__builtins__": {}}, dict(SAFE))  # noqa: S307 受限词汇表
    except Exception as e:  # noqa: BLE001
        return {"error": f"{type(e).__name__}: {e}"}
    return {"value": round(val, 6) if isinstance(val, float) else val}


def normalize(params):
    """把 '120 mm' / 1.2e3 之类统一成 float，剔除布尔与非数值。"""
    out = {}
    for k, v in (params or {}).items():
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)):
            out[k] = float(v)
        elif isinstance(v, str):
            m = NUM_RE.search(v)
            if m:
                out[k] = float(m.group())
    return out


def fingerprint(p):
    return hashlib.sha256(json.dumps({k: round(float(p.get(k, 0)), 4) for k in FIELDS},
                                     sort_keys=True).encode()).hexdigest()[:10]


def phys_view(p):
    vals, viol, adv = cp.ruler(p)
    vv = vals if isinstance(vals, dict) else {}
    keys = ["u2_m_s", "pressure_ratio_recomputed", "FOS_recomputed", "M_rel_tip",
            "sigma_eq_MPa", "cm2_m_s", "ca1_m_s", "T02_K", "dh0_kJ_kg", "Ns"]
    return {"recomputed": {k: vv.get(k) for k in keys if k in vv and vv.get(k) is not None},
            "violations": viol, "advisory": adv[:2]}


def core(p):
    return {k: p.get(k) for k in ("D2_mm", "N_rpm", "Z_blades", "beta2b_deg", "b2_mm", "D1t_mm",
                                  "D1h_mm", "axial_length_mm", "claimed_tip_speed_m_s",
                                  "claimed_pressure_ratio", "claimed_FOS")}


def viol_fields(viol):
    hit = []

    def _add(*ks):
        for k in ks:
            if k in FIELDS and k not in hit:
                hit.append(k)

    for v in viol:
        if "轴向长" in v:
            _add("axial_length_mm")
        elif "出口流道宽比" in v or "b2/D2" in v:
            _add("b2_mm", "D2_mm")
        elif "进口叶顶径比" in v or "D1t/D2" in v:
            _add("D1t_mm", "D2_mm")
        elif "直径序" in v:
            _add("D1t_mm", "D1h_mm", "bore_diameter_mm", "D2_mm")
        elif "叶片数" in v:
            _add("Z_blades")
        elif "出口后弯角" in v or "beta2b" in v:
            _add("beta2b_deg")
        elif "总效率" in v or "eta=" in v:
            _add("eta_total")
        elif "叶片厚" in v:
            _add("blade_thickness_mm")
        elif "盖盘厚" in v:
            _add("shroud_thickness_mm")
        elif "叶根圆角" in v:
            _add("fillet_root_mm")
        elif "宣称叶尖速" in v:
            _add("claimed_tip_speed_m_s")
        elif "宣称压比" in v:
            _add("claimed_pressure_ratio")
        elif "宣称 FOS" in v:
            _add("claimed_FOS")
        elif "复算总压比" in v or "叶尖速度 u2=" in v or "复算 FOS=" in v:
            _add("D2_mm", "N_rpm", "beta2b_deg")
        elif "相对马赫数" in v or "进口阻塞" in v:
            _add("D1t_mm", "D1h_mm", "N_rpm")
        elif "出口迭代非物理" in v:
            _add("b2_mm", "D2_mm")
        elif "通道净宽" in v:
            _add("Z_blades", "D1t_mm", "blade_thickness_mm")

    blob = " ".join(viol)
    for k in FIELDS:
        if k in blob:
            _add(k)
    alias = {"轴向长": "axial_length_mm", "b2": "b2_mm", "D1t": "D1t_mm", "D1h": "D1h_mm",
             "bore": "bore_diameter_mm", "D2": "D2_mm", "叶尖速": "claimed_tip_speed_m_s",
             "压比": "claimed_pressure_ratio", "FOS": "claimed_FOS", "效率": "eta_total",
             "转速": "N_rpm", "叶片数": "Z_blades", "出口角": "beta2b_deg"}
    for a, k in alias.items():
        if a in blob:
            _add(k)
    return hit[:4]


def interval_hints(viol, p=None):
    """从违规文本里抠出 [lo,hi] 区间约束，绑定到可修复字段（比例约束自动按 D2_mm 换算为 mm）。"""
    hints = []
    d2 = float((p or {}).get("D2_mm") or 0.0) if isinstance(p, dict) else 0.0
    for v in viol:
        if "相对马赫数" in v or "M_rel" in v:
            continue
        if "b2/D2" in v or "出口流道宽比" in v:
            if d2 >= 60.0:
                hints.append({
                    "field": "b2_mm",
                    "lo": round(0.02 * d2, 2),
                    "hi": round(0.10 * d2, 2),
                    "text": v,
                })
            continue
        if "D1t/D2" in v or "进口叶顶径比" in v:
            if d2 >= 60.0:
                hints.append({
                    "field": "D1t_mm",
                    "lo": round(0.40 * d2, 2),
                    "hi": round(0.85 * d2, 2),
                    "text": v,
                })
            continue
        flds = viol_fields([v])
        if not flds:
            continue
        for m in re.finditer(r"\[\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*\]", v):
            lo, hi = float(m.group(1)), float(m.group(2))
            if hi > lo:
                hints.append({"field": flds[0], "lo": lo, "hi": hi, "text": v})
    return hints


def build_patch_prompt(p, viol):
    fields = []
    for k in FIELDS:
        fields.append(f"  {k} = {p.get(k)}")
    cands = viol_fields(viol)
    ih = interval_hints(viol, p)
    head = ("你上两轮给出的是同一组参数，复算结果没有变化，说明你没有落实修正。现在只做字段级修正。\n"
            "当前参数：\n" + "\n".join(fields) +
            "\n\n仍存在的违规：\n" + "\n".join(f"- {x}" for x in viol))
    if cands:
        head += ("\n\n本轮只允许修改这几个字段中的 1 个：" + ", ".join(cands) +
                 "。必须是能消除上面违规的那个字段，值要跨量级地改（不是 ±10% 的微调）。")
    if ih:
        head += ("\n\n【强制区间】下列字段有硬区间，越界就是不合格，必须把值放进区间内：\n" +
                 "\n".join(f"- {h['field']} 必须在 [{h['lo']}, {h['hi']}]，当前 {p.get(h['field'])}"
                           for h in ih))
    return (head + "\n\n只输出 {\"action\":\"patch\",\"patch\":{...},\"reason\":\"...\"}，"
            "patch 里只放你要改的字段，值必须是数字。不要重复输出完整参数表。")


STEP1 = ("【流程强制·第 1 步】你还没有做过任何 calc。不要直接猜参数。\n"
         "先用 calc 反解达到 π_c 目标所需的叶尖速量级，例如：\n"
         '{"action":"calc","expr":"sqrt(1004.5*288.15*((4.0)**(0.2857)-1)/(0.88*0.9))"}\n'
         "（把 0.88 换成你假设的 η_total，0.9 换成你假设的 σ·(1-(cm2/u2)·tanβ2b) 项），"
         "得到 u2 后，再自己选定 N_rpm 并用 calc 反解 D2_mm=u2*60000/(pi*N)。"
         "只输出一个 calc 动作。")


def robust_json(text):
    """从任意自由文本里抠出第一个含 action 的 JSON 对象。"""
    if not text:
        return None
    obj = cp.extract_json(text)
    if isinstance(obj, dict) and "action" in obj:
        return obj
    t = re.sub(r"```(?:json)?", "", str(text))
    for m in re.finditer(r"\{", t):
        depth = 0
        for i in range(m.start(), len(t)):
            if t[i] == "{":
                depth += 1
            elif t[i] == "}":
                depth -= 1
                if depth == 0:
                    cand = t[m.start():i + 1]
                    for fix in (cand, cand.replace("'", '"'),
                                re.sub(r",\s*([}\]])", r"\1", cand.replace("'", '"'))):
                        try:
                            o = json.loads(fix)
                        except Exception:
                            continue
                        if isinstance(o, dict) and "action" in o:
                            return o
                    break
    return None


def run(model, rounds, host, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    system = cp.SYSTEM + "\n" + METHOD_CARD
    msgs = [{"role": "system", "content": system},
            {"role": "user", "content": cp.BRIEF +
             "\n\n【严格执行顺序】\n"
             "第 1 步（本轮）：不要让猜参数量级。先用 calc 求达到 π_c 目标所需的叶尖速，只输出：\n"
             '{"action":"calc","expr":"sqrt(1004.5*288.15*((pi_req)**(0.2857)-1)/(eta*(sigma_term)))"}\n'
             "把 pi_req 换成客户要求的压比数值，eta 换成你假设的总效率，sigma_term 换成你假设的"
             "滑移与子午速修正系数乘积，数值自己定。\n"
             "第 2 步：拿到 u2 后自己选定 N_rpm，用 calc 反解 D2_mm=u2*60000/(pi*N)。\n"
             "第 3 步：给出完整 17 字段，格式 "
             '{"action":"check","params":{' + ",".join(f'"{k}":数值' for k in FIELDS) + "}}\n"
             "params 必须是纯数字，不要写单位、不要写解释。全场每轮只输出一个 JSON。"}]
    trace, p, prev_fp, best, t_start = [], {}, None, None, time.time()
    stall = 0
    did_calc = False
    step1_done = False
    calc_log = []

    for r in range(1, rounds + 1):
        try:
            content, dt, ev = chat(host, model, msgs)
        except Exception as e:  # noqa: BLE001
            trace.append({"round": r, "error": f"{type(e).__name__}: {e}"})
            log(f"round {r} 调用失败: {e}")
            break
        obj = robust_json(content)
        rec = {"round": r, "elapsed_s": dt, "eval_count": ev}

        if not isinstance(obj, dict) or "action" not in obj:
            rec.update({"parse": False, "head": content[:240]})
            trace.append(rec)
            log(f"round {r} 无法解析动作（{dt}s）")
            msgs.append({"role": "assistant", "content": content[:1200]})
            msgs.append({"role": "user", "content":
                         '只输出一个 JSON 动作，例如 {"action":"check","params":{...}}，不要写解释文字。'})
            continue

        action = str(obj.get("action", "")).lower()
        rec["action"] = action

        if action == "calc":
            res = safe_eval(obj.get("expr", ""))
            rec.update({"expr": obj.get("expr"), "result": res})
            trace.append(rec)
            did_calc = True
            if isinstance(res, dict) and isinstance(res.get("value"), (int, float)):
                calc_log.append({"round": r, "value": float(res["value"])})
            log(f"round {r} calc {obj.get('expr')} -> {res}")
            msgs.append({"role": "assistant", "content": json.dumps(obj, ensure_ascii=False)})
            msgs.append({"role": "user", "content":
                         "计算结果：" + json.dumps(res, ensure_ascii=False) +
                         "。下一步：继续 calc 或 check，参数齐了就 check。"})
            continue

        if action == "patch":
            patch = normalize(obj.get("patch") or {})
            patch = {k: v for k, v in patch.items() if k in FIELDS}
            rec["patch"] = patch
            rec["reason"] = str(obj.get("reason", ""))[:200]
            if not patch:
                trace.append(rec)
                log(f"round {r} patch 为空（{dt}s）")
                msgs.append({"role": "assistant", "content": content[:600]})
                msgs.append({"role": "user", "content":
                             "你的 patch 是空的，等于没改。必须至少给出 1 个违规字段的新数值（数字），"
                             '格式 {"action":"patch","patch":{"字段名":数值},"reason":"..."}。'})
                continue
            p.update(patch)
            action = "check"

        if action in ("check", "final") and not did_calc and not step1_done:
            step1_done = True
            rec["step1_forced"] = True
            trace.append(rec)
            log(f"round {r} 强制先做反解 calc（{dt}s）")
            msgs.append({"role": "assistant", "content": content[:500]})
            msgs.append({"role": "user", "content": STEP1})
            continue

        if action in ("check", "final"):
            incoming = normalize(obj.get("params") or {})
            if action == "final" and not incoming and p:
                incoming = dict(p)
            if incoming:
                p.update(incoming)
            missing = [k for k in FIELDS if k not in p]
            if not missing and not (0 < float(p.get("eta_total") or 0) < 1):
                bad = p.get("eta_total")
                p["eta_total"] = 0.85
                rec["fixed_eta"] = {"model_had": bad, "set_to": 0.85}
                log(f"round {r} eta_total={bad} 非物理，已按 0.85 归一")
                if not missing:
                    msgs.append({"role": "assistant", "content": content[:400]})
                    msgs.append({"role": "user", "content":
                                 f"你把 eta_total 填成 {bad}，总效率必须满足 0<eta_total<1（含所有损失），"
                                 "这是物理下限，我已按 0.85 归一。请用 0<η<1 的正确假设重做反解，再 check。"})
                    trace.append(rec)
                    continue
            if not missing:
                v0 = phys_view(p)
                recomp = v0.get("recomputed") or {}
                u2_now = recomp.get("u2_m_s")
                claim = p.get("claimed_tip_speed_m_s")
                if u2_now and claim and abs(float(claim) - float(u2_now)) > 0.01 * float(u2_now):
                    p["claimed_tip_speed_m_s"] = round(float(u2_now), 2)
                    rec.setdefault("derived_claim", {})["claimed_tip_speed_m_s"] = {
                        "set_to": p["claimed_tip_speed_m_s"], "model_had": claim
                    }
                pr_now = recomp.get("pressure_ratio_recomputed")
                pr_claim = p.get("claimed_pressure_ratio")
                if pr_now and pr_claim and abs(float(pr_claim) - float(pr_now)) > 0.08 * float(pr_now):
                    p["claimed_pressure_ratio"] = round(float(pr_now), 3)
                    rec.setdefault("derived_claim", {})["claimed_pressure_ratio"] = {
                        "set_to": p["claimed_pressure_ratio"], "model_had": pr_claim
                    }
                fos_now = recomp.get("FOS_recomputed")
                fos_claim = p.get("claimed_FOS")
                if fos_now and fos_claim and float(fos_claim) > 1.15 * float(fos_now):
                    p["claimed_FOS"] = round(float(fos_now), 2)
                    rec.setdefault("derived_claim", {})["claimed_FOS"] = {
                        "set_to": p["claimed_FOS"], "model_had": fos_claim
                    }
            view = phys_view(p) if not missing else {"violations": [f"缺字段 {missing}"], "recomputed": {}}
            n = len(view["violations"])
            fp = fingerprint(p)
            rec.update({"n_viol": n, "core": core(p), "violations": view["violations"],
                        "recomputed": view["recomputed"], "fp": fp})
            trace.append(rec)
            log(f"round {r} {action} 违规 {n} 项 fp={fp} core={rec['core']}")
            if best is None or n < best["n_viol"]:
                best = {"n_viol": n, "params": dict(p), "round": r}

            if n == 0:
                log(f"round {r} 通过独立尺子")
                return finalize(model, trace, best, p, True, host, out_dir, t_start, r)

            if action == "final":
                break

            stall = stall + 1 if fp == prev_fp else 0
            prev_fp = fp
            msgs.append({"role": "assistant", "content": json.dumps({"action": action, "params": core(p)},
                                                                   ensure_ascii=False)})
            if stall >= 1:
                msgs.append({"role": "user", "content": build_patch_prompt(p, view["violations"])})
            else:
                u2_now = (view.get("recomputed") or {}).get("u2_m_s") or 0.0
                tail = ""
                if calc_log:
                    big = max(calc_log, key=lambda x: x["value"])
                    if big["value"] > 200 and u2_now and big["value"] > 1.5 * u2_now:
                        tail = ("\n\n【一致性强制】你在第 %d 轮算出达到 π_c 需要 u2≈%.1f m/s，"
                                "但你当前 D2_mm=%s 与 N_rpm=%s 组合的复算叶尖速只有 %.1f m/s，"
                                "差 %.1f 倍——你的计算没有落到参数上。"
                                "用 calc 反解 D2_mm = %.1f*60000/(pi*%s) 得到你需要的外径，"
                                "或反过来提高 N_rpm，二者至少要动一个且要跨量级。"
                                % (big["round"], big["value"], p.get("D2_mm"), p.get("N_rpm"),
                                   u2_now, big["value"] / max(u2_now, 1e-9),
                                   big["value"], p.get("N_rpm")))
                ih2 = interval_hints(view["violations"], p)
                if ih2:
                    tail += ("\n\n【硬区间】" + "; ".join(
                        f"{h['field']} 必须在 [{h['lo']}, {h['hi']}] 内，当前 {p.get(h['field'])}"
                        for h in ih2) + "。这是硬约束，直接落到参数上。")
                msgs.append({"role": "user", "content":
                             "独立复算结果：" + json.dumps(view, ensure_ascii=False) +
                             "。逐条针对违规改相应字段（必要时先用 calc 反解所需量级），再 check。" + tail})
            continue

        rec["unknown_action"] = action
        trace.append(rec)
        msgs.append({"role": "assistant", "content": content[:800]})
        msgs.append({"role": "user", "content": '未知动作。只允许 calc / check / final / patch。'})

    return finalize(model, trace, best, p, False, host, out_dir, t_start, rounds)


def run_solver(model, rounds, host, out_dir, mode="assist"):
    """路线 A'：把 3 类单变量可反解约束从模型决策域移交给确定性求解器。

    模型保留：Z_blades / beta2b_deg / b2 比值假设 / eta_total，以及候选方案的
    accept 权（可 revise 后重算）。求解器负责：axial_length_mm、D1t_mm/D1h_mm、
    b2_mm 与 claimed_* 的反解。
    判定仍只由 closed_impeller_proctor.ruler 给出。
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    trace, t_start = [], time.time()
    if mode == "assist":
        free_prompt = (
            cp.BRIEF + "\n\n【本轮任务：给出你完整的 17 字段设计，之后由确定性求解器校核与修复】\n"
            "你可以自由决定全部参数，但必须只输出一个 JSON，且只能包含下列 17 个键，"
            "不得添加 rationale / 说明 / 单位 / 注释等任何其他键或文字：\n"
            '{"action":"check","params":{' + ",".join(f'"{k}":数值' for k in FIELDS) + "}}\n"
        )
    else:
        free_prompt = (
            cp.BRIEF + "\n\n【本轮任务：只给设计自由度，禁止自己填全套参数】\n"
            "你要决定的是 6 个自由度，其余字段由确定性求解器反解：\n"
            "- Z_blades：叶片数（6~24 整数）\n"
            "- beta2b_deg：出口后弯角（15~55°）\n"
            "- eta_total：假设总效率（0.70~0.90，且必须 0<η<1）\n"
            "- D2_mm：你首选的叶轮外径（mm）\n"
            "- N_rpm：你首选的转速（rpm）\n"
            "- b2_ratio：出口流道宽比 b2/D2（0.03~0.09）\n"
            "只输出一个 JSON：\n"
            '{"action":"free","free":{"Z_blades":12,"beta2b_deg":25,"eta_total":0.85,'
            '"D2_mm":220,"N_rpm":40000,"b2_ratio":0.09},"reason":"一句话"}'
        )
    msgs = [{"role": "system", "content": cp.SYSTEM + "\n" + METHOD_CARD},
            {"role": "user", "content": free_prompt}]

    free, rec0 = None, {"stage": "free" if mode != "assist" else "model_params"}
    try:
        content, dt, ev = chat(host, model, msgs)
        rec0.update({"elapsed_s": dt, "eval_count": ev, "raw_head": content[:400]})
        obj = robust_json(content)
        if mode == "assist":
            if isinstance(obj, dict) and isinstance(obj.get("params"), dict):
                pm = normalize(obj["params"])
                miss = [k for k in FIELDS if k not in pm]
                rec0["model_params"] = pm
                rec0["missing"] = miss
                if not miss and all(isinstance(pm.get(k), (int, float)) for k in FIELDS):
                    v0 = cp.ruler(pm)[1]
                    rec0["n_viol_model_alone"] = len(v0)
                    rec0["violations_model_alone"] = v0
                    free = pm
                else:
                    rec0["parse_fail"] = True
            else:
                rec0["parse_fail"] = True
        else:
            if isinstance(obj, dict) and isinstance(obj.get("free"), dict):
                free = obj["free"]
                rec0["free"] = free
                rec0["reason"] = str(obj.get("reason", ""))[:160]
            else:
                rec0["parse_fail"] = True
    except Exception as e:  # noqa: BLE001
        rec0["error"] = f"{type(e).__name__}: {e}"
    if free is None:
        free = ({"Z_blades": 12, "beta2b_deg": 25.0, "eta_total": 0.85,
                 "D2_mm": 220.0, "N_rpm": 40000.0, "b2_ratio": 0.09}
                if mode != "assist" else
                {"Z_blades": 12, "beta2b_deg": 25.0, "eta_total": 0.85,
                 "D2_mm": 100.0, "N_rpm": 12000.0})
        rec0["fallback_default"] = True
        log("模型未给出可用输入，使用默认值继续（已记录 fallback）")
    trace.append(rec0)
    log(f"模型输入：{json.dumps(free, ensure_ascii=False)[:300]}")

    if mode == "assist":
        cands = solver.from_model_params(free)
        free_brief = {k: free.get(k) for k in ("Z_blades", "beta2b_deg", "eta_total",
                                               "D2_mm", "N_rpm")}
    else:
        cands = solver.candidates(free)
        free_brief = free
    if not cands:
        return finalize_solver(model, trace, None, None, False, host, out_dir,
                               t_start, mode, free_brief, "求解器在该输入下无可行解")
    trace.append({"stage": "solver_candidates",
                  "candidates": [{"id": c["id"], "policy": c["policy"],
                                  "n_viol": c["n_viol"],
                                  "params": c["params"]} for c in cands]})
    log("候选：" + " | ".join(f"{c['id']} {c['policy']} 违规{c['n_viol']}" for c in cands))

    # 把候选交回模型决定接受哪一条
    brief = []
    for c in cands:
        vv = cp.ruler(c["params"])[0]
        brief.append({
            "id": c["id"], "policy": c["policy"],
            "params": c["params"],
            "ruler_recompute": {"pressure_ratio": vv.get("pressure_ratio_recomputed"),
                                "u2_m_s": vv.get("u2_m_s"),
                                "FOS": vv.get("FOS_recomputed"),
                                "M_rel_tip": vv.get("M_rel_tip"),
                                "ca1_m_s": vv.get("ca1_m_s")},
            "n_viol": c["n_viol"], "violations": c["violations"]})
    msgs.append({"role": "assistant", "content": json.dumps(
        ({"action": "check", "params": free} if mode == "assist"
         else {"action": "free", "free": free_brief}), ensure_ascii=False)})
    msgs.append({"role": "user", "content":
                 "确定性求解器已按你的自由度反解出候选方案（L、D1t/D1h、b2、宣称量均已反解）：\n"
                 + json.dumps(brief, ensure_ascii=False) +
                 "\n\n你要做的是决定：接受哪一条，或修正自由度后重算。只输出一个 JSON：\n"
                 '{"action":"accept","choice":"A","reason":"一句话"}\n'
                 '或 {"action":"revise","free":{同上 6 个自由度},"reason":"一句话"}'})

    choice, rec1 = None, {"stage": "decide"}
    try:
        content, dt, ev = chat(host, model, msgs)
        rec1.update({"elapsed_s": dt, "eval_count": ev, "raw_head": content[:400]})
        obj = robust_json(content)
        if isinstance(obj, dict):
            act = str(obj.get("action", "")).lower()
            rec1["action"] = act
            if act == "accept":
                choice = str(obj.get("choice", "")).strip().upper()[:1]
                rec1["choice"] = choice
                rec1["reason"] = str(obj.get("reason", ""))[:160]
            elif act == "revise" and isinstance(obj.get("free"), dict):
                rec1["revised_free"] = obj["free"]
                free_brief = obj["free"]
                cands2 = (solver.from_model_params(obj["free"]) if mode == "assist"
                          else solver.candidates(obj["free"]))
                rec1["revised_candidates"] = [
                    {"id": c["id"], "policy": c["policy"], "n_viol": c["n_viol"]} for c in cands2]
                if cands2:
                    cands = cands2
                    choice = cands2[0]["id"]
                    rec1["auto_taken_after_revise"] = choice
    except Exception as e:  # noqa: BLE001
        rec1["error"] = f"{type(e).__name__}: {e}"
    trace.append(rec1)

    by_id = {c["id"]: c for c in cands}
    if choice not in by_id:
        cands_sorted = sorted(cands, key=lambda c: (c["n_viol"], -(
            cp.ruler(c["params"])[0].get("FOS_recomputed") or 0)))
        choice = cands_sorted[0]["id"]
        trace.append({"stage": "choice_fallback", "taken": choice,
                      "note": "模型未给出有效选择，按违规数最少/FOS 最高择一"})
        log(f"模型未给出有效选择，取候选 {choice}")
    final = by_id[choice]["params"]
    _, viol, _ = cp.ruler(final)
    passed = len(viol) == 0
    log(f"采用候选 {choice}，ruler 判定违规 {len(viol)} 项 -> passed={passed}")
    return finalize_solver(model, trace, by_id[choice], final, passed, host, out_dir,
                           t_start, mode, free_brief, None)


def finalize_solver(model, trace, cand, p, passed, host, out_dir, t_start, mode, free, err):
    report = {
        "route": "A'", "mode": mode, "model": model, "host": host,
        "passed": passed, "elapsed_s": round(time.time() - t_start, 1),
        "model_free_degrees": free,
        "chosen_candidate": None if cand is None else {"id": cand["id"],
                                                      "policy": cand["policy"],
                                                      "n_viol": cand["n_viol"]},
        "final_params": p,
        "final_violations": [] if p is None else cp.ruler(p)[1],
        "ruler": "closed_impeller_proctor.ruler (non-model, 未修改)",
        "accounting": {
            "model_decides": "Z_blades / beta2b_deg / b2 比值假设 / eta_total / 候选接受权",
            "solver_derives": "axial_length_mm（区间中值）、D1t_mm/D1h_mm（由 ca1 目标反解喉口面积）、"
                              "b2_mm（由比值 × D2）、claimed_*（由 ruler 复算派生）",
            "system_does_not": "不改判据、不放宽 ruler、不参与合格判定"},
        "error": err,
        "trace": trace,
    }
    tag = f"Aprime_{mode}"
    out = out_dir / f"report_{tag}_{model.replace(':', '_').replace('/', '_')}_{time.strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"报告写入 {out} | passed={passed}")
    print(json.dumps({"route": "A'", "mode": mode, "passed": passed,
                      "final_params": p, "report": str(out)}, ensure_ascii=False))
    return report


def finalize(model, trace, best, p, passed, host, out_dir, t_start, rounds_used):
    # 系统在模型"决策"之外只做归一化，不代选任何设计值
    report = {
        "model": model, "host": host, "passed": passed, "rounds_used": rounds_used,
        "elapsed_s": round(time.time() - t_start, 1),
        "best_n_viol": best["n_viol"] if best else None,
        "best_params": best["params"] if best else None,
        "final_params": p,
        "ruler": "closed_impeller_proctor.ruler (non-model, 未修改)",
        "accounting": {"model_decides": "全部设计参数与修正方向",
                       "system_provides": "算式求值 / 物理复算回喂 / 格式归一",
                       "system_does_not": "不代选设计值、不改判据、不给目标解"},
        "trace": trace,
    }
    out = out_dir / f"report_{model.replace(':', '_').replace('/', '_')}_{time.strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"报告写入 {out} | passed={passed} | best_n_viol={report['best_n_viol']}")
    print(json.dumps({"passed": passed, "best_n_viol": report["best_n_viol"],
                      "report": str(out)}, ensure_ascii=False))
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="virtu-ties-v1:latest")
    ap.add_argument("--rounds", type=int, default=10)
    ap.add_argument("--host", default=DEFAULT_HOST)
    ap.add_argument("--out", default=str(OUT_BASE))
    ap.add_argument("--mode", default="full", choices=["full", "assist", "auto"],
                    help="full=路线A（模型独占全部决策）；"
                         "assist/auto=路线A'（单变量可反解约束移交确定性求解器）")
    a = ap.parse_args()
    if a.mode == "full":
        run(a.model, a.rounds, a.host, Path(a.out))
    else:
        run_solver(a.model, a.rounds, a.host, Path(a.out), mode=a.mode)


if __name__ == "__main__":
    main()
