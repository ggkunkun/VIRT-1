#!/usr/bin/env bash
# =============================================================================
# Virtu 工程能力训练 — 云端一键开训（零值守 / 零手工干预）
# -----------------------------------------------------------------------------
# 最小用法（裸 GPU VM，有外网）：
#   bash engineering_capability_train/cloud/launch.sh
#
# 自带基座（离线集群）：
#   export VIRTU_BASE=/models/Qwen3-8B
#   bash engineering_capability_train/cloud/launch.sh --no-download
#
# Docker：
#   docker run --gpus all -e VIRTU_BASE=/models/Qwen3-8B \
#     -v /models:/models:ro -v "$PWD:/workspace" virtu-ect:1.0.0
#
# 自动完成：GPU 体检 + profile 选择（不依赖 torch） → 缺依赖则装（含国内镜像）
#           → 缺基座则下载（含镜像） → manifest 校验 → 分词自检
#           → SFT(QLoRA) → DPO → 打包回传 adapter + 日志
#
# 退出码：0=成功；非 0=SFT/DPO 失败（已打包日志，便于定位）。
# =============================================================================
set -euo pipefail

PKG="engineering_capability_train"
ROOT="${VIRTU_REPO_ROOT:-$(pwd)}"
cd "$ROOT"

# --- Python 选择：显式覆盖 > 平台 conda > venv > 系统 python3 ---
if [ -n "${ECT_PYTHON:-}" ]; then
    PY="$ECT_PYTHON"
    PIP="${ECT_PIP:-$ECT_PYTHON -m pip}"
elif [ -x /opt/conda/bin/python3 ]; then
    PY=/opt/conda/bin/python3
    PIP=/opt/conda/bin/pip
elif [ -x /opt/venv/bin/python ]; then
    PY=/opt/venv/bin/python
    PIP=/opt/venv/bin/pip
else
    PY=python3
    PIP=pip
fi

export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export TOKENIZERS_PARALLELISM=false
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"
export VIRTU_REPO_ROOT="$ROOT"

INSTALL_DEPS=auto
SKIP_DPO=0
SELFTEST_ONLY=0
NO_DOWNLOAD=0
PROFILE=""
for arg in "$@"; do
    case "$arg" in
        --install-deps) INSTALL_DEPS=1 ;;
        --no-install-deps) INSTALL_DEPS=0 ;;
        --skip-dpo) SKIP_DPO=1 ;;
        --selftest-only) SELFTEST_ONLY=1 ;;
        --no-download) NO_DOWNLOAD=1 ;;
        --profile=*) PROFILE="${arg#--profile=}" ;;
        *) echo "[WARN] 忽略未知参数: $arg" ;;
    esac
done

echo "======================================================================"
echo "  Virtu Engineering Capability Training — cloud launch"
echo "  repo=$ROOT  python=$PY"
echo "======================================================================"

# 产物打包（无论成败都尽量保留证据）
_package_artifacts() {
    local status="$1"
    mkdir -p "$PKG/artifacts"
    local STAMP
    STAMP=$(date +%Y%m%d_%H%M%S)
    local TAR="$PKG/artifacts/ect_adapters_${STAMP}.tar.gz"
    tar -czf "$TAR" \
        "$PKG/artifacts/ect_sft_adapter" \
        "$PKG/artifacts/ect_dpo_adapter" \
        "$PKG/artifacts/sft_train.log" \
        "$PKG/artifacts/dpo_train.log" 2>/dev/null \
        || tar -czf "$TAR" "$PKG/artifacts/ect_sft_adapter" \
            "$PKG/artifacts/sft_train.log" 2>/dev/null \
        || true
    if [ -f "$TAR" ]; then
        sha256sum "$TAR" | tee "$TAR.sha256"
        echo "[package] status=$status -> $TAR"
    fi
}

# --- Step 1/6 GPU 体检与 profile 自动选择（不依赖 torch，直接读 nvidia-smi） ---
echo "[1/6] GPU 体检与 profile 选择"
nvidia-smi --query-gpu=index,name,memory.total,driver_version --format=csv,noheader \
    || { echo "[ERROR] 未检测到 NVIDIA GPU，无法开训"; exit 1; }
if [ -z "$PROFILE" ]; then
    PROFILE=$("$PY" - <<'PY' 2>/dev/null || echo l40s_48g
import re, subprocess
out = subprocess.check_output(
    ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"]
).decode(errors="replace")
name, mem = (out.splitlines()[0].split(",") + ["", ""])[:2]
mem_gb = int(re.sub(r"[^0-9]", "", mem) or 0) / 1024.0
nl = name.lower()
if "v100" in nl:
    prof = "v100_32g"
elif re.search(r"a100|h100|h200|a800|h800", nl):
    prof = "a100_80g"
else:
    prof = "l40s_48g"
print(prof)
PY
    )
