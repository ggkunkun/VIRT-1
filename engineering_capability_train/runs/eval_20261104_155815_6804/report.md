# Virtu 工程能力评测报告

- 生成时间：2026-11-04T15:58:15+08:00
- 有效任务：139 / 总记录 149
- 本轮有效（transport_error <= 5%）：**True**
- 物理否决项通过：**True**
- **最终验收：FAIL**

## 量化指标

| 指标 | 数值 | 方向 | 权重 |
|---|---:|---|---:|
| task_success_rate | 1.0000 | higher | 0.24 |
| first_attempt_success_rate | 1.0000 | higher | 0.08 |
| physics_compliance_rate | 1.0000 | higher | 0.16 |
| decision_optimality_rate | 1.0000 | higher | 0.12 |
| semantic_grounding_rate | 1.0000 | higher | 0.1 |
| tool_call_valid_rate | 1.0000 | higher | 0.08 |
| parametric_model_valid_rate | 1.0000 | higher | 0.1 |
| gui_action_valid_rate | None | higher | 0.06 |
| error_rate | 0.0000 | lower | 0.06 |
| fatal_error_rate | 0.0000 | lower | 0.0 |
| transport_error_rate | 0.0000 | lower | 0.0 |
| latency_mean_s | None | lower | 0.0 |
| latency_p50_s | None | lower | 0.0 |
| latency_p95_s | None | lower | 0.0 |
| recovery_rate | None | higher | 0.0 |

| engineering_capability_score | 1.0000 | higher | — |

## 验收门

| 门 | 实测 | 阈值 | 结果 |
|---|---:|---:|---|
| task_success_rate_min | 1.0 | 0.85 | PASS |
| first_attempt_success_rate_min | 1.0 | 0.7 | PASS |
| physics_compliance_rate_min | 1.0 | 1.0 | PASS |
| decision_optimality_rate_min | 1.0 | 0.85 | PASS |
| semantic_grounding_rate_min | 1.0 | 0.8 | PASS |
| tool_call_valid_rate_min | 1.0 | 0.95 | PASS |
| parametric_model_valid_rate_min | 1.0 | 0.95 | PASS |
| gui_action_valid_rate_min | None | 0.98 | FAIL |
| error_rate_max | 0.0 | 0.1 | PASS |
| fatal_error_rate_max | 0.0 | 0.02 | PASS |
| transport_error_rate_max | 0.0 | 0.05 | PASS |
| latency_p95_s_max | None | 180.0 | FAIL |
| engineering_capability_score_min | 1.0 | 0.8 | PASS |
| min_valid_tasks | 139 | 30 | PASS |

## 口径说明

- transport_error / recorded_replay / 非 real 的 GUI 回放不计入能力分母，单独记覆盖损失
- 任何物理违规（体积不守恒 / FOS<1.5 / G00 扎刀 / 公差带为负 / 选中不可行候选）判该任务失败
- decision_optimality 要求 chosen 等于可行集里 cost=time*(1+0.5*risk) 的最小者
- 只有 gui_task_runner.py --backend real 的执行结果才计入 GUI 能力指标
