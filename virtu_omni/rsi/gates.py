"""Paired independent validation gates; fail closed on incomplete evidence."""

from __future__ import annotations

from .evaluation import CRITICAL_TYPES, summarize


BAD_VERDICTS = {"transport_error", "grader_error", "empty_response", "truncated",
                "dry_run", "recorded_replay"}


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
    if not improvements:
        reasons.append("no paired improvement")
    if regressions > config.max_regressions:
        reasons.append(f"paired regressions: {regressions} > {config.max_regressions}")
    b_summary, c_summary = summarize(baseline), summarize(candidate)
    for dimension, before in b_summary["dimensions"].items():
        after = c_summary["dimensions"].get(dimension)
        if after is None or after + config.max_dimension_regression + 1e-8 < before:
            reasons.append(f"dimension regression: {dimension}")
    return {"eligible": not reasons, "reasons": sorted(set(reasons)),
            "candidate_sha256": candidate_sha256,
            "baseline": b_summary, "candidate": c_summary,
            "mean_gain": mean_gain, "paired_improvements": improvements,
            "paired_regressions": regressions, "validation_ids": sorted(expected),
            "scope": "sampled text/physical tasks; not weight improvement or production acceptance"}
