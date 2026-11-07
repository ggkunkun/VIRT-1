#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/densify_virtu_to_dense.py — P1-2 稠密化：把 virtu-moe-14b 的两条专家增量
TIES 合并回单条稠密 FFN，产出 Qwen3 稠密架构 HF 目录（供 ollama create -q 量化）。

数学口径（与 build_virtu_franken_moe.py 严格对齐，保证唯一变量是 FFN）：
  Δe0 = 0.60·Δcad + 0.40·Δtool        （MoE 专家 0 配方）
  Δe1 = 0.65·Δconv + 0.35·Δug         （MoE 专家 1 配方）
  FFN  = W_base + TIES_merge(Δe0, Δe1; w=(0.5,0.5), density=d, 符号选举)
  Attn = W_base + 0.25Δcad + 0.35Δtool + 0.25Δconv + 0.15Δug   （与 MoE 共享注意力逐位一致）

TIES 实现要点（Yadav et al. 2023）：
  1) magnitude trim：每个 Δ 只保留 |值| 前 density 比例（阈值用 1/50 采样分位数估计）
  2) sign election：按 Σ w·τ 的符号做加权多数表决，异号项置零
  3) 不做 DARE 式 1/p 重标定（非随机丢弃，重标定会放大噪声）

流式内存控制：单 tensor 峰值 ≈ 2×fp32(201MB) + base(100MB) + mask(50MB) < 600MB。
"""
from __future__ import annotations

import argparse, gc, hashlib, json, logging, math, os, shutil, sys, time
from pathlib import Path
from typing import Dict, Optional

import torch
import safetensors.torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_virtu_franken_moe import SafeTensorReader, LoraAdapter  # noqa: E402

torch.set_num_threads(6)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)])
log = logging.getLogger("densify")

ROOT = Path(__file__).resolve().parent.parent
LORAS = {
    "cad": ("checkpoints/cad_cam_six_software_lora", 0.25),
    "tool": ("checkpoints/virtu_toolcall_lora", 0.35),
    "conv": ("checkpoints/turing_conversational_lora", 0.25),
    "ug": ("checkpoints/ug_teacher_guided_agent_lora", 0.15),
}
EXPERT0 = {"cad": 0.60, "tool": 0.40}
EXPERT1 = {"conv": 0.65, "ug": 0.35}


def sha256_file(p: Path, chunk: int = 1 << 22) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


def ties_trim_(d: torch.Tensor, density: float, sample_stride: int = 50) -> float:
    """就地 magnitude trim，返回所用阈值。"""
    flat = d.abs().flatten()
    samp = flat[::sample_stride]
    thr = torch.quantile(samp, 1.0 - density).item()
    d.mul_(d.abs() >= thr)
    return thr


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="checkpoints/_base_qwen3_8b")
    ap.add_argument("--out", default="checkpoints/virtu_dense_merged_hf")
    ap.add_argument("--merge-mode", choices=["sum_norm", "ties"], default="sum_norm")
    ap.add_argument("--density", type=float, default=0.6)
    ap.add_argument("--ffn-scale", type=float, default=1.0, help="合并后 FFN 增量整体缩放")
    ap.add_argument("--layers", type=int, default=36)
    ap.add_argument("--shard-gb", type=float, default=1.6)
    args = ap.parse_args()

    base_dir = ROOT / args.base if not Path(args.base).is_absolute() else Path(args.base)
    out_dir = ROOT / args.out if not Path(args.out).is_absolute() else Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    for p in out_dir.glob("model-*-of-*.safetensors"):
        p.unlink()

    t0 = time.time()
    idx = json.loads((base_dir / "model.safetensors.index.json").read_text(encoding="utf-8"))
    wmap = idx["weight_map"]
    readers: Dict[str, SafeTensorReader] = {}

    def base_t(name: str) -> torch.Tensor:
        sh = wmap[name]
        if sh not in readers:
            readers[sh] = SafeTensorReader(base_dir / sh)
        return readers[sh].read_tensor(name)

    loras = {k: LoraAdapter(ROOT / v[0], k) for k, v in LORAS.items()}
    for k, l in loras.items():
        log.info("LoRA %s r=%d scale=%.3f", k, l.r, l.scaling)

    tensors: Dict[str, torch.Tensor] = {}
    cur_bytes = 0
    max_bytes = int(args.shard_gb * 1024**3)
    shard_idx = 1
    out_map: Dict[str, str] = {}
    n_params = 0
    trim_stats = []

    def flush():
        nonlocal shard_idx, tensors, cur_bytes
        if not tensors:
            return
        name = f"model-{shard_idx:05d}-of-TOTAL.safetensors"
        safetensors.torch.save_file(tensors, str(out_dir / name))
        for k in tensors:
            out_map[k] = name
        log.info("分片 %s 写入 %d 张量 / %.2f GB", name, len(tensors), cur_bytes / 1024**3)
        tensors = {}
        cur_bytes = 0
        shard_idx += 1
        gc.collect()

    def add(name: str, t: torch.Tensor):
        nonlocal cur_bytes, n_params
        t = t.contiguous().to(torch.bfloat16)
        b = t.numel() * 2
        if cur_bytes + b > max_bytes and tensors:
            flush()
        tensors[name] = t
        cur_bytes += b
        n_params += t.numel()

    def delta(layer: int, proj: str, mix: Dict[str, float]) -> Optional[torch.Tensor]:
        acc = None
        for k, w in mix.items():
            d = loras[k].get_delta(layer, proj)
            if d is None:
                return None
            d = d.float().mul_(w)
            if acc is None:
                acc = d
            else:
                acc.add_(d)
                del d
        return acc

    log.info("稠密化启动 base=%s out=%s mode=%s density=%.2f ffn_scale=%.2f",
             base_dir, out_dir, args.merge_mode, args.density, args.ffn_scale)
    add("model.embed_tokens.weight", base_t("model.embed_tokens.weight"))

    for i in range(args.layers):
        lp = f"model.layers.{i}"
        add(f"{lp}.input_layernorm.weight", base_t(f"{lp}.input_layernorm.weight"))
        add(f"{lp}.post_attention_layernorm.weight", base_t(f"{lp}.post_attention_layernorm.weight"))
        for nn_ in ("q_norm", "k_norm"):
            k = f"{lp}.self_attn.{nn_}.weight"
            if k in wmap:
                add(k, base_t(k))

        # 共享注意力：与 MoE 完全相同配方（唯一变量控制）
        for proj in ("q_proj", "k_proj", "v_proj", "o_proj"):
            w = base_t(f"{lp}.self_attn.{proj}.weight").float()
            for k, (_, wt) in LORAS.items():
                d = loras[k].get_delta(i, proj)
                if d is not None:
                    w.add_(d.float(), alpha=wt)
            add(f"{lp}.self_attn.{proj}.weight", w)
            del w

        # FFN：合并两条专家增量
        #  mode=sum_norm（实测推荐）：两位专家增量实测近正交（cos≈0.002~0.02），
        #    TIES 的符号选举会把正交方向各删一半；改为「归一化后等强相加」，
        #    再整体缩放到 max(‖Δ0‖,‖Δ1‖)，使两条技能都保留 ~95% 强度。
        #  mode=ties（v1，已证伪）：纯 TIES(density=0.6)，实测 cos(Δdense,Δe0) 仅 0.19，
        #    专家 0 方向被 Δ1 的 3 倍量级压制 → 仅 31% 强度（见 verify_dense_merge.py）。
        for proj in ("gate_proj", "up_proj", "down_proj"):
            wb = base_t(f"{lp}.mlp.{proj}.weight")
            d0 = delta(i, proj, EXPERT0)
            d1 = delta(i, proj, EXPERT1)
            if d0 is None or d1 is None:
                log.warning("层 %d %s 缺 LoRA 增量，回退基座", i, proj)
                add(f"{lp}.mlp.{proj}.weight", wb)
                continue
            if args.merge_mode == "ties":
                t0_ = ties_trim_(d0, args.density)
                t1_ = ties_trim_(d1, args.density)
                acc = d0.to(torch.bfloat16).mul_(0.5)
                acc.add_(d1.to(torch.bfloat16), alpha=0.5)
                elected = torch.sign(acc)
                del acc
                merged = d0.mul_(torch.sign(d0).eq(elected).to(d0.dtype)).mul_(0.5)
                merged.add_(d1.mul_(torch.sign(d1).eq(elected).to(d1.dtype)), alpha=0.5)
                stat = {"layer": i, "proj": proj, "thr0": round(t0_, 6), "thr1": round(t1_, 6),
                        "kept_ratio": round(float((merged != 0).float().mean()), 4)}
            else:
                n0 = float(torch.linalg.vector_norm(d0))
                n1 = float(torch.linalg.vector_norm(d1))
                merged = d0.add_(d1)                       # Δ0 + Δ1（正交 → 平方和相加）
                ns = float(torch.linalg.vector_norm(merged))
                alpha = (max(n0, n1) / ns) if ns else 0.0
                merged.mul_(alpha)
                stat = {"layer": i, "proj": proj, "n0": round(n0, 5), "n1": round(n1, 5),
                        "alpha": round(alpha, 5),
                        "proj_ratio_e0": round(alpha * n0 / n0, 4) if n0 else 0.0,
                        "proj_ratio_e1": round(alpha * n1 / n1, 4) if n1 else 0.0}
            merged.mul_(args.ffn_scale)
            w = wb.float().add_(merged)
            add(f"{lp}.mlp.{proj}.weight", w)
            if i in (0, 18, 35) and proj == "gate_proj":
                trim_stats.append(stat)
                log.info("L%d %s %s |Δ|mean=%.6f", i, proj, json.dumps(stat, ensure_ascii=False),
                         merged.abs().mean().item())
            del d0, d1, merged, w
            gc.collect()
        log.info("层 %02d/%d 完成 (%.1fs, 累计 %.2f GB)", i, args.layers - 1,
                 time.time() - t0, cur_bytes / 1024**3)

    add("model.norm.weight", base_t("model.norm.weight"))
    add("lm_head.weight", base_t("lm_head.weight"))
    flush()

    # index + config + tokenizer
    (out_dir / "model.safetensors.index.json").write_text(json.dumps({
        "metadata": {"total_size": n_params * 2, "total_parameters": n_params,
                     "architecture": "Qwen3ForCausalLM",
                     "created_by": "Virtu-Densifier-TIES",
                     "ties_density": args.density, "ffn_scale": args.ffn_scale},
        "weight_map": out_map}, indent=2, ensure_ascii=False), encoding="utf-8")
    cfg = json.loads((base_dir / "config.json").read_text(encoding="utf-8"))
    cfg["architectures"] = ["Qwen3ForCausalLM"]
    cfg["model_type"] = "qwen3"
    for k in ("num_experts", "num_experts_per_tok", "moe_intermediate_size",
              "shared_expert_intermediate_size", "norm_topk_prob"):
        cfg.pop(k, None)
    (out_dir / "config.json").write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    for f in ("tokenizer.json", "tokenizer_config.json", "vocab.json", "merges.txt",
              "generation_config.json", "configuration.json"):
        if (base_dir / f).exists():
            shutil.copy2(base_dir / f, out_dir / f)

    receipt = {
        "kind": "dense_ties_merge", "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "script": "scripts/densify_virtu_to_dense.py",
        "script_sha256": sha256_file(Path(__file__).resolve()),
        "base_dir": str(base_dir), "out_dir": str(out_dir),
        "params": n_params, "params_b": round(n_params / 1e9, 4),
        "merge_mode": args.merge_mode,
        "density": args.density, "ffn_scale": args.ffn_scale,
        "expert0_mix": EXPERT0, "expert1_mix": EXPERT1,
        "attention_mix": {k: v[1] for k, v in LORAS.items()},
        "trim_stats": trim_stats, "shards": shard_idx - 1,
        "elapsed_s": round(time.time() - t0, 1), "basis": "measured",
    }
    (out_dir / "dense_receipt.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=False),
                                                encoding="utf-8")
    log.info("完成：%.2fB 参数 / %d 分片 / %.1fs", n_params / 1e9, shard_idx - 1, time.time() - t0)
    print(json.dumps({k: receipt[k] for k in ("params_b", "shards", "density", "ffn_scale", "elapsed_s")},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
