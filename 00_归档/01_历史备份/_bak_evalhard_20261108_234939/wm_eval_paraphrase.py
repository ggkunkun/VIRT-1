#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""评测题面改写层 —— 让「模板级去污」后的评测真正测泛化，而不是测背诵。

背景（2026-11-08，承接 wm_eval_purity.py 的发现）：
  GEN_BY_FAMILY 直接复用训练语料构建器（build_worldmodel_sft / build_worldmodel_v2），
  题面只有一套措辞，数字一脱敏就 100% 与训练集同模板 —— 评测等于开卷考。
  只改数字不改句式时，模型学的是「记住模板 → 填数字」，指标再高也证明不了泛化。

本模块的做法：**不动训练侧任何一行代码**（data/sft 是冻结证据），只在评测侧
把同一道题换成另一种工程口吻重新表述：
  - 数值一律从 rec["scenario"]["inputs"] / expected world_state 取，不解析原题面，
    因此改写不会篡改物理量（同一道题、同一组输入、同一个期望输出）；
  - 每族提供 3 种句式（工序卡 / 问答 / 审计单），轮转使用，模板签名随文字变化；
  - 严格保留下游场景推断（anti_hallucination_guard.infer_scenario_from_prompt）
    所依赖的关键标签（DOC= / φ / 切削速度 vc= / 屈服强度 / 安全平面 / 半公差[…] /
    特征体积 / 质量属性 / 现场物性表 …），否则改写会把「题面看不懂」当成
    「泛化失败」，把推断器的脆性误算到模型头上。
    selftest() 对 12 族逐条断言改写后 infer 仍归到本族，命中率必须 100%。

用法：
  from wm_eval_paraphrase import wrap
  gen2 = wrap(gen, fam)          # 生成器包一层改写
  python scripts/wm_eval_paraphrase.py            # 只跑改写×推断一致性自测
  python scripts/wm_eval_paraphrase.py --samples 300 --verbose
