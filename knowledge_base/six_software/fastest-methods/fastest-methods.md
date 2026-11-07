# 六软件最快方法总表（fastest-methods.md）

> 阶段 A 产物 · 2026-11-04 · 让 Virtu 模型「自己找画图/建模/仿真/加工的最快方法」
> 本表为**归并总表**：每软件 × 每任务族给「最快路线 + 次优备选 + 判定依据 + 置信度」；每格完整路线全集（通道类型/调用路径/证据链接）与 7 维度量（步骤数/调用数/启动开销/可并行度/证据等级/确定性/失败风险）见各软件独立文档：
> `solidworks.md` / `autocad.md` / `nx.md` / `cimco.md` / `vericut.md` / `sscnc.md`
> 格式契约：`FASTEST_METHODS_CONTRACT.md`。历史实测优先引用，无实测不臆造（时间量级标 [估算]）。

---

## 1. 画图（2D drafting）

| 软件 | 最快路线 | 次优备选 | 判定依据（简） | 置信度 |
| :-- | :-- | :-- | :-- | :-- |
| SOLIDWORKS | **COM/API 早绑定出图**（create_drawing） | 方程联动出图 | 1 调用、常驻、确定性高（API），verified-working；出工程图含三视图+标注 | [高] |
| AutoCAD | **ezdxf 文件级**（单件/参数化）：零进程、可并行、确定性高 | accoreconsole+SCR（已开图温通道） | ezdxf R2018 文件级 verified-working，0 步骤启动；大批量另见 accoreconsole | [高] |
| AutoCAD（批量改既有 dwg） | **accoreconsole /i /s 多实例并发** | ezdxf 读改写 | 无头批处理可并行；verified-working | [高] |
| NX | **NXOpen Python Journal 批量出图** | GUI Drafting | Journal 2 步+对象级 vs GUI 8 步+15 菜单；run_journal verified-working | [中] |
| CIMCO | **N/A** | — | NC 编辑器职责域不含 2D 绘图（路由至 AutoCAD/NX） | [高]（N/A 判定） |
| VERICUT | **N/A** | — | 切削仿真验证器，无 2D 绘图职责 | — |
| SSCNC | **N/A** | — | 数控操作仿真器，无绘图职责 | — |

## 2. 建模（3D modeling）

| 软件 | 最快路线 | 次优备选 | 判定依据（简） | 置信度 |
| :-- | :-- | :-- | :-- | :-- |
| SOLIDWORKS | **COM 早绑定参数化建模** | 方程驱动（EquationMgr） | 1-2 API 调用、常驻、确定性高；verified-working；体积守恒 ΔV≠0 公理 | [高] |
| AutoCAD | **COM SendCommand EXTRUDE**（2.5D） | GUI 拉伸 | 仅 2.5D 职责域；COM 温通道 verified-working | [中] |
| NX | **NXOpen Python Journal + run_journal.exe** | GUI 手工 | run_journal verified-working [高] + ΔV≠0 校验；批量改参/多体建模均对象级 | [高] |
| CIMCO | **N/A** | — | 无几何建模模块（路由至 NX/SOLIDWORKS） | [高]（N/A 判定） |
| VERICUT | **N/A** | — | 非 CAD 建模器，几何经转换器导入 | — |
| SSCNC | **N/A** | — | 非建模器，机床几何由 spec.ini 定义 | — |

## 3. 仿真

