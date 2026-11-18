"""Provenance: the one place that decides whether a number may be published.

Every fabrication found on 2026-11-05 was the same shape - a number in a report with no
way to ask "which bytes produced you?":

  * `physics_compliance = 1.0` (a source literal) printed as a 100% veto metric;
  * `HISTORICAL_BASELINES` typed into a file printed as three measured arms, plus 0.62/0.85/0.94
    invented inline;
  * a 56-record arm made entirely of `http_404` recorded as `completed`;
  * scores attributed to a tag name that another session re-pointed mid-leg (four tags sharing
    one manifest), and a ruler (`graders.py`) swapped between legs;
  * 255 corpus rows teaching mm^5 under an `inertia_*_mm4` field name, uncaught because no
    case graded that family.

So this module provides four primitives and nothing else:

1. ``RunIdentity.capture()``  - content-addressed pin of artifacts (Ollama layer digests),
   case files and ruler sources, reduced to one ``run_id``. Two runs are comparable only if
   their ``run_id`` matches; ``verify()`` lists what moved, which is how a mid-leg re-tag or a
   grader edit stops being a surprise.
2. ``Metric`` - a value that must carry ``basis`` (measured / asserted / inferred) plus the
   evidence path and sample size, and refuses to be rendered otherwise.
3. ``render_table()`` - the only publishing path; a measured metric without existing evidence
   or with n==0 raises instead of printing a number.
4. ``noise_envelope()`` + ``delta_verdict()`` - before any two-arm difference is called a gain,
   the ruler's own run-to-run spread (paired temperature=0 re-asks) sets the band, and an
   asymmetric budget-truncation rate voids a delta that only points at the token ceiling.

Deliberately no framework, no registry, no base class: a dict of digests and a raising function.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import math
import os
import statistics
import time
from pathlib import Path

ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASIS = ("measured", "partial", "asserted", "inferred")


def sha256_file(path) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _store_manifest_path(model_id: str):
    home = Path(os.path.expanduser("~"))
    name, _, revision = model_id.partition(":")
    for base in (home / ".ollama" / "models" / "manifests", Path(r"E:\ollama\models\manifests")):
        candidate = base / "registry.ollama.ai" / "library" / name / (revision or "latest")
        if candidate.exists():
            return candidate
    return None


def artifact_identity(model_id: str) -> dict:
    """Digest-addressed identity of what a tag currently resolves to (absent -> present=False)."""
    path = _store_manifest_path(model_id)
    if path is None:
        return {"model_id": model_id, "present": False}
    doc = json.loads(path.read_text(encoding="utf-8"))
    layers = {}
    for layer in doc.get("layers", []):
        media = layer.get("mediaType", "")
        for kind in ("model", "template", "system", "adapter", "parameters"):
            if media.endswith("." + kind):
                layers[kind] = layer.get("digest", "")
                layers[kind + "_bytes"] = layer.get("size", 0)
    return {"model_id": model_id, "present": True,
            "manifest_sha256": sha256_file(path), **layers}


class RunIdentity:
    """What a measurement actually touched, by digest rather than by name."""

    def __init__(self, artifacts, cases, ruler, extra=None, captured_at=None, run_id=None):
        self.artifacts = artifacts
        self.cases = cases
        self.ruler = ruler
        self.extra = extra or {}
        self.captured_at = captured_at or time.strftime("%Y-%m-%dT%H:%M:%S")
        self.run_id = run_id or self._fingerprint()

    def _fingerprint(self) -> str:
        blob = json.dumps({"a": self.artifacts, "c": self.cases, "r": self.ruler,
                            "x": self.extra}, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]

    @classmethod
    def capture(cls, model_ids=(), case_dirs=(), ruler_files=("virtu_eval/graders.py",
                                                              "virtu_eval/runner.py",
                                                              "virtu_eval/arms.py"),
                extra=None) -> "RunIdentity":
        artifacts = {}
        for model_id in model_ids:
            ident = artifact_identity(model_id)
            if ident.get("model_bytes"):
                ident["weights_bytes"] = ident["model_bytes"]
            artifacts[model_id] = ident
        cases = {}
        for case_dir in case_dirs:
            directory = Path(case_dir)
            if not directory.is_absolute():
                directory = ROOT / directory
            for path in sorted(directory.glob("*.jsonl")):
                # Key by workspace-relative path, not bare filename: this repo
                # has several same-named corpora (e.g. boundary.jsonl), so a
                # name-only key cannot be attributed to a specific byte range.
                try:
                    key = path.resolve().relative_to(Path(ROOT).resolve()).as_posix()
                except ValueError:
                    key = path.resolve().as_posix()
                cases[key] = sha256_file(path)
        ruler = {}
        for rel in ruler_files:
            path = ROOT / rel
            if path.exists():
                ruler[rel] = sha256_file(path)
        return cls(artifacts, cases, ruler, extra=extra)

    def to_dict(self) -> dict:
        return {"run_id": self.run_id, "captured_at": self.captured_at,
                "artifacts": self.artifacts, "cases": self.cases, "ruler": self.ruler,
                "extra": self.extra}

    def write(self, path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)

    @classmethod
    def read(cls, path) -> "RunIdentity":
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(doc["artifacts"], doc["cases"], doc["ruler"], doc.get("extra", {}),
                   doc.get("captured_at"), doc.get("run_id"))

    def drift(self) -> list:
        """What moved since capture. Non-empty means scores in this run are not attributable."""
        moved = []
        now = RunIdentity.capture(model_ids=self.artifacts, case_dirs=(), ruler_files=())
        for model_id, pinned in self.artifacts.items():
            current = now.artifacts.get(model_id, {})
            if pinned.get("present") and not current.get("present"):
                moved.append(f"artifact {model_id} 已不在库中")
                continue
            for kind in ("model", "template", "system"):
                if pinned.get(kind) and current.get(kind) and pinned[kind] != current[kind]:
                    moved.append(f"{model_id} 的 {kind} 层从 {pinned[kind][7:19]} 变成 "
                                 f"{current[kind][7:19]}")
        for rel, digest in self.ruler.items():
            path = ROOT / rel
            if not path.exists():
                moved.append(f"判分器 {rel} 已缺失（证据缺失，判红）")
                continue
            current = sha256_file(path)
            if current != digest:
                moved.append(f"判分器 {rel} 已被改动（{digest[:12]} -> {current[:12]}）")
        for key, digest in self.cases.items():
            candidate = ROOT / key
            if candidate.is_file():
                paths = [candidate]
            else:
                # Legacy identity.json files keyed cases by bare filename.
                paths = sorted(
                    p for p in (ROOT / "data" / "benchmark").rglob(Path(key).name)
                    if p.is_file()
                )
            if not paths:
                moved.append(f"用例集 {key} 已不存在（证据缺失，判红）")
                continue
            if len(paths) > 1:
                # Ambiguous name: only content can settle it. If the captured
                # digest is still present among the candidates, nothing moved.
                if digest not in {sha256_file(p) for p in paths}:
                    moved.append(
                        f"用例集 {key} 有 {len(paths)} 个同名文件且无匹配内容，身份不唯一（判红）"
                    )
                continue
            if sha256_file(paths[0]) != digest:
                moved.append(f"用例集 {key} 已被改动")
        return moved


class Metric:
    """One published number, with what it is and where it came from."""

    def __init__(self, name, value, basis="measured", n=0, evidence=None, run_id=None,
                 note="", planned=None):
        if basis not in BASIS:
            raise ValueError(f"basis must be one of {BASIS}, got {basis!r}")
        self.planned = planned
        self.name = name
        self.value = value
        self.basis = basis
        self.n = n
        self.evidence = evidence
        self.run_id = run_id
        self.note = note

    def check(self) -> None:
        if self.value is None:
            raise ValueError(f"{self.name}: 值为空，不得作为分数发布（写『未测』而不是 null）")
        if self.basis not in ("measured", "partial"):
            return
        if self.basis == "measured" and self.planned is not None and self.n < self.planned:
            raise ValueError(f"{self.name}: 计划 {self.planned} 条只答到 {self.n} 条，"
                             f"不得按实测发布（用 basis=partial 显式承认覆盖不全）")
        if not self.evidence or not Path(self.evidence).exists():
            raise ValueError(f"{self.name}: 声称实测却无证据文件 {self.evidence!r}")
        if not self.n:
            raise ValueError(f"{self.name}: 声称实测却没报样本量 n")
        if not self.run_id:
            raise ValueError(f"{self.name}: 声称实测却没带 run_id，无法核对被测字节")

    def as_row(self):
        self.check()
        label = {"measured": "实测", "partial": "部分覆盖", "asserted": "断言(未测)",
                 "inferred": "外推"}[self.basis]
        if self.planned is not None and self.planned != self.n:
            label = f"{label} {self.n}/{self.planned}"
        return (self.name, self.value, label, self.n,
                os.path.basename(str(self.evidence)) if self.evidence else "-",
                self.run_id or "-", self.note)


def seal_leg(leg_dir, owner: str = "") -> dict:
    """Freeze a leg's evidence so a later rewrite is detectable instead of silent.

    Measured 2026-11-05: a leg whose 30 toolcall records were `http_404` at 10:0x came back
    at 11:0x with 210 unique rows, zero transport errors and a scored toolcall dimension -
    somebody replaced the file. Without a seal there is no way to tell a re-run from a rewrite.
    """
    leg_dir = Path(leg_dir)
    raw = leg_dir / "raw.jsonl"
    if not raw.exists():
        raise ValueError(f"{leg_dir}: 无 raw.jsonl，无从封缄")
    doc = {"raw_sha256": sha256_file(raw), "rows": sum(1 for l in raw.read_text(
        encoding="utf-8-sig").splitlines() if l.strip()), "sealed_at": time.strftime(
        "%Y-%m-%dT%H:%M:%S"), "owner": owner}
    tmp = leg_dir / "_seal.json.tmp"
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, leg_dir / "_seal.json")
    return doc


def verify_seal(leg_dir) -> dict:
    """Raise unless the leg dir carries a seal that still matches its bytes."""
    leg_dir = Path(leg_dir)
    seal_path = leg_dir / "_seal.json"
    raw = leg_dir / "raw.jsonl"
    if not seal_path.exists():
        raise ValueError(f"{leg_dir.name}: 未封缄，不得发布（谁写的、写完有没有人动过，都无从证明）")
    if not raw.exists():
        raise ValueError(f"{leg_dir.name}: 封缄了却没有证据文件")
    seal = json.loads(seal_path.read_text(encoding="utf-8"))
    current = sha256_file(raw)
    if current != seal["raw_sha256"]:
        raise ValueError(f"{leg_dir.name}: 证据在封缄后被改写（{seal['raw_sha256'][:12]} -> "
                         f"{current[:12]}），本腿分数作废")
    rows = sum(1 for l in raw.read_text(encoding="utf-8-sig").splitlines() if l.strip())
    if rows != seal["rows"]:
        raise ValueError(f"{leg_dir.name}: 行数从 {seal['rows']} 变成 {rows}（追加也是改写）")
    return seal


def metrics_from_raw(raw_path, run_id=None, transport_limit=0.05, planned=None,
                     require_row_identity=False, planned_by_dim=None) -> list:
    """Turn a leg's ``raw.jsonl`` into publishable metrics, refusing a broken run.

    This is the check that would have stopped a 56-record arm made entirely of ``http_404``
    from being recorded as ``completed``: the records exist, the model was never asked.
    """
    raw_path = Path(raw_path)
    if not raw_path.exists():
        raise ValueError(f"无证据文件：{raw_path}")
    latest, transport, total = {}, 0, 0
    for line in raw_path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        total += 1
        # A retried case appends, so the last attempt is the answer; counting the earlier
        # transport failure as well would double-score one case.
        key = record.get("case_id") or f"__line{total}"
        latest[key] = record
    buckets = {}
    for record in latest.values():
        if record.get("verdict") in ("transport_error", "dry_run", "empty_response"):
            transport += 1
            continue
        if not isinstance(record.get("score"), (int, float)):
            continue
        buckets.setdefault(record.get("dimension", "?"), []).append(float(record["score"]))
    if not total:
        raise ValueError(f"{raw_path.name}: 零条记录，无分可发")
    if require_row_identity:
        # Since 2026-11-05 an Ollama arm stamps every response with the layer digests that
        # served it. Rows without that stamp cannot be attributed to a byte-identical
        # artifact - tags on this box get re-pointed - so they are evidence, not scores.
        missing = [r.get("case_id") for r in latest.values()
                   if isinstance(r.get("score"), (int, float))
                   and not (r.get("gen") or {}).get("served_layers")]
        if missing:
            raise ValueError(f"{raw_path.parent.name}: {len(missing)} 条记录无 per-row 身份取证"
                             f"（{missing[0]} 等），不得作为本轮实测发布")
    if planned is not None and len(latest) > planned:
        raise ValueError(f"{raw_path.parent.name}: 唯一用例数 {len(latest)} 超过计划 {planned}，"
                         f"这份证据被外部加写过")
    if (planned is not None and planned_by_dim is None
            and len(latest) < planned):
        raise ValueError(f"{raw_path.parent.name}: 只有 {len(latest)}/{planned} 条，覆盖不全，"
                         f"不得当作该维度的分数发布")
    if transport / len(latest) > transport_limit:
        raise ValueError(f"{raw_path.parent.name}: {transport}/{len(latest)} 条从未被模型答到，"
                         f"本轮无分数可发布（先修传输/构件身份再重跑）")
    metrics = []
    for dim, v in sorted(buckets.items()):
        want = (planned_by_dim or {}).get(dim)
        basis = "measured"
        if want is not None and len(v) < want:
            basis = "partial"
        metrics.append(Metric(dim, round(sum(v) / len(v), 2), basis, len(v), str(raw_path),
                              run_id, planned=want))
    return metrics


def render_table(metrics, header=("指标", "值", "口径", "n", "证据", "run_id", "备注")) -> str:
    """The only allowed way to print metrics; raises on the first unprovable one."""
    rows = []
    for metric in metrics:
        rows.append(metric.as_row())
    widths = [max(len(str(r[i])) for r in (header, *rows)) for i in range(len(header))]
    out = [" | ".join(str(h).ljust(w) for h, w in zip(header, widths)),
           "-+-".join("-" * w for w in widths)]
    out += [" | ".join(str(c).ljust(w) for c, w in zip(row, widths)) for row in rows]
    return "\n".join(out)


MIN_PROBE_PAIRS = 8          # sigma from fewer paired repeats is a guess, not a measurement
TRUNC_CONFOUND_RATE = 0.10   # >=3 cases per 30 of asymmetric budget-truncation


def noise_envelope(probe_path) -> dict:
    """Measured run-to-run spread of the ruler, from paired temperature=0 re-asks.

    Same model, same prompt, same seed, asked twice; the paired score deltas say how far the
    ruler itself moves. Without this, every per-dimension difference between two arms is
    indistinguishable from that spread, so ``delta_verdict`` refuses to call anything a gain.
    """
    recs = json.loads(Path(probe_path).read_text(encoding="utf-8"))
    if isinstance(recs, dict):
        recs = recs.get("records") or recs.get("probes") or []
    pairs = [r for r in recs if len(r.get("scores") or []) == 2]
    if len(pairs) < MIN_PROBE_PAIRS:
        raise ValueError(f"{probe_path}: 只有 {len(pairs)} 对复测（需 ≥{MIN_PROBE_PAIRS}），"
                         f"噪声底线未测，任何两臂差值都不得称为增益")
    deltas = [abs(float(r["scores"][0]) - float(r["scores"][1])) for r in pairs]
    sigma = statistics.stdev(deltas)
    dims = sorted({str(r.get("case_id", "")).rsplit("-", 1)[0] for r in pairs})
    return {"paired_sigma": round(sigma, 2), "n_pairs": len(pairs), "dims": dims,
            "p_score_changed": round(sum(1 for d in deltas if d > 0) / len(deltas), 4),
            "max_paired_delta": round(max(deltas), 2), "evidence": str(probe_path)}


def delta_verdict(delta, *, n_cases: int, sigma: float,
                  trunc_a: int = 0, trunc_b: int = 0, z: float = 1.96) -> dict:
    """Is an A-B per-dimension delta attributable? Directional, because truncation is.

    A budget-truncated case can only lose points, so the arm that truncated more is depressed.
    That makes a delta in its *disfavour* conservative (it lost anyway) and a delta in its
    *favour* unattributable (the gap may be nothing but the token ceiling).
    """
    if n_cases < 1:
        raise ValueError(f"n_cases={n_cases}，没有样本就没有差值可判")
    band = z * sigma * math.sqrt(2.0 / n_cases)
    rate_a, rate_b = trunc_a / n_cases, trunc_b / n_cases
    gap = abs(rate_a - rate_b)
    out = {"delta": round(delta, 2), "band": round(band, 2), "n": n_cases,
           "trunc_rate_a": round(rate_a, 3), "trunc_rate_b": round(rate_b, 3)}
    if abs(delta) <= band:
        out.update(verdict="噪声内", why=f"|Δ|={abs(delta):.2f} ≤ 95% 带 {band:.2f}"
                                       f"（σ={sigma}，n={n_cases}），与复测散布不可分")
        return out
    favours = (rate_a > rate_b and delta < 0) or (rate_b > rate_a and delta > 0)
    if gap >= TRUNC_CONFOUND_RATE and not favours:
        depressed = "B" if rate_b > rate_a else "A"
        out.update(verdict="截断混淆", why=f"{depressed} 侧截断 {max(rate_a, rate_b):.0%} vs "
                                          f"{min(rate_a, rate_b):.0%}，被压低的一方恰好是输的一方，"
                                          f"差值可能只是 token 上限")
        return out
    out.update(verdict="净正增益" if delta > 0 else "净负增益",
               why=f"|Δ|={abs(delta):.2f} > 95% 带 {band:.2f}"
                   + (f"，且截断不对称（{gap:.0%}）偏向本结论方向，属保守判定" if favours else
                      f"，两臂截断率差 {gap:.0%} 不足以解释"))
    return out


def _iso(value):
    try:
        return datetime.datetime.fromisoformat(str(value))
    except ValueError:
        return None


def sentinel_coverage(ticks_path, drift_log_path, leg_start, leg_end, poll_s: int = 60) -> dict:
    """Was the drift sentinel actually watching during this leg, or just not complaining?

    ``layer_moved`` silence is only evidence if the watcher is provably alive, so the watchdog
    appends one tick per poll to ``sentinel_ticks.jsonl``. Absent ticks fall back to the
    ``watch_start``/``watch_end`` pair, which brackets the window but cannot prove it stayed up
    - that publishes as ``partial``, never ``measured``. A pid change or a gap wider than
    3 polls is a blind spot inside the leg and voids the leg.
    """
    start, end = _iso(leg_start), _iso(leg_end)
    if start is None or end is None:
        raise ValueError(f"腿窗口时间戳无法解析（{leg_start} / {leg_end}），覆盖判定一律不放行")
    ticks = []
    if Path(ticks_path).exists():
        with open(ticks_path, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    return {"status": "none", "ticks": 0,
                            "why": f"{ticks_path} 有残缺行，哨兵账本不可信（解析失败判红）"}
                at = _iso(rec.get("at"))
                if at:
                    ticks.append((at, rec.get("pid")))
    inside = sorted(t for t, _ in ticks if start <= t <= end)
    pids = {p for _, p in ticks}
    if inside:
        if len(pids) > 1:
            return {"status": "gapped", "ticks": len(inside),
                    "why": f"腿窗口内哨兵换过进程（{sorted(pids)}），重启期间的漂移无人记录"}
        gaps = [(b - a).total_seconds() for a, b in zip(inside, inside[1:])]
        worst = max(gaps) if gaps else poll_s
        if worst > 3 * poll_s:
            return {"status": "gapped", "ticks": len(inside),
                    "why": f"哨兵心跳最大空档 {worst:.0f}s > {3 * poll_s}s，窗口内有盲区"}
        return {"status": "full", "ticks": len(inside), "why": "逐拍心跳覆盖整条腿"}
    starts, ends = [], []
    if Path(drift_log_path).exists():
        with open(drift_log_path, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    return {"status": "none", "ticks": 0,
                            "why": f"{drift_log_path} 有残缺行，哨兵账本不可信（解析失败判红）"}
                at = _iso(rec.get("at"))
                if not at:
                    continue
                if rec.get("event") == "watch_start":
                    starts.append(at)
                elif rec.get("event") == "watch_end":
                    ends.append(at)
    lo = max([s for s in starts if s <= end], default=None)
    hi = min([e for e in ends if e >= start], default=None)
    if not lo or not hi:
        return {"status": "none", "ticks": 0,
                "why": "该腿窗口没有任何哨兵证据，漂移未知，不得发布分数"}
    if lo > start or hi < end:
        blind = ((lo - start).total_seconds() if lo > start else 0) +                 ((end - hi).total_seconds() if hi < end else 0)
        return {"status": "partial", "ticks": 0,
                "why": f"哨兵只看着这段腿的 {100 * (1 - blind / max((end - start).total_seconds(), 1)):.0f}"
                       f"，另有 {blind / 60:.0f} 分钟无人观察且无逐拍心跳"}
    return {"status": "partial", "ticks": 0,
            "why": "哨兵声明在腿前启动、腿后停止，但没有逐拍心跳，无法证明其间一直醒着"}
