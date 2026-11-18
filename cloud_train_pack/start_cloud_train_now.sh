#!/usr/bin/env bash
# ==============================================================================
# cloud_train_pack/start_cloud_train_now.sh
# Virtu 云端实例上线马上开训·统一总控入口
#
# 支持直接在云端 GPU 实例终端内一键启动任一产线，强制前置：
#   flock 单实例排他锁 -> GPU fp16 torch.matmul 实算探测 (/root/venv25 自愈)
#   -> 目标产线离线 --selftest 预检 -> 立即开训（支持 --bg 后台 + 8s 存活探针）
#
# 用法示例：
#   bash cloud_train_pack/start_cloud_train_now.sh --track master-8b --bg
#   bash cloud_train_pack/start_cloud_train_now.sh --track 13b --bg
#   bash cloud_train_pack/start_cloud_train_now.sh --track all90 --bg
#   bash cloud_train_pack/start_cloud_train_now.sh --track worldmodel --bg
#   bash cloud_train_pack/start_cloud_train_now.sh --track safety --bg
#   bash cloud_train_pack/start_cloud_train_now.sh --track vericut96 --bg
#   bash cloud_train_pack/start_cloud_train_now.sh --track vericut96-v2 --bg
#   bash cloud_train_pack/start_cloud_train_now.sh --track vericut-e --bg
#   bash cloud_train_pack/start_cloud_train_now.sh --track six-software --bg
#   bash cloud_train_pack/start_cloud_train_now.sh --tracks vericut96-v2,vericut-e,six-software --bg
#   bash cloud_train_pack/start_cloud_train_now.sh --selftest
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -d "${SCRIPT_DIR}/virtu_eval" ]]; then
  REPO_ROOT="$SCRIPT_DIR"
elif [[ -d "${SCRIPT_DIR}/../virtu_eval" ]]; then
  REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
else
  REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
fi
cd "$REPO_ROOT"

TRACK="${VIRTU_CLOUD_TRACK:-master-8b}"
TRACKS_CSV="${VIRTU_CLOUD_TRACKS:-}"
BG_MODE=0
SELFTEST_ONLY=0
SKIP_SELFTEST=0
WAIT_GPU_S="${VIRTU_WAIT_GPU_SECONDS:-60}"
EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --track)
      TRACK="${2:-}"
      shift 2
      ;;
    --track=*)
      TRACK="${1#*=}"
      shift
      ;;
    --tracks)
      TRACKS_CSV="${2:-}"
      shift 2
      ;;
    --tracks=*)
      TRACKS_CSV="${1#*=}"
      shift
      ;;
    --wait-gpu-s)
      WAIT_GPU_S="${2:-60}"
      shift 2
      ;;
    --wait-gpu-s=*)
      WAIT_GPU_S="${1#*=}"
      shift
      ;;
    --bg)
      BG_MODE=1
      shift
      ;;
    --selftest)
      SELFTEST_ONLY=1
      shift
      ;;
    --skip-selftest)
      SKIP_SELFTEST=1
      shift
      ;;
    *)
      EXTRA_ARGS+=("$1")
      shift
      ;;
  esac
done

TRACK_LIST=()
if [[ -n "$TRACKS_CSV" ]]; then
  IFS=',' read -r -a _raw_tracks <<< "$TRACKS_CSV"
  for _t in ${_raw_tracks[@]+"${_raw_tracks[@]}"}; do
    _t="${_t//[[:space:]]/}"
    if [[ -n "$_t" ]]; then
      TRACK_LIST+=("$_t")
    fi
  done
  if [[ "${#TRACK_LIST[@]}" -eq 0 ]]; then
    echo "[FATAL] --tracks 参数为空！" >&2
    exit 2
  fi
  TRACK="${TRACK_LIST[0]}"
else
  TRACK_LIST=("$TRACK")
fi

validate_track_name() {
  case "$1" in
    master-8b|13b|all90|worldmodel|safety|vericut96|vericut96-v2|vericut96_v2|vericut-e|vericut_e|six-software|six_software)
      return 0
      ;;
    *)
      echo "[FATAL] 未知产线 --track=$1 (可选: master-8b|13b|all90|worldmodel|safety|vericut96|vericut96-v2|vericut-e|six-software)" >&2
      exit 2
      ;;
  esac
}
for _t in "${TRACK_LIST[@]}"; do
  validate_track_name "$_t"
