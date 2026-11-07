# Virtu 无效思考治理与能力强化台账（2026-11-05）

## 0. 一句话结论

「无效思考」在这台机器上的真实形态被量出来了两条：模板强塞的**空 `<think>` 块**
（10:23 腿 180/210 条，破坏「恰好 N 行」类判据）和贪心解码的**退化复读**
（704 token 重复同一句、512 token 重复一个词）。对应交付了一个纯后处理卫生层 +
严格格式编译 + 同权重新模型臂 + 活体 A/B 脚本。

**证据强度（已按测量宪法更正，见 §3）**：

- 在**唯一可归因**的腿（frozen_comp_v5，210/210、每行带层哈希）上，该腿没有吐空 think
  块，卫生层 Δ=**0.00**、0 例回退——干净答案原样通过，这是它该有的行为。
- **反证探针**（§3.2）：把缺陷植入这条干净腿 → 掉 2.76 分、坏 19 例；过卫生层 →
  **19/19 全部还原，残差 0.00，0 例误修**。所以它是保险，不是空转闸。
- 在确实带缺陷的 10:23 腿上，回放回收 **+3.17 加权**（63.70→66.87，22 升 0 降，
  字符 -19.9%）；该腿行内无身份，按 §8 记作**外推**，不写成某个 tag 的成绩。
- 同一批冻结文本上，桥后端的确定性核算在可归因腿值 **+3.11**，但其中含 1 例
  **把答对的批量工具调用折叠成一项**的真缺陷（§3.4，已登记 3 条 strict xfail，未改）。
- 权重级：本机 6GB 训不动 8B，云端按你「零租卡」约束默认不开；仓内正路是 RSI，
  今日两次预算太小（验证 n=4），只算管道打通。活体 A/B 已排队等静默窗口。

---

## 1. 证据：无效思考到底浪费在哪

数据源：`runs/eval/fullboard_20261105_0930/board7__comprehensive/raw.jsonl`
（210 例，`virtu-comprehensive:latest`，temperature 0，seed 1234，num_ctx 8192）。

| 现象 | 实测 | 后果 |
|---|---|---|
| 空 `<think>` 块 | 180/210 条响应含 think 标签，其中 175 条块内为空（5 条有内容） | 模板给这些答案加了至少 2 个非空行，直接打破「恰好 N 行」「单行」判据 |
| 退化复读 | 至少 7 例可见：`generalization-h05` 704 token 重复同一句；`boundary-e05` 512 token 重复「进给」；`instruction-h04` 同一 6 值列表反复到 799 字符；`reasoning-h06` 答案重复；`generation-h03` G 代码段循环；`generalization-e07` 整段答案重复；`generation-m02` `G1 X-30 Y-20` 连续重复 | 白烧 token、拉高延迟、截断丢答案；卫生层安全剪掉其中 5 例（`boundary-e05`/`generalization-e07`/`generalization-h05`/`generation-m02`/`reasoning-h06`），`instruction-h04` 与 `generation-h03` 的变值循环保留为内容错误 |
| 思考回退 | 21 例正文为空、答案落在 thinking（多为 toolcall） | 不是内容浪费，是模板路由问题；本轮按「答案回退」保留 |
| 工具外壳污染 | 7 条非 toolcall 响应仍输出 `{"tool":...}` 外壳 | instruction/boundary 少量失分 |
| 数值硬错 | `numeric_near` 失败 62/100 条，其中 51 条相对误差 >1% | 最大内容缺口；不是格式能修的，需计算器/训练 |

基线逐维（加权 63.70）：

| 维 | 分数 |
|---|---:|
| toolcall | 75.56 |
| generation | 75.82 |
| boundary | 72.50 |
| knowledge | 61.67 |
| reasoning | 54.74 |
| instruction | 54.88 |
| generalization | 46.94 |

---

## 2. 已落地

### 2.1 运行时卫生层（纯函数，可逐条回滚）

