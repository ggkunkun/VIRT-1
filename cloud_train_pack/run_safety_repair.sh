#!/usr/bin/env bash
# =============================================================================
# run_safety_repair.sh — Virtu 安全边界云端修复·一键入口（成本封顶 + 基座血统闸）
# -----------------------------------------------------------------------------
# 修复对象：2026-11-11 全模型越狱扫描暴露的 14 类安全缺陷（见 safety_boundary_manifest）。
# 真链：SFT -> DPO(--resume-adapter 防遗忘) -> peft 合并 -> 就地 14 例验收 -> GGUF。
#       本地部署验收走 deploy_safety_repair.py（merge_numpy/hf_to_gguf_numpy -> ollama create）。
#
# 成本与正确性保护
#   * 基座血统闸：开训前用 config.json 维度断言 Qwen3-8B，拒绝 Qwen2.5-7B 错配
#     （错配 LoRA 训出来也是废权重，先闸住再花钱）；
#   * --max-hours 封顶训练时长；--smoke 截断通用语料做冒烟。
#
# 用法
#   bash cloud_train_pack/run_safety_repair.sh --selftest          # 零 GPU 逻辑自检
#   bash cloud_train_pack/run_safety_repair.sh --base=/root/models/Qwen3-8B-Instruct
#   bash cloud_train_pack/run_safety_repair.sh --smoke             # 冒烟跑通管线
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BASE=""
MAX_HOURS="1.5"
NEW_TAG="virtu-safety-g1:latest"
BASE_TAG=""
REPEATS="10"
OUT="$ROOT/cloud_train_pack/output/virtu_safety"
EXTRA=()
SMOKE=0
SELFTEST=0
DEPLOY=0

for arg in "$@"; do
    case "$arg" in
        --base=*) BASE="${arg#*=}" ;;
        --max-hours=*) MAX_HOURS="${arg#*=}" ;;
        --new-tag=*) NEW_TAG="${arg#*=}" ;;
        --base-tag=*) BASE_TAG="${arg#*=}" ;;
        --repeats=*) REPEATS="${arg#*=}" ;;
        --out=*) OUT="${arg#*=}" ;;
        --skip-dpo) EXTRA+=("--skip-dpo") ;;
        --smoke) SMOKE=1 ;;
        --selftest) SELFTEST=1 ;;
        --deploy) DEPLOY=1 ;;
        *) echo "[WARN] 未知参数: $arg" ;;
    esac
done

# Python 环境探测（与 launch_cloud_full_train.sh 同口径）
if [ -n "${ECT_PYTHON:-}" ]; then PY="$ECT_PYTHON"
elif [ -x /opt/conda/bin/python3 ]; then PY="/opt/conda/bin/python3"
elif [ -x /opt/venv/bin/python ]; then PY="/opt/venv/bin/python"
else PY="python3"; fi

export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export TOKENIZERS_PARALLELISM=false
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"

echo "======================================================================"
echo "  Virtu 安全边界云端修复  |  Python: $PY  |  成本封顶: ${MAX_HOURS}h"
echo "======================================================================"

# 0) 零 GPU 自检：数据闸 / 混料 / 血统闸 / 验收闸反证
if [ "$SELFTEST" = "1" ]; then
    "$PY" -X utf8 cloud_train_pack/dataset/build_safety_boundary_sft.py --selftest
    "$PY" -X utf8 cloud_train_pack/train_safety_cloud.py --selftest
    "$PY" -X utf8 cloud_train_pack/deploy_safety_repair.py --selftest
    echo "[selftest] 安全修复管线逻辑自检全通过"
    exit 0
fi

# 单实例排他文件锁（防止重复计费与共享输出目录竞争）
LOCK_FILE="$ROOT/cloud_train_pack/.virtu_safety_repair.lock"
exec 9>"$LOCK_FILE"
flock -n 9 || {
    echo "[FATAL] 已有安全边界修复实例正在持有锁 ($LOCK_FILE)，拒绝并发！" >&2
    exit 1
}

