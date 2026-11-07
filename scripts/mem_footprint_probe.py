#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Measure the real VRAM / host-RAM / commit-charge cost of a serving config.

Every number this script prints is sampled from the OS and the GPU, not from a
source literal, so a footprint claim can be attributed to one knob (num_ctx,
num_gpu, use_mmap, quant, keep_alive).

Authoritative counters come from a child PowerShell because in-process reads of
GlobalMemoryStatusEx have been observed to be quota-polluted on this box.

    python -X utf8 scripts/mem_footprint_probe.py --preset sweep
    python -X utf8 scripts/mem_footprint_probe.py --model virtu-dense-merged:q4_0 \
        --num-ctx 4096 --num-gpu 99 --repeats 3
"""
import argparse
import json
import os
import statistics
import subprocess
import sys
import time
import urllib.request

BASE = os.environ.get("VIRTU_OLLAMA_BASE", "http://127.0.0.1:11434")
OUT_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "runs")

PS_SAMPLE = r"""
$o = Get-CimInstance Win32_OperatingSystem
$p = Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory
$ls = Get-Process llama-server -ErrorAction SilentlyContinue
$ws = 0; $pr = 0
if ($ls) { $ws = ($ls | Measure-Object WorkingSet64 -Sum).Sum; $pr = ($ls | Measure-Object PrivateMemorySize64 -Sum).Sum }
"{0}|{1}|{2}|{3}|{4}" -f ($o.FreePhysicalMemory/1MB), ($p.CommitLimit/1GB), ($p.CommittedBytes/1GB), ($ws/1GB), ($pr/1GB)
"""


def _fail(msg):
    print("PROBE_FAIL %s" % msg, flush=True)
    raise SystemExit(2)


def env_sample():
    """(ram_free_gb, commit_limit_gb, committed_gb, ls_ws_gb, ls_priv_gb, gpu_used_mib)."""
    r = subprocess.run(["powershell", "-NoProfile", "-Command", PS_SAMPLE],
                       capture_output=True, text=True, timeout=90)
    line = (r.stdout or "").strip().splitlines()
    if not line or "|" not in line[-1]:
        _fail("powershell sampler returned no data: %r" % (r.stderr or "")[:200])
    a, b, c, d, e = (float(x) for x in line[-1].split("|"))
    g = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                       capture_output=True, text=True, timeout=60)
    try:
        gpu = int((g.stdout or "").strip().splitlines()[0])
    except Exception:
        _fail("nvidia-smi unreadable: %r" % (g.stdout or g.stderr)[:120])
    return {"ram_free_gb": round(a, 2), "commit_limit_gb": round(b, 2),
            "committed_gb": round(c, 2), "commit_avail_gb": round(b - c, 2),
            "llama_ws_gb": round(d, 2), "llama_priv_gb": round(e, 2),
            "gpu_used_mib": gpu}


def api(path, payload, timeout=600, method="POST"):
    data = json.dumps(payload).encode("utf-8") if method == "POST" else None
    req = urllib.request.Request(BASE + path, data=data,
                                 headers={"Content-Type": "application/json"},
                                 method=method)
    with urllib.request.urlopen(req, timeout=timeout) as fh:
        return json.loads(fh.read().decode("utf-8", "replace"))


def loaded(strict=False):
    try:
        return api("/api/ps", {}, 20, method="GET").get("models", [])
    except Exception:
        if strict:
            raise
        return []


def server_identity():
    """Port + version + store path, so a footprint number can be attributed to a server."""
    ver = None
    try:
        ver = api("/api/version", {}, 20, method="GET").get("version")
    except Exception:
        pass
    names = []
    try:
        names = [m["name"] for m in api("/api/tags", {}, 30, method="GET").get("models", [])]
    except Exception as exc:
        _fail("cannot read /api/tags from %s: %s" % (BASE, exc))
    if not names:
        # A serve started without OLLAMA_MODELS reports 0 tags and every leg would
        # silently 404; that is a broken server identity, not a model result.
        _fail("server at %s reports 0 tags (OLLAMA_MODELS not inherited?)" % BASE)
    return {"base_url": BASE, "version": ver, "tag_count": len(names),
            "models_dir": os.environ.get("OLLAMA_MODELS", "(server env, not visible here)")}


def assert_model_present(model, identity):
    names = set()
    try:
        names = {m["name"] for m in api("/api/tags", {}, 30, method="GET").get("models", [])}
    except Exception as exc:
        _fail("tag re-read failed: %s" % exc)
    if model not in names:
        _fail("model %r absent from %s (%d tags) - refusing to measure"
              % (model, identity.get("base_url"), len(names)))


def unload_all(wait_s=40):
    # strict: an unreachable server must not be mistaken for "everything unloaded".
    for m in loaded(strict=True):
        try:
            api("/api/generate", {"model": m.get("name", ""), "keep_alive": "0s"}, 60)
        except Exception:
            pass
    t0 = time.time()
    while time.time() - t0 < wait_s:
        if not loaded(strict=True):
            return True
        time.sleep(2)
    return not loaded(strict=True)


def peak_sampler(stop_ev, interval=1.0):
    """Poll the counters while a leg runs; return the worst (max) of each field."""
    samples = []
    while stop_ev[0] is False:
        samples.append(env_sample())
        time.sleep(interval)
    return samples


def measure(model, num_ctx, num_gpu=None, use_mmap=None, repeats=1, n_predict=48):
    """Load + generate once per repeat; report footprint peak and decode speed."""
    opts = {"temperature": 0, "num_ctx": num_ctx, "num_predict": n_predict,
            "seed": 42, "keep_alive": "60s"}
    if num_gpu is not None:
        opts["num_gpu"] = num_gpu
    if use_mmap is not None:
        opts["use_mmap"] = use_mmap
    rows, toks, loads = [], [], []
    prompt = ("You are a CNC engineer. List the three G-code modal groups that must be "
              "set before the first cutting move, then explain each in one short sentence. "
              "Answer in Chinese with the English keywords kept.\n" * 6)[:1800]
    for _ in range(repeats):
        unload_all()
        idle = env_sample()
        t0 = time.time()
        try:
            res = api("/api/generate", {"model": model, "prompt": prompt, "options": opts,
                                        "stream": False, "keep_alive": "60s"}, 900)
        except Exception as exc:
            # A leg that cannot even load is a result, not a reason to abandon the sweep.
            rows.append({"idle": idle, "error": str(exc)[:300], "load_s": round(time.time() - t0, 1)})
            print("  LEG_ERROR ctx=%s gpu=%s mmap=%s: %s" % (num_ctx, num_gpu, use_mmap,
                                                            str(exc)[:160]), flush=True)
            continue
        load_s = round(time.time() - t0, 1)
        live = env_sample()
        ec = res.get("eval_count") or 0
        ed = res.get("eval_duration") or 0
        pc = res.get("prompt_eval_count") or 0
        loads.append(load_s)
        toks.append(round(ec / (ed / 1e9), 2) if ed and ec else None)
        rows.append({"idle": idle, "live": live, "prompt_tokens": pc, "eval_tokens": ec,
                     "load_s": load_s, "tok_s": toks[-1],
                     "load_dur_s": round((res.get("load_duration") or 0) / 1e9, 1)})
    unload_all()
    after = env_sample()

    def worst(key):
        vals = [r["live"][key] for r in rows if "live" in r]
        return max(vals) if vals else None

    def best(key):
        vals = [r["idle"][key] for r in rows if "idle" in r]
        return min(vals) if vals else None
    measured_toks = [t for t in toks if t]
    errors = [r.get("error") for r in rows if r.get("error")]
    return {
        "model": model, "num_ctx": num_ctx, "num_gpu": num_gpu, "use_mmap": use_mmap,
        "basis": "measured", "n": len(rows), "n_failed": len(errors), "errors": errors,
        "gpu_used_mib_peak": worst("gpu_used_mib"),
        "llama_priv_gb_peak": worst("llama_priv_gb"),
        "llama_ws_gb_peak": worst("llama_ws_gb"),
        "ram_free_gb_min": best("ram_free_gb"),
        "commit_avail_gb_min": best("commit_avail_gb"),
        "load_s_median": statistics.median(loads) if loads else None,
        "tok_s_median": round(statistics.median(measured_toks), 2) if measured_toks else None,
        "tok_s_spread": [min(measured_toks), max(measured_toks)] if len(measured_toks) > 1 else None,
        "after_unload": {"gpu_used_mib": after["gpu_used_mib"],
                         "commit_avail_gb": after["commit_avail_gb"]},
        "per_repeat": rows,
    }


PRESETS = [
    # Small/cheap legs first: a big leg that exhausts commit must not mask the rest.
    ("dense q4_0 ctx4096 gpu99", "virtu-dense-merged:q4_0", 4096, 99, None),
    ("dense q4_0 ctx2048 gpu99", "virtu-dense-merged:q4_0", 2048, 99, None),
    ("dense q4_0 ctx4096 mmap", "virtu-dense-merged:q4_0", 4096, 99, True),
    ("moe ctx4096 gpu30 mmap", "virtu-moe-14b:latest", 4096, 30, True),
    ("moe ctx4096 gpu30", "virtu-moe-14b:latest", 4096, 30, None),
    ("moe ctx1024 gpu30 mmap", "virtu-moe-14b:latest", 1024, 30, True),
    ("moe current serving cfg", "virtu-moe-14b:latest", 8192, None, None),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", choices=["sweep"])
    ap.add_argument("--model")
    ap.add_argument("--num-ctx", type=int, default=4096)
    ap.add_argument("--num-gpu", type=int)
    ap.add_argument("--use-mmap", action="store_true")
    ap.add_argument("--repeats", type=int, default=2)
    ap.add_argument("--tag", default="ad_hoc")
    args = ap.parse_args()

    run_dir = os.path.join(OUT_ROOT, "mem_footprint_%s" % time.strftime("%Y%m%d_%H%M%S"))
    os.makedirs(run_dir, exist_ok=True)
    identity = server_identity()
    out = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S%z"), "basis": "measured",
           "server": identity, "idle_before": env_sample(), "legs": []}
    path = os.path.join(run_dir, "report.json")

    cases = ([(p[1], p[2], p[3], p[4], p[0]) for p in PRESETS] if args.preset == "sweep"
             else [(args.model, args.num_ctx, args.num_gpu,
                    True if args.use_mmap else None, args.tag)])
    for (model, ctx, gpu, mmap, label) in cases:
        assert_model_present(model, identity)
        leg = {"label": label}
        leg.update(measure(model, ctx, gpu, mmap, repeats=args.repeats))
        out["legs"].append(leg)
        print("[%s] ctx=%s gpu=%s mmap=%s | GPU peak %s MiB | priv %s GB | commit_avail_min %s GB "
              "| ws %s GB | tok/s %s +-%s | load %s s"
              % (label, ctx, gpu, mmap, leg["gpu_used_mib_peak"], leg["llama_priv_gb_peak"],
                 leg["commit_avail_gb_min"], leg["llama_ws_gb_peak"], leg["tok_s_median"],
                 leg["tok_s_spread"], leg["load_s_median"]), flush=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=1)
    print("report -> %s" % path, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
