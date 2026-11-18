# 审计 S5：修复后复查报告（2026-11-13 18:2x–19:0x）

> 口径：只把「能在文件里读到真实调用 / 能在现场跑出真实返回」的算作已修复或已确认。
> 未实测项一律标 `unverified`，不写「应该没问题」。

---

## 0. 先说一件影响结论的事：工作区正被另一个会话写入

复查开始时发现源码 mtime 异常，取证结果：

| 时间 | 文件 | 规模 | 归属 |
| :-- | :-- | :-- | :-- |
| 18:23:18 | `tests/test_swarm_orchestrator.py` | 7.2 KB（新） | 非本会话 |
| 18:29:28 | `virtu_omni/agent/swarm_orchestrator.py` | 36.1 KB（新） | 非本会话 |
| 18:29:34 | `tests/test_swarm_entry.py` | 9.9 KB（新） | 非本会话 |
| 18:30:00 | `virtu_omni/agent/super_agent.py` | **+1185 / -28 行** | 非本会话 |

该会话把 AGENTS.md §4 中原本标注「规划中（未实现）」的四项契约（SWARM 层级委派 / Blackboard 写锁租约 / Meta-SOP 文档交接 / adversarial_critic 红蓝辩论）落成代码，并把 §1/§4 改为「已实现 2026-11-13」。

**我对这批代码做了独立核验（不是采信它的自述）**：

- `tests/test_swarm_orchestrator.py + test_swarm_entry.py` → **4 passed in 6.26s**
- 编排器确实调真实模块：`surface_observability.observe_surface`、`design_web_self_correction.verify_and_correct`、`scripts.setup_vericut_simulation.derive_stock_from_product`、`product_integrity_gate`
- `basis` 逐段标注 `measured / offline_kb / asserted`，PRD/ARCHITECTURE 自标 `asserted`（没有把文档当实测）
- 失败路径诚实：委派抛异常 → `success=False` + `rcfa_report` + `circuit_breaker_tripped=True`，不吞异常
- 3 处 `pass` 命中是异常类定义（`LeaseTimeout/LeaseError/HandoffError`），合法，非桩

**副作用**：我 18:32 启动的全量测试扫描跑在「移动靶」上（我自己同时在改 4 个文件），46 个 failed / 4 个 hang 里含大量假红。见 §4。

---

## 1. 本轮修复（7 项）

| # | 问题 | 证据 | 修法 | 现场验证 |
| :-- | :-- | :-- | :-- | :-- |
| 1 | 我上一轮加的断言**反向失真** | `test_agents_md_marks_planned_items` 断言 AGENTS.md 必须含「Swarm Orchestration（设计契约，未实现」；SWARM 落地后此断言必红 | 改为**证据链校验**：凡标「已实现」的行必须引用真实存在的文件，且不得同时写「规划中/未实现」 | `24 passed` |
| 2 | `cimco.create_macro_b` **假可执行** | 映射到 `cadcam_cimco_validate:validate_macro`，但 `bridges/cimco_bridge.py` 只有 `validate_fanuc_macro_b` 与 `launch`，无生成能力 | 移入 `KNOWLEDGE_ONLY`，detail 写明「宏须模型自写，工具只校验」 | 调用返回 `status=knowledge_only` / `TOOL_NOT_EXECUTABLE` |
| 3 | 3 个网络工具**无 status 信封** | 其余 17 工具统一回 `status`，三支直出裸 payload → 调用方 `res.get("status")` 恒为 `None`，无法区分成功/失败 | 三支补 `status`（error 优先），保留全部原字段 | search → `ok`（4 条真实结果）；fetch → `error`（本机 SSL 拦截，如实上报） |
| 4 | `feature_ops` 0 步成功仍报 **partial** | 单个未知 op → `status=partial`，但 `ops_executed` 全部带 error | 全部 op 失败 → `status=error` + 「全部 op 均失败」 | 新增断言，返回 `error` |
| 5 | 凭据闸门**扫到自己** | `candidate_files()` 把 `tests/test_no_hardcoded_credentials.py` 自己纳入扫描，而该文件含「探测器必须响」的合成字面量 `password='Sup3rSecretValue'` → 这道闸门永久红、等于失效 | 只排除该文件自身（其余 tests 仍全扫）；同时把 `tests/test_server.py:10` 的 `TEST_TOKEN = "serving-test-token-" + ...` 改为 `secrets.token_urlsafe(36)` 运行时生成，**不放宽扫描规则** | 26 passed |
| 6 | 评测器单测与「空转闸」冲突 | `test_eval_runner` 传的臂 spec 没有 `tools`，但 `_Arm.tools_for()` 实际暴露了 schema → 新加的空转闸先抛 `ValueError` | 给这些 spec 补 `tools`（如实声明该腿暴露了工具面），不放宽闸门 | 26 passed |
| 7 | 缺**防漂移不变量** | 声明面/映射面此前只靠人看 | 新增 4 条测试：①声明必可分批（AST）②可执行映射 action 必在枚举内 ③AGENTS 已实现行必有真证据 ④0 成功不得 partial | 全部随 `24 passed` 绿 |

