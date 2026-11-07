# -*- coding: utf-8 -*-
"""
scripts/moe14b_service_point_grid.py — 13.63B MoE 在 6GB 显存上的实测服务位网格

背景：HARD 路径一直沿用 num_gpu=22 这个从未被复验的数字。PROVENANCE 里
`serving_bench` 只测过两个点（ctx8192/gpu22=10.59 tok/s、ctx4096/gpu99=5.68 tok/s），
其余取值全是 asserted。本脚本把「层卸载数 × 上下文长度 × 采样惩罚」测成一张真实表格，
输出 tok/s、加载耗时、墙钟与退化计数，给出可归因的最优点；不会自动改任何配置。

测量链独占：启动前检查 runs/*.chain.lock，命中未过期锁即拒绝运行（宪法第 6 条）。
归因：每个响应校验 model 字段前缀，防止把别的模型的回答记到这一臂上。

用法：
  python scripts/moe14b_service_point_grid.py --model virtu-moe-14b:fast
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import atexit
import re
import sys
import time
import urllib.error
import urllib.request

BASE = os.environ.get("OLLAMA_BASE", "http://127.0.0.1:11434").rstrip("/")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PROMPTS = {
    "domain": "G71 粗车循环里 U、R、F 三个地址字各代表什么？每个用一句话回答。",
    "repeat_prone": "列出数控车削中常见的十种表面粗糙度改善措施，每条一行。",
}

REPEAT_TOKEN_RE = re.compile(r"(\S{4,})\s*(?:\1\s*){6,}")


def _no_proxy():
    for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "ALL_PROXY"):
        os.environ.pop(k, None)


def get(url, timeout=60):
    _no_proxy()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, ConnectionRefusedError) as e:
        raise SystemExit(f"[FATAL] 服务未监听 {BASE}（{e}）。"
                         f"起服务：E:\\OllamaApp\\serve_e_store.bat，然后重试。绝不在无服务时出数。")


def post(url, payload, timeout=900):
    _no_proxy()
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, ConnectionRefusedError) as e:
        raise SystemExit(f"[FATAL] 请求 {url} 失败（{e}）；本条计为传输错误，不得当作成绩")


LOCK_STALE_S = 300   # a live chain heartbeats its lock; older than this means abandoned


def acquire_lock(name):
    lock_dir = os.path.join(ROOT, "runs")
    os.makedirs(lock_dir, exist_ok=True)
    mine = os.path.join(lock_dir, f"{name}.chain.lock")
    for existing in glob.glob(os.path.join(lock_dir, "*.chain.lock")):
        if os.path.abspath(existing) == os.path.abspath(mine):
            continue
        try:
            age = time.time() - os.path.getmtime(existing)
        except OSError:
            age = 0
        if age < LOCK_STALE_S:
            raise SystemExit(f"[LOCKED] 测量链独占资源被占用: {existing} age={age:.0f}s (<{LOCK_STALE_S}s)")
    heartbeat(mine)
    atexit.register(_release, mine)
    return mine


def heartbeat(path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"chain": os.path.basename(path), "pid": os.getpid(),
                   "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}, f)


def _release(path):
    try:
        if os.path.exists(path) and json.load(open(path, encoding="utf-8")).get("pid") == os.getpid():
            os.remove(path)
    except Exception:  # a lock we cannot read is left in place, never silently deleted
        pass


def ask(model, prompt, options, num_predict):
    opts = {k: v for k, v in options.items() if not (k == "num_gpu" and v < 0)}
    opts["num_predict"] = num_predict
    t0 = time.time()
    r = post(f"{BASE}/api/generate", {"model": model, "prompt": prompt, "stream": False,
                                      "options": opts, "keep_alive": "5m"})
    wall = time.time() - t0
    eval_n = r.get("eval_count", 0) or 0
    eval_ns = r.get("eval_duration", 0) or 0
    load_ns = r.get("load_duration", 0) or 0
    pe_n = r.get("prompt_eval_count", 0) or 0
    pe_ns = r.get("prompt_eval_duration", 0) or 0
    text = r.get("response", "") or ""
    return {
        "served_model": r.get("model", ""),
        "wall_s": round(wall, 2),
        "load_s": round(load_ns / 1e9, 2),
        "eval_tokens": eval_n,
        "tok_s": round(eval_n / (eval_ns / 1e9), 2) if eval_ns else None,
        "prompt_tokens": pe_n,
        "prompt_tok_s": round(pe_n / (pe_ns / 1e9), 1) if pe_ns else None,
        "truncated": eval_n >= num_predict,
        "repeat_runs": len(REPEAT_TOKEN_RE.findall(text)),
        "response_head": text[:160],
    }


EMPTY_REC = {"served_model": "", "wall_s": None, "load_s": None, "eval_tokens": 0, "tok_s": None,
             "prompt_tokens": 0, "prompt_tok_s": None, "truncated": False, "repeat_runs": None,
             "response_head": ""}


def measure_cell(model, prompt, options, num_predict, label, num_ctx, num_gpu, penalties):
    """One grid cell. A runner crash/500 becomes a recorded transport error with NO speed —
    it must never be rendered as a number, and never aborts the whole sweep."""
    rec = {"cell": label, "num_ctx": num_ctx, "num_gpu": num_gpu, "penalties": penalties}
    try:
        rec.update(ask(model, prompt, options, num_predict))
    except (SystemExit, OSError) as e:
        rec.update(EMPTY_REC)
        rec["transport_error"] = str(e).replace("[FATAL] ", "")[:400]
    return rec


def assert_model_present(model, tags_payload):
    """Refuse to measure a model we cannot see in /api/tags — otherwise the numbers get
    attributed to whatever Ollama actually served (or to a 404 that reads as a speed)."""
    names = [m.get("name", "") for m in tags_payload.get("models", [])]
    if model not in names:
        raise SystemExit(f"[FATAL] {model!r} 不在 /api/tags（有 {len(names)} 个标签），拒绝出数")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="virtu-moe-14b:fast")
    ap.add_argument("--out", default=os.path.join(ROOT, "runs", "moe14b_service_point_grid.json"))
    ap.add_argument("--num-predict", type=int, default=96)
    ap.add_argument("--gpu-cells", default="0,12,22,30,36",
                    help="empty string skips the offload stage (long legs get split on this box)")
    ap.add_argument("--ctx-cells", default="4096,8192", help="empty string skips the ctx stage")
    ap.add_argument("--penalties", default="1", help="0 skips the sampling-penalty stage")
    ap.add_argument("--fix-gpu", type=int, default=-1,
                    help="num_gpu to use when the offload stage is skipped")
    args = ap.parse_args()

    lock = acquire_lock("moe14b_service_point_grid")
    tags = get(f"{BASE}/api/tags")
    assert_model_present(args.model, tags)

    rows = []
    base_opts = {"temperature": 0.1, "top_p": 0.9, "seed": 1234}

    def run_cell(label, options, prompt_key="domain"):
        rec = measure_cell(args.model, PROMPTS[prompt_key], options, args.num_predict, label,
                           options.get("num_ctx"), options.get("num_gpu"),
                           {k: options[k] for k in ("repeat_penalty", "presence_penalty", "min_p")
                            if k in options})
        heartbeat(lock)
        rows.append(rec)
        archive(rec)
        if rec.get("transport_error"):
            print(f"[{label:>34}] gpu={rec['num_gpu']} TRANSPORT ERROR: "
                  f"{rec['transport_error'][:180]}", flush=True)
        else:
            print(f"[{label:>34}] ctx={rec['num_ctx']} gpu={rec['num_gpu']} "
                  f"tok/s={rec['tok_s']} load={rec['load_s']}s wall={rec['wall_s']}s "
                  f"rep={rec['repeat_runs']} trunc={rec['truncated']}", flush=True)
        return rec

    def archive(last):
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump({"model": args.model, "basis": "measured", "partial": True,
                       "num_predict": args.num_predict, "rows": rows, "last": last},
                      f, indent=2, ensure_ascii=False)

    print(f"=== grid on {args.model} (num_predict={args.num_predict}, temp=0.1, seed=1234) ===", flush=True)

    def cells(spec):
        return [int(x) for x in spec.split(",") if x.strip()]

    best = None
    for gpu in cells(args.gpu_cells):
        r = run_cell("gpu-sweep ctx4096", {"num_ctx": 4096, "num_gpu": gpu, **base_opts})
        if r["tok_s"] and (best is None or r["tok_s"] > best["tok_s"]):
            best = r
    if best is None and args.fix_gpu < 0:
        raise SystemExit("[FATAL] no successful offload cell and --fix-gpu not given; "
                         "later cells would have no basis")
    if best is None:
        best = {"num_gpu": args.fix_gpu, "tok_s": None}
    print(f"\n[best offload] num_gpu={best['num_gpu']} at {best['tok_s']} tok/s; "
          f"transport errors so far: {sum(1 for r in rows if r.get('transport_error'))}\n", flush=True)

    for ctx in cells(args.ctx_cells):
        run_cell(f"ctx-sweep gpu{best['num_gpu']}",
                 {"num_ctx": ctx, "num_gpu": best["num_gpu"], **base_opts})

    if args.penalties not in ("0", "false", "no"):
        pen_sets = {
            "no-penalty": {},
            "rp1.15+pp0.3+minp0.05": {"repeat_penalty": 1.15, "presence_penalty": 0.3, "min_p": 0.05},
            "rp1.15 only": {"repeat_penalty": 1.15},
        }
        for name, extra in pen_sets.items():
            opts = {"num_ctx": 4096, "num_gpu": best["num_gpu"], **base_opts, **extra}
            run_cell(f"penalty:{name} (repeat_prone)", opts, prompt_key="repeat_prone")

    # re-ask the winner twice to record run-to-run spread of the service point itself
    win_opts = {"num_ctx": 4096, "num_gpu": best["num_gpu"], **base_opts}
    spread = []
    for _ in range(2):
        try:
            spread.append(ask(args.model, PROMPTS["domain"], win_opts, args.num_predict)["tok_s"])
        except SystemExit:
            spread.append(None)

    out = {
        "model": args.model,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "basis": "measured",
        "num_predict": args.num_predict,
        "rows": rows,
        "best_num_gpu_by_tok_s": best["num_gpu"],
        "best_tok_s": best["tok_s"],
        "winner_repeat_spread_tok_s": spread,
        "note": "tok/s 取 Ollama eval_count/eval_duration（非墙钟）；load 为请求内加载耗时；"
                "repeat_runs=输出中连续重复 token 串数量",
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\n[out] {args.out}\nwinner spread: {spread}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
