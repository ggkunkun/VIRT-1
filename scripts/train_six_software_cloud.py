#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
train_six_software_cloud.py — 六软件 tool-call 语料的云端训练脚本

数据源：D:/Virtu模型/knowledge_base/six_software/training/datasets/
  12 个 OpenAI function-calling JSONL（每软件 train + holdout），
  格式契约见 training/TRAINING_CONTRACT.md（tools+messages、tool_calls 带 id/function、
  arguments=JSON 字符串、tool 回执角色）。

设计原则（沿用既有权威实现，不重复造轮子）：
  - 掩码：统一走 scripts/virtu_tokenize.py 的 build_example
    （整条渲染 -> 字符定位 assistant 段 -> offset_mapping 映射 token；
     system/user/tool 段一律 -100，防止模型学会伪造工具返回值）
  - 模板：Qwen3 官方 tokenizer.apply_chat_template(tools=...)，训练/推理序列化一致
  - LoRA：r=32 / alpha=64 / 全 attn+MLP target_modules，
    与仓库既有 4 个 r=32 LoRA 兼容，可 add_weighted_adapter(linear) 合并
  - 容错：逐行 json.loads 体检，坏行【跳过并落盘清单】，好行全部入训；
    --strict 时坏行 FATAL（用于数据已修复后的权威门禁）

云端执行（GPU 机，L40S 48GB / A800 80GB 均可）：
  1) 打包：把本脚本 + virtu_tokenize.py + datasets/ 12 个 JSONL 传到 GPU 机工作目录
  2) 装依赖：pip install -U "transformers>=4.51" "peft>=0.14" "accelerate>=0.34"
             "datasets>=3.0" "bitsandbytes>=0.44" modelscope
  3) 下载基座（放数据盘，先 df -h 确认挂载点）：
     python scripts/download_base_modelscope.py /root/virtu_train/Qwen3-8B
  4) 冒烟（限 20 条跑通全流程，约 3 分钟）：
     python scripts/train_six_software_cloud.py --data-dir <datasets 目录> \
         --base /root/virtu_train/Qwen3-8B --out /root/virtu_train/lora_six \
         --smoke 20 --epochs 1 --yes
  5) 全量：
     python scripts/train_six_software_cloud.py --data-dir <datasets 目录> \
         --base /root/virtu_train/Qwen3-8B --out /root/virtu_train/lora_six \
         --epochs 2 --batch 2 --grad-accum 4 --no-grad-ckpt --min-vram-gb 60
  6) 拉回：整目录拷回 D:/Virtu模型/checkpoints/lora_six_software/，
     用 training_receipt.json 与 bad_lines_manifest.json 核对。

时长估算（参考 TOOLCALL_TRAINING_RUNBOOK.md 实测基线反推，语料 ~221 条×2ep 是分钟级）：
  - L40S 48GB QLoRA 2ep ≈ 6~12 分钟（221 条，max_len 4096）
  - A800 80GB 关梯度检查点 ≈ 4~8 分钟
  - 环境/下载/调试固定开销 10~25 分钟另计

用法（本地无 torch 也能 --help；--probe-only / --validate-only 不加载模型）：
  python scripts/train_six_software_cloud.py --base <base> --data-dir <dir> --help
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from virtu_tokenize import build_example  # noqa: E402  (掩码权威实现)

DEFAULT_DATA_DIR = r"D:/Virtu模型/knowledge_base/six_software/training/datasets"


