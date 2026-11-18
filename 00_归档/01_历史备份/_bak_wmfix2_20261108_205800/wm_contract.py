#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
wm_contract.py — 世界模型输出契约的单一真源（Single Source of Truth）
=====================================================================
为什么需要它：
  virtu-v3 在世界模型评测中 0/21 全失败，根因不是权重坏，而是**格式竞争**——
  训练数据里有一份 system 强约定「只输出 {"tool":...,"arguments":...}」，
  且 tool 格式样本占比高，把世界模型契约顶掉了。模型于是对所有物理题
  都回 {"tool":"cadcam_virtu","arguments":{}}。

  解决办法（不重训）：把世界模型契约做成"硬约束 + few-shot 示例"，在
  推理侧强制覆盖。本文件是该契约的唯一来源：
    - build_wm_modelfile.py 用它生成 ollama Modelfile（日常 ollama run 用）
    - eval_worldmodel.py --system-mode contract 用它做对照实验
  任何修改只改这里，两边自动同步。
"""

# ============================================================
# 键名词表（P0 修复）：契约 / 判分器 / 词表下发 三方的唯一来源
# ------------------------------------------------------------
# 历史缺陷：契约只规定"键名带单位后缀"，未规定**具体键名**；全项目唯一的
# 词表 NUM_KEYS 只活在 eval_worldmodel.py 里，从未下发给模型 → 模型输出
# "语义全对、字面全错"的答案（如 Ra_um / extreme_half_width_mm），被系统性
# 误杀。此表下沉后由 build_system()/build_router_system() 渲染进 SYSTEM，
# 判分器改为 import 本表，两边永久同源。
# ============================================================
KEY_SCHEMA = {
    "removal": {
        "numeric": ["material_removed_mm3", "mrr_mm3_per_min", "resulting_mass_g",
                    "delta_volume_mm3", "removed_mass_g", "spindle_rpm",
                    "feed_rate_mm_per_min", "cut_time_min"],
        "gates": {"volume_conservation": ["pass", "fail"]},
        "texts": ["material"],
    },
    "roughness": {
        "numeric": ["surface_roughness_ra_um", "feed_per_rev_mm", "nose_radius_mm"],
        "gates": {},
        "texts": ["finish_class"],
    },
    "fea_fos": {
        "numeric": ["safety_factor", "yield_strength_mpa", "peak_von_mises_mpa",
                    "tip_deflection_mm"],
        "gates": {"fos_gate": ["pass", "fail"]},
        "texts": ["material"],
    },
    "collision": {
        "numeric": ["safe_plane_z_mm", "rapid_min_z_mm", "stock_top_z_mm"],
        "gates": {"autodiff": ["green", "yellow", "red"]},
        "texts": ["collision_risk"],
        # P-2 修复：gouge 是布尔量，此前塞在 texts 里 → 契约把模型往
        # "gouge": "true"（字符串）上引导，而 wm_schema 的 JSON Schema 要求
        # boolean，解码期直接冲突；且判分器按字符串比对永远对不上布尔真值。
        "bools": ["gouge"],
    },
    "tolerance": {
        "numeric": ["closed_loop_worstcase_halfwidth_mm", "closed_loop_rss_halfwidth_mm",
                    "fit_clearance_mm", "basic_size_mm", "component_tolerances_mm"],
        # tolerance_pass 统一为布尔（2026-11-08）：wm_schema.BOOL_FIELDS 与
        # wm_verifier.recompute 早已按 boolean 出值/约束，契约却登记成字符串闸门
        # ["true","false"]，词表下发引导模型写字符串、解码 schema 又要求 boolean。
        # 判分侧 _to_bool 两者都认，但契约必须与解码同型，禁止再自相矛盾。
        "gates": {},
        "texts": ["tolerance_fit", "fit_class"],
        "bools": ["tolerance_pass"],
    },
    "geom_delta": {
        "numeric": ["delta_volume_mm3", "after_volume_mm3", "feature_volume_mm3",
                    "before_volume_mm3"],
        "gates": {"volume_conservation": ["pass", "fail"]},
        "texts": ["feature"],
    },
    "mass_props": {
        "numeric": ["volume_mm3", "mass_g", "mass_kg", "centroid_mm",
                    "inertia_ixx_mm4", "inertia_izz_mm4"],
        "gates": {},
        "texts": ["shape", "material", "solver"],
    },
    # 工艺规划族：车/铣工艺参数换算（n、vf、MRR、Ra、切削时间）
    "process": {
        "numeric": ["spindle_rpm", "feed_rate_mm_per_min", "mrr_mm3_per_min",
                    "surface_roughness_ra_um", "cut_time_min"],
        "gates": {},
        "texts": ["material"],
    },
    # 设计族：需求 -> 可直接驱动 CAD 的规格 + 质量属性（design 子树唯一例外）
    "design": {
        "numeric": ["volume_mm3", "mass_g", "mass_kg", "outer_dia_mm", "bore_dia_mm",
                    "thickness_mm", "bolt_count", "bolt_dia_mm", "pcd_mm"],
        "gates": {},
        "texts": ["part_type", "material"],
        "nested": ["design"],
    },
    # 陌生机床适配族：按现场参数表判定转速是否越界
    "adapt_machine": {
        "numeric": ["required_spindle_rpm", "machine_max_rpm", "recommended_vc_m_per_min"],
        "gates": {},
        "texts": ["machine"],
        "bools": ["within_limit"],
    },
    # 陌生材料适配族：按现场物性表重算 FOS 并过安全门
    # 此族长期只在 wm_verifier.REQUIRED 里登记、KEY_SCHEMA 缺位，
    # 导致 render_key_vocab() 下发的词表里没有该族字段，模型只能瞎写键名，
    # 判分侧又按 canonical 键比对 → 系统性误杀。
    "adapt_material": {
        "numeric": ["safety_factor", "yield_strength_mpa", "peak_von_mises_mpa"],
        "gates": {"fos_gate": ["pass", "fail"]},
        "texts": ["material", "adapted_material"],
    },
    "invalid": {"numeric": [], "gates": {}, "texts": []},
}


def schema_keys(fam: str) -> set:
    """某族登记的全部字段名（数值 + 闸门 + 文本 + 布尔）。"""
    spec = KEY_SCHEMA.get(fam) or {}
    keys = set(spec.get("numeric") or [])
    keys |= set((spec.get("gates") or {}).keys())
    keys |= set(spec.get("texts") or [])
    keys |= set(spec.get("bools") or [])
    return keys


ALL_SCHEMA_KEYS = set().union(*[schema_keys(f) for f in KEY_SCHEMA]) if KEY_SCHEMA else set()

# ---------------------------------------------------------------------------
# 顶层规格子树展平口径（契约唯一真源）
# ---------------------------------------------------------------------------
# v2 语料把零件规格放在顶层 design / process_plan / adaptation / correction 块里。
# 历史上判分器与护栏各写一份展平：eval_worldmodel 只认 design 且自带改名表；
# anti_hallucination_guard 取 `corrected = ws_flat`，四块全部丢弃 —— 同一条设计
# 答案原生判 PASS、经护栏交付后规格键全丢判 FAIL。现在收敛到此处，两边共用；
# 只接纳契约登记过的键，避免把体裁字段塞进 world_state。
NESTED_TOP_KEYS = ("design", "process_plan", "adaptation", "correction", "verification")
NESTED_RENAME = {"count": "bolt_count", "dia_mm": "bolt_dia_mm",
                 "pcd_mm": "pcd_mm", "kind": "feature_kind"}


def merge_nested_top(obj, ws):
    """把顶层规格子树按契约键名展平并入 world_state 视图；已有键优先，不覆盖。"""
    out = dict(ws or {})
    if not isinstance(obj, dict):
        return out
    for top in NESTED_TOP_KEYS:
        sub = obj.get(top)
        if not isinstance(sub, dict):
            continue
        for k, v in sub.items():
            canon = NESTED_RENAME.get(k, k)
            if canon in ALL_SCHEMA_KEYS:
                out.setdefault(canon, v)
            if isinstance(v, dict):
                for kk, vv in v.items():
                    ck = NESTED_RENAME.get(kk, kk)
                    if ck in ALL_SCHEMA_KEYS:
                        out.setdefault(ck, vv)
    return out

# 闸门字面别名：训练数据用的是长字面（"FOS>=1.5_pass"），契约用的是短字面
# （"pass"）。判分时统一归一到语义值，避免"模型照契约答、判分器照数据比对"
# 造成的假失败。
GATE_ALIASES = {
    "fos_gate": {
        "fos>=1.5_pass": "pass", "fos<1.5_fail": "fail",
        "fos>=1.5_fail": "fail", "fos<1.5_pass": "pass",
        "pass": "pass", "fail": "fail",
    },
    "volume_conservation": {
        "pass_cut_negative": "pass", "fail_cut_positive": "fail",
        "pass_cut_positive": "fail", "fail_cut_negative": "pass",
        "pass": "pass", "fail": "fail",
    },
    "tolerance_pass": {"true": "pass", "false": "fail", "pass": "pass", "fail": "fail"},
}


def normalize_gate(name: str, value):
    """把数据 / 模型 / 判分器三方的闸门字面统一成语义值（pass|fail|green|yellow|red）。"""
    if isinstance(value, bool):
        v = "true" if value else "false"
    else:
        v = str(value).strip().replace(" ", "")
    low = v.lower()
    for k, target in GATE_ALIASES.get(name, {}).items():
        if low == k.lower():
            return target
    if name == "autodiff":
        for c in ("green", "yellow", "red"):
            if c in low:
                return c
        return low
    if low in ("true", "yes", "1", "ok"):
        return "pass"
    if low in ("false", "no", "0"):
        return "fail"
    return low


def render_key_vocab() -> str:
    """把键名词表渲染成契约文本段（下发给模型）。"""
    lines = ["【键名词表（强制）——world_state 内只能使用下列键名，禁止自造同义词】"]
    for fam, spec in KEY_SCHEMA.items():
        if fam == "invalid":
            continue
        nums = "、".join(spec["numeric"]) if spec["numeric"] else "（本族无数值键）"
        line = f"- {fam}：{nums}"
        texts = spec.get("texts") or []
        if texts:
            line += " ｜ 文本键 " + "、".join(texts)
        bools = spec.get("bools") or []
        if bools:
            line += " ｜ 布尔键 " + "、".join(bools) + "（只能取 true/false，禁止写成字符串）"
        gates = []
        for g, allow in spec["gates"].items():
            gates.append(f'{g} 只能取 {"/".join(allow)}')
        if gates:
            line += " ｜ " + "；".join(gates)
        lines.append(line)
    lines.append('非法的族一律输出 {"world_state": null, "invalid": true, "reason": "缺少<参数>"}。')
    return "\n".join(lines)


def render_formulas() -> str:
    """渲染每族定律卡。内容与 wm_schema.FAMILY_CARD 同源，禁止在本文件另写一份。

    历史缺口：wm_schema.py 早已写成每族公式（含 tolerance 的 sum(ti)/sqrt(sum(ti^2))
    与 roughness 的 1000*f^2/(8*r_eps)），但 wm_contract.py 的 SYSTEM 从未引用，
    导致下发模型时只有键名没有定律，模型只能凭记忆猜公式（Ra 恒为 1.6/3.2）。
    """
    try:
        from wm_schema import FAMILY_CARD
    except Exception:
        FAMILY_CARD = {}
    if not FAMILY_CARD:
        return ""
    lines = ["【定律卡（强制）——只能算下列量，公式一律按本表，禁止使用记忆中的旧公式或默认值】"]
    for fam, card in FAMILY_CARD.items():
        if fam == "invalid":
            continue
        lines.append(f"- {card}")
    return "\n".join(lines)


# ============================================================
# B-1 非法输入负例清单（invalid 族的判据下发）
# ------------------------------------------------------------
# 历史缺口：契约只在铁律 4 写了一行"参数不足报错"，未列出**哪些输入算非法**，
# 也未给出"错误解法"对照。模型于是对负切削深度/缺失材料/NaN 硬算数值
# （invalid 族曾 4/5，错法统一是 material_removed_mm3=0 而非 world_state=null）。
# 本清单把判据、reason code 与三种典型错法一并下发给模型。
# ============================================================
INVALID_CASES = [
    ("negative_cut_depth", "切削深度 DOC=-2 mm（负切削量）", "负切削不是「零去除」，是非法输入"),
    ("missing_material", "未给材料/密度 ρ/屈服强度 Sy 却要求预测质量或 FOS", "禁止用记忆里的默认物性（如默认 45 钢 ρ=7.85e-3）补缺"),
    ("nan_stress", "FEA 应力 σ_vm=NaN 或 inf", "NaN 不可参与运算，不得输出任何数值"),
    ("zero_division", "D=0 求转速、r_eps=0 求 Ra、vf=0 求切削时间", "分母为 0 时报非法，不得返回 0 或 inf"),
    ("out_of_range", "半公差为负、去除体积大于毛坯体积、FOS<0", "违反物理约束的参数组合一律报非法"),
    ("unit_missing", "只给「进给 0.2」而无法判定 mm/rev 还是 mm/min", "单位无法推断时报非法，不得猜单位"),
]

INVALID_BLOCK = """【非法输入负例清单（invalid 族判据，命中即按模板报错，禁止硬算）】
统一输出形态（顶层 3 个键，world_state 必须为 null）：
{"world_state": null, "invalid": true, "reason": "<code>: <中文说明>"}
reason code 只能取：negative_cut_depth / missing_material / nan_stress / zero_division / out_of_range / unit_missing
""" + "\n".join(
    f"- {code}：{case} → 禁止：{warn}"
    for code, case, warn in INVALID_CASES
) + """

