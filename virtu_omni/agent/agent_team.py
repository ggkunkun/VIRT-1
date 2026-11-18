"""Virtu Industrial Omni-Agent Multi-Agent Team (Agent Team) Architecture.

Decomposes complex CAD/CAM/CAE manufacturing tasks across a collaborative team
of specialized AI Agents:
1. ChiefArchitectAgent: Master system architecture, intent decomposition & team coordinator.
2. ParametricModelingAgent: 3D CAD parametric FeatureTree planner & equation designer.
3. StandardsAndGDAgent: 2D drawing projection, fits & tolerances (H7/g6) & GD&T expert.
4. MachiningAndToolpathAgent: CAM toolpaths, cutting feeds & speeds, CNC Macro B & G-code specialist.
5. AuditorAndSandboxAgent: Headless simulation verification, collision detection & self-reflection optimizer.
6. EvolutionAndMemoryAgent: Dense-vector episodic memory retrieval, experience commitment & SKILL synthesis.

运行时分两类（2026-11-13 收敛，避免"两套并行"被误用）：

- **legacy 信封（本模块 ``IndustrialAgentTeam.solve``）**：保留 7 步「落盘 → 关软件 →
  回收内存」内存安全流水线 + Hindsight 记忆与安全审计。其**工程内容仍是模板/桩**
  （固定子模块、写死 GD&T、示例 VBA / Macro B），返回体显式标注
  ``runtime=agent_team.legacy_stub_pipeline``、``evidence_basis=asserted``、
  ``engineering_verified=False``，**不得**当作真实几何/加工已验证的证据。
- **真实工程运行时（``swarm_orchestrator.SwarmCommander``）**：几何解析 / 工艺规划 /
  刀路 / 仿真审计接真实模块，带 Blackboard 写锁、Meta-SOP 交接与红蓝辩论门。
  通过 ``IndustrialAgentTeam.solve_engineering()`` 调用；``solve_full()`` 则先用 legacy
  信封保证内存安全与记忆，再跑真实工程，**状态以真实门为准**（工程失败即 FAILED，
  不被桩 agent 的自报 COMPLETED 掩盖）。
"""

from __future__ import annotations
import os
import sys
import json
import math
import time
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("virtu_omni.agent.agent_team")

#: 真实工程运行时（唯一入口；legacy 流水线不再承担工程验证职责）
REAL_ENGINEERING_RUNTIME = "virtu_omni.agent.swarm_orchestrator.SwarmCommander"
#: legacy 7 步信封的运行时标签（写入返回体，供上层区分"桩自报"与"实测通过"）
LEGACY_RUNTIME_TAG = "agent_team.legacy_stub_pipeline"


# ---------------------------------------------------------------------------
# ISO 286-1 尺寸公差实算（StandardsAndGDAgent 用；拒绝写死 "H7 (+0.021/0)"）
# ---------------------------------------------------------------------------
_ISO_SIZE_STEPS = ((1, 3), (3, 6), (6, 10), (10, 18), (18, 30), (30, 50),
                   (50, 80), (80, 120), (120, 180), (180, 250), (250, 315),
                   (315, 400), (400, 500))
_IT_MULTIPLIERS = {5: 7, 6: 10, 7: 16, 8: 25, 9: 40, 10: 64, 11: 100}


def _iso_size_mean(nominal_mm: float) -> float:
    """按 ISO 286-1 尺寸分段取几何平均 D（超出 1~500mm 时钳制）。"""
    d = float(nominal_mm)
    for lo, hi in _ISO_SIZE_STEPS:
        if lo < d <= hi:
            return math.sqrt(lo * hi)
    return max(1.0, min(d, 500.0))


def iso286_tolerance_um(nominal_mm: float, grade: int) -> float:
    """标准公差（µm）：i = 0.45·D^(1/3) + 0.001·D，ITn = k·i。"""
    D = _iso_size_mean(nominal_mm)
    i = 0.45 * (D ** (1.0 / 3.0)) + 0.001 * D
    return round(i * _IT_MULTIPLIERS.get(int(grade), 16), 1)


def iso286_fit(nominal_mm: float, code: str) -> Dict[str, Any]:
    """计算孔/轴极限偏差（mm），支持大写孔 H 与小写轴 h/g。

    依据：ISO 286-1 标准公差因子 + 基本偏差（H: EI=0；h: es=0；g: es=-2.5·D^0.34）。
    """
    letter = code[0]
    grade = int(code[1:])
    it = iso286_tolerance_um(nominal_mm, grade) / 1000.0
    if letter == "H":          # 基孔制孔
        ei, es = 0.0, it
    elif letter == "h":        # 基轴制轴
        es, ei = 0.0, -it
    elif letter == "g":        # 轴 g：基本偏差为负
        D = _iso_size_mean(nominal_mm)
        es = round(-2.5 * (D ** 0.34) / 1000.0, 3)
        ei = round(es - it, 3)
    else:
        ei, es = 0.0, it
    return {
        "code": code,
        "nominal_mm": round(float(nominal_mm), 3),
        "upper_mm": round(es, 3),
        "lower_mm": round(ei, 3),
        "tolerance_mm": round(es - ei, 3),
        "it_micron": iso286_tolerance_um(nominal_mm, grade),
        "basis": "ISO 286-1 实算",
    }


def _format_fit_label(code: str, fit: Dict[str, Any]) -> str:
    """输出图纸标注习惯写法，如 H7 (+0.021 / 0 mm)。"""
    return f"{code} ({fit['upper_mm']:+.3f} / {fit['lower_mm']:+.3f} mm)"


def _form_tolerance_mm(nominal_mm: float, grade: int) -> float:
    """形位公差取值：按对应尺寸的 IT 等级换算（mm）。"""
    return round(iso286_tolerance_um(nominal_mm, grade) / 1000.0, 3)


# ---------------------------------------------------------------------------
# 几何族判定与模块拆解（ChiefArchitectAgent 用；不再固定三条子模块）
# ---------------------------------------------------------------------------
_ROTATIONAL_HINTS = ("套", "轴", "轮", "盘", "法兰", "环", "杆", "衬套", "辊", "销", "管")
_PLATE_HINTS = ("板", "盖", "座", "支架", "壳", "底座", "垫片", "型腔")
# 2026-11-14：涡轮叶片必须先于回转体判定——"涡轮叶片"含"轮"字，旧逻辑把它误判成"回转体-盘套类"(圆棒 Ø53×45 + G71 车削)
_TURBINE_BLADE_HINTS = ("涡轮叶片", "航空叶片", "工作叶片", "导向叶片", "叶片", "turbine blade", "airfoil", "榫头")
_MULTIAXIS_IMPELLER_HINTS = ("封闭式叶轮", "整体叶轮", "叶轮", "整体叶盘", "impeller", "blisk")
_BOX_STOCK_HINTS = ("包容块", "方料", "方块", "矩形毛坯", "box")
FAMILY_TURBINE_BLADE = "五轴叶片-复杂曲面类"
FAMILY_IMPELLER_BOX = "五轴叶轮-包容块类"


def classify_geometry(prompt: str, spec: Dict[str, Any]) -> Tuple[str, str]:
    """由规格与语义判定几何族，返回 (family, rationale)。"""
    d_outer = float(spec.get("d_outer") or 0.0)
    d_inner = float(spec.get("d_inner") or 0.0)
    length = float(spec.get("overall_len") or 0.0)
    low = str(prompt).lower()
    is_impeller = any(h in low for h in _MULTIAXIS_IMPELLER_HINTS)
    if spec.get("is_turbine_blade") or (any(h in low for h in _TURBINE_BLADE_HINTS) and not is_impeller):
        return (FAMILY_TURBINE_BLADE,
                "语义命中航空发动机涡轮叶片，基于样本(turbine_blade_design.stl/turbine_blade_stock.stl)"
                "反推包容块方料与五轴联动(G43.4 B/C)工艺")
    if is_impeller and (any(h in low for h in _BOX_STOCK_HINTS) or spec.get("stock_shape") == "box"):
        return (FAMILY_IMPELLER_BOX,
                "语义命中封闭式叶轮+包容块要求，基于样本反推矩形包容块毛坯(is_revolution=False)与五轴联动加工")
    if any(h in prompt for h in _PLATE_HINTS) and not any(h in prompt for h in _ROTATIONAL_HINTS):
        return "板类", "语义命中板/盖/座类关键词"
    if any(h in prompt for h in _ROTATIONAL_HINTS):
        if length and d_outer and length / d_outer >= 1.5:
            return "回转体-轴类", f"语义命中回转体且长径比 {length / d_outer:.2f} ≥ 1.5"
        return "回转体-盘套类", f"语义命中回转体且长径比 {(length / d_outer if d_outer else 0):.2f} < 1.5"
    if d_outer and d_inner and length:
        return "回转体-盘套类", "无关键词但有外径/内径/长度三要素，按回转体处理"
    return "异形件", "无回转/板类特征，按异形件处理"


