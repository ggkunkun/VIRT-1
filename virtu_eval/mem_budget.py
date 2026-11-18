#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Memory budget for model legs on this box (6 GiB VRAM / 15.7 GiB RAM).

Three rules this module exists to enforce:

1. A footprint number is *derived* from the GGUF (layer bytes, KV heads, key/value
   length) or *measured* by ``scripts/mem_footprint_probe.py``. A source literal is
   never a measurement.
2. ``num_ctx`` is sized from the token demand of the actual case set, not from a
   magic 8192. Allocating 8x the KV cache a leg needs is pure waste.
3. Every reading fails closed. An unreadable counter, an unknown model, or an
   empty tag list must refuse the leg -- never silently read as "plenty of room".

The binding constraint on Windows is *commit charge*, not free physical RAM: an
idle llama-server can hold ~9 GiB of commit with a 60 MiB working set while
``/api/ps`` reports nothing loaded.
"""
import json
import math
import os
import re
import struct
import subprocess

GiB = 1024 ** 3
MiB = 1024 ** 2

# ggml quant block layout: (block_size, bytes_per_block). q8_0 = 32 elems / 34 B.
KV_BYTES_PER_ELEM = {"f16": 2.0, "q8_0": 34.0 / 32.0, "q4_0": 18.0 / 32.0}

# Overhead that is not weights or KV: CUDA context, compute graphs, scratch.
# Calibrate against a measured report before trusting a projection to the GB.
RUNTIME_OVERHEAD_GB = 0.9
COMPUTE_BUFFER_MIB = 160     # measured: sched_reserve CUDA0 compute buffer 159.75 MiB
# mmap is NOT assumed to save host commit. One measured dense leg (full offload)
# showed private bytes 5.41 -> 5.10 GB (~7%) while the working set rose 0.75 ->
# 4.39 GB; the MoE partial-offload case is unmeasured. A gate must not be loosened
# by an unverified saving, so the default keeps the weights counted.
MMAP_HOST_WEIGHT_FRACTION = 1.0
COMMIT_RESERVE_GB = 1.5      # headroom for the harness process itself
VRAM_RESERVE_MIB = 512       # WDDM/desktop needs room or the whole box stalls
RAM_FLOOR_GB = 1.0


class BudgetError(RuntimeError):
    """Raised when a leg must not start. Never swallowed into a pass."""


_PS_SAMPLE = r"""
$o = Get-CimInstance Win32_OperatingSystem
$p = Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory
$ls = Get-Process llama-server -ErrorAction SilentlyContinue
$ws = 0; $pr = 0
if ($ls) { $ws = ($ls | Measure-Object WorkingSet64 -Sum).Sum; $pr = ($ls | Measure-Object PrivateMemorySize64 -Sum).Sum }
"{0}|{1}|{2}|{3}|{4}" -f ($o.FreePhysicalMemory/1MB), ($p.CommitLimit/1GB), ($p.CommittedBytes/1GB), ($ws/1GB), ($pr/1GB)
"""

_GGUF_SIZE = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 8}
_GGUF_FMT = {0: "<B", 1: "<b", 2: "<H", 3: "<h", 4: "<I", 5: "<i", 6: "<f",
             7: "<B", 10: "<Q", 11: "<q", 12: "<d"}


def sample():
    """Authoritative live counters. Child PowerShell: in-process reads of
    GlobalMemoryStatusEx have been quota-polluted on this box."""
    r = subprocess.run(["powershell", "-NoProfile", "-Command", _PS_SAMPLE],
                       capture_output=True, text=True, timeout=120)
    lines = (r.stdout or "").strip().splitlines()
    if not lines or "|" not in lines[-1]:
        raise BudgetError("memory sampler unreadable: %r" % ((r.stderr or "")[:200],))
    try:
        ram_free, commit_limit, committed, ls_ws, ls_priv = (float(x) for x in lines[-1].split("|"))
    except ValueError as exc:
        raise BudgetError("memory sampler returned non-numeric fields: %s" % exc)
    g = subprocess.run(["nvidia-smi", "--query-gpu=memory.total,memory.used",
                        "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=90)
    try:
        total_mib, used_mib = (int(x) for x in (g.stdout or "").strip().splitlines()[0].split(","))
    except Exception:
        raise BudgetError("nvidia-smi unreadable: %r" % ((g.stdout or g.stderr)[:160],))
    if total_mib <= 0:
        raise BudgetError("nvidia-smi reported zero total VRAM - refusing to budget")
    return {
        "basis": "measured",
        "ram_free_gb": round(ram_free, 2),
        "commit_limit_gb": round(commit_limit, 2),
        "committed_gb": round(committed, 2),
        "commit_avail_gb": round(commit_limit - committed, 2),
        "llama_ws_gb": round(ls_ws, 2),
        "llama_priv_gb": round(ls_priv, 2),
        "gpu_total_mib": total_mib,
        "gpu_used_mib": used_mib,
        "gpu_free_mib": total_mib - used_mib,
    }


def gguf_facts(path):
    """Architecture + exact per-layer byte layout, read from the GGUF itself.

    Tensor sizes come from consecutive data offsets (the data section is packed in
    metadata order), so no quant-type table is needed and the numbers are exact.
    """
    if not os.path.exists(path):
        raise BudgetError("GGUF not found: %s" % path)
    md, tensors = {}, []
    with open(path, "rb") as fh:
        if fh.read(4) != b"GGUF":
            raise BudgetError("not a GGUF: %s" % path)
        struct.unpack("<I", fh.read(4))
        n_tensors, n_kv = struct.unpack("<QQ", fh.read(16))
        if not (0 < n_tensors < 100000 and 0 < n_kv < 100000):
            raise BudgetError("implausible GGUF counts %d/%d" % (n_tensors, n_kv))

        def rstr():
            n = struct.unpack("<Q", fh.read(8))[0]
            if n > 2_000_000:
                raise BudgetError("implausible GGUF string length %d" % n)
            return fh.read(n)

        for _ in range(n_kv):
            key = rstr().decode("utf-8", "replace")
            typ = struct.unpack("<I", fh.read(4))[0]
            if typ == 8:
                val = rstr()[:80].decode("utf-8", "replace")
            elif typ == 9:
                at = struct.unpack("<I", fh.read(4))[0]
                cnt = struct.unpack("<Q", fh.read(8))[0]
                if cnt > 10_000_000:
                    raise BudgetError("implausible GGUF array length %d" % cnt)
                if at == 8:
                    # Must consume EVERY element or the stream desynchronises.
                    for _ in range(cnt):
                        rstr()
                    val = "strarr(%d)" % cnt
                else:
                    fh.seek(_GGUF_SIZE[at] * cnt, 1)
                    val = "arr(%d)" % cnt
            else:
                val = struct.unpack(_GGUF_FMT[typ], fh.read(_GGUF_SIZE[typ]))[0]
            md[key] = val
        arch = md.get("general.architecture")
        if not arch:
            raise BudgetError("GGUF has no general.architecture")
        for _ in range(n_tensors):
            name = rstr().decode("utf-8", "replace")
            nd = struct.unpack("<I", fh.read(4))[0]
            for _ in range(nd):
                struct.unpack("<Q", fh.read(8))
            struct.unpack("<I", fh.read(4))
            off = struct.unpack("<Q", fh.read(8))[0]
            tensors.append((name, off))

    ordered = sorted(tensors, key=lambda t: t[1])
    per_layer, non_layer = {}, {}
    for i, (name, off) in enumerate(ordered):
        size = (ordered[i + 1][1] - off) if i + 1 < len(ordered) else 0
        m = re.match(r"^(?:[A-Za-z0-9_]+\.)?blk\.(\d+)\.", name)
        if m:
            idx = int(m.group(1))
            per_layer[idx] = per_layer.get(idx, 0) + size
        else:
            non_layer[name] = non_layer.get(name, 0) + size

    def num(suffix, default=None):
        v = md.get("%s.%s" % (arch, suffix))
        return v if isinstance(v, (int, float)) else default

    layers = num("block_count")
    kv_heads = num("attention.head_count_kv")
    key_len = num("attention.key_length")
    val_len = num("attention.value_length")
    if not all(isinstance(x, int) and x > 0 for x in (layers, kv_heads, key_len, val_len)):
        raise BudgetError("GGUF %s lacks attention geometry (layers=%r kv=%r k=%r v=%r)"
                          % (path, layers, kv_heads, key_len, val_len))
    if len(per_layer) != layers:
        raise BudgetError("GGUF layer count mismatch: header %d, tensors %d"
                          % (layers, len(per_layer)))
    # (key_len + val_len) already covers both K and V; no extra factor of 2.
    elems = layers * kv_heads * (key_len + val_len)
    return {
        "basis": "measured", "path": path, "arch": arch,
        "file_bytes": os.path.getsize(path),
        "block_count": layers, "head_count_kv": kv_heads,
        "key_length": key_len, "value_length": val_len,
        "context_length": num("context_length"),
        "expert_count": num("expert_count"), "expert_used_count": num("expert_used_count"),
        "per_layer_bytes": [per_layer[i] for i in range(layers)],
        "non_layer_bytes": non_layer,
        "kv_elems_per_token": elems,
    }


def kv_bytes(facts, num_ctx, kv_type="q8_0"):
    if kv_type not in KV_BYTES_PER_ELEM:
        raise BudgetError("unknown kv cache type %r" % kv_type)
    if not isinstance(num_ctx, int) or num_ctx <= 0:
        raise BudgetError("num_ctx must be a positive int, got %r" % (num_ctx,))
    return int(facts["kv_elems_per_token"] * num_ctx * KV_BYTES_PER_ELEM[kv_type])


def project(facts, num_ctx, num_gpu=None, kv_type="q8_0", mmap=False):
    """Where the bytes land. basis=inferred except the GGUF-derived weights.

    llama.cpp puts the LAST ``num_gpu`` blocks on the GPU and splits the KV cache
    per layer across the same boundary, so both terms are sliced from the end.
    Verified against a real over-fit: MoE num_gpu=30 asked for 6174 MiB model +
    246 MiB KV + 159 MiB compute = 6580 MiB against 5080 MiB free, and because the
    user pinned n_gpu_layers llama.cpp refused to auto-fit and crashed instead.
    """
    layers = facts["block_count"]
    per_layer = facts["per_layer_bytes"]
    n_gpu = layers if num_gpu is None else max(0, min(int(num_gpu), layers + 1))
    on_gpu = min(n_gpu, layers)
    gpu_layer_bytes = sum(per_layer[layers - on_gpu:]) if on_gpu else 0
    if n_gpu > layers:
        # Full offload also pulls the embedding/output tables onto the device.
        # Measured: dense ctx4096 gpu99 peaked at 4653 MiB vs 4193 MiB projected
        # without this term; token_embd is 334 MiB of that gap.
        gpu_layer_bytes += facts["non_layer_bytes"].get("output.weight", 0)
        gpu_layer_bytes += facts["non_layer_bytes"].get("token_embd.weight", 0)
    weights = facts["file_bytes"]
    kv = kv_bytes(facts, num_ctx, kv_type)
    kv_gpu = int(kv * on_gpu / layers)
    kv_host = kv - kv_gpu
    compute = int(COMPUTE_BUFFER_MIB * MiB)
    overhead = int(RUNTIME_OVERHEAD_GB * GiB)
    host_weights = int(weights * (MMAP_HOST_WEIGHT_FRACTION if mmap else 1.0))
    host_commit = host_weights + kv_host + overhead
    vram = gpu_layer_bytes + kv_gpu + compute
    return {
        "basis": "inferred",
        "weights_bytes": weights,
        "gpu_layer_bytes": gpu_layer_bytes,
        "kv_bytes": kv, "kv_gpu_bytes": kv_gpu, "kv_host_bytes": kv_host,
        "compute_bytes": compute,
        "num_gpu_effective": n_gpu,
        "vram_bytes": vram,
        "host_commit_bytes": host_commit,
        "host_commit_gb": round(host_commit / GiB, 2),
        "vram_gb": round(vram / GiB, 2),
        "vram_mib": round(vram / MiB),
        "kv_gb": round(kv / GiB, 3),
        "mmap": bool(mmap), "kv_type": kv_type, "num_ctx": num_ctx,
    }


def max_offload_layers(facts, num_ctx, env=None, kv_type="q8_0",
                       reserve_mib=VRAM_RESERVE_MIB):
    """Largest num_gpu that actually fits the *currently free* VRAM.

    Replaces hardcoded 22/30/99: those are only safe at one desktop load, and
    pinning them disables llama.cpp's auto-fit, turning an over-fit into a crash.
    """
    env = env if env is not None else sample()
    budget_mib = env["gpu_free_mib"] - reserve_mib
    if budget_mib <= 0:
        raise BudgetError("no VRAM headroom: free %d MiB, reserve %d MiB"
                          % (env["gpu_free_mib"], reserve_mib))
    layers = facts["block_count"]
    best = 0
    for n in range(layers + 1):
        if project(facts, num_ctx, n, kv_type)["vram_mib"] <= budget_mib:
            best = n
        else:
            break
    return best


def recommend_ctx(demand_tokens, facts=None, ceiling=8192, floor=512, margin=1.25,
                  granularity=512):
    """Smallest context that covers measured token demand, rounded to ``granularity``.

    Power-of-two rounding is too coarse here: it turns a 1200-token demand into a
    2048 window and doubles the KV cache for nothing. 512-token steps keep the
    allocation tight while staying aligned.

    ``demand_tokens`` must be prompt+completion, not prompt alone: the KV cache is
    allocated for the whole window the leg can reach.
    """
    if not isinstance(demand_tokens, (int, float)) or demand_tokens <= 0:
        raise BudgetError("token demand must be positive, got %r" % (demand_tokens,))
    if granularity <= 0:
        raise BudgetError("granularity must be positive")
    need = int(math.ceil(demand_tokens * margin))
    ctx = max(floor, int(math.ceil(need / granularity)) * granularity)
    if facts and facts.get("context_length"):
        ctx = min(ctx, int(facts["context_length"]))
    return min(ctx, ceiling)


def demand_from_records(paths):
    """p99 / max of prompt+completion tokens from existing eval records.

    Zero inference: reads ``gen`` blocks already written by a previous leg, so the
    context size can be justified from evidence instead of a guess.
    """
    totals = []
    seen = 0
    for p in paths:
        if not os.path.exists(p):
            raise BudgetError("record file missing: %s" % p)
        with open(p, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                seen += 1
                gen = rec.get("gen") or {}
                pt, ct = gen.get("prompt_tokens"), gen.get("completion_tokens")
                if isinstance(pt, int) and pt > 0:
                    totals.append(pt + (ct if isinstance(ct, int) else 0))
    if not totals:
        # An empty match set is not "the leg needs no context".
        raise BudgetError("no token demand found in %d records across %s" % (seen, paths))
    totals.sort()
    p99 = totals[min(len(totals) - 1, int(0.99 * len(totals)))]
    return {"basis": "measured", "n": len(totals), "records_seen": seen,
            "median": totals[len(totals) // 2], "p99": p99, "max": totals[-1]}


def check(projection, env=None, commit_reserve_gb=COMMIT_RESERVE_GB,
          vram_reserve_mib=VRAM_RESERVE_MIB, ram_floor_gb=RAM_FLOOR_GB):
    """Fail-closed verdict. Returns a dict; ``ok=False`` means do not start."""
    env = env if env is not None else sample()
    reasons = []
    need_commit = projection["host_commit_gb"] + commit_reserve_gb
    need_vram_mib = projection["vram_bytes"] / MiB + vram_reserve_mib
    if env["commit_avail_gb"] < need_commit:
        reasons.append("commit: need %.2f GB (proj %.2f + reserve %.2f), have %.2f GB"
                       % (need_commit, projection["host_commit_gb"], commit_reserve_gb,
                          env["commit_avail_gb"]))
    if env["gpu_free_mib"] < need_vram_mib:
        reasons.append("vram: need %.0f MiB (proj %.0f + reserve %d), have %d MiB"
                       % (need_vram_mib, projection["vram_bytes"] / MiB, vram_reserve_mib,
                          env["gpu_free_mib"]))
    if env["ram_free_gb"] < ram_floor_gb:
        reasons.append("ram: free %.2f GB below floor %.2f GB (thrash risk)"
                       % (env["ram_free_gb"], ram_floor_gb))
    return {"ok": not reasons, "reasons": reasons, "projection": projection, "env": env,
            "need_commit_gb": round(need_commit, 2), "need_vram_mib": round(need_vram_mib)}


def require(facts, num_ctx, num_gpu=None, kv_type="q8_0", mmap=False, env=None):
    """Gate a leg. Raises BudgetError rather than returning a falsy 'ok'."""
    verdict = check(project(facts, num_ctx, num_gpu, kv_type, mmap), env=env)
    if not verdict["ok"]:
        raise BudgetError("memory budget refused: " + "; ".join(verdict["reasons"]))
    return verdict


def models_dir():
    # A store must contain a manifest layout; an empty leftover directory named
    # by OLLAMA_MODELS (rolled-back migration target) must not shadow the real
    # store, or every tag reads as missing and gates silently degrade.
    home = os.path.join(os.path.expanduser("~"), ".ollama", "models")
    for d in (os.environ.get("OLLAMA_MODELS"), home):
        if d and (os.path.isdir(os.path.join(d, "manifests"))
                  or os.path.isdir(os.path.join(d, "manifests-v2"))):
            return d
    return home


def _manifest_for_tag(tag, root=None):
    """Locate a tag's manifest, checking BOTH layouts this box keeps.

    ``manifests-v2/ollama.com/library`` is current; the older
    ``manifests/registry.ollama.ai/library`` still exists. Reading only one reports
    the model as missing, and a gate that treats "missing" as "small" waves it through.
    """
    root = root or models_dir()
    name, _, t = tag.partition(":")
    t = t or "latest"
    candidates = [
        os.path.join(root, "manifests-v2", "ollama.com", "library", name, t),
        os.path.join(root, "manifests", "registry.ollama.ai", "library", name, t),
        os.path.join(root, "manifests-v2", "registry.ollama.ai", "library", name, t),
    ]
    for path in candidates:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                return path, json.load(fh), root
    raise BudgetError("tag %r not found under %s (checked %d manifest layouts)"
                      % (tag, root, len(candidates)))


def _layer_blob(man, root, suffix):
    for layer in man.get("layers", []):
        if layer.get("mediaType", "").endswith(suffix):
            blob = os.path.join(root, "blobs", "sha256-" + layer["digest"].split(":")[-1])
            if not os.path.exists(blob):
                raise BudgetError("manifest points at missing blob %s" % blob)
            return blob
    return None


def blob_for_tag(tag, root=None):
    """Resolve an Ollama tag to its GGUF blob."""
    path, man, root = _manifest_for_tag(tag, root)
    blob = _layer_blob(man, root, "image.model")
    if blob is None:
        raise BudgetError("manifest %s has no model layer" % path)
    return blob


def params_for_tag(tag, root=None):
    """The tag's baked PARAMETER layer (num_ctx / num_gpu / sampling) as a dict.

    An arm that does not pin num_gpu inherits THIS value, not "full offload" --
    confusing the two over-estimates VRAM and refuses legs that actually fit.
    """
    path, man, root = _manifest_for_tag(tag, root)
    blob = _layer_blob(man, root, "image.params")
    if blob is None:
        return {}
    with open(blob, encoding="utf-8", errors="replace") as fh:
        text = fh.read().strip()
    if not text:
        return {}
    try:
        doc = json.loads(text)
    except ValueError as exc:
        raise BudgetError("params layer for %s is not JSON: %s" % (tag, exc))
    if not isinstance(doc, dict):
        raise BudgetError("params layer for %s is not an object" % tag)
    return doc


def facts_for_tag(tag, root=None):
    return gguf_facts(blob_for_tag(tag, root))


def require_headroom(env=None, commit_reserve_gb=COMMIT_RESERVE_GB,
                     vram_reserve_mib=VRAM_RESERVE_MIB, ram_floor_gb=RAM_FLOOR_GB):
    """Tier-1 gate that needs no GGUF: is there room for *anything* at all?

    The client's OLLAMA_MODELS may differ from the server's (the 0-tag trap), so a
    projection is not always possible. This tier still fails closed on unreadable
    counters and on a box that is already out of commit or VRAM.
    """
    env = env if env is not None else sample()
    reasons = []
    if env["commit_avail_gb"] < commit_reserve_gb:
        reasons.append("commit headroom %.2f GB < reserve %.2f GB"
                       % (env["commit_avail_gb"], commit_reserve_gb))
    if env["gpu_free_mib"] < vram_reserve_mib:
        reasons.append("VRAM headroom %d MiB < reserve %d MiB"
                       % (env["gpu_free_mib"], vram_reserve_mib))
    if env["ram_free_gb"] < ram_floor_gb:
        reasons.append("free RAM %.2f GB < floor %.2f GB" % (env["ram_free_gb"], ram_floor_gb))
    if reasons:
        raise BudgetError("no headroom to start a model leg: " + "; ".join(reasons))
    return env


def hf_weight_bytes(path):
    """On-disk weight bytes of a HF model dir (shards included)."""
    if not os.path.isdir(path):
        raise BudgetError("model dir not found: %s" % path)
    total, found = 0, 0
    for name in os.listdir(path):
        if name.endswith((".safetensors", ".bin", ".pt", ".pth")):
            fp = os.path.join(path, name)
            if os.path.isfile(fp):
                total += os.path.getsize(fp)
                found += 1
    if not found:
        raise BudgetError("no weight shards found in %s" % path)
    return total


def require_hf_fit(path, device="cuda", env=None, reserve_gb=COMMIT_RESERVE_GB):
    """Refuse an in-process HF load that cannot fit, before it thrashes the box.

    ``torch_dtype="auto"`` keeps the on-disk precision, so an 8B bf16 dir is ~16 GB
    of commit -- more than this machine's physical RAM. With device_map=cuda the
    same bytes also have to fit in VRAM. Quantise (nf4) or serve via Ollama instead.
    """
    env = env if env is not None else sample()
    weight_gb = hf_weight_bytes(path) / GiB
    need = weight_gb + reserve_gb
    reasons = []
    if env["commit_avail_gb"] < need:
        reasons.append("commit: weights %.2f GB + reserve %.2f GB > available %.2f GB"
                       % (weight_gb, reserve_gb, env["commit_avail_gb"]))
    if str(device).startswith("cuda") and env["gpu_free_mib"] / 1024 < need:
        reasons.append("vram: weights %.2f GB + reserve %.2f GB > free %.2f GiB"
                       % (weight_gb, reserve_gb, env["gpu_free_mib"] / 1024))
    if reasons:
        raise BudgetError("unquantized HF load of %s does not fit (%s); "
                          "use 4-bit quantisation or the Ollama serving path"
                          % (path, "; ".join(reasons)))
    return {"weight_gb": round(weight_gb, 2), "env": env}


def orphan_runners():
    """llama-server processes whose parent ollama server is gone.

    Measured failure mode: when the server crashes (e.g. a pinned num_gpu over-fit)
    the runner child survives holding ~5.9 GiB VRAM and ~9 GiB commit, and no
    /api/ps can report it because the API is dead. Report only -- killing is the
    caller's decision and must be parentage-proven, never title-matched.
    """
    ps = r"""
Get-CimInstance Win32_Process -Filter "Name='llama-server.exe'" | ForEach-Object {
  $alive = [bool](Get-Process -Id $_.ParentProcessId -ErrorAction SilentlyContinue)
  "{0}|{1}|{2}|{3}" -f $_.ProcessId, $_.ParentProcessId, $alive, [math]::Round($_.WorkingSetSize/1GB,2)
}
"""
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True, text=True, timeout=120)
    out = []
    for line in (r.stdout or "").strip().splitlines():
        parts = line.split("|")
        if len(parts) != 4:
            continue
        pid, parent, alive, ws = parts
        if alive.strip().lower() == "false":
            out.append({"pid": int(pid), "parent_pid": int(parent),
                        "parent_alive": False, "ws_gb": float(ws)})
    return out
