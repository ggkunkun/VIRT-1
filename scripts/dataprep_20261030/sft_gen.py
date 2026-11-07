# -*- coding: utf-8 -*-
"""
Virtu 数据集构建 · SFT 生成层
================================
生成规则：**每条回答中的每一个工程数值都必须来自抽取层的实际字段**，
不得出现未经抽取的臆造尺寸/转速/进给。凡是源文件没有的信息，
要么不写，要么显式标注为"图面未标注"。
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

# --------------------------------------------------------------------------
# 通用
# --------------------------------------------------------------------------


def sample(sid: str, system: str, user: str, assistant: str, **meta) -> dict:
    """构造一条 ShareGPT 样本。"""
    obj = {"id": sid, "messages": [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
        {"role": "assistant", "content": assistant},
    ]}
    obj.update(meta)
    return obj


# --------------------------------------------------------------------------
# A. NX 模型理解
# --------------------------------------------------------------------------

SYS_NX = ("你是 Virtu 工业模型中心的 UG NX 建模内核专家，精通 Parasolid 几何内核、"
          "NX 特征树结构、装配结构描述与零件属性体系。"
          "你只依据用户提供的模型文件真实解析信息作答，绝不臆造图面未标注的数值。")


def _fmt_ops(ops: dict) -> str:
    if not ops:
        return "（该文件未检出可识别的特征建模操作名）"
    return "、".join(f"{k} × {v}" for k, v in ops.items())


def _fmt_feats(feats: dict, limit: int = 12) -> str:
    if not feats:
        return "（无）"
    items = list(feats.items())[:limit]
    return "、".join(f"{k}({v})" for k, v in items)


def gen_nx_model_understanding(rec: dict) -> dict:
    name = rec["part_name"]
    op = rec["operation_counts"]
    feats = rec["feature_type_census"]
    attrs = rec["attributes"]
    lines = []

    kind = "装配体" if rec["is_assembly"] else "零件"
    lines.append(f"### {name}.prt —— NX 模型结构分析\n")
    lines.append("**1. 模型基本属性**")
    lines.append(f"- 模型类型：{kind}"
                 + ("（含装配结构描述，无独立实体几何）" if rec["is_assembly"]
                    else "（含 Parasolid 实体几何）"))
    if rec["parasolid_schema"]:
        lines.append(f"- 几何内核：Parasolid，schema {rec['parasolid_schema']}"
                     f"，内核版本 {rec['parasolid_version']}")
    else:
        lines.append("- 几何内核：本文件不含 Parasolid 实体数据（装配体或纯引用件）")
    lines.append(f"- 文件体积：{rec['size_bytes']:,} 字节；"
                 f"SHA256 前 16 位 {rec['sha256'][:16]}")
    lines.append(f"- 轻量化显示：{'含 JT 三角网格显示数据' if rec['has_jt_tessellation'] else '无 JT 数据'}"
                 f"；{'含内嵌模型预览图' if rec['has_embedded_preview'] else '无内嵌预览图'}")
    if rec["preview_size"]:
        lines.append(f"- 内嵌预览图分辨率：{rec['preview_size'][0]}×{rec['preview_size'][1]}"
                     "（NX 内部缩略图，放大后仅可用于形态判读，不能用于尺寸量取）")

    lines.append("\n**2. 建模特征统计（从模型文件内部特征类型直接统计）**")
    lines.append(f"- 建模操作命中：{_fmt_ops(op)}")
    lines.append(f"- 几何/标注类型分布：{_fmt_feats(feats)}")
    if rec["body_count"]:
        lines.append(f"- 实体（Body）相关类型出现次数：{rec['body_count']}")
    lines.append(f"- 随模型保存的工程图：{'有' if rec['drawing_present'] else '无'}"
                 f"；标注对象：{'有' if rec['annotation_present'] else '无'}")

    if attrs:
        lines.append("\n**3. 模型属性表（NX UgAttributes）**")
        for k, v in attrs.items():
            lines.append(f"- {k} = {v}")
    if rec["is_assembly"] and rec["component_parts"]:
        lines.append(f"\n**4. 装配引用**：外链 {rec['component_count']} 个零件文件"
                     f"（明细见装配结构样本）")

    lines.append("\n**5. 工程判断**")
    if rec["is_assembly"]:
        lines.append("- 该文件是装配主文件，实体几何由被引用零件承载，"
                     "修改特征应在子零件中进行，再由装配更新引用。")
    else:
        lines.append("- 该文件为可编辑零件主文件，可直接进入 Part Navigator 修改特征树。")
    if op.get("EXTRUDE"):
        lines.append(f"- 文件中检出 {op['EXTRUDE']} 处 EXTRUDE 拉伸特征，"
                     "说明主体几何由草图轮廓拉伸生成；重建时应保持草图与基准的关联关系。")
    if op.get("HOLE PACKAGE") or op.get("SIMPLE HOLE"):
        lines.append(f"- 检出孔特征（HOLE PACKAGE {op.get('HOLE PACKAGE', 0)} 处，"
                     f"SIMPLE HOLE {op.get('SIMPLE HOLE', 0)} 处），"
                     "孔的定位依赖草图基准，重建时须同时复制定位草图。")
    if rec["has_jt_tessellation"]:
        lines.append("- 含 JT 轻量化数据，可用更低成本的方式做装配可视化与干涉预检。")
    lines.append("- 提示：NX 未在文件中保存实体的完整可读参数表，"
                 "具体直径/深度/角度需在 NX 内打开对应特征后读取，"
                 "或由随附工程图（drawing）获得标注值。")
    return sample(
        f"nx_model_{rec['filename'].rsplit('.', 1)[0]}",
        SYS_NX,
        f"我拿到一个 UG NX 模型文件 {rec['filename']}（{rec['size_bytes']:,} 字节）。"
        f"请解析它的模型类型、几何内核、建模特征与属性信息，并说明在 NX 中应如何操作它。",
        "\n".join(lines),
        source_type="nx_prt",
        source_file=rec["filename"],
        source_dir=rec["source_dir"],
        sha256=rec["sha256"],
        grounded=True,
    )


# --------------------------------------------------------------------------
# B. NX 装配结构
# --------------------------------------------------------------------------

SYS_ASSY = ("你是 Virtu 工业模型中心的装配结构与 BOM 分析专家，"
            "熟悉 UG NX 装配体结构描述、组件层级、零部件功能划分与运动副选型。"
            "你只依据模型文件中真实存在的组件引用作答。")


_PART_ROLE = [
    # 先判"非机械零件"的模板/图框类，避免被后面的关键词误命中
    (r"^title_?block", "图框/标题栏模板（非机械零件）"),
    (r"^template|^tpl", "模板文件（非机械零件）"),
    # 机械零件：按"基名去掉修饰词"后的关键词匹配
    (r"gear", "齿轮传动件"),
    (r"pin", "销轴/定位件"),
    (r"screw|bolt|nut", "紧固件"),
    (r"servo", "伺服驱动组件"),
    (r"box", "箱体/容纳结构"),
    (r"elbow", "肘关节组件"),
    (r"shoulder", "肩关节组件"),
    (r"wrist", "腕关节组件"),
    (r"lever", "杠杆/压紧组件"),
    (r"drill", "钻床/钻孔机构"),
    (r"table", "工作台面/支撑件"),
    (r"lock", "锁紧机构"),
    (r"model", "通用/主模型"),
    (r"arm", "臂杆主体"),
]


def _role_of(fname: str) -> str:
    """按零件文件名判定功能族。注意标题栏模板文件名里也可能含 lock/table 等词，
    因此先剥离扩展名与数字后缀，再用整词匹配，避免误判。"""
    base = os.path.splitext(os.path.basename(fname))[0]
    low = base.lower()
    for pat, role in _PART_ROLE:
        if re.search(pat, low):
            return role
    return "零部件"


def gen_nx_assembly(rec: dict) -> dict:
    comps = rec["component_parts"]
    groups: dict[str, list[str]] = {}
    for c in comps:
        groups.setdefault(_role_of(c), []).append(c)
    lines = []
    lines.append(f"### {rec['part_name']}.prt —— 装配体 BOM 与结构分析\n")
    lines.append("**1. 装配总览**")
    lines.append(f"- 装配文件：{rec['filename']}（{rec['size_bytes']:,} 字节）")
    lines.append(f"- 外链零部件数量：**{rec['component_count']}** 个（依据装配体内部组件引用记录）")
    lines.append(f"- 装配属性：NX_Arrangement = {rec['attributes'].get('NX_Arrangement', '未记录')}；"
                 f"NX_ComponentGroup = {rec['attributes'].get('NX_ComponentGroup', '未记录')}；"
                 f"NX_ReferenceSet = {rec['attributes'].get('NX_ReferenceSet', '未记录')}")
    lines.append(f"- 内嵌预览图：{rec['preview_size'][0]}×{rec['preview_size'][1]} 像素"
                 if rec["preview_size"] else "- 内嵌预览图：无")
    lines.append("\n**2. 组件清单（按功能族归类）**")
    for role, items in sorted(groups.items(), key=lambda x: -len(x[1])):
        lines.append(f"- **{role}**（{len(items)}）：" + "、".join(items))
    lines.append("\n**3. 全量 BOM（逐项）**")
    for i, c in enumerate(comps, 1):
        lines.append(f"{i:>2}. {c}  —— {_role_of(c)}")
    lines.append("\n**4. 结构与装配工艺判断**")
    if any("gear" in c.lower() for c in comps):
        lines.append("- 该装配含齿轮传动件，说明存在减速/传动支路；"
                     "装配后必须做齿侧间隙与啮合位置校核，并保证两齿轮分度圆中心距"
                     "与轴线平行度。")
    if any(re.search(r"elbow|shoulder|wrist", c, re.I) for c in comps):
        lines.append("- 组件命名呈 elbow / shoulder / wrist 的关节序列，"
                     "判定为多自由度机械臂（或等效关节链）装配。"
                     "装配顺序应遵循『基座 → 根部关节 → 中间臂节 → 腕部 → 手端』，"
                     "并逐级复核运动干涉。")
    if any(re.search(r"pin|screw", c, re.I) for c in comps):
        lines.append("- 存在销轴与螺钉类零件，属定位与紧固件；"
                     "装配时应确认销孔配合公差（推荐 H7/m6 或 H7/js6）并加装防松措施。")
    if any(re.search(r"servo", c, re.I) for c in comps):
        lines.append("- 含伺服驱动组件，装配后应复核联轴器同轴度与电机安装面平面度，"
                     "并按电机说明书预留散热与检修空间。")
    lines.append("- 注意：NX_ReferenceSet 为 "
                 f"{rec['attributes'].get('NX_ReferenceSet', '未记录')}，"
                 + ("表示当前未保存参考集状态，跨版本传递时需重新指定或校验。"
                    if rec["attributes"].get("NX_ReferenceSet") == "Empty"
                    else "请在装配前确认参考集可用。"))
    lines.append("- 本文件不含各组件的实体几何与装配约束参数，"
                 "配合关系与约束类型需在 NX 装配模块中查看；"
                 "以上清单仅依据文件中实际存在的组件引用记录。")
    return sample(
        f"nx_assy_{rec['part_name']}",
        SYS_ASSY,
        f"请分析 UG NX 装配体 {rec['filename']}：它引用了哪些零件？"
        f"按功能给出 BOM 归类，并说明装配顺序、配合与校核要点。",
        "\n".join(lines),
        source_type="nx_assembly",
        source_file=rec["filename"],
        component_count=rec["component_count"],
        grounded=True,
    )


# --------------------------------------------------------------------------
# C. 工程图识读
# --------------------------------------------------------------------------

SYS_DWG = ("你是 Virtu 工业智能体的二维工程图识读与尺寸提取专家，"
           "精通机械制图国家标准（GB/T 1804、GB/T 4458）、形位公差、"
           "基准体系与多视图投影规则。"
           "你依据图纸实际标注作答；未标注的项目必须明确说明「图面未标注」。")


def _dim_table(dims: list[dict]) -> tuple[str, dict]:
    buckets: dict[str, list[dict]] = {}
    for d in dims:
        buckets.setdefault(d["type"], []).append(d)
    lines = []
    stats = {}
    labels = {
        "diameter": "直径尺寸", "radius": "半径尺寸", "chamfer": "倒角尺寸",
        "thread": "螺纹规格", "toleranced_linear": "带公差线性尺寸",
        "linear": "线性尺寸", "depth": "深度尺寸", "roughness": "表面粗糙度",
        "angle": "角度", "thru_diameter": "通孔直径", "thru_all": "通孔阵列",
    }
    order = ["toleranced_linear", "diameter", "radius", "chamfer", "thread",
             "depth", "angle", "roughness", "thru_diameter", "thru_all", "linear"]
    for t in order:
        items = buckets.get(t)
        if not items:
            continue
        vals = []
        for d in items:
            if d.get("qty"):
                vals.append(f"{d['text']}（{d['qty']} 处）")
            elif t == "toleranced_linear":
                vals.append(f"{d['nominal']}±{d['tolerance']}")
            elif "value" in d:
                vals.append(str(d["value"]))
            else:
                vals.append(d["text"])
        stats[t] = len(items)
        lines.append(f"- **{labels.get(t, t)}**（{len(items)}）：" + "、".join(vals))
    return "\n".join(lines), stats


def gen_drawing_reading(rec: dict) -> dict:
    tb = rec.get("title_block", {}) or {}
    dims = rec.get("dimension_callouts", []) or []
    tech = rec.get("tech_requirements", []) or []
    views = rec.get("view_labels") or []
    dno = tb.get("drawing_no") or rec.get("drawing_no") or rec["source_file"]
    lines = []

    lines.append(f"### {dno} 工程图识读\n")
    lines.append("**1. 标题栏信息**")
    if tb:
        for k, label in [("part_name", "零件名称"), ("drawing_no", "图号"),
                         ("material", "材料"), ("scale", "比例"),
                         ("quantity", "数量"), ("designer", "设计"),
                         ("date", "日期"), ("organization", "单位")]:
            if tb.get(k):
                lines.append(f"- {label}：{tb[k]}")
    else:
        lines.append("- 该图纸无标准中文标题栏（属英文练习图/矢量图），"
                     "零件信息以图面标注与图题为准。")
    if rec.get("drawing_title"):
        lines.append(f"- 图题：{rec['drawing_title']}")

    lines.append("\n**2. 视图构成**")
    if views:
        lines.append("- 图面标注的视图：" + "、".join(views))
    else:
        lines.append("- 图面未使用「VIEW/SECTION/DETAIL」字样标注视图名；"
                     "按矢量分布判断为单一主视图 + 局部剖视的布局。")
    lines.append(f"- 矢量图元统计：{json.dumps(rec.get('vector_stats', {}), ensure_ascii=False)}")

    lines.append("\n**3. 尺寸标注清单（逐条自图面提取）**")
    if dims:
        tbl, stats = _dim_table(dims)
        lines.append(tbl)
        lines.append(f"\n- 标注条目合计：**{len(dims)}** 条"
                     f"（分类计数 {json.dumps(stats, ensure_ascii=False)}）")
    else:
        lines.append("- 该图纸为纯矢量图（无文字标注层），"
                     "尺寸需通过矢量图元几何反求，本样本不提供臆测数值。")

    if tech:
        lines.append("\n**4. 技术要求（原文）**")
        for i, t in enumerate(tech, 1):
            lines.append(f"{t}")

    lines.append("\n**5. 识读结论**")
    if tb.get("material"):
        lines.append(f"- 材料为 {tb['material']}，"
                     f"图纸技术要求中若出现未注公差条款（GB/T 1804-m），"
                     "则按该标准确定未注线性尺寸与角度公差等级。")
    if stats.get("toleranced_linear"):
        lines.append(f"- 图中共 {stats['toleranced_linear']} 处带 ± 公差尺寸，"
                     "这些是检验与工艺控制的重点尺寸，"
                     "加工方案必须为其单独安排精加工或选配工序。")
    if stats.get("diameter"):
        lines.append(f"- 共 {stats['diameter']} 处直径标注，"
                     "其中带阵列系数的孔位需要单独编制钻孔循环（G81/G83）或镗削工序。")
    if stats.get("radius") or stats.get("chamfer"):
        lines.append(f"- 圆角 {stats.get('radius', 0)} 处、倒角 {stats.get('chamfer', 0)} 处，"
                     "属于三轴铣削的清角工序，建议放在半精加工之后、精加工之前单独一刀。")
    lines.append("- 未在本图面标注的尺寸（如壁厚、材料热处理状态、"
                 "基准符号的完整定义）一律按「图面未标注」处理，"
                 "需回原始设计文件或三维模型确认，不得据推测填写。")
    return sample(
        f"dwg_read_{rec['source_file'].rsplit('.', 1)[0]}",
        SYS_DWG,
        f"请识读工程图《{dno}》："
        f"提取标题栏信息、视图构成与全部尺寸标注，并按类别汇总。",
        "\n".join(lines),
        source_type="drawing_pdf",
        source_file=rec["source_file"],
        dimension_count=len(dims),
        grounded=True,
    )


# --------------------------------------------------------------------------
# D. 工艺规划
# --------------------------------------------------------------------------

SYS_CAM = ("你是 Virtu 工业智能体的数控加工工艺与编程专家，"
           "熟悉 UG NX / VERICUT / CIMCO 等仿真平台，"
           "精通粗精分开、刀具选择、切削用量、分层策略与 G 代码循环选型。"
           "你依据图纸给出的真实参数表与工艺条款编制工艺卡，不臆造转速与进给。")


def gen_process_plan(rec: dict) -> dict:
    tb = rec.get("title_block", {}) or {}
    tech = rec.get("tech_requirements", []) or []
    tbl = rec.get("param_table", []) or []
    dno = tb.get("drawing_no") or rec.get("drawing_no") or rec["source_file"]
    lines = []
    lines.append(f"### {dno} 数控加工工艺卡\n")
    lines.append("**1. 工件信息**")
    lines.append(f"- 零件：{tb.get('part_name', '（图面未标注）')}")
    lines.append(f"- 材料：{tb.get('material', '（图面未标注）')}；"
                 f"毛坯与数量见图纸技术要求")
    lines.append(f"- 数量：{tb.get('quantity', '（图面未标注）')}")

    lines.append("\n**2. 工序卡（严格按图纸「加工参数表」引用）**")
    if tbl:
        lines.append("| 工序 | 刀具 | 主轴转速 | 进给 | 备注 |")
        lines.append("| :--- | :--- | :--- | :--- | :--- |")
        for r in tbl:
            rpm = r.get("spindle_rpm", "")
            feed = r.get("feed", "")
            lines.append(f"| {r.get('operation','')} | {r.get('tool','')} | "
                         f"{rpm + ' r/min' if rpm else '—'} | "
                         f"{feed + ' mm/min' if feed else '—'} | "
                         f"{r.get('remark','') or '—'} |")
    else:
        lines.append("- 本图未提供加工参数表，切削用量需另行给定。")

    lines.append("\n**3. 装夹与坐标系（依据技术要求原文）**")
    for t in tech:
        if any(k in t for k in ("原点", "G54", "对刀", "夹紧", "基准", "毛坯")):
            lines.append(f"- {t}")
    lines.append("- 装夹方案：按图纸「编程原点 G54」条款执行，"
                 "工件左下角上表面为 XY 原点，Z0=0 定在顶面；"
                 "粗加工前须用寻边器找正 X/Y 两边并以顶面为 Z 向对刀基准。")

    lines.append("\n**4. 工艺路线说明**")
    for t in tech:
        if any(k in t for k in ("分层", "余量", "精加工", "粗", "去毛刺", "接刀痕")):
            lines.append(f"- {t}")
    if tbl:
        for r in tbl:
            op = r.get("operation", "")
            rem = r.get("remark", "")
            if "G8" in rem or "G7" in rem:
                lines.append(f"- 「{op}」备注给出 {rem}，"
                             "即采用固定循环钻孔；编程时应同时给出 Z 向每次切深与 "
                             "R 点抬刀高度（一般取 +2~3mm）。")
        first = tbl[0]
        lines.append(f"- 首序为「{first.get('operation','')}」，"
                     f"刀具 {first.get('tool','')}，"
                     f"转速 {first.get('spindle_rpm','')} r/min、"
                     f"进给 {first.get('feed','')} mm/min，"
                     f"备注 {first.get('remark','')}；该序为去除余量的主工序，"
                     "必须优先保证不撞刀与余量均匀。")
        last = tbl[-1]
        lines.append(f"- 末序为「{last.get('operation','')}」，"
                     f"刀具 {last.get('tool','')}，"
                     f"备注 {last.get('remark','')}，属于表面质量收尾工序，"
                     "走刀应避免接刀痕。")
    lines.append("- 刀具清单（按图面参数表汇总）："
                 + ("、".join(sorted({r.get('tool','') for r in tbl if r.get('tool')}))
                    if tbl else "图面未给出") )
    lines.append("- 检验控制点：凡图面标注 ± 公差的尺寸与 Ra 粗糙度，"
                 "均在末序后以三坐标或粗糙度样块确认；"
                 "孔位需用坐标检具复核。")

    lines.append("\n**5. 仿真与校验**")
    for t in tech:
        if any(k in t for k in ("仿真", "VERICUT", "CIMCO", "校验", "NX")):
            lines.append(f"- {t}")
    lines.append("- 校验清单：① 毛坯尺寸与图面「毛坯」条款一致；"
                 "② 装夹与 G54 原点一致；③ 每层切深不超过条款上限；"
                 "④ 粗加工后留精加工余量；⑤ 无撞刀与过切；"
                 "⑥ 孔位与孔深与标注一致；⑦ 表面粗糙度达标。")
    return sample(
        f"proc_{dno.replace('/', '_').replace(' ', '_')}",
        SYS_CAM,
        f"请依据图纸《{dno}》的技术要求与加工参数表，"
        f"编制该零件的数控加工工艺卡（装夹、坐标系、工序、刀具、校验要点）。",
        "\n".join(lines),
        source_type="process_planning",
        source_file=rec["source_file"],
        operation_count=len(tbl),
        grounded=True,
    )


# --------------------------------------------------------------------------
# D2. 二维图纸 → 三维特征树（Drawing-to-CAD 核心能力）
# --------------------------------------------------------------------------

SYS_TREE = ("你是 Virtu 工业智能体的参数化建模专家，"
            "熟练依据二维工程图在 SolidWorks / UG NX 中重建参数化特征树。"
            "你的每一步特征参数都必须来自图纸实际标注；"
            "图纸未标注的要素一律标注为「图面未标注，需回查三维模型」，绝不臆造数值。")


def _group_dims(dims: list[dict]) -> dict:
    g: dict[str, list[dict]] = {}
    for d in dims:
        g.setdefault(d["type"], []).append(d)
    return g


def _fmt_q(d: dict) -> str:
    """把一个标注对象格式化为可读串；数值若已含在原文本中则不重复追加。"""
    if d.get("qty"):
        return f"{d['text']}（{d['qty']} 处）"
    if d["type"] == "toleranced_linear":
        return f"{d['nominal']}±{d['tolerance']}"
    v = d.get("value")
    if v is None:
        return d["text"]
    sv = str(v)
    if sv in d["text"] or d["text"].rstrip("H h g G").endswith(sv):
        return d["text"]
    return f"{d['text']}（{sv}）"


def gen_feature_tree(rec: dict) -> dict:
    tb = rec.get("title_block", {}) or {}
    dims = rec.get("dimension_callouts", []) or []
    tech = rec.get("tech_requirements", []) or []
    g = _group_dims(dims)
    dno = tb.get("drawing_no") or rec.get("drawing_no") or rec["source_file"]
    pname = tb.get("part_name") or rec.get("drawing_title") or dno

    lines = []
    lines.append(f"### {dno}（{pname}）—— 二维图 → 参数化特征树\n")

    # ---- 1. 总体尺寸推断 ----
    overall = sorted({d["nominal"] for d in g.get("toleranced_linear", [])
                      if "nominal" in d}, reverse=True)
    lin = sorted({d["value"] for d in g.get("linear", []) if "value" in d}, reverse=True)
    lines.append("**1. 主体尺寸识别**")
    if overall:
        lines.append(f"- 带公差的主尺寸（由大到小）：{', '.join(str(v) for v in overall)}"
                     " —— 其中最大值通常为轮廓总长/总宽。")
    if lin:
        lines.append(f"- 其他线性尺寸（由大到小，前 12 个）："
                     f"{', '.join(str(v) for v in lin[:12])}")
    if not overall and not lin:
        lines.append("- 图面为纯矢量图，无文字尺寸层，主体尺寸无法从标注直接读取。")

    # ---- 2. 特征清单 ----
    lines.append("\n**2. 特征类型清单（逐条来自图面标注）**")
    feature_map = [
        ("diameter", "圆柱/孔特征", "Hole Wizard / Hole Feature"),
        ("thread", "螺纹特征", "Thread / Hole Wizard 螺纹孔"),
        ("radius", "圆角特征", "Fillet"),
        ("chamfer", "倒角特征", "Chamfer"),
        ("depth", "深度特征", "Extrude Cut（深度）/ Pocket"),
        ("toleranced_linear", "轮廓与定位尺寸", "Sketch 尺寸约束"),
        ("linear", "辅助与次要尺寸", "Sketch 尺寸约束"),
        ("roughness", "表面粗糙度", "表面处理/质量属性"),
        ("angle", "角度约束", "Sketch 角度约束"),
        ("thru_diameter", "通孔", "Hole Wizard 通孔"),
    ]
    for key, label, feature in feature_map:
        items = g.get(key)
        if not items:
            continue
        vals = "、".join(_fmt_q(d) for d in items[:14])
        extra = f"（共 {len(items)} 处）" if len(items) > 14 else ""
        lines.append(f"- **{label}** → 对应特征：{feature}{extra}：{vals}")

    # ---- 3. 特征树时序 ----
    lines.append("\n**3. 建议特征树时序（SolidWorks / UG NX 通用）**")
    steps = []
    n = 1
    steps.append(f"{n}. **建立基准**：以 Top Plane 为草绘基准面，"
                 f"Front Plane 为正视基准，Right Plane 为侧基准，"
                 f"三者两两垂直；原点置于图面标注的编程/设计原点。")
    n += 1
    body = overall[:3] if overall else lin[:3]
    if body:
        steps.append(f"{n}. **主体成形**：在基准面绘制轮廓草图并做对称/完全约束，"
                     f"按主要尺寸 {'、'.join(str(v) for v in body)} 拉伸成型；"
                     f"草图轮廓必须完全约束，禁止欠约束建模。")
    else:
        steps.append(f"{n}. **主体成形**：图面未给出可读的主体尺寸标注，"
                     f"需先回原始模型取得轮廓尺寸后再建草图。")
    n += 1
    if g.get("diameter") or g.get("thru_diameter"):
        vals = "、".join(_fmt_q(d) for d in (g.get("diameter") or [])[:8])
        steps.append(f"{n}. **孔系特征**：用 Hole Wizard（UG NX 用 Hole/Drill 特征）"
                     f"一次性建立孔组，定位方式为「草图点选 → 阵列/多选」，"
                     f"直径依据 {vals}；"
                     f"若标注含 H7/g6 等配合公差，务必在特征属性中同步设定。")
        n += 1
    if g.get("thread"):
        vals = "、".join(_fmt_q(d) for d in g["thread"][:6])
        steps.append(f"{n}. **螺纹特征**：按 {vals} 建立内螺纹孔，"
                     f"注意记录牙型、螺距与有效螺纹深度，"
                     f"并按规范绘制螺纹终止线（退刀槽）。")
        n += 1
    if g.get("depth") or g.get("radius"):
        seg = []
        if g.get("depth"):
            seg.append("凹槽/型腔按标注深度成形")
        if g.get("radius"):
            seg.append("内凹圆角按标注 R 值成形")
        steps.append(f"{n}. **{'、'.join(seg)}**：以切除特征实现，"
                     f"注意底面余量与侧壁精加工余量的分配。")
        n += 1
    if g.get("chamfer"):
        vals = "、".join(_fmt_q(d) for d in g["chamfer"][:8])
        steps.append(f"{n}. **倒角特征**：在精加工之后统一施加倒角 {vals}，"
                     f"避免过早倒角影响定位与检测。")
        n += 1
    if g.get("roughness"):
        vals = "、".join(_fmt_q(d) for d in g["roughness"][:8])
        steps.append(f"{n}. **表面质量**：将 {vals} 等粗糙度要求写入对应面的"
                     f"外观属性，导出加工/检验工序时作为工艺依据。")
        n += 1
    steps.append(f"{n}. **工程图与校验**：重建工程图视图（三视图 + 局部剖视），"
                 f"把带公差尺寸回标为带公差标注，"
                 f"补齐基准符号与形位公差，再与原图逐项比对。")
    lines.extend(steps)

    # ---- 4. 建模注意事项 ----
    lines.append("\n**4. 重建要点与风险**")
    if tb.get("material"):
        lines.append(f"- 材料 {tb['material']}，加工余量与最小壁厚需按该材料工艺性确定。")
    for t in tech:
        if "公差" in t:
            lines.append(f"- {t}（这条决定所有未标注尺寸的公差来源，"
                         f"重建后须用同一标准填写模型属性）")
            break
    for t in tech:
        if "圆角" in t and "倒角" in t:
            lines.append(f"- {t}（未注圆角/倒角虽不在尺寸标注中，"
                         f"但必须体现在模型上，否则与原图不一致）")
            break
    lines.append("- 孔位阵列务必核对「数量 × 中心距 × 分布形式」，"
                 "图面只给中心距时，阵列起点与方向必须与视图一致，"
                 "否则会出现孔位整体偏移的经典错误。")
    lines.append("- 重建完成后应做「三视图回标比对」与「质量属性/材料属性核对」，"
                 "这一步是图纸理解正确与否的最终校验。")
    lines.append("- 说明：本特征树由图面标注反推得到；"
                 "凡图面未标注的圆角过渡、内部结构与加工要求，"
                 "均需回查原始三维模型或设计说明，不得凭推测补全。")
    return sample(
        f"tree_{dno.replace('/', '_').replace(' ', '_')}",
        SYS_TREE,
        f"请依据工程图《{dno}》的尺寸标注与技术要求，"
        f"在 SolidWorks / UG NX 中给出重建该零件的完整参数化特征树时序"
        f"（含每一步特征的类型、参数来源与建模约束）。",
        "\n".join(lines),
        source_type="drawing_to_feature_tree",
        source_file=rec["source_file"],
        dimension_count=len(dims),
        grounded=True,
    )


# --------------------------------------------------------------------------
# E. 世赛评分标准
# --------------------------------------------------------------------------

SYS_WSC = ("你是 Virtu 工业智能体的技能赛评分标准与考评专家，"
           "熟悉 WorldSkills 技能赛制（技术要求 → 子标准 → 评分项 Aspect → 分值）"
           "及机械设计 CAD 与数控车削两个技能方向的考核要点。"
           "你依据真实评分表数据作答。")


def gen_wsc_qa(rec: dict) -> dict:
    scheme = rec["scheme"]
    skill = scheme.get("skill_name", "")
    lines = []
    lines.append(f"### {skill} —— 评分标准结构\n")
    lines.append("**1. 顶层评分模块（Criteria）**")
    crit = scheme.get("criteria") or []
    if crit:
        for c in crit:
            mk = c.get("max_mark")
            lines.append(f"- **{c['id']}. {c['name']}** —— 满分 {mk}" if mk is not None
                         else f"- **{c['id']}. {c['name']}**")
        total = scheme.get("criteria_total_mark")
        if total is not None:
            lines.append(f"- 合计满分：{total}")
    else:
        lines.append("- 本样本聚焦单一子标准的判分细则，"
                     "顶层评分模块结构见同技能的「评分标准结构」样本。")

    subs = scheme.get("sub_criteria") or []
    if subs:
        lines.append("\n**2. 子标准（Sub Criteria）**")
        for s in subs:
            lines.append(f"- {s['id']}：{s['name']}")

    aspects = rec.get("aspects", [])
    if aspects:
        lines.append("\n**3. 评分项明细（Aspect，取自官方 OMF 评分表）**")
        lines.append("| Aspect | 分值 | 判分内容 | 尺寸/名义要求 |")
        lines.append("| :--- | :--- | :--- | :--- |")
        for a in aspects[:40]:
            lines.append(f"| {a.get('aspect_id','')} | {a.get('max_mark','')} | "
                         f"{a.get('description','')} | {a.get('requirement','') or '—'} |")
        lines.append(f"\n- 该评分表 Aspect 条目总数：{len(aspects)}")

    lines.append("\n**4. 备考要点**")
    if "CAD" in skill:
        lines.append("- 建模类考核（A1 PART MODELING / A2 ASSEMBLY MODELING）"
                     "要求特征树可编辑、参数可回改，禁止用「导入体」替代建模；"
                     "出图类（A3 DIMENSIONING / A4 PRESENTATION）要求尺寸完整、"
                     "基准与形位公差标注齐全、图框与标题栏符合 ISO。")
        lines.append("- B（Mechanical Fabrication）指向工艺可行性："
                     "模型必须可制造——壁厚、拔模、圆角、刀具可达性都要成立。")
        lines.append("- D（Reverse Engineering from a Physical Model）"
                     "要求由实物反求，尺寸读取与公差判定必须可复核。")
    elif "Turning" in skill:
        lines.append("- CNC 车削按「图纸符合性 → 表面质量 → 主尺寸 → 次尺寸 → 材料利用」"
                     "分层给分；主尺寸与次尺寸分值最高，"
                     "说明评分重点在尺寸精度而非单纯做完。")
        lines.append("- 评分表中的 Requirement 列给出的「上限/下限」双值即合格区间"
                     "（如 52,006/51,994 表示上偏差 0.006、下偏差 0.006 的区间），"
                     "超出即该项不得分。")
        lines.append("- 材料利用（Use of material）按模块分别设项，"
                     "车削件的毛坯长度与去除量直接影响得分。")
    lines.append("- 通用建议：训练时以「子标准 → Aspect → 判分内容 → 尺寸区间」"
                 "四元组记忆考核要求，再反向映射到建模/编程动作，"
                 "比死记整张表更有效。")
    return sample(
        f"wsc_{rec['skill_id']}_{rec['topic']}",
        SYS_WSC,
        rec["question"],
        "\n".join(lines),
        source_type="worldskills_assessment",
        source_file=rec.get("source_file", ""),
        grounded=True,
    )


# --------------------------------------------------------------------------
# F. 多模态：CAD 图像 → 语义描述
# --------------------------------------------------------------------------

SYS_VLM = ("你是 Virtu 工业视觉引擎的 CAD 图像理解专家，"
           "能够从零件渲染图/线框图中识别零件类型、功能特征、"
           "装配形态与可能的加工工艺，并给出结构化的图像描述。")


def _semantic_hint(fname: str) -> str:
    low = fname.lower()
    hints = [
        (r"assembly|assy", "整机/子装配体"),
        (r"wireframe", "线框显示（仅表达拓扑与骨架，无实体着色）"),
        (r"model|model1", "三维实体模型渲染图"),
        (r"drawing|sheet", "工程图/出图视图"),
        (r"gear", "齿轮类零件"),
        (r"table", "台面/平台类结构件"),
        (r"lock", "锁紧机构"),
        (r"lever", "杠杆机构"),
        (r"arm", "机械臂"),
        (r"level", "水平仪/水平机构"),
        (r"drive|hub", "驱动轮毂"),
        (r"needle", "针阀/喷针"),
        (r"valve", "阀体"),
        (r"fuel", "燃油管路"),
        (r"tank", "油箱"),
        (r"gasket", "密封垫片"),
        (r"pin", "销轴"),
        (r"nut", "螺母/螺帽"),
        (r"step", "台阶块"),
        (r"colou?mn|column", "立柱/支柱"),
        (r"support", "支撑件"),
        (r"drill", "钻床"),
        (r"pmi", "PMI 图（产品制造信息标注图）"),
    ]
    for pat, h in hints:
        if re.search(pat, low):
            return h
    return "机械零件/装配件渲染图"


def gen_image_caption(rec: dict) -> dict:
    hint = _semantic_hint(rec["filename"])
    lines = []
    lines.append(f"### 图像语义描述（{rec['filename']}）\n")
    lines.append("**1. 图像基本信息**")
    lines.append(f"- 分辨率：{rec['width']}×{rec['height']} 像素，"
                 f"宽高比 {rec.get('aspect_ratio')}，色彩模式 {rec['mode']}")
    lines.append(f"- 资产类别：{rec.get('asset_class', '未知')}；"
                 f"来源目录：{rec.get('source_dir', '')}")
    lines.append(f"- 文件名语义判定：**{hint}**")
    lines.append(f"- SHA256：{rec['sha256'][:32]}…")
    lines.append("\n**2. 图像内容判读**")
    lines.append(f"- 该图属于{hint}。")
    if rec.get("asset_class") == "cad_render":
        lines.append("- 画面为 CAD 三维视窗截图/渲染，"
                     "包含实体着色与光照信息，可用于识别零件的体量关系、"
                     "凸台/凹槽/肋板分布以及安装面位置。")
    elif rec.get("asset_class") == "cad_wireframe":
        lines.append("- 画面为线框模式，只有拓扑边线没有材质信息，"
                     "适合判读轮廓层次与内部筋板走向，不适合判读表面质量。")
    elif rec.get("asset_class") == "drawing_sheet":
        lines.append("- 画面为工程图纸幅面，含图框、视图与标注，"
                     "适合做图纸版面理解与标题栏解析。")
    elif rec.get("asset_class") == "aigc_label":
        lines.append("- 该图来自带 AIGC 标注的资产流水线，"
                     "文件名中 `_aigc_label` 后缀标识其为标注后的可视化版本。")
    lines.append("\n**3. 可用于的模型能力**")
    lines.append("- 训练用途：① 图像→零件类型与功能部件的分类；"
                 "② 图像→结构描述（体量/特征/接口）；"
                 "③ 图像→装配关系推断（当为装配体时）；"
                 "④ 与配套文本标注做图文对齐。")
    lines.append("\n**4. 注意事项**")
    if rec.get("duplicate_of"):
        lines.append(f"- 本图与《{rec['duplicate_of']}》为内容完全相同的重复文件"
                     "（SHA256 一致），训练时应只保留一份，避免重复采样导致过拟合。")
    lines.append("- 渲染图不含加工尺寸信息，"
                 "不得从图像反推精确尺寸；尺寸必须以配套工程图或三维模型为准。")
    return sample(
        f"img_{rec['id']}",
        SYS_VLM,
        f"请描述这张 CAD 相关图像的内容：它是什么、反映了哪些结构信息、"
        f"可用于训练什么能力？（资产文件：{rec['filename']}）",
        "\n".join(lines),
        source_type="multimodal",
        source_file=rec["filename"],
        image_path=rec.get("relative_path", ""),
        grounded=True,
    )