done

export PATH="/root/venv25/bin:/opt/conda/bin:/usr/local/miniconda3/bin:${PATH}"
export PYTHONPATH="${REPO_ROOT}:${PYTHONPATH:-}"
export TOKENIZERS_PARALLELISM=false
export PYTORCH_CUDA_ALLOC_CONF="${PYTORCH_CUDA_ALLOC_CONF:-expandable_segments:True}"

pick_py() {
  local cand
  for cand in "${ECT_PYTHON:-}" "/root/venv25/bin/python" "/opt/conda/bin/python" "/opt/venv/bin/python" "${REPO_ROOT}/.venv/Scripts/python.exe" "${REPO_ROOT}/.venv/bin/python" "$(command -v python3 || true)" "$(command -v python || true)"; do
    if [[ -n "$cand" ]] && [[ -x "$cand" || -x "$(command -v "$cand" 2>/dev/null || true)" ]]; then
      echo "$cand"
      return 0
    fi
  done
  echo "[FATAL] 未找到可用 Python 解释器！" >&2
  exit 2
}

PY="$(pick_py)"

run_track_selftest() {
  case "$TRACK" in
    master-8b)
      "$PY" "${SCRIPT_DIR}/train_turnkey.py" --selftest
      ;;
    13b)
      "$PY" "${SCRIPT_DIR}/train_cloud_virtu_13b.py" --selftest
      ;;
    all90)
      "$PY" "${SCRIPT_DIR}/train_turnkey.py" --selftest
      "$PY" "${REPO_ROOT}/scripts/gate_all90_dataset.py" --self-test
      "$PY" "${REPO_ROOT}/scripts/train_dpo_all90.py" --self-test
      "$PY" "${REPO_ROOT}/scripts/eval_all90_three_boards.py" --self-test
      ;;
    worldmodel)
      "$PY" - <<'PY'
import os, json, hashlib
sft = "cloud_train_pack/dataset/virtu_worldmodel_fix_sft.jsonl"
led = "cloud_train_pack/dataset/virtu_worldmodel_fix_sft_ledger.json"
assert os.path.exists(sft) and os.path.exists(led), "missing worldmodel corpus or ledger"
exp = json.load(open(led, "r", encoding="utf-8")).get("output_sha256", "")
h = hashlib.sha256(open(sft, "rb").read()).hexdigest()
assert exp == h, f"worldmodel ledger mismatch: {exp} != {h}"
print("[SELFTEST] PASS: worldmodel ledger SHA256 verified")
PY
      ;;
    safety)
      "$PY" "${SCRIPT_DIR}/train_safety_cloud.py" --selftest
      "$PY" "${SCRIPT_DIR}/deploy_safety_repair.py" --selftest
      ;;
    vericut96|vericut96-v2|vericut96_v2)
      "$PY" "${REPO_ROOT}/scripts/build_vericut96_cloud_datasets.py" --selftest
      "$PY" "${SCRIPT_DIR}/train_turnkey.py" --selftest
      "$PY" "${REPO_ROOT}/scripts/train_dpo_all90.py" --self-test
      "$PY" "${REPO_ROOT}/scripts/gate_all90_dataset.py" --self-test
      "$PY" "${SCRIPT_DIR}/deploy_trained_adapter.py" --selftest
      if [[ "$TRACK" == "vericut96-v2" || "$TRACK" == "vericut96_v2" ]] && [[ -f "${SCRIPT_DIR}/dataset_v2/vericut96_v2_sft_mix_ledger.json" ]]; then
        TRACK_VERSION=v2 bash "${SCRIPT_DIR}/run_vericut96.sh" --selftest
      fi
      ;;
    vericut-e|vericut_e)
      bash "${SCRIPT_DIR}/run_vericut_e_training.sh" --selftest
      ;;
    six-software|six_software)
      bash "${SCRIPT_DIR}/run_six_software_real.sh" --selftest
      ;;
    *)
      echo "[FATAL] 未知产线 --track=$TRACK (可选: master-8b|13b|all90|worldmodel|safety|vericut96|vericut96-v2|vericut-e|six-software)" >&2
      exit 2
      ;;
  esac
}

if [[ "$SELFTEST_ONLY" -eq 1 ]]; then
  for _t in "${TRACK_LIST[@]}"; do
    TRACK="$_t"
    echo "[Selftest] track=$TRACK | PY=$PY"
    run_track_selftest
  done
  exit 0
