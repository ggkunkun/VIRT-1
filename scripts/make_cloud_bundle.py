#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the upload bundle for a cloud training route.

  python scripts/make_cloud_bundle.py --route a          # L40S 48GB, bf16 LoRA
  python scripts/make_cloud_bundle.py --route c          # V100 32GB, fp16 QLoRA
  python scripts/make_cloud_bundle.py --route a --check  # gate only, write nothing

Each route re-verifies every file it ships (bytes + sha256), keeps data files
byte-identical so the trainer's own sha256 gate still passes on the host, forces
LF on shell scripts (bash refuses a CRLF script), and writes a reproducible
tarball plus the route's manifest ledger.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import sys
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HANDOFF = ROOT / "cloud_handoff"
SOURCE_DATE = 1762000000  # fixed for byte-reproducible tarballs

# v3 hardened corpus (CLOUD_TRAINING_HARDENING_PLAN_2026-11-01.md §3/§7.1)
CORPUS_JSONL = "data/train/virtu_v3/train/virtu_v3_text_sft.jsonl"
CORPUS_MANIFEST = "data/train/virtu_v3/virtu_fix_text_sft_v1.manifest.json"
CORPUS_MANIFEST_CANONICAL = "data/train/virtu_v3/manifest.json"

CORPUS = [
    CORPUS_JSONL,
    CORPUS_MANIFEST,
    CORPUS_MANIFEST_CANONICAL,
    "data/benchmark/virtu_fix_v1/formula_holdout_200.jsonl",
    "train_virtu.py",
    "scripts/build_train_v3.py",
    "scripts/build_capability_sft.py",
    "cloud_train_pack/prepare_v100_targeted_corpus.py",
    "scripts/build_fix_text_corpus.py",
    "scripts/knowledge_reasoning_seed.py",
    "scripts/build_formula_holdout.py",
    "CLOUD_TRAINING_HARDENING_PLAN_2026-11-01.md",
]

ROUTES = {
    "c": {
        "name": "C - V100-SXM2-32GB fp16 QLoRA",
        "hardware": "Tesla V100-SXM2-32GB, 32GB VRAM, 90GB RAM, 50GB data disk, CNY 1.98/h",
        "route_files": ["requirements-v100.txt",
                        "scripts/train_virtu_v100.py",
                        "scripts/bootstrap_v100_train.sh"],
        "budget_cap_cny": 50,
        "bootstrap": "scripts/bootstrap_v100_train.sh",
        "note": "V100 has no bf16 and no FlashAttention-2: fp16 + sdpa/eager, 4-bit NF4.",
    },
    "a": {
        "name": "A - L40S 48GB bf16 LoRA",
        "hardware": "NVIDIA L40S 48GB (Ada sm_89), bf16 + tf32, unquantized base, max_len 4096",
        "route_files": ["requirements-l40s.txt",
                        "scripts/train_virtu_l40s.py",
                        "scripts/bootstrap_l40s_train.sh"],
        "budget_cap_cny": 50,
        "bootstrap": "scripts/bootstrap_l40s_train.sh",
        "note": "flash-attn is optional; the trainer falls back to sdpa and never needs it.",
    },
}

# Only shell needs LF. Data ships byte-for-byte so the recorded sha256 stays true.
LF_SUFFIXES = (".sh",)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def normalize(raw: bytes, rel: str) -> tuple[bytes, bool]:
    if not rel.endswith(LF_SUFFIXES):
        return raw, False
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    out = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return out, out != raw


def route_paths(route: str) -> list[str]:
    return CORPUS + ROUTES[route]["route_files"]


def load_ledger(manifest: Path, route: str) -> dict:
    if not manifest.exists():
        return {"files": {}, "route": ROUTES[route]["name"]}
    return json.load(open(manifest, encoding="utf-8"))


