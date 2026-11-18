# 轮毂 bore 强度复核：口径修正与设计闭合（v2）

日期：2026-11-12　范围：`projects/impeller_workbench_v1`　对象：闭式叶轮 tapered 轮毂

## 1. 结论

1. 原先"根部加厚即可消除 bore 屈服风险"的判断**不成立**。该判断来自经验折减因子，与真实解方向相反。
2. 真实口径下，等厚 8 mm 轮毂在 u2=464 m/s 时 bore 切向应力 719.4 MPa，**FOS=1.223 < 1.5，不通过**。
3. 唯一的有效杠杆是**厚度坡度 h′/h（内厚外薄）**，不是等厚段厚度。
4. 在 D2=220 / N=40300.5 下，满足 π≥4.0 且 bore FOS≥1.6 的最小方案为：
   **h_bore=12.25 mm，h_rim=4.0 mm，外段幂律指数 p=6.0，拐点半径 r_knee=38.25 mm**，
   bore 应力 545.6 MPa，FOS=1.613，质量 0.86 kg（原等厚 1.33 kg）。

## 2. 数学依据（本轮确认）

平面应力轴对称变厚度盘膜解：

    d/dr(h·r·σ_r) − h·σ_θ + ρ·ω²·r²·h = 0

代入 σ_r、σ_θ 后，惯性项与刚度项**同时含 h，可整体约去**，方程中 h 只以 `h′/h` 出现。
数值验证（FD 600 节点）：

| h_bore | bore 处 h | σ_θ,bore | 说明 |
|---|---|---|---|
| 16 mm | 16.0 | 455.73 MPa | 内段等厚 |
| 22 mm | 22.0 | 455.73 MPa | 完全一致 |

即：**等厚段加厚不降低 bore 应力，只增加质量**。工程含义：
- 内段取工艺/装配允许的最小等厚值；
- 外段落差尽量大（幂律 p 尽量大），把 h_rim 压到 4 mm 下界；
- 应力降低来自坡度，不来自绝对厚度。

## 3. 被推翻的旧口径

原 `impeller_deterministic_solver.tapered_hub_check()` 用：

    reduction = 1 / (1 + 0.22·ln(h_bore/h_rim)·p^0.45)
    σ_tapered = σ_equal · reduction

三处缺陷：
1. **无物理依据**：0.22、0.45 为手调常数，非任何解析或实验来源。
2. **参数越界**：默认 `h_rim=3.5 mm`，低于 4.0 mm 的叶根过渡/密封面下界。
3. **结论反向**：等厚 8 mm 真实 FOS=1.223（不通过），旧式却报通过，属假绿。

已删除该因子，改为直接求解 ODE。

## 4. 新口径定义

- 求解器：变厚度盘轴对称 ODE，有限差分 600 节点，`hub_stress_tapered.solve_var`。
- 叶片载荷：叶片离心力折算为外缘等效径向拉
  `σ_rim = Z·m_blade·ω²·r_cg / (2π·b·h_rim)`，弦长取中弧 0.7 折减、轴向长取 L。
- **不再乘 K_BLADE=1.2**：叶片载荷已显式施加，再乘即重复计入。
- 判据：`FOS_bore = σy/σ_θ,bore ≥ 1.5`（σy=880 MPa）；反解厚度时用 1.60 留约 7% 裕度。

## 5. 设计反解规则（写入 solver）

`solve_min_hub_thickness()`：内段等厚、外段幂律，从 8 mm 起以 0.25 mm 步长向上扫描，
返回首个满足 FOS≥1.60 的厚度（FOS 随厚度单调递增）。
`build()` 中 L 与 th 互相依赖，迭代 3 次收敛。

反解结果：

