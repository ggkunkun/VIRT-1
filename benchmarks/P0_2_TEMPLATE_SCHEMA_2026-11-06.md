# P0-2 执行报告：模板一致性 + 参数级约束解码（2026-11-06）

> **结论先说：这条路线被自己的数据否证了。** 原定三项子任务中，两项在动手前就已经没有对象（线上早已修好），第三项（约束解码）实测净增益 **+0.37/100**，由 5 例变动构成、3 增 2 减，不构成能力改进。本文同时交付一个已修的判分器 bug、三条新发现的用例缺陷，以及一份可归因的 A/B 台账。
>
> 本文不宣称任何"提升 X 分"。所有数字带 `run_id` + `n` + 证据路径 + 口径。

---

## 0. 口径与归因

| 项 | 值 |
|---|---|
| `run_id` | `fe53bb7e1dc1e40e` |
| 被测构件 | `virtu-comprehensive:latest`，权重层 `c3b78c7735c9ac1f`（4,614,297,600 B）、template `bdae0a81055c0aa2`（1434 B）、system `6f29675499aa0cdc`（879 B） |
| 用例 | `data/benchmark/virtu_eval_cl_v1/toolrouting.jsonl`，n=30（全量，非抽样） |
| 判分器 | `virtu_eval/graders.py`（本次已修改，sha 变化，见 §2） |
| 采样 | `temperature=0, top_p=0.95, seed=1234, num_ctx=8192`，`num_predict` 逐例取用例自带的 256/448/704 |
| 噪声带 | **同臂重测 30/30 原文逐字节相同，分数变动 0/30**（详见 §3.2） |
| 证据 | `scratch/_p02_probe_{A1_unconstrained,A2_repeat,B1_schema}.jsonl`（含逐例原文与逐条判据） |
| 台账 | `scratch/_p02_ab_report.json`、`scratch/_p02_run_identity.json` |

**不可与历史数字直比**：全板基线 `run_id dde13885346d93ff` 测的是 `virtu-frozen:comp_v5`（template `53e6e1ca3b6cbb00`、system `9f4faa44ed3d2528`），与本文的 `bdae0a81` / `6f29675` **不是同一把尺**。更严重的是**用例集本身也漂移了**，详见 §1.4。

---

## 1. 勘误：原计划有两条已无对象

### 1.1 线上模板不是 156 字符，且早就支持 tools

方案 v2 §1 写着"线上生效 chat template 是 156 字符老式单轮模板、无 `.Tools/.ToolCalls` → 带 tools 请求 HTTP 400"。**这条引用的是 `VIRTU_FULL_BOARD_2026-11-05.md:31`，但漏读了同一文件 `:36` 的时界说明**：

> 「时间界（重要）：这条结论只对 09:5x 的字节成立。11:2x 复核，标签又被换过：`virtu-frozen:comp_v5` 与两个部署标签的 template 层分别是 `53e6e1ca3b6cbb00` / `bdae0a81055c0aa2`，且对 tools 请求**不再回 400**」

今日实测确认：

| 标签 | template 长度 | 含 `.Tools` | 含 `<tool_call>` | capabilities |
|---|---|---|---|---|
| `virtu-comprehensive:latest` | **1434** | ✅ | ✅ | `completion, tools` |
| `virtu-frozen:comp_v5` | 1780 | ✅ | ✅ | `completion, tools, thinking` |
| `qwen3:8b`（原生） | 1723 | ✅ | ✅ | `completion, tools, thinking` |

`Modelfile_v5_comprehensive` / `Modelfile_virtu_disciplined` 里那份含工具分支的模板，**已经 create 到线上了**。原计划的"把它 create 到线上"没有对象可改。

### 1.2 键名问题也已不存在

方案 v2 §2 写"v3 toolcall 70.00，20/30 失败 100% 因 JSON 格式：模型输出 `{"name":...}`，判分器要 `{"tool":...}`"。

今日实测 30 条：

- 顶层键为 `name` 的响应：**0 / 30**
- 顶层键含 `tool` 的响应：**29 / 30**
- `shape`（`required_keys=[tool,arguments]` + `forbidden_keys=[name,function]`）通过：**29 / 30**

键名合规率已是 100%，那条历史失败属**旧标签 + 旧模板**状态，不能用来论证今天还需要修键名。

### 1.3 空 `<think>` 块同样是历史状态

