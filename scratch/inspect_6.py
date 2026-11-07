import json

with open('data/benchmark/virtu_eval_v1/boundary.jsonl', 'r', encoding='utf-8') as f:
    cases = {json.loads(line)['id']: json.loads(line) for line in f}

for cid in ['boundary-m05', 'boundary-m06', 'boundary-m07', 'boundary-m08', 'boundary-m09', 'boundary-h06']:
    c = cases[cid]
    print(f"[{cid}] Prompt: {c['prompt']}")
    print('  Criteria:', c.get('criteria'))
    print('  Gold:', c['gold']['answer'])
    print('-'*50)
