# -*- coding: utf-8 -*-
import os
import sys
import json

sys.stdout.reconfigure(encoding='utf-8')

root_dir = r"e:\新建文件夹 (3)"
print("==================================================================")
print("VALIDATING ALL DATASET FILES IN e:\\新建文件夹 (3)")
print("==================================================================")

total_files = 0
total_json_files = 0
total_jsonl_files = 0
errors = []

for root, dirs, files in os.walk(root_dir):
    for f in files:
        fp = os.path.join(root, f)
        total_files += 1
        rel = os.path.relpath(fp, root_dir)
        sz = os.path.getsize(fp)
        
        if f.endswith('.json'):
            total_json_files += 1
            try:
                with open(fp, 'r', encoding='utf-8') as jf:
                    data = json.load(jf)
                print(f"[OK] JSON  : {rel} ({sz/1024:.1f} KB)")
            except Exception as e:
                errors.append(f"JSON Error in {rel}: {e}")
                print(f"[FAIL] JSON: {rel} -> {e}")
                
        elif f.endswith('.jsonl'):
            total_jsonl_files += 1
            line_count = 0
            has_messages = 0
            try:
                with open(fp, 'r', encoding='utf-8') as jlf:
                    for line_idx, line in enumerate(jlf):
                        line_str = line.strip()
                        if not line_str: continue
                        obj = json.loads(line_str)
                        line_count += 1
                        if "messages" in obj:
                            has_messages += 1
                print(f"[OK] JSONL : {rel} ({line_count} records, {has_messages} SFT conversations, {sz/1024:.1f} KB)")
            except Exception as e:
                errors.append(f"JSONL Error in {rel} at line {line_count}: {e}")
                print(f"[FAIL] JSONL: {rel} -> {e}")

print("==================================================================")
print(f"Validation Finished: {total_files} total files ({total_json_files} JSON, {total_jsonl_files} JSONL)")
if errors:
    print(f"ERRORS DETECTED: {len(errors)}")
    for err in errors:
        print("  -", err)
else:
    print("ALL FILES PASSED VALIDATION! 100% HEALTHY & READY FOR TRAINING.")
print("==================================================================")
