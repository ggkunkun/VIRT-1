import json

with open(r'd:\Virtu模型\benchmarks\cad_cam_blind_test_results.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f"Total: {data['total_cases']}, Passed: {data['passed']}, Rate: {data['pass_rate_pct']:.1f}%")
print("="*60)
for r in data['results']:
    if not r['passed']:
        print(f"[{r['test_id']}] Software: {r['software']} | Score: {r['score']}")
        print(f"Errors: {r['errors']}")
        print(f"Prompt snippet: {r['prompt'][:80]}...")
        print(f"Preview snippet: {r['response_preview'][:150]}...")
        print("-" * 60)