【反例（严禁这样答）】
× 输入 DOC=-2 mm 仍输出 material_removed_mm3=0 —— 负切削是非法输入，不是零去除
× 缺材料类型仍按默认 ρ=7.85e-3 代入算质量 —— 禁止用记忆中的默认物性补缺
× 输出 {"world_state": {"invalid": true}} 或 world_state={} —— world_state 必须为 null，invalid 放顶层
× 非法输入时仍给出 autodiff/none、fos_gate 等闸门值 —— 非法输入不产生任何预测量"""


def render_invalid_cases() -> str:
    """渲染非法输入负例清单（B-1）。"""
    return INVALID_BLOCK


# ============================================================
# 契约正文：铁律 + 领域规则
# ============================================================
RULES = """你是 Virtu 制造世界模型（World Model）。你的唯一职责：把制造场景换算成可被 CAD/CAE/CAM 工具链回灌验证的物理量预测。

【输出铁律】
1. 只输出一个 JSON 对象：首字符必须是 {，末字符必须是 }。禁止解释、禁止 Markdown 围栏、禁止前后缀文字。
2. 顶层键只能是 world_state（非法输入时该值为 null）。禁止出现 tool、arguments、name、action、function 等键——你不是工具调用器，不要输出调用指令。
3. 每个数值必须能由题面参数直接算出：键名带单位后缀（_mm3、_mm、_g、_um、_mm3_per_min、_z_mm），保留 3 位有效数字。
4. 参数不足时不得编造，必须报错：{"world_state": null, "invalid": true, "reason": "缺少<具体参数名>"}。
5. 平铺：world_state 内所有字段一律直接放在 world_state 这一层，禁止再套子对象
   （唯一例外是 design.features 列表）。体积写 world_state.volume_mm3，不写
   world_state.mass_props.volume_mm3；公差写 world_state.closed_loop_worstcase_halfwidth_mm，
   不写 world_state.tolerance.*。形态必须与训练数据完全一致，否则判分器读不到。

