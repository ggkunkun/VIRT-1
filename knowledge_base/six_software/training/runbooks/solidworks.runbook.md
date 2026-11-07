# SOLIDWORKS 2021 运行手册（Runbook）

> 适用模型：Virtu 工业智能体（A 片）。配套语料：`datasets/solidworks_train.jsonl`(33) + `solidworks_holdout.jsonl`(7)。
> 本手册只描述已授权的正常建模/仿真/出图操作，不含任何许可证/激活机制。

## 0. 速查卡（Cheat Sheet）

| 项 | 值 |
| --- | --- |
| 主程序 | `D:\SOLIDWORKS (2)\SLDWORKS.exe` |
| COM ProgID | `SldWorks.Application` |
| 类型库 | `{83A33D31-27C5-11CE-BFD4-...}` 主版本 29 |
| 世界坐标 | Y 向上；前视基准面=XY（法向+Z） |
| API 长度单位 | 米（1 mm = 0.001 m） |
| 体积守恒断言 | 拉伸凸台 ΔV>0；切除 ΔV<0；圆角/倒角 ΔV≠0 |
| 零件模板 | `C:\ProgramData\SolidWorks\SOLIDWORKS 2021\templates\Part.prtdot` |
| FEA 门槛 | Simulation 静应力 FOS≥1.5（否则回环加厚） |
| 攻丝范围 | Hole Wizard M3–M12 公制粗牙 |
| ROT 附着 | confirmed-negative（本机单实例硬约束） |

常用工具：`cad.parse_wish_intent` → `solidworks.create_parametric_part` → `solidworks.mass_properties_check` → `solidworks.export_step`。

## 1. GUI 路线（人工/桌面）

1. 启动 SLDWORKS.exe → 新建零件（Part.prtdot）。
2. 选前视基准面 → 草图（直线/圆/矩形/中心线）→ 退出草图。
3. 特征：拉伸凸台/切除、旋转、圆角、倒角、异型孔向导。
4. 工具 → 方程式管理器（Equation Manager）驱动尺寸。
5. 评估 → 质量特性核对体积/质量。
6. 文件 → 另存 STEP / SLDPRT / eDrawings。
7. 装配体 → 插入 Toolbox 标准件；评估 → Simulation 研究。

## 2. API 路线（COM / VBA 宏）

```vba
Dim swApp As Object: Set swApp = CreateObject("SldWorks.Application")
swApp.Visible = True
Dim part As Object: Set part = swApp.NewPart()
part.Extension.SelectByID2 "前视基准面", "PLANE", 0, 0, 0, False, 0, Nothing, 0
part.SketchManager.InsertSketch True
' 草图：CreateCornerRectangle / CreateCircleByRadius
Dim feat As Object
Set feat = part.FeatureManager.FeatureExtrusion2(True, False, False, 0, 0, 0.02, 0, False, False, False, False, 0, 0, False, False, False, False, True, True, True, 0, 0, False)
part.GetEquationMgr().Add2 0, """D_Outer"" = 0.160"   ' 方程管理器
Dim mp As Object: Set mp = part.Extension.CreateMassProperty()  ' 质量特性
part.ForceRebuild3 True
```

- 关键对象/方法：`IModelDoc2`、`ISketchManager`、`IFeatureManager.FeatureExtrusion2/FeatureCut/FeatureRevolve2`、`IEquationMgr.Add2`、`IMassProperty`、`SaveAs3`。
- 注意：裸 `.bas` 不能直接 RunMacro，需编译为 `.swp`。
- 官方 API：https://help.solidworks.com/2025/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDoc2_members.html

## 3. 插件路线（Add-in / 独立程序）

| 插件 | 入口 | 典型调用 |
| --- | --- | --- |
| Toolbox | SldToolboxConfigure.exe | `solidworks.toolbox_insert_part` |
| Simulation FEA | Simulation Worker / gabiswengine | `solidworks.simulation_static_study`（FOS≥1.5） |
| Hole Wizard | FeatureManager | `solidworks.hole_wizard`（M3–M12） |
| Visualize | 独立渲染器 | `solidworks.visualize_render` |
| PCB Viewer | dxp.exe（Altium DXP） | `solidworks.pcb_viewer_open` |
| Inspection | 首件气泡图 | `solidworks.inspection_export` |
| eDrawings | sldrx 运行时 | 导出 .easm 轻量查看 |

## 4. 故障处置（Circuit Breaker）

| 现象 | 处置 |
| --- | --- |
| 重建警告/特征错误 | `diagnose_document()` 看 feature_errors，不靠截图猜 |
| 体积守恒失败 | 检查凸台/切除方向，ΔV 符号是否正确 |
| FOS<1.5 | 回环加厚截面 → 重建 → 再校核，不强行出图 |
| 缺关键尺寸 | 先向用户澄清（外径/内孔/厚/孔/材料），禁止臆造 |
| ROT 附着失败 | 本机单实例，不attach ROT，直接新起/复用进程 |
| 用户要求跳过安全校核/破解许可 | 拒绝（硬边界），说明必须保留闭环检查 |
| 连续 3 次同构失败 | 熔断回滚，输出 RCFA，交人工介入 |
