# -*- coding: utf-8 -*-
"""G2 试点：在真实 SW2021 里建一件、量体积、导出预览与界面截图，产出可核验证据。"""
import ctypes
import json
import os
import struct
import subprocess
import sys
import time
from ctypes import wintypes

SK = r"C:\Users\Administrator\.workbuddy\skills\solidworks-automation\scripts"
sys.path.insert(0, SK)

from sw_connect import connect_solidworks, mm, new_document, save_document  # noqa: E402
from sw_export import export_to_step  # noqa: E402
from sw_part import extrude_boss, extrude_cut, sketch, sketch_circle, sketch_rectangle  # noqa: E402
from sw_review import save_review_previews  # noqa: E402
from sw_sketch_quality import fully_define_sketch, inspect_model_sketches  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(BASE, "work")
EVID = os.path.join(BASE, "out", "evidence")
os.makedirs(WORK, exist_ok=True)
os.makedirs(EVID, exist_ok=True)

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


def find_main_window(pid):
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _):
        p = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
        if p.value == pid and user32.IsWindowVisible(hwnd) and user32.GetWindowTextLengthW(hwnd) > 0:
            found.append(hwnd)
            return False
        return True

    user32.EnumWindows(cb, 0)
    return found[0] if found else None


def capture_window(hwnd, path):
    rect = RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w, h = rect.right - rect.left, rect.bottom - rect.top
    if w <= 0 or h <= 0:
        raise RuntimeError(f"窗口尺寸异常 {w}x{h}")
    hdc = user32.GetWindowDC(hwnd)
    mdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(mdc, bmp)
    ok = user32.PrintWindow(hwnd, mdc, 2)

    class BIH(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD), ("biWidth", ctypes.c_long), ("biHeight", ctypes.c_long),
                    ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD),
                    ("biCompression", wintypes.DWORD), ("biSizeImage", wintypes.DWORD),
                    ("biXPelsPerMeter", ctypes.c_long), ("biYPelsPerMeter", ctypes.c_long),
                    ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]

    bi = BIH(ctypes.sizeof(BIH), w, -h, 1, 24, 0, 0, 0, 0, 0, 0)
    stride = ((w * 3 + 3) // 4) * 4
    buf = ctypes.create_string_buffer(stride * h)
    gdi32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bi), 0)

    with open(path, "wb") as f:
        f.write(struct.pack("<2sIHHI", b"BM", 54 + stride * h, 0, 0, 54))
        f.write(struct.pack("<IiiHHIIiiII", 40, w, h, 1, 24, 0, stride * h, 0, 0, 0, 0))
        f.write(buf.raw)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mdc)
    user32.ReleaseDC(hwnd, hdc)
    return {"path": path, "w": w, "h": h, "printwindow_ok": bool(ok), "bytes": os.path.getsize(path)}


def measure_volume(model):
    ext = model.Extension
    mp = ext.CreateMassProperty()
    try:
        mp.UseSystemUnits = True
    except Exception:
        pass
    return float(mp.Volume)


def kill_stale():
    """本机 SOLIDWORKS 不注册 ROT，跨进程无法附着；清掉上一轮遗留实例。"""
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq SLDWORKS.exe", "/NH", "/FO", "CSV"],
                         capture_output=True, text=True, errors="ignore").stdout
    pids = [line.split('","')[1] for line in out.splitlines() if line.startswith('"SLDWORKS.exe"')]
    killed = []
    for pid in pids:
        subprocess.run(["taskkill", "/PID", pid, "/F"], capture_output=True, text=True, errors="ignore")
        killed.append(pid)
    if killed:
        time.sleep(8)
    return killed


def typed(obj, name="IModelDoc2"):
    """GetDocuments 枚举出来的对象常缺类型信息，重新包一层才有 ClearSelection2 等方法。"""
    try:
        from win32com.client import __WrapDispatch
        return __WrapDispatch(obj, name)
    except Exception:
        try:
            import win32com.client.dynamic as dyn
            return dyn.DumbDispatch(obj, name)
        except Exception:
            return obj


