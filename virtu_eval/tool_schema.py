"""The tool surface, read from the runtime registry instead of being retyped per harness.

Two drift modes were measured on 2026-11-05:
  * `virtu_eval/arms.json` injects 10 `cadcam_*` schemas while `bridges/tool_calling_specs.py`
    registers 14, so the four newest capabilities (CAE 应力、钣金套料、极限链、通用几何)
    are invisible to any tool-call measurement.
  * the 240-case board routes only to those same 10 names - no gold, no criterion mentions
    the other four - so widening the schema without authoring cases would move the score
    for reasons the board cannot attribute.
"""
from __future__ import annotations

import ast
import json
import os
import re
from pathlib import Path

ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REGISTRY = ROOT / "bridges" / "tool_calling_specs.py"
VARIABLE = "CADCAM_TOOLS_DEFINITION"
BOARD_DIRS = (ROOT / "data" / "benchmark" / "virtu_eval_v1",
              ROOT / "data" / "benchmark" / "virtu_eval_cl_v1")


def runtime_tools(registry_path: Path = REGISTRY) -> list[dict]:
    """Read the registry literal with ast; importing the bridge would need COM and torch."""
    tree = ast.parse(Path(registry_path).read_text(encoding="utf-8"), filename=str(registry_path))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == VARIABLE for t in node.targets):
            value = ast.literal_eval(node.value)
            if not isinstance(value, list):
                raise ValueError(f"{VARIABLE} must be a list, got {type(value).__name__}")
            return value
    raise ValueError(f"{VARIABLE} not found at module level in {registry_path}")


def runtime_tool_names(registry_path: Path = REGISTRY) -> list[str]:
    return [t["function"]["name"] for t in runtime_tools(registry_path)]


def tool_contract(registry_path: Path = REGISTRY) -> dict:
    """name -> (required args, enum-valued args) for building routing criteria."""
    out = {}
    for tool in runtime_tools(registry_path):
        fn = tool["function"]
        params = fn.get("parameters") or {}
        props = params.get("properties") or {}
        out[fn["name"]] = {
            "required": list(params.get("required") or []),
            "enums": {k: list(v["enum"]) for k, v in props.items() if isinstance(v, dict) and "enum" in v},
            "types": {k: (v.get("type") if isinstance(v, dict) else None) for k, v in props.items()},
        }
    return out


def referenced_tool_names(case_dirs=BOARD_DIRS) -> set:
    """Tool names the board can actually grade: present in a gold answer or a criterion."""
    names = set()
    for case_dir in case_dirs:
        if not Path(case_dir).exists():
            continue
        for fname in sorted(os.listdir(case_dir)):
            if not fname.endswith(".jsonl"):
                continue
            with open(os.path.join(case_dir, fname), encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    rec = json.loads(line)
                    graded = json.dumps({"gold": rec.get("gold"),
                                         "criteria": rec.get("criteria")}, ensure_ascii=False)
                    names.update(re.findall(r"cadcam_[a-z_]+", graded))
    return {n for n in names if n.rstrip("_") in set(runtime_tool_names())}


def uncovered_runtime_tools(case_dirs=BOARD_DIRS) -> list[str]:
    graded = referenced_tool_names(case_dirs)
    return [name for name in runtime_tool_names() if name not in graded]


def eval_schema_tool_names(arms_config: Path = ROOT / "virtu_eval" / "arms.json") -> set:
    data = json.loads(Path(arms_config).read_text(encoding="utf-8"))
    names = set()
    for spec in data.values():
        for tool in (spec or {}).get("tools") or []:
            names.add(tool["function"]["name"])
    return names


if __name__ == "__main__":
    names = runtime_tool_names()
    print(json.dumps({"runtime_tools": len(names), "names": names,
                      "uncovered_by_board": uncovered_runtime_tools(),
                      "eval_schema_extra": sorted(eval_schema_tool_names() - set(names))},
                     ensure_ascii=False, indent=2))
