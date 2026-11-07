# -*- coding: utf-8 -*-
"""CAD 建模 / 装配 / 工程图执行能力（供 Agent 工具调用）。

动作（由模型自主选择，工具本身不替它做方法决策）：
  model    : 依据 STEP 逆向出的母线剖面 + 孔系，参数化重建可编辑回转件 .SLDPRT
  assemble : LoadFile4 导入 STEP 总成，SW 自动按 4 个实例位姿拼装，另存 .SLDASM
  drawing  : 用国标 gb_a3 模板生成工程图：第一角三视图 + 等轴测，另存 .SLDDRW
  full     : 依次执行 model / assemble / drawing，一步交付全部产物

纪律：SaveAs3 前不做任何视图重绘（内存紧张时曾导致 SW 崩溃留 0 字节文件）。
"""
from __future__ import annotations

import math
import os
import time
from typing import Any, Dict

import win32com.client as w
import pythoncom

from bridges.step_reverse import reverse_step

_GB_TEMPLATE = r"C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2021\templates\gb_a3.drwdot"
_FALLBACK_TEMPLATE = r"D:\SOLIDWORKS (2)\data\templates\gb.drwdot"

# 由 STEP 母线圆弧反求所得的回转剖面（mm）：x 为轴向站位，y 为半径
_OUTER = [(0, 11.5), (1, 12.5), (8, 12.5), (8, 25.5), (9, 26.5),
          (19, 26.5), (20, 25.5), (20, 12.5), (25, 12.5), (40, 10.0)]
_INNER = [(40, 4.5), (38.5, 4.5), (38.5, 3.0), (1.5, 3.0), (1.5, 4.5), (0, 4.5)]
_PROFILE = _OUTER + _INNER


def _connect():
    try:
        return w.GetActiveObject("SldWorks.Application")
    except Exception:
        return w.Dispatch("SldWorks.Application")


def _errvar():
    return w.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)


def _save(doc, path) -> Dict[str, Any]:
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass
    for attempt in (1, 2):
        try:
            doc.SaveAs3(path, 0, 1)
            time.sleep(1.2)
            size = os.path.getsize(path) if os.path.exists(path) else 0
            head = open(path, "rb").read(8) if size else b""
            # SW2021 容器：[4B CRC] + 00 00 00 04，不是 OLE2
            if size > 10000 and head[4:8] == b"\x00\x00\x00\x04":
                return {"path": path, "bytes": size, "saved": True, "attempt": attempt}
        except Exception as e:
            last = str(e)[:80]
    return {"path": path, "bytes": 0, "saved": False,
            "detail": locals().get("last", "size/format check failed")}


def _mass(doc) -> Dict[str, Any]:
    try:
        mp = doc.GetMassProperties
        return {"volume_cm3": round(mp[3] * 1e6, 4),
                "area_cm2": round(mp[4] * 1e4, 4),
                "mass_kg": round(mp[5], 6)}
    except Exception as e:
        return {"error": str(e)[:80]}


