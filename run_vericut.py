import subprocess, os

PROJ = r"D:\Virtu模型\runs\cad_cam_chain\20261030_144849\wheel_mold_vericut.vcproject"
bat = r"E:\windows64\commands\vericut.bat"
cwd = r"E:\windows64\commands"

env = os.environ.copy()
env["CGTECH_VCPROJECT"] = PROJ
env["CGTECH_IGNORE_LAST"] = "TRUE"

print("Launching Vericut BATCH with project:", PROJ, flush=True)
p = subprocess.Popen([bat, "BATCH"], env=env, cwd=cwd,
                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
try:
    out, err = p.communicate(timeout=180)
except subprocess.TimeoutExpired:
    p.kill()
    out, err = p.communicate()
    print("TIMEOUT (Vericut still running or hung)", flush=True)

print("EXIT CODE:", p.returncode)
print("==== STDOUT ====")
print(out[:3000])
print("==== STDERR ====")
print(err[:2000])
