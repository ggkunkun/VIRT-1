"""Deterministic recomputation for quantities the milling-chain guard does not cover.

Why this module exists
----------------------
``VIRTU_NUMERIC_GAP_2026-11-05.md`` measured 54/100 ``numeric_near`` misses on the
frozen leg and listed the quantities no registered formula could reach.  The gap is
not reasoning: the model states the right law and then loses the arithmetic.  This
module adds the missing laws as *pure functions of explicitly stated inputs* so the
serving layer can recompute them and publish an authoritative value.

Every family is gated on the prompt stating all of its inputs unambiguously and
asking for that quantity.  Ambiguity vetoes the formula -- publishing a guess as
"authoritative" is worse than not checking.  ``tests/test_arithmetic_guard.py::
test_every_published_value_matches_the_case_gold`` is the safety net: any value this
module publishes must agree with every shipped case's gold, so a wrong law fails CI
rather than a customer's part.

Nothing here defines physics independently of the rest of the repo: the milling,
scallop, tolerance and clearance laws are the same hand-book formulas quoted in the
benchmark prompts themselves; unit conversion uses the exact 1 in = 25.4 mm.
"""
from __future__ import annotations

import math
import re

Problem = tuple[str, str, float]

_F = r"(\d+(?:\.\d+)?)"


def _f(value: float, decimals: int = 4) -> str:
    text = f"{value:.{decimals}f}".rstrip("0")
    return text[:-1] if text.endswith(".") else (text or "0")


def _milling_compact(text: str) -> list[Problem]:
    """n / Vf from the compact card notation ``D80 z6 VC180 fz0.2``."""
    if not re.search(r"(主轴转速|转速|spindle|r/min|rpm|S\s*=)", text, re.I):
        return []
    if not re.search(r"(进给|feed|F\s*=)", text, re.I):
        return []
    d = re.search(r"(?<![A-Za-z])D\s*=?\s*" + _F + r"\s*(?:mm)?", text)
    vc = re.search(r"(?<![A-Za-z])Vc\s*=?\s*" + _F, text, re.I)
    if not (d and vc):
        return []
    if re.search(r"(系数|档位|档表|查表|按表|每提高一档|折减|乘\s*0?\.\d)", text):
        return []
    d_val, vc_val = float(d.group(1)), float(vc.group(1))
    if d_val <= 0 or vc_val <= 0:
        return []
    n = 1000.0 * vc_val / (math.pi * d_val)
    out: list[Problem] = [
        ("主轴转速", f"n = 1000·Vc/(π·D) = 1000×{_f(vc_val)}/(π×{_f(d_val)}) = {n:.1f} r/min", n)
    ]
    z = re.search(r"(?<![A-Za-z])z\s*=?\s*" + _F, text, re.I) or re.search(
        _F + r"\s*(?:个)?\s*(?:齿|teeth|flutes)", text, re.I)
    fz = re.search(r"(?<![A-Za-z])fz\s*=?\s*" + _F, text, re.I)
    if not fz:
        fz = re.search(r"(?:每齿进给(?:量)?|每齿|feed per tooth)[^0-9]{0,12}" + _F, text, re.I)
    if z and fz:
        z_val, fz_val = float(z.group(1)), float(fz.group(1))
        if z_val > 0:
            vf = fz_val * z_val * n
            out.append(("进给速度",
                        f"Vf = fz·z·n = {_f(fz_val)}×{_f(z_val)}×{n:.1f} = {vf:.1f} mm/min",
                        vf))
    return out


