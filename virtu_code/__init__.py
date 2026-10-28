"""VirtuCode: Industrial-Grade Code Large Language Model Construction Framework.

Fully compliant, auditable, and end-to-end framework covering:
1. GitHub Open-Source Crawler & 3-Level Auditable Filtering
2. Source Code Preprocessing, Cleansing, Deduplication & Normalization
3. Multi-Language Syntax-Aware Tokenization & Streaming Vectorization
4. Distributed Causal LM / Fill-in-the-Middle Pretraining Engine
5. 10-Language Code Capability Benchmark Suite
6. Cryptographically Verifiable License Provenance & Audit Ledger
"""

__version__ = "1.0.0"
__author__ = "Antigravity Engineering"

from virtu_code.config import (
    VirtuCodeConfig,
    ScraperConfig,
    PreprocessingConfig,
    TokenizerConfig,
    CodeTrainingConfig,
    EvaluationConfig,
    ComplianceConfig,
)

__all__ = [
    "VirtuCodeConfig",
    "ScraperConfig",
    "PreprocessingConfig",
    "TokenizerConfig",
    "CodeTrainingConfig",
    "EvaluationConfig",
    "ComplianceConfig",
]
