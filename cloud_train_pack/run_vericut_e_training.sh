#!/usr/bin/env bash
# ==============================================================================
# cloud_train_pack/run_vericut_e_training.sh
# VERICUT 9.6 (E:\training) + 涡轮叶片五轴联动 & 毛坯反推 云端 8 阶段硬门禁闭环开训
#
# 上线即开训特性（适配 AutoDL / DaModel / RunPod / 裸金属 L40S/A100/V100/4090）：
#   flock 单实例锁 -> Stage 0 CUDA fp16 matmul 探测 + /root/venv25 自愈 + 显存分档
#   -> Stage 1 SFT/DPO 语料 Ledger SHA256 + 三基准 & 留出集零泄漏 + 单位审计 + DPO 检验
#   -> Stage 2 训练器离线 --selftest -> Stage 3 Qwen3-8B 非 Instruct 身份锁与自动拉取
#   -> Stage 4 真实 GPU 冒烟 (SFT 6步 + DPO 2步) -> Stage 5 run_identity.json
#   -> Stage 6 全量 SFT (1007条) -> Stage 7 受控 DPO (117对)
#   -> Stage 8 零漂移校验 & 统一输出 output/virtu_vericut_e/virtu_vericut_e_deliverable.tar.gz
#
# 用法：
#   bash run_vericut_e_training.sh                 # 默认后台 nohup 启动 + 3s 存活探针 (日志 train_vericut_e.log)
#   bash run_vericut_e_training.sh --fg            # 前台同步输出全部日志
#   bash run_vericut_e_training.sh --selftest      # 零 GPU 本地/云端逻辑自检
#   bash run_vericut_e_training.sh --smoke-only    # 仅跑通 SFT+DPO 真实 GPU 冒烟
#   bash run_vericut_e_training.sh --skip-dpo      # 仅跑 SFT 并打包交付
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ -d "${SCRIPT_DIR}/virtu_eval" ]]; then
  REPO_ROOT="$SCRIPT_DIR"
elif [[ -d "${SCRIPT_DIR}/../virtu_eval" ]]; then
  REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
else
  echo "[FATAL] 未找到 virtu_eval 目录（请确认压缩包或仓库完整性）" >&2
  exit 2
fi

FG_MODE=0
SELFTEST_ONLY=0
SMOKE_ONLY=0
SKIP_SMOKE=0
SKIP_DPO=0
USE_QLORA="${USE_QLORA:-auto}"
MAX_HOURS="${MAX_HOURS:-1.5}"
EPOCHS="${EPOCHS:-3.0}"
LR="${LR:-1.2e-4}"
DPO_EPOCHS="${DPO_EPOCHS:-1.0}"
DPO_LR="${DPO_LR:-5e-6}"
BETA="${BETA:-0.1}"
MAX_STEPS="-1"
MAX_LEN_ARG="${MAX_LEN:-auto}"
DPO_MAX_LEN_ARG="${DPO_MAX_LEN:-auto}"
GPU_ID="${CUDA_VISIBLE_DEVICES:-0}"
BASE_ARG=""
SFT_DATA="${SFT_DATA:-dataset/vericut_e_training_sft.jsonl}"
SFT_LEDGER="${SFT_LEDGER:-dataset/vericut_e_training_sft_ledger.json}"
DPO_DATA="${DPO_DATA:-dataset/vericut_e_training_dpo.jsonl}"
OUT_DIR="output/virtu_vericut_e"

ORIG_ARGS=("$@")
while [[ $# -gt 0 ]]; do
  case "$1" in
    --fg) FG_MODE=1; shift ;;
    --selftest|--self-test) SELFTEST_ONLY=1; shift ;;
    --smoke-only) SMOKE_ONLY=1; shift ;;
    --skip-smoke) SKIP_SMOKE=1; shift ;;
    --skip-dpo) SKIP_DPO=1; shift ;;
    --qlora) USE_QLORA=1; shift ;;
    --no-qlora) USE_QLORA=0; shift ;;
    --max-hours) MAX_HOURS="$2"; shift 2 ;;
    --epochs) EPOCHS="$2"; shift 2 ;;
    --lr) LR="$2"; shift 2 ;;
    --dpo-epochs) DPO_EPOCHS="$2"; shift 2 ;;
    --dpo-lr) DPO_LR="$2"; shift 2 ;;
    --beta) BETA="$2"; shift 2 ;;
    --max-steps) MAX_STEPS="$2"; shift 2 ;;
    --max-length) MAX_LEN_ARG="$2"; shift 2 ;;
    --dpo-max-length) DPO_MAX_LEN_ARG="$2"; shift 2 ;;
    --gpu-id) GPU_ID="$2"; shift 2 ;;
    --base) BASE_ARG="$2"; shift 2 ;;
    --base=*) BASE_ARG="${1#*=}"; shift ;;
    --data) SFT_DATA="$2"; shift 2 ;;
    --ledger) SFT_LEDGER="$2"; shift 2 ;;
    --dpo-data) DPO_DATA="$2"; shift 2 ;;
    --out) OUT_DIR="$2"; shift 2 ;;
    *) echo "[WARN] 忽略未知参数: $1"; shift ;;
  esac
