"""约束注册表：内置工艺约束 + 动态扩展的自定义表达式约束（AST 白名单安全求值）。

每条约束返回归一化违反量 g（g <= 0 可行）。新增约束只需 ``registry.register(...)``，求解器无需改动。
"""
from __future__ import annotations

import ast
import math
import operator
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional

from cam_autogen.contracts import CustomConstraint

ConstraintFn = Callable[[Dict[str, float]], Optional[float]]

ALLOWED_VARS = {"Vc", "f", "fz", "ap", "ae", "n", "vf", "D", "z", "Pc", "Ra", "T_life", "defl", "mrr", "t_cut",
                "torque", "n_max", "P_max", "vf_max", "Ra_req", "defl_allow"}
_BIN = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.Pow: operator.pow}
_FUN = {"min": min, "max": max, "sqrt": math.sqrt, "abs": abs, "log": math.log}


@dataclass
class Constraint:
    name: str
    fn: ConstraintFn
    applies_to: List[str] = field(default_factory=list)
    hard: bool = True
    description: str = ""

    def applies(self, category: str) -> bool:
        return not self.applies_to or category in self.applies_to


class ExpressionError(ValueError):
    pass


def compile_expression(expr: str) -> Callable[[Dict[str, float]], float]:
    """把 'lhs <= rhs' 编译为 g(ctx) = (lhs - rhs) / max(|rhs|, 1)。只允许白名单节点。"""
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise ExpressionError(f"约束表达式语法错误: {expr!r}") from exc
    cmp = tree.body
    if not isinstance(cmp, ast.Compare) or len(cmp.ops) != 1 or not isinstance(cmp.ops[0], (ast.LtE, ast.Lt, ast.GtE, ast.Gt)):
        raise ExpressionError(f"约束必须是单个 <=/>=/</> 比较: {expr!r}")

    def check(node: ast.AST) -> None:
        if isinstance(node, ast.BinOp):
            if type(node.op) not in _BIN:
                raise ExpressionError(f"不允许的运算符 {type(node.op).__name__}")
            check(node.left)
            check(node.right)
        elif isinstance(node, ast.UnaryOp):
            if not isinstance(node.op, (ast.USub, ast.UAdd)):
                raise ExpressionError("不允许的一元运算")
            check(node.operand)
        elif isinstance(node, ast.Name):
            if node.id not in ALLOWED_VARS:
                raise ExpressionError(f"未知变量 {node.id!r}；允许: {sorted(ALLOWED_VARS)}")
        elif isinstance(node, ast.Constant):
            if not isinstance(node.value, (int, float)) or isinstance(node.value, bool):
                raise ExpressionError("只允许数值常量")
        elif isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in _FUN or node.keywords:
                raise ExpressionError("只允许调用 min/max/sqrt/abs/log")
            for a in node.args:
                check(a)
        else:
            raise ExpressionError(f"不允许的语法节点 {type(node).__name__}")

    check(cmp.left)
    check(cmp.comparators[0])
    sign = 1.0 if isinstance(cmp.ops[0], (ast.LtE, ast.Lt)) else -1.0

    def ev(node: ast.AST, ctx: Dict[str, float]) -> float:
        if isinstance(node, ast.BinOp):
            return _BIN[type(node.op)](ev(node.left, ctx), ev(node.right, ctx))
        if isinstance(node, ast.UnaryOp):
            v = ev(node.operand, ctx)
            return -v if isinstance(node.op, ast.USub) else v
        if isinstance(node, ast.Name):
            return float(ctx.get(node.id, 0.0))
        if isinstance(node, ast.Constant):
            return float(node.value)
        return float(_FUN[node.func.id](*[ev(a, ctx) for a in node.args]))  # type: ignore[union-attr]

    def g(ctx: Dict[str, float]) -> float:
        lhs, rhs = ev(cmp.left, ctx), ev(cmp.comparators[0], ctx)
        return sign * (lhs - rhs) / max(abs(rhs), 1.0)

    return g


def _ratio(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None or b <= 0:
        return None
    return a / b - 1.0


def builtin_constraints() -> List[Constraint]:
    cut_cats = None  # 全部
    return [
        Constraint("spindle_speed", lambda c: _ratio(c["n"], c["n_max"]), description="主轴转速 ≤ 机床/动力刀上限"),
        Constraint("spindle_power", lambda c: _ratio(c["Pc"], 0.8 * c["P_max"]), description="切削功率 ≤ 80% 额定功率"),
        Constraint("feed_rate", lambda c: _ratio(c["vf"], c["vf_max"]), description="进给速度 ≤ 机床最大切削进给"),
        Constraint("torque", lambda c: _ratio(c["torque"], c.get("torque_max")) if c.get("torque_max") else None,
                   description="主轴扭矩 ≤ 额定扭矩"),
        Constraint("surface_roughness", lambda c: _ratio(c["Ra"], c["Ra_req"]) if c.get("Ra_req") else None,
                   description="预测 Ra ≤ 要求 Ra"),
        Constraint("deflection", lambda c: _ratio(c["defl"], c["defl_allow"]) if c.get("defl_allow") else None,
                   description="刀具/工件挠度 ≤ 允许值（精加工=0.3×公差）"),
        Constraint("tool_life", lambda c: _ratio(c["T_req"], c["T_life"]), description="刀具寿命 ≥ 本工序所需（≥5min）"),
        Constraint("min_chip_thickness", lambda c: _ratio(c["h_min"], c["h"]) if c.get("h") else None,
                   description="切屑厚度 ≥ 最小值（防挤压/硬化）"),
    ]


class ConstraintRegistry:
    def __init__(self, constraints: Optional[Iterable[Constraint]] = None):
        self._items: Dict[str, Constraint] = {}
        for c in constraints if constraints is not None else builtin_constraints():
            self.register(c)

    def register(self, c: Constraint) -> None:
        self._items[c.name] = c

    def disable(self, names: Iterable[str]) -> None:
        for n in names:
            self._items.pop(n, None)

    def add_custom(self, cc: CustomConstraint) -> None:
        g = compile_expression(cc.expr)
        self.register(Constraint(cc.name, g, list(cc.applies_to), cc.hard, f"custom: {cc.expr}"))

    def names(self) -> List[str]:
        return list(self._items)

    def evaluate(self, category: str, ctx: Dict[str, float]) -> Dict[str, float]:
        out: Dict[str, float] = {}
        for c in self._items.values():
            if not c.applies(category):
                continue
            v = c.fn(ctx)
            if v is not None and math.isfinite(v):
                out[c.name] = v
            elif v is not None:
                out[c.name] = 1e6
        return out

    def hard_names(self) -> set:
        return {n for n, c in self._items.items() if c.hard}

    def describe(self) -> List[Dict[str, object]]:
        return [{"name": c.name, "applies_to": c.applies_to, "hard": c.hard, "description": c.description}
                for c in self._items.values()]
