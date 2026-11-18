# Agent 链 × 六大工业软件 熟练度评分报告

- 评估日期：2026-11-12
- 评估对象：`VirtuSuperAgent` / `SixSoftwareOrchestrator` / 六条 `bridges/*_bridge.py` / 知识库 / 训练集 / 技能
- 评分基准：`asserted`（按公开评分规则打分）；每个分数下挂 `measured` 证据（运行日志、回读数值、行数统计）
- 复现命令见文末

---

## 1. 总评分

| 软件 | 知识库 | 接口深度 | 实战执行 | 可靠性 | 训练固化 | **加权总分** | 等级 |
| :-- | --: | --: | --: | --: | --: | --: | :-- |
| AutoCAD 2026 | 77.5 | 88 | 95 | 88 | 39 | **81** | 熟练 |
| SOLIDWORKS 2021 | 83 | 90 | 95 | 85 | 19 | **79** | 熟练 |
| VERICUT 9.6 | 97.5 | 80 | 78 | 80 | 35 | **75** | 熟练（偏窄） |
| Siemens NX 12.0 | 77 | 85 | 75 | 82 | 8 | **69** | 胜任 |
| SSCNC 7.2 | 75.5 | 55 | 52 | 88 | 39 | **60** | 入门偏上 |
| CIMCO Edit 2026 | 77 | 55 | 60 | 85 | 20 | **59** | 入门偏上 |

**六软件均值 70.5 / 100。** 结论：CAD 两件（AutoCAD / SOLIDWORKS）达到"可无人值守出活"；VERICUT 知识最深但通道脆弱；NX 建模可跑、特征不完整；CIMCO 与 SSCNC 只能算"半自动 + 人工复核"。

权重：知识库 15%（9 文件完整性 + 证据三态计数）、接口深度 25%（真实通道数与代码量）、实战执行 30%（全链回读证据）、可靠性 15%（自校验/诚实闸门）、训练固化 15%（JSONL 有效率 60% + 专属技能 40%）。

---

## 2. 分软件证据

