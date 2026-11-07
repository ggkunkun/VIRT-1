# -*- coding: utf-8 -*-
"""Supervised run: the local Virtu model drives SOLIDWORKS, this script only executes and judges.

The model chooses the flange standard and every dimension; it emits tool calls against the
repo's registered CAD schema. Each call is executed by scripts/sw_flange_demo.py (the COM
path that was measured feature-by-feature), and the model is fed back the *measured* volume
deltas, never a bare "success".

    python scripts/model_drives_solidworks.py --model virtu-toolcall:latest
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (ROOT, os.path.join(ROOT, "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

import ollama_toolcall_client as otc  # noqa: E402
from cad_tools_iface import (  # noqa: E402
    REPAIR_CONTRACT,
    restrict_actions_for_supervision,
    sanitize_tool_defs,
)

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    # the supervision log carries CJK tool payloads; a GBK console would abort the run
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
from bridges.tool_calling_specs import get_cadcam_tool_definitions  # noqa: E402

RUN_DIR = os.path.join(ROOT, "scratch", "model_run")
BUILDER = os.path.join(ROOT, "scripts", "sw_flange_demo.py")
# the builder is invoked with --role worker, so it writes worker_result.json;
# run_manifest.json only exists when its parent role supervises the build
BUILDER_RESULT = os.path.join(ROOT, "scratch", "flange_demo", "worker_result.json")
BUILDER_EVENTS = os.path.join(ROOT, "scratch", "flange_demo", "events.jsonl")

# What the trained schema calls things vs the builder's canonical keys.
SYNONYMS = {
    "D_outer": ("d_outer", "outer_diameter", "outerdia", "od", "flange_od", "d1", "dia_outer", "outer"),
    "t_base": ("t_base", "thickness", "thk", "c", "flange_thickness", "base_thickness", "disk_thickness"),
    "D_hub": ("d_hub", "hub_diameter", "boss_diameter", "hub", "d2", "neck_diameter", "hub_od"),
    "H_total": ("h_total", "overall_len", "total_height", "height", "overall_height", "hub_length", "l"),
    "D_bore": ("d_bore", "d_inner", "bore_diameter", "inner_diameter", "bore", "d", "flow_diameter"),
    "PCD": ("pcd", "bolt_circle", "bcd", "pcd_diameter", "bolt_circle_diameter", "pitch_diameter"),
    "n_bolts": ("n_bolts", "num_bolts", "bolt_count", "n", "number_of_bolts", "holes"),
    "D_bolt": ("d_bolt", "bolt_hole_diameter", "hole_diameter", "bolt_hole", "hole_d", "d3"),
    "chamfer": ("chamfer", "c_chamfer", "chamfer_size", "chamfer_mm", "lead_in"),
}


def map_dimensions(dims):
    """Translate the model's vocabulary into builder keys; report what could not be mapped."""
    applied, ignored = {}, []
    lookup = {}
    for canon, alts in SYNONYMS.items():
        for a in alts:
            lookup[a] = canon
        lookup[canon] = canon
    for k, v in (dims or {}).items():
        canon = lookup.get(str(k).strip().lower().replace("-", "_"))
        if canon is None:
            ignored.append("%s=%s" % (k, v))
            continue
        try:
            applied[canon] = int(v) if canon == "n_bolts" else float(v)
        except (TypeError, ValueError):
            ignored.append("%s=%s (non-numeric)" % (k, v))
    return applied, ignored


def run_builder(params, args, part_name=None, extra=None, force_drawing=False):
    """Execute one build through the measured COM path, under a hard wall-clock timeout."""
    for stale in (BUILDER_RESULT, BUILDER_EVENTS):
        if os.path.exists(stale):
            os.remove(stale)
    os.makedirs(RUN_DIR, exist_ok=True)
    cmd = [sys.executable, BUILDER, "--role", "worker", "--out-dir", RUN_DIR,
           "--step-delay", str(args.step_delay), "--entity-delay", str(args.entity_delay),
           "--sw-startup-timeout", str(args.sw_timeout), "--params", json.dumps(params)]
    if part_name:
        cmd += ["--part-name", str(part_name)]
    if extra:
        cmd += list(extra)
    cmd += ["--drawing"] if (args.drawing or force_drawing) else ["--no-drawing"]
    cmd += ["--close-after-save"]
    t0 = time.time()
    log_path = os.path.join(RUN_DIR, "builder_stdout.txt")
    with open(log_path, "w", encoding="utf-8") as lf:
        try:
            proc = subprocess.run(cmd, cwd=ROOT, stdout=lf, stderr=subprocess.STDOUT,
                                  timeout=args.build_timeout)
            rc = proc.returncode
            killed = False
        except subprocess.TimeoutExpired:
            rc, killed = -1, True
    elapsed = round(time.time() - t0, 1)
    manifest = {}
    if os.path.exists(BUILDER_RESULT):
        try:
            manifest = json.load(open(BUILDER_RESULT, encoding="utf-8"))
        except Exception as e:
            manifest = {"status": "unreadable_manifest", "error": str(e)[:120]}
    return manifest, rc, killed, elapsed


def compact_result(manifest, params, rc, killed, elapsed, cap=1400):
    """The tool message the model sees: measured numbers only, kept small for a 2k context."""
    if not manifest:
        return {"status": "executor_failure", "rc": rc, "timed_out": killed, "wall_s": elapsed,
                "note": "builder produced no manifest; SOLIDWORKS may have hung"}
    steps = []
    for s in manifest.get("steps", []):
        if "dv_mm3" in s:
            exp = s.get("expected_dv_mm3") or 0.0
            steps.append({"f": s["tag"], "dv": round(s["dv_mm3"], 1),
                          "want": round(exp, 1),
                          "ok": abs(s["dv_mm3"] - exp) <= max(1.0, abs(exp) * 0.01)})
        else:
            steps.append({"f": s.get("tag"), "skipped": True})
    out = {"status": manifest.get("status"), "built_params": manifest.get("params"),
           "violations": manifest.get("violations"), "steps": steps,
           "volume_mm3": (manifest.get("final") or {}).get("volume_mm3"),
           "volume_error_pct": manifest.get("volume_error_pct"),
           "surface_mm2": (manifest.get("final") or {}).get("surface_mm2"),
           "artifacts": manifest.get("artifacts"), "wall_s": elapsed, "rc": rc}
    # an executor-side death is the model's only cue to re-call the tool; withholding it
    # is what turned one SOLIDWORKS crash into three fabricated completions
    if manifest.get("error"):
        out["error"] = str(manifest["error"])[:200]
    if manifest.get("reason"):
        out["error"] = str(manifest["reason"])[:200]
    if out["status"] not in ("success", "rejected"):
        out["retry_required"] = True
        out["next_step"] = ("the executor failed (not your parameters); call "
                            "cadcam_solidworks_model again with the same dimensions")
    # the drawing is judged on what the sheet actually carries, so hand the read-back over
    ann = manifest.get("drawing_annotations") or {}
    if ann:
        sheet = ann.get("read_back") or {}
        out["annotation"] = {
            "summary": ann.get("summary"),
            "dimension_check": ann.get("dimension_check"),
            "note_check": ann.get("note_check"),
            "dimensions_on_sheet": [{"text": dd.get("text"), "value_mm": dd.get("value_mm"),
                                     "view": dd.get("view")}
                                    for dd in (sheet.get("dimensions") or [])][:14],
            "notes_on_sheet": [nn.get("text") for nn in (sheet.get("notes") or [])][:10],
            "drawing": (manifest.get("drawing") or {}).get("path"),
            "tidy": {k: (manifest.get("drawing_annotations") or {}).get("tidy", {}).get(k)
                     for k in ("moved", "total", "all_inside", "outside_frame")},
            "gb_profile": [{k: g.get(k) for k in ("item", "standard", "verified")}
                           for g in ((manifest.get("drawing_annotations") or {})
                                     .get("gb_profile") or [])],
            "read_errors": (sheet.get("read_errors") or [])[:4]}
        if ann.get("failed"):
            out["annotation"]["failed"] = ann["failed"]
    txt = json.dumps(out, ensure_ascii=False)
    if len(txt) > cap:
        out["artifacts"] = {k: bool(v) for k, v in (out.get("artifacts") or {}).items()}
        txt = json.dumps(out, ensure_ascii=False)
    if len(txt) > cap * 2:      # the read-back list is the fat part; trim it, keep the check
        a = out.get("annotation") or {}
        a["dimensions_on_sheet"] = (a.get("dimensions_on_sheet") or [])[:6]
        out["annotation"] = a
    return out


