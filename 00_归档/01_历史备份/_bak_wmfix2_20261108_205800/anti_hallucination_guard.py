#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
anti_hallucination_guard.py — 推理时反幻觉护栏（原型，可 import）
=================================================================
设计立场：本项目实测的幻觉几乎全部落在「确定性可判定」的位置上
  - 数值 / 量纲 / 物理定律绑定错      -> 交给解析求解器，不让模型写数字
  - 不存在的字段名 / 工具名           -> 交给白名单，不让模型自由命名
  - 格式竞争（tool vs world_state）   -> 交给 JSON schema + 顶层键白名单
  - 伪造「已验证 / PASS / 完成」       -> 交给证据门，无执行回执即拒
模型只保留它擅长的部分：意图理解、定律选择、参数绑定。

四层（成本从低到高，命中即短路）：
  L0 SHAPE   schema / 顶层键 / 工具名白名单
  L1 GROUND  数字接地（算式字面量必须来自题面或定律常数）+ 量纲一致性
  L2 SOLVER  wm_verifier.recompute 复算并覆盖数值
  L3 EVIDENCE 断言类措辞必须有执行回执

用法：
  from anti_hallucination_guard import Guard, load_tool_whitelist
  g = Guard()
  r = g.run(response_text, prompt, scenario, case_criteria)
  # r.action in {accept, corrected, rejected, escalate}
  # r.corrected 是可直接回灌工具链的 world_state

  python scripts/anti_hallucination_guard.py --selftest
