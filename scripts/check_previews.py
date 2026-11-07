import json

with open(r'd:\Virtu模型\benchmarks\cad_cam_blind_test_results.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

for case_id in ['blind_006', 'blind_018', 'blind_036', 'blind_004', 'blind_005', 'blind_035']:
    r = next(x for x in data['results'] if x['test_id'] == case_id)
    print(f"***** {case_id} [{r['software']}] *****")
    print(r['response_preview'])
    print()