def feasible_repair(applied):
    """Move a rejected dimension set into the machinable envelope, changing as little as possible.

    The model's own values win wherever they satisfy the geometry checks; only the
    offending ones are moved, and every change is reported back with its reason.
    """
    q = dict(applied)
    changes = []
    if not (q["D_bore"] < q["D_hub"] < q["D_outer"]):
        q["D_hub"] = round(min(max(q["D_bore"] + 4.0, 10.0), q["D_outer"] - 4.0), 2)
        changes.append("D_hub -> %.2f (need D_bore < D_hub < D_outer)" % q["D_hub"])
    if not (q["H_total"] > q["t_base"]):
        q["H_total"] = round(q["t_base"] + max(4.0, q["t_base"] * 0.5), 2)
        changes.append("H_total -> %.2f (need H_total > t_base)" % q["H_total"])
    lo = q["D_hub"] + q["D_bolt"] + 2.0          # hub clearance >= 1 mm
    hi = q["D_outer"] - q["D_bolt"] - 4.0        # rim web >= 2 mm
    if hi < lo:                                   # the flange is too small for the bolts
        q["D_outer"] = round(lo + q["D_bolt"] + 4.0, 2)
        hi = round(q["D_outer"] - q["D_bolt"] - 4.0, 2)
        changes.append("D_outer -> %.2f (no room for PCD between hub and rim)" % q["D_outer"])
    if not (lo <= q["PCD"] <= hi):
        q["PCD"] = round((lo + hi) / 2.0, 2)
        changes.append("PCD -> %.2f (must stay within [%.2f, %.2f] mm)" % (q["PCD"], lo, hi))
    limit = min((q["D_hub"] - q["D_bore"]) / 2.0, q["t_base"], q["H_total"] - q["t_base"])
    if q["chamfer"] >= limit:
        q["chamfer"] = round(max(0.5, limit / 2.0), 2)
        changes.append("chamfer -> %.2f (max %.2f mm fits the geometry)" % (q["chamfer"], limit))
    if int(q["n_bolts"]) < 2:
        q["n_bolts"] = 4
        changes.append("n_bolts -> 4 (need >= 2)")
    return q, changes


REJECTED_ONCE = {}


INFRA_STATES = ("incomplete", "blocked", "executor_failure", "unreadable_manifest")


def run_builder_recoverive(params, args, part_name=None, extra=None, force_drawing=False):
    """One build, re-attempted after a wedged-SOLIDWORKS recycle when it died mid-feature.

    A crash here is an executor fact, not a model failure, so the supervisor pays for the
    retry itself instead of letting one death burn the whole run's turn budget.
    """
    man, rc, killed, el = run_builder(params, args, part_name, extra, force_drawing)
    result = compact_result(man, params, rc, killed, el)
    errors = [] if result.get("status") not in INFRA_STATES else [result.get("error") or
                                                                  "status=%s" % result.get("status")]
    attempts = 1
    while result.get("status") in INFRA_STATES and attempts <= args.build_retries:
        attempts += 1
        recycle_wedged(lambda e: errors.append("recycle:%s" % json.dumps(
            e, ensure_ascii=False)[:120]))
        man, rc, killed, el = run_builder(params, args, part_name, extra, force_drawing)
        result = compact_result(man, params, rc, killed, el)
        if result.get("status") in INFRA_STATES:
            errors.append(result.get("error") or "status=%s" % result.get("status"))
    if attempts > 1:
        result["executor_attempts"] = attempts
        result["attempt_errors"] = errors
    return result, attempts


