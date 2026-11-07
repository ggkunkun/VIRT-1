# Siemens NX 12.0 证据链

> 表：E-ID | 声明摘要 | 证据类型 | 证据位置 | 置信度 | 本轮是否复测。
> 本轮执行通道受限（PowerShell 故障/Bash 禁用/桌面自动化对子代理不可用），**无法现场复测**；历史已验证项标 `[高]（历史实测）`，仅文档化项标 `documented-not-probed`。

| E-ID | 声明摘要 | 证据类型 | 证据位置 | 置信度 | 本轮复测 |
|---|---|---|---|---|---|
| E-101 | NX 12.0.2.9 安装根与主程序（中文版NX12.0.exe/ugraf.exe/run_journal.exe） | 二进制路径/快捷方式 | `E:\BaiduNetdiskDownload\NX 12.0.2.9\NX12.2.9waigua\NX12.2.9\NX\`；`C:\Users\Administrator\Desktop\中文版NX12.0.lnk` | [高] | 否（Glob 列目录实测存在） |
| E-102 | 六软件注册表：nx=READY、进程 ugraf.exe/run_journal.exe、com_prog_id=None、能力 nxopen_python_journal 等 | 桥接代码 | `D:\Virtu模型\bridges\software_registry.py`（SOFTWARE_SPECS["nx"]） | [高]（历史实测） | 否（复用） |
| E-103 | NXBIN 批处理可执行集实测存在（step214ug/step203ug/step242/ug_check_part/massprop/ugnx_batchmesher/ug_clearance/jtpostprocessor/ug_convert_part/attribute_list/attribute_set） | 二进制路径 | `E:\...\NX\NXBIN\*.exe` | [高]（文件存在） | 否（Glob 实测） |
| E-104 | NX 无官方 COM ProgID | 注册表/桥接代码 | software_registry.py `com_prog_id=None` | [高] | 否（复用） |
| E-105 | UGII 定制/配置文件清单实测（ugii_env.dat、ug_cam.dpx、ug_modeling.dpx、ug_drafting.dpx、ug_sketcher.dpx、ug_assemblies.dpx、ug_analysis.dpx、ug_gdt.dpx、thd_metric.dat、xhatch.chx、ug.xla、CH_NX.BAT、gripbatch.bat、se_nxcam.bat） | 安装目录文件 | `E:\...\NX\UGII\` | [高]（文件存在） | 否（Glob 实测） |
| E-106 | NXOpen Python API 方法签名（Block/Cylinder/Extrude/Blend/Chamfer/Text/STEP 导出/布尔/错误表） | 领域技能文档 | `.user_skills\nx-automation\SKILL.md` | [高]（历史实测） | 否（复用） |
| E-107 | nx_bridge.py 桥接实现：run_python_journal + generate_parametric_nx_model（FileNew/Expressions.CreateWithUnits） | 桥接代码 | `D:\Virtu模型\bridges\nx_bridge.py` | [高] | 否（复用） |
| E-108 | NXOpen Python 12.0 / .NET 官方文档 URL（Siemens PLM docs 站） | 官方文档 URL | https://docs.plm.automation.siemens.com/data_services/resources/nx/12/nx_api/custom/en_US/nxopen_python_ref/ ；https://docs.plm.automation.siemens.com/data_services/resources/nx/1926/nx_api/custom/en_US/nxopen_net/index.html ；FS PDF https://www.plm.automation.siemens.com/en_gb/Images/nx%20programming%20and%20customization%20fs%20W%203_tcm642-4564.pdf | [高]（实际搜索返回） | 在线查询 |
| E-109 | STEP214UG 目录实测：ugstep214.def、step214ug.def、AP203/AP214/AP242 rose schema | 安装目录文件 | `E:\...\NX\STEP214UG\` | [高]（文件存在） | 否（Glob 实测） |
| E-110 | run_nx_journal.py 先例：ugraf -journal + 环境变量 UGII_BASE_DIR/UGII_ROOT_DIR/UGII_LANG=simpl_chinese | 历史脚本 | `D:\Virtu模型\run_nx_journal.py` | [高]（历史实测） | 否（复用） |
| E-111 | .prt 为 NX 原生格式，基于 Parasolid 内核（第三方说明） | 第三方文档 URL | https://www.filetypeadvisor.com/extension/prt | [中] | 在线查询 |
| E-112 | ISO 6983-1:2009 NC 程序格式（G 代码底层规范） | 官方标准 URL | https://www.iso.org/obp/ui/en/#!iso:std:34608:en | [高] | 在线查询 |
| E-113 | STEP AP203/214/242 本地 Rose schema 与 step203ug/step242.exe | 安装目录文件/EXE | `E:\...\NX\STEP214UG\*.rose`；`NXBIN\step203ug.exe`/`step242.exe` | [高] | 否（Glob 实测） |
| E-114 | JT 为 Siemens PLM 可视化/协作格式 | 官方博客 URL | https://blogs.sw.siemens.com/nx-design/siemens-open-plm-components-sdks/ | [中] | 在线查询 |
| E-115 | FANUC Macro B 变量/WHILE-DO-END 逻辑（供 NX CAM 输出后 CIMCO 校验参考） | 第三方文档 URL | https://www.mentorcnc.com/en/fanuc-custom-macro-b-guide/ | [中] | 在线查询 |

## 阶段一（插件级）新增证据 E-116 ~ E-126

| E-ID | 声明摘要 | 证据类型 | 证据位置 | 置信度 | 本轮复测 |
|---|---|---|---|---|---|
| E-116 | NXOpen 绑定 DLL 全量按域拆分：`libnxopencpp_*.dll`/`libnxopenjava_*.dll` 覆盖 cam/cae/drafting/assemblies/features/gateway/sheetmetal/routing/die/shipdesign/mechatronics/motion/sim/validation/weld/formboard/diagramming/report/geometricanalysis/facet/pdm/tooling/bodydes/layout2d/shapesearch/modldirect 等；UF 包装 `libnxopenufjava.dll`/`libnxopenufuijava.dll`；UI `libnxopenuicpp.dll`/`libnxopenuijava.dll` | 安装目录 Glob | `E:\...\NX\NXBIN\libnxopen*.dll`（约 100 个） | [高]（文件存在） | Glob 实测 |
| E-117 | NX 菜单/工具条定制系统：`ug_main.men`/`ug_gateway.men`/`ug_modeling.men`/`ug_sketcher.men` + CAM 工具条 `ug_cam_actions/create/data_preparation/geometry/mfn/objects/robotics/selection/tpanimation/tpdebug/tpdisplay/views/workpiece.tbr` + 结构/运动/出图/船舶/细分/测量 `ug_struc_*/ug_motion_*/ug_drafting_*/ug_ship_*/ug_subdiv_*/ug_inspection_*.tbr` + `custom_dirs.dat` + `styler_blocks*.pax`（simpl_chinese/trad_chinese） | 安装目录 Glob | `E:\...\NX\UGII\menus\*` | [高]（文件存在） | Glob 实测 |
| E-118 | CAM 模板集 `.opt`：cam_general/mill_planar/mill_contour/mill_multi-axis/mill_multi-axis_hsm/hole_making/lathe/lathe_mill/prismatic/feature_machining/wire_edm/nc_grip/cam_teamcenter_general | 安装目录 Glob | `E:\...\NX\MACH\resource\template_set\*.opt`（15 个） | [高]（文件存在） | Glob 实测 |
| E-119 | Post Builder 基础 TCL 库：`ugpost_base.tcl`/`ugpost_base_clsf.tcl`/`ugpost_base_group.tcl`/`ugpost_base_math.tcl`/`ugpost_base_ys.tcl`；通用机床 mill3ax/mill3ax_turbo/m4bh/m5actt/m5abtt/millturn_*/lathe_tool_tip/lathe_turret_ref/wedm*；probing_cycles_fanuc/siemens；Sinumerik 840D 3/5 axis in/mm + actt；sim_* 仿真辅助 TCL | 安装目录 Glob | `E:\...\NX\MACH\resource\postprocessor\*.tcl`（约 100 个） | [高]（文件存在） | Glob 实测 |
| E-120 | YANGJEE（杨杰）外挂定制后处理包：yangje_post*/YANGJEE*/YS5_*_Fanuc/Mitsubishi/M70_BC/KD_RTCP/XD_RTCP/YSUG3-5a/wtc_ptff*/FANUCLG/MORI/Mikron_VCP600/MITSUBISHI/roeders/electrode_cu/gr*/MS_NL1500Y_*/deckel_maho_dmcxxu/JTGK-3axis_nx3/nx4/JTFA_3_Axis-V2/FANUC-G05.1/G05P10000/HAN-4Z-X-ZG/KIR-A3/FV56-A/A14/nuoxin/xmz/steel/Deep/4B_axis/TPCC/jtjk/cnc3.0/656（.tcl+.def+.pui 三件套） | 安装目录 Glob | `E:\...\NX\MACH\resource\postprocessor\*.{tcl,def,pui}` | [高]（文件存在） | Glob 实测 |
| E-121 | installed_machines 机床/机器人库：FANUC R_2000iB、KUKA KR300、ABB IRB 6640/7600 机器人；sim01~sim18 仿真机床（3/4/5 轴/车铣/立磨双主轴），每机带 fanuc/heidenhainTNC/sinumerik/okuma/millplus 子后处理 .pui；post_configurator post_template\template\template.pui | 安装目录 Glob | `E:\...\NX\MACH\resource\library\machine\installed_machines\`、`E:\...\NX\MACH\resource\post_configurator\post_template\template\template.pui` | [高]（文件存在） | Glob 实测 |
| E-122 | GC Toolkits 国标工具包文档：GC_Toolkits_UserManual.pdf / GC_Toolkits_GearModeling.pdf / GC_Toolkits_CAM_UserManual.pdf | 安装目录 Glob | `E:\...\NX\LOCALIZATION\prc\documents\*.pdf` | [高]（文件存在） | Glob 实测 |
| E-123 | YANGJEE repack 启动壳：根目录 `中文版NX12.0.exe`/`英文版NX12.0.exe`/`tupcd.exe`/`conf.ini`（GBK，CDName=Siemens_NX_12.0.2.9_MP14_20221212 YANGJEE）/`autorun.inf`/`创建中英文快捷到桌面.exe`；`NX\NX缩略图修复.exe`；`NX\YANGJEE\jdk-19_windows-x64_bin.exe` | 安装目录 Glob + Read conf.ini | `E:\...\NX12.2.9waigua\NX12.2.9\`、`E:\...\NX\YANGJEE\` | [高]（文件存在） | Glob + Read 实测 |
| E-124 | GRIP 编译器/链接器在 NX 12 NXBIN 中已不存在（Glob `NXBIN\*grip*.exe` 无命中）；仅 `MACH\resource\template_set\nc_grip.opt` 保留兼容入口 | 安装目录 Glob（负结果） | `E:\...\NX\NXBIN\`（无命中）；`E:\...\NX\MACH\resource\template_set\nc_grip.opt` | [高]（confirmed-negative） | Glob 实测 |
| E-125 | Block UI Styler：`styler_blocks*.pax` 含 `simpl_chinese\`/`trad_chinese\` 本地化子目录 | 安装目录 Glob | `E:\...\NX\UGII\menus\` | [高]（文件存在） | Glob 实测 |
| E-126 | DEX STEP 导出历史实测：`run_nx_journal.py` 经 `DexManager.CreateStepCreator()` + `ugstep214.def` 导出 .stp | 历史脚本（复用第一轮） | `D:\Virtu模型\run_nx_journal.py`、`E:\...\NX\STEP214UG\ugstep214.def` | [高]（历史实测） | 否（复用） |

## 无证据声明（未写入知识库）
- 本轮**未**实测 COM/启动/批处理执行结果（执行通道受限）；相关项一律标 `documented-not-probed` 或 `[高]（历史实测，复用）`，无伪造实测。
- 未触碰许可证/服务器/激活内部文件（scope.md out_of_scope）。