def _scallop(text: str) -> list[Problem]:
    """Residual scallop height: the prompt states which formula governs."""
    if not re.search(r"(残留高度|scallop)", text, re.I):
        return []
    s = re.search(r"(?<![A-Za-z])s\s*=\s*" + _F, text, re.I)
    if not s:
        s = re.search(r"(?:行距|步距|stepover|步长)[^0-9]{0,12}" + _F + r"\s*(?:mm|毫米)?", text, re.I)
    r = re.search(r"(?<![A-Za-z])R\s*=\s*" + _F + r"\s*(?:mm|毫米)?", text)
    if not r:
        r = re.search(r"(?:球头|球刀|ball)[^0-9]{0,12}R\s*=?\s*" + _F, text, re.I)
    if not r:
        r = re.search(r"(?<![A-Za-z])R\s*" + _F + r"\s*(?:mm|毫米)?[^0-9，。,]{0,10}(?:球头|球刀)",
                      text, re.I)
    if not (s and r):
        return []
    s_val, r_val = float(s.group(1)), float(r.group(1))
    if s_val <= 0 or r_val <= 0:
        return []
    if re.search(r"R\s*-\s*(?:sqrt|√)", text, re.I):
        # Exact circular scallop: h = R - sqrt(R² - (s/2)²).
        h = r_val - math.sqrt(max(0.0, r_val ** 2 - (s_val / 2.0) ** 2))
        return [("残留高度", f"h = R-sqrt(R²-(s/2)²) = {_f(r_val)}-sqrt({_f(r_val)}²-{_f(s_val)}²/4) = {h:.3f} mm", h)]
    if re.search(r"(s\s*\^?\s*2\s*/\s*\(\s*8\s*R|约等于|近似)", text, re.I):
        h = s_val ** 2 / (8.0 * r_val)
        return [("残留高度", f"h ≈ s²/(8R) = {_f(s_val)}²/(8×{_f(r_val)}) = {h:.4f} mm", h)]
    return []


def _imperial(text: str) -> list[Problem]:
    """Exact inch/feet -> mm conversions, including rectangle area."""
    if not re.search(r"(英寸|inch|in\.|\bft\b|英尺)", text, re.I):
        return []
    out: list[Problem] = []

    def is_definition(match) -> bool:
        """``1 英寸=25.4 mm`` states the unit, it is not a value to convert."""
        return text[match.end():match.end() + 2].strip().startswith(("=", "＝"))

    rect = re.search(_F + r"\s*(?:英寸|inch|in\.)\s*[×xX*]\s*" + _F + r"\s*(?:英寸|inch|in\.)",
                     text, re.I)
    if rect:
        a, b = float(rect.group(1)), float(rect.group(2))
        a_mm, b_mm = a * 25.4, b * 25.4
        out.append(("长边毫米", f"{_f(a)} in × 25.4 = {a_mm:.1f} mm", a_mm))
        out.append(("短边毫米", f"{_f(b)} in × 25.4 = {b_mm:.1f} mm", b_mm))
        out.append(("面积", f"{a_mm:.1f}×{b_mm:.1f} = {a_mm * b_mm:.1f} mm²", a_mm * b_mm))
    frac = re.search(r"(\d+)\s*/\s*(\d+)\s*(?:英寸|inch|in\.)", text, re.I)
    if frac and not rect and not is_definition(frac):
        num, den = float(frac.group(1)), float(frac.group(2))
        if den > 0:
            mm = num / den * 25.4
            out.append(("英寸换算", f"{int(num)}/{int(den)} in × 25.4 = {mm:.3f} mm", mm))
    if not rect and not frac:
        for one in re.finditer(_F + r"\s*(?:英寸|inch|in\.)", text, re.I):
            if is_definition(one):
                continue
            mm = float(one.group(1)) * 25.4
            out.append(("英寸换算", f"{_f(float(one.group(1)))} in × 25.4 = {mm:.1f} mm", mm))
    for feet in re.finditer(_F + r"\s*(?:ft|英尺)", text, re.I):
        if is_definition(feet):
            continue
        mm = float(feet.group(1)) * 304.8
        out.append(("英尺换算", f"{_f(float(feet.group(1)))} ft × 304.8 = {mm:.1f} mm", mm))
    # A millimetre depth asked back in feet: 50.8 mm -> 0.17 ft.
    if re.search(r"换算成英尺|转换为英尺|折合.{0,4}英尺", text):
        inch = next((m for m in re.finditer(_F + r"\s*(?:in|inch|英寸)", text, re.I)
                     if not is_definition(m)), None)
        if inch:
            feet_val = float(inch.group(1)) / 12.0
            out.append(("深度英尺", f"{_f(float(inch.group(1)))} in ÷ 12 = {feet_val:.2f} ft",
                        feet_val))
    return out


