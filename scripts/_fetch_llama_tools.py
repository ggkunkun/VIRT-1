#!/usr/bin/env python3
# 临时辅助：逐个拉取 llama.cpp 的 conversion/ 与 gguf-py/ 到本地（绕过 git/大文件传输限制）
import os, json, subprocess, time

REPO = "ggerganov/llama.cpp"
REF = "master"
BASE = r"D:/Virtu模型/scripts/llama_cpp_tools/llama.cpp"
API = f"https://api.github.com/repos/{REPO}/contents"
RAW = f"https://ghfast.top/https://raw.githubusercontent.com/{REPO}/{REF}"

os.makedirs(BASE, exist_ok=True)


def curl_bytes(url, timeout=120):
    for _ in range(3):
        try:
            r = subprocess.run(["curl", "-sSL", "-m", str(timeout), url],
                               capture_output=True)
            if r.returncode == 0 and r.stdout:
                return r.stdout
        except Exception:
            pass
        time.sleep(1)
    return b""


def list_dir(path):
    url = f"{API}/{path}?ref={REF}"
    try:
        items = json.loads(curl_bytes(url, timeout=90))
    except Exception as e:
        print("LIST_FAIL", path, e)
        return []
    files = []
    for it in items:
        if it.get("type") == "file":
            files.append(it["path"])
        elif it.get("type") == "dir":
            files += list_dir(it["path"])
    return files


print("enumerate conversion/ ...")
conv_files = list_dir("conversion")
print("enumerate gguf-py/ ...")
gguf_files = list_dir("gguf-py")
all_files = conv_files + gguf_files
print(f"total files to fetch: {len(all_files)}")

ok = fail = 0
for i, p in enumerate(all_files, 1):
    target = os.path.join(BASE, p)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    data = curl_bytes(f"{RAW}/{p}", timeout=120)
    if data:
        with open(target, "wb") as f:
            f.write(data)
        ok += 1
    else:
        print("FAIL", p)
        fail += 1
    if i % 40 == 0:
        print(f"  progress {i}/{len(all_files)} ok={ok} fail={fail}")

print(f"DONE ok={ok} fail={fail}")
print("conv_init", os.path.exists(os.path.join(BASE, "conversion", "__init__.py")))
print("gguf_init", os.path.exists(os.path.join(BASE, "gguf-py", "gguf", "__init__.py")))
print("conv_entries", len(os.listdir(os.path.join(BASE, "conversion"))) if os.path.isdir(os.path.join(BASE, "conversion")) else 0)
print("gguf_entries", len(os.listdir(os.path.join(BASE, "gguf-py", "gguf"))) if os.path.isdir(os.path.join(BASE, "gguf-py", "gguf")) else 0)
