#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/run_domain_ab.py — 同尺域内 A/B（精确槽位判分，可复算）。

P0-B 口径变更：
- 旧版用子串匹配（``norm(alt) in t``），``flange -> flange_X`` 仍给满分
  （README §26/§28 已自述证伪）。现改精确 token/槽位匹配：候选词必须作为完整
  token 槽位命中；``grader_version`` 随之变更，与历史 substring 分不可混用。
- ``gen()`` 补 ``seed`` / ``num_ctx`` 并写入 options 与汇总；raw.jsonl 每行补
  ``served_layers``（离线解析 Ollama manifest 层摘要，参考
  ``virtu_eval/arms.py::OllamaNativeArm._read_layers``）。
- summary.json 强制写 ``run_id``（16 位 hex 内容指纹）、``n``、``basis``、
  ``raw_sha256``、``cases_sha256``、``grader_sha256``、``grader_version``，
  并调 ``provenance.seal_leg()`` 封缄证据。
- HTTP/传输错误记 ``verdict=transport_error``（score=None），绝不记 0 分当实测；
  汇总里排除并按 ``basis=partial`` 判红，不静默降级为 success。

用法：
  python scripts/run_domain_ab.py \
      --models virtu-comprehensive:fast,virtu-moe-14b:fast \
      --nruns 1 --out runs/domain_ab_20261108 --seed 1234 --num-ctx 4096
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from virtu_eval import provenance as P  # noqa: E402

API = "http://localhost:11434/api/generate"
THINK_RE = re.compile(r"<think>.*?</think>", re.S)

# 判分器版本：与旧版 substring 口径的分不可混用。
GRADER_VERSION = "slot_exact_v2"
PREVIOUS_GRADER_VERSION = "substring_any_v1"
RUN_ID_RE = re.compile(r"^[0-9a-f]{16}$")

# 精确 token/槽位：ASCII 词（含下划线/数字）或连续汉字串各自成一个 token。
# "flange_X" 会切成单个 token "flange_x"，与候选 "flange" 不等 => 不再误判满分。
TOKEN_RE = re.compile(r"[a-z0-9_]+|[\u4e00-\u9fff]+")


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").lower()


def strip_think(s: str) -> str:
    return THINK_RE.sub("", s or "").strip()


def tokens(s: str):
    return TOKEN_RE.findall(norm(s))


def slot_hit(alt, haystack_tokens):
    """候选 any-of 项作为完整、连续的 token 槽位命中，取代旧版子串匹配。"""
    seq = tokens(alt)
    if not seq:
        return False
    width = len(seq)
    return any(haystack_tokens[i:i + width] == seq
               for i in range(len(haystack_tokens) - width + 1))


def read_served_layers(model: str) -> dict:
    """离线把 tag 解析成层摘要，参考 virtu_eval/arms.py::OllamaNativeArm._read_layers。

    不依赖 Ollama 服务在线：只读本地 manifest 文件；找不到时返回带 ``error`` 的
    dict（而不是空 dict —— 空 dict 会把"没取到身份"伪装成"已取证"）。
    """
    home = os.path.expanduser("~")
    roots = [p for p in (os.environ.get("OLLAMA_MODELS"),
                         os.path.join(home, ".ollama", "models"),
                         r"E:\ollama\models") if p and os.path.isdir(p)]
    if not roots:
        return {"error": "no ollama model store found"}
    name, _, tag = model.partition(":")
    tag = tag or "latest"
    layouts = (
        os.path.join("manifests-v2", "ollama.com", "library", name, tag),
        os.path.join("manifests", "registry.ollama.ai", "library", name, tag),
        os.path.join("manifests-v2", "registry.ollama.ai", "library", name, tag),
    )
    doc = None
    for root in roots:
        for layout in layouts:
            path = os.path.join(root, layout)
            if os.path.isfile(path):
                try:
                    with open(path, encoding="utf-8") as f:
                        doc = json.load(f)
                    break
                except (OSError, ValueError) as exc:
                    return {"error": f"manifest 解析失败 {path}: "
                                     f"{type(exc).__name__}:{exc}"}
        if doc is not None:
            break
    if doc is None:
        return {"error": f"tag {model!r} 的 manifest 未找到（checked {len(layouts)} layouts）"}
    out = {}
    for layer in doc.get("layers", []):
        media = layer.get("mediaType", "")
        for kind in ("model", "template", "system", "adapter", "params", "parameters"):
            if media.endswith("." + kind):
                key = "parameters" if kind == "params" else kind
                out[key] = layer.get("digest", "")
                out[key + "_bytes"] = layer.get("size")
    out["manifest_digest"] = doc.get("config", {}).get("digest", "")
    out["model_id"] = model
    return out


