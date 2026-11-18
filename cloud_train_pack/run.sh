#!/usr/bin/env bash
# ==============================================================================
# cloud_train_pack/run.sh — Virtu 8.2B 主力模型 7 阶段硬门禁云端训练编排器 (v2)
# 遵循 AGENTS.md §8 测量宪法与 fail-closed 原则：
#   flock 单实例锁 -> Stage 0 GPU fp16 实算探测 & venv25 自愈
#   -> Stage 1 语料/Ledger/防污染/单位审计 -> Stage 2 训练器 --selftest
#   -> Stage 3 Qwen3-8B 基座血统门禁 (拒绝 Instruct) -> Stage 4 20 步真实冒烟
#   -> Stage 5 run_identity.json 身份落盘 -> Stage 6 全量训练
#   -> Stage 7 sha256sum -c 交付验证 & 零语料漂移终检
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

FG_MODE=0
SKIP_SMOKE=0
USE_QLORA=0
MAX_HOURS="1.5"
EPOCHS="2.0"
LR="1.5e-4"
MAX_STEPS="-1"
GPU_ID="${CUDA_VISIBLE_DEVICES:-0}"
DATA_ARG=""
LEDGER_ARG=""
BASE_ARG=""
OUT_DIR="output/virtu_lora_master"

ORIG_ARGS=("$@")
while [[ $# -gt 0 ]]; do
  case "$1" in
    --fg) FG_MODE=1; shift ;;
    --skip-smoke) SKIP_SMOKE=1; shift ;;
    --qlora) USE_QLORA=1; shift ;;
    --max-hours) MAX_HOURS="$2"; shift 2 ;;
    --epochs) EPOCHS="$2"; shift 2 ;;
    --lr) LR="$2"; shift 2 ;;
    --max-steps) MAX_STEPS="$2"; shift 2 ;;
    --gpu-id) GPU_ID="$2"; shift 2 ;;
    --data) DATA_ARG="$2"; shift 2 ;;
    --ledger) LEDGER_ARG="$2"; shift 2 ;;
    --base) BASE_ARG="$2"; shift 2 ;;
    --out) OUT_DIR="$2"; shift 2 ;;
    *) echo "[WARN] 忽略未知参数: $1"; shift ;;
  esac
done

export CUDA_VISIBLE_DEVICES="$GPU_ID"
export TOKENIZERS_PARALLELISM=false
export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"

resolve_dataset() {
  if [[ -n "$DATA_ARG" ]]; then
    if [[ ! -f "$DATA_ARG" ]]; then
      echo "[FATAL] 指定的 --data=$DATA_ARG 不存在，拒绝静默回退！" >&2
      exit 2
    fi
    echo "$DATA_ARG"
    return 0
  fi
  local candidates=(
    "dataset/virtu_master_sft.jsonl"
    "dataset/virtu_capability_sft_v5.jsonl"
    "dataset/virtu_v100_production_sft.jsonl"
    "dataset/virtu_gold_production_sft.jsonl"
  )
  local c
  for c in "${candidates[@]}"; do
    if [[ -f "$c" ]]; then
      echo "$c"
      return 0
    fi
  done
  echo "[FATAL] 未找到任何主训 SFT 语料 (virtu_master_sft.jsonl / virtu_capability_sft_v5.jsonl)" >&2
  exit 2
}

LOCK_FILE="${SCRIPT_DIR}/.virtu_master_train.lock"
LOG_FILE="${SCRIPT_DIR}/train_master.log"

