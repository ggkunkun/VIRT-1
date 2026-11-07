"""Inspect full text of failed test cases."""
import json
from remote_damodel_helper import exec_remote

cmd = """python3 -c "
import json
data = json.load(open('/root/workspace/Virtu/benchmarks/cad_cam_blind_test_results.json'))
for id_ in ['blind_002', 'blind_004', 'blind_005', 'blind_006']:
    r = next(x for x in data['results'] if x['test_id'] == id_)
    print('### CASE:', r['test_id'], r['software'], r['score'], r['errors'])
    print(r.get('response_preview'))
" """
out, err = exec_remote(cmd)
print(out)
