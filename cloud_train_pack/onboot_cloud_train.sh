#!/usr/bin/env bash
# ==============================================================================
# cloud_train_pack/onboot_cloud_train.sh
# 云端实例开机即训 (Auto-Boot / Auto-Extract / GPU Wait / Dispatch) 启动器
#
# 适用场景：
#   1. AutoDL / 智星云 / 阿里云 / Vast 等“开机启动命令” (/root/onstart.sh)
#   2. 云机刚启动后自动等待 GPU (/dev/nvidia*) 就绪
#   3. 若存在本地压缩包 (virtu_*_bundle*.tar.gz) 且未解包，先过 SHA256 校验再安全解压
#   4. 单实例 flock 锁保护，防止平台重复触发 onstart 导致双开爆显存
#   5. 立即转调 start_cloud_train_now.sh (--tracks / --track) 后台稳态开训，并写 onboot_receipt.json
#
# 用法：
#   bash onboot_cloud_train.sh --track vericut96-v2
#   bash onboot_cloud_train.sh --tracks vericut96-v2,vericut-e,six-software --wait-gpu-s 180
#   bash onboot_cloud_train.sh --dir /root/autodl-tmp/virtu_train --bundle /root/autodl-tmp/virtu_vericut96_v2_bundle.tar.gz --track vericut96-v2
#   bash onboot_cloud_train.sh --selftest
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_DIR="${VIRTU_WORKDIR:-}"
BUNDLE_ARG="${VIRTU_BUNDLE:-}"
TRACK="${VIRTU_CLOUD_TRACK:-vericut96-v2}"
TRACKS_CSV="${VIRTU_CLOUD_TRACKS:-}"
WAIT_GPU_S="${VIRTU_WAIT_GPU_SECONDS:-120}"
BG_MODE=1
SKIP_SELFTEST=0
SELFTEST_ONLY=0
EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dir|--workdir)
      WORK_DIR="${2:-}"
      shift 2
      ;;
    --dir=*|--workdir=*)
      WORK_DIR="${1#*=}"
      shift
      ;;
    --bundle)
      BUNDLE_ARG="${2:-}"
      shift 2
      ;;
    --bundle=*)
      BUNDLE_ARG="${1#*=}"
      shift
      ;;
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
      WAIT_GPU_S="${2:-120}"
      shift 2
      ;;
    --wait-gpu-s=*)
      WAIT_GPU_S="${1#*=}"
      shift
      ;;
    --fg)
      BG_MODE=0
      shift
      ;;
    --bg)
      BG_MODE=1
      shift
      ;;
    --skip-selftest)
      SKIP_SELFTEST=1
      shift
      ;;
    --selftest|--self-test)
      SELFTEST_ONLY=1
      shift
      ;;
    *)
      EXTRA_ARGS+=("$1")
      shift
      ;;
  esac
done

export PATH="/root/venv25/bin:/opt/conda/bin:/usr/local/miniconda3/bin:${PATH}"

verify_bundle_sha256() {
  local archive="$1"
  local sidecar="${archive}.sha256"
  if [[ ! -f "$sidecar" ]]; then
    echo "[OnBoot] 未发现 ${sidecar}，跳过 sidecar SHA256（若需强制校验请上传 .sha256）"
    return 0
  fi
  local exp act sha_target="$archive"
  if command -v cygpath >/dev/null 2>&1; then
    sha_target="$(cygpath -u "$archive")"
  fi
  exp="$(awk '{val=$1; sub(/^\\/, "", val); print tolower(val); exit}' "$sidecar")"
  if [[ "${#exp}" -ne 64 ]]; then
    echo "[FATAL] 无效的 SHA256 sidecar 文件: $sidecar" >&2
    return 1
  fi
  if command -v sha256sum >/dev/null 2>&1; then
    act="$(sha256sum "$sha_target" | awk '{val=$1; sub(/^\\/, "", val); print tolower(val); exit}')"
  else
    local py_cmd
    py_cmd="$(command -v python3 || command -v python || true)"
    if [[ -z "$py_cmd" ]]; then
      echo "[FATAL] 缺少 sha256sum 与 python，无法校验证书 $sidecar" >&2
      return 1
    fi
    local py_target="$archive"
    if command -v cygpath >/dev/null 2>&1; then
      py_target="$(cygpath -w "$sha_target")"
    fi
    act="$("$py_cmd" -c "import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest().lower())" "$py_target")"
  fi
  if [[ "$exp" != "$act" ]]; then
    echo "[FATAL] 压缩包 SHA256 校验失败: expected=$exp actual=$act ($archive)" >&2
    return 1
  fi
  echo "[OnBoot] PASS: SHA256 verified ($archive -> ${act:0:12}...)"
  return 0
}

