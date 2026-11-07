#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Virtu-10B 阶段 B（能力激活）训练成本核算 —— 可复算，数字带 basis。

所有输入锚点都从本仓实测文件读取，不硬编码训练结果：
  - checkpoints/virtu_toolcall_lora/training_receipt.json : L40S 真实训练耗时/token
  - data/validation/train_cost_analysis.json              : 23,178 条语料实测 token
  - checkpoints/virtu-10b-d46-q4_0.gguf.receipt.json     : 10B 结构参数量
  - CLOUD_FINETUNE_PLAN_2026-11-01_v2.md §1              : 3,104,927 tok/epoch (2048 口径)

单价来自用户提供的云平台截图 / 项目文档标注的实测价。
输出 benchmarks/VIRTU_10B_TRAIN_COST.json
"""
import hashlib
import json
import os
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def j(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- measured
anchor = j("checkpoints/virtu_toolcall_lora/training_receipt.json")
corpus = j("data/validation/train_cost_analysis.json")
gguf = j("checkpoints/virtu-10b-d46-q4_0.gguf.receipt.json")

ANCHOR_TOKENS = anchor["total_tokens"]           # 3,140,926 (2 epoch 累计)
ANCHOR_SEC = anchor["runtime_seconds"]           # 3514.5878
ANCHOR_TOK_S = ANCHOR_TOKENS / ANCHOR_SEC        # L40S 实测吞吐
ANCHOR_CFG = "%s / lora r%d / grad_ckpt=%s / %s" % (
    anchor["gpu"], anchor["lora_r"], anchor["gradient_checkpointing"],
    anchor["attn_impl"])

N_TOTAL = gguf["output"]["params"]               # 10,120,199,680
N_FROZEN = 8_190_735_360                         # 原 36 层 + embed/lm_head
N_NEW = N_TOTAL - N_FROZEN                      # 1,929,464,320
assert N_NEW == 10 * 192_946_432

# 用户截图/文档标注的实测单价（元/小时）
PRICES = {
    "Tesla V100-SXM2-32GB": {"cny_per_h": 1.98, "tflops": 125, "vram_gb": 32,
                              "source": "2026-11-01 用户截图 (memory/2026-11-01.md:188)"},
    "NVIDIA L40S-48GB": {"cny_per_h": 4.50, "tflops": 181, "vram_gb": 48,
                          "source": "CLOUD_TRAINING_HARDENING_PLAN_2026-11-01.md:22"},
    "NVIDIA A800-80GB": {"cny_per_h": 7.20, "tflops": 312, "vram_gb": 80,
                          "source": "2026-10-30 用户截图 (memory/2026-10-30.md:202)"},
}

# ---------------------------------------------------------------- 显存核算 (design)
GiB = 2**30


def mem_gb(trainable_params, optimizer="adamw_fp32", frozen_params=N_FROZEN):
    w_frozen = frozen_params * 2 / GiB                 # bf16 冻结权重
    w_train = trainable_params * 2 / GiB               # bf16 可训权重
    if optimizer == "adamw_fp32":
        grad = trainable_params * 4 / GiB             # fp32 梯度
        opt = trainable_params * 8 / GiB              # fp32 m + v
        master = trainable_params * 4 / GiB           # fp32 master weights
    elif optimizer == "adamw_8bit":
        grad = trainable_params * 2 / GiB             # bf16 梯度
        opt = trainable_params * 1 / GiB              # 8bit m + v
        master = 0.0
    else:                                             # lora
        grad = trainable_params * 2 / GiB
        opt = trainable_params * 2 / GiB
        master = 0.0
    return {"frozen_weights": round(w_frozen, 2), "trainable_weights": round(w_train, 2),
            "grad": round(grad, 2), "optimizer_state": round(opt, 2),
            "fp32_master": round(master, 2),
            "state_total": round(w_frozen + w_train + grad + opt + master, 2)}


CONFIGS = {
    "full_adamw_fp32": {"label": "全参训 1.93B + AdamW(fp32)",
                        "mem": mem_gb(N_NEW, "adamw_fp32"),
                        "trainable": N_NEW},
    "full_adamw_8bit": {"label": "全参训 1.93B + AdamW(8bit)",
                        "mem": mem_gb(N_NEW, "adamw_8bit"),
                        "trainable": N_NEW},
    "lora_r64_new_layers": {"label": "仅新增层 LoRA r=64 (约 0.11B 可训)",
                            "mem": mem_gb(110_000_000, "lora"),
                            "trainable": 110_000_000},
}

# ---------------------------------------------------------------- FLOPs (design)
# 冻结层在前、可训层在后 => 反向只需过新增 10 层
F_PER_TOK = {
    "anchor_8b_lora_gc": 6 * N_FROZEN,              # fwd 2N + bwd-input 2N + ckpt 重算 2N
    "ours_10b_frozen_gc": 2 * N_TOTAL + 4 * N_NEW + 2 * N_NEW,
}
RATIO = F_PER_TOK["ours_10b_frozen_gc"] / F_PER_TOK["anchor_8b_lora_gc"]

# 实测外推：以 L40S 真实吞吐为锚，按 FLOPs 比修正，再打折覆盖全参优化器/batch 变小
# 打折系数给 0.5 / 0.8 / 1.2 三档，形成可信区间而非单点
EFF = {"conservative": 0.5, "baseline": 0.8, "optimistic": 1.2}
TOK_S = {k: ANCHOR_TOK_S / RATIO * v for k, v in EFF.items()}

# 卡间时长缩放：锚点实测在 L40S (181 TFLOPS)，其余按有效算力比折算。
# V100 另乘 0.75 折扣（sm70 无 bf16 Tensor Core / 无 FlashAttention-2）。
HOURS_SCALE = {
    "Tesla V100-SXM2-32GB": 181.0 / (125.0 * 0.75),
    "NVIDIA L40S-48GB": 1.0,
    "NVIDIA A800-80GB": 181.0 / 312.0,
}
# 显存可行性：状态占用 + 激活余量
FEASIBLE = {
    "Tesla V100-SXM2-32GB": "仅 lora_r64_new_layers 可行 (15.87GiB)，全参档仅供价格参照",
    "NVIDIA L40S-48GB": "full_adamw_8bit 可行；full_adamw_fp32 装不下",
    "NVIDIA A800-80GB": "三种配置全部可行",
}

# 语料档（token 均为 2 epoch 累计，可训练口径）
TOK_FIX_V1_1EP = 3_104_927        # CLOUD_FINETUNE_PLAN v2 §1，Qwen3 tokenizer 实测
CORPORA = {
    "A_试点_6.21M": {"tokens": TOK_FIX_V1_1EP * 2,
                     "basis": "measured(tok) / asserted(epochs)",
                     "source": "virtu_fix_v1 5991 条, 2048 口径"},
    "B_推荐_12.42M": {"tokens": TOK_FIX_V1_1EP * 4,
                      "basis": "asserted (v3 7216 条 + toolcall 通道, 同量级外推)",
                      "source": "data/train/virtu_v3 + toolcall_optimal"},
    "C_全量_120.55M": {"tokens": corpus["tokens_total"] * 2,
                       "basis": "measured(tok) / asserted(epochs); 含 52M tools-schema 噪声",
                       "source": "data/validation/train_cost_analysis.json"},
}

MFU = 0.40


def estimate(tokens, gpu, eff_key="baseline"):
    p = PRICES[gpu]
    hours_measured = tokens / TOK_S[eff_key] / 3600 * HOURS_SCALE[gpu]
    flops = F_PER_TOK["ours_10b_frozen_gc"] * tokens
    hours_flops = flops / (p["tflops"] * 1e12 * MFU) / 3600
    return {
        "hours_from_measured_anchor": round(hours_measured, 3),
        "cost_from_measured_anchor": round(hours_measured * p["cny_per_h"], 2),
        "hours_from_flops_MFU40": round(hours_flops, 3),
        "cost_from_flops_MFU40": round(hours_flops * p["cny_per_h"], 2),
    }


# ---------------------------------------------------------------- 完整总账
# 推荐档 B / L40S / baseline 吞吐，按 hardening plan S0-S6 阶段划分
B_HOURS = estimate(CORPORA["B_推荐_12.42M"]["tokens"], "NVIDIA L40S-48GB")
TRAIN_H = B_HOURS["hours_from_measured_anchor"]
PRICE_L40S = PRICES["NVIDIA L40S-48GB"]["cny_per_h"]

LEDGER = [
    {"stage": "S0 语料构建/去重/三闸", "cny": [0, 0], "basis": "measured",
     "note": "本地，virtu_v3 / virtu_fix_v1 已生成"},
    {"stage": "S1 环境准备 + 基座就位", "cny": [0, 9.0], "basis": "asserted",
     "note": "0~2h 机时；平台已预置 Qwen3-8B 则 0"},
    {"stage": "S2 preflight + 20 步 smoke", "cny": [0.5, 1.0], "basis": "asserted",
     "note": "约 10~15 min"},
    {"stage": "S3 主训练 2 epoch (12.42M tok)", "cny": [
        round(TRAIN_H * PRICE_L40S * 0.7, 2), round(TRAIN_H * PRICE_L40S * 1.6, 2)],
     "basis": "design (实测锚点外推)", "note": "%.2f h @ ¥%.2f/h，区间覆盖吞吐不确定" % (TRAIN_H, PRICE_L40S)},
    {"stage": "S4 条件补强 / 失败重试 (最多 2 轮)", "cny": [0, 9.0], "basis": "asserted",
     "note": "hardening plan S5: 0.5~1h/轮；不过闸才发生"},
    {"stage": "S5 产物回传 + 数据盘/存储", "cny": [0, 5.0], "basis": "asserted",
     "note": "新增层权重 3.86GB(bf16) + 50GB 数据盘按天"},
    {"stage": "S6 本地合并 / GGUF / Ollama 注册", "cny": [0, 0], "basis": "measured",
     "note": "纯 numpy，阶段 A 已验证约 1~3 min"},
    {"stage": "S7 本地 A/B 评测 (300 条 × 2 臂)", "cny": [0, 0], "basis": "measured",
     "note": "¥0 但耗时：10B 8.41 tok/s × 512 tok ≈ 61 s/条 → 约 10.2 h 本机"},
]

lo = sum(x["cny"][0] for x in LEDGER)
hi = sum(x["cny"][1] for x in LEDGER)

result = {
    "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    "question": "Virtu-10B 阶段 B（L2 能力激活）完整训练成本",
    "scope": "阶段 A 结构扩展 ¥0（本机 65.6s）；阶段 C 上线 ¥0（本机纯 numpy）。仅阶段 B 产生云算力费用。",
    "inputs_measured": {
        "anchor_receipt": "checkpoints/virtu_toolcall_lora/training_receipt.json",
        "anchor_gpu": anchor["gpu"], "anchor_config": ANCHOR_CFG,
        "anchor_tokens_2ep": ANCHOR_TOKENS, "anchor_runtime_s": ANCHOR_SEC,
        "anchor_tok_per_s": round(ANCHOR_TOK_S, 2),
        "corpus_full_rows": corpus["samples"],
        "corpus_full_tokens_per_epoch": corpus["tokens_total"],
        "corpus_full_loss_tokens": corpus["loss_tokens_total"],
        "model_params_total": N_TOTAL, "model_params_frozen": N_FROZEN,
        "model_params_new": N_NEW,
        "prices": PRICES,
    },
    "memory_analysis": CONFIGS,
    "memory_verdict": {
        "full_adamw_fp32": "%.2f GiB 状态 + 激活 => L40S 48GB 装不下，需 A800 80GB 或改 8bit 优化器" % CONFIGS["full_adamw_fp32"]["mem"]["state_total"],
        "full_adamw_8bit": "%.2f GiB 状态 => L40S 48GB 可行" % CONFIGS["full_adamw_8bit"]["mem"]["state_total"],
        "lora_r64_new_layers": "%.2f GiB 状态 => V100 32GB 可行，单价最低" % CONFIGS["lora_r64_new_layers"]["mem"]["state_total"],
        "correction_to_plan": "上一版方案写 L40S 48GB 全参训新增层，未注明必须 8bit AdamW，此处修正",
    },
    "flops_model": {
        "anchor_GFLOPs_per_token": round(F_PER_TOK["anchor_8b_lora_gc"] / 1e9, 2),
        "ours_GFLOPs_per_token": round(F_PER_TOK["ours_10b_frozen_gc"] / 1e9, 2),
        "ratio_ours_over_anchor": round(RATIO, 3),
        "note": "冻结层在前 => 反向只需过新增 10 层，每 token 计算量低于 8B 全层 LoRA",
    },
    "throughput_projection": {"tok_per_s": {k: round(v, 1) for k, v in TOK_S.items()},
                              "MFU_assumed": MFU,
                              "efficiency_factors": EFF},
    "gpu_hours_scale_vs_L40S": {k: round(v, 3) for k, v in HOURS_SCALE.items()},
    "gpu_feasibility": FEASIBLE,
    "unit_cost_cny_per_M_tokens": {
        gpu: {k: round(1e6 / TOK_S[k] / 3600 * HOURS_SCALE[gpu]
                       * PRICES[gpu]["cny_per_h"], 2)
              for k in EFF} for gpu in PRICES},
    "scenarios": {cname: {gpu: estimate(c["tokens"], gpu) for gpu in PRICES}
                  for cname, c in CORPORA.items()},
    "corpora": CORPORA,
    "full_ledger_recommended": {
        "config": "档 B 12.42M tok / L40S-48GB / baseline 吞吐 / 8bit AdamW",
        "stages": LEDGER,
        "total_cny_low": round(lo, 2), "total_cny_high": round(hi, 2),
        "total_cny_budget_cap": 60,
        "wall_clock": {"gpu_hours": round(TRAIN_H + 3.5, 1),
                       "local_eval_hours": 10.2,
                       "note": "GPU 机时 + 环境/补强；本地评测并行不占云机时"},
    },
    "not_included": [
        "从头预训练一个真 10B (200B~1T token)：项目 VIRTU_REAL_MODEL_PLAN 估数十万~数百万 ¥，与本方案不是同一件事",
        "本机 6GB 显存无法完成 1.93B 全参训练，未计入任何本机训练成本",
        "人工标注/语料扩充：当前语料不足以稳妥激活 1.93B 全参，若需扩 10× 语料，成本按 ¥/M token 线性上浮",
        "实际云账单：仓库内无任何账单/发票文件，以上全部为预算估算，不是已发生费用",
    ],
    "basis_warning": "所有 cny 数值均为 design/asserted 估算；measured 的只有：历史训练耗时/token、语料 token 数、模型参数量、云单价截图。真实成本须以跑完后的云账单为准。",
}
result["run_id"] = hashlib.sha256(json.dumps(
    {k: result[k] for k in ("inputs_measured", "flops_model", "scenarios")},
    sort_keys=True).encode()).hexdigest()[:16]

out = os.path.join(ROOT, "benchmarks", "VIRTU_10B_TRAIN_COST.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

# ---------------------------------------------------------------- 打印
print("run_id:", result["run_id"])
print("实测锚点: %s | %d tok / %.1f s = %.1f tok/s" %
      (ANCHOR_CFG, ANCHOR_TOKENS, ANCHOR_SEC, ANCHOR_TOK_S))
print("参数: 总 %d / 冻结 %d / 新增 %d" % (N_TOTAL, N_FROZEN, N_NEW))
print("FLOPs/token: 锚点 %.2f G, 本方案 %.2f G, 比值 %.3f" %
      (F_PER_TOK["anchor_8b_lora_gc"] / 1e9,
       F_PER_TOK["ours_10b_frozen_gc"] / 1e9, RATIO))
print("\n--- 显存 (GiB, 不含激活) ---")
for k, v in CONFIGS.items():
    print("  %-24s %6.2f  %s" % (k, v["mem"]["state_total"], v["label"]))
print("\n--- 三档语料 × 三种卡（L40S 基准口径，实测锚点外推 / FLOPs 交叉）---")
for cname, c in CORPORA.items():
    print("  %-18s %10.2f M tok" % (cname, c["tokens"] / 1e6))
    for gpu in PRICES:
        e = estimate(c["tokens"], gpu)
        print("    %-24s ¥%7.2f / %5.2f h   (FLOPs法 ¥%6.2f / %5.2f h)" %
              (gpu, e["cost_from_measured_anchor"], e["hours_from_measured_anchor"],
               e["cost_from_flops_MFU40"], e["hours_from_flops_MFU40"]))
print("\n--- 完整总账（推荐档 B / L40S）---")
for s in LEDGER:
    print("  ¥%6.2f ~ %6.2f  %-38s [%s]" %
          (s["cny"][0], s["cny"][1], s["stage"], s["basis"]))
print("  " + "-" * 70)
print("  合计 ¥%.2f ~ ¥%.2f   (预算硬上限 ¥60)" % (lo, hi))
print("  墙钟: GPU %.1f h + 本地评测 %.1f h" %
      (result["full_ledger_recommended"]["wall_clock"]["gpu_hours"], 10.2))
print("\n输出:", out)
