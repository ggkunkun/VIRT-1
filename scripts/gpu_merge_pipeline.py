#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gpu_merge_pipeline.py — GPU 机一键合并流水线

流程：环境/磁盘体检 → 下载 Qwen3-8B 基座（ModelScope 国内源）
      → merge_lora.py --all（4 个同 rank 的 r=32 LoRA）→ 可选转 GGUF
      → 产出合并权重 + tokenizer + merge_receipt.json

为什么必须走 GPU 机：
  - 本机 Windows 无 torch/peft，内存仅 16.9GB（可用 1.8GB），
    8B bf16 基座 ~16GB + 合并峰值远超此数，物理上跑不动。
  - 云端 Damodel 实例系统盘仅 40GB（镜像 ~20GB），放不下
    「基座16GB + 合并产物16GB」，权重/产物一律落数据盘（--work-dir）。

用法（在 GPU 机上，工程根目录执行）:
  python scripts/gpu_merge_pipeline.py --work-dir /root/workspace/virtu_merge
  python scripts/gpu_merge_pipeline.py --base /root/models/Qwen3-8B \
      --out checkpoints/virtu_merged
  python scripts/gpu_merge_pipeline.py ... --to-gguf --llama-cpp /root/llama.cpp

本机无 torch 也可 --help（依赖全部延迟导入）。
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL_ID = "Qwen/Qwen3-8B"
MIN_FREE_GB = 45.0


def parse_args():
    p = argparse.ArgumentParser(description="Virtu GPU 机一键合并流水线")
    p.add_argument("--base", default=None, help="已有 Qwen3-8B 基座目录；不填则自动下载")
    p.add_argument("--work-dir", default="/root/workspace/virtu_merge",
                   help="数据盘工作目录（务必不要放 40GB 系统盘）")
    p.add_argument("--out", default=None, help="合并产物目录，默认 <work-dir>/virtu_merged")
    p.add_argument("--to-gguf", action="store_true", help="合并后转 Q4_K_M GGUF")
    p.add_argument("--llama-cpp", default=None, help="llama.cpp 目录（--to-gguf 时必填）")
    p.add_argument("--skip-download", action="store_true")
    p.add_argument("--yes", action="store_true", help="跳过交互确认")
    return p.parse_args()


def run(cmd, **kw):
    print("[cmd]", " ".join(str(c) for c in cmd), flush=True)
    return subprocess.run(cmd, check=True, **kw)


def check_env(work: Path) -> None:
    print("=== 1/5 环境与磁盘体检 ===")
    print("  python:", sys.version.split()[0])
    for mod in ("torch", "transformers", "peft", "accelerate"):
        ok = importlib.util.find_spec(mod) is not None
        print(f"  {mod:14s}: {'OK' if ok else 'MISSING'}")
        if not ok:
            raise SystemExit(f"[FATAL] 缺少 {mod}，请先 pip install {mod}（transformers>=4.51 支持 Qwen3）")
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total",
                              "--format=csv,noheader"], capture_output=True, text=True, timeout=20)
        print("  gpu:", out.stdout.strip() or out.stderr.strip()[:120])
    except Exception as exc:
        print("  gpu: 查询失败（CPU 合并也可，但会很慢）", type(exc).__name__)
    work.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(work).free / 1e9
    print(f"  工作目录 {work} 剩余 {free:.1f} GB")
    if free < MIN_FREE_GB:
        raise SystemExit(f"[FATAL] 剩余空间不足 {MIN_FREE_GB:.0f}GB（基座~16GB + 产物~16GB + 峰值），"
                         f"请换到数据盘挂载点后重跑 --work-dir。")


def ensure_base(args, work: Path) -> Path:
    print("=== 2/5 准备 Qwen3-8B 基座 ===")
    if args.base:
        base = Path(args.base)
        if not (base / "config.json").exists():
            raise SystemExit(f"[FATAL] --base 不是完整模型目录（缺 config.json）: {base}")
        print("  使用已有基座:", base)
        return base
    base = work / "Qwen3-8B"
    if (base / "config.json").exists() and args.skip_download:
        print("  跳过下载，使用已缓存基座:", base)
        return base
    if importlib.util.find_spec("modelscope") is None:
        print("  安装 modelscope ...")
        run([sys.executable, "-m", "pip", "install", "modelscope", "-q"])
    run([sys.executable, "-m", "modelscope", "download", "--model", MODEL_ID,
         "--local_dir", str(base)])
    if not (base / "config.json").exists():
        raise SystemExit(f"[FATAL] 下载后仍缺 config.json: {base}\n"
                         f"        手动命令: modelscope download --model {MODEL_ID} --local_dir {base}")
    return base