| 软件 | 最快路线 | 次优备选 | 判定依据（简） | 置信度 |
| :-- | :-- | :-- | :-- | :-- |
| SOLIDWORKS | **Simulation add-in API 静应力**（FOS≥1.5 回环） | GUI 研究向导 | API 常驻、可脚本回环校核 vs GUI 向导多步；FOS≥1.5 闭环公理 | [中] |
| NX | **NX CAE GUI + Nastran** | CAE Journal | CAE Journal documented-not-probed；GUI 路径成熟、有官方文档 | [中] |
| CIMCO | **外部 Python G00 哨兵背绘校验** | CIMCO GUI 背绘 | 外部脚本常驻+可并行+verified-working [高] vs GUI 背绘 documented-not-probed | [高] |
| VERICUT | **.vcreview 回读**（批量复核）+ **GUI 播放(1890,860)**（首证） | CGTECH_VCPROJECT 自动加载+TRANSACTION_LOG 审计 | vcreview 文件级秒级可并行（227MB 实测）；batchp/batcht **confirmed-negative 不可作最快路线**；GUI 坐标脆弱故仅首证复核 | [高] |
| SSCNC | **桥接 launch + find_window + 离线算对刀** | 多控制器选择（并行） | 桥接 3 API、确定性高、verified-working vs 面板 8+ 步坐标脆弱、documented-not-probed | [高]/[低] |

## 4. 加工

| 软件 | 最快路线 | 次优备选 | 判定依据（简） | 置信度 |
| :-- | :-- | :-- | :-- | :-- |
| SOLIDWORKS | **SW CAM add-in 生成刀路**（辅助） | — | CAM 模块 documented-not-probed；SW 定位为建模主职，CAM 路由 NX | [低] |
| NX | **CAM 操作导航器 + Post Builder 三件套**（.pui/.tcl/.def） | NXOpen CAM Journal | AGENTS.md 公理：操作导航器 `!` 消除后 Post；三件套 verified 存在；YANGJEE 外挂 70+ 后处理作备选 | [中] |
| CIMCO | **外部 Python Macro B 校验**（#100/#500/WHILE-DO） | GUI CycleMacro 展开 | 外部脚本 1 步+常驻+可并行+verified-working [高]；NC 转换/后处理/DNC 模板族作辅助 | [高] |
| VERICUT | **日志数值解析**（碰撞/去除体积） | Auto-Diff 红蓝绿（GUI 1576,451 + 肉眼） | 1 调用常驻可并行、实测碰撞判据 vs Auto-Diff 需 GUI+肉眼；红=过切/蓝=残料/绿=合格公理 | [高]/[中] |
| SSCNC | **离线算对刀量（预生成）+ Tnnnn[形状]录入** | G54[测量]（面板） | 离线算 1 调用常驻可并行；面板对刀/启动必走但 documented-not-probed；启动前 CRT 三页核对 | [高]/[中] |

## 5. N/A 声明汇总（路由规则）

| N/A 格 | 原因 | 路由去向 |
| :-- | :-- | :-- |
| CIMCO × 画图/建模 | NC 编辑器/无几何建模模块 | AutoCAD（2D）、NX/SOLIDWORKS（3D） |
| VERICUT × 画图/建模 | 切削仿真验证器，几何经转换器导入 | AutoCAD/NX 出几何，转换器族导入 |
| SSCNC × 画图/建模 | 数控操作仿真器，机床几何由 spec.ini 定义 | AutoCAD/NX/SW |
| AutoCAD × 仿真/加工 | 本机无 FEA/CAM 模块（N/A 判定 [高]） | SW Simulation、NX CAM、VERICUT |
| SOLIDWORKS × 加工 | CAM add-in 辅助、documented-not-probed | NX CAM 主职 |

## 6. 证据与通道三态（全局判定原则）

1. **通道优先级**：文件级/无头（ezdxf、accoreconsole、run_journal、.vcreview、外部脚本）> API 常驻（COM 早绑定、NXOpen）> GUI（坐标脆弱、冷启动）。
2. **证据优先**：verified-working（历史实测）> documented-not-probed > 官方文档；**confirmed-negative 通道（VERICUT batch、SW ROT、各 COM 判死）绝不作最快路线**，仅作失败风险标注。
3. **批量 vs 单件**：批量优先可并行文件级通道；单件/首证优先常驻 API 或 GUI 复核。
4. 无实测时间一律标 [估算]；置信度：历史实测结论 [高]、文档化推断 [中]、纯推测 [低]。
5. 许可证/激活机制内容全程不涉及（边界不变）。