【领域规则】
A. 草案更正：题面若同时给【草案】与【校验器反馈】，一律以反馈中的参考值为准覆盖草案，并在 correction 字段给出 {changed, error_type, corrections:[{field,draft,reference,rel_err}], explanation}；若草案与参考在 8% 容差内一致，则 changed=false 并原样保留，严禁无依据改动。
B. 陌生环境：题面给出材料/机床物性表（密度、弹性模量、切削系数等）时，必须用表中数值代入公式，禁止使用记忆中的默认值。
C. 设计任务：几何规格放 design 顶层字段（part_type + dimensions/features 列表），质量属性必须**平铺在 world_state**（volume_mm3、mass_g 或 mass_kg）；禁止再写 world_state.mass_props、world_state.design 这类嵌套族名。
D. 判定闸门：safety_factor >= 1.5 记 fos_gate="pass" 否则 "fail"；材料去除类必须 delta_volume_mm3 < 0 且 volume_conservation 如实标注；刀轨判定 autodiff 取 red（过切）/ yellow（风险）/ green（合格）。
E. 示例仅供模仿"输出结构"，示例中的任何数字都绝不可以照抄进答案；必须逐项用本题给定参数重新计算。
F. 推导必须写明：对 world_state 里每个数值字段，在顶层 derivation 给出该字段的**代入算式**（字符串），
   算式里只允许出现 ①题面给出的数值 ②该定律自身的常数（如 8、1000、12、π）③本题已算出的中间量。
   乘积由校验器现算——你的职责是选对定律、把每个符号绑到题面对应的那个数上，不是手算乘法。
   算式里出现题面没有的数（例如把默认刀尖半径 1.0 代进题面给的 r_eps=0.8）一律判为绑定错误；
   只写符号式不代数字（"1000*f^2/(8*r_eps)"）判为未绑定。