"""
from __future__ import annotations

import argparse
import json
import random
import re
from typing import Any, Callable, Dict, Optional

ENABLED = True          # eval_worldmodel 的 --no-paraphrase 会把这里置 False
STYLE_COUNT = 3         # 每族句式数量


# ---------------------------------------------------------------------------
# 小工具
# ---------------------------------------------------------------------------
def _n(x, sig: int = 10) -> str:
    """数值转题面文本：整数不带小数点，其余按有效位打印，避免 0.30000000000000004。"""
    if isinstance(x, bool):
        return str(x)
    try:
        v = float(x)
    except Exception:
        return str(x)
    if v == int(v) and abs(v) < 1e15:
        return str(int(v))
    return "%.*g" % (sig, v)


def _g(d: Any, k: str, default=None):
    return d.get(k, default) if isinstance(d, dict) else default


def _inputs(rec: Dict[str, Any]) -> Dict[str, Any]:
    return (rec.get("scenario") or {}).get("inputs") or {}


def _expected(rec: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return json.loads(rec["messages"][2]["content"])
    except Exception:
        return {}


def _ws(rec: Dict[str, Any]) -> Dict[str, Any]:
    return _g(_expected(rec), "world_state") or {}


def _orig_prompt(rec: Dict[str, Any]) -> str:
    try:
        return rec["messages"][1]["content"]
    except Exception:
        return ""


def _mat_by_rho(rho) -> Optional[str]:
    """材料库反查牌号（生成器的 rho 直接取自 MATERIALS，可精确反查）。"""
    try:
        import build_worldmodel_sft as W

        for name, spec in W.MATERIALS.items():
            if rho is not None and abs(float(spec["rho"]) - float(rho)) < 1e-12:
                return name
    except Exception:
        pass
    return None


def _mat_from_text(t: str) -> Optional[str]:
    try:
        import anti_hallucination_guard as G

        for pat, name in G._MAT_ALIAS:
            if re.search(pat, t):
                return name
    except Exception:
        pass
    return None


def _rho_g(rho) -> str:
    """rho 单位 g/mm3 → g/cm3 文本。"""
    try:
        return "%.2f" % (float(rho) * 1000.0)
    except Exception:
        return "7.85"


# ---------------------------------------------------------------------------
# 各族的句式变体（每族 3 种；返回 None 表示本族不参与改写）
# ---------------------------------------------------------------------------
def _rw_removal(rec, rng):
    inp = _inputs(rec)
    doc, woc = inp.get("doc"), inp.get("woc")
    vf, L = inp.get("vf"), inp.get("L")
    rho, stock = inp.get("rho"), inp.get("stock_vol")
    if None in (doc, woc, vf, L, rho, stock):
        return None
    mat = _mat_by_rho(rho) or _mat_from_text(_orig_prompt(rec)) or "工件材料"
    rg = _rho_g(rho)
    v = rng.randrange(STYLE_COUNT)
    if v == 0:      # 工序卡
        return (f"铣削工步工序卡：工件材料 {mat}，毛坯体积 {_n(stock)} mm3，"
                f"密度 {rg} g/cm3。本工步切削深度 DOC={_n(doc)} mm、"
                f"切削宽度 WOC={_n(woc)} mm、进给速度 vf={_n(vf)} mm/min、"
                f"刀路长度 L={_n(L)} mm。请回填材料去除率 MRR、去除体积、"
                f"去除质量与剩余质量。")
    if v == 1:      # 现场采集 + 提问式
        return (f"现场采集到一条端铣单刀路参数：DOC={_n(doc)} mm、"
                f"WOC={_n(woc)} mm、进给速度 vf={_n(vf)} mm/min、刀路长度 L={_n(L)} mm；"
                f"毛坯体积 {_n(stock)} mm3，材料为 {mat}，密度 {rg} g/cm3。"
                f"问：这一刀走完，切除的材料体积是多少、切除质量是多少？"
                f"材料去除率多大？切削后还剩多少料？")
    return (f"请按给定铣削参数做物料平衡推算：DOC={_n(doc)} mm、WOC={_n(woc)} mm、"
            f"vf={_n(vf)} mm/min、L={_n(L)} mm。工件为 {mat}，密度 {rg} g/cm3，"
            f"毛坯体积 {_n(stock)} mm3。要求逐项回答：① 材料去除率 MRR；② 去除体积；"
            f"③ 去除质量；④ 余下质量。")


def _rw_roughness(rec, rng):
    inp = _inputs(rec)
    f, r_eps = inp.get("f"), inp.get("r_eps")
    if None in (f, r_eps):
        return None
    v = rng.randrange(STYLE_COUNT)
    if v == 0:
        return (f"精车外圆工序：每转进给 f={_n(f)} mm/rev，"
                f"刀尖圆弧半径 r_ε={_n(r_eps)} mm。"
                f"请推算理论表面粗糙度 Ra（μm），并给出对应的粗糙度等级判定。")
    if v == 1:
        return (f"某车削工步的切削条件为每转进给 f={_n(f)} mm/rev、"
                f"刀尖圆弧半径 {_n(r_eps)} mm。"
                f"问：理论 Ra 是多少微米？该表面属于粗加工、半精还是精加工档？")
    return (f"按车削粗糙度理论式估算表面质量：给定 f={_n(f)} mm/rev 与 "
            f"刀尖圆弧半径 r_ε={_n(r_eps)} mm，请给出 Ra(μm) 数值与粗糙度等级。")


def _rw_fea_fos(rec, rng):
    inp = _inputs(rec)
    Sy, sigma = inp.get("Sy"), inp.get("sigma")
    if None in (Sy, sigma):
        return None
    mat = _g(_ws(rec), "material") or "金属"
    v = rng.randrange(STYLE_COUNT)
    if v == 0:
        return (f"结构强度校核：{mat} 构件的屈服强度 Sy={_n(Sy)} MPa，"
                f"FEA 计算峰值 von Mises 应力 σ_vm={_n(sigma)} MPa。"
                f"请给出安全系数，并判定 FOS≥1.5 是否满足。")
    if v == 1:
        return (f"有限元结果复核：材料 {mat}，屈服强度 {_n(Sy)} MPa，"
                f"峰值 von Mises 应力 {_n(sigma)} MPa。"
                f"请给出 FOS 数值，并说明能否通过 1.5 的安全门限。")
    return (f"{mat} 零件承受 FEA 峰值 von Mises 应力 σ_vm={_n(sigma)} MPa，"
            f"其屈服强度为 {_n(Sy)} MPa。安全裕度够不够？"
            f"请算出安全系数并给出通过/不通过的结论。")


def _rw_collision(rec, rng):
    inp = _inputs(rec)
    z_safe, z_min, z_top = inp.get("z_safe"), inp.get("z_min_rapid"), inp.get("stock_top")
    if None in (z_safe, z_min, z_top):
        return None
    v = rng.randrange(STYLE_COUNT)
    if v == 0:
        return (f"数控程序过切风险检查：程序设定安全平面 Z={_n(z_safe)} mm，"
                f"某段 G00 快速移动段的最低 Z={_n(z_min)} mm，"
                f"毛坯顶面 Z={_n(z_top)} mm。请判定碰撞/过切风险，并给出 "
                f"VERICUT Auto-Diff 颜色（红=过切，黄=风险，绿=合格）。")
    if v == 1:
        return (f"刀具轨迹安全审计：毛坯顶面高度 Z={_n(z_top)} mm，"
                f"安全平面 Z={_n(z_safe)} mm，快移段最低点 Z={_n(z_min)} mm。"
                f"这段轨迹会不会撞刀或过切？Auto-Diff 会标成什么颜色？")
    return (f"给定毛坯顶面 Z={_n(z_top)} mm 与安全平面 Z={_n(z_safe)} mm，"
            f"一段 G00 快速移动的最低 Z={_n(z_min)} mm。"
            f"请给出 collision_risk 与 gouge 判定，并说明对应的 Auto-Diff 颜色。")


def _rw_tolerance(rec, rng):
    inp = _inputs(rec)
    tols, up, lo = inp.get("tols"), inp.get("upper_dev"), inp.get("lower_dev")
    if not tols or up is None or lo is None:
        return None
    basic = inp.get("basic")
    n = len(tols)
    arr = "[" + ", ".join(_n(t) for t in tols) + "]"
    base_txt = f"基本尺寸 {_n(basic)} mm" if basic is not None else "基本尺寸未标注"
    v = rng.randrange(STYLE_COUNT)
    if v == 0:
        return (f"尺寸链校核：共 {n} 个组成环，半公差分别为 {arr} mm（{base_txt}）；"
                f"孔轴上偏差 {_n(up)} mm、下偏差 {_n(lo)} mm。"
                f"请用极值法与统计法（RSS）给出封闭环公差带半宽，"
                f"并判定配合性质与配合等级。")
    if v == 1:
        chain = "、".join(f"{_n(t)} mm" for t in tols)
        return (f"公差链由 {n} 个环节组成：{chain}。"
                f"孔轴配合上偏差 {_n(up)} mm、下偏差 {_n(lo)} mm（{base_txt}）。"
                f"请用极值法与统计法求封闭环公差带半宽，并判定配合性质与等级。")
    return (f"配合公差预算单：{n} 个组成环的半公差分别为 {arr} mm（{base_txt}），"
            f"孔的上偏差 {_n(up)} mm、下偏差 {_n(lo)} mm。"
            f"输出极值法半宽与 RSS 半宽，并给出配合类别与配合等级。")


def _rw_geom_delta(rec, rng):
    inp = _inputs(rec)
    vol, before = inp.get("feature_vol"), inp.get("before")
    if None in (vol, before):
        return None
    feat = _g(_ws(rec), "feature") or "特征"
    v = rng.randrange(STYLE_COUNT)
    if v == 0:
        return (f"特征切除校核：在工件上加工一个{feat}，特征体积 {_n(vol)} mm3，"
                f"切除前工件体积 {_n(before)} mm3。请给出体积变化量 ΔV 与切除后体积，"
                f"并校验体积守恒是否通过。")
    if v == 1:
        return (f"某工序需切除一个{feat}：切除前工件体积 {_n(before)} mm3，"
                f"特征体积 {_n(vol)} mm3。请给出几何体积变化量 ΔV、加工后体积，"
                f"并说明体积守恒结论。")
    return (f"体积守恒断言：切除前工件体积 {_n(before)} mm3，本次切除的{feat} "
            f"特征体积 {_n(vol)} mm3。请预测 ΔV 与切除后体积，"
            f"并校验 before+ΔV=after 是否成立。")


def _rw_mass_props(rec, rng):
    inp = _inputs(rec)
    shape, params, rho = inp.get("shape"), inp.get("params") or {}, inp.get("rho")
    if not shape or not params or rho is None:
        return None
    mat = _mat_by_rho(rho) or _mat_from_text(_orig_prompt(rec)) or "钢"
    ask = "请给出体积、质量、质心坐标、绕质心惯性矩 Ixx 与 Izz。"
    v = rng.randrange(STYLE_COUNT)
    if shape == "box":
        l, w, h = params.get("l"), params.get("w"), params.get("h")
        if None in (l, w, h):
            return None
        geo = f"长 l={_n(l)} mm、宽 w={_n(w)} mm、高 h={_n(h)} mm"
        if v == 0:
            return f"质量属性计算：{mat} 长方体零件，{geo}。{ask}"
        if v == 1:
            return (f"预测box（{geo}）的质量属性，材料 {mat}，"
                    f"求体积、质量、质心与惯性矩。")
        return (f"已知 {mat} 方块：长度 l={_n(l)} mm、宽度 w={_n(w)} mm、"
                f"高度 h={_n(h)} mm。{ask}")
    r, h = params.get("r"), params.get("h")
    if None in (r, h):
        return None
    geo = f"半径 r={_n(r)} mm、高 h={_n(h)} mm"
    if v == 0:
        return f"质量属性计算：{mat} 圆柱零件，{geo}。{ask}"
    if v == 1:
        return (f"预测cylinder（{geo}）的体积、质量、质心与惯性矩，材料 {mat}。")
    return (f"已知 {mat} 实心圆柱：半径 r={_n(r)} mm、高度 h={_n(h)} mm。{ask}")


def _rw_invalid(rec, rng):
    """非法输入题的语义就是「这几句原话」，只能加不同程度的审查包装。"""
    orig = _orig_prompt(rec).strip()
    if not orig:
        return None
    v = rng.randrange(STYLE_COUNT)
    if v == 0:
        return f"现场提交的参数如下：{orig} 请先判断该输入是否合法；若不合法，按契约给出结构化报错。"
    if v == 1:
        return f"请审查这条工单：{orig} 说明它能否参与物理求解，并给出结论。"
    return orig


def _rw_design(rec, rng):
    inp = _inputs(rec)
    r_out, r_bore = inp.get("r_out"), inp.get("r_bore")
    t, n, r_hole = inp.get("t"), inp.get("n_holes"), inp.get("r_hole")
    rho = inp.get("rho")
    if None in (r_out, r_bore, t, n, r_hole):
        return None
    d_out, d_bore, d_hole = float(r_out) * 2, float(r_bore) * 2, float(r_hole) * 2
    pcd = _g(_g(_g(_expected(rec), "design") or {}, "bolt_holes") or {}, "pcd_mm")
    mat = _g(_ws(rec), "material") or _mat_by_rho(rho) or "钢"
    pcd_txt = f"φ{_n(pcd)} mm 节圆" if pcd is not None else "同一节圆"
    v = rng.randrange(STYLE_COUNT)
    if v == 0:
        return (f"设计一个{mat}法兰：外径 φ{_n(d_out)} mm，中心孔 φ{_n(d_bore)} mm，"
                f"厚度 {_n(t)} mm，{int(n)}×φ{_n(d_hole)} mm 螺栓孔均布于 {pcd_txt}。"
                f"请给出可直接驱动 CAD 建模的设计规格（含特征树）与质量属性。")
    if v == 1:
        return (f"需要一张{mat}法兰的 CAD 建模规格：外径 φ{_n(d_out)} mm、"
                f"中心孔 φ{_n(d_bore)} mm、厚度 {_n(t)} mm；{int(n)} 个 "
                f"φ{_n(d_hole)} mm 的螺栓孔均布于 {pcd_txt}。"
                f"同时给出体积与质量。")
    return (f"请按需求输出{mat}法兰件设计：外径 φ{_n(d_out)} mm，内孔 φ{_n(d_bore)} mm，"
            f"板厚 {_n(t)} mm，螺栓孔 {int(n)} 个 φ{_n(d_hole)} mm，节圆 φ{_n(pcd) if pcd is not None else 0} mm。"
            f"需要完整特征树与质量属性。")


def _rw_process(rec, rng):
    inp = _inputs(rec)
    D, L, ap = inp.get("D"), inp.get("L"), inp.get("ap")
    f, vc, r_eps = inp.get("f"), inp.get("vc"), inp.get("r_eps")
    if None in (D, f, vc):
        return None
    mat = _mat_from_text(_orig_prompt(rec)) or "工件"
    ap_txt = f"ap={_n(ap)} mm" if ap is not None else "ap 按粗车常规取值"
    re_txt = f"rε={_n(r_eps)} mm" if r_eps is not None else "rε 按刀片样本取值"
    L_txt = f"车削长度 L={_n(L)} mm" if L is not None else "车削长度按图样"
    v = rng.randrange(STYLE_COUNT)
    if v == 0:
        return (f"为{mat}轴类件（φ{_n(D)} mm，{L_txt}）编车削工艺："
                f"粗车 {ap_txt}、每转进给 f={_n(f)} mm/rev、"
                f"切削速度 vc={_n(vc)} m/min、刀尖圆弧半径 {re_txt}。"
                f"请算出主轴转速、进给速度、MRR、Ra 与单刀切削时间，并给出工序序列。")
    if v == 1:
        return (f"{mat}轴类件车削任务：工件直径 φ{_n(D)} mm，{L_txt}；"
                f"粗加工取 {ap_txt}、f={_n(f)} mm/rev、vc={_n(vc)} m/min、{re_txt}。"
                f"请给出主轴转速 n、进给速度 vf、材料去除率 MRR、表面粗糙度 Ra、"
                f"单刀切削时间，以及粗/精车的工序安排。")
    return (f"按下列参数编制{mat}外圆车削工艺并核算性能指标：φ{_n(D)} mm、"
            f"{L_txt}、{ap_txt}、f={_n(f)} mm/rev、切削速度 vc={_n(vc)} m/min、{re_txt}。"
            f"需要主轴转速、进给速度、材料去除率、表面粗糙度与单刀工时。")


def _rw_adapt_material(rec, rng):
    inp = _inputs(rec)
    Sy, sigma = inp.get("Sy"), inp.get("sigma")
    if None in (Sy, sigma):
        return None
    ws = _ws(rec)
    name = _g(ws, "material") or "该材料"
    rho_txt = ""
    try:
        import build_worldmodel_v2 as V2

        for m in V2.UNFAMILIAR_MATS:
            if str(m.get("name")) == str(name):
                rho_txt = (f"、密度 {float(m['rho']) * 1000.0:.2f} g/cm3"
                           f"、弹性模量 {_n(m['E'])} MPa")
                break
    except Exception:
        pass
    v = rng.randrange(STYLE_COUNT)
    if v == 0:
        return (f"陌生材料 {name}（不在标准库）。现场物性表给出："
                f"屈服强度 {_n(Sy)} MPa{rho_txt}。"
                f"构件 FEA 峰值 von Mises 应力 σ_vm={_n(sigma)} MPa。"
                f"请严格用该表数据计算安全系数，并判定 FOS≥1.5 是否通过。")
    if v == 1:
        return (f"{name} 属现场新引入材料（不在标准库，只有现场物性表："
                f"屈服强度 {_n(Sy)} MPa{rho_txt}）。"
                f"构件峰值 von Mises 应力 {_n(sigma)} MPa。"
                f"请据此给出安全系数与门限判定，不得套用常识物性。")
    return (f"请用现场物性表作答、不要凭记忆取物性：材料 {name}，"
            f"物性表给出屈服强度 {_n(Sy)} MPa{rho_txt}；"
            f"FEA 峰值 von Mises 应力 {_n(sigma)} MPa。"
            f"求安全系数，并判定 FOS≥1.5 是否满足。")


def _rw_adapt_machine(rec, rng):
    inp = _inputs(rec)
    D, vc, n_max = inp.get("D"), inp.get("vc"), inp.get("n_max")
    if None in (D, vc, n_max):
        return None
    ws = _ws(rec)
    mc = _g(ws, "machine") or "该机床"
    feed_txt = ""
    try:
        import build_worldmodel_v2 as V2

        for m in V2.UNFAMILIAR_MACHINES:
            if str(m.get("name")) == str(mc):
                feed_txt = f"，最大进给 {_n(m['feed_max'])} mm/min"
                break
    except Exception:
        pass
    v = rng.randrange(STYLE_COUNT)
    if v == 0:
        return (f"陌生机床 {mc}（现场参数表：最高转速 {_n(n_max)} rpm{feed_txt}）。"
                f"要在 φ{_n(D)} mm 工件上以切削速度 vc={_n(vc)} m/min 车削，"
                f"需要多少主轴转速？是否超出机床能力？请严格按参数表判定。")
    if v == 1:
        return (f"现场有一台不在常用库里的机床 {mc}，参数表标注最高转速 {_n(n_max)} rpm"
                f"{feed_txt}。计划车削 φ{_n(D)} mm 工件，切削速度取 vc={_n(vc)} m/min。"
                f"请按参数表核算所需转速，并判断是否在能力范围内。")
    return (f"机床能力校核：{mc}（额定最高转速 {_n(n_max)} rpm{feed_txt}）。"
            f"待加工 φ{_n(D)} mm 外圆，切削速度 vc={_n(vc)} m/min。"
            f"所需主轴转速是多少？现有设备够不够用？")


REWRITERS: Dict[str, Callable[[Dict[str, Any], random.Random], Optional[str]]] = {
    "removal": _rw_removal,
    "roughness": _rw_roughness,
    "fea_fos": _rw_fea_fos,
    "collision": _rw_collision,
    "tolerance": _rw_tolerance,
    "geom_delta": _rw_geom_delta,
    "mass_props": _rw_mass_props,
    "invalid": _rw_invalid,
    "design": _rw_design,
    "process": _rw_process,
    "adapt_material": _rw_adapt_material,
    "adapt_machine": _rw_adapt_machine,
}


# ---------------------------------------------------------------------------
# 对外接口
# ---------------------------------------------------------------------------
def rewrite(rec: Dict[str, Any], fam: str, rng: random.Random) -> Optional[str]:
    """返回改写后的 user prompt；None 表示本族/本样本不改写（保持原文）。"""
    fn = REWRITERS.get(fam)
    if fn is None or not rec:
        return None
    try:
        new = fn(rec, rng)
    except Exception:
        return None
    if not new or not str(new).strip():
        return None
    return new


def wrap(gen: Callable[[random.Random], Optional[Dict[str, Any]]], fam: str):
    """把生成器包一层题面改写。改写失败时原样返回，绝不丢样本、绝不改期望值。

    用 functools.wraps 挂上 __wrapped__，便于去污探针/审计反查未改写的原始生成器。
    """

    def g(rng: random.Random):
        rec = gen(rng)
        if not rec or not ENABLED:
            return rec
        new = rewrite(rec, fam, rng)
        if new:
            try:
                rec["messages"][1]["content"] = new
                rec.setdefault("meta", {})["paraphrase"] = fam
            except Exception:
                return rec
        return rec

    g.__name__ = f"para_{getattr(gen, '__name__', 'gen')}"
    g.__wrapped__ = gen
    return g


# ---------------------------------------------------------------------------
# 自测：改写不得破坏下游场景推断
# ---------------------------------------------------------------------------
def selftest(samples: int = 200, seed: int = 20261108, verbose: bool = False) -> int:
    import eval_worldmodel as E
    from anti_hallucination_guard import infer_scenario_from_prompt

    print("=" * 78)
    print("评测题面改写层自测：改写后 infer 是否仍归本族")
    print("=" * 78)
    total_bad = 0
    for fam, gen in E.GEN_BY_FAMILY.items():
        rng = random.Random(seed)
        ok = miss = none = 0
        bad_cases = []
        for _ in range(samples):
            rec = gen(rng)
            if not rec:
                none += 1
                continue
            orig = _orig_prompt(rec)
            new = rewrite(rec, fam, rng)
            if not new:
                none += 1
                continue
            got = (infer_scenario_from_prompt(new) or {}).get("task")
            if got == fam:
                ok += 1
            else:
                miss += 1
                if len(bad_cases) < 2:
                    bad_cases.append((got, new[:160]))
        total_bad += miss
        flag = "OK" if miss == 0 and ok > 0 else "MISMATCH"
        print(f"{fam:<16} 改写成功 {ok:>4}  推断失配 {miss:>3}  未改写 {none:>3}   {flag}")
        if verbose or miss:
            for got, txt in bad_cases:
                print(f"    -> 判成 {got}: {txt}")
    print("-" * 78)
    if total_bad:
        print(f"[FAIL] 共 {total_bad} 条改写后族归属失配：改写句式破坏了场景推断依赖的标签，"
              f"必须先修改写器（或补推断器），不能靠评测分数掩盖")
        return 1
    print("[PASS] 12 族改写后 infer 归族 100% 一致，改写只换措辞不换语义")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=200, help="每族采样次数")
    ap.add_argument("--seed", type=int, default=20261108)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    return selftest(args.samples, args.seed, args.verbose)


if __name__ == "__main__":
    raise SystemExit(main())
