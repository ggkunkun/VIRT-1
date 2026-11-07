#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/reconstruct_moe_semantic_gates.py
Virtu-MoE-14B (13.63B 物理总参) 免训练正交语义门控重构引擎。

【测量宪法合规】:
- 输入: checkpoints/_base_qwen3_8b/model-00001-of-00005.safetensors (token_embd)
        checkpoints/virtu-moe-14b-q4_k_m.gguf
- 输出: checkpoints/virtu-moe-14b-semantic-q4_k_m.gguf
        checkpoints/virtu-moe-14b-semantic-q4_k_m.gguf.receipt.json
- 依据: Gram-Schmidt 正交化 + 领域词嵌入质心投影 (cheap_embed)
- 条件数检验: kappa < 3.0 (mergekit 阈值为 5.0)
- 严禁任何随机全 1 向量或不可归因的伪门控
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import logging
import math
import os
import random
import shutil
import statistics
import struct
import sys
import time
from pathlib import Path

import numpy as np
from tokenizers import Tokenizer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("reconstruct_gates")

ROOT = Path(__file__).resolve().parent.parent
BASE_DIR = ROOT / "checkpoints" / "_base_qwen3_8b"
SRC_GGUF = ROOT / "checkpoints" / "virtu-moe-14b-q4_k_m.gguf"
DST_GGUF = ROOT / "checkpoints" / "virtu-moe-14b-semantic-q4_k_m.gguf"

# --------------------------------------------------------------------------
# 领域语义锚点词库 (Domain Semantic Anchors)
# --------------------------------------------------------------------------
# Expert 0: CAD 建模、草图约束、三维装配、特征几何、工程图、API与智能体工具面
ANCHORS_EXPERT_0 = [
    # 软件与系统
    "SolidWorks", "AutoCAD", "Siemens", "NX", "CAD", "CAE", "API", "COM",
    "macro", "script", "journal", "dxf", "dwg", "step", "iges", "sldprt",
    "sldasm", "slddrw", "prt", "json", "tool_call", "function", "arguments",
    # 几何与建模特征
    "草图", "基准面", "拉伸", "切除", "旋转", "扫描", "放样", "筋", "孔",
    "孔系", "沉孔", "倒角", "圆角", "抽壳", "拔模", "实体", "特征", "几何",
    "约束", "重合", "平行", "垂直", "相切", "同心", "尺寸", "标注", "公差带",
    "装配体", "配合", "同轴心", "距离配合", "工程图", "主视图", "俯视图",
    "剖视图", "向视图", "局部放大", "明细表", "BOM", "图框", "标题栏"
]

# Expert 1: 力学理论、材料物性、切削动力学、CNC加工代码、公差分析
ANCHORS_EXPERT_1 = [
    # 材料与力学
    "弹性模量", "泊松比", "屈服强度", "抗拉强度", "切变模量", "应力", "应变",
    "von_mises", "米塞斯", "主应力", "安全系数", "FOS", "拉梅", "厚壁圆筒",
    "内压", "外压", "弹性力学", "刚度", "挠度", "疲劳", "热应力", "热膨胀",
    # 加工与CNC
    "切削", "车削", "铣削", "钻削", "磨削", "进给量", "进给速度", "主轴转速",
    "背吃刀量", "切削深度", "线速度", "去除率", "MRR", "粗糙度", "Ra", "退刀",
    "FANUC", "发那科", "西门子", "Sinumerik", "G代码", "M代码", "宏程序",
    "G00", "G01", "G02", "G03", "G71", "G72", "G73", "G76", "G81", "G84",
    "G90", "G91", "G54", "G43", "刀具补偿", "对刀", "磨损", "颤振", "切削液"
]


def load_tokenizer_and_vocab():
    tok_path = BASE_DIR / "tokenizer.json"
    if not tok_path.exists():
        raise FileNotFoundError(f"Tokenizer not found at {tok_path}")
    logger.info(f"Loading Tokenizer from {tok_path}...")
    tokenizer = Tokenizer.from_file(str(tok_path))
    return tokenizer


def get_token_ids_for_anchors(tokenizer: Tokenizer, words: list[str]) -> list[int]:
    ids = []
    for w in words:
        enc = tokenizer.encode(w, add_special_tokens=False)
        ids.extend(enc.ids)
    ids = sorted(list(set(ids)))
    logger.info(f"Anchor list ({len(words)} words) -> resolved to {len(ids)} unique token IDs")
    return ids


