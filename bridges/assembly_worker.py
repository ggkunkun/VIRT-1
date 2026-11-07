# -*- coding: utf-8 -*-
"""SolidWorks COM worker（独立子进程，可由父进程超时 taskkill）。

阶段：
  convert : 每件 STEP -> .SLDPRT，回读 体数/面数/包围盒/体积 作证据
  build   : 新建装配 -> AddComponent5 按 BOM 4x4 位姿插入 -> 真实配合
            -> 保存 .SLDASM -> 关闭重开核对组件变换/配合数
协议：argv[1] = spec JSON 路径；结果写 spec["result_path"]（原子替换）。
纪律：任何一步读不到证据都记 status=error/partial，绝不把 None 当成功。
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
import traceback
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pythoncom  # noqa: E402
import win32com.client as win32  # noqa: E402
from win32com.client import dynamic  # noqa: E402

SW_PREF_3D_INTERCONNECT = 691


def _errvar():
    return win32.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)


SW_EXE_CANDIDATES = (
    r"D:\SOLIDWORKS (2)\SLDWORKS.exe",
    r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\SLDWORKS.exe",
)


def _sw_running() -> bool:
    try:
        win32.GetActiveObject("SldWorks.Application")
        return True
    except Exception:
        return False


def connect() -> Any:
    """SW 必须先作为普通进程完成启动（splash ~40s）再绑定；
    在启动期调用 Dispatch/OpenDoc6 会被拒并拖死实例。"""
    import subprocess

    try:
        sw = win32.GetActiveObject("SldWorks.Application")
    except Exception:
        exe = next((p for p in SW_EXE_CANDIDATES if os.path.exists(p)), None)
        if not exe:
            raise RuntimeError("SLDWORKS.exe not found")
        subprocess.Popen([exe])
        sw = None
        for _ in range(90):
            time.sleep(2.0)
            try:
                sw = win32.GetActiveObject("SldWorks.Application")
                break
            except Exception:
                continue
        if sw is None:
            raise RuntimeError("SolidWorks did not register in ROT within 180s")
    sw.Visible = True
    stable = 0
    for _ in range(60):
        try:
            if _prop(sw, "RevisionNumber") and isinstance(int(_call(sw, "GetDocumentCount", default=-1)), int):
                stable += 1
                if stable >= 3:
                    return sw
        except Exception:
            stable = 0
        time.sleep(1.0)
    return sw


def _prop(obj, name, default=None):
    """SW 是 late-bound：部分方法在 pywin32 里表现为属性（GetTitle/GetType/...）。"""
    try:
        v = getattr(obj, name)
        return v() if callable(v) else v
    except Exception:
        return default


def _call(obj, name, *args, default=None):
    try:
        fn = getattr(obj, name)
        return fn(*args) if callable(fn) else default
    except Exception:
        return default


def _mm(v: float) -> float:
    return float(v) / 1000.0


def _bbox_mm(body) -> Optional[List[float]]:
    try:
        box = body.GetBodyBox()
        return [round((box[i + 3] - box[i]) * 1000.0, 3) for i in range(3)]
    except Exception:
        return None


def _face_count(body) -> Optional[int]:
    try:
        n, face = 0, body.GetFirstFace()
        while face is not None and n < 20000:
            n += 1
            face = face.GetNextFace()
        return n
    except Exception:
        return None


def _doc_mass(doc) -> Dict[str, Any]:
    try:
        mp = doc.GetMassProperties
        return {"volume_cm3": round(mp[3] * 1e6, 4), "area_cm2": round(mp[4] * 1e4, 4),
                "mass_kg": round(mp[5], 6)}
    except Exception as e:
        return {"error": type(e).__name__ + ": " + str(e)[:120]}


def _save(doc, path: str) -> Dict[str, Any]:
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass
    last = ""
    for attempt in (1, 2):
        try:
            doc.SaveAs3(path, 0, 1)
            time.sleep(1.0)
            size = os.path.getsize(path) if os.path.exists(path) else 0
            head = open(path, "rb").read(8) if size else b""
            if size > 10000 and head[4:8] == b"\x00\x00\x00\x04":
                return {"path": path, "bytes": size, "saved": True, "attempt": attempt}
            last = "size/format check failed (bytes=%d)" % size
        except Exception as e:  # noqa: BLE001
            last = type(e).__name__ + ": " + str(e)[:120]
    return {"path": path, "bytes": 0, "saved": False, "detail": last}


def _close(sw, doc) -> None:
    try:
        sw.CloseDoc(_prop(doc, "GetTitle", ""))
    except Exception:
        pass


def _disable_interconnect(sw) -> bool:
    try:
        was = bool(sw.GetUserPreferenceToggle(SW_PREF_3D_INTERCONNECT))
        if was:
            sw.SetUserPreferenceToggle(SW_PREF_3D_INTERCONNECT, False)
        return was
    except Exception:
        return False


def _restore_interconnect(sw, was: bool) -> None:
    if not was:
        return
    try:
        sw.SetUserPreferenceToggle(SW_PREF_3D_INTERCONNECT, True)
    except Exception:
        pass


def _open_with_out_params(sw, name: str, args: tuple, n_out: int):
    """OpenDoc6/LoadFile4 的 byref 出参在早绑定/晚绑定下类型不同：
    早绑定要普通 int，晚绑定要 VARIANT。逐种试，返回 (doc, style, raw, attempts)。"""
    attempts = []
    styles = [("int", [0] * n_out), ("variant", [_errvar() for _ in range(n_out)]),
              ("missing", [pythoncom.Missing] * n_out)]
    for style, outs in styles:
        try:
            r = getattr(sw, name)(*(tuple(args) + tuple(outs)))
            doc = r[0] if isinstance(r, tuple) and r else r
            return doc, style, r, attempts
        except Exception as e:  # noqa: BLE001
            attempts.append("%s/%s: %s: %s" % (name, style, type(e).__name__, str(e)[:90]))
    return None, "", None, attempts


def _active_doc(sw):
    for name in ("ActiveDoc", "IActiveDoc2"):
        d = _prop(sw, name)
        if d is not None:
            return d
    return None


def import_part(sw, step_path: str, out_path: str) -> Dict[str, Any]:
    stem = os.path.splitext(os.path.basename(step_path))[0].lower()
    doc = None
    opened_by, attempts = "", []
    before = _call(sw, "GetDocumentCount", default=0)
    for attempt in range(2):
        doc, style, _raw, att = _open_with_out_params(
            sw, "OpenDoc6", (step_path, 1, 1, ""), 2)
        if doc:
            opened_by = "OpenDoc6/" + style
        attempts.extend("try%d %s" % (attempt + 1, a) for a in att)
        if not doc:
            ifd = _call(sw, "GetImportFileData", step_path, default=None)
            if ifd is not None:
                doc, style, _raw, att = _open_with_out_params(
                    sw, "LoadFile4", (step_path, "", ifd), 1)
                if doc:
                    opened_by = "LoadFile4/" + style
                attempts.extend("try%d %s" % (attempt + 1, a) for a in att)
        for _ in range(30):
            if doc:
                break
            time.sleep(1.0)
            cand = _active_doc(sw)
            if cand is None:
                n = _call(sw, "GetDocumentCount", default=before)
                if isinstance(n, int) and n > before:
                    cand = _call(sw, "GetOpenDocumentByName", step_path)
            if cand is not None:
                t = str(_prop(cand, "GetTitle", "")).lower()
                if t.startswith(stem):
                    doc, opened_by = cand, opened_by or "poll"
                    break
        if doc:
            break
    if not doc:
        return {"status": "error", "message": "STEP import failed",
                "detail": "; ".join(attempts) or "no document appeared"}
    time.sleep(1.5)
    try:
        dtype = int(_prop(doc, "GetType", -1))
    except Exception as e:  # noqa: BLE001
        _close(sw, doc)
        return {"status": "error", "message": "GetType failed", "detail": str(e)[:120]}
    if dtype != 1:
        _close(sw, doc)
        return {"status": "error", "message": "STEP imported as doc type %d, expected part" % dtype}
    bodies = []
    try:
        bodies = list(_call(doc, "GetBodies2", 0, True, default=None) or [])
    except Exception as e:  # noqa: BLE001
        attempts.append("GetBodies2: " + str(e)[:100])
    faces = sum((_face_count(b) or 0) for b in bodies) if bodies else 0
    bbox = _bbox_mm(bodies[0]) if bodies else None
    saved = _save(doc, out_path) if bodies else {"saved": False, "path": out_path, "detail": "no solid bodies"}
    result = {"status": "ok" if (bodies and saved.get("saved")) else "error",
              "opened_by": opened_by, "doc_type": dtype, "title": _prop(doc, "GetTitle", ""),
              "bodies": len(bodies), "faces": faces, "bbox_mm": bbox,
              "mass": _doc_mass(doc), "file": saved}
    if attempts:
        result["attempts"] = attempts
    _close(sw, doc)
    return result


def stage_convert(sw, spec: Dict[str, Any]) -> Dict[str, Any]:
    was = _disable_interconnect(sw)
    out_dir = os.path.abspath(spec["out_dir"])
    os.makedirs(out_dir, exist_ok=True)
    results = []
    try:
        for part in spec["parts"]:
            out = os.path.join(out_dir, part["part_name"] + ".SLDPRT")
            r = import_part(sw, os.path.abspath(part["step_file"]), out)
            r["part_name"] = part["part_name"]
            r["expected"] = {"solids": part["solids"], "faces": part["faces"],
                             "bbox": part["bbox"], "placement": part.get("placement")}
            if r["status"] == "ok":
                r["face_match"] = r["faces"] == part["faces"] if r["faces"] else None
                r["body_match"] = r["bodies"] == part["solids"]
            results.append(r)
    finally:
        _restore_interconnect(sw, was)
    ok = all(r["status"] == "ok" and r.get("body_match") and r.get("face_match") for r in results)
    return {"status": "ok" if ok else "error", "stage": "convert", "parts": results}


def stage_extract(sw, spec: Dict[str, Any]) -> Dict[str, Any]:
    """整包 STEP 导入 SW -> 对每个 Component2 的模型文档另存为 .SLDPRT。
    比手工拆 STEP 可靠：几何由 SW 自己的翻译器生成，形状表示关联完整。"""
    was = _disable_interconnect(sw)
    out_dir = os.path.abspath(spec["out_dir"])
    os.makedirs(out_dir, exist_ok=True)
    src = os.path.abspath(spec["source_step"])
    doc, style, _raw, attempts = _open_with_out_params(sw, "LoadFile4", (src, "", _call(sw, "GetImportFileData", src, default=None)), 1)
    if not doc:
        doc, style2, _raw, att2 = _open_with_out_params(sw, "OpenDoc6", (src, 2, 1, ""), 2)
        attempts += att2
    if not doc:
        _restore_interconnect(sw, was)
        return {"status": "error", "stage": "extract", "message": "assembly STEP import failed",
                "detail": "; ".join(attempts)[-1200:]}
    time.sleep(1.5)
    try:
        dtype = int(_prop(doc, "GetType", -1))
    except Exception:
        dtype = -1
    if dtype != 2:
        _close(sw, doc)
        _restore_interconnect(sw, was)
        return {"status": "error", "stage": "extract",
                "message": "expected assembly (type 2), got %r" % dtype}
    _call(doc, "ResolveAllLightWeightComponents", True)
    comps = list(_call(doc, "GetComponents", False, default=None) or [])
    expected = spec.get("expected_parts", [])
    results = []
    for i, comp in enumerate(comps):
        md = _call(comp, "GetModelDoc2", default=None)
        rec = {"index": i, "component": _prop(comp, "Name2", "")}
        if md is None:
            rec.update({"status": "error", "message": "GetModelDoc2 returned None (lightweight?)"})
            results.append(rec)
            continue
        bodies = list(_call(md, "GetBodies2", 0, True, default=None) or [])
        faces = sum((_face_count(b) or 0) for b in bodies) if bodies else 0
        bbox = _bbox_mm(bodies[0]) if bodies else None
        out = os.path.join(out_dir, "sw_part_%d.SLDPRT" % i)
        saved = _save(md, out) if bodies else {"saved": False, "path": out, "detail": "no bodies"}
        exp = expected[i] if i < len(expected) else None
        face_match = (faces == exp["faces"]) if exp else None
        rec.update({"status": "ok" if (bodies and saved.get("saved") and face_match) else "error",
                    "doc_title": _prop(md, "GetTitle", ""), "bodies": len(bodies),
                    "faces": faces, "bbox_mm": bbox, "mass": _doc_mass(md),
                    "file": saved, "expected": exp, "face_match": face_match})
        results.append(rec)
    _close(sw, doc)
    _restore_interconnect(sw, was)
    ok = bool(results) and all(r["status"] == "ok" for r in results)
    return {"status": "ok" if ok else "error", "stage": "extract",
            "opened_by": style, "component_count": len(comps),
            "parts": results, "attempts": attempts[-6:]}


def _wrap(mod, asm) -> Dict[str, Any]:
    disp = asm._oleobj_
    ext = disp.Invoke(66306, 0, pythoncom.DISPATCH_PROPERTYGET, True)
    return {"disp": disp,
            "dyn": dynamic.Dispatch(disp),
            "ext": mod.IModelDocExtension(ext),
            "mdoc": mod.IModelDoc2(disp),
            "adoc": mod.IAssemblyDoc(disp)}


def _open_native(sw, path: str, doc_type: int) -> Optional[Any]:
    """原生文件重开：SW 关闭/保存有延迟，带重试；类型不对时退化到 0。"""
    for attempt in range(4):
        for typ in (doc_type, 0):
            try:
                doc, _style, _raw, _att = _open_with_out_params(
                    sw, "OpenDoc6", (path, typ, 1, ""), 2)
            except Exception:
                doc = None
            if doc is not None:
                return doc
        time.sleep(2.0)
    return None


def _comp_translation(comp) -> Optional[List[float]]:
    try:
        return [round(float(v) * 1000.0, 4) for v in list(comp.Transform2.ArrayData)[9:12]]
    except Exception:
        return None


def _insert_component(da, path: str, center_mm: List[float], placement_mm: List[float]):
    x = (placement_mm[0] + center_mm[0]) / 1000.0
    y = (placement_mm[1] + center_mm[1]) / 1000.0
    z = (placement_mm[2] + center_mm[2]) / 1000.0
    return da.AddComponent5(path, 0, "", False, "", x, y, z)


def _select_face(ew, point_mm, append: bool):
    return ew.SelectByID2("", "Face", point_mm[0] / 1000.0, point_mm[1] / 1000.0,
                          point_mm[2] / 1000.0, append, 0, None, 0)


ASSEMBLY_PLANES = {"X": "右视基准面", "Y": "上视基准面", "Z": "前视基准面"}


def _axis_aligned_faces(planes: List[Dict[str, Any]], center: List[float]) -> Dict[str, Dict[str, Any]]:
    """每个轴选一个最外侧的轴对齐平面（用于与装配基准面做距离配合）。"""
    best: Dict[str, Dict[str, Any]] = {}
    for p in planes:
        n = p["normal"]
        for axis, idx in (("X", 0), ("Y", 1), ("Z", 2)):
            if abs(abs(n[idx]) - 1.0) > 1e-3:
                continue
            if abs(n[(idx + 1) % 3]) > 1e-3 or abs(n[(idx + 2) % 3]) > 1e-3:
                continue
            dist = abs(p["point"][idx] - center[idx])
            if axis not in best or dist > best[axis]["dist"]:
                best[axis] = {"plane": p, "dist": dist,
                              "value_mm": abs(p["point"][idx])}
    return best


def _sel_surface(mod, sm, idx: int) -> Dict[str, Any]:
    """读取当前选中的面：类型 + 圆柱半径/平面法向，用于核对选中的是不是目标面。"""
    try:
        obj = sm.GetSelectedObject6(idx, -1)
        face = mod.IFace2(obj._oleobj_)
        surf = face.GetSurface()
        def _bv(name):
            v = getattr(surf, name)
            return bool(v() if callable(v) else v)
        if _bv("IsCylinder"):
            p = list(_prop(surf, "CylinderParams", []) or [])
            return {"kind": "cylinder", "radius": float(p[6]) if len(p) >= 7 else None,
                    "origin": [float(v) for v in p[:3]] if len(p) >= 3 else None}
        if _bv("IsPlane"):
            p = list(_prop(surf, "PlaneParams", []) or [])
            return {"kind": "plane", "point": [float(v) for v in p[:3]],
                    "normal": [float(v) for v in p[3:6]]}
        return {"kind": "other"}
    except Exception as e:  # noqa: BLE001
        return {"kind": "error", "error": type(e).__name__ + ": " + str(e)[:100]}


def _snapshot(comps) -> List[Optional[List[float]]]:
    return [_comp_translation(c["component"]) for c in comps]


def _mate_subs(mdoc) -> List[Dict[str, str]]:
    """MateGroup 子特征 = 真实落盘的配合特征。"""
    mg = None
    try:
        for f in list(mdoc.FeatureManager.GetFeatures(False) or []):
            if _prop(f, "GetTypeName2", "") == "MateGroup":
                mg = f
                break
    except Exception:
        return []
    out = []
    if mg is None:
        return out
    sf = _call(mg, "GetFirstSubFeature", default=None)
    while sf is not None and len(out) < 100:
        out.append({"type": _prop(sf, "GetTypeName2", ""), "name": _prop(sf, "Name", "")})
        sf = _call(sf, "GetNextSubFeature", default=None)
    return out


def _drifted(comps, placements, snap, tol=0.1) -> List[int]:
    bad = []
    for i, tr in enumerate(snap):
        if tr is None or any(abs(tr[k] - placements[i][k]) > tol for k in range(3)):
            bad.append(i)
    return bad


def stage_build(sw, spec: Dict[str, Any]) -> Dict[str, Any]:
    import win32com.client
    from win32com.client import dynamic
    mod = win32com.client.gencache.EnsureModule(
        "{83A33D31-27C5-11CE-BFD4-00400513BB57}", 0, 29, 0)
    _call(sw, "SetUserPreferenceToggle", 691, True)   # 3D Interconnect 供 InsertImportedFeature
    work = os.path.abspath(spec["working_dir"])
    out_dir = os.path.abspath(spec["out_dir"])
    os.makedirs(work, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)

    parts = spec["parts"]
    imported = []
    for part in parts:
        rec = {"index": part["index"], "name": part["name"], "step_file": part["step_file"]}
        files = part.get("solid_files") or [part["step_file"]]
        doc, bodies, errs = None, [], []
        for attempt in range(3):
            doc = _call(sw, "NewPart", default=None) or _prop(sw, "ActiveDoc")
            dp = dynamic.Dispatch(doc._oleobj_)
            bodies = []
            for fi, f in enumerate(files):
                err = win32.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
                feat = None
                try:
                    feat = dp.InsertImportedFeature(os.path.abspath(f), err)
                except Exception as e:  # noqa: BLE001
                    rec.setdefault("attempts", []).append(
                        "a%d InsertImportedFeature(%d): %s" % (attempt + 1, fi, str(e)[:100]))
                errs.append(int(getattr(err, "value", -1)))
                # 断开 3D Interconnect 链接，零件才自包含、可重开、配合才可落盘
                if feat is not None:
                    try:
                        br = _call(feat, "BreakLink", True, True)
                        rec.setdefault("break_link", []).append(bool(br))
                    except Exception as e:  # noqa: BLE001
                        rec.setdefault("break_link", []).append("ERR: " + str(e)[:90])
                for _ in range(60):
                    time.sleep(1.0)
                    bodies = list(_call(doc, "GetBodies2", 0, True, default=None) or [])
                    if len(bodies) >= fi + 1:
                        break
                if len(bodies) < fi + 1:
                    break
            if len(bodies) >= len(files):
                break
            rec.setdefault("attempts", []).append(
                "a%d: %d/%d bodies" % (attempt + 1, len(bodies), len(files)))
            _close(sw, doc)
            doc = None
            time.sleep(3.0)
        rec["import_error_codes"] = errs
        if not doc or len(bodies) < len(files):
            if doc:
                _close(sw, doc)
            rec.update({"status": "error",
                        "message": "import produced %d/%d bodies" % (len(bodies), len(files))})
            imported.append(rec)
            continue
        boxes = [list(b.GetBodyBox()) for b in bodies]
        box = [min(b[0] for b in boxes), min(b[1] for b in boxes), min(b[2] for b in boxes),
               max(b[3] for b in boxes), max(b[4] for b in boxes), max(b[5] for b in boxes)]
        center = [(box[i + 3] + box[i]) / 2.0 * 1000.0 for i in range(3)]
        mass = _doc_mass(doc)
        vol_mm3 = mass.get("volume_cm3", 0) * 1000.0
        tol = max(1.0, part["volume_mm3"] * 5e-4)
        out = os.path.join(work, (spec.get("part_prefix", "native") + "_%d.SLDPRT") % part["index"])
        saved = _save(doc, out)
        rec.update({"status": "ok" if saved.get("saved") else "error",
                    "bodies": len(bodies), "center_mm": [round(v, 4) for v in center],
                    "volume_mm3": round(vol_mm3, 3), "expected_volume_mm3": part["volume_mm3"],
                    "volume_match": abs(vol_mm3 - part["volume_mm3"]) <= tol,
                    "file": saved})
        _close(sw, doc)
        imported.append(rec)

    if any(r["status"] != "ok" or not r.get("volume_match") for r in imported):
        return {"status": "error", "stage": "build", "steps": {"import": imported},
                "message": "part import/volume check failed"}

    for r in imported:
        sw.OpenDoc6(r["file"]["path"], 1, 1, "", 0, 0)

    asm = _call(sw, "NewAssembly", default=None) or _prop(sw, "ActiveDoc")
    title = _prop(asm, "GetTitle", "")
    W = _wrap(mod, asm)
    da, ew, mdoc, adoc = W["dyn"], W["ext"], W["mdoc"], W["adoc"]
    sw.ActivateDoc3(title, False, 0, 0)
    adoc.ResolveAllLightWeightComponents(True)

    comps, placements = [], []
    for part, r in zip(parts, imported):
        placement = part["placement"]["origin_mm"]
        placements.append(placement)
        c = _insert_component(da, r["file"]["path"], r["center_mm"], placement)
        trans = _comp_translation(c) if c is not None else None
        ok = bool(c) and trans is not None and all(
            abs(trans[i] - placement[i]) <= 0.05 for i in range(3))
        comps.append({"index": part["index"], "name": _prop(c, "Name2", ""),
                      "component": c, "transform_mm": trans,
                      "placement_mm": placement, "placement_ok": ok})
    if not all(c["placement_ok"] for c in comps):
        return {"status": "error", "stage": "build", "steps": {
            "import": imported, "components": [{k: v for k, v in c.items() if k != "component"}
                                               for c in comps]},
            "message": "component placement mismatch"}

    # 基准件固定
    p0 = comps[0]
    try:
        mod.IComponent2(p0["component"]._oleobj_).Select4(True, None, False)
        adoc.FixComponent()
        mdoc.ClearSelection2(True)
        fixed = True
    except Exception as e:  # noqa: BLE001
        fixed = False
        p0["fix_error"] = str(e)[:150]

    mate_results = []
    def _matches(info, expect, radius):
        if expect == "cylinder":
            got = info.get("radius")
            return (info.get("kind") == "cylinder" and got is not None and radius is not None
                    and abs(got - radius / 1000.0) <= 5e-5)
        if expect == "plane":
            return info.get("kind") == "plane"
        return True

    def add_mate(kind: str, points_a, points_b, value_mm: float = 0.0, expect: str = "",
                 expect_radius: Optional[float] = None):
        sm = mdoc.SelectionManager
        chosen = None
        last_err = ""
        for pa in list(points_a)[:8]:
            for pb in list(points_b)[:8]:
                mdoc.ClearSelection2(True)
                if not _select_face(ew, pa, False):
                    last_err = "face A not selectable"
                    continue
                ia = _sel_surface(mod, sm, 1)
                if not _matches(ia, expect, expect_radius):
                    last_err = "face A type mismatch: " + str(ia.get("kind"))
                    continue
                if not _select_face(ew, pb, True):
                    last_err = "face B not selectable"
                    continue
                if sm.GetSelectedObjectCount2(-1) != 2:
                    last_err = "selection count %d" % sm.GetSelectedObjectCount2(-1)
                    continue
                ib = _sel_surface(mod, sm, 2)
                if not _matches(ib, expect, expect_radius):
                    last_err = "face B type mismatch: " + str(ib.get("kind"))
                    continue
                chosen = (pa, pb, ia, ib)
                break
            if chosen:
                break
        rec = {"type": kind, "value_mm": value_mm}
        if not chosen:
            rec.update({"ok": False, "error": last_err or "no verified face pair"})
            mdoc.ClearSelection2(True)
            return rec
        pa, pb, ia, ib = chosen
        rec.update({"point_a": pa, "point_b": pb, "surface_a": ia, "surface_b": ib,
                    "selected": 2})
        before = _snapshot(comps)
        mt = {"coincident": 0, "concentric": 1, "distance": 5}[kind]
        try:
            ret = adoc.AddMate5(mt, 2, False, value_mm / 1000.0, 0, 0, 0, 0,
                                0, 0, 0, False, False, 0, 0)
            mate, status = (ret if isinstance(ret, tuple) else (ret, None))
            rec.update({"ok": mate is not None, "mate_status": status,
                        "mate_entities": _call(mate, "GetMateEntityCount", default=None)
                        if mate is not None else None})
        except Exception as e:  # noqa: BLE001
            rec.update({"ok": False, "error": type(e).__name__ + ": " + str(e)[:160]})
        mdoc.ClearSelection2(True)
        if rec.get("ok"):
            after = _snapshot(comps)
            moved = _drifted(comps, placements, after)
            for i in moved:
                rec.setdefault("moved", []).append({"index": i, "before": before[i], "after": after[i]})
            if moved:
                try:
                    mdoc.EditUndo2(1)
                    rec["rolled_back"] = True
                except Exception as e:  # noqa: BLE001
                    rec["rolled_back"] = False
                    rec["undo_error"] = str(e)[:120]
                rec["ok"] = False
                rec["error"] = "mate moved components; undone"
        return rec

    for m in spec.get("mates", []):
        pa_list = m.get("points_a") or [m["point_a"]]
        pb_list = m.get("points_b") or [m["point_b"]]
        if m["type"] == "coaxial":
            mate_results.append(add_mate("concentric", pa_list, pb_list,
                                         expect="cylinder", expect_radius=m.get("radius")))
        else:
            mate_results.append(add_mate(m["type"], pa_list, pb_list,
                                         m.get("value_mm", 0.0), expect="plane"))

    # 无成功接触配合的零件：STEP 中无接触（爆炸图位姿），固定并明确标注
    touched = set()
    for m, res in zip(spec.get("mates", []), mate_results):
        if res.get("ok"):
            touched.update((m["a"], m["b"]))
    pose_locks = []
    for c in comps:
        idx = c["index"]
        if idx in touched:
            continue
        rec = {"index": idx, "contact_mates": 0,
               "policy": "no contact in STEP; pose locked by FixComponent"}
        try:
            mod.IComponent2(c["component"]._oleobj_).Select4(True, None, False)
            adoc.FixComponent()
            mdoc.ClearSelection2(True)
            rec["fixed"] = True
        except Exception as e:  # noqa: BLE001
            rec["fixed"] = False
            rec["error"] = str(e)[:150]
        pose_locks.append(rec)

    mdoc.EditRebuild3()
    subs_after_rebuild = _mate_subs(mdoc)
    after = [_comp_translation(c["component"]) for c in comps]
    drift = []
    for i, tr in enumerate(after):
        if tr is None or any(abs(tr[k] - placements[i][k]) > 0.1 for k in range(3)):
            drift.append({"index": i, "after": tr, "expected": placements[i]})

    asm_path = os.path.join(out_dir, spec.get("name", "wheel_mold_mated") + ".SLDASM")
    saved = _save(asm, asm_path)
    mass = _doc_mass(asm)
    vol_sum = round(sum(r["volume_mm3"] for r in imported), 3)
    vol_asm = round(mass.get("volume_cm3", 0) * 1000.0, 3)

    def _comp_mates(comp):
        try:
            cw = mod.IComponent2(comp._oleobj_)
            ms = list(cw.GetMates() or [])
            return [_prop(m, "Name", "") for m in ms]
        except Exception as e:  # noqa: BLE001
            return {"error": type(e).__name__ + ": " + str(e)[:100]}

    mate_evidence = {c["name"]: _comp_mates(c["component"]) for c in comps}
    result = {
        "status": "ok" if saved.get("saved") and not drift else "error",
        "stage": "build",
        "steps": {
            "import": imported,
            "components": [{k: v for k, v in c.items() if k != "component"} for c in comps],
            "anchor_fixed": fixed,
            "contact_mates": mate_results,
            "pose_locks": pose_locks,
        },
        "assembly": {"title": title, "file": saved,
                     "volume_mm3": vol_asm, "parts_volume_sum_mm3": vol_sum,
                     "volume_match": abs(vol_asm - vol_sum) <= max(1.0, vol_sum * 5e-4)},
        "mate_evidence": mate_evidence,
        "mate_subs_before_save": subs_after_rebuild,
        "transform_drift": drift,
    }
    # 关闭重开取证
    try:
        sw.CloseDoc(title)
        time.sleep(2.0)
        reopened = _open_native(sw, asm_path, 2)
        rec = {"opened_by": "OpenDoc6", "title": _prop(reopened, "GetTitle", "") if reopened else ""}
        if reopened:
            W2 = _wrap(mod, reopened)
            adoc2 = W2["adoc"]
            adoc2.ResolveAllLightWeightComponents(True)
            rcomps = list(adoc2.GetComponents(False) or [])
            rec["components"] = [{
                "name": _prop(c, "Name2", ""),
                "transform_mm": _comp_translation(c),
                "mates": _comp_mates(c),
            } for c in rcomps]
            status = _mate_subs(W2["mdoc"])
            rec["mate_features"] = status
            rec["mate_feature_count"] = len(status)
            _close(sw, reopened)
        result["reopen"] = rec
    except Exception as e:  # noqa: BLE001
        result["reopen"] = {"error": type(e).__name__ + ": " + str(e)[:200]}
    return result


def stage_drawing(sw, spec: Dict[str, Any]) -> Dict[str, Any]:
    asm_path = os.path.abspath(spec["assembly_path"])
    out_dir = os.path.abspath(spec["out_dir"])
    os.makedirs(out_dir, exist_ok=True)
    templates = (r"C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2021\templates\gb_a3.drwdot",
                 r"D:\SOLIDWORKS (2)\data\templates\gb.drwdot")
    tpl = next((t for t in templates if os.path.exists(t)), None)
    if not tpl:
        return {"status": "error", "stage": "drawing", "message": "GB template not found"}
    # 必须先打开模型，Create1stAngleViews2 才能解析引用
    opened = _open_native(sw, asm_path, 2)
    if opened is None:
        return {"status": "error", "stage": "drawing", "message": "assembly open failed"}
    draw, opened_by = None, ""
    for label, fn in (("NewDrawing2", lambda: sw.NewDrawing2(tpl, "", 0, 0.0, 0.0)),
                      ("NewDocument", lambda: sw.NewDocument(tpl, 0, 0.0, 0.0))):
        try:
            draw = fn()
            if draw is not None:
                opened_by = label
                break
        except Exception:  # noqa: BLE001
            continue
    if draw is None:
        _close(sw, opened)
        return {"status": "error", "stage": "drawing", "message": "create drawing doc failed"}
    title = _prop(draw, "GetTitle", "")
    sw.ActivateDoc3(title, False, 0, 0)
    import win32com.client as _w
    mod = _w.gencache.EnsureModule("{83A33D31-27C5-11CE-BFD4-00400513BB57}", 0, 29, 0)
    dd = mod.IDrawingDoc(draw._oleobj_)
    errors = []
    first_ret = None
    try:
        first_ret = draw.Create1stAngleViews2(asm_path)
    except Exception as e:  # noqa: BLE001
        errors.append("Create1stAngleViews2: " + str(e)[:120])
    view_count = _call(dd, "GetViewCount", default=None)
    iso_ret = False
    for vname in ("*Isometric", "*等轴测", "*Trimetric"):
        try:
            iso_ret = bool(draw.CreateDrawViewFromModelView3(asm_path, vname, 0.30, 0.20, 0.0))
        except Exception as e:  # noqa: BLE001
            iso_ret = False
            errors.append("iso %s: %s" % (vname, str(e)[:90]))
        if iso_ret:
            break
    names = []
    try:
        v = draw.GetFirstView()
        guard = 0
        while v is not None and guard < 30:
            guard += 1
            names.append(_prop(v, "Name", ""))
            v = _prop(v, "GetNextView", None) or _call(v, "GetNextView", default=None)
    except Exception as e:  # noqa: BLE001
        errors.append("enumerate views: " + str(e)[:120])
    out = os.path.join(out_dir, os.path.splitext(os.path.basename(asm_path))[0] + ".SLDDRW")
    saved = _save(draw, out)
    final_count = _call(dd, "GetViewCount", default=None)
    _close(sw, draw)
    _close(sw, opened)
    # 重开工程图核对视图数是否真的落盘
    reopen_views = None
    try:
        d2, _s2, _r2, _a2 = _open_with_out_params(sw, "OpenDoc6", (out, 3, 1, ""), 2)
        if d2 is not None:
            dd2 = mod.IDrawingDoc(d2._oleobj_)
            reopen_views = _call(dd2, "GetViewCount", default=None)
            _close(sw, d2)
    except Exception as e:  # noqa: BLE001
        errors.append("reopen drawing: " + str(e)[:120])
    ok = (saved.get("saved") and final_count is not None and int(final_count) >= 4
          and reopen_views is not None and int(reopen_views) >= 4)
    return {"status": "ok" if ok else "error", "stage": "drawing",
            "template": os.path.basename(tpl), "opened_by": opened_by,
            "first_angle_ret": first_ret, "isometric_ret": iso_ret,
            "view_count_before_iso": view_count, "view_count": final_count,
            "reopen_view_count": reopen_views, "views": names, "errors": errors,
            "projection": "第一角画法 (GB/T 17451)", "file": saved}


def main(argv: List[str]) -> int:
    spec_path = argv[1]
    spec = json.load(open(spec_path, encoding="utf-8"))
    result_path = spec["result_path"]
    pythoncom.CoInitialize()
    t0 = time.time()
    try:
        sw = connect()
        stage = spec.get("stage", "convert")
        if stage == "convert":
            result = stage_convert(sw, spec)
        elif stage == "extract":
            result = stage_extract(sw, spec)
        elif stage == "build":
            result = stage_build(sw, spec)
        elif stage == "drawing":
            result = stage_drawing(sw, spec)
        else:
            result = {"status": "error", "message": "unknown stage " + str(stage)}
    except Exception as e:  # noqa: BLE001
        result = {"status": "error", "message": type(e).__name__ + ": " + str(e)[:400],
                  "traceback": traceback.format_exc()[-3000:]}
    result["elapsed_s"] = round(time.time() - t0, 2)
    tmp = result_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    os.replace(tmp, result_path)
    return 0 if result.get("status") == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
