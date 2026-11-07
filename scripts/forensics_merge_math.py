"""Forensics: is the merged weight delta the *correct* sum of LoRA deltas?

The merge receipt states the formula actually used::

    A_new = sum_i sqrt(g_i) * A_i
    B_new = sum_i sqrt(g_i) * B_i
    dW    = B_new @ A_new
    g_i   = w_i * (alpha_i / r_i)

Expanding that product gives

    dW = sum_i  g_i * B_i @ A_i          <- the diagonal: what we want
       + sum_{i != j} sqrt(g_i g_j) * B_i @ A_j   <- 12 pure-noise cross terms
                                               for four adapters

The cross terms mix unrelated adapters and are not small.  The correct merge
is a plain sum of per-adapter deltas::

    dW_correct = sum_i w_i * (alpha_i / r_i) * B_i @ A_i

This script recomputes both from the on-disk tensors and compares them with
what the merged checkpoint actually contains, so the claim is settled by
numbers rather than by reading a receipt.
"""

from __future__ import annotations

import json
import os

import numpy as np
from safetensors import safe_open

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(ROOT, "checkpoints", "_base_qwen3_8b")
MERGED = os.path.join(ROOT, "checkpoints", "virtu_merged")
CK = os.path.join(ROOT, "checkpoints")

MERGE_SPEC = [
    ("turing_conversational_lora", 1.2),
    ("cad_cam_six_software_lora", 1.0),
    ("omni_autonomous_agent_lora", 0.8),
    ("ug_teacher_guided_agent_lora", 0.7),
]

TARGETS = [
    "model.layers.0.mlp.down_proj.weight",
    "model.layers.0.self_attn.q_proj.weight",
    "model.layers.17.mlp.gate_proj.weight",
    "model.layers.35.self_attn.o_proj.weight",
]


def index_of(model_dir):
    with open(os.path.join(model_dir, "model.safetensors.index.json"), encoding="utf-8") as f:
        return json.load(f)["weight_map"]


def load_tensor(model_dir, wmap, name):
    """safetensors' numpy backend cannot decode bfloat16; go through torch."""
    import torch
    shard = os.path.join(model_dir, wmap[name])
    with safe_open(shard, framework="pt") as f:
        t = f.get_tensor(name)
    return t.to(torch.float32).numpy()


def lora_factors(adapter_dir, target):
    """Return (A, B, alpha, r) for one adapter, or None if it does not touch target."""
    import torch
    path = os.path.join(adapter_dir, "adapter_model.safetensors")
    if not os.path.exists(path):
        return None
    want_a = None
    want_b = None
    # adapter keys look like
    #   base_model.model.model.layers.0.mlp.down_proj.lora_A.weight
    # while the checkpoint key is
    #   model.layers.0.mlp.down_proj.weight
    stem = target[: -len(".weight")] if target.endswith(".weight") else target
    with safe_open(path, framework="pt") as f:
        keys = list(f.keys())
        for k in keys:
            if not k.endswith(".lora_A.weight"):
                continue
            base = k[: -len(".lora_A.weight")]
            if base.endswith(stem):
                want_a, want_b = k, k[: -len(".lora_A.weight")] + ".lora_B.weight"
                break
        if want_a is None:
            return None
        A = f.get_tensor(want_a).to(torch.float32).numpy()
        B = f.get_tensor(want_b).to(torch.float32).numpy()
    with open(os.path.join(adapter_dir, "adapter_config.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    return A, B, float(cfg.get("lora_alpha", 1.0)), int(cfg.get("r", A.shape[0]))


def main():
    out = []
    base_map = index_of(BASE)
    merged_map = index_of(MERGED)

    for target in TARGETS:
        W = load_tensor(BASE, base_map, target).astype(np.float32)
        Wp = load_tensor(MERGED, merged_map, target).astype(np.float32)
        actual_delta = Wp - W

        correct = np.zeros_like(W)
        buggy = np.zeros_like(W)
        A_sum = None
        B_sum = None
        used = []
        for name, weight in MERGE_SPEC:
            got = lora_factors(os.path.join(CK, name), target)
            if got is None:
                continue
            A, B, alpha, r = got
            g = weight * (alpha / r)
            used.append({"adapter": name, "weight": weight, "alpha": alpha, "r": r,
                         "g": g, "A_shape": list(A.shape), "B_shape": list(B.shape)})
            correct += (g * (B.astype(np.float32) @ A.astype(np.float32)))
            ca = np.sqrt(g) * A.astype(np.float32)
            cb = np.sqrt(g) * B.astype(np.float32)
            A_sum = ca if A_sum is None else A_sum + ca
            B_sum = cb if B_sum is None else B_sum + cb
        if A_sum is None:
            out.append({"target": target, "error": "no adapter touches this tensor"})
            continue
        buggy = B_sum @ A_sum

        # cross terms = what the buggy formula adds on top of the correct sum
        cross = buggy - correct

        def rel(a, b):
            nb = np.linalg.norm(b)
            return float(np.linalg.norm(a) / nb) if nb else float("nan")

        def stats(d):
            return {"l2": float(np.linalg.norm(d)),
                    "max_abs": float(np.abs(d).max()),
                    "rms": float(np.sqrt((d ** 2).mean()))}

        out.append({
            "target": target,
            "adapters_used": used,
            "delta_actually_in_merged_file": stats(actual_delta),
            "correct_sum_of_lora_deltas": stats(correct),
            "buggy_cross_term_formula": stats(buggy),
            "pure_cross_term_noise": stats(cross),
            "relerr_file_vs_correct": rel(actual_delta - correct, correct),
            "relerr_file_vs_buggy": rel(actual_delta - buggy, buggy),
            "relerr_cross_vs_correct": rel(cross, correct),
            "noise_share_of_file_delta": rel(cross, actual_delta),
            "verdict": ("merged file matches the CORRECT sum" if rel(actual_delta - correct, correct) < 0.05
                        else "merged file matches the CROSS-TERM formula" if rel(actual_delta - buggy, buggy) < 0.05
                        else "merged file matches NEITHER"),
        })

    path = os.path.join(ROOT, "benchmarks", "merge_math_forensics.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"base": BASE, "merged": MERGED, "results": out}, f, ensure_ascii=False, indent=2)
    print("wrote", path)
    for r in out:
        if "error" in r:
            print(r["target"], "ERROR", r["error"])
            continue
        print("=" * 90)
        print(r["target"])
        print("  merged-file delta      :", r["delta_actually_in_merged_file"])
        print("  correct sum of deltas  :", r["correct_sum_of_lora_deltas"])
        print("  cross-term formula     :", r["buggy_cross_term_formula"])
        print("  pure cross-term noise  :", r["pure_cross_term_noise"])
        print("  relerr(file, correct)   : %.4f" % r["relerr_file_vs_correct"])
        print("  relerr(file, buggy)     : %.4f" % r["relerr_file_vs_buggy"])
        print("  noise share of delta   : %.4f" % r["noise_share_of_file_delta"])
        print("  VERDICT:", r["verdict"])


if __name__ == "__main__":
    main()
