import ctypes, time
from ctypes import wintypes
u = ctypes.windll.user32
u.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
hw = []
EP = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_void_p)
def cb(h, l):
    n = u.GetWindowTextLengthW(h)
    if n:
        b = ctypes.create_unicode_buffer(n+1)
        u.GetWindowTextW(h, b, n+1)
        if 'jilunmo' in b.value.lower() and u.IsWindowVisible(h):
            hw.append(h)
    return True
u.EnumWindows(EP(cb), 0)
print('HWND', hw)
if hw:
    t = hw[0]
    if u.IsZoomed(t):
        u.ShowWindow(t, 9)   # SW_RESTORE
        time.sleep(0.6)
    u.SetWindowPos(t, 0, 0, 0, 1230, 692, 0x0040)   # SWP_SHOWWINDOW
    u.SetForegroundWindow(t)
    r = wintypes.RECT()
    u.GetWindowRect(t, ctypes.byref(r))
    print('RECT', r.left, r.top, r.right, r.bottom, 'size', r.right-r.left, r.bottom-r.top)
time.sleep(1.5)
