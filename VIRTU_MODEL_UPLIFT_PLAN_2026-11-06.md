# Virtu 模型提升方案 v2（2026-11-06）

联网调研 2025–2026 年小模型 / 领域模型能力提升方案，结合本工作区全仓只读调研与逐文件复核后收敛。**本文不是评测报告，不宣称任何"已提升 X 分"。**

> v2 说明：v1 只依据 11-05/11-06 两份日志，经全仓复核发现 4 处事实错误，已在本文修正。以 v2 为准。

## 0. 口径声明与 v1 勘误

| 标记 | 含义 |
|---|---|
| `[本地·实测]` | 有明确证据文件（日志、GGUF 头、逐例 `raw.jsonl`、`receipt.json`、运行记录） |
| `[外部·报告值]` | 论文 / 厂商公开报告，未在 Virtu 上复现。**禁止**写入 `benchmarks/`、`README.md`、`PROVENANCE.json`，也不得当本地预期收益 |
| `[历史存档]` | 旧臂 / 旧 grader / 旧覆盖下产生，按现行闸门**不可与新数直比** |
| `[推断]` | 基于上述证据的判断，需实测证伪 |

**v1 的四处勘误（重要）**

1. **基座是 `Qwen/Qwen3-8B`（base），不是 Qwen3-8B-Instruct**。`PROVENANCE.json:33-38`、`cad_cam_six_software_lora/adapter_config.json:6`；`2026-10-30.md:70,84` 实测 Instruct 在 ModelScope 404 并已修脚本。`VIRTU_MODEL_STRENGTHEN_2026-11-05.md:102,108` 云端 runbook 里写 `--base .../Qwen3-8B-Instruct` 属设计稿笔误，**照抄会拉错基座**。
2. **云端训练已跑过多轮，不是"未训练"**：边界强化 v6 → v2 续训 → v3 定向精修（overall 80.03）。11-05 那批新数据（DPO 30 条 / 弱维 SFT 23 条 / RSI 108 条）才是"数据已产出、训练未跑"。
3. **测量闸门不是从零建**：`virtu_eval/provenance.py` 已实现 `RunIdentity` / `seal_leg` / `verify_seal` / `noise_envelope` / `delta_verdict`，且已产出唯一经闸门的全板基线（`run_id dde13885346d93ff`，210 例逐行 `served_layers` + 封缄）。缺的是 anchor set、判分器版本固化与口径统一。
4. **项目已有一条真·10B 主线**：`VIRTU_10B_UPSCALE_PLAN.md`，阶段 A（36→46 层深度扩展）**已执行并实测**，v1 完全未纳入。见 §4 P2-0。

补充口径不一致：`virtu_eval/provenance.py:43` 的 `BASIS = ("measured","partial","asserted","inferred")` 是 4 种，而 `AGENTS.md §8.1` 只写 3 种（缺 `partial`）。需统一后再谈数字入账。

---

## 1. 本地现状（先对齐事实）

