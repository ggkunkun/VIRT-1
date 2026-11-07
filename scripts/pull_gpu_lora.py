#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""训练完成后把 GPU 实例上的 LoRA 产物拉回本机「原来的文件夹」。

分工原则：云端只产出**便宜的 adapter**（~180MB），合并模型 / GGUF / 上线全部在本机做——
因为本机已有完整 Qwen3-8B 基座（checkpoints/_base_qwen3_8b，16GB），
没必要把 16GB merged + 5GB GGUF 从云端拖回来，既慢又占公网带宽。

默认落点就和历史上几次远程训练一致：checkpoints/virtu_toolcall_lora/

用法
----
    set DAMODEL_PASS=...
    python scripts/pull_gpu_lora.py                       # 拉默认远端目录
    python scripts/pull_gpu_lora.py --remote /root/workspace/virtu/virtu_toolcall_lora
    python scripts/pull_gpu_lora.py --dest checkpoints/my_lora
    python scripts/pull_gpu_lora.py --include-receipt     # 连回执/日志一起拉（默认已含）

拉完会做三项本地校验：adapter_config.json 的 rank 是否为 32、
adapter 权重文件是否存在且非空、training_receipt.json 能否解析。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import remote_gpu as rg  # noqa: E402

REQUIRED_LORA_R = 32

DEFAULT_REMOTE = "/root/workspace/virtu/virtu_toolcall_lora"
DEFAULT_DEST = os.path.join("checkpoints", "virtu_toolcall_lora")

# 只拉这些：核心权重 + 配置 + tokenizer + 回执。日志和中间大数据一律不拉。
KEEP_SUFFIX = (".json", ".jinja", ".txt", ".safetensors", ".model", ".bin", ".md")
SKIP_NAMES = {"optimizer.pt", "scheduler.pt", "rng_state.pth", "trainer_state.json"}


def human(n: float) -> str:
    for unit in ("MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}GB"


def pull(remote_dir: str, dest: str, flat: bool = False):
    c = rg.connect()
    sftp = c.open_sftp()
    t0 = time.time()
    total = 0.0
    names: list[str] = []
    try:
        try:
            entries = sftp.listdir(remote_dir)
        except IOError:
            sys.exit(f"[FATAL] 远端目录不存在: {remote_dir}\n"
                     f"        训练是否已完成？可先跑 remote_gpu.py exec 'ls -la {remote_dir}'")

        wanted = []
        for name in sorted(entries):
            rpath = remote_dir.rstrip("/") + "/" + name
            st = sftp.stat(rpath)
            import stat as _stat
            if _stat.S_ISDIR(st.st_mode):
                continue
            if name in SKIP_NAMES or not name.endswith(KEEP_SUFFIX):
                print(f"  [skip] {name}")
                continue
            wanted.append((name, rpath, st.st_size))

        if not wanted:
            sys.exit(f"[FATAL] {remote_dir} 下没有可拉走的产物")

        os.makedirs(dest, exist_ok=True)
        print(f"\n拉取 {len(wanted)} 个文件 -> {os.path.abspath(dest)}")
        for name, rpath, size in wanted:
            local = os.path.join(dest, name)
            print(f"  [get] {name}  ({human(size / 1e6)})", flush=True)
            sftp.get(rpath, local)
            got = os.path.getsize(local)
            if got != size:
                print(f"    {WARN} 尺寸不符 remote={size} local={got}")
            total += size / 1e6
            names.append(name)
    finally:
        sftp.close()
        c.close()

    print(f"\n完成：{human(total)} / {len(names)} 个文件 / {time.time() - t0:.1f}s")
    return names


def verify(dest: str, names: list[str]):
    """落地三项校验，避免拉回来才发现是半成品。"""
    print("\n=== 本地校验 ===")
    ok = True

    cfgp = os.path.join(dest, "adapter_config.json")
    if os.path.exists(cfgp):
        cfg = json.load(open(cfgp, encoding="utf-8"))
        r = cfg.get("r")
        print(f"  {'OK ' if r == REQUIRED_LORA_R else 'DIFF'} adapter rank r={r} "
              f"(期望 {REQUIRED_LORA_R}), alpha={cfg.get('lora_alpha')}")
        print(f"       target_modules={cfg.get('target_modules')}")
        ok = ok and (r == REQUIRED_LORA_R)
    else:
        print("  FATAL 缺 adapter_config.json")
        ok = False

    wts = [n for n in names if n.endswith(".safetensors")]
    if wts:
        for w in wts:
            sz = os.path.getsize(os.path.join(dest, w)) / 1e6
            print(f"  {'OK ' if sz > 1 else 'WARN'} {w}  {sz:.1f}MB")
    else:
        print("  FATAL 没有任何 adapter 权重")
        ok = False

    rp = os.path.join(dest, "training_receipt.json")
    if os.path.exists(rp):
        try:
            r = json.load(open(rp, encoding="utf-8"))
            print(f"  OK   回执: samples={r.get('samples')} "
                  f"loss_tokens={r.get('loss_tokens')} steps={r.get('steps')}")
        except Exception as e:
            print(f"  WARN 回执解析失败: {e}")
    else:
        print("  WARN 无 training_receipt.json（训练可能异常中断）")

    print("\n=== 下一步（本机完成，不再占用 GPU 机时）===")
    print("  合并 + GGUF：")
    print("    python scripts/merge_numpy.py --base checkpoints/_base_qwen3_8b \\")
    print(f"        --lora {dest} --out checkpoints/virtu_merged_toolcall --mode peft_linear")
    print("  然后用 hf_to_gguf_numpy.py 转 GGUF，再 ollama create 上线")
    return ok


def main():
    ap = argparse.ArgumentParser(description="拉取远端 LoRA 产物回本机")
    ap.add_argument("--remote", default=DEFAULT_REMOTE, help="远端 LoRA 目录")
    ap.add_argument("--dest", default=DEFAULT_DEST, help="本机落点")
    args = ap.parse_args()

    names = pull(args.remote, args.dest)
    ok = verify(args.dest, names)
    sys.exit(0 if ok else 2)


WARN = "[WARN]"

if __name__ == "__main__":
    main()
