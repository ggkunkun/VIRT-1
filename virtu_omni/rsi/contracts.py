"""Validated contracts and deterministic development/validation isolation."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import math
import random
import re
import time
import unicodedata
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import urlsplit


class RSIError(RuntimeError):
    """A fail-closed RSI operation."""


class BudgetExhausted(RSIError):
    """No more model calls are authorized by this run's budget."""


def remote_url(value):
    """Opt-in non-loopback endpoint for cloud runs; no credentials may ride in the URL."""
    try:
        p = urlsplit(value)
        host = p.hostname
        port = p.port
    except ValueError as exc:
        raise RSIError("Malformed remote endpoint") from exc
    if (p.scheme not in ("http", "https") or not host or p.username or p.password
            or p.path not in ("", "/", "/v1", "/v1/") or p.query or p.fragment):
        raise RSIError("Remote endpoint must be a bare http(s) origin, optionally /v1, "
                       "without credentials")
    if not port:
        raise RSIError("Remote endpoint needs an explicit port")
    return value.rstrip("/")


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def fingerprint(value):
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def normalized(text):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).strip().lower()


def question_key(case):
    return fingerprint([normalized(m.get("content", ""))
                        for m in case.get("context", []) if m.get("role") == "user"]
                       + [normalized(case["prompt"])])


def scenario_keys(case):
    return sorted({fingerprint(c["scenario"]) for c in case.get("criteria", [])
                   if isinstance(c.get("scenario"), dict)})


def inside(root, path):
    root = Path(root).resolve()
    path = Path(path)
    path = (path if path.is_absolute() else root / path).resolve()
    if not path.is_relative_to(root):
        raise RSIError(f"Path is outside the project: {path}")
    return path


def local_url(value):
    try:
        p = urlsplit(value)
        host = p.hostname
        loopback = host == "localhost" or bool(host and ipaddress.ip_address(host).is_loopback)
        port = p.port
    except ValueError as exc:
        raise RSIError("Only a literal loopback endpoint or localhost is allowed") from exc
    if (p.scheme not in ("http", "https") or not loopback or p.username or p.password
            or p.path not in ("", "/") or p.query or p.fragment or not port):
        raise RSIError("RSI may contact only a loopback model endpoint with an explicit port")
    return value.rstrip("/")


