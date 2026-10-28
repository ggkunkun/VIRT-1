"""Loop Transformer: Recurrent Iterative Core Components.

This module provides the independent modularized components for the Loop Transformer
architecture:
1. LoopStepController: Runtime dynamic loop step scheduler and controller.
2. LoopConvergenceCriterion: Tensor convergence detector with relative L2 / Cosine metrics.
3. LoopStateCache: Cross-loop-step hidden state and KV cache manager.
4. LoopRMSNorm: Recurrent normalization layer for iterative stabilization.
5. LoopStateGate: Learnable state gating mechanism between consecutive loop iterations.
"""

from __future__ import annotations
from typing import Optional, Tuple, Dict, Any, List
import math
import torch
import torch.nn as nn
import torch.nn.functional as F

from virtu_omni.config import ModelConfig


class LoopRMSNorm(nn.Module):
    """Loop Normalization layer for recurrent stabilization across iterations.

    Normalizes recurrent activations at the boundary of each loop step to
    prevent representation collapse or gradient explosion.
    """

    def __init__(self, dim: int, eps: float = 1e-6) -> None:
        super().__init__()
        self.eps = eps
        self.weight = nn.Parameter(torch.ones(dim))

    def _norm(self, x: torch.Tensor) -> torch.Tensor:
        return x * torch.rsqrt(x.pow(2).mean(-1, keepdim=True) + self.eps)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        normed = self._norm(x.float()).type_as(x)
        return normed * self.weight


class LoopStateGate(nn.Module):
    """Learnable State Gating Unit for Loop Transformer.

    Computes a dynamic gate balancing the newly transformed representation
    h_tilde_t against the prior state h_{t-1}:
        g_t = sigmoid(W_gate * h_tilde_t + U_gate * h_{t-1} + b_gate)
        h_t = g_t * h_tilde_t + (1 - g_t) * h_{t-1}

    Initialized with zero weights and positive bias (+10.0) so that g_t ~ 1.0
    at step 0, ensuring seamless numerical equivalence to standard Transformer.
    """

    def __init__(self, hidden_dim: int, bias_init: float = 10.0) -> None:
        super().__init__()
        self.hidden_dim = hidden_dim
        self.w_gate = nn.Linear(hidden_dim, hidden_dim, bias=True)
        self.u_gate = nn.Linear(hidden_dim, hidden_dim, bias=False)

        # Initialize to identity passthrough
        nn.init.zeros_(self.w_gate.weight)
        nn.init.constant_(self.w_gate.bias, bias_init)
        nn.init.zeros_(self.u_gate.weight)

    def forward(self, h_tilde: torch.Tensor, h_prev: torch.Tensor) -> torch.Tensor:
        """Blend h_tilde and h_prev via state gate."""
        gate = torch.sigmoid(self.w_gate(h_tilde) + self.u_gate(h_prev))
        return gate * h_tilde + (1.0 - gate) * h_prev


class LoopStepController:
    """Runtime dynamic loop step scheduler and controller.

    Enables dynamic, adaptive adjustment of the recurrent iteration depth
    during both training and inference without graph recompilation.
    """

    def __init__(self, config: ModelConfig) -> None:
        self.config = config
        self._max_loop_steps: int = config.max_loop_steps
        self.adaptive_loop: bool = config.adaptive_loop
        self.step_history: List[Dict[str, Any]] = []

    @property
    def max_loop_steps(self) -> int:
        return self._max_loop_steps

    def set_max_steps(self, steps: int) -> None:
        """Dynamically adjust maximum loop steps at runtime."""
        if steps < 1:
            raise ValueError(f"Loop steps must be >= 1, got {steps}")
        self._max_loop_steps = steps

    def reset(self) -> None:
        """Clear execution history."""
        self.step_history.clear()

    def record_step(
        self,
        step_idx: int,
        delta: float,
        converged: bool,
        layer_idx: Optional[int] = None,
    ) -> None:
        """Record telemetry of an executed loop iteration."""
        self.step_history.append({
            "step_idx": step_idx,
            "layer_idx": layer_idx,
            "delta": delta,
            "converged": converged,
        })

    def get_summary(self) -> Dict[str, Any]:
        """Return execution summary statistics."""
        if not self.step_history:
            return {
                "total_steps": 0,
                "avg_delta": 0.0,
                "converged_steps": 0,
                "max_configured_steps": self._max_loop_steps,
            }
        total = len(self.step_history)
        avg_delta = sum(item["delta"] for item in self.step_history) / total
        converged = sum(1 for item in self.step_history if item["converged"])
        return {
            "total_steps": total,
            "avg_delta": round(avg_delta, 6),
            "converged_steps": converged,
            "max_configured_steps": self._max_loop_steps,
        }


