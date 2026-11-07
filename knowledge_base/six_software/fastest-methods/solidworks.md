# SOLIDWORKS 2021 最快方法证据基准

> 依据 `FASTEST_METHODS_CONTRACT.md`。证据回溯本仓 `six_software\solidworks\`（automation_api.md / plugins.md / commands.md / workflows.md / runbooks\solidworks.runbook.md）。
> 硬边界：无许可证/激活内容；不臆造实测，时间量级标 [估算]。
> 已确认事实：COM ProgID `SldWorks.Application`（早绑定 verified-working [高] 历史实测）；ROT `GetActiveObject` confirmed-negative（本机未注册 ROT，单实例）；`RunMacro` 仅认编译后 `.swp`，裸 `.bas` 不可直接跑；API 内部米制（1mm=0.001m）；世界 Y 向上；体积守恒 ΔV≠0。

## 任务族适用性
| 任务族 | 适用性 | 说明 |
| :-- | :-- | :-- |
| 画图 2D drafting | ✅ | 草图→GB 工程图（第一角/BOM/孔表） |
| 建模 3D modeling | ✅ | 参数化主职 |
| 仿真 | ✅ | Simulation add-in FEA，FOS≥1.5 |
| 加工 | ⚠️ 辅助 | CAM add-in（非主职主域；CAM 主职在 NX/CIMCO/VERICUT） |

---

## 一、画图族（2D drafting：从零件出 GB 工程图）

### R-draw-1：COM/API 早绑定自动出图（推荐基线）
- 通道类型：API（COM 早绑定，pywin32）
- 调用路径：`CreateObject("SldWorks.Application")` → `NewDocument(draw.drwdot)` → 插入标准三视图 → 中心线/标注/BOM → `SaveAs3`（见 runbook §2、commands create_drawing）
- 证据：solidworks/automation_api.md（COM 早绑定 verified-working [高]）；runbooks/solidworks.runbook.md §2；commands `solidworks.create_drawing`
- 度量：步骤数 5｜API 调用数 ~8（NewDocument+InsertView×3+center+dim+save）｜启动开销 冷 30–60s [估算]（SW 进程）｜可并行度 低（COM 单实例）｜证据等级 verified-working（COM）｜确定性 高｜失败风险 中（COM 判死需重连；ROT 未注册不能 attach 常驻实例，每次新起）

### R-draw-2：GUI 交互出图
- 通道类型：GUI
- 调用路径：文件→从零件制作工程图→选模板→拖三视图→标注→PDF（runbook §1）
- 证据：solidworks/automation_api.md（GUI 通道 documented）；runbooks/solidworks.runbook.md §1
- 度量：步骤数 12–15｜菜单操作数 ~12｜启动开销 冷 30–60s [估算]｜可并行度 低｜证据等级 documented-not-probed（本轮未实测点击）｜确定性 低（焦点/对话框脆弱）｜失败风险 中（误点/模板缺失）

### R-draw-3：方程/参数驱动联动出图
- 通道类型：混合（API + EquationMgr）
- 调用路径：先 `IEquationMgr.Add2` 改参 → `ForceRebuild3(True)` → 工程图自动更新视图/尺寸（commands create_parametric_part equation 项）
- 证据：runbooks/solidworks.runbook.md §2（EquationMgr.Add2 / ForceRebuild3）；commands `solidworks.create_parametric_part`
- 度量：步骤数 6｜API 调用数 ~9｜启动开销 冷 30–60s [估算]｜可并行度 低｜证据等级 verified-working（COM）｜确定性 高｜失败风险 中（参数约束链报错需 diagnose_document）

> 说明：SW 无 accoreconsole 式无头批处理进程，故画图族最快仍须拉起 SW 进程；文件级 2D 交换走 DXF/DWG 由 AutoCAD/ezdxf 承担（见跨软件矩阵）。

---

## 二、建模族（3D parametric modeling）

### R-model-1：COM 早绑定（pywin32 直连 API）
- 通道类型：API（COM 早绑定）
- 调用路径：`CreateObject("SldWorks.Application")`→`NewPart()`→`SelectByID2 "前视基准面"`→SketchManager 草图→`FeatureExtrusion2`→`CreateMassProperty()` 校验体积守恒→`SaveAs3`（runbook §2）
- 证据：automation_api.md（COM 早绑定 verified-working [高]）；runbook §2；commands `solidworks.create_parametric_part`
- 度量：步骤数 6｜API 调用数 ~10｜启动开销 冷 30–60s [估算]｜可并行度 低（单实例）｜证据等级 verified-working｜确定性 高（米制/体积守恒可断言）｜失败风险 中（ROT confirmed-negative：不能 attach 已开窗口，须新起进程；特征报错调 diagnose_document）

### R-model-2：RunMacro（预编译 .swp 宏）
- 通道类型：批处理/API（运行内嵌宏）
- 调用路径：`swApp.RunMacro(path, module, proc)`，**仅认编译后 `.swp`**；裸 `.bas` 不能直接 RunMacro
- 证据：automation_api.md（RunMacro 仅认 .swp confirmed 事实）；contract §5 实测必引
- 度量：步骤数 4（写/编 .swp → RunMacro → 校验）｜API 调用数 1（RunMacro）｜启动开销 冷 30–60s [估算]｜可并行度 低｜证据等级 documented-not-probed（本轮未真机跑宏）｜确定性 中（宏内部错误不即时可见）｜失败风险 中（宏编译错误、.swp 与版本绑定）

### R-model-3：方程驱动参数化（EquationMgr）
- 通道类型：API（参数化核心）
- 调用路径：建基线特征后 `GetEquationMgr().Add2 idx,"\"D_Outer\"=0.160"` → 改值 → `ForceRebuild3`（runbook §2）
- 证据：runbook §2；commands equation 项
- 度量：步骤数 5｜API 调用数 ~7｜启动开销 冷 30–60s [估算]｜可并行度 低｜证据等级 verified-working｜确定性 高｜失败风险 低（参数链错误可 Rebuild 提示）

### R-model-4：GUI 交互建模
- 通道类型：GUI
- 调用路径：新建零件→选前视基准面→草图→特征→圆角/倒角（runbook §1）
- 证据：runbook §1
- 度量：步骤数 10+｜菜单/点击 ~10｜启动开销 冷 30–60s [估算]｜可并行度 低｜证据等级 documented-not-probed｜确定性 低（坐标/焦点脆弱）｜失败风险 中（误操作需撤销）

---

## 三、仿真族（Simulation FEA，FOS≥1.5）

### R-sim-1：Simulation add-in API 静应力研究
- 通道类型：插件（Simulation add-in）
- 调用路径：启用 Simulation → 建 Static Study → 赋材料 → 约束/载荷 → 跑求解（gabiswengine/mg-tetra）→ 读 von Mises 与 FOS（commands `solidworks.simulation_static_study`）
- 证据：plugins.md（Simulation Worker / gabiswengine.exe / mg-tetra.exe）；commands `solidworks.simulation_static_study`；AGENTS.md §3 FOS≥1.5 闭环
- 度量：步骤数 7｜API/求解调用数 ~5（建研究+材料+约束+求解+读结果）｜启动开销 冷 30–60s [估算]+求解时长 [估算]｜可并行度 低｜证据等级 documented-not-probed（本轮未真机跑求解器）｜确定性 中（网格相关）｜失败风险 中（网格/约束不当导致 FOS 误判）

### R-sim-2：GUI Simulation 研究
- 通道类型：GUI + 插件
- 调用路径：Simulation 标签页→新算例→向导施加载荷→运行→结果图解
- 证据：plugins.md；runbook §3
- 度量：步骤数 10+｜操作数 ~10｜启动开销 冷+求解 [估算]｜可并行度 低｜证据等级 documented-not-probed｜确定性 中｜失败风险 中

> 注：FOS<1.5 必须回 WF-SW-1 建模族加厚尺寸再校核（AGENTS.md §3 闭环），不是仿真族内迭代。

---

## 四、加工族（CAM add-in，辅助）

### R-mill-1：SOLIDWORKS CAM add-in（特征识别→刀路）
- 通道类型：插件（CAM add-in）
- 调用路径：启用 SOLIDWORKS CAM → 自动特征识别 → 选毛坯/刀具 → 生成刀路 → 后处理输出 G 代码
- 证据：plugins.md（CAM add-in）；AGENTS.md §3（CAM/后处理在 NX/CIMCO/VERICUT 主职）
- 度量：步骤数 8｜调用数 ~6｜启动开销 冷 30–60s+ [估算]｜可并行度 低｜证据等级 documented-not-probed｜确定性 中｜失败风险 中（刀路仍需 CIMCO/VERICUT 复核）
- 适用性说明：SOLIDWORKS CAM 仅为**辅助**；加工主职链按 AGENTS.md 走 NX CAM → CIMCO 背绘 → VERICUT Auto-Diff，SW 侧最快定位是"出 STEP 交 NX"而非自产刀路。

---

## 最快结论（SOLIDWORKS 2021）
| 任务族 | 最快路线 | 次优备选 | 判定依据（度量对比） | 置信度 |
| :-- | :-- | :-- | :-- | :-- |
| 画图 2D | R-draw-1 COM/API 早绑定出图 | R-draw-3 方程联动出图 | API 5 步/8 调用、确定性高 vs GUI 12–15 步、坐标脆弱；COM 早绑定 verified-working [高] | [高] |
| 建模 3D | R-model-1 COM 早绑定参数化建模 | R-model-3 方程驱动参数化 | COM 直接落草图+特征+体积守恒断言，确定性高；ROT confirmed-negative 故新起进程而非 attach；RunMacro 需先编 .swp 多一步 | [高] |
| 仿真 FEA | R-sim-1 Simulation API 静应力 | R-sim-2 GUI 研究 | API 一键建研究+读 FOS，结构化可断言；GUI 向导点击步数多；但求解器本轮未实测 | [中] |
| 加工 CAM | R-mill-1 SW CAM add-in（辅助） | — | SW CAM 仅辅助，加工主链交 NX/CIMCO/VERICUT；此处仅给最快定位 | [低]（documented-not-probed） |
