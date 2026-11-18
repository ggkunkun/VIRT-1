import json

for folder in ['virtu-v3_hardened', 'virtu-moe-14b_hardened', 'virtu-13.63b_hardened']:
    path = f'runs/eval/all_models_blind_test_v3_clean_20261108/{folder}/raw.jsonl'
    print('='*30, folder, '='*30)
    for line in open(path, encoding='utf-8'):
        r = json.loads(line)
        if r.get('score', 0) < 100:
            print(f"[{r['case_id']}] dim={r['dimension']} score={r['score']}")
            print(f"  prompt: {r.get('prompt')}")
            print(f"  response: {repr(r.get('response'))}")
            for c in r.get('criteria', []):
                if not c.get('passed'):
                    print(f"  FAILED [{c.get('key')} / {c.get('type')}]: {c.get('evidence')}")
            print('-'*50)
