#!/usr/bin/env python3
"""
input_action.py - Execute mouse, keyboard, and window focus actions for Computer Use.
Supports click, move, drag, scroll, type, press, hotkey, and focus.
"""

import os
import sys
import time
import json
import argparse
import ctypes
from ctypes import wintypes

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import desktop_util
desktop_util.attach_default_desktop()

# Register workspace root for Virtu Computer Use engine
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

try:
    from virtu_omni.computer_use.action import ActionEngine
    _action_engine = ActionEngine()
except Exception:
    _action_engine = None

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.05
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False

user32 = ctypes.windll.user32

def force_foreground_window(hwnd):
    """Force bring a window to the foreground, bypassing Windows focus-stealing restrictions."""
    if not user32.IsWindow(hwnd):
        return False

    # Restore if minimized (SW_RESTORE = 9)
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)
    else:
        # Show normal (SW_SHOW = 5)
        user32.ShowWindow(hwnd, 5)

    current_thread = ctypes.windll.kernel32.GetCurrentThreadId()
    target_thread = user32.GetWindowThreadProcessId(hwnd, None)

    # Attach thread input to bypass focus lock
    user32.AttachThreadInput(current_thread, target_thread, True)
    user32.SetForegroundWindow(hwnd)
    user32.BringWindowToTop(hwnd)
    user32.SetFocus(hwnd)
    user32.AttachThreadInput(current_thread, target_thread, False)

    time.sleep(0.1)
    return True

def parse_coords(val):
    if not val:
        return None
    try:
        parts = [int(p.strip()) for p in val.split(",")]
        if len(parts) >= 2:
            return parts[0], parts[1]
    except Exception:
        pass
    return None

