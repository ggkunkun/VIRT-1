#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
virtu_tokenize.py — Virtu tool-call 语料的唯一权威 tokenization / loss-mask 实现

【为什么必须单独成文件】
Qwen3 官方 chat_template 有两条隐藏规则，导致"逐消息前缀对齐"这个常见做法**必然错位**：

  L42: {%- if loop.index0 > ns.last_query_index %}
       只有最后一个 user 之后的 assistant 段才渲染成
       "assistant\n<think>\n{reasoning}\n</think>\n\n{content}"
  L46: {%- else %}
       其余 assistant 段渲染成 "assistant\n{content}"（无 think 包裹）

  更关键的是：同一条 assistant 消息，**单独渲染**与**作为前缀渲染**结果不同
  （是否处于"最后一个 query 之后"会翻转），所以
  "template(messages[:i+1]).startswith(template(messages[:i]))" 这个假设不成立。

  错误后果：loss 被打到错误的 token 上，模型学到"在 tool 之前就该开始输出 tool_call"，
  或者更糟——把 tool_response 的内容当成自己的输出学。

【本模块的做法】一次性渲染整条对话 -> 字符级定位 assistant 段 -> offset mapping 映射到 token
  1. 整条渲染：template(messages) 一次搞定，绕开前缀假设
  2. 字符定位：找 "assistant\\n" 标记，段尾取下一个 "assistant\\n" / "user\\n" 边界
  3. token 映射：用 tokenizer 的 offset_mapping 把字符区间映射到 token 区间
  4. 掩码：只有 assistant 段内的 token 计 loss，其余一律 -100
     （system / user / tool_response 全部屏蔽，防止模型学会伪造工具返回值）

训练侧（train_virtu_toolcall.py）与体检侧（validate_render_dataset.py）都调用这里，
保证"训练时看到的"与"体检时验证的"是同一套逻辑。
"""

from __future__ import annotations

import re
from typing import List, Tuple

# 段边界标记：assistant 段从 "assistant\n" 之后开始，到下一个这些标记之前结束
_ASSISTANT_MARK = "assistant\n"
_BOUNDARY_MARKS = ("assistant\n", "user\n")
# 段尾若恰好是一个换行，那是与下一段的分隔符，不属于本段内容
_TRAILING_NEWLINE = re.compile(r"\n+$")


def render_full(tokenizer, messages, tools):
    """整条渲染。失败时抛异常由调用方记录。"""
    return tokenizer.apply_chat_template(
        messages, tools=tools or [], tokenize=False, add_generation_prompt=False)


def find_assistant_spans(text: str) -> List[Tuple[int, int]]:
    """在整条渲染文本里定位每个 assistant 段的字符区间 [start, end)。

    段起于 "assistant\\n" 之后，止于下一个 "assistant\\n" 或 "user\\n" 之前。
    段尾的换行符属于分隔符，不计入本段。
    """
    spans: List[Tuple[int, int]] = []
    for m in re.finditer(re.escape(_ASSISTANT_MARK), text):
        start = m.end()
        nxt = len(text)
        for b in _BOUNDARY_MARKS:
            j = text.find(b, start)
            if j >= 0:
                nxt = min(nxt, j)
        end = nxt
        # 去掉段尾的换行（分隔符）
        while end > start and text[end - 1] == "\n":
            end -= 1
        if end > start:
            spans.append((start, end))
    return spans


def build_example(messages, tools, tokenizer, max_length: int = 4096):
    """渲染 + 掩码。

    返回 (ids, labels, meta)
      ids    : token id 列表（已截断到 max_length）
      labels : 与 ids 等长；assistant 段为原 id，其余为 -100
      meta   : 诊断信息 dict
    """
    text = render_full(tokenizer, messages, tools)
    spans = find_assistant_spans(text)

    enc = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)
    ids = enc["input_ids"]
    offs = enc["offset_mapping"]

    labels = [-100] * len(ids)
    for s0, e0 in spans:
        for i, (a, b) in enumerate(offs):
            if a >= s0 and b <= e0 and b > a:
                labels[i] = ids[i]

    n_loss = sum(1 for x in labels if x != -100)

    # 统计每个 assistant 段命中的 token 数（用于体检）
    seg_counts = []
    for s0, e0 in spans:
        c = sum(1 for a, b in offs if a >= s0 and b <= e0 and b > a)
        seg_counts.append(c)

    truncated = len(ids) > max_length
    if truncated:
        ids = ids[:max_length]
        labels = labels[:max_length]

    meta = {
        "n_tok": len(ids),
        "n_loss": n_loss,
        "n_assistant_spans": len(spans),
        "span_token_counts": seg_counts,
        "n_chars": len(text),
        "truncated": truncated,
        "loss_ratio": round(n_loss / max(1, len(ids)), 4),
    }
    return ids, labels, meta


def decode_loss_segments(tokenizer, ids, labels, limit=3):
    """把计 loss 的连续片段解码出来，供人工核对。"""
    segs, cur = [], []
    for t, l in zip(ids, labels):
        if l != -100:
            cur.append(t)
        elif cur:
            segs.append(cur)
            cur = []
    if cur:
        segs.append(cur)
    return [tokenizer.decode(s) for s in segs[:limit]]
