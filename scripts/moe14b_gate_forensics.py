# -*- coding: utf-8 -*-
"""
scripts/moe14b_gate_forensics.py — Virtu-MoE-14B（13.63B 稀疏总参）资产独立取证

不采信任何 receipt：直接从 GGUF 字节重算参数量、逐张量 sha256，回答两个问题：
  Q1 两个 GGUF（随机门 vs 语义门）到底差在哪些字节上？除路由外是否逐字节相同？
  Q2 路由张量本身长什么样（行范数、行间余弦、每层门控是否真的互不相同）？

量化块几何不写死枚举，而是从「张量偏移间隔」反推并对每个张量校验
（exact <= span < exact+alignment），任何一个对不上即硬失败——避免把 dtype 序号记错
导致静默算错字节。

用法：
  python scripts/moe14b_gate_forensics.py
  python scripts/moe14b_gate_forensics.py --a X.gguf --b Y.gguf --out runs/xx.json --skip-hash
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import struct
import sys
from fractions import Fraction

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GGUF_MAGIC = b"GGUF"

T_UINT8, T_INT8, T_UINT16, T_INT16, T_UINT32, T_INT32, T_FLOAT32, T_BOOL = 0, 1, 2, 3, 4, 5, 6, 7
T_STRING, T_ARRAY, T_UINT64, T_INT64, T_FLOAT64 = 8, 9, 10, 11, 12

# (block_elems, block_bytes, label) candidates — geometry only, no enum-index assumptions.
GEOMETRY_CANDIDATES = [
    (1, 4, "F32"), (1, 2, "F16/BF16"),
    (32, 18, "Q4_0"), (32, 20, "Q4_1"), (32, 22, "Q5_0"), (32, 24, "Q5_1"), (32, 34, "Q8_0"),
    (256, 84, "Q2_K"), (256, 110, "Q3_K"), (256, 144, "Q4_K"), (256, 176, "Q5_K"),
    (256, 210, "Q6_K"), (256, 292, "Q8_K"),
    (128, 68, "IQ4_NL"), (256, 136, "IQ4_XS"), (256, 108, "IQ3_XXS"), (256, 128, "IQ3_S"),
    (256, 72, "IQ2_XS?"), (256, 66, "IQ2_XXS"), (256, 96, "IQ2_S/IQ1_M"),
]

# ggml dtype enum -> (block_elems, block_bytes, label). This table is NOT trusted blindly:
# infer_geometry() checks it against the observed tensor-offset spans and hard-fails on any
# mismatch, so a wrong enum index cannot silently produce wrong byte counts.
# Two types share 4.5 bpw (Q4_0 / Q4_K), so layout alone is ambiguous and the index is needed.
ENUM_GEOMETRY = {
    0: (1, 4, "F32"), 1: (1, 2, "F16"), 2: (32, 18, "Q4_0"), 3: (32, 20, "Q4_1"),
    6: (32, 22, "Q5_0"), 7: (32, 24, "Q5_1"), 8: (32, 34, "Q8_0"),
    10: (256, 84, "Q2_K"), 11: (256, 110, "Q3_K"), 12: (256, 144, "Q4_K"),
    13: (256, 176, "Q5_K"), 14: (256, 210, "Q6_K"), 15: (256, 292, "Q8_K"),
    16: (256, 66, "IQ2_XXS"), 17: (256, 72, "IQ2_XS"), 18: (256, 108, "IQ3_XXS"),
    20: (128, 68, "IQ4_NL"), 21: (256, 128, "IQ3_S"), 22: (256, 96, "IQ2_S"),
    23: (256, 136, "IQ4_XS"), 24: (1, 1, "I8"), 25: (1, 2, "I16"), 26: (1, 4, "I32"),
    27: (1, 8, "I64"), 28: (1, 8, "F64"), 29: (256, 96, "IQ1_M"), 30: (1, 2, "BF16"),
}




class Reader:
    def __init__(self, f):
        self.f = f

    def raw(self, n):
        b = self.f.read(n)
        if len(b) != n:
            raise EOFError(f"short read: wanted {n} got {len(b)}")
        return b

    def u32(self):
        return struct.unpack("<I", self.raw(4))[0]

    def i32(self):
        return struct.unpack("<i", self.raw(4))[0]

    def u64(self):
        return struct.unpack("<Q", self.raw(8))[0]

    def f32(self):
        return struct.unpack("<f", self.raw(4))[0]

    def string(self):
        return self.raw(self.u64()).decode("utf-8", "replace")

    def value(self, t):
        if t == T_UINT8:
            return self.raw(1)[0]
        if t == T_INT8:
            return struct.unpack("<b", self.raw(1))[0]
        if t == T_UINT16:
            return struct.unpack("<H", self.raw(2))[0]
        if t == T_INT16:
            return struct.unpack("<h", self.raw(2))[0]
        if t == T_UINT32:
            return self.u32()
        if t == T_INT32:
            return self.i32()
        if t == T_UINT64:
            return self.u64()
        if t == T_INT64:
            return struct.unpack("<q", self.raw(8))[0]
        if t == T_FLOAT32:
            return self.f32()
        if t == T_FLOAT64:
            return struct.unpack("<d", self.raw(8))[0]
        if t == T_BOOL:
            return bool(self.raw(1)[0])
        if t == T_STRING:
            return self.string()
        raise ValueError(f"unknown GGUF kv type {t}")

    def array(self):
        elem_t = self.u32()
        return [self.value(elem_t) for _ in range(self.u64())]


def read_header(path):
    with open(path, "rb") as f:
        r = Reader(f)
        if r.raw(4) != GGUF_MAGIC:
            raise ValueError(f"{path}: not a GGUF file")
        version = r.u32()
        n_tensors = r.u64()
        n_kv = r.u64()
        kv = {}
        for _ in range(n_kv):
            k = r.string()
            t = r.u32()
            kv[k] = r.array() if t == T_ARRAY else r.value(t)
        infos = []
        for _ in range(n_tensors):
            name = r.string()
            dims = [r.u64() for _ in range(r.u32())]
            dtype = r.u32()
            off = r.u64()
            infos.append({"name": name, "dims": dims, "dtype": dtype, "offset": off})
        info_end = f.tell()
    return kv, infos, version, n_tensors, n_kv, info_end


def infer_geometry(infos, file_size, data_start, align):
    """Pick, per dtype, the (block_elems, block_bytes) consistent with every tensor's offset span."""
    ordered = sorted(infos, key=lambda x: x["offset"])
    for i in range(1, len(ordered)):
        if ordered[i]["offset"] <= ordered[i - 1]["offset"]:
            raise ValueError("tensor offsets not strictly increasing; layout assumption broken")
    spans = {}
    for i, m in enumerate(ordered):
        nxt = ordered[i + 1]["offset"] if i + 1 < len(ordered) else file_size - data_start
        spans[m["name"]] = nxt - m["offset"]

    groups = {}
    for m in infos:
        n = int(np.prod(m["dims"])) if m["dims"] else 0
        groups.setdefault(m["dtype"], []).append((n, spans[m["name"]]))

    resolved = {}
    for dtype, items in sorted(groups.items()):
        if dtype not in ENUM_GEOMETRY:
            raise ValueError(f"dtype {dtype}: not in ENUM_GEOMETRY; refusing to guess byte layout")
        bs, ts, label = ENUM_GEOMETRY[dtype]

        def fits_geometry(bs_, ts_, items=items):
            return all(n % bs_ == 0 and (n // bs_) * ts_ <= span < (n // bs_) * ts_ + max(align, 1)
                       for n, span in items)

        if not fits_geometry(bs, ts):
            alt = [c for c in GEOMETRY_CANDIDATES if fits_geometry(c[0], c[1])]
            ub = max(Fraction(span * 8, n) for n, span in items)
            raise ValueError(
                f"dtype {dtype} ({label}): declared geometry bs={bs} ts={ts} contradicts the "
                f"file layout (observed <= {float(ub):.3f} bpw; candidates that fit: "
                f"{[c[2] for c in alt]}). Refusing to produce numbers from a wrong table.")
        resolved[dtype] = (bs, ts, label)
    return resolved


def build_tensor_map(infos, geometry, data_start):
    out = {}
    for m in infos:
        bs, ts, label = geometry[m["dtype"]]
        n = int(np.prod(m["dims"])) if m["dims"] else 0
        if n % bs:
            raise ValueError(f"{m['name']}: {n} elems not a multiple of block {bs}")
        out[m["name"]] = {"dtype": m["dtype"], "dtype_label": label, "dims": m["dims"],
                          "elems": n, "offset": m["offset"], "nbytes": (n // bs) * ts,
                          "abs_start": data_start + m["offset"]}
    return out


def hash_tensors(path, tensors):
    res = {}
    with open(path, "rb") as f:
        for name, m in sorted(tensors.items(), key=lambda kv_: kv_[1]["abs_start"]):
            f.seek(m["abs_start"])
            h = hashlib.sha256()
            remaining = m["nbytes"]
            while remaining > 0:
                chunk = f.read(min(remaining, 1 << 22))
                if not chunk:
                    raise EOFError(f"{path}:{name}: truncated")
                h.update(chunk)
                remaining -= len(chunk)
            res[name] = h.hexdigest()
    return res


def read_f32_tensor(path, m):
    if m["dtype_label"] != "F32":
        raise ValueError(f"{m['name']}: expected F32 gate, got {m['dtype_label']}")
    with open(path, "rb") as f:
        f.seek(m["abs_start"])
        buf = f.read(m["nbytes"])
    if len(buf) != m["nbytes"]:
        raise EOFError(f"{m['name']}: truncated")
    return np.frombuffer(buf, dtype=np.float32).reshape(m["dims"])


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def param_report(tensors):
    total = 0
    by_dtype, by_class = {}, dict.fromkeys(
        ["gate", "expert_ffn", "shared_ffn", "attn", "embed", "norm", "other"], 0)
    for name, m in tensors.items():
        n = m["elems"]
        total += n
        by_dtype[m["dtype_label"]] = by_dtype.get(m["dtype_label"], 0) + n
        if "ffn_gate_inp" in name:
            by_class["gate"] += n
        elif "exps" in name:
            by_class["expert_ffn"] += n
        elif "ffn_" in name:
            by_class["shared_ffn"] += n
        elif "attn" in name:
            by_class["attn"] += n
        elif "token_embd" in name or name == "output.weight":
            by_class["embed"] += n
        elif "norm" in name:
            by_class["norm"] += n
        else:
            by_class["other"] += n
    return total, by_dtype, by_class


def gate_stats(path, tensors, n_experts=2, hidden=None):
    """Routing geometry of the MoE gate, read in the CORRECT orientation.

    GGUF stores tensor dims in reverse (column-major) order, so a `ffn_gate_inp.weight`
    with header dims [hidden, n_experts] is logically (n_experts, hidden): expert e's vector
    is w[:, e] of the C-order view, NOT w[e]. Getting this wrong turns every norm/cosine
    below into a statistic over 2-element fragments — which is what the 2026-11-06
    router_audit numbers were measured on.
    """
    names = sorted(n for n in tensors if n.endswith("ffn_gate_inp.weight"))
    if not names:
        raise ValueError("no ffn_gate_inp.weight tensors found — not a MoE file")
    mats = {n: read_f32_tensor(path, tensors[n]) for n in names}
    shape = mats[names[0]].shape
    if min(shape) != n_experts:
        raise ValueError(f"gate shape {shape} does not contain {n_experts} experts")
    if hidden is not None and max(shape) != hidden:
        raise ValueError(f"gate shape {shape} disagrees with declared hidden={hidden}")

    hid = shape[1] if min(shape) == shape[0] else max(shape)
    ones_dir = np.ones(hid, dtype=np.float64) / np.sqrt(float(hid))
    per_layer = []
    for n in names:
        E = mats[n].astype(np.float64).T          # (n_experts, hidden) — logical orientation
        rn = np.linalg.norm(E, axis=1)
        if rn.min() <= 0:
            raise ValueError(f"{n}: zero-norm gate row, routing would be degenerate")
        cos01 = float(np.dot(E[0], E[1]) / (rn[0] * rn[1]))
        # energy of each row explained by the all-ones direction (a "global mean activation" probe)
        proj = np.abs(E @ ones_dir) / rn
        frac_ones = (proj ** 2).tolist()
        # decision boundary normal: margin(h) = (r0-r1).h, so this tells what actually flips experts
        nb = E[0] - E[1]
        ones_align_boundary = float(np.dot(nb, ones_dir) / np.linalg.norm(nb))
        sv = np.linalg.svd(E, compute_uv=False)
        rank_deficient = bool(sv[-1] <= 1e-12 * max(sv[0], 1e-12))
        per_layer.append({
            "layer": n, "row_norms": [round(float(x), 6) for x in rn],
            "cos_rows": round(cos01, 6),
            "frac_energy_in_ones_dir": [round(x, 6) for x in frac_ones],
            "boundary_align_to_ones": round(ones_align_boundary, 6),
            # identical or opposite expert rows make the gate rank-1: the two experts become
            # one direction and routing collapses. Recorded, never averaged into a nan.
            "cond_number": None if rank_deficient else round(float(sv[0] / sv[-1]), 6),
            "rank_deficient": rank_deficient,
        })

    def agg(key):
        return [pl[key] for pl in per_layer]

    def aggstats(vals):
        v = np.asarray([x for x in vals if x is not None], dtype=np.float64)
        if v.size == 0:
            return {"mean": None, "min": None, "max": None, "n_defined": 0}
        return {"mean": round(float(v.mean()), 6), "min": round(float(v.min()), 6),
                "max": round(float(v.max()), 6), "n_defined": int(v.size)}

    rows_all = np.vstack([mats[n].astype(np.float64).T for n in names])
    norms_all = np.linalg.norm(rows_all, axis=1)
    return {
        "orientation_note": "header dims [4096,2] are column-major; logical shape is (2 experts, 4096 hidden)",
        "n_gate_tensors": len(names),
        "distinct_gate_values": len({mats[n].tobytes() for n in names}),
        "all_gate_rows_nonzero": bool(np.all(norms_all > 0)),
        "expert_row_norm_mean": round(float(norms_all.mean()), 6),
        "expert_row_norm_min": round(float(norms_all.min()), 6),
        "expert_row_norm_max": round(float(norms_all.max()), 6),
        "cos_rows": aggstats(agg("cos_rows")),
        "boundary_align_to_ones": aggstats(agg("boundary_align_to_ones")),
        "frac_energy_in_ones_dir_e0": aggstats([pl["frac_energy_in_ones_dir"][0] for pl in per_layer]),
        "frac_energy_in_ones_dir_e1": aggstats([pl["frac_energy_in_ones_dir"][1] for pl in per_layer]),
        "cond_number": aggstats([pl["cond_number"] for pl in per_layer]),
        "rank_deficient_layers": sum(1 for pl in per_layer if pl["rank_deficient"]),
        "per_layer_first4": per_layer[:4],
    }



def _ollama_store_roots():
    home = os.path.expanduser("~")
    return [os.path.join(home, ".ollama", "models"), os.path.join(ROOT, "..", "ollama", "models"),
            r"E:\ollama\models"]


def resolve_artifact(spec):
    """按内容寻址定位被测权重：给定路径 > checkpoints/ 同名 > Ollama blob（按收据 sha256）。

    2026-11-06 的另一会话按 `space_cleanup_2026_11_06` 账本删掉了 D 侧 GGUF（字节仍在 E 盘
    blob 里），名字寻址会当场悬空。测量宪法第 2 条要求"被测对象按内容寻址，不按名字"，
    所以这里回退到 sha256 blob，并把回退事实写进结果，绝不静默换对象。
    """
    if spec and os.path.exists(spec):
        return spec, None
    name = os.path.basename(spec or "")
    local = os.path.join(ROOT, "checkpoints", name)
    if os.path.exists(local):
        return local, None
    receipt = local + ".receipt.json"
    note = None
    if os.path.exists(receipt):
        doc = json.load(open(receipt, encoding="utf-8"))
        digests = [doc.get("sha256")]
        if isinstance(doc.get("output"), dict):
            digests.append(doc["output"].get("sha256"))
        for d in [x for x in digests if x]:
            for root in _ollama_store_roots():
                blob = os.path.join(root, "blobs", f"sha256-{d}")
                if os.path.exists(blob):
                    note = (f"原路径 {spec} 已不存在（见 PROVENANCE#space_cleanup_2026_11_06）；"
                            f"按收据 sha256={d[:16]}… 回退到内容相同的 Ollama blob")
                    print(f"[fallback] {note}")
                    return blob, note
    raise FileNotFoundError(
        f"找不到被测权重 {spec}：checkpoints/ 与 Ollama blob 都没有它对应的字节。"
        f"若被清理，请用 scripts/d_model_space_cleanup.py --restore {name} 还原后再测。")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", default=os.path.join(ROOT, "checkpoints", "virtu-moe-14b-q4_k_m.gguf"))
    ap.add_argument("--b", default=os.path.join(ROOT, "checkpoints", "virtu-moe-14b-semantic-q4_k_m.gguf"))
    ap.add_argument("--out", default=os.path.join(ROOT, "runs", "moe14b_gate_forensics.json"))
    ap.add_argument("--skip-hash", action="store_true", help="skip the full per-tensor hash pass")
    args = ap.parse_args()

    orig_a, orig_b = args.a, args.b
    resolved = {}
    for tag, p in (("a", args.a), ("b", args.b)):
        try:
            path, note = resolve_artifact(p)
        except FileNotFoundError as exc:
            print(f"[FATAL] {exc}")
            return 2
        resolved[tag] = (path, note)
    args.a, note_a = resolved["a"]
    args.b, note_b = resolved["b"]

    script_sha = file_sha256(os.path.abspath(__file__))
    a_sha, b_sha = file_sha256(args.a), file_sha256(args.b)
    run_id = hashlib.sha256((a_sha + b_sha + script_sha).encode()).hexdigest()[:16]

    report = {
        "run_id": run_id,
        "artifact_resolution": {"a": {"requested": orig_a, "used": args.a, "fallback_note": note_a},
                                "b": {"requested": orig_b, "used": args.b, "fallback_note": note_b}},
        "generated_at": _dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S%z"),
        "basis": "measured",
        "tool": "scripts/moe14b_gate_forensics.py",
        "tool_sha256": script_sha,
        "inputs": {"a": {"path": args.a, "sha256": a_sha, "bytes": os.path.getsize(args.a)},
                   "b": {"path": args.b, "sha256": b_sha, "bytes": os.path.getsize(args.b)}},
    }

    parsed = {}
    for tag, path in (("a", args.a), ("b", args.b)):
        kv, infos, version, n_tensors, n_kv, info_end = read_header(path)
        align = int(kv.get("general.alignment", 32))
        data_start = (info_end + align - 1) // align * align
        geometry = infer_geometry(infos, os.path.getsize(path), data_start, align)
        tensors = build_tensor_map(infos, geometry, data_start)
        if len(tensors) != n_tensors:
            raise ValueError(f"{path}: duplicate tensor names ({len(tensors)} != {n_tensors})")
        parsed[tag] = (kv, tensors)
        report[f"header_{tag}"] = {
            "gguf_version": version, "n_tensors": n_tensors, "n_kv": n_kv,
            "alignment": align, "data_start": data_start,
            "dtype_geometry_inferred": {str(k): {"bs": v[0], "bytes": v[1], "label": v[2],
                                                 "bpw": round(v[1] * 8 / v[0], 4)}
                                        for k, v in geometry.items()},
        }

    kv_a, tn_a = parsed["a"]
    kv_b, tn_b = parsed["b"]
    total_a, by_dtype_a, by_class_a = param_report(tn_a)
    total_b, _, by_class_b = param_report(tn_b)

    arch_keys = [k for k in kv_a if k.startswith("qwen3moe.")] + ["general.architecture", "general.name"]
    report["architecture_kv"] = {k: kv_a[k] for k in arch_keys if k in kv_a}
    report["params"] = {"a_total_from_dims": total_a, "b_total_from_dims": total_b,
                        "a_by_class": by_class_a, "b_by_class": by_class_b,
                        "a_by_dtype_elems": by_dtype_a}

    def gi(key, default=0):
        return int(kv_a.get(f"qwen3moe.{key}", default))

    n_layer, n_experts, n_used = gi("block_count"), gi("expert_count"), gi("expert_used_count")
    h, ffn_e = gi("embedding_length"), gi("expert_feed_forward_length")
    shared_e = gi("expert_shared_feed_forward_length")
    if 0 in (n_layer, n_experts, n_used, h, ffn_e):
        print("[FATAL] MoE geometry metadata incomplete; refusing to derive active params")
        return 3
    inactive_ffn = (n_experts - n_used) * 3 * h * ffn_e * n_layer
    gate_params = n_experts * h * n_layer
    per_expert_ffn_from_tensors = sum(m["elems"] for n, m in tn_a.items() if "exps" in n) // n_experts
    report["active_param_derivation"] = {
        "n_layers": n_layer, "n_experts": n_experts, "n_experts_used": n_used,
        "hidden": h, "expert_ffn": ffn_e, "shared_expert_ffn": shared_e,
        "inactive_expert_ffn_params": inactive_ffn,
        "router_params": gate_params,
        "active_total_incl_router": total_a - inactive_ffn,
        "active_excl_router": total_a - inactive_ffn - gate_params,
        "formula": "active = total - (E - top_k) * 3 * hidden * expert_ffn * n_layer",
        "cross_check_expert_ffn_elems_from_tensors": per_expert_ffn_from_tensors,
        "cross_check_expert_ffn_elems_from_formula": 3 * h * ffn_e * n_layer,
        "cross_check_router_elems_from_tensors": by_class_a["gate"],
        "note": "shared_expert_ffn=0 ⇒ 无共享专家；每 token 只有 1 个专家的 FFN 参与计算；"
                "注意力/嵌入两专家共享，不折半。",
    }

    names_a, names_b = set(tn_a), set(tn_b)
    common = sorted(names_a & names_b)
    report["tensor_name_sets"] = {"only_in_a": sorted(names_a - names_b)[:20],
                                  "only_in_b": sorted(names_b - names_a)[:20],
                                  "count_a": len(names_a), "count_b": len(names_b)}
    meta_diff = [n for n in common
                 if (tn_a[n]["dtype"], tn_a[n]["dims"]) != (tn_b[n]["dtype"], tn_b[n]["dims"])]
    report["metadata_diff_count"] = len(meta_diff)
    report["metadata_diff_tensors"] = meta_diff[:20]

    report["gate_stats_a"] = gate_stats(args.a, tn_a, n_experts, h)
    report["gate_stats_b"] = gate_stats(args.b, tn_b, n_experts, h)
    report["gate_tensors_identical_between_files"] = all(
        read_f32_tensor(args.a, tn_a[n]).tobytes() == read_f32_tensor(args.b, tn_b[n]).tobytes()
        for n in common if n.endswith("ffn_gate_inp.weight"))

    if not args.skip_hash:
        ha, hb = hash_tensors(args.a, tn_a), hash_tensors(args.b, tn_b)
        diff = sorted(n for n in common if ha[n] != hb[n])
        report["hash_pass"] = {
            "differing_tensor_count": len(diff),
            "differing_tensors": diff[:80],
            "all_differences_are_ffn_gate_inp": bool(diff) and all("ffn_gate_inp" in n for n in diff),
            "identical_tensor_count": len(common) - len(diff),
        }

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(json.dumps({k: v for k, v in report.items()
                      if k not in ("gate_stats_a", "gate_stats_b", "architecture_kv")},
                     indent=2, ensure_ascii=False))
    print("\n[gate A] " + json.dumps(report["gate_stats_a"], ensure_ascii=False))
    print("[gate B] " + json.dumps(report["gate_stats_b"], ensure_ascii=False))
    print(f"\n[out] {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
