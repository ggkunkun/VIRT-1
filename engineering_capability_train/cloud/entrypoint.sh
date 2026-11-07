#!/usr/bin/env bash
# 容器入口：默认跑完整云端链路（校验 -> SFT 分词自检 -> SFT -> DPO）
set -euo pipefail
export VIRTU_REPO_ROOT="${VIRTU_REPO_ROOT:-/workspace}"
cd "$VIRTU_REPO_ROOT"
exec bash engineering_capability_train/cloud/launch.sh "$@"
