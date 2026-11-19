# -*- coding: utf-8 -*-
"""重排测试用例选项位置，使答案分布均衡（A/B/C/D），保持每题正确答案文本不变。"""
import json, random

P = r"D:\Virtu模型\ssnc_teaching\tests\sscnc_testcases.jsonl"
tcs = [json.loads(l) for l in open(P, encoding='utf-8') if l.strip()]
random.seed(7212026)  # 确定性，可复跑

# 目标：让答案均匀分布，按 id 顺序循环分配目标答案位置
targets = ['A','B','C','D']
for idx, t in enumerate(tcs):
    opts = t['options'][:]
    ans_idx = ord(t['answer']) - 65
    correct_text = opts[ans_idx]
    # 目标位置轮换（打散规律）
    target_idx = idx % 4
    # 其余选项随机排列
    others = [o for j,o in enumerate(opts) if j != ans_idx]
    random.shuffle(others)
    new_opts = others[:target_idx] + [correct_text] + others[target_idx:]
    t['options'] = new_opts
    t['answer'] = chr(65 + target_idx)

with open(P, 'w', encoding='utf-8') as f:
    for t in tcs:
        f.write(json.dumps(t, ensure_ascii=False)+"\n")

# 更新答案键
json.dump({t['id']: t['answer'] for t in tcs},
          open(r"D:\Virtu模型\ssnc_teaching\tests\answer_key.json",'w',encoding='utf-8'),
          ensure_ascii=False, indent=1)

from collections import Counter
print("answer distribution:", dict(Counter(t['answer'] for t in tcs)))
# 校验无重复、答案有效
bad=[]
for t in tcs:
    if len(set(t['options']))!=4 or t['options'][ord(t['answer'])-65] is None:
        bad.append(t['id'])
print("invalid cases:", bad)
