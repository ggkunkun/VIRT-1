# 系统操作与换产配置手册 — AE-CI-258

## 1. 开机与工位确认

1. 确认机床 B/C 回零、刀库 T1/T2 在位、冷却液液位与压力。
2. 调用程序（按控制系统）：见下表。
3. 核对 G54：X0Y0 = 毛坯上表面中心，Z0 = 上表面；用寻边器/探针复检并记录。
4. 首件前执行空运行（机床锁住 + 图形校验），确认无超程与干涉。

| 工序 | 方言 | 机床 | NC 文件 | 断点 N 号 |
|---|---|---|---|---|
| OP1 | fanuc | prod_5ax_fanuc_0imf | D:\Virtu模型\production\nc\prod_5ax_fanuc_0imf\AE-CI-258_OP1.nc | {'OP1': 40} |
| OP2 | fanuc | prod_5ax_fanuc_0imf | D:\Virtu模型\production\nc\prod_5ax_fanuc_0imf\AE-CI-258_OP2.nc | {'OP2': 40} |
| OP3 | fanuc | prod_5ax_fanuc_0imf | D:\Virtu模型\production\nc\prod_5ax_fanuc_0imf\AE-CI-258_OP3.nc | {'OP3-A': 40, 'OP3-B': 420} |
| OP1 | siemens | prod_5ax_siemens_840dsl | D:\Virtu模型\production\nc\prod_5ax_siemens_840dsl\AE-CI-258_OP1.nc | {'OP1': 30} |
| OP2 | siemens | prod_5ax_siemens_840dsl | D:\Virtu模型\production\nc\prod_5ax_siemens_840dsl\AE-CI-258_OP2.nc | {'OP2': 30} |
| OP3 | siemens | prod_5ax_siemens_840dsl | D:\Virtu模型\production\nc\prod_5ax_siemens_840dsl\AE-CI-258_OP3.nc | {'OP3-A': 30, 'OP3-B': 390} |
| OP1 | hnc | prod_5ax_hnc8 | D:\Virtu模型\production\nc\prod_5ax_hnc8\AE-CI-258_OP1.nc | {'OP1': 40} |
| OP2 | hnc | prod_5ax_hnc8 | D:\Virtu模型\production\nc\prod_5ax_hnc8\AE-CI-258_OP2.nc | {'OP2': 40} |
| OP3 | hnc | prod_5ax_hnc8 | D:\Virtu模型\production\nc\prod_5ax_hnc8\AE-CI-258_OP3.nc | {'OP3-A': 40, 'OP3-B': 420} |

## 2. 换产流程（目标 ≤15 min）

| 步骤 | 计划(min) |
|---|---|
| 夹具/软爪更换与找正 | 4.0 |
| 刀具装载与对刀（T1/T2） | 3.0 |
| 程序调用与刀补/零点写入 | 2.0 |
| 空运行与首件试切（含 M01 检查） | 4.0 |
| 首件三坐标/目视确认 | 1.5 |

- 软件侧重构实测：0.13 s
- 合计（现场计划 + 软件实测）：14.5 min → PASS

## 3. 断点接续

1. 可选停止 M01 停在每个工序结束；按循环启动继续。
2. 断刀/断电后按断点 N 号做程序再启动（BLOCK SEARCH / 搜索执行）。
3. 再启动前必须确认：刀长补偿已重新对刀、G54 未变、B/C 已回零。

## 4. 报警与处置

| 报警 | 触发条件 | 处置 |
|---|---|---|
| 刀具磨损 WARN/ALARM | 磨损率 ≥80% / ≥100% | 提前/立即换刀并复位寿命计数 |
| 撞机风险 HIGH/CRITICAL | 最小间隙 <1 mm / <0 | 停机复核夹具与刀柄，禁止强制运行 |
| 超差 OUT_OF_TOLERANCE | Cpk<1.33 或有超差件 | 隔离首件，复测并调整刀补 |
| 节拍超目标 | 单工序 > 目标节拍 | 复核进给与空切比例，按工艺变更单调整 |

## 5. OPC UA 采集

- 端点：opc.tcp://127.0.0.1:4840/virtu/
- 节点：State, Part, ProgramHash, BatchCount, CycleTime_s, MinClearance_mm, Cpk, ToolWear_pct, AlarmCode, AlarmText
- 采集周期建议 1 s；报警节点写 1 触发产线看板。

## 6. 现场安全边界（不可编程替代）

- 硬件急停、门锁、软限位（存储行程）必须由机床参数与安全回路实现；NC 侧仅提供 M00/M01 停止与安全高度/补偿逻辑。
- 首次上机必须空运行 + 单段试切；本报告不替代实机首件确认。