@dataclass(frozen=True)
class Config:
    case_dir: str = "data/benchmark/virtu_eval_phys_v1"
    dimensions: tuple = ("physics",)
    model_id: str = "virtu-ties-v1:latest"
    base_url: str = "http://127.0.0.1:11434"
    rounds: int = 2
    limit: int = 0
    seed: int = 20261104
    validation_fraction: float = 0.4
    min_validation: int = 20
    min_gain: float = 5.0
    max_dimension_regression: float = 0.0
    max_regressions: int = 0
    min_dev_gain: float = 0.1
    plateau_rounds: int = 2
    max_calls: int = 160
    max_seconds: int = 900
    timeout: int = 90
    max_tokens: int = 512
    proposal_tokens: int = 1024
    max_strategy_chars: int = 2400
    synthetic_per_task: int = 12
    # Extra case directories whose scenarios/prompts must never be reproduced by the SFT
    # candidates, even though they are not selectable for dev/validation. Without this the
    # protection scope silently equals the selection scope: point RSI at a fresh pool and the
    # published evaluation boards stop being protected at all.
    protect_dirs: tuple = ()
    # Full build_arm spec for models whose served profile differs from the RSI default.
    # The 13.63B MoE has to be measured as served (num_gpu=30 + the tool schema on the
    # toolcall dimension); without it the loop measures a profile nobody runs.
    arm_spec: dict = field(default_factory=dict)
    # Cloud runs drive an OpenAI-compatible endpoint outside loopback. That is never the
    # default: without this explicit opt-in every run stays pinned to the local box.
    allow_remote: bool = False
    # Paired-noise resolution gate. A mean gain must clear noise_z*noise_sigma/sqrt(n) before
    # it may be called an improvement: measured paired_sigma on this box is 8.84 points
    # (runs/moe14b_noise_probe.json), while min_dev_gain is 0.1, so without this gate the
    # loop accepts sampling jitter as self-improvement. 0 keeps the historical behaviour.
    noise_sigma: float = 0.0
    noise_z: float = 1.96
    # Protocol fixtures (a declared fake transport) set this so the loop can be exercised
    # without a live model on the box. A synthetic run can never be certified or approved:
    # the gate reports certifiable=false no matter how large the scores it fabricates are.
    synthetic_run: bool = False

    def __post_init__(self):
        for name in ("rounds", "min_validation", "plateau_rounds", "max_calls", "max_seconds",
                     "timeout", "max_tokens", "proposal_tokens", "max_strategy_chars"):
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                raise RSIError(f"{name} must be a positive integer")
        for name in ("limit", "max_regressions", "synthetic_per_task", "seed"):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise RSIError(f"{name} must be a nonnegative integer")
        for name in ("validation_fraction", "min_gain", "max_dimension_regression", "min_dev_gain"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise RSIError(f"{name} must be finite")
        if not 0 < self.validation_fraction < 1 or not 0 < self.min_gain <= 100:
            raise RSIError("Invalid validation fraction or minimum gain")
        if self.max_dimension_regression < 0 or self.min_dev_gain <= 0:
            raise RSIError("Invalid regression/development gate")
        if self.rounds > 8 or self.max_calls > 2000 or self.max_seconds > 86400:
            raise RSIError("Requested recursion or resource budget is above the hard limit")
        if self.synthetic_per_task > 200 or self.max_strategy_chars > 8000:
            raise RSIError("Candidate size is above the hard limit")
        if not isinstance(self.model_id, str) or not self.model_id.strip():
            raise RSIError("model_id is required")
        if not isinstance(self.dimensions, (tuple, list)) or any(not isinstance(d, str) for d in self.dimensions):
            raise RSIError("dimensions must be a list of strings")
        if not isinstance(self.protect_dirs, (tuple, list)) or any(
                not isinstance(d, str) or not d.strip() for d in self.protect_dirs):
            raise RSIError("protect_dirs must be a list of directory paths")
        object.__setattr__(self, "protect_dirs", tuple(self.protect_dirs))
        if not isinstance(self.arm_spec, dict):
            raise RSIError("arm_spec must be an object")
        unknown = set(self.arm_spec) - {"kind", "model_id", "base_url", "num_ctx", "num_gpu",
                                        "think", "strip_think", "retries", "timeout",
                                        "tools", "tools_dimensions"}
        if unknown:
            raise RSIError(f"arm_spec has unknown keys: {sorted(unknown)}")
        kind = self.arm_spec.get("kind", "ollama_native")
        if kind not in ("ollama_native", "http_openai"):
            raise RSIError(f"RSI does not drive arm kind: {kind}")
        if type(self.allow_remote) is not bool:
            raise RSIError("allow_remote must be a boolean")
        if type(self.synthetic_run) is not bool:
            raise RSIError("synthetic_run must be a boolean")
        if kind == "http_openai" and not self.allow_remote:
            raise RSIError("http_openai requires allow_remote=true; RSI never contacts a "
                           "non-loopback endpoint by default")
        for name in ("noise_sigma", "noise_z"):
            value = getattr(self, name)
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value) or value < 0):
                raise RSIError(f"{name} must be a finite nonnegative number")
        if self.noise_sigma > 0 and not self.noise_z > 1.0:
            raise RSIError("noise_z must exceed 1 when the noise gate is enabled")
        if self.arm_spec.get("kind", "ollama_native") == "http_openai":
            remote_url(self.base_url)
        else:
            local_url(self.base_url)

    def snapshot(self):
        return asdict(self)


class Budget:
    def __init__(self, config, clock=time.monotonic):
        self.config = config
        self.clock = clock
        self.started = clock()
        self.calls = 0

    @property
    def remaining_seconds(self):
        return self.config.max_seconds - (self.clock() - self.started)

    def acquire(self):
        if self.calls >= self.config.max_calls or self.remaining_seconds < 2:
            raise BudgetExhausted("Model-call or wall-clock budget exhausted")
        self.calls += 1
        return max(1, min(self.config.timeout, int(self.remaining_seconds) - 1))

    def snapshot(self):
        return {"calls": self.calls, "max_calls": self.config.max_calls,
                "elapsed_s": round(self.clock() - self.started, 3),
                "max_seconds": self.config.max_seconds}


def read_jsonl(path):
    records = []
    with Path(path).open(encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, 1):
            if not line.strip():
                continue
            try:
                rec = json.loads(line, parse_constant=lambda s: (_ for _ in ()).throw(ValueError(s)))
            except ValueError as exc:
                raise RSIError(f"Malformed JSON at {Path(path).name}:{line_no}") from exc
            if not isinstance(rec, dict):
                raise RSIError(f"Record is not an object at {Path(path).name}:{line_no}")
            records.append(rec)
    return records


