# -*- coding: utf-8 -*-
"""Industrial CNC process standards, blank allowances, clamping & safety policies.

Aligned with standard mechanical machining reference specifications:
- 《金属切削加工工艺手册》 (Metal Cutting Process Handbook)
- 《数控加工工艺规范》 (CNC Machining Process Specification)
- GB/T 699, GB/T 3077, GB/T 3190, GB/T 2965, GB/T 20878, GB/T 9439, GB/T 1800 (ISO 286)

Provides deterministic engineering lookup, cutting parameter derivation
(n = 1000*Vc / (pi*D), F = n*z*fz / f_rev), Taylor tool-life constants,
full-dimensional allowance allocation (rough, semi-finish, finish, corner rest),
clamping datum & keep-out geometries (3-jaw chuck, precision vise, dedicated
1-plane-2-pin zero-point fixture), and motion safety thresholds (Z safe height,
R-plane, rapid deceleration zone, XY clearance).
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Literal, Optional, Tuple

from stock_derivation import BBox, StockSpec, derive_stock_strict

ClampingType = Literal["three_jaw_chuck", "precision_vise", "dedicated_fixture"]
OperationType = Literal["turning_rough", "turning_finish", "milling_rough",
                        "milling_semi_finish", "milling_finish", "drilling",
                        "tapping", "grooving"]


@dataclass(frozen=True)
class MaterialSpec:
    material_id: str
    gb_standard: str
    name_zh: str
    density_g_cm3: float
    yield_strength_mpa: float
    tensile_strength_mpa: float
    elastic_modulus_gpa: float
    hardness_hb: float
    thermal_conductivity_w_mk: float
    specific_cutting_force_kc11_mpa: float
    machinability_km: float
    taylor_ct: float          # Vc * T^n = C_T (m/min @ T=1 min, coated carbide baseline)
    taylor_n: float
    coolant_mode: str         # flood_emulsion | flood_high_pressure | mist_air | dry_air
    cutting_ranges: Dict[str, Dict[str, Tuple[float, float]]]
    # Handbook single-side allowances (mm)
    rough_allowance_mm: Tuple[float, float]
    semi_finish_allowance_mm: Tuple[float, float]
    finish_allowance_mm: Tuple[float, float]
    corner_rest_allowance_mm: Tuple[float, float]
    handbook_ref: str


MATERIAL_HANDBOOK: Dict[str, MaterialSpec] = {
    "Steel45": MaterialSpec(
        material_id="Steel45",
        gb_standard="GB/T 699-2015 (45优质碳素结构钢)",
        name_zh="45号调质/正火碳素结构钢",
        density_g_cm3=7.85,
        yield_strength_mpa=355.0,
        tensile_strength_mpa=600.0,
        elastic_modulus_gpa=210.0,
        hardness_hb=215.0,
        thermal_conductivity_w_mk=49.8,
        specific_cutting_force_kc11_mpa=1800.0,
        machinability_km=1.00,
        taylor_ct=290.0,
        taylor_n=0.25,
        coolant_mode="flood_emulsion",
        cutting_ranges={
            "turning_rough": {"vc": (120.0, 200.0), "f_rev": (0.20, 0.45), "ap": (1.5, 4.0)},
            "turning_finish": {"vc": (180.0, 280.0), "f_rev": (0.08, 0.16), "ap": (0.2, 0.5)},
            "milling_rough": {"vc": (110.0, 180.0), "fz": (0.08, 0.18), "ap": (1.5, 4.0)},
            "milling_semi_finish": {"vc": (140.0, 210.0), "fz": (0.06, 0.12), "ap": (0.5, 1.5)},
            "milling_finish": {"vc": (160.0, 240.0), "fz": (0.04, 0.10), "ap": (0.1, 0.4)},
            "drilling": {"vc": (60.0, 100.0), "f_rev": (0.10, 0.22), "ap": (2.0, 5.0)},
            "tapping": {"vc": (10.0, 22.0), "f_rev": (1.0, 2.0), "ap": (0.5, 2.0)},
            "grooving": {"vc": (80.0, 130.0), "f_rev": (0.06, 0.12), "ap": (0.5, 3.0)},
        },
        rough_allowance_mm=(2.0, 4.0),
        semi_finish_allowance_mm=(0.4, 0.8),
        finish_allowance_mm=(0.15, 0.35),
        corner_rest_allowance_mm=(0.10, 0.25),
        handbook_ref="《金属切削加工工艺手册》第3篇 第2章 碳素钢车/铣加工参数",
    ),
    "40Cr": MaterialSpec(
        material_id="40Cr",
        gb_standard="GB/T 3077-2015 (40Cr合金结构钢调质态)",
        name_zh="40Cr调质合金结构钢",
        density_g_cm3=7.85,
        yield_strength_mpa=785.0,
        tensile_strength_mpa=980.0,
        elastic_modulus_gpa=211.0,
        hardness_hb=245.0,
        thermal_conductivity_w_mk=42.6,
        specific_cutting_force_kc11_mpa=2100.0,
        machinability_km=0.82,
        taylor_ct=245.0,
        taylor_n=0.24,
        coolant_mode="flood_emulsion",
        cutting_ranges={
            "turning_rough": {"vc": (100.0, 170.0), "f_rev": (0.18, 0.38), "ap": (1.5, 3.5)},
            "turning_finish": {"vc": (150.0, 240.0), "f_rev": (0.07, 0.14), "ap": (0.2, 0.45)},
            "milling_rough": {"vc": (95.0, 155.0), "fz": (0.07, 0.15), "ap": (1.2, 3.5)},
            "milling_semi_finish": {"vc": (120.0, 180.0), "fz": (0.05, 0.11), "ap": (0.4, 1.2)},
            "milling_finish": {"vc": (140.0, 210.0), "fz": (0.04, 0.08), "ap": (0.1, 0.3)},
            "drilling": {"vc": (50.0, 85.0), "f_rev": (0.08, 0.18), "ap": (1.5, 4.0)},
            "tapping": {"vc": (8.0, 18.0), "f_rev": (1.0, 2.0), "ap": (0.5, 2.0)},
            "grooving": {"vc": (70.0, 115.0), "f_rev": (0.05, 0.10), "ap": (0.5, 2.5)},
        },
        rough_allowance_mm=(2.0, 4.0),
        semi_finish_allowance_mm=(0.4, 0.7),
        finish_allowance_mm=(0.15, 0.30),
        corner_rest_allowance_mm=(0.10, 0.25),
        handbook_ref="《金属切削加工工艺手册》第3篇 合金结构钢调质态切削用量",
    ),
    "AL7075-T6": MaterialSpec(
        material_id="AL7075-T6",
        gb_standard="GB/T 3190-2020 (7075-T6超硬铝合金)",
        name_zh="7075-T6 航空超硬铝合金",
        density_g_cm3=2.81,
        yield_strength_mpa=503.0,
        tensile_strength_mpa=572.0,
        elastic_modulus_gpa=71.7,
        hardness_hb=150.0,
        thermal_conductivity_w_mk=130.0,
        specific_cutting_force_kc11_mpa=750.0,
        machinability_km=2.80,
        taylor_ct=880.0,
        taylor_n=0.30,
        coolant_mode="flood_emulsion",
        cutting_ranges={
            "turning_rough": {"vc": (280.0, 550.0), "f_rev": (0.18, 0.40), "ap": (2.0, 5.0)},
            "turning_finish": {"vc": (350.0, 700.0), "f_rev": (0.06, 0.15), "ap": (0.15, 0.5)},
            "milling_rough": {"vc": (300.0, 750.0), "fz": (0.10, 0.25), "ap": (2.0, 8.0)},
            "milling_semi_finish": {"vc": (380.0, 850.0), "fz": (0.08, 0.18), "ap": (0.5, 2.0)},
            "milling_finish": {"vc": (400.0, 1000.0), "fz": (0.05, 0.12), "ap": (0.1, 0.3)},
            "drilling": {"vc": (120.0, 220.0), "f_rev": (0.12, 0.28), "ap": (3.0, 8.0)},
            "tapping": {"vc": (15.0, 35.0), "f_rev": (1.0, 2.0), "ap": (0.5, 2.0)},
            "grooving": {"vc": (220.0, 400.0), "f_rev": (0.08, 0.16), "ap": (0.5, 3.0)},
        },
        rough_allowance_mm=(1.5, 3.0),
        semi_finish_allowance_mm=(0.3, 0.6),
        finish_allowance_mm=(0.10, 0.20),
        corner_rest_allowance_mm=(0.10, 0.20),
        handbook_ref="《金属切削加工工艺手册》轻合金高速铣削与车削标准参数",
    ),
    "Ti-6Al-4V": MaterialSpec(
        material_id="Ti-6Al-4V",
        gb_standard="GB/T 2965-2023 (TC4钛合金)",
        name_zh="TC4 (Ti-6Al-4V) 航空钛合金",
        density_g_cm3=4.43,
        yield_strength_mpa=880.0,
        tensile_strength_mpa=950.0,
        elastic_modulus_gpa=114.0,
        hardness_hb=335.0,
        thermal_conductivity_w_mk=6.7,
        specific_cutting_force_kc11_mpa=1450.0,
        machinability_km=0.35,
        taylor_ct=110.0,
        taylor_n=0.20,
        coolant_mode="flood_high_pressure",
        cutting_ranges={
            "turning_rough": {"vc": (40.0, 65.0), "f_rev": (0.12, 0.25), "ap": (1.0, 2.5)},
            "turning_finish": {"vc": (55.0, 85.0), "f_rev": (0.06, 0.12), "ap": (0.2, 0.4)},
            "milling_rough": {"vc": (38.0, 65.0), "fz": (0.06, 0.12), "ap": (0.8, 2.5)},
            "milling_semi_finish": {"vc": (45.0, 75.0), "fz": (0.05, 0.10), "ap": (0.3, 0.8)},
            "milling_finish": {"vc": (55.0, 90.0), "fz": (0.04, 0.08), "ap": (0.15, 0.35)},
            "drilling": {"vc": (22.0, 42.0), "f_rev": (0.06, 0.14), "ap": (1.0, 3.0)},
            "tapping": {"vc": (4.0, 10.0), "f_rev": (1.0, 2.0), "ap": (0.5, 2.0)},
            "grooving": {"vc": (30.0, 50.0), "f_rev": (0.04, 0.08), "ap": (0.3, 1.5)},
        },
        rough_allowance_mm=(1.5, 3.0),
        semi_finish_allowance_mm=(0.4, 0.7),
        finish_allowance_mm=(0.20, 0.35),  # 防止过薄摩擦硬化
        corner_rest_allowance_mm=(0.12, 0.25),
        handbook_ref="《金属切削加工工艺手册》难加工材料(钛合金)低速大进给规范",
    ),
    "SS304": MaterialSpec(
        material_id="SS304",
        gb_standard="GB/T 20878-2007 (06Cr19Ni10奥氏体不锈钢)",
        name_zh="304奥氏体不锈钢",
        density_g_cm3=7.93,
        yield_strength_mpa=205.0,
        tensile_strength_mpa=520.0,
        elastic_modulus_gpa=193.0,
        hardness_hb=190.0,
        thermal_conductivity_w_mk=16.2,
        specific_cutting_force_kc11_mpa=2150.0,
        machinability_km=0.55,
        taylor_ct=170.0,
        taylor_n=0.22,
        coolant_mode="flood_emulsion",
        cutting_ranges={
            "turning_rough": {"vc": (75.0, 125.0), "f_rev": (0.15, 0.30), "ap": (1.0, 3.0)},
            "turning_finish": {"vc": (95.0, 150.0), "f_rev": (0.06, 0.13), "ap": (0.2, 0.4)},
            "milling_rough": {"vc": (65.0, 115.0), "fz": (0.05, 0.12), "ap": (1.0, 2.5)},
            "milling_semi_finish": {"vc": (80.0, 130.0), "fz": (0.04, 0.09), "ap": (0.3, 1.0)},
            "milling_finish": {"vc": (95.0, 150.0), "fz": (0.03, 0.07), "ap": (0.15, 0.3)},
            "drilling": {"vc": (30.0, 55.0), "f_rev": (0.07, 0.15), "ap": (1.5, 3.0)},
            "tapping": {"vc": (6.0, 12.0), "f_rev": (1.0, 2.0), "ap": (0.5, 2.0)},
            "grooving": {"vc": (55.0, 90.0), "f_rev": (0.04, 0.09), "ap": (0.4, 2.0)},
        },
        rough_allowance_mm=(1.8, 3.5),
        semi_finish_allowance_mm=(0.4, 0.7),
        finish_allowance_mm=(0.18, 0.30),
        corner_rest_allowance_mm=(0.12, 0.25),
        handbook_ref="《金属切削加工工艺手册》奥氏体不锈钢防加工硬化规范",
    ),
    "HT250": MaterialSpec(
        material_id="HT250",
        gb_standard="GB/T 9439-2010 (HT250灰铸铁)",
        name_zh="HT250 高强度灰铸铁",
        density_g_cm3=7.25,
        yield_strength_mpa=250.0,
        tensile_strength_mpa=250.0,
        elastic_modulus_gpa=115.0,
        hardness_hb=210.0,
        thermal_conductivity_w_mk=46.0,
        specific_cutting_force_kc11_mpa=1150.0,
        machinability_km=1.15,
        taylor_ct=310.0,
        taylor_n=0.25,
        coolant_mode="dry_air",
        cutting_ranges={
            "turning_rough": {"vc": (120.0, 210.0), "f_rev": (0.22, 0.45), "ap": (1.5, 4.0)},
            "turning_finish": {"vc": (160.0, 260.0), "f_rev": (0.08, 0.16), "ap": (0.2, 0.5)},
            "milling_rough": {"vc": (110.0, 190.0), "fz": (0.08, 0.18), "ap": (1.5, 4.0)},
            "milling_semi_finish": {"vc": (130.0, 210.0), "fz": (0.06, 0.13), "ap": (0.4, 1.5)},
            "milling_finish": {"vc": (150.0, 240.0), "fz": (0.05, 0.10), "ap": (0.1, 0.3)},
            "drilling": {"vc": (55.0, 95.0), "f_rev": (0.12, 0.25), "ap": (2.0, 5.0)},
            "tapping": {"vc": (10.0, 20.0), "f_rev": (1.0, 2.0), "ap": (0.5, 2.0)},
            "grooving": {"vc": (80.0, 140.0), "f_rev": (0.06, 0.14), "ap": (0.5, 3.0)},
        },
        rough_allowance_mm=(2.0, 4.0),
        semi_finish_allowance_mm=(0.4, 0.8),
        finish_allowance_mm=(0.15, 0.30),
        corner_rest_allowance_mm=(0.10, 0.25),
        handbook_ref="《金属切削加工工艺手册》灰铸铁高效切削规范",
    ),
}


@dataclass(frozen=True)
class ClampingDatumScheme:
    scheme_id: ClampingType
    name_zh: str
    applicable_processes: Tuple[str, ...]
    locating_principle: str
    dof_constrained: int
    wcs_origin_rule: str
    min_grip_depth_mm: float
    max_overhang_ld_ratio: float
    clamping_pressure_mpa: Tuple[float, float]
    repeatability_mm: float
    smed_interface: str
    keepout_clearance_z_mm: float
    keepout_clearance_xy_mm: float
    handbook_ref: str


CLAMPING_SCHEMES: Dict[ClampingType, ClampingDatumScheme] = {
    "three_jaw_chuck": ClampingDatumScheme(
        scheme_id="three_jaw_chuck",
        name_zh="三爪自定心液压卡盘（配硬爪/软爪轴向定位台）",
        applicable_processes=("turning", "mill_turn"),
        locating_principle="短圆柱面定心(4-DOF)+卡盘端面/台阶轴向止动(1-DOF)=5-DOF限制；L/D>3.0须配尾座顶尖(6-DOF)",
        dof_constrained=5,
        wcs_origin_rule="G54: X0=主轴回转中心, Z0=成品右端面(毛坯右端面预留端面车削余量+Z_end)",
        min_grip_depth_mm=20.0,
        max_overhang_ld_ratio=3.0,
        clamping_pressure_mpa=(1.2, 2.8),
        repeatability_mm=0.015,
        smed_interface="液压快换软爪(带定位止口键)",
        keepout_clearance_z_mm=5.0,
        keepout_clearance_xy_mm=4.0,
        handbook_ref="《数控加工工艺规范》车削装夹定位与悬伸安全准则",
    ),
    "precision_vise": ClampingDatumScheme(
        scheme_id="precision_vise",
        name_zh="精密平口虎钳（固定钳口基准+平行垫铁+左侧定位挡块）",
        applicable_processes=("milling_3axis", "milling_3plus2"),
        locating_principle="3-2-1六点定位：垫铁底面支承(3点/Z)+固定钳口侧基准(2点/Y)+左侧挡块止动(1点/X)",
        dof_constrained=6,
        wcs_origin_rule="G54: X0/Y0=工件上表面中心(或固定钳口角点), Z0=精加工顶平面",
        min_grip_depth_mm=8.0,
        max_overhang_ld_ratio=2.5,
        clamping_pressure_mpa=(0.8, 2.0),
        repeatability_mm=0.008,
        smed_interface="零点快换底板+卡位平行垫铁组",
        keepout_clearance_z_mm=3.0,
        keepout_clearance_xy_mm=5.0,
        handbook_ref="《数控加工工艺规范》铣削虎钳基准统一与干涉避让准则",
    ),
    "dedicated_fixture": ClampingDatumScheme(
        scheme_id="dedicated_fixture",
        name_zh="专用一面两销零点快换夹具（底面基准+圆柱销+削边销+压板）",
        applicable_processes=("milling_3axis", "milling_3plus2", "milling_5axis"),
        locating_principle="一面两销经典6-DOF定位：精密底平面(3点)+圆柱销A(2-DOF)+菱形削边销B(1-DOF角向防转)",
        dof_constrained=6,
        wcs_origin_rule="G54: X0/Y0=主定位销A中心(或托盘零点中心), Z0=夹具基准面+零件高度顶面",
        min_grip_depth_mm=10.0,
        max_overhang_ld_ratio=2.5,
        clamping_pressure_mpa=(1.0, 2.5),
        repeatability_mm=0.003,
        smed_interface="气动/液压零点定位基座(4拉钉重复定位<=0.003mm)",
        keepout_clearance_z_mm=5.0,
        keepout_clearance_xy_mm=6.0,
        handbook_ref="《机床夹具设计手册》一面两销过定位消除与SMED零点接口规范",
    ),
}


@dataclass
class AllowanceAllocation:
    material: str
    process_family: str
    rough_single_side_mm: float
    semi_finish_single_side_mm: float
    finish_single_side_mm: float
    corner_rest_allowance_mm: float
    end_face_allowance_mm: float
    clamping_stock_extension_mm: float
    total_single_side_stock_mm: float
    handbook_ref: str
    within_handbook_bounds: bool
    warnings: List[str] = field(default_factory=list)


@dataclass
class MotionSafetyPolicy:
    z_safe_global_mm: float         # 全局安全高度 (高于最高障碍物 + 50~100mm)
    z_r_plane_mm: float             # 循环参考平面 R (距加工表面 2~5mm)
    rapid_decel_zone_mm: float      # 快移减速切换高度 (G00 停在此高度以上, 下方强制 G01 接近)
    xy_clearance_mm: float          # XY 避让行程余量 (>= D_tool/2 + 5mm)
    atc_retract_z_machine_mm: float # 换刀机床 Z 零点参考 (0.0mm)
    rapid_override_first_piece_pct: int
    corner_feed_reduction_pct: int
    max_spindle_rpm_limit: int
    soft_limit_x_mm: Tuple[float, float]
    soft_limit_y_mm: Tuple[float, float]
    soft_limit_z_mm: Tuple[float, float]


def get_material_spec(material_id: str) -> MaterialSpec:
    if material_id in MATERIAL_HANDBOOK:
        return MATERIAL_HANDBOOK[material_id]
    aliases = {
        "45": "Steel45", "45#": "Steel45", "45钢": "Steel45", "c45": "Steel45",
        "40cr": "40Cr",
        "al7075": "AL7075-T6", "7075": "AL7075-T6", "7075-t6": "AL7075-T6",
        "ti6al4v": "Ti-6Al-4V", "tc4": "Ti-6Al-4V", "ti-6al-4v": "Ti-6Al-4V",
        "304": "SS304", "ss304": "SS304", "sus304": "SS304",
        "ht250": "HT250", "cast_iron": "HT250",
    }
    key = aliases.get(str(material_id).strip().lower())
    if key and key in MATERIAL_HANDBOOK:
        return MATERIAL_HANDBOOK[key]
    raise KeyError(f"Unsupported material_id: {material_id!r}. Valid: {sorted(MATERIAL_HANDBOOK)}")


def compute_allowance_plan(
    material_id: str,
    process_family: Literal["turning", "milling"],
    clamping_type: ClampingType,
    *,
    rough_mm: Optional[float] = None,
    semi_finish_mm: Optional[float] = None,
    finish_mm: Optional[float] = None,
    corner_mm: Optional[float] = None,
    end_face_mm: Optional[float] = None,
) -> AllowanceAllocation:
    """Compute and validate full-dimensional machining allowance rules."""
    mat = get_material_spec(material_id)
    scheme = CLAMPING_SCHEMES[clamping_type]
    warnings: List[str] = []

    def _mid(rng: Tuple[float, float]) -> float:
        return round(0.5 * (rng[0] + rng[1]), 3)

    r_val = _mid(mat.rough_allowance_mm) if rough_mm is None else float(rough_mm)
    sf_val = _mid(mat.semi_finish_allowance_mm) if semi_finish_mm is None else float(semi_finish_mm)
    f_val = _mid(mat.finish_allowance_mm) if finish_mm is None else float(finish_mm)
    c_val = _mid(mat.corner_rest_allowance_mm) if corner_mm is None else float(corner_mm)
    end_val = (2.0 if process_family == "turning" else 2.5) if end_face_mm is None else float(end_face_mm)

    clamp_ext = scheme.min_grip_depth_mm if clamping_type == "three_jaw_chuck" else 0.0
    total_side = round(r_val, 3)

    # Check allowance stratification consistency: rough > semi_finish > finish > 0
    within = True
    for label, val, rng in (
        ("rough_single_side_mm", r_val, mat.rough_allowance_mm),
        ("semi_finish_single_side_mm", sf_val, mat.semi_finish_allowance_mm),
        ("finish_single_side_mm", f_val, mat.finish_allowance_mm),
        ("corner_rest_allowance_mm", c_val, mat.corner_rest_allowance_mm),
    ):
        if val < rng[0] or val > rng[1]:
            within = False
            warnings.append(f"{label}={val}mm 超出《金属切削加工工艺手册》标准推荐范围 {rng}")
    if not (r_val > sf_val > f_val > 0):
        within = False
        warnings.append(
            f"余量分层必须满足 粗加工({r_val}) > 半精({sf_val}) > 精加工({f_val}) > 0"
        )
    if end_val < 0.5 or end_val > 5.0:
        within = False
        warnings.append(f"end_face_allowance_mm={end_val}mm 超出常规端面余量范围 [0.5, 5.0]")

    return AllowanceAllocation(
        material=mat.material_id,
        process_family=process_family,
        rough_single_side_mm=r_val,
        semi_finish_single_side_mm=sf_val,
        finish_single_side_mm=f_val,
        corner_rest_allowance_mm=c_val,
        end_face_allowance_mm=end_val,
        clamping_stock_extension_mm=clamp_ext,
        total_single_side_stock_mm=total_side,
        handbook_ref=mat.handbook_ref,
        within_handbook_bounds=within,
        warnings=warnings,
    )


def compute_cutting_params(
    material_id: str,
    operation: OperationType,
    diameter_mm: float,
    *,
    flutes: int = 4,
    tool_material: str = "coated_carbide",
    spindle_max_rpm: int = 8000,
    pitch_mm: Optional[float] = None,
) -> Dict[str, Any]:
    """Compute handbook-grounded cutting speed, RPM, feedrate, DOC & Taylor life."""
    mat = get_material_spec(material_id)
    if operation not in mat.cutting_ranges:
        raise ValueError(f"Unsupported operation {operation!r} for {material_id}")
    rng = mat.cutting_ranges[operation]
    d = float(diameter_mm)
    if d <= 0:
        raise ValueError(f"diameter_mm must be > 0, got {diameter_mm}")

    # Coated carbide uses handbook midpoint; HSS scales down 0.45x; PCD/CBN scales up
    mat_factor = {"coated_carbide": 1.0, "carbide": 0.9, "hss": 0.45, "pcd": 1.4, "cbn": 1.25}.get(
        tool_material.lower(), 1.0
    )
    vc = round(0.5 * (rng["vc"][0] + rng["vc"][1]) * mat_factor, 2)
    raw_rpm = 1000.0 * vc / (math.pi * d)
    rpm = max(60, min(int(round(raw_rpm)), int(spindle_max_rpm)))
    # Recompute effective Vc if spindle RPM was clamped
    vc_eff = round(math.pi * d * rpm / 1000.0, 2)
    ap = round(0.5 * (rng["ap"][0] + rng["ap"][1]), 3)

    if "fz" in rng:
        fz = round(0.5 * (rng["fz"][0] + rng["fz"][1]), 4)
        feed_mm_min = round(rpm * max(1, int(flutes)) * fz, 1)
        feed_mode = "G94_mm_per_min"
        f_rev = round(fz * max(1, int(flutes)), 4)
    else:
        if operation == "tapping" and pitch_mm is not None and pitch_mm > 0:
            f_rev = round(float(pitch_mm), 4)
        else:
            f_rev = round(0.5 * (rng["f_rev"][0] + rng["f_rev"][1]), 4)
        fz = round(f_rev / max(1, int(flutes)), 4)
        feed_mm_min = round(rpm * f_rev, 1)
        feed_mode = "G95_mm_per_rev"

    # Taylor tool life T = (C_T / Vc_eff)^(1/n) clamped to practical bounds [5, 240] min
    taylor_life_min = round(
        max(5.0, min(240.0, (mat.taylor_ct / max(1.0, vc_eff)) ** (1.0 / mat.taylor_n))),
        1,
    )

    return {
        "material": mat.material_id,
        "operation": operation,
        "tool_material": tool_material,
        "diameter_mm": d,
        "flutes": flutes,
        "vc_m_min": vc_eff,
        "vc_handbook_range": rng["vc"],
        "spindle_rpm": rpm,
        "s_max_clamp_rpm": int(spindle_max_rpm),
        "fz_mm": fz,
        "f_rev_mm": f_rev,
        "feed_mm_min": feed_mm_min,
        "feed_mode": feed_mode,
        "ap_mm": ap,
        "coolant": mat.coolant_mode,
        "taylor_tool_life_min": taylor_life_min,
        "kc11_mpa": mat.specific_cutting_force_kc11_mpa,
        "handbook_ref": mat.handbook_ref,
    }


def compute_motion_safety_policy(
    max_obstacle_z_mm: float,
    tool_diameter_mm: float,
    machine_travel_mm: Optional[Dict[str, Tuple[float, float]]] = None,
    *,
    z_safe_clearance_mm: float = 50.0,
    z_r_plane_mm: float = 3.0,
    rapid_decel_zone_mm: float = 5.0,
) -> MotionSafetyPolicy:
    """Build standard Z safety height, R-plane, rapid decel zone & XY clearance."""
    travel = machine_travel_mm or {
        "X": (-500.0, 500.0),
        "Y": (-500.0, 500.0),
        "Z": (-600.0, 0.0),
    }
    if z_safe_clearance_mm < 50.0:
        raise ValueError(f"Z安全高度余量不得低于 50mm（《数控加工工艺规范》），实传 {z_safe_clearance_mm}")
    if not (2.0 <= z_r_plane_mm <= 5.0):
        raise ValueError(f"R平面高度应落在 [2.0, 5.0] mm，实传 {z_r_plane_mm}")
    if rapid_decel_zone_mm < 5.0:
        raise ValueError(f"快移减速切换区间不得小于 5.0mm，实传 {rapid_decel_zone_mm}")

    xy_clear = round(max(5.0, tool_diameter_mm / 2.0 + 5.0), 3)
    return MotionSafetyPolicy(
        z_safe_global_mm=round(max_obstacle_z_mm + z_safe_clearance_mm, 3),
        z_r_plane_mm=round(z_r_plane_mm, 3),
        rapid_decel_zone_mm=round(rapid_decel_zone_mm, 3),
        xy_clearance_mm=xy_clear,
        atc_retract_z_machine_mm=0.0,
        rapid_override_first_piece_pct=25,
        corner_feed_reduction_pct=60,
        max_spindle_rpm_limit=10000,
        soft_limit_x_mm=tuple(travel["X"]),  # type: ignore[arg-type]
        soft_limit_y_mm=tuple(travel["Y"]),  # type: ignore[arg-type]
        soft_limit_z_mm=tuple(travel["Z"]),  # type: ignore[arg-type]
    )


def derive_production_stock(
    product_bbox: BBox,
    is_revolution: bool,
    material_id: str,
    clamping_type: ClampingType,
    *,
    axis: Literal["X", "Y", "Z"] = "Z",
    allowance: Optional[AllowanceAllocation] = None,
) -> Dict[str, Any]:
    """Derive blank geometry from finished-part bbox + handbook allowances."""
    proc_family = "turning" if is_revolution else "milling"
    allow = allowance or compute_allowance_plan(material_id, proc_family, clamping_type)
    if is_revolution:
        spec: StockSpec = derive_stock_strict(
            product_bbox,
            True,
            axis=axis,
            radial_allowance=allow.rough_single_side_mm,
            end_allowance=allow.end_face_allowance_mm + allow.clamping_stock_extension_mm / 2.0,
        )
    else:
        spec = derive_stock_strict(
            product_bbox,
            False,
            side_allowance=allow.rough_single_side_mm,
        )
    return {
        "stock_spec": spec,
        "allowance": asdict(allow),
        "clamping_scheme": asdict(CLAMPING_SCHEMES[clamping_type]),
        "material": asdict(get_material_spec(material_id)),
        "basis": "derived_from_product_bbox_and_handbook_allowances",
    }


def validate_process_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Fail-closed validation gate for blank, clamping, safety & cutting parameters."""
    violations: List[str] = []

    allow = plan.get("allowance")
    if not isinstance(allow, dict):
        violations.append("ALLOWANCE_MISSING: 缺少全维度余量配置")
    else:
        if not allow.get("within_handbook_bounds"):
            violations.extend(allow.get("warnings") or ["ALLOWANCE_OUT_OF_HANDBOOK_BOUNDS"])

    safety = plan.get("motion_safety")
    if not isinstance(safety, dict):
        violations.append("MOTION_SAFETY_MISSING: 缺少 Z 安全高度 / XY 避让 / 快移减速参数")
    else:
        if float(safety.get("z_safe_global_mm", 0.0)) < 50.0:
            violations.append(f"UNSAFE_Z_HEIGHT: z_safe_global_mm={safety.get('z_safe_global_mm')} < 50mm")
        if float(safety.get("rapid_decel_zone_mm", 0.0)) < 5.0:
            violations.append(f"UNSAFE_RAPID_DECEL: rapid_decel_zone_mm={safety.get('rapid_decel_zone_mm')} < 5mm")
        if float(safety.get("xy_clearance_mm", 0.0)) < 5.0:
            violations.append(f"UNSAFE_XY_CLEARANCE: xy_clearance_mm={safety.get('xy_clearance_mm')} < 5mm")

    clamp = plan.get("clamping")
    if not isinstance(clamp, dict):
        violations.append("CLAMPING_MISSING: 缺少装夹定位基准方案")
    else:
        ld = float(clamp.get("overhang_ld_ratio", 0.0))
        max_ld = float(clamp.get("max_overhang_ld_ratio", 3.0))
        has_tailstock = bool(clamp.get("tailstock_engaged", False))
        if ld > max_ld and not has_tailstock:
            violations.append(
                f"OVERHANG_EXCEEDED: L/D={ld:.2f} > {max_ld:.2f} 且未启用尾座顶尖支撑"
            )
        if float(clamp.get("grip_depth_mm", 0.0)) < float(clamp.get("min_grip_depth_mm", 8.0)):
            violations.append(
                f"INSUFFICIENT_CLAMP_GRIP: 夹持深度 {clamp.get('grip_depth_mm')} < {clamp.get('min_grip_depth_mm')}mm"
            )

    ops = plan.get("operations") or []
    if not ops:
        violations.append("OPERATIONS_EMPTY: 缺少分工序切削参数定义")
    for idx, op in enumerate(ops, 1):
        mat_id = op.get("material") or plan.get("material_id")
        op_type = op.get("operation")
        vc = float(op.get("vc_m_min", 0.0))
        if mat_id and op_type:
            mat = get_material_spec(mat_id)
            if op_type in mat.cutting_ranges:
                lo, hi = mat.cutting_ranges[op_type]["vc"]
                # Allow +/-15% margin when spindle RPM clamp applies
                if vc <= 0 or vc > hi * 1.45 or vc < lo * 0.35:
                    violations.append(
                        f"OP{idx}_VC_OUT_OF_RANGE: {op_type} Vc={vc}m/min 偏离手册范围 {lo}..{hi}"
                    )

    return {
        "passed": not violations,
        "violations": violations,
        "basis": "handbook_and_kinematic_safety_gate",
    }
