# 六软件逆向知识库 Schema 契约（统一模板）

> 本文件是 `D:\Virtu模型\knowledge_base\six_software\` 下全部六份软件知识库的**唯一格式契约**。三个分片子代理必须逐字段遵守，保证六份交付物结构完全一致、JSON 与 Markdown 严格对应。生成日期基准：2026-11-03。

---

## 1. 目标与硬边界

- **目标**：对六款本机已授权软件做「功能模块 / 自动化接口 / 命令集 / 文件格式 / 工作流 / 配置」的**文档化逆向**，产出供 Virtu 模型深度学习/训练 AI 智能体操控这些软件的结构化知识库。
- **授权**：`auth.status=granted`（own_system；用户为本机 owner，软件为用户自有安装）；`network_profile=offline` 优先，官方文档站可在线补充。
- **硬边界（违反即失败）**：
  - 严禁触碰许可证/授权/加密/激活相关内部机制；严禁任何破解、绕过、keygen 内容；
  - 不得扫描或触及任何外部目标；
  - 禁止无证据断言——所有事实必须可回溯到 evidence.md 的 E-ID。

## 2. 目录结构（固定）

`D:\Virtu模型\knowledge_base\six_software\<software>\` 下 **10 个文件**（9 契约 + plugins.md），`<software> ∈ {solidworks, sscnc, cimco, autocad, vericut, nx}`；阶段二训练产物位于 `D:\Virtu模型\knowledge_base\six_software\training\`（格式见 `training\TRAINING_CONTRACT.md`）：

| 文件 | 内容 |
|---|---|
| README.md | 软件内索引（身份表 + 文件清单 + 使用说明） |
| modules.md | GUI 功能模块树（按应用领域分块，中英文名，模块→命令映射） |
| plugins.md | 插件/附加模块清单（独立程序/Add-in/外挂/工具集，中英文名、安装路径、API 入口、三态判定、mermaid 关系图） |
| automation_api.md | 自动化接口清单（COM/NXOpen/AutoLISP/批处理/环境变量/DDE，关键对象与方法签名，判死通道如实记录） |
| commands.md | 各模块关键命令表 |
| file_formats.md | 原生格式 + 导入/导出格式 |
| workflows.md | 端到端工作流（含关键参数与检查点） |
| config.md | 设置/配置文件位置 |
| module_inventory.json | 机器可读清单（供模型训练） |
| evidence.md | 逐条声明的证据来源 |

## 3. 通用写作规则

1. **语言**：简体中文为主；英文专有名词 / 命令 / API 原名保留，置于括号或代码块。
2. **置信度**：每条关键断言标注 `[高]/[中]/[低]` 并引用证据 `E-<n>`（见 evidence.md）。
3. **复用已验证资产（勿重新推导）**：
   - `D:\Virtu模型\bridges\software_registry.py`（六软件路径/COM/能力，6/6 READY 已验证）；
   - `D:\Virtu模型\_diag_result.txt`（6/6 READY 诊断输出）；
   - `D:\Virtu模型\bridges\<software>_bridge.py`（各软件自动化桥接实现 = 接口证据）；
   - `D:\Virtu模型\2026-10-30_逆向-VERICUT9.6-report.md`（质量模板：Evidence-Finding-Path 表、逐通道判定、可复现命令、坐标/参数具体化、置信度标注）；
   - `D:\Virtu模型\work\vericut-toolchain\`（VERICUT 先例：scope.md / vericut_link.py / keybinding.txt / vericut-toolchain-flow.mmd）；
   - 用户已装领域技能 SKILL.md：`workspace\.user_skills\` 下 nx-automation / solidworks-* / autocad-* / cnc-milling / cnc-lathe / dwg-analysis / iges-wireframe-reverse（作为自动化接口证据源）；
   - 项目 `D:\Virtu模型\AGENTS.md` 六软件操作公理（知识库领域事实须与之对齐）。
4. **判死通道如实记录**为 `confirmed-negative`（先例：VERICUT COM 6 个 ProgID 全部判死 `-2147221005`、stdin IPC 无响应）。
5. **本轮执行通道限制（必须如实标注）**：PowerShell 工具为持久故障（`HISTORY_INVALID_PATH`）、Bash 禁用、桌面自动化对子代理不可用——**本轮无法现场复测 COM/启动类探测**。凡属「复用历史已验证资产」的判定标注 `[高]（历史实测，见证据）`；凡属「本轮未复测、仅文档化」的通道标注 `documented-not-probed`；**禁止伪造任何实测结果**。

## 4. 每文件结构（模板）

### 4.1 README.md（软件内索引）
1. 软件身份表：显示名 / 版本 / 类别 / 主程序路径 / 进程名 / COM ProgID / 能力标签 / 验证状态（6/6 READY 中该软件状态）
2. 本目录文件清单与用途表
3. 模块树总览（1-2 段 + 指向 modules.md）+ 关键自动化入口摘要（指向 automation_api.md）
4. 供模型训练的使用说明（每个文件怎么读、怎么用）

### 4.2 modules.md — GUI 功能模块树
- 按**应用领域分块**，每块包含：
  - 菜单条目：中文名(英文原名)、所属菜单路径；
  - Ribbon / 工具栏 / 面板：组名与按钮名；
  - **模块→命令映射**：模块名 → commands.md 中的命令 ID 列表。
- 结构：层级列表 + **至少一个 mermaid 模块树**（` ```mermaid flowchart TD ... ``` `）。
- 证据来源：安装目录自带 help/文档、菜单定义文件（SolidWorks `.cui/.sldCui`、AutoCAD `CUIX`、NX `.men/.tbr`、CIMCO 菜单资源、SSCNC 界面文档/截图）、官方在线文档。

### 4.3 automation_api.md — 自动化接口清单
- **通道总表**：`通道 | 入口/ProgID/路径 | 状态(verified-working / confirmed-negative / documented-not-probed) | 证据`
- 每通道细节：
  - COM：ProgID、类型库路径、关键对象与核心方法签名（如 `SldWorks.ISldWorks::OpenDoc6`、`AcadApplication.ActiveDocument.ModelSpace`）；
  - 脚本：VBA 宏（SW）、AutoLISP（AutoCAD）、NXOpen Python Journal + UF_MODL（NX）；
  - 批处理/命令行：`vericut.bat` 参数透传、`accoreconsole.exe /i /s`、`run_journal.exe`、`CNCLogin.exe` 参数；
  - 环境变量：`CGTECH_VCPROJECT`、`CGTECH_TRANSACTION_LOG=Yes`、`UGII_*`、AutoCAD 支持路径等；
  - 文件级通道：DDE、stdin IPC、工程文件自动加载（`CGTECH_VCPROJECT` 先例）；
  - 无 COM 软件（SSCNC/CIMCO）如实记录，并列出既有桥接封装（`sscnc_bridge.py` / `cimco_bridge.py`）的实现方式与局限。

### 4.4 commands.md — 各模块关键命令表
表：`命令 ID | 模块 | 类型(菜单/工具栏/命令行/API/宏/快捷键) | 参数/坐标 | 说明 | 证据`
- 每条命令给出**可复现的调用方式**（菜单路径、LISP 函数、NXOpen 调用、快捷键等）。

### 4.5 file_formats.md — 文件格式
表：`格式 | 扩展名 | 角色(原生/导入/导出) | 说明 | 证据`
- 含官方格式规范链接（DXF 规范、STEP AP203/214、SLDPRT、NX part、VERICUT .vcp/.cl/.tl 等，URL 必须来自实际搜索/抓取结果）。

### 4.6 workflows.md — 端到端工作流
- 至少覆盖项目级闭环（按软件角色裁剪）：**蓝图 → CAD 参数化建模 → FEA 强度校核(FOS≥1.5) → CAM 编程 → 后处理 → 虚拟加工仿真（VERICUT Auto-Diff / SSCNC）**；
- 每流程：步骤序列 | 涉及模块与命令 | 关键参数（公差、FOS、坐标、进给、安全高度）| 检查点（体积守恒 ΔV≠0、G00 快速进给碰撞哨兵、Auto-Diff 红=过切/蓝=残料/绿=合格）；
- 与 AGENTS.md 公理对齐。

### 4.7 config.md — 设置与配置文件
表：`配置文件/目录 | 用途 | 位置(注册表/用户目录/安装目录) | 证据`

### 4.8 module_inventory.json — 机器可读（供模型训练）

精确 JSON Schema（必须与 commands.md / modules.md / automation_api.md 严格一致）：

```json
{
  "software": "<canonical key: solidworks|sscnc|cimco|autocad|vericut|nx>",
  "display_name": "<官方显示名>",
  "version": "<版本号，如 2021 / 7.2 / 2026 / 9.6 / 12.0.2.9>",
  "generated": "2026-11-03",
  "source": "reverse-skill offline-sample RE; evidence.md",
  "modules": [
    {
      "id": "<software>_<domain>_<module>",
      "name": "中文名 (English name)",
      "category": "part_modeling",
      "menu": ["文件|新建", "插入|草图绘制"],
      "commands": ["<命令 ID，与 commands.md 一致>"],
      "api": ["ISldWorks::SketchManager", "NXOpen.UF.UF_MODL", "AutoLISP: command"],
      "file_formats": ["SLDPRT"],
      "workflow_refs": ["wf_blueprint_to_cad"],
      "notes": "一句话说明（含置信度）"
    }
  ]
}
```

- `category` 枚举（可扩展，须在 README 中声明用到的集合）：`part_modeling / assembly / drafting / fea_simulation / cam_toolpath / post_processing / nc_editor / virtual_machine / data_exchange / config_admin / collaboration / visualization / simulation_verification`。
- JSON 必须是**合法 JSON**（无注释、无尾逗号、双引号字符串）；内容与 Markdown 严格一致（验收项）。

### 4.9 evidence.md — 证据链
表：`E-ID | 声明摘要 | 证据类型(二进制路径/帮助文档/注册表/官方文档URL/桥接代码/先例报告) | 证据位置 | 置信度 | 本轮是否复测`
- 禁止无证据声明；官方文档 URL 必须真实（来自 general_search / web_fetch 实际返回，不得编造）。

### 4.10 plugins.md — 插件与附加模块清单（阶段一新增）
1. **插件总表**：`名称（中文名+英文名） | 类型（独立程序/Add-in/外挂/工具集） | 安装路径或桌面快捷方式 | 可执行/库文件 | 与主程序集成方式（菜单/启动器/API） | 状态三态 | 证据 E-ID`
2. 每插件一节：功能域、启动方式、自动化接口（API 入口/命令）、文件格式、关键操作（可复现）；
3. **mermaid 插件关系图**（主程序 ↔ 各插件）；
4. 证据链并入 evidence.md（追加 E-ID），三态判定纪律与 4.3 相同；
5. 硬边界：只文档化插件功能与接口，严禁触碰许可证/激活机制（尤其插件授权文件）。

## 5. 质量与验收标准

- 每软件 **10 个文件**齐全（9 契约 + plugins.md），落在 `D:\Virtu模型\knowledge_base\six_software\<software>\`；
- GUI 模块树按领域分块、含中英文名、含 mermaid 图；
- 自动化接口含状态判定（verified-working / confirmed-negative / documented-not-probed 三态齐全）；
- 命令表 / 格式 / 工作流 / 配置齐全；工作流与 AGENTS.md 公理对齐；
- JSON 与 Markdown 一致；无任何许可证绕过内容；
- 全部断言可回溯到 evidence.md。
