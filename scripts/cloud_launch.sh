#!/usr/bin/env bash
# cloud_launch.sh — Virtu QLoRA 云端一键开训
#
# 用法（云端 GPU 实例，Linux）：
#   bash scripts/cloud_launch.sh
#
# 可覆盖的环境变量（可选）：
#   BASE=./models/Qwen3-8B  LR=2e-4  EPOCHS=3  BS=4  ACCUM=4  LORA_R=32  LORA_ALPHA=64
#   DATA=data/sft/virtu_capability_sft_v6.jsonl  OUT=checkpoints/cad_cam_boundary_lora
#
# 说明：优先复用实例已有的带 CUDA 的 python（如 /opt/conda/bin/python3.11），
#       只补装缺失的 ML 库，按需下载 Qwen3-8B 基座，先 selftest 再正式训练。

set -euo pipefail

echo "===== Virtu QLoRA Cloud Launcher $(date -u) ====="

# ---- 镜像（国内加速） ----
export PIP_INDEX_URL="${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"
export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
export TOKENIZERS_PARALLELISM=false
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

# ---- 选 python：优先带 CUDA 的 conda python ----
PYEXE="python3"
if [ -x /opt/conda/bin/python3.11 ] && /opt/conda/bin/python3.11 -c "import torch; assert torch.cuda.is_available()" 2>/dev/null; then
  PYEXE=/opt/conda/bin/python3.11
elif command -v python3 >/dev/null 2>&1 && python3 -c "import torch; assert torch.cuda.is_available()" 2>/dev/null; then
  PYEXE=python3
fi
PIP="$PYEXE -m pip"
echo "using python: $($PYEXE --version 2>&1)"

# ---- 默认参数（可用环境变量覆盖） ----
BASE_DIR="${BASE_DIR:-./models/Qwen3-8B}"
BASE="${BASE:-Qwen/Qwen3-8B}"
DATA="${DATA:-data/sft/virtu_capability_sft_v6.jsonl}"
OUT="${OUT:-checkpoints/cad_cam_boundary_lora}"
LR="${LR:-2e-4}"
EPOCHS="${EPOCHS:-3}"
BS="${BS:-4}"
ACCUM="${ACCUM:-4}"
LORA_R="${LORA_R:-32}"
LORA_ALPHA="${LORA_ALPHA:-64}"
SEED="${SEED:-20261031}"
RESUME_ADAPTER="${RESUME_ADAPTER:-}"

# ---- 0) GPU 健康检查 ----
echo "[0/5] GPU check:"
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi --query-gpu=name,memory.total --format=csv,noheader || echo "  nvidia-smi present but query failed"
else
  echo "  WARNING: nvidia-smi not found; proceeding (driver may still work)"
fi

# ---- 0.5) 自举 pip（若无） ----
if ! $PYEXE -m pip --version >/dev/null 2>&1; then
  echo "[0.5/5] pip missing; bootstrapping via ensurepip..."
  $PYEXE -m ensurepip --upgrade 2>/dev/null || {
    echo "  ensurepip failed; fetching get-pip.py..."
    curl -fsSL https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py \
      && $PYEXE /tmp/get-pip.py
  }
fi

# ---- 1) 依赖 ----
echo "[1/5] Installing dependencies..."
# 若已自带 torch+cuda，跳过重装以免破坏已匹配的 CUDA 环境
if $PYEXE -c "import torch; assert torch.cuda.is_available()" 2>/dev/null; then
  echo "  torch+cuda already present ($( $PYEXE -c 'import torch;print(torch.__version__)' 2>/dev/null )), skip reinstall."
else
  # 仅当缺失时才装 torch（走官方 cu124 源）
  $PIP install -q --no-input torch==2.6.0 --index-url https://download.pytorch.org/whl/cu124 \
    || $PIP install -q --no-input torch==2.6.0
fi
$PIP install -q --no-input \
  transformers==4.56.0 peft==0.13.2 bitsandbytes==0.43.3 \
  datasets==3.0.2 accelerate==1.15.0 modelscope
echo "  deps installed."

# ---- 2) 基座（优先本地目录；否则 modelscope 下载；再否则交给 transformers 自动下载） ----
BASE_ARG=""
if [ -d "$BASE_DIR" ]; then
  echo "[2/5] Using local base at $BASE_DIR"
  BASE_ARG="--base $BASE_DIR"
else
  echo "[2/5] Local base not found; trying modelscope download to $BASE_DIR ..."
  if $PYEXE -c "from modelscope import snapshot_download; snapshot_download('Qwen/Qwen3-8B', local_dir='$BASE_DIR')" 2>/dev/null; then
    BASE_ARG="--base $BASE_DIR"
    echo "  downloaded via modelscope."
  else
    echo "  modelscope failed; will let transformers autodownload '$BASE' (needs network)."
    BASE_ARG="--base $BASE"
  fi
fi

# ---- 3) 数据校验 ----
echo "[3/5] Data check:"
if [ ! -f "$DATA" ]; then
  echo "  ERROR: training data not found at $DATA"
  echo "  请把 virtu_capability_sft_v6.jsonl 放到工作区 $DATA（随仓库上传）。"
  exit 1
fi
echo "  data OK: $DATA"

# ---- 4) selftest -> train ----
echo "[4/5] Selftest:"
$PYEXE scripts/train_qwen3_8b_qlora.py $BASE_ARG \
  --data "$DATA" --out "$OUT" --selftest

RESUME_ARG=""
if [ -n "$RESUME_ADAPTER" ]; then
  RESUME_ARG="--resume-adapter $RESUME_ADAPTER"
  echo "[5/5] Resume mode: continuing from $RESUME_ADAPTER"
fi
echo "[5/5] Training:"
$PYEXE scripts/train_qwen3_8b_qlora.py $BASE_ARG \
  --data "$DATA" --out "$OUT" $RESUME_ARG \
  --lora_r "$LORA_R" --lora_alpha "$LORA_ALPHA" \
  --lr "$LR" --epochs "$EPOCHS" --bs "$BS" --accum "$ACCUM" --seed "$SEED"

echo "===== DONE: LoRA adapter at $OUT ====="
echo "下一步（本地/部署机）：合并+量化+注册 Ollama，见 CLOUD_FINETUNE_PLAN.md 第 5/6 节。"
