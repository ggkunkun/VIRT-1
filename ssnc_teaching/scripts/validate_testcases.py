# -*- coding: utf-8 -*-
"""校验测试用例：答案必须是选项之一；每题4个去重选项；统计分布。"""
import json
from collections import Counter

p = r"D:\Virtu模型\ssnc_teaching\tests\sscnc_testcases.jsonl"
tcs = [json.loads(l) for l in open(p, encoding='utf-8') if l.strip()]

issues = []
for t in tcs:
    opts = t['options']
    if len(opts) != 4:
        issues.append((t['id'], '选项数≠4', len(opts)))
    if len(set(opts)) != len(opts):
        issues.append((t['id'], '选项重复', opts))
    if t['answer'] not in 'ABCD':
        issues.append((t['id'], '答案非ABCD', t['answer']))
    else:
        idx = ord(t['answer'])-65
        if idx >= len(opts):
            issues.append((t['id'], '答案越界', t['answer']))
        else:
            print("CHECK %-4s ans=%s -> %s" % (t['id'], t['answer'], opts[idx]))

print("\n=== issues (%d) ===" % len(issues))
for x in issues:
    print("  ", x)