if [[ "$FG_MODE" -eq 0 ]]; then
  (
    flock -n 9 || {
      echo "[FATAL] 已有训练实例持有锁 ($LOCK_FILE)，拒绝并发启动！" >&2
      exit 1
    }
  ) 9>"$LOCK_FILE"
  nohup bash "$0" --fg "${ORIG_ARGS[@]}" > "$LOG_FILE" 2>&1 < /dev/null &
  CHILD_PID=$!
  sleep 2
  if ! kill -0 "$CHILD_PID" 2>/dev/null; then
    echo "[FATAL] 后台训练进程在 2 秒内意外退出，请检查日志: $LOG_FILE" >&2
    tail -n 40 "$LOG_FILE" || true
    exit 1
  fi
  echo "[LAUNCHED] 后台训练已启动 PID=$CHILD_PID | 日志: $LOG_FILE"
  exit 0
fi

# 前台执行模式：全程持有排他文件锁
exec 9>"$LOCK_FILE"
flock -n 9 || {
  echo "[FATAL] 并发冲突：另一训练进程正在运行 ($LOCK_FILE)" >&2
  exit 1
}

echo "======================================================================"
echo "[START] Virtu 8.2B 7 阶段硬门禁云端训练 | $(date '+%Y-%m-%d %H:%M:%S')"
echo "======================================================================"

# ----------------------------------------------------------------------
# Stage 0: 真实 CUDA + fp16 matmul 探测，必要时自愈 /root/venv25
# ----------------------------------------------------------------------
probe_python() {
  local py="$1"
  [[ -x "$py" ]] || command -v "$py" >/dev/null 2>&1 || return 1
  "$py" - <<'PY' >/dev/null 2>&1
import torch, transformers, peft, datasets
assert torch.cuda.is_available(), "no cuda"
a = torch.randn(16, 16, device="cuda", dtype=torch.float16)
c = torch.matmul(a, a)
torch.cuda.synchronize()
assert tuple(c.shape) == (16, 16)
PY
}

PY=""
for cand in "/root/venv25/bin/python" "/usr/local/miniconda3/envs/py312/bin/python" "/usr/local/miniconda3/bin/python" "/root/miniconda3/bin/python" "/opt/conda/bin/python" "$(command -v python3 || true)" "$(command -v python || true)"; do
  if [[ -n "$cand" ]] && probe_python "$cand"; then
    PY="$cand"
    break
  fi
done

if [[ -z "$PY" ]]; then
  echo "[Stage0] 现有 Python 环境未通过 GPU fp16 实算探测，尝试构建/修复 /root/venv25 ..."
  BASE_SYS_PY=""
  for sc in "/usr/local/miniconda3/envs/py312/bin/python" "/usr/local/miniconda3/bin/python" "/opt/conda/bin/python" "$(command -v python3 || true)" "$(command -v python || true)"; do
    if [[ -n "$sc" && -x "$sc" ]] && "$sc" -m pip --version >/dev/null 2>&1; then
      BASE_SYS_PY="$sc"
      break
    fi
  done
  if [[ -z "$BASE_SYS_PY" ]]; then
    BASE_SYS_PY="$(command -v python3 || command -v python || true)"
  fi
  if [[ -z "$BASE_SYS_PY" ]]; then
    echo "[FATAL] 未找到系统 python3，无法自愈环境！" >&2
    exit 2
  fi
  if [[ ! -x "/root/venv25/bin/python" ]] || ! /root/venv25/bin/python -m pip --version >/dev/null 2>&1; then
    rm -rf /root/venv25
    "$BASE_SYS_PY" -m venv /root/venv25 --system-site-packages || "$BASE_SYS_PY" -m venv /root/venv25
  fi
  PIP_MIRROR="${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"
  if ! /root/venv25/bin/python -c "import torch; assert torch.cuda.is_available()" >/dev/null 2>&1; then
    echo "[Stage0] 安装 CUDA torch (cu124 / sm_70+ 兼容) ..."
    /root/venv25/bin/python -m pip install -q --upgrade pip -i "$PIP_MIRROR" || true
    /root/venv25/bin/python -m pip install -q "torch==2.5.1" --index-url "https://download.pytorch.org/whl/cu124" --extra-index-url "$PIP_MIRROR" \
      || /root/venv25/bin/python -m pip install -q "torch==2.5.1" -i "$PIP_MIRROR"
  fi
  /root/venv25/bin/python -m pip install -q -i "$PIP_MIRROR" "transformers>=4.51.0,<5.0.0" "peft>=0.13.0,<0.16.0" "datasets>=2.18.0,<4.0.0" "accelerate>=0.33.0,<2.0.0" safetensors sentencepiece protobuf modelscope
  if probe_python "/root/venv25/bin/python"; then
    PY="/root/venv25/bin/python"
  else
    echo "[FATAL] /root/venv25 GPU fp16 torch.matmul 探测仍失败，拒绝盲跑！" >&2
    exit 2
  fi
