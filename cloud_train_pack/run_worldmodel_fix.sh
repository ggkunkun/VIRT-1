#!/usr/bin/env bash
# =============================================================================
# cloud_train_pack/run_worldmodel_fix.sh
# Virtu 世界工程模型（World Engineering Model）云端一键修复训练闭环（v2 硬化版）
#
# 相对 v1 的修复（全部来自 2026-11-09/11-10 实测踩坑）：
#   1. 环境自修复：实例预装 torch(cu13x) 在 V100(sm_70) 上 is_available 撒谎、
#      加载即崩 —— 先真实 fp16 matmul 探针，失败自动建 venv25 (torch 2.5.0+cu124)。
#   2. 不再默认安装 bitsandbytes：V100-32GB 走全量 fp16 LoRA（实测 ~22GB 显存），
#      QLoRA(nf4) 仅在显式 USE_QLORA=1 且架构支持时才装。
#   3. sha256sum 硬闸：v1 的 `|| true` 让校验空转，违反测量宪法第 4 条。
#   4. 单实例锁（flock）：测量链是独占资源，防两条链并行污染。
#   5. 20 步冒烟先行：冒烟不过不开正式训练，避免付费卡上白烧。
#   6. 基座身份闸：拒绝 Instruct 变体（本尊基座是 Qwen3-8B，错基座=全腿作废）。
#   7. 开训前落 run_identity.json（语料/训练器/脚本指纹 + GPU），供回收侧漂移核对。
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ---- 单实例锁：同一工作目录只允许一条训练链 -------------------------------
exec 9>"$SCRIPT_DIR/.wm_train.lock"
if ! flock -n 9; then
    echo "[FATAL] 另一条世界模型训练链已持有本目录锁。测量链是独占资源，拒绝并行。"
    exit 1
fi

export PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True"
export TOKENIZERS_PARALLELISM="false"
export PYTHONUTF8="1"

DATA_FILE="${DATA_FILE:-dataset/virtu_worldmodel_fix_sft.jsonl}"
OUT_DIR="${OUT_DIR:-output/virtu_wm_lora_fix}"
EPOCHS="${EPOCHS:-2.5}"
LR="${LR:-1.0e-4}"
BATCH="${BATCH:-2}"
GRAD_ACCUM="${GRAD_ACCUM:-8}"
MAX_LEN="${MAX_LEN:-2560}"
MAX_HOURS="${MAX_HOURS:-2.0}"
USE_QLORA="${USE_QLORA:-0}"
BASE_DIR="${BASE_DIR:-}"
VENV_DIR="${VENV_DIR:-$SCRIPT_DIR/venv25}"
PIP_MIRROR="https://pypi.tuna.tsinghua.edu.cn/simple"
TORCH_MIRROR="https://mirrors.aliyun.com/pytorch-wheels/cu124/"

echo "======================================================================"
echo "   Virtu 世界工程模型 — 云端修复训练 v2（环境自修复 + 硬门禁 + 冒烟）"
echo "======================================================================"

# ---- Stage 0: GPU 事实 -----------------------------------------------------
echo "[Stage 0/7] GPU 事实 ..."
nvidia-smi --query-gpu=index,name,memory.total,memory.free,compute_cap --format=csv

# ---- 真实 matmul 探针：is_available 会撒谎，必须实算 -----------------------
probe_python() {
    "$1" - <<'PY'
import sys
try:
    import torch
    if not torch.cuda.is_available():
        print("[probe] cuda.is_available=False"); sys.exit(1)
    cc = torch.cuda.get_device_capability(0)
    x = torch.randn(256, 256, device="cuda", dtype=torch.float16)
    y = torch.matmul(x, x)
    torch.cuda.synchronize()
    if not torch.isfinite(y).all():
        print("[probe] matmul 产出非有限值"); sys.exit(1)
    print(f"[probe] OK torch={torch.__version__} cc={cc} gpu={torch.cuda.get_device_name(0)}")
except Exception as e:
    print(f"[probe] FAIL {type(e).__name__}: {e}")
    sys.exit(1)
PY
}

pick_system_python() {
    for c in /opt/conda/bin/python3 python3.11 python3.10 python3; do
        if command -v "$c" >/dev/null 2>&1; then echo "$c"; return 0; fi
    done
    echo "[FATAL] 找不到系统 python3" >&2; return 1
}

# CUDA 探针过了不代表能开训：transformers/peft/modelscope 缺一个都会在半路崩
probe_deps() {
    "$1" - <<'PY'
import importlib, sys
missing = []
for m in ("transformers", "peft", "accelerate", "modelscope", "sentencepiece", "safetensors"):
    try:
        importlib.import_module(m)
    except Exception:
        missing.append(m)
if missing:
    print("[deps] MISSING " + ",".join(missing)); sys.exit(1)
print("[deps] OK")
PY
}

