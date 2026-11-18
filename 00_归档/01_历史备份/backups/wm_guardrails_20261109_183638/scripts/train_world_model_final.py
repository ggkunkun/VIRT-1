#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Virtu 世界模型 · 最终版训练脚本（自主思考 / 自主决策）
================================================================================
一条命令完成：建数据 -> 合并 -> 自检 -> 多轮智能体轨迹 SFT -> 保存 adapter。

训练目标（"自主思考、自主决策"的可训练定义）：
  多轮轨迹： user(任务)
            -> assistant{think, plan, action{tool,args}}     # 自主思考+决策
            -> tool{ok,result}                               # 真实求解器观测
            -> assistant{think, verify, action{finalize}}    # 自检
            -> tool{ok}
            -> assistant{world_state/design, decision}       # 定稿
  训练器只对 assistant 段算 loss，tool 段全 mask —— 模型学的是"怎么想、选什么工具、
  怎么校验、怎么定稿"，而不是背答案。

数据来源（自动合并）：
  * data/sft/virtu_worldmodel_v2.jsonl  物理世界状态 + 设计 + 工艺 + 陌生环境适配 + 自纠错
  * data/sft/virtu_agentic.jsonl        六类多轮智能体轨迹（含单位错误自恢复）
  * data/sft/virtu_v3_patch.jsonl       工具调用格式 replay（防遗忘，可用 --no-replay 关闭）

用法：
  # 0) 本地只自检（只加载 tokenizer，不训练、不占显存）
  python scripts/train_world_model_final.py --selftest

  # 1) 生成/合并数据 + 自检
  python scripts/train_world_model_final.py --build --selftest

  # 2) 云端正式训练（在 v3 adapter 上续训，继承已有能力）
  python scripts/train_world_model_final.py \
      --base /root/public-storage/model/Qwen/Qwen3-8B \
      --resume-adapter checkpoints/virtu_v3_all90 \
      --out checkpoints/virtu_wm_auto --epochs 3 --lr 8e-5

  # 3) 冒烟（只跑 5 步验证显存/流水线）
  python scripts/train_world_model_final.py --max-steps 5 --out checkpoints/_smoke

