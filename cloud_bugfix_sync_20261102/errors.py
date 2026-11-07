"""Unified Exception Hierarchy for Virtu-Omni-10B.

Provides structured, domain-specific exception classes across configuration,
checkpoint loading, tensor validation, and inference serving. All custom
exceptions inherit from both ``VirtuError`` and standard Python exceptions
(``ValueError``, ``RuntimeError``, ``TimeoutError``) for backward compatibility.
"""

from __future__ import annotations


class VirtuError(Exception):
    """Base exception for all Virtu-Omni errors."""


class ConfigurationError(VirtuError, ValueError):
    """Raised when configuration parameters are invalid or inconsistent."""


class CheckpointLoadError(VirtuError, RuntimeError):
    """Raised when a model checkpoint or Smelt bundle fails integrity or schema checks."""


class ValidationError(VirtuError, ValueError):
    """Raised when input tensors, dimensions, or engineering parameters fail validation."""


class InferenceTimeoutError(VirtuError, TimeoutError):
    """Raised when model inference or external CAD/CAM tool execution exceeds deadline."""


__all__ = [
    "VirtuError",
    "ConfigurationError",
    "CheckpointLoadError",
    "ValidationError",
    "InferenceTimeoutError",
]