30 条响应的 `content` 中 `<think></think>` 计数：**0 / 30**。

当前 `virtu-comprehensive:latest` 模板在 assistant 起始处**无条件**注入 `<think>\n</think>`（`{{- if and (ne .Role "assistant") $last }}` 分支，无 `IsThinkSet` 条件），这是 prompt 侧的"跳过思考"指令，不是输出侧的空块。它与 11-05 记录的 175/210 不是同一现象 —— 后者是模板把空块写进了被测内容。

> 建议：这两个模板（`bdae0a81` 无 `IsThinkSet`、`53e6e1ca` 有）的差异仍值得单独 A/B，因为它直接决定 `/no_think` 是否生效。本次未做，因为要改 template 层就换了被测对象，会与 §3 的 A/B 混在一起。

### 1.4 用例集已漂移：8/30 道题被替换（本次最重要的发现）

核对全部历史腿 `manifest.json` 里的 `case_file_sha256` 与当前文件哈希，发现**三个用例文件在腿跑完之后被改过**：

| 用例文件 | 腿内记录 | 当前文件 | 受影响腿 | 状态 |
|---|---|---|---|---|
| `toolrouting.jsonl` | `627ca5b0` | `6c4aa5be` | `toolrouting__frozen_comp_v5__v4`（13:29）、`toolrouting__base_qwen3_8b__v4`（13:30） | **已漂移** |
| `derivation.jsonl`（phys） | `b73a1453` / `025b4212` | `13ca297c` | `phys__frozen_comp_v5__v4`、`phys__base_qwen3_8b__v4`、`phys__master_scaffold` | **已漂移** |
| `physics.jsonl`（phys） | `5c96b4d8` / `2a1d5536` | `a319c798` | 同上 | **已漂移** |

`toolrouting.jsonl` 的 mtime 是 **2026-11-05 23:05:12**，而两条腿分别启动于 13:29 / 13:30 —— 腿跑完 9 小时后文件被换。

**具体换了什么**：逐条比对历史腿存档的 `prompt` 与 `criteria` 与当前文件，**8/30 条题面与判据都被替换**：

| 用例 | 存档判据要求 | 当前判据要求 |
|---|---|---|
| `v04` / `v05` / `v06` / `v07` | `cadcam_universal_geometry` | `cadcam_assembly_build` |
| `v11` / `v12` / `v13` / `v14` | `cadcam_cae_stress_analysis` | `cadcam_step_reverse` |

**后果（三条，都影响结论）**：

1. 历史腿 `toolrouting` 的存档分 **78.67 永久不可复现**。用当前用例规则重打分同一批响应得 67.10，但这是"用新题判旧答"，两个数字都无意义 —— 无法再分离"判分器变更"与"用例变更"各自贡献。
2. 本文 §3 的 A/B 是在**新版 30 条**上跑的，两臂内部严格可比（同用例同版本同判分器），但**不能**与 78.67 或全板 `board7` 的 `toolcall 79.76` 相加/相减（后者用的是 `toolcall.jsonl`，另一套题）。
3. `RunIdentity.capture(case_dirs=…)` 本来会把用例 sha 写进 manifest —— **机制在，但没有任何闸去比对**，所以文件被换也不会报警。这正是 §8.2「被测对象按内容寻址」要防的事，而防线只做到"记录"，没做到"否决"。

**好消息**：`board7` 那七个维度（reasoning / knowledge / instruction / generation / generalization / boundary / toolcall）的用例文件哈希与当前**全部一致**，即 `VIRTU_FULL_BOARD §3` 的可复现性未受影响。

**建议（已在本次落地）**：新增 `data/benchmark/CASES.lock`（22 个用例文件的 sha256 + 字节数 + 行数 + mtime）与 `scripts/check_case_lock.py`：

```
python scripts/check_case_lock.py            # 校验，漂移则 exit 1
python scripts/check_case_lock.py --leg runs/eval/<腿>   # 顺带核对某条腿当年跑的是哪份题
python scripts/check_case_lock.py --write    # 明确接受当前文件为新基线
```

反证已验证：给 `toolrouting.jsonl` **只追加一个换行**，闸即报 `DRIFT` 并 `exit 1`；恢复后 `exit 0`。该脚本同时能回答"某条历史腿跑的是不是当前这份题"——对本次那条腿的输出为：

