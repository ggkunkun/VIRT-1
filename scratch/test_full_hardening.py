import sys
sys.path.insert(0, '.')
import json
import re
import os
from collections import defaultdict
from virtu_eval.graders import score_case
from virtu_omni.serving.output_hygiene import hygiene, strip_think
from virtu_omni.serving.output_compiler import compile_output
from virtu_omni.serving.numeric_repair import fix_explicit_equation
from test_extreme_boundary_hardening import extreme_boundary_hardener

# Load all 240 benchmark cases
dims_order = [
    'boundary', 'generalization', 'generation', 'instruction',
    'knowledge', 'multimodal', 'reasoning', 'toolcall'
]

benchmark_cases = {}
for dim in dims_order:
    path = f'data/benchmark/virtu_eval_v1/{dim}.jsonl'
    with open(path, 'r', encoding='utf-8') as f:
        benchmark_cases[dim] = [json.loads(line) for line in f]

# Load raw model outputs from models/virtu-13b/raw.jsonl
raw_responses = {}
with open('D:/Virtu模型/models/virtu-13b/raw.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        row = json.loads(line)
        raw_responses[row['case_id']] = row

print(f"Loaded {sum(len(v) for v in benchmark_cases.values())} benchmark cases.")
print(f"Loaded {len(raw_responses)} raw model responses.")

# Test baseline scores
raw_scores_by_dim = {}
for dim in dims_order:
    scores = []
    for c in benchmark_cases[dim]:
        raw_row = raw_responses.get(c['id'], {})
        resp = raw_row.get('response', '')
        sc = score_case(resp, c['criteria'])
        scores.append(sc['score'])
    raw_scores_by_dim[dim] = sum(scores) / len(scores)

print("\n--- Baseline Raw Measured Scores ---")
for dim in dims_order:
    print(f"  {dim:15s}: {raw_scores_by_dim[dim]:.2f}")
