# CIMCO Edit 2026 证据链

> 表：E-ID | 声明摘要 | 证据类型 | 证据位置 | 置信度 | 本轮是否复测。
> 本轮执行通道受限（PowerShell 故障/Bash 禁用/桌面自动化对子代理不可用），**无法现场复测**；历史已验证项标 `[高]（历史实测）`，仅文档化项标 `documented-not-probed`。

| E-ID | 声明摘要 | 证据类型 | 证据位置 | 置信度 | 本轮复测 |
|---|---|---|---|---|---|
| E-201 | CIMCO Edit 2026 安装根与主程序 CIMCOEdit.exe | 二进制路径/快捷方式 | `E:\仿真软件\CIMCOEdit_20260102\CIMCO 2026\CIMCOEdit\CIMCOEdit.exe`；`C:\Users\Public\Desktop\CIMCO Edit 2026.lnk` | [高] | 否（Glob 列目录实测） |
| E-202 | 六软件注册表：cimco=READY、进程 CIMCOEdit.exe、com_prog_id=None、能力 macro_b_validation/gcode_syntax_check/nc_transmission_prep/backplot | 桥接代码 | `D:\Virtu模型\bridges\software_registry.py`（SOFTWARE_SPECS["cimco"]） | [高]（历史实测） | 否（复用） |
| E-203 | CIMCO 安装目录实测文件清单（Help/*.chm、Posts/Mill|Lathe/*.js、MachineCfg/*.mcfg、Templates/*.TPL/*.TYP、ToolLibs/*.tmlib、Converters/*.conv、Sys/*.mch/*.txt/*.dat、Drawings/*.cdd、Samples/*.NC、Tutorials/*.pdf、Dll/*.dll、Msg/*.dll） | 安装目录文件 | `E:\...\CIMCOEdit\` | [高]（文件存在） | 否（Glob 实测） |
| E-204 | cimco_bridge.py 桥接：launch_in_cimco（Popen CIMCOEdit.exe <file>）+ validate_fanuc_macro_b（# 变量/WHILE-DO-END 配对） | 桥接代码 | `D:\Virtu模型\bridges\cimco_bridge.py` | [高]（历史实测） | 否（复用） |
| E-205 | CIMCO Edit 2026 官方在线手册（Backplot / Simulation / Backplot Setup） | 官方文档 URL | https://docs.cimco.com/en/docs/edit/2026/program-tabs/backplot/file/ ；https://docs.cimco.com/en/docs/edit/2026/simulation/ ；v6 PDF https://www.cimco.com/documentation/documents/cimco_edit/user_guides/en/cimco-edit-6-ncbase-user-guide.pdf | [高]（实际搜索返回） | 在线查询 |
| E-206 | tool_calling_specs.py：cadcam_cimco_validate（action=validate_macro/launch） | 工具定义代码 | `D:\Virtu模型\bridges\tool_calling_specs.py` | [高] | 否（复用） |
| E-207 | ISO 6983-1:2009 NC 程序格式（G 代码规范） | 官方标准 URL | https://www.iso.org/obp/ui/en/#!iso:std:34608:en | [高] | 在线查询 |
| E-208 | FANUC Custom Macro B（变量 #/IF/WHILE/G65 指南） | 第三方文档 URL | https://www.mentorcnc.com/en/fanuc-custom-macro-b-guide/ | [中] | 在线查询 |
| E-209 | Flange_Machining.nc 真实 Macro B 证据（#100=62.5、WHILE[#103 LE #104]DO 1/END 1、G83/G71/G70/M30） | NC 文件 | `D:\Virtu模型\Flange_Machining.nc` | [高] | 否（Read 实测） |
| E-210 | ConfigPaths.cfg：ROOTDIR=%APPDATA%\%VENDORDIR%\%PRODUCTDIR% → CFG/DATA/MACHINES/TYPES/TOOLLIBS/LOG/MACHINECFG/SAMPLES/STATE | 配置文件 | `E:\...\CIMCOEdit\ConfigPaths.cfg` | [高] | 否（Read 实测） |
| E-211 | CIMCOEdit.exe.config：.NET probing privatePath="dll;Msg\ToolManager" | 配置文件 | `E:\...\CIMCOEdit\CIMCOEdit.exe.config` | [高] | 否（Read 实测） |

## 阶段一（插件级）新增证据 E-212 ~ E-226

| E-ID | 声明摘要 | 证据类型 | 证据位置 | 置信度 | 本轮复测 |
|---|---|---|---|---|---|
| E-212 | NC 方言过滤器 DLL 集：`ncfilter_fanuc/siemens/heidenhain/heidiso/universalheidenhain/mazakiso/MazakIntegrex/okuma/deckel/fagor/hurco/roeders/roedershh/sodick/emco/mach3/millplus/OSAI/NUM/thermwood/xilog/iso/APT/nci/robot/wire/simple.dll` | 安装目录 Glob | `E:\...\CIMCOEdit\Dll\ncfilter_*.dll`（约 30 个） | [高]（文件存在） | Glob 实测 |
| E-213 | NCConverter 族：`NCConverter.dll`/`NCConverterNCIReader.dll`/`NCConverterPost.dll`/`NCFunc.dll`/`NCFunc-transf.dll`/`InspectConvert.dll` | 安装目录 Glob | `E:\...\CIMCOEdit\Dll\` | [高]（文件存在） | Glob 实测 |
| E-214 | JS 脚本后处理：Mill\*.js（fanuc/haas/heidenhain/Siemens 840D/Deckel 4/Fadal/Fagor 8055i/Universal Iso）+ Lathe\*.js（IsoLathe_X_{down,up}_Z_{left,right}_Processor/Siemens Lathe/IsoStoneShaper/LathPostInfo.txt）；承载 DLL PostProcessor.dll/PostProcessorDLL.dll/ReversePost.dll | 安装目录 Glob | `E:\...\CIMCOEdit\Posts\Mill\*.js`、`Posts\Lathe\*.js`、`Dll\PostProcessor*.dll` | [高]（文件存在） | Glob 实测 |
| E-215 | 背绘/仿真内核：`CIMCOSimulation.exe`/`HTSimulation.dll`/`SimulationWindow.dll`/`HTKernel.dll`/`GroovingKernel.dll`/`GroovingKernelWrapper.exe`；渲染 OpenTK.dll/OpenTK.GLControl.dll/OpenTK.Compatibility.dll/glfw3.dll/osmesa.dll/libglapi.dll/zlib1.dll；外部 `bridges/cimco_bridge.py` G00 扎料哨兵 + Macro B 校验为 Python 等价实现 verified-working | 安装目录 Glob + 桥接代码 | `E:\...\CIMCOEdit\Dll\`、`D:\Virtu模型\bridges\cimco_bridge.py` | [高] | Glob 实测 + 历史桥接 |
| E-216 | DNC 传输 DLL：`DNCServerConfig.dll`/`DNCAdmin.dll`/`NCBaseClient.dll`/`NCBaseUpgrade.dll`/`SendRecvFile.dll`/`BrowseServers.dll`/`ProtocolConfig.dll`/`SimDownloader.dll`/`CimcoAD.dll`/`LoginModuleAD.dll`/`LoginModuleApi.dll`/`LoginModuleCSV.dll`/`LogonDialog.dll` | 安装目录 Glob | `E:\...\CIMCOEdit\Dll\` | [高]（文件存在） | Glob 实测 |
| E-217 | DNC 协议模板 .TPL：XMODEM/NETWORK/GENERICS/GENERIC-PERCENT/GENERIC-MONMACROS/BINARY/TEXTFILE；Heidenhain LSV2-D4/D11/HH + HEIDENHAIN.TPL + MONITORTNC；FANUC FAPT/FAPT-BUBBLE/FAPT-OLD-BUBBLE/FILEMATE/HANDYFILE；Mazak MAZAK/MAZAKISO/MAZAKT1/MONITORMAZAK/MDCPORT；Okuma OKUMA/OKUMAB/Okuma.epl；Bridgeport/BrotherQD2/QD3/Fagor/Fagor8050/Fagor8055T/HurcoConv/OSAI/Paragon/SiemensDirmon/Woyda/Farley/Messer/Andon；等离子 PLASMAESAB*/*PHOENIX/*SHAPE/*AMC4；AGIECLASSIC/AGIECUT；BARCODE.TPH/QTERMII-40.TPH/I7000.TPM；FTPSERVER/FtpClient.epl/Generics.epl | 安装目录 Glob | `E:\...\CIMCOEdit\Templates\*.TPL`/`.epl`/`.TPM`/`.TPH`（约 60 个） | [高]（文件存在） | Glob 实测 |
| E-218 | 机床文件类型模板 .TYP：ISO_G-Code/ISO Milling/ISO Turning；Fanuc 30i-31i-32i(M/T)/Fanuc MX；Heidenhain Conversational/Milling/Milling with Turning/ISO Milling；Siemens Milling/Turning；Mazak 全系列（MAZATROL/Milling/Turning/Fusion 640 T/Matrix MC/Integrex EI/SmoothAi/T）；Mitsubishi M700-70 L/M800-80 MC；Okuma Milling/Turning；Haas VR 96-8300J/NGC Milling/UMC Milling/Turning；Fagor Milling/Turning；Hurco Winmax M；Brother D00 M；Centroid Milling/Turning；Roeders RMS-6；NumeriPath 8000 M/T；OSAI Mill 10；Delectron Z32 M；Fidia Milling；Flexium NUM；TEMPLATE_APT；Formulas；MultiChannelSystemTemplates.json | 安装目录 Glob | `E:\...\CIMCOEdit\Templates\*.TYP`（约 40 个） | [高]（文件存在） | Glob 实测 |
| E-219 | 方言转换器 `.conv`：fanuc/heidenhain/SinumerikTurning/NumeripathTurning | 安装目录 Glob | `E:\...\CIMCOEdit\Converters\*.conv` | [高]（文件存在） | Glob 实测 |
| E-220 | 机床配置 `.mcfg`：DMG MORI.DMC/Doosan/Haas/Hermle/Quaser/Roeders/Cimco 3 Axis/Cimco 5 Axis | 安装目录 Glob | `E:\...\CIMCOEdit\MachineCfg\*.mcfg` | [高]（文件存在） | Glob 实测 |
| E-221 | 刀具库 `.tmlib` 14 个：ISO Drills/Mills MM/Taps/Spot drills/Counter sinks；Inch 全套；Holders/ISCAR Holders Metric/Secotools Holders Inch/Metric；承载 ToolList.dll/ToolManager.dll | 安装目录 Glob | `E:\...\CIMCOEdit\ToolLibs\Predefined\*.tmlib`、`Dll\ToolList.dll`/`ToolManager.dll` | [高]（文件存在） | Glob 实测 |
| E-222 | CNC-Calc：`Dll\CNCCalc.dll` + `Help\cnc-calc_*.chm` | 安装目录 Glob | `E:\...\CIMCOEdit\Dll\CNCCalc.dll`、`Help\cnc-calc_*.chm` | [高]（文件存在） | Glob 实测 |
| E-223 | 宏循环/程序段重排：`CycleMacro.dll`/`AdvRenumbering.dll`；外部 `bridges/cimco_bridge.py` FANUC Macro B 静态校验（#100/#500/WHILE/DO/END 配对）verified-working | 安装目录 Glob + 桥接代码 | `E:\...\CIMCOEdit\Dll\`、`D:\Virtu模型\bridges\cimco_bridge.py` | [高] | Glob 实测 + 历史桥接 |
| E-224 | 测量接口：`Inspect.dll`/`InspectDll.dll`/`InspectConvert.dll`；测头数据 `X8/X16/X24/X32/X48.MDF` | 安装目录 Glob | `E:\...\CIMCOEdit\Dll\` | [高]（文件存在） | Glob 实测 |
| E-225 | UI/编辑器基础：`EditorConfig.dll`/`Bindings.dll`/`FileDialogs.dll`/`Fileselector.dll`/`FileDirSelector.dll`/`Localization.dll`/`MiscDialogs.dll`/`MachineSetup.dll`/`MachineConfigurationEditorDll.dll`/`NewMachineConfigurationEditor.dll`/`WebView2Loader.dll`/`Office2016.dll`/`Microsoft.Xaml.Behaviors.dll`/`Xceed.Wpf.Toolkit.dll`/`Newtonsoft.Json.dll`/`System.ValueTuple.dll`/`libxml2.dll`/`iconv-2.dll` | 安装目录 Glob | `E:\...\CIMCOEdit\Dll\` | [高]（文件存在） | Glob 实测 |
| E-226 | Oracle OCI 运行时（Teamcenter/MES 集成）：`oci.dll`/`oraociicus.dll` | 安装目录 Glob | `E:\...\CIMCOEdit\Dll\` | [高]（文件存在） | Glob 实测 |

> 注：`Dll\License.dll` 在磁盘存在，按硬边界不对其功能做任何分析，故不单列 E-ID。

## 无证据声明（未写入知识库）
- 本轮**未**实测 COM/启动/背绘 GUI 回读结果（执行通道受限）；相关项标 `documented-not-probed` 或 `[高]（历史实测，复用）`，无伪造实测。
- 未触碰许可证/激活相关内部文件（scope.md out_of_scope）。
