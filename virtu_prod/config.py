# -*- coding: utf-8 -*-
"""量产配置装载与合法性审查（参数必须先过标准区间，再允许生成 NC）。

设计原则（测量宪法）：
  * 所有判据输入来自 YAML 与实测网格包围盒，不写死“合格”。
  * 每个 gate 都输出 measured 值与判据，可被反证（越界即红）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

CONFIG_DIR = Path(__file__).resolve().parent.parent / "production" / "config"


@dataclass
class Tool:
    tid: str
    name: str
    type: str
    diameter_mm: float
    flutes: int
    gauge_length_mm: float
    flute_length_mm: float
    shank_diameter_mm: float
    holder_diameter_mm: float
    holder_length_mm: float
    taylor_c: float
    taylor_n: float
    life_target_min: float


@dataclass
class Machine:
    key: str
    label: str
    controller: str
    dialect: str
    production_ready: bool
    travel_mm: Dict[str, List[float]]
    rotary_limits_deg: Dict[str, List[float]]
    spindle_rpm: List[float]
    rapid_mm_min: float
    tool_change_s: float
    tool_change_point: Dict[str, float]
    work_offset: str
    supports_rtcp: bool


@dataclass
class Process:
    part: Dict[str, Any]
    stock: Dict[str, Any]
    stations: Dict[str, Any]
    safety: Dict[str, Any]
    operations: List[Dict[str, Any]]
    quality: Dict[str, Any]
    production: Dict[str, Any]
    tools: Dict[str, Tool]
    standards: Dict[str, Any]
    machines: Dict[str, Machine]
    checks: List[Dict[str, Any]] = field(default_factory=list)

    def op(self, op_id: str) -> Dict[str, Any]:
        for o in self.operations:
            if o["id"] == op_id:
                return o
        raise KeyError(op_id)


def _load_yaml(path: Path) -> Dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load(config_dir: Optional[Path] = None) -> Process:
    cd = Path(config_dir) if config_dir else CONFIG_DIR
    machines_raw = _load_yaml(cd / "machines.yml")["machines"]
    process_raw = _load_yaml(cd / "process_ae_ci_258.yml")
    tools_raw = _load_yaml(cd / "tools.yml")["tools"]
    standards = _load_yaml(cd / "standards.yml")

    tools: Dict[str, Tool] = {}
    for tid, t in tools_raw.items():
        tools[tid] = Tool(
            tid=tid, name=t["name"], type=t["type"], diameter_mm=float(t["diameter_mm"]),
            flutes=int(t["flutes"]), gauge_length_mm=float(t["gauge_length_mm"]),
            flute_length_mm=float(t["flute_length_mm"]),
            shank_diameter_mm=float(t["shank_diameter_mm"]),
            holder_diameter_mm=float(t["holder"]["diameter_mm"]),
            holder_length_mm=float(t["holder"]["length_mm"]),
            taylor_c=float(t["taylor"]["C"]), taylor_n=float(t["taylor"]["n"]),
            life_target_min=float(t["life_target_min"]),
        )

    machines: Dict[str, Machine] = {}
    for key, m in machines_raw.items():
        machines[key] = Machine(
            key=key, label=m["label"], controller=m["controller"], dialect=m["dialect"],
            production_ready=bool(m.get("production_ready", True)),
            travel_mm={k: [float(v[0]), float(v[1])] for k, v in m["travel_mm"].items()},
            rotary_limits_deg={k: [float(v[0]), float(v[1])]
                               for k, v in m["rotary_limits_deg"].items()},
            spindle_rpm=[float(v) for v in m["spindle_rpm"]],
            rapid_mm_min=float(m["rapid_mm_min"]),
            tool_change_s=float(m["tool_change_s"]),
            tool_change_point={k: float(v) for k, v in m["tool_change_point"].items()},
            work_offset=m.get("work_offset", "G54"),
            supports_rtcp=bool(m.get("supports_rtcp", False)),
        )

    return Process(
        part=process_raw["part"], stock=process_raw["stock"], stations=process_raw["stations"],
        safety=process_raw["safety"], operations=process_raw["operations"],
        quality=process_raw["quality"], production=process_raw["production"],
        tools=tools, standards=standards, machines=machines,
    )


def _check(checks: List[Dict[str, Any]], gate: str, ok: bool, evidence: Any,
           rule: str) -> None:
    checks.append({"gate": gate, "status": "PASS" if ok else "FAIL",
                   "evidence": evidence, "rule": rule})


def _in(v: float, rng: List[float]) -> bool:
    return rng[0] <= v <= rng[1]


def validate(p: Process, design_bbox: Optional[Dict[str, List[float]]] = None) -> List[Dict[str, Any]]:
    """参数合法性审查：标准区间 + 几何一致性。返回 checks 列表。"""
    checks: List[Dict[str, Any]] = []
    mat = p.standards["materials"][p.part["material"]]["machining"]
    rules = p.standards["process_rules"]

    # 1) 安全参数
    safe_z = float(p.safety["safe_z_work_mm"])
    _check(checks, "SAFE-Z", safe_z >= rules["safe_z_mm"]["min"],
           f"safe_z={safe_z} mm", f"≥{rules['safe_z_mm']['min']} mm")
    red = float(p.safety["rapid_reduction_mm"])
    _check(checks, "RAPID-REDUCTION", red >= rules["rapid_reduction_mm"]["min"],
           f"rapid_reduction={red} mm", f"≥{rules['rapid_reduction_mm']['min']} mm")

    # 2) 装夹
    band = float(p.stations["op1"]["clamp_band_mm"])
    _check(checks, "CLAMP-BAND", band >= rules["clamp_band_mm"]["min"],
           f"clamp_band={band} mm", f"≥{rules['clamp_band_mm']['min']} mm")

    # 3) 毛坯余量与尺寸
    margins = p.stock["margins_mm"]
    for k, key in (("side", "side"), ("top", "top"), ("bottom", "bottom")):
        rng = rules["stock_margin_mm"][key]
        v = float(margins[k])
        _check(checks, f"STOCK-MARGIN-{k.upper()}", _in(v, rng), f"{k}={v} mm",
               f"{rng[0]}..{rng[1]} mm")
    if design_bbox:
        dx = design_bbox["x"][1] - design_bbox["x"][0]
        dy = design_bbox["y"][1] - design_bbox["y"][0]
        dz = design_bbox["z"][1] - design_bbox["z"][0]
        sx, sy, sz = [float(v) for v in p.stock["size_mm"]]
        _check(checks, "STOCK-SIZE", abs(sx - (dx + 2 * margins["side"])) <= 0.01
               and abs(sy - (dy + 2 * margins["side"])) <= 0.01
               and abs(sz - (dz + margins["top"] + margins["bottom"])) <= 0.01,
               {"stock": [sx, sy, sz], "design": [round(dx, 2), round(dy, 2), round(dz, 2)]},
               "毛坯 = 设计包络 + 侧 3 / 顶 3 / 底 5")
        cham = float(p.stock["chamfer_bottom_mm"])
        bottom_margin = float(margins["bottom"])
        _check(checks, "STOCK-CHAMFER-CLEARANCE", cham < bottom_margin,
               f"chamfer={cham} < bottom_margin={bottom_margin}",
               "底倒角不得侵入设计包络（否则包容性失效）")

    # 4) 余量分配
    allow = p.stock["allowances_mm"]
    for key, rng in rules["allowance_mm"].items():
        v = float(allow[key])
        _check(checks, f"ALLOW-{key.upper()}", _in(v, rng), f"{key}={v} mm",
               f"{rng[0]}..{rng[1]} mm")

    # 5) 切削参数（Vc / fz）——按工序类型查区间
    for op in p.operations:
        tool = p.tools[op["tool"]]
        cut_type = op.get("cut_type", "rough")
        vc = 3.141592653589793 * tool.diameter_mm * float(op["rpm"]) / 1000.0
        rng = mat["vc_m_min"][cut_type]
        _check(checks, f"{op['id']}-VC", _in(vc, rng),
               f"Vc={vc:.1f} m/min (D{tool.diameter_mm:g} @ {op['rpm']} rpm)",
               f"{cut_type} 区间 {rng[0]}..{rng[1]} m/min")
        fz = float(op["feed_cut"]) / (float(op["rpm"]) * tool.flutes)
        frng = mat["fz_mm_z"][cut_type]
        _check(checks, f"{op['id']}-FZ", _in(fz, frng),
               f"fz={fz:.3f} mm/z (F{op['feed_cut']:g} / {op['rpm']} / {tool.flutes}刃)",
               f"{cut_type} 区间 {frng[0]}..{frng[1]} mm/z")
        rpm_max = p.machines["prod_5ax_fanuc_0imf"].spindle_rpm[1]
        _check(checks, f"{op['id']}-RPM-LIMIT", float(op["rpm"]) <= rpm_max,
               f"{op['rpm']} ≤ {rpm_max}", "主轴上限")
        if op.get("cut_type") == "finish" and "feed_cut" in op:
            pass
        # 第二把刀（OP3 T2）
        if "tool2" in op:
            t2 = p.tools[op["strategy"]["tool2"]]
            vc2 = 3.141592653589793 * t2.diameter_mm * float(op["strategy"]["rpm2"]) / 1000.0
            rng2 = mat["vc_m_min"]["finish"]
            _check(checks, f"{op['id']}-T2-VC", _in(vc2, rng2),
                   f"Vc={vc2:.1f} m/min (D{t2.diameter_mm:g} @ {op['strategy']['rpm2']} rpm)",
                   f"finish 区间 {rng2[0]}..{rng2[1]} m/min")

    # 6) 质量与量产
    cpk = float(p.quality["cpk_min"])
    _check(checks, "CPK-MIN", cpk >= rules["cpk_min"],
           f"Cpk_min={cpk}", f"≥{rules['cpk_min']}（PPAP 量产下限）")
    chg = float(p.production["changeover_target_min"])
    _check(checks, "CHANGEOVER-TARGET", chg <= rules["changeover_min"],
           f"target={chg} min", f"≤{rules['changeover_min']} min")
    for tid, tool in p.tools.items():
        tgt = float(p.production["tool_life_target_min"][tid])
        ok = abs(tgt - tool.life_target_min) <= 15.0
        _check(checks, f"{tid}-LIFE", ok,
               f"config={tgt} / tool={tool.life_target_min}",
               "刀具寿命目标差 ≤15 min（避免换刀策略冲突）")

    # 7) 机床适配
    for key, m in p.machines.items():
        if m.production_ready:
            _check(checks, f"MACHINE-{key}-RTCP", m.supports_rtcp,
                   f"supports_rtcp={m.supports_rtcp}", "五轴工序要求 RTCP")
    return checks


def summary(checks: List[Dict[str, Any]]) -> Dict[str, Any]:
    failed = [c for c in checks if c["status"] == "FAIL"]
    return {"total": len(checks), "failed": len(failed),
            "verdict": "PASS" if not failed else "FAIL",
            "failed_gates": [c["gate"] for c in failed]}
