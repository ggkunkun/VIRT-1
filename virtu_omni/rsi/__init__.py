"""Bounded, approval-gated recursive self-improvement (RSI) for Virtu.

Importing this package never starts inference, training, or deployment.
"""

from .approval import approved_policy, find_latest_approved_policy, get_active_rsi_strategy, infer, review, verified_run
from .candidates import SUPPORTED, build_sft_candidates, development_feedback
from .contracts import (
    Budget,
    BudgetExhausted,
    Config,
    RSIError,
    canonical_json,
    fingerprint,
    inside,
    load_cases,
    local_url,
    normalized,
    question_key,
    read_jsonl,
    scenario_keys,
    split_cases,
)
from .engine import (
    PROPOSER_SYSTEM,
    approve_run,
    development_improves,
    parse_proposal,
    run,
    run_rsi,
    verify_approval,
)
from .evaluation import (
    CRITICAL_TYPES,
    PHYSICS_TYPES,
    LocalModel,
    evaluate_cases,
    policy_messages,
    strict_score,
    summarize,
)
from .gates import BAD_VERDICTS, validation_gate
from .storage import (
    FileLock,
    RunStore,
    append_jsonl,
    assert_sources,
    file_hash,
    source_hashes,
    utc_now,
    write_json,
)

__version__ = "1.0.0"

__all__ = [
    "Config",
    "Budget",
    "BudgetExhausted",
    "RSIError",
    "LocalModel",
    "RunStore",
    "FileLock",
    "run",
    "run_rsi",
    "review",
    "infer",
    "approved_policy",
    "find_latest_approved_policy",
    "get_active_rsi_strategy",
    "verified_run",
    "approve_run",
    "verify_approval",
    "validation_gate",
    "build_sft_candidates",
    "development_feedback",
    "strict_score",
    "evaluate_cases",
    "summarize",
    "load_cases",
    "split_cases",
    "parse_proposal",
    "development_improves",
]
