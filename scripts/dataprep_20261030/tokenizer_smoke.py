# -*- coding: utf-8 -*-
"""
真实分词器冒烟测试：用仓库内的 Qwen3-8B tokenizer 对主训练集做
与 train_virtu.py 完全一致的 ChatML 拼装 + 编码 + 截断 + label 对齐，
验证数据能真正喂进训练管线。
"""
import sys, os, json, statistics
sys.stdout.reconfigure(encoding="utf-8")
from tokenizers import Tokenizer

TOK_DIR = r"D:\Virtu模型\checkpoints\_base_qwen3_8b"
DATA = r"E:\数据\00_UNIFIED_MASTER_TRAIN\virtu_master_train_sft.jsonl"

tok = Tokenizer.from_file(os.path.join(TOK_DIR, "tokenizer.json"))
print("tokenizer 载入成功 · vocab =", tok.get_vocab_size())

samples = []
with open(DATA, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:
            samples.append(json.loads(line))

MAX_LEN = 2048
lens, truncated, label_bad, empty = [], 0, 0, 0
for s in samples:
    msgs = s["messages"]
    sys_m = next((m["content"] for m in msgs if m["role"] == "system"), "")
    usr_m = next((m["content"] for m in msgs if m["role"] == "user"), "")
    asst_m = next((m["content"] for m in msgs if m["role"] == "assistant"), "")
    if not usr_m or not asst_m:
        empty += 1
        continue
    prompt = (f"<|im_start|>system\n{sys_m}<|im_end|>\n"
              f"<|im_start|>user\n{usr_m}<|im_end|>\n"
              f"<|im_start|>assistant\n")
    full = prompt + asst_m + "<|im_end|>"
    p_ids = tok.encode(prompt).ids
    f_ids = tok.encode(full).ids
    if len(f_ids) > MAX_LEN:
        truncated += 1
        f_ids = f_ids[:MAX_LEN]
        p_ids = p_ids[:MAX_LEN]
    labels = [-100] * len(p_ids) + f_ids[len(p_ids):]
    if len(labels) != len(f_ids):
        label_bad += 1
    if not any(x != -100 for x in labels):
        label_bad += 1
    lens.append(len(f_ids))

lens_sorted = sorted(lens)
print()
print("=" * 70)
print("Qwen3-8B 真实分词结果")
print("=" * 70)
print(f"  样本数            : {len(samples)}")
print(f"  可编码样本        : {len(lens)}（user/assistant 缺失 {empty}）")
print(f"  token 长度 min/中位/均值/max : "
      f"{min(lens)} / {lens_sorted[len(lens)//2]} / {int(statistics.mean(lens))} / {max(lens)}")
print(f"  超过 max_len=2048 被截断    : {truncated} "
      f"({truncated/len(lens)*100:.1f}%)")
print(f"  label 对齐异常               : {label_bad}")
tot = sum(lens)
print(f"  全量 token 总量              : {tot:,}")
print(f"  平均每 epoch 步数(bs2×ga4=8) : {tot/8:,.0f}")

# 特殊标记是否正确切分
probe = tok.encode("<|im_start|>user\n测试<|im_end|>\n").tokens
print()
print("  ChatML 特殊标记切分抽样:", [t for t in probe if "im_" in t])

# 新旧样本对比
new = [s for s in samples if s.get("source_type")]
old = [s for s in samples if not s.get("source_type")]
def stat(rows):
    out = []
    for s in rows:
        m = s["messages"]
        txt = "".join(x.get("content", "") for x in m)
        out.append(len(tok.encode(txt).ids))
    return out
if new and old:
    a, b = stat(new), stat(old)
    print()
    print(f"  新增样本 {len(a)} 条：中位 {int(statistics.median(a))} tokens")
    print(f"  原有样本 {len(b)} 条：中位 {int(statistics.median(b))} tokens")

ok = (empty == 0 and label_bad == 0)
print()
print("结论：", "训练管线兼容（labels 对齐正确、无空样本）" if ok
      else "存在兼容性问题")
sys.exit(0 if ok else 1)
