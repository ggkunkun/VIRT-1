#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
from pathlib import Path

ROOT = Path("/root/virtu_evolution_train")
sys.path.insert(0, str(ROOT))

from cloud_train_pack.train_cloud_virtu_evolution import merge_export_and_package

output_dir = str(ROOT / "cloud_train_pack" / "output")
base_model = "/model/ModelScope/Qwen/Qwen3-8B"
adapter_dpo = str(ROOT / "cloud_train_pack" / "output" / "adapter_evolution_dpo")

print("[START] 执行阶段 4 权重合并、GGUF 导出与交付打包...")
tarball = merge_export_and_package(
    base_model_path=base_model,
    adapter_path=adapter_dpo,
    output_dir=output_dir,
    keep_merged=False
)
print("🎉 阶段 4 执行成功！交付成果包:", tarball)
