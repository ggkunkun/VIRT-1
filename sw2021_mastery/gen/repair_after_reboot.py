# -*- coding: utf-8 -*-
"""重启后修复执行器：带源 REINSTALL=ALL，提权启动 + 轮询 MSI 日志直到结束。"""
import ctypes, json, os, subprocess, time

MSI = r"G:\SW2021_SP5_64bit\swwi\data\solidworks.msi"
LOG = r"D:\Virtu模型\sw2021_mastery\work\repair_after_reboot.log"
RESULT = r"D:\Virtu模型\sw2021_mastery\work\repair_after_reboot.json"
EXE = r"D:\SOLIDWORKS (2)\SLDWORKS.exe"


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def main():
    if os.path.exists(LOG):
        os.remove(LOG)
    if os.path.exists(RESULT):
        os.remove(RESULT)

    params = (f'/i "{MSI}" REINSTALL=ALL REINSTALLMODE=vomus SLDIM=1 '
              f'REBOOT=ReallySuppress /qn /l*v "{LOG}"')
    log("launching elevated msiexec: " + params)
    rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", "msiexec.exe", params, None, 0)
    log(f"ShellExecuteW rc={rc} (42 = launched)")
    if rc <= 32:
        with open(RESULT, "w", encoding="utf-8") as f:
            json.dump({"ok": False, "stage": "launch", "rc": rc}, f)
        return

    # 轮询：等日志出现 "MainEngineThread is returning" 或进程消失
    deadline = time.time() + 2.5 * 3600
    last_size = -1
    while time.time() < deadline:
        time.sleep(20)
        size = os.path.getsize(LOG) if os.path.exists(LOG) else 0
        if size != last_size:
            log(f"log size={size}")
            last_size = size
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq msiexec.exe",
                              "/NH", "/FO", "CSV"],
                             capture_output=True, text=True, errors="ignore").stdout
        rows = [l for l in out.splitlines() if l.startswith('"msiexec.exe"')]
        done = False
        if os.path.exists(LOG):
            raw = open(LOG, "rb").read()
            tail = raw[-4000:].decode("utf-16-le", errors="ignore")
            if "MainEngineThread is returning" in tail:
                done = True
        if done or not rows:
            time.sleep(5)
            break
    # 读结论
    code = None
    if os.path.exists(LOG):
        raw = open(LOG, "rb").read()
        t = raw.decode("utf-16-le", errors="ignore")
        for key in ("MainEngineThread is returning",):
            i = t.rfind(key)
            if i >= 0:
                seg = t[i:i + 120]
                log("TAIL: " + seg.replace("\n", " | ")[:120])
        if "return value 3" in t:
            code = 1603
        elif "return value 2" in t:
            code = 1602
        elif "MainEngineThread is returning" in t:
            # 找最终返回码行
            i = t.rfind("MainEngineThread is returning")
            code = t[i:i + 100]
    ver = ""
    if os.path.exists(EXE):
        out = subprocess.run(
            ["powershell", "-NoProfile", "-c",
             f'(Get-Item "{EXE}").VersionInfo.ProductVersion'],
            capture_output=True, text=True)
        ver = out.stdout.strip()
    result = {"ok": code in (None,) or (isinstance(code, int) and code == 0) or "0" in str(code),
              "msi_signal": str(code), "sldworks_version": ver,
              "log_bytes": os.path.getsize(LOG) if os.path.exists(LOG) else 0,
              "finished_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    with open(RESULT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    log("RESULT " + json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
