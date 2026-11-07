#!/usr/bin/env bash
# =============================================================================
# launch_cloud_full_train.sh — Virtu 云端全面训练与全维度高分测评·一键总入口
# -----------------------------------------------------------------------------
# 适用平台：AutoDL / 丹摩 Damodel / 恒源云 / RunPod / Lambda / 阿里云 / 本地 GPU
# 适用显卡：Tesla V100 32G (fp16)、L40S 48G (bf16)、A100/H100 80G (bf16)、RTX 4090 24G
#
# 单条命令即可开训（免配置、零值守、全自动）：
#   bash cloud_train_pack/launch_cloud_full_train.sh
#
# 常用开关：
#   --base=/path/to/Qwen3-8B    # 指定本地预置基座目录（跳过联网下载）
#   --skip-dpo                 # 跳过 DPO 阶段，仅跑 SFT 与全维度评测
#   --smoke                    # 20 步极速冒烟跑通全管线
#   --selftest                 # 零 GPU 依赖全流程逻辑自检
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# 1. Python 环境探测
if [ -n "${ECT_PYTHON:-}" ]; then
    PY="$ECT_PYTHON"
    PIP="${ECT_PIP:-$ECT_PYTHON -m pip}"
elif [ -x /opt/conda/bin/python3 ]; then
    PY="/opt/conda/bin/python3"
    PIP="/opt/conda/bin/pip"
elif [ -x /opt/venv/bin/python ]; then
    PY="/opt/venv/bin/python"
    PIP="/opt/venv/bin/pip"
else
    PY="python3"
    PIP="pip"
fi

export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export TOKENIZERS_PARALLELISM=false
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"
export VIRTU_REPO_ROOT="$ROOT"

echo "======================================================================"
echo "  🚀 Virtu 工业大模型 · 云端全面训练与全维度高分测评闭环系统"
echo "  工作区: $ROOT"
echo "  Python 解释器: $PY"
echo "======================================================================"

# 2. GPU 算力检查
echo "[1/5] GPU 硬件体检..."
if ! command -v nvidia-smi &> /dev/null; then
    echo "[WARN] 未找到 nvidia-smi 命令，将以 CPU/自检模式启动！"
else
    nvidia-smi --query-gpu=index,name,memory.total,memory.free,driver_version --format=csv,noheader || true
fi

# 3. 依赖自动安装（缺则补齐，含清华源加速）
echo "[2/5] 检查与补齐 Python 依赖包..."
PIP_INDEX="${PIP_INDEX:-https://pypi.tuna.tsinghua.edu.cn/simple}"
if ! "$PY" -c "import torch, transformers, peft, trl, bitsandbytes, datasets, modelscope" &> /dev/null; then
    echo "  正在安装训练核心库 (transformers, peft, trl, bitsandbytes, datasets, modelscope)..."
    "$PIP" install "peft>=0.10.0" "bitsandbytes>=0.43.0" "modelscope" "transformers>=4.45.0" "datasets" "accelerate" "trl>=0.12.0" -i "$PIP_INDEX" -q
else
    echo "  [OK] 所有训练核心依赖库已就绪！"
fi

# 4. 高分微调与 DPO 语料自检/构建
echo "[3/5] 检查全面高分语料集与 DPO 偏好对..."
SFT_DATA="$ROOT/cloud_train_pack/dataset/train_corpus_comprehensive.jsonl"
DPO_DATA="$ROOT/cloud_train_pack/dataset/dpo_comprehensive_pairs.jsonl"
if [ ! -f "$SFT_DATA" ] || [ ! -f "$DPO_DATA" ]; then
    echo "  语料缺失，自动启动 build_high_score_corpus.py 构建高分语料..."
    "$PY" "$ROOT/cloud_train_pack/build_high_score_corpus.py" --samples 7000 --dpo-pairs 1000
else
    echo "  [OK] 发现已就绪高分训练集: $(wc -l < "$SFT_DATA") 条, DPO 偏好对: $(wc -l < "$DPO_DATA") 对"
fi

# 5. 启动主训练与全维度就地测评引擎 (全面采用进化版 Evolution Master)
echo "[4/5] 启动主训练与闭环测评总引擎 (train_cloud_virtu_evolution.py)..."
"$PY" "$ROOT/cloud_train_pack/train_cloud_virtu_evolution.py" "$@"

echo "======================================================================"
echo "  🎉 训练、评测与交付全流程圆满完成！"
echo "  成果物存放目录: $ROOT/cloud_train_pack/output"
echo "  详细测评报告见: $ROOT/cloud_train_pack/output/COMPREHENSIVE_EVAL_REPORT.md"
echo "======================================================================"
