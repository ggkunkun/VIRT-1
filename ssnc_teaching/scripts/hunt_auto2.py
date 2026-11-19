# -*- coding: utf-8 -*-
"""Find AUTO mode: CW arc-drag mode knob (id 9651) one detent at a time,
press cycle-start, detect 3D-view motion = AUTO running."""
import os, sys, time, ctypes, math, json
os.environ['VIRTU_DESKTOP_INPUT'] = '1'
os.environ['VIRTU_DESKTOP_AGENT'] = 'hunt-auto2'
sys.path.insert(0, r'D:\Virtu模型')
from ctypes import wintypes
import virtu_omni.computer_use.input_guard as ig
from PIL import ImageGrab, ImageChops

u = ctypes.windll.user32
PID = 17464
PANEL = 198528
VIEW = 198292
CYC = 9518
KNOB = 9651
OUT = r'D:\Virtu模型\ssnc_teaching\evidence'
DOWN, UP = 0x0002, 0x0004


def knob_center():
    h = u.GetDlgItem(PANEL, KNOB)
    r = wintypes.RECT()
    u.GetWindowRect(h, ctypes.byref(r))
    return ((r.left + r.right) // 2, (r.top + r.bottom) // 2)


def detent_drag(cx, cy, clockwise=True):
    """Short arc drag ~40deg = one detent."""
    a0, a1 = (-60, 60) if clockwise else (60, -60)
    steps = 14
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


def shot(name):
    r = wintypes.RECT()
    u.GetWindowRect(VIEW, ctypes.byref(r))
    im = ImageGrab.grab((r.left, r.top, r.right, r.bottom))
    im.save(os.path.join(OUT, name))
    return im


def delta(a, b):
    d = ImageChops.difference(a.convert('RGB'), b.convert('RGB'))
    return sum(d.convert('L').histogram()[10:])


def dialogs():
    res = []
    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hw, lp):
        p = wintypes.DWORD()
        u.GetWindowThreadProcessId(hw, ctypes.byref(p))
        if p.value == PID and u.IsWindowVisible(hw):
            t = ctypes.create_unicode_buffer(300)
            u.GetWindowTextW(hw, t, 300)
            texts = []
            @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            def cc(ch, l2):
                tt = ctypes.create_unicode_buffer(300)
                u.GetWindowTextW(ch, tt, 300)
                if tt.value:
                    texts.append(tt.value)
                return True
            u.EnumChildWindows(hw, cc, 0)
            res.append((hw, t.value, texts[:4]))
        return True
    u.EnumWindows(cb, 0)
    return res


def dismiss():
    for hw, t, texts in dialogs():
        if hw in (PANEL, 394740, 199500, VIEW):
            continue
        btns = []
        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def cc(ch, l2):
            c = ctypes.create_unicode_buffer(64)
            u.GetClassNameW(ch, c, 64)
            if c.value == 'Button':
                btns.append(ch)
            return True
        u.EnumChildWindows(hw, cc, 0)
        if btns:
            u.SendMessageW(btns[0], 0x00F5, 0, 0)
        else:
            u.PostMessageW(hw, 0x0010, 0, 0)
        time.sleep(0.3)


def bm(cid):
    h = u.GetDlgItem(PANEL, cid)
    if h:
        u.SendMessageW(h, 0x00F5, 0, 0)


def main():
    cx, cy = knob_center()
    print('knob center', cx, cy)
    shot('h2_base.png')
    for i in range(1, 11):
        detent_drag(cx, cy, clockwise=True)
        time.sleep(0.4)
        b = shot('h2_b%d.png' % i)
        bm(CYC)
        time.sleep(1.0)
        a = shot('h2_a%d.png' % i)
        d = delta(b, a)
        dl = [x for x in dialogs() if x[0] not in
              (PANEL, 394740, 199500, VIEW)]
        print('detent', i, 'motion_px', d,
              'dlgs', [(x[0], x[2][:2]) for x in dl])
        dismiss()
        if d > 8000:
            print('>>> AUTO MOTION DETECTED at detent', i)
            break


if __name__ == '__main__':
    main()
