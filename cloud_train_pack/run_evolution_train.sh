#!/usr/bin/env bash
# =============================================================================
# run_evolution_train.sh — Virtu 工业大模型·云端进化版全流程训练一键入口
# -----------------------------------------------------------------------------
# 适用平台：AutoDL / 丹摩 Damodel / 恒源云 / RunPod / Lambda / 阿里云 / 腾讯云 / 本地算力
# 适用显卡：Tesla V100 32G (fp16)、L40S 48G (bf16)、A100/H100 80G (bf16)、RTX 3090/4090 24G
#
# 特性保证：
#   1. 自动环境探测与国内镜像 (清华/阿里源) 依赖极速补齐；
#   2. 自动集成 6,099 条强化语料 (5x 物理弱项 + 5x 多语言代码防御)；
#   3. 前置严格通过 virtu_eval 防污染审查 (0 泄漏保证)；
#   4. 阶段 1 QLoRA SFT (r=32 / alpha=64) + 阶段 2 DPO 反幻觉与防御对齐；
#   5. 阶段 3 原地全维度评测验收 + 阶段 4 标准 Delta 权重合并；
#   6. 自动导出注入官方 1723 字符工具调用模版的 Modelfile，彻底修复历史 400 缺陷；
#   7. 生成 GGUF 量化产物并打包带 SHA-256 账本的交付压缩包。
#
# 使用方式：
#   bash cloud_train_pack/run_evolution_train.sh
#
# 常用参数：
#   --base=/path/to/Qwen3-8B    # 指定本地预置基座路径 (缺省时自动从 ModelScope 下载)
#   --epochs=2.0               # SFT 轮数 (默认 2.0)
#   --skip-dpo                 # 跳过 DPO 阶段
#   --smoke                    # 冒烟模式 (以少量样本在 2 分钟内验证端到端全流程)
#   --selftest                 # 零 GPU 依赖 CPU 逻辑通道自检
#   --rebuild-corpus           # 强制重新合成与校验训练语料
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

echo "======================================================================"
echo "  🚀 Virtu 工业大模型 · 云端进化版训练系统 (Evolution Master)"
echo "  工程根目录: $ROOT"
echo "  启动时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "======================================================================"

# 1. 自动定位 Python 解释器
if [ -n "${ECT_PYTHON:-}" ] && [ -x "$ECT_PYTHON" ]; then
    PY="$ECT_PYTHON"
    PIP="${ECT_PIP:-$ECT_PYTHON -m pip}"
elif [ -x /opt/conda/bin/python3 ]; then
    PY="/opt/conda/bin/python3"
    PIP="/opt/conda/bin/pip"
elif [ -x /root/miniconda3/bin/python3 ]; then
    PY="/root/miniconda3/bin/python3"
    PIP="/root/miniconda3/bin/pip"
elif [ -x "$ROOT/.venv/bin/python" ]; then
    PY="$ROOT/.venv/bin/python"
    PIP="$ROOT/.venv/bin/pip"
else
    PY="python3"
    PIP="pip"
fi

echo "[1/4] 环境自检: Python=$("$PY" --version 2>&1) ($PY)"

# 2. GPU 算力探测
echo "[2/4] GPU 硬件体检..."
if command -v nvidia-smi &> /dev/null; then
    nvidia-smi --query-gpu=index,name,memory.total,memory.free,driver_version --format=csv,noheader || true
else
    echo "  [WARN] 未检测到 nvidia-smi，将以 CPU/模拟自检模式运行！"
fi

# 3. 核心依赖检查与自愈安装 (国内镜像加速)
echo "[3/4] 检查与补齐 Python 依赖环境..."
PIP_INDEX="${PIP_INDEX:-https://pypi.tuna.tsinghua.edu.cn/simple}"

# 验证核心依赖
if ! "$PY" -c "import torch, transformers, peft, trl, bitsandbytes, datasets, modelscope" &> /dev/null; then
    echo "  正在通过镜像安装核心训练库 (transformers, peft, trl, bitsandbytes, datasets, modelscope)..."
    "$PIP" install \
        "torch" \
        "peft>=0.10.0" \
        "bitsandbytes>=0.43.0" \
        "transformers>=4.45.0" \
        "datasets" \
        "accelerate" \
        "trl>=0.12.0" \
        "modelscope" \
        -i "$PIP_INDEX" -q
else
    echo "  [OK] 训练所需依赖库已完全就绪！"
fi

# 4. 环境变量与安全配置
export PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True"
export TOKENIZERS_PARALLELISM="false"
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"
export VIRTU_REPO_ROOT="$ROOT"
export PYTHONPATH="$ROOT:${PYTHONPATH:-}"

# 5. 启动总训练与交付引擎
echo "[4/4] 启动全流程进化训练引擎 (train_cloud_virtu_evolution.py)..."
"$PY" "$ROOT/cloud_train_pack/train_cloud_virtu_evolution.py" "$@"

echo "======================================================================"
echo "  🎉 云端全流程训练、对齐、评测、合并与打包圆满完成！"
echo "  成果物存放目录: $ROOT/cloud_train_pack/output"
echo "  可直接将输出压缩包拷贝回本地或私有服务器通过 Ollama 部署。"
echo "======================================================================"
