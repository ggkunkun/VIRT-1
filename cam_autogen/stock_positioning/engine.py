"""毛坯摆放与装夹定位计算引擎。

计算输出 ``StockSetup``（夹具类型、WCS 原点、装夹夹持深度、悬伸长度、碰撞防区 ``fixture_zones``、
规范依据与告警），供程序生成（M3）和路径校验（Verification）消费。
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from cam_autogen.contracts import FixtureZone, ProcessType, StockSetup, WorkpieceSpec
from cam_autogen.stock_positioning.standards import lookup_positioning_standards

ENGINE_VERSION = "stock-pos-1.0.0"
FACE_ALLOW_MM = 1.0
CHUCK_JAW_RADIAL_CLEARANCE_MM = 2.0
CHUCK_SAFETY_MARGIN_Z_MM = 5.0


def compute_stock_setup(
    wp: WorkpieceSpec,
    process_type: ProcessType,
    enable_web_lookup: bool = False,
    fetcher: Optional[Callable[[str, float], str]] = None,
) -> StockSetup:
    """根据工件特征、毛坯规格与工艺类型自动计算最优毛坯摆放与夹具禁区。"""
    std = lookup_positioning_standards(process_type.value, enable_web=enable_web_lookup, fetcher=fetcher)
    rules_applied: List[Dict[str, Any]] = list(std["rules"])
    if std.get("web_references"):
        rules_applied.append({"id": "WEB-REF", "web_status": std["web_status"],
                              "basis": std["basis"], "references": std["web_references"]})
    else:
        rules_applied.append({"id": "LOOKUP-AUDIT", "web_status": std["web_status"], "basis": std["basis"]})

    warnings: List[str] = []
    if process_type == ProcessType.MILLING or wp.envelope.type == "prismatic":
        return _setup_milling(wp, rules_applied, warnings)
    return _setup_turning(wp, rules_applied, warnings)


def _setup_milling(wp: WorkpieceSpec, rules_applied: List[Dict[str, Any]], warnings: List[str]) -> StockSetup:
    px = wp.envelope.x or 100.0
    py = wp.envelope.y or 80.0
    pz = wp.envelope.z or 30.0
    sx = wp.stock.x or (px + 4.0)
    sy = wp.stock.y or (py + 4.0)
    sz = wp.stock.z or (pz + 10.0)
    off_x = round((sx - px) / 2.0, 3)
    off_y = round((sy - py) / 2.0, 3)

    if sx < px or sy < py or sz < pz + FACE_ALLOW_MM:
        warnings.append(f"毛坯尺寸 ({sx}×{sy}×{sz}) 偏小，可能余量不足以包覆成品 ({px}×{py}×{pz})")

    # 最大铣削深度决定最低安全伸出高度
    max_feat_depth = 0.0
    for f in wp.features:
        if f.type in ("pocket", "slot", "keyway", "contour", "hole", "thread_hole"):
            max_feat_depth = max(max_feat_depth, float(f.params.get("depth", 0.0)))
    # 如果需要铣外形轮廓且下方有余量，伸出高度需至少覆盖零件高+2mm避让；否则保证底面夹持 >= 5mm
    need_outline = (sx - px > 0.2) or (sy - py > 0.2)
    extra_z = sz - pz - FACE_ALLOW_MM
    ideal_grip = max(5.0, min(12.0, 0.35 * sz))
    if need_outline and extra_z >= 7.0:
        # 垫高至露出零件全高+2mm，同时保持>=5mm夹持
        grip = max(5.0, min(ideal_grip, sz - (pz + FACE_ALLOW_MM + 2.0)))
    else:
        grip = min(ideal_grip, max(5.0, sz - max_feat_depth - 2.0))
        if grip < 5.0:
            grip = min(5.0, sz * 0.4)
            warnings.append(f"毛坯高度 {sz:.1f}mm 较薄，虎钳夹持仅 {grip:.1f}mm，建议使用定制台阶钳口或真空吸盘")
    stickout = round(sz - grip, 3)
    grip = round(grip, 3)

    if stickout / max(min(sx, sy), 1.0) > 2.5:
        warnings.append(f"毛坯伸出高宽比 {stickout / min(sx, sy):.2f} > 2.5，悬伸偏大建议降低切削参数")

    # 零件坐标系 Z=0 为精加工后顶面；毛坯顶面 Z=+FACE_ALLOW_MM；毛坯底面 Z=FACE_ALLOW_MM - sz
    z_top = FACE_ALLOW_MM
    z_jaw_top = round(z_top - stickout, 3)
    z_bot = round(z_top - sz, 3)
    # 虎钳固定/活动钳口分别位于 Y=[-off_y-25, -off_y] 与 Y=[py+off_y, py+off_y+25]，Z=[z_bot, z_jaw_top]
    zones = [
        FixtureZone(
            name="fixed_vise_jaw",
            kind="vise_jaw",
            box=[round(-off_x - 10.0, 3), round(px + off_x + 10.0, 3),
                 round(-off_y - 25.0, 3), round(-off_y, 3), z_bot, z_jaw_top],
        ),
        FixtureZone(
            name="movable_vise_jaw",
            kind="vise_jaw",
            box=[round(-off_x - 10.0, 3), round(px + off_x + 10.0, 3),
                 round(py + off_y, 3), round(py + off_y + 25.0, 3), z_bot, z_jaw_top],
        ),
        FixtureZone(
            name="parallel_blocks",
            kind="parallel",
            box=[round(-off_x, 3), round(px + off_x, 3),
                 round(-off_y, 3), round(py + off_y, 3), round(z_bot - 20.0, 3), z_bot],
        ),
    ]
    return StockSetup(
        part_id=wp.part_id,
        fixture="vise",
        wcs_origin="毛坯顶面加工基准(Z=0在精加工顶面，毛坯顶Z=+1.0mm)，XY零点位于成品左下角",
        stock_dims={"x": sx, "y": sy, "z": sz},
        part_offset_in_stock={"x": off_x, "y": off_y, "z_top_allow": FACE_ALLOW_MM},
        stickout_mm=stickout,
        grip_mm=grip,
        fixture_zones=zones,
        rules_applied=rules_applied,
        warnings=warnings,
    )


def _setup_turning(wp: WorkpieceSpec, rules_applied: List[Dict[str, Any]], warnings: List[str]) -> StockSetup:
    pd = wp.envelope.diameter or 40.0
    pl = wp.envelope.length or 80.0
    sd = wp.stock.diameter or (pd + 4.0)
    sl = wp.stock.length or (pl + max(25.0, 0.9 * sd))

    if sd < pd:
        warnings.append(f"棒料直径 Ø{sd} 小于零件最大外径 Ø{pd}，无法包覆成品")

    min_grip = max(18.0, 0.8 * sd)
    rec_grip = max(20.0, 1.0 * sd)
    required_stickout = pl + FACE_ALLOW_MM + CHUCK_SAFETY_MARGIN_Z_MM
    available_grip = sl - required_stickout

    if available_grip < min_grip:
        # 尽量保证安全退刀空间，压缩夹持并发出严格告警
        grip = max(10.0, sl - (pl + FACE_ALLOW_MM + 2.0))
        warnings.append(
            f"棒料长度 {sl:.1f}mm 较短（需加工 {pl:.1f}mm + 端面 {FACE_ALLOW_MM:.1f}mm + "
            f"夹持 {min_grip:.1f}mm），实际夹持仅 {grip:.1f}mm，建议换用更长毛坯"
        )
    else:
        grip = min(rec_grip, available_grip)
    stickout = round(sl - grip, 3)
    grip = round(grip, 3)

    ld_ratio = stickout / max(sd, 1.0)
    fixture = "three_jaw_chuck"
    # 卡爪区间在零件坐标系 [z_chuck_back, z_chuck_face]
    # 零件 Z=0 在右端面，毛坯右端 Z=+FACE_ALLOW_MM，左端 Z = FACE_ALLOW_MM - sl，卡爪右端面 Z = FACE_ALLOW_MM - stickout
    z_chuck_face = round(FACE_ALLOW_MM - stickout, 3)
    z_chuck_back = round(z_chuck_face - max(grip, 25.0) - 30.0, 3)
    zones = [
        FixtureZone(
            name="three_jaw_chuck_body",
            kind="chuck_jaw",
            # [zmin, zmax, rmin, rmax]
            box=[z_chuck_back, z_chuck_face, 0.0, round(sd / 2.0 + 45.0, 3)],
        )
    ]

    if ld_ratio > 3.0:
        has_axial_center_hole = any(f.type == "bore_axial" or f.on_axis for f in wp.features)
        if has_axial_center_hole:
            fixture = "three_jaw_chuck"
            warnings.append(f"悬伸长径比 L/D={ld_ratio:.2f} > 3.0 且含中心孔/内孔：无法使用尾座顶尖，建议使用中心架支撑")
        else:
            fixture = "chuck_tailstock"
            zones.append(
                FixtureZone(
                    name="tailstock_center",
                    kind="tailstock",
                    box=[5.0, 85.0, 0.0, 15.0],
                )
            )
            if ld_ratio > 6.0:
                warnings.append(f"悬伸长径比 L/D={ld_ratio:.2f} > 6.0：除尾座顶尖外建议增加中心架/跟刀架")
            else:
                warnings.append(f"悬伸长径比 L/D={ld_ratio:.2f} > 3.0：已启用尾座顶尖辅助支撑")

    return StockSetup(
        part_id=wp.part_id,
        fixture=fixture,
        wcs_origin="零件右端面回转中心(X=0, Z=0)，毛坯右端面 Z=+1.0mm，-Z 指向卡盘",
        stock_dims={"diameter": sd, "length": sl},
        part_offset_in_stock={"z_face_allow": FACE_ALLOW_MM, "chuck_face_z": z_chuck_face},
        stickout_mm=stickout,
        grip_mm=grip,
        fixture_zones=zones,
        rules_applied=rules_applied,
        warnings=warnings,
    )