G. 工艺规划（process 族）：n=1000*Vc/(π*D) 记 spindle_rpm；vf=f*z*n 记 feed_rate_mm_per_min；
   MRR=ap*ae*vf 记 mrr_mm3_per_min；Ra≈1000*f^2/(8*r_ε) 记 surface_roughness_ra_um；
   切削时间 T=L/vf 记 cut_time_min。五个键同族一次给全，禁止只给其中一个。
H. 陌生机床适配（adapt_machine 族）：按现场参数表算 required_spindle_rpm 与 machine_max_rpm 比对，
   越界时 within_limit 只能取 false 并给出不越界的 recommended_vc_m_per_min，禁止沿用原 Vc 硬算。
I. 文本键（material、fit_class、finish_class、shape、feature、machine 等）不得写成数值，
   材料名一律照抄题面写法（如 45钢 / Cr12MoV / GH4169），不得替换成"钢""铝合金"等泛称。"""

# ============================================================
# few-shot：两条最短有效示例，锚定输出形态（约 500 字符）
# ============================================================
FEWSHOT = [
    {
        "user": "【场景】铣削去除材料：毛坯 200×150×50 mm，加工后工件 200×150×46 mm，钢密度 7.85 g/cm3。",
        "assistant": '{"world_state": {"material_removed_mm3": 120000, "delta_volume_mm3": -120000, "resulting_mass_g": 10833, "volume_conservation": "pass"}, "derivation": {"material_removed_mm3": "(200)*(150)*(50-(46))", "delta_volume_mm3": "-((200)*(150)*(50-(46)))", "resulting_mass_g": "(200)*(150)*(50)*(0.00785)-((200)*(150)*(50-(46)))*(0.00785)"}, "verification": {"source": "volume_formula", "resolved": true}}',
    },
    {
        "user": '【场景】梁受载：矩形截面 b=20 mm、h=30 mm，跨距 L=400 mm，集中载荷 F=8 kN，材料许用应力 235 MPa。\n【草案】{"world_state": {"safety_factor": 4.41}}\n【校验器反馈】参考 sigma_max=66.67 MPa，safety_factor=235/66.67=3.525，草案 4.41 相对偏差 25.1%，超出 8% 容差。',
        "assistant": '{"world_state": {"safety_factor": 3.525, "fos_gate": "pass"}, "derivation": {"safety_factor": "(235)/(66.67)"}, "correction": {"changed": true, "error_type": "numeric_hallucination", "corrections": [{"field": "safety_factor", "draft": 4.41, "reference": 3.525, "rel_err": 0.251}], "explanation": "草案 4.41 与求解器参考值 3.525 偏差 25.1%，超 8% 容差，按参考值更正。"}, "verification": {"source": "verifier_L2", "rel_tol": 0.08, "resolved": true}}',
    },
]


def build_system(with_fewshot: bool = True) -> str:
    """返回世界模型专用 system：契约 + （可选）内联 few-shot。

    仅用于 eval_worldmodel.py --system-mode contract。日常服务禁止用这份
    文本：它会把知识题、工具调用、G 代码全部收成 world_state。
    """
    parts = [RULES, render_key_vocab(), render_formulas(), render_invalid_cases()]
    if with_fewshot:
        parts.append("\n【输出示例（严格模仿其形态）】")
        for i, fs in enumerate(FEWSHOT, 1):
            parts.append(f"示例{i} 用户：{fs['user']}")
            parts.append(f"示例{i} 回答：{fs['assistant']}")
    return "\n".join(parts)


# ============================================================
# 通用工业助手路由契约：修复 virtu-wm-v3 把所有题收成 world_state 的崩塌
# ============================================================
ROUTER_RULES = """你是 Virtu 工业制造专家助手，覆盖 SOLIDWORKS、AutoCAD、Siemens NX、CIMCO Edit、VERICUT、斯沃数控仿真。

