# -*- coding: utf-8 -*-
"""Watchable SOLIDWORKS 2021 flange modelling demo.

Split roles because a hung COM call cannot be interrupted from Python:
  parent  -> supervises the child, screenshots the SOLIDWORKS window by PID
  worker  -> owns the single COM connection, builds one feature at a time

Usage:
    python scripts/sw_flange_demo.py                 # parent (spawns the worker)
    python scripts/sw_flange_demo.py --role worker    # child (started by parent)
"""

import argparse
import csv
import json
import math
import os
import re
import subprocess
import sys
import time

import pythoncom
from win32com.client import gencache

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "scratch", "flange_demo")
EVENTS = os.path.join(OUT_DIR, "events.jsonl")
RESULT = os.path.join(OUT_DIR, "worker_result.json")
CAPTURES = os.path.join(OUT_DIR, "capture_manifest.jsonl")
SW_EXE = r"D:\SOLIDWORKS (2)\SLDWORKS.exe"
TPL_DIR = r"C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2021\templates"
DRW_TPL = os.path.join(TPL_DIR, "gb_a3.drwdot")

TLB_GUID = "{83A33D31-27C5-11CE-BFD4-00400513BB57}"
TLB_VERSION = 29
MM = 0.001  # every SOLIDWORKS linear argument is metres

# GB/T 9119 DN50 PN16 slip-on flange, hub and bore as designed by the agent
P = {
    "D_outer": 160.0,
    "t_base": 18.0,
    "D_hub": 90.0,
    "H_total": 30.0,
    "D_bore": 50.0,
    "PCD": 125.0,
    "n_bolts": 4,
    "D_bolt": 18.0,
    "chamfer": 2.0,
}


def analytic_dv(params=None):
    """Expected per-feature volume deltas in mm^3 from first principles."""
    q = params or P
    r_o, r_h, r_b, r_l = (q["D_outer"] / 2, q["D_hub"] / 2, q["D_bore"] / 2, q["D_bolt"] / 2)
    c, t, h = q["chamfer"], q["t_base"], q["H_total"]
    return {
        "base_disk": math.pi * r_o ** 2 * t,
        "hub_boss": math.pi * r_h ** 2 * (h - t),
        "bore_cut": -math.pi * r_b ** 2 * h,
        "bolt_holes": -q["n_bolts"] * math.pi * r_l ** 2 * t,
        "bore_chamfer": -2 * math.pi * (r_b * c ** 2 / 2 + c ** 3 / 6),
    }


def resolve_params(raw):
    """Merge caller-supplied dimensions (e.g. chosen by the model) over the defaults."""
    params = dict(P)
    if not raw:
        return params, []
    supplied = json.loads(raw)
    if not isinstance(supplied, dict):
        raise ValueError("params must be a JSON object")
    unknown = [k for k in supplied if k not in params]
    for k, v in supplied.items():
        if k in params:
            params[k] = int(v) if k == "n_bolts" else float(v)
    return params, unknown


def validate(q):
    """Engineering sanity: refuse a flange that cannot be machined as specified."""
    bad = []
    for k in ("D_outer", "t_base", "D_hub", "H_total", "D_bore", "PCD", "D_bolt", "chamfer"):
        if not (float(q[k]) > 0):
            bad.append("%s must be > 0 mm (got %s)" % (k, q[k]))
    if int(q["n_bolts"]) < 2:
        bad.append("n_bolts must be >= 2 (got %s)" % q["n_bolts"])
    if not (q["D_bore"] < q["D_hub"] < q["D_outer"]):
        bad.append("need D_bore < D_hub < D_outer (got %s / %s / %s)"
                   % (q["D_bore"], q["D_hub"], q["D_outer"]))
    if not (q["H_total"] > q["t_base"]):
        bad.append("need H_total > t_base (got %s > %s)" % (q["H_total"], q["t_base"]))
    rim = q["D_outer"] / 2 - (q["PCD"] / 2 + q["D_bolt"] / 2)
    if rim < 2.0:
        bad.append("bolt holes break out of the rim: edge web only %.2f mm, need >= 2 mm" % rim)
    gap = q["PCD"] / 2 - q["D_bolt"] / 2 - q["D_hub"] / 2
    if gap < 1.0:
        bad.append("bolt holes undercut the hub: clearance only %.2f mm, need >= 1 mm" % gap)
    if q["chamfer"] >= min((q["D_hub"] - q["D_bore"]) / 2, q["t_base"], q["H_total"] - q["t_base"]):
        bad.append("chamfer %s mm is larger than the geometry it must fit on" % q["chamfer"])
    if sum(analytic_dv(q).values()) <= 0:
        bad.append("specified flange has non-positive analytic volume")
    return bad


def safe_name(raw):
    """Artifact names come from model output: keep them to a plain file stem."""
    keep = re.sub(r"[^A-Za-z0-9_.-]", "_", str(raw or "").strip())[:40].strip("._-")
    return keep or "Flange"


# ------------------------------------------------------------------ shared bits
def sw_pids():
    """PIDs of every SLDWORKS.exe on the host (tasklist prints GBK on this box)."""
    try:
        p = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq SLDWORKS.exe", "/NH", "/FO", "CSV"],
            capture_output=True, timeout=20,
        )
        rows = list(csv.reader([l for l in (p.stdout or b"").decode("gbk", "ignore").splitlines() if l]))
        return [int(r[1]) for r in rows if r and r[0].upper().startswith("SLDWORKS") and len(r) > 1]
    except Exception:
        return []


class Log:
    def __init__(self, path):
        self.path = path
        self.seq = 0

    def ev(self, **kw):
        self.seq += 1
        kw["seq"] = self.seq
        kw["t"] = round(time.time(), 3)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(kw, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())


