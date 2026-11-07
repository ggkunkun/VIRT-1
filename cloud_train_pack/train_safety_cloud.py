#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cloud_train_pack/train_safety_cloud.py — Virtu 安全边界云端一键训练

训练目标（来自 2026-11-05 实测缺陷，见 dataset/safety_boundary_manifest.json）：
  1. C3 类「先拒绝、后贴命令」——SFT 与 DPO 双向压制；
  2. A2 类「拒绝 + 给绕过建议」——DPO 惩罚 rejected；
  3. B4 类「假称已输出系统提示」——SFT 示范如实拒绝，不虚构。

流程
----
  build 数据闸 -> 混料（安全样本占比受控，避免灾难性遗忘）
  -> SFT (train_turnkey.py) -> DPO (train_dpo_cloud.py, --resume-adapter 防遗忘)
  -> 合并 adapter -> 指纹凭证 -> 就地验收 (eval_safety_boundary.py, 可选)

用法
----
    python cloud_train_pack/train_safety_cloud.py --selftest          # 无 GPU，本地可跑
    python cloud_train_pack/train_safety_cloud.py --dry-run           # 只做数据与混料
    python cloud_train_pack/train_safety_cloud.py --base /root/models/Qwen3-8B-Instruct
    python cloud_train_pack/train_safety_cloud.py --verify            # 训完自动跑 14 例探针
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATASET = os.path.join(HERE, "dataset")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def read_jsonl(path: str) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: str, rows: list[dict]) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for rec in rows:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def build_safety_data(skip_build: bool = False) -> dict:
    sft = os.path.join(DATASET, "safety_boundary_sft.jsonl")
    dpo = os.path.join(DATASET, "safety_boundary_dpo_pairs.jsonl")
    manifest = os.path.join(DATASET, "safety_boundary_manifest.json")
    if skip_build:
        for p in (sft, dpo, manifest):
            if not os.path.exists(p):
                raise SystemExit(f"[FATAL] --skip-build 但缺少 {p}；拒绝猜测数据来源")
    else:
        cmd = [sys.executable, os.path.join(DATASET, "build_safety_boundary_sft.py")]
        print("[data] 重建安全边界数据:", " ".join(cmd))
        subprocess.run(cmd, cwd=ROOT, check=True)
    with open(manifest, encoding="utf-8") as f:
        meta = json.load(f)
    if not meta.get("gate", {}).get("passed"):
        raise SystemExit("[FATAL] 数据 manifest 的闸未通过，拒绝开训")
    # 训练前再做一次去污染闸（小文件，成本可忽略）
    sys.path.insert(0, ROOT)
    from virtu_eval.contamination_check import assert_no_leak

    assert_no_leak(sft)
    return {"sft": sft, "dpo": dpo, "manifest": manifest, "meta": meta}


def mix_corpus(general_path: str, safety_path: str, ratio: float,
               out_path: str, max_general: int = 0) -> dict:
    """按目标占比把安全样本均匀插入通用语料，重复上限 10 防止过拟合单条。"""
    if not 0.0 < ratio < 0.5:
        raise SystemExit("[FATAL] --safety-ratio 必须在 (0, 0.5) 内，否则会牺牲通用能力")
    general = read_jsonl(general_path)
    safety = read_jsonl(safety_path)
    if not general:
        raise SystemExit(f"[FATAL] 通用语料为空: {general_path}")
    if not safety:
        raise SystemExit(f"[FATAL] 安全语料为空: {safety_path}")
    if max_general > 0:
        general = general[:max_general]

    target = len(general) * ratio / (1.0 - ratio)
    reps = max(1, min(10, round(target / len(safety))))
    total_safety = len(safety) * reps
    step = len(general) / total_safety
    out, si, next_at = [], 0, 0.0
    for i, rec in enumerate(general):
        out.append(rec)
        while si < total_safety and (i + 1) >= next_at:
            out.append(safety[si % len(safety)])
            si += 1
            next_at += step
    while si < total_safety:
        out.append(safety[si % len(safety)])
        si += 1
    write_jsonl(out_path, out)
    actual = total_safety / len(out)
    info = {"general": len(general), "safety_unique": len(safety), "safety_reps": reps,
            "mixed_rows": len(out), "target_ratio": ratio, "actual_ratio": round(actual, 4),
            "out_path": out_path, "out_sha256": sha256_file(out_path)}
    print(f"[mix] general={len(general)} safety×{reps}={total_safety} "
          f"-> {len(out)} 行, 安全占比 {actual:.3f}")
    return info


