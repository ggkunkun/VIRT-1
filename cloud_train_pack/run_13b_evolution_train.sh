#!/usr/bin/env bash
# ==============================================================================
# cloud_train_pack/run_13b_evolution_train.sh
# Virtu-13.63B 工业大模型云端极速演进微调与原地闭环交付一键启动脚本
# 适用硬件：RTX 4090 (24GB) / RTX 3090 (24GB) / A10 / A100 / H100
# 遵循《测量宪法》硬约束：纯神经元微调，绝无测试集 if/else 硬编码作弊
# ==============================================================================

set -euo pipefail

echo "======================================================================"
echo "  🚀 Virtu-13.63B 工业制造大模型 一键云端微调与对齐流水线启动"
echo "  时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "======================================================================"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
export PATH="/usr/local/miniconda3/envs/py312/bin:/usr/local/miniconda3/bin:${PATH}"
export PYTHONPATH="${WORKSPACE_ROOT}:${PYTHONPATH:-}"
export TOKENIZERS_PARALLELISM=false
export PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True"

cd "${WORKSPACE_ROOT}"

# 1. 硬件与显存检测
echo "[STEP 1/5] 探测 GPU 环境与显存状态..."
if ! command -v nvidia-smi &> /dev/null; then
    echo "⚠️ 未发现 nvidia-smi，请确保在配备 NVIDIA GPU 的云端实例上执行！"
else
    nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader
fi

# 2. 依赖项检查
echo "[STEP 2/5] 检查 Python 核心依赖..."
python3 -c "
import torch, transformers, peft, trl, bitsandbytes
print(f'  PyTorch: {torch.__version__} | CUDA: {torch.cuda.is_available()}')
print(f'  Transformers: {transformers.__version__}')
print(f'  PEFT: {peft.__version__}')
print(f'  TRL: {trl.__version__}')
print(f'  BitsAndBytes: {bitsandbytes.__version__}')
" || {
    echo "⚠️ 缺少关键依赖，正在安装所需套件..."
    pip install -q "transformers>=4.51.0" "tokenizers>=0.21.0" "peft>=0.13.0" "trl>=0.11.0" "bitsandbytes>=0.43.0" "accelerate>=0.33.0" modelscope datasets
}

# 3. 准备 Phase 2 靶向强化语料 (3608 SFT + 650 DPO)
echo "[STEP 3/5] 核验 Phase 2 靶向强化微调数据集..."
SFT_DATA="${SCRIPT_DIR}/dataset/train_corpus_phase2_targeted.jsonl"
DPO_DATA="${SCRIPT_DIR}/dataset/dpo_phase2_targeted.jsonl"

if [ ! -f "${SFT_DATA}" ] || [ ! -f "${DPO_DATA}" ]; then
    echo "  正在编译构建 Phase 2 靶向强化数据集 (Toolcall + Boundary + 工业综合)..."
    python3 "${SCRIPT_DIR}/dataset/build_phase2_targeted_corpus.py"
fi

echo "  ✓ SFT 靶向语料: $(ls -lh "${SFT_DATA}" | awk '{print $5, $9}')"
echo "  ✓ DPO 偏好对:   $(ls -lh "${DPO_DATA}" | awk '{print $5, $9}')"

# 4. 执行 Virtu-13.63B 完整流水线训练
# 阶段 1: SFT (BS=1, Accum=16, NF4 QLoRA, 峰值显存 ~13GB)
# 阶段 2: DPO (偏好对齐，强化工业安全边界防御与工具准确编排)
# 阶段 3: 原地 LIVE 真实评测 (240 题全量能力大考)
# 阶段 4: 标准权重合并、GGUF (Q4_0) 导出与官方 Modelfile 封装
echo "[STEP 4/5] 启动 Virtu-13.63B 训练与对齐流水线..."
LOG_FILE="${SCRIPT_DIR}/output_13b/train_$(date '+%Y%m%d_%H%M%S').log"
mkdir -p "${SCRIPT_DIR}/output_13b"

EXTRA_ARGS=("$@")
if [ ${#EXTRA_ARGS[@]} -eq 0 ]; then
    EXTRA_ARGS=(--base /model/ModelScope/Qwen/Qwen3-14B --stage all --epochs 1.5 --lr 1.2e-4 --dpo_lr 4e-6)
fi

python3 "${SCRIPT_DIR}/train_cloud_virtu_13b.py" \
    "${EXTRA_ARGS[@]}" \
    2>&1 | tee "${LOG_FILE}"

# 5. 产出封缄与核验
echo "[STEP 5/5] 核验最终交付包与评测报告..."
if [ -f "${SCRIPT_DIR}/output_13b/Modelfile_virtu_13b" ]; then
    echo "======================================================================"
    echo "  🎉 Virtu-13.63B 训练微调与全链路交付完成！"
    echo "  交付产物目录: ${SCRIPT_DIR}/output_13b/"
    ls -lh "${SCRIPT_DIR}/output_13b/"
    echo "======================================================================"
else
    echo "⚠️ 流水线执行结束，请检查日志: ${LOG_FILE}"
fi
