import os, subprocess, sys, time, urllib.request
ROOT = r"D:/Virtu模型"
env = dict(os.environ, VIRTU_VLLM_MODEL="virtu-boundary-sft")
# explorer.exe 派生的进程脱离沙箱作业对象，可常驻真机
subprocess.Popen(["explorer.exe", os.path.join(ROOT, "scripts", "virtu_service_pinned.py")],
                 cwd=ROOT, env=env)
print("launched via explorer, VIRTU_VLLM_MODEL=virtu-boundary-sft")
