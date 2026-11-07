#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GPU 实例一键引导：把平台 Ollama 镜像改造成「训练 + 合并 + GGUF + 上线验证」一体机。

背景
----
平台 Ollama 镜像规格：Ollama v0.21.0 / PyTorch 2.5.0 / CUDA 12.4 / Python 3.11.10 / 约 10GB。
它自带 torch + CUDA + Python 运行时，因此既是最后一公里的服务环境，也能直接当训练机用。
选它就意味着：基座下载、LoRA 训练、权重合并、GGUF 量化、ollama create、tool-call 冒烟，
全部在同一张卡同一个实例里闭环，不需要在两台机器之间搬 16GB 权重。

用法（在 GPU 实例上）
--------------------
    python scripts/gpu_bootstrap.py                       # 体检 + 补依赖
    python scripts/gpu_bootstrap.py --also-download-base  # 顺带下载 Qwen3-8B 基座
    python scripts/gpu_bootstrap.py --smoke-ollama        # 额外验证 ollama serving 可用

设计原则
--------
* 幂等：缺什么补什么，已装且版本合格就跳过，重复跑安全。
* 不覆盖镜像自带 torch：检测到已有 2.5.0+cu124 就保留（flash-attn 预编译 wheel 严格绑定
  torch/CUDA/py 的 ABI，一旦被升级替换，flash-attn 就装不上或导入失败）。
* 失败立即停并给出可执行的补救命令，不留半成品环境。
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

OK = "[OK]"
WARN = "[WARN]"
FATAL = "[FATAL]"


def run(cmd, check=True):
    """打印并执行一条命令；失败时命令已经回显，方便手动复现。"""
    printable = " ".join(str(c) for c in cmd)
    print(f"  $ {printable}", flush=True)
    return subprocess.run([str(c) for c in cmd], check=check,
                          capture_output=True, text=True)


def ver_of(module: str):
    """读模块版本号；未安装返回 None（用子进程，避免污染当前解释器）。"""
    code = f"import {module};print(getattr({module},'__version__','?'))"
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def key(v: str):
    """把 '2.5.0+cu124' 这类版本号转成可比较的元组，非数字段忽略。"""
    out = []
    for part in v.split(".")[:4]:
        digits = ""
        for ch in part:
            if ch.isdigit():
                digits += ch
            else:
                break
        out.append(int(digits) if digits else 0)
    return tuple(out)


def need(module: str, min_ver: str):
    """返回 'ok' / 'old' / 'missing'。"""
    cur = ver_of(module)
    if not cur:
        return "missing"
    try:
        return "ok" if key(cur) >= key(min_ver) else "old"
    except Exception:
        return "old"


def stage_env():
    """S0 环境体检：确认这张镜像的底子能训、能 Serving。"""
    print("=== S0 环境体检 ===")
    report = {}

    print(f"  python {sys.version.split()[0]} | exe {sys.executable}")

    try:
        import torch

        tv = torch.__version__
        cuda = torch.version.cuda
        report["torch"] = tv
        report["cuda"] = cuda
        print(f"  torch {tv} | CUDA {cuda}")
        if not cuda:
            print(f"  {FATAL} 这是 CPU 版 torch —— 换镜像或重装 cu124 版本，别往下走")
            sys.exit(1)
        if torch.cuda.is_available():
            n = torch.cuda.device_count()
            report["ngpu"] = n
            for i in range(n):
                name = torch.cuda.get_device_name(i)
                total = torch.cuda.get_device_properties(i).total_memory / 1e9
                major, minor = torch.cuda.get_device_capability(i)
                print(f"  GPU{i}: {name} | {total:.1f}GB | SM{major}{minor}")
                report[f"gpu{i}"] = {"name": name, "vram_gb": round(total, 1),
                                     "sm": f"{major}{minor}"}
                if total < 24:
                    print(f"  {WARN} 显存 <24GB：Qwen3-8B LoRA 会很勉强，建议 48GB 卡")
                if (major, minor) < (8, 0):
                    print(f"  {WARN} SM{major}{minor} 不满足 FlashAttention-2（需 Ampere/8.0+）")
        else:
            print(f"  {FATAL} torch 看不到 CUDA —— 别往下走了，先解决驱动/容器设备映射")
            sys.exit(1)
    except ImportError:
        print(f"  {FATAL} 未装 torch。安装：")
        print("         pip install torch==2.5.0 --index-url https://download.pytorch.org/whl/cu124")
        sys.exit(1)

    usage = shutil.disk_usage("/root")
    free = usage.free / 1e9
    report["disk_free_gb"] = round(free, 1)
    print(f"  磁盘可用 {free:.1f}GB / {usage.total / 1e9:.1f}GB")
    need_gb = 48  # 基座16 + merged16 + GGUF6 + 数据与中间件约10
    if free < need_gb:
        print(f"  {WARN} 磁盘偏紧：建议 ≥{need_gb}GB，中途写满会留下损坏的 safetensors")

    ol = shutil.which("ollama")
    report["ollama"] = None
    if ol:
        try:
            out = run(["ollama", "--version"], check=False)
            v = (out.stdout or "").strip() or "?"
        except Exception:
            v = "?"
        report["ollama"] = v
        print(f"  {OK} ollama 已就位: {v}")
    else:
        print(f"  {WARN} 未找到 ollama 命令 —— GGUF 之后的 Serving 验证需要另行安装")
    return report


