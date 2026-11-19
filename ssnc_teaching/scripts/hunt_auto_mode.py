# -*- coding: utf-8 -*-
"""Hunt for AUTO mode: click mode knob, press cycle-start, detect machine motion.

Readback signals (all measured, no guessing):
- pixel diff of 3D view region (AfxFrameOrView100s hwnd 198292) -> motion
- new visible dialog windows -> alarms/prompts
- cycle-start button response
"""
import os, sys, time, ctypes, json
os.environ.setdefault('VIRTU_DESKTOP_INPUT', '1')
os.environ.setdefault('VIRTU_DESKTOP_AGENT', 'ssnc-auto-hunt')
sys.path.insert(0, r'D:\Virtu模型')
from ctypes import wintypes
import virtu_omni.computer_use.input_guard as ig
from virtu_omni.computer_use.action import ActionEngine
from PIL import ImageGrab, ImageChops

u = ctypes.windll.user32
PID = 17464
PANEL = 198528
VIEW = 198292          # 3D machine view
KNOB_ID = 9651
CYC = 9518
OUT = r'D:\Virtu模型\ssnc_teaching\evidence'
LOG = OUT + r'\auto_hunt_log.jsonl'


def view_rect():
    r = wintypes.RECT()
    u.GetWindowRect(VIEW, ctypes.byref(r))
    return (r.left, r.top, r.right, r.bottom)


def grab(path):
    rc = view_rect()
    im = ImageGrab.grab(rc)
    im.save(path)
    return im


def motion_delta(a, b):
    d = ImageChops.difference(a.convert('RGB'), b.convert('RGB'))
    hist = d.convert('L').histogram()
    return sum(hist[10:])


def dialogs():
    res = []
    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hw, lp):
        p = wintypes.DWORD()
        u.GetWindowThreadProcessId(hw, ctypes.byref(p))
        if p.value == PID and u.IsWindowVisible(hw):
            c = ctypes.create_unicode_buffer(64)
            u.GetClassNameW(hw, c, 64)
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
            res.append({'hwnd': hw, 'cls': c.value, 'title': t.value,
                        'texts': texts[:10]})
        return True
    u.EnumWindows(cb, 0)
    return res


def dismiss():
    for d in dialogs():
        if d['hwnd'] in (PANEL, 394740, 199500, VIEW):
            continue
        hw = d['hwnd']
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
    return h


def knob(eng):
    h = u.GetDlgItem(PANEL, KNOB_ID)
    r = wintypes.RECT()
    u.GetWindowRect(h, ctypes.byref(r))
    eng.click((r.left + r.right) // 2, (r.top + r.bottom) // 2, hwnd=PANEL)
    time.sleep(0.4)


def main():
    eng = ActionEngine()
    log = open(LOG, 'a', encoding='utf-8')
    base = grab(OUT + r'\view_base.png')
    print('view rect', view_rect())

    for i in range(1, 9):
        knob(eng)
        time.sleep(0.3)
        before = grab(OUT + r'\view_step%d_before.png' % i)
        bm(CYC)
        time.sleep(1.2)
        after = grab(OUT + r'\view_step%d_after.png' % i)
        delta = motion_delta(before, after)
        dlgs = [d for d in dialogs() if d['hwnd'] not in
                (PANEL, 394740, 199500, VIEW, 199742)]
        rec = {'step': i, 'motion_px': delta, 'dialogs': dlgs}
        print('step', i, 'motion_px', delta, 'dialogs',
              [(d['hwnd'], d['texts'][:3]) for d in dlgs])
        log.write(json.dumps(rec, ensure_ascii=False) + '\n')
        log.flush()
        dismiss()
        if delta > 5000:
            print('>>> MOTION DETECTED - likely AUTO running')
            break

    # final: leave machine stopped if running? press cycle stop candidate later
    log.close()


if __name__ == '__main__':
    main()
    for rec in ig.audit_tail(3):
        print('audit:', rec)