```
toolrouting.jsonl: LEG RAN ON A DIFFERENT CASE FILE (leg 627ca5b0bfb7 / lock 6c4aa5beb5ba)
```

注意它目前是**独立校验脚本，尚未接进 `runner.py`**。接进去会改 harness 源码 sha、使所有现存腿的 `RunIdentity` 失效，需与"重新起腿"一起安排；在接进去之前，起腿前手工跑一次即可。

---

## 2. 已修：判分器 `forbidden_keys` 作用域错误

### 2.1 缺陷

`virtu_eval/graders.py::g_json_object` 把 `forbidden_keys` 与**全递归收集到的所有键**比对：

```python
stack = [obj]
while stack:                      # 递归收集每一层的键
    ...
banned = [k for k in forbid if k in keys]
```

而用例原文写的是「**顶层**键必须是 tool 与 arguments；严禁使用 name/function 键」（`toolrouting.jsonl` 全部 30 条的 `system`）。`arguments.parts[0].name` 是合法的零件名，却被判成协议违规。

实测后果：`toolrouting-m01` 输出 3 个零件、结构完全正确，`shape` 判据却因 `parts[].name` 判红，整条 60.00 分。

### 2.2 修复

`forbidden_keys` 默认只在顶层匹配；保留 `forbidden_keys_scope="recursive"` 以便逐字复现历史判定。`required_keys` **保持全递归**——有 348 条 physics 用例断言嵌套字段（`items[].op`、`bom[].qty`），放宽会静默丢检查。

### 2.3 反证测试（AGENTS.md §8.4）

`tests/test_json_object_grader.py`，**13 passed**，其中 11 条是"植入缺陷必须判红"：

- 顶层 `{"name": ...}` → 必须红 ✅
- 顶层 `{"function": ...}` → 必须红 ✅
- `arguments.parts[].name` → 必须绿 ✅
- `bom[[{"name":...}]]`（二维嵌套）→ 必须绿 ✅
- 缺 `arguments` → 必须红 ✅
- 不可解析文本 → 必须红且 `evidence == "no_json_object_parsed"` ✅
- `scope="recursive"` → 嵌套 name 必须红（旧行为可复现）✅
- 空 criteria 集 → 必须 raise ✅

### 2.4 修复带来的分数变化（零成本重打分，未重跑模型）

| 臂 | 修复前 | 修复后 |
|---|---|---|
| A（无约束） | 78.87（14/30） | **79.53（14/30）** |
| 变动用例 | `m01: 60.00 → 80.00`（`three_parts` 仍红，见 §4.1） |

---

## 3. A/B：参数级约束解码

### 3.1 做法

从**权威工具契约** `virtu_eval/arms.json` 派生 `oneOf` 判别式 schema（10 个分支，对应用例 `system` 里声明的 10 个工具），经 Ollama `format` 下发做约束解码。

**不从用例 `gold` 派生**——那是拿测试集调参，会让 A/B 不可证伪。schema 指纹 `340edeb6369b2a45`。

先验证 Ollama 能力边界：

| 能力 | 结论 |
|---|---|
| `format` 生效 | ✅ 同请求无约束时幻觉出不存在的工具 `cadcam_dxf_plate`；约束后强制在 enum 内 |
| `oneOf` 判别式 | ✅ 支持，10 分支可用 |
| 约束延迟开销 | 冷启动 15.0s，稳态 2.78s vs 无约束 2.92s（GBNF 编译被缓存） |

### 3.2 噪声带（先标定，再看信号）

同一臂（A1）原样重跑一遍（A2），逐例比对：

- 原文**逐字节相同：30 / 30**
- 分数变动：**0 / 30**
- 判据逐条一致：**139 / 139 = 100%**

⇒ 本实验的分数噪声带为 **0.00**。下面的 +0.37 是确定差值，不是采样抖动。

> 例外记录：单条重复 3 次的小样本曾观察到 1/3 次 `"target_fos": "1.5"`（字符串）vs `1.5`（数字）的类型抖动，该差异不影响该条得分。8B 在 6GB 卡上只有 77% 进 GPU，CPU/GPU 混合推理的浮点累加顺序是可解释来源。全量 30 条重测未复现。

### 3.3 结果

