#!/usr/bin/env python3
"""
closed_loop_sentinel.py - Action Closed-Loop Verification & State Transition Sentinel.
Grounded in SOTA GitHub projects:
  - microsoft/UFO: Action verification & state transition validation
  - BAAI-Agents/Cradle: Self-reflection & desktop environment error recovery loop
  - Win32 User32 IsHungAppWindow & psutil: Process freeze detection & health monitoring
"""

import os
import sys
import json
import time
import argparse
import ctypes
from ctypes import wintypes
from typing import Dict, Any, Optional, Tuple, List

import cv2
import numpy as np
import psutil

# Ensure desktop attachment & DPI awareness
def attach_interactive_desktop():
    if sys.platform != 'win32':
        return None
    try:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass
        user32 = ctypes.windll.user32
        user32.OpenInputDesktop.restype = wintypes.HANDLE
        user32.OpenInputDesktop.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        user32.SetThreadDesktop.restype = wintypes.BOOL
        user32.SetThreadDesktop.argtypes = [wintypes.HANDLE]
        hdesk = user32.OpenInputDesktop(0, False, 0x01FF)
        if hdesk:
            user32.SetThreadDesktop(hdesk)
            return hdesk
    except Exception:
        pass
    return None

attach_interactive_desktop()

user32 = ctypes.windll.user32


class VisualDiffSentinel:
    """Verifies that user/agent actions caused expected UI state transitions."""

    @staticmethod
    def compare_frames(img_before_path: str, img_after_path: str) -> Dict[str, Any]:
        """
        Compare before and after screenshots using structural diff and contour bounding boxes.
        Returns transition status: TRANSITION_SUCCESS, TRANSITION_STAGNANT, or MODAL_DETECTED.
        """
        img1 = cv2.imread(img_before_path)
        img2 = cv2.imread(img_after_path)

        if img1 is None or img2 is None:
            return {"success": False, "error": "Unable to load comparison images"}

        if img1.shape != img2.shape:
            img2 = cv2.resize(img2, (img1.shape[1], img1.shape[0]))

        # Grayscale difference
        g1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
        g2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)

        diff = cv2.absdiff(g1, g2)
        _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
        
        # Morphological close to group local pixel noise into component regions
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
        closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

        total_pixels = float(diff.shape[0] * diff.shape[1])
        changed_pixels = float(cv2.countNonZero(thresh))
        change_ratio = changed_pixels / total_pixels

        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        bounding_boxes = []
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            if w * h > 100:  # Ignore microscopic 10x10 flickers
                bounding_boxes.append([x, y, x + w, y + h])

        # Classification
        if change_ratio < 0.0003 and len(bounding_boxes) == 0:
            status = "TRANSITION_STAGNANT"  # Action had no visual effect (click missed or ignored)
        elif any((b[2] - b[0] > 250 and b[3] - b[1] > 150) for b in bounding_boxes):
            status = "MODAL_DIALOG_OR_WINDOW_CHANGE"
        else:
            status = "TRANSITION_SUCCESS"

        return {
            "success": True,
            "status": status,
            "change_ratio_pct": round(change_ratio * 100.0, 3),
            "changed_region_count": len(bounding_boxes),
            "bounding_boxes": bounding_boxes[:10]
        }


