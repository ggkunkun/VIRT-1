# Windows Desktop Automation Guide

This guide details the architectural requirements and solutions for reliable desktop automation on Windows within AI agent environments.

---

## 1. Thread Desktop Attachment (`WinSta0\default`)

In many automated, sandbox, or subshell environments (such as Antigravity or Task Scheduler), child processes and threads may be started on an isolated thread desktop (e.g. `exebox-...` or `Winlogon`).

### The Symptom
- Standard `ImageGrab.grab()` fails with `OSError: screen grab failed`.
- `GetForegroundWindow()` returns `0` / `NULL`.
- Mouse clicks land on the wrong virtual surface or are discarded.

### The Solution (`desktop_util.py`)
Attach the calling thread to the interactive `'default'` desktop **before** initializing GUI or COM libraries:

```python
import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32
user32.OpenDesktopW.restype = wintypes.HANDLE
user32.OpenDesktopW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
user32.SetThreadDesktop.restype = wintypes.BOOL
user32.SetThreadDesktop.argtypes = [wintypes.HANDLE]

DESKTOP_ALL_ACCESS = 0x01FF
hdesk = user32.OpenDesktopW("default", 0, False, DESKTOP_ALL_ACCESS)
if hdesk:
    user32.SetThreadDesktop(hdesk)
```

> **CRITICAL RULE**: `SetThreadDesktop` **must** be called **before** any window, message loop, or `pywinauto`/COM hook is created on that thread. Calling it after `import pywinauto` will fail with `ERROR_BUSY`.

---

## 2. DPI Awareness and Coordinate Scaling

Modern Windows displays often use 125%, 150%, or 200% scaling. If an agent does not declare DPI awareness:
- The OS virtualizes screen coordinates (e.g., reporting 1280x720 instead of 1920x1080).
- Pixel clicks calculated from screenshots will land off-target.

### The Solution
Enable Per-Monitor DPI Awareness v2 before querying screen metrics:

```python
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2) # PROCESS_PER_MONITOR_DPI_AWARE
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass
```

All bundled scripts in `scripts/` automatically execute this through `desktop_util.attach_default_desktop()`.

---

## 3. Bypassing Windows Focus-Stealing Restrictions

Windows restricts background processes from calling `SetForegroundWindow()` directly to prevent disruptive popups.

### The Solution (`input_action.py focus`)
Use `AttachThreadInput` to temporarily link input queues between the current thread and the target window's thread:

```python
current_thread = ctypes.windll.kernel32.GetCurrentThreadId()
target_thread = user32.GetWindowThreadProcessId(hwnd, None)

user32.AttachThreadInput(current_thread, target_thread, True)
user32.SetForegroundWindow(hwnd)
user32.BringWindowToTop(hwnd)
user32.SetFocus(hwnd)
user32.AttachThreadInput(current_thread, target_thread, False)
```

---

## 4. UI Automation (UIA) vs Pixel Coordinates

Whenever possible, prefer inspecting and referencing UI elements by their control hierarchy (`inspect_elements.py`) instead of pure pixel estimation:
1. Run `python scripts/inspect_elements.py --window <name>` to get element bounds and center coordinates.
2. Click directly on the verified `center: [x, y]`.
3. If an element is dynamic or unexposed, fall back to vision models with `capture_screen.py --grid`.
