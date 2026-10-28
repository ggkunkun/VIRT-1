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


class VirtuRMSNorm(nn.Module):
    """Root Mean Square Layer Normalization with learnable scale parameter.

    Eliminates mean subtraction overhead while maintaining activation stability.
    """

    def __init__(self, dim: int, eps: float = 1e-6) -> None:
        super().__init__()
        self.eps = eps
        self.weight = nn.Parameter(torch.ones(dim))

    def _norm(self, x: torch.Tensor) -> torch.Tensor:
        return x * torch.rsqrt(x.pow(2).mean(-1, keepdim=True) + self.eps)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        output = self._norm(x.float()).type_as(x)
        return output * self.weight


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

    def _rotate_half(self, x: torch.Tensor) -> torch.Tensor:
        x1 = x[..., : x.shape[-1] // 2]
        x2 = x[..., x.shape[-1] // 2 :]
        return torch.cat((-x2, x1), dim=-1)

    def apply_1d_rope(
        self, q: torch.Tensor, k: torch.Tensor, positions: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Apply 1D standard rotary embeddings for textual tokens."""
        # positions: [B, S] or [S]
        if positions.dim() == 1:
            positions = positions.unsqueeze(0)

        freqs = torch.einsum("bi,j->bij", positions.float(), self.inv_freq_1d)
        emb = torch.cat((freqs, freqs), dim=-1)  # [B, S, D]
        cos = emb.cos().unsqueeze(2)  # [B, S, 1, D]
        sin = emb.sin().unsqueeze(2)

        q_rot = (q * cos) + (self._rotate_half(q) * sin)
        k_rot = (k * cos) + (self._rotate_half(k) * sin)
        return q_rot, k_rot

    def apply_2d_rope(
        self, q: torch.Tensor, k: torch.Tensor, grid_h: int, grid_w: int
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Apply 2D spatial rotary embeddings for visual patch tokens."""
        y_pos = torch.arange(grid_h, device=q.device).repeat_interleave(grid_w)
        x_pos = torch.arange(grid_w, device=q.device).repeat(grid_h)

        freqs_y = torch.einsum("i,j->ij", y_pos.float(), self.inv_freq_2d)
        freqs_x = torch.einsum("i,j->ij", x_pos.float(), self.inv_freq_2d)

        emb_y = torch.cat((freqs_y, freqs_y), dim=-1)
        emb_x = torch.cat((freqs_x, freqs_x), dim=-1)
        emb_2d = torch.cat((emb_y, emb_x), dim=-1)  # [N_patches, D]

        cos = emb_2d.cos().unsqueeze(0).unsqueeze(2)  # [1, N_patches, 1, D]
        sin = emb_2d.sin().unsqueeze(0).unsqueeze(2)

        q_rot = (q * cos) + (self._rotate_half(q) * sin)
        k_rot = (k * cos) + (self._rotate_half(k) * sin)
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

    def forward(
        self,
        hidden_states: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None,
        rope_engine: Optional[UniRoPE] = None,
        is_visual: bool = False,
        grid_hw: Optional[Tuple[int, int]] = None,
    ) -> torch.Tensor:
        batch_size, seq_len, _ = hidden_states.shape

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

        # Apply positional rotations (Uni-RoPE)
        if rope_engine is not None:
            if is_visual and grid_hw is not None:
                q, k = rope_engine.apply_2d_rope(q, k, grid_hw[0], grid_hw[1])
            else:
                pos = torch.arange(seq_len, device=hidden_states.device)
                q, k = rope_engine.apply_1d_rope(q, k, pos)

        # Repeat KV heads for Grouped Query Attention
        if self.num_kv_groups > 1:
            k = k.repeat_interleave(self.num_kv_groups, dim=2)
            v = v.repeat_interleave(self.num_kv_groups, dim=2)

        # Compute Scaled Dot-Product Attention: [B, H, S, D]
        q = q.transpose(1, 2)
        k = k.transpose(1, 2)
        v = v.transpose(1, 2)

        attn_weights = torch.matmul(q, k.transpose(-2, -1)) * self.scale

        if attention_mask is not None:
            attn_weights = attn_weights + attention_mask

        attn_probs = F.softmax(attn_weights, dim=-1, dtype=torch.float32).to(q.dtype)
        output = torch.matmul(attn_probs, v)  # [B, H, S, D]
        output = output.transpose(1, 2).contiguous().view(batch_size, seq_len, -1)

        return self.o_proj(output)


class VirtuSwiGLU(nn.Module):
    """Swish Gated Linear Unit Feed-Forward Network.

    Implements: Down(SiLU(Gate(x)) * Up(x)) with dimension 4096 -> 12288 -> 4096.
    """

    def __init__(self, config: ModelConfig) -> None:
        super().__init__()
        self.gate_proj = nn.Linear(config.hidden_dim, config.intermediate_dim, bias=False)
        self.up_proj = nn.Linear(config.hidden_dim, config.intermediate_dim, bias=False)
        self.down_proj = nn.Linear(config.intermediate_dim, config.hidden_dim, bias=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.down_proj(F.silu(self.gate_proj(x)) * self.up_proj(x))


class VirtuTransformerBlock(nn.Module):
    """Transformer Layer Block with Pre-RMSNorm and Residual Bypass."""

    def __init__(self, config: ModelConfig) -> None:
        super().__init__()
        self.input_layernorm = VirtuRMSNorm(config.hidden_dim, eps=config.rms_norm_eps)
        self.self_attn = VirtuAttention(config)
        self.post_attention_layernorm = VirtuRMSNorm(config.hidden_dim, eps=config.rms_norm_eps)
        self.mlp = VirtuSwiGLU(config)

    def forward(
        self,
        hidden_states: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None,
        rope_engine: Optional[UniRoPE] = None,
        is_visual: bool = False,
        grid_hw: Optional[Tuple[int, int]] = None,
    ) -> torch.Tensor:
        # Pre-Norm Attention
        normed_attn_in = self.input_layernorm(hidden_states)
        attn_out = self.self_attn(
            normed_attn_in,
            attention_mask=attention_mask,
            rope_engine=rope_engine,
            is_visual=is_visual,
            grid_hw=grid_hw,
        )
        hidden_states = hidden_states + attn_out

        # Pre-Norm MLP
        normed_mlp_in = self.post_attention_layernorm(hidden_states)
        mlp_out = self.mlp(normed_mlp_in)
        hidden_states = hidden_states + mlp_out

        return hidden_states


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
        batch_size, channels, h, w = images.shape
        p = self.patch_size
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

        # 48-Layer Transformer Backbone
        self.layers = nn.ModuleList([
            VirtuTransformerBlock(self.config) for _ in range(self.config.num_layers)
        ])
        self.final_norm = VirtuRMSNorm(self.config.hidden_dim, eps=self.config.rms_norm_eps)

        # Decoupled Dual Output Heads
        self.lm_head = LanguageModelHead(self.config)
        self.vision_gen_head = DiscreteLatentHead(self.config)

    def get_num_params(self) -> int:
        """Return total trainable parameter count."""
        return sum(p.numel() for p in self.parameters())

    def create_block_hybrid_mask(
        self, num_vision: int, num_text: int, device: torch.device
    ) -> torch.Tensor:
        """Construct the Block-Hybrid Causal Mask (BHCM) for zero-loss cross-modal flow."""
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

    def forward(
        self,
        input_ids: Optional[torch.Tensor] = None,
        images: Optional[torch.Tensor] = None,
        labels: Optional[torch.Tensor] = None,
        mode: str = "text_gen",  # 'text_gen', 'image_gen', or 'multimodal_eval'
    ) -> Dict[str, Any]:
        """Unified forward pass processing interleaved or separate modalities."""
        device = input_ids.device if input_ids is not None else images.device

        # Process Modalities
        num_vision = 0
        grid_hw = None
        vis_features = None
        if images is not None:
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
        elif txt_features is not None:
            hidden_states = txt_features
            # Standard causal mask for pure text
            causal_mask = torch.triu(
                torch.full((num_text, num_text), float("-inf"), device=device), diagonal=1
            )
            attention_mask = causal_mask.unsqueeze(0).unsqueeze(0)
        else:
            raise ValueError("At least one modality (input_ids or images) must be provided.")

        # Pass through 48 Transformer Layers
        for layer in self.layers:
            hidden_states = layer(
                hidden_states,
                attention_mask=attention_mask,
                rope_engine=self.rope_engine,
                is_visual=(images is not None and input_ids is None),
                grid_hw=grid_hw,
            )

        hidden_states = self.final_norm(hidden_states)

        # Output Head Routing
        outputs: Dict[str, Any] = {"hidden_states": hidden_states}

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

        return outputs
