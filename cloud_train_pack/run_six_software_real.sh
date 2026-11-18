#!/usr/bin/env bash
# ==============================================================================
# cloud_train_pack/run_six_software_real.sh
# Six-Software Real Assets (SOLIDWORKS 2021 / NX 12.0 / AutoCAD 2026 /
#   CIMCO Edit 2026 / VERICUT 9.6 / SSCNC 7.2) Cloud End-to-End SFT + DPO Runner
#
# 一上线直接执行即开训（自动守护后台 + 单实例锁 + GPU探针/自愈 + 八段硬门禁）：
#   bash run_six_software_real.sh                 # 默认自后台守护并立即开训 (推荐)
#   bash run_six_software_real.sh --fg            # 前台同步运行
#   bash run_six_software_real.sh --selftest      # 零 GPU 离线全门禁自检
#   bash run_six_software_real.sh --smoke-only    # 仅跑真实 GPU 12步SFT+2步DPO冒烟
# ==============================================================================
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_NAME="$(basename "${BASH_SOURCE[0]}")"
if [[ -d "${SCRIPT_DIR}/virtu_eval" && -d "${SCRIPT_DIR}/data/benchmark" ]]; then
  REPO_ROOT="${SCRIPT_DIR}"
else
  REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
fi
LOG_FILE="${VIRTU_TRAIN_LOG:-${SCRIPT_DIR}/train_six_software.log}"
LOCK_FILE="${SCRIPT_DIR}/.run_six_software_real.lock"

FOREGROUND=0
EXPLICIT_FG=0
SELFTEST=0
SMOKE_ONLY=0
SKIP_SMOKE=0
SKIP_DPO=0
QLORA=0
BASE_PATH=""
SFT_DATA_ARG=""
DPO_DATA_ARG=""
LEDGER_ARG=""
DELIV_NAME="six_software_real_deliverable.tar.gz"
TRACK_LABEL="six-software"
REUSE_SFT_DIR=""
EPOCHS="3.0"
DPO_EPOCHS="1"
LR="1.2e-4"
DPO_LR="5e-6"
BETA="0.2"
DPO_GRAD_ACCUM="8"
DPO_REF_MODE="sft"
MAX_HOURS="4.0"
MAX_STEPS="0"
MAX_LEN="0"
DPO_MAX_LEN="0"
GPU_ID="${VIRTU_GPU_ID:-${CUDA_VISIBLE_DEVICES:-0}}"
OUT_DIR="${SCRIPT_DIR}/output/six_software_real"

usage() {
  cat <<'EOF'
Usage: bash run_six_software_real.sh [options]
  --fg                    Run in foreground (default auto-daemonizes with nohup)
  --bg                    Explicit background daemonize (default behavior)
  --selftest              Run Stage 1+2 offline data/ledger/script gates (no GPU needed)
  --smoke-only            Run Stage 0-4 real GPU 12-step SFT + 2-step DPO smoke test & clean up
  --skip-smoke            Skip Stage 4 smoke test and start full SFT+DPO immediately
  --skip-dpo              Skip Stage 7 DPO stage (deliver SFT final_adapter)
  --reuse-sft <dir>       Skip Stage 6 SFT and reuse an existing verified SFT final_adapter
  --base <path>           Override local Qwen3-8B non-Instruct base path
  --epochs <float>        SFT epochs (default: 3.0)
  --dpo-epochs <int>      DPO epochs (default: 1)
  --lr <float>            SFT learning rate (default: 1.2e-4)
  --dpo-lr <float>        DPO learning rate (default: 5e-6)
  --beta <float>          DPO beta (default: 0.2)
  --dpo-grad-accum <int>  DPO gradient accumulation steps (default: 8)
  --dpo-ref-mode <mode>   DPO reference policy mode: sft|base (default: sft)
  --max-hours <float>     Total training budget hours (default: 4.0)
  --max-steps <int>       Optional max steps override (>0)
  --max-length <int>      SFT sequence cutoff (0=auto by GPU VRAM: 4096/3072/2048)
  --dpo-max-length <int>  DPO sequence cutoff (0=auto by GPU VRAM: 2048/1536)
  --gpu-id <id>           CUDA GPU index (default: 0)
  --qlora                 Force 4-bit NF4 QLoRA
  --out <dir>             Output directory (default: ./output/six_software_real)
  -h, --help              Show help
EOF
}

