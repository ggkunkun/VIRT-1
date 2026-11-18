# 推理侧缺陷修复（2026-11-18）

**范围**：用户选方案 1——推理侧修复，**不改权重**。被修对象来自
`reports/SIX_SOFTWARE_STEP1_AUDIT_2026-11-18.json`（probes-2026-11-16-v5，grader 74a7da08…，basis=measured）。

## 新增文件（只新增，未改任何共享/他人在改的文件）

| 文件 | 作用 |
|---|---|
| `virtu_omni/agent/grounded_inference.py` | Lamé 闭式解 + 题面解析 + 数值一致性门；按题面参数化的 G71/G70 语义门；确定性 G71 生成器；`GroundedResponder`（模型 → 门 → 带违规重写 ≤3 次 → 确定性兜底，兜底也必须过门） |
| `tests/test_grounded_inference.py` | 29 条离线契约测试 |
| `scripts/grounded_reprobe.py` | 真机复测：裸模型 vs 接地层，按 digest 归属，测量链非独占即拒跑 |

## 证据（basis=measured，离线，n=29）

`.venv/Scripts/python.exe -m pytest tests/test_grounded_inference.py` → **29 passed**

- 回放 v3（digest 35cd9e06）的真实失败输出：两条 G71 都判红，并且具体指出违规——G00 Z-25 扎刀、轮廓无 G01 切削、首块带 Z（违反 Type I）、缺 Ø38/Ø46 台阶、G70 带 U/W。
- 植入坏样本 ⇒ 必须判红：10 种变异（G00 负 Z、台阶长度不对、U 取负、起刀点在毛坯内、没退出毛坯、首块带 Z、G70 带 U、总长不足、缺 M30、空程序）全部判红。
- 交叉核对：Lamé 结果与 `skills/cae-fos-gate` 的独立实现在 4 组参数上一致（rel 1e-12）；生成程序同时通过 `scripts/g71_semantic_check`、`cnc_semantic_gate`、官方令牌门 `evaluate_fanuc_g71_safety_probe` 三道门，Lamé 兜底结果通过官方 `evaluate_lame_stress_probe`。
- 记忆型错误能被拦住：换参数后仍写 33.33 MPa，或混入编造的 MPa 数值 ⇒ 判红。
- 诚实标注：模型连续答错时走兜底，标 `source=deterministic_*`、`model_passed=False`；没有模型、传输错误或 `ERROR` 字符串都不算模型答案。

## 未测

- **真机复测未测**：`grounded_reprobe.py` 在 16:03 拒跑，因为 `run_full_repair_v9.py` 和 `train_vericut_local_qlora.py` 正在占用测量链。
- **尚未接入生产链路**：`super_agent.py` 和 `scripts/workbuddy_virtu_bridge.py` 有别的会话的未提交改动，按 §8.3 没有去动。

## 边界

- 这是推理侧防线，**不是模型变强**。裸模型的能力仍要按原探针测；兜底次数不计入模型分。
- 题面解析靠正则；解析不出参数时原样放行模型输出，不会臆造参数。
- G71 门只核对程序文本，不等于 VERICUT 或机床仿真通过。
