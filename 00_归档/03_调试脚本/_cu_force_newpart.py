import ctypes, time

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

SW_HIDE = 0
SW_RESTORE = 9

_targets = []

def enum_windows_callback(hwnd, lparam):
    length = user32.GetWindowTextLengthW(hwnd)
    if length == 0:
        return True
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    title = buf.value
    if "SOLIDWORKS Premium 2021" in title and user32.IsWindowVisible(hwnd):
        _targets.append(hwnd)
    return True

EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_void_p)
user32.EnumWindows(EnumWindowsProc(enum_windows_callback), 0)
targets = _targets

if not targets:
    print("NO_SW_WINDOW")
    raise SystemExit(1)

sw_hwnd = targets[0]
print("SW_HWND", sw_hwnd)

def get_foreground_pid():
    fg = user32.GetForegroundWindow()
    pid = ctypes.c_uint32(0)
    user32.GetWindowThreadProcessId(fg, ctypes.byref(pid))
    return fg, pid.value

# Tight loop: try to make SW foreground, then send Ctrl+N the instant it sticks.
sent = False
for attempt in range(40):
    fg, fpid = get_foreground_pid()
    if fg == sw_hwnd:
        # SW is foreground -> send Ctrl+N via keybd_event (global, but targets foreground)
        # Ctrl down
        user32.keybd_event(0x11, 0, 0, 0)   # VK_CONTROL
        user32.keybd_event(0x4E, 0, 0, 0)   # VK_N
        user32.keybd_event(0x4E, 0, 0x0002, 0)  # keyup N
        user32.keybd_event(0x11, 0, 0x0002, 0)  # keyup CONTROL
        sent = True
        print("SENT_CTRL_N at attempt", attempt)
        break
    else:
        # attach thread input to foreground thread then force foreground
        cur_thread = kernel32.GetCurrentThreadId()
        fg_thread = user32.GetWindowThreadProcessId(fg, None)
        sw_thread = user32.GetWindowThreadProcessId(sw_hwnd, None)
        try:
            user32.AttachThreadInput(cur_thread, fg_thread, True)
            user32.AttachThreadInput(cur_thread, sw_thread, True)
        except Exception:
            pass
        user32.ShowWindow(sw_hwnd, SW_RESTORE)
        user32.SetForegroundWindow(sw_hwnd)
        user32.BringWindowToTop(sw_hwnd)
        try:
            user32.AttachThreadInput(cur_thread, fg_thread, False)
            user32.AttachThreadInput(cur_thread, sw_thread, False)
        except Exception:
            pass
        time.sleep(0.15)

print("SENT", sent)
time.sleep(5)
print("DONE")
