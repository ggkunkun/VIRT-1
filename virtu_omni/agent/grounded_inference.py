# -*- coding: utf-8 -*-
"""推理侧接地（grounded inference）：不改权重，修补模型在**换参数**后暴露的三类缺陷。

立项证据（reports/SIX_SOFTWARE_STEP1_AUDIT_2026-11-18.json，probes-2026-11-16-v5，measured）：
  - v3 官方 10 探针 10/10，但 Lamé 换参数（Di50/Do100/Pi24）给不出 σθ=40 MPa；
  - G71 官方题轮廓只有 2 个运动块（缺 Ø38 台阶 / X60 肩 / Z-45 总长）；
  - G71 换参数（Ø80→Ø46×25，L60）在轮廓里写出 ``G0 Z-25.0``（G00 朝 −Z 快移扎刀）。
  三项都是"官方题会背、换参就错"的记忆型缺陷；v7/v8 重训未修好、v8 回退。

修法（推理侧，权重不动）：
  1. 数值物理 —— 模型不再心算。``lame_thick_cylinder`` 闭式解先算出结果，作为
     "已核验工具结果"注入上下文，再对模型叙述做数值一致性门（带 MPa 的数必须落在
     允许集合内）；不一致则带违规清单重写，仍失败 ⇒ 输出确定性结果块。
  2. G71/G70 —— 模型输出必须过 ``validate_g71_against_spec``（按题面参数化的语义门：
     台阶直径/长度、肩、总长、X 单调、G70 起刀、无 G00 负 Z、U/R 正值等）。
     失败带违规清单重写 ≤ max_repairs 次；仍失败 ⇒ ``generate_g71_program`` 确定性生成，
     且生成结果**同样过门**才放行。
  3. 诚实标注 —— 每次回答附 ``grounding``：``source=model|deterministic_*``、
     ``model_passed``、每轮违规历史。确定性兜底**不得**被统计为模型能力（测评法律第四条）。

边界（必须说清）：
  - 这是推理侧防线，**不是**模型变强；被测对象若是"模型本体"，仍要按原探针测裸模型。
  - 题面解析是规则式（正则）；解析不出参数 ⇒ ``applicable=False``，原样返回模型输出，
    绝不臆造参数。
  - G71 语义门只核对程序文本，不等于 VERICUT/机床仿真通过。
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

ModelCaller = Callable[[list], Optional[str]]

_NUM = r"(\d+(?:\.\d+)?)"
_MINUS = "-\u2212\uff0d"


def _strip_think(text: str) -> str:
    t = re.sub(r"<(think|redacted_reasoning|analysis)>.*?</\1>", "", str(text or ""),
               flags=re.S | re.I)
    return t


# ============================================================================
# 1. Lamé 厚壁圆筒
# ============================================================================

def lame_thick_cylinder(di_mm: float, do_mm: float, pi_mpa: float, po_mpa: float = 0.0) -> dict:
    """Lamé 闭式解（受拉为正）。返回内/外壁环向、径向应力与内壁 von Mises，单位 MPa。

    σr(r) = A − B/r²，σθ(r) = A + B/r²，
    A = (pi·ri² − po·ro²)/(ro² − ri²)，B = (pi − po)·ri²·ro²/(ro² − ri²)。
    """
    di, do, pi, po = float(di_mm), float(do_mm), float(pi_mpa), float(po_mpa)
    if not (di > 0 and do > di):
        raise ValueError(f"invalid geometry: Di={di}, Do={do} (need 0 < Di < Do)")
    if pi < 0 or po < 0:
        raise ValueError("pressures must be non-negative")
    ri, ro = di / 2.0, do / 2.0
    den = ro ** 2 - ri ** 2
    a = (pi * ri ** 2 - po * ro ** 2) / den
    b = (pi - po) * ri ** 2 * ro ** 2 / den
    st_i, sr_i = a + b / ri ** 2, a - b / ri ** 2
    st_o, sr_o = a + b / ro ** 2, a - b / ro ** 2
    vm_i = math.sqrt(st_i ** 2 - st_i * sr_i + sr_i ** 2)
    return {
        "ri_mm": ri, "ro_mm": ro,
        "sigma_theta_inner_mpa": st_i, "sigma_r_inner_mpa": sr_i,
        "sigma_theta_outer_mpa": st_o, "sigma_r_outer_mpa": sr_o,
        "von_mises_inner_mpa": vm_i,
        "law": "Lame thick-walled cylinder, tension positive",
        "basis": "closed_form",
    }


_LAME_TRIGGER = re.compile(r"lam[eé]|厚壁圆筒|厚壁筒|thick[- ]?wall", re.I)


def parse_lame_request(text: str) -> Optional[dict]:
    """从题面抽取 Di/Do/Pi(/Po)。抽不全返回 None（不臆造）。"""
    t = str(text or "")
    if not _LAME_TRIGGER.search(t):
        return None

    def grab(patterns: list[str]) -> Optional[float]:
        for p in patterns:
            m = re.search(p, t, flags=re.I)
            if m:
                return float(m.group(1))
        return None

    di = grab([rf"\bDi\s*[=:：为是]\s*{_NUM}", rf"内径\s*(?:Di)?\s*[=:：为是]?\s*[Ø⌀φΦ]?\s*{_NUM}"])
    do = grab([rf"\bDo\s*[=:：为是]\s*{_NUM}", rf"外径\s*(?:Do)?\s*[=:：为是]?\s*[Ø⌀φΦ]?\s*{_NUM}"])
    pi = grab([rf"\bPi\s*[=:：为是]\s*{_NUM}", rf"内压\s*(?:Pi)?\s*[=:：为是]?\s*{_NUM}"])
    po = grab([rf"\bPo\s*[=:：为是]\s*{_NUM}", rf"外压\s*(?:Po)?\s*[=:：为是]?\s*{_NUM}"])
    if di is None or do is None:
        ri = grab([rf"\bri\s*[=:：为是]\s*{_NUM}", rf"内半径\s*[=:：为是]?\s*{_NUM}"])
        ro = grab([rf"\bro\s*[=:：为是]\s*{_NUM}", rf"外半径\s*[=:：为是]?\s*{_NUM}"])
        if ri is not None and ro is not None:
            di, do = 2 * ri, 2 * ro
    if di is None or do is None or pi is None:
        return None
    if not (0 < di < do):
        return None
    return {"di_mm": di, "do_mm": do, "pi_mpa": pi, "po_mpa": po or 0.0}


def _mpa_numbers(text: str) -> list[float]:
    """所有紧邻 MPa 的数值（兼容 LaTeX ``\\,\\text{MPa}`` 与三种负号）。"""
    t = _strip_think(text)
    out = []
    pat = (rf"([{_MINUS}]?\s*\d+(?:\.\d+)?)\s*(?:\\[,;! ]|\s|~)*(?:\\text\{{\s*|\\mathrm\{{\s*)?MPa")
    for m in re.finditer(pat, t):
        raw = re.sub(r"\s+", "", m.group(1))
        raw = raw.replace("\u2212", "-").replace("\uff0d", "-")
        try:
            out.append(float(raw))
        except ValueError:
            continue
    return out


def check_lame_answer(text: str, params: dict, result: dict, tol: float = 0.15) -> dict:
    """数值一致性门：必须出现 σθ_inner 与 σr_inner；所有带 MPa 的数必须在允许集合内。"""
    vis = _strip_think(text)
    raw_nums = re.findall(rf"[{_MINUS}]?\d+(?:\.\d+)?", vis)
    # 兼容 `= − 24 MPa` 等负号与数字间有空格的排版，同时避免把 `100 - 20` 当成 `-20`
    spaced_neg = re.findall(rf"(?:^|[=＝:：约为是(（,，])\s*([{_MINUS}]\s*\d+(?:\.\d+)?)", vis)
    nums = []
    for raw in raw_nums + spaced_neg:
        norm = re.sub(r"\s+", "", raw).replace("\u2212", "-").replace("\uff0d", "-")
        try:
            nums.append(float(norm))
        except ValueError:
            continue
    st, sr = result["sigma_theta_inner_mpa"], result["sigma_r_inner_mpa"]
    violations = []
    if not any(abs(v - st) <= tol for v in nums):
        violations.append(f"missing_sigma_theta_inner({st:.2f})")
    if not any(abs(v - sr) <= tol for v in nums):
        violations.append(f"missing_sigma_r_inner({sr:.2f})")
    allowed = [params["pi_mpa"], -params["pi_mpa"], params.get("po_mpa", 0.0),
               -params.get("po_mpa", 0.0), 0.0]
    allowed += [result[k] for k in ("sigma_theta_inner_mpa", "sigma_r_inner_mpa",
                                    "sigma_theta_outer_mpa", "sigma_r_outer_mpa",
                                    "von_mises_inner_mpa")]
    for v in _mpa_numbers(vis):
        if not any(abs(v - a) <= max(tol, 0.005 * abs(a)) for a in allowed):
            violations.append(f"unsupported_MPa_value({v:g})")
    violations = list(dict.fromkeys(violations))
    return {"passed": not violations, "violations": violations}


def render_lame_answer(params: dict, result: dict) -> str:
    p = params
    r = result
    po_txt = f"，外压 Po = {p['po_mpa']:g} MPa" if p.get("po_mpa") else "（外压 Po = 0）"
    return (
        "【Lamé 厚壁圆筒 · 闭式解核验结果（确定性计算，受拉为正）】\n"
        f"- 已知：Di = {p['di_mm']:g} mm，Do = {p['do_mm']:g} mm，内压 Pi = {p['pi_mpa']:g} MPa{po_txt}\n"
        f"- ri = {r['ri_mm']:g} mm，ro = {r['ro_mm']:g} mm\n"
        "- σθ(ri) = [Pi·ri² − Po·ro² + (Pi − Po)·ro²] / (ro² − ri²)\n"
        f"- 内壁环向应力 σθ = {r['sigma_theta_inner_mpa']:.2f} MPa\n"
        f"- 内壁径向应力 σr = {r['sigma_r_inner_mpa']:.2f} MPa\n"
        f"- 外壁环向应力 σθ(ro) = {r['sigma_theta_outer_mpa']:.2f} MPa，"
        f"外壁径向应力 σr(ro) = {r['sigma_r_outer_mpa']:.2f} MPa\n"
        f"- 内壁 von Mises σvm = {r['von_mises_inner_mpa']:.2f} MPa"
    )


# ============================================================================
# 2. FANUC G71/G70 台阶轴
# ============================================================================

@dataclass
class G71Spec:
    stock_d: float
    steps: list  # [(diameter, length), ...] 自右端起，直径递增
    total_len: float
    s_clamp: Optional[float] = None
    vc: Optional[float] = None
    feed: Optional[float] = None
    tool: str = "T0101"
    tol_d: float = 2.0
    tol_len: float = 1.5
    extra: dict = field(default_factory=dict)


_G71_TRIGGER = re.compile(r"\bG71\b", re.I)


def parse_g71_request(text: str) -> Optional[G71Spec]:
    """抽取棒料直径、台阶（Ø×长）、总长与切削参数。抽不全返回 None。"""
    t = str(text or "")
    if not _G71_TRIGGER.search(t):
        return None
    dia = r"[Ø⌀φΦ]\s*"
    m_stock = (re.search(rf"{dia}{_NUM}\s*(?:mm)?\s*(?:的)?\s*(?:棒料|毛坯|圆钢|bar)", t, re.I)
               or re.search(rf"(?:棒料|毛坯)\s*{dia}?{_NUM}", t))
    m_total = re.search(rf"总长\s*(?:为|=|:|：)?\s*{_NUM}", t) or re.search(
        rf"total\s+length\s*(?:=|:)?\s*{_NUM}", t, re.I)
    steps = []
    for m in re.finditer(rf"台阶\s*{dia}{_NUM}\s*(?:mm)?\s*(?:长|[x×*]|，长)\s*{_NUM}", t):
        steps.append((float(m.group(1)), float(m.group(2))))
    if not steps:
        for m in re.finditer(rf"{dia}{_NUM}\s*[x×*]\s*{_NUM}", t):
            steps.append((float(m.group(1)), float(m.group(2))))
    if not (m_stock and m_total and steps):
        return None
    stock_d, total = float(m_stock.group(1)), float(m_total.group(1))
    if sum(L for _, L in steps) > total + 1e-9 or any(d >= stock_d + 1e-9 for d, _ in steps):
        return None
    if any(steps[i][0] > steps[i + 1][0] for i in range(len(steps) - 1)):
        return None  # G71 Type I 要求 X 单调，非单调轮廓不在本门处理范围
    s_clamp = re.search(rf"G50\s*S\s*{_NUM}", t, re.I)
    vc = re.search(rf"G96\s*S\s*{_NUM}", t, re.I)
    feed = re.search(rf"\bF\s*{_NUM}", t)
    tool = re.search(r"\b(T\d{4})\b", t)
    return G71Spec(stock_d=stock_d, steps=steps, total_len=total,
                   s_clamp=float(s_clamp.group(1)) if s_clamp else None,
                   vc=float(vc.group(1)) if vc else None,
                   feed=float(feed.group(1)) if feed else None,
                   tool=tool.group(1).upper() if tool else "T0101")


def _program_lines(text: str) -> list[str]:
    vis = _strip_think(text)
    vis = re.sub(r"\([^)]*\)", " ", vis)
    out = []
    for raw in re.split(r"[\r\n;]+", vis):
        line = raw.strip().upper()
        if line and re.search(r"\b[GMTXZSFNUPQRW]\s*-?\d", line) and not line.startswith("```"):
            out.append(line)
    return out


def _w(line: str, letter: str) -> list[float]:
    return [float(v) for v in re.findall(rf"(?<![A-Z]){letter}\s*(-?\d+(?:\.\d+)?)", line)]


def _profile_targets(spec: G71Spec) -> list:
    """[(diameter, z_end)]：每段直径应切到的 Z。最后一段若小于毛坯，补到总长。"""
    targets, z = [], 0.0
    for d, L in spec.steps:
        z -= L
        targets.append((d, z))
    if abs(z) < spec.total_len - 1e-9:
        targets.append((spec.stock_d, -spec.total_len))
    return targets


def validate_g71_against_spec(text: str, spec: G71Spec) -> dict:
    """按题面参数化的 G71/G70 语义门。violations 为空才通过；空程序/解析失败判红。"""
    lines = _program_lines(text)
    v: list[str] = []
    ev: dict[str, Any] = {}
    if not lines:
        return {"passed": False, "violations": ["no_gcode_lines"], "evidence": {}}
    up = "\n".join(lines)

    for tok in ("G70", "G71"):
        if not re.search(rf"\b{tok}\b", up):
            v.append(f"missing_{tok}")
    if not re.search(r"\bM30\b|\bM0?2\b", up):
        v.append("missing_program_end")
    if not re.search(r"\bM0?3\b", up):
        v.append("missing_M03")
    if spec.s_clamp is not None and not any(abs(s - spec.s_clamp) < 1e-6
                                            for ln in lines if re.search(r"\bG50\b", ln)
                                            for s in _w(ln, "S")):
        v.append(f"missing_G50_S{spec.s_clamp:g}")
    if spec.vc is not None and not any(abs(s - spec.vc) < 1e-6
                                       for ln in lines if re.search(r"\bG96\b", ln)
                                       for s in _w(ln, "S")):
        v.append(f"missing_G96_S{spec.vc:g}")
    tool_num = spec.tool[1:3]
    if not re.search(rf"\bT0?{int(tool_num)}(?:\d\d)?\b", up):
        v.append(f"missing_{spec.tool}")
    if spec.feed is not None and not any(abs(f - spec.feed) < 1e-6 for ln in lines for f in _w(ln, "F")):
        v.append(f"missing_F{spec.feed:g}")

    g71 = [i for i, ln in enumerate(lines) if re.search(r"\bG71\b", ln)]
    first = next((i for i in g71 if not (re.search(r"\bP\d+", lines[i]) and re.search(r"\bQ\d+", lines[i]))), None)
    cyc = next((i for i in g71 if re.search(r"\bP\d+", lines[i]) and re.search(r"\bQ\d+", lines[i])), None)
    if first is None:
        v.append("G71_first_block_missing")
    else:
        fb = lines[first]
        ev["first_block"] = fb
        if not _w(fb, "U") or any(x <= 0 for x in _w(fb, "U")):
            v.append("G71_U_must_be_positive")
        if not _w(fb, "R") or any(x <= 0 for x in _w(fb, "R")):
            v.append("G71_R_must_be_positive")
        if _w(fb, "W"):
            v.append("G71_first_block_has_W")

    # 循环起点（G71 之前最后一次定位）必须在毛坯外
    if g71:
        x0 = z0 = None
        for ln in lines[:g71[0]]:
            if _w(ln, "X"):
                x0 = _w(ln, "X")[-1]
            if _w(ln, "Z"):
                z0 = _w(ln, "Z")[-1]
        ev["cycle_start"] = (x0, z0)
        if x0 is None or x0 < spec.stock_d or z0 is None or z0 <= 0:
            v.append("cycle_start_not_outside_stock")

    profile: list[str] = []
    q_idx = None
    if cyc is None:
        v.append("G71_PQ_block_missing")
    else:
        pm, qm = re.search(r"\bP(\d+)", lines[cyc]), re.search(r"\bQ(\d+)", lines[cyc])
        p_idx = next((i for i, ln in enumerate(lines) if re.match(rf"N0*{int(pm.group(1))}\b", ln)), None)
        q_idx = next((i for i, ln in enumerate(lines) if re.match(rf"N0*{int(qm.group(1))}\b", ln)), None)
        if p_idx is None or q_idx is None:
            v.append("profile_markers_not_found")
            q_idx = None
        elif q_idx <= p_idx:
            v.append("profile_Q_before_P")
            q_idx = None
        else:
            profile = lines[p_idx:q_idx + 1]
    ev["profile"] = profile

    if profile:
        # Type I：首块只允许 X 向（不得带 Z）
        if _w(profile[0], "Z"):
            v.append("profile_first_block_has_Z(TypeI)")
        x = z = None
        pts = []
        mode = None
        for ln in profile:
            g = re.findall(r"\bG0?([0-3])\b", ln)
            if g:
                mode = g[-1]
            nx, nz = _w(ln, "X"), _w(ln, "Z")
            if nx:
                x = nx[-1]
            if nz:
                z = nz[-1]
            if nx or nz:
                pts.append((x, z, mode))
        ev["profile_points"] = pts
        if len(pts) < len(_profile_targets(spec)) + 2:
            v.append(f"profile_too_short({len(pts)})")
        xs = [p[0] for p in pts if p[0] is not None]
        if any(xs[i + 1] < xs[i] - 1e-6 for i in range(len(xs) - 1)):
            v.append("profile_X_not_monotonic")
        for d, z_end in _profile_targets(spec):
            reach = [p[1] for p in pts if p[0] is not None and p[1] is not None
                     and abs(p[0] - d) <= spec.tol_d and p[2] == "1"]
            if not reach:
                v.append(f"profile_missing_diameter_{d:g}")
            elif min(reach) > z_end + spec.tol_len or min(reach) < z_end - spec.tol_len:
                v.append(f"profile_diameter_{d:g}_wrong_length(need Z{z_end:g},got Z{min(reach):g})")
        if x is None or x < spec.stock_d:
            v.append("profile_does_not_exit_stock")
        if not any(p[2] == "1" for p in pts):
            v.append("profile_has_no_feed_cut")

    if q_idx is not None:
        g70 = next((i for i, ln in enumerate(lines) if re.search(r"\bG70\b", ln) and i > q_idx), None)
        if g70 is None:
            v.append("G70_not_after_Q")
        else:
            g70_line = lines[g70]
            if not (re.search(r"\bP\d+", g70_line) and re.search(r"\bQ\d+", g70_line)):
                v.append("G70_missing_PQ")
            if _w(g70_line, "U") or _w(g70_line, "W"):
                v.append("G70_must_not_have_U_W")

    motion_mode = None
    for ln in lines:
        g_codes = re.findall(r"\bG0?([0-3])\b", ln)
        if g_codes:
            motion_mode = g_codes[-1]
        is_ref_return = bool(re.search(r"\bG(?:28|30|53)\b", ln))
        has_g00 = bool(re.search(r"\bG0?0\b", ln))
        if not is_ref_return and (has_g00 or (motion_mode == "0" and not g_codes)):
            if any(zz < 0 for zz in _w(ln, "Z")):
                v.append("unsafe_G00_negative_Z_plunge")
                break
    for letter, tag in (("S", "non_positive_S"), ("F", "non_positive_F")):
        if any(val <= 0 for ln in lines for val in _w(ln, letter)):
            v.append(tag)

    v = list(dict.fromkeys(v))
    return {"passed": not v, "violations": v, "evidence": ev, "basis": "static_semantic"}


def generate_g71_program(spec: G71Spec, program_no: int = 1000) -> str:
    """确定性生成 G71 Type I 粗车 + G70 精车程序（不含 G00 负 Z）。"""
    s_clamp = spec.s_clamp or 2000
    vc = spec.vc or 150
    f_rough = spec.feed or 0.25
    f_fin = round(min(f_rough, 0.12), 3)
    x_start = spec.stock_d + 2.0
    steps_txt = " ".join(f"D{d:g}x{L:g}" for d, L in spec.steps)
    lines = [
        "%",
        f"O{program_no:04d} (G71/G70 STEP SHAFT D{spec.stock_d:g} {steps_txt} L{spec.total_len:g})",
        "G21 G40 G99",
        f"G50 S{s_clamp:g}",
        f"{spec.tool}",
        f"G96 S{vc:g} M03",
        f"G00 X{x_start:.1f} Z2.0 M08",
        "G71 U1.5 R0.5",
    ]
    n = 10
    cur_x = spec.steps[0][0]
    prof = [f"N{n} G00 X{cur_x:.1f}"]          # Type I：首块只走 X（Z 仍在 +2.0）
    n += 10
    prof.append(f"N{n} G01 Z0.0 F{f_fin:g}")
    for d, z_end in _profile_targets(spec):
        if abs(d - cur_x) > 1e-9:
            n += 10
            prof.append(f"N{n} G01 X{d:.1f}")   # 台阶肩：径向切出
            cur_x = d
        n += 10
        prof.append(f"N{n} G01 Z{z_end:.1f}")   # 沿该直径切到目标 Z
    n += 10
    prof.append(f"N{n} G01 X{x_start:.1f}")     # 径向退出毛坯，G70 起刀点在毛坯外
    q = n
    retract_x = max(100.0, spec.stock_d + 20.0)
    lines.append(f"G71 P10 Q{q} U0.4 W0.1 F{f_rough:g}")
    lines += prof
    lines += [f"G70 P10 Q{q}", f"G00 X{retract_x:.1f} Z100.0 M09", "M05", "M30", "%"]
    return "\n".join(lines)


# ============================================================================
# 3. 编排：模型 → 门 → 带违规重写 → 确定性兜底（同样过门）
# ============================================================================

def _last_user_text(messages: list) -> str:
    for m in reversed(messages or []):
        if isinstance(m, dict) and m.get("role") == "user":
            c = m.get("content")
            if isinstance(c, list):
                return " ".join(str(x.get("text", "")) for x in c if isinstance(x, dict))
            return str(c or "")
    return ""


def _call(model_caller: Optional[ModelCaller], messages: list) -> Optional[str]:
    if model_caller is None:
        return None
    try:
        out = model_caller(messages)
    except Exception:  # 传输错误按"无输出"处理，不当作模型答案（测评法律第三条）
        return None
    if out is None or not str(out).strip() or str(out).startswith("ERROR"):
        return None
    return str(out)


def is_grounded_applicable(text: str) -> bool:
    """True when the prompt matches a grounded deterministic solver/gate domain."""
    return parse_g71_request(text) is not None or parse_lame_request(text) is not None


def build_grounding_hint(text: str) -> Optional[str]:
    """Build deterministic grounding context for SuperAgent/REACT prompts, or None."""
    spec = parse_g71_request(text)
    if spec is not None:
        targets = ", ".join(f"Ø{d:g} 至 Z{z:g}" for d, z in _profile_targets(spec))
        return (
            f"G71 Type I 约束：循环起点在毛坯外（X>{spec.stock_d:g}, Z>0）；"
            f"轮廓 N(P) 只走 X，随后用 G01 依次切出 {targets}，最后 G01 径向退出毛坯；"
            "轮廓内及任何 G00 行不得出现负 Z；G70 P Q 紧随轮廓之后。"
        )
    lame = parse_lame_request(text)
    if lame is not None:
        result = lame_thick_cylinder(**lame)
        return (
            "以下为已核验的工具计算结果（Lamé 闭式解，受拉为正），回答中的数值必须与之一致，"
            "不得自行另算：" + render_lame_answer(lame, result)
        )
    return None


def _inject_system_hint(messages: list, hint: Optional[str]) -> list:
    conv = [dict(m) for m in (messages or [])]
    if not hint:
        return conv
    if conv and conv[0].get("role") == "system":
        cur = str(conv[0].get("content", ""))
        if hint not in cur:
            conv[0]["content"] = (cur + "\n\n" + hint).strip() if cur.strip() else hint
    else:
        conv.insert(0, {"role": "system", "content": hint})
    return conv


class GroundedResponder:
    def __init__(self, model_caller: Optional[ModelCaller] = None, max_repairs: int = 3):
        self.model_caller = model_caller
        self.max_repairs = max(0, int(max_repairs))

    def respond(self, messages: list) -> dict:
        user = _last_user_text(messages)
        spec = parse_g71_request(user)
        if spec is not None:
            return self._g71(messages, spec)
        lame = parse_lame_request(user)
        if lame is not None:
            return self._lame(messages, lame)
        raw = _call(self.model_caller, messages)
        return {"content": raw, "grounding": {"applicable": False, "kind": None,
                                              "source": "model" if raw else "none"}}

    def _repair_loop(self, messages: list, check: Callable[[str], dict], first_hint: Optional[str]):
        history = []
        conv = _inject_system_hint(messages, first_hint)
        for attempt in range(self.max_repairs + 1):
            out = _call(self.model_caller, conv)
            if out is None:
                history.append({"attempt": attempt, "violations": ["no_model_output"]})
                break
            verdict = check(out)
            history.append({"attempt": attempt, "violations": verdict["violations"]})
            if verdict["passed"]:
                return out, history
            conv = conv + [
                {"role": "assistant", "content": out},
                {"role": "user", "content": "上一版未通过自动核验，违规项：" + "；".join(verdict["violations"])
                 + "。请逐条修正后输出完整答案，不要解释违规项本身。"},
            ]
        return None, history

    def _lame(self, messages: list, params: dict) -> dict:
        result = lame_thick_cylinder(**params)
        hint = ("以下为已核验的工具计算结果（Lamé 闭式解，受拉为正），回答中的数值必须与之一致，"
                "不得自行另算：" + render_lame_answer(params, result))
        out, hist = self._repair_loop(messages, lambda t: check_lame_answer(t, params, result), hint)
        if out is not None:
            return {"content": out, "grounding": {
                "applicable": True, "kind": "lame", "source": "model",
                "model_passed": True, "attempts": hist, "params": params, "result": result}}
        content = render_lame_answer(params, result)
        verdict = check_lame_answer(content, params, result)
        return {"content": content if verdict["passed"] else None, "grounding": {
            "applicable": True, "kind": "lame", "source": "deterministic_closed_form",
            "model_passed": False, "attempts": hist, "fallback_gate": verdict,
            "params": params, "result": result}}

    def _g71(self, messages: list, spec: G71Spec) -> dict:
        targets = ", ".join(f"Ø{d:g} 至 Z{z:g}" for d, z in _profile_targets(spec))
        hint = (f"G71 Type I 约束：循环起点在毛坯外（X>{spec.stock_d:g}, Z>0）；"
                f"轮廓 N(P) 只走 X，随后用 G01 依次切出 {targets}，最后 G01 径向退出毛坯；"
                "轮廓内及任何 G00 行不得出现负 Z；G70 P Q 紧随轮廓之后。")
        out, hist = self._repair_loop(messages, lambda t: validate_g71_against_spec(t, spec), hint)
        if out is not None:
            return {"content": out, "grounding": {
                "applicable": True, "kind": "g71", "source": "model",
                "model_passed": True, "attempts": hist, "spec": spec.__dict__}}
        prog = generate_g71_program(spec)
        verdict = validate_g71_against_spec(prog, spec)
        return {"content": prog if verdict["passed"] else None, "grounding": {
            "applicable": True, "kind": "g71", "source": "deterministic_generator",
            "model_passed": False, "attempts": hist, "fallback_gate": verdict,
            "spec": spec.__dict__}}
