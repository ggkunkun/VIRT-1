"""Configuration specifications for Virtu-Omni-10B Multimodal Model.

Provides strongly typed dataclasses and validation for model architecture,
distributed training, streaming data pipeline, health monitoring, and serving.
"""

from __future__ import annotations
import os
import dataclasses
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Optional, Type
import yaml

from virtu_omni.errors import ModelError, CFG_INVALID_FIELD, CFG_INVALID_YAML, CFG_UNKNOWN_FIELD


@dataclass
class ModelConfig:
    """Hyperparameters for Virtu-Omni-10B neural architecture."""
    model_name: str = "Virtu-Omni-10B"
    param_scale: str = "10B"
    num_layers: int = 48
    hidden_dim: int = 4096
    intermediate_dim: int = 12288  # 3 * hidden_dim for SwiGLU
    num_attention_heads: int = 32
    num_kv_heads: int = 8  # Grouped Query Attention 4:1
    head_dim: int = 128
    vocab_size: int = 128000
    vision_codebook_size: int = 16384
    image_resolution: int = 448
    patch_size: int = 14
    max_position_embeddings: int = 8192
    rms_norm_eps: float = 1e-6
    rope_theta: float = 100000.0
    initializer_range: float = 0.02
    use_qk_norm: bool = True
    dropout_prob: float = 0.0

    # Loop Transformer Recurrent Iterative Configuration
    max_loop_steps: int = 1
    convergence_threshold: float = 1e-4
    enable_state_cache: bool = True
    loop_norm_type: str = "rms"
    loop_gating: bool = True
    adaptive_loop: bool = True
    loop_exit_metric: str = "relative_l2"

    # Hybrid DeepSeek-MoE Backbone Configuration
    use_moe: bool = False
    moe_layer_freq: int = 2
    num_routed_experts: int = 8
    moe_top_k: int = 2
    moe_intermediate_dim: int = 0  # 0 defaults to intermediate_dim // 2
    moe_aux_loss_coef: float = 0.01
    use_loss_free_balancing: bool = True

    # 3D CAD Geometry Manifold Modality Configuration
    enable_geometry_modality: bool = False
    geometry_feature_dim: int = 8

    # Multi-Token Prediction (MTP) & PRM Physics Value Head Configuration
    mtp_depth: int = 0
    mtp_loss_weight: float = 0.3
    enable_value_head: bool = False

    # Long-Context YaRN/NTK RoPE & Attention Logit Softcapping Configuration
    rope_scaling_factor: float = 1.0
    attn_logit_softcapping: float = 0.0

    def __post_init__(self) -> None:
        """Fail fast on structurally impossible hyperparameters.

        Previously an illegal config (e.g. 0 layers, odd head_dim, mismatched
        GQA ratio) only surfaced as a confusing reshape error deep inside the
        forward pass. Validate at construction time instead.
        """
        checks = [
            (self.num_layers >= 1, "num_layers", self.num_layers, "must be >= 1"),
            (self.hidden_dim >= 1, "hidden_dim", self.hidden_dim, "must be >= 1"),
            (self.intermediate_dim >= 1, "intermediate_dim", self.intermediate_dim, "must be >= 1"),
            (self.num_attention_heads >= 1, "num_attention_heads", self.num_attention_heads, "must be >= 1"),
            (self.num_kv_heads >= 1, "num_kv_heads", self.num_kv_heads, "must be >= 1"),
            (self.head_dim >= 2 and self.head_dim % 2 == 0, "head_dim", self.head_dim,
             "must be >= 2 and even (Uni-RoPE rotates dimension pairs)"),
            (self.vocab_size >= 2, "vocab_size", self.vocab_size, "must be >= 2"),
            (self.vision_codebook_size >= 1, "vision_codebook_size", self.vision_codebook_size, "must be >= 1"),
            (self.patch_size >= 1, "patch_size", self.patch_size, "must be >= 1"),
            (self.image_resolution >= self.patch_size, "image_resolution", self.image_resolution,
             "must be >= patch_size"),
            (self.max_position_embeddings >= 1, "max_position_embeddings", self.max_position_embeddings, "must be >= 1"),
            (self.max_loop_steps >= 1, "max_loop_steps", self.max_loop_steps, "must be >= 1"),
            (self.convergence_threshold > 0, "convergence_threshold", self.convergence_threshold, "must be > 0"),
            (self.moe_layer_freq >= 1, "moe_layer_freq", self.moe_layer_freq, "must be >= 1"),
            (self.num_routed_experts >= 1, "num_routed_experts", self.num_routed_experts, "must be >= 1"),
            (1 <= self.moe_top_k <= self.num_routed_experts, "moe_top_k", self.moe_top_k,
             f"must be in [1, num_routed_experts={self.num_routed_experts}]"),
            (self.geometry_feature_dim >= 1, "geometry_feature_dim", self.geometry_feature_dim, "must be >= 1"),
            (self.mtp_depth >= 0, "mtp_depth", self.mtp_depth, "must be >= 0"),
            (self.rope_scaling_factor > 0.0, "rope_scaling_factor", self.rope_scaling_factor, "must be > 0"),
            (self.attn_logit_softcapping >= 0.0, "attn_logit_softcapping", self.attn_logit_softcapping, "must be >= 0"),
        ]
        for ok, name, value, rule in checks:
            if not ok:
                raise ModelError(
                    CFG_INVALID_FIELD,
                    f"ModelConfig.{name}={value!r} is invalid: {rule}",
                    hint="Fix the YAML/constructor value before building the model.",
                    context={"field": name, "value": value, "rule": rule},
                )
        if self.num_attention_heads % self.num_kv_heads != 0:
            raise ModelError(
                CFG_INVALID_FIELD,
                f"num_attention_heads ({self.num_attention_heads}) must be divisible by "
                f"num_kv_heads ({self.num_kv_heads}) for Grouped-Query Attention",
                hint="Pick a KV head count that divides the query head count (e.g. 32:8).",
                context={"num_attention_heads": self.num_attention_heads, "num_kv_heads": self.num_kv_heads},
            )
        if self.loop_exit_metric not in ("relative_l2", "cosine"):
            raise ModelError(
                CFG_INVALID_FIELD,
                f"loop_exit_metric={self.loop_exit_metric!r} is not supported",
                hint="Use 'relative_l2' or 'cosine'.",
                context={"field": "loop_exit_metric", "value": self.loop_exit_metric},
            )

    @property
    def total_estimated_parameters(self) -> int:
        """Calculate exact theoretical parameter count (Dense or Hybrid MoE + MTP + Value Head)."""
        attn_params = (
            (self.hidden_dim * self.hidden_dim)
            + 2 * (self.hidden_dim * (self.num_kv_heads * self.head_dim))
            + (self.hidden_dim * self.hidden_dim)
        )
        # Check whether QK-Norm is present? Keep base dense formula backwards-exact when flags off
        dense_ffn_params = 3 * (self.hidden_dim * self.intermediate_dim)
        norm_params = 2 * self.hidden_dim

        if not self.use_moe:
            backbone_params = self.num_layers * (attn_params + dense_ffn_params + norm_params)
        else:
            moe_inter = (
                self.moe_intermediate_dim
                if self.moe_intermediate_dim > 0
                else max(1, self.intermediate_dim // 2)
            )
            moe_ffn_params = (
                (1 + self.num_routed_experts) * (3 * self.hidden_dim * moe_inter)
                + (self.hidden_dim * self.num_routed_experts)
            )
            backbone_params = 0
            for layer_idx in range(self.num_layers):
                ffn = moe_ffn_params if (layer_idx % self.moe_layer_freq == 0) else dense_ffn_params
                backbone_params += attn_params + ffn + norm_params

        # Embeddings & Heads:
        text_emb = self.vocab_size * self.hidden_dim
        vision_proj = (3 * self.patch_size * self.patch_size * self.hidden_dim) + (self.hidden_dim * self.hidden_dim)
        vision_head = self.hidden_dim * self.vision_codebook_size
        lm_head = self.hidden_dim * self.vocab_size
        final_norm = self.hidden_dim

        extra_params = 0
        if self.enable_geometry_modality:
            extra_params += (
                (self.geometry_feature_dim * self.hidden_dim)
                + self.hidden_dim
                + 3 * self.hidden_dim * (self.hidden_dim * 3)
            )
        if self.mtp_depth > 0:
            mtp_layer = attn_params + dense_ffn_params + norm_params
            mtp_per_depth = (2 * self.hidden_dim) + (2 * self.hidden_dim * self.hidden_dim) + mtp_layer
            extra_params += self.mtp_depth * mtp_per_depth
        if self.enable_value_head:
            inner_val = max(16, self.hidden_dim // 4)
            extra_params += self.hidden_dim + (self.hidden_dim * inner_val) + inner_val

        return backbone_params + text_emb + vision_proj + vision_head + lm_head + final_norm + extra_params


@dataclass
class ParallelismConfig:
    """3D Distributed Parallelism Configuration."""
    tensor_parallel_size: int = 4
    pipeline_parallel_size: int = 4
    data_parallel_size: int = 8  # TP * PP * DP = 128 cards
    sequence_parallel: bool = True
    zero_stage: int = 3  # ZeRO-3 parameter sharding
    micro_batch_size: int = 1
    global_batch_size: int = 512
    gradient_accumulation_steps: int = 16
    activation_checkpointing: bool = True
    mixed_precision: str = "bf16"  # bf16 or fp16
    offload_optimizer_to_cpu: bool = False


@dataclass
class TrainingConfig:
    """Training optimization and scheduling hyperparameters."""
    learning_rate: float = 2.0e-4
    min_learning_rate: float = 2.0e-5
    weight_decay: float = 0.1
    adam_beta1: float = 0.9
    adam_beta2: float = 0.95
    adam_eps: float = 1e-8
    warmup_steps: int = 2000
    max_steps: int = 100000
    clip_grad_norm: float = 1.0
    z_loss_weight: float = 1e-4
    eval_interval_steps: int = 500
    save_interval_steps: int = 1000
    output_dir: str = "checkpoints"
    resume_from_checkpoint: Optional[str] = None


@dataclass
class DataConfig:
    """High-throughput multimodal data pipeline configuration."""
    num_workers: int = 16
    prefetch_factor: int = 4
    max_daily_pairs: int = 10_000_000  # >= 10M pairs/day throughput
    image_resolution: int = 448
    patch_size: int = 14
    max_text_tokens: int = 2048
    buffer_size: int = 65536
    data_cache_dir: str = "cache/data"

    def __post_init__(self) -> None:
        """Guard the two knobs the preprocessing pipeline indexes with."""
        checks = [
            (self.num_workers >= 1, "num_workers", self.num_workers, "must be >= 1"),
            (self.max_text_tokens >= 2, "max_text_tokens", self.max_text_tokens,
             "must be >= 2 to fit BOS/EOS boundary tokens"),
            (self.image_resolution >= 1, "image_resolution", self.image_resolution, "must be >= 1"),
            (self.patch_size >= 1, "patch_size", self.patch_size, "must be >= 1"),
        ]
        for ok, name, value, rule in checks:
            if not ok:
                raise ModelError(
                    CFG_INVALID_FIELD,
                    f"DataConfig.{name}={value!r} is invalid: {rule}",
                    hint="Fix the data pipeline configuration before streaming.",
                    context={"field": name, "value": value, "rule": rule},
                )


@dataclass
class MonitorConfig:
    """Real-time health monitoring and multi-channel alerting rules."""
    enable_monitoring: bool = True
    loss_spike_sigma_threshold: float = 3.0
    grad_norm_hard_threshold: float = 5.0
    gpu_temp_max_celsius: float = 85.0
    gpu_memory_threshold_percent: float = 98.5
    alert_wechat_webhook: str = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=mock-key"
    alert_feishu_webhook: str = "https://open.feishu.cn/open-apis/bot/v2/hook/mock-key"
    smtp_server: str = "smtp.enterprise.com"
    smtp_port: int = 587
    alert_email_receiver: str = "ops-ai-team@enterprise.com"
    auto_pause_on_anomaly: bool = True
    emergency_checkpoint_dir: str = "checkpoints/emergency"


@dataclass
class ServingConfig:
    """RESTful inference serving configuration."""
    host: str = "127.0.0.1"
    port: int = 8080
    workers: int = 4
    max_concurrency: int = 16
    max_inference_concurrency: int = 4
    max_request_bytes: int = 36 * 1024 * 1024
    target_latency_ms: float = 200.0  # Single A100 latency <= 200ms
    enable_paged_attention: bool = True
    enable_smoothquant_int8: bool = False
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        checks = [
            (bool(self.host.strip()), "host", self.host, "must not be empty"),
            (1 <= self.port <= 65535, "port", self.port, "must be between 1 and 65535"),
            (1 <= self.max_concurrency <= 1024, "max_concurrency", self.max_concurrency,
             "must be between 1 and 1024"),
            (1 <= self.max_inference_concurrency <= 128, "max_inference_concurrency",
             self.max_inference_concurrency, "must be between 1 and 128"),
            (1024 <= self.max_request_bytes <= 128 * 1024 * 1024, "max_request_bytes",
             self.max_request_bytes, "must be between 1 KiB and 128 MiB"),
        ]
        for ok, name, value, rule in checks:
            if not ok:
                raise ModelError(
                    CFG_INVALID_FIELD,
                    f"ServingConfig.{name}={value!r} is invalid: {rule}",
                    hint="Fix the serving limits before starting the HTTP service.",
                    context={"field": name, "value": value, "rule": rule},
                )


@dataclass
class VirtuOmniConfig:
    """Consolidated master configuration for Virtu-Omni-10B."""
    model: ModelConfig = field(default_factory=ModelConfig)
    parallelism: ParallelismConfig = field(default_factory=ParallelismConfig)
    training: TrainingConfig = field(default_factory=TrainingConfig)
    data: DataConfig = field(default_factory=DataConfig)
    monitor: MonitorConfig = field(default_factory=MonitorConfig)
    serving: ServingConfig = field(default_factory=ServingConfig)

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return asdict(self)

    def save_yaml(self, path: str) -> None:
        """Export configuration to YAML file."""
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False, sort_keys=False)

    @classmethod
    def from_yaml(cls, path: str) -> VirtuOmniConfig:
        """Load configuration from YAML file.

        Unknown keys and non-mapping sections are reported as structured
        ``ModelError`` instances (E1002/E1003) instead of leaking a raw
        ``TypeError`` from the dataclass constructor, which previously made an
        operator typo look like an architecture crash.
        """
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        if not isinstance(data, dict):
            raise ModelError(
                CFG_INVALID_YAML,
                f"YAML root must be a mapping, got {type(data).__name__}",
                hint="Wrap the sections under keys: model/parallelism/training/data/monitor/serving.",
                context={"path": path},
            )

        sections = {
            "model": ModelConfig,
            "parallelism": ParallelismConfig,
            "training": TrainingConfig,
            "data": DataConfig,
            "monitor": MonitorConfig,
            "serving": ServingConfig,
        }
        kwargs: Dict[str, Any] = {}
        for section, section_cls in sections.items():
            raw = data.get(section, {})
            if not isinstance(raw, dict):
                raise ModelError(
                    CFG_INVALID_YAML,
                    f"Section '{section}' must be a mapping, got {type(raw).__name__}",
                    hint=f"Use 'section:' followed by 'key: value' pairs under '{section}'.",
                    context={"section": section},
                )
            kwargs[section] = cls._build_section(section, section_cls, raw, path)
        return cls(**kwargs)

    @staticmethod
    def _build_section(section: str, section_cls: Type, raw: Dict[str, Any], path: str) -> Any:
        """Instantiate one config section, rejecting unknown keys explicitly."""
        valid = {f.name for f in dataclasses.fields(section_cls)}
        unknown = sorted(set(raw) - valid)
        if unknown:
            raise ModelError(
                CFG_UNKNOWN_FIELD,
                f"Unknown key(s) in section '{section}': {', '.join(unknown)}",
                hint=f"Allowed keys: {', '.join(sorted(valid))}.",
                context={"section": section, "unknown_keys": unknown, "path": path},
            )
        try:
            return section_cls(**raw)
        except TypeError as exc:
            raise ModelError(
                CFG_UNKNOWN_FIELD,
                f"Type error while building section '{section}': {exc}",
                hint="Check the value types declared under this section.",
                context={"section": section, "path": path},
            ) from exc
