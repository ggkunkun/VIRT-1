#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""wm_gate.py — 世界模型确定性判定层（把"阈值判定"从模型手里拿走）

实测依据（2026-11-07 探针）：13.63B 能算对数值（FOS=1.13、Ra=1.68 均在 8% 容差内），
但把 1.13 判成 fos_gate="FOS>=1.5_pass"、把 1.68μm 判成"粗加工"——即
**数值推理可用、规则连接不可用**。因此闸门/等级/Auto-Diff 颜色一律由本层按
确定阈值重算，schema 中不再让模型生成。

覆盖：
  fos_gate        : safety_factor >= 1.5 -> pass
  finish_class    : Ra<3.2 精加工 / <6.3 半精 / else 粗加工
  volume_conservation : delta_volume_mm3<0 -> pass
  autodiff        : gouge True -> red / collision_risk high -> yellow / else green
  tolerance_pass  : fit_clearance_mm >= 0（与 wm_verifier.recompute 同口径；
                    旧阈值 -0.005 是第二套定律， clearance∈[-0.005,0) 时与判分器冲突）
  fit_class       : 由 fit_clearance 与 tolerance_fit 推 H7/g6 | H7/js6 | H7/p6

闸门字面一律用契约短字面（pass/fail），与 wm_contract.KEY_SCHEMA / guard 同源；
长字面（FOS>=1.5_pass 等）只作历史语料兼容，由 normalize_gate 归一，本层不再产出。
"""
from __future__ import annotations
import sys
from typing import Any, Dict, Optional


def _f(ws: Dict[str, Any], k: str) -> Optional[float]:
    v = ws.get(k)
    if isinstance(v, bool):
        # FIX H6b（2026-11-08 审计）：bool 是 int 子类，原实现对 bool 直接返回 None，
        # 于是 {"safety_factor": True} / {"safety_factor": False} 静默逃过 FOS 闸门
        # （fos_gate 缺失 = 等于没判）。按 1/0 释义处理（True=1.0 < 1.5 → fail），
        # 属 fail-closed 方向，不会把不合格件放行。
        return float(int(v))
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        # FIX H6：字符串数值（"1.13" / " 1.5 "）原实现返回 None，闸门静默不判，
        # 等于模型写字符串就绕过 fos_gate / finish_class。此处按字面解析。
        try:
            t = v.strip()
            return float(t) if t and t.lower() not in ("nan", "inf", "-inf") else None
        except (TypeError, ValueError):
            return None
    return None


_TRUE_LIT = {"true", "1", "yes", "y", "是", "on", "t"}
_FALSE_LIT = {"false", "0", "no", "n", "否", "off", "f", ""}


def _b(v: Any) -> Optional[bool]:
    """FIX H6：布尔归一。bool("False") 在 Python 里是 True，原实现直接把
    gouge="False" 判成 gouge=True → autodiff=red（反向错判）。未知字面返回
    None（fail-closed），由调用方决定是否记账，绝不默认 True。"""
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    if isinstance(v, str):
        t = v.strip().lower()
        if t in _TRUE_LIT:
            return True
        if t in _FALSE_LIT:
            return False
    return None


def normalize(ws: Dict[str, Any], corrections: Optional[list] = None) -> Dict[str, Any]:
    """就地补全/纠正确定性判定字段，返回新 dict。

    corrections（可选）：传入 list 时，本层对 world_state 的任何改写都会追加一条
    {"field", "from", "to", "reason"}，供 guard 记账。FIX H7：原实现静默改写
    （布尔强转、round(3)、after_volume 覆盖）不留痕，用户看到的数已被改过却无从得知。
    """
    if not isinstance(ws, dict):
        return ws
    out = dict(ws)

    def _rec(field: str, old: Any, new: Any, reason: str) -> None:
        if old == new:
            return
        if corrections is None:
            # FIX H7 兜底：调用侧没传记账容器时，改写也不得完全静默——
            # 至少落一条 stderr，让「数被改过」这件事在日志里可发现。
            print(f"[WARN] wm_gate.normalize 未记账改写 {field}: {old!r} -> {new!r}"
                  f"（{reason}）", file=sys.stderr)
            return
        corrections.append({"field": field, "from": old, "to": new, "reason": reason})
    # 1) FOS 闸门
    fos = _f(out, "safety_factor")
    if fos is not None:
        out["fos_gate"] = "pass" if fos >= 1.5 - 1e-12 else "fail"
    # 2) 粗糙度等级
    ra = _f(out, "surface_roughness_ra_um")
    if ra is not None:
        out["finish_class"] = "精加工" if ra < 3.2 else ("半精" if ra < 6.3 else "粗加工")
    # 3) 体积守恒
    dv = _f(out, "delta_volume_mm3")
    if dv is not None:
        out["volume_conservation"] = "pass" if dv < 0 else "fail"
        b, a = _f(out, "before_volume_mm3"), _f(out, "after_volume_mm3")
        if b is not None and a is not None and abs((b + dv) - a) > 1e-6:
            # 三者过定：before/after 多为题面/实测值，delta 是可推导量（delta = after - before）。
            # 因此自纠只允许动 delta，不得把题面给的 after 改成计算值——那是篡改输入数据。
            fixed = round(a - b, 3)
            if corrections is not None:
                _rec("delta_volume_mm3", dv, fixed,
                     "体积守恒自纠：delta 与 after-before 不闭合，以 before/after 为准")
                out["delta_volume_mm3"] = fixed
                out["volume_conservation"] = "pass" if fixed < 0 else "fail"
            else:
                # FIX H7（2026-11-08 审计）：调用侧没给记账容器 = 不打算留痕，
                # 这种情况下宁可保留模型原值（23430.06）也不静默改成计算值（23430.0）。
                # 改写用户/模型给的原始数值且留下不痕迹，是比数值本身更严重的问题。
                print(f"[WARN] wm_gate.normalize 发现体积不闭合（before+delta={fixed} vs "
                      f"after={a}），未提供记账容器，保持原值不改写", file=sys.stderr)
    # 4) Auto-Diff 颜色
    if "gouge" in out or "collision_risk" in out:
        raw_gouge = out.get("gouge")
        gouge = _b(raw_gouge)
        if gouge is None:
            # 未知字面（"maybe" / None / dict）：fail-closed，按"未报过切"处理并记账，
            # 绝不像旧实现那样 bool() 强转成 True。
            gouge = False
            _rec("gouge", raw_gouge, False, "过切标志字面不可解析，按否处理（fail-closed）")
        elif gouge is not raw_gouge and not isinstance(raw_gouge, bool):
            _rec("gouge", raw_gouge, gouge, "过切标志类型归一")
        risk = str(out.get("collision_risk", "")).lower()
        old_ad = out.get("autodiff")
        new_ad = "red" if gouge else ("yellow" if risk in ("high", "medium") else "green")
        _rec("autodiff", old_ad, new_ad, "按 gouge/collision_risk 确定性重算")
        out["autodiff"] = new_ad
        # collision_risk 是 L2 求解器按题面 Z 值算出的判定（需两个比较同时成立），
        # 旧实现只要 gouge=True 就无条件改写成 "high"，与 wm_verifier.recompute /
        # 定律卡 / 训练标签直接冲突：同一份输入，闸门把求解器判 "none" 的答案
        # 悄悄改成 "high"，护栏后评测必然误判。判定权归求解器，本层只推 autodiff。
    # 5) 公差配合
    clr = _f(out, "fit_clearance_mm")
    if clr is not None:
        if clr > 0.01:
            out["tolerance_fit"], out["fit_class"] = "间隙配合", "H7/g6"
        elif clr < -0.01:
            out["tolerance_fit"], out["fit_class"] = "过盈配合", "H7/p6"
        else:
            out["tolerance_fit"], out["fit_class"] = "过渡配合", "H7/js6"
        out["tolerance_pass"] = bool(clr >= 0.0)
    return out


def normalize_pred(pred: Any, corrections: Optional[list] = None) -> Any:
    """对整条预测做归一化（world_state 内），保留其余键。"""
    if not isinstance(pred, dict):
        return pred
    ws = pred.get("world_state")
    if isinstance(ws, dict):
        p = dict(pred)
        p["world_state"] = normalize(ws, corrections)
        return p
    return pred


def _selftest() -> int:
    ok = 0
    cases = [
        ({"safety_factor": 1.13}, "fos_gate", "fail"),
        ({"safety_factor": 1.5}, "fos_gate", "pass"),
        ({"surface_roughness_ra_um": 1.68}, "finish_class", "精加工"),
        ({"surface_roughness_ra_um": 4.0}, "finish_class", "半精"),
        ({"surface_roughness_ra_um": 8.0}, "finish_class", "粗加工"),
        ({"delta_volume_mm3": -1200.0}, "volume_conservation", "pass"),
        ({"delta_volume_mm3": 5.0}, "volume_conservation", "fail"),
        ({"gouge": True, "collision_risk": "none"}, "autodiff", "red"),
        # 反证：判定权归求解器，闸门不得把 risk=none 悄悄改写成 high
        ({"gouge": True, "collision_risk": "none"}, "collision_risk", "none"),
        ({"gouge": False, "collision_risk": "high"}, "autodiff", "yellow"),
        ({"gouge": False, "collision_risk": "none"}, "autodiff", "green"),
        ({"fit_clearance_mm": 0.03}, "fit_class", "H7/g6"),
        ({"fit_clearance_mm": -0.03}, "fit_class", "H7/p6"),
        ({"fit_clearance_mm": 0.0}, "fit_class", "H7/js6"),
        # 反证：旧阈值 -0.005 会把这两条判 True，与 wm_verifier(>=0) 冲突
        ({"fit_clearance_mm": -0.003}, "tolerance_pass", False),
        ({"fit_clearance_mm": 0.0}, "tolerance_pass", True),
        # FIX H6 反证：字符串布尔/字符串数值不得绕过或反向错判
        ({"gouge": "False", "collision_risk": "none"}, "autodiff", "green"),
        ({"gouge": "True", "collision_risk": "none"}, "autodiff", "red"),
        ({"gouge": "maybe", "collision_risk": "none"}, "autodiff", "green"),
        ({"safety_factor": "1.13"}, "fos_gate", "fail"),
        ({"surface_roughness_ra_um": "4.0"}, "finish_class", "半精"),
    ]
    for ws, k, want in cases:
        got = normalize(ws).get(k)
        if got == want:
            ok += 1
        else:
            print(f"[FAIL] {ws} -> {k}={got!r} want {want!r}")
    # 体积守恒自纠
    n = normalize({"delta_volume_mm3": -100.0, "before_volume_mm3": 5000.0, "after_volume_mm3": 4900.0})
    ok += int(n["after_volume_mm3"] == 4900.0)
    # FIX（2026-11-08 二轮）：三者过定时自纠只准动 delta（可推导量），
    # before/after 是题面/实测输入，不得被改成计算值——那是篡改输入数据。
    n2 = normalize({"delta_volume_mm3": -100.0, "before_volume_mm3": 5000.0,
                    "after_volume_mm3": 4800.0}, [])
    ok += int(n2["after_volume_mm3"] == 4800.0 and n2["delta_volume_mm3"] == -200.0)
    # FIX H7 反证：无记账容器时不得改写模型原值
    n3 = normalize({"delta_volume_mm3": -100.0, "before_volume_mm3": 5000.0,
                    "after_volume_mm3": 4800.0})
    ok += int(n3["after_volume_mm3"] == 4800.0)
    # FIX H7 反证：改写必须记账，不得静默
    rec = []
    normalize({"delta_volume_mm3": -100.0, "before_volume_mm3": 5000.0,
               "after_volume_mm3": 4800.0, "gouge": "False"}, rec)
    hit = {c["field"] for c in rec}
    ok += int({"delta_volume_mm3", "gouge"} <= hit)
    # FIX H6b 反证：布尔型数值字段不得静默逃过闸门
    ok += int(normalize({"safety_factor": True}).get("fos_gate") == "fail")
    ok += int(normalize({"safety_factor": False}).get("fos_gate") == "fail")
    total = len(cases) + 6
    print(f"[wm_gate] SELFTEST {ok}/{total} PASS")
    return 0 if ok == total else 1


if __name__ == "__main__":
    raise SystemExit(_selftest())