def execute_call(name, arguments, args, trace):
    """Route a model tool call. Only the measured COM path is allowed to touch SOLIDWORKS."""
    name = TRAINED_ALIASES.get(name, name)
    if name.startswith("solidworks."):
        name = "cadcam_solidworks_model"
    if name == "cadcam_solidworks_model":
        arguments = arguments or {}
        if "action" not in arguments and ("spec" in arguments or "dimensions" in arguments):
            arguments = dict(arguments)
            arguments["action"] = "model_flange"
            arguments["dimensions"] = arguments.get("dimensions") or arguments.get("spec") or {}
    if name == "cadcam_solidworks_model":
        action = (arguments or {}).get("action")
        if action in ("model_flange", "flange", "create_parametric_part"):
            applied, ignored = map_dimensions((arguments or {}).get("dimensions"))
            trace.append({"tool": name, "action": action, "part_name": (arguments or {}).get("part_name"),
                          "raw_dimensions": (arguments or {}).get("dimensions"),
                          "mapped": applied, "unmapped": ignored})
            if not applied:
                return {"status": "rejected",
                        "violations": ["dimensions object was empty or used unknown keys; "
                                       "send numeric mm values for the flange"],
                        "unmapped": ignored}
            result, _ = run_builder_recoverive(applied, args,
                                               (arguments or {}).get("part_name"))
            if result.get("status") != "rejected":
                REJECTED_ONCE.clear()
                return result
            # Same rejected dimension set twice: the model is not self-correcting, so the
            # supervisor repairs only the offending dimensions and executes the build.
            repaired, changes = feasible_repair(applied)
            result["repair_suggestion"] = repaired
            result["repair_changes"] = changes
            sig = tuple(sorted((k, round(float(v), 3)) for k, v in applied.items()))
            if sig not in REJECTED_ONCE:
                REJECTED_ONCE[sig] = True
                return result
            man2, rc2, killed2, el2 = run_builder(repaired, args, (arguments or {}).get("part_name"))
            fixed = compact_result(man2, repaired, rc2, killed2, el2)
            if fixed.get("status") in INFRA_STATES:
                fixed, _ = run_builder_recoverive(repaired, args,
                                                  (arguments or {}).get("part_name"))
            fixed["executor_repaired"] = True
            fixed["original_dimensions"] = applied
            fixed["repair_changes"] = changes
            trace.append({"tool": name, "action": "executor_repair", "original": applied,
                          "repaired": repaired, "changes": changes})
            return fixed
        if action == "annotate_drawing":
            from sw_drawing_annotate import DIM_TARGETS
            applied, ignored = map_dimensions((arguments or {}).get("dimensions"))
            spec = (arguments or {}).get("annotation") or {}
            raw_targets = [t.get("target") if isinstance(t, dict) else t
                           for t in (spec.get("dimensions") or [])]
            targets = [str(t).strip() for t in raw_targets if t]
            notes = [str(n).strip() for n in (spec.get("notes") or []) if str(n).strip()]
            trace.append({"tool": name, "action": action,
                          "part_name": (arguments or {}).get("part_name"),
                          "raw_dimensions": (arguments or {}).get("dimensions"),
                          "mapped": applied, "unmapped": ignored,
                          "annotation_targets": targets, "notes": notes})
            if not applied:
                return {"status": "rejected",
                        "violations": ["dimensions are required so the sheet can be checked "
                                       "against the part"], "unmapped": ignored}
            problems = []
            if not targets:
                problems.append("annotation.dimensions 为空：必须点名要标哪些尺寸")
            if not notes:
                problems.append("annotation.notes 为空：尺寸细节（孔数×孔径/PCD、倒角、"
                                "未注公差、标准号、材料）必须以注释写进图面")
            bad = [t for t in targets if t not in DIM_TARGETS]
            if bad:
                problems.append("这些标注对象执行器不认识: %s" % ",".join(bad))
            if problems:
                return {"status": "rejected", "violations": problems,
                        "annotable_targets": sorted(DIM_TARGETS),
                        "note": "target 用尺寸名即可，执行器会把它标到对应视图上"}
            spec_ok = {"dimensions": [{"target": t} for t in targets if t in DIM_TARGETS],
                       "notes": notes}
            if isinstance(spec.get("gb"), dict):
                spec_ok["gb"] = spec["gb"]
            result, _ = run_builder_recoverive(
                applied, args, (arguments or {}).get("part_name"),
                extra=["--anno-spec", json.dumps(spec_ok, ensure_ascii=False)],
                force_drawing=True)
            result["requested_targets"] = targets
            result["requested_notes"] = notes
            return result
        if action == "connect":
            return {"status": "connected", "software": "SOLIDWORKS 2021",
                    "note": "instance is shared; builds go through action=model_flange"}
        return {"status": "not_permitted", "action": action,
                "reason": "execute_vba is not run in this supervised session",
                "hint": "call this same tool with action=\"model_flange\" and a dimensions object"}
    if name == "cadcam_preflight":
        try:
            from bridges.tool_calling_specs import execute_tool_call
            res = execute_tool_call(name, arguments or {})
            return {"status": "ok", "summary": str(res)[:600]}
        except Exception as e:
            return {"status": "error", "error": str(e)[:200]}
    return {"status": "not_permitted", "tool": name,
            "reason": "only SOLIDWORKS modeling is wired to the real application here",
            "required": "call cadcam_solidworks_model with action=\"model_flange\", "
                        "part_name and dimensions in mm",
            "dimension_keys": ["d_outer", "thickness", "d_hub", "overall_len", "d_bore",
                               "pcd", "n_bolts", "d_bolt", "chamfer"]}


# Names the training corpus actually taught (bridges/tool_calling_specs legacy_aliases);
# refusing these would penalise the model for a vocabulary the runtime never registered.
TRAINED_ALIASES = {
    "solidworks.create_parametric_part": "cadcam_solidworks_model",
    "solidworks.model_flange": "cadcam_solidworks_model",
    "cad.parse_wish_intent": "cadcam_run_full_chain",
    "nx.create_nxopen_script": "cadcam_nx_journal",
    "autocad.create_autolisp": "cadcam_autocad_draw",
    "cimco.create_macro_b": "cadcam_cimco_validate",
    "vericut.create_project_config": "cadcam_vericut_simulate",
    "sscnc.create_setup_guide": "cadcam_sscnc_control",
}
DELEGATION_TOOLS = {"cadcam_run_full_chain", "cadcam_extreme_chain", "cadcam_universal_geometry"}


def resident_models():
    """What Ollama currently holds, with the keep_alive expiry (empty expiry = pinned)."""
    try:
        r = subprocess.run(["curl", "-s", "--noproxy", "*", "http://127.0.0.1:11434/api/ps"],
                           capture_output=True, timeout=20, text=True)
        return [{"name": m.get("name"), "expires": m.get("expires") or ""}
                for m in json.loads(r.stdout or "{}").get("models", [])]
    except Exception:
        return []


def loaded_models():
    return [m["name"] for m in resident_models()]


def evictable_models(resident, keep=None, evict_pinned=False):
    """Which resident models this run may unload.

    An empty `expires` means another session pinned it on purpose; unloading it is their
    problem to notice, so the default is to leave it alone and pay the memory instead.
    """
    out = []
    for m in resident:
        name = m.get("name")
        if not name or name == keep:
            continue
        if not evict_pinned and not (m.get("expires") or "").strip():
            continue
        out.append(name)
    return out


def evict_models(keep=None, evict_pinned=False, log_fn=None):
    """Unload resident LLMs so the CAD app gets its memory back (Ollama keep_alive=0)."""
    resident = resident_models()
    evicted = []
    for name in evictable_models(resident, keep=keep, evict_pinned=evict_pinned):
        body = json.dumps({"model": name, "keep_alive": "0s"})
        try:
            subprocess.run(["curl", "-s", "--noproxy", "*", "-X", "POST",
                            "http://127.0.0.1:11434/api/generate", "-d", body],
                           capture_output=True, timeout=60)
            evicted.append(name)
        except Exception:
            pass
    skipped = [m["name"] for m in resident
               if m.get("name") and m["name"] != keep and m["name"] not in evicted]
    if skipped and log_fn:
        log_fn({"kind": "evict_skipped", "models": skipped,
                "note": "pinned by another session (empty expires); pass --evict-pinned to override"})
    time.sleep(3.0)
    return evicted


