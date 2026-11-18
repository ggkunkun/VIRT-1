# 六大工业软件「深度学习深度」审计与评分报告

- 审计日期：2026-11-13
- 审计对象：Virtu 本地模型家族（Qwen3-8B + `cad_cam_six_software_lora`、`virtu-max:293cdac3` 等 72 个标签）+ VirtuSuperAgent 工程链
- 证据口径：`basis=measured`（全部来自只读取证：代码盘点 / 凭证抽核 / 18 份 chain 取证包统计 / 环境基线实测）；分数本身 `basis=asserted`（公开标尺打分）
- 现场推理实测：`unmeasured`（Ollama 服务离线：11434 拒绝连接、进程枚举为空）；模型层证据采用 2026-11-12 留出集实测报告
- 方法：3 路只读调查（代码实现深度 / 训练·评测·知识层 / 运行证据链）+ 原始凭证逐项抽核

---

## 0. 三句话结论

1. **模型权重层的六软件深度学习深度很浅且六软件几乎无差异**：六软件合训 LoRA = Qwen3-8B + r=32，仅 **1632 个训练样本**（每软件约 272 条份额）；六软件专属语料仅 **260 条合成 function-call 轨迹**，其中工具返回值是**硬编码伪造**（从未真正调用软件）；LoRA 产出于 2026-10-29，此后**权重从未再训练**。
2. **历史高分是关键词/格式合规率**：36 题盲测「94.4%」经重判为关键词分（尺寸保真 0.7292、13 个幻觉尺寸）；换确定性判分后 11 族留出集**原生通过 0/22、数值对 0/22**，而形态合规 22/22、护栏 14/14 全绿——**工程护栏合格，权重能力未达标**。
3. **真实能力在「知识文档 + 系统脚手架 + 确定性闸门」层，不在权重里**：模型裸分 67.20、闸门兜底 87.06、闸门接管 6/14 题。综合两轴评分：**深度学习深度（A 轴）均值 28.2/100；工程掌握深度（B 轴）复核均值 62.5/100**（同日评分卡自报 73.2）。

---

## 1. 环境基线：六大软件真实安装与自动化接口（6 个快捷方式解析，全部实测存在）

| 软件 | 真实目标（.lnk 解析 + 存在性核验） | 启动方式 | 自动化接口实测结论 |
| :-- | :-- | :-- | :-- |
| SOLIDWORKS 2021 | `C:\WINDOWS\Installer\{9C0A2571-…}\i386_SldWorks.exe`（MSI 广告快捷方式），主程序目录 `D:\SOLIDWORKS (2)` | exe | **COM 可用**：早绑定 TLB `{83A33D31-…}` v29（`bridges/solidworks_bridge.py:91-95,307`） |
| AutoCAD 2026 | `D:\cad2026\AutoCAD 2026\acad.exe`（参数 `/product ACAD /language "zh-CN"`），`accoreconsole.exe` 同目录存在 | exe + 参数 | **COM + accoreconsole 无头双通道**（`bridges/autocad_bridge.py:71,101-111,151-159`） |
| Siemens NX 12.0 | `E:\BaiduNetdiskDownload\NX 12.0.2.9\NX12.2.9waigua\NX12.2.9\中文版NX12.0.exe`（**中文外挂启动器，非原生 ugraf.exe**） | exe | 无头依赖 `NXBIN\run_journal.exe`（`bridges/nx_bridge.py:21-27`） |
| CIMCO Edit 2026 | `E:\仿真软件\CIMCOEdit_20260102\CIMCO 2026\CIMCOEdit\CIMCOEdit.exe` | exe | **无 COM/CLI**：5 个 `CIMCO.*` ProgID 均无 CLSID（`runs/full_chain/20261112_220806/chain_evidence.json:585`） |
| VERICUT 9.6 | `E:\windows64\commands\vericut.bat`（批处理启动） | bat | **COM/IPC/batch/UIA 全死**，唯一可靠驱动是 GUI（`bridges/vericut_bridge.py:30-36`） |
| 斯沃 SSCNC 7.2 | `E:\仿真软件\2斯沃7.2（内含安装说明）\SSCNC\CNCLogin.exe` | exe | 无 COM；自绘面板 Win32 读不到（`bridges/sscnc_bridge.py:95-99`） |

