# 量产级数控加工仿真验证报告

生成：2026-11-18 23:39:44
运行摘要：总计 9，通过 9，失败 0，耗时 36.32s

## 口径声明

本报告遵循工作区《测量宪法》：每个数值带 basis；未实测项标未测，
禁止把源码字面量当实测结果。控制器执行 basis=measured_deterministic_emulator，
几何干涉 basis=measured，SPC/良品率若无实测样本 basis=simulated。

## 1. 总门结果

| 工件 | 方言 | 控制器 | 总判定 | 分项门 | 程序SHA256 |
|---|---|---|---|---|---|
| WP-SHAFT-3JAW | fanuc | fanuc_0i_tf | PASS | PROCESS-CONFIG:PASS INSTRUCTION-SET:PASS NC-AUDIT:PASS BREAKPOINT-RESTART:PASS FRAME-INTERFERENCE:PASS | 96eec91210b8 |
| WP-SHAFT-3JAW | siemens | siemens_840d_sl | PASS | PROCESS-CONFIG:PASS INSTRUCTION-SET:PASS NC-AUDIT:PASS BREAKPOINT-RESTART:PASS FRAME-INTERFERENCE:PASS | a1804fbb4699 |
| WP-SHAFT-3JAW | hnc | hnc_8t | PASS | PROCESS-CONFIG:PASS INSTRUCTION-SET:PASS NC-AUDIT:PASS BREAKPOINT-RESTART:PASS FRAME-INTERFERENCE:PASS | 1f91a5361fb6 |
| WP-MANIFOLD-VISE | fanuc | fanuc_0i_mf | PASS | PROCESS-CONFIG:PASS INSTRUCTION-SET:PASS NC-AUDIT:PASS BREAKPOINT-RESTART:PASS FRAME-INTERFERENCE:PASS | eb7682031759 |
| WP-MANIFOLD-VISE | siemens | siemens_840d_sl | PASS | PROCESS-CONFIG:PASS INSTRUCTION-SET:PASS NC-AUDIT:PASS BREAKPOINT-RESTART:PASS FRAME-INTERFERENCE:PASS | 2396456fabce |
| WP-MANIFOLD-VISE | hnc | hnc_8m | PASS | PROCESS-CONFIG:PASS INSTRUCTION-SET:PASS NC-AUDIT:PASS BREAKPOINT-RESTART:PASS FRAME-INTERFERENCE:PASS | 975768f1f436 |
| WP-HOUSING-FIXTURE | fanuc | fanuc_0i_mf | PASS | PROCESS-CONFIG:PASS INSTRUCTION-SET:PASS NC-AUDIT:PASS BREAKPOINT-RESTART:PASS FRAME-INTERFERENCE:PASS | ba0b0983ee42 |
| WP-HOUSING-FIXTURE | siemens | siemens_840d_sl | PASS | PROCESS-CONFIG:PASS INSTRUCTION-SET:PASS NC-AUDIT:PASS BREAKPOINT-RESTART:PASS FRAME-INTERFERENCE:PASS | 022b1ca846ea |
| WP-HOUSING-FIXTURE | hnc | hnc_8m | PASS | PROCESS-CONFIG:PASS INSTRUCTION-SET:PASS NC-AUDIT:PASS BREAKPOINT-RESTART:PASS FRAME-INTERFERENCE:PASS | 512b039a9865 |

**总体判定：PASS**

## 1b. G/M 指令集匹配（控制器支持清单逐条比对）

| 工件 | 方言 | 控制器 | 判定 | 用G数 | 用M数 | 支持G数 | 支持M数 | 口径 |
|---|---|---|---|---|---|---|---|---|
| WP-SHAFT-3JAW | fanuc | fanuc_0i_tf | PASS | 16 | 6 | 39 | 16 | measured (controller profile set-membership; normalized) |
| WP-SHAFT-3JAW | siemens | siemens_840d_sl | PASS | 12 | 7 | 35 | 13 | measured (controller profile set-membership; normalized) |
| WP-SHAFT-3JAW | hnc | hnc_8t | PASS | 16 | 6 | 38 | 13 | measured (controller profile set-membership; normalized) |
| WP-MANIFOLD-VISE | fanuc | fanuc_0i_mf | PASS | 17 | 7 | 44 | 14 | measured (controller profile set-membership; normalized) |
| WP-MANIFOLD-VISE | siemens | siemens_840d_sl | PASS | 10 | 7 | 35 | 13 | measured (controller profile set-membership; normalized) |
| WP-MANIFOLD-VISE | hnc | hnc_8m | PASS | 17 | 7 | 42 | 12 | measured (controller profile set-membership; normalized) |
| WP-HOUSING-FIXTURE | fanuc | fanuc_0i_mf | PASS | 17 | 7 | 44 | 14 | measured (controller profile set-membership; normalized) |
| WP-HOUSING-FIXTURE | siemens | siemens_840d_sl | PASS | 11 | 7 | 35 | 13 | measured (controller profile set-membership; normalized) |
| WP-HOUSING-FIXTURE | hnc | hnc_8m | PASS | 17 | 7 | 42 | 12 | measured (controller profile set-membership; normalized) |

