#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_ect_rowcheck.py — 语料单条记录的共享校验逻辑。

独立成模块是为了让 01_prepare_data.py 与 validate_corpus.py 使用**同一份**实现，
避免"生成时一套规则、体检时另一套规则"造成的假绿。
"""
from __future__ import annotations

import ast
import json
from typing import Any, Dict, List

from ect_common import resolve
from physics_gate import check_parametric_model


def load_tool_specs() -> List[Dict[str, Any]]:
    """工具面单一事实源：AST 静态提取 bridges/tool_calling_specs.py，无需 import 重依赖。"""
    p = resolve("bridges/tool_calling_specs.py")
    if not p.is_file():
        raise FileNotFoundError(f"tool specs missing: {p}")
    tree = ast.parse(p.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if "CADCAM_TOOLS_DEFINITION" in names:
                return list(ast.literal_eval(node.value))
    raise ValueError("CADCAM_TOOLS_DEFINITION not found (non-literal assignment?)")


def tool_spec_index() -> Dict[str, Dict[str, Any]]:
    return {t["function"]["name"]: t["function"] for t in load_tool_specs()}


def check_tool_calls(text: str, index: Dict[str, Dict[str, Any]]) -> List[str]:
    """校验一条 assistant 文本里的工具调用：白名单 / required / enum / 键名。"""
    errs: List[str] = []
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return []  # 自然语言答案合法
    calls = obj if isinstance(obj, list) else [obj]
    for call in calls:
        if not isinstance(call, dict):
            continue
        if "name" in call and "tool" not in call:
            errs.append("使用了 name 键，必须改为 tool")
        if "tool" not in call:
            continue
        name = call.get("tool")
        if name not in index:
            errs.append(f"工具名 {name!r} 不在 14 个 cadcam_* 白名单内（taught_only）")
            continue
        args = call.get("arguments")
        if not isinstance(args, dict):
            errs.append(f"{name}: arguments 必须是对象")
            continue
        params = index[name].get("parameters") or {}
        for k in params.get("required") or []:
            if k not in args:
                errs.append(f"{name}: 缺少 required 参数 {k}")
        for k, sch in (params.get("properties") or {}).items():
            if k in args and "enum" in sch and args[k] not in sch["enum"]:
                errs.append(f"{name}.{k}={args[k]!r} 不在 enum {sch['enum']}")
    return errs


def normalize_messages(msgs: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """把历史语料的 OpenAI tool_calls 格式规范化为本项目约定的纯文本 messages。

    * content=None -> ""
    * tool_calls -> 序列化为 {"tool": ..., "arguments": ...}（或数组）写入 content
    * tool 回执 content 非字符串 -> JSON 字符串（训练时该段会被 mask）
    * role 非标准 -> "user"
    """
    out: List[Dict[str, str]] = []
    for m in msgs:
        role = m.get("role") if m.get("role") in {"system", "user", "assistant", "tool"} else "user"
        content = m.get("content")
        if content is None:
            content = ""
        elif not isinstance(content, str):
            content = json.dumps(content, ensure_ascii=False)
        tcs = m.get("tool_calls")
        if tcs:
            calls = []
            for tc in tcs:
                fn = tc.get("function", {}) if isinstance(tc, dict) else {}
                args = fn.get("arguments")
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                calls.append({"tool": fn.get("name", ""), "arguments": args or {}})
            payload = calls if len(calls) > 1 else (calls[0] if calls else {})
            content = (content + "\n" if content else "") + json.dumps(payload, ensure_ascii=False)
        out.append({"role": role, "content": content})
    return out


def assistant_text(row: Dict[str, Any]) -> str:
    return "\n".join(str(m.get("content", "")) for m in row.get("messages", [])
                     if m.get("role") == "assistant")


def user_text(row: Dict[str, Any]) -> str:
    return next((str(m.get("content", "")) for m in row.get("messages", [])
                 if m.get("role") == "user"), "")


def physics_ok(row: Dict[str, Any]) -> tuple:
    """单条语料的物理过闸。返回 (ok, reasons)。

    纯自然语言样本（拒答 / 通用 replay / 语义解析）无数值断言，直接放行；
    但只要声明了 model_spec 或工具调用里带几何尺寸，就必须通过物理校验。
    """
    meta = row.get("meta") or {}
    if meta.get("boundary"):
        return True, []  # 拒答本身就是物理边界的正确表达
    if meta.get("model_spec"):
        v = check_parametric_model(meta["model_spec"])
        if not v.ok:
            return False, v.violations
    try:
        obj = json.loads(assistant_text(row))
    except (json.JSONDecodeError, TypeError):
        return True, []
    calls = obj if isinstance(obj, list) else [obj]
    for call in calls:
        if not isinstance(call, dict):
            continue
        args = call.get("arguments") or {}
        dims = args.get("dimensions") if isinstance(args, dict) else None
        if isinstance(dims, dict) and "d_outer" in dims and "d_inner" in dims:
            v = check_parametric_model({"dimensions": dims})
            if not v.ok:
                return False, v.violations
    return True, []


__all__ = ["assistant_text", "user_text", "physics_ok", "load_tool_specs",
           "tool_spec_index", "check_tool_calls", "normalize_messages"]
