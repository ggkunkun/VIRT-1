"""Standardized Smelted Parameter Bundle Loader and Production Inference Engine.

Provides official model loading and inference interfaces for the standardized
smelted parameter collection. Enforces strict schema verification, SHA-256
checksum validation, strict state_dict loading (zero missing/unexpected keys),
and turnkey high-performance inference across industrial multimodal tasks.
"""

from __future__ import annotations
import os
import sys
import json
import time
import hashlib
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import torch
import torch.nn as nn
import torch.nn.functional as F

from virtu_omni.errors import ModelError, FEAT_TOKENIZER_ARG
from virtu_omni.security.weights import safe_torch_load as _safe_torch_load

# Ensure VIRTU source root in path for Virtu neural architecture definition
CANDIDATE_PATHS = [
    Path(r"D:\ent_build\Virtu"),
    Path(r"D:\_arena_gate_wt\Virtu"),
    Path(r"D:\_loopcore_wt\Virtu"),
    Path(r"D:\_widen_wt\Virtu"),
    Path(r"D:\智能制造Agent\Virtu"),
]
for p in CANDIDATE_PATHS:
    if p.exists() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

try:
    from virtu import config as C
except ImportError:
    C = None

try:
    from virtu.model import WPT2 as Virtu
except ImportError:
    try:
        from virtu.model import Virtu
    except ImportError:
        Virtu = None

SUBSYSTEM_NAMES = [
    "代码开发与重构 (coding_dev)",
    "数控制造与切削动力学 (cnc_mfg)",
    "终端命令与系统运维 (shell_sys)",
    "网络检索与数据抓取 (web_research)",
    "版本控制与仓库管理 (git_vcs)",
    "文件读写与工作区索引 (file_fs)",
    "故障诊断与异常修复 (debug_troubleshoot)",
    "测试验证与质量评估 (test_qa)",
    "安全合规与权限防线 (sec_compliance)",
    "多模态视觉与几何感知 (multimodal_geom)",
    "知识蒸馏与参数微调 (distill_tuning)",
    "服务推理与并发调度 (serving_sched)",
]
SUBSYSTEM_KEYS = [
    "coding_dev", "cnc_mfg", "shell_sys", "web_research",
    "git_vcs", "file_fs", "debug_troubleshoot", "test_qa",
    "sec_compliance", "multimodal_geom", "distill_tuning", "serving_sched"
]
PAD_ID, BOS_ID, EOS_ID, UNK_ID = 0, 1, 2, 3

# Supported operations and materials
OPERATIONS = ["face", "pocket", "drill", "slot", "contour", "thread", "chamfer", "boss"]
MATERIALS = ["al6061", "steel4140", "ti6al4v", "cuc360", "inconel718", "ss304", "pa66", "castiron"]

# 字节码产物：其摘要随解释器版本与实际编译结果漂移，不构成归档内容的完整性证据。
_COMPILED_CACHE_SUFFIXES = (".pyc", ".pyo")


def _sha256_file(path: Path, chunk_size: int = 4 * 1024 * 1024) -> str:
    """流式计算文件 SHA-256（分块读取，不把大权重整体载入内存）。"""
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_compiled_cache(path: Path) -> bool:
    """判断路径是否属于 Python 字节码缓存（.pyc/.pyo 或 __pycache__ 下）。"""
    return path.suffix.lower() in _COMPILED_CACHE_SUFFIXES or "__pycache__" in path.parts