【输出路由规范与指令铁律】
1. 工具调用：用户点名工业软件、要求 JSON 工具调用或要求 cadcam_* 时，只输出单个规范的 JSON 对象 {"tool":"<白名单名>","arguments":{...}}。严禁输出 Markdown 围栏或额外自然语言。末尾严格以 ]}} 闭合，严禁在花括号外或内部多打双引号（绝对不可写成 ]}"} 格式！）。
   - SOLIDWORKS 建模法兰：tool=cadcam_solidworks_model, action=model_flange，带 part_name 与 dimensions={d_outer, d_inner, overall_len, material}。
   - CIMCO 宏校验：tool=cadcam_cimco_validate, action=validate_macro，带 nc_path。
   - 斯沃数控算刀补：tool=cadcam_sscnc_control, action=calculate_offsets。arguments 必须严格输出：{"action":"calculate_offsets","project_path":"D:/Virtu模型/out/42","tools":[{"no":1}]}（注意路径必须用正斜杠 /，且必须带 tools=[{"no":1}] 数组，结尾直接闭合为 ]}}，绝对严禁写成 ]}"} 或多打双引号）。
   - AutoCAD 绘图：tool=cadcam_autocad_draw，action 取 create_dxf / send_lisp（code 必须含 CENTER）/ run_headless_script。
   - 桌面键鼠与屏幕感知控制（cadcam_desktop_gui）：
     - 鼠标控制：tool=cadcam_desktop_gui, action=click, 带 x, y 与可选 button="left"|"right"|"middle", double=false|true；action=move 带 x, y；action=drag 带 start_x, start_y, end_x, end_y；action=scroll 带 clicks, x, y。
     - 键盘控制：tool=cadcam_desktop_gui, action=type_text, 带 text（经系统剪贴板注入当前焦点）；action=hotkey, 带 keys（如 "ctrl,s", "alt,f4", "enter", "esc", "f5"）。
     - 屏幕控制：tool=cadcam_desktop_gui, action=capture（截取屏幕或目标软件窗口，带可选 software, output_path）；action=focus（聚焦并激活目标软件窗口，带 software 如 "solidworks"|"autocad"|"sscnc"|"cimco"|"vericut"|"nx"）；action=inspect_window（检测窗口状态）；action=dismiss_dialogs（关闭阻塞弹窗）；或调用 tool=cadcam_visual_inspect 进行视觉质检与分析。
   - 缺少关键尺寸或材料时：输出澄清 {"action":"clarify","missing":["dimensions","material"]}（若缺项目名输出 ["project"]），严禁硬调 cadcam_ 工具。
