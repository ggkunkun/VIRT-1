"""Inspect cloud blind test results."""
import json
from remote_damodel_helper import exec_remote

cmd = "python3 -c \"import json; data=json.load(open('/root/workspace/Virtu/benchmarks/cad_cam_blind_test_results.json')); print('Total:', len(data['results']), 'Passed:', data['passed']); [print(r['test_id'], r['software'], r['score'], r['errors']) for r in data['results'] if not r['passed']]\""
out, err = exec_remote(cmd)
print("STDOUT:\n", out)
if err:
    print("STDERR:\n", err)