"""
from __future__ import annotations

import ast
import json
import math
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Set, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
import wm_verifier  # noqa: E402  项目内单一真源求解器
try:  # 契约字段名录（平铺归一用；缺失时降级为「剥前缀」策略）
    import wm_contract  # noqa: E402
    import wm_schema  # noqa: E402
except Exception:  # pragma: no cover
    wm_contract = None
    wm_schema = None

# 顶层键白名单：契约规定 world_state 是唯一合法顶层业务键
ALLOWED_TOP_KEYS: Set[str] = {
    "world_state", "derivation", "correction", "verification",
    "design", "invalid", "reason", "fos_gate", "volume_conservation",
    "autodiff", "evidence",
    # 契约 A-1：结构键（非业务数值）必须放行，否则 process/adapt 两族的
    # 工序序列块与适配回执块会被判「未登记的顶层键」而整条拒掉。
    # 这三块只承载体裁信息，任何数值仍必须落在 world_state 内经 L2 接地校验。
    "process_plan", "adaptation", "metadata",
}
FORBIDDEN_TOP_KEYS: Set[str] = {
    "tool", "arguments", "name", "action", "function", "vba_code", "tool_calls",
}

# 定律自身允许的常数（题面未给、但代入公式合法）
LAW_CONSTANTS: Set[float] = {0.0, 1.0, 2.0, 3.0, 4.0, 8.0, 12.0, 1000.0,
                             100.0, 60.0, math.pi, 1e-9, 0.5, 1.5}

# 「已验证」类断言：没有执行回执就不许说
CLAIM_PATTERNS = [
    r"(?i)\b(100%|全部|均已|已经)\s*(pass|通过|验证|校验)",
    # 注意：不能把 auto-?diff 放进来 —— autodiff 是 VERICUT 的合法结果字段名，
    # 早期版本曾因此把 collision 任务的无缺陷对照误杀（10% FPR）。
    r"(?i)(沙箱仿真校验|已验证|验证通过|校验通过|已完成建模|实测通过)",
    r"(?i)(validation passed|all tests passed|fully verified)",
]
EVIDENCE_MARKERS = ("receipt", "execution_id", "tool_result", "verified_by_solver",
                    "evidence_id", "log_id")


# ---------------------------------------------------------------------------
# 工具白名单：从工具定义源码 AST 枚举，杜绝手写名单漂移
# ---------------------------------------------------------------------------
def load_tool_whitelist(path: Optional[str] = None) -> Set[str]:
    p = path or os.path.join(ROOT, "bridges", "tool_calling_specs.py")
    with open(p, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    names: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            v = node.value
            if v.startswith("cadcam_") and re.fullmatch(r"cadcam_[a-z0-9_]+", v):
                names.add(v)
    return names


# ---------------------------------------------------------------------------
# JSON 提取：容忍围栏 / 前后缀 / Python 字面量（事后容错，非解码期约束）
# ---------------------------------------------------------------------------
def parse_json_candidate(text: str) -> Tuple[Optional[Any], Optional[str]]:
    if text is None:
        return None, "empty_response"
    s = str(text).strip()
    if not s:
        return None, "empty_response"
    # 去掉 <think>...</think>
    s = re.sub(r"<think>.*?</think>", "", s, flags=re.S | re.I).strip()
    # 去围栏
    s = re.sub(r"^```(?:json|python)?\s*|\s*```$", "", s, flags=re.I | re.M).strip()
    try:
        return json.loads(s), None
    except Exception:
        pass
    start = s.find("{")
    if start < 0:
        return None, "no_json_object"
    depth, in_str, esc = 0, False, False
    for i in range(start, len(s)):
        ch = s[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                frag = s[start:i + 1]
                for candidate in (frag,
                                  frag.replace("True", "true").replace("False", "false")
                                      .replace("None", "null")):
                    try:
                        return json.loads(candidate), None
                    except Exception:
                        continue
                return None, "malformed_json_object"
    return None, "unterminated_json_object"


# ---------------------------------------------------------------------------
# L1 数字接地
# ---------------------------------------------------------------------------
# 负向后顾只挡数字/小数点，不能挡中文：Python 的 \w 含 CJK，
# "外径59.6mm" 用 (?<![\w.]) 会一个数字都抽不到，导致题面白名单为空、全量误报。
NUM_RE = re.compile(r"(?<![0-9.])(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)")
UNIT_NUM_RE = re.compile(
    r"(?<![0-9.])(-?\d+(?:\.\d+)?)\s*(mm3|mm|um|g|kg|MPa|kN|deg|rev|min)\b",
    re.I)


def _canon(x: float) -> float:
    return round(float(x), 6)


def numbers_in(text: str) -> Set[float]:
    return {_canon(float(m)) for m in NUM_RE.findall(text or "")}


def unit_numbers_in(text: str) -> Set[float]:
    return {_canon(float(m)) for m, _ in UNIT_NUM_RE.findall(text or "")}


def grounding_issues(prompt: str, response: str, derivation: Any = None,
                     extra_allowed: Optional[Set[float]] = None) -> List[str]:
    """响应中带单位的数字必须能在题面 / 定律常数 / 求解器参考值里找到出处。

    这是 cad_cam_blind_test_report.md「响应中出现单位数字但不在 prompt」口径的
    运行时化：判分器只在事后统计，护栏在生成链路上当场拦。
    """
    allowed = numbers_in(prompt) | LAW_CONSTANTS | set(extra_allowed or ())
    if isinstance(derivation, dict):
        # 推导式里的字面量单列检查（模型把 r_eps=0.8 换成默认 1.0 就在这里露馅）
        expr_text = " ".join(str(v) for v in derivation.values() if isinstance(v, str))
        allowed |= numbers_in(expr_text) & numbers_in(prompt)
    seen = unit_numbers_in(response)
    # 只查带单位的数字，避免把代码里的数组下标 / 版本号当幻觉
    stray = sorted(seen - allowed)
    return [f"无出处数字 {v:g}（响应中带单位，但题面/定律常数中没有）" for v in stray]


# ---------------------------------------------------------------------------
# 场景自动抽取器：从用户提示词直接识别工程物理场景
# ---------------------------------------------------------------------------
# 常用材料密度 g/mm^3（与数据生成器同源；此处内联，避免 import 重型训练脚本）
_MAT_RHO = {
    "45钢": 7.85e-3,
    "铝合金6061": 2.70e-3,
    "不锈钢304": 8.00e-3,
    "钛合金TC4": 4.43e-3,
    "黄铜H62": 8.50e-3,
}
_MAT_ALIAS = (
    (r"45\s*[#＃]?\s*钢|(?<!\d)45#(?!\d)", "45钢"),
    (r"(?<!\d)6061(?!\d)|铝合?金", "铝合金6061"),
    (r"(?<!\d)304(?!\d)|不锈钢", "不锈钢304"),
    (r"(?<!\d)TC4(?!\d)|钛合?金", "钛合金TC4"),
    (r"(?<!\d)H62(?!\d)|黄铜", "黄铜H62"),
)
# 牌号必须带数字边界：不加边界时 "毛坯体积 453044 mm^3" 里的 4530**44**→ 含子串
# "304"，mat_name 被判成不锈钢304，进而把黄铜 8.5e-3 的密度改写成 8.0e-3
# （实测 self_correction 样本 rho 全错到 0.008，根因即此）。

# 标签与等号之间常夹轴字母/字段名（「安全平面 Z=29.3」「长 l=120」），
# 旧的 `标签\s*[=:]\s*数字` 会整段失配。下面统一允许 1~6 个标识符字符。
# 关键：尾部不得含数字——「外径 φ197.6」中 φ 属希腊字母会被吃掉，
# 若允许续接数字，_AXIS_OPT 会贪婪吞到 φ19 再回溯抓 7.6，
# 造成直径被解析成个位数（实测 design 族 200/200 全错，根因即此）。
_AXIS_OPT = r"(?:[A-Za-zα-ωΑ-Ω_][A-Za-zα-ωΑ-Ω_]{0,5})?"


def _num(p: str, names: str, signed: bool = True) -> Optional[float]:
    """抓取「标签 [轴字母]=数值」形式的量。失败返回 None。"""
    sgn = r"[-+]?" if signed else r""
    pat = (rf"(?<![A-Za-z0-9_])(?:{names})\s*{_AXIS_OPT}\s*[=＝:：]?\s*"
           rf"(?:[φΦ∅]\s*)?({sgn}\d+(?:\.\d+)?)")
    m = re.search(pat, p, re.I)
    return float(m.group(1)) if m else None


def infer_scenario_from_prompt(prompt: str) -> Optional[Dict[str, Any]]:
    """从用户提示词直接推断标准工程物理场景与参数输入。"""
    if not prompt:
        return None
    p = str(prompt)

    # 0. invalid 族：题面本身缺参/越界/NaN，只能按契约报错，禁止硬算
    if re.search(r"未提供|未给出|未给|没有给|没给|未说明|没说明|缺失参数|缺少参数|"
                 r"缺少|未包含|不包含|无法判定单位|单位缺失|"
                 r"DOC\s*[=＝]\s*[-−]\d|NaN|Inf\b|inf\b|除以零|分母为\s*0|"
                 r"半公差为负|vf\s*[=＝]\s*0", p):
        return {"task": "invalid", "inputs": {}}

    # 0b. 「要质量却没给物性」的非法题：需求与输入不匹配，必须报 invalid。
    # 实测 STEP #8：题面只给体积与实体数、直接要总质量，旧逻辑推不出场景 →
    # 掉进 derivation 通道，把体积乘默认钢密度硬算出 1893.06 g，
    # 属于「把非法题静默算成合法值」的假绿，危害大于拒答，故前置拦下。
    if re.search(r"(?:总质量|质量)\s*[（(]?\s*(?:kg|g|千克|克)?\s*[)）]?|求.{0,10}质量|给出.{0,10}质量", p):
        has_rho = bool(re.search(r"密度|rho|ρ|g/cm3|g/mm3|kg/m3|7\.85|0\.0027|0\.00785", p, re.I))
        has_mat = any(re.search(pat, p) for pat, _ in _MAT_ALIAS)
        if not has_rho and not has_mat:
            return {"task": "invalid", "inputs": {"material": None}}

    # 1c. adapt_material: 陌生材料 + 现场物性表（必须用表值，禁用常识记忆）。
    # 必须排在 fea_fos 之前：两者的判别式都是「屈服强度 + 应力」，
    # 若 fea_fos 先匹配，适配族的 σ_vm 会被当成普通 FEA 题，
    # 参考值虽同构（Sy/σ）但 task 标签会错，eval 按族判分时整族判负。
    if re.search(r"陌生材料|不在标准库|现场物性表|用户物性表|物性表", p):
        m_sy2 = re.search(r"屈服强度\s*[=＝:：]?\s*(\d+(?:\.\d+)?)", p)
        m_sig2 = re.search(r"(?:von\s*Mises|σ_vm|σ|sigma|工作应力|最大应力|峰值应力|应力)"
                           r"\s*[=＝:：]?\s*(\d+(?:\.\d+)?)", p, re.I)
        if m_sy2 and m_sig2:
            return {"task": "adapt_material",
                    "inputs": {"Sy": float(m_sy2.group(1)),
                               "sigma": float(m_sig2.group(1))}}

    # 1a. adapt_machine: 现场机床参数（最高转速上限）+ 刀具直径 + 切削速度。
    # 契约补齐族之一：旧 infer 完全没有这一族，题面只要带「现场机床/最高转速」，
    # 推断即返回 None → 全部数值退化为无参考的可信度直出，护栏形同虚设。
    m_nmax = re.search(r"(?:最高转速|最大转速|转速上限|主轴上限|n_?max)\s*[=＝:：]?"
                       r"\s*(\d+(?:\.\d+)?)", p, re.I)
    m_mc = re.search(r"机床|设备|机型|machine|加工中心|车床", p, re.I)
    if m_mc and m_nmax:
        d_a = re.search(r"(?:φ|Φ|∅)\s*(\d+(?:\.\d+)?)", p) or \
            re.search(r"(?:刀具直径|工件直径|直径|(?<![A-Za-z])D)\s*[=＝:：]?\s*"
                      r"(\d+(?:\.\d+)?)", p)
        v_a = re.search(r"(?:切削速度|线速度|(?<![A-Za-z])[Vv]c)\s*[=＝:：]?\s*"
                        r"(\d+(?:\.\d+)?)", p)
        if d_a and v_a:
            return {"task": "adapt_machine",
                    "inputs": {"D": float(d_a.group(1)), "vc": float(v_a.group(1)),
                               "n_max": float(m_nmax.group(1))}}

    # 1b. process: 工艺规划（切削速度 + 工件直径 + 每转进给 → n/vf/MRR/Ra/切削时间）。
    # 必须排在 roughness 之前：工艺题同样带「f=… 与 rε=…」，若先跑 roughness
    # 分支，process 族会被误判成粗糙度族，只复算 Ra 一项、其余四项失去参考。
    m_vc = re.search(r"(?:切削速度|线速度|(?<![A-Za-z])[Vv]c)\s*[=＝:：]?\s*"
                     r"(\d+(?:\.\d+)?)", p)
    if m_vc:
        d_p = re.search(r"(?:φ|Φ|∅)\s*(\d+(?:\.\d+)?)", p) or \
            re.search(r"(?:工件直径|刀具直径|直径|(?<![A-Za-z])D)\s*[=＝:：]?\s*"
                      r"(\d+(?:\.\d+)?)", p)
        f_p = re.search(r"(?<![A-Za-z])f\s*[=＝:：]\s*(\d+(?:\.\d+)?)", p) or \
            re.search(r"(?:每转进给(?:量)?|进给量|f_r)\s*[=＝:：]?\s*(\d+(?:\.\d+)?)", p, re.I)
        if d_p and f_p:
            ap_p = re.search(r"(?:ap|背吃刀量|切削深度|切深|DOC)\s*[=＝:：]?\s*"
                             r"(\d+(?:\.\d+)?)", p, re.I)
            re_p = re.search(r"(?:r_?ε|r_?eps|刀尖圆弧(?:半径)?|刃口半径)\s*[=＝:：]?\s*"
                             r"(\d+(?:\.\d+)?)", p, re.I)
            l_p = re.search(r"(?:车削长度|加工长度|刀路长度|切削长度|(?<![A-Za-z])L)"
                            r"\s*[=＝:：]?\s*(\d+(?:\.\d+)?)", p)
            return {"task": "process", "inputs": {
                "D": float(d_p.group(1)), "vc": float(m_vc.group(1)),
                "f": float(f_p.group(1)),
                "ap": float(ap_p.group(1)) if ap_p else None,
                "r_eps": float(re_p.group(1)) if re_p else None,
                "L": float(l_p.group(1)) if l_p else None,
            }}

    # 1. fea_fos: 屈服强度与应力
    m_sy = re.search(r"(?:屈服强度|Sy|S_y)\s*[=＝:：]?\s*(\d+(?:\.\d+)?)", p, re.I)
    m_sig = re.search(r"(?:von\s*Mises|σ_vm|σ|sigma|峰值应力|应力)\s*[=＝:：]?\s*(\d+(?:\.\d+)?)", p, re.I)
    if m_sy and m_sig:
        return {"task": "fea_fos", "inputs": {"Sy": float(m_sy.group(1)), "sigma": float(m_sig.group(1))}}

    # 2. roughness: 进给量与刀尖圆弧
    # 题面写法多样：「r_eps=0.8」「刀尖圆弧半径 0.8 mm」「刃口半径 0.8」，
    # 旧正则只认「刀尖圆弧」紧跟数字，遇到「刀尖圆弧半径 0.8」直接失配 →
    # 推断失败 → 护栏退回纯 derivation 通道（实测 STEP #5 因此漏纠 16.9→2.25）。
    m_f = re.search(r"(?<![a-zA-Z])f\s*[=＝:：]?\s*(\d+(?:\.\d+)?)", p)
    m_reps = re.search(r"(?:r_eps|r_ε|刀尖圆弧(?:半径)?|刀尖半径|圆弧半径|刃口半径|"
                       r"(?<![A-Za-z])r(?:eps)?)\s*(?:半径)?\s*[=＝:：]?\s*(\d+(?:\.\d+)?)", p)
    if m_f and m_reps:
        return {"task": "roughness", "inputs": {"f": float(m_f.group(1)), "r_eps": float(m_reps.group(1))}}

    # 3. geom_delta: 通孔/切除体积与切除前体积
    m_feat = re.search(r"(?:特征体积|通孔体积|切除体积|切槽体积|孔体积|"
                       r"feature_vol(?:ume)?|"
                       r"该(?:实体|特征|支耳实体)[^。；;，,]{0,10}?体积)"
                       r"\s*[=＝:：]?\s*(\d+(?:\.\d+)?)", p, re.I)
    m_bef = re.search(r"(?:切除前工件体积|before_volume|before|切除前体积|工件体积|"
                      r"实测总体积|总体积|毛坯体积|part_volume)"
                      r"\s*[=＝:：]?\s*(\d+(?:\.\d+)?)", p, re.I)
    if m_feat and m_bef:
        return {"task": "geom_delta", "inputs": {"feature_vol": float(m_feat.group(1)), "before": float(m_bef.group(1))}}

    # 4. removal: doc, woc, L, rho, stock_vol
    m_doc = re.search(r"(?:DOC|切削深度|ap)\s*[=＝:：]?\s*(\d+(?:\.\d+)?)", p, re.I)
    m_woc = re.search(r"(?:WOC|切削宽度|ae)\s*[=＝:：]?\s*(\d+(?:\.\d+)?)", p, re.I)
    m_l = re.search(r"(?:L|刀路长度|切削长度)\s*[=＝:：]?\s*(\d+(?:\.\d+)?)", p, re.I)
    m_rho = re.search(r"(?:rho|密度)\s*[=＝:：]?\s*(\d+(?:\.\d+)?)", p, re.I)
    m_stock = re.search(r"(?:stock_vol|毛坯体积)\s*[=＝:：]?\s*(\d+(?:\.\d+)?)", p, re.I)
    m_vf = re.search(r"(?:vf|进给速度)\s*[=＝:：]?\s*(\d+(?:\.\d+)?)", p, re.I)
    # 毛坯体积两条来源：显式 stock_vol，或「方料 A×B×C」尺寸（CAD 包围盒口径）。
    # 成品体积同理，题面常写「加工后成品实测体积 241153.93 mm3」。
    # 实测 STEP #1：旧逻辑要求 doc*woc*L 与 stock_vol 齐备，题面没有 L、
    # 毛坯只给方料尺寸 → 推断失败 → 场景为空 → 求解器给不出 mrr，判 FAIL。
    m_box = re.search(r"(\d+(?:\.\d+)?)\s*[×xX*]\s*(\d+(?:\.\d+)?)\s*[×xX*]\s*(\d+(?:\.\d+)?)", p)
    m_fin = re.search(r"(?:成品(?:实测)?体积|加工后成品(?:实测)?体积|加工后(?:实测)?体积|"
                      r"resulting_volume|成品体积)\s*[=＝:：]?\s*(\d+(?:\.\d+)?)", p, re.I)
    stock_vol = (float(m_stock.group(1)) if m_stock
                 else (round(float(m_box.group(1)) * float(m_box.group(2)) * float(m_box.group(3)), 4)
                       if m_box else None))
    fin_vol = float(m_fin.group(1)) if m_fin else None
    has_cad = stock_vol is not None and fin_vol is not None
    has_analytic = bool(m_doc and m_woc and m_l)
    mat_name_hint = next((nm for pat, nm in _MAT_ALIAS if re.search(pat, p)), None)
    if (m_rho or mat_name_hint or has_analytic or has_cad) and (has_cad or has_analytic):
        # 密度来源两条：题面显式密度，或题面给出的材料牌号（45钢/6061/304…）。
        # 旧逻辑强制要求显式密度，真实题面「45钢铣削 DOC=1.2 WOC=8 vf=350 L=120」
        # 不带密度即判 None → L2 数值复算整体失效（护栏只剩证据层）。
        rho_val = float(m_rho.group(1)) if m_rho else None
        if rho_val is not None and rho_val > 0.1:
            rho_val = rho_val / 1000.0
        # 题面密度常被四舍五入（7.85 -> 7.8 g/cm^3），有材料名时以材料库真值为准
        mat_name = mat_name_hint
        if mat_name:
            rho_val = _MAT_RHO[mat_name]
        if rho_val is None:
            rho_val = 7.85e-3
        return {
            "task": "removal",
            "inputs": {
                "doc": float(m_doc.group(1)) if m_doc else None,
                "woc": float(m_woc.group(1)) if m_woc else None,
                "L": float(m_l.group(1)) if m_l else None,
                "rho": rho_val,
                "stock_vol": stock_vol,
                "V": fin_vol,
                "vf": float(m_vf.group(1)) if m_vf else 500.0,
            }
        }

    # 5. collision: z_safe, z_min_rapid, stock_top
    # B-3 修复：题面写作「安全平面 Z=29.3」，标签与等号间夹了轴字母 Z，
    # 旧正则只认「安全平面=29.3」→ 推断失败 → 任何 issue 都被 rejected 拦死。
    z_safe = _num(p, r"z_safe|safe_plane_z|safe_z|安全高度|安全平面")
    z_min = _num(p, r"z_min_rapid|rapid_min_z|rapid_z|z_min|最低高度|最低|最小")
    z_top = _num(p, r"stock_top_z|stock_top|stock_z|工件顶面|毛坯顶面|毛坯上表面")
    if z_safe is not None and z_min is not None and z_top is not None:
        return {
            "task": "collision",
            "inputs": {"z_safe": z_safe, "z_min_rapid": z_min,
                       "stock_top": z_top},
        }

    # 6. tolerance: 半公差数组 + 上下偏差
    m_tols = re.search(r"半公差[^\[\]]{0,10}\[\s*([-\d.,\s]+?)\s*\]", p)
    up_dev = _num(p, r"上偏差|upper_dev|ES")
    lo_dev = _num(p, r"下偏差|lower_dev|EI")
    if m_tols and up_dev is not None and lo_dev is not None:
        try:
            tols = [float(t) for t in re.split(r"[,\s]+", m_tols.group(1)) if t]
        except ValueError:
            tols = []
        if tols and all(t >= 0 for t in tols):
            return {
                "task": "tolerance",
                "inputs": {"tols": tols, "upper_dev": up_dev,
                           "lower_dev": lo_dev},
            }

    # 6b. tolerance 自然语言写法：「公差链由 3 个环节组成：0.021 mm、0.013 mm、0.008 mm」
    # 旧逻辑只认「半公差[...]」方括号数组，真实题面几乎不会这么写，
    # 导致 tolerance 族只能靠 derivation 兜底（模型不写算式就无护栏）。
    m_chain = re.search(r"(?:公差链|公差环|tolerance_chain|分量公差|各环节公差|各环公差|"
                        r"各分量(?:公差)?)[^；;。\n]{0,60}", p)
    if up_dev is not None and lo_dev is not None and m_chain:
        seq = [float(x) for x in re.findall(r"(\d+(?:\.\d+)?)\s*mm", m_chain.group(0))]
        if len(seq) < 2:
            seq = [float(x) for x in
                   re.findall(r"(\d\.\d+)", m_chain.group(0))]
        if len(seq) >= 2:
            return {"task": "tolerance",
                    "inputs": {"tols": seq[:8], "upper_dev": up_dev, "lower_dev": lo_dev}}

    # 7b. mass_props 装配体口径：「各实体体积分别为 a, b, c mm3」+ 密度/材料名
    m_parts = re.search(r"(?:各实体|各零件|各部件)体积[^。；;\n]{0,16}?"
                        r"((?:\d+(?:\.\d+)?\s*[，,、]?\s*){2,})", p)
    if m_parts:
        parts = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", m_parts.group(1))]
        mat = next((nm for pat, nm in _MAT_ALIAS if re.search(pat, p)), None)
        rho_m = _MAT_RHO.get(mat) if mat else None
        if not rho_m:
            m_rho2 = re.search(r"(?:rho|密度)\s*[=＝:：]?\s*(\d+(?:\.\d+)?)", p, re.I)
            if m_rho2:
                v = float(m_rho2.group(1))
                rho_m = v / 1000.0 if v > 0.1 else v
        if len(parts) >= 2 and rho_m:
            return {"task": "mass_props", "inputs": {"parts": parts, "rho": rho_m}}

    # 7c. mass_props 自然语言几何题：「圆柱 r=28.7mm h=98.3mm，材料45钢，求质量/惯性矩」。
    # 旧逻辑只认生成器模板里的「预测 cylinder」，真实题面从不这么写 →
    # 推断返回 None，体积/质量/惯性矩三项全部失去复算参考。
    # 排除 design 族关键词，避免「设计轴套（含圆柱特征）」被质量族抢判。
    if not re.search(r"设计|design|法兰|轴套|端盖|螺栓孔|安装孔", p, re.I) and \
            re.search(r"质量属性|转动惯量|惯性矩|质心|"
                      r"求[^。；\n]{0,14}(?:质量|体积)", p):
        m_geo = re.search(r"圆柱|cylinder|长方体|方块|方料|(?<![A-Za-z])box\b", p, re.I)
        if m_geo:
            g = m_geo.group(0).lower()
            is_cyl = g in ("圆柱", "cylinder")
            if is_cyl:
                pr = _num(p, r"半径|(?<![A-Za-z])r|(?<![A-Za-z])R|(?<![A-Za-z])d")
                ph = _num(p, r"高度|高|(?<![A-Za-z])h")
                if _num(p, r"(?<![A-Za-z])d") and not re.search(
                        r"半径|(?<![A-Za-z])r\s*[=＝:：]", p):
                    pd = _num(p, r"(?<![A-Za-z])d")
                    pr = pd / 2.0 if pd else pr
                params = {"r": pr, "h": ph} if None not in (pr, ph) else None
                shape = "cylinder"
            else:
                pl = _num(p, r"长度|长|(?<![A-Za-z])l")
                pw = _num(p, r"宽度|宽|(?<![A-Za-z])w")
                ph2 = _num(p, r"高度|高|(?<![A-Za-z])h")
                params = ({"l": pl, "w": pw, "h": ph2}
                          if None not in (pl, pw, ph2) else None)
                shape = "box"
            if params:
                mat = next((nm for pat, nm in _MAT_ALIAS if re.search(pat, p)), None)
                m_rho3 = re.search(r"(?:rho|密度)\s*[=＝:：]?\s*(\d+(?:\.\d+)?)", p, re.I)
                rho3 = _MAT_RHO.get(mat) if mat else None
                if rho3 is None and m_rho3:
                    v3 = float(m_rho3.group(1))
                    rho3 = v3 / 1000.0 if v3 > 0.1 else v3
                if rho3:
                    return {"task": "mass_props",
                            "inputs": {"shape": shape, "params": params, "rho": rho3}}

    # 7. mass_props: 形状 + 几何参数 + 材料密度
    m_shape = re.search(r"预测\s*(box|cylinder|长方体|圆柱)", p, re.I)
    if m_shape:
        raw = m_shape.group(1).lower()
        shape = "box" if raw in ("box", "长方体") else "cylinder"
        if shape == "box":
            pl, pw, ph = _num(p, r"长"), _num(p, r"宽"), _num(p, r"高")
            params = {"l": pl, "w": pw, "h": ph} if None not in (pl, pw, ph) else None
        else:
            pr, ph = _num(p, r"半径|r"), _num(p, r"高|h")
            params = {"r": pr, "h": ph} if None not in (pr, ph) else None
        if params:
            mat = next((name for pat, name in _MAT_ALIAS if re.search(pat, p)), None)
            return {
                "task": "mass_props",
                "inputs": {"shape": shape, "params": params,
                           "rho": _MAT_RHO.get(mat, 7.85e-3)},
            }

    # 8. design: 需求 → 法兰规格（外径/中心孔/厚度/n×φ孔/材料）。
    # 契约补齐族之一：design 是唯一「输出可与 CAD 特征树对齐」的族，
    # 旧 infer 缺此分支使全部设计题无可复算参考，只能靠 LLM 自证。
    if re.search(r"设计|design", p, re.I) and re.search(r"法兰|flange|端盖|轴套", p, re.I):
        d_out = _num(p, r"外径|outer_dia|最大外形直径")
        d_bore = _num(p, r"中心孔|内孔|内径|bore_dia")
        th = _num(p, r"厚度|板厚|壁厚|thickness|(?<![A-Za-z])t(?![A-Za-z])|厚")
        m_nh = re.search(r"(\d+)\s*[×xX*]\s*(?:φ|Φ|∅)?\s*(\d+(?:\.\d+)?)\s*(?:mm)?\s*"
                         r"(?:的)?\s*(?:螺栓孔|通孔|安装孔)", p)
        if m_nh is None:
            m_nh = re.search(r"(?:螺栓孔|通孔|安装孔)\s*(\d+)\s*[×xX*]\s*"
                             r"(?:φ|Φ|∅)?\s*(\d+(?:\.\d+)?)", p)
        if m_nh is None:
            # 自然语言写法：「4 个 φ9 孔」「6 颗 φ11 的安装孔」
            m_nh = re.search(r"(\d+)\s*(?:个|颗|处)\s*(?:φ|Φ|∅)?\s*(\d+(?:\.\d+)?)\s*"
                             r"(?:mm)?\s*(?:的)?\s*(?:螺栓孔|通孔|安装孔|孔)", p)
        mat_d = next((nm for pat, nm in _MAT_ALIAS if re.search(pat, p)), None)
        if None not in (d_out, d_bore, th) and m_nh and mat_d:
            return {"task": "design",
                    "inputs": {"r_out": float(d_out) / 2.0,
                               "r_bore": float(d_bore) / 2.0,
                               "t": float(th),
                               "n_holes": int(m_nh.group(1)),
                               "r_hole": float(m_nh.group(2)) / 2.0,
                               "rho": _MAT_RHO[mat_d]}}

    return None


# ---------------------------------------------------------------------------
# world_state 单层平铺归一（契约铁律：world_state 内字段一律平铺，
# 禁止再套子对象，唯一例外 design.features）
# ---------------------------------------------------------------------------
# 必须同时处理两类脏数据，否则同一字段会出现两个来源并存：
#   1) 嵌套子对象：{"mass_props": {"volume_mm3": 355958.88}}
#   2) 带前缀平铺键：{"mass_props.volume_mm3": 241153.89}
# 二者归一后都落到 canonical 键，再由求解器值覆盖，从根上消除同义重复。
_NESTED_EXCEPTION = ("features",)  # design.features 是唯一允许保留嵌套的子对象


def _known_ws_keys() -> Set[str]:
    keys: Set[str] = set()
    if wm_contract is not None:
        for spec in (getattr(wm_contract, "KEY_SCHEMA", None) or {}).values():
            keys.update(spec.get("numeric") or [])
            keys.update((spec.get("gates") or {}).keys())
            keys.update(spec.get("texts") or [])
            # P-2 同步：契约新增 bools 分区（gouge / within_limit），
            # 若不纳入已知键集，前缀剥离与嵌套展平会把它们当外来键丢弃/误判幻觉。
            keys.update(spec.get("bools") or [])
    if wm_schema is not None:
        for name in ("NUM_FIELDS", "STR_FIELDS", "BOOL_FIELDS", "ARR_FIELDS", "FREE_STR_FIELDS"):
            seq = getattr(wm_schema, name, None)
            if isinstance(seq, dict):
                keys.update(seq.keys())
            elif isinstance(seq, (list, tuple, set)):
                keys.update(seq)
    return keys


_KNOWN_WS_KEYS: Set[str] = _known_ws_keys()


def _norm_key(key: str) -> str:
    """`mass_props.volume_mm3` → `volume_mm3`（仅当末段是契约登记字段）。"""
    k = str(key).strip()
    if "." in k:
        tail = k.split(".")[-1].strip()
        if tail in _KNOWN_WS_KEYS:
            return tail
    return k


def _flatten_ws(ws: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """把 world_state 归一为单层平铺字典（嵌套展开 + 前缀剥离）。"""
    out: Dict[str, Any] = {}
    if not isinstance(ws, dict):
        return out
    for k, val in ws.items():
        key = _norm_key(k)
        if isinstance(val, dict) and key not in _NESTED_EXCEPTION:
            for kk, vv in val.items():
                out[_norm_key(kk)] = vv
            continue
        out[key] = val
    return out


def _apply_invariants_and_gates(ws: Dict[str, Any], issues: List[str]):
    """强制执行物理守恒律与安全门，彻底杜绝假绿（False Pass）。"""
    # 1. 安全系数与强度闸门检查（幂等：字面已正确时静默放行）
    # 历史缺陷：原实现按 ("safety_factor", "FOS") 逐个别名各跑一遍闸门，两轮各自改写
    # fos_gate / status，导致「求解器复算 safety_factor=1.23」被紧随其后的
    # 「模型自填 FOS=1.5」覆盖回 pass（典型假绿），且同一条响应报出两条互相矛盾的
    # issue（既说 FOS=1.23 熔断、又说字面与 FOS=1.50 不一致）。
    # 修复口径：canonical 键唯一优先，别名只在 canonical 缺位时迁移；数值冲突时
    # 以 canonical 为准并显式记账（禁止静默丢弃）。
    fos_val: Optional[float] = None
    if isinstance(ws.get("safety_factor"), (int, float)):
        fos_val = float(ws["safety_factor"])
        alias = ws.pop("FOS", None)
        if isinstance(alias, (int, float)) and abs(float(alias) - fos_val) > max(1e-9, abs(fos_val) * 1e-3):
            issues.append(
                f"别名 FOS={float(alias):.4g} 与复算 safety_factor={fos_val:.4g} 冲突，以 safety_factor 为准"
            )
    elif isinstance(ws.get("FOS"), (int, float)):
        fos_val = float(ws["FOS"])
        ws["safety_factor"] = fos_val
        ws.pop("FOS", None)

    if fos_val is not None:
        hot = fos_val < 1.5
        want_gate = "fail" if hot else "pass"
        want_status = "FAIL (FOS < 1.5)" if hot else "PASS (FOS >= 1.5)"
        changed = False
        if ws.get("fos_gate") != want_gate:
            ws["fos_gate"] = want_gate
            changed = True
        if "status" in ws and ws["status"] != want_status:
            ws["status"] = want_status
            changed = True
        # 只有真的改了字面才记 issue。原实现无条件 append，
        # 导致模型已经写出 "FAIL (FOS < 1.5)" + fos_gate=fail 的正确响应
        # 也被判 corrected——契约形态核验里全是假阳性，训练数据被反向污染。
        if changed and hot:
            issues.append(f"安全系数 FOS={fos_val:.2f} < 1.5，触发安全熔断，强制判定为 FAIL")
        elif changed:
            issues.append(f"安全门字面与 FOS={fos_val:.2f} 不一致，已归一为 {want_status}")

    # 2. 几何切除体积守恒检查
    if "delta_volume_mm3" in ws and isinstance(ws["delta_volume_mm3"], (int, float)):
        dv = float(ws["delta_volume_mm3"])
        if dv < 0:
            ws["volume_conservation"] = "pass"
        elif dv > 0:
            ws["volume_conservation"] = "fail"
            issues.append(f"切除特征体积 delta_volume_mm3={dv} 违背守恒律（必须为负）")

    # 3. 物理非负量保真检查
    for pos_key in ("material_removed_mm3", "resulting_mass_g", "volume_mm3", "mass_g"):
        if pos_key in ws and isinstance(ws[pos_key], (int, float)):
            if ws[pos_key] < 0:
                issues.append(f"物理量 {pos_key}={ws[pos_key]} 不能为负")
                ws[pos_key] = abs(ws[pos_key])


# ---------------------------------------------------------------------------
# 结果结构
# ---------------------------------------------------------------------------
def _invalid_reason(scenario: Optional[Dict[str, Any]]) -> str:
    """从 scenario.inputs 推断 invalid 理由：缺什么就写什么，禁止泛泛而谈。"""
    inputs = (scenario or {}).get("inputs") or {}
    missing = [k for k, v in inputs.items() if v is None]
    if not missing:
        missing = [k for k in ("material", "rho") if k not in inputs]
    label = {"material": "material", "rho": "material_density",
             "V": "feature_volume", "stock_vol": "stock_volume"}
    if not missing:
        return "invalid_input: 题面参数不足或不满足求解前置条件，拒绝给数值"
    return "missing_material: " + ", ".join(label.get(k, str(k)) for k in missing)


@dataclass
class GuardResult:
    action: str                       # accept | corrected | rejected | escalate
    layers_hit: List[str] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)
    corrected: Optional[Dict[str, Any]] = None
    reference: Optional[Dict[str, Any]] = None
    provenance: str = ""              # model | solver | hybrid

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class Guard:
    def __init__(self, tool_whitelist: Optional[Set[str]] = None,
                 strict_grounding: bool = True, evidence_required: bool = True):
        self.tools = tool_whitelist if tool_whitelist is not None else load_tool_whitelist()
        self.strict_grounding = strict_grounding
        self.evidence_required = evidence_required

    # L0 ------------------------------------------------------------------
    def ghost_tools(self, obj: Any) -> List[str]:
        """返回对象中出现的、不在白名单内的工具名（编造即幻觉，一票否决）。

        不能只认 cadcam_ 前缀——编造名也可能是 arbitrary-string 这类任意串，
        所以同时检查显式工具字段的值。
        """
        if not isinstance(obj, dict):
            return []
        raw = json.dumps(obj, ensure_ascii=False)
        used = set(re.findall(r"\b(cadcam_[a-z0-9_]+)\b", raw))
        for k in ("tool", "name", "function", "tool_name"):
            v = obj.get(k)
            if isinstance(v, str) and v.strip():
                used.add(v.strip())
        return sorted(u for u in used if u not in self.tools)

    def l0_shape(self, obj: Any) -> List[str]:
        issues: List[str] = []
        raw = json.dumps(obj, ensure_ascii=False) if obj is not None else ""
        if not isinstance(obj, dict):
            return ["顶层不是 JSON 对象"]
        bad = (set(obj) & FORBIDDEN_TOP_KEYS)
        if bad:
            issues.append("禁止的顶层键: " + ",".join(sorted(bad)))
        unknown = set(obj) - ALLOWED_TOP_KEYS
        if unknown:
            issues.append("未登记的顶层键: " + ",".join(sorted(unknown)))
        # 工具名白名单（一票否决项：幻觉函数名率=0）。
        # 不能只认 cadcam_ 前缀——编造名也可能是 nonexistent-model-xyz 这类任意串，
        # 所以同时检查显式工具字段的值。
        ghost = self.ghost_tools(obj)
        if ghost:
            issues.append("不存在的工具名: " + ",".join(ghost))
        if "vba_code" in raw:
            issues.append("字段 vba_code 不在任何 schema 中")
        return issues

    # L3 ------------------------------------------------------------------
    def l3_evidence(self, text: str) -> List[str]:
        if not self.evidence_required:
            return []
        s = text or ""
        # 只查散文里的宣称；JSON 字段值（如 "autodiff":"red"、
        # "volume_conservation":"pass"）是合法结果，不是「宣称已验证」。
        a, b = s.find("{"), s.rfind("}")
        if a >= 0 and b > a:
            s = s[:a] + " " + s[b + 1:]
        claims = [p for p in CLAIM_PATTERNS if re.search(p, s)]
        if not claims:
            return []
        has_receipt = any(m in (text or "") for m in EVIDENCE_MARKERS)
        return [] if has_receipt else ["宣称已验证/PASS 但无执行回执（execution receipt）"]

    # 主入口 ---------------------------------------------------------------
    def run(self, response_text: str, prompt: str = "",
            scenario: Optional[Dict[str, Any]] = None,
            tol_rel: float = 0.08,
            execution_receipt: Optional[str] = None) -> GuardResult:
        obj, err = parse_json_candidate(response_text)
        issues: List[str] = []
        layers: List[str] = []

        # 裸字段世界状态归一化：模型常输出 {"field": value} 而非 {"world_state": {...}}。
        # 只要不含任一允许的结构键(world_state/invalid/...)与禁止键(tool/arguments/...)，
        # 即视为裸 world_state 字段并归一化为契约包裹，避免误杀有效内容。
        if isinstance(obj, dict) and obj:
            _has_allowed = any(k in ALLOWED_TOP_KEYS for k in obj)
            _has_forbidden = any(k in FORBIDDEN_TOP_KEYS for k in obj)
            tool_obj = ("tool" in obj) or ("arguments" in obj)
            wm_prompt = ("【场景】" in (prompt or "")) or ("world_state" in (prompt or ""))
            # 工具调用题不得被世界模型契约改写成 world_state。
            if tool_obj and not wm_prompt:
                # 工具/命令类响应不走世界模型数值校验，但绝不等于免检：
                # 编造工具名属一票否决项，必须在早退前拦下（否则幻觉函数名直接放行）。
                ghost = self.ghost_tools(obj)
                if ghost:
                    return GuardResult(action="rejected", layers_hit=["L0_SHAPE"],
                                       issues=["不存在的工具名: " + ",".join(ghost)],
                                       provenance="toolcall")
                return GuardResult(action="accept", corrected=None, provenance="toolcall")
            if not _has_allowed and not _has_forbidden:
                obj = {"world_state": obj}

        # 场景推断：若调用侧未显式给出，则尝试从用户 prompt 自动抽取
        if not scenario:
            scenario = infer_scenario_from_prompt(prompt)

        # 非法输入族闸门：题面缺参/越界时只允许契约形态（world_state=null + invalid=true），
        # 一旦模型硬算数字，直接拒，绝不放行编造物性/负去除量。
        if scenario and scenario.get("task") == "invalid":
            if isinstance(obj, dict) and obj.get("invalid") is True and obj.get("world_state") is None:
                return GuardResult(
                    action="accept", layers_hit=layers + ["L2_INVALID"],
                    corrected={"world_state": None, "invalid": True,
                               "reason": str(obj.get("reason") or "")},
                    provenance="invalid_gate")
            # 缺口 C：只拒不改会让下游拿到「硬算出来的错值」或干脆空响应。
            # 正确做法是主动改写为契约形态，让消费侧直接得到可判分的 invalid 结构。
            reason = _invalid_reason(scenario)
            issues.append("非法输入题未按契约报错，已改写为 world_state=null + invalid=true")
            layers.append("L2_INVALID")
            return GuardResult(action="corrected", layers_hit=layers, issues=issues,
                               corrected={"world_state": None, "invalid": True,
                                          "reason": reason},
                               provenance="invalid_gate")

        # 先派生求解器参考值：它既是 L2 的真值，也是数字接地的合法出处
        ref = None
        if scenario and scenario.get("task"):
            try:
                ref = wm_verifier.recompute(scenario) or None
            except Exception:
                ref = None
        ref_nums = {_canon(float(v)) for v in (ref or {}).values()
                    if isinstance(v, (int, float)) and not isinstance(v, bool)}

        if obj is None:
            issues.append("响应不可解析为 JSON: " + str(err))
            layers.append("L0_SHAPE")
        else:
            s0 = self.l0_shape(obj)
            if s0:
                issues.extend(s0)
                layers.append("L0_SHAPE")

        if self.strict_grounding:
            der = obj.get("derivation") if isinstance(obj, dict) else None
            g1 = grounding_issues(prompt, response_text or "", der,
                                  extra_allowed=ref_nums)
            if g1:
                issues.extend(g1[:6])
                layers.append("L1_GROUND")

        if self.evidence_required and execution_receipt:
            # 有回执时追加到文本里，证据门自然放行
            response_text = (response_text or "") + " " + execution_receipt
        e3 = self.l3_evidence(response_text or "")
        if e3:
            issues.extend(e3)
            layers.append("L3_EVIDENCE")

        # L1 量纲 + L2 求解器复算：只要有结构化场景就执行
        ws = None
        if isinstance(obj, dict):
            ws = obj.get("world_state", obj)
            if not isinstance(ws, dict):
                ws = None
        if scenario and scenario.get("task"):
            if not ref:
                # P-17 修复（假绿通道）：ref 为空时原实现直接跳过整个 L2 求解器比对，
                # 落到"无结构化场景"分支返回 accept —— 表面通过、实则一个字都没校验。
                # 空 ref 的真实来源有两类：scenario 参数不全，或 wm_verifier 的量纲/CSG
                # 能力不可用；后者以前静默吞掉，评测统计里完全看不出来。
                # 现在显式记 L2_NO_REF，让"通过"可追溯到"未校验"，不再与"校验通过"混淆。
                issues.append("L2 无参考值（scenario 参数不全或求解器能力不可用），"
                              "本次未做数值复算校验，结论不可视为已接地")
                layers.append("L2_NO_REF")
            if ref:
                # 关键顺序：先平铺归一，再做量纲检查与求解器比对。
                # 若在归一并前比对，嵌套子对象里的错值（如 world_state.mass_props.volume_mm3）
                # 会因顶层键不存在而逃过 _cmp_numeric，随后又被求解器值覆盖，
                # 造成 action=accept 却内容已改的静默改写（审计不可追溯）。
                ws_flat = _flatten_ws(ws) if isinstance(ws, dict) else {}
                if isinstance(ws, dict) and ws_flat != ws:
                    issues.append("world_state 存在嵌套子对象或前缀同义键，已平铺归一"
                                  "（契约要求字段单层，唯一例外 design.features）")
                    if "L0_SHAPE" not in layers:
                        layers.append("L0_SHAPE")
                dim = wm_verifier.dimension_check(ws_flat, scenario)
                if dim:
                    issues.extend(dim)
                    if "L1_GROUND" not in layers:
                        layers.append("L1_GROUND")
                if ws is None:
                    issues.append("缺 world_state，数值改由求解器全量给出")
                    layers.append("L2_SOLVER")
                else:
                    mism = wm_verifier._cmp_numeric(ws_flat, ref, tol=tol_rel)
                    if mism:
                        issues.append("求解器复算超差: " + json.dumps(
                            mism[:4], ensure_ascii=False))
                        layers.append("L2_SOLVER")
                # 无论草案好坏，数值一律以确定性求解器为准——这是本方案的核心。
                # 写回前已双侧平铺归一：嵌套里的错值不会再以子对象形式残留，
                # 也不产生 `mass_props.xxx` 这类前缀同义键（缺口 B 根因）。
                # 顶层规格子树（design / process_plan / adaptation / correction）
                # 此前被整块丢弃：Guard.run 只取 world_state 内层，交付 payload
                # 里 outer_dia_mm / bore_dia_mm / bolt_count 等规格键全部消失，
                # 同一条设计答案「原生判 PASS、护栏后判 FAIL」。用契约唯一口径并入，
                # 只接纳契约登记过的键，world_state 原有值优先。
                corrected = (wm_contract.merge_nested_top(obj, ws_flat)
                             if wm_contract is not None else ws_flat)
                corrected.update(_flatten_ws(ref))
                _apply_invariants_and_gates(corrected, issues)
                result = GuardResult(
                    action="corrected" if (issues or ws is None) else "accept",
                    layers_hit=layers, issues=issues, corrected=corrected,
                    reference=ref,
                    provenance="solver" if ws is None else "hybrid")
                return result

        # 无结构化场景时：检查是否输出 derivation 推导式，由解析器现算重构
        if isinstance(obj, dict) and isinstance(obj.get("derivation"), dict):
            der = obj["derivation"]
            evaluated_count = 0
            ws = _flatten_ws(ws)
            for field_name, expr in der.items():
                if isinstance(expr, str) and expr.strip():
                    try:
                        from virtu_eval.audit_case_arithmetic import eval_expr
                        val, err_expr = eval_expr(expr)
                        if err_expr == "" and val is not None and math.isfinite(val):
                            canonical = _norm_key(field_name)
                            orig_val = ws.get(canonical)
                            ws[canonical] = round(val, 4)
                            evaluated_count += 1
                            if orig_val is not None:
                                try:
                                    if abs(float(orig_val) - float(val)) > max(0.01, abs(float(val)) * tol_rel):
                                        issues.append(f"字段 {canonical}={orig_val} 与 derivation 复算 {ws[canonical]} 不一致，已更正")
                                        if "L2_SOLVER" not in layers:
                                            layers.append("L2_SOLVER")
                                except Exception:
                                    pass
                    except Exception:
                        pass
            if evaluated_count > 0:
                _apply_invariants_and_gates(ws, issues)
                action_name = "corrected" if (issues or "L2_SOLVER" in layers) else "accept"
                return GuardResult(
                    action=action_name,
                    layers_hit=layers,
                    issues=issues,
                    corrected=ws,
                    reference=dict(ws),
                    provenance="derivation_solver",
                )

        # 无结构化场景与推导式：只能做形状/接地/证据门，不能编造数值
        # P-17 补充：L2_NO_REF 只是"没校验"的标记，不是缺陷，不能据此判 rejected；
        # 但保留 layer + issue，让下游能把这批 accept 单独统计出来。
        hard = [i for i in issues if "L2 无参考值" not in i]
        if hard:
            return GuardResult(action="rejected", layers_hit=layers, issues=issues,
                               provenance="model")
        return GuardResult(action="accept", layers_hit=layers,
                           corrected=obj if isinstance(obj, dict) else None,
                           provenance="no_reference" if "L2_NO_REF" in layers else "model")


# ---------------------------------------------------------------------------
# 自检（含无缺陷对照：正确响应不得被误杀）
# ---------------------------------------------------------------------------
def selftest() -> int:
    g = Guard()
    scen = {"task": "roughness", "inputs": {"f": 0.12, "r_eps": 0.8}}
    ref = wm_verifier.recompute(scen)
    prompt = "【场景】f=0.12 mm/rev，r_eps=0.8 mm。计算 Ra=1000*f^2/(8*r_eps)。"
    ok = True

    def check(tag: str, cond: bool, detail: str = ""):
        nonlocal ok
        ok &= bool(cond)
        print(f"[{'PASS' if cond else 'FAIL'}] {tag}{(' -> ' + detail) if detail else ''}")

    # 1 无缺陷对照：求解器 gold 原样，护栏必须 accept
    clean = json.dumps({"world_state": ref}, ensure_ascii=False)
    r = g.run(clean, prompt, scen)
    check("clean reference accepted", r.action == "accept", r.action)

    # 2 数字幻觉：2.25 -> 1.8（用默认 r_eps=1.0 代入）必须被拦且纠正
    bad = json.dumps({"world_state": {"surface_roughness_ra_um": 1.8}}, ensure_ascii=False)
    r = g.run(bad, prompt, scen)
    check("numeric hallucination caught", "L2_SOLVER" in r.layers_hit,
          ",".join(r.layers_hit))
    check("numeric hallucination corrected",
          abs(r.corrected["surface_roughness_ra_um"] - ref["surface_roughness_ra_um"]) < 1e-9,
          str(r.corrected))

    # 3 格式竞争：{"tool": ...} 必须被 L0 拦
    toolish = json.dumps({"tool": "cadcam_virtu", "arguments": {}})
    r = g.run(toolish, prompt, scen)
    check("format-competition tool key caught", "L0_SHAPE" in r.layers_hit,
          ",".join(r.layers_hit))

    # 4 编造工具名
    ghost = json.dumps({"world_state": ref, "tool": "cadcam_hallucinated_api"})
    r = g.run(ghost, prompt, scen)
    check("ghost tool name caught", any("不存在的工具名" in i for i in r.issues),
          ";".join(r.issues)[:120])

    # 5 伪造验证结论
    fake = json.dumps({"world_state": ref, "verification": {"source": "sandbox"}})
    fake += " 沙箱仿真校验 100% PASS，多智能体总耗时 3.2s"
    r = g.run(fake, prompt, scen)
    check("fabricated verification caught", "L3_EVIDENCE" in r.layers_hit,
          ",".join(r.layers_hit))

    # 5b 有执行回执时不得误杀
    r = g.run(clean + " execution_id=RUN-2026-1104-001", prompt, scen)
    check("clean + receipt still accepted", r.action == "accept", r.action)

    # 6 量纲错 1000 倍
    scen2 = {"task": "removal", "inputs": {"doc": 2.0, "woc": 5.0, "vf": 400.0,
                                            "L": 100.0, "rho": 7.85e-3,
                                            "stock_vol": 200000.0}}
    ref2 = wm_verifier.recompute(scen2)
    ws2 = dict(ref2, resulting_mass_g=ref2["resulting_mass_g"] * 1000.0)
    r = g.run(json.dumps({"world_state": ws2}), "毛坯 200x150x50 密度 7.85 g/cm3", scen2)
    check("1000x dimension error caught", any("量纲" in i for i in r.issues),
          ";".join(r.issues)[:110])

    # 7 无响应 / 纯散文：不编造，但可用求解器兜底
    r = g.run("根据经验，大约是 1.8 左右。", prompt, scen)
    check("unparseable response still yields solver truth",
          r.action == "corrected" and abs(r.corrected["surface_roughness_ra_um"] - 2.25) < 1e-9,
          r.action)

    # 8 derivation 推导式重算：算式 (120)*(80)*(30-25) 纠正模型幻觉数字 6000 -> 48000
    der_resp = json.dumps({
        "world_state": {"material_removed_mm3": 6000, "delta_volume_mm3": -6000},
        "derivation": {
            "material_removed_mm3": "(120)*(80)*(30-25)",
            "delta_volume_mm3": "-((120)*(80)*(30-25))"
        }
    })
    r_der = g.run(der_resp, "铣削毛坯 120x80x30 到 120x80x25")
    check("derivation recomputes exact volume",
          r_der.action == "corrected" and abs(r_der.corrected["material_removed_mm3"] - 48000.0) < 1e-6,
          str(r_der.corrected))

    # 9 安全系数熔断门：FOS=1.17 < 1.5 严禁假绿 PASS
    fea_prompt = "黄铜H62构件，屈服强度 Sy=200 MPa，FEA 应力 σ=171.3 MPa。预测安全系数并判定 FOS≥1.5。"
    fake_pass = json.dumps({
        "world_state": {"safety_factor": 1.768, "status": "PASS (FOS >= 1.5)"}
    })
    r_fea = g.run(fake_pass, fea_prompt)
    check("fake FOS pass prevented by solver gate",
          r_fea.action == "corrected" and r_fea.corrected.get("fos_gate") == "fail" and abs(r_fea.corrected["safety_factor"] - (200.0/171.3)) < 0.05,
          str(r_fea.corrected))

    # 10 场景推断：题面「安全平面 Z=」写法必须能还原参数（B-3 回归）
    sc_c = infer_scenario_from_prompt(
        "分析一段 FANUC 加工程序：安全平面 Z=29.3 mm，某 G00 快速移动段最低 "
        "Z=18.1 mm，毛坯顶面 Z=5.3 mm。预测碰撞/过切风险与 Auto-Diff 颜色。")
    check("scenario inferred from 'Z=' collision prompt",
          sc_c is not None and sc_c.get("task") == "collision"
          and [sc_c["inputs"][k] for k in ("z_safe", "z_min_rapid", "stock_top")]
          == [29.3, 18.1, 5.3],
          str(sc_c))

    # 11 场景推断：公差链族
    sc_t = infer_scenario_from_prompt(
        "尺寸链含 2 个组成环，半公差分别为 [0.061, 0.082] mm（基本尺寸 25.0 mm）。"
        "孔轴偏差：上偏差 +0.006 mm，下偏差 -0.012 mm。用极值法与 RSS 给出半宽。")
    check("scenario inferred for tolerance",
          sc_t is not None and sc_t.get("task") == "tolerance"
          and sc_t["inputs"]["tols"] == [0.061, 0.082]
          and abs(sc_t["inputs"]["upper_dev"] - 0.006) < 1e-12,
          str(sc_t))

    # 12 场景推断：质量属性族（box 与 cylinder 两种）
    sc_m = infer_scenario_from_prompt(
        "预测box（长 l=120.0 mm，宽 w=80.0 mm，高 h=50.0 mm）的质量属性：体积、"
        "质量、质心坐标。材料 45钢。")
    check("scenario inferred for mass_props box",
          sc_m is not None and sc_m.get("task") == "mass_props"
          and sc_m["inputs"]["params"] == {"l": 120.0, "w": 80.0, "h": 50.0}
          and abs(sc_m["inputs"]["rho"] - 7.85e-3) < 1e-12,
          str(sc_m))
    sc_m2 = infer_scenario_from_prompt(
        "预测cylinder（半径 r=10.0 mm，高 h=50.0 mm）的质量属性：体积、质量。"
        "材料 铝合金6061。")
    check("scenario inferred for mass_props cylinder",
          sc_m2 is not None and sc_m2.get("task") == "mass_props"
          and sc_m2["inputs"]["params"] == {"r": 10.0, "h": 50.0}
          and abs(sc_m2["inputs"]["rho"] - 2.70e-3) < 1e-12,
          str(sc_m2))

    # 13 非法输入族闸门：契约形态放行，硬算数字必拒（不依赖外部传入 scenario）
    inv_prompt = "未提供材料类型，要求预测去除质量。"
    good_inv = json.dumps({"world_state": None, "invalid": True,
                           "reason": "missing_material: 缺材料类型"},
                          ensure_ascii=False)
    r_inv = g.run(good_inv, inv_prompt)
    check("invalid-family contract form accepted",
          r_inv.action == "accept" and "L2_INVALID" in r_inv.layers_hit, r_inv.action)

    # 14 缺材料却按默认 45 钢硬算 -> 必须拒
    bad_inv = json.dumps({"world_state": {"removed_mass_g": 35.15}}, ensure_ascii=False)
    r_inv2 = g.run(bad_inv, inv_prompt)
    check("invalid-family fabricated numbers rewritten to contract",
          r_inv2.action == "corrected"
          and r_inv2.corrected.get("world_state", "missing") is None
          and r_inv2.corrected.get("invalid") is True
          and "L2_INVALID" in r_inv2.layers_hit,
          str(r_inv2.corrected))

    # 15 缺口 B 回归：嵌套子对象必须就地覆盖并平铺归一，不得残留前缀同义键
    sc_mp = {"task": "mass_props",
             "inputs": {"parts": [1000.0, 2000.0], "rho": 7.85e-3}}
    nest = json.dumps({"world_state": {
        "mass_props": {"volume_mm3": 355958.88, "mass_g": 961.14},
        "material": "45钢"}}, ensure_ascii=False)
    r_mp = g.run(nest, "装配体 45钢", sc_mp)
    check("nested subobject flattened and overwritten in place",
          abs(float(r_mp.corrected.get("volume_mm3", -1)) - 3000.0) < 1e-6
          and "mass_props" not in r_mp.corrected
          and not any(k.startswith("mass_props.") for k in r_mp.corrected),
          str(r_mp.corrected))

    # 16 缺口 B 变体：带前缀平铺键必须剥成 canonical 键
    pre = json.dumps({"world_state": {"mass_props.volume_mm3": 999.0,
                                      "mass_props.mass_g": 1.0}}, ensure_ascii=False)
    r_pre = g.run(pre, "装配体 45钢", sc_mp)
    check("prefixed keys stripped to canonical",
          "mass_props.volume_mm3" not in r_pre.corrected
          and abs(float(r_pre.corrected.get("volume_mm3", -1)) - 3000.0) < 1e-6,
          str(r_pre.corrected))

    # 17 缺口 A 回归：模型漏 mrr 时求解器必须补全（ap/ae 别名 + 体积差口径）
    sc_rm = {"task": "removal",
             "inputs": {"ap": 2.0, "ae": 5.0, "vf": 400.0, "rho": 7.85e-3,
                        "stock_vol": 300000.0, "V": 241153.9}}
    r_rm = g.run(json.dumps({"world_state": {"material_removed_mm3": 58846.1}},
                            ensure_ascii=False), "铣削去除量", sc_rm)
    check("missing mrr filled by solver",
          abs(float(r_rm.corrected.get("mrr_mm3_per_min", -1)) - 4000.0) < 1e-6
          and abs(float(r_rm.corrected.get("material_removed_mm3", -1)) - 58846.1) < 1e-2
          and abs(float(r_rm.corrected.get("removed_mass_g", -1)) - 58846.1 * 7.85e-3) < 1e-2,
          str(r_rm.corrected))

    print("\n[selftest]", "ALL PASS" if ok else "SOME FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    print(__doc__)
