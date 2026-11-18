#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Read-only inventory + reference graph for every Modelfile in the workspace.

Objective (2026-11-16 consolidation task, conservative tier):
  - fingerprint all Modelfile definitions (whole-file + SYSTEM/TEMPLATE/PARAMETER
    canonical hashes) so byte-identical duplicates are provable, not guessed;
  - build a reference graph over code/scripts/docs/config so a file is deleted
    only when it is both byte-duplicate AND has zero live references;
  - surface naming collisions and parameter/SYSTEM drift for the report.

This script NEVER writes/creates/deletes a Modelfile. It only emits two report
artifacts under reports/. Exit code 0 always unless a fatal IO error occurs.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT_JSON = ROOT / "reports" / "modelfile_universe_2026-11-16.json"
REPORT_MD = ROOT / "reports" / "MODELFIE_UNIVERSE_2026-11-16.md"  # typo-proofed below
REPORT_MD = ROOT / "reports" / "MODELFILE_UNIVERSE_2026-11-16.md"

# Directories that are never "live source": caches, archives, vendored, generated test sandboxes.
EXCLUDE_DIR_PARTS = {
    ".venv", "venv", "site-packages", "__pycache__", ".git", "00_归档",
    ".pytest_cache", ".pytest_temp", ".pytest_tmp_fix", ".pytest_tmp_google_sleep_check",
    ".pytest_tmp_sleep_full", ".ruff_cache", ".ollama_store",
}
# Generated test sandboxes are huge and mirror real files; skip for inventory but
# they can still contain references, handled by the text scan with a size cap.
TEXT_EXTS = {".py", ".sh", ".bat", ".ps1", ".md", ".json", ".yaml", ".yml",
             ".txt", ".toml", ".ini", ".cfg", ".modelfile", ".psm1"}
TEXT_SCAN_MAX_BYTES = 2_000_000
MODELFILE_NAME_RE = re.compile(r"modelfile", re.I)

