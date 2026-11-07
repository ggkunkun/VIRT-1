import sys
sys.path.insert(0, '.')
import json
from virtu_eval.graders import score_case
from virtu_omni.serving.output_hygiene import hygiene, strip_think
from virtu_omni.serving.output_compiler import compile_output

with open('data/benchmark/virtu_eval_v1/instruction.jsonl', 'r', encoding='utf-8') as f:
    cases = [json.loads(line) for line in f]

raw_map = {}
with open('D:/Virtu模型/models/virtu-13b/raw.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        row = json.loads(line)
        if row.get('dimension') == 'instruction':
            raw_map[row['case_id']] = row

for c in cases:
    cid = c['id']
    prompt = c['prompt']
    raw_row = raw_map.get(cid, {})
    raw_resp = raw_row.get('response', '')

    cl = strip_think(raw_resp)
    cl = hygiene(cl)
    cl = compile_output(prompt, cl)
    sc = score_case(cl, c['criteria'])
    if sc['score'] < 100.0:
        print(f"[{cid}] ({sc['score']:.1f})")
        print(f"  Prompt: {prompt[:70]}")
        print(f"  Resp: {cl[:80].replace(chr(10), ' ')}")
        for crit in sc['criteria']:
            if not crit['passed']:
                print(f"    FAIL: {crit['key']} ({crit['type']}) -> {crit['evidence']}")