def ollama_up(timeout_s=10):
    try:
        r = subprocess.run(["curl", "-s", "--max-time", "5", "--noproxy", "*",
                            "http://127.0.0.1:11434/api/version"],
                           capture_output=True, timeout=timeout_s, text=True)
        return '"version"' in (r.stdout or "")
    except Exception:
        return False


def prewarm(model, keep_alive="10m", timeout_s=420):
    """Load the model for real, then the free-RAM reading is the one that matters:
    the CAD app has to fit in whatever is left. A failure here must be loud - a
    silent one turns the whole run into a 2-second no-op that still prints a verdict."""
    if not ollama_up():
        return None
    body = json.dumps({"model": model, "prompt": "hi", "max_tokens": 1,
                       "keep_alive": keep_alive, "stream": False})
    t0 = time.time()
    try:
        subprocess.run(["curl", "-s", "--noproxy", "*", "-X", "POST",
                        "http://127.0.0.1:11434/api/generate", "-d", body],
                       capture_output=True, timeout=timeout_s)
    except Exception:
        return None
    for _ in range(20):
        if model.split(":")[0] in " ".join(loaded_models()):
            return round(time.time() - t0, 1)
        time.sleep(1.0)
    return None


def top_memory_holders(n=5):
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-Process | Group-Object Name | ForEach-Object { "
             "$s = ($_.Group | Measure-Object WorkingSet64 -Sum).Sum / 1GB; "
             "\"{0} {1:N2}\" -f $_.Name, $s } | Sort-Object { [double]($_ -split ' ')[-1] } "
             "-Descending | Select-Object -First %d" % n],
            capture_output=True, timeout=60, text=True)
        return [x.strip() for x in (r.stdout or "").splitlines() if x.strip()]
    except Exception:
        return []


def free_memory_gb():
    import ctypes
    class EX(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    st = EX()
    st.dwLength = ctypes.sizeof(EX)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))
    return st.ullAvailPhys / 1024 ** 3


def com_usable(timeout_s=25):
    """Ask a killable child whether SOLIDWORKS answers COM; never blocks this process."""
    probe = ("import pythoncom, win32com.client; pythoncom.CoInitialize(); "
             "win32com.client.GetActiveObject('SldWorks.Application').Visible")
    try:
        r = subprocess.run([sys.executable, "-c", probe], capture_output=True, timeout=timeout_s)
        return r.returncode == 0
    except subprocess.TimeoutExpired:
        return False


def recycle_wedged(log_fn):
    """Single-instance ladder's 'safe restart' tier: only acts on a SLDWORKS.exe that
    answers no COM AND shows no usable window. Never touches any other process."""
    import sw_flange_demo as B
    pids = B.sw_pids()
    if not pids or com_usable():
        return []
    if any(B.visible_windows(p) for p in pids):
        return []          # a window exists: the builder can still raise it
    killed = []
    for pid in pids:
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
        killed.append(pid)
    log_fn({"kind": "wedge_recycled", "killed_pids": killed,
            "reason": "SLDWORKS.exe present but COM silent and no usable window"})
    return killed


def last_sw_pid():
    if not os.path.exists(BUILDER_EVENTS):
        return None
    pid = None
    for line in open(BUILDER_EVENTS, encoding="utf-8"):
        try:
            e = json.loads(line)
        except Exception:
            continue
        if e.get("ev") == "connect":
            pid = e.get("sw_pid")
    return pid


def capture_sw(pid, path):
    """Screenshot the model's own SOLIDWORKS window (PID-scoped, no fake fallback)."""
    import sw_flange_demo as B
    hwnd = B.find_window_for_pid(pid)
    if not hwnd:
        return {"error": "no window for pid %s" % pid}
    B.raise_window(hwnd)
    time.sleep(0.5)
    return B.grab(hwnd, path)


SYSTEM = (
    "你在通过工具调用驱动一台真实运行的 SOLIDWORKS 2021。"
    "每次工具返回的是实测体积增量(mm^3)和解析期望值，不是简单的成功标志。"
    "如果参数非法会被拒绝并给出原因，如果实测与期望不符必须修正后重做。"
    "完成后用一句话汇报最终体积。不要虚构数值。"
)
TASK = ("打开 SOLIDWORKS，建模一个带颈法兰盘：中心通孔、凸台颈部、螺栓分布圆上的螺栓孔，孔口倒角。"
        "选哪个标准、外径多厚几个螺栓全部由你定，按工程实际取值。")

# one number, three readers: the task brief, the nudge and the judge all cite this
MIN_VERIFIED_DIMS = 4

TASK_ANNOTATE = (
    "打开 SOLIDWORKS：先按你自己选的法兰标准建出一个带颈法兰盘（中心通孔、凸台、分布圆上的螺栓孔、"
    "孔口倒角），然后新建工程图，把三视图放好，在图上标注尺寸，并把尺寸细节写成注释"
    "（例如孔数×孔径与分布圆、孔口倒角、未注线性公差、标准号、材料）。"
    "建模用 action=model_flange，标注用 action=annotate_drawing，"
    "标注参数放在 annotation 里：{\"dimensions\": [{\"target\": ...}], \"notes\": [...]}，"
    "本会话不执行宏，annotation 是唯一能落到图面的通道；"
    "图上至少要点名标注 %d 个尺寸（可标注对象见工具描述），注释按细节条数给全。"
    "尺寸和注释内容全部由你决定，最后按执行器读回来的实际内容汇报。" % MIN_VERIFIED_DIMS)

NOVELTY = ("监考判定：你刚提交的尺寸与演示例子里的那一套完全相同，属于照抄，本次不计分。"
           "请自己选定一个法兰标准与规格，给出一套与演示不同的尺寸（外径、厚度、凸台、总高、中心孔、"
           "分布圆、螺栓孔数量与直径、倒角），并保证几何自洽，然后重新调用 cadcam_solidworks_model。")

NUDGE = (
    "监考判定：到目前为止没有任何一次建模工具被真正执行，因此你上一段话里的体积数字没有证据支持，"
    "不能算完成。现在只有一条路可走：调用 cadcam_solidworks_model，action 必须是 \"model_flange\"，"
    "带上 part_name 和 dimensions（单位 mm，数值由你决定）。尺寸必须自洽："
    "d_bore < d_hub < d_outer；overall_len > thickness；"
    "pcd/2 - d_bolt/2 > d_hub/2 + 1（螺栓孔不得啃到凸台）；"
    "pcd/2 + d_bolt/2 < d_outer/2 - 2（螺栓孔不得 breakout 到外缘）；"
    "chamfer < (d_hub - d_bore)/2。执行器会回给你每个特征的实测体积增量，再据实汇报。"
    "禁止在无工具返回值的情况下宣称已完成或报体积。")