ORIG_ARGS=("$@")
while [[ $# -gt 0 ]]; do
  case "$1" in
    --fg) FOREGROUND=1; EXPLICIT_FG=1; shift ;;
    --bg)
      if [[ "${EXPLICIT_FG}" -eq 0 ]]; then
        FOREGROUND=0
      fi
      shift
      ;;
    --selftest) SELFTEST=1; FOREGROUND=1; shift ;;
    --smoke-only) SMOKE_ONLY=1; FOREGROUND=1; shift ;;
    --skip-smoke) SKIP_SMOKE=1; shift ;;
    --skip-dpo) SKIP_DPO=1; shift ;;
    --qlora) QLORA=1; shift ;;
    --reuse-sft) REUSE_SFT_DIR="${2:?Missing value for --reuse-sft}"; shift 2 ;;
    --base) BASE_PATH="${2:?Missing value for --base}"; shift 2 ;;
    --epochs) EPOCHS="${2:?Missing value for --epochs}"; shift 2 ;;
    --dpo-epochs) DPO_EPOCHS="${2:?Missing value for --dpo-epochs}"; shift 2 ;;
    --lr) LR="${2:?Missing value for --lr}"; shift 2 ;;
    --dpo-lr) DPO_LR="${2:?Missing value for --dpo-lr}"; shift 2 ;;
    --beta) BETA="${2:?Missing value for --beta}"; shift 2 ;;
    --dpo-grad-accum) DPO_GRAD_ACCUM="${2:?Missing value for --dpo-grad-accum}"; shift 2 ;;
    --dpo-ref-mode) DPO_REF_MODE="${2:?Missing value for --dpo-ref-mode}"; shift 2 ;;
    --max-hours) MAX_HOURS="${2:?Missing value for --max-hours}"; shift 2 ;;
    --max-steps) MAX_STEPS="${2:?Missing value for --max-steps}"; shift 2 ;;
    --max-length) MAX_LEN="${2:?Missing value for --max-length}"; shift 2 ;;
    --dpo-max-length) DPO_MAX_LEN="${2:?Missing value for --dpo-max-length}"; shift 2 ;;
    --gpu-id) GPU_ID="${2:?Missing value for --gpu-id}"; shift 2 ;;
    --out) OUT_DIR="${2:?Missing value for --out}"; shift 2 ;;
    --sft-data) SFT_DATA_ARG="${2:?Missing value for --sft-data}"; shift 2 ;;
    --dpo-data) DPO_DATA_ARG="${2:?Missing value for --dpo-data}"; shift 2 ;;
    --ledger) LEDGER_ARG="${2:?Missing value for --ledger}"; shift 2 ;;
    --deliverable-name) DELIV_NAME="${2:?Missing value for --deliverable-name}"; shift 2 ;;
    --track) TRACK_LABEL="${2:?Missing value for --track}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "[FATAL] Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

# Self-backgrounding wrapper when started directly on cloud SSH terminal
if [[ "${FOREGROUND}" -eq 0 ]]; then
  exec 9>"${LOCK_FILE}"
  if ! flock -n 9; then
    echo "[FATAL] Another six_software training instance already holds ${LOCK_FILE}" >&2
    exit 1
  fi
  flock -u 9 || true
  exec 9>&-

  mkdir -p "$(dirname "${LOG_FILE}")"
  : > "${LOG_FILE}"
  nohup bash "${SCRIPT_DIR}/${SCRIPT_NAME}" --fg ${ORIG_ARGS[@]+"${ORIG_ARGS[@]}"} > "${LOG_FILE}" 2>&1 < /dev/null &
  CHILD_PID=$!
  sleep 3
  if ! kill -0 "${CHILD_PID}" 2>/dev/null; then
    echo "[FATAL] Background process PID=${CHILD_PID} exited prematurely! Log tail:" >&2
    tail -n 60 "${LOG_FILE}" >&2 || true
    exit 1
  fi
  echo "[LAUNCHED] six_software_real running in background (PID=${CHILD_PID})"
  echo "[LOG]      ${LOG_FILE}"
  echo "[MONITOR]  tail -f ${LOG_FILE}"
  tail -n 20 "${LOG_FILE}" || true
  exit 0
fi

# Single-instance lock inside foreground GPU training runner (skip read-only --selftest)
if [[ "${SELFTEST}" -eq 0 ]] && command -v flock >/dev/null 2>&1; then
  exec 9>"${LOCK_FILE}"
  if ! flock -n 9; then
    echo "[FATAL] Concurrent six_software_real run detected (${LOCK_FILE}); aborting." >&2
    exit 1
  fi
fi

# Environment hardening
export PYTHONUNBUFFERED=1
export PYTHONUTF8=1
export TOKENIZERS_PARALLELISM=false
export PYTORCH_CUDA_ALLOC_CONF="${PYTORCH_CUDA_ALLOC_CONF:-expandable_segments:True}"
export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
export CUDA_VISIBLE_DEVICES="${GPU_ID}"
export VIRTU_ALLOW_DOWNLOAD="${VIRTU_ALLOW_DOWNLOAD:-1}"

