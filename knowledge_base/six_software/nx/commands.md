# Siemens NX 12.0 关键命令表

> 表：命令 ID | 模块 | 类型 | 参数/坐标 | 说明 | 证据。每条给出可复现调用方式。
> 类型：菜单(Menu) / 工具栏(Ribbon) / 命令行(CLI) / API(NXOpen) / 批处理(EXE) / 快捷键(Shortcut)。

| 命令 ID | 模块 | 类型 | 参数/坐标 | 说明 | 证据 |
|---|---|---|---|---|---|
| `nx_new_part` | gateway_basics | API | `Parts.NewBase(path, Units.Millimeters)` 或 `Parts.FileNew()` | 新建毫米制零件 | E-106/E-107 |
| `nx_open_part` | gateway_basics | 菜单 | 文件\|打开 | 打开 .prt | E-106 |
| `nx_save_part` | gateway_basics | API | `workPart.Save(SaveComponents.TrueValue, CloseAfterSave.FalseValue)` | 保存部件 | E-106 |
| `nx_block` | part_modeling | API | `CreateBlockFeatureBuilder`，OriginAndEdgeLengths(原点,长,宽,高) | 长方体，ΔV>0 | E-106 |
| `nx_cylinder` | part_modeling | API | `CreateCylinderBuilder`，AxisDiameterAndHeight(直径,高,方向,原点) | 圆柱/圆柱切除(Subtract) | E-106 |
| `nx_extrude` | part_modeling | API | `CreateExtrudeBuilder`，Section/Direction/Limits 0~长度，BooleanOperation | 拉伸（最常用） | E-106 |
| `nx_revolve` | part_modeling | API | `CreateRevolveBuilder`，截面+回转轴 | 回转特征 | E-106（推断，同 Builder 模式） |
| `nx_blend` | part_modeling | API(UF) | `uf.ModlFeatures.CreateBlend("R", edge_tags,0,0,0,0.0001)` | 边圆角，先大后小(R4→R1) | E-106 |
| `nx_chamfer` | part_modeling | API(UF) | `uf.Modeling.CreateChamfer(1,"0.2","0.2","45",edge_tags)` | 倒角(subtype 1 单向/2 双向/3 偏置角度) | E-106 |
| `nx_text` | part_modeling | API | `CreateTextBuilder`，Type=Planar，TextString，PlanarFrame.Height，CoordinateSystem | 刻字（拉伸切除） | E-106 |
| `nx_sketch` | sketcher | API | `workPart.Sketcher.CreateSketchOnPlane(plane)` | 草图任务环境 | E-106 |
| `nx_create_line` | sketcher | API | `workPart.Curves.CreateLine(Point3d,p1, Point3d,p2)` | 直线 | E-106 |
| `nx_section_build` | sketcher | API | `CreateSection(0.00095,0.01,0.5)` + `ScRuleFactory.CreateRuleCurveDumb([curves])` | 拉伸截面构造 | E-106 |
| `nx_expression` | expressions | API | `workPart.Expressions.CreateWithUnits('D=160', mm_unit)` | 表达式参数化 | E-107 |
| `nx_assembly_add_component` | assembly | 菜单 | 装配\|组件\|添加组件 | 添加组件到装配 | E-105 |
| `nx_assembly_constraint` | assembly | 菜单 | 装配\|组件\|配对约束 | 配对约束 | E-105 |
| `nx_assy_build` | assembly | 批处理 | `NXBIN\ug_assy_build.exe` | 装配构建 | E-103 |
| `nx_clearance` | assembly | 批处理 | `NXBIN\ug_clearance.exe` | 装配间隙检查 | E-103 |
| `nx_drafting_view` | drafting | 菜单 | 插入\|视图\|基本视图/投影视图 | 工程图视图 | E-105 |
| `nx_drafting_dimension` | drafting | 菜单 | 插入\|尺寸 | 标注尺寸/公差 | E-105 |
| `nx_fea_mesh` | fea_simulation | 批处理 | `NXBIN\ugnx_batchmesher.exe` | 批处理网格划分 | E-103 |
| `nx_fea_solve` | fea_simulation | 菜单 | 开始\|高级仿真\|求解(NX Nastran) | FEA 求解 von Mises/位移 | E-105（推断） |
| `nx_massprop` | fea_simulation | 批处理 | `NXBIN\massprop.exe` | 质量属性（体积/质心） | E-103 |
| `nx_check_part` | part_modeling | 批处理 | `NXBIN\ug_check_part.exe` | 部件诊断/特征错误检查 | E-103 |
| `nx_cam_create_operation` | cam_toolpath | 菜单/API | 加工\|创建操作：型腔铣/平面铣/轮廓铣/钻孔/多轴 | 创建 CAM 操作 | E-105 |
| `nx_cam_generate` | cam_toolpath | 菜单 | 加工\|生成刀轨 Generate | 生成刀轨 | E-105 |
| `nx_cam_operation_check` | cam_toolpath | GUI | Operation Navigator 检查感叹号(!) | **公理：导出刀路前必须查 CAM 树感叹号警告** | AGENTS.md §2.C |
| `nx_cam_postprocess` | post_processing | 菜单 | 加工\|输出\|后处理 Post Process | 后处理输出 NC/CLS | E-105 |
| `nx_cls_output` | post_processing | 菜单 | 加工\|输出\|刀位源文件 CLSF | 输出刀位源文件 .cls | E-105（推断） |
| `nx_jt_postprocessor` | post_processing | 批处理 | `NXBIN\jtpostprocessor.exe` | JT 后处理 | E-103 |
| `nx_step_export` | data_exchange | API | `DexManager.CreateStepCreator`，ExportAs=Ap214，SettingsFile=ugstep214.def | STEP AP214 导出 | E-106 |
| `nx_iges_export` | data_exchange | 菜单 | 文件\|导出\|IGES | IGES 导出 | E-105（推断） |
| `nx_jt_export` | data_exchange | 菜单/批处理 | 文件\|导出\|JT / `jtpostprocessor.exe` | JT 可视化 | E-103 |
| `nx_run_journal` | automation_journal | CLI | `run_journal.exe script.py` 或 `ugraf.exe -journal script.py` | 运行 NXOpen Python 日志 | E-107/E-110 |
| `nx_step214_batch` | data_exchange | 批处理 | `NXBIN\step214ug.exe` (+`STEP214UG\ugstep214.def`) | STEP AP214 批处理 | E-103/E-109 |

## 可复现命令模式（PowerShell，历史实测）

```powershell
# 无头运行 NXOpen Python 日志
$env:UGII_BASE_DIR="E:\BaiduNetdiskDownload\NX 12.0.2.9\NX12.2.9waigua\NX12.2.9\NX"
$env:UGII_ROOT_DIR="$env:UGII_BASE_DIR\NXBIN"
& "$env:UGII_BASE_DIR\NXBIN\run_journal.exe" "D:\Virtu模型\scratch\part_nx.py"
```
（E-107/E-110）