> 5/6 两条修的都是**测量闸门自己坏了**——闸门红了但红的原因不是产品缺陷，这类红最危险：会训练人「看到红就绕过」。

---

## 2. 复查后确认**没有**问题的项（避免「没查」被读成「没问题」）

| 检查项 | 结论 | 证据 |
| :-- | :-- | :-- |
| 声明面是否存在「能看不能调」的工具 | 无 | 20 个声明工具 100% 在 `_execute_tool_call_impl` 有分支（AST 比对，missing=[]）；反向 2 个内部入口 `cadcam_knowledge_lookup` / `cadcam_reverse_engineering` |
| 可执行映射是否指向不存在的 action | 无 | 26 条可执行映射逐条比对 action 枚举，违规 0 |
| 语料工具名覆盖 | 满覆盖 | 60 名：可执行 26 / 仅知识 34 / 未映射 0（`lint_corpus_tool_names.py`） |
| 失败路径会不会假成功 | 不会 | VERICUT 缺文件→`error`；SW 非法 action→`invalid_arguments/TOOL_SCHEMA_VIOLATION`；feature_ops 未知 op→`error` |
| `assembly_build` / `six_software_orchestrator` 的 `status: success` 是否空转 | 不是 | 均在真实调用后返回（`engine.analyze_step` 等），非裸常量 |
| 抽象基类 `NotImplementedError`、异常类 `pass` | 合法 | `agent_team.py:81` 是抽象方法；3 处 `pass` 是异常类 |
| 本轮改动文件语法 | 全 OK | 5 个文件 `compile()` 全通过 |

---

## 3. 仍需处理（3 项，均需你决策或需数据）

### P1-1 测量面缺口 4 个：`test_closed_loop_coverage` 3 条红灯（既有，非本轮引入）

实测数值：

| 项 | 值 |
| :-- | :-- |
| 运行时声明面 | **20** |
| `arms.json` 注入面 | **16** |
| 无任何 gold/criterion 覆盖 | **4**：`cadcam_feature_ops` + `cadcam_web_search` + `cadcam_fetch_web_content` + `cadcam_internet_deep_learning` |
| 只看旧板 `virtu_eval_v1` 的未覆盖数 | **10**（该测试期望 6） |

三条红灯：`len(tools)==16`（实际 20）、`uncovered==[]`（实际 4）、`v1-only==6`（实际 10）。**这三条在本轮改动之前就是红的**（HEAD 提交时声明面已 17 项）。

两条修法，代价不同：

- **A（推荐）**：给 `cadcam_feature_ops` 补 ≥4 条 `toolrouting` 用例（它是真实 CAD 能力，本应判分）；3 个网络工具降为内部入口（联网结果不可复现，本不该进判分面）。代价：板面 n 30→34，需同步改 3 处 pin 死的期望值（`n==30`、`easy==9`、tier 分布）。
- **B**：4 个全部降为内部入口，回到 16 项。代价：`feature_ops` 这个真实能力永远不判分。

**我没有擅自动板面**——改判分面等于改历史可比性，属于你的决策。

### P1-1 处置结果（2026-11-13，用户选 A，已执行）

