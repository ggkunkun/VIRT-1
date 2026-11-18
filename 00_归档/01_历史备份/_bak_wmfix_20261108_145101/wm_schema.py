#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""wm_schema.py — 世界模型结构化输出约束（Ollama format=JSON Schema）

把「键名 + 类型 + 语法合法性」从概率问题变成解码期保证（仓库计划 P2-2）。
提供：
  - WIDE_SCHEMA   ：全族字段并集，族中立，生产默认用
  - FAMILY_SCHEMA ：按族收紧（评测上界探针用）
  - LITE_SYSTEM   ：精简铁律 system（约 300 字），替代冗长契约以节省 prefill
"""
from __future__ import annotations

# 全族 world_state 字段白名单（键名唯一真源，与 build_worldmodel_sft 的生成器对齐）
NUM_FIELDS = [
    "material_removed_mm3", "mrr_mm3_per_min", "removed_mass_g", "resulting_mass_g",
    "delta_volume_mm3", "feed_per_rev_mm", "nose_radius_mm", "surface_roughness_ra_um",
    "yield_strength_mpa", "peak_von_mises_mpa", "safety_factor",
    "safe_plane_z_mm", "rapid_min_z_mm", "stock_top_z_mm",
    "closed_loop_worstcase_halfwidth_mm", "closed_loop_rss_halfwidth_mm",
    "basic_size_mm", "fit_clearance_mm",
    "feature_volume_mm3", "before_volume_mm3", "after_volume_mm3",
    "volume_mm3", "mass_g", "inertia_ixx_mm4", "inertia_izz_mm4",
    # v2 三族（process / design / adapt_machine）+ adapt_material 补齐：
    # 此前白名单只覆盖 v1 8 族，family_schema() 对 v2 族取不到字段，
    # 结构化输出约束退化成"整宽不限"，模型自造键名无人拦。
    "spindle_rpm", "feed_rate_mm_per_min", "cut_time_min",
    "mass_kg", "outer_dia_mm", "bore_dia_mm", "thickness_mm",
    "bolt_count", "bolt_dia_mm", "pcd_mm",
    "required_spindle_rpm", "machine_max_rpm", "recommended_vc_m_per_min",
]
STR_FIELDS = {
    "volume_conservation": ["pass", "fail", "pass_cut_negative"],
    "finish_class": ["精加工", "半精", "粗加工"],
    "material": ["45钢", "铝合金6061", "不锈钢304", "钛合金TC4", "黄铜H62"],
    # 闸门字面双轨历史包袱：wm_gate/wm_schema 出长字面，wm_contract/guard 出短字面。
    # wm_contract.normalize_gate 已做长短互认，但 JSON Schema 枚举此前只列长字面，
    # 与 KEY_SCHEMA 下发的 "pass/fail" 直接矛盾（同一份契约自相矛盾）。
    # 修复口径：枚举取并集，长短均合法，归一交给 normalize_gate。
    "fos_gate": ["pass", "fail", "FOS>=1.5_pass", "FOS<1.5_FAIL"],
    "collision_risk": ["high", "none", "low", "medium"],
    "autodiff": ["red", "yellow", "green"],
    "tolerance_fit": ["间隙配合", "过盈配合", "过渡配合"],
    "fit_class": ["H7/g6", "H7/p6", "H7/js6"],
    "shape": ["box", "cylinder"],
    "feature": ["通孔", "沉槽", "键槽", "倒角"],
    "solver": ["analytic_csg"],
}
BOOL_FIELDS = ["gouge", "tolerance_pass"]
ARR_FIELDS = ["component_tolerances_mm", "centroid_mm"]


def _ws_props():
    p = {k: {"type": "number"} for k in NUM_FIELDS}
    for k, en in STR_FIELDS.items():
        p[k] = {"type": "string", "enum": en}
    for k in BOOL_FIELDS:
        p[k] = {"type": "boolean"}
    for k in ARR_FIELDS:
        p[k] = {"type": "array", "items": {"type": "number"}}
    return p


def wide_schema():
    return {
        "type": "object",
        "properties": {
            "world_state": {
                "type": ["object", "null"],
                "properties": _ws_props(),
                "additionalProperties": False,
            },
            "derivation": {"type": "object", "additionalProperties": {"type": "string"}},
            "invalid": {"type": "boolean"},
            "reason": {"type": "string"},
            "verification": {"type": "object"},
        },
        "required": ["world_state"],
        "additionalProperties": False,
    }


FAMILY_FIELDS = {
    "removal": ["material_removed_mm3", "mrr_mm3_per_min", "removed_mass_g", "resulting_mass_g",
                "delta_volume_mm3", "volume_conservation"],
    "roughness": ["feed_per_rev_mm", "nose_radius_mm", "surface_roughness_ra_um", "finish_class"],
    "fea_fos": ["material", "yield_strength_mpa", "peak_von_mises_mpa", "safety_factor", "fos_gate"],
    "collision": ["safe_plane_z_mm", "rapid_min_z_mm", "stock_top_z_mm", "collision_risk", "gouge", "autodiff"],
    "tolerance": ["component_tolerances_mm", "closed_loop_worstcase_halfwidth_mm",
                  "closed_loop_rss_halfwidth_mm", "basic_size_mm", "fit_clearance_mm",
                  "tolerance_fit", "fit_class", "tolerance_pass"],
    "geom_delta": ["feature", "feature_volume_mm3", "delta_volume_mm3", "before_volume_mm3",
                   "after_volume_mm3", "volume_conservation"],
    "mass_props": ["shape", "volume_mm3", "mass_g", "centroid_mm", "inertia_ixx_mm4",
                   "inertia_izz_mm4", "solver"],
    "process": ["spindle_rpm", "feed_rate_mm_per_min", "mrr_mm3_per_min",
                "surface_roughness_ra_um", "cut_time_min"],
    "design": ["volume_mm3", "mass_g", "mass_kg", "outer_dia_mm", "bore_dia_mm",
               "thickness_mm", "bolt_count", "bolt_dia_mm", "pcd_mm"],
    "adapt_machine": ["required_spindle_rpm", "machine_max_rpm",
                      "recommended_vc_m_per_min"],
    "adapt_material": ["yield_strength_mpa", "peak_von_mises_mpa", "safety_factor",
                       "fos_gate"],
    "invalid": [],
}


REQUIRED_FIELDS = {
    "removal": ["material_removed_mm3", "mrr_mm3_per_min", "removed_mass_g", "resulting_mass_g", "delta_volume_mm3"],
    "roughness": ["surface_roughness_ra_um", "finish_class"],
    "fea_fos": ["safety_factor", "fos_gate"],
    "collision": ["safe_plane_z_mm", "rapid_min_z_mm", "stock_top_z_mm", "collision_risk", "gouge", "autodiff"],
    "tolerance": ["closed_loop_worstcase_halfwidth_mm", "closed_loop_rss_halfwidth_mm",
                  "fit_clearance_mm", "tolerance_fit", "fit_class", "tolerance_pass"],
    "geom_delta": ["delta_volume_mm3", "before_volume_mm3", "after_volume_mm3", "volume_conservation"],
    "mass_props": ["volume_mm3", "mass_g", "centroid_mm", "inertia_ixx_mm4", "inertia_izz_mm4"],
    "process": ["spindle_rpm", "feed_rate_mm_per_min", "mrr_mm3_per_min",
                "surface_roughness_ra_um", "cut_time_min"],
    "design": ["volume_mm3", "mass_g", "mass_kg"],
    "adapt_machine": ["required_spindle_rpm"],
    "adapt_material": ["safety_factor", "fos_gate"],
    "invalid": [],
}


def family_schema(fam: str):
    s = wide_schema()
    fields = FAMILY_FIELDS.get(fam)
    if fields is not None:
        allp = _ws_props()
        s["properties"]["world_state"]["properties"] = {k: allp[k] for k in fields}
        req = [k for k in REQUIRED_FIELDS.get(fam, []) if k in fields]
        if req:
            s["properties"]["world_state"]["required"] = req
    return s


# 族级公式卡（deprecated: 仅作为"契约内"评测臂，生产应改由求解器复算）
FAMILY_CARD = {
    "removal": "本族：material_removed_mm3=DOC*WOC*L；mrr_mm3_per_min=DOC*WOC*vf；removed_mass_g=V_removed*rho(g/cm3)/1000；resulting_mass_g=stock_mass-removed_mass；delta_volume_mm3=-V_removed。",
    "roughness": "本族：surface_roughness_ra_um=1000*f*f/(8*r_eps)，f 为每转进给（不除以 2），r_eps 为刀尖圆弧半径。",
    "fea_fos": "本族：safety_factor=Sy/von_Mises；fos_gate 按 1.5 阈值。",
    "collision": "本族必须填全三个 Z 值：safe_plane_z_mm、rapid_min_z_mm、stock_top_z_mm（照抄题面）。判定必须按顺序做两个比较，且两个条件**同时成立**才算 high：条件① rapid_min < safe_plane；条件② rapid_min < stock_top+1。只满足其中一个 → collision_risk=none。gouge=(rapid_min<stock_top)。autodiff：gouge 为真→red；否则 risk=high→yellow；否则 green。注意 rapid_min 只要不低于 stock_top+1 就没有穿透毛坯，即使低于安全平面也不是 high。",
    "tolerance": "本族：closed_loop_worstcase_halfwidth_mm=sum(ti)（把各分量公差**直接相加**，不是平方和）；closed_loop_rss_halfwidth_mm=sqrt(sum(ti^2))（平方和再开根）；fit_clearance_mm=上偏差-下偏差；tolerance_fit 按间隙正负。自检不等式：worstcase 必须**大于** rss（各分量全为正时恒成立），若算出 worstcase<=rss 说明把两个公式用混了，必须重算。",
    "geom_delta": "本族：delta_volume_mm3=-feature_volume_mm3；after_volume_mm3=before_volume_mm3+delta_volume_mm3；before_volume_mm3 照抄题面。",
    "mass_props": "本族：**先用分步乘法算体积再写结果**（先算底面积，再乘高；π 取 3.14159），禁止一步心算：圆柱 volume_mm3=pi*r^2*h、长方体=l*w*h。**复合形状必须先减料**——先按外轮廓算实心体积，再逐项减去所有孔/切槽/切角/台阶的体积（圆柱上切掉一段方料、方料上挖孔，都必须减），净体积才是 volume_mm3；圆柱 volume_mm3=pi*r^2*h、惯性矩为截面二次矩（面积惯性矩 mm^4）：inertia_ixx_mm4=pi*r^4/4、inertia_izz_mm4=pi*r^4/2；长方体 volume=l*w*h、Ixx=w*h^3/12、Izz=l*w^3/12；centroid 为净几何形心坐标 [x,y,z]；mass_g=净 volume_mm3*rho(g/cm3)/1000。",
    "invalid": "本族：输入非法或关键参数缺失时 world_state=null、invalid=true、reason 指出缺什么，禁止猜数值。",
    # v2 三族 + adapt_material 定律卡：此前只写 v1 8 族，card_system() 对这四族返回空串，
    # 模型在 card 模式下拿不到公式，只能凭记忆编（Ra 恒 1.6/3.2 的同源缺陷）。
    "process": "本族：spindle_rpm=1000*vc/(pi*D)；feed_rate_mm_per_min=f*n（f 为每转进给，单位 mm/r）；mrr_mm3_per_min=ap*f*vc*1000；surface_roughness_ra_um=1000*f*f/(8*r_eps)；cut_time_min=切削长度/feed。只用题面给定数值，禁止套用记忆中某材料的「标准转速」。",
    "design": "本族：先算净体积再乘密度——volume_mm3=pi*(r_out^2-r_bore^2)*t - n*pi*r_hole^2*t（管类零件带 n 个径向孔时逐孔减料）；mass_g=volume_mm3*rho(g/cm3)/1000；mass_kg=mass_g/1000。直径一律用半径的平方，pi 取 3.14159，禁止一步心算。",
    "adapt_machine": "本族：required_spindle_rpm=1000*vc/(pi*D)（vc 用现场参数表给出的推荐切削速度，D 为工件/刀具直径）；machine_max_rpm 照抄机床铭牌上限；within_limit=(required_spindle_rpm <= machine_max_rpm)；recommended_vc_m_per_min 照抄参数表。判定只做这一个不等式。",
    "adapt_material": "本族：safety_factor=Sy/sigma（Sy 取现场物性表屈服强度，sigma 取题面工作应力）；fos_gate 按 1.5 阈值（>=1.5 记 pass，否则 fail）。现场物性表的数值优先于记忆中的牌号典型值，禁止用 <已知牌号> 的常识值覆盖现场数据。",
}


def card_system(fam: str) -> str:
    return LITE_SYSTEM + "\n" + FAMILY_CARD.get(fam, "")


LITE_SYSTEM = """你是 Virtu 制造世界模型。给定制造场景参数，输出可被求解器复算的物理量。
铁律：
1) 只输出 JSON 对象，顶层含 world_state；参数非法/缺失时 world_state=null 且 invalid=true、reason 说明。
2) world_state 只用给定键名（如 surface_roughness_ra_um、safety_factor、delta_volume_mm3），数值不带单位；
   每个数值必须在 derivation 里给出代入题面数字的算式（如 "(0.13)*(0.13)/(8*(1.2))*1000"）。
3) 一律用题面给定数值，禁止使用记忆中的默认值；禁止编造题面没有的参数。
4) 闸门：safety_factor>=1.5 记 fos_gate="FOS>=1.5_pass"；材料去除 delta_volume_mm3<0。"""


def _selftest():
    import json
    w = wide_schema()
    json.dumps(w)
    assert w["properties"]["world_state"]["properties"]["safety_factor"]["type"] == "number"
    f = family_schema("roughness")
    assert set(f["properties"]["world_state"]["properties"]) == set(FAMILY_FIELDS["roughness"])
    print("[wm_schema] SELFTEST OK, fields =", len(_ws_props()))


if __name__ == "__main__":
    _selftest()
