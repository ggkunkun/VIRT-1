"""Prepare and merge Master SFT training dataset for Damodel 2xL40S fine-tuning."""

import json
import os

DATA_DIR = r"D:\Virtu模型\damodel_cad_cam_tuning\dataset"
OUTPUT_FILE = os.path.join(DATA_DIR, "master_cad_cam_six_software_train.jsonl")

files = [
    os.path.join(DATA_DIR, "comprehensive_wish_cad_cam_sft_1200.jsonl"),
    os.path.join(DATA_DIR, "toolcall_automation_feature_tree_sft.jsonl"),
    os.path.join(DATA_DIR, "six_software_parametric_sft.jsonl"),
]

all_samples = []
seen_hashes = set()

import hashlib

for fp in files:
    if not os.path.exists(fp):
        print(f"[WARN] File not found: {fp}")
        continue
    count = 0
    with open(fp, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            # Create a SHA256 of the content for exact deduplication
            line_hash = hashlib.sha256(line.encode("utf-8")).hexdigest()
            if line_hash in seen_hashes:
                continue
            seen_hashes.add(line_hash)
            all_samples.append(item)
            count += 1
    print(f"Loaded {count} new samples from {os.path.basename(fp)}")

print(f"\nTotal merged samples: {len(all_samples)}")

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    for s in all_samples:
        f.write(json.dumps(s, ensure_ascii=False) + "\n")

print(f"Saved master training dataset to: {OUTPUT_FILE} ({os.path.getsize(OUTPUT_FILE):,} bytes)")