| 项目 | 事实 | 证据 / basis |
|---|---|---|
| 参数量 | **8.19074 B**（399 张量逐 dims 累乘），`virtu-cad-cam-10b` 是品牌名 / 兼容别名 | `.workbuddy/memory/2026-11-06.md`、GGUF 头 `[本地·实测]` |
| 基座 | Qwen3-8B **base** + 6 个 LoRA（r=32/α=64）→ 4 适配器 delta/TIES 合并 → Q4_0 GGUF | `PROVENANCE.json:33-58` `[本地·实测]` |
| 别名陷阱 | 6 个 `virtu-*` 标签权重层逐字节相同 `sha256:c3b78c773`，仅 template/system/parameters 三层不同 | `PROVENANCE.json:268-280` `[本地·实测]` |
| 当前可发布基线 | `virtu-frozen:comp_v5`，`run_id dde13885346d93ff`：reasoning 62.35 / knowledge 69.67 / instruction 77.43 / generation 71.65 / generalization 56.42 / boundary 61.33 / toolcall 79.76（**部分覆盖 28/30**） | `benchmarks/VIRTU_FULL_BOARD_2026-11-05.md §3`，经闸门生成 `[本地·实测]` |
| 历史训练峰值 | v3 定向精修 overall **80.03**（v2 72.76 → +7.27），generation 90.71 破 90 | `2026-11-03.md:59-63` `[历史存档，旧臂旧 grader，不可与上行直比]` |
| 工具模板错配 | 线上生效 chat template 是 **156 字符**老式单轮模板、无 `.Tools/.ToolCalls` → 带 tools 请求 HTTP 400；但磁盘 `checkpoints/Modelfile_v5_comprehensive:10-27` **已含 `.Tools` 分支与 `<tool_call>` 格式**，`Modelfile_virtu_disciplined:10-27` 同样含；`qwen3:8b` 为 1723 字符原生模板 | `VIRTU_FULL_BOARD_2026-11-05.md:24-37` + 两份 Modelfile 逐行复核 `[本地·实测]` |
| 10B 深度扩展 | 阶段 A 产物 `virtu-10b-d46-q4_0.gguf`（5,699,918,176 B），`run_id a45b34271744f9ca`，GATE A 7/7 PASS；llama.cpp / Ollama 独立算出 **10.1202 B**、46 层；**8.41 tok/s**（8B 为 21.2）；L2 能力激活未做 | `VIRTU_10B_UPSCALE_PLAN.md §9`、`.receipt.json` `[本地·实测]` |
| 硬件硬墙 | RTX 4050 Laptop 6GB：8B 77% GPU / ~17 tok/s；3B 100% GPU / ~78 tok/s。本机 8B QLoRA **两次实测连加载都失败**（`No module named torch`、`caching_allocator_warmup` 额外 4.8GB → OOM、os error 1455、页面文件不足） | `2026-11-05.md:167-184`、`VIRTU_MODEL_STRENGTHEN §5` `[本地·实测]` |
| 云端 | 脚本 / 语料 / 预算（¥50–80 档）齐全；v4 的 damodel 41858 实例**已离线**，需新端口与凭据 | `2026-11-03.md:66-72` `[本地·实测]` |

---

## 2. 已经做过，别重复投入

**有效 · 已落地验证**

| 项 | 结果 |
|---|---|
| `disciplined` 提示词 + `VIRTU_THINKING_MODE=off` | 自由对话 7420 → 33–199 token（-98%）`[本地·实测]`；**只治部署态冗长，不治能力** |
| v3 定向精修（854 条 curated） | overall 72.76→80.03，knowledge +20 / generalization +18.12 / boundary +12.33 / generation 90.71 破 90 `[历史存档]` |
| 边界强化 SFT v6 | boundary 53.45→66.56，但 reasoning/generalization 退化 → 单维过拟合 `[历史存档]` |
| 输出卫生层 / 确定性核算 / toolcall 覆写修复 | 可归因腿 Δ=0.00、反证 19/19 还原；离线回放 +3.11~+4.29；57 passed `[本地·实测]` |
| 四层反幻觉护栏 | E1 180 条 recall 100%/FPR 0；E4 在线 A/B wm-v3 27→100、qwen3 33→100；**E5 结构化解码形状 100% 但数值仅 33%** `[本地·实测]` |
| 工具面补齐 + 通用接口契约 | 18 个 cadcam_* 工具；补契约后模型一次写出完整 10 步方案 —— **补的是接口，不是调模型** |
| 测量链治理 | `RunIdentity` / 封缄 / 逐行 `served_layers` / 反证测试 / 泄漏与量纲门禁（抓出 157 条逐字泄漏、255 条 mm⁵ 冒充 mm⁴） |
| 3B/8B 路由网关 + Ollama 0.40.14 + q8_0 KV | 3B 78 tok/s；**8B 6GB 硬墙不变** |

**无效 / 已证伪 / 红线**

