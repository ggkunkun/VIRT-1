# -*- coding: utf-8 -*-
import ctypes, time, urllib.request, sys
EXE = r"E:\OllamaApp\ollama.exe"
WD  = r"E:\OllamaApp"
op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
def alive():
    try:
        with op.open("http://127.0.0.1:11434/api/tags", timeout=2) as r:
            return r.status
    except Exception:
        return None
print("BEFORE", alive(), flush=True)
if alive() is None:
    rc = ctypes.windll.shell32.ShellExecuteW(None, "open", EXE, "serve", WD, 0)
    print("SHELLEXEC_RC", rc, flush=True)
    for i in range(60):
        s = alive()
        if s:
            print("READY", s, "after", i, "s", flush=True)
            break
        time.sleep(1)
    else:
        print("NOT_READY", flush=True)
        sys.exit(1)
else:
    print("ALREADY_RUNNING", flush=True)
with op.open("http://127.0.0.1:11434/api/tags", timeout=8) as r:
    import json
    d = json.loads(r.read().decode())
print("MODELS", len(d.get("models", [])), [m["name"] for m in d.get("models", [])][:8], flush=True)
