"""Arm sanity probe: is each deployed model still coherent?

Before any capability score is meaningful we must separate two very different
failure modes:

  A. the model answers, but answers badly   -> capability problem
  B. the model answers with damaged text    -> artifact / merge corruption

Both look like "low score" in a grader. Only (B) is a model-integrity incident.

The probe runs a fixed set of prompts per arm, records raw output plus latency
and token throughput, and writes one JSON file per arm so every claim in the
report can be re-checked against the stored response.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

OLLAMA = os.environ.get("VIRTU_OLLAMA_URL", "http://127.0.0.1:11434")
# The host sets HTTP_PROXY; 127.0.0.1 must not go through it.
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

TOOLS_SCHEMA = [{
    "type": "function",
    "function": {
        "name": "cadcam_solidworks_model",
        "description": "SOLIDWORKS 2021 parametric model build via COM/VBA.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string",
                           "enum": ["model_flange", "create_parametric_part",
                                    "execute_vba", "connect"]},
                "part_name": {"type": "string"},
                "dimensions": {"type": "object"},
            },
            "required": ["action"],
        },
    },
}]

PROBES = [
    {"key": "p1_chinese_fact", "zh": True,
     "prompt": "用一句话解释数控车床中主轴转速 n 与切削速度 Vc 的关系。"},
    {"key": "p2_cad_term", "zh": True,
     "prompt": "G71 在数控车床里是什么？它的作用是什么？"},
    {"key": "p3_format", "zh": False,
     "prompt": "Output ONLY a JSON object with keys \"name\" and \"value\", "
               "where value is 42. No other text."},
    {"key": "p4_toolcall", "zh": True,
     "prompt": "我要做一个轮模：外径53mm、轴孔14mm、长度45mm，材质 Cr12MoV。"
               "请选择合适的工具并给出参数。"},
]


def chat(model, messages, num_predict=400, temperature=0.0, seed=1234, tools=None):
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        # Qwen3-family templates emit a reasoning block by default and put the
        # *answer* inside it, leaving message.content empty.  Scoring an empty
        # content field would silently score a working model as 0.
        "think": False,
        "options": {"temperature": temperature, "seed": seed,
                    "num_predict": num_predict, "num_ctx": 4096},
    }
    if tools:
        payload["tools"] = tools
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(OLLAMA + "/api/chat", data=body,
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    t0 = time.perf_counter()
    with _OPENER.open(req, timeout=900) as resp:
        data = json.loads(resp.read().decode("utf-8", "replace"))
    msg = data.get("message") or {}
    content = msg.get("content") or ""
    thinking = msg.get("thinking") or ""
    if not content and thinking:
        # fall back so a non-empty generation is never silently discarded
        content = thinking
        fell_back = True
    else:
        fell_back = False
    return {
        "elapsed_s": round(time.perf_counter() - t0, 2),
        "eval_count": data.get("eval_count"),
        "prompt_eval_count": data.get("prompt_eval_count"),
        "done_reason": data.get("done_reason"),
        "content": content,
        "thinking": msg.get("thinking"),
        "content_was_empty": not bool(msg.get("content")),
        "fell_back_to_thinking": fell_back,
        "tool_calls": msg.get("tool_calls"),
    }


def coherence_flags(text):
    """Cheap, deterministic red flags for damaged generation."""
    if not text:
        return ["empty"]
    flags = []
    n = len(text)
    if n < 5:
        flags.append("too_short")
    # a token repeated >=6 times in a row anywhere
    import re
    if re.search(r"([A-Za-z]{2,10})\1{5,}", text):
        flags.append("token_repetition")
    # same 12-char shingle appearing >=4 times -> loop
    shingles = [text[i:i + 12] for i in range(0, max(n - 12, 0), 6)]
    if shingles:
        from collections import Counter
        top = Counter(shingles).most_common(1)[0][1]
        if top >= 4:
            flags.append("loop")
    # non-CJK garbage ratio: many lone latin words mixed into zh text
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    latin_words = re.findall(r"\b[A-Za-z]{2,}\b", text)
    if cjk >= 10 and len(latin_words) > cjk * 0.35:
        flags.append("zh_en_code_mix")
    # known corruption pattern seen in this project: doubled period mid-word
    if re.search(r"\w\.\w", text):
        flags.append("split_token")
    return flags


def run(model, out_dir, warmup=True):
    os.makedirs(out_dir, exist_ok=True)
    rec = {"model": model, "ollama": OLLAMA, "probes": []}

    if warmup:
        t0 = time.perf_counter()
        try:
            w = chat(model, [{"role": "user", "content": "hi"}], num_predict=8)
            rec["warmup_s"] = round(time.perf_counter() - t0, 2)
            rec["warmup_ok"] = True
        except Exception as exc:  # noqa: BLE001
            rec["warmup_ok"] = False
            rec["warmup_error"] = f"{type(exc).__name__}: {exc}"

    for p in PROBES:
        messages = [{"role": "user", "content": p["prompt"]}]
        tools = TOOLS_SCHEMA if p["key"] == "p4_toolcall" else None
        try:
            r = chat(model, messages, tools=tools)
        except Exception as exc:  # noqa: BLE001
            rec["probes"].append({"key": p["key"], "error": f"{type(exc).__name__}: {exc}"})
            continue
        r["key"] = p["key"]
        r["prompt"] = p["prompt"]
        r["flags"] = coherence_flags(r.get("content"))
        r["has_tool_calls"] = bool(r.get("tool_calls"))
        rec["probes"].append(r)

    path = os.path.join(out_dir, f"{model.replace(':', '__').replace('/', '_')}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=2)
    return path, rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--out-dir", default="runs/eval/sanity")
    ap.add_argument("--no-warmup", action="store_true")
    a = ap.parse_args()
    for m in a.models:
        try:
            path, rec = run(m, a.out_dir, warmup=not a.no_warmup)
        except Exception as exc:  # noqa: BLE001
            print(f"[skip] {m}: {type(exc).__name__}: {exc}", flush=True)
            continue
        # stdout on this box is a GBK console and the model's raw output can
        # contain characters it cannot encode -> the process dies on print.
        # Everything non-ASCII goes to the JSON file, stdout stays ASCII.
        print(f"\n===== {m}  ->  {path}", flush=True)
        if "warmup_s" in rec:
            print(f"  warmup {rec['warmup_s']}s", flush=True)
        for p in rec["probes"]:
            if p.get("error"):
                print(f"  {p['key']}: ERROR {p['error'][:120]}", flush=True)
                continue
            print(f"  {p['key']}: {p['elapsed_s']}s  eval={p['eval_count']} "
                  f"tok/s={round((p['eval_count'] or 0) / max(p['elapsed_s'], .01), 2)} "
                  f"flags={p['flags']} tool_calls={p['has_tool_calls']}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
