"""Configuration specifications for Virtu-Omni-10B Multimodal Model.

Provides strongly typed dataclasses and validation for model architecture,
distributed training, streaming data pipeline, health monitoring, and serving.
"""

from __future__ import annotations
import os
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Optional
import yaml

from virtu_omni.errors import ConfigurationError


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

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Validate architectural hyperparameters for mathematical consistency."""
        if self.num_layers < 1:
            raise ConfigurationError(f"num_layers must be >= 1, got {self.num_layers}")
        if self.hidden_dim <= 0 or self.intermediate_dim <= 0:
            raise ConfigurationError("hidden_dim and intermediate_dim must be positive")
        if self.num_attention_heads < 1 or self.num_kv_heads < 1:
            raise ConfigurationError("num_attention_heads and num_kv_heads must be >= 1")
        if self.num_attention_heads % self.num_kv_heads != 0:
            raise ConfigurationError(
                f"num_attention_heads ({self.num_attention_heads}) must be divisible by "
                f"num_kv_heads ({self.num_kv_heads})"
            )
        if self.image_resolution <= 0 or self.patch_size <= 0:
            raise ConfigurationError("image_resolution and patch_size must be positive")
        if self.image_resolution % self.patch_size != 0:
            raise ConfigurationError(
                f"image_resolution ({self.image_resolution}) must be divisible by "
                f"patch_size ({self.patch_size})"
            )
        if self.max_loop_steps < 1:
            raise ConfigurationError(f"max_loop_steps must be >= 1, got {self.max_loop_steps}")

    @property
    def total_estimated_parameters(self) -> int:
        """Calculate exact theoretical parameter count."""
        layer_params = (
            (self.hidden_dim * self.hidden_dim)
            + 2 * (self.hidden_dim * (self.num_kv_heads * self.head_dim))
            + (self.hidden_dim * self.hidden_dim)
            + 3 * (self.hidden_dim * self.intermediate_dim)
            + 2 * self.hidden_dim
        )
        backbone_params = self.num_layers * layer_params
        text_emb = self.vocab_size * self.hidden_dim
        vision_proj = (3 * self.patch_size * self.patch_size * self.hidden_dim) + (
            self.hidden_dim * self.hidden_dim
        )
        vision_head = self.hidden_dim * self.vision_codebook_size
        lm_head = self.hidden_dim * self.vocab_size
        final_norm = self.hidden_dim

        return backbone_params + text_emb + vision_proj + vision_head + lm_head + final_norm


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
    host: str = "0.0.0.0"
    port: int = 8080
    workers: int = 4
    max_concurrency: int = 64
    target_latency_ms: float = 200.0  # Single A100 latency <= 200ms
    enable_paged_attention: bool = True
    enable_smoothquant_int8: bool = False
    timeout_seconds: float = 30.0


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
        """Load configuration from YAML file."""
        if not os.path.exists(path):
            raise ConfigurationError(f"Configuration YAML file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        return cls(
            model=ModelConfig(**data.get("model", {})),
            parallelism=ParallelismConfig(**data.get("parallelism", {})),
            training=TrainingConfig(**data.get("training", {})),
            data=DataConfig(**data.get("data", {})),
            monitor=MonitorConfig(**data.get("monitor", {})),
            serving=ServingConfig(**data.get("serving", {})),
        )
