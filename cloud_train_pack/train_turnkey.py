#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cloud_train_pack/train_turnkey.py — Virtu 8.2B 工业大模型云端极速训练引擎 (One-Click Turnkey SFT)

设计原则：
1. 极限成本压缩：自动探测硬件，显存分档 (>=36GB 走纯 bf16-LoRA，<36GB 走 fp16-LoRA/QLoRA)；
2. 零冗余空转：启用 group_by_length=True 消除填充计算浪费；
3. 学习质量拉满：精确 assistant 段逐轮 loss 掩码 (System/User/Tool回执以及标记 "loss": false 的坏解轮次全置 -100，只学正确输出)；
4. 交付零摩擦：训练完毕自动生成指纹凭证并压缩打包 deliverable.tar.gz，方便一键拉取合并。
"""

import os
import re
import sys
import json
import time
import math
import shutil
import tarfile
import hashlib
import argparse
import tempfile
from types import SimpleNamespace

# 确保在导入 torch 前锁定单卡
if "--gpu-id" in sys.argv:
    idx = sys.argv.index("--gpu-id")
    if idx + 1 < len(sys.argv):
        os.environ["CUDA_VISIBLE_DEVICES"] = sys.argv[idx + 1]
else:
    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")

try:
    import torch
except ImportError:
    torch = None
try:
    from datasets import Dataset
except ImportError:
    Dataset = None
try:
    from peft import LoraConfig, PeftModel, get_peft_model, TaskType, prepare_model_for_kbit_training
except ImportError:
    LoraConfig = PeftModel = get_peft_model = TaskType = prepare_model_for_kbit_training = None
try:
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        TrainingArguments,
        Trainer,
        DataCollatorForSeq2Seq,
        TrainerCallback,
    )
except ImportError:
    AutoModelForCausalLM = AutoTokenizer = TrainingArguments = Trainer = DataCollatorForSeq2Seq = None
    class TrainerCallback:  # type: ignore[no-redef]
        pass

TARGET_MODULES = [
    "q_proj", "k_proj", "v_proj", "o_proj",
    "gate_proj", "up_proj", "down_proj"
]

EXPECTED_BASE_SPEC = {
    "hidden_size": 4096,
    "num_hidden_layers": 36,
    "vocab_size": 151936,
}

CANDIDATE_BASE_PATHS = [
    "/model/ModelScope/Qwen/Qwen3-8B",
    "/model/HuggingFace/Qwen/Qwen3-8B",
    "/root/virtu_train/models/Qwen3-8B",
    "/root/workspace/models/Qwen3-8B",
    "/root/models/Qwen3-8B",
    "/root/autodl-tmp/models/Qwen3-8B",
    "/root/damodel-tmp/models/Qwen3-8B",
    "/root/public-storage/model/Qwen/Qwen3-8B",
    "checkpoints/_base_qwen3_8b",
    "./models/Qwen3-8B",
]


def get_best_storage_dir() -> str:
    """探测磁盘空间，自动将模型缓存与权重锁定在剩余空间最大的数据盘路径。"""
    candidates = [
        "/root/virtu_train",
        "/root/workspace",
        "/root/data",
        "/root/damodel-tmp",
        "/root/autodl-tmp",
        "/mnt/data",
        "/mnt",
        "/root",
        "."
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
    print(f"[Storage] 自动探测最优存储盘: {best_dir} (剩余可用空间: {max_free_gb:.1f} GB)")
    return best_dir


class TimeBudgetCallback(TrainerCallback):
    """时间预算防超时守卫：达到时间上限时触发优雅提前停机保存。"""
    def __init__(self, max_minutes: float):
        self.max_seconds = max_minutes * 60.0 if max_minutes > 0 else float("inf")
        self.start_time = time.time()
        self.budget_stopped = False

    def on_step_end(self, args, state, control, **kwargs):
        elapsed = time.time() - self.start_time
        if elapsed > self.max_seconds:
            print(f"\n[TimeBudgetGuard] 已达到时间预算上限 ({elapsed/60:.1f}m > {self.max_seconds/60:.1f}m)，触发保存并优雅停止！")
            self.budget_stopped = True
            control.should_training_stop = True
            control.should_save = True


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(4 * 1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def resolve_resume_checkpoint(out_dir: str, resume_arg: str = None):
    """解析并校验断点续训目录；支持 'auto' 自动匹配 out/_checkpoints/checkpoint-*。"""
    if not resume_arg:
        return None
    raw = str(resume_arg).strip()
    if not raw:
        return None
    if raw.lower() == "auto":
        ckpt_root = os.path.join(out_dir, "_checkpoints")
        if not os.path.isdir(ckpt_root):
            raise RuntimeError(f"断点续训目录不存在: {ckpt_root}")
        candidates = []
        for entry in os.listdir(ckpt_root):
            m = re.fullmatch(r"checkpoint-(\d+)", entry)
            if not m:
                continue
            cand_dir = os.path.join(ckpt_root, entry)
            if os.path.isdir(cand_dir) and os.path.exists(os.path.join(cand_dir, "trainer_state.json")):
                candidates.append((int(m.group(1)), cand_dir))
        if not candidates:
            raise RuntimeError(f"未在 {ckpt_root} 找到含 trainer_state.json 的有效 checkpoint-*")
        candidates.sort(key=lambda item: item[0])
        return candidates[-1][1]
    if not os.path.isdir(raw) or not os.path.exists(os.path.join(raw, "trainer_state.json")):
        raise RuntimeError(f"指定断点目录无效或缺少 trainer_state.json: {raw}")
    return raw


def resolve_init_adapter(adapter_arg: str = None):
    """校验纯 safetensors 热启动 LoRA 目录，避开旧版 torch<2.6 的 .pt 限制。"""
    if not adapter_arg:
        return None
    raw = str(adapter_arg).strip()
    if not raw:
        return None
    st = os.path.join(raw, "adapter_model.safetensors")
    cfg = os.path.join(raw, "adapter_config.json")
    if not os.path.isdir(raw) or not os.path.exists(st) or not os.path.exists(cfg):
        raise RuntimeError(f"指定 --init-adapter 目录缺少 adapter_model.safetensors/adapter_config.json: {raw}")
    return raw


def assert_base_identity(base_path: str) -> dict:
    """强门禁：验证基座确为 Qwen3-8B (4096/36/151936) 且非 Instruct/Qwen2.5 错配权重。"""
    if not base_path:
        raise RuntimeError("[FATAL] 基座路径为空")
    norm_path = str(base_path).replace("\\", "/")
    if "instruct" in norm_path.lower():
        raise RuntimeError(f"[FATAL] 拒绝加载 Instruct 权重作为主力基座: {base_path}")
    cfg_path = os.path.join(base_path, "config.json")
    if not os.path.exists(cfg_path):
        raise RuntimeError(f"[FATAL] 基座缺少 config.json，无法验证血统: {cfg_path}")
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    name_or_path = str(cfg.get("_name_or_path", ""))
    if "instruct" in name_or_path.lower():
        raise RuntimeError(f"[FATAL] config.json[_name_or_path] 包含 Instruct ({name_or_path})，拒绝训练！")
    model_type = str(cfg.get("model_type", "")).lower()
    if model_type and "qwen3" not in model_type:
        raise RuntimeError(f"[FATAL] 基座 model_type={model_type!r} 非 qwen3 系列: {base_path}")
    mismatches = []
    for k, expected in EXPECTED_BASE_SPEC.items():
        actual = cfg.get(k)
        if actual != expected:
            mismatches.append(f"{k}={actual!r}(expected {expected!r})")
    if mismatches:
        raise RuntimeError(f"[FATAL] 基座架构维度不匹配 Qwen3-8B: {', '.join(mismatches)} ({base_path})")
    print(
        f"[BaseGate] 基座血统校验通过: model_type={cfg.get('model_type', 'qwen3')} | "
        f"h={cfg.get('hidden_size')}, L={cfg.get('num_hidden_layers')}, V={cfg.get('vocab_size')}"
    )
    return cfg


def verify_ledger_if_present(data_path: str, ledger_arg: str = None) -> str:
    """校验语料 SHA256 与 ledger_json 是否一致；发现篡改/不匹配立即以退出码 2 终止。"""
    actual_sha = sha256_file(data_path)
    data_basename = os.path.basename(data_path)

    if ledger_arg:
        if not os.path.exists(ledger_arg):
            print(f"[FATAL] 指定的 --ledger 文件不存在: {ledger_arg}", file=sys.stderr)
            raise SystemExit(2)
        candidate_ledger = ledger_arg
        strict_ledger = True
    else:
        sibling = os.path.join(os.path.dirname(os.path.abspath(data_path)), "dataset_ledger.json")
        candidate_ledger = sibling if os.path.exists(sibling) else None
        strict_ledger = False

    if candidate_ledger:
        with open(candidate_ledger, "r", encoding="utf-8") as f:
            ledger = json.load(f)
        expected_sha = None
        if isinstance(ledger, dict):
            files_map = ledger.get("files")
            if isinstance(files_map, dict) and data_basename in files_map:
                entry = files_map[data_basename]
                expected_sha = entry.get("sha256") if isinstance(entry, dict) else entry
            elif strict_ledger:
                expected_sha = ledger.get("output_sha256") or ledger.get("sha256")
            else:
                target_name = os.path.basename(str(ledger.get("output_path") or ledger.get("dataset") or ""))
                if target_name == data_basename or not target_name:
                    expected_sha = ledger.get("output_sha256") or ledger.get("sha256")

        if expected_sha and expected_sha.lower() != actual_sha.lower():
            print(
                f"[FATAL] 语料 SHA256 与 ledger 不匹配 ({candidate_ledger})! "
                f"expected={expected_sha[:16]} actual={actual_sha[:16]}",
                file=sys.stderr,
            )
            raise SystemExit(2)
        if expected_sha:
            print(f"[LedgerGate] 语料 SHA256 校验通过: {actual_sha[:16]}... ({candidate_ledger})")

    sha_sidecar = data_path + ".sha256"
    if os.path.exists(sha_sidecar):
        with open(sha_sidecar, "r", encoding="utf-8") as sf:
            expected_sidecar = sf.read().strip().split()[0]
        if expected_sidecar and expected_sidecar.lower() != actual_sha.lower():
            print(
                f"[FATAL] 语料 SHA256 与 sidecar 不匹配 ({sha_sidecar})! "
                f"expected={expected_sidecar[:16]} actual={actual_sha[:16]}",
                file=sys.stderr,
            )
            raise SystemExit(2)
        print(f"[LedgerGate] sidecar .sha256 校验通过: {actual_sha[:16]}...")

    return actual_sha


def find_or_download_base(specified_base: str = None) -> str:
    if specified_base and os.path.exists(specified_base):
        print(f"[Base] 使用指定基座路径: {specified_base}")
        return specified_base

    for p in CANDIDATE_BASE_PATHS:
        if os.path.exists(p) and os.path.exists(os.path.join(p, "config.json")):
            print(f"[Base] 探测到已有 8.2B 基座权重: {p} (免下载，0 带宽成本)")
            return p

    best_dir = get_best_storage_dir()
    target_dir = os.path.join(best_dir, "models", "Qwen3-8B")
    os.makedirs(os.path.dirname(target_dir), exist_ok=True)

    print(f"[Base] 未探测到本地基座，正在通过 ModelScope 高速拉取 Qwen/Qwen3-8B -> {target_dir} ...")
    try:
        from modelscope import snapshot_download
        downloaded = snapshot_download("Qwen/Qwen3-8B", local_dir=target_dir)
        return downloaded
    except Exception as e:
        print(f"[Base] ModelScope 下载失败 ({e})，尝试 HuggingFace 国内镜像站 ...")
        os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
        from huggingface_hub import snapshot_download
        downloaded = snapshot_download("Qwen/Qwen3-8B", local_dir=target_dir)
        return downloaded


def format_chatml_sample(rec: dict, tokenizer, max_length: int = 4096):
    """严格 ChatML 渲染与多轮对话逐轮精确 Loss 掩码。"""
    raw_msgs = list(rec.get("messages", []))
    while raw_msgs and raw_msgs[-1].get("role") != "assistant":
        raw_msgs.pop()
    if not raw_msgs:
        return None

    tools = rec.get("tools", [])
    last_only = bool(rec.get("last_assistant_only", False))
    assistant_msgs = [m for m in raw_msgs if m.get("role") == "assistant"]
    if not assistant_msgs:
        return None

    assistant_loss_flags = []
    for idx, m in enumerate(assistant_msgs):
        if last_only and idx < len(assistant_msgs) - 1:
            assistant_loss_flags.append(False)
        elif m.get("loss") is False:
            assistant_loss_flags.append(False)
        else:
            assistant_loss_flags.append(True)

    has_explicit_think = any("<think>" in str(m.get("content", "")) for m in assistant_msgs)

    full_text = None
    if tools and hasattr(tokenizer, "apply_chat_template"):
        try:
            full_text = tokenizer.apply_chat_template(
                raw_msgs, tools=tools, tokenize=False, add_generation_prompt=False,
                enable_thinking=has_explicit_think,
            )
        except Exception:
            try:
                full_text = tokenizer.apply_chat_template(
                    raw_msgs, tools=tools, tokenize=False, add_generation_prompt=False
                )
            except Exception:
                full_text = None

    if full_text is None:
        blocks = []
        for m in raw_msgs:
            role = m.get("role", "user")
            content = str(m.get("content", ""))
            tc = m.get("tool_calls")
            if tc:
                content = (content + "\n" if content else "") + json.dumps(tc, ensure_ascii=False)
            blocks.append(f"<|im_start|>{role}\n{content}<|im_end|>\n")
        full_text = "".join(blocks)
    elif not has_explicit_think:
        full_text = re.sub(r"<\|im_start\|>assistant\n<think>\s*</think>\s*", "<|im_start|>assistant\n", full_text)

    enc = tokenizer(
        full_text,
        max_length=max_length,
        truncation=True,
        return_offsets_mapping=True,
        add_special_tokens=False,
    )
    input_ids = enc["input_ids"]
    offsets = enc["offset_mapping"]
    labels = [-100] * len(input_ids)

    matches = list(re.finditer(r"<\|im_start\|>assistant\n", full_text))
    for turn_idx, match in enumerate(matches):
        train_this_turn = assistant_loss_flags[turn_idx] if turn_idx < len(assistant_loss_flags) else True
        if not train_this_turn:
            continue
        start_char = match.end()
        end_match = re.search(r"<\|im_end\|>", full_text[start_char:])
        end_token_char = start_char + end_match.end() if end_match else len(full_text)

        for i, (tok_start, tok_end) in enumerate(offsets):
            if tok_end > tok_start and tok_start >= start_char and tok_end <= end_token_char:
                labels[i] = input_ids[i]

    if all(l == -100 for l in labels):
        return None

    return {
        "input_ids": input_ids,
        "labels": labels,
        "attention_mask": [1] * len(input_ids),
    }


def load_dataset(dataset_path: str, tokenizer, max_length: int = 4096) -> Dataset:
    print(f"[Data] 加载并解析工业 SFT 语料: {dataset_path}")
    samples = []
    skipped = 0
    with open(dataset_path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                item = format_chatml_sample(rec, tokenizer, max_length)
                if item:
                    samples.append(item)
                else:
                    skipped += 1
            except Exception:
                skipped += 1

    print(f"[Data] 有效训练样本: {len(samples)} 条 (跳过/不符合: {skipped} 条)")
    return Dataset.from_list(samples)


def _ensure_repo_paths() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    for p in (here, root, os.path.join(here, "scripts"), os.path.join(root, "scripts")):
        if os.path.exists(p) and p not in sys.path:
            sys.path.insert(0, p)


def run_selftest() -> int:
    """离线零 GPU 自检：验证基座门禁、时间预算停机、ChatML/工具掩码、Ledger 校验与防污染/单位门。"""
    _ensure_repo_paths()
    from virtu_eval.contamination_check import assert_no_leak
    from corpus_unit_audit import assert_units_clean

    with tempfile.TemporaryDirectory(prefix="virtu_turnkey_selftest_") as td:
        # 1. 基座血统门禁 (正反双证)
        valid_base = os.path.join(td, "Qwen3-8B")
        os.makedirs(valid_base, exist_ok=True)
        with open(os.path.join(valid_base, "config.json"), "w", encoding="utf-8") as f:
            json.dump({
                "_name_or_path": "Qwen/Qwen3-8B",
                "model_type": "qwen3",
                **EXPECTED_BASE_SPEC,
            }, f)
        assert_base_identity(valid_base)

        instruct_base = os.path.join(td, "Qwen3-8B-Instruct")
        os.makedirs(instruct_base, exist_ok=True)
        with open(os.path.join(instruct_base, "config.json"), "w", encoding="utf-8") as f:
            json.dump({"_name_or_path": "Qwen/Qwen3-8B-Instruct", "model_type": "qwen3", **EXPECTED_BASE_SPEC}, f)
        try:
            assert_base_identity(instruct_base)
            raise AssertionError("assert_base_identity 未拦截 Instruct 路径")
        except RuntimeError:
            pass

        wrong_dim_base = os.path.join(td, "Qwen25-7B")
        os.makedirs(wrong_dim_base, exist_ok=True)
        with open(os.path.join(wrong_dim_base, "config.json"), "w", encoding="utf-8") as f:
            json.dump({"_name_or_path": "Qwen/Qwen2.5-7B", "model_type": "qwen2", "hidden_size": 3584, "num_hidden_layers": 28, "vocab_size": 152064}, f)
        try:
            assert_base_identity(wrong_dim_base)
            raise AssertionError("assert_base_identity 未拦截错误维度权重")
        except RuntimeError:
            pass

        # 2. TimeBudgetCallback 超时状态标记
        cb = TimeBudgetCallback(max_minutes=1e-6)
        assert cb.budget_stopped is False
        time.sleep(0.01)
        ctrl = SimpleNamespace(should_training_stop=False, should_save=False)
        cb.on_step_end(None, None, ctrl)
        assert cb.budget_stopped is True
        assert ctrl.should_training_stop is True
        assert ctrl.should_save is True

        # 3. ChatML + 工具调用轮次 Loss 掩码验证
        class _CharOffsetTokenizer:
            def __call__(self, text, max_length=2048, truncation=True, return_offsets_mapping=True, add_special_tokens=False):
                text = text[:max_length] if truncation else text
                ids = [ord(ch) % 150000 for ch in text]
                offsets = [(i, i + 1) for i in range(len(text))]
                return {"input_ids": ids, "offset_mapping": offsets}

        tok = _CharOffsetTokenizer()
        sample = {
            "messages": [
                {"role": "system", "content": "You are Virtu CAD/CAM expert."},
                {"role": "user", "content": "Measure flange bore diameter."},
                {
                    "role": "assistant",
                    "content": '<tool_call>\n{"name": "cadcam_universal_geometry", "arguments": {"part": "flange"}}\n</tool_call>',
                },
                {"role": "tool", "content": '{"bore_mm": 40.0}'},
                {"role": "assistant", "content": "Bore diameter verified at 40.0 mm."},
            ]
        }
        encoded = format_chatml_sample(sample, tok, max_length=2048)
        assert encoded is not None, "format_chatml_sample 返回 None"
        valid_labels = sum(1 for x in encoded["labels"] if x != -100)
        assert valid_labels >= 8, f"有效训练标签过少: {valid_labels}"

        # 4. Ledger + 防污染 + 单位审计
        clean_jsonl = os.path.join(td, "selftest_corpus.jsonl")
        with open(clean_jsonl, "w", encoding="utf-8") as f:
            f.write(json.dumps({
                "messages": [
                    {"role": "user", "content": "计算薄壁圆筒壁厚 t_min 与应力校验（合成自检样例）"},
                    {"role": "assistant", "content": "由薄壁公式得 sigma = p*R/t，取 FOS >= 1.5 后确认几何尺寸合格。"},
                ]
            }, ensure_ascii=False) + "\n")

        good_ledger = os.path.join(td, "dataset_ledger.json")
        real_sha = sha256_file(clean_jsonl)
        with open(good_ledger, "w", encoding="utf-8") as f:
            json.dump({"output_path": clean_jsonl, "output_sha256": real_sha}, f)
        assert verify_ledger_if_present(clean_jsonl, good_ledger) == real_sha

        bad_ledger = os.path.join(td, "bad_ledger.json")
        with open(bad_ledger, "w", encoding="utf-8") as f:
            json.dump({"output_path": clean_jsonl, "output_sha256": "0" * 64}, f)
        import contextlib
        import io
        captured = io.StringIO()
        try:
            with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
                verify_ledger_if_present(clean_jsonl, bad_ledger)
            raise AssertionError("verify_ledger_if_present 未拦截篡改 SHA256")
        except SystemExit as exc:
            assert exc.code == 2
            assert "FATAL" in captured.getvalue()

        assert_no_leak(clean_jsonl)
        assert_units_clean(clean_jsonl)

        # 5. resolve_resume_checkpoint (auto 选择最高步数 + 空目录报错门禁)
        resume_root = os.path.join(td, "resume_out")
        os.makedirs(os.path.join(resume_root, "_checkpoints", "checkpoint-100"), exist_ok=True)
        with open(os.path.join(resume_root, "_checkpoints", "checkpoint-100", "trainer_state.json"), "w", encoding="utf-8") as f:
            f.write("{}")
        os.makedirs(os.path.join(resume_root, "_checkpoints", "checkpoint-283"), exist_ok=True)
        with open(os.path.join(resume_root, "_checkpoints", "checkpoint-283", "trainer_state.json"), "w", encoding="utf-8") as f:
            f.write("{}")
        os.makedirs(os.path.join(resume_root, "_checkpoints", "checkpoint-999"), exist_ok=True)
        picked = resolve_resume_checkpoint(resume_root, "auto")
        assert os.path.basename(picked) == "checkpoint-283", f"picked={picked}"
        try:
            resolve_resume_checkpoint(os.path.join(td, "missing_out"), "auto")
            raise AssertionError("resolve_resume_checkpoint 未拦截缺失断点目录")
        except RuntimeError:
            pass

        init_dir = os.path.join(td, "init_lora")
        os.makedirs(init_dir, exist_ok=True)
        for fn in ("adapter_model.safetensors", "adapter_config.json"):
            with open(os.path.join(init_dir, fn), "w", encoding="utf-8") as f:
                f.write("{}")
        assert resolve_init_adapter(init_dir) == init_dir
        try:
            resolve_init_adapter(os.path.join(td, "empty_init"))
            raise AssertionError("resolve_init_adapter 未拦截缺失权重目录")
        except RuntimeError:
            pass

    print("[SELFTEST] PASS: base_gate / time_budget / chatml_tool_mask / ledger / leak_unit_gates / resume_gate")
    return 0


def train():
    parser = argparse.ArgumentParser(description="Virtu 云端高性价比一键训练脚本")
    parser.add_argument("--base", default=None, help="基座模型路径")
    parser.add_argument("--data", default="dataset/virtu_capability_sft_v5.jsonl", help="SFT 语料文件")
    parser.add_argument("--ledger", default=None, help="语料指纹 ledger JSON 路径 (可选，显式提供时强制匹配 SHA256)")
    parser.add_argument("--out", default="output/virtu_lora_master", help="LoRA 产物输出路径")
    parser.add_argument("--epochs", type=float, default=2.0, help="训练轮数")
    parser.add_argument("--max-steps", type=int, default=-1, help="最大训练步数 (>0 时覆盖 epochs，用于冒烟实测)")
    parser.add_argument("--lr", type=float, default=1.5e-4, help="学习率")
    parser.add_argument("--batch", type=int, default=1, help="单设备 batch size")
    parser.add_argument("--grad-accum", type=int, default=16, help="梯度累积步数")
    parser.add_argument("--max-length", type=int, default=4096, help="最大上下文截断长度")
    parser.add_argument("--max-hours", type=float, default=1.5, help="最大预算时间 (小时)")
    parser.add_argument("--qlora", action="store_true", help="强制启用 4-bit QLoRA")
    parser.add_argument("--resume", default=None, help="断点续训路径 (传 'auto' 自动选取 out/_checkpoints 最新 checkpoint，或传具体路径)")
    parser.add_argument("--init-adapter", default=None, help="安全热启动 LoRA 适配器目录 (仅加载 safetensors 权重继续 SFT)")
    parser.add_argument("--selftest", action="store_true", help="运行零 GPU 离线门禁与掩码自检")
    parser.add_argument("--gpu-id", default="0", help="指定可见 GPU 编号")
    args = parser.parse_args()

    if args.selftest:
        raise SystemExit(run_selftest())

    resume_ckpt = resolve_resume_checkpoint(args.out, args.resume)
    init_adapter_dir = resolve_init_adapter(args.init_adapter)
    if resume_ckpt and init_adapter_dir:
        raise SystemExit("[FATAL] --resume 与 --init-adapter 不可同时指定")
    if resume_ckpt:
        print(f"[Resume] 启用断点续训，将加载优化器与步数状态: {resume_ckpt}")
    if init_adapter_dir:
        print(f"[WarmStart] 启用 safetensors LoRA 热启动: {init_adapter_dir}")

    if not os.path.exists(args.data):
        raise SystemExit(
            f"[FATAL] --data={args.data} 不存在。拒绝自动回退到其它语料；"
            f"可用的有: " + ", ".join(c for c in [
                "dataset/virtu_impeller_retrain_sft.jsonl",
                "dataset/virtu_impeller_fix_sft.jsonl",
                "dataset/virtu_capability_sft_v5.jsonl",
                "dataset/virtu_v100_production_sft.jsonl",
                "dataset/virtu_gold_production_sft.jsonl"] if os.path.exists(c)))
    _ensure_repo_paths()
    from virtu_eval.contamination_check import assert_no_leak
    from corpus_unit_audit import assert_units_clean
    assert_no_leak(args.data)
    assert_units_clean(args.data)
    verified_data_sha = verify_ledger_if_present(args.data, args.ledger)

    if torch is None or Dataset is None or LoraConfig is None or AutoTokenizer is None:
        raise SystemExit("[FATAL] 缺少训练依赖 (torch/datasets/peft/transformers)，请先确认虚拟环境。")

    t_start = time.time()
    base_path = find_or_download_base(args.base)
    assert_base_identity(base_path)

    if not torch.cuda.is_available():
        raise SystemExit("[FATAL] 未检测到可用 CUDA GPU，无法进行训练！")

    gpu_name = torch.cuda.get_device_name(0)
    total_vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
    print(f"[Hardware] 检测到 GPU: {gpu_name} | 显存: {total_vram_gb:.2f} GB")

    major_cc = torch.cuda.get_device_capability(0)[0]
    has_bf16 = (major_cc >= 8) and getattr(torch.cuda, "is_bf16_supported", lambda: False)()
    compute_dtype = torch.bfloat16 if has_bf16 else torch.float16
    use_qlora = bool(args.qlora) or (total_vram_gb < 22.0)
    mode_str = f"QLoRA (4-bit, {compute_dtype})" if use_qlora else f"Full {compute_dtype} LoRA"
    print(f"[Strategy] 架构主版本: sm_{major_cc}x | 硬件支持 bf16: {has_bf16} | 计算精度: {compute_dtype} | 选型: {mode_str}")

    tokenizer = AutoTokenizer.from_pretrained(base_path, trust_remote_code=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token

    model_kwargs = {"trust_remote_code": True}
    if use_qlora:
        from transformers import BitsAndBytesConfig
        model_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=compute_dtype,
            bnb_4bit_use_double_quant=True,
        )
        model_kwargs["device_map"] = {"": 0}
    else:
        model_kwargs["torch_dtype"] = compute_dtype
        model_kwargs["device_map"] = {"": 0}

    model_kwargs["attn_implementation"] = "sdpa"

    print(f"[Model] 正在加载基座权重: {base_path} ...")
    model = AutoModelForCausalLM.from_pretrained(base_path, **model_kwargs)

    if use_qlora:
        model = prepare_model_for_kbit_training(model)

    model.gradient_checkpointing_enable()

    if init_adapter_dir:
        if PeftModel is None:
            raise SystemExit("[FATAL] 缺少 peft.PeftModel，无法加载 --init-adapter")
        model = PeftModel.from_pretrained(model, init_adapter_dir, is_trainable=True)
        if hasattr(model, "enable_input_require_grads"):
            model.enable_input_require_grads()
    else:
        lora_cfg = LoraConfig(
            r=32,
            lora_alpha=64,
            lora_dropout=0.05,
            target_modules=TARGET_MODULES,
            bias="none",
            task_type=TaskType.CAUSAL_LM,
        )
        model = get_peft_model(model, lora_cfg)
    trainable_params, all_param = model.get_nb_trainable_parameters()
    if trainable_params <= 0:
        raise RuntimeError(f"[FATAL] LoRA 可训练参数为 0，无法继续训练 (init_adapter={init_adapter_dir})")
    print(f"[LoRA] 可训练参数: {trainable_params:,} / {all_param:,} ({trainable_params/all_param*100:.2f}%)")

    dataset = load_dataset(args.data, tokenizer, args.max_length)

    os.makedirs(args.out, exist_ok=True)
    training_args = TrainingArguments(
        output_dir=os.path.join(args.out, "_checkpoints"),
        num_train_epochs=args.epochs,
        max_steps=args.max_steps,
        per_device_train_batch_size=args.batch,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        warmup_ratio=0.05,
        logging_steps=10,
        save_strategy="steps",
        save_steps=100,
        save_total_limit=2,
        bf16=has_bf16,
        fp16=not has_bf16,
        group_by_length=True,
        report_to="none",
        dataloader_num_workers=0,
        optim="paged_adamw_8bit" if use_qlora else "adamw_torch",
    )

    budget_cb = TimeBudgetCallback(args.max_hours * 60)
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        data_collator=DataCollatorForSeq2Seq(tokenizer, pad_to_multiple_of=8, return_tensors="pt", padding=True),
        callbacks=[budget_cb],
    )

    print("\n" + "="*70)
    print("🚀 开始极速模型训练 ... (预计耗时: 30 ~ 50 分钟)")
    print("="*70 + "\n")

    train_res = trainer.train(resume_from_checkpoint=resume_ckpt)

    if train_res.training_loss is None or math.isnan(train_res.training_loss) or train_res.training_loss <= 0:
        raise RuntimeError(f"[FATAL] 训练损失异常 (Loss={train_res.training_loss})，未正常收敛！")
    print(f"[Loss] 训练收敛检验通过：最终 Loss = {train_res.training_loss:.4f}")

    final_adapter_dir = os.path.join(args.out, "final_adapter")
    print(f"\n[Save] 正在保存最终 LoRA 适配器 -> {final_adapter_dir}")
    model.save_pretrained(final_adapter_dir)
    tokenizer.save_pretrained(final_adapter_dir)

    safetensor_file = os.path.join(final_adapter_dir, "adapter_model.safetensors")
    if not os.path.exists(safetensor_file):
        raise RuntimeError(f"[FATAL] 缺少适配器权重文件: {safetensor_file}")
    adapter_sha = sha256_file(safetensor_file)
    dataset_sha = verified_data_sha or sha256_file(args.data)
    status_str = "TIME_BUDGET_STOPPED" if budget_cb.budget_stopped else "COMPLETED"

    deliverable_tar = os.path.join(args.out, "virtu_lora_deliverable.tar.gz")
    receipt = {
        "model_brand": "Virtu-Omni-CAD-CAM-8.2B",
        "base_model": base_path,
        "base_spec": EXPECTED_BASE_SPEC,
        "dataset_path": args.data,
        "dataset_sha256": dataset_sha,
        "adapter_sha256": adapter_sha,
        "lora_r": 32,
        "lora_alpha": 64,
        "target_modules": TARGET_MODULES,
        "precision_mode": mode_str,
        "total_train_samples": len(dataset),
        "global_step": int(getattr(train_res, "global_step", 0)),
        "max_steps": int(args.max_steps),
        "resumed_from": resume_ckpt,
        "init_adapter": init_adapter_dir,
        "total_train_seconds": round(time.time() - t_start, 2),
        "train_loss": float(train_res.training_loss),
        "final_train_loss": float(train_res.training_loss),
        "stopped_by_time_budget": bool(budget_cb.budget_stopped),
        "completed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "status": status_str,
    }

    receipt_path = os.path.join(final_adapter_dir, "training_receipt.json")
    out_receipt_path = os.path.join(args.out, "training_receipt.json")
    for rp in (receipt_path, out_receipt_path):
        with open(rp, "w", encoding="utf-8") as rf:
            json.dump(receipt, rf, ensure_ascii=False, indent=2)

    print(f"[Archive] 正在打包交付件 -> {deliverable_tar}")
    with tarfile.open(deliverable_tar, "w:gz") as tar:
        tar.add(final_adapter_dir, arcname="virtu_lora_adapter")

    tar_sha = sha256_file(deliverable_tar)
    receipt["deliverable_sha256"] = tar_sha
    for rp in (receipt_path, out_receipt_path):
        with open(rp, "w", encoding="utf-8") as rf:
            json.dump(receipt, rf, ensure_ascii=False, indent=2)
    with open(deliverable_tar + ".sha256", "w", encoding="utf-8") as sf:
        sf.write(f"{tar_sha}  {os.path.basename(deliverable_tar)}\n")

    sz_mb = os.path.getsize(deliverable_tar) / (1024**2)
    print("\n" + "="*70)
    if budget_cb.budget_stopped:
        print(f"⚠️ 训练因时间预算上限提前保存停机！耗时: {(time.time() - t_start)/60:.1f} 分钟 | Loss: {train_res.training_loss:.4f}")
    else:
        print(f"🎉 训练圆满完成！耗时: {(time.time() - t_start)/60:.1f} 分钟 | 最终 Loss: {train_res.training_loss:.4f}")
    print(f"📦 产物交付包: {deliverable_tar} ({sz_mb:.1f} MB) | sha256={tar_sha[:16]}...")
    print(f"🔑 权重指纹 (SHA256): {adapter_sha[:16]}...")
    print("="*70 + "\n")

    if budget_cb.budget_stopped:
        raise SystemExit(3)


if __name__ == "__main__":
    train()