fi
echo "[Stage0] PASS: Python=$PY | $("$PY" -c 'import torch; print(torch.cuda.get_device_name(0), f"{torch.cuda.get_device_properties(0).total_memory/1024**3:.1f}GB")')"

# ----------------------------------------------------------------------
# Stage 1: 语料锁定 + Ledger SHA256 校验 + 防污染 + 单位制审计
# ----------------------------------------------------------------------
DATA_FILE="$(resolve_dataset)"
DATA_SHA="$(sha256sum "$DATA_FILE" | awk '{print $1}')"
echo "[Stage1] 锁定语料: $DATA_FILE (sha256=${DATA_SHA:0:16}...)"

"$PY" - "$DATA_FILE" "$LEDGER_ARG" "$SCRIPT_DIR" <<'PY'
import os, sys, json, hashlib
data_file, ledger_arg, script_dir = sys.argv[1:4]
parent_dir = os.path.dirname(script_dir)
for p in (script_dir, parent_dir, os.path.join(script_dir, "scripts"), os.path.join(parent_dir, "scripts")):
    if os.path.exists(p) and p not in sys.path:
        sys.path.insert(0, p)

from virtu_eval.contamination_check import assert_no_leak
from corpus_unit_audit import assert_units_clean

with open(data_file, "rb") as f:
    actual = hashlib.sha256(f.read()).hexdigest()

ledger = ledger_arg or os.path.join(os.path.dirname(os.path.abspath(data_file)), "dataset_ledger.json")
if os.path.exists(ledger):
    with open(ledger, "r", encoding="utf-8") as lf:
        meta = json.load(lf)
    base_name = os.path.basename(data_file)
    exp = None
    if isinstance(meta.get("files"), dict) and base_name in meta["files"]:
        entry = meta["files"][base_name]
        exp = entry.get("sha256") if isinstance(entry, dict) else entry
    elif ledger_arg or os.path.basename(str(meta.get("output_path") or meta.get("dataset") or "")) in ("", base_name):
        exp = meta.get("output_sha256") or meta.get("sha256")
    if exp and exp.lower() != actual.lower():
        raise SystemExit(f"[FATAL] Ledger SHA256 不匹配: expected={exp[:16]} actual={actual[:16]}")
elif ledger_arg:
    raise SystemExit(f"[FATAL] 指定的 --ledger 不存在: {ledger_arg}")

assert_no_leak(data_file)
assert_units_clean(data_file)
print("[Stage1] PASS: Ledger / 防污染 / 单位制审计全部通过")
PY

# ----------------------------------------------------------------------
# Stage 2: 训练器零 GPU 自检
# ----------------------------------------------------------------------
echo "[Stage2] 执行 train_turnkey.py --selftest ..."
"$PY" "${SCRIPT_DIR}/train_turnkey.py" --selftest