class StandardizedSmeltTokenizer:
    """Tokenizer interface matching the 4096-token manufacturing domain vocabulary."""

    def __init__(self, vocab_path: str | Path):
        self.vocab_path = Path(vocab_path)
        with open(self.vocab_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.vocab: List[str] = data.get("text", [])
        self.stoi: Dict[str, int] = {t: i for i, t in enumerate(self.vocab)}
        self.itos: Dict[int, str] = {i: t for i, t in enumerate(self.vocab)}
        self.vocab_size = len(self.vocab)

    def encode(self, text: str, max_length: int = 60, add_special_tokens: bool = True) -> Tuple[torch.Tensor, torch.Tensor]:
        """Encode text to padded token tensor and boolean attention mask."""
        if not isinstance(text, str):
            raise ModelError(
                FEAT_TOKENIZER_ARG,
                f"Expected str input, got {type(text).__name__}",
                hint="Coerce the prompt to text before tokenising.",
                context={"type": type(text).__name__},
            )
        if max_length < 1:
            raise ModelError(
                FEAT_TOKENIZER_ARG,
                f"max_length must be >= 1, got {max_length}",
                hint="Use a positive sequence budget.",
                context={"max_length": max_length},
            )

        tokens = []
        if add_special_tokens:
            tokens.append(BOS_ID)

        # Tokenize by char/subword. Reserve room for the EOS id so that a
        # truncated sequence still ends with an explicit boundary token instead
        # of silently dropping it (the model then never learns to stop).
        body_budget = max_length - (2 if add_special_tokens else 0)
        if body_budget < 0:
            body_budget = 0
        body = [self.stoi.get(ch, UNK_ID) for ch in text][:body_budget]
        tokens.extend(body)
        if add_special_tokens:
            tokens.append(EOS_ID)

        # Truncate or pad to max_length
        tokens = tokens[:max_length]
        pad_len = max_length - len(tokens)
        mask = [1] * len(tokens) + [0] * pad_len
        tokens = tokens + [PAD_ID] * pad_len

        token_tensor = torch.tensor([tokens], dtype=torch.long)
        mask_tensor = torch.tensor([mask], dtype=torch.long)
        return token_tensor, mask_tensor

    def decode(self, token_ids: Union[List[int], torch.Tensor]) -> str:
        """Decode token sequence back to text string."""
        if isinstance(token_ids, torch.Tensor):
            # Flattening (rather than squeeze) keeps single-token batches list-like:
            # squeeze() collapsed [1, 1] to a 0-d scalar and raised TypeError on iter.
            token_ids = token_ids.reshape(-1).tolist()
        words = []
        for tid in token_ids:
            if tid in (PAD_ID, BOS_ID, EOS_ID):
                continue
            words.append(self.itos.get(int(tid), "<unk>"))
        return "".join(words)


class StandardizedSmeltBundle:
    """Official loader for the standardized smelted parameter bundle.

    Provides end-to-end checksum verification, structural inspection,
    strict PyTorch model loading, and turnkey manufacturing inference.
    """

    def __init__(self, bundle_dir: str | Path):
        self.bundle_dir = Path(bundle_dir)
        if not self.bundle_dir.exists():
            raise FileNotFoundError(f"Standardized smelt bundle directory does not exist: {self.bundle_dir}")

        self.weights_path = self.bundle_dir / "weights" / "standardized_weights.pt"
        self.config_path = self.bundle_dir / "config" / "model_config.json"
        self.params_path = self.bundle_dir / "config" / "params.json"
        self.vocab_path = self.bundle_dir / "vocab" / "vocab.json"
        self.package_manifest_path = self.bundle_dir / "package_manifest.json"
        self.verification_report_path = self.bundle_dir / "verification_report.json"

        # Lazy loaded components
        self._manifest: Optional[Dict[str, Any]] = None
        self._verification_report: Optional[Dict[str, Any]] = None
        self._model: Optional[Virtu] = None
        self._tokenizer: Optional[StandardizedSmeltTokenizer] = None
        self._model_config: Optional[Dict[str, Any]] = None
        self.device = torch.device("cpu")

    def load_manifest(self) -> Dict[str, Any]:
        """Load and return package manifest."""
        if self._manifest is None:
            if not self.package_manifest_path.exists():
                raise FileNotFoundError(f"Missing package manifest: {self.package_manifest_path}")
            with open(self.package_manifest_path, "r", encoding="utf-8") as f:
                self._manifest = json.load(f)
        return self._manifest

    def load_verification_report(self) -> Dict[str, Any]:
        """Load and return triple verification report."""
        if self._verification_report is None:
            if not self.verification_report_path.exists():
                raise FileNotFoundError(f"Missing verification report: {self.verification_report_path}")
            with open(self.verification_report_path, "r", encoding="utf-8") as f:
                self._verification_report = json.load(f)
        return self._verification_report

    def verify_bundle_integrity(
        self,
        check_sha256: bool = True,
        skip_compiled_cache: bool = True,
    ) -> Tuple[bool, List[str]]:
        """Verify file sizes, SHA-256 digests and structural integrity of the bundle on disk.

        兼容升级策略（不把旧 manifest 一刀切判红）:
          * 记录带 ``sha256``      -> 计算实际摘要逐字节比对，不一致记入 ``errors`` 判失败；
          * 记录缺 ``sha256``      -> 发出 ``RuntimeWarning`` 告警但仍放行（内容无法校验）；
          * ``.pyc`` / ``__pycache__`` -> 字节码产物，摘要随解释器版本漂移，默认跳过并告警，
            置 ``skip_compiled_cache=False`` 可强制纳入校验。

        Args:
            check_sha256: 是否执行摘要比对（False 时退化为旧行为，仅比对尺寸）。
            skip_compiled_cache: 是否跳过 Python 字节码缓存条目。

        Returns:
            ``(ok, errors)``：``ok`` 为 True 表示未发现完整性缺陷；
            ``errors`` 逐条给出缺失 / 尺寸不符 / 摘要不符的具体原因。
        """
        manifest = self.load_manifest()
        errors: List[str] = []
        notes: List[str] = []

        for record in manifest.get("files", []):
            target_path = Path(record["target_path"])

            if skip_compiled_cache and _is_compiled_cache(target_path):
                notes.append(f"跳过字节码缓存条目（摘要随解释器版本漂移）：{record['filename']}")
                continue

            if not target_path.exists():
                errors.append(f"Missing bundle file: {target_path}")
                continue

            expected_size = record.get("size_bytes")
            actual_size = target_path.stat().st_size
            if expected_size is not None and actual_size != expected_size:
                errors.append(
                    f"Size mismatch on {record['filename']}: expected {expected_size}, got {actual_size}"
                )

            if not check_sha256:
                continue

            declared = str(record.get("sha256") or "").strip().lower()
            if not declared:
                notes.append(f"manifest 未记录 sha256，内容无法校验：{record['filename']}")
                continue

            actual = _sha256_file(target_path)
            if actual != declared:
                errors.append(
                    f"SHA-256 mismatch on {record['filename']}: "
                    f"expected {declared[:16]}..., got {actual[:16]}..."
                )

        if notes:
            warnings.warn(
                "verify_bundle_integrity：%d 条条目未做内容校验或按设计跳过 —— %s"
                % (len(notes), "；".join(notes[:5])),
                RuntimeWarning,
                stacklevel=2,
            )

        return (len(errors) == 0, errors)

    def load_model(self, device: str | torch.device = "cpu", strict: bool = True) -> Virtu:
        """Initialize official Virtu architecture and strictly load standardized parameters."""
        self.device = torch.device(device)
        t0 = time.time()

        if not self.weights_path.exists():
            raise FileNotFoundError(f"Weights file not found: {self.weights_path}")

        # Load standardized weights package
        package = _safe_torch_load(self.weights_path, map_location="cpu")
        raw_sd = package.get("model_state_dict", package)
        model_cfg = package.get("model_config", {})

        if not model_cfg:
            # Fallback to params.json or constants defaults
            if self.params_path.exists():
                with open(self.params_path, "r", encoding="utf-8") as f:
                    p = json.load(f)
            model_cfg = {
                "d_model": 1152,
                "n_heads": 24,
                "d_ff": 4608,
                "dropout": 0.1,
                "recurrent_dropout": 0.15,
                "text_vocab": 4096,
                "max_text": 60,
                "text_layers": 10,
                "dec_layers": 10,
                "n_queries": 32,
                "fusion_layers": 6,
                "rnn_type": "gru",
                "rnn_hidden": 768,
                "recursions": 5,
                "embed_dim": 512,
                "verifier_hidden": 512,
                "mfg_tasks": True,
                "n_subsystems": 12,
                "n_ops": 8,
                "n_materials": 8,
            }

        self._model_config = model_cfg

        # Instantiate official Virtu neural model
        model = Virtu(model_cfg)

        # Execute strict parameter loading
        load_res = model.load_state_dict(raw_sd, strict=strict)
        if len(load_res.missing_keys) > 0 or len(load_res.unexpected_keys) > 0:
            raise RuntimeError(
                f"Strict loading failed: {len(load_res.missing_keys)} missing, "
                f"{len(load_res.unexpected_keys)} unexpected keys"
            )

        model.eval().to(self.device)
        self._model = model

        load_duration = time.time() - t0
        print(f"[StandardizedSmeltBundle] Model successfully loaded ({sum(p.numel() for p in model.parameters()):,} params) in {load_duration:.3f}s on {self.device}")
        return self._model

    def get_tokenizer(self) -> StandardizedSmeltTokenizer:
        """Retrieve tokenizer instance."""
        if self._tokenizer is None:
            if not self.vocab_path.exists():
                raise FileNotFoundError(f"Vocabulary file not found: {self.vocab_path}")
            self._tokenizer = StandardizedSmeltTokenizer(self.vocab_path)
        return self._tokenizer

    # -------------------------------------------------------------------------
    # Turnkey Production Inference APIs
    # -------------------------------------------------------------------------

    @torch.no_grad()
    def predict_subsystem(self, text: str) -> Dict[str, Any]:
        """Predict manufacturing subsystem classification for input condition."""
        if self._model is None:
            self.load_model(device=self.device)
        tokenizer = self.get_tokenizer()

        token_ids, mask = tokenizer.encode(text)
        token_ids = token_ids.to(self.device)
        mask = mask.to(self.device)

        t0 = time.time()
        info = self._model.context({"text": token_ids, "text_mask": mask})
        mfg_out = self._model.mfg_heads(info)
        sub_logits = mfg_out["subsystem"].squeeze(0)  # [12]
        probs = F.softmax(sub_logits.float(), dim=-1).cpu().tolist()
        pred_idx = int(torch.argmax(sub_logits).item())
        latency_ms = (time.time() - t0) * 1000.0

        # Build candidate distribution
        distribution = [
            {
                "index": i,
                "key": SUBSYSTEM_KEYS[i] if i < len(SUBSYSTEM_KEYS) else f"sub_{i}",
                "name": SUBSYSTEM_NAMES[i] if i < len(SUBSYSTEM_NAMES) else f"Subsystem_{i}",
                "probability": round(probs[i], 5),
            }
            for i in range(len(probs))
        ]
        distribution.sort(key=lambda x: x["probability"], reverse=True)

        return {
            "input_text": text,
            "predicted_index": pred_idx,
            "predicted_key": SUBSYSTEM_KEYS[pred_idx],
            "predicted_name": SUBSYSTEM_NAMES[pred_idx],
            "confidence": round(probs[pred_idx], 5),
            "top_candidates": distribution[:3],
            "latency_ms": round(latency_ms, 2),
        }

    @torch.no_grad()
    def predict_machining_task(self, text: str) -> Dict[str, Any]:
        """Jointly predict subsystem, machining operation, and workpiece material."""
        if self._model is None:
            self.load_model(device=self.device)
        tokenizer = self.get_tokenizer()

        token_ids, mask = tokenizer.encode(text)
        token_ids = token_ids.to(self.device)
        mask = mask.to(self.device)

        t0 = time.time()
        info = self._model.context({"text": token_ids, "text_mask": mask})
        mfg_out = self._model.mfg_heads(info)

        sub_idx = int(mfg_out["subsystem"].squeeze(0).argmax().item())
        op_idx = int(mfg_out["op"].squeeze(0).argmax().item())
        mat_idx = int(mfg_out["material"].squeeze(0).argmax().item())
        latency_ms = (time.time() - t0) * 1000.0

        return {
            "input_text": text,
            "subsystem": {
                "index": sub_idx,
                "name": SUBSYSTEM_NAMES[sub_idx],
                "key": SUBSYSTEM_KEYS[sub_idx],
            },
            "operation": {
                "index": op_idx,
                "name": OPERATIONS[op_idx] if op_idx < len(OPERATIONS) else f"op_{op_idx}",
            },
            "material": {
                "index": mat_idx,
                "name": MATERIALS[mat_idx] if mat_idx < len(MATERIALS) else f"mat_{mat_idx}",
            },
            "latency_ms": round(latency_ms, 2),
        }

    @torch.no_grad()
    def verify_action_pair(self, context_text: str, action_text: str) -> Dict[str, Any]:
        """Verify manufacturing context-action compatibility via JEV InfoNCE/JEPA verifier."""
        if self._model is None:
            self.load_model(device=self.device)
        tokenizer = self.get_tokenizer()

        cx_ids, cx_mask = tokenizer.encode("工况 " + context_text)
        ac_ids, ac_mask = tokenizer.encode(action_text)

        cx_ids, cx_mask = cx_ids.to(self.device), cx_mask.to(self.device)
        ac_ids, ac_mask = ac_ids.to(self.device), ac_mask.to(self.device)

        t0 = time.time()
        info = self._model.context({"text": cx_ids, "text_mask": cx_mask})
        res = self._model.mfg_pair_logits({"text_b": ac_ids, "text_b_mask": ac_mask}, info)
        logits = res[2] if isinstance(res, tuple) and len(res) == 3 else res
        score = float(torch.sigmoid(logits.view(-1)).item())
        latency_ms = (time.time() - t0) * 1000.0

        return {
            "context": context_text,
            "action": action_text,
            "verification_score": round(score, 5),
            "verdict": "COMPLIANT" if score >= 0.50 else "NON_COMPLIANT",
            "latency_ms": round(latency_ms, 2),
        }

    @torch.no_grad()
    def extract_joint_embedding(self, text: str) -> List[float]:
        """Extract 512-d normalized JEV joint representation embedding."""
        if self._model is None:
            self.load_model(device=self.device)
        tokenizer = self.get_tokenizer()

        token_ids, mask = tokenizer.encode(text)
        token_ids = token_ids.to(self.device)
        mask = mask.to(self.device)

        t, _, _, zt, _, _ = self._model.encode_all({"text": token_ids, "text_mask": mask})
        proj_emb = self._model.proj["txt"](zt)
        norm_emb = F.normalize(proj_emb, p=2, dim=-1).squeeze(0).cpu().tolist()
        return norm_emb


def load_standardized_bundle(
    bundle_path: str | Path = Path(r"D:\Virtu模型\checkpoints\standardized_smelt_bundle"),
    device: str = "cpu",
) -> Tuple[StandardizedSmeltBundle, Virtu]:
    """Official entrypoint to load the standardized smelt bundle."""
    bundle = StandardizedSmeltBundle(bundle_path)
    model = bundle.load_model(device=device, strict=True)
    return bundle, model