- `virtu_omni/serving/output_hygiene.py`
  - `strip_think()`：去空 think 块；正文为空时回退到 thinking 正文。
  - `collapse_repeated_lines()`：连续相同行 ≥4 次才折叠（保留第一行）。
  - `collapse_token_runs()`：行尾同词连续 ≥8 次才折叠（如「进给进给…」）。
  - `collapse_periodic_tail()`：≥3 个连续相同行块才折叠。
  - `collapse_exact_halves()`：整段答案逐字重复两次才折叠。
  - 不合并行、不重排、不改写内容；代码/G 代码中的两行重复不会被误伤。
- `virtu_omni/serving/output_compiler.py`
  - 仅在用户明确要求时：竖线表转 CSV、普通 JSON 题解包 `arguments`、
    去掉「工件号是：」这类短标签、把一行 N 项拆成 N 行。
  - 工具调用请求永不拆 `tool/arguments`；结构化 JSON 不做文本重写。
- `virtu_omni/serving/answer_pipeline.py`
  - `clean_served_answer(prompt, text)`：卫生 → 编译，返回字符数/去 think/剪环/编译标记，供线上遥测。
- 测试：`tests/test_output_hygiene.py`、`tests/test_output_compiler.py` 共 **24 项**，
  加上 `tests/test_disciplined_ab_provenance.py` 的封缄/行身份/传输失败/静默闸 **7 项**，
  合计 **31 passed + 3 xfailed（后端已登记缺陷）**。
  反证覆盖：正常答案恒等（防误杀）、两行合法重复保留（防过度折叠）、
  结构化 JSON 不改写（防拆 JSON）、工具调用不拆包（防误路由）、
  静默闸既不能漏判真评测器、也不能被自家探针卡死。

### 2.2 同权重模型臂 `virtu-disciplined:v1`

- 构建文件：`Modelfile_virtu_disciplined`（模板已烘进文件，不再依赖会被共享清理的
  `scratch/` 构建脚本；用 `ollama create virtu-disciplined:v1 -f Modelfile_virtu_disciplined` 可复现）。
- 与基线**同一模型层**：`sha256 c3b78c7735c9…`（4,614,297,600 B）。
- 当前 tag 身份（内容寻址，禁止按名字引用）：
  - model `c3b78c7735c9…`（4,614,297,600 B）
  - template `18bb59385e39…`（1,371 B）
  - system `12772e17c478…`（2,835 B）
  - parameters `938ff0aa1dad…`（146 B）
  - manifest `41a8801aa448…`
- 差异只在服务层：
  - 模板：删掉空 `<think>` 注入块（其余工具分支/消息分支保持原样）。
  - 系统提示：安全底线 + 输出纪律 + **工具路由表** + 工业事实卡
    （位置度/轮廓度、MMC、ISO 2768-mK、IT 等级、DWG/DXF、材料切削难易、
    VERICUT 厂商、OEE、GB/T 15706、NX Journaling、常用切削公式）。
  - 参数：`repeat_penalty 1.15`、`repeat_last_n 512`，其余 num_ctx/stop/temperature 不变。
- 静态核对：`ollama show` 确认模板已无空 think 块，参数已生效，模型层 digest 与基线一致。
- **基线 tag 在本会话中被其他会话重建过**：10:23 冻结 raw 对应的是
  template `53e6e1ca3b6c` / system `9f4faa44ed3d`；之后 `virtu-comprehensive:latest`
  变成 template `bdae0` / system `6f296`，当前模板又是 1,434 B。**禁止按 tag 名复算**；
  新臂 A/B 每行带 `served_layers`，只认内容哈希。
- **未做活体生成验证**：主机上另有评测链在跑（`run_chain3/4.py`、`virtu_eval/runner.py`），
  按仓内独占约定不抢 GPU。活体 A/B 命令见 §4。

### 2.3 可复现 A/B 脚本

`scripts/eval_disciplined_ab.py`：

