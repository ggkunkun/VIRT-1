#!/usr/bin/env bash
# cloud_train_pack/run_impeller_fix.sh — Virtu 8.2B (Qwen3-8B) 云端一键全链路修复训练脚本
# 兼容 V100 (.venv25: torch2.5.0+cu124 sm_70 fp16 LoRA) 与 A100/H100/4090/L40S (sm_80+ bf16 LoRA)
set -Eeuo pipefail
cd "$(dirname "$0")"
WORK="$(pwd)"

if [ -x "$WORK/.venv25/bin/python" ]; then
    PY="$WORK/.venv25/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PY="$(command -v python3)"
else
    PY="$(command -v python)"
fi

export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export TOKENIZERS_PARALLELISM=false
export PYTHONUNBUFFERED=1
export MODELSCOPE_CACHE="$WORK/.modelscope"
export HF_ENDPOINT="https://hf-mirror.com"

echo "[impeller-fix 1/6] 校验 Python 环境与 CUDA 矩阵乘实算 ($PY)"
"$PY" - <<'PY'
import torch
assert torch.cuda.is_available(), "[FATAL] CUDA 不可用"
x = torch.randn(1024, 1024, device="cuda", dtype=torch.float16)
y = x @ x
torch.cuda.synchronize()
print("[torch]", torch.__version__, "cuda", torch.version.cuda, "gpu", torch.cuda.get_device_name(0), "cc", torch.cuda.get_device_capability(0), "matmul_ok", tuple(y.shape))
PY

echo "[impeller-fix 2/6] 校验训练依赖"
"$PY" -c "import numpy,transformers,peft,datasets,accelerate; print('[deps] ok', transformers.__version__, peft.__version__)"

echo "[impeller-fix 3/6] 准备 8.2B 基座 Qwen3-8B"
BASE="$WORK/models/Qwen3-8B"
for cand in "$WORK/models/Qwen3-8B" "/root/virtu_train/models/Qwen3-8B" "/root/workspace/models/Qwen3-8B" "/root/models/Qwen3-8B" "/root/autodl-tmp/models/Qwen3-8B"; do
    if [ -f "$cand/config.json" ]; then
        BASE="$cand"
        break
    fi
done

if [ ! -f "$BASE/config.json" ]; then
    mkdir -p "$(dirname "$BASE")"
    "$PY" - <<PY
try:
    from modelscope import snapshot_download
    snapshot_download("Qwen/Qwen3-8B", local_dir="$BASE")
except Exception as e:
    print("[warn] modelscope fallback to huggingface_hub:", e)
    from huggingface_hub import snapshot_download
    snapshot_download("Qwen/Qwen3-8B", local_dir="$BASE")
PY
fi
test -f "$BASE/config.json" || { echo "[FATAL] 基座缺 config.json: $BASE"; exit 1; }

DATA_FILE="dataset/virtu_impeller_retrain_sft.jsonl"
echo "[impeller-fix 4/6] 校验修复语料与防泄漏/量纲/Loss掩码三重闸门"
test -f "$DATA_FILE" || { echo "[FATAL] 缺 $DATA_FILE"; exit 1; }
du -h "$DATA_FILE"
"$PY" - <<PY
import sys
sys.path.insert(0, ".")
sys.path.insert(0, "scripts")
from virtu_eval.contamination_check import assert_no_leak
from corpus_unit_audit import assert_units_clean
from train_turnkey_impeller import format_chatml_sample
from transformers import AutoTokenizer

assert_no_leak("$DATA_FILE")
assert_units_clean("$DATA_FILE")
tok = AutoTokenizer.from_pretrained("$BASE", trust_remote_code=True)
rec = {"messages": [
    {"role": "system", "content": "sys"},
    {"role": "user", "content": "u1"},
    {"role": "assistant", "content": "BAD_TURN_MASKED", "loss": False},
    {"role": "user", "content": "fb"},
    {"role": "assistant", "content": "GOOD_TURN_UNMASKED", "loss": True},
], "last_assistant_only": True}
out = format_chatml_sample(rec, tok, 2048)
unmasked = tok.decode([l for l in out["labels"] if l != -100])
assert "BAD_TURN_MASKED" not in unmasked and "GOOD_TURN_UNMASKED" in unmasked, f"Loss mask gate failed: {unmasked}"
print("[gate] 三重闸门 (防泄漏 + 量纲 + 坏解轮Loss掩码) 全部通过")
PY

echo "[impeller-fix 5/6] 启动 8.2B 全量 LoRA 根因重训 (2946 条全链路修复语料)"
"$PY" train_turnkey_impeller.py \
    --base "$BASE" \
    --data "$DATA_FILE" \
    --out output/virtu_impeller_fix2_lora \
    --epochs 3.0 --lr 1.0e-4 --batch 1 --grad-accum 8 \
    --max-length 3072 --max-hours 1.5 "$@"

echo "[impeller-fix 6/6] 同步双路径交付件别名 (兼容 fix 与 fix2 监控/拉取)"
mkdir -p output/virtu_impeller_fix_lora
cp -f output/virtu_impeller_fix2_lora/virtu_lora_deliverable.tar.gz output/virtu_impeller_fix_lora/virtu_lora_deliverable.tar.gz

echo "✅ 8.2B 根因修复训练完成：output/virtu_impeller_fix2_lora/virtu_lora_deliverable.tar.gz"
