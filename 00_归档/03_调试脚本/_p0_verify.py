#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P0 验收闸：对 :fast 两个部署画像做速度/显存/退化/think 四项实测。"""
import json, re, sys, time, urllib.request

BASE = "http://127.0.0.1:11434"
PROMPTS = [
    ("G71语义", "FANUC G71 循环里 U、R、F 三个地址分别代表什么？各一句话。"),
    ("退刀退化诱因", "解释数控车削中退刀量对加工的影响。"),
]

def post(path, payload, timeout=300):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())

def get(path):
    with urllib.request.urlopen(BASE + path, timeout=10) as r:
        return json.loads(r.read())

def max_repeat(text, n=6):
    toks = re.findall(r"\S+", text)
    best, cnt = 0, {}
    for i in range(len(toks) - n + 1):
        g = " ".join(toks[i:i+n])
        cnt[g] = cnt.get(g, 0) + 1
        best = max(best, cnt[g])
    return best

def run(model, prompt, npred=160):
    t0 = time.time()
    r = post("/api/generate", {
        "model": model, "prompt": prompt, "stream": False,
        "options": {"num_predict": npred},
    })
    wall = time.time() - t0
    ec = r.get("eval_count", 0)
    ed = r.get("eval_duration", 1) / 1e9
    return {"model": model, "tok_s": round(ec / ed, 2) if ed else 0,
            "eval_count": ec, "wall_s": round(wall, 1),
            "load_s": round(r.get("load_duration", 0) / 1e9, 1),
            "text": r.get("response", "")}

results = []
for model in ["virtu-comprehensive:fast", "virtu-moe-14b:fast"]:
    for tag, p in PROMPTS:
        runs = []
        for k in range(3 if tag == "G71语义" else 1):
            out = run(model, p)
            ps = get("/api/ps")["models"]
            proc = ps[0].get("size_vram", 0) / ps[0].get("size", 1) * 100 if ps else 0
            runs.append(out)
            print(f"[{model}] {tag} #{k+1}: {out['tok_s']} tok/s  vram={proc:.0f}%  "
                  f"load={out['load_s']}s  len={out['eval_count']}", flush=True)
        texts = [r["text"] for r in runs]
        rep = max(max_repeat(t) for t in texts)
        think = any("<think" in t or "</think" in t for t in texts)
        hits = sum(1 for t in texts if re.search(r"专家\s*[12１２]|内部专家|正在执行以下步骤|分工", t))
        results.append({"model": model, "case": tag,
                        "tok_s": [r["tok_s"] for r in runs],
                        "gpu_pct": round(proc), "max_repeat6": rep,
                        "think_leak": think, "cosplay_hits": hits,
                        "sample": texts[0][:400]})

print("\n=== 汇总 ===")
for r in results:
    print(json.dumps({k: v for k, v in r.items() if k != "sample"}, ensure_ascii=False))
print("\n=== 首条样本 (G71) ===")
for r in results:
    if r["case"] == "G71语义":
        print(f"\n--- {r['model']} ---\n{r['sample']}")
