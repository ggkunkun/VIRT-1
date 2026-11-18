
# -*- coding: utf-8 -*-
"""缺参 fail-closed 探针（防"缺参 → 不给参考值 → 上游 accept 假绿"）。

2026-11-08 二轮：wm_verifier.recompute 改为查表显式识别缺参，不再靠
KeyError 兜底。本探针锁定行为契约——每族故意少给一个必需参数，模型给出
"看起来合理"的 world_state，断言 verify 绝不 accept（必须 escalate 或 reject）。
断言方向：假绿必须为 0，任何一族回到 accept 即判红。
"""
import sys, json
sys.path.insert(0, r"D:\Virtu模型\scripts")
import wm_verifier as V

# 缺参场景：每组故意少给一个必需参数，模型给出"看起来合理"的 world_state
CASES = [
 ("roughness",     {"f": 0.1},                                   {"surface_roughness_ra_um": 1.6}),
 ("fea_fos",       {"Sy": 800.0},                                 {"safety_factor": 2.0, "fos_gate": "pass"}),
 ("collision",     {"z_safe": 10.0, "z_min_rapid": 12.0},         {"collision_risk": "none", "gouge": False}),
 ("tolerance",     {"tols": [0.05, 0.05]},                        {"closed_loop_worstcase_halfwidth_mm": 0.1}),
 ("process",       {"D": 50.0, "L": 100.0, "ap": 1.0, "f": 0.2},  {"spindle_rpm": 1200.0}),
 ("adapt_machine", {"vc": 150.0, "n_max": 8000.0},                {"required_spindle_rpm": 955.0, "within_limit": True}),
]
bad = 0
for task, inputs, ws in CASES:
    scn = {"task": task, "inputs": inputs}
    ref = V.recompute(scn)
    res = V.verify({"world_state": ws}, scn)
    action = res.get("action") if isinstance(res, dict) else res
    ok = res.get("ok") if isinstance(res, dict) else None
    fake_green = (ref == {} and ok is True and action == "accept" and task != "invalid")
    bad += 1 if fake_green else 0
    print(f"  {task:<14} ref={'空' if not ref else ref} ok={ok} action={action} {'<< 假绿' if fake_green else ''}")
print(f"[probe] 缺参假绿 {bad}/{len(CASES)}")
sys.exit(1 if bad else 0)
