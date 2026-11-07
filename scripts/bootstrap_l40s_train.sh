#!/usr/bin/env bash
# Route A one-click bootstrap: NVIDIA L40S 48GB, bf16 LoRA, max_len 4096.
# Installs deps only when missing (reuses the image's CUDA torch and a local
# Qwen3-8B copy when present), then runs preflight -> smoke -> full training.
# After uploading the bundle, one command is enough:
#   tar xzf virtu_bundle_route_A.tar.gz -C ~ && bash ~/virtu/scripts/bootstrap_l40s_train.sh
# Safe to rerun: resumes from the newest checkpoint if one exists.
set -Eeuo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ -z "${WORKDIR:-}" ]; then
  for cand in /data /root/autodl-tmp /workspace /root/public-storage; do
    if [ -d "$cand" ] && [ -w "$cand" ]; then WORKDIR="$cand/virtu_train"; break; fi
  done
  WORKDIR="${WORKDIR:-/root/virtu_train}"
fi
BASE="${BASE:-$WORKDIR/models/Qwen3-8B}"
DATA="${DATA:-$REPO_ROOT/data/train/virtu_v3/train}"
OUTPUT="${OUTPUT:-$WORKDIR/out/virtu_hardened_v1_lora}"
SMOKE_OUT="${SMOKE_OUT:-$WORKDIR/out/virtu_hardened_v1_smoke}"
VENV="${VENV:-$WORKDIR/.venv-l40s}"
TRAINER="$REPO_ROOT/scripts/train_virtu_l40s.py"
LOGDIR="$WORKDIR/logs"
STATUS="$WORKDIR/TRAIN_STATUS.json"
MAX_HOURS="${MAX_HOURS:-8}"
TORCH_INDEX="${TORCH_INDEX:-https://mirrors.aliyun.com/pytorch-wheels/cu124}"
PIP_INDEX="${PIP_INDEX:-https://pypi.tuna.tsinghua.edu.cn/simple}"
SKIP_SMOKE="${SKIP_SMOKE:-0}"
CURRENT_LOG="$LOGDIR/bootstrap.log"

mkdir -p "$WORKDIR" "$LOGDIR" "$(dirname "$OUTPUT")" "$(dirname "$SMOKE_OUT")"
export PYTHONUNBUFFERED=1 TOKENIZERS_PARALLELISM=false CUDA_VISIBLE_DEVICES=0
export MODELSCOPE_CACHE="$WORKDIR/.modelscope" HF_HOME="$WORKDIR/.hf"
export TRANSFORMERS_CACHE="$WORKDIR/.hf"

log() { echo "[$(date '+%F %T')] $*" | tee -a "$CURRENT_LOG"; }

