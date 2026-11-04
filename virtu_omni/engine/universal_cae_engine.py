# -*- coding: utf-8 -*-
"""universal_cae_engine.py — 全通用物理力学有限元分析与安全系数 (FOS >= 1.5) 自愈闭环引擎.

核心能力：
1. 多构件族力学仿真模型：
   - 回转轴/厚壁套筒：Lamé 厚壁圆筒弹性力学 + von Mises 等效应力求解
   - 法兰盘：Timoshenko 环形圆板弯曲力学 + 螺栓预紧工况内压力分析
   - 轴承支座：立柱弯剪组合应力 + 悬臂弯曲挠度核算
   - 钣金件：弯曲极限弯矩与回弹角 (Springback) 补偿计算
2. 极限自愈与闭环公理 (Closed-Loop FOS Assertion & Self-Healing)：
   - 当安全系数 FOS < 1.5 时，严禁直接放行或抛出未捕获错误；
   - 自动反求达标所需最小安全特征尺寸 (壁厚 t_min / 法兰厚度 T_min / 圆角 r_min)；
   - 触发 Reflexion 几何参数自愈调整，使得 FOS >= 1.6，完成自适应工程闭环。
"""

from __future__ import annotations
import math
import json
from typing import Dict, Any, Tuple, Optional
from dataclasses import dataclass, asdict

from virtu_omni.engine.universal_geometry_engine import PartFamily


@dataclass
class MaterialProperties:
    """机械工程材料物理与力学属性。"""
    name: str
    density_g_cm3: float
    yield_strength_mpa: float
    tensile_strength_mpa: float
    elastic_modulus_gpa: float
    poisson_ratio: float


STANDARD_MATERIALS: Dict[str, MaterialProperties] = {
    "Cr12MoV": MaterialProperties(
        name="冷作模具钢 Cr12MoV",
        density_g_cm3=7.75,
        yield_strength_mpa=850.0,
        tensile_strength_mpa=1100.0,
        elastic_modulus_gpa=210.0,
        poisson_ratio=0.28
    ),
    "Ti-6Al-4V": MaterialProperties(
        name="钛合金 TC4 (Ti-6Al-4V)",
        density_g_cm3=4.43,
        yield_strength_mpa=880.0,
        tensile_strength_mpa=950.0,
        elastic_modulus_gpa=114.0,
        poisson_ratio=0.34
    ),
    "AL7075-T6": MaterialProperties(
        name="超硬航空铝 7075-T6",
        density_g_cm3=2.81,
        yield_strength_mpa=503.0,
        tensile_strength_mpa=572.0,
        elastic_modulus_gpa=71.7,
        poisson_ratio=0.33
    ),
    "Steel45": MaterialProperties(
        name="优质碳素结构钢 45#",
        density_g_cm3=7.85,
        yield_strength_mpa=355.0,
        tensile_strength_mpa=600.0,
        elastic_modulus_gpa=206.0,
        poisson_ratio=0.29
    ),
    "SS304": MaterialProperties(
        name="奥氏体不锈钢 304",
        density_g_cm3=7.93,
        yield_strength_mpa=205.0,
        tensile_strength_mpa=515.0,
        elastic_modulus_gpa=193.0,
        poisson_ratio=0.30
    ),
    "Q235B": MaterialProperties(
        name="碳素结构钢 Q235B",
        density_g_cm3=7.85,
        yield_strength_mpa=235.0,
        tensile_strength_mpa=400.0,
        elastic_modulus_gpa=200.0,
        poisson_ratio=0.28
    ),
}

MATERIAL_ALIASES: Dict[str, str] = {
    "45号钢": "Steel45", "45#钢": "Steel45", "45": "Steel45", "steel45": "Steel45",
    "q235": "Q235B", "q235b": "Q235B", "304": "SS304", "ss304": "SS304",
    "tc4": "Ti-6Al-4V", "ti6al4v": "Ti-6Al-4V", "7075": "AL7075-T6",
    "cr12mov": "Cr12MoV",
}

DEFAULT_MATERIAL_KEY = "Cr12MoV"


