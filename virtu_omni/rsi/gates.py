"""Paired independent validation gates; fail closed on incomplete evidence."""

from __future__ import annotations

import math
import re

from .evaluation import CRITICAL_TYPES, summarize


BAD_VERDICTS = {"transport_error", "grader_error", "empty_response", "truncated",
                "dry_run", "recorded_replay"}

_HEX_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_SYNTHETIC_MARKER = re.compile(r"^(?:mock|fake|dummy|test|placeholder|synthetic)", re.I)


def identity_is_real(identity):
    """Whether a served artifact identity can be audited after the fact.

    A ``mock_*`` digest is legitimate inside a protocol test, but the moment one reaches a
    receipt it makes the run look like evidence of a real model improvement. So the identity
    is checked at the gate, not trusted from the caller.
    """
    if not isinstance(identity, dict):
        return False
    digest = str(identity.get("digest") or "")
    model_id = str(identity.get("model_id") or "")
    if not digest or _SYNTHETIC_MARKER.match(digest) or _SYNTHETIC_MARKER.match(model_id):
        return False
    if _HEX_DIGEST.match(digest):
        return True
    # Cloud runs have no ollama digest: the endpoint's own fingerprint stands in for it.
    return identity.get("kind") == "http_openai" and len(digest) >= 32


def validation_gate(baseline, candidate, expected_ids, config, candidate_sha256,
                    identity_valid=True, data_valid=True, fresh_validation=True):
    reasons = []
    expected = set(expected_ids)
    b = {r["case_id"]: r for r in baseline}
    c = {r["case_id"]: r for r in candidate}
    if len(b) != len(baseline) or len(c) != len(candidate):
        reasons.append("duplicate validation records")
    if set(b) != expected or set(c) != expected or not expected:
        reasons.append("incomplete paired validation coverage")
    if len(expected) < config.min_validation:
        reasons.append(f"validation too small: {len(expected)} < {config.min_validation}")
    if not candidate_sha256:
        reasons.append("no candidate was selected on development data")
    if not identity_valid:
        reasons.append("model/source identity mismatch")
    if not data_valid:
        reasons.append("candidate data failed validation or contamination checks")
    if not fresh_validation:
        reasons.append("validation was already used by an earlier RSI run")
    # Fail closed when there is no measured resolution. sigma=0 used to mean "gate off", which
    # let a 12-case mock run report +83.3 points as a resolved gain.
    synthetic = bool(getattr(config, "synthetic_run", False))
    if not synthetic and config.noise_sigma <= 0:
        reasons.append("noise resolution gate not configured (noise_sigma<=0): "
                       "mean gain cannot be separated from sampling jitter")
    for label, records in (("baseline", baseline), ("candidate", candidate)):
        if any(r["verdict"] in BAD_VERDICTS for r in records):
            reasons.append(f"{label} contains transport/scoring/empty/truncated/synthetic failures")
    gains = []
    improvements = regressions = 0
    for cid in sorted(expected & set(b) & set(c)):
        before, after = b[cid], c[cid]
        if before["dimension"] != after["dimension"]:
            reasons.append("paired dimension mismatch")
        gain = after["score"] - before["score"]
        gains.append(gain)
        improvements += gain > 1e-8
        regressions += gain < -1e-8
        before_checks = {(v["key"], v["type"]) for v in before["criteria"]}
        after_checks = {(v["key"], v["type"]) for v in after["criteria"]}
        if not before_checks <= after_checks:
            reasons.append("candidate omitted evaluation criteria")
        if any(not check["passed"] for check in after["criteria"]
               if check["type"] in CRITICAL_TYPES or check["type"] == "strict_physics"):
            reasons.append("candidate failed a critical physical/safety criterion")
    mean_gain = round(sum(gains) / len(gains), 4) if gains else None
    if mean_gain is None or mean_gain < config.min_gain:
        reasons.append(f"mean validation gain below {config.min_gain}")
    # Resolution, not just direction: a paired mean gain smaller than the sampling band is
    # indistinguishable from jitter, so accepting it publishes noise as self-improvement.
    noise_band = None
    if config.noise_sigma > 0 and gains:
        noise_band = round(config.noise_z * config.noise_sigma / math.sqrt(len(gains)), 4)
        if mean_gain is None or mean_gain <= noise_band:
            reasons.append(f"mean validation gain {mean_gain} inside paired noise band "
                           f"+/-{noise_band}")
    if not improvements:
        reasons.append("no paired improvement")
    if regressions > config.max_regressions:
        reasons.append(f"paired regressions: {regressions} > {config.max_regressions}")
    b_summary, c_summary = summarize(baseline), summarize(candidate)
    for dimension, before in b_summary["dimensions"].items():
        after = c_summary["dimensions"].get(dimension)
        if after is None or after + config.max_dimension_regression + 1e-8 < before:
            reasons.append(f"dimension regression: {dimension}")
    # eligible  = the evidence set is internally consistent (protocol level).
    # certifiable = the number may be quoted outside this box: real served artifact, measured
    #               resolution, not a synthetic fixture. Approval keys off certifiable only.
    certifiable = (not reasons and bool(identity_valid) and not synthetic
                   and config.noise_sigma > 0)
    return {"eligible": not reasons, "reasons": sorted(set(reasons)),
            "certifiable": certifiable, "synthetic": synthetic,
            "identity_valid": bool(identity_valid),
            "candidate_sha256": candidate_sha256,
            "baseline": b_summary, "candidate": c_summary,
            "mean_gain": mean_gain, "paired_improvements": improvements,
            "paired_regressions": regressions, "validation_ids": sorted(expected),
            "paired_noise_band": noise_band, "noise_sigma": config.noise_sigma,
            "scope": "sampled text/physical tasks; not weight improvement or production acceptance"}
