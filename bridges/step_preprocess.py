# -*- coding: utf-8 -*-
"""STEP → 模型可懂上下文 的单函数预处理接口（virtu_omni 感知/建模通道入口）。

这是「13.63B 读不懂装配体」的 P0 解法落地：任何把 STEP 喂给大模型之前，
先调用本模块把 8000 行几何噪声压成 ~12 行结构描述。

典型用法（感知通道 wpt2-main / 建模通道通用）：

    from bridges.step_preprocess import preprocess_step, build_step_prompt

    # 1) 只要结构化上下文（字符串，可直接塞进 system/user prompt）
    ctx = preprocess_step("assets/wheel_mold_P0.step")

    # 2) 直接把用户问题 + STEP 结构拼成完整 prompt
    prompt = build_step_prompt("这个装配体有几个零件？", "assets/wheel_mold_P0.step")

    # 3) 要结构化数据（dict / JSON / DSL）
    data = preprocess_step(path, output="json")     # dict
    dsl  = preprocess_step(path, output="dsl")      # str

也提供 CLI：
    python3 bridges/step_preprocess.py <file.step> [--mode prompt|json|dsl|md]
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, Union

# 兼容「作为包 import」与「直接运行脚本」两种用法
try:
    from bridges.step_bom import StepBOM
except ImportError:  # pragma: no cover
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from step_bom import StepBOM  # type: ignore


def preprocess_step(step_path: str,
                    output: str = "prompt",
                    max_chars: int = 0) -> Union[str, Dict[str, Any]]:
    """把 STEP 转成模型可注入的上下文。

    Parameters
    ----------
    step_path : .step / .stp 文件路径
    output    : prompt(默认，自然语言+DSL) | ctx(=prompt) | dsl | md | json(dict)
    max_chars : >0 时按字符硬截断（防止超长上下文），会附加截断提示

    Returns
    -------
    str 或 dict；出错时返回带 status=error 的 dict（不抛异常，便于链路容错）
    """
    if not os.path.isfile(step_path):
        return {"status": "error", "message": "STEP 文件不存在: %s" % step_path}
    try:
        bom = StepBOM(step_path)
        mode = (output or "prompt").lower()
        if mode == "json":
            return bom.to_dict()
        if mode == "dsl":
            text = bom.to_dsl()
        elif mode == "md":
            text = bom.to_markdown()
        else:  # prompt / ctx
            text = bom.to_prompt_context()
        if max_chars and len(text) > max_chars:
            text = text[:max_chars] + "\n…[上下文已截断，完整结构请查 BOM JSON]"
        return text
    except Exception as exc:  # noqa: BLE001
        return {"status": "error",
                "message": "%s: %s" % (type(exc).__name__, exc),
                "source": os.path.basename(step_path)}


def build_step_prompt(user_query: str, step_path: str,
                      system_hint: str = "") -> str:
    """把「用户问题 + STEP 结构摘要」拼成一条完整 prompt。"""
    ctx = preprocess_step(step_path, output="prompt")
    if isinstance(ctx, dict):
        ctx = "[STEP 预处理失败] " + ctx.get("message", "")
    parts = []
    if system_hint:
        parts.append(system_hint)
    parts += [
        "以下是该 STEP 文件的结构化装配/零件摘要（已由确定性解析器从原始几何提取，"
        "请直接基于此作答，不要臆测原始几何细节）：",
        "",
        ctx,
        "",
        "---",
        "用户问题：" + user_query,
    ]
    return "\n".join(parts)


def inject_into_messages(messages: list, step_path: str,
                         role: str = "system") -> list:
    """把 BOM 上下文注入既有 OpenAI 风格 messages 列表（返回新列表，不改原对象）。"""
    ctx = preprocess_step(step_path, output="prompt")
    if isinstance(ctx, dict):
        ctx = "[STEP 预处理失败] " + ctx.get("message", "")
    injected = [{"role": role,
                 "content": "STEP 装配结构上下文（确定性解析，优先采信）：\n" + ctx}]
    return injected + list(messages)


def main(argv=None):
    argv = argv or sys.argv[1:]
    if not argv:
        print("用法: python3 bridges/step_preprocess.py <file.step> "
              "[--mode prompt|json|dsl|md] [--max-chars N]")
        return 1
    mode = "prompt"
    max_chars = 0
    for i, a in enumerate(argv[1:], 1):
        if a == "--mode" and i < len(argv):
            mode = argv[i + 1]
        elif a == "--max-chars" and i < len(argv):
            max_chars = int(argv[i + 1])
    out = preprocess_step(argv[0], output=mode, max_chars=max_chars)
    if isinstance(out, dict):
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