done

export CUDA_VISIBLE_DEVICES="$GPU_ID"
export TOKENIZERS_PARALLELISM=false
export PYTHONUTF8=1
export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
export PYTORCH_CUDA_ALLOC_CONF="${PYTORCH_CUDA_ALLOC_CONF:-expandable_segments:True}"
export PATH="/root/venv25/bin:/opt/conda/bin:/usr/local/miniconda3/bin:${PATH}"
export PYTHONPATH="${REPO_ROOT}:${REPO_ROOT}/scripts:${SCRIPT_DIR}:${PYTHONPATH:-}"

pick_basic_py() {
  local c
  for c in "${ECT_PYTHON:-}" "/root/venv25/bin/python" "/opt/conda/bin/python" "/usr/local/miniconda3/bin/python" "${REPO_ROOT}/.venv/Scripts/python.exe" "$(command -v python3 || true)" "$(command -v python || true)"; do
    if [[ -n "$c" ]] && [[ -x "$c" || -x "$(command -v "$c" 2>/dev/null || true)" ]]; then
      echo "$c"
      return 0
    fi
  done
  echo "[FATAL] 未找到可用 Python 解释器！" >&2
  exit 2
}

if [[ "$SELFTEST_ONLY" -eq 1 ]]; then
  PY_ST="$(pick_basic_py)"
  echo "[Selftest] PY=$PY_ST | REPO_ROOT=$REPO_ROOT"
  "$PY_ST" "${SCRIPT_DIR}/train_turnkey.py" --selftest
  "$PY_ST" "${REPO_ROOT}/scripts/train_dpo_all90.py" --self-test
  if [[ -f "${REPO_ROOT}/scripts/gate_all90_dataset.py" ]]; then
    "$PY_ST" "${REPO_ROOT}/scripts/gate_all90_dataset.py" --self-test
  fi
  "$PY_ST" - "$SFT_DATA" "$SFT_LEDGER" "$DPO_DATA" "$REPO_ROOT" <<'PY'
import hashlib, json, os, sys
sft_p, led_p, dpo_p, root = sys.argv[1:5]
for dp in (sft_p, dpo_p, led_p):
    assert os.path.isfile(dp), f"missing dataset/ledger: {dp}"
meta = json.load(open(led_p, "r", encoding="utf-8"))
files = meta.get("files", {})
for dp in (sft_p, dpo_p):
    act = hashlib.sha256(open(dp, "rb").read()).hexdigest()
    bn = os.path.basename(dp)
    ent = files.get(bn, {})
    exp = ent.get("sha256") if isinstance(ent, dict) else (ent or meta.get("output_sha256", ""))
    assert exp and exp.lower() == act.lower(), f"SHA256 mismatch for {bn}: {exp} != {act}"
print("[SELFTEST] PASS: vericut_e SFT+DPO SHA256 ledger verified")
PY
  echo "[SELFTEST] PASS: run_vericut_e_training offline gates"
  exit 0
fi

LOCK_FILE="${SCRIPT_DIR}/.vericut_e_train.lock"
LOG_FILE="${SCRIPT_DIR}/train_vericut_e.log"