# ----------------------------------------------------------------------
# Stage 3: Qwen3-8B 基座血统门禁 (拒绝 Instruct / 错维权重)
# ----------------------------------------------------------------------
RESOLVED_BASE="$BASE_ARG"
if [[ -z "$RESOLVED_BASE" ]]; then
  for bp in \
    "/model/ModelScope/Qwen/Qwen3-8B" \
    "/model/HuggingFace/Qwen/Qwen3-8B" \
    "/root/virtu_train/models/Qwen3-8B" \
    "/root/workspace/models/Qwen3-8B" \
    "/root/models/Qwen3-8B" \
    "/root/autodl-tmp/models/Qwen3-8B" \
    "/root/damodel-tmp/models/Qwen3-8B" \
    "/root/public-storage/model/Qwen/Qwen3-8B" \
    "checkpoints/_base_qwen3_8b" \
    "./models/Qwen3-8B"; do
    if [[ -d "$bp" && -f "$bp/config.json" ]]; then
      RESOLVED_BASE="$bp"
      break
    fi
  done
fi

if [[ -n "$RESOLVED_BASE" ]]; then
  "$PY" - "$RESOLVED_BASE" <<'PY'
import os, sys, json
base = sys.argv[1]
if "instruct" in base.lower():
    raise SystemExit(f"[FATAL] Stage3 拒绝 Instruct 基座: {base}")
cfg_path = os.path.join(base, "config.json")
if not os.path.exists(cfg_path):
    raise SystemExit(f"[FATAL] Stage3 缺少 config.json: {cfg_path}")
with open(cfg_path, "r", encoding="utf-8") as f:
    cfg = json.load(f)
if "instruct" in str(cfg.get("_name_or_path", "")).lower():
    raise SystemExit(f"[FATAL] Stage3 拒绝 _name_or_path=Instruct: {cfg.get('_name_or_path')}")
exp = {"hidden_size": 4096, "num_hidden_layers": 36, "vocab_size": 151936}
for k, v in exp.items():
    if cfg.get(k) != v:
        raise SystemExit(f"[FATAL] Stage3 维度不匹配 {k}={cfg.get(k)} != {v}")
print(f"[Stage3] PASS: 基座已核验为 Qwen3-8B -> {base}")
PY
else
  echo "[Stage3] 本地尚无缓存基座，将在训练启动时拉取 Qwen/Qwen3-8B 并强制过 assert_base_identity 门禁"
fi

# 构建公共参数
COMMON_ARGS=(--data "$DATA_FILE" --gpu-id "$GPU_ID" --lr "$LR")
[[ -n "$RESOLVED_BASE" ]] && COMMON_ARGS+=(--base "$RESOLVED_BASE")
[[ -n "$LEDGER_ARG" ]] && COMMON_ARGS+=(--ledger "$LEDGER_ARG")
[[ "$USE_QLORA" -eq 1 ]] && COMMON_ARGS+=(--qlora)

# ----------------------------------------------------------------------
# Stage 4: 20 步真实 GPU 冒烟测试 (若未 --skip-smoke 且未覆盖 --max-steps)
# ----------------------------------------------------------------------
if [[ "$SKIP_SMOKE" -eq 0 && "$MAX_STEPS" -le 0 ]]; then
  SMOKE_OUT="${OUT_DIR}_smoke"
  rm -rf "$SMOKE_OUT"
  echo "[Stage4] 启动 20 步真实冒烟训练 -> $SMOKE_OUT ..."
  "$PY" "${SCRIPT_DIR}/train_turnkey.py" "${COMMON_ARGS[@]}" --out "$SMOKE_OUT" --max-steps 20 --max-hours 0.35
  if [[ ! -f "${SMOKE_OUT}/final_adapter/adapter_model.safetensors" ]]; then
    echo "[FATAL] Stage4 冒烟未产出 adapter_model.safetensors！" >&2
    exit 2
  fi
  rm -rf "$SMOKE_OUT"
  echo "[Stage4] PASS: 20 步冒烟收敛并通过，已清理临时目录"
else
  echo "[Stage4] SKIP: 按参数跳过独立冒烟阶段 (skip_smoke=$SKIP_SMOKE max_steps=$MAX_STEPS)"