def build_entries(manifest: dict, required: list[str], strict: bool) -> tuple[list[dict], list[str]]:
    listed = manifest.get("files", {})
    missing = [p for p in required if p not in listed]
    if missing:
        print("[warn] not yet in the ledger, will be added: " + ", ".join(missing))

    entries, problems = [], []
    for rel in required:
        src = ROOT / rel
        if not src.exists():
            problems.append(f"missing file: {rel}")
            continue
        payload, changed = normalize(src.read_bytes(), rel)
        digest = sha256_bytes(payload)
        old = listed.get(rel, {})
        if old.get("sha256") and old["sha256"] != digest:
            if changed and old["sha256"] == sha256_bytes(src.read_bytes()):
                pass
            elif strict:
                problems.append(
                    f"sha256 drift: {rel}\n    ledger ={old['sha256']}\n    actual ={digest}")
            else:
                print(f"[note] refreshing stale hash for {rel}")
        entries.append({
            "path": rel,
            "bytes": len(payload),
            "sha256": digest,
            "mode": 0o755 if rel.endswith(".sh") else 0o644,
            "lf_normalized": changed,
            "payload": payload,
        })
    return entries, problems


def check_corpus_gate(entries: list[dict]) -> list[str]:
    """train_virtu_{v100,l40s}.py aborts if the jsonl sha != the corpus manifest sha."""
    shipped = {e["path"]: e["sha256"] for e in entries}
    if CORPUS_JSONL not in shipped or CORPUS_MANIFEST not in shipped:
        return ["corpus or its manifest is not in the bundle"]
    doc = json.loads((ROOT / CORPUS_MANIFEST).read_bytes().decode("utf-8"))
    if doc.get("sha256") != shipped[CORPUS_JSONL]:
        return [f"corpus gate would fail on the host: {CORPUS_MANIFEST}.sha256="
                f"{doc.get('sha256')} but shipped {CORPUS_JSONL} is {shipped[CORPUS_JSONL]}"]
    if CORPUS_MANIFEST_CANONICAL in shipped:
        canon = json.loads((ROOT / CORPUS_MANIFEST_CANONICAL).read_bytes().decode("utf-8"))
        if canon.get("sha256") != doc.get("sha256"):
            return [f"manifests disagree: {CORPUS_MANIFEST_CANONICAL}.sha256="
                    f"{canon.get('sha256')} but {CORPUS_MANIFEST} says {doc.get('sha256')}"]
    print(f"[gate] {CORPUS_JSONL} sha256 == {CORPUS_MANIFEST}.sha256 ({doc['sha256'][:12]}...)")
    return []


def check_trainer_matches_ledger(entries: list[dict], route: str) -> list[str]:
    """The bundle must carry the trainer the bootstrap actually invokes."""
    boot = next((e for e in entries if e["path"] == ROUTES[route]["bootstrap"]), None)
    if boot is None:
        return ["bootstrap script missing from bundle"]
    text = boot["payload"].decode("utf-8")
    trainer = {"a": "scripts/train_virtu_l40s.py", "c": "scripts/train_virtu_v100.py"}[route]
    req = {"a": "requirements-l40s.txt", "c": "requirements-v100.txt"}[route]
    problems = []
    if f"$REPO_ROOT/{trainer}" not in text and trainer not in text:
        problems.append(f"{boot['path']} does not invoke {trainer}")
    for needed in (trainer, req):
        if needed not in {e["path"] for e in entries}:
            problems.append(f"bootstrap needs {needed} but the bundle does not ship it")
    return problems


def write_bundle(entries: list[dict], bundle: Path) -> tuple[str, int]:
    HANDOFF.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for e in sorted(entries, key=lambda x: x["path"]):
            info = tarfile.TarInfo(name="virtu/" + e["path"])
            info.size = e["bytes"]
            info.mtime = SOURCE_DATE
            info.mode = e["mode"]
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            tar.addfile(info, io.BytesIO(e["payload"]))
    tmp = bundle.parent / (bundle.name + ".tmp")
    with open(tmp, "wb") as fh:
        fh.write(gzip.compress(buf.getvalue(), compresslevel=9, mtime=0))
    os.replace(tmp, bundle)
    blob = bundle.read_bytes()
    return sha256_bytes(blob), len(blob)


