from remote_damodel_helper import exec_remote
out, err = exec_remote("python3 -c \"import json; d=json.load(open('/root/workspace/Virtu/benchmarks/cad_cam_blind_test_results.json')); print([x for x in d['results'] if x['test_id']=='blind_004'][0]['response_preview'])\"")
print(out)
if err:
    print("ERR:", err)
