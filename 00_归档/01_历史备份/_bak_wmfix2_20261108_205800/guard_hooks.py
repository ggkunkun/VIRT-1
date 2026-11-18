#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
guard_hooks.py — 推理时护栏高级封装（生成侧输出层调用入口）
============================================================
把 `anti_hallucination_guard.Guard` 的四层拦截（L0 形状 / L1 量纲定律 /
L2 求解器复算 / L3 证据门）封装成生成侧可直接调用的后处理 hook。

设计目标：
  - 生成侧只管「调模型 -> 拿 raw 文本 -> 调本模块 -> 拿最终 world_state」。
  - 对结构化 world_state 数值做 correct 重写、对量纲荒谬/伪造结论做 reject/escalate。
  - 内置 E6 场景绑定防护：若 scenario.inputs 与 prompt 抽取数字不一致，明确标记
    风险（护栏可信度上界 = 场景/参数绑定可信度）。
  - 不扫描自由文本全文（E2 结论：全文数字接地在自由文本/代码场景不可用），
    只校验结构化 JSON 数值字段。

用法：
  from guard_hooks import apply_guard, guard_world_state, check_scenario_binding
  out = apply_guard(raw_response, prompt=u, scenario={"task":"roughness","inputs":{"f":0.12,"r_eps":0.8}})
  world_state = out["final_world_state"]   # 已是护栏纠正后的 dict 或原 parse
  if out["action"] in ("rejected","escalate"):  # 走人工/重生成分支
      ...
"""
from __future__ import annotations

import os
import re
import sys
import json
from typing import Any, Dict, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from anti_hallucination_guard import (  # noqa: E402
    Guard,
    GuardResult,
    parse_json_candidate,
    numbers_in,
)

DEFAULT_TOL_REL = 0.08  # 8% 相对容差，与 wm_verifier / eval_worldmodel 一致


# ---------------------------------------------------------------------------
# E6 场景绑定防护：护栏可信度上界 = 场景/参数绑定的可信度
# ---------------------------------------------------------------------------
def check_scenario_binding(prompt: str, scenario: Optional[Dict[str, Any]]) -> Optional[str]:
    """若 scenario.inputs 中的数字未全部出现在 prompt 中，说明调用侧可能把
    参数绑错（如把 r_eps=0.8 绑成默认值 1.0）。此时 L2 复算会用错输入，
    护栏可能 confidently wrong。返回风险说明，否则 None。"""
    if not scenario or not isinstance(scenario.get("inputs"), dict):
        return None
    prompt_nums = {round(float(x), 6) for x in numbers_in(prompt or "")}
    mismatch = []
    for k, v in scenario["inputs"].items():
        if isinstance(v, (int, float)):
            if round(float(v), 6) not in prompt_nums:
                mismatch.append(f"{k}={v}")
    if mismatch:
        return ("场景绑定风险：inputs 中的 " + ",".join(mismatch) +
                " 未出现在 prompt 文本中，L2 复算将使用这些参数，护栏可信度上界受限。"
                "请在上游确保 scenario 与 prompt 同源。")
    return None


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------
def guard_world_state(
    raw_response: str,
    prompt: str = "",
    scenario: Optional[Dict[str, Any]] = None,
    tol_rel: float = DEFAULT_TOL_REL,
    require_evidence: bool = True,
    execution_receipt: Optional[str] = None,
) -> GuardResult:
    """四层护栏：直接委托 Guard.run。"""
    g = Guard(evidence_required=require_evidence)
    return g.run(raw_response, prompt, scenario, tol_rel, execution_receipt)


def apply_guard(
    raw_response: str,
    prompt: str = "",
    scenario: Optional[Dict[str, Any]] = None,
    tol_rel: float = DEFAULT_TOL_REL,
    require_evidence: bool = True,
    execution_receipt: Optional[str] = None,
) -> Dict[str, Any]:
    """生成侧输出层标准后处理。返回可直接消费的结构：
      - action: accept | corrected | rejected | escalate
      - final_world_state: 纠正后的 dict（rejected/escalate 时可能为 None）
      - issues / layers_hit / provenance: 诊断
      - binding_risk: E6 场景绑定风险提示（None 表示无）
    用法：把生成侧原来的 `pred = extract_json(raw)` 替换为
      `out = apply_guard(raw, prompt, scenario); pred = out["final_world_state"]`。
    """
    gr = guard_world_state(raw_response, prompt, scenario, tol_rel, require_evidence, execution_receipt)
    obj, _err = parse_json_candidate(raw_response)
    # 优先用护栏纠正/归一化后的结果（corrected 总是 world_state 包裹，含裸字段归一化）；
    # 仅当 corrected 缺失且解析成功时回退到原 parse。
    if isinstance(gr.corrected, dict):
        final = gr.corrected
    elif gr.action == "accept" and isinstance(obj, dict):
        final = obj
    else:
        final = obj  # rejected/escalate：保留原 parse（可能 None），由上游决定
    return {
        "action": gr.action,
        "issues": gr.issues,
        "layers_hit": gr.layers_hit,
        "provenance": gr.provenance,
        "final_world_state": final,
        "binding_risk": check_scenario_binding(prompt, scenario),
    }


# ---------------------------------------------------------------------------
# 自检
# ---------------------------------------------------------------------------
def selftest() -> int:
    ok = 0
    total = 0

    def check(name, cond):
        nonlocal ok, total
        total += 1
        if cond:
            ok += 1
            print(f"[PASS] {name}")
        else:
            print(f"[FAIL] {name}")

    # 1) 数字幻觉被纠正
    raw = json.dumps({"world_state": {"surface_roughness_ra_um": 112.5}})
    sc = {"task": "roughness", "inputs": {"f": 0.12, "r_eps": 0.8}}
    out = apply_guard(raw, prompt="f=0.12, r_eps=0.8, Ra=1000*f^2/(8*r_eps)", scenario=sc)
    check("numeric hallucination -> corrected", out["action"] == "corrected")
    check("corrected value ~2.25", abs((out["final_world_state"] or {}).get("surface_roughness_ra_um", 0) - 2.25) < 1e-6)

    # 2) 干净输出被接受且无风险
    clean = json.dumps({"world_state": {"surface_roughness_ra_um": 2.25}})
    out = apply_guard(clean, prompt="f=0.12, r_eps=0.8", scenario=sc)
    check("clean -> accept", out["action"] == "accept")
    check("clean no binding risk", out["binding_risk"] is None)

    # 3) 幽灵工具名被拦
    ghost = json.dumps({"tool": "cadcam_hallucinated_api"})
    out = apply_guard(ghost, prompt="", scenario=None)
    check("ghost tool -> rejected", out["action"] == "rejected")

    # 4) 伪造验证结论被证据门拦
    forged = "本报告 100% PASS，auto-diff 验证通过，实测全部达标。"
    out = apply_guard(forged, prompt="", scenario=None)
    check("forged claim -> flagged (rejected/escalate)", out["action"] in ("rejected", "escalate"))

    # 5) E6 场景绑定风险检测
    wrong_sc = {"task": "roughness", "inputs": {"f": 0.12, "r_eps": 1.0}}  # 与 prompt 不一致
    out = apply_guard(clean, prompt="f=0.12, r_eps=0.8", scenario=wrong_sc)
    check("E6 scenario binding risk detected", out["binding_risk"] is not None)

    print(f"\n[selftest] {ok}/{total} PASS")
    return 0 if ok == total else 1


if __name__ == "__main__":
    raise SystemExit(selftest())
