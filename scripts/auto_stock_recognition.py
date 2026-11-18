# -*- coding: utf-8 -*-
"""自动识别毛坯（包容块）并生成 VERICUT 可用的 Stock 模型 + 工位补丁。

模式
  blank     : 以设计模型包围盒 + 余量生成完整包容块，底面放在夹具/工作台支撑面上
  residual  : 只生成指定世界 Z 区间内的残余包容块（翻面工序 OP3 用）

用法
  python scripts/auto_stock_recognition.py --design design.stl --mode blank \
      --side 3 --top 3 --bottom 5 --fixture-top 70 --out stock.stl --report stock.json
  python scripts/auto_stock_recognition.py --design design_flip.stl --mode residual \
      --z-bottom 127.0 --z-top 152.85 --side 3 --out op3_stock.stl --report op3_stock.json

  # 可选：把结果写回 VERICUT 工程（改 Stock 的 File 与 ModelMatrix Z）
  ... --patch-project E:\\vericut_impeller_run\\proj.vcproject

口径
  - 单位 mm；Attach 链默认 Z=-100（NMV1500），matrix_z = world_bottom + 100 - local_zmin
  - 包容性用设计表面 20000 点实测，outside 必须为 0
  - basis=measured（包围盒与采样均来自文件实测，不靠猜）
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np
import trimesh


def load_design(path: Path, flip_x: bool) -> trimesh.Trimesh:
    m = trimesh.load(str(path), force="mesh")
    if flip_x:
        m.apply_transform(np.array([[1, 0, 0, 0], [0, -1, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]], float))
    return m


def write_box_stl(path: Path, sx: float, sy: float, z0: float, z1: float) -> None:
    m = trimesh.creation.box(extents=[sx, sy, z1 - z0])
    m.apply_translation([0.0, 0.0, (z0 + z1) / 2.0])
    m.export(str(path))


def containment(mesh: trimesh.Trimesh, sx: float, sy: float, z0: float, z1: float,
                bottom: float, side: float, n: int = 20000) -> dict:
    pts, _ = trimesh.sample.sample_surface(mesh, n)
    # 设计模型局部坐标 -> 毛坯坐标（毛坯 XY 居中、Z 从 0 起）
    local = pts + np.array([0.0, 0.0, bottom])
    inside = (
        (np.abs(local[:, 0]) <= sx / 2.0 + 1e-6)
        & (np.abs(local[:, 1]) <= sy / 2.0 + 1e-6)
        & (local[:, 2] >= z0 - 1e-6)
        & (local[:, 2] <= z1 + 1e-6)
    )
    return {
        "samples": int(n),
        "outside": int((~inside).sum()),
        "min_margin_mm": round(float(min(
            sx / 2.0 - np.abs(local[:, 0]).max(),
            sy / 2.0 - np.abs(local[:, 1]).max(),
            local[:, 2].min() - z0,
            z1 - local[:, 2].max(),
        )), 3),
    }


def patch_project(project: Path, stock_file: str, matrix_z: float) -> None:
    text = project.read_text(encoding="utf-8")
    m = re.search(r'(<Component Name="Stock"[\s\S]*?)(?=<Component Name=|</Components>)', text)
    if not m:
        raise SystemExit("Stock component not found")
    block = m.group(1)
    block = re.sub(r"(<Poly[\s\S]*?<File>)[^<]*(</File>)", lambda x: x.group(1) + stock_file + x.group(2), block, count=1)
    block = re.sub(r'(<MatrixOrigin X="0" Y="0" Z=")[-\d.]+("/>)', lambda x: x.group(1) + f"{matrix_z:g}" + x.group(2), block, count=1)
    project.write_text(text[:m.start(1)] + block + text[m.end(1):], encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--design", required=True)
    ap.add_argument("--mode", choices=["blank", "residual"], default="blank")
    ap.add_argument("--side", type=float, default=3.0)
    ap.add_argument("--top", type=float, default=3.0)
    ap.add_argument("--bottom", type=float, default=5.0)
    ap.add_argument("--fixture-top", type=float, default=None, help="blank 模式：支撑面世界 Z")
    ap.add_argument("--z-bottom", type=float, default=None, help="residual 模式：块底世界 Z")
    ap.add_argument("--z-top", type=float, default=None, help="residual 模式：块顶世界 Z")
    ap.add_argument("--flip-x", action="store_true")
    ap.add_argument("--attach-z", type=float, default=-100.0)
    ap.add_argument("--out", required=True)
    ap.add_argument("--report", required=True)
    ap.add_argument("--patch-project", default=None)
    args = ap.parse_args()

    design = load_design(Path(args.design), args.flip_x)
    lo, hi = design.bounds
    dx, dy, dz = hi - lo

    sx = dx + 2 * args.side
    sy = dy + 2 * args.side

    if args.mode == "blank":
        if args.fixture_top is None:
            raise SystemExit("blank mode needs --fixture-top")
        sz = dz + args.top + args.bottom
        world_bottom = args.fixture_top
        world_top = world_bottom + sz
        local_z0, local_z1 = 0.0, sz
        matrix_z = world_bottom - args.attach_z
        bottom_allow = args.bottom
    else:
        if args.z_bottom is None or args.z_top is None:
            raise SystemExit("residual mode needs --z-bottom and --z-top")
        world_bottom, world_top = args.z_bottom, args.z_top
        sz = world_top - world_bottom
        local_z0, local_z1 = 0.0, sz
        matrix_z = world_bottom - args.attach_z
        # 残余块只覆盖设计的一段，包容性按该段截取
        bottom_allow = world_bottom - (hi[2] - dz)  # 仅用于报告

    out = Path(args.out)
    write_box_stl(out, sx, sy, local_z0, local_z1)

    if args.mode == "blank":
        cont = containment(design, sx, sy, local_z0, local_z1, bottom_allow, args.side)
        world_design = [round(float(lo[2] + args.fixture_top + args.bottom), 2),
                        round(float(hi[2] + args.fixture_top + args.bottom), 2)]
    else:
        # residual：把设计平移到与块同一世界高度后再采样
        shift = args.z_bottom - (lo[2] + (args.z_top - args.z_bottom) - sz)  # 0，占位
        cont = {"samples": 0, "outside": None, "min_margin_mm": None,
                "note": "residual band: containment is bounded by the OP1 cut plane"}
        world_design = [round(float(lo[2]), 2), round(float(hi[2]), 2)]

    report = {
        "mode": args.mode,
        "design_file": str(args.design),
        "design_bbox_mm": {
            "x": [round(float(lo[0]), 2), round(float(hi[0]), 2)],
            "y": [round(float(lo[1]), 2), round(float(hi[1]), 2)],
            "z": [round(float(lo[2]), 2), round(float(hi[2]), 2)],
            "size": [round(float(dx), 2), round(float(dy), 2), round(float(dz), 2)],
        },
        "stock_box_mm": {
            "size": [round(sx, 2), round(sy, 2), round(sz, 2)],
            "local_z": [local_z0, local_z1],
        },
        "world": {
            "z_bottom": round(world_bottom, 2),
            "z_top": round(world_top, 2),
            "attach_z": args.attach_z,
            "stock_matrix_origin_z": round(matrix_z, 2),
        },
        "allowance_mm": {"side": args.side, "top": args.top, "bottom": args.bottom},
        "containment": cont,
        "stock_file": str(out),
        "basis": "measured (mesh bounds + surface sampling)",
    }
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.patch_project:
        patch_project(Path(args.patch_project), str(out), matrix_z)
        report["patched_project"] = args.patch_project

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