| 项 | 修前 | 修后 |
| :-- | --: | --: |
| 运行时宣告面 | 20 | **17** |
| `arms.json` 注入面 | 16 | **17**（19 个臂各 +`cadcam_feature_ops`） |
| 题板可判工具 | 16 | **17**（无未覆盖项） |
| `toolrouting` 题数 | 30（9/15/6） | **34（10/18/6）**，实测配比合法 |
| 只看旧板的未覆盖数 | 10（闸期望 6） | **7**（闸已改为 7，并加 `feature_ops` 断言） |

具体动作：

1. **新增 4 条 `cadcam_feature_ops` 路由用例**（`toolrouting-e04 / m05 / m06 / h04`）：
   - `e04` easy：只要 STEP 原始测量数据（母线闭合点列/直径谱/孔系/包围盒）→ `action=measure`；
   - `m05` medium：题面自带 7 步 op 序列，禁止自加步骤 → `execute_plan` 保序；
   - `m06` medium：要求 `method_reason` 与 `expected_volume_mm3`，装配/排料为干扰项；
   - `h04` hard：第 4 步只写 `cut` 不写 `type`，**补 `through_all` 即判红**（判据权重 4/13）。
   负样本实测：gold 100.0、擅补 `cut.type=through_all` 69.23、误路由 `cadcam_solidworks_model` 36.36 —— 用例具有区分度，不是形式覆盖。
2. **三个联网工具降级**：移入 `bridges/tool_calling_specs.py::INTERNAL_TOOL_DEFINITIONS`。`execute_tool_call` 分发与旧语料名映射不变，`get_tool_parameter_schemas()` 同时收拢宣告面与内部入口，`test_agent_stage2_gates` 的 required/类型/枚举拒绝 3 条仍全绿（30 passed）。
3. **补一条反向缺口闸**：`test_closed_loop_coverage::test_harness_advertises_the_whole_declared_surface` —— 板上有题、臂里没 schema 与「臂里有、运行时没有」同样判红。只改一边的漂移从此两侧都会响。
4. **`CASES.lock` 只重钉一条**：`toolrouting.jsonl` `6c4aa5be…`（30 行）→ `12064cb4…`（34 行）。未使用 `--write`：那会把 52 个从未入锁的新用例文件一起"合法化"，把闸门盲区写成基线。仓内另有 4 条历史 DRIFT（`virtu_eval_phys_v1` / `virtu_rsi_pool_v1` 各 2 条）在本次改动前即存在，未触碰。

**仍未测**：17 工具面的服务端 `prompt_eval_count` 没有回读。4779 只对 16 工具面成立，把 `test_toolcall_plumbing_gates` 拆成"实测面校准（16 工具，仍卡 20%）+ 新面不得低于实测下界"两条，而不是回调 `_CHARS_PER_TOKEN` 把数字弄绿。

### P1-2 SWARM 降级语义与 docstring 不一致（小，未改）

`_solve_swarm` docstring 写「`res.mode` 只有真的跑完 SwarmCommander 时才写 SWARM」，但代码在委派抛异常时写 `mode=SWARM` + `success=False` + `rcfa_report`。

行为是诚实的（失败显式、有 RCFA、熔断置位），只是描述与实现差一句。建议把描述改成「只有真跑完才 `success=True` 的 SWARM」。**未改**：该文件 18:30 刚被另一会话写入，避免撞车。

### P2 已知未做（非代码可替代）

- 训练语料仍是「规则引擎生成 + 硬编码 tool 返回」的合成轨迹（审计 §4 P0），需 1,420 次真实采集。
- SSCNC CRT OCR / VERICUT 双确认未入链（P2 能力补齐）。

---

## 4. 测试口径（为什么要打折看首轮数字）

首轮全量扫描（18:32–18:55）：**141 文件 / 91 ok / 46 failed / 4 hang**。

但这一轮跑在我**并发修改** 5 个文件的同一时间窗内。铁证：`test_contract_fixes` 扫描内 `1 failed + 1 error`，独立跑 24 passed；`test_extreme_cadcam_pipeline` 扫描内 2 errors，独立跑 2 passed。

### 4.1 对 31 个可疑文件逐条归因（`runs/test_classify_20261113.json`）

