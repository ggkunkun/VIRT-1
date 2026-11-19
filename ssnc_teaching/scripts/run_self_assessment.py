# -*- coding: utf-8 -*-
"""能力考核自测：用测试用例集对教学体系知识做一次模拟作答，验证判分链路与验收口径。
说明：此处模拟的是'教学体系覆盖度自检'——检查每道有据用例的答案是否能在其一手依据文档中找到支撑，
不是宣称 Agent 已通过真实软件操作考核。"""
import json, os, re

ROOT = r"D:\Virtu模型\ssnc_teaching"
tcs = [json.loads(l) for l in open(os.path.join(ROOT,"tests","sscnc_testcases.jsonl"),encoding='utf-8') if l.strip()]

# 加载一手文本作为检索语料。
# 关键：必须排除 docs/04_测试用例集与能力考核.md 与 tests/ 目录，
# 因为它们复述了用例答案，纳入语料会造成"自检索命中自己"的虚假 100%（数据污染）。
EXCLUDE = {"04_测试用例集与能力考核.md"}
corpus = []
for sub in ["docs", "evidence", "source/help_kb_md", "source"]:
    d = os.path.join(ROOT, sub)
    if not os.path.isdir(d): continue
    for fn in os.listdir(d):
        fp = os.path.join(d, fn)
        if fn in EXCLUDE:
            continue
        if os.path.isfile(fp) and fn.endswith(('.md','.json')):
            try: corpus.append(open(fp,encoding='utf-8').read())
            except: pass
big = "\n".join(corpus)

# 对每个用例：检查其"正确选项文本"是否能在语料中检索到（作为有据支撑的近似判定）
def answer_text(t): return t['options'][ord(t['answer'])-65]

supported = 0
unsupported = []
for t in tcs:
    at = answer_text(t)
    # 取答案中的关键中文/数字片段做检索
    key = re.sub(r'[()（）/·\s]', '', at)
    fragments = [f for f in re.findall(r'[\u4e00-\u9fff]{2,}|[A-Za-z0-9]{2,}', at) if len(f)>=2]
    hit = any(frag in big for frag in fragments) if fragments else (at in big)
    if hit: supported += 1
    else: unsupported.append((t['id'], at, t['verified']))

total = len(tcs)
print("总用例:", total)
print("答案文本可在教学语料中检索到支撑:", supported)
print("检索不到(需补充文档或属外推):", len(unsupported))
print("覆盖率: %.1f%%" % (100.0*supported/total))
print("\n未命中样例(前20):")
for x in unsupported[:20]:
    print("  ", x)

# 分层统计
from collections import Counter
print("\n按验证类型覆盖率:")
def has_support(t):
    frags = [f for f in re.findall(r'[\u4e00-\u9fff]{2,}|[A-Za-z0-9]{2,}', answer_text(t)) if len(f)>=2]
    return any(f in big for f in frags) if frags else (answer_text(t) in big)
for v in ['measured','official','standard']:
    grp=[t for t in tcs if t['verified']==v]
    s=sum(1 for t in grp if has_support(t))
    print("  %-10s %d/%d" % (v,s,len(grp)))
