#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gpu_train_pipeline.py — 远程 GPU 机一键：体检 → 备料 → 训练 r=32 LoRA → 合并 → 导出

【设计原则：GPU 机只做训练，合并与量化在本机做】
本机（Windows/RTX4050 6GB/内存16.9GB）跑不了 8B QLoRA（需 ~16GB 显存），
但有 numpy 纯流式合并器 + GGUF 转换器（scripts/merge_numpy.py、scripts/hf_to_gguf_numpy.py）。
所以 GPU 机只需产出一个小体积的 LoRA adapter（~350MB），其余全部在本机完成。
这比让 GPU 机做全链路更省显存、更省带宽、也更容易排错。

阶段：
  S0 环境体检     GPU 显存 / torch / peft / transformers / bitsandbytes / 磁盘
  S1 备料         基座权重就位 + 数据集就位 + 脚本就位
  S2 数据体检     复用 scripts/validate_render_dataset.py 的 5 项检查（不花 GPU 时间）
  S3 训练         QLoRA，r=32/alpha=64（必须与既有 4 个 LoRA 一致）
  S4 产物校验     adapter 文件完整 + rank/alpha 与既有 LoRA 一致 + 训练回执完整
  S5 回传清单     打印需回传到本机的文件清单与校验和

用法（GPU 机）:
  python scripts/gpu_train_pipeline.py --work-dir /root/virtu_train \
      --data /root/virtu_train/data.jsonl --yes
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# 必须与 checkpoints/ 下既有 4 个 LoRA 完全一致的 rank 配置
REQUIRED_LORA_R = 32
REQUIRED_LORA_ALPHA = 64
REQUIRED_TARGETS = ["q_proj", "k_proj", "v_proj", "o_proj",
                     "gate_proj", "up_proj", "down_proj"]


def log(step, msg):
    print(f"[{step}] {msg}", flush=True)


def run(cmd, cwd=None, check=True, env=None):
    log("exec", " ".join(cmd)[:200])
    e = dict(os.environ)
    if env:
        e.update(env)
    p = subprocess.run(cmd, cwd=cwd, env=e, text=True,
                       capture_output=True, encoding="utf-8", errors="replace")
    if p.stdout:
        print(p.stdout[-4000:])
    if p.stderr:
        print(p.stderr[-3000:], file=sys.stderr)
    if check and p.returncode != 0:
        raise SystemExit(f"[FATAL] 命令失败 rc={p.returncode}")
    return p


def sha256(path, limit=None):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(1 << 20)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


