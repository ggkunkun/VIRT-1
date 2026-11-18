#!/usr/bin/env bash
# =============================================================================
# Virtu 根目录快捷开训入口 (支持 --track master-8b|13b|all90|worldmodel|safety 或直传 evolution 参数)
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

for arg in "$@"; do
  case "$arg" in
    --track|--track=*|--tracks|--tracks=*|--bg|--wait-gpu-s|--wait-gpu-s=*)
      exec bash "$ROOT/cloud_train_pack/start_cloud_train_now.sh" "$@"
      ;;
  esac
done

exec bash "$ROOT/cloud_train_pack/launch_cloud_full_train.sh" "$@"
