#!/usr/bin/env bash
# =============================================================================
# cloud_train_pack/run_dpo.sh — Virtu 世界模型「反幻觉」云端 DPO 开训入口
# 配套：build_dpo_dataset.py（生成本地偏好对） + train_dpo_cloud.py（云端训练）
# 数据集来源：6 组 _eval_phys_*_*/triples.jsonl 的 132 条带标签错误
# =============================================================================
set -e

if [ -d "/opt/conda/bin" ]; then
    export PATH="/opt/conda/bin:$PATH"
    PYTHON_CMD="/opt/conda/bin/python3"
    PIP_CMD="/opt/conda/bin/pip"
else
    PYTHON_CMD="python3"
    PIP_CMD="pip"
fi

export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export TOKENIZERS_PARALLELISM=false

echo "====================================================================="
echo "   Virtu 世界模型 · 反幻觉 DPO 云端训练套件"
echo "====================================================================="

echo "[Step 1/4] 检查 GPU 算力状态 ..."
nvidia-smi --query-gpu=index,name,memory.total,memory.free --format=csv || {
    echo "[ERROR] 未检测到 NVIDIA GPU！"
    exit 1
}

echo "[Step 2/4] 安装训练依赖（含 trl DPO 引擎）..."
$PIP_CMD install "peft>=0.13.0,<0.16.0" "transformers>=4.51.0,<5.0.0" "datasets>=2.18.0,<4.0.0" "accelerate>=0.33.0,<2.0.0" "trl>=0.12.0,<0.18.0" "bitsandbytes>=0.43.0,<0.47.0" -i https://pypi.tuna.tsinghua.edu.cn/simple -q

echo "[Step 3/4] 检查 DPO 偏好对数据集 ..."
if [ -f "dataset/dpo_phys_rejects.jsonl" ]; then
    DATA_FILE="dataset/dpo_phys_rejects.jsonl"
else
    echo "[ERROR] 未找到 dataset/dpo_phys_rejects.jsonl，请先在本地运行 build_dpo_dataset.py"
    exit 1
fi
echo "  -> 发现 DPO 偏好对: $DATA_FILE ($(wc -l < "$DATA_FILE") 条)"

# 继承 v3 能力：若云端实例已同步 v3 adapter 则传入，否则从 base 直接 DPO
RESUME_FLAG=""
if [ -d "checkpoints/virtu_v3_all90" ]; then
    RESUME_FLAG="--resume-adapter checkpoints/virtu_v3_all90"
    echo "  -> 发现 v3 adapter，将 merge 进 base 再 DPO（防遗忘）"
else
    echo "  -> 未找到 v3 adapter，从 base 直接 DPO（仍有效）"
fi

echo "[Step 4/4] 启动 DPO 训练引擎 ..."
$PYTHON_CMD train_dpo_cloud.py \
    --data "$DATA_FILE" \
    --out output/virtu_dpo_antihallu \
    --epochs "${EPOCHS:-2.0}" \
    --lr "${LR:-5e-6}" \
    --beta "${BETA:-0.1}" \
    --batch "${BS:-2}" \
    --grad-accum "${ACCUM:-8}" \
    --max-length "${MAX_LEN:-1536}" \
    --max-hours "${MAX_HOURS:-1.5}" \
    $RESUME_FLAG "$@"

echo "====================================================================="
echo "✅ DPO 训练完成！交付物: output/virtu_dpo_antihallu/virtu_dpo_deliverable.tar.gz"
echo "可用 SCP 或 deploy_trained_adapter.py 拉取回本机合并。"
echo "====================================================================="