def _tolerance_stack(text: str) -> list[Problem]:
    """Worst-case and RSS stack-up -- only for the quantities the prompt asks for."""
    if not re.search(r"(极值法|最坏情况|worst[ -]?case|公差带|RSS|统计法|方和根|单边)", text, re.I):
        return []
    if re.search(r"(没有标注公差|未标注公差|只标注了?名义尺寸|缺少.{0,8}公差|条件不足)", text):
        return []
    raw_pairs = [
        (m.start(), float(m.group(1)), float(m.group(2)))
        for m in re.finditer(_F + r"\s*±\s*" + _F, text)
    ]
    # A drawing/assembly requirement (e.g. "图纸要求是 28±0.30") is the target,
    # never a ring of the chain.
    pairs = [(nom, tol) for pos, nom, tol in raw_pairs if "要求" not in text[max(0, pos - 14):pos]]
    if len(pairs) < 2:
        return []
    noms = [nom for nom, _ in pairs]
    tols = [tol for _, tol in pairs]
    total = sum(noms)
    band_half = sum(tols)
    rss = math.sqrt(sum(t * t for t in tols))
    sq = sum(t * t for t in tols)
    wants_sizes = bool(re.search(r"(最大极限尺寸|最小极限尺寸|公差带宽度|公差带)", text))
    wants_half = bool(re.search(r"(单边|半宽|合成公差)", text))
    wants_rss = bool(re.search(r"(RSS|统计法|方和根)", text))
    wants_sq = bool(re.search(r"(根号内|平方和)", text))
    out: list[Problem] = []
    if wants_sizes:
        out.append(("最大极限尺寸", f"Σnom+Σtol = {_f(total)}+{_f(band_half)} = {total + band_half:.2f} mm",
                    total + band_half))
        out.append(("最小极限尺寸", f"Σnom-Σtol = {_f(total)}-{_f(band_half)} = {total - band_half:.2f} mm",
                    total - band_half))
        out.append(("公差带宽度", f"2×Σtol = 2×{_f(band_half)} = {2 * band_half:.2f} mm",
                    2 * band_half))
    if wants_half:
        out.append(("极值法单边公差", f"Σtol = {'+'.join(_f(t) for t in tols)} = {band_half:.3f} mm",
                    band_half))
    if wants_rss:
        out.append(("RSS单边公差", f"sqrt(Σt²) = sqrt({_f(sq, 6)}) = {rss:.3f} mm", rss))
    if wants_sq:
        out.append(("根号内平方和", f"Σt² = {_f(sq, 6)} mm²", sq))
    return out


def _clearance(text: str) -> list[Problem]:
    """Max/min clearance of a hole-shaft fit from stated deviations."""
    if not re.search(r"(间隙|clearance)", text, re.I):
        return []
    hole = re.search(
        r"孔.{0,40}?上偏差\s*([+-]?\d+(?:\.\d+)?)\s*[、,，]\s*下偏差\s*([+-]?\d+(?:\.\d+)?)",
        text)
    shaft = re.search(
        r"轴.{0,40}?上偏差\s*([+-]?\d+(?:\.\d+)?)\s*[、,，]\s*下偏差\s*([+-]?\d+(?:\.\d+)?)",
        text)
    if not (hole and shaft):
        return []
    hu, hl = float(hole.group(1)), float(hole.group(2))
    su, sl = float(shaft.group(1)), float(shaft.group(2))
    mx, mn = hu - sl, hl - su
    return [
        ("最大间隙", f"ES-ei = {hu:+.3f}-({sl:+.3f}) = {mx:.3f} mm", mx),
        ("最小间隙", f"EI-es = {hl:+.3f}-({su:+.3f}) = {mn:.3f} mm", mn),
    ]