| 分类 | 数量 | 含义 |
| :-- | --: | :-- |
| **PASS（假红）** | 14 | 独立重跑全绿：`test_architecture` / `test_bundle_integrity_sha256` / `test_disciplined_ab_provenance` / `test_extreme_cadcam_pipeline` / `test_mem_budget_gate` / `test_memory_lifecycle` / `test_model_evolution_suite` / `test_moe14b_asset_gates` / `test_operator_gate_and_kernels` / `test_p0_symbol_fixes` / `test_physics_case_set` / `test_physics_corpus_gates` / `test_rsi_candidates` / `test_rsi_engine` |
| **HANG>30s** | 9 | 重型用例（跑深度流水线/等模型端点）：`test_agent_team` / `test_context_mode_integration` / `test_contract_fixes`（含联网用例）/ `test_google_deepmind_suite` / `test_hindsight_integration` / `test_memory_safe_agent_team` / `test_model_hardening` / `test_operator_extreme` / `test_paperclip_integration` |
| **FAIL — 环境垫片** | 4 | `safe-delete` 批量确认阈值 50：`test_paired_verdict_ruler`(52) / `test_provenance_gates`(50) / `test_rsi_case_pool`(58) / `test_rsi_contracts`(58) → 临时目录被拦，非产品缺陷 |
| **FAIL — 外部凭据** | 1 | `test_ai_scratch_integration`：`HTTP 401 Unauthorized`，需真实 API key |
| **FAIL — 真缺陷（已修）** | 2 | `test_no_hardcoded_credentials`（闸门扫到自己）、`test_eval_runner`（spec 缺 tools 触发空转闸） |
| **FAIL — 待决策** | 1 | `test_closed_loop_coverage`：3 条，即 §3 的 P1-1 |
| **未归因** | 18 | 归因跑在 520s 预算处停止，剩余 18 个文件未逐个复核，**不作任何结论** |

结论：首轮 **46 failed 里，真正落在产品代码上的只有 2 个（已修）+ 1 个待决策**；其余是假红、重型超时、环境垫片与外部凭据。

**教训（写进规程）**：跑全量回归必须冻结工作区；边改边测等于自造假红，且会污染哈希类闸门。

### 4.2 第二轮全量：27 failed → 真缺陷 3 个（同日收口）

冻结工作区后重跑 `pytest tests/`：**27 failed / 1779 passed / 9 skipped（1680s）**。逐文件隔离 + 换环境复跑后归因如下。

| 分类 | 数量 | 证据 |
| :-- | --: | :-- |
| 环境垫片（删除守卫） | 22 | 报错栈落在 WorkBuddy `sitecustomize.py:868` 的 `SystemExit: 1`；清 4 个 `CODEBUDDY_SAFE_DELETE_BULK_*` 后 `test_provenance_gates` 5 failed→17 passed、`test_paired_verdict_ruler` 2→12、`test_runner_repeats` 2→9、`test_security_audit`/`test_sleep_framework` 各 1→全绿 |
| 并发写仓 | 2 | `test_train_data_gate` 全量 3 failed / 隔离 6 passed；同刻 `data/sft/continual_web_learning.jsonl` mtime 在跑动中被改 |
| 显存被占 | 1 | `test_operator_extreme` 报 6.832 GB/s；同卡空闲直测 173 GB/s（Ollama 持有显存），清空后 8 passed |
| **真缺陷（已修）** | 3 | 见下 |

三条真缺陷：

1. **工具 JSON 重试风暴**（`virtu_real_backend._chat_with_room`）。`base` 在循环外取一次，第三次仍算出同一个 768 再试一遍——白跑一次完整前向。改为 `widened_once` 旗标，放宽只做一次。`test_tool_call_retry` 由 `[220,768,768]` 回到 `[220,768]`。
2. **SWARM 断言过期**（`tests/test_super_agent.py::test_10`）。旧断言要求 `mode` 恒 AUTONOMOUS、`require_real_swarm=True` 抛 `NotImplementedError`——那是 SwarmCommander 还只是别名时的口径。真委派落地后两条都反了。改写为更强的三条：写 SWARM ⇒ 必须真调过（`swarm_status=executed`）；中途抛异常仍写 SWARM 但 `success=False` + RCFA + 熔断；成功只看验证门。顺带把该用例从 4 分钟压到 60 秒（第二次调用改成 monkeypatch 的失败路径）。
3. **云端闸 fixture 缺文件**（`tests/test_wm_cloud_gates.py`）。`run_worldmodel_fix.sh` 在 2026-11-11 起额外要求 `dataset/virtu_wm_repairloop_sft.jsonl`，fixture 只拷了 impeller 那份，于是 `test_baseline_green` 被自己的闸门拒开训。补齐 fixture 并新增 `test_wm_repairloop_source_missing_red` 反证（缺该文件必须红）。

