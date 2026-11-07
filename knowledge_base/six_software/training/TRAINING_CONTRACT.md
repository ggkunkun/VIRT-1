# 训练语料契约（TRAINING_CONTRACT）— 六软件深度学习语料与运行手册

> 本文件是 `D:\Virtu模型\knowledge_base\six_software\training\` 的唯一格式契约（阶段二）。
> 目标：让 Virtu 模型「完全理解六大软件并熟练使用软件与插件功能」。生成基准 2026-11-04。
> 格式锚点：**严格对齐既有 tool-call 管线** —— 逐字段参照 `data/toolcall_optimal.jsonl` 样例与 `scripts/validate_render_dataset.py` 的 C1-C5 约定（C1 JSON 结构 / C2 template 渲染含 `<tools>` 段 / C3 前缀对齐掩码 / C4 loss 只落 assistant 段 / C5 tool_calls 可解析且渲染数一致）。

---

## 1. 目录结构（固定）

```
D:\Virtu模型\knowledge_base\six_software\training\
├── TRAINING_CONTRACT.md          ← 本文件
├── datasets\                     ← tool-call 训练语料（按软件分文件 + train/holdout 划分）
│   ├── solidworks_train.jsonl / solidworks_holdout.jsonl
│   ├── autocad_train.jsonl   / autocad_holdout.jsonl
│   ├── nx_train.jsonl        / nx_holdout.jsonl
│   ├── cimco_train.jsonl     / cimco_holdout.jsonl
│   ├── vericut_train.jsonl   / vericut_holdout.jsonl
│   └── sscnc_train.jsonl     / sscnc_holdout.jsonl
├── runbooks\                     ← 六软件操作运行手册（GUI+API+插件三路线）
│   ├── solidworks.runbook.md / autocad.runbook.md / nx.runbook.md
│   └── cimco.runbook.md / vericut.runbook.md / sscnc.runbook.md
├── manifest.json                 ← 汇总清单（条数/格式/划分/校验命令/sha256 留待有 shell 会话补）
└── validation_report.md          ← 静态结构校验报告（校验子代理产出）
```

## 2. 记录格式（JSONL 每行一条，OpenAI function-calling 协议）

逐字段必须与既有样例一致（参照 `D:\Virtu模型\data\toolcall_optimal.jsonl` 第 1 条）：

```json
{
  "tools": [
    {"type": "function", "function": {"name": "<software>.<action>", "description": "中文说明（1 句）", "parameters": {"type": "object", "properties": {...}, "required": [...]}}}
  ],
  "messages": [
    {"role": "system", "content": "你是 Virtu 工业智能体……（见 §3 系统提示词模板）"},
    {"role": "user", "content": "<中文任务描述，含具体参数>"},
    {"role": "assistant", "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "<software>.<action>", "arguments": "<合法 JSON 字符串>"}}]},
    {"role": "tool", "tool_call_id": "call_1", "name": "<software>.<action>", "content": "<工具回执：JSON 或代码或操作结果>"},
    {"role": "assistant", "content": "<最终总结：确认完成 + 关键参数复述>"}
  ]
}
```

**硬性规则（违反即 C5 失败/验收失败）**：
1. `arguments` 必须是**字符串化的合法 JSON**（无尾逗号、无双引号转义错误）；`tool` 回执的 `content` 可为 JSON/代码/文本，但其中若含 JSON 也须合法；
2. 每条 `tool_calls` 的 `id` 必须与后续 `{"role": "tool", "tool_call_id": ...}` 一一对应（连续编号 call_1..call_N）；
3. 多轮工具链允许：assistant(tool_calls) → tool → assistant(tool_calls) → tool → assistant(最终)；
4. `tool_calls` 里 `type` 固定为 `"function"`；`function` 对象含 `name` 与 `arguments`；
5. 每条记录必须含 `tools` 数组（可只含本次用到的工具，也可含该软件全部工具集——推荐后者，与既有样例一致：每条带全量 8 工具）；跨软件工具链记录可含多软件工具。
6. **禁止**在 messages 中出现 `system` 之外的自造角色；无 tool 的纯对话条目不进本语料（澄清/拒答类见 §5 场景 D，作为单轮无工具样本，须有 assistant 文本答案）。

## 3. 系统提示词模板（每条记录 system 内容，可微调但保持风格）

```
你是 Virtu 工业智能体，精通六大工业软件（SOLIDWORKS 2021 / AutoCAD 2026 / Siemens NX 12.0 / CIMCO Edit 2026 / VERICUT 9.6 / 斯沃数控仿真 SSCNC 7.2）及全部插件模块。
需要产出可执行代码、配置或操作步骤时，必须通过工具调用完成，不要凭空输出。先调用 <knowledge.lookup_module> 核验模块/插件事实（仅当不确定时），再调用对应软件工具。
参数必须与知识库（six_software\<software>\commands.md、workflows.md、plugins.md）一致，禁止虚构数值。
```

## 4. 工具命名约定与建议工具集

- 命名：`<software>.<action>`，action 用 snake_case；插件操作在 action 中体现插件名（如 `vericut.toolman_define_tool`、`solidworks.toolbox_insert_part`、`nx.postbuilder_configure`、`cimco.converter_translate`、`autocad.express_tools_run`、`sscnc.panel_cycle_start`）。
- 跨软件工具（沿用既有语料命名，勿改）：`cad.parse_wish_intent`（参数与既有一致：wish/material/d_outer/d_inner/num_features/fillet_r/overall_len/sweep_angle/is_multiaxis/is_die_mold，material enum 同既有 10 种）；新增 `knowledge.lookup_module`（参数：software∈六软件 key、module/plugin 名，作用：查知识库模块事实）。
- 每软件至少定义 6 个工具（覆盖 核心操作 ≥3 + 插件操作 ≥3），其中至少 1 个插到跨软件链中。工具 schema 用 OpenAI JSON Schema（type/properties/required）。

## 5. 场景类型与条数目标（每软件）

| 场景 | 说明 | 每软件 train 目标 | holdout 目标 |
|---|---|---|---|
| A. core_op | 核心操作链：建模/出图/仿真/CAM/后处理/仿真验证（参数与 workflows.md 一致） | 12-16 条 | 2-3 条 |
| B. plugin_op | 插件操作链：Toolbox/Simulation/CAM/Visualize、CUIX/ARX/LISP/Express、waigua/NXOpen add-in/Post Builder/GRIP、Converters/Posts/背绘/DNC、ToolMan/Reviewer/Assembly Manager/OptiPath/batch、面板对刀/循环启动/多控制器 | 12-16 条 | 2-3 条 |
| C. kb_lookup | 模型先 `knowledge.lookup_module` 再执行（体现"完全理解"：先核验再动手） | 4-6 条 | 1 条 |
| D. edge | 澄清（缺参数先问）/越界拒答（安全联锁、超铭牌转速、停用保护等，参照 build_train_final.py A/B 行为） | 2-4 条 | 1 条 |
| **合计** | | **30-42 条** | **6-8 条** |

- **holdout 只评测不入训**：与 train 不同参数/不同插件组合（如 train 用 ToolMan 定义车刀、holdout 用 ToolMan 定义铣刀；或材料/尺寸组合不重叠）。
- 总规模：6 软件 × (30-42 + 6-8) ≈ **216-300 条**。

## 6. 内容来源约束（防幻觉，验收项）

- 参数、路径、命令 ID、模块名、插件名**必须**来自同软件知识库：`six_software\<software>\commands.md / workflows.md / plugins.md / automation_api.md / module_inventory.json / evidence.md`（含插件场景必须引用新产出的 plugins.md 与 E-ID）；
- 用户任务描述须含**具体参数**（尺寸/材料/插件名/控制器型号等），不得空泛；
- 工具回执 content 须与知识库事实一致（如 SSCNC FANUC 0i 面板：AUTO/EDIT/MDI/JOG 模式、G54 对刀、循环启动；VERICUT Auto-Diff 红蓝绿约定；CIMCO Macro B #100/#500/WHILE-DO）；
- 严禁任何许可证/授权/激活机制相关内容进入语料。

## 7. runbook.md 结构模板（每软件一份，放 runbooks\）

```
# <软件显示名> 运行手册（runbook）
## 0. 速查卡：启动入口/进程/版本/关键文件（引用 knowledge_base 对应 README）
## 1. GUI 操作路线（逐步可执行）：核心任务 ×N（如 建法兰并导 STEP；FANUC 0i 面板循环启动）
   - 每步：动作 | 菜单位置/坐标锚点（如 VERICUT 播放按钮 1890,860 @1920×1080） | 预期结果 | 检查点（体积守恒 ΔV≠0、G00 哨兵、红蓝绿）
## 2. API/自动化路线：每核心任务给可复现调用（COM 方法签名/NXOpen/ AutoLISP/accoreconsole/bat 参数/环境变量），标注通道状态三态
## 3. 插件路线：每插件给 启动方式 + 关键操作 + API 入口（引用 plugins.md E-ID）
## 4. 常见故障与处置（来自 workflows.md 检查点与 AGENTS.md 公理）
```
- 目标读者：模型（直接作为上下文注入）与人工复核基准；每条操作必须可执行、参数具体。

## 8. manifest.json 结构

```json
{
  "generated": "2026-11-04",
  "source": "six_software knowledge base (reverse-skill RE) + TRAINING_CONTRACT",
  "total_train": <int>, "total_holdout": <int>,
  "per_software": {
    "solidworks": {"train": <int>, "holdout": <int>, "scenarios": {"core_op": <int>, "plugin_op": <int>, "kb_lookup": <int>, "edge": <int>}},
    "...": "..."
  },
  "format": "OpenAI function-calling JSONL (messages+tools), C1-C5 compatible",
  "validation_commands": [
    "python scripts/validate_render_dataset.py --data D:/Virtu模型/knowledge_base/six_software/training/datasets/<software>_train.jsonl --out data/validation/render_report_<software>.json",
    "...（6 软件 train + 6 holdout 共 12 条命令）"
  ],
  "sha256": {"<file>": "pending（需有 shell 会话补算）"},
  "notes": "静态结构校验见 validation_report.md；权威 C1-C5 需在有 python 的会话执行 validation_commands"
}
```

## 9. 校验要求

1. **静态结构校验（本轮可做，校验子代理执行）**：每文件行数=条数；每行含 `"tools"` 与 `"messages"`；`"role": "assistant"` 数与 `"tool_calls"` 出现数对应；`"tool_call_id"` 与 `"id": "call_N"` 配对；`"arguments"` 均为字符串且形如 `{...}`；无许可证关键词（license/keygen/crack/激活/授权绕过等）；输出 `validation_report.md`（C1-C5 等价静态结论 + 权威命令）。
2. **权威校验（留待有 shell 会话）**：`scripts/validate_render_dataset.py --data <file> --base checkpoints/_base_qwen3_8b`（C1-C5 全量渲染校验），命令写入 manifest。
3. 与知识库一致性抽检：每条记录的参数可从 `commands.md/workflows.md/plugins.md` 找到依据（抽查 ≥20%）。

## 10. 硬边界

- 语料与手册严禁许可证/授权/加密/激活机制内容；无破解/keygen/外部扫描；
- 工具参数禁止虚构（无知识库依据的数值不得出现）；
- 本轮 shell 不可用：不做 sha256 计算与权威渲染，如实标注 pending；不伪造校验结果。

## 11. 场景 E：fastest_route（阶段 A/B 迭代新增）

**目标**：让模型学会「自己找画图/建模/仿真/加工的最快方法」——用户提任务 → 模型选最优路线并直接落地。

### 11.1 样本结构（沿用 §2 记录格式）

```
user:  "<任务族>任务 + 具体目标 + 规模/约束（如 批量 20 张图标注；单件法兰建模；切削仿真复核；某工序加工方案）>"
assistant(tool_calls): [选中的最快路线的具体工具调用（含软件+通道+关键参数）]
tool:  "<工具回执：确认通道/参数/预期产物>"
assistant: "<最终文本：一句话说明为何选该路线（通道类型+确定性+启动开销+证据等级），复述关键参数>"
```

- **路线选择落地为真实工具调用**（调用该路线对应的 `<software>.<action>`），不是输出"建议文本"；
- 允许（非必须）先 `knowledge.lookup_module(software, module)` 核验再落地（体现"自己找"）；
- 工具名优先复用该软件 datasets 中已定义的工具；若最快路线尚无工具（如 ezdxf 批量、VERICUT batcht），可新增 `<software>.<action>`，命名与既有约定一致；
- system 提示词模板按 §3，追加一句："选择路线时优先确定性高、无进程/低启动开销、可并行的通道（证据等级 verified-working 优先）。"

### 11.2 覆盖要求（每软件）

- 四大任务族（画图/建模/仿真/加工）**各 ≥1 条** fastest_route train 样本；每软件 train 合计 **≥5 条**（上限 8 条）；
- holdout：每软件 **1-2 条**，与 train 的路线/参数**零重叠**（如 train 选 ezdxf 批量、holdout 选 accoreconsole 脚本；train 用 ToolMan 定义车刀、holdout 用批量 batcht 复核）；
- N/A 任务族（CIMCO/SSCNC 画图等）不产样本，但在相应软件 train 中可有 1 条"拒答/澄清"类说明（如"该软件职责域不含 2D 绘图"——计入 edge 亦可，标注即可）。

### 11.3 内容来源

- 最快路线判定必须来自 `fastest-methods\<software>.md` 的结论（阶段 A 产物）与知识库 E-ID/runbook；
- 关键参数（坐标锚点、bat 开关、API 方法）与 knowledge_base 一致；禁止虚构；
- 历史实测优先：VERICUT batch 不可靠（confirmed-negative）不得当作最快路线训练；GUI 坐标脆弱性要在理由文本中体现（如"GUI 复核用、批量用 batcht"）。

### 11.4 落盘与校验

- **追加**到既有 `datasets\<software>_train.jsonl` / `_holdout.jsonl`（保留既有 231 条，新增追加，行数=原条数+新增）；
- 同步更新 `manifest.json`（per_software 计数 + 新增 fastest_route 场景计数）；
- 校验：沿用独立校验子代理 C1-C5 等价静态校验（行数/配对/坏模式/arguments 闭合/边界扫描），结果并入 `validation_report.md`。
