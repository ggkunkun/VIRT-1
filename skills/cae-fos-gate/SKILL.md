---
name: cae-fos-gate
description: CAE 强度闸的独立复核——用闭式解(Lamé 厚壁圆筒、Timoshenko 环形法兰板、弯剪组合支座)重算 von Mises 与 FOS，与 cadcam_cae_stress_analysis 的自报数字对账，并检查它宣称的材料屈服是否真的被用上。当模型要做 FOS>=1.5 判定、触发几何自愈、或收到 status=optimized 的结果时使用。
metadata:
  version: "1.0.0"
  owner: "Virtu 自建（GitHub CAE 技能全绑 Abaqus/Ansys/CalculiX/FEniCS，本机无求解器）"
  tools: [cadcam_cae_stress_analysis, cadcam_universal_geometry, cadcam_extreme_chain]
  executor: scripts/fos_crosscheck.py
  evidence: "法兰/轴/支座三族与引擎自洽(相对偏差<=0.06%)；修掉材料静默降级、载荷未接入、钣金族假达标三处缺陷"
---

# CAE 安全系数闸（FOS 复核）

## 为什么要有这个技能
`cadcam_cae_stress_analysis` 返回的是**解析式**结果，不是有限元。它曾经有三处会给出"看着像绿的"结论，本技能就是把它逼回可复算：
1. 材料名不在表内时静默改用 Cr12MoV(σy 850)，而工具默认传的是"45号钢"→ FOS 虚高 2.4 倍。现在解析不到材料返回 `status=blocked / MATERIAL_UNRESOLVED`，不出数。
2. 工具层 `force_n` 映射成 `load_n`，而各构件族读的是 `radial_load_n/bending_force_n`→ 用户载荷被丢掉、按默认 45 MPa 或 12 kN 算。现在做键名归一，`torque_nm` 也进入轴的 von Mises。
3. 钣金族的 σ 是"外层纤维是否屈服"的成形性指标，FOS<1.5 意味着折弯必然塑性回弹，不是强度不足；按强度自愈会算出 ~957 mm 的荒谬圆角。现在直接返回 `formability_advisory` 并禁止自愈改几何。

## 执行
```
python skills/cae-fos-gate/scripts/fos_crosscheck.py \
  --family FLANGE_PLATE --spec '{"d_outer":160,"d_inner":50,"thickness":20,"pcd":125,"bolt_hole_count":6}' \
  --loads '{"fluid_pressure_mpa":1.6}' --material 45号钢 --engine --json-out <报告.json>
```
`--engine` 会同时调用 `virtu_omni/engine/universal_cae_engine.py`，报告里给 `rel_diff_vs_engine` 与 `engine_yield_matches_claim`。

## 判据
- `rel_diff_vs_engine > 0.02` → 任一侧算式漂移，停止采信，先修数不修词。
- `engine_yield_matches_claim == false` → 报出来的材料不是真正参与计算的材料，判废。
- `status=optimized` 只允许在 `factor_of_safety >= 1.5` 时出现；`not_healed` 必须如实保留并回 CAD 环节。
- `status=formability_advisory` → 转折弯系数/回弹补偿路径（`cadcam_universal_geometry(part_type=sheet_metal)`），不得当强度不合格反复加厚板材。
- `verdict_code=MATERIAL_UNRESOLVED` → 把可用材料键回给用户，禁止挑一个"差不多的"顶替。

## 硬规则
- 受力工况（压力、轴向力、扭矩、力臂）必须来自图纸或用户，缺项就阻断，不用引擎默认值凑数。
- 截面属性、单位（N/mm/MPa）与几何族必须一致；Lamé 公式只适用于连续厚壁回转体，有开孔/键槽时另计。
- FOS 判据的分子用屈服，不用抗拉；报告里两个都要写清楚用的是哪一个。

## 输出契约
`{family, spec, loads, material_arg, independent{yield_used_mpa,von_mises_mpa,fos}, engine{...}, rel_diff_vs_engine, engine_yield_matches_claim, verdict}`，`verdict ∈ FOS_OK / FOS_FAIL_OR_MISMATCH`。任何 mismatch → 闭环回到 CAD，不得进 CAM。