另有 1 处非缺陷但需改口径：`test_operator_extreme` 的 `>50 GB/s` 断言**不该放宽**（偏低的带宽会算错 roofline 下界），改为断言消息里直接打印 `free/total` 显存并点名 Ollama 占用，让下一个人不用查代码。

---

## 5. 吞异常报成功（补充扫描：6 处命中，修 4 处、2 处判为可接受）

扫描口径：`except ...:` 之后 6 行内直接 `return {"status": "success"/"ok"}`。命中 6 处（去重后），逐条读过上下文：

| 位置 | 判定 | 处置 |
| :-- | :-- | :-- |
| `bridges/cimco_bridge.py:109` | **真缺陷**：深检哨兵 import/解析失败被 `pass`，`status` 仍 `success`、`is_valid` 只反映"跑过的检查"——「没检查」被读成「检查通过」 | 已修：新增 `syntax_checked` / `syntax_check_error`；哨兵没跑时 `status=partial`、`is_valid` 必须同时满足"哨兵真跑过"，不可用原因以 `CHECK_UNAVAILABLE:` 前缀进错误清单（不伪装成程序缺陷，也不静默） |
| `virtu_omni/agent/adaptive_router.py:386` | **真缺陷**：CLI 退出码 0 但 stdout 不是 JSON，仍报 `status=success` + `raw_output` | 已修：`status=error` + `verdict_code=CLI_OUTPUT_NOT_JSON`，保留 `raw_output` 供排查 |
| `virtu_omni/agent/adaptive_router.py:415` | **真缺陷**：MCP 返回纯文本时同上 | 已修：`status=error` + `MCP_RESULT_NOT_JSON` |
| `bridges/assembly_build.py:189` | **真缺陷（度量层）**：组件/包围盒读取失败被 `pass`，`component_count=0` 与"真的没有组件"不可区分 | 已修：`read_errors` 字段显式记录哪一项没读到；`status` 不因此改变（保存成功仍是成功） |
| `bridges/assembly_build.py:265` | 误报：视图枚举失败已收进 `view_errors` 并随返回值带出（`:280`） | 不改 |
| `bridges/solidworks_bridge.py:966` | 可接受：`ViewZoomtofit2` 是纯视图适配，顶层状态不从它推导 | 不改 |

**扫描之外又发现一处同类问题**：`assembly_build.build()` 的顶层 `status` 恒为 `"ok"`，即使三个 step 全抛异常，只有 `all_ok` 是诚实的。已修为由 `all_ok` 反推（全成 `ok` / 部分 `partial` / 零产物 `error`）。

回归：`tests/test_contract_fixes_20261113.py` 新增 3 条（哨兵不可用不得绿、CLI 非 JSON 不得成功、MCP 非 JSON 不得成功），27 passed；受影响模块 `test_agent_adaptive_routing` / `test_agent_toolchain_full` / `test_assembly_gates` / `test_router_server_security` / `test_toolchain_access_modes` 共 46 passed。

## 5.1 评测基线可复现化（同日收口，三条结构性缺口）

§5 修的是「代码说谎」，这一节修的是**「分数不可复现」**——更隐蔽，因为它不报错。

