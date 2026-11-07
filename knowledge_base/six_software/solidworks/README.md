# SOLIDWORKS 2021 — 结构化知识库（A 片文档化逆向）

> 本目录是 Virtu 模型「六软件逆向知识库」中 SOLIDWORKS 2021 分片。所有断言可回溯到同目录 `evidence.md` 的 E-ID。本轮为**文档化逆向**：因执行通道限制（PowerShell 持久故障 `HISTORY_INVALID_PATH`、Bash 禁用、桌面自动化对子代理不可用），**未现场复测 COM/启动类探测**；历史已验证判定标注 `[高]（历史实测）`，本轮仅文档化者标注 `documented-not-probed`。

## 1. 软件身份表

| 项 | 值 | 证据 |
|---|---|---|
| 显示名 | SOLIDWORKS 2021 | E-SW-01 |
| 版本 | 2021（内部主版本号 = 29，SW2021） | E-SW-02 |
| 类别 | 3D CAD / 参数化建模（Parametric Modeling） | E-SW-01 |
| 主程序路径 | `D:\SOLIDWORKS (2)\SLDWORKS.exe` | E-SW-03 |
| 进程名 | `SLDWORKS.exe` | E-SW-03 |
| COM ProgID | `SldWorks.Application` | E-SW-04 |
| 类型库 | `D:\SOLIDWORKS (2)\sldworks.tlb`，GUID `{83A33D31-27C5-11CE-BFD4-00400513BB57}`，主版本 29 | E-SW-02 |
| 能力标签 | 参数化建模 parametric_modeling / 方程管理器 equation_manager / VBA 宏 vba_macros / STEP 导出 step_export | E-SW-01 |
| 验证状态 | 六软件预检中 `solidworks ready=True, running=True`（历史实测 PID 21056） | E-SW-05 |
| 坐标系公理 | 世界 Y 向上；前视基准面=XY（法向 +Z）；上视=XZ（法向 +Y）；右视=YZ（法向 +X）；单位 mm/度；COM API 内部长度单位为米 | E-SW-06, E-SW-07 |

## 2. 本目录文件清单

| 文件 | 用途 |
|---|---|
| `README.md` | 本索引（身份表 + 文件清单 + 使用说明） |
| `modules.md` | GUI 功能模块树（按应用领域分块，中英文名，模块→命令映射，含 mermaid） |
| `automation_api.md` | 自动化接口清单（COM/VBA 宏/批处理/单实例约束，三态判定，关键对象与方法签名） |
| `commands.md` | 各模块关键命令表（菜单/工具栏/API/宏，可复现调用） |
| `file_formats.md` | 原生格式 + 导入/导出格式（含官方规范链接） |
| `workflows.md` | 端到端工作流（蓝图→CAD→FEA(FOS≥1.5)→CAM→后处理→仿真，按 SW 角色裁剪） |
| `config.md` | 设置/配置文件位置（模板、材料表、钣金表、BOM 模板等） |
| `module_inventory.json` | 机器可读模块清单（供模型训练，与 markdown 严格一致） |
| `evidence.md` | 逐条证据链（E-ID → 来源） |
| `plugins.md` | 第 10 文件：插件/附加模块（Toolbox/Simulation/PCB Viewer/eDrawings/PDM/Manage/Visualize 等） |

## 3. 模块树与自动化入口摘要

SOLIDWORKS 2021 是参数化特征建模核心：草图(SketchManager) → 特征(FeatureManager) → 方程式(EquationMgr) → 装配(Mates) → 工程图(Drawing) → 仿真(Simulation/CosmosWorks)。完整模块树见 `modules.md`。

**关键自动化入口**（详见 `automation_api.md`）：
- 进程内首选：**早绑定 COM** `win32com.client.gencache.EnsureModule(TLB_GUID,0,29,0)` → `mod.SldWorks()` → `IModelDoc2` 封装；
- 核心对象：`ISldWorks`（应用）、`IModelDoc2`（零件/装配/工程图）、`IFeatureManager`（特征）、`ISketchManager`（草图）、`EquationMgr`（方程）、`MassProperty`（质量特性）；
- 单实例硬约束：本机此版本**未注册进 ROT**，`GetActiveObject` 通常失败，桥接强制只允许一个 SLDWORKS.exe。

## 4. 供模型训练的使用说明

- **要驱动建模**：先读 `automation_api.md` 的「通道总表」确认哪条通道 verified-working，再按 `commands.md` 的签名调用；坐标一律用米（API 内部单位），1 mm = 0.001 m。
- **要搭工作流**：读 `workflows.md` 的闭环图与检查点（体积守恒 ΔV≠0、FOS≥1.5 回环）。
- **要枚举模块**：`module_inventory.json` 是机器可读事实源；`category` 枚举集合见该文件头部注释区（part_modeling / assembly / drafting / fea_simulation / data_exchange / config_admin / visualization）。
- **核验任何结论**：先回 `evidence.md` 查 E-ID；凡 `documented-not-probed` 的项，模型在无人值守执行前必须先现场复测。
