# -*- coding: utf-8 -*-
"""三方言工业级 NC 发射器（FANUC 0i / SINUMERIK 840D sl / HNC-8）。

工业结构（三方言一致）：
  程序头（程序号 / 零件与毛坯标识 / 安全块 / 工件零点 / 断点表）
  -> 每工序：抬刀到换刀高度 -> B/C 回零 -> 移到换刀点 -> 换刀 -> 安全高度定位
     -> 刀长补偿（五轴用 G43.4）/ Siemens T-D -> 主轴 -> 冷却 -> 刀位
     -> 抬刀 -> 冷却停 -> 主轴停 -> 补偿取消 -> M01 可选停止
  -> 程序尾：G28 回参考点 / B C 回零 / M30
断点接续：每块带 N 号（步距 10），发射器同时产出 restart 映射（op -> N 号）。
半径补偿：Operation.radius_comp=True 时首块 G41/G42 D、末块 G40；本例中心线编程保持 G40。
"""
from __future__ import annotations

import math
from typing import Dict, List

from .programs import Block, Operation, Program


def _f(v: float) -> str:
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "", "-") else s


def tool_axis(b: float, c: float) -> tuple:
    """工作坐标系下的刀轴矢量（转台式 B/C：work <- machine = Rz(-C)Ry(-B)）。"""
    br, cr = math.radians(b), math.radians(c)
    return (-math.sin(br) * math.cos(cr), math.sin(br) * math.sin(cr), math.cos(br))


def _tid(op: Operation) -> str:
    return str(op.tool.tid).lstrip("Tt")


def _op_comments(op: Operation) -> List[str]:
    return [f"=== {op.op_id}: {op.name} ===",
            f"TOOL T{_tid(op)} D{_f(op.tool.diameter_mm)} {op.tool.type.upper()} "
            f"GAUGE {_f(op.tool.gauge_length_mm)}",
            f"MODE {op.mode} RPM {op.rpm} FEED {_f(op.feed_cut)}"]


def _motion_fanuc(b: Block) -> str:
    g = {"rapid": "G00", "feed": "G01", "arc_cw": "G02", "arc_ccw": "G03"}[b.kind]
    words = [g]
    for k in ("x", "y", "z", "b", "c"):
        v = getattr(b, k)
        if v is not None:
            words.append(f"{k.upper()}{_f(v)}")
    if b.kind in ("arc_cw", "arc_ccw"):
        if b.i is not None:
            words.append(f"I{_f(b.i)}")
        if b.j is not None:
            words.append(f"J{_f(b.j)}")
    if b.f is not None:
        words.append(f"F{_f(b.f)}")
    return " ".join(words)


def _motion_siemens(b: Block) -> str:
    g = {"rapid": "G0", "feed": "G1", "arc_cw": "G2", "arc_ccw": "G3"}[b.kind]
    words = [g]
    for k in ("x", "y", "z"):
        v = getattr(b, k)
        if v is not None:
            words.append(f"{k.upper()}={_f(v)}")
    if b.kind in ("arc_cw", "arc_ccw"):
        if b.i is not None:
            words.append(f"I={_f(b.i)}")
        if b.j is not None:
            words.append(f"J={_f(b.j)}")
    if b.f is not None:
        words.append(f"F{_f(b.f)}")
    if b.b is not None or b.c is not None:
        ax, ay, az = tool_axis(b.b or 0.0, b.c or 0.0)
        words.append(f"A3={_f(round(ax, 6))} B3={_f(round(ay, 6))} C3={_f(round(az, 6))}")
    return " ".join(words)