def do_merge(base: Path, out: Path) -> None:
    print("=== 3/5 合并 4 个同 rank LoRA 进基座 ===")
    out.mkdir(parents=True, exist_ok=True)
    run([sys.executable, str(ROOT / "merge_lora.py"), "--all",
         "--base", str(base), "--out", str(out), "--device", "auto"])
    if not (out / "config.json").exists():
        raise SystemExit(f"[FATAL] 合并产物缺 config.json: {out}")
    weights = list(out.glob("*.safetensors")) + list(out.glob("*.bin"))
    if not weights:
        raise SystemExit(f"[FATAL] 合并产物无权重文件: {out}")
    size = sum(w.stat().st_size for w in weights) / 1e9
    print(f"  合并完成: {len(weights)} 个权重分片, 共 {size:.2f} GB")


def do_gguf(args, out: Path, work: Path) -> Path | None:
    if not args.to_gguf:
        return None
    print("=== 4/5 转 GGUF (Q4_K_M) ===")
    if not args.llama_cpp:
        raise SystemExit("[FATAL] --to-gguf 需要 --llama-cpp /path/to/llama.cpp")
    conv = Path(args.llama_cpp) / "convert_hf_to_gguf.py"
    if not conv.exists():
        raise SystemExit(f"[FATAL] 找不到 {conv}")
    gguf = work / "virtu-q4_k_m.gguf"
    run([sys.executable, str(conv), str(out), "--outfile", str(gguf), "--outtype", "q4_k_m"])
    print(f"  GGUF -> {gguf} ({gguf.stat().st_size / 1e9:.2f} GB)")
    return gguf


def main() -> None:
    args = parse_args()
    work = Path(args.work_dir).resolve()
    out = Path(args.out).resolve() if args.out else (work / "virtu_merged")
    print(f"[pipeline] 工作目录={work}\n[pipeline] 产物目录={out}")
    if not args.yes:
        print("  确认继续？(Ctrl-C 取消，或加 --yes 跳过)")

    t0 = time.time()
    check_env(work)
    base = ensure_base(args, work)
    do_merge(base, out)
    gguf = do_gguf(args, out, work)
    print("=== 5/5 生成回执 ===")

    receipt = {
        "status": "COMPLETED", "base_model": str(base),
        "merged_dir": str(out), "gguf": str(gguf) if gguf else None,
        "merged_loras": [
            "turing_conversational_lora (r=32, w=1.2)",
            "cad_cam_six_software_lora (r=32, w=1.0)",
            "omni_autonomous_agent_lora (r=32, w=0.8)",
            "ug_teacher_guided_agent_lora (r=32, w=0.7)",
        ],
        "excluded_loras": [
            "tool_agent_lora_final (r=16, rank 不兼容，保留为运行时可挂载适配器)",
            "damodel_l40s_cad_cam_lora (与 cad_cam_six_software_lora 重复拷贝)",
        ],
        "elapsed_seconds": round(time.time() - t0, 1),
        "download_back_to_local": [
            str(out / "config.json"), str(out / "*.safetensors"),
            str(out / "tokenizer.json"), str(out / "tokenizer_config.json"),
        ] + ([str(gguf)] if gguf else []),
        "cleanup_warning": "云端磁盘紧张：回传完成后立即删除 <work-dir> 下的基座与合并权重，避免爆盘。",
    }
    rp = out / "merge_receipt.json"
    with rp.open("w", encoding="utf-8") as f:
        json.dump(receipt, f, ensure_ascii=False, indent=2)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    print(f"\n[pipeline] 完成，耗时 {receipt['elapsed_seconds']}s，回执 -> {rp}")
    print("[pipeline] 下一步：把产物下载回本地 checkpoints/virtu_merged，"
          "WorkBuddy 桥会自动探测并切换到本地真模型（见 GPU_MERGE_RUNBOOK.md）。")


if __name__ == "__main__":
    main()
