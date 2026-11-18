# -*- coding: utf-8 -*-
"""virtu_omni/internet — Universal Internet, Safety Filtering, and Continual Deep Learning Subsystem."""

from virtu_omni.internet.safety_filter import (
    HarmfulContentFilter,
    FilterResult,
    get_safety_filter,
)
from virtu_omni.internet.search_engine import (
    WebSearchEngine,
    SearchResultItem,
    SearchResponse,
    get_search_engine,
)
from virtu_omni.internet.deep_learning_pipeline import (
    ContinualLearningPipeline,
    KnowledgeEntry,
    get_learning_pipeline,
)
from virtu_omni.internet.internet_hub import (
    VirtuInternetHub,
    ModelIdentityInfo,
    get_internet_hub,
)
from virtu_omni.internet.augmentation import (
    MARKER,
    internet_enabled,
    web_context_block,
    augment_prompt,
    augment_messages,
)
from virtu_omni.internet.autonomous_engine import (
    AutonomousLearningEngine,
    AutonomousTopic,
    get_autonomous_engine,
)

__all__ = [
    "HarmfulContentFilter",
    "FilterResult",
    "get_safety_filter",
    "WebSearchEngine",
    "SearchResultItem",
    "SearchResponse",
    "get_search_engine",
    "ContinualLearningPipeline",
    "KnowledgeEntry",
    "get_learning_pipeline",
    "VirtuInternetHub",
    "ModelIdentityInfo",
    "get_internet_hub",
    "MARKER",
    "internet_enabled",
    "web_context_block",
    "augment_prompt",
    "augment_messages",
    "AutonomousLearningEngine",
    "AutonomousTopic",
    "get_autonomous_engine",
]
