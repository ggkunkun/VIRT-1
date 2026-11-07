# 13.63B 深度规划智能体 vs 单轮直调：实测报告

- 日期：2026-11-06 22:30 — 2026-11-07 00:16（GMT+8）
- 被测模型：`virtu-moe-14b:a2103c68`（13.6B / caps: tools, thinking, completion；digest `4007223565…`）
- MCP：`external/windows-mcp` v4.1.3，stdio，协议 `2025-06-18`
- 证据根目录：`runs/deep_agent_20261106_2235/`
- 口径：除显式标注 `asserted` 外，所有数字均为 **measured**，可回溯到具体证据文件

---

## 1. 结论先行

用户诉求「让模型深度思考拆任务而不是靠一直暴力穷举」已落地为可运行架构：

**一次结构化深度规划 → 硬闸门校验 → 计划即契约的确定性执行 → 带证据引用的验收。**

实测最有价值的发现不是"通过率"，而是**对照臂暴露的幻觉**：单轮直调桥（改造前）在 NX 根本没运行时，输出了

> 「Siemens NX 已启动，进程 ID 是 `18688`。它当前拥有 **1** 个可见窗口（主窗口）。」

而同一时刻的客观快照是 `nx_running=false, nx_process_count=0, visible_windows=0`；
`PID 18688` 经 `psutil` 核实为 **`D:\AIApps\Marvis\...\Marvis.exe`**，根本不是 NX。
证据：`baseline/bridge_trace.json`、`baseline/nx_state_after.json`。
**没有验收闸门时，2 次工具调用就足以让模型编出一个完整、自信、错误的结论。**

深度规划臂不会这样：它把每条 `success_criteria` 的 `met=yes` 与观察原文绑定，引用不到就降级为 `unsupported/unknown`，因此 v6/v7 都诚实地判了 `success=false`（见第 5 节残留风险）。

---

## 2. 架构：三段式 + 四道抗穷举闸门

`bridges/deep_agent.py`（本轮新建，约 500 行）

| 阶段 | 模型做什么 | 代码做什么 |
|---|---|---|
| **P 规划** | 在 `analysis` 字段写拆解理由，产出 `goal / success_criteria / steps[{tool,args,expect}]` | 用 Ollama `format=<JSON Schema>` **语法约束解码**保证结构合法；按真实 `tools/list` inputSchema 校验工具名、参数键、required、enum；占位符（`"..."`/`例如`/`原文`）判红 |
| **A 执行** | 不再临场决定调什么 | **计划即契约**：严格按计划里的 tool + args 调到 MCP；执行期核对改为确定性关键词比对（不让小模型现编证据引用） |
| **V 验收** | 逐条判 `yes/no/unknown` 并引用观察原文 | 证据片段必须逐字命中观察文本；只引用表头（如 `Processes (20 shown):`）判 `unsupported`；criteria 以计划为准，丢弃模型多吐的模板项 |

抗穷举硬约束：

1. **动作签名去重**：`tool + sha256(sorted args)`；同签名重复且中间无写操作 → 直接拦截，不执行。
2. **合法前后对照不误杀**：两次相同查询之间若发生过写操作（如 `App.launch`），记为 `productive_reobservation`，不算穷举。
3. **计划外写操作拒绝**：未在计划中出现的 `launch/kill/stop` 一律不执行。
4. **熔断**：连续 3 步失败即停，输出 RCFA，不继续试。

辅助确定性纠错器（不浪费模型往返）：`sanitize_plan` / `coerce_arg`
依据真实 schema 的 `anyOf/type` 删除类型非法的可选参数、把 `"640"` 转整数、把 `"true"` 转布尔、补齐缺失必填枚举、把 `on_fail` 字符串条件转成结构化 `skip_if` 谓词。
反证：`semantic_gate.py` 模拟 4 步闭环 → 4 次调用全部执行、`blocked_duplicates=0`、`SEMANTIC_GATE_OK=True`。

配套文件：`bridges/windows_mcp_bridge.py`（官方 stdio 接入，本轮加了有界传输重试）、
`runs/deep_agent_20261106_2235/{gt_snapshot.py,baseline_run.py,compare.py,finalize.py,semantic_gate.py}`。

---

## 3. 两臂对比（同一任务、同一初始状态 NX 未运行）

任务：「确认 Siemens NX 是否正在运行；没运行就启动它并确认成功；报告进程 ID 和可见窗口数量」

| 指标 | 对照臂（单轮直调） | 深度臂 v7（修复后完整执行） | 深度臂 v6（客观成功腿） |
|---|---|---|---|
| `executed_calls` | 2 | 4 | 3 |
| `unique_actions` | 2 | 3 | 3 |
| `productive_reobservations` | 0 | 1 | 0 |
| `unproductive_repeats` | 0 | **0** | **0** |
| `redundancy` | 0.0 | **0.0** | **0.0** |
| 有规划 / 有验收 | 否 / 否 | **是 / 是** | **是 / 是** |
| `plan_valid` | — | True | True |
| `hallucinated_evidence` | 未测（无该闸门） | **0** | 0（确定性执行） |
| `wall_s` | 未测（桥未记时） | 257.6 | 557.9 |
| 客观终态 NX | **未运行** | 未运行（见 §5） | **运行中 pid=19912 / 1 窗口** |
| 自述结论 | **幻觉：宣称已启动、给出假 PID** | 诚实判 `success=false` | 诚实判 `success=false` |

> `redundancy = 同签名且中间无写操作的重试 / 调用总数`。两臂都是 0，说明本任务里"暴力穷举"并非表现为重复调用，而是表现为**无验收的抢答式结论**。深度臂的价值在于把结论与证据绑定，而不是少调几次工具。
> 证据：`comparison_deep_v7.json`、`comparison_deep_v6.json`、`comparison.json`、`final_verdict.json`。