---

## 2. A 轴：深度学习深度评分（模型权重/语料/评测内化）

维度权重：**A1 权重内化 35% + A2 语料真实性 25% + A3 评测可证伪性 25% + A4 知识覆盖 15%**

| 软件 | A1 权重内化 | A2 语料真实性 | A3 评测可证伪 | A4 知识覆盖 | **A 轴总分** |
| :-- | --: | --: | --: | --: | --: |
| SOLIDWORKS 2021 | 26 | 20 | 30 | 80 | **34** |
| AutoCAD 2026 | 26 | 15 | 22 | 72 | **29** |
| Siemens NX 12.0 | 22 | 18 | 26 | 62 | **28** |
| VERICUT 9.6 | 24 | 18 | 18 | 78 | **29** |
| CIMCO Edit 2026 | 22 | 18 | 12 | 66 | **25** |
| 斯沃 SSCNC 7.2 | 22 | 15 | 10 | 64 | **24** |
| **均值** | | | | | **28.2** |

### 共同硬证据（六软件共性，决定 A1/A2 上限）

- 权重：`checkpoints/cad_cam_six_software_lora/training_receipt.json:3-19` —— 1632 样本、408 步、L40S、`adapter_config.json:6` r=32；`README.md:11-207` 为 PEFT 空模板（Model Card 全 `[More Information Needed]`）。
- 六软件专属语料：`knowledge_base/six_software/training/manifest.json:5-15` —— 212 train + 48 holdout = 260 条，每软件 31-38 条；`:55` 自认「语料参数全部来自 knowledge_base 静态文档枚举」；`:53` sha256 pending。
- **语料工具返回为伪造**：`training/datasets/autocad_train.jsonl:1` —— `role:"tool"` 返回硬编码 `{"status":"created","layers":6,…}`，从未真实调用 AutoCAD；知识以 system 提示词注入。
- 无真实交互轨迹：`AGENT_TRAINING_PLAN.md:45`「Agent 轨迹数据现状：0 条」；`:25`「1226 条没有一条 tool_call」。
- 权重未再训练：`benchmarks/PRODUCTION_FINAL_EVAL_2026-11-08.md:3`「权重未重新训练……任何把增益说成模型变聪明的表述都不成立」。
- 能力真相：`runs/industrial_eval_20261112/summary_holdout22_model.md:19` —— 11 族**原生通过 0/22 = 0.0%、数值对 0/22**、形态合规 22/22、removal 误差中位 2790.5%。
- 知识在提示层：`Modelfile_virtu_disciplined:96-108` SYSTEM 硬编码 14 条工业事实；`PRODUCTION_FINAL_EVAL_2026-11-08.md:12` 自认 11-07 那批 100 分「把题库答案写进 11 KB system 提示词，模型在复述提示词」。

### 分软件关键差异

- **SW（34，A 轴第一）**：知识层最厚（本体 65 行枚举 + `knowledge_base/six_software/solidworks/` 10 文件 + C 盘技能包 104 次提及、48 个能力条目、约 60 个 `sw_*.py` 脚本）；盲测 6 题尺寸保真 0.67-1.0，是唯一没有保真 0.0 题的软件。但坐标系 Y-up、ΔV 体积守恒、`diagnose_document()` 等契约要点**零评测题**。
- **AutoCAD（29）**：`blind_009/015/027` 三题关键词 100 PASS 但**尺寸保真 0.0000**（`benchmarks/cad_cam_blind_test_report.md:26-29`），A3 大幅扣分；技能包 `autocad-automation` 无 Python 实现（仅 C# 工程）。
- **NX（28）**：37 处 `documented-not-probed`（CAM 五轴/后处理基本未实测）；语料工具名 `nx.run_journal_headless` 无运行时映射；Operation Navigator 警告检查零实现零评测。
- **VERICUT（29）**：知识层最深（逆向报告 118KB + 29 处 verified-working + 17 处 confirmed-negative），但 `blind_016` 有 **8 个幻觉尺寸**；Auto-Diff 无本机 oracle、无真实色差图取证。
- **CIMCO（25）/SSCNC（24）**：24 案例基准 **0 题**；SSCNC 盲测 4/4 全部是关键词假绿（面板/CRT/G54 零数值评测）；SSCNC 语料教的 `sscnc.panel_set_mode` 在自绘面板上实际 `unsupported`（`sscnc_bridge.py:96`），语料教的是运行时做不到的操作。