- v2 用通用平衡数据（4233 条）续训 ⇒ 7 维无一 ≥90、overall 72.76 —— **用错数据，未对准弱点**。
- v3 从基座全新 LoRA 不继承 v2 ⇒ reasoning −2.41 / toolcall −3.33；curated 里 ~80 条格式数据被稀释没顶住。
- **v3 toolcall 70.00，20/30 失败 100% 因 JSON 格式**：模型输出 `{"name":...}`，判分器要 `{"tool":...}`。这是一个键名问题，不是能力问题。
- 旧 6-LoRA `peft_linear` 合并（Σ 原始权重 5.7）⇒ 乱码 / 死循环，已隔离 `_broken/`，禁止再部署。
- 本机 8B QLoRA、KV 量化 / flash-attn / `OLLAMA_GPU_LAYERS=-1` 全部试过，77% GPU offload 是物理硬墙。
- 直接改 system/prompt 治世界模型：格式合规 0→84.4%，但数值天花板 **28.1%**（量纲错 1000 倍、输出散文、字段缺失），报告明确判为「**prompt 修不了，必须重训**」。
- Qwen3 系微调把 `<tool_call>` 写进 `message.thinking`：14 工具 + 长任务必退化，`content`/`tool_calls` 为空；不要指望原生 tools 路径。
- `cadcam_assembly_build(full)` 宣称「模型自主闭环」已被 11-05 日志纠正归因（full 封装了 WorkBuddy 全部逻辑，模型只按一次按钮）。
- RSI 两次小预算（n=4/6，一次 blocked 一次 rejected，mean_gain −10.0）：**只能证明管道接通，不能读成 RSI 无效**。
- 6 个 virtu 别名相加 / 改 GGUF metadata 手写 `parameter_count` / 追加全零张量凑 10B / 240 例评测题当训练语料 / SMOKE_ONLY adapter 合并 / 无 receipt 服务：均为 `VIRTU_10B_UPSCALE_PLAN §7` 与 `PROVENANCE invariants` 红线。

---

## 3. 瓶颈诊断（这次该打哪里）

| 编号 | 瓶颈 | 实测证据 |
|---|---|---|
| **B1** | **权重级能力天花板（最根本）** | 难度断崖：知识 hard **40.83** vs easy **89.81**、边界 hard 46.95、工具 hard 38.89；`numeric_near` **62/100 失败**（51 条相对误差 >1%；原文 `:36/:181/:210` 三处一致，调研摘要曾写 54/100，以原文为准），`VIRTU_DISCIPLINE_2026-11-05.md:36,181` 明确判为「最大内容缺口；不是格式能修的，需计算器/训练」；世界模型 28.1% 天花板被判「必须重训」。所有优化至今停在提示词 / 后处理 / 合并，**没有一次带 run_id 的训练前后 A/B 被发布** |
| **B0** | **测量链仍不足以判定"有没有提升"** | 闸门已实现，但：`toolcall-h04` 存盘 100 vs 现判分器复评 33.33；11-05 事故（4 个 tag 被重指成同一 manifest、11 个构件被删、一条腿 30 条 404 被外部整体改写）；`published=0 refused=8`；**3 份 `basis=measured` 的玩具套件报告**（`benchmarks/VIRTU_GOOGLE_DEEPMIND_SUITE_VERIFICATION_2026-11-05.json`、`VIRTU_MODEL_EVOLUTION_SUITE_VERIFICATION_2026-11-06.json`、`VIRTU_ULTIMATE_SUITE_VERIFICATION_2026-11-06.json`）为硬编码常量、无逐题证据、无 run_id 溯源；**`checkpoints/COMPREHENSIVE_EVAL_REPORT.json` 仍写着 `weighted_total_score: 52.02` 与 `physics_compliance_rate: 1.0`**（后者正是 §8.1 点名的事故源），只有同名 .md 抬头加了作废标注、**JSON 本体未改**，是最易被误引的一处 —— 以上均未清理，会污染后续判断；`BASIS` 3 vs 4 种口径不一致 |
| **B2** | **服务层脚手架与模型能力错配** | 线上 156 字符模板 ≠ 磁盘已含工具分支的 Modelfile；JSON 键名 `name`/`tool` 不一致；`deception_gate` 把正文工具 JSON 判假调用并改写；`virtu-ties-v1` ReAct 尾部退回 `cadcam_preflight` 循环 7–11 次；缺接口契约漏 `sketch_holes`/`save_assembly`。日志原话：**「它缺的是接口知识，不是方法推理能力」** |
| **B3** | **无效思考（根因已精确到行）** | `checkpoints/Modelfile_v5_comprehensive:45-48` 模板末尾**无条件注入空 `<think></think>`**；210 例中 180 条含 think 标签、**175 条块内为空**；贪心解码退化复读 ≥7 例；21 例答案落在 thinking。disciplined 已把部署态 -98%，但评测通道本就带 max_tokens 压制 |
| **B4** | **量化档位老旧** | 全线上用 Q4_0（老式，比 Q4_K_M 差一档）；工具调用 / 数值 / 长推理对量化最敏感，**此共因从未做过 A/B** |
| **B5** | **架构认知偏差** | 全仓未找到 `wpt2-main@:8799` 的监听服务绑定（只有 `scripts/convert_smelt_folder.py` 引用工作区外路径 `D:\智能制造Agent\Virtu\out\wpt2_mfg_main`），也未找到「16 智能体编队」的精确代码对应；实际是 `virtu_omni/agent/agent_team.py` 的 **6 个**智能体 + AGENTS.md §4 的 **8 个 facets** + 18 个工具 + RSI gate/approval 与桥 `deception_gate` 两类信任机制。见 §7 |

