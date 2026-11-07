# -*- coding: utf-8 -*-
r"""bridges/desktop_coord.py — 屏幕坐标空间的唯一真源（读屏像素 ↔ 点击坐标）

这里解决的是一个"不报错但一直点歪"的缺陷，实测于本机 2026-11-04：

    默认（进程未声明 DPI 感知）:
        GetSystemMetrics(SM_CXSCREEN) = 1536 x 864   ← 被系统虚拟化的逻辑像素
        PIL ImageGrab.grab().size     = 1920 x 1080  ← 物理像素（截图就是这个尺寸）
        SetCursorPos(1900, 1070) 回读 = (1535, 863)  ← 越界被静默夹紧，没有任何错误
    声明 SetProcessDpiAwarenessContext(PER_MONITOR_AWARE_V2) 之后：
        GetSystemMetrics(SM_CXSCREEN) = 1920 x 1080  ← 与截图一致
        GetDpiForSystem()             = 120（125% 缩放）

也就是说：模型看的是 1920 宽的画面，鼠标坐标系却只有 1536 宽。差值 1.25 倍，
越界不抛异常只夹紧，症状就是"点什么都没反应 / 点偏一格"。任何读屏→点击的闭环
都必须先把这两个空间对齐，并把这个事实告诉模型，否则训得再多也是在学一个歪的坐标系。

本模块只做三件事：
1. ensure_dpi_awareness() —— 在动作发出之前把空间对齐，并如实返回对齐结果；
2. probe_spaces()        —— 量出"截图空间"和"点击空间"是否 1:1；
3. to_click()/check_clickable() —— 唯一的坐标换算入口，越界一律拒绝并给理由，
   绝不像 SetCursorPos 那样静默夹紧。
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import sys
from typing import Any, Dict, Optional, Tuple

_SHIMS = (
    ("SetProcessDpiAwarenessContext", ctypes.c_void_p(-4), 1),  # PER_MONITOR_AWARE_V2
    ("SetProcessDpiAwarenessContext", ctypes.c_void_p(-3), 1),  # PER_MONITOR_AWARE
    ("SetProcessDpiAwareness", ctypes.c_int(2), 1),             # PROCESS_PER_MONITOR_DPI_AWARE
    ("SetProcessDPIAware", None, 0),                            # SYSTEM_DPI_AWARE（最弱兜底）
)

_SM_CXSCREEN, _SM_CYSCREEN = 0, 1
_SM_CXVIRTUALSCREEN, _SM_CYVIRTUALSCREEN = 8, 9
_SM_XVIRTUALSCREEN, _SM_YVIRTUALSCREEN = 76, 77


def ensure_dpi_awareness() -> Dict[str, Any]:
    """把当前进程声明为 DPI 感知，使鼠标坐标系与截图像素系一致。

    返回 {"aware": bool, "via": str|None, "note": str}。失败不抛异常——但调用方
    必须检查 aware，未对齐时不允许发点击（见 check_clickable）。
    """
    u = ctypes.windll.user32
    for name, arg, nargs in _SHIMS:
        fn = getattr(u, name, None)
        if fn is None:
            continue
        try:
            if nargs:
                fn(arg)
            else:
                fn()
        except Exception:  # noqa: BLE001 - 老 Windows 上这些入口会直接抛，逐个降级
            continue
        # 真正生效与否用 metrics 判，不看返回值（SetProcessDPIAware 的返回语义不一致）
        w, h = u.GetSystemMetrics(_SM_CXSCREEN), u.GetSystemMetrics(_SM_CYSCREEN)
        dpi = _dpi()
        if dpi and dpi != 96 and w * h >= _grab_area_hint():
            return {"aware": True, "via": name, "screen": [w, h], "dpi": dpi, "note": ""}
        if dpi is not None:
            return {"aware": True, "via": name, "screen": [w, h], "dpi": dpi,
                    "note": "dpi=%d；仍需与截图像素核对是否 1:1" % dpi}
    w, h = u.GetSystemMetrics(_SM_CXSCREEN), u.GetSystemMetrics(_SM_CYSCREEN)
    return {"aware": False, "via": None, "screen": [w, h], "dpi": _dpi(),
            "note": "全部 DPI 感知入口都不可用，点击坐标与画面像素不一致的风险由调用方承担"}


def _dpi() -> Optional[int]:
    try:
        d = ctypes.windll.user32.GetDpiForSystem()
        return int(d) if d else None
    except Exception:  # noqa: BLE001
        return None


_GRAB_HINT: Optional[int] = None


def _grab_area_hint() -> int:
    """懒加载一次截图尺寸，用来判断 metrics 是否已经是物理像素。"""
    global _GRAB_HINT
    if _GRAB_HINT is None:
        try:
            from PIL import ImageGrab
            im = ImageGrab.grab()
            _GRAB_HINT = im.size[0] * im.size[1]
        except Exception:  # noqa: BLE001
            _GRAB_HINT = 0
    return _GRAB_HINT


def probe_spaces(frame_size: Optional[Tuple[int, int]] = None) -> Dict[str, Any]:
    """量出两个空间：截图像素系 vs 点击坐标系，并给出比例与是否一致。"""
    u = ctypes.windll.user32
    lw, lh = u.GetSystemMetrics(_SM_CXSCREEN), u.GetSystemMetrics(_SM_CYSCREEN)
    vw, vh = u.GetSystemMetrics(_SM_CXVIRTUALSCREEN), u.GetSystemMetrics(_SM_CYVIRTUALSCREEN)
    ox, oy = u.GetSystemMetrics(_SM_XVIRTUALSCREEN), u.GetSystemMetrics(_SM_YVIRTUALSCREEN)
    fw, fh = frame_size if frame_size else (None, None)
    if not fw:
        try:
            from PIL import ImageGrab
            fw, fh = ImageGrab.grab().size
        except Exception:  # noqa: BLE001
            fw, fh = None, None
    ratio = None
    if fw and lw:
        ratio = round(fw / float(lw), 6)
    return {
        "click_space": [lw, lh],
        "virtual_space": [vw, vh],
        "virtual_origin": [ox, oy],
        "frame_space": [fw, fh],
        "dpi": _dpi(),
        "frame_over_click_ratio": ratio,
        "aligned": (ratio is not None and abs(ratio - 1.0) < 1e-3),
    }


def to_click(x: int, y: int, spaces: Optional[Dict[str, Any]] = None,
             ) -> Tuple[Optional[Tuple[int, int]], str]:
    """画面像素 -> 点击坐标；空间不一致时按比例换算并做边界检查。

    返回 (坐标, "") 或 (None, 拒绝理由)。绝不静默夹紧。
    """
    sp = spaces or probe_spaces()
    fw, fh = sp.get("frame_space") or (None, None)
    cw, ch = sp.get("click_space") or (None, None)
    if not all([fw, fh, cw, ch]):
        return None, "无法确定屏幕/画面尺寸，拒绝发送坐标"
    try:
        sx = int(round(x * (cw / float(fw))))
        sy = int(round(y * (ch / float(fh))))
    except (TypeError, ValueError):
        return None, "坐标不是整数像素: (%r, %r)" % (x, y)
    if not (0 <= sx <= cw - 1 and 0 <= sy <= ch - 1):
        return None, ("坐标 %d,%d 换算成点击空间后为 %d,%d，越出可点范围 0..%d x 0..%d"
                      % (x, y, sx, sy, cw - 1, ch - 1))
    if not sp.get("aligned"):
        return (sx, sy), ("scaled_by_ratio:%s（点击空间与画面空间不等，已按比例换算；"
                          "建议先 ensure_dpi_awareness 对齐）" % sp.get("frame_over_click_ratio"))
    return (sx, sy), ""


def check_clickable(spaces: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """发任何点击之前的一票闸：空间没对齐就要求调用方先处理，而不是带着 1.25 倍偏差继续。"""
    sp = spaces or probe_spaces()
    ok = bool(sp.get("aligned"))
    return {
        "ok": ok,
        "reason": "" if ok else (
            "截图空间 %sx%s 与点击空间 %sx%s 不一致（比值 %s）；"
            "先调用 ensure_dpi_awareness()，仍不一致则本步不得发点击"
            % (sp["frame_space"][0], sp["frame_space"][1],
               sp["click_space"][0], sp["click_space"][1],
               sp["frame_over_click_ratio"])),
        "spaces": sp,
    }


def contract_block() -> Dict[str, Any]:
    """给语料/系统提示注入用的坐标契约（实测值，不是假设）。"""
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    except Exception:  # noqa: BLE001
        pass
    sp = probe_spaces()
    return {
        "coordinate_contract": {
            "frame_space": sp["frame_space"],
            "click_space": sp["click_space"],
            "dpi": sp["dpi"],
            "aligned": sp["aligned"],
            "rule": ("汇报坐标一律用截图像素系；发点击前必须经 to_click 换算；"
                     "越界必须拒绝并说明理由，禁止依赖 SetCursorPos 的静默夹紧"),
        }
    }


def sha256_of_source() -> str:
    p = os.path.abspath(__file__)
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


if __name__ == "__main__":
    before = probe_spaces()
    aware = ensure_dpi_awareness()
    after = probe_spaces()
    out = {"before": before, "aware": aware, "after": after,
           "check": check_clickable(after)}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if out["check"]["ok"] else 5)
