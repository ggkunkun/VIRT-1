# -*- coding: utf-8 -*-
"""Arc-drag the SSCNC mode knob candidate; verify via cycle-start prompt."""
import os, sys, time, ctypes, math, json
os.environ['VIRTU_DESKTOP_INPUT'] = '1'
os.environ['VIRTU_DESKTOP_AGENT'] = 'knob-drag'
sys.path.insert(0, r'D:\Virtu模型')
from ctypes import wintypes
import virtu_omni.computer_use.input_guard as ig

u = ctypes.windll.user32
PID = 17464
PANEL = 198528
VIEW = 198292
CYC = 9518
OUT = r'D:\Virtu模型\ssnc_teaching\evidence'
DOWN = 0x0002
UP = 0x0004
MOVE = 0x0001


def knob_rect(cid):
    h = u.GetDlgItem(PANEL, cid)
    r = wintypes.RECT()
    u.GetWindowRect(h, ctypes.byref(r))
    return (r.left, r.top, r.right, r.bottom)


def arc_drag(cx, cy, r_px, a0, a1, steps=24, dur=0.9):
    """Drag along arc inside one input_session lease."""
    with ig.input_session('drag', x=cx, y=cy, require_bounds=True) as ctx:
        if ctx['dry_run']:
            print('dryrun/denied', ctx.get('reason'))
            return False
        u.SetCursorPos(cx, cy)
        time.sleep(0.05)
        u.mouse_event(DOWN, 0, 0, 0, 0)
        try:
            for i in range(1, steps + 1):
                a = math.radians(a0 + (a1 - a0) * i / steps)
                x = int(cx + r_px * math.cos(a))
                y = int(cy + r_px * math.sin(a))
                u.SetCursorPos(x, y)
                time.sleep(dur / steps)
        finally:
            u.mouse_event(UP, 0, 0, 0, 0)
        return True


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


def probe(label):
    bm(CYC)
    time.sleep(1.0)
    dl = [x for x in dialogs() if x[0] not in (PANEL, 394740, 199500, VIEW)]
    print(label, '->', [(x[0], x[2][:2]) for x in dl])
    dismiss()
    return dl


def main():
    for cid in (9651, 9650, 9652):
        rc = knob_rect(cid)
        cx, cy = (rc[0] + rc[2]) // 2, (rc[1] + rc[3]) // 2
        print('knob id', cid, 'rect', rc, 'center', cx, cy)
        # clockwise arc drag top->right->bottom (angles -90..90 deg)
        ok = arc_drag(cx, cy, 30, -90, 90, steps=24, dur=1.0)
        print('  cw drag ok', ok)
        time.sleep(0.4)
        probe('  after CW')
        # counter-clockwise
        ok = arc_drag(cx, cy, 30, 90, -90, steps=24, dur=1.0)
        print('  ccw drag ok', ok)
        time.sleep(0.4)
        probe('  after CCW')


if __name__ == '__main__':
    main()
    for rec in ig.audit_tail(4):
        print('audit:', rec)
