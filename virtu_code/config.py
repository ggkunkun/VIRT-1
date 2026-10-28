"""Configuration center for Code Large Language Model pipeline.

Provides strongly-typed dataclasses for:
1. GitHub Scraper & 3-level auditable filtering rules
2. Multi-language source code preprocessing
3. Syntax-aware code tokenization & streaming vectorization
4. Distributed Causal LM / FIM pretraining
5. Multi-dimensional code capability evaluation
6. License compliance ledger & provenance tracking
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List
import os
import yaml


@dataclass
class ScraperConfig:
    """GitHub API crawler and 3-level filtering parameters."""
    max_requests_per_minute: int = 50
    request_timeout_seconds: int = 15
    max_retries: int = 3
    backoff_factor: float = 2.0
    circuit_breaker_failures: int = 5
    circuit_breaker_cooldown_seconds: int = 60

    # Level 1: License Filter (OSI Permissive ONLY)
    allowed_licenses: List[str] = field(default_factory=lambda: [
        "MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "Unlicense", "CC0-1.0"
    ])
    prohibited_licenses: List[str] = field(default_factory=lambda: [
        "GPL-2.0", "GPL-3.0", "AGPL-3.0", "LGPL-2.1", "LGPL-3.0", "MPL-2.0", "SSPL-1.0",
        "CC-BY-NC-4.0", "CC-BY-NC-ND-4.0"
    ])

    # Level 2: Activity Filter
    min_stars: int = 50
    max_stars: int = 500000
    max_days_since_last_commit: int = 180
    min_contributors: int = 3
    max_issue_resolution_days: int = 14

    # Level 3: Quality & Structure Filter
    required_structural_markers: List[str] = field(default_factory=lambda: [
        "README", "test", "src", "lib", "build"
    ])
    min_business_loc: int = 500
    exclude_forks_with_zero_delta: bool = True

    output_dir: str = "data/raw"
    audit_log_path: str = "logs/scraper_audit.jsonl"


@dataclass
class PreprocessingConfig:
    """Source code cleaning, deduplication, and normalization."""
    supported_languages: List[str] = field(default_factory=lambda: [
        "java", "python", "javascript", "typescript", "c", "cpp", "go", "rust"
    ])
    excluded_directories: List[str] = field(default_factory=lambda: [
        "node_modules", "vendor", "target", "build", "dist", "out", "bin",
        ".git", ".github", "__pycache__", ".venv", "env", "site-packages"
    ])
    excluded_extensions: List[str] = field(default_factory=lambda: [
        ".exe", ".dll", ".so", ".dylib", ".class", ".pyc", ".o", ".a",
        ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg",
        ".zip", ".tar", ".gz", ".7z", ".pdf", ".lock"
    ])
    min_line_length: int = 3
    max_line_length: int = 1000
    max_consecutive_blank_lines: int = 2
    dedup_hash_algo: str = "sha256"
    output_dir: str = "data/processed"
    metadata_index_path: str = "data/processed/clean_code_metadata.jsonl"


@dataclass
class TokenizerConfig:
    """Syntax-aware code tokenizer and streaming DataLoader configurations."""
    vocab_size: int = 64000
    max_sequence_length: int = 4096
    fim_rate: float = 0.5  # Fill-in-the-Middle permutation rate
    fim_spm_rate: float = 0.5  # SPM vs PSM permutation ratio
    indentation_tokenization: bool = True
    streaming_batch_size: int = 64
    target_throughput_samples_per_sec: int = 10000


@dataclass
class CodeTrainingConfig:
    """Distributed Code LLM Pretraining hyperparameters."""
    hidden_dim: int = 2048
    intermediate_dim: int = 6144
    num_layers: int = 24
    num_attention_heads: int = 16
    num_kv_heads: int = 4
    learning_rate: float = 3e-4
    min_learning_rate: float = 3e-5
    warmup_steps: int = 2000
    max_steps: int = 100000
    save_interval_steps: int = 10000
    checkpoint_dir: str = "checkpoints/code_llm"
    training_log_path: str = "logs/code_training.jsonl"
    mixed_precision: str = "bf16"


@dataclass
class EvaluationConfig:
    """10-language code capability benchmark configurations."""
    languages: List[str] = field(default_factory=lambda: [
        "python", "java", "cpp", "c", "go", "rust", "javascript", "typescript", "csharp", "shell"
    ])
    passing_threshold_score: float = 75.0
    benchmark_dataset_path: str = "data/benchmark/code_eval_dataset.json"
    report_output_path: str = "benchmarks/code_capability_report.md"


@dataclass
class ComplianceConfig:
    """License provenance ledger and immutable audit configuration."""
    ledger_path: str = "data/compliance/license_provenance_manifest.json"
    audit_chain_path: str = "logs/compliance_audit_ledger.jsonl"
    audit_retention_years: int = 3
    scan_report_path: str = "benchmarks/compliance_scan_report.md"


@dataclass
class VirtuCodeConfig:
    """Unified configuration root for Code LLM system."""
    scraper: ScraperConfig = field(default_factory=ScraperConfig)
    preprocessing: PreprocessingConfig = field(default_factory=PreprocessingConfig)
    tokenizer: TokenizerConfig = field(default_factory=TokenizerConfig)
    training: CodeTrainingConfig = field(default_factory=CodeTrainingConfig)
    evaluation: EvaluationConfig = field(default_factory=EvaluationConfig)
    compliance: ComplianceConfig = field(default_factory=ComplianceConfig)

    @classmethod
    def from_yaml(cls, path: str) -> VirtuCodeConfig:
        """Load configuration from YAML file."""
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return cls(
            scraper=ScraperConfig(**data.get("scraper", {})),
            preprocessing=PreprocessingConfig(**data.get("preprocessing", {})),
            tokenizer=TokenizerConfig(**data.get("tokenizer", {})),
            training=CodeTrainingConfig(**data.get("training", {})),
            evaluation=EvaluationConfig(**data.get("evaluation", {})),
            compliance=ComplianceConfig(**data.get("compliance", {})),
        )

    def to_yaml(self, path: str) -> None:
        """Export configuration to YAML file."""
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        raw_dict = {
            "scraper": self.scraper.__dict__,
            "preprocessing": self.preprocessing.__dict__,
            "tokenizer": self.tokenizer.__dict__,
            "training": self.training.__dict__,
            "evaluation": self.evaluation.__dict__,
            "compliance": self.compliance.__dict__,
        }
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(raw_dict, f, default_flow_style=False, sort_keys=False)