resolve_workdir() {
  if [[ -n "$WORK_DIR" ]]; then
    mkdir -p "$WORK_DIR"
    echo "$(cd "$WORK_DIR" && pwd)"
    return 0
  fi
  if [[ -d "${SCRIPT_DIR}/virtu_eval" ]] && [[ -f "${SCRIPT_DIR}/start_cloud_train_now.sh" || -f "${SCRIPT_DIR}/run_vericut96.sh" ]]; then
    echo "$SCRIPT_DIR"
    return 0
  fi
  if [[ -d "${SCRIPT_DIR}/../virtu_eval" ]] && [[ -f "${SCRIPT_DIR}/start_cloud_train_now.sh" ]]; then
    echo "$(cd "${SCRIPT_DIR}/.." && pwd)"
    return 0
  fi
  local cand
  for cand in "/root/autodl-tmp/virtu_vericut96_v2" "/root/autodl-tmp/virtu_vericut96" "/root/autodl-tmp/virtu_train" "/workspace/virtu_train" "/root/virtu_train"; do
    if [[ -d "$cand" ]]; then
      echo "$cand"
      return 0
    fi
  done
  echo "$SCRIPT_DIR"
}

find_bundle_candidate() {
  local wd="$1"
  if [[ -n "$BUNDLE_ARG" ]]; then
    echo "$BUNDLE_ARG"
    return 0
  fi
  local search_dirs=("$wd" "$SCRIPT_DIR" "/root/autodl-tmp" "/workspace" "/root")
  local dir f
  for dir in "${search_dirs[@]}"; do
    [[ -d "$dir" ]] || continue
    for f in \
      "$dir/virtu_vericut96_v2_bundle.tar.gz" \
      "$dir/virtu_vericut_e_bundle.tar.gz" \
      "$dir/virtu_six_software_bundle.tar.gz" \
      "$dir/virtu_vericut96_bundle.tar.gz" \
      "$dir/cloud_train_pack.tar.gz"; do
      if [[ -f "$f" ]]; then
        echo "$f"
        return 0
      fi
    done
  done
  return 1
}

if [[ "$SELFTEST_ONLY" -eq 1 ]]; then
  command -v bash >/dev/null 2>&1 || { echo "[FATAL] bash missing" >&2; exit 2; }
  WORK_DIR="$(resolve_workdir)"
  echo "[SELFTEST] PASS: onboot_cloud_train.sh ready (work_dir=$WORK_DIR, default_track=$TRACK, wait_gpu_s=$WAIT_GPU_S)"
  exit 0
fi

WORK_DIR="$(resolve_workdir)"
mkdir -p "${WORK_DIR}/runs"

LOCK_FILE="${WORK_DIR}/.onboot_cloud_train.lock"
USE_FLOCK=0
if command -v flock >/dev/null 2>&1 && [[ "$(uname -s 2>/dev/null || true)" == Linux* ]]; then
  USE_FLOCK=1
  exec 9>"$LOCK_FILE"
  flock -n 9 || {
    echo "[FATAL] 已有 onboot_cloud_train 实例持有锁 ($LOCK_FILE)，拒绝并发拉起！" >&2
    exit 1
  }
fi

echo "======================================================================"
echo "  Virtu On-Boot Cloud Auto-Trainer | work_dir=${WORK_DIR} | $(date '+%Y-%m-%d %H:%M:%S')"
echo "======================================================================"

