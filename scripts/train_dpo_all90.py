#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scripts/train_dpo_all90.py — All-90 受控 DPO 偏好对齐训练脚本 (beta=0.1, lr=5e-6, epochs=1)

强制门禁：
  1. DPO 样本对完整性检查 (chosen != rejected, 工具面合法, system <= 702B)；
  2. assert_no_leak + assert_units_clean；
  3. 基座血统门禁 (Qwen3-8B 非 Instruct 4096/36/151936，或显式 --lineage 14b)；
  4. TimeBudgetCallback 防超时停机回执 (TIME_BUDGET_STOPPED -> exit 3)。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from gate_all90_dataset import (
    SYSTEM_PROMPT_MAX_BYTES,
    _extract_tool_invocations,
    load_known_tool_names,
)
from virtu_eval.contamination_check import assert_no_leak
from corpus_unit_audit import assert_units_clean

try:
    from transformers import TrainerCallback
except ImportError:
    class TrainerCallback:  # type: ignore[no-redef]
        pass

EXPECTED_QWEN3_8B_SPEC = {
    "hidden_size": 4096,
    "num_hidden_layers": 36,
    "vocab_size": 151936,
}


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


class TimeBudgetCallback(TrainerCallback):
    def __init__(self, max_minutes: float):
        self.max_seconds = max_minutes * 60.0 if max_minutes > 0 else float("inf")
        self.start_time = time.time()
        self.budget_stopped = False

    def on_step_end(self, args, state, control, **kwargs):
        elapsed = time.time() - self.start_time
        if elapsed > self.max_seconds:
            self.budget_stopped = True
            control.should_training_stop = True
            control.should_save = True


def assert_base_identity(base_path: str, lineage: str = "qwen3-8b") -> dict:
    if not base_path:
        raise RuntimeError("[FATAL] --base 为空")
    if "instruct" in str(base_path).lower():
        raise RuntimeError(f"[FATAL] 拒绝将 Instruct 模型用于 DPO 训练: {base_path}")
    cfg_path = os.path.join(base_path, "config.json")
    if not os.path.exists(cfg_path):
        raise RuntimeError(f"[FATAL] 基座缺少 config.json: {cfg_path}")
    cfg = json.loads(Path(cfg_path).read_text(encoding="utf-8"))
    if "instruct" in str(cfg.get("_name_or_path", "")).lower():
        raise RuntimeError(f"[FATAL] config.json[_name_or_path] 包含 Instruct: {cfg.get('_name_or_path')}")
    if lineage == "qwen3-8b":
        mtype = str(cfg.get("model_type", "")).lower()
        if mtype and "qwen3" not in mtype:
            raise RuntimeError(f"[FATAL] 基座 model_type={mtype!r} 非 qwen3")
        for k, v in EXPECTED_QWEN3_8B_SPEC.items():
            if cfg.get(k) != v:
                raise RuntimeError(f"[FATAL] 基座维度不匹配 {k}={cfg.get(k)!r} != {v!r}")
    else:
        if int(cfg.get("hidden_size") or 0) < 4096 or int(cfg.get("num_hidden_layers") or 0) < 36:
            raise RuntimeError(f"[FATAL] 14B 基座维度异常: {cfg}")
    return cfg


