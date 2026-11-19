# -*- coding: utf-8 -*-
"""Probe the SSCNC FANUC op-panel mode knob (Static id 9651).
Evidence-driven: measured hwnd/rect, input via ActionEngine (input_guard),
readback via pixel diff + dialog detection."""
import os, sys, time, ctypes, math, json
os.environ.setdefault('VIRTU_DESKTOP_INPUT', '1')
os.environ.setdefault('VIRTU_DESKTOP_AGENT', 'ssnc-knob-probe')
sys.path.insert(0, r'D:\Virtu模型')
from ctypes import wintypes
import virtu_omni.computer_use.input_guard as ig
from virtu_omni.computer_use.action import ActionEngine
from PIL import ImageGrab, ImageChops

u = ctypes.windll.user32
PANEL = 198528
KNOB_ID = 9651
OUT = r'D:\Virtu模型\ssnc_teaching\evidence'


def knob_hwnd():
    return u.GetDlgItem(PANEL, KNOB_ID)


def rect_of(h):
    r = wintypes.RECT()
    u.GetWindowRect(h, ctypes.byref(r))
    return (r.left, r.top, r.right, r.bottom)


def grab(rect, path):
    im = ImageGrab.grab(rect)
    im.save(path)
    return im


def diff(a, b):
    d = ImageChops.difference(a.convert('RGB'), b.convert('RGB'))
    bbox = d.getbbox()
    if not bbox:
        return 0, None
    hist = d.convert('L').histogram()
    return sum(hist[8:]), bbox


def visible_dialogs(pid):
    dlg = []
    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hw, lp):
        p = wintypes.DWORD()
        u.GetWindowThreadProcessId(hw, ctypes.byref(p))
        if p.value == pid and u.IsWindowVisible(hw):
            t = ctypes.create_unicode_buffer(200)
            u.GetWindowTextW(hw, t, 200)
            if t.value:
                dlg.append((hw, t.value))
        return True
    u.EnumWindows(cb, 0)
    return dlg


def main():
    h = knob_hwnd()
    print('knob hwnd', h)
    if not h:
        print('knob not found')
        return
    rc = rect_of(h)
    print('knob rect', rc)
    cx, cy = (rc[0] + rc[2]) // 2, (rc[1] + rc[3]) // 2
    print('center', cx, cy)

    pad = 40
    region = (rc[0] - pad, rc[1] - pad, rc[2] + pad, rc[3] + pad)
    im0 = grab(region, OUT + r'\knob_before.png')

    eng = ActionEngine()

    # Test 1: real click at center
    r = eng.click(cx, cy, hwnd=PANEL)
    print('click ->', {k: r.get(k) for k in ('ok', 'input_sent', 'status')})
    time.sleep(0.8)
    im1 = grab(region, OUT + r'\knob_after_click.png')
    n, bb = diff(im0, im1)
    print('click pixel-diff changed px:', n, 'bbox:', bb)
    print('dialogs:', visible_dialogs(17464))

    # Test 2: straight-line drag downward (knob drag candidate)
    r = eng.drag(cx, cy, cx, cy + 60, steps=12, hwnd=PANEL) \
        if 'hwnd' in eng.drag.__code__.co_varnames else \
        eng.drag(cx, cy, cx, cy + 60, steps=12)
    print('drag ->', {k: r.get(k) for k in ('ok', 'input_sent', 'status')})
    time.sleep(0.8)
    im2 = grab(region, OUT + r'\knob_after_drag.png')
    n2, bb2 = diff(im0, im2)
    print('drag pixel-diff changed px:', n2, 'bbox:', bb2)
    print('dialogs:', visible_dialogs(17464))


if __name__ == '__main__':
    main()
    for rec in ig.audit_tail(5):
        print('audit:', rec)
