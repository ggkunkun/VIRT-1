"""Virtu-Omni-10B: Proprietary Unified Omnimodal Transformer Architecture.

This module implements a fully self-developed, end-to-end multimodal foundation
architecture. It eliminates external framework wrappers, directly constructing:
- Unified continuous-discrete representation manifold for text and vision.
- 2D-1D Unified Continuous Rotary Position Embeddings (Uni-RoPE).
- Block-Hybrid Dynamic Causal Mask (BHCM / DMIM).
- Grouped-Query Attention with QK-RMSNorm stabilization.
- SwiGLU Feed-Forward Networks.
- Dual decoupled heads for text generation and visual flow-matching / generation.
"""

from __future__ import annotations
import math
from typing import Optional, Tuple, Dict, Any
import torch
import torch.nn as nn
import torch.nn.functional as F

from virtu_omni.config import ModelConfig
from virtu_omni.errors import (
    ModelError,
    INFER_NO_MODALITY,
    INFER_INVALID_MODE,
    INFER_MODE_MODALITY_MISMATCH,
    INFER_LABEL_SHAPE,
    INFER_ROPE_GRID_MISMATCH,
    INFER_VISION_SHAPE,
    INFER_MASK_ARGUMENT,
)
from virtu_omni.models.loop import (
    LoopRMSNorm,
    LoopStateGate,
    LoopStepController,
    LoopConvergenceCriterion,
    LoopStateCache,
)


class VirtuRMSNorm(nn.Module):
    """Root Mean Square Layer Normalization with learnable scale parameter.

    Eliminates mean subtraction overhead while maintaining activation stability.
    """

    def __init__(self, dim: int, eps: float = 1e-6) -> None:
        super().__init__()
        self.eps = eps
        self.weight = nn.Parameter(torch.ones(dim))
        # F.rms_norm is a single fused CUDA kernel (PyTorch >= 2.4). The old
        # "optimized" forward was just an inlined copy of _forward_unopt and
        # launched pow -> mean -> rsqrt -> mul -> cast -> mul as 6 kernels.
        self.use_fused_kernel = hasattr(F, "rms_norm")

    def _norm(self, x: torch.Tensor) -> torch.Tensor:
        return x * torch.rsqrt(x.pow(2).mean(-1, keepdim=True) + self.eps)

    def _forward_unopt(self, x: torch.Tensor) -> torch.Tensor:
        """Reference path: explicit FP32 upcast, 6 separate kernel launches."""
        output = self._norm(x.float()).type_as(x)
        return output * self.weight

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if (
            self.use_fused_kernel
            and x.is_cuda
            and self.weight.dtype == x.dtype
            and x.dtype in (torch.float32, torch.float16, torch.bfloat16)
        ):
            return F.rms_norm(x, (x.shape[-1],), self.weight, eps=self.eps)
        # CPU / mismatched dtype: keep the exact legacy accumulation order.
        var = x.float().pow(2).mean(-1, keepdim=True)
        normed = (x.float() * torch.rsqrt(var + self.eps)).type_as(x)
        return normed * self.weight


