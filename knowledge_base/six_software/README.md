# 六软件逆向知识库 · 总索引（Virtu 模型深度学习语料）

> 编制：2026-11-03 ~ 2026-11-04 ｜ reverse-skill（offline-sample preset，auth.status=granted / own_system）｜ 文档化逆向：功能模块 / 自动化接口 / 命令集 / 文件格式 / 工作流 / 配置
> 统一格式契约：`SCHEMA_CONTRACT.md`（六份交付物 schema 完全一致）
> **边界声明**：本知识库不含任何许可证/授权/加密/激活机制内容；无破解/keygen/外部扫描；全部断言可回溯到各软件 `evidence.md` 的 E-ID。

---

## 1. 六软件矩阵表

| 软件 | 版本 | 类别 | 主程序路径 | 关键自动化通道（状态） | JSON 模块数 | 目录 |
| :-- | :-- | :-- | :-- | :-- | :-- | :-- |
| SOLIDWORKS | 2021 | 3D CAD / 参数化建模 | `D:\SOLIDWORKS (2)\SLDWORKS.exe` | COM `SldWorks.Application` 早绑定（verified-working，历史实测）；VBA 宏 `.swp`（confirmed-negative）；ROT 未注册（confirmed-negative） | 12 | [solidworks/](solidworks/) |
| AutoCAD | 2026 简体中文 | 2D 制图与工程图 | `D:\cad2026\AutoCAD 2026\acad.exe` | COM ActiveX `SendCommand`（verified-working）；`accoreconsole.exe /i /s` 无头（verified-working）；`ezdxf` 文件级（verified-working） | 9 | [autocad/](autocad/) |
| Siemens NX | 12.0.2.9（中文版） | 高端 CAD/CAM/CAE · 多轴刀轨 | `…\NX\NXBIN\run_journal.exe` | NXOpen Python Journal（verified-working，历史实测）；UF_MODL API；无 COM（confirmed-negative） | 11 | [nx/](nx/) |
| CIMCO Edit | 2026 | CNC G 代码 & FANUC Macro B 编辑器 | `…\CIMCOEdit\CIMCOEdit.exe` | 命令行拉起（verified-working）；外部 Python Macro B 校验（verified-working）；无 COM（confirmed-negative） | 10 | [cimco/](cimco/) |
| VERICUT | 9.6 by CGTech | 机床运动仿真 / 碰撞检测 | `E:\windows64\commands\vericut.bat` | GUI 坐标点击 + bat 官方开关 `CGTECH_VCPROJECT`/`CGTECH_TRANSACTION_LOG`（verified-working）；COM·stdin IPC·batch·UIA（confirmed-negative）；日志/`.vcreview` 回读（verified-working） | 9 | [vericut/](vericut/) |
| 斯沃数控仿真 SSCNC | 7.2 | 虚拟数控机床操作仿真 | `…\SSCNC\CNCLogin.exe` → 每控制器 `sscnc.exe` | 进程拉起 + win32gui 找窗 + 对刀量离线计算（verified-working，历史桥接）；无 COM（confirmed-negative）；面板按键/cycstart（documented-not-probed） | 9 | [sscnc/](sscnc/) |

