#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Virtu 模型本机适配基准：逐模型 × 逐 profile 测 tok/s / 显存 / 是否超限"""
import json, time, sys, urllib.request, subprocess, os

API = "http://127.0.0.1:11434"
PROMPT = "用一句话解释什么是数控加工中心。"
NUM_PREDICT = 96

def post(path, payload, timeout=900):
    req = urllib.request.Request(API + path,
                                 data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())

def unload(model):
    try:
        post("/api/chat", {"model": model, "messages": [{"role": "user", "content": "x"}],
                           "keep_alive": 0, "stream": False,
                           "options": {"num_predict": 1}})
    except Exception:
        pass

def probe(model, num_gpu, num_ctx):
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": PROMPT}],
        "stream": False,
        "keep_alive": "2m",
        "options": {
            "num_gpu": num_gpu,
            "num_ctx": num_ctx,
            "num_predict": NUM_PREDICT,
            "temperature": 0,
            "top_p": 1,
            "num_thread": 10,
        },
    }
    t0 = time.time()
    try:
        r = post("/api/chat", payload)
    except Exception as e:
        return {"ok": False, "err": str(e)[:200], "wall": round(time.time() - t0, 1)}
    wall = time.time() - t0
    ev_count = r.get("eval_count") or 0
    ev_dur = (r.get("eval_duration") or 1) / 1e9
    ld_dur = (r.get("load_duration") or 0) / 1e9
    pm_dur = (r.get("prompt_eval_duration") or 0) / 1e9
    tps = ev_count / ev_dur if ev_dur > 0 and ev_count else 0
    return {
        "ok": True,
        "tok_s": round(tps, 2),
        "load_s": round(ld_dur, 1),
        "prefill_s": round(pm_dur, 1),
        "eval_count": ev_count,
        "wall_s": round(wall, 1),
        "size_gb": round((r.get("model_size") or 0) / 1e9, 2) if r.get("model_size") else None,
        "sample": (r.get("message", {}).get("content") or "")[:60].replace("\n", " "),
    }

def vram():
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=20).stdout.strip()
        u, t = [int(x) for x in out.split(",")]
        return u, t
    except Exception:
        return None, None

if __name__ == "__main__":
    plan = json.load(open(sys.argv[1], encoding="utf-8"))
    out_path = sys.argv[2]
    results = []
    for item in plan:
        model = item["model"]
        for prof in item["profiles"]:
            ng, nc = prof["num_gpu"], prof["num_ctx"]
            u0, total = vram()
            res = probe(model, ng, nc)
            u1, _ = vram()
            rec = {"model": model, "num_gpu": ng, "num_ctx": nc,
                   "vram_used_before": u0, "vram_used_after": u1, "vram_total": total}
            rec.update(res)
            results.append(rec)
            print(json.dumps(rec, ensure_ascii=False), flush=True)
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=1)
        unload(model)
    print("DONE", len(results))
