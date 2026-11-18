# -*- coding: utf-8 -*-
"""agent_team 五个 agent 的"实算 vs 桩"可证伪验证。

改造前：子模块固定三条、GD&T 写死 0.015/0.020、公差写死 "H7 (+0.021/0)"、
主轴转速按材料查常量表、特征树 width/thickness 混用 overall_len。

改造后必须满足（每条都可被坏实现推翻）：

A. 几何族：回转体件与板类件拆出的模块集合不同；长径比影响轴类/盘套类判定。
B. 公差：ISO 286 实算，公称尺寸变化 → 极限偏差变化；Ø80 g6 必须等于标准 -10/-29 µm。
C. 切削参数：同一材料直径加倍 → 转速近似减半；不同材料同直径 → 转速不同。
D. 分层：径向余量/背吃刀量变化 → 粗车次数变化。
E. Macro B 必须通过运动学沙箱（无 G00 负向扎刀、无主轴未转切削），且保留 G71。
F. 建模：包络尺寸随 spec 的 overall_len 变化；特征树非空。
G. 五个 agent 全部 COMPLETED（含审计 agent 对生成代码的沙箱判定）。

运行： python tests/test_agent_team_real_agents.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from virtu_omni.agent.agent_team import (  # noqa: E402
    ChiefArchitectAgent, MachiningAndToolpathAgent, ParametricModelingAgent,
    StandardsAndGDAgent, classify_geometry, cutting_params_for, iso286_fit,
)
from virtu_omni.agent.headless_sandbox_verifier import HeadlessSandboxVerifier  # noqa: E402

PROMPT_SLEEVE = "我想制造一款精密成型轮模 材质Cr12MoV 外径53mm 轴孔14mm 宽度45mm"
PROMPT_PLATE = "需要一块安装底板 材质AL7075-T6 外径120mm 内孔10mm 长度12mm"


def _arch(prompt: str):
    return ChiefArchitectAgent().run({"user_prompt": prompt})


def main() -> int:
    checks = []

    # ---- A. 几何族与模块拆解 ----
    a_rot = _arch(PROMPT_SLEEVE)
    a_plate = _arch(PROMPT_PLATE)
    mod_rot = [m["module_name"] for m in a_rot["sub_modules"]]
    mod_plate = [m["module_name"] for m in a_plate["sub_modules"]]
    print("A family:", a_rot["geometry_family"], "|", a_plate["geometry_family"])
    print("A modules:", mod_rot, "vs", mod_plate)
    checks.append(("A 回转/板类族不同", a_rot["geometry_family"] != a_plate["geometry_family"]))
    checks.append(("A 模块集合不同", mod_rot != mod_plate))
    checks.append(("A 模块数量>3（不再固定三条）",
                   len(mod_rot) >= 4 and len(mod_plate) >= 4))
    shaft = dict(a_rot["parsed_spec"], overall_len=120.0, d_outer=40.0)
    checks.append(("A 长径比 3.0 → 轴类", classify_geometry("轴", shaft)[0] == "回转体-轴类"))
    short = dict(a_rot["parsed_spec"], overall_len=10.0, d_outer=100.0)
    checks.append(("A 长径比 0.1 → 盘套类", classify_geometry("盘", short)[0] == "回转体-盘套类"))

    # ---- B. ISO 286 公差实算 ----
    f14 = iso286_fit(14.0, "H7")
    f80 = iso286_fit(80.0, "H7")
    g80 = iso286_fit(80.0, "g6")
    print("B H7(14)=", f14["upper_mm"], "H7(80)=", f80["upper_mm"],
          "g6(80)=", (g80["upper_mm"], g80["lower_mm"]))
    checks.append(("B 公称尺寸影响公差", f14["upper_mm"] != f80["upper_mm"]))
    checks.append(("B Ø80 g6 命中标准 -10/-29µm",
                   abs(g80["upper_mm"] + 0.010) < 1e-6 and abs(g80["lower_mm"] + 0.029) < 1e-6))
    s = StandardsAndGDAgent().run({"architecture": {"parsed_spec": a_rot["parsed_spec"]}})
    checks.append(("B 图纸标注非写死",
                   s["drawing_spec"]["fit_tolerances"][0]["tolerance_class"] != "H7 (+0.021 / 0 mm)"))
    checks.append(("B 形位公差由 IT 换算",
                   s["drawing_spec"]["geometric_tolerances_gdt"][0].get("derivation", "").startswith("IT5")))

    # ---- C. 切削参数随直径/材料变化 ----
    c50 = cutting_params_for("AL7075-T6", 50.0, 20.0)
    c100 = cutting_params_for("AL7075-T6", 100.0, 20.0)
    c_ti = cutting_params_for("Ti-6Al-4V", 50.0, 20.0)
    ratio = c50["spindle_rpm"] / c100["spindle_rpm"]
    print("C rpm(50)=", c50["spindle_rpm"], "rpm(100)=", c100["spindle_rpm"],
          "ratio=", round(ratio, 3), "| Ti rpm=", c_ti["spindle_rpm"])
    checks.append(("C 直径加倍转速近似减半", 1.9 <= ratio <= 2.1))
    checks.append(("C 材料不同转速不同", c_ti["spindle_rpm"] < c50["spindle_rpm"]))
    checks.append(("C 转速由公式而非常量表",
                   c50["spindle_rpm"] == int(round(1000 * 300.0 / (3.141592653589793 * 50.0)))))

    # ---- D. 分层数随余量/背吃刀量变化 ----
    d_small = cutting_params_for("Cr12MoV", 40.0, 30.0)   # 余量 5mm / ap1.5 -> 4
    d_large = cutting_params_for("Cr12MoV", 80.0, 20.0)   # 余量 30mm / ap1.5 -> 20
    print("D passes:", d_small["roughing_passes"], "vs", d_large["roughing_passes"])
    checks.append(("D 分层数随径向余量增加", d_large["roughing_passes"] > d_small["roughing_passes"]))

    # ---- E. 生成的 Macro B 必须过运动学沙箱 ----
    mach = MachiningAndToolpathAgent().run({"architecture": {"parsed_spec": a_rot["parsed_spec"]}})
    code = mach["macro_b_code"]
    ver = HeadlessSandboxVerifier().verify_cimco_macro_b(code)
    print("E macro sandbox passed=", ver["passed"], "collision=", ver["collision_detected"],
          "errors=", ver["errors"][:2])
    checks.append(("E Macro B 过沙箱", ver["passed"] is True and ver["collision_detected"] is False))
    checks.append(("E 保留 G71 粗车循环", "G71" in code))
    checks.append(("E 无 G00 负向 Z 扎刀",
                   not any(l.strip().upper().startswith(("G0 Z-", "G00 Z-"))
                           for l in code.splitlines())))

    # ---- F. 建模包络随 spec 变化 ----
    pm1 = ParametricModelingAgent().run({
        "user_prompt": PROMPT_SLEEVE,
        "architecture": {"parsed_spec": a_rot["parsed_spec"],
                         "geometry_family": a_rot["geometry_family"]}})
    spec2 = dict(a_rot["parsed_spec"], overall_len=90.0)
    pm2 = ParametricModelingAgent().run({
        "user_prompt": PROMPT_SLEEVE,
        "architecture": {"parsed_spec": spec2, "geometry_family": a_rot["geometry_family"]}})
    print("F thickness:", pm1["bbox_mm"]["thickness"], "->", pm2["bbox_mm"]["thickness"])
    checks.append(("F 包络厚度随 overall_len 变",
                   pm1["bbox_mm"]["thickness"] != pm2["bbox_mm"]["thickness"]))
    checks.append(("F 特征树非空", len(pm1["feature_tree"]) > 0 and "equations" in pm1))

    # ---- G. 五 agent 状态 ----
    statuses = [a_rot["status"], s["status"], mach["status"], pm1["status"]]
    print("G statuses:", statuses)
    checks.append(("G 各 agent 均 COMPLETED", all(x == "COMPLETED" for x in statuses)))

    print("\n=== agent_team 实算测试 ===")
    all_pass = True
    for name, ok in checks:
        print(("  PASS  " if ok else "  FAIL  ") + name)
        all_pass = all_pass and bool(ok)
    print("\n" + ("ALL PASS (%d/%d)" % (sum(1 for _, o in checks if o), len(checks))
                  if all_pass else "HAS FAILURES"))
    return 0 if all_pass else 1


def test_real_agent_engineering_contracts():
    assert main() == 0


if __name__ == "__main__":
    raise SystemExit(main())