- 起跑前检查：无其他 `runner.py` / `run_chain*` / `eval_disciplined_ab` 进程，
  且 `ollama ps` 无已加载模型，连续静默 120 s 才继续；带独占锁。
- 生成新臂原始回答，分别用**同一套判分器与用例**打 raw 与 cleaned 两列；
  与冻结基线 raw.jsonl 按 case_id 配对。
- 测量宪法接入：`RunIdentity.capture()` 记录模型/模板/系统层、用例 sha、判分器 sha；
  跑完 `drift()` 非空即 `publishable=false`；`seal_leg()` + `verify_seal()` 封缄
  raw.jsonl；`metrics_from_raw(..., require_row_identity=True)` 拒绝没有 per-row
  `served_layers` 的分数。
- 输出 `run_identity.json`、`manifest.json`、`raw.jsonl`、`summary.json`、
  `summary.md`；只有 `publishable=true` 才允许把 clean 列当实测。
- 示例：

```bash
.venv/Scripts/python.exe scripts/eval_disciplined_ab.py \
  --model virtu-disciplined:v1 \
  --baseline runs/eval/fullboard_20261105_0930/board7__comprehensive/raw.jsonl \
  --dims instruction,generalization,reasoning,boundary,knowledge,generation,toolcall \
  --out runs/eval/disciplined_20261105
```

---

## 3. 实测（三条腿，同尺复评，全部非新生成）

**先更正**：本报告初稿把 +3.17 写成普适增益，并把 `board7__frozen_comp_v5__v4` 判为
「不可用对照」。该腿后来 **210/210 跑完、0 传输错误、每行带 `served_layers`**，
是目前**唯一可归因**的腿；而 10:23 那条腿没有行内身份，才是要降级的。重测后结论如下。

### 3.1 可归因腿（frozen_comp_v5，model `c3b78c7735c9` / template `53e6e1ca3b6c` / system `9f4faa44ed3d`）

`scripts/stack_attribution_offline.py`，`run_id=f68f0e40934e2e04`，n=210：

| 栈 | 加权 | Δ vs raw | 逐例 |
|---|---:|---:|---|
| raw | 68.44 | — | — |
| hygiene（我的卫生+编译） | **68.44** | **0.00** | 0 升 / 0 降 |
| backend（桥后端确定性核算+工具编译） | 71.55 | +3.11 | 11 升 / **1 降** |
| both | 71.55 | +3.11 | 11 升 / 1 降 |

这条腿**没有吐空 think 块**（`think_removed=0`），所以卫生层正确地不动任何分数——
这正是它该有的行为：干净答案必须原样通过。

### 3.2 反证探针（证明卫生层不是空转闸）

`scripts/hygiene_insurance_probe.py`，`run_id=cf7f514e9c52cdfb`：把 10:23 腿观察到的
缺陷（每条答案前面一段空 `<think>\n\n</think>`）**植入**这条干净腿，再让卫生层修。

| 阶段 | 加权 | 说明 |
|---|---:|---|
| 干净腿 | 68.44 | 基线 |
| 植入缺陷 | 65.68 | **-2.76，19 例被打坏** |
| 植入后经卫生层 | **68.44** | **+2.76，19/19 全部还原，残差 0.00，0 例误修** |

探针判定 GREEN。所以：卫生层的价值是**保险**——缺陷出现时它全额回收（10:23 腿上
实测回收 +3.17），缺陷不出现时它不动分数（3.1 节 Δ=0.00）。

### 3.3 不可归因腿（10:23，`board7__comprehensive`，行内无 `served_layers`）

`run_id=73d9ef4b75dbb5c7`，n=210：raw 63.70 → clean 66.87（配对 Δ +3.17，22 升 0 降，
字符 -19.9%，去空 think 180 例、剪环 5 例、编译 7 例）。
按 AGENTS.md §8 只能记作**外推**：它的 tag 在会话中被其他会话重建过
（template 1780 B→1434 B、system 710 B→879 B），不能写成「`virtu-comprehensive` 的成绩」。