外部对照：Agents' Last Exam（2026，1490 道真实职场题，工程制造 368 题）失败归因「方法选错/中途放弃 47%」+「领域知识缺口 25%」+「输出格式错误 10%」+「伪造数据 6%」`[外部·报告值]`，与 B1/B2/B3 同构。

---

## 4. 方案清单

### P0 · 零 GPU，当天可 A/B

**P0-1 补完测量链（治 B0，必须先做）** —— 注意闸门已存在，这里只补四个缺口
- 建 30–50 条**人标且输出永久冻结**的 anchor set；每次起腿用当前判分器重打 anchor，漂移即整腿作废（区分"系统退化"与"裁判变严"）。
- 判分器版本固化：每条腿记录 `graders.py` sha256 与 rubric/parser 版本；`BASIS` 统一为 `provenance.py:43` 的 4 种并回写 `AGENTS.md §8.1`。
- **清理四份假绿 / 残留假数**：三份玩具套件报告标记为 `asserted` 或移出 `benchmarks/`；`checkpoints/COMPREHENSIVE_EVAL_REPORT.json` 的 `52.02` 与 `physics_compliance_rate: 1.0` 改为 `asserted` 或加 `superseded_by` + 不可引用标记，禁止被后续引用。
- 闸门反证沿用 `tests/test_provenance_gates.py` + `scratch/_mutation_probe_gate.py`；植入坏样本必须判红。
- 验证判据：同一冻结输出重复 3 次零方差；复评 `toolcall-h04` 稳定在 33.33 而非 100；改判分器版本 → anchor 报警；`published` 数从 0 变正。
- 外部依据：*Who Drifted: the System or the Judge?*（arXiv 2026-06）；评测报告十项运行元数据；Aipolix 关于共享 API 漂移使 release gate 失效的仪器资格化 `[外部·报告值]`。

**P0-2 模板一致性修复（治 B2/B3，权重不动）** —— 项目已识别但未落地
- 磁盘 `Modelfile_v5_comprehensive` / `Modelfile_virtu_disciplined` **已含 `.Tools/.ToolCalls` 分支与 `<tool_call>` 格式**，`VIRTU_10B_UPSCALE_PLAN §9` 也写明「上线前必须注入 1723 字符原生模板」。缺的只是**把它 create 到线上标签**，去替换那个 156 字符老模板 —— 不是重新设计模板。
- 同时删掉 `Modelfile_v5_comprehensive:45-48` 的**无条件空 `<think></think>` 注入**，改为 `IsThinkSet` 条件分支（disciplined 版 `:33-39,55-61` 已是正确写法）。
- 把 `thinking → tool_calls` 转换上移到桥（11-05 RCFA 已建议未落地）；按阶段只下发 2–3 个工具子集。
- 把 18 个工具参数编成 Pydantic / JSON Schema 交给 Ollama `format`（GBNF 约束解码），重点统一 `{"tool","arguments"}` 键名 —— 这正是 v3 toolcall 20/30 失败的根因。**注意约束只保证语法合法、不保证语义正确**（本地 E5 已实测形状 100% / 数值 33%），必须叠加现有 L2 求解器复算。
- 可写 **G 代码 GBNF 语法**（`G00/G01/G02/G03` + `G54/G43/G90` 安全块 + 精加工刀调用）排除可检查缺陷。
- 验证判据：同请求 10 次 `temp=0` 的 `tool_calls` 非空率 / schema 合法率；`name` 键出现次数归零；空 think 块计数 180/210 → 0；preflight 重复轮数。

