import os, sys
ROOT = os.getcwd()
sys.path.insert(0, ROOT)
from virtu_eval import runner as RUNNER

case_dir = os.path.join(ROOT, 'data', 'benchmark', 'virtu_blind_test_v2')
sample = {'easy': 1, 'medium': 1}
cases = RUNNER.load_cases(case_dir, dims=['reasoning', 'knowledge', 'instruction', 'generation', 'generalization', 'boundary', 'toolcall'], sample_per_tier=sample)
print(f"Total blind test v2 cases loaded: {len(cases)}")
for c in cases:
    print(f"[{c['id']}] ({c['dimension']}/{c['tier']}): {c['prompt']}")
