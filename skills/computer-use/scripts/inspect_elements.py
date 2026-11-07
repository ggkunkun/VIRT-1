#!/usr/bin/env python3
"""
inspect_elements.py - Inspect UI Automation accessibility tree and controls on Windows.
Dumps buttons, inputs, tabs, menus, and clickable elements with bounding rectangles and center click targets.
"""

import os
import sys
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import desktop_util
desktop_util.attach_default_desktop()

try:
    from pywinauto import Desktop
except ImportError:
    print(json.dumps({"success": False, "error": "pywinauto is not installed"}))
    sys.exit(1)

def find_target_window(query, d):
    """Find target window by HWND, process name, or title substring."""
    import ctypes
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    if not query:
        # Default to active foreground window
        hwnd = user32.GetForegroundWindow()
        if hwnd:
            for w in d.windows():
                if w.handle == hwnd:
                    return w
        return None

    hwnd_val = None
    if isinstance(query, int):
        hwnd_val = query
    elif isinstance(query, str):
        if query.startswith("0x") or query.isdigit():
            try:
                hwnd_val = int(query, 16) if query.startswith("0x") else int(query)
            except ValueError:
                pass

    q_lower = query.lower() if isinstance(query, str) else ""

    for w in d.windows():
        if hwnd_val and w.handle == hwnd_val:
            return w
        title = (w.window_text() or "").lower()
        if q_lower and q_lower in title:
            return w

        # Also check process name
        try:
            pid = ctypes.wintypes.DWORD()
            user32.GetWindowThreadProcessId(w.handle, ctypes.byref(pid))
            if pid.value:
                h_proc = kernel32.OpenProcess(0x1000, False, pid.value)
                if h_proc:
                    buf = ctypes.create_unicode_buffer(512)
                    size = ctypes.wintypes.DWORD(512)
                    if kernel32.QueryFullProcessImageNameW(h_proc, 0, buf, ctypes.byref(size)):
                        pname = os.path.basename(buf.value).lower()
                        if q_lower and q_lower in pname:
                            kernel32.CloseHandle(h_proc)
                            return w
                    kernel32.CloseHandle(h_proc)
        except Exception:
            pass
    return None

def main():
    parser = argparse.ArgumentParser(description="Inspect window UI elements via UI Automation")
    parser.add_argument("--window", "-w", help="Window title substring or HWND (e.g. 0x1234, default: foreground window)")
    parser.add_argument("--depth", "-d", type=int, default=3, help="Max recursion depth (default: 3)")
    parser.add_argument("--types", "-t", help="Comma-separated control types to filter (e.g. 'Button,Edit,MenuItem')")
    parser.add_argument("--json", "-j", action="store_true", help="Output JSON result")
    args = parser.parse_args()

    desktop_util.attach_default_desktop()
    d = Desktop(backend="uia")
    win = find_target_window(args.window, d)

    if not win:
        err = f"Window matching '{args.window or 'foreground'}' not found"
        if args.json:
            print(json.dumps({"success": False, "error": err}))
        else:
            print(f"Error: {err}", file=sys.stderr)
        sys.exit(1)

    type_filter = None
    if args.types:
        type_filter = set(t.strip().lower() for t in args.types.split(","))

    elements = []
    win_title = win.window_text() or "Untitled"
    win_hwnd = hex(win.handle)

    def walk_descendants(ctrl, current_depth):
        if current_depth > args.depth:
            return

        try:
            children = ctrl.children()
        except Exception:
            return

        for idx, child in enumerate(children):
            try:
                info = child.element_info
                ctype = info.control_type or "Unknown"
                name = (info.name or "").strip()
                rect = info.rectangle

                if rect is None:
                    continue

                w = max(0, rect.right - rect.left)
                h = max(0, rect.bottom - rect.top)

                # Skip completely hidden/empty elements
                if w <= 0 or h <= 0:
                    continue

                # Filter by control type if requested
                if type_filter and ctype.lower() not in type_filter:
                    walk_descendants(child, current_depth + 1)
                    continue

                center_x = rect.left + w // 2
                center_y = rect.top + h // 2

                elem_data = {
                    "index": len(elements) + 1,
                    "type": ctype,
                    "name": name,
                    "auto_id": info.automation_id or "",
                    "class_name": info.class_name or "",
                    "bounds": [rect.left, rect.top, w, h],
                    "center": [center_x, center_y],
                    "handle": hex(info.handle) if info.handle else None
                }
                elements.append(elem_data)

                walk_descendants(child, current_depth + 1)
            except Exception:
                continue

    walk_descendants(win, 1)

    result = {
        "success": True,
        "window": {
            "title": win_title,
            "hwnd": win_hwnd
        },
        "count": len(elements),
        "elements": elements
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Window: [{win_hwnd}] {win_title}")
        print(f"Found {len(elements)} elements (depth <= {args.depth}):\n")
        print(f"{'#':<4} {'TYPE':<15} {'CENTER':<14} {'BOUNDS':<18} {'NAME / AUTO_ID'}")
        print("-" * 80)
        for e in elements[:100]: # display top 100
            c_str = f"({e['center'][0]},{e['center'][1]})"
            b_str = f"{e['bounds'][0]},{e['bounds'][1]} {e['bounds'][2]}x{e['bounds'][3]}"
            desc = e['name'] or e['auto_id'] or ""
            desc = desc[:30] + ("..." if len(desc) > 30 else "")
            print(f"#{e['index']:<3} {e['type']:<15} {c_str:<14} {b_str:<18} {desc}")
        if len(elements) > 100:
            print(f"... and {len(elements) - 100} more elements (use --json for full output)")

if __name__ == "__main__":
    main()
