import os, subprocess, time, sys

NXBASE = r"E:\BaiduNetdiskDownload\NX 12.0.2.9\NX12.2.9waigua\NX12.2.9\NX"
UGII_ROOT = os.path.join(NXBASE, "ugii")
OUT = r"D:\Virtu模型\runs\cad_cam_chain\20261030_144849"
journal = os.path.join(OUT, "02_NX_fixed.py")
res = os.path.join(OUT, "nx_result.txt")
ugraf = os.path.join(NXBASE, "NXBIN", "ugraf.exe")

if os.path.exists(res):
    os.remove(res)

env = os.environ.copy()
env["UGII_BASE_DIR"] = NXBASE
env["UGII_ROOT_DIR"] = UGII_ROOT
env["UGII_LIBRARY_DIR"] = UGII_ROOT
env["UGII_UGRAF_DIR"] = os.path.join(NXBASE, "ugraf")
env["UGII_LANG"] = "simpl_chinese"
env["UGII_COUNTRY"] = "prc"
env["PATH"] = UGII_ROOT + ";" + env["PATH"]

print("Launching ugraf -journal ...", flush=True)
p = subprocess.Popen([ugraf, "-journal", journal], env=env, cwd=UGII_ROOT)

# poll for result file (NX stays open after journal; we only need the part saved)
for i in range(200):
    if os.path.exists(res):
        print("RESULT FILE APPEARED after ~%ds" % (i*1), flush=True)
        break
    time.sleep(1)
else:
    print("TIMEOUT: result file not written in 200s", flush=True)

if os.path.exists(res):
    print("----- nx_result.txt -----")
    print(open(res, encoding="utf-8", errors="ignore").read())
else:
    print("no result file; NX may have failed to start (check license/env)")

# leave NX running; report process state
print("ugraf returncode so far:", p.poll())
