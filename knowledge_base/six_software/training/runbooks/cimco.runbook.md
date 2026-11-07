# CIMCO Edit 2026 运行手册（runbook）

> 知识库上下文：`D:\Virtu模型\knowledge_base\six_software\cimco\`。
> 无 COM；自动化=命令行拉起 + 外部 Python 校验。

## 0. 速查卡
- 主程序：`E:\仿真软件\CIMCOEdit_20260102\CIMCO 2026\CIMCOEdit\CIMCOEdit.exe`
- 进程：`CIMCOEdit.exe`；无 COM
- 关键能力：FANUC Macro B 校验（#100/#500/WHILE/DO）、G 代码语法检查、背绘 backplot（G00 碰撞哨兵）、DNC 传输
- 关键插件目录：`Posts\Mill|Lathe\*.js`、`Templates\*.TPL|*.TYP|*.epl`、`Converters\*.conv`、`MachineCfg\*.mcfg`、`ToolLibs\Predefined\*.tmlib`、`Dll\ncfilter_*.dll`

## 1. GUI 操作路线

### 1.1 校验 FANUC Macro B 程序
| 步骤 | 动作 | 菜单 | 检查点 |
|---|---|---|---|
| 1 | 打开 .nc | 文件→打开 | 选 ISO_G-Code.TYP |
| 2 | 宏展开 | 编辑→Cycle Macro | #100/#500 变量可见 |
| 3 | WHILE/DO 配对 | 检查→循环配对 | DO 数=END 数 |
| 4 | 背绘 | Backplot 标签 | G00 不扎毛坯 |

### 1.2 G00 碰撞哨兵
- 背绘时提取所有 G00 行；比较快速段终点与毛坯边界；落入毛坯即报警（项目公理）。

### 1.3 DNC 传输 FANUC
- 模板：XMODEM.TPL（通用）/ FANUC-FAPT.TPL（FAPT 系统）
- Heidenhain：LSV2-HH.TPL；Mazak：MAZAK.TPL；Okuma：OKUMA.TPL

## 2. API / 自动化路线
- CIMCO 无 COM（confirmed-negative）。
- 外部拉起：`CIMCOEdit.exe <file.nc>`（命令行）。
- Macro B 校验由外部 `D:\Virtu模型\bridges\cimco_bridge.py` 复现（verified-working）：
  - 检查 #100/#500 变量声明
  - WHILE[..]DO n / END n 配对
  - G83/G71/G70/M30 闭环

## 3. 插件路线（详见 plugins.md）

| 插件 | 启动方式 | 关键文件 | E-ID |
|---|---|---|---|
| ncfilter_*.dll 方言过滤器 | 打开 .nc 自动加载 | Dll\ncfilter_fanuc.dll 等 30+ | E-212 |
| Posts\Mill|Lathe\*.js 后处理 | Post Process 菜单 | fanuc.js/haas.js/heidenhain.js/IsoLathe_*.js | E-214 |
| Backplot 仿真 | Backplot 标签 | CIMCOSimulation.exe/HTSimulation.dll | E-215 |
| DNC .TPL 传输模板 | DNC 配置 | XMODEM/LSV2-HH/FANUC-FAPT/MAZAK/OKUMA/FTPSERVER | E-217 |
| .TYP 机床类型 | 打开文件时选 | ISO_G-Code/Fanuc 30i/Heidenhain_Conversational/Mazatrol/Haas NGC | E-218 |
| Converters .conv | NC Data→Convert | fanuc/heidenhain/SinumerikTurning/NumeripathTurning | E-219 |
| MachineCfg .mcfg | 背绘机床选择 | DMG MORI/Doosan/Haas/Hermle/Quaser/Roeders/Cimco | E-220 |
| ToolLibs .tmlib | Tool Manager | ISO Mills MM/Drills/Taps + ISCAR/Secotools Holders | E-221 |
| CNCCalc | 菜单 CNCCalc | CNCCalc.dll + cnc-calc_*.chm | E-222 |
| CycleMacro | 自动展开 | CycleMacro.dll + AdvRenumbering.dll | E-223 |

## 4. 常见故障与处置
- **G00 扎料报警**：检查毛坯边界设置；G00 段不得高速扎入 raw stock（项目公理）。
- **WHILE/DO 不配对**：CycleMacro 展开失败；手动检查 DO n 与 END n。
- **#500 误判为局部变量**：#500 是公共变量；#1~#33 才是局部。
- **Mazatrol 程序语法高亮错**：选 Mazak_Mazatrol_*.TYP 而非 ISO_G-Code。
- **Heidenhain 对话程序乱码**：用 Heidenhain_Conversational.TYP；转 ISO 用 heidenhain.conv。