def resolve_material(key: Optional[str]):
    """把材料名解析到 STANDARD_MATERIALS；解析失败返回 (None, 可选键)。绝不静默换料。"""
    raw = "" if key is None else str(key).strip()
    if raw in STANDARD_MATERIALS:
        return STANDARD_MATERIALS[raw], sorted(STANDARD_MATERIALS)
    norm = raw.lower().replace(" ", "").replace("-", "").replace("_", "")
    hit = MATERIAL_ALIASES.get(norm) or MATERIAL_ALIASES.get(raw)
    if hit:
        return STANDARD_MATERIALS[hit], sorted(STANDARD_MATERIALS)
    return None, sorted(STANDARD_MATERIALS)



class UniversalCAEEngine:
    """通用力学仿真、安全系数闭环核验与自动强化引擎。"""

    TARGET_FOS = 1.5           # 工程准入最低安全系数
    OPTIMIZED_FOS = 1.65       # 自动修复目标安全系数

    @staticmethod
    def _normalize_loads(load_params: Dict[str, Any]) -> Dict[str, Any]:
        """把工具层传入的 load_n / torque_nm 接到各构件族真正读取的键上。"""
        lp = dict(load_params)
        if "load_n" in lp:
            lp.setdefault("radial_load_n", lp["load_n"])
            lp.setdefault("bending_force_n", lp["load_n"])
        return lp

    def analyze_and_optimize(self, intent_data: Dict[str, Any], load_params: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        """全自动力学仿真核查，并在不达标时自动自愈调整几何尺寸。"""
        family = intent_data.get("family", PartFamily.ROTATIONAL_SHAFT.value)
        spec = dict(intent_data.get("spec", {}))
        mat_key = spec.get("material")
        mat, known_keys = resolve_material(mat_key if mat_key is not None else DEFAULT_MATERIAL_KEY)
        if mat is None:
            return {
                "status": "blocked",
                "verdict_code": "MATERIAL_UNRESOLVED",
                "material_arg": mat_key,
                "accepted_materials": known_keys,
                "needs_reinforcement": False,
                "verdict": "材料 %s 不在可用表内，拒绝用默认材料代算安全系数" % mat_key,
            }

        load_params = self._normalize_loads(load_params or {})

        # 1. 初始工况应力求解
        initial_res = self._compute_stress_and_fos(family, spec, mat, load_params)
        fos = initial_res["factor_of_safety"]

        # 2. 安全闭环核验：如果 FOS >= 1.5，直接合格
        if fos >= self.TARGET_FOS:
            return {
                "status": "passed",
                "family": family,
                "material": mat.name,
                "yield_strength_mpa": mat.yield_strength_mpa,
                "von_mises_stress_mpa": initial_res["von_mises_stress_mpa"],
                "factor_of_safety": fos,
                "required_fos": self.TARGET_FOS,
                "needs_reinforcement": False,
                "optimized_spec": spec,
                "verdict": f"CAE 力学仿真合格：von Mises 应力 {initial_res['von_mises_stress_mpa']:.1f} MPa, FOS = {fos:.2f} >= 1.5"
            }

        if family == PartFamily.SHEET_METAL_BEND.value:
            return {
                "status": "formability_advisory",
                "family": family,
                "material": mat.name,
                "yield_strength_mpa": mat.yield_strength_mpa,
                "von_mises_stress_mpa": initial_res["von_mises_stress_mpa"],
                "factor_of_safety": fos,
                "required_fos": self.TARGET_FOS,
                "needs_reinforcement": False,
                "optimized_spec": spec,
                "verdict": "铆金柏的 FOS 是折弯成形性指标（外层纤维是否屈服），不是强度安全系数；FOS < 1.5 说明该内弧半径/板厚比下折弯必然塑性变形，应走弯半径与回弹补偿，禁止按强度闸自愈改几何。"
            }

        # 3. 不达标自愈强化 (Self-Healing Reinforcement)
        reinforced_spec, healed_res = self._self_heal_geometry(family, spec, mat, load_params, initial_res)
        healed_fos = healed_res["factor_of_safety"]
        healed = healed_fos >= self.TARGET_FOS

        return {
            "status": "optimized" if healed else "not_healed",
            "family": family,
            "material": mat.name,
            "yield_strength_mpa": mat.yield_strength_mpa,
            "initial_stress_mpa": initial_res["von_mises_stress_mpa"],
            "initial_fos": fos,
            "factor_of_safety": healed_fos,
            "required_fos": self.TARGET_FOS,
            "needs_reinforcement": True,
            "healed_to_target": healed,
            "reinforcement_applied": healed_res["reinforcement_action"],
            "optimized_spec": reinforced_spec,
            "verdict": (f"已触发闭环自愈强化：FOS 从 {fos:.2f} 强化至 {healed_fos:.2f} (>= {self.TARGET_FOS:.2f})") if healed else (f"自愈后 FOS = {healed_fos:.2f} 仍低于 {self.TARGET_FOS:.2f}，几何自愈无法达标，需改材料/工艺或重新设计，禁止放行")
        }

    def _compute_stress_and_fos(self, family: str, spec: Dict[str, Any], mat: MaterialProperties, loads: Dict[str, float]) -> Dict[str, Any]:
        """根据构件族计算最大等效应力与安全系数。"""
        if family == PartFamily.FLANGE_PLATE.value:
            return self._analyze_flange_plate(spec, mat, loads)
        elif family == PartFamily.BEARING_BRACKET.value:
            return self._analyze_bearing_bracket(spec, mat, loads)
        elif family == PartFamily.SHEET_METAL_BEND.value:
            return self._analyze_sheet_metal(spec, mat, loads)
        else:
            return self._analyze_cylindrical_shaft(spec, mat, loads)

    def _analyze_cylindrical_shaft(self, spec: Dict[str, Any], mat: MaterialProperties, loads: Dict[str, float]) -> Dict[str, Any]:
        """厚壁套筒 Lamé 公式分析。"""
        d_out = float(spec.get("d_outer", 53.0))
        d_in = float(spec.get("d_inner", 14.0))
        p_in = loads.get("internal_pressure_mpa", 45.0)  # 默认 45 MPa 高压工况

        r_o = d_out / 2.0
        r_i = d_in / 2.0
        if r_i >= r_o:
            r_i = r_o * 0.5

        # Lamé 内壁最大环向应力与径向压应力
        sigma_t = p_in * (r_o**2 + r_i**2) / (r_o**2 - r_i**2)
        sigma_r = -p_in
        # 扭矩引入剪应力：T 由 N·m 转 N·mm，空心轴 J = pi/2*(ro^4-ri^4)
        t_nm = float(loads.get("torque_nm", 0.0))
        tau = 0.0
        if t_nm:
            j_pol = math.pi * (r_o**4 - r_i**4) / 2.0
            tau = (t_nm * 1000.0) * r_o / max(1.0, j_pol)
        sigma_vm = math.sqrt(sigma_t**2 - sigma_t * sigma_r + sigma_r**2 + 3.0 * tau**2)
        fos = mat.yield_strength_mpa / max(1.0, sigma_vm)

        return {
            "von_mises_stress_mpa": round(sigma_vm, 2),
            "factor_of_safety": round(fos, 2)
        }

    def _analyze_flange_plate(self, spec: Dict[str, Any], mat: MaterialProperties, loads: Dict[str, float]) -> Dict[str, Any]:
        """Timoshenko 环形法兰板螺栓弯曲应力分析。"""
        d_out = float(spec.get("d_outer", 120.0))
        d_in = float(spec.get("d_inner", 40.0))
        thick = float(spec.get("thickness", 18.0))
        pcd = float(spec.get("pcd", 90.0))
        n_bolts = int(spec.get("bolt_hole_count", 4))
        p_fluid = loads.get("fluid_pressure_mpa", 16.0)  # 16 MPa 法兰公称压力

        # 内压在受载面积上产生的总推力
        total_thrust_n = p_fluid * (math.pi * (d_in / 2.0)**2)
        # 预紧与操作合力在螺栓圆环上施加的弯矩
        moment_arm = (pcd - d_in) / 2.0
        bending_moment = (total_thrust_n * 1.5 * moment_arm) / (math.pi * d_out)
        
        # 环板弯曲截面模量 W_z = (1/6) * b * t^2
        sigma_bend = (6.0 * bending_moment) / (thick**2)
        sigma_vm = sigma_bend
        fos = mat.yield_strength_mpa / max(1.0, sigma_vm)

        return {
            "von_mises_stress_mpa": round(sigma_vm, 2),
            "factor_of_safety": round(fos, 2)
        }

    def _analyze_bearing_bracket(self, spec: Dict[str, Any], mat: MaterialProperties, loads: Dict[str, float]) -> Dict[str, Any]:
        """轴承立式支座弯剪组合应力分析。"""
        h = float(spec.get("center_height", 50.0))
        t_b = float(spec.get("base_thickness", 14.0))
        w = float(spec.get("base_width", 60.0))
        t_rib = float(spec.get("rib_thickness", 8.0))
        radial_load_n = loads.get("radial_load_n", 12000.0)  # 12 kN 轴承动载荷

        # 弯矩 M = F * H
        m_bend = radial_load_n * h
        # 截面模量近似 (肋板 + 立柱)
        eff_width = max(t_rib * 2.0, w * 0.4)
        w_section = (eff_width * h**2) / 6.0
        sigma_b = m_bend / max(1.0, w_section)
        # 剪应力 tau = F / A
        tau = radial_load_n / max(1.0, eff_width * h)
        sigma_vm = math.sqrt(sigma_b**2 + 3.0 * tau**2)
        fos = mat.yield_strength_mpa / max(1.0, sigma_vm)

        return {
            "von_mises_stress_mpa": round(sigma_vm, 2),
            "factor_of_safety": round(fos, 2)
        }

    def _analyze_sheet_metal(self, spec: Dict[str, Any], mat: MaterialProperties, loads: Dict[str, float]) -> Dict[str, Any]:
        """钣金折弯部位极限塑性与弹性应力。"""
        t = float(spec.get("sheet_thickness", 2.0))
        r = float(spec.get("inner_bend_radius", 2.0))
        bending_force_n = loads.get("bending_force_n", 500.0)
        # 弯曲外层纤维应力
        sigma_fiber = (mat.elastic_modulus_gpa * 1e3 * (t / 2.0)) / (r + t / 2.0)
        sigma_vm = min(mat.yield_strength_mpa * 1.2, sigma_fiber)
        fos = mat.yield_strength_mpa / max(1.0, sigma_vm)
        return {
            "von_mises_stress_mpa": round(sigma_vm, 2),
            "factor_of_safety": round(fos, 2)
        }

    def _self_heal_geometry(self, family: str, spec: Dict[str, Any], mat: MaterialProperties,
                            loads: Dict[str, float], initial_res: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """执行针对性自愈几何增厚调整，直到 FOS >= OPTIMIZED_FOS。"""
        new_spec = dict(spec)
        target_fos = self.OPTIMIZED_FOS
        ratio = target_fos / max(0.1, initial_res["factor_of_safety"])

        action = ""
        if family == PartFamily.FLANGE_PLATE.value:
            old_thick = float(new_spec.get("thickness", 18.0))
            # 法兰厚度与应力平方反比：sigma ~ 1 / thick^2
            new_thick = round(old_thick * math.sqrt(ratio), 1)
            new_spec["thickness"] = max(old_thick + 2.0, new_thick)
            action = f"法兰盘基体厚度从 {old_thick}mm 增厚强化至 {new_spec['thickness']}mm"
        elif family == PartFamily.BEARING_BRACKET.value:
            old_rib = float(new_spec.get("rib_thickness", 8.0))
            new_rib = round(old_rib * ratio, 1)
            new_spec["rib_thickness"] = max(old_rib + 2.0, new_rib)
            action = f"轴承支座加强筋厚度从 {old_rib}mm 强化至 {new_spec['rib_thickness']}mm"
        else:
            old_d_out = float(new_spec.get("d_outer", 53.0))
            old_d_in = float(new_spec.get("d_inner", 14.0))
            # 增加壁厚：外径适度增大
            wall = (old_d_out - old_d_in) / 2.0
            new_wall = wall * ratio
            new_d_out = round(old_d_in + 2.0 * new_wall, 1)
            new_spec["d_outer"] = max(old_d_out + 4.0, new_d_out)
            action = f"套筒外径从 {old_d_out}mm 增加至 {new_spec['d_outer']}mm 以增强承压壁厚"

        healed_res = self._compute_stress_and_fos(family, new_spec, mat, loads)
        healed_res["reinforcement_action"] = action
        return new_spec, healed_res
