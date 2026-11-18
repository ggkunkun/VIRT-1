#!/usr/bin/env bash
# =============================================================================
# launch_cloud_full_train.sh — Virtu 云端全面训练与全维度高分测评·一键总入口 (v2)
# -----------------------------------------------------------------------------
# 适用平台：AutoDL / 丹摩 Damodel / 恒源云 / RunPod / Lambda / 阿里云 / 本地 GPU
# 常用开关：
#   --base=/path/to/Qwen3-8B    # 指定本地预置基座目录（跳过联网下载）
#   --skip-dpo                 # 跳过 DPO 阶段，仅跑 SFT 与全维度评测
#   --smoke                    # 20 步极速冒烟跑通全管线
#   --selftest                 # 零 GPU 依赖全流程逻辑自检
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SELFTEST_ONLY=0
for arg in "$@"; do
  if [[ "$arg" == "--selftest" ]]; then
    SELFTEST_ONLY=1
  fi
done

# 1. Python 环境探测
if [ -n "${ECT_PYTHON:-}" ]; then
  PY="$ECT_PYTHON"
  PIP="${ECT_PIP:-$ECT_PYTHON -m pip}"
elif [ -x /root/venv25/bin/python ]; then
  PY="/root/venv25/bin/python"
  PIP="/root/venv25/bin/pip"
elif [ -x /opt/conda/bin/python3 ]; then
  PY="/opt/conda/bin/python3"
  PIP="/opt/conda/bin/pip"
elif [ -x /opt/venv/bin/python ]; then
  PY="/opt/venv/bin/python"
  PIP="/opt/venv/bin/pip"
else
  PY="$(command -v python3 || command -v python)"
  PIP="$PY -m pip"
fi

export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export TOKENIZERS_PARALLELISM=false
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"
export VIRTU_REPO_ROOT="$ROOT"

if [[ "$SELFTEST_ONLY" -eq 1 ]]; then
  echo "[Selftest] 执行 train_cloud_virtu_evolution.py --selftest ..."
  "$PY" "$ROOT/cloud_train_pack/train_cloud_virtu_evolution.py" --selftest
  exit 0
fi

# 单实例排他文件锁
LOCK_FILE="$ROOT/cloud_train_pack/.virtu_full_train.lock"
exec 9>"$LOCK_FILE"
flock -n 9 || {
  echo "[FATAL] 已有全面训练实例正在持有锁 ($LOCK_FILE)，禁止并发启动！" >&2
  exit 1
}

echo "======================================================================"
echo "  🚀 Virtu 工业大模型 · 云端全面训练与全维度高分测评闭环系统"
echo "  工作区: $ROOT | Python 解释器: $PY"
echo "======================================================================"

# 2. GPU 算力 + fp16 torch.matmul 实算探测
echo "[1/6] GPU 硬件与 fp16 实算探测..."
if ! command -v nvidia-smi &> /dev/null; then
  echo "[FATAL] 未找到 nvidia-smi，无法启动云端 GPU 训练！" >&2
  exit 2
fi
nvidia-smi --query-gpu=index,name,memory.total,memory.free,driver_version --format=csv,noheader

probe_gpu_py() {
  local py_bin="$1"
  "$py_bin" - <<'PY' >/dev/null 2>&1
import torch, transformers, peft, trl, bitsandbytes, datasets, modelscope
assert torch.cuda.is_available()
a = torch.randn(16, 16, device="cuda", dtype=torch.float16)
c = torch.matmul(a, a)
torch.cuda.synchronize()
assert tuple(c.shape) == (16, 16)
PY
}

echo "[2/6] 校验与自愈 Python/CUDA 核心依赖..."
PIP_INDEX="${PIP_INDEX:-https://pypi.tuna.tsinghua.edu.cn/simple}"
if ! probe_gpu_py "$PY"; then
  echo "  当前 $PY 未通过 CUDA fp16 matmul + 核心库探测，尝试补齐依赖或构建 /root/venv25 ..."
  $PIP install "peft>=0.13.0,<0.16.0" "bitsandbytes>=0.43.0,<0.47.0" "modelscope" "transformers>=4.51.0,<5.0.0" "datasets>=2.18.0,<4.0.0" "accelerate>=0.33.0,<2.0.0" "trl>=0.12.0,<0.18.0" -i "$PIP_INDEX" -q || true
  if ! probe_gpu_py "$PY"; then
    if [[ ! -x /root/venv25/bin/python ]]; then
      "$PY" -m venv /root/venv25 --system-site-packages || "$PY" -m venv /root/venv25
    fi
    /root/venv25/bin/python -m pip install -q "peft>=0.13.0,<0.16.0" "bitsandbytes>=0.43.0,<0.47.0" "modelscope" "transformers>=4.51.0,<5.0.0" "datasets>=2.18.0,<4.0.0" "accelerate>=0.33.0,<2.0.0" "trl>=0.12.0,<0.18.0" -i "$PIP_INDEX"
    if probe_gpu_py /root/venv25/bin/python; then
      PY="/root/venv25/bin/python"
    else
      echo "[FATAL] GPU fp16 torch.matmul 实算探测仍失败，拒绝盲跑！" >&2
      exit 2
    fi
  fi
fi
echo "  [OK] Python=$PY 已通过 fp16 torch.matmul 实算探测"

# 3. 执行离线逻辑自检预检
echo "[3/6] 执行 train_cloud_virtu_evolution.py --selftest 预检..."
"$PY" "$ROOT/cloud_train_pack/train_cloud_virtu_evolution.py" --selftest

# 4. 高分微调与 DPO 语料构建 + SHA256/防污染/单位门禁
echo "[4/6] 检查高分语料集与 DPO 偏好对并运行防污染/单位审计..."
SFT_DATA="$ROOT/cloud_train_pack/dataset/train_corpus_comprehensive.jsonl"
DPO_DATA="$ROOT/cloud_train_pack/dataset/dpo_comprehensive_pairs.jsonl"
if [ ! -f "$SFT_DATA" ] || [ ! -f "$DPO_DATA" ]; then
  echo "  语料缺失，启动 build_high_score_corpus.py 构建高分语料..."
  "$PY" "$ROOT/cloud_train_pack/build_high_score_corpus.py" --samples 7000 --dpo-pairs 1000
fi

"$PY" - "$SFT_DATA" "$DPO_DATA" "$ROOT" <<'PY'
import os, sys, json, hashlib
sft_p, dpo_p, root = sys.argv[1:4]
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

manifest_p = os.path.join(os.path.dirname(sft_p), "corpus_manifest.json")
sft_sha = sha(sft_p)
if os.path.exists(manifest_p):
    man = json.loads(open(manifest_p, "r", encoding="utf-8").read())
    exp = man.get("sft_sha256") or (man.get("files") or {}).get(os.path.basename(sft_p), {}).get("sha256")
    if exp and exp != sft_sha:
        raise SystemExit(f"[FATAL] SFT SHA256 与 {manifest_p} 不符")
assert_no_leak(sft_p)
assert_units_clean(sft_p)
assert_no_leak(dpo_p)
assert_units_clean(dpo_p)
print(f"[Gate] PASS: sft={sft_sha[:16]}... dpo={sha(dpo_p)[:16]}...")
PY

# 5. 启动主训练与全维度就地测评引擎
echo "[5/6] 启动主训练与闭环测评总引擎 (train_cloud_virtu_evolution.py)..."
"$PY" "$ROOT/cloud_train_pack/train_cloud_virtu_evolution.py" "$@"

echo "[6/6] 🎉 训练、评测与交付全流程圆满完成！"
echo "  成果物目录: $ROOT/cloud_train_pack/output"