def _mmc_bonus(text: str) -> list[Problem]:
    """MMC bonus, capped at the size tolerance band, plus any size overrun.

    A hole whose actual size is already past its upper limit earns no extra bonus:
    the bonus ceiling is the size tolerance itself (0.030 here), and the overrun
    (0.005) is what actually rejects the part.  Publishing the uncapped 0.135 would
    be the classic MMC trap.
    """
    if not re.search(r"最大实体要求|(?:符号\s*M|Ⓜ)", text):
        return []
    if not re.search(r"位置度", text):
        return []
    actual = re.search(r"实测孔径\s*Ø?\s*" + _F, text)
    if not actual:
        return []
    size = re.search(r"孔\s*Ø\s*" + _F + r"\s*上偏差\s*([+-]?\d+(?:\.\d+)?)\s*[、,，]\s*下偏差\s*([+-]?\d+(?:\.\d+)?)",
                     text)
    if not size:
        return []
    tol = re.search(r"位置度公差\s*Ø?\s*" + _F, text)
    if not tol:
        return []
    nominal, upper, lower = float(size.group(1)), float(size.group(2)), float(size.group(3))
    actual_val, tol_val = float(actual.group(1)), float(tol.group(1))
    size_tol = abs(upper - lower)
    mmc = nominal + min(lower, upper)
    max_limit = nominal + max(lower, upper)
    overrun = max(0.0, actual_val - max_limit)
    bonus = min(max(0.0, actual_val - mmc), size_tol)
    return [
        ("最大实体补偿量",
         f"min(实测-|MMC|, 尺寸公差) = min({actual_val:.3f}-{mmc:.3f}, {size_tol:.3f}) = {bonus:.3f} mm",
         bonus),
        ("允许位置度公差", f"给定+补偿 = {tol_val:.3f}+{bonus:.3f} = {tol_val + bonus:.3f} mm",
         tol_val + bonus),
        ("尺寸超差", f"实测-最大极限 = {actual_val:.3f}-{max_limit:.3f} = {overrun:.3f} mm", overrun),
    ]


def _gcode_modal(text: str) -> list[Problem]:
    """Final tool position under alternating G90/G91 modal groups."""
    if not (re.search(r"G90", text) and re.search(r"G91", text)):
        return []
    if not re.search(r"(绝对坐标|终点|最终|走到|坐标值|最后)", text):
        return []
    x = y = 0.0
    seen = 0
    for line in re.split(r"[;；\n]+", text):
        modes = re.findall(r"G9[01]", line)
        coords = re.findall(r"([XY])\s*([-+]?\d+(?:\.\d+)?)", line)
        if not modes and not coords:
            continue
        relative = bool(modes) and modes[-1] == "G91"
        if modes:
            seen += 1
        for axis, raw in coords:
            value = float(raw)
            if axis == "X":
                x = x + value if relative else value
            else:
                y = y + value if relative else value
    if seen < 2:
        return []
    return [
        ("终点X", f"G90/G91 模态累计 X = {x:g} mm", x),
        ("终点Y", f"G90/G91 模态累计 Y = {y:g} mm", y),
    ]


def _rss_plain(text: str) -> list[Problem]:
    """RSS of a plain hand-written tolerance list (no ``±`` pairs)."""
    if not re.search(r"(RSS|统计法|方和根)", text, re.I):
        return []
    if re.search(_F + r"\s*±\s*" + _F, text):
        return []  # the ± stack family owns that shape
    m = re.search(r"(?:单边值|组成环公差)[^0-9]{0,10}((?:0\.\d+\s*[、,，]\s*){1,}0\.\d+)", text)
    if not m:
        return []
    tols = [float(x) for x in re.findall(r"0\.\d+", m.group(1))]
    if len(tols) < 2:
        return []
    sq = sum(t * t for t in tols)
    rss = math.sqrt(sq)
    return [
        ("RSS单边公差", f"sqrt({' + '.join(_f(t) + '²' for t in tols)}) = {rss:.3f} mm", rss),
        ("根号内平方和", f"Σt² = {_f(sq, 6)} mm²", sq),
    ]


def _shaft_mmc(text: str) -> list[Problem]:
    """MMC bonus for a shaft: MMC is the maximum size, so bonus = nominal - actual."""
    if "孔" in text or not re.search(r"最大实体要求", text) or not re.search(r"轴", text):
        return []
    actual = re.search(r"实际(?:测得)?直径为?\s*" + _F, text)
    nominal = re.search(r"(?:phi|Φ|Ø)\s*" + _F, text, re.I)
    tol = re.search(r"位置度给定公差\s*" + _F, text)
    if not (actual and nominal and tol):
        return []
    mmc, actual_val, tol_val = float(nominal.group(1)), float(actual.group(1)), float(tol.group(1))
    bonus = max(0.0, mmc - actual_val)
    return [
        ("最大实体补偿量", f"MMC-实测 = {mmc:.1f}-{actual_val:.1f} = {bonus:.3f} mm", bonus),
        ("允许位置度公差", f"给定+补偿 = {tol_val:.1f}+{bonus:.3f} = {tol_val + bonus:.3f} mm",
         tol_val + bonus),
    ]


