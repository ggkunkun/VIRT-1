#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_merged.py — 合并产物的静态完整性与可加载性校验（零 torch 依赖）。

本机无 transformers，无法真正 from_pretrained，但可以静态验证所有会导致加载失败的条件：
  1. 必需文件齐全（config / tokenizer / index / 分片）
  2. index.weight_map 的键集合 == 所有分片 header 的张量键集合（无缺失、无多余、无重复）
  3. 每个分片 header 的 data_offsets 连续、无空洞、总长与文件大小吻合
  4. 每个张量 dtype/shape 与基座完全一致（合并不得改变结构）
  5. config.json 架构字段与基座一致，chat_template 存在
  6. 参数量统计（应等于 Qwen3-8B 的 ~8.19B）
  7. 合并产物与基座的张量数值差异分布（确认确实发生了合并，且幅度合理）

用法:
  python scripts/validate_merged.py --merged checkpoints/virtu_merged \
      --base checkpoints/_base_qwen3_8b
  python scripts/validate_merged.py --merged checkpoints/virtu_merged   # 只校验结构
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DTYPE_BYTES = {"F64": 8, "F32": 4, "F16": 2, "BF16": 2, "I64": 8, "I32": 4,
               "I16": 2, "I8": 1, "U8": 1, "BOOL": 1}
REQUIRED_FILES = ("config.json", "tokenizer.json", "tokenizer_config.json",
                  "model.safetensors.index.json")


