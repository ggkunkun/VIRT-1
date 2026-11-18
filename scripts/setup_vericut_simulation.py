# -*- coding: utf-8 -*-
"""为闭式叶轮五轴仿真准备 VERICUT 工程：毛坯 STL + 工程文件（复用 DMG NMV1500 样例机床）。

2026-11-12 修复（成品优先 / product-first）：
    原实现把 STOCK_R=135 / STOCK_H=82 硬编码成 Cylinder 毛坯，
    完全脱离成品几何（design_stl），report basis 自标 "asserted"，
    换非回转体复杂曲面零件时就会产出"超长圆柱"。

    现在毛坯一律由成品包围盒程序化派生（stock_derivation.derive_stock_strict），
    并带体积比/长径比熔断；非回转体自动改为方块料，不再强行套圆柱。
    证据优先级：成品 STL 实测 > 显式声明的设计包络（仍须过 sanity 门）。
    顶层不再有写文件副作用，派生函数可被独立 import 验证。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from stock_derivation import (BBox, StockSpec, bbox_from_mesh, derive_stock_strict,
                              infer_is_revolution, inverse_derive_from_sample)

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "artifacts" / "aero_closed_impeller"
SAMPLE_PROJECT = Path(r"E:\samples\All\force_impeller_dmg_mori_nmv1500_fan30im_mm.vcproject")
SUPPORT = Path(r"E:\samples\Support_files")
TLS = Path(r"E:\samples\TLS\force-impeller.tls")
# 本件自建的工装与两把刀（D16 平刀 / D8 球头 D5 颈）：必须落在工程可访问的本仓路径，
# 否则 VERICUT 初始化加载缺失模型时会直接崩在原生层（EXCEPTION_ACCESS_VIOLATION）。
FIXTURE = OUT_DIR / "impeller_fixture.ply"
TOOL_LIB = OUT_DIR / "impeller_tools.tls"

stock_stl = OUT_DIR / "AE_CLOSED_IMPELLER_stock.stl"
design_stl = OUT_DIR / "AE_CLOSED_IMPELLER_NASA1975.stl"
# NC 优先级：几何驱动修正版 > 旧版。旧版沿叶片中曲面单程直穿，已被本轮证伪。
_nc_fixed = OUT_DIR / "AE_CLOSED_IMPELLER_5AXIS_FIXED.nc"
nc_file = _nc_fixed if _nc_fixed.exists() else OUT_DIR / "AE_CLOSED_IMPELLER_NASA1975_5AXIS.nc"
project_path = OUT_DIR / "AE_CLOSED_IMPELLER_VERICUT.vcproject"

# 零件语义默认值：避免调用方漏传时把别的零件（如"连杆衬套"）残留进来，
# 污染 infer_is_revolution / 毛坯形状推断。
DEFAULT_PART_TYPE = "航空发动机闭式离心叶轮（Shrouded Impeller），材料 TC11"

# 样本毛坯资产（E:\samples\Support_files）：VERICUT 官方 force-impeller 训练样本。
# 实测该样本毛坯 Φ48.00 x 30.00 @ z=-30..0，成品 Φ48.00 x 25.00 @ z=-25..0，
# 即约定为「外径与成品一致、仅下方多 5mm」的预车盘料，而非「成品包围盒 + 径向余量」。
# 本件必须沿用同一约定，否则毛坯与刀路假定不一致。
SAMPLE_STOCK_ASSET = SUPPORT / "force-impeller_stock.ply"
SAMPLE_DESIGN_ASSET = SUPPORT / "force-impeller_design.ply"

# 成品设计包络（仅在成品 STL 不可读时作为显式声明依据，仍须过 sanity 熔断门）。
# 来源：原脚本 STOCK_R=135 / STOCK_H=82 反推的叶轮设计包络，已转为具名规格而非魔法数。
DESIGN_PRODUCT_BBOX = BBox(-135.0, 135.0, -135.0, 135.0, 0.0, 82.0)
IS_REVOLUTION = True          # 仅为默认件（闭式叶轮）的兜底；实际一律由 infer_is_revolution 推断
REVOLUTION_AXIS = "Z"

# 最近一次派生的样本反推证据（供 main()/swarm 记录）
LAST_INVERSE_EVIDENCE: Dict[str, Any] = {}


def derive_stock_from_product(
    design_mesh: Optional[Path] = None,
    part_type: str = "",
    stock_hint: str = "",
    sample_stock_mesh: Optional[Path] = None,
    sample_vcproject: Optional[Path] = None,
    sample_design_mesh: Optional[Path] = None,
) -> Tuple[StockSpec, str]:
    """从成品几何派生毛坯；返回 (毛坯规格, 证据依据)。

    2026-11-14：不再硬编码 IS_REVOLUTION=True。形状由零件族语义 + 包围盒对称性推断；
    提供样本毛坯时按样本逐面余量反推（inverse_derive_from_sample）。
    证据宪法：不允许脱离成品几何硬编码圆柱。成品 STL 缺失时降级为显式声明的
    设计包络，但仍必须经过 derive_stock_strict 的合理性熔断。
    """
    global LAST_INVERSE_EVIDENCE
    LAST_INVERSE_EVIDENCE = {}
    mesh = design_mesh or design_stl
    if mesh is not None and Path(mesh).exists():
        if sample_stock_mesh is not None and Path(sample_stock_mesh).exists():
            ev = inverse_derive_from_sample(
                str(mesh), str(sample_stock_mesh),
                str(sample_vcproject) if sample_vcproject else None,
                part_type=part_type, stock_hint=stock_hint,
                sample_design_mesh=str(sample_design_mesh) if sample_design_mesh else None)
            spec = ev.pop("stock_spec")
            LAST_INVERSE_EVIDENCE = ev
            return spec, "measured_from_sample_inverse_derivation"
        product = bbox_from_mesh(str(mesh))
        basis = "measured_from_product_mesh"
    else:
        product = DESIGN_PRODUCT_BBOX
        basis = "declared_product_spec_with_sanity_gate"
    if part_type or stock_hint or design_mesh is not None:
        is_rev, reason = infer_is_revolution(product, part_type=part_type, stock_hint=stock_hint)
    else:
        is_rev, reason = IS_REVOLUTION, "default_closed_impeller"
    LAST_INVERSE_EVIDENCE = {"inferred_is_revolution": is_rev, "inference_reason": reason,
                             "product_size_mm": [round(v, 4) for v in product.size]}
    spec = derive_stock_strict(product, is_revolution=is_rev, axis=REVOLUTION_AXIS)
    return spec, basis


def build_stock_shape(spec: StockSpec):
    """按派生规格构造毛坯几何：回转体=圆柱，非回转体=方块料。

    build123d 延迟导入：毛坯派生逻辑可在无 CAD 环境独立验证（证据宪法）。
    """
    from build123d import Align, Box, Cylinder
    if spec.shape == "cylinder":
        return Cylinder(
            spec.dims["diameter"] / 2.0,
            spec.dims["height"],
            align=(Align.CENTER, Align.CENTER, Align.MIN),
        )
    d = spec.dims
    return Box(d["dx"], d["dy"], d["dz"],
               align=(Align.CENTER, Align.CENTER, Align.MIN))


def export_stock_stl(spec: StockSpec, path: Path, segments: int = 128) -> None:
    """纯标准库写二进制 STL 毛坯（按派生规格的真实坐标：box 原点=最小角，cylinder 原点=底面圆心）。"""
    import math
    import struct
    tris = []
    if spec.shape == "box":
        x0, y0, z0 = spec.origin
        x1, y1, z1 = x0 + spec.dims["dx"], y0 + spec.dims["dy"], z0 + spec.dims["dz"]
        v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
             (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        quads = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
        for a, b, c, d in quads:
            tris += [(v[a], v[b], v[c]), (v[a], v[c], v[d])]
    else:
        cx, cy, z0 = spec.origin
        r = spec.dims["diameter"] / 2.0
        z1 = z0 + spec.dims["height"]
        ring = [(cx + r * math.cos(2 * math.pi * k / segments),
                 cy + r * math.sin(2 * math.pi * k / segments)) for k in range(segments)]
        for k in range(segments):
            (xa, ya), (xb, yb) = ring[k], ring[(k + 1) % segments]
            tris += [((xa, ya, z0), (xb, yb, z0), (xb, yb, z1)), ((xa, ya, z0), (xb, yb, z1), (xa, ya, z1)),
                     ((cx, cy, z0), (xb, yb, z0), (xa, ya, z0)), ((cx, cy, z1), (xa, ya, z1), (xb, yb, z1))]
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(b"virtu stock derived from product/sample".ljust(80, b" "))
        fh.write(struct.pack("<I", len(tris)))
        for t in tris:
            fh.write(struct.pack("<3f", 0.0, 0.0, 0.0))
            for p in t:
                fh.write(struct.pack("<3f", *p))
            fh.write(b"\x00\x00")


def _stock_stl_matches(spec: StockSpec, path: Path, tol: float = 0.6) -> bool:
    """缓存毛坯 STL 是否与当前派生规格一致（形状 + 包围盒）；不一致必须重生成。"""
    if not path.exists():
        return False
    try:
        from stock_derivation import classify_stock_mesh_shape
        bb = bbox_from_mesh(str(path))
        shape = classify_stock_mesh_shape(str(path))
    except Exception:
        return False
    sx, sy, sz = bb.size
    if spec.shape == "box":
        want = (spec.dims["dx"], spec.dims["dy"], spec.dims["dz"])
        if shape != "box":
            return False
    else:
        d = spec.dims["diameter"]
        want = (d, d, spec.dims["height"])
        if shape == "box":
            return False
    return all(abs(a - b) <= tol for a, b in zip((sx, sy, sz), want))


def main(
    design_mesh: Optional[str] = None,
    part_type: str = "",
    stock_hint: str = "",
    sample_stock_mesh: Optional[str] = None,
    sample_vcproject: Optional[str] = None,
    sample_design_mesh: Optional[str] = None,
) -> Dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    part_type = part_type or DEFAULT_PART_TYPE
    # 包容块毛坯优先（用户 2026-11-17 要求）：五轴加工中心用「bbox + 余量」的长方块，
    # 与机床 X/Y/Z 对齐；不再使用圆柱/回转仿形毛坯。
    box_report = OUT_DIR / "blank_box_report.json"
    nearnet = OUT_DIR / "blank_nearnet_report.json"
    blank_src = box_report if box_report.exists() else nearnet
    if blank_src.exists() and design_mesh is None and not sample_stock_mesh:
        nn = json.loads(blank_src.read_text(encoding="utf-8"))
        is_box = blank_src == box_report
        stl = OUT_DIR / "AE_CLOSED_IMPELLER_stock.stl"
        if stl.exists():
            report = {
                "stock_stl": str(stl), "stock_bytes": stl.stat().st_size,
                "stock_shape": "block" if is_box else "nearnet_offset",
                "stock_dims": nn["measured"]["size_mm"],
                "stock_origin": [0.0, 0.0, nn["measured"]["bbox_min"][2]],
                "stock_source": "block_bbox_plus_allowance" if is_box else "nearnet_offset_blank",
                "stock_basis": ("measured_from_product_bbox_plus_allowance" if is_box
                                else "measured_from_product_offset_profile"),
                "blank_profile": nn.get("profile_points", []),
                "allowance_mm": nn["allowance_mm"],
                "part_type": part_type, "inferred_is_revolution": False,
                "design_stl": str(design_stl), "nc_file": str(nc_file),
                "project": str(project_path),
                "basis": "measured (bbox+allowance block; not a cylinder)",
            }
            text = SAMPLE_PROJECT.read_text(encoding="utf-8", errors="ignore")
            repl = {
                "force-impeller_stock.ply": str(stl),
                "force-impeller_design.ply": str(design_stl),
                "force-impeller.nc": str(nc_file),
                "force-impeller_fixture1.ply": str(FIXTURE),
                "force-impeller_fixture2.ply": str(FIXTURE),
                "force-impeller_fixture3.ply": str(FIXTURE),
                "<Library>force-impeller.tls</Library>": f"<Library>{TOOL_LIB}</Library>",
                # 与正确案例对齐：夹具 PLY 自身 z=145..170、MatrixOrigin Z=0 →
                # 夹具顶 world=170；毛坯 STL 自身 z=-5..77.85，MatrixOrigin Z=175
                # → 毛坯底面 world=170，正好贴合夹具顶（gap=0），Design 随动。
                # 注：原注释"world 70"是把案例 Attach=-100 的局部坐标误套到本件，
                # 本件 Attach 链无 -100 偏移，真实接触面是 world 170。
                '<MatrixOrigin X="0" Y="0" Z="200"/>': '<MatrixOrigin X="0" Y="0" Z="175"/>',
                # G57 坐标系是 Stock 的子节点，随毛坯一起下移，保持案例中的相对层级。
                '<Position X="0" Y="0" Z="200"/>': '<Position X="0" Y="0" Z="175"/>',
            }
            for a, b in repl.items():
                text = text.replace(a, b)
            # 移除样例模板残留的 Cylinder 占位节点（毛坯必须且只能是长方体包容块，
            # 不得在 Stock 组件内保留任何圆柱定义，即使 Visible/Enabled=off）。
            import re as _re
            text = _re.sub(r'\s*<Cylinder\b[^>]*>.*?</Cylinder>', '', text, flags=_re.S)
            project_path.write_text(text, encoding="utf-8")
            # 2026-11-17 修正：把主工程同步到 vericut_run 副本（实际跑仿真的目录），
            # 防止副本残留 Z=200 导致毛坯悬空 25mm。两副本必须逐字节一致。
            run_copy = OUT_DIR / "vericut_run" / project_path.name
            if run_copy.parent.exists():
                run_copy.write_text(text, encoding="utf-8")
            (OUT_DIR / "vericut_setup.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return report
    # 未显式给样本时，默认沿用 force-impeller 训练样本的毛坯约定（逐面余量反推）
    if sample_stock_mesh is None and SAMPLE_STOCK_ASSET.exists():
        sample_stock_mesh = str(SAMPLE_STOCK_ASSET)
        if sample_design_mesh is None and SAMPLE_DESIGN_ASSET.exists():
            sample_design_mesh = str(SAMPLE_DESIGN_ASSET)
    target_design = Path(design_mesh).resolve() if design_mesh else design_stl

    # 1) 毛坯：由成品几何 / 样本反推派生（不再硬编码圆柱、不再盲目复用缓存）
    spec, basis = derive_stock_from_product(
        target_design if design_mesh else None,
        part_type=part_type, stock_hint=stock_hint,
        sample_stock_mesh=Path(sample_stock_mesh) if sample_stock_mesh else None,
        sample_vcproject=Path(sample_vcproject) if sample_vcproject else None,
        sample_design_mesh=Path(sample_design_mesh) if sample_design_mesh else None)
    inverse_ev = dict(LAST_INVERSE_EVIDENCE)
    if target_design.resolve() != design_stl.resolve() or spec.shape == "box":
        out_stock = OUT_DIR / f"{target_design.stem}_stock_{spec.shape}.stl"
    else:
        out_stock = stock_stl
    if _stock_stl_matches(spec, out_stock):
        stock_source = "reused_existing_stock_stl_verified_against_spec"
    else:
        export_stock_stl(spec, out_stock)
        stock_source = "generated_stock_stl"
        if not _stock_stl_matches(spec, out_stock):
            raise RuntimeError(f"毛坯 STL 写出后与派生规格不一致: {out_stock}")

    # 2) 工程文件：样例机床 + 本件 NC / 毛坯 / 设计模型
    is_default_part = target_design.resolve() == design_stl.resolve() and not sample_vcproject
    if is_default_part:
        template = SAMPLE_PROJECT
        text = template.read_text(encoding="utf-8", errors="ignore")
        replacements = {
            "force-impeller_stock.ply": str(out_stock),
            "force-impeller_design.ply": str(target_design),
            "force-impeller.nc": str(nc_file),
            "force-impeller_fixture1.ply": str(SUPPORT / "force-impeller_fixture1.ply"),
            "force-impeller_fixture2.ply": str(SUPPORT / "force-impeller_fixture2.ply"),
            "force-impeller_fixture3.ply": str(SUPPORT / "force-impeller_fixture3.ply"),
            "<Library>force-impeller.tls</Library>": f"<Library>{TLS}</Library>",
            "DMG Mori, NMV1500, Mapps IV, 5 axis vertical mill, AC table, Metric, Force, Aerospace, Impeller, Autodiff":
                "DMG Mori NMV1500 - AE_CLOSED_IMPELLER_NASA1975 5-Axis Machining",
        }
        out_project = project_path
        out_nc = nc_file
    else:
        # 以样本工程为模板：仅替换其 Stock / Design 附着文件为本件派生结果
        from stock_derivation import parse_vcproject_setup
        template = Path(sample_vcproject) if sample_vcproject else SAMPLE_PROJECT
        text = template.read_text(encoding="utf-8", errors="ignore")
        setup = parse_vcproject_setup(str(template))
        replacements = {}
        if setup["stock_files"]:
            replacements[setup["stock_files"][0]] = str(out_stock)
        if setup["design_files"]:
            replacements[setup["design_files"][0]] = str(target_design)
        out_project = OUT_DIR / f"{target_design.stem}_VERICUT.vcproject"
        out_nc = Path(setup["nc_checked_for_rtcp"]) if setup.get("nc_checked_for_rtcp") else nc_file
    missing = [old for old in replacements if old not in text]
    for old, new in replacements.items():
        text = text.replace(old, new)
    out_project.write_text(text, encoding="utf-8")

    report = {
        "stock_stl": str(out_stock),
        "stock_bytes": out_stock.stat().st_size,
        "stock_shape": spec.shape,
        "stock_dims": spec.dims,
        "stock_origin": list(spec.origin),
        "stock_sanity": spec.sanity,
        "stock_source": stock_source,         # generated_stock_stl / reused_..._verified_against_spec
        "stock_basis": basis,                 # measured_from_sample_inverse_derivation / measured_from_product_mesh / declared_...
        "part_type": part_type,
        "stock_hint": stock_hint,
        "inferred_is_revolution": spec.shape == "cylinder",
        "inverse_sample_evidence": inverse_ev,
        "design_stl": str(target_design),
        "nc_file": str(out_nc),
        "project": str(out_project),
        "project_template": str(template),
        "sample_vcproject": str(sample_vcproject) if sample_vcproject else None,
        "replacements_not_found": missing,
        "basis": "measured (product/sample-derived stock / files written) / asserted (sample machine reused)",
    }
    report_name = "vericut_setup.json" if is_default_part else f"{target_design.stem}_vericut_setup.json"
    (OUT_DIR / report_name).write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return report


if __name__ == "__main__":
    main()
