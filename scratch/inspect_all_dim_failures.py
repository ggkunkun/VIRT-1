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

print("Dimensions summary in raw.jsonl:")
for dim, rows in sorted(dim_cases.items()):
    scores = [r.get('score', 0.0) for r in rows]
    avg = sum(scores) / len(scores)
    passed_cnt = sum(1 for r in rows if r.get('score', 0.0) >= 90.0)
    print(f"  {dim:15s}: count={len(rows):2d}, mean={avg:5.2f}, >=90={passed_cnt:2d}")
