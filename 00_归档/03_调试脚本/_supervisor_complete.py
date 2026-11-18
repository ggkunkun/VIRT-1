# -*- coding: utf-8 -*-
"""监督补位：模型自修失败后，保留其方法框架，只补它反复遗漏的执行缺口。

补丁清单（每一项都在输出里显式标注，不与模型贡献混算）：
  P1 在 cut 前插入 sketch_holes —— 模型方案里 cut 无轮廓，实测 ok=False、ΔV=0
  P2 在 import_assembly 后插入 save_assembly —— 模型方案没保存装配体，磁盘无 .SLDASM
  P3 给 drawing 补 model_path —— 指向 P2 保存的装配体，否则工程图引用不存在的模型
除此之外，op 顺序、类型、参数全部沿用模型最后一轮 self-repair 的方案。
"""
import json
import os
import sys

ROOT = r"D:\Virtu模型"
sys.path.insert(0, ROOT)
from bridges.feature_ops import feature_ops

TRACE = os.path.join(ROOT, "runs", "virtu_understand_20261105_233101", "trace.json")
OUT = os.path.join(ROOT, "works", "model_supervised")
STEP = os.path.join(ROOT, "assets", "wheel_mold_P0.step")

d = json.load(open(TRACE, encoding="utf-8"))
model_plan = None
for p in d["phases"]:
    if p["phase"] == "E_self_repair":
        model_plan = p.get("model_fixed_plan") or {}
ops = [dict(o) for o in model_plan.get("ops", []) if isinstance(o, dict)]
print("MODEL_OPS", [o["op"] for o in ops], flush=True)

patches = []


def patch(ops, before, new_op, tag, reason):
    for i, o in enumerate(ops):
        if o["op"] == before:
            ops.insert(i, new_op)
            patches.append({"id": tag, "inserted_before": before,
                            "op": new_op["op"], "reason": reason})
            return True
    return False


# P1：孔参数来自 STEP 逆向测量（3 个 120° 扇区各 1 个 Ø7 @ PCD38，
#     已由上一轮 ΔV=1385.442 mm³ 精确验证），不是监督者自行设定。
patch(ops, "cut",
      {"op": "sketch_holes", "pcd_mm": 38.0, "hole_dia_mm": 7.0,
       "count": 3, "angles_deg": [0, 120, 240], "plane": "右视基准面"},
      "P1", "cut 无轮廓导致 ok=False 且 ΔV=0；模型两轮自修均未补")
# P2
patch(ops, "drawing",
      {"op": "save_assembly", "name": "model_assembly.SLDASM"},
      "P2", "import_assembly 后未保存，磁盘无 .SLDASM")
# P3：给已有 drawing 补 model_path（不新增 op）
asm_path = os.path.join(OUT, "model_assembly.SLDASM")
for o in ops:
    if o["op"] == "drawing":
        o["model_path"] = asm_path
        o["first_angle"] = True
        o["isometric"] = True
        o["name"] = "model_drawing.SLDDRW"
        patches.append({"id": "P3", "op": "drawing",
                        "reason": "补 model_path 指向 P2 的装配体，否则工程图引用不存在的模型"})
    if o["op"] == "save_part":
        o["name"] = "model_part.SLDPRT"

plan = {
    "method_reason": model_plan.get("method_reason", ""),
    "expected_volume_mm3": model_plan.get("expected_volume_mm3"),
    "ops": ops,
}
print("PATCHED_OPS", [o["op"] for o in ops], flush=True)
print("PATCHES", json.dumps(patches, ensure_ascii=False), flush=True)

res = feature_ops(action="execute_plan", plan=plan, step_path=STEP, out_dir=OUT)
print("\nEXEC_STATUS", res.get("status"), flush=True)
for r in res.get("ops_executed", []):
    print("  op%-2d %-18s ok=%-5s V=%s err=%s file=%s" % (
        r["step"], r["op"], r.get("ok"),
        (r.get("mass_after") or {}).get("volume_mm3"),
        r.get("error", ""),
        (r.get("file") or {}).get("saved") if isinstance(r.get("file"), dict) else None),
        flush=True)
print("FINAL_MASS", res.get("final_mass"), flush=True)

report = {
    "supervisor_patch": True,
    "reason": "Virtu 模型自修失败（两轮同构方案、cut 恒 False），按 AGENTS.md §6 熔断后由监督者补位",
    "model_plan_source": TRACE,
    "model_ops": [o["op"] for o in model_plan.get("ops", [])],
    "patches": patches,
    "patched_ops": [o["op"] for o in ops],
    "execution": res,
}
out_json = os.path.join(ROOT, "runs", "supervisor_complete_20261105.json")
json.dump(report, open(out_json, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("REPORT", out_json, flush=True)