def decompose_modules(family: str, spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    """按几何族把零件拆成可加工模块，尺寸来自 spec。"""
    d_outer = float(spec.get("d_outer") or 0.0)
    d_inner = float(spec.get("d_inner") or 0.0)
    length = float(spec.get("overall_len") or 0.0)
    if family in (FAMILY_TURBINE_BLADE, FAMILY_IMPELLER_BOX):
        sd = spec.get("stock_dims_mm") or {}
        db = spec.get("design_bbox_mm") or {}
        al = spec.get("allowances_mm") or {}
        side = min([v for k, v in al.items() if k.startswith(("x_", "y_"))] or [0.0])
        clamp = float(al.get("z_bottom_clamp") or 0.0)
        stock_txt = (f"矩形包容块 {sd.get('dx', 0):g}×{sd.get('dy', 0):g}×{sd.get('dz', 0):g}mm "
                     f"(成品 {db.get('dx', 0):g}×{db.get('dy', 0):g}×{db.get('dz', 0):g}mm，"
                     f"最小单边余量+{side:g}mm，底端装夹+{clamp:g}mm，样本反推)") if sd else \
            "矩形包容块（样本缺失：须先提供成品网格+样本毛坯再反推）"
        if family == FAMILY_TURBINE_BLADE:
            twist = spec.get("twist_angle_deg")
            return [
                {"module_name": "包容块方料毛坯（样本反推）", "type": "stock", "parts": [stock_txt]},
                {"module_name": "三齿枞树形榫头基准 (OP1)", "type": "milling",
                 "parts": ["榫头成形铣削，建立五轴专用夹具基准面"]},
                {"module_name": "缘板与进排气边过渡 (OP2)", "type": "milling",
                 "parts": ["3+2 轴定轴清根与缘板台阶精铣"]},
                {"module_name": "扭曲叶身五轴联动流道曲面 (OP3)", "type": "5axis_simultaneous",
                 "parts": [f"G43.4 RTCP X/Y/Z/B/C 五轴联动螺旋球头刀精加工"
                           + (f"（扭转角 {twist:g}°）" if twist else "")]},
            ]
        return [
            {"module_name": "包容块方料毛坯（样本反推）", "type": "stock", "parts": [stock_txt]},
            {"module_name": "外形与轮毂粗开 (OP1)", "type": "milling", "parts": ["包容块外形与轮毂回转面粗开"]},
            {"module_name": "封闭流道五轴插铣/摆线 (OP2)", "type": "5axis_simultaneous", "parts": ["G43.4 B/C 流道开粗"]},
            {"module_name": "叶片与盖板内壁五轴精加工 (OP3)", "type": "5axis_simultaneous", "parts": ["球头刀五轴联动精修"]},
        ]
    if family == "回转体-轴类":
        return [
            {"module_name": "毛坯与中心孔基准", "type": "stock", "parts": [f"棒料 Ø{d_outer:g}×{length:g}"]},
            {"module_name": "外圆阶梯轴段", "type": "turning", "parts": [f"外圆 Ø{d_outer:g}", f"总长 {length:g}"]},
            {"module_name": "键槽与退刀槽", "type": "feature", "parts": ["键槽", "退刀槽"]},
            {"module_name": "端部螺纹/倒角", "type": "feature", "parts": ["端部倒角 C1", "螺纹段"]},
        ]
    if family == "回转体-盘套类":
        return [
            {"module_name": "毛坯与端面装夹基准", "type": "stock", "parts": [f"圆棒 Ø{d_outer:g}×{length:g}"]},
            {"module_name": "外圆与端面回转主体", "type": "turning", "parts": [f"外圆 Ø{d_outer:g}", f"端面厚 {length:g}"]},
            {"module_name": "内孔与止口配合面", "type": "boring", "parts": [f"内孔 Ø{d_inner:g}", "止口定位面"]},
            {"module_name": "键槽/均布孔特征", "type": "feature", "parts": ["键槽或均布螺栓孔"]},
        ]
    if family == "板类":
        return [
            {"module_name": "基板轮廓铣削", "type": "milling", "parts": [f"外形 {d_outer:g}×{length:g}"]},
            {"module_name": "孔系与沉孔", "type": "drilling", "parts": [f"安装孔 Ø{d_inner:g}"]},
            {"module_name": "台阶/型腔", "type": "pocket", "parts": ["台阶面", "型腔"]},
            {"module_name": "倒角与去毛刺", "type": "finish", "parts": ["周边倒角 C1"]},
        ]
    return [
        {"module_name": "扫描/放样主体", "type": "surface", "parts": ["自由曲面主体"]},
        {"module_name": "曲面过渡与圆角", "type": "surface", "parts": ["过渡曲面"]},
        {"module_name": "定位孔系", "type": "drilling", "parts": [f"定位孔 Ø{d_inner:g}" if d_inner else "定位孔"]},
        {"module_name": "清角与精加工", "type": "finish", "parts": ["清角刀路"]},
    ]


# ---------------------------------------------------------------------------
# 切削参数实算（MachiningAndToolpathAgent 用）
# 参考值：硬质合金刀具车削中碳钢/铝合金/钛合金的常规线速度与每转进给。
# 主轴转速不写死，由 n = 1000·Vc / (π·D) 按实际直径反解。
# ---------------------------------------------------------------------------
_MATERIAL_CUTTING = {
    "AL7075-T6": {"vc_rough": 300.0, "vc_finish": 360.0, "feed": 0.20, "ap": 2.5, "label": "铝合金 7075-T6"},
    "AL6061-T6": {"vc_rough": 250.0, "vc_finish": 320.0, "feed": 0.22, "ap": 2.5, "label": "铝合金 6061-T6"},
    "Ti-6Al-4V": {"vc_rough": 55.0, "vc_finish": 70.0, "feed": 0.10, "ap": 1.0, "label": "钛合金 Ti-6Al-4V"},
    "Cr12MoV": {"vc_rough": 85.0, "vc_finish": 110.0, "feed": 0.12, "ap": 1.5, "label": "冷作模具钢 Cr12MoV"},
    "Steel45": {"vc_rough": 120.0, "vc_finish": 150.0, "feed": 0.15, "ap": 2.0, "label": "45 钢"},
    "SS304": {"vc_rough": 90.0, "vc_finish": 110.0, "feed": 0.12, "ap": 1.5, "label": "不锈钢 304"},
    "Inconel718": {"vc_rough": 30.0, "vc_finish": 45.0, "feed": 0.08, "ap": 0.8, "label": "镍基高温合金 Inconel 718"},
}
# 铣削每齿进给（mm/z，硬质合金立铣/球头刀常规值）
_MILL_FZ = {"Inconel718": 0.05, "Ti-6Al-4V": 0.06, "AL7075-T6": 0.10, "AL6061-T6": 0.10,
            "Cr12MoV": 0.06, "Steel45": 0.08, "SS304": 0.06}


def milling_params_for(material: str, tool_d: float, flutes: int = 4, finish: bool = False) -> Dict[str, Any]:
    """铣削参数实算：n=1000·Vc/(π·Dtool)，F=n·z·fz。"""
    cfg = _MATERIAL_CUTTING.get(material, _DEFAULT_CUTTING)
    vc = cfg["vc_finish"] if finish else cfg["vc_rough"]
    d = max(0.5, float(tool_d))
    n = int(round(1000.0 * vc / (math.pi * d)))
    n = max(_SPINDLE_LIMIT[0], min(n, _SPINDLE_LIMIT[1]))
    fz = _MILL_FZ.get(material, 0.06)
    return {"tool_d_mm": d, "vc_m_min": vc, "spindle_rpm": n, "fz_mm": fz, "flutes": flutes,
            "feed_mm_min": int(round(n * flutes * fz)), "material_label": cfg["label"],
            "basis": "n=1000·Vc/(π·Dtool)，F=n·z·fz 实算"}
_DEFAULT_CUTTING = {"vc_rough": 150.0, "vc_finish": 180.0, "feed": 0.15, "ap": 2.0, "label": "通用钢件"}
_SPINDLE_LIMIT = (50, 12000)


def cutting_params_for(material: str, d_outer: float, d_inner: float) -> Dict[str, Any]:
    """由材料与毛坯直径实算主轴转速、进给、分层次数。"""
    cfg = _MATERIAL_CUTTING.get(material, _DEFAULT_CUTTING)
    d = max(1.0, float(d_outer))

    def _rpm(vc: float) -> int:
        n = int(round(1000.0 * vc / (math.pi * d)))
        return max(_SPINDLE_LIMIT[0], min(n, _SPINDLE_LIMIT[1]))

    n_rough = _rpm(cfg["vc_rough"])
    n_finish = _rpm(cfg["vc_finish"])
    radial_stock = max(0.1, (float(d_outer) - float(d_inner)) / 2.0)
    passes = max(1, int(math.ceil(radial_stock / cfg["ap"])))
    return {
        "material": material,
        "material_label": cfg["label"],
        "diameter_mm": round(d, 3),
        "surface_speed_m_min": cfg["vc_rough"],
        "finish_surface_speed_m_min": cfg["vc_finish"],
        "spindle_rpm": n_rough,
        "finish_spindle_rpm": n_finish,
        "feed_rate": cfg["feed"],                 # mm/rev
        "feed_rate_mm_min": int(round(n_rough * cfg["feed"])),
        "depth_of_cut_mm": cfg["ap"],
        "radial_stock_mm": round(radial_stock, 3),
        "roughing_passes": passes,
        "basis": "n=1000·Vc/(π·D) 实算，Vc/进给取材料常规切削库",
    }

try:  # E 组：统一运行上下文（run_id 内容指纹 + span + step）
    from virtu_omni.agent.run_context import RunContext, content_fingerprint, ensure_ctx
except Exception as _rc_exc:  # pragma: no cover - 极端环境下退化，不阻断主流程
    logger.warning("run_context 不可用，退化为主键拼接: %s", _rc_exc)

    def content_fingerprint(*parts, length: int = 16):
        import hashlib as _h
        return _h.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:length]

    class RunContext:  # type: ignore
        def __init__(self, run_id, span="root", parent_span="", step=0, extra=None):
            self.run_id = run_id
            self.span = span
            self.parent_span = parent_span
            self.step = step
            self.extra = dict(extra or {})
            self.started_at = time.time()

        @classmethod
        def root(cls, *parts, run_id=None, **extra):
            return cls(run_id or content_fingerprint(*parts), extra=extra)

        def child(self, span, step=None):
            return RunContext(self.run_id, f"{self.span}/{span}", self.span,
                              self.step if step is None else step, self.extra)

        def log(self, stage, **kw):
            logger.info("run_id=%s span=%s stage=%s %s", self.run_id, self.span, stage, kw)

        def to_dict(self):
            return {"run_id": self.run_id, "span": self.span, "step": self.step}

    def ensure_ctx(ctx=None, *parts, **extra):
        return ctx if isinstance(ctx, RunContext) else RunContext.root(*parts, **extra)

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

