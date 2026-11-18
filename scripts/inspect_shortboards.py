import json

models = ['virtu-v3_hardened', 'virtu-moe-14b_hardened', 'virtu-13.63b_hardened']

for m in models:
    path = f'runs/eval/all_models_blind_test_v2_20261107/{m}/raw.jsonl'
    print('='*40, m, '='*40)
    for line in open(path, encoding='utf-8'):
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec['score'] < 100.0:
            cid = rec['case_id']
            dim = rec['dimension']
            score = rec['score']
            print(f"Case: {cid} ({dim}) | Score: {score}")
            print("Response:", repr(rec['response']))
            print("Criteria:", rec.get('criteria'))
            print("-" * 50)
