"""Detailed inspector for evaluation results."""
from remote_damodel_helper import exec_remote

script = """
import json

with open('/root/workspace/Virtu/benchmarks/cad_cam_blind_test_results.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

for r in data['results']:
    if not r['passed']:
        print(f"=== {r['test_id']} [{r['software']}] Score: {r['score']} ===")
        print(f"Errors: {r['errors']}")
        print(f"Preview: {r['response_preview']}")
        print()
"""

out, err = exec_remote(f"python3 -c \"{script}\"")
print(out)
if err:
    print("STDERR:", err)
