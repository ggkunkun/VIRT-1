#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/align_toolcall_corpus.py — Transform legacy toolcall corpora to canonical deployed schema.

Aligns the 8 legacy training tool schemas with the 10 deployed `cadcam_*` tools
from `cadcam_toolchain_manifest.json`.
"""

import os
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def load_canonical_tools():
    manifest_path = ROOT / "cadcam_toolchain_manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("tools", [])

def convert_tool_call(tc):
    fn = tc.get("function", {})
    name = fn.get("name", "")
    args_raw = fn.get("arguments", "{}")
    if isinstance(args_raw, str):
        try:
            args = json.loads(args_raw)
        except Exception:
            args = {}
    else:
        args = args_raw or {}

    new_name = name
    new_args = args

    if name == "solidworks.create_parametric_part":
        new_name = "cadcam_solidworks_model"
        new_args = {
            "action": "create_parametric_part",
            "part_name": args.get("part_name", "part_parametric"),
            "dimensions": args.get("spec", args.get("dimensions", {})),
            "vba_code": args.get("vba_code", "")
        }
    elif name == "nx.create_nxopen_script":
        new_name = "cadcam_nx_journal"
        new_args = {
            "action": "create_parametric_model",
            "part_name": args.get("part_name", "nx_part"),
            "expressions": args.get("spec", args.get("expressions", {}))
        }
    elif name == "autocad.create_autolisp":
        new_name = "cadcam_autocad_draw"
        new_args = {
            "action": "send_lisp",
            "code": args.get("code", ";; AutoLISP Generated\n(princ)"),
            "drawing_name": args.get("drawing_name", "drawing")
        }
    elif name == "cimco.create_macro_b":
        new_name = "cadcam_cimco_validate"
        new_args = {
            "action": "validate_macro",
            "code": args.get("code", args.get("macro_code", "G00 X0\nM30"))
        }
    elif name == "vericut.create_project_config":
        new_name = "cadcam_vericut_simulate"
        new_args = {
            "action": "run_simulation",
            "project_path": args.get("project_path", "simulation.vcproj")
        }
    elif name == "sscnc.create_setup_guide":
        new_name = "cadcam_sscnc_control"
        new_args = {
            "action": "calculate_offsets",
            "tools": args.get("tools", [])
        }
    elif name == "cad.parse_wish_intent":
        new_name = "cadcam_run_full_chain"
        new_args = {
            "wish": args.get("wish", args.get("intent", ""))
        }
    elif name == "ontology.lookup_plugin":
        new_name = "cadcam_preflight"
        new_args = {}

    return {
        "id": tc.get("id", "call_0"),
        "type": "function",
        "function": {
            "name": new_name,
            "arguments": json.dumps(new_args, ensure_ascii=False)
        }
    }

def process_file(src_path: Path, dst_path: Path, canonical_tools: list):
    count = 0
    with open(src_path, "r", encoding="utf-8") as fin, open(dst_path, "w", encoding="utf-8") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue

            rec["tools"] = canonical_tools
            msgs = rec.get("messages", [])
            for m in msgs:
                if "tool_calls" in m:
                    m["tool_calls"] = [convert_tool_call(tc) for tc in m["tool_calls"]]

            fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
            count += 1
    return count

def main():
    tools = load_canonical_tools()
    print(f"Loaded {len(tools)} canonical deployed tools.")

    src = ROOT / "data" / "toolcall_pilot_2000.jsonl"
    dst = ROOT / "data" / "train" / "virtu_toolcall_train_aligned.jsonl"
    dst.parent.mkdir(parents=True, exist_ok=True)

    if src.exists():
        n = process_file(src, dst, tools)
        print(f"Successfully processed {n} aligned samples -> {dst}")
    else:
        print(f"Source file not found: {src}")

if __name__ == "__main__":
    main()
