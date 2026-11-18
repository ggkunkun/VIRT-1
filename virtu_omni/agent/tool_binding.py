# -*- coding: utf-8 -*-
"""virtu_omni/agent/tool_binding.py — facet 工具调用的签名绑定层（2026-11-16 D1 修复）。

**为什么单独成模块**：Super Agent 的注册表把 facet 当**单参函数**（``fn(payload)``），
但有 10 个 facet 的真实签名是多参（``facet_pinn_predict`` 需要 3 个必填参、
``facet_rlvr_eval`` 需要 2 个、``facet_mcts_plan`` / ``facet_brep_compile`` 需要结构化列表、
``facet_quiet_star_heal`` 需要代码…）。模型按广播 schema 发的 JSON 对象会被**整体**绑到
第一个位置参数，其余静默取默认值 ⇒ 这 10 个工具在 REACT 真实路径下要么抛 TypeError，
要么悄悄丢掉参数（``dispatch_modality`` 的 ``action`` 被丢成 ``""``、
``check_software_affordance`` 的 ``software`` 被丢成默认值 ``SOLIDWORKS_2021``）。

这里按 facet 自己的签名做绑定。本模块**零依赖**（只用标准库），有两个关键性质：

1. ``tests/test_product_first_closed_loop.py`` 与 ``tests/test_swarm_entry.py`` 会用
   ``ast.get_source_segment`` 把 Super Agent 的方法源码抠出来、在合成命名空间里 ``exec``。
   被抽取的方法因此**不能依赖模块级名字**——所以调用方要用**函数内 import**拿本模块的函数。
2. 绑定规则本身是纯函数，可以被单独证伪（缺必填参数必须抛错，不许静默降级）。

绑定规则（按优先级）：

1. 载荷是 dict 且键命中 facet 形参名 → **按关键字传参**；必填项缺失时**明确报错**，
   不静默用默认值顶替；
2. facet 只有一个形参，且载荷是「单键且键名等于形参名」的 dict → 解包该值
   （修 ``blueprint_spatial_ground {"raw_elements": [...]}``、``funsearch_evolve {"steps": 1}``）；
3. 其余情况按旧契约把载荷整体绑到第一个形参，其余形参取默认值
   （保证 26 个已验证可用的单参工具行为完全不变）。
"""

from __future__ import annotations

import inspect
import typing
from typing import Any, Callable, Dict, List, Tuple

__all__ = [
    "FACET_ARRAY_ITEM_FIELDS",
    "bind_facet_args",
    "facet_input_schema",
    "facet_json_type",
    "facet_params",
]

#: 数组型形参的内部字段提示。facet 内部用 dataclass(**item) 展开，
#: 键名对不上会报 "unexpected keyword argument"；schema 里不写出来，
#: 规划器就只能猜（实测把 operation_id 当成了 op_id 之外的键）。
FACET_ARRAY_ITEM_FIELDS: Dict[str, List[str]] = {
    "operations": [
        "op_id", "op_name", "op_type", "tool_id",
        "tool_ld_ratio", "required_preconditions", "fixture_id",
    ],
}


def facet_params(fn: Callable[..., Any]) -> List[inspect.Parameter]:
    """取 facet 的业务形参（去掉 self 与 *args/**kwargs）。"""
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):  # pragma: no cover - 无签名的内建对象
        return []
    return [p for p in sig.parameters.values()
            if p.name != "self"
            and p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD)]


def facet_json_type(annotation: Any) -> str:
    """把 Python 注解映射成 JSON Schema 类型名（拿不准就当 string，宽松优先）。"""
    if annotation is inspect.Parameter.empty:
        return "string"
    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)
    if origin is typing.Union or (origin is None and args and hasattr(annotation, "__args__")):
        for arg in args:
            if arg is not type(None):
                return facet_json_type(arg)
        return "string"
    if origin in (list, tuple, set):
        return "array"
    if origin is dict:
        return "object"
    if annotation is bool:
        return "boolean"
    if annotation is int:
        return "integer"
    if annotation is float:
        return "number"
    if annotation is dict:
        return "object"
    if annotation is list:
        return "array"
    if annotation is str:
        return "string"
    return "string"


def facet_input_schema(fn: Callable[..., Any]) -> Dict[str, Any]:
    """按 facet 真实签名生成 JSON Schema（properties + required）。"""
    params = facet_params(fn)
    props: Dict[str, Any] = {}
    required: List[str] = []
    for p in params:
        jt = facet_json_type(p.annotation)
        prop: Dict[str, Any] = {"type": jt, "description": f"facet 形参 {p.name}"}
        if jt == "array":
            fields = FACET_ARRAY_ITEM_FIELDS.get(p.name) or []
            if fields:
                prop["items"] = {
                    "type": "object",
                    "properties": {f: {"type": "string"} for f in fields},
                    "required": list(fields),
                }
                prop["description"] = (
                    f"facet 形参 {p.name}（数组，元素字段：{', '.join(fields)}）")
            else:
                prop["items"] = {"type": "object"}
        props[p.name] = prop
        if p.default is p.empty:
            required.append(p.name)
    return {"type": "object", "properties": props, "required": required}


def bind_facet_args(fn: Callable[..., Any], payload: Any) -> Tuple[Tuple[Any, ...], Dict[str, Any]]:
    """把一次工具调用的载荷绑定到 facet 的真实签名上。

    返回 ``(args, kwargs)``，调用方用 ``fn(*args, **kwargs)`` 调用。
    """
    params = facet_params(fn)
    if not params:
        return (), {}
    names = [p.name for p in params]

    if isinstance(payload, dict):
        if len(params) == 1:
            if len(payload) == 1 and names[0] in payload:
                return (payload[names[0]],), {}
            return (payload,), {}
        matched = {k: payload[k] for k in names if k in payload}
        if matched:
            missing = [p.name for p in params
                       if p.default is p.empty and p.name not in matched]
            if missing:
                raise TypeError(
                    f"工具参数缺失：需要 {missing}，实际收到键 {sorted(payload)}")
            return (), matched
        return (payload,), {}

    return (payload,), {}