def pip_install(specs):
    """装一组包。返回 True/False。"""
    cmd = [sys.executable, "-m", "pip", "install", "-q"] + list(specs)
    try:
        run(cmd)
        return True
    except subprocess.CalledProcessError as e:
        tail = (e.stderr or "").strip()[-500:]
        print(f"  {FATAL} 安装失败: {' '.join(specs)}")
        if tail:
            print(f"    {tail}")
        return False


def stage_deps():
    """S1 补装训练依赖：只补缺的，不碰镜像自带的 torch。"""
    print("\n=== S1 依赖补齐 ===")
    targets = [
        ("transformers", "4.51.0", ["transformers>=4.51.0"]),   # Qwen3 模型类的最低门槛
        ("datasets", "3.0.0", ["datasets>=3.0.0"]),
        ("accelerate", "1.0.0", ["accelerate>=1.0.0"]),
        ("peft", "0.14.0", ["peft>=0.14.0"]),
        ("bitsandbytes", "0.45.0", ["bitsandbytes>=0.45.0"]),
    ]
    for mod, minv, specs in targets:
        state = need(mod, minv)
        cur = ver_of(mod)
        if state == "ok":
            print(f"  {OK} {mod} {cur}（≥{minv}，跳过）")
        else:
            print(f"  -> 安装 {mod}（当前 {cur}，要求 ≥{minv}）")
            if not pip_install(specs):
                sys.exit(1)
            print(f"  {OK} {mod} {ver_of(mod)}")

    cur = ver_of("flash_attn")
    if cur and cur != "?":
        print(f"  {OK} flash-attn {cur}（跳过）")
        return {"flash_attn": cur}

    print("  -> 安装 flash-attn 2.7.4.post1（预编译 wheel，约 1~3 分钟）")
    if not pip_install(["flash-attn==2.7.4.post1", "--no-build-isolation"]):
        print(f"  {WARN} flash-attn 装不上 -> 将降级 sdpa（激活回到 O(s^2)，batch 要调小）")
        print("        补救：确认 torch 没被改动后重跑本脚本")
        return {"flash_attn": None}
    got = ver_of("flash_attn")
    if got and got != "?":
        print(f"  {OK} flash-attn {got} 可导入（batch 可翻倍、可关梯度检查点）")
    else:
        print(f"  {WARN} 安装成功但无法 import，多半是 torch ABI 不匹配")
    return {"flash_attn": got}


