# -*- coding: utf-8 -*-
"""Hover every toolbar button; capture tooltip_class32 text -> command map."""
import os, sys, time, ctypes, json
os.environ['VIRTU_DESKTOP_INPUT'] = '1'
os.environ['VIRTU_DESKTOP_AGENT'] = 'tooltip-probe'
sys.path.insert(0, r'D:\Virtu模型')
from ctypes import wintypes
import virtu_omni.computer_use.input_guard as ig

u = ctypes.windll.user32
PID = 17464
OUT = r'D:\Virtu模型\ssnc_teaching\evidence\toolbar_tooltips.json'
TOOLBARS = [198174, 198188, 198162, 198168, 198186, 198190, 198192]
TB_BUTTONCOUNT = 0x0418
TB_GETITEMRECT = 0x0416   # TB_GETITEMRECT = WM_USER+22? verify: TB_GETITEMRECT=0x0416


def move(x, y):
    with ig.input_session('move', x=x, y=y, require_bounds=True) as ctx:
        if ctx['dry_run']:
            return False
        u.SetCursorPos(x, y)
        return True


def tooltips():
    res = []
    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hw, lp):
        p = wintypes.DWORD()
        u.GetWindowThreadProcessId(hw, ctypes.byref(p))
        c = ctypes.create_unicode_buffer(64)
        u.GetClassNameW(hw, c, 64)
        if p.value == PID and c.value == 'tooltips_class32' and u.IsWindowVisible(hw):
            # tooltip text lives in a static child or via TTM_GETTEXT
            texts = []
            @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            def cc(ch, l2):
                t = ctypes.create_unicode_buffer(500)
                u.GetWindowTextW(ch, t, 500)
                if t.value:
                    texts.append(t.value)
                return True
            u.EnumChildWindows(hw, cc, 0)
            if not texts:
                t = ctypes.create_unicode_buffer(500)
                u.GetWindowTextW(hw, t, 500)
                if t.value:
                    texts.append(t.value)
            res.append((hw, texts))
        return True
    u.EnumWindows(cb, 0)
    return res


def main():
    out = {}
    for tb in TOOLBARS:
        cnt = u.SendMessageW(tb, TB_BUTTONCOUNT, 0, 0)
        r = wintypes.RECT()
        u.GetWindowRect(tb, ctypes.byref(r))
        print('toolbar', tb, 'buttons', cnt, 'rect',
              (r.left, r.top, r.right, r.bottom))
        items = []
        for i in range(cnt):
            # TB_GETITEMRECT: wParam=index, lParam=RECT*
            rr = wintypes.RECT()
            u.SendMessageW(tb, TB_GETITEMRECT, i, ctypes.byref(rr))
            cx, cy = (rr.left + rr.right) // 2, (rr.top + rr.bottom) // 2
            # convert client->screen via toolbar origin
            sx, sy = r.left + cx, r.top + cy
            if sx <= 0 or sy <= 0 or sx > 3000 or sy > 3000:
                continue
            move(sx, sy)
            time.sleep(0.9)
            tips = tooltips()
            tip_text = ''
            for hw, texts in tips:
                for t in texts:
                    if t.strip():
                        tip_text = t
                        break
                if tip_text:
                    break
            items.append({'idx': i, 'screen': [sx, sy], 'tooltip': tip_text})
            print('  btn', i, 'tip', repr(tip_text[:60]))
        out[str(tb)] = items
    json.dump(out, open(OUT, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('wrote', OUT)


if __name__ == '__main__':
    main()
