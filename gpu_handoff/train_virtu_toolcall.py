#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
train_virtu_toolcall.py — Virtu wish/tool-call 语料的标准训练脚本（推荐）

与旧 scripts/train_tool_agent.py 的区别：
  - 用 Qwen3 官方 tokenizer.apply_chat_template(tools=...) 渲染，训练/推理序列化一致
    （旧脚本是手写 ChatML，需推理侧配套手写解析器）
  - 训练前做模板探针，模板不认 tools 时明确告警并给出退路
  - CLI 参数化路径，支持 QLoRA(4bit) / bf16-LoRA，支持 --single-gpu
  - 依赖全部延迟导入，本机无 torch 也能 --help；py_compile 可独立校验

逐轮 loss mask：仅 assistant 段（含 tool_calls）计 loss，
system / user / tool 段一律 -100（防止模型学会伪造工具返回值）。

【重要】掩码构造不在本文件内实现，统一由 scripts/virtu_tokenize.py 提供。
原因：Qwen3 官方模板有两条隐藏规则，使"逐消息前缀对齐"做法必然错位——
  L42: {%- if loop.index0 > ns.last_query_index %}
       只有最后一个 user 之后的 assistant 段才带 <think> 包裹
  同一条 assistant 消息单独渲染 vs 作为前缀渲染结果不同
  => template(messages[:i+1]).startswith(template(messages[:i])) 不成立
正确做法：整条渲染 -> 字符级定位 assistant 段 -> offset mapping 映射到 token。

用法（GPU 机）:
  python scripts/train_virtu_toolcall.py --base /root/models/Qwen3-8B \
      --data damodel_cad_cam_tuning/dataset/virtu_toolcall_train_unified.jsonl \
      --mode qlora --epochs 3 --single-gpu
  python scripts/train_virtu_toolcall.py --base ... --probe-only   # 只验证 chat template
  python scripts/train_virtu_toolcall.py --base ... --validate-only  # 只做数据体检
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from virtu_tokenize import build_example, decode_loss_segments  # noqa: E402


def _pre_argv() -> None:
    """在 import torch 之前处理设备选择（CUDA_VISIBLE_DEVICES 必须早于 CUDA 初始化）。"""
    if "--single-gpu" in sys.argv:
        os.environ["CUDA_VISIBLE_DEVICES"] = "0"
        sys.argv.remove("--single-gpu")
        print("[argv] --single-gpu -> CUDA_VISIBLE_DEVICES=0")
    if "--gpu-id" in sys.argv:
        i = sys.argv.index("--gpu-id")
        if i + 1 < len(sys.argv):
            os.environ["CUDA_VISIBLE_DEVICES"] = sys.argv[i + 1]
            print(f"[argv] --gpu-id -> CUDA_VISIBLE_DEVICES={sys.argv[i + 1]}")
            del sys.argv[i:i + 2]


def parse_args():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    p = argparse.ArgumentParser(description="Virtu wish/tool-call Agent 训练（官方 chat template）")
    p.add_argument("--base", required=True, help="Qwen3-8B 基座目录（与 LoRA 同源）")
    p.add_argument("--data", default=os.path.join(here, "damodel_cad_cam_tuning", "dataset",
                                                  "virtu_toolcall_train_unified.jsonl"))
    p.add_argument("--out", default=os.path.join(here, "checkpoints", "virtu_toolcall_lora"))
    p.add_argument("--mode", default="qlora", choices=["qlora", "lora"])
    p.add_argument("--epochs", type=float, default=3.0)
    p.add_argument("--batch", type=int, default=2)
    p.add_argument("--grad-accum", type=int, default=4)
    p.add_argument("--max-length", type=int, default=4096)
    p.add_argument("--lr", type=float, default=1e-4)
    # LoRA 超参：必须与已合并的 4 个 r=32 LoRA 一致，
    # 否则 peft add_weighted_adapter(linear) 会因 rank 不匹配而无法合并
    # （历史教训：tool_agent_lora_final 是 r=16，被排除在合并之外）
    p.add_argument("--lora-r", type=int, default=32)
    p.add_argument("--lora-alpha", type=int, default=64)
    p.add_argument("--lora-dropout", type=float, default=0.05)
    p.add_argument("--limit", type=int, default=0, help="只训练前 N 条（0=全部），用于冒烟")
    p.add_argument("--no-grad-ckpt", action="store_true",
                   help="关闭梯度检查点（A800/80GB 等大显存卡可省 ~25%% 计算量）")
    p.add_argument("--auto-batch", action="store_true",
                   help="按实测可用显存自动选 batch size（大显存卡用）")
    p.add_argument("--min-vram-gb", type=float, default=0.0,
                   help="启动前校验可用显存不低于该值（GB），不足则退出，避免 OOM 浪费时间")
    p.add_argument("--probe-only", action="store_true", help="只做模板探针并退出，不加载模型")
    p.add_argument("--validate-only", action="store_true", help="只做数据体检并退出，不加载模型")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--group-by-length", action="store_true",
                   help="按长度分桶组 batch（实测 padding 浪费 4.9%% -> 0.06%%）")
    p.add_argument("--attn-impl", default="", choices=["", "flash_attention_2", "sdpa"],
                   help="注意力实现，默认 flash_attention_2（未安装则自动降级 sdpa）。"
                        "FA 把注意力激活从 O(s^2) 降到 O(s)，显存允许 batch 翻倍，强烈建议开启")
    p.add_argument("--max-steps", type=int, default=0,
                   help="限制总优化步数（0=不限）；用于超时时强制收敛")
    p.add_argument("--time-budget-min", type=float, default=0.0,
                   help="训练时间预算（分钟）；到达即优雅停止并保存 LoRA，0=不限")
    return p.parse_args()


