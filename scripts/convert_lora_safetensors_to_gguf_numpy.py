#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/convert_lora_safetensors_to_gguf_numpy.py

Pure NumPy, zero-torch/zero-peft converter that translates a HuggingFace PEFT
LoRA adapter (safetensors) into a GGUF v3 adapter file compatible with
llama.cpp and Ollama (`ADAPTER <path_to_gguf>`).

Features:
- Handles Qwen2 / Qwen2.5 / Qwen3 layer name mapping.
- Reverses tensor dimensions according to GGML convention (ne0 = fastest changing).
- Converts weights to FP16 (or keeps FP32) without external dependencies.
- Embeds required GGUF adapter metadata (general.architecture, general.type,
  adapter.type, adapter.lora.alpha).
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import struct
import sys
from pathlib import Path

import numpy as np

# GGUF constants
GGUF_MAGIC = b"GGUF"
GGUF_VERSION = 3
GGUF_DEFAULT_ALIGNMENT = 32

# Value types
VT_UINT8, VT_INT8, VT_UINT16, VT_INT16 = 0, 1, 2, 3
VT_UINT32, VT_INT32, VT_FLOAT32, VT_BOOL = 4, 5, 6, 7
VT_STRING, VT_ARRAY, VT_UINT64, VT_INT64, VT_FLOAT64 = 8, 9, 10, 11, 12

# GGML tensor types
TT_F32 = 0
TT_F16 = 1

MODULE_MAP = {
    "q_proj": "attn_q.weight",
    "k_proj": "attn_k.weight",
    "v_proj": "attn_v.weight",
    "o_proj": "attn_output.weight",
    "gate_proj": "ffn_gate.weight",
    "up_proj": "ffn_up.weight",
    "down_proj": "ffn_down.weight",
}


def kv_str(key: str, val: str) -> bytes:
    kb = key.encode("utf-8")
    vb = val.encode("utf-8")
    return struct.pack("<Q", len(kb)) + kb + struct.pack("<I", VT_STRING) + struct.pack("<Q", len(vb)) + vb


def kv_f32(key: str, val: float) -> bytes:
    kb = key.encode("utf-8")
    return struct.pack("<Q", len(kb)) + kb + struct.pack("<I", VT_FLOAT32) + struct.pack("<f", float(val))


def parse_safetensors_header(fpath: Path) -> tuple[dict, int]:
    with open(fpath, "rb") as f:
        hlen = struct.unpack("<Q", f.read(8))[0]
        hdr = json.loads(f.read(hlen).decode("utf-8"))
    return hdr, 8 + hlen


def map_hf_to_gguf_name(hf_name: str) -> str | None:
    # Pattern: base_model.model.model.layers.{idx}.{self_attn|mlp}.{module}.lora_{A|B}.weight
    m = re.match(r"(?:base_model\.model\.)?model\.layers\.(\d+)\.(?:self_attn|mlp)\.([a-z_]+)\.lora_([AB])\.weight", hf_name)
    if not m:
        # Fallback pattern without model.layers
        m = re.search(r"layers\.(\d+)\.(?:self_attn|mlp)\.([a-z_]+)\.lora_([AB])\.weight", hf_name)
    if m:
        layer_idx = int(m.group(1))
        module = m.group(2)
        ab = m.group(3).lower()  # 'a' or 'b'
        if module in MODULE_MAP:
            return f"blk.{layer_idx}.{MODULE_MAP[module]}.lora_{ab}"
    return None