环境变量兼容云端一键启动：BASE(BASE_DIR) / DATA / OUT / LR / EPOCHS / BS / ACCUM /
LORA_R / LORA_ALPHA / SEED / RESUME_ADAPTER 均可覆盖默认值。
"""
import argparse
import json
import os
import subprocess
import sys
import time

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

import torch
from peft import (  # noqa: E402
    LoraConfig, get_peft_model, TaskType, prepare_model_for_kbit_training, PeftModel,
)
from transformers import (  # noqa: E402
    AutoModelForCausalLM, AutoTokenizer, TrainingArguments, Trainer,
    DataCollatorForSeq2Seq, set_seed,
)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA_DIR = os.path.join(ROOT, "data", "sft")
# virtu_final_train.jsonl 是冻结证据（tests/test_physics_reference_honesty.py
# 钉住 3017 行 / 255 条 mm^5 坏靶，用来证明量纲审计非空转），--build 不得覆写它。
# 新合并产物落 BUILD_DATA；默认 --data 仍指向旧文件，由量纲闸 fail-closed 拒绝。
FINAL_DATA = os.path.join(DATA_DIR, "virtu_final_train.jsonl")
BUILD_DATA = os.path.join(DATA_DIR, "virtu_wm_final_train.jsonl")

SYS_DEFAULT = (
    "你是 Virtu 自主制造世界模型智能体。面对任务先思考(think)、规划(plan)、"
    "调用工业工具(act)、读取真实观测(observe)、校验(verify)、必要时重规划(replan)、"
    "最后定稿 world_state JSON。严禁臆造数值；工具返回是唯一真值来源。"
)


# ----------------------------------------------------------------------------
# 精度 / 序列化（与已验证的 v3 训练器同源，保证行为一致）
# ----------------------------------------------------------------------------
def pick_precision():
    if not torch.cuda.is_available():
        return "fp16", torch.float16
    major, _minor = torch.cuda.get_device_capability(0)
    return ("bf16", torch.bfloat16) if major >= 8 else ("fp16", torch.float16)


def serialize_message(m, tokenizer):
    role = m.get("role", "user")
    if role == "assistant" and m.get("tool_calls"):
        parts = []
        if m.get("content"):
            parts.append(m["content"])
        for tc in m["tool_calls"]:
            fn = tc.get("function", {})
            parts.append(json.dumps({"name": fn.get("name"), "arguments": fn.get("arguments")},
                                    ensure_ascii=False))
        seg = f"<|im_start|>assistant\n" + "\n".join(parts) + "<|im_end|>\n"
    elif role == "tool":
        seg = f"<|im_start|>tool\n{m.get('content', '')}<|im_end|>\n"
    else:
        seg = f"<|im_start|>{role}\n{m.get('content', '')}<|im_end|>\n"
    return tokenizer.encode(seg, add_special_tokens=False)


def format_sample(item, tokenizer, max_len):
    messages = item.get("messages")
    if not messages:
        inst = item.get("instruction", "")
        inp = item.get("input", "")
        out = item.get("output", "")
        uc = f"{inst}\n【输入参数与背景】: {inp}" if inp else inst
        messages = [{"role": "system", "content": SYS_DEFAULT},
                    {"role": "user", "content": uc},
                    {"role": "assistant", "content": out}]
    input_ids, labels, has_assistant = [], [], False
    for m in messages:
        seg = serialize_message(m, tokenizer)
        if m.get("role") == "assistant":
            has_assistant = True
            labels.extend(seg)
        else:
            labels.extend([-100] * len(seg))
        input_ids.extend(seg)
    if not has_assistant:
        return None
    truncated = False
    if len(input_ids) > max_len:
        # 头+尾保留截断：保住任务前缀（system+user）与最终定稿答案（world_state），
        # 避免"从左侧截断"把最后一段 assistant 答案切掉导致学不到定稿。
        truncated = True
        head = max_len // 3
        tail = max_len - head
        input_ids = input_ids[:head] + input_ids[-tail:]
        labels = labels[:head] + labels[-tail:]
    return {"input_ids": input_ids, "labels": labels,
            "attention_mask": [1] * len(input_ids), "_truncated": truncated}


def load_dataset(path, tokenizer, max_len):
    from datasets import Dataset
    items = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    out, dropped, truncated = [], 0, 0
    for it in items:
        s = format_sample(it, tokenizer, max_len)
        if s is None:
            dropped += 1
            continue
        if s.pop("_truncated", False):
            truncated += 1
        out.append(s)
    print(f"[Dataset] raw={len(items)} usable={len(out)} dropped={dropped} "
          f"head+tail_truncated={truncated}")
    return Dataset.from_list(out)


def find_latest_checkpoint(out_dir):
    if not os.path.isdir(out_dir):
        return None
    ck = [d for d in os.listdir(out_dir) if d.startswith("checkpoint-")]
    if not ck:
        return None
    ck.sort(key=lambda x: int(x.split("-")[-1]))
    return os.path.join(out_dir, ck[-1])


def write_receipt(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ----------------------------------------------------------------------------
# 数据构建：v2 世界模型 + 智能体轨迹 + 可选 replay
# ----------------------------------------------------------------------------
def _run(cmd):
    print(">>>", " ".join(cmd))
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if r.stdout:
        print(r.stdout[-1500:])
    if r.returncode != 0:
        print(r.stderr[-2000:])
        raise SystemExit(f"[FATAL] 子命令失败: {' '.join(cmd)}")


def build_final_data(n_agentic, with_replay):
    py = sys.executable
    _run([py, os.path.join(HERE, "build_worldmodel_v2.py")])
    _run([py, os.path.join(HERE, "build_agentic_sft.py"), "--n", str(n_agentic)])

    sources = [
        os.path.join(DATA_DIR, "virtu_worldmodel_v2.jsonl"),
        os.path.join(DATA_DIR, "virtu_agentic.jsonl"),
    ]
    if with_replay:
        rp = os.path.join(DATA_DIR, "virtu_v3_patch.jsonl")
        if os.path.exists(rp):
            sources.append(rp)

    recs, seen = [], set()
    counts = {}
    for p in sources:
        if not os.path.exists(p):
            print(f"[warn] 缺失数据源，跳过: {p}")
            continue
        n = 0
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            key = json.dumps(d.get("messages", d), ensure_ascii=False, sort_keys=True)
            if key in seen:
                continue
            seen.add(key)
            recs.append(d)
            n += 1
        counts[os.path.basename(p)] = n

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(BUILD_DATA, "w", encoding="utf-8") as f:
        for d in recs:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    # 量纲闸：合并产物里任何 mm^5 冒充 mm^4 的靶值都不得进入训练
    #（另两个训练器早已接闸，本训练器此前漏接，默认数据恰好带 255 条坏靶）。
    import corpus_unit_audit
    corpus_unit_audit.assert_units_clean(BUILD_DATA)
    print(f"[ok] 合并 {len(recs)} 条 -> {BUILD_DATA}")
    print(f"[sources] {json.dumps(counts, ensure_ascii=False)}")
    return BUILD_DATA


# ----------------------------------------------------------------------------
def selftest(args, tokenizer):
    print("=================== SELFTEST ===================")
    samples = []
    with open(args.data, encoding="utf-8") as f:
        for line in f:
            if len(samples) >= 6:
                break
            if line.strip():
                samples.append(json.loads(line))
    max_tok = 0
    for i, s in enumerate(samples):
        msgs = s.get("messages", [])
        fs = format_sample(s, tokenizer, args.max_len)
        if fs is None:
            print(f"  sample[{i}] 无 assistant 轮 -> 会被丢弃")
            continue
        n_loss = sum(1 for x in fs["labels"] if x != -100)
        n_asst = sum(1 for m in msgs if m.get("role") == "assistant")
        max_tok = max(max_tok, len(fs["input_ids"]))
        print(f"  sample[{i}] roles={[m['role'] for m in msgs]} "
              f"asst_turns={n_asst} tokens={len(fs['input_ids'])} loss_tokens={n_loss}")
    print(f"  tokenizer vocab_size={tokenizer.vocab_size}  max_tokens={max_tok} (max_len={args.max_len})")
    print("=================== SELFTEST OK ===================")


def main():
    ap = argparse.ArgumentParser(description="Virtu 世界模型最终版训练（自主思考/决策）")
    ap.add_argument("--base", default=os.environ.get("BASE", os.environ.get("BASE_DIR", "Qwen/Qwen3-8B")))
    ap.add_argument("--data", default=os.environ.get("DATA", FINAL_DATA))
    ap.add_argument("--out", default=os.environ.get("OUT", "checkpoints/virtu_wm_auto"))
    ap.add_argument("--lora_r", type=int, default=int(os.environ.get("LORA_R", "32")))
    ap.add_argument("--lora_alpha", type=int, default=int(os.environ.get("LORA_ALPHA", "64")))
    ap.add_argument("--lora_dropout", type=float, default=0.05)
    ap.add_argument("--lr", type=float, default=float(os.environ.get("LR", "8e-5")))
    ap.add_argument("--epochs", type=int, default=int(os.environ.get("EPOCHS", "3")))
    ap.add_argument("--bs", type=int, default=int(os.environ.get("BS", "4")))
    ap.add_argument("--accum", type=int, default=int(os.environ.get("ACCUM", "4")))
    ap.add_argument("--max_len", type=int, default=2560)
    ap.add_argument("--seed", type=int, default=int(os.environ.get("SEED", "20261103")))
    ap.add_argument("--val_ratio", type=float, default=0.03)
    ap.add_argument("--max_steps", type=int, default=-1, help=">0 时只跑这么多步（冒烟）")
    ap.add_argument("--resume-adapter", default=os.environ.get("RESUME_ADAPTER") or None)
    ap.add_argument("--build", action="store_true", help="先生成并合并最终数据")
    ap.add_argument("--n-agentic", type=int, default=120, help="每类智能体轨迹样本数")
    ap.add_argument("--no-replay", action="store_true", help="不并入 v3 工具调用 replay")
    ap.add_argument("--selftest", action="store_true", help="只做数据/分词自检")
    args = ap.parse_args()

    set_seed(args.seed)

    # 0) 数据：需要则构建；不存在则自动构建
    if args.build or not os.path.exists(args.data):
        args.data = build_final_data(args.n_agentic, with_replay=not args.no_replay)

    print("=" * 62)
    print("  Virtu 世界模型 · 最终版训练（自主思考/决策）")
    print(f"  base      = {args.base}")
    print(f"  data      = {args.data}")
    print(f"  out       = {args.out}")
    print(f"  lora      = r={args.lora_r} alpha={args.lora_alpha}")
    print(f"  hyper     = lr={args.lr} epochs={args.epochs} bs={args.bs} accum={args.accum}")
    print(f"  resume    = {args.resume_adapter}")
    print("=" * 62)

    # 量纲闸（加载路径）：不经过 --build 直接用现成数据时同样必须先过审计，
    # 否则冻结的坏靶文件（255 条 mm^5）会被直接喂进训练。
    import corpus_unit_audit
    corpus_unit_audit.assert_units_clean(args.data)

    tokenizer = AutoTokenizer.from_pretrained(args.base, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    if args.selftest:
        selftest(args, tokenizer)
        return

    os.makedirs(args.out, exist_ok=True)

    # 1) 4bit 基座
    from transformers import BitsAndBytesConfig
    prec_name, prec_dtype = pick_precision()
    print(f"[1/5] Loading 4bit base ({prec_name}) ...")
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                             bnb_4bit_compute_dtype=prec_dtype,
                             bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(
        args.base, torch_dtype=prec_dtype, quantization_config=bnb,
        device_map="auto", trust_remote_code=True)
    model = prepare_model_for_kbit_training(model)

    # 2) LoRA / 续训
    if args.resume_adapter:
        print(f"[2/5] Resume from adapter: {args.resume_adapter}")
        model = PeftModel.from_pretrained(model, args.resume_adapter)
        model.print_trainable_parameters()
    else:
        print("[2/5] Inject LoRA ...")
        cfg = LoraConfig(r=args.lora_r, lora_alpha=args.lora_alpha,
                         lora_dropout=args.lora_dropout,
                         target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                                         "gate_proj", "up_proj", "down_proj"],
                         bias="none", task_type=TaskType.CAUSAL_LM)
        model = get_peft_model(model, cfg)
        model.print_trainable_parameters()

    # 3) 数据
    print("[3/5] Tokenizing ...")
    dataset = load_dataset(args.data, tokenizer, args.max_len)
    if len(dataset) == 0:
        raise SystemExit("[FATAL] 数据为空，检查数据文件")
    if args.val_ratio > 0:
        split = dataset.train_test_split(test_size=args.val_ratio, seed=args.seed)
        train_ds, val_ds = split["train"], split["test"]
        print(f"[Dataset] train={len(train_ds)} val={len(val_ds)}")
    else:
        train_ds, val_ds = dataset, None

    # 4) 训练参数
    print("[4/5] Configuring trainer ...")
    ta = TrainingArguments(
        output_dir=args.out,
        per_device_train_batch_size=args.bs,
        gradient_accumulation_steps=args.accum,
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        warmup_ratio=0.03,
        weight_decay=0.01,
        num_train_epochs=args.epochs,
        max_steps=args.max_steps,
        logging_steps=10,
        save_strategy="steps",
        save_steps=300,
        save_total_limit=2,
        bf16=(prec_name == "bf16"),
        fp16=(prec_name == "fp16"),
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        optim="paged_adamw_8bit",
        report_to="none",
        dataloader_num_workers=2,
        seed=args.seed,
        logging_dir=os.path.join(args.out, "logs"),
    )
    collator = DataCollatorForSeq2Seq(tokenizer, pad_to_multiple_of=8,
                                      return_tensors="pt", padding=True)
    trainer = Trainer(model=model, args=ta, train_dataset=train_ds,
                      eval_dataset=val_ds, data_collator=collator)

    resume = find_latest_checkpoint(args.out)
    if resume:
        print(f"[Resume] from {resume}")

    # 5) 开训
    print("\n=================== LAUNCHING TRAINING ===================")
    t0 = time.time()
    try:
        result = trainer.train(resume_from_checkpoint=resume)
        elapsed = time.time() - t0
        train_loss = result.training_loss
        print(f"=================== DONE ({elapsed:.1f}s) ===================")
        print(f"global_step={trainer.state.global_step} loss={train_loss:.4f}")
    except Exception as e:  # noqa: BLE001
        elapsed = time.time() - t0
        write_receipt(os.path.join(args.out, "training_receipt.json"),
                      {"status": "FAILED", "error": repr(e), "runtime_seconds": elapsed,
                       "base": args.base, "data": args.data})
        print(f"[ERROR] training failed: {e}")
        sys.exit(1)

    # 6) 保存
    print(f"[Artifacts] saving adapter -> {args.out}")
    model.save_pretrained(args.out)
    tokenizer.save_pretrained(args.out)

    gpus = [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]
    write_receipt(os.path.join(args.out, "training_receipt.json"), {
        "status": "COMPLETED",
        "task": "Virtu autonomous world-model SFT (agentic think/act/verify)",
        "base": args.base,
        "data": args.data,
        "num_samples": len(dataset),
        "resume_adapter": args.resume_adapter,
        "lora_r": args.lora_r,
        "lora_alpha": args.lora_alpha,
        "learning_rate": args.lr,
        "epochs": args.epochs,
        "global_step": trainer.state.global_step,
        "train_loss": train_loss,
        "runtime_seconds": elapsed,
        "gpus": gpus,
        "adapter_dir": os.path.abspath(args.out),
    })
    print(f"[SUCCESS] receipt -> {os.path.join(args.out, 'training_receipt.json')}")
    print("\n[ALL PIPELINES COMPLETE] 下一步：合并/量化/注册，跑 agentic 评测。")


if __name__ == "__main__":
    main()
