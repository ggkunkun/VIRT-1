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
]
STR_FIELDS = {
    "volume_conservation": ["pass_cut_negative", "pass", "FAIL"],
    "finish_class": ["精加工", "半精", "粗加工"],
    "material": ["45钢", "铝合金6061", "不锈钢304", "钛合金TC4", "黄铜H62"],
    "fos_gate": ["FOS>=1.5_pass", "FOS<1.5_FAIL"],
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
    "collision": "本族必须填全三个 Z 值：safe_plane_z_mm、rapid_min_z_mm、stock_top_z_mm（照抄题面），gouge=(Z_rapid_min<Z_stock_top)，collision_risk=high 当 (Z_rapid_min<Z_safe 且 Z_rapid_min<Z_stock_top+1) 否则 none，autodiff 由 gouge/risk 决定。",
    "tolerance": "本族：closed_loop_worstcase_halfwidth_mm=sum(ti)；closed_loop_rss_halfwidth_mm=sqrt(sum(ti^2))；fit_clearance_mm=上偏差-下偏差；tolerance_fit 按间隙正负。",
    "geom_delta": "本族：delta_volume_mm3=-feature_volume_mm3；after_volume_mm3=before_volume_mm3+delta_volume_mm3；before_volume_mm3 照抄题面。",
    "mass_props": "本族：圆柱 volume_mm3=pi*r^2*h、惯性矩为截面二次矩（面积惯性矩 mm^4）：inertia_ixx_mm4=pi*r^4/4、inertia_izz_mm4=pi*r^4/2；长方体 volume=l*w*h、Ixx=w*h^3/12、Izz=l*w^3/12；centroid 为几何中心坐标 [x,y,z]（圆柱 [r,r,h/2]、长方体 [l/2,w/2,h/2]）；mass_g=volume_mm3*rho(g/cm3)/1000。",
    "invalid": "本族：输入非法或关键参数缺失时 world_state=null、invalid=true、reason 指出缺什么，禁止猜数值。",
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
