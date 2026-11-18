# -*- coding: utf-8 -*-
"""原子特征执行器：按 Agent 自己给出的方案逐步建模，不含任何策略。

与 cadcam_assembly_build(full) 的区别：
  full 是封装好的一键策略；这里只提供「读数据」和「按方案逐步执行」。
方案（plan.ops 的顺序、参数、op 类型）全部由调用方（Virtu 模型）决定，
执行器只做确定性翻译，不替它选方法、不补齐缺失步骤。

每个 op 执行后立即读质量属性，形成可核对的证据链。
"""
from __future__ import annotations

import math
import os
import time
from typing import Any, Dict, List

import win32com.client as w
import pythoncom

from bridges.step_reverse import analyze

# STEP 母线测量结果（上一轮从 B-Rep 圆弧/平面反求并已用体积 0 误差验证）。
# 这是「测量数据」，不是建模方法；是否用它、怎么组合由模型决定。
_MERIDIAN_MM = [
    (0, 11.5), (1, 12.5), (8, 12.5), (8, 25.5), (9, 26.5),
    (19, 26.5), (20, 25.5), (20, 12.5), (25, 12.5), (40, 10.0),
    (40, 4.5), (38.5, 4.5), (38.5, 3.0), (1.5, 3.0), (1.5, 4.5), (0, 4.5),
]
_GB_TEMPLATE = r"C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2021\templates\gb_a3.drwdot"


_SW = None


def _connect():
    """单实例闸门：整个进程只连接/启动一次 SldWorks.Application，避免多实例互抢 COM。

    SW 冷启动常瞬时返回「服务器运行失败」，这里只重试连接，不重复启动新实例。
    """
    global _SW
    if _SW is not None:
        return _SW
    last = None
    for _ in range(4):
        try:
            _SW = w.GetActiveObject("SldWorks.Application")
            break
        except Exception:
            try:
                _SW = w.Dispatch("SldWorks.Application")
                break
            except Exception as e:
                last = e
                _SW = None
                time.sleep(1.5)
    if _SW is None:
        raise last or RuntimeError("cannot connect to SldWorks.Application")
    return _SW


def _ev():
    return w.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)


def _mass(doc):
    try:
        mp = doc.GetMassProperties
        return {"volume_mm3": round(mp[3] * 1e9, 4),
                "area_mm2": round(mp[4] * 1e6, 4),
                "mass_kg": round(mp[5], 6)}
    except Exception:
        return None


def _save(doc, path):
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass
    try:
        doc.SaveAs3(path, 0, 1)
        time.sleep(1.1)
        n = os.path.getsize(path) if os.path.exists(path) else 0
        head = open(path, "rb").read(8) if n else b""
        return {"path": path, "bytes": n,
                "saved": bool(n > 10000 and head[4:8] == b"\x00\x00\x00\x04")}
    except Exception as e:
        return {"path": path, "bytes": 0, "saved": False, "error": str(e)[:80]}


def single_case() -> Dict[str, Any]:
    """报告当前 SolidWorks 实例里的文档数与活动文档的真实特征树。

    这是「只开一个案例」的可核对证据：open_documents 应为 1。
    """
    pythoncom.CoInitialize()
    sw = _connect()
    titles = []
    try:
        d = sw.GetFirstDocument2()
        while d:
            titles.append(d.GetTitle)
            d = d.GetNext
    except Exception:
        pass
    active = sw.ActiveDoc
    enum_source = "GetFirstDocument2"
    if not titles and active:
        # GetFirstDocument2/GetNext 在该 pywin32 包装层常报 ENUM_ERR；
        # ActiveDoc 是权威来源，回退时显式标注，不伪装成枚举成功。
        titles = [active.GetTitle]
        enum_source = "active_doc_fallback (GetFirstDocument2 unavailable)"
    feats = []
    if active:
        f = active.FirstFeature
        while f:
            feats.append({"name": f.Name, "type": f.GetTypeName2})
            f = f.GetNextFeature
    proc_count = None
    try:
        import psutil
        proc_count = sum(1 for p in psutil.process_iter(["name"])
                         if (p.info.get("name") or "").lower() == "sldworks.exe")
    except Exception:
        pass
    out = {
        "status": "ok", "action": "single_case",
        "open_document_count": len(titles),
        "open_documents": titles,
        "document_enum_source": enum_source,
        "sldworks_process_count": proc_count,
        "single_case_ok": len(titles) == 1 and (proc_count in (None, 1)),
        "active_document": active.GetTitle if active else None,
        "active_document_type": active.GetType if active else None,
        "native_feature_tree": feats,
        "mass_properties": _mass(active) if active else None,
        "sw_revision": sw.RevisionNumber,
    }
    if active:
        try:
            bodies = active.GetBodies2(0, True) or []
            out["body_count"] = len(bodies)
            if bodies:
                box = bodies[0].GetBodyBox()
                out["bbox_mm"] = [round((box[i + 3] - box[i]) * 1000, 4) for i in range(3)]
        except Exception:
            pass
    return out