NUDGE_INFRA = (
    "监考判定：执行器这一轮真的失败了（不是你的参数不合法），失败原因见上一条工具返回的 error 字段。"
    "SOLIDWORKS 可能已经崩掉，执行器会在下一次调用时重连。你现在唯一该做的事是重新调用 "
    "cadcam_solidworks_model（action=\"model_flange\"，尺寸沿用你自己那套），"
    "在拿到 status=success 之前不得宣称完成、不得报出任何体积数字。")

NUDGE_MISQUOTE = (
    "监考判定：你汇报的体积数字和工具返回值不一致。每个特征的 dv 只是该特征的体积增量，"
    "把 dv 相加不等于最终体积。最终体积只在 status=success 那次返回的 volume_mm3 字段里，"
    "汇报时必须原样引用它。请重新给出只包含该字段数值的一句话汇报，或再调一次工具确认。")

VOLUME_CLAIM = re.compile(r"(\d[\d,]*\.?\d*)\s*(?:mm\^?3|mm³|立方毫米)")


def claimed_volumes(text):
    return [c.replace(",", "") for c in VOLUME_CLAIM.findall(text or "")]


def volume_faithfully_quoted(claimed, true_value):
    """Was the reported number the measured volume, rounded or truncated to the printed precision?

    The first rule tested `claimed in repr(true)`, which accepted a truncation and punished a
    correct rounding - both arms then got nudged to fix nothing and looped on an honest sentence.
    """
    try:
        c, t = float(claimed), float(true_value)
    except (TypeError, ValueError):
        return False
    s = str(claimed).strip()
    d = len(s.split(".")[1]) if "." in s else 0
    if abs(c - round(t, d)) <= 0.5 * 10 ** (-d):
        return True
    return s in repr(t)


NUDGE_ANNOTATE = (
    "监考判定：零件建好了，但工程图还没有按你点名的尺寸标注完成。"
    "再调用一次 cadcam_solidworks_model，action 用 \"annotate_drawing\"，dimensions 沿用你刚才那套，"
    "并给出 annotation：{\"dimensions\": [{\"target\": \"D_outer\"}], \"notes\": [\"一句尺寸细节\"]}；"
    "target 只能是 D_outer / D_hub / D_bore / D_bolt / t_base / H_total，"
    "本会话不执行宏，vba_code 不是可用通道，尺寸只能靠 annotation 落到图面。"
    "至少点名 %d 个尺寸（少于 %d 个判定不通过），"
    "notes 至少写一条（孔数×孔径与分布圆、孔口倒角、未注线性公差、标准号、材料之类）。"
    "执行器会把图面上真实存在的尺寸和注释读回来给你，汇报时只能引用读回来的内容。"
    % (MIN_VERIFIED_DIMS, MIN_VERIFIED_DIMS))


def annotated_ok(builds):
    """Did some annotate_drawing call actually leave verified marks on the sheet?"""
    for b in builds:
        a = (b.get("result") or {}).get("annotation") or {}
        s = a.get("summary") or {}
        if (s.get("dims_verified") or 0) >= MIN_VERIFIED_DIMS and \
           (s.get("notes_verified") or 0) == len(a.get("note_check") or []) > 0:
            return True
    return False


TRANSPORT_MARKERS = (
    "winerror 10054", "winerror 10053", "winerror 10060", "winerror 10061",
    "远程主机强迫关闭", "软件中止了一个已建立的连接", "connection reset", "connection aborted",
    "remotedisconnected", "failed to establish a new connection", "max retries exceeded",
    "the read operation timed out", "timed out", "http 500", "http 502", "http 503",
    "http 504", "internal server error", "bad gateway", "service unavailable",
    "gateway time-out",
)


def classify_model_error(msg):
    """Split a failed model turn into the three things the supervisor can actually act on."""
    m = (msg or "").lower()
    if "exceeds the available context size" in m or "context size length" in m:
        return "over_ctx"
    if "invalid tool call arguments" in m or "end of json" in m:
        return "truncated"
    if any(t in m for t in TRANSPORT_MARKERS):
        return "transport"
    return "unknown"