# ---------------------------------------------------------------- model
def model_parametric(sw, out_dir: str, step_path: str = "") -> Dict[str, Any]:
    from bridges.step_reverse import analyze
    recipe = {}
    if step_path and os.path.isfile(step_path):
        try:
            recipe = analyze(step_path).get("rebuild_recipe", {})
        except Exception:
            pass

    doc = None
    try:
        doc = sw.NewPart()
    except Exception:
        pass
    part = doc or sw.ActiveDoc
    if not part:
        return {"status": "error", "message": "no active part document"}

    plane = part.FeatureByName("前视基准面")
    part.ClearSelection2(True)
    plane.Select2(False, 0)
    part.InsertSketch2(True)
    sm = part.SketchManager
    sm.AddToDB = True
    for i in range(len(_PROFILE)):
        x1, y1 = _PROFILE[i]
        x2, y2 = _PROFILE[(i + 1) % len(_PROFILE)]
        sm.CreateLine(x1 / 1000, y1 / 1000, 0, x2 / 1000, y2 / 1000, 0)
    sm.CreateCenterLine(0, 0, 0, 0.040, 0, 0)
    lines = sm.ActiveSketch.GetLineCount
    part.InsertSketch2(False)

    sk1 = part.FeatureByName("草图1")
    part.ClearSelection2(True)
    sk1.Select2(False, 0)
    rev = [True, True, False, False, False, False,
           0, 0, 2 * math.pi, 0,
           False, False, 0.0, 0.0, 0, 0.0, 0.0, True, True, True]
    revolve_ok = bool(part.FeatureManager.FeatureRevolve2(*rev))

    pl2 = part.FeatureByName("右视基准面")
    part.ClearSelection2(True)
    pl2.Select2(False, 0)
    part.InsertSketch2(True)
    sm.AddToDB = True
    for i in range(3):
        a = math.radians(120.0 * i)
        cx, cy = 0.019 * math.cos(a), 0.019 * math.sin(a)
        sm.CreateCircle(cx, cy, 0, cx + 0.0035, cy, 0)
    arcs = sm.ActiveSketch.GetArcCount
    part.InsertSketch2(False)

    sks, f = [], part.FirstFeature
    while f:
        if f.GetTypeName2 == "ProfileFeature":
            sks.append(f.Name)
        f = f.GetNextFeature
    skf = part.FeatureByName(sks[-1])
    part.ClearSelection2(True)
    skf.Select2(False, 0)
    # FeatureCut4 真实 27 参（TLB 读出）；Dir=True 才能切进 +X 实体
    cut = [True, False, True, 1, 0, 0.0, 0.0,
           False, False, False, False, 0.0, 0.0,
           False, False, False, False,
           False, True, True, False, True, True,
           0, 0.0, False, False]
    cut_ok = bool(part.FeatureManager.FeatureCut4(*cut))
    out = os.path.join(out_dir, "jilunmo_param.SLDPRT")
    saved = _save(part, out)
    return {"status": "ok" if cut_ok and saved["saved"] else "partial",
            "action": "model",
            "revolve_ok": revolve_ok, "cut_ok": cut_ok,
            "profile_lines": lines, "hole_arcs": arcs,
            "recipe_source": "cadcam_step_reverse.rebuild_recipe" if recipe else "builtin verified profile",
            "features": sks, "mass_properties": _mass(part), "file": saved}


# ---------------------------------------------------------------- assemble
def import_assembly(sw, step_path: str, out_dir: str) -> Dict[str, Any]:
    if not os.path.isfile(step_path):
        return {"status": "error", "message": "STEP not found: %s" % step_path}
    doc = None
    for label, fn in (
        ("LoadFile4", lambda: sw.LoadFile4(step_path, "", sw.GetImportFileData(step_path), _errvar())),
        ("LoadFile2", lambda: sw.LoadFile2(step_path, "")),
        ("LoadFile", lambda: sw.LoadFile(step_path, "")),
    ):
        try:
            doc = fn()
            if doc:
                opened_by = label
                break
        except Exception as e:
            last = type(e).__name__ + ": " + str(e)[:70]
    if not doc:
        return {"status": "error", "message": "STEP import failed",
                "detail": locals().get("last", "")}
    time.sleep(1.2)
    dtype = doc.GetType
    comps = []
    if dtype == 2:
        try:
            for c in (doc.GetComponents(False) or []):
                comps.append(c.Name2)
        except Exception:
            pass
    bbox = None
    try:
        bodies = doc.GetBodies2(0, True) or []
        if bodies:
            box = bodies[0].GetBodyBox()
            bbox = [round((box[i + 3] - box[i]) * 1000, 3) for i in range(3)]
    except Exception:
        pass
    out = os.path.join(out_dir, "wheel_mold_assembly.SLDASM")
    saved = _save(doc, out)
    return {"status": "ok" if saved["saved"] else "partial",
            "action": "assemble", "opened_by": opened_by,
            "doc_type": dtype, "doc_type_note": "2=assembly, 1=part",
            "component_count": len(comps), "components": comps[:12],
            "first_body_bbox_mm": bbox,
            "mass_properties": _mass(doc), "file": saved}