class LoopConvergenceCriterion:
    """Dynamic iteration termination decision module based on tensor convergence.

    Evaluates relative change between successive hidden states:
    - Relative L2: ||h_t - h_{t-1}||_F / (||h_{t-1}||_F + eps)
    - Cosine Distance: 1.0 - CosineSimilarity(h_t, h_{t-1})
    """

    def __init__(
        self,
        threshold: float = 1e-4,
        metric: str = "relative_l2",
        eps: float = 1e-8,
    ) -> None:
        self.threshold = threshold
        self.metric = metric
        self.eps = eps

    def compute_delta(self, h_curr: torch.Tensor, h_prev: torch.Tensor) -> torch.Tensor:
        """Compute scalar distance metric between current and previous representations."""
        if self.metric == "cosine":
            # Cosine distance over hidden dimension
            cos_sim = F.cosine_similarity(h_curr.flatten(0, 1), h_prev.flatten(0, 1), dim=-1, eps=self.eps)
            return (1.0 - cos_sim.mean())
        else:
            # Default: Relative Frobenius / L2 norm
            diff_norm = torch.linalg.norm(h_curr - h_prev, dim=-1)
            prev_norm = torch.linalg.norm(h_prev, dim=-1) + self.eps
            relative_diff = (diff_norm / prev_norm).mean()
            return relative_diff

    def evaluate(
        self, h_curr: torch.Tensor, h_prev: torch.Tensor
    ) -> Tuple[bool, float]:
        """Determine if iteration has reached convergence within threshold.

        Returns:
            (converged: bool, delta: float)
        """
        with torch.no_grad():
            delta_tensor = self.compute_delta(h_curr, h_prev)
            delta_val = float(delta_tensor.item())
            if math.isnan(delta_val) or math.isinf(delta_val):
                return False, 1.0
            converged = delta_val < self.threshold
            return converged, delta_val


class LoopStateCache:
    """Cross-loop-step state cache and memory reuse unit.

    Provides zero-leak storage for:
    1. Past loop activations h_{t-1} across iterations.
    2. Reusable Key-Value attention states to reduce redundant projections.
    """

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self._state_store: Dict[str, torch.Tensor] = {}
        self._kv_store: Dict[str, Tuple[torch.Tensor, torch.Tensor]] = {}

    def set_state(self, key: str, tensor: torch.Tensor) -> None:
        """Store intermediate tensor for given identifier."""
        if not self.enabled:
            return
        self._state_store[key] = tensor

    def get_state(self, key: str) -> Optional[torch.Tensor]:
        """Retrieve stored intermediate tensor."""
        if not self.enabled:
            return None
        return self._state_store.get(key)

    def set_kv(
        self, layer_idx: int, step_idx: int, k: torch.Tensor, v: torch.Tensor
    ) -> None:
        """Store Key-Value cache for a specific layer and loop step."""
        if not self.enabled:
            return
        cache_key = f"L{layer_idx}_S{step_idx}"
        self._kv_store[cache_key] = (k, v)

    def get_kv(
        self, layer_idx: int, step_idx: int
    ) -> Optional[Tuple[torch.Tensor, torch.Tensor]]:
        """Retrieve cached Key-Value pairs."""
        if not self.enabled:
            return None
        cache_key = f"L{layer_idx}_S{step_idx}"
        return self._kv_store.get(cache_key)

    def clear(self) -> None:
        """Clear all stored state and KV buffers."""
        self._state_store.clear()
        self._kv_store.clear()

    def __len__(self) -> int:
        return len(self._state_store) + len(self._kv_store)