fi

mkdir -p "${REPO_ROOT}/runs"
if [[ "${#TRACK_LIST[@]}" -gt 1 ]]; then
  LOCK_TAG="chain"
  LOG_OUT="${REPO_ROOT}/runs/start_cloud_chain.log"
else
  LOCK_TAG="${TRACK}"
  LOG_OUT="${REPO_ROOT}/runs/start_cloud_${TRACK}.log"
fi

# 单实例排他文件锁（防止云端窗口误触多次并发开训）
LOCK_FILE="${SCRIPT_DIR}/.start_cloud_train_now_${LOCK_TAG}.lock"
exec 9>"$LOCK_FILE"
flock -n 9 || {
  echo "[FATAL] 已有产线 track=${TRACKS_CSV:-$TRACK} 的开机启动器持有锁 ($LOCK_FILE)，拒绝并发启动！" >&2
  exit 1
}

echo "======================================================================"
echo "  Virtu 上线马上开训 | tracks=${TRACKS_CSV:-$TRACK} | Python=${PY} | $(date '+%Y-%m-%d %H:%M:%S')"
echo "======================================================================"

# Stage 0: 开机等待 GPU 就绪 + 真实 fp16 torch.matmul 实算探测 + /root/venv25 自愈
wait_for_gpu_ready() {
  local wait_s="$1"
  local elapsed=0
  while true; do
    if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi --query-gpu=index,name,memory.total,memory.free --format=csv,noheader >/dev/null 2>&1; then
      nvidia-smi --query-gpu=index,name,memory.total,memory.free --format=csv,noheader
      return 0
    fi
    if [[ "$elapsed" -ge "$wait_s" ]]; then
      echo "[FATAL] 等待 GPU 就绪超时 (${wait_s}s)，未找到可用 nvidia-smi / CUDA 设备，无法启动 GPU 训练！" >&2
      exit 2
    fi
    if [[ "$elapsed" -eq 0 ]]; then
      echo "[Boot] GPU/nvidia-smi 尚未就绪，轮询等待最多 ${wait_s}s ..."
    fi
    sleep 3
    elapsed=$((elapsed + 3))
  done
}
wait_for_gpu_ready "$WAIT_GPU_S"

probe_gpu_matmul() {
  local py_bin="$1"
  "$py_bin" - <<'PY' >/dev/null 2>&1
import torch, transformers, peft, datasets, accelerate, trl, safetensors
assert torch.cuda.is_available(), "cuda unavailable"
a = torch.randn(16, 16, device="cuda", dtype=torch.float16)
c = torch.matmul(a, a)
torch.cuda.synchronize()
assert tuple(c.shape) == (16, 16) and torch.isfinite(c).all()
PY
}

PIP_INDEX="${PIP_INDEX:-https://pypi.tuna.tsinghua.edu.cn/simple}"
if ! probe_gpu_matmul "$PY"; then
  echo "[Env] $PY 未通过 fp16 torch.matmul + 核心依赖探测，尝试修复或启用 /root/venv25 ..."
  "$PY" -m pip install -q "transformers>=4.51.0,<5.0.0" "peft>=0.13.0,<0.16.0" "datasets>=2.18.0,<4.0.0" "accelerate>=0.33.0,<2.0.0" "trl>=0.12.0,<0.18.0" modelscope safetensors sentencepiece -i "$PIP_INDEX" || true
  if ! probe_gpu_matmul "$PY"; then
    if [[ ! -x /root/venv25/bin/python ]]; then
      "$PY" -m venv /root/venv25 --system-site-packages || "$PY" -m venv /root/venv25
    fi
    /root/venv25/bin/python -m pip install -q "transformers>=4.51.0,<5.0.0" "peft>=0.13.0,<0.16.0" "datasets>=2.18.0,<4.0.0" "accelerate>=0.33.0,<2.0.0" "trl>=0.12.0,<0.18.0" modelscope safetensors sentencepiece -i "$PIP_INDEX"
    if probe_gpu_matmul /root/venv25/bin/python; then
      PY="/root/venv25/bin/python"
    else
      echo "[FATAL] GPU fp16 torch.matmul 实算探测失败，拒绝盲跑烧卡！" >&2
      exit 2
    fi
  fi