def stage_download_base(model_dir: str):
    """S2 拉基座：走 modelscope，国内机无需代理。"""
    print("\n=== S2 下载 Qwen3-8B 基座 ===")
    dst = Path(model_dir)
    if (dst / "config.json").exists():
        print(f"  {OK} 基座已存在: {dst}")
        return {"downloaded": False, "path": str(dst)}
    dst.mkdir(parents=True, exist_ok=True)
    script = Path(__file__).resolve().parent / "download_base_modelscope.py"
    if script.exists():
        try:
            run([sys.executable, str(script)])
        except subprocess.CalledProcessError:
            print(f"  {FATAL} 下载失败；可手动执行：")
            print(f"         modelscope download --model Qwen/Qwen3-8B --local_dir {dst}")
            sys.exit(1)
    else:
        print("  pip install modelscope 后手动执行：")
        print(f"    modelscope download --model Qwen/Qwen3-8B --local_dir {dst}")
        return {"downloaded": False, "path": str(dst), "manual": True}
    ok = (dst / "config.json").exists()
    print(f"  {OK} 基座就绪" if ok else f"  {WARN} 未见 config.json，请检查目录")
    return {"downloaded": ok, "path": str(dst)}


def stage_smoke_ollama():
    """S3 Serving 冒烟：确认 daemon 能起、API 能应答。模型能力要等 LoRA 落 GGUF 再验。"""
    print("\n=== S3 Ollama Serving 冒烟 ===")
    import urllib.request

    if not shutil.which("ollama"):
        print(f"  {WARN} 无 ollama，跳过")
        return {"ok": False, "reason": "no ollama"}

    proc = subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    base = "http://127.0.0.1:11434"
    try:
        ready = False
        for _ in range(30):
            try:
                with urllib.request.urlopen(base + "/api/tags", timeout=2) as r:
                    json.loads(r.read())
                ready = True
                break
            except Exception:
                time.sleep(1)
        if not ready:
            print(f"  {WARN} 30s 内 daemon 未就绪（首次启动属常见，可稍后手动重试）")
            return {"ok": False, "reason": "timeout"}
        print(f"  {OK} daemon 已监听 11434")
        with urllib.request.urlopen(base + "/api/version", timeout=5) as r:
            v = json.loads(r.read())
        print(f"  {OK} API version {v.get('version')}")
        print("  tool-call 能力留到 GGUF -> ollama create 之后用真实 LoRA 复验")
        return {"ok": True, "version": v.get("version")}
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


def main():
    ap = argparse.ArgumentParser(description="Ollama 镜像 -> 训练/服务一体机 引导脚本")
    ap.add_argument("--also-download-base", action="store_true", help="顺带下载 Qwen3-8B 基座")
    ap.add_argument("--model-dir", default="/root/workspace/Qwen3-8B", help="基座落地目录")
    ap.add_argument("--smoke-ollama", action="store_true", help="额外做 Ollama Serving 冒烟")
    ap.add_argument("--report", default="data/validation/gpu_bootstrap.json",
                    help="体检报告落盘路径")
    args = ap.parse_args()

    t0 = time.time()
    rep = {"image": "ollama / torch2.5.0 / cuda12.4 / py3.11"}
    rep["env"] = stage_env()
    rep["deps"] = stage_deps()
    if args.also_download_base:
        rep["base"] = stage_download_base(args.model_dir)
    if args.smoke_ollama:
        rep["ollama_smoke"] = stage_smoke_ollama()
    rep["elapsed_min"] = round((time.time() - t0) / 60, 2)

    out = Path(args.report)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n=== 完成（{rep['elapsed_min']} 分钟）===")
    print(f"  报告 -> {out}")
    print("\n下一步：一条命令进入训练")
    print("  python scripts/gpu_train_pipeline.py \\")
    print("      --data data/toolcall_optimal.jsonl \\")
    print("      --mode lora --no-grad-ckpt \\")
    print("      --batch 2 --grad-accum 8 \\")
    print("      --attn-impl flash_attention_2 \\")
    print("      --group-by-length --min-vram-gb 44 \\")
    print("      --time-budget-min 40")
    print("\n训练完在同一实例继续闭环：")
    print("  python scripts/gpu_merge_pipeline.py --yes --to-gguf --llama-cpp /root/llama.cpp")
    print("  ollama create virtu-toolcall -f Modelfile && ollama run virtu-toolcall")


if __name__ == "__main__":
    main()
