# SOLIDWORKS 2021 — 证据链

> 规则：每条断言可回溯到下表 E-ID。`本轮复测`列：本轮执行通道（Read/Grep/Glob/在线搜索）下的勘察标记；历史实测项标注来源文件。禁止无证据声明。

| E-ID | 声明摘要 | 证据类型 | 证据位置 | 置信度 | 本轮是否复测 |
|---|---|---|---|---|---|
| E-SW-01 | 显示名 SOLIDWORKS 2021；类别 3D CAD/参数化；能力 parametric_modeling/equation_manager/vba_macros/step_export | 桥接注册表代码 | `bridges/software_registry.py` SOFTWARE_SPECS["solidworks"] | 高 | 是（Read） |
| E-SW-02 | 主程序/进程/COM ProgID/类型库 GUID=29/NewPart/SelectByID/SketchManager/FeatureManager.FeatureExtrusion2(23参)/FeatureCut/EquationMgr/MassProperty/SaveAs3/RunMacro/单实例约束 | 桥接代码（接口证据） | `bridges/solidworks_bridge.py` 全文（TLB_GUID、PLANE_NAMES、SolidWorksBridge 各方法） | 高 | 是（Read） |
| E-SW-03 | 主程序路径 `D:\SOLIDWORKS (2)\SLDWORKS.exe`，进程 SLDWORKS.exe | 二进制路径 | software_registry known_binaries；_diag_result.txt 第4行 | 高 | 是（Read diag） |
| E-SW-04 | COM ProgID = SldWorks.Application | 桥接代码/注册表探测 | solidworks_bridge.py GetActiveObject/Dispatch；software_registry com_prog_id | 高 | 是（Read） |
| E-SW-05 | 预检 6/6 READY；solidworks ready=True running=True PID 21056 | 诊断输出 | `D:\Virtu模型\_diag_result.txt` 第3-4行 | 高（历史实测） | 是（Read diag） |
| E-SW-06 | 世界Y向上/前视=XY/单位mm/体积守恒断言 | 项目公理 | `D:\Virtu模型\AGENTS.md` 第2.A节 | 高 | 是（Read 项目规则） |
| E-SW-07 | API 内部长度单位米（1mm=0.001m） | 桥接代码注释+技能 | solidworks_bridge.py mass_properties 单位换算；solidworks-unified SKILL「SW默认米(0.02m=20mm)」 | 高 | 是（Read） |
| E-SW-08 | 功能模块（放样/阵列/旋转扫描/钣金/焊件/装配配合/工程图/静应力/运动算例/导入导出/方程/DXF） | 安装目录帮助文档(CHM) | `D:\SOLIDWORKS (2)\lang\chinese-simplified\*.chm`（OTLoft/OTPatternFeatures/OTRevolveSweep/OTSheetMetal/OTweldments/OTAssemblyMates/OTAdvancedDrawings/cworks/motionstudies/OTImportExport/otequations/slddxf） | 高 | 是（Glob） |
| E-SW-09 | 6 个 SW 子技能能力边界（螺纹孔M3-M12、圆角倒角、GB第一角/BOM/孔表/标题栏、STEP/IGES/STL） | 用户已装领域技能 | `.user_skills/solidworks-unified/SKILL.md` 路由表与门禁 | 高 | 是（Read） |
| E-SW-10 | FeatureExtrusion2 官方方法页（已obsolete→FeatureExtrusion3）；IModelDoc2 成员；VBA 拉伸示例 | 官方文档URL | help.solidworks.com FeatureExtrusion2 / IModelDoc2_members / Insert_Feature_Extrusion_Example_VB.htm | 高 | 是（general_search） |
| E-SW-11 | 材料库/线型/剖面线/GD&T符号/钣金折弯表/焊件轮廓/BOM模板/标题栏/孔表模板位置 | 安装目录文件 | `D:\SOLIDWORKS (2)\lang\chinese-simplified\`（Swlines.lin、Sldwks.ptn、gtol97.sym、sldmaterials\*.sldmat、Sheetmetal Bend Tables\、weldment profiles\ANSI\*.sldlfp、bom-*.sldbomtbt、title block.sldtbt、*.sldholtbt） | 高 | 是（Glob） |
| E-SW-12 | 类型库清单（sldworks.tlb/swcommands/swconst/swvba/MacroBuilder/swmotionstudy/swdimxpert/swscanto3d/SWRoutingLib等） | 安装目录二进制 | `D:\SOLIDWORKS (2)\*.tlb`（Glob 列出16个） | 高 | 是（Glob） |
| E-SW-13 | 跨软件工具 cadcam_solidworks_model / cadcam_cae_stress_analysis(FOS默认1.5) / cadcam_extreme_chain 定义 | 桥接编排代码 | `bridges/tool_calling_specs.py` | 高 | 是（Read） |
| E-SW-14 | STEP AP203/214/242 规范 | 官方/标准URL | iso.org 10303-214；loc.gov fdd000448；nist.gov STEP File Analyzer | 高 | 是（general_search） |
| E-SW-15 | 模板位置（零件.prtdot/assem.asmdot/draw.drwdot） | 安装目录文件 | `D:\SOLIDWORKS (2)\data\templates\零件.prtdot`；`lang\chinese-simplified\Tutorial\*.dot` | 高 | 是（Glob） |
| E-SW-16 | 既有产物 Flange_Parametric.SLDPRT 存在 | 项目产物 | `D:\Virtu模型\Flange_Parametric.SLDPRT`（任务书声明，本轮未 Glob 复核） | 中 | 否（任务书引用） |

## 判死/未复测通道记录

| 通道 | 判定 | 依据 |
|---|---|---|
| ROT 附着 `GetActiveObject("SldWorks.Application")` | confirmed-negative | solidworks_bridge.py 注释明确「本机实例未在 ROT 注册，无法自动连接」；桥接枚举 ROT 找不到 sldworks（E-SW-02） |
| 裸 `.bas` 经 RunMacro 执行 | confirmed-negative | bridge.execute_vba_code 实测 RunMacro 需编译 `.swp`，`.bas` 仅 saved_only（E-SW-02） |
| SW 内置 Simulation 求解器驱动 | documented-not-probed | 本轮未启动求解器；FOS 校核由跨软件解析引擎承担（E-SW-13） |
| SW 用户注册表/roaming 偏好目录 | documented-not-probed | 本轮未读注册表（通道限制） |
| 命令行 headless 批处理 | documented-not-probed | 桥接无此路径；SW 无官方无界面 CLI |

## 插件扩展证据（plugins.md）

| E-ID | 声明摘要 | 证据类型 | 证据位置 | 置信度 | 本轮是否复测 |
|---|---|---|---|---|---|
| E-SW-P01 | Toolbox 标准件库在盘（配置器/更新器 exe） | 安装目录二进制 | `D:\SOLIDWORKS (2)\SldToolboxConfigure.exe`、`sldtoolboxupdater.exe` | 高 | 是（Glob） |
| E-SW-P02 | Simulation FEA 求解器/Worker 在盘 | 安装目录二进制 | `D:\SOLIDWORKS (2)\SOLIDWORKS Simulation Worker Agent.exe`、`gabiswengine.exe`、`mg-tetra.exe`、`mpiexec.hydra.exe`、`pmi_proxy.exe`；`Common Files\SOLIDWORKS Shared\Simulation Worker Agent\`；cworks/vcwlinear.chm、simulation_theory_manual.pdf | 高 | 是（Glob） |
| E-SW-P03 | PCB Viewer 独立程序在盘（Altium DXP） | 安装目录二进制 | `C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS PCB Viewer\dxp.exe`、`AltiumMS.exe` | 高 | 是（Glob） |
| E-SW-P04 | eDrawings 共享运行时在盘；主 exe 未定位 | 安装目录二进制+快捷方式 | `Common Files\SOLIDWORKS Shared\sldrx\sldrx.exe`、`swcef\sldCefViewer.exe`；桌面 `eDrawings 2021 x64 Edition.lnk` | 中 | 是（Glob） |
| E-SW-P05 | SOLIDWORKS PDM 安装在盘 | 安装目录二进制 | `C:\Program Files (x86)\SOLIDWORKS PDM\AddInRegSrv32.exe`、`TaskExecutor.exe`、`InventorServer.exe` | 高 | 是（Glob） |
| E-SW-P06 | Manage/Visualize/Visualize Boost/Inspection/Electrical/Composer Player 桌面快捷方式在盘 | 桌面快捷方式 | `C:\Users\Public\Desktop\` 下对应 6 个 .lnk（Manage/Visualize/Visualize Boost/Inspection/Electrical/Composer Player） | 中（.lnk 存在已证；exe 路径因二进制无 shell 未解码） | 是（Glob） |
| E-SW-P07 | SW CAM add-in 本轮未在安装根定位独立 exe | 安装目录勘察 | `D:\SOLIDWORKS (2)\*.exe` 列表无 CAM 主程序 | 低 | 是（Glob） |

> 边界声明：`Common Files\SOLIDWORKS Shared\2021\lmutil.exe`/`swlmutil.exe`/`swlmwiz.exe` 等许可证工具虽勘察到，按 scope（排除 license_server/激活机制）**不文档化、不展开**。
