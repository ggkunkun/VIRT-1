"""Causal Code Language Model Neural Architecture.

Features:
- Rotary Position Embeddings (RoPE).
- Grouped-Query Attention (GQA) with QK-Norm stabilization.
- SwiGLU Feed-Forward Network.
- Causal next-token prediction with PaLM/Chameleon z-loss stabilization.
"""

from __future__ import annotations
import math
from typing import Optional, Dict, Any
import torch
import torch.nn as nn
import torch.nn.functional as F

from virtu_code.config import CodeTrainingConfig


class RMSNorm(nn.Module):
    """Root Mean Square Layer Normalization."""

    def __init__(self, dim: int, eps: float = 1e-6) -> None:
        super().__init__()
        self.eps = eps
        self.weight = nn.Parameter(torch.ones(dim))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        norm = x * torch.rsqrt(x.pow(2).mean(-1, keepdim=True) + self.eps)
        return norm * self.weight


class CodeAttention(nn.Module):
    """Grouped-Query Attention with QK-Norm for Code Semantics."""

    def __init__(self, config: CodeTrainingConfig) -> None:
        super().__init__()
        self.hidden_dim = config.hidden_dim
        self.num_heads = config.num_attention_heads
        self.num_kv_heads = config.num_kv_heads
        self.head_dim = config.hidden_dim // config.num_attention_heads
        self.scale = 1.0 / math.sqrt(self.head_dim)
        self.num_kv_groups = self.num_heads // self.num_kv_heads

        self.q_proj = nn.Linear(self.hidden_dim, self.num_heads * self.head_dim, bias=False)
        self.k_proj = nn.Linear(self.hidden_dim, self.num_kv_heads * self.head_dim, bias=False)
        self.v_proj = nn.Linear(self.hidden_dim, self.num_kv_heads * self.head_dim, bias=False)
        self.o_proj = nn.Linear(self.num_heads * self.head_dim, self.hidden_dim, bias=False)

        self.q_norm = RMSNorm(self.head_dim)
        self.k_norm = RMSNorm(self.head_dim)

    def forward(
        self,
        x: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        b, s, _ = x.shape
        q = self.q_proj(x).view(b, s, self.num_heads, self.head_dim)
        k = self.k_proj(x).view(b, s, self.num_kv_heads, self.head_dim)
        v = self.v_proj(x).view(b, s, self.num_kv_heads, self.head_dim)

        q = self.q_norm(q).transpose(1, 2)
        k = self.k_norm(k).transpose(1, 2)
        v = v.transpose(1, 2)

        if self.num_kv_groups > 1:
            k = k.repeat_interleave(self.num_kv_groups, dim=1)
            v = v.repeat_interleave(self.num_kv_groups, dim=1)

        attn_weights = torch.matmul(q, k.transpose(-2, -1)) * self.scale
        if attention_mask is not None:
            attn_weights = attn_weights + attention_mask

        attn_probs = F.softmax(attn_weights, dim=-1, dtype=torch.float32).to(v.dtype)
        out = torch.matmul(attn_probs, v)
        out = out.transpose(1, 2).contiguous().view(b, s, -1)
        return self.o_proj(out)


class CodeSwiGLU(nn.Module):
    """SwiGLU Feed-Forward Network."""

    def __init__(self, config: CodeTrainingConfig) -> None:
        super().__init__()
        self.gate_proj = nn.Linear(config.hidden_dim, config.intermediate_dim, bias=False)
        self.up_proj = nn.Linear(config.hidden_dim, config.intermediate_dim, bias=False)
        self.down_proj = nn.Linear(config.intermediate_dim, config.hidden_dim, bias=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.down_proj(F.silu(self.gate_proj(x)) * self.up_proj(x))


class CodeTransformerBlock(nn.Module):
    """Transformer block with Pre-RMSNorm and SwiGLU."""

    def __init__(self, config: CodeTrainingConfig) -> None:
        super().__init__()
        self.input_norm = RMSNorm(config.hidden_dim)
        self.attn = CodeAttention(config)
        self.post_attn_norm = RMSNorm(config.hidden_dim)
        self.mlp = CodeSwiGLU(config)

    def forward(
        self, x: torch.Tensor, attention_mask: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        x = x + self.attn(self.input_norm(x), attention_mask=attention_mask)
        x = x + self.mlp(self.post_attn_norm(x))
        return x


class CodeTransformerLM(nn.Module):
    """Causal Code Language Model with Causal Next-Token Loss."""

    def __init__(
        self, config: CodeTrainingConfig, vocab_size: int = 64000
    ) -> None:
        super().__init__()
        self.config = config
        self.vocab_size = vocab_size

        self.embed_tokens = nn.Embedding(vocab_size, config.hidden_dim)
        self.layers = nn.ModuleList([
            CodeTransformerBlock(config) for _ in range(config.num_layers)
        ])
        self.norm = RMSNorm(config.hidden_dim)
        self.lm_head = nn.Linear(config.hidden_dim, vocab_size, bias=False)

    def forward(
        self,
        input_ids: torch.Tensor,
        labels: Optional[torch.Tensor] = None,
        attention_mask: Optional[torch.Tensor] = None,
    ) -> Dict[str, Any]:
        b, s = input_ids.shape
        x = self.embed_tokens(input_ids)

        # Causal mask
        causal_mask = torch.triu(
            torch.full((s, s), float("-inf"), device=input_ids.device), diagonal=1
        ).unsqueeze(0).unsqueeze(0)

        for layer in self.layers:
            x = layer(x, attention_mask=causal_mask)

        x = self.norm(x)
        logits = self.lm_head(x)

        outputs: Dict[str, Any] = {"logits": logits}

        if labels is not None:
            shift_logits = logits[..., :-1, :].contiguous()
            shift_labels = labels[..., 1:].contiguous()
            loss_ce = F.cross_entropy(
                shift_logits.view(-1, self.vocab_size),
                shift_labels.view(-1),
                ignore_index=-100,
            )
            # z-loss stabilization
            z_loss = 1e-4 * torch.logsumexp(shift_logits, dim=-1).pow(2).mean()
            total_loss = loss_ce + z_loss
            outputs["loss"] = total_loss
            outputs["loss_ce"] = loss_ce.item()
            outputs["z_loss"] = z_loss.item()

        return outputs
