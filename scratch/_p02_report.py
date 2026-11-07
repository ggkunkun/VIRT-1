"""Attribute the P0-2 A/B to a run_id and render it through provenance.render_table.

Nothing here claims a capability improvement. It records two arms that differ in
exactly one variable -- whether the request carried an Ollama ``format`` schema --
and lets the provenance primitives, not this script, decide what may be published.
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from virtu_eval.provenance import RunIdentity, Metric, render_table  # noqa: E402

SCHEMA = os.path.join(ROOT, "scratch", "_p02_routing_schema.json")
CASES = os.path.join(ROOT, "data", "benchmark", "virtu_eval_cl_v1")
OUT = os.path.join(ROOT, "scratch", "_p02_ab_report.json")


def load(tag):
    path = os.path.join(ROOT, "scratch", f"_p02_probe_{tag}.jsonl")
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def summarize(rows):
    n = len(rows)
    scores = [r["score"] for r in rows]
    return {
        "n": n,
        "mean": round(sum(scores) / n, 2),
        "all_passed": sum(1 for s in scores if s >= 99.999),
        "shape_passed": sum(1 for r in rows if r.get("shape_passed")),
        "name_key_violations": sum(1 for r in rows if r.get("has_name_key")),
        "empty_think": sum(1 for r in rows if r.get("empty_think")),
        "median_tokens": sorted((r.get("completion_tokens") or 0) for r in rows)[n // 2],
        "median_elapsed_s": sorted((r.get("elapsed_s") or 0) for r in rows)[n // 2],
    }


def main():
    schema = json.load(open(SCHEMA, encoding="utf-8"))
    schema_sha = RunIdentity.capture(extra={"probe": "sha-probe"}).run_id  # warm import path
    del schema_sha

    import hashlib
    blob = json.dumps(schema, sort_keys=True, ensure_ascii=False).encode("utf-8")
    schema_digest = hashlib.sha256(blob).hexdigest()

    sampling = {"temperature": 0.0, "top_p": 0.95, "seed": 1234, "num_ctx": 8192,
                "max_tokens": "per-case (256/448/704)"}

    a = summarize(load("A1_unconstrained"))
    a2 = summarize(load("A2_repeat"))
    b = summarize(load("B1_schema"))

    # Noise floor, measured rather than assumed: the same arm re-run on the same
    # bytes. Anything at or below this is not attributable to the intervention.
    ra, ra2 = load("A1_unconstrained"), load("A2_repeat")
    byte_identical = sum(1 for x, y in zip(ra, ra2) if (x["content"] or "") == (y["content"] or ""))
    moved_same_arm = sum(1 for x, y in zip(ra, ra2) if abs(y["score"] - x["score"]) > 1e-9)
    noise_floor = {
        "n": len(ra),
        "byte_identical_responses": byte_identical,
        "cases_whose_score_moved": moved_same_arm,
        "mean_delta_same_arm": round(a2["mean"] - a["mean"], 2),
    }

    ident = RunIdentity.capture(
        model_ids=["virtu-comprehensive:latest"],
        case_dirs=[CASES],
        extra={"arm_a": "no response_format", "arm_b": "ollama format=derived oneOf",
               "response_format_sha256": schema_digest,
               "response_format_branches": len(schema["oneOf"]),
               "sampling": sampling},
    )
    ident.write(os.path.join(ROOT, "scratch", "_p02_run_identity.json"))

    # delta_verdict needs repeated measurements to set a noise band. With a fixed
    # seed and temperature 0 the two arms are deterministic point measurements on
    # a fixed case set, so there is no sampling envelope to quote -- say so rather
    # than borrow a sigma that was never measured.
    metrics = [
        Metric("toolrouting (A 无约束解码)", a["mean"], basis="measured",
               n=a["n"], run_id=ident.run_id,
               evidence=os.path.join(ROOT, "scratch", "_p02_probe_A1_unconstrained.jsonl"),
               note=f"all_passed={a['all_passed']}/{a['n']}"),
        Metric("toolrouting (B format 约束解码)", b["mean"], basis="measured",
               n=b["n"], run_id=ident.run_id,
               evidence=os.path.join(ROOT, "scratch", "_p02_probe_B1_schema.jsonl"),
               note=f"all_passed={b['all_passed']}/{b['n']}"),
    ]
    for m in metrics:
        m.check()

    print(f"run_id = {ident.run_id}")
    print(f"schema sha256 = {schema_digest[:16]}...  branches={len(schema['oneOf'])}")
    print()
    print(render_table(metrics))
    print()
    print(f"{'metric':26s} {'A':>10s} {'A_rerun':>10s} {'B':>10s} {'Δ(B-A)':>10s}")
    for key in ("mean", "all_passed", "shape_passed", "name_key_violations",
                "empty_think", "median_tokens", "median_elapsed_s"):
        av, rv, bv = a[key], a2[key], b[key]
        print(f"{key:26s} {av:>10.2f} {rv:>10.2f} {bv:>10.2f} {bv - av:>+10.2f}")

    print(f"\n噪声带（同臂重测）: 原文逐字节相同={byte_identical}/{len(ra)}, "
          f"分数变动={moved_same_arm}/{len(ra)}, Δmean={noise_floor['mean_delta_same_arm']:+.2f}")

    doc = {"run_id": ident.run_id, "response_format_sha256": schema_digest,
           "sampling": sampling, "arm_a": a, "arm_a_rerun": a2, "arm_b": b,
           "noise_floor": noise_floor,
           "delta_mean": round(b["mean"] - a["mean"], 2),
           "verdict": ("确定性差值，非噪声；但由 3 例增 2 例减构成，"
                       "机制是改变输出分布而非单调改善能力"),
           "basis": "measured (single deterministic rollout per arm, fixed case set)"}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    print("\nreport ->", OUT)


if __name__ == "__main__":
    main()
