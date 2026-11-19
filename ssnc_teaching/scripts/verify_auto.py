# -*- coding: utf-8 -*-
"""Verify AUTO mode definitively:
- dismiss modals
- one CW detent drag on mode knob 9651
- cycle start (BM_CLICK 9518)
- sample 3D view 6x over 6s: continuous motion = AUTO program running
- record prompt presence per step to map mode cycle
"""
import os, sys, time, ctypes, math, json
os.environ['VIRTU_DESKTOP_INPUT'] = '1'
os.environ['VIRTU_DESKTOP_AGENT'] = 'verify-auto'
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
LOG = []


def knob_center():
    h = u.GetDlgItem(PANEL, KNOB)
    r = wintypes.RECT()
    u.GetWindowRect(h, ctypes.byref(r))
    return ((r.left + r.right) // 2, (r.top + r.bottom) // 2)


def detent(cx, cy):
    a0, a1 = -90.0, 90.0
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


def vrect():
    r = wintypes.RECT()
    u.GetWindowRect(VIEW, ctypes.byref(r))
    return (r.left, r.top, r.right, r.bottom)


def shot():
    return ImageGrab.grab(vrect())


def dpx(a, b):
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


def has_prompt():
    for hw, t, texts in dialogs():
        if hw in (PANEL, 394740, 199500, VIEW):
            continue
        for x in texts:
            if '模式' in x or 'AUTO' in x or '确定' in x:
                return (hw, texts)
    return None


def dismiss_all():
    for _ in range(8):
        if u.IsWindowEnabled(PANEL):
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
    return u.IsWindowEnabled(PANEL) != 0


def main():
    cx, cy = knob_center()
    print('knob', cx, cy)
    dismiss_all()
    for i in range(1, 9):
        detent(cx, cy)
        time.sleep(0.5)
        pr = has_prompt()
        # press cycle start only if no modal
        if u.IsWindowEnabled(PANEL):
            h = u.GetDlgItem(PANEL, CYC)
            u.SendMessageW(h, 0x00F5, 0, 0)
        time.sleep(0.5)
        # sample 6 frames over 5s
        frames = []
        prev = shot()
        motions = []
        for k in range(6):
            time.sleep(0.8)
            cur = shot()
            motions.append(dpx(prev, cur))
            prev = cur
        pr2 = has_prompt()
        running = sum(1 for m in motions if m > 3000)
        rec = {'detent': i, 'pre_prompt': bool(pr), 'motions': motions,
               'running_frames': running, 'post_prompt': bool(pr2)}
        LOG.append(rec)
        print('detent', i, 'pre_prompt', bool(pr), 'motions', motions,
              'running_frames', running, 'post_prompt', bool(pr2))
        with open(OUT + r'\verify_auto_log.jsonl', 'a', encoding='utf-8') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        dismiss_all()
        if running >= 3:
            print('>>> CONTINUOUS MOTION = AUTO CONFIRMED')
            break


if __name__ == '__main__':
    main()
    for rec in ig.audit_tail(3):
        print('audit:', rec)
