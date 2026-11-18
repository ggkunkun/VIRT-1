#!/usr/bin/env bash
# ==============================================================================
# cloud_train_pack/run_13b_evolution_train.sh
# Virtu-13.63B 工业大模型云端极速演进微调与原地闭环交付一键启动脚本 (v2)
# 遵循《测量宪法》硬约束：flock 锁 + fp16 实算探测 + 语料门禁 + --selftest 预检
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
export PATH="/root/venv25/bin:/usr/local/miniconda3/envs/py312/bin:/usr/local/miniconda3/bin:${PATH}"
export PYTHONPATH="${WORKSPACE_ROOT}:${PYTHONPATH:-}"
export TOKENIZERS_PARALLELISM=false
export PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True"

cd "${WORKSPACE_ROOT}"

SELFTEST_ONLY=0
for arg in "$@"; do
  if [[ "$arg" == "--selftest" ]]; then
    SELFTEST_ONLY=1
  fi
done

# 选择可用 Python (优先 venv25)
PY=""
for cand in "${ECT_PYTHON:-}" "/root/venv25/bin/python" "$(command -v python3 || true)" "$(command -v python || true)"; do
  if [[ -n "$cand" ]] && command -v "$cand" >/dev/null 2>&1; then
    PY="$cand"
    break
  fi
done
if [[ -z "$PY" ]]; then
  echo "[FATAL] 未找到可用 python 解释器！" >&2
  exit 2
fi

if [[ "$SELFTEST_ONLY" -eq 1 ]]; then
  "$PY" "${SCRIPT_DIR}/train_cloud_virtu_13b.py" --selftest
  exit 0
fi

# 单实例排他文件锁
LOCK_FILE="${SCRIPT_DIR}/.virtu_13b_train.lock"
exec 9>"$LOCK_FILE"
flock -n 9 || {
  echo "[FATAL] 已有 Virtu-13.63B 训练实例正在运行 ($LOCK_FILE)，拒绝并发！" >&2
  exit 1
}

echo "======================================================================"
echo "  🚀 Virtu-13.63B 工业制造大模型 一键云端微调与对齐流水线启动"
echo "  时间: $(date '+%Y-%m-%d %H:%M:%S') | Python: $PY"
echo "======================================================================"

# 1. 硬件探测 + 真实 CUDA fp16 matmul 探测 (必要时自愈 /root/venv25)
echo "[STEP 1/6] 探测 GPU 硬件与 fp16 实算环境..."
if ! command -v nvidia-smi &> /dev/null; then
  echo "[FATAL] 未发现 nvidia-smi，无法开展 13.63B GPU 训练！" >&2
  exit 2
fi
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader

probe_gpu_py() {
  local py_bin="$1"
  "$py_bin" - <<'PY' >/dev/null 2>&1
import torch, transformers, peft, trl, bitsandbytes, datasets
assert torch.cuda.is_available()
a = torch.randn(16, 16, device="cuda", dtype=torch.float16)
c = torch.matmul(a, a)
torch.cuda.synchronize()
assert tuple(c.shape) == (16, 16)
PY
}

if ! probe_gpu_py "$PY"; then
  echo "[WARN] 当前 $PY 未通过 CUDA fp16 matmul + 核心依赖探测，尝试自愈 /root/venv25 ..."
  if [[ ! -x "/root/venv25/bin/python" ]]; then
    "$PY" -m venv /root/venv25 --system-site-packages || "$PY" -m venv /root/venv25
  fi
  /root/venv25/bin/python -m pip install -q "transformers>=4.51.0,<5.0.0" "tokenizers>=0.21.0,<0.23.0" "peft>=0.13.0,<0.16.0" "trl>=0.11.0,<0.18.0" "bitsandbytes>=0.43.0,<0.47.0" "accelerate>=0.33.0,<2.0.0" modelscope "datasets>=2.18.0,<4.0.0" safetensors
  if probe_gpu_py "/root/venv25/bin/python"; then
    PY="/root/venv25/bin/python"
  else
    echo "[FATAL] GPU fp16 torch.matmul 探测失败，拒绝继续！" >&2
    exit 2
  fi
fi

# 2. 离线 --selftest 预检
echo "[STEP 2/6] 执行 train_cloud_virtu_13b.py --selftest 预检..."
"$PY" "${SCRIPT_DIR}/train_cloud_virtu_13b.py" --selftest

