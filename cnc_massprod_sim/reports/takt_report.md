# 节拍统计数据

生成：2026-11-18 23:06:46
口径：确定性解释器逐段时长累计（路径长/进给 + 快移），basis=measured_deterministic_emulator。
不含机床加减速与换刀确认耗时，现场需实测标定。

| 工件 | 方言 | 段数 | 总时长s | 切削s | 快移s | 目标s | 判定 |
|---|---|---|---|---|---|---|---|
| WP-SHAFT-3JAW | fanuc | 51 | 101.06 | 98.53 | 2.53 | 95.0 | WARN |
| WP-SHAFT-3JAW | siemens | 48 | 88.53 | 86.49 | 2.04 | 95.0 | PASS |
| WP-SHAFT-3JAW | hnc | 51 | 101.06 | 98.53 | 2.53 | 95.0 | WARN |
| WP-MANIFOLD-VISE | fanuc | 110 | 66.65 | 57.32 | 9.33 | 130.0 | PASS |
| WP-MANIFOLD-VISE | siemens | 86 | 54.06 | 45.17 | 8.89 | 130.0 | PASS |
| WP-MANIFOLD-VISE | hnc | 110 | 66.65 | 57.32 | 9.33 | 130.0 | PASS |
| WP-HOUSING-FIXTURE | fanuc | 75 | 153.45 | 145.49 | 7.96 | 155.0 | PASS |
| WP-HOUSING-FIXTURE | siemens | 63 | 119.72 | 112.41 | 7.31 | 155.0 | PASS |
| WP-HOUSING-FIXTURE | hnc | 75 | 153.45 | 145.49 | 7.96 | 155.0 | PASS |

## 批量生产计划（源自 assurance.batch_plan）

| 工件 | 方言 | 批量 | 单件min | 换刀次数 | 总工时h | 一致性保障 |
|---|---|---|---|---|---|---|
| WP-SHAFT-3JAW | fanuc | 50 | 1.7 | 17 | 3.95 | 同程序哈希 + 同刀补/零点 + 首件与每 N 件抽检（Cpk≥1.33） |
| WP-SHAFT-3JAW | siemens | 50 | 1.5 | 15 | 3.48 | 同程序哈希 + 同刀补/零点 + 首件与每 N 件抽检（Cpk≥1.33） |
| WP-SHAFT-3JAW | hnc | 50 | 1.7 | 17 | 3.95 | 同程序哈希 + 同刀补/零点 + 首件与每 N 件抽检（Cpk≥1.33） |
| WP-MANIFOLD-VISE | fanuc | 50 | 1.1 | 9 | 2.28 | 同程序哈希 + 同刀补/零点 + 首件与每 N 件抽检（Cpk≥1.33） |
| WP-MANIFOLD-VISE | siemens | 50 | 0.9 | 7 | 1.8 | 同程序哈希 + 同刀补/零点 + 首件与每 N 件抽检（Cpk≥1.33） |
| WP-MANIFOLD-VISE | hnc | 50 | 1.1 | 9 | 2.28 | 同程序哈希 + 同刀补/零点 + 首件与每 N 件抽检（Cpk≥1.33） |
| WP-HOUSING-FIXTURE | fanuc | 50 | 2.6 | 17 | 4.68 | 同程序哈希 + 同刀补/零点 + 首件与每 N 件抽检（Cpk≥1.33） |
| WP-HOUSING-FIXTURE | siemens | 50 | 2.0 | 13 | 3.61 | 同程序哈希 + 同刀补/零点 + 首件与每 N 件抽检（Cpk≥1.33） |
| WP-HOUSING-FIXTURE | hnc | 50 | 2.6 | 17 | 4.68 | 同程序哈希 + 同刀补/零点 + 首件与每 N 件抽检（Cpk≥1.33） |
