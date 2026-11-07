#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_pipeline.py — 一键复现编排器。

完整链路（每步都写 receipt，失败即停，不允许在半成品上叠加）：
  01_prepare_data  ->  validate_corpus  ->  [bundle]  ->  train_sft
                   ->  train_dpo  ->  evaluate  ->  pipeline_receipt.json

分工沿用工作区约定：
  * GPU / 云端：只做数据校验 + SFT + DPO，产出 adapter（数十 MB）
  * 本机：语料生成、LoRA 合并（delta/TIES）、GGUF、Ollama 注册、真实 GUI 评测
  * 合并脚本入口见 README；GPU 机上不做合并（省显存、避免 peft 版本漂移）

用法：
  python run_pipeline.py --dry-run                       # 只打印执行计划
  python run_pipeline.py --stage prepare,validate       # 只跑前两步
  python run_pipeline.py --cloud --bundle               # 准备 + 打包（上云前）
  python run_pipeline.py --stage train --profile l40s_48g --base /root/models/Qwen3-8B
  python run_pipeline.py --stage evaluate --endpoint http://127.0.0.1:8000/v1
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from ect_common import (PACKAGE_DIR, atomic_write_json, load_config, log, now_iso,
                        repo_root, resolve, seed_everything, sha256_file)

STAGES = ["prepare", "validate", "bundle", "train", "dpo", "evaluate"]
# 本机默认只做数据链路；评测必须显式给 --endpoint / --predictions，
# 否则会产生全 transport_error，按口径本轮无效，不应伪装成"跑过评测"
DEFAULT_LOCAL = ["prepare", "validate"]
DEFAULT_CLOUD = ["validate", "train", "dpo"]


def build_commands(stage: str, args, cfg, train_cfg) -> List[List[str]]:
    py = sys.executable
    pkg = str(PACKAGE_DIR)
    def p(name: str) -> str:
        return str(PACKAGE_DIR / name)

    if stage == "prepare":
        cmd = [py, p("01_prepare_data.py"), "--target-samples", str(args.target_samples),
               "--seed", str(args.seed)]
        if args.bundle:
            cmd.append("--bundle")
        return [cmd]
    if stage == "validate":
        return [[py, p("validate_corpus.py"), "--report-out",
                 cfg["paths"]["data_dir"] + "/validation_report.json"]]
    if stage == "bundle":
        return [[py, p("01_prepare_data.py"), "--target-samples",
                 str(args.target_samples), "--seed", str(args.seed), "--bundle"]]
    if stage == "train":
        cmd = [py, p("train_sft.py"), "--profile", args.profile,
               "--engine", args.engine, "--seed", str(args.seed),
               "--max-len", str(args.max_len)]
        if args.base:
            cmd += ["--base", args.base]
        if args.lr is not None:
            cmd += ["--lr", str(args.lr)]
        if args.epochs is not None:
            cmd += ["--epochs", str(args.epochs)]
        cmds = [[py, p("train_sft.py"), "--selftest", "--base", args.base]
                ] if (args.selftest and args.base) else []
        return cmds + [cmd]
    if stage == "dpo":
        cmd = [py, p("train_dpo.py"), "--seed", str(args.seed)]
        if args.base:
            cmd += ["--base", args.base]
        if args.sft_adapter:
            cmd += ["--sft-adapter", args.sft_adapter]
        if args.smoke:
            cmd.append("--smoke")
        return [cmd]
    if stage == "evaluate":
        cmd = [py, p("evaluate.py")]
        if args.endpoint:
            cmd += ["--endpoint", args.endpoint, "--model", args.model]
        if args.predictions:
            cmd += ["--predictions", args.predictions]
        if args.gui_results:
            cmd += ["--gui-results", args.gui_results]
        if args.limit:
            cmd += ["--limit", str(args.limit)]
        return [cmd]
    return []