# --------------------------------------------------------------------------- #
# S0 环境体检
# --------------------------------------------------------------------------- #
def stage_preflight(args):
    log("S0", "环境体检 ...")
    report = {"gpu": [], "python": {}, "disk": {}, "ok": True}

    try:
        import torch
        report["python"]["torch"] = torch.__version__
        report["python"]["cuda_available"] = torch.cuda.is_available()
        if torch.cuda.is_available():
            for i in range(torch.cuda.device_count()):
                p = torch.cuda.get_device_properties(i)
                report["gpu"].append({
                    "index": i, "name": p.name,
                    "total_gb": round(p.total_memory / 1e9, 2),
                })
            log("S0", f"CUDA 可用，{len(report['gpu'])} 张卡: "
                      f"{report['gpu'][0]['name']} {report['gpu'][0]['total_gb']}GB")
            if report["gpu"][0]["total_gb"] < 16:
                log("S0", "[WARN] 显存 <16GB，8B QLoRA 可能 OOM（建议 24GB+）")
                report["ok"] = False
                report["disk_note"] = "显存不足"
        else:
            log("S0", "[FATAL] 无 CUDA")
            report["ok"] = False
    except ImportError:
        log("S0", "[FATAL] 未装 torch。安装：pip install torch --index-url "
                  "https://download.pytorch.org/whl/cu124")
        report["ok"] = False

    for mod in ["transformers", "peft", "datasets", "accelerate", "bitsandbytes"]:
        try:
            m = __import__(mod)
            report["python"][mod] = getattr(m, "__version__", "?")
        except ImportError:
            report["python"][mod] = "MISSING"
            if mod in ("transformers", "peft", "datasets"):
                report["ok"] = False
            log("S0", f"[WARN] {mod} 未安装")
    log("S0", "Python 依赖: " + ", ".join(f"{k}={v}" for k, v in report["python"].items()))

    # ---- FlashAttention：现在是决定性开关，不是可选加速 ----
    # 朴素注意力的激活是 O(s^2)，换成 FA 变成 O(s)，同样显存下 batch 能翻倍。
    # 在 48GB 卡上这直接决定能否关闭梯度检查点（见 TRAIN_ACCELERATION.md §10.2）。
    fa_missing = False
    try:
        import flash_attn  # noqa: F401
        report["python"]["flash_attn"] = getattr(flash_attn, "__version__", "?")
        log("S0", f"[OK] flash-attn {report['python']['flash_attn']} 就绪，"
                  f"注意力激活按 O(s) 计，可用更大 batch")
    except ImportError:
        report["python"]["flash_attn"] = "MISSING"
        fa_missing = True
        log("S0", "[WARN] 未安装 flash-attn，将降级 sdpa：激活回到 O(s^2)。"
                  "请把 --batch 减半，或先执行 "
                  "pip install flash-attn --no-build-isolation")

    # torch x cuda 版本组合：flash-attn 的预编译 wheel 严格绑定
    # torch版本 / cuda版本 / python版本 / ABI，组合对不上就要源码编译（很慢）。
    tv = str(report["python"].get("torch", ""))
    if tv and tv != "MISSING" and report["gpu"]:
        try:
            import torch as _t
            cuda_v = _t.version.cuda
            report["python"]["cuda_runtime"] = cuda_v
            log("S0", f"版本组合: torch {tv} / CUDA {cuda_v} / py"
                      f"{sys.version.split()[0]}")
            if fa_missing and cuda_v and cuda_v.startswith("12"):
                log("S0", "提示: 该组合通常有 flash-attn 预编译 wheel，"
                          "装不上多半是 ABI 不匹配，可试 "
                          "pip install flash-attn --no-build-isolation --force-reinstall")
        except Exception:
            pass

    # ---- 按显存自动推荐 batch ----
    if report["gpu"]:
        vram = report["gpu"][0]["total_gb"]
        if vram >= 70:
            rec = "6~8"
        elif vram >= 40:
            rec = "2（48GB 卡配 flash-attn 的最佳点）"
        elif vram >= 24:
            rec = "1~2，且建议开启梯度检查点"
        else:
            rec = "1，且必须 QLoRA + 梯度检查点"
        log("S0", f"显存 {vram}GB -> 建议 --batch {rec}")
        report["batch_recommendation"] = rec

    # peft 版本必须 >= 0.21（add_weighted_adapter 语义以此为准）
    pv = str(report["python"].get("peft", ""))
    if pv != "MISSING":
        try:
            if tuple(int(x) for x in pv.split(".")[:2]) < (0, 21):
                log("S0", f"[WARN] peft {pv} < 0.21，合并语义可能与本机不一致")
        except Exception:
            pass

    du = shutil.disk_usage(args.work_dir if os.path.exists(args.work_dir) else ROOT)
    report["disk"] = {"total_gb": round(du.total / 1e9, 1),
                      "free_gb": round(du.free / 1e9, 1)}
    log("S0", f"磁盘: {report['disk']['free_gb']}GB 可用 / {report['disk']['total_gb']}GB")
    if report["disk"]["free_gb"] < 30:
        log("S0", "[WARN] 磁盘 <30GB：基座 16GB + 数据 + 训练中间件可能不够")
        report["ok"] = False

    with open(os.path.join(args.work_dir, "preflight.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    if not report["ok"]:
        raise SystemExit("[FATAL] 环境体检未通过，见 preflight.json")
    return report


# --------------------------------------------------------------------------- #
# S1 备料
# --------------------------------------------------------------------------- #
def stage_prepare(args):
    log("S1", "备料 ...")
    os.makedirs(args.work_dir, exist_ok=True)

    # 基座
    if not os.path.exists(os.path.join(args.base, "config.json")):
        log("S1", f"[WARN] 基座 {args.base} 缺 config.json，需先下载 Qwen3-8B")
        raise SystemExit(
            "[FATAL] 基座未就位。下载命令：\n"
            "  python scripts/download_base_modelscope.py " + args.base)
    log("S1", f"基座 OK: {args.base}")

    # 数据
    if not os.path.exists(args.data):
        raise SystemExit(f"[FATAL] 数据集不存在: {args.data}")
    n = sum(1 for line in open(args.data, encoding="utf-8") if line.strip())
    log("S1", f"数据集 OK: {args.data} ({n} 行)")
    if n < 1000:
        raise SystemExit(f"[FATAL] 数据量仅 {n} 行，明显不足")

    # 脚本
    for rel in ["scripts/train_virtu_toolcall.py", "scripts/virtu_tokenize.py",
                "scripts/validate_render_dataset.py"]:
        src = os.path.join(ROOT, rel)
        if not os.path.exists(src):
            raise SystemExit(f"[FATAL] 缺脚本: {src}")
    log("S1", "脚本 OK")


# --------------------------------------------------------------------------- #
# S2 数据体检
# --------------------------------------------------------------------------- #
def stage_validate(args):
    log("S2", "数据体检（官方 chat template 渲染 + 掩码校验）...")
    out = os.path.join(args.work_dir, "render_report.json")
    run([sys.executable, os.path.join(HERE, "validate_render_dataset.py"),
         "--data", args.data, "--base", args.base, "--out", out])
    with open(out, encoding="utf-8") as f:
        rep = json.load(f)
    log("S2", f"通过 {rep['passed']}/{rep['total']} | 检查 {rep['checks']}")
    if rep["failed"]:
        raise SystemExit("[FATAL] 数据体检未通过")
    ts = rep["token_stats"]
    log("S2", f"token 总量 {ts['total_tokens']:,} | loss token {ts['total_loss_tokens']:,} "
              f"| p50={ts['p50']} max={ts['max']} | 截断 {ts['truncated_at_max_length']}")
    return rep


# --------------------------------------------------------------------------- #
# S3 训练
# --------------------------------------------------------------------------- #
def stage_train(args):
    log("S3", "训练开始（QLoRA r=%d alpha=%d）..." % (REQUIRED_LORA_R, REQUIRED_LORA_ALPHA))
    cmd = [sys.executable, os.path.join(HERE, "train_virtu_toolcall.py"),
           "--base", args.base,
           "--data", args.data,
           "--out", args.out,
           "--mode", args.mode,
           "--epochs", str(args.epochs),
           "--batch", str(args.batch),
           "--grad-accum", str(args.grad_accum),
           "--max-length", str(args.max_length),
           "--lr", str(args.lr),
           "--lora-r", str(REQUIRED_LORA_R),
           "--lora-alpha", str(REQUIRED_LORA_ALPHA)]
    if args.limit:
        cmd += ["--limit", str(args.limit)]
    if args.single_gpu:
        cmd += ["--single-gpu"]
    if args.no_grad_ckpt:
        cmd += ["--no-grad-ckpt"]
    if args.min_vram_gb:
        cmd += ["--min-vram-gb", str(args.min_vram_gb)]
    if args.group_by_length:
        cmd += ["--group-by-length"]
    if args.attn_impl:
        cmd += ["--attn-impl", args.attn_impl]
    if args.time_budget_min:
        cmd += ["--time-budget-min", str(args.time_budget_min)]
    if args.max_steps:
        cmd += ["--max-steps", str(args.max_steps)]
    t0 = time.time()
    run(cmd)
    log("S3", f"训练完成，耗时 {(time.time()-t0)/60:.1f} 分钟")


# --------------------------------------------------------------------------- #
# S4 产物校验
# --------------------------------------------------------------------------- #
def stage_verify(args):
    log("S4", "产物校验 ...")
    cfg_path = os.path.join(args.out, "adapter_config.json")
    if not os.path.exists(cfg_path):
        raise SystemExit(f"[FATAL] 缺 adapter_config.json: {cfg_path}")
    with open(cfg_path, encoding="utf-8") as f:
        cfg = json.load(f)

    errs = []
    if cfg.get("r") != REQUIRED_LORA_R:
        errs.append(f"rank={cfg.get('r')} != {REQUIRED_LORA_R}")
    if cfg.get("lora_alpha") != REQUIRED_LORA_ALPHA:
        errs.append(f"alpha={cfg.get('lora_alpha')} != {REQUIRED_LORA_ALPHA}")
    targets = sorted(cfg.get("target_modules") or [])
    if targets != sorted(REQUIRED_TARGETS):
        errs.append(f"target_modules 不匹配: {targets}")
    base = str(cfg.get("base_model_name_or_path", ""))
    log("S4", f"r={cfg.get('r')} alpha={cfg.get('lora_alpha')} "
              f"targets={len(targets)} base={base}")
    if errs:
        raise SystemExit("[FATAL] 产物与既有 LoRA 不兼容: " + "; ".join(errs))

    # adapter 权重文件
    wts = [f for f in os.listdir(args.out) if f.endswith(".safetensors")]
    if not wts:
        raise SystemExit("[FATAL] 无 adapter safetensors 权重")
    total = 0
    for w in wts:
        p = os.path.join(args.out, w)
        total += os.path.getsize(p)
        log("S4", f"  {w}  {os.path.getsize(p)/1e6:.1f}MB")
    log("S4", f"adapter 权重合计 {total/1e6:.1f}MB")

    # 训练回执
    rp = os.path.join(args.out, "training_receipt.json")
    if not os.path.exists(rp):
        log("S4", "[WARN] 缺 training_receipt.json")
    else:
        with open(rp, encoding="utf-8") as f:
            r = json.load(f)
        log("S4", f"回执: {r.get('samples')} 样本 / loss {r.get('loss_tokens')} / "
                  f"train_loss={r.get('train_loss')}")

    # 既有 LoRA 的 rank 一致性（跨目录核对）
    lora_root = os.path.join(ROOT, "checkpoints")
    if os.path.isdir(lora_root):
        log("S4", "既有 LoRA rank 核对:")
        for d in sorted(os.listdir(lora_root)):
            c = os.path.join(lora_root, d, "adapter_config.json")
            if not os.path.exists(c):
                continue
            with open(c, encoding="utf-8") as f:
                cc = json.load(f)
            mark = "OK " if cc.get("r") == REQUIRED_LORA_R else "DIFF"
            log("S4", f"  [{mark}] {d}: r={cc.get('r')} alpha={cc.get('lora_alpha')}")
    return True


# --------------------------------------------------------------------------- #
# S5 回传清单
# --------------------------------------------------------------------------- #
def stage_handoff(args):
    log("S5", "回传清单（拷回本机 checkpoints/virtu_toolcall_lora/）:")
    items = []
    for f in sorted(os.listdir(args.out)):
        p = os.path.join(args.out, f)
        if os.path.isfile(p) and (f.endswith(".safetensors") or f.endswith(".json")
                                  or f.endswith(".model") or f.endswith(".txt")):
            items.append({"file": f, "bytes": os.path.getsize(p),
                          "sha256": sha256(p)})
            log("S5", f"  {f:44s} {os.path.getsize(p)/1e6:9.2f}MB  {items[-1]['sha256'][:16]}")
    manifest = os.path.join(args.work_dir, "handoff_manifest.json")
    with open(manifest, "w", encoding="utf-8") as f:
        json.dump({"source": args.out, "files": items,
                   "created": time.strftime("%Y-%m-%d %H:%M:%S")},
                  f, ensure_ascii=False, indent=2)
    log("S5", f"清单 -> {manifest}")

    print("\n" + "=" * 68)
    print("[DONE] GPU 侧全部完成。回传到本机后执行：")
    print("  1) 放到 D:/Virtu模型/checkpoints/virtu_toolcall_lora/")
    print("  2) 本机合并+量化（无需 GPU，峰值内存 <1GB）：")
    print("     python scripts/merge_numpy.py --base checkpoints/_base_qwen3_8b \\")
    print("            --out checkpoints/virtu_merged_v2 --mode peft_linear \\")
    print("            --lora checkpoints/virtu_toolcall_lora --lora-weight 1.0")
    print("  3) 转 GGUF + 导入 Ollama（见 GPU_MERGE_RUNBOOK.md）")
    print("=" * 68)


def main():
    p = argparse.ArgumentParser(description="Virtu tool-call LoRA 远程 GPU 一键流水线")
    p.add_argument("--work-dir", required=True, help="GPU 机工作目录")
    p.add_argument("--base", default="", help="Qwen3-8B 基座目录")
    p.add_argument("--data", default="", help="训练集 jsonl")
    p.add_argument("--out", default="", help="LoRA 输出目录")
    p.add_argument("--mode", default="qlora", choices=["qlora", "lora"])
    p.add_argument("--epochs", type=float, default=3.0)
    p.add_argument("--batch", type=int, default=2)
    p.add_argument("--grad-accum", type=int, default=4)
    p.add_argument("--max-length", type=int, default=4096)
    p.add_argument("--lr", type=float, default=1e-4)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--single-gpu", action="store_true")
    p.add_argument("--no-grad-ckpt", action="store_true",
                   help="关闭梯度检查点（A800/80GB 等大显存卡，省 ~25%% 计算量）")
    p.add_argument("--min-vram-gb", type=float, default=0.0,
                   help="启动前校验可用显存（GB），不足则退出避免空烧")
    p.add_argument("--group-by-length", action="store_true",
                   help="按长度分桶组 batch（padding 浪费 4.9%% -> 0.06%%）")
    p.add_argument("--attn-impl", default="", choices=["", "flash_attention_2", "sdpa"],
                   help="注意力实现，默认 flash_attention_2（未装则自动降级 sdpa 并告警）。"
                        "FA 消掉 O(s^2) 激活显存，让 batch 翻倍、得以关闭梯度检查点")
    p.add_argument("--time-budget-min", type=float, default=0.0,
                   help="训练时间预算（分钟），到点自动保存 LoRA 并停止，避免空烧")
    p.add_argument("--max-steps", type=int, default=0,
                   help="限制总优化步数（0=不限）")
    p.add_argument("--skip-preflight", action="store_true")
    p.add_argument("--skip-validate", action="store_true")
    p.add_argument("--yes", action="store_true", help="跳过交互确认")
    args = p.parse_args()

    args.work_dir = os.path.abspath(args.work_dir)
    os.makedirs(args.work_dir, exist_ok=True)
    args.base = args.base or os.path.join(args.work_dir, "Qwen3-8B")
    args.data = args.data or os.path.join(args.work_dir, "virtu_toolcall_train_unified.jsonl")
    args.out = args.out or os.path.join(args.work_dir, "virtu_toolcall_lora")

    print("=" * 68)
    print(" Virtu tool-call LoRA 远程 GPU 流水线")
    print(f" work-dir : {args.work_dir}")
    print(f" base     : {args.base}")
    print(f" data     : {args.data}")
    print(f" out      : {args.out}")
    print(f" LoRA     : r={REQUIRED_LORA_R} alpha={REQUIRED_LORA_ALPHA} "
          f"mode={args.mode} epochs={args.epochs}")
    print("=" * 68)

    if not args.skip_preflight:
        stage_preflight(args)
    stage_prepare(args)
    if not args.skip_validate:
        stage_validate(args)

    if not args.yes:
        ans = input("\n确认开始训练？(yes/no) ").strip().lower()
        if ans not in ("yes", "y"):
            raise SystemExit("[ABORT] 用户取消")

    stage_train(args)
    stage_verify(args)
    stage_handoff(args)


if __name__ == "__main__":
    main()
