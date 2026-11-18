"""Manufacturing planning utilities with fail-closed evidence gates."""

from .machine_selection import (
    FEATURE_RULES,
    load_training_machine_profiles,
    requirements_from_features,
    select_machine_and_stock,
)
from .nc_audit import audit_nc_capability

__all__ = [
    "FEATURE_RULES", "load_training_machine_profiles",
    "requirements_from_features", "select_machine_and_stock",
    "audit_nc_capability",
]
