#!/usr/bin/env bash
# 闭环收尾：复评成功后写 DEPLOYED 旗标 + 删除云端凭据（凭证不留盘）
set -e
cd "D:/Virtu模型"
ART="cloud_artifacts"
FLAG="$ART/DEPLOYED.flag"
PW="scripts/.damodel_pw"

echo "=== 1) 写 DEPLOYED 旗标 ==="
if [ ! -f "$FLAG" ]; then
  {
    echo "deployed after training COMPLETED"
    echo "model: virtu-boundary-sft (Qwen3-8B base + cad_cam_boundary_lora delta-merged, Q4_0 GGUF)"
    echo "gguf: checkpoints/virtu-boundary-sft-q4_0.gguf"
    echo "bridge: VIRTU_VLLM_MODEL=virtu-boundary-sft (alias virtu-cad-cam-10b unchanged)"
    echo "eval run: _eval_sft_boundary"
    echo "completed_at: $(date '+%Y-%m-%d %H:%M:%S')"
  } > "$FLAG"
  echo "已写 $FLAG"
else
  echo "旗标已存在，跳过: $FLAG"
fi

echo
echo "=== 2) 删除云端凭据 ==="
if [ -f "$PW" ]; then
  rm -f "$PW"
  echo "已删除 $PW（凭证不留盘）"
else
  echo "凭据文件不存在（可能已删）: $PW"
fi

echo
echo "=== 3) 收尾状态 ==="
cat "$FLAG"
ls -la "$PW" 2>&1 || echo "确认：凭据已移除"
