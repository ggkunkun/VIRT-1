"""Windows Native Industrial Desktop Automation Controller.

Provides high-speed screen capture, mouse clicks, drags, keyboard typing,
window discovery, and focus management using pywin32 and pyautogui.
"""

import sys
import os
import time
import argparse
import json

try:
    from PIL import ImageGrab
except ImportError:
    ImageGrab = None

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.05
except ImportError:
    pyautogui = None

try:
    import win32gui
    import win32con
    import win32process
except ImportError:
    win32gui = None
    win32con = None
    win32process = None


def capture_screen(output_path="screenshot.png", bbox=None, window_title=None):
    """Capture full screen, specific window, or bounding box."""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    if window_title and win32gui:
        hwnd = find_window_by_title(window_title)
        if hwnd:
            focus_window(hwnd)
            time.sleep(0.2)
            rect = win32gui.GetWindowRect(hwnd)
            bbox = (rect[0], rect[1], rect[2], rect[3])

    if ImageGrab:
        img = ImageGrab.grab(bbox=bbox, all_screens=True)
        img.save(output_path)
        print(f"[CAPTURE] Saved screenshot ({img.width}x{img.height}) to: {output_path}")
        return output_path
    elif pyautogui:
        img = pyautogui.screenshot(region=bbox)
        img.save(output_path)
        print(f"[CAPTURE] Saved screenshot ({img.width}x{img.height}) to: {output_path}")
        return output_path
    else:
        raise RuntimeError("Neither PIL.ImageGrab nor pyautogui is available for screen capture.")


def list_windows(filter_text=None):
    """Enumerate all visible top-level windows."""
    if not win32gui:
        print("[WARN] win32gui not available.")
        return []

    windows = []

    def enum_cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd).strip()
            if title:
                if not filter_text or filter_text.lower() in title.lower():
                    rect = win32gui.GetWindowRect(hwnd)
                    windows.append({
                        "hwnd": hwnd,
                        "title": title,
                        "bounds": {"left": rect[0], "top": rect[1], "right": rect[2], "bottom": rect[3]},
                        "width": rect[2] - rect[0],
                        "height": rect[3] - rect[1]
                    })

    win32gui.EnumWindows(enum_cb, None)
    return windows


def find_window_by_title(title_query):
    """Find the best matching window HWND by title."""
    wins = list_windows(title_query)
    if wins:
        return wins[0]["hwnd"]
    return None


def focus_window(hwnd):
    """Force bring window to foreground."""
    if not win32gui or not win32con:
        return False
    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        return True
    except Exception as e:
        print(f"[WARN] Failed to focus window {hwnd}: {e}")
        return False


def click_at(x, y, button="left", clicks=1):
    """Execute click at given screen coordinate."""
    if not pyautogui:
        raise RuntimeError("pyautogui is required for mouse execution.")
    pyautogui.click(x=x, y=y, button=button, clicks=clicks)
    print(f"[MOUSE] Clicked {button} ({clicks}x) at ({x}, {y})")


def drag_mouse(x1, y1, x2, y2, duration=0.5):
    """Drag mouse from (x1, y1) to (x2, y2)."""
    if not pyautogui:
        raise RuntimeError("pyautogui is required for mouse execution.")
    pyautogui.moveTo(x1, y1)
    pyautogui.dragTo(x2, y2, duration=duration, button="left")
    print(f"[MOUSE] Dragged from ({x1}, {y1}) to ({x2}, {y2})")


def type_text(text, interval=0.01):
    """Type alphanumeric string."""
    if not pyautogui:
        raise RuntimeError("pyautogui is required for keyboard execution.")
    pyautogui.write(text, interval=interval)
    print(f"[KEYBOARD] Typed: {text}")


def press_hotkey(*keys):
    """Press key combination, e.g. ['ctrl', 's']."""
    if not pyautogui:
        raise RuntimeError("pyautogui is required for keyboard execution.")
    pyautogui.hotkey(*keys)
    print(f"[KEYBOARD] Pressed hotkey: {keys}")


def main():
    parser = argparse.ArgumentParser(description="Windows Desktop Automation Controller")
    subparsers = parser.add_subparsers(dest="command")

    # capture
    p_cap = subparsers.add_parser("capture")
    p_cap.add_argument("--output", default="screenshot.png")
    p_cap.add_argument("--window", default=None)
    p_cap.add_argument("--region", default=None, help="x1,y1,x2,y2")

    # list-windows
    p_list = subparsers.add_parser("list-windows")
    p_list.add_argument("--filter", default=None)

    # focus
    p_focus = subparsers.add_parser("focus")
    p_focus.add_argument("--title", required=True)

    # click
    p_click = subparsers.add_parser("click")
    p_click.add_argument("--x", type=int, required=True)
    p_click.add_argument("--y", type=int, required=True)
    p_click.add_argument("--button", default="left")
    p_click.add_argument("--clicks", type=int, default=1)

    # drag
    p_drag = subparsers.add_parser("drag")
    p_drag.add_argument("--start", required=True, help="x1,y1")
    p_drag.add_argument("--end", required=True, help="x2,y2")

    # type
    p_type = subparsers.add_parser("type")
    p_type.add_argument("--text", required=True)

    # hotkey
    p_key = subparsers.add_parser("hotkey")
    p_key.add_argument("--keys", required=True, help="comma separated, e.g. ctrl,s")

    args = parser.parse_args()

    if args.command == "capture":
        bbox = None
        if args.region:
            bbox = tuple(map(int, args.region.split(",")))
        capture_screen(args.output, bbox=bbox, window_title=args.window)

    elif args.command == "list-windows":
        wins = list_windows(args.filter)
        print(json.dumps(wins, ensure_ascii=False, indent=2))

    elif args.command == "focus":
        hwnd = find_window_by_title(args.title)
        if hwnd:
            focus_window(hwnd)
            print(f"[FOCUS] Focused window HWND={hwnd} matching '{args.title}'")
        else:
            print(f"[NOT FOUND] No window matching '{args.title}'")

    elif args.command == "click":
        click_at(args.x, args.y, button=args.button, clicks=args.clicks)

    elif args.command == "drag":
        x1, y1 = map(int, args.start.split(","))
        x2, y2 = map(int, args.end.split(","))
        drag_mouse(x1, y1, x2, y2)

    elif args.command == "type":
        type_text(args.text)

    elif args.command == "hotkey":
        keys = [k.strip() for k in args.keys.split(",")]
        press_hotkey(*keys)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