def convert_lora(lora_dir: Path, out_gguf: Path, out_type: str = "f16") -> Path:
    safetensors_path = lora_dir / "adapter_model.safetensors"
    config_path = lora_dir / "adapter_config.json"

    if not safetensors_path.exists():
        raise FileNotFoundError(f"Safetensors file not found: {safetensors_path}")
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    alpha = float(cfg.get("lora_alpha", 64.0))
    base_model = cfg.get("base_model_name_or_path", "")
    arch = "qwen2"
    if "qwen3" in base_model.lower():
        arch = "qwen3"

    hdr, data_offset = parse_safetensors_header(safetensors_path)

    # 1. Build Metadata
    meta_parts = [
        kv_str("general.architecture", arch),
        kv_str("general.type", "adapter"),
        kv_str("adapter.type", "lora"),
        kv_f32("adapter.lora.alpha", alpha),
    ]
    meta_bytes = b"".join(meta_parts)
    meta_count = len(meta_parts)

    # 2. Gather Tensor Infos
    tensor_infos = []  # (gguf_name, gguf_dims, ggml_type, raw_bytes, nbytes)
    f_in = open(safetensors_path, "rb")

    try:
        # Sort keys to ensure deterministic ordering (layer 0 to N)
        sorted_keys = sorted([k for k in hdr.keys() if k != "__metadata__"])
        for hf_key in sorted_keys:
            gg_name = map_hf_to_gguf_name(hf_key)
            if not gg_name:
                print(f"[WARN] Skipping unmapped key: {hf_key}")
                continue

            entry = hdr[hf_key]
            shape = entry["shape"]
            beg, end = entry["data_offsets"]
            dtype = entry["dtype"]

            f_in.seek(data_offset + beg)
            raw_data = f_in.read(end - beg)

            if dtype == "F32":
                arr = np.frombuffer(raw_data, dtype=np.float32)
            elif dtype == "BF16":
                # BF16 -> F32
                u16 = np.frombuffer(raw_data, dtype=np.uint16)
                u32 = u16.astype(np.uint32) << 16
                arr = u32.view(np.float32)
            elif dtype == "F16":
                arr = np.frombuffer(raw_data, dtype=np.float16).astype(np.float32)
            else:
                raise ValueError(f"Unsupported dtype: {dtype} for {hf_key}")

            if out_type == "f16":
                out_arr = arr.astype(np.float16)
                gtype = TT_F16
            else:
                out_arr = arr.astype(np.float32)
                gtype = TT_F32

            out_bytes = out_arr.tobytes()
            # GGML dims convention: reverse the HF shape
            dims = tuple(reversed(shape))
            tensor_infos.append((gg_name, dims, gtype, out_bytes))

    finally:
        f_in.close()

    print(f"Mapped {len(tensor_infos)} LoRA tensors from {safetensors_path.name}")

    # 3. Write GGUF File
    out_gguf.parent.mkdir(parents=True, exist_ok=True)
    with open(out_gguf, "wb") as f_out:
        # GGUF Header
        f_out.write(GGUF_MAGIC)
        f_out.write(struct.pack("<I", GGUF_VERSION))
        f_out.write(struct.pack("<Q", len(tensor_infos)))  # tensor_count
        f_out.write(struct.pack("<Q", meta_count))          # metadata_kv_count

        # Metadata
        f_out.write(meta_bytes)

        # First pass to compute tensor data offset
        # Pre-calculate tensor info section size
        info_bytes = io.BytesIO()
        offset = 0
        offsets = []
        for name, dims, gtype, tbytes in tensor_infos:
            nb = name.encode("utf-8")
            info_bytes.write(struct.pack("<Q", len(nb)) + nb)
            info_bytes.write(struct.pack("<I", len(dims)))
            for d in dims:
                info_bytes.write(struct.pack("<Q", d))
            info_bytes.write(struct.pack("<I", gtype))
            info_bytes.write(struct.pack("<Q", offset))
            offsets.append(offset)
            # Align next offset to GGUF_DEFAULT_ALIGNMENT
            pad = (GGUF_DEFAULT_ALIGNMENT - (len(tbytes) % GGUF_DEFAULT_ALIGNMENT)) % GGUF_DEFAULT_ALIGNMENT
            offset += len(tbytes) + pad

        # Write tensor info section
        f_out.write(info_bytes.getvalue())

        # Align to GGUF_DEFAULT_ALIGNMENT before data starts
        pos = f_out.tell()
        align_pad = (GGUF_DEFAULT_ALIGNMENT - (pos % GGUF_DEFAULT_ALIGNMENT)) % GGUF_DEFAULT_ALIGNMENT
        if align_pad:
            f_out.write(b"\x00" * align_pad)

        # Write tensor data
        for (_, _, _, tbytes), off in zip(tensor_infos, offsets):
            f_out.write(tbytes)
            pad = (GGUF_DEFAULT_ALIGNMENT - (len(tbytes) % GGUF_DEFAULT_ALIGNMENT)) % GGUF_DEFAULT_ALIGNMENT
            if pad:
                f_out.write(b"\x00" * pad)

    file_size_mb = out_gguf.stat().st_size / (1024 * 1024)
    print(f"Successfully generated GGUF LoRA adapter: {out_gguf} ({file_size_mb:.2f} MB)")
    return out_gguf


def main():
    p = argparse.ArgumentParser(description="Convert HF safetensors LoRA to GGUF adapter")
    p.add_argument("--lora", default="checkpoints/virtu_lora_adapter", help="Directory with adapter_model.safetensors")
    p.add_argument("--out", default="checkpoints/virtu_lora_adapter.gguf", help="Output GGUF file path")
    p.add_argument("--type", choices=["f16", "f32"], default="f16", help="Output data type")
    args = p.parse_args()

    import io
    convert_lora(Path(args.lora), Path(args.out), out_type=args.type)


if __name__ == "__main__":
    main()