def gen(model, prompt, num_predict, temperature, seed, num_ctx, timeout=600):
    """返回 ``(text, meta)``。传输失败返回 ``(None, {error...})``，绝不返回伪分数。"""
    body = {"model": model, "prompt": prompt, "stream": False, "keep_alive": "20s",
            "options": {"num_predict": num_predict, "temperature": temperature,
                        "seed": seed, "num_ctx": num_ctx}}
    req = urllib.request.Request(API, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        r = json.load(urllib.request.urlopen(req, timeout=timeout))
    except urllib.error.HTTPError as e:
        # 传输层失败：不是模型答错，不记 0 分。
        return None, {"error": f"http_{e.code}:{e.read().decode('utf-8', 'replace')[:200]}",
                      "wall": time.time() - t0, "transport_error": True}
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        # 捕获具体异常并记录原因（不是 bare except / pass），调用方据此判红。
        return None, {"error": f"{type(e).__name__}:{e}",
                      "wall": time.time() - t0, "transport_error": True}
    ec = r.get("eval_count", 0) or 0
    ed = (r.get("eval_duration", 1) or 1) / 1e9
    return r.get("response", ""), {"eval_count": ec, "eval_duration": ed,
                                   "tok_s": (ec / ed if ed else 0),
                                   "wall": time.time() - t0,
                                   "transport_error": False}


def unload(model: str, wait_s: int = 25):
    """卸载模型并等 ollama ps 清空，避免切臂时两模型共存把系统内存打爆。"""
    subprocess.run(["ollama", "stop", model], capture_output=True, text=True,
                   encoding="utf-8", errors="replace")
    for _ in range(wait_s):
        out = subprocess.run(["ollama", "ps"], capture_output=True, text=True,
                             encoding="utf-8", errors="replace").stdout
        if len(out.strip().splitlines()) <= 1:
            return True
        time.sleep(1)
    return False


def score(text: str, case: dict):
    """精确 token/槽位判分。空匹配集（must 为空 / 空 any-of 组）一律判红。"""
    toks = tokens(strip_think(text))
    groups = case.get("must") or []
    if not groups:
        raise ValueError(f"空匹配集：用例 {case.get('id')!r} 的 must 为空，判分不得放行")
    hits, missed = 0, []
    for g in groups:
        if not g:
            raise ValueError(f"空匹配集：用例 {case.get('id')!r} 存在空的 any-of 组")
        if any(slot_hit(alt, toks) for alt in g):
            hits += 1
        else:
            missed.append(g[0])
    viol = 0
    for v in case.get("violations", []):
        if any(slot_hit(alt, toks) for alt in v):
            viol += 1
    raw = hits / len(groups)
    s = max(0.0, (hits - viol) / len(groups))
    return round(s * 100, 1), {"hits": hits, "groups": len(groups),
                               "violations": viol, "missed": missed,
                               "raw": round(raw * 100, 1),
                               "grader_version": GRADER_VERSION}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", required=True)
    ap.add_argument("--cases", default="benchmarks/virtu_domain_cases_2026-11-06.json")
    ap.add_argument("--out", default="runs/domain_ab")
    ap.add_argument("--num-predict", type=int, default=260)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--num-ctx", type=int, default=4096)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    cases_path = ROOT / args.cases
    cases = json.loads(cases_path.read_text(encoding="utf-8"))["cases"]
    if args.limit:
        cases = cases[:args.limit]
    if not cases:
        raise SystemExit("[FATAL] 空用例集，不得当成全绿放行")
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    if not models:
        raise SystemExit("[FATAL] 空模型列表")
    out_dir = ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    grader_sha256 = P.sha256_file(__file__)
    cases_sha256 = P.sha256_file(cases_path)

    summary = {}
    raw_path = out_dir / "raw.jsonl"
    total_scored, total_transport = 0, 0
    with open(raw_path, "w", encoding="utf-8") as raw_f:
        for model in models:
            served_layers = read_served_layers(model)
            scores, speeds, transport_ids = [], [], []
            t_start = time.time()
            for i, case in enumerate(cases, 1):
                text, meta = gen(model, case["q"], args.num_predict,
                                 args.temperature, args.seed, args.num_ctx)
                if text is None:
                    # 传输错误：score=None，绝不记 0 分当实测，也不计入均值。
                    sc, det = None, {"error": meta.get("error")}
                    transport_ids.append(case["id"])
                    verdict = "transport_error"
                else:
                    sc, det = score(text, case)
                    scores.append(sc)
                    speeds.append(meta["tok_s"])
                    verdict = "scored"
                raw_f.write(json.dumps({
                    "model": model, "case_id": case["id"], "cat": case.get("cat"),
                    "score": sc, "detail": det, "verdict": verdict,
                    "tok_s": meta.get("tok_s"),
                    "answer": strip_think(text or "")[:1200],
                    "served_layers": served_layers,
                    "grader_version": GRADER_VERSION,
                    "seed": args.seed, "num_ctx": args.num_ctx,
                }, ensure_ascii=False) + "\n")
                raw_f.flush()
                print(f"  [{model}] {i:>2}/{len(cases)} {case['id']:<16} "
                      f"{(f'{sc:>5.1f}' if sc is not None else '  ERR')} "
                      f"{meta.get('tok_s', 0):>6.2f} tok/s {verdict}", flush=True)
            total_scored += len(scores)
            total_transport += len(transport_ids)
            ok = bool(scores) and not transport_ids
            summary[model] = {
                "n": len(scores),                       # 有效样本量（已排除传输错误）
                "n_transport_errors": len(transport_ids),
                "transport_case_ids": transport_ids,
                "mean_score": round(statistics.mean(scores), 2) if scores else None,
                "median_score": round(statistics.median(scores), 2) if scores else None,
                "min_score": min(scores) if scores else None,
                "max_score": max(scores) if scores else None,
                "mean_tok_s": round(statistics.mean(speeds), 2) if speeds else None,
                "elapsed_s": round(time.time() - t_start, 1),
                "basis": "measured" if ok else "partial",
                "status": "ok" if ok else "transport_errors_excluded",
            }
            unload(model)
            print(f"== {model}: mean={summary[model]['mean_score']} "
                  f"tok/s={summary[model]['mean_tok_s']} n={summary[model]['n']} "
                  f"transport_errors={len(transport_ids)}", flush=True)

    # 封缄证据：raw.jsonl 的 sha256 与行数写入 _seal.json，事后改写可检出。
    seal = P.seal_leg(out_dir, owner="scripts/run_domain_ab.py")
    # run_id = 内容指纹：把证据/用例/判分器/采样参数/有效样本量一起哈希，取 16 位 hex。
    fingerprint_blob = json.dumps({
        "raw_sha256": seal["raw_sha256"],
        "cases_sha256": cases_sha256,
        "grader_sha256": grader_sha256,
        "grader_version": GRADER_VERSION,
        "params": {"models": models, "num_predict": args.num_predict,
                   "temperature": args.temperature, "seed": args.seed,
                   "num_ctx": args.num_ctx, "limit": args.limit},
        "n": total_scored,
    }, sort_keys=True, ensure_ascii=False).encode("utf-8")
    run_id = hashlib.sha256(fingerprint_blob).hexdigest()[:16]
    if not RUN_ID_RE.fullmatch(run_id):
        raise ValueError(f"run_id 生成异常（非 16 位 hex）：{run_id!r}")

    # 有传输错误 / 零有效样本 => 绝不按 measured 发布。
    top_basis = "measured" if (total_scored > 0 and total_transport == 0) else "partial"
    (out_dir / "summary.json").write_text(json.dumps({
        "when": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "cases": str(cases_path),
        "num_predict": args.num_predict,
        "temperature": args.temperature,
        "seed": args.seed,
        "num_ctx": args.num_ctx,
        "grader_version": GRADER_VERSION,
        "previous_grader_version": PREVIOUS_GRADER_VERSION,
        "grader_note": "精确 token/槽位匹配；与 substring 口径的历史分不可混用",
        "run_id": run_id,
        "n": total_scored,
        "basis": top_basis,
        "raw_sha256": seal["raw_sha256"],
        "cases_sha256": cases_sha256,
        "grader_sha256": grader_sha256,
        "seal": seal,
        "transport_errors": total_transport,
        "summary": summary,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n=== SUMMARY ===")
    for m, s in summary.items():
        mean = s["mean_score"] if s["mean_score"] is not None else "未测"
        print(f"{m:34s} score={mean} basis={s['basis']} n={s['n']} "
              f"transport_errors={s['n_transport_errors']}")
    print(f"run_id={run_id} basis={top_basis} n={total_scored} "
          f"grader_version={GRADER_VERSION}")


if __name__ == "__main__":
    main()
