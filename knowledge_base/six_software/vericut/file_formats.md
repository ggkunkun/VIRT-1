# VERICUT 9.6 文件格式

> 官方规范来源（已在线核验）：
> - Working with Vericut Files: https://help.vericut.com/4_vericut_help/2.2_working_with_vericut_files
> - Vericut File Descriptions: https://help.vericut.com/4_vericut_help/2.3_vericut_file_descriptions
> - 本机本地帮助（bat 配置）：`CGTECH_HELP_LOCAL_DIR=E:\hhelp`，在线版 `https://help96.vericut.com/hhelp`（E-V01）

## 1. 原生格式

| 格式 | 扩展名 | 角色 | 说明 | 证据 |
| :-- | :-- | :-- | :-- | :-- |
| 工程文件 | `.vcproject` | 原生（XML 文本） | 会话设置/用户值：单位、颜色、路径、NC 程序引用；体积小但控制整个切削流程；可命令行 `CGTECH_VCPROJECT` / batch `vcp=` 指定 | E-V09 + E-V02 实测（130,757B） |
| 用户值文件 | `.usr` | 原生（XML 文本） | 与工程同类的会话设置 | E-V09 |
| 机床文件 | `.mch` / `.xmch` | 原生（XML / 加密 X-File 压缩二进制） | 机床运动学构造；`.xmch` 禁配置页、内嵌所有引用模型 | E-V09 |
| 控制文件 | `.ctl` / `.xctl` | 原生（XML） | G 代码解释规则：可解释代码列表、格式、分组、宏调用 | E-V09 |
| 刀具库 | `.tls` | 原生（ASCII） | 刀具/刀柄/夹头描述，按 Tool ID 存取；Tool Manager 维护 | E-V09 |
| 过程文件（In-Process） | `.ip` | 原生（默认压缩二进制） | 会话快照：当前切削模型、UI 设置、日志副本；`SAVE_IP` 命令记录；`CGTECH_COMPRESS=IP` 控压缩 | E-V09 |
| VERICUT Solid | `.vct` | 原生（压缩二进制） | 已切削毛坯模型；可作新会话毛坯/夹具/Design；`SAVE_VCT` 命令记录；可带/不带特征历史 | E-V09 |
| 回转体 | `.sor` | 原生（ASCII） | ZX 平面 2D 轮廓绕 Z 轴旋转；`dxf2sor.bat` 可由 DXF 生成 | E-V09 + E-V04 |
| 多边形模型 | `.swp` | 原生 | 闭合多边形挤出；格式记录头 + 法向/顶点数据 | E-V09 |
| 复查文件 | `.vcreview` | 原生（Reviewer 9.6 ZIP 容器） | 仿真复查包：NC 副本/设计 STL/ip 仿真记录/日志；本机实测 227MB、25 条目 | E-V02 实测 |
| 仿真日志 | `.log` | 原生（ASCII） | NC 程序名/错误/警告/加工时间；本项目样本 `force_turning_sample.log`（118,540B） | E-V02 实测 |
| 控制报告 | `.rpt` | 原生（ASCII） | 当前控制配置如何解释各代码：G 代码/宏动作/变量/刀具/子程序 | E-V09 |
| CGTECH 宏 | `.cme` | 原生（平台无关二进制） | CME-API 自定义宏，加工 G 代码数据处理 | E-V09 |
| 优化库 | `.olb` | 原生（ASCII） | OptiPath 进给优化数据，按刀具/材料/机床条件 | E-V09 |
| 检验序列 | `.VcInspect` | 原生（XML） | Inspection 数据表 + 检验标记 | E-V09 |
| 坐标系统文件 | CSYS file（无固定后缀） | 原生（ASCII） | APT CL 矩阵集合（CATIA/NX/PTC 语法），`csys_file` 命令行参数 | E-V09 |
| 设计点 | `.pts` | 原生（ASCII） | `GOTO/X,Y,Z[,I,J,K[,intol,outtol]]` | E-V09 |
| 后处理器文件 | `.VcPost` | 原生 | Post-Processor File | E-V09 |

## 2. NC 程序（仿真输入）

| 格式 | 扩展名 | 角色 | 说明 | 证据 |
| :-- | :-- | :-- | :-- | :-- |
| G 代码 NC | `.mcd` / `.nc`（及各 CAM 后缀） | 导入（ASCII 文本） | EIA RS-274 标准；NC Program Type = G-Code Data；本项目样本 46 行 FANUC Macro B（G71 粗车/G70 精车/M30） | E-V02 实测 + E-V09 |
| APT-CLS | `.tp` / `.cl` | 导入（ASCII 文本） | 中间刀位文件（UG CLS/CATIA APT 等变体）；Vericut 只处理 Simple ASCII APT（GOTO/CIRCLE/CYCLE） | E-V09 |
| 优化输出 | `.opti` / `.mco`（G 代码）/ `.tpo`（APT） | 导出 | OptiPath 优化后的 NC | E-V09 |

## 3. 几何模型（导入）

| 格式 | 扩展名 | 角色 | 说明 | 证据 |
| :-- | :-- | :-- | :-- | :-- |
| STEP | `.stp` / `.step` | 导入（ASCII，ISO 标准交换） | 多程序可识别的 3D 模型 | E-V09 |
| STL（SLA） | `.stl` | 导入（ASCII/二进制） | 三角面片 + 法向；本项目复查包内含设计 STL（877,145B） | E-V09 + E-V02 实测 |
| ACIS | `.sat` | 导入（ASCII） | Spatial 3D ACIS Modeler | E-V09 |
| IGES | `.igs` | 导入 | `iges2v.bat` 转换器存在 | E-V09 + E-V04 |
| CATIA V5 | `.CATPart` | 导入（二进制） | 需 CATIA V5 Model Interface（需对应许可，不在本逆向范围） | E-V09 |

## 4. 转换器 bat（E-V04，`E:\windows64\commands\`）

| bat | 用途 |
| :-- | :-- |
| `dxf2sor.bat` / `dxf2sweep.bat` | DXF → SOR / Sweep 几何 |
| `iges2v.bat` | IGES → VERICUT |
| `cad2v.bat` / `bincl2v.bat` / `sur2stk.bat` | 通用 CAD / CLS / 曲面→毛坯 |
| `polyfix.bat` | 多边形模型修复（对应 Auto-Diff 设计一致性修补） |
| `toolman.bat` / `reviewer.bat` / `bwizard.bat` | Tool Manager / Reviewer / 装配向导独立启动 |
| `nx_export.bat`、`mastercam*.bat`、`powermill.bat`、`catv*.bat`、`proev.bat`、`gibbsv.bat`、`esprit.bat`、`edgecam.bat`、`cgt_teamcenter.bat`、`cgt_zoller.bat` | 各 CAM/CAD 系统接口（版本对应启动器） |
| `vericut_console.bat` | 控制台入口 |

> 全部转换器 bat 文件存在已核验（Glob）；本轮未运行，状态 `documented-not-probed`。