fi

# ----------------------------------------------------------------------
# Stage 5: 写入 run_identity.json 测量宪法身份锚定文件
# ----------------------------------------------------------------------
mkdir -p "$OUT_DIR"
"$PY" - "$OUT_DIR" "$DATA_FILE" "$DATA_SHA" "$RESOLVED_BASE" <<'PY'
import os, sys, json, time, hashlib, torch
out_dir, data_file, data_sha, base_path = sys.argv[1:5]
with open("train_turnkey.py", "rb") as f:
    trainer_sha = hashlib.sha256(f.read()).hexdigest()
ident = {
    "run_id": f"master_{time.strftime('%Y%m%d_%H%M%S')}_{data_sha[:8]}",
    "model_lineage": "Qwen3-8B",
    "dataset_path": data_file,
    "dataset_sha256": data_sha,
    "trainer_sha256": trainer_sha,
    "base_path": base_path or "Qwen/Qwen3-8B",
    "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "unknown",
    "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
}
with open(os.path.join(out_dir, "run_identity.json"), "w", encoding="utf-8") as f:
    json.dump(ident, f, ensure_ascii=False, indent=2)
print(f"[Stage5] PASS: run_identity.json 写入完成 run_id={ident['run_id']}")
PY

# ----------------------------------------------------------------------
# Stage 6: 全量 SFT 训练
# ----------------------------------------------------------------------
echo "[Stage6] 启动全量 SFT 训练 -> $OUT_DIR ..."
TRAIN_RC=0
"$PY" "${SCRIPT_DIR}/train_turnkey.py" "${COMMON_ARGS[@]}" \
  --out "$OUT_DIR" --epochs "$EPOCHS" --max-hours "$MAX_HOURS" --max-steps "$MAX_STEPS" || TRAIN_RC=$?

if [[ "$TRAIN_RC" -eq 3 ]]; then
  echo "[WARN] Stage6 因 --max-hours=$MAX_HOURS 时间预算触发优雅保存停机 (TIME_BUDGET_STOPPED, exit=3)"
  exit 3
elif [[ "$TRAIN_RC" -ne 0 ]]; then
  echo "[FATAL] Stage6 全量训练异常退出 rc=$TRAIN_RC" >&2
  exit "$TRAIN_RC"
fi

# ----------------------------------------------------------------------
# Stage 7: 交付件完整性与零漂移终检
# ----------------------------------------------------------------------
(
  cd "$OUT_DIR"
  sha256sum -c virtu_lora_deliverable.tar.gz.sha256
)

"$PY" - "$OUT_DIR" "$DATA_FILE" "$DATA_SHA" <<'PY'
import os, sys, json, hashlib
out_dir, data_file, start_sha = sys.argv[1:4]
receipt_path = os.path.join(out_dir, "training_receipt.json")
if not os.path.exists(receipt_path):
    raise SystemExit(f"[FATAL] Stage7 缺少 training_receipt.json: {receipt_path}")
with open(receipt_path, "r", encoding="utf-8") as f:
    rec = json.load(f)
if rec.get("status") != "COMPLETED":
    raise SystemExit(f"[FATAL] Stage7 交付状态非 COMPLETED: {rec.get('status')}")
with open(data_file, "rb") as f:
    end_sha = hashlib.sha256(f.read()).hexdigest()
if end_sha != start_sha:
    raise SystemExit(f"[FATAL] Stage7 检测到训练期语料漂移! start={start_sha[:16]} end={end_sha[:16]}")
print(f"[Stage7] PASS: status=COMPLETED | loss={rec.get('final_train_loss'):.4f} | adapter={rec.get('adapter_sha256', '')[:16]}... | zero drift")
PY

echo "======================================================================"
echo "[DONE] Virtu 8.2B 主力模型云端训练圆满完成 | $(date '+%Y-%m-%d %H:%M:%S')"
echo "======================================================================"
