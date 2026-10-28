"""
诊断脚本：列 ckpt 顶层 18 个键的类型 + 大小（不读取内容）
用于判断 state_dict 在哪一层
"""
from __future__ import annotations
import sys
import torch
from pathlib import Path

CKPT = Path(r"D:\智能制造Agent\Virtu\out\wpt2_mfg_main\ckpt.pt")

try:
    state = torch.load(CKPT, map_location="cpu", weights_only=False)
except Exception as e:
    print(f"[FAIL] load: {type(e).__name__}: {e}")
    sys.exit(1)

print(f"top-level type = {type(state).__name__}, len = {len(state) if hasattr(state, '__len__') else 'N/A'}")
print()
for i, (k, v) in enumerate(state.items()):
    if isinstance(v, torch.Tensor):
        info = f"Tensor shape={tuple(v.shape)} dtype={v.dtype} numel={v.numel()}"
    elif isinstance(v, dict):
        info = f"dict len={len(v)}"
    elif isinstance(v, (int, float, str, bool)):
        info = f"{type(v).__name__}={v!r}"
    elif isinstance(v, (list, tuple)):
        info = f"{type(v).__name__} len={len(v)}"
    else:
        info = f"{type(v).__module__}.{type(v).__name__}"
    print(f"  [{i:2d}] {k!r:40s}  {info}")
