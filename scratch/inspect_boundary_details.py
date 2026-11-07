import json

with open('D:/Virtu模型/models/virtu-13b/raw.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        row = json.loads(line)
        if row.get('dimension') == 'boundary':
            cid = row.get('case_id')
            score = row.get('score')
            prompt = row.get('prompt', '')[:60]
            resp = str(row.get('response') or '')[:100].replace('\n', ' ')
            details = row.get('grading_details')
            print(f"[{cid}] Score: {score} | Prompt: {prompt}")
            print(f"   Resp: {resp}")
            print(f"   Details: {details}")