def _pre_argv() -> None:
    """在 import torch 前处理设备选择（CUDA_VISIBLE_DEVICES 必须早于 CUDA 初始化）。"""
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
    p = argparse.ArgumentParser(description="六软件 tool-call 语料云端训练（Qwen3 官方 chat template + LoRA/QLoRA）")
    p.add_argument("--base", required=True, help="Qwen3-8B 基座目录（与 LoRA 同源）")
    p.add_argument("--data-dir", default=DEFAULT_DATA_DIR,
                   help="datasets 目录，内含 *_train.jsonl / *_holdout.jsonl 12 个文件")
    p.add_argument("--out", default=os.path.join(HERE, "..", "checkpoints", "lora_six_software"))
    p.add_argument("--mode", default="qlora", choices=["qlora", "lora"])
    p.add_argument("--epochs", type=float, default=2.0)
    p.add_argument("--batch", type=int, default=2)
    p.add_argument("--grad-accum", type=int, default=4)
    p.add_argument("--max-length", type=int, default=4096)
    p.add_argument("--lr", type=float, default=1e-4)
    p.add_argument("--lora-r", type=int, default=32)
    p.add_argument("--lora-alpha", type=int, default=64)
    p.add_argument("--lora-dropout", type=float, default=0.05)
    p.add_argument("--limit", type=int, default=0, help="每个文件最多取前 N 条（0=全部）")
    p.add_argument("--smoke", type=int, default=0, help="全局冒烟条数（≤N 条跑通全流程，0=关）")
    p.add_argument("--strict", action="store_true",
                   help="体检发现坏 JSON 行即 FATAL（数据已修复后的权威门禁）；默认跳过坏行并落盘清单")
    p.add_argument("--no-grad-ckpt", action="store_true",
                   help="关闭梯度检查点（A800/80GB 等大显存卡可省约 25 个百分点计算量）")
    p.add_argument("--min-vram-gb", type=float, default=0.0,
                   help="启动前校验可用显存不低于该值（GB），不足退出")
    p.add_argument("--probe-only", action="store_true", help="只做模板探针并退出，不加载模型")
    p.add_argument("--validate-only", action="store_true", help="只做数据体检并退出，不加载模型")
    p.add_argument("--eval-holdout", action="store_true",
                   help="训练结束后对 holdout 计算 loss（只评测不入训）")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--group-by-length", action="store_true", help="按长度分桶组 batch")
    p.add_argument("--attn-impl", default="", choices=["", "flash_attention_2", "sdpa"],
                   help="注意力实现，默认优先 flash_attention_2（未安装自动降级 sdpa）")
    p.add_argument("--max-steps", type=int, default=0, help="限制总优化步数（0=不限）")
    p.add_argument("--time-budget-min", type=float, default=0.0,
                   help="训练时间预算（分钟）；到点优雅停止并保存 LoRA，0=不限")
    return p.parse_args()


# ---------------------------------------------------------------- 数据层
def scan_files(data_dir, split):
    """返回 (data_dir, split) 下全部 *_<split>.jsonl 的排序文件列表。"""
    pat = os.path.join(data_dir, f"*_{split}.jsonl")
    files = sorted(glob.glob(pat))
    return files