from virtu_omni.agent.blueprint_inverse_engine import BlueprintInverseEngine
from virtu_omni.agent.self_reflection_optimizer import SelfReflectionOptimizer
from virtu_omni.agent.headless_sandbox_verifier import HeadlessSandboxVerifier
from virtu_omni.agent.skill_writer_and_memory import SkillWriterAndMemory
from virtu_omni.agent.process_memory_reclaimer import ProcessMemoryReclaimer
from virtu_omni.engine.wish_cad_cam_engine import WishCADCAMEngine
from virtu_omni.security.auditor import ModelSecurityAuditor
from virtu_omni.memory import VirtuHindsightMemory, MemoryType


class BaseIndustrialAgent:
    """Base class for specialized industrial autonomous agents."""

    def __init__(self, name: str, role: str, responsibilities: List[str]):
        self.name = name
        self.role = role
        self.responsibilities = responsibilities

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError


class ChiefArchitectAgent(BaseIndustrialAgent):
    """Lead Architect Agent: Analyzes requirements, parses design intent, and coordinates team."""

    def __init__(self):
        super().__init__(
            name="Virtu-Chief-Architect",
            role="工业系统总架构师与工程任务分解中心",
            responsibilities=[
                "用户制造愿景深度揣测与参数解析",
                "自动化设备系统级工程拆解 (Frame, Feeding, Tooling)",
                "分派多智能体任务与最终交付物统合"
            ]
        )
        self.engine = WishCADCAMEngine()

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        prompt = context.get("user_prompt", "")
        # Parse intent using WishCADCAMEngine
        spec = self.engine.parse_wish_intent(prompt)

        # 几何族与模块拆解由规格推导（不再固定三条子模块）
        family, rationale = classify_geometry(prompt, spec)
        sub_modules = decompose_modules(family, spec)
        equipment_type = f"{family}零件"

        return {
            "agent": self.name,
            "status": "COMPLETED",
            "parsed_spec": spec,
            "geometry_family": family,
            "classification_basis": rationale,
            "equipment_type": equipment_type,
            "sub_modules": sub_modules,
            "summary": (
                f"已完成需求解析：识别为【{spec.get('wish_name', '精密机械构件')}】，"
                f"材料【{spec.get('material', 'AL6061-T6')}】，"
                f"几何族【{family}】（{rationale}），按该族拆解 {len(sub_modules)} 个可加工模块。"
            ),
        }


class ParametricModelingAgent(BaseIndustrialAgent):
    """Parametric Modeling Specialist: Designs 3D sketches, FeatureTree, and parametric equations."""

    def __init__(self):
        super().__init__(
            name="Virtu-Parametric-Modeler",
            role="3D CAD 原生特征树规划与参数化建模专家",
            responsibilities=[
                "逆向图纸几何基元推导 (Revolving / Prismatic)",
                "SolidWorks FeatureManager 原生设计树规划",
                "全局方程式驱动绑定 (swEqnMgr) 与 0 呆料实体建模"
            ]
        )
        self.inverse_engine = BlueprintInverseEngine()

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        arch_data = context.get("architecture", {})
        spec = arch_data.get("parsed_spec", {})
        prompt = context.get("user_prompt", "")
        family = arch_data.get("geometry_family") or classify_geometry(prompt, spec)[0]

        d_outer = float(spec.get("d_outer") or 80.0)
        d_inner = float(spec.get("d_inner") or 20.0)
        length = float(spec.get("overall_len") or 30.0)
        num_features = int(spec.get("num_features") or 3)

        # 尺寸全由 spec 驱动：回转件按外径作包络，板类按长×宽×厚
        stock_derivation_ev: Dict[str, Any] = {}
        if family in (FAMILY_TURBINE_BLADE, FAMILY_IMPELLER_BOX) and spec.get("design_bbox_mm"):
            db = spec["design_bbox_mm"]
            bbox = {"length": float(db["dx"]), "width": float(db["dy"]), "thickness": float(db["dz"])}
            stock_derivation_ev = {
                "stock_shape": spec.get("stock_shape"),
                "stock_dims_mm": spec.get("stock_dims_mm"),
                "allowances_mm": spec.get("allowances_mm"),
                "sample_provenance": spec.get("sample_provenance"),
                "basis": "measured_from_sample (stock_derivation.inverse_derive_from_sample)",
            }
        elif family.startswith("回转体"):
            bbox = {"length": d_outer, "width": d_outer, "thickness": length}
        else:
            bbox = {"length": d_outer, "width": max(d_outer * 0.75, d_inner * 2), "thickness": length}

        blueprint_input = {
            "description": prompt,
            "material": spec.get("material", "AL6061-T6"),
            "dimensions": {
                **bbox,
                "hole_d": d_inner,
                # 均布孔节圆：按特征数与包络外径推导（0.7 倍外径为常用螺栓圆）
                "pitch": round(max(d_outer, d_inner * 2) * 0.7, 3),
                "feature_count": num_features,
            },
            "dimension_provenance": {
                "length_mm": (spec.get("dimension_evidence", {}).get("d_outer_mm", {}).get("source")
                              or "derived_from_parsed_spec"),
                "width_mm": ("derived_from_outer_diameter" if family.startswith("回转体")
                             else "derived_from_envelope_rule"),
                "thickness_mm": (spec.get("dimension_evidence", {}).get("overall_len_mm", {}).get("source")
                                 or "derived_from_parsed_spec"),
                "hole_diameter_mm": (spec.get("dimension_evidence", {}).get("d_inner_mm", {}).get("source")
                                     or "derived_from_parsed_spec"),
                "pitch_mm": "derived_from_0.7x_envelope_rule",
            },
        }

        inverse_res = self.inverse_engine.infer_blueprint_features(blueprint_input)
        sw_vba = self.inverse_engine.generate_solidworks_vba_script(inverse_res)

        return {
            "agent": self.name,
            "status": "COMPLETED",
            "geometry_family": family,
            "bbox_mm": bbox,
            "stock_derivation": stock_derivation_ev,
            "category": inverse_res["classified_primitive"],
            "equations": inverse_res["deduced_equations"],
            "feature_tree": inverse_res["feature_tree"],
            "assembly_mates": inverse_res["assembly_mates"],
            "solidworks_vba": sw_vba,
            "geometry_evidence": inverse_res.get("geometry_evidence", {
                "status": "insufficient", "verified": False,
                "basis": "feature_tree_rule_inference",
            }),
            "engineering_verified": False,
            "basis": "尺寸取自 parsed_spec（外径/内径/长度），特征树由 BlueprintInverseEngine 推导",
            "summary": (
                f"完成 3D 参数化特征树构建：几何族【{family}】，包络 "
                f"{bbox['length']:g}×{bbox['width']:g}×{bbox['thickness']:g}mm，"
                f"基元分类【{inverse_res['classified_primitive']}】，"
                f"绑定 {len(inverse_res['deduced_equations'])} 项全局方程式。"
            ),
        }


class StandardsAndGDAgent(BaseIndustrialAgent):
    """Engineering Standards & GD&T Specialist: Generates 2D views, fits, GD&T, and roughness."""

    def __init__(self):
        super().__init__(
            name="Virtu-Standards-GD&T-Engineer",
            role="工程图标准基准、配合公差与形位公差专家",
            responsibilities=[
                "正交三视图投影与剖视规划",
                "基孔制/基轴制标准配合公差计算 (H7/g6, H7/h6)",
                "形位公差 (GD&T) 与主要加工面表面粗糙度 (Ra) 规范定义"
            ]
        )

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        arch_data = context.get("architecture", {})
        spec = arch_data.get("parsed_spec", {})
        d_inner = float(spec.get("d_inner") or 20.0)
        d_outer = float(spec.get("d_outer") or 60.0)
        length = float(spec.get("overall_len") or 50.0)

        # ISO 286 实算：同一套规则对任何公称尺寸都成立，不再写死 "H7 (+0.021 / 0)"
        bore = iso286_fit(d_inner, "H7")        # 基孔制轴承/配合孔
        spigot = iso286_fit(d_outer, "g6")      # 止口/定位台阶轴
        shaft = iso286_fit(d_inner, "h6")       # 与孔配合的轴（间隙/过渡备用）

        # 形位公差按对应尺寸的 IT 等级换算（IT5 平行度 / IT6 同轴度）
        parallelism = _form_tolerance_mm(length, 5)
        concentricity = _form_tolerance_mm(d_inner, 6)

        # 粗糙度由公差等级反推：IT<=7 需磨/精镗，IT8 精铣，其余一般加工
        ra_bore = "Ra 0.8 (磨削/精密镗孔)" if bore["it_micron"] <= 25 else "Ra 1.6 (精镗)"
        ra_face = "Ra 1.6 (精铣)" if parallelism <= 0.02 else "Ra 3.2 (半精铣)"

        drawing_spec = {
            "sheet_size": "A3_Landscape" if max(d_outer, length) <= 420 else "A2_Landscape",
            "projection_views": ["主视图(1:1)", "俯视图(1:1)", "左视图(1:1)", "局部轴测剖视图"],
            "fit_tolerances": [
                {
                    "dimension_target": "核心配合轴承孔",
                    "nominal_size": round(d_inner, 3),
                    "tolerance_class": _format_fit_label("H7", bore),
                    "limits_mm": {"upper": bore["upper_mm"], "lower": bore["lower_mm"]},
                    "basis": bore["basis"],
                },
                {
                    "dimension_target": "端面安装止口定位台阶",
                    "nominal_size": round(d_outer, 3),
                    "tolerance_class": _format_fit_label("g6", spigot),
                    "limits_mm": {"upper": spigot["upper_mm"], "lower": spigot["lower_mm"]},
                    "basis": spigot["basis"],
                },
                {
                    "dimension_target": "配合轴径（间隙定位）",
                    "nominal_size": round(d_inner, 3),
                    "tolerance_class": _format_fit_label("h6", shaft),
                    "limits_mm": {"upper": shaft["upper_mm"], "lower": shaft["lower_mm"]},
                    "basis": shaft["basis"],
                },
            ],
            "geometric_tolerances_gdt": [
                {"symbol": "parallelism", "value_mm": parallelism,
                 "datum_ref": "A (底面安装基准)",
                 "derivation": f"IT5({length:.1f}mm) 实算"},
                {"symbol": "concentricity", "value_mm": concentricity,
                 "datum_ref": "B (内孔轴线)",
                 "derivation": f"IT6({d_inner:.1f}mm) 实算"},
            ],
            "surface_roughness": {
                "bearing_bore": ra_bore,
                "mounting_face": ra_face,
                "non_contact": "Ra 6.3 (去氧化皮)",
            },
            "technical_notes": [
                "1. 未注倒角均按 C1.0 执行，锐边倒钝去毛刺；",
                "2. 调质处理硬度达到 HRC 28~32；",
                "3. 表面本色阳极氧化，膜厚 12~15 μm。",
            ],
            "basis": "ISO 286-1 实算（公称尺寸驱动，非模板常量）",
        }

        return {
            "agent": self.name,
            "status": "COMPLETED",
            "drawing_spec": drawing_spec,
            "summary": (
                f"按 ISO 286 实算完成工程图标注：孔 Ø{d_inner:g} H7 "
                f"({bore['upper_mm']:+.3f}/{bore['lower_mm']:+.3f})、"
                f"止口 Ø{d_outer:g} g6 ({spigot['upper_mm']:+.3f}/{spigot['lower_mm']:+.3f})、"
                f"平行度 {parallelism}mm、同轴度 {concentricity}mm。"
            ),
        }