install_train_deps() {
    "$1" -m pip install -q \
        "transformers>=4.51.0,<5.0.0" "peft>=0.13.0,<0.16.0" "accelerate>=0.33.0,<2.0.0" "modelscope" \
        "sentencepiece" "safetensors" -i "$PIP_MIRROR"
}

SYS_PY="$(pick_system_python)"
PYTHON_CMD="$SYS_PY"
USE_SYSTEM=0
if probe_python "$PYTHON_CMD"; then
    if probe_deps "$PYTHON_CMD"; then
        USE_SYSTEM=1
    else
        echo "[Env] CUDA 可用但训练依赖缺失，先向系统环境补齐 ..."
        if install_train_deps "$SYS_PY" && probe_deps "$PYTHON_CMD"; then
            USE_SYSTEM=1
        fi
    fi
fi
if [ "$USE_SYSTEM" = "1" ]; then
    echo "[Env] 系统 Python 环境通过真实 matmul 探针与依赖检查，直接使用。"
else
    echo "[Env] 系统环境不可用（典型：torch cu13x 无 sm_70 内核）。重建 venv25 (torch 2.5.0+cu124) ..."
    if [ -x "$VENV_DIR/bin/python" ] && probe_python "$VENV_DIR/bin/python" && probe_deps "$VENV_DIR/bin/python"; then
        echo "[Env] 复用既有 venv25。"
    else
        if command -v uv >/dev/null 2>&1; then
            uv venv "$VENV_DIR" --python 3.10
        else
            "$SYS_PY" -m venv "$VENV_DIR"
        fi
        "$VENV_DIR/bin/python" -m pip install -q --upgrade pip -i "$PIP_MIRROR"
        # CUDA torch 只能从 pytorch-wheels 镜像拿（PyPI 的轮子在部分镜像是 CPU-only）
        "$VENV_DIR/bin/python" -m pip install -q torch==2.5.0 \
            --index-url "$TORCH_MIRROR" --extra-index-url "$PIP_MIRROR"
        install_train_deps "$VENV_DIR/bin/python"
        if [ "$USE_QLORA" = "1" ]; then
            "$VENV_DIR/bin/python" -m pip install -q "bitsandbytes>=0.43.0" -i "$PIP_MIRROR"
        fi
    fi
    PYTHON_CMD="$VENV_DIR/bin/python"
    probe_python "$PYTHON_CMD" && probe_deps "$PYTHON_CMD" || {
        echo "[FATAL] venv25 重建后探针仍失败。买卡前须确认 GPU 架构与 torch cubin 匹配。"
        exit 1
    }
fi
export PYTHON_CMD

# ---- Stage 1: 语料与账本硬闸 ----------------------------------------------
echo "[Stage 1/7] 语料指纹与账本核验 ..."
if [ ! -f "$DATA_FILE" ]; then
    echo "[FATAL] 未找到修复语料: $DATA_FILE"
    exit 1
fi
LEDGER_FILE="${DATA_FILE%.jsonl}_ledger.json"
if [ ! -f "$LEDGER_FILE" ]; then
    echo "[FATAL] 缺少溯源账本 $LEDGER_FILE —— 无账本语料不得开训。"
    exit 1
fi
"$PYTHON_CMD" - "$DATA_FILE" "$LEDGER_FILE" <<'PY'
import hashlib, json, os, sys
data, ledger = sys.argv[1], sys.argv[2]
h = hashlib.sha256(open(data, "rb").read()).hexdigest()
led = json.load(open(ledger, encoding="utf-8"))
if led.get("output_sha256") != h:
    sys.exit(f"[FATAL] 语料 sha256 与账本不一致: ledger={led.get('output_sha256')} actual={h}")
if not led.get("repairloop_kept_rows"):
    sys.exit("[FATAL] 账本显示 repairloop 深根因语料 0 行入集，拒绝开训。")
# 深根因语料源头指纹复核（包内自带源文件，防「账本说有、实际没有」）
rl_rel = led.get("repairloop_path", "")
rl_local = os.path.join("dataset", os.path.basename(rl_rel)) if rl_rel else ""
if rl_local and os.path.exists(rl_local):
    rl_sha = hashlib.sha256(open(rl_local, "rb").read()).hexdigest()
    if led.get("repairloop_sha256") and rl_sha != led["repairloop_sha256"]:
        sys.exit(f"[FATAL] repairloop 源语料指纹与账本不一致: {rl_sha[:16]}...")
    print(f"[Ledger] repairloop 源指纹核验通过 sha={rl_sha[:16]}...")
