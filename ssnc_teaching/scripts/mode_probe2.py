# -*- coding: utf-8:
"""Per-detent probe: CW drag -> OCR mode text -> cycle-start -> modal? -> force-dismiss.
"""
import os, sys, time, ctypes, math, json
os.environ['VIRTU_DESKTOP_INPUT'] = '1'
os.environ['VIRTU_DESKTOP_AGENT'] = 'mode-probe2'
sys.path.insert(0, r'D:\Virtu模型')
from ctypes import wintypes
import virtu_omni.computer_use.input_guard as ig
from PIL import ImageGrab
from rapidocr_onnxruntime import RapidOCR

u = ctypes.windll.user32
MAIN, PANEL, PID = 199500, 198528, 17464
CX, CY = 1053, 713
LOG = r'D:\Virtu模型\ssnc_teaching\evidence\mode_probe2.jsonl'
_ocr = None


def ocr():
    global _ocr
    if _ocr is None:
        _ocr = RapidOCR()
    return _ocr


def stext(h, n=300):
    buf = ctypes.create_unicode_buffer(n)
    res = ctypes.c_size_t(0)
    ok = u.SendMessageTimeoutW(h, 0x000D, n, ctypes.cast(buf, ctypes.c_void_p),
                             0x0002, 800, ctypes.byref(res))
    return buf.value if ok else ''


def sclick(h, ms=2000):
    res = ctypes.c_size_t(0)
    return u.SendMessageTimeoutW(h, 0x00F5, 0, 0, 0x0002, ms, ctypes.byref(res))


def read_mode():
    r = wintypes.RECT()
    u.GetWindowRect(MAIN, ctypes.byref(r))
    im = ImageGrab.grab((r.left + 1120, r.top + 405, r.left + 1260, r.top + 480))
    p = r'D:\Virtu模型\ssnc_teaching\evidence\_mp2.png'
    im.save(p)
    res, _ = ocr()(p)
    return [t for _, t, c in (res or [])]


def drag(cw=True):
    a0, a1 = (-90.0, 90.0) if cw else (90.0, -90.0)
    with ig.input_session('drag', x=CX, y=CY, require_bounds=True) as ctx:
        u.SetCursorPos(int(CX + 30 * math.cos(math.radians(a0))),
                       int(CY + 30 * math.sin(math.radians(a0))))
        time.sleep(0.05)
        u.mouse_event(2, 0, 0, 0, 0)
        try:
            for i in range(1, 25):
                a = math.radians(a0 + (a1 - a0) * i / 24)
                u.SetCursorPos(int(CX + 30 * math.cos(a)),
                               int(CY + 30 * math.sin(a)))
                time.sleep(0.04)
        finally:
            u.mouse_event(4, 0, 0, 0, 0)


def modal_texts():
    out = []
    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(h, l):
        p = wintypes.DWORD()
        u.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value == PID and u.IsWindowVisible(h) and h not in (MAIN, PANEL):
            tx = []
            @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            def cc(c, l2):
                t = stext(c)
                if t:
                    tx.append(t)
                return True
            u.EnumChildWindows(h, cc, 0)
            if tx:
                out.append((h, tx[:3]))
        return True
    u.EnumWindows(cb, 0)
    return out


def force_dismiss():
    """Click every button of every modal until panel enabled (max ~15s)."""
    for _ in range(30):
        if u.IsWindowEnabled(PANEL):
            return True
        for hw, tx in modal_texts():
            btns = []
            @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            def cc(c, l2):
                cl = ctypes.create_unicode_buffer(64)
                u.GetClassNameW(c, cl, 64)
                if cl.value == 'Button':
                    btns.append(c)
                return True
            u.EnumChildWindows(hw, cc, 0)
            if btns:
                sclick(btns[0])
        time.sleep(0.5)
    return u.IsWindowEnabled(PANEL) != 0


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    cw = not (len(sys.argv) > 2 and sys.argv[2] == 'ccw')
    force_dismiss()
    cyc = u.GetDlgItem(PANEL, 9518)
    for i in range(1, n + 1):
        mode_pre = read_mode()
        drag(cw)
        time.sleep(0.7)
        mode_post = read_mode()
        # cycle start
        if u.IsWindowEnabled(PANEL):
            sclick(cyc)
        time.sleep(0.9)
        mods = modal_texts()
        reject = any('模式' in ' '.join(tx) or 'AUTO' in ' '.join(tx)
                     for _, tx in mods)
        rec = {'detent': i, 'mode_pre': mode_pre, 'mode_post': mode_post,
               'modals': mods, 'reject': reject}
        with open(LOG, 'a', encoding='utf-8') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        print('detent', i, 'mode', mode_pre, '->', mode_post,
              'reject', reject, 'modals', mods, flush=True)
        force_dismiss()
        time.sleep(0.3)


if __name__ == '__main__':
    main()