def load_and_tokenize(data_dir, split, tokenizer, max_length, limit=0, strict=False):
    """逐文件逐行加载 -> json.loads -> build_example。
    返回 (records, bad_manifest, n_trunc, tok_total, loss_total)。
    bad_manifest: [{"file", "line", "error"}]，坏行不入训。
    """
    files = scan_files(data_dir, split)
    if not files:
        raise SystemExit(f"[FATAL] {data_dir} 下未找到 *_ {split}.jsonl")
    records, bad, n_trunc = [], [], 0
    tok_total = loss_total = 0
    for fp in files:
        base = os.path.basename(fp)
        with open(fp, encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                if not line.strip():
                    continue
                try:
                    r = json.loads(line)
                except Exception as e:
                    bad.append({"file": base, "line": lineno, "error": str(e)[:160]})
                    if strict:
                        raise SystemExit(f"[FATAL][{base}:{lineno}] 坏 JSON 行: {e}")
                    continue
                try:
                    ids, labels, meta = build_example(
                        r["messages"], r.get("tools") or [], tokenizer, max_length)
                except Exception as e:
                    bad.append({"file": base, "line": lineno, "error": f"build_example: {e}"})
                    if strict:
                        raise SystemExit(f"[FATAL][{base}:{lineno}] build_example 失败: {e}")
                    continue
                if not ids:
                    continue
                if meta["truncated"]:
                    n_trunc += 1
                records.append({"input_ids": ids, "labels": labels,
                                "attention_mask": [1] * len(ids)})
                tok_total += meta["n_tok"]
                loss_total += meta["n_loss"]
                if limit and len(records) >= limit:
                    break
    return records, bad, n_trunc, tok_total, loss_total


def summarize_split(name, records, bad, n_trunc, tok_total, loss_total):
    n_loss = sum(1 for d in records for x in d["labels"] if x != -100)
    n_tok = sum(len(d["input_ids"]) for d in records)
    print(f"[data][{name}] 有效 {len(records)} 条 | token {n_tok:,} | 计loss {n_loss:,} "
          f"({n_loss/max(1,n_tok)*100:.1f}%) | 截断 {n_trunc} | 坏行 {len(bad)}")
    return {"name": name, "records": len(records), "tokens": n_tok, "loss_tokens": n_loss,
            "truncated": n_trunc, "bad_lines": len(bad)}


# ---------------------------------------------------------------- 探针/体检
def probe_template(tokenizer, data_dir):
    files = scan_files(data_dir, "train")
    if not files:
        raise SystemExit(f"[FATAL] 探针需要至少一个 *_train.jsonl: {data_dir}")
    with open(files[0], encoding="utf-8") as f:
        for line in f:
            if line.strip():
                sample = json.loads(line)
                break
    text = tokenizer.apply_chat_template(
        sample["messages"], tools=sample.get("tools") or [],
        tokenize=False, add_generation_prompt=False)
    print("[probe] 渲染长度:", len(text), "字符")
    print("[probe] 前 700 字符:\n" + text[:700])
    has_tools = ("<tools>" in text) or ("tool_call" in text)
    has_name = any(t["function"]["name"] in text for t in sample.get("tools", []))
    if not (has_tools and has_name):
        print("[probe][WARN] 模板可能未渲染 tools / tool_calls 段。退路："
              "手写 ChatML（tools 塞 system、tool_calls 序列化 <tool_call>{json}</tool_call>），"
              "并确保训练/推理两侧同一序列化。")
    else:
        print("[probe][OK] Qwen3 chat template 已正确渲染 tools 与 tool_calls 段。")
    return text


def dump_bad_manifest(out_dir, bad):
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "bad_lines_manifest.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(bad, f, ensure_ascii=False, indent=2)
    print(f"[data] 坏行清单 -> {path}（共 {len(bad)} 行，均未入训）")
    return path


# ---------------------------------------------------------------- 训练
def main() -> None:
    args = parse_args()
    if not os.path.isdir(args.data_dir):
        raise SystemExit(f"[FATAL] 数据目录不存在: {args.data_dir}")

    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(args.base, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    probe_template(tokenizer, args.data_dir)
    if args.probe_only:
        print("[probe-only] 探针完成，退出（未加载模型）。")
        return

    # ---- 训练集 tokenize ----
    limit = args.limit
    if args.smoke:
        limit = args.smoke
        print(f"[smoke] 全局冒烟：最多 {args.smoke} 条")
    train_records, train_bad, n_trunc_t, tok_t, loss_t = load_and_tokenize(
        args.data_dir, "train", tokenizer, args.max_length, limit, args.strict)
    train_sum = summarize_split("train", train_records, train_bad, n_trunc_t, tok_t, loss_t)

    # ---- holdout 只评测不入训（若目录有且用户要）----
    holdout_sum = None
    holdout_records = None
    if args.eval_holdout:
        hold_files = scan_files(args.data_dir, "holdout")
        if hold_files:
            hr, hbad, hn_t, htok, hloss = load_and_tokenize(
                args.data_dir, "holdout", tokenizer, args.max_length, args.limit, args.strict)
            holdout_sum = summarize_split("holdout", hr, hbad, hn_t, htok, hloss)
            holdout_records = hr

    if args.validate_only:
        print("[validate-only] 数据体检完成（未加载模型）。")
        return

    import torch
    from datasets import Dataset
    from peft import LoraConfig, get_peft_model, TaskType, prepare_model_for_kbit_training
    from transformers import (AutoModelForCausalLM, TrainingArguments, Trainer,
                              DataCollatorForSeq2Seq, BitsAndBytesConfig,
                              TrainerCallback)

    torch.manual_seed(args.seed)
    if not torch.cuda.is_available():
        raise SystemExit("[FATAL] 无 CUDA 设备。本脚本需要 GPU（或用远程 GPU 机）。")

    free_b, total_b = torch.cuda.mem_get_info()
    free_gb, total_gb = free_b / 1e9, total_b / 1e9
    print(f"[train] 显存: 总量 {total_gb:.1f} GB | 可用 {free_gb:.1f} GB")
    if args.min_vram_gb and free_gb < args.min_vram_gb:
        raise SystemExit(f"[FATAL] 可用显存 {free_gb:.1f}GB < 要求的 {args.min_vram_gb}GB。")
    need = 20 if args.mode == "qlora" else 40
    if free_gb < need:
        print(f"[WARN] 可用显存 {free_gb:.1f}GB 偏紧（建议 ≥{need}GB）。可 --no-grad-ckpt 或减 --batch。")

    use_ckpt = not args.no_grad_ckpt
    kw = {}
    impl = args.attn_impl or "flash_attention_2"
    if impl == "flash_attention_2":
        try:
            import flash_attn  # noqa: F401
            kw["attn_implementation"] = "flash_attention_2"
            print("[train] 注意力实现: flash_attention_2")
        except ImportError:
            kw["attn_implementation"] = "sdpa"
            print("[WARN] 未安装 flash-attn，降级 sdpa。注意激活 O(s^2)，可调低 batch 或开梯度检查点。")
    elif impl != "":
        kw["attn_implementation"] = impl
        print(f"[train] 注意力实现: {impl}")

    if args.mode == "qlora":
        bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                 bnb_4bit_compute_dtype=torch.bfloat16,
                                 bnb_4bit_use_double_quant=True)
        model = AutoModelForCausalLM.from_pretrained(
            args.base, quantization_config=bnb, device_map={"": 0},
            torch_dtype=torch.bfloat16, trust_remote_code=True, **kw)
        model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=use_ckpt)
    else:
        model = AutoModelForCausalLM.from_pretrained(
            args.base, torch_dtype=torch.bfloat16, device_map={"": 0},
            trust_remote_code=True, **kw)
    model.config.use_cache = False
    if use_ckpt:
        model.enable_input_require_grads()
    print(f"[train] 梯度检查点: {'开启' if use_ckpt else '关闭（省 ~25% 计算量）'}")

    lora = LoraConfig(
        r=args.lora_r, lora_alpha=args.lora_alpha, lora_dropout=args.lora_dropout,
        bias="none",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
        task_type=TaskType.CAUSAL_LM,
    )
    model = get_peft_model(model, lora)
    model.print_trainable_parameters()

    if not train_records:
        raise SystemExit("[FATAL] 训练集 0 条有效样本（可能全部坏行被跳过）。")
    ds = Dataset.from_list(train_records)
    n_loss = sum(1 for d in train_records for x in d["labels"] if x != -100)
    n_tok = sum(len(d["input_ids"]) for d in train_records)
    print(f"[train] 有效样本 {len(train_records)} 条 | token {n_tok:,} | 计loss {n_loss:,} "
          f"({n_loss/max(1,n_tok)*100:.1f}%)")

    os.makedirs(args.out, exist_ok=True)
    if args.group_by_length:
        for d in train_records:
            d["length"] = len(d["input_ids"])
    targs = TrainingArguments(
        output_dir=args.out, num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch, gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr, lr_scheduler_type="cosine", warmup_steps=15,
        logging_steps=10, save_strategy="epoch", bf16=True,
        gradient_checkpointing=use_ckpt, max_grad_norm=1.0,
        group_by_length=args.group_by_length,
        length_column_name="length" if args.group_by_length else "length",
        remove_unused_columns=False, report_to="none", seed=args.seed,
        max_steps=args.max_steps if args.max_steps > 0 else -1,
    )

    class TimeBudgetCallback(TrainerCallback):
        def __init__(self, minutes):
            self.deadline = time.time() + minutes * 60
            self.tripped = False

        def on_step_end(self, a, state, control, **kw):
            if self.tripped or time.time() < self.deadline:
                return control
            self.tripped = True
            print("[train][TIME-BUDGET] 到达时间预算，停止训练并保存 LoRA")
            control.should_training_stop = True
            control.should_save = True
            return control

        def on_train_end(self, a, state, control, **kw):
            return control

    cb = []
    if args.time_budget_min > 0:
        cb.append(TimeBudgetCallback(args.time_budget_min))
        print(f"[train] 时间预算: {args.time_budget_min} 分钟")

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

    # ---- holdout 评测（可选）----
    eval_loss = None
    if args.eval_holdout and holdout_records:
        hds = Dataset.from_list(holdout_records)
        try:
            ev = trainer.evaluate(eval_dataset=hds)
            eval_loss = float(ev.get("eval_loss"))
            print(f"[eval][holdout] eval_loss = {eval_loss:.4f}")
        except Exception as e:
            print(f"[WARN] holdout 评测失败: {e}")

    bad_path = dump_bad_manifest(args.out, train_bad + ([] if not args.eval_holdout else []))

    receipt = {
        "status": "COMPLETED",
        "task": "six_software tool-call LoRA (OpenAI function-calling)",
        "base_model": args.base, "data_dir": args.data_dir, "output_dir": args.out,
        "epochs": args.epochs, "mode": args.mode,
        "lora_r": args.lora_r, "lora_alpha": args.lora_alpha, "lora_dropout": args.lora_dropout,
        "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj",
                           "gate_proj", "up_proj", "down_proj"],
        "max_length": args.max_length, "batch": args.batch, "grad_accum": args.grad_accum,
        "lr": args.lr, "seed": args.seed, "gradient_checkpointing": use_ckpt,
        "group_by_length": args.group_by_length, "attn_impl": impl,
        "max_steps": args.max_steps, "time_budget_min": args.time_budget_min,
        "time_budget_tripped": bool(cb and cb[0].tripped) if cb else False,
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "vram_total_gb": round(total_gb, 1), "runtime_seconds": runtime_s,
        "train_stats": train_sum,
        "holdout_stats": holdout_sum,
        "holdout_eval_loss": eval_loss,
        "bad_lines_manifest": bad_path,
        "train_loss": float(train_result.training_loss) if hasattr(train_result, "training_loss") else None,
        "chat_template": "official_apply_chat_template",
        "mask_impl": "scripts/virtu_tokenize.py (整条渲染+字符定位+offset_mapping)",
        "merge_hint": "r=32/alpha=64 与既有 LoRA 一致，可 add_weighted_adapter(linear) 合并；"
                      "语料契约见 training/TRAINING_CONTRACT.md",
    }
    with open(os.path.join(args.out, "training_receipt.json"), "w", encoding="utf-8") as f:
        json.dump(receipt, f, ensure_ascii=False, indent=2)
    print(f"[train] 完成 -> {args.out}（receipt: training_receipt.json）")


if __name__ == "__main__":
    _pre_argv()
    main()
