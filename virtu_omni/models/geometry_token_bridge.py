# -*- coding: utf-8 -*-
"""geometry_token_bridge.py — 工业 CAD/CAM 几何实体与流形向量对齐桥接器.

建立从工程几何语义到 Virtu-Omni 连续流形空间的端到端映射：
1. 几何图元语义词汇表 (Geometric Entity Vocabulary):
   - 基础草图图元：<GEOM_POINT>, <GEOM_LINE>, <GEOM_ARC>, <GEOM_CIRCLE>, <GEOM_SPLINE>
   - 3D 特征操作：<FEAT_EXTRUDE_BOSS>, <FEAT_EXTRUDE_CUT>, <FEAT_REVOLVE_BOSS>, <FEAT_CIRCULAR_PATTERN>, <FEAT_FILLET>, <FEAT_CHAMFER>
   - 制造公差与基准：<TOL_DATUM>, <TOL_PERPENDICULAR>, <TOL_CONCENTRIC>, <TOL_RUNOUT>
   - 数控代码语法块：<NC_G00_RAPID>, <NC_G01_LINEAR>, <NC_G02_CW_ARC>, <NC_G03_CCW_ARC>, <NC_G71_ROUGH>, <NC_G70_FINISH>, <NC_MACRO_VAR>
2. 几何拓扑编码器 (GeometryFeatureProjector):
   - 接收几何特征向量 [B, N_features, 6] (x, y, z, dx, dy, dz / radius)
   - 经由两层 RMSNorm + SwiGLU 投影至 Virtu-Omni 主干隐层维度 (Hidden Dim = 4096)
   - 与文本 Token Embeddings 共同送入 Uni-RoPE 与混合注意力层进行跨模态协同推理
"""

from __future__ import annotations
import math
import warnings
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, List, Optional, Tuple, Any

from virtu_omni.config import ModelConfig
from virtu_omni.errors import ModelError, FEAT_GEOM_VALUE, FEAT_VOCAB_RANGE
from virtu_omni.models.architecture import VirtuRMSNorm, VirtuSwiGLU


# 工业几何特化 Token 起始偏移量 (位于预留区间 120,000 ~ 125,000)
GEOMETRY_TOKEN_OFFSET = 120000

GEOMETRY_SPECIAL_TOKENS = [
    "<GEOM_POINT>",
    "<GEOM_LINE>",
    "<GEOM_ARC>",
    "<GEOM_CIRCLE>",
    "<GEOM_SPLINE>",
    "<FEAT_EXTRUDE_BOSS>",
    "<FEAT_EXTRUDE_CUT>",
    "<FEAT_REVOLVE_BOSS>",
    "<FEAT_CIRCULAR_PATTERN>",
    "<FEAT_FILLET>",
    "<FEAT_CHAMFER>",
    "<TOL_DATUM>",
    "<TOL_PERPENDICULAR>",
    "<TOL_CONCENTRIC>",
    "<TOL_RUNOUT>",
    "<NC_G00_RAPID>",
    "<NC_G01_LINEAR>",
    "<NC_G02_CW_ARC>",
    "<NC_G03_CCW_ARC>",
    "<NC_G71_ROUGH>",
    "<NC_G70_FINISH>",
    "<NC_MACRO_VAR>",
]

# Entity type -> special token. Previously the encoder only synthesised
# "<GEOM_{TYPE}>", so every feature / tolerance / NC entity ("extrude_boss",
# "datum", "g00_rapid") silently degraded to <GEOM_LINE> and the model never
# saw the manufacturing semantics these tokens exist for.
TYPE_TO_TOKEN: Dict[str, str] = {
    "POINT": "<GEOM_POINT>",
    "LINE": "<GEOM_LINE>",
    "ARC": "<GEOM_ARC>",
    "CIRCLE": "<GEOM_CIRCLE>",
    "SPLINE": "<GEOM_SPLINE>",
    "EXTRUDE_BOSS": "<FEAT_EXTRUDE_BOSS>",
    "EXTRUDE_CUT": "<FEAT_EXTRUDE_CUT>",
    "REVOLVE_BOSS": "<FEAT_REVOLVE_BOSS>",
    "CIRCULAR_PATTERN": "<FEAT_CIRCULAR_PATTERN>",
    "FILLET": "<FEAT_FILLET>",
    "CHAMFER": "<FEAT_CHAMFER>",
    "DATUM": "<TOL_DATUM>",
    "PERPENDICULAR": "<TOL_PERPENDICULAR>",
    "CONCENTRIC": "<TOL_CONCENTRIC>",
    "RUNOUT": "<TOL_RUNOUT>",
    "G00_RAPID": "<NC_G00_RAPID>",
    "G01_LINEAR": "<NC_G01_LINEAR>",
    "G02_CW_ARC": "<NC_G02_CW_ARC>",
    "G03_CCW_ARC": "<NC_G03_CCW_ARC>",
    "G71_ROUGH": "<NC_G71_ROUGH>",
    "G70_FINISH": "<NC_G70_FINISH>",
    "MACRO_VAR": "<NC_MACRO_VAR>",
}


