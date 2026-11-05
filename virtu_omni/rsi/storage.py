"""Isolated, checksummed runs; no writes to weights or production configuration."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .contracts import RSIError, canonical_json, fingerprint, inside


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path, value):
    path = Path(path)
    payload = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp." + uuid.uuid4().hex)
    with temporary.open("x", encoding="utf-8", newline="\n") as fh:
        fh.write(payload)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(temporary, path)


def append_jsonl(path, value):
    with Path(path).open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(canonical_json(value) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


class FileLock:
    """OS-released advisory lock; the lock file is deliberately never deleted."""

    def __init__(self, path):
        self.path = Path(path)
        self.fh = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fh = self.path.open("a+b")
        self.fh.seek(0, os.SEEK_END)
        if self.fh.tell() == 0:
            self.fh.write(b"0")
            self.fh.flush()
        self.fh.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.fh.close()
            self.fh = None
            raise RSIError("Another RSI operation owns the lock") from exc
        return self

    def __exit__(self, *_):
        if self.fh is not None:
            self.fh.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.fh.fileno(), fcntl.LOCK_UN)
            self.fh.close()


class RunStore:
    def __init__(self, root, path=None):
        self.root = Path(root).resolve()
        base = inside(self.root, "runs/rsi")
        base.mkdir(parents=True, exist_ok=True)
        if path is None:
            name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:12]
            self.path = base / name
            self.path.mkdir(exist_ok=False)
        else:
            self.path = inside(base, inside(self.root, path))
            if not self.path.is_dir() or self.path == base:
                raise RSIError("Not an isolated RSI run directory")
        self.previous_audit_hash = "0" * 64

    def target(self, relative):
        path = inside(self.path, relative)
        if path == self.path:
            raise RSIError("A file name is required")
        return path

    def write(self, relative, value):
        write_json(self.target(relative), value)

    def append(self, relative, value):
        path = self.target(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        append_jsonl(path, value)

    def audit(self, event, **fields):
        record = {"time": utc_now(), "event": event, "previous": self.previous_audit_hash, **fields}
        record["hash"] = fingerprint(record)
        self.append("audit.jsonl", record)
        self.previous_audit_hash = record["hash"]

    def seal(self, sources):
        files = {}
        for path in sorted(self.path.rglob("*")):
            if not path.is_file() or path.name in ("evidence.json", ".lock", "approval.json"):
                continue
            if ".tmp." in path.name:
                continue
            inside(self.path, path)
            files[path.relative_to(self.path).as_posix()] = file_hash(path)
        body = {"version": 1, "files": files, "sources": sources}
        body["review_sha256"] = fingerprint(body)
        self.write("evidence.json", body)
        return body

    def verify(self, review_sha256=None, check_sources=True):
        try:
            evidence = json.loads(self.target("evidence.json").read_text(encoding="utf-8"))
            digest = evidence.pop("review_sha256")
            if digest != fingerprint(evidence) or review_sha256 and digest != review_sha256:
                raise RSIError("Review evidence fingerprint does not match")
            for relative, expected in evidence["files"].items():
                if file_hash(self.target(relative)) != expected:
                    raise RSIError(f"Run evidence was modified: {relative}")
            if check_sources:
                for relative, expected in evidence["sources"].items():
                    if file_hash(inside(self.root, relative)) != expected:
                        raise RSIError(f"Evaluator/source changed since this run: {relative}")
            evidence["review_sha256"] = digest
            return evidence
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise RSIError("Missing or malformed sealed evidence") from exc


def source_hashes(root, case_dir):
    root = Path(root).resolve()
    paths = list((root / "virtu_omni/rsi").glob("*.py"))
    paths += list((root / "virtu_eval").glob("*.py"))
    paths += [root / "scripts/wm_verifier.py", root / "scripts/distill_local_solver.py"]
    paths += list(inside(root, case_dir).glob("*.jsonl"))
    hard_holdout = root / "data/benchmark/virtu_fix_v1/formula_holdout_200.jsonl"
    if hard_holdout.is_file():
        paths.append(hard_holdout)
    return {p.relative_to(root).as_posix(): file_hash(p) for p in sorted(paths) if p.is_file()}


def assert_sources(root, expected):
    if any(file_hash(inside(root, path)) != digest for path, digest in expected.items()):
        raise RSIError("Evaluation/source fingerprint drift during run")