**P0-3 确定性核算从"兜底改写"改成"不覆写正确答案"** —— 3/3 调研给出的最近杠杆
- 现有 `_apply_numeric_corrections` / `_verify_arithmetic_response` 离线回放 +3.11~+4.29，但曾把正确的两项数组折叠成一项（已登记 xfail）。改为只在不确定时补算、已正确则原样透传，可拿到回放增益而不引入回归。

**P0-4 自适应思考预算 + 解码参数（治 B3）**
- 从"全局简洁"升级为按难度分配：`virtu_router.py` 三档扩成 `3B 直答 / 8B no_think / 8B think`。
- 修贪心退化复读：调 `repeat_penalty` / `top_p`（当前 `repeat_penalty 1.15` / `top_p 0.95` / `temp 0`），对 preflight 循环做 step 级早停（累积 logprob Φ 检测"高置信无新信息"重复步）。
- 避免朴素 token 级长度惩罚 —— 2026 多篇指出会砍掉必要推理，且本地已用 DPO 做过简洁偏好。
- 外部依据：SAGE / SAGE-RL（Qwen3-8B 上 MATH-500 超 50% 正确回答含无效步，报告 −46.5% token 且精度提升）；Sonata（ICLR 2026，同精度 −20~60% thinking token，开销 <1‰）；Step-GRPO / SLAT / SAR `[外部·报告值]`。

**P0-5 量化档位 A/B（治 B4，零训练）**
- `Q4_0` → `Q4_K_M` / `imatrix` 校准 / `Q5_K_M` 三档，用 `llama-perplexity` + 冻结集 + toolcall 子集对照，同时量 tok/s 与 GPU 卸载比。
- 外部依据：Q4_K_M 典型 PPL 劣化 1–3%、Q8_0 <0.5%；工具调用建议 ≥Q5_K_M，`sub-Q4` 更易破坏 JSON `[外部·报告值]`。

### P1 · 知识层，零训练，绕过 6GB 硬墙（治 B1/B2）

- **P1-1 领域知识图谱 / 最小证据子图 RAG**：把 `bridges/tool_calling_specs.py`、`derivation.LAWS`、执行器契约、G 代码与 GD&T 规范抽成可检索三元组/片段，每次只注入最小证据子图而非 9974 字符全量定义。外部依据：ARKNESS（*Int. J. Production Economics* 2026，CNC 工艺规划 280 题，小模型匹配或超越大模型，选择题 +16.6pp / F1 +16.5pp / ROUGE-L 8.9×，全本地）`[外部·报告值]`。
- **P1-2 Agent Memory Distillation（免训练）**：从成功轨迹提取「工作流 / 子任务 / 函数」三层记忆，任务开始注入前两类，工具报错后按需检索函数记忆。外部依据：AMD（arXiv 2608.07169，4B–8B 学生，AppWorld +27.2pp / BFCL V3 +11.2pp / ToolSandbox +3.4pp）`[外部·报告值]`。对"接口契约记不住 + ReAct 尾部退化"最对症。
- **P1-3 接口契约 → schema + RAFT**：契约机器可读化，训练模型"用检索到的契约、忽略干扰文档"；SFT 样本聚焦**带完整参数的工具调用 + 缺参报错自修**，JSON 示例禁止放真实量级数字（已实测会照抄 12345.6）。

### P2 · 权重训练（云端 ≥24GB，这是唯一能抬高 B1 的路径）

