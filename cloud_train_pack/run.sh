#!/usr/bin/env bash
# =============================================================================
# cloud_train_pack/run.sh — Virtu 工业大模型云端一键极速开训入口脚本
# =============================================================================

set -e

# 确保使用 Conda 预装环境 (含 torch 2.5 + CUDA)
if [ -d "/opt/conda/bin" ]; then
    export PATH="/opt/conda/bin:$PATH"
    PYTHON_CMD="/opt/conda/bin/python3"
    PIP_CMD="/opt/conda/bin/pip"
else
    PYTHON_CMD="python3"
    PIP_CMD="pip"
fi

# 显存碎片整理与 Tokenizer 并行化安全配置
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export TOKENIZERS_PARALLELISM=false

echo "====================================================================="
echo "   Virtu CAD/CAM 工业智能体大模型 — 云端一键极速训练套件"
echo "====================================================================="

# 1. 检查 Python 与 GPU 环境
echo "[Step 1/4] 检查 GPU 算力状态 ..."
nvidia-smi --query-gpu=index,name,memory.total,memory.free --format=csv || {
    echo "[ERROR] 未检测到 NVIDIA GPU，请检查实例配置！"
    exit 1
}

# 2. 检查与快速安装训练依赖
echo "[Step 2/4] 检查 Python 运行依赖与模型加速库 ..."
$PIP_CMD install "peft>=0.10.0" "bitsandbytes>=0.43.0" "modelscope" "transformers>=4.45.0" "datasets" "accelerate" -i https://pypi.tuna.tsinghua.edu.cn/simple -q

# 3. 检查基座与语料
echo "[Step 3/4] 检查生产级工业 SFT 数据集 ..."
if [ -f "dataset/virtu_capability_sft_v5.jsonl" ]; then
    DATA_FILE="dataset/virtu_capability_sft_v5.jsonl"
elif [ -f "dataset/virtu_v100_production_sft.jsonl" ]; then
    DATA_FILE="dataset/virtu_v100_production_sft.jsonl"
else
    DATA_FILE="dataset/virtu_gold_production_sft.jsonl"
fi

if [ ! -f "$DATA_FILE" ]; then
    echo "[ERROR] 未找到训练语料！请确认 dataset 目录下存在 virtu_v100_production_sft.jsonl 或 virtu_gold_production_sft.jsonl"
    exit 1
fi

DATA_SIZE=$(du -h "$DATA_FILE" | cut -f1)
echo "  -> 发现生产级 SFT 语料: $DATA_FILE (${DATA_SIZE})"

# 4. 启动单卡极速训练引擎 (Tesla V100 32GB 专属调优)
echo "[Step 4/4] 启动 V100 训练引擎 (预计 30-45 分钟，机时费约 1.5 元) ..."
$PYTHON_CMD train_turnkey.py \
    --data "$DATA_FILE" \
    --out output/virtu_lora_master \
    --epochs 2.0 \
    --lr 1.5e-4 \
    --batch 1 \
    --grad-accum 16 \
    --max-length 2048 \
    --max-hours 1.5 "$@"

echo "====================================================================="
echo "✅ 训练完成！可交付成果位于: output/virtu_lora_master/virtu_lora_deliverable.tar.gz"
echo "可以使用 SCP 或本地脚本将其下载回本机进行干净 LoRA 合并！"
echo "====================================================================="