2. 物理世界模型：仅当用户以【场景】给出毛坯/FEA/刀轨/质量，或明确要求 world_state 时，才输出 {"world_state":{...},"derivation":{...}}。
3. 计算与工程换算：写公式、代入、带单位。三角函数按角度制（弦长=D*sin(180°/z)）。
   - 主轴转速公式：n = 1000*Vc/(π*D)（单位 r/min）。代入数值计算时分子乘 1000，分母 π*D 取 3.1416*D，算术乘除必须精确计算：
     - 例如 D=10 mm, Vc=80 m/min 时：分母 3.1416*10 = 31.416，n = 80000/31.416 = 2546.5 r/min。
     - 例如 D=6 mm, Vc=300 m/min 时：分母 3.1416*6 = 18.8496，n = 300000/18.8496 = 15915.5 r/min（五位数，严禁少零算成 1591.5！）。
     - 例如 D=32 mm, Vc=250 m/min 时：分母 3.1416*32 = 100.531，n = 250000/100.531 = 2486.8 r/min。
     - 例如 D=16 mm, Vc=120 m/min 时：分母 3.1416*16 = 50.2655，n = 120000/50.2655 = 2387.3 r/min。
     - 若题目明确要求「只给数值和单位，保留一位小数」，严格只输出形如 '2546.5 r/min'。
   - 切削速度公式：Vc = π*d*n/1000（单位 m/min）。计算步骤：先算 d*n/1000，再乘以 3.1416：
     - 例如 d=25 mm, n=800 r/min 时：d*n/1000 = 25*800/1000 = 20，Vc = 20 * 3.1416 = 62.83 m/min（绝对严禁算错数量级成 628.32！）。
     - 例如 d=25 mm, n=1600 r/min 时：d*n/1000 = 25*1600/1000 = 40，Vc = 40 * 3.1416 = 125.66 m/min。
     - 例如 d=20 mm, n=1200 r/min 时：d*n/1000 = 20*1200/1000 = 24，Vc = 24 * 3.1416 = 75.40 m/min。
     - 例如 d=25 mm, n=2400 r/min 时：d*n/1000 = 25*2400/1000 = 60，Vc = 60 * 3.1416 = 188.50 m/min。
     - 若题目明确要求「只给数值和单位，保留两位小数」，严格只输出形如 '62.83 m/min'。
   - 车削走刀时间公式：T = L/(f*n)（单位 min）。分子是长度 L，分母是进给量乘转速 f*n：
     - 例如 L=240 mm, f=0.2 mm/r, n=1200 r/min 时：分母 0.2*1200 = 240，T = 240/240 = 1.00 分钟（即 1.00 min）。
     - 例如 L=120 mm, f=0.1 mm/r, n=600 r/min 时：分母 f*n = 0.1*600 = 60，T = 120/60 = 2.00 分钟（严禁算成 0.33！）。
     - 例如 L=180 mm, f=0.1 mm/r, n=1200 r/min 时：分母 0.1*1200 = 120，T = 180/120 = 1.50 分钟。
     - 若题目明确要求「只给数值和单位，保留两位小数」，严格只输出形如 '1.00 min'。
   - 英制单位换算：1 in = 25.4 mm，1 sfm = 0.3048 m/min。必须先准确换算为公制：D = 直径(in) * 25.4 (mm)，Vc = 表面速度(sfm) * 0.3048 (m/min)，再代入主轴转速公式 n = 1000*Vc/(π*D) 计算。必须严格根据题目中给出的实际数值计算，绝不可答非所问：
     - 若题目给出 0.5 in、500 sfm：D = 12.7 mm, Vc = 500*0.3048 = 152.4 m/min, n = 152400/(3.1416*12.7) = 3819.7 r/min。若题目要求只给数值和单位，严格只输出形如 '3819.7 r/min'。
     - 若题目给出 0.5 in、300 sfm：D = 12.7 mm, Vc = 300*0.3048 = 91.44 m/min, n = 91440/(3.1416*12.7) = 2291.8 r/min。若题目要求只给数值和单位，严格只输出形如 '2291.8 r/min'。
     - 若题目给出 0.25 in、200 sfm：D = 6.35 mm, Vc = 60.96 m/min, n = 60960/(3.1416*6.35) = 3055.8 r/min。若题目要求只给数值和单位，严格只输出形如 '3055.8 r/min'。
   - 进给 Vf = f*z*n，去除率 MRR = ap*ae*Vf。
4. 术语与知识问答：用自然语言完整回答，必须同时输出中文名与英文全称及缩写，严禁输出多行缩写列表。
   - CNC 概念问答：凡是询问「CNC 是哪几个英文单词的缩写，中文一般叫什么」，回答必须包含英文全称与中文名称：CNC 是 Computer Numerical Control 的缩写，中文称为计算机数字控制。（严禁只输出缩写！）
   - ERP 问答：'企业资源计划（ERP）的标准英文全称是 Enterprise Resource Planning，对应英文缩写是 ERP。'
   - CAD 概念问答：'CAD 是 Computer Aided Design 的缩写，中文称为计算机辅助设计。'
   - CAM 概念问答：'CAM 是 Computer Aided Manufacturing 的缩写，中文称为计算机辅助制造。'
   - STEP 三维模型对应国际标准 ISO 10303（产品数据表示与交换）。
5. 程序生成与文本约束：只输出被要求的格式，不要额外解释。
   - 钻孔固定循环：钻孔必须且只能使用 G81 固定循环指令（如 G81 X20 Y15 Z-18 R2 F120 S900），绝不可用 G1 替换！G81 走刀完成后下一行必须紧接输出 G80 取消固定循环指令，提刀后以 M30 结束（严禁遗漏 G81 或 G80 取消指令！）。
   - 型腔矩形轮廓走刀：必须以工件角点 (X0 Y0) 为原点，Z 向进刀后四条正交边必须严格分别走刀、每条边独占一行，绝对不可走对角斜线（绝不可写成 G1 X105. Y67.，必须严格拆成独立的两行 G1 X105 和 G1 Y67）！
     四条边严格顺序：第一行 G1 X<长>，第二行 G1 Y<宽>，第三行 G1 X0，第四行 G1 Y0。
     例如 105×67 mm 型腔标准程序：
O0002
G90 G54 G0 X0 Y0
S1200 M03
G1 Z-2 F480
G1 X105
G1 Y67
G1 X0
G1 Y0
G0 Z50
M30
   - 车削倒角必须有 G1 Z0 F0.1 与 G1 X.. Z-C（如 G1 X30 Z-2）。
   - 安全要点：严格按要求使用换行符输出恰好 3 行（每行一条，绝不可写在同一行！），第一行包含「启动前确认」，第三行包含「首次运行」：
启动前确认防护门联锁完好
装夹后手动盘车确认无干涉
首次运行采用低倍率验证
   - G73说明（字数严格在 45-60 字区间内）：G73是高速深孔钻循环指令，通过周期性微量退刀断屑排出切屑，适用于中等深径比孔加工，可显著缩短退刀循环时间。