if [[ "$FG_MODE" -eq 0 ]]; then
  (
    flock -n 9 || {
      echo "[FATAL] 已有 vericut-e 训练实例持有锁 ($LOCK_FILE)，拒绝并发启动！" >&2
      exit 1
    }
  ) 9>"$LOCK_FILE"
  rm -f "$LOG_FILE"
  nohup bash "$0" --fg ${ORIG_ARGS[@]+"${ORIG_ARGS[@]}"} > "$LOG_FILE" 2>&1 < /dev/null &
  CHILD_PID=$!
  sleep 3
  if ! kill -0 "$CHILD_PID" 2>/dev/null; then
    echo "[FATAL] 后台训练进程在 3 秒内意外退出，日志尾部:" >&2
    tail -n 50 "$LOG_FILE" >&2 || true
    exit 1
  fi
  if grep -q "\[FATAL\]" "$LOG_FILE" 2>/dev/null; then
    echo "[FATAL] 后台启动日志出现 [FATAL]:" >&2
    tail -n 50 "$LOG_FILE" >&2 || true
    exit 1
  fi
  echo "[LAUNCHED] E:\\training + 涡轮叶片五轴云端训练已后台启动 PID=$CHILD_PID | tail -f ${SCRIPT_DIR}/train_vericut_e.log"
  exit 0
fi

exec 9>"$LOCK_FILE"
flock -n 9 || {
  echo "[FATAL] 并发冲突：另一 vericut-e 训练进程正在运行 ($LOCK_FILE)" >&2
  exit 1
}

echo "======================================================================"
echo "[START] Virtu E:\\training + 涡轮叶片五轴毛坯反推 8 阶段云端开训 | $(date '+%Y-%m-%d %H:%M:%S')"
echo "======================================================================"

# ----------------------------------------------------------------------
# Stage 0: 真实 CUDA + fp16 matmul 探测 + /root/venv25 自愈 + 显存分档
# ----------------------------------------------------------------------
if ! command -v nvidia-smi >/dev/null 2>&1; then
  echo "[FATAL] 未找到 nvidia-smi，无法启动 GPU 训练！" >&2
  exit 2
fi
nvidia-smi --query-gpu=index,name,memory.total,memory.free,compute_cap --format=csv,noheader

probe_python() {
  local py="$1"
  local need_bnb="$2"
  [[ -x "$py" ]] || command -v "$py" >/dev/null 2>&1 || return 1
  "$py" - "$need_bnb" <<'PY' >/dev/null 2>&1
import importlib, sys, torch
for m in ("transformers", "peft", "datasets", "accelerate", "trl", "modelscope", "safetensors", "sentencepiece"):
    importlib.import_module(m)
if sys.argv[1] == "1":
    importlib.import_module("bitsandbytes")
assert torch.cuda.is_available(), "cuda unavailable"
a = torch.randn(64, 64, device="cuda", dtype=torch.float16)
c = torch.matmul(a, a)
torch.cuda.synchronize()
assert tuple(c.shape) == (64, 64) and torch.isfinite(c).all()
PY
}

VRAM_MIB="$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -n 1 | tr -d '[:space:]')"
if [[ "$USE_QLORA" == "auto" ]]; then
  if [[ "${VRAM_MIB:-0}" -gt 0 && "${VRAM_MIB:-0}" -lt 36864 ]]; then
    USE_QLORA=1
  else
    USE_QLORA=0
  fi
fi
NEED_BNB="$USE_QLORA"

PY=""
for cand in "${ECT_PYTHON:-}" "/root/venv25/bin/python" "/usr/local/miniconda3/envs/py312/bin/python" "/usr/local/miniconda3/bin/python" "/root/miniconda3/bin/python" "/opt/conda/bin/python" "$(command -v python3 || true)" "$(command -v python || true)"; do
  if [[ -n "$cand" ]] && probe_python "$cand" "$NEED_BNB"; then
    PY="$cand"
    break
  fi
done

