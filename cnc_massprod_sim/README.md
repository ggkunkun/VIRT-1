# 量产级数控加工仿真 Agent — 交付物索引

生成版本 1.0.0 ｜ 运行入口：`../.venv/Scripts/python.exe run_sim.py`

## 一、可运行系统（源码）
| 文件 | 职责 |
|---|---|
| `run_sim.py` | 命令行入口（--workpiece / --dialect / --step / --batch / --out / --no-opcua） |
| `src/cnc_massprod_sim/config.py` | 装载 controllers.yaml + 工件原型 + 方言映射 |
| `src/cnc_massprod_sim/agent.py` | 主编排器：配置→NC→审计→逐帧仿真→门判定 |
| `src/cnc_massprod_sim/geometry.py` | 逐帧扫掠干涉/撞机/超程几何内核（可证伪） |
| `src/cnc_massprod_sim/assurance.py` | 刀具磨损/撞机风险/SPC/节拍/换产/OPC UA |
| `src/cnc_massprod_sim/reporting.py` | 全部交付物生成 |
| `config/controllers.yaml` | 5 种控制器完整 profile（G/M 指令集、面板模式、软限位、CTL） |
| `tests/test_massprod_sim.py` | 15 项反证测试（植入坏样本必红，含指令集不匹配） |

## 二、配置文件
- `config/controllers.yaml` — FANUC 0i-MF/TF、SIEMENS 840D sl、HNC-8M/T 指令集与模态组。

## 三、量产 G-code 程序集（`programs/`，9 套）
- 三工件 × 三方言：阶梯轴（车削）、歧管块（虎钳铣）、壳体（专用夹具铣）。
- FANUC/HNC `.nc`，SIEMENS `.mpf`；含工序分层、G43/G41 补偿、M06 换刀、断点、M30。

## 四、仿真验证报告（`reports/`）
| 文件 | 内容 |
|---|---|
| `SIMULATION_VERIFICATION_REPORT.md` | 主报告：总门/审计/干涉/节拍精度/量产保障/OPC UA/边界 |
| `verification_result.json` | 机器可读全量结果（含每条门 basis） |
| `interference_report.md` | 逐帧干涉检测 + 有界豁免 |
| `precision_report.md` | 精度校验 + 关键特征公差（ISO 286） |
| `takt_report.md` | 节拍统计 + 批量生产计划 |
| `parameter_checklist.md` | 全维度工艺参数校验清单（带标准出处） |
| `opcua_nodes.md` | OPC UA 信息模型节点表 |

## 五、操作手册
- `docs/OPERATION_AND_CHANGEOVER_MANUAL.md` — 系统操作、换产 SMED（≤15min）、断点/急停、补偿/换刀、OPC UA 对接、免责声明。

## 六、运行日志
- `logs/simulation_run.log` — 逐条程序门结果。

## 诚实边界（重要）
本系统是**仿真与验证**工具，非任何具体机床的现场控制系统。控制器逻辑对齐三系统公开编程手册并经确定性解释器实测；干涉为几何实测而非 VERICUT 布尔材料去除；Cpk/良品率无实测样本时标 `simulated`。投入实际量产前必须完成：机床特定后处理核对、VERICUT 机床模型标定与 Auto-Diff、首件试切与三坐标实测、现场软限位/补偿/零点标定。详见主报告第 7 节与手册第 9 节。
