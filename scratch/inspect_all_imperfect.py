import sys
sys.path.insert(0, '.')
sys.path.insert(0, 'scratch')
import json
from virtu_eval.graders import score_case

for dim in ['generation', 'generalization', 'reasoning', 'knowledge']:
    with open(f'data/benchmark/virtu_eval_v1/{dim}.jsonl', 'r', encoding='utf-8') as f:
        cases = [json.loads(line) for line in f]

    with open('D:/Virtu模型/models/virtu-13b/raw.jsonl', 'r', encoding='utf-8') as f:
        raw_map = {json.loads(line)['case_id']: json.loads(line) for line in f if json.loads(line).get('dimension') == dim}

    print(f"\n=== [{dim.upper()}] Imperfect Cases ===")
    for c in cases:
        cid = c['id']
        raw_resp = raw_map[cid]['response']
        sc = score_case(raw_resp, c['criteria'])
        if sc['score'] < 90:
            print(f"[{cid}] ({sc['score']:.1f}) Q: {c['prompt'][:60]}")
            for crit in sc['criteria']:
                if not crit['passed']:
                    print(f"   FAIL: {crit['key']} ({crit['type']}) -> {crit['evidence']}")
