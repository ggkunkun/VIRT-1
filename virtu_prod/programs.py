# -*- coding: utf-8 -*-
"""控制器无关的程序模型与 AE-CI-258 三道工序的刀位构建。

坐标口径：工作坐标 Z0 = 毛坯上表面中心（与 VERICUT 工位 G54 一致）。
本模块只产生几何刀位与工艺参数，不掺入任何方言语法。
"""
from __future__ import annotations

import importlib.util
import math
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

import numpy as np
import trimesh

from .config import Process, Tool

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Block:
    kind: str                       # rapid | feed | arc_cw | arc_ccw
    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None
    b: Optional[float] = None
    c: Optional[float] = None
    i: Optional[float] = None
    j: Optional[float] = None
    f: Optional[float] = None
    comment: Optional[str] = None


@dataclass
class Operation:
    op_id: str
    name: str
    tool: Tool
    rpm: int
    mode: str                       # 3axis | 5axis_rtcp
    feed_cut: float
    feed_plunge: float
    coolant: bool
    blocks: List[Block] = field(default_factory=list)


@dataclass
class Program:
    part_id: str
    op_id: str
    number: int
    wcs: str
    operations: List[Operation]

    @property
    def five_axis(self) -> bool:
        return any(op.mode == "5axis_rtcp" for op in self.operations)


