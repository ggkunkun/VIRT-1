import torch
import transformers
import peft
import accelerate

print("=" * 60)
print("  Damodel Remote GPU & Deep Learning Probe")
print("=" * 60)
print(f"PyTorch version: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")
print(f"Device count: {torch.cuda.device_count()}")
for i in range(torch.cuda.device_count()):
    props = torch.cuda.get_device_properties(i)
    print(f"  GPU [{i}]: {props.name} | Total Memory: {props.total_memory / (1024**3):.2f} GB")

print(f"Transformers: {transformers.__version__}")
print(f"PEFT: {peft.__version__}")
print(f"Accelerate: {accelerate.__version__}")

# Check base model path
import os
base_path = "/root/public-storage/model/Qwen/Qwen3-8B"
if os.path.exists(base_path):
    files = os.listdir(base_path)
    print(f"\nBase model found at {base_path} ({len(files)} files)")
    safetensors = [f for f in files if f.endswith(".safetensors")]
    print(f"Safetensor weights: {safetensors}")
else:
    print(f"\nBase model NOT found at {base_path}")
