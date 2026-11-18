# 精度校验数据

生成：2026-11-18 23:29:24
说明：Cpk/SPC 若有实测样本则 basis=measured；未提供实测样本时
按声明 σ 生成 basis=simulated 样本，绝不冒充实测。

| 工件 | 方言 | Cpk(仿真) | Cp | 目标Cpk | 对目标判定 | 声明σ mm | 估算良品率% |
|---|---|---|---|---|---|---|---|
| WP-SHAFT-3JAW | fanuc | 1.42 | 1.54 | 1.67 | WARN | 0.00998 | 99.998 |
| WP-SHAFT-3JAW | siemens | 1.42 | 1.54 | 1.67 | WARN | 0.00998 | 99.998 |
| WP-SHAFT-3JAW | hnc | 1.42 | 1.54 | 1.67 | WARN | 0.00998 | 99.998 |
| WP-MANIFOLD-VISE | fanuc | 1.42 | 1.54 | 1.67 | WARN | 0.00998 | 99.998 |
| WP-MANIFOLD-VISE | siemens | 1.42 | 1.54 | 1.67 | WARN | 0.00998 | 99.998 |
| WP-MANIFOLD-VISE | hnc | 1.42 | 1.54 | 1.67 | WARN | 0.00998 | 99.998 |
| WP-HOUSING-FIXTURE | fanuc | 1.42 | 1.54 | 1.67 | WARN | 0.00998 | 99.998 |
| WP-HOUSING-FIXTURE | siemens | 1.42 | 1.54 | 1.67 | WARN | 0.00998 | 99.998 |
| WP-HOUSING-FIXTURE | hnc | 1.42 | 1.54 | 1.67 | WARN | 0.00998 | 99.998 |

> 注：Cpk 为 basis=simulated（按目标能力反推声明 σ 生成样本），
> 非实测；`对目标判定=WARN` 表示仿真样本 Cpk 未达工件原型目标，
> 需现场首件实测复核。良品率为正态假设下由 Cpk 反推，同为仿真值。


## 关键特征公差（源自工件原型 / ISO 286）

| 工件 | 特征 | 公称mm | 上偏差 | 下偏差 |
|---|---|---|---|---|
| WP-SHAFT-3JAW | OD_28h6 | 28.0 | 0.0 | -0.013 |
| WP-SHAFT-3JAW | OD_40k6 | 40.0 | 0.018 | 0.002 |
| WP-SHAFT-3JAW | OD_50g6 | 50.0 | -0.009 | -0.025 |
| WP-MANIFOLD-VISE | POCKET_W_76H8 | 76.0 | 0.046 | 0.0 |
| WP-MANIFOLD-VISE | POCKET_L_48H8 | 48.0 | 0.039 | 0.0 |
| WP-MANIFOLD-VISE | CONTOUR_120js7 | 120.0 | 0.018 | -0.018 |
| WP-HOUSING-FIXTURE | BORE_52H7 | 52.0 | 0.03 | 0.0 |
| WP-HOUSING-FIXTURE | POS_BOLT_4X11 | 11.0 | 0.043 | 0.0 |