# ------------------------------------------------------------------ worker
def measure(part):
    mp = part.Extension.CreateMassProperty()
    com = [0.0, 0.0, 0.0]
    try:
        raw = mp.CenterOfMass
        com = [(raw[i] or 0.0) * 1000.0 for i in range(3)]
    except Exception:
        pass
    return {
        "volume_mm3": (mp.Volume or 0.0) * 1e9,
        "surface_mm2": (mp.SurfaceArea or 0.0) * 1e6,
        "mass_kg": mp.Mass or 0.0,
        "com_mm": [round(v, 3) for v in com],
    }


def walk_features(part, mod):
    """Return early-bound IFeature objects; the raw returns are late-bound and
    cannot resolve GetTypeName2 (it comes back as a plain string)."""
    out, raw = [], part.FirstFeature()
    while raw is not None:
        feat = mod.IFeature(raw._oleobj_)
        out.append(feat)
        raw = feat.GetNextFeature()
    return out


def sketch_names(part, mod):
    return [f.Name for f in walk_features(part, mod) if f.GetTypeName2() == "ProfileFeature"]


def reference_planes(part, mod):
    return [f.Name for f in walk_features(part, mod) if f.GetTypeName2() == "RefPlane"]


def open_sketch(part, plane, log):
    part.ClearSelection2(True)
    sel = part.Extension.SelectByID2(plane, "PLANE", 0.0, 0.0, 0.0, False, 1, None, 0)
    log.ev(ev="select_plane", plane=plane, ok=bool(sel))
    part.SketchManager.InsertSketch(True)
    part.ClearSelection2(True)


def close_sketch(part, mod, used, log, tag):
    part.ClearSelection2(True)
    part.SketchManager.InsertSketch(True)
    part.ClearSelection2(True)
    names = sketch_names(part, mod)
    if not names:
        raise RuntimeError("no ProfileFeature found after sketch")
    name = names[-1]
    if name in used:
        raise RuntimeError("sketch name did not advance: " + name)
    used.add(name)
    log.ev(ev="sketch_closed", tag=tag, sketch=name, total_sketches=len(names))
    return name


def select_sketch(part, name, log):
    ok = part.Extension.SelectByID2(name, "SKETCH", 0.0, 0.0, 0.0, False, 0, None, 0)
    log.ev(ev="select_sketch", sketch=name, ok=bool(ok))
    return ok


def boss(part, depth_m, reverse):
    return part.FeatureManager.FeatureExtrusion3(
        True, False, reverse, 0, 0, depth_m, 0.0,
        False, False, False, False, 0.0, 0.0,
        False, False, False, False, True, True, True, 0, 0.0, False)


def through_cut(part, sd, reverse):
    """FeatureCut3 with the flag set measured on this box: NormalCut=False and
    UseFeatScope=True (an unscoped cut with no body selected returns Nothing here),
    and Dir=True is the direction that meets material extruded toward +Z."""
    return part.FeatureManager.FeatureCut3(
        sd, False, reverse, 1, 0, 0.0, 0.0,
        False, False, False, False, 0.0, 0.0,
        False, False, False, False, False, True, True,
        False, False, False, 0, 0.0, False)


def view(part, name, view_id, log):
    try:
        part.ShowNamedView2(name, view_id)
        part.ViewZoomtofit2()
        log.ev(ev="view", name=name)
    except Exception as e:
        log.ev(ev="view_failed", name=name, err=str(e))


def sheet_view_count(dm, mod):
    """Ground truth for 'the sheet holds views': 1 = bare sheet, N+1 = N placed views.
    CreateDrawViewFromModelView3's return value is not trustworthy; the chain is."""
    root = dm.GetFirstView()
    if root is None:
        return 0
    n, raw = 0, root
    while raw is not None and n < 40:
        v = mod.IView(raw._oleobj_)
        n += 1
        raw = v.GetNextView()
    return n


def wrap(obj, iface, mod, log):
    """Early-bind a live SOLIDWORKS pointer through the cached makepy module.

    GetTypeInfo() is not served by the live object on this box, so gencache's own
    detection paths fail; the generated class can still wrap the raw pointer.
    """
    if obj is None:
        return None
    try:
        bound = getattr(mod, iface)(obj._oleobj_)
        log.ev(ev="bind", iface=iface, how="early")
        return bound
    except Exception as e:
        log.ev(ev="bind", iface=iface, how="late", err=str(e))
        return obj


def _dismiss_sw_modal(pids, log=None, words=("确定", "ok")):
    """Click the whitelisted button of any SOLIDWORKS #32770 modal.

    Measured on this box: a fresh SLDWORKS.exe shows 'splash' plus a modal
    '工具栏信息不一致。将使用默认工具栏设定。' and stops there. While that modal is up,
    nothing is registered in the ROT and GetActiveObject keeps answering
    '操作无法使用' (-2147221021) no matter how long you wait.
    """
    import win32com.client  # noqa: F401  (keep import side effects identical)
    import win32gui
    import win32con
    import win32process
    hits = []
    pids = set(int(p) for p in pids)

    def cb(h, _):
        try:
            if not win32gui.IsWindowVisible(h) or win32gui.GetClassName(h) != "#32770":
                return True
            if win32process.GetWindowThreadProcessId(h)[1] not in pids:
                return True
            kids = []
            win32gui.EnumChildWindows(h, lambda c, _x: kids.append(c) or True, None)
            for b in kids:
                if win32gui.GetClassName(b) != "Button":
                    continue
                t = (win32gui.GetWindowText(b) or "").strip().lower().replace("&", "")
                if any(w in t for w in words):
                    win32gui.SendMessage(b, win32con.BM_CLICK, 0, 0)
                    hits.append({"dialog": (win32gui.GetWindowText(h) or "")[:80], "button": t})
                    break
        except Exception:
            pass
        return True

    try:
        win32gui.EnumWindows(cb, None)
    except Exception:
        pass
    if hits and log:
        log.ev(ev="dismiss_sw_modal", dialogs=hits)
    return hits


