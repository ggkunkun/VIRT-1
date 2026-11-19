# -*- coding: utf-8 -*-
import os, sys, time, ctypes, json
os.environ['VIRTU_DESKTOP_INPUT'] = '1'
os.environ['VIRTU_DESKTOP_AGENT'] = 'hunt2'
sys.path.insert(0, r'D:\Virtu模型')
from ctypes import wintypes
import virtu_omni.computer_use.input_guard as ig
from PIL import ImageGrab, ImageChops

u = ctypes.windll.user32
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
PID = 17464
PANEL = 198528
VIEW = 198292
KNOB = 9651
CYC = 9518
OUT = r'D:\Virtu模型\ssnc_teaching\evidence'


def click_raw(x, y):
    with ig.input_session('click', x=x, y=y, require_bounds=True) as ctx:
        if ctx['dry_run']:
            print('DRYRUN denied:', ctx.get('reason'))
            return False
        u.SetCursorPos(x, y)
        time.sleep(0.05)
        u.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.05)
        u.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        return True


def vrect():
    r = wintypes.RECT()
    u.GetWindowRect(VIEW, ctypes.byref(r))
    return (r.left, r.top, r.right, r.bottom)


def shot(name):
    im = ImageGrab.grab(vrect())
    im.save(os.path.join(OUT, name))
    return im


def delta(a, b):
    d = ImageChops.difference(a.convert('RGB'), b.convert('RGB'))
    return sum(d.convert('L').histogram()[10:])


def knob_pos():
    h = u.GetDlgItem(PANEL, KNOB)
    r = wintypes.RECT()
    u.GetWindowRect(h, ctypes.byref(r))
    return ((r.left + r.right) // 2, (r.top + r.bottom) // 2)


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
            res.append((hw, c.value, t.value, texts[:6]))
        return True
    u.EnumWindows(cb, 0)
    return res


def dismiss():
    for hw, c, t, texts in dialogs():
        if hw in (PANEL, 394740, 199500, VIEW):
            continue
        btns = []
        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def cc(ch, l2):
            cn = ctypes.create_unicode_buffer(64)
            u.GetClassNameW(ch, cn, 64)
            if cn.value == 'Button':
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
    print('knob pos', knob_pos())
    print('view rect', vrect())
    shot('v_base.png')
    for i in range(1, 9):
        x, y = knob_pos()
        ok = click_raw(x, y)
        print('step', i, 'knob click ok', ok, 'at', x, y)
        time.sleep(0.3)
        b = shot('v_b%d.png' % i)
        bm(CYC)
        time.sleep(1.0)
        a = shot('v_a%d.png' % i)
        d = delta(b, a)
        dl = [x for x in dialogs() if x[0] not in (PANEL, 394740, 199500, VIEW)]
        print('  motion_px', d, 'newdlgs', [(x[0], x[2], x[3][:2]) for x in dl])
        dismiss()
        if d > 8000:
            print('MOTION!')
            break
    shot('v_final.png')


if __name__ == '__main__':
    main()
