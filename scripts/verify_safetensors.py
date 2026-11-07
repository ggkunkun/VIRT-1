import struct
import json
import os

p = r"D:\Virtu模型\checkpoints\ug_teacher_guided_agent_lora\adapter_model.safetensors"
with open(p, "rb") as f:
    header_len = struct.unpack("<Q", f.read(8))[0]
    header = json.loads(f.read(header_len).decode("utf-8"))
    tensors = {k: v for k, v in header.items() if k != "__metadata__"}
    print("Safetensors Header Parsed Successfully!")
    print(f"Total Weight Tensors: {len(tensors)}")
    print("Sample Tensors:")
    for k in list(tensors.keys())[:6]:
        print(f"  - {k} -> shape {tensors[k]['shape']}, dtype {tensors[k]['dtype']}")

cfg_path = r"D:\Virtu模型\checkpoints\ug_teacher_guided_agent_lora\adapter_config.json"
with open(cfg_path, "r", encoding="utf-8") as f:
    cfg = json.load(f)
print(f"LoRA Rank: {cfg.get('r')}, Alpha: {cfg.get('lora_alpha')}")
print(f"Target Modules: {cfg.get('target_modules')}")
