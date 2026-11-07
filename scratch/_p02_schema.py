"""Derive the routing response schema from the *authoritative* tool contract.

Rule (AGENTS.md §8.5, one law one reference): the schema must come from
``virtu_eval/arms.json`` -- the same definition the bridge dispatches on -- never
from a case's ``gold`` answer. Fitting the schema to gold would be training on the
test set and would make the A/B unfalsifiable.

Only the tools a case's own system prompt advertises are enumerated, because a
constrained decoder that forbids a tool the prompt offers is a contradiction, not
a measurement.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def advertised_tools(case_path):
    names = set()
    for line in open(case_path, encoding="utf-8"):
        if line.strip():
            names.update(re.findall(r"cadcam_\w+", json.loads(line).get("system") or ""))
    return names


def build_schema(tool_names, arms_path=None):
    arms_path = arms_path or os.path.join(ROOT, "virtu_eval", "arms.json")
    doc = json.load(open(arms_path, encoding="utf-8"))
    tools = {t["function"]["name"]: t["function"] for t in doc["comprehensive"]["tools"]}

    branches = []
    for name in sorted(tool_names):
        fn = tools.get(name)
        if fn is None:
            raise KeyError(f"tool {name!r} advertised by cases but absent from arms.json")
        params = fn.get("parameters") or {}
        props = params.get("properties") or {}
        # A parameter typed only as a bare object (e.g. cae ``spec``) is left
        # unconstrained on purpose: inventing a shape the contract never stated
        # would be a new specification, not a transcription of the existing one.
        clean = {}
        for key, spec in props.items():
            clean[key] = spec if isinstance(spec, dict) else {"type": "string"}
            if clean[key].get("type") == "object" and not clean[key].get("properties"):
                clean[key] = {"type": "object"}
        arg_schema = {"type": "object", "properties": clean,
                      "required": list(params.get("required") or [])}
        branches.append({
            "type": "object",
            "properties": {"tool": {"const": name}, "arguments": arg_schema},
            "required": ["tool", "arguments"],
        })

    return {
        "type": "object",
        "properties": {
            "tool": {"type": "string", "enum": sorted(tool_names)},
            "arguments": {"type": "object"},
        },
        "required": ["tool", "arguments"],
        "oneOf": branches,
    }


def schema_digest(schema):
    blob = json.dumps(schema, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def main():
    case_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        ROOT, "data", "benchmark", "virtu_eval_cl_v1", "toolrouting.jsonl")
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        ROOT, "scratch", "_p02_routing_schema.json")

    names = advertised_tools(case_path)
    schema = build_schema(names)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(schema, f, ensure_ascii=False, indent=1)
    size = os.path.getsize(out)
    print(f"tools advertised : {len(names)} -> {sorted(names)}")
    print(f"oneOf branches   : {len(schema['oneOf'])}")
    print(f"schema sha256[:16]: {schema_digest(schema)}")
    print(f"bytes            : {size}  -> {out}")


if __name__ == "__main__":
    main()
