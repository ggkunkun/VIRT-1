#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
download_qwen.py — 自动下载 Qwen GGUF 权重（ModelScope 国内源，避免境外域名被墙）

默认下载 Qwen3-8B-Instruct 的 GGUF 量化版（与你的对话/CAD LoRA 基底同版本）。
优先用 modelscope SDK；若未安装则直连 ModelScope CDN 并带进度条。

用法:
  python download_qwen.py                       # 默认 Q4_K_M
  python download_qwen.py --quant q5_k_m        # 更高精度
  python download_qwen.py --out-dir D:/models   # 指定目录
  python download_qwen.py --file Qwen3-8B-Instruct-Q8_0.gguf

下载完直接用:
  python start_virtu_bridge.py --backend llamacpp --gguf <输出路径>
"""

import os
import sys
import argparse
import urllib.request
import shutil

GGUF_FILES = {
    "q4_k_m": "Qwen3-8B-Instruct-Q4_K_M.gguf",
    "q5_k_m": "Qwen3-8B-Instruct-Q5_K_M.gguf",
    "q8_0": "Qwen3-8B-Instruct-Q8_0.gguf",
    "f16": "Qwen3-8B-Instruct-F16.gguf",
}
DEFAULT_MODEL = "Qwen/Qwen3-8B-Instruct-GGUF"


def parse_args():
    p = argparse.ArgumentParser(description="下载 Qwen GGUF (ModelScope 国内源)")
    p.add_argument("--quant", default="q4_k_m", choices=list(GGUF_FILES), help="量化档")
    p.add_argument("--model", default=DEFAULT_MODEL, help="ModelScope 模型 id")
    p.add_argument("--out-dir", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "models"))
    p.add_argument("--file", default=None, help="显式指定 GGUF 文件名")
    return p.parse_args()


def download_modelscope(model_id, filename, out_dir):
    try:
        from modelscope import snapshot_download
    except ImportError:
        return None
    print("[dl] 使用 modelscope SDK 下载...")
    cache = snapshot_download(model_id, allow_patterns=[filename])
    src = os.path.join(cache, filename)
    os.makedirs(out_dir, exist_ok=True)
    dst = os.path.join(out_dir, filename)
    if os.path.abspath(src) != os.path.abspath(dst):
        shutil.copyfile(src, dst)
    return dst


def download_http(model_id, filename, out_dir):
    url = f"https://modelscope.cn/models/{model_id}/resolve/master/{filename}"
    os.makedirs(out_dir, exist_ok=True)
    dst = os.path.join(out_dir, filename)
    print(f"[dl] 直连下载: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as r:
        total = int(r.headers.get("Content-Length", "0") or 0)
        downloaded = 0
        with open(dst, "wb") as f:
            while True:
                chunk = r.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded * 100 // total
                    sys.stdout.write(f"\r[dl] {pct:3d}%  {downloaded // 1024 // 1024}M/{total // 1024 // 1024}M")
                    sys.stdout.flush()
    print()
    return dst


def main():
    args = parse_args()
    filename = args.file or GGUF_FILES[args.quant]
    dst = download_modelscope(args.model, filename, args.out_dir)
    if not dst:
        print("[dl] modelscope 不可用，改用直连 HTTP。")
        dst = download_http(args.model, filename, args.out_dir)
    print(f"[dl] 完成: {dst}")
    print(f"[dl] 启动: python start_virtu_bridge.py --backend llamacpp --gguf {dst}")


if __name__ == "__main__":
    main()
