# Siemens NX 12.0（中文版）知识库

> 本目录是「六软件文档化逆向」B 片（NX 部分）的结构化知识库，供 Virtu 模型深度学习与操控本机 NX 12.0 使用。
> 生成日期：2026-11-03 ｜ 授权：own_system（本机已授权软件，offline-sample preset）｜ 范围：仅功能模块 / 自动化接口 / 命令集 / 文件格式 / 工作流 / 配置，**不含任何许可证/激活/加密内部机制**。

## 1. 软件身份表

| 项 | 值 | 证据 |
|---|---|---|
| 显示名 | Siemens NX 12.0（中文版，Unigraphics NX） | E-101 |
| 版本 | 12.0.2.9（中文版 12.0.2.9） | E-101 |
| 类别 | 高端 CAD/CAM/CAE · 多轴刀轨 | E-102 |
| 安装根 | `E:\BaiduNetdiskDownload\NX 12.0.2.9\NX12.2.9waigua\NX12.2.9\NX` | E-101 |
| 主程序 | `NX\NXBIN\run_journal.exe`（无头日志运行器）、`NX\UGII\ugraf.exe`（主 GUI）、`NX\中文版NX12.0.exe`（中文启动器） | E-101/E-103 |
| 进程名 | `ugraf.exe`、`run_journal.exe` | E-102 |
| COM ProgID | 无官方 COM ProgID（注册表无 NX ProgID；NX 走 NXOpen/UF 而非 COM Automation） | E-102/E-104 |
| 能力标签 | `nxopen_python_journal`、`parametric_expressions`、`uf_modl_csys`、`multi_axis_cam` | E-102 |
| 验证状态 | 6/6 READY 注册表诊断中该软件 READY（二进制路径实测存在） | E-102 |

## 2. 本目录文件清单

| 文件 | 用途 |
|---|---|
| `README.md` | 本文件：软件内索引 + 使用说明 |
| `modules.md` | GUI 功能模块树（按应用领域分块，中英文名 + 模块→命令映射 + mermaid 模块树） |
| `automation_api.md` | 自动化接口清单（NXOpen Python Journal、UF_MODL、run_journal.exe 命令行、环境变量；含通道三态判定） |
| `commands.md` | 各模块关键命令表（可复现调用方式） |
| `file_formats.md` | 原生/导入/导出文件格式（.prt、CLS、STEP AP203/214/242、IGES、JT）+ 官方规范链接 |
| `workflows.md` | 端到端工作流（蓝图→CAD→FEA(FOS≥1.5)→CAM→后处理→仿真，按 NX 角色裁剪，对齐 AGENTS.md 公理） |
| `config.md` | 配置文件位置（ugii_env.dat、UGII 环境变量、.dpx 定制、STEP 定义文件） |
| `module_inventory.json` | 机器可读模块清单（供模型训练，与 md 严格一致） |
| `evidence.md` | 逐条证据链（E-101…E-1xx） |

## 3. 模块树总览

NX 12.0 按应用领域划分为：**Gateway 启动与环境 → 建模（Modeling）→ 草图（Sketcher）→ 表达式（Expressions）→ 装配（Assemblies）→ 工程图（Drafting）→ 仿真（Simcenter/FEA，含 ugnx_batchmesher）→ CAM 加工操作（Operation Navigator 刀轨）→ 后处理（Post Processing/CLS）→ 数据交换（STEP/IGES/JT，DexManager）→ 自动化日志（NXOpen Journal）**。详见 `modules.md`（含 mermaid 模块树）。

关键自动化入口摘要：NX **无 COM**，主自动化通道是 **NXOpen Python Journal**（Python 3.6 随 NX 自带）经 `NXBIN\run_journal.exe` 无头执行，或 `ugraf.exe -journal script.py` 带界面执行；底层建模经 `NXOpen.UF.UF_MODL`（UFUNC）函数族。详见 `automation_api.md`。

## 4. 供模型训练的使用说明

- **操控 NX 时**：先读 `automation_api.md` 选通道（无头首选 `run_journal.exe` + 环境变量 `UGII_BASE_DIR/UGII_ROOT_DIR`），再按 `commands.md` 的命令 ID 调用对应 NXOpen API。
- **建模任务**：用 `nx_part_modeling`/`nx_sketcher`/`nx_expressions` 模块；注意坐标约定（NX 右手坐标系，单位 mm）与布尔类型 `NXOpen.GeometricUtilities.BooleanOperation.BooleanType.Create/Subtract/Unite`。
- **CAM 任务**：走 `nx_cam_toolpath`（Operation Navigator 操作导航器）→ `nx_post_processing`（生成 CLS/NC）；**公理强制：导出刀路前必须检查 Operation Navigator CAM 树的感叹号警告**（AGENTS.md §2.C）。
- **格式/配置问题**：查 `file_formats.md` / `config.md`。
- **置信度**：所有断言均带 `[高]/[中]/[低]` 与 E-ID；标注 `documented-not-probed` 的为本轮仅文档化、未现场复测的通道。