`run_id`：v6 = `1ea7b70284a8b595`，v7 = `995d8369f98def12`（内容指纹，见各腿 `deep_agent_trace.json`）。

---

## 4. 迭代中的真实失败与 RCFA（按熔断公理留痕）

| 腿 | 现象 | 根因 | 处置 |
|---|---|---|---|
| 探测 | 自由生成计划里编造 `executable_path` 参数、写不存在的 NX 路径 | 未给真实 schema | 改为从 `tools/list` 动态取 schema 并做参数键校验 |
| v1 | 3 步计划合法，但执行时把 `launch_executable+真实路径` 改成 `launch+"Siemens NX"` → 启动失败；验收照抄模板占位符 | 执行层没把计划当契约；criteria 未做占位符检测 | 加契约执行 + 占位符闸门 + criteria 权威来自计划 |
| v2 | 计划 JSON 语法错误（`"args={`、`on0fail`）；返修版只错一个可选枚举 `sort_by=pid` 却被整份判死 | 13.63B 自由生成嵌套 JSON 不可靠；闸门缺确定性纠错 | 加 `sanitize_plan` 无损纠错 |
| v3 | 连续第 2 次同类 JSON 语法崩坏 | 同构错误停滞，触发熔断 | **改设计**：改用 Ollama `format` 语法约束解码，实测 `VALID_JSON=True` 且带 `analysis` 推理字段 |
| v4 | 计划合法但模型在执行期两次不发 `tool_call` → 熔断 | 执行依赖临场工具调用 | 改为计划驱动执行 |
| v5 | 5 步全执行、0 重复，但 NX 未启动：`window_loc="centered"` 类型错（应为整数数组）触发 MCP pydantic 校验失败；模型还编了 4 次不存在的证据引用 | 缺类型校验；执行期让模型引用原文不可靠 | 加 `coerce_arg` 通用类型归一化 + 执行期核对改确定性 |
| v6 | **NX 客观启动成功**（pid 19912 / 1 窗口），但「启动后复查」被重复动作闸门误拦 | `App` 计划省略 `mode`，代码没读 schema `default=launch` | 加 `effective_mode()` |
| v7 | 4 步全执行、0 重复、0 幻觉证据；终态 NX 未存活 | 启动异步时序（见 §5） | 直连诊断排除环境锁，列为残留风险 |

中途还处理了两次环境级故障（**与模型能力无关**）：
- Ollama 托盘程序 `ollama app.exe` 用默认模型目录重启，把 E 盘模型库顶掉 → 28 个标签变 0，请求 404。已固化用户级 `OLLAMA_MODELS=E:\ollama\models` 并独立起 serve。
- 模型冷加载 24.5s 造成对照臂 HTTP 500 → 加有界传输重试（仅传输层，不改推理逻辑）。

---

## 5. 残留风险与未测项（必须如实交代）

1. **NX 启动异步时序**：`App.launch` 返回 `launched` 只是命令已发出。直连诊断实测进程在 **t+10s** 才出现并稳定存活（`nx_state_diagnostic.json`：pid 10860 / 1 窗口）。v7 与对照臂在腿结束拍快照时为 0，属时序/存活问题，不是工具调用能力问题。**当前代码尚未内置"等待目标进程出现"的状态收敛步骤** —— 这是下一步最该补的一块。
2. **自动验收偏严**：v6 客观成功但 `success=false`，因为 `Process(mode=list)` 默认只列前 20 条，NX 进程未出现在文本证据里，模型判 `no/unknown`。计划里应让复查步带 `name="ugraf.exe"` 过滤。这属于计划质量，不是闸门失灵（闸门正确地拒绝了没有证据的"通过"）。
3. **未测**：对照臂 `wall_s`（原桥未记录耗时）；`think=true` 原生 thinking 通道在本模型 tag 上返回 0 字符（深度思考实际由 `format` schema 里必填的 `analysis` 字段承载，已实测）；多任务泛化、其它工业软件（SolidWorks/VERICUT 等）未测。
4. **口径**：`success` 字段是"计划验收链路自评"，**不是**机器终态；终态一律以 `final_verdict.json` 的 `objective_success`（psutil + win32gui 枚举）为准。
5. 当前 NX 进程为直连诊断所启动（pid 10860），如不需要可自行关闭。

---

## 6. 复现

```bash
# 深度规划臂（完整：模型现场规划）
python bridges/deep_agent.py \
  --tools "ControlStatus,Process,App,Snapshot" \
  --task "确认 Siemens NX 是否正在运行；如果没在运行就启动它，并确认它真的启动成功了；最后报告 NX 的进程 ID 和它拥有的可见窗口数量。" \
  --env-facts "开始菜单名「Siemens NX 12.0」；主进程名 ugraf.exe；当前 NX 未运行。" \
  --out runs/deep_agent_xxx/deep

# 复用上一腿模型真实产出的计划（跳过昂贵规划阶段）
python bridges/deep_agent.py --plan-cache runs/deep_agent_20261106_2235/plan_cache_v6.json \
  --task "..." --out runs/deep_agent_xxx/deep_replay

# 客观终态 + 对照 + 终局判定
python runs/deep_agent_20261106_2235/gt_snapshot.py <out>/nx_state_after.json
python runs/deep_agent_20261106_2235/compare.py deep_v7
python runs/deep_agent_20261106_2235/finalize.py deep_v7
python runs/deep_agent_20261106_2235/semantic_gate.py     # 闸门反证，不碰模型
```

`asserted` 项：架构职责与闸门规则的文字描述来自源码；所有数值与终态结论均来自 `runs/deep_agent_20261106_2235/` 下的 JSON 证据。
