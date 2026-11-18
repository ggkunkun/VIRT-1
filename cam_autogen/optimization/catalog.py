"""材料与刀具数据（手册名义值，basis=handbook_nominal；上线前需按刀具厂商样本校准）。"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from cam_autogen.contracts import MaterialSpec, ToolSpec

# kc1: 单位切削力 (N/mm², h=1mm)；mc: 切屑厚度指数；vc_turn/vc_mill: T=15min 参考切速 (m/min, 涂层硬质合金)
# n: Taylor 指数；e_mod: 弹性模量 (N/mm²)；group: ISO 513 材料组
MATERIALS: Dict[str, Dict[str, float | str]] = {
    "C45":     {"group": "P", "kc1": 1700, "mc": 0.25, "vc_turn": 240, "vc_mill": 220, "n": 0.25, "hb": 200, "e_mod": 210000},
    "Q235":    {"group": "P", "kc1": 1500, "mc": 0.25, "vc_turn": 280, "vc_mill": 250, "n": 0.25, "hb": 140, "e_mod": 206000},
    "42CrMo":  {"group": "P", "kc1": 2000, "mc": 0.25, "vc_turn": 190, "vc_mill": 170, "n": 0.23, "hb": 280, "e_mod": 210000},
    "SUS304":  {"group": "M", "kc1": 2100, "mc": 0.21, "vc_turn": 180, "vc_mill": 150, "n": 0.22, "hb": 180, "e_mod": 193000},
    "6061-T6": {"group": "N", "kc1": 700,  "mc": 0.25, "vc_turn": 700, "vc_mill": 600, "n": 0.35, "hb": 95,  "e_mod": 69000},
    "7075-T6": {"group": "N", "kc1": 850,  "mc": 0.25, "vc_turn": 600, "vc_mill": 500, "n": 0.35, "hb": 150, "e_mod": 71700},
    "HT250":   {"group": "K", "kc1": 1100, "mc": 0.28, "vc_turn": 220, "vc_mill": 200, "n": 0.25, "hb": 220, "e_mod": 110000},
    "H62":     {"group": "N", "kc1": 780,  "mc": 0.18, "vc_turn": 380, "vc_mill": 320, "n": 0.35, "hb": 110, "e_mod": 100000},
    "Ti6Al4V": {"group": "S", "kc1": 1450, "mc": 0.23, "vc_turn": 60,  "vc_mill": 50,  "n": 0.20, "hb": 330, "e_mod": 114000},
}
ALIASES = {"45": "C45", "45#": "C45", "AISI1045": "C45", "S45C": "C45", "304": "SUS304", "AISI304": "SUS304",
           "6061": "6061-T6", "AL6061": "6061-T6", "7075": "7075-T6", "TC4": "Ti6Al4V", "GR5": "Ti6Al4V",
           "40CRMO": "42CrMo", "42CRMO4": "42CrMo", "SCM440": "42CrMo", "GG25": "HT250", "BRASS": "H62"}


def resolve_material(m: MaterialSpec) -> Tuple[str, Dict[str, float | str], Optional[str]]:
    key = m.name.strip()
    norm = key.upper().replace(" ", "").replace("_", "")
    for k in MATERIALS:
        if k.upper() == norm:
            return k, MATERIALS[k], None
    if norm in ALIASES:
        return ALIASES[norm], MATERIALS[ALIASES[norm]], None
    # 未知牌号：按硬度就近匹配，并显式告警
    hb = m.hardness_hb or (m.tensile_mpa / 3.45 if m.tensile_mpa else 200)
    best = min((k for k in MATERIALS if k != "Ti6Al4V"), key=lambda k: abs(float(MATERIALS[k]["hb"]) - hb))
    return best, MATERIALS[best], f"未知材料 '{m.name}'，按硬度 {hb:.0f}HB 就近套用 {best} 的切削数据"


END_MILLS = [20, 16, 12, 10, 8, 6, 5, 4, 3]
DRILLS = [round(1 + 0.1 * i, 1) for i in range(191)]  # 1.0 … 20.0，0.1 级差（GB/T 6135 直柄麻花钻常备规格）
TAP_DRILL = {3: (0.5, 2.5), 4: (0.7, 3.3), 5: (0.8, 4.2), 6: (1.0, 5.0), 8: (1.25, 6.8), 10: (1.5, 8.5),
             12: (1.75, 10.2), 16: (2.0, 14.0), 20: (2.5, 17.5)}


def end_mill(d: float, depth: float, kind: str = "end_mill") -> ToolSpec:
    return ToolSpec(tool_id=f"{'LEM' if kind.startswith('live') else 'EM'}{d:g}", kind=kind, diameter=d, flutes=4 if d >= 6 else 3,
                    corner_radius=0.0, length=max(3.0 * d, depth + 15.0), flute_length=max(2.0 * d, depth + 2.0),
                    max_ap=max(1.5 * d, depth), edge_cost=30.0 + 6.0 * d)


def pick_end_mill(max_d: float, depth: float, kind: str = "end_mill") -> ToolSpec:
    for d in END_MILLS:
        if d <= max_d + 1e-9:
            return end_mill(d, depth, kind)
    raise ValueError(f"无可用立铣刀：允许最大直径 {max_d:.2f} mm < 3 mm")


def face_mill(width: float) -> ToolSpec:
    d = 63.0 if width >= 45 else 50.0 if width >= 35 else 32.0
    return ToolSpec(tool_id=f"FM{d:g}", kind="face_mill", diameter=d, flutes=5 if d >= 50 else 3, corner_radius=0.8,
                    length=60.0, flute_length=6.0, max_ap=5.0, edge_cost=12.0, center_cutting=False)


def drill(d: float, depth: float, kind: str = "drill") -> ToolSpec:
    std = min(DRILLS, key=lambda x: abs(x - d))
    return ToolSpec(tool_id=f"{'LDR' if kind.startswith('live') else 'DR'}{std:g}", kind=kind, diameter=std, flutes=2,
                    length=max(depth + 20, 5 * std), flute_length=depth + 5, max_ap=std / 2, edge_cost=25 + 3 * std)


def spot_drill() -> ToolSpec:
    return ToolSpec(tool_id="SP10", kind="spot_drill", diameter=10, flutes=2, length=60, flute_length=10, max_ap=3,
                    edge_cost=30)


def reamer(d: float, depth: float) -> ToolSpec:
    return ToolSpec(tool_id=f"RM{d:g}", kind="reamer", diameter=d, flutes=6, length=depth + 30, flute_length=depth + 5,
                    max_ap=0.3, edge_cost=80)


def tap(d: float, pitch: float, depth: float) -> ToolSpec:
    return ToolSpec(tool_id=f"TP-M{d:g}", kind="tap", diameter=d, flutes=3, length=depth + 40, flute_length=depth + 5,
                    max_ap=pitch, edge_cost=40, pitch=pitch)


TURN_ROUGH = ToolSpec(tool_id="CNMG120408", kind="turn_rough", diameter=25, corner_radius=0.8, length=40,
                      flute_length=12, max_ap=4.0, edge_cost=6.0)
TURN_FINISH = ToolSpec(tool_id="VNMG160404", kind="turn_finish", diameter=25, corner_radius=0.4, length=40,
                       flute_length=16, max_ap=2.0, edge_cost=6.0)


def groove_tool(width: float) -> ToolSpec:
    w = 3.0 if width >= 3 else 2.0
    return ToolSpec(tool_id=f"GR{w:g}", kind="groove", diameter=w, corner_radius=0.2, length=40, flute_length=10,
                    max_ap=w, edge_cost=9.0)


def thread_tool(pitch: float) -> ToolSpec:
    return ToolSpec(tool_id="TH60", kind="thread", diameter=25, corner_radius=0.1, length=40, flute_length=10,
                    max_ap=0.5, edge_cost=10.0, pitch=pitch)


def boring_bar(min_bore: float, depth: float) -> ToolSpec:
    d = 10 if min_bore < 16 else 16 if min_bore < 25 else 20
    return ToolSpec(tool_id=f"BB{d}", kind="boring_bar", diameter=d, corner_radius=0.4, length=depth + 20,
                    flute_length=depth + 5, max_ap=1.5, edge_cost=8.0)


def all_material_names() -> List[str]:
    return sorted(MATERIALS)
