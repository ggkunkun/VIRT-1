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

# 顶层键白名单：契约规定 world_state 是唯一合法顶层业务键
ALLOWED_TOP_KEYS: Set[str] = {
    "world_state", "derivation", "correction", "verification",
    "design", "invalid", "reason", "fos_gate", "volume_conservation",
    "autodiff", "evidence",
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
def infer_scenario_from_prompt(prompt: str) -> Optional[Dict[str, Any]]:
    """从用户提示词直接推断标准工程物理场景与参数输入。"""
    if not prompt:
        return None
    p = str(prompt)

    # 1. fea_fos: 屈服强度与应力
    m_sy = re.search(r"(?:屈服强度|Sy|S_y)\s*[=＝:：]?\s*(\d+(?:\.\d+)?)", p, re.I)
    m_sig = re.search(r"(?:von\s*Mises|σ_vm|σ|sigma|峰值应力|应力)\s*[=＝:：]?\s*(\d+(?:\.\d+)?)", p, re.I)
    if m_sy and m_sig:
        return {"task": "fea_fos", "inputs": {"Sy": float(m_sy.group(1)), "sigma": float(m_sig.group(1))}}

    # 2. roughness: 进给量与刀尖圆弧
    m_f = re.search(r"(?<![a-zA-Z])f\s*[=＝:：]?\s*(\d+(?:\.\d+)?)", p)
    m_reps = re.search(r"(?:r_eps|刀尖圆弧|r_ε)\s*[=＝:：]?\s*(\d+(?:\.\d+)?)", p)
    if m_f and m_reps:
        return {"task": "roughness", "inputs": {"f": float(m_f.group(1)), "r_eps": float(m_reps.group(1))}}

    # 3. geom_delta: 通孔/切除体积与切除前体积
    m_feat = re.search(r"(?:特征体积|通孔体积|切除体积)\s*[=＝:：]?\s*(\d+(?:\.\d+)?)", p)
    m_bef = re.search(r"(?:切除前工件体积|before_volume|切除前体积|工件体积)\s*[=＝:：]?\s*(\d+(?:\.\d+)?)", p)
    if m_feat and m_bef:
        return {"task": "geom_delta", "inputs": {"feature_vol": float(m_feat.group(1)), "before": float(m_bef.group(1))}}

    # 4. removal: doc, woc, L, rho, stock_vol
    m_doc = re.search(r"(?:DOC|切削深度|ap)\s*[=＝:：]?\s*(\d+(?:\.\d+)?)", p, re.I)
    m_woc = re.search(r"(?:WOC|切削宽度|ae)\s*[=＝:：]?\s*(\d+(?:\.\d+)?)", p, re.I)
    m_l = re.search(r"(?:L|刀路长度|切削长度)\s*[=＝:：]?\s*(\d+(?:\.\d+)?)", p, re.I)
    m_rho = re.search(r"(?:rho|密度)\s*[=＝:：]?\s*(\d+(?:\.\d+)?)", p, re.I)
    m_stock = re.search(r"(?:stock_vol|毛坯体积)\s*[=＝:：]?\s*(\d+(?:\.\d+)?)", p, re.I)
    m_vf = re.search(r"(?:vf|进给速度)\s*[=＝:：]?\s*(\d+(?:\.\d+)?)", p, re.I)
    if m_doc and m_woc and m_l and m_rho and m_stock:
        rho_val = float(m_rho.group(1))
        if rho_val > 0.1:
            rho_val = rho_val / 1000.0
        return {
            "task": "removal",
            "inputs": {
                "doc": float(m_doc.group(1)),
                "woc": float(m_woc.group(1)),
                "L": float(m_l.group(1)),
                "rho": rho_val,
                "stock_vol": float(m_stock.group(1)),
                "vf": float(m_vf.group(1)) if m_vf else 500.0,
            }
        }

    # 5. collision: z_safe, z_min_rapid, stock_top
    m_zsafe = re.search(r"(?:z_safe|安全高度|安全平面)\s*[=＝:：]?\s*([-+]?\d+(?:\.\d+)?)", p, re.I)
    m_zmin = re.search(r"(?:z_min_rapid|z_min|最低高度|最小z)\s*[=＝:：]?\s*([-+]?\d+(?:\.\d+)?)", p, re.I)
    m_ztop = re.search(r"(?:stock_top|工件顶面|毛坯顶面)\s*[=＝:：]?\s*([-+]?\d+(?:\.\d+)?)", p, re.I)
    if m_zsafe and m_zmin and m_ztop:
        return {
            "task": "collision",
            "inputs": {
                "z_safe": float(m_zsafe.group(1)),
                "z_min_rapid": float(m_zmin.group(1)),
                "stock_top": float(m_ztop.group(1)),
            }
        }

    return None


def _apply_invariants_and_gates(ws: Dict[str, Any], issues: List[str]):
    """强制执行物理守恒律与安全门，彻底杜绝假绿（False Pass）。"""
    # 1. 安全系数与强度闸门检查
    for fos_key in ("safety_factor", "FOS"):
        if fos_key in ws and isinstance(ws[fos_key], (int, float)):
            fos_val = float(ws[fos_key])
            if fos_val < 1.5:
                ws["fos_gate"] = "FOS<1.5_FAIL"
                if "status" in ws:
                    ws["status"] = "FAIL (FOS < 1.5)"
                issues.append(f"安全系数 FOS={fos_val:.2f} < 1.5，触发安全熔断，强制判定为 FAIL")
            else:
                ws["fos_gate"] = "FOS>=1.5_PASS"
                if "status" in ws:
                    ws["status"] = "PASS (FOS >= 1.5)"

    # 2. 几何切除体积守恒检查
    if "delta_volume_mm3" in ws and isinstance(ws["delta_volume_mm3"], (int, float)):
        dv = float(ws["delta_volume_mm3"])
        if dv < 0:
            ws["volume_conservation"] = "pass_cut_negative"
        elif dv > 0:
            ws["volume_conservation"] = "fail_cut_positive"
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
    def l0_shape(self, obj: Any) -> List[str]:
        issues: List[str] = []
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
        raw = json.dumps(obj, ensure_ascii=False)
        used = set(re.findall(r"\b(cadcam_[a-z0-9_]+)\b", raw))
        for k in ("tool", "name", "function", "tool_name"):
            v = obj.get(k)
            if isinstance(v, str) and v.strip():
                used.add(v.strip())
        ghost = {u for u in used if u not in self.tools}
        if ghost:
            issues.append("不存在的工具名: " + ",".join(sorted(ghost)))
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
                return GuardResult(action="accept", corrected=None, provenance="toolcall")
            if not _has_allowed and not _has_forbidden:
                obj = {"world_state": obj}

        # 场景推断：若调用侧未显式给出，则尝试从用户 prompt 自动抽取
        if not scenario:
            scenario = infer_scenario_from_prompt(prompt)

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
            if ref:
                dim = wm_verifier.dimension_check(ws or {}, scenario)
                if dim:
                    issues.extend(dim)
                    if "L1_GROUND" not in layers:
                        layers.append("L1_GROUND")
                if ws is None:
                    issues.append("缺 world_state，数值改由求解器全量给出")
                    layers.append("L2_SOLVER")
                else:
                    mism = wm_verifier._cmp_numeric(ws, ref, tol=tol_rel)
                    if mism:
                        issues.append("求解器复算超差: " + json.dumps(
                            mism[:4], ensure_ascii=False))
                        layers.append("L2_SOLVER")
                # 无论草案好坏，数值一律以确定性求解器为准——这是本方案的核心
                corrected = dict(ws or {})
                corrected.update(ref)
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
            if ws is None:
                ws = {}
            for field_name, expr in der.items():
                if isinstance(expr, str) and expr.strip():
                    try:
                        from virtu_eval.audit_case_arithmetic import eval_expr
                        val, err_expr = eval_expr(expr)
                        if err_expr == "" and val is not None and math.isfinite(val):
                            orig_val = ws.get(field_name)
                            ws[field_name] = round(val, 4)
                            evaluated_count += 1
                            if orig_val is not None:
                                try:
                                    if abs(float(orig_val) - float(val)) > max(0.01, abs(float(val)) * tol_rel):
                                        issues.append(f"字段 {field_name}={orig_val} 与 derivation 复算 {ws[field_name]} 不一致，已更正")
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
        if issues:
            return GuardResult(action="rejected", layers_hit=layers, issues=issues,
                               provenance="model")
        return GuardResult(action="accept", layers_hit=layers,
                           corrected=obj if isinstance(obj, dict) else None,
                           provenance="model")


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
          r_fea.action == "corrected" and r_fea.corrected.get("fos_gate") == "FOS<1.5_FAIL" and abs(r_fea.corrected["safety_factor"] - (200.0/171.3)) < 0.05,
          str(r_fea.corrected))

    print("\n[selftest]", "ALL PASS" if ok else "SOME FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    print(__doc__)
