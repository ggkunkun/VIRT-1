# -*- coding: utf-8 -*-
"""提权重跑修复：缓存 MSI + amus，死源已用 junction 复活。"""
import ctypes, os, subprocess, sys, time

LOG = r'D:\Virtu模型\sw2021_mastery\work\repair_localcache2.log'
if os.path.exists(LOG):
    os.remove(LOG)

params = (
    r'/i C:\WINDOWS\Installer\f2659.msi '
    'REINSTALL=ALL REINSTALLMODE=amus '
    r'/l*v ' + LOG + ' /qn REBOOT=ReallySuppress'
)
rc = ctypes.windll.shell32.ShellExecuteW(None, 'runas', 'msiexec.exe', params, None, 0)
print('ShellExecute rc =', rc)

# 等待 msiexec 进程退出
deadline = time.time() + 60
while time.time() < deadline:
    out = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq msiexec.exe'],
                         capture_output=True, text=True).stdout
    if 'msiexec' not in out.lower():
        print('msiexec started-and-exited or not visible yet')
        break
    time.sleep(2)
time.sleep(8)
out = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq msiexec.exe'],
                     capture_output=True, text=True).stdout
print('after 8s, msiexec running?', 'msiexec' in out.lower())
print('log exists?', os.path.exists(LOG), os.path.getsize(LOG) if os.path.exists(LOG) else 0)
