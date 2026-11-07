#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""virtu-toolcall 的 Ollama 调用客户端（含 tool_call 解析兜底）。

为什么需要兜底
--------------
训练语料里 assistant 的工具调用是以 role="tool" 消息存放的（content 为 JSON 字符串），
不是标准 OpenAI 的 assistant.tool_calls 结构。因此经合并/量化后的模型，一旦 believes
自己该调工具，会吐出带冗余前缀的文本：

    <|im_start|>tool_call
    {"name": "cad.parse_wish_intent", "arguments": {...}}
    </tool_call>
    </tool_call>

Ollama 0.35.1 的解析器识别不了这个变体，于是整段落进 content，tool_calls 为空。
本客户端负责把这种文本还原成标准 OpenAI tool_calls 结构，让上层 Agent 链路照常工作。

另注意：stop 只设 <|im_end|>，不要带 <|im_start|> —— 实测后者会把输出掐断成空串。
"""
from __future__ import annotations

import sys
import json
import re
import time
import urllib.request
from typing import Any

BASE = "http://127.0.0.1:11434"
# 匹配被 <|im_start|>tool_call 或 <tool_call> 包裹的一到多段 JSON
TOOL_CALL_RE = re.compile(
    r"(?:<\|im_start\|>tool_call|<tool_call>)\s*(.*?)\s*</tool_call>", re.DOTALL
)
# GGUF 特殊 token 映射偏差的兜底清理：
#  - [PAD\d+]      —— 转换器旧版把补位/特殊 token 错写成字面量，llama.cpp 原样吐出
#  - 思维分隔符    —— Qwen3 的 <think>…</think>（修复后正确渲染）或 <｜begin/end▁of▁thinking｜>
#                    偶尔泄漏到正文（尤其在没关 think 模式的旧前端里）
PAD_RE = re.compile(r"\[PAD\d+\]")
THINK_RE = re.compile(r"<[｜|]?(?:begin|end)▁?of▁?thinking[｜|]?>")
# 修复后 token 151667/151668 正确渲染成 <think> / </think>；整段思考块连同标签一起清掉
THINK_TAG_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
THINK_TAG_RE2 = re.compile(r"</?think>")
LEGACY_THINK_BLOCK_RE = re.compile(r"<[｜|]?(?:begin)▁?of▁?thinking[｜|]?>(.*?)<[｜|]?(?:end)▁?of▁?thinking[｜|]?>", re.DOTALL)


def extract_thinking(text: str) -> tuple[str, str]:
    """从文本中分离深度思考内容 (thinking) 与最终正文 (content)。

    支持 Qwen3 的标准 <think>...</think> 标签以及历史 GGUF 的 <|begin/end_of_thinking|> 标记。
    返回 (clean_content, extracted_thinking)。
    """
    if not text:
        return "", ""
    thoughts = []
    for m in THINK_TAG_RE.finditer(text):
        inner = THINK_TAG_RE2.sub("", m.group(0)).strip()
        if inner:
            thoughts.append(inner)
    for m in LEGACY_THINK_BLOCK_RE.finditer(text):
        inner = m.group(1).strip()
        if inner:
            thoughts.append(inner)
    clean_text = _clean(text)
    combined_thinking = "\n\n".join(thoughts).strip()
    return clean_text, combined_thinking


def _clean(text: str) -> str:
    text = PAD_RE.sub("", text)
    text = THINK_RE.sub("", text)
    text = THINK_TAG_RE.sub("", text)
    text = THINK_TAG_RE2.sub("", text)
    text = re.sub(r"</?tool_call>", "", text)  # 冗余闭合残留
    return text.strip()


# ---------------------------------------------------------------------------
# 输出层加固（2026-11-07）：JSON 语法约束 / 容器解包 / 退化循环截断 / 工具腿正文丢弃
# 依据：20 题实测中 JSON 腿失败的主因是模型在正文里夹带推理与多段重复输出，
#       而非双引号转义；参数层（repeat_penalty 1.05→1.00、num_gpu 22→30）无显著增益。
# ---------------------------------------------------------------------------
JSON_HINT_RE = re.compile(r"\bjson\b|json\s*格式|json\s*输出|json\s*对象", re.I)
# 模型在 grammar 模式下会把结果套一层容器，单键且在下列白名单内时视为包装层
UNWRAP_KEYS = {
    "tools", "result", "results", "data", "output", "outputs", "items",
    "records", "rows", "list", "response", "answer", "payload", "content",
}
# 连续重复片段（"jaws\njaws\n..." 型退化），单元 3~40 字符，重复 >=6 次
REPEAT_RE = re.compile(r"(.{3,40}?)\1{5,}", re.DOTALL)
WORD_RE = re.compile(r"[\w\u4e00-\u9fff]")
# 文本化工具调用："调用工具：query_stock，参数：{...}" / "set_cnc_param {"..."}"
TEXTUAL_CALL_RE = re.compile(
    r"(?:调用(?:工具|函数)?|call(?:ing)?\s+tool|使用(?:工具)?)\s*[:：]?\s*"
    r"([A-Za-z_][A-Za-z0-9_.]*)[\s\S]{0,60}?"
    r"(?:参数|arguments?)\s*[:：]?\s*(\{[\s\S]*?\})",
    re.IGNORECASE,
)


def _last_user_text(messages: list[dict] | None) -> str:
    for m in reversed(messages or []):
        if (m.get("role") or "") == "user":
            c = m.get("content")
            if isinstance(c, str):
                return c
    return ""


def json_intent(messages: list[dict] | None, tools: list[dict] | None) -> bool:
    """判断本轮是否为"要 JSON 结果"的请求。

    工具腿不套 grammar（llama.cpp 的 JSON 文法会与 tool_calls 解析冲突）。
    """
    if tools:
        return False
    return bool(JSON_HINT_RE.search(_last_user_text(messages)))


def collapse_repeats(text: str) -> tuple[str, bool]:
    """把模型退化的连续重复段压成一份。返回 (新文本, 是否发生截断)。"""
    if not text or len(text) < 40:
        return text or "", False

    def _rep(m: re.Match) -> str:
        unit = m.group(1)
        if not WORD_RE.search(unit):      # 纯标点/空白重复不动
            return m.group(0)
        return unit

    new = REPEAT_RE.sub(_rep, text)
    return new, new != text


def _strip_fence(text: str) -> str:
    t = (text or "").strip()
    blocks = re.findall(r"```(?:json|JSON)?\s*([\s\S]*?)```", t)
    if blocks:
        cand = [b.strip() for b in blocks if "{" in b or "[" in b]
        if cand:
            return cand[-1]
    return t


def _balanced_slice(text: str) -> str | None:
    for i, ch in enumerate(text):
        if ch in "{[":
            depth, instr, esc = 0, False, False
            for j in range(i, len(text)):
                c = text[j]
                if instr:
                    if esc:
                        esc = False
                    elif c == "\\":
                        esc = True
                    elif c == '"':
                        instr = False
                else:
                    if c == '"':
                        instr = True
                    elif c in "{[":
                        depth += 1
                    elif c in "}]":
                        depth -= 1
                        if depth == 0:
                            return text[i:j + 1]
    return None


def parse_json_payload(text: str) -> tuple[bool, Any]:
    """宽松解析模型返回的 JSON：先剥代码块，再整体解析，最后取第一个平衡括号段。"""
    t = _strip_fence(text)
    if not t:
        return False, None
    try:
        return True, json.loads(t)
    except Exception:
        pass
    blk = _balanced_slice(t)
    if blk:
        try:
            return True, json.loads(blk)
        except Exception:
            pass
    return False, None


def unwrap_json_container(value: Any) -> tuple[Any, str | None]:
    """拆掉模型自套的单键容器（如 {"tools": [...]}）。

    返回 (值, 被拆掉的键名)。只拆白名单键，避免误伤正常单键对象。
    """
    key_used = None
    for _ in range(3):
        if isinstance(value, dict) and len(value) == 1:
            k, v = next(iter(value.items()))
            if isinstance(v, (list, dict)) and str(k).strip().lower() in UNWRAP_KEYS:
                key_used = str(k)
                value = v
                continue
        break
    return value, key_used


def recover_textual_call(text: str, allowed_names: set[str]) -> list[dict] | None:
    """把"调用工具：xxx，参数：{...}"这类纯文本调用还原成标准 tool_calls。

    仅在 Ollama 没有给出结构化 tool_calls 时兜底使用，且函数名必须在传入的
    tools 白名单内，避免把普通正文误判成调用。
    """
    if not text or not allowed_names:
        return None
    calls = []
    for m in TEXTUAL_CALL_RE.finditer(_strip_fence(text)):
        name, args_txt = m.group(1), m.group(2)
        if name not in allowed_names:
            continue
        try:
            args = json.loads(args_txt)
        except Exception:
            blk = _balanced_slice(args_txt)
            if not blk:
                continue
            try:
                args = json.loads(blk)
            except Exception:
                continue
        if not isinstance(args, dict):
            continue
        calls.append({
            "type": "function",
            "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)},
        })
    return calls or None


def _tool_names(tools: list[dict] | None) -> set[str]:
    names = set()
    for t in tools or []:
        if not isinstance(t, dict):
            continue
        fn = t.get("function") if isinstance(t.get("function"), dict) else t
        n = (fn or {}).get("name")
        if isinstance(n, str):
            names.add(n)
    return names


def normalize_tool_calls(calls: list[dict] | None) -> list[dict] | None:
    """统一成 OpenAI 结构：arguments 一定是 JSON 字符串，且带 type / id。

    Ollama 原生返回的 arguments 是 dict，兜底解析出来的是 str，两者混用会让上层
    在 r["arguments"][:n] 这类切片上直接 TypeError（2026-11-07 实测踩到）。
    """
    if not calls:
        return calls
    out = []
    for i, c in enumerate(calls):
        if not isinstance(c, dict):
            continue
        fn = c.get("function") if isinstance(c.get("function"), dict) else {}
        name = fn.get("name") or c.get("name")
        args = fn.get("arguments", c.get("arguments", {}))
        if isinstance(args, str):
            try:
                args_obj = json.loads(args) if args.strip() else {}
                args = json.dumps(args_obj, ensure_ascii=False)
            except Exception:
                args = args if args.strip() else "{}"
        else:
            args = json.dumps(args if args is not None else {}, ensure_ascii=False)
        out.append({
            "id": c.get("id") or "call_%d" % i,
            "type": "function",
            "function": {"name": name, "arguments": args},
        })
    return out or None


def http_json(payload, timeout=1800):
    """绕过本机透明代理直连 localhost。"""
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    req = urllib.request.Request(
        BASE + "/api/chat",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with op.open(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", "replace")
        raise RuntimeError(f"Ollama API HTTP {e.code}: {err_msg}")


def http_stream(payload, timeout=1800):
    """绕过本机透明代理直连 localhost 并以流式迭代逐行返回 NDJSON 块。"""
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    req = urllib.request.Request(
        BASE + "/api/chat",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        resp = op.open(req, timeout=timeout)
        try:
            for raw_line in resp:
                line = raw_line.decode("utf-8", "replace").strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
        finally:
            resp.close()
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", "replace")
        raise RuntimeError(f"Ollama API HTTP {e.code}: {err_msg}")


def parse_tool_calls(text: str) -> list[dict[str, Any]] | None:
    """从带冗余前缀或代码块的文本里抽出标准 tool_calls；没有则返回 None。"""
    if not text:
        return None
    raw = TOOL_CALL_RE.findall(text)
    if raw:
        calls = []
        for blob in raw:
            blob = blob.strip()
            # 去掉可能重复的尾部闭合标记残留
            blob = blob.replace("</tool_call>", "").strip()
            try:
                obj = json.loads(blob)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and ("name" in obj or "tool" in obj):
                fn_name = obj.get("name") or obj.get("tool")
                args = obj.get("arguments", {})
                if not isinstance(args, str):
                    args = json.dumps(args, ensure_ascii=False)
                calls.append({
                    "type": "function",
                    "function": {
                        "name": fn_name,
                        "arguments": args,
                    },
                })
        if calls:
            return calls

    # 兜底：扫描 JSON 代码块或裸 JSON 对象
    dec = json.JSONDecoder()
    calls = []
    seen_spans = set()
    for i, ch in enumerate(text):
        if ch == '{':
            try:
                obj, end = dec.raw_decode(text, i)
                if (i, end) in seen_spans:
                    continue
                seen_spans.add((i, end))
                if isinstance(obj, dict) and ("name" in obj or "tool" in obj):
                    fn_name = obj.get("name") or obj.get("tool")
                    if isinstance(fn_name, str) and (fn_name.startswith("cadcam_") or fn_name.startswith("cad.")):
                        args = obj.get("arguments", {})
                        if not isinstance(args, str):
                            args = json.dumps(args, ensure_ascii=False)
                        calls.append({
                            "type": "function",
                            "function": {
                                "name": fn_name,
                                "arguments": args,
                            },
                        })
            except Exception:
                pass
    return calls or None


def sanitize_tools(tools: list[dict] | None) -> list[dict] | None:
    """Ensure tool schemas passed to Ollama contain valid parameters object to prevent HTTP 400."""
    if not tools:
        return None
    sanitized = []
    for t in tools:
        if not isinstance(t, dict):
            continue
        item = dict(t)
        if "function" in item and isinstance(item["function"], dict):
            fn = dict(item["function"])
            params = fn.get("parameters")
            if not isinstance(params, dict):
                params = {"type": "object", "properties": {}}
            elif "properties" not in params or not isinstance(params.get("properties"), dict):
                params = dict(params)
                params.setdefault("type", "object")
                params["properties"] = {}
            fn["parameters"] = params
            item["function"] = fn
        elif "parameters" not in item:
            item = {
                "type": "function",
                "function": {
                    "name": item.get("name", "unknown_tool"),
                    "description": item.get("description", ""),
                    "parameters": {"type": "object", "properties": {}},
                }
            }
        sanitized.append(item)
    return sanitized


def chat(model: str, messages: list[dict], tools: list[dict] | None = None,
         temperature: float = 0.0, num_ctx: int = 2048, num_predict: int = 512,
         timeout: int = 1800, think: bool = False,
         num_gpu: int | None = None, keep_alive: str = "10m",
         format_schema: dict | None = None, json_mode: bool | None = None) -> dict:
    # JSON 出参统一走 llama.cpp grammar：实测能把"夹带推理/多段重复/引号异常"的
    # 输出压成单段合法 JSON。json_mode=None 时按最后一条 user 文本自动判定。
    if json_mode is None:
        json_mode = format_schema is not None or json_intent(messages, tools)
    if json_mode:
        think = False                       # grammar 与 think 同时开会互相破坏
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        # 工具调用模型：默认关闭思考模式，避免纯聊天吐 <think>…</think>
        # （Modelfile 已设 PARAMETER think false，这里再显式兜底）
        "think": think,
        # 推理提速：避免 Ollama 空闲 5min 卸载模型，下次调用重新加载（首响 12-16s 大半是加载）
        # 连续对话 / 一个任务里多次 tool-call 时，首字延迟直接砍掉；长任务可调大或设 -1 常驻
        "keep_alive": keep_alive,
        "options": {
            "num_ctx": min(num_ctx, 4096) if "moe" in model.lower() else num_ctx,
            "num_predict": num_predict,
            "temperature": temperature,
            # 关键：只留结束符。加 <|im_start|> 会把 tool_call 输出掐成空串
            "stop": ["<|im_end|>"],
            # num_gpu 不写死在 Modelfile：本地 4050(6GB) 强制全 offload 会 OOM，
            # L40S(45GB) 默认 -1 已全 offload。需要强制时由调用方按机器能力传（如 9999）
            **({"num_gpu": (24 if num_gpu is None else num_gpu)} if "moe" in model.lower() else ({"num_gpu": num_gpu} if num_gpu is not None else {})),
            **({"repeat_penalty": 1.15, "presence_penalty": 0.3} if "moe" in model.lower() else {}),
        },
    }
    if tools:
        payload["tools"] = sanitize_tools(tools)
    if format_schema is not None:
        payload["format"] = format_schema
    elif json_mode:
        payload["format"] = "json"

    t0 = time.time()
    r = http_json(payload, timeout=timeout)
    msg = r.get("message", {})
    raw_content = msg.get("content") or ""
    msg_thinking = msg.get("thinking") or ""

    # 退化重复（如 "jaws\n" ×N）先压掉，否则下游拿到的是无法解析的残段
    raw_content, degenerate = collapse_repeats(raw_content)
    clean_content, inline_thinking = extract_thinking(raw_content)
    thinking_parts = [p.strip() for p in (msg_thinking, inline_thinking) if p and p.strip()]
    final_thinking = "\n\n".join(thinking_parts).strip()

    allowed = _tool_names(tools)
    calls = msg.get("tool_calls") or parse_tool_calls(clean_content) or parse_tool_calls(raw_content)
    if not calls and allowed:
        calls = recover_textual_call(clean_content, allowed)
        if calls:
            clean_content = _clean(TEXTUAL_CALL_RE.sub("", clean_content))
    if calls and not msg.get("tool_calls"):
        # 兜底解析出来的，content 里那段冗余文本应清掉，避免上层重复处理与欺骗门误判
        clean_content = _clean(TOOL_CALL_RE.sub("", clean_content))
        # 若剩下的内容全是 JSON 或代码块包裹的 tool call，则直接置空
        if clean_content.startswith("```") and clean_content.endswith("```"):
            clean_content = ""
        elif clean_content.startswith("{") and clean_content.endswith("}"):
            clean_content = ""

    # 工具腿：一旦拿到 tool_calls，正文里的"收到指令/正在调用…"一律丢弃，
    # 原文留在 content_raw 备查。这样既不为消灭客套话去改 system（实测会导致不调工具）。
    calls = normalize_tool_calls(calls)
    content_out = clean_content
    discarded_text = ""
    if calls:
        discarded_text = clean_content
        content_out = ""

    json_ok = None
    json_value = None
    json_unwrapped = None
    unwrap_key = None
    if json_mode:
        json_ok, parsed = parse_json_payload(clean_content)
        if json_ok:
            # json_value 保留模型原始结构（题目若明确要求键名 tools，不能把键拆掉），
            # 另给 json_unwrapped 供"确实要裸数组"的调用方取用。
            json_value = parsed
            json_unwrapped, unwrap_key = unwrap_json_container(parsed)

    return {
        "content": content_out,
        "content_raw": raw_content,
        "discarded_content": discarded_text,
        "tool_calls": calls,
        "thinking": final_thinking,
        "raw": msg,
        "elapsed_s": round(time.time() - t0, 1),
        "eval_count": r.get("eval_count"),
        "prompt_eval_count": r.get("prompt_eval_count"),
        "parsed_by_fallback": bool(calls) and not msg.get("tool_calls"),
        "json_mode": bool(json_mode),
        "json_ok": json_ok,
        "json_value": json_value,
        "json_value_unwrapped": json_unwrapped,
        "json_unwrap_key": unwrap_key,
        "json_truncated": r.get("done_reason") == "length",
        "degenerate": degenerate,
    }


def chat_stream(model: str, messages: list[dict], tools: list[dict] | None = None,
                temperature: float = 0.0, num_ctx: int = 2048, num_predict: int = 512,
                timeout: int = 1800, think: bool = False,
                num_gpu: int | None = None, keep_alive: str = "10m",
                format_schema: dict | None = None, json_mode: bool | None = None):
    """流式自回归调用 Ollama /api/chat，实时产出思考 (thinking) 与正文 (content) 增量。

    yields 字典对象：
        {"type": "thinking", "delta": "..."}
        {"type": "content", "delta": "..."}
        {"type": "done", "content": full_text, "thinking": full_thinking,
         "prompt_eval_count": N, "eval_count": M, "json_ok": ..., "json_value": ...}
    """
    if json_mode is None:
        json_mode = format_schema is not None or json_intent(messages, tools)
    if json_mode:
        think = False
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "think": think,
        "keep_alive": keep_alive,
        "options": {
            "num_ctx": num_ctx,
            "num_predict": num_predict,
            "temperature": temperature,
            "stop": ["<|im_end|>"],
            **({"num_gpu": num_gpu} if num_gpu is not None else {}),
        },
    }
    if tools:
        payload["tools"] = sanitize_tools(tools)
    if format_schema is not None:
        payload["format"] = format_schema
    elif json_mode:
        payload["format"] = "json"

    accumulated_content = []
    accumulated_thinking = []
    prompt_eval_count = None
    eval_count = None

    for chunk in http_stream(payload, timeout=timeout):
        msg = chunk.get("message", {})
        c = msg.get("content") or ""
        t = msg.get("thinking") or ""

        if t:
            accumulated_thinking.append(t)
            yield {"type": "thinking", "delta": t}

        if c:
            clean_delta = _clean(c) if ("<think>" in c or "</think>" in c or "[PAD" in c) else c
            if clean_delta:
                accumulated_content.append(clean_delta)
                yield {"type": "content", "delta": clean_delta}

        if chunk.get("done"):
            prompt_eval_count = chunk.get("prompt_eval_count")
            eval_count = chunk.get("eval_count")

    full_content = "".join(accumulated_content)
    full_content, degenerate = collapse_repeats(full_content)
    full_thinking = "".join(accumulated_thinking)
    json_ok = json_value = unwrapped = None
    unwrap_key = None
    if json_mode:
        json_ok, json_value = parse_json_payload(full_content)
        if json_ok:
            unwrapped, unwrap_key = unwrap_json_container(json_value)
    yield {
        "type": "done",
        "content": full_content,
        "thinking": full_thinking,
        "prompt_eval_count": prompt_eval_count,
        "eval_count": eval_count,
        "json_mode": bool(json_mode),
        "json_ok": json_ok,
        "json_value": json_value,
        "json_value_unwrapped": unwrapped,
        "json_unwrap_key": unwrap_key,
        "degenerate": degenerate,
    }


def _self_test():
    sample = (
        '<|im_start|>tool_call\n'
        '{"name": "cad.parse_wish_intent", "arguments": {"wish": "x", "material": "AL7075-T6"}}\n'
        '</tool_call>\n</tool_call>'
    )
    got = parse_tool_calls(sample)
    assert got and got[0]["function"]["name"] == "cad.parse_wish_intent", got
    print("[self-test] OK", json.dumps(got, ensure_ascii=False))
    assert parse_tool_calls("普通文本") is None
    print("[self-test] OK 非工具文本返回 None")
    # [PAD\d+] 碎片清理
    dirty = "[PAD151667] 这是一段正常回复 [PAD151668]"
    assert _clean(dirty) == "这是一段正常回复", repr(_clean(dirty))
    print("[self-test] OK [PAD\\d+] 碎片已清理")
    # 思维分隔符泄漏清理
    think = "<｜begin▁of▁thinking｜>嗯 <｜end▁of▁thinking｜>结论"
    assert _clean(think) == "嗯 结论", repr(_clean(think))
    print("[self-test] OK 思维分隔符已清理")
    # 修复后正确渲染的 <think>…</think> 整段清理与抽取
    think2 = "<think>我先分析一下需求</think>好的，已为您生成建模脚本"
    assert _clean(think2) == "好的，已为您生成建模脚本", repr(_clean(think2))
    c2, t2 = extract_thinking(think2)
    assert c2 == "好的，已为您生成建模脚本" and t2 == "我先分析一下需求", (c2, t2)
    print("[self-test] OK <think> 思考抽取与整段清理通过")
    # 残留孤立 <think>/</think> 标签
    think3 = "结论<think>中间</think>补充"
    assert _clean(think3) == "结论补充", repr(_clean(think3))
    c3, t3 = extract_thinking(think3)
    assert c3 == "结论补充" and t3 == "中间", (c3, t3)
    print("[self-test] OK 孤立 <think> 标签抽取与清理通过")

    # 流式接口自测 (Mock http_stream)
    mock_chunks = [
        {"message": {"thinking": "思考步骤1"}, "done": False},
        {"message": {"content": "这是输出"}, "done": False},
        {"message": {}, "done": True, "prompt_eval_count": 10, "eval_count": 5},
    ]
    import unittest.mock
    with unittest.mock.patch.object(sys.modules[__name__], "http_stream", return_value=iter(mock_chunks)):
        stream_out = list(chat_stream("test-model", [{"role": "user", "content": "hi"}]))
        assert len(stream_out) == 3
        assert stream_out[0] == {"type": "thinking", "delta": "思考步骤1"}
        assert stream_out[1] == {"type": "content", "delta": "这是输出"}
        assert stream_out[2]["type"] == "done"
        assert stream_out[2]["eval_count"] == 5
    print("[self-test] OK chat_stream 流式输出与 usage 解析通过")


if __name__ == "__main__":
    _self_test()