status() {
  local stage="$1" state="$2" extra="${3:-}"
  python3 - "$STATUS" "$stage" "$state" "$CURRENT_LOG" "$OUTPUT" "$$" "$extra" <<'PY' 2>/dev/null || true
import json, sys, time
path, stage, state, log, out, pid, extra = sys.argv[1:]
json.dump({
    "route": "A-L40S", "stage": stage, "status": state,
    "time": time.strftime("%Y-%m-%d %H:%M:%S"),
    "log": log, "output": out, "pid": int(pid), "extra": extra,
}, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
PY
}

fail() {
  log "FAIL: $*"
  status "FAILED" "FAILED" "$*"
  echo "--- last 30 log lines ($CURRENT_LOG) ---"
  tail -n 30 "$CURRENT_LOG" || true
  exit 1
}

trap 'rc=$?; if [ "$rc" -ne 0 ]; then status "ERROR" "FAILED" "line=$LINENO rc=$rc"; fi' ERR

log "Route A L40S bootstrap"
log "repo=$REPO_ROOT workdir=$WORKDIR base=$BASE data=$DATA output=$OUTPUT"
log "max_hours=$MAX_HOURS skip_smoke=$SKIP_SMOKE"

# ---------- 1. hardware / disk ----------
command -v nvidia-smi >/dev/null 2>&1 || fail "nvidia-smi not found; is this a GPU instance?"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader || true
GPU_NAME="$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)"
GPU_MEM_MB="$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -1 | tr -d ' ')"
log "gpu=$GPU_NAME ${GPU_MEM_MB}MB"
if [ "$GPU_MEM_MB" -lt 40000 ]; then
  log "WARN: ${GPU_MEM_MB}MB is not a 48GB L40S. Route A assumes bf16 unquantized; "
  log "      for a 32GB V100 use scripts/bootstrap_v100_train.sh, for <=24GB add --load-4bit"
fi
FREE_KB="$(df -Pk "$WORKDIR" | awk 'NR==2{print $4}')"
log "free disk at $WORKDIR: $((FREE_KB / 1024 / 1024))GB"
if [ -f "$BASE/config.json" ]; then NEED_KB=8000000; else NEED_KB=30000000; fi
if [ "$FREE_KB" -lt "$NEED_KB" ]; then
  fail "need >=$((NEED_KB / 1000000))GB free at $WORKDIR (base local=$([ -f "$BASE/config.json" ] && echo yes || echo no) + venv/checkpoints). Point WORKDIR at a larger disk."
fi

# ---------- 2. repo prerequisites ----------
ls "$DATA"/*.jsonl >/dev/null 2>&1 || fail "training data missing at $DATA; upload/extract the bundle first"
log "data files: $(ls "$DATA"/*.jsonl | wc -l)"
[ -f "$DATA/../manifest.json" ] || [ -f "$DATA/../virtu_fix_text_sft_v1.manifest.json" ] \
  || fail "corpus manifest missing next to $DATA; the sha256 gate is mandatory (rebuild with scripts/build_train_v3.py)"
log "corpus manifest: $([ -f "$DATA/../manifest.json" ] && echo "$DATA/../manifest.json" || echo "$DATA/../virtu_fix_text_sft_v1.manifest.json")"
[ -f "$REPO_ROOT/train_virtu.py" ] \
  || fail "train_virtu.py missing at repo root (the loader imports load_and_tokenize from it)"
[ -f "$REPO_ROOT/requirements-l40s.txt" ] || fail "requirements-l40s.txt missing at repo root"
[ -f "$TRAINER" ] || fail "scripts/train_virtu_l40s.py missing"

# ---------- 3. python env + deps (reuse a CUDA torch if the image already has one) ----------
has_cuda_torch() {
  "$1" - <<'PY' >/dev/null 2>&1
import sys
try:
    import torch
except Exception:
    sys.exit(1)
sys.exit(0 if torch.version.cuda and torch.cuda.is_available() else 1)
PY
}

CURRENT_LOG="$LOGDIR/install.log"
status INSTALL RUNNING
PY=""
if [ "${FORCE_VENV:-0}" != "1" ]; then
  for cand in python3 /opt/conda/bin/python3.11 /opt/conda/bin/python3 /usr/local/bin/python3; do
    if command -v "$cand" >/dev/null 2>&1 && has_cuda_torch "$cand"; then
      PY="$(command -v "$cand")"
      log "reusing preinstalled CUDA torch via $PY: $("$PY" -c 'import torch; print(torch.__version__, "cuda", torch.version.cuda)')"
      break
    fi
  done
fi
if [ -z "$PY" ]; then
  if [ ! -x "$VENV/bin/python" ]; then
    log "creating venv at $VENV"
    if ! python3 -m venv "$VENV" >/dev/null 2>&1; then
      log "plain venv failed; trying apt python3-venv"
      { apt-get update -qq && apt-get install -y -qq python3-venv; } >/dev/null 2>&1 || true
      python3 -m venv "$VENV" \
        || fail "cannot create a venv at $VENV. As root: apt-get install -y python3-venv; or VENV=/root/miniconda3"
    fi
  fi
  PY="$VENV/bin/python"
  [ -x "$PY" ] || fail "venv python missing at $PY"
  "$PY" -m pip install --upgrade pip >/dev/null 2>&1 || true
fi
"$PY" -c "import sys; print('[python]', sys.version.split()[0], sys.executable)"

install_torch() {
  "$PY" -m pip install torch==2.5.0 --index-url https://download.pytorch.org/whl/cu124 >>"$CURRENT_LOG" 2>&1 && return 0
  log "official cu124 index failed; trying aliyun mirror"
  "$PY" -m pip install torch==2.5.0 --index-url "$TORCH_INDEX" >>"$CURRENT_LOG" 2>&1 && return 0
  log "aliyun mirror failed; trying PyPI"
  "$PY" -m pip install torch==2.5.0 >>"$CURRENT_LOG" 2>&1
}

if has_cuda_torch "$PY"; then
  log "torch already usable; skipping the torch download"
else
  log "installing torch 2.5.0 cu124"
  install_torch || fail "torch install failed; see $CURRENT_LOG"
fi
"$PY" - <<'PY' || fail "torch is CPU-only; install a CUDA 12.4 wheel"
import sys, torch
print("[torch]", torch.__version__, "cuda", torch.version.cuda, "available", torch.cuda.is_available())
if torch.version.cuda is None or not torch.cuda.is_available():
    sys.exit(1)
PY

install_reqs() {
  "$PY" -m pip install -r "$REPO_ROOT/requirements-l40s.txt" -i "$PIP_INDEX" >>"$CURRENT_LOG" 2>&1 && return 0
  "$PY" -m pip install -r "$REPO_ROOT/requirements-l40s.txt" >>"$CURRENT_LOG" 2>&1 && return 0
  "$PY" -m pip install -r "$REPO_ROOT/requirements-l40s.txt" --break-system-packages >>"$CURRENT_LOG" 2>&1
}
install_reqs || fail "requirements install failed; see $CURRENT_LOG"
status INSTALL OK

# ---------- 4. base model (reuse a local copy if the image already has one) ----------
find_local_base() {
  local c
  for c in "$BASE" "$WORKDIR/models/Qwen3-8B" /root/models/Qwen3-8B \
           /root/autodl-tmp/models/Qwen3-8B /data/models/Qwen3-8B \
           /root/.cache/modelscope/hub/Qwen/Qwen3-8B; do
    if [ -f "$c/config.json" ]; then echo "$c"; return 0; fi
  done
  for c in /root/.cache/huggingface/hub/models--Qwen--Qwen3-8B/snapshots/*; do
    if [ -f "$c/config.json" ]; then echo "$c"; return 0; fi
  done
  return 1
}

download_base() {
  "$PY" - "$BASE" >>"$CURRENT_LOG" 2>&1 <<'PY'
import os, sys

target = sys.argv[1]
try:
    from modelscope import snapshot_download
    print("modelscope ->", snapshot_download("Qwen/Qwen3-8B", local_dir=target))
except Exception as exc:
    print("modelscope failed:", repr(exc))
    os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
    from huggingface_hub import snapshot_download as hf_snapshot
    print("huggingface ->", hf_snapshot("Qwen/Qwen3-8B", local_dir=target))
PY
}

if FOUND_BASE="$(find_local_base)"; then
  BASE="$FOUND_BASE"
  log "reusing local base model: $BASE"
else
  if [[ "$BASE" == /* ]]; then
    CURRENT_LOG="$LOGDIR/download_base.log"
    status DOWNLOAD_BASE RUNNING
    log "downloading Qwen/Qwen3-8B -> $BASE (ModelScope, HF-mirror fallback; ~16GB)"
    download_base || fail "base model download failed; see $CURRENT_LOG"
    [ -f "$BASE/config.json" ] || fail "base download incomplete: $BASE"
    log "base ready: $BASE"
  else
    log "BASE is a repo id ($BASE); the loader will download it"
  fi
fi
status DOWNLOAD_BASE OK

# ---------- 5. preflight + length audit ----------
CURRENT_LOG="$LOGDIR/preflight.log"
status PREFLIGHT RUNNING
"$PY" "$TRAINER" --base "$BASE" --data "$DATA" --preflight >>"$CURRENT_LOG" 2>&1 \
  || fail "preflight failed; see $CURRENT_LOG"
# Truncation census is cheap and decides whether --max-len 4096 is honest.
"$PY" "$TRAINER" --base "$BASE" --data "$DATA" --audit-lengths >>"$CURRENT_LOG" 2>&1 \
  || log "WARN: length audit failed; continuing"
status PREFLIGHT OK

# ---------- 6. smoke, walking down a fixed ladder ----------
CHOSEN_FLAGS=""
SMOKE_FOUND=0
if [ "$SKIP_SMOKE" != "1" ]; then
  rm -rf "$SMOKE_OUT"
  LADDER=(
    ""
    "--max-len 4096"
    "--max-len 3072"
    "--max-len 3072 --batch 1"
    "--max-len 2048 --batch 1"
    "--load-4bit"
    "--load-4bit --max-len 3072 --batch 1"
  )
  run_smoke() {
    local tag="$1"; shift
    CURRENT_LOG="$LOGDIR/smoke_$tag.log"
    log "smoke[$tag] flags: $*"
    "$PY" "$TRAINER" --base "$BASE" --data "$DATA" --smoke --output "$SMOKE_OUT" "$@" \
      >>"$CURRENT_LOG" 2>&1
  }
  status SMOKE RUNNING
  for i in "${!LADDER[@]}"; do
    flags="${LADDER[$i]}"
    # shellcheck disable=SC2086
    if run_smoke "try$i" $flags; then
      CHOSEN_FLAGS="$flags"
      SMOKE_FOUND=1
      log "smoke OK on rung $i with flags: [${flags:-default}]"
      break
    fi
    log "smoke rung $i [$flags] failed; last lines:"
    tail -n 6 "$LOGDIR/smoke_try$i.log" 2>/dev/null || true
  done
  if [ "$SMOKE_FOUND" -ne 1 ]; then
    fail "every smoke rung failed; do not burn GPU hours on the full run. See $LOGDIR/smoke_try*.log"
  fi
  status SMOKE OK "${CHOSEN_FLAGS:-default}"
else
  log "SKIP_SMOKE=1; full training without the 20-step smoke"
fi

# ---------- 7. full training (timeout guard) ----------
CURRENT_LOG="$LOGDIR/train.log"
status TRAIN RUNNING
LATEST="$(ls -d "$OUTPUT"/checkpoint-* 2>/dev/null | sort -V | tail -1 || true)"
TRAIN_CMD=("$PY" "$TRAINER" --base "$BASE" --data "$DATA" --output "$OUTPUT")
if [ -n "$CHOSEN_FLAGS" ]; then
  # shellcheck disable=SC2206
  TRAIN_CMD+=($CHOSEN_FLAGS)
fi
if [ -n "$LATEST" ]; then
  log "resuming from $LATEST"
  TRAIN_CMD+=(--resume "$LATEST")
fi
log "training command: ${TRAIN_CMD[*]}"
set +e
if command -v timeout >/dev/null 2>&1; then
  timeout --signal=TERM "$((MAX_HOURS * 3600))s" "${TRAIN_CMD[@]}" >>"$CURRENT_LOG" 2>&1
  RC=$?
else
  "${TRAIN_CMD[@]}" >>"$CURRENT_LOG" 2>&1
  RC=$?
fi
set -e
if [ "$RC" -eq 124 ]; then
  status TRAIN TIMEOUT "max_hours=$MAX_HOURS; rerun to resume from checkpoint"
  fail "training hit MAX_HOURS=${MAX_HOURS}h; checkpoints kept; rerun this script to resume"
fi
[ "$RC" -eq 0 ] || fail "training failed rc=$RC; see $CURRENT_LOG"

# ---------- 8. verify receipt ----------
"$PY" - "$OUTPUT/training_receipt.json" <<'PY' || fail "training receipt missing or not COMPLETED"
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
assert d.get("status") == "COMPLETED", d.get("status")
print("[receipt] status=COMPLETED route=", d.get("route"), "attn=", d.get("attention"),
      "final_loss=", d.get("final_loss"), "runtime_s=", d.get("train_runtime_s"),
      "s_per_step=", d.get("s_per_step"), "peak_vram_gb=", d.get("peak_vram_gb"))
PY
status DONE COMPLETED
ADAPTER_MB="$(du -sm "$OUTPUT" | awk '{print $1}')"
log "adapter=$OUTPUT size=${ADAPTER_MB}MB (plan gate <=350MB)"
if [ "$ADAPTER_MB" -gt 350 ]; then
  log "WARN: adapter exceeds the 350MB gate; inspect $OUTPUT before merging"
fi
touch "$WORKDIR/DONE.flag"
log "DONE adapter=$OUTPUT"
log "next: python $REPO_ROOT/scripts/merge_numpy.py --base $BASE --out $WORKDIR/out/virtu_hardened_v1 --mode delta --lora $OUTPUT --weight 1.0"
log "eval: 240-case virtu_eval + 200 formula holdout; never merge a SMOKE_ONLY adapter"