def main():
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument("--capture-after", help="Path to take and save a screenshot right after action")
    common_parser.add_argument("--json", "-j", action="store_true", help="Output JSON result")
    common_parser.add_argument("--normalized", "-n", action="store_true", help="Coordinates are normalized (0~1 or 0~1000) for screen adaptation")

    parser = argparse.ArgumentParser(description="Perform GUI input actions", parents=[common_parser])
    subparsers = parser.add_subparsers(dest="action", help="Action to execute")

    # click
    p_click = subparsers.add_parser("click", parents=[common_parser], help="Click at coordinates")
    p_click.add_argument("--coord", "-c", help="x,y coordinate")
    p_click.add_argument("--x", type=int, help="X coordinate")
    p_click.add_argument("--y", type=int, help="Y coordinate")
    p_click.add_argument("--button", default="left", choices=["left", "right", "middle"])
    p_click.add_argument("--clicks", type=int, default=1)

    # double_click
    p_dclick = subparsers.add_parser("double_click", parents=[common_parser], help="Double click at coordinates")
    p_dclick.add_argument("--coord", "-c", help="x,y coordinate")
    p_dclick.add_argument("--x", type=int, help="X coordinate")
    p_dclick.add_argument("--y", type=int, help="Y coordinate")

    # right_click
    p_rclick = subparsers.add_parser("right_click", parents=[common_parser], help="Right click at coordinates")
    p_rclick.add_argument("--coord", "-c", help="x,y coordinate")
    p_rclick.add_argument("--x", type=int, help="X coordinate")
    p_rclick.add_argument("--y", type=int, help="Y coordinate")

    # move
    p_move = subparsers.add_parser("move", parents=[common_parser], help="Move mouse to coordinates")
    p_move.add_argument("--coord", "-c", help="x,y coordinate")
    p_move.add_argument("--x", type=int, help="X coordinate")
    p_move.add_argument("--y", type=int, help="Y coordinate")
    p_move.add_argument("--duration", type=float, default=0.2)

    # drag
    p_drag = subparsers.add_parser("drag", parents=[common_parser], help="Drag mouse from coord to coord")
    p_drag.add_argument("--from-coord", help="start x,y coordinate")
    p_drag.add_argument("--to-coord", help="target x,y coordinate")
    p_drag.add_argument("--from-x", type=int)
    p_drag.add_argument("--from-y", type=int)
    p_drag.add_argument("--to-x", type=int)
    p_drag.add_argument("--to-y", type=int)
    p_drag.add_argument("--duration", type=float, default=0.5)

    # scroll
    p_scroll = subparsers.add_parser("scroll", parents=[common_parser], help="Scroll mouse wheel")
    p_scroll.add_argument("--amount", "-a", type=int, required=True, help="Clicks to scroll (+ for up, - for down)")
    p_scroll.add_argument("--coord", "-c", help="x,y coordinate to scroll over")
    p_scroll.add_argument("--x", type=int)
    p_scroll.add_argument("--y", type=int)

    # type
    p_type = subparsers.add_parser("type", parents=[common_parser], help="Type text via keyboard")
    p_type.add_argument("--text", "-t", required=True, help="Text to type")
    p_type.add_argument("--interval", type=float, default=0.02, help="Interval between characters")

    # press
    p_press = subparsers.add_parser("press", parents=[common_parser], help="Press a single key (e.g. enter, esc, tab)")
    p_press.add_argument("--key", "-k", required=True, help="Key name")
    p_press.add_argument("--presses", type=int, default=1)

    # hotkey
    p_hotkey = subparsers.add_parser("hotkey", parents=[common_parser], help="Press shortcut keys combination")
    p_hotkey.add_argument("--keys", "-k", required=True, help="Comma-separated keys, e.g. 'ctrl,c' or 'alt,f4'")

    # focus
    p_focus = subparsers.add_parser("focus", parents=[common_parser], help="Focus window by HWND or title")
    p_focus.add_argument("--hwnd", help="Window HWND hex or dec")
    p_focus.add_argument("--title", help="Window title substring")

    # launch
    p_launch = subparsers.add_parser("launch", parents=[common_parser], help="Launch application or .lnk shortcut")
    p_launch.add_argument("--target", "-t", required=True, help="Path to executable, .lnk shortcut, or app alias")

    args = parser.parse_args()

    if not args.action:
        parser.print_help()
        sys.exit(1)

    desktop_util.attach_default_desktop()

    result = {"success": True, "action": args.action}

    try:
        is_norm = getattr(args, "normalized", False)

        if args.action in ["click", "double_click", "right_click"]:
            x, y = None, None
            if args.coord:
                c = parse_coords(args.coord)
                if c:
                    x, y = c
            if x is None and args.x is not None:
                x = args.x
            if y is None and args.y is not None:
                y = args.y

            btn = getattr(args, "button", "left")
            clicks = getattr(args, "clicks", 1)
            if args.action == "double_click":
                clicks = 2
            elif args.action == "right_click":
                btn = "right"

            if _action_engine is not None:
                if x is not None and y is not None:
                    res = _action_engine.click(
                        x=x, y=y, button=btn, double=(clicks == 2), normalized=is_norm
                    )
                else:
                    class POINT(ctypes.Structure):
                        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
                    pt = POINT()
                    user32.GetCursorPos(ctypes.byref(pt))
                    res = _action_engine.click(
                        x=pt.x, y=pt.y, button=btn, double=(clicks == 2)
                    )
                result["details"] = res
            elif HAS_PYAUTOGUI:
                if x is not None and y is not None:
                    pyautogui.click(x=x, y=y, clicks=clicks, button=btn)
                    result["details"] = {"x": x, "y": y, "button": btn, "clicks": clicks}
                else:
                    pyautogui.click(clicks=clicks, button=btn)
                    pos = pyautogui.position()
                    result["details"] = {"x": pos.x, "y": pos.y, "button": btn, "clicks": clicks}
            else:
                raise RuntimeError("No input execution engine available (ActionEngine or PyAutoGUI)")

        elif args.action == "move":
            x, y = None, None
            if args.coord:
                c = parse_coords(args.coord)
                if c:
                    x, y = c
            if x is None and args.x is not None:
                x = args.x
            if y is None and args.y is not None:
                y = args.y

            if x is None or y is None:
                raise ValueError("Must provide coordinates via --coord or --x and --y")

            if _action_engine is not None:
                res = _action_engine.mouse_move(x=x, y=y, normalized=is_norm)
                result["details"] = res
            elif HAS_PYAUTOGUI:
                pyautogui.moveTo(x=x, y=y, duration=args.duration)
                result["details"] = {"x": x, "y": y, "duration": args.duration}
            else:
                raise RuntimeError("No input execution engine available")

        elif args.action == "drag":
            from_x, from_y = None, None
            to_x, to_y = None, None

            if args.from_coord:
                c = parse_coords(args.from_coord)
                if c: from_x, from_y = c
            if from_x is None: from_x = args.from_x
            if from_y is None: from_y = args.from_y

            if args.to_coord:
                c = parse_coords(args.to_coord)
                if c: to_x, to_y = c
            if to_x is None: to_x = args.to_x
            if to_y is None: to_y = args.to_y

            if None in [from_x, from_y, to_x, to_y]:
                raise ValueError("Must provide both start and end coordinates for drag")

            if _action_engine is not None:
                res = _action_engine.drag(
                    start_x=from_x, start_y=from_y, end_x=to_x, end_y=to_y, normalized=is_norm
                )
                result["details"] = res
            elif HAS_PYAUTOGUI:
                pyautogui.moveTo(from_x, from_y)
                pyautogui.dragTo(to_x, to_y, duration=args.duration)
                result["details"] = {"from": [from_x, from_y], "to": [to_x, to_y]}
            else:
                raise RuntimeError("No input execution engine available")

        elif args.action == "scroll":
            x, y = None, None
            if args.coord:
                c = parse_coords(args.coord)
                if c: x, y = c
            if x is None: x = args.x
            if y is None: y = args.y

            if _action_engine is not None:
                res = _action_engine.scroll(clicks=args.amount, x=x, y=y)
                result["details"] = res
            elif HAS_PYAUTOGUI:
                pyautogui.scroll(args.amount, x=x, y=y)
                result["details"] = {"amount": args.amount, "x": x, "y": y}
            else:
                raise RuntimeError("No input execution engine available")

        elif args.action == "type":
            if _action_engine is not None:
                res = _action_engine.type_text(args.text)
                result["details"] = res
            else:
                has_unicode = any(ord(char) > 127 for char in args.text)
                if has_unicode:
                    ctypes.windll.user32.OpenClipboard(0)
                    ctypes.windll.user32.EmptyClipboard()
                    text_bytes = (args.text + '\0').encode('utf-16le')
                    h_mem = ctypes.windll.kernel32.GlobalAlloc(0x0042, len(text_bytes))
                    ptr = ctypes.windll.kernel32.GlobalLock(h_mem)
                    ctypes.cdll.msvcrt.memcpy(ctypes.c_void_p(ptr), text_bytes, len(text_bytes))
                    ctypes.windll.kernel32.GlobalUnlock(h_mem)
                    CF_UNICODETEXT = 13
                    ctypes.windll.user32.SetClipboardData(CF_UNICODETEXT, h_mem)
                    ctypes.windll.user32.CloseClipboard()
                    time.sleep(0.05)
                    if HAS_PYAUTOGUI:
                        pyautogui.hotkey('ctrl', 'v')
                    result["details"] = {"text": args.text, "method": "clipboard_paste"}
                else:
                    if HAS_PYAUTOGUI:
                        pyautogui.typewrite(args.text, interval=args.interval)
                    result["details"] = {"text": args.text, "method": "typewrite"}

        elif args.action == "press":
            if _action_engine is not None:
                res = _action_engine.hotkey([args.key])
                result["details"] = res
            elif HAS_PYAUTOGUI:
                pyautogui.press(args.key, presses=args.presses)
                result["details"] = {"key": args.key, "presses": args.presses}
            else:
                raise RuntimeError("No input execution engine available")

        elif args.action == "hotkey":
            keys = [k.strip().lower() for k in args.keys.split(",")]
            if _action_engine is not None:
                res = _action_engine.hotkey(keys)
                result["details"] = res
            elif HAS_PYAUTOGUI:
                pyautogui.hotkey(*keys)
                result["details"] = {"keys": keys}
            else:
                raise RuntimeError("No input execution engine available")

        elif args.action == "focus":
            target_hwnd = None
            if args.hwnd:
                target_hwnd = int(args.hwnd, 16) if args.hwnd.startswith("0x") else int(args.hwnd)
            elif args.title:
                t_lower = args.title.lower()
                found = []
                def enum_cb(h, _):
                    if user32.IsWindowVisible(h):
                        length = user32.GetWindowTextLengthW(h)
                        if length > 0:
                            buf = ctypes.create_unicode_buffer(length + 1)
                            user32.GetWindowTextW(h, buf, length + 1)
                            if t_lower in buf.value.lower():
                                found.append(h)
                    return True
                WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
                user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
                if found:
                    target_hwnd = found[0]

            if not target_hwnd:
                raise ValueError("Target window not found")

            ok = force_foreground_window(target_hwnd)
            result["details"] = {"hwnd": hex(target_hwnd), "focused": ok}

        elif args.action == "launch":
            target = os.path.expandvars(os.path.expanduser(args.target))
            known_aliases = {
                "智能制造agent企业版": r"C:\Users\Administrator\Desktop\智能制造Agent企业版.lnk",
                "智能制造agent": r"C:\Users\Administrator\Desktop\智能制造Agent企业版.lnk",
                "smai": r"C:\Users\Administrator\Desktop\智能制造Agent企业版.lnk",
                "enterprise": r"C:\Users\Administrator\Desktop\智能制造Agent企业版.lnk"
            }
            if target.lower() in known_aliases:
                target = known_aliases[target.lower()]

            if os.path.exists(target):
                os.startfile(target)
                result["details"] = {"target": target, "status": "launched"}
            else:
                raise FileNotFoundError(f"Launch target not found: {target}")

        # Optional follow-up screenshot
        if args.capture_after:
            time.sleep(0.1)
            desktop_util.attach_default_desktop()
            from PIL import ImageGrab
            img = ImageGrab.grab()
            cap_path = os.path.abspath(args.capture_after)
            os.makedirs(os.path.dirname(cap_path) or ".", exist_ok=True)
            img.save(cap_path)
            result["capture"] = cap_path

    except Exception as e:
        result = {"success": False, "action": args.action, "error": str(e)}

    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        if result["success"]:
            print(f"Action '{args.action}' succeeded: {result.get('details', '')}")
            if "capture" in result:
                print(f"Follow-up capture saved to: {result['capture']}")
        else:
            print(f"Error: {result['error']}", file=sys.stderr)
            sys.exit(1)

if __name__ == "__main__":
    main()
