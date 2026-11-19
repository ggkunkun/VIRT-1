# -*- coding: utf-8 -*-
"""Map every mode-knob detent to observable behavior (hang-safe version).

All cross-process window text/message ops use SendMessageTimeoutW so a busy
SSCNC thread cannot wedge the probe. No hardcoded hwnd.
"""
import os, sys, time, ctypes, math, json
os.environ['VIRTU_DESKTOP_INPUT'] = '1'
os.environ['VIRTU_DESKTOP_AGENT'] = 'mode-detent-map'
sys.path.insert(0, r'D:\Virtu模型')
from ctypes import wintypes
import virtu_omni.computer_use.input_guard as ig
from PIL import ImageGrab, ImageChops

u = ctypes.windll.user32
OUT = r'D:\Virtu模型\ssnc_teaching\evidence'
LOG = OUT + r'\mode_detent_map.jsonl'
DOWN, UP = 0x0002, 0x0004
SMTO = 0x0002  # SMTO_ABORTIFHUNG
WM_GETTEXT = 0x000D
BM_CLICK = 0x00F5
WM_NULL = 0x0000


def stext(h, n=300):
    """Timeout-safe window text (WM_GETTEXT). Returns '' if hung/timeout."""
    buf = ctypes.create_unicode_buffer(n)
    res = ctypes.c_size_t(0)
    ok = u.SendMessageTimeoutW(h, WM_GETTEXT, n,
                             ctypes.cast(buf, ctypes.c_void_p),
                             SMTO, 800, ctypes.byref(res))
    return buf.value if ok else ''


def sclick(h, ms=1500):
    res = ctypes.c_size_t(0)
    return u.SendMessageTimeoutW(h, BM_CLICK, 0, 0, SMTO, ms,
                                 ctypes.byref(res))


def responsive(h, ms=400):
    res = ctypes.c_size_t(0)
    return u.SendMessageTimeoutW(h, WM_NULL, 0, 0, SMTO, ms,
                                 ctypes.byref(res)) != 0


def find_main():
    res = []
    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(h, l):
        if u.IsWindowVisible(h):
            t = stext(h, 200)
            if 'SwanSoft CNC' in t and 'Login' not in t:
                res.append(h)
        return True
    u.EnumWindows(cb, 0)
    return res[0] if res else None


def find_controls(main, pid):
    panel = view = crt = None
    others = []
    tops = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def top_cb(h, l):
        p = wintypes.DWORD()
        u.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value == pid and u.IsWindowVisible(h):
            tops.append(h)
        return True
    u.EnumWindows(top_cb, 0)

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(ch, l):
        nonlocal view
        c = ctypes.create_unicode_buffer(64)
        u.GetClassNameW(ch, c, 64)
        if c.value == 'AfxFrameOrView100s' and view is None:
            view = ch
        return True
    u.EnumChildWindows(main, cb, 0)

    for h in tops:
        if h == main:
            continue
        c = ctypes.create_unicode_buffer(64)
        u.GetClassNameW(h, c, 64)
        if c.value != '#32770':
            continue
        if u.GetDlgItem(h, 9651):
            panel = h
            continue
        btns = []
        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def cc(x, l2):
            cc2 = ctypes.create_unicode_buffer(64)
            u.GetClassNameW(x, cc2, 64)
            if cc2.value == 'Button':
                btns.append(x)
            return True
        u.EnumChildWindows(h, cc, 0)
        if len(btns) > 50:
            crt = h
        elif len(btns) <= 3:
            others.append(h)
    return panel, view, crt, others


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


def vrect(view):
    r = wintypes.RECT()
    u.GetWindowRect(view, ctypes.byref(r))
    return (r.left, r.top, r.right, r.bottom)


def shot(view):
    return ImageGrab.grab(vrect(view))


def dpx(a, b):
    d = ImageChops.difference(a.convert('RGB'), b.convert('RGB'))
    return sum(d.convert('L').histogram()[10:])


def child_texts(hw):
    texts = []
    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cc(ch, l2):
        tt = stext(ch, 300)
        if tt:
            texts.append(tt)
        return True
    u.EnumChildWindows(hw, cc, 0)
    return texts


def dialogs(pid, skip):
    res = []
    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hw, lp):
        p = wintypes.DWORD()
        u.GetWindowThreadProcessId(hw, ctypes.byref(p))
        if p.value == pid and u.IsWindowVisible(hw) and hw not in skip:
            texts = child_texts(hw)
            if texts or stext(hw, 300):
                res.append((hw, stext(hw, 300), texts))
        return True
    u.EnumWindows(cb, 0)
    return res


def dismiss_all(pid, panel, skip):
    for _ in range(8):
        if u.IsWindowEnabled(panel):
            return True
        for hw, t, texts in dialogs(pid, skip):
            if not responsive(hw):
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
                sclick(btns[0])
            else:
                u.PostMessageW(hw, 0x0010, 0, 0)
        time.sleep(0.4)
    return u.IsWindowEnabled(panel) != 0


def main():
    main_h = find_main()
    pid = wintypes.DWORD()
    u.GetWindowThreadProcessId(main_h, ctypes.byref(pid))
    panel, view, crt, others = find_controls(main_h, pid.value)
    print('main', main_h, 'pid', pid.value, 'panel', panel, 'view', view, 'crt', crt, flush=True)
    assert panel and view, 'controls not found'
    skip = {panel, view, crt, main_h}
    cx, cy = knob_center(panel)
    print('knob center', cx, cy, flush=True)
    dismiss_all(pid.value, panel, skip)

    cyc = u.GetDlgItem(panel, 9518)
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    for i in range(1, n + 1):
        if not u.IsWindowEnabled(panel):
            dismiss_all(pid.value, panel, skip)
        detent(cx, cy, cw=True)
        time.sleep(0.5)
        dlgs = dialogs(pid.value, skip)
        prompt = None
        for hw, t, texts in dlgs:
            joined = ' | '.join(texts)
            if '模式' in joined or 'AUTO' in joined.upper():
                prompt = (hw, texts[:3])
        motions = []
        if u.IsWindowEnabled(panel) and responsive(cyc):
            sclick(cyc)
            prev = shot(view)
            for k in range(5):
                time.sleep(0.7)
                cur = shot(view)
                motions.append(dpx(prev, cur))
                prev = cur
        running = sum(1 for m in motions if m > 3000)
        if prompt:
            cls = 'REJECT_MODE'
        elif running >= 3:
            cls = 'AUTO_RUNNING'
        elif motions and max(motions) > 500:
            cls = 'SOME_MOTION'
        else:
            cls = 'NO_RESPONSE'
        rec = {'step': i, 'class': cls, 'prompt': prompt,
               'motions': motions, 'running_frames': running,
               'all_dialogs': [(h, tt[:2]) for h, tt, tx in dlgs]}
        with open(LOG, 'a', encoding='utf-8') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        print('detent', i, cls, 'prompt=', prompt, 'run_frames=', running, flush=True)
        dismiss_all(pid.value, panel, skip)
        time.sleep(0.5)

    for rec in ig.audit_tail(3):
        print('audit:', rec)


if __name__ == '__main__':
    main()
