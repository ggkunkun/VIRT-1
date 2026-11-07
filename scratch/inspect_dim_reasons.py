import sys
sys.path.insert(0, '.')
import json
from collections import defaultdict
from virtu_eval.graders import score_case

dim_cases = defaultdict(list)
with open('D:/Virtu模型/models/virtu-13b/raw.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        row = json.loads(line)
        dim_cases[row['dimension']].append(row)

for dim in ['instruction', 'toolcall', 'reasoning', 'knowledge', 'generalization', 'generation']:
    rows = dim_cases[dim]
    print(f"\n==================== [{dim.upper()}] Failures ====================")
    failures = [r for r in rows if r.get('score', 0.0) < 90.0]
    print(f"Total < 90: {len(failures)} / {len(rows)}")
    for f in failures[:3]:
        cid = f['case_id']
        sc = f.get('score')
        prompt = f.get('prompt', '')[:80].replace('\n', ' ')
        resp = str(f.get('response') or '')[:100].replace('\n', ' ')
        print(f"  [{cid}] ({sc:.1f}) Q: {prompt}")
        print(f"     A: {resp}")
        # print failed criteria
        for crit in f.get('criteria', []):
            if not crit.get('passed', True):
                print(f"     FAILED: {crit.get('key')} ({crit.get('type')}) -> {crit.get('evidence')}")
