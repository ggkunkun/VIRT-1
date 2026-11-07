#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""01_prepare_data.py — 数据准备总入口（可复现、零随机性漂移）。

流程：
  1. 固定种子，按 pipeline.json 的 data_mix 配比生成四大能力语料 + 反遗忘 replay
  2. 逐条过 physics_gate；违反物理规律的样本直接剔除并计数（绝不进训练）
  3. 去重（assistant 文本 sha256）、坏格式剔除（name+arguments 键名）
  4. 独立生成评测任务集（不同随机流 + 不同措辞），做训练/评测 prompt 泄漏检查
  5. 输出【恰好一个】train_corpus.jsonl + dpo_pairs.jsonl + eval_tasks.jsonl
  6. 写 corpus_manifest.json（sha256 / 行数 / 生成器版本 / 统计），供云端开训前校验
  7. 可选 --bundle 打成 tar.gz，并把所有脚本与配置一并装包

用法：
  python 01_prepare_data.py                          # 全量准备
  python 01_prepare_data.py --target-samples 500 --dry-run
  python 01_prepare_data.py --bundle                 # 准备并打包上云
  python 01_prepare_data.py --verify-only           # 只校验已有 manifest
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
import tarfile
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Sequence

from ect_common import (
    PACKAGE_DIR, atomic_write_json, atomic_write_jsonl, iter_jsonl, load_config,
    log, now_iso, repo_root, resolve, seed_everything, sha256_file, sha256_text,
    verify_manifest, write_manifest,
)
from data_builders import (
    build_dpo_pairs, build_engineering_semantics, build_gui_trajectories,
    build_replay, build_toolchain, build_vision_decisions, load_tool_specs,
)
from _ect_rowcheck import (assistant_text as _assistant_text,
                           user_text as _user_text,
                           physics_ok as row_physics_ok)

GENERATOR_VERSION = "1.0.0"


