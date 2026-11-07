#!/usr/bin/env bash
# 本地 GPU 简洁偏好 DPO 训练启动器（A3）—— 复用 train_dpo_cloud.py，但指向本地 HF 基座与 .venv torch。
# 用法:
#   bash run_local_dpo.sh [BASE] [DATA] [OUT] [MAXHOURS]
set -e
cd "$(dirname "$0")/.."
BASE="${1:-checkpoints/virtu_cad_cam_merged_v3}"
DATA="${2:-cloud_train_pack/dataset/dpo_concise_pairs.jsonl}"
OUT="${3:-output/dpo_concise_disciplined}"
MAXH="${4:-1.0}"
echo ">>> base=$BASE data=$DATA out=$OUT maxhours=$MAXH"
./.venv/Scripts/python cloud_train_pack/train_dpo_cloud.py \
  --base "$BASE" --data "$DATA" --out "$OUT" \
  --epochs 3 --lr 5e-6 --beta 0.2 \
  --batch 1 --grad-accum 4 --max-length 768 \
  --lora-r 16 --lora-alpha 32 --seed 42 --max-hours "$MAXH"
echo ">>> DPO training done -> $OUT"
