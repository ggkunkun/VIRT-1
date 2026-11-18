import json

path = "runs/eval/all_models_blind_test_v3_20261108/virtu-v3_hardened/raw.jsonl"
with open(path, "r", encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        if r.get("score", 0) < 100:
            print(f"[{r['case_id']}] dim={r['dimension']} score={r['score']}")
            print(f"  prompt: {r.get('prompt')}")
            print(f"  response: {repr(r.get('response'))}")
            unpassed = [c for c in r.get("criteria", []) if not c.get("passed")]
            for c in unpassed:
                print(f"  failed crit [{c.get('key')} / {c.get('type')}]: {c.get('evidence')}")
            print("-" * 60)
