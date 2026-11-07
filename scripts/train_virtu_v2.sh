#!/usr/bin/env bash
# train_virtu_v2.sh —「全部 90」第二轮 QLoRA 开训（云端 GPU 实例执行）
#
# 设计原则：质量优先、成本最低。
#   * 复用已有成熟训练器 scripts/train_qwen3_8b_qlora.py（4bit NF4 + LoRA），不重写。
#   * 默认数据用已就绪的平衡能力集 data/sft/virtu_capability_sft_v6.jsonl（4233 条，覆盖多维度 + 反遗忘），
#     避免再从零生成万级数据；如需精标 v2 集，用 DATA=... 覆盖。
#   * 2 epoch、lr 1.5e-4、LoRA r=32/alpha=64，单卡 24G 即可，短作业、低单价。
#   * 若要从当前 SFT 续训，设 BASE_DIR=checkpoints/virtu_boundary_sft_merged（HF 目录）。
#
# 用法（云端工作目录 /root/virtu_train）：
#   bash scripts/train_virtu_v2.sh
#   DATA=data/sft/virtu_v2_all90.jsonl OUT=checkpoints/virtu_v2_all90 bash scripts/train_virtu_v2.sh
set -euo pipefail

export PIP_INDEX_URL="${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"
export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
export TOKENIZERS_PARALLELISM=false
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

DATA="${DATA:-data/sft/virtu_capability_sft_v6.jsonl}"
OUT="${OUT:-checkpoints/virtu_v2_all90}"
BASE_DIR="${BASE_DIR:-./models/Qwen3-8B}"
LR="${LR:-1.5e-4}"
EPOCHS="${EPOCHS:-2}"
BS="${BS:-4}"
ACCUM="${ACCUM:-4}"
LORA_R="${LORA_R:-32}"
LORA_ALPHA="${LORA_ALPHA:-64}"
SEED="${SEED:-20261102}"

echo "===== Virtu v2 (all-90) QLoRA $(date -u) ====="
echo "DATA=$DATA OUT=$OUT lr=$LR epochs=$EPOCHS bs=$BS accum=$ACCUM lora=$LORA_R/$LORA_ALPHA base_dir=$BASE_DIR"

# 复用 cloud_launch.sh 的环境探测/依赖安装/基座下载/数据校验/selftest 全流程，
# 仅通过环境变量覆盖超参与输出目录，避免重复维护训练逻辑。
export DATA OUT BASE_DIR LR EPOCHS BS ACCUM LORA_R LORA_ALPHA SEED
bash scripts/cloud_launch.sh

echo "===== DONE: adapter at $OUT ====="