def run_train(args, mixed_path: str, data: dict) -> dict:
    sft_out = os.path.join(args.out, "sft")
    dpo_out = os.path.join(args.out, "dpo")
    t0 = time.time()
    base = args.base or ""
    if not base:
        # train_turnkey 自带云端基座探测；这里只提示，不重复实现
        print("[train] 未显式指定 --base，将由 train_turnkey 自动探测云上基座")
    sft_cmd = [sys.executable, os.path.join(HERE, "train_turnkey.py"),
               "--data", mixed_path, "--out", sft_out,
               "--epochs", str(args.epochs), "--lr", str(args.lr),
               "--max-hours", str(args.max_hours), "--gpu-id", args.gpu_id]
    if base:
        sft_cmd += ["--base", base]
    print("[train] SFT:", " ".join(sft_cmd))
    subprocess.run(sft_cmd, cwd=ROOT, check=True)

    dpo_meta = {}
    if not args.skip_dpo:
        dpo_cmd = [sys.executable, os.path.join(HERE, "train_dpo_cloud.py"),
                   "--data", data["dpo"], "--out", dpo_out,
                   "--resume-adapter", os.path.join(sft_out, "final_adapter"),
                   "--epochs", str(args.dpo_epochs), "--lr", str(args.dpo_lr),
                   "--max-hours", str(args.max_hours), "--gpu-id", args.gpu_id]
        if base:
            dpo_cmd += ["--base", base]
        print("[train] DPO:", " ".join(dpo_cmd))
        subprocess.run(dpo_cmd, cwd=ROOT, check=True)
        dpo_meta = {"out": dpo_out,
                    "adapter_sha256": sha256_file(os.path.join(dpo_out, "adapter_model.safetensors"))
                    if os.path.exists(os.path.join(dpo_out, "adapter_model.safetensors")) else "missing"}

    adapter = os.path.join(dpo_out, "final_adapter")
    if not os.path.isdir(adapter):
        adapter = os.path.join(dpo_out, "adapter_model")  # DPO 脚本把 adapter 写在 out 根
    return {"sft_out": sft_out, "dpo_out": dpo_out if not args.skip_dpo else "",
            "adapter_dir": dpo_out if not args.skip_dpo else os.path.join(sft_out, "final_adapter"),
            "dpo": dpo_meta, "seconds": round(time.time() - t0, 1)}


def merge_adapter(base: str, adapter_dir: str, out_dir: str) -> str:
    """把 LoRA 合并回基座，产出可直接转 GGUF 的 HF 权重目录。"""
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    print(f"[merge] {base} + {adapter_dir} -> {out_dir}")
    model = AutoModelForCausalLM.from_pretrained(
        base, torch_dtype=torch.bfloat16, device_map="cpu", trust_remote_code=True)
    model = PeftModel.from_pretrained(model, adapter_dir)
    model = model.merge_and_unload()
    os.makedirs(out_dir, exist_ok=True)
    model.save_pretrained(out_dir, safe_serialization=True)
    AutoTokenizer.from_pretrained(base, trust_remote_code=True).save_pretrained(out_dir)
    print(f"[merge] done -> {out_dir}")
    return out_dir


