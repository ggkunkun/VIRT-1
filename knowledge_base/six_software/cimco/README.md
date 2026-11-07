# CIMCO Edit 2026 知识库

> 本目录是「六软件文档化逆向」B 片（CIMCO 部分）的结构化知识库，供 Virtu 模型深度学习与操控本机 CIMCO Edit 2026 使用。
> 生成日期：2026-11-03 ｜ 授权：own_system（本机已授权软件，offline-sample preset）｜ 范围：仅功能模块 / 自动化接口 / 命令集 / 文件格式 / 工作流 / 配置，**不含任何许可证/激活/加密内部机制**。

## 1. 软件身份表

| 项 | 值 | 证据 |
|---|---|---|
| 显示名 | CIMCO Edit 2026 | E-201 |
| 版本 | 2026（2026-01-02 构建） | E-201 |
| 类别 | CNC G 代码 & FANUC Macro B 编辑器 / NC 仿真 | E-202 |
| 安装根 | `E:\仿真软件\CIMCOEdit_20260102\CIMCO 2026\CIMCOEdit` | E-201 |
| 主程序 | `CIMCOEdit\CIMCOEdit.exe` | E-201 |
| 进程名 | `CIMCOEdit.exe` | E-202 |
| COM ProgID | 无（`com_prog_id=None`） | E-202 |
| 能力标签 | `macro_b_validation`、`gcode_syntax_check`、`nc_transmission_prep`、`backplot` | E-202 |
| 验证状态 | 6/6 READY 注册表诊断中该软件 READY | E-202 |

## 2. 本目录文件清单

| 文件 | 用途 |
|---|---|
| `README.md` | 本文件：软件内索引 + 使用说明 |
| `modules.md` | GUI 功能模块树（按应用领域分块，中英文名 + 模块→命令映射 + mermaid 模块树） |
| `automation_api.md` | 自动化接口清单（无 COM；批处理启动/命令行、既有桥接封装、通道三态） |
| `commands.md` | 各模块关键命令表（可复现调用方式） |
| `file_formats.md` | NC/后处理/机床/刀具库模板格式（.nc/.js/.mcfg/.tpl/.typ/.tmlib/.conv/.cdd）+ 官方规范链接 |
| `workflows.md` | 端到端工作流（接收 NC → Macro B 校验 → G00 碰撞哨兵 → 背绘 → 后处理 → 仿真，对齐 AGENTS.md §2.D） |
| `config.md` | 配置文件位置（ConfigPaths.cfg、%APPDATA% 根、MachineCfg/ToolLibs/Sys） |
| `module_inventory.json` | 机器可读模块清单（供模型训练，与 md 严格一致） |
| `evidence.md` | 逐条证据链（E-201…E-2xx） |

## 3. 模块树总览

CIMCO Edit 2026 按应用领域划分为：**NC 编辑器（ISO G 代码）→ FANUC Macro B 校验 → G 代码语法/模态检查 → 背绘 Backplot（刀轨仿真）→ 机床仿真 Machine Simulation（*.mcfg 3/5 轴）→ CNC-Calc 计算器 → 后处理 Post Processor（*.js）→ NC 传输准备 DNC → 刀具库 ToolLibs → 格式转换 Converters（*.conv）**。详见 `modules.md`（含 mermaid 模块树）。

关键自动化入口：CIMCO **无 COM**，自动化靠「命令行 `CIMCOEdit.exe <nc_file>` 拉起」+ 既有桥接 `cimco_bridge.py` 的纯 Python 静态校验（Macro B 变量/WHILE-DO-END 配对）。详见 `automation_api.md`。

## 4. 供模型训练的使用说明

- **校验 NC 程序**：用 `cimco_bridge.py::validate_fanuc_macro_b`（#100/#500 变量、WHILE/DO/END 配对），或 `cadcam_cimco_validate` 工具（action=validate_macro）。
- **打开 NC 供人审**：`launch_in_cimco(nc_file)` → `CIMCOEdit.exe <file>`。
- **背绘/碰撞**：公理强制——背绘检查 **G00 快速进给不得高速扎入毛坯**（碰撞哨兵，AGENTS.md §2.D）。
- **配置问题**：查 `config.md`（ConfigPaths.cfg 定义 %APPDATA%\%VENDORDIR%\%PRODUCTDIR%）。
- **置信度**：所有断言带 `[高]/[中]/[低]` 与 E-ID；`documented-not-probed` 为本轮仅文档化、未现场复测项。