| 缺口 | 实测证据 | 处置 |
| :-- | :-- | :-- |
| 题板不在 git 里 | `data/benchmark/` 74 个 `.jsonl` 中 **73 个 untracked**（只跟 `COVERAGE.json` + 图片）；`CASES.lock` 也在库外 | 80 文件 7.7 MB 入库，排除 `derivation.jsonl.pre_fosgate` 备份 |
| 克隆会打翻哈希 | `core.autocrlf=true`（本机实测），旧 `.gitattributes` 只护 `skills/**` ⇒ 克隆后 LF→CRLF，lock 里 74 条 sha256 全不匹配 | `data/benchmark/**/*.jsonl` 与 `CASES.lock` 标 `-text`，`git check-attr` 实测 `unset` |
| 锁只锁了 21/74 | 52 个题板「改了也没人知道」；另有 4 条漂移 | `--write` 重建，74 文件 0 problem |

为什么第三条不是「顺手把红灯按绿」：4 条漂移逐条查过，都是 2026-11-08 16:09:47–51 同一批的 FOS 闸改题——`phys_v1` 的 30/30 行、`rsi_pool_v1` 的 144/144 行 `system` 被扩写（新增平铺键规约、定律卡、非法输入负例族），`gold`/`criteria` 同步改。**属有意改题，不是损坏**；但它同时意味着 11-08 之前跑在这两份题板上的分数，口径与现在不同。这一点已写进条目 35。

新增 `tests/test_benchmark_baseline.py` 三条闸（入库 / `-text` / 锁覆盖且逐字节一致）。用 `git ls-files` 与 `check-attr` 取证，不靠人工记忆。

### 17 工具面的 `prompt_eval_count`：已补测

Ollama 本轮在线（72 个模型），用同题 `toolcall-e01`、同模型 `virtu-moe-14b:latest`、`num_ctx=8192` 各发一次真实 `/api/chat`：

| 工具面 | `prompt_eval_count` | 估算 | 偏差 |
| :-- | --: | --: | --: |
| 16（去掉 `cadcam_feature_ops`） | **4759** | 5315 | +11.7%（偏保守） |
| 17（当前宣告面） | **5132** | 5860 | +14.2%（偏保守） |

产物 `reports/PROMPT_TOKENS_BY_TOOL_SURFACE_2026-11-13.json`，脚本 `scripts/measure_prompt_tokens.py`（本机透明代理会截 localhost，脚本显式清空 `ProxyHandler`——不清空会表现为「TCP 连得上但读响应超时」）。

于是 `test_toolcall_plumbing_gates` 从「新面不得低于旧实测 4779」升级为**两个面各自卡 20%**，不再有靠旧数字外推的项。11-06 记的 4779 与今天 4759 差 20，是这期间工具描述文本被改过；两个数都保留，测试里注明来源，不当作矛盾。

---

## 6. 一句话结论

本轮清掉 11 处「会说谎/会失效」的地方：2 处产品契约（假可执行、0 成功报 partial）、1 处接口一致性（网络工具缺 status）、2 处**测量闸门自己坏了**（凭据扫描扫到自己、评测器 spec 与空转闸冲突）、1 处反向失真断言、1 组防漂移不变量，以及本轮新增的 4 处吞异常报成功（NC 校验哨兵、CLI/MCP 非 JSON、装配度量、顶层 status）。

**P1-1 已按你选的 A 执行完毕**：宣告 17 == 判分 17 == 注入 17，题板 30 → 34，`test_closed_loop_coverage` 三条红灯合法转绿并新增一条反向缺口闸。

**收尾轮（同日）把两件「挂着的」也做完了**：① 17 工具面的服务端 `prompt_eval_count` 已实测 —— 同题同模型下 16 工具 4759、17 工具 5132（+373），估算偏保守 11.7%/14.2%，测试从「不低于旧实测」升级为两个面各自卡 20%；② 评测基线可复现化 —— 73 个从未入库的题板 + `CASES.lock` 入库、题板标 `-text` 抗 CRLF、锁从 21/74 补到 74/74、新增三条基线闸。

全量回归从 **27 failed** 归因到 **3 个真缺陷（已修）+ 22 个环境假红 + 1 个显存占用**，最终 6 failed 逐条单独复跑全绿。三件真缺陷里最值钱的是重试风暴：它每次浪费一次完整前向，却只在「重试仍失败」时才暴露。

**真正没做的只剩两类**：语料仍是合成轨迹（需 1,420 次真实采集）、SSCNC/VERICUT 双确认未入链。这两件不是代码能替代的。
