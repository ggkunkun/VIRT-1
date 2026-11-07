# CIMCO Edit 2026 配置文件

> 表：配置文件/目录 | 用途 | 位置 | 证据。

| 配置文件/目录 | 用途 | 位置 | 证据 |
|---|---|---|---|
| `ConfigPaths.cfg` | 定义配置根路径映射（%APPDATA%\%VENDORDIR%\%PRODUCTDIR%） | 安装根 `CIMCOEdit\ConfigPaths.cfg` | E-210 |
| 用户配置根 | `%APPDATA%\%VENDORDIR%\%PRODUCTDIR%`（默认 CFG/DATA/MACHINES/TYPES/TOOLLIBS/LOG/MACHINECFG/SAMPLES/STATE） | 运行时按 ConfigPaths.cfg 解析 | E-210 |
| `CIMCOEdit.exe.config` | .NET 运行时程序集探测路径（privatePath="dll;Msg\ToolManager"） | 安装根 | E-211 |
| `Sys\ConfigPaths-appdir.cfg` / `ConfigPaths-exedir.cfg` | 应用目录/可执行目录配置路径变体 | `CIMCOEdit\Sys\` | E-203 |
| `MachineCfg\*.mcfg` | 机床运动配置（3/5 轴） | `CIMCOEdit\MachineCfg\` | E-203 |
| `MachineCfg\*\config.json` | 机床仿真参数（Cimco Mill 3/5 轴） | `CIMCOEdit\MachineCfg\` | E-203 |
| `ToolLibs\Predefined\*.tmlib` | 刀具库 | `CIMCOEdit\ToolLibs\Predefined\` | E-203 |
| `Posts\Mill\*.js` / `Posts\Lathe\*.js` | 后处理脚本 | `CIMCOEdit\Posts\` | E-203 |
| `Templates\*.TPL` / `*.TYP` | 传输模板/文件类型定义 | `CIMCOEdit\Templates\` | E-203 |
| `Converters\*.conv` | 格式转换器 | `CIMCOEdit\Converters\` | E-203 |
| `Sys\MACHINE1.MCH`/`MACHINE2.MCH` | 机床主配置 | `CIMCOEdit\Sys\` | E-203 |
| `Sys\ToolList.txt`/`NewToolList.txt` | 刀具清单文本 | `CIMCOEdit\Sys\` | E-203 |
| `Sys\Threads.dat` | 螺纹参数表 | `CIMCOEdit\Sys\` | E-203 |
| `Sys\Notify.wav` | 传输完成提示音 | `CIMCOEdit\Sys\` | E-203 |
| `Help\*.chm` | 帮助文档（多语言） | `CIMCOEdit\Help\` | E-203 |
| `Dll\*.dll` | 运行时组件（PostProcessor/GroovingKernel/HTKernel/InspectConvert/Newtonsoft.Json） | `CIMCOEdit\Dll\` | E-203 |
| `Msg\External\ToolkitPro.ResourceZhCn.dll` | 简体中文 UI 资源 | `CIMCOEdit\Msg\External\` | E-203 |

## 备注
- `ConfigPaths.cfg` 实测定义：`ROOTDIR=%APPDATA%\%VENDORDIR%\%PRODUCTDIR%`，派生 `CFG/DATA/MACHINES/TYPES/TOOLLIBS/LOG/MACHINECFG/SAMPLES/STATE`（E-210）。
- 本文件**仅记录功能/配置位置**，不含许可证/激活相关内部文件（scope.md out_of_scope）。
- 用户实际 `%APPDATA%\CIMCO...\` 下的运行时配置未在本轮探测，标注 `documented-not-probed`。
