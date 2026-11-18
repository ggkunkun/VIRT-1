---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 4089e70912072d5b0de62543257d198b_f3279d77dc3c11f19280525400393706
    ReservedCode1: WIivH44eP57WmjCpQMMRrS12OxYUfegmZuWSySwlgZ4Qcj9hHwxphAp+0+kNdl5yxsORYJSkGQ8y8RGChalfFdaTF3UudQ7fBs6pLLOMec3GqZ6zmZl30iOptCW763xc26Fe4U1JTKgIQCYF/rJ4jlUmZdByA5MdKXMD1gDh4689RASPn5elHpeZUyY=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 4089e70912072d5b0de62543257d198b_f3279d77dc3c11f19280525400393706
    ReservedCode2: WIivH44eP57WmjCpQMMRrS12OxYUfegmZuWSySwlgZ4Qcj9hHwxphAp+0+kNdl5yxsORYJSkGQ8y8RGChalfFdaTF3UudQ7fBs6pLLOMec3GqZ6zmZl30iOptCW763xc26Fe4U1JTKgIQCYF/rJ4jlUmZdByA5MdKXMD1gDh4689RASPn5elHpeZUyY=
---

# 路线 A′ 结题报告：单变量可反解约束移交确定性求解器

生成时间：2026-11-09
模型：`virtu-ties-v1:latest`（Ollama 独立实例 `127.0.0.1:11435`）
判定器：`scripts/closed_impeller_proctor.py::ruler()`（未修改、未放宽、未参与工作台内部逻辑）

---

## 1. 结论（一句话）

**A′ 成立：工作台可以在 1 小时内（实测 22–456 s/次）产出 `passed=True` 的合格设计，共 2 次。**
但必须分账：**合格结果来自确定性求解器，不来自 8B 模型的决策能力**——模型在 A′ 中只提供 6 个自由度，且经对照实验证实其自由度取值是 prompt 示例的逐字复读。

---

## 2. 做了什么

把 3 类"单变量可反解"约束从模型决策域移交给确定性求解器：

| 约束 | 原状态（路线 A） | A′ 处理 |
|---|---|---|
| `axial_length_mm ∈ [0.20·D2, 0.55·D2]` 且 `L ≥ th+ts+b2` | 模型自由填，历史 10 轮保持 L=15.0 不动 | 求解器取可行区间中值 |
| `ca1 ∈ [80,240] m/s` → `D1t/D1h` | 模型填 D1t=0.85 mm、D1t>D2 等非物理值 | 由 ca1 目标反解喉口面积，再取 M_rel≤1.13 允许的 D1t 上界，反解 D1h |
| `b2/D2 ∈ [0.02,0.10]` + 宣称量与复算一致性 | `claimed_pressure_ratio` 6 次恒填 4.0 | b2 = 比值×D2；`claimed_*` 由 ruler 复算派生 |

模型保留：`Z_blades` / `beta2b_deg` / `b2_ratio` / `eta_total` / `D2_mm` 与 `N_rpm` 的首选，以及**候选方案的 accept / revise 权**。

新增/修改文件：
- `scripts/impeller_deterministic_solver.py`（新增，7652 字节）：`candidates()` / `from_model_params()` / `tune_N_for_pi()` / `tune_D2_for_pi()` / `build()` / `inlet_geometry()` / `fill_claims()`
- `scripts/impeller_design_workbench.py`（新增 240 行）：`--mode {full,assist,auto}`，`run_solver()` / `finalize_solver()`；`full` 分支即原路线 A 逻辑，**行为未变**

---

## 3. 实测数据

| 运行 | 模式 | 耗时 | 模型自由度输入 | 采用候选 | D2/N | π 复算 | u2 | FOS | 违规 | passed |
|---|---|---|---|---|---|---|---|---|---|---|
| `report_Aprime_auto_...203927` | auto | 21.9 s | Z12/β25/η0.85/D2 220/N 40000/br0.09 | A 锁 D2=220 → N=40301 | 220 / 40300.5 | 4.010 | 464.23 | 1.84 | **0** | **True** |
| `report_Aprime_assist_...205157` | assist | 34.4 s | Z10/β30/η0.85/D2 150/N 15000（模型裸填 17 字段含 D1t=200>D2、L=10） | B 锁 N=15000 → D2=579 | 578.63 / 15000 | 4.010 | 454.45 | 1.92 | **0** | **True** |
| `report_Aprime_assist_...204942` | assist | 456.2 s | 首版 prompt 未限制额外键 → 输出 1400 token 截断，fallback D2=100/N=12000 | B 锁 N=12000 → D2=600（被搜索上限截断） | 600 / 12000 | 2.803 | 376.99 | 2.50 | 1（π<3.96） | False |