else:
    sys.exit(f"[FATAL] 包内缺少 repairloop 源语料 {rl_local}，无法溯源，拒绝开训。")
# 世界模型专用 repairloop（算式不执行/字段不回填）源头指纹复核
if not led.get("wm_repairloop_kept_rows"):
    sys.exit("[FATAL] 账本显示世界模型 repairloop 0 行入集，拒绝开训。")
wm_rel = led.get("wm_repairloop_path", "")
wm_local = os.path.join("dataset", os.path.basename(wm_rel)) if wm_rel else ""
if not (wm_local and os.path.exists(wm_local)):
    sys.exit(f"[FATAL] 包内缺少世界模型 repairloop 源语料 {wm_local}，无法溯源，拒绝开训。")
wm_sha = hashlib.sha256(open(wm_local, "rb").read()).hexdigest()
if led.get("wm_repairloop_sha256") and wm_sha != led["wm_repairloop_sha256"]:
    sys.exit(f"[FATAL] 世界模型 repairloop 指纹不一致: {wm_sha[:16]}...")
print(f"[Ledger] wm repairloop 源指纹核验通过 sha={wm_sha[:16]}... rows={led.get('wm_repairloop_kept_rows')}")
print(f"[Ledger] OK rows={led.get('kept_rows')} repairloop={led.get('repairloop_kept_rows')} wm_repairloop={led.get('wm_repairloop_kept_rows')} sha={h[:16]}...")
PY

# ---- Stage 2: 契约/求解器自检 + 训练器四重门禁 -----------------------------
echo "[Stage 2/7] 契约与求解器自检 + 训练器门禁 selftest ..."
"$PYTHON_CMD" - <<'PY'
import sys
sys.path.insert(0, '.')
sys.path.insert(0, './scripts')
import wm_contract as C
import wm_verifier as V
# 定律复算钉：FOS=235/198=1.187<1.5 必须判 fail
s = V.recompute({'task': 'fea_fos', 'Sy': 235.0, 'sigma': 198.0})
assert s['fos_gate'] == 'fail', f'expected fail, got {s}'
# 契约键名全覆盖 + 闸门归一（与 build_wm_modelfile --check 同口径）
sysm = C.build_router_system(True)
sysw = C.build_system(True)
miss = [f'{fam}:{k}' for fam in C.KEY_SCHEMA for k in C.schema_keys(fam)
        if k not in sysm or k not in sysw]
assert not miss, f'键名缺失: {miss}'
assert C.normalize_gate('fos_gate', 'FOS>=1.5_pass') == 'pass'
# 验证器内建自检（含反证：坏草案必须被纠正、缺参/除零必须 fail-closed）
rc = V.selftest()
if rc != 0:
    sys.exit('[FATAL] wm_verifier selftest 未通过')
print('[Contract-Gate] wm_contract & wm_verifier 自检通过')
PY
"$PYTHON_CMD" train_turnkey_worldmodel.py \
    --data "$DATA_FILE" \
    --out "$OUT_DIR" \
    --max-length "$MAX_LEN" \
    --selftest

# ---- Stage 3: 基座身份闸（拒绝 Instruct 错基座） ---------------------------
echo "[Stage 3/7] 基座身份核验 ..."
BASE_ARGS=()
if [ -n "$BASE_DIR" ]; then
    BASE_ARGS=(--base "$BASE_DIR")
fi
"$PYTHON_CMD" - "$BASE_DIR" <<'PY'
import glob, json, os, sys
cands = []
if sys.argv[1]:
    cands.append(sys.argv[1])
cands += [
    "/root/public-storage/model/Qwen/Qwen3-8B",
    "/root/virtu_train/models/Qwen3-8B",
    "/root/workspace/models/Qwen3-8B",
    "/root/models/Qwen3-8B",
    "/root/autodl-tmp/models/Qwen3-8B",
    "/root/damodel-tmp/models/Qwen3-8B",
    "./models/Qwen3-8B",
]
for p in cands:
    cfg = os.path.join(p, "config.json")
    if os.path.exists(cfg):
        name = json.load(open(cfg, encoding="utf-8")).get("_name_or_path", "")
        if "Instruct" in p or "Instruct" in name:
            sys.exit(f"[FATAL] 基座 {p} 是 Instruct 变体；本尊基座必须是 Qwen3-8B。")
        print(f"[Base-Gate] OK {p}")
        break
else:
    print("[Base-Gate] 本地无基座，训练器将经 ModelScope 下载 Qwen/Qwen3-8B（非 Instruct）。")
PY

