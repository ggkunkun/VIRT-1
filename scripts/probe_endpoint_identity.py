"""Endpoint identity probe for the live Virtu bridge (127.0.0.1:8000).

Answers three questions before any evaluation is scored:
  1. Is a real autoregressive model answering, or the template fallback?
  2. Which upstream actually serves the tokens (local weights vs cloud relay)?
  3. What is the measured per-request latency and decode throughput?
"""
import json
import sys
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"
OUT = "D:/Virtu模型/_eval_probe_result.json"


def post(path, payload, timeout=180):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        BASE + path,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            return {"ok": True, "status": resp.status, "elapsed": time.perf_counter() - t0, "body": raw}
    except urllib.error.HTTPError as e:
        return {"ok": False, "status": e.code, "elapsed": time.perf_counter() - t0, "body": e.read().decode("utf-8", "replace")}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "status": None, "elapsed": time.perf_counter() - t0, "body": repr(e)}


def get(path, timeout=20):
    req = urllib.request.Request(BASE + path, method="GET")
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return {"ok": True, "status": resp.status, "elapsed": time.perf_counter() - t0, "body": resp.read().decode("utf-8", "replace")}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "status": None, "elapsed": time.perf_counter() - t0, "body": repr(e)}


def chat(content, max_tokens=256, temperature=0.0, extra=None):
    payload = {
        "model": "virtu-cad-cam-10b",
        "messages": [{"role": "user", "content": content}],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if extra:
        payload.update(extra)
    r = post("/v1/chat/completions", payload)
    if r["ok"]:
        try:
            j = json.loads(r["body"])
            choices = j.get("choices") or []
            msg = (choices[0].get("message") or {}) if choices else {}
            r["parsed"] = {
                "model_field": j.get("model"),
                "content": msg.get("content"),
                "reasoning": msg.get("reasoning_content"),
                "finish_reason": (choices[0].get("finish_reason") if choices else None),
                "usage": j.get("usage"),
            }
        except Exception as e:  # noqa: BLE001
            r["parse_error"] = repr(e)
    return r


def main():
    results = {"probe_started": time.strftime("%Y-%m-%d %H:%M:%S")}

    m = get("/v1/models")
    results["models"] = {"ok": m["ok"], "body": m["body"][:800]}

    # A: persona probe - a template fallback has a fixed industrial-monologue answer.
    probes = {
        "identity": ("你是谁？请用一句话回答，并说出你的基座模型名称。", 200),
        "instruction_following": ("把下面这句话倒过来逐字输出，不要加任何解释：ABCDEFG", 200),
        "arithmetic": ("计算 17*23+11 等于多少？只输出数字。", 64),
        "cad_domain": ("G34125-1992 是什么标准？一句话回答。", 200),
    }
    results["probes"] = {}
    for key, (text, mt) in probes.items():
        r = chat(text, max_tokens=mt)
        results["probes"][key] = {
            "ok": r["ok"],
            "status": r["status"],
            "elapsed_s": round(r["elapsed"], 3),
            "parsed": r.get("parsed"),
            "raw_head": r["body"][:300] if not r.get("parsed") else None,
        }

    # B: latency/throughput, 3 warm identical requests, temp 0
    lat = []
    for i in range(3):
        r = chat("用三句话介绍一下数控铣削中的顺铣与逆铣区别。", max_tokens=300)
        p = r.get("parsed") or {}
        usage = p.get("usage") or {}
        comp = usage.get("completion_tokens")
        lat.append({
            "ok": r["ok"],
            "elapsed_s": round(r["elapsed"], 3),
            "completion_tokens": comp,
            "prompt_tokens": usage.get("prompt_tokens"),
            "tok_per_s": round(comp / r["elapsed"], 2) if comp else None,
            "content_head": (p.get("content") or "")[:120],
            "model_field": p.get("model_field"),
        })
    results["latency"] = lat

    # C: does an unknown-route fall back / does the bridge echo usage at all?
    r = post("/v1/chat/completions", {"model": "nonexistent-model-xyz",
                                      "messages": [{"role": "user", "content": "hi"}],
                                      "max_tokens": 32})
    results["unknown_model"] = {"ok": r["ok"], "status": r["status"], "body": r["body"][:400]}

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(json.dumps(results, ensure_ascii=False, indent=2)[:4000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