def probe_template(tokenizer, data_path):
    with open(data_path, encoding="utf-8") as f:
        sample = json.loads(f.readline())
    text = tokenizer.apply_chat_template(
        sample["messages"], tools=sample.get("tools") or [],
        tokenize=False, add_generation_prompt=False)
    print("[probe] 渲染长度:", len(text), "字符")
    print("[probe] 前 700 字符:\n" + text[:700])
    has_tools = ("<tools>" in text) or ("tool_call" in text)
    has_name = any(t["function"]["name"] in text for t in sample.get("tools", []))
    if not (has_tools and has_name):
        print("[probe][WARN] 模板可能未渲染 tools / tool_calls 段。退路："
              "换用 scripts/train_tool_agent.py（手写 ChatML，已把 tools 塞进 system），"
              "并确保推理侧用同一套序列化。")
    else:
        print("[probe][OK] Qwen3 chat template 已正确渲染 tools 与 tool_calls 段。")
    return text


def validate_data(tokenizer, data_path, limit=0):
    """数据体检：不加载模型，用官方 template 全量渲染并校验掩码。"""
    n = 0
    n_loss_total = 0
    tok_total = 0
    bad = []
    with open(data_path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            if limit and n >= limit:
                break
            r = json.loads(line)
            try:
                ids, labels, meta = build_example(
                    r["messages"], r.get("tools") or [], tokenizer, 4096)
            except Exception as e:
                bad.append((n, str(e)))
                n += 1
                continue
            n_loss_total += meta["n_loss"]
            tok_total += meta["n_tok"]
            n += 1
    print(f"[validate] {n} 条 | token {tok_total:,} | loss token {n_loss_total:,} "
          f"({n_loss_total/max(1,tok_total)*100:.1f}%) | 失败 {len(bad)}")
    for i, e in bad[:5]:
        print(f"   #{i} {e}")
    if bad:
        raise SystemExit("[FATAL] 数据体检未通过，终止训练")
    return n, tok_total, n_loss_total


def main() -> None:
    args = parse_args()
    if not os.path.exists(args.data):
        raise SystemExit(f"[FATAL] 数据集不存在: {args.data}")

    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(args.base, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    probe_template(tokenizer, args.data)
    if args.probe_only:
        print("[probe-only] 探针完成，退出（未加载模型）。")
        return

    if args.validate_only:
        validate_data(tokenizer, args.data, args.limit)
        print("[validate-only] 数据体检通过，退出（未加载模型）。")
        return

    import torch
    from datasets import Dataset
    from peft import LoraConfig, get_peft_model, TaskType, prepare_model_for_kbit_training
    from transformers import (AutoModelForCausalLM, TrainingArguments, Trainer,
                              DataCollatorForSeq2Seq, BitsAndBytesConfig,
                              TrainerCallback)

    torch.manual_seed(args.seed)

    print(f"[train] 基座={args.base} 模式={args.mode} 设备={'cuda' if torch.cuda.is_available() else 'cpu'}")
    if not torch.cuda.is_available():
        raise SystemExit("[FATAL] 无 CUDA 设备。本脚本需要 GPU（或用远程 GPU 机）。")

    # ---- 显存体检：不足则早退，别让机器空烧几小时 ----
    free_b, total_b = torch.cuda.mem_get_info()
    free_gb, total_gb = free_b / 1e9, total_b / 1e9
    print(f"[train] 显存: 总量 {total_gb:.1f} GB | 可用 {free_gb:.1f} GB")
    if args.min_vram_gb and free_gb < args.min_vram_gb:
        raise SystemExit(f"[FATAL] 可用显存 {free_gb:.1f}GB < 要求的 {args.min_vram_gb}GB。"
                         f"请换卡或先用 --limit 试点。")
    # bf16 基座权重本身就要 ~16GB；4bit 约 ~5GB
    need = 20 if args.mode == "qlora" else 40
    if free_gb < need:
        print(f"[WARN] 可用显存 {free_gb:.1f}GB 偏紧（建议 ≥{need}GB）。"
              f"建议加 --no-grad-ckpt 或减小 --batch，否则可能 OOM。")

    use_ckpt = not args.no_grad_ckpt
    kw = {}
    # FlashAttention 不只是"快一点"：朴素注意力的激活是 O(s^2)，
    # 换成 FA 后该项被消掉，同样显存下 batch 可翻倍（L40S 48GB 上 1->2），
    # 直接决定能否关闭梯度检查点。故默认开启，装不了才降级。
    impl = args.attn_impl or "flash_attention_2"
    if impl == "flash_attention_2":
        try:
            import flash_attn  # noqa: F401
            kw["attn_implementation"] = "flash_attention_2"
            print("[train] 注意力实现: flash_attention_2 (激活 O(s) 显存)")
        except ImportError:
            kw["attn_implementation"] = "sdpa"
            print("[WARN] 未安装 flash-attn，降级到 sdpa。"
                  "朴素注意力激活为 O(s^2)，请下调 --batch 或开启梯度检查点，否则可能 OOM。")
            print("       修复: pip install flash-attn --no-build-isolation")
    elif impl != "":
        kw["attn_implementation"] = impl
        print(f"[train] 注意力实现: {impl}")
    if args.mode == "qlora":
        bnb = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
        model = AutoModelForCausalLM.from_pretrained(
            args.base, quantization_config=bnb, device_map={"": 0},
            torch_dtype=torch.bfloat16, trust_remote_code=True, **kw)
        model = prepare_model_for_kbit_training(
            model, use_gradient_checkpointing=use_ckpt)
    else:
        model = AutoModelForCausalLM.from_pretrained(
            args.base, torch_dtype=torch.bfloat16, device_map={"": 0},
            trust_remote_code=True, **kw)
    model.config.use_cache = False
    if use_ckpt:
        model.enable_input_require_grads()
    print(f"[train] 梯度检查点: {'开启' if use_ckpt else '关闭（省 ~25% 计算量）'}")

    lora = LoraConfig(
        r=args.lora_r, lora_alpha=args.lora_alpha, lora_dropout=args.lora_dropout, bias="none",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
        task_type=TaskType.CAUSAL_LM,
    )
    model = get_peft_model(model, lora)
    model.print_trainable_parameters()

    data = []
    n_trunc = 0
    with open(args.data, encoding="utf-8") as f:
        for idx, line in enumerate(f):
            if not line.strip():
                continue
            if args.limit and len(data) >= args.limit:
                break
            r = json.loads(line)
            ids, labels, meta = build_example(
                r["messages"], r.get("tools") or [], tokenizer, args.max_length)
            if not ids:
                continue
            if meta["truncated"]:
                n_trunc += 1
            data.append({"input_ids": ids, "labels": labels, "attention_mask": [1] * len(ids)})
            if (idx + 1) % 5000 == 0:
                print(f"[train] tokenized {idx + 1} ...", flush=True)
    ds = Dataset.from_list(data)
    n_loss = sum(1 for d in data for x in d["labels"] if x != -100)
    n_tok = sum(len(d["input_ids"]) for d in data)
    print(f"[train] 有效样本 {len(data)} 条 | token {n_tok:,} | 计 loss {n_loss:,} "
          f"({n_loss/max(1,n_tok)*100:.1f}%) | 截断 {n_trunc}")

    # 抽样打印计 loss 段，人工确认掩码落在正确位置
    if data:
        segs = decode_loss_segments(tokenizer, data[0]["input_ids"], data[0]["labels"], limit=2)
        for i, s in enumerate(segs):
            print(f"[train][样本0] 计loss段{i}: {s[:200]!r}")

    os.makedirs(args.out, exist_ok=True)
    # group_by_length 需要数据集带 length 列（Trainer 用它分桶，减少 padding 浪费）
    if args.group_by_length:
        for d in data:
            d["length"] = len(d["input_ids"])
    targs = TrainingArguments(
        output_dir=args.out, num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch, gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr, lr_scheduler_type="cosine", warmup_steps=15,
        logging_steps=10, save_strategy="epoch", bf16=True,
        gradient_checkpointing=use_ckpt,
        max_grad_norm=1.0,
        group_by_length=args.group_by_length,
        length_column_name="length" if args.group_by_length else "length",
        remove_unused_columns=False, report_to="none",
        seed=args.seed,
        max_steps=args.max_steps if args.max_steps > 0 else -1,
    )

    class TimeBudgetCallback(TrainerCallback):
        """到达时间预算即优雅停止并保存 LoRA，避免云实例空烧钱。

        必须继承 TrainerCallback：Trainer 会对每个事件 getattr(callback, event) 后直接调用，
        裸类缺方法会抛 AttributeError（transformers 4.51 实测）。
        """
        def __init__(self, minutes):
            self.deadline = time.time() + minutes * 60
            self.tripped = False

        def on_step_end(self, a, state, control, **kw):
            if self.tripped or time.time() < self.deadline:
                return control
            self.tripped = True
            print(f"[train][TIME-BUDGET] 到达 {a.max_steps and ''}时间预算，停止训练并保存 LoRA")
            control.should_training_stop = True
            control.should_save = True
            return control

        def on_train_end(self, a, state, control, **kw):
            return control

    cb = []
    if args.time_budget_min > 0:
        cb.append(TimeBudgetCallback(args.time_budget_min))
        print(f"[train] 时间预算: {args.time_budget_min} 分钟，到点自动保存停止")

    trainer = Trainer(
        model=model, args=targs, train_dataset=ds,
        data_collator=DataCollatorForSeq2Seq(tokenizer, padding=True, label_pad_token_id=-100),
        callbacks=cb,
    )
    train_result = trainer.train()
    runtime_s = None
    try:
        runtime_s = float(train_result.metrics.get("train_runtime", 0)) or None
    except Exception:
        pass
    model.save_pretrained(args.out)
    tokenizer.save_pretrained(args.out)

    receipt = {
        "status": "COMPLETED", "base_model": args.base, "dataset": args.data,
        "samples": len(data), "epochs": args.epochs, "mode": args.mode,
        "lora_r": args.lora_r, "lora_alpha": args.lora_alpha,
        "lora_dropout": args.lora_dropout,
        "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj",
                           "gate_proj", "up_proj", "down_proj"],
        "max_length": args.max_length, "batch": args.batch, "grad_accum": args.grad_accum,
        "lr": args.lr, "seed": args.seed,
        "gradient_checkpointing": use_ckpt,
        "group_by_length": args.group_by_length,
        "attn_impl": args.attn_impl or "default",
        "max_steps": args.max_steps,
        "time_budget_min": args.time_budget_min,
        "time_budget_tripped": bool(cb and cb[0].tripped) if cb else False,
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "vram_total_gb": round(total_gb, 1),
        "runtime_seconds": runtime_s,
        "total_tokens": n_tok, "loss_tokens": n_loss,
        "truncated_samples": n_trunc,
        "train_loss": float(train_result.training_loss) if hasattr(train_result, "training_loss") else None,
        "output_dir": args.out,
        "chat_template": "official_apply_chat_template",
        "mask_impl": "scripts/virtu_tokenize.py (整条渲染+字符定位+offset_mapping)",
        "merge_hint": "r 必须与既有 LoRA 一致(r=32/alpha=64)才能 add_weighted_adapter(linear) 合并",
    }
    with open(os.path.join(args.out, "training_receipt.json"), "w", encoding="utf-8") as f:
        json.dump(receipt, f, ensure_ascii=False, indent=2)
    print(f"[train] 完成 -> {args.out}")


if __name__ == "__main__":
    _pre_argv()
    main()
