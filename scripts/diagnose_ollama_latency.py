"""Why is every Ollama request paying 80 seconds?

Ollama reports three durations per request:

  load_duration   - time spent materialising the model in VRAM
  prompt_eval_duration - time spent ingesting the prompt
  eval_duration   - time spent generating tokens

If load_duration dominates, the model is being evicted between requests and
the benchmark measures disk I/O, not the model.  This sweeps the two knobs
that control it (context size and keep_alive) and reports the actual split.
"""

from __future__ import annotations

import json
import time
import urllib.request

OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
URL = "http://127.0.0.1:11434/api/chat"


def ask(model, num_ctx, keep_alive, num_predict=128, prompt="用一句话说明什么是切削速度 Vc。"):
    payload = {"model": model,
               "messages": [{"role": "user", "content": prompt}],
               "stream": False, "think": False,
               "options": {"temperature": 0, "seed": 1,
                           "num_predict": num_predict, "num_ctx": num_ctx}}
    if keep_alive:
        payload["keep_alive"] = keep_alive
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(URL, data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    t0 = time.perf_counter()
    with OPENER.open(req, timeout=900) as resp:
        d = json.loads(resp.read().decode("utf-8", "replace"))
    wall = time.perf_counter() - t0
    return {
        "wall_s": round(wall, 1),
        "load_s": round((d.get("load_duration") or 0) / 1e9, 1),
        "prompt_s": round((d.get("prompt_eval_duration") or 0) / 1e9, 2),
        "eval_s": round((d.get("eval_duration") or 0) / 1e9, 2),
        "tokens": d.get("eval_count"),
        "tok_per_s": round((d.get("eval_count") or 0) / ((d.get("eval_duration") or 1) / 1e9), 2),
    }


def main():
    model = "virtu-omni-8b:v2"
    print("=== warm-up ===")
    print(" ", ask(model, 1024, "10m", num_predict=16))
    for num_ctx, keep in ((1024, "10m"), (2048, "10m"), (4096, "10m"), (1024, None)):
        print(f"\n=== num_ctx={num_ctx} keep_alive={keep} ===")
        for i in range(3):
            print(f"  run{i}", ask(model, num_ctx, keep))


if __name__ == "__main__":
    main()
