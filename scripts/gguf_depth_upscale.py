#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GGUF v3 depth up-scaler for Virtu (SOLAR-style layer duplication).

Goal: turn the real 8.190735360 B model into a real >=10 B model by appending
copied (NON-ZERO, information-bearing) transformer blocks. No metadata field
claiming a parameter count is written: the loader derives 10.1B from tensor
dimensions by itself. Zero torch, zero network, pure stdlib + struct.

Usage:
  python scripts/gguf_depth_upscale.py \
      --src  checkpoints/virtu-comprehensive-q4_0.gguf \
      --out  checkpoints/virtu-10b-d46-q4_0.gguf \
      --target-layers 46 --copy-from 18

  python scripts/gguf_depth_upscale.py --verify \
      --out checkpoints/virtu-10b-d46-q4_0.gguf
"""

import argparse
import hashlib
import json
import os
import struct
import sys
import time

MAGIC = b"GGUF"
DEFAULT_ALIGNMENT = 32
CHUNK = 4 << 20  # 4 MiB

# gguf_metadata_value_type
PACK_FMT = {0: "<B", 1: "<b", 2: "<H", 3: "<h", 4: "<I", 5: "<i",
            6: "<f", 7: "<?", 10: "<Q", 11: "<q", 12: "<d"}


def align_up(n, a):
    return (n + a - 1) // a * a


def sha256_file(path, start=0, length=None):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        f.seek(start)
        remain = length
        while True:
            n = CHUNK if remain is None else min(CHUNK, remain)
            if n <= 0:
                break
            b = f.read(n)
            if not b:
                break
            h.update(b)
            if remain is not None:
                remain -= len(b)
    return h.hexdigest()


# --------------------------------------------------------------------------
# Reader
# --------------------------------------------------------------------------
class Reader:
    def __init__(self, f):
        self.f = f

    def u8(self):
        return struct.unpack("<B", self.f.read(1))[0]

    def u32(self):
        return struct.unpack("<I", self.f.read(4))[0]

    def u64(self):
        return struct.unpack("<Q", self.f.read(8))[0]

    def string(self):
        n = self.u64()
        return self.f.read(n).decode("utf-8", "replace")

    def value(self, t):
        if t in PACK_FMT:
            return struct.unpack(PACK_FMT[t], self.f.read(struct.calcsize(PACK_FMT[t])))[0]
        if t == 8:
            return self.string()
        if t == 9:
            et = self.u32()
            n = self.u64()
            return (et, [self.value(et) for _ in range(n)])
        raise ValueError("unsupported metadata value type %d" % t)


def read_header(path):
    """Return (version, metadata list, tensor info list, data_offset, alignment)."""
    with open(path, "rb") as f:
        r = Reader(f)
        magic = f.read(4)
        if magic != MAGIC:
            raise ValueError("not a GGUF file: %r" % magic)
        version, n_tensors, n_kv = r.u32(), r.u64(), r.u64()
        if version != 3:
            raise ValueError("only GGUF v3 supported, got %d" % version)
        metadata = []
        for _ in range(n_kv):
            key = r.string()
            t = r.u32()
            v = r.value(t)
            metadata.append((key, t, v))
        infos = []
        for _ in range(n_tensors):
            name = r.string()
            n_dims = r.u32()
            dims = [r.u64() for _ in range(n_dims)]
            typ = r.u32()
            off = r.u64()
            infos.append({"name": name, "dims": dims, "type": typ, "offset": off})
        header_end = f.tell()

    md = dict((k, v) for k, t, v in metadata)
    alignment = md.get("general.alignment", DEFAULT_ALIGNMENT)
    if isinstance(alignment, tuple):
        raise ValueError("general.alignment has unexpected array type")
    alignment = int(alignment)
    data_offset = align_up(header_end, alignment)
    return version, metadata, infos, data_offset, alignment


# --------------------------------------------------------------------------
# Writer
# --------------------------------------------------------------------------
def enc_string(s):
    b = s.encode("utf-8")
    return struct.pack("<Q", len(b)) + b


def enc_value(t, v):
    if t in PACK_FMT:
        return struct.pack(PACK_FMT[t], v)
    if t == 8:
        return enc_string(v)
    if t == 9:
        et, items = v
        return (struct.pack("<I", et) + struct.pack("<Q", len(items))
                + b"".join(enc_value(et, x) for x in items))
    raise ValueError("unsupported metadata value type %d" % t)


def build_header(version, metadata, infos, alignment):
    out = bytearray()
    out += MAGIC
    out += struct.pack("<I", version)
    out += struct.pack("<Q", len(infos))
    out += struct.pack("<Q", len(metadata))
    for key, t, v in metadata:
        out += enc_string(key)
        out += struct.pack("<I", t)
        out += enc_value(t, v)
    for info in infos:
        out += enc_string(info["name"])
        out += struct.pack("<I", len(info["dims"]))
        for d in info["dims"]:
            out += struct.pack("<Q", d)
        out += struct.pack("<I", info["type"])
        out += struct.pack("<Q", info["offset"])
    pad = align_up(len(out), alignment) - len(out)
    out += b"\x00" * pad
    return bytes(out)


def copy_range(src_f, dst_f, src_start, length, label=""):
    src_f.seek(src_start)
    remain = length
    while remain > 0:
        b = src_f.read(min(CHUNK, remain))
        if not b:
            raise IOError("unexpected EOF while copying %s" % label)
        dst_f.write(b)
        remain -= len(b)


# --------------------------------------------------------------------------
# Core
# --------------------------------------------------------------------------
def tensor_nelems(info):
    n = 1
    for d in info["dims"]:
        n *= d
    return n


def segment_lengths(infos, data_len, alignment):
    """Derive each tensor's byte span from the next offset (includes padding)."""
    order = sorted(range(len(infos)), key=lambda i: infos[i]["offset"])
    for i, idx in enumerate(order):
        off = infos[idx]["offset"]
        if off % alignment != 0:
            raise ValueError("tensor %s offset %d not %d-aligned"
                             % (infos[idx]["name"], off, alignment))
        end = infos[order[i + 1]]["offset"] if i + 1 < len(order) else data_len
        if end <= off:
            raise ValueError("bad tensor span for %s" % infos[idx]["name"])
        infos[idx]["nbytes"] = end - off
    return infos