def main() -> int:
    ap = argparse.ArgumentParser(description="Virtu 工程能力训练 - 一键编排")
    ap.add_argument("--stage", default=None, help="逗号分隔，留空按模式取默认")
    ap.add_argument("--cloud", action="store_true", help="云端模式：只做校验+训练")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--bundle", action="store_true")
    ap.add_argument("--target-samples", type=int, default=0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--profile", default="auto")
    ap.add_argument("--engine", default="native", choices=["native", "legacy"])
    ap.add_argument("--base", default=None)
    ap.add_argument("--lr", type=float, default=None)
    ap.add_argument("--epochs", type=int, default=None)
    ap.add_argument("--max-len", type=int, default=2560)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--sft-adapter", default=None)
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--endpoint", default=None)
    ap.add_argument("--model", default="virtu-ect")
    ap.add_argument("--predictions", default=None)
    ap.add_argument("--gui-results", default=None)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--receipt", default=None)
    args = ap.parse_args()

    cfg = load_config("pipeline")
    train_cfg = load_config("train")
    args.seed = args.seed or int(cfg["seed"])
    args.target_samples = args.target_samples or int(cfg.get("target_train_samples", 6000))
    args.base = args.base or os.environ.get(cfg["base_model_env"])
    stages = ([s.strip() for s in args.stage.split(",") if s.strip()]
              if args.stage else (DEFAULT_CLOUD if args.cloud else DEFAULT_LOCAL))
    unknown = [s for s in stages if s not in STAGES]
    if unknown:
        raise SystemExit(f"未知阶段 {unknown}，可选 {STAGES}")

    seed_everything(args.seed)
    receipt: Dict[str, Any] = {
        "pipeline": "virtu-engineering-capability", "version": "1.0.0",
        "started_at": now_iso(), "seed": args.seed, "cloud_mode": args.cloud,
        "stages": stages, "steps": [], "status": "RUNNING",
        "config_sha256": {f: sha256_file(PACKAGE_DIR / "configs" / f)
                          for f in ("pipeline.json", "train.json", "metrics.json")},
    }
    log("pipeline", f"stages={stages} seed={args.seed} dry_run={args.dry_run}")
    t_all = time.time()
    for stage in stages:
        cmds = build_commands(stage, args, cfg, train_cfg)
        for cmd in cmds:
            entry: Dict[str, Any] = {"stage": stage, "cmd": " ".join(cmd),
                                     "started_at": now_iso()}
            log("pipeline", f"[{stage}] {' '.join(cmd)}")
            if args.dry_run:
                entry.update({"status": "SKIPPED_DRY_RUN", "returncode": 0})
                receipt["steps"].append(entry)
                continue
            t0 = time.time()
            try:
                rc = subprocess.call(cmd, cwd=str(repo_root()))
            except OSError as exc:
                rc = 127
                entry["error"] = repr(exc)
            entry.update({"returncode": rc, "elapsed_s": round(time.time() - t0, 2),
                          "status": "OK" if rc == 0 else "FAILED",
                          "finished_at": now_iso()})
            receipt["steps"].append(entry)
            if rc != 0:
                # 熔断：停止后续阶段，不在半成品上继续叠加
                receipt["status"] = "FAILED"
                receipt["failed_stage"] = stage
                receipt["finished_at"] = now_iso()
                receipt["total_elapsed_s"] = round(time.time() - t_all, 2)
                out = resolve(args.receipt or (cfg["paths"]["artifacts_dir"]
                                               + "/pipeline_receipt.json"))
                atomic_write_json(out, receipt)
                log("pipeline", f"熔断于 {stage} (rc={rc})，receipt -> {out}")
                return rc

    receipt["status"] = "SKIPPED_DRY_RUN" if args.dry_run else "COMPLETED"
    receipt["finished_at"] = now_iso()
    receipt["total_elapsed_s"] = round(time.time() - t_all, 2)
    # 汇总产物身份
    artifacts = {}
    for name, rel in cfg["paths"].items():
        if name.endswith("_out"):
            p = resolve(rel)
            if p.is_file():
                artifacts[name] = {"path": str(p), "sha256": sha256_file(p),
                                   "bytes": p.stat().st_size}
    receipt["artifacts"] = artifacts
    out = resolve(args.receipt or (cfg["paths"]["artifacts_dir"] + "/pipeline_receipt.json"))
    atomic_write_json(out, receipt)
    log("pipeline", f"{receipt['status']} elapsed={receipt['total_elapsed_s']}s -> {out}")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
