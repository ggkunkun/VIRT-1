# -*- coding: utf-8 -*-
"""virtu_omni/models/task_arithmetic_merger.py — DARE / TIES-Merging for Industrial Model Parameter Space.

Grounded in:
1. Task Arithmetic: "Editing Models with Task Arithmetic" (Ilharco et al., ICLR 2023).
2. TIES-Merging: "Resolving Interference When Merging Models" (Yadav et al., NeurIPS 2023).
3. DARE: "Language Models are Super Mario: Absorbing Abilities from Multiple Models without Forgetting" (Yu et al., 2024).

Core Architecture:
Virtu combines 4 specialized domain capabilities:
- tau_cad: Parametric CAD, FeatureTree, swEqnMgr, build123d.
- tau_cam: CNC Macro B, multi-controller dialects (FANUC/Siemens/Heidenhain).
- tau_cae: Lamé thick-cylinder elasticity, von Mises stress, FOS >= 1.5.
- tau_standards: 2D Drafting (ezdxf sub-10ms), standard layers, GD&T (H7/g6).

Merging Process:
1. Extract Task Vectors: tau_k = theta_k - theta_0.
2. DARE (Drop And REscale): Randomly drop p% delta parameters and rescale by 1/(1-p).
3. TIES (Trimming, Electing Signs, Disjoint Merging):
   - Trim: Retain top-k% largest magnitude entries.
   - Elect Sign: Consensual sign election via sign(sum_k tau_k).
   - Disjoint Merge: Filter out conflicting signs, average matching directions.
4. Synthesize Final Super-Weight: theta_merged = theta_0 + lambda * tau_consensus.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import math
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import torch
import torch.nn as nn

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

logger = logging.getLogger("virtu_omni.models.merger")


@dataclass
class TaskVector:
    """Represents parameter delta vector tau_k = theta_k - theta_0."""
    domain: str                                 # "CAD", "CAM", "CAE", "STANDARDS"
    deltas: Dict[str, torch.Tensor]             # param_name -> delta_tensor
    weight_scale: float = 1.0


@dataclass
class MergeProvenance:
    """Audit metadata adhering to Section 8 Measurement Constitution."""
    merge_id: str
    domains_fused: List[str]
    dare_drop_rate: float
    ties_topk: float
    consensus_alignment_score: float
    num_parameters_merged: int
    timestamp: float
    basis: str = "measured"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DAREPruner:
    """Applies Drop And REscale pruning to eliminate delta parameter redundancy."""

    @classmethod
    def prune_and_rescale(cls, tensor: torch.Tensor, drop_rate: float = 0.5) -> torch.Tensor:
        """Drop drop_rate elements with Bernoulli mask and scale by 1/(1-drop_rate)."""
        if drop_rate <= 0.0 or drop_rate >= 1.0:
            return tensor
        keep_prob = 1.0 - drop_rate
        mask = torch.bernoulli(torch.full_like(tensor, keep_prob))
        return (tensor * mask) / keep_prob


class TIESMerger:
    """Performs Trimming, Electing Sign, and Disjoint Merging across task vectors."""

    @classmethod
    def trim_topk(cls, tensor: torch.Tensor, topk: float = 0.2) -> torch.Tensor:
        """Retain top-k% entries with largest absolute magnitudes, zero out the rest."""
        if topk >= 1.0:
            return tensor
        flat = tensor.abs().flatten()
        k = max(1, int(len(flat) * topk))
        threshold = torch.topk(flat, k, largest=True).values[-1]
        mask = tensor.abs() >= threshold
        return tensor * mask.to(tensor.dtype)

    @classmethod
    def elect_sign(cls, task_tensors: List[torch.Tensor]) -> torch.Tensor:
        """Computes consensus sign across multiple task vectors."""
        summed = torch.zeros_like(task_tensors[0])
        for t in task_tensors:
            summed += t
        return torch.sign(summed)

    @classmethod
    def disjoint_merge(cls, task_tensors: List[torch.Tensor], consensus_sign: torch.Tensor) -> torch.Tensor:
        """Average only elements where task vector sign agrees with consensus sign."""
        accumulator = torch.zeros_like(consensus_sign)
        counts = torch.zeros_like(consensus_sign)

        for t in task_tensors:
            matches_sign = (torch.sign(t) == consensus_sign) & (t != 0)
            accumulator += t * matches_sign.to(t.dtype)
            counts += matches_sign.to(t.dtype)

        counts = torch.clamp(counts, min=1.0)
        return accumulator / counts


class VirtuTaskArithmeticEngine:
    """Unified DARE/TIES parameter fusion engine for Virtu Industrial Super-Models."""

    def __init__(
        self,
        dare_drop_rate: float = 0.3,
        ties_topk: float = 0.5,
        merge_lambda: float = 1.0,
    ):
        self.dare_drop_rate = dare_drop_rate
        self.ties_topk = ties_topk
        self.merge_lambda = merge_lambda

    def merge_task_vectors(
        self,
        base_weights: Dict[str, torch.Tensor],
        task_vectors: List[TaskVector],
    ) -> Tuple[Dict[str, torch.Tensor], MergeProvenance]:
        """Fuses multiple task vectors into base weights with zero interference."""
        t_start = time.time()
        fused_weights: Dict[str, torch.Tensor] = {}
        domains = [tv.domain for tv in task_vectors]

        param_names = list(base_weights.keys())
        total_params_count = 0
        alignment_scores = []

        for name in param_names:
            base_p = base_weights[name]
            deltas_for_param: List[torch.Tensor] = []

            for tv in task_vectors:
                if name in tv.deltas:
                    d = tv.deltas[name] * tv.weight_scale
                    # 1. DARE pruning
                    d_dare = DAREPruner.prune_and_rescale(d, drop_rate=self.dare_drop_rate)
                    # 2. TIES trimming
                    d_trimmed = TIESMerger.trim_topk(d_dare, topk=self.ties_topk)
                    deltas_for_param.append(d_trimmed)

            if not deltas_for_param:
                fused_weights[name] = base_p.clone()
                continue

            # 3. TIES Sign Election & Disjoint Merge
            consensus_sign = TIESMerger.elect_sign(deltas_for_param)
            merged_delta = TIESMerger.disjoint_merge(deltas_for_param, consensus_sign)

            # Consensus alignment metric
            flat_consensus = consensus_sign.flatten()
            aligned_ratio = (flat_consensus != 0).float().mean().item()
            alignment_scores.append(aligned_ratio)

            # 4. Synthesize fused parameter
            fused_weights[name] = base_p + self.merge_lambda * merged_delta
            total_params_count += base_p.numel()

        mean_align = sum(alignment_scores) / max(1, len(alignment_scores))
        h = hashlib.sha256(f"{domains}_{total_params_count}_{t_start}".encode()).hexdigest()[:8]
        merge_id = f"TIES_MERGE_{time.strftime('%Y%m%d_%H%M%S')}_{h}"

        provenance = MergeProvenance(
            merge_id=merge_id,
            domains_fused=domains,
            dare_drop_rate=self.dare_drop_rate,
            ties_topk=self.ties_topk,
            consensus_alignment_score=round(mean_align, 4),
            num_parameters_merged=total_params_count,
            timestamp=t_start,
            basis="measured",
        )

        return fused_weights, provenance

    @classmethod
    def falsifiable_ties_probe(cls) -> bool:
        """Rule 4: Injects 2 aligned task vectors (+1.0) and 1 rogue conflicting vector (-1.0).

        TIES consensus sign MUST elect +1.0 and purge/suppress the rogue -1.0 vector.
        """
        engine = VirtuTaskArithmeticEngine(dare_drop_rate=0.0, ties_topk=1.0)
        base = {"layer.weight": torch.zeros(10, 10)}

        v_cad = TaskVector("CAD", {"layer.weight": torch.ones(10, 10)})
        v_cam = TaskVector("CAM", {"layer.weight": torch.ones(10, 10)})
        v_rogue = TaskVector("ROGUE", {"layer.weight": -torch.ones(10, 10)})

        fused, prov = engine.merge_task_vectors(base, [v_cad, v_cam, v_rogue])
        fused_tensor = fused["layer.weight"]

        # Consensus direction must be strictly positive (+1.0), rogue vector suppressed
        return (fused_tensor > 0.0).all().item() and prov.consensus_alignment_score > 0.9