fi
export ECT_PYTHON="$PY"
echo "[Stage0] PASS: PY=$PY 通过 fp16 torch.matmul + SFT/DPO 依赖实算探测"

if [[ "$SKIP_SELFTEST" -eq 0 ]]; then
  for _t in "${TRACK_LIST[@]}"; do
    TRACK="$_t"
    echo "[Stage1] 执行产线 $TRACK 离线门禁自检..."
    run_track_selftest
  done
  TRACK="${TRACK_LIST[0]}"
fi

dispatch_foreground() {
  case "$TRACK" in
    master-8b|all90)
      if [[ "${#EXTRA_ARGS[@]}" -gt 0 ]]; then
        bash "${SCRIPT_DIR}/run.sh" --fg "${EXTRA_ARGS[@]}"
      else
        bash "${SCRIPT_DIR}/run.sh" --fg
      fi
      ;;
    13b)
      if [[ "${#EXTRA_ARGS[@]}" -gt 0 ]]; then
        bash "${SCRIPT_DIR}/run_13b_evolution_train.sh" "${EXTRA_ARGS[@]}"
      else
        bash "${SCRIPT_DIR}/run_13b_evolution_train.sh"
      fi
      ;;
    worldmodel)
      if [[ "${#EXTRA_ARGS[@]}" -gt 0 ]]; then
        bash "${SCRIPT_DIR}/run_worldmodel_fix.sh" "${EXTRA_ARGS[@]}"
      else
        bash "${SCRIPT_DIR}/run_worldmodel_fix.sh"
      fi
      ;;
    safety)
      if [[ "${#EXTRA_ARGS[@]}" -gt 0 ]]; then
        bash "${SCRIPT_DIR}/run_safety_repair.sh" "${EXTRA_ARGS[@]}"
      else
        bash "${SCRIPT_DIR}/run_safety_repair.sh"
      fi
      ;;
    vericut96)
      bash "${SCRIPT_DIR}/run_vericut96.sh" --fg ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}
      ;;
    vericut96-v2|vericut96_v2)
      TRACK_VERSION=v2 bash "${SCRIPT_DIR}/run_vericut96.sh" --fg ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}
      ;;
    vericut-e|vericut_e)
      bash "${SCRIPT_DIR}/run_vericut_e_training.sh" --fg ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}
      ;;
    six-software|six_software)
      bash "${SCRIPT_DIR}/run_six_software_real.sh" --fg ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}
      ;;
  esac
}

if [[ "$BG_MODE" -eq 1 ]]; then
  # 释放调度锁再由后台常驻训练，使各产线子锁接管并打印真实 8s 存活探针
  flock -u 9
  exec 9>&-
  rm -f "$LOG_OUT"
  if [[ "${#TRACK_LIST[@]}" -gt 1 ]]; then
    nohup bash "${BASH_SOURCE[0]}" --tracks "$TRACKS_CSV" --skip-selftest --wait-gpu-s 0 ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"} > "$LOG_OUT" 2>&1 < /dev/null &
  else
    nohup bash "${BASH_SOURCE[0]}" --track "$TRACK" --skip-selftest --wait-gpu-s 0 ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"} > "$LOG_OUT" 2>&1 < /dev/null &
  fi
  BG_PID=$!
  sleep 8
  if ! kill -0 "$BG_PID" 2>/dev/null; then
    echo "[FATAL] 后台进程在 8s 内异常退出 (PID=$BG_PID)，日志尾部:" >&2
    tail -n 50 "$LOG_OUT" >&2 || true
    exit 1
  fi
  if grep -q "\[FATAL\]" "$LOG_OUT" 2>/dev/null; then
    echo "[FATAL] 日志出现 [FATAL]，立即告警:" >&2
    tail -n 50 "$LOG_OUT" >&2 || true
    exit 1
  fi
  echo "[LAUNCHED] 后台训练已稳态启动 tracks=${TRACKS_CSV:-$TRACK} PID=$BG_PID | tail -f $LOG_OUT"
  exit 0
fi

for _t in "${TRACK_LIST[@]}"; do
  TRACK="$_t"
  echo "[Chain] 开始产线 track=${TRACK} | $(date '+%Y-%m-%d %H:%M:%S')"
  dispatch_foreground
  echo "[Chain] 完成产线 track=${TRACK} | $(date '+%Y-%m-%d %H:%M:%S')"
done
