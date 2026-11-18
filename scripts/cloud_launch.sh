#!/usr/bin/env bash
# cloud_launch.sh — Virtu QLoRA 云端硬门禁一键开训 (v2 硬化版)
#
# 用法（云端 GPU 实例，Linux）：
#   bash scripts/cloud_launch.sh
#
# 可覆盖的环境变量（可选）：
#   BASE=./models/Qwen3-8B  LR=2e-4  EPOCHS=3  BS=4  ACCUM=4  LORA_R=32  LORA_ALPHA=64
#   DATA=data/sft/virtu_capability_sft_v6.jsonl  OUT=checkpoints/cad_cam_boundary_lora

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$ROOT"

echo "===== Virtu QLoRA Cloud Launcher $(date -u) ====="

export PIP_INDEX_URL="${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"
export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
export TOKENIZERS_PARALLELISM=false
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export PYTHONPATH="${ROOT}:${PYTHONPATH:-}"

# ---- 单实例排他文件锁 ----
LOCK_FILE="${ROOT}/scripts/.virtu_cloud_launch.lock"
exec 9>"$LOCK_FILE"
flock -n 9 || {
  echo "[FATAL] 已有 cloud_launch 实例正在持有锁 ($LOCK_FILE)，拒绝并发开训！" >&2
  exit 1
}

# ---- 0) GPU 健康与 fp16 torch.matmul 实算探测 ----
echo "[0/5] GPU hardware & fp16 torch.matmul check:"
if ! command -v nvidia-smi >/dev/null 2>&1; then
  echo "[FATAL] nvidia-smi not found; refusing blind cloud run!" >&2
  exit 2
fi
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader

probe_gpu_py() {
  local py_bin="$1"
  "$py_bin" - <<'PY' >/dev/null 2>&1
import torch, transformers, peft, bitsandbytes, datasets
assert torch.cuda.is_available()
a = torch.randn(16, 16, device="cuda", dtype=torch.float16)
c = torch.matmul(a, a)
torch.cuda.synchronize()
assert tuple(c.shape) == (16, 16) and torch.isfinite(c).all()
PY
}

PYEXE=""
for cand in "${ECT_PYTHON:-}" "/root/venv25/bin/python" "/opt/conda/bin/python3.11" "/opt/conda/bin/python3" "$(command -v python3 || true)" "$(command -v python || true)"; do
  if [[ -n "$cand" ]] && [[ -x "$cand" || -x "$(command -v "$cand" 2>/dev/null || true)" ]] && probe_gpu_py "$cand"; then
    PYEXE="$cand"
    break
  fi
done

if [[ -z "$PYEXE" ]]; then
  BASE_PY="$(command -v python3 || command -v python || true)"
  if [[ -z "$BASE_PY" ]]; then
    echo "[FATAL] python3 not found" >&2
    exit 2
  fi
  echo "[1/5] 自愈 /root/venv25 并通过 fp16 torch.matmul 探测..."
  if [[ ! -x /root/venv25/bin/python ]]; then
    "$BASE_PY" -m venv /root/venv25 --system-site-packages || "$BASE_PY" -m venv /root/venv25
  fi
  /root/venv25/bin/python -m pip install -q --no-input \
    "transformers>=4.51.0,<5.0.0" "peft>=0.13.0,<0.16.0" "bitsandbytes>=0.43.0,<0.47.0" "datasets>=2.18.0,<4.0.0" "accelerate>=0.33.0,<2.0.0" modelscope safetensors
  if probe_gpu_py /root/venv25/bin/python; then
    PYEXE="/root/venv25/bin/python"
  else
    echo "[FATAL] /root/venv25 GPU fp16 torch.matmul 实算探测失败，拒绝盲跑！" >&2
    exit 2
  fi
fi
echo "  [OK] using python: $PYEXE ($($PYEXE --version 2>&1))"

# ---- 参数与默认语料解析（显式 DATA 不存在时绝不静默回退） ----
BASE_DIR="${BASE_DIR:-./models/Qwen3-8B}"
BASE="${BASE:-Qwen/Qwen3-8B}"
OUT="${OUT:-checkpoints/cad_cam_boundary_lora}"
LR="${LR:-2e-4}"
EPOCHS="${EPOCHS:-3}"
BS="${BS:-4}"
ACCUM="${ACCUM:-4}"
LORA_R="${LORA_R:-32}"
LORA_ALPHA="${LORA_ALPHA:-64}"
SEED="${SEED:-20261031}"
RESUME_ADAPTER="${RESUME_ADAPTER:-}"

