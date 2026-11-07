"""Offline, GPU-free replay: quantify the toolcall fixes on the identity-stamped frozen leg.

Compares three stacks on the same 30 toolcall responses with the same grader:
  raw        -> the model answer exactly as stored
  old_backend-> the pre-fix serving logic (single-object detection + unconditional compile
                with invented defaults + nc rename), re-implemented here so the comparison
                still works after virtu_real_backend.py was fixed
  new_backend-> the fixed logic (_parse_tool_payload + preserve arrays/field names +
                compile only fields the prompt states, fail-closed otherwise)
"""
import json, pathlib, re, sys
sys.path.insert(0, r"D:\Virtu模型")

import virtu_real_backend as B
from virtu_eval.graders import score_case

RAW = pathlib.Path(r"D:\Virtu模型\runs\eval\fullboard_20261105_0930\board7__frozen_comp_v5__v4\raw.jsonl")


def old_compile(text):
    """The compile fallback exactly as it was before the 2026-11-05 fail-closed fix."""
    t = text or ""
    path_m = re.search(r"(runs/[A-Za-z0-9_./\\-]+\.nc|models/[A-Za-z0-9_./\\-]+\.\w+)", t)
    path = path_m.group(1).replace("\\", "/") if path_m else None
    if "CIMCO" in t:
        action = "launch" if ("launch" in t.lower() or "背绘" in t) else "validate_macro"
        return {"tool": "cadcam_cimco_validate",
                "arguments": {"action": action, "nc_file_path": path or "runs/macro.nc"}}
    if "SOLIDWORKS" in t and re.search(r"VBA|vba", t):
        part_m = re.search(r"part_name\s*[=：:]\s*([A-Za-z0-9_\-]+)", t)
        return {"tool": "cadcam_solidworks_model",
                "arguments": {"action": "execute_vba", "part_name": part_m.group(1) if part_m else "part",
                              "vba_code": "Sub main()\nEnd Sub"}}
    if re.search(r"cadcam_nx_journal", t) and re.search(r"run_journal", t):
        sp = re.search(r"script_path\s*[=：:]\s*([A-Za-z0-9_./\\-]+)", t)
        return {"tool": "cadcam_nx_journal",
                "arguments": {"action": "run_journal", "script_path": sp.group(1) if sp else "runs/nx.py"}}
    return None


def old_looks_like_tool_json(text):
    if not isinstance(text, str) or "tool" not in text:
        return False
    try:
        s, e = text.find("{"), text.rfind("}")
        if s < 0 or e <= s:
            return False
        obj = json.loads(text[s:e + 1])
    except Exception:
        return False
    return isinstance(obj, dict) and ("tool" in obj or "arguments" in obj)


def old_normalize(obj):
    if not isinstance(obj, dict):
        return obj
    tool = obj.get("tool") or obj.get("name")
    if isinstance(tool, str) and tool in B._TOOL_ALIASES:
        obj["tool"] = B._TOOL_ALIASES[tool]
        obj.pop("name", None)
    args = obj.get("arguments")
    if isinstance(args, dict):
        a = args.get("action")
        if a in B._ACTION_ALIASES:
            args["action"] = B._ACTION_ALIASES[a]
        if "nc_file_path" in args and "nc_path" not in args:
            args["nc_path"] = args.pop("nc_file_path")
        obj["arguments"] = args
    return obj


def old_backend(text, prompt):
    if not B._is_toolcall_prompt(prompt):
        return text
    if old_looks_like_tool_json(text):
        try:
            s, e = text.find("{"), text.rfind("}")
            return json.dumps(old_normalize(json.loads(text[s:e + 1])), ensure_ascii=False)
        except Exception:
            return text
    comp = old_compile(prompt)
    return json.dumps(comp, ensure_ascii=False) if comp else text


rows = [json.loads(l) for l in RAW.read_text(encoding="utf-8").splitlines() if l.strip()]
CASES = {c["id"]: c for c in (json.loads(l) for l in
                              pathlib.Path(r"D:\Virtu模型\data\benchmark\virtu_eval_v1\toolcall.jsonl")
                              .read_text(encoding="utf-8").splitlines() if l.strip())}


def model_answer(row):
    """What the arm actually said: text, or the native tool calls when content was empty."""
    resp = row.get("response") or ""
    if resp.strip():
        return resp
    calls = row.get("tool_calls") or []
    if not calls:
        return resp
    made = [{"tool": (c.get("function") or {}).get("name", ""),
             "arguments": (c.get("function") or {}).get("arguments", {})} for c in calls]
    return json.dumps(made if len(made) > 1 else made[0], ensure_ascii=False)


tc = [r for r in rows if r.get("dimension") == "toolcall"]
sums = {"raw": 0.0, "old": 0.0, "new": 0.0}
changes = []
for r in tc:
    prompt = r.get("prompt", "")
    criteria = CASES[r["case_id"]]["criteria"]          # specs, not stored verdicts
    resp = model_answer(r)
    raw_s = score_case(resp, criteria)["score"]
    old_t = old_backend(resp, prompt)
    old_s = score_case(old_t, criteria)["score"]
    new_t = B._verify_arithmetic_response(resp, [{"role": "user", "content": prompt}])
    new_s = score_case(new_t, criteria)["score"]
    sums["raw"] += raw_s; sums["old"] += old_s; sums["new"] += new_s
    if abs(old_s - new_s) > 1e-9 or abs(raw_s - new_s) > 1e-9:
        changes.append((r["case_id"], raw_s, old_s, new_s, len(resp.strip()),
                        B._parse_tool_payload(resp) is not None, r.get("score"),
                        new_t[:140].replace("\n", " ")))

n = len(tc)
print(f"toolcall n={n}  (stored-leg score: {sum(r.get('score') or 0 for r in tc)/n:.2f})")
for k in ("raw", "old", "new"):
    print(f"  {k:12s} mean={sums[k]/n:6.2f}")
print(f"  old->new delta mean={(sums['new']-sums['old'])/n:+.2f}  (fail-closed contribution)")
print("changed cases (case_id, raw, old_backend, new_backend, answer_len, had_call, leg_score):")
for cid, r0, o, nw, ln, had_call, leg, t in changes:
    print(f"  {cid:16s} raw={r0:6.2f} old={o:6.2f} new={nw:6.2f} len={ln:4d} "
          f"had_call={had_call} leg={leg} | {t}")
print("NO_CHANGE_IN_TOOLCALL" if not changes else "CHANGES_FOUND")
