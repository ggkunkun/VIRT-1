import json, os

models = ['virtu-v3:hardened', 'virtu-13.63b:hardened', 'virtu-moe-14b:hardened', 'virtu-v3-all90-q4_0:latest', 'qwen3:8b']
cases_seen = ['rsipool-i-001', 'rsipool-i-022', 'rsipool-n-001', 'rsipool-n-022']

for cid in cases_seen:
    print(f"\n=== Case: {cid} ===")
    for m in models:
        m_dir = m.replace(':', '_').replace('/', '_')
        raw_p = os.path.join('runs/eval/all_models_blind_test_20261107', m_dir, 'raw.jsonl')
        if os.path.exists(raw_p):
            for l in open(raw_p, encoding='utf-8'):
                rec = json.loads(l)
                if rec['case_id'] == cid:
                    print(f"  {m:30} score={rec['score']:5.1f} resp={rec['response'][:60]!r}")