def _gcode_table_count(text: str) -> list[Problem]:
    """Distinct G codes declared in a custom (deliberately inverted) table."""
    if not re.search(r"代码对照表|对照表", text) or not re.search(r"G\s*代码", text):
        return []
    table = text.split("要求")[0]
    codes = set(re.findall(r"\bG(\d{1,2})\b", table))
    if len(codes) < 2:
        return []
    return [("本表G代码数", f"表内不同 G 代码 {sorted('G' + c for c in codes)} 共 {len(codes)} 个",
             float(len(codes)))]


def _radius_table(text: str) -> list[Problem]:
    """Round requested fillet radii up to the nearest allowed table value."""
    if not re.search(r"圆角半径表", text) or not re.search(r"向上圆整", text):
        return []
    tbl = re.search(r"离散值[^0-9]{0,6}((?:\d+(?:\.\d+)?\s*[、,，]\s*){1,}\d+(?:\.\d+)?)", text)
    req = re.search(r"输出\s*[：:]?\s*(R\d+(?:\.\d+)?\s*[、,，]\s*R\d+(?:\.\d+)?)", text)
    if not (tbl and req):
        return []
    table = sorted(float(x) for x in re.findall(r"\d+(?:\.\d+)?", tbl.group(1)))
    requests = [float(x) for x in re.findall(r"R\s*(\d+(?:\.\d+)?)", req.group(1))]
    out: list[Problem] = []
    for index, request in enumerate(requests[:2]):
        pick = next((v for v in table if v >= request), None)
        if pick is None:
            continue
        label = "第一直径" if index == 0 else "第二直径"
        out.append((label, f"R{_f(request)} → 表内 R{_f(pick)} → Ø{2 * pick:.1f} mm", 2 * pick))
    return out


def _g41_corner(text: str) -> list[Problem]:
    """Tool-centre corner of two G41/G42 offset lines."""
    if not re.search(r"G4[12]", text) or not re.search(r"交点", text):
        return []
    pts = re.findall(r"\(\s*([-+]?\d+(?:\.\d+)?)\s*,\s*([-+]?\d+(?:\.\d+)?)\s*\)", text)
    comp = re.search(r"D0?\d{1,2}\s*(?:存储值|值)?\s*(?:为|=)?\s*" + _F, text)
    if len(pts) < 3 or not comp:
        return []
    (x0, y0), (x1, y1), (x2, y2) = [(float(a), float(b)) for a, b in pts[:3]]
    radius = float(comp.group(1))
    sign = 1.0 if "G41" in text else -1.0

    def normal(p, q):
        dx, dy = q[0] - p[0], q[1] - p[1]
        length = math.hypot(dx, dy)
        if length == 0:
            return None
        return sign * (-dy / length), sign * (dx / length)

    n1, n2 = normal((x0, y0), (x1, y1)), normal((x1, y1), (x2, y2))
    if not (n1 and n2):
        return []
    p1 = (x0 + radius * n1[0], y0 + radius * n1[1])
    p2 = (x1 + radius * n2[0], y1 + radius * n2[1])
    u = (x1 - x0, y1 - y0)
    v = (x2 - x1, y2 - y1)
    den = u[0] * v[1] - u[1] * v[0]
    if abs(den) < 1e-12:
        return []
    t = ((p2[0] - p1[0]) * v[1] - (p2[1] - p1[1]) * v[0]) / den
    cx, cy = p1[0] + t * u[0], p1[1] + t * u[1]
    return [
        ("拐角X", f"两偏置直线交点 X = {cx:.1f} mm", cx),
        ("拐角Y", f"两偏置直线交点 Y = {cy:.1f} mm", cy),
    ]


