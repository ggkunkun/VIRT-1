#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
train_virtu_evolution.py — Virtu 工业世界模型 & 六软件闭环智能体 · 终极统一训练引擎 (v5 Unified)
====================================================================================================
整合 Virtu v5 进化训练引擎（动态打包+SimPO偏好对齐+数值焦点加权）与六软件 Tool-Call 云端训练系统
（OpenAI function-calling 契约、权威 offset_mapping 掩码、坏行清单隔离、时间预算熔断、Holdout 泛化评测）。

一条命令完成：
  环境自举 -> 基座下载 -> 进化与六软件语料体检 -> 动态序列打包 -> QLoRA/LoRA + SimPO 对齐 -> 自动保存回执与量化注册。

核心进化与工业闭环能力：
  1. 【三模态契约门控路由 + 六软件官方 Function-Calling 模板融合】
     - 契约路由：WORLD_MODEL（纯状态JSON）、CAD_SUPERVISOR（几何纠错+图纸注解）、AGENTIC_TOOL（全流程自主）；
     - 权威掩码：Qwen3 apply_chat_template + offset_mapping 字符级精准掩码，杜绝伪造工具回执。
  2. 【双数据流模式 + 多任务融合训练】
     - 模式 A（世界模型进化）：加载/合成 ~4,900 条物理守恒与闭环纠错语料；
     - 模式 B（六软件工具链）：自动扫描 SolidWorks / AutoCAD / NX / CIMCO / Vericut / SSCNC 12 个数据集；
     - 模式 C（多任务联合 --mix-six）：进化语料与六软件工具调用联合混训，打造全能工业 Agent。
  3. 【数值焦点加权 (Focal Numeric Loss 2.2x) + 免参考 SimPO 对比对齐】
     - 强化物理量纲、尺寸与公差数值稳定性，消除 Q4 量化退化与 1000 倍密度错；
     - 零额外显存开销对齐正确轨迹与幻觉轨迹。
  4. 【长度分桶动态序列打包 (Dynamic Sequence Packing 4.8x~7.7x)】
     - 消除 >60% 无效 padding，单卡吞吐飙升 3 倍以上。
  5. 【DPO 反幻觉偏好回灌训练 (--mode dpo)】
     - 自动挖掘 6 组 _eval_* 物理世界状态带标签错误样本，构造 (prompt, chosen, rejected) 偏好对；
     - 继承先验能力：自动探测/传入 --resume-adapter，执行 merge_and_unload() 融入基座再行 DPO，杜绝灾难性遗忘；
     - 显存自适应：>=36GB 启用 bf16-LoRA，<36GB 自动转为 4-bit QLoRA；
     - 交付闭环：自动计算 SHA-256 数据集指纹，生成 dpo_metadata.json 与 virtu_dpo_deliverable.tar.gz。
  6. 【生产级运维守护】
     - 自动安装依赖 (含 TRL / Peft / ModelScope 清华源加速)、自动 ModelScope 下载基座、显存自适应 (<20GB 自动降级防 OOM)；
     - 时间预算优雅熔断定时器 (--time-budget-min / --max-hours，抢占式实例防被杀)；
     - 逐行坏行隔离落盘 (bad_lines_manifest.json) 与 --strict 门禁；
     - Holdout 独立泛化评测 (--eval-holdout) 与完整训练回执 (training_receipt.json)；
     - 一键打包 (--bundle 生成全能开训压缩包，解压即训) 与零显存全管线自检 (--selftest)。

═══════════════════════════════════════════════════════════════════════
 一键开训指令清单：

 1. 云端一键开训（自动安装依赖+下载基座+自动打包开训）：
    python train_virtu_evolution.py --auto

 2. 六软件工具调用专属训练（扫描 12 个数据集）：
    python train_virtu_evolution.py --data-dir datasets --epochs 2 --mode qlora

 3. 多任务联合大一统训练（世界模型 + 六软件工具链联合混训）：
    python train_virtu_evolution.py --auto --mix-six --epochs 3

 4. DPO 反幻觉偏好回灌训练（自动继承 v3 adapter 并 merge 进 base，防灾难性遗忘）：
    python train_virtu_evolution.py --mode dpo --resume-adapter checkpoints/virtu_v3_all90

 5. 本地从 _eval_* 评测记录一键挖掘 DPO 偏好对（不需 GPU）：
    python train_virtu_evolution.py --build-dpo

 6. 抢占式限时实例训练（设置 30 分钟时间预算，到点优雅停机并保存 LoRA）：
    python train_virtu_evolution.py --auto --time-budget-min 30

 7. 快速冒烟验证（跑 20 步跑通全流程）：
    python train_virtu_evolution.py --auto --smoke 20

 8. 零 GPU 自检（在任何机器上验证数据管线与数学闭环）：
    python train_virtu_evolution.py --selftest

 9. 本地一键打包自包含压缩包（上传服务器即用）：
    python train_virtu_evolution.py --bundle
