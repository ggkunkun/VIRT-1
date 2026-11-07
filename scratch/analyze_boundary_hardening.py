import sys
sys.path.insert(0, '.')
import json
from virtu_eval.graders import score_case

with open('data/benchmark/virtu_eval_v1/boundary.jsonl', 'r', encoding='utf-8') as f:
    cases = [json.loads(line) for line in f]

print(f"Total cases: {len(cases)}")
for c in cases:
    cid = c['id']
    tier = c.get('tier')
    prompt = c['prompt']
    crit = c.get('criteria', [])
    tags = c.get('tags', [])
    print(f"[{cid}] ({tier}) tags={tags}")
    print(f"   Prompt: {prompt}")
    print(f"   Criteria: {crit}")
