---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 4089e70912072d5b0de62543257d198b_4cd8ed93dc3811f19280525400393706
    ReservedCode1: hO09ZPogKrp+wtOB69GxbDXIW/t84uKZl9/AXznH1M121abPmbMZ35qqDqM+N7FNhKhessJzliwhbqJWpdLzrF1yOUxlWwWvlo2VC+wm0VwaT1LBVbVPp1QxHU3tFVv9Te/S7fZETl3+/5n9rDYSemA7cxrUjv7bkdf+1dXPt4DfxdaR4ZC/tToTkc0=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 4089e70912072d5b0de62543257d198b_4cd8ed93dc3811f19280525400393706
    ReservedCode2: hO09ZPogKrp+wtOB69GxbDXIW/t84uKZl9/AXznH1M121abPmbMZ35qqDqM+N7FNhKhessJzliwhbqJWpdLzrF1yOUxlWwWvlo2VC+wm0VwaT1LBVbVPp1QxHU3tFVv9Te/S7fZETl3+/5n9rDYSemA7cxrUjv7bkdf+1dXPt4DfxdaR4ZC/tToTkc0=
---

# 路线 A 结题报告：8.2B 推理期工作台（impeller_design_workbench）

- 日期：2026-11-09
- 被测模型：`virtu-ties-v1:latest`（8.2B，qwen3 架构，Q4_0）
- 判分器：`scripts/closed_impeller_proctor.py` → `ruler()`（未修改、未放宽、未参与工作台内部逻辑）
- 工作台：`scripts/impeller_design_workbench.py`（本次新建，13.7 KB）
- 运行账本：`projects/impeller_workbench_v1/workbench_runs_ledger.json`
- 原始报告：`projects/impeller_workbench_v1/report_virtu-ties-v1_latest_*.json`（8 份）
- 口径：模型负责全部设计决策；系统只做三件确定性事——算式求值、物理复算回喂、格式归一与字段拼装。工作台不判分、不代选设计值。

## 1. 结论（先说结果）

**路线 A 在「模型独占设计决策」的分账口径下不能闭环：8 次运行全部 FAIL，历史最优为残余 3 项违规，从未达到 0。**

但工作台确实修好了它该修的部分，且已留证。失效已经收敛到一个可命名的模式，不再是「说不清为什么不行」。

## 2. 工作台做了什么（已验证生效）

| 能力 | 实现 | 验证证据 |
|---|---|---|
| 动作协议 | `calc / check / final / patch` 四选一，每轮只输出一个 JSON | 8 次运行协议无死锁 |
| 安全求值 | 白名单 `math.*` + `abs/min/max/round`，无 `__builtins__`，表达式正则限字符集 | `sqrt(1004.5*288.15*((4.0)**(0.2857)-1)/(0.85*0.9))` → 428.80 |
| 物理复算回喂 | 每轮回喂 `u2 / π_recomputed / FOS / M_rel / σ_eq / cm2 / ca1 / T02 / Δh0 / Ns` | 每轮 trace 均含 recomputed |
| 格式归一 | `normalize()` 把 `"120 mm"`、`1.2e3` 统一成 float，剔布尔 | 首轮字段全空后，后续轮稳定拿到 17 字段 |
| 复读检测 | 参数指纹相同 → 进入 field-patch 模式，只允许改违规字段 | 多次触发，日志可见「只允许修改这几个字段中的 1 个」 |
| 区间硬约束回喂 | 从违规文本抽 `[lo,hi]`，绑定字段后强制提示 | 已生效但模型不执行（见 §4.2） |
| 宣称量自洽 | `claimed_tip_speed_m_s` 与其自给 D2/N 复算值不符时由系统按公式派生 | 轮 3：模型宣称 235、复算 141.37 → 归为 141.37 并记录 `model_had` |
| 物理合法性护栏 | `eta_total` 不满足 `0<η<1` 时归一为 0.85 并要求重做反解 | 轮 2：η=1.0 被拦截；历史轮出现 η=1.2/1.5 |

## 3. 8 次运行数据

| # | 轮数 | passed | best_n_viol | 违规数轨迹 | 该次最优 D2/N/宣称u2 |
|---|---|---|---|---|---|
| 1 | 1 | False | — | — | Ollama 未启动（服务中断） |
| 2 | 2 | False | 1 | 1,1 | 字段全空（首轮 eval_count=14，模型只输出 action） |
| 3 | 3 | False | 4 | 4,4 | 150 / 12000 / 235（宣称 235 vs 复算 94.2） |
| 4 | 10 | False | 4 | 5,5,4,4,5,5,4,4,5,4 | 120 / 20000 / 235（十轮只在 b2 上 2→3→5→8→10 微调） |
| 5 | 12 | False | 6 | 8,7,6,6,6,8,8,7,7,7 | 120 / 12000 / 235 |
| 6 | 10 | False | **3（历史最优）** | 5,4,4,4,5,4,3,3 | **387 / 15000 / 303.95（自洽，见 §4.1）** |
| 7 | 12 | False | 4 | 6,4,5,6,6,6,5,5,6,6 | 250 / 15000 / 196.35（η=1.5 非物理导致反解偏低） |
| 8 | 12 | False | 4 | 4,4,4,5,5,6,6,6,6,6 | 100 / 12000 / 62.83（反向漂移，D2 向 20mm 走） |