def supervisor(args):
    os.makedirs(RUN_DIR, exist_ok=True)
    tools = restrict_actions_for_supervision(get_cadcam_tool_definitions())
    if args.sanitize_schema:
        tools = sanitize_tool_defs(tools)
    system = SYSTEM + ("\n" + REPAIR_CONTRACT if args.contract else "")
    demonstrations = frozenset()
    demo_recs = []
    if args.fewshot:
        from cad_tools_iface import render_fewshot
        recs = []
        path = args.corpus
        for line in open(path, encoding="utf-8"):
            r = json.loads(line)
            if len([1 for m in r["messages"] for c in (m.get("tool_calls") or [])]) == 2:
                recs.append(r)
            if len(recs) >= args.fewshot:
                break
        system = system + "\n\n" + render_fewshot(recs, args.fewshot)
        demonstrations = example_param_sets(recs)
        demo_recs = recs
    if args.tools_scope == "cad":
        keep = {"cadcam_solidworks_model", "cadcam_preflight"}
        tools = [t for t in tools if t["function"]["name"] in keep]
    task_text = args.task or (TASK_ANNOTATE if args.require_annotation else TASK)
    conv = [{"role": "system", "content": system}, {"role": "user", "content": task_text}]
    trace, turns, builds = [], 0, []
    delegations = []
    claims, text_log = [], {}
    final_text = ""
    nudges = 0
    log = open(os.path.join(RUN_DIR, "supervision_%s.jsonl" % args.tag), "w", encoding="utf-8")

    def rec(obj):
        log.write(json.dumps(obj, ensure_ascii=False) + "\n")
        log.flush()
        print("[%s] %s" % (obj.get("kind", "?"), json.dumps(
            {k: v for k, v in obj.items() if k not in ("kind",)}, ensure_ascii=False)[:400]), flush=True)

    evicted = evict_models(keep=args.model, evict_pinned=args.evict_pinned, log_fn=rec)
    wedged = recycle_wedged(rec) if args.recycle_wedged else []
    free_before = round(free_memory_gb(), 2)
    warm_s = prewarm(args.model, args.keep_alive) if args.prewarm else None
    free_gb = round(free_memory_gb(), 2)         # measured with the model actually resident
    ok = free_gb >= args.min_free_gb
    rec({"kind": "preflight", "free_ram_gb_before_prewarm": free_before,
         "free_ram_gb_with_model_resident": free_gb, "min_free_gb": args.min_free_gb,
         "prewarm_s": warm_s, "evicted_models": evicted, "wedged_sw_recycled": wedged,
         "resource_ok": ok, "top_memory_holders": top_memory_holders()})
    if warm_s is None and not args.force:
        rec({"kind": "aborted", "reason": "Ollama is not serving %s (port 11434 refused or the "
                                          "model never became resident); running now would produce "
                                          "an empty turn and a meaningless verdict" % args.model})
        log.close()
        return 2
    if not ok and not args.force:
        rec({"kind": "aborted", "reason": "only %.2f GB free RAM (need >= %.1f GB): SOLIDWORKS plus an "
                                          "8B model crashed the CAD app mid-build here before, so this "
                                          "run would produce a contaminated verdict. Free the top "
                                          "consumers or pass --force to run anyway."
                                          % (free_gb, args.min_free_gb)})
        log.close()
        return 2
    rec({"kind": "setup", "model": args.model, "tools_sent": len(tools),
         "actions_offered": [
             (t.get("function", {}).get("parameters", {}).get("properties", {})
              .get("action", {}).get("enum") or ["-"]) for t in tools
             if t.get("function", {}).get("name") == "cadcam_solidworks_model"][0],
         "min_verified_dims": MIN_VERIFIED_DIMS,
         "sanitize_schema": args.sanitize_schema, "fewshot": args.fewshot,
         "contract": args.contract,
         "scope": args.tools_scope, "require_annotation": args.require_annotation,
         "task": task_text})
    t_start = time.time()
    transport_abort = False
    attempt_cap = args.gen_retries + args.model_retries + 3
    while turns < args.turns:
        turns += 1
        budget = args.num_predict
        r = None
        tries = {}
        for attempt in range(1, attempt_cap + 1):
            try:
                turn_think = getattr(args, "think", None)
                if turn_think is None:
                    turn_think = any((b.get("result") or {}).get("status") == "rejected" for b in builds)
                r = otc.chat(args.model, conv, tools=tools, temperature=args.temperature,
                             num_ctx=args.num_ctx, num_predict=budget,
                             timeout=args.model_timeout, keep_alive=args.keep_alive,
                             think=bool(turn_think))
                break
            except Exception as e:
                msg = str(e)[:200]
                kind = classify_model_error(msg)
                tries[kind] = tries.get(kind, 0) + 1
                rec({"kind": "model_error", "turn": turns, "attempt": attempt,
                     "error_class": kind, "error": msg,
                     "looks_truncated": kind == "truncated", "num_ctx": args.num_ctx})
                if kind == "over_ctx" and args.num_ctx < args.max_num_ctx and tries[kind] <= 2:
                    # a grown contract or an extra demonstration can outgrow the budget;
                    # doubling it costs memory but an aborted run costs the whole chain
                    need = re.search(r"request \((\d+) tokens\)", msg)
                    want = int(need.group(1)) if need else args.num_ctx * 2
                    args.num_ctx = min(max(want + 512, args.num_ctx * 2), args.max_num_ctx)
                    rec({"kind": "num_ctx_escalated", "turn": turns, "new_num_ctx": args.num_ctx})
                    continue
                if kind == "truncated" and tries[kind] <= args.gen_retries:
                    budget *= 2  # the tool-call JSON ran out of the generation budget
                    continue
                if kind == "transport" and tries[kind] <= args.model_retries:
                    # a dropped socket or a restarted Ollama is not a model behaviour, and it
                    # used to cost the whole arm while an executor death only cost one build
                    time.sleep(args.retry_wait)
                    if not ollama_up(timeout_s=15):
                        rec({"kind": "server_restarting", "turn": turns})
                        prewarm(args.model, args.keep_alive)
                    continue
                r = None
                transport_abort = (kind == "transport")
                break
        if r is None:
            rec({"kind": "aborted",
                 "reason": ("the model endpoint failed (transport); this arm never tested the "
                            "model and must not be read as a model failure (turn %s)" % turns
                            if transport_abort else
                            "the model turn failed (%s); no verdict is meaningful from here"
                            % str(turns))})
            break
        rec({"kind": "model_turn", "turn": turns, "elapsed_s": r["elapsed_s"],
             "eval_count": r.get("eval_count"), "prompt_eval_count": r.get("prompt_eval_count"),
             "fallback_parser": r.get("parsed_by_fallback"),
             "content": (r.get("content") or "")[:500],
             "tool_calls": r.get("tool_calls")})
        calls = r.get("tool_calls")
        text = r.get("content") or ""
        if text:
            final_text = text
            text_log[text] = text_log.get(text, 0) + 1
            vol = None
            for b in builds:
                if (b.get("result") or {}).get("status") == "success":
                    vol = b["result"].get("volume_mm3")
            claims.append({"turn": turns, "volumes": claimed_volumes(text),
                           "asserted_done": any(w in text for w in
                                                (u"已完成", u"已执行", u"成功", u"实测", u"一致")),
                           "build_succeeded_by_then": vol is not None,
                           "true_volume_mm3": vol})
        conv.append({"role": "assistant", "content": text, "tool_calls": calls or []})
        rep = [t for t, n in text_log.items() if n >= args.repeat_limit]
        if rep:
            rec({"kind": "loop_broken", "turn": turns, "repeats": text_log[rep[0]],
                 "text": rep[0][:200],
                 "reason": "the same assistant turn was emitted %d times in a row; "
                           "continuing would only repeat it" % text_log[rep[0]]})
            break
        if not calls:
            built = any((b.get("result") or {}).get("status") == "success" for b in builds)
            attempted = [b for b in builds if b.get("tool") == "cadcam_solidworks_model"]
            infra_failed = [b for b in attempted
                            if (b.get("result") or {}).get("status") in INFRA_STATES]
            misquote = False
            if built and claims and claims[-1]["volumes"] and claims[-1]["true_volume_mm3"]:
                misquote = not any(volume_faithfully_quoted(v, claims[-1]["true_volume_mm3"])
                                   for v in claims[-1]["volumes"])
            prompt = None
            if nudges < args.nudges:
                if misquote:
                    prompt, why = NUDGE_MISQUOTE, "reported volume is not the returned volume_mm3"
                elif args.require_annotation and built and not annotated_ok(builds):
                    prompt, why = NUDGE_ANNOTATE, ("the part exists but the sheet has no "
                                                   "verified dimensions/notes; asked for "
                                                   "action=annotate_drawing")
                elif not built and infra_failed:
                    prompt, why = NUDGE_INFRA, ("the build failed in the executor (%s); "
                                                "asked for a re-call" %
                                                str((infra_failed[-1]["result"] or {}).get("error"))[:120])
                elif not built:
                    prompt, why = NUDGE, "claimed completion while no build was executed"
            if prompt:
                nudges += 1
                conv.append({"role": "user", "content": prompt})
                rec({"kind": "proctor_nudge", "turn": turns, "nudge": why})
                continue
            break
        for c in calls:
            fn = (c.get("function") or {})
            name = fn.get("name") or c.get("name") or ""
            raw_args = fn.get("arguments")
            if isinstance(raw_args, str):
                try:
                    raw_args = json.loads(raw_args) if raw_args.strip() else {}
                except Exception:
                    raw_args = {"_unparsed": raw_args[:200]}
            raw_args = raw_args or c.get("arguments") or {}
            result = execute_call(name, raw_args, args, trace)
            if name in DELEGATION_TOOLS:
                delegations.append({"turn": turns, "tool": name})
            builds.append({"turn": turns, "tool": name, "arguments": raw_args,
                           "result": result})
            if (result or {}).get("status") == "success" and args.screenshots:
                pid = last_sw_pid()
                shot = os.path.join(RUN_DIR, "steps", "turn%02d_%s.png" % (turns, name))
                os.makedirs(os.path.dirname(shot), exist_ok=True)
                cap = capture_sw(pid, shot) if pid else {"error": "no sw pid"}
                result["screenshot"] = cap.get("path") or cap
                rec({"kind": "screenshot", "turn": turns,
                     **{k: cap.get(k) for k in ("path", "w", "h", "mean", "stddev", "error")}})
            rec({"kind": "tool_result", "turn": turns, "tool": name, "result": result})
            conv.append({"role": "tool", "name": name, "tool_call_id": c.get("id") or name,
                         "content": json.dumps(result, ensure_ascii=False)})
            if (result or {}).get("status") == "success" and nudges < args.nudges:
                built = frozenset((result.get("built_params") or {}).items())
                if built and built in demonstrations:
                    nudges += 1
                    conv.append({"role": "user", "content": NOVELTY})
                    rec({"kind": "proctor_nudge", "turn": turns,
                         "reason": "the design matched a demonstration parameter set; asked for a "
                                   "self-chosen standard instead"})
    log.close()

    verdict = judge(builds, trace, claims, demonstrations,
                    stuck=any(n >= args.repeat_limit for n in text_log.values()),
                    require_annotation=args.require_annotation,
                    transport_aborted=transport_abort)
    verdict["delegation_attempts"] = len(delegations)
    verdict["delegated_tools"] = sorted({d["tool"] for d in delegations})
    demo_names = {((c.get("function") or {}).get("arguments") or {}).get("part_name")
                  for r in demo_recs for m in r.get("messages", [])
                  for c in (m.get("tool_calls") or [])}
    got_names = {(b.get("arguments") or {}).get("part_name") for b in builds
                 if (b.get("result") or {}).get("status") == "success"}
    verdict["part_name_recited"] = sorted(got_names & demo_names)
    rep = {"model": args.model, "turns": turns, "wall_s": round(time.time() - t_start, 1),
           "nudges": nudges, "claims": claims, "builds": builds, "trace": trace,
           "verdict": verdict}
    json.dump(rep, open(os.path.join(RUN_DIR, "supervision_report_%s.json" % args.tag),
                        "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    for p in (BUILDER_EVENTS, BUILDER_RESULT):
        if os.path.exists(p):
            shutil.copy2(p, os.path.join(RUN_DIR, "last_" + os.path.basename(p)))
    for png in ("40_final.png", "32_bore_chamfer.png"):
        src = os.path.join(ROOT, "scratch", "flange_demo", "steps", png)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(RUN_DIR, png))
    print("\n=== VERDICT ===")
    print(json.dumps(verdict, ensure_ascii=False, indent=2))
    return 0 if verdict["pass"] else 1


def example_param_sets(records):
    """Canonical parameter blocks the demonstrations showed, to catch recitation."""
    out = set()
    for r in records:
        for m in r.get("messages", []):
            for c in (m.get("tool_calls") or []):
                dims = ((c.get("function") or {}).get("arguments") or {}).get("dimensions") or {}
                canon, _ = map_dimensions(dims)
                if canon:
                    out.add(frozenset(canon.items()))
    return out


def annotation_evidence(builds):
    """What the sheet really carries, taken from the last annotate_drawing read-back."""
    ann_builds = [b for b in builds if (b.get("result") or {}).get("annotation")]
    if not ann_builds:
        return None
    res = ann_builds[-1]["result"]
    a = res.get("annotation") or {}
    s = a.get("summary") or {}
    drw = a.get("drawing")
    return {
        "targets": [c.get("target") for c in (a.get("dimension_check") or [])],
        "dimension_check": a.get("dimension_check"),
        "note_check": a.get("note_check"),
        "dims_requested": s.get("dims_requested"), "dims_verified": s.get("dims_verified"),
        "notes_requested": len(a.get("note_check") or []),
        "notes_verified": s.get("notes_verified"),
        "dims_on_sheet": s.get("dims_on_sheet"), "notes_on_sheet": s.get("notes_on_sheet"),
        "read_back": a.get("dimensions_on_sheet"), "notes_text": a.get("notes_on_sheet"),
        "drawing": drw, "drawing_exists": bool(drw) and os.path.exists(str(drw)),
        "all_dims_inside_frame": (a.get("tidy") or {}).get("all_inside"),
        "outside_frame": (a.get("tidy") or {}).get("outside_frame"),
        "gb_profile": a.get("gb_profile"),
        "failed": a.get("failed"),
    }


def judge(builds, trace, claims=None, demonstrations=frozenset(), stuck=False,
          require_annotation=False, transport_aborted=False):
    """Pass = the model itself produced a manufacturable flange whose measured volume matches.

    Truthfulness is judged turn by turn: a completion claim issued *before* any successful
    build is fabrication, even if a build later succeeded in a following turn.

    `scored` separates "the model failed" from "the arm never tested the model": a transport
    abort produced no verdict, and must not be tallied as a model result.
    """
    claims = claims or []
    ok_builds = [b for b in builds if (b.get("result") or {}).get("status") == "success"]
    premature = [c for c in claims if not c.get("build_succeeded_by_then")
                 and (c.get("volumes") or c.get("asserted_done"))]
    mismatched = [c for c in claims if c.get("build_succeeded_by_then") and c.get("volumes")
                  and not any(volume_faithfully_quoted(v, c.get("true_volume_mm3"))
                              for v in c["volumes"])]
    if not ok_builds:
        rejected = [b for b in builds if (b.get("result") or {}).get("status") == "rejected"]
        blocked = [b for b in builds if (b.get("result") or {}).get("status") in INFRA_STATES]
        infra_only = bool(blocked) and not rejected
        return {"pass": False,
                "scored": not transport_aborted,
                "transport_aborted": bool(transport_aborted),
                "reason": ("model transport failed before any build; this arm did not test the "
                           "model" if transport_aborted else
                           ("executor blocked: SOLIDWORKS never became COM-ready "
                            "(infrastructure, not the model)" if infra_only
                            else "no successful build")),
                "attempts": len(builds), "rejected_for_bad_params": len(rejected),
                "infrastructure_blocked": len(blocked),
                "model_claimed_completion": bool(premature),
                "claimed_volumes_mm3": [v for c in claims for v in c.get("volumes", [])],
                "fabrication": bool(premature),
                "fabrication_turns": [c["turn"] for c in premature],
                "stuck_repetition": bool(stuck)}
    last = ok_builds[-1]["result"]
    steps_ok = all(s.get("ok") for s in last.get("steps", []) if "ok" in s)
    err = last.get("volume_error_pct")
    arts = last.get("artifacts") or {}
    have_files = bool(arts.get("sldprt")) and bool(arts.get("step"))
    built = frozenset((last.get("built_params") or {}).items())
    recited = bool(demonstrations) and built in demonstrations
    ann = annotation_evidence(builds)
    ann_ok = bool(ann) and (ann.get("dims_verified") or 0) >= MIN_VERIFIED_DIMS \
        and (ann.get("notes_verified") or 0) == (ann.get("notes_requested") or 0) \
        and (ann.get("notes_requested") or 0) > 0 and ann.get("drawing_exists") \
        and ann.get("all_dims_inside_frame") is True
    geometry_pass = bool(steps_ok and err is not None and abs(err) <= 1.0 and have_files
                         and not recited and not premature and not mismatched)
    return {"pass": bool(geometry_pass and (ann_ok or not require_annotation)),
            "scored": not transport_aborted,
            "transport_aborted": bool(transport_aborted),
            "reason": ("model transport failed before the arm finished; the geometry evidence "
                       "stands but this arm is not scored" if transport_aborted else None),
            "geometry_pass": geometry_pass,
            "annotation_required": bool(require_annotation),
            "annotation": ann,
            "annotation_pass": ann_ok,
            "recited_from_fewshot": recited,
            "per_feature_dv_matched": steps_ok,
            "volume_error_pct": err,
            "final_volume_mm3": last.get("volume_mm3"),
            "artifacts_on_disk": have_files,
            "build_attempts": len(builds),
            "model_chose_params": bool(trace and trace[-1].get("mapped")),
            "fabricated_before_any_build": [c["turn"] for c in premature],
            "misquoted_volume_turns": [c["turn"] for c in mismatched],
            "stuck_repetition": bool(stuck),
            "params": last.get("built_params")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="virtu-toolcall:latest")
    ap.add_argument("--turns", type=int, default=6)
    ap.add_argument("--nudges", type=int, default=2,
                    help="corrections issued when the model tries to finish without an executed build")
    ap.add_argument("--temperature", type=float, default=0.2)
    ap.add_argument("--num-ctx", dest="num_ctx", type=int, default=8192,
                    help="measured: contract + 2 masked demonstrations + 14 tool schemas "
                         "is a 5.4k-token prompt, so 4096 aborts the run at turn 1")
    ap.add_argument("--max-num-ctx", dest="max_num_ctx", type=int, default=12288,
                    help="upper bound for the automatic escalation when Ollama rejects a turn "
                         "as larger than the context (each doubling costs KV-cache RAM)")
    ap.add_argument("--num-predict", dest="num_predict", type=int, default=512)
    ap.add_argument("--gen-retries", dest="gen_retries", type=int, default=2,
                    help="extra attempts with a doubled token budget when the tool-call JSON is truncated")
    ap.add_argument("--model-retries", dest="model_retries", type=int, default=1,
                    help="extra attempts when the model endpoint itself fails (connection reset, "
                         "timeout, 5xx) - measured 2026-11-03: one dropped socket cost a whole arm")
    ap.add_argument("--retry-wait", dest="retry_wait", type=float, default=5.0,
                    help="seconds to wait before retrying a failed model turn")
    ap.add_argument("--model-timeout", dest="model_timeout", type=int, default=600)
    ap.add_argument("--build-timeout", dest="build_timeout", type=int, default=900)
    ap.add_argument("--sw-timeout", dest="sw_timeout", type=float, default=300.0)
    ap.add_argument("--step-delay", dest="step_delay", type=float, default=3.0)
    ap.add_argument("--entity-delay", dest="entity_delay", type=float, default=0.5)
    ap.add_argument("--keep-alive", dest="keep_alive", default="10m")
    ap.add_argument("--tools-scope", dest="tools_scope", choices=["full", "cad"], default="full")
    ap.add_argument("--drawing", dest="drawing", action="store_true", default=False)
    ap.add_argument("--min-free-gb", dest="min_free_gb", type=float, default=1.6,
                    help="free RAM required with the model resident; measured on this box: a build "
                         "completed at 1.19 GB free, while the run that started at 0.77 GB free "
                         "lost SOLIDWORKS mid-feature (2 of 5 features built), so 0.8 was too low")
    ap.add_argument("--build-retries", dest="build_retries", type=int, default=1,
                    help="extra executor attempts after SOLIDWORKS dies mid-build "
                         "(each recycles a wedged instance and re-runs one build)")
    ap.add_argument("--repeat-limit", dest="repeat_limit", type=int, default=3,
                    help="stop the run when the same assistant turn is emitted this many times")
    ap.add_argument("--no-prewarm", dest="prewarm", action="store_false", default=True)
    ap.add_argument("--force", action="store_true", default=False,
                    help="run even when the resource preflight fails (verdict then flagged)")
    ap.add_argument("--evict-pinned", dest="evict_pinned", action="store_true", default=False,
                    help="unload models another session pinned with keep_alive=-1; by default "
                         "those are left resident (this box runs several jobs on one Ollama)")
    ap.add_argument("--recycle-wedged", dest="recycle_wedged", action="store_true", default=True,
                    help="taskkill a SLDWORKS.exe that answers no COM and shows no window")
    ap.add_argument("--no-recycle-wedged", dest="recycle_wedged", action="store_false")
    ap.add_argument("--screenshots", dest="screenshots", action="store_true", default=True)
    ap.add_argument("--no-screenshots", dest="screenshots", action="store_false")
    ap.add_argument("--sanitize-schema", dest="sanitize_schema", action="store_true", default=True,
                    help="strip copyable example numbers out of the tool descriptions "
                         "(they are the original measured failure: the model transcribed them)")
    ap.add_argument("--no-sanitize-schema", dest="sanitize_schema", action="store_false")
    ap.add_argument("--fewshot", type=int, default=0, help="repair records injected as demonstrations")
    ap.add_argument("--corpus", default=os.path.join(ROOT, "data", "repair_toolcall.jsonl"))
    ap.add_argument("--tag", default="run", help="suffix for the supervision log of this arm")
    ap.add_argument("--task", default=None, help="override the supervision task text")
    ap.add_argument("--require-annotation", dest="require_annotation", action="store_true",
                    default=False,
                    help="the pass also needs verified dimensions and notes on the "
                         "drawing sheet; switches the task brief to model+annotate "
                         "unless --task overrides it")
    ap.add_argument("--contract", action="store_true", default=False,
                    help="append the numeric repair contract to the system prompt")
    ap.add_argument("--think", dest="think", action="store_true", default=None,
                    help="force thinking (CoT reasoning) in tool turns")
    ap.add_argument("--no-think", dest="think", action="store_false",
                    help="disable thinking in tool turns")
    a = ap.parse_args()
    sys.exit(supervisor(a))


if __name__ == "__main__":
    main()
