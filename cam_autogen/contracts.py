"""标准化数据接口（Standardized Data Contracts）。

本文件是四个模块之间**唯一**允许共享的东西：纯数据结构（pydantic v2），不含任何业务逻辑。
每个模块只依赖本文件 + 标准库/第三方库，模块之间互不 import（由
``tests/cam_autogen/test_cam_architecture.py`` 以 AST 扫描强制，坏样本必判红）。

数据流::

    WorkpieceSpec ──► [M1 工艺识别] ──► RecognitionResult
    WorkpieceSpec + RecognitionResult + MachineLimits ──► [M2 方案求解] ──► ProcessPlan
    ProcessPlan + StockSetup + PostProfile ──► [M3 程序生成] ──► NCProgram
    NCProgram (+ProgramRequirements) ──► [M4 机床配置] ──► MachineSetup (+PostProfile)
    NCProgram + MachineSetup + ProcessPlan + StockSetup ──► [校验] ──► VerificationReport

约定：长度 mm，角度 deg，速度 m/min，转速 rpm，进给 mm/min（或 mm/rev 时字段名显式带 _rev）。
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

CONTRACT_VERSION = "1.0.0"


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())


# ---------------------------------------------------------------- 输入：工件
class ProcessType(str, Enum):
    MILLING = "MILLING"
    TURNING = "TURNING"
    TURN_MILL = "TURN_MILL"


class MaterialSpec(_Base):
    name: str = Field(..., description="材料牌号，如 C45 / 6061-T6 / SUS304 / Ti6Al4V / HT250 / 42CrMo")
    hardness_hb: Optional[float] = Field(None, ge=30, le=750)
    tensile_mpa: Optional[float] = Field(None, ge=50, le=2500)


class Envelope(_Base):
    """零件外形包络。cylindrical: diameter+length（Z 为回转轴）；prismatic: x,y,z。"""

    type: Literal["cylindrical", "prismatic"]
    diameter: Optional[float] = Field(None, gt=0)
    length: Optional[float] = Field(None, gt=0)
    x: Optional[float] = Field(None, gt=0)
    y: Optional[float] = Field(None, gt=0)
    z: Optional[float] = Field(None, gt=0)


FeatureType = Literal[
    # 回转类（车削原生）
    "face", "od_cylinder", "od_taper", "groove_od", "thread_od", "chamfer_od", "bore_axial",
    # 非回转类（铣削原生）
    "planar_face", "pocket", "slot", "contour", "hole", "thread_hole", "keyway", "flat",
    "cross_hole", "polygon", "chamfer_edge",
]


class Feature(_Base):
    """加工特征。坐标在零件坐标系：prismatic 原点=毛坯顶面左下角；cylindrical 原点=右端面中心，-Z 指向卡盘。

    ``params`` 典型键：
      od_cylinder: diameter, z_start, z_end（z_end < z_start <= 0）
      od_taper: d_start, d_end, z_start, z_end
      groove_od: diameter(槽底), width, z
      thread_od: diameter, pitch, z_start, z_end
      chamfer_od: size, z
      bore_axial / hole(on axis): diameter, depth
      pocket: x, y(中心), length, width, depth, corner_radius
      slot: x1, y1, x2, y2, width, depth
      contour: x, y, length, width, depth（外轮廓凸台）
      planar_face: depth
      hole/thread_hole: x, y, diameter, depth, (pitch)；cylindrical 上的轴向偏心孔: radius(分布圆半径), angle
      keyway/flat: length, width, depth, z_center, angle
      cross_hole: diameter, z, angle, through(bool)
      polygon: sides, across_flats, length
    """

    id: str
    type: FeatureType
    params: Dict[str, float] = Field(default_factory=dict)
    tolerance_mm: Optional[float] = Field(None, gt=0, description="对称公差带宽（±值的两倍）")
    ra_um: Optional[float] = Field(None, gt=0)
    on_axis: Optional[bool] = Field(None, description="仅对 hole/bore 有意义：是否与回转轴同轴")


class StockSpec(_Base):
    type: Literal["bar", "block", "plate", "tube", "casting"]
    diameter: Optional[float] = Field(None, gt=0)
    length: Optional[float] = Field(None, gt=0)
    x: Optional[float] = Field(None, gt=0)
    y: Optional[float] = Field(None, gt=0)
    z: Optional[float] = Field(None, gt=0)


class WorkpieceSpec(_Base):
    part_id: str
    material: MaterialSpec
    envelope: Envelope
    stock: StockSpec
    features: List[Feature] = Field(..., min_length=1)
    general_tolerance_mm: float = Field(0.1, gt=0)
    general_ra_um: float = Field(3.2, gt=0)
    batch_size: int = Field(1, ge=1)


# ---------------------------------------------------------------- M1 输出
class RecognitionResult(_Base):
    part_id: str
    process_type: ProcessType
    confidence: float = Field(..., ge=0, le=1)
    probabilities: Dict[str, float]
    low_confidence: bool
    rationale: List[str] = Field(default_factory=list)
    feature_votes: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    exception: Optional[Dict[str, Any]] = None
    engine_version: str = ""


# ---------------------------------------------------------------- M2 输入/输出
class ObjectiveWeights(_Base):
    efficiency: float = Field(0.35, ge=0)
    tool_wear: float = Field(0.2, ge=0)
    precision: float = Field(0.25, ge=0)
    cost: float = Field(0.2, ge=0)


class CustomConstraint(_Base):
    """动态扩展约束：安全表达式（AST 白名单），形如 ``"Vc * f <= 60"``。

    可用变量：Vc, f, fz, ap, ae, n, vf, D, z, Pc, Ra, T_life, defl, mrr, t_cut
    """

    name: str
    expr: str
    applies_to: List[str] = Field(default_factory=list, description="空=全部工序类别")
    hard: bool = True


class MachineLimits(_Base):
    max_rpm: float = Field(8000, gt=0)
    max_power_kw: float = Field(11.0, gt=0)
    max_feed_mm_min: float = Field(10000, gt=0)
    max_torque_nm: Optional[float] = Field(None, gt=0)
    live_tool_max_rpm: float = Field(4000, gt=0)
    live_tool_power_kw: float = Field(3.7, gt=0)


class OptimizationRequest(_Base):
    workpiece: WorkpieceSpec
    process_type: ProcessType
    weights: ObjectiveWeights = Field(default_factory=ObjectiveWeights)
    machine_limits: MachineLimits = Field(default_factory=MachineLimits)
    custom_constraints: List[CustomConstraint] = Field(default_factory=list)
    disabled_constraints: List[str] = Field(default_factory=list)
    time_budget_s: float = Field(25.0, gt=0, le=30.0)
    seed: int = 7
    machine_rate_per_h: float = Field(120.0, gt=0, description="机时费（货币/小时）")


class ToolSpec(_Base):
    tool_id: str
    kind: Literal[
        "face_mill", "end_mill", "ball_mill", "drill", "spot_drill", "reamer", "tap",
        "turn_rough", "turn_finish", "groove", "thread", "boring_bar",
        "live_end_mill", "live_drill",
    ]
    diameter: float = Field(..., gt=0)
    flutes: int = Field(1, ge=1)
    corner_radius: float = Field(0.0, ge=0)
    length: float = Field(..., gt=0, description="伸出长度/刀长")
    flute_length: float = Field(..., gt=0)
    max_ap: float = Field(..., gt=0)
    center_cutting: bool = True
    edge_cost: float = Field(8.0, gt=0, description="单刃成本")
    pitch: Optional[float] = None


class CuttingParams(_Base):
    vc_m_min: float
    rpm: float
    feed_mm_min: float
    feed_per_rev: Optional[float] = None
    feed_per_tooth: Optional[float] = None
    ap_mm: float
    ae_mm: Optional[float] = None
    constant_surface_speed: bool = False


class OperationMetrics(_Base):
    cut_time_min: float
    tool_life_min: float
    tool_wear_fraction: float
    ra_pred_um: float
    deflection_mm: float
    power_kw: float
    cost: float
    binding_constraints: List[str] = Field(default_factory=list)
    max_violation: float = 0.0


class Operation(_Base):
    op_id: str
    seq: int
    category: str
    feature_ids: List[str]
    tool: ToolSpec
    params: CuttingParams
    metrics: OperationMetrics
    geometry: Dict[str, Any] = Field(default_factory=dict, description="生成刀路所需几何（来自特征）")
    setup: Literal["main", "live"] = "main"
    notes: List[str] = Field(default_factory=list)


class ProcessPlan(_Base):
    part_id: str
    process_type: ProcessType
    material: str
    operations: List[Operation]
    totals: Dict[str, float]
    weights: ObjectiveWeights
    solver: Dict[str, Any]
    feasible: bool
    infeasible_reasons: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------- 毛坯摆放
class FixtureZone(_Base):
    name: str
    kind: Literal["vise_jaw", "chuck_jaw", "parallel", "tailstock"]
    # prismatic: 盒体 [xmin,xmax,ymin,ymax,zmin,zmax]；turning: [zmin,zmax,rmin,rmax]
    box: List[float]


class StockSetup(_Base):
    part_id: str
    fixture: Literal["vise", "three_jaw_chuck", "chuck_tailstock"]
    wcs_origin: str
    stock_dims: Dict[str, float]
    part_offset_in_stock: Dict[str, float]
    stickout_mm: float
    grip_mm: float
    fixture_zones: List[FixtureZone]
    rules_applied: List[Dict[str, Any]]
    warnings: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------- M3 输出
class Move(_Base):
    """中间表示（IR）中的一条指令，控制系统无关。"""

    kind: Literal[
        "comment", "rapid", "linear", "arc_cw", "arc_ccw", "thread", "dwell",
        "tool_change", "spindle", "spindle_stop", "coolant", "coolant_off",
        "work_offset", "safe_retract", "c_axis", "feed_mode", "css", "program_end",
        "live_spindle", "live_spindle_stop",
    ]
    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None
    c: Optional[float] = None
    i: Optional[float] = None
    j: Optional[float] = None
    f: Optional[float] = None
    s: Optional[float] = None
    tool: Optional[int] = None
    text: Optional[str] = None
    op_id: Optional[str] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


class PostProfile(_Base):
    """控制系统/机床专用指令映射规则（由 M4 产出，M3 消费）。"""

    dialect: Literal["FANUC", "SIEMENS", "HUAZHONG"] = "FANUC"
    machine_kind: Literal["mill", "lathe", "turn_mill"] = "mill"
    program_number: int = Field(1, ge=1, le=9999)
    work_offset: str = "G54"
    coolant_on: str = "M08"
    coolant_off: str = "M09"
    spindle_max_rpm: float = 8000
    live_spindle_cw: str = "M13"
    live_spindle_stop: str = "M15"
    c_axis_on: str = "M18"
    c_axis_off: str = "M19"
    home_return: Literal["G28", "G53", "SUPA"] = "G28"
    tool_number_map: Dict[str, int] = Field(default_factory=dict)
    line_numbers: bool = True
    line_step: int = 5
    decimals: int = 3
    max_rpm_clamp_code: Optional[str] = None


class NCProgram(_Base):
    part_id: str
    process_type: ProcessType
    dialect: str
    program_text: str
    ir: List[Move]
    tool_table: List[Dict[str, Any]]
    stats: Dict[str, Any]
    post_profile: PostProfile
    sha256: str


class ProgramRequirements(_Base):
    """M4 只看 NC 程序就能推导出的需求（由 M4 自行从 NCProgram 提取）。"""

    process_type: ProcessType
    max_rpm: float
    max_feed: float
    tools_count: int
    max_tool_diameter: float
    max_tool_length: float
    needs_y_axis: bool
    needs_c_axis: bool
    needs_live_tool: bool
    envelope_mm: Dict[str, float]
    peak_power_kw: float = 0.0


# ---------------------------------------------------------------- M4 输出
class MachineSpec(_Base):
    model: str
    vendor: str
    kind: Literal["mill", "lathe", "turn_mill"]
    controller: str
    dialect: Literal["FANUC", "SIEMENS", "HUAZHONG"]
    travel: Dict[str, float]
    max_rpm: float
    spindle_power_kw: float
    max_feed_mm_min: float
    rapid_mm_min: float
    tool_capacity: int
    max_tool_diameter: float
    max_tool_length: float
    has_y_axis: bool = False
    has_c_axis: bool = False
    live_tooling: bool = False
    live_tool_max_rpm: float = 0
    live_tool_power_kw: float = 0
    max_swing_diameter: float = 0
    max_turning_length: float = 0
    table_center: Dict[str, float] = Field(default_factory=dict)
    coolant_codes: Dict[str, str] = Field(default_factory=lambda: {"on": "M08", "off": "M09"})
    live_codes: Dict[str, str] = Field(default_factory=dict)
    supported_g: List[str] = Field(default_factory=list)
    supported_m: List[str] = Field(default_factory=list)
    basis: str = "nominal_catalog_approx"


class MachineSetup(_Base):
    machine: MachineSpec
    match_score: float
    candidates: List[Dict[str, Any]]
    work_offset: str
    work_offset_values: Dict[str, float]
    tool_pockets: List[Dict[str, Any]]
    post_profile: PostProfile
    travel_check: Dict[str, Any]
    notes: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------- 校验
class RiskItem(_Base):
    level: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
    check: str
    code: str
    message: str
    location: Dict[str, Any] = Field(default_factory=dict)


class VerificationReport(_Base):
    part_id: str
    passed: bool
    path_check: Dict[str, Any]
    compat_check: Dict[str, Any]
    risks: List[RiskItem]
    summary: Dict[str, int]
    html_path: Optional[str] = None
    json_path: Optional[str] = None


class PipelineResult(_Base):
    trace_id: str
    status: Literal["SUCCESS", "BLOCKED", "FAILED"]
    part_id: str
    recognition: Optional[RecognitionResult] = None
    plan: Optional[ProcessPlan] = None
    stock_setup: Optional[StockSetup] = None
    program: Optional[NCProgram] = None
    machine_setup: Optional[MachineSetup] = None
    verification: Optional[VerificationReport] = None
    output_files: Dict[str, str] = Field(default_factory=dict)
    stage_timings_ms: Dict[str, float] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)
    events: List[Dict[str, Any]] = Field(default_factory=list)