if [[ -z "$PY" ]]; then
  echo "[Stage0] 现有 Python 环境未通过 GPU fp16 matmul + 核心依赖探测，修复或重建 /root/venv25 ..."
  BASE_SYS_PY=""
  for sc in "/usr/local/miniconda3/envs/py312/bin/python" "/opt/conda/bin/python" "/usr/local/miniconda3/bin/python" "/root/miniconda3/bin/python" "$(command -v python3 || true)" "$(command -v python || true)"; do
    if [[ -n "$sc" ]] && "$sc" -m pip --version >/dev/null 2>&1; then
      BASE_SYS_PY="$sc"
      break
    fi
  done
  [[ -n "$BASE_SYS_PY" ]] || { echo "[FATAL] 未找到可用 pip 的系统 Python！" >&2; exit 2; }

  PIP_MIRROR="${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"
  TORCH_MIRROR="${TORCH_INDEX_URL:-https://mirrors.aliyun.com/pytorch-wheels/cu124/}"

  if [[ ! -x "/root/venv25/bin/python" ]] || ! /root/venv25/bin/python -m pip --version >/dev/null 2>&1; then
    rm -rf /root/venv25
    "$BASE_SYS_PY" -m venv /root/venv25 --system-site-packages || "$BASE_SYS_PY" -m venv /root/venv25
  fi
  if ! /root/venv25/bin/python -c "import torch; assert torch.cuda.is_available(); a=torch.randn(16,16,device='cuda',dtype=torch.float16); torch.matmul(a,a)" >/dev/null 2>&1; then
    echo "[Stage0] 安装 torch==2.5.1 (cu124 / sm_70~sm_89) ..."
    /root/venv25/bin/python -m pip install -q --upgrade pip -i "$PIP_MIRROR" || true
    /root/venv25/bin/python -m pip install -q "torch==2.5.1" --index-url "$TORCH_MIRROR" --extra-index-url "$PIP_MIRROR" \
      || /root/venv25/bin/python -m pip install -q "torch==2.5.1" --index-url "https://download.pytorch.org/whl/cu124" --extra-index-url "$PIP_MIRROR"
  fi
  PKGS=("transformers>=4.51.0,<5.0.0" "peft>=0.13.0,<0.16.0" "datasets>=2.18.0,<4.0.0" "accelerate>=0.33.0,<2.0.0" "trl>=0.12.0,<0.18.0" "safetensors" "sentencepiece" "protobuf" "modelscope")
  if [[ "$NEED_BNB" == "1" ]]; then
    PKGS+=("bitsandbytes>=0.43.0,<0.47.0")
  fi
  /root/venv25/bin/python -m pip install -q -i "$PIP_MIRROR" "${PKGS[@]}"
  if probe_python "/root/venv25/bin/python" "$NEED_BNB"; then
    PY="/root/venv25/bin/python"
  else
    echo "[FATAL] /root/venv25 GPU fp16 torch.matmul 或核心训练库探测仍失败，拒绝盲跑！" >&2
    exit 2
  fi
fi

# vericut_e_training_sft.jsonl 实测 tok_max=1536；DPO max=627。>=40GB 走 3072/2048，其余走 2048/1536 均保证 0 截断
if [[ "$MAX_LEN_ARG" == "auto" ]]; then
  if [[ "${VRAM_MIB:-0}" -ge 40000 ]]; then MAX_LEN=3072; else MAX_LEN=2048; fi
else
  MAX_LEN="$MAX_LEN_ARG"
fi
if [[ "$DPO_MAX_LEN_ARG" == "auto" ]]; then
  if [[ "${VRAM_MIB:-0}" -ge 40000 ]]; then DPO_MAX_LEN=2048; else DPO_MAX_LEN=1536; fi
else
  DPO_MAX_LEN="$DPO_MAX_LEN_ARG"
fi
echo "[Stage0] PASS: PY=$PY | VRAM=${VRAM_MIB}MiB | max_len=$MAX_LEN | dpo_max_len=$DPO_MAX_LEN | qlora=$USE_QLORA"

# ----------------------------------------------------------------------
# Stage 1: SFT/DPO 语料存在性、Ledger SHA256、三基准 & 留出集去污染、单位与 DPO 检验
# ----------------------------------------------------------------------
for req in "$SFT_DATA" "$SFT_LEDGER" "$DPO_DATA"; do
  [[ -f "$req" ]] || { echo "[FATAL] 缺少必需语料/账本文件: $req" >&2; exit 2; }
done

SFT_SHA="$(sha256sum "$SFT_DATA" | awk '{print $1}')"
DPO_SHA="$(sha256sum "$DPO_DATA" | awk '{print $1}')"

"$PY" - "$SFT_DATA" "$SFT_LEDGER" "$DPO_DATA" "$REPO_ROOT" "$SCRIPT_DIR" <<'PY'
import hashlib, json, os, sys

sft_p, led_p, dpo_p, root, script_dir = sys.argv[1:6]
for d in (root, os.path.join(root, "scripts"), script_dir):
    if d and d not in sys.path:
        sys.path.insert(0, d)

from virtu_eval.contamination_check import assert_no_leak, jaccard, ngrams, prompt_hash, sample_text
from corpus_unit_audit import assert_units_clean
from train_dpo_all90 import validate_dpo_pairs

meta = json.load(open(led_p, "r", encoding="utf-8"))
files = meta.get("files", {})