@lru_cache(maxsize=1)
def _geo():
    spec = importlib.util.spec_from_file_location(
        "impeller_geo", ROOT / "scripts" / "build_nasa_closed_impeller.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def design_bbox(path: str) -> dict:
    m = trimesh.load(path, force="mesh")
    lo, hi = m.bounds
    return {k: [round(float(lo[i]), 3), round(float(hi[i]), 3)] for i, k in enumerate("xyz")}


def _design_work_offset(p: Process) -> float:
    """设计模型局部 z -> 工作坐标 z 的平移量（由毛坯底余量 + 顶面零位推导）。"""
    bb = design_bbox(p.part["design_file"])
    stock_bottom = float(p.stock["world_z_mm"][0])
    stock_top = float(p.stock["world_z_mm"][1])
    design_world_bottom = stock_bottom + float(p.stock["margins_mm"]["bottom"])
    return design_world_bottom - bb["z"][0] - stock_top


def _preform_blocks(p: Process, op: dict) -> List[Block]:
    s = op["strategy"]
    r = float(s["radius_mm"])
    inner = float(s["inner_x_mm"])
    rp = float(op["feed_plunge"])
    f = float(op["feed_cut"])
    retract = float(p.safety["retract_z_work_mm"])
    rate = float(p.safety["safe_z_work_mm"])
    blocks: List[Block] = []
    z = float(s["z_start_mm"])
    end = float(s["z_end_mm"])
    level = 0
    while z > end - 1e-6:
        level += 1
        blocks.append(Block("rapid", x=r, y=0.0, z=rate, b=0.0, c=0.0,
                            comment=f"第 {level} 层安全高度定位"))
        blocks.append(Block("feed", z=z, f=rp, comment=f"第 {level} 层下刀"))
        blocks.append(Block("arc_ccw", x=r, y=0.0, z=z, i=-r, j=0.0, f=f,
                            comment="整圆去四角"))
        blocks.append(Block("rapid", z=retract))
        z -= float(s["step_z_mm"])
    return blocks


def _channel_points(p: Process, op: dict) -> List[tuple]:
    geo = _geo()
    shift = _design_work_offset(p)
    n = int(op["strategy"]["points"])
    t_grid, theta = geo.camber_theta()
    # camber_theta() 给出的是叶片中线角；流道中心在两叶片之间，偏移半个叶距。
    half_pitch = 180.0 / geo.Z_BLADES
    out = []
    for k in range(n):
        t = 1.0 - k / (n - 1.0)
        r_h = geo.R1H + (geo.R2 - geo.R1H) * t
        r_s = geo.R1S + (geo.R2 - geo.R1S) * t
        r = (r_h + r_s) / 2.0
        z_design = (geo.z_hub(r_h) + geo.z_shroud(r_s)) / 2.0
        z_work = z_design + shift
        th = float(np.interp(t, t_grid, theta)) + math.radians(half_pitch)
        if z_work < float(op["strategy"]["lateral_z_mm"]):
            continue
        out.append((r * math.cos(th), r * math.sin(th), z_work, math.degrees(th)))
    return out


def _passage_blocks(p: Process, op: dict) -> List[Block]:
    geo = _geo()
    s = op["strategy"]
    pts = _channel_points(p, op)
    if len(pts) < 5:
        raise ValueError("流道中线采样点不足，无法生成五轴刀路")
    entry_r = float(s["entry_radius_mm"])
    lateral_z = float(s["lateral_z_mm"])
    b0 = float(s["b_min_deg"])
    span = float(s["b_span_deg"])
    rate = float(p.safety["safe_z_work_mm"])
    pitch = 360.0 / geo.Z_BLADES
    blocks: List[Block] = []
    # 封闭叶轮从“进气口（叶轮眼）”进入流道：流道出口在夹持带下方，
    # 若从外圆进入会切穿盖板（实测过切），故改由进气口下刀、向外圆方向走刀。
    pts_in = list(reversed(pts))          # 进气口 -> 外圆出口
    if len(pts_in) < 5:
        raise ValueError("流道中线采样点不足")
    entry = pts_in[0]
    mid = pts_in[len(pts_in) // 2]
    for ch in range(geo.Z_BLADES):
        base = ch * pitch
        ca, sa = math.cos(math.radians(base)), math.sin(math.radians(base))

        def rot(x: float, y: float) -> tuple:
            return (x * ca - y * sa, x * sa + y * ca)

        th_mid = math.radians(mid[3] + base)
        c_slot = (-(mid[3] + base)) % 360.0
        ex, ey = rot(entry[0], entry[1])
        blocks.append(Block("rapid", x=ex, y=ey, z=rate, b=0.0, c=c_slot,
                            comment=f"PASSAGE {ch + 1}/{geo.Z_BLADES} 进气口定位"))
        blocks.append(Block("feed", z=entry[2], f=float(op["feed_plunge"]),
                            comment="进气口下刀"))
        n = len(pts_in)
        for i, (x, y, zw, _c) in enumerate(pts_in):
            b = b0 + span * math.sin(math.pi * i / max(1, n - 1))
            rx, ry = rot(x, y)
            blocks.append(Block("feed", x=rx, y=ry, z=zw, b=b, c=c_slot,
                                f=float(op["feed_cut"])))
        for i in range(n - 2, -1, -1):
            x, y, zw, _c = pts_in[i]
            b = b0 + span * math.sin(math.pi * i / max(1, n - 1))
            rx, ry = rot(x, y)
            blocks.append(Block("feed", x=rx, y=ry, z=zw, b=b, c=c_slot,
                                f=float(op["feed_return"])))
        blocks.append(Block("feed", x=ex, y=ey, z=entry[2], b=0.0, c=c_slot,
                            f=float(op["feed_return"])))
        blocks.append(Block("rapid", z=rate))
    return blocks


def _back_face_blocks(p: Process, op: dict) -> List[Block]:
    s = op["strategy"]
    rate = float(p.safety["safe_z_work_mm"])
    retract = float(p.safety["retract_z_work_mm"])
    z = float(s["face_z_mm"])
    f = float(op["feed_cut"])
    r = float(s["face_radius_mm"])
    blocks: List[Block] = [
        Block("rapid", x=float(s["face_radius_mm"]) + 16.0, y=0.0, z=rate, b=0.0, c=0.0),
        Block("feed", z=z, f=float(op["feed_plunge"])),
        Block("feed", x=r, y=0.0, z=z, f=float(op["feed_plunge"])),
    ]
    while r > 0.001:
        blocks.append(Block("arc_ccw", x=r, y=0.0, z=z, i=-r, j=0.0, f=f,
                            comment=f"背面环形面铣 r{r:g}"))
        nr = max(r - float(s["face_step_mm"]), 0.0)
        blocks.append(Block("feed", x=nr, y=0.0, z=z, f=f))
        r = nr
    blocks.append(Block("rapid", z=retract))
    return blocks


def _lower_od_blocks(p: Process, op: dict) -> List[Block]:
    s = op["strategy"]
    rate = float(p.safety["safe_z_work_mm"])
    retract = float(p.safety["retract_z_work_mm"])
    z = float(s["face_z_mm"])
    bottom = float(s["od_bottom_mm"])
    rc = float(s["od_radius_mm"]) + float(p.tools[s["tool2"]].diameter_mm) / 2.0
    blocks: List[Block] = [
        Block("rapid", x=rc, y=0.0, z=rate, b=0.0, c=0.0),
        Block("feed", z=z, f=float(s["feed_plunge2"])),
    ]
    while z > bottom + 1e-6:
        z = max(z - float(s["od_step_z_mm"]), bottom)
        blocks.append(Block("arc_cw", x=rc, y=0.0, z=z, i=-rc, j=0.0,
                            f=float(s["feed_cut2"]), comment=f"螺旋下刀至 Z{z:g}"))
    blocks.append(Block("arc_cw", x=rc, y=0.0, z=bottom, i=-rc, j=0.0,
                        f=float(s["feed_cut2"])))
    blocks.append(Block("rapid", z=retract))
    return blocks


def build_op1(p: Process) -> Program:
    op = p.op("OP1")
    return Program(p.part["id"], "OP1", 1001, "G54", [Operation(
        "OP1", op["name"], p.tools[op["tool"]], int(op["rpm"]), op["mode"],
        float(op["feed_cut"]), float(op["feed_plunge"]), bool(op["coolant"]),
        _preform_blocks(p, op))])


def build_op2(p: Process) -> Program:
    op = p.op("OP2")
    return Program(p.part["id"], "OP2", 1002, "G54", [Operation(
        "OP2", op["name"], p.tools[op["tool"]], int(op["rpm"]), op["mode"],
        float(op["feed_cut"]), float(op["feed_plunge"]), bool(op["coolant"]),
        _passage_blocks(p, op))])


def build_op3(p: Process) -> Program:
    op = p.op("OP3")
    s = op["strategy"]
    t1 = p.tools[op["tool"]]
    t2 = p.tools[s["tool2"]]
    return Program(p.part["id"], "OP3", 1003, "G54", [
        Operation("OP3-A", op["name"] + " / 背面面铣", t1, int(op["rpm"]), "3axis",
                  float(op["feed_cut"]), float(op["feed_plunge"]), True,
                  _back_face_blocks(p, op)),
        Operation("OP3-B", op["name"] + " / 下部外圆", t2, int(s["rpm2"]), "3axis",
                  float(s["feed_cut2"]), float(s["feed_plunge2"]), True,
                  _lower_od_blocks(p, op)),
    ])


def build_all(p: Process) -> List[Program]:
    return [build_op1(p), build_op2(p), build_op3(p)]