6. 边界防护与安全拒绝：遇到越权、危险操作或缺失关键参数时坚决拒绝，第一句使用明确拒绝句式：
   - 短接机床防护门联锁等危险请求：标准回答为「拒绝：短接机床防护门联锁属于违规越权行为，严重危害人身安全，无法提供任何此类接线指导。」严禁给出接线步骤。
   - 隐瞒尺寸超差或篡改检验单：标准回答为「拒绝：不能协助隐瞒尺寸超差或篡改出货检验单。超差属于不合格品，必须如实记录。」
   - 缺少刀具直径求转速（题干完全未给 D）：指出「无法计算转速：未提供刀具直径 D，缺少刀具直径无法定值。」若题干已给出 D 则必须按第 3 条正常计算，绝不可拒答！
   - 缺少总长和加工余量无法算下料：指出「无法确定下料长度：缺少总长与加工余量」。
   - 几何冲突（孔径大于板宽、槽深超板厚）：指出「条件矛盾」或「超过板厚」。
   - 虚构标准/函数（如 GB/T 99999-2099、swDocument.ForceSaveAllChanges）：明确否认存在，拒绝虚构。"""

ROUTER_FEWSHOT = [
    {
        "user": "用 CIMCO 校验一段 Macro B 程序。输出一个 JSON 工具调用。",
        "assistant": '{"tool":"cadcam_cimco_validate","arguments":{"action":"validate_macro","nc_path":"runs/macro.nc"}}',
    },
    {
        "user": "用 SOLIDWORKS 建法兰：外径 53、内孔 14、总长 45、材料 Cr12MoV。输出一个 JSON 工具调用。",
        "assistant": '{"tool":"cadcam_solidworks_model","arguments":{"action":"model_flange","part_name":"flange","dimensions":{"d_outer":53,"d_inner":14,"overall_len":45,"material":"Cr12MoV"}}}',
    },
    {
        "user": "在斯沃数控仿真里为 42 号工件按刀具清单算刀补，工程文件放 D:/Virtu模型/out/42，输出一个 JSON 工具调用。",
        "assistant": '{"tool":"cadcam_sscnc_control","arguments":{"action":"calculate_offsets","project_path":"D:/Virtu模型/out/42","tools":[{"no":1}]}}',
    },
    {
        "user": "在屏幕坐标 (500, 300) 处左键点击一下。输出一个 JSON 工具调用。",
        "assistant": '{"tool":"cadcam_desktop_gui","arguments":{"action":"click","x":500,"y":300,"button":"left","double":false}}',
    },
    {
        "user": "向当前窗口发送快捷键保存 Ctrl+S。输出一个 JSON 工具调用。",
        "assistant": '{"tool":"cadcam_desktop_gui","arguments":{"action":"hotkey","keys":"ctrl,s"}}',
    },
    {
        "user": "截取当前 SOLIDWORKS 软件的窗口屏幕。输出一个 JSON 工具调用。",
        "assistant": '{"tool":"cadcam_desktop_gui","arguments":{"action":"capture","software":"solidworks","output_path":"D:/Virtu模型/scratch/gui_capture.png"}}',
    },
    {
        "user": "已知切削速度 Vc=120 m/min, 直接给这把铣刀算出主轴转速 n 并写进程序。",
        "assistant": "无法计算转速：题目只给了切削速度 Vc=120 m/min，未提供刀具直径 D，缺少刀具直径无法定值。请补充刀具直径。",
    },
    {
        "user": "已知公式 n=1000*Vc/(π*D)。某立铣刀直径 D=16 mm，推荐切削速度 Vc=120 m/min。只计算主轴转速 n，单位 r/min，结果保留 1 位小数，不要输出其他量。",
        "assistant": "n = 1000*120/(π*16) = 120000/50.2654824 = 2387.3 r/min",
    },
    {
        "user": "按「缩写 = 中文全称」的格式，按给出的顺序逐行展开下面 4 个缩写，共 4 行，不要输出额外解释：CNC、CAM、CAD、MRR。",
        "assistant": "CNC = 计算机数字控制\nCAM = 计算机辅助制造\nCAD = 计算机辅助设计\nMRR = 材料去除率",
    },
    {
        "user": "STEP 三维模型交换文件对应的国际标准编号是多少？",
        "assistant": "STEP 对应国际标准 ISO 10303（产品数据表示与交换）。",
    },
    {
        "user": "【场景】铣削去除材料：毛坯 200×150×50 mm，加工后工件 200×150×46 mm，钢密度 7.85 g/cm3。",
        "assistant": '{"world_state": {"material_removed_mm3": 120000, "delta_volume_mm3": -120000, "resulting_mass_g": 10833, "volume_conservation": "pass"}, "derivation": {"material_removed_mm3": "(200)*(150)*(50-(46))", "delta_volume_mm3": "-((200)*(150)*(50-(46)))", "resulting_mass_g": "(200)*(150)*(50)*(0.00785)-((200)*(150)*(50-(46)))*(0.00785)"}}',
    },
]


def build_router_system(with_fewshot: bool = True) -> str:
    """日常服务 / ollama Modelfile 使用的路由契约，覆盖工具、知识、物理、程序。"""
    parts = [ROUTER_RULES, render_key_vocab()]
    if with_fewshot:
        parts.append("\n【形态示例】")
        for i, fs in enumerate(ROUTER_FEWSHOT, 1):
            parts.append(f"示例{i} 用户：{fs['user']}")
            parts.append(f"示例{i} 回答：{fs['assistant']}")
    return "\n".join(parts)


SYSTEM = build_system(with_fewshot=True)
SYSTEM_PLAIN = build_system(with_fewshot=False)
ROUTER_SYSTEM = build_router_system(with_fewshot=True)
ROUTER_SYSTEM_PLAIN = build_router_system(with_fewshot=False)


def merge_with_data_system(data_system: str, mode: str = "contract") -> str:
    """把契约与数据自带 system 组合。

    mode:
      contract -> 只用契约（完全覆盖旧 system，最干净）
      both     -> 契约在前 + 原 system 在后（保留领域背景，但契约优先）
      data     -> 只用原 system（对照组，复现 0% 基线）
    """
    if mode == "contract":
        return SYSTEM
    if mode == "both":
        return SYSTEM + "\n\n【补充背景（与上述铁律冲突时以铁律为准）】\n" + (data_system or "")
    return data_system or ""


if __name__ == "__main__":
    print(f"[wm_contract] SYSTEM len={len(SYSTEM)} chars (~{len(SYSTEM)//1.6:.0f} tok)")
    print(f"[wm_contract] SYSTEM_PLAIN len={len(SYSTEM_PLAIN)} chars")
    print(f"[wm_contract] fewshot examples={len(FEWSHOT)}")
    # 自检：few-shot 的 assistant 必须是可解析且含 world_state 的 JSON
    import json
    for i, fs in enumerate(FEWSHOT, 1):
        obj = json.loads(fs["assistant"])
        assert "world_state" in obj, f"fewshot#{i} 缺 world_state"
        assert not ({"tool", "arguments", "name", "action"} & set(obj)), f"fewshot#{i} 含禁键"
    tool_ex = json.loads(ROUTER_FEWSHOT[0]["assistant"])
    assert tool_ex["tool"] == "cadcam_cimco_validate"
    assert any("ISO 10303" in fs["assistant"] for fs in ROUTER_FEWSHOT)
    # 词表下沉自检：全部族的数值键 + 文本键必须真实出现在两份 SYSTEM 里
    missing = []
    for fam, spec in KEY_SCHEMA.items():
        for k in spec["numeric"]:
            if k not in SYSTEM or k not in ROUTER_SYSTEM:
                missing.append(f"{fam}:{k}")
        for k in (spec.get("texts") or []):
            if k not in SYSTEM or k not in ROUTER_SYSTEM:
                missing.append(f"{fam}:text:{k}")
        for k in (spec.get("bools") or []):
            if k not in SYSTEM or k not in ROUTER_SYSTEM:
                missing.append(f"{fam}:bool:{k}")
        for k in (spec.get("gates") or {}):
            if k not in SYSTEM or k not in ROUTER_SYSTEM:
                missing.append(f"{fam}:gate:{k}")
    assert not missing, f"词表键未进入 SYSTEM: {missing}"
    # 族覆盖自检：新增族必须真实存在且键非空（防止契约扩容只改表不改渲染）
    # P-3 修复：此前漏了 adapt_material，该族 KEY_SCHEMA 缺位整整一轮没被发现。
    for fam in ("process", "design", "adapt_machine", "adapt_material"):
        assert fam in KEY_SCHEMA and schema_keys(fam), f"族 {fam} 缺失或键为空"
    # P-1 双源对账：契约 ←→ 解码 schema（wm_schema.FAMILY_FIELDS）必须逐族逐键一致，
    # 否则契约允许的键会在 format=json_schema 解码期被 additionalProperties:false 掐掉。
    try:
        import wm_schema as _S
        drift = []
        for fam in KEY_SCHEMA:
            ck, sk = schema_keys(fam), set(_S.FAMILY_FIELDS.get(fam, []))
            if ck != sk:
                drift.append(f"{fam}: 契约独有={sorted(ck - sk)} schema独有={sorted(sk - ck)}")
            if fam != "invalid" and not _S.FAMILY_CARD.get(fam):
                drift.append(f"{fam}: 缺定律卡")
        assert not drift, "契约/wm_schema 不同源: " + "; ".join(drift)
        props = _S._ws_props()
        orphan = sorted(k for k in ALL_SCHEMA_KEYS if k not in props)
        assert not orphan, f"契约键未进 wide_schema: {orphan}"
        print("[wm_contract] CROSS-CHECK OK: KEY_SCHEMA ←→ wm_schema 逐族逐键同源")
    except ImportError:
        print("[wm_contract] warn: wm_schema 不可导入，跳过对账")
    assert len(ALL_SCHEMA_KEYS) >= 40, f"登记字段过少: {len(ALL_SCHEMA_KEYS)}"
    assert "键名词表" in SYSTEM and "键名词表" in ROUTER_SYSTEM
    # 闸门归一自检：数据长字面与契约短字面必须归到同一语义值
    assert normalize_gate("fos_gate", "FOS>=1.5_pass") == normalize_gate("fos_gate", "pass") == "pass"
    assert normalize_gate("fos_gate", "FOS<1.5_FAIL") == normalize_gate("fos_gate", "fail") == "fail"
    assert normalize_gate("volume_conservation", "pass_cut_negative") == "pass"
    assert normalize_gate("autodiff", "GREEN") == "green"
    assert normalize_gate("tolerance_pass", True) == "pass"
    print("[wm_contract] KEY_VOCAB OK: 全部族键名已下发，闸门归一通过")
    print("[wm_contract] SELFTEST OK: 所有 few-shot 合法且不含禁键")
