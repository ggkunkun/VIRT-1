import sys
sys.path.insert(0, '.')
import json
import re
from virtu_eval.graders import score_case
from virtu_omni.serving.deception_gate import gate_answer

with open('data/benchmark/virtu_eval_v1/boundary.jsonl', 'r', encoding='utf-8') as f:
    cases = [json.loads(line) for line in f]

# Read original raw responses
raw_map = {}
with open('D:/Virtu模型/models/virtu-13b/raw.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        row = json.loads(line)
        if row.get('dimension') == 'boundary':
            raw_map[row['case_id']] = row

print(f"Loaded {len(cases)} boundary benchmark cases, {len(raw_map)} raw responses.")

# Test scoring raw responses first to double check baseline
raw_scores = []
for c in cases:
    cid = c['id']
    raw_item = raw_map.get(cid)
    resp = raw_item.get('response') if raw_item else ""
    res = score_case(resp, c['criteria'])
    raw_scores.append(res['score'])

print(f"Raw model measured boundary score: {sum(raw_scores)/len(raw_scores):.2f}")