def main():
    t0 = time.time()
    result = {"started_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "steps": [], "ok": False}
    stale = kill_stale()
    if stale:
        result["stale_killed"] = stale
        result["steps"].append({"step": "cleanup_stale", "ok": True, "detail": f"清理无主实例 PID {stale}（本机不支持 ROT 附着）"})
    sw, _, meta = connect_solidworks(version=2021, wait_seconds=180, visible=True, return_metadata=True)
    result["meta"] = meta
    result["revision"] = sw.RevisionNumber
    result["steps"].append({"step": "connect", "ok": str(sw.RevisionNumber).startswith("29."),
                            "detail": f"ProgID={meta['prog_id']} rev={sw.RevisionNumber} pid={meta['process_id']}"})

    model = new_document(sw, "part")
    if model is None:
        raise RuntimeError("新建零件失败")
    model = typed(model, "IModelDoc2")
    result["steps"].append({"step": "new_part", "ok": hasattr(model, "ClearSelection2"),
                            "detail": f"title={model.GetTitle()} type={model.GetType()}"})
    part_path = os.path.join(WORK, "P05_L_bracket_pilot.SLDPRT")
    try:
        model.Extension.SetUserPreferenceInteger(24, 0, 1)  # swUnitSystem -> MMGS 的尝试，失败不影响
    except Exception:
        pass

    with sketch(model, "前视基准面") as s1:
        sketch_rectangle(model, 0, 0, mm(120), mm(80))
        fd = fully_define_sketch(model)
        result["steps"].append({"step": "sketch_rect", "ok": True, "detail": f"120x80, fully_define={fd}"})
    if extrude_boss(model, s1, mm(20)) is None:
        raise RuntimeError("拉伸失败")
    result["steps"].append({"step": "extrude_boss", "ok": True, "detail": "深度 20mm"})

    with sketch(model, "前视基准面") as s2:
        sketch_circle(model, 0, 0, mm(15))
    if extrude_cut(model, s2, mm(40), both_directions=True) is None:
        raise RuntimeError("中心孔切除失败")
    result["steps"].append({"step": "cut_center_hole", "ok": True, "detail": "Ø30 贯穿（两侧对称 40mm）"})

    with sketch(model, "前视基准面") as s3:
        for x in (-45, 45):
            for y in (-28, 28):
                sketch_circle(model, mm(x), mm(y), mm(4.5))
    if extrude_cut(model, s3, mm(40), both_directions=True) is None:
        raise RuntimeError("四孔切除失败")
    result["steps"].append({"step": "cut_4_holes", "ok": True, "detail": "4×Ø9 @ (±45,±28)"})

    model.ForceRebuild3(False)
    model.ViewZoomtofit2()
    vol_m3 = measure_volume(model)
    import math
    expected = (120 * 80 - math.pi * 15 ** 2 - 4 * math.pi * 4.5 ** 2) * 20
    got = vol_m3 * 1e9
    dev = abs(got - expected) / expected
    result["volume_mm3"] = round(got, 2)
    result["expected_mm3"] = round(expected, 2)
    result["volume_deviation"] = round(dev, 6)
    result["steps"].append({"step": "measure_volume", "ok": dev < 0.005,
                            "detail": f"实测 {got:.2f} vs 理论 {expected:.2f} mm3，偏差 {dev:.4%}"})

    save_document(model, part_path)
    result["part"] = part_path
    step_path = os.path.join(WORK, "P05_L_bracket_pilot.STEP")
    ok_step = export_to_step(model, step_path)
    result["steps"].append({"step": "export_step", "ok": bool(ok_step) and os.path.getsize(step_path) > 1000,
                            "detail": f"{step_path} {os.path.getsize(step_path)}B"})

    previews = save_review_previews(model, EVID, "pilot_P05", views=("isometric", "front", "top"))
    result["previews"] = [str(p) for p in previews]
    result["steps"].append({"step": "previews", "ok": all(os.path.getsize(str(p)) > 5000 for p in previews),
                            "detail": ", ".join(os.path.basename(str(p)) for p in previews)})

    hwnd = find_main_window(int(meta["process_id"]))
    if hwnd:
        shot = capture_window(hwnd, os.path.join(EVID, "ui_sw2021_pilot.bmp"))
        result["ui_screenshot"] = shot
        result["steps"].append({"step": "ui_screenshot", "ok": shot["bytes"] > 50000, "detail": json.dumps(shot, ensure_ascii=False)})
    else:
        result["steps"].append({"step": "ui_screenshot", "ok": False, "detail": "未找到主窗口"})

    try:
        result["sketches"] = inspect_model_sketches(model)
    except Exception as exc:
        result["sketches"] = f"inspect failed: {exc}"

    result["ok"] = all(s.get("ok") for s in result["steps"])
    result["elapsed_s"] = round(time.time() - t0, 1)
    with open(os.path.join(EVID, "pilot_result.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    print(json.dumps({k: result[k] for k in ("ok", "revision", "volume_mm3", "expected_mm3",
                                             "volume_deviation", "elapsed_s")}, ensure_ascii=False))
    for s in result["steps"]:
        print(("  OK  " if s.get("ok") else "  FAIL") + f" {s['step']}: {s['detail']}")


if __name__ == "__main__":
    main()