第 3 行为**已修复的历史缺陷**，保留归档：`tune_D2_for_pi()` 原 D2 搜索上界硬编码 600，未按 u2 硬上限反解；模型给出 N=12000 时需要的 D2≈724 被截断，压比停在 2.803。修复后上界改为 `min(1600, U2_LIMIT·60000/(π·N)·1.02)`，同一输入下 `D2=441`、违规 0。

---

## 4. 关键反证：模型的"自由度决策"是复读

对 auto 分支做对照实验（`temp/echo_probe.py`）：把 prompt 里的示例从 `Z12/β25/η0.85/D2 220/N 40000/br0.09` 整体换成 `Z16/β35/η0.80/D2 300/N 25000/br0.05`，
模型输出：

```json
{"action":"free","free":{"Z_blades":16,"beta2b_deg":35,"eta_total":0.8,"D2_mm":300,"N_rpm":25000,"b2_ratio":0.05},
 "reason":"自主设定 16 片后弯叶片，出口角 35°，总效率 0.8，叶轮外径 300 mm，转速 25000 rpm，流道宽比 0.05"}
```

**6 项与示例完全一致，0 项差异，且自述"自主设定"。**
结论：模型在 auto 分支没有行使设计判断，只是复读示例。A′ 的 `passed=True` 因此**不能计入模型裸能力**，只能证明"求解器 + 判定器 + 契约"这套工程链路能闭环。

---

## 5. 分账口径（红线）

- **可计入交付工具**：A′ 工作台能稳定产出 ruler 零违规设计（2/3 次，第 3 次为已修缺陷）。
- **不可计入模型能力**：模型未展现独立的量级判断；其贡献等价于"返回一个符合 schema 的 JSON"。
- **与路线 A 结论一致**：缺陷在权重层的量级判断与跨步一致性，不在脚手架（对照 `LAYER1_ABLATION_REPORT.json`）。A′ 的做法是把"需要判断"的部分换成"算术可反解"的部分，从而绕开缺陷，而非修复缺陷。

---

## 6. 已知局限

1. **D2=579 mm 的解在物理上偏大**：ruler 无 D2 上限判据，只有 `u2 ≤ 514 m/s`（FOS 反解）与 `b2/D2` 比值约束，因此"大直径低转速"与"小直径高转速"在尺子口径下等价。交付时需人工择一（A′ 已把 A/B 两条候选交模型 accept，但模型的 accept 判断同样不可靠）。
2. **assist 模式对模型输出格式敏感**：首版未禁止额外键，模型输出 `design_rationale` 导致 JSON 截断（1400 token 打满、456 s）。修复后单次 34 s。
3. **`beta2b_deg` / `Z_blades` / `eta_total` 仍由模型定**，且已证实是复读；这三个量在可行域内的敏感度低（η 落在 0.70–0.90 都被接受），但若模型给出域外值，求解器会 clamp 到默认（η→0.85、br→[0.03,0.09]）。
4. `impeller_deterministic_solver.py` 的常数与被尺子的常数是**两处独立维护**（求解器 import cp 但 U2_LIMIT/PI_TARGET 是自算的），尺子若改阈值，求解器需同步。

---

## 7. 复现命令

```powershell
Set-Location "D:\Virtu模型"
# A′（求解器接管单变量反解）
.\.venv\Scripts\python.exe scripts\impeller_design_workbench.py --mode auto   --model "virtu-ties-v1:latest" --host http://127.0.0.1:11435
.\.venv\Scripts\python.exe scripts\impeller_design_workbench.py --mode assist --model "virtu-ties-v1:latest" --host http://127.0.0.1:11435
# 路线 A（模型独占全部决策，对照组）
.\.venv\Scripts\python.exe scripts\impeller_design_workbench.py --mode full   --model "virtu-ties-v1:latest" --host http://127.0.0.1:11435
```

产物目录：`projects\impeller_workbench_v1\report_Aprime_*.json`

---

## 8. 建议的下一步

1. **不再在 8B 上尝试"让它自己做量级判断"**。路线 A 的 8 次全 FAIL 与本次复读实验已构成证据闭包。
2. 若目标是交付可用设计工具：把 A/B 候选的选择权交给**人工**而非模型（当前 `accept` 环节是唯一仍在模型手里的判断，且实测 2.5 s 返回"接受反解的完整硬约束方案"，无实质比较）。
3. 若目标是验证模型能力：改用"给定 u2 目标 + 给定 D2，反解 N 并自检"这类**单步可验**任务，避开跨步一致性，才能得到可归因的分数。
*（内容由AI生成，仅供参考）*
