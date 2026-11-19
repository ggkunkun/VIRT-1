# -*- coding: utf-8 -*-
"""v3: proven 180deg CW detent drag on mode knob id 9651.
Safety: skip cycle-start if panel disabled (modal up); dismiss modals first.
Detect AUTO by 3D-view pixel motion after cycle start."""
import os, sys, time, ctypes, math
os.environ['VIRTU_DESKTOP_INPUT'] = '1'
os.environ['VIRTU_DESKTOP_AGENT'] = 'hunt-auto3'
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


def detent(cx, cy):
    a0, a1 = -90.0, 90.0   # proven CW 180deg
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


def panel_enabled():
    return u.IsWindowEnabled(PANEL) != 0


def dismiss_all():
    """Click every button of every non-panel dialog until panel re-enabled."""
    for _ in range(6):
        if panel_enabled():
            return True
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
        time.sleep(0.4)
    return panel_enabled()


def main():
    cx, cy = knob_center()
    print('knob center', cx, cy, 'panel_enabled', panel_enabled())
    dismiss_all()
    shot('h3_base.png')
    for i in range(1, 9):
        if not panel_enabled():
            dismiss_all()
        detent(cx, cy)
        time.sleep(0.5)
        if not panel_enabled():
            # modal appeared right after drag? shouldn't happen; dismiss
            dismiss_all()
        b = shot('h3_b%d.png' % i)
        # only press cycle start if panel enabled (no modal)
        cyc_ok = panel_enabled()
        if cyc_ok:
            h = u.GetDlgItem(PANEL, CYC)
            u.SendMessageW(h, 0x00F5, 0, 0)
            time.sleep(1.0)
        else:
            print('step', i, 'panel disabled, skip cycle')
        a = shot('h3_a%d.png' % i)
        d = delta(b, a)
        dl = [x for x in dialogs() if x[0] not in
              (PANEL, 394740, 199500, VIEW)]
        print('detent', i, 'motion_px', d, 'cyc_ok', cyc_ok,
              'dlgs', [(x[0], x[2][:2]) for x in dl])
        dismiss_all()
        if d > 8000:
            print('>>> AUTO MOTION at detent', i)
            break


if __name__ == '__main__':
    main()