**合计**：6 软件 × 10 文件（9 契约 + plugins.md）= 60 文件 + 1 附赠（solidworks/capability_cards.json）= 61 文件；另有 `training\` 训练产物（语料 231 条 + 6 runbook + manifest + 校验报告）。

## 2. 目录结构与统一 Schema

每个软件目录固定 **10 个文件**（schema 见 `SCHEMA_CONTRACT.md`，逐字段强制一致）：

| 文件 | 内容 | 模型训练用法 |
| :-- | :-- | :-- |
| `README.md` | 软件身份表（版本/路径/进程/COM/能力）+ 索引 + 使用说明 | 软件元数据入口 |
| `modules.md` | GUI 功能模块树（按应用领域分块，中英文名，模块→命令映射，含 mermaid 树） | 界面/功能域枚举 |
| `plugins.md` | 插件/附加模块清单（独立程序/Add-in/外挂/工具集，安装路径、API 入口、三态判定、mermaid 关系图） | 插件域枚举 |
| `automation_api.md` | 自动化通道总表（三态：verified-working / confirmed-negative / documented-not-probed）+ 关键对象与方法签名 | 驱动方式判定 |
| `commands.md` | 各模块关键命令表（菜单/面板/API/快捷键，可复现调用） | 命令-模块映射 |
| `file_formats.md` | 原生 + 导入/导出格式（含官方规范链接） | 文件级互操作 |
| `workflows.md` | 端到端闭环（蓝图→CAD→FEA(FOS≥1.5)→CAM→后处理→虚拟仿真），对齐 AGENTS.md 公理 | 编排与检查点 |
| `config.md` | 设置/配置文件位置 | 环境准备 |
| `module_inventory.json` | 机器可读模块清单（与 markdown 严格一致） | **主训练数据** |
| `evidence.md` | 逐条证据链（E-ID → 来源 → 置信度 → 是否复测） | 核验锚 |

## 3. 每软件证据摘要

| 软件 | 证据条数 | 主要证据来源 |
| :-- | :-- | :-- |
| SOLIDWORKS | E-SW-01…（十余条） | 安装目录类型库 `sldworks.tlb`/CHM 帮助族；`bridges/solidworks_bridge.py`；`software_registry.py`；官方 API 文档（help.solidworks.com） |
| AutoCAD | E-AC-01…（十余条） | CUIX/.dwt/.lsp 支持文件；`bridges/autocad_bridge.py`；DXF 规范（AC1032/R2018）；accoreconsole 官方文档 |
| Siemens NX | E-101~E-115（15 条） | NXBIN 60+ exe 实测存在；UGII/ugii_env.dat/STEP214UG；`bridges/nx_bridge.py`；docs.plm.automation.siemens.com；真实 NC 证据 `Flange_Machining.nc` |
| CIMCO Edit | E-201~E-211（11 条） | Help/Posts/MachineCfg/Converters/Dll 全量实测；`ConfigPaths.cfg`/`CIMCOEdit.exe.config`；docs.cimco.com；ISO 6983-1:2009 |
| VERICUT | E-V01~E-V10（10 条） | `vericut.bat` 168 行全文；commands/ 约 60 个转换器 bat；keybinding.txt（javap 反编译）；2026-10-30/31 先例实测报告；help.vericut.com 官方文件描述页 |
| SSCNC | E-S01~E-S06+ | 安装根 11 厂商控制器目录；JNC_BTN_Symbol 按钮位图约 40 张；config.ini/spec.ini 逐行；`bridges/sscnc_bridge.py`；swansc.com 官方对刀说明书 |

## 4. 全局缺口与局限（如实汇总）

**执行通道限制（影响全部六软件）**：本轮 PowerShell 工具为本机持久故障（`HISTORY_INVALID_PATH`）、Bash 禁用、桌面自动化对子代理不可用 → **任何运行时通道都未现场复测**。凡「历史实测」判定均复用先前会话已验证资产（如 `_diag_result.txt` 6/6 READY、VERICUT 2026-10-30 报告）并标注来源；其余一律标注 `documented-not-probed`，**无伪造实测**。建议在具备可执行 shell / 桌面自动化的会话中补测：COM 注册态、各软件启动参数、GUI 面板键鼠驱动。

| 软件 | 具体缺口 |
| :-- | :-- |
| SOLIDWORKS | 本机版本未注册进 ROT（`GetActiveObject` confirmed-negative）；`RunMacro` 仅认编译后 `.swp`（confirmed-negative）；FEA 求解器本轮未驱动（FOS≥1.5 由跨软件引擎承担） |
| AutoCAD | 启动类操作未复测；其余三通道（COM/accoreconsole/ezdxf）均已文档化并标注状态 |
| Siemens NX | COM 注册表细节、.NET NXOpen DLL 类签名、GRIP 批处理、NXBIN\*.exe 命令行参数仅文档化；Operation Navigator CAM 树感叹号检查未自动化遍历 |
| CIMCO Edit | 内部 .NET 类/接口未探测；机床仿真 GUI、DNC 串口/网络行为未探测；**背绘坐标提取无桥接实现**（cimco_bridge 仅 Macro B + token 骨架） |
| VERICUT | `parse_vcproject` 正则对当前 XML 未全命中；几何输出面板路径曾误置 F:\ 未落盘；CME-API/OptiPath/Inspection/X-Caliper/各 CAM 接口 bat 仅文档化 |
| SSCNC | 面板级键鼠自动化（cycstart/对刀软键）无实测通道；`.LIB`/offset.dat/sysparam.XML 内部取值未解析；DNC 服务行为未探测 |

## 5. 供 Virtu 模型训练的使用指引

1. **主训练数据**：`module_inventory.json`（每软件一份）——模块 ID/名称/领域分类/菜单/命令/API/格式/工作流引用，字段与 markdown 严格一致，可直接进语料管线。
2. **操作驱动**：先查 `automation_api.md` 通道三态，再按 `commands.md` 的可复现调用；`documented-not-probed` 项无人值守执行前必须先现场复测。
3. **工作流编排**：`workflows.md` 覆盖 蓝图→CAD→FEA(FOS≥1.5)→CAM→后处理→虚拟仿真 闭环，检查点与 `D:\Virtu模型\AGENTS.md` 六软件公理对齐（SW 体积守恒 ΔV≠0；AutoCAD 标准图层；NX CAM 树警告；CIMCO G00 碰撞哨兵 + Macro B；VERICUT Auto-Diff 红/蓝/绿；SSCNC 面板模式 + CRT 坐标核对）。
4. **核验纪律**：任何结论回 `evidence.md` 查 E-ID；无证据的断言在本知识库中不存在。

## 6. 配套资产（本目录外）

- 自动化桥接实现：`D:\Virtu模型\bridges\`（solidworks/autocad/nx/cimco/vericut/sscnc 六个 `*_bridge.py` + `software_registry.py` + `six_software_orchestrator.py` + `tool_calling_specs.py`）
- VERICUT 多通道链接库：`D:\Virtu模型\work\vericut-toolchain\vericut_link.py`（9 通道）
- 先例报告：`D:\Virtu模型\2026-10-30_逆向-VERICUT9.6-report.md`
- 经验回写：`D:\Virtu模型\work\six-software-re\field-journal\`（A/B/C 三片各 1 篇，脱敏）
- 六份 case scope：`D:\Virtu模型\work\reverse-<software>\scope.md`（auth.status=granted / offline）

## 7. 插件级深度逆向（阶段一）

每软件新增 `plugins.md`（第 10 文件）+ 证据追加（E-ID 见各软件 evidence.md）：

| 软件 | 插件数 | 代表插件（状态） |
| :-- | :-- | :-- |
| SOLIDWORKS | 10+ | Toolbox（verified-working，SldToolboxConfigure.exe 在盘）、Simulation FEA（verified-working，Worker+gabiswengine）、PCB Viewer（verified-working，dxp.exe）、eDrawings（documented-not-probed）、PDM（verified-working）、Manage/Visualize/Visualize Boost/Inspection/Electrical/Composer Player（documented-not-probed，.lnk 在盘）、SOLIDWORKS CAM（documented-not-probed） |
| AutoCAD | 8 | CUIX 定制（verified-working）、ObjectARX/.NET 加载（verified-working）、AutoLISP/VisualLISP（verified-working）、Express Tools（verified-working）、*.ctb 打印样式（verified-working）、动态块（documented-not-probed）、accoreconsole headless 扩展（verified-working） |
| Siemens NX | 11 | NXOpen C++/Java Binding 100 DLL（documented-not-probed）、.men/.tbr 菜单定制（documented-not-probed）、CAM 模板 15 .opt（documented-not-probed）、Post Builder 后处理体系（documented-not-probed）、YANGJEE 外挂后处理 70+ 三件套（documented-not-probed）、installed_machines 库、GC Toolkits、Block UI Styler、DEX 转换（verified-working 历史实测）、GRIP（confirmed-negative） |
| CIMCO Edit | 15 | ncfilter 方言过滤器族、NCConverter 转换族、Posts/*.js 后处理、背绘内核（G00 哨兵 verified-working 桥接）、DNC 模板 60+（XMODEM/NETWORK/LSV2）、机床 .TYP 40+、Converters .conv、刀具库 .tmlib、CNC-Calc、CycleMacro 展开（均 documented-not-probed，文件在盘实测） |
| VERICUT | 16 | ToolMan（com.cgtech.toolman.ToolManager）、Reviewer（verified-working，.vcreview 227MB 历史产物）、Assembly Manager、Single Platform、VDAF/AutoFastener、BWizard、OptiPath、Force、CME-API（官方 URL 已核验）、Optimization API、几何转换器族、CAM/CAD 接口族（batchp/batcht confirmed-negative） |
| SSCNC | 14 | CNCLogin（verified-working）、FANUC 0i 车/铣族 13 exe、KND/MITSUBISHI/Haas/Mazak/SINUMERIK/Heidenhain/HNC/MORI/JNC/NCT 控制器、SERVER DNC（ssFtp/ssHttp）、面板位图 ~40 张（存在核验）、sysparam.XML 结构解析成功、offset.dat 二进制定性 |

边界纪律：勘察中遇到的许可证工具（lmutil/swlmutil/swlmwiz、CIMCO License.dll、YANGJEE 授权文件）**一律排除、不文档化**。

## 8. 模型训练语料与运行手册（阶段二）

目录：`D:\Virtu模型\knowledge_base\six_software\training\`（契约见 `training\TRAINING_CONTRACT.md`）

| 产物 | 内容 |
| :-- | :-- |
| `datasets\`（12 个 JSONL） | OpenAI function-calling 语料：**train 合计 189 条 + holdout 42 条**（solidworks 33/7、autocad 33/7、nx 30/7、cimco 30/7、vericut 32/7、sscnc 31/7）；场景 A core_op / B plugin_op / C kb_lookup / D edge；holdout 与 train 参数/插件组合零重叠，只评测不入训 |
| `runbooks\`（6 份） | 每软件运行手册：§0 速查卡 + GUI 路线（坐标锚点/菜单路径）+ API 路线（COM/NXOpen/AutoLISP/accoreconsole/bat 参数）+ 插件路线，可直接作模型上下文与人工复核基准 |
| `manifest.json` | 条数/格式/划分/校验命令汇总（sha256 待有 shell 会话补算） |
| `validation_report.md` | 独立校验子代理产出的静态校验报告（C1-C5 等价结论） |

语料参数全部来自知识库（commands/workflows/plugins，防幻觉）；工具命名 `<software>.<action>`（如 `vericut.toolman_define_tool`、`sscnc.panel_cycle_start`、`nx.postbuilder_configure`）；全程无许可证/激活内容（D 场景为合法澄清/拒答）。

## 9. 补测与语料校验结论（阶段三）

**桌面自动化补测（如实结论）**：`computer_use_tool(plane=cu)` 本轮与上轮累计 3 次重试均返回 `40003 method not supported for plane cu`（判定为配置层面不支持、非通道占用）；`mac_computer_use_tool` 对子代理返回"不支持操作电脑"。故 **GUI/面板级键鼠补测（SSCNC 面板、VERICUT 播放、COM 注册态）本轮仍不可执行**，一律如实标注 documented-not-probed，无伪造实测。PowerShell 工具继续为持久故障（HISTORY_INVALID_PATH），已用文件工具 + 官方文档完成全部证据链。

**语料独立校验（validation_report.md）**：独立校验子代理完成 C1-C5 等价静态校验——12 个 JSONL 共 **231 条（189 train + 42 holdout）全部通过**；过程中检出并修复 **20 处缺陷**（A 片 3 处 arguments JSON 缺陷；B 片 17 处 `tool_call_id` 冒号误写 + 4 条缺失记录），复检 0 残留；id↔tool_call_id 配对平衡；边界扫描 6 处命中均为 D 场景合法拒答文本（工具名/参数零命中）；6 份 runbook 四路线齐全。**权威渲染校验待办**：`validate_render_dataset.py`（C1-C6）与逐行 `json.loads` 需在具备 python/shell 的会话执行，命令见 `training\manifest.json`。

**全程硬边界遵守**：六软件插件勘察中遇到的许可证工具（lmutil/swlmutil/swlmwiz、CIMCO License.dll、YANGJEE 授权文件）一律排除未文档化；语料与手册无破解/keygen/激活绕过内容。

## 10. 最快方法基准（阶段四迭代）

**目标**：让 Virtu 模型「自己找画图/建模/仿真/加工的最快方法」。目录 `fastest-methods\`：

| 文件 | 内容 |
| :-- | :-- |
| `FASTEST_METHODS_CONTRACT.md` | 阶段 A 格式契约（四任务族×六软件路线全集格式、7 维度量、历史实测必引清单） |
| `<software>.md` × 6 | 每软件候选路线全集（通道类型/调用路径/证据链接/度量）+ 每任务族最快结论表 |
| `fastest-methods.md` | 归并总表：每软件 × 每任务族「最快路线+次优+判定依据+置信度」+ N/A 路由 |
| `toolchain_choice_matrix.md` | 跨软件选型矩阵（14 类任务原型→软件+最快路线）+ 通道优先级原则 |

**核心结论（每任务族最快路线摘要）**：
- 画图：单件/参数化 → AutoCAD ezdxf 文件级（零进程可并行）；批量改 dwg → accoreconsole 多实例并发；SW 出三视图工程图走 COM 早绑定；NX 批量出图走 NXOpen Journal。
- 建模：NXOpen Python Journal（run_journal，verified-working [高]）与 SW COM 早绑定按下游链路选型；批量改参优先 NX Journal；AutoCAD 仅 2.5D 拉伸。
- 仿真：切削仿真首证 = VERICUT CGTECH_VCPROJECT 自动加载 + GUI 播放(1890,860) 核 ActionMainPlay；**批量复核 = .vcreview 回读**（batchp/batcht confirmed-negative 禁用）；FEA 校核 = SW Simulation API（FOS≥1.5）；SSCNC = 桥接离线算对刀。
- 加工：NX CAM 操作导航器 + Post Builder 三件套；CIMCO 外部 Python Macro B + G00 背绘哨兵；VERICUT 日志数值解析 + Auto-Diff 复核；SSCNC 离线算对刀预生成 + CRT 核对。
- 通道原则：文件级/无头 > 常驻 API > GUI；confirmed-negative 通道（VERICUT batch、SW ROT、COM 判死）绝不作最快路线。

**语料扩增（fastest_route 场景 E，TRAINING_CONTRACT §11）**：train +32、holdout +8，**总计 271 条**（train 221 + holdout 50）；每软件 train ≥5 条（四大任务族各 ≥1）、holdout 1-2 条且路线/参数与 train 零重叠；路线判定全部来自 `fastest-methods\<software>.md`。静态校验与边界扫描见 `training\validation_report.md` 复检节。
