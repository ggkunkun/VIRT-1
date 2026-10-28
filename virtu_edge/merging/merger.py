"""Model Fusion Engine for Merging Models in Weight Space."""

from __future__ import annotations
import json
import os
import time
from typing import Dict, List, Any, Optional
import torch

from virtu_edge.merging.methods import slerp, ties_merge, dare_merge, linear_merge


class ModelMerger:
    """Weight-space model fusion engine executing SLERP, TIES, DARE, or Linear merging."""

    def __init__(self, method: str = "slerp") -> None:
        valid_methods = {"slerp", "ties", "dare", "linear"}
        if method not in valid_methods:
            raise ValueError(f"Unknown merge method: {method}. Valid: {valid_methods}")
        self.method = method

    def merge_state_dicts(
        self,
        base_state: Dict[str, torch.Tensor],
        task_states: List[Dict[str, torch.Tensor]],
        weights: Optional[List[float]] = None,
        slerp_factor: float = 0.5,
        ties_density: float = 0.5,
        dare_drop_rate: float = 0.3,
    ) -> Dict[str, torch.Tensor]:
        """Merge multiple state dicts into a unified state dict."""
        num_tasks = len(task_states)
        if weights is None:
            weights = [1.0 / num_tasks] * num_tasks

        merged_state: Dict[str, torch.Tensor] = {}
        common_keys = set(base_state.keys())
        for ts in task_states:
            common_keys = common_keys.intersection(ts.keys())

        for key in sorted(common_keys):
            base_t = base_state[key]
            tasks_t = [ts[key] for ts in task_states]

            # Only float tensors are interpolated; integer/bool buffers are copied from base
            if not base_t.is_floating_point():
                merged_state[key] = base_t.clone()
                continue

            if self.method == "slerp":
                if len(tasks_t) == 1:
                    merged_t = slerp(base_t, tasks_t[0], factor=slerp_factor)
                else:
                    # Sequential pairwise SLERP
                    curr = base_t
                    for i, t_val in enumerate(tasks_t):
                        curr = slerp(curr, t_val, factor=weights[i])
                    merged_t = curr
            elif self.method == "ties":
                merged_t = ties_merge(base_t, tasks_t, weights=weights, density=ties_density)
            elif self.method == "dare":
                merged_t = dare_merge(base_t, tasks_t, weights=weights, drop_rate=dare_drop_rate)
            elif self.method == "linear":
                merged_t = linear_merge([base_t] + tasks_t, weights=[1.0] + weights)
            else:
                merged_t = base_t.clone()

            merged_state[key] = merged_t

        return merged_state

    def merge_and_save(
        self,
        base_state: Dict[str, torch.Tensor],
        task_states: List[Dict[str, torch.Tensor]],
        output_checkpoint_path: str,
        weights: Optional[List[float]] = None,
        recipe_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Merge state dicts and save physical checkpoint with audit report."""
        os.makedirs(os.path.dirname(output_checkpoint_path), exist_ok=True)
        start_time = time.time()

        merged_dict = self.merge_state_dicts(base_state, task_states, weights=weights)
        torch.save(merged_dict, output_checkpoint_path)

        duration = time.time() - start_time
        file_size_mb = os.path.getsize(output_checkpoint_path) / (1024 * 1024)

        # Audit stats
        num_keys = len(merged_dict)
        total_params = sum(t.numel() for t in merged_dict.values())

        report = {
            "method": self.method,
            "output_checkpoint": output_checkpoint_path,
            "file_size_mb": round(file_size_mb, 2),
            "merged_tensors_count": num_keys,
            "total_parameters": total_params,
            "duration_sec": round(duration, 3),
            "metadata": recipe_metadata or {},
        }

        # Write audit receipt
        receipt_path = output_checkpoint_path.replace(".pt", "_receipt.json")
        with open(receipt_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        return report
