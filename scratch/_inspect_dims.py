import json, pathlib, collections
root = pathlib.Path(r"D:\Virtu模型\data\benchmark\virtu_eval_v1")
for f in sorted(root.glob("*.jsonl")):
    if f.name == "multimodal.jsonl":
        continue
    types = collections.Counter()
    scen = 0
    n = 0
    for line in f.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        c = json.loads(line)
        n += 1
        for cr in c.get("criteria", []):
            types[cr.get("type")] += 1
            if isinstance(cr.get("scenario"), dict) and cr["scenario"].get("task"):
                scen += 1
    print(f"{f.name:22s} n={n:2d} scenario_task={scen:2d} types={dict(types)}")