| D2 (mm) | N (rpm) | th (mm) | h_rim | p | r_knee | π 复算 | bore σ (MPa) | FOS_bore | 判定 |
|---|---|---|---|---|---|---|---|---|---|
| 220 | 40300.5 | 12.25 | 4.0 | 6.0 | 38.25 | 4.010 | 545.6 | 1.613 | 通过（0 违规） |
| 240 | 37000 | 13.25 | 4.0 | 6.0 | 52.42 | 4.089 | 550.9 | 1.597 | 通过（0 违规） |
| 220 | 39000 | 11.25 | 4.0 | 6.0 | 43.93 | 3.702 | 549.9 | 1.600 | π 不足（既定约束，非 bore 问题） |

### 5.1 尺子层验证（`temp/neg_ruler.py`）

| 用例 | 结果 |
|---|---|
| 基线（D2=220/N=40300.5，th=12.25） | VIOL=0 |
| 反例（th=8.0, h_rim=4.0, p=1.0） | VIOL=1：`tapered 轮毂 bore 复算 FOS=1.134 < 1.5（sigma_theta_bore=776.1 MPa，已含叶片离心载荷；h_bore=8.0/h_rim=4.0/p=1.0/rk=38.2 mm）` |
| 退化（删除 `hub_rim_thickness_mm` 字段） | VIOL=0，硬判据不启用，旧报告仍可复判 |

求解器层反例：等厚 8 mm、无坡度 → FOS=1.111，判红 ✓

## 6. 轮廓族扫描（sweep3/4/5）

- **sweep3**：线性两段，120 组 → 仅 12 组可行，最轻 1.944 kg（h_bore=20/h_rim=4）。
- **sweep4**：外段幂律 + 内段等厚，560 组 → 104 组可行，最轻 1.188 kg（暴露"h_bore 不影响应力"）。
- **sweep5**：内段取最小等厚，140 组 → 92 组可行，最轻 **0.800 kg**（h0=11/p=8/rk=30，FOS 1.537）。
  该最优点位于参数边界（p 上界、h0 近下界），工程上偏激进；设计值取 **h0=12.25/p=6.0/rk=38.25**，
  质量 0.86 kg，比 sweep5 极值重 7%，但外段厚度分布更平顺、叶根过渡更可控。

原始数据：`hub_taper_sweep3.json` / `sweep4.json` / `sweep5.json`（同目录）。

## 7. 代码变更

| 文件 | 变更 |
|---|---|
| `closed_impeller_proctor.py` | 新增 tapered 轮毂 bore **硬判据**：当参数含 `hub_rim_thickness_mm` 且 < 轮毂盘厚度时，用 FD 解复算，FOS<1.5 直接判红；原 advisory 保留 |
| `impeller_deterministic_solver.py` | 删除 `tapered_hub_check` 经验折减；新增 `_taper_profile` / `bore_fos_fd` / `solve_min_hub_thickness`；`build()` 反解 th 并输出 `hub_rim_thickness_mm`、`hub_knee_r_mm`、`hub_taper_exponent`；新增常量 `H_RIM_MIN=4.0`、`HUB_TAPER_POWER=6.0`、`HUB_FOS_TARGET=1.60` |
| `hub_taper_sweep3/4/5.py` | 轮廓族扫描脚本（新增） |

备份：`impeller_deterministic_solver.py.bak_before_fd_bore`

## 8. 复现

    .venv\Scripts\python.exe temp\accept_e2e.py
    .venv\Scripts\python.exe scripts\hub_taper_sweep5.py

## 9. 未完成 / 风险

1. **未做 FEA**：FD 轴对称解不含叶片-轮毂连接处的局部应力集中、不含热载与气动轴向力。
   本轮只解决膜应力层面的 bore 屈服，局部 FEA 仍是放行前的必需步骤。
2. **未跑完整 workbench auto**：`--rounds 4` 因单次工具 600 s 上限被中断，改为 1 轮后台验证。
   模型侧字段不受本次改动影响（确定性接管时由 solver 写入）。
3. **外段 4 mm 等厚圈面积较大**：p=6 时 r>90 mm 区域已接近 h_rim，需在 FEA 中确认该区刚度与
   与盖盘的连接刚度，必要时把 p 下调至 4 并接受约 2% 增重。
4. **口径未覆盖热态**：全表按冷态 ρ、σy 计算，未计 288→400 K 的 σy 折减。