**P2-0 现有「真·10B 深度扩展」主线的评估与立场**
- 现状：`VIRTU_10B_UPSCALE_PLAN.md` 已定稿，阶段 A（36→46 层、10.1202B、run_id `a45b34271744f9ca`）**已实测达成 L1 结构真实**；阶段 B（冻结 layers.0~35、只训 36~45 的继续预训练，L40S 48GB）待算力；阶段 C 内容寻址上线待。红线：阶段 A 不宣称能力提升、不覆盖 latest。
- **判断 `[推断]`**：阶段 B 确实直指 B1 的"难度断崖 / 基座规模瓶颈"，但**在同等预算下应先做 P2-1，再评估阶段 B**，理由有三：
  1. 阶段 A 新增的 1.93B 是复制层，**能力为零**，激活它需要继续预训练 + 大量语料；而 v3→v4 的 368 条 patch 已就绪、根因已诊断（一个 JSON 键名）、成本确定（≤¥50、≤40min）。
  2. 10B 在 6GB 本机实测 **8.41 tok/s**（8B 21.2），12 层 CPU 卸载，且 `tokenizer.chat_template` 为空、capabilities 只有 completion、无 tools —— 部署成本明显变差，阶段 C 还得先补 P0-2 的模板。
  3. 2026 年 8B 级能力提升的主流证据集中在后训练 / 自蒸馏 / 可验证 RL / test-time compute，而非单纯堆层数（见 §6）。
- 建议：把阶段 B 作为**第二阶段**目标，前提是 P2-1 跑通且用同尺同 grader 证明 v4 增益；两条线共用 `RunIdentity` + 封缄 + `published=1` 闸门。

**P2-1 v4「短板补齐」补训 —— 最短、最确定（首推）**
- `data/sft/virtu_v3_patch.jsonl`（368 条：190 条 tool 格式强修 + 200 条 v2_curated replay 防回退，`bad=0`）、`scripts/_upload_and_launch_v4.py`、`_post_train_v4.py` 全部就绪且语法校验通过；`train_qwen3_8b_qlora.py` 已支持 `--resume-adapter` 从 v3 续训（**不重蹈 v3 不继承 v2 的覆辙**）。
- 唯一阻塞：damodel 41858 实例已离线，需新端口/凭据。预期 ≤¥50、≤40min。
- 目标：toolcall 70.00 → ≥83（历史一代 83–91）、reasoning 80.93 不回落、`{"tool","arguments"}` 键名合规率 100%。

**P2-2 11-05 新数据补训**：`dpo_concise_pairs.jsonl`(30) / `sft_weak_dims.jsonl`(23) / `rsi_synth_weak_2026-11-05.jsonl`(108，污染检查 PASS) 尚未训练。样本量小，应与 P2-1 合并一次云训而非单跑；先 SFT 后 RL，别跳级（AWS Qwen3-8B 案例：0.354 → SFT 0.6827 → GRPO 仅 0.6941）`[外部·报告值]`。

**P2-3 RLVR / GRPO 用现成 verifier（最大未被利用的资产）**
- 项目已有可程序化判真的东西：`ΔV` 体积守恒、`derivation.LAWS` + `wm_verifier.recompute`、FOS ≥ 1.5、G00 plunge 碰撞哨兵、FANUC Macro B 语法、工具 schema、单位量纲审计 —— 这就是 RLVR 的 verifier，无需人工偏好标注。
- reward：正确性（可验证）+ 契约合法性 + 仅对**正确解**施加 step 级长度惩罚；错误答案施加早停惩罚。优先打 `numeric_near` 62/100 这个最大内容缺口（可验证数值题天然适配 RLVR）。
- 外部依据：GRPO/RLVR；TLDR（错误答案一律加长度惩罚）；SAR self-aligned reward（准确率约 +4%、长度至少 −30%）`[外部·报告值]`。

**P2-4 U-OPSD 无监督在策略自蒸馏**：多次 rollout → 自一致性阈值下多数投票造伪解 → 在"自信但错"处自我蒸馏；无标签/无教师/无验证器。arXiv 2608.06296，代码 `github.com/williamium3000/u-opsd`；Qwen3-8B 非思考模式 5 个数学基准平均 **+10.7%** `[外部·报告值]`。**风险**：错误共识自强化，须留冻结 anchor 与独立 held-out，禁止自生成数据自评自己。

