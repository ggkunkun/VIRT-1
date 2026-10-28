import os
import subprocess

print("Checking WorkBuddy shortcut and directories...")

lnk_path = r"C:\Users\Administrator\Desktop\WorkBuddy.lnk"
cmd = f'(New-Object -ComObject WScript.Shell).CreateShortcut("{lnk_path}").TargetPath'
res = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True)
target = res.stdout.strip()
print(f"Shortcut Target: {target}")

for path in [target, r"D:\WorkBuddy", r"D:\WorkBuddyData", r"D:\.workbuddy", r"C:\Users\Administrator\.workbuddy"]:
    if os.path.exists(path):
        print(f"\n=== Found Path: {path} ===")
        if os.path.isdir(path):
            try:
                items = os.listdir(path)
                print(f"  Contents ({len(items)} items): {items[:25]}")
            except Exception as e:
                print(f"  Error reading dir: {e}")
        else:
            print(f"  File size: {os.path.getsize(path)} bytes")
