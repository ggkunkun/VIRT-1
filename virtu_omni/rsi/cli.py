"""CLI for bounded experiments and explicit, fingerprint-bound human review."""

from __future__ import annotations

import argparse
import json
from dataclasses import fields
from pathlib import Path

from .approval import infer, review
from .contracts import Config, RSIError, inside
from .engine import run
from .storage import RunStore


ROOT = Path(__file__).resolve().parents[2]


def parser():
    p = argparse.ArgumentParser(description="Virtu approval-gated RSI; never changes weights or production routing")
    sub = p.add_subparsers(dest="command", required=True)
    run_p = sub.add_parser("run", help="dev-only recursive proposals followed by one-shot independent validation")
    run_p.add_argument("--config", help="project-local JSON config; CLI values override it")
    run_p.add_argument("--case-dir")
    run_p.add_argument("--dims", help="comma-separated dimensions; default physics")
    run_p.add_argument("--model-id")
    run_p.add_argument("--base-url")
    for name in ("rounds", "limit", "seed", "min_validation", "max_calls", "max_seconds", "timeout",
                 "max_tokens", "proposal_tokens", "synthetic_per_task", "plateau_rounds"):
        run_p.add_argument("--" + name.replace("_", "-"), type=int)
    for name in ("validation_fraction", "min_gain"):
        run_p.add_argument("--" + name.replace("_", "-"), type=float)
    inspect_p = sub.add_parser("inspect", help="read-only run evidence and integrity check")
    inspect_p.add_argument("--run", required=True)
    review_p = sub.add_parser("review", aliases=["approve"], help="record an explicit human decision; no deployment")
    review_p.add_argument("--run", required=True)
    review_p.add_argument("--reviewer", required=True)
    review_p.add_argument("--decision", choices=("approve", "reject"), required=True)
    review_p.add_argument("--candidate-sha256", required=True)
    review_p.add_argument("--review-sha256", required=True)
    infer_p = sub.add_parser("infer", help="isolated local inference with a previously approved strategy")
    infer_p.add_argument("--run", required=True)
    infer_p.add_argument("--prompt", required=True)
    infer_p.add_argument("--system", default="")
    return p


def config_from(args, root):
    values = {}
    if args.config:
        with inside(root, args.config).open(encoding="utf-8") as fh:
            values = json.load(fh)
        if not isinstance(values, dict) or set(values) - {f.name for f in fields(Config)}:
            raise RSIError("Config contains unknown fields or is not an object")
    for field in fields(Config):
        value = getattr(args, field.name, None)
        if value is not None:
            values[field.name] = value
    if args.dims is not None:
        values["dimensions"] = tuple(d.strip() for d in args.dims.split(",") if d.strip())
    if "dimensions" in values:
        values["dimensions"] = tuple(values["dimensions"])
    return Config(**values)


def inspect(root, path):
    store = RunStore(root, path)
    evidence = store.verify()
    receipt = json.loads(store.target("receipt.json").read_text(encoding="utf-8"))
    approval_path = store.target("approval.json")
    return {**receipt, "integrity_verified": True, "review_sha256": evidence["review_sha256"],
            "human_decision": json.loads(approval_path.read_text(encoding="utf-8"))
            if approval_path.exists() else None}


def main(argv=None, root=ROOT):
    args = parser().parse_args(argv)
    root = Path(root).resolve()
    try:
        if args.command == "run":
            result = run(root, config_from(args, root))
            code = 3 if result["status"] == "blocked" else 0
        elif args.command == "inspect":
            result, code = inspect(root, args.run), 0
        elif args.command in ("review", "approve"):
            result = review(root, args.run, args.reviewer, args.decision,
                            args.candidate_sha256, args.review_sha256)
            code = 0
        else:
            result = infer(root, args.run, args.prompt, args.system)
            code = 3 if result["generation"].get("error") else 0
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), flush=True)
        return code
    except (RSIError, OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({"status": "refused", "error": str(exc), "weights_updated": False},
                         ensure_ascii=False), flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