def check_ledger(dp):
    act = hashlib.sha256(open(dp, "rb").read()).hexdigest()
    bn = os.path.basename(dp)
    ent = files.get(bn)
    exp = (ent.get("sha256") if isinstance(ent, dict) else ent) or meta.get("output_sha256") or meta.get("sha256") or ""
    if not str(exp).strip() or str(exp).strip().lower() != act.lower():
        raise SystemExit(f"[FATAL] Ledger 校验失败 ({dp}): expected={str(exp)[:16]} actual={act[:16]}")
    return act

s_sha = check_ledger(sft_p)
d_sha = check_ledger(dpo_p)

for sub in ("virtu_eval_v1", "virtu_eval_phys_v1", "virtu_eval_cl_v1"):
    bdir = os.path.join(root, "data", "benchmark", sub)
    if os.path.isdir(bdir):
        assert_no_leak(sft_p, bdir)
        assert_no_leak(dpo_p, bdir)

holdout_p = None
for cand in (
    os.path.join(root, "data", "sft", "vericut_e_training", "vericut_e_holdout.jsonl"),
    os.path.join(script_dir, "data", "sft", "vericut_e_training", "vericut_e_holdout.jsonl"),
):
    if os.path.isfile(cand):
        holdout_p = cand
        break

if holdout_p:
    h_hashes = set()
    h_ngrams = []
    for ln in open(holdout_p, "r", encoding="utf-8"):
        if not ln.strip():
            continue
        obj = json.loads(ln)
        p = str(obj.get("prompt") or "")
        h_hashes.add(prompt_hash(p))
        h_ngrams.append(ngrams(p, 8))
    for ln in open(sft_p, "r", encoding="utf-8"):
        if not ln.strip():
            continue
        u_txt, _ = sample_text(json.loads(ln))
        if prompt_hash(u_txt) in h_hashes:
            raise SystemExit("[FATAL] SFT 语料命中 vericut_e_holdout 完全相同提示词!")
        ung = ngrams(u_txt, 8)
        for hg in h_ngrams:
            if jaccard(ung, hg) >= 0.75:
                raise SystemExit("[FATAL] SFT 语料命中 vericut_e_holdout 高相似泄漏!")

assert_units_clean(sft_p)
assert_units_clean(dpo_p)
pairs = validate_dpo_pairs(dpo_p)
print(f"[Stage1] PASS: sft_sha={s_sha[:16]}... | dpo_sha={d_sha[:16]}... ({len(pairs)} pairs) | zero leaks & clean units")
PY

# ----------------------------------------------------------------------
# Stage 2: 训练器离线逻辑自检
# ----------------------------------------------------------------------
echo "[Stage2] 执行离线训练器自检 ..."
"$PY" "${SCRIPT_DIR}/train_turnkey.py" --selftest
"$PY" "${REPO_ROOT}/scripts/train_dpo_all90.py" --self-test

# ----------------------------------------------------------------------
# Stage 3: Qwen3-8B 非 Instruct 基座定位 / 拉取与血统锁定
# ----------------------------------------------------------------------
echo "[Stage3] 解析并锁死 Qwen3-8B 非 Instruct 基座 ..."
RESOLVED_BASE="$("$PY" - "$BASE_ARG" "${SCRIPT_DIR}/train_turnkey.py" "${REPO_ROOT}/scripts/train_dpo_all90.py" <<'PY'
import importlib.util, os, sys

base_arg, tk_path, dpo_path = sys.argv[1:4]
spec_tk = importlib.util.spec_from_file_location("train_turnkey", tk_path)
tk = importlib.util.module_from_spec(spec_tk)
spec_tk.loader.exec_module(tk)

spec_dpo = importlib.util.spec_from_file_location("train_dpo_all90", dpo_path)
dpo = importlib.util.module_from_spec(spec_dpo)
spec_dpo.loader.exec_module(dpo)

base_dir = tk.find_or_download_base(base_arg or None)
tk.assert_base_identity(base_dir)
dpo.assert_base_identity(base_dir, lineage="qwen3-8b")
print("RESOLVED_BASE=" + os.path.abspath(base_dir))
PY
)"
RESOLVED_BASE="$(printf '%s\n' "$RESOLVED_BASE" | grep '^RESOLVED_BASE=' | tail -n 1 | cut -d= -f2-)"
[[ -d "$RESOLVED_BASE" ]] || { echo "[FATAL] Stage3 未能解析出有效基座目录!" >&2; exit 2; }
echo "[Stage3] PASS: RESOLVED_BASE=$RESOLVED_BASE"