| 指标 | A 无约束 | A 重测 | B 约束解码 | Δ(B−A) |
|---|---|---|---|---|
| mean | 79.53 | 79.53 | **79.90** | **+0.37** |
| 全通 | 14/30 | 14/30 | 15/30 | +1 |
| `shape` 通过 | 29/30 | 29/30 | 30/30 | +1 |
| 顶层 `name` 违规 | 0/30 | 0/30 | 0/30 | 0 |
| 空 think | 0/30 | 0/30 | 0/30 | 0 |
| 中位 token | 48 | 48 | 45 | −3 |
| 中位耗时 | 2.92s | 2.93s | 2.78s | −0.14s |

**逐例变动只有 5 条**：

| 用例 | A | B | Δ | 机制 |
|---|---|---|---|---|
| `e03` | 87.50 | 100.00 | **+12.50** | `required=["spec"]` 逼出 spec；`pressure_mpa` 被塞进 spec 内部，**恰好字面命中**判据 |
| `m03` | 88.89 | 100.00 | **+11.11** | `required=["wish"]` 逼出真正缺失的必填参数 |
| `v18` | 60.00 | 70.00 | **+10.00** | JSON 语法错（`"parts": 2"`）被约束消除 |
| `m02` | 100.00 | 87.50 | **−12.50** | `spec:{type:object}` 诱导模型把 `torque_nm` 塞进 spec，顶层丢字段 |
| `v19` | 80.00 | 70.00 | **−10.00** | `parts` required 被 `"parts": []` 空数组满足，随后的 `sheet_width/height/margin/output_dxf` 全丢 |

净 +11.11 分 / 30 条 = **+0.37**。

### 3.4 判定

**不构成改进。** 理由三条：

1. 幅度：+0.37/100，低于任何可宣布门槛；
2. 方向：5 例里 3 增 2 减，机制是"改变了输出分布"，不是"改善了能力"；
3. 机制：两个负例暴露的是约束解码的**结构性副作用**，不是随机波动——
   - `type:"object"` 的无约束参数会被诱导成嵌套容器，把本该在顶层的标量参数吸进去；
   - `required` 数组型参数可被空数组满足，形式合法、内容空洞。

这正好复文本地 E5 已有的结论：**约束只保证语法合法、不保证语义正确**（形状 100% / 数值 33%）。本次在 toolrouting 上再次独立复现。

---

## 4. 新发现的三个用例/契约缺陷（本次未修，需你定夺）

### 4.1 `count_between` 依赖一个不可知的字段名

`cadcam_sheetmetal_nest` 的权威契约（`arms.json`）规定 parts 每项为 `{name, width, height}`，`required=["name","width","height"]`。

但 5 条排料用例的判据是：

```json
{"type": "count_between", "pattern": "w_mm", "min": 3, "max": 3}
```

`w_mm` 既不在工具契约里，也不在用例的 `system`（只写 `cadcam_sheetmetal_nest(parts, 可选 sheet_width/sheet_height/margin/output_dxf)`）或 `prompt` 里。**模型无从得知这个字段名**，只能猜。

- gold 能拿满分（`gold` 用的是 `{"label","w_mm","h_mm"}`）→ 判据自洽
- 模型按契约输出 `{"name","width","height"}` → `w_mm` 计数为 0 → 每条固定丢 2 分
- 模型实际输出 `{"name","size_mm"}` → 同样为 0

⇒ 这 5 条用例的 2 分是**结构性死分**，与模型能力无关。要么把 `pattern` 改成 `(?:w_mm|width)`，要么把 `w_mm` 写进 system。

### 4.2 `arguments_present` 是字面匹配，不是结构校验

```json
{"type": "literal_all", "values": ["arguments", "spec", "pressure_mpa", "target_fos"]}
```

`g_literal_all` 只检查这些字符串是否在响应文本里出现。`e03` 在 B 臂拿满分的真实原因是模型把 `pressure_mpa` 写进了 `spec` 对象内部：

```json
{"tool":"cadcam_cae_stress_analysis","arguments":{"spec":{"inner_radius_mm":50,"outer_radius_mm":80,"pressure_mpa":12},...}}
```

判据认为"参数齐了"，但它并不在 `arguments` 顶层 —— 真实执行器会读不到。**这是判分器可以被字面绕过的实例**，与 §8.4「闸必须能被证伪」相冲突。建议改为按路径断言（`arguments.pressure_mpa`）。