**P2-5 MOPD 多教师 on-policy 蒸馏，替代/补强 TIES**：现有 7 个 LoRA 专精适配器作教师，少量样本融合（外部报告 10K 样本 +4.18 分）`[外部·报告值]`。硬约束：合并前按 `PROVENANCE invariants` 做 delta/base 幅度检查 + held-out 逐任务闸门；不得再制造可改名别名。

**P2-6 语料治理补缺**：现有治理已相当完整（invariants 四条、`formula_holdout_200` 只做 gate、cloud_handoff sha gate、SMOKE_ONLY 不合并、`contamination_check` hard_leaks、`corpus_unit_audit` 量纲、`validate_cases.py` 拒收手写 gold）。**只补尚未有的**：cluster 级切分防泄漏、难度分级与类别下限 5%、训练输入长度分布匹配生产、内容寻址 id + drop ledger、13-gram 污染检测。在 `scripts/corpus_unit_audit.py` 上扩展即可。

### P3 · 评测集升级

- 建本地版 **MUSE 式三阶段执行闸门**：① 脚本可执行并导出 ② 几何有效性（水密/流形/无自交/无重叠）③ 设计意图对齐（功能性/可制造性/可装配性）。项目已有 COM 体积与特征树反读，可直接落地，天然满足 §4「闸门必须可证伪」。
- 外部对照：MUSE（106 个 CNC/3D 打印/激光切割实例）、BenchCAD（17,900 个执行验证 CadQuery 程序）、Agents' Last Exam 工程制造 368 题 `[外部·报告值]`。

---

## 5. 执行顺序与立场

| 序 | 方案 | GPU | 可验证信号 | 风险 |
|---|---|---|---|---|
| 1 | P0-1 补测量链（anchor / BASIS / 清三份假绿） | 无 | 冻结输出零方差；坏样本判红；`published` 转正 | 不做则后续增益不可归因 |
| 2 | P0-2 模板一致性 + JSON 键名 schema | 无 | 空 think 180/210→0；`name` 键归零；tool_calls 非空率 | 改 template 层会改 `RunIdentity`，须重新起腿 |
| 3 | P0-3 确定性核算不覆写 / P0-4 解码参数 | 无 | 回放增益且不引入数组折叠 | 过度早停砍必要推理 |
| 4 | P0-5 量化 A/B | 无 | PPL + 冻结集 + tok/s + offload 比 | 高档位在 6GB 更慢 |
| 5 | P1-1 / P1-2 知识层 | 无 | 接口参数完整率、ReAct 完成轮数 | 检索错上下文比不检索更糟 |
| 6 | **P2-1 v4 补训**（先开云实例） | 云端 ≥24GB | toolcall ≥83、reasoning 不回落、键名 100% | 实例凭据；SMOKE_ONLY 绝不合并 |
| 7 | P2-3 / P2-4 RLVR、U-OPSD | 云端 ≥24GB | 可验证 reward 收敛 + held-out | 奖励黑客、错误共识自强化 |
| 8 | **P2-0 10B 阶段 B**（条件触发） | L40S 48GB | layers.36~45 sha256 Δ≠0；board7+toolrouting+phys A/B 任一维跌 >3 分即拒 | 复制层扰动、灾难性遗忘、8.41 tok/s |
| 9 | P3 执行式闸门 | 无 / 少量 | 植入坏样本必须红 | 闸门空转 |

**三句话结论**
- **只做一件事** → P0-1。闸门虽已实现，但判分器版本没固化、三份假绿没清、anchor 没有，`published=0` 的状态下任何"提升"都无法写进台账。
- **零成本当天见效** → P0-2。磁盘上早就有含工具分支的正确模板，线上却挂着 156 字符老模板 + 无条件空 think 块；这是纯部署不一致，不是模型问题。
- **真正抬上限** → P2-1 先、P2-0 阶段 B 后。B1（hard 断崖 / numeric_near 62/100 / 世界模型 28.1%）被多份报告判定为"prompt 修不了，必须重训"，但 v4 的 368 条 patch 与续训链路已就绪、根因明确、成本确定；10B 扩层的 1.93B 目前是复制品，激活成本与部署代价都更高。