class Emitter:
    def __init__(self, dialect: str, prog: Program, machine: Dict, stock: Dict):
        self.d = dialect
        self.prog = prog
        self.m = machine
        self.stock = stock
        self.lines: List[str] = []
        self.n = 0
        self.restart: Dict[str, int] = {}

    def _num(self) -> str:
        self.n += 10
        return f"N{self.n}"

    def line(self, text: str) -> None:
        if self.d == "siemens":
            self.lines.append(f"{self._num()} {text}")
        else:
            self.lines.append(f"{self._num()} {text}")

    def comment(self, text: str) -> None:
        self.lines.append(f";{text}" if self.d == "siemens" else f"({text})")

    def header(self) -> None:
        if self.d == "siemens":
            self.comment(f"{self.prog.part_id} / {self.prog.op_id} / SINUMERIK 840D sl")
            self.comment(f"PART {self.prog.part_id} MATERIAL {self.stock['material']} "
                         f"STOCK {self.stock['size'][0]:g}X{self.stock['size'][1]:g}X"
                         f"{self.stock['size'][2]:g}")
            self.comment(f"WCS {self.prog.wcs} STOCK TOP CENTER SAFE Z {self.m['safe_z']:g}")
            self.comment(f"RESTART BY BLOCK SEARCH / OPERATIONS {len(self.prog.operations)}")
            self.line("G71 G90 G17 G40 G54")
            self.line("M01")
        else:
            tag = "FANUC 0i" if self.d == "fanuc" else "HNC-8"
            self.lines.append("%")
            self.lines.append(f"O{self.prog.number:04d} ({self.prog.part_id} / {self.prog.op_id})")
            self.comment(f"CONTROLLER {tag} MACHINE {self.m['label']}")
            self.comment(f"PART {self.prog.part_id} MATERIAL {self.stock['material']} "
                         f"STOCK {self.stock['size'][0]:g}X{self.stock['size'][1]:g}X"
                         f"{self.stock['size'][2]:g}")
            self.comment(f"WCS {self.prog.wcs} STOCK TOP CENTER SAFE Z {self.m['safe_z']:g}")
            self.comment("OPTIONAL STOP M01 BETWEEN OPERATIONS")
            self.line("G21 G17 G40 G49 G80 G90")
            self.line(self.prog.wcs)
            self.line("M01")

    def op(self, op: Operation) -> None:
        for c in _op_comments(op):
            self.comment(c)
        self.restart[op.op_id] = self.n + 10
        if self.d == "siemens":
            self.line(f"G0 Z{_f(self.m['tc_z'])}")
            self.line("B0 C0")
            self.line(f"G0 X{_f(self.m['tc_x'])} Y{_f(self.m['tc_y'])}")
            self.line(f"T{_tid(op)} D1 M6")
            first = op.blocks[0]
            if first.x is not None and first.y is not None:
                self.line(f"G0 X={_f(first.x)} Y={_f(first.y)} Z={_f(first.z or self.m['safe_z'])}")
            if op.mode == "5axis_rtcp":
                self.line("TRAORI")
            self.line(f"S{op.rpm} M3")
            if op.coolant:
                self.line("M8")
            skip = first.x is not None and first.y is not None
            for idx, b in enumerate(op.blocks):
                if idx == 0 and skip:
                    continue
                self.line(_motion_siemens(b))
            if op.mode == "5axis_rtcp":
                self.line("TRAFOOF")
            if op.coolant:
                self.line("M9")
            self.line("M5")
            self.line(f"G0 Z{_f(self.m['tc_z'])}")
            self.line("M01")
            return

        self.line(f"G00 G90 G49 Z{_f(self.m['tc_z'])}")
        self.line("G00 B0. C0.")
        self.line(f"G00 X{_f(self.m['tc_x'])} Y{_f(self.m['tc_y'])}")
        self.line(f"T{_tid(op)} M06")
        first = op.blocks[0]
        if first.x is not None and first.y is not None:
            self.line(f"G00 X{_f(first.x)} Y{_f(first.y)} Z{_f(first.z or self.m['safe_z'])}")
        if op.mode == "5axis_rtcp":
            self.line(f"G43.4 H{_tid(op)} (TCPM ON / LENGTH COMP)")
        else:
            self.line(f"G43 H{_tid(op)} Z{_f(self.m['safe_z'])}")
        self.line(f"S{op.rpm} M03")
        if op.coolant:
            self.line("M08")
        skip = first.x is not None and first.y is not None
        for idx, b in enumerate(op.blocks):
            if idx == 0 and skip:
                continue
            self.line(_motion_fanuc(b))
        self.line("G49")
        if op.coolant:
            self.line("M09")
        self.line("M05")
        self.line(f"G00 Z{_f(self.m['tc_z'])}")
        self.line("M01")

    def footer(self) -> None:
        if self.d == "siemens":
            self.line(f"G0 Z{_f(self.m['tc_z'])}")
            self.line("B0 C0")
            self.line("M30")
        else:
            self.line("G91 G28 Z0.")
            self.line("G28 X0. Y0.")
            self.line("G90")
            self.line("G00 B0. C0.")
            self.line("M30")
            self.lines.append("%")

    def emit(self) -> Dict:
        self.header()
        for op in self.prog.operations:
            self.op(op)
        self.footer()
        return {"nc": "\n".join(self.lines) + "\n", "restart": self.restart}


def emit(prog: Program, machine: Dict, stock: Dict) -> Dict:
    """machine 需含 label/dialect/safe_z/tc_z/tc_x/tc_y；stock 需含 material/size。"""
    return Emitter(machine["dialect"], prog, machine, stock).emit()
