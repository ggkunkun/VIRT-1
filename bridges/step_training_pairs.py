# -*- coding: utf-8 -*-
"""训练数据配对生成器：(STEP, BOM) → JSONL，供 13.63B 领域模型继续预训练 / LoRA。

解决「模型读不懂装配体」的 P1 解法：批量生成「原始 STEP 噪声 → 结构化装配树」
配对样本，让模型学会从几何噪声里抽结构，而不是靠推理时临时 prompt。

每个 STEP 产出 4 类任务视角（可用 --tasks 选择）：
  1. step_to_bom     : 原始 STEP 片段(结构行+几何噪声) → 紧凑 DSL          [核心]
  2. bom_to_nl       : DSL → 中文自然语言装配描述
  3. qa              : 由 BOM 确定性生成的问答对(零件数/名称/实体数/位姿/AP/编码)
  4. schema_detect   : STEP 头部 → AP 版本 + 编码 + 是否装配体

输入片段策略（--raw-lines N，默认 120）：
  从原始 STEP 中抽取【全部结构实体行】+【随机若干几何噪声行】并按原始 #id 顺序还原，
  模拟真实「结构信号被几何淹没」的分布；--full-raw 则放完整原文(长上下文预训练用)。

溯源：每条样本带 source_sha256 / basis / task / generator，符合项目测量宪法。
用法:
  python3 bridges/step_training_pairs.py --dir assets --out data/step_bom_sft.jsonl
  python3 bridges/step_training_pairs.py --dir assets --tasks qa step_to_bom \
      --out data/step_bom_sft.jsonl --raw-lines 200 --report reports/step_pairs.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import sys
import time
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from step_bom import StepBOM, detect_ap, detect_encoding  # noqa: E402

GENERATOR = "bridges.step_training_pairs/1.0"

STRUCT_KEYS = (
    "PRODUCT(", "PRODUCT_DEFINITION(", "PRODUCT_DEFINITION_FORMATION",
    "PRODUCT_DEFINITION_SHAPE(", "NEXT_ASSEMBLY_USAGE_OCCURRENCE",
    "PRODUCT_DEFINITION_USAGE", "SHAPE_DEFINITION_REPRESENTATION",
    "SHAPE_REPRESENTATION(", "ADVANCED_BREP_SHAPE_REPRESENTATION",
    "MANIFOLD_SOLID_BREP", "BREP_WITH_VOIDS", "CLOSED_SHELL(",
    "ITEM_DEFINED_TRANSFORMATION", "REPRESENTATION_RELATIONSHIP",
    "AXIS2_PLACEMENT_3D(", "CONTEXT_DEPENDENT_SHAPE_REPRESENTATION",
)


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(65536), b""):
            h.update(c)
    return h.hexdigest()


def raw_snippet(path: str, enc: str, max_lines: int, seed: int = 0) -> str:
    """抽取 STEP 片段：全结构行 + 随机几何噪声行，按文件原始顺序还原。"""
    raw = open(path, "rb").read()
    try:
        text = raw.decode(enc, errors="replace")
    except Exception:
        text = raw.decode("latin-1", errors="replace")
    lines = text.splitlines()
    struct_idx = [i for i, ln in enumerate(lines) if any(k in ln for k in STRUCT_KEYS)]
    struct_set = set(struct_idx)
    noise_idx = [i for i in range(len(lines)) if i not in struct_set and "#" in lines[i]]
    rnd = random.Random(seed)
    take_noise = max(0, max_lines - len(struct_idx))
    if take_noise > len(noise_idx):
        take_noise = len(noise_idx)
    chosen = set(struct_idx) | set(rnd.sample(noise_idx, take_noise))
    picked = [lines[i] for i in sorted(chosen)]
    # 保留头部（模型需看到 FILE_SCHEMA 判断 AP）
    header = [ln for ln in lines[:15] if ln.strip()][:12]
    return "\n".join(header + ["..."] + picked)


def flatten(tree: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for n in tree:
        out.append(n)
        out.extend(flatten(n.get("children", [])))
    return out


def make_pairs(path: str, tasks: List[str], raw_lines: int,
               full_raw: bool, seed: int) -> List[Dict[str, Any]]:
    raw = open(path, "rb").read()
    enc = detect_encoding(raw)
    ap = detect_ap(raw)
    try:
        text = raw.decode(enc, errors="replace")
    except Exception:
        text = raw.decode("latin-1", errors="replace")

    bom = StepBOM(path)
    d = bom.to_dict()
    dsl = bom.to_dsl()
    nl = bom.to_prompt_context()
    nodes = flatten(d["tree"])
    digest = sha256_file(path)
    src = os.path.basename(path)

    if full_raw:
        snippet = text
    else:
        snippet = raw_snippet(path, enc, raw_lines, seed=seed)

    meta = {
        "source": src,
        "source_sha256": digest,
        "ap_version": ap,
        "encoding": enc,
        "is_assembly": d["is_assembly"],
        "basis": "measured_from_step",
        "generator": GENERATOR,
        "raw_lines": raw_lines if not full_raw else "full",
        "entity_count": d["entity_count"],
    }
    pairs: List[Dict[str, Any]] = []

    def add(task: str, instruction: str, inp: str, out: str):
        pairs.append({
            **meta,
            "task": task,
            "instruction": instruction,
            "input": inp,
            "output": out,
        })

    if "step_to_bom" in tasks:
        add("step_to_bom",
            "把下面的 STEP 文件片段解析为结构化装配树，用紧凑 DSL 输出。",
            snippet, dsl)

    if "bom_to_nl" in tasks:
        add("bom_to_nl",
            "把下面 STEP 装配结构 DSL 转述为准确的中文自然语言描述。",
            dsl, nl)

    if "schema_detect" in tasks:
        head = "\n".join(text.splitlines()[:14])
        obj = {"ap_version": ap, "encoding": enc,
               "is_assembly": d["is_assembly"],
               "product_count": d["product_count"],
               "component_count": d["component_count"]}
        add("schema_detect",
            "判断该 STEP 文件的 AP 版本、文本编码、是否为装配体及零件/装配关系数，输出 JSON。",
            head, json.dumps(obj, ensure_ascii=False))

    if "qa" in tasks:
        # 所有答案由 BOM 数据确定性生成
        ctx = dsl
        parts = [n for n in nodes if n["solids"] > 0]
        add("qa", "该 STEP 模型一共有几个零件？", ctx,
            "共 %d 个零件定义%s。" % (
                d["product_count"],
                "（其中 %d 个为含几何的实体零件）" % len(parts)
                if len(parts) != d["product_count"] else ""))
        add("qa", "该 STEP 文件是装配体还是单一零件？有几处装配关系？", ctx,
            "%s，共 %d 处装配关系。" % (
                "装配体" if d["is_assembly"] else "单一零件",
                d["component_count"]))
        add("qa", "这个模型使用了哪个 STEP AP 版本？文件是什么编码？", ctx,
            "AP 版本 %s，文本编码 %s。" % (ap, enc))
        if d["is_assembly"]:
            names = [n["name"] for n in nodes]
            add("qa", "请列出该装配体包含的所有零件名称。", ctx,
                "包含：%s。" % "、".join(names))
            placed = [n for n in nodes if n.get("placement")]
            if placed:
                add("qa", "各子零件在装配体中的摆放坐标是什么？", ctx,
                    "\n".join("%s → (%s) mm" % (
                        n["name"], ", ".join(str(x) for x in n["placement"]["origin_mm"]))
                        for n in placed))
        for n in parts:
            add("qa", "零件「%s」由几个实体构成、共有多少个面？" % n["name"], ctx,
                "由 %d 个实体构成，共 %d 个面%s。" % (
                    n["solids"], n["faces"],
                    ("，特征为 %s" % "、".join(n["features"])) if n["features"] else ""))
        total_solids = sum(n["solids"] for n in nodes)
        total_faces = sum(n["faces"] for n in nodes)
        add("qa", "整个模型共有多少个实体、多少个面？", ctx,
            "共 %d 个实体、%d 个面。" % (total_solids, total_faces))
        if d["is_assembly"]:
            multi = [n for n in parts if n["solids"] > 1]
            if multi:
                add("qa", "哪个零件包含多个实体？分别是什么特征？", ctx,
                    "\n".join("%s：%d 个实体（%s）" % (
                        n["name"], n["solids"], "、".join(n["features"]))
                        for n in multi))
    return pairs


def main(argv=None):
    ap = argparse.ArgumentParser(description="(STEP,BOM) 训练数据配对生成器")
    ap.add_argument("--dir", action="append", default=[], help="STEP 目录(可多次)")
    ap.add_argument("--file", action="append", default=[], help="单个 STEP(可多次)")
    ap.add_argument("--out", default="data/step_bom_sft.jsonl", help="输出 JSONL")
    ap.add_argument("--report", default="", help="写出统计报告 JSON")
    ap.add_argument("--tasks", nargs="+", default=["step_to_bom", "bom_to_nl", "qa", "schema_detect"])
    ap.add_argument("--raw-lines", type=int, default=120)
    ap.add_argument("--full-raw", action="store_true", help="输入放完整 STEP 原文(长上下文预训练)")
    ap.add_argument("--seed", type=int, default=20261106)
    a = ap.parse_args(argv)

    dirs = a.dir or ["assets"]
    paths: List[str] = []
    for p in a.file:
        if os.path.isfile(p):
            paths.append(p)
    for d in dirs:
        if os.path.isfile(d):
            paths.append(d)
            continue
        for base, _sub, fns in os.walk(d):
            if any(s in base for s in (".git", "__pycache__", ".venv")):
                continue
            for fn in fns:
                if fn.lower().endswith((".step", ".stp")):
                    paths.append(os.path.join(base, fn))
    paths = sorted(set(paths))
    if not paths:
        print("[!] 未找到 STEP 文件")
        return 1

    all_pairs: List[Dict[str, Any]] = []
    per_file = []
    for p in paths:
        try:
            ps = make_pairs(p, a.tasks, a.raw_lines, a.full_raw, a.seed)
            all_pairs.extend(ps)
            per_file.append({"file": os.path.basename(p), "pairs": len(ps), "status": "ok"})
        except Exception as exc:  # noqa: BLE001
            per_file.append({"file": os.path.basename(p), "pairs": 0,
                             "status": "error", "error": "%s: %s" % (type(exc).__name__, exc)})

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        for rec in all_pairs:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    by_task: Dict[str, int] = {}
    for r in all_pairs:
        by_task[r["task"]] = by_task.get(r["task"], 0) + 1
    report = {
        "generator": GENERATOR,
        "basis": "measured_from_step + deterministic_qa",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "run_id": hashlib.sha256(
            "|".join(sorted(x["source_sha256"] for x in all_pairs)).encode()
        ).hexdigest()[:16] if all_pairs else "",
        "source_file_count": len(paths),
        "total_pairs": len(all_pairs),
        "by_task": by_task,
        "tasks": a.tasks,
        "raw_lines": "full" if a.full_raw else a.raw_lines,
        "output": a.out,
        "per_file": per_file,
    }
    print("[step_training_pairs] 源文件=%d 样本=%d 分布=%s" %
          (len(paths), len(all_pairs), by_task))
    print("  → %s" % a.out)
    if a.report:
        os.makedirs(os.path.dirname(os.path.abspath(a.report)), exist_ok=True)
        with open(a.report, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print("  → 报告 %s" % a.report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