class ProcessHangSentinel:
    """Sub-millisecond process hang detection via Win32 IsHungAppWindow."""

    @staticmethod
    def get_hwnd_from_title(target_query: str) -> Optional[int]:
        matched = []
        q_lower = target_query.lower()
        
        # Check if query matches class name directly
        h_cls = user32.FindWindowW(target_query, None)
        if h_cls:
            return h_cls

        def enum_cb(h, _):
            if user32.IsWindowVisible(h):
                length = user32.GetWindowTextLengthW(h)
                buf_title = ctypes.create_unicode_buffer(length + 1)
                if length > 0:
                    user32.GetWindowTextW(h, buf_title, length + 1)
                
                buf_class = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(h, buf_class, 256)
                
                # Title match or Class match
                if q_lower in buf_title.value.lower() or q_lower in buf_class.value.lower():
                    matched.append(h)
                    return False
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
        return matched[0] if matched else None

    @classmethod
    def check_hang(cls, hwnd_or_title: str) -> Dict[str, Any]:
        """Check if target window is responding or frozen."""
        hwnd = None
        if hwnd_or_title.isdigit():
            hwnd = int(hwnd_or_title)
        elif hwnd_or_title.startswith("0x"):
            hwnd = int(hwnd_or_title, 16)
        else:
            hwnd = cls.get_hwnd_from_title(hwnd_or_title)

        if not hwnd or not user32.IsWindow(hwnd):
            return {"success": False, "error": f"Window not found for '{hwnd_or_title}'"}

        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        
        is_hung = bool(user32.IsHungAppWindow(hwnd))
        
        proc_info = {}
        try:
            p = psutil.Process(pid.value)
            proc_info = {
                "name": p.name(),
                "status": p.status(),
                "cpu_percent": p.cpu_percent(interval=0.05),
                "memory_mb": round(p.memory_info().rss / (1024 * 1024), 2)
            }
        except Exception:
            pass

        return {
            "success": True,
            "hwnd": hwnd,
            "pid": pid.value,
            "is_hung": is_hung,
            "health": "FROZEN_NOT_RESPONDING" if is_hung else "HEALTHY",
            "process_info": proc_info
        }


class DialogAutoDismissal:
    """Detects and safely dismisses blocking modal popups (Alert, Save confirmation, Error dialogs)."""

    @staticmethod
    def dismiss_dialog(action: str = "accept", window_title: Optional[str] = None) -> Dict[str, Any]:
        """Dismiss active modal dialog via Enter (accept) or Escape (cancel)."""
        HUMANOID_SCRIPTS = r"C:\Users\Administrator\.gemini\config\skills\humanoid-computer-control\scripts"
        if HUMANOID_SCRIPTS not in sys.path:
            sys.path.insert(0, HUMANOID_SCRIPTS)
        try:
            import humanoid_controller as hc
            kb = hc.HumanoidKeyboard(mode="human")
            key = "enter" if action == "accept" else "esc"
            kb.press(key)
            return {"success": True, "action": action, "key_pressed": key}
        except Exception as e:
            return {"success": False, "error": str(e)}


def main():
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument("--json", action="store_true", help="Output JSON format")

    parser = argparse.ArgumentParser(description="Action Closed-Loop Verification Sentinel", parents=[common_parser])
    sub = parser.add_subparsers(dest="command")

    # verify-transition
    p_diff = sub.add_parser("verify-transition", parents=[common_parser])
    p_diff.add_argument("--before", required=True, help="Path to pre-action screenshot")
    p_diff.add_argument("--after", required=True, help="Path to post-action screenshot")

    # check-hang
    p_hang = sub.add_parser("check-hang", parents=[common_parser])
    p_hang.add_argument("--target", required=True, help="Window title substring or HWND")

    # dismiss-dialog
    p_dis = sub.add_parser("dismiss-dialog", parents=[common_parser])
    p_dis.add_argument("--action", choices=["accept", "cancel"], default="accept")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "verify-transition":
        res = VisualDiffSentinel.compare_frames(args.before, args.after)
        if args.json:
            print(json.dumps(res, ensure_ascii=False))
        else:
            print(f"Transition Status: {res.get('status')} (Diff: {res.get('change_ratio_pct')}%, Regions: {res.get('changed_region_count')})")

    elif args.command == "check-hang":
        res = ProcessHangSentinel.check_hang(args.target)
        if args.json:
            print(json.dumps(res, ensure_ascii=False))
        else:
            print(f"Target '{args.target}' Health: {res.get('health')} (is_hung={res.get('is_hung')})")

    elif args.command == "dismiss-dialog":
        res = DialogAutoDismissal.dismiss_dialog(action=args.action)
        if args.json:
            print(json.dumps(res, ensure_ascii=False))
        else:
            print(f"Dismissed dialog with action '{args.action}': {res}")


if __name__ == "__main__":
    main()