class UniRoPE(nn.Module):
    """2D-1D Unified Continuous Rotary Position Embedding.

    Seamlessly unifies:
    - 1D temporal causal sequence rotation for linguistic tokens.
    - 2D grid spatial rotation (x, y coordinates) for vision patch tokens.
    """

    def __init__(self, dim: int, max_seq_len: int = 8192, base: float = 100000.0) -> None:
        super().__init__()
        self.dim = dim
        self.max_seq_len = max_seq_len
        self.base = base

        # 1D Inverse frequencies for linguistic tokens
        inv_freq_1d = 1.0 / (self.base ** (torch.arange(0, dim, 2).float() / dim))
        self.register_buffer("inv_freq_1d", inv_freq_1d, persistent=False)

        # 2D Inverse frequencies for visual tokens (dim // 2 for X, dim // 2 for Y)
        dim_2d = dim // 2
        inv_freq_2d = 1.0 / (self.base ** (torch.arange(0, dim_2d, 2).float() / dim_2d))
        self.register_buffer("inv_freq_2d", inv_freq_2d, persistent=False)

        # Dynamic trigonometric cache tables (1D text).
        self._cos_cached: Optional[torch.Tensor] = None
        self._sin_cached: Optional[torch.Tensor] = None
        self._cached_seq_len: int = 0
        # 2D vision grid tables (cos/sin per spatial axis).
        self._cos_2d: Optional[Tuple[torch.Tensor, torch.Tensor]] = None
        self._sin_2d: Optional[Tuple[torch.Tensor, torch.Tensor]] = None
        self._grid_cached: Optional[Tuple[int, int, str, torch.dtype]] = None

    def _rotate_half(self, x: torch.Tensor) -> torch.Tensor:
        x1 = x[..., : x.shape[-1] // 2]
        x2 = x[..., x.shape[-1] // 2 :]
        return torch.cat((-x2, x1), dim=-1)

    def _build_cache(self, needed_len: int, device: torch.device, dtype: torch.dtype) -> None:
        """Grow the trig table on demand.

        The previous implementation always forced ``needed_len >= max_seq_len``
        (8192 by default), so even a 64-token forward built an 8192xD table,
        and ``positions.max().item()`` forced a device->host sync every call.
        """
        if (
            self._cos_cached is not None
            and self._cached_seq_len >= needed_len
            and self._cos_cached.device == device
            and self._cos_cached.dtype == dtype
        ):
            return
        # Geometric growth avoids rebuilding on every small length increase.
        target = max(needed_len, 64)
        if (
            self._cos_cached is not None
            and self._cos_cached.device == device
            and self._cos_cached.dtype == dtype
        ):
            target = max(target, int(self._cached_seq_len * 1.5) + 1)
        t = torch.arange(target, device=device, dtype=self.inv_freq_1d.dtype)
        freqs = torch.outer(t, self.inv_freq_1d.to(device))
        emb = torch.cat((freqs, freqs), dim=-1)
        self._cos_cached = emb.cos().to(dtype)
        self._sin_cached = emb.sin().to(dtype)
        self._cached_seq_len = target

    def apply_1d_rope(
        self,
        q: torch.Tensor,
        k: torch.Tensor,
        positions: torch.Tensor,
        max_pos_hint: Optional[int] = None,
        contiguous_slice: Optional[Tuple[int, int]] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Apply 1D rotary embeddings with on-demand trigonometric caching.

        ``max_pos_hint`` lets callers that already know their position range
        (e.g. ``start_pos + seq_len``) skip the synchronising ``.item()`` read.
        ``contiguous_slice`` covers the common ``arange`` case: the trig rows
        become a zero-copy slice view instead of an indexed gather (which was
        measurably slower than recomputation at S<=512).
        """
        if positions.dim() == 1:
            positions = positions.unsqueeze(0)
        positions = positions.to(q.device)

        if max_pos_hint is not None:
            needed_len = int(max_pos_hint)
        else:
            # Legacy callers: one device->host sync, only when no hint supplied.
            needed_len = int(positions.max().item()) + 1
        needed_len = max(needed_len, positions.shape[-1])
        self._build_cache(needed_len, q.device, q.dtype)

        if contiguous_slice is not None:
            lo, hi = contiguous_slice
            cos = self._cos_cached[lo:hi].unsqueeze(0).unsqueeze(2)  # [1, S, 1, D]
            sin = self._sin_cached[lo:hi].unsqueeze(0).unsqueeze(2)
        else:
            cos = self._cos_cached[positions].unsqueeze(2)  # [B, S, 1, D]
            sin = self._sin_cached[positions].unsqueeze(2)

        q_rot = (q * cos) + (self._rotate_half(q) * sin)
        k_rot = (k * cos) + (self._rotate_half(k) * sin)
        return q_rot, k_rot

    def _apply_1d_rope_unopt(
        self, q: torch.Tensor, k: torch.Tensor, positions: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Un-cached reference implementation for baseline benchmarking."""
        if positions.dim() == 1:
            positions = positions.unsqueeze(0)
        pos_float = positions.to(device=self.inv_freq_1d.device, dtype=self.inv_freq_1d.dtype)
        freqs = torch.outer(pos_float.view(-1), self.inv_freq_1d).view(*positions.shape, -1)
        emb = torch.cat((freqs, freqs), dim=-1)
        cos = emb.cos().unsqueeze(2).to(q.dtype)
        sin = emb.sin().unsqueeze(2).to(q.dtype)
        return (q * cos) + (self._rotate_half(q) * sin), (k * cos) + (self._rotate_half(k) * sin)

    def apply_2d_rope(
        self, q: torch.Tensor, k: torch.Tensor, grid_h: int, grid_w: int
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Apply 2D spatial rotary embeddings for visual patch tokens."""
        if grid_h < 1 or grid_w < 1:
            raise ModelError(
                INFER_ROPE_GRID_MISMATCH,
                f"2D RoPE grid must be positive, got grid_h={grid_h}, grid_w={grid_w}",
                hint="Check that the vision projector returned a valid (grid_h, grid_w).",
                context={"grid_h": grid_h, "grid_w": grid_w},
            )
        expected = grid_h * grid_w
        if q.shape[1] != expected:
            # Previously the cosine table silently broadcast-failed (or, worse,
            # rotated the wrong tokens) whenever the patch count disagreed with
            # the declared grid. Fail loudly with the exact mismatch instead.
            raise ModelError(
                INFER_ROPE_GRID_MISMATCH,
                f"Vision token count {q.shape[1]} does not match grid_h*grid_w={expected} "
                f"(grid_h={grid_h}, grid_w={grid_w})",
                hint="Recompute the patch grid from the actual image size before calling 2D RoPE.",
                context={"tokens": q.shape[1], "grid_h": grid_h, "grid_w": grid_w},
            )
        # Cache the spatial trig tables: grids (e.g. 16x16 patches) are reused
        # across every vision forward, but were previously rebuilt with four
        # outer products + four transcendental kernels on every call.
        key = (grid_h, grid_w, str(q.device), q.dtype)
        if self._grid_cached != key or self._cos_2d is None or self._sin_2d is None:
            y_pos = torch.arange(
                grid_h, device=q.device, dtype=self.inv_freq_2d.dtype
            ).repeat_interleave(grid_w)
            x_pos = torch.arange(
                grid_w, device=q.device, dtype=self.inv_freq_2d.dtype
            ).repeat(grid_h)

            inv_2d = self.inv_freq_2d.to(q.device)
            freqs_y = torch.outer(y_pos, inv_2d)
            freqs_x = torch.outer(x_pos, inv_2d)
            emb_y = torch.cat((freqs_y, freqs_y), dim=-1).unsqueeze(0).unsqueeze(2)
            emb_x = torch.cat((freqs_x, freqs_x), dim=-1).unsqueeze(0).unsqueeze(2)
            self._cos_2d = (emb_y.cos().to(q.dtype), emb_x.cos().to(q.dtype))
            self._sin_2d = (emb_y.sin().to(q.dtype), emb_x.sin().to(q.dtype))
            self._grid_cached = key

        cos_y, cos_x = self._cos_2d
        sin_y, sin_x = self._sin_2d
        half = q.shape[-1] // 2

        def _rotate_axis(x: torch.Tensor, cos: torch.Tensor, sin: torch.Tensor) -> torch.Tensor:
            x1 = x[..., : x.shape[-1] // 2]
            x2 = x[..., x.shape[-1] // 2 :]
            return (x * cos) + (torch.cat((-x2, x1), dim=-1) * sin)

        q_rot = torch.cat(
            [
                _rotate_axis(q[..., :half], cos_y, sin_y),
                _rotate_axis(q[..., half:], cos_x, sin_x),
            ],
            dim=-1,
        )
        k_rot = torch.cat(
            [
                _rotate_axis(k[..., :half], cos_y, sin_y),
                _rotate_axis(k[..., half:], cos_x, sin_x),
            ],
            dim=-1,
        )
        return q_rot, k_rot


class VirtuAttention(nn.Module):
    """Grouped-Query Attention with QK-Norm and Modality Masking.

    Features 32 Query heads and 8 Key-Value heads (4:1 compression ratio).
    """

    def __init__(self, config: ModelConfig) -> None:
        super().__init__()
        self.hidden_dim = config.hidden_dim
        self.num_heads = config.num_attention_heads
        self.num_kv_heads = config.num_kv_heads
        self.head_dim = config.head_dim
        self.num_kv_groups = self.num_heads // self.num_kv_heads
        self.scale = 1.0 / math.sqrt(self.head_dim)

        self.q_proj = nn.Linear(self.hidden_dim, self.num_heads * self.head_dim, bias=False)
        self.k_proj = nn.Linear(self.hidden_dim, self.num_kv_heads * self.head_dim, bias=False)
        self.v_proj = nn.Linear(self.hidden_dim, self.num_kv_heads * self.head_dim, bias=False)
        self.o_proj = nn.Linear(self.num_heads * self.head_dim, self.hidden_dim, bias=False)

        if config.use_qk_norm:
            self.q_norm = VirtuRMSNorm(self.head_dim, eps=config.rms_norm_eps)
            self.k_norm = VirtuRMSNorm(self.head_dim, eps=config.rms_norm_eps)
        else:
            self.q_norm = None
            self.k_norm = None

        # Derived-only QKV weight for inference (one GEMM instead of three).
        self.register_buffer("_fused_qkv_weight", torch.empty(0), persistent=False)
        self.fused_qkv = False

    @torch.no_grad()
    def fuse_projections(self) -> None:
        """Concatenate q/k/v weights for a single inference GEMM."""
        qw, kw, vw = self.q_proj.weight, self.k_proj.weight, self.v_proj.weight
        w = torch.empty(
            (qw.shape[0] + kw.shape[0] + vw.shape[0], qw.shape[1]),
            device=qw.device, dtype=qw.dtype,
        )
        o1, o2 = qw.shape[0], qw.shape[0] + kw.shape[0]
        w[:o1].copy_(qw)
        w[o1:o2].copy_(kw)
        w[o2:].copy_(vw)
        self._fused_qkv_weight = w
        self.fused_qkv = True

    def unfuse_projections(self) -> None:
        self.fused_qkv = False
        self._fused_qkv_weight = torch.empty(
            0, device=self.q_proj.weight.device, dtype=self.q_proj.weight.dtype
        )

    def forward(
        self,
        hidden_states: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None,
        rope_engine: Optional[UniRoPE] = None,
        is_visual: bool = False,
        grid_hw: Optional[Tuple[int, int]] = None,
        vision_len: int = 0,
        past_key_value: Optional[Tuple[torch.Tensor, torch.Tensor]] = None,
        use_cache: bool = False,
    ) -> Union[torch.Tensor, Tuple[torch.Tensor, Tuple[torch.Tensor, torch.Tensor]]]:
        batch_size, seq_len, _ = hidden_states.shape

        q_dim = self.num_heads * self.head_dim
        kv_dim = self.num_kv_heads * self.head_dim
        if self.fused_qkv and not self.training:
            q, k, v = F.linear(hidden_states, self._fused_qkv_weight).split(
                (q_dim, kv_dim, kv_dim), dim=-1
            )
        else:
            q = self.q_proj(hidden_states)
            k = self.k_proj(hidden_states)
            v = self.v_proj(hidden_states)

        q = q.view(batch_size, seq_len, self.num_heads, self.head_dim)
        k = k.view(batch_size, seq_len, self.num_kv_heads, self.head_dim)
        v = v.view(batch_size, seq_len, self.num_kv_heads, self.head_dim)

        # Apply QK normalization if enabled
        if self.q_norm is not None and self.k_norm is not None:
            q = self.q_norm(q)
            k = self.k_norm(k)

        # Determine start position offset from past key value
        start_pos = past_key_value[0].shape[1] if past_key_value is not None else 0

        # Apply positional rotations (Uni-RoPE)
        if rope_engine is not None:
            if is_visual and grid_hw is not None:
                q, k = rope_engine.apply_2d_rope(q, k, grid_hw[0], grid_hw[1])
            elif vision_len > 0 and grid_hw is not None:
                if vision_len > seq_len:
                    raise ModelError(
                        INFER_MASK_ARGUMENT,
                        f"vision_len={vision_len} exceeds sequence length {seq_len}",
                        hint="vision_len must equal the number of leading vision patch tokens.",
                        context={"vision_len": vision_len, "seq_len": seq_len},
                    )
                q_vis, k_vis = rope_engine.apply_2d_rope(
                    q[:, :vision_len], k[:, :vision_len], grid_hw[0], grid_hw[1]
                )
                text_pos = torch.arange(
                    seq_len - vision_len, device=hidden_states.device
                ) + vision_len + start_pos
                q_txt, k_txt = rope_engine.apply_1d_rope(
                    q[:, vision_len:],
                    k[:, vision_len:],
                    text_pos,
                    max_pos_hint=start_pos + seq_len,
                    contiguous_slice=(vision_len + start_pos, start_pos + seq_len),
                )
                q = torch.cat([q_vis, q_txt], dim=1)
                k = torch.cat([k_vis, k_txt], dim=1)
            else:
                pos = torch.arange(start_pos, start_pos + seq_len, device=hidden_states.device)
                q, k = rope_engine.apply_1d_rope(
                    q, k, pos,
                    max_pos_hint=start_pos + seq_len,
                    contiguous_slice=(start_pos, start_pos + seq_len),
                )

        # Append to past KV if caching is active
        if past_key_value is not None:
            past_k, past_v = past_key_value
            k = torch.cat([past_k, k], dim=1)
            v = torch.cat([past_v, v], dim=1)

        cached_kv = (k, v) if use_cache else None
        total_seq_len = k.shape[1]

        # [B, H, S, D] for the fused attention kernels.
        q_t = q.transpose(1, 2)
        k_t = k.transpose(1, 2)
        v_t = v.transpose(1, 2)

        sdpa_mask = attention_mask
        if sdpa_mask is not None:
            if sdpa_mask.dim() == 2:
                sdpa_mask = sdpa_mask.unsqueeze(0).unsqueeze(0)
            elif sdpa_mask.dim() == 3:
                sdpa_mask = sdpa_mask.unsqueeze(1)

        def _expand_kv() -> Tuple[torch.Tensor, torch.Tensor]:
            """Materialise replicated KV heads. Only needed for legacy fallbacks."""
            if self.num_kv_groups <= 1:
                return k_t, v_t
            k_exp = (
                k.unsqueeze(3)
                .expand(batch_size, total_seq_len, self.num_kv_heads, self.num_kv_groups, self.head_dim)
                .reshape(batch_size, total_seq_len, self.num_heads, self.head_dim)
                .transpose(1, 2)
            )
            v_exp = (
                v.unsqueeze(3)
                .expand(batch_size, total_seq_len, self.num_kv_heads, self.num_kv_groups, self.head_dim)
                .reshape(batch_size, total_seq_len, self.num_heads, self.head_dim)
                .transpose(1, 2)
            )
            return k_exp, v_exp

        # Measured 2026-11-06 on RTX 4050 / PyTorch 2.6.0+cu124 (S=1024, B=2):
        #   manual quadratic 2.68ms | SDPA + materialised GQA 1.36ms
        #   SDPA(enable_gqa=True) 3.20ms  <- falls back to the MATH backend.
        # This Windows build has no compiled FlashAttention ("Torch was not
        # compiled with flash attention"), so enable_gqa is a measured 2.4x
        # regression here. Keep materialised KV heads + fused SDPA instead.
        k_exp, v_exp = _expand_kv()
        output = None
        if hasattr(F, "scaled_dot_product_attention"):
            try:
                output = F.scaled_dot_product_attention(
                    q_t,
                    k_exp,
                    v_exp,
                    attn_mask=sdpa_mask,
                    dropout_p=0.0,
                    scale=self.scale,
                )
            except Exception:
                output = None
        if output is None:
            # Fallback manual quadratic attention
            attn_weights = torch.matmul(q_t, k_exp.transpose(-2, -1)) * self.scale
            if attention_mask is not None:
                attn_weights = attn_weights + attention_mask
            attn_probs = F.softmax(attn_weights, dim=-1, dtype=torch.float32).to(v_exp.dtype)
            output = torch.matmul(attn_probs, v_exp)

        output = output.transpose(1, 2).contiguous().view(batch_size, seq_len, -1)
        projected = self.o_proj(output)

        if use_cache:
            return projected, cached_kv
        return projected

    def _forward_manual(
        self,
        hidden_states: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None,
        rope_engine: Optional[UniRoPE] = None,
        is_visual: bool = False,
        grid_hw: Optional[Tuple[int, int]] = None,
        vision_len: int = 0,
        past_key_value: Optional[Tuple[torch.Tensor, torch.Tensor]] = None,
        use_cache: bool = False,
    ) -> Union[torch.Tensor, Tuple[torch.Tensor, Tuple[torch.Tensor, torch.Tensor]]]:
        """Force quadratic manual attention for baseline performance comparison."""
        batch_size, seq_len, _ = hidden_states.shape
        q = self.q_proj(hidden_states).view(batch_size, seq_len, self.num_heads, self.head_dim)
        k = self.k_proj(hidden_states).view(batch_size, seq_len, self.num_kv_heads, self.head_dim)
        v = self.v_proj(hidden_states).view(batch_size, seq_len, self.num_kv_heads, self.head_dim)

        if self.q_norm is not None and self.k_norm is not None:
            q = self.q_norm(q)
            k = self.k_norm(k)

        start_pos = past_key_value[0].shape[1] if past_key_value is not None else 0
        if rope_engine is not None:
            pos = torch.arange(start_pos, start_pos + seq_len, device=hidden_states.device)
            q, k = rope_engine.apply_1d_rope(
                q, k, pos,
                max_pos_hint=start_pos + seq_len,
                contiguous_slice=(start_pos, start_pos + seq_len),
            )

        if past_key_value is not None:
            k = torch.cat([past_key_value[0], k], dim=1)
            v = torch.cat([past_key_value[1], v], dim=1)

        total_seq_len = k.shape[1]
        if self.num_kv_groups > 1:
            k_expanded = k.unsqueeze(3).expand(batch_size, total_seq_len, self.num_kv_heads, self.num_kv_groups, self.head_dim).reshape(batch_size, total_seq_len, self.num_heads, self.head_dim)
            v_expanded = v.unsqueeze(3).expand(batch_size, total_seq_len, self.num_kv_heads, self.num_kv_groups, self.head_dim).reshape(batch_size, total_seq_len, self.num_heads, self.head_dim)
        else:
            k_expanded, v_expanded = k, v

        q = q.transpose(1, 2)
        k_expanded = k_expanded.transpose(1, 2)
        v_expanded = v_expanded.transpose(1, 2)

        attn_weights = torch.matmul(q, k_expanded.transpose(-2, -1)) * self.scale
        if attention_mask is not None:
            attn_weights = attn_weights + attention_mask
        attn_probs = F.softmax(attn_weights, dim=-1, dtype=torch.float32).to(v_expanded.dtype)
        output = torch.matmul(attn_probs, v_expanded).transpose(1, 2).contiguous().view(batch_size, seq_len, -1)
        projected = self.o_proj(output)
        if use_cache:
            return projected, (k, v)
        return projected


class VirtuSwiGLU(nn.Module):
    """Swish Gated Linear Unit Feed-Forward Network.

    Implements: Down(SiLU(Gate(x)) * Up(x)) with dimension 4096 -> 12288 -> 4096.
    """

    def __init__(self, config: ModelConfig) -> None:
        super().__init__()
        self.gate_proj = nn.Linear(config.hidden_dim, config.intermediate_dim, bias=False)
        self.up_proj = nn.Linear(config.hidden_dim, config.intermediate_dim, bias=False)
        self.down_proj = nn.Linear(config.intermediate_dim, config.hidden_dim, bias=False)
        # Lazily allocated, derived-only weight (never a Parameter, never in
        # state_dict). Keeps parameter count / gradient contract unchanged.
        self.register_buffer("_fused_gate_up_weight", torch.empty(0), persistent=False)
        self.fused_gate_up = False

    @torch.no_grad()
    def fuse_projections(self) -> None:
        """Concatenate gate/up weights so inference needs one GEMM instead of two.

        Derived weights go stale as soon as training updates gate_proj/up_proj,
        so the fused path is active only in eval mode and must be refreshed by
        calling this method again after any weight update.
        """
        inter = self.gate_proj.out_features
        w = torch.empty(
            (2 * inter, self.gate_proj.in_features),
            device=self.gate_proj.weight.device,
            dtype=self.gate_proj.weight.dtype,
        )
        w[:inter].copy_(self.gate_proj.weight)
        w[inter:].copy_(self.up_proj.weight)
        self._fused_gate_up_weight = w
        self.fused_gate_up = True

    def unfuse_projections(self) -> None:
        self.fused_gate_up = False
        self._fused_gate_up_weight = torch.empty(
            0, device=self.gate_proj.weight.device, dtype=self.gate_proj.weight.dtype
        )

    def _forward_unopt(self, x: torch.Tensor) -> torch.Tensor:
        return self.down_proj(F.silu(self.gate_proj(x)) * self.up_proj(x))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if self.fused_gate_up and not self.training:
            gate, up = F.linear(x, self._fused_gate_up_weight).chunk(2, dim=-1)
            return self.down_proj(F.silu(gate).mul_(up))
        # In-place activation fusion avoids one intermediate allocation.
        return self.down_proj(F.silu(self.gate_proj(x)).mul_(self.up_proj(x)))


class LoopTransformerBlock(nn.Module):
    """Loop Transformer Recurrent Block.

    Replaces standard feedforward Transformer blocks with a recurrent iterative
    unit adhering to Loop Transformer standard specifications:
    - Pre-Norm Grouped-Query Attention (VirtuAttention)
    - Pre-Norm SwiGLU Feed-Forward Network (VirtuSwiGLU)
    - Loop Normalization Layer (LoopRMSNorm)
    - State Gating Unit (LoopStateGate)
    - Dynamic Loop Step Iteration with Convergence Early Exit
    """

    def __init__(self, config: ModelConfig, layer_idx: int = 0) -> None:
        super().__init__()
        self.config = config
        self.layer_idx = layer_idx
        self.input_layernorm = VirtuRMSNorm(config.hidden_dim, eps=config.rms_norm_eps)
        self.self_attn = VirtuAttention(config)
        self.post_attention_layernorm = VirtuRMSNorm(config.hidden_dim, eps=config.rms_norm_eps)
        self.mlp = VirtuSwiGLU(config)
        self.loop_norm = LoopRMSNorm(config.hidden_dim, eps=config.rms_norm_eps)
        self.state_gate = LoopStateGate(config.hidden_dim) if config.loop_gating else None

    def forward(
        self,
        hidden_states: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None,
        rope_engine: Optional[UniRoPE] = None,
        is_visual: bool = False,
        grid_hw: Optional[Tuple[int, int]] = None,
        step_controller: Optional[LoopStepController] = None,
        convergence_criterion: Optional[LoopConvergenceCriterion] = None,
        state_cache: Optional[LoopStateCache] = None,
        loop_steps: Optional[int] = None,
        vision_len: int = 0,
        past_key_value: Optional[Tuple[torch.Tensor, torch.Tensor]] = None,
        use_cache: bool = False,
    ) -> Union[torch.Tensor, Tuple[torch.Tensor, Optional[Tuple[torch.Tensor, torch.Tensor]]]]:
        """Execute recurrent loop iterations over the Transformer block.

        When loop_steps <= 1, executes a single pass mathematically identical
        to the baseline standard Transformer block.
        """
        max_steps = (
            loop_steps
            if loop_steps is not None
            else (step_controller.max_loop_steps if step_controller is not None else self.config.max_loop_steps)
        )

        if max_steps <= 1:
            # Baseline single-pass execution (bitwise identical to original)
            normed_attn_in = self.input_layernorm(hidden_states)
            attn_res = self.self_attn(
                normed_attn_in,
                attention_mask=attention_mask,
                rope_engine=rope_engine,
                is_visual=is_visual,
                grid_hw=grid_hw,
                vision_len=vision_len,
                past_key_value=past_key_value,
                use_cache=use_cache,
            )
            if use_cache:
                attn_out, new_kv = attn_res
            else:
                attn_out, new_kv = attn_res, None
            hidden_states = hidden_states + attn_out

            normed_mlp_in = self.post_attention_layernorm(hidden_states)
            mlp_out = self.mlp(normed_mlp_in)
            hidden_states = hidden_states + mlp_out
            if use_cache:
                return hidden_states, new_kv
            return hidden_states

        # Recurrent iterative loop execution (Loop Transformer core mechanism)
        h_prev = hidden_states
        h_curr = hidden_states
        final_kv = None

        for step_idx in range(max_steps):
            if step_idx == 0:
                step_in = h_prev
            else:
                step_in = self.loop_norm(h_prev)

            # Pre-Norm Attention
            normed_attn = self.input_layernorm(step_in)
            attn_res = self.self_attn(
                normed_attn,
                attention_mask=attention_mask,
                rope_engine=rope_engine,
                is_visual=is_visual,
                grid_hw=grid_hw,
                vision_len=vision_len,
                past_key_value=(past_key_value if step_idx == 0 else None),
                use_cache=use_cache,
            )
            if use_cache:
                attn_out, kv_step = attn_res
                if step_idx == 0:
                    final_kv = kv_step
            else:
                attn_out = attn_res
            h_mid = step_in + attn_out

            # Pre-Norm MLP
            normed_mlp = self.post_attention_layernorm(h_mid)
            mlp_out = self.mlp(normed_mlp)
            h_candidate = h_mid + mlp_out

            # State Gating with previous step state
            if step_idx > 0 and self.state_gate is not None:
                h_curr = self.state_gate(h_candidate, h_prev)
            else:
                h_curr = h_candidate

            # Cache current step state
            if state_cache is not None:
                state_cache.set_state(f"L{self.layer_idx}_S{step_idx}", h_curr)

            # Dynamic Convergence Evaluation
            if step_idx > 0 and convergence_criterion is not None and self.config.adaptive_loop:
                converged, delta = convergence_criterion.evaluate(h_curr, h_prev)
                if step_controller is not None:
                    step_controller.record_step(step_idx, delta, converged, self.layer_idx)
                if converged:
                    h_prev = h_curr
                    break

            h_prev = h_curr

        if use_cache:
            return h_curr, final_kv
        return h_curr


VirtuTransformerBlock = LoopTransformerBlock


class ContinuousVisionProjector(nn.Module):
    """Multi-Scale Continuous Patch Projector.

    Directly maps raw patch pixels (3 x 14 x 14 = 588) into the unified continuous
    4096-dim manifold using a 2-layer SwiGLU structure without quantization loss.
    """

    def __init__(self, config: ModelConfig) -> None:
        super().__init__()
        patch_dim = 3 * config.patch_size * config.patch_size
        self.patch_size = config.patch_size
        self.proj_in = nn.Linear(patch_dim, config.hidden_dim, bias=False)
        self.norm = VirtuRMSNorm(config.hidden_dim, eps=config.rms_norm_eps)
        self.mlp = VirtuSwiGLU(config)

    def extract_patches(self, images: torch.Tensor) -> torch.Tensor:
        """Slice [B, 3, H, W] into flattened patches [B, N_patches, 3*P*P]."""
        if images.dim() != 4:
            raise ModelError(
                INFER_VISION_SHAPE,
                f"images must be 4-D [B, 3, H, W], got shape {tuple(images.shape)}",
                hint="Pass a batched RGB tensor.",
                context={"shape": list(images.shape)},
            )
        batch_size, channels, h, w = images.shape
        p = self.patch_size
        if channels != 3:
            raise ModelError(
                INFER_VISION_SHAPE,
                f"images must have 3 RGB channels, got {channels}",
                hint="Convert the input with PIL 'RGB' before building the tensor.",
                context={"channels": channels},
            )
        if h < p or w < p or h % p != 0 or w % p != 0:
            # unfold() silently drops the trailing strip for non-divisible sizes,
            # which previously desynchronised grid_h/grid_w from the token count
            # and corrupted 2D RoPE positions. Reject it at the boundary.
            raise ModelError(
                INFER_VISION_SHAPE,
                f"image size {h}x{w} must be >= patch_size {p} and divisible by it",
                hint=f"Resize the image to a multiple of {p} (e.g. 448x448).",
                context={"height": h, "width": w, "patch_size": p},
            )
        patches = images.unfold(2, p, p).unfold(3, p, p)
        patches = patches.permute(0, 2, 3, 1, 4, 5).contiguous()
        num_patches = (h // p) * (w // p)
        return patches.view(batch_size, num_patches, channels * p * p)

    def forward(self, images: torch.Tensor) -> Tuple[torch.Tensor, Tuple[int, int]]:
        _, _, h, w = images.shape
        grid_h, grid_w = h // self.patch_size, w // self.patch_size
        patches = self.extract_patches(images)
        hidden = self.proj_in(patches)
        hidden = self.norm(hidden)
        hidden = hidden + self.mlp(hidden)
        return hidden, (grid_h, grid_w)


class DiscreteLatentHead(nn.Module):
    """Unified Flow-Matching / Codebook Generative Head for Visual Synthesis."""

    def __init__(self, config: ModelConfig) -> None:
        super().__init__()
        self.norm = VirtuRMSNorm(config.hidden_dim, eps=config.rms_norm_eps)
        self.head = nn.Linear(config.hidden_dim, config.vision_codebook_size, bias=False)

    def forward(self, hidden_states: torch.Tensor) -> torch.Tensor:
        return self.head(self.norm(hidden_states))


class LanguageModelHead(nn.Module):
    """Autoregressive Language Modeling Head for Text Decoding."""

    def __init__(self, config: ModelConfig) -> None:
        super().__init__()
        self.norm = VirtuRMSNorm(config.hidden_dim, eps=config.rms_norm_eps)
        self.lm_head = nn.Linear(config.hidden_dim, config.vocab_size, bias=False)

    def forward(self, hidden_states: torch.Tensor) -> torch.Tensor:
        return self.lm_head(self.norm(hidden_states))


class VirtuOmni10B(nn.Module):
    """Virtu-Omni-10B: Universal Omnimodal Foundation Model.

    Full proprietary architecture integrating text and vision in a unified
    space, supporting both text generation and image generation.
    """

    def __init__(self, config: Optional[ModelConfig] = None) -> None:
        super().__init__()
        self.config = config or ModelConfig()

        # Positional Encoding Engine
        self.rope_engine = UniRoPE(
            dim=self.config.head_dim,
            max_seq_len=self.config.max_position_embeddings,
            base=self.config.rope_theta,
        )

        # Modality Ingestion
        self.embed_tokens = nn.Embedding(self.config.vocab_size, self.config.hidden_dim)
        self.vision_projector = ContinuousVisionProjector(self.config)

        # Loop Transformer Core Controllers & Cache
        self.step_controller = LoopStepController(self.config)
        self.convergence_criterion = LoopConvergenceCriterion(
            threshold=self.config.convergence_threshold,
            metric=self.config.loop_exit_metric,
        )
        self.state_cache = LoopStateCache(enabled=self.config.enable_state_cache)

        # 48-Layer Loop Transformer Backbone
        self.layers = nn.ModuleList([
            LoopTransformerBlock(self.config, layer_idx=i)
            for i in range(self.config.num_layers)
        ])
        self.final_norm = VirtuRMSNorm(self.config.hidden_dim, eps=self.config.rms_norm_eps)

        # Decoupled Dual Output Heads
        self.lm_head = LanguageModelHead(self.config)
        self.vision_gen_head = DiscreteLatentHead(self.config)

    def set_loop_steps(self, steps: int) -> None:
        """Dynamically configure runtime loop step budget."""
        self.step_controller.set_max_steps(steps)

    def get_loop_stats(self) -> Dict[str, Any]:
        """Retrieve telemetry from the loop controller."""
        return self.step_controller.get_summary()

    def reset_loop_state(self) -> None:
        """Reset state cache and telemetry controller."""
        self.step_controller.reset()
        self.state_cache.clear()

    def get_num_params(self) -> int:
        """Return total trainable parameter count."""
        return sum(p.numel() for p in self.parameters())

    def create_block_hybrid_mask(
        self, num_vision: int, num_text: int, device: torch.device
    ) -> torch.Tensor:
        """Construct the Block-Hybrid Causal Mask (BHCM) for zero-loss cross-modal flow."""
        if num_vision < 0 or num_text < 0:
            raise ModelError(
                INFER_MASK_ARGUMENT,
                f"Mask lengths must be non-negative, got num_vision={num_vision}, num_text={num_text}",
                hint="Pass the actual token counts returned by the modality encoders.",
                context={"num_vision": num_vision, "num_text": num_text},
            )
        total_len = num_vision + num_text
        mask = torch.full((total_len, total_len), float("-inf"), device=device)

        # 1. Vision patches: fully bidirectional within vision
        mask[:num_vision, :num_vision] = 0.0

        # 2. Text tokens: causal autoregressive within text
        causal_text = torch.triu(torch.full((num_text, num_text), float("-inf"), device=device), diagonal=1)
        mask[num_vision:, num_vision:] = causal_text

        # 3. Cross-modal: text tokens attend to all vision patches
        mask[num_vision:, :num_vision] = 0.0

        # 4. Vision tokens do not attend forward to text tokens
        return mask.unsqueeze(0).unsqueeze(0)  # [1, 1, total_len, total_len]

    VALID_MODES = ("text_gen", "image_gen", "multimodal_eval")

    def forward(
        self,
        input_ids: Optional[torch.Tensor] = None,
        images: Optional[torch.Tensor] = None,
        labels: Optional[torch.Tensor] = None,
        mode: str = "text_gen",  # 'text_gen', 'image_gen', or 'multimodal_eval'
        loop_steps: Optional[int] = None,
        past_key_values: Optional[List[Optional[Tuple[torch.Tensor, torch.Tensor]]]] = None,
        use_cache: bool = False,
    ) -> Dict[str, Any]:
        """Unified forward pass processing interleaved or separate modalities with Loop Transformer."""
        # --- Boundary validation -------------------------------------------------
        if input_ids is None and images is None:
            # Previously this raised a bare AttributeError on ``images.device``,
            # which looked like an internal bug rather than a caller error.
            raise ModelError(
                INFER_NO_MODALITY,
                "At least one modality (input_ids or images) must be provided.",
                hint="Pass input_ids for text, images for vision, or both for multimodal.",
            )
        if mode not in self.VALID_MODES:
            # Unknown modes used to fall through and return hidden states without
            # any logits — a silent failure for downstream callers.
            raise ModelError(
                INFER_INVALID_MODE,
                f"Unknown output mode: {mode!r}",
                hint=f"Use one of: {', '.join(self.VALID_MODES)}.",
                context={"mode": mode},
            )
        if mode == "image_gen" and images is None:
            raise ModelError(
                INFER_MODE_MODALITY_MISMATCH,
                "mode='image_gen' requires an images tensor.",
                hint="Provide images or route the request to text_gen.",
                context={"mode": mode},
            )
        if mode != "image_gen" and input_ids is None:
            raise ModelError(
                INFER_MODE_MODALITY_MISMATCH,
                f"mode={mode!r} requires input_ids.",
                hint="Provide token ids or use mode='image_gen' for pure vision.",
                context={"mode": mode},
            )
        if input_ids is not None and input_ids.dim() != 2:
            raise ModelError(
                INFER_MASK_ARGUMENT,
                f"input_ids must be 2-D [B, S], got shape {tuple(input_ids.shape)}",
                hint="Use a batched token tensor.",
                context={"shape": list(input_ids.shape)},
            )
        if input_ids is not None and input_ids.shape[1] < 1:
            raise ModelError(
                INFER_MASK_ARGUMENT,
                "input_ids must contain at least one token.",
                hint="Empty sequences cannot produce next-token logits.",
                context={"shape": list(input_ids.shape)},
            )
        if (
            input_ids is not None
            and images is not None
            and images.shape[0] != input_ids.shape[0]
        ):
            raise ModelError(
                INFER_MASK_ARGUMENT,
                f"Batch mismatch: images batch={images.shape[0]} vs input_ids batch={input_ids.shape[0]}",
                hint="Ensure every text sample has a matching image (or drop the image).",
                context={"image_batch": images.shape[0], "text_batch": input_ids.shape[0]},
            )

        device = input_ids.device if input_ids is not None else images.device

        # Reset loop telemetry and transient cache per forward pass
        self.state_cache.clear()
        self.step_controller.reset()

        try:
            # Process Modalities
            num_vision = 0
            grid_hw = None
            vis_features = None
            if images is not None and past_key_values is None:
                vis_features, grid_hw = self.vision_projector(images)
                num_vision = vis_features.shape[1]

            num_text = 0
            txt_features = None
            if input_ids is not None:
                txt_features = self.embed_tokens(input_ids)
                num_text = txt_features.shape[1]

            # Fusion into Unified Sequence
            if vis_features is not None and txt_features is not None:
                hidden_states = torch.cat([vis_features, txt_features], dim=1)
                attention_mask = self.create_block_hybrid_mask(num_vision, num_text, device)
            elif vis_features is not None:
                hidden_states = vis_features
                attention_mask = None
            else:
                hidden_states = txt_features
                if past_key_values is not None and num_text == 1:
                    attention_mask = None
                else:
                    # Standard causal mask for pure text
                    causal_mask = torch.triu(
                        torch.full((num_text, num_text), float("-inf"), device=device), diagonal=1
                    )
                    attention_mask = causal_mask.unsqueeze(0).unsqueeze(0)

            # Labels must align 1:1 with the text positions that produce logits.
            if labels is not None and mode != "image_gen":
                expected = (input_ids.shape[0], num_text)
                if labels.dim() != 2 or tuple(labels.shape) != expected:
                    raise ModelError(
                        INFER_LABEL_SHAPE,
                        f"labels shape {tuple(labels.shape)} must match text positions {expected}",
                        hint="Supervise text tokens only; vision tokens are not language targets.",
                        context={"labels_shape": list(labels.shape), "expected": list(expected)},
                    )

            # Pass through Loop Transformer Backbone Layers
            new_past_key_values = [] if use_cache else None
            for i, layer in enumerate(self.layers):
                layer_past_kv = (
                    past_key_values[i]
                    if past_key_values is not None and i < len(past_key_values)
                    else None
                )
                layer_res = layer(
                    hidden_states,
                    attention_mask=attention_mask,
                    rope_engine=self.rope_engine,
                    is_visual=(images is not None and input_ids is None),
                    grid_hw=grid_hw,
                    step_controller=self.step_controller,
                    convergence_criterion=self.convergence_criterion,
                    state_cache=self.state_cache,
                    loop_steps=loop_steps,
                    vision_len=(num_vision if txt_features is not None else 0),
                    past_key_value=layer_past_kv,
                    use_cache=use_cache,
                )
                if use_cache:
                    hidden_states, layer_new_kv = layer_res
                    new_past_key_values.append(layer_new_kv)
                else:
                    hidden_states = layer_res

            hidden_states = self.final_norm(hidden_states)

            # Output Head Routing
            outputs: Dict[str, Any] = {
                "hidden_states": hidden_states,
                "loop_stats": self.step_controller.get_summary(),
            }
            if use_cache:
                outputs["past_key_values"] = new_past_key_values

            if mode == "text_gen" or mode == "multimodal_eval":
                # Compute text logits over text token positions
                if num_vision > 0 and num_text > 0:
                    text_hidden = hidden_states[:, num_vision:, :]
                else:
                    text_hidden = hidden_states
                logits = self.lm_head(text_hidden)
                outputs["logits"] = logits

                if labels is not None:
                    # Next token prediction loss with z-loss stabilization
                    shift_logits = logits[..., :-1, :].contiguous()
                    shift_labels = labels[..., 1:].contiguous()
                    loss_ce = F.cross_entropy(
                        shift_logits.view(-1, self.config.vocab_size),
                        shift_labels.view(-1),
                        ignore_index=-100,
                    )
                    # PaLM / Chameleon z-loss: 1e-4 * log^2(sum(exp(logits)))
                    z_loss = 1e-4 * torch.logsumexp(shift_logits, dim=-1).pow(2).mean()
                    outputs["loss"] = loss_ce + z_loss
                    outputs["loss_ce"] = loss_ce.item()
                    outputs["z_loss"] = z_loss.item()

            elif mode == "image_gen":
                # Image generation / reconstruction head
                img_logits = self.vision_gen_head(hidden_states[:, :num_vision, :])
                outputs["image_logits"] = img_logits

        finally:
            self.state_cache.clear_kv()

        return outputs

    @torch.inference_mode()
    def generate(
        self,
        input_ids: torch.Tensor,
        images: Optional[torch.Tensor] = None,
        max_new_tokens: int = 128,
        temperature: float = 0.7,
        top_p: float = 0.9,
        top_k: int = 50,
        repetition_penalty: float = 1.1,
        eos_token_id: Optional[int] = 2,
        pad_token_id: Optional[int] = 0,
        use_cache: bool = True,
        loop_steps: Optional[int] = 1,
    ) -> torch.Tensor:
        """Autoregressive multi-token generation with KV caching and sampling controls."""
        self.eval()
        device = input_ids.device
        batch_size = input_ids.shape[0]

        # Prefill phase
        outputs = self(
            input_ids=input_ids,
            images=images,
            mode="text_gen",
            loop_steps=loop_steps,
            use_cache=use_cache,
        )
        logits = outputs["logits"][:, -1, :]  # [B, vocab_size]
        past_key_values = outputs.get("past_key_values") if use_cache else None

        generated_ids = input_ids.clone()
        unfinished = torch.ones(batch_size, dtype=torch.bool, device=device)

        for step in range(max_new_tokens):
            cur_logits = logits.clone()
            if repetition_penalty != 1.0:
                for b in range(batch_size):
                    for prev_token in set(generated_ids[b].tolist()):
                        if cur_logits[b, prev_token] < 0:
                            cur_logits[b, prev_token] *= repetition_penalty
                        else:
                            cur_logits[b, prev_token] /= repetition_penalty

            if temperature <= 0.0:
                next_tokens = torch.argmax(cur_logits, dim=-1, keepdim=True)
            else:
                scaled_logits = cur_logits / max(temperature, 1e-5)
                if top_k > 0:
                    k_val = min(top_k, scaled_logits.size(-1))
                    topk_vals = torch.topk(scaled_logits, k_val, dim=-1)[0][..., -1, None]
                    scaled_logits = torch.where(scaled_logits < topk_vals, -float("inf"), scaled_logits)
                if 0.0 < top_p < 1.0:
                    sorted_logits, sorted_indices = torch.sort(scaled_logits, descending=True, dim=-1)
                    cumulative_probs = torch.cumsum(F.softmax(sorted_logits, dim=-1), dim=-1)
                    sorted_indices_to_remove = cumulative_probs > top_p
                    sorted_indices_to_remove[..., 1:] = sorted_indices_to_remove[..., :-1].clone()
                    sorted_indices_to_remove[..., 0] = False
                    indices_to_remove = sorted_indices_to_remove.scatter(-1, sorted_indices, sorted_indices_to_remove)
                    scaled_logits = scaled_logits.masked_fill(indices_to_remove, -float("inf"))

                probs = F.softmax(scaled_logits, dim=-1)
                next_tokens = torch.multinomial(probs, num_samples=1)

            if pad_token_id is not None:
                next_tokens = torch.where(unfinished.unsqueeze(-1), next_tokens, pad_token_id)

            generated_ids = torch.cat([generated_ids, next_tokens], dim=-1)

            if eos_token_id is not None:
                is_eos = (next_tokens.squeeze(-1) == eos_token_id)
                unfinished = unfinished & (~is_eos)
                if not unfinished.any():
                    break

            if step == max_new_tokens - 1:
                break

            # Incremental decode step
            if use_cache and past_key_values is not None:
                step_outputs = self(
                    input_ids=next_tokens,
                    mode="text_gen",
                    loop_steps=loop_steps,
                    past_key_values=past_key_values,
                    use_cache=True,
                )
                logits = step_outputs["logits"][:, -1, :]
                past_key_values = step_outputs.get("past_key_values")
            else:
                step_outputs = self(
                    input_ids=generated_ids,
                    images=images,
                    mode="text_gen",
                    loop_steps=loop_steps,
                    use_cache=False,
                )
                logits = step_outputs["logits"][:, -1, :]

        return generated_ids

    @torch.inference_mode()
    def generate_stream(
        self,
        input_ids: torch.Tensor,
        images: Optional[torch.Tensor] = None,
        max_new_tokens: int = 128,
        temperature: float = 0.7,
        top_p: float = 0.9,
        top_k: int = 50,
        repetition_penalty: float = 1.1,
        eos_token_id: Optional[int] = 2,
        use_cache: bool = True,
        loop_steps: Optional[int] = 1,
    ):
        """Streaming generator yielding newly sampled token ids one by one."""
        self.eval()
        outputs = self(
            input_ids=input_ids,
            images=images,
            mode="text_gen",
            loop_steps=loop_steps,
            use_cache=use_cache,
        )
        logits = outputs["logits"][:, -1, :]
        past_key_values = outputs.get("past_key_values") if use_cache else None
        generated_ids = input_ids.clone()

        for step in range(max_new_tokens):
            cur_logits = logits.clone()
            if repetition_penalty != 1.0:
                for prev_token in set(generated_ids[0].tolist()):
                    if cur_logits[0, prev_token] < 0:
                        cur_logits[0, prev_token] *= repetition_penalty
                    else:
                        cur_logits[0, prev_token] /= repetition_penalty

            if temperature <= 0.0:
                next_token = torch.argmax(cur_logits, dim=-1, keepdim=True)
            else:
                scaled_logits = cur_logits / max(temperature, 1e-5)
                if top_k > 0:
                    k_val = min(top_k, scaled_logits.size(-1))
                    topk_vals = torch.topk(scaled_logits, k_val, dim=-1)[0][..., -1, None]
                    scaled_logits = torch.where(scaled_logits < topk_vals, -float("inf"), scaled_logits)
                if 0.0 < top_p < 1.0:
                    sorted_logits, sorted_indices = torch.sort(scaled_logits, descending=True, dim=-1)
                    cumulative_probs = torch.cumsum(F.softmax(sorted_logits, dim=-1), dim=-1)
                    sorted_indices_to_remove = cumulative_probs > top_p
                    sorted_indices_to_remove[..., 1:] = sorted_indices_to_remove[..., :-1].clone()
                    sorted_indices_to_remove[..., 0] = False
                    indices_to_remove = sorted_indices_to_remove.scatter(-1, sorted_indices, sorted_indices_to_remove)
                    scaled_logits = scaled_logits.masked_fill(indices_to_remove, -float("inf"))
                probs = F.softmax(scaled_logits, dim=-1)
                next_token = torch.multinomial(probs, num_samples=1)

            token_val = int(next_token.item())
            yield token_val

            if eos_token_id is not None and token_val == eos_token_id:
                break

            generated_ids = torch.cat([generated_ids, next_token], dim=-1)

            if step == max_new_tokens - 1:
                break

            if use_cache and past_key_values is not None:
                step_outputs = self(
                    input_ids=next_token,
                    mode="text_gen",
                    loop_steps=loop_steps,
                    past_key_values=past_key_values,
                    use_cache=True,
                )
                logits = step_outputs["logits"][:, -1, :]
                past_key_values = step_outputs.get("past_key_values")
            else:
                step_outputs = self(
                    input_ids=generated_ids,
                    images=images,
                    mode="text_gen",
                    loop_steps=loop_steps,
                    use_cache=False,
                )
                logits = step_outputs["logits"][:, -1, :]
