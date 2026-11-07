"""Prototype test for Hierarchical Virtu Attention."""

import os
import sys
import math
from typing import Optional, Tuple, Union, Dict, Any, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import torch
import torch.nn as nn
import torch.nn.functional as F

from virtu_omni.config import ModelConfig
from virtu_omni.models.architecture import VirtuRMSNorm, UniRoPE


class HierarchicalVirtuAttention(nn.Module):
    """Hierarchical Grouped-Query Attention (H-GQA) Mechanism.

    Two-tier attention decomposition:
    Tier 1: Local intra-segment attention (fine-grained token interactions within chunk).
    Tier 2: Global inter-segment summary attention (coarse-grained cross-chunk routing).
    Tier 3: Multi-level hierarchical gating fusion.
    """

    def __init__(self, config: ModelConfig, segment_size: int = 16) -> None:
        super().__init__()
        self.hidden_dim = config.hidden_dim
        self.num_heads = config.num_attention_heads
        self.num_kv_heads = config.num_kv_heads
        self.head_dim = config.head_dim
        self.num_kv_groups = self.num_heads // self.num_kv_heads
        self.scale = 1.0 / math.sqrt(self.head_dim)
        self.segment_size = segment_size

        # Local Projections
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

        # Global Segment-Level Attention
        self.global_q_proj = nn.Linear(self.hidden_dim, self.num_heads * self.head_dim, bias=False)
        self.global_k_proj = nn.Linear(self.hidden_dim, self.num_heads * self.head_dim, bias=False)
        self.global_v_proj = nn.Linear(self.hidden_dim, self.num_heads * self.head_dim, bias=False)
        self.global_out_proj = nn.Linear(self.num_heads * self.head_dim, self.hidden_dim, bias=False)

        # Hierarchical Gating Unit
        self.gate_proj = nn.Linear(self.hidden_dim * 2, self.hidden_dim, bias=True)
        # Initialize gate bias to high negative or near zero to preserve initial gradient flow
        nn.init.zeros_(self.gate_proj.weight)
        nn.init.constant_(self.gate_proj.bias, 0.0)

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

        q = self.q_proj(hidden_states)
        k = self.k_proj(hidden_states)
        v = self.v_proj(hidden_states)

        q = q.view(batch_size, seq_len, self.num_heads, self.head_dim)
        k = k.view(batch_size, seq_len, self.num_kv_heads, self.head_dim)
        v = v.view(batch_size, seq_len, self.num_kv_heads, self.head_dim)

        if self.q_norm is not None and self.k_norm is not None:
            q = self.q_norm(q)
            k = self.k_norm(k)

        start_pos = past_key_value[0].shape[1] if past_key_value is not None else 0

        # UniRoPE
        if rope_engine is not None:
            if is_visual and grid_hw is not None:
                q, k = rope_engine.apply_2d_rope(q, k, grid_hw[0], grid_hw[1])
            elif vision_len > 0 and grid_hw is not None:
                q_vis, k_vis = rope_engine.apply_2d_rope(
                    q[:, :vision_len], k[:, :vision_len], grid_hw[0], grid_hw[1]
                )
                text_pos = torch.arange(
                    seq_len - vision_len, device=hidden_states.device
                ) + vision_len + start_pos
                q_txt, k_txt = rope_engine.apply_1d_rope(
                    q[:, vision_len:], k[:, vision_len:], text_pos
                )
                q = torch.cat([q_vis, q_txt], dim=1)
                k = torch.cat([k_vis, k_txt], dim=1)
            else:
                pos = torch.arange(start_pos, start_pos + seq_len, device=hidden_states.device)
                q, k = rope_engine.apply_1d_rope(q, k, pos)

        if past_key_value is not None:
            past_k, past_v = past_key_value
            k = torch.cat([past_k, k], dim=1)
            v = torch.cat([past_v, v], dim=1)

        cached_kv = (k, v) if use_cache else None
        total_seq_len = k.shape[1]

        # Expand KV heads
        if self.num_kv_groups > 1:
            k_expanded = (
                k.unsqueeze(3)
                .expand(batch_size, total_seq_len, self.num_kv_heads, self.num_kv_groups, self.head_dim)
                .reshape(batch_size, total_seq_len, self.num_heads, self.head_dim)
            )
            v_expanded = (
                v.unsqueeze(3)
                .expand(batch_size, total_seq_len, self.num_kv_heads, self.num_kv_groups, self.head_dim)
                .reshape(batch_size, total_seq_len, self.num_heads, self.head_dim)
            )
        else:
            k_expanded = k
            v_expanded = v

        # -------------------------------------------------------------
        # Tier 1: Local Intra-Segment Attention
        # -------------------------------------------------------------
        q_t = q.transpose(1, 2)            # [B, H, S, D]
        k_t = k_expanded.transpose(1, 2)   # [B, H, S_total, D]
        v_t = v_expanded.transpose(1, 2)   # [B, H, S_total, D]

        attn_scores = torch.matmul(q_t, k_t.transpose(-2, -1)) * self.scale  # [B, H, S, S_total]

        # Local segment mask: restrict attention to within same segment or past tokens
        C = self.segment_size
        device = hidden_states.device

        # If total sequence length <= C or vision tokens dominate, local covers entire sequence
        if total_seq_len > C and seq_len > 1:
            # Construct hierarchical local mask
            # row index i in [0..seq_len-1] corresponds to global index (start_pos + i)
            q_idx = torch.arange(start_pos, start_pos + seq_len, device=device).unsqueeze(1)
            k_idx = torch.arange(total_seq_len, device=device).unsqueeze(0)
            # Same segment condition: q_idx // C == k_idx // C
            # Causal condition: k_idx <= q_idx
            local_valid = (q_idx // C == k_idx // C) & (k_idx <= q_idx)
            # Cross-segment attention is masked out locally (handled by Tier 2 global routing)
            local_mask = torch.where(local_valid, 0.0, float("-inf")).unsqueeze(0).unsqueeze(0)
            attn_scores = attn_scores + local_mask
        elif attention_mask is not None:
            attn_scores = attn_scores + attention_mask

        attn_probs = F.softmax(attn_scores, dim=-1, dtype=torch.float32).to(v_t.dtype)
        local_out = torch.matmul(attn_probs, v_t)  # [B, H, S, D]
        local_out = local_out.transpose(1, 2).contiguous().view(batch_size, seq_len, -1)

        # -------------------------------------------------------------
        # Tier 2: Global Inter-Segment Summary Attention
        # -------------------------------------------------------------
        if total_seq_len > C and seq_len > 1:
            num_segments = (seq_len + C - 1) // C
            # Extract segment pooled representations
            # Pad seq_len to multiple of C for parallel pooling
            pad_len = (num_segments * C) - seq_len
            if pad_len > 0:
                h_padded = F.pad(hidden_states, (0, 0, 0, pad_len))
            else:
                h_padded = hidden_states

            # Reshape into [B, num_segments, C, D] and compute segment mean
            seg_chunks = h_padded.view(batch_size, num_segments, C, self.hidden_dim)
            if pad_len > 0:
                # Correct mean for the last padded chunk
                seg_summaries = seg_chunks.sum(dim=2) / torch.tensor(
                    [C] * (num_segments - 1) + [C - pad_len], device=device, dtype=hidden_states.dtype
                ).view(1, -1, 1)
            else:
                seg_summaries = seg_chunks.mean(dim=2)  # [B, num_segments, D]

            q_glob = self.global_q_proj(seg_summaries).view(batch_size, num_segments, self.num_heads, self.head_dim)
            k_glob = self.global_k_proj(seg_summaries).view(batch_size, num_segments, self.num_heads, self.head_dim)
            v_glob = self.global_v_proj(seg_summaries).view(batch_size, num_segments, self.num_heads, self.head_dim)

            q_gt = q_glob.transpose(1, 2)
            k_gt = k_glob.transpose(1, 2)
            v_gt = v_glob.transpose(1, 2)

            glob_scores = torch.matmul(q_gt, k_gt.transpose(-2, -1)) * self.scale
            causal_seg = torch.triu(torch.full((num_segments, num_segments), float("-inf"), device=device), diagonal=1)
            glob_scores = glob_scores + causal_seg.unsqueeze(0).unsqueeze(0)

            glob_probs = F.softmax(glob_scores, dim=-1, dtype=torch.float32).to(v_gt.dtype)
            glob_out = torch.matmul(glob_probs, v_gt)  # [B, H, num_segments, D]
            glob_out = glob_out.transpose(1, 2).contiguous().view(batch_size, num_segments, -1)
            glob_proj = self.global_out_proj(glob_out)  # [B, num_segments, hidden_dim]

            # Broadcast back to token sequence
            glob_broadcast = glob_proj.repeat_interleave(C, dim=1)[:, :seq_len, :]

            # Tier 3: Hierarchical Gated Fusion
            gate_input = torch.cat([local_out, glob_broadcast], dim=-1)
            gate = torch.sigmoid(self.gate_proj(gate_input))
            fused = local_out + gate * glob_broadcast
            final_out = self.o_proj(fused)
        else:
            final_out = self.o_proj(local_out)

        if use_cache:
            return final_out, cached_kv
        return final_out


def run_test():
    print("Testing HierarchicalVirtuAttention...")
    cfg = ModelConfig(
        num_layers=2,
        hidden_dim=256,
        intermediate_dim=512,
        num_attention_heads=4,
        num_kv_heads=2,
        head_dim=64,
        vocab_size=1000,
    )
    attn = HierarchicalVirtuAttention(cfg, segment_size=16)
    x = torch.randn(2, 64, cfg.hidden_dim)
    rope = UniRoPE(dim=cfg.head_dim)

    # 1. Forward check
    out = attn(x, rope_engine=rope)
    assert out.shape == (2, 64, cfg.hidden_dim)
    print("✓ Forward pass shape OK:", out.shape)

    # 2. Backward check
    loss = out.sum()
    loss.backward()
    assert attn.q_proj.weight.grad is not None
    assert attn.global_q_proj.weight.grad is not None
    assert attn.gate_proj.weight.grad is not None
    print("✓ Backward pass gradient OK")

    # 3. Short sequence (< C)
    x_short = torch.randn(2, 8, cfg.hidden_dim)
    out_short = attn(x_short, rope_engine=rope)
    assert out_short.shape == (2, 8, cfg.hidden_dim)
    print("✓ Short sequence (< segment_size) OK")

    # 4. Odd sequence length
    x_odd = torch.randn(2, 37, cfg.hidden_dim)
    out_odd = attn(x_odd, rope_engine=rope)
    assert out_odd.shape == (2, 37, cfg.hidden_dim)
    print("✓ Non-divisible sequence length (37) OK")

    # 5. KV Cache check
    x_step = torch.randn(2, 1, cfg.hidden_dim)
    past_kv = (torch.randn(2, 32, 2, 64), torch.randn(2, 32, 2, 64))
    out_cached, new_kv = attn(x_step, rope_engine=rope, past_key_value=past_kv, use_cache=True)
    assert out_cached.shape == (2, 1, cfg.hidden_dim)
    assert new_kv[0].shape == (2, 33, 2, 64)
    print("✓ KV cache incremental step OK")
    print("All prototype checks passed!")


if __name__ == "__main__":
    run_test()