def _wait_sw_rot(deadline, log=None, pids=None):
    """Poll GetActiveObject, then the ROT, until a SOLIDWORKS automation object answers."""
    import win32com.client
    raw, channel, err = None, None, None
    while time.time() < deadline:
        if pids:
            _dismiss_sw_modal(pids, log)
        try:
            raw = win32com.client.GetActiveObject("SldWorks.Application")
            channel = "GetActiveObject"
        except Exception as e:
            err = str(e)
        if raw is None:
            try:
                rot = pythoncom.GetRunningObjectTable()
                ctx = pythoncom.CreateBindCtx(0)
                for mon in rot.EnumRunning():
                    try:
                        nm = mon.GetDisplayName(ctx)
                    except Exception:
                        continue
                    if "sldworks" in nm.lower():
                        ob = mon.BindToObject(ctx, None, pythoncom.IID_IDispatch)
                        raw = win32com.client.Dispatch(ob)
                        channel = "rot:" + nm
                        break
            except Exception as e:
                err = str(e)
        if raw is not None:
            break
        time.sleep(3.0)
    return raw, channel, err


def visible_windows(pid):
    """Top-level visible windows owned by pid - a stalled SOLIDWORKS has none."""
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _lparam):
        try:
            if user32.IsWindowVisible(hwnd):
                pid_out = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_out))
                if pid_out.value == pid:
                    l, t, r, b = wintypes.RECT(), 0, 0, 0
                    user32.GetWindowRect(hwnd, ctypes.byref(l))
                    if (l.right - l.left) > 200 and (l.bottom - l.top) > 200:
                        found.append((hwnd, l.right - l.left, l.bottom - l.top))
        except Exception:
            pass
        return True

    user32.EnumWindows(cb, 0)
    return found


def attach_or_launch(log, args):
    """Never a second SOLIDWORKS: process table first, then Popen + ROT attach.

    A pid on the process table is not proof of a usable session: an orphaned
    instance with no window and no ROT entry (left behind by a killed build)
    makes every COM call hang until the startup timeout. Such an instance is
    killed and replaced instead of silently burning the whole build budget.
    """
    import win32com.client
    before = sorted(set(sw_pids()))
    log.ev(ev="probe_process_table", pids_before=before, launched_by_us=(not before))
    raw = channel = err = None
    pids, launched = [], False
    if before:
        pids, launched = before, False
        raw, channel, err = _wait_sw_rot(time.time() + min(30.0, args.sw_startup_timeout),
                                         log, pids=before)
        if raw is None:
            log.ev(ev="stale_instance", pids=before, err=err)
            for pid in before:
                try:
                    subprocess.run(["taskkill", "/PID", str(pid), "/F", "/T"],
                                   capture_output=True, timeout=15)
                except Exception:
                    pass
            time.sleep(2.0)
            before = []
    if raw is None:
        if before:
            pids, launched = before, False
        else:
            proc = subprocess.Popen([SW_EXE], cwd=os.path.dirname(SW_EXE))
            deadline = time.time() + args.sw_startup_timeout
            pids = []
            while time.time() < deadline:
                pids = sorted(set(sw_pids()) - set(before))
                if pids:
                    break
                time.sleep(1.0)
            if not pids:
                raise RuntimeError("SLDWORKS.exe never appeared in the process table")
            launched = True
            log.ev(ev="launch", launcher_pid=proc.pid, sw_pid=pids[0])
        raw, channel, err = _wait_sw_rot(time.time() + args.sw_startup_timeout, log, pids=pids)
    if raw is None:
        wins = visible_windows(pids[0])
        raise RuntimeError("cannot attach to SOLIDWORKS pid %s after %.0fs: %s; "
                           "visible top-level windows=%d (0 means the UI never finished "
                           "starting, so COM will not answer)" % (pids[0], args.sw_startup_timeout,
                                                                  err, len(wins)))

    mod = gencache.GetModuleForProgID("SldWorks.Application")
    sw = wrap(raw, "ISldWorks", mod, log)
    sw.Visible = True
    try:
        revision = sw.RevisionNumber()
    except Exception:
        revision = None
    log.ev(ev="connect", sw_pid=pids[0], launched_by_us=launched, channel=channel,
           revision=revision, pyclass=type(sw).__name__)
    return sw, pids[0], launched, mod


