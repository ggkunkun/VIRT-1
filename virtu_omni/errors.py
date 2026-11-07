# -*- coding: utf-8 -*-
"""Unified error codes and exception types for the Virtu-Omni model chain.

Every failure surfaced by the model pipeline carries an explicit, stable code so
that logs, REST responses and monitoring dashboards can map an error to a
precise processing node instead of a generic stack trace.

Code ranges:
- E1xxx: configuration / boundary validation
- E2xxx: inference core (architecture, loop controller)
- E3xxx: data preprocessing pipeline
- E4xxx: serving / output generation
- E5xxx: feature transformation (geometry bridge, expander, tokenizer)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


# --- Configuration ---------------------------------------------------------------
CFG_INVALID_FIELD = "E1001"       # A config field holds an illegal value
CFG_INVALID_YAML = "E1002"        # YAML structure is not a mapping
CFG_UNKNOWN_FIELD = "E1003"       # YAML contains keys unknown to the dataclass

# --- Inference core --------------------------------------------------------------
INFER_NO_MODALITY = "E2001"       # Neither input_ids nor images were supplied
INFER_INVALID_MODE = "E2002"      # Unknown output routing mode
INFER_MODE_MODALITY_MISMATCH = "E2003"  # Mode requires a modality that is missing
INFER_LABEL_SHAPE = "E2004"       # labels are incompatible with the text positions
INFER_ROPE_GRID_MISMATCH = "E2005"  # Vision token count != grid_h * grid_w
INFER_VISION_SHAPE = "E2006"      # Image tensor does not satisfy patch constraints
INFER_MASK_ARGUMENT = "E2007"     # Invalid mask construction arguments
INFER_LOOP_METRIC = "E2008"       # Unsupported convergence metric

# --- Data pipeline ---------------------------------------------------------------
DATA_IMAGE_TYPE = "E3001"         # Sample image is not a PIL image
DATA_TEXT_TYPE = "E3002"          # Sample text is not a string
DATA_EMPTY_BATCH = "E3003"        # collate_fn received an empty batch
DATA_BATCH_SHAPE = "E3004"        # Samples inside a batch are inconsistent
DATA_INVALID_ARGUMENT = "E3005"   # num_samples / batch_size out of range

# --- Serving ---------------------------------------------------------------------
SERVE_IMAGE_DECODE = "E4001"      # Base64 / image payload could not be decoded
SERVE_MODEL_FAILURE = "E4002"     # Forward pass raised an unexpected error
SERVE_INFER_FAILURE = "E4003"     # Generation returned no usable tokens

# --- Feature transformation ------------------------------------------------------
FEAT_GEOM_VALUE = "E5001"         # Geometry attribute is not a finite number
FEAT_VOCAB_RANGE = "E5002"        # Geometry token id exceeds the model vocabulary
FEAT_SOURCE_WEIGHTS = "E5003"     # Source checkpoint missing required tensors
FEAT_TOKENIZER_ARG = "E5004"      # Tokenizer input / max_length is invalid


@dataclass
class ModelError(Exception):
    """Structured exception carrying a stable code and remediation hint."""

    code: str
    message: str
    hint: str = ""
    context: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Keep Exception's args populated so str(e) stays informative.
        Exception.__init__(self, f"[{self.code}] {self.message}")

    def to_dict(self) -> Dict[str, Any]:
        """Serializable representation for REST responses and audit logs."""
        return {
            "code": self.code,
            "message": self.message,
            "hint": self.hint,
            "context": self.context,
        }


__all__ = [
    "ModelError",
    "CFG_INVALID_FIELD",
    "CFG_INVALID_YAML",
    "CFG_UNKNOWN_FIELD",
    "INFER_NO_MODALITY",
    "INFER_INVALID_MODE",
    "INFER_MODE_MODALITY_MISMATCH",
    "INFER_LABEL_SHAPE",
    "INFER_ROPE_GRID_MISMATCH",
    "INFER_VISION_SHAPE",
    "INFER_MASK_ARGUMENT",
    "INFER_LOOP_METRIC",
    "DATA_IMAGE_TYPE",
    "DATA_TEXT_TYPE",
    "DATA_EMPTY_BATCH",
    "DATA_BATCH_SHAPE",
    "DATA_INVALID_ARGUMENT",
    "SERVE_IMAGE_DECODE",
    "SERVE_MODEL_FAILURE",
    "SERVE_INFER_FAILURE",
    "FEAT_GEOM_VALUE",
    "FEAT_VOCAB_RANGE",
    "FEAT_SOURCE_WEIGHTS",
    "FEAT_TOKENIZER_ARG",
]
