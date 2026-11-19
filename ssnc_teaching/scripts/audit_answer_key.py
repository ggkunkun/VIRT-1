# -*- coding: utf-8 -*-
"""答案键审计：核对 jsonl 内嵌答案与 answer_key.json 一致性，输出分布。"""
import json
from collections import Counter

BASE = r"D:\Virtu模型\ssnc_teaching\tests"
tcs = [json.loads(l) for l in open(BASE + r"\sscnc_testcases.jsonl", encoding="utf-8") if l.strip()]
ak = json.load(open(BASE + r"\answer_key.json", encoding="utf-8"))

print("total:", len(tcs), "key entries:", len(ak))
print("answer distribution:", dict(Counter(t["answer"] for t in tcs)))
mismatch = [(t["id"], t["answer"], ak.get(t["id"])) for t in tcs if ak.get(t["id"]) != t["answer"]]
print("jsonl<->key mismatches:", mismatch)
missing = [t["id"] for t in tcs if t["id"] not in ak]
extra = [k for k in ak if k not in {t["id"] for t in tcs}]
print("missing in key:", missing, "extra in key:", extra)
# 每题正确选项文本唯一性
bad = [t["id"] for t in tcs if len(set(t["options"])) != 4]
print("dup-option cases:", bad)
print("verified dist:", dict(Counter(t.get("verified") for t in tcs)))
print("category dist:", dict(Counter(t["category"] for t in tcs)))
for t in tcs:
    print(t["id"], t["answer"], t["options"][ord(t["answer"]) - 65][:50])

if mismatch or missing or extra or bad:
    raise SystemExit(1)
print("AUDIT OK")