if [[ -n "${DATA:-}" ]]; then
  if [[ ! -f "$DATA" ]]; then
    echo "[FATAL] 显式指定 DATA=$DATA 不存在，拒绝静默回退！" >&2
    exit 2
  fi
elif [[ -f "data/sft/virtu_capability_sft_v6.jsonl" ]]; then
  DATA="data/sft/virtu_capability_sft_v6.jsonl"
elif [[ -f "cloud_train_pack/dataset/virtu_capability_sft_v5.jsonl" ]]; then
  DATA="cloud_train_pack/dataset/virtu_capability_sft_v5.jsonl"
else
  echo "[FATAL] 未找到主训语料 (virtu_capability_sft_v6.jsonl / v5.jsonl)" >&2
  exit 2
fi

# ---- 2) 基座血统门禁（禁止 Qwen3-8B-Instruct 等错配变体） ----
BASE_ARG=""
if [[ -d "$BASE_DIR" ]]; then
  echo "[2/5] Using local base at $BASE_DIR"
  BASE_ARG="--base $BASE_DIR"
else
  echo "[2/5] Local base not found; trying modelscope download Qwen/Qwen3-8B -> $BASE_DIR ..."
  "$PYEXE" -c "from modelscope import snapshot_download; snapshot_download('Qwen/Qwen3-8B', local_dir='$BASE_DIR')"
  BASE_ARG="--base $BASE_DIR"
fi

"$PYEXE" - "$BASE_DIR" <<'PY'
import json, os, sys
cfg_p = os.path.join(sys.argv[1], "config.json")
if not os.path.exists(cfg_p):
    raise SystemExit(f"[FATAL] 缺少基座 config.json: {cfg_p}")
if "instruct" in sys.argv[1].lower():
    raise SystemExit(f"[FATAL] 禁止使用 Instruct 变体作为主力基座: {sys.argv[1]}")
cfg = json.load(open(cfg_p, "r", encoding="utf-8"))
exp = {"hidden_size": 4096, "num_hidden_layers": 36, "vocab_size": 151936}
for k, v in exp.items():
    if cfg.get(k) != v:
        raise SystemExit(f"[FATAL] 基座维度不匹配 Qwen3-8B: {k}={cfg.get(k)} != {v}")
print("[Lineage] PASS: non-Instruct Qwen3-8B (4096/36/151936)")
PY

# ---- 3) 数据防污染与物理单位硬门禁 ----
echo "[3/5] Running assert_no_leak + assert_units_clean on $DATA ..."
"$PYEXE" - "$DATA" "$ROOT" <<'PY'
import os, sys, hashlib
data_p, root = sys.argv[1:3]
sys.path.insert(0, root)
sys.path.insert(0, os.path.join(root, "scripts"))
from virtu_eval.contamination_check import assert_no_leak
from corpus_unit_audit import assert_units_clean
assert_no_leak(data_p)
assert_units_clean(data_p)
sha = hashlib.sha256(open(data_p, "rb").read()).hexdigest()
print(f"[Gate] PASS: {data_p} sha256={sha[:16]}...")
PY

# ---- 4) selftest -> train ----
echo "[4/5] Selftest:"
"$PYEXE" scripts/train_qwen3_8b_qlora.py $BASE_ARG --data "$DATA" --out "$OUT" --selftest

RESUME_ARG=""
if [[ -n "$RESUME_ADAPTER" ]]; then
  RESUME_ARG="--resume-adapter $RESUME_ADAPTER"
  echo "[5/5] Resume mode: continuing from $RESUME_ADAPTER"
fi
echo "[5/5] Training:"
"$PYEXE" scripts/train_qwen3_8b_qlora.py $BASE_ARG \
  --data "$DATA" --out "$OUT" $RESUME_ARG \
  --lora_r "$LORA_R" --lora_alpha "$LORA_ALPHA" \
  --lr "$LR" --epochs "$EPOCHS" --bs "$BS" --accum "$ACCUM" --seed "$SEED"

echo "===== DONE: LoRA adapter at $OUT ====="