### 2.1 AutoCAD 2026 — 81 分
- 通道三态并存且全部实测：`COM SendCommand`、`accoreconsole /i /s` 无头、`ezdxf R2018` 文件级，另有 AutoLISP 自写计数做交叉验证。
- 实测回读：[acad_probe2_20261102.log](file:///d:/Virtu模型/logs/acad_probe2_20261102.log)：新增 7 个图元、4 个规范图层、COM 计数 = LISP 自报计数 = 7、`cmdactive` 进退场均为 0、DWG 落盘。
- 知识库：10 文件，`verified-working` 17 处，`confirmed-negative` 1 处。
- 短板：训练集仅 18.4% 行可解析；例外处理依赖子进程硬超时。

### 2.2 SOLIDWORKS 2021 — 79 分
- 通道：早绑定 `EnsureModule({83A33D31-...},0,29,0)` + VBA 宏 + 质量特性回读 + STEP 导出 + 工程图标注，桥接 961 行 / 11 个公开方法。
- 实测回读：[stage01_sw_metrics.txt](file:///d:/Virtu模型/runs/full_chain/20261102_160238/stage01_sw_metrics.txt)：`VOLUME_M3=3.86792887509975E-04`，与解析体积偏差 0.0%，STEP 11841 字节；`01_CAD交付件` 另有 10 个 SLDPRT 交付件。
- 历史缺陷已根因归档：`CreateMassProperty` 成员不存在、模板缺失、晚绑定失败，均写入桥接文件头。
- 短板：训练集 18.4% 可解析；无 SW 专属技能（仅共享技能提及）；2026-10-30 曾因质量特性读取失败判 blocked，修复后才有本次数据。

### 2.3 VERICUT 9.6 — 75 分
- 知识最深：10 文件、`verified-working` 29 处、`confirmed-negative` 17 处（含 6 个 COM ProgID 判死）；`work/vericut-toolchain/vericut_link.py` 353 行 9 通道封装 + 17 张 GUI 取证截图。
- 实测回读：[vericut_probe_20261102.log](file:///d:/Virtu模型/logs/vericut_probe_20261102.log)：仿真总时长 0:01:50、空切 27%、切削距离 645.378 mm、日志增长 23698 字节且指名本次 NC。
- 硬伤：无程序化接口；`vericut.bat -b` 批处理实测 `IDLE_KILLED`（[vc_verify_20261102.log](file:///d:/Virtu模型/logs/vc_verify_20261102.log)）；同日晚些的全链中 GUI 通道又出现"启动后没有 VERICUT 窗口"；一次成功仿真仍报 94 条 errors 未逐条归因。
- 判定：能出真实仿真数值，但复现性依赖坐标锚点与窗口焦点，属"一次性可证、批量不可靠"。

### 2.4 Siemens NX 12.0 — 69 分
- 通道：`run_journal.exe` 无头执行 NXOpen Python，表达式驱动，路径白名单校验；桥接 230 行。
- 实测回读：[stage02_nx.json](file:///d:/Virtu模型/runs/full_chain/20261102_160238/stage02_nx.json)：rc=0、part 121692 字节、bbox 精确为 [-36,-36,-95,36,36,0]、4 个表达式回读。
- 硬伤：3 个环槽特征全部失败——`FeatureCollection` 无 `CreateTorusBuilder`，`feature_count=2`（预期 4）；即"能建毛坯，不能建完整零件"。知识库 `documented-not-probed` 37 处为六软件最高，CAM 五轴/后处理基本未实测。
- 训练集 0% 行可解析。

### 2.5 CIMCO Edit 2026 — 59 分
- 事实已判死：无 `Application` COM（5 个 `CIMCO.*` ProgID 均无 CLSID）、无 CLI 开关；能做的只有"拉进程打开文件 + 外部 Python 解析器"。
- 实测回读：[stage04_nc_validation.json](file:///d:/Virtu模型/runs/full_chain/20261102_160238/stage04_nc_validation.json)：窗口标题回读确认文件已载入；Macro B 包络 38 行 / 9 个运动块 / 6 个变量 / 粗精车与 M30 齐全。
- 背绘（backplot）与 G00 碰撞哨兵只能 GUI 人眼，未纳入自动链；桥接仅 120 行，G 代码语法检查是空实现（`pass`）。
- 训练集 0% 行可解析。

### 2.6 SSCNC 7.2 — 60 分
- 通道：`general.ini` 切机床 + `CNCLogin.exe` 拉起 + NC 写入控制器程序区 + `WM_COMMAND` 菜单验证；无 COM。
- 实测回读：[sscnc_20261102.log](file:///d:/Virtu模型/logs/sscnc_20261102.log)：NCT104 M / FANUC 0iT、程序 `WM2026.cnc` 1117 字节写入、窗口就绪、59 个菜单项、ini 原值已还原。
- 明确边界：面板 EDIT 键未找到，循环启动走刀未验证，日志自述"未宣称跑过"——诚实但能力到此为止。
- 训练集是六软件中最健康的（train 25%、holdout 87.5% 可解析），但基数小。

---

## 3. 横向关键发现

1. **发现率满格**：`software_registry.diagnose_all()` 实测 6/6 `ready`，SOLIDWORKS 正在运行且 COM 已注册。
2. **全链达成率在提升**：2026-10-30 为 2/6 executed，2026-11-02 为 5/6 executed（VERICUT 走替代判定）。
3. **训练固化是最大系统性短板**：六软件 12 个 JSONL 共 272 行，仅 47 行可被 `json.loads` 解析（17.28%），而 [train_six_software_cloud.py](file:///d:/Virtu模型/scripts/train_six_software_cloud.py) 的策略是"坏行跳过"——意味着 82.7% 的领域训练样本实际未入训。
4. **能力分布两极**：知识库/文档层（六软件 80+ 分）明显强于"机器可验证执行层"（CIMCO 60、SSCNC 52）。
5. **可靠性反而是强项**：六条链都能把失败写成具体根因（`IDLE_KILLED`、`-2147221021`、`CreateTorusBuilder` 缺失），未发现把未验证结果报成成功的情况。

---

## 4. 改进优先级

| 优先级 | 动作 | 指向 |
| :-- | :-- | :-- |
| P0 | 修复 12 个 JSONL 的转义（内嵌换行/引号），重跑 `authoritative_validation` | 训练固化 15% 权重，六软件共同受益 |
| P1 | NX 环槽改用 `CreateRevolve` 或 `CreateCylinder` 布尔减，补齐 4 特征 | NX 69 → 预测 75+ |
| P1 | VERICUT GUI 通道加"窗口存活 + 事务日志 ActionMainPlay 双确认"再判定 executed | 消除复现性波动 |
| P2 | CIMCO 用 `gbnf_grammar.validate_gcode_syntax` 替换 `pass` 占位 | CIMCO 59 → 65 |
| P2 | SSCNC 面板按键改 UIA/模板匹配，补循环启动证据；或正式声明"仅离线对刀" | SSCNC 60 → 68 |
| P3 | 为 SW/NX 增补专属技能（当前只被共享技能覆盖） | 技能覆盖 40% 子项 |

---

## 5. 复现命令

```powershell
# 六软件安装/进程/COM 探活
python -c "import sys;sys.path.insert(0,r'd:\Virtu模型');from bridges.software_registry import diagnose_all;print(diagnose_all()['ready_count'])"

# 训练集完整度
python scratch\_dataset_recover_check.py

# 知识库证据三态计数
python scratch\_kb_evidence_count.py

# 桥接静态审计
python scratch\_six_sw_audit.py

# 全链取证原始报告
Get-Content runs\full_chain\20261102_160238\AGENT_CHAIN_REPORT.md
```

---

## 6. 修复记录（2026-11-12 执行，"全面修复"）

### 6.1 P0 训练语料

- 实测：修复前 47/271（17.28%）可解析；修复后 **260/260（100%）** 通过 `json.loads` + 结构 + tool_call 配对 + arguments 解析。
- 处理：结构缺陷逐行修复 213 条；截断/语义残缺 11 条丢弃（不猜测补全）；原文件备份 `*.jsonl.bak_repair_20261112`。
- 产物：[validation_report.md](file:///d:/Virtu模型/knowledge_base/six_software/training/validation_report.md) §11、`authoritative_validation_report_2026-11-12.json`、`manifest.json` 计数已同步。
- 工具：`scratch/repair_six_datasets.py`、`scratch/validate_six_datasets.py`。

### 6.2 NX 环槽

- 实测探针确认 NX12 无任何 torus API（`uf.Modl` / `NXOpen.Features` 均为空），可用的是 `uf.ModlFeatures.CreateBallGroove`。
- 修复：改用 BALL_END_GROOVE，按 `groove_radii` 生成 `(z, 2R)` 槽参数；因面替换顺序敏感，加入槽序重试（正序/逆序/奇偶序）。
- 实测：默认愿望（OD53/L45/R15 R12 R10）**3/3 槽成功，feature_count=5，part 149155 bytes**，首次顺序即通过（13s）。

### 6.3 VERICUT GUI 双确认

- `play_simulation` 改为三条件确认：窗口存活可见 + 事务日志新增 >0 + `ActionMainPlay` 计数增加；失败给 `reason`（`window_closed_after_click` / `transaction_log_not_grown` / `ActionMainPlay_not_recorded`）。
- 离线注入验证通过（`scratch/test_vericut_dual_confirm.py`）：正常路径 ok=True；窗口死亡路径 ok=False 且 reason 正确。

### 6.4 CIMCO 校验

- 移除 `pass` 占位，加入 G/M 码范围、程序结束 M02/M30、主轴 M05 检查；Macro B 赋值/WHILE/表达式坐标不再被误报为非法 G 代码。
- `gbnf_grammar` 的 G00 下刀哨兵改为"纯 Z 快速"才判 CRITICAL，避免车削 `G42 G00 X[#102] Z-46` 误报。
- 实测：链路 NC `04_CIMCO_Edit_2026.nc` 现为 `valid=True, errors=[]`；`tests/test_gbnf_grammar.py` 8/8 通过。

### 6.5 SSCNC 面板边界

- 新增 `panel_capability()`：枚举子控件，明确返回 `supported/unsupported`（自绘面板说明理由）。
- 新增 `press_panel_key(label)`：有可寻址按键才 PostMessage BM_CLICK，否则返回 `unsupported`，不再伪称按键成功。
- 编排器与 `cadcam_sscnc_control` 工具 schema 已接入两个新动作。

### 6.6 复评（asserted 口径）

| 软件 | 修复前 | 修复后 | 变化依据 |
| :-- | --: | --: | :-- |
| AutoCAD 2026 | 81 | 81 | 无缺陷 |
| SOLIDWORKS 2021 | 79 | 79 | 无本轮代码缺陷 |
| VERICUT 9.6 | 75 | **78** | GUI 双确认 + 可靠性提升 |
| Siemens NX 12.0 | 69 | **74** | 环槽 3/3、feature_count 5 |
| SSCNC 7.2 | 60 | **62** | 面板能力探针 + 显式边界 |
| CIMCO Edit 2026 | 59 | **65** | 真实 G 代码校验 + 链路 NC 0 错误 |
| **均值** | **70.5** | **73.2** | — |

P3"专属技能"未新增空壳：SW/NX 的实操路径已由 `knowledge_base/six_software/*/runbook.md` 与 `extreme-cadcam-lifecycle` 覆盖，新增未实测技能会违反证据门。
