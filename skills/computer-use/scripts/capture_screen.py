#!/usr/bin/env python3
"""
capture_screen.py - High-precision screen capture tool for Computer Use.
Supports full-screen capture, window cropping, region cropping, and coordinate grids.
"""

import os
import sys
import json
import argparse
from datetime import datetime

# Import desktop utility from same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import desktop_util
desktop_util.attach_default_desktop()

try:
    from PIL import Image, ImageGrab, ImageDraw, ImageFont
except ImportError:
    print(json.dumps({"success": False, "error": "Pillow is not installed. Run: pip install Pillow"}))
    sys.exit(1)

def get_window_rect(window_query):
    """Find window by title substring or hwnd, returning (hwnd, (left, top, right, bottom))."""
    import ctypes
    user32 = ctypes.windll.user32

    target_hwnd = None
    if isinstance(window_query, int) or (isinstance(window_query, str) and window_query.startswith("0x")):
        hwnd_val = int(window_query, 16) if isinstance(window_query, str) else window_query
        if user32.IsWindow(hwnd_val):
            target_hwnd = hwnd_val
    else:
        q_lower = window_query.lower()
        found = []
        def enum_cb(h, _):
            if user32.IsWindowVisible(h):
                length = user32.GetWindowTextLengthW(h)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(h, buf, length + 1)
                    if q_lower in buf.value.lower():
                        found.append(h)
            return True
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
        if found:
            target_hwnd = found[0]

    if not target_hwnd:
        return None, None

    rect = ctypes.wintypes.RECT()
    user32.GetWindowRect(target_hwnd, ctypes.byref(rect))
    return target_hwnd, (rect.left, rect.top, rect.right, rect.bottom)

def draw_grid(img, step=100):
    """Draw coordinate grid on image to assist multimodal models."""
    draw = ImageDraw.Draw(img)
    w, h = img.size
    grid_color = (200, 50, 50, 128)
    text_color = (255, 0, 0, 255)

    for x in range(0, w, step):
        draw.line([(x, 0), (x, h)], fill=grid_color, width=1)
        draw.text((x + 2, 2), str(x), fill=text_color)
    for y in range(0, h, step):
        draw.line([(0, y), (w, y)], fill=grid_color, width=1)
        draw.text((2, y + 2), str(y), fill=text_color)
    return img

def main():
    parser = argparse.ArgumentParser(description="Capture screen or window")
    parser.add_argument("--output", "-o", help="Target image path (.png)")
    parser.add_argument("--window", "-w", help="Window title substring or HWND (e.g. 0x1234)")
    parser.add_argument("--region", "-r", help="Region as x,y,w,h")
    parser.add_argument("--grid", "-g", action="store_true", help="Overlay coordinate grid")
    parser.add_argument("--json", "-j", action="store_true", help="Output JSON result")
    args = parser.parse_args()

    # Re-attach desktop right before capture
    desktop_util.attach_default_desktop()

    bbox = None
    matched_hwnd = None

    if args.window:
        matched_hwnd, win_rect = get_window_rect(args.window)
        if not win_rect:
            err = f"Window matching '{args.window}' not found"
            if args.json:
                print(json.dumps({"success": False, "error": err}))
            else:
                print(f"Error: {err}", file=sys.stderr)
            sys.exit(1)
        bbox = win_rect
    elif args.region:
        try:
            rx, ry, rw, rh = [int(v.strip()) for v in args.region.split(",")]
            bbox = (rx, ry, rx + rw, ry + rh)
        except Exception as e:
            err = f"Invalid region format '{args.region}', expected x,y,w,h: {e}"
            if args.json:
                print(json.dumps({"success": False, "error": err}))
            else:
                print(f"Error: {err}", file=sys.stderr)
            sys.exit(1)

    try:
        if bbox:
            img = ImageGrab.grab(bbox=bbox)
        else:
            img = ImageGrab.grab()
    except Exception as e:
        err = f"Screenshot capture failed: {e}"
        if args.json:
            print(json.dumps({"success": False, "error": err}))
        else:
            print(f"Error: {err}", file=sys.stderr)
        sys.exit(1)

    if args.grid:
        img = draw_grid(img)

    output_path = args.output
    if not output_path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.abspath(f"screenshot_{ts}.png")
    else:
        output_path = os.path.abspath(output_path)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    img.save(output_path)

    result = {
        "success": True,
        "path": output_path,
        "width": img.width,
        "height": img.height,
        "bbox": bbox if bbox else [0, 0, img.width, img.height],
        "hwnd": hex(matched_hwnd) if matched_hwnd else None
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(f"Screenshot saved to: {output_path} ({img.width}x{img.height})")

if __name__ == "__main__":
    main()
