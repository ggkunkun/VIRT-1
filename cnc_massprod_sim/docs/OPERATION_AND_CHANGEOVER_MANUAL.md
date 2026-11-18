# 数控加工仿真系统 — 操作与换产配置手册

版本 1.0.0  生成：2026-11-18 23:29:24

## 0. 系统定位与诚实边界

本系统为量产级数控加工仿真与验证 Agent，控制器逻辑对齐 FANUC 0i /
SINUMERIK 840D sl / 华中 HNC-8 公开编程手册，由确定性解释器实测。
**边界**：逻辑对齐公开规范 ≠ 任何具体机床的现场标定；逐帧干涉为几何
实测而非 VERICUT 布尔材料去除；Cpk/良品率若无实测样本标 simulated。
投入实际量产前必须完成：机床特定后处理核对、VERICUT 机床模型标定、
首件试切与三坐标实测。

## 1. 环境

- Python 3.12+（工作区 .venv），依赖 numpy / scipy / trimesh / pyyaml / asyncua
- 工作区：D:/Virtu模型

## 2. 运行

```bash
cd D:/Virtu模型/cnc_massprod_sim
../.venv/Scripts/python.exe run_sim.py            # 全部工件×方言
../.venv/Scripts/python.exe run_sim.py --step 0.5 --batch 50
../.venv/Scripts/python.exe run_sim.py --workpiece WP-SHAFT-3JAW --dialect fanuc
```

## 3. 支持的工件与控制系统

| 工件ID | 名称 | 材料 | 方言 | 控制器 | VERICUT CTL |
|---|---|---|---|---|---|
| WP-SHAFT-3JAW | 40Cr精密阶梯传动轴（三爪卡盘车削） | 40Cr | fanuc | fanuc_0i_tf | fan0t.ctl |
| WP-SHAFT-3JAW | 40Cr精密阶梯传动轴（三爪卡盘车削） | 40Cr | siemens | siemens_840d_sl | sin840d.ctl |
| WP-SHAFT-3JAW | 40Cr精密阶梯传动轴（三爪卡盘车削） | 40Cr | hnc | hnc_8t | fan0t.ctl |
| WP-MANIFOLD-VISE | AL7075-T6液压集成阀块（精密虎钳三轴铣削） | AL7075-T6 | fanuc | fanuc_0i_mf | fan0m.ctl |
| WP-MANIFOLD-VISE | AL7075-T6液压集成阀块（精密虎钳三轴铣削） | AL7075-T6 | siemens | siemens_840d_sl | sin840d.ctl |
| WP-MANIFOLD-VISE | AL7075-T6液压集成阀块（精密虎钳三轴铣削） | AL7075-T6 | hnc | hnc_8m | huazhong_hnc.ctl |
| WP-HOUSING-FIXTURE | 45钢法兰轴承座（专用一面两销零点夹具铣削） | Steel45 | fanuc | fanuc_0i_mf | fan0m.ctl |
| WP-HOUSING-FIXTURE | 45钢法兰轴承座（专用一面两销零点夹具铣削） | Steel45 | siemens | siemens_840d_sl | sin840d.ctl |
| WP-HOUSING-FIXTURE | 45钢法兰轴承座（专用一面两销零点夹具铣削） | Steel45 | hnc | hnc_8m | huazhong_hnc.ctl |

## 4. 换产配置（SMED，目标 ≤15 min）

| 步骤 | 计划分钟 |
|---|---|
| 夹具/软爪更换与找正 | 4.0 |
| 刀具装载与对刀（T1/T2） | 3.0 |
| 程序调用与刀补/零点写入 | 2.0 |
| 空运行与首件试切（含 M01 检查） | 4.0 |
| 首件三坐标/目视确认 | 1.5 |

现场换装计划合计 14.5 min；软件重构实测 0.0 s；总 14.5 min（PASS）。

口径：on-site=planned (需车间实测), software=measured

## 5. 断点续传与急停

- FANUC/HNC：程序头 #501=10/20/30/40 选择起始工序，GOTO 跳转；
  同时支持 N100/N200/N300/N400 顺序号搜索（Q-TYPE 刀具入口重启）。
- 西门子 840D sl：SERUPRO / 程序段搜索重启。
- 急停：CNC 面板 E-STOP 触发后 INTERLOCK 禁止进入 AUTO 模式；
  警报代码 EMG-001；复位需 release_e_stop_and_reset。
- 超程防护：双软限位（Stored Stroke Check 1&2）+ OT-X/Y/Z 报警。

## 6. 刀具补偿与换刀

- 长度补偿：FANUC/HNC G43 Hxx / G49；五轴 G43.4；西门子 T-D 刀沿。
- 半径补偿：G41/G42 Dxx，线性段引入/引出，G40 关闭（成对校验）。
- 换刀：G28 U0 W0 回参考点 → 换刀点 → Txxxx M06 → 补偿激活。
- ATC 校验：换刀前必须在换刀点（TOOL-CHANGE-POINT 判据）。

## 7. OPC UA 产线对接

端点：opc.tcp://<host>:4840/virtu/；命名空间 urn:virtu:production。
节点见 reports/opcua_nodes.md；自检见 verification_result.json.opcua。

## 8. 输出物

- programs/：三方言 × 三工件 NC 程序集（FANUC .nc / Siemens .mpf / HNC .nc）
- reports/：仿真验证报告、干涉检测报告、精度校验、节拍统计、参数清单
- logs/：仿真运行日志（逐条程序门结果）
- reports/verification_result.json：机器可读全量结果

## 9. 免责声明

本系统输出不得在未完成现场机床标定、后处理核对、首件试切与
VERICUT Auto-Diff 验证前直接用于实际生产。所有程序以仿真验证为目的。