# ---- Stage 4: 20 步冒烟（不过不开正式训练） --------------------------------
echo "[Stage 4/7] 20 步冒烟训练 ..."
SMOKE_OUT="${OUT_DIR}_smoke"
SMOKE_ARGS=()
if [ "$USE_QLORA" = "1" ]; then SMOKE_ARGS+=(--qlora); fi
"$PYTHON_CMD" train_turnkey_worldmodel.py \
    --data "$DATA_FILE" \
    --out "$SMOKE_OUT" \
    --epochs 1 --max-steps 20 \
    --batch "$BATCH" --grad-accum "$GRAD_ACCUM" \
    --max-length "$MAX_LEN" --max-hours 0.5 \
    "${BASE_ARGS[@]}" "${SMOKE_ARGS[@]}"
"$PYTHON_CMD" - "$SMOKE_OUT" <<'PY'
import json, math, os, sys
p = os.path.join(sys.argv[1], "final_adapter", "training_receipt.json")
r = json.load(open(p, encoding="utf-8"))
loss = r.get("train_loss")
if r.get("status") != "COMPLETED" or loss is None or not math.isfinite(loss) or loss <= 0:
    sys.exit(f"[FATAL] 冒烟回执异常: {r.get('status')} loss={loss}")
print(f"[Smoke] OK loss={loss:.4f} precision={r.get('precision_mode')}")
PY

# ---- Stage 5: 开训前漂移指纹 -----------------------------------------------
echo "[Stage 5/7] 记录 run_identity（语料/训练器/脚本/GPU 指纹） ..."
"$PYTHON_CMD" - "$DATA_FILE" "$OUT_DIR" <<'PY'
import hashlib, json, os, subprocess, sys, time
def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()
data, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
ident = {
    "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    "data_sha256": sha(data),
    "trainer_sha256": sha("train_turnkey_worldmodel.py"),
    "entry_sha256": sha("run_worldmodel_fix.sh"),
    "nvidia_smi": subprocess.run(
        ["nvidia-smi", "--query-gpu=name,memory.total,compute_cap", "--format=csv,noheader"],
        capture_output=True, text=True).stdout.strip(),
}
with open(os.path.join(out, "run_identity.json"), "w", encoding="utf-8") as f:
    json.dump(ident, f, ensure_ascii=False, indent=2)
print("[Identity] run_identity.json 已落盘")
PY

# ---- Stage 6: 正式训练 ------------------------------------------------------
echo "[Stage 6/7] 正式 LoRA 修复训练 ..."
TRAIN_ARGS=()
if [ "$USE_QLORA" = "1" ]; then TRAIN_ARGS+=(--qlora); fi
"$PYTHON_CMD" -u train_turnkey_worldmodel.py \
    --data "$DATA_FILE" \
    --out "$OUT_DIR" \
    --epochs "$EPOCHS" \
    --lr "$LR" \
    --batch "$BATCH" \
    --grad-accum "$GRAD_ACCUM" \
    --max-length "$MAX_LEN" \
    --max-hours "$MAX_HOURS" \
    "${BASE_ARGS[@]}" "${TRAIN_ARGS[@]}"

# ---- Stage 7: 交付件硬校验 --------------------------------------------------
echo "[Stage 7/7] 交付物与 SHA256 硬校验 ..."
DELIV_TAR="${OUT_DIR}/virtu_wm_lora_deliverable.tar.gz"
RECEIPT_JSON="${OUT_DIR}/final_adapter/training_receipt.json"
if [ ! -f "$DELIV_TAR" ] || [ ! -f "$RECEIPT_JSON" ]; then
    echo "[FATAL] 交付压缩包或训练收据缺失！"
    exit 1
fi
# .sha256 里写的是裸文件名，必须进交付目录再 -c，否则从 SCRIPT_DIR 找不到文件
( cd "$(dirname "$DELIV_TAR")" && sha256sum -c "virtu_wm_lora_deliverable.tar.gz.sha256" )
"$PYTHON_CMD" - "$RECEIPT_JSON" "$DATA_FILE" <<'PY'
import hashlib, json, sys
r = json.load(open(sys.argv[1], encoding="utf-8"))
if r.get("status") != "COMPLETED":
    sys.exit(f"[FATAL] 训练回执非 COMPLETED: {r.get('status')}")
actual = hashlib.sha256(open(sys.argv[2], "rb").read()).hexdigest()
if r.get("dataset_sha256") != actual:
    sys.exit("[FATAL] 回执语料指纹与开训时不一致 —— 训练期间语料被改动，该腿作废。")
print(f"[Receipt] OK status=COMPLETED train_loss={r.get('train_loss')} eval_loss={r.get('eval_loss')}")
PY
echo "======================================================================"
echo "世界工程模型云端修复训练完成（v2 硬门禁全过）"
echo "交付件: ${DELIV_TAR}"
echo "训练收据: ${RECEIPT_JSON}"
echo "======================================================================"