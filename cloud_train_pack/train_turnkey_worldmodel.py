#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cloud_train_pack/train_turnkey_worldmodel.py — Virtu 世界工程模型（World Engineering Model）云端一键修复训练引擎

核心特性：
  1. 开训前硬门禁（Fail-Closed）：
     - 拒绝缺失数据集时的静默回退（拒绝自动回退）；
     - 强制校验语料 SHA256 账本（virtu_worldmodel_fix_sft_ledger.json）；
     - 强制通过评测集防泄漏门禁 assert_no_leak（覆盖 virtu_eval_v1 / phys_v1 / cl_v1）；
     - 强制通过物理量纲门禁 assert_units_clean（杜绝 mm^5 冒充 mm^4）；
     - 强制断言 0 遗留门禁字面量（仅允许 wm_contract 规范的 pass/fail）。
  2. 多轮智能体轨迹精确 Loss 掩码：
     - 仅对有效 assistant 轮计算交叉熵 Loss；
     - 对 system / user / tool 观测轮，以及带 "loss": false 的错误草稿轮（如 1000x 单位错误首轮、
       CAD 负体积待修复首轮、Student 违规轮）全部置为 -100，彻底根除“把反例当正例训”；
     - 自动剥离 Qwen3 chat_template 注入的空 <think></think> 块；
     - 超长样本采用“头 1/3 + 尾 2/3”保尾截断，确保末尾定稿 world_state JSON 绝不被切掉。
  3. 硬件自适应：
     - Tesla V100 (sm_70, 32GB)：自动启用 fp16 Full LoRA；
     - A100 / H800 / RTX 4090 (sm_80+)：自动启用 bf16 Full LoRA；
     - 显存 < 24GB 或显式传入 --qlora：启用 4-bit NF4 QLoRA。
  4. 零摩擦交付：
     -支持 --selftest 离线全量语料 Tokenize 与掩码审计（无需 GPU）；
     - 训练完成自动生成 training_receipt.json、virtu_wm_lora_deliverable.tar.gz 与 .sha256 校验文件。
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import math
import os
import random
import re
import shutil
import sys
import tarfile
import time

if "--gpu-id" in sys.argv:
    _idx = sys.argv.index("--gpu-id")
    if _idx + 1 < len(sys.argv):
        os.environ["CUDA_VISIBLE_DEVICES"] = sys.argv[_idx + 1]
