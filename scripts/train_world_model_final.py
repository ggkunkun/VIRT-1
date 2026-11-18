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
import glob
import json
import os
import random
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
for _p in (HERE, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import wm_contract as _wm_contract  # noqa: E402

DATA_DIR = os.path.join(ROOT, "data", "sft")
# virtu_final_train.jsonl 是冻结证据（tests/test_physics_reference_honesty.py
# 钉住 3017 行 / 255 条 mm^5 坏靶，用来证明量纲审计非空转），--build 不得覆写它。
FINAL_DATA = os.path.join(DATA_DIR, "virtu_final_train.jsonl")
BUILD_DATA = os.path.join(DATA_DIR, "virtu_wm_final_train.jsonl")
# 默认训练数据：重平衡 + 量纲修复版（2026-11-09 切换）。
# 理由有两个，缺一不可：
#   1) 旧 FINAL_DATA 带 455 条 inertia_*_mm4 靶值错误（mm^5 数值被标成 mm4），
#      直接喂进去等于训练模型记住错靶，量纲闸 assert_units_clean 会在开训前 fail-closed；
#   2) 旧集模板多样性偏低（401 个模板簇），重平衡版 1327 簇 / 7828 行，覆盖旧集 100%。
# .unitfix.clean 版在 .unitfix 基础上经 virtu_eval/contamination_check.py 剔除 592 条评测硬泄漏
# （7828 -> 7236 行），同时通过 assert_no_leak 与 assert_units_clean 双重门禁。
# 原始 wm_train_cap12_v2.jsonl 与 wm_train_cap12_v2.unitfix.jsonl 保留作审计留痕，不删。
REBALANCED_DATA = os.path.join(ROOT, "data", "sft_rebalanced",
                               "wm_train_cap12_v2.unitfix.clean.jsonl")

SYS_DEFAULT = (
    "你是 Virtu 自主制造世界模型智能体。面对任务先思考(think)、规划(plan)、"
    "调用工业工具(act)、读取真实观测(observe)、校验(verify)、必要时重规划(replan)、"
    "最后定稿 world_state JSON。严禁臆造数值；工具返回是唯一真值来源。"
)


class ListDataset(torch.utils.data.Dataset):
    """轻量 Dataset 容器，消除对 huggingface `datasets` 包的硬依赖。"""

    def __init__(self, items):
        self.items = list(items)

    def __len__(self):
        return len(self.items)

    def __getitem__(self, idx):
        return self.items[idx]

    def train_test_split(self, test_size=0.03, seed=20261103):
        idx = list(range(len(self.items)))
        rng = random.Random(seed)
        rng.shuffle(idx)
        n_test = max(1, int(round(len(idx) * float(test_size)))) if idx else 0
        test_set = set(idx[:n_test])
        train_items = [self.items[i] for i in range(len(self.items)) if i not in test_set]
        test_items = [self.items[i] for i in idx[:n_test]]
        return {"train": ListDataset(train_items), "test": ListDataset(test_items)}


def resolve_base_path(base_arg: str) -> str:
    """优先复用本机/云端已有 Qwen3-8B 目录，避免离线或无网时 AutoTokenizer 失败。"""
    if os.path.isdir(base_arg) and os.path.exists(os.path.join(base_arg, "config.json")):
        return base_arg
    cands = [
        os.path.join(ROOT, "checkpoints", "_base_qwen3_8b"),
        "/root/models/Qwen3-8B",
        "/root/autodl-tmp/models/Qwen3-8B",
        "/root/public-storage/model/Qwen/Qwen3-8B",
        "/data/models/Qwen3-8B",
    ]
    hf_pat = os.path.expandvars(
        r"C:\Users\Administrator\.cache\huggingface\hub\models--Qwen--Qwen3-8B\snapshots\*"
    )
    cands.extend(sorted(glob.glob(hf_pat)))
    cands.extend(sorted(glob.glob(os.path.expanduser(
        "~/.cache/huggingface/hub/models--Qwen--Qwen3-8B/snapshots/*"
    ))))
    for c in cands:
        if os.path.isdir(c) and os.path.exists(os.path.join(c, "config.json")):
            return c
    return base_arg


# ----------------------------------------------------------------------------
# 精度 / 多 Schema 归一 / 坏轮次 Loss 屏蔽 / 序列化
# ----------------------------------------------------------------------------
def pick_precision():
    if not torch.cuda.is_available():
        return "fp16", torch.float16
    major, _minor = torch.cuda.get_device_capability(0)
    return ("bf16", torch.bfloat16) if major >= 8 else ("fp16", torch.float16)


def _normalize_legacy_gates_in_text(text: str) -> str:
    if not isinstance(text, str) or not text:
        return ""
    return (text.replace('"FOS>=1.5_pass"', '"pass"')
                .replace('"FOS<1.5_FAIL"', '"fail"')
                .replace('"pass_cut_negative"', '"pass"'))


def _is_error_feedback_turn(m: dict) -> bool:
    """判断一条 tool / user 消息是否是对上一轮 assistant 错误尝试的拒绝或报错反馈。"""
    role = m.get("role", "")
    c = str(m.get("content", ""))
    if role == "tool":
        if any(tok in c for tok in (
            '"status": "FAILED"', '"status": "rejected"', '"ok": false',
            '"warning": "载荷单位可疑', '"violations":', '"error_type":',
        )):
            return True
    elif role == "user":
        if "【教师诊断与指导】" in c or "存在严重冲突" in c:
            return True
    return False


def normalize_item_messages(item: dict) -> list[dict] | None:
    """将重平衡语料中的 9 种 schema 统一转为规范 messages，并自动标注坏轮次 loss=False。

    修复缺陷：
      1) 旧实现只识别 messages 与 instruction/input/output，导致 prompt+chosen (144)、
         prompt_messages+chosen (5)、family+inputs+outputs (290) 共 439 条退化为
         空 user / 空 assistant，教模型输出空串；
      2) 多轮自纠错轨迹（recover_agent 1000x 单位错误首轮、cad_loop_repair_annotate 几何干涉首轮、
         Student-Teacher 初次失败轮）旧实现未设 loss=False，把错误示范一并算进正样本梯度；
      3) 历史遗留的长闸门字面量（FOS>=1.5_pass / FOS<1.5_FAIL / pass_cut_negative）统一归一为 pass/fail。
    """
    raw_msgs = item.get("messages")
    if isinstance(raw_msgs, list) and raw_msgs:
        msgs = [dict(m) for m in raw_msgs if isinstance(m, dict)]
    elif isinstance(item.get("prompt_messages"), list) and item.get("chosen"):
        msgs = [dict(m) for m in item["prompt_messages"] if isinstance(m, dict)]
        msgs.append({"role": "assistant", "content": str(item["chosen"])})
    elif item.get("prompt") and item.get("chosen"):
        chosen_s = str(item["chosen"])
        sys_p = _wm_contract.SYSTEM if '"world_state"' in chosen_s else SYS_DEFAULT
        msgs = [
            {"role": "system", "content": sys_p},
            {"role": "user", "content": str(item["prompt"])},
            {"role": "assistant", "content": chosen_s},
        ]
    elif item.get("instruction") or item.get("output"):
        inst = str(item.get("instruction", "")).strip()
        inp = str(item.get("input", "")).strip()
        out = str(item.get("output", "")).strip()
        if not inst or not out:
            return None
        uc = f"{inst}\n【输入参数与背景】: {inp}" if inp else inst
        msgs = [
            {"role": "system", "content": SYS_DEFAULT},
            {"role": "user", "content": uc},
            {"role": "assistant", "content": out},
        ]
    elif "inputs" in item and "outputs" in item:
        inp_obj = item.get("inputs")
        out_obj = item.get("outputs")
        fam = item.get("family", "")
        if not isinstance(out_obj, dict) or not out_obj:
            return None
        clean_out = {k: v for k, v in out_obj.items() if not str(k).startswith("_")}
        if fam == "invalid" or clean_out.get("invalid") is True:
            ans_obj = {
                "invalid": True,
                "world_state": None,
                "reason": str(clean_out.get("reason") or "invalid_input"),
                "violated_constraints": list(clean_out.get("violated_constraints")
                                             or [str(clean_out.get("reason") or "invalid_input")]),
            }
        else:
            ans_obj = {"world_state": clean_out}
        user_txt = (inp_obj.get("prompt")
                    if isinstance(inp_obj, dict) and isinstance(inp_obj.get("prompt"), str)
                    else f"仿真器输入：{json.dumps(inp_obj, ensure_ascii=False)}")
        msgs = [
            {"role": "system", "content": _wm_contract.SYSTEM},
            {"role": "user", "content": user_txt},
            {"role": "assistant", "content": json.dumps(ans_obj, ensure_ascii=False)},
        ]
    else:
        return None

    # 归一文本中的旧闸门枚举，并识别多轮错误示范轮次
    last_only = bool(item.get("last_assistant_only", False))
    # 若对话中出现【教师诊断与指导】，其前面的所有 student assistant 轮均为初次错误尝试，全部 mask
    teacher_diag_idx = -1
    for i, m in enumerate(msgs):
        if m.get("role") == "user" and "【教师诊断与指导】" in str(m.get("content", "")):
            teacher_diag_idx = i
            break

    asst_indices = [i for i, m in enumerate(msgs) if m.get("role") == "assistant"]
    if not asst_indices:
        return None
    last_asst_idx = asst_indices[-1]

    has_trainable_asst = False
    for i, m in enumerate(msgs):
        if isinstance(m.get("content"), str):
            m["content"] = _normalize_legacy_gates_in_text(m["content"])
        if m.get("role") != "assistant":
            continue
        has_text = bool(str(m.get("content", "")).strip())
        has_tc = bool(m.get("tool_calls"))
        if not has_text and not has_tc:
            return None
        # 判断本轮 assistant 是否应屏蔽 loss
        mask_this = (m.get("loss") is False)
        if last_only and i != last_asst_idx:
            mask_this = True
        if teacher_diag_idx > 0 and i < teacher_diag_idx:
            mask_this = True
        if i + 1 < len(msgs) and _is_error_feedback_turn(msgs[i + 1]):
            mask_this = True
        if mask_this:
            m["loss"] = False
        else:
            has_trainable_asst = True

    if not has_trainable_asst:
        return None
    return msgs


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
    messages = normalize_item_messages(item)
    if not messages:
        return None
    input_ids, labels, has_assistant = [], [], False
    masked_asst_turns = 0
    for m in messages:
        seg = serialize_message(m, tokenizer)
        if m.get("role") == "assistant" and m.get("loss") is not False:
            has_assistant = True
            labels.extend(seg)
        else:
            if m.get("role") == "assistant":
                masked_asst_turns += 1
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
    if not any(x != -100 for x in labels):
        return None
    return {"input_ids": input_ids, "labels": labels,
            "attention_mask": [1] * len(input_ids),
            "_truncated": truncated, "_masked_asst_turns": masked_asst_turns}


def load_dataset(path, tokenizer, max_len):
    items = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    out, dropped, truncated, masked_turns = [], 0, 0, 0
    for it in items:
        s = format_sample(it, tokenizer, max_len)
        if s is None:
            dropped += 1
            continue
        if s.pop("_truncated", False):
            truncated += 1
        masked_turns += s.pop("_masked_asst_turns", 0)
        out.append(s)
    print(f"[Dataset] raw={len(items)} usable={len(out)} dropped={dropped} "
          f"head+tail_truncated={truncated} masked_bad_asst_turns={masked_turns}")
    return ListDataset(out)


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
    items = [json.loads(l) for l in open(args.data, encoding="utf-8") if l.strip()]
    usable = dropped = truncated = masked_turns = legacy_gates = 0
    max_tok = 0
    for i, s in enumerate(items):
        msgs = normalize_item_messages(s)
        if msgs is None:
            dropped += 1
            continue
        for m in msgs:
            if m.get("role") == "assistant" and m.get("loss") is not False:
                c = str(m.get("content", ""))
                if any(g in c for g in ("FOS>=1.5_pass", "FOS<1.5_FAIL", "pass_cut_negative")):
                    legacy_gates += 1
        fs = format_sample(s, tokenizer, args.max_len)
        if fs is None:
            dropped += 1
            continue
        usable += 1
        if fs.get("_truncated"):
            truncated += 1
        masked_turns += fs.get("_masked_asst_turns", 0)
        n_loss = sum(1 for x in fs["labels"] if x != -100)
        n_asst = sum(1 for m in msgs if m.get("role") == "assistant")
        max_tok = max(max_tok, len(fs["input_ids"]))
        if i < 6:
            print(f"  sample[{i}] roles={[m['role'] for m in msgs]} "
                  f"asst_turns={n_asst} masked={fs.get('_masked_asst_turns', 0)} "
                  f"tokens={len(fs['input_ids'])} loss_tokens={n_loss}")
    print(f"  total={len(items)} usable={usable} dropped={dropped} "
          f"truncated={truncated} masked_bad_asst_turns={masked_turns} "
          f"legacy_gates_remaining={legacy_gates}")
    print(f"  tokenizer vocab_size={tokenizer.vocab_size}  max_tokens={max_tok} (max_len={args.max_len})")
    if dropped > 0 or legacy_gates > 0:
        raise SystemExit(f"[FATAL] selftest failed: dropped={dropped}, legacy_gates={legacy_gates}")
    print("=================== SELFTEST OK ===================")


def main():
    ap = argparse.ArgumentParser(description="Virtu 世界模型最终版训练（自主思考/决策）")
    ap.add_argument("--base", default=os.environ.get("BASE", os.environ.get("BASE_DIR", "Qwen/Qwen3-8B")))
    ap.add_argument("--data", default=os.environ.get("DATA", REBALANCED_DATA))
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

    # 0) 数据：需要则构建；不存在则报错拒绝静默回退
    if args.build:
        args.data = build_final_data(args.n_agentic, with_replay=not args.no_replay)
    elif not os.path.exists(args.data):
        raise SystemExit(f"[FATAL] 指定数据集不存在，拒绝静默回退: {args.data}")

    args.base = resolve_base_path(args.base)

    print("=" * 62)
    print("  Virtu 世界模型 · 最终版训练（自主思考/决策）")
    print(f"  base      = {args.base}")
    print(f"  data      = {args.data}")
    print(f"  out       = {args.out}")
    print(f"  lora      = r={args.lora_r} alpha={args.lora_alpha}")
    print(f"  hyper     = lr={args.lr} epochs={args.epochs} bs={args.bs} accum={args.accum}")
    print(f"  resume    = {args.resume_adapter}")
    print("=" * 62)

    # 泄漏闸 + 量纲闸（加载路径）：开训/加载分词器前必须先过双重门禁
    from virtu_eval.contamination_check import assert_no_leak
    import corpus_unit_audit
    assert_no_leak(args.data)
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
