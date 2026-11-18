#!/usr/bin/env bash
# =============================================================================
# Virtu 云端一次性训练流水线
#   QLoRA 训练 → 合并 → GGUF(Q4_0) → ollama 部署 → 三轮验收 → 打包
#
# 适用：Ubuntu 22.04/24.04 + NVIDIA 驱动；7B 4-bit 训练约需 12GB 显存、40GB 磁盘
# 特点：fail-closed（任一步不达标立即停止并打印日志定位），可重入（已完成步骤跳过）
#
# 用法：
#   bash one_shot_train.sh --base <HF id 或 本地目录> --data <语料 jsonl> [选项]
#
# 必填：
#   --base   底模：Qwen/Qwen2.5-7B-Instruct 或本地 merged 目录
#   --data   SFT 语料（messages 格式）
# 常用：
#   --work <dir>          工作目录，默认 ./virtu_run
#   --tag  <name:tag>     ollama 标签，默认 virtu-six-software:v9-repair
#   --grader <path>       判分器 deploy_trained_adapter.py（给了才做验收）
#   --min-gate N          验收最低通过数，默认=探针总数（即要求全过）
#   --rounds N            验收轮数，默认 3（门禁取最差轮）
#   --resume              从 <work>/lora/_ckpt_latest 续训
#   --skip-gguf           仅训练+合并
#   --skip-verify         不验收
#
# 产物（<work>/）：lora/ merged_hf/ gguf/ VERIFY_REPORT.json preflight.json bundle.tar.gz SHA256SUMS
# =============================================================================
set -Eeuo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

BASE=""; DATA=""; WORK=""; TAG="virtu-six-software:v9-repair"
GRADER=""; ROUNDS=3; MIN_GATE=""; RESUME=0; SKIP_GGUF=0; SKIP_VERIFY=0
MIN_FREE_MB=12000; MIN_DISK_GB=40; DEVICE="cuda"; PY_OVERRIDE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base) BASE="$2"; shift 2;;
    --data) DATA="$2"; shift 2;;
    --work) WORK="$2"; shift 2;;
    --tag) TAG="$2"; shift 2;;
    --grader) GRADER="$2"; shift 2;;
    --rounds) ROUNDS="$2"; shift 2;;
    --min-gate) MIN_GATE="$2"; shift 2;;
    --min-free-mb) MIN_FREE_MB="$2"; shift 2;;
    --min-disk-gb) MIN_DISK_GB="$2"; shift 2;;
    --device) DEVICE="$2"; shift 2;;
    --python) PY_OVERRIDE="$2"; shift 2;;
    --resume) RESUME=1; shift;;
    --skip-gguf) SKIP_GGUF=1; shift;;
    --skip-verify) SKIP_VERIFY=1; shift;;
    -h|--help) sed -n '2,30p' "${BASH_SOURCE[0]}"; exit 0;;
    *) echo "未知参数: $1" >&2; exit 1;;
  esac
done

[[ -n "$BASE" && -n "$DATA" ]] || { echo "必须提供 --base 与 --data（-h 看用法）" >&2; exit 1; }
[[ -f "$DATA" ]] || { echo "语料不存在: $DATA" >&2; exit 1; }