class GeometryFeatureProjector(nn.Module):
    """工业几何连续特征至 10B 主干隐层空间的无损投影器。"""

    def __init__(self, in_features: int = 8, hidden_dim: int = 4096) -> None:
        super().__init__()
        self.in_features = in_features
        self.hidden_dim = hidden_dim
        
        # 两层特征投影与非线性映射
        self.input_proj = nn.Linear(in_features, hidden_dim, bias=False)
        self.norm = VirtuRMSNorm(hidden_dim)
        cfg = ModelConfig(hidden_dim=hidden_dim, intermediate_dim=hidden_dim * 3)
        self.swiglu = VirtuSwiGLU(cfg)

    def forward(self, geom_tensor: torch.Tensor) -> torch.Tensor:
        """
        Args:
            geom_tensor: [Batch, Seq_len, in_features] 连续几何参数张量
        Returns:
            [Batch, Seq_len, hidden_dim] 对齐后的几何流形向量
        """
        if geom_tensor.dim() != 3 or geom_tensor.shape[-1] != self.in_features:
            raise ModelError(
                FEAT_GEOM_VALUE,
                f"geom_tensor must be [B, S, {self.in_features}], got {tuple(geom_tensor.shape)}",
                hint="Use GeometryTokenBridge.encode_geometry_sequence to build the feature tensor.",
                context={"shape": list(geom_tensor.shape), "in_features": self.in_features},
            )
        if not torch.isfinite(geom_tensor).all():
            raise ModelError(
                FEAT_GEOM_VALUE,
                "geom_tensor contains NaN/Inf values",
                hint="Sanitize CAD coordinates before projecting them into the manifold.",
            )
        x = self.input_proj(geom_tensor)
        x = self.norm(x)
        x = self.swiglu(x)
        return x


class GeometryTokenBridge:
    """几何实体分词与流形对齐调度器。"""

    def __init__(self, hidden_dim: int = 4096):
        self.token_to_id: Dict[str, int] = {
            t: GEOMETRY_TOKEN_OFFSET + i for i, t in enumerate(GEOMETRY_SPECIAL_TOKENS)
        }
        self.id_to_token: Dict[int, str] = {v: k for k, v in self.token_to_id.items()}
        self.projector = GeometryFeatureProjector(in_features=8, hidden_dim=hidden_dim)

    def encode_geometry_sequence(
        self,
        geom_elements: List[Dict[str, Any]],
        vocab_size: Optional[int] = None,
    ) -> Tuple[List[int], torch.Tensor]:
        """将几何要素列表编码为混合结构化 Token IDs 和连续参数张量。

        Args:
            geom_elements: 几何要素字典列表。
            vocab_size: 可选的主干词表大小；提供时校验几何特化 Token 不越界。
        """
        token_ids: List[int] = []
        raw_features: List[List[float]] = []

        for idx, elem in enumerate(geom_elements):
            elem_type = str(elem.get("type", "line")).upper()
            # Accept both bare types ("line") and already-prefixed forms
            # ("geom_line" / "feat_fillet" / "nc_g01_linear").
            for strip_prefix in ("GEOM_", "FEAT_", "TOL_", "NC_"):
                if elem_type.startswith(strip_prefix):
                    elem_type = elem_type[len(strip_prefix):]
                    break
            tok_name = TYPE_TO_TOKEN.get(elem_type)
            if tok_name is None:
                # Unknown entity types are still tolerated (drawings carry many
                # annotation entities), but no longer silently masquerade as lines.
                warnings.warn(
                    f"Unknown geometry entity type {elem.get('type')!r} at index {idx}; "
                    "falling back to <GEOM_LINE>.",
                    UserWarning,
                    stacklevel=2,
                )
                tok_name = "<GEOM_LINE>"
            token_ids.append(self.token_to_id[tok_name])

            # 抽取连续几何数值特征 [x1, y1, z1, x2, y2, z2, r, param]
            feat = []
            for field_name in ("x1", "y1", "z1", "x2", "y2", "z2", "r", "value"):
                raw_value = elem.get(field_name, 0.0)
                try:
                    value = float(raw_value)
                except (TypeError, ValueError) as exc:
                    raise ModelError(
                        FEAT_GEOM_VALUE,
                        f"Geometry field '{field_name}'={raw_value!r} at index {idx} is not numeric",
                        hint="Feed coordinates as int/float; convert unit strings upstream.",
                        context={"index": idx, "field": field_name, "value": str(raw_value)},
                    ) from exc
                if not math.isfinite(value):
                    raise ModelError(
                        FEAT_GEOM_VALUE,
                        f"Geometry field '{field_name}' at index {idx} is not finite ({value})",
                        hint="Remove NaN/Inf values before encoding the entity.",
                        context={"index": idx, "field": field_name, "value": value},
                    )
                feat.append(value)
            raw_features.append(feat)

        if vocab_size is not None and token_ids:
            max_id = max(token_ids)
            if max_id >= vocab_size:
                raise ModelError(
                    FEAT_VOCAB_RANGE,
                    f"Geometry token id {max_id} exceeds vocabulary size {vocab_size}",
                    hint="Reserve ids " f"{GEOMETRY_TOKEN_OFFSET}..{GEOMETRY_TOKEN_OFFSET + len(GEOMETRY_SPECIAL_TOKENS) - 1} "
                    "in the embedding table or shrink the entity set.",
                    context={"max_token_id": max_id, "vocab_size": vocab_size},
                )

        if not raw_features:
            # Must stay shape-consistent: the previous (1, 1, 8) placeholder
            # introduced a phantom feature token with no matching token id.
            tensor = torch.zeros(1, 0, 8, dtype=torch.float32)
        else:
            tensor = torch.tensor([raw_features], dtype=torch.float32)

        return token_ids, tensor

    def project_to_manifold(self, geom_tensor: torch.Tensor) -> torch.Tensor:
        """投影至 Virtu-Omni 统一流形空间。"""
        return self.projector(geom_tensor)