def refresh_ledger(manifest: dict, route: str, entries: list[dict],
                   bundle: Path, digest: str, size: int) -> dict:
    meta = ROUTES[route]
    manifest["route"] = meta["name"]
    manifest["hardware"] = meta["hardware"]
    manifest["note"] = meta["note"]
    manifest["budget_cap_cny"] = meta["budget_cap_cny"]
    manifest["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    manifest["files"] = {e["path"]: dict(bytes=e["bytes"], sha256=e["sha256"],
                                         **({"lf_normalized": True} if e["lf_normalized"] else {}))
                         for e in sorted(entries, key=lambda x: x["path"])}
    manifest["bundle"] = {"path": str(bundle.relative_to(ROOT)).replace("\\", "/"),
                          "bytes": size, "sha256": digest, "extract_root": "virtu/"}
    manifest["remote_one_liner"] = (
        f"tar xzf {bundle.name} -C ~ && bash ~/virtu/{meta['bootstrap']}")
    manifest["train_command"] = f"bash {meta['bootstrap']}   # deps -> base -> preflight -> smoke -> train, resumable"
    manifest.setdefault("eval_gates", [
        "240-case virtu_eval gold=100",
        "200/200 formula holdout",
        "toolcall 30>=90 and 210 overall>=72.56",
        "knowledge/reasoning>=60 if claimed",
        "receipt status must be COMPLETED, never SMOKE_ONLY",
    ])
    tmp = manifest_path(route).with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, manifest_path(route))
    return manifest


def manifest_path(route: str) -> Path:
    return HANDOFF / f"MANIFEST_ROUTE_{route.upper()}.json"


def bundle_path(route: str) -> Path:
    return HANDOFF / f"virtu_bundle_route_{route.upper()}.tar.gz"


def sync_provenance(route: str, digest: str, size: int, count: int) -> None:
    prov_path = ROOT / "checkpoints" / "PROVENANCE.json"
    if not prov_path.exists():
        print("[warn] checkpoints/PROVENANCE.json missing; ledger not synced")
        return
    prov = json.load(open(prov_path, encoding="utf-8"))
    block = prov.setdefault("cloud_handoff", {})
    block[f"route_{route.upper()}"] = {
        "bundle": f"cloud_handoff/virtu_bundle_route_{route.upper()}.tar.gz",
        "bundle_sha256": digest,
        "bundle_bytes": size,
        "file_count": count,
        "ledger": f"cloud_handoff/MANIFEST_ROUTE_{route.upper()}.json",
        "recorded_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    tmp = prov_path.with_suffix(f".json.r{route}.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(prov, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, prov_path)
    print(f"[ledger] PROVENANCE cloud_handoff.route_{route.upper()}.bundle_sha256 = {digest[:16]}...")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--route", required=True, choices=sorted(ROUTES))
    ap.add_argument("--check", action="store_true", help="verify only; write nothing")
    args = ap.parse_args()

    route = args.route
    required = route_paths(route)
    mpath, bpath = manifest_path(route), bundle_path(route)
    manifest = load_ledger(mpath, route)
    entries, problems = build_entries(manifest, required, strict=args.check)
    problems += check_corpus_gate(entries)
    problems += check_trainer_matches_ledger(entries, route)
    if problems:
        for p in problems:
            print("[FATAL] " + p)
        return 2

    total = sum(e["bytes"] for e in entries)
    print(f"[route {route.upper()}] {ROUTES[route]['name']}")
    print(f"[bundle] {len(entries)} files, {total / 1e6:.2f}MB unpacked")
    for e in sorted(entries, key=lambda x: x["path"]):
        print(f"  {e['bytes']:>10,}  {e['sha256'][:12]}  {e['path']}"
              + ("  [LF]" if e["lf_normalized"] else ""))

    if args.check:
        if not bpath.exists():
            print(f"[FATAL] {bpath.name} not built yet")
            return 2
        actual = sha256_bytes(bpath.read_bytes())
        if manifest.get("bundle", {}).get("sha256") != actual:
            print(f"[FATAL] ledger names a different tarball: {actual}")
            return 2
        print("[check] all sha256 verified; nothing written")
        return 0

    digest, size = write_bundle(entries, bpath)
    refresh_ledger(manifest, route, entries, bpath, digest, size)
    sync_provenance(route, digest, size, len(entries))
    print(f"[bundle] wrote {bpath.relative_to(ROOT)} size={size / 1e6:.2f}MB sha256={digest}")
    print(f"[next] upload {bpath.name}, then on the host run exactly:")
    print(f"       {manifest['remote_one_liner']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