def read_header(path: Path):
    with open(path, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        header = json.loads(f.read(n))
    return n, header


def shard_keys(path: Path):
    hlen, h = read_header(path)
    keys = {}
    for k, v in h.items():
        if k == "__metadata__":
            continue
        keys[k] = (v["dtype"], tuple(v["shape"]), tuple(v["data_offsets"]))
    return hlen, keys, path.stat().st_size


def check_offsets(name: str, keys: dict, hlen: int, fsize: int):
    items = sorted(keys.values(), key=lambda x: x[2][0])
    pos = 0
    problems = []
    for dt, shp, (st, en) in items:
        if st != pos:
            problems.append(f"{name}: 空洞/重叠 offset st={st} expected={pos}")
        nb = 1
        for d in shp:
            nb *= d
        expect = nb * DTYPE_BYTES.get(dt, 0)
        if expect != en - st:
            problems.append(f"{name}: {shp} {dt} 字节数 {en-st} != {expect}")
        pos = en
    data_len = pos
    if 8 + hlen + data_len != fsize:
        problems.append(f"{name}: 文件总长 {fsize} != 8+{hlen}+{data_len}")
    return problems


def bf16_to_f32(buf: bytes) -> np.ndarray:
    u16 = np.frombuffer(buf, dtype="<u2")
    return (u16.astype(np.uint32) << 16).view(np.float32)


def tensor_diff(src: Path, dst: Path, key: str, src_keys, dst_keys):
    """返回 (rms_base, rms_delta, ratio)，用于量化合并幅度。"""
    _, _, (sst, sen) = src_keys
    _, _, (dst_st, dst_en) = dst_keys
    with open(src, "rb") as f:
        f.seek(8 + read_header(src)[0] + sst)
        a = bf16_to_f32(f.read(sen - sst)).astype(np.float64)
    with open(dst, "rb") as f:
        f.seek(8 + read_header(dst)[0] + dst_st)
        b = bf16_to_f32(f.read(dst_en - dst_st)).astype(np.float64)
    d = b - a
    rb = float(np.sqrt(np.mean(a * a)))
    rd = float(np.sqrt(np.mean(d * d)))
    return rb, rd, (rd / rb if rb > 1e-12 else 0.0)


def artifact_manifest(directory: Path):
    """Capture the exact file set and metadata covered by this validation report."""
    paths = [directory / name for name in REQUIRED_FILES]
    paths += sorted(directory.glob("model-*.safetensors"))
    manifest = {}
    for path in paths:
        if path.is_file():
            manifest[path.name] = {"size": path.stat().st_size,
                                   "mtime_ns": path.stat().st_mtime_ns}
            if path.name in {"config.json", "tokenizer_config.json",
                             "model.safetensors.index.json"}:
                manifest[path.name]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return manifest


def main():
    p = argparse.ArgumentParser(description="合并产物静态完整性与可加载性校验")
    p.add_argument("--merged", default=str(ROOT / "checkpoints" / "virtu_merged"))
    p.add_argument("--base", default=None, help="基座目录（提供则做结构对比与幅度统计）")
    p.add_argument("--samples", type=int, default=8, help="幅度统计抽样张量数")
    args = p.parse_args()
    if args.samples < 1:
        p.error("--samples must be a positive integer")

    merged = Path(args.merged)
    base = Path(args.base) if args.base else None
    problems = []
    infos = []

    # 1. 必需文件
    for f in REQUIRED_FILES:
        if not (merged / f).exists():
            problems.append(f"缺必需文件: {f}")
    shards_m = sorted(merged.glob("model-*.safetensors"))
    if not shards_m:
        problems.append("合并目录没有 model-*.safetensors 分片")
    infos.append(f"合并分片数: {len(shards_m)}")

    # 2/3. 分片 header + 键集合 + offset
    merged_keys = {}
    total_params = 0
    for sp in shards_m:
        hlen, keys, fsize = shard_keys(sp)
        problems += check_offsets(sp.name, keys, hlen, fsize)
        for k, v in keys.items():
            if k in merged_keys:
                problems.append(f"重复张量键: {k}（{merged_keys[k][0]} 与 {sp.name}）")
            merged_keys[k] = (sp, v)
            nb = 1
            for d in v[1]:
                nb *= d
            total_params += nb
    infos.append(f"合并参数量: {total_params:,} ({total_params/1e9:.4f} B)")

    # 4. index 对齐
    idx_path = merged / "model.safetensors.index.json"
    if idx_path.exists():
        idx = json.load(open(idx_path, encoding="utf-8"))
        wm = idx.get("weight_map", {})
        idx_keys = set(wm.keys())
        hdr_keys = set(merged_keys.keys())
        miss = idx_keys - hdr_keys
        extra = hdr_keys - idx_keys
        if miss:
            problems.append(f"index 有 {len(miss)} 个键在分片中不存在: {list(miss)[:5]}")
        if extra:
            problems.append(f"分片有 {len(extra)} 个键不在 index 中: {list(extra)[:5]}")
        # 键 -> 分片文件名一致性
        wrong = [(k, v, merged_keys[k][0].name) for k, v in wm.items()
                 if k in merged_keys and v != merged_keys[k][0].name]
        if wrong:
            problems.append(f"index 分片归属错误 {len(wrong)} 处: {wrong[:3]}")
        infos.append(f"index 键数: {len(wm)}，与分片键集合{'一致' if not miss and not extra else '不一致'}")
        total_size = idx.get("metadata", {}).get("total_size")
        if total_size:
            actual = sum(shard_keys(sp)[2] - 8 - shard_keys(sp)[0] for sp in shards_m)
            if int(total_size) != actual:
                problems.append(f"index total_size={total_size} != 实际数据区 {actual}")
            else:
                infos.append(f"index total_size 与实际数据区一致: {actual:,} bytes")

    # 5. config + chat_template
    cfg = json.load(open(merged / "config.json", encoding="utf-8"))
    infos.append(f"config: model_type={cfg.get('model_type')} "
                 f"hidden={cfg.get('hidden_size')} layers={cfg.get('num_hidden_layers')} "
                 f"dtype={cfg.get('torch_dtype')}")
    tokcfg = json.load(open(merged / "tokenizer_config.json", encoding="utf-8"))
    ct = tokcfg.get("chat_template")
    has_tools = bool(ct) and ("tools" in ct)
    infos.append(f"chat_template: {'YES len=%d' % len(ct) if ct else 'NO'}"
                 + ("（含 tools 段）" if has_tools else ""))
    if not ct:
        problems.append("tokenizer_config.json 缺 chat_template（对话/工具调用会失败）")

    # 6/7. 与基座对比
    if base and (base / "config.json").exists():
        base_shards = sorted(base.glob("model-*.safetensors"))
        base_keys = {}
        for sp in base_shards:
            _, keys, _ = shard_keys(sp)
            for k, v in keys.items():
                base_keys[k] = (sp, v)
        if set(base_keys.keys()) != set(merged_keys.keys()):
            problems.append(f"基座/合并张量键集合不一致: "
                            f"仅基座{len(set(base_keys)-set(merged_keys))} "
                            f"仅合并{len(set(merged_keys)-set(base_keys))}")
        struct_diff = [(k, base_keys[k][1], merged_keys[k][1]) for k in base_keys
                       if k in merged_keys and (base_keys[k][1][0] != merged_keys[k][1][0]
                                                or base_keys[k][1][1] != merged_keys[k][1][1])]
        if struct_diff:
            problems.append(f"{len(struct_diff)} 个张量 dtype/shape 与基座不一致: {struct_diff[:3]}")
        else:
            infos.append("所有张量 dtype/shape 与基座完全一致")

        # 幅度统计：分层抽样 target 张量
        targets = [k for k in merged_keys if k.startswith("model.layers.") and
                   k.endswith((".q_proj.weight", ".k_proj.weight", ".v_proj.weight",
                               ".o_proj.weight", ".gate_proj.weight", ".up_proj.weight",
                               ".down_proj.weight"))]
        step = max(1, len(targets) // args.samples)
        picked = targets[::step][:args.samples]
        ratios = []
        print("=== 合并幅度抽样（delta_rms / base_rms） ===")
        for k in picked:
            rb, rd, ratio = tensor_diff(base_keys[k][0], merged_keys[k][0], k,
                                        base_keys[k][1], merged_keys[k][1])
            ratios.append(ratio)
            print(f"  {k:58s} base_rms={rb:.4f} delta_rms={rd:.4f} ratio={ratio:.3%}")
        if ratios:
            mx, mean = max(ratios), sum(ratios) / len(ratios)
            infos.append(f"delta/base RMS: mean={mean:.3%} max={mx:.3%} (n={len(ratios)})")
            # 经验阈值：正常 LoRA 合并通常 <10%；>30% 有过合并风险
            if mx > 0.30:
                problems.append(f"[WARN] delta/base RMS 最大 {mx:.1%} > 30%，"
                                f"存在过合并风险，建议改用 --mode delta 或降低权重")
    else:
        infos.append("未提供 --base，跳过结构对比与幅度统计")

    # 输出
    print("\n=== 校验信息 ===")
    for i in infos:
        print("  ", i)
    warns = [p for p in problems if p.startswith("[WARN]")]
    errs = [p for p in problems if not p.startswith("[WARN]")]
    print("\n=== 校验结果 ===")
    for w in warns:
        print("  [WARN]", w)
    for e in errs:
        print("  [FAIL]", e)
    status = "PASS" if not errs and not warns else "FAIL"
    print(f"\n  结构校验: {status}"
          f"（{len(errs)} 错误, {len(warns)} 警告）")
    report = {"status": status, "merged": str(merged), "base": str(base) if base else None,
              "infos": infos, "warnings": warns, "errors": errs,
              "total_params": total_params, "shards": [s.name for s in shards_m],
              "artifact_manifest": artifact_manifest(merged)}
    out = merged / "validation_report.json"
    json.dump(report, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"  报告 -> {out}")
    sys.exit(0 if not errs else 1)


if __name__ == "__main__":
    main()