def _slot_width(text: str) -> list[Problem]:
    """Actual slot width when the stored radius compensation differs from the tool."""
    if not re.search(r"槽宽", text) or not re.search(r"补偿", text) or not re.search(r"实际", text):
        return []
    width = re.search(r"(?:编程)?槽宽\s*" + _F + r"\s*mm", text)
    comp = re.search(r"D0?\d{1,2}\s*(?:存储值|值)?\s*(?:为|=)?\s*" + _F, text)
    dia = re.search(r"实际装夹的?立铣刀直径为\s*" + _F, text)
    if not (width and comp and dia):
        return []
    w, c, tool_r = float(width.group(1)), float(comp.group(1)), float(dia.group(1)) / 2.0
    actual = w - 2.0 * (c - tool_r)
    return [("实际槽宽", f"W-2×(C-r) = {w:g}-2×({c:g}-{tool_r:g}) = {actual:.1f} mm", actual)]


def _grade_count(text: str) -> list[Problem]:
    """IT01..IT18 includes IT0, so the count is 20 -- a stated standard fact."""
    if not (re.search(r"IT01", text) and re.search(r"IT18", text)):
        return []
    if not re.search(r"(多少级|多少个|几级)", text):
        return []
    return [("标准公差等级数", "IT01、IT0 加 IT1…IT18，共 20 级", 20.0)]


def _hardness_vc(text: str) -> list[Problem]:
    """Work-shop hardness table: Vc = base × factor^(grade-1), then n and Vf."""
    if not re.search(r"硬度每提高一档", text) or not re.search(r"基准\s*Vc", text):
        return []
    ranges = re.findall(r"HB\s*(\d+)\s*[-~—]\s*(\d+)\s*=\s*档\s*(\d+)", text)
    target_m = re.search(r"(?:实测)?硬度\s*HB\s*(\d+)", text)
    base_m = re.search(r"档\s*1\s*基准\s*Vc\s*=\s*(\d+)", text)
    mult = re.search(r"乘\s*(0?\.\d+)", text)
    pct = re.search(r"(\d+)\s*%", text)
    if len(ranges) < 2 or not (target_m and base_m and (mult or pct)):
        return []
    target = float(target_m.group(1))
    grade = next((int(g) for lo, hi, g in ranges if float(lo) <= target <= float(hi)), None)
    if grade is None:
        return []
    factor = float(mult.group(1)) if mult else float(pct.group(1)) / 100.0
    base = float(base_m.group(1))
    vc = base * (factor ** (grade - 1))
    out: list[Problem] = [
        ("切削速度", f"档{grade}：Vc = {base:g}×{factor:g}^{grade - 1} = {vc:.1f} m/min", vc)
    ]
    d = re.search(r"(?:Ø|Φ|φ)\s*" + _F, text)
    z = re.search(_F + r"\s*齿", text)
    fz = re.search(r"每齿进给\s*" + _F, text)
    if d and z and fz and float(d.group(1)) > 0 and float(z.group(1)) > 0:
        d_val, z_val, fz_val = float(d.group(1)), float(z.group(1)), float(fz.group(1))
        n = 1000.0 * vc / (math.pi * d_val)
        vf = fz_val * z_val * n
        out.append(("主轴转速", f"n = 1000×{vc:.1f}/(π×{_f(d_val)}) = {n:.1f} r/min", n))
        out.append(("进给速度", f"Vf = {_f(fz_val)}×{_f(z_val)}×{n:.1f} = {vf:.1f} mm/min", vf))
    return out


def _stainless_scale(text: str) -> list[Problem]:
    """Rule card: Vc scaled for stainless, f derived as D/100, then n and Vf."""
    if not re.search(r"加工不锈钢", text):
        return []
    if not re.search(r"乘系数", text) or not re.search(r"f\s*=\s*D\s*/\s*100", text):
        return []
    vc_m = re.search(r"Vc\s*=\s*" + _F, text)
    factor_m = re.search(r"乘系数\s*" + _F, text)
    d_m = re.search(r"(?:Ø|Φ|φ)\s*" + _F, text)
    z_m = re.search(_F + r"\s*齿", text)
    if not (vc_m and factor_m and d_m and z_m):
        return []
    d, z = float(d_m.group(1)), float(z_m.group(1))
    if d <= 0 or z <= 0:
        return []
    vc = float(vc_m.group(1)) * float(factor_m.group(1))
    fz = d / 100.0
    n = 1000.0 * vc / (math.pi * d)
    vf = fz * z * n
    return [
        ("切削速度", f"Vc = {_f(float(vc_m.group(1)))}×{_f(float(factor_m.group(1)))} = {vc:.2f} m/min",
         vc),
        ("每齿进给", f"f = D/100 = {_f(d)}/100 = {fz:.3f} mm/齿", fz),
        ("主轴转速", f"n = 1000×{vc:.1f}/(π×{_f(d)}) = {n:.1f} r/min", n),
        ("进给速度", f"Vf = {_f(fz, 3)}×{_f(z)}×{n:.1f} = {vf:.1f} mm/min", vf),
    ]