COMMON_SFT_ARGS=(--base "$RESOLVED_BASE" --data "$SFT_DATA" --ledger "$SFT_LEDGER" --gpu-id "$GPU_ID" --lr "$LR" --max-length "$MAX_LEN")
COMMON_DPO_ARGS=(--base "$RESOLVED_BASE" --data "$DPO_DATA" --beta "$BETA" --lr "$DPO_LR" --batch 1 --grad-accum 16 --max-length "$DPO_MAX_LEN")
if [[ "$USE_QLORA" -eq 1 ]]; then
  COMMON_SFT_ARGS+=(--qlora)
  COMMON_DPO_ARGS+=(--qlora)
fi

# ----------------------------------------------------------------------
# Stage 4: 真实 GPU 联合冒烟 (SFT 6步 + DPO 2步，快速实测防半小时后翻车)
# ----------------------------------------------------------------------
if [[ "$SKIP_SMOKE" -eq 0 && "$MAX_STEPS" -le 0 ]]; then
  SMOKE_SFT="${OUT_DIR}_smoke_sft"
  SMOKE_DPO="${OUT_DIR}_smoke_dpo"
  rm -rf "$SMOKE_SFT" "$SMOKE_DPO"
  echo "[Stage4a] 启动 SFT 6 步真实 GPU 冒烟 -> $SMOKE_SFT ..."
  "$PY" -u "${SCRIPT_DIR}/train_turnkey.py" "${COMMON_SFT_ARGS[@]}" --out "$SMOKE_SFT" --max-steps 6 --max-hours 0.30
  [[ -f "${SMOKE_SFT}/final_adapter/adapter_model.safetensors" ]] || { echo "[FATAL] Stage4a SFT 冒烟未产出权重！" >&2; exit 2; }

  if [[ "$SKIP_DPO" -eq 0 ]]; then
    echo "[Stage4b] 启动 DPO 2 步真实 GPU 冒烟 (接续 Stage4a adapter) -> $SMOKE_DPO ..."
    "$PY" -u "${REPO_ROOT}/scripts/train_dpo_all90.py" "${COMMON_DPO_ARGS[@]}" \
      --adapter "${SMOKE_SFT}/final_adapter" --out "$SMOKE_DPO" --max-steps 2 --max-hours 0.20
    [[ -f "${SMOKE_DPO}/final_dpo_adapter/adapter_model.safetensors" ]] || { echo "[FATAL] Stage4b DPO 冒烟未产出权重！" >&2; exit 2; }
  fi
  rm -rf "$SMOKE_SFT" "$SMOKE_DPO"
  echo "[Stage4] PASS: SFT+DPO 真实 GPU 冒烟全通，已清理临时目录"
  if [[ "$SMOKE_ONLY" -eq 1 ]]; then
    echo "[DONE] --smoke-only 完成，正常退出。"
    exit 0
  fi
fi

# ----------------------------------------------------------------------
# Stage 5: 记录 run_identity.json 测量宪法指纹锚点
# ----------------------------------------------------------------------
mkdir -p "$OUT_DIR"
rm -f "${OUT_DIR}/training_receipt.json" "${OUT_DIR}/virtu_vericut_e_deliverable.tar.gz" "${OUT_DIR}/virtu_vericut_e_deliverable.tar.gz.sha256"
"$PY" - "$OUT_DIR" "$SFT_DATA" "$SFT_SHA" "$DPO_DATA" "$DPO_SHA" "$RESOLVED_BASE" "$MAX_LEN" "$DPO_MAX_LEN" "$USE_QLORA" "${SCRIPT_DIR}/train_turnkey.py" "${REPO_ROOT}/scripts/train_dpo_all90.py" "${BASH_SOURCE[0]}" <<'PY'
import hashlib, json, os, sys, time, torch
(
    out_dir, sft_p, sft_sha, dpo_p, dpo_sha, base_dir, max_len, dpo_max_len,
    use_qlora, tk_p, dpo_tr_p, entry_p,
) = sys.argv[1:13]
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
ident = {
    "run_id": f"vericut_e_{time.strftime('%Y%m%d_%H%M%S')}_{sft_sha[:8]}",
    "model_lineage": "Qwen3-8B",
    "sft_dataset_path": sft_p,
    "sft_dataset_sha256": sft_sha,
    "dpo_dataset_path": dpo_p,
    "dpo_dataset_sha256": dpo_sha,
    "sft_trainer_sha256": sha(tk_p),
    "dpo_trainer_sha256": sha(dpo_tr_p),
    "entry_sha256": sha(entry_p),
    "base_path": base_dir,
    "max_length": int(max_len),
    "dpo_max_length": int(dpo_max_len),
    "use_qlora": bool(int(use_qlora)),
    "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "unknown",
    "vram_gb": round(torch.cuda.get_device_properties(0).total_memory / (1024**3), 2) if torch.cuda.is_available() else 0.0,
    "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
}
with open(os.path.join(out_dir, "run_identity.json"), "w", encoding="utf-8") as f:
    json.dump(ident, f, ensure_ascii=False, indent=2)