## 4. 关键证据

### 4.1 工作台能消除算术缺陷（第 6 次运行）

模型自己算出达到 π 目标所需 `u2≈428.8 m/s`（用 η=0.85、修正项 0.9）。紧接着它把 `D2_mm` 从 250 直接跳到 **387**，并把宣称叶尖速写成 303.95。复算：`π×387×15000/60000 = 303.95 m/s`，与它填的宣称值完全一致。

这说明两件事：
1. 只要工作台给出算式与再喂回结果，8B **有能力**完成反解并把结果落回参数；
2. 这一步之后违规数从 8 项降到 3 项，是本项目 8B 侧的历史最好成绩。

### 4.2 但跨步一致性、量级锚定、区间执行三项稳定失效

- **跨步失忆**：第 1 轮算出 u2=419.3（第 9 次运行）后，同一会话第 3 轮给出 `D2=100, N=12000`，复算 u2 仅 **62.8 m/s**，与其自算结果差 **6.7 倍**。该模式在 8 次运行中稳定复现，不是偶然。
- **区间视而不见**：违规文本已明确给出 `轴向长 L 不在 [77.4, 212.9]`（按它自己的 D2 算的），它连续 **10 轮**把 `L` 保持为 15.0，一次未改。
- **宣称不自检**：`claimed_pressure_ratio` 在 6 次运行中恒填 4.0，即使复算压比只有 1.805（差 2.2 倍）也不修正；`eta_total` 反复填 1.0/1.2/1.5（>1，超物理上限），被工作台归一后仍重犯。
- **反向漂移**：第 8 次运行中 D2 沿 100→55→20 收敛到错误方向，最终 `D1t=0.85 mm`，产生 6 项新违规。
- **复读**：参数指纹在多轮内完全相同（`ca29c164b6`、`41814c6ca2` 各出现 2 次以上），工作台已切 field-patch 模式，模型仍输出无效或空 patch。

### 4.3 与既有根因诊断一致

本次结论与 `LAYER1_ABLATION_REPORT.json` 及基座探针一致：缺陷在权重层的定量设计能力（量级判断 + 跨步一致性 + 指令遵循），不在接口、契约、少样本脚手架。工作台把「脚手架能做的」全部做完后，残余违规仍全部落在模型自主决策域。

## 5. 可行的下一步（按性价比排序）

### A′ 工具化收窄分账（1 小时内可验证，建议先做）
把 3 个「单变量可反解」约束从模型决策域移交确定性求解器，模型只保留 `Z_blades / beta2b_deg / b2_mm / eta_total` 与是否接受结果：
- `axial_length_mm` ← 取 `[0.20·D2, 0.55·D2]` 区间的中值；
- `D1t_mm / D1h_mm` ← 由 `ca1` 目标区间反解喉口面积，再反解直径；
- `u2` 不足 → 由 `D2` 与 `N` 的组合反解，二选一由模型定。

代价：这会突破当前分账红线，**结果不得计入模型裸能力**，只能作为交付工具。收益：立刻拿到一个能产出合格设计的工程工作台。

### B 权重修复（8B QLoRA，云端）
数据缺口从 24 条扩到 500–1000 条。本次运行日志本身就是高质量数据源：每一轮都是「模型错误参数 → 独立复算的违规诊断 → 模型修正」，可直接做**拒绝采样 / DPO 配对数据**（workbench 当教师，ruler 当裁判）。
本地 RTX 4050 6GB 无法承担 8B QLoRA（此前已证伪），仍需云端 GPU。

### 推荐路径
先 A′（拿工具 + 拿数据工厂）→ 用 A′ 批量生成正确/违规配对 → 供 B 训练。A′ 不是 B 的替代，而是 B 的产线。

## 6. 交付物清单

| 文件 | 说明 |
|---|---|
| `scripts\impeller_design_workbench.py` | 工作台正式脚本，13,175 字节，py_compile 通过 |
| `projects\impeller_workbench_v1\workbench_runs_ledger.json` | 8 次运行结构化账本（含违规轨迹、最优参数） |
| `projects\impeller_workbench_v1\report_virtu-ties-v1_latest_*.json` | 8 份原始 trace |
| `projects\impeller_workbench_v1\ROUTE_A_REPORT.md` | 本报告 |

## 7. 环境备注

- Ollama 独立实例：`E:\OllamaApp\ollama.exe serve`，`OLLAMA_HOST=127.0.0.1:11435`，`OLLAMA_MODELS=E:\ollama\models`（68 个模型）。本次实验期间该实例曾中断，已重启（pid 21060）。
- 单轮耗时 10–120 s（随上下文增长变慢），12 轮约 6–12 分钟。
- 未修改：`closed_impeller_proctor.py`、模型权重、`LAYER1_ABLATION_REPORT.json`。
*（内容由AI生成，仅供参考）*
