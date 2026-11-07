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

scores_raw = []
scores_cleaned = []

for c in cases:
    cid = c['id']
    prompt = c['prompt']
    raw_row = raw_map.get(cid, {})
    raw_resp = raw_row.get('response', '')

    sc_raw = score_case(raw_resp, c['criteria'])
    scores_raw.append(sc_raw['score'])

    # clean
    cl = strip_think(raw_resp)
    cl = hygiene(cl)
    cl = compile_output(prompt, cl)
    sc_clean = score_case(cl, c['criteria'])
    scores_cleaned.append(sc_clean['score'])

print(f"Instruction Raw: {sum(scores_raw)/len(scores_raw):.2f}")
print(f"Instruction with Output Pipeline: {sum(scores_cleaned)/len(scores_cleaned):.2f}")
