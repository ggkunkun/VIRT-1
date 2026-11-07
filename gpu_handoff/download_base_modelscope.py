#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
download_base_modelscope.py — 从 ModelScope 下载 Qwen3-8B 基座到本地缓存。

为什么用这个脚本而不是 modelscope SDK:
  - 本机无 modelscope/torch，且 SDK 会拉一堆依赖；这里只用 urllib + curl，零依赖。
  - 支持断点续传、失败重试、大小校验；16GB 下载中断可原地续。

基座选择: Qwen3-8B（非 Instruct）。
  依据: 6 个 LoRA 的 adapter_config.json 全部写
  base_model_name_or_path=/root/public-storage/model/Qwen/Qwen3-8B，
  tool_agent 回执亦写 base_model=/root/public-storage/model/Qwen/Qwen3-8B。
  合并必须用训练时的同一基座，否则 delta 语义偏移。chat_template 由
  merge_numpy.py 从 Qwen3-8B-Instruct 的 tokenizer_config.json 补写。

用法:
  python scripts/download_base_modelscope.py [目标目录]
  默认目标: checkpoints/_base_qwen3_8b
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

MODEL = "Qwen/Qwen3-8B"
API = f"https://www.modelscope.cn/api/v1/models/{MODEL}/repo/files?Revision=master"
RESOLVE = f"https://www.modelscope.cn/models/{MODEL}/resolve/master/"
UA = "Mozilla/5.0"
KEEP_SUFFIX = (".safetensors", ".json", ".txt")


def list_files() -> dict[str, int]:
    req = urllib.request.Request(API, headers={"User-Agent": UA})
    last = None
    for _ in range(6):
        try:
            d = json.load(urllib.request.urlopen(req, timeout=60))
            return {f["Name"]: int(f["Size"]) for f in d["Data"]["Files"]}
        except Exception as exc:  # noqa: BLE001
            last = exc
            print("[api] 重试:", exc, flush=True)
            time.sleep(3)
    raise SystemExit(f"[FATAL] 无法获取文件清单: {last}")


def fetch(name: str, size: int, dest: Path) -> bool:
    if dest.exists() and dest.stat().st_size == size:
        print(f"  [skip] {name} 已完整 ({size:,})", flush=True)
        return True
    url = RESOLVE + name
    curl = shutil.which("curl")
    if not curl:
        raise SystemExit("[FATAL] 找不到 curl，请安装 curl 或改用 modelscope SDK")
    dest.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, 8):
        have = dest.stat().st_size if dest.exists() else 0
        if have > size:  # 损坏，删了重下
            dest.unlink()
            have = 0
        cmd = [curl, "-L", "--fail", "--retry", "3", "--retry-delay", "3",
               "--connect-timeout", "30", "-o", str(dest)]
        if 0 < have < size:
            cmd += ["-C", "-"]
        cmd += [url]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if dest.exists() and dest.stat().st_size == size:
            print(f"  [ok] {name} ({size:,})", flush=True)
            return True
        got = dest.stat().st_size if dest.exists() else 0
        print(f"  [retry {attempt}/7] {name}: {got:,}/{size:,} rc={r.returncode} "
              f"{r.stderr.strip()[-180:]}", flush=True)
        if r.returncode != 0 and have > 0 and got == have:
            # 续传卡住（Range 不被支持 / 签名过期）→ 删掉整片重下
            dest.unlink()
        time.sleep(2)
    return False


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else root / "checkpoints" / "_base_qwen3_8b"
    out.mkdir(parents=True, exist_ok=True)
    files = list_files()
    need = {k: v for k, v in files.items() if k.endswith(KEEP_SUFFIX)}
    total = sum(need.values())
    print(f"[download] {MODEL} -> {out}", flush=True)
    print(f"[download] {len(need)} 个文件 共 {total/1e9:.3f} GB", flush=True)
    t0 = time.time()
    for name in sorted(need):
        if not fetch(name, need[name], out / name):
            raise SystemExit(f"[FATAL] 下载失败: {name}")
    print(f"[download] 全部完成 耗时 {time.time()-t0:.0f}s -> {out}", flush=True)


if __name__ == "__main__":
    main()
