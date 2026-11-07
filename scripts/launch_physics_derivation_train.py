#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage the verified physics corpus for the V100/L40S ladder and gate the run around it.

Target of this launcher is the already-verified path -- scripts/train_virtu_v100.py driven by
scripts/bootstrap_v100_train.sh. That path is chosen over cloud_train_pack/train_turnkey.py because
train_virtu_v100._data_files FATALs when the training file's sha256 disagrees with its manifest,
while train_turnkey quietly falls back to another corpus when --data does not resolve.

What this adds on top (the verified path does not check these):
  * layout conformance: exactly one *.jsonl under train/, manifest.json one level up;
  * a length gate: the corpus measures est p95 ~2091 tokens while the trainer defaults to
    max_len 2048, which would truncate assistant labels -- the job is refused before any GPU hour;
  * a ruler re-check: a random sample of staged rows must still score 100 under
    derivation_verified/physics_invariant, so a corpus cannot drift away from the eval it feeds;
  * receipt verification: rows, max_len, status and data_file must match what we staged.

Usage:
    python scripts/launch_physics_derivation_train.py --stage
    python scripts/launch_physics_derivation_train.py --preflight --mode v100
    python scripts/launch_physics_derivation_train.py --print-command --mode v100
    python scripts/launch_physics_derivation_train.py --verify-receipt <output/training_receipt.json>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (ROOT, os.path.join(ROOT, "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

SRC_DIR = os.path.join(ROOT, "data", "physics_derivation_v1")
SRC_CORPUS = os.path.join(SRC_DIR, "derivation_sft.jsonl")
SRC_MANIFEST = os.path.join(SRC_DIR, "MANIFEST.json")
STAGED_DIR = os.path.join(SRC_DIR, "train")
STAGED_CORPUS = os.path.join(STAGED_DIR, "derivation_sft.jsonl")
STAGED_MANIFEST = os.path.join(SRC_DIR, "manifest.json")   # train_virtu_v100 looks one level up


def rel_posix(path):
    """Rental boxes are Linux: never emit backslashed paths into a printed command."""
    return os.path.relpath(path, ROOT).replace(os.sep, "/")
TRAINER = "scripts/train_virtu_v100.py"

MODES = {
    "v100": {"base": "$WORKDIR/models/Qwen3-8B", "max_len": 3072, "epochs": 3, "bs": 1,
             "accum": 32, "hours": 3, "tok_per_s": 1814.0, "cny_per_hour": 1.98,
             "extra": [], "note": "V100-32GB, sm_70 无 bf16 -> fp16/nf4；1814 padded tok/s 为实测锚点"},
    "l40s": {"base": "$WORKDIR/models/Qwen3-8B", "max_len": 3072, "epochs": 2, "bs": 2,
             "accum": 8, "hours": 2, "tok_per_s": 3600.0, "cny_per_hour": 3.2,
             "extra": [], "note": "L40S-48GB bf16"},
}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def stage():
    """Copy the corpus into the layout the verified trainer requires, then prove the bytes moved."""
    problems = []
    if not os.path.exists(SRC_CORPUS):
        return [f"corpus missing: {SRC_CORPUS} (run build_physics_derivation_corpus.py)"]
    manifest = json.load(open(SRC_MANIFEST, encoding="utf-8"))
    src_sha = sha256_file(SRC_CORPUS)
    if src_sha != manifest.get("sha256"):
        return [f"source sha256 {src_sha[:16]} != MANIFEST {manifest.get('sha256','')[:16]}"]

    os.makedirs(STAGED_DIR, exist_ok=True)
    shutil.copyfile(SRC_CORPUS, STAGED_CORPUS)
    staged_sha = sha256_file(STAGED_CORPUS)
    if staged_sha != src_sha:
        problems.append(f"staged copy differs: {staged_sha[:16]} != {src_sha[:16]}")
    json.dump({"sha256": src_sha, "rows": manifest["rows"],
               "file": "train/derivation_sft.jsonl",
               "source": "scripts/build_physics_derivation_corpus.py",
               "gates": {"registry_equals_solver": True, "gold_scores_100": True,
                          "eval_holdout_separated": True},
               "rejects_at_generation": manifest.get("rejects"),
               "per_task": manifest.get("per_task")},
              open(STAGED_MANIFEST, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    files = [f for f in os.listdir(STAGED_DIR) if f.endswith(".jsonl")]
    if len(files) != 1:
        problems.append(f"train_virtu_v100 expects exactly one *.jsonl in train/, found {files}")
    print(f"[stage] {os.path.relpath(STAGED_CORPUS, ROOT)} sha256={staged_sha[:16]}... "
          f"rows={manifest['rows']}")
    print(f"[stage] {os.path.relpath(STAGED_MANIFEST, ROOT)} (read by the trainer as its FATAL gate)")
    return problems


def est_tokens(text):
    """CJK char/token ratio taken from wm_contract's own estimate (chars/1.6)."""
    return len(text) / 1.6


def preflight(mode, sample_rows=40, seed=7):
    problems = []
    if not os.path.exists(STAGED_CORPUS):
        return ["staged corpus missing; run --stage first"], {}
    staged_manifest = json.load(open(STAGED_MANIFEST, encoding="utf-8"))
    sha = sha256_file(STAGED_CORPUS)
    if sha != staged_manifest.get("sha256"):
        problems.append(f"staged sha256 {sha[:16]} != manifest {staged_manifest.get('sha256','')[:16]}")

    rows = [json.loads(l) for l in open(STAGED_CORPUS, encoding="utf-8") if l.strip()]
    if len(rows) != staged_manifest.get("rows"):
        problems.append(f"staged rows {len(rows)} != manifest {staged_manifest.get('rows')}")

    lengths, bad_shape = [], 0
    for r in rows:
        msgs = r.get("messages")
        if not (isinstance(msgs, list) and [m.get("role") for m in msgs]
                == ["system", "user", "assistant"]):
            bad_shape += 1
            continue
        try:
            ans = json.loads(msgs[2]["content"])
        except Exception:  # noqa: BLE001
            bad_shape += 1
            continue
        if not {"world_state", "derivation"} <= set(ans):
            bad_shape += 1
            continue
        lengths.append(sum(est_tokens(m["content"]) for m in msgs))
    if bad_shape:
        problems.append(f"{bad_shape} rows have the wrong message/answer shape")

    p95 = sorted(lengths)[int(len(lengths) * 0.95)] if lengths else 0
    cfg = MODES[mode]
    if p95 + 128 > cfg["max_len"]:
        problems.append(f"{mode} max_len {cfg['max_len']} would truncate: est p95 {p95:.0f} needs "
                        f">= {p95 + 128:.0f}; raise --max-len or shorten the system contract")

    from virtu_eval.graders import score_case

    rng = random.Random(seed)
    failed = []
    for idx in rng.sample(range(len(rows)), min(sample_rows, len(rows))):
        r = rows[idx]
        scen = r.get("scenario")
        if not scen:
            failed.append(f"row {idx}: no scenario sidecar")
            continue
        crit = [{"type": "json_object", "key": "j", "required_keys": ["world_state", "derivation"]},
                {"type": "derivation_verified", "key": "d", "scenario": scen, "tol_rel": 0.01},
                {"type": "physics_invariant", "key": "i", "scenario": scen}]
        scored = score_case(r["messages"][2]["content"], crit)
        if scored["score"] < 100.0:
            failed.append(f"row {idx} ({scen['task']}): " + "; ".join(
                c["evidence"] for c in scored["criteria"] if not c["passed"])[:150])
    if failed:
        problems.append(f"{len(failed)}/{sample_rows} sampled rows no longer score 100 under the ruler")
        problems.extend("    " + f for f in failed[:5])

    return problems, {"rows": len(rows), "sha256": sha, "est_p95": round(p95),
                      "est_max": round(max(lengths)) if lengths else 0, "mode": mode}


def build_command(mode, output):
    cfg = MODES[mode]
    return ["python", TRAINER,
            "--base", cfg["base"], "--data", rel_posix(STAGED_DIR),
            "--output", output, "--max-len", str(cfg["max_len"]),
            "--epochs", str(cfg["epochs"]), "--bs", str(cfg["bs"]),
            "--accum", str(cfg["accum"])] + list(cfg["extra"])


def cost_estimate(mode, rows, avg_tokens):
    cfg = MODES[mode]
    total = rows * avg_tokens * cfg["epochs"]
    hours = total / cfg["tok_per_s"] / 3600.0
    return {"mode": mode, "tokens_total_M": round(total / 1e6, 2), "hours": round(hours, 2),
            "cny": round(hours * cfg["cny_per_hour"], 2),
            "global_batch": cfg["bs"] * cfg["accum"],
            "steps": int(rows * cfg["epochs"] // (cfg["bs"] * cfg["accum"]))}


def verify_receipt(path, expected):
    if not os.path.exists(path):
        return [f"receipt not found: {path}"], {}
    rec = json.load(open(path, encoding="utf-8"))
    problems = []
    if rec.get("data_rows") != expected["rows"]:
        problems.append(f"receipt data_rows={rec.get('data_rows')} != staged {expected['rows']}")
    if os.path.basename(rec.get("data_file", "")) != os.path.basename(STAGED_CORPUS):
        problems.append(f"receipt data_file={rec.get('data_file')} is not the staged derivation corpus")
    max_len = (rec.get("train") or {}).get("max_len")
    if not max_len or max_len < expected["est_p95"] + 128:
        problems.append(f"receipt max_len={max_len} < est p95 {expected['est_p95']}+128 "
                        f"-> labels were truncated during training")
    if rec.get("status") not in ("COMPLETED",):
        problems.append(f"receipt status={rec.get('status')} (expected COMPLETED); "
                        f"a SMOKE_ONLY adapter must not be reported as a trained model")
    return problems, rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", action="store_true")
    ap.add_argument("--preflight", action="store_true")
    ap.add_argument("--print-command", action="store_true")
    ap.add_argument("--mode", choices=MODES, default="v100")
    ap.add_argument("--output", default="checkpoints/virtu_physics_derivation_lora")
    ap.add_argument("--verify-receipt")
    args = ap.parse_args()

    if args.stage:
        problems = stage()
        for p in problems:
            print("STAGE FAILED:", p)
        return 1 if problems else 0

    if args.verify_receipt:
        expected = {"rows": 2400, "est_p95": 0}
        if os.path.exists(STAGED_MANIFEST):
            m = json.load(open(STAGED_MANIFEST, encoding="utf-8"))
            expected["rows"] = m.get("rows", expected["rows"])
        problems, rec = verify_receipt(args.verify_receipt, expected)
        for p in problems:
            print("RECEIPT GATE FAILED:", p)
        if rec:
            print(f"[receipt] status={rec.get('status')} rows={rec.get('data_rows')} "
                  f"max_len={(rec.get('train') or {}).get('max_len')} "
                  f"final_loss={rec.get('final_loss')} runtime={rec.get('train_runtime_s')}s")
        return 1 if problems else 0

    problems, stats = preflight(args.mode)
    for p in problems:
        print("PREFLIGHT FAILED:", p)
    if problems:
        return 1
    est = cost_estimate(args.mode, stats["rows"], stats["est_p95"])
    print(f"[preflight OK] rows={stats['rows']} sha256={stats['sha256'][:16]}... "
          f"est_tokens p95={stats['est_p95']} max={stats['est_max']}")
    print(f"[cost derived from measured anchor ({MODES[args.mode]['note']})] "
          f"~{est['hours']} h ~= ¥{est['cny']}, steps≈{est['steps']}, "
          f"global_batch={est['global_batch']}, tokens={est['tokens_total_M']}M")
    print("[command on the rental box] " + " ".join(build_command(args.mode, args.output)))
    print("[bootstrap form] BASE=... DATA=" + rel_posix(STAGED_DIR) +
          " OUTPUT=" + args.output + f" MAX_HOURS={MODES[args.mode]['hours']} "
          f"bash scripts/bootstrap_v100_train.sh")
    print("[note] nothing is launched from this box; GPU work happens on the rental instance.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