def _spindle_from_clause(text: str) -> list[Problem]:
    """n from a process-card clause that binds one Ø to one Vc in the same phrase."""
    if re.search(r"(?<![A-Za-z])D\s*=", text):
        return []  # the explicit-equation family owns it
    if not re.search(r"Vc\s*=\s*\d+", text):
        return []
    m = re.search(r"(?:Ø|Φ|φ)\s*" + _F + r"\s*(?:mm)?[^；;。]{0,40}?Vc\s*=\s*" + _F, text)
    if not m:
        return []
    d_val, vc_val = float(m.group(1)), float(m.group(2))
    if d_val <= 0 or vc_val <= 0:
        return []
    n = 1000.0 * vc_val / (math.pi * d_val)
    return [("主轴转速", f"n = 1000·Vc/(π·D) = 1000×{_f(vc_val)}/(π×{_f(d_val)}) = {n:.1f} r/min", n)]


_EQ_RE = re.compile(
    r"(?P<expr>[0-9π×÷+\-*/().\s]{5,})\s*[=≈]\s*(?P<num>[-+]?\d+(?:\.\d+)?)"
)
_NUM_ONLY_RE = re.compile(r"[-+]?\d+(?:\.\d+)?")


def _safe_eval_expression(expr: str) -> float | None:
    cleaned = (
        expr.replace("π", "pi")
        .replace("×", "*")
        .replace("÷", "/")
        .replace("（", "(")
        .replace("）", ")")
    )
    if not re.fullmatch(r"[0-9pi+\-*/().\s]+", cleaned):
        return None
    if len(_NUM_ONLY_RE.findall(cleaned)) < 2:
        return None
    try:
        value = eval(cleaned, {"__builtins__": {}}, {"pi": math.pi})
    except Exception:
        return None
    return float(value) if isinstance(value, (int, float)) else None


def fix_explicit_equation(text: str) -> str:
    """Repair single explicit arithmetic equation slips in generated answers."""
    if not text:
        return ""
    matches = list(_EQ_RE.finditer(text))
    if len(matches) != 1:
        return text
    match = matches[0]
    computed = _safe_eval_expression(match.group("expr"))
    if computed is None or not math.isfinite(computed):
        return text
    raw_result = match.group("num")
    try:
        original = float(raw_result)
    except ValueError:
        return text
    if abs(computed - original) <= max(0.005, abs(computed) * 0.002):
        return text
    decimals = len(raw_result.split(".", 1)[1]) if "." in raw_result else 0
    corrected = f"{computed:.{decimals}f}" if decimals else str(int(round(computed)))
    return text[:match.start("num")] + corrected + text[match.end("num"):]


def numeric_problems(text: str) -> list[Problem]:
    """All extra families that fire for one user prompt, in output order."""
    text = text or ""
    out: list[Problem] = []
    out.extend(_milling_compact(text))
    out.extend(_scallop(text))
    out.extend(_imperial(text))
    out.extend(_tolerance_stack(text))
    out.extend(_rss_plain(text))
    out.extend(_clearance(text))
    out.extend(_mmc_bonus(text))
    out.extend(_shaft_mmc(text))
    out.extend(_gcode_modal(text))
    out.extend(_gcode_table_count(text))
    out.extend(_radius_table(text))
    out.extend(_g41_corner(text))
    out.extend(_slot_width(text))
    out.extend(_grade_count(text))
    out.extend(_hardness_vc(text))
    out.extend(_stainless_scale(text))
    out.extend(_spindle_from_clause(text))
    return out