# 1. 开机自动解包（仅当显式指定 --bundle 或当前工作目录尚未解出运行器时触发）
RUNNER_NOW=""
if [[ -f "${WORK_DIR}/cloud_train_pack/start_cloud_train_now.sh" ]]; then
  RUNNER_NOW="${WORK_DIR}/cloud_train_pack/start_cloud_train_now.sh"
elif [[ -f "${WORK_DIR}/start_cloud_train_now.sh" ]]; then
  RUNNER_NOW="${WORK_DIR}/start_cloud_train_now.sh"
fi

BUNDLE_USED=""
if [[ -n "$BUNDLE_ARG" ]] || [[ -z "$RUNNER_NOW" && ! -f "${WORK_DIR}/run_vericut96.sh" && ! -f "${WORK_DIR}/run_vericut_e_training.sh" && ! -f "${WORK_DIR}/run_six_software_real.sh" && ! -f "${WORK_DIR}/run.sh" ]]; then
  BUNDLE_CAND="$(find_bundle_candidate "$WORK_DIR" || true)"
  if [[ -n "$BUNDLE_CAND" && -f "$BUNDLE_CAND" ]]; then
    verify_bundle_sha256 "$BUNDLE_CAND"
    echo "[OnBoot] 解压训练包 $BUNDLE_CAND -> $WORK_DIR ..."
    TAR_SRC="$BUNDLE_CAND"
    TAR_DST="$WORK_DIR"
    if command -v cygpath >/dev/null 2>&1; then
      TAR_SRC="$(cygpath -u "$BUNDLE_CAND")"
      TAR_DST="$(cygpath -u "$WORK_DIR")"
    fi
    tar -xzf "$TAR_SRC" -C "$TAR_DST"
    chmod +x "${WORK_DIR}"/*.sh "${WORK_DIR}"/cloud_train_pack/*.sh 2>/dev/null || true
    BUNDLE_USED="$BUNDLE_CAND"
  fi
fi

# 重新探测解包后的运行器
if [[ -f "${WORK_DIR}/cloud_train_pack/start_cloud_train_now.sh" ]]; then
  RUNNER_NOW="${WORK_DIR}/cloud_train_pack/start_cloud_train_now.sh"
elif [[ -f "${WORK_DIR}/start_cloud_train_now.sh" ]]; then
  RUNNER_NOW="${WORK_DIR}/start_cloud_train_now.sh"
fi

# 2. 等待 GPU (/dev/nvidia*) 上线就绪
wait_for_gpu_boot() {
  local max_s="$1"
  local elapsed=0
  while true; do
    if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi --query-gpu=index,name,memory.total,memory.free --format=csv,noheader >/dev/null 2>&1; then
      nvidia-smi --query-gpu=index,name,memory.total,memory.free --format=csv,noheader
      return 0
    fi
    if [[ "$elapsed" -ge "$max_s" ]]; then
      echo "[FATAL] 开机等待 GPU 超时 (${max_s}s)，放弃启动！" >&2
      exit 2
    fi
    if [[ "$elapsed" -eq 0 ]]; then
      echo "[OnBoot] 等待 GPU 驱动就绪 (最多 ${max_s}s) ..."
    fi
    sleep 3
    elapsed=$((elapsed + 3))
  done
}

wait_for_gpu_boot "$WAIT_GPU_S"
GPU_SUMMARY="$(nvidia-smi --query-gpu=index,name,memory.total --format=csv,noheader | head -n 1 || true)"

# 3. 写入开机回执 (onboot_receipt.json) 并调度开训
RECEIPT_PATH="${WORK_DIR}/runs/onboot_receipt.json"
PY_BIN="$(command -v python3 || command -v python || true)"
write_onboot_receipt() {
  local status="$1"
  local runner="$2"
  local pid_val="$3"
  local out_receipt="$RECEIPT_PATH"
  [[ -n "$PY_BIN" ]] || return 0
  if command -v cygpath >/dev/null 2>&1; then
    out_receipt="$(cygpath -w "$RECEIPT_PATH")"
  fi
  "$PY_BIN" - "$out_receipt" "$status" "$WORK_DIR" "${TRACKS_CSV:-$TRACK}" "$BUNDLE_USED" "$GPU_SUMMARY" "$runner" "$pid_val" <<'PY' || true
import json, sys, time
out_p, st, wd, trk, bdl, gpu, run, pid = sys.argv[1:9]
payload = {
    "schema_version": "1.0",
    "status": st,
    "work_dir": wd,
    "tracks": trk,
    "bundle": bdl,
    "gpu": gpu,
    "runner": run,
    "pid": pid,
    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
}
with open(out_p, "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)
PY
}

CMD_ARGS=()
if [[ -n "$TRACKS_CSV" ]]; then
  CMD_ARGS+=(--tracks "$TRACKS_CSV")
else
  CMD_ARGS+=(--track "$TRACK")
fi
if [[ "$SKIP_SELFTEST" -eq 1 ]]; then
  CMD_ARGS+=(--skip-selftest)
fi
if [[ "$BG_MODE" -eq 1 ]]; then
  CMD_ARGS+=(--bg)
fi

if [[ -n "$RUNNER_NOW" ]]; then
  CMD_ARGS+=(--wait-gpu-s 0)
  echo "[OnBoot] 调度统一启动器: $RUNNER_NOW ${CMD_ARGS[*]} ${EXTRA_ARGS[@]+"${EXTRA_ARGS[*]}"}"
  write_onboot_receipt "DISPATCHING" "$RUNNER_NOW" "$$"
  if [[ "$USE_FLOCK" -eq 1 ]]; then
    flock -u 9 || true
    exec 9>&-
  fi
  set +e
  bash "$RUNNER_NOW" "${CMD_ARGS[@]}" ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}
  rc=$?
  set -e
  if [[ "$rc" -eq 0 ]]; then
    write_onboot_receipt "LAUNCHED" "$RUNNER_NOW" "$$"
  else
    write_onboot_receipt "FAILED:$rc" "$RUNNER_NOW" "$$"
  fi
  exit "$rc"
fi

# 兜底：若只解包了单产线最小压缩包（不含 start_cloud_train_now.sh）
FALLBACK_RUNNER=""
FIRST_TRACK="${TRACK%%,*}"
if [[ -n "$TRACKS_CSV" ]]; then
  FIRST_TRACK="${TRACKS_CSV%%,*}"
fi
case "$FIRST_TRACK" in
  vericut96-v2|vericut96_v2)
    export TRACK_VERSION="v2"
    FALLBACK_RUNNER="${WORK_DIR}/run_vericut96.sh"
    ;;
  vericut96)
    FALLBACK_RUNNER="${WORK_DIR}/run_vericut96.sh"
    ;;
  vericut-e|vericut_e)
    FALLBACK_RUNNER="${WORK_DIR}/run_vericut_e_training.sh"
    ;;
  six-software|six_software)
    FALLBACK_RUNNER="${WORK_DIR}/run_six_software_real.sh"
    ;;
  master-8b|all90)
    FALLBACK_RUNNER="${WORK_DIR}/run.sh"
    ;;
esac

if [[ -n "$FALLBACK_RUNNER" && -f "$FALLBACK_RUNNER" ]]; then
  echo "[OnBoot] 调度单产线运行器: $FALLBACK_RUNNER (track=$FIRST_TRACK, bg=$BG_MODE)"
  write_onboot_receipt "DISPATCHING" "$FALLBACK_RUNNER" "$$"
  if [[ "$USE_FLOCK" -eq 1 ]]; then
    flock -u 9 || true
    exec 9>&-
  fi
  set +e
  if [[ "$BG_MODE" -eq 0 ]]; then
    bash "$FALLBACK_RUNNER" --fg ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}
  else
    bash "$FALLBACK_RUNNER" ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}
  fi
  rc=$?
  set -e
  if [[ "$rc" -eq 0 ]]; then
    write_onboot_receipt "LAUNCHED" "$FALLBACK_RUNNER" "$$"
  else
    write_onboot_receipt "FAILED:$rc" "$FALLBACK_RUNNER" "$$"
  fi
  exit "$rc"
fi

write_onboot_receipt "FAILED:NO_RUNNER" "" "$$"
echo "[FATAL] 工作目录 $WORK_DIR 下未找到 start_cloud_train_now.sh 或对应产线 run_*.sh！" >&2
exit 2
