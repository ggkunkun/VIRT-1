# -*- coding: utf-8 -*-
"""Convenient entry point for the traceable 240-case Virtu evaluation harness.

Examples:
    python virtu_eval.py --sample-per-tier easy=1,medium=1,hard=1
    python virtu_eval.py --dims reasoning,knowledge,toolcall
    python virtu_eval.py --arm ollama_qwen3_8b_base --out-dir runs/eval/qwen3_full

The runner stores every raw response and its per-criterion evidence. It never
turns transport failures or a zero-case selection into a successful score.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from virtu_eval import report, runner  # noqa: E402


def _parse_kv_spec(text):
    out = {}
    for part in (text or "").split(","):
        part = part.strip()
        if not part:
            continue
        key, sep, value = part.partition("=")
        if not sep:
            raise ValueError(f"Expected key=value, got {part!r}")
        out[key.strip()] = int(value)
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", default="bridge_deployed")
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--dims", default="")
    parser.add_argument("--tiers", default="")
    parser.add_argument("--limit-per-dim", type=int, default=0)
    parser.add_argument("--sample-per-tier", default="")
    parser.add_argument("--cap-by-tier", default="")
    parser.add_argument("--max-tokens-cap", type=int, default=0)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    arms_path = os.path.join(ROOT, "virtu_eval", "arms.json")
    with open(arms_path, encoding="utf-8") as stream:
        arms = json.load(stream)
    if args.arm not in arms:
        parser.error(f"unknown arm {args.arm!r}; available: {', '.join(arms)}")
    spec = dict(arms[args.arm])
    if spec.get("kind") == "http_openai" and not spec.get("api_key"):
        spec["api_key"] = (os.environ.get("VIRTU_EVAL_API_KEY")
                           or os.environ.get("VIRTU_API_KEY"))
        if not spec["api_key"]:
            from bridges.bridge_security import ensure_bridge_token
            spec["api_key"] = ensure_bridge_token()

    out_dir = args.out_dir or os.path.join("runs", "eval", args.arm + "_latest")
    out_abs = out_dir if os.path.isabs(out_dir) else os.path.join(ROOT, out_dir)
    raw = runner.run(
        os.path.join(ROOT, "data", "benchmark", "virtu_eval_v1"), spec, out_abs,
        dims=[x for x in args.dims.split(",") if x],
        tiers=[x for x in args.tiers.split(",") if x],
        limit_per_dim=args.limit_per_dim or None,
        sample_per_tier=_parse_kv_spec(args.sample_per_tier) or None,
        cap_by_tier=_parse_kv_spec(args.cap_by_tier) or None,
        temperature=args.temperature, seed=args.seed,
        max_tokens_cap=args.max_tokens_cap or None, dry=args.dry_run)
    if args.dry_run:
        print("Dry run:", raw)
        return 0

    manifest, records, malformed = report.load_run(out_abs)
    if not records:
        raise RuntimeError("Evaluation produced zero records; refusing to report success")
    gate = report.gate(manifest, records, malformed)
    stats = report.aggregate(records)
    payload = {"gate": gate, "arm": args.arm, "results": stats,
               "raw_jsonl": raw, "manifest": os.path.join(out_abs, "manifest.json")}
    result_path = os.path.join(out_abs, "results.json")
    with open(result_path, "w", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
    text_path = os.path.join(out_abs, "report.txt")
    with open(text_path, "w", encoding="utf-8") as stream:
        stream.write(f"Virtu evaluation: {args.arm}\n")
        stream.write(f"records={len(records)} valid={gate['valid']} "
                     f"transport_errors={gate['transport_errors']}\n")
        stream.write(f"overall_weighted={stats['overall_weighted']}\n")
        for dim, dim_stats in stats["dimensions"].items():
            stream.write(f"{dim}: score={dim_stats['score']} n={dim_stats['n_valid']} "
                         f"pass_rate={dim_stats['pass_rate']}\n")
        if gate["problems"]:
            stream.write("problems:\n- " + "\n- ".join(gate["problems"]) + "\n")
    print(json.dumps({"records": len(records), "valid": gate["valid"],
                      "overall_weighted": stats["overall_weighted"],
                      "results": result_path}, ensure_ascii=False))
    return 0 if gate["valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