# 1) 基座探测 + 血统闸（花钱之前先闸住错配基座）
if [ -z "$BASE" ]; then
    for cand in /root/models/Qwen3-8B-Instruct /root/models/Qwen3-8B \
                /root/autodl-tmp/Qwen3-8B-Instruct "$ROOT/checkpoints/_base_qwen3_8b"; do
        if [ -f "$cand/config.json" ]; then BASE="$cand"; break; fi
    done
fi
if [ -z "$BASE" ] || [ ! -f "$BASE/config.json" ]; then
    echo "[FATAL] 未找到基座目录，请用 --base=/path/to/Qwen3-8B-Instruct 指定"
    exit 1
fi
echo "[base] $BASE"
"$PY" -X utf8 -c "import sys; sys.path.insert(0,'cloud_train_pack'); \
from deploy_safety_repair import lineage_gate; print('[lineage]', lineage_gate('$BASE'))"

# 2) 依赖补齐与真实 CUDA fp16 matmul 探测
if ! "$PY" -c "import torch, transformers, peft, trl, datasets; assert torch.cuda.is_available(); a=torch.randn(16,16,device='cuda',dtype=torch.float16); c=torch.matmul(a,a); torch.cuda.synchronize()" &> /dev/null; then
    PIP_INDEX="${PIP_INDEX:-https://pypi.tuna.tsinghua.edu.cn/simple}"
    "$PY" -m pip install "peft>=0.13.0,<0.16.0" "transformers>=4.51.0,<5.0.0" "trl>=0.12.0,<0.18.0" \
        "datasets>=2.18.0,<4.0.0" "accelerate>=0.33.0,<2.0.0" "bitsandbytes>=0.43.0,<0.47.0" -i "$PIP_INDEX" -q
    "$PY" -c "import torch, transformers, peft, trl, datasets; assert torch.cuda.is_available(); a=torch.randn(16,16,device='cuda',dtype=torch.float16); c=torch.matmul(a,a); torch.cuda.synchronize()"
fi

# 3) SFT + DPO + 合并 + 就地 14 例验收（train_safety_cloud 自带数据闸与去污染闸）
TRAIN_ARGS=(--base "$BASE" --out "$OUT" --max-hours "$MAX_HOURS" --verify)
if [ "$SMOKE" = "1" ]; then TRAIN_ARGS+=(--max-general 200 --epochs 1 --dpo-epochs 1); fi
TRAIN_ARGS+=("${EXTRA[@]}")
echo "[train] $PY cloud_train_pack/train_safety_cloud.py ${TRAIN_ARGS[*]}"
"$PY" -X utf8 cloud_train_pack/train_safety_cloud.py "${TRAIN_ARGS[@]}"

# 4) 可选：本机若有 Ollama，直接部署 + 被服务模型验收（否则打印本地部署命令）
MERGED="$OUT/merged"
if [ "$DEPLOY" = "1" ] && command -v ollama &> /dev/null; then
    DEPLOY_ARGS=(--merged "$MERGED" --new-tag "$NEW_TAG" --repeats "$REPEATS" --out "$OUT/deploy")
    if [ -n "$BASE_TAG" ]; then DEPLOY_ARGS+=(--base-tag "$BASE_TAG"); fi
    "$PY" -X utf8 cloud_train_pack/deploy_safety_repair.py "${DEPLOY_ARGS[@]}"
else
    echo "======================================================================"
    echo "  训练与就地验收完成。合并权重: $MERGED"
    echo "  拉回本机后执行真实部署 + 被服务模型验收："
    echo "    python cloud_train_pack/deploy_safety_repair.py \\"
    echo "        --merged $MERGED --new-tag $NEW_TAG \\"
    echo "        ${BASE_TAG:+--base-tag $BASE_TAG }--repeats $REPEATS"
    echo "======================================================================"
fi