| 维度 | raw | clean | 配对 Δ |
|---|---:|---:|---:|
| instruction | 54.88 | 73.91 | +19.03 |
| generalization | 46.94 | 50.08 | +3.14 |
| reasoning | 54.74 | 55.11 | +0.37 |
| boundary / generation / knowledge / toolcall | 72.50 / 75.82 / 61.67 / 75.56 | 同值 | 0 |
| **加权** | **63.70** | **66.87** | **+3.17** |

两条腿的 raw 相差 4.74 分（63.70 vs 68.44）而 model 层 digest 相同——这本身就是
共享 tag 被改写的直接后果，任何按 tag 名复算的做法都不可信。

**卫生层不能做的事**（两腿一致）：`instruction-e03` 的 20→40 只是格式判据通过，
模型答「否」而正确是「是」，事实错误不被掩盖；`generation`/`knowledge` 的内容错、
`numeric_near` 的 62/100 失败都不是卫生层能碰的。

---

## 3.4 后端确定性核算的一处真缺陷（已登记，本轮未改）

`backend` 列的 +3.11 里有 1 例**变坏**：`toolcall-h04` 模型本来输出了正确的**两项数组**，
后端把它折叠成一项，丢掉 `runs/b.nc`，100 → 33.33。最小复现与根因：

- `_looks_like_tool_json()` 只认单个对象，数组被判成「模型没调工具」；
- 于是走 `_compile_toolcall_from_prompt()`，**无条件覆写**模型已正确的答案，
  还把 `nc_file_path` 改成它自己 schema 里的 `nc_path`（单对象情形同样被改写）。

修法（属于 `virtu_real_backend._verify_arithmetic_response`）：可解析的对象**或对象数组**
都算已作答；只有答案里完全没有调用时才编译；绝不重命名模型写对的字段。
本轮不改——桥正在服务另一会话的 `_eval_disciplined_text` 腿（12:03 起），§8.6 禁止
在链运行时动测量路径。已登记为 `tests/test_backend_toolcall_batch_defect.py`
三条 `xfail(strict=True)`（现在 3 xfailed；一旦修好会立刻变红，提醒删除标记）。

---

## 4. 全面 / 极限的可行性矩阵

| 档 | 内容 | 状态 | 证据或阻塞 |
|---|---|---|---|
| A | 去空 think、剪退化环、格式编译、同权重新臂 | **已交付**：可归因腿 Δ=0.00 且 0 回退；反证探针 19/19 还原（残差 0.00）；带缺陷的 10:23 腿回收 +3.17 | `run_id=f68f0e40934e2e04`（可归因）、`cf7f514e9c52cdfb`（探针）、`73d9ef4b75dbb5c7`（外推腿） |
| B | 新臂活体 A/B（提示词事实卡/工具路由/repeat penalty） | **已排队**（42 例冒烟，等静默窗口） | 主机同时有 chain2/chain4、`base_qwen3_8b` 腿与另一会话的 `bridge_deployed` 腿；闸见 §2.3 |
| C | 权重级：RSI 合成候选 → 验证 → 人工 approval | **管道已通，统计量不足** | 今日两次 RSI 预算 limit 6/10、验证 n=4，一次 blocked 一次 rejected；不能读成无效。见 §6 |
| D | 8B QLoRA 真训练 | **默认不开** | 本机 6GB 训不了 8B（7B 已证伪）；按你的零租卡约束需明确点头 |
| E | 算术硬能力（numeric_near 62/100 失败） | **部分缓解** | 提示词要精确 π/复核；桥后端已有 `[确定性核算]` 重算追加，直连臂不含它 |
| F | 知识硬错（ISO/GB、GD&T、刀具厂商等） | **部分缓解** | 事实卡覆盖本轮审计出的硬错；活体是否吸收待 B 档验证 |
| G | 后端工具编译会覆写正确答案（§3.4） | **已登记未改** | 3 条 `xfail(strict=True)`；桥在服务他人腿，§8.6 禁止运行中动测量路径 |

