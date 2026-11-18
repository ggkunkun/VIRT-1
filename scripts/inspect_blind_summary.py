import os
import sys
import json

path = sys.argv[1] if len(sys.argv) > 1 else 'runs/eval/all_models_blind_test_v2_20261107/summary.json'
if not os.path.exists(path):
    path = 'runs/eval/all_models_blind_test_20261107/summary.json'

with open(path, encoding='utf-8') as f:
    data = json.load(f)

dims_list = ['reasoning', 'knowledge', 'instruction', 'generation', 'generalization', 'boundary', 'toolcall']

hdr = f"{'Model Tag':32} | {'Overall':7} | " + " | ".join(f"{d[:4].upper():4}" for d in dims_list) + " | Run ID"
print(hdr)
print("-" * len(hdr))

for tag, info in data.get('models', {}).items():
    det = info.get('detail', {})
    overall = det.get('overall_weighted', 0.0)
    dims = det.get('dimensions', {})
    rid = det.get('run_id', 'unknown')
    scores = []
    for d in dims_list:
        s = dims.get(d, {}).get('score', 0.0)
        scores.append(f"{s:4.1f}")
    dim_str = " | ".join(scores)
    print(f"{tag:32} | {overall:7.2f} | {dim_str} | {rid}")