pick_python() {
  local cands=()
  local cand
  [[ -n "${VIRTU_PYTHON:-}" ]] && cands+=("${VIRTU_PYTHON}")
  cands+=(
    "/root/venv25/bin/python"
    "/usr/local/miniconda3/envs/py312/bin/python"
    "/opt/conda/bin/python"
    "/usr/local/miniconda3/bin/python"
    "/root/miniconda3/bin/python"
    "${VIRTUAL_ENV:-}/bin/python"
    "${REPO_ROOT}/.venv/Scripts/python.exe"
    "${REPO_ROOT}/.venv/bin/python"
  )
  for cand in /usr/local/miniconda3/envs/*/bin/python /opt/conda/envs/*/bin/python /root/miniconda3/envs/*/bin/python; do
    [[ -x "${cand}" ]] && cands+=("${cand}")
  done
  local sys_py3 sys_py
  sys_py3="$(command -v python3 2>/dev/null || true)"
  sys_py="$(command -v python 2>/dev/null || true)"
  [[ -n "${sys_py3}" ]] && cands+=("${sys_py3}")
  [[ -n "${sys_py}" ]] && cands+=("${sys_py}")

  # Pass 1: prefer interpreter that already has working torch + transformers
  for cand in "${cands[@]}"; do
    if [[ -n "${cand}" && -x "${cand}" ]] && "${cand}" -c "import torch, transformers" >/dev/null 2>&1; then
      echo "${cand}"
      return 0
    fi
  done
  # Pass 2 (non-selftest GPU boot): prefer interpreter with working pip (avoids Ubuntu ensurepip failure)
  for cand in "${cands[@]}"; do
    if [[ -n "${cand}" && -x "${cand}" ]] && "${cand}" -m pip --version >/dev/null 2>&1; then
      echo "${cand}"
      return 0
    fi
  done
  # Pass 3: any executable python
  for cand in "${cands[@]}"; do
    if [[ -n "${cand}" && -x "${cand}" ]]; then
      echo "${cand}"
      return 0
    fi
  done
  return 1
}

PY="$(pick_python || true)"
if [[ -z "${PY}" ]]; then
  echo "[FATAL] No usable python interpreter found!" >&2
  exit 1
fi

win_path() {
  local p="$1"
  if [[ "${PY}" == *.exe ]] && command -v cygpath >/dev/null 2>&1; then
    cygpath -w "${p}"
  else
    echo "${p}"
  fi
}

SCRIPT_DIR_PY="$(win_path "${SCRIPT_DIR}")"
REPO_ROOT_PY="$(win_path "${REPO_ROOT}")"
resolve_cli_path() {
  local raw="$1"
  local fallback="$2"
  if [[ -z "${raw}" ]]; then
    echo "${fallback}"
  elif [[ "${raw}" = /* ]] || [[ "${raw}" =~ ^[A-Za-z]:[/\\] ]] || [[ -f "${raw}" ]]; then
    echo "${raw}"
  else
    echo "${SCRIPT_DIR}/${raw}"
  fi
}
SFT_DATA="$(resolve_cli_path "${SFT_DATA_ARG}" "${SCRIPT_DIR}/dataset/six_software_real_assets_sft.jsonl")"
DPO_DATA="$(resolve_cli_path "${DPO_DATA_ARG}" "${SCRIPT_DIR}/dataset/six_software_real_assets_dpo.jsonl")"
LEDGER_FILE="$(resolve_cli_path "${LEDGER_ARG}" "${SCRIPT_DIR}/dataset/six_software_real_assets_sft_ledger.json")"
HOLDOUT_FILE="${SCRIPT_DIR}/dataset/six_software_holdout.jsonl"
if [[ ! -f "${HOLDOUT_FILE}" && -f "${REPO_ROOT}/data/sft/six_software_real_assets/six_software_holdout.jsonl" ]]; then
  HOLDOUT_FILE="${REPO_ROOT}/data/sft/six_software_real_assets/six_software_holdout.jsonl"
fi
SFT_DATA_PY="$(win_path "${SFT_DATA}")"
DPO_DATA_PY="$(win_path "${DPO_DATA}")"
LEDGER_FILE_PY="$(win_path "${LEDGER_FILE}")"
HOLDOUT_FILE_PY="$(win_path "${HOLDOUT_FILE}")"

echo "========================================================================"
echo "[Virtu-Six-Software] Cloud Training Orchestrator"
echo "  SCRIPT_DIR = ${SCRIPT_DIR}"
echo "  OUT_DIR    = ${OUT_DIR}"
echo "  PYTHON     = ${PY}"
echo "  EPOCHS     = ${EPOCHS} | DPO_EPOCHS = ${DPO_EPOCHS} | SKIP_DPO = ${SKIP_DPO}"
echo "  LR         = ${LR} | DPO_LR = ${DPO_LR} | BETA = ${BETA}"
echo "  MAX_HOURS  = ${MAX_HOURS} | SKIP_SMOKE = ${SKIP_SMOKE} | SELFTEST = ${SELFTEST}"
echo "========================================================================"

# ------------------------------------------------------------------------------
# Stage 0: GPU Hardware Probe & /root/venv25 Auto Self-Heal (Skipped on --selftest)
# ------------------------------------------------------------------------------
GPU_VRAM_GB="0"
if [[ "${SELFTEST}" -eq 0 ]]; then
  echo ""
  echo "[Stage 0/8] GPU CUDA Hardware & Runtime Probe ..."
  if command -v nvidia-smi >/dev/null 2>&1; then
    nvidia-smi --query-gpu=index,name,memory.total,memory.free,driver_version --format=csv,noheader || true
  fi

  probe_cuda_env() {
    local py_bin="$1"
    "${py_bin}" - <<'PYPROBE'
import sys
import torch
import transformers
import peft
import accelerate
import datasets
if not torch.cuda.is_available():
    raise RuntimeError("torch.cuda.is_available() == False")
a = torch.randn((256, 256), device="cuda:0", dtype=torch.float16)
c = torch.matmul(a, a)
torch.cuda.synchronize()
del a, c
props = torch.cuda.get_device_properties(0)
vram_gb = props.total_memory / (1024 ** 3)
print(f"[CUDA_OK] gpu={props.name} vram_gb={vram_gb:.2f} bf16_supported={torch.cuda.is_bf16_supported()}")
PYPROBE
  }

  if ! probe_cuda_env "${PY}" >/tmp/virtu_six_cuda_probe.txt 2>&1; then
    echo "[WARN] Initial python environment probe failed:"
    cat /tmp/virtu_six_cuda_probe.txt || true
    echo "[Stage 0/8] Attempting Python/CUDA self-heal (PY=${PY}) ..."
    PIP_MIRROR="${PIP_INDEX:-https://pypi.tuna.tsinghua.edu.cn/simple}"
    # Clean partial broken /root/venv25 without pip
    if [[ -d "/root/venv25" ]] && ! /root/venv25/bin/python -m pip --version >/dev/null 2>&1; then
      rm -rf /root/venv25
    fi
    if ! "${PY}" -m pip --version >/dev/null 2>&1; then
      SYS_PY="$(command -v python3 || command -v python)"
      "${SYS_PY}" -m venv --system-site-packages /root/venv25 || "${SYS_PY}" -m venv /root/venv25
      PY="/root/venv25/bin/python"
    fi
    "${PY}" -m pip install -q --upgrade --resume-retries 8 --timeout 120 pip -i "${PIP_MIRROR}" || "${PY}" -m pip install -q --upgrade pip || true
    if ! "${PY}" -c "import torch; assert torch.cuda.is_available()" >/dev/null 2>&1; then
      "${PY}" -m pip install -q --resume-retries 8 --timeout 120 "torch>=2.5.1,<2.7.0" -i "${PIP_MIRROR}" \
        || "${PY}" -m pip install -q --resume-retries 8 --timeout 120 "torch>=2.5.1,<2.7.0" -i https://mirrors.aliyun.com/pypi/simple \
        || "${PY}" -m pip install -q --resume-retries 8 --timeout 120 "torch>=2.5.1,<2.7.0" --index-url https://download.pytorch.org/whl/cu124 \
        || "${PY}" -m pip install -q --resume-retries 8 --timeout 120 "torch>=2.5.1,<2.7.0"
    fi
    "${PY}" -m pip install -q --resume-retries 8 --timeout 120 "transformers>=4.51.0,<5.0.0" "peft>=0.13.0,<0.17.0" \
      "accelerate>=0.33.0,<2.0.0" "datasets>=2.18.0,<4.0.0" bitsandbytes safetensors sentencepiece modelscope \
      -i "${PIP_MIRROR}" \
      || "${PY}" -m pip install -q --resume-retries 8 --timeout 120 "transformers>=4.51.0,<5.0.0" "peft>=0.13.0,<0.17.0" \
      "accelerate>=0.33.0,<2.0.0" "datasets>=2.18.0,<4.0.0" bitsandbytes safetensors sentencepiece modelscope \
      -i https://mirrors.aliyun.com/pypi/simple
    if ! probe_cuda_env "${PY}" >/tmp/virtu_six_cuda_probe.txt 2>&1; then
      cat /tmp/virtu_six_cuda_probe.txt >&2 || true
      echo "[FATAL] GPU fp16 torch.matmul probe failed after self-heal! Aborting." >&2
      exit 1
    fi
  fi
  cat /tmp/virtu_six_cuda_probe.txt
  rm -f /tmp/virtu_six_cuda_probe.txt

  GPU_VRAM_GB="$("${PY}" -c 'import torch; print(f"{torch.cuda.get_device_properties(0).total_memory/(1024**3):.2f}")')"
  read -r AUTO_MAX_LEN AUTO_DPO_LEN AUTO_QLORA AUTO_BATCH AUTO_ACCUM < <("${PY}" -c "
vram = float('${GPU_VRAM_GB}')
req_qlora = int('${QLORA}')
if vram < 22.0 or req_qlora == 1:
    qlora = 1
else:
    qlora = 0
if vram >= 36.0 and qlora == 0:
    print(4096, 2048, qlora, 2, 8)
elif vram >= 20.0:
    print(3072, 2048, qlora, 1, 16)
else:
    print(2048, 1536, 1, 1, 16)
")
  if [[ "${MAX_LEN}" -le 0 ]]; then MAX_LEN="${AUTO_MAX_LEN}"; fi
  if [[ "${DPO_MAX_LEN}" -le 0 ]]; then DPO_MAX_LEN="${AUTO_DPO_LEN}"; fi
  if [[ "${AUTO_QLORA}" -eq 1 ]]; then QLORA=1; fi
else
  if [[ "${MAX_LEN}" -le 0 ]]; then MAX_LEN=4096; fi
  if [[ "${DPO_MAX_LEN}" -le 0 ]]; then DPO_MAX_LEN=2048; fi
  AUTO_BATCH=1
  AUTO_ACCUM=16
fi

QLORA_FLAG=""
if [[ "${QLORA}" -eq 1 ]]; then
  QLORA_FLAG="--qlora"
fi

echo "[Stage 0/8] Config resolved: VRAM=${GPU_VRAM_GB}GiB max_len=${MAX_LEN} dpo_max_len=${DPO_MAX_LEN} qlora=${QLORA} batch=${AUTO_BATCH}x${AUTO_ACCUM}"

# ------------------------------------------------------------------------------
# Stage 1: Corpus SHA256 Ledger + Schema/Tool + Units + Anti-Leak Gates
# ------------------------------------------------------------------------------
echo ""
echo "[Stage 1/8] Pre-Flight Six-Software Corpus Integrity & Zero-Leak Gates ..."
"${PY}" - "${REPO_ROOT_PY}" "${SFT_DATA_PY}" "${DPO_DATA_PY}" "${LEDGER_FILE_PY}" "${HOLDOUT_FILE_PY}" "${SKIP_DPO}" <<'PYSTAGE1'
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

root = Path(sys.argv[1])
sft_path = Path(sys.argv[2])
dpo_path = Path(sys.argv[3])
ledger_path = Path(sys.argv[4])
holdout_file = Path(sys.argv[5])
skip_dpo = int(sys.argv[6])

sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "scripts"))

def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        while chunk := f.read(1 << 16):
            h.update(chunk)
    return h.hexdigest()

for req in (sft_path, ledger_path):
    if not req.is_file():
        raise SystemExit(f"[FATAL] Missing required file: {req}")

ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
files_meta = ledger.get("files") or {}

def check_ledger_hash(path: Path) -> str:
    actual = sha256_file(path)
    entry = files_meta.get(path.name)
    expected = entry.get("sha256") if isinstance(entry, dict) else entry
    if not expected and path == sft_path:
        expected = ledger.get("output_sha256")
    if not expected:
        raise SystemExit(f"[FATAL] Ledger missing expected sha256 for {path.name}")
    if expected.lower() != actual.lower():
        raise SystemExit(f"[FATAL] SHA256 mismatch for {path.name}: expected={expected[:16]} actual={actual[:16]}")
    sidecar = Path(str(path) + ".sha256")
    if sidecar.is_file():
        sc_hex = sidecar.read_text(encoding="utf-8").strip().split()[0].lower()
        if sc_hex != actual.lower():
            raise SystemExit(f"[FATAL] Sidecar .sha256 mismatch for {path.name}: sidecar={sc_hex[:16]} actual={actual[:16]}")
    print(f"[Gate-SHA256] OK {path.name}: {actual}")
    return actual

sft_sha = check_ledger_hash(sft_path)

sft_rows = [json.loads(ln) for ln in sft_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
if not sft_rows:
    raise SystemExit("[FATAL] Empty SFT dataset!")

# Schema, tool-call validation & 1024B system prompt ceiling
try:
    import gate_all90_dataset as ga
    g1 = ga.gate_schema_and_tools(sft_rows)
    if not g1.get("passed"):
        raise SystemExit(f"[FATAL] gate_1_schema_and_tools failed: {g1.get('errors')}")
    g2 = ga.gate_system_prompt_budget_and_leak(sft_rows, max_bytes=1024)
    if not g2.get("passed"):
        raise SystemExit(f"[FATAL] gate_2_system_prompt_budget failed: {g2.get('errors')}")
    print(f"[Gate-Schema] OK rows={g1['rows']} tool_calls={g1['tool_calls_checked']} max_sys_bytes={g2['max_bytes_seen']}")
except ImportError as exc:
    raise SystemExit(f"[FATAL] Cannot import scripts/gate_all90_dataset.py: {exc}")

from scripts.corpus_unit_audit import assert_units_clean
assert_units_clean(str(sft_path))

from virtu_eval.contamination_check import assert_no_leak
eval_dirs = [
    root / "data" / "benchmark" / "virtu_eval_v1",
    root / "data" / "benchmark" / "virtu_eval_phys_v1",
    root / "data" / "benchmark" / "virtu_eval_cl_v1",
]
missing_evals = [str(d) for d in eval_dirs if not d.is_dir()]
if missing_evals:
    raise SystemExit(f"[FATAL] Missing anti-leak benchmark dirs: {missing_evals}")

with tempfile.TemporaryDirectory(prefix="virtu_six_holdout_") as td:
    if holdout_file.is_file():
        hd = Path(td)
        shutil.copy2(holdout_file, hd / "six_software_holdout.jsonl")
        eval_dirs.append(hd)

    for ed in eval_dirs:
        assert_no_leak(str(sft_path), str(ed))

    if skip_dpo == 0:
        if not dpo_path.is_file():
            raise SystemExit(f"[FATAL] Missing DPO dataset: {dpo_path}")
        check_ledger_hash(dpo_path)
        assert_units_clean(str(dpo_path))
        dpo_rows = [json.loads(ln) for ln in dpo_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        if not dpo_rows:
            raise SystemExit("[FATAL] Empty DPO dataset!")
        for idx, p in enumerate(dpo_rows):
            pr, ch, rj = p.get("prompt"), p.get("chosen"), p.get("rejected")
            if not isinstance(pr, list) or not pr:
                raise SystemExit(f"[FATAL] DPO row {idx} invalid/empty prompt")
            if not isinstance(ch, str) or not isinstance(rj, str) or not ch.strip() or not rj.strip():
                raise SystemExit(f"[FATAL] DPO row {idx} chosen/rejected must be non-empty str")
            if ch.strip() == rj.strip():
                raise SystemExit(f"[FATAL] DPO row {idx} chosen == rejected")
            for m in pr:
                if m.get("role") == "system":
                    sb = len((m.get("content") or "").encode("utf-8"))
                    if sb > 1024:
                        raise SystemExit(f"[FATAL] DPO row {idx} system prompt {sb}B > 1024B")
        for ed in eval_dirs:
            assert_no_leak(str(dpo_path), str(ed))
        print(f"[Gate-DPO] OK pairs={len(dpo_rows)} schema/diff/anti-leak passed")
PYSTAGE1

# ------------------------------------------------------------------------------
# Stage 2: Offline Script Self-Tests
# ------------------------------------------------------------------------------
echo ""
echo "[Stage 2/8] Running Trainer & Gate Offline Selftests ..."
"${PY}" "${SCRIPT_DIR_PY}/train_turnkey.py" --selftest
"${PY}" "${SCRIPT_DIR_PY}/train_vericut_dpo.py" --selftest
if [[ -f "${SCRIPT_DIR}/deploy_trained_adapter.py" ]]; then
  "${PY}" "${SCRIPT_DIR_PY}/deploy_trained_adapter.py" --selftest
fi

if [[ "${SELFTEST}" -eq 1 ]]; then
  echo "[PASS] run_six_software_real.sh --selftest completed (all offline gates passed)."
  exit 0
fi

# Set PYTHONPATH using OS-appropriate separator so python finds virtu_eval cleanly
if [[ "${PY}" != *.exe ]]; then
  export PYTHONPATH="${REPO_ROOT}:${SCRIPT_DIR}:${PYTHONPATH:-}"
else
  export PYTHONPATH="${REPO_ROOT_PY};${SCRIPT_DIR_PY};${PYTHONPATH:-}"
fi

# ------------------------------------------------------------------------------
# Stage 3: Qwen3-8B Non-Instruct Base Resolve & Lineage Identity Lock
# ------------------------------------------------------------------------------
echo ""
echo "[Stage 3/8] Resolving & Verifying Qwen3-8B Non-Instruct Base ..."
RESOLVED_BASE="$("${PY}" - "${SCRIPT_DIR_PY}" "${REPO_ROOT_PY}" "${BASE_PATH}" <<'PYSTAGE3'
import sys
from pathlib import Path

script_dir = Path(sys.argv[1])
repo_root = Path(sys.argv[2])
override = sys.argv[3].strip() or None
sys.path.insert(0, str(script_dir))
from train_turnkey import find_or_download_base, assert_base_identity

if not override:
    local_cand = repo_root / "checkpoints" / "_base_qwen3_8b"
    if (local_cand / "config.json").is_file():
        override = str(local_cand)

base = find_or_download_base(override)
assert_base_identity(base)
print(base)
PYSTAGE3
)"
RESOLVED_BASE="$(echo "${RESOLVED_BASE}" | tail -n 1 | tr -d '\r')"
if [[ -z "${RESOLVED_BASE}" || ! -d "${RESOLVED_BASE}" ]]; then
  echo "[FATAL] Failed to resolve Qwen3-8B base model directory: '${RESOLVED_BASE}'" >&2
  exit 1
fi
echo "[Stage 3/8] Locked Base Model: ${RESOLVED_BASE}"

# ------------------------------------------------------------------------------
# Stage 4: Real GPU 12-Step SFT + 2-Step DPO Smoke Test
# ------------------------------------------------------------------------------
mkdir -p "${OUT_DIR}"
if [[ "${SKIP_SMOKE}" -eq 0 ]]; then
  echo ""
  echo "[Stage 4/8] Real GPU Joint Smoke Test (12-step SFT + 2-step DPO) ..."
  SMOKE_SFT_DIR="${OUT_DIR}/_smoke_sft"
  SMOKE_DPO_DIR="${OUT_DIR}/_smoke_dpo"
  rm -rf "${SMOKE_SFT_DIR}" "${SMOKE_DPO_DIR}"

  "${PY}" "${SCRIPT_DIR}/train_turnkey.py" \
    --base "${RESOLVED_BASE}" \
    --data "${SFT_DATA}" \
    --ledger "${LEDGER_FILE}" \
    --out "${SMOKE_SFT_DIR}" \
    --max-steps 12 \
    --epochs 1 \
    --batch 1 \
    --grad-accum 1 \
    --max-length "${MAX_LEN}" \
    --gpu-id "${GPU_ID}" \
    ${QLORA_FLAG}

  if [[ ! -f "${SMOKE_SFT_DIR}/final_adapter/adapter_model.safetensors" ]]; then
    echo "[FATAL] Stage 4 SFT smoke failed to produce final_adapter/adapter_model.safetensors" >&2
    exit 1
  fi

  if [[ "${SKIP_DPO}" -eq 0 ]]; then
    CUDA_VISIBLE_DEVICES="${GPU_ID}" "${PY}" "${SCRIPT_DIR}/train_vericut_dpo.py" \
      --base "${RESOLVED_BASE}" \
      --sft-adapter "${SMOKE_SFT_DIR}/final_adapter" \
      --data "${DPO_DATA}" \
      --ledger "${LEDGER_FILE}" \
      --out "${SMOKE_DPO_DIR}" \
      --max-steps 2 \
      --epochs 1 \
      --grad-accum 1 \
      --ref-mode "${DPO_REF_MODE}" \
      --max-length "${DPO_MAX_LEN}" \
      --max-prompt-length 1024 \
      ${QLORA_FLAG}
    if [[ ! -f "${SMOKE_DPO_DIR}/adapter_model.safetensors" ]]; then
      echo "[FATAL] Stage 4 DPO smoke failed to produce adapter_model.safetensors" >&2
      exit 1
    fi
  fi

  rm -rf "${SMOKE_SFT_DIR}" "${SMOKE_DPO_DIR}"
  echo "[Stage 4/8] PASS: Joint GPU smoke succeeded cleanly!"
  if [[ "${SMOKE_ONLY}" -eq 1 ]]; then
    echo "[PASS] --smoke-only finished with zero errors."
    exit 0
  fi
else
  echo ""
  echo "[Stage 4/8] Skipped (--skip-smoke)"
fi

# ------------------------------------------------------------------------------
# Stage 5: Content-Addressed Run Identity Fingerprint Lock
# ------------------------------------------------------------------------------
echo ""
echo "[Stage 5/8] Recording Content-Addressed run_identity.json ..."
RUN_IDENTITY_FILE="${OUT_DIR}/run_identity.json"
"${PY}" - "${SCRIPT_DIR_PY}" "$(win_path "${RUN_IDENTITY_FILE}")" "${RESOLVED_BASE}" \
  "${SFT_DATA_PY}" "${DPO_DATA_PY}" "${LEDGER_FILE_PY}" "${HOLDOUT_FILE_PY}" \
  "${EPOCHS}" "${DPO_EPOCHS}" "${LR}" "${DPO_LR}" "${BETA}" "${MAX_LEN}" "${DPO_MAX_LEN}" "${QLORA}" "${SKIP_DPO}" "${MAX_HOURS}" "${TRACK_LABEL}" <<'PYSTAGE5'
import hashlib
import json
import sys
import time
from pathlib import Path

root = Path(sys.argv[1])
out_file = Path(sys.argv[2])
base = sys.argv[3]
sft_p = Path(sys.argv[4])
dpo_p = Path(sys.argv[5])
ledger_p = Path(sys.argv[6])
holdout_p = Path(sys.argv[7])

def sha256(p: Path) -> str:
    if not p.is_file():
        return ""
    h = hashlib.sha256()
    with p.open("rb") as f:
        while chunk := f.read(1 << 16):
            h.update(chunk)
    return h.hexdigest()

ident = {
    "track": sys.argv[18] if len(sys.argv) > 18 else "six-software",
    "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "base_model": base,
    "files_sha256": {
        "sft_data": sha256(sft_p),
        "dpo_data": sha256(dpo_p) if int(sys.argv[16]) == 0 else "",
        "ledger": sha256(ledger_p),
        "holdout": sha256(holdout_p),
        "train_turnkey": sha256(root / "train_turnkey.py"),
        "train_vericut_dpo": sha256(root / "train_vericut_dpo.py"),
        "runner_sh": sha256(root / "run_six_software_real.sh"),
    },
    "hyperparams": {
        "epochs": float(sys.argv[8]),
        "dpo_epochs": int(sys.argv[9]),
        "lr": sys.argv[10],
        "dpo_lr": sys.argv[11],
        "beta": float(sys.argv[12]),
        "max_length": int(sys.argv[13]),
        "dpo_max_length": int(sys.argv[14]),
        "qlora": bool(int(sys.argv[15])),
        "skip_dpo": bool(int(sys.argv[16])),
        "max_hours": float(sys.argv[17]),
    },
}
out_file.parent.mkdir(parents=True, exist_ok=True)
out_file.write_text(json.dumps(ident, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(ident, ensure_ascii=False, indent=2))
PYSTAGE5

# ------------------------------------------------------------------------------
# Stage 6: Full SFT Training (Qwen3-8B + LoRA r=32/alpha=64)
# ------------------------------------------------------------------------------
SFT_OUT_DIR="${OUT_DIR}/sft_run"
MAX_STEPS_ARG=""
if [[ "${MAX_STEPS}" -gt 0 ]]; then
  MAX_STEPS_ARG="--max-steps ${MAX_STEPS}"
fi
SFT_FINAL_ADAPTER="${SFT_OUT_DIR}/final_adapter"

if [[ -n "${REUSE_SFT_DIR}" ]]; then
  echo ""
  echo "[Stage 6/8] Reusing Verified SFT Adapter: ${REUSE_SFT_DIR}"
  if [[ ! -f "${REUSE_SFT_DIR}/adapter_model.safetensors" || ! -f "${REUSE_SFT_DIR}/training_receipt.json" ]]; then
    echo "[FATAL] --reuse-sft missing adapter_model.safetensors or training_receipt.json: ${REUSE_SFT_DIR}" >&2
    exit 1
  fi
  SFT_FINAL_ADAPTER="${REUSE_SFT_DIR}"
else
  rm -rf "${SFT_OUT_DIR}"
  SFT_MAX_HOURS="${MAX_HOURS}"
  if [[ "${SKIP_DPO}" -eq 0 ]]; then
    SFT_MAX_HOURS="$("${PY}" -c "h=float('${MAX_HOURS}'); print(f'{max(0.25, h - 0.35):.3f}')")"
  fi

  echo ""
  echo "[Stage 6/8] Launching Full SFT Training (budget=${SFT_MAX_HOURS}h) ..."
  set +e
  "${PY}" "${SCRIPT_DIR}/train_turnkey.py" \
    --base "${RESOLVED_BASE}" \
    --data "${SFT_DATA}" \
    --ledger "${LEDGER_FILE}" \
    --out "${SFT_OUT_DIR}" \
    --epochs "${EPOCHS}" \
    --lr "${LR}" \
    --batch "${AUTO_BATCH}" \
    --grad-accum "${AUTO_ACCUM}" \
    --max-length "${MAX_LEN}" \
    --max-hours "${SFT_MAX_HOURS}" \
    --gpu-id "${GPU_ID}" \
    ${MAX_STEPS_ARG} \
    ${QLORA_FLAG}
  SFT_RC=$?
  set -e
  if [[ "${SFT_RC}" -ne 0 && "${SFT_RC}" -ne 3 ]]; then
    echo "[FATAL] Stage 6 SFT exited with error rc=${SFT_RC}" >&2
    exit "${SFT_RC}"
  fi
  if [[ ! -f "${SFT_FINAL_ADAPTER}/adapter_model.safetensors" ]]; then
    echo "[FATAL] Stage 6 missing ${SFT_FINAL_ADAPTER}/adapter_model.safetensors" >&2
    exit 1
  fi
fi

# ------------------------------------------------------------------------------
# Stage 7: Controlled DPO Preference Alignment (SFT-ref KL anchor)
# ------------------------------------------------------------------------------
DPO_OUT_DIR="${OUT_DIR}/dpo_run"
FINAL_ADAPTER_SRC="${SFT_FINAL_ADAPTER}"
if [[ "${SKIP_DPO}" -eq 0 ]]; then
  echo ""
  echo "[Stage 7/8] Launching Controlled DPO Alignment (epochs=${DPO_EPOCHS}, lr=${DPO_LR}, beta=${BETA}, grad_accum=${DPO_GRAD_ACCUM}, ref=${DPO_REF_MODE}) ..."
  rm -rf "${DPO_OUT_DIR}"
  CUDA_VISIBLE_DEVICES="${GPU_ID}" "${PY}" "${SCRIPT_DIR}/train_vericut_dpo.py" \
    --base "${RESOLVED_BASE}" \
    --sft-adapter "${SFT_FINAL_ADAPTER}" \
    --data "${DPO_DATA}" \
    --ledger "${LEDGER_FILE}" \
    --out "${DPO_OUT_DIR}" \
    --beta "${BETA}" \
    --lr "${DPO_LR}" \
    --epochs "${DPO_EPOCHS}" \
    --grad-accum "${DPO_GRAD_ACCUM}" \
    --ref-mode "${DPO_REF_MODE}" \
    --max-length "${DPO_MAX_LEN}" \
    --max-prompt-length 1024 \
    --max-hours 1.5 \
    ${MAX_STEPS_ARG} \
    ${QLORA_FLAG}
  if [[ ! -f "${DPO_OUT_DIR}/adapter_model.safetensors" ]]; then
    echo "[FATAL] Stage 7 DPO missing ${DPO_OUT_DIR}/adapter_model.safetensors" >&2
    exit 1
  fi
  FINAL_ADAPTER_SRC="${DPO_OUT_DIR}"
else
  echo ""
  echo "[Stage 7/8] Skipped (--skip-dpo)"
fi

# ------------------------------------------------------------------------------
# Stage 8: Zero-Drift Audit + Unified Deliverable Archive + SHA256 Checksum
# ------------------------------------------------------------------------------
echo ""
echo "[Stage 8/8] Verifying Zero Corpus Drift & Packaging Deliverable ..."
DELIV_TAR="${OUT_DIR}/$(basename "${DELIV_NAME}")"
"${PY}" - "${OUT_DIR}" "${RUN_IDENTITY_FILE}" "${FINAL_ADAPTER_SRC}" \
  "${SFT_FINAL_ADAPTER}" "${DPO_OUT_DIR}" \
  "${SFT_DATA}" "${DPO_DATA}" "${LEDGER_FILE}" "${SKIP_DPO}" "${DELIV_TAR}" "${RESOLVED_BASE}" "${TRACK_LABEL}" <<'PYSTAGE8'
import hashlib
import json
import shutil
import sys
import tarfile
from pathlib import Path

out_dir = Path(sys.argv[1])
ident_file = Path(sys.argv[2])
final_src = Path(sys.argv[3])
sft_adapter_dir = Path(sys.argv[4])
dpo_adapter_dir = Path(sys.argv[5])
sft_data = Path(sys.argv[6])
dpo_data = Path(sys.argv[7])
ledger_file = Path(sys.argv[8])
skip_dpo = int(sys.argv[9])
deliv_tar = Path(sys.argv[10])
base_model = sys.argv[11]
track_name = sys.argv[12] if len(sys.argv) > 12 else "six-software"

def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        while chunk := f.read(1 << 16):
            h.update(chunk)
    return h.hexdigest()

ident = json.loads(ident_file.read_text(encoding="utf-8"))
expected = ident["files_sha256"]
checks = [("sft_data", sft_data), ("ledger", ledger_file)]
if skip_dpo == 0:
    checks.append(("dpo_data", dpo_data))
for key, path in checks:
    cur = sha256(path)
    if cur != expected[key]:
        raise SystemExit(f"[FATAL] Corpus drift detected during training for {key}: {expected[key][:16]} -> {cur[:16]}")
print("[Stage 8/8] Zero-drift check PASSED (SFT/DPO/Ledger unchanged).")

if "instruct" in base_model.lower():
    raise SystemExit(f"[FATAL] Invalid base model lineage (Instruct forbidden): {base_model}")

sft_rec = json.loads((sft_adapter_dir / "training_receipt.json").read_text(encoding="utf-8"))
dpo_rec = json.loads((dpo_adapter_dir / "training_receipt.json").read_text(encoding="utf-8")) if skip_dpo == 0 else None

cfg = json.loads((final_src / "adapter_config.json").read_text(encoding="utf-8"))
if int(cfg.get("r", -1)) != 32 or int(cfg.get("lora_alpha", -1)) != 64:
    raise SystemExit(f"[FATAL] Deliverable LoRA rank mismatch: r={cfg.get('r')} alpha={cfg.get('lora_alpha')}")

stage_root = out_dir / "_deliverable_stage"
if stage_root.exists():
    shutil.rmtree(stage_root)
adapter_dst = stage_root / "virtu_lora_adapter"
shutil.copytree(final_src, adapter_dst)

weight_file = adapter_dst / "adapter_model.safetensors"
if not weight_file.is_file():
    raise SystemExit(f"[FATAL] Missing final adapter weights: {weight_file}")
adapter_sha = sha256(weight_file)

statuses = [sft_rec.get("status")]
if dpo_rec is not None:
    statuses.append(dpo_rec.get("status"))
overall_status = "COMPLETED" if all(s == "COMPLETED" for s in statuses) else (
    "TIME_BUDGET_STOPPED" if any(s == "TIME_BUDGET_STOPPED" for s in statuses) else str(statuses[-1])
)

unified_receipt = {
    "status": overall_status,
    "track": track_name,
    "base_model": base_model,
    "dataset_sha256": expected["sft_data"],
    "sft_dataset_sha256": expected["sft_data"],
    "dpo_dataset_sha256": expected["dpo_data"],
    "holdout_dataset_sha256": expected["holdout"],
    "adapter_sha256": adapter_sha,
    "lora_r": int(cfg["r"]),
    "lora_alpha": int(cfg["lora_alpha"]),
    "sft_receipt": sft_rec,
    "dpo_receipt": dpo_rec,
}
rec_text = json.dumps(unified_receipt, ensure_ascii=False, indent=2)
(adapter_dst / "training_receipt.json").write_text(rec_text, encoding="utf-8")
(stage_root / "training_receipt.json").write_text(rec_text, encoding="utf-8")
(out_dir / "training_receipt.json").write_text(rec_text, encoding="utf-8")
shutil.copy2(ident_file, stage_root / "run_identity.json")

with tarfile.open(deliv_tar, "w:gz") as tar:
    for item in sorted(stage_root.rglob("*")):
        rel = item.relative_to(stage_root).as_posix()
        tar.add(item, arcname=rel, recursive=False)

shutil.rmtree(stage_root)
deliv_sha = sha256(deliv_tar)
sha_line = f"{deliv_sha}  {deliv_tar.name}\n"
(Path(str(deliv_tar) + ".sha256")).write_text(sha_line, encoding="utf-8")
print(f"[DELIVERABLE] status={overall_status} tar={deliv_tar.name} sha256={deliv_sha} adapter_sha256={adapter_sha[:16]}...")
PYSTAGE8

(cd "${OUT_DIR}" && sha256sum -c "$(basename "${DELIV_TAR}").sha256")
echo "========================================================================"
echo "[DONE] Six-Software Cloud Training & Packaging Completed Successfully!"
echo "  Receipt     : ${OUT_DIR}/training_receipt.json"
echo "  Deliverable : ${DELIV_TAR}"
echo "  Checksum    : ${DELIV_TAR}.sha256"
echo "========================================================================"