def upscale(src, out, target_layers, copy_from, name):
    t0 = time.time()
    version, metadata, infos, data_offset, alignment = read_header(src)
    src_size = os.path.getsize(src)
    data_len = src_size - data_offset

    md = dict((k, v) for k, t, v in metadata)
    src_layers = int(md["qwen3.block_count"])
    if target_layers <= src_layers:
        raise ValueError("target_layers must exceed %d" % src_layers)
    add = target_layers - src_layers
    if copy_from + add > src_layers:
        raise ValueError("copy_from+add exceeds source layer count")

    infos = segment_lengths(infos, data_len, alignment)
    by_name = dict((i["name"], i) for i in infos)

    # metadata: change ONLY block_count and general.name
    new_md = []
    changed = set()
    for key, t, v in metadata:
        if key == "qwen3.block_count":
            new_md.append((key, t, target_layers))
            changed.add(key)
        elif key == "general.name":
            new_md.append((key, t, name))
            changed.add(key)
        else:
            new_md.append((key, t, v))
    if "qwen3.block_count" not in changed or "general.name" not in changed:
        raise ValueError("missing block_count / general.name in metadata")

    # append new tensors, named blk.<src+i+1>.*
    new_infos = list(infos)
    plan = []          # (new_name, source_name, source_info, new_offset)
    cursor = align_up(data_len, alignment)
    for j in range(add):
        s_layer = copy_from + j
        d_layer = src_layers + j
        # fixed order == blk.0 ordering of the source file
        s_names = [i["name"] for i in infos
                   if i["name"].startswith("blk.%d." % s_layer)]
        if len(s_names) != 11:
            raise ValueError("layer %d has %d tensors (expected 11)"
                             % (s_layer, len(s_names)))
        for s_name in s_names:
            suffix = s_name.split(".", 2)[2]
            d_name = "blk.%d.%s" % (d_layer, suffix)
            si = by_name[s_name]
            plan.append((d_name, s_name, si, cursor))
            new_infos.append({"name": d_name, "dims": list(si["dims"]),
                              "type": si["type"], "offset": cursor})
            cursor += si["nbytes"]

    header = build_header(version, new_md, new_infos, alignment)
    new_data_offset = len(header)

    # write
    tmp = out + ".tmp"
    with open(src, "rb") as sf, open(tmp, "wb") as df:
        df.write(header)
        copy_range(sf, df, data_offset, data_len, "original data region")
        df.write(b"\x00" * (align_up(data_len, alignment) - data_len))
        for d_name, s_name, si, new_off in plan:
            copy_range(sf, df, data_offset + si["offset"], si["nbytes"], s_name)
    os.replace(tmp, out)

    # ---------------- verification (G-A1..G-A4) ----------------
    v_meta, v_infos, v_data_offset = read_header(out)[1:4]
    vm = dict((k, v) for k, t, v in v_meta)
    total_params = sum(tensor_nelems(i) for i in v_infos)
    checks = {}
    checks["n_tensors"] = (len(v_infos), len(v_infos) == len(new_infos))
    checks["block_count"] = (vm.get("qwen3.block_count"),
                             vm.get("qwen3.block_count") == target_layers)
    checks["total_params"] = (total_params, total_params >= 10_000_000_000)
    checks["no_param_count_metadata"] = (
        [k for k in vm if "parameter_count" in k],
        not any("parameter_count" in k for k in vm))

    v_infos = segment_lengths(v_infos, os.path.getsize(out) - v_data_offset, alignment)
    v_by_name = dict((i["name"], i) for i in v_infos)

    # G-A2: every new tensor byte-identical to its source tensor
    sha_pairs, all_equal = [], True
    nonzero_all = True
    for d_name, s_name, si, new_off in plan:
        a = sha256_file(src, data_offset + si["offset"], si["nbytes"])
        b = sha256_file(out, v_data_offset + v_by_name[d_name]["offset"],
                        si["nbytes"])
        eq = (a == b)
        all_equal &= eq
        # non-zero check: a copied real weight segment must not be all zeros
        with open(out, "rb") as f:
            f.seek(v_data_offset + v_by_name[d_name]["offset"])
            seg = f.read(min(si["nbytes"], 1 << 20))
        nonzero = any(seg)
        nonzero_all &= nonzero
        sha_pairs.append({"new": d_name, "source": s_name,
                          "src_sha256": a, "dst_sha256": b,
                          "byte_identical": eq, "nonzero": nonzero,
                          "nbytes": si["nbytes"]})
    checks["new_tensors_byte_identical"] = (len(plan), all_equal)
    checks["new_tensors_nonzero"] = (len(plan), nonzero_all)

    # G-A4: original data region preserved verbatim
    a = sha256_file(src, data_offset, data_len)
    b = sha256_file(out, v_data_offset, data_len)
    checks["original_data_region_unchanged"] = ({"src": a, "dst": b}, a == b)

    failed = [k for k, (_, ok) in checks.items() if not ok]
    src_sha = sha256_file(src)
    script_sha = sha256_file(os.path.abspath(__file__))
    run_id = hashlib.sha256(
        ("%s|%s|%d|%d|%d" % (src_sha, script_sha, src_layers,
                              target_layers, copy_from)).encode()).hexdigest()[:16]
    receipt = {
        "run_id": run_id,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "basis": "measured",
        "method": "SOLAR-style depth up-scaling (byte-exact layer duplication)",
        "source": {"path": os.path.abspath(src), "sha256": src_sha,
                   "bytes": src_size, "layers": src_layers,
                   "params": sum(tensor_nelems(i) for i in infos)},
        "output": {"path": os.path.abspath(out),
                   "sha256": sha256_file(out),
                   "bytes": os.path.getsize(out),
                   "layers": target_layers,
                   "params": total_params,
                   "n_tensors": len(v_infos),
                   "general.name": vm.get("general.name"),
                   "quantization": "Q4_0 (unchanged)",
                   "alignment": alignment},
        "copy_plan": {"copy_from": copy_from, "added_layers": add,
                      "source_layers": list(range(copy_from, copy_from + add)),
                      "target_layers": list(range(src_layers, target_layers)),
                      "tensors_per_layer": 11},
        "checks": dict((k, {"value": val, "pass": ok}) for k, (val, ok) in checks.items()),
        "gate_A_pass": len(failed) == 0,
        "failed_checks": failed,
        "n": len(plan),
        "elapsed_sec": round(time.time() - t0, 2),
        "claims": [
            "L1 structural >=10B: ACHIEVED (loader-derived parameter count)",
            "L2 capability >=10B: NOT CLAIMED - copied layers require continued pretraining",
        ],
        "tensor_evidence": sha_pairs,
    }
    with open(out + ".receipt.json", "w", encoding="utf-8") as f:
        json.dump(receipt, f, ensure_ascii=False, indent=2)

    print("run_id            :", run_id)
    print("output            :", out)
    print("size              : %d B (%.2f GiB)" % (receipt["output"]["bytes"],
                                                    receipt["output"]["bytes"] / 2**30))
    print("layers            : %d -> %d (+%d)" % (src_layers, target_layers, add))
    print("n_tensors         : %d -> %d" % (399, len(v_infos)))
    print("TOTAL PARAMS      : %d  = %.6f B" % (total_params, total_params / 1e9))
    print("elapsed           : %.1f s" % receipt["elapsed_sec"])
    for k, (val, ok) in checks.items():
        print("  [%s] %-38s %s" % ("PASS" if ok else "FAIL", k,
                                   str(val)[:90]))
    print("GATE A            :", "PASS" if not failed else "FAIL " + str(failed))
    print("receipt           :", out + ".receipt.json")
    return 0 if not failed else 1


