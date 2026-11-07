# -*- coding: utf-8 -*-
"""A2：剥离 SFT 数据里的「战报式」模板套话，防止下轮训练重新引入冗长。

根因（见 VIRTU_MODEL_STRENGTHEN）：virtu_gold_production_sft 与
master_cad_cam_six_software_train 中 32%~54% 的 assistant 响应 >1500 字符，
且前缀充满「为您生成的 XXX 如下：」「根据您的许愿式…」等模板套话——
这正是旧模型吐 7420-token 战报的训练侧来源。

本脚本对 messages 格式数据做：
  1) 去掉开头的套话引导段（"为您生成/根据您的许愿式/以下是为您…"等）；
  2) 去掉结尾的营销式收尾（"💡…""希望这对您…""如有需要…"等）；
  3) 压缩连续分隔线；
  4) 超长且仍以散文为主的记录下采样（保留含代码的工程实体内容）。
输出 *_cleaned.jsonl，长度分布向 v5(median 34) 靠拢但不破坏代码/事实。

用法
----
    python clean_verbose_sft.py
"""
from __future__ import annotations

import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))

IN_FILES = [
    "virtu_gold_production_sft.jsonl",
    "../../damodel_cad_cam_tuning/dataset/master_cad_cam_six_software_train.jsonl",
]
# 入口套话（行首匹配即整段丢弃到第一个空行/代码块之前）
LEAD_PAT = re.compile(
    r"^\s*(为您生成|根据您的许愿式|以下是为您|为您编制|根据您|已对工件|下面为|以下为|为您准备的|为您定制)",
    re.M)
# 结尾营销句（整行丢弃）
TAIL_PAT = re.compile(
    r"(💡|希望这对您|如有需要|如果您还有|欢迎随时|期待您的|如需进一步|希望以上|请随时|祝您)",
)
SEP = re.compile(r"^[=\-_~]{3,}\s*$")


def clean_text(text: str) -> str:
    if not text:
        return text
    # 1) 去入口套话：删掉从匹配行到下一个空行之间的引导段
    m = LEAD_PAT.search(text)
    if m:
        # 找到匹配行起点
        start = text.rfind("\n", 0, m.start()) + 1
        # 找到其后第一个空行
        nxt = text.find("\n\n", m.end())
        if nxt == -1:
            nxt = len(text)
        text = text[:start] + text[nxt:]
    # 2) 去结尾营销句
    lines = text.split("\n")
    out = []
    for ln in lines:
        if TAIL_PAT.search(ln):
            continue
        out.append(ln)
    text = "\n".join(out)
    # 3) 压缩连续分隔线
    lines = text.split("\n")
    out = []
    prev_sep = False
    for ln in lines:
        if SEP.match(ln):
            if prev_sep:
                continue
            prev_sep = True
            out.append(ln)
        else:
            prev_sep = False
            out.append(ln)
    return "\n".join(out).strip()


def is_mostly_prose(text: str) -> bool:
    return "```" not in text and len(text) > 1500


def main():
    for fn in IN_FILES:
        src = os.path.join(HERE, fn)
        if not os.path.exists(src):
            print("skip (missing):", fn)
            continue
        dst = os.path.join(HERE, fn.replace(".jsonl", "_cleaned.jsonl"))
        kept = 0
        dropped = 0
        shrink = 0
        with open(src, encoding="utf-8") as f, open(dst, "w", encoding="utf-8") as g:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    dropped += 1
                    continue
                msgs = rec.get("messages")
                if not msgs:
                    g.write(line + "\n")
                    kept += 1
                    continue
                new_msgs = []
                changed = False
                for m in msgs:
                    if m.get("role") == "assistant" and isinstance(m.get("content"), str):
                        cleaned = clean_text(m["content"])
                        if len(cleaned) < len(m["content"]):
                            shrink += len(m["content"]) - len(cleaned)
                            changed = True
                        m = dict(m)
                        m["content"] = cleaned
                    new_msgs.append(m)
                # 下采样：若清洗后 assistant 仍超长且纯散文，丢弃该条
                asst = [m.get("content") or "" for m in new_msgs if m.get("role") == "assistant"]
                if asst and all(is_mostly_prose(a) for a in asst):
                    dropped += 1
                    continue
                rec = dict(rec)
                rec["messages"] = new_msgs
                g.write(json.dumps(rec, ensure_ascii=False) + "\n")
                kept += 1
        print(f"{fn}: kept={kept} dropped={dropped} 共削减字符={shrink}")


if __name__ == "__main__":
    main()