**红线**：
1. 不用 240 条评测题做训练语料；需要合成同分布的新数字/新场景。
2. 不把「格式通过」写成「能力提升」；raw 与 clean 分栏。
3. 不把不同 tag / 不同用例数 / 不同判分器的分数相加；行内无 `served_layers` 的腿只算证据，不算成绩。
4. 未跑活体 A/B 前，不宣称新臂的分数；§3 只证明运行时卫生层与其反证探针。

---

## 5. 与仓内既有机制的关系（已核对，避免重复实现与口径混淆）

- `virtu_real_backend.py::_should_enable_thinking`：自适应思考路由——计算类/带「推导、校核」等
  提示词的请求开思考，带 tools 的请求关思考。这是「减少无效思考」的请求级实现，
  作用在 **桥后端栈**；我的板测腿（`OllamaNativeArm` 直连 Ollama）不经过它。
- `virtu_real_backend.py::_apply_numeric_corrections`：把 rpm/Vf/MRR/走刀时间/弦长/圆弧
  等解析后**确定性重算**，缺失时追加 `[确定性核算] …（以此为准）`，短答案则整行替换。
  这是桥栈在数值题上可能高于直连臂的真实原因。
  **我的 A/B 刻意不调用它**：否则 §3 的 +3.17 就分不清是卫生层还是求解器给的。
- 另一会话此刻在跑 `bridge_deployed` 的 `_eval_disciplined_text{,_v2}` 腿
  （读其 raw 时分别 20/12 行，未完成，不计入任何结论）。
- `virtu_omni/rsi`（提交 `2671c86`）才是权重级的仓内正路：开发集诊断 → 求解器可验的
  合成 SFT 候选 → 独立验证集配对判增益 → 人工 approval，且 `weights_updated` 恒 false。
  今日两次实跑预算很小（`limit` 6/10、`min_validation` 2/4）：一次 `blocked`
  （运行被打断，gate 明确拒绝审批），一次 `rejected`（验证 n=4，mean_gain −10.0，
  paired_regressions 1）。**这两次只能证明管道接通，不能读成「RSI 无效」**——
  验证样本 4 条时任何 5.0 分的门槛都在噪声里。
- 我的卫生层是纯后处理，不与上述任何机制冲突；可叠加，但叠加后必须分栏报告。

### 5.1 四栈离线归因（10:23 外推腿、同一把尺，不吃 GPU）

`scripts/stack_attribution_offline.py`，`run_id=bce780998e14cd50`，n=210
（该腿行内无 `served_layers`，故为外推；可归因腿的四栈表在 §3.1）：

| 栈 | 加权分 | 相对 raw | 逐例 |
|---|---:|---:|---|
| raw（模型原样） | 63.70 | — | — |
| hygiene（我的卫生+编译） | 66.87 | **+3.17** | 22 升 / 0 降 |
| backend（桥后端确定性核算+守卫+工具编译） | 67.99 | **+4.29** | 13 升 / 0 降 |
| both（先卫生后后端） | **71.16** | **+7.46** | 35 升 / 0 降 |

两栈正交可加：卫生层收格式/思考损耗（instruction +19.0，这腿真带了空 think 块），
后端收数值/工具（knowledge +5.8、toolcall +6.7）。四列都是**同一批冻结文本的后处理
回放**，不是模型重生成；模型自身的分数只有 raw 那列。

> 后端缺陷与最小复现见 §3.4（同一缺陷在这条腿上只升不降，在可归因腿上暴露出 1 例回退）。

### 5.2 同一编译路径的另一面：替模型编造内容（假绿风险）

`toolcall-h04` 这条 10:23 外推腿上模型输出为空，后端把整个调用写了出来；
另两例它补出了**题面没有的字段**，判分器照给满分：