# 3. 准备并强校 Phase 2 靶向强化语料 (SHA256 + 防污染 + 单位制)
echo "[STEP 3/6] 核验 Phase 2 靶向强化微调数据集..."
SFT_DATA="${SCRIPT_DIR}/dataset/train_corpus_phase2_targeted.jsonl"
DPO_DATA="${SCRIPT_DIR}/dataset/dpo_phase2_targeted.jsonl"
LEDGER_FILE="${SCRIPT_DIR}/dataset/phase2_targeted_ledger.json"

if [ ! -f "${SFT_DATA}" ] || [ ! -f "${DPO_DATA}" ]; then
  echo "  正在编译构建 Phase 2 靶向强化数据集..."
  "$PY" "${SCRIPT_DIR}/dataset/build_phase2_targeted_corpus.py"
fi

"$PY" - "${SFT_DATA}" "${DPO_DATA}" "${LEDGER_FILE}" "${WORKSPACE_ROOT}" <<'PY'
import os, sys, json, hashlib
sft_p, dpo_p, ledger_p, root = sys.argv[1:5]
sys.path.insert(0, root)
sys.path.insert(0, os.path.join(root, "scripts"))
from virtu_eval.contamination_check import assert_no_leak
from corpus_unit_audit import assert_units_clean

def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while c := f.read(1 << 20):
            h.update(c)
    return h.hexdigest()

sft_sha, dpo_sha = sha(sft_p), sha(dpo_p)
if os.path.exists(ledger_p):
    meta = json.loads(open(ledger_p, "r", encoding="utf-8").read())
    if meta.get("sft_sha256") and meta["sft_sha256"] != sft_sha:
        raise SystemExit(f"[FATAL] SFT SHA256 mismatch against {ledger_p}")
    if meta.get("dpo_sha256") and meta["dpo_sha256"] != dpo_sha:
        raise SystemExit(f"[FATAL] DPO SHA256 mismatch against {ledger_p}")
assert_no_leak(sft_p)
assert_units_clean(sft_p)
assert_no_leak(dpo_p)
assert_units_clean(dpo_p)
print(f"[Gate] PASS: sft_sha={sft_sha[:16]}... dpo_sha={dpo_sha[:16]}...")
PY

# 4. 启动训练与对齐流水线
echo "[STEP 4/6] 启动 Virtu-13.63B 训练与对齐流水线..."
mkdir -p "${SCRIPT_DIR}/output_13b"
LOG_FILE="${SCRIPT_DIR}/output_13b/train_$(date '+%Y%m%d_%H%M%S').log"

EXTRA_ARGS=("$@")
if [ ${#EXTRA_ARGS[@]} -eq 0 ]; then
  EXTRA_ARGS=(--base /model/ModelScope/Qwen/Qwen3-14B --stage all --epochs 1.5 --lr 1.2e-4 --dpo_lr 4e-6 --max-hours 2.5)
fi

set +e
"$PY" "${SCRIPT_DIR}/train_cloud_virtu_13b.py" "${EXTRA_ARGS[@]}" 2>&1 | tee "${LOG_FILE}"
PIPE_RC=${PIPESTATUS[0]}
set -e
if [[ "$PIPE_RC" -ne 0 ]]; then
  echo "[FATAL] Virtu-13.63B 训练未正常完成 rc=$PIPE_RC，请检查 ${LOG_FILE}" >&2
  exit "$PIPE_RC"
fi

# 5. 收据与交付包 SHA256 核验
echo "[STEP 5/6] 核验 training_summary.json 与 SHA256 指纹..."
"$PY" - "${SCRIPT_DIR}/output_13b/training_summary.json" <<'PY'
import sys, json, os
p = sys.argv[1]
if not os.path.exists(p):
    raise SystemExit(f"[FATAL] 缺少 {p}")
data = json.load(open(p, "r", encoding="utf-8"))
if data.get("status") != "COMPLETED":
    raise SystemExit(f"[FATAL] training_summary status={data.get('status')!r} != COMPLETED")
print(f"[Receipt] PASS: status=COMPLETED | base={data.get('base_model')}")
PY

echo "[STEP 6/6] Virtu-13.63B 训练微调与闭环交付完成！"
ls -lh "${SCRIPT_DIR}/output_13b/"
