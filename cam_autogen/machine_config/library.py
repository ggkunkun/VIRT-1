"""内置主流 CNC 机床参数库（24 种型号）+ 自定义机床动态注册。

涵盖：
  - 10 台加工中心 / 数控铣床（FANUC / SIEMENS / HUAZHONG）
  - 7 台数控车床（FANUC / SIEMENS / HUAZHONG）
  - 7 台车铣复合中心（含 C 轴 / 动力刀 / Y 轴，FANUC / SIEMENS / HUAZHONG）

注：各参数为公开样本名义规格（``basis="nominal_catalog_approx"``），上机前应以车间实测验收参数为准。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from cam_autogen.contracts import MachineSpec

# 各控制器/机床类型支持的标准指令集
_G_MILL_COMMON = ["G00", "G0", "G01", "G1", "G02", "G03", "G04", "G17", "G18", "G19",
                  "G21", "G28", "G40", "G41", "G42", "G43", "G49", "G53", "G54", "G55",
                  "G56", "G57", "G58", "G59", "G80", "G81", "G83", "G84", "G90", "G91", "G94", "G95"]
_G_MILL_SIEMENS = _G_MILL_COMMON + ["G71", "G710", "G331", "G332", "SUPA"]

_G_LATHE_COMMON = ["G00", "G0", "G01", "G1", "G02", "G03", "G04", "G18", "G21", "G28",
                   "G32", "G40", "G41", "G42", "G50", "G53", "G54", "G55", "G56", "G57", "G58", "G59",
                   "G71", "G80", "G90", "G91", "G94", "G95", "G96", "G97", "G98", "G99"]
_G_LATHE_HNC = _G_LATHE_COMMON + ["G46"]
_G_LATHE_SIEMENS = [g for g in _G_LATHE_COMMON if g not in ("G32", "G50", "G98", "G99")] + ["G33", "G710", "SUPA"]

_M_MILL = ["M00", "M01", "M03", "M04", "M05", "M06", "M08", "M09", "M29", "M30"]
_M_LATHE = ["M00", "M01", "M03", "M04", "M05", "M08", "M09", "M30"]
_M_TURN_MILL = _M_LATHE + ["M06", "M13", "M14", "M15", "M18", "M19", "M28", "M29", "M33", "M34", "M35", "M70", "M71", "M88"]


def _g_for(kind: str, dialect: str) -> List[str]:
    if kind == "mill":
        return list(_G_MILL_SIEMENS if dialect == "SIEMENS" else _G_MILL_COMMON)
    if dialect == "SIEMENS":
        base = list(_G_LATHE_SIEMENS)
        if kind == "turn_mill":
            base += ["G17", "G19", "G84", "G331", "G332"]
        return base
    if dialect == "HUAZHONG":
        base = list(_G_LATHE_HNC)
        if kind == "turn_mill":
            base += ["G17", "G19", "G84"]
        return base
    base = list(_G_LATHE_COMMON)
    if kind == "turn_mill":
        base += ["G17", "G19", "G84"]
    return base


def _m_for(kind: str) -> List[str]:
    if kind == "mill":
        return list(_M_MILL)
    if kind == "turn_mill":
        return list(_M_TURN_MILL)
    return list(_M_LATHE)


def _mill(model: str, vendor: str, controller: str, dialect: str,
          tx: float, ty: float, tz: float, rpm: float, kw: float,
          feed: float, rapid: float, cap: int, max_td: float, max_tl: float,
          coolant_on: str = "M08") -> MachineSpec:
    return MachineSpec(
        model=model, vendor=vendor, kind="mill", controller=controller, dialect=dialect,  # type: ignore[arg-type]
        travel={"x": tx, "y": ty, "z": tz}, max_rpm=rpm, spindle_power_kw=kw,
        max_feed_mm_min=feed, rapid_mm_min=rapid, tool_capacity=cap,
        max_tool_diameter=max_td, max_tool_length=max_tl,
        has_y_axis=True, has_c_axis=False, live_tooling=False,
        table_center={"x": round(tx / 2, 1), "y": round(ty / 2, 1)},
        coolant_codes={"on": coolant_on, "off": "M09"},
        supported_g=_g_for("mill", dialect), supported_m=_m_for("mill"),
    )


def _lathe(model: str, vendor: str, controller: str, dialect: str, kind: str,
           tx: float, tz: float, x_neg: float, swing: float, turn_len: float,
           rpm: float, kw: float, feed: float, rapid: float, cap: int,
           max_td: float, max_tl: float, has_y: bool = False, has_c: bool = False,
           live: bool = False, live_rpm: float = 0, live_kw: float = 0,
           live_codes: Optional[Dict[str, str]] = None, coolant_on: str = "M08") -> MachineSpec:
    return MachineSpec(
        model=model, vendor=vendor, kind=kind, controller=controller, dialect=dialect,  # type: ignore[arg-type]
        travel={"x": tx, "z": tz, "x_neg": x_neg}, max_rpm=rpm, spindle_power_kw=kw,
        max_feed_mm_min=feed, rapid_mm_min=rapid, tool_capacity=cap,
        max_tool_diameter=max_td, max_tool_length=max_tl,
        has_y_axis=has_y, has_c_axis=has_c, live_tooling=live,
        live_tool_max_rpm=live_rpm, live_tool_power_kw=live_kw,
        max_swing_diameter=swing, max_turning_length=turn_len,
        table_center={"x": 0.0, "z_chuck_home": round(tz * 0.45, 1)},
        coolant_codes={"on": coolant_on, "off": "M09"},
        live_codes=live_codes or ({"cw": "M13", "stop": "M15", "c_on": "M18", "c_off": "M19"} if live else {}),
        supported_g=_g_for(kind, dialect), supported_m=_m_for(kind),
    )


BUILTIN_MACHINES: List[MachineSpec] = [
    # ---- 10 台加工中心 / 铣床 ----
    _mill("FANUC-ROBODRILL-D21MiB5", "FANUC", "FANUC 31i-B5", "FANUC",
          500, 400, 330, 10000, 5.5, 15000, 54000, 21, 80, 200),
    _mill("HAAS-VF2", "Haas", "Haas NGC (FANUC-compat)", "FANUC",
          762, 406, 508, 8100, 22.4, 16500, 25400, 20, 89, 250),
    _mill("HAAS-VF4SS", "Haas", "Haas NGC (FANUC-compat)", "FANUC",
          1270, 508, 635, 12000, 22.4, 21200, 35600, 30, 89, 300),
    _mill("SMTCL-VMC850B", "沈阳机床", "FANUC 0i-MF Plus", "FANUC",
          800, 500, 500, 8000, 11.0, 10000, 30000, 24, 90, 250),
    _mill("DMTG-VDL850A", "大连机床", "FANUC 0i-MF", "FANUC",
          800, 500, 550, 10000, 15.0, 12000, 36000, 24, 90, 280),
    _mill("MAZAK-VCN530C", "Mazak", "Mazatrol SmoothG (FANUC-ISO)", "FANUC",
          1050, 530, 510, 12000, 18.5, 18000, 42000, 30, 100, 300),
    _mill("MAKINO-F5", "Makino", "Professional 6 (FANUC-ISO)", "FANUC",
          900, 500, 450, 20000, 22.0, 20000, 30000, 30, 100, 280),
    _mill("DMG-CMX600V", "DMG MORI", "SIEMENS Sinumerik 840D sl", "SIEMENS",
          600, 560, 510, 12000, 13.0, 20000, 30000, 30, 80, 280),
    _mill("HAITIAN-VMC1000II", "海天精工", "SIEMENS Sinumerik 828D", "SIEMENS",
          1000, 600, 600, 10000, 15.0, 12000, 30000, 24, 100, 300),
    _mill("HNC-HMC850", "华中数控", "HNC-848C", "HUAZHONG",
          850, 520, 520, 10000, 11.0, 12000, 32000, 24, 90, 250),

    # ---- 7 台数控车床 ----
    _lathe("SMTCL-CAK5085", "沈阳机床", "FANUC 0i-TF Plus", "FANUC", "lathe",
           260, 850, 15, 500, 750, 2500, 11.0, 6000, 20000, 8, 32, 160),
    _lathe("DMTG-CKA6150", "大连机床", "FANUC 0i-TF", "FANUC", "lathe",
           280, 1000, 15, 500, 900, 3000, 11.0, 8000, 24000, 8, 32, 180),
    _lathe("DOOSAN-LYNX2100", "DN Solutions", "FANUC 0i-TF Plus", "FANUC", "lathe",
           205, 550, 20, 510, 510, 4500, 15.0, 10000, 30000, 12, 32, 180),
    _lathe("HAAS-ST20", "Haas", "Haas NGC (FANUC-compat)", "FANUC", "lathe",
           236, 533, 20, 533, 533, 4000, 14.9, 12000, 24000, 12, 32, 180),
    _lathe("DMG-CLX350", "DMG MORI", "SIEMENS Sinumerik 840D sl", "SIEMENS", "lathe",
           220, 530, 20, 520, 500, 5000, 16.5, 10000, 30000, 12, 32, 180),
    _lathe("NEWAY-NL252", "纽威数控", "SIEMENS Sinumerik 828D", "SIEMENS", "lathe",
           230, 550, 20, 500, 520, 4000, 15.0, 10000, 24000, 12, 32, 180),
    _lathe("HNC-CK6140", "华中数控", "HNC-818T", "HUAZHONG", "lathe",
           210, 750, 15, 400, 680, 4000, 11.0, 8000, 20000, 8, 32, 160),

    # ---- 7 台车铣复合中心 ----
    _lathe("DMG-NLX2500SY", "DMG MORI", "FANUC 31i-B (CELOS)", "FANUC", "turn_mill",
           260, 795, 40, 460, 705, 4000, 18.5, 12000, 30000, 12, 32, 200,
           has_y=True, has_c=True, live=True, live_rpm=6000, live_kw=5.5),
    _lathe("DOOSAN-PUMA2600SY", "DN Solutions", "FANUC 31i-B", "FANUC", "turn_mill",
           260, 830, 40, 520, 760, 3500, 22.0, 12000, 30000, 12, 32, 200,
           has_y=True, has_c=True, live=True, live_rpm=5000, live_kw=5.5),
    _lathe("MAZAK-QTN200MSY", "Mazak", "Mazatrol SmoothG", "FANUC", "turn_mill",
           220, 560, 35, 380, 510, 5000, 18.5, 12000, 30000, 12, 32, 180,
           has_y=True, has_c=True, live=True, live_rpm=6000, live_kw=5.5),
    _lathe("OKUMA-LB3000EX-MY", "Okuma", "OSP-P300L (ISO)", "FANUC", "turn_mill",
           260, 1020, 35, 580, 950, 4200, 22.0, 12000, 25000, 12, 32, 200,
           has_y=True, has_c=True, live=True, live_rpm=6000, live_kw=5.5),
    _lathe("TSUGAMI-M08SY", "津上机床", "FANUC 0i-TF", "FANUC", "turn_mill",
           190, 480, 35, 350, 440, 4500, 11.0, 10000, 24000, 12, 25, 160,
           has_y=True, has_c=True, live=True, live_rpm=6000, live_kw=3.7),
    _lathe("DMG-CTX-BETA800", "DMG MORI", "SIEMENS Sinumerik 840D sl", "SIEMENS", "turn_mill",
           280, 850, 40, 500, 800, 5000, 25.0, 15000, 30000, 16, 32, 200,
           has_y=True, has_c=True, live=True, live_rpm=6000, live_kw=8.4,
           live_codes={"cw": "M33", "stop": "M35", "c_on": "M70", "c_off": "M71"}),
    _lathe("HNC-CK6150MY", "华中数控", "HNC-848T", "HUAZHONG", "turn_mill",
           250, 800, 35, 500, 720, 3500, 15.0, 10000, 24000, 12, 32, 180,
           has_y=True, has_c=True, live=True, live_rpm=4500, live_kw=4.5),
]


class MachineRegistry:
    """可动态扩展的机床参数库。"""

    def __init__(self, store_path: Optional[Path] = None):
        self._machines: Dict[str, MachineSpec] = {m.model: m.model_copy(deep=True) for m in BUILTIN_MACHINES}
        self._custom_models: set[str] = set()
        self._store_path = store_path
        if store_path and store_path.is_file():
            self.load_custom_file(store_path)

    def list_machines(self, kind: Optional[str] = None, dialect: Optional[str] = None) -> List[MachineSpec]:
        res = list(self._machines.values())
        if kind:
            res = [m for m in res if m.kind == kind]
        if dialect:
            res = [m for m in res if m.dialect == dialect]
        return res

    def get(self, model: str) -> Optional[MachineSpec]:
        return self._machines.get(model)

    def register(self, spec: MachineSpec, overwrite: bool = False) -> MachineSpec:
        if spec.model in self._machines and not overwrite:
            raise ValueError(f"机床型号 {spec.model!r} 已存在（如需更新请设 overwrite=True）")
        # 补齐默认指令集（允许外部简化提交）
        data = spec.model_dump()
        if not data["supported_g"]:
            data["supported_g"] = _g_for(spec.kind, spec.dialect)
        if not data["supported_m"]:
            data["supported_m"] = _m_for(spec.kind)
        if not data["table_center"]:
            data["table_center"] = (
                {"x": round(spec.travel["x"] / 2, 1), "y": round(spec.travel.get("y", 400) / 2, 1)}
                if spec.kind == "mill" else {"x": 0.0, "z_chuck_home": round(spec.travel["z"] * 0.45, 1)}
            )
        if spec.live_tooling and not data["live_codes"]:
            data["live_codes"] = {"cw": "M13", "stop": "M15", "c_on": "M18", "c_off": "M19"}
        filled = MachineSpec.model_validate(data)
        self._machines[filled.model] = filled
        self._custom_models.add(filled.model)
        if self._store_path:
            self._save_custom()
        return filled

    def remove_custom(self, model: str) -> bool:
        if model not in self._custom_models:
            return False
        self._custom_models.remove(model)
        self._machines.pop(model, None)
        if self._store_path:
            self._save_custom()
        return True

    def count(self) -> int:
        return len(self._machines)

    def _save_custom(self) -> None:
        if not self._store_path:
            return
        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        items = [self._machines[k].model_dump(mode="json") for k in sorted(self._custom_models) if k in self._machines]
        self._store_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_custom_file(self, path: Path) -> int:
        raw = json.loads(path.read_text(encoding="utf-8"))
        n = 0
        for item in raw:
            self.register(MachineSpec.model_validate(item), overwrite=True)
            n += 1
        return n


DEFAULT_REGISTRY = MachineRegistry()