def _gui_eval_tasks(rows: Sequence[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for i, r in enumerate(rows[:limit]):
        try:
            ans = json.loads(_assistant_text(r))
        except json.JSONDecodeError:
            continue
        out.append({
            "task_id": f"gui-{i:05d}", "capability": "gui_trajectory",
            "prompt": "【独立验收题】" + _user_text(r),
            "expected_actions": ans.get("actions", []),
            "expected_verification": ans.get("verification", {}),
            "required_grounding_fields": r["meta"].get("grounding_fields", []),
            "scenario": {}, "max_latency_s": 180.0,
        })
    return out


def _tool_eval_tasks(n: int, rng: random.Random) -> List[Dict[str, Any]]:
    specs = load_tool_specs()
    out: List[Dict[str, Any]] = []
    for i in range(n):
        s = specs[i % len(specs)]
        name = s["function"]["name"]
        out.append({
            "task_id": f"tool-{i:05d}", "capability": "toolchain",
            "prompt": ("【独立验收题】请只输出一个 JSON 对象调用正确工具完成："
                       f"六大软件工具链第 {i + 1} 号标准工况，目标工具为 {name}，"
                       "参数按该工具 JSON Schema 的 required 填写，键名必须是 tool/arguments。"),
            "expected_tool": name,
            "required_grounding_fields": ["tool"],
            "scenario": {}, "max_latency_s": 60.0,
        })
    return out


def prepare(cfg: Dict[str, Any], target: int, seed: int, dry: bool = False) -> Dict[str, Any]:
    seed_everything(seed)
    mix = cfg["data_mix"]
    total_w = sum(mix.values())
    if abs(total_w - 1.0) > 1e-6:
        raise ValueError(f"data_mix 权重之和必须为 1.0，当前 {total_w}")
    stats: Dict[str, Any] = {"generator_version": GENERATOR_VERSION, "seed": seed,
                             "target_samples": target}
    rng = random.Random(seed)

    # 各能力用独立派生随机流：修改任一能力的生成逻辑不会影响其它能力的样本
    def sub(name: str) -> random.Random:
        return random.Random(seed + sum(ord(c) for c in name))

    log("prepare", f"生成四大能力语料 (target={target})")
    # 2.5x 富余：给去重与物理过闸留出补位空间，保证各能力都能取满配额
    want = {k: int(math.ceil(target * w * 2.5)) for k, w in mix.items()}
    tool_rows = build_toolchain(want["toolchain"], sub("toolchain"), stats)
    gui_rows = build_gui_trajectories(want["gui_trajectory"], sub("gui"), stats)
    vision_rows, vision_eval = build_vision_decisions(want["vision_decision"], sub("vision"), stats)
    sem_rows, sem_eval = build_engineering_semantics(
        want["engineering_semantics"], sub("semantic"), stats)

    # 独立 holdout 轨迹：绝不进入训练集
    gui_holdout = build_gui_trajectories(max(10, target // 60),
                                        random.Random(seed + 99991), {})
    replay_rows = build_replay(want["replay"], sub("replay"),
                               cfg["existing_corpora_for_replay"], set(), stats)

    # 泄漏检查：replay 不得复用本轮任何训练 prompt
    train_prompts = {_user_text(r) for r in (tool_rows + gui_rows + vision_rows + sem_rows)}
    replay_rows = [r for r in replay_rows if _user_text(r) not in train_prompts]

    caps = {
        "toolchain": tool_rows,
        "gui_trajectory": gui_rows,
        "vision_decision": vision_rows,
        "engineering_semantics": sem_rows,
        "replay": replay_rows,
    }
    # 配比：按能力「先去重 + 物理过闸，再取配额」。
    # 之前是先按配额截断再全局去重，生成器若有重复（如 8 直径 x 3 配合的语义题）
    # 会让该能力被削掉一半、配比失衡；现在富余样本自动补位，配比稳定。
    mixed: List[Dict[str, Any]] = []
    seen = set()
    rejected: List[Dict[str, str]] = []
    dedup_total = 0
    for name, rows in caps.items():
        quota = int(round(target * mix[name]))
        uniq: List[Dict[str, Any]] = []
        dropped = 0
        for r in rows:
            if len(uniq) >= quota:
                break
            # 去重键取整条对话：同一工具调用配不同措辞/规格是有效监督，不能误删
            h = sha256_text(_user_text(r) + "\x00" + _assistant_text(r))
            if h in seen:
                dropped += 1
                dedup_total += 1
                continue
            ok, reasons = row_physics_ok(r)
            if not ok:
                rejected.append({"id": r.get("meta", {}).get("id", ""),
                                 "reason": "; ".join(reasons)[:300]})
                continue
            seen.add(h)
            uniq.append(r)
        mixed.extend(uniq)
        stats[f"quota_{name}"] = {
            "requested": quota, "available": len(rows), "used": len(uniq),
            "dedup_dropped": dropped,
            "shortfall": max(0, quota - len(uniq)),
        }
    rng.shuffle(mixed)
    clean = mixed
    stats["deduplicated"] = dedup_total
    stats["physics_rejected_corpus"] = len(rejected)
    stats["rejected_examples"] = rejected[:5]
    stats["final_train_samples"] = len(clean)
    stats["capability_distribution"] = dict(Counter(r["meta"]["capability"] for r in clean))
    stats["deduplicated"] = stats.get("deduplicated", 0)

    # DPO 偏好对
    dpo = build_dpo_pairs(cfg.get("target_dpo_pairs", 900), sub("dpo"), vision_rows, stats)

    # 评测任务集（全部独立生成，措辞与训练集不同）
    eval_tasks: List[Dict[str, Any]] = []
    eval_tasks.extend(vision_eval)
    eval_tasks.extend(sem_eval)
    eval_tasks.extend(_gui_eval_tasks(gui_holdout, len(gui_holdout)))
    eval_tasks.extend(_tool_eval_tasks(max(10, target // 100), sub("tool_eval")))
    stats["eval_tasks_unsampled"] = len(eval_tasks)
    # 分层限流：全量生成会有数千题，真实模型逐题推理代价过高；
    # 按能力 round-robin 采样，保证小类（GUI/工具）不被大类推掉
    cap_eval = int(cfg.get("max_eval_tasks", 0) or 0)
    if cap_eval and len(eval_tasks) > cap_eval:
        by_cap: Dict[str, List[Dict[str, Any]]] = {}
        for t in eval_tasks:
            by_cap.setdefault(str(t["capability"]), []).append(t)
        sampler = random.Random(seed + 7777)
        for items in by_cap.values():
            sampler.shuffle(items)
        sampled: List[Dict[str, Any]] = []
        idx = 0
        while len(sampled) < cap_eval:
            added = False
            for cap in sorted(by_cap):
                if idx < len(by_cap[cap]) and len(sampled) < cap_eval:
                    sampled.append(by_cap[cap][idx])
                    added = True
            if not added:
                break
            idx += 1
        eval_tasks = sampled
        stats["eval_tasks_sampling"] = {
            "method": "stratified_round_robin", "seed": seed + 7777,
            "cap": cap_eval, "from": stats["eval_tasks_unsampled"]}
    stats["eval_tasks"] = len(eval_tasks)
    stats["eval_capability_distribution"] = dict(
        Counter(t["capability"] for t in eval_tasks))
    eval_prompts = {t["prompt"] for t in eval_tasks}
    leak = len(eval_prompts & {_user_text(r) for r in clean})
    stats["train_eval_prompt_overlap"] = leak
    if leak:
        raise RuntimeError(f"训练/评测 prompt 泄漏 {leak} 条，拒绝产出语料")

    # 硬 holdout 泄漏检查（formula_holdout_200 只允许训练后验收）
    hard = resolve(cfg["reuse_assets"]["hard_holdout"])
    if hard.is_file():
        holdout_texts = set()
        for rec in iter_jsonl(hard):
            holdout_texts.add(str(rec.get("prompt") or rec.get("user") or ""))
        if holdout_texts:
            stats["hard_holdout_overlap"] = sum(
                1 for r in clean if _user_text(r) in holdout_texts)
            if stats["hard_holdout_overlap"]:
                raise RuntimeError("硬 holdout 泄漏进训练集，拒绝产出语料")
    else:
        stats["hard_holdout_overlap"] = "not_present"

    if dry:
        log("prepare", "DRY-RUN：不写任何文件")
        return stats

    paths = cfg["paths"]
    corpus_p = resolve(paths["corpus_out"])
    dpo_p = resolve(paths["dpo_out"])
    eval_p = resolve(paths["data_dir"]) / "eval_tasks.jsonl"
    manifest_p = resolve(paths["manifest_out"])
    corpus_p.parent.mkdir(parents=True, exist_ok=True)

    atomic_write_jsonl(corpus_p, clean)
    atomic_write_jsonl(dpo_p, dpo)
    atomic_write_jsonl(eval_p, eval_tasks)
    log("prepare", f"写出 train_corpus={len(clean)} dpo={len(dpo)} eval={len(eval_tasks)}")

    manifest = write_manifest(
        manifest_p, [corpus_p, dpo_p, eval_p],
        extra={"seed": seed, "generator_version": GENERATOR_VERSION,
               "stats": stats, "config_sha256": {
                   f: sha256_file(PACKAGE_DIR / "configs" / f)
                   for f in ("pipeline.json", "train.json", "metrics.json")},
               "created_at": now_iso()},
    )
    chk = verify_manifest(manifest_p)
    if not chk["ok"]:
        raise RuntimeError(f"manifest 自检失败: {chk['mismatches']}")
    log("prepare", f"manifest 校验通过 ({chk['checked']} 个文件) -> {manifest_p}")
    stats["manifest"] = str(manifest_p)
    stats["corpus_sha256"] = sha256_file(corpus_p)
    return stats


def bundle(cfg: Dict[str, Any]) -> Path:
    """把脚本 + 配置 + 语料打成云端训练包；打包前后都做 sha256 门控。"""
    paths = cfg["paths"]
    manifest_p = resolve(paths["manifest_out"])
    chk = verify_manifest(manifest_p)
    if not chk["ok"]:
        raise RuntimeError(f"拒绝对损坏语料打包: {chk['mismatches']}")
    root = repo_root()
    pkg = PACKAGE_DIR
    out_dir = resolve(paths["artifacts_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    tar_p = out_dir / "ect_cloud_bundle.tar.gz"
    files = [p for p in pkg.rglob("*.py")] + [p for p in (pkg / "configs").glob("*.json")]
    files += [resolve(paths["corpus_out"]), resolve(paths["dpo_out"]),
              resolve(paths["data_dir"]) / "eval_tasks.jsonl", manifest_p]
    req = pkg / "requirements-cloud.txt"
    if req.is_file():
        files.append(req)
    # 云端一键入口与镜像/手册必须随包交付，否则拿到包后没有开训命令
    files += list((pkg / "cloud").glob("*.sh"))
    for extra in ("Dockerfile", "README.md"):
        ep = pkg / extra
        if ep.is_file():
            files.append(ep)
    with tarfile.open(tar_p, "w:gz") as tf:
        for p in files:
            if not p.is_file():
                continue
            tf.add(p, arcname=str(p.relative_to(root)).replace("\\", "/"))
    log("bundle", f"打包 {len(files)} 个文件 -> {tar_p} ({tar_p.stat().st_size} bytes)")
    atomic_write_json(out_dir / "bundle_manifest.json", {
        "bundle": str(tar_p), "sha256": sha256_file(tar_p),
        "bytes": tar_p.stat().st_size, "created_at": now_iso(),
        "corpus_manifest_sha256": sha256_file(manifest_p),
        "included": [str(p.relative_to(root)).replace("\\", "/") for p in files if p.is_file()],
    })
    return tar_p


def main() -> int:
    ap = argparse.ArgumentParser(description="Virtu 工程能力训练 - 数据准备")
    ap.add_argument("--target-samples", type=int, default=None)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--bundle", action="store_true")
    ap.add_argument("--verify-only", action="store_true")
    ap.add_argument("--stats-out", default=None)
    args = ap.parse_args()

    cfg = load_config("pipeline")
    manifest_p = resolve(cfg["paths"]["manifest_out"])
    if args.verify_only:
        chk = verify_manifest(manifest_p)
        print(json.dumps(chk, ensure_ascii=False, indent=2))
        return 0 if chk["ok"] else 1

    seed = args.seed if args.seed is not None else int(cfg["seed"])
    target = args.target_samples or int(cfg.get("target_train_samples", 6000))
    stats = prepare(cfg, target, seed, dry=args.dry_run)
    if args.stats_out:
        atomic_write_json(resolve(args.stats_out), stats)
    if args.bundle and not args.dry_run:
        stats["bundle"] = str(bundle(cfg))
    print(json.dumps({k: v for k, v in stats.items()
                      if k not in ("rejected_examples",)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