### 明确不建议

本地训 8B（两次实测失败）；继续堆同权重 `virtu-*` 别名；朴素 token 级长度惩罚 / 硬 budget forcing；把 9974 字符全量工具定义塞进 prompt；把外部论文数字写成本地预期或写进 `benchmarks/` / `README.md` / `PROVENANCE.json`；把 v3 的 80.03 与 11-05 的 62.35 等直接相减（不同臂不同 grader）。

---

## 6. 外部来源（均为报告值，未在 Virtu 上复现）

| 主题 | 来源 |
|---|---|
| 过度思考 / 推理压缩 | SAGE & SAGE-RL (labnotes.tech)；ACL 2026 推理压缩三法 (graphastra.com)；Step-GRPO / SLAT / SAR (graphastra.com, lacuna.tiptreesystems.com, i.ifeng.com)；Sonata, ICLR 2026 (iclr.cc/virtual/2026/poster/10011708)；TLDR (lacuna.tiptreesystems.com) |
| 无监督自蒸馏 | U-OPSD, arXiv 2608.06296, code: github.com/williamium3000/u-opsd；ZAYA1-8B (alphaxiv.org/audio/2605.05365) |
| 后训练 recipe / 蒸馏 | NebulaExp-8B, arXiv 2606.26671；AWS Qwen3-8B Serverless SFT+RLVR (digestai.news, tmtpost.com) |
| 知识层 / Agent | ARKNESS, Int. J. Production Economics vol.300 (2026)；AMD, arXiv 2608.07169；RAG vs FT 2026 (selfhostindex.com, pavlo.sh)；RAFT |
| 结构化解码 | Ollama structured outputs / llama.cpp GBNF (localaimaster.com, intelligibberish.com, sapirex.com) |
| 量化 | 2026 量化实战手册 (blog.llmgo.top, ainomam.com) |
| 模型合并风险 | mergekit / TIES / DARE skill conflicts (theneuralbase.com, iotdigitaltwinplm.com) |
| 语料治理 | SLM data curation (ertas.ai, aicassindra.com, mageex.com) |
| 评测可信度 | Who Drifted: the System or the Judge? (2026-06)；评测报告十项运行元数据 (juejin.cn/post/7698645127041433600)；Aipolix shared API drift；chatpaper.com/paper/349271 |
| 领域评测 | MUSE (selectdataset.com)；BenchCAD, arXiv 2605.10865；Agents' Last Exam (2026)；CNC G-code 对比研究 (eprints.ums.ac.id/147319) |
| 10B 深度扩展先例 | SOLAR 10.7B（见 `VIRTU_10B_UPSCALE_PLAN.md §3`，本项目自有方案文档） |

---

## 7. 需要用户澄清的一处前提

全仓只读检索**未找到** `wpt2-main@:8799` 的运行时服务绑定，也未找到「16 智能体编队」的精确代码对应：

- `scripts/convert_smelt_folder.py:3,84` 只引用工作区外路径 `D:\智能制造Agent\Virtu\out\wpt2_mfg_main`（24 个文件的转换脚本）；`2026-10-30.md:11` 把它定性为另一条**感知通道**模型线（1.28B LoopTransformer，与 Qwen3-8B 键空间交集 0，不可合并）。
- 实际代码是 `virtu_omni/agent/agent_team.py` 的 **6 个**专用智能体 + `AGENTS.md §4` 的 **8 个 facets** + 18 个 cadcam_* 工具；信任机制最接近的是 `virtu_omni/rsi/` 的 gate/approval 状态机与桥的 `deception_gate`。
- 指挥/感知通道分离（`qwen2.5:3b@11434` 快通道 / `virtu-comprehensive` 8B / Qwen3-VL-2B 独立视觉通道）**成立且已核实**。

若这两项来自本工作区之外的上下文，请补线索再定位；本方案没有建立在未经核实的前提上。