print(f"[Stage5] PASS: run_identity.json 写入 run_id={ident['run_id']}")
PY

# 时间预算分配: 75% 给 SFT, 剩余给 DPO (至少 0.35h)
read -r SFT_HOURS DPO_HOURS < <("$PY" - "$MAX_HOURS" <<'PY'
import sys
tot = float(sys.argv[1])
sft_h = max(0.3, round(tot * 0.75, 2))
dpo_h = max(0.35, round(tot - sft_h, 2))
print(f"{sft_h} {dpo_h}")
PY
)

# ----------------------------------------------------------------------
# Stage 6: 全量 SFT 训练
# ----------------------------------------------------------------------
SFT_OUT="output/virtu_vericut_e_sft"
rm -rf "$SFT_OUT"
echo "[Stage6] 启动 E:\\training + 涡轮叶片五轴全量 SFT (epochs=$EPOCHS max_len=$MAX_LEN max_hours=$SFT_HOURS) -> $SFT_OUT ..."
SFT_RC=0
"$PY" -u "${SCRIPT_DIR}/train_turnkey.py" "${COMMON_SFT_ARGS[@]}" \
  --out "$SFT_OUT" --epochs "$EPOCHS" --max-hours "$SFT_HOURS" --max-steps "$MAX_STEPS" || SFT_RC=$?

if [[ "$SFT_RC" -eq 3 ]]; then
  echo "[WARN] Stage6 SFT 因时间预算上限保存停机 (TIME_BUDGET_STOPPED, exit=3)"
  exit 3
elif [[ "$SFT_RC" -ne 0 ]]; then
  echo "[FATAL] Stage6 SFT 异常退出 rc=$SFT_RC" >&2
  exit "$SFT_RC"
fi

SFT_ADAPTER="${SFT_OUT}/final_adapter"
[[ -f "${SFT_ADAPTER}/adapter_model.safetensors" && -f "${SFT_ADAPTER}/training_receipt.json" ]] || {
  echo "[FATAL] Stage6 缺少 SFT final_adapter 或 training_receipt.json" >&2
  exit 2
}

# ----------------------------------------------------------------------
# Stage 7: 受控 DPO 偏好对齐 (可选 --skip-dpo 跳过)
# ----------------------------------------------------------------------
FINAL_SOURCE_DIR="$SFT_ADAPTER"
DPO_OUT="output/virtu_vericut_e_dpo"
if [[ "$SKIP_DPO" -eq 0 ]]; then
  rm -rf "$DPO_OUT"
  echo "[Stage7] 启动受控 DPO 对齐 (epochs=$DPO_EPOCHS beta=$BETA lr=$DPO_LR max_len=$DPO_MAX_LEN max_hours=$DPO_HOURS) ..."
  DPO_RC=0
  "$PY" -u "${REPO_ROOT}/scripts/train_dpo_all90.py" "${COMMON_DPO_ARGS[@]}" \
    --adapter "$SFT_ADAPTER" --out "$DPO_OUT" \
    --epochs "$DPO_EPOCHS" --max-hours "$DPO_HOURS" --max-steps "$MAX_STEPS" || DPO_RC=$?

  if [[ "$DPO_RC" -eq 3 ]]; then
    echo "[WARN] Stage7 DPO 因时间预算上限保存停机 (TIME_BUDGET_STOPPED, exit=3)"
    exit 3
  elif [[ "$DPO_RC" -ne 0 ]]; then
    echo "[FATAL] Stage7 DPO 异常退出 rc=$DPO_RC" >&2
    exit "$DPO_RC"
  fi

  FINAL_SOURCE_DIR="${DPO_OUT}/final_dpo_adapter"
  [[ -f "${FINAL_SOURCE_DIR}/adapter_model.safetensors" && -f "${FINAL_SOURCE_DIR}/training_receipt.json" ]] || {
    echo "[FATAL] Stage7 缺少 DPO final_dpo_adapter 或 training_receipt.json" >&2
    exit 2
  }
