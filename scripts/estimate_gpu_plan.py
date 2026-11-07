#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""GPU 选型测算：给定语料档位，算出各种卡能否装下、要多久、花多少钱。

显存模型（保守，宁可高估不过低估）：
  weights    = params * 2                      (bf16)
  lora adamw = P_lora * 8                      (exp_avg + exp_avg_sq, fp32)
  lora grad  = P_lora * 2                      (bf16)
  activations(关ckpt) = L * (34*s*b*h + 5*a*s*s*b)
      来源 Megatron/Korthikanti et al. 的 fp16 激活公式
  logits     = b*s*vocab*6                     (bf16 logits + fp32 CE upcast)

时间模型：
  FLOPs = 4*N*T (关梯度检查点) / 6*N*T (开检查点，多一次重算前向)
  T = FLOPs / (peak_flops * MFU)
"""
import json
import os
import sys

GB = 1024 ** 3

# ---------- Qwen3-8B 架构（读自 checkpoints/_base_qwen3_8b/config.json） ----------
def load_arch(base_dir):
    cfg = json.load(open(os.path.join(base_dir, "config.json"), encoding="utf-8"))
    h = cfg["hidden_size"]; inter = cfg["intermediate_size"]
    L = cfg["num_hidden_layers"]; a = cfg["num_attention_heads"]
    kv = cfg["num_key_value_heads"]; vocab = cfg["vocab_size"]
    return dict(h=h, inter=inter, L=L, a=a, kv=kv, vocab=vocab)

ARCH_DEFAULT = dict(h=4096, inter=12288, L=36, a=32, kv=8, vocab=151936)
PARAMS = 8_190_735_360          # 实测(pytorch-numel)

def lora_params(arch, rank=32, targets=("q", "k", "v", "o", "gate", "up", "down")):
    h, inter = arch["h"], arch["inter"]
    kv_dim = arch["kv"] * 128   # head_dim=128 for Qwen3-8B
    dims = {"q": (h, h), "k": (h, kv_dim), "v": (h, kv_dim), "o": (h, h),
            "gate": (h, inter), "up": (h, inter), "down": (inter, h)}
    total = 0
    for t in targets:
        i, o = dims[t]
        total += rank * (i + o)
    return total * arch["L"]

def vram_estimate(seq, batch, ckpt, arch=ARCH_DEFAULT, rank=32, flash=False):
    h, L, a, vocab = arch["h"], arch["L"], arch["a"], arch["vocab"]
    plora = lora_params(arch, rank)
    weights = PARAMS * 2
    opt = plora * 8
    grad = plora * 2
    if ckpt:
        # 只保留每层边界的输入张量 + 少量中间
        act = L * seq * batch * h * 2 * 2
    else:
        act = L * 34 * seq * batch * h
        if not flash:
            # 朴素注意力要存 attention_scores + softmax：O(s^2)
            # FlashAttention 在线 softmax 消掉了这一项
            act = act + L * 5 * a * seq * seq * batch
    logits = batch * seq * vocab * 6
    total = weights + opt + grad + act + logits
    return {
        "weights": weights, "optimizer": opt, "grad": grad,
        "activations": act, "logits": logits, "total": total,
        "lora_params": plora,
    }

# ---------- GPU 规格 ----------
GPUS = {
    "A800-80G":  dict(vram=80, tflops=312, bw=2039),
    "L40S-48G":  dict(vram=48, tflops=181, bw=864),
    "4090-24G":  dict(vram=24, tflops=165, bw=1008),
    "A6000-48G": dict(vram=48, tflops=155, bw=768),
}

# ---------- 语料档位（实测 token，来自 validate_render_dataset 全量计量） ----------
CORPORA = {
    "原语料":       dict(n=23178, tok=60_272_726, seq=2600),
    "slim":         dict(n=18330, tok=30_163_029, seq=1646),
    "opt1000/ultra":dict(n=5116,  tok=6_840_000,  seq=1337),
    "opt300/ultra": dict(n=2316,  tok=3_140_926,  seq=1356),
    "opt300/none":  dict(n=2316,  tok=1_616_998,  seq=698),
}

def train_hours(tokens, gpu, ckpt, mfu=0.40, n=8e9):
    mult = 6 if ckpt else 4
    flops = mult * n * tokens
    return flops / (gpu["tflops"] * 1e12 * mfu) / 3600

def fmt(x):
    return f"{x/GB:6.2f} GB"

def pick_plan(name, corpus, gpu_name, gpu, safety=0.90, flash=False):
    """为该 GPU 挑一个能装下的最快配置（优先关 ckpt，其次大 batch）。"""
    seq = corpus["seq"]
    cap = gpu["vram"] * GB * safety
    best = None
    for ckpt in (False, True):
        for b in (16, 12, 8, 6, 4, 2, 1):
            v = vram_estimate(seq, b, ckpt, flash=flash)["total"]
            if v <= cap:
                cand = dict(batch=b, ckpt=ckpt, vram=v)
                if best is None:
                    best = cand
                # 关 ckpt 优先；同为关 ckpt 则 batch 大的优先
                better = (not cand["ckpt"] and best["ckpt"]) or \
                         (cand["ckpt"] == best["ckpt"] and cand["batch"] > best["batch"])
                if better:
                    best = cand
                break   # 该 ckpt 档下已取到最大可行 batch
    if best is None:
        return None
    mfu = 0.40 if best["batch"] >= 2 else 0.32   # batch1 kernel 效率低
    h1 = train_hours(corpus["tok"], gpu, best["ckpt"], mfu)
    best.update(mfu=mfu, h_epoch=h1, h2=h1 * 2, seq=seq)
    return best

def main():
    arch = ARCH_DEFAULT
    print("Qwen3-8B 架构:", {k: v for k, v in arch.items()})
    print(f"总参数    : {PARAMS/1e9:.3f} B")
    print(f"LoRA r=32 : {lora_params(arch)/1e6:.2f} M 参数")
    print()

    for flash in (True, False):
        ftag = "启用 FlashAttention" if flash else "朴素注意力 sdpa/eager"
        print("=" * 96)
        print(f"显存需求矩阵（保守估算，GiB；✗ = 超该卡显存 90% 安全线）  ——  {ftag}")
        print("=" * 96)
        hdr = f"{'档位':<16}{'seq':>6}{'b':>3}{'ckpt':>6} | {'权重':>8}{'优化器':>7}{'激活':>9}{'logits':>7}{'合计':>8} | " + "".join(f"{g:>11}" for g in GPUS)
        print(hdr)
        print("-" * len(hdr))
        for cname, c in CORPORA.items():
            seq = c["seq"]
            for ckpt in (False, True):
                for b in (2, 1):
                    v = vram_estimate(seq, b, ckpt, flash=flash)
                    tot = v["total"]
                    marks = []
                    for gname, g in GPUS.items():
                        ok = tot <= g["vram"] * GB * 0.90
                        marks.append(f"{'OK' if ok else '✗':>11}")
                    tag = f"{cname} {'ckpt' if ckpt else 'nocp'}"
                    print(f"{tag:<16}{seq:>6}{b:>3}{str(ckpt):>6} | "
                          f"{v['weights']/GB:>6.2f}G{v['optimizer']/GB:>6.2f}G"
                          f"{v['activations']/GB:>7.2f}G{v['logits']/GB:>6.2f}G{tot/GB:>6.2f}G | "
                          + "".join(marks))
        print()

    for flash in (False, True):
        tag = "FlashAttention" if flash else "朴素注意力 (sdpa/eager)"
        print()
        print("=" * 100)
        print(f"各卡可行配置与时长（2 epoch）  ——  {tag}")
        print("=" * 100)
        print(f"{'档位':<16}{'GPU':<12}{'配置':<22}{'显存':>9}{'MFU':>6}{'2ep(h)':>9}{'相对A800':>10}")
        print("-" * 94)
        results = {}
        for cname, c in CORPORA.items():
            base_h = None
            for gname, g in GPUS.items():
                p = pick_plan(cname, c, gname, g, flash=flash)
                if p is None:
                    print(f"{cname:<16}{gname:<12}{'装不下 / 需降batch或QLoRA':<22}{'-':>9}")
                    continue
                if gname == "A800-80G":
                    base_h = p["h2"]
                # FlashAttention 本身也让计算快 ~10~15%，这里保守不计入
                cfg = f"batch{p['batch']} {'开' if p['ckpt'] else '关'}ckpt"
                results[(cname, gname)] = p
                ratio = ""
                if base_h and gname != "A800-80G":
                    ratio = f"{p['h2']/base_h:.2f}x"
                print(f"{cname:<16}{gname:<12}{cfg:<22}{p['vram']/GB:>7.2f}G{p['mfu']:>6.2f}{p['h2']:>9.2f}{ratio:>10}")
            print("-" * 94)
        key = "gpu_plan_flash.json" if flash else "gpu_plan.json"
        out = {}
        for (cn, gn), p in results.items():
            out[f"{cn}|{gn}"] = dict(batch=p["batch"], ckpt=p["ckpt"],
                                     vram_gb=round(p["vram"]/GB, 2), mfu=p["mfu"],
                                     hours_2ep=round(p["h2"], 3))
        os.makedirs("data/validation", exist_ok=True)
        json.dump(out, open(f"data/validation/{key}", "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        print(f"已保存 data/validation/{key}")

if __name__ == "__main__":
    main()
