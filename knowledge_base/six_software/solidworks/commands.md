# SOLIDWORKS 2021 — 关键命令表

> 类型：菜单 / 工具栏 / API(COM) / 宏(VBA)。所有 API 命令坐标单位为**米**。可复现调用方式给出最小片段。证据见各行列。

| 命令 ID | 模块 | 类型 | 参数/坐标 | 可复现调用 | 说明 | 证据 |
|---|---|---|---|---|---|---|
| SW_CMD_Connect | 会话 | API(COM) | ProgID=`SldWorks.Application` | `gc.EnsureModule(TLB,0,29,0); sw=gc.GetModuleForProgID("SldWorks.Application").SldWorks()` | 连接/启动 SW，单实例 | E-SW-02 |
| SW_CMD_NewPart | 零件建模 | API(COM) | 默认零件模板 | `part=__WrapDispatch(sw.NewPart(),"IModelDoc2")` | 新建空白零件 | E-SW-02 |
| SW_CMD_SelectPlane | 草图 | API(COM) | 平面名/类型/x,y,z | `part.SelectByID("前视基准面","PLANE",0,0,0)` | 选基准面（双语回退） | E-SW-02 |
| SW_CMD_InsertSketch | 草图 | API(COM) | 正交切换 bool | `part.SketchManager.InsertSketch(True)` | 进入/退出草图 | E-SW-02 |
| SW_CMD_CornerRectangle | 草图 | API(COM) | x1,y1,x2,y2（米） | `SketchManager.CreateCornerRectangle(0,0,0,0.05,0.03,0)` | 中心角矩形 | E-SW-02 |
| SW_CMD_CircleByRadius | 草图 | API(COM) | cx,cy,r（米） | `SketchManager.CreateCircleByRadius(0,0,0,0.08)` | 圆心半径画圆 | E-SW-02 |
| SW_CMD_ClearSelection | 会话 | API(COM) |  | `part.ClearSelection2(True)` | 清除选择集 | E-SW-02 |
| SW_CMD_FeatureExtrusion2 | 特征 | API(COM) | 23 参（见 automation_api 2.4） | `FeatureManager.FeatureExtrusion2(Sd,Flip,Dir,0,0,depth,0,...)` | 盲拉伸凸台；ΔV>0 | E-SW-02,E-SW-10 |
| SW_CMD_FeatureCut | 特征 | API(COM) | 同拉伸族参数 | `FeatureManager.FeatureCut(False,False,True,1,1,0,0,...)` | 拉伸切除；ΔV<0 | E-SW-02 |
| SW_CMD_Fillet | 特征 | API(COM) | 半径/面/setback | （领域技能 fillet-chamfer-cnc 封装） | 恒定/可变半径圆角 | E-SW-09 |
| SW_CMD_Chamfer | 特征 | API(COM) | 距离/角度 | （领域技能 fillet-chamfer-cnc 封装） | 距离-距离/角度倒角 | E-SW-09 |
| SW_CMD_HoleWizard | 特征 | API(COM) | M3–M12 公制 | （领域技能 threaded-holes 封装） | 异型孔向导/攻丝底孔 | E-SW-09 |
| SW_CMD_EquationMgr_Add | 方程式 | API(COM) | idx,'"名"=值' | `eq=part.GetEquationMgr(); eq.Add(idx,'"D_Outer"=0.160')` | 写参数方程 | E-SW-02 |
| SW_CMD_EditRebuild3 | 会话 | API(COM) |  | `part.EditRebuild3` | 重建模型 | E-SW-02 |
| SW_CMD_ForceRebuild3 | 会话 | API(COM) |  | `part.ForceRebuild3(True)` | 强制重建 | E-SW-02 |
| SW_CMD_MassProperties | 校验 | API(COM) | bodies | `mp=part.Extension.CreateMassProperty(); mp.AddBodies(part.GetBodies2(0))` | 体积/质量/质心/表面积 | E-SW-02 |
| SW_CMD_ViewZoomtofit2 | 可视化 | API(COM) |  | `part.ViewZoomtofit2()` | 缩放至整屏 | E-SW-02 |
| SW_CMD_SaveAs3 | 数据交换 | API(COM) | path,options,version | `part.SaveAs3(r"D:\...\a.SLDPRT",0,1)` | 另存为零件 | E-SW-02 |
| SW_CMD_SaveAsSTEP | 数据交换 | 菜单/API | AP203/214 | 文件→另存为→*.STEP（能力 step_export） | 导出中性格式 | E-SW-01 |
| SW_CMD_RunMacro | 宏 | VBA | swp,module,proc | `sw.RunMacro(path,"Main","main")` | 执行编译后 .swp | E-SW-02 |
| SW_CMD_DrawView | 工程图 | 菜单 | 第一角画法 | 插入→工程图视图（GB/T 17451） | 投影视图 | E-SW-09 |
| SW_CMD_Dimension | 工程图 | 菜单/API |  | 智能尺寸 | 尺寸标注 | E-SW-09 |
| SW_CMD_GTol | 工程图 | 菜单 | 符号库 gtol97.sym | 注解→形位公差 | GD&T | E-SW-11 |
| SW_CMD_BOM | 工程图 | 菜单 | 模板 *.sldbomtbt | 插入→表格→材料明细表 | BOM | E-SW-11 |
| SW_CMD_HoleTable | 工程图 | 菜单 | 模板 *.sldholtbt | 注解→孔表 | 孔表 | E-SW-11 |
| SW_CMD_Material | 配置 | 菜单 | *.sldmat | 编辑材料→solidworks materials.sldmat | 赋材质 | E-SW-11 |
| SW_CMD_StaticStudy | 仿真 | 菜单 |  | Simulation→静应力 | FEA 静应力（documented-not-probed 本轮未驱动） | E-SW-08 |

## 桥接高层封装命令（来自 tool_calling_specs / orchestrator）

| 工具名 | 动作 | 说明 | 证据 |
|---|---|---|---|
| `cadcam_solidworks_model` | `connect` / `create_parametric_part` / `model_flange` / `annotate_drawing` / `execute_vba` | 跨软件编排入口；model_flange 建带颈法兰盘 | E-SW-13 |
| `SolidWorksBridge.model_flange` | 全流程 | 方程→圆盘→轮毂→6×螺栓孔→保存 SLDPRT | E-SW-02 |