class MachiningAndToolpathAgent(BaseIndustrialAgent):
    """CAM & CNC Toolpath Specialist: Computes machining feeds/speeds, Macro B, and G-code."""

    def __init__(self):
        super().__init__(
            name="Virtu-CAM-CNC-Engineer",
            role="数控加工工艺、切削刀路与宏程序专家",
            responsibilities=[
                "切削参数动力学计算 (线速度 Vc, 进给率 Fz, 主轴转速 S)",
                "FANUC/SIEMENS Macro B 参数化数控程序合成",
                "对刀基准 (G54) 与刀尖方位号 (T01~T09) 配置"
            ]
        )

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        arch_data = context.get("architecture", {})
        spec = arch_data.get("parsed_spec", {})
        family = arch_data.get("geometry_family", "")
        if family in (FAMILY_TURBINE_BLADE, FAMILY_IMPELLER_BOX) or spec.get("is_turbine_blade") \
                or (spec.get("is_multiaxis") and spec.get("stock_shape") == "box"):
            return self._run_five_axis(spec, family)
        material = spec.get("material", "AL6061-T6")
        d_outer = float(spec.get("d_outer") or 80.0)
        d_inner = float(spec.get("d_inner") or 20.0)
        length = float(spec.get("overall_len") or 50.0)

        # 实算：转速由 Vc 与**实际直径**反解，分层数由径向余量/背吃刀量决定
        cp = cutting_params_for(material, d_outer, d_inner)
        n_rough = cp["spindle_rpm"]
        n_finish = cp["finish_spindle_rpm"]
        f_r = cp["feed_rate"]
        ap = cp["depth_of_cut_mm"]
        passes = cp["roughing_passes"]
        cut_depth = round(min(length, d_outer), 3)

        macro_b_code = f"""%
O0001 (VIRTU AGENT TEAM CNC PARAMETRIC MACRO)
(MATERIAL: {cp['material_label']} | Vc: {cp['surface_speed_m_min']} m/min | D: Ø{cp['diameter_mm']})
(SPINDLE: n=1000*Vc/(pi*D)={n_rough} rpm | FINISH: {n_finish} rpm | f={f_r} mm/rev | ap={ap} mm)
(ROUGHING PASSES: {passes} (radial stock {cp['radial_stock_mm']} mm))
G21 G40 G99
G28 U0.0 W0.0
T0101 (ROUGH TURNING TOOL R0.8)
G54
M03 S{n_rough}
M08 (COOLANT ON)

#100 = {d_outer:.3f} (RAW STOCK OD)
#101 = {d_inner:.3f} (TARGET BORE ID)
#102 = {cut_depth:.3f} (TURNED LENGTH)
#103 = {passes} (ROUGHING PASS COUNT)

(--- SAFE RAPID POSITIONING: only positive Z before cutting ---)
G00 X[#100 + 4.0] Z2.0

(--- G71 ROUGH TURNING CYCLE: ap={ap} mm, {passes} passes ---)
G71 U{ap} R0.5
G71 P10 Q20 U0.4 W0.1 F{f_r}
N10 G00 X[#101 + 5.0]
    G01 Z0.0 F{f_r}
    G01 X[#100] Z-2.0 F{f_r}
    G01 Z-[#102] F{f_r}
N20 G01 X[#100 + 2.0] F{f_r}

(--- G70 FINISH TURNING CYCLE: n={n_finish} rpm ---)
M03 S{n_finish}
G70 P10 Q20 F{f_r}

M09
G28 U0.0 W0.0
M05
M30
%
"""

        return {
            "agent": self.name,
            "status": "COMPLETED",
            "cutting_params": cp,
            "macro_b_code": macro_b_code,
            "summary": (
                f"由【{cp['material_label']}】与 Ø{cp['diameter_mm']:g} 实算切削参数："
                f"粗车 S{n_rough} rpm、精车 S{n_finish} rpm、进给 f={f_r} mm/rev、"
                f"背吃刀量 ap={ap} mm、分 {passes} 次粗车（径向余量 {cp['radial_stock_mm']} mm），"
                f"生成含 G71/G70 的安全 Macro B。"
            ),
        }

    def _run_five_axis(self, spec: Dict[str, Any], family: str) -> Dict[str, Any]:
        """五轴联动程序（叶片/包容块叶轮）：毛坯与余量全部来自样本反推，不再出 G71/G70 车削。

        诚实边界：OP3 是按样本成品包络 + 扭转角参数化的 Macro B 螺旋刀路（包络级），
        不是从真实叶型曲面计算的 CAM 刀轨；真实曲面刀轨须由 CAM（NX/VERICUT 样本 NC）提供。
        """
        material = spec.get("material", "Inconel718")
        db = spec.get("design_bbox_mm") or {"dx": float(spec.get("d_outer") or 36.0),
                                             "dy": float(spec.get("width_mm") or 32.0),
                                             "dz": float(spec.get("overall_len") or 121.0)}
        sd = spec.get("stock_dims_mm") or {}
        al = spec.get("allowances_mm") or {}
        top_allow = float(al.get("z_top") or 3.0)
        clamp = float(al.get("z_bottom_clamp") or 2.0)
        twist = float(spec.get("twist_angle_deg") or 0.0)
        is_blade = family == FAMILY_TURBINE_BLADE or bool(spec.get("is_turbine_blade"))
        # 刀具：OP1 D10R1 牛鼻刀；OP3 D6R3 球头刀
        rough = milling_params_for(material, 10.0, 4, finish=False)
        fin = milling_params_for(material, 6.0, 4, finish=True)
        r_ball = 3.0
        # 叶身区段长度：成品高度扣除榫头+缘板（样本 SPEC：榫头 30 + 缘板 6），仅叶片适用
        root_platform = 36.0 if is_blade else 0.0
        airfoil_len = round(max(5.0, float(db["dz"]) - root_platform), 3)
        semi_x = round(float(db["dx"]) / 2.0 + r_ball, 3)
        semi_y = round(float(db["dy"]) / 2.0 + r_ball, 3)
        step_z = 1.0
        stock_txt = (f"BOX {sd.get('dx', 0):g}X{sd.get('dy', 0):g}X{sd.get('dz', 0):g} MM"
                     if sd else "BOX (SAMPLE MISSING)")
        kin = spec.get("kinematics") or "5-Axis Simultaneous (X/Y/Z/B/C, G43.4 RTCP)"
        root_depth = round(top_allow + float(db["dz"]) - 30.0, 3) if is_blade else round(top_allow + 5.0, 3)
        code = f"""%
O5001 (VIRTU 5-AXIS {'TURBINE BLADE' if is_blade else 'BOX-STOCK IMPELLER'} - SAMPLE INVERSE DERIVED)
(STOCK {stock_txt} | PRODUCT {db['dx']:g}X{db['dy']:g}X{db['dz']:g} MM)
(ALLOWANCE TOP {top_allow:g} | ROOT CLAMP {clamp:g} | WCS G54 Z0 = STOCK TOP)
(KINEMATICS {kin.upper()})
(MATERIAL {rough['material_label']} | VC {rough['vc_m_min']:g}/{fin['vc_m_min']:g} M/MIN)
G21 G40 G49 G80 G90 G17
G28 G91 Z0.
G90
(--- OP1 ROOT / DATUM ROUGHING : T1 D10R1 ---)
T1 M06
G54
M03 S{rough['spindle_rpm']}
M08
G00 B0. C0.
G00 G43.4 H01 Z100.0
G00 X{semi_x + 8.0:.3f} Y0.
G00 Z5.0
G01 Z-{top_allow:.3f} F{rough['feed_mm_min']}
G01 X-{semi_x + 8.0:.3f} F{rough['feed_mm_min']}
G01 Z-{root_depth:.3f} F{int(rough['feed_mm_min'] * 0.5)}
G01 X{semi_x + 8.0:.3f} F{rough['feed_mm_min']}
G00 Z100.0
(--- OP2 PLATFORM 3+2 INDEXED : B-15 C90 ---)
G00 B-15. C90.
G00 X{semi_x + 8.0:.3f} Y0.
G00 Z5.0
G01 Z-{top_allow + 1.0:.3f} F{rough['feed_mm_min']}
G01 X-{semi_x + 8.0:.3f} F{rough['feed_mm_min']}
G00 Z100.0
G00 B0. C0.
M05
(--- OP3 5-AXIS SIMULTANEOUS SPIRAL AIRFOIL FINISH : T3 D6R3 ---)
T3 M06
M03 S{fin['spindle_rpm']}
G00 G43.4 H03 Z100.0
#100 = {airfoil_len:.3f} (AIRFOIL ZONE LENGTH)
#101 = {step_z:.3f} (AXIAL STEP PER REV)
#102 = {twist:.3f} (TOTAL TWIST DEG FROM SAMPLE)
#103 = -{top_allow:.3f} (CURRENT Z START)
#104 = 0 (C ANGLE)
#110 = {semi_x:.3f} (SEMI AXIS X = HALF CHORD + R)
#111 = {semi_y:.3f} (SEMI AXIS Y = HALF THICK + R)
G00 X[#110] Y0.
G00 Z5.0
G01 Z[#103] F{fin['feed_mm_min']}
WHILE [#103 GE -[#100 + {top_allow:.3f}]] DO1
#104 = 0
WHILE [#104 LT 360] DO2
#105 = #102 * [[#103 + {top_allow:.3f}] / [0 - #100]]
G01 X[#110 * COS[#104]] Y[#111 * SIN[#104]] Z[#103 - #101 * #104 / 360] B[#105] C[#104] F{fin['feed_mm_min']}
#104 = #104 + 5
END2
#103 = #103 - #101
END1
G49
G00 Z100.0
G00 B0. C0.
M09
G28 G91 Z0.
G90
M05
M30
%
"""
        return {
            "agent": self.name,
            "status": "COMPLETED",
            "cutting_params": {"op1_rough": rough, "op3_finish": fin, "material": material},
            "macro_b_code": code,
            "kinematics": kin,
            "stock_derivation": {
                "stock_shape": spec.get("stock_shape"),
                "stock_dims_mm": sd,
                "allowances_mm": al,
                "design_bbox_mm": db,
                "sample_provenance": spec.get("sample_provenance"),
            },
            "sample_vcproject": (spec.get("sample_provenance") or {}).get("sample_vcproject"),
            "honest_boundary": "OP3 为包络级参数化螺旋刀路（成品包络+样本扭转角），非真实叶型曲面 CAM 刀轨",
            "summary": (
                f"基于样本反推：毛坯 {stock_txt}（成品 {db['dx']:g}×{db['dy']:g}×{db['dz']:g}mm），"
                f"{kin}；OP1 S{rough['spindle_rpm']} F{rough['feed_mm_min']}，"
                f"OP3 球头 D6 S{fin['spindle_rpm']} F{fin['feed_mm_min']}，扭转 {twist:g}°。"
            ),
        }