fi
echo "  -> profile=$PROFILE"

# --- Step 2/6 依赖（缺则自动安装；V100 严禁 flash-attn） ---
if [ "$INSTALL_DEPS" = "0" ]; then
    echo "[2/6] 跳过依赖安装（--no-install-deps）"
elif [ "$INSTALL_DEPS" = "1" ] || ! "$PY" -c "import torch, transformers, peft" 2>/dev/null; then
    echo "[2/6] 安装锁定依赖（torch/transformers/peft/bitsandbytes/datasets/accelerate）"
    PIP_INDEX="${PIP_INDEX:-https://pypi.tuna.tsinghua.edu.cn/simple}"
    "$PIP" install -r "$PKG/requirements-cloud.txt" -i "$PIP_INDEX" -q
else
    echo "[2/6] 依赖已就绪，跳过安装"
fi

# --- Step 3/6 基座解析 / 下载 ---
echo "[3/6] 基座解析"
if [ "$NO_DOWNLOAD" = "1" ]; then
    echo "  --no-download：要求 VIRTU_BASE 指向本地基座目录"
    if [ -z "${VIRTU_BASE:-}" ] || [ ! -f "${VIRTU_BASE}/config.json" ]; then
        echo "[ERROR] --no-download 但 VIRTU_BASE 无效：${VIRTU_BASE:-未设置}"
        exit 1
    fi
else
    # shellcheck source=/dev/null
    source "$PKG/cloud/download_base.sh"
fi
echo "  -> VIRTU_BASE=$VIRTU_BASE"
if [ ! -f "$VIRTU_BASE/config.json" ]; then
    echo "[ERROR] 基座不可用: $VIRTU_BASE"
    exit 1
fi

# --- Step 4/6 语料门禁 + 分词自检 ---
echo "[4/6] 语料 sha256 校验与门禁 + 分词自检"
"$PY" "$PKG/01_prepare_data.py" --verify-only
"$PY" "$PKG/validate_corpus.py" --report-out "$PKG/data/validation_report.json"
"$PY" "$PKG/train_sft.py" --selftest --base "$VIRTU_BASE"
if [ "$SELFTEST_ONLY" -eq 1 ]; then
    echo "[selftest-only] 链路自检完成，未开训"
    exit 0
fi

# --- Step 5/6 SFT ---
echo "[5/6] 阶段1 SFT（QLoRA r=32/alpha=64，只产 adapter）"
set +e
"$PY" "$PKG/train_sft.py" --profile "$PROFILE" --base "$VIRTU_BASE" --engine native \
    2>&1 | tee "$PKG/artifacts/sft_train.log"
SFT_RC=${PIPESTATUS[0]}
set -e
if [ "$SFT_RC" -ne 0 ]; then
    echo "[ERROR] SFT 失败 (rc=$SFT_RC)，详见 $PKG/artifacts/sft_train.log"
    _package_artifacts "SFT_FAILED"
    exit "$SFT_RC"
fi
"$PY" - "$PKG/artifacts/ect_sft_adapter/training_receipt.json" <<'PY'
import json, sys
r = json.load(open(sys.argv[1], encoding="utf-8"))
if r.get("status") != "COMPLETED":
    raise SystemExit(f"SFT receipt 非 COMPLETED: {r.get('status')}")
print(f"  SFT OK: loss={r.get('train_loss')} step={r.get('global_step')} "
      f"runtime={r.get('runtime_seconds')}s")
PY

# --- Step 6/6 DPO（可选） ---
if [ "$SKIP_DPO" -eq 1 ]; then
    echo "[6/6] 跳过 DPO（--skip-dpo）"
else
    echo "[6/6] 阶段2 DPO（chosen=物理合规且最快 / rejected=违规·更慢·瞎猜）"
    set +e
    "$PY" "$PKG/train_dpo.py" --base "$VIRTU_BASE" \
        2>&1 | tee "$PKG/artifacts/dpo_train.log"
    DPO_RC=${PIPESTATUS[0]}
    set -e
    if [ "$DPO_RC" -ne 0 ]; then
        echo "[ERROR] DPO 失败 (rc=$DPO_RC)，详见 $PKG/artifacts/dpo_train.log"
        _package_artifacts "DPO_FAILED"
        exit "$DPO_RC"
    fi
fi

_package_artifacts "OK"

echo "======================================================================"
echo "  云端训练完成，产物已打包回传（见上方 tar 路径）"
echo "  下一步（本机）：python engineering_capability_train/03_merge_local.py \\"
echo "        --sft-adapter <解压后>/ect_sft_adapter \\"
echo "        --dpo-adapter <解压后>/ect_dpo_adapter \\"
echo "        --out checkpoints/ect_merged"
echo "  再 GGUF -> Ollama 注册 -> 真实 GUI 评测。详见 README.md"
echo "======================================================================"
