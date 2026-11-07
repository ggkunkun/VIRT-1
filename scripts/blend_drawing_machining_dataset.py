# -*- coding: utf-8 -*-
"""
blend_drawing_machining_dataset.py — 合成「识图 -> 标注 -> 绘图 -> 建模 -> CAM -> 仿真 -> 加工」全链路微调集
"""

import json
import os

ROOT = r"d:\Virtu模型"
DATA_ROOT = r"e:\数据"

out_path = os.path.join(ROOT, "data", "virtu_drawing_to_machining_chain_train.jsonl")
pilot_path = os.path.join(ROOT, "data", "toolcall_pilot_2000.jsonl")

extra_sources = [
    os.path.join(DATA_ROOT, "11_CNC_DRAWINGS_AND_PROCESS_PLANNING", "drawing_reading_sft.jsonl"),
    os.path.join(DATA_ROOT, "11_CNC_DRAWINGS_AND_PROCESS_PLANNING", "drawing_to_feature_tree_sft.jsonl"),
    os.path.join(DATA_ROOT, "11_CNC_DRAWINGS_AND_PROCESS_PLANNING", "machining_process_planning_sft.jsonl"),
    os.path.join(DATA_ROOT, "04_MULTIMODAL_DRAWING_TO_CAD", "drawing_to_cad_sft.jsonl"),
    os.path.join(DATA_ROOT, "02_SFT_CAD_CAM_CODE", "virtu_cad_cam_code_sft.jsonl"),
    os.path.join(DATA_ROOT, "02_SFT_CAD_CAM_CODE", "virtu_software_samples_sft.jsonl"),
]

records = []

# 1. 优先载入识图、建模与加工的专业 SFT 样本（重复多轮权重注入，强化学习权重）
for src in extra_sources:
    if os.path.exists(src):
        count = 0
        with open(src, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    item = json.loads(line)
                    # 复制 3 遍以强化专业图纸理解权重
                    for _ in range(3):
                        records.append(item)
                    count += 1
        print(f"Loaded {count} expert samples from: {os.path.basename(src)}")

# 2. 载入 2,000 条结构化工具调用样本（骨架与协议）
toolcall_count = 0
if os.path.exists(pilot_path):
    with open(pilot_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
                toolcall_count += 1
print(f"Loaded {toolcall_count} toolcall pilot samples.")

# 3. 统一写入目标训练集
with open(out_path, "w", encoding="utf-8") as f:
    for rec in records:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

print(f"\n[DONE] 生成全链路复合微调集: {out_path}")
print(f"       总样本数: {len(records)} 条 | 文件体积: {os.path.getsize(out_path) / 1024 / 1024:.2f} MB")