class AuditorAndSandboxAgent(BaseIndustrialAgent):
    """Quality & Simulation Auditor: Verifies code in headless sandbox, enforces security audit, and drives self-reflection."""

    def __init__(self):
        super().__init__(
            name="Virtu-Sandbox-Auditor",
            role="无头沙箱仿真执行、合规性审计与自省自愈专家",
            responsibilities=[
                "Headless CAD/CAM 虚拟沙箱仿真执行",
                "运动学刀路碰撞检测与 COM 对象生命周期检查",
                "自动化自省反思与代码闭环自愈",
                "Defensive Security Audit: 提示词注入检测、工具参数汇校验与安全报告生成",
            ]
        )
        self.optimizer = SelfReflectionOptimizer()
        self.verifier = HeadlessSandboxVerifier()
        self.security_auditor = ModelSecurityAuditor()

    def security_audit(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Perform defensive security audit on prompt, parameters, and generated code."""
        prompt = context.get("user_prompt", "")
        prompt_check = self.security_auditor.audit_prompt_injection(prompt)

        arch_data = context.get("architecture", {})
        spec = arch_data.get("parsed_spec", {})
        tool_check = self.security_auditor.audit_tool_arguments("cad.parse_wish_intent", spec)

        return {
            "prompt_security": prompt_check,
            "tool_arguments_security": tool_check,
            "passed": prompt_check["passed"] and tool_check["passed"],
        }

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        modeling_data = context.get("modeling", {})
        machining_data = context.get("machining", {})

        sw_code = modeling_data.get("solidworks_vba", "")
        macro_code = machining_data.get("macro_b_code", "")

        # 1. Audit SolidWorks Code
        sw_audit = self.optimizer.audit_code(sw_code, "solidworks")
        sw_optimized, sw_reflection = self.optimizer.reflect_and_optimize(sw_code, sw_audit)

        # 2. Audit Macro B Code
        macro_audit = self.optimizer.audit_code(macro_code, "cimco_macro")
        macro_optimized, macro_reflection = self.optimizer.reflect_and_optimize(macro_code, macro_audit)

        # 3. Defensive Security Audit (Cloudflare security-audit-skill)
        sec_audit = self.security_audit(context)

        # 4. Headless Sandbox Verifier on post-optimization artifacts
        sandbox_verification = {}
        if hasattr(self.verifier, "verify_solidworks_vba") and hasattr(self.verifier, "verify_cimco_macro_b"):
            sw_sandbox = self.verifier.verify_solidworks_vba(sw_optimized)
            macro_sandbox = self.verifier.verify_cimco_macro_b(macro_optimized)
            sandbox_verification = {
                "solidworks_vba": sw_sandbox,
                "macro_b": macro_sandbox,
                "passed": bool(sw_sandbox.get("passed")) and bool(macro_sandbox.get("passed")),
            }

        # Gate must be falsifiable: never hard-code a passing verdict.
        audit_breakdown = {
            "solidworks_vba_audit": bool(sw_audit.get("passed")),
            "macro_b_audit": bool(macro_audit.get("passed")),
            "security_audit": bool(sec_audit.get("passed")),
        }
        if sandbox_verification and not sandbox_verification.get("passed", True):
            audit_breakdown["headless_sandbox_verify"] = False
        all_passed = all(audit_breakdown.values())
        failed_checks = [name for name, ok in audit_breakdown.items() if not ok]
        if all_passed:
            summary = "沙箱审计通过：VBA / Macro B / 安全审计三项均 PASS（基于本次实际审计结果）。"
        else:
            summary = (
                "沙箱审计未通过（FAIL）：" + ", ".join(failed_checks)
                + "。禁止据此宣称任务完成，修复后必须重跑验证。"
            )
        return {
            "agent": self.name,
            "status": "COMPLETED" if all_passed else "FAILED",
            "passed": all_passed,
            "audit_breakdown": audit_breakdown,
            "failed_checks": failed_checks,
            "sw_audit_score": sw_audit.get("score"),
            "macro_audit_score": macro_audit.get("score"),
            "security_audit": sec_audit,
            "sandbox_verification": sandbox_verification,
            "verified_sw_vba": sw_optimized,
            "verified_macro_code": macro_optimized,
            "reflection_log": f"{sw_reflection}\n\n{macro_reflection}",
            "summary": summary,
        }


class EvolutionAndMemoryAgent(BaseIndustrialAgent):
    """Memory & Evolution Agent: Retrieves past experience via Hindsight multi-tiered memory and synthesizes skills."""

    def __init__(self, hindsight_memory: Optional[VirtuHindsightMemory] = None):
        super().__init__(
            name="Virtu-Memory-Evolution-Curator",
            role="Hindsight 跨会话语义记忆图谱与自主技能演化专家",
            responsibilities=[
                "Hindsight 核心操作三部曲 (Retain / Recall / Reflect)",
                "多维度记忆银行 (virtu_cad_cam, virtu_cnc_machining, virtu_quality_audit)",
                "新任务成功经验固化落盘 (Commit Experience) 与自省反思",
                "将高频通用工艺自主沉淀为标准 Antigravity SKILL 包",
                "长期记忆防投毒与跨会话隔离校验",
            ]
        )
        self.memory_engine = SkillWriterAndMemory()
        self.security_auditor = ModelSecurityAuditor()
        self.hindsight = hindsight_memory if hindsight_memory is not None else VirtuHindsightMemory()

    def retrieve_context(self, prompt: str, *, update_stats: bool = False) -> List[Dict[str, Any]]:
        """Retrieve historical similar solved engineering patterns across all Hindsight banks."""
        # 1. Cross-bank Hindsight Recall (CAD, CNC, Quality/CAE, General)
        hindsight_hits = self.hindsight.recall_all_banks(
            query=prompt,
            bank_ids=["virtu_cad_cam", "virtu_cnc_machining", "virtu_quality_audit", "default"],
            max_results=5,
            update_stats=update_stats,
        )
        # 2. Legacy Vector Store
        legacy_hits = self.memory_engine.query_memory(prompt, top_k=2)

        combined = list(hindsight_hits)
        for h in legacy_hits:
            if not any(c.get("id") == h.get("id") for c in combined):
                combined.append(h)
        return combined

    def reflect_on_intent(self, prompt: str, *, update_stats: bool = False) -> Dict[str, Any]:
        """Synthesize past learnings and coordinate-isolated mental models for the current task."""
        p_low = (prompt or "").lower()
        if any(k in p_low for k in ("vericut", "g71", "g70", "fanuc", "cnc", "车削", "铣削", "刀路")):
            primary_bank = "virtu_cnc_machining"
        elif any(k in p_low for k in ("lam", "fos", "应力", "过切", "公差", "audit", "质检")):
            primary_bank = "virtu_quality_audit"
        else:
            primary_bank = "virtu_cad_cam"
        reflected = self.hindsight.reflect(
            bank_id=primary_bank,
            query=prompt,
            budget="mid",
            update_stats=update_stats,
        )
        reflected["coordinate_invariants"] = dict(self.hindsight.select_coordinate_invariants(prompt))
        return reflected

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        arch_data = context.get("architecture", {})
        spec = arch_data.get("parsed_spec", {})
        task_sig = f"AgentTeam_{spec.get('wish_name', 'Part')}_{spec.get('material', 'AL')}"
        solution_strategy = "协同 Agent Team：架构拆解 -> 参数化特征树 -> GD&T 标注 -> G71 宏程序 -> 沙箱闭环自愈"

        # Validate against memory poisoning before committing
        mem_audit = self.security_auditor.audit_memory_entry(task_sig, solution_strategy)
        if not mem_audit["passed"]:
            raise ValueError(f"Security audit blocked poisoned memory commit: {mem_audit['violations']}")

        key_rules = [
            "回转特征必须优先绑定 swEqnMgr 方程式管理器",
            "精密切削必须使用 G71 粗车留 0.4mm 余量再经 G70 精修",
            "沙箱仿真必须验证 ForceRebuild3 与 G00 快速移动无负向切削碰撞"
        ]

        # 1. Commit to Hindsight Memory (both agent experiences and mental models)
        h_exp = self.hindsight.retain(
            bank_id="virtu_cad_cam",
            content=f"成功完成【{spec.get('wish_name', '零件')}】参数化建模与数控规划。材质: {spec.get('material', 'AL')}, 策略: {solution_strategy}",
            context="procedures",
            tags=["agent_team", "cad_cam", spec.get("material", "AL")],
            memory_type=MemoryType.AGENT_EXPERIENCES,
            metadata={"task_signature": task_sig, "spec": spec}
        )

        h_mm = self.hindsight.retain(
            bank_id="virtu_cad_cam",
            content=f"针对【{spec.get('wish_name', '零件')}】设计经验法则: {' | '.join(key_rules)}",
            context="learnings",
            tags=["mental_model", "best_practices"],
            memory_type=MemoryType.MENTAL_MODELS,
            metadata={"task_signature": task_sig}
        )

        # 2. Commit to legacy dense vector memory
        rec = self.memory_engine.commit_experience(
            task_signature=task_sig,
            problem_summary=context.get("user_prompt", "")[:200],
            solution_strategy=solution_strategy,
            key_rules_learned=key_rules,
            code_snippet=context.get("auditor", {}).get("verified_sw_vba", "")[:1000]
        )

        prov_check = (
            self.memory_engine.verify_skills_provenance()
            if hasattr(self.memory_engine, "verify_skills_provenance")
            else {"passed": False, "verified_skills": 0}
        )

        return {
            "agent": self.name,
            "status": "COMPLETED",
            "memory_id": rec["id"],
            "hindsight_experience_id": h_exp["id"],
            "hindsight_mental_model_id": h_mm["id"],
            "memory_security": mem_audit,
            "skills_provenance": prov_check,
            "total_experiences": self.memory_engine.memory["total_experiences"],
            "hindsight_total_units": self.hindsight.get_status()["total_units"],
            "summary": f"已将本次多智能体协同经验与心智模型固化至 Hindsight 记忆库 (EXP: {h_exp['id']}, MM: {h_mm['id']})，通过防投毒安全审查。"
        }


class IndustrialAgentTeam:
    """Master Orchestrator for the Collaborative Industrial Multi-Agent Team.
    
    遵循铁律：
    每完一步任务就保存到本地文件，关闭上一步的软件用来节省内存，完成以后执行下一步任务。
    """

    def __init__(self, log_path: Optional[str] = None):
        self.memory_agent = EvolutionAndMemoryAgent()
        self.architect_agent = ChiefArchitectAgent()
        self.modeler_agent = ParametricModelingAgent()
        self.standards_agent = StandardsAndGDAgent()
        self.machining_agent = MachiningAndToolpathAgent()
        self.auditor_agent = AuditorAndSandboxAgent()
        self.reclaimer = ProcessMemoryReclaimer(log_path=log_path)

    def to_super_agent(self):
        """Bridge and convert this multi-agent team into a unified Virtu Super Agent."""
        from virtu_omni.agent.super_agent import VirtuSuperAgent
        return VirtuSuperAgent()

    def to_swarm(self):
        """返回真实工程运行时（SwarmCommander）。

        本模块的 7 步流水线是 legacy 信封（内存安全 + 记忆归档），**不承担工程验证**。
        需要真实几何/工艺/刀路/审计结论时，走 ``solve_engineering()`` 或本方法。
        """
        from virtu_omni.agent.swarm_orchestrator import SwarmCommander
        return SwarmCommander()

    # ------------------------------------------------------------------
    # 真实工程运行时（收敛入口）
    # ------------------------------------------------------------------
    def solve_engineering(
        self,
        user_prompt: str,
        params: Optional[Dict[str, Any]] = None,
        output_dir: Optional[str] = None,
        run_ctx: Any = None,
    ) -> Dict[str, Any]:
        """跑**真实**工程链（SwarmCommander），不做 legacy 桩。

        与 ``solve()`` 的区别：几何来自成品 STL 实测、毛坯由成品派生、刀路写出
        VERICUT 工程、审计过成品完整性门、红蓝辩论门决定 success。
        """
        ctx = ensure_ctx(run_ctx, "agent_team.solve_engineering", user_prompt)
        t0 = time.time()
        task: Dict[str, Any] = dict(params or {})
        task.setdefault("part_type", user_prompt)
        try:
            from pathlib import Path
            from virtu_omni.agent.swarm_orchestrator import resolve_sample_assets_for_task
            resolved = resolve_sample_assets_for_task(task, Path(WORKSPACE_DIR))
            if not task.get("design_stl") and resolved.get("design_stl"):
                task["design_stl"] = resolved["design_stl"]
            for asset_k in ("sample_stock_stl", "sample_vcproject", "sample_design_stl"):
                if not task.get(asset_k) and resolved.get(asset_k):
                    task[asset_k] = resolved[asset_k]
            if not task.get("stock_shape") and resolved.get("expected_stock_shape"):
                task["stock_shape"] = resolved["expected_stock_shape"]
        except Exception:
            pass
        if not task.get("design_stl"):
            default_stl = os.path.join(WORKSPACE_DIR, "artifacts", "aero_closed_impeller",
                                       "AE_CLOSED_IMPELLER_NASA1975.stl")
            if os.path.exists(default_stl):
                task["design_stl"] = default_stl

        if not output_dir:
            ts = time.strftime("%Y%m%d_%H%M%S")
            output_dir = os.path.join(WORKSPACE_DIR, "runs", "agent_team_engineering",
                                      f"{ts}_{ctx.run_id}")
        os.makedirs(output_dir, exist_ok=True)

        swarm_res = self.to_swarm().solve(task, output_dir=output_dir)
        vr = swarm_res.get("verification_report") or {}
        errs = swarm_res.get("results") or {}
        worker_status = {}
        for key, res in errs.items():
            ok = isinstance(res, dict) and bool(res.get("passed", True)) and not res.get("error")
            worker_status[f"swarm.{key}"] = "COMPLETED" if ok else "FAILED"
        success = bool(swarm_res.get("success"))
        ctx.log("engineering_solve_done", success=success,
                blackboard_keys=len(swarm_res.get("blackboard_keys") or []))

        return {
            "runtime": "swarm",
            "engineering_runtime": REAL_ENGINEERING_RUNTIME,
            "engineering_verified": success,
            "evidence_basis": vr.get("evidence_basis", "asserted"),
            "status": "SUCCESS" if success else "FAILED",
            "success": success,
            "per_agent_status": worker_status,
            "verification_report": vr,
            "red_team_gate": vr.get("red_team_gate"),
            "red_team_findings": vr.get("red_team_findings"),
            "meta_sop_files": swarm_res.get("meta_sop_files") or [],
            "blackboard_keys": swarm_res.get("blackboard_keys") or [],
            "audit_log_len": swarm_res.get("audit_log_len"),
            "trace": swarm_res.get("trace") or [],
            "output_dir": output_dir,
            "runtime_seconds": round(time.time() - t0, 3),
            "run_context": ctx.to_dict() if hasattr(ctx, "to_dict") else {"run_id": ctx.run_id},
        }

    def solve_full(
        self,
        user_prompt: str,
        params: Optional[Dict[str, Any]] = None,
        output_dir: Optional[str] = None,
        memory_safe: bool = True,
        run_ctx: Any = None,
    ) -> Dict[str, Any]:
        """legacy 信封 + 真实工程：一次调用同时拿到"内存安全/记忆"与"真实验证"。

        **状态以真实门为准**：即使 legacy 桩 agent 全部自报 COMPLETED，只要真实工程
        链失败（红队判红 / 审计门未过），``status`` 就是 FAILED。``legacy_status``
        单独保留，便于对照"桩自报"与"实测"的差异。
        """
        base_dir = output_dir or os.path.join(
            WORKSPACE_DIR, "runs", "agent_team_full", time.strftime("%Y%m%d_%H%M%S"))
        legacy_dir = os.path.join(base_dir, "legacy_envelope")
        engineering_dir = os.path.join(base_dir, "engineering")
        os.makedirs(legacy_dir, exist_ok=True)
        os.makedirs(engineering_dir, exist_ok=True)

        legacy = self.solve(user_prompt, output_dir=legacy_dir,
                            memory_safe=memory_safe, run_ctx=run_ctx)
        eng = self.solve_engineering(user_prompt, params=params,
                                     output_dir=engineering_dir, run_ctx=run_ctx)

        merged = dict(legacy)  # 保留 legacy 字段（架构/特征树/GD&T/记忆等）以兼容下游
        merged.update({
            "runtime": "agent_team.legacy_envelope+swarm",
            "engineering_runtime": REAL_ENGINEERING_RUNTIME,
            "engineering_verified": eng["engineering_verified"],
            "evidence_basis": eng["evidence_basis"],
            # 关键：工程结论以真实门为准，legacy 自报状态只作对照
            "status": eng["status"],
            "legacy_status": legacy.get("status"),
            "legacy_runtime": LEGACY_RUNTIME_TAG,
            "legacy_is_stub": True,
            "swarm_status": eng["status"],
            "swarm_verification": eng["verification_report"],
            "per_agent_status": {**legacy.get("per_agent_status", {}),
                                 **eng["per_agent_status"]},
            "engineering": eng,
            "output_dir": base_dir,
            "legacy_output_dir": legacy.get("output_dir"),
            "engineering_output_dir": eng.get("output_dir"),
        })
        return merged

    # 七步流水线中登记进 per_agent_status 的角色顺序（用于团队级状态聚合）
    ROLE_ORDER = (
        "EvolutionAndMemoryAgent.retrieve_context",
        "ChiefArchitectAgent",
        "ParametricModelingAgent",
        "StandardsAndGDAgent",
        "MachiningAndToolpathAgent",
        "AuditorAndSandboxAgent",
        "EvolutionAndMemoryAgent.commit",
    )

    def probe_residual_processes(self) -> Dict[str, Any]:
        """实测六大 CAD/CAM 软件的残留进程数（报告用，替代原先未实测的模板断言）。

        ``residual_total`` 是全机目标进程数（含用户自己开的实例）；
        ``orphan_total`` 只统计**本会话产生且仍未关闭**的进程——后者才是流水线要保证为零的。
        """
        softwares = ("solidworks", "autocad", "nx", "cimco", "vericut", "sscnc")
        detail: Dict[str, Any] = {}
        orphans: Dict[str, int] = {}
        measured = True
        total = 0
        probe = getattr(self.reclaimer, "find_target_processes", None)
        if not callable(probe):
            return {"basis": "unmeasured", "detail": {}, "residual_total": "unmeasured",
                    "orphan_total": "unmeasured", "orphans": {}}
        for key in softwares:
            try:
                procs = probe(key)
                n = len(procs) if procs is not None else 0
                detail[key] = n
                total += n
                orphan_probe = getattr(self.reclaimer, "orphan_processes", None)
                orphans[key] = len(orphan_probe(key)) if callable(orphan_probe) else 0
            except Exception as e:  # pragma: no cover - 探测失败如实标注
                detail[key] = f"unmeasured: {e}"
                orphans[key] = "unmeasured: {e}"
                measured = False
        return {
            "basis": "measured" if measured else "partially_unmeasured",
            "detail": detail,
            "residual_total": total if measured else "unmeasured",
            "orphans": orphans,
            "orphan_total": sum(v for v in orphans.values() if isinstance(v, int)) if measured else "unmeasured",
        }

    @staticmethod
    def aggregate_team_status(per_agent_status: Dict[str, str]) -> str:
        """由 7 步子智能体真实 status 聚合出团队级状态（禁止字面量 SUCCESS）。

        规则：任一 FAILED → FAILED；全部 COMPLETED → SUCCESS；其余 → PARTIAL。
        """
        values = [str(v).upper() for v in per_agent_status.values()]
        if any(v == "FAILED" for v in values):
            return "FAILED"
        if values and all(v == "COMPLETED" for v in values):
            return "SUCCESS"
        return "PARTIAL"

    def _persist_and_reclaim_ctx(
        self,
        ctx: "RunContext",
        step_idx: int,
        step_title: str,
        artifacts_to_save: Dict[str, Any],
        output_dir: str,
        software_key: Optional[str] = None,
        memory_safe: bool = True,
    ) -> Dict[str, Any]:
        """_persist_and_reclaim 的带上下文包装：产出结构化 step 日志（run_id/stage/step/时长/pid）。"""
        step_ctx = ctx.child(f"step{step_idx}", step=step_idx)
        t = time.time()
        rec = self._persist_and_reclaim(step_idx, step_title, artifacts_to_save, output_dir,
                                        software_key, memory_safe)
        step_ctx.log(
            "team_step_done",
            duration_ms=(time.time() - t) * 1000.0,
            stage_name=step_title,
            persisted=len(rec.get("saved_files") or []),
            all_persisted=rec.get("all_persisted"),
            software_closed=rec.get("software_closed"),
        )
        rec["run_id"] = ctx.run_id
        rec["duration_ms"] = round((time.time() - t) * 1000.0, 1)
        return rec

    def _persist_and_reclaim(
        self,
        step_idx: int,
        step_title: str,
        artifacts_to_save: Dict[str, Any],
        output_dir: str,
        software_key: Optional[str] = None,
        memory_safe: bool = True
    ) -> Dict[str, Any]:
        """立即将步骤产物落盘至本地文件，确证大小>0，关闭对应软件并净化内存。"""
        saved_files = []
        for fname, content in artifacts_to_save.items():
            fpath = os.path.join(output_dir, fname)
            if isinstance(content, (dict, list)):
                with open(fpath, "w", encoding="utf-8") as f:
                    json.dump(content, f, ensure_ascii=False, indent=2)
            else:
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write(str(content))
            sz = os.path.getsize(fpath)
            saved_files.append({"filename": fname, "path": fpath, "bytes": sz, "valid": sz > 0})

        reclaim_record = None
        ram_before = self.reclaimer.get_system_memory()
        if memory_safe:
            if software_key:
                reclaim_record = self.reclaimer.close_software(software_key)
            self.reclaimer.trim_system_working_set()
        ram_after = self.reclaimer.get_system_memory()

        return {
            "step_idx": step_idx,
            "step_title": step_title,
            "saved_files": saved_files,
            "all_persisted": all(f["valid"] for f in saved_files),
            "software_closed": software_key if memory_safe and software_key else None,
            "ram_before_mb": ram_before["available_mb"],
            "ram_after_mb": ram_after["available_mb"],
            "reclaimed_mb": round(ram_after["available_mb"] - ram_before["available_mb"], 2),
            "reclaim_record": reclaim_record
        }

    def solve(
        self,
        user_prompt: str,
        output_dir: Optional[str] = None,
        memory_safe: bool = True,
        run_ctx: Any = None,
    ) -> Dict[str, Any]:
        """Execute collaborative end-to-end multi-agent problem solving with stage-gated memory safety.

        run_ctx: 上游（super_agent / deep_agent）透传的 RunContext；缺省按内容指纹自建，
        保证同一 prompt 的 run_id 可复现（审计 §7.2 / §8.2）。
        """
        t0 = time.time()
        ctx = ensure_ctx(run_ctx, "agent_team.solve", user_prompt)
        ctx.log("team_solve_start", memory_safe=memory_safe)
        # 记录"开工前"已在运行的 CAD/CAM 进程作为不可接管基线：
        # 用户自己开着的 SolidWorks 等实例绝不被关闭；运行期间新出现的才算本会话所有。
        baseline = self.reclaimer.snapshot_baseline()
        ctx.log("cad_cam_baseline_snapshot",
                baseline={k: v for k, v in baseline.items() if v})
        if not getattr(self, "_legacy_notice_emitted", False):
            logger.info(
                "IndustrialAgentTeam.solve() 运行的是 legacy 信封（内存安全+记忆归档），"
                "工程内容为模板/桩，evidence_basis=asserted；真实几何/加工验证请用 "
                "solve_engineering() 或 solve_full()（运行时 %s）。",
                REAL_ENGINEERING_RUNTIME,
            )
            self._legacy_notice_emitted = True
        if not output_dir:
            ts = time.strftime("%Y%m%d_%H%M%S")
            # 产物目录加 run_id 后缀：同秒并发不再冲突，且可按内容指纹回查（审计 §8.2）
            output_dir = os.path.join(WORKSPACE_DIR, "runs", "agent_team",
                                      f"{ts}_{ctx.run_id}")
        os.makedirs(output_dir, exist_ok=True)

        collaboration_log: List[Dict[str, Any]] = []
        persisted_manifest = []

        # Step 1: Memory Agent retrieves historical patterns via Hindsight Recall & Reflect
        past_experiences = self.memory_agent.retrieve_context(user_prompt)
        reflection = self.memory_agent.reflect_on_intent(user_prompt)
        step1_files = {
            "01_hindsight_retrieval.json": {
                "past_experiences": past_experiences,
                "reflection": reflection
            }
        }
        rec1 = self._persist_and_reclaim_ctx(ctx, 1, "Hindsight 语义检索与自省", step1_files, output_dir, None, memory_safe)
        persisted_manifest.extend(rec1["saved_files"])
        collaboration_log.append({
            "stage": "1. Hindsight 跨会话语义检索与自省合成 (Recall & Reflect)",
            "agent": self.memory_agent.name,
            "action": f"Hindsight 匹配 {len(past_experiences)} 条相关记忆，合成 {len(reflection['directives'])} 条高阶工艺准则。",
            "memory_reclamation": rec1
        })

        # Step 2: Chief Architect plans and decomposes
        arch_res = self.architect_agent.run({
            "user_prompt": user_prompt,
            "past_experiences": past_experiences,
            "reflection": reflection
        })
        step2_files = {
            "02_architecture_spec.json": arch_res
        }
        rec2 = self._persist_and_reclaim_ctx(ctx, 2, "需求拆解与架构规划", step2_files, output_dir, None, memory_safe)
        persisted_manifest.extend(rec2["saved_files"])
        collaboration_log.append({
            "stage": "2. 需求拆解与架构规划",
            "agent": self.architect_agent.name,
            "action": arch_res["summary"],
            "memory_reclamation": rec2
        })

        # Step 3: Parametric Modeler generates 3D FeatureTree & VBA
        model_res = self.modeler_agent.run({"user_prompt": user_prompt, "architecture": arch_res})
        step3_files = {
            "03_parametric_feature_tree.json": model_res["feature_tree"],
            "03_parametric_equations.json": model_res["equations"],
            "03_solidworks_native.swb": model_res["solidworks_vba"]
        }
        rec3 = self._persist_and_reclaim_ctx(ctx, 3, "3D 原生特征树与方程式建模", step3_files, output_dir, "solidworks", memory_safe)
        persisted_manifest.extend(rec3["saved_files"])
        collaboration_log.append({
            "stage": "3. 3D 原生特征树与方程式建模",
            "agent": self.modeler_agent.name,
            "action": model_res["summary"],
            "memory_reclamation": rec3
        })

        # Step 4: Standards Agent produces GD&T and 2D annotations
        std_res = self.standards_agent.run({"architecture": arch_res, "modeling": model_res})
        step4_files = {
            "04_drawing_standards_gdt.json": std_res["drawing_spec"]
        }
        rec4 = self._persist_and_reclaim_ctx(ctx, 4, "工程制图标准与 GD&T 标注", step4_files, output_dir, "autocad", memory_safe)
        persisted_manifest.extend(rec4["saved_files"])
        collaboration_log.append({
            "stage": "4. 工程制图标准与 GD&T 标注",
            "agent": self.standards_agent.name,
            "action": std_res["summary"],
            "memory_reclamation": rec4
        })

        # Step 5: Machining Agent produces CAM & CNC Macro B
        mach_res = self.machining_agent.run({"architecture": arch_res, "modeling": model_res})
        step5_files = {
            "05_machining_macro_b.nc": mach_res["macro_b_code"],
            "05_cutting_params.json": mach_res["cutting_params"]
        }
        rec5 = self._persist_and_reclaim_ctx(ctx, 5, "数控加工工艺与 Macro B 刀路", step5_files, output_dir, "cimco", memory_safe)
        persisted_manifest.extend(rec5["saved_files"])
        collaboration_log.append({
            "stage": "5. 数控加工工艺与 Macro B 刀路",
            "agent": self.machining_agent.name,
            "action": mach_res["summary"],
            "memory_reclamation": rec5
        })

        # Step 6: Auditor Agent runs Headless Sandbox Simulation & Self-Healing Loop
        audit_res = self.auditor_agent.run({"modeling": model_res, "machining": mach_res})
        step6_files = {
            "06_sandbox_simulation_audit.json": audit_res
        }
        rec6 = self._persist_and_reclaim_ctx(ctx, 6, "虚拟沙箱仿真与自省自愈", step6_files, output_dir, "vericut", memory_safe)
        persisted_manifest.extend(rec6["saved_files"])
        collaboration_log.append({
            "stage": "6. 虚拟沙箱仿真与自省自愈",
            "agent": self.auditor_agent.name,
            "action": audit_res["summary"],
            "memory_reclamation": rec6
        })

        # Step 7: Memory Agent commits verified patterns
        mem_res = self.memory_agent.run({
            "user_prompt": user_prompt,
            "architecture": arch_res,
            "auditor": audit_res
        })
        step7_files = {
            "07_hindsight_memory_commit.json": mem_res
        }
        rec7 = self._persist_and_reclaim_ctx(ctx, 7, "长期经验向量化归档", step7_files, output_dir, "sscnc", memory_safe)
        persisted_manifest.extend(rec7["saved_files"])
        collaboration_log.append({
            "stage": "7. 长期经验向量化归档",
            "agent": self.memory_agent.name,
            "action": mem_res["summary"],
            "memory_reclamation": rec7
        })

        # 终极净化：确保没有任何后台残余，清空 Ollama 显存
        if memory_safe:
            self.reclaimer.reclaim_all_cad_cam()
            self.reclaimer.unload_ollama_model()

        runtime = round(time.time() - t0, 3)

        # 团队级状态：由 7 步子智能体真实 status 聚合，禁止字面量 SUCCESS
        # 缺省值取 "UNKNOWN"（fail-closed）：子 agent 未显式上报 status 时不得默认视为完成
        per_agent_status: Dict[str, str] = {
            "EvolutionAndMemoryAgent.retrieve_context": "COMPLETED",
            "ChiefArchitectAgent": str(arch_res.get("status", "UNKNOWN")).upper(),
            "ParametricModelingAgent": str(model_res.get("status", "UNKNOWN")).upper(),
            "StandardsAndGDAgent": str(std_res.get("status", "UNKNOWN")).upper(),
            "MachiningAndToolpathAgent": str(mach_res.get("status", "UNKNOWN")).upper(),
            "AuditorAndSandboxAgent": str(
                audit_res.get("status",
                              "COMPLETED" if audit_res.get("passed") is True else "FAILED")
            ).upper(),
            "EvolutionAndMemoryAgent.commit": str(mem_res.get("status", "UNKNOWN")).upper(),
        }
        team_status = self.aggregate_team_status(per_agent_status)
        ctx.log("team_status_aggregated", team_status=team_status,
                per_agent=json.dumps(per_agent_status, ensure_ascii=False),
                duration_ms=(time.time() - t0) * 1000.0)

        # 写入全流程清单与人类可读报告
        manifest = {
            "project": "Virtu Industrial Agent Team",
            "user_prompt": user_prompt,
            "output_dir": output_dir,
            "team_status": team_status,
            "per_agent_status": per_agent_status,
            "run_context": ctx.to_dict() if hasattr(ctx, "to_dict") else {"run_id": ctx.run_id},
            "runtime_seconds": runtime,
            "persisted_artifacts": persisted_manifest,
            "collaboration_log": collaboration_log
        }
        with open(os.path.join(output_dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        # 生成 Markdown 交付报告
        report_lines = [
            "# Virtu Industrial Agent Team · 阶段式内存安全执行报告\n",
            f"- **用户愿望**: {user_prompt}",
            f"- **执行耗时**: {runtime} 秒",
            f"- **产物输出目录**: `{output_dir}`",
            f"- **落盘工件总数**: {len(persisted_manifest)} 个（全体验证非空）\n",
            "## 阶段递进与内存回收流水线",
            "| 步骤 | 智能体角色 | 产物文件 | 关停软件 | 回收前可用(MB) | 回收后可用(MB) | 内存净回收(MB) |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
        ]
        for log in collaboration_log:
            rec = log.get("memory_reclamation", {})
            f_names = ", ".join(f"`{f['filename']}`" for f in rec.get("saved_files", []))
            sw = rec.get("software_closed") or "—"
            report_lines.append(
                f"| {rec.get('step_idx')} | {log['agent']} | {f_names} | {sw} | "
                f"{rec.get('ram_before_mb')} | {rec.get('ram_after_mb')} | +{rec.get('reclaimed_mb')} |"
            )
        report_lines.append("\n## 子智能体状态聚合（实测 status，非模板常量）")
        report_lines.append("| 子智能体 | 真实 status |")
        report_lines.append("| :--- | :--- |")
        for role, st in per_agent_status.items():
            report_lines.append(f"| {role} | {st} |")
        report_lines.append(
            f"\n> **团队级状态**：{team_status}"
            "（聚合规则：任一 FAILED → FAILED；全部 COMPLETED → SUCCESS；其余 → PARTIAL）\n"
        )
        report_lines.append(
            "> **落盘与内存准则**：每完成一步即落盘并校验字节非空（结果见上表产物列与 persisted_manifest），"
            "关停软件与内存回收为实测值（见上表回收前后可用内存）。\n"
        )
        residual = self.probe_residual_processes()
        if residual["basis"] == "measured":
            report_lines.append(
                f"> **残留进程实测**：六大 CAD/CAM 软件进程总数 {residual['residual_total']}"
                f"（含开工前已存在的用户实例），其中**本会话产生且未关闭的孤儿进程 "
                f"{residual['orphan_total']}**，明细 {residual['detail']}。\n"
            )
        else:
            report_lines.append(
                f"> **残留进程实测**：未测（basis={residual['basis']}，明细 {residual['detail']}）。\n"
            )
        report_path = os.path.join(output_dir, "AGENT_TEAM_EXECUTION_REPORT.md")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(report_lines))

        return {
            # —— 诚实标注：本方法只跑 legacy 信封，工程内容为模板/桩，非实测验证 ——
            "runtime": LEGACY_RUNTIME_TAG,
            "engineering_runtime": REAL_ENGINEERING_RUNTIME,
            "engineering_verified": False,
            "evidence_basis": "asserted",
            "status": team_status,
            "per_agent_status": per_agent_status,
            "run_context": ctx.to_dict() if hasattr(ctx, "to_dict") else {"run_id": ctx.run_id},
            "audit_passed": audit_res.get("passed"),
            "residual_processes": residual,
            "runtime_seconds": runtime,
            "output_dir": output_dir,
            "report_path": report_path,
            "user_prompt": user_prompt,
            "persisted_manifest": persisted_manifest,
            "team_collaboration_log": collaboration_log,
            "architecture": arch_res,
            "parametric_model": model_res,
            "standards_gdt": std_res,
            "machining_cnc": mach_res,
            "sandbox_audit": audit_res,
            "memory_evolution": mem_res
        }
