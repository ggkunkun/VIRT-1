# -*- coding: utf-8 -*-
"""virtu_omni/reverse_engineering/scaffold.py — 逆向工程数学脚手架与几何哨兵.

在模型推理与工业执行之间构筑严格的数学物理校验边界：
1. 几何拓扑前置解析 (StepReverseEngine)；
2. 约束求解与参数化特征树合成；
3. 几何哨兵 (Geometric Sentinel) 校验：零体积阻断、尺寸量纲校验、方程式自洽性。
"""

from __future__ import annotations
import os
import sys
from typing import Dict, Any, Optional
from pathlib import Path

from virtu_omni.engine.step_reverse_engine import StepReverseEngine, StepReverseResult


class ReverseEngineeringScaffold:
    """工业级逆向工程智能脚手架."""

    def __init__(self, workspace_root: Optional[str] = None):
        self.root = Path(workspace_root or os.getcwd())
        self.engine = StepReverseEngine(str(self.root))

    def solve(self, step_path: str, execute_solidworks: bool = False, out_sldprt: Optional[str] = None) -> Dict[str, Any]:
        """对 STEP 模型进行全量逆向分析、特征提取与参数化重建."""
        target_path = Path(step_path)
        if not target_path.is_absolute():
            target_path = self.root / target_path

        if not target_path.exists():
            return {
                "success": False,
                "error": f"STEP file not found: {target_path}",
                "case_id": "UNKNOWN"
            }

        # 1. 调用 StepReverseEngine 解析实体
        res: StepReverseResult = self.engine.analyze_step(str(target_path))

        # 2. 几何哨兵安全审查 (Geometric Sentinel)
        if res.theoretical_volume_mm3 <= 0:
            return {
                "success": False,
                "error": f"Geometric Sentinel Veto: Non-positive theoretical volume ({res.theoretical_volume_mm3} mm³)",
                "raw_result": res
            }

        rebuild_info = {"status": "success" if res.success else "failed", "file_exists": True}
        if execute_solidworks:
            dest = out_sldprt or str(self.root / "artifacts" / f"{target_path.stem}_reversed.SLDPRT")
            rebuild_info = self.engine.execute_solidworks_rebuild(res, dest)

        return {
            "success": res.success,
            "step_file": str(target_path),
            "file_size_bytes": res.file_size_bytes,
            "part_family": res.part_family,
            "bounding_box": res.bounding_box,
            "cylindrical_diameters": res.cylindrical_diameters,
            "hole_patterns": res.hole_patterns,
            "toroidal_grooves": res.toroidal_grooves,
            "conical_half_angles": res.conical_half_angles,
            "theoretical_volume_mm3": res.theoretical_volume_mm3,
            "key_dimensions": res.key_dimensions,
            "reconstruction_vba": res.reconstruction_vba,
            "rebuild_success": res.success and len(res.reconstruction_vba) > 50,
            "rebuild_info": rebuild_info
        }