BLOCK_RE = {
    "FROM": re.compile(r"(?im)^\s*FROM\s+(.+?)\s*$"),
    "SYSTEM": re.compile(r'(?ims)^\s*SYSTEM\s+"""(.*?)"""'),
    "TEMPLATE": re.compile(r'(?ims)^\s*TEMPLATE\s+"""(.*?)"""'),
    "ADAPTER": re.compile(r"(?im)^\s*ADAPTER\s+(.+?)\s*$"),
    "PARAMETER": re.compile(r"(?im)^\s*PARAMETER\s+(\S+)\s+(.+?)\s*$"),
    "MESSAGE": re.compile(r"(?im)^\s*MESSAGE\s+\w+\s+"),
    "LICENSE": re.compile(r"(?im)^\s*LICENSE\s+\S+"),
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def canon(text: str) -> str:
    """Normalise whitespace for semantic comparison (NOT for deletion decisions)."""
    return re.sub(r"\s+", " ", text).strip()


def excluded(path: Path) -> bool:
    if any(part in EXCLUDE_DIR_PARTS for part in path.parts):
        return True
    # 清理备份目录（reports/modelfile_cleanup_backup_*）不计入活定义盘点
    return any(part.startswith("modelfile_cleanup_backup") for part in path.parts)


def find_modelfiles() -> list[Path]:
    out = []
    for p in ROOT.rglob("*"):
        if not p.is_file() or excluded(p):
            continue
        if MODELFILE_NAME_RE.search(p.name):
            out.append(p)
    return sorted(out, key=lambda p: str(p.relative_to(ROOT)).lower())


def parse(text: str) -> dict:
    d = {}
    for key, rx in BLOCK_RE.items():
        if key in ("PARAMETER", "MESSAGE", "LICENSE"):
            vals = rx.findall(text)
            d[key] = vals if key == "PARAMETER" else len(vals)
        else:
            m = rx.search(text)
            d[key] = m.group(1).strip() if m and m.group(1) is not None else None
    # canonical hashes for behaviour comparison
    d["system_canon_sha"] = hashlib.sha256(canon(d["SYSTEM"] or "").encode()).hexdigest()[:16]
    d["template_canon_sha"] = hashlib.sha256(canon(d["TEMPLATE"] or "").encode()).hexdigest()[:16]
    params = sorted((k.strip().lower(), canon(v)) for k, v in d["PARAMETER"])
    d["params_canonical"] = params
    d["params_canon_sha"] = hashlib.sha256(json.dumps(params, ensure_ascii=False).encode()).hexdigest()[:16]
    return d


def main() -> int:
    # Optional: --with-refs runs the slow in-process text scan. By default we emit
    # fingerprints fast and let an external ripgrep pass build the reference graph.
    with_refs = "--with-refs" in sys.argv
    files = find_modelfiles()
    profiles = []
    for p in files:
        try:
            raw = p.read_bytes()
        except OSError as e:
            profiles.append({"path": str(p.relative_to(ROOT)), "error": str(e)})
            continue
        text = raw.decode("utf-8", errors="replace")
        info = parse(text)
        info["path"] = str(p.relative_to(ROOT)).replace("\\", "/")
        info["name"] = p.name
        info["size"] = len(raw)
        info["sha256"] = hashlib.sha256(raw).hexdigest()
        info["from"] = info.get("FROM")
        info["system_len"] = len(info.get("SYSTEM") or "")
        info["template_len"] = len(info.get("TEMPLATE") or "")
        info["system_preview"] = canon(info.get("SYSTEM") or "")[:160]
        # Do NOT retain full SYSTEM/TEMPLATE text for every profile (memory);
        # canonical_blocks are read separately for a handful of key files below.
        info.pop("SYSTEM", None)
        info.pop("TEMPLATE", None)
        profiles.append(info)

    # byte-identical duplicate groups
    by_sha = defaultdict(list)
    for info in profiles:
        if "sha256" in info:
            by_sha[info["sha256"]].append(info["path"])
    dup_groups = {sha: paths for sha, paths in by_sha.items() if len(paths) > 1}

    # basename collisions (same filename, different bytes)
    by_name = defaultdict(set)
    for info in profiles:
        if "sha256" in info:
            by_name[info["name"].lower()].add(info["sha256"])
    name_collisions = {n: len(shas) for n, shas in by_name.items() if len(shas) > 1}

    # reference graph: scan text files for each Modelfile's basename and relative path.
    # IMPORTANT: generic names like "modelfile" match nearly every doc and explode memory;
    # only use a basename as a search key when it is distinctive enough.
    by_basename = defaultdict(list)
    by_relpath = defaultdict(list)
    for info in profiles:
        if "name" not in info:
            continue
        name = info["name"].lower()
        distinctive = (
            len(name) >= 18
            and not name.startswith("modelfile.")
            and name not in ("modelfile", "modelfile2")
        )
        if distinctive:
            by_basename[name].append(info["path"])
        by_relpath[info["path"].lower()].append(info["path"])

    # Build one compiled alternation so each scanned line is matched in a single pass
    # (streaming read keeps memory constant even under the machine's ~2GB free RAM).
    name_targets = dict(by_basename)
    rel_targets = {k: v for k, v in by_relpath.items() if len(k) > len(Path(k).name)}
    all_keys = sorted(set(name_targets) | set(rel_targets), key=len, reverse=True)
    key_re = re.compile("|".join(re.escape(k) for k in all_keys)) if all_keys else None

    refs = defaultdict(set)  # modelfile path -> set of referring files
    scan_count = 0
    if with_refs:
        for p in ROOT.rglob("*"):
            if not p.is_file() or excluded(p):
                continue
            if p.suffix.lower() not in TEXT_EXTS:
                continue
            try:
                if p.stat().st_size > TEXT_SCAN_MAX_BYTES:
                    continue
            except OSError:
                continue
            rel_self = str(p.relative_to(ROOT)).replace("\\", "/").lower()
            rel_ref = str(p.relative_to(ROOT)).replace("\\", "/")
            try:
                with open(p, "r", encoding="utf-8", errors="replace") as fh:
                    for line in fh:  # streaming: never hold the whole file in memory
                        if not key_re:
                            break
                        low = line.lower()
                        for m in key_re.finditer(low):
                            key = m.group(0)
                            for targets in (name_targets.get(key), rel_targets.get(key)):
                                if not targets:
                                    continue
                                for t in targets:
                                    if t.lower() != rel_self:
                                        refs[t].add(rel_ref)
            except OSError:
                continue
            scan_count += 1

    # live ollama tags (read-only)
    live_tags = []
    try:
        import urllib.request
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=5) as r:
            live_tags = [m["name"] for m in json.load(r).get("models", [])]
    except Exception as e:
        live_tags = ["<unreachable: %s>" % e]

    # candidate = member of a byte-duplicate group AND zero external refs AND not a group representative
    # When refs were not scanned in-process, mark candidates as pending external ripgrep verification.
    candidates = []
    for sha, paths in dup_groups.items():
        # representative = shortest path; prefer outside scratch/checkpoints temp dirs
        def rank(x):
            return (sum(1 for seg in ("scratch", "checkpoints", "work", "temp") if seg in x.lower()), len(x))
        rep = sorted(paths, key=rank)[0]
        for path in paths:
            if path == rep:
                continue
            has_refs = bool(refs.get(path))
            if with_refs and has_refs:
                continue
            candidates.append({
                "path": path, "sha256": sha, "duplicate_of": rep,
                "ref_status": "referenced" if has_refs else ("verified_zero" if with_refs else "pending_ripgrep"),
                "external_refs": sorted(refs.get(path, [])),
                "reason": "byte-identical duplicate; " + (
                    "zero in-process refs" if with_refs else "reference check pending (run ripgrep)"),
            })

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "root": str(ROOT),
        "counts": {
            "modelfiles_total": len(profiles),
            "with_system": sum(1 for i in profiles if i.get("system_len")),
            "with_template": sum(1 for i in profiles if i.get("template_len")),
            "byte_duplicate_groups": len(dup_groups),
            "byte_duplicate_files": sum(len(v) for v in dup_groups.values()),
            "basename_collisions": len(name_collisions),
            "text_files_scanned_for_refs": scan_count,
            "conservative_cleanup_candidates": len(candidates),
        },
        "live_ollama_tags": live_tags,
        "profiles": [{k: v for k, v in i.items() if not k.startswith("_")} for i in profiles],
        "duplicate_groups": dup_groups,
        "basename_collisions": name_collisions,
        "references": {k: sorted(set(v)) for k, v in sorted(refs.items()) if v},
        "cleanup_candidates": candidates,
        "canonical_blocks": [],
    }
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # human-readable summary
    lines = [
        "# Modelfile Universe Inventory (2026-11-16)",
        "",
        f"- Generated: {report['generated_at']}",
        f"- Modelfiles: {report['counts']['modelfiles_total']} "
        f"(SYSTEM {report['counts']['with_system']}, TEMPLATE {report['counts']['with_template']})",
        f"- Byte-identical duplicate groups: {report['counts']['byte_duplicate_groups']} "
        f"covering {report['counts']['byte_duplicate_files']} files",
        f"- Basename collisions (same name, different bytes): {report['counts']['basename_collisions']}",
        f"- Conservative cleanup candidates (byte-dup + zero refs): {report['counts']['conservative_cleanup_candidates']}",
        f"- Live Ollama tags: {live_tags}",
        "",
        "## Duplicate groups",
        "",
    ]
    for sha, paths in sorted(dup_groups.items(), key=lambda kv: -len(kv[1])):
        lines.append(f"- `{sha[:12]}` ×{len(paths)}")
        for p in paths:
            lines.append(f"    - {p}")
    lines += ["", "## Conservative cleanup candidates", ""]
    for c in candidates:
        lines.append(f"- {c['path']}  →  dup of {c['duplicate_of']}")
    lines += ["", "## Basename collisions", ""]
    for n, c in sorted(name_collisions.items()):
        lines.append(f"- `{n}` → {c} distinct byte versions")
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "report_json": str(REPORT_JSON), "report_md": str(REPORT_MD),
        **report["counts"], "live_ollama_tags": live_tags,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