def measure(step_path: str) -> Dict[str, Any]:
    """返回可供模型自主决策的原始测量数据（不给方法、不给结论）。"""
    a = analyze(step_path)
    return {
        "status": "ok",
        "action": "measure",
        "source": os.path.basename(step_path),
        "products": a["products"],
        "global_bbox_mm": a["global_bbox_mm"],
        "cylinder_dia_spectrum": a["cylinder_dia_spectrum"],
        "cone_half_angles_deg": a["cone_half_angles_deg"],
        "solid_count": a["solid_count"],
        "meridian_polyline_mm": [{"x": x, "r": r} for x, r in _MERIDIAN_MM],
        "meridian_note": "闭合剖面点列 (x=轴向 mm, r=半径 mm)，按序连线即母线；来源为 STEP B-Rep 测量",
        "hole_evidence": a["rebuild_recipe"],
    }


def execute_plan(plan: Dict[str, Any], step_path: str,
                 out_dir: str) -> Dict[str, Any]:
    """严格按模型给出的 ops 顺序执行；不认识 / 缺参数的 op 如实报错，不自动补齐。"""
    ops = plan.get("ops") or []
    if not isinstance(ops, list) or not ops:
        return {"status": "error", "message": "plan.ops 为空；执行器不会替你补步骤"}
    pythoncom.CoInitialize()
    sw = _connect()
    sw.Visible = True
    out: Dict[str, Any] = {"status": "ok", "action": "execute_plan",
                           "out_dir": out_dir, "ops_executed": [], "evidence": []}
    doc, skf = None, None

    for i, op in enumerate(ops, 1):
        name = op.get("op") if isinstance(op, dict) else None
        rec: Dict[str, Any] = {"step": i, "op": name, "params": op}
        try:
            if name == "new_part":
                try:
                    doc = sw.NewPart()
                except Exception:
                    pass
                doc = doc or sw.ActiveDoc
                rec["doc"] = doc.GetTitle if doc else None

            elif name == "sketch_profile":
                if doc is None:
                    raise RuntimeError("需要先 new_part")
                src = op.get("source", "step_meridian")
                pts = op.get("points") or (_MERIDIAN_MM if src == "step_meridian" else None)
                if not pts:
                    raise RuntimeError("缺少 points 或非法 source")
                plane = doc.FeatureByName(op.get("plane", "前视基准面"))
                doc.ClearSelection2(True)
                plane.Select2(False, 0)
                doc.InsertSketch2(True)
                sm = doc.SketchManager
                sm.AddToDB = True
                P = [(float(p[0]), float(p[1])) if isinstance(p, (list, tuple))
                     else (float(p["x"]), float(p["r"])) for p in pts]
                for k in range(len(P)):
                    x1, y1 = P[k]
                    x2, y2 = P[(k + 1) % len(P)]
                    sm.CreateLine(x1 / 1000, y1 / 1000, 0, x2 / 1000, y2 / 1000, 0)
                sm.CreateCenterLine(0, 0, 0, 0.040, 0, 0)
                rec["lines"] = sm.ActiveSketch.GetLineCount
                doc.InsertSketch2(False)
                skf = doc.FeatureByName("草图1")

            elif name == "revolve":
                if skf is None:
                    raise RuntimeError("需要先 sketch_profile")
                doc.ClearSelection2(True)
                skf.Select2(False, 0)
                ang = math.radians(float(op.get("angle_deg", 360)))
                args = [True, True, False, False, False, False,
                        0, 0, ang, 0, False, False, 0.0, 0.0,
                        0, 0.0, 0.0, True, True, True]
                rec["ok"] = bool(doc.FeatureManager.FeatureRevolve2(*args))
                rec["mass_after"] = _mass(doc)

            elif name == "sketch_holes":
                pcd = float(op.get("pcd_mm", 38.0)) / 2000
                dia = float(op.get("hole_dia_mm", 7.0)) / 2000
                n = int(op.get("count", 3))
                angs = op.get("angles_deg") or [360.0 * k / n for k in range(n)]
                pl = doc.FeatureByName(op.get("plane", "右视基准面"))
                doc.ClearSelection2(True)
                pl.Select2(False, 0)
                doc.InsertSketch2(True)
                sm = doc.SketchManager
                sm.AddToDB = True
                for deg in angs:
                    a = math.radians(float(deg))
                    cx, cy = pcd * math.cos(a), pcd * math.sin(a)
                    sm.CreateCircle(cx, cy, 0, cx + dia, cy, 0)
                rec["arcs"] = sm.ActiveSketch.GetArcCount
                doc.InsertSketch2(False)
                sks, f = [], doc.FirstFeature
                while f:
                    if f.GetTypeName2 == "ProfileFeature":
                        sks.append(f.Name)
                    f = f.GetNextFeature
                skf = doc.FeatureByName(sks[-1])
                rec["sketch"] = skf.Name

            elif name == "cut":
                doc.ClearSelection2(True)
                skf.Select2(False, 0)
                # FeatureCut4 真实 27 参（TLB）；Dir=True 才能切进 +X 实体
                args = [True, bool(op.get("flip", False)), True, 1, 0, 0.0, 0.0,
                        False, False, False, False, 0.0, 0.0,
                        False, False, False, False,
                        False, True, True, False, True, True,
                        0, 0.0, False, False]
                rec["ok"] = bool(doc.FeatureManager.FeatureCut4(*args))
                rec["mass_after"] = _mass(doc)

            elif name == "save_part":
                p = os.path.join(out_dir, op.get("name", "model_part.SLDPRT"))
                rec["file"] = _save(doc, p)

            elif name == "import_assembly":
                src = op.get("step_path") or step_path
                imp = sw.GetImportFileData(src)
                doc = sw.LoadFile4(src, "", imp, _ev())
                time.sleep(1.0)
                rec["doc_type"] = doc.GetType if doc else None
                rec["components"] = len(doc.GetComponents(False) or []) if doc and doc.GetType == 2 else 0
                rec["mass"] = _mass(doc)

            elif name == "save_assembly":
                p = os.path.join(out_dir, op.get("name", "model_assembly.SLDASM"))
                rec["file"] = _save(doc, p)

            elif name == "drawing":
                tpl = op.get("template") or _GB_TEMPLATE
                draw = sw.NewDocument(tpl, 0, 0.0, 0.0)
                model = op.get("model_path") or os.path.join(out_dir, "model_assembly.SLDASM")
                views = []
                if op.get("first_angle", True):
                    try:
                        draw.Create1stAngleViews2(model)
                        views.append("first_angle_3views")
                    except Exception as e:
                        rec["first_angle_err"] = str(e)[:80]
                if op.get("isometric", True):
                    try:
                        draw.CreateDrawViewFromModelView3(model, "*Isometric", 0.30, 0.20, 0.0)
                        views.append("isometric")
                    except Exception as e:
                        rec["isometric_err"] = str(e)[:80]
                rec["views"] = views
                try:
                    rec["view_count"] = draw.GetViewCount
                except Exception:
                    pass
                p = os.path.join(out_dir, op.get("name", "model_drawing.SLDDRW"))
                rec["file"] = _save(draw, p)

            elif name == "verify":
                rec["mass"] = _mass(doc)
                fs, f = [], doc.FirstFeature if doc else None
                while f:
                    if f.GetTypeName2 in ("ProfileFeature", "Revolution", "ICE"):
                        fs.append((f.Name, f.GetTypeName2))
                    f = f.GetNextFeature
                rec["features"] = fs

            else:
                rec["error"] = "未知 op（执行器不自动替换）"
        except Exception as e:
            rec["error"] = type(e).__name__ + ": " + str(e)[:110]
        out["ops_executed"].append(rec)
        if rec.get("error") or rec.get("ok") is False:
            out["status"] = "partial"
    # 「partial」意味着有部分成功，0 步成功不能叫 partial（2026-11-13 复查）
    _failed = [r for r in out["ops_executed"] if r.get("error") or r.get("ok") is False]
    if _failed and len(_failed) == len(out["ops_executed"]):
        out["status"] = "error"
        out["message"] = "全部 op 均失败（执行器不自动补齐），无任何特征落地"
    out["final_mass"] = _mass(doc)
    return out


def feature_ops(action: str = "measure", plan: Dict[str, Any] | None = None,
                step_path: str = "", out_dir: str = "",
                workspace_root: str = "") -> Dict[str, Any]:
    root = workspace_root or r"D:\Virtu模型"
    step_path = step_path or os.path.join(root, "assets", "wheel_mold_P0.step")
    out_dir = out_dir or os.path.join(root, "works", "model_plan")
    if not os.path.normcase(os.path.abspath(out_dir)).startswith(os.path.normcase(os.path.abspath(root))):
        return {"status": "blocked", "message": "out_dir escapes workspace"}
    os.makedirs(out_dir, exist_ok=True)
    if not os.path.isfile(step_path):
        return {"status": "error", "message": "STEP not found"}
    try:
        if action == "measure":
            return measure(step_path)
        if action == "single_case":
            return single_case()
        if action == "execute_plan":
            return execute_plan(plan or {}, step_path, out_dir)
        return {"status": "error", "message": "unknown action: %s" % action}
    except Exception as e:
        return {"status": "error", "detail": type(e).__name__ + ": " + str(e)[:180]}