| 例 | 模型输出 | 后端输出 | 判分 |
|---|---|---|---|
| `toolcall-h04` | 空 | `{"tool":"cadcam_cimco_validate","arguments":{"action":"validate_macro","nc_path":"runs/a.nc"}}` | 0 → 33.3 |
| `toolcall-m06` | `{"name":"cadcam_preflight","arguments":{}}` | `{"tool":"cadcam_solidworks_model","arguments":{"action":"execute_vba","part_name":"flange","vba_code":"Sub main()\nEnd Sub"}}` | 0 → 100 |
| `toolcall-m13` | 工具名写成 `name` 且路径被改写 | 修正为 `tool` 与 `nc_path` | 33.3 → 100 |

后两例里 `vba_code` 是**题面没有的内容**，被系统补出来后判分器给了满分——这正是
测量宪法要防的假绿。所以 toolcall 的 +6.7 **不是模型能力**，是系统兜底。
建议（未实施）：编译只允许搬运题面可确定的字段；必需参数缺失时 fail-closed
返回原输出或「缺参数」错误，绝不合成内容；并配「植入空输出 ⇒ 必须红」的反证测试。
本轮不改，因为桥正在服务另一会话的 `_eval_disciplined_text` 腿（12:03 起），
§8.6 禁止在链运行时动测量路径。

## 6. 权重级下一步（按你既有约束：本机不训练 8B，零租卡）

要把 numeric/knowledge 的内容缺口压下去，仓内正路是 RSI，而不是继续堆提示词：

1. 先给 RSI **够统计量**的预算（今日两次是管道冒烟，验证只有 4 条，任何 5.0 分门槛
   都在噪声里）。建议量级：`--limit 60 --min-validation 24 --rounds 2
   --max-calls 160 --max-seconds 3600`，跑在 `virtu-disciplined:v1` 的静默窗口之后。
2. RSI 产出的 `data/sft_candidate.jsonl` 是**求解器可验、非评测题**的合成语料；
   落地前仍要过 `virtu_eval/contamination_check.py`，对 240 例评测集 `hard_leaks=0`。
3. 只有拿到 `gate.eligible=true` + 人工 approval 的候选，才谈得上云端 8B QLoRA
   （此前实测锚点：V100-32GB 1814 padded tok/s、¥1.98/h、264 步约 1.9 h/¥3.7）。
   按你「零租卡」的既有约束，这一步默认**不开**，要开需要你点头。
4. 训练后仍用同一 210 例盲测，raw / cleaned / 后端确定性核算三栏分报，不合并成一个分。

---

## 7. 交付物清单

- `virtu_omni/serving/output_hygiene.py`
- `virtu_omni/serving/output_compiler.py`
- `virtu_omni/serving/answer_pipeline.py`
- `tests/test_output_hygiene.py`
- `tests/test_output_compiler.py`
- `tests/test_disciplined_ab_provenance.py`（封缄/行身份/传输失败闸的反证测试）
- `Modelfile_virtu_disciplined`
- Ollama tag `virtu-disciplined:v1`（model `c3b78c7735c9…` / template `18bb59385e39…`
  / system `12772e17c478…` / parameters `938ff0aa1dad…` / manifest `41a8801aa448…`）
- `scripts/eval_disciplined_ab.py`
- `scripts/stack_attribution_offline.py`（四栈离线归因，可换任意腿）
- `scripts/hygiene_insurance_probe.py`（植入缺陷 ⇒ 必须回收的反证探针）
- `tests/test_backend_toolcall_batch_defect.py`（后端覆写正确工具答案，3 条 strict xfail）
- `runs/eval/discipline_replay_20261105/`（run_id `73d9ef4b75dbb5c7`，外推腿）
- `runs/eval/stack_attribution_20261105/`（run_id `bce780998e14cd50`）
- `runs/eval/stack_attribution_frozen_leg/`（run_id `f68f0e40934e2e04`，可归因腿）
- `runs/eval/hygiene_insurance_20261105/`（run_id `cf7f514e9c52cdfb`，探针）
- 本台账
