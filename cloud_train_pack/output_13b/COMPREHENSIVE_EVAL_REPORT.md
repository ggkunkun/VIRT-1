# Virtu 全维度能力全面测评验收报告

- **测试日期**：2026-11-07 05:54:14
- **被测模型**：`/model/ModelScope/Qwen/Qwen3-14B` + Adapter `/root/virtu_13b_train/cloud_train_pack/output_13b/adapter_13b_sft`
- **归因指纹**：git `unknown`，用例 sha256 前缀 `3546c40f3ce8`，逐题响应见 `raw.jsonl`（5 条）
- **维度覆盖**：1/8 维（权重覆盖 0.12）；缺 ['generalization', 'generation', 'instruction', 'knowledge', 'multimodal', 'reasoning', 'toolcall']
- **综合加权得分**：`54.67 / 100`（按已覆盖权重归一）
- **物理规律合规率**：`36.7%`（实测 11/30，判据＝求解器复算+守恒式同时通过）(否决项)
- **高分验收结论**：**【未通过】** boundary (54.7 < 90.0)；coverage (1/8 维, 缺 ['generalization', 'generation', 'instruction', 'knowledge', 'multimodal', 'reasoning', 'toolcall'])；physics_gate (36.7% < 100%, 11/30)

> **口径警告**：表中「常量基座/常量v2/常量v3」三列是本文件手写的常量，仓内没有可复现它们的 raw 记录，**不得引用为历史实测成绩**；本报告的对比一律以带 manifest 指纹的 run 目录为准。

## 维度对比矩阵

| 维度 | 权重 | 常量基座* | 常量v2* | 常量v3* | 本次实测得分 | 难度分布(Easy/Med/Hard) | 状态 |
|---|---|---|---|---|---|---|---|
| **边界处理** (boundary) | 0.12 | 36.4 | 62.5 | 74.8 | **54.7** | 54.7 / 0.0 / 0.0 | ⚠️ 未达标 |
| **综合总分** | **1.00** | **53.9** | **68.4** | **75.2** | **54.7** | — | **⚠️ 未通过: boundary (54.7 < 90.0); coverage (1/8 维, 缺 ['generalization', 'generation', 'instruction', 'knowledge', 'multimodal', 'reasoning', 'toolcall']); physics_gate (36.7% < 100%, 11/30)** |