### 4.3 `cadcam_step_reverse` 的 `required` 与用例期望冲突

契约里 `cadcam_step_reverse` 的 `required=[]`，但 `v11`/`v13`/`v14` 都要求 `action` 出现且取值在 `list/analyze` 内。这不是模型问题，是**契约与用例两套标准**。要么在契约里把 `action` 标为必填，要么用例放宽。

（同类：`cadcam_assembly_build` 的 `action` 也是可选，但没被用例要求。）

---

## 5. 本次交付物

| 文件 | 内容 |
|---|---|
| `virtu_eval/graders.py` | `g_json_object` 的 `forbidden_keys` 作用域修复（含 docstring 说明为何 required 仍递归） |
| `tests/test_json_object_grader.py` | 13 条反证测试，11 条为"必须判红" |
| `scratch/_p02_probe.py` | 探针，逐例落原文+逐条判据，支持 `--format-file`，`max_tokens` 逐例取用例自带值 |
| `scratch/_p02_schema.py` | 从 `arms.json` 派生约束 schema（附 sha256） |
| `scratch/_p02_rescore.py` | 零成本重打分（raw 落盘 → 换尺重判，不重跑模型） |
| `scratch/_p02_report.py` | 出 `run_id` + provenance 表 + 噪声带 + 台账 JSON |
| `scratch/_p02_probe_*.jsonl` | A1 / A2 / B1 三份逐例证据 |
| `scratch/_p02_ab_report.json` | 台账（含 `verdict` 字段写明"非改进"） |
| `scratch/_p02_routing_schema.json` | 派生的 10 分支 schema |
| `data/benchmark/CASES.lock` | 22 个用例文件的 sha256/字节/行数/mtime 基线 |
| `scripts/check_case_lock.py` | 用例漂移闸（反证已验证：加一个换行即 `exit 1`），支持 `--leg` 回溯某条历史腿跑的是哪份题 |

**顺带修掉的一个方法学错误（已记录，避免复犯）**：`runs/eval/*/raw.jsonl` 里的 `criteria` 字段是**已判分的记录**（`passed`/`evidence`），不是判据规则（`values`/`patterns`）。用它直接喂 `score_case` 会让每个 grader 抛 KeyError，而 `score_case` 的兜底 `except Exception: ok=False` 把"输入错误"静默记成"模型答错"——我第一次重打分因此得到 78.67→23.27 的假结果。重打分必须按 `case_id` 从用例文件取规则。

---

## 6. 建议的下一步（按性价比）

1. **停止在 P0-2 上加投入**。键名、空 think、模板一致性三条都已无可归因增益；约束解码的净收益 +0.37 且机制有害。保留 `--format-file` 作为可选工具即可，不设为默认。
2. **先锁用例，再改口径**：建 `data/benchmark/CASES.lock`（文件名 → sha256），起腿前比对，不一致拒绝启动；改题必须换文件名或加版本目录，禁止原地覆盖。之后再修 §4.1（`pattern` 加 `width`）与 §4.2（`arguments_present` 改路径断言）并重跑。**当前 toolrouting 的 79.53 不是一个干净的分数**：它含 5 条结构性死分（10 分/30 条 = 3.3 分）、1 条可被字面绕过的判据，而且它测的是 11-05 23:05 之后才存在的新题。
3. **转向 P2-1（v4 补训）**：本次实测再次证明工具路由的失分主体是**判断错误**（6 条拒答式 `cadcam_preflight`、2 条选错工具），不是格式。这类错误 prompt 与 schema 都修不了，只能改权重或补契约知识。
4. **P1-1 可以立刻做且零 GPU**：把 §4.3 这类"契约与用例不一致"的地方，连同 18 个工具的参数语义，做成最小证据子图注入。日志原话「它缺的是接口知识，不是方法推理能力」在本次 6 条拒答里再次得到印证。

---

## 7. 明确不建议

- 把 `format` 设为所有臂的默认值（负例机制明确，且会改变 `RunIdentity` 语义）
- 从 `gold` 反推 schema 或判据来"提分"（违反 §8.1/§8.5）
- 用本文的 79.53 / 79.90 与全板基线 62.35 / v3 存档 80.03 相减（三份不同 template、不同 grader 版本）
- 在 `benchmarks/` 或 `README.md` 里写"约束解码提升 toolrouting 0.37 分"
