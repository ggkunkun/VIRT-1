"""Specialized CAD/CAM/CNC GUI Bridge for Desktop Automation.

Automates common CAD operations (SolidWorks, AutoCAD, Siemens NX, SSCNC):
- New Part / New Assembly (`Ctrl+N` followed by dialog confirmation)
- Zoom to fit (`F` key in SW, `Z` `Enter` `E` `Enter` in AutoCAD)
- Save / Export STEP / DWG
- Dialog detection and automatic dismissal (Error alerts, Rebuild prompts)
"""

import sys
import os
import time
import argparse

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.1
except ImportError:
    pyautogui = None

try:
    import win32gui
    import win32con
except ImportError:
    win32gui = None
    win32con = None


def focus_software(name_query):
    """Bring target CAD software to foreground."""
    if not win32gui:
        return False

    target_hwnd = None
    def enum_cb(hwnd, _):
        nonlocal target_hwnd
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd).strip()
            if name_query.lower() in title.lower():
                target_hwnd = hwnd

    win32gui.EnumWindows(enum_cb, None)
    if target_hwnd:
        try:
            win32gui.ShowWindow(target_hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(target_hwnd)
            time.sleep(0.3)
            print(f"[CAD] Successfully focused {name_query} (HWND: {target_hwnd})")
            return True
        except Exception as e:
            print(f"[CAD] Failed to set foreground: {e}")
            return False
    print(f"[CAD] Software matching '{name_query}' not found.")
    return False


def new_part(software="solidworks"):
    """Trigger New Part dialog and confirm."""
    if not focus_software(software):
        return False

    if software.lower() in ["solidworks", "sw"]:
        pyautogui.hotkey("ctrl", "n")
        time.sleep(0.5)
        pyautogui.press("enter")
        print("[CAD] Triggered New Part in SOLIDWORKS.")
        return True
    elif software.lower() in ["autocad", "acad"]:
        pyautogui.hotkey("ctrl", "n")
        time.sleep(0.5)
        pyautogui.press("enter")
        print("[CAD] Triggered New Drawing in AutoCAD.")
        return True
    return False


def zoom_to_fit(software="solidworks"):
    """Fit all geometry to active viewport."""
    if not focus_software(software):
        return False

    if software.lower() in ["solidworks", "sw"]:
        pyautogui.press("f")
        print("[CAD] Pressed 'F' (Zoom to Fit) in SOLIDWORKS.")
        return True
    elif software.lower() in ["autocad", "acad"]:
        pyautogui.typewrite("z\n")
        time.sleep(0.1)
        pyautogui.typewrite("e\n")
        print("[CAD] Executed 'Z' -> 'E' (Zoom Extents) in AutoCAD.")
        return True
    return False


def export_file(software="solidworks", output_path="export.step"):
    """Trigger Save As and type export path."""
    if not focus_software(software):
        return False

    pyautogui.hotkey("ctrl", "s")
    time.sleep(0.5)
    pyautogui.typewrite(output_path, interval=0.02)
    time.sleep(0.2)
    pyautogui.press("enter")
    print(f"[CAD] Export command sent for: {output_path}")
    return True


def dismiss_dialogs():
    """Press ESC or Enter to dismiss modal alert boxes."""
    if pyautogui:
        pyautogui.press("escape")
        time.sleep(0.1)
        pyautogui.press("enter")
        print("[CAD] Sent ESC and ENTER to dismiss potential modal dialogs.")
        return True
    return False


def main():
    parser = argparse.ArgumentParser(description="CAD GUI Automation Bridge")
    subparsers = parser.add_subparsers(dest="command")

    p_focus = subparsers.add_parser("focus")
    p_focus.add_argument("--software", required=True)

    p_new = subparsers.add_parser("new-part")
    p_new.add_argument("--software", default="solidworks")

    p_zoom = subparsers.add_parser("zoom-fit")
    p_zoom.add_argument("--software", default="solidworks")

    p_exp = subparsers.add_parser("export")
    p_exp.add_argument("--software", default="solidworks")
    p_exp.add_argument("--path", required=True)

    p_dismiss = subparsers.add_parser("dismiss-dialogs")

    args = parser.parse_args()

    if args.command == "focus":
        focus_software(args.software)
    elif args.command == "new-part":
        new_part(args.software)
    elif args.command == "zoom-fit":
        zoom_to_fit(args.software)
    elif args.command == "export":
        export_file(args.software, args.path)
    elif args.command == "dismiss-dialogs":
        dismiss_dialogs()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