def verify(out):
    version, metadata, infos, data_offset, alignment = read_header(out)
    vm = dict((k, v) for k, t, v in metadata)
    total = sum(tensor_nelems(i) for i in infos)
    print("file        :", out)
    print("bytes       :", os.path.getsize(out))
    print("sha256      :", sha256_file(out))
    print("version     :", version)
    print("n_tensors   :", len(infos))
    print("block_count :", vm.get("qwen3.block_count"))
    print("general.name:", vm.get("general.name"))
    print("alignment   :", alignment)
    print("TOTAL PARAMS: %d = %.6f B" % (total, total / 1e9))
    from collections import Counter
    c = Counter(i["name"].split(".")[1] for i in infos if i["name"].startswith("blk."))
    print("layers found:", len(c), "tensors/layer:", set(c.values()))
    rpath = out + ".receipt.json"
    if os.path.exists(rpath):
        r = json.load(open(rpath, encoding="utf-8"))
        print("receipt run_id:", r["run_id"], "gate_A_pass:", r["gate_A_pass"])
        print("receipt params:", r["output"]["params"],
              "match:", r["output"]["params"] == total)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src")
    ap.add_argument("--out")
    ap.add_argument("--target-layers", type=int, default=46)
    ap.add_argument("--copy-from", type=int, default=18)
    ap.add_argument("--name", default="virtu-10b-d46-merged")
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args()
    if a.verify:
        if not a.out:
            ap.error("--verify needs --out")
        return verify(a.out)
    if not a.src or not a.out:
        ap.error("--src and --out are required")
    if os.path.abspath(a.src) == os.path.abspath(a.out):
        ap.error("src and out must differ")
    return upscale(a.src, a.out, a.target_layers, a.copy_from, a.name)


if __name__ == "__main__":
    sys.exit(main())
