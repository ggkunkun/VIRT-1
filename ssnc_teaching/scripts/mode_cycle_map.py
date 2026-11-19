# -*- coding: utf-8 -*-
"""Definitive mode-knob map via OCR readback of the on-screen mode indicator.

Mode indicator location (measured 2026-11-19, maximized main window):
  window-relative approx x 1130-1240, y 410-470  ->  tokens like JOG**, AUTO, EDIT, MDI

For each CW detent: drag knob -> sleep -> OCR crop -> record mode name.
Detects wrap when a mode repeats. No cycle-start needed.
"""
import os, sys, time, ctypes, math, json, re
os.environ['VIRTU_DESKTOP_INPUT'] = '1'
os.environ['VIRTU_DESKTOP_AGENT'] = 'mode-cycle-map'
sys.path.insert(0, r'D:\Virtu模型')
from ctypes import wintypes
import virtu_omni.computer_use.input_guard as ig
from PIL import ImageGrab
from rapidocr_onnxruntime import RapidOCR

u = ctypes.windll.user32
OUT = r'D:\Virtu模型\ssnc_teaching\evidence'
LOG = OUT + r'\mode_cycle_map.jsonl'
DOWN, UP = 0x0002, 0x0004

# mode-indicator crop relative to main-window rect (from OCR bbox measurement)
RX0, RY0, RX1, RY1 = 1120, 405, 1260, 480
MODE_RE = re.compile(r'(AUTO|EDIT|MDI|JOG|REF|HANDLE|TEACH|DNC|INC)', re.I)

_ocr = None


def ocr():
    global _ocr
    if _ocr is None:
        _ocr = RapidOCR()
    return _ocr


def find_main():
    res = []
    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(h, l):
        if u.IsWindowVisible(h):
            t = ctypes.create_unicode_buffer(200)
            u.GetWindowTextW(h, t, 200)
            if 'SwanSoft CNC' in t.value and 'Login' not in t.value:
                res.append(h)
        return True
    u.EnumWindows(cb, 0)
    return res[0] if res else None


def find_panel(pid):
    res = []
    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(h, l):
        p = wintypes.DWORD()
        u.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value == pid and u.GetDlgItem(h, 9651):
            res.append(h)
        return True
    u.EnumWindows(cb, 0)
    return res[0] if res else None


def knob_center(panel):
    h = u.GetDlgItem(panel, 9651)
    r = wintypes.RECT()
    u.GetWindowRect(h, ctypes.byref(r))
    return ((r.left + r.right) // 2, (r.top + r.bottom) // 2)


def detent(cx, cy, cw=True):
    a0, a1 = (-90.0, 90.0) if cw else (90.0, -90.0)
    steps = 24
    with ig.input_session('drag', x=cx, y=cy, require_bounds=True) as ctx:
        if ctx['dry_run']:
            return False
        u.SetCursorPos(int(cx + 30 * math.cos(math.radians(a0))),
                       int(cy + 30 * math.sin(math.radians(a0))))
        time.sleep(0.05)
        u.mouse_event(DOWN, 0, 0, 0, 0)
        try:
            for i in range(1, steps + 1):
                a = math.radians(a0 + (a1 - a0) * i / steps)
                u.SetCursorPos(int(cx + 30 * math.cos(a)),
                               int(cy + 30 * math.sin(a)))
                time.sleep(0.04)
        finally:
            u.mouse_event(UP, 0, 0, 0, 0)
        return True


def read_mode(main_h):
    r = wintypes.RECT()
    u.GetWindowRect(main_h, ctypes.byref(r))
    box = (r.left + RX0, r.top + RY0, r.left + RX1, r.top + RY1)
    im = ImageGrab.grab(box)
    tmp = os.path.join(OUT, '_mode_crop.png')
    im.save(tmp)
    res, _ = ocr()(tmp)
    texts = [t for _, t, c in (res or [])]
    for t in texts:
        m = MODE_RE.search(t.upper())
        if m:
            return m.group(1).upper(), texts
    return None, texts


def main():
    main_h = find_main()
    pid = wintypes.DWORD()
    u.GetWindowThreadProcessId(main_h, ctypes.byref(pid))
    panel = find_panel(pid.value)
    print('main', main_h, 'panel', panel, flush=True)
    cx, cy = knob_center(panel)
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 9
    cw = (sys.argv[2] != 'ccw') if len(sys.argv) > 2 else True

    seen = []
    for i in range(n):
        mode, texts = read_mode(main_h)
        print('pre-detent', i, 'mode=', mode, texts, flush=True)
        detent(cx, cy, cw=cw)
        time.sleep(0.8)
        mode2, texts2 = read_mode(main_h)
        rec = {'step': i, 'before': mode, 'after': mode2,
               'after_texts': texts2}
        with open(LOG, 'a', encoding='utf-8') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        print('  -> after:', mode2, texts2, flush=True)
        seen.append(mode2)
        # stop early if wrapped to a previously seen mode (full cycle covered)
        if mode2 and mode2 in seen[:-1]:
            print('>>> wrapped at step', i, flush=True)
            break
        time.sleep(0.3)

    for rec in ig.audit_tail(3):
        print('audit:', rec)


if __name__ == '__main__':
    main()