def write_receipt(args, data: dict, mix_info: dict, train_info: dict,
                  merged: str, extra: dict | None = None) -> str:
    receipt = {
        "model": "virtu-safety-boundary",
        "base": args.base or "auto-detected-by-train_turnkey",
        "safety_dataset": {"path": data["sft"], "sha256": sha256_file(data["sft"]),
                           "samples": data["meta"]["sft_samples"]},
        "dpo_dataset": {"path": data["dpo"], "sha256": sha256_file(data["dpo"]),
                        "pairs": data["meta"]["dpo_pairs"]},
        "data_gate": data["meta"]["gate"],
        "mix": mix_info,
        "train": train_info,
        "merged_dir": merged or "",
        "hyperparams": {"sft_epochs": args.epochs, "sft_lr": args.lr,
                        "dpo_epochs": args.dpo_epochs, "dpo_lr": args.dpo_lr,
                        "safety_ratio": args.safety_ratio},
        "completed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "basis": "measured",
        **(extra or {}),
    }
    path = os.path.join(args.out, "safety_training_receipt.json")
    os.makedirs(args.out, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(receipt, f, ensure_ascii=False, indent=2)
    print(f"[receipt] {path}")
    return path


def selftest() -> int:
    """无 GPU 验证：数据闸、混料算术、凭证 schema。"""
    import tempfile

    data = build_safety_data(skip_build=False)
    assert data["meta"]["gate"]["chosen_safe"] == data["meta"]["sft_samples"], "chosen 未全过闸"
    fake_general = [{"messages": [{"role": "user", "content": f"通用题 {i}"},
                                  {"role": "assistant", "content": "答案"}]} for i in range(100)]
    with tempfile.TemporaryDirectory() as td:
        gp = os.path.join(td, "general.jsonl")
        write_jsonl(gp, fake_general)
        info = mix_corpus(gp, data["sft"], 0.15, os.path.join(td, "mixed.jsonl"))
        expected = round(100 * 0.15 / 0.85)
        if not (expected - 20 <= info["mixed_rows"] - 100 <= expected + 20):
            raise AssertionError(f"混料行数异常: {info}")
        if not 0.10 <= info["actual_ratio"] <= 0.22:
            raise AssertionError(f"实际安全占比偏离目标: {info}")
        mixed = read_jsonl(info["out_path"])
        if not any("system" in {m["role"] for m in r["messages"]} for r in mixed):
            raise AssertionError("混料中未检出安全样本")
        receipt_path = os.path.join(td, "receipt.json")
        payload = {"sft_samples": 20, "basis": "measured"}
        with open(receipt_path, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        if json.load(open(receipt_path, encoding="utf-8"))["basis"] != "measured":
            raise AssertionError("receipt 写入失败")
    print("[selftest] 数据闸 / 混料 / 凭证 schema 全通过")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=os.environ.get("BASE", ""))
    ap.add_argument("--general", default=os.path.join(DATASET, "train_corpus_comprehensive.jsonl"))
    ap.add_argument("--out", default=os.path.join(HERE, "output", "virtu_safety"))
    ap.add_argument("--safety-ratio", type=float, default=0.12)
    ap.add_argument("--epochs", type=float, default=2.0)
    ap.add_argument("--lr", type=float, default=1.5e-4)
    ap.add_argument("--dpo-epochs", type=float, default=2.0)
    ap.add_argument("--dpo-lr", type=float, default=5e-6)
    ap.add_argument("--max-hours", type=float, default=1.5)
    ap.add_argument("--gpu-id", default="0")
    ap.add_argument("--max-general", type=int, default=0, help="冒烟时截断通用语料行数")
    ap.add_argument("--skip-build", action="store_true")
    ap.add_argument("--skip-dpo", action="store_true")
    ap.add_argument("--no-merge", action="store_true")
    ap.add_argument("--verify", action="store_true", help="训完用 14 例探针就地验收")
    ap.add_argument("--dry-run", action="store_true", help="只建数据与混料，不训练")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    data = build_safety_data(args.skip_build)
    if not os.path.exists(args.general):
        raise SystemExit(f"[FATAL] 通用语料不存在: {args.general}；拒绝用安全样本单训（会毁掉通用能力）")
    mixed = os.path.join(args.out, "train_mix_safety.jsonl")
    mix_info = mix_corpus(args.general, data["sft"], args.safety_ratio, mixed,
                          max_general=args.max_general)
    if args.dry_run:
        write_receipt(args, data, mix_info, {"dry_run": True}, "", {"dry_run": True})
        print("[dry-run] 数据与混料就绪，未启动 GPU 训练")
        return 0

    train_info = run_train(args, mixed, data)
    merged = ""
    if not args.no_merge:
        if not args.base:
            raise SystemExit("[FATAL] --merge 需要显式 --base；否则无法确定合并对象")
        merged = merge_adapter(args.base, train_info["adapter_dir"],
                               os.path.join(args.out, "merged"))
    receipt = write_receipt(args, data, mix_info, train_info, merged)
    print(f"[done] receipt={receipt}")

    if args.verify:
        if not merged:
            raise SystemExit("[FATAL] --verify 需要合并后的权重目录（不要加 --no-merge）")
        rc = subprocess.call([sys.executable, os.path.join(HERE, "eval_safety_boundary.py"),
                              "--model", merged,
                              "--out", os.path.join(args.out, "safety_eval")])
        print(f"[verify] exit={rc}")
        return rc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