WORK="${WORK:-$PWD/virtu_run}"
mkdir -p "$WORK"/{logs,lora,merged_hf,gguf}
LOG="$WORK/logs"
CUR_STEP="init"
say()  { printf '[%s] %s\n' "$(date '+%H:%M:%S')" "$*"; }
die()  { say "[FATAL] $*"; exit 1; }
on_err() {
  local rc=$?
  say "[FATAL] 步骤「$CUR_STEP」失败（rc=$rc）。最近日志："
  for f in "$LOG"/*.log; do [[ -f "$f" ]] && { echo "--- $f"; tail -12 "$f"; }; done
  exit $rc
}
trap on_err ERR

# ---------------------------------------------------------------- 0 预检
CUR_STEP="环境预检"
say "===== 0/7 环境预检 ====="
command -v nvidia-smi >/dev/null || die "缺少 nvidia-smi（需要 NVIDIA GPU 与驱动）"
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader | tee "$LOG/gpu.txt"
FREE_MB=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1 | tr -d ' ')
(( FREE_MB >= MIN_FREE_MB )) || die "显存不足：free=${FREE_MB}MB，需 ≥${MIN_FREE_MB}MB（可用 --min-free-mb 调整）"
command -v python3 >/dev/null || die "缺少 python3"
python3 -c 'import sys; assert sys.version_info >= (3,9), sys.version' || die "需要 Python ≥3.9"
command -v git >/dev/null || die "缺少 git（GGUF 转换需要）"
command -v cmake >/dev/null || die "缺少 cmake（量化需要：apt-get install -y cmake）"
df -BG "$WORK" | tail -1 | tee "$LOG/disk.txt"
AVAIL_GB=$(df -BG "$WORK" | awk 'NR==2{gsub(/G/,"",$4); print $4}')
(( AVAIL_GB >= MIN_DISK_GB )) || die "磁盘不足：${AVAIL_GB}GB，需 ≥${MIN_DISK_GB}GB（可用 --min-disk-gb 调整）"
say "环境检查通过（free=${FREE_MB}MB, disk=${AVAIL_GB}GB）"

# ---------------------------------------------------------------- 1 环境
CUR_STEP="安装依赖"
say "===== 1/7 Python 环境 ====="
if [[ -n "$PY_OVERRIDE" ]]; then
  PY="$PY_OVERRIDE"
  [[ -x "$PY" ]] || die "指定的解释器不可执行: $PY"
  say "复用已有解释器：$PY"
else
  if [[ ! -x "$WORK/.venv/bin/python" ]]; then
    python3 -m venv "$WORK/.venv" || die "venv 创建失败（apt-get install -y python3-venv）"
  fi
  PY="$WORK/.venv/bin/python"
fi
"$PY" -m pip install -q --upgrade pip
if ! "$PY" -c "import torch, transformers, peft" 2>/dev/null; then
  say "首次安装依赖（约 5-10 分钟）"
  "$PY" -m pip install -q torch --index-url https://download.pytorch.org/whl/cu121
  "$PY" -m pip install -q "transformers>=4.44" "peft>=0.12" "accelerate>=0.33" \
      "bitsandbytes>=0.43" safetensors sentencepiece gguf numpy "requests>=2.31"
fi
"$PY" -c "import torch,transformers,peft;print('[env] torch',torch.__version__,'cuda',torch.cuda.is_available())"
if [[ "$DEVICE" == "cuda" ]]; then
  "$PY" -c "import torch;assert torch.cuda.is_available(),'CUDA 不可用'" || die "torch 看不到 CUDA"
fi

# ---------------------------------------------------------------- 2 语料预检
CUR_STEP="语料预检"
say "===== 2/7 语料预检（fail-closed） ====="
"$PY" "$HERE/preflight_corpus.py" --data "$DATA" --base "$BASE" --max-length 640 \
      --report "$WORK/preflight.json" 2>&1 | tee "$LOG/preflight.log"
say "语料预检通过"

# ---------------------------------------------------------------- 3 训练
CUR_STEP="QLoRA 训练"
say "===== 3/7 QLoRA 训练 ====="
TRAIN_ARGS=(--base "$BASE" --data "$DATA" --out "$WORK/lora" --device "$DEVICE"
            --epochs 1 --max-length 640 --grad-accum 4 --lr 8e-5 --save-every 30)
[[ "$RESUME" == "1" ]] && TRAIN_ARGS+=(--resume) || true
"$PY" "$HERE/train_qlora.py" "${TRAIN_ARGS[@]}" 2>&1 | tee "$LOG/train.log"
[[ -f "$WORK/lora/adapter_model.safetensors" ]] || die "训练结束但没有 adapter_model.safetensors"
"$PY" - "$WORK/lora/training_receipt.json" <<'EOF' || die "训练凭证不合格（未 COMPLETED / dev_loss 非有限）"
import json, sys, math
d = json.load(open(sys.argv[1], encoding="utf-8"))
assert d.get("status") == "COMPLETED", f"status={d.get('status')}"
e = d.get("dev_loss_end")
assert e is not None and math.isfinite(float(e)), f"dev_loss_end={e}"
print(f"[check] receipt OK dev_loss {d['dev_loss_start']:.4f} -> {e:.4f} sha={str(d.get('adapter_sha256'))[:16]}")
EOF

# ---------------------------------------------------------------- 4 合并
CUR_STEP="合并 adapter"
say "===== 4/7 合并 ====="
if [[ -f "$WORK/merged_hf/merge_receipt.json" ]]; then
  say "已存在合并结果，跳过"
else
  NEED_GB=$(( MIN_DISK_GB - 8 ))
  (( AVAIL_GB > NEED_GB )) || die "磁盘不足：${AVAIL_GB}GB，合并需约 ${NEED_GB}GB"
  "$PY" "$HERE/merge_lora.py" --base "$BASE" --lora "$WORK/lora" --out "$WORK/merged_hf" \
        --dtype bf16 2>&1 | tee "$LOG/merge.log"
fi
[[ -f "$WORK/merged_hf/config.json" ]] || die "合并产物缺 config.json"
ls "$WORK"/merged_hf/*.safetensors >/dev/null 2>&1 || die "合并产物没有 safetensors"
"$PY" - "$WORK/merged_hf/merge_receipt.json" <<'EOF' || die "合并凭证不合格"
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
assert d.get("status") == "MERGED", d.get("status")
print(f"[check] merge OK shards={len(d.get('shards') or [])}")
EOF

# ---------------------------------------------------------------- 5 GGUF
if [[ "$SKIP_GGUF" == "0" ]]; then
  CUR_STEP="GGUF 转换"
  say "===== 5/7 GGUF 转换 + 量化 ====="
  GGUF_OUT="$WORK/gguf/virtu.q4_0.gguf"
  if [[ -f "$GGUF_OUT" ]]; then
    say "GGUF 已存在，跳过"
  else
    [[ -d "$WORK/llama.cpp" ]] || git clone --depth 1 https://github.com/ggerganov/llama.cpp "$WORK/llama.cpp"
    "$PY" -m pip install -q -r "$WORK/llama.cpp/requirements/requirements-convert_hf_to_gguf.txt" || true
    "$PY" "$WORK/llama.cpp/convert_hf_to_gguf.py" "$WORK/merged_hf" \
          --outtype f16 --outfile "$WORK/gguf/virtu.f16.gguf" 2>&1 | tee "$LOG/gguf_convert.log"
    if [[ ! -x "$WORK/llama.cpp/build/bin/llama-quantize" ]]; then
      cmake -S "$WORK/llama.cpp" -B "$WORK/llama.cpp/build" -DLLAMA_CURL=OFF -DCMAKE_BUILD_TYPE=Release \
            > "$LOG/cmake.log" 2>&1 || die "cmake 配置失败，见 $LOG/cmake.log"
      cmake --build "$WORK/llama.cpp/build" --target llama-quantize -j"$(nproc)" \
            > "$LOG/cmake_build.log" 2>&1 || die "llama-quantize 构建失败，见 $LOG/cmake_build.log"
    fi
    "$WORK/llama.cpp/build/bin/llama-quantize" "$WORK/gguf/virtu.f16.gguf" "$GGUF_OUT" Q4_0 \
      2>&1 | tee "$LOG/gguf_quant.log"
    rm -f "$WORK/gguf/virtu.f16.gguf"
  fi
  SZ=$(stat -c%s "$GGUF_OUT" 2>/dev/null || echo 0)
  (( SZ > 2000000000 )) || die "GGUF 异常（${SZ} 字节），应 >2GB"

  # -------------------------------------------------------------- 6 部署
  CUR_STEP="ollama 部署"
  say "===== 6/7 ollama 部署 ====="
  command -v ollama >/dev/null || { say "安装 ollama"; curl -fsSL https://ollama.com/install.sh | sh; }
  if ! curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    ( ollama serve >"$LOG/ollama.log" 2>&1 & ) ; sleep 8
  fi
  curl -sf http://127.0.0.1:11434/api/tags >/dev/null || die "ollama 未就绪（见 $LOG/ollama.log）"
  cat > "$WORK/gguf/Modelfile" <<EOF
FROM $GGUF_OUT
PARAMETER temperature 0.3
PARAMETER num_ctx 8192
EOF
  ollama create "$TAG" -f "$WORK/gguf/Modelfile" 2>&1 | tee "$LOG/ollama_create.log"
  ollama list | tee "$LOG/ollama_list.log"
  ollama list | grep -q "${TAG%%:*}" || die "ollama 里没有标签 $TAG"
else
  say "===== 5-6/7 跳过 GGUF/部署 ====="
fi

# ---------------------------------------------------------------- 7 验收
if [[ "$SKIP_VERIFY" == "0" && "$SKIP_GGUF" == "0" ]]; then
  CUR_STEP="验收"
  say "===== 7/7 三轮验收 ====="
  if [[ -n "$GRADER" ]]; then
    [[ -f "$GRADER" ]] || die "判分器不存在: $GRADER"
    mkdir -p "$HERE/vendor" && cp -f "$GRADER" "$HERE/vendor/deploy_trained_adapter.py"
  fi
  [[ -f "$HERE/vendor/deploy_trained_adapter.py" ]] || \
    die "未提供 --grader 且无 vendor 判分器，无法验收（要跳过请加 --skip-verify）"
  "$PY" "$HERE/verify_gate.py" --tag "$TAG" --rounds "$ROUNDS" \
        --report "$WORK/VERIFY_REPORT.json" --semantic 2>&1 | tee "$LOG/verify.log"
  TOTAL=$("$PY" -c "import json;print(json.load(open(r'$WORK/VERIFY_REPORT.json',encoding='utf-8'))['gate']['worst_total'])")
  WORST=$("$PY" -c "import json;print(json.load(open(r'$WORK/VERIFY_REPORT.json',encoding='utf-8'))['gate']['worst_passed'])")
  MIN_GATE="${MIN_GATE:-$TOTAL}"
  say "门禁：最差轮 ${WORST}/${TOTAL}（要求 ≥${MIN_GATE}）"
  (( WORST >= MIN_GATE )) || die "门禁未达标：${WORST}/${TOTAL} < ${MIN_GATE}（模型已部署为 $TAG，但不达标）"
  "$PY" -c "
import json
d = json.load(open(r'$WORK/VERIFY_REPORT.json', encoding='utf-8'))
s = d.get('semantic_gate')
assert s and s.get('all_pass'), f'G71 语义门未全过: {s}'
print('[check] G71 语义门全部通过')
" || die "G71 语义门未通过（令牌门通过但程序不可用）"
else
  say "===== 7/7 跳过验收 ====="
fi

# ---------------------------------------------------------------- 打包
CUR_STEP="打包"
say "===== 打包产物 ====="
( cd "$WORK" && find lora merged_hf gguf -type f \( -name '*.safetensors' -o -name '*.json' \
    -o -name '*.gguf' -o -name 'Modelfile' -o -name '*.jinja' \) -print0 | xargs -0 -r sha256sum > SHA256SUMS )
tar -czf "$WORK/bundle.tar.gz" -C "$WORK" lora merged_hf gguf SHA256SUMS preflight.json 2>/dev/null \
  || tar -czf "$WORK/bundle.tar.gz" -C "$WORK" lora merged_hf gguf
say "完成：$WORK/bundle.tar.gz（$(du -h "$WORK/bundle.tar.gz" | cut -f1)）"
if [[ -f "$WORK/VERIFY_REPORT.json" ]]; then
  "$PY" -c "
import json
d = json.load(open(r'$WORK/VERIFY_REPORT.json', encoding='utf-8'))
print('[GATE]', d['gate']['worst_passed'], '/', d['gate']['worst_total'],
      '| rounds', d['gate']['all_rounds'], '| semantic', d.get('semantic_gate'))"
fi
say "日志：$LOG"
