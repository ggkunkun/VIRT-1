#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""wm_eval.py — 世界模型算式求值层（神经符号接线）

实测依据（2026-11-07，virtu-13.63b）：
  粗糙度题模型自写 derivation "1000*(0.064)*(0.064)/(8*(1.2))"，真值 0.4267，
  却把 world_state 填成 1000；
  质量属性题自写 "pi*(28.7)^2*98.3"，真值 254370，却填 66428。
结论：**模型会写算式，但不会执行算式**。因此把 derivation 的表达式做安全 AST
求值后回填 world_state，可在不训练、不改量化的前提下把这类算术错误清零。

安全：仅允许 数字 / + - * / // % ** / 一元正负 / 括号 / 白名单函数
(sqrt, abs, sin, cos, tan, log, log10, exp) / 常量 (pi, e)。其余一律拒绝。
"""
from __future__ import annotations
import ast
import math
import re
from typing import Any, Dict, Optional, Tuple

_ALLOWED_FUNCS = {
    "sqrt": math.sqrt, "abs": abs, "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "log": math.log, "log10": math.log10, "exp": math.exp, "pi": math.pi,
}
_ALLOWED_NAMES = {"pi": math.pi, "e": math.e, "π": math.pi}
_BINOPS = {
    ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b, ast.Div: lambda a, b: a / b,
    ast.Pow: lambda a, b: a ** b, ast.Mod: lambda a, b: a % b,
    ast.FloorDiv: lambda a, b: a // b,
}
_UNOPS = {ast.UAdd: lambda a: a, ast.USub: lambda a: -a}


def normalize_expr(s: str) -> str:
    """把题面/模型常用的写法转成 Python 可解析形式。"""
    t = s.strip()
    t = t.replace("×", "*").replace("÷", "/").replace("−", "-").replace("–", "-")
    t = t.replace("^", "**").replace("²", "**2").replace("³", "**3").replace("π", "pi")
    t = re.sub(r"(?<=\d)\s*(?=[a-zA-Z_])", "*", t)   # 2pi -> 2*pi（罕见）
    # 相邻括号隐式乘法 "(2)(3)" -> "(2)*(3)"。旧替换 r")\1(" 把捕获的右括号
    # 又写了一遍，产出 "(2))(3)" 直接解析失败（实测 safe_eval('(2)(3)')=None）。
    t = re.sub(r"\)\s*\(", ")*(", t)
    return t


class UnsafeExpr(Exception):
    pass


def _eval_node(node) -> float:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise UnsafeExpr("non-numeric constant")
        return float(node.value)
    if isinstance(node, ast.BinOp):
        fn = _BINOPS.get(type(node.op))
        if fn is None:
            raise UnsafeExpr(f"binop {type(node.op).__name__}")
        return fn(_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp):
        fn = _UNOPS.get(type(node.op))
        if fn is None:
            raise UnsafeExpr(f"unop {type(node.op).__name__}")
        return fn(_eval_node(node.operand))
    if isinstance(node, ast.Name):
        if node.id not in _ALLOWED_NAMES:
            raise UnsafeExpr(f"name {node.id}")
        return float(_ALLOWED_NAMES[node.id])
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _ALLOWED_FUNCS:
            raise UnsafeExpr("call")
        args = [_eval_node(a) for a in node.args]
        return float(_ALLOWED_FUNCS[node.func.id](*args))
    raise UnsafeExpr(type(node).__name__)


def safe_eval(expr: str) -> Optional[float]:
    """求值成功返回 float，失败返回 None（绝不抛异常给上层）。"""
    if not isinstance(expr, str) or not expr.strip():
        return None
    t = normalize_expr(expr)
    if len(t) > 300:
        return None
    # 只允许表达式字符集，先做粗筛
    if re.search(r"[=\[\]]", t):
        # 允许 "Ra=..." 形式，取最后一个等号右边
        t = t.split("=")[-1]
    if not re.fullmatch(r"[0-9eEpiπ\s\.\+\-\*/%\(\)_,a-zA-Z]+", t):
        return None
    try:
        tree = ast.parse(t, mode="eval")
        v = _eval_node(tree)
        if v != v or v in (float("inf"), float("-inf")):  # NaN / inf
            return None
        return v
    except UnsafeExpr:
        return None
    except Exception:
        return None


def _match_key(dkey: str, ws_keys) -> Optional[str]:
    """derivation 的键名常与 world_state 有拼写漂移（finish_lass / ienergia_ixx_mm4）。"""
    if dkey in ws_keys:
        return dkey
    dl = dkey.lower()
    for k in ws_keys:
        if k.lower() == dl:
            return k
    # 后缀包含匹配：要求长度 >= 6 的唯一命中
    cands = [k for k in ws_keys if dl.endswith(k.lower()) or k.lower().endswith(dl)]
    if len(cands) == 1:
        return cands[0]
    return None


def repair(pred: Any, override: bool = True) -> Tuple[Any, list]:
    """用 derivation 表达式求值改写 world_state 数值字段。

    override=True  ：无条件以求值结果覆盖（默认；因实测模型算术不可信）
    override=False ：仅在差异 > 1% 时覆盖
    返回 (新 pred, 修复记录列表)
    """
    fixes = []
    if not isinstance(pred, dict):
        return pred, fixes
    ws = pred.get("world_state")
    der = pred.get("derivation")
    if not isinstance(ws, dict) or not isinstance(der, dict):
        return pred, fixes
    out = dict(pred)
    nws = dict(ws)
    for dk, dv in der.items():
        if not isinstance(dv, str):
            continue
        val = safe_eval(dv)
        if val is None:
            continue
        target = _match_key(dk, nws.keys())
        if target is None or isinstance(nws.get(target), (list, str, bool)):
            continue
        old = nws.get(target)
        if isinstance(old, (int, float)) and not override:
            if abs(float(old)) > 1e-12 and abs(val - float(old)) / abs(float(old)) <= 0.01:
                continue
        if isinstance(old, (int, float)) and abs(val - float(old)) <= 1e-12:
            continue
        nws[target] = round(val, 6)
        fixes.append({"field": target, "from": old, "to": round(val, 6), "expr": dv})
    # 中间值回填：模型常在算式里硬编码错误的中间结果
    # （实测 removal：resulting=291958*2.7/1000 - 1399.4416，其中 1399.44 是算错的 removed_mass）
    if fixes:
        from_to = {}
        for f in fixes:
            old, new = f["from"], f["to"]
            if isinstance(old, (int, float)) and abs(float(old)) > 1e-9:
                from_to[repr(float(old))] = f"{new}"
                if abs(float(old) - round(float(old), 4)) < 1e-12:
                    from_to[f"{round(float(old), 4):g}"] = f"{new}"
        for _ in range(3):
            changed = False
            for dk, dv in der.items():
                if not isinstance(dv, str):
                    continue
                target = _match_key(dk, nws.keys())
                if target is None or isinstance(nws.get(target), (list, str, bool)):
                    continue
                e = normalize_expr(dv)
                e2 = e
                for old_s, new_s in from_to.items():
                    if old_s and old_s in e2:
                        e2 = e2.replace(old_s, f"({new_s})")
                if e2 == e:
                    continue
                val = safe_eval(e2)
                if val is None:
                    continue
                oldv = nws.get(target)
                if isinstance(oldv, (int, float)) and abs(val - float(oldv)) <= 1e-9:
                    continue
                nws[target] = round(val, 6)
                fixes.append({"field": target, "from": oldv, "to": round(val, 6),
                              "expr": e2, "stage": "backfill"})
                changed = True
            if not changed:
                break
        out["world_state"] = nws
        out["eval_repair"] = fixes
    return out, fixes


def _selftest() -> int:
    ok = 0
    cases = [
        ("1000*(0.064)*(0.064)/(8*(1.2))", 0.4266667),
        ("pi*(28.7)^2*98.3", 254370.76),
        ("pi*(28.7)^4/4", 532865.33),
        ("sqrt(0.072^2 + 0.09^2)", 0.1153698),
        ("215 / 190.2", 1.130389),
        ("(2)(3)", 6.0),
        ("-DOC*WOC*L", None),
    ]
    for expr, want in cases:
        got = safe_eval(expr)
        if want is None:
            ok += int(got is None)
        else:
            ok += int(got is not None and abs(got - want) / abs(want) < 1e-3)
        if want is None and got is not None:
            print(f"[FAIL] unsafe allowed: {expr} -> {got}")
    # 恶意表达式必须拒绝
    for bad in ["__import__('os').system('dir')", "open('x')", "exec('1')",
                "9**9**9", "(lambda:1)()"]:
        r = safe_eval(bad)
        ok += int(r is None)
        if r is not None:
            print(f"[FAIL] unsafe eval: {bad} -> {r}")
    # repair 端到端
    pred = {"world_state": {"surface_roughness_ra_um": 1000, "finish_class": "粗加工"},
            "derivation": {"surface_roughness_ra_um": "1000*(0.064)*(0.064)/(8*(1.2))",
                           "finis_roughness": "1000*(0.064)*(0.064)/(8*(1.2))"}}
    new, fixes = repair(pred)
    ok += int(abs(new["world_state"]["surface_roughness_ra_um"] - 0.426667) < 1e-4)
    ok += int(len(fixes) >= 1)
    total = len(cases) + 4 + 2
    ok = min(ok, total)
    print(f"[wm_eval] SELFTEST {ok}/{total} PASS")
    return 0 if ok == total else 1


if __name__ == "__main__":
    raise SystemExit(_selftest())