---

## 3. B 轴：工程掌握深度复核（对同日评分卡 73.2 的独立重算）

沿用评分卡五维权重（知识库 15 / 接口深度 25 / 实战执行 30 / 可靠性 15 / 训练固化 15），以 **18 份 `runs/full_chain/*/chain_evidence.json`** 实测统计重算实战执行与训练固化两项：

| 软件 | 评分卡自报（复评后） | **本次复核** | 差异主因 |
| :-- | --: | --: | :-- |
| SOLIDWORKS 2021 | 79 | **77** | 一致性最高：COM 真跑 + 体积回读偏差 0.0% + STEP 落盘 |
| Siemens NX 12.0 | 74 | **72** | 18/18 全 executed、环槽 3/3 修复；但 CAM/后处理未实测 |
| AutoCAD 2026 | 81 | **70** | 4/18 blocked，最新一次 `RPC 服务器不可用`；评分卡未计入复现性波动 |
| VERICUT 9.6 | 78 | **56** | executed 仅 3/18；唯一 157 碰撞数值已被作者撤回（sidecar 冒充）；`IDLE_KILLED` |
| CIMCO Edit 2026 | 65 | **50** | executed 是「打开 NC + 标题回读」，校验全部由外部 Python 代劳 |
| 斯沃 SSCNC 7.2 | 62 | **50** | executed 是「写 NC + 菜单打开」；循环启动走刀未执行、CRT 无 OCR |
| **均值** | **73.2** | **62.5** | |

### 18 份取证包 status 统计（measured）

| 软件 | executed | substituted | blocked | 真跑率 |
| :-- | --: | --: | --: | --: |
| SOLIDWORKS 2021 | 15 | 0 | 3 | 83.3% |
| Siemens NX 12.0 | 18 | 0 | 0 | 100% |
| AutoCAD 2026 | 14 | 0 | 4 | 77.8% |
| CIMCO Edit 2026 | 14 | 4 | 0 | 77.8%（口径弱） |
| VERICUT 9.6 | 3 | 9 | 6 | 16.7% |
| 斯沃 SSCNC 7.2 | 13 | 0 | 5 | 72.2%（口径弱） |

复核降分理由：
1. 评分卡把「打开即算」计入实战执行（CIMCO/SSCNC 的 executed 无软件自身输出，只有标题回读/文件写入）。
2. 评分卡复评给「训练固化」满分因 JSONL 解析率 100%（`manifest.json:16-25`），但 260 条仍为合成语料且权重未再训练——**修 JSON 不改变训练固化**。
3. 评分卡 §6.3 自认复评为 `asserted` 口径；`knowledge_base/six_software/vericut/evidence.md:3` 自认「本轮未现场复测任何运行时通道」。
4. 闭环断点（四步模型：启动→执行→回读→取证）：SW/NX 四步全通；AutoCAD 断在启动（RPC/模态框）；CIMCO 断在执行+回读；VERICUT 断在执行+回读（11 次成功 1 次、`sim.log` 0 字节、无真实 Auto-Diff 色差图——`vc_green_mask.png` 是播放按钮模板掩膜，`vericut_link.py:44`）；SSCNC 断在执行+回读（走刀未执行、`agent_chain_executor.py:379`「本机无 OCR，未宣称跑过」）。

---

## 4. 宣称 vs 实现落差 TOP 问题（路径可核对）

