# -*- coding: utf-8 -*-
"""wm_derivation —— 语料/契约一致性补全器（derivation 注入 + 闸门字面归一）。

为什么需要这个模块
------------------
`wm_contract.RULES` 领域规则 F 明确规定：world_state 里**每个数值字段**都必须在
顶层 `derivation` 给出该字段的代入算式（字符串），算式只允许出现题面数值、定律
常数与本题中间量；`guard` 的 L2_SOLVER 通道完全依赖这段 dict 才能复算纠错。

但历史语料（data/sft/virtu_worldmodel*.jsonl 共 4120 条）derivation 覆盖率实测
为 **0**，即训练数据从未教过模型写 derivation，而 FEWSHOT 与 SYSTEM 都要求写。
结果是模型产出形态完全取决于采样运气，护栏的 L2 复算通道在真实题上经常无源可用。

同一批语料还有第二处不一致：闸门字段字面存在四套并存——
    契约 KEY_SCHEMA      : fos_gate = "pass" / "fail"
    wm_verifier.recompute: fos_gate = "PASS" / "FAIL"（已在本轮修正为 pass/fail）
    guard 强制改写       : fos_gate = "FOS>=1.5_PASS" / "FOS<1.5_FAIL"（已修正）
    历史语料             : fos_gate = "FOS>=1.5_pass" / "FOS<1.5_FAIL"
                            volume_conservation = "pass_cut_negative" / "FAIL"
                            tolerance_pass = "true"/"false" 字符串（契约已统一为布尔）
归一全靠 `GATE_ALIASES` 运行时兜底，护栏一旦不启用（纯模型直出、第三方判分器）
就判错。

本模块做两件事，且都保证**幂等**：
1. `derive(scenario)`：按 `wm_verifier.recompute` 同一口径生成 `{字段: 代入算式}`，
   算式求值结果与语料标签值一致，绝不制造"算式与标签自相矛盾"的脏样本。
2. `enrich(obj, scenario)`：把 derivation 与契约字面写回输出对象。

用法（生成器侧）：
    from wm_derivation import enrich
    return make_messages(u, enrich(ws, scenario), scenario)
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, Optional

try:
    from wm_contract import GATE_ALIASES
except Exception:  # pragma: no cover - 契约缺失时退化，不至于让生成器崩掉
    GATE_ALIASES = {}

# tolerance_pass 已统一为布尔（契约/schema/verifier 同型，2026-11-08），
# 不再做字符串化；此处留空集合表示没有需要特殊处理的布尔字面闸门。
BOOL_LITERAL_GATES: set = set()


def fmt(x: Any) -> str:
    """把数值写成算式里的字面量：整数不带小数点，避免 1e-05 这类科学计数法。"""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "0"
    if v == int(v) and abs(v) < 1e15:
        return str(int(v))
    s = repr(round(v, 12))
    if "e" in s or "E" in s:
        s = "{:.12f}".format(v).rstrip("0").rstrip(".")
    return s


def _sub(a: Any, b: Any) -> str:
    """a-b 的算式：减数一律加括号，避免 "--0.02" 这种非法写法。"""
    return f"{fmt(a)}-({fmt(b)})"


def _sum(terms) -> str:
    terms = list(terms)
    if not terms:
        return "0"
    return "+".join(fmt(t) for t in terms)


# --------------------------------------------------------------------------- #
# 各族算式（与 wm_verifier.recompute 同源口径）
# --------------------------------------------------------------------------- #
def _derive_removal(s: Dict[str, Any]) -> Dict[str, str]:
    doc = s.get("doc", s.get("ap"))
    woc = s.get("woc", s.get("ae"))
    vf, L, rho = s.get("vf"), s.get("L"), s.get("rho")
    stock_vol, fin_vol = s.get("stock_vol"), s.get("V", s.get("volume_mm3"))
    out: Dict[str, str] = {}
    # 与 wm_verifier.recompute 同优先级：成品体积差（CAD 真值）> doc*woc*L。
    # 旧实现缺 L 就整体放弃，stock-fin 口径的场景（真实 STEP 回归）永远无算式。
    if stock_vol is not None and fin_vol is not None:
        rem_expr = f"{fmt(stock_vol)}-({fmt(fin_vol)})"
    elif doc is not None and woc is not None and L is not None:
        rem_expr = f"{fmt(doc)}*{fmt(woc)}*{fmt(L)}"
    else:
        return out
    out["material_removed_mm3"] = rem_expr
    out["delta_volume_mm3"] = f"-({rem_expr})"
    if vf is not None and doc is not None and woc is not None:
        out["mrr_mm3_per_min"] = f"{fmt(doc)}*{fmt(woc)}*{fmt(vf)}"
    rho_s = fmt(rho if rho is not None else 7.85e-3)
    out["removed_mass_g"] = f"({rem_expr})*{rho_s}"
    if fin_vol is not None:
        out["resulting_mass_g"] = f"{fmt(fin_vol)}*{rho_s}"
    elif stock_vol is not None:
        out["resulting_mass_g"] = f"{fmt(stock_vol)}*{rho_s}-({rem_expr})*{rho_s}"
    return out


def _derive_roughness(s: Dict[str, Any]) -> Dict[str, str]:
    f, r_eps = s.get("f"), s.get("r_eps")
    if f is None or r_eps is None:
        return {}
    return {
        "feed_per_rev_mm": fmt(f),
        "nose_radius_mm": fmt(r_eps),
        "surface_roughness_ra_um": f"1000*{fmt(f)}*{fmt(f)}/(8*{fmt(r_eps)})",
    }


def _derive_fea_fos(s: Dict[str, Any]) -> Dict[str, str]:
    Sy, sigma = s.get("Sy"), s.get("sigma")
    if Sy is None or sigma is None:
        return {}
    out = {"yield_strength_mpa": fmt(Sy), "peak_von_mises_mpa": fmt(sigma)}
    if float(sigma) > 0:
        out["safety_factor"] = f"{fmt(Sy)}/{fmt(sigma)}"
    return out


def _derive_collision(s: Dict[str, Any]) -> Dict[str, str]:
    out = {}
    for k_input, k_ws in (("z_safe", "safe_plane_z_mm"),
                          ("z_min_rapid", "rapid_min_z_mm"),
                          ("stock_top", "stock_top_z_mm")):
        if s.get(k_input) is not None:
            out[k_ws] = fmt(s[k_input])
    return out


def _derive_tolerance(s: Dict[str, Any]) -> Dict[str, str]:
    tols = s.get("tols")
    up, lo = s.get("upper_dev"), s.get("lower_dev")
    out: Dict[str, str] = {}
    if tols:
        tols = list(tols)
        out["closed_loop_worstcase_halfwidth_mm"] = _sum(tols)
        out["closed_loop_rss_halfwidth_mm"] = (
            "sqrt(" + "+".join(f"({fmt(t)})*({fmt(t)})" for t in tols) + ")"
        )
    if up is not None and lo is not None:
        out["fit_clearance_mm"] = _sub(up, lo)
    if s.get("basic") is not None:
        out["basic_size_mm"] = fmt(s["basic"])
    return out


def _derive_geom_delta(s: Dict[str, Any]) -> Dict[str, str]:
    feat, before = s.get("feature_vol"), s.get("before")
    if feat is None:
        return {}
    out = {"feature_volume_mm3": fmt(feat), "delta_volume_mm3": f"-({fmt(feat)})"}
    if before is not None:
        out["before_volume_mm3"] = fmt(before)
        out["after_volume_mm3"] = _sub(before, feat)
    return out


def _derive_mass_props(s: Dict[str, Any]) -> Dict[str, str]:
    rho = s.get("rho")
    rho_s = fmt(rho) if rho is not None else None
    # 装配体口径：各零件体积相加
    if s.get("parts"):
        parts = list(s["parts"])
        vol_expr = _sum(parts)
        out = {"volume_mm3": vol_expr}
        if rho_s is not None:
            out["mass_g"] = f"({vol_expr})*{rho_s}"
        return out

    shape, p = s.get("shape"), s.get("params") or {}
    if shape == "box":
        l, w, h = p.get("l"), p.get("w"), p.get("h")
        if None in (l, w, h):
            return {}
        vol_expr = f"{fmt(l)}*{fmt(w)}*{fmt(h)}"
        out = {
            "volume_mm3": vol_expr,
            "centroid_mm_x": f"{fmt(l)}/2",
            "centroid_mm_y": f"{fmt(w)}/2",
            "centroid_mm_z": f"{fmt(h)}/2",
            # 面积二次矩口径（mm^4）：绕某轴用另两边作截面
            "inertia_ixx_mm4": f"{fmt(w)}*{fmt(h)}*{fmt(h)}*{fmt(h)}/12",
            "inertia_izz_mm4": f"{fmt(l)}*{fmt(w)}*{fmt(w)}*{fmt(w)}/12",
        }
        if rho_s is not None:
            out["mass_g"] = f"({vol_expr})*{rho_s}"
        return out
    if shape == "cylinder":
        r, h = p.get("r"), p.get("h")
        if None in (r, h):
            return {}
        vol_expr = f"pi*{fmt(r)}*{fmt(r)}*{fmt(h)}"
        out = {
            "volume_mm3": vol_expr,
            "centroid_mm_z": f"{fmt(h)}/2",
            "inertia_ixx_mm4": f"pi*{fmt(r)}*{fmt(r)}*{fmt(r)}*{fmt(r)}/4",
            # 绕轴线（z）的极惯性矩是 pi*r^4/2；旧 /4 与修正后的 mass_props_csg
            # 标签差一倍，会造出"算式与标签自相矛盾"的脏样本（2026-11-08 修）。
            "inertia_izz_mm4": f"pi*{fmt(r)}*{fmt(r)}*{fmt(r)}*{fmt(r)}/2",
        }
        if rho_s is not None:
            out["mass_g"] = f"({vol_expr})*{rho_s}"
        return out
    return {}


def _derive_design(s: Dict[str, Any]) -> Dict[str, str]:
    """法兰盘设计：V = pi*(R^2-r^2)*t - n*pi*r_h^2*t"""
    ro, ri = s.get("r_out"), s.get("r_bore")
    t, n, rh, rho = s.get("t"), s.get("n_holes"), s.get("r_hole"), s.get("rho")
    if None in (ro, ri, t, n, rh):
        return {}
    vol_expr = (f"pi*({fmt(ro)}*{fmt(ro)}-{fmt(ri)}*{fmt(ri)})*{fmt(t)}"
                f"-{fmt(n)}*pi*{fmt(rh)}*{fmt(rh)}*{fmt(t)}")
    out = {"volume_mm3": vol_expr}
    if rho is not None:
        out["mass_g"] = f"({vol_expr})*{fmt(rho)}"
        out["mass_kg"] = f"({vol_expr})*{fmt(rho)}/1000"
    return out


def _derive_process(s: Dict[str, Any]) -> Dict[str, str]:
    D, L, ap, f, vc, r_eps = (s.get("D"), s.get("L"), s.get("ap"),
                              s.get("f"), s.get("vc"), s.get("r_eps"))
    out: Dict[str, str] = {}
    if D is None or vc is None:
        return out
    rpm_expr = f"1000*{fmt(vc)}/(pi*{fmt(D)})"
    out["spindle_rpm"] = rpm_expr
    if f is not None:
        feed_expr = f"{fmt(f)}*({rpm_expr})"
        out["feed_rate_mm_per_min"] = feed_expr
        if ap is not None:
            out["mrr_mm3_per_min"] = f"{fmt(ap)}*{fmt(f)}*{fmt(vc)}*1000"
        if L is not None:
            out["cut_time_min"] = f"({fmt(L)})/({feed_expr})"
    if f is not None and r_eps is not None:
        out["surface_roughness_ra_um"] = f"1000*{fmt(f)}*{fmt(f)}/(8*{fmt(r_eps)})"
    return out


def _derive_adapt_machine(s: Dict[str, Any]) -> Dict[str, str]:
    D, vc, n_max = s.get("D"), s.get("vc"), s.get("n_max")
    if D is None or vc is None:
        return {}
    out = {"required_spindle_rpm": f"1000*{fmt(vc)}/(pi*{fmt(D)})"}
    # 契约规则 F：每个数值字段都要有算式；照抄量也是绑定（恒等式），
    # 缺了这两条，v2 语料的 machine_max_rpm/recommended_vc 永远无 derivation。
    if n_max is not None:
        out["machine_max_rpm"] = fmt(n_max)
    out["recommended_vc_m_per_min"] = fmt(vc)
    return out


def _derive_adapt_material(s: Dict[str, Any]) -> Dict[str, str]:
    Sy, sigma = s.get("Sy"), s.get("sigma")
    if Sy is None or sigma is None or float(sigma) <= 0:
        return {}
    return {
        "yield_strength_mpa": fmt(Sy),
        "peak_von_mises_mpa": fmt(sigma),
        "safety_factor": f"{fmt(Sy)}/{fmt(sigma)}",
    }


DERIVERS = {
    "removal": _derive_removal,
    "roughness": _derive_roughness,
    "fea_fos": _derive_fea_fos,
    "collision": _derive_collision,
    "tolerance": _derive_tolerance,
    "geom_delta": _derive_geom_delta,
    "mass_props": _derive_mass_props,
    "design": _derive_design,
    "process": _derive_process,
    "adapt_machine": _derive_adapt_machine,
    "adapt_material": _derive_adapt_material,
}


def derive(scenario: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """按场景生成 {字段: 代入算式}；无法识别场景时返回空 dict。"""
    if not isinstance(scenario, dict):
        return {}
    task = scenario.get("task")
    fn = DERIVERS.get(task)
    if fn is None:
        return {}
    inputs = scenario.get("inputs") or {}
    try:
        return {k: v for k, v in fn(inputs).items() if isinstance(v, str) and v}
    except Exception:
        return {}


# --------------------------------------------------------------------------- #
# 闸门字面归一
# --------------------------------------------------------------------------- #
def _canon_gate(key: str, value: Any) -> Any:
    """按 wm_contract.GATE_ALIASES 把闸门值归一成契约字面。"""
    if key in BOOL_LITERAL_GATES:
        if isinstance(value, bool):
            return "true" if value else "false"
        s = str(value).strip().lower()
        return "true" if s in ("true", "1", "pass", "yes") else "false"
    table = GATE_ALIASES.get(key) or {}
    if isinstance(value, bool):
        s = "true" if value else "false"
    else:
        s = str(value).strip().lower()
    if s in table:
        return table[s]
    # 表里没有的长字面：用包含关系兜底，仍无法判定时回 pass/fail 二元
    if s in ("pass", "fail"):
        return s
    if "fail" in s:
        return "fail"
    if "pass" in s:
        return "pass"
    return value


def norm_gates(obj: Any) -> Any:
    """就地归一 obj（含 world_state 嵌套形态）里的闸门字面，幂等。"""
    if not isinstance(obj, dict):
        return obj
    ws = obj.get("world_state")
    targets = [obj]
    if isinstance(ws, dict):
        targets.append(ws)
    for tgt in targets:
        for key in ("fos_gate", "volume_conservation", "autodiff"):
            if key in tgt:
                tgt[key] = _canon_gate(key, tgt[key])
    return obj


# --------------------------------------------------------------------------- #
# 对外主入口
# --------------------------------------------------------------------------- #
def _numeric_only(deriv: Dict[str, str], ws: Dict[str, Any]) -> Dict[str, str]:
    """只保留 world_state 里真实存在、且为数值的字段，避免算式指向不存在的键。"""
    out = {}
    for k, expr in deriv.items():
        if k in ws and isinstance(ws[k], (int, float)) and not isinstance(ws[k], bool):
            out[k] = expr
    return out


def enrich(obj: Dict[str, Any], scenario: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """给输出对象补 derivation 并把闸门字面归一为契约字面。

    - 幂等：已有 derivation 时不再覆盖（保留模型/人工写好的算式）。
    - world_state 为 None（invalid 契约）时不做任何注入。
    """
    if not isinstance(obj, dict):
        return obj
    norm_gates(obj)
    ws = obj.get("world_state")
    if not isinstance(ws, dict) or obj.get("derivation"):
        return obj
    deriv = _numeric_only(derive(scenario), ws)
    if deriv:
        obj["derivation"] = deriv
    return obj


__all__ = ["derive", "enrich", "norm_gates", "fmt"]