fi

# ----------------------------------------------------------------------
# Stage 8: 零语料漂移校验 + 统一交付包打包 + 最终 receipt 落盘
# ----------------------------------------------------------------------
DELIV_NAME="virtu_vericut_e_deliverable.tar.gz"
"$PY" - "$OUT_DIR" "$FINAL_SOURCE_DIR" "$SFT_OUT/final_adapter/training_receipt.json" "$SFT_DATA" "$SFT_SHA" "$DPO_DATA" "$DPO_SHA" "$RESOLVED_BASE" "$DELIV_NAME" "$SKIP_DPO" <<'PY'
import hashlib, json, os, shutil, sys, tarfile, time

(
    out_dir, src_dir, sft_rec_p, sft_data, start_sft_sha,
    dpo_data, start_dpo_sha, base_dir, deliv_name, skip_dpo,
) = sys.argv[1:11]

sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
if sha(sft_data) != start_sft_sha:
    raise SystemExit("[FATAL] Stage8 检测到训练期 SFT 语料漂移，本腿作废！")
if sha(dpo_data) != start_dpo_sha:
    raise SystemExit("[FATAL] Stage8 检测到训练期 DPO 语料漂移，本腿作废！")

sft_rec = json.load(open(sft_rec_p, "r", encoding="utf-8"))
src_rec = json.load(open(os.path.join(src_dir, "training_receipt.json"), "r", encoding="utf-8"))
if sft_rec.get("status") != "COMPLETED" or src_rec.get("status") != "COMPLETED":
    raise SystemExit(f"[FATAL] Stage8 回执非 COMPLETED: sft={sft_rec.get('status')} final={src_rec.get('status')}")

adapter_dir = os.path.join(out_dir, "virtu_lora_adapter")
if os.path.exists(adapter_dir):
    shutil.rmtree(adapter_dir)
shutil.copytree(src_dir, adapter_dir)

st_path = os.path.join(adapter_dir, "adapter_model.safetensors")
adapter_sha = sha(st_path)
if adapter_sha != src_rec.get("adapter_sha256"):
    raise SystemExit("[FATAL] Stage8 拷贝后权重 SHA256 异常")

unified_receipt = {
    **src_rec,
    "pipeline": "vericut_e_sft_plus_dpo" if skip_dpo == "0" else "vericut_e_sft_only",
    "base_model": base_dir,
    "dataset_path": sft_data if skip_dpo == "1" else dpo_data,
    "dataset_sha256": start_sft_sha if skip_dpo == "1" else start_dpo_sha,
    "sft_dataset_sha256": start_sft_sha,
    "dpo_dataset_sha256": start_dpo_sha,
    "sft_final_loss": sft_rec.get("final_train_loss"),
    "sft_total_train_samples": sft_rec.get("total_train_samples"),
    "total_train_samples": sft_rec.get("total_train_samples"),
    "final_train_loss": src_rec.get("final_loss") or sft_rec.get("final_train_loss"),
    "adapter_sha256": adapter_sha,
    "status": "COMPLETED",
    "completed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
}
for rp in (os.path.join(adapter_dir, "training_receipt.json"), os.path.join(out_dir, "training_receipt.json")):
    with open(rp, "w", encoding="utf-8") as rf:
        json.dump(unified_receipt, rf, ensure_ascii=False, indent=2)

deliv_tar = os.path.join(out_dir, deliv_name)
with tarfile.open(deliv_tar, "w:gz") as tar:
    tar.add(adapter_dir, arcname="virtu_lora_adapter")
tar_sha = sha(deliv_tar)
with open(deliv_tar + ".sha256", "w", encoding="utf-8", newline="\n") as sf:
    sf.write(f"{tar_sha}  {deliv_name}\n")

print(f"[Stage8] PASS: deliverable={deliv_tar} sha256={tar_sha[:16]}... | adapter={adapter_sha[:16]}...")
PY

(
  cd "$OUT_DIR"
  sha256sum -c "${DELIV_NAME}.sha256"
)

echo "======================================================================"
echo "[DONE] VERICUT E:\\training + 涡轮叶片五轴云端训练圆满完成 | $(date '+%Y-%m-%d %H:%M:%S')"
echo "交付包: ${OUT_DIR}/${DELIV_NAME}"
echo "======================================================================"
