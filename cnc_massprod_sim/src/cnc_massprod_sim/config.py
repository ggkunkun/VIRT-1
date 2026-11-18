# -*- coding: utf-8 -*-
"""配置装载：控制器 profile (controllers.yaml) + 工件原型 + 工艺标准。

所有参数从权威源读取，不在本 Agent 内写死数值：
  * 控制器 G/M 指令集 / 面板模式 / 换刀回退 / 补偿语法 → config/controllers.yaml
  * 材质力学 / 余量 / 装夹 / 安全阈值 → virtu_omni.manufacturing.process_standards
  * 工件几何 / KeepOut / 刀具 / 工序 / 节拍目标 → cnc_controller_runtime 原型
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

import yaml

_PKG = Path(__file__).resolve()
_SIM_ROOT = _PKG.parents[2]          # cnc_massprod_sim/
_WORKSPACE = _SIM_ROOT.parent        # D:/Virtu模型/

for _p in (str(_WORKSPACE), str(_SIM_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

CONTROLLERS_YAML = _SIM_ROOT / "config" / "controllers.yaml"


def workspace() -> Path:
    return _WORKSPACE


def sim_root() -> Path:
    return _SIM_ROOT


def load_controller_profiles() -> Dict[str, Dict[str, Any]]:
    """读取五种控制器的完整 profile（含 G/M 指令集、模态组、软限位参数）。"""
    data = yaml.safe_load(CONTROLLERS_YAML.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not data:
        raise RuntimeError(f"控制器配置为空或非法: {CONTROLLERS_YAML}")
    return data


def dialect_to_profile(process_family: str) -> Dict[str, str]:
    """方言 + 工艺族 → 控制器 profile id（与 runtime.resolve_controller_id 一致）。"""
    return {
        ("fanuc", "turning"): "fanuc_0i_tf",
        ("fanuc", "milling"): "fanuc_0i_mf",
        ("siemens", "turning"): "siemens_840d_sl",
        ("siemens", "milling"): "siemens_840d_sl",
        ("hnc", "turning"): "hnc_8t",
        ("hnc", "milling"): "hnc_8m",
    }


SUPPORTED_WORKPIECES = [
    "WP-SHAFT-3JAW",       # 三爪卡盘车削（FANUC 0i-TF / 840D sl / HNC-8T）
    "WP-MANIFOLD-VISE",    # 精密虎钳铣削（FANUC 0i-MF / 840D sl / HNC-8M）
    "WP-HOUSING-FIXTURE",  # 专用一面两销夹具铣削
]
SUPPORTED_DIALECTS = ["fanuc", "siemens", "hnc"]
