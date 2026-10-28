"""Weight-Space Fusion Methods: SLERP, TIES, DARE, and Linear Interpolation."""

from __future__ import annotations
import math
from typing import Dict, List, Optional
import torch


def slerp(
    v0: torch.Tensor,
    v1: torch.Tensor,
    factor: float = 0.5,
    eps: float = 1e-7,
) -> torch.Tensor:
    """Spherical Linear Interpolation (SLERP) for high-dimensional parameter tensors.

    Preserves directional vector geometry on the hypersphere manifold.
    """
    v0_f = v0.float()
    v1_f = v1.float()

    v0_norm = torch.linalg.norm(v0_f)
    v1_norm = torch.linalg.norm(v1_f)

    if v0_norm < eps or v1_norm < eps:
        return (1.0 - factor) * v0 + factor * v1

    u0 = v0_f / v0_norm
    u1 = v1_f / v1_norm

    dot = torch.sum(u0 * u1).clamp(-1.0 + eps, 1.0 - eps)
    omega = torch.acos(dot)

    sin_omega = torch.sin(omega)
    if torch.abs(sin_omega) < eps:
        # Collinear vectors, fall back to linear
        return (1.0 - factor) * v0 + factor * v1

    c0 = torch.sin((1.0 - factor) * omega) / sin_omega
    c1 = torch.sin(factor * omega) / sin_omega

    res = (c0 * u0 + c1 * u1) * ((1.0 - factor) * v0_norm + factor * v1_norm)
    return res.to(v0.dtype)


def ties_merge(
    base: torch.Tensor,
    task_tensors: List[torch.Tensor],
    weights: List[float],
    density: float = 0.5,
) -> torch.Tensor:
    """TIES-Merging: Trimming, Electing Sign, and Disjoint Merging.

    Resolves parameter interference across multiple fine-tuned models.
    """
    deltas = [t.float() - base.float() for t in task_tensors]

    # Step 1: Trim small-magnitude entries (top-k density)
    trimmed_deltas: List[torch.Tensor] = []
    for d in deltas:
        k = max(1, int(d.numel() * density))
        flat_abs = torch.abs(d).reshape(-1)
        thresh = torch.kthvalue(flat_abs, flat_abs.numel() - k + 1).values
        mask = torch.abs(d) >= thresh
        trimmed_deltas.append(d * mask)

    # Step 2: Elect sign consensus
    weighted_sum = sum(w * d for w, d in zip(weights, trimmed_deltas))
    sign_consensus = torch.sign(weighted_sum)

    # Step 3: Disjoint Merge (filter out entries conflicting with sign consensus)
    merged_delta = torch.zeros_like(base, dtype=torch.float32)
    counts = torch.zeros_like(base, dtype=torch.float32)

    for w, d in zip(weights, trimmed_deltas):
        valid = (torch.sign(d) == sign_consensus) & (sign_consensus != 0)
        merged_delta += w * (d * valid)
        counts += (valid.float() * w)

    counts = torch.clamp(counts, min=1e-8)
    avg_delta = merged_delta / counts
    avg_delta[sign_consensus == 0] = 0.0

    return (base.float() + avg_delta).to(base.dtype)


def dare_merge(
    base: torch.Tensor,
    task_tensors: List[torch.Tensor],
    weights: List[float],
    drop_rate: float = 0.3,
) -> torch.Tensor:
    """DARE: Drop And REscale weight space merging.

    Randomly zeroes out delta entries and rescales remaining elements.
    """
    keep_prob = max(1e-4, 1.0 - drop_rate)
    rescaled_deltas: List[torch.Tensor] = []

    for d in [t.float() - base.float() for t in task_tensors]:
        mask = torch.bernoulli(torch.full_like(d, keep_prob))
        rescaled_deltas.append((d * mask) / keep_prob)

    blended_delta = sum(w * d for w, d in zip(weights, rescaled_deltas))
    return (base.float() + blended_delta).to(base.dtype)


def linear_merge(
    tensors: List[torch.Tensor],
    weights: List[float],
) -> torch.Tensor:
    """Standard convex linear interpolation of weights."""
    norm_weights = [w / sum(weights) for w in weights]
    res = sum(w * t.float() for w, t in zip(norm_weights, tensors))
    return res.to(tensors[0].dtype)
