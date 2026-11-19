# -*- coding: utf-8 -*-
"""Cycle the SSCNC mode knob and read back mode via mode-dependent prompts."""
import os, sys, time, ctypes, json
os.environ.setdefault('VIRTU_DESKTOP_INPUT', '1')
os.environ.setdefault('VIRTU_DESKTOP_AGENT', 'ssnc-mode-cycle')
sys.path.insert(0, r'D:\Virtu模型')
from ctypes import wintypes
import virtu_omni.computer_use.input_guard as ig
from virtu_omni.computer_use.action import ActionEngine

u = ctypes.windll.user32
PID = 17464
PANEL = 198528
KNOB_ID = 9651
OUT = r'D:\Virtu模型\ssnc_teaching\evidence\mode_cycle_log.jsonl'
KNOWN = {198528, 394740, 199500, 199742}


def all_dialogs():
    res = []
    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hw, lp):
        p = wintypes.DWORD()
        u.GetWindowThreadProcessId(hw, ctypes.byref(p))
        if p.value != PID or not u.IsWindowVisible(hw) or hw in KNOWN:
            return True
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
        res.append({'hwnd': hw, 'class': c.value, 'title': t.value,
                    'texts': texts[:12]})
        return True
    u.EnumWindows(cb, 0)
    return res


def dismiss_dialogs():
    for d in all_dialogs():
        hw = d['hwnd']
        btn = []
        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def cc(ch, l2):
            c = ctypes.create_unicode_buffer(64)
            u.GetClassNameW(ch, c, 64)
            if c.value == 'Button':
                btn.append(ch)
            return True
        u.EnumChildWindows(hw, cc, 0)
        if btn:
            u.SendMessageW(btn[0], 0x00F5, 0, 0)
        else:
            u.PostMessageW(hw, 0x0010, 0, 0)
        time.sleep(0.4)


def bm_click(cid):
    h = u.GetDlgItem(PANEL, cid)
    if not h:
        return None
    u.SendMessageW(h, 0x00F5, 0, 0)
    time.sleep(0.8)
    return h


def knob_click(eng):
    h = u.GetDlgItem(PANEL, KNOB_ID)
    r = wintypes.RECT()
    u.GetWindowRect(h, ctypes.byref(r))
    cx, cy = (r.left + r.right) // 2, (r.top + r.bottom) // 2
    eng.click(cx, cy, hwnd=PANEL)
    time.sleep(0.5)


def main():
    eng = ActionEngine()
    log = open(OUT, 'a', encoding='utf-8')

    for name, cid in [('jog9586', 9586), ('cyc9518', 9518)]:
        bm_click(cid)
        dlgs = all_dialogs()
        rec = {'step': 'baseline_' + name, 'dialogs': dlgs}
        print('baseline', name, '->', dlgs)
        log.write(json.dumps(rec, ensure_ascii=False) + '\n')
        log.flush()
        dismiss_dialogs()

    for i in range(1, 7):
        knob_click(eng)
        bm_click(9586)
        dlgs = all_dialogs()
        rec = {'step': 'knob_click_%d' % i, 'dialogs': dlgs}
        print('knob click', i, '->', dlgs)
        log.write(json.dumps(rec, ensure_ascii=False) + '\n')
        log.flush()
        dismiss_dialogs()

    log.close()


if __name__ == '__main__':
    main()
