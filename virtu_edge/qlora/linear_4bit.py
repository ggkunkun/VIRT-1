"""Native 4-bit Quantized Linear Layer with Low-Rank Adaptation (QLoRA)."""

from __future__ import annotations
import math
from typing import Optional, Tuple
import torch
import torch.nn as nn
import torch.nn.functional as F


def quantize_to_int4_blockwise(
    weight: torch.Tensor,
    block_size: int = 64,
) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Quantize full-precision weight to 4-bit representation with block-wise scaling.

    Args:
        weight: Original weight tensor of shape [out_features, in_features].
        block_size: Block size for per-channel/block quantization scaling.

    Returns:
        quantized_int4: Packed 4-bit values represented in int8 tensor.
        scales: Scale factors per block.
        zeros: Zero-point offsets per block.
    """
    orig_shape = weight.shape
    flat_w = weight.reshape(-1)
    num_elements = flat_w.numel()
    padding = (block_size - (num_elements % block_size)) % block_size
    if padding > 0:
        flat_w = F.pad(flat_w, (0, padding))

    blocks = flat_w.reshape(-1, block_size)
    min_val = blocks.min(dim=-1, keepdim=True).values
    max_val = blocks.max(dim=-1, keepdim=True).values

    scales = (max_val - min_val) / 15.0
    scales = torch.clamp(scales, min=1e-8)
    zeros = min_val

    # Quantize to 0..15
    q_blocks = torch.round((blocks - zeros) / scales).clamp(0, 15).to(torch.int8)

    # Pack two 4-bit numbers into one int8
    # Even elements in lower 4 bits, odd elements in upper 4 bits
    even = q_blocks[:, 0::2]
    odd = q_blocks[:, 1::2]
    packed = (odd << 4) | (even & 0x0F)

    return packed, scales, zeros


def dequantize_int4_blockwise(
    packed: torch.Tensor,
    scales: torch.Tensor,
    zeros: torch.Tensor,
    orig_shape: torch.Size,
    block_size: int = 64,
) -> torch.Tensor:
    """Dequantize packed 4-bit representation back to float tensor."""
    even = (packed & 0x0F).to(torch.float32)
    odd = ((packed >> 4) & 0x0F).to(torch.float32)

    num_blocks = packed.shape[0]
    unpacked = torch.empty((num_blocks, block_size), dtype=torch.float32, device=packed.device)
    unpacked[:, 0::2] = even
    unpacked[:, 1::2] = odd

    dequant = unpacked * scales + zeros
    flat = dequant.reshape(-1)
    total_orig = orig_shape.numel()
    return flat[:total_orig].reshape(orig_shape)


class Linear4bitLoRA(nn.Module):
    """Memory-efficient 4-bit frozen base weight with high-precision LoRA adapters."""

    def __init__(
        self,
        in_features: int,
        out_features: int,
        r: int = 8,
        lora_alpha: float = 16.0,
        lora_dropout: float = 0.05,
        bias: bool = False,
        block_size: int = 64,
        device: Optional[torch.device] = None,
        dtype: torch.dtype = torch.float32,
    ) -> None:
        super().__init__()
        self.in_features = in_features
        self.out_features = out_features
        self.r = r
        self.lora_alpha = lora_alpha
        self.scaling = lora_alpha / r if r > 0 else 1.0
        self.block_size = block_size
        self.orig_shape = torch.Size([out_features, in_features])

        # Base 4-bit quantized buffers (frozen, not updated by optimizer)
        init_weight = torch.randn(out_features, in_features, device=device, dtype=dtype) * 0.02
        packed, scales, zeros = quantize_to_int4_blockwise(init_weight, block_size=block_size)
        self.register_buffer("packed_weight", packed)
        self.register_buffer("scales", scales)
        self.register_buffer("zeros", zeros)

        if bias:
            self.bias = nn.Parameter(torch.zeros(out_features, device=device, dtype=dtype))
        else:
            self.register_parameter("bias", None)

        # Trainable low-rank adapters (Float32 for numerical stability)
        if r > 0:
            self.lora_A = nn.Parameter(torch.empty((r, in_features), device=device, dtype=dtype))
            self.lora_B = nn.Parameter(torch.zeros((out_features, r), device=device, dtype=dtype))
            nn.init.kaiming_uniform_(self.lora_A, a=math.sqrt(5))
            nn.init.zeros_(self.lora_B)
            self.dropout = nn.Dropout(p=lora_dropout) if lora_dropout > 0.0 else nn.Identity()
        else:
            self.register_parameter("lora_A", None)
            self.register_parameter("lora_B", None)
            self.dropout = nn.Identity()

        self._merged = False

    @classmethod
    def from_linear(
        cls,
        linear: nn.Linear,
        r: int = 8,
        lora_alpha: float = 16.0,
        lora_dropout: float = 0.05,
        block_size: int = 64,
    ) -> Linear4bitLoRA:
        """Instantiate Linear4bitLoRA from an existing PyTorch nn.Linear."""
        instance = cls(
            in_features=linear.in_features,
            out_features=linear.out_features,
            r=r,
            lora_alpha=lora_alpha,
            lora_dropout=lora_dropout,
            bias=linear.bias is not None,
            block_size=block_size,
            device=linear.weight.device,
            dtype=linear.weight.dtype,
        )
        # Quantize original linear weight
        packed, scales, zeros = quantize_to_int4_blockwise(linear.weight.data, block_size=block_size)
        instance.packed_weight.copy_(packed)
        instance.scales.copy_(scales)
        instance.zeros.copy_(zeros)

        if linear.bias is not None:
            instance.bias.data.copy_(linear.bias.data)

        return instance

    def get_dequantized_weight(self) -> torch.Tensor:
        """Dequantize 4-bit weight to full floating point."""
        return dequantize_int4_blockwise(
            self.packed_weight,
            self.scales,
            self.zeros,
            self.orig_shape,
            block_size=self.block_size,
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass combining dequantized base linear and LoRA branch."""
        w_base = self.get_dequantized_weight().to(x.dtype)
        out = F.linear(x, w_base, self.bias)

        if self.r > 0 and not self._merged:
            lora_out = (self.dropout(x) @ self.lora_A.T) @ self.lora_B.T
            out = out + lora_out * self.scaling

        return out

    def merge_weights(self) -> None:
        """Merge LoRA low-rank delta directly into the quantized base representation."""
        if self.r > 0 and not self._merged:
            w_base = self.get_dequantized_weight()
            delta = (self.lora_B @ self.lora_A) * self.scaling
            new_w = w_base + delta.to(w_base.dtype)

            packed, scales, zeros = quantize_to_int4_blockwise(new_w, self.block_size)
            self.packed_weight.copy_(packed)
            self.scales.copy_(scales)
            self.zeros.copy_(zeros)
            self._merged = True