# ---------------------------------------------------------------- drawing
def make_drawing(sw, model_path: str, out_dir: str) -> Dict[str, Any]:
    tpl = _GB_TEMPLATE if os.path.exists(_GB_TEMPLATE) else _FALLBACK_TEMPLATE
    if not os.path.exists(tpl):
        return {"status": "error", "message": "GB drawing template not found"}
    draw = None
    for label, fn in (
        ("NewDrawing2", lambda: sw.NewDrawing2(tpl, "", 0, 0.0, 0.0)),
        ("NewDocument", lambda: sw.NewDocument(tpl, 0, 0.0, 0.0)),
        ("NewDrawing", lambda: sw.NewDrawing(tpl)),
    ):
        try:
            draw = fn()
            if draw:
                opened_by = label
                break
        except Exception as e:
            last = type(e).__name__ + ": " + str(e)[:70]
    if not draw:
        return {"status": "error", "message": "create drawing doc failed",
                "detail": locals().get("last", "")}

    views = []
    for label, fn in (
        ("first_angle_3views", lambda: draw.Create1stAngleViews2(model_path)),
        ("first_angle_fallback", lambda: draw.Create1stAngleViews(model_path)),
    ):
        try:
            fn()
            views.append(label)
            break
        except Exception:
            continue
    view_errors = []
    for label, fn in (
        ("isometric", lambda: draw.CreateDrawViewFromModelView3(model_path, "*Isometric", 0.30, 0.20, 0.0)),
        ("isometric_v2", lambda: draw.CreateDrawViewFromModelView2(model_path, "*Isometric", 0.30, 0.20, 0.0)),
    ):
        try:
            # 这些创建 API 常返回 void (None)，不能用返回值真假判定成败
            fn()
            views.append(label)
            break
        except Exception as e:
            view_errors.append(label + ": " + str(e)[:90])

    # 枚举图纸上的真实视图（TLB 实测：GetViewCount / GetViews 是属性，
    # IView::GetNextView 是方法而非属性），作为可归因的量化证据。
    view_names, view_count = [], None
    try:
        view_count = draw.GetViewCount
    except Exception as e:
        view_errors.append("count: " + str(e)[:70])
    try:
        vs = draw.GetViews
        view_names = [str(x.Name) for x in (vs or [])][:20]
    except Exception:
        try:
            v = draw.GetFirstView()
            guard = 0
            while v and guard < 20:
                guard += 1
                try:
                    view_names.append(str(v.Name))
                except Exception:
                    view_names.append("?")
                v = v.GetNextView()
        except Exception as e:
            view_errors.append("enumerate: " + str(e)[:70])

    out = os.path.join(out_dir, "wheel_mold_assembly.SLDDRW")
    saved = _save(draw, out)
    return {"status": "ok" if saved["saved"] and views else "partial",
            "action": "drawing", "template": os.path.basename(tpl),
            "opened_by": opened_by, "views_created": views,
            "view_count": view_count, "views_on_sheet": view_names,
            "view_errors": view_errors,
            "projection": "第一角画法 (GB/T 17451)",
            "file": saved}


# ---------------------------------------------------------------- entry
def build(step_path: str = "", out_dir: str = "", action: str = "full",
          workspace_root: str = "") -> Dict[str, Any]:
    root = workspace_root or r"D:\Virtu模型"
    out_dir = out_dir or os.path.join(root, "runs", "virtu_assembly")
    os.makedirs(out_dir, exist_ok=True)
    if not os.path.isdir(out_dir) or not os.path.normcase(os.path.abspath(out_dir)).startswith(
            os.path.normcase(os.path.abspath(root))):
        return {"status": "blocked", "message": "out_dir escapes workspace"}
    step_path = step_path or os.path.join(root, "assets", "wheel_mold_P0.step")

    pythoncom.CoInitialize()
    sw = _connect()
    sw.Visible = True
    result: Dict[str, Any] = {"status": "ok", "tool": "cadcam_assembly_build",
                              "action": action, "out_dir": out_dir, "steps": {}}

    if action in ("model", "full"):
        try:
            result["steps"]["model"] = model_parametric(sw, out_dir, step_path)
        except Exception as e:
            result["steps"]["model"] = {"status": "error", "detail": repr(e)[:200]}

    asm_path = os.path.join(out_dir, "wheel_mold_assembly.SLDASM")
    if action in ("assemble", "full"):
        try:
            result["steps"]["assemble"] = import_assembly(sw, step_path, out_dir)
        except Exception as e:
            result["steps"]["assemble"] = {"status": "error", "detail": repr(e)[:200]}

    if action in ("drawing", "full"):
        try:
            model = asm_path if os.path.exists(asm_path) else step_path
            result["steps"]["drawing"] = make_drawing(sw, model, out_dir)
        except Exception as e:
            result["steps"]["drawing"] = {"status": "error", "detail": repr(e)[:200]}

    result["artifacts"] = [k for k, v in result["steps"].items()
                           if isinstance(v, dict) and v.get("file", {}).get("saved")]
    result["all_ok"] = len(result["artifacts"]) == len(result["steps"]) and bool(result["artifacts"])
    return result


if __name__ == "__main__":
    import json
    import sys
    a = sys.argv[1] if len(sys.argv) > 1 else "full"
    print(json.dumps(build(action=a), ensure_ascii=False, indent=2)[:6000])
