import os
import shutil
import hashlib

src_dir = r"D:\Virtu模型\checkpoints\damodel_l40s_cad_cam_lora"
dst_dir = r"D:\Virtu模型\checkpoints\cad_cam_six_software_lora"

os.makedirs(dst_dir, exist_ok=True)

print(f"Copying model from {src_dir} to {dst_dir} ...")

for item in os.listdir(src_dir):
    s = os.path.join(src_dir, item)
    d = os.path.join(dst_dir, item)
    if os.path.isfile(s):
        shutil.copy2(s, d)
        size = os.path.getsize(d)
        print(f"  [COPIED] {item} ({size:,} bytes)")
    elif os.path.isdir(s):
        if os.path.exists(d):
            shutil.rmtree(d)
        shutil.copytree(s, d)
        print(f"  [COPIED DIR] {item}")

print("\n=== VERIFYING DESTINATION CONTENTS ===")
for item in sorted(os.listdir(dst_dir)):
    p = os.path.join(dst_dir, item)
    if os.path.isfile(p):
        print(f"  - {item:30s} {os.path.getsize(p):>12,} bytes")

print("\n[SUCCESS] Model copied back to original folder successfully!")
