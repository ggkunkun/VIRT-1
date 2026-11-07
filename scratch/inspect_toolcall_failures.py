import sys
sys.path.insert(0, '.')
import json
from virtu_eval.graders import score_case

with open('data/benchmark/virtu_eval_v1/toolcall.jsonl', 'r', encoding='utf-8') as f:
    cases = [json.loads(line) for line in f]

raw_map = {}
with open('D:/Virtu模型/models/virtu-13b/raw.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        row = json.loads(line)
        if row.get('dimension') == 'toolcall':
            raw_map[row['case_id']] = row

print(f"Total toolcall cases: {len(cases)}")
for c in cases:
    cid = c['id']
    tier = c['tier']
    prompt = c['prompt']
    raw_row = raw_map.get(cid, {})
    raw_resp = raw_row.get('response', '')
    sc = score_case(raw_resp, c['criteria'])
    if sc['score'] < 100.0:
        print(f"[{cid}] ({tier}) Score: {sc['score']:.1f}")
        print(f"  Prompt: {prompt[:80].replace(chr(10), ' ')}")
        print(f"  Resp: {raw_resp[:90].replace(chr(10), ' ')}")
        for crit in sc['criteria']:
            if not crit['passed']:
                print(f"    FAIL: {crit['key']} ({crit['type']}) -> {crit['evidence']}")