| # | 落差 | 宣称侧 | 实现/真相侧 |
| :-- | :-- | :-- | :-- |
| 1 | VERICUT「无头批处理」 | `bridges/tool_calling_specs.py:181,188` | `bridges/vericut_bridge.py:30-36,43` 返回 `unsupported_headless` |
| 2 | 标准件库查询恒空 | `tool_calling_specs.py:1754-1755` 用错误键名 `SolidWorks_2021`/`standard_features` | `virtu_omni/knowledge/software_plugin_ontology.py:16` 键为 `"SOLIDWORKS 2021"` 且无该字段 |
| 3 | 悬空调用 | `virtu_omni/agent/super_agent.py:1383` 调 `vb.analyze_inspection(...)` | `cadcam_vision_bridge.py` 无此方法（仅 `inspect_vericut_autodiff/analyze_drawing_blueprint/inspect_cnc_screen`） |
| 4 | Auto-Diff 审计接线断裂 | `skills/vericut-autodiff-triage/scripts/triage_autodiff.py:20-26` 读 `red_pixels/verdict` | `cadcam_vision_bridge.py:86-94` 实际返回 `gouge_pixels/safety_verdict`，直接对接恒读 0 |
| 5 | 契约自我否认 | `AGENTS.md:7,92-99` 全能力书写 | `AGENTS.md:70-73,77` 四项「规划中（未实现）」：SWARM/Blackboard/Meta-SOP/adversarial_critic |
| 6 | 语料工具名失配 | 语料 `vericut.launch_project`、`sscnc.panel_set_mode` 等 | 运行时工具面为 14 个 `cadcam_*`；多数语料工具名无运行时映射 |
| 7 | 硬编码判词 | `extreme_cadcam_pipeline.py:192` `"ΔV > 0 Verified"` | 无实测支撑（理论公式层，与 SW COM 实测质量属性是两条不同链路） |

---

## 5. 结论

- **A 轴（深度学习深度）**：SW 34 / AutoCAD 29 / NX 28 / VERICUT 29 / CIMCO 25 / SSCNC 24，均值 **28.2/100**。六软件几乎无差异——因为六软件共享同一份浅层 LoRA，权重里几乎没有软件特有知识的差别；差异主要来自知识文档厚度与评测覆盖。
- **B 轴（工程掌握深度）**：SW 77 / NX 72 / AutoCAD 70 / VERICUT 56 / CIMCO 50 / SSCNC 50，均值 **62.5/100**。两极分化：SW/NX 可无人值守出活，VERICUT/CIMCO/SSCNC 是「半自动 + 人工复核」。
- 两轴落差 **28 vs 62** 即本项目真实画像：**能力在系统与文档里，不在权重里**。

## 6. 改进优先级

| 级 | 动作 |
| :-- | :-- |
| P0 | 把训练语料从「静态文档枚举 + 伪造工具返回」重建为**真实执行轨迹**：tool 返回必须来自 chain 链真实回读（SW 体积/NX 特征数/AutoCAD 图层计数等均有现成回读通道）；再训练并留出独立 holdout。在此之前，任何「深度学习深度提升」的说法都不成立。 |
| P1 | 评测口径换数值 oracle：关键词判分全面替换为确定性判分（参照 `runs/industrial_eval_20261112` 的 11 族）；为 CIMCO/SSCNC 补独立留出题（当前 0 题）。 |
| P1 | 修复 §4 的 5 个具体缺陷（标准件键名、`analyze_inspection` 悬空、Auto-Diff 字段对接、VERICUT 工具描述、语料工具名映射）。 |
| P2 | VERICUT GUI 通道加「窗口存活 + 事务日志 ActionMainPlay 双确认」后才计 executed（代码已具备，需纳入链判定）；SSCNC 补模板匹配 OCR 读 CRT，或正式声明「仅离线对刀」边界。 |
| P3 | 文档回收：README 标题、工具描述、AGENTS.md 正文按 §4 状态表统一口径。 |

## 7. 复现命令

```powershell
# 训练凭证与语料
Get-Content checkpoints\cad_cam_six_software_lora\training_receipt.json
Get-Content knowledge_base\six_software\training\manifest.json
Get-Content knowledge_base\six_software\training\datasets\autocad_train.jsonl -TotalCount 1

# 能力真相（deterministic holdout）
Get-Content runs\industrial_eval_20261112\summary_holdout22_model.md

# 18 份链取证 status 统计
Get-ChildItem runs\full_chain\*\chain_evidence.json | ForEach-Object { ($_ | Get-Content | ConvertFrom-Json).verdicts }
```
