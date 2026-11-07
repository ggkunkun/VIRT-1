"""Audit: do the tool-call training corpora teach the tools that are actually deployed?

A model that learned tool calling perfectly still fails in production if the
schema it was trained on is not the schema the dispatcher accepts.  This
compares, tool by tool:

  * the tool names the training corpora expose in their ``tools`` blocks
  * the tool names the deployed manifest exposes
  * the parameter names each side uses for the same physical operation
  * the shape of the assistant turn (is it a real ``tool_calls`` object with a
    JSON-encoded ``arguments`` string, or free text?)
"""

from __future__ import annotations

import collections
import io
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CORPORA = [
    "data/train/virtu_toolcall_train_aligned.jsonl",
    "data/toolcall_optimal.jsonl",
    "data/toolcall_slim.jsonl",
    "data/toolcall_pilot_2000.jsonl",
    "data/train/virtu_toolcall_train_final.jsonl",
    "data/virtu_drawing_to_machining_chain_train.jsonl",
]
MANIFEST = "cadcam_toolchain_manifest.json"


def norm(name):
    """Compare tool identity modulo the naming convention.

    ``solidworks.create_parametric_part`` and ``cadcam_solidworks_model`` are
    different names for the same vendor/capability, so the audit reports both
    the literal overlap and a normalised overlap.
    """
    n = name.lower().replace("_", "").replace(".", "")
    for vendor in ("solidworks", "sw", "nx", "siemensnx", "autocad", "acad",
                   "vericut", "cimco", "sscnc", "siemens"):
        if vendor in n:
            n = n.replace(vendor, "")
    for verb in ("create", "model", "make", "build", "generate", "run",
                 "validate", "parse", "simulate", "control", "draw", "journal"):
        n = n.replace(verb, "")
    return n


def tool_names(rec):
    out = []
    for t in rec.get("tools") or []:
        f = t.get("function") if isinstance(t, dict) else None
        if isinstance(f, dict) and f.get("name"):
            out.append(f["name"])
        elif isinstance(t, dict) and t.get("name"):
            out.append(t["name"])
    return out


def main():
    manifest_path = os.path.join(ROOT, MANIFEST)
    deployed = []
    if os.path.exists(manifest_path):
        with open(manifest_path, encoding="utf-8") as f:
            for t in json.load(f).get("tools", []):
                fn = t.get("function", t)
                props = (fn.get("parameters") or {}).get("properties", {})
                deployed.append({
                    "name": fn.get("name"),
                    "params": sorted(props),
                    "actions": (props.get("action") or {}).get("enum"),
                })

    report = {"deployed_tools": deployed, "corpora": {}}
    out_lines = []

    for rel in CORPORA:
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            continue
        names = collections.Counter()
        n = 0
        assistant_shapes = collections.Counter()
        arg_types = collections.Counter()
        param_names = collections.defaultdict(set)
        with io.open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:  # noqa: BLE001
                    continue
                n += 1
                for nm in tool_names(rec):
                    names[nm] += 1
                    props = {}
                    for t in rec.get("tools") or []:
                        fn = t.get("function") if isinstance(t, dict) else None
                        if isinstance(fn, dict) and fn.get("name") == nm:
                            props = (fn.get("parameters") or {}).get("properties", {})
                            break
                    param_names[nm].update(props)
                for m in rec.get("messages") or []:
                    if m.get("role") != "assistant":
                        continue
                    tcs = m.get("tool_calls")
                    if not tcs:
                        assistant_shapes["plain_text"] += 1
                        continue
                    assistant_shapes["tool_calls"] += 1
                    for tc in tcs:
                        fn = tc.get("function") or {}
                        a = fn.get("arguments")
                        arg_types[type(a).__name__] += 1
                        if isinstance(a, str):
                            try:
                                json.loads(a)
                            except Exception:  # noqa: BLE001
                                arg_types["arguments_not_json_string"] += 1
        report["corpora"][rel] = {
            "records": n,
            "tool_names": dict(names),
            "assistant_turn_shape": dict(assistant_shapes),
            "arguments_type": dict(arg_types),
            "params_by_tool": {k: sorted(v) for k, v in param_names.items()},
        }
        out_lines.append(f"### {rel}: {n} records")
        out_lines.append(f"    assistant turns: {dict(assistant_shapes)}")
        out_lines.append(f"    arguments type: {dict(arg_types)}")
        out_lines.append(f"    tools taught: {dict(names)}")
        out_lines.append("")

    out_lines.append("### deployed manifest")
    for d in deployed:
        out_lines.append(f"    {d['name']}: params={d['params']} actions={d['actions']}")
    out_lines.append("")

    # overlap
    deployed_names = {d["name"] for d in deployed}
    deployed_norm = {norm(n) for n in deployed_names}
    for rel, info in report["corpora"].items():
        taught = set(info["tool_names"])
        literal = taught & deployed_names
        normalised = {n for n in taught if norm(n) in deployed_norm}
        out_lines.append(f"### overlap for {rel}")
        out_lines.append(f"    literal overlap      : {sorted(literal) or 'NONE'}")
        out_lines.append(f"    capability overlap   : {len(normalised)}/{len(taught)} taught tools map to a deployed capability")
        out_lines.append(f"    tools with NO deployed counterpart: "
                         f"{sorted(n for n in taught if norm(n) not in deployed_norm)[:12]}")
        out_lines.append("")

    report["overlap"] = {}
    for rel, info in report["corpora"].items():
        taught = set(info["tool_names"])
        report["overlap"][rel] = {
            "literal": sorted(taught & deployed_names),
            "capability_mapped": sorted(n for n in taught if norm(n) in deployed_norm),
            "taught_only": sorted(n for n in taught if norm(n) not in deployed_norm),
        }

    path = os.path.join(ROOT, "benchmarks", "toolcall_schema_audit.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    text_path = os.path.join(ROOT, "benchmarks", "toolcall_schema_audit.txt")
    with io.open(text_path, "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines))
    print("wrote", path)
    print("wrote", text_path)


if __name__ == "__main__":
    main()
