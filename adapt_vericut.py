import shutil, os, win32com.client

SAMPLE = r"E:\samples\All\force_turning_generic_2_axis_lathe_turret_fan15t_mm.vcproject"
OUT = r"D:\Virtu模型\runs\cad_cam_chain\20261030_144849"
OUR_NC = r"D:\Virtu模型\runs\cad_cam_chain\20261030_144849\04_CIMCO_Edit_2026.nc"
PROJ = os.path.join(OUT, "wheel_mold_vericut.vcproject")

# 1. copy sample
if os.path.exists(PROJ):
    os.chmod(PROJ, 0o666)
    os.remove(PROJ)
shutil.copy2(SAMPLE, PROJ)
os.chmod(PROJ, 0o666)
txt = open(PROJ, encoding="utf-8", errors="ignore").read()
# 2. point NC references to our program (absolute, forward slashes)
old = "force_turning_fanuc_sample.nc"
n = txt.count(old)
txt = txt.replace(old, OUR_NC.replace("\\", "/"))
open(PROJ, "w", encoding="utf-8").write(txt)
print("Replaced %d NC references -> %s" % (n, OUR_NC))

# 3. test Vericut Automation COM
try:
    v = win32com.client.Dispatch("Vericut.Application")
    print("Vericut COM OK, version:", getattr(v, "Version", "?"), getattr(v, "VersionNumber", "?"))
    # try open project
    try:
        v.OpenProject(PROJ)
        print("OpenProject called")
    except Exception as e:
        print("OpenProject err:", e)
    # list projects
    try:
        print("ProjectCount:", v.ProjectCount)
    except Exception as e:
        print("ProjectCount err:", e)
except Exception as e:
    print("Vericut COM NOT available:", e)
