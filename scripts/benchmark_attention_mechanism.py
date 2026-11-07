"""Rigorous Empirical Attention Mechanism Benchmark & Evaluation Suite.

Measures and compares:
1. Convergence loss & loss reduction rate on standard task corpus.
2. Cross-entropy loss across varied sequence lengths (64, 256, 1024) and multimodal.
3. Inference latency (ms) and throughput (tokens/sec).
4. Autoregressive KV cache generation consistency (bit-exact match).
5. Gradient flow health (mean, min, max gradient norms).

Adheres strictly to Workspace Axiom 8 (Measurement Constitution: verifiable, attributable).
"""

from __future__ import annotations
import json
import os
import sys
import time
from typing import Dict, Any, List
import torch
import torch.nn as nn
import torch.nn.functional as F

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from virtu_omni.config import ModelConfig
from virtu_omni.models.architecture import VirtuOmni10B


def run_attention_evaluation(
    model_label: str = "Baseline_GQA",
    seed: int = 42,
    device_str: str = "cpu",
) -> Dict[str, Any]:
    torch.manual_seed(seed)
    device = torch.device(device_str)

    config = ModelConfig(
        num_layers=4,
        hidden_dim=256,
        intermediate_dim=768,
        num_attention_heads=4,
        num_kv_heads=2,
        head_dim=64,
        vocab_size=2000,
        vision_codebook_size=500,
        image_resolution=56,
        patch_size=14,
        max_position_embeddings=4096,
        max_loop_steps=1,
    )

    print(f"[{model_label}] Initializing model on {device}...")
    model = VirtuOmni10B(config).to(device)

    # 1. Forward Loss on multiple sequence lengths
    seq_lengths = [64, 256, 1024]
    loss_metrics: Dict[str, float] = {}

    model.eval()
    with torch.no_grad():
        for s in seq_lengths:
            torch.manual_seed(seed + s)
            input_ids = torch.randint(0, config.vocab_size, (2, s), device=device)
            labels = input_ids.clone()
            out = model(input_ids=input_ids, labels=labels, mode="text_gen")
            loss_val = float(out["loss"].item())
            loss_metrics[f"loss_seq_{s}"] = round(loss_val, 4)

        # Multimodal forward loss
        torch.manual_seed(seed + 999)
        mm_input_ids = torch.randint(0, config.vocab_size, (2, 64), device=device)
        mm_labels = mm_input_ids.clone()
        mm_images = torch.randn(2, 3, 56, 56, device=device)
        out_mm = model(input_ids=mm_input_ids, images=mm_images, labels=mm_labels, mode="multimodal_eval")
        loss_metrics["loss_multimodal"] = round(float(out_mm["loss"].item()), 4)

    # 2. Training Convergence Capability (20 steps on fixed corpus)
    print(f"[{model_label}] Evaluating training convergence across 20 steps...")
    model.train()
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=0.01)

    torch.manual_seed(seed)
    fixed_corpus = [
        torch.randint(0, config.vocab_size, (2, 128), device=device)
        for _ in range(20)
    ]

    initial_loss = 0.0
    final_loss = 0.0
    grad_norms: List[float] = []

    for step, batch_ids in enumerate(fixed_corpus):
        optimizer.zero_grad()
        out = model(input_ids=batch_ids, labels=batch_ids, mode="text_gen")
        loss = out["loss"]
        loss_val = float(loss.item())

        if step == 0:
            initial_loss = loss_val

        loss.backward()

        # Compute gradient norm
        total_norm = 0.0
        for p in model.parameters():
            if p.grad is not None:
                param_norm = p.grad.detach().data.norm(2)
                total_norm += param_norm.item() ** 2
        total_norm = total_norm ** 0.5
        grad_norms.append(total_norm)

        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()

        if step == len(fixed_corpus) - 1:
            final_loss = loss_val

    loss_reduction = initial_loss - final_loss
    loss_reduction_pct = (loss_reduction / initial_loss) * 100.0 if initial_loss > 0 else 0.0

    # 3. Autoregressive KV-Cache Consistency Check
    model.eval()
    torch.manual_seed(seed + 42)
    prompt = torch.randint(0, config.vocab_size, (1, 8), device=device)

    with torch.no_grad():
        torch.manual_seed(seed + 77)
        gen_cached = model.generate(
            input_ids=prompt, max_new_tokens=10, temperature=0.0, use_cache=True
        )
        torch.manual_seed(seed + 77)
        gen_uncached = model.generate(
            input_ids=prompt, max_new_tokens=10, temperature=0.0, use_cache=False
        )

    cache_consistent = bool(torch.equal(gen_cached, gen_uncached))

    # 4. Latency & Throughput Benchmark
    bench_lengths = [128, 512, 1024]
    latency_metrics: Dict[str, Any] = {}

    with torch.no_grad():
        for bl in bench_lengths:
            torch.manual_seed(seed + bl)
            inp = torch.randint(0, config.vocab_size, (1, bl), device=device)
            # warmup
            _ = model(input_ids=inp, mode="text_gen")

            iters = 5
            t0 = time.perf_counter()
            for _ in range(iters):
                _ = model(input_ids=inp, mode="text_gen")
            t_avg = (time.perf_counter() - t0) / iters
            throughput = bl / t_avg

            latency_metrics[f"latency_{bl}_ms"] = round(t_avg * 1000, 2)
            latency_metrics[f"throughput_{bl}_tok_s"] = round(throughput, 1)

    result = {
        "model_label": model_label,
        "loss_metrics": loss_metrics,
        "convergence": {
            "initial_loss": round(initial_loss, 4),
            "final_loss": round(final_loss, 4),
            "loss_reduction": round(loss_reduction, 4),
            "loss_reduction_pct": round(loss_reduction_pct, 2),
            "mean_grad_norm": round(float(sum(grad_norms) / len(grad_norms)), 4),
            "min_grad_norm": round(float(min(grad_norms)), 4),
            "max_grad_norm": round(float(max(grad_norms)), 4),
        },
        "generation": {
            "cache_consistent": cache_consistent,
            "generated_tokens": gen_cached.tolist()[0],
        },
        "latency": latency_metrics,
        "param_count": sum(p.numel() for p in model.parameters()),
    }

    return result


if __name__ == "__main__":
    label = sys.argv[1] if len(sys.argv) > 1 else "Baseline_GQA"
    out_file = sys.argv[2] if len(sys.argv) > 2 else f"benchmarks/{label.lower()}_results.json"
    print(f"Running evaluation for {label}...")
    res = run_attention_evaluation(model_label=label)
    os.makedirs(os.path.dirname(os.path.abspath(out_file)), exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2, ensure_ascii=False)
    print(f"\nResult saved to {out_file}:")
    print(json.dumps(res, indent=2))
