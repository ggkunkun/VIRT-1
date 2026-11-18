# -*- coding: utf-8 -*-
import subprocess, sys, os
os.chdir(r"D:\Virtu模型\deploy")
tags = [
    ("virtu-opt-8b", "Modelfile.virtu-opt-8b"),
    ("virtu-opt-8b-ties", "Modelfile.virtu-opt-8b-ties"),
    ("virtu-opt-8b-v3", "Modelfile.virtu-opt-8b-v3"),
    ("virtu-opt-13b", "Modelfile.virtu-opt-13b"),
    ("virtu-opt-moe14b", "Modelfile.virtu-opt-moe14b"),
    ("virtu-opt-13b-q4", "Modelfile.virtu-opt-13b-q4"),
]
for tag, mf in tags:
    r = subprocess.run(["ollama", "create", tag, "-f", mf],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    print("====", tag, "rc=", r.returncode)
    out = (r.stdout or "") + (r.stderr or "")
    print(out.strip()[-400:])