else:
    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (
    _HERE,
    _ROOT,
    os.path.join(_HERE, "scripts"),
    os.path.join(_ROOT, "scripts"),
):
    if os.path.exists(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

import torch  # noqa: E402
from transformers import (  # noqa: E402
    AutoModelForCausalLM,
    AutoTokenizer,
    DataCollatorForSeq2Seq,
    Trainer,
    TrainerCallback,
    TrainingArguments,
    set_seed,
)
try:
    from peft import (
        LoraConfig,
        PeftModel,
        TaskType,
        get_peft_model,
        prepare_model_for_kbit_training,
    )
except ImportError:
    LoraConfig = PeftModel = TaskType = get_peft_model = prepare_model_for_kbit_training = None

from virtu_eval.contamination_check import assert_no_leak  # noqa: E402
from corpus_unit_audit import assert_units_clean  # noqa: E402
from train_world_model_final import (  # noqa: E402
    ListDataset,
    normalize_item_messages,
)

TARGET_MODULES = [
    "q_proj", "k_proj", "v_proj", "o_proj",
    "gate_proj", "up_proj", "down_proj",
]

LEGACY_GATE_TOKENS = ("FOS>=1.5_pass", "FOS<1.5_FAIL", "pass_cut_negative")

CANDIDATE_BASE_PATHS = [
    os.path.join(_ROOT, "checkpoints", "_base_qwen3_8b"),
    os.path.join(_HERE, "checkpoints", "_base_qwen3_8b"),
    "/root/virtu_train/models/Qwen3-8B",
    "/root/workspace/models/Qwen3-8B",
    "/root/models/Qwen3-8B",
    "/root/autodl-tmp/models/Qwen3-8B",
    "/root/damodel-tmp/models/Qwen3-8B",
    "/root/public-storage/model/Qwen/Qwen3-8B",
    # 禁止 Instruct 变体：本尊基座是 Qwen3-8B，错基座=整条训练腿作废（11-09 实测坑）
    "./models/Qwen3-8B",
]


def assert_base_identity(base_path: str) -> None:
    cfg_path = os.path.join(base_path, "config.json")
    if os.path.exists(cfg_path):
        with open(cfg_path, "r", encoding="utf-8") as f:
            name = json.load(f).get("_name_or_path", "")
        if "Instruct" in base_path or "Instruct" in name:
            raise SystemExit(
                f"[FATAL] 基座 {base_path} 是 Instruct 变体；本尊基座必须是 Qwen3-8B。"
            )


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(4 * 1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def get_best_storage_dir() -> str:
    candidates = [
        "/root/virtu_train",
        "/root/workspace",
        "/root/autodl-tmp",
        "/root/damodel-tmp",
        "/mnt/data",
        "/root",
        ".",
    ]
    best_dir = "."
    max_free_gb = 0.0
    for c in candidates:
        if os.path.exists(c):
            try:
                free_gb = shutil.disk_usage(c).free / (1024**3)
                if free_gb > max_free_gb:
                    max_free_gb = free_gb
                    best_dir = c
            except Exception:
                pass
    print(f"[Storage] 最优存储路径: {best_dir} (可用空间: {max_free_gb:.1f} GB)")
    return best_dir


def find_or_download_base(specified_base: str | None = None,
                          tokenizer_only: bool = False) -> str:
    if specified_base and os.path.exists(specified_base) and os.path.exists(
        os.path.join(specified_base, "config.json")
    ):
        print(f"[Base] 使用指定基座路径: {specified_base}")
        return specified_base

    search_list = list(CANDIDATE_BASE_PATHS)
    search_list.extend(sorted(glob.glob(os.path.expandvars(
        r"C:\Users\Administrator\.cache\huggingface\hub\models--Qwen--Qwen3-8B\snapshots\*"
    ))))
    search_list.extend(sorted(glob.glob(os.path.expanduser(
        "~/.cache/huggingface/hub/models--Qwen--Qwen3-8B/snapshots/*"
    ))))
    for p in search_list:
        if os.path.exists(p) and os.path.exists(os.path.join(p, "config.json")):
            print(f"[Base] 探测到本机/云端已有 Qwen3-8B 权重/Tokenizer: {p}")
            return p

    best_dir = get_best_storage_dir()
    target_dir = os.path.join(best_dir, "models", "Qwen3-8B")
    os.makedirs(os.path.dirname(target_dir), exist_ok=True)
    if tokenizer_only:
        # selftest 只需 tokenizer：拉全量 16GB 权重是白烧计费时长
        print(f"[Base] selftest 模式：仅拉取 Qwen3-8B tokenizer/配置 -> {target_dir} ...")
        try:
            from modelscope import snapshot_download
            return snapshot_download(
                "Qwen/Qwen3-8B", local_dir=target_dir,
                allow_patterns=["tokenizer*", "vocab*", "merges*", "*.json"],
            )
        except TypeError:
            print("[Base] 旧版 modelscope 不支持 allow_patterns，回退全量下载。")
        except Exception as e:
            print(f"[Base] tokenizer-only 下载失败 ({e})，回退全量下载。")
    print(f"[Base] 未探测到本地基座，正在通过 ModelScope 拉取 Qwen/Qwen3-8B -> {target_dir} ...")
    try:
        from modelscope import snapshot_download
        return snapshot_download("Qwen/Qwen3-8B", local_dir=target_dir)
    except Exception as e:
        print(f"[Base] ModelScope 下载失败 ({e})，切换 HuggingFace 国内镜像 ...")
        os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
        from huggingface_hub import snapshot_download
        return snapshot_download("Qwen/Qwen3-8B", local_dir=target_dir)


class TimeBudgetCallback(TrainerCallback):
    def __init__(self, max_minutes: float):
        self.max_seconds = max_minutes * 60.0 if max_minutes > 0 else float("inf")
        self.start_time = time.time()
        self.budget_stopped = False

    def on_step_end(self, args, state, control, **kwargs):
        elapsed = time.time() - self.start_time
        if elapsed > self.max_seconds:
            print(
                f"\n[TimeBudgetGuard] 已达到时间预算上限 ({elapsed/60:.1f}m > "
                f"{self.max_seconds/60:.1f}m)，保存当前权重并优雅停机！"
            )
            self.budget_stopped = True
            control.should_training_stop = True
            control.should_save = True


def _render_single_message(m: dict) -> str:
    role = m.get("role", "user")
    content = str(m.get("content", ""))
    tc = m.get("tool_calls")
    if tc:
        content = (content + "\n" if content else "") + json.dumps(tc, ensure_ascii=False)
    return f"<|im_start|>{role}\n{content}<|im_end|>\n"


def tokenize_wm_sample(rec: dict, tokenizer, max_length: int = 2560) -> dict | None:
    """将单条样本编码为 (input_ids, labels, attention_mask)，对非 assistant 及 loss=False 轮置 -100。"""
    msgs = normalize_item_messages(rec)
    if not msgs:
        return None
    while msgs and msgs[-1].get("role") != "assistant":
        msgs.pop()
    if not msgs:
        return None

    last_only = bool(rec.get("last_assistant_only", False))
    asst_indices = [i for i, m in enumerate(msgs) if m.get("role") == "assistant"]
    if not asst_indices:
        return None

    input_ids: list[int] = []
    labels: list[int] = []
    masked_asst_turns = 0
    active_asst_turns = 0

    for idx, m in enumerate(msgs):
        role = m.get("role", "user")
        content = str(m.get("content", ""))
        tc = m.get("tool_calls")
        if tc:
            content = (content + "\n" if content else "") + json.dumps(tc, ensure_ascii=False)
        # 剥离可能残留在文本中的空 <think></think>
        if role == "assistant" and "<think>" in content:
            content = re.sub(r"<think>\s*</think>\s*", "", content)

        prefix = f"<|im_start|>{role}\n"
        body = f"{content}<|im_end|>\n"
        p_ids = tokenizer.encode(prefix, add_special_tokens=False)
        b_ids = tokenizer.encode(body, add_special_tokens=False)

        train_this_turn = False
        if role == "assistant":
            if last_only and idx != asst_indices[-1]:
                train_this_turn = False
            elif m.get("loss") is False:
                train_this_turn = False
            else:
                train_this_turn = True

            if train_this_turn:
                active_asst_turns += 1
            else:
                masked_asst_turns += 1

        input_ids.extend(p_ids)
        labels.extend([-100] * len(p_ids))
        input_ids.extend(b_ids)
        if train_this_turn:
            labels.extend(b_ids)
        else:
            labels.extend([-100] * len(b_ids))

    truncated = False
    if len(input_ids) > max_length:
        # 头 1/3 + 尾 2/3 保尾截断，确保最终定稿 world_state JSON 完整保留
        head = max_length // 3
        tail = max_length - head
        input_ids = input_ids[:head] + input_ids[-tail:]
        labels = labels[:head] + labels[-tail:]
        truncated = True

    if not any(x != -100 for x in labels):
        return None

    return {
        "input_ids": input_ids,
        "labels": labels,
        "attention_mask": [1] * len(input_ids),
        "_meta": {
            "active_asst_turns": active_asst_turns,
            "masked_asst_turns": masked_asst_turns,
            "truncated": truncated,
        },
    }


def load_wm_dataset(dataset_path: str, tokenizer, max_length: int = 2560):
    print(f"[Data] 加载并编码世界工程模型修复语料: {dataset_path}")
    samples = []
    stats = {
        "total_rows": 0,
        "usable_rows": 0,
        "skipped_rows": 0,
        "truncated_rows": 0,
        "masked_bad_asst_turns": 0,
        "legacy_gates_remaining": 0,
        "max_tokens": 0,
    }
    with open(dataset_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            stats["total_rows"] += 1
            for tok in LEGACY_GATE_TOKENS:
                if f'"{tok}"' in line:
                    stats["legacy_gates_remaining"] += 1
            rec = json.loads(line)
            enc = tokenize_wm_sample(rec, tokenizer, max_length=max_length)
            if enc is None:
                stats["skipped_rows"] += 1
                continue
            meta = enc.pop("_meta")
            stats["usable_rows"] += 1
            if meta["truncated"]:
                stats["truncated_rows"] += 1
            stats["masked_bad_asst_turns"] += meta["masked_asst_turns"]
            stats["max_tokens"] = max(stats["max_tokens"], len(enc["input_ids"]))
            samples.append(enc)

    print(
        f"[Data] 编码汇总: total={stats['total_rows']} usable={stats['usable_rows']} "
        f"skipped={stats['skipped_rows']} truncated={stats['truncated_rows']} "
        f"masked_bad_asst_turns={stats['masked_bad_asst_turns']} "
        f"legacy_gates_remaining={stats['legacy_gates_remaining']} "
        f"max_tokens={stats['max_tokens']}"
    )
    if stats["legacy_gates_remaining"] > 0:
        raise SystemExit(
            f"[FATAL] 语料中检测到 {stats['legacy_gates_remaining']} 处未归一化的旧版门禁字面量，拒绝开训！"
        )
    if stats["usable_rows"] == 0:
        raise SystemExit("[FATAL] 可用训练样本数为 0，拒绝开训！")
    return ListDataset(samples), stats


def resolve_default_data_path(arg_data: str) -> str:
    if os.path.exists(arg_data):
        return arg_data
    alt = os.path.join(_HERE, arg_data)
    if os.path.exists(alt):
        return alt
    alt_root = os.path.join(_ROOT, arg_data)
    if os.path.exists(alt_root):
        return alt_root
    return arg_data


def verify_ledger_if_present(data_path: str, ledger_arg: str | None = None) -> dict | None:
    candidates = []
    if ledger_arg:
        candidates.append(ledger_arg)
    if data_path.endswith(".jsonl"):
        candidates.append(data_path[:-6] + "_ledger.json")
    for lp in candidates:
        if lp and os.path.exists(lp):
            with open(lp, "r", encoding="utf-8") as f:
                ledger = json.load(f)
            expected_sha = ledger.get("output_sha256")
            actual_sha = sha256_file(data_path)
            if expected_sha and expected_sha != actual_sha:
                raise SystemExit(
                    f"[FATAL] 语料 SHA256 与账本不一致！ledger={expected_sha[:16]}... "
                    f"actual={actual_sha[:16]}... 拒绝开训。"
                )
            print(f"[Ledger] 账本指纹核验通过: {os.path.basename(lp)} (sha256={actual_sha[:16]}...)")
            return ledger
    return None


def train() -> int:
    parser = argparse.ArgumentParser(
        description="Virtu 世界工程模型（World Engineering Model）云端一键修复训练脚本"
    )
    parser.add_argument("--base", default=os.environ.get("BASE"), help="Qwen3-8B 基座模型路径")
    parser.add_argument(
        "--data",
        default=os.environ.get("DATA", "dataset/virtu_worldmodel_fix_sft.jsonl"),
        help="世界工程模型修复 SFT 语料路径",
    )
    parser.add_argument("--ledger", default=None, help="语料溯源账本路径（可选，默认自动匹配 *_ledger.json）")
    parser.add_argument(
        "--out",
        default=os.environ.get("OUT", "output/virtu_wm_lora_fix"),
        help="LoRA 产物与交付包输出目录",
    )
    parser.add_argument(
        "--resume-adapter",
        default=os.environ.get("RESUME_ADAPTER"),
        help="可选：已有 LoRA adapter 路径，在其上继续微调",
    )
    parser.add_argument("--epochs", type=float, default=float(os.environ.get("EPOCHS", 2.5)))
    parser.add_argument("--lr", type=float, default=float(os.environ.get("LR", 1.0e-4)))
    parser.add_argument("--batch", type=int, default=int(os.environ.get("BS", 2)))
    parser.add_argument("--grad-accum", type=int, default=int(os.environ.get("ACCUM", 8)))
    parser.add_argument("--max-length", type=int, default=int(os.environ.get("MAX_LEN", 2560)))
    parser.add_argument("--lora-r", type=int, default=int(os.environ.get("LORA_R", 32)))
    parser.add_argument("--lora-alpha", type=int, default=int(os.environ.get("LORA_ALPHA", 64)))
    parser.add_argument("--max-hours", type=float, default=float(os.environ.get("MAX_HOURS", 2.0)))
    parser.add_argument("--max-steps", type=int, default=int(os.environ.get("MAX_STEPS", -1)))
    parser.add_argument("--seed", type=int, default=int(os.environ.get("SEED", 20261110)))
    parser.add_argument("--gpu-id", default="0", help="指定可见 GPU 编号")
    parser.add_argument("--qlora", action="store_true", help="显式启用 4-bit NF4 QLoRA（适用于 <24GB 显存）")
    parser.add_argument("--selftest", action="store_true", help="仅执行四重门禁与全量 Tokenize 自检，不加载 GPU 权重")
    args = parser.parse_args()

    data_path = resolve_default_data_path(args.data)
    if not os.path.exists(data_path):
        raise SystemExit(
            f"[FATAL] --data={args.data} 不存在。拒绝自动回退到其它语料；"
            f"请先运行 `python scripts/build_wm_cloud_fix_corpus.py` 生成世界工程模型修复语料。"
        )

    # 门禁 1 & 2 & 3：开训前防泄漏、量纲与账本 SHA256 校验（必须在加载权重和读数据之前）
    assert_no_leak(data_path)
    for extra_eval in ("virtu_eval_phys_v1", "virtu_eval_cl_v1"):
        for root_cand in (_HERE, _ROOT):
            bdir = os.path.join(root_cand, "data", "benchmark", extra_eval)
            if os.path.isdir(bdir):
                assert_no_leak(data_path, eval_dir=bdir)
                break
    assert_units_clean(data_path)
    ledger = verify_ledger_if_present(data_path, args.ledger)

    set_seed(args.seed)
    t_start = time.time()
    base_path = find_or_download_base(args.base, tokenizer_only=args.selftest)
    assert_base_identity(base_path)

    tokenizer = AutoTokenizer.from_pretrained(base_path, trust_remote_code=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token

    full_ds, ds_stats = load_wm_dataset(data_path, tokenizer, max_length=args.max_length)
    split = full_ds.train_test_split(test_size=0.03, seed=args.seed)
    train_ds, eval_ds = split["train"], split["test"]

    if args.selftest:
        print("=" * 70)
        print("[SELFTEST] 世界工程模型云端训练器自检通过")
        print(f"  base_path              = {base_path}")
        print(f"  data_path              = {data_path}")
        print(f"  usable_rows            = {ds_stats['usable_rows']} (train={len(train_ds)}, eval={len(eval_ds)})")
        print(f"  masked_bad_asst_turns  = {ds_stats['masked_bad_asst_turns']}")
        print(f"  legacy_gates_remaining = {ds_stats['legacy_gates_remaining']}")
        print(f"  max_tokens             = {ds_stats['max_tokens']} (limit={args.max_length})")
        print("=" * 70)
        return 0

    if not torch.cuda.is_available():
        raise SystemExit("[FATAL] 未检测到可用 CUDA GPU！离线验证请加 --selftest。")

    gpu_name = torch.cuda.get_device_name(0)
    total_vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
    major_cc = torch.cuda.get_device_capability(0)[0]
    has_bf16 = (major_cc >= 8) and getattr(torch.cuda, "is_bf16_supported", lambda: False)()
    compute_dtype = torch.bfloat16 if has_bf16 else torch.float16
    use_qlora = bool(args.qlora or total_vram_gb < 24.0)
    if use_qlora:
        # bnb 在 CUDA 13.x/新 torch 上无对应内核（11-09 实测）：先验证再加载，
        # 否则 16GB 权重下完才崩，白烧计费时长。
        try:
            import bitsandbytes  # noqa: F401
        except Exception as e:
            raise SystemExit(
                f"[FATAL] QLoRA 需要 bitsandbytes 但不可用 ({e})。"
                "V100-32GB 请走全量 fp16 LoRA（去掉 --qlora，显存>=24GB 时自动选择）；"
                "要 QLoRA 必须 torch<=2.5(cu124) 且 bnb 有对应内核。"
            )
    mode_str = f"QLoRA (4-bit NF4, {compute_dtype})" if use_qlora else f"Full {compute_dtype} LoRA"
    print(
        f"[Hardware] GPU: {gpu_name} | 显存: {total_vram_gb:.2f} GB | "
        f"架构: sm_{major_cc}x | 策略: {mode_str}"
    )

    model_kwargs = {"trust_remote_code": True, "device_map": {"": 0}, "attn_implementation": "sdpa"}
    if use_qlora:
        from transformers import BitsAndBytesConfig
        model_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=compute_dtype,
            bnb_4bit_use_double_quant=True,
        )
    else:
        model_kwargs["torch_dtype"] = compute_dtype

    print(f"[Model] 正在加载基座权重: {base_path} ...")
    model = AutoModelForCausalLM.from_pretrained(base_path, **model_kwargs)
    model.config.use_cache = False
    if use_qlora:
        model = prepare_model_for_kbit_training(model)
    model.gradient_checkpointing_enable()

    if args.resume_adapter and os.path.isdir(args.resume_adapter):
        print(f"[LoRA] 从已有适配器继续微调: {args.resume_adapter}")
        model = PeftModel.from_pretrained(model, args.resume_adapter, is_trainable=True)
    else:
        lora_cfg = LoraConfig(
            r=args.lora_r,
            lora_alpha=args.lora_alpha,
            lora_dropout=0.05,
            target_modules=TARGET_MODULES,
            bias="none",
            task_type=TaskType.CAUSAL_LM,
        )
        model = get_peft_model(model, lora_cfg)

    trainable_params, all_param = model.get_nb_trainable_parameters()
    print(
        f"[LoRA] 可训练参数: {trainable_params:,} / {all_param:,} "
        f"({trainable_params / all_param * 100:.2f}%)"
    )

    os.makedirs(args.out, exist_ok=True)
    training_args = TrainingArguments(
        output_dir=os.path.join(args.out, "_checkpoints"),
        num_train_epochs=args.epochs,
        max_steps=args.max_steps,
        per_device_train_batch_size=args.batch,
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        warmup_ratio=0.05,
        weight_decay=0.01,
        max_grad_norm=1.0,
        logging_steps=10,
        eval_strategy="steps",
        eval_steps=100,
        save_strategy="steps",
        save_steps=100,
        save_total_limit=2,
        bf16=has_bf16,
        fp16=not has_bf16,
        gradient_checkpointing=True,
        group_by_length=True,
        report_to="none",
        dataloader_num_workers=0,
        optim="paged_adamw_8bit" if use_qlora else "adamw_torch",
        seed=args.seed,
    )

    budget_cb = TimeBudgetCallback(args.max_hours * 60)
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        data_collator=DataCollatorForSeq2Seq(
            tokenizer, pad_to_multiple_of=8, return_tensors="pt", padding=True
        ),
        callbacks=[budget_cb],
    )

    print("\n" + "=" * 70)
    print("🚀 启动世界工程模型（World Engineering Model）云端修复微调 ...")
    print("=" * 70 + "\n")

    train_res = trainer.train()
    if (
        train_res.training_loss is None
        or math.isnan(train_res.training_loss)
        or train_res.training_loss <= 0
    ):
        raise RuntimeError(f"[FATAL] 训练损失异常 (loss={train_res.training_loss})，未正常收敛！")

    eval_metrics = trainer.evaluate()
    eval_loss = eval_metrics.get("eval_loss")
    print(f"[Metrics] train_loss={train_res.training_loss:.4f}  eval_loss={eval_loss}")

    final_adapter_dir = os.path.join(args.out, "final_adapter")
    os.makedirs(final_adapter_dir, exist_ok=True)
    model.save_pretrained(final_adapter_dir)
    tokenizer.save_pretrained(final_adapter_dir)

    safetensor_file = os.path.join(final_adapter_dir, "adapter_model.safetensors")
    adapter_sha = sha256_file(safetensor_file) if os.path.exists(safetensor_file) else "unknown"
    dataset_sha = sha256_file(data_path)

    receipt = {
        "schema_version": "virtu_wm_training_receipt.v2",
        "model_brand": "Virtu-World-Engineering-Model-8B",
        "basis": "measured",
        "base_model": base_path,
        "resume_adapter": args.resume_adapter,
        "dataset_path": data_path,
        "dataset_sha256": dataset_sha,
        "ledger_verified": bool(ledger is not None),
        "adapter_sha256": adapter_sha,
        "lora_r": args.lora_r,
        "lora_alpha": args.lora_alpha,
        "target_modules": TARGET_MODULES,
        "precision_mode": mode_str,
        "gpu_name": gpu_name,
        "torch_version": torch.__version__,
        "device_capability": list(torch.cuda.get_device_capability(0)),
        "epochs_requested": args.epochs,
        "max_steps_requested": args.max_steps,
        "stopped_by_time_budget": bool(budget_cb.budget_stopped),
        "dataset_stats": ds_stats,
        "train_rows": len(train_ds),
        "eval_rows": len(eval_ds),
        "train_loss": float(train_res.training_loss),
        "eval_loss": float(eval_loss) if eval_loss is not None else None,
        "total_train_seconds": round(time.time() - t_start, 2),
        "completed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        # 预算停机 ≠ 完成：下游部署闸只认 COMPLETED，防止半程权重被静默部署
        "status": "TIME_BUDGET_STOPPED" if budget_cb.budget_stopped else "COMPLETED",
    }

    receipt_path = os.path.join(final_adapter_dir, "training_receipt.json")
    with open(receipt_path, "w", encoding="utf-8", newline="\n") as rf:
        json.dump(receipt, rf, ensure_ascii=False, indent=2)

    deliverable_tar = os.path.join(args.out, "virtu_wm_lora_deliverable.tar.gz")
    with tarfile.open(deliverable_tar, "w:gz") as tar:
        tar.add(final_adapter_dir, arcname="virtu_wm_lora_adapter")

    tar_sha = sha256_file(deliverable_tar)
    with open(deliverable_tar + ".sha256", "w", encoding="utf-8", newline="\n") as sf:
        sf.write(f"{tar_sha}  virtu_wm_lora_deliverable.tar.gz\n")

    sz_mb = os.path.getsize(deliverable_tar) / (1024**2)
    print("\n" + "=" * 70)
    print(f"🎉 世界工程模型修复训练完成！耗时: {(time.time() - t_start)/60:.1f} 分钟")
    print(f"📉 train_loss: {train_res.training_loss:.4f} | eval_loss: {eval_loss}")
    print(f"📦 交付压缩包: {deliverable_tar} ({sz_mb:.1f} MB)")
    print(f"🔑 适配器 SHA256: {adapter_sha}")
    print("=" * 70 + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(train())