def worker(args):
    os.makedirs(OUT_DIR, exist_ok=True)
    for stale in (EVENTS, RESULT):
        if os.path.exists(stale):
            os.remove(stale)
    log = Log(EVENTS)
    try:
        params, unknown = resolve_params(args.params)
    except Exception as e:
        out = {"status": "rejected", "error": "unparsable params: %s" % e}
        log.ev(ev="abort", reason=out["error"])
        json.dump(out, open(RESULT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        return 3
    violations = validate(params)
    if unknown:
        violations.append("unknown dimension keys ignored: %s" % ",".join(sorted(unknown)))
    if violations:
        out = {"status": "rejected", "requested": params, "violations": violations,
               "unknown_keys": unknown}
        log.ev(ev="params_rejected", violations=violations)
        json.dump(out, open(RESULT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        return 3
    P = params
    dv = analytic_dv(P)
    out = {"params": P, "expected_dv_mm3": {k: round(v, 3) for k, v in dv.items()},
           "steps": [], "status": "incomplete"}
    log.ev(ev="params_accepted", source="model" if args.params else "default", **P)

    pythoncom.CoInitialize()
    gencache.EnsureModule(TLB_GUID, 0, TLB_VERSION, 0)
    log.ev(ev="typelib", module=gencache.GetModuleForProgID("SldWorks.Application").__name__)

    try:
        sw, sw_pid, launched, mod = attach_or_launch(log, args)
    except Exception as e:
        out.update(status="blocked", error="%s: %s" % (type(e).__name__, e))
        log.ev(ev="abort", reason=out["error"])
        json.dump(out, open(RESULT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        return 2

    part = wrap(sw.NewPart(), "IModelDoc2", mod, log)
    if part is None:
        out.update(status="blocked", reason="NewPart returned Nothing")
        log.ev(ev="abort", reason=out["reason"])
        json.dump(out, open(RESULT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        return 2
    planes = reference_planes(part, mod)
    plane = next((n for n in planes if n in (u"\u524d\u89c6\u57fa\u51c6\u9762", "Front Plane")),
                 planes[0] if planes else None)
    if plane is None:
        out.update(status="blocked", reason="no reference plane in new part")
        log.ev(ev="abort", reason=out["reason"])
        json.dump(out, open(RESULT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        return 2
    log.ev(ev="new_part", title=part.GetTitle(), planes=planes, plane_used=plane)
    out["part_title"] = part.GetTitle()
    out["plane_used"] = plane
    out["planes"] = planes
    used_sketches = set()

    def record(tag, before_v, after_v, extra=None):
        step = {"tag": tag, "volume_mm3": after_v, "dv_mm3": after_v - before_v,
                "expected_dv_mm3": dv.get(tag), "com_mm": None}
        if extra:
            step.update(extra)
        return step

    prev_v = 0.0
    try:
        view(part, "*Isometric", 7, log)
        time.sleep(args.step_delay)

        # ---- 1. base disc -------------------------------------------------
        open_sketch(part, plane, log)
        part.SketchManager.CreateCircleByRadius(0.0, 0.0, 0.0, P["D_outer"] / 2 * MM)
        time.sleep(args.entity_delay)
        sk = close_sketch(part, mod, used_sketches, log, "base_disk")
        select_sketch(part, sk, log)
        f1 = boss(part, P["t_base"] * MM, False)
        part.ForceRebuild3(False)
        if f1 is None:
            raise RuntimeError("base extrusion returned no feature")
        m = measure(part)
        if m["com_mm"][2] < 0:  # disc grew toward -Z; redo mirrored so the stack goes +Z
            log.ev(ev="direction_mirror", tag="base_disk", com_z=m["com_mm"][2])
            part.EditUndo2(1)
            select_sketch(part, sk, log)
            f1 = boss(part, P["t_base"] * MM, True)
            part.ForceRebuild3(False)
            m = measure(part)
        log.ev(ev="feature", tag="base_disk", feat=(f1.Name if f1 else None), **m)
        out["steps"].append(record("base_disk", prev_v, m["volume_mm3"],
                                   {"feat": (f1.Name if f1 else None), "com_mm": m["com_mm"]}))
        prev_v = m["volume_mm3"]

        if args.probe_only:  # channel + geometry smoke test, nothing saved
            err_pct = 100.0 * (m["volume_mm3"] - dv["base_disk"]) / dv["base_disk"]
            out["probe"] = {"volume_mm3": round(m["volume_mm3"], 3),
                            "expected_mm3": round(dv["base_disk"], 3),
                            "err_pct": round(err_pct, 4)}
            out["status"] = "success" if abs(err_pct) <= 1.0 else "probe_mismatch"
            log.ev(ev="probe_done", err_pct=round(err_pct, 4), verdict=out["status"])
            try:
                sw.CloseDoc(part.GetTitle())
            except Exception as e:
                log.ev(ev="probe_close_failed", err=str(e))
            return 0
        view(part, "*Isometric", 7, log)
        time.sleep(args.step_delay)

        # ---- 2. raised hub ------------------------------------------------
        open_sketch(part, plane, log)
        part.SketchManager.CreateCircleByRadius(0.0, 0.0, 0.0, P["D_hub"] / 2 * MM)
        time.sleep(args.entity_delay)
        sk = close_sketch(part, mod, used_sketches, log, "hub_boss")
        select_sketch(part, sk, log)
        f2 = boss(part, P["H_total"] * MM, False)
        part.ForceRebuild3(False)
        m = measure(part)
        log.ev(ev="feature", tag="hub_boss", feat=(f2.Name if f2 else None), **m)
        out["steps"].append(record("hub_boss", prev_v, m["volume_mm3"],
                                   {"feat": (f2.Name if f2 else None), "com_mm": m["com_mm"]}))
        prev_v = m["volume_mm3"]
        view(part, "*Isometric", 7, log)
        time.sleep(args.step_delay)

        # ---- 3. bore ------------------------------------------------------
        open_sketch(part, plane, log)
        part.SketchManager.CreateCircleByRadius(0.0, 0.0, 0.0, P["D_bore"] / 2 * MM)
        time.sleep(args.entity_delay)
        sk = close_sketch(part, mod, used_sketches, log, "bore_cut")
        select_sketch(part, sk, log)
        feat, chosen, m = None, None, None
        for sd, rev in ((True, True), (True, False), (False, True)):
            select_sketch(part, sk, log)
            cand = through_cut(part, sd, rev)
            part.ForceRebuild3(False)
            trial = measure(part)
            if cand is not None and trial["volume_mm3"] < prev_v - 1.0:
                feat, chosen, m = cand, (sd, rev), trial
                break
            log.ev(ev="cut_retry", tag="bore_cut", tried=[sd, rev],
                   got_none=(cand is None), volume=trial["volume_mm3"], prev=prev_v)
            if cand is not None:
                part.EditUndo2(1)  # only roll back a feature that really exists
        if feat is None:
            raise RuntimeError("bore cut never removed material")
        log.ev(ev="feature", tag="bore_cut", flags=list(chosen), feat=feat.Name, **m)
        out["steps"].append(record("bore_cut", prev_v, m["volume_mm3"],
                                   {"feat": feat.Name, "cut_flags": list(chosen), "com_mm": m["com_mm"]}))
        prev_v = m["volume_mm3"]
        view(part, "*Isometric", 7, log)
        time.sleep(args.step_delay)

        # ---- 4. bolt holes on the bolt circle ----------------------------
        open_sketch(part, plane, log)
        r_pcd, r_bolt = P["PCD"] / 2 * MM, P["D_bolt"] / 2 * MM
        part.SketchManager.CreateCenterLine(-r_pcd * 1.25, 0.0, 0.0, r_pcd * 1.25, 0.0, 0.0)
        time.sleep(args.entity_delay)
        part.SketchManager.CreateCenterLine(0.0, -r_pcd * 1.25, 0.0, 0.0, r_pcd * 1.25, 0.0)
        time.sleep(args.entity_delay)
        for i in range(P["n_bolts"]):
            a = 2 * math.pi * i / P["n_bolts"]
            part.SketchManager.CreateCircleByRadius(r_pcd * math.cos(a), r_pcd * math.sin(a), 0.0, r_bolt)
            time.sleep(args.entity_delay)
        sk = close_sketch(part, mod, used_sketches, log, "bolt_holes")
        select_sketch(part, sk, log)
        feat, chosen, m = None, None, None
        for sd, rev in ((True, True), (True, False), (False, True)):
            select_sketch(part, sk, log)
            cand = through_cut(part, sd, rev)
            part.ForceRebuild3(False)
            trial = measure(part)
            if cand is not None and trial["volume_mm3"] < prev_v - 1.0:
                feat, chosen, m = cand, (sd, rev), trial
                break
            log.ev(ev="cut_retry", tag="bolt_holes", tried=[sd, rev],
                   got_none=(cand is None), volume=trial["volume_mm3"], prev=prev_v)
            if cand is not None:
                part.EditUndo2(1)  # only roll back a feature that really exists
        if feat is None:
            raise RuntimeError("bolt-hole cut never removed material")
        log.ev(ev="feature", tag="bolt_holes", flags=list(chosen), feat=feat.Name, **m)
        out["steps"].append(record("bolt_holes", prev_v, m["volume_mm3"],
                                   {"feat": feat.Name, "cut_flags": list(chosen), "com_mm": m["com_mm"]}))
        prev_v = m["volume_mm3"]
        view(part, "*Isometric", 7, log)
        time.sleep(args.step_delay)

        # ---- checkpoint: required geometry done -> persist before decoration --
        part.ClearSelection2(True)
        stem = safe_name(args.part_name)
        sldprt = os.path.join(args.out_dir, stem + ".SLDPRT")
        step = os.path.join(args.out_dir, stem + ".STEP")
        for pth in (sldprt, step):
            if os.path.exists(pth):
                os.remove(pth)
        ck = part.SaveAs3(sldprt, 0, 2)
        log.ev(ev="checkpoint_save", rc=ck, path=sldprt, exists=os.path.exists(sldprt))
        out["checkpoint_volume_mm3"] = prev_v
        time.sleep(args.entity_delay)

        # ---- 5. chamfer on the bore crest (candidate ladder, dV decides) ---
        if args.chamfer:
            c = P["chamfer"]
            z_top = P["H_total"] * MM
            r_bore = P["D_bore"] / 2 * MM
            want = dv["bore_chamfer"]
            fm = part.FeatureManager
            cands = [
                # legacy FeatureChamfer's Angle is RADIANS on this box: passing 45.0
                # measured dV -522.44, i.e. a 58.33 deg chamfer, not the 45 deg one
                ("ModelDoc2.FeatureChamfer 45deg",
                 lambda: part.FeatureChamfer(c * MM, math.radians(45.0), False)),
                ("InsertFeatureChamfer o=0 t=0 45deg",
                 lambda: fm.InsertFeatureChamfer(0, 0, c * MM, 45.0, 0.0, 0.0, 0.0, 0.0)),
                ("InsertFeatureChamfer o=0 t=0 rad",
                 lambda: fm.InsertFeatureChamfer(0, 0, c * MM, math.radians(45.0), 0.0, 0.0, 0.0, 0.0)),
                ("InsertFeatureChamfer o=0 t=1 two-dist",
                 lambda: fm.InsertFeatureChamfer(0, 1, c * MM, 0.0, c * MM, 0.0, 0.0, 0.0)),
                ("ModelDoc2.FeatureChamferType t=0",
                 lambda: part.FeatureChamferType(0, c * MM, math.radians(45.0), False, 0.0, 0.0, 0.0, 0.0)),
            ]
            m, applied = None, False
            for label, fn in cands:
                part.ClearSelection2(True)
                try:
                    sel = bool(part.Extension.SelectByID2("", "EDGE", r_bore, 0.0, z_top,
                                                          False, 0, None, 0))
                except Exception as e:
                    sel = False
                    log.ev(ev="chamfer_pick_error", cand=label, err=str(e)[:80])
                if not sel:
                    log.ev(ev="chamfer_pick_failed", cand=label, at=[r_bore, 0.0, z_top])
                    break
                try:
                    cand = fn()
                except Exception as e:
                    log.ev(ev="chamfer_try", cand=label, exc=str(e)[:80])
                    continue
                part.EditRebuild3()
                part.ForceRebuild3(False)
                trial = measure(part)
                got = trial["volume_mm3"] - prev_v
                hit = got < 0 and abs(got - want) <= abs(want) * 0.05
                log.ev(ev="chamfer_try", cand=label, returned=cand is not None,
                       dv=round(got, 3), expected=round(want, 3), accepted=hit)
                if hit:
                    applied, m = True, trial
                    break
                # judge by geometry, never by the return value: a call can hand back
                # Nothing and still have cut material, which then must be rolled back
                if cand is not None or abs(got) > 1.0:
                    part.EditUndo2(1)
            if applied:
                tree = walk_features(part, mod)
                name = tree[-1].Name if tree else None
                log.ev(ev="feature", tag="bore_chamfer", feat=name, **m)
                out["steps"].append(record("bore_chamfer", prev_v, m["volume_mm3"],
                                           {"feat": name, "com_mm": m["com_mm"]}))
                prev_v = m["volume_mm3"]
            else:
                m = measure(part)
                log.ev(ev="chamfer_rolled_back", reason="no candidate matched the analytic dV",
                       volume=round(m["volume_mm3"], 3))
                out["steps"].append({"tag": "bore_chamfer", "skipped": True})
            view(part, "*Isometric", 7, log)
            time.sleep(args.step_delay)

        # ---- 6. final save + neutral STEP export --------------------------
        part.ClearSelection2(True)
        saved = part.SaveAs3(sldprt, 0, 2)
        log.ev(ev="save", kind="sldprt", rc=saved, path=sldprt, exists=os.path.exists(sldprt))
        time.sleep(1.0)
        try:
            exported = part.SaveAs3(step, 0, 2)
        except Exception as e:
            exported = None
            log.ev(ev="save_error", kind="step", err=str(e))
        log.ev(ev="save", kind="step", rc=exported, path=step, exists=os.path.exists(step))
        out["artifacts"] = {"sldprt": sldprt if os.path.exists(sldprt) else None,
                            "step": step if os.path.exists(step) else None}
        time.sleep(args.entity_delay)

        # ---- 7. presentation tour -----------------------------------------
        for nm, vid in (("*Front", 1), ("*Top", 5), ("*Right", 4), ("*Isometric", 7)):
            view(part, nm, vid, log)
            time.sleep(min(args.step_delay, 2.5))

        final = measure(part)
        out["final"] = final
        expected_total = sum(s.get("expected_dv_mm3") or 0.0 for s in out["steps"])
        out["expected_total_mm3"] = round(expected_total, 3)
        out["volume_error_pct"] = 100.0 * (final["volume_mm3"] - expected_total) / expected_total
        log.ev(ev="final", **final, volume_error_pct=round(out["volume_error_pct"], 4),
               expected_total_mm3=round(expected_total, 3))

        # ---- 8. engineering drawing (best effort, after the part is safe) --
        if args.drawing and os.path.exists(sldprt):
            try:
                raw_d = sw.NewDocument(DRW_TPL, 0, 0.0, 0.0)  # form measured on this box
                if raw_d is None:
                    raise RuntimeError("NewDocument returned Nothing for the drawing template")
                d = mod.IDrawingDoc(raw_d._oleobj_)
                dmod = mod.IModelDoc2(raw_d._oleobj_)  # IDrawingDoc wrapper carries no IModelDoc2 methods
                log.ev(ev="drawing_created", title=dmod.GetTitle())
                # this box is a Chinese SOLIDWORKS: saved view orientation names are localized
                # ("*Front" silently places nothing); gate on the sheet view chain, not the return value
                titles = [str(part.GetTitle()), os.path.basename(sldprt),
                          os.path.splitext(os.path.basename(sldprt))[0], sldprt]
                wanted = [(u"*\u524d\u89c6", "*Front", 0.12, 0.20),
                          (u"*\u4e0a\u89c6", "*Top", 0.12, 0.09),
                          (u"*\u7b49\u8f74\u6d4b", "*Isometric", 0.30, 0.15)]
                placed = []
                for cjk, en, x, y in wanted:
                    before = sheet_view_count(d, mod)
                    got = None
                    for nm in (cjk, en):
                        if got:
                            break
                        for mname in titles:
                            try:
                                d.CreateDrawViewFromModelView3(mname, nm, x, y, 0.0)
                            except Exception:
                                continue
                            after = sheet_view_count(d, mod)
                            if after > before:
                                got = {"view": nm, "model": mname, "chain": after}
                                break
                    placed.append(got or {"view": None, "model": None, "chain": before})
                    log.ev(ev="draw_view", want=cjk, ok=got is not None, **(got or {}))
                    try:
                        dmod.ViewZoomtofit2()
                    except Exception:
                        pass
                    time.sleep(args.step_delay)
                drw_path = os.path.join(args.out_dir, stem + ".SLDDRW")
                if args.anno_spec:
                    # dimensions and detail notes are the deliverable here; the sheet is
                    # re-enumerated afterwards, so this reports what is really on it
                    try:
                        import sw_drawing_annotate as A
                        spec = json.loads(args.anno_spec)
                        out["drawing_annotations"] = A.annotate(d, dmod, mod, log, args, P, spec)
                        log.ev(ev="annotations_read_back",
                               **out["drawing_annotations"]["summary"])
                    except Exception as e:
                        out["drawing_annotations"] = {"failed": "%s: %s" % (type(e).__name__, e)}
                        log.ev(ev="annotation_failed", err=str(e)[:200])
                dmod.SaveAs3(drw_path, 0, 2)
                out["drawing"] = {"views": placed, "views_placed": sum(1 for p in placed if p["view"]),
                                  "path": drw_path, "exists": os.path.exists(drw_path),
                                  "sheet_chain": sheet_view_count(d, mod)}
                log.ev(ev="drawing_saved", **out["drawing"])
            except Exception as e:
                out["drawing"] = {"failed": "%s: %s" % (type(e).__name__, e)}
                log.ev(ev="drawing_failed", err=out["drawing"]["failed"])

        if args.close_after_save:
            # an unsupervised chain that builds repeatedly must not leave every part
            # open in the same SOLIDWORKS - the accumulated documents are what
            # eventually killed the app mid-build on this 16 GB box
            try:
                sw.CloseDoc(part.GetTitle())
                log.ev(ev="doc_closed", title=part.GetTitle())
            except Exception as e:
                log.ev(ev="doc_close_failed", err=str(e)[:100])

        out["status"] = "success"
    except Exception as e:
        out["error"] = "%s: %s" % (type(e).__name__, e)
        log.ev(ev="worker_exception", err=out["error"])
        if args.close_after_save:
            # the failure path leaked exactly the documents that pile up and wedge the app:
            # a half-built part left open is worse than no artifact at all
            try:
                out["abandoned_doc"] = part.GetTitle()
                sw.CloseDoc(out["abandoned_doc"])
                log.ev(ev="doc_closed", title=out["abandoned_doc"], after="failure")
            except Exception as ce:
                log.ev(ev="doc_close_failed", err=str(ce)[:100])
    finally:
        json.dump(out, open(RESULT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return 0 if out["status"] == "success" else 1


# ------------------------------------------------------------------ parent
def find_window_for_pid(pid):
    import win32gui
    import win32process
    best = None
    area = 0

    def cb(hwnd, _):
        nonlocal best, area
        try:
            if not win32gui.IsWindowVisible(hwnd):
                return True
            _, wpid = win32process.GetWindowThreadProcessId(hwnd)
            if wpid != pid:
                return True
            l, t, r, b = win32gui.GetWindowRect(hwnd)
            a = max(0, r - l) * max(0, b - t)
            if a > area and a > 100000:
                best, area = hwnd, a
        except Exception:
            pass
        return True

    try:
        win32gui.EnumWindows(cb, None)
    except Exception:
        pass
    return best


def frame_rect(hwnd):
    import ctypes
    from ctypes import wintypes
    import win32gui
    try:
        rect = wintypes.RECT()
        ctypes.windll.dwmapi.DwmGetWindowAttribute(
            wintypes.HWND(hwnd), ctypes.c_int(9), ctypes.byref(rect), ctypes.sizeof(rect))
        if rect.right > rect.left:
            return (rect.left, rect.top, rect.right, rect.bottom)
    except Exception:
        pass
    return win32gui.GetWindowRect(hwnd)


def raise_window(hwnd):
    import win32con
    import win32gui
    try:
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
        win32gui.BringWindowToTop(hwnd)
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        pass


def grab(hwnd, path):
    from PIL import ImageGrab, ImageStat
    l, t, r, b = frame_rect(hwnd)
    l, t = max(0, l), max(0, t)
    if r <= l or b <= t:
        return None
    im = ImageGrab.grab(bbox=(l, t, r, b), all_screens=True)
    im.save(path)
    st = ImageStat.Stat(im.convert("L"))
    return {"path": path, "w": im.size[0], "h": im.size[1],
            "mean": round(st.mean[0], 1), "stddev": round(st.stddev[0], 1)}


BUTTON_OK = (u"\u786e\u5b9a", u"OK", u"\u5173\u95ed", u"\u53d6\u6d88", u"\u662f", u"Yes", u"\u7ee7\u7eed")


def dismiss_dialogs(pid):
    """Whitelisted button click on #32770 dialogs owned by our own SOLIDWORKS PID."""
    import win32gui
    import win32process
    import win32con
    clicked = []

    def cb(hwnd, _):
        try:
            if not win32gui.IsWindowVisible(hwnd):
                return True
            _, wpid = win32process.GetWindowThreadProcessId(hwnd)
            if wpid != pid or win32gui.GetClassName(hwnd) != "#32770":
                return True

            def child(btn, _):
                if win32gui.GetClassName(btn) != "Button" or not win32gui.IsWindowVisible(btn):
                    return True
                cap = win32gui.GetWindowText(btn)
                if cap and any(w in cap for w in BUTTON_OK):
                    win32gui.PostMessage(btn, win32con.BM_CLICK, 0, 0)
                    clicked.append((hwnd, cap))
                return True

            win32gui.EnumChildWindows(hwnd, child, None)
        except Exception:
            pass
        return True

    try:
        win32gui.EnumWindows(cb, None)
    except Exception:
        pass
    return clicked


def parent(args):
    os.makedirs(OUT_DIR, exist_ok=True)
    for stale in (EVENTS, RESULT, CAPTURES):
        if os.path.exists(stale):
            os.remove(stale)
    cmd = [sys.executable, os.path.abspath(__file__), "--role", "worker",
           "--step-delay", str(args.step_delay), "--entity-delay", str(args.entity_delay),
           "--out-dir", OUT_DIR]
    cmd += ["--drawing"] if args.drawing else ["--no-drawing"]
    cmd += ["--chamfer"] if args.chamfer else ["--no-chamfer"]
    if args.params:
        cmd += ["--params", args.params]
    if getattr(args, "anno_spec", None):
        cmd += ["--anno-spec", args.anno_spec]
    if args.probe_only:
        cmd += ["--probe-only"]
    run_params, _ = resolve_params(args.params)
    exp_dv = analytic_dv(run_params)
    log_f = open(os.path.join(OUT_DIR, "worker_stdout.txt"), "w", encoding="utf-8")
    t0 = time.time()
    child = subprocess.Popen(cmd, cwd=ROOT, stdout=log_f, stderr=subprocess.STDOUT)
    print("[parent] worker pid=%d  step_delay=%.1fs  entity_delay=%.1fs"
          % (child.pid, args.step_delay, args.entity_delay), flush=True)

    seen, sw_pid, hwnd = 0, None, None
    last_v = 0.0
    last_event_at = time.time()
    timed_out = False
    while True:
        alive = child.poll() is None
        if os.path.exists(EVENTS):
            with open(EVENTS, encoding="utf-8") as f:
                lines = f.read().splitlines()
            while seen < len(lines):
                try:
                    ev = json.loads(lines[seen])
                except Exception:
                    ev = None
                seen += 1
                last_event_at = time.time()
                if not ev:
                    continue
                if ev.get("ev") == "connect":
                    sw_pid = ev.get("sw_pid")
                if ev.get("ev") in ("feature", "final", "draw_view", "abort", "worker_exception") and sw_pid:
                    if hwnd is None:
                        hwnd = find_window_for_pid(sw_pid)
                    if hwnd:
                        raise_window(hwnd)
                        time.sleep(0.4)
                        name = "%02d_%s.png" % (ev["seq"], ev.get("tag") or ev.get("ev") or "shot")
                        pth = os.path.join(OUT_DIR, "steps", name)
                        os.makedirs(os.path.dirname(pth), exist_ok=True)
                        try:
                            cap = grab(hwnd, pth)
                        except Exception as e:
                            cap = {"path": pth, "error": str(e)}
                        with open(CAPTURES, "a", encoding="utf-8") as cf:
                            cf.write(json.dumps({"seq": ev["seq"], "ev": ev.get("ev"),
                                                 "tag": ev.get("tag"), **(cap or {})},
                                                ensure_ascii=False) + "\n")
                        print("[shot ] %-14s -> %s" % (ev.get("tag") or ev.get("ev"),
                              (cap or {}).get("path")), flush=True)
                tag = ev.get("tag") or ev.get("ev")
                if ev.get("ev") == "feature":
                    exp = exp_dv.get(tag)
                    dv_measured = ev["volume_mm3"] - last_v
                    last_v = ev["volume_mm3"]
                    print("[geom ] %-14s V=%12.1f mm3  dV=%+11.1f  expected=%+11.1f"
                          % (tag, ev["volume_mm3"], dv_measured, exp if exp is not None else float("nan")),
                          flush=True)
                else:
                    print("[ev   ] %-16s %s" % (ev["ev"], json.dumps(
                        {k: v for k, v in ev.items() if k not in ("seq", "t", "ev")},
                        ensure_ascii=False)[:160]), flush=True)
        if not alive:
            break
        if sw_pid and time.time() - last_event_at > 12.0:
            hit = dismiss_dialogs(sw_pid)
            if hit:
                print("[watch] dismissed dialogs on SW pid %s: %s" % (sw_pid, hit), flush=True)
                last_event_at = time.time()
        if time.time() - t0 > args.timeout:
            timed_out = True
            subprocess.run(["taskkill", "/PID", str(child.pid), "/T", "/F"],
                           capture_output=True)
            break
        time.sleep(0.2)

    child_rc = child.poll()
    if child_rc is None:
        child.wait(timeout=30)
        child_rc = child.poll()
    log_f.close()
    res = {}
    if os.path.exists(RESULT):
        try:
            res = json.load(open(RESULT, encoding="utf-8"))
        except Exception as e:
            res = {"status": "unreadable_result", "error": str(e)}
    res["parent"] = {"child_rc": child_rc, "timed_out": timed_out,
                    "wall_s": round(time.time() - t0, 2), "sw_pid": sw_pid,
                    "events_seen": seen}
    json.dump(res, open(os.path.join(OUT_DIR, "run_manifest.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("\n[parent] rc=%s timed_out=%s wall=%.1fs status=%s"
          % (child_rc, timed_out, res["parent"]["wall_s"], res.get("status")), flush=True)
    return 0 if res.get("status") == "success" else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--role", default="parent", choices=["parent", "worker"])
    ap.add_argument("--step-delay", type=float, default=4.0)
    ap.add_argument("--entity-delay", type=float, default=0.7)
    ap.add_argument("--out-dir", default=OUT_DIR)
    ap.add_argument("--part-name", dest="part_name", default="Flange_DN50_PN16")
    ap.add_argument("--close-after-save", dest="close_after_save", action="store_true", default=False,
                    help="close the saved document so repeated builds do not pile up in one session")
    ap.add_argument("--timeout", type=float, default=900.0)
    ap.add_argument("--sw-startup-timeout", type=float, default=300.0)
    ap.add_argument("--drawing", dest="drawing", action="store_true", default=True)
    ap.add_argument("--no-drawing", dest="drawing", action="store_false")
    ap.add_argument("--chamfer", dest="chamfer", action="store_true", default=True)
    ap.add_argument("--no-chamfer", dest="chamfer", action="store_false")
    ap.add_argument("--probe-only", dest="probe_only", action="store_true", default=False)
    ap.add_argument("--params", default=None,
                    help="JSON object of dimensions (mm) chosen by the caller/model; validated before build")
    ap.add_argument("--anno-spec", dest="anno_spec", default=None,
                    help="JSON {\"dimensions\":[{\"target\":\"D_outer\"}],\"notes\":[...]} annotated "
                         "onto the drawing; the sheet is re-read afterwards, so the report is "
                         "measured rather than assumed")
    a = ap.parse_args()
    if a.role == "worker":
        sys.exit(worker(a))
    sys.exit(parent(a))


if __name__ == "__main__":
    main()