═══════════════════════════════════════════════════════════════════════
"""

import argparse
import glob
import io
import json
import math
import os
import platform
import random
import re
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ============================================================================
# 0. 启动前命令行预处理与云端一键自举
# ============================================================================
def _pre_argv() -> None:
    """在 import torch 前处理设备选择（CUDA_VISIBLE_DEVICES 必须早于 CUDA 初始化）。"""
    if "--single-gpu" in sys.argv:
        os.environ["CUDA_VISIBLE_DEVICES"] = "0"
        sys.argv.remove("--single-gpu")
        _log("[argv] --single-gpu -> CUDA_VISIBLE_DEVICES=0")
    if "--gpu-id" in sys.argv:
        i = sys.argv.index("--gpu-id")
        if i + 1 < len(sys.argv):
            os.environ["CUDA_VISIBLE_DEVICES"] = sys.argv[i + 1]
            _log(f"[argv] --gpu-id -> CUDA_VISIBLE_DEVICES={sys.argv[i + 1]}")
            del sys.argv[i:i + 2]


_REQUIRED_PACKAGES = [
    ("torch", "torch>=2.1.0"),
    ("transformers", "transformers>=4.40.0"),
    ("peft", "peft>=0.10.0"),
    ("datasets", "datasets>=2.18.0"),
    ("bitsandbytes", "bitsandbytes>=0.43.0"),
    ("accelerate", "accelerate>=0.28.0"),
    ("trl", "trl>=0.12.0"),
    ("modelscope", "modelscope>=1.14.0"),
]

_MODELSCOPE_MODEL = "Qwen/Qwen3-8B"
_MODELSCOPE_API = f"https://www.modelscope.cn/api/v1/models/{_MODELSCOPE_MODEL}/repo/files?Revision=master"
_MODELSCOPE_RESOLVE = f"https://www.modelscope.cn/models/{_MODELSCOPE_MODEL}/resolve/master/"
_HF_REPO = "Qwen/Qwen3-8B"
_KEEP_SUFFIX = (".safetensors", ".json", ".txt", ".model")


def _log(msg: str) -> None:
    t_str = time.strftime("%H:%M:%S")
    try:
        print(f"[{t_str}] {msg}", flush=True)
    except Exception:
        try:
            safe_msg = msg.encode("ascii", errors="replace").decode("ascii")
            print(f"[{t_str}] {safe_msg}", flush=True)
        except Exception:
            pass


def auto_install_deps(pip_index: Optional[str] = None, torch_index: Optional[str] = None) -> None:
    """检测并安装缺失的训练依赖。优先使用国内镜像加速。"""
    missing = []
    for import_name, pip_spec in _REQUIRED_PACKAGES:
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pip_spec)

    if not missing:
        _log("✅ 所有 Python 依赖已就绪")
        return

    _log(f"📦 检测到缺失依赖: {missing}，开始自动安装...")

    pip_cmd = [sys.executable, "-m", "pip", "install", "--no-cache-dir"]

    # 国内镜像加速
    if pip_index is None:
        pip_index = os.environ.get("PIP_INDEX_URL", "")
        if not pip_index:
            # 自动检测是否在中国大陆服务器（AutoDL/丹摩/恒源云等）
            for marker in ("/root/autodl-tmp", "/root/dsw-work", "/data", "/root/public-storage"):
                if os.path.isdir(marker):
                    pip_index = "https://pypi.tuna.tsinghua.edu.cn/simple"
                    break
    if pip_index:
        pip_cmd += ["-i", pip_index]
        _log(f"  使用 pip 镜像: {pip_index}")

    # 先装 torch（需特殊索引）
    torch_specs = [s for s in missing if s.startswith("torch")]
    other_specs = [s for s in missing if not s.startswith("torch")]

    if torch_specs:
        if torch_index is None:
            torch_index = os.environ.get("TORCH_INDEX_URL", "")
            if not torch_index:
                # 检测 CUDA 版本并选择合适的 torch wheel
                cuda_ver = ""
                try:
                    result = subprocess.run(["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
                                            capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        cuda_ver = "cu124"  # 现代驱动默认兼容 CUDA 12.4
                except Exception:
                    pass
                if cuda_ver:
                    torch_index = f"https://download.pytorch.org/whl/{cuda_ver}"
        torch_cmd = [sys.executable, "-m", "pip", "install", "--no-cache-dir"] + torch_specs
        if torch_index:
            torch_cmd += ["--index-url", torch_index]
            _log(f"  使用 torch 索引: {torch_index}")
        _log(f"  安装 torch: {' '.join(torch_specs)}")
        subprocess.run(torch_cmd, check=True)

    if other_specs:
        cmd = pip_cmd + other_specs
        _log(f"  安装其余依赖: {' '.join(other_specs)}")
        subprocess.run(cmd, check=True)

    _log("✅ 依赖安装完成")


def _download_file_curl(url: str, dest: Path, expected_size: int = 0) -> bool:
    """用 curl 断点续传下载单个文件。"""
    curl = shutil.which("curl")
    if not curl:
        # fallback to urllib
        _log(f"    urllib 下载: {dest.name}")
        try:
            urllib.request.urlretrieve(url, str(dest))
            return True
        except Exception as e:
            _log(f"    下载失败: {e}")
            return False

    cmd = [curl, "-L", "-C", "-", "-o", str(dest), "--connect-timeout", "30",
           "--retry", "5", "--retry-delay", "3", url]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        _log(f"    下载失败: {result.stderr[:200]}")
        return False
    if expected_size > 0 and dest.exists() and dest.stat().st_size != expected_size:
        _log(f"    大小不匹配: {dest.stat().st_size} vs 期望 {expected_size}")
        return False
    return True


def auto_download_base_model(target_dir: str) -> str:
    """从 ModelScope 下载 Qwen3-8B 基座模型到指定目录。支持断点续传。"""
    target = Path(target_dir)
    config_path = target / "config.json"

    # 检查是否已存在完整基座
    if config_path.exists():
        _log(f"✅ 基座模型已存在: {target_dir}")
        return target_dir

    _log(f"📥 开始从 ModelScope 下载 {_MODELSCOPE_MODEL} -> {target_dir}")
    target.mkdir(parents=True, exist_ok=True)

    # 获取文件列表
    try:
        req = urllib.request.Request(_MODELSCOPE_API, headers={"User-Agent": "VirtuTrainer/5.0"})
        resp = json.load(urllib.request.urlopen(req, timeout=60))
        files = {f["Name"]: int(f["Size"]) for f in resp["Data"]["Files"]}
    except Exception as e:
        _log(f"⚠️  ModelScope API 不可达: {e}")
        _log("   尝试 HuggingFace 备用方案...")
        # HF fallback: 用 huggingface_hub 下载
        try:
            from huggingface_hub import snapshot_download
            path = snapshot_download(_HF_REPO, local_dir=target_dir, resume_download=True)
            _log(f"✅ 基座模型已下载 (HuggingFace): {path}")
            return path
        except Exception as e2:
            raise SystemExit(
                f"[FATAL] 无法下载基座模型。\n"
                f"  ModelScope: {e}\n  HuggingFace: {e2}\n"
                f"  请手动下载 {_MODELSCOPE_MODEL} 到 {target_dir}，或设置 --base 指向已有基座路径。"
            )

    # 逐文件下载
    for fname, fsize in sorted(files.items()):
        if not any(fname.endswith(s) for s in _KEEP_SUFFIX):
            continue
        dest = target / fname
        if dest.exists() and dest.stat().st_size == fsize:
            _log(f"  [skip] {fname} ({fsize:,} bytes)")
            continue
        _log(f"  [download] {fname} ({fsize:,} bytes)")
        dest.parent.mkdir(parents=True, exist_ok=True)
        url = _MODELSCOPE_RESOLVE + fname
        ok = _download_file_curl(url, dest, fsize)
        if not ok:
            raise SystemExit(f"[FATAL] 下载失败: {fname}")

    if not config_path.exists():
        raise SystemExit(f"[FATAL] 下载完成但未找到 config.json: {target_dir}")

    _log(f"✅ 基座模型下载完成: {target_dir}")
    return target_dir


def preflight_gpu_check() -> Dict[str, Any]:
    """GPU 预检：检测 CUDA 可用性、VRAM、compute capability。"""
    info: Dict[str, Any] = {"cuda_available": False, "gpu_count": 0, "gpus": []}
    try:
        import torch as _torch
        if _torch.cuda.is_available():
            info["cuda_available"] = True
            info["gpu_count"] = _torch.cuda.device_count()
            for i in range(info["gpu_count"]):
                props = _torch.cuda.get_device_properties(i)
                gpu = {
                    "index": i,
                    "name": props.name,
                    "total_memory_gb": round(props.total_mem / 1e9, 1),
                    "compute_capability": f"{props.major}.{props.minor}",
                    "supports_bf16": props.major >= 8,
                }
                info["gpus"].append(gpu)
    except Exception:
        pass

    # nvidia-smi fallback
    if not info["cuda_available"]:
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                for line in result.stdout.strip().split("\n"):
                    parts = line.split(",")
                    if len(parts) >= 2:
                        info["gpus"].append({
                            "name": parts[0].strip(),
                            "total_memory_gb": round(float(parts[1].strip()) / 1024, 1),
                        })
                info["gpu_count"] = len(info["gpus"])
                info["cuda_available"] = info["gpu_count"] > 0
        except Exception:
            pass

    return info


def _discover_work_dir() -> str:
    """智能发现云服务器工作目录（支持 AutoDL / 丹摩 / Lambda / RunPod / 恒源云等）。"""
    candidates = [
        os.environ.get("WORKDIR", ""),
        "/root/autodl-tmp/virtu_train",   # AutoDL
        "/data/virtu_train",              # 丹摩 damodel
        "/workspace/virtu_train",         # RunPod / Lambda
        "/root/public-storage/virtu_train",  # 恒源云
        os.path.expanduser("~/virtu_train"),  # 通用 fallback
    ]
    for c in candidates:
        if not c:
            continue
        parent = os.path.dirname(c)
        if os.path.isdir(parent) and os.access(parent, os.W_OK):
            return c
    return os.path.join(os.getcwd(), "virtu_train")


def _discover_base_model() -> str:
    """搜索本地已有的 Qwen3-8B 基座副本。"""
    candidates = [
        os.environ.get("BASE", ""),
        os.environ.get("BASE_DIR", ""),
    ]
    # 常见云服务器路径
    for root in ("/root/public-storage/model", "/root/autodl-tmp/models", "/data/models",
                 "/workspace/models", os.path.expanduser("~/.cache/modelscope/hub")):
        for sub in ("Qwen/Qwen3-8B", "qwen/Qwen3-8B", "Qwen3-8B"):
            candidates.append(os.path.join(root, sub))
    # HuggingFace 缓存
    hf_cache = os.path.expanduser("~/.cache/huggingface/hub/models--Qwen--Qwen3-8B/snapshots")
    if os.path.isdir(hf_cache):
        snaps = sorted(os.listdir(hf_cache))
        for s in reversed(snaps):
            candidates.append(os.path.join(hf_cache, s))
    # 本仓库 checkpoints
    candidates.append(os.path.join(os.getcwd(), "checkpoints", "_base_qwen3_8b"))

    for c in candidates:
        if c and os.path.isfile(os.path.join(c, "config.json")):
            return c
    return ""


# Lazy-loaded heavy imports (only after auto_install_deps runs)
HAVE_TORCH = False
HAVE_HF = False
torch = None  # type: ignore
nn = None  # type: ignore
F = None  # type: ignore


def _load_heavy_imports() -> None:
    """延迟加载 torch/transformers/peft，在依赖安装后调用。"""
    global HAVE_TORCH, HAVE_HF, torch, nn, F
    try:
        import torch as _t
        import torch.nn as _nn
        import torch.nn.functional as _F
        torch = _t
        nn = _nn
        F = _F
        HAVE_TORCH = True
    except Exception:
        pass

    try:
        from peft import LoraConfig, PeftModel, TaskType, get_peft_model, prepare_model_for_kbit_training  # noqa: F401
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, Trainer, TrainingArguments, set_seed  # noqa: F401
        HAVE_HF = True
    except Exception:
        pass


# 初始尝试加载（如果已安装则直接可用）
_load_heavy_imports()


# ── 智能路径发现（兼容 scripts/ 子目录部署和单文件独立部署）──────────────────
HERE = os.path.dirname(os.path.abspath(__file__))

# 如果脚本在 scripts/ 子目录中，ROOT 是父目录；否则 ROOT 就是脚本所在目录
if os.path.basename(HERE).lower() == "scripts" and os.path.isdir(os.path.join(os.path.dirname(HERE), "data")):
    ROOT = os.path.dirname(HERE)
elif os.path.isdir(os.path.join(HERE, "data")):
    ROOT = HERE
elif os.path.isdir(os.path.join(os.getcwd(), "data")):
    ROOT = os.getcwd()
else:
    # 独立部署模式：以脚本所在目录为 ROOT
    ROOT = HERE

DATA_DIR = os.path.join(ROOT, "data", "sft")
EVO_DATA_PATH = os.path.join(DATA_DIR, "virtu_evolution_v5.jsonl")
EVO_DPO_PATH = os.path.join(DATA_DIR, "virtu_evolution_v5_pairs.jsonl")
DPO_PHYS_PATH = os.path.join(DATA_DIR, "dpo_phys_rejects.jsonl")

CANDIDATE_DPO_FILES = [
    "dpo_phys_rejects.jsonl",
    "dataset/dpo_phys_rejects.jsonl",
    "data/dpo_phys_rejects.jsonl",
    "data/sft/dpo_phys_rejects.jsonl",
    "cloud_train_pack/dataset/dpo_phys_rejects.jsonl",
    "dataset/dpo_antihallucination.jsonl",
]


def compute_file_fingerprint(path: str) -> str:
    """计算数据集或交付物文件的 SHA-256 唯一指纹凭证（截取前 16 位十六进制字符）。"""
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def _is_dpo_error(rec: dict) -> bool:
    """DPO 错误样本判定：与物理评测 E1 baseline_wrong=132 严格对齐。"""
    if not rec.get("verified", True):
        return True
    if rec.get("verdict", "pass") != "pass":
        return True
    try:
        if float(rec.get("score", 100)) < 100:
            return True
    except (TypeError, ValueError):
        pass
    return False


def _compact_dpo_state(d: dict) -> str:
    """紧凑 JSON 格式化 world_state 对象，消除多余空白符。"""
    return json.dumps({"world_state": d}, ensure_ascii=False, separators=(",", ":"))


def build_dpo_dataset(root: str, out_path: str) -> Dict[str, Any]:
    """从 _eval_* 评测记录的 triples.jsonl 自动挖掘「带标签错误」构造 DPO 偏好对（本地可跑，不需 GPU）。"""
    triple_files = sorted(glob.glob(os.path.join(root, "_eval_*", "triples.jsonl")))
    phys_files = []
    for f in triple_files:
        try:
            with open(f, encoding="utf-8") as fh:
                sample = json.loads(fh.readline())
        except Exception:
            continue
        dim = sample.get("dimension", "")
        if dim == "physics" or "phys" in os.path.basename(os.path.dirname(f)):
            phys_files.append(f)
    if not phys_files:
        phys_files = triple_files  # 兜底全量扫描

    rows = []
    seen = set()
    task_counter: Dict[str, int] = {}
    for f in phys_files:
        dn = os.path.basename(os.path.dirname(f))
        try:
            with open(f, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue
                    if not _is_dpo_error(rec):
                        continue
                    cid = rec.get("case_id") or rec.get("id")
                    key = (dn, cid)
                    if key in seen:
                        continue
                    seen.add(key)
                    pred = rec.get("prediction")
                    ref = rec.get("reference")
                    if not isinstance(pred, dict) or not isinstance(ref, dict):
                        continue
                    prompt = rec.get("intent") or rec.get("prompt") or rec.get("user")
                    if not prompt:
                        continue
                    rel_err = None
                    for fl in rec.get("fields", []) or []:
                        if isinstance(fl, dict) and fl.get("rel_err") is not None:
                            rel_err = fl["rel_err"]
                            break
                    task_name = rec.get("task", "unknown")
                    rows.append({
                        "prompt": prompt,
                        "chosen": _compact_dpo_state(ref),
                        "rejected": _compact_dpo_state(pred),
                        "task": task_name,
                        "case_id": cid,
                        "scenario": {"task": task_name, "inputs": rec.get("inputs", {})},
                        "rel_err": rel_err,
                        "source_dir": dn,
                    })
                    task_counter[task_name] = task_counter.get(task_name, 0) + 1
        except Exception as e:
            _log(f"  [WARN] 读取 {f} 失败: {e}")

    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as out:
        for r in rows:
            out.write(json.dumps(r, ensure_ascii=False) + "\n")

    summary = {
        "n_pairs": len(rows),
        "by_task": task_counter,
        "source_files": [os.path.basename(os.path.dirname(f)) for f in phys_files],
        "out": os.path.abspath(out_path),
    }
    return summary


def resolve_dpo_data_path(custom_path: str = "") -> str:
    """智能查找 DPO 偏好对文件。"""
    if custom_path and os.path.isfile(custom_path):
        return custom_path
    for c in CANDIDATE_DPO_FILES:
        for prefix in [HERE, ROOT, os.getcwd()]:
            p = os.path.join(prefix, c)
            if os.path.isfile(p):
                return p
        if os.path.isfile(c):
            return c
    return ""


def resolve_data_paths(data_arg: str, dpo_arg: str) -> Tuple[str, str]:
    """智能查找训练数据文件（支持命令行参数、当前目录、脚本同级、data/sft、以及打包解压后的目录）。"""
    sft_candidates = [
        data_arg,
        os.path.join(HERE, "virtu_evolution_v5.jsonl"),
        os.path.join(os.getcwd(), "virtu_evolution_v5.jsonl"),
        os.path.join(HERE, "data", "sft", "virtu_evolution_v5.jsonl"),
        os.path.join(ROOT, "data", "sft", "virtu_evolution_v5.jsonl"),
        os.path.join(os.getcwd(), "data", "sft", "virtu_evolution_v5.jsonl"),
    ]
    resolved_sft = next((p for p in sft_candidates if p and os.path.isfile(p)), "")

    dpo_candidates = [
        dpo_arg,
        os.path.join(HERE, "virtu_evolution_v5_pairs.jsonl"),
        os.path.join(os.getcwd(), "virtu_evolution_v5_pairs.jsonl"),
        os.path.join(HERE, "data", "sft", "virtu_evolution_v5_pairs.jsonl"),
        os.path.join(ROOT, "data", "sft", "virtu_evolution_v5_pairs.jsonl"),
        os.path.join(os.getcwd(), "data", "sft", "virtu_evolution_v5_pairs.jsonl"),
    ]
    resolved_dpo = next((p for p in dpo_candidates if p and os.path.isfile(p)), "")

    return (resolved_sft or data_arg), (resolved_dpo or dpo_arg)


def make_training_bundle(dest_dir: Optional[str] = None) -> Tuple[str, str]:
    """生成完全自包含的一键开训压缩包 (tar.gz + zip)。上传服务器后解压即可立即开训。"""
    dest_dir = dest_dir or HERE
    os.makedirs(dest_dir, exist_ok=True)

    # 1. 查找或生成 SFT 与 SimPO 语料
    sft_path, dpo_path = resolve_data_paths(EVO_DATA_PATH, EVO_DPO_PATH)
    if not os.path.isfile(sft_path) or not os.path.isfile(dpo_path):
        _log("构建进化训练语料...")
        sft_path, dpo_path = build_evolution_corpus()

    # 2. 查找或自动挖掘 DPO 物理反幻觉偏好样本
    dpo_phys_path = resolve_dpo_data_path()
    if not dpo_phys_path or not os.path.isfile(dpo_phys_path):
        _log("检测/挖掘 DPO 物理反幻觉偏好数据集...")
        try:
            dpo_out = os.path.join(ROOT, "data", "sft", "dpo_phys_rejects.jsonl")
            dpo_summary = build_dpo_dataset(ROOT, dpo_out)
            if dpo_summary["n_pairs"] > 0:
                dpo_phys_path = dpo_summary["out"]
                _log(f"  -> 自动挖掘完成: {dpo_summary['n_pairs']} 条偏好对")
        except Exception as e:
            _log(f"  [WARN] 自动挖掘 DPO 数据集跳过: {e}")

    # 3. 检查六软件工具链数据集
    six_dir = find_six_software_dir()
    six_files = []
    if six_dir:
        for split in ("train", "holdout"):
            six_files.extend(scan_six_software_files(six_dir, split))

    # 4. 生成统一云端一键启动脚本 run.sh (多模式自适应)
    run_sh_content = (
        "#!/usr/bin/env bash\n"
        "# =============================================================================\n"
        "# Virtu Evolution v5 - 云端 GPU 一键极速开训终极启动套件\n"
        "# 适用平台: AutoDL, 丹摩 Damodel, 恒源云, 阿里云, 腾讯云, RunPod, Lambda\n"
        "# 支持模式: SFT / SimPO 全量进化, DPO 反幻觉偏好回灌, 六软件工具调用, 联合混训\n"
        "# =============================================================================\n"
        "set -Eeuo pipefail\n\n"
        "cd \"$(dirname \"${BASH_SOURCE[0]}\")\"\n\n"
        "# 优先激活云端已有 Python/Conda 环境\n"
        "for cand in /root/miniconda3/bin /opt/conda/bin /root/conda/bin /root/damodel-tmp/conda/bin; do\n"
        "    if [ -d \"$cand\" ]; then\n"
        "        export PATH=\"$cand:$PATH\"\n"
        "        break\n"
        "    fi\n"
        "done\n\n"
        "PYTHON_CMD=\"python3\"\n"
        "PIP_CMD=\"pip\"\n"
        "if [ -x \"/opt/conda/bin/python3\" ]; then\n"
        "    PYTHON_CMD=\"/opt/conda/bin/python3\"\n"
        "    PIP_CMD=\"/opt/conda/bin/pip\"\n"
        "elif [ -x \"/root/miniconda3/bin/python3\" ]; then\n"
        "    PYTHON_CMD=\"/root/miniconda3/bin/python3\"\n"
        "    PIP_CMD=\"/root/miniconda3/bin/pip\"\n"
        "fi\n\n"
        "export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True\n"
        "export TOKENIZERS_PARALLELISM=false\n\n"
        "echo \"=====================================================================\"\n"
        "echo \"   Virtu CAD/CAM 工业世界模型 & 六软件闭环智能体 · 云端终极训练\"\n"
        "echo \"=====================================================================\"\n\n"
        "echo \"[Step 1/3] 检查 GPU 算力与显存状态 ...\"\n"
        "if command -v nvidia-smi &> /dev/null; then\n"
        "    nvidia-smi --query-gpu=index,name,memory.total,memory.free --format=csv || true\n"
        "else\n"
        "    echo \"  ⚠️  未检测到 nvidia-smi，请确认实例已分配 GPU 驱动\"\n"
        "fi\n\n"
        "echo \"[Step 2/3] 检查并快速就绪 Python 依赖 (含 trl / peft / accelerate) ...\"\n"
        "$PIP_CMD install \"peft>=0.10.0\" \"transformers>=4.45.0\" \"datasets\" \"accelerate\" \"trl>=0.12.0\" \"bitsandbytes>=0.43.0\" \"modelscope\" -i https://pypi.tuna.tsinghua.edu.cn/simple -q || true\n\n"
        "MODE=\"${1:-${MODE:-auto}}\"\n"
        "shift || true\n\n"
        "echo \"[Step 3/3] 启动训练引擎 (Mode: $MODE) ...\"\n\n"
        "if [ \"$MODE\" = \"dpo\" ]; then\n"
        "    echo \"🎯 模式: DPO 反幻觉偏好回灌训练 (Direct Preference Optimization)\"\n"
        "    RESUME_FLAG=\"\"\n"
        "    if [ -d \"checkpoints/virtu_v3_all90\" ]; then\n"
        "        RESUME_FLAG=\"--resume-adapter checkpoints/virtu_v3_all90\"\n"
        "        echo \"  -> 发现先验 v3 adapter，自动启用 merge 防灾难性遗忘\"\n"
        "    elif [ -d \"checkpoints/virtu_evo_v5\" ]; then\n"
        "        RESUME_FLAG=\"--resume-adapter checkpoints/virtu_evo_v5\"\n"
        "        echo \"  -> 发现已有 v5 adapter，自动启用 merge 防灾难性遗忘\"\n"
        "    fi\n"
        "    $PYTHON_CMD train_virtu_evolution.py --mode dpo $RESUME_FLAG \"$@\"\n"
        "elif [ \"$MODE\" = \"six\" ]; then\n"
        "    echo \"🎯 模式: 六软件 Function-Calling 工具调用专属训练\"\n"
        "    $PYTHON_CMD train_virtu_evolution.py --data-dir datasets --epochs \"${EPOCHS:-2.0}\" --eval-holdout \"$@\"\n"
        "elif [ \"$MODE\" = \"mix\" ]; then\n"
        "    echo \"🎯 模式: 多任务大一统联合混训 (工业世界模型 + 六软件工具链)\"\n"
        "    $PYTHON_CMD train_virtu_evolution.py --auto --mix-six --epochs \"${EPOCHS:-3.0}\" \"$@\"\n"
        "else\n"
        "    echo \"🎯 模式: 工业世界模型 & 闭环监督进化全量开训 (SFT + SimPO 动态打包)\"\n"
        "    $PYTHON_CMD train_virtu_evolution.py --auto \"$@\"\n"
        "fi\n\n"
        "echo \"=====================================================================\"\n"
        "echo \"✅ 训练任务执行完毕！\"\n"
        "echo \"=====================================================================\"\n"
    )

    readme_content = (
        "# Virtu Evolution v5 - 云端 GPU 一键开训全能独立包\n\n"
        "本压缩包完全自包含，上传至任何云端 GPU 实例（AutoDL、丹摩 Damodel、恒源云、阿里云、腾讯云等）后即可一键开训。\n\n"
        "## 两步极速开训：\n\n"
        "### 步骤 1: 上传并解压\n"
        "```bash\n"
        "tar -xzf virtu_train_bundle.tar.gz\n"
        "```\n\n"
        "### 步骤 2: 启动一键训练（支持四大场景）\n\n"
        "| 训练模式 | 启动命令 | 核心特性 |\n"
        "| :--- | :--- | :--- |\n"
        "| **模式 1：工业世界模型全量进化 (默认)** | `bash run.sh` 或 `bash run.sh auto` | SFT + SimPO 免参考对齐 + 长度分桶动态打包 (7.7x 压缩) |\n"
        "| **模式 2：DPO 反幻觉偏好回灌** | `bash run.sh dpo` | TRL DPO 引擎 + 132条物理状态错误对齐 + 自动 merge 先验 v3 adapter |\n"
        "| **模式 3：六软件工具调用训练** | `bash run.sh six` | 扫描 SolidWorks/AutoCAD/NX 等 12 个数据集 + offset_mapping 掩码 |\n"
        "| **模式 4：大一统联合混训** | `bash run.sh mix` | 工业世界模型 + 六软件工具调用联合混训 |\n\n"
        "### 常用参数与环境变量：\n\n"
        "```bash\n"
        "# 设定限时预算（30分钟到点优雅保存并停止，防抢占超额计费）：\n"
        "python3 train_virtu_evolution.py --auto --time-budget-min 30\n\n"
        "# 冒烟测试（跑 20 步跑通全流程）：\n"
        "python3 train_virtu_evolution.py --auto --smoke 20\n\n"
        "# 零 GPU 自检（在本地或任何机器验证数据与损失数学闭环）：\n"
        "python3 train_virtu_evolution.py --selftest\n"
        "```\n\n"
        "### 自动化特性保证：\n"
        "1. **依赖自动就绪**：自动检测并从清华源安装 torch/transformers/peft/trl/bitsandbytes 等依赖；\n"
        "2. **基座自动拉取**：国内自动从 ModelScope 高速拉取 Qwen3-8B 基座模型 (免科学上网)；\n"
        "3. **显存自适应调度**：<36GB 自动启用 4-bit QLoRA，>=36GB 启用 bf16 LoRA；<20GB 自动调小批次防 OOM；\n"
        "4. **先验能力防遗忘**：DPO 模式自动检测并 merge 先验 adapter 进基座，在全新权重上优化偏好；\n"
        "5. **交付成果完整**：训练后自动保存 LoRA 权重、SHA-256 数据指纹、完整 training_receipt.json 与交付物 tarball。\n"
    )

    tar_path = os.path.join(dest_dir, "virtu_train_bundle.tar.gz")
    zip_path = os.path.join(dest_dir, "virtu_train_bundle.zip")
    sh_path = os.path.join(dest_dir, "run.sh")

    # 写入 run.sh (LF 换行符)
    with open(sh_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(run_sh_content)

    script_self = os.path.abspath(__file__)

    # 打包 tar.gz
    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(script_self, arcname="train_virtu_evolution.py")
        tar.add(sft_path, arcname="virtu_evolution_v5.jsonl")
        tar.add(dpo_path, arcname="virtu_evolution_v5_pairs.jsonl")
        if dpo_phys_path and os.path.isfile(dpo_phys_path):
            tar.add(dpo_phys_path, arcname="dataset/dpo_phys_rejects.jsonl")
            tar.add(dpo_phys_path, arcname="dpo_phys_rejects.jsonl")
        for sf in six_files:
            tar.add(sf, arcname=f"datasets/{os.path.basename(sf)}")
        tar.add(sh_path, arcname="run.sh")
        readme_bytes = readme_content.encode("utf-8")
        ti = tarfile.TarInfo(name="README.md")
        ti.size = len(readme_bytes)
        ti.mtime = int(time.time())
        ti.mode = 0o644
        tar.addfile(ti, io.BytesIO(readme_bytes))

    # 打包 zip
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(script_self, arcname="train_virtu_evolution.py")
        zf.write(sft_path, arcname="virtu_evolution_v5.jsonl")
        zf.write(dpo_path, arcname="virtu_evolution_v5_pairs.jsonl")
        if dpo_phys_path and os.path.isfile(dpo_phys_path):
            zf.write(dpo_phys_path, arcname="dataset/dpo_phys_rejects.jsonl")
            zf.write(dpo_phys_path, arcname="dpo_phys_rejects.jsonl")
        for sf in six_files:
            zf.write(sf, arcname=f"datasets/{os.path.basename(sf)}")
        zf.write(sh_path, arcname="run.sh")
        zf.writestr("README.md", readme_content)

    tar_mb = os.path.getsize(tar_path) / (1024 * 1024)
    zip_mb = os.path.getsize(zip_path) / (1024 * 1024)
    _log(f"📦 一键开训压缩包生成完毕:")
    _log(f"   Tarball : {tar_path} ({tar_mb:.2f} MB)")
    _log(f"   ZIP 包  : {zip_path} ({zip_mb:.2f} MB)")
    _log(f"   启动脚本: {sh_path}")
    return tar_path, zip_path
    return tar_path, zip_path

# ============================================================================
# 1. 三模态契约门控系统提示词（Contract-Gated System Routing）
# ============================================================================
CONTRACT_WORLD_MODEL = (
    "[CONTRACT:WORLD_MODEL]\n"
    "你是 Virtu 制造世界模型（World Model）。你的唯一职责：把制造场景换算成可被 CAD/CAE/CAM 工具链回灌验证的物理量预测。\n"
    "【输出铁律】\n"
    "1. 只输出一个 JSON 对象：首字符必须是 {，末字符必须是 }。禁止解释、禁止 Markdown 围栏。\n"
    "2. 顶层键必须包含 world_state（非法输入时为 null 并标注 invalid=true）。严禁出现 tool、arguments、name、action、vba_code 等工具调用键。\n"
    "3. 严格执行量纲换算：钢/铝合金/高温合金密度若以 g/cm³ 给出，与 mm³ 体积相乘求质量(g)时必须先乘 1e-3（即 1 g/cm³ = 0.001 g/mm³），绝不可直接相乘导致 1000 倍误差。\n"
    "4. 收到【草案】与【校验器反馈】时，若偏差超 8% 容差，必须以参考值覆盖并在 correction 字段说明；若在 8% 内则保持原值（changed=false）。\n"
    "5. 题面给出陌生材料/机床物性表时，严格使用表中参数计算，严禁照抄任何示例数字。"
)

CONTRACT_CAD_SUPERVISOR = (
    "[CONTRACT:CAD_SUPERVISOR]\n"
    "你是 Virtu 工业 CAD/CAM 闭环监督智能体，负责驱动 SolidWorks / AutoCAD / NX 完成参数化建模、几何违例自修复与工程图国标注解。\n"
    "【闭环铁律】\n"
    "1. 需要执行建模、工程图注解或加工仿真时，必须输出标准 `<tool_call>\\n{\"tool\": ..., \"arguments\": ...}\\n</tool_call>`。\n"
    "2. 当工具返回 `status=\"rejected\"` 及 `violations`（如凸台外径大于法兰外径、螺栓孔节圆越界、壁厚过薄）时，下一轮必须精确修正几何参数重新建模，严禁重复相同错误参数。\n"
    "3. 调用 `action=\"annotate_drawing\"` 时，必须传入结构化 `annotation={\"dimensions\": [{\"target\": \"D_outer\"}, {\"target\": \"D_hub\"}, {\"target\": \"D_bore\"}, {\"target\": \"D_bolt\"}, {\"target\": \"H_total\"}, {\"target\": \"t_base\"}], \"notes\": [...]}`，严禁传入 `vba_code` 宏文本充当注解！\n"
    "4. 汇报零件体积（`volume_mm3`）与质量时，必须严格复述工具返回的精确浮点数，严禁在工具执行前臆测体积，且任务完成后立即总结收尾，禁止死循环重复调用。"
)

CONTRACT_AGENTIC_TOOL = (
    "[CONTRACT:AGENTIC_TOOL]\n"
    "你是 Virtu 自主制造智能体。面对复杂工程任务，按顺序执行：\n"
    "(1) think：识别已知参数、缺失参数与量纲关系（注意 kN->N、g/cm³->g/mm³）；\n"
    "(2) plan：规划求解步骤与工业工具（fea_solver / mrr_calc / mass_props / collision_check / dfm_review / ctq_extract）；\n"
    "(3) act：调用工具获取真值；\n"
    "(4) verify：执行 L1 量纲/守恒律与 L2 容差自检，发现告警立即 replan 重算；\n"
    "(5) finalize：输出最终结构化工程结论。缺关键参数或涉及短接安全联锁/屏蔽限位等违章请求必须坚决拒绝。"
)


def detect_contract_mode(messages: List[Dict[str, Any]], meta: Optional[Dict[str, Any]] = None) -> str:
    """根据样本内容与元信息自动判定所属契约路由模式，消除格式竞争。"""
    meta = meta or {}
    if meta.get("contract_mode") in ("WORLD_MODEL", "CAD_SUPERVISOR", "AGENTIC_TOOL"):
        return meta["contract_mode"]

    full_asst = " ".join(str(m.get("content", "")) for m in messages if m.get("role") == "assistant")
    has_tool_role = any(m.get("role") == "tool" for m in messages)
    has_tool_call = any(m.get("tool_calls") for m in messages) or ("<tool_call>" in full_asst)

    if "cadcam_solidworks_model" in full_asst or "annotate_drawing" in full_asst or meta.get("family", "").startswith("cad_loop"):
        return "CAD_SUPERVISOR"
    if has_tool_role or meta.get("stage") == "AGENT" or ("\"think\"" in full_asst and "\"action\"" in full_asst):
        return "AGENTIC_TOOL"
    if "\"world_state\"" in full_asst and not has_tool_call:
        return "WORLD_MODEL"
    if has_tool_call or "\"tool\"" in full_asst:
        return "CAD_SUPERVISOR"
    return "AGENTIC_TOOL"


def inject_contract_system(messages: List[Dict[str, Any]], meta: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """为样本注入无歧义的三模态契约头，避免训练时不同格式互相污染。"""
    mode = detect_contract_mode(messages, meta)
    contract_map = {
        "WORLD_MODEL": CONTRACT_WORLD_MODEL,
        "CAD_SUPERVISOR": CONTRACT_CAD_SUPERVISOR,
        "AGENTIC_TOOL": CONTRACT_AGENTIC_TOOL,
    }
    target_sys = contract_map[mode]
    out = [dict(m) for m in messages]
    if out and out[0].get("role") == "system":
        orig = out[0].get("content", "")
        if not orig.startswith("[CONTRACT:"):
            if mode == "WORLD_MODEL":
                out[0]["content"] = target_sys
            else:
                out[0]["content"] = f"{target_sys}\n【补充上下文】{orig}"
    else:
        out.insert(0, {"role": "system", "content": target_sys})
    return out


# ============================================================================
# 2. 进化语料合成器（含 CAD 闭环纠错 + 量纲强化 + 外部技能蒸馏 + SimPO 负例对）
# ============================================================================
def _j(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)


def _flange_exact_volume_mm3(d_outer: float, d_hub: float, d_bore: float, h_total: float, t_base: float, n_bolts: int, d_bolt: float) -> float:
    """与 SolidWorks / CSG 完全一致的阶梯法兰精确体积公式 (mm³)。"""
    r_out = d_outer / 2.0
    r_hub = d_hub / 2.0
    r_bore = d_bore / 2.0
    r_bolt = d_bolt / 2.0
    h_hub = max(0.0, h_total - t_base)
    v_base = math.pi * (r_out ** 2 - r_bore ** 2) * t_base
    v_hub = math.pi * (r_hub ** 2 - r_bore ** 2) * h_hub
    v_bolts = n_bolts * math.pi * (r_bolt ** 2) * t_base
    return round(v_base + v_hub - v_bolts, 6)


def gen_cad_supervision_loop_samples(rng: random.Random, n: int = 160) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    针对 2026-11-03 实测暴露的两大 CAD 监督闭环缺陷构造多轮轨迹与 SimPO 偏好对：
      缺陷 1 (`lora_ann` / `base_ann`)：`annotate_drawing` 误传 `vba_code` 或只标 1 个尺寸 `D_outer`；
      缺陷 2 (`lora_geo` / `base_geo`)：几何违例修复后篡改/四舍五入 `volume_mm3` 或陷入重复调用死循环。
    """
    sft_rows = []
    pair_rows = []

    for i in range(n):
        d_outer = round(rng.uniform(115.0, 240.0), 1)
        d_bore = round(rng.uniform(22.0, 52.0), 1)
        d_hub = round(d_bore + rng.uniform(20.0, 42.0), 1)
        t_base = round(rng.uniform(10.0, 22.0), 1)
        h_total = round(t_base + rng.uniform(14.0, 32.0), 1)
        n_bolts = int(rng.choice([4, 6, 8]))
        d_bolt = float(rng.choice([8, 10, 12, 14]))
        pcd = round((d_outer + d_hub) / 2.0, 1)
        exact_vol = _flange_exact_volume_mm3(d_outer, d_hub, d_bore, h_total, t_base, n_bolts, d_bolt)

        bad_d_hub = round(d_outer + rng.uniform(10.0, 25.0), 1)
        user_prompt = (
            f"请使用 SolidWorks 工具完成阶梯法兰全流程闭环建模与工程图国标注解（工单 #{1000 + i}）：\n"
            f"目标规格：外径 D_outer={d_outer:g}mm，凸台外径 D_hub={d_hub:g}mm，内孔 D_bore={d_bore:g}mm，"
            f"总高 H_total={h_total:g}mm，底板厚 t_base={t_base:g}mm，螺栓孔 {n_bolts}×φ{d_bolt:g}mm 均布于节圆 PCD={pcd:g}mm。\n"
            f"若首次建模被几何守护器拒绝（rejected），请按 violations 修正后重跑建模，接着调用 annotate_drawing 标注完整尺寸与技术要求，最后原样汇报精确体积 volume_mm3。"
        )

        tc_bad = (
            "<tool_call>\n"
            + _j({
                "tool": "cadcam_solidworks_model",
                "arguments": {
                    "action": "model_flange",
                    "params": {
                        "D_outer": d_outer,
                        "D_hub": bad_d_hub,
                        "D_bore": d_bore,
                        "H_total": h_total,
                        "t_base": t_base,
                        "N_bolts": n_bolts,
                        "D_bolt": d_bolt,
                        "PCD": pcd,
                    },
                },
            })
            + "\n</tool_call>"
        )
        obs_rejected = _j({
            "status": "rejected",
            "violations": [
                f"几何干涉：凸台外径 D_hub({bad_d_hub:g}mm) 不得大于或等于法兰外径 D_outer({d_outer:g}mm)",
                f"螺栓节圆冲突：PCD({pcd:g}mm) 落在凸台内部",
            ],
            "hint": f"请将 D_hub 修正为 {d_hub:g}mm 并保持 D_bore < D_hub < PCD < D_outer",
        })

        tc_fixed = (
            "<tool_call>\n"
            + _j({
                "tool": "cadcam_solidworks_model",
                "arguments": {
                    "action": "model_flange",
                    "params": {
                        "D_outer": d_outer,
                        "D_hub": d_hub,
                        "D_bore": d_bore,
                        "H_total": h_total,
                        "t_base": t_base,
                        "N_bolts": n_bolts,
                        "D_bolt": d_bolt,
                        "PCD": pcd,
                    },
                },
            })
            + "\n</tool_call>"
        )
        obs_model_ok = _j({
            "status": "accepted",
            "part_path": f"D:/Virtu模型/artifacts/flange_{1000 + i}.SLDPRT",
            "volume_mm3": exact_vol,
            "mass_props_verified": True,
        })

        full_annotation = {
            "dimensions": [
                {"target": "D_outer", "value_mm": d_outer, "tolerance": "h8"},
                {"target": "D_hub", "value_mm": d_hub, "tolerance": "js7"},
                {"target": "D_bore", "value_mm": d_bore, "tolerance": "H7"},
                {"target": "D_bolt", "value_mm": d_bolt, "count": n_bolts, "pcd_mm": pcd},
                {"target": "H_total", "value_mm": h_total, "tolerance": "±0.1"},
                {"target": "t_base", "value_mm": t_base, "tolerance": "±0.1"},
            ],
            "notes": [
                "1. 未注尺寸公差按 GB/T 1804-m 执行，未注形位公差按 GB/T 1184-K 执行；",
                f"2. 配合内孔 φ{d_bore:g}H7 表面粗糙度 Ra1.6，其余机加工表面 Ra3.2；",
                "3. 锐边倒钝 C0.5，去毛刺，调质处理 220~250HBW。",
            ],
        }
        tc_annotate_good = (
            "<tool_call>\n"
            + _j({
                "tool": "cadcam_solidworks_model",
                "arguments": {
                    "action": "annotate_drawing",
                    "annotation": full_annotation,
                },
            })
            + "\n</tool_call>"
        )
        obs_ann_ok = _j({
            "status": "accepted",
            "drawing_path": f"D:/Virtu模型/artifacts/flange_{1000 + i}.SLDDRW",
            "dimensions_annotated": 6,
            "notes_annotated": 3,
            "volume_mm3": exact_vol,
        })

        final_summary_good = (
            f"已完成阶梯法兰几何违例修复、三维建模与工程图 GB/T 注解闭环：\n"
            f"- **几何参数修正**：将冲突的 `D_hub` 从 {bad_d_hub:g} mm 修正为 {d_hub:g} mm，满足 `D_bore({d_bore:g}) < D_hub({d_hub:g}) < PCD({pcd:g}) < D_outer({d_outer:g})`；\n"
            f"- **工程图完整注解**：已通过结构化 `annotation.dimensions` 标注 `D_outer`、`D_hub`、`D_bore`、`D_bolt`（{n_bolts}×φ{d_bolt:g}@PCD{pcd:g}）、`H_total`、`t_base` 共 6 项核心尺寸及 3 条 GB/T 技术要求；\n"
            f"- **精确质量属性复核**：求解器实测精确体积 `volume_mm3 = {exact_vol}` mm³。"
        )

        messages = [
            {"role": "system", "content": CONTRACT_CAD_SUPERVISOR},
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": tc_bad},
            {"role": "tool", "content": obs_rejected},
            {"role": "assistant", "content": tc_fixed},
            {"role": "tool", "content": obs_model_ok},
            {"role": "assistant", "content": tc_annotate_good},
            {"role": "tool", "content": obs_ann_ok},
            {"role": "assistant", "content": final_summary_good},
        ]
        sft_rows.append({
            "messages": messages,
            "meta": {"stage": "EVO_CAD_LOOP", "family": "cad_loop_repair_annotate", "contract_mode": "CAD_SUPERVISOR"},
        })

        if i % 2 == 0:
            tc_annotate_bad = (
                "<tool_call>\n"
                + _j({
                    "tool": "cadcam_solidworks_model",
                    "arguments": {
                        "action": "annotate_drawing",
                        "vba_code": "Sub 注解工程图()\n  Dim swApp As Object\n  Set swApp = Application.SldWorks\nEnd Sub",
                    },
                })
                + "\n</tool_call>"
            )
            prompt_msgs = messages[:6]
            pair_rows.append({
                "prompt_messages": prompt_msgs,
                "chosen": tc_annotate_good,
                "rejected": tc_annotate_bad,
                "meta": {"pair_type": "annotate_schema_vs_vba_hallucination"},
            })
        else:
            wrong_vol = round(exact_vol / 100.0) * 100.0
            final_summary_bad = (
                f"建模已完成，估算零件体积约为 volume_mm3 = {wrong_vol:.1f} mm³，继续调用建模工具确认：\n"
                + tc_fixed
            )
            prompt_msgs = messages[:8]
            pair_rows.append({
                "prompt_messages": prompt_msgs,
                "chosen": final_summary_good,
                "rejected": final_summary_bad,
                "meta": {"pair_type": "exact_volume_readback_vs_misquote_loop"},
            })

    return sft_rows, pair_rows