def load_cases(root, directory, dimensions=()):
    from virtu_eval.graders import GRADERS

    directory = inside(root, directory)
    if not directory.is_dir():
        raise RSIError("Case directory does not exist")
    selected, protected, seen_ids, seen_questions = [], [], set(), set()
    for path in sorted(directory.glob("*.jsonl")):
        inside(root, path)
        for case in read_jsonl(path):
            if (not isinstance(case.get("id"), str) or not case["id"]
                    or not isinstance(case.get("prompt"), str) or not case["prompt"].strip()
                    or not isinstance(case.get("dimension"), str)
                    or not isinstance(case.get("criteria"), list) or not case["criteria"]):
                raise RSIError(f"Incomplete case schema in {path.name}")
            if case["id"] in seen_ids:
                raise RSIError(f"Duplicate case id: {case['id']}")
            for criterion in case["criteria"]:
                if not isinstance(criterion, dict) or criterion.get("type") not in GRADERS:
                    raise RSIError(f"Unknown criterion in {case['id']}")
                w = criterion.get("weight", 1)
                if isinstance(w, bool) or not isinstance(w, (float, int)) or not math.isfinite(w) or w <= 0:
                    raise RSIError(f"Invalid criterion weight in {case['id']}")
            key = question_key(case)
            if key in seen_questions:
                raise RSIError(f"Duplicate normalized question: {case['id']}")
            seen_ids.add(case["id"])
            seen_questions.add(key)
            protected.append(case)
            if not dimensions or case["dimension"] in dimensions:
                selected.append(case)
    if not selected:
        raise RSIError("No matching evaluation cases")
    return selected, protected


def protect_cases(root, dirs):
    """Cases whose scenarios and prompts the SFT candidates must never reproduce.

    These are *not* selectable for dev/validation -- they only widen the protection scope, so
    running RSI on a fresh pool cannot silently stop protecting the published boards.
    Malformed or duplicated rows here are skipped rather than fatal: this is a guard set, not
    a scored case set, and a guard must not be able to break a run by being noisy.
    """
    collected, seen_ids, seen_questions = [], set(), set()
    for rel in dirs:
        directory = inside(root, rel)
        if not directory.is_dir():
            raise RSIError(f"protect_dir does not exist: {rel}")
        for path in sorted(directory.glob("*.jsonl")):
            inside(root, path)
            for case in read_jsonl(path):
                if not isinstance(case, dict) or not isinstance(case.get("criteria"), list):
                    continue
                key = question_key(case) if case.get("prompt") else None
                cid = case.get("id")
                if (isinstance(cid, str) and cid in seen_ids) or (key and key in seen_questions):
                    continue
                if isinstance(cid, str):
                    seen_ids.add(cid)
                if key:
                    seen_questions.add(key)
                collected.append(case)
    return collected


def split_cases(cases, config):
    """Group identical scenarios first; never put a reformulation across splits."""
    groups, by_key = [], {}
    for case in sorted(cases, key=lambda c: c["id"]):
        keys = ["q:" + question_key(case)] + ["s:" + k for k in scenario_keys(case)]
        matches = {id(by_key[k]): by_key[k] for k in keys if k in by_key}
        if matches:
            group = next(iter(matches.values()))
            for other in list(matches.values())[1:]:
                group.extend(other)
                groups.remove(other)
                for k, value in list(by_key.items()):
                    if value is other:
                        by_key[k] = group
        else:
            group = []
            groups.append(group)
        group.append(case)
        for key in keys:
            by_key[key] = group
    buckets = defaultdict(list)
    for group in groups:
        strata = tuple(sorted({(c["dimension"], c.get("tier", "unknown")) for c in group}))
        buckets[strata].append(group)
    rng = random.Random(config.seed)
    for bucket in buckets.values():
        rng.shuffle(bucket)
    ordered = []
    while any(buckets.values()):
        for key in sorted(buckets):
            if buckets[key]:
                ordered.append(buckets[key].pop())
    chosen, count = [], 0
    for group in ordered:
        if not config.limit or count + len(group) <= config.limit:
            chosen.append(group)
            count += len(group)
    strata = defaultdict(list)
    for group in chosen:
        key = tuple(sorted({(c["dimension"], c.get("tier", "unknown")) for c in group}))
        strata[key].append(group)
    dev, validation = [], []
    for key in sorted(strata):
        bucket = strata[key]
        n_val = min(len(bucket) - 1, max(1, round(len(bucket) * config.validation_fraction)))
        for i, group in enumerate(bucket):
            (validation if i < n_val else dev).extend(group)
    if not dev or not validation:
        raise RSIError("Need disjoint development and validation groups; increase --limit")
    return sorted(dev, key=lambda c: c["id"]), sorted(validation, key=lambda c: c["id"])
