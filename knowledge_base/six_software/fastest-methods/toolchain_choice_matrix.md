# 跨软件选型矩阵（toolchain_choice_matrix.md）

> 阶段 A 产物 · 2026-11-04 · 「什么任务 → 用哪个软件 → 哪条路最快」
> 判定依据：`fastest-methods.md` 总表 + 各 `<software>.md` 路线全集与 7 维度量；证据三态与历史实测优先原则见 `FASTEST_METHODS_CONTRACT.md` §4-§6。

---

## 1. 任务原型 → 首选软件+最快路线（选型表）

| 任务原型 | 首选（软件·路线） | 备选 | 判定要点 | 置信度 |
| :-- | :-- | :-- | :-- | :-- |
| 2D 大批量新图/标注（数十张） | **AutoCAD · ezdxf 文件级** | accoreconsole+SCR | 零进程、可并行、确定性高；ezdxf R2018 verified-working | [高] |
| 2D 批量改既有 dwg | **AutoCAD · accoreconsole /i /s 多实例并发** | ezdxf 读改写 | 无头批处理可并行；verified-working | [高] |
| 2D 单件快速出图/三视图 | **SOLIDWORKS · COM create_drawing** | AutoCAD COM 温通道 | SW 工程图含三视图+标注，COM 常驻 1 调用 | [高] |
| 3D 单件参数化建模 | 下游在 NX CAM → **NX · NXOpen Journal**；下游在 SW 装配/出图 → **SW · COM 早绑定** | GUI 手工 | 二者均 verified-working [高]；按下游链路选型 | [高] |
| 3D 批量改参/批量建模 | **NX · NXOpen Python Journal（run_journal.exe 批量）** | SW 方程驱动/宏 | run_journal 对象级批量+ΔV≠0；SW 宏仅 .swp | [高] |
| 2.5D 拉伸造型 | **AutoCAD · COM SendCommand EXTRUDE** | GUI | 仅 2.5D 职责域；COM 温通道 | [中] |
| FEA 强度校核（FOS≥1.5） | **SOLIDWORKS · Simulation add-in API 静应力** | NX CAE GUI+Nastran | API 常驻可脚本回环；FOS≥1.5 闭环公理 | [中] |
| 切削仿真·首次验证 | **VERICUT · CGTECH_VCPROJECT 自动加载 + GUI 播放(1890,860) 核 ActionMainPlay** | CGTECH_TRANSACTION_LOG 审计 | 历史实测首证链；GUI 仅复核用途 | [高] |
| 切削仿真·批量复核 | **VERICUT · .vcreview 回读** | 日志数值解析 | 文件级秒级可并行、227MB 实测；batchp/batcht confirmed-negative 禁用 | [高] |
| NC 语法/Macro B 校验 | **CIMCO · 外部 Python Macro B 校验** | CIMCO GUI CycleMacro | 外部脚本常驻+可并行+verified-working | [高] |
| G00 快速进给碰撞哨兵 | **CIMCO · 背绘 G00 哨兵（外部脚本）** | GUI 背绘 | verified-working 桥接 vs GUI documented-not-probed | [高] |
| 后处理生成 | **NX · Post Builder 三件套（.pui/.tcl/.def）** | YANGJEE 外挂 70+ 后处理 | 操作导航器 `!` 消除后 Post（AGENTS.md 公理） | [中] |
| 虚拟面板操作验证 | **SSCNC · 离线算对刀量预生成 + CRT 三页核对** | 多控制器并行 | 离线算 verified-working；面板触发 documented-not-probed，启动前必核对 | [中] |
| 多软件接力（CAD→CAM→仿真） | 按 AGENTS.md 闭环：SW/NX 建模 → NX CAM → CIMCO 校验 → VERICUT Auto-Diff → SSCNC 面板验证 | — | 各接力点用本矩阵最快路线，检查点公理对齐 | [高] |

## 2. 通道优先级原则（选型第一判据）

1. **文件级/无头通道**（ezdxf / accoreconsole / run_journal / .vcreview / 外部 Python 脚本）：零或低启动、可并行、确定性高 → **批量首选**。
2. **常驻 API**（SW COM 早绑定 / NXOpen 对象级 / CIMCO 外部校验）：1-2 调用、可脚本化 → **单件/自动化首选**。
3. **GUI**：冷启动（SLDWORKS 30-60s [估算]）、坐标脆弱（分辨率/焦点）、不可并行 → **仅首证/人工复核**，绝不作批量路线。
4. **批处理开关**（VERICUT batchp/batcht、SW RunMacro(.swp)）：有 confirmed-negative / 有限约束记录的，**默认排除**，除非知识库另有 verified-working 记录。

## 3. 跨软件路由规则

- **N/A 职责域路由**：2D 制图 → AutoCAD/NX/SW；3D 建模 → SW/NX（按下游）；FEA → SW Simulation；切削仿真 → VERICUT；面板验证 → SSCNC；CIMCO 只管 NC 校验/转换/背绘，不承担建模与绘图。
- **CAM 接力**：加工主职 = NX CAM；SW CAM add-in 仅辅助（documented-not-probed）；刀路产出后必走 CIMCO 校验（Macro B + G00 哨兵）→ VERICUT 仿真（首证 GUI、批量 vcreview）→ SSCNC 面板复核（可选）。
- **批量优先文件级**：任何"批量/大量/重复"任务，先问文件级通道是否可行（ezdxf/accoreconsole/vcreview/run_journal），再退 API，最后 GUI。
- **证据兜底**：选型结论与知识库 E-ID 冲突时以 E-ID 为准；无证据的路线不存在。

## 4. 证据与置信度图例

- [高]：历史实测 verified-working（或 N/A 职责判定明确）；
- [中]：官方文档 + 结构化推理（含 documented-not-probed 但确定性高的 API 路线）；
- [低]：纯推测 / documented-not-probed 且无确定性支撑（标出失败风险后仍可用作备选）；
- 所有时间量级无实测处标 [估算]；禁止臆造实测数据。