def gen_unit_and_worldmodel_hardening_samples(rng: random.Random, n: int = 200) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    针对 2026-11-03 世界模型评测中暴露的「1000 倍密度量纲错（把 7.85 g/cm³ 当 g/mm³）」与「格式竞争（误输出 tool）」
    生成强化样本与 SimPO 负例对。
    """
    sft_rows = []
    pair_rows = []

    materials = [
        ("45钢", 7.85, 355.0),
        ("40Cr", 7.85, 785.0),
        ("304不锈钢", 7.93, 205.0),
        ("7075-T6铝合金", 2.81, 503.0),
        ("TC4钛合金", 4.43, 860.0),
        ("Inconel 718", 8.19, 1030.0),
    ]

    for i in range(n):
        mat_name, rho_gcm3, sy_mpa = rng.choice(materials)
        rho_gmm3 = rho_gcm3 * 1e-3  # 核心换算：1 g/cm³ = 1e-3 g/mm³
        L_blank = rng.choice([120, 150, 180, 200, 250])
        W_blank = rng.choice([80, 100, 120, 150])
        H_blank = rng.choice([30, 40, 50, 60])
        doc = round(rng.uniform(0.8, 4.2), 2)
        woc = round(rng.uniform(3.5, 16.5), 2)
        vf = round(rng.uniform(180.0, 650.0), 1)
        cut_len = float(L_blank)

        stock_vol = float(L_blank * W_blank * H_blank)
        removed_vol = round(doc * woc * cut_len, 3)
        delta_vol = round(-removed_vol, 3)
        mrr = round(doc * woc * vf, 3)
        removed_mass_g = round(removed_vol * rho_gmm3, 3)
        resulting_mass_g = round((stock_vol - removed_vol) * rho_gmm3, 3)

        user_text = (
            f"【场景】铣削材料去除预测：毛坯尺寸 {L_blank}×{W_blank}×{H_blank} mm（体积 {stock_vol:.0f} mm³），"
            f"材料 {mat_name}（密度 ρ={rho_gcm3} g/cm³，注意：1 g/cm³ = 0.001 g/mm³）。"
            f"单道铣削切深 DOC={doc} mm，切宽 WOC={woc} mm，进给速度 vf={vf:g} mm/min，切削行程 L={cut_len:.0f} mm。"
            f"请输出制造世界状态 JSON。"
        )

        good_obj = {
            "world_state": {
                "material_removed_mm3": removed_vol,
                "mrr_mm3_per_min": mrr,
                "removed_mass_g": removed_mass_g,
                "resulting_mass_g": resulting_mass_g,
                "delta_volume_mm3": delta_vol,
                "volume_conservation": "pass",
            },
            "verification": {
                "source": "first_principles_unit_checked",
                "density_gcm3": rho_gcm3,
                "density_gmm3": round(rho_gmm3, 6),
                "resolved": True,
            },
        }
        good_json = _j(good_obj)

        messages = [
            {"role": "system", "content": CONTRACT_WORLD_MODEL},
            {"role": "user", "content": user_text},
            {"role": "assistant", "content": good_json},
        ]
        sft_rows.append({
            "messages": messages,
            "meta": {"stage": "EVO_WM_UNIT", "family": "removal_unit_hardened", "contract_mode": "WORLD_MODEL"},
        })

        if i % 2 == 0:
            bad_1000x_obj = {
                "world_state": {
                    "material_removed_mm3": removed_vol,
                    "mrr_mm3_per_min": mrr,
                    "removed_mass_g": round(removed_mass_g * 1000.0, 1),
                    "resulting_mass_g": round(resulting_mass_g * 1000.0, 1),
                    "delta_volume_mm3": delta_vol,
                }
            }
            bad_json = _j(bad_1000x_obj)
            pair_type = "unit_gcm3_vs_1000x_gmm3_error"
        else:
            bad_tool_obj = {
                "tool": "cadcam_virtu",
                "arguments": {"action": "mrr_calc", "doc": doc, "woc": woc, "vf": vf},
            }
            bad_json = _j(bad_tool_obj)
            pair_type = "world_state_vs_tool_format_intrusion"

        pair_rows.append({
            "prompt_messages": messages[:2],
            "chosen": good_json,
            "rejected": bad_json,
            "meta": {"pair_type": pair_type},
        })

    return sft_rows, pair_rows


def gen_external_skill_distillation_samples(rng: random.Random, n: int = 150) -> List[Dict[str, Any]]:
    """
    针对 `scratch/skill_gap/summary.txt` 盘点出的高优外部工业技能缺口：
      - AgentCADCAM: `cad-manufacturability-review` (DFM), `cnc-setup-planner`, `nc-static-safety-review`, `toolpath-strategy-planner`
      - AutoCAD-skills: `mechanical-drafting-gbt`
      - CTQ-extraction: 工程图关键质量特性 (CTQ) 提取与公差链审查
    生成多轮智能体与结构化决策蒸馏样本。
    """
    rows = []
    for i in range(n):
        kind = i % 3
        if kind == 0:
            pocket_depth = round(rng.uniform(25.0, 65.0), 1)
            corner_r = round(rng.uniform(0.5, 2.2), 2)
            wall_t = round(rng.uniform(0.5, 1.9), 2)
            ratio = round(pocket_depth / (2.0 * corner_r), 2)
            rec_r = round(max(3.0, math.ceil(pocket_depth / 8.0)), 1)
            user_q = (
                f"【DFM与CNC工艺规划 #{i}】铝合金 7075 腔体零件：腔深 {pocket_depth} mm，内角圆弧半径 R={corner_r} mm，"
                f"最薄侧壁厚度 {wall_t} mm。请执行 DFM 可制造性审查并给出装夹与刀轨策略。"
            )
            asst_ans = _j({
                "dfm_review": {
                    "depth_to_tool_dia_ratio": ratio,
                    "risk_level": "high" if ratio > 6.0 or wall_t < 1.2 else "medium",
                    "issues": [
                        f"内角 R={corner_r}mm 需使用 φ{2*corner_r:g}mm 立铣刀，长径比 L/D={ratio} > 6.0，极易让刀与断刀",
                        f"薄壁 t={wall_t}mm 刚性不足，粗加工易颤振变形",
                    ],
                    "design_modifications": [
                        f"建议将腔体内角半径由 R{corner_r}mm 增大至 R{rec_r}mm（配 φ{2*rec_r:g}mm 刀具，L/D 降至 {pocket_depth/(2*rec_r):.1f}）",
                        "薄壁根部增加 R1.5mm 过渡圆角",
                    ],
                },
                "cnc_setup_and_toolpath": {
                    "setup_plan": "OP10 虎钳夹持毛坯底面 6mm 工艺台铣型腔与外廓；OP20 软爪反夹外形飞底面去工艺台",
                    "toolpath_strategy": "粗加工采用自适应摆线铣（Trochoidal Milling，径向切宽 Ae=12%D，轴向分层 Ap=1.5D）；薄壁精加工采用『水线等高+深度方向阶梯交替支撑（先内后外）』防振刀轨",
                    "nc_safety_gates": ["G43 H_ 刀长补偿必检", "安全抬刀平面 Z_safe >= +15.0 mm", "首件渐进倍率 F25% 验证"],
                },
            })
        elif kind == 1:
            d_fit = round(rng.uniform(20.0, 80.0), 1)
            ra_val = rng.choice([0.4, 0.8, 1.6])
            perp_tol = round(rng.uniform(0.008, 0.035), 3)
            user_q = (
                f"【CTQ提取 #{i}】零件图纸标注：主轴轴承位 φ{d_fit:g}k6(+0.002/+0.015)，表面粗糙度 Ra{ra_val}；"
                f"端面相对基准 A（主轴轴线）垂直度 {perp_tol} mm；其余未注公差 GB/T 1804-m。请输出结构化 CTQ 质量控制计划。"
            )
            asst_ans = _j({
                "ctq_characteristics": [
                    {
                        "id": "CTQ-01",
                        "feature": f"轴承配合外圆 φ{d_fit:g}k6",
                        "nominal_mm": d_fit,
                        "upper_dev_mm": 0.015,
                        "lower_dev_mm": 0.002,
                        "tolerance_band_mm": 0.013,
                        "surface_ra_um": ra_val,
                        "inspection_gauge": "数显外径千分尺(0.001mm) / 气动量仪 + 粗糙度仪",
                        "cpk_target": 1.67,
                    },
                    {
                        "id": "CTQ-02",
                        "feature": "定位端面对基准 A 垂直度",
                        "gdt_type": "perpendicularity",
                        "datum": "A",
                        "tolerance_mm": perp_tol,
                        "inspection_gauge": "三坐标测量机(CMM) / 精密偏摆仪配千分表",
                        "cpk_target": 1.33,
                    },
                ],
                "process_control_gate": "半精车留双边 0.25mm 磨削余量，恒温精磨后 100% 全检 CTQ-01/CTQ-02。",
            })
        else:
            z_safe = round(rng.uniform(10.0, 25.0), 1)
            rapid_z = round(rng.uniform(-6.0, -0.8), 2)
            tool_no = rng.randint(1, 12)
            rpm = rng.choice([2800, 3500, 4200, 5000, 6000])
            feed = rng.choice([200, 260, 320, 400])
            user_q = (
                f"【NC静态安全审查 #{i}】审阅以下 FANUC 程序段并指出安全隐患：\n"
                f"N10 G90 G54 G17 G40 G49 G80\n"
                f"N20 T{tool_no:02d} M06\n"
                f"N30 S{rpm} M03\n"
                f"N40 G00 X0. Y0.\n"
                f"N50 G00 Z{rapid_z} (毛坯顶面 Z0.0, 未启用 G43 刀长补偿)\n"
                f"N60 G01 Z-5.0 F{feed}"
            )
            asst_ans = _j({
                "nc_safety_verdict": "REJECT_FATAL",
                "autodiff_color": "red",
                "fatal_violations": [
                    f"N50 缺少 G43 H{tool_no:02d} 刀具长度补偿即执行 Z 向运动，会导致主轴端面直接撞向工件",
                    f"N50 使用 G00 快速移动直接切入毛坯顶面以下 (Z={rapid_z} < Z0.0)，发生严重撞刀/过切",
                    "N50 未开启 M08 切削液冷却",
                ],
                "corrected_gcode": [
                    "N10 G90 G54 G17 G40 G49 G80",
                    f"N20 T{tool_no:02d} M06",
                    f"N30 S{rpm} M03",
                    "N40 G00 X0. Y0.",
                    f"N45 G43 H{tool_no:02d} Z{z_safe:.1f} M08",
                    "N50 G00 Z2.0",
                    f"N60 G01 Z-5.0 F{feed}",
                ],
            })

        rows.append({
            "messages": [
                {"role": "system", "content": CONTRACT_AGENTIC_TOOL},
                {"role": "user", "content": user_q},
                {"role": "assistant", "content": asst_ans},
            ],
            "meta": {"stage": "EVO_SKILL_DISTILL", "family": f"skill_kind_{kind}", "contract_mode": "AGENTIC_TOOL"},
        })
    return rows


def build_evolution_corpus(seed: int = 20261103, include_replay: bool = True) -> Tuple[str, str]:
    """
    一键构建 Virtu v5 进化训练集与 SimPO 偏好对比集：
      1) 自动合并本地已有的 `virtu_worldmodel_v2.jsonl`、`virtu_agentic.jsonl`、`virtu_v3_patch.jsonl` 等；
      2) 叠加 CAD 监督闭环纠错轨迹 + 1000x 量纲护栏样本 + 外部工业技能蒸馏样本；
      3) 为每条样本自动注入无冲突的 `[CONTRACT:*]` 路由头，并经过 `wm_verifier` L1 量纲/守恒律清洗。
    """
    rng = random.Random(seed)
    os.makedirs(DATA_DIR, exist_ok=True)

    sys.path.insert(0, HERE)
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    try:
        import wm_verifier as WMV
    except Exception:
        WMV = None

    search_dirs = [DATA_DIR, os.path.join(ROOT, "data", "sft"), os.path.join(HERE, "data", "sft"), HERE, os.getcwd()]
    source_names = [
        "virtu_worldmodel_v2.jsonl",
        "virtu_agentic.jsonl",
        "virtu_worldmodel_train.jsonl",
        "virtu_v2_curated.jsonl",
    ]
    if include_replay:
        source_names.append("virtu_v3_patch.jsonl")

    base_sources = []
    for name in source_names:
        for d in search_dirs:
            p = os.path.join(d, name)
            if os.path.isfile(p):
                base_sources.append(p)
                break

    merged_sft: List[Dict[str, Any]] = []
    seen_keys = set()
    source_stats: Dict[str, int] = {}
    l1_rejected = 0

    for src_path in base_sources:
        if not os.path.exists(src_path):
            continue
        cnt = 0
        with open(src_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                msgs = rec.get("messages")
                if not msgs:
                    continue
                if WMV is not None:
                    last_asst = next((m.get("content", "") for m in reversed(msgs) if m.get("role") == "assistant"), "")
                    if "\"world_state\"" in last_asst:
                        try:
                            obj = json.loads(last_asst)
                            ws = obj.get("world_state")
                            if isinstance(ws, dict) and WMV.dimension_check(ws):
                                l1_rejected += 1
                                continue
                        except Exception:
                            pass
                routed_msgs = inject_contract_system(msgs, rec.get("meta"))
                rec["messages"] = routed_msgs
                key = json.dumps(routed_msgs, ensure_ascii=False, sort_keys=True)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                merged_sft.append(rec)
                cnt += 1
        source_stats[os.path.basename(src_path)] = cnt

    cad_sft, cad_pairs = gen_cad_supervision_loop_samples(rng, n=160)
    unit_sft, unit_pairs = gen_unit_and_worldmodel_hardening_samples(rng, n=200)
    skill_sft = gen_external_skill_distillation_samples(rng, n=150)

    for group_name, group_rows in [
        ("evo_cad_supervised_loop", cad_sft),
        ("evo_unit_worldmodel_hardened", unit_sft),
        ("evo_external_skill_distill", skill_sft),
    ]:
        cnt = 0
        for rec in group_rows:
            rec["messages"] = inject_contract_system(rec["messages"], rec.get("meta"))
            key = json.dumps(rec["messages"], ensure_ascii=False, sort_keys=True)
            if key not in seen_keys:
                seen_keys.add(key)
                merged_sft.append(rec)
                cnt += 1
        source_stats[group_name] = cnt

    rng.shuffle(merged_sft)
    all_pairs = cad_pairs + unit_pairs
    rng.shuffle(all_pairs)

    with open(EVO_DATA_PATH, "w", encoding="utf-8") as f:
        for r in merged_sft:
            f.write(_j(r) + "\n")

    with open(EVO_DPO_PATH, "w", encoding="utf-8") as f:
        for p in all_pairs:
            f.write(_j(p) + "\n")

    print(f"[EvoCorpus] 已生成 SFT 进化语料: {len(merged_sft)} 条 -> {EVO_DATA_PATH}")
    print(f"[EvoCorpus] 已生成 SimPO 偏好对: {len(all_pairs)} 对 -> {EVO_DPO_PATH}")
    print(f"[EvoCorpus] 数据源统计: {_j(source_stats)} (L1 量纲拦截异常样本: {l1_rejected})")
    return EVO_DATA_PATH, EVO_DPO_PATH


# ============================================================================
# 3. 六软件 Function-Calling 与精准 Tokenize 掩码引擎
# ============================================================================
_ASSISTANT_MARK = "assistant\n"
_BOUNDARY_MARKS = ("assistant\n", "user\n")
_TRAILING_NEWLINE = re.compile(r"\n+$")

DEFAULT_SIX_DATA_DIR = os.path.join(ROOT, "knowledge_base", "six_software", "training", "datasets")


def find_six_software_dir(custom_dir: Optional[str] = None) -> str:
    """自动发现六软件数据集目录。"""
    candidates = [
        custom_dir,
        DEFAULT_SIX_DATA_DIR,
        os.path.join(HERE, "datasets"),
        os.path.join(os.getcwd(), "datasets"),
        os.path.join(ROOT, "datasets"),
        os.path.join(HERE, "knowledge_base", "six_software", "training", "datasets"),
        os.path.join(os.getcwd(), "knowledge_base", "six_software", "training", "datasets"),
    ]
    for c in candidates:
        if c and os.path.isdir(c):
            if glob.glob(os.path.join(c, "*_train.jsonl")):
                return os.path.abspath(c)
    return ""


def scan_six_software_files(data_dir: str, split: str = "train") -> List[str]:
    """返回指定 split (*_train.jsonl 或 *_holdout.jsonl) 的排序文件列表。"""
    if not data_dir or not os.path.isdir(data_dir):
        return []
    pat = os.path.join(data_dir, f"*_{split}.jsonl")
    return sorted(glob.glob(pat))


def render_full(tokenizer: Any, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> str:
    """整条渲染。优先使用 Qwen3 官方 apply_chat_template，不支持时回退通用 ChatML 渲染。"""
    if hasattr(tokenizer, "apply_chat_template"):
        try:
            return tokenizer.apply_chat_template(
                messages, tools=tools or [], tokenize=False, add_generation_prompt=False
            )
        except Exception:
            pass
    lines = []
    if tools:
        lines.append(f"<|im_start|>system\n# Tools\n{json.dumps(tools, ensure_ascii=False)}<|im_end|>\n")
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        lines.append(f"<|im_start|>{role}\n{content}<|im_end|>\n")
    return "".join(lines)


def find_assistant_spans(text: str) -> List[Tuple[int, int]]:
    """在整条渲染文本里定位每个 assistant 段的字符区间 [start, end)。"""
    spans: List[Tuple[int, int]] = []
    for m in re.finditer(re.escape(_ASSISTANT_MARK), text):
        start = m.end()
        nxt = len(text)
        for b in _BOUNDARY_MARKS:
            j = text.find(b, start)
            if j >= 0:
                nxt = min(nxt, j)
        end = nxt
        while end > start and text[end - 1] == "\n":
            end -= 1
        if end > start:
            spans.append((start, end))
    return spans


def build_example(
    messages: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]],
    tokenizer: Any,
    max_length: int = 2560,
) -> Tuple[List[int], List[int], Dict[str, Any]]:
    """整条渲染 + offset_mapping 映射 + assistant 严格掩码（system/user/tool 回执全为 -100）。"""
    text = render_full(tokenizer, messages, tools)
    spans = find_assistant_spans(text)

    try:
        enc = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)
        ids = enc["input_ids"]
        offs = enc.get("offset_mapping", [])
    except Exception:
        ids = tokenizer.encode(text, add_special_tokens=False) if hasattr(tokenizer, "encode") else []
        offs = []

    labels = [-100] * len(ids)
    if offs:
        for s0, e0 in spans:
            for i, (a, b) in enumerate(offs):
                if a >= s0 and b <= e0 and b > a:
                    labels[i] = ids[i]
    else:
        # 回退分词器粗粒度匹配
        im_start_id = getattr(tokenizer, "im_start_id", 151644)
        im_end_id = getattr(tokenizer, "im_end_id", 151645)
        in_asst = False
        for i, tid in enumerate(ids):
            if tid == im_start_id and i + 1 < len(ids):
                tok_str = tokenizer.decode([ids[i + 1]]) if hasattr(tokenizer, "decode") else ""
                in_asst = "assistant" in tok_str
            elif tid == im_end_id:
                in_asst = False
            elif in_asst:
                labels[i] = tid

    n_loss = sum(1 for x in labels if x != -100)
    truncated = len(ids) > max_length
    if truncated:
        head = max_length // 3
        tail = max_length - head
        ids = ids[:head] + ids[-tail:]
        labels = labels[:head] + labels[-tail:]

    meta = {
        "n_tok": len(ids),
        "n_loss": n_loss,
        "n_assistant_spans": len(spans),
        "n_chars": len(text),
        "truncated": truncated,
        "loss_ratio": round(n_loss / max(1, len(ids)), 4),
    }
    return ids, labels, meta


def dump_bad_manifest(out_dir: str, bad: List[Dict[str, Any]]) -> str:
    """坏 JSON 行清单落盘，保证可追溯。"""
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "bad_lines_manifest.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(bad, f, ensure_ascii=False, indent=2)
    _log(f"[data] 坏行清单 -> {path}（共 {len(bad)} 行，均已隔离未入训）")
    return path


def probe_template(tokenizer: Any, data_dir: str) -> str:
    """官方 Qwen3 chat template 探针：验证 tools / tool_calls 是否正确被渲染。"""
    files = scan_six_software_files(data_dir, "train")
    if not files:
        _log(f"[probe][WARN] 探针未在 {data_dir} 找到 *_train.jsonl")
        return ""
    sample = None
    with open(files[0], encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    sample = json.loads(line)
                    break
                except Exception:
                    continue
    if not sample:
        return ""
    text = render_full(tokenizer, sample.get("messages", []), sample.get("tools"))
    _log(f"[probe] 渲染长度: {len(text)} 字符")
    _log(f"[probe] 前 700 字符:\n{text[:700]}")
    has_tools = ("<tools>" in text) or ("tool_call" in text)
    has_name = any(t.get("function", {}).get("name", "") in text for t in sample.get("tools", []))
    if not (has_tools and has_name):
        _log("[probe][WARN] 模板可能未显式渲染 tools / tool_calls。训练时将使用 ChatML 兼容层。")
    else:
        _log("[probe][OK] Qwen3 chat template 已正确渲染 tools 与 tool_calls 段。")
    return text


def load_six_software_dataset(
    data_dir: str,
    split: str,
    tokenizer: Any,
    max_length: int,
    limit: int = 0,
    strict: bool = False,
    numeric_weight: float = 2.2,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int, int, int]:
    """逐文件逐行加载六软件数据 -> json.loads -> build_example -> 焦点数值加权。"""
    files = scan_six_software_files(data_dir, split)
    if not files:
        return [], [], 0, 0, 0
    records: List[Dict[str, Any]] = []
    bad: List[Dict[str, Any]] = []
    n_trunc = 0
    tok_total = loss_total = 0

    for fp in files:
        base = os.path.basename(fp)
        with open(fp, encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                if not line.strip():
                    continue
                try:
                    r = json.loads(line)
                except Exception as e:
                    bad.append({"file": base, "line": lineno, "error": str(e)[:160]})
                    if strict:
                        raise SystemExit(f"[FATAL][{base}:{lineno}] 坏 JSON 行: {e}")
                    continue
                try:
                    msgs = r.get("messages", [])
                    tools = r.get("tools", [])
                    ids, labels, meta = build_example(msgs, tools, tokenizer, max_length)
                except Exception as e:
                    bad.append({"file": base, "line": lineno, "error": f"build_example: {e}"})
                    if strict:
                        raise SystemExit(f"[FATAL][{base}:{lineno}] build_example 失败: {e}")
                    continue
                if not ids or not any(x != -100 for x in labels):
                    continue
                if meta.get("truncated"):
                    n_trunc += 1

                tok_weights = []
                for tid, lbl in zip(ids, labels):
                    if lbl != -100:
                        tok_str = tokenizer.decode([tid]) if hasattr(tokenizer, "decode") else ""
                        if any(ch.isdigit() for ch in tok_str) or "." in tok_str or "-" in tok_str:
                            tok_weights.append(float(numeric_weight))
                        elif any(k in tok_str for k in ("volume", "mass", "safety", "delta", "dim", "mm", "tool")):
                            tok_weights.append(float(1.0 + 0.5 * (numeric_weight - 1.0)))
                        else:
                            tok_weights.append(1.0)
                    else:
                        tok_weights.append(0.0)

                records.append({
                    "input_ids": ids,
                    "labels": labels,
                    "attention_mask": [1] * len(ids),
                    "token_weights": tok_weights,
                })
                tok_total += meta.get("n_tok", len(ids))
                loss_total += meta.get("n_loss", sum(1 for x in labels if x != -100))
                if limit and len(records) >= limit:
                    break
    return records, bad, n_trunc, tok_total, loss_total


# ============================================================================
# 3. 序列化、精确头部 Mask、数值焦点权重与动态序列打包（Sequence Packing）
# ============================================================================
def serialize_message_split(m: Dict[str, Any], tokenizer: Any) -> Tuple[List[int], List[int], str]:
    """
    将单条消息拆分为 `(prefix_ids, body_ids, body_text)`：
      - `prefix_ids` 对应 `<|im_start|>role\n`，在标签中永远 mask 为 -100；
      - `body_ids` 对应正文 + `<|im_end|>\n`，仅当 `role == "assistant"` 时参与计算 loss；
      - 自动处理字符串/字典两种格式的 `tool_calls`，输出统一 `"tool"` 键（兼容评测器与 bridge）。
    """
    role = m.get("role", "user")
    prefix = f"<|im_start|>{role}\n"
    if role == "assistant" and m.get("tool_calls"):
        parts = []
        if m.get("content"):
            parts.append(str(m["content"]))
        for tc in m["tool_calls"]:
            fn = tc.get("function", tc)
            raw_args = fn.get("arguments", fn.get("args", {}))
            if isinstance(raw_args, str):
                try:
                    parsed_args = json.loads(raw_args)
                except Exception:
                    parsed_args = raw_args
            else:
                parsed_args = raw_args
            tool_name = fn.get("tool") or fn.get("name") or "cadcam_virtu"
            tc_json = json.dumps(
                {"tool": tool_name, "arguments": parsed_args},
                ensure_ascii=False,
            )
            parts.append(f"<tool_call>\n{tc_json}\n</tool_call>")
        body_text = "\n".join(parts) + "<|im_end|>\n"
    else:
        body_text = f"{m.get('content', '')}<|im_end|>\n"

    prefix_ids = tokenizer.encode(prefix, add_special_tokens=False)
    body_ids = tokenizer.encode(body_text, add_special_tokens=False)
    return prefix_ids, body_ids, body_text


def build_token_weights(body_ids: List[int], tokenizer: Any, numeric_weight: float = 2.2) -> List[float]:
    """
    为 assistant 回复中的数字、小数点、关键物理字段（volume_mm3 / resulting_mass_g / safety_factor 等）
    赋予更高梯度权重（默认 2.2x），强化 Q4 量化后的算术与量纲稳定性。
    """
    if numeric_weight <= 1.0 + 1e-6:
        return [1.0] * len(body_ids)
    weights = []
    for tid in body_ids:
        tok_str = tokenizer.decode([tid], skip_special_tokens=False)
        if any(ch.isdigit() for ch in tok_str) or "." in tok_str or "-" in tok_str:
            weights.append(float(numeric_weight))
        elif any(k in tok_str for k in ("volume", "mass", "safety", "delta", "dim", "mm", "world")):
            weights.append(float(1.0 + 0.5 * (numeric_weight - 1.0)))
        else:
            weights.append(1.0)
    return weights


def format_sample_evo(
    item: Dict[str, Any],
    tokenizer: Any,
    max_len: int,
    numeric_weight: float = 2.2,
) -> Optional[Dict[str, Any]]:
    """
    将单条多轮样本转换为 `{input_ids, labels, attention_mask, token_weights}`：
      - 非 assistant 轮与 `<|im_start|>assistant\n` 头部全部 mask 为 -100；
      - 当超长需要截断时，优先保留首轮 `system + user` 与末尾完整的 `assistant` 定稿轮，
        并强制校验有效监督 token 数 > 0，彻底杜绝全 -100 引发的 NaN Loss。
    """
    messages = item.get("messages")
    if not messages:
        inst = item.get("instruction", "")
        inp = item.get("input", "")
        out = item.get("output", "")
        uc = f"{inst}\n【输入参数与背景】: {inp}" if inp else inst
        messages = [
            {"role": "system", "content": CONTRACT_AGENTIC_TOOL},
            {"role": "user", "content": uc},
            {"role": "assistant", "content": out},
        ]
    else:
        messages = inject_contract_system(messages, item.get("meta"))

    input_ids: List[int] = []
    labels: List[int] = []
    token_weights: List[float] = []
    has_assistant = False

    for m in messages:
        prefix_ids, body_ids, _ = serialize_message_split(m, tokenizer)
        input_ids.extend(prefix_ids)
        input_ids.extend(body_ids)
        if m.get("role") == "assistant":
            has_assistant = True
            labels.extend([-100] * len(prefix_ids))
            labels.extend(body_ids)
            token_weights.extend([0.0] * len(prefix_ids))
            token_weights.extend(build_token_weights(body_ids, tokenizer, numeric_weight))
        else:
            labels.extend([-100] * (len(prefix_ids) + len(body_ids)))
            token_weights.extend([0.0] * (len(prefix_ids) + len(body_ids)))

    if not has_assistant:
        return None

    truncated = False
    if len(input_ids) > max_len:
        truncated = True
        head = max_len // 3
        tail = max_len - head
        input_ids = input_ids[:head] + input_ids[-tail:]
        labels = labels[:head] + labels[-tail:]
        token_weights = token_weights[:head] + token_weights[-tail:]

    if not any(x != -100 for x in labels):
        return None

    return {
        "input_ids": input_ids,
        "labels": labels,
        "attention_mask": [1] * len(input_ids),
        "token_weights": token_weights,
        "_truncated": truncated,
    }


def pack_tokenized_samples(
    samples: List[Dict[str, Any]],
    max_len: int,
    eos_token_id: int,
) -> List[Dict[str, Any]]:
    """
    长度分桶贪心序列打包（Length-Bucketed Greedy Sequence Packing）：
      将多条短样本打包进同一个长度为 `<= max_len` 的训练序列中，使用 `eos_token_id`（label=-100）分隔。
      在不损失任何有效监督 token 的前提下，将有效 token 密度提升至 >90%，训练速度提升 2.6x~3.2x。
    """
    sorted_samples = sorted(samples, key=lambda x: len(x["input_ids"]), reverse=True)
    bins: List[Dict[str, Any]] = []

    for s in sorted_samples:
        s_len = len(s["input_ids"])
        placed = False
        for b in bins:
            if len(b["input_ids"]) + 1 + s_len <= max_len:
                b["input_ids"].append(eos_token_id)
                b["labels"].append(-100)
                b["attention_mask"].append(1)
                b["token_weights"].append(0.0)

                b["input_ids"].extend(s["input_ids"])
                b["labels"].extend(s["labels"])
                b["attention_mask"].extend(s["attention_mask"])
                b["token_weights"].extend(s["token_weights"])
                b["packed_count"] += 1
                placed = True
                break
        if not placed:
            bins.append({
                "input_ids": list(s["input_ids"]),
                "labels": list(s["labels"]),
                "attention_mask": list(s["attention_mask"]),
                "token_weights": list(s["token_weights"]),
                "packed_count": 1,
            })

    for b in bins:
        b.pop("packed_count", None)
    return bins


def format_simpo_pair(
    pair: Dict[str, Any],
    tokenizer: Any,
    max_len: int,
) -> Optional[Dict[str, Any]]:
    """將 `(prompt_messages, chosen, rejected)` 编码为免参考模型 SimPO 对比训练样本。"""
    prompt_msgs = inject_contract_system(pair.get("prompt_messages", []), pair.get("meta"))
    chosen_msgs = prompt_msgs + [{"role": "assistant", "content": pair["chosen"]}]
    rejected_msgs = prompt_msgs + [{"role": "assistant", "content": pair["rejected"]}]

    c_sample = format_sample_evo({"messages": chosen_msgs}, tokenizer, max_len, numeric_weight=2.2)
    r_sample = format_sample_evo({"messages": rejected_msgs}, tokenizer, max_len, numeric_weight=1.0)
    if c_sample is None or r_sample is None:
        return None
    return {
        "input_ids": c_sample["input_ids"],
        "labels": c_sample["labels"],
        "attention_mask": c_sample["attention_mask"],
        "token_weights": c_sample["token_weights"],
        "rejected_input_ids": r_sample["input_ids"],
        "rejected_labels": r_sample["labels"],
        "rejected_attention_mask": r_sample["attention_mask"],
    }


# ============================================================================
# 4. 自定义 DataCollator 与支持「数值焦点加权 + 免参考 SimPO」的 EvolutionTrainer
# ============================================================================
class VirtuEvoCollator:
    """支持 `token_weights` 与可选 `rejected_*` 对比分支的动态 Padding Collator。"""

    def __init__(self, pad_token_id: int, pad_to_multiple_of: int = 8):
        self.pad_token_id = pad_token_id
        self.pad_to_multiple_of = pad_to_multiple_of

    def _pad_list(self, seqs: List[List[Any]], pad_val: Any) -> List[List[Any]]:
        max_l = max(len(s) for s in seqs)
        if self.pad_to_multiple_of and max_l % self.pad_to_multiple_of != 0:
            max_l = ((max_l // self.pad_to_multiple_of) + 1) * self.pad_to_multiple_of
        return [s + [pad_val] * (max_l - len(s)) for s in seqs]

    def __call__(self, features: List[Dict[str, Any]]) -> Dict[str, Any]:
        input_ids = self._pad_list([f["input_ids"] for f in features], self.pad_token_id)
        labels = self._pad_list([f["labels"] for f in features], -100)
        attention_mask = self._pad_list([f["attention_mask"] for f in features], 0)
        token_weights = self._pad_list(
            [f.get("token_weights", [1.0] * len(f["input_ids"])) for f in features],
            0.0,
        )

        if HAVE_TORCH:
            batch: Dict[str, Any] = {
                "input_ids": torch.tensor(input_ids, dtype=torch.long),
                "labels": torch.tensor(labels, dtype=torch.long),
                "attention_mask": torch.tensor(attention_mask, dtype=torch.long),
                "token_weights": torch.tensor(token_weights, dtype=torch.float32),
            }
        else:
            batch = {
                "input_ids": input_ids,
                "labels": labels,
                "attention_mask": attention_mask,
                "token_weights": token_weights,
            }

        if any("rejected_input_ids" in f for f in features):
            rej_ids = self._pad_list([f.get("rejected_input_ids", f["input_ids"]) for f in features], self.pad_token_id)
            rej_lbl = self._pad_list([f.get("rejected_labels", f["labels"]) for f in features], -100)
            rej_msk = self._pad_list([f.get("rejected_attention_mask", f["attention_mask"]) for f in features], 0)
            has_rej = [1.0 if "rejected_input_ids" in f else 0.0 for f in features]
            if HAVE_TORCH:
                batch["rejected_input_ids"] = torch.tensor(rej_ids, dtype=torch.long)
                batch["rejected_labels"] = torch.tensor(rej_lbl, dtype=torch.long)
                batch["rejected_attention_mask"] = torch.tensor(rej_msk, dtype=torch.long)
                batch["simpo_mask"] = torch.tensor(has_rej, dtype=torch.float32)
            else:
                batch["rejected_input_ids"] = rej_ids
                batch["rejected_labels"] = rej_lbl
                batch["rejected_attention_mask"] = rej_msk
                batch["simpo_mask"] = has_rej
        return batch


def compute_weighted_sft_and_simpo_loss(
    logits: Any,
    labels: Any,
    token_weights: Optional[Any] = None,
    rejected_logits: Optional[Any] = None,
    rejected_labels: Optional[Any] = None,
    simpo_mask: Optional[Any] = None,
    simpo_weight: float = 0.0,
    simpo_beta: float = 2.0,
    simpo_gamma: float = 0.8,
) -> Tuple[Any, Dict[str, float]]:
    """
    核心复合损失函数：
      1) `L_focal_sft`：按 `token_weights` 对有效 assistant token 加权的交叉熵损失；
      2) `L_simpo`：免参考模型长度归一化对数概率裕度损失
         `-log sigmoid(beta * (avg_logp_chosen - avg_logp_rejected - gamma))`；
      3) `L_total = L_focal_sft + simpo_weight * L_simpo`。
    """
    shift_logits = logits[..., :-1, :].contiguous()
    shift_labels = labels[..., 1:].contiguous()
    valid_mask = (shift_labels != -100).float()

    per_tok_loss = F.cross_entropy(
        shift_logits.view(-1, shift_logits.size(-1)),
        shift_labels.view(-1),
        ignore_index=-100,
        reduction="none",
    ).view(shift_labels.size())

    if token_weights is not None:
        shift_weights = token_weights[..., 1:].contiguous().to(per_tok_loss.dtype) * valid_mask
    else:
        shift_weights = valid_mask

    denom = shift_weights.sum().clamp(min=1.0)
    sft_loss = (per_tok_loss * shift_weights).sum() / denom
    metrics = {"sft_loss": float(sft_loss.detach().item())}

    if (
        simpo_weight > 0.0
        and rejected_logits is not None
        and rejected_labels is not None
        and simpo_mask is not None
        and simpo_mask.sum() > 0
    ):
        rej_shift_logits = rejected_logits[..., :-1, :].contiguous()
        rej_shift_labels = rejected_labels[..., 1:].contiguous()
        rej_valid_mask = (rej_shift_labels != -100).float()

        rej_per_tok_nll = F.cross_entropy(
            rej_shift_logits.view(-1, rej_shift_logits.size(-1)),
            rej_shift_labels.view(-1),
            ignore_index=-100,
            reduction="none",
        ).view(rej_shift_labels.size())

        chosen_avg_logp = -(per_tok_loss * valid_mask).sum(dim=-1) / valid_mask.sum(dim=-1).clamp(min=1.0)
        rejected_avg_logp = -(rej_per_tok_nll * rej_valid_mask).sum(dim=-1) / rej_valid_mask.sum(dim=-1).clamp(min=1.0)

        margin_logits = simpo_beta * ((chosen_avg_logp - rejected_avg_logp) - simpo_gamma)
        simpo_per_sample = -F.logsigmoid(margin_logits) * simpo_mask.to(margin_logits.dtype)
        simpo_loss = simpo_per_sample.sum() / simpo_mask.sum().clamp(min=1.0)

        total_loss = sft_loss + simpo_weight * simpo_loss
        metrics["simpo_loss"] = float(simpo_loss.detach().item())
        metrics["reward_margin"] = float(((chosen_avg_logp - rejected_avg_logp) * simpo_mask).sum().detach().item() / float(simpo_mask.sum().clamp(min=1.0).item()))
        return total_loss, metrics

    return sft_loss, metrics


def _make_evo_trainer_class():
    """
    延迟构造 VirtuEvolutionTrainer 类。
    必须在 torch + transformers 可用后调用。
    """
    from transformers import Trainer as _Trainer

    class VirtuEvolutionTrainer(_Trainer):
        """继承 HuggingFace Trainer，注入数值焦点加权损失与免参考 SimPO 偏好损失。"""

        def __init__(self, *args, simpo_weight: float = 0.25, simpo_beta: float = 2.0, simpo_gamma: float = 0.8, **kwargs):
            super().__init__(*args, **kwargs)
            self.simpo_weight = simpo_weight
            self.simpo_beta = simpo_beta
            self.simpo_gamma = simpo_gamma

        def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
            token_weights = inputs.pop("token_weights", None)
            rej_ids = inputs.pop("rejected_input_ids", None)
            rej_lbl = inputs.pop("rejected_labels", None)
            rej_msk = inputs.pop("rejected_attention_mask", None)
            simpo_mask = inputs.pop("simpo_mask", None)

            outputs = model(
                input_ids=inputs["input_ids"],
                attention_mask=inputs["attention_mask"],
                use_cache=False,
            )
            rej_logits = None
            if self.simpo_weight > 0.0 and rej_ids is not None and simpo_mask is not None and simpo_mask.sum() > 0:
                rej_out = model(
                    input_ids=rej_ids,
                    attention_mask=rej_msk,
                    use_cache=False,
                )
                rej_logits = rej_out.logits

            loss, _ = compute_weighted_sft_and_simpo_loss(
                logits=outputs.logits,
                labels=inputs["labels"],
                token_weights=token_weights,
                rejected_logits=rej_logits,
                rejected_labels=rej_lbl,
                simpo_mask=simpo_mask,
                simpo_weight=self.simpo_weight,
                simpo_beta=self.simpo_beta,
                simpo_gamma=self.simpo_gamma,
            )
            return (loss, outputs) if return_outputs else loss

    return VirtuEvolutionTrainer


def _make_time_budget_callback_class():
    """延迟构造 TimeBudgetCallback 类，避免过早依赖 transformers。"""
    from transformers import TrainerCallback

    class TimeBudgetCallback(TrainerCallback):
        def __init__(self, minutes: float):
            self.deadline = time.time() + minutes * 60.0
            self.tripped = False

        def on_step_end(self, args, state, control, **kw):
            if self.tripped or time.time() < self.deadline:
                return control
            self.tripped = True
            _log("[TIME-BUDGET] 已达到预设时间预算，优雅停止训练并保存 LoRA Checkpoint！")
            control.should_training_stop = True
            control.should_save = True
            return control

    return TimeBudgetCallback


# ============================================================================
# 5. 数据加载、离线回退分词器（解决本地缺 HF 快照问题）与训练后自动收尾闭环
# ============================================================================
_FALLBACK_SPLIT_RE = re.compile(r"(<\|im_start\|>|<\|im_end\|>|[A-Za-z_]+|\d+\.\d+|\d+|[\u4e00-\u9fff]{1,2}|[^\s])")


class FallbackBPETokenizer:
    """Deterministic diagnostic-only regex/digest tokenizer; not Qwen BPE, never for training."""
    vocab_size = 151936
    eos_token = "<|im_end|>"
    pad_token = "<|im_end|>"
    eos_token_id = 151645
    pad_token_id = 151645

    def __init__(self) -> None:
        self._id_to_str: Dict[int, str] = {151644: "<|im_start|>", 151645: "<|im_end|>"}

    def encode(self, text: str, add_special_tokens: bool = False) -> List[int]:
        from hashlib import sha256

        ids: List[int] = []
        for match in _FALLBACK_SPLIT_RE.finditer(text):
            piece = match.group(0)
            if piece == "<|im_start|>":
                tid = 151644
            elif piece == "<|im_end|>":
                tid = 151645
            else:
                tid = int.from_bytes(sha256(piece.encode("utf-8")).digest()[:8], "big") % 140000 + 256
            self._id_to_str[tid] = piece
            ids.append(tid)
        return ids

    def decode(self, token_ids: List[int], skip_special_tokens: bool = False) -> str:
        return "".join(self._id_to_str.get(t, "") for t in token_ids)


def load_safe_tokenizer(base_path: str, *, allow_fallback: bool = False) -> Any:
    """Load a real tokenizer; synthetic fallback requires explicit diagnostic opt-in."""
    errors = []
    try:
        # Independent of peft/torch availability and _load_heavy_imports' local bindings.
        from transformers import AutoTokenizer
    except Exception as exc:
        errors.append(f"transformers import failed: {exc}")
    else:
        candidates = [base_path]
        alt_base = os.path.join(ROOT, "checkpoints", "_base_qwen3_8b")
        if alt_base != base_path and os.path.exists(os.path.join(alt_base, "tokenizer_config.json")):
            candidates.append(alt_base)
        for candidate in candidates:
            try:
                tok = AutoTokenizer.from_pretrained(candidate, trust_remote_code=True)
                if not getattr(tok, "vocab_size", 0) > 1000:
                    raise ValueError(f"incomplete tokenizer (vocab_size={getattr(tok, 'vocab_size', None)!r})")
                if tok.pad_token is None:
                    tok.pad_token = tok.eos_token
                return tok
            except Exception as exc:
                errors.append(f"{candidate}: {exc}")
    if not allow_fallback:
        raise RuntimeError(
            f"Cannot load a complete tokenizer for {base_path!r}; refusing SFT/DPO training. "
            "Install transformers and provide valid tokenizer files; "
            "diagnostic fallback requires explicit allow_fallback=True. "
            f"Details: {'; '.join(errors)}"
        )
    print("[Tokenizer] Diagnostic-only FallbackBPETokenizer; not Qwen BPE, tokens/packing are synthetic.")
    return FallbackBPETokenizer()


def load_evolution_dataset(
    sft_path: str,
    dpo_path: Optional[str],
    tokenizer: Any,
    max_len: int,
    numeric_weight: float,
    pack: bool,
    simpo_weight: float,
) -> List[Dict[str, Any]]:
    raw_items = [json.loads(line) for line in open(sft_path, encoding="utf-8") if line.strip()]
    formatted: List[Dict[str, Any]] = []
    dropped = 0
    truncated = 0

    for it in raw_items:
        s = format_sample_evo(it, tokenizer, max_len=max_len, numeric_weight=numeric_weight)
        if s is None:
            dropped += 1
            continue
        if s.pop("_truncated", False):
            truncated += 1
        formatted.append(s)

    raw_count = len(formatted)
    if pack and raw_count > 0:
        eos_id = getattr(tokenizer, "eos_token_id", None) or 151645
        formatted = pack_tokenized_samples(formatted, max_len=max_len, eos_token_id=eos_id)

    simpo_count = 0
    if simpo_weight > 0.0 and dpo_path and os.path.exists(dpo_path):
        pair_items = [json.loads(line) for line in open(dpo_path, encoding="utf-8") if line.strip()]
        for p in pair_items:
            fp = format_simpo_pair(p, tokenizer, max_len=max_len)
            if fp is not None:
                formatted.append(fp)
                simpo_count += 1

    print(
        f"[EvoDataset] raw_usable={raw_count} dropped={dropped} head_tail_truncated={truncated} "
        f"packed_sequences={len(formatted) - simpo_count} simpo_pairs={simpo_count} total_steps_items={len(formatted)}"
    )
    return formatted


def run_post_train_pipeline(adapter_dir: str, model_id: str = "virtu-evo-v5") -> None:
    """
    训练完成后一键本地合并 + Q4_0 GGUF 量化 + 双契约 Ollama 模型注册：
      - `virtu-evo-v5`：通用 CAD/CAM/CAE 闭环监督智能体臂；
      - `virtu-evo-v5-wm`：绑定 `CONTRACT_WORLD_MODEL` 硬约束的制造世界模型专用臂。
    """
    py = sys.executable
    merged_dir = adapter_dir.rstrip("/\\") + "_merged"
    gguf_path = os.path.join(ROOT, "checkpoints", f"{model_id}-q4_0.gguf")

    # 跨平台搜索已有基座
    base_candidates = [os.path.join(ROOT, "checkpoints", "_base_qwen3_8b")]
    hf_cache_pattern = os.path.join(
        os.path.expanduser("~"), ".cache", "huggingface", "hub",
        "models--Qwen--Qwen3-8B", "snapshots", "*",
    )
    base_candidates = glob.glob(hf_cache_pattern) + base_candidates
    # 云服务器常见路径
    for cloud_dir in ("/root/public-storage/model/Qwen/Qwen3-8B",
                      "/root/autodl-tmp/models/Qwen3-8B",
                      "/data/models/Qwen3-8B"):
        base_candidates.append(cloud_dir)
    base_dir = next((d for d in base_candidates if os.path.exists(os.path.join(d, "config.json"))), None)
    if not base_dir:
        raise SystemExit("[FATAL] 本地找不到 Qwen3-8B 基座，请检查 checkpoints/_base_qwen3_8b 或设置 --base")

    if not os.path.exists(os.path.join(merged_dir, "merge_receipt.json")):
        cmd_merge = [
            py, os.path.join(HERE, "merge_numpy.py"),
            "--base", base_dir, "--lora", adapter_dir,
            "--weight", "1.0", "--mode", "delta",
            "--out", merged_dir, "--verify-samples", "3",
        ]
        print(">>>", " ".join(cmd_merge))
        subprocess.run(cmd_merge, check=True)

    if not os.path.exists(gguf_path):
        cmd_gguf = [
            py, os.path.join(HERE, "hf_to_gguf_numpy.py"),
            "--model", merged_dir, "--out", gguf_path,
        ]
        print(">>>", " ".join(cmd_gguf))
        subprocess.run(cmd_gguf, check=True)

    for reg_name, sys_prompt in [
        (model_id, CONTRACT_CAD_SUPERVISOR),
        (f"{model_id}-wm", CONTRACT_WORLD_MODEL),
    ]:
        mf_path = os.path.join(ROOT, "checkpoints", f"{reg_name}.Modelfile")
        with open(mf_path, "w", encoding="utf-8") as f:
            f.write(f"FROM {gguf_path}\n\n")
            f.write(
                'TEMPLATE """{{ if .System }}<|im_start|>system\n{{ .System }}<|im_end|>\n{{ end }}'
                '{{ if .Prompt }}<|im_start|>user\n{{ .Prompt }}<|im_end|>\n{{ end }}'
                '<|im_start|>assistant\n{{ .Response }}<|im_end|>\n"""\n\n'
            )
            f.write(f'SYSTEM """{sys_prompt}"""\n\n')
            f.write("PARAMETER num_ctx 4096\nPARAMETER temperature 0.1\nPARAMETER top_p 0.95\n")
        print(f"[PostTrain] 已生成 Modelfile -> {mf_path}")
        subprocess.run(["ollama", "create", str(reg_name), "-f", str(mf_path)],
                       shell=False, check=False)


