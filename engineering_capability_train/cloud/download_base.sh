#!/usr/bin/env bash
# =============================================================================
# download_base.sh — 把 VIRTU_BASE 解析为「可用的基座目录」。
# 设计为被 launch.sh source（同进程，直接 export VIRTU_BASE）。
#
# 解析顺序：
#   1) VIRTU_BASE 已是含 config.json 的目录  -> 直接用（离线集群首选）
#   2) VIRTU_BASE 形如 "org/model"（含 /）    -> 下载 / 命中缓存到 $VIRTU_MODEL_CACHE
#   3) 未设置 VIRTU_BASE                     -> 用 configs/pipeline.json 的 base_model
#                                               （默认 Qwen/Qwen3-8B）下载
#
# 约定：本文件只负责基座获取。依赖（含 huggingface_hub）必须在 source 本文件
#       之前已安装；HF_ENDPOINT 默认指向国内镜像，境外云机可覆盖。
# =============================================================================
set -euo pipefail

: "${VIRTU_MODEL_CACHE:=/models}"
: "${HF_ENDPOINT:=https://hf-mirror.com}"

_resolve_base() {
  local arg="${VIRTU_BASE:-}"
  local hf_id="$1"

  # 1) 本地目录直接可用
  if [ -n "$arg" ] && [ -d "$arg" ] && [ -f "$arg/config.json" ]; then
    echo "[download_base] 使用本地基座目录: $arg"
    export VIRTU_BASE="$arg"
    return 0
  fi

  # 2) VIRTU_BASE 是指定的 HF id
  if [ -n "$arg" ] && echo "$arg" | grep -q '/'; then
    hf_id="$arg"
  fi

  local local_dir="$VIRTU_MODEL_CACHE/$(echo "$hf_id" | tr '/' '_')"

  # 3) 缓存命中
  if [ -f "$local_dir/config.json" ]; then
    echo "[download_base] 缓存命中: $local_dir"
  else
    echo "[download_base] 下载 $hf_id -> $local_dir (HF_ENDPOINT=$HF_ENDPOINT)"
    mkdir -p "$VIRTU_MODEL_CACHE"
    HF_ENDPOINT="$HF_ENDPOINT" "$PY" - <<PY
from huggingface_hub import snapshot_download
import os
p = snapshot_download("$hf_id", local_dir="$local_dir")
print("downloaded:", p)
PY
  fi

  export VIRTU_BASE="$local_dir"
  echo "[download_base] VIRTU_BASE=$VIRTU_BASE"
}

_resolve_base "${VIRTU_BASE:-Qwen/Qwen3-8B}"
