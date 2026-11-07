# -*- coding: utf-8 -*-
"""virtu_omni.reverse_engineering — 工业级三维 CAD 逆向工程、特征重构与确定性客观评测套件."""

from virtu_omni.reverse_engineering.graders import (
    grade_dimension_fidelity,
    grade_family_classification,
    grade_volume_conservation,
    grade_hole_pattern_fidelity,
    grade_parametric_feature_tree,
    grade_vba_code_integrity,
    grade_reconstruction_case
)
from virtu_omni.reverse_engineering.scaffold import ReverseEngineeringScaffold

__all__ = [
    "grade_dimension_fidelity",
    "grade_family_classification",
    "grade_volume_conservation",
    "grade_hole_pattern_fidelity",
    "grade_parametric_feature_tree",
    "grade_vba_code_integrity",
    "grade_reconstruction_case",
    "ReverseEngineeringScaffold"
]