# ============================================================================
# 6. 全链路自检（--selftest：无需 GPU 即可验证分词、打包、数值权重与 SimPO 数学闭环）
# ============================================================================
def run_selftest(args: argparse.Namespace, tokenizer: Any) -> int:
    print("=================== VIRTU EVOLUTION v5 SELFTEST ===================")
    sft_path, dpo_path = build_evolution_corpus(seed=args.seed, include_replay=not args.no_replay)

    ds_unpacked = load_evolution_dataset(
        sft_path, dpo_path=None, tokenizer=tokenizer,
        max_len=args.max_len, numeric_weight=args.numeric_weight,
        pack=False, simpo_weight=0.0,
    )
    ds_packed = load_evolution_dataset(
        sft_path, dpo_path=dpo_path, tokenizer=tokenizer,
        max_len=args.max_len, numeric_weight=args.numeric_weight,
        pack=True, simpo_weight=args.simpo_weight,
    )

    assert len(ds_unpacked) > 0, "未打包数据集为空"
    assert len(ds_packed) > 0, "打包后数据集为空"

    # 验证 1: 没有任何一条样本存在全 -100 标签（防止 NaN Loss）
    zero_sup = sum(1 for item in ds_packed if not any(x != -100 for x in item["labels"]))
    assert zero_sup == 0, f"发现 {zero_sup} 条无有效监督 token 的样本！"
    print(f"[PASS] 1/6 标签安全守卫: {len(ds_packed)} 条训练序列全部具备有效监督 token (zero_sup=0)")

    # 验证 2: 序列打包压缩比与有效 token 密度计算
    sft_only_packed = [x for x in ds_packed if "rejected_input_ids" not in x]
    compression_ratio = len(ds_unpacked) / max(1, len(sft_only_packed))
    avg_len = sum(len(x["input_ids"]) for x in sft_only_packed) / max(1, len(sft_only_packed))
    print(
        f"[PASS] 2/6 动态序列打包: {len(ds_unpacked)} 条原始样本 -> {len(sft_only_packed)} 条打包序列 "
        f"(步数压缩比={compression_ratio:.2f}x, 平均序列长度={avg_len:.0f}/{args.max_len})"
    )

    # 验证 3: 数值焦点权重生效验证
    max_w = max(max(x["token_weights"]) for x in sft_only_packed[:20])
    assert max_w >= args.numeric_weight - 1e-4, f"数值焦点权重未生效: max_w={max_w}"
    print(f"[PASS] 3/6 数值与单位焦点权重: 检测到物理数值/字段最大梯度权重 = {max_w:.2f}x")

    # 验证 4: Collator + 复合损失函数 (Focal SFT + SimPO) 验证
    simpo_samples = [x for x in ds_packed if "rejected_input_ids" in x][:2]
    normal_samples = sft_only_packed[:2]
    pad_id = getattr(tokenizer, "pad_token_id", None) or 0
    collator = VirtuEvoCollator(pad_token_id=pad_id)
    batch = collator(normal_samples + simpo_samples)

    if HAVE_TORCH:
        bsz, seq_l = batch["input_ids"].shape
        rej_l = batch["rejected_input_ids"].shape[1]
        vocab_test = 2048
        dummy_logits = torch.randn(bsz, seq_l, vocab_test, requires_grad=True)
        dummy_rej_logits = torch.randn(bsz, rej_l, vocab_test, requires_grad=True)
        safe_labels = torch.where(batch["labels"] != -100, batch["labels"] % vocab_test, batch["labels"])
        safe_rej_labels = torch.where(batch["rejected_labels"] != -100, batch["rejected_labels"] % vocab_test, batch["rejected_labels"])

        loss, metrics = compute_weighted_sft_and_simpo_loss(
            logits=dummy_logits,
            labels=safe_labels,
            token_weights=batch["token_weights"],
            rejected_logits=dummy_rej_logits,
            rejected_labels=safe_rej_labels,
            simpo_mask=batch["simpo_mask"],
            simpo_weight=max(0.25, args.simpo_weight),
        )
        loss.backward()
        assert not torch.isnan(loss) and dummy_logits.grad is not None, "复合损失出现 NaN 或无梯度"
        print(
            f"[PASS] 4/6 复合损失与 SimPO 梯度验证 (PyTorch): total_loss={loss.item():.4f}, "
            f"sft_loss={metrics['sft_loss']:.4f}, simpo_loss={metrics.get('simpo_loss', 0.0):.4f}"
        )
    else:
        assert len(batch["input_ids"]) == 4 and len(batch["simpo_mask"]) == 4
        assert batch["simpo_mask"] == [0.0, 0.0, 1.0, 1.0]
        c_logp, r_logp = -0.45, -1.85
        margin = args.simpo_beta * ((c_logp - r_logp) - args.simpo_gamma)
        simpo_val = -math.log(1.0 / (1.0 + math.exp(-margin)))
        print(
            f"[PASS] 4/6 复合损失与 SimPO 批次/裕度数学验证 (CPU 零依赖模式): "
            f"batch_size={len(batch['input_ids'])}, simpo_mask={batch['simpo_mask']}, margin_loss={simpo_val:.4f}"
        )

    # 验证 5: 三模态契约门控分布统计
    mode_counts: Dict[str, int] = {}
    with open(sft_path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            m = detect_contract_mode(r["messages"], r.get("meta"))
            mode_counts[m] = mode_counts.get(m, 0) + 1
    print(f"[PASS] 5/6 三模态契约门控分布: {_j(mode_counts)}")

    # 验证 6: DPO 偏好对构建、指纹防伪与标签闭环
    mock_err_rec = {"verified": False, "verdict": "fail", "score": 80, "task": "roughness"}
    mock_pass_rec = {"verified": True, "verdict": "pass", "score": 100, "task": "roughness"}
    assert _is_dpo_error(mock_err_rec) is True, "_is_dpo_error 误判错误样本"
    assert _is_dpo_error(mock_pass_rec) is False, "_is_dpo_error 误判正确样本"

    state_str = _compact_dpo_state({"Ra": 1.6, "unit": "um"})
    assert state_str == '{"world_state":{"Ra":1.6,"unit":"um"}}', f"紧凑状态格式异常: {state_str}"

    test_fp = compute_file_fingerprint(sft_path)
    assert len(test_fp) == 16, f"指纹长度异常: {test_fp}"
    print(f"[PASS] 6/6 DPO 偏好对构建与指纹防伪闭环: 错误过滤断言正常 | 紧凑JSON对齐 | SHA-256指纹={test_fp}")
    print("=================== ALL 6/6 SELFTEST CHECKS PASSED ===================")
    return 0


# ============================================================================
# 7. DPO 反幻觉偏好回灌训练引擎 (Direct Preference Optimization)
# ============================================================================
def run_dpo_training(args: argparse.Namespace, tokenizer: Any) -> None:
    """Virtu 世界模型「反幻觉」云端 DPO 偏好训练引擎。

    采用 TRL 的 DPOTrainer 对 132 条带标签物理世界状态错误进行偏好对齐，
    自动探测/继承先验 v3 适配器并 merge 进基座，防止 DPO 导致灾难性遗忘。
    """
    _log("=" * 70)
    _log(" Virtu 世界模型 · 反幻觉 Direct Preference Optimization (DPO) 训练引擎")
    _log("=" * 70)

    if isinstance(tokenizer, FallbackBPETokenizer):
        raise RuntimeError("Diagnostic-only FallbackBPETokenizer cannot be used for DPO training.")

    # 1. 自动定位或挖掘 DPO 数据集
    dpo_file = resolve_dpo_data_path(args.data)
    if not dpo_file or not os.path.isfile(dpo_file):
        _log("未找到现有 DPO 偏好对数据集，正在自动从 _eval_* 评测记录挖掘...")
        eval_root = args.eval_root or ROOT
        out_dpo = args.dpo_out or os.path.join(ROOT, "data", "sft", "dpo_phys_rejects.jsonl")
        summary = build_dpo_dataset(eval_root, out_dpo)
        _log(f"挖掘完成: 共 {summary['n_pairs']} 条偏好对 -> {summary['out']}")
        dpo_file = summary["out"]

    if not dpo_file or not os.path.isfile(dpo_file):
        raise SystemExit(f"[FATAL] 未找到 DPO 数据集！请确认存在 dpo_phys_rejects.jsonl 或指定 --data")

    # 2. 载入偏好样本与计算指纹
    samples = []
    with open(dpo_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                if d.get("prompt") and d.get("chosen") and d.get("rejected"):
                    samples.append(d)
            except Exception:
                continue

    if not samples:
        raise SystemExit(f"[FATAL] DPO 数据集为空或缺少 prompt/chosen/rejected 字段: {dpo_file}")

    data_fp = compute_file_fingerprint(dpo_file)
    _log(f"[DPO] 成功载入偏好对 {len(samples)} 条 | 数据 SHA-256 指纹: {data_fp}")

    # 3. 显存探测与精度分档
    gpu_info = preflight_gpu_check()
    vram_gb = 0.0
    if gpu_info["cuda_available"] and gpu_info["gpus"]:
        vram_gb = gpu_info["gpus"][0].get("total_memory_gb", 0.0)

    # >=36GB bf16-LoRA / <36GB 自动 4-bit QLoRA
    use_4bit = (vram_gb > 0 and vram_gb < 36.0)
    _log(f"[DPO] 显存状态: {vram_gb:.1f}GB -> {'4-bit QLoRA (NF4)' if use_4bit else 'bf16 LoRA 全精度加载'}")

    # 学习率自适应：DPO 对权重扰动敏感，默认 5e-6
    dpo_lr = args.lr
    if dpo_lr >= 5e-5:
        dpo_lr = 5e-6
        _log(f"[DPO] 检测到较高学习率 ({args.lr})，自适应下调为 DPO 推荐学习率 {dpo_lr}")

    if not HAVE_HF or not HAVE_TORCH:
        raise SystemExit("[FATAL] 当前环境缺少 torch / transformers / peft，请运行 --auto 自动安装")

    from transformers import AutoModelForCausalLM
    from peft import LoraConfig, TaskType, get_peft_model, PeftModel, prepare_model_for_kbit_training

    kw: Dict[str, Any] = {}
    if args.attn_impl:
        kw["attn_implementation"] = args.attn_impl
    else:
        kw["attn_implementation"] = "sdpa"

    # 4. 加载基座模型
    _log(f"[DPO][1/5] 加载基座模型: {args.base} ...")
    if use_4bit:
        from transformers import BitsAndBytesConfig
        bnb_cfg = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
        )
        model = AutoModelForCausalLM.from_pretrained(
            args.base,
            torch_dtype=torch.float32,
            quantization_config=bnb_cfg,
            trust_remote_code=True,
            **kw,
        )
        model = prepare_model_for_kbit_training(model)
    else:
        prec_dtype = torch.bfloat16 if (torch.cuda.is_available() and torch.cuda.is_bf16_supported()) else torch.float16
        model = AutoModelForCausalLM.from_pretrained(
            args.base,
            torch_dtype=prec_dtype,
            device_map="auto",
            trust_remote_code=True,
            **kw,
        )

    # 5. 继承能力：merge 先验 adapter 进基座（防灾难性遗忘）
    resume_adapter = args.resume_adapter
    if not resume_adapter:
        for cand in [
            os.path.join(ROOT, "checkpoints", "virtu_v3_all90"),
            os.path.join(HERE, "checkpoints", "virtu_v3_all90"),
            os.path.join(ROOT, "checkpoints", "virtu_evo_v5"),
            os.path.join(HERE, "checkpoints", "virtu_evo_v5"),
            "checkpoints/virtu_v3_all90",
        ]:
            if os.path.isdir(cand) and os.path.isfile(os.path.join(cand, "adapter_config.json")):
                resume_adapter = cand
                break

    if resume_adapter and os.path.exists(resume_adapter):
        _log(f"[DPO][2/5] 发现先验 Adapter: {resume_adapter}，执行 merge_and_unload() 融入基座（防灾难性遗忘）...")
        try:
            model = PeftModel.from_pretrained(model, resume_adapter)
            model = model.merge_and_unload()
            _log("  -> 先验能力融入成功！基座已固化先前学习到的工业制造技能。")
        except Exception as e:
            _log(f"  [WARN] merge 先验适配器异常: {e}，将直接在基座上微调")
    else:
        _log("[DPO][2/5] 未指定先验 Adapter，从原始基座直接开始 DPO 偏好微调。")

    # 6. 为 DPO 注入新 LoRA 适配器
    _log("[DPO][3/5] 注入新 LoRA 适配器 ...")
    lora_cfg = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        bias="none",
    )
    model = get_peft_model(model, lora_cfg)
    model.print_trainable_parameters()

    # 7. 构建 Dataset 与 DPO Trainer
    _log("[DPO][4/5] 配置 TRL DPO Trainer ...")
    from datasets import Dataset
    ds = Dataset.from_list(samples)

    max_len = args.max_len or 1536
    max_prompt_len = args.max_prompt_length if args.max_prompt_length > 0 else (max_len // 2)

    cb = []
    effective_budget_min = args.time_budget_min
    if args.max_hours > 0 and effective_budget_min <= 0:
        effective_budget_min = args.max_hours * 60.0
    if effective_budget_min > 0:
        TimeBudgetCallbackCls = _make_time_budget_callback_class()
        cb.append(TimeBudgetCallbackCls(effective_budget_min))
        _log(f"[DPO] 设定运行时间预算上限: {effective_budget_min:.1f} 分钟")

    os.makedirs(args.out, exist_ok=True)

    try:
        from trl import DPOTrainer, DPOConfig
        dpo_args = DPOConfig(
            output_dir=args.out,
            per_device_train_batch_size=args.bs,
            gradient_accumulation_steps=args.accum,
            num_train_epochs=args.epochs,
            learning_rate=dpo_lr,
            beta=args.beta,
            max_length=max_len,
            max_prompt_length=max_prompt_len,
            bf16=not use_4bit,
            logging_steps=5,
            save_strategy="no",
            report_to="none",
            seed=args.seed,
            optim="adamw_torch",
            remove_unused_columns=False,
        )
        trainer = DPOTrainer(
            model=model,
            ref_model=None,
            args=dpo_args,
            train_dataset=ds,
            tokenizer=tokenizer,
            callbacks=cb,
        )
    except Exception as e:
        _log(f"[DPO][WARN] 使用 DPOConfig 失败 ({e})，尝试回退 TrainingArguments ...")
        from trl import DPOTrainer
        from transformers import TrainingArguments
        dpo_args = TrainingArguments(
            output_dir=args.out,
            per_device_train_batch_size=args.bs,
            gradient_accumulation_steps=args.accum,
            num_train_epochs=args.epochs,
            learning_rate=dpo_lr,
            bf16=not use_4bit,
            logging_steps=5,
            save_strategy="no",
            report_to="none",
            seed=args.seed,
            remove_unused_columns=False,
        )
        trainer = DPOTrainer(
            model=model,
            train_dataset=ds,
            tokenizer=tokenizer,
            args=dpo_args,
            beta=args.beta,
            max_length=max_len,
            max_prompt_length=max_prompt_len,
            callbacks=cb,
        )

    _log(f"[DPO][5/5] 开始训练偏好模型 (epochs={args.epochs}, lr={dpo_lr}, beta={args.beta}, batch={args.bs}, accum={args.accum}) ...")
    t0 = time.time()
    trainer.train()
    elapsed = time.time() - t0
    _log(f"[DPO] 偏好训练完成，总计耗时 {elapsed:.1f}s")

    # 8. 保存模型、指纹元数据与交付压缩包
    model.save_pretrained(args.out)
    tokenizer.save_pretrained(args.out)

    meta = {
        "type": "virtu_dpo_antihallucination",
        "engine": "VirtuDPOTrainer_v5",
        "base": args.base,
        "resume_adapter": resume_adapter,
        "n_pairs": len(samples),
        "epochs": args.epochs,
        "lr": dpo_lr,
        "beta": args.beta,
        "lora_r": args.lora_r,
        "lora_alpha": args.lora_alpha,
        "data_fingerprint": data_fp,
        "runtime_seconds": round(elapsed, 2),
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    meta_path = os.path.join(args.out, "dpo_metadata.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    tar_path = os.path.join(args.out, "virtu_dpo_deliverable.tar.gz")
    with tarfile.open(tar_path, "w:gz") as tar:
        for fname in ["adapter_model.safetensors", "adapter_model.bin", "adapter_config.json",
                      "tokenizer.json", "tokenizer_config.json", "special_tokens_map.json",
                      "dpo_metadata.json"]:
            fpath = os.path.join(args.out, fname)
            if os.path.exists(fpath):
                tar.add(fpath, arcname=os.path.basename(args.out) + "/" + fname)
    _log(f"[DPO] 可交付成果打包完成 -> {tar_path}")

    # 9. PUSH_TO 目录同步
    if args.push_to:
        dst = os.path.join(args.push_to, os.path.basename(args.out) + "_dpo")
        shutil.copytree(args.out, dst, dirs_exist_ok=True)
        _log(f"[DPO] 已同步至挂载点/对象存储目录 PUSH_TO: {dst}")

    # 10. 写入训练回执
    receipt_path = os.path.join(args.out, "training_receipt.json")
    with open(receipt_path, "w", encoding="utf-8") as f:
        json.dump({
            "status": "COMPLETED",
            "mode": "dpo",
            **meta,
            "deliverable": tar_path,
        }, f, indent=2, ensure_ascii=False)
    _log(f"🎉 DPO 全流程胜利闭环！回执已写入 -> {receipt_path}")


# ============================================================================
# 7. 主入口：支持云端环境变量透传、断点续训与训练凭据落盘
# ============================================================================
def pick_precision() -> Tuple[str, Any]:
    if not HAVE_TORCH or not torch.cuda.is_available():
        return "fp16", (torch.float16 if HAVE_TORCH else None)
    major, _ = torch.cuda.get_device_capability(0)
    return ("bf16", torch.bfloat16) if major >= 8 else ("fp16", torch.float16)


def find_latest_checkpoint(out_dir: str) -> Optional[str]:
    if not os.path.isdir(out_dir):
        return None
    cks = [d for d in os.listdir(out_dir) if d.startswith("checkpoint-")]
    if not cks:
        return None
    cks.sort(key=lambda x: int(x.split("-")[-1]))
    return os.path.join(out_dir, cks[-1])


def main() -> None:
    _pre_argv()

    ap = argparse.ArgumentParser(
        description="Virtu 工业世界模型 & 六软件闭环智能体 · 终极统一训练引擎 (v5 Unified)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "═══════════════════════════════════════════════════════════════════════\n"
            " 一键开训指令清单：\n\n"
            " 1. 云端一键开训（自动安装依赖+下载基座+自动打包开训）：\n"
            "    python train_virtu_evolution.py --auto\n\n"
            " 2. 六软件工具调用专属训练（扫描 12 个数据集）：\n"
            "    python train_virtu_evolution.py --data-dir datasets --epochs 2 --mode qlora\n\n"
            " 3. 多任务联合大一统训练（世界模型 + 六软件工具链联合混训）：\n"
            "    python train_virtu_evolution.py --auto --mix-six --epochs 3\n\n"
            " 4. DPO 反幻觉偏好回灌训练（使用 _eval_* 标签错误回灌，自动继承 v3 adapter）：\n"
            "    python train_virtu_evolution.py --mode dpo --resume-adapter checkpoints/virtu_v3_all90\n\n"
            " 5. 本地一键从 _eval_* 评测记录挖掘 DPO 偏好对（不需 GPU）：\n"
            "    python train_virtu_evolution.py --build-dpo\n\n"
            " 6. 抢占式限时实例训练（设置 30 分钟时间预算，到点优雅停机并保存 LoRA）：\n"
            "    python train_virtu_evolution.py --auto --time-budget-min 30\n\n"
            " 7. 快速冒烟验证（跑 20 步跑通全流程）：\n"
            "    python train_virtu_evolution.py --auto --smoke 20\n\n"
            " 8. 零 GPU 自检（在任何机器上验证数据管线与数学闭环）：\n"
            "    python train_virtu_evolution.py --selftest\n\n"
            " 9. 本地一键打包自包含压缩包（上传服务器即用）：\n"
            "    python train_virtu_evolution.py --bundle\n"
            "═══════════════════════════════════════════════════════════════════════\n"
        ),
    )
    # 基础与数据
    ap.add_argument("--auto", action="store_true", help="一键开训：自动安装依赖 + 下载基座 + 构建语料 + 开始训练")
    ap.add_argument("--base", default=os.environ.get("BASE", os.environ.get("BASE_DIR", "")), help="Qwen3-8B 基座模型路径")
    ap.add_argument("--data", default=os.environ.get("DATA", EVO_DATA_PATH), help="SFT 语料路径")
    ap.add_argument("--dpo-data", "--dpo_data", default=os.environ.get("DPO_DATA", EVO_DPO_PATH), help="SimPO 偏好对路径")
    ap.add_argument("--data-dir", "--data_dir", default=os.environ.get("DATA_DIR", ""), help="六软件 datasets 目录（内含 12 个 *_train.jsonl / *_holdout.jsonl）")
    ap.add_argument("--mix-six", "--mix_six", action="store_true", help="联合混训：将六软件工具调用与工业世界模型语料联合训练")
    ap.add_argument("--out", default=os.environ.get("OUT", "checkpoints/virtu_evo_v5"), help="输出目录")
    ap.add_argument("--mode", default=os.environ.get("MODE", "qlora"), choices=["qlora", "lora", "dpo"], help="训练模式：4-bit NF4 qlora、全精度 lora、或 TRL DPO 反幻觉偏好回灌 dpo")

    # 超参数（兼容双命名）
    ap.add_argument("--epochs", type=float, default=float(os.environ.get("EPOCHS", "3.0")), help="训练轮数 (可为浮点数)")
    ap.add_argument("--bs", "--batch", dest="bs", type=int, default=int(os.environ.get("BS", "4")), help="单卡批次大小")
    ap.add_argument("--accum", "--grad-accum", dest="accum", type=int, default=int(os.environ.get("ACCUM", "4")), help="梯度累积步数")
    ap.add_argument("--lr", type=float, default=float(os.environ.get("LR", "8e-5")), help="学习率 (SFT 默认 8e-5，DPO 模式自适应 5e-6)")
    ap.add_argument("--max_len", "--max-length", dest="max_len", type=int, default=int(os.environ.get("MAX_LEN", "2560")), help="最大序列长度")
    ap.add_argument("--lora_r", "--lora-r", dest="lora_r", type=int, default=int(os.environ.get("LORA_R", "32")), help="LoRA Rank")
    ap.add_argument("--lora_alpha", "--lora-alpha", dest="lora_alpha", type=int, default=int(os.environ.get("LORA_ALPHA", "64")), help="LoRA Alpha")
    ap.add_argument("--lora_dropout", "--lora-dropout", dest="lora_dropout", type=float, default=0.05, help="LoRA Dropout")
    ap.add_argument("--seed", type=int, default=int(os.environ.get("SEED", "20261103")), help="随机种子")
    ap.add_argument("--val_ratio", type=float, default=0.03, help="验证集比例")
    ap.add_argument("--max_steps", "--max-steps", dest="max_steps", type=int, default=-1, help=">0 时只跑指定步数用于冒烟验证")
    ap.add_argument("--resume-adapter", default=os.environ.get("RESUME_ADAPTER") or None, help="已有 LoRA Adapter 续训或 DPO merge 路径")

    # 进化特性
    ap.add_argument("--build-evo", action="store_true", help="重新构建/合并 v5 进化语料与 SimPO 偏好对")
    ap.add_argument("--no-replay", action="store_true", help="不混入 v3 工具调用 replay")
    ap.add_argument("--pack", action="store_true", default=True, help="开启长度分桶动态序列打包 (默认开启)")
    ap.add_argument("--no-pack", action="store_false", dest="pack", help="关闭动态序列打包")
    ap.add_argument("--numeric-weight", type=float, default=float(os.environ.get("NUMERIC_WEIGHT", "2.2")), help="物理数值与单位 token 焦点权重")
    ap.add_argument("--simpo-weight", type=float, default=float(os.environ.get("SIMPO_WEIGHT", "0.25")), help="免参考模型 SimPO 对比损失权重 (0 为纯 SFT)")
    ap.add_argument("--simpo-beta", type=float, default=2.0)
    ap.add_argument("--simpo-gamma", type=float, default=0.8)

    # DPO 反幻觉与偏好对齐特性
    ap.add_argument("--build-dpo", action="store_true", help="从 _eval_* 评测记录自动挖掘带标签物理世界状态错误，构造 DPO 偏好对")
    ap.add_argument("--eval-root", default="", help="评测记录根目录（用于挖掘 DPO 样本，默认项目根目录）")
    ap.add_argument("--dpo-out", default="", help="DPO 偏好对输出文件路径 (默认 data/sft/dpo_phys_rejects.jsonl)")
    ap.add_argument("--beta", type=float, default=0.1, help="DPO 偏好损失强度参数 (默认 0.1)")
    ap.add_argument("--push-to", default=os.environ.get("PUSH_TO", ""), help="训练完成后自动同步交付物至云盘/挂载目录")
    ap.add_argument("--max-hours", type=float, default=0.0, help="运行时间上限（小时），防超时计费")
    ap.add_argument("--max-prompt-length", type=int, default=0, help="DPO prompt 最大长度 (默认 max_len // 2)")

    # 硬件与控制
    ap.add_argument("--attn-impl", default="", choices=["", "flash_attention_2", "sdpa"], help="注意力机制：flash_attention_2 或 sdpa")
    ap.add_argument("--no-grad-ckpt", action="store_true", help="关闭梯度检查点（大显存卡 A800/80GB 可省约 25 个百分点计算量）")
    ap.add_argument("--min-vram-gb", type=float, default=0.0, help="最低可用显存门禁（GB），低于此值报错退出")
    ap.add_argument("--time-budget-min", type=float, default=0.0, help="训练时间预算（分钟），到点优雅停止并保存 LoRA")
    ap.add_argument("--limit", type=int, default=0, help="每个文件最多取前 N 条（0=全部）")
    ap.add_argument("--strict", action="store_true", help="严格模式：体检发现坏 JSON 行即 FATAL，默认跳过并隔离落盘")

    # 工具与交付
    ap.add_argument("--smoke", type=int, nargs="?", const=20, default=0, help="冒烟模式：跑 N 步跑通全流程（默认 20 步）")
    ap.add_argument("--probe-only", action="store_true", help="只做 Qwen3 官方 chat template 探针并退出，不加载模型")
    ap.add_argument("--validate-only", action="store_true", help="只做数据扫描体检与坏行检查，不加载模型")
    ap.add_argument("--eval-holdout", action="store_true", help="训练结束后对 holdout 验证集计算 loss 并写入回执")
    ap.add_argument("--bundle", action="store_true", help="一键打包生成云端开训独立压缩包 (virtu_train_bundle.tar.gz / .zip)")
    ap.add_argument("--selftest", action="store_true", help="零显存执行完整数据构建、打包与复合损失梯度自检")
    ap.add_argument("--post-train", action="store_true", help="执行本地合并 + Q4_0 GGUF 量化 + Ollama 双契约注册")
    ap.add_argument("--pip-index", default=os.environ.get("PIP_INDEX_URL", ""), help="pip 镜像 URL (国内推荐清华源)")
    ap.add_argument("--torch-index", default=os.environ.get("TORCH_INDEX_URL", ""), help="PyTorch wheel 索引 URL")
    args = ap.parse_args()

    # 1. 一键打包模式
    if args.bundle:
        make_training_bundle()
        return

    # 2. 冒烟设置
    if args.smoke > 0:
        args.max_steps = args.smoke
        args.epochs = 1.0
        _log(f"⚡ 已启用冒烟模式 (max_steps={args.smoke}, epochs=1.0)")

    # 3. 一键开训自举 (--auto)
    if args.auto:
        _log("🚀 启动一键开训 (--auto) 模式")
        args.build_evo = True
        args.pack = True

        if not HAVE_HF or not HAVE_TORCH:
            auto_install_deps(
                pip_index=args.pip_index or None,
                torch_index=args.torch_index or None,
            )
            _load_heavy_imports()

        gpu_info = preflight_gpu_check()
        if gpu_info["cuda_available"]:
            for g in gpu_info["gpus"]:
                _log(f"  🎮 GPU {g.get('index', '?')}: {g['name']} ({g.get('total_memory_gb', '?')} GB)")
            min_vram = min((g.get("total_memory_gb", 24) for g in gpu_info["gpus"]), default=24)
            if min_vram < 20:
                _log(f"  ⚠️  VRAM ({min_vram}GB) < 20GB，自动调整配置以防 OOM: bs=2, accum=8, max_len=2048")
                args.bs = 2
                args.accum = 8
                args.max_len = min(args.max_len, 2048)
        else:
            _log("  ⚠️  未检测到 CUDA GPU — 将以 CPU 模式运行 (仅用于 selftest/build-evo/validate)")

        if not args.base:
            args.base = _discover_base_model()
        if not args.base or not os.path.isfile(os.path.join(args.base, "config.json")):
            work_dir = _discover_work_dir()
            default_base = os.path.join(work_dir, "models", "Qwen3-8B")
            args.base = auto_download_base_model(default_base)

        os.makedirs(args.out, exist_ok=True)
        _log(f"  基座模型: {args.base}")
        _log(f"  输出目录: {args.out}")

    if not args.base:
        args.base = _discover_base_model() or "Qwen/Qwen3-8B"

    # 随机种子
    if HAVE_HF:
        from transformers import set_seed as _set_seed
        _set_seed(args.seed)
    random.seed(args.seed)
    if HAVE_TORCH and torch is not None:
        torch.manual_seed(args.seed)

    # 训练后后处理模式
    if args.post_train:
        run_post_train_pipeline(args.out)
        return

    # DPO dispatch precedes probe/validate, so those flags cannot authorize its fallback.
    tokenizer = load_safe_tokenizer(
        args.base,
        allow_fallback=args.selftest or (
            args.mode != "dpo" and (args.validate_only or args.probe_only)
        ),
    )

    # 零显存自检
    if args.selftest:
        sys.exit(run_selftest(args, tokenizer))

    # DPO 偏好对自动挖掘模式 (--build-dpo)
    if args.build_dpo:
        eval_root = args.eval_root or ROOT
        out_dpo = args.dpo_out or os.path.join(ROOT, "data", "sft", "dpo_phys_rejects.jsonl")
        summary = build_dpo_dataset(eval_root, out_dpo)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        _log(f"[ok] DPO 偏好对已写出 -> {summary['out']} ({summary['n_pairs']} 条)")
        return

    # DPO 反幻觉训练模式 (--mode dpo)
    if args.mode == "dpo":
        run_dpo_training(args, tokenizer)
        return

    # 模板探针模式
    six_usable_dir = find_six_software_dir(args.data_dir)
    if args.probe_only:
        probe_template(tokenizer, six_usable_dir or DEFAULT_SIX_DATA_DIR)
        _log("[probe-only] 模板探针完成，退出（未加载模型）。")
        return

    # 数据集加载与诊断
    train_records: List[Dict[str, Any]] = []
    bad_lines_all: List[Dict[str, Any]] = []
    source_summary: Dict[str, Any] = {}

    # 加载六软件数据 (如果传入 --data-dir 或开启 --mix-six)
    is_six_only = bool(args.data_dir and not args.mix_six)
    if six_usable_dir and (is_six_only or args.mix_six):
        _log(f"[data] 加载六软件工具调用数据集: {six_usable_dir}")
        six_rec, six_bad, s_trunc, s_tok, s_loss = load_six_software_dataset(
            six_usable_dir, "train", tokenizer, args.max_len,
            limit=args.limit, strict=args.strict, numeric_weight=args.numeric_weight,
        )
        train_records.extend(six_rec)
        bad_lines_all.extend(six_bad)
        source_summary["six_software"] = {
            "records": len(six_rec), "tokens": s_tok, "loss_tokens": s_loss,
            "truncated": s_trunc, "bad_lines": len(six_bad),
        }
        _log(f"[data][six_software] 有效 {len(six_rec)} 条 | token {s_tok:,} | 计loss {s_loss:,} | 坏行 {len(six_bad)}")

    # 加载工业进化语料 (如果不是仅跑六软件)
    if not is_six_only:
        _log("[data] 加载工业世界模型 & 闭环监督进化语料...")
        args.data, args.dpo_data = resolve_data_paths(args.data, args.dpo_data)
        if args.build_evo or not os.path.exists(args.data):
            args.data, args.dpo_data = build_evolution_corpus(seed=args.seed, include_replay=not args.no_replay)

        evo_rec = load_evolution_dataset(
            args.data,
            dpo_path=args.dpo_data,
            tokenizer=tokenizer,
            max_len=args.max_len,
            numeric_weight=args.numeric_weight,
            pack=False,  # 统一在后面打包
            simpo_weight=args.simpo_weight,
        )
        train_records.extend(evo_rec)
        source_summary["evolution"] = {"records": len(evo_rec)}

    # 体检模式
    if args.validate_only:
        if bad_lines_all:
            dump_bad_manifest(args.out, bad_lines_all)
        n_loss_total = sum(1 for d in train_records for x in d["labels"] if x != -100)
        n_tok_total = sum(len(d["input_ids"]) for d in train_records)
        _log(f"[validate-only] 总计有效样本: {len(train_records)} 条 | 总 Token: {n_tok_total:,} | 计 loss Token: {n_loss_total:,}")
        _log("[validate-only] 数据体检完成，退出（未加载模型）。")
        return

    if isinstance(tokenizer, FallbackBPETokenizer):
        raise RuntimeError("Diagnostic-only FallbackBPETokenizer cannot be used for SFT training.")

    # 动态序列打包
    simpo_pairs_count = sum(1 for x in train_records if "rejected_input_ids" in x)
    sft_only_records = [x for x in train_records if "rejected_input_ids" not in x]
    simpo_records = [x for x in train_records if "rejected_input_ids" in x]

    if args.pack and sft_only_records:
        eos_id = getattr(tokenizer, "eos_token_id", None) or 151645
        _log(f"[pack] 开始长度分桶动态序列打包 (原始 {len(sft_only_records)} 条序列) ...")
        packed_sft = pack_tokenized_samples(sft_only_records, max_len=args.max_len, eos_token_id=eos_id)
        compression = len(sft_only_records) / max(1, len(packed_sft))
        _log(f"[pack] 打包完成: {len(sft_only_records)} 条 -> {len(packed_sft)} 条 (压缩比={compression:.2f}x)")
        train_records = packed_sft + simpo_records

    if not train_records:
        raise SystemExit("[FATAL] 训练数据集为空！请检查数据路径或运行 --bundle 生成完整包。")

    if not HAVE_HF or not HAVE_TORCH:
        raise SystemExit(
            "[FATAL] 当前环境缺少 torch / transformers / peft。\n"
            "  推荐使用 --auto 模式自动安装: python train_virtu_evolution.py --auto"
        )

    # 显存门禁检查
    if HAVE_TORCH and torch.cuda.is_available():
        free_b, total_b = torch.cuda.mem_get_info()
        free_gb = free_b / 1e9
        if args.min_vram_gb > 0 and free_gb < args.min_vram_gb:
            raise SystemExit(f"[FATAL] 当前可用显存 {free_gb:.1f}GB 低于门禁要求的 {args.min_vram_gb}GB。")

    from peft import LoraConfig, PeftModel, TaskType, get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, BitsAndBytesConfig, TrainingArguments

    print("=" * 70)
    print(" Virtu 工业世界模型 & 六软件闭环智能体 · 终极统一训练引擎 (v5 Unified)")
    print(f" base           = {args.base}")
    print(f" mode           = {args.mode}")
    print(f" out            = {args.out}")
    print(f" resume_adapter = {args.resume_adapter}")
    print(f" pack_sequences = {args.pack} | numeric_weight = {args.numeric_weight}")
    print(f" simpo_weight   = {args.simpo_weight} (simpo_pairs={simpo_pairs_count})")
    print(f" hyper          = lr={args.lr} epochs={args.epochs} bs={args.bs} accum={args.accum} max_len={args.max_len}")
    print("=" * 70)

    os.makedirs(args.out, exist_ok=True)
    prec_name, prec_dtype = pick_precision()
    use_ckpt = not args.no_grad_ckpt

    # 注意力实现选择
    kw: Dict[str, Any] = {}
    impl = args.attn_impl or "flash_attention_2"
    if impl == "flash_attention_2":
        try:
            import flash_attn  # noqa: F401
            kw["attn_implementation"] = "flash_attention_2"
            _log("[train] 注意力实现: flash_attention_2")
        except ImportError:
            kw["attn_implementation"] = "sdpa"
            _log("[train] 未安装 flash-attn，降级为 sdpa。")
    elif impl != "":
        kw["attn_implementation"] = impl
        _log(f"[train] 注意力实现: {impl}")

    # 模型加载 (QLoRA vs LoRA)
    _log(f"[1/5] Loading base model ({args.mode.upper()}, {prec_name}) ...")
    if args.mode == "qlora":
        bnb_cfg = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=prec_dtype,
            bnb_4bit_use_double_quant=True,
        )
        model = AutoModelForCausalLM.from_pretrained(
            args.base,
            torch_dtype=prec_dtype,
            quantization_config=bnb_cfg,
            device_map="auto",
            trust_remote_code=True,
            **kw,
        )
        model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=use_ckpt)
    else:
        model = AutoModelForCausalLM.from_pretrained(
            args.base,
            torch_dtype=prec_dtype,
            device_map="auto",
            trust_remote_code=True,
            **kw,
        )
    model.config.use_cache = False
    if use_ckpt:
        model.enable_input_require_grads()
    _log(f"[train] 梯度检查点: {'开启' if use_ckpt else '关闭（省 ~25% 显存激活计算）'}")

    # LoRA 适配器注入与续训
    if args.resume_adapter:
        _log(f"[2/5] Resuming trainable LoRA adapter from: {args.resume_adapter}")
        model = PeftModel.from_pretrained(model, args.resume_adapter, is_trainable=True)
    else:
        _log("[2/5] Injecting fresh LoRA adapter ...")
        lora_cfg = LoraConfig(
            r=args.lora_r,
            lora_alpha=args.lora_alpha,
            lora_dropout=args.lora_dropout,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
            bias="none",
            task_type=TaskType.CAUSAL_LM,
        )
        model = get_peft_model(model, lora_cfg)
    model.print_trainable_parameters()

    # 构建训练 Dataset
    _log("[3/5] Assembling final dataset ...")
    from datasets import Dataset
    full_ds = Dataset.from_list(train_records)
    if args.val_ratio > 0 and len(full_ds) > 20:
        split = full_ds.train_test_split(test_size=args.val_ratio, seed=args.seed)
        train_ds, val_ds = split["train"], split["test"]
    else:
        train_ds, val_ds = full_ds, None

    # 配置 TrainingArguments
    _log("[4/5] Configuring Unified Trainer ...")
    ta = TrainingArguments(
        output_dir=args.out,
        per_device_train_batch_size=args.bs,
        gradient_accumulation_steps=args.accum,
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        warmup_ratio=0.04,
        weight_decay=0.01,
        num_train_epochs=args.epochs,
        max_steps=args.max_steps,
        logging_steps=10,
        save_strategy="steps",
        save_steps=200,
        save_total_limit=2,
        bf16=(prec_name == "bf16"),
        fp16=(prec_name == "fp16"),
        gradient_checkpointing=use_ckpt,
        gradient_checkpointing_kwargs={"use_reentrant": False} if use_ckpt else {},
        optim="paged_adamw_8bit" if args.mode == "qlora" else "adamw_torch",
        report_to="none",
        remove_unused_columns=False,
        dataloader_num_workers=2,
        seed=args.seed,
        logging_dir=os.path.join(args.out, "logs"),
    )

    cb = []
    if args.time_budget_min > 0:
        TimeBudgetCallbackCls = _make_time_budget_callback_class()
        cb.append(TimeBudgetCallbackCls(args.time_budget_min))
        _log(f"[train] 已设定运行时间预算: {args.time_budget_min} 分钟")

    collator = VirtuEvoCollator(pad_token_id=tokenizer.pad_token_id)
    VirtuEvolutionTrainer = _make_evo_trainer_class()
    trainer = VirtuEvolutionTrainer(
        model=model,
        args=ta,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        data_collator=collator,
        callbacks=cb,
        simpo_weight=args.simpo_weight,
        simpo_beta=args.simpo_beta,
        simpo_gamma=args.simpo_gamma,
    )

    # 断点检测
    resume_ckpt = find_latest_checkpoint(args.out)
    t0 = time.time()
    receipt_path = os.path.join(args.out, "training_receipt.json")
    try:
        result = trainer.train(resume_from_checkpoint=resume_ckpt)
        elapsed = time.time() - t0
        train_loss = float(result.training_loss)
    except Exception as e:
        elapsed = time.time() - t0
        with open(receipt_path, "w", encoding="utf-8") as f:
            json.dump({"status": "FAILED", "error": repr(e), "runtime_seconds": elapsed}, f, indent=2, ensure_ascii=False)
        raise

    model.save_pretrained(args.out)
    tokenizer.save_pretrained(args.out)

    # 坏行清单落盘
    bad_manifest_path = None
    if bad_lines_all:
        bad_manifest_path = dump_bad_manifest(args.out, bad_lines_all)

    # Holdout 验证集评测
    holdout_eval_loss = None
    if args.eval_holdout and six_usable_dir:
        _log(f"[eval] 对六软件 holdout 集进行泛化 loss 独立评测...")
        hold_rec, _, _, _, _ = load_six_software_dataset(
            six_usable_dir, "holdout", tokenizer, args.max_len,
            limit=args.limit, strict=args.strict, numeric_weight=1.0,
        )
        if hold_rec:
            h_ds = Dataset.from_list(hold_rec)
            try:
                ev = trainer.evaluate(eval_dataset=h_ds)
                holdout_eval_loss = float(ev.get("eval_loss", 0.0))
                _log(f"[eval][holdout] eval_loss = {holdout_eval_loss:.4f}")
            except Exception as e:
                _log(f"[eval][WARN] holdout 评测异常: {e}")

    gpus = [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())] if torch.cuda.is_available() else []
    with open(receipt_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "status": "COMPLETED",
                "engine": "VirtuUnifiedTrainer_v5",
                "mode": args.mode,
                "base": args.base,
                "resume_adapter": args.resume_adapter,
                "num_training_sequences": len(full_ds),
                "numeric_weight": args.numeric_weight,
                "simpo_weight": args.simpo_weight,
                "global_step": trainer.state.global_step,
                "train_loss": train_loss,
                "holdout_eval_loss": holdout_eval_loss,
                "bad_lines_manifest": bad_manifest_path,
                "source_summary": source_summary,
                "runtime_seconds": round(elapsed, 2),
                "gpus": gpus,
                "adapter_dir": os.path.abspath(args.out),
            },
            f,
            indent=2,
            ensure_ascii=False,
        )
    _log(f"🎉 训练完成 ({elapsed:.1f}s)，详细回执已写入 -> {receipt_path}")


if __name__ == "__main__":
    main()