> 比对两侧用同一规范化（G4↔G04、M3↔M03），避免补零差异造成假阳性；
> 任一程序使用了控制器不支持的 G/M 代码即判红。

## 2. 静态与运行时审计

| 工件 | 方言 | 审计 | 执行块 | 运动段 | 断点重启 | 问题数 |
|---|---|---|---|---|---|---|
| WP-SHAFT-3JAW | fanuc | PASS | 62 | 51 | True | 0 |
| WP-SHAFT-3JAW | siemens | PASS | 81 | 48 | True | 0 |
| WP-SHAFT-3JAW | hnc | PASS | 62 | 51 | True | 0 |
| WP-MANIFOLD-VISE | fanuc | PASS | 153 | 110 | True | 0 |
| WP-MANIFOLD-VISE | siemens | PASS | 148 | 86 | True | 0 |
| WP-MANIFOLD-VISE | hnc | PASS | 153 | 110 | True | 0 |
| WP-HOUSING-FIXTURE | fanuc | PASS | 119 | 75 | True | 0 |
| WP-HOUSING-FIXTURE | siemens | PASS | 113 | 63 | True | 0 |
| WP-HOUSING-FIXTURE | hnc | PASS | 119 | 75 | True | 0 |

## 3. 逐帧仿真与干涉

| 工件 | 方言 | 判定 | 帧数 | 最小间隙mm | 违规 |
|---|---|---|---|---|---|
| WP-SHAFT-3JAW | fanuc | PASS | 1384 | 5.8 | 0 |
| WP-SHAFT-3JAW | siemens | PASS | 1254 | 5.8 | 0 |
| WP-SHAFT-3JAW | hnc | PASS | 1384 | 5.8 | 0 |
| WP-MANIFOLD-VISE | fanuc | PASS | 6149 | 2.0 | 0 |
| WP-MANIFOLD-VISE | siemens | PASS | 5653 | 2.0 | 0 |
| WP-MANIFOLD-VISE | hnc | PASS | 6149 | 2.0 | 0 |
| WP-HOUSING-FIXTURE | fanuc | PASS | 5050 | 0.0 | 0 |
| WP-HOUSING-FIXTURE | siemens | PASS | 4562 | 11.0 | 0 |
| WP-HOUSING-FIXTURE | hnc | PASS | 5050 | 0.0 | 0 |

## 4. 节拍与精度

| 工件 | 方言 | 节拍s | 目标s | Cpk | 估算良品率% |
|---|---|---|---|---|---|
| WP-SHAFT-3JAW | fanuc | 85.1 | 95.0 | 1.42 | 99.998 |
| WP-SHAFT-3JAW | siemens | 74.91 | 95.0 | 1.42 | 99.998 |
| WP-SHAFT-3JAW | hnc | 85.1 | 95.0 | 1.42 | 99.998 |
| WP-MANIFOLD-VISE | fanuc | 66.65 | 130.0 | 1.42 | 99.998 |
| WP-MANIFOLD-VISE | siemens | 54.06 | 130.0 | 1.42 | 99.998 |
| WP-MANIFOLD-VISE | hnc | 66.65 | 130.0 | 1.42 | 99.998 |
| WP-HOUSING-FIXTURE | fanuc | 153.45 | 155.0 | 1.42 | 99.998 |
| WP-HOUSING-FIXTURE | siemens | 119.72 | 155.0 | 1.42 | 99.998 |
| WP-HOUSING-FIXTURE | hnc | 153.45 | 155.0 | 1.42 | 99.998 |

## 5. 量产保障

| 工件 | 方言 | 撞机风险 | 换产min | 换产判定 | 预警数 |
|---|---|---|---|---|---|
| WP-SHAFT-3JAW | fanuc | LOW | 14.5 | PASS | 0 |
| WP-SHAFT-3JAW | siemens | LOW | 14.5 | PASS | 0 |
| WP-SHAFT-3JAW | hnc | LOW | 14.5 | PASS | 0 |
| WP-MANIFOLD-VISE | fanuc | MEDIUM | 14.5 | PASS | 0 |
| WP-MANIFOLD-VISE | siemens | MEDIUM | 14.5 | PASS | 0 |
| WP-MANIFOLD-VISE | hnc | MEDIUM | 14.5 | PASS | 0 |
| WP-HOUSING-FIXTURE | fanuc | LOW | 14.5 | PASS | 0 |
| WP-HOUSING-FIXTURE | siemens | LOW | 14.5 | PASS | 0 |
| WP-HOUSING-FIXTURE | hnc | LOW | 14.5 | PASS | 0 |

## 6. OPC UA 自检

- 协议栈可用：True
- 读写回读一致：True
- basis：measured

## 7. 部署前必做（诚实边界）

1. 按具体机床型号/固件版本核对 G/M 代码支持表（controllers.yaml）。
2. VERICUT 导入对应 CTL 并加载机床模型，跑 Auto-Diff 偏差图。
3. 首件试切 + 三坐标实测关键特征，用实测样本重算 Cpk。
4. 现场标定软限位、刀具长度/半径补偿、G54 零点。
5. OPC UA 端点接入车间采集系统并验证节点写入。