def validate_dpo_pairs(dpo_jsonl: str | Path) -> List[Dict[str, Any]]:
    known = load_known_tool_names()
    rows: List[Dict[str, Any]] = []
    with open(dpo_jsonl, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            s = line.strip()
            if not s:
                continue
            obj = json.loads(s)
            prompt = obj.get("prompt")
            chosen = obj.get("chosen")
            rejected = obj.get("rejected")
            if not prompt or not chosen or not rejected:
                raise ValueError(f"[FATAL] DPO 第 {idx} 行缺少 prompt/chosen/rejected")
            if chosen == rejected:
                raise ValueError(f"[FATAL] DPO 第 {idx} 行 chosen 与 rejected 完全相同，无效偏好对")

            if isinstance(prompt, list):
                for m in prompt:
                    if isinstance(m, dict) and m.get("role") == "system":
                        sb = len(str(m.get("content") or "").encode("utf-8"))
                        if sb > SYSTEM_PROMPT_MAX_BYTES:
                            raise ValueError(f"[FATAL] DPO 第 {idx} 行 system prompt {sb}B > {SYSTEM_PROMPT_MAX_BYTES}B")

            chosen_txt = chosen[-1].get("content", "") if isinstance(chosen, list) else str(chosen)
            dummy_rec = {"messages": [{"role": "assistant", "content": chosen_txt}]}
            for t_name, _ in _extract_tool_invocations(dummy_rec):
                if t_name not in known:
                    raise ValueError(f"[FATAL] DPO 第 {idx} 行 chosen 引用未知工具 {t_name!r}")
            rows.append(obj)

    if not rows:
        raise ValueError(f"[FATAL] DPO 数据集为空: {dpo_jsonl}")
    return rows


def resolve_dpo_get_batch_fn(orig_dpo_get_batch, orig_trainer_get_batch):
    """Preserve real iterator batches across trl/transformers Trainer.get_batch_samples changes."""
    if orig_dpo_get_batch is None or orig_dpo_get_batch is orig_trainer_get_batch:
        return None

    def safe_get_batch(self, *a, **kw):
        try:
            return orig_dpo_get_batch(self, *a, **kw)
        except TypeError:
            if orig_trainer_get_batch is not None:
                return orig_trainer_get_batch(self, *a, **kw)
            raise

    return safe_get_batch


def assert_nonzero_global_step(train_result: Any, trainer_state: Any = None) -> int:
    """Fail closed if DPOTrainer exited with 0 optimizer steps (e.g., empty epoch_iterator)."""
    global_step = int(
        getattr(train_result, "global_step", 0)
        or getattr(trainer_state, "global_step", 0)
        or 0
    )
    if global_step <= 0:
        raise RuntimeError(
            "[FATAL] DPO 训练 global_step=0，未执行任何真实梯度更新，拒绝写 COMPLETED 回执！"
        )
    return global_step


def run_dpo_training(args) -> int:
    if not os.path.exists(args.data):
        raise SystemExit(f"[FATAL] --data={args.data} 不存在")
    if not os.path.exists(args.adapter):
        raise SystemExit(f"[FATAL] --adapter={args.adapter} 不存在")

    assert_no_leak(args.data)
    assert_units_clean(args.data)
    pairs = validate_dpo_pairs(args.data)
    assert_base_identity(args.base, lineage=args.lineage)
    data_sha = sha256_file(args.data)

    import torch
    from datasets import Dataset
    from peft import PeftModel, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, Trainer
    from trl import DPOConfig, DPOTrainer

    if not torch.cuda.is_available():
        raise SystemExit("[FATAL] DPO 训练需要可用 CUDA GPU")

    safe_get_batch = resolve_dpo_get_batch_fn(
        getattr(DPOTrainer, "get_batch_samples", None),
        getattr(Trainer, "get_batch_samples", None),
    )
    if safe_get_batch is not None:
        DPOTrainer.get_batch_samples = safe_get_batch

    tokenizer = AutoTokenizer.from_pretrained(args.base, trust_remote_code=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token

    has_bf16 = torch.cuda.get_device_capability(0)[0] >= 8 and getattr(torch.cuda, "is_bf16_supported", lambda: False)()
    compute_dtype = torch.bfloat16 if has_bf16 else torch.float16
    model_kwargs: Dict[str, Any] = {"trust_remote_code": True, "device_map": {"": 0}, "attn_implementation": "sdpa"}
    if args.qlora:
        model_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=compute_dtype, bnb_4bit_use_double_quant=True,
        )
    else:
        model_kwargs["torch_dtype"] = compute_dtype

    base_model = AutoModelForCausalLM.from_pretrained(args.base, **model_kwargs)
    if args.qlora:
        base_model = prepare_model_for_kbit_training(base_model)
    model = PeftModel.from_pretrained(base_model, args.adapter, is_trainable=True)
    if hasattr(model, "enable_input_require_grads"):
        model.enable_input_require_grads()

    formatted = []
    for row in pairs:
        p = row["prompt"]
        c = row["chosen"]
        r = row["rejected"]
        if isinstance(p, list) and hasattr(tokenizer, "apply_chat_template"):
            p = tokenizer.apply_chat_template(p, tokenize=False, add_generation_prompt=True)
        if isinstance(c, list):
            c = c[-1].get("content", "") if c else ""
        if isinstance(r, list):
            r = r[-1].get("content", "") if r else ""
        formatted.append({"prompt": str(p), "chosen": str(c), "rejected": str(r)})

    ds = Dataset.from_list(formatted)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    final_dir = out_dir / "final_dpo_adapter"

    dpo_cfg = DPOConfig(
        output_dir=str(out_dir / "_checkpoints"),
        per_device_train_batch_size=args.batch,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        num_train_epochs=args.epochs,
        max_steps=args.max_steps,
        beta=args.beta,
        max_length=args.max_length,
        logging_steps=5,
        save_strategy="no",
        bf16=has_bf16,
        fp16=not has_bf16,
        gradient_checkpointing=True,
        report_to="none",
        optim="paged_adamw_8bit" if args.qlora else "adamw_torch",
    )

    budget_cb = TimeBudgetCallback(args.max_hours * 60.0)
    trainer = DPOTrainer(
        model=model,
        ref_model=None,
        train_dataset=ds,
        processing_class=tokenizer,
        args=dpo_cfg,
        callbacks=[budget_cb],
    )
    t0 = time.time()
    res = trainer.train()
    global_step = assert_nonzero_global_step(res, getattr(trainer, "state", None))
    trainer.model.save_pretrained(str(final_dir))
    tokenizer.save_pretrained(str(final_dir))

    st_file = final_dir / "adapter_model.safetensors"
    adapter_sha = sha256_file(st_file) if st_file.exists() else ""
    receipt = {
        "stage": "dpo_all90",
        "base_model": args.base,
        "source_adapter": args.adapter,
        "dataset_path": args.data,
        "dataset_sha256": data_sha,
        "adapter_sha256": adapter_sha,
        "beta": args.beta,
        "lr": args.lr,
        "epochs": args.epochs,
        "n_pairs": len(formatted),
        "global_step": global_step,
        "final_loss": float(res.training_loss),
        "elapsed_seconds": round(time.time() - t0, 2),
        "stopped_by_time_budget": bool(budget_cb.budget_stopped),
        "status": "TIME_BUDGET_STOPPED" if budget_cb.budget_stopped else "COMPLETED",
        "completed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    (out_dir / "training_receipt.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")
    (final_dir / "training_receipt.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")
    return 3 if budget_cb.budget_stopped else 0


def run_self_test() -> int:
    with tempfile.TemporaryDirectory(prefix="dpo_all90_selftest_") as td:
        td_p = Path(td)
        # 1. Base gate
        b8 = td_p / "Qwen3-8B"
        b8.mkdir()
        (b8 / "config.json").write_text(
            json.dumps({"_name_or_path": "Qwen/Qwen3-8B", "model_type": "qwen3", **EXPECTED_QWEN3_8B_SPEC}),
            encoding="utf-8",
        )
        assert_base_identity(str(b8), lineage="qwen3-8b")

        b_inst = td_p / "Qwen3-8B-Instruct"
        b_inst.mkdir()
        (b_inst / "config.json").write_text(
            json.dumps({"_name_or_path": "Qwen/Qwen3-8B-Instruct", "model_type": "qwen3", **EXPECTED_QWEN3_8B_SPEC}),
            encoding="utf-8",
        )
        try:
            assert_base_identity(str(b_inst))
            raise AssertionError("assert_base_identity failed to block Instruct")
        except RuntimeError:
            pass

        # 2. DPO pairs validation
        dpo_f = td_p / "dpo.jsonl"
        good_pair = {
            "prompt": [{"role": "system", "content": "你是 Virtu 工业代理。"}, {"role": "user", "content": "校核圆柱体几何尺寸"}],
            "chosen": '<tool_call>\n{"name": "cadcam_universal_geometry", "arguments": {"d": 80}}\n</tool_call>',
            "rejected": "我猜体积大约是 100。",
        }
        dpo_f.write_text(json.dumps(good_pair, ensure_ascii=False) + "\n", encoding="utf-8")
        assert len(validate_dpo_pairs(dpo_f)) == 1
        assert_no_leak(str(dpo_f))
        assert_units_clean(str(dpo_f))

        bad_f = td_p / "bad_dpo.jsonl"
        bad_pair = {**good_pair, "chosen": "same", "rejected": "same"}
        bad_f.write_text(json.dumps(bad_pair, ensure_ascii=False) + "\n", encoding="utf-8")
        try:
            validate_dpo_pairs(bad_f)
            raise AssertionError("validate_dpo_pairs failed to block chosen == rejected")
        except ValueError:
            pass

        # 3. TimeBudgetCallback
        cb = TimeBudgetCallback(max_minutes=1e-6)
        time.sleep(0.01)
        ctrl = SimpleNamespace(should_training_stop=False, should_save=False)
        cb.on_step_end(None, None, ctrl)
        assert cb.budget_stopped and ctrl.should_training_stop and ctrl.should_save

        # 4. Falsifiable zero-step & get_batch_samples fallback gates
        try:
            assert_nonzero_global_step(SimpleNamespace(global_step=0), SimpleNamespace(global_step=0))
            raise AssertionError("assert_nonzero_global_step failed to block global_step=0")
        except RuntimeError:
            pass
        assert assert_nonzero_global_step(SimpleNamespace(global_step=2)) == 2

        trainer_fn = lambda _self, it, n, _dev: ([next(it) for _ in range(n)], n)
        assert resolve_dpo_get_batch_fn(trainer_fn, trainer_fn) is None
        legacy_dpo = lambda _self, _model_only: (_ for _ in ()).throw(TypeError("bad signature"))
        wrapped = resolve_dpo_get_batch_fn(legacy_dpo, trainer_fn)
        assert wrapped is not None
        got_batches, got_n = wrapped(None, iter([{"x": 1}, {"x": 2}]), 2, "cpu")
        assert got_n == 2 and got_batches == [{"x": 1}, {"x": 2}]

    print("[SELF-TEST] PASS: train_dpo_all90 (base_gate / pair_validation / time_budget / nonzero_step / batch_compat / leak+unit)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="All-90 受控 DPO 训练 (beta=0.1, lr=5e-6, epochs=1)")
    parser.add_argument("--base", default=None)
    parser.add_argument("--adapter", default=None)
    parser.add_argument("--data", default=str(ROOT / "cloud_train_pack" / "dataset" / "dpo_phase2_targeted.jsonl"))
    parser.add_argument("--out", default=str(ROOT / "cloud_train_pack" / "output" / "all90_dpo"))
    parser.add_argument("--lineage", default="qwen3-8b", choices=("qwen3-8b", "14b"))
    parser.add_argument("--beta", type=float, default=0.1)
    parser.add_argument("--lr", type=float, default=5e-6)
    parser.add_argument("--epochs", type=float, default=1.0)
    parser.add_argument("--batch", type=int, default=1)
    parser.add_argument("--grad-accum", type=int, default=16)
    parser.add_argument("--max-length", type=int, default=2048)
    parser.add_argument("--max-steps", type=int, default=-1)
    parser.add_argument("--max-hours", type=float, default=1.0)
    parser.add_argument("--qlora", action="store_true")
    parser.add_argument("--self-test", "--selftest", dest="self_test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()
    if not args.base or not args.adapter:
        parser.error("请提供 --base 与 --adapter，或运行 --self-test")
    return run_dpo_training(args)


if __name__ == "__main__":
    raise SystemExit(main())
