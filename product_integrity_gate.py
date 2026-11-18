# -*- coding: utf-8 -*-
"""product_integrity_gate.py — 第四层：成品完整性校验门（防"拿毛坯当产品"）。

背景（2026-11-12 用户痛点）：
    仿真加工出的"产品"总是超长圆柱/毛坯体，而不是完整成品。
    除毛坯派生错误外，更深层是建模阶段成品可能退化成简单体，且缺少
    "加工结果是否真的形成完整产品"的验证门。

本模块提供三道证据门（Evidence Before Assertions，AGENTS.md §5）：
    1. 体积守恒门：每个 CAD 特征 ΔV != 0，且符号与特征类型一致
       （extrude>0 / cut<0 / fillet,chamfer,revolve != 0，AGENTS.md §2.A）。
    2. 成品几何门：实体有效（volume>0 / watertight / solid_count>=1）；
       检测"成品其实是圆柱毛坯"退化（填充率≈π/4 且面数<=6 且曲面<=2）；
       复杂曲面产品必须有足够非平面曲面。
    3. VERICUT Auto-Diff 门：红(过切)=0 为 Fatal；蓝(残料)<=2%；
       绿(合格)>=98%，即成品确实被完整加工出来。

证据宪法：缺少几何/仿真证据时**不得断言通过**，直接判失败并熔断。
不合格 -> ProductIntegrityError（可由 super_agent 转成 RCFA 熔断）。

用法：
    from product_integrity_gate import verify_product_integrity
    report = verify_product_integrity(features=..., geometry=..., autodiff=...)
    if not report.passed:  # 熔断
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

# ---- 阈值 --------------------------------------------------------------------
MIN_GREEN_RATIO = 0.98      # 绿色合格区覆盖率下限
MAX_GOUGE_RATIO = 0.0       # 红色过切零容忍（Fatal）
MAX_EXCESS_RATIO = 0.02     # 蓝色残料上限
MIN_CURVED_FACES = 3        # 复杂曲面成品至少应有的曲面数量
CYL_FILL_LOW, CYL_FILL_HIGH = 0.76, 0.80   # 圆柱填充率 π/4≈0.785 判定带
MAX_PRIMITIVE_FACES = 6     # 简单体（圆柱/方块）面数上限
MIN_FILL_RATIO = 0.01       # 体积/包围盒体积 下限（防空壳）


class ProductIntegrityError(Exception):
    """成品完整性校验未通过，触发熔断（RCFA 应由调用方产出）。"""

    def __init__(self, report: "GateReport"):
        self.report = report
        super().__init__("成品完整性熔断: " + " | ".join(report.failures))


# ---- 证据结构 ----------------------------------------------------------------
@dataclass
class FeatureDelta:
    """单个 CAD 特征的体积增量（mm^3），来自 CAD 内核实测，禁止断言。"""
    name: str
    kind: Literal["extrude", "cut", "fillet", "chamfer", "revolve", "other"]
    delta_v: float


@dataclass
class GeometryEvidence:
    """成品几何证据。可由 from_mesh() 从 STL/STEP 实测生成。"""
    volume: float
    bbox_volume: float
    solid_count: int = 1
    face_count: int = 0
    curved_face_count: int = 0
    is_watertight: bool = True
    #: False = 网格代理证据（STL 实测体积/包围盒，无 CAD 面/曲面拓扑数据）
    has_cad_face_data: bool = True

    @property
    def fill_ratio(self) -> float:
        return self.volume / self.bbox_volume if self.bbox_volume > 0 else 0.0


@dataclass
class AutoDiffEvidence:
    """VERICUT Auto-Diff 偏差图证据（比例，0~1）。"""
    gouge_ratio: float = 0.0    # 红：过切 -> Fatal
    excess_ratio: float = 0.0   # 蓝：残料 -> 补半精加工
    in_tol_ratio: float = 0.0   # 绿：合格（成品已成形）
    coverage_ratio: float = 1.0 # 参与比对的成品表面积覆盖率


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str
    fatal: bool = False


@dataclass
class GateReport:
    passed: bool
    checks: List[CheckResult] = field(default_factory=list)
    failures: List[str] = field(default_factory=list)
    circuit_breaker: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "circuit_breaker": self.circuit_breaker,
            "failures": list(self.failures),
            "checks": [
                {"name": c.name, "passed": c.passed, "fatal": c.fatal, "detail": c.detail}
                for c in self.checks
            ],
        }


# ---- 三道门 ------------------------------------------------------------------
def check_volume_conservation(features: Optional[List[FeatureDelta]]) -> CheckResult:
    """门1：每个特征 ΔV != 0 且符号符合物理（AGENTS.md §2.A）。"""
    if features is None:
        return CheckResult("volume_conservation", False,
                           "缺少特征体积增量证据，禁止断言通过")
    bad: List[str] = []
    for f in features:
        dv = float(f.delta_v)
        if abs(dv) < 1e-9:
            bad.append(f"{f.name}: ΔV=0 (空特征)")
        elif f.kind in ("extrude", "revolve") and dv < 0:
            bad.append(f"{f.name}: {f.kind} 应为 ΔV>0，实测 {dv:.3f}")
        elif f.kind == "cut" and dv > 0:
            bad.append(f"{f.name}: cut 应为 ΔV<0，实测 {dv:.3f}")
    ok = not bad and len(features) > 0
    return CheckResult("volume_conservation", ok,
                       f"{len(features)} 个特征体积守恒成立" if ok else "；".join(bad),
                       fatal=not ok)


def check_product_geometry(
    geometry: Optional[GeometryEvidence],
    require_curved_faces: bool = True,
) -> CheckResult:
    """门2：成品是真实完整实体，而非退化成圆柱/方块的毛坯。"""
    if geometry is None:
        return CheckResult("product_geometry", False,
                           "缺少成品几何证据，禁止断言通过")
    g = geometry
    problems: List[str] = []
    if g.volume <= 0:
        problems.append("成品体积 <= 0（空壳/退化体）")
    if g.solid_count < 1:
        problems.append("实体数 < 1")
    if not g.is_watertight:
        problems.append("非 watertight（破面/未封闭）")
    if g.fill_ratio < MIN_FILL_RATIO:
        problems.append(f"填充率 {g.fill_ratio:.4f} 过低（疑似空壳）")

    # 关键：识别"成品其实是圆柱毛坯"——填充率≈π/4 是主判据（对 CAD 与 STL 网格
    # 证据都成立），面数/曲面数约束仅在有 CAD 拓扑数据时才附加。
    is_cylinder_primitive = (
        CYL_FILL_LOW <= g.fill_ratio <= CYL_FILL_HIGH
        and (g.face_count == 0 or g.face_count <= MAX_PRIMITIVE_FACES)
        and (g.curved_face_count == 0 or g.curved_face_count <= 2)
    )
    if is_cylinder_primitive:
        problems.append(
            f"疑似圆柱毛坯退化（填充率 {g.fill_ratio:.3f}≈π/4，面数 {g.face_count}，"
            f"曲面 {g.curved_face_count}）——交付的不是完整产品")

    if (require_curved_faces and g.has_cad_face_data
            and g.curved_face_count < MIN_CURVED_FACES):
        problems.append(
            f"曲面数 {g.curved_face_count} < {MIN_CURVED_FACES}（复杂曲面成品未成形）")

    ok = not problems
    return CheckResult("product_geometry", ok,
                       "成品实体有效且非退化" if ok else "；".join(problems),
                       fatal=not ok)


def check_autodiff(autodiff: Optional[AutoDiffEvidence]) -> CheckResult:
    """门3：VERICUT Auto-Diff 红/蓝/绿偏差，验证成品确实被完整加工出来。"""
    if autodiff is None:
        return CheckResult("autodiff", False,
                           "缺少 VERICUT Auto-Diff 偏差图证据，禁止断言通过")
    a = autodiff
    problems: List[str] = []
    fatal = False
    if a.gouge_ratio > MAX_GOUGE_RATIO:
        problems.append(f"红色过切 {a.gouge_ratio:.4f} > {MAX_GOUGE_RATIO}（Fatal：立即停机改刀路）")
        fatal = True
    if a.excess_ratio > MAX_EXCESS_RATIO:
        problems.append(f"蓝色残料 {a.excess_ratio:.4f} > {MAX_EXCESS_RATIO}（需补半精加工）")
    if a.in_tol_ratio < MIN_GREEN_RATIO:
        problems.append(f"绿色合格区 {a.in_tol_ratio:.4f} < {MIN_GREEN_RATIO}（成品未完整成形）")
    if a.coverage_ratio < 0.95:
        problems.append(f"比对覆盖率 {a.coverage_ratio:.4f} 过低（证据不足）")
    ok = not problems
    return CheckResult("autodiff", ok,
                       "红=0 / 蓝<=2% / 绿>=98%，成品完整成形" if ok else "；".join(problems),
                       fatal=fatal)


def verify_product_integrity(
    *,
    features: Optional[List[FeatureDelta]] = None,
    geometry: Optional[GeometryEvidence] = None,
    autodiff: Optional[AutoDiffEvidence] = None,
    require_curved_faces: bool = True,
    strict: bool = False,
) -> GateReport:
    """统一入口。strict=True 时不合格直接抛 ProductIntegrityError（熔断）。"""
    checks = [
        check_volume_conservation(features),
        check_product_geometry(geometry, require_curved_faces),
        check_autodiff(autodiff),
    ]
    failures = [c.detail for c in checks if not c.passed]
    passed = not failures
    circuit_breaker = any((not c.passed) and c.fatal for c in checks)
    report = GateReport(passed=passed, checks=checks,
                        failures=failures, circuit_breaker=circuit_breaker)
    if strict and not passed:
        raise ProductIntegrityError(report)
    return report


# ---- 证据采集（可选，需 build123d / OCP）------------------------------------
def geometry_from_stl_pure(stl_path: str) -> GeometryEvidence:
    """纯标准库实测 STL 几何证据（散度定理算封闭体积），无需 build123d / OCP。

    二进制 STL 每个三角形 50 字节：12(normal) + 36(v1,v2,v3) + 2(attr)。
    体积 V = Σ v1·(v2×v3)/6。返回网格代理证据（has_cad_face_data=False）。
    """
    import struct

    from stock_derivation import bbox_from_stl

    bb = bbox_from_stl(stl_path)
    bbox_volume = ((bb.xmax - bb.xmin) * (bb.ymax - bb.ymin)
                   * (bb.zmax - bb.zmin))
    with open(stl_path, "rb") as f:
        data = f.read()
    if len(data) < 84:
        raise ValueError(f"STL 文件过短: {stl_path}")
    n_tri = struct.unpack_from("<I", data, 80)[0]
    if 84 + 50 * n_tri != len(data):
        raise ValueError("非标准二进制 STL（ASCII 需 CAD 内核解析）")
    volume = 0.0
    off = 84
    for _ in range(n_tri):
        v1 = struct.unpack_from("<fff", data, off + 12)
        v2 = struct.unpack_from("<fff", data, off + 24)
        v3 = struct.unpack_from("<fff", data, off + 36)
        volume += (v1[0] * (v2[1] * v3[2] - v2[2] * v3[1])
                   + v1[1] * (v2[2] * v3[0] - v2[0] * v3[2])
                   + v1[2] * (v2[0] * v3[1] - v2[1] * v3[0])) / 6.0
        off += 50
    return GeometryEvidence(
        volume=abs(volume), bbox_volume=float(bbox_volume),
        solid_count=1, face_count=0, curved_face_count=0,
        has_cad_face_data=False,
    )


def geometry_from_mesh(mesh_path: str) -> GeometryEvidence:
    """从成品网格读取几何证据。STL 优先纯标准库实测；STEP 才需要 CAD 内核。"""
    p = str(mesh_path)
    if not p.lower().endswith((".step", ".stp")):
        try:
            return geometry_from_stl_pure(p)
        except Exception as exc_stl:
            cad_error = exc_stl
    else:
        cad_error = RuntimeError("STEP 需要 build123d/OCP")

    try:
        from build123d import import_step, import_stl
        from OCP.BRepAdaptor import BRepAdaptor_Surface
        from OCP.GeomAbs import GeomAbs_Plane
        shape = import_step(p) if p.lower().endswith((".step", ".stp")) else import_stl(p)
        bb = shape.bounding_box()
        bbox_vol = ((bb.max.X - bb.min.X) * (bb.max.Y - bb.min.Y)
                    * (bb.max.Z - bb.min.Z))
        faces = shape.faces()
        curved = 0
        for face in faces:
            try:
                if BRepAdaptor_Surface(face.wrapped).GetType() != GeomAbs_Plane:
                    curved += 1
            except Exception:
                curved += 1
        return GeometryEvidence(
            volume=float(shape.volume), bbox_volume=float(bbox_vol),
            solid_count=max(1, len(shape.solids())), face_count=len(faces),
            curved_face_count=curved, has_cad_face_data=True,
        )
    except Exception as exc_cad:
        raise RuntimeError(
            f"无法采集成品几何证据（纯 STL 解析失败: {cad_error}；CAD 内核失败: {exc_cad}）"
        ) from exc_cad


def autodiff_from_report(data: Dict[str, Any]) -> AutoDiffEvidence:
    """把 VERICUT Auto-Diff 统计转成证据。接受比例或百分比。"""
    def _norm(v: Any) -> float:
        x = float(v)
        return x / 100.0 if x > 1.0 else x

    keys = {
        "gouge_ratio": ("gouge_ratio", "gouge", "red", "red_pct"),
        "excess_ratio": ("excess_ratio", "excess", "blue", "blue_pct"),
        "in_tol_ratio": ("in_tol_ratio", "in_tol", "green", "green_pct"),
        "coverage_ratio": ("coverage_ratio", "coverage"),
    }
    out: Dict[str, float] = {}
    for dst, candidates in keys.items():
        val = 1.0 if dst == "coverage_ratio" else 0.0
        for k in candidates:
            if k in data:
                val = _norm(data[k])
                break
        out[dst] = val
    return AutoDiffEvidence(**out)


if __name__ == "__main__":
    # ---- 自测：证明三道门能拦住"拿毛坯当产品" ----------------------------------
    cases = []

    good_features = [
        FeatureDelta("基体拉伸", "extrude", 185000.0),
        FeatureDelta("叶片曲面", "revolve", 42000.0),
        FeatureDelta("流道切除", "cut", -31000.0),
        FeatureDelta("进口圆角", "fillet", -820.0),
    ]
    good_geo = GeometryEvidence(volume=196000.0, bbox_volume=470000.0,
                                face_count=48, curved_face_count=31)
    good_ad = AutoDiffEvidence(gouge_ratio=0.0, excess_ratio=0.005, in_tol_ratio=0.995)
    r1 = verify_product_integrity(features=good_features, geometry=good_geo, autodiff=good_ad)
    cases.append(("完整复杂曲面成品", r1.passed, "PASS 三道门全绿"))

    # 用例2：成品退化成圆柱毛坯（填充率 π/4、3 面、1 曲面）
    cyl_geo = GeometryEvidence(volume=0.7854 * 1000000.0, bbox_volume=1000000.0,
                               face_count=3, curved_face_count=1)
    r2 = verify_product_integrity(features=good_features, geometry=cyl_geo, autodiff=good_ad)
    cases.append(("退化成圆柱毛坯", not r2.passed and r2.circuit_breaker,
                  f"拦截: {r2.failures[0][:60]}…"))

    # 用例3：空特征 ΔV=0
    bad_f = [FeatureDelta("空拉伸", "extrude", 0.0)]
    r3 = verify_product_integrity(features=bad_f, geometry=good_geo, autodiff=good_ad)
    cases.append(("特征 ΔV=0", not r3.passed, f"拦截: {r3.failures[0]}"))

    # 用例4：Auto-Diff 红色过切（Fatal）
    bad_ad = AutoDiffEvidence(gouge_ratio=0.01, excess_ratio=0.0, in_tol_ratio=0.99)
    r4 = verify_product_integrity(features=good_features, geometry=good_geo, autodiff=bad_ad)
    cases.append(("红色过切 Fatal", (not r4.passed) and r4.circuit_breaker,
                  f"拦截: {r4.failures[0][:50]}…"))

    # 用例5：缺仿真证据（证据宪法：不得断言通过）
    r5 = verify_product_integrity(features=good_features, geometry=good_geo, autodiff=None)
    cases.append(("缺 Auto-Diff 证据", not r5.passed, f"拦截: {r5.failures[0]}"))

    # 用例6：strict 模式抛熔断异常
    try:
        verify_product_integrity(features=good_features, geometry=cyl_geo,
                                 autodiff=good_ad, strict=True)
        cases.append(("strict 熔断异常", False, "未抛异常（BUG）"))
    except ProductIntegrityError:
        cases.append(("strict 熔断异常", True, "已抛 ProductIntegrityError"))

    print("=" * 74)
    print("product_integrity_gate 自测结果")
    print("=" * 74)
    all_ok = True
    for name, ok, desc in cases:
        all_ok = all_ok and ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {name:<20} -> {desc}")
    print("=" * 74)
    print("总结:", "ALL PASS" if all_ok else "HAS FAILURE")
    raise SystemExit(0 if all_ok else 1)
