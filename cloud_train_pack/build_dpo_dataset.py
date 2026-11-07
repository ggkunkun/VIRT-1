#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_dpo_dataset.py — 从「带标签错误」构造 DPO 偏好对（本地可跑，不需 GPU）
===================================================================================
数据源：6 组 `_eval_phys_*_*/triples.jsonl`（与 VIRTU_ANTIHALLUCINATION_FEASIBILITY.json
的 E1 一致）。每条 triples 已含：
  - intent   : 模型当时收到的 user prompt（作为 DPO 的 prompt）
  - inputs   : 物理输入参数（作为 scenario.inputs，供复算/审计）
  - task     : 任务类型
  - prediction : 模型「错误」world_state 字段 dict  -> rejected
  - reference  : 求解器「正确」world_state 字段 dict -> chosen
  - verdict / verified / score : 标签（错误样本过滤依据）

过滤规则（与 E1 的 baseline_wrong=132 对齐）：
  not verified  OR  verdict != "pass"  OR  score < 100
即只保留「模型确实错了」的样本进入 DPO，避免用正确样本做无意义偏好对。

输出格式（每行一个 JSON）：
  {"prompt": <intent>, "chosen": <{"world_state": reference} 紧凑JSON>,
   "rejected": <{"world_state": prediction} 紧凑JSON>,
   "task": .., "case_id": .., "scenario": {"task":..,"inputs":..}, "rel_err": ..}

用法：
  python cloud_train_pack/build_dpo_dataset.py \
      --root D:/Virtu模型 --out cloud_train_pack/dataset/dpo_phys_rejects.jsonl
"""
from __future__ import annotations

import os
import sys
import json
import glob
import argparse
from collections import Counter

ROOT_DEFAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _is_error(rec: dict) -> bool:
    if not rec.get("verified", True):
        return True
    if rec.get("verdict", "pass") != "pass":
        return True
    try:
        if float(rec.get("score", 100)) < 100:
            return True
    except (TypeError, ValueError):
        pass
    return False


def _compact(d: dict) -> str:
    return json.dumps({"world_state": d}, ensure_ascii=False, separators=(",", ":"))


def build(root: str, out_path: str) -> dict:
    triple_files = sorted(glob.glob(os.path.join(root, "_eval_*", "triples.jsonl")))
    # 只取物理世界状态类（dimension == physics 或目录名含 phys）
    phys_files = []
    for f in triple_files:
        try:
            sample = json.loads(open(f, encoding="utf-8").readline())
        except Exception:
            continue
        dim = sample.get("dimension", "")
        if dim == "physics" or "phys" in os.path.basename(os.path.dirname(f)):
            phys_files.append(f)
    if not phys_files:
        phys_files = triple_files  # 兜底：全用

    rows = []
    seen = set()
    task_counter = Counter()
    for f in phys_files:
        dn = os.path.basename(os.path.dirname(f))
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if not _is_error(rec):
                    continue
                cid = rec.get("case_id") or rec.get("id")
                key = (dn, cid)
                if key in seen:
                    continue
                seen.add(key)
                pred = rec.get("prediction")
                ref = rec.get("reference")
                if not isinstance(pred, dict) or not isinstance(ref, dict):
                    continue
                prompt = rec.get("intent") or rec.get("prompt") or rec.get("user")
                if not prompt:
                    continue
                rel_err = None
                for fl in rec.get("fields", []) or []:
                    if isinstance(fl, dict) and fl.get("rel_err") is not None:
                        rel_err = fl["rel_err"]
                        break
                rows.append({
                    "prompt": prompt,
                    "chosen": _compact(ref),
                    "rejected": _compact(pred),
                    "task": rec.get("task"),
                    "case_id": cid,
                    "scenario": {"task": rec.get("task"), "inputs": rec.get("inputs", {})},
                    "rel_err": rel_err,
                    "source_dir": dn,
                })
                task_counter[rec.get("task")] += 1

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as out:
        for r in rows:
            out.write(json.dumps(r, ensure_ascii=False) + "\n")

    return {
        "n_pairs": len(rows),
        "by_task": dict(task_counter),
        "source_files": [os.path.basename(os.path.dirname(f)) for f in phys_files],
        "out": out_path,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=ROOT_DEFAULT)
    ap.add_argument("--out", default=os.path.join(ROOT_DEFAULT, "cloud_train_pack", "dataset", "dpo_phys_rejects.jsonl"))
    args = ap.parse_args()
    summary = build(args.root, args.out)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\n[ok] DPO 偏好对已写出 -> {summary['out']}  ({summary['n_pairs']} 条)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