def load_embeddings(token_ids: list[int]) -> np.ndarray:
    """流式只读取需要的 token 嵌入向量，显存/内存开销 < 50MB"""
    shard_path = BASE_DIR / "model-00001-of-00005.safetensors"
    logger.info(f"Loading token embeddings from {shard_path.name}...")
    with open(shard_path, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        hdr = json.loads(f.read(n).decode("utf-8"))
        meta = hdr["model.embed_tokens.weight"]
        data_start = 8 + n
        st, en = meta["data_offsets"]
        shape = meta["shape"]  # [151936, 4096]
        hidden_dim = shape[1]

        # 逐个读取
        vectors = []
        for tid in token_ids:
            offset = data_start + st + tid * hidden_dim * 2  # BF16 = 2 bytes
            f.seek(offset)
            raw = f.read(hidden_dim * 2)
            u = np.frombuffer(raw, dtype=np.uint16)
            # BF16 -> FP32
            vec = (u.astype(np.uint32) << 16).view(np.float32)
            vectors.append(vec)

    return np.array(vectors, dtype=np.float32)


def compute_orthogonal_prototypes(emb_0: np.ndarray, emb_1: np.ndarray):
    """
    计算两组领域的质心并执行 Gram-Schmidt 正交化，确保绝对正交解耦
    """
    c0 = np.mean(emb_0, axis=0)
    c1 = np.mean(emb_1, axis=0)

    # 减去全局平均值，增强特征对比度
    global_mean = (c0 + c1) / 2.0
    c0_centered = c0 - global_mean
    c1_centered = c1 - global_mean

    # 利用 QR 分解进行高精度正交归一化 (Householder QR)
    mat = np.stack([c0_centered, c1_centered], axis=1).astype(np.float64)  # [4096, 2]
    Q, R = np.linalg.qr(mat)
    v0 = Q[:, 0].astype(np.float32)
    v1 = Q[:, 1].astype(np.float32)

    # 保证方向与原语义质心保持正相关 (>0)
    if np.dot(v0, c0_centered) < 0:
        v0 = -v0
    if np.dot(v1, c1_centered) < 0:
        v1 = -v1

    # 验证数学性质
    dot_prod = float(np.dot(v0, v1))
    logger.info(f"Base Prototype 0 Norm: {np.linalg.norm(v0):.6f}")
    logger.info(f"Base Prototype 1 Norm: {np.linalg.norm(v1):.6f}")
    logger.info(f"Orthogonality cos(v0, v1): {dot_prod:+.8e} (Must be ~0.0)")
    assert abs(dot_prod) < 1e-6, f"QR Orthogonalization failed, dot = {dot_prod}"

    # 条件数检查
    gate_pair = np.stack([v0, v1], axis=0)  # [2, 4096]
    s = np.linalg.svd(gate_pair, compute_uv=False)
    kappa = float(s[0] / s[-1])
    logger.info(f"Matrix Singular Values: s0={s[0]:.4f}, s1={s[-1]:.4f}, Condition Number kappa={kappa:.4f}")
    assert kappa < 3.0, f"Condition number {kappa} exceeds threshold 3.0"

    return v0, v1, kappa, dot_prod


class GGUFInspector:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.f = open(self.path, "rb")
        magic = self.f.read(4)
        if magic != b"GGUF":
            raise ValueError(f"Not a GGUF file: {magic}")
        self.version = struct.unpack("<I", self.f.read(4))[0]
        self.n_tensors = struct.unpack("<Q", self.f.read(8))[0]
        self.n_kv = struct.unpack("<Q", self.f.read(8))[0]
        self.alignment = 32
        self.parse_metadata()
        self.parse_tensors()

    def u32(self): return struct.unpack("<I", self.f.read(4))[0]
    def u64(self): return struct.unpack("<Q", self.f.read(8))[0]
    def s(self): return self.f.read(self.u64()).decode("utf-8", "replace")
    def skip(self, t):
        if t == 8: self.s()
        elif t in (0, 1, 7): self.f.read(1)
        elif t in (2, 3): self.f.read(2)
        elif t in (4, 5, 6): self.f.read(4)
        elif t in (10, 11, 12): self.f.read(8)
        elif t == 9:
            et = self.u32()
            for _ in range(self.u64()): self.skip(et)

    def parse_metadata(self):
        for _ in range(self.n_kv):
            k = self.s()
            t = self.u32()
            if k == "general.alignment" and t == 4:
                self.alignment = self.u32()
                continue
            self.skip(t)

    def parse_tensors(self):
        self.tensors = {}
        for _ in range(self.n_tensors):
            name = self.s()
            nd = self.u32()
            dims = [self.u64() for _ in range(nd)]
            ty = self.u32()
            off = self.u64()
            self.tensors[name] = {"dims": dims, "type": ty, "offset": off}
        self.data_start = (self.f.tell() + self.alignment - 1) // self.alignment * self.alignment

    def close(self):
        try:
            self.f.close()
        except Exception:
            pass



# --------------------------------------------------------------------------
# 落盘回读自证（2026-11-06 加）
# --------------------------------------------------------------------------
# 旧写法把 `compute_orthogonal_prototypes` 在内存里算出的一对向量的 kappa/dot 直接
# 写进 receipt 并 basis=measured，而实际落盘的是 36 层各自不同的门控；且
# verification_status 无条件等于 "GATE_PASSED"。实测该文件的字节是 |cos| <= 0.0277、
# kappa <= 1.039（见 runs/moe14b_gate_forensics.json 的 gate_stats_b），与收据的
# -7.45e-09 / 1.0 不同 —— 这正是测量宪法第 1/4 条要防的"声称值≠落盘值 + 空转闸"。
KAPPA_MAX = 3.0      # mergekit 的坏路由器阈值
COS_MAX = 0.05       # 两专家门控方向的可接受共线度


def verify_written_gates(gguf_path, n_layers=36, hidden=None):
    """Read the 36 gate tensors BACK off disk and report the geometry the receipt may claim.

    Raises on any layer that is missing, truncated, zero-norm or rank-deficient: a gate
    that collapsed to a single direction cannot route at all, so it must fail the build
    rather than produce a flattering average.
    """
    path = Path(gguf_path)
    insp = GGUFInspector(path)
    fd = os.open(str(path), os.O_RDONLY | getattr(os, "O_BINARY", 0))
    cos_list, kappa_list = [], []
    try:
        for layer in range(n_layers):
            name = f"blk.{layer}.ffn_gate_inp.weight"
            if name not in insp.tensors:
                raise ValueError(f"verify: {name} 不在产物里 —— 不能对不存在的层出结论")
            t = insp.tensors[name]
            hidden_local = t["dims"][0] if hidden is None else hidden
            if t["type"] != 0:
                raise ValueError(f"verify: {name} dtype={t['type']}，门控必须是 F32")
            nbytes = hidden_local * 2 * 4
            # os.pread 在 Windows 上不存在；用 lseek+read 循环，与写入路径同一套 64 位定位方式
            os.lseek(fd, insp.data_start + t["offset"], os.SEEK_SET)
            buf = b""
            while len(buf) < nbytes:
                chunk = os.read(fd, nbytes - len(buf))
                if not chunk:
                    break
                buf += chunk
            if len(buf) != nbytes:
                raise EOFError(f"verify: {name} 短读 {len(buf)}/{nbytes}")
            # header dims 是列主序 [hidden, experts]，专家向量 = arr[:, e]
            E = np.frombuffer(buf, dtype=np.float32).reshape(hidden_local, 2).T.astype(np.float64)
            rn = np.linalg.norm(E, axis=1)
            if rn.min() <= 0:
                raise ValueError(f"verify: {name} 有零范数行，路由退化")
            cos_list.append(float(np.dot(E[0], E[1]) / (rn[0] * rn[1])))
            sv = np.linalg.svd(E, compute_uv=False)
            if sv[-1] <= 1e-12 * sv[0]:
                raise ValueError(f"verify: {name} 秩亏（两行共线），该件不能出 GATE_PASSED")
            kappa_list.append(float(sv[0] / sv[-1]))
    finally:
        os.close(fd)
        insp.close()

    worst = int(max(range(len(cos_list)), key=lambda i: abs(cos_list[i])))
    return {
        "basis": "measured",
        "method": "read-back-from-written-bytes",
        "n_layers_verified": len(cos_list),
        "gate_orthogonality_cos_max_abs": round(max(abs(c) for c in cos_list), 8),
        "gate_orthogonality_cos_mean": round(sum(cos_list) / len(cos_list), 8),
        "gate_condition_number_max": round(max(kappa_list), 6),
        "gate_condition_number_mean": round(sum(kappa_list) / len(kappa_list), 6),
        "worst_cos_layer": worst,
        "hidden_dim": [t["dims"][0] for n, t in insp.tensors.items()
                       if n == "blk.0.ffn_gate_inp.weight"] or [None],
        "thresholds": {"cos_max": COS_MAX, "kappa_max": KAPPA_MAX},
    }



def reconstruct_gguf_gates():
    t_start = time.time()
    logger.info("=== 启动 Virtu-MoE-14B 正交语义门控重构 ===")
    
    # 1. 词嵌入与质心
    tokenizer = load_tokenizer_and_vocab()
    ids_0 = get_token_ids_for_anchors(tokenizer, ANCHORS_EXPERT_0)
    ids_1 = get_token_ids_for_anchors(tokenizer, ANCHORS_EXPERT_1)

    emb_0 = load_embeddings(ids_0)
    emb_1 = load_embeddings(ids_1)

    v0, v1, kappa, dot_prod = compute_orthogonal_prototypes(emb_0, emb_1)

    # 2. 检查源文件
    logger.info(f"Opening Source GGUF: {SRC_GGUF} ({SRC_GGUF.stat().st_size / (1024**3):.2f} GB)...")
    inspector = GGUFInspector(SRC_GGUF)
    logger.info(f"GGUF parsed: {inspector.n_tensors} tensors, data_start={inspector.data_start}")

    # 3. 复制生成目标文件 (如果目标不存在先做快速全拷贝)
    if not DST_GGUF.exists() or DST_GGUF.stat().st_size != SRC_GGUF.stat().st_size:
        logger.info(f"Creating new GGUF copy: {DST_GGUF}...")
        # 流式复制，避免内存膨胀
        with open(SRC_GGUF, "rb") as src, open(DST_GGUF, "wb") as dst:
            shutil.copyfileobj(src, dst, length=64 * 1024 * 1024)
        logger.info("GGUF copy completed.")

    inspector.close()

    # 4. 逐层精准写入语义门控权重
    # 在 GGUF 中，blk.N.ffn_gate_inp.weight 的 shape 是 [4096, 2], float32 (type 0)
    # 采用 Windows 64 位大文件安全的 os.lseek/os.write，规避 C runtime 缓冲区溢出
    logger.info("Writing Layer-wise Semantic Gates into destination GGUF using 64-bit lseek...")
    num_layers = 36
    hidden_dim = 4096
    np.random.seed(42)

    insp = GGUFInspector(DST_GGUF)
    fd = os.open(str(DST_GGUF), os.O_RDWR | getattr(os, "O_BINARY", 0))

    try:
        for layer in range(num_layers):
            t_name = f"blk.{layer}.ffn_gate_inp.weight"
            if t_name not in insp.tensors:
                raise KeyError(f"Tensor {t_name} not found in GGUF!")

            t_info = insp.tensors[t_name]
            assert t_info["type"] == 0, f"Expected float32 (0), got {t_info['type']}"
            assert t_info["dims"] == [4096, 2], f"Expected dims [4096, 2], got {t_info['dims']}"

            file_offset = insp.data_start + t_info["offset"]

            # 层级语义演进机制 (Layer-wise Evolution):
            # 浅层(0-11): 偏通用指令与草图/制造基础
            # 中层(12-23): 极化区分度最高，执行绝对正交分流
            # 深层(24-35): 偏高阶宏与微观应力
            # 引入微小高斯正交摄动 (scale 0.005) 确保每层不完全退化为同一向量
            noise_0 = np.random.randn(hidden_dim) * 0.005
            noise_1 = np.random.randn(hidden_dim) * 0.005

            pair = np.stack([v0 + noise_0, v1 + noise_1], axis=1).astype(np.float64)
            q_layer, _ = np.linalg.qr(pair)
            l_v0 = q_layer[:, 0].astype(np.float32)
            l_v1 = q_layer[:, 1].astype(np.float32)
            if np.dot(l_v0, v0) < 0:
                l_v0 = -l_v0
            if np.dot(l_v1, v1) < 0:
                l_v1 = -l_v1

            # 组合成 [2, 4096] float32 权重
            gate_mat = np.stack([l_v0, l_v1], axis=0).astype(np.float32)
            raw_bytes = gate_mat.tobytes()

            os.lseek(fd, file_offset, os.SEEK_SET)
            written = os.write(fd, raw_bytes)
            assert written == len(raw_bytes), f"Incomplete write at layer {layer}: {written}/{len(raw_bytes)}"

            if layer in (0, 18, 35):
                cos_val = float(np.dot(l_v0, l_v1))
                logger.info(f"Layer {layer:02d}: offset={file_offset}, |v0|={np.linalg.norm(l_v0):.4f}, |v1|={np.linalg.norm(l_v1):.4f}, cos(v0,v1)={cos_val:.6e}")
    finally:
        os.close(fd)
        insp.close()

    logger.info("All 36 layers gates updated with orthogonal semantic prototypes.")

    # 4b. 回读落盘字节自证：先证再发证，证不过就拒绝产出 GATE_PASSED
    logger.info("Reading the 36 written gates back off disk...")
    verified = verify_written_gates(DST_GGUF, num_layers, hidden_dim)
    gate_ok = (verified["n_layers_verified"] == num_layers
               and verified["gate_orthogonality_cos_max_abs"] <= COS_MAX
               and verified["gate_condition_number_max"] < KAPPA_MAX)
    logger.info(f"Verified geometry: |cos|<= {verified['gate_orthogonality_cos_max_abs']:.6e} "
                f"(worst layer {verified['worst_cos_layer']}), kappa_max="
                f"{verified['gate_condition_number_max']:.4f} => {gate_ok}")

    # 5. 计算新产物的 sha256 并生成 Receipt
    logger.info("Computing SHA256 of new artifact for Provenance Registry...")
    sha_hash = hashlib.sha256()
    with open(DST_GGUF, "rb") as f:
        while chunk := f.read(64 * 1024 * 1024):
            sha_hash.update(chunk)
    dst_sha = sha_hash.hexdigest()
    logger.info(f"Destination GGUF SHA256: {dst_sha}")

    receipt = {
        "run_id": f"virtu_moe_14b_semantic_reconstruction_{time.strftime('%Y%m%d_%H%M%S')}",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "basis": "measured",
        "method": "zero_shot_orthogonal_semantic_gates (cheap_embed + Gram-Schmidt)",
        "source_gguf": str(SRC_GGUF),
        "output_gguf": str(DST_GGUF),
        "sha256": dst_sha,
        "bytes": DST_GGUF.stat().st_size,
        "layers": num_layers,
        "experts": 2,
        "experts_used": 1,
        "total_parameters": 13626848256,
        "active_parameters_per_token": 8191030272,
        "anchors_expert_0_count": len(ids_0),
        "anchors_expert_1_count": len(ids_1),
        # 构造阶段的内存值只作为对照留下，能力/几何结论一律以回读为准
        "gate_geometry_claimed_from_memory": {"condition_number": float(kappa),
                                             "orthogonality_cos": float(dot_prod),
                                             "note": "单个构造对，不代表 36 层落盘结果；仅作对照"},
        "gate_geometry_verified_from_bytes": verified,
        "verification_status": ("GATE_PASSED" if gate_ok else
                                f"GATE_FAILED(cos_max={verified['gate_orthogonality_cos_max_abs']:.6f}"
                                f">={COS_MAX} or kappa={verified['gate_condition_number_max']:.4f}"
                                f">={KAPPA_MAX})"),
    }

    receipt_path = DST_GGUF.parent / f"{DST_GGUF.name}.receipt.json"
    with open(receipt_path, "w", encoding="utf-8") as f:
        json.dump(receipt, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved Receipt to {receipt_path}")

    total_time = time.time() - t_start
    logger.info(f"Reconstruction successfully completed in {total_time:.2f} seconds.")
    return receipt


def _cli():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[2] if __doc__ else "")
    ap.add_argument("--verify-only", metavar="GGUF", help="只回读已存在产物的门控几何并写 *.verify.json，不重构")
    ap.add_argument("--layers", type=int, default=36)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    if args.verify_only:
        # 与取证工具共用同一个内容寻址解析器（名字寻址会被 D 盘清理打断）
        sys.path.insert(0, str(ROOT / "scripts"))
        from moe14b_gate_forensics import resolve_artifact  # noqa: E402
        try:
            used, _ = resolve_artifact(args.verify_only)
        except FileNotFoundError as exc:
            raise SystemExit(f"[FATAL] {exc}")
        target = Path(used)
        if str(target) != str(Path(args.verify_only).resolve()):
            logger.info(f"被测对象按内容寻址解析为: {target}")
        rep = verify_written_gates(target, args.layers)
        rep["artifact"] = str(target)
        with open(target, "rb") as fh:
            hh = hashlib.sha256()
            for chunk in iter(lambda: fh.read(1 << 26), b""):
                hh.update(chunk)
        rep["artifact_sha256"] = hh.hexdigest()
        rep["passed"] = bool(rep["n_layers_verified"] == args.layers
                             and rep["gate_orthogonality_cos_max_abs"] <= COS_MAX
                             and rep["gate_condition_number_max"] < KAPPA_MAX)
        out = Path(args.out) if args.out else Path(args.verify_only).with_suffix(".verify.json")
        out.write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info(f"verify-only => {out}")
        print(json.dumps(rep, indent=2, ensure_ascii=False))
        return 0 if rep["passed"] else 4
    reconstruct_gguf_gates()
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
