import sys
sys.path.insert(0, '.')
import json
from virtu_eval.graders import score_case

with open('data/benchmark/virtu_eval_v1/boundary.jsonl', 'r', encoding='utf-8') as f:
    cases = [json.loads(line) for line in f]

raw_map = {}
with open('D:/Virtu模型/models/virtu-13b/raw.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        row = json.loads(line)
        if row.get('dimension') == 'boundary':
            raw_map[row['case_id']] = row

failed_cases = []
for c in cases:
    cid = c['id']
    raw_item = raw_map.get(cid)
    resp = raw_item.get('response') if raw_item else ""
    res = score_case(resp, c['criteria'])
    if res['score'] < 100.0:
        failed_cases.append({
            'id': cid,
            'tier': c['tier'],
            'tags': c.get('tags'),
            'score': res['score'],
            'prompt': c['prompt'],
            'gold': c['gold'],
            'criteria': c['criteria'],
            'resp': resp,
            'details': res['criteria']
        })

print(f"Total cases scoring < 100: {len(failed_cases)} / {len(cases)}")
for fc in failed_cases:
    print(f"\n--- [{fc['id']}] ({fc['tier']}) Score: {fc['score']} ---")
    print(f"Tags: {fc['tags']}")
    print(f"Prompt: {fc['prompt']}")
    print(f"Gold: {fc['gold']['answer'][:100]}...")
    print(f"Resp: {fc['resp'][:120]}...")
    for crit in fc['details']:
        if not crit['passed']:
            print(f"  FAILED criterion: {crit['key']} ({crit['type']}) -> {crit['evidence']}")
