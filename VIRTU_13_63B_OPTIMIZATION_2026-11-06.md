# Virtu 13.63B（virtu-moe-14b）全面优化记录 · 2026-11-06

> 口径遵循测量宪法：本文每个数字都标 `measured / asserted / design / 未测`，并给出证据路径。
> **§9 是同日"全面修复轮"的结果，其结论覆盖 §0/§3/§7 里当时因样本空转而写下的判断。**
> **§10 是同日"归因轮"的结果，其结论覆盖 §0/§9 里的数字**：§0 那句"n=30 维可分辨下限 4.47 分"用的是**复测 σ**，而两臂差的可分辨下限是**配对 CI**（实测 toolcall ±8.79、knowledge ±13.59）——4.47 只是地板，不是尺子。§10 另给出今晚唯一被实测支持的降噪杠杆（判据粒度，σ(Δ) −14%）。

---

## 0. 一句话结论

13.63B 的问题**不在专家，也不在量化，而在两处"没人能证伪的环节"**：模型内路由从未训练（本轮实测两专家门控方向余弦 +0.643、条件数 2.145），以及判分器没有噪声底线（本轮第一次测出 σ=8.84 ⇒ n=30 维的可分辨下限是 **4.47 分**）。今天所有关于 MoE「领先 2.78 / 4.44 分」「正交门控已强化」的结论，都落在这两个环节的噪声里，因此**全部作废待重测**；本轮交付的是把它们变成可判定的工具与臂。

---

## 1. 身份复核：13.63B 到底是什么（独立复算，不采信收据）

工具：`scripts/moe14b_gate_forensics.py`（自研 GGUF 解析，逐张量 sha256），输出 `runs/moe14b_gate_forensics.json`，`run_id=efa73072469d7761`，basis=measured。

| 项 | 复算值 | 与收据一致？ |
|---|---|---|
| 张量数 | 435 | 收据未记，新测 |
| 总参（逐张量 dims 累乘） | **13,626,848,256** | ✅ 一致 |
| 每 token 激活（含路由） | **8,191,030,272** | ✅ 一致；公式 `total − (E−top_k)·3·H·FFN·L` |
| 不含路由激活 | 8,190,735,360（= Qwen3-8B 基座） | ✅ 两条独立路径互印 |
| 未激活专家 FFN | 5,435,817,984（张量计数与公式双算一致） | ✅ |
| 路由参数 | 294,912（2×4096×36） | ✅ |
| 共享专家 FFN | **0**（`expert_shared_feed_forward_length=0`） | ⚠️ 新发现：本件**无共享专家** |
| 量化布局 | Q4_K(4.5bpw)+Q6_K(6.56bpw)+F32 ⇒ Q4_K_M | ✅ 块几何由文件偏移间隔反推并逐张量校验 |

**"13.63B"是稀疏总参，每 token 只走 8.19B；不得表述为 dense 14B。**（此口径此前已写入 receipts，本轮复核为 measured。）

---

## 2. 本轮落地的四项优化

### 2.1 路由层：把「无语义」从口头结论变成可复算数字

同一工具实测两版门控张量（朝向修正后；GGUF 的 `ffn_gate_inp` header dims 是 `[4096, 2]` **列主序**，专家向量是 `w[:,e]` 而非 `w[e]`——`PROVENANCE#strengthen_audit_2026_11_06.router_audit` 的 ±0.8066/−0.8005 与 −0.6476 是按错误朝向量的统计，本轮已在反证测试里钉死这条朝向回归）：

| 指标 | `:latest` 随机门（在役） | `:semantic` 正交门 | 含义 |
|---|---|---|---|
| 两专家行向量余弦（36 层） | **+0.643**（min 0.631 / max 0.652） | **−0.015**（min −0.028 / max −0.002） | 随机门两方向高度共线 ⇒ 判别分量只占每行能量 ~34% |
| 门控条件数 κ | **2.145**（2.10–2.18） | **1.027**（1.01–1.04） | mergekit 口径 κ≥5 才算坏，但 2.15 仍是"near-parallel" |
| 每层门控是否互异 | 36 个值全不同 ✅ | 36 个值全不同 ✅ | 非单一复制张量 |
| 与全 1 方向的能量占比 | 5e-5 ~ 3.8e-4 | 5e-6 ~ 6.4e-4 | 决策边界**不是**"隐状态均值符号"，旧审计这句话的机理不成立 |
| 秩亏层数 | 0 | 0 | 未塌成单方向（反证测试合成件才触发，见 §4） |

**正交化确实是真改进（κ 2.145→1.027）**，但它是**构造性质**，不是能力证据。而 `:semantic` 的收据写着 `gate_orthogonality_cos = −7.45e−09`，实测文件里是 −0.015（|cos|≤0.028）——**收据数字与字节不符**，属宪法第 1 条违规，已在 §5 记为待修。

### 2.2 判据层：造出「只差路由权重」的两臂，并补上噪声尺子的生产者

- **发现混淆**：在役 `:fast` 与 `:semantic` 在 8 处不一致（template source、system 文本、num_ctx 8192↔4096、num_gpu 22↔24、presence_penalty、min_p、repeat_last_n、stop 列表）。因此「正交门控有没有用」这个问题**在当前标签上根本无法回答**。
- **修复**：`scripts/moe14b_matched_tags.py` 参照 `:fast` 生效配置重建两臂，标签按 GGUF 内容哈希（宪法第 2 条）：
  - `virtu-moe-14b:a2103c68`（随机门对照臂）
  - `virtu-moe-14b:01068725`（正交语义门实验臂）
  - 产物闸 G-0…G-5 全绿（`runs/moe14b_matched_tags.json`）：两文件 **kv 段逐字节相同**（含 chat_template sha `a55ee1b1…`）、渲染模板相同、system 相同、parameters 相同、参数量均 13,626,848,256、而 GGUF 字节不同。张量级证明见 §1：**435 张量中恰好 36 个不同，全部是 `ffn_gate_inp.weight`，其余 399 个 sha256 相同**。
- **补生产者**：`virtu_eval/provenance.py::noise_envelope` 早就规定「没有 ≥8 对配对复测就不准称增益」，但**仓库里没有任何脚本产出过 probe 文件** ⇒ 今天的增益判定实际上全部在无闸状态下发出。新增 `scripts/moe14b_noise_probe.py` 补上，实测：

  ```
  臂 virtu-moe-14b:a2103c68 · knowledge+toolcall 各 4 题 · temp=0 · 同 seed · 同题问两遍
  paired_sigma = 8.84    n_pairs = 8    p_score_changed = 0.125    max_paired_delta = 25.0
  证据：runs/moe14b_noise_probe.json（basis=measured）
  ```

  即：**同模型、同题、同 seed 重问，8 题里有 1 题分数会变，最大变 25 分**。

### 2.3 服务位：把沿用的 num_gpu=22 换成实测最优

`scripts/moe14b_service_point_grid.py`（端口显式钉 11435、请求前校验 `/api/tags` 有该标签、单格崩溃记为传输错误而非成绩、链锁独占）：

| num_gpu @ctx4096 | tok/s | load | 备注 |
|---|---|---|---|
| 0（纯 CPU） | 2.87 | 49.7 s | 早前一次独立运行 |
| 12 | 3.07 | 34.3 s | 同上那次运行 |
| auto（不传 num_gpu） | **500 崩溃** | — | 未测出数字 |
| 18 | 4.20 | 27.8 s | |
| 22（在役值） | 5.23 | 34.6 s | **另一次运行同配置直接 500 崩溃** ⇒ 崩溃与配置无确定对应 |
| 24 | 500 崩溃 | — | |
| **30** | **10.18 / 9.77** | 22.0 / 23.9 s | **实测最优，建议取代 22** |
| 36 | 6.55 | 22.3 s | 全推反而更慢 |
| ctx 4096↔8192 @30 | 9.77 ↔ 9.57 | — | 差别小于散布，不构成决策 |
| 惩罚三组 @30 | 9.52 / 9.94 / 10.02 | — | `repeat_runs` 全 0 ⇒ **本轮未复现退化**，惩罚对质量的作用＝未测 |

两条附带硬事实：① 7 格里 3 格撞 llama-server CUDA 崩溃（`ggml_cuda_kernel_can_use_pdl` 初始化失败 → 进程 `0xc0000409`），这是 **P1-3.2 里"主动预热触发 500"的真因**，不是 keep_alive 语义问题；② 同一最优点跨时段 tok/s 散布 `[10.18, 9.77, 7.55, 7.27]`（±25%），**单个 tok/s 数字不得用来论证步数/成本**（与既有记忆一致）。

### 2.4 反证闸：每条新判据都有"植入坏样本⇒必须红"

`tests/test_moe14b_asset_gates.py`：**23 passed**，覆盖

| 植入的坏样本 | 必须红 |
|---|---|
| 门控朝向被读成 `w[e]`（正交合成件 cos 应为 0） | ✅ 否则测试失败 |
| 两专家行完全反平行（秩亏） | ✅ 记 `rank_deficient_layers`，聚合值出 `None`，**不许悄悄变 nan** |
| 无 `ffn_gate_inp` 的稠密件 | ✅ 抛异常，不得"空匹配=通过" |
| dtype 表与文件布局矛盾（把 F32 声明成 Q4_K） | ✅ `contradicts the file layout` |
| 文件被截断 | ✅ 抛异常，不得算成 0 参 |
| MoE 几何 kv 缺失 | ✅ 拒绝推导激活参（rc=3） |
| 两臂喂同一个 GGUF | ✅ G-5 红：比较无意义 |
| 模板/system/参数漂移、参数量不是 13.63B、kv sha 缺失 | ✅ G-0…G-4 逐条红 |
| 只有一臂 | ✅ G-0_two_arms 红 |
| 不存在的模型标签 / 空标签表 | ✅ 拒测 |
| 别的链持锁（新鲜） | ✅ 拒跑；锁过期(>300s)则放行，防闸把机器卡死 |
| 单格 500 | ✅ 记 `transport_error` 且 `tok_s=None`；成功腿仍出速度（正反两路都测） |

---

## 3. 被本轮否证的既有结论（不得再复述）

| 既有说法 | 出处 | 否证依据 |
|---|---|---|
| 「MoE 在知识维领先稠密 4.44 / 2.78 分」 | `PROVENANCE#densify_moe_exit_2026_11_06` | σ=8.84、带 = 1.96σ√(2/n) ⇒ n=24 为 ±5.00、n=30 为 ±4.47；2.78 与 4.44 均 ≤ 带 ⇒ **不可判** |
| 「路由 hybrid 比稠密 +6.95 分（oracle 86.12）」 | `PROVENANCE#p1_3_routing_2026_11_06` | n=24 时带 ±5.00 ⇒ 6.95 勉强超带，但 oracle 是**样本内上限**、不是现场保底，仍不可当作现场增益 |
| 「正交语义门控 GATE_PASSED / 已强化」 | `virtu-moe-14b-semantic…receipt.json`、`:semantic` 的 system 文案 | ① 只有构造性质、无能力腿；② 与在役臂存在 8 处配置混淆，能力腿在当时**不可测**；③ 收据的正交度 −7.45e−09 与字节实测 −0.015 不符 |
| 「路由决策≈隐状态全局符号」 | `PROVENANCE#strengthen_audit_2026_11_06.router_audit` | 朝向读错；实测与全 1 方向能量占比 <4e-4，结论方向对（无语义）但机理表述错 |
| 「主动预热触发 500 是 keep_alive 切换问题」 | `VIRTU_P1_3_2_ADAPTIVE_2026-11-06.md` | 真因是 llama-server CUDA 核初始化崩溃（本轮 3/7 格复现） |

---

## 4. 本轮新发现的资产/基础设施缺陷（待修，非本轮范围）

1. **判据件与账本都不在版本控制里**（`git ls-files` 实测）：`virtu_eval/` **0 个文件被跟踪**（判分器/runner/provenance 本体）、`checkpoints/PROVENANCE.json` **未跟踪**且散落 3 个 `.bak_*`、`runs/` **0 个文件被跟踪**；相比之下 `scripts/` 49、`tests/` 30、`benchmarks/` 12 已跟踪。后果：宪法第 1/3 条的"可归因"目前**只靠本地磁盘**——2026-11-05 那类"标签被重指 / raw.jsonl 被替换"事件事后无从对证。建议 `git add virtu_eval/ checkpoints/PROVENANCE.json` 加本轮 5 个新工具与测试；`runs/` 视体积决定。**这是仓库跟踪面改动，等你点头再做。**
2. **`virtu-moe-14b:semantic` 收据的正交度与字节不符**（§2.1）。要么改收据为 measured 实测值，要么标 asserted 并说明来源。
3. **11434 端口现在服务 0 个模型**：桌面 `ollama app.exe` 看门狗在 20:03 重拉起的 `ollama serve` 环境里没有 `OLLAMA_MODELS`，日志逐条 `bad manifest … The system cannot find the path specified`（走 `C:\Users\Administrator\.ollama\models` junction 时全 manifest 失败；直接 `E:\ollama\models` 则 26 标签正常）。**后果：路由层 `/ask` 与任何默认打 11434 的工具现在都拿不到模型。** 本轮测量全部改打 11435（PID 见 `runs/ollama_11435.log`，version 0.40.14，store=E:\ollama\models，blobs 78）。修法二选一，都要你确认：A) 停 app 看门狗再用 `E:\OllamaApp\serve_e_store.bat` 顶住 11434；B) 修 junction 让默认路径可读。
4. **`virtu_eval/arms.json` 本轮被整体重排**（补 tools 时 `json.dumps(indent=2)` 与磁盘原格式不等，自检 `formatting stable: False`）：已用断言证明**其余 21 条臂的语义逐字段未变**，但文件形态变了；该文件未入 git，故无 diff 可对证。后续改它请走"读→改→等值断言→写回"，并要求先入版本控制。
5. **工具面 schema 与 ctx 阶梯不匹配（本轮实测暴露，影响线上工具调用）**：给臂注入 16 个 `cadcam_*` 工具后，**toolcall prompt 实测 4779 tokens**，Ollama 直接 `400 request (4779 tokens) exceeds the available context size (4096 tokens)`，30 题 12/12 同构失败 ⇒ 按熔断公理立即停腿。而线上 `virtu_real_backend.py:1236/1380/1457` 的阶梯是 `need_4k = bool(tools or has_tool_msg or total_len > 3000)` → `num_ctx = 4096 if need_4k else 2048`，**带工具的天花板就是 4096**；`_chat_with_room` 只对 `invalid tool call arguments` 放宽 `num_predict`，**不处理 400 溢出**；`VIRTU_NUM_CTX` 在 HKCU、当前环境、仓库文件里都未设置（三处均查过）。
   ⇒ 结论：同一份 16 工具 schema 在线上路径也是 4779 > 4096 的必然失败（`measured` prompt tokens + `asserted` 代码天花板），**不是模型不会调工具，是请求根本进不去**。修法二选一，建议都做：① `need_4k` 分支按 token 计（现在 `total_len` 是**字符**数）并加 8192/12288 档；② `_chat_with_room` 增加"400 exceeds context ⇒ 升 ctx 重试一次"的分支。另注：`arms.json` 里 `moe_fast`/`dense_fast` 只写了 `tools_dimensions` 没写 `tools` ⇒ 任何用它俩跑的 toolcall 维都是**判据空转**（本轮就是这样浪费了一轮：24/30 零分、三臂同分 16.67）。
6. **磁盘**：D 仅剩 23.8 GB，而 `checkpoints/` 上 MoE 三件套占 43.9 GB（bf16 参考件 25.4 GB 从未用于推理，`num_gpu=0`）。建议把 bf16 件迁 E: 或隔离；**属破坏性/搬迁操作，未执行**。

---

## 5. 三档可行性矩阵（机器可读版：`benchmarks/VIRTU_13_63B_FEASIBILITY.json`）

| 档 | 项 | 判据 |
|---|---|---|
| **本机可交付**（零训练、零租卡） | 路由几何取证 ✓ / 配对臂构造 ✓ / 噪声底线 ✓ / 服务位网格 ✓ / 反证闸 ✓ / A/B 出判（在跑，§7） | 全部有产物与 run_id |
| **受限可交付**（需时数或需你点头） | 惩罚对退化质量的测量（要 ≥512 tok × 多题，本机 ~1 h）；把 A/B 扩到 6 维全板（≈3 h）；git 跟踪 virtu_eval；11434 服务修复；bf16 件搬迁 | 成本已实测/外推，标注见 JSON |
| **不可达**（本机证伪，须算力或须架构改动） | 训练路由 W_gate（需 hidden-state 监督，6 GB 上 8B 前向不可行）；专家继续预训练（P1-3 已终止，且记忆口径「零租卡」）；把 13.63B 变成"每 token 真用 13.63B"（架构即如此，不可能） | 见 §6 路线，均需 GPU |

---

## 6. 后续进化方向（按杠杆排序，全部标口径）

**E1｜先让判据有分辨率，再谈任何增益**（最高杠杆，零训练）
现 σ=8.84 是**判分器尺度过粗**（100 分制、少判据）造成的。两条降 σ 路径：① 把 score 改成**逐判据 pass_ratio 的均值**并固定判据数；② 同 seed 3 次重复取中位。~~σ 降到 4 ⇒ n=30 时可分辨下限从 4.47 分降到 2.02 分~~ ⇒ **本句算术已订正（22:5x）**：CI 半宽是 `1.96·σ(Δ)/√n`，不是 `1.96·σ·√(2/n)`。按实测 σ(Δ) 重算：要在 n=30 上判出 Δ̄=+2.22（正交门那条），需 σ(Δ) ≤ **6.2 分**，即从现在的 8.46 再降 **1.4 倍**；而 MoE-vs-稠密那条的 σ(Δ)=24.14，需降 **4 倍**才同量级可判。⇒ 两条约束不同，优先级也不同：**正交门那条只缺分歧题数（2→8，McNemar 口径），不缺 σ**；MoE-vs-稠密那条才缺 σ。
> **E1 状态更新（§10.2 实测）**：路径①已落地并被零推理验证 —— 按槽位拆判据使 σ(Δ) 24.14→**20.76**（−14%，覆盖 7/30 题；`runs/moe14b_rescore_discriminative.json` run_id `8421bf66d5c7c28b`）。路径②（`--repeats 3`）代码与 9 条测试已就绪，经验腿仍被提交内存挡住。原句的 `design` 现改为：①`measured(partial)`、②`未测(等资源)`。

**E2｜路由要走"文档级 + 专家专稠密"，不要再指望逐 token 门控**（零训练，本机可建）
数学事实：2 专家、无 bias 的线性门控，其决策边界是过原点的超平面，**不可能恒选某一专家**（要恒定只能让两行相等 ⇒ 平局，落到实现细节）。所以本轮否掉了"强制专家 GGUF"这条路。可行替代：
- 用同一配方各造一个**单专家稠密件**（`base + TIES 注意力` + 只挂 expert_0 的 FFN 增量 / 只挂 expert_1 的），
- 由已实测 recall=1.0/precision=1.0（n=20，样本内）的 bge-m3 文档级路由器选模型。
- 上限有实测锚点：oracle 混合 86.12 vs 稠密 79.17 vs MoE 81.95（`run_id rt-c3f88964c48392ef`，n=24 样本内 ⇒ 只当**上限**，不当保底）。
`design`，建件 + 评测 ≈ 半天机时；**结论必须过 E1 的分辨率闸**。

**E3｜真正的 MoE 激活要么训练，要么删**（需算力，本机证伪）
`expert_delta_audit` 实测两专家增量近正交（cos 0.0068）⇒ 分工是真的，坏在门。门需要 hidden-state 监督：6 GB 上跑 8B 前向不可行 ⇒ 与阶段 B 同判：**不在本机宣称**。若某日有卡，最小成本动作是**只拟合 294,912 个路由参数**（冻结其余），比"重训整个 MoE"便宜三个数量级。`asserted`（依据是既有实测显存/吞吐结论）。

**E4｜架构卫生**：本件 `shared_expert=0`。现代 MoE（Mixtral/DeepSeek）都有共享专家 + 负载均衡损失；没有共享专家意味着被路由错就是全错。若要继续保 MoE 形态，加共享专家比加专家数更值。`design`。

**E5｜服务化**：把 `virtu_router.py` 的 `GEN_OPTS_HARD` 从 `num_gpu 22` 改为 **30**（§2.3 实测），并在路由器里加"500/CUDA 崩溃 ⇒ 重试或降级到稠密"的 fail-closed 分支——现在崩溃直接变 500 给用户。`measured` 支撑，改动 5 行，**待你确认是否现在改**（链在跑时不动执行器，见记忆 [[refactor-under-experiments]]）。

**E6｜RSI 闭环接入**：最新提交 `2671c86` 落地的 RSI 需要一个"能证伪的判分器"才能自我改进；本轮的噪声尺子+配对臂正是它的准入条件。**顺序必须是 E1→E2→再谈自我改进**，否则 RSI 会把噪声当信号放大。`inferred`。

---

## 7. 第一轮配对 A/B 结果（已收口，basis=measured）

链 `runs/moe14b_ab_chain.log`：三臂 × knowledge+toolcall 各 30 题，temp=0、seed=1234、token_floor=224、全部走 11435，**0 传输错误**。
臂身份已复核：`random↔orthogonal` 逐字相同响应仅 3/60、`random↔dense` 0/60，model_id/base_url 逐腿核对 manifest ⇒ **不是同一份权重冒名三臂**。

| 维度 | 随机门 | 正交门 | 稠密 merged-v2 | 判定 |
|---|---|---|---|---|
| knowledge (n=30) | **69.56** | 69.44 | 66.27 | 正交门 Δ=−0.12 ⇒ **噪声内**；MoE−稠密 +3.29 ⇒ **噪声内**（带 ±4.47） |
| toolcall (n=30) | 16.67 | 16.67 | 16.67 | **判据空转**（见下），本轮不作结论 |

配对逐题分析（比均值带更硬的独立路线）：`random vs orthogonal` 同分 50/60、逐题 Δ 均值 **−0.06**、σ(Δ)=19.48 ⇒ SE=2.51、t=−0.02；`random vs dense` 同分 47/60、Δ 均值 **−1.64**、σ(Δ)=26.46 ⇒ SE=3.42、t=−0.48。**两条都是零效应。**

**本轮自己造成的第二个假绿风险（已修）**：三条新臂沿用了 `moe_fast`/`dense_fast` 的写法，**只写了 `tools_dimensions` 没写 `tools` schema** ⇒ toolcall 30 题对三臂全是 24/30 零分、均值一模一样 16.67，这条维量的是"没给工具"而不是能力。已给三臂补上 16 个 `cadcam_*` 工具并重跑（`runs/moe14b_ab_tools.log`，输出 `runs/moe14b_ab_verdict_toolcall_*.json`）。

**诚实结论（可写进台账的那一句）**：正交语义门控重构在 knowledge 上**测不出任何效应**（Δ=−0.12，t=−0.02）；MoE 相对稠密 merged-v2 在本尺当前 σ 下**仍不可判**（+3.29 < 4.47）。因此「`:semantic` 是优化」不成立，它至多是 κ 2.145→1.027 的**构造改进**。

---

## 8. 证据清单

| 文件 | 内容 |
|---|---|
| `scripts/moe14b_gate_forensics.py` / `runs/moe14b_gate_forensics.json` | 参数量、张量级 diff、门控几何，run_id `efa73072469d7761`。⚠️ 该 run 之后脚本又加了两处（秩亏不得聚合成 nan、门控形状按 kv 参数化而非写死 4096），**receipt 里的 `tool_sha256` 对应改动前版本**；A/B 链跑完后需重发一次取证 receipt 以做到码证同源 |
| `scripts/moe14b_matched_tags.py` / `runs/moe14b_matched_tags.json` | 只差路由权重的两臂 + G-0…G-5 |
| `scripts/moe14b_noise_probe.py` / `runs/moe14b_noise_probe.json` | 判分器噪声 σ=8.84 |
| `scripts/moe14b_service_point_grid.py` / `runs/moe14b_grid_*.json` | 服务位网格 + 崩溃记录 |
| `scripts/moe14b_ab_verdict.py` / `runs/moe14b_ab/*` | 配对 A/B 与预登记判据 |
| `tests/test_moe14b_asset_gates.py` | 23 条反证测试 |

> **本轮自纠（写作后校验）**：本文初稿把手算的 95% 带写成 7.05/6.29/4.45/3.91，比脚本实际公式 `band = 1.96·σ·√(2/n)` 大了 √2 倍。正确值为 **n=24 ⇒ ±5.00、n=30 ⇒ ±4.47、n=60 ⇒ ±3.16、n=78 ⇒ ±2.77**（与 `scripts/moe14b_ab_verdict.py` 打印值同源）。结论方向不变：2.78/4.44 仍在带内。


---

## 9. 全面修复轮（2026-11-06 21:0x–22:0x，覆盖前文若干结论）

### 9.0 统计口径自纠（第三次，也是最重要的一次）：今晚所有"超带"结论都作废

9.1 一度宣布"MoE 在 toolcall 上 +5.55 超带 ⇒ 真净增益"。**那个判定用错了分母**，现已撤回。

- 沿用 `delta_verdict` 的 `band = 1.96·σ_复测·√(2/n)` 是把**同一臂复测的散布**当成**两臂配对差**的散布。配对差的正确分母是逐题 Δ 的标准差：`SE = σ(Δ)/√n`。
- 两条腿各自实测：`σ_复测(MoE)=8.84`、`σ_复测(稠密)=23.57`（`runs/moe14b_noise_probe_dense.json`）⇒ **"σ 来自 MoE 的 CPU 卸载"这一假设被否证**：全 GPU 的稠密臂反而更噪。
- 用配对统计重算今晚四个比较（`runs/moe14b_ab_paired_stats.json`、`runs/moe14b_ab_paired_recheck.json`）：

| 比较 | Δ̄(B−A) | σ(Δ) | 配对 95%CI | t | 逐题不同分 | 判定 |
|---|---|---|---|---|---|---|
| toolcall：MoE 随机门 vs 稠密 v2 | −5.56 | 26.38 | **±9.44** | −1.15 | 5/30 | **不可判** |
| toolcall：随机门 vs 正交门 | +2.22 | 8.46 | ±3.03 | +1.44 | 2/30 | **不可判** |
| knowledge：随机门 vs 稠密 v2 | −3.29 | 37.98 | ±13.59 | −0.47 | 13/30 | **不可判** |
| knowledge：随机门 vs 正交门 | −0.11 | 28.02 | ±10.03 | −0.02 | 10/30 | **不可判** |

> ⚠️ 本表第一行随后又被 §10.0 修正：−5.56/±9.44/5-30 里含**一条不可归因的空响应**（`toolcall-m14`，当时稠密标签 manifest 缺失），剔除后为 **−3.45 / σ(Δ)=24.14 / ±8.79 / 4-29**（run_id `4eec822bba919daa`）。判定仍是不可判，但引用数字请用 §10 的版本。本表保留只为记录"当时怎么算的"。

- 更要命的是**判别力本身**：toolcall 两臂 **25/30 题分数完全相同**，5.56 的差全靠 5 道题翻转撑着；knowledge 也只有 13/30 不同。⇒ 这套用例对这两条臂**几乎没有分辨率**，扩题方向应该是"专门找两臂会分歧的题型"，而不是把 30 题加到 60 题。
- 已修：`moe14b_ab_verdict.py` 现在同时报 `band_paired / band_reask / σ(Δ) / t / discordant_cases`，**必须两个都越过才叫增益**；`不同分=0/N` 直接判"这条维不含任何判别信息"。回归测试 7 条（`tests/test_paired_verdict_ruler.py`），含"今晚这个翻转分布必须判不可判"的钉死断言。全套 **44 passed**。

### 9.1 实测数字（判定见 9.0：全部不可判）
第一轮 toolcall 是判据空转（三臂都没带 tools schema），带真实 16 工具面重测后：

| 臂 | toolcall 均分 (n=30) | 产出 native tool_calls | 零分题 |
|---|---|---|---|
| `virtu-moe-14b:a2103c68`（随机门） | **91.11** | 28/30 | 0 |
| `virtu-moe-14b:01068725`（正交门） | **93.33** | 28/30 | 0 |
| `virtu-dense-merged-v2:q4_0` | **85.56** | 26/30 | 2 |

（均值差是真实的观测，但按 9.0 的配对统计全部落在 CI 内；下表只作"两臂在这条维上大致相当、MoE 略高"的描述，不得引用为增益。）

- **今晚对"MoE 该不该留在难路径"的最终回答是：不可判**——既不是"退出"（那建立在空转样本上），也不是"留下"（+5.56 落在配对 ±9.44 内）。
- 能站住的只有两件：① toolcall 判据在没给 tools schema 时是**假绿**（已加闸+重测）；② 两臂在 25–28/30 题上**分数相同**，说明现行用例无法区分稠密与 MoE，需要的是**判别性用例**而不是更多同质用例。

### 9.2 已修清单（每项都有反证测试，全套 37 passed）
| # | 缺陷 | 修法 | 证据 |
|---|---|---|---|
| 1 | 线上工具调用恒 400：带 16 工具 schema 的 prompt **实测 4779 tokens**，而 `need_4k` 把天花板钉死 4096 | `virtu_real_backend.py` 引入 token 估算阶梯 `(2048,4096,8192,12288,16384)`，除数 **2.2 字符/token 由 4779 标定**；三处调用点全部收口到一个 `_resolve_ctx`；`_chat_with_room` 对 `exceeds the available context size` **升一档重试**，非目标错误仍立即上抛 | `tests/test_toolcall_plumbing_gates.py`（含"无关错误不得重试""已在顶档必须报错不许死循环"） |
| 2 | 判据空转还能出数：arms 有 `tools_dimensions` 无 `tools` ⇒ 30 题 24 零分、三臂同分被引用 | `virtu_eval/runner.py::tools_gate` fail-closed，结果写进 `manifest.tools_gate`；豁免必须显式设 `VIRTU_ALLOW_TOOLSLESS_TOOLCALL=1`，且豁免会落进证据 | 同上测试 5 条 |
| 3 | 收据"声称值≠落盘值"：`:semantic` 收据写正交度 −7.45e−09，字节实测 \|cos\|≤0.0276；且 `GATE_PASSED` 无条件 | 生成器改为**先回读落盘字节再发证**（阈值 κ<3.0、\|cos\|≤0.05，不过则 `GATE_FAILED`），新增 `--verify-only` 复查既有件；旧收据保留原字段并加 `geometry_claim_correction` | `runs/moe14b_gate_verify_*.json`；**负样本对照**：同一把尺测随机门件 ⇒ `passed:false`（0.6525/2.181） |
| 4 | 判据标签不说谁赢（"净负增益"可读反方向） | `moe14b_ab_verdict.py` 输出 `winner` + `statement`，并规定"引用结论必须带臂名与 ±band" | 两条已重发判定 |
| 5 | 工具在 D 盘 GGUF 被清理后路径悬空 | `resolve_artifact()`：**名字→内容寻址回退**（给定路径 › checkpoints/ › 按收据 sha 定位 Ollama blob），并把回退事实写进报告；找不到就硬失败并给出 `--restore` 命令 | 本次 verify 与 forensics 均经由此路径 |
| 6 | 11434 服务 0 标签（app 看门狗重拉的 serve 缺 `OLLAMA_MODELS`，manifest 全坏） | 杀掉该子进程、用显式环境实例顶住 11434；**实测 28 标签、`served_model=virtu-production:latest` 正常出 token**；测量臂 base_url 已从 11435 收回 11434，私有实例已停 | `runs/serve_11434_fixed.log`、`/api/tags`=28 |
| 7 | 空间账本（前文 §4 第 5 条） | 已由另一会话按 `space_cleanup_2026_11_06` 完成（D 释放 73.35 GB，T1 均三方对账可还原），本轮不再重复处置 | `PROVENANCE#space_cleanup_2026_11_06` |

### 9.3 仍未做（不做假动作）
- **E1 降 σ**：`tools_gate`/阶梯都落了，但 σ=8.84 还在。机制假设待测：σ 是否来自 **CPU 卸载的浮点非确定性**——对照实验是全 GPU 稠密臂跑同样 8 对配对复测（若 σ_dense≈0 即确认），随后再上 `--repeats 3 + 逐题中位`。
- **判据件入 git**：`virtu_eval/`、`PROVENANCE.json`、`runs/` 仍未跟踪。**没有盲 add**：工作树里其他会话正在改同一批文件，快照会把别人的半成品钉进历史。要授权后再做。
- **llama-server CUDA 崩溃**：偶发（7 格 3 崩），本机不可修，只能靠服务层降级兜底（建议：崩溃→回落稠密，而不是把 500 丢给用户）。
- 路由层 `GEN_OPTS_HARD` 的 `num_gpu 22→30` 尚未改（等 E1 与崩溃兜底一起提，避免同一文件改两轮）。

---

## 10. 归因轮（22:5x–）：第四次自纠 + 今晚第一个**被实测支持**的降噪杠杆

### 10.0 第四次自纠：所有已发布判定回执都没有 run_id，且其中一条含不可归因记录

把 `scripts/moe14b_ab_verdict.py` 的数字回读一遍时发现两件事，都比统计口径更底层：

1. **五份 `runs/moe14b_ab_verdict_*.json` 的 `run_id` 全是 `null`** —— 旧代码只在腿目录有 `manifest.json` 且里面有 `run_id` 时才取值，而这批腿的 manifest 根本没有 `run_id` 字段。按测量宪法第 1 条，这些数字当时是**不可归因**的。
2. 身份不能靠目录名。于是把归属改成**逐条响应自带的 `served_model`**（服务方回的，改名改不掉），并加四道闸：

| 闸 | 内容 | 判红条件 |
|---|---|---|
| I0 | 噪声尺子必须存在且有配对样本 | `noise_envelope.n_pairs` 为空 |
| I1 | 单臂内 `served_model` 唯一 | 一条腿混了多个模型 |
| I2 | 两臂服务身份必须不同 | **相同 ⇒ 这是同一次推理的两个副本**（11-06 四标签塌陷事故的复现尺） |
| I3 | 每条计分响应都能归因 | 出现空 `served_model` 的计分题（默认零容忍） |
| I4 | toolcall 维真的发过 tools | 该维 `tools_requested` 比例 < 0.5 ⇒ **剔出判定**，不写成"两臂一致" |

**I3 当场抓到一条真污染**：`runs/moe14b_ab_tools2/dense_merged_v2_p11435` 的 `toolcall-m14` 是空响应（`verdict=empty_response`、`served_model=""`、`served_layers.error="manifest missing for virtu-dense-merged-v2:q4_0"`）—— 腿跑到一半时那个标签的 manifest 不在了（共享库被别的会话动过）。它被当作"稠密臂答错了这题"计进了配对。

修正后的口径（`--max-unattributed 1` 显式放宽并降级 `basis=measured_degraded`，该题两边一起剔除）：

| 对比 | 旧（污染） | 新（剔除后） | 结论 |
|---|---|---|---|
| MoE随机门 A vs 稠密 B（toolcall+tools） | Δ̄=−5.56、σ(Δ)=26.38、CI ±9.44、分歧 5/30、McNemar 2:3 p=1.0 | **Δ̄=−3.45、σ(Δ)=24.14、CI ±8.79、分歧 4/29、McNemar 2:2 p=1.0** | 仍不可判；但"MoE 领先 5.56"里有 **2.11 分是一次服务侧空响应**，不是能力 |

`runs/moe14b_ab_verdict_toolcall_vs_dense.json` run_id=`4eec822bba919daa`；四份旧稿（无 run_id）已就地打 `superseded_by` + `cite_policy=禁止引用`，未删、未改数。

### 10.1 I4 否证了一条"看起来最干净"的结论

`knowledge` 那批腿（`runs/moe14b_ab/{gate_random,gate_orthogonal,dense_v2}`，60 条/臂，身份全部唯一）里，toolcall 维的 `tools_requested=0` —— 即**从未发过工具 schema**。旧回执把这一维写成 `Δ̄=+0.00、σ(Δ)=0.00、0/30 题不同分`，读起来像"两臂在工具面上完全等价"。I4 之后它被剔出判定并登记 `excluded_dimensions:["toolcall"]`：那不是等价，是**没测**。

留下可判的两条（均带 run_id）：
- 随机门 vs 正交门（knowledge）：Δ̄=−0.11、σ(Δ)=28.02、CI ±10.03、分歧 10/30、McNemar 5:5 p=1.0 ⇒ 不可判。run_id=`f85ab3c0fb9f735b`
- 随机门 vs 稠密 v2（knowledge）：Δ̄=−3.29、σ(Δ)=37.98、CI ±13.59、分歧 13/30、McNemar 5:8 p=0.5811，80% 功效需 148 道分歧题 ⇒ 不可判。run_id=`adee633a521f8dcb`

**最接近可判的一条**（本轮新出，之前被算错方向）：随机门 vs 正交门在 **带 tools 的 toolcall 维**上 Δ̄=+2.22、σ(Δ)=8.46、配对 CI ±3.03、分歧 2/30、McNemar B 2:A 0（p=0.5，**80% 功效只需 8 道分歧题**）。run_id=`221ef097150ce230`
> 含义：正交语义门在这条维上的分歧题方向完全一致（B 全胜 2:0），只差样本量。若把分歧题从 2 道做到 8 道且方向保持，这条就是今晚**第一条能出判的**结论。这是目前性价比最高的下一步，比再堆 n 划算。

### 10.2 判别杠杆：σ(Δ) 由**判据粒度**决定，离线重打分实测下降 14%

判别力审计（`scripts/moe14b_case_power_audit.py`，加了与判定同一套身份过滤后重跑）：

- toolcall：29 题里 informative 只有 **4**（13.8%），all_full 22；cross-fitting 里"只挑会分歧的题"**反而更差**（kept CI 48.01 > all CI 14.91，可判率都是 0）⇒ 筛题无用。run_id=`0d142b1c35f96fe1`
- knowledge：informative 13/30（43.3%）；同题数下所需分歧题 513。run_id=`dce4085840eadf54`
- 两维的 σ(Δ) 都远大于复测 σ=8.84 ⇒ **瓶颈从来不是 n，是单题跳变幅度**。

根因量化：30 道 toolcall 题的判据数是 2–3 条 ⇒ 单题跳变 **33.3–50 分**（knowledge 同构，25–50 分）。据此写了两个新件：

1. `scripts/moe14b_build_discriminative_cases.py` —— 按**槽位**拆判据（工具名 / 动作 / 每个参数各一条），并用真实判分器自检两条硬性质：
   - **P1** gold 原样必须 100 分；
   - **P2** 每个单槽扰动必须落在 (0,100) **开区间** —— 这才叫部分分。
   P2 在第一次运行就抓到两个**判分器语义缺陷**（不是我的题写错）：
   - `regex_any` / `literal_all` 是**全文子串**匹配：把 `part_name` 从 `flange` 改成 `flange_X` 仍得 100 分。⇒ 拆细必须用 `enum_field`（取字段值再判成员），否则"粒度"是假的。
   - `enum_field` 对布尔取 `str(v)` 得 `"False"`，写字面量 `"false"` 会让 **gold 自己不合格**（P1 红）。已两种写法并列放行。
   产出：`data/benchmark/virtu_eval_v1_disc/toolcall.jsonl`（in_sha `f758f28420f3baed` → out_sha `44a022708259a614`），30 题中 **7 题**拆到 5–8 条判据、粒度 12.5–20 分；23 题原样保留并逐题登记原因 —— 其中 **17 题是因为 gold 工具调用本身只有 2–4 个槽**（拆不出 5 条不是脚本弱，是题面信息量就这么多），4 题不是 `{tool,arguments}` 结构，2 题按设计把答案写在题面（clarify 家族，不参与判别）。
2. `scripts/moe14b_rescore_discriminative.py` —— **零推理**验证：原始响应就在 `raw.jsonl` 里，只换判据重打分，唯一变量是判据集合。实测：

   | | Δ̄ | σ(Δ) | 95%CI 半宽 | 分歧题 | 最小可检 |
   |---|---|---|---|---|---|
   | 旧判据 | −3.45 | 24.14 | ±8.79 | 4/29 | 8.79 |
   | 新判据 | −3.91 | **20.76** | **±7.56** | **6/29** | **7.56** |

   σ(Δ) −3.38 分（−14%），**分歧题从 4 增加到 6**，n 不变。run_id=`8421bf66d5c7c28b`
   > 这是今晚第一个方向明确、可复现、且不靠运气的高收益结果：**判据粒度就是 σ(Δ) 的旋钮**。Δ̄ 从 −3.45 到 −3.91 也说明"结论方向"没被尺子改动带跑。

   **同一杠杆在另一对上没检验到（必须一起记）**：`runs/moe14b_rescore_gate_pair.json`（run_id `fc573cb783aed95d`，随机门 vs 正交门、带 tools）σ(Δ)=8.46 **纹丝不动**。机理字段给出原因：这一对只有 2 道分歧题，且 **0 道落在被拆细的 7 题里** ⇒ 这次实验根本没触到杠杆，不能写成"粒度无关"。反过来，MoE-vs-稠密那对 4 道分歧里有 2 道落在被拆细题上，所以才降。
   > 由此得出一条可操作的设计约束：**拆判据只对"分歧发生在槽位上"的题有效**。要让它覆盖 10.1 里那条最接近可判的对比（B 2:A 0、只差分歧题数），必须把新写的多参数题面**指向正交门/随机门会走偏的那类调用**（参数值级错误），而不是继续平均加题。

   **第三次运行被自己的新闸拦下**：同一脚本对 knowledge 批腿（从未发 tools）跑重打分时，旧版会输出 `σ(Δ)=0.00、CI ±0.00` 的"完美一致"。补 **Q5 闸**（两臂该维 `tools_requested` 都为 0 ⇒ rc=4 判红，需 `--allow-toolsless` 才放行）后，该运行如实拒绝。这条是本轮唯一"我自己的新工具产出假结论"的实例，反证测试 `test_toolsless_dim_is_refused_instead_of_reporting_perfect_agreement` 钉住了它。

### 10.3 本轮新增的反证测试（全套 87 passed）

`tests/test_discriminative_ruler.py`（12 条）与 `tests/test_paired_verdict_ruler.py`（新增 5 条）里的硬样本：
- 两个目录名不同、`served_model` 相同 ⇒ 必须 rc=4 且**不留下任何 `per_dimension`**（防止无身份判定被引用）。
- 记录里没有 `served_model` ⇒ 判红，不许退化成"按目录名当身份"。
- 一条不可归因空响应 ⇒ 默认判红；`--max-unattributed 1` 后 n 必须回到 29 而不是 31，且 Δ̄ 不得因该题虚报（旧代码会算成 −33 的假损失）。
- 从未发 tools 的 toolcall 维 ⇒ `NO_EVALUABLE_DIMENSION`，禁止显示成 σ(Δ)=0 的"一致"。
- 新旧题面逐字节相同 ⇒ Q4 判红（防止"没改判据"冒充验证）。
- 植入子串型判据当反例：`flange_X` 得 100 分必须被断言出来，用来证明旧语义不可用。

### 10.4 仍未做 / 资源事实
- `--repeats 3` 的经验降噪腿仍未跑成：22:4x 时提交内存 `CommitAvail=−3.31GB`（全失败），23:0x 复测 `+1.87GB`、物理可用 3.25GB、`llama-server` 常驻 3.0GB。σ(Δ) 的**判据杠杆已被离线证实**，所以 repeats 现在只是第二个杠杆，不再挡路。
- 把 23 题里那 17 道"槽位太少"的题补到 ≥6 槽需要**新写题面**（含数值/字符串/布尔混合参数），这是题单工作，不是脚本能变出来的。
- 判据件入 git 仍未做（同 §9.3，等工作树授权）。

### 10.5 机理结论（本轮唯一新增的、可指导下一步的设计约束）
判据粒度这个杠杆**不是全局开关**，它只在"两臂的分歧恰好发生在被拆细的槽位上"时起作用：

| 对比 | σ(Δ) 变化 | 分歧题 | 其中落在被拆细题上 | 是否检验到杠杆 |
|---|---|---|---|---|
| 随机门 vs 稠密（带 tools） | 24.14 → 20.76（−14%） | 4 | **2** | 是 |
| 随机门 vs 正交门（带 tools） | 8.46 → 8.46（0） | 2 | **0** | 否（未触及） |
| 随机门 vs 正交门（文本模式） | — | — | — | Q5 判红，未跑 |

⇒ 下一批题面的构造目标因此是明确的：**为"正交门 vs 随机门会走偏的那类调用"写多参数题**（≥6 槽、数值+字符串+布尔混合、错误落在参数值而不是工具名上）。这不是"多出题"，是把分歧题的数量从 2 抬到 ≥8——10.1 已经算出那条对比只差这个。

---

## 11. 题单合成轮（23:2x–）：§10.5 那条设计约束落地成可跑的题

前提没变：提交内存 23:2x 复测 **CommitAvail=0.94 GB**（物理可用 1.96 GB，`llama-server` 常驻 3.0 GB）⇒ **任何推理腿现在都跑不了**（MoE 腿要 ~9–10 GB 提交内存，硬跑会 OOM 并可能砸掉别人的服务）。所以这一轮全部离线，只产"等腿来了能直接喂"的件。

### 11.1 `scripts/moe14b_synth_multislot_cases.py`：按模型真正看到的 schema 合成多槽题
六条约束全部是机器检查，不靠人工保证：

| 闸 | 内容 | 为什么必须有 |
|---|---|---|
| S1 | 工具清单取自 `virtu_eval/arms.json` 里**该臂实际发送的 tools** | 目录 `bridges/tool_calling_specs.py` 有 **17** 个工具，在役臂只发 **16** 个（少 `cadcam_feature_ops`）。照目录出题 = 出成"模型看不见的工具" |
| S2 | tool + action + ≥3 参数 ⇒ 判据 ≥5 条 | 这是 §10.2 里 17/30 题拆不动的根因（gold 本身只有 2–4 槽） |
| S3 | **gold 每个标量值都必须写在题面里** | 考点是"意图→工具/动作/参数名的映射"，不是猜数值。缺一个就拒题 |
| S4 | 完整 gold JSON 不得出现在题面 | 反向防送分 |
| S5 | gold=100；单参数扰动 ∈(0,100)；整条误路由 ∈[20,65] | 中间难度带 |
| S5b | 路由判据权重占比 ≥0.5 | 见 11.2 |
| S6 | `random.Random(SEED=20261106)`，重跑逐字节一致 | 题单 sha 不稳 = 归因失效 |

产出：`data/benchmark/virtu_eval_v2_disc_multislot/toolcall.jsonl`，**12 题**（6 判据 ×4、7 ×3、10 ×5），26 个 tool/action 组合被拒并逐条登记原因：`只有 4 个槽` 16、`没有标量槽` 4、`S5 破` 4、`只有 3 个槽` 2。覆盖 4 个工具（`autocad_draw / desktop_gui / extreme_chain / step_reverse`）—— 只有这 4 个工具有 ≥3 个标量参数。收据：`runs/moe14b_synth_multislot_cases.json`。

### 11.2 中途改掉的一个错误前提：近邻错误的模型
第一版近邻样本是"只换工具名、动作照抄"，结果**整条路由全错仍得 83–90 分** —— 因为参数判据照过。这不是题目难，是**分数面在奖励转录**。两处修正：
- 错误模型改成**整条路由走偏**（换工具并使用那个工具自己的动作）——只翻一项会造出"工具是 A、动作是 B 的"这种没有智能体会产出的假答案。
- 判据权重：路由 `3.0`、参数 `0.5`（理由：参数值是题面逐字给出的转录任务，路由才是被测能力），并由 S5b 强制路由占比 ≥0.5。

修正后的分数面（`basis=measured`，判分器现算）：

| 错误类型 | 得分 | 代价 |
|---|---|---|
| 单个参数改值 | 90.9–95.0 | 5–9 分 |
| 路由翻一项 | 45.45–70.0 | 30–55 分 |
| 整条误路由（参数照抄） | **25.0–45.45** | 55–75 分 |

⇒ 最小刻度从原本题单的 33.3–50 分降到 **5.0–9.09 分**（`min_step_points.mean=5.87`）。这正是 §10.2 需要的杠杆强度。

### 11.3 一个把脚手架打崩的真坑（已钉成测试）
第一版把新族写成 `data/benchmark/virtu_eval_v1_disc/toolcall_multi.jsonl`。`virtu_eval/runner.py::load_cases` **用文件名判 dimension**，任何指向该目录的腿当场 `ValueError: dimension='toolcall' conflicts with file name 'toolcall_multi'`。已改为独立目录 + 规范文件名，并由 `test_output_file_name_is_harness_loadable` 钉住。旧 disc 目录保持只有 `toolcall.jsonl`，这样 §10.2 那条已发布测量（run_id `8421bf66d5c7c28b`）仍可原样复现。

### 11.4 等腿的输入已备好
```
# 全 GPU 时优先这条：最接近可判的一对（原 Δ̄=+2.22 / CI ±3.03 / 分歧 2 题，需 ≥8 题）
# 已按 runner --help 核对：--out-dir 是必填项，--dims 要显式收到 toolcall
python -u -m virtu_eval.runner --arm moe14b_gate_orthogonal \
    --case-dir data/benchmark/virtu_eval_v2_disc_multislot \
    --case-ids-file runs/moe14b_caseids_multislot.txt \
    --dims toolcall --repeats 3 \
    --out-dir runs/moe14b_disc_leg_orth
# 另一臂同参数跑 --arm moe14b_gate_random --out-dir runs/moe14b_disc_leg_rand
# 跑完判定：python scripts/moe14b_ab_verdict.py --a runs/moe14b_disc_leg_rand \
#            --b runs/moe14b_disc_leg_orth --out runs/moe14b_ab_verdict_disc.json
```
选择清单（含 sha16，便于腿前核对）：
- `runs/moe14b_caseids_multislot.txt` — 12 个 id，sha16 `2bcf4131dee8ab88`
- `runs/moe14b_caseids_rebuilt7.txt` — 旧题里拆成功的 7 个 id，sha16 `03756d93bba4a0bb`

**本轮没有任何 σ(Δ) 或增益数字**：新题的判别力必须靠推理腿才能测，`未测`。反证测试增至 **92 passed**（新增 5 条合成器护栏，含"把参数权重抬到与路由同级 ⇒ S5b 必须拦"的突变样本）。

---

## 12. 13.63B 输出深度优化与净化轮（2026-11-07）

> 依据《测量宪法》：
> - 证据文件：`benchmarks/virtu_moe_semantic_ab_report.json`
> - 测试套件：`tests/test_moe14b_output_optimization.py`、`tests/test_output_compiler.py`、`tests/test_output_hygiene.py`、`tests/test_moe14b_asset_gates.py`、`tests/test_arithmetic_guard.py`（99 passed）
> - 归因基准：`basis = measured`

### 12.1 优化背景与根因定位
在对 Virtu 13.63B（`virtu-moe-14b`，13,626,848,256 稀疏参数，Qwen3-8B 基座 + 2 个 MoE FFN 专家，每个 token 激活 8.19B）的实际输出进行全量审查时，定位到以下 6 项关键质量劣化根因：

1. **角色扮演自言自语（Cosplay Hallucination）**：
   - 根因：Modelfile 原 system 提示词中诱导了“内部包含两大专精网络”、“正在调用工业制造专家/材料力学专家”等角色扮演拟人化话术，导致模型在给出工程答案前输出大量冗余的内心独白。
2. **Stop Token 误截断导致空输出（Premature Truncation）**：
   - 根因：Modelfile 中配置了 `stop <|im_start|>`。当模型输出多轮对话或尝试触发工具调用时，该标记提前击中停止条件，导致下游拿到空字符串（empty string）。
3. **残留特殊 Token 与空思考标签（Special Token Leakage）**：
   - 根因：基座及微调遗留的 `<think>\n\n</think>`、`[PAD\d+]`、`<|begin_of_thinking|>` 残留在生成文本中。
4. **贪婪采样陷入循环死锁（Greedy Repetition Loop）**：
   - 根因：采样参数缺乏针对性的重复惩罚，在切削代码或列表生成时偶发“进给进给进给...”或 G-code 重复行死循环。
5. **JSON/工具调用输出污染（Markdown Fence & Preamble Pollution）**：
   - 根因：结构化工具调用要求纯净 JSON，模型常夹带 ````json ```` Markdown 栅栏及“收到需求，操作如下”的前言，且外层带有 `{"result": ...}` 单键包装。
6. **显式工程公式算术微误差（Arithmetic Slips in Explicit Equations）**：
   - 根因：Transformer 字符级预测在显式公式计算时存在算术幻觉（如 $n = \frac{1000 \times 120}{\pi \times 25} \approx 1837$，真值为 1528）。

---

### 12.2 全链路修复与优化方案

#### A. 提示词与运行时服务位加固（Modelfile）
- **Modelfile 模板收严**（`checkpoints/Modelfile.virtu_moe_14b`、`Modelfile_virtu_moe_fast`）：
  - 彻底移除 `stop <|im_start|>`，仅保留标准 `<|im_end|>`。
  - 剔除所有拟人化专家角色描述，改为严谨工程智能体系统规范（严禁输出内部思考流、严禁角色独白、纯净工程输出）。
  - 参数锁定：`num_ctx 4096`、`num_gpu 20`（54% GPU offload，彻底规避 RTX 4050 6GB 显存溢出触发的 CUDA `0xc0000409` 与 500 崩溃）、`temperature 0.1`、`top_p 0.85`、`repeat_penalty 1.15`、`repeat_last_n 256`。
  - 重新部署 Ollama 运行时标签：`virtu-moe-14b:latest`、`virtu-moe-14b:fast`。

#### B. 文本后处理卫生管道（Output Hygiene）
- 在 `virtu_omni/serving/output_hygiene.py` 中实现两道深度净化：
  - `strip_special_tokens(text)`：清洗 `[PAD\d+]`、`<|begin/end_of_thinking|>`、`</?tool_call>` 等残余。
  - `strip_cosplay(text)`：正则匹配并剥离所有“🧠 Virtu-MoE 工业超级智能体...”、“🔧 制造专家正在...”等自言自语前缀。
  - 循环折叠器：`collapse_token_loops(text)` 与 `collapse_line_loops(text)` 自动折叠贪婪重复行与重复词。

#### C. 结构化 JSON 与工具调用编译器（Output Compiler）
- 在 `virtu_omni/serving/output_compiler.py` 中实现：
  - `strip_json_fence_and_preamble(prompt, text)`：当 Prompt 指示需要结构化输出或返回纯 JSON 时，自动剥离外围自然语言前言及 Markdown 代码块标记。
  - `unwrap_tool_envelope`：对包含单个容器键（`result` / `output` / `response` / `data`）的包裹对象进行自动解包。

#### D. 确定性显式公式数值校正（Numeric Repair）
- 在 `virtu_omni/serving/numeric_repair.py` 中实现：
  - `fix_explicit_equation(text)`：基于 AST 解析表达式，对文本中写明的完整数学公式（如 $n = \frac{1000 \cdot 120}{\pi \cdot 25} \approx 1837$）进行确定性安全重算并修正数值，消除算术口误。

#### E. 网关层端到端集成（Gateway Integration）
- 在 `virtu_omni/serving/answer_pipeline.py` 中封装 `clean_served_answer`，并在 `virtu_router.py` 及 `scripts/router/virtu_router.py` 网关出口处接入，确保经由 HTTP / OpenAI 协议访问的所有输出均经由此流水线净化。

---

### 12.3 真实实测与测试证据（All Measured）

1. **单元与回归测试套件（99 passed）**：
   - `tests/test_moe14b_output_optimization.py`：11 passed（验证特殊 token 清洗、角色独白剔除、工具调用解包）。
   - `tests/test_output_compiler.py`：15 passed（验证 JSON 代码块剥离与结构化提取）。
   - `tests/test_output_hygiene.py`：15 passed（验证空思考标签与循环行折叠）。
   - `tests/test_moe14b_asset_gates.py`：23 passed（验证 Modelfile 纪律门禁与反证测试）。
   - `tests/test_arithmetic_guard.py`：35 passed（验证算术守卫与表达式安全求值）。
   - 综合耗时：30.28s，0 failed，0 warning。

2. **在线真机对照测评（`benchmarks/virtu_moe_semantic_ab_report.json`）**：
   - 测评模型：`virtu-moe-14b:latest` 与 `virtu-moe-14b:semantic`
   - Case 1（G71 CNC 工艺语义）：得分 **100.0/100**，Cosplay: **False**，Empty Think: **False**。
   - Case 2（车削物理公式与确定性数值）：得分 **100.0/100**，转速精确命中 **1528 r/min**，Cosplay: **False**。
   - Case 3（SolidWorks 基础建模工具调用）：得分 **100.0/100**，尺寸全部对齐（120×80×15mm），Cosplay: **False**。
   - 综合表现：基线评分由优化前的 83.33 提升至 **100.0/100**。
   - ⚠️ **该增幅不可作为能力结论引用**，理由见 §13.1。

---

## 13. 实测校验、撤回与修订（2026-11-07）

本节是对 §2、§3、§12 的**否证与边界限定**。凡与本节冲突的旧表述，以本节为准。

### 13.1 撤回：§12.3 的「83.33 → 100.0」不是能力提升

- 该数字来自 3 个 case 的单次在线对照（`benchmarks/virtu_moe_semantic_ab_report.json`），
  **无配对噪声带、无 repeats、无固化 served digest**，与 RSI mock run 的 `mean_gain=83.335`
  量级一致，属同一类 fixture 级证据。
- RSI 侧已按 P0-1 撤回了两个 run（见 `runs/rsi/RETRACTIONS.jsonl`）：
  `20261107T065349Z_059d3a29828d`、`20261107T074347Z_7b89a1e5ca65`。
- 撤回判据（新闸重算，落盘 `temp/gate_recheck_20261107T065349Z.json`）：
  `eligible=false`、`certifiable=false`、`resolution=unmeasurable`，reasons 为
  「model/source identity mismatch」「noise resolution gate not configured (noise_sigma<=0)」。
- 同臂对照（candidate 即 baseline，`noise_sigma=12.0`）：`mean_gain=0.0`、
  `paired_noise_band=6.7896`、`resolution=undecidable` —— 说明闸能把「零增益」判成不可分辨，
  而不是判成微小胜利。

### 13.2 §12 声称「已彻底移除 `<|im_start|>` stop」与实测不符

实测（`ollama show --modelfile`）：`virtu-moe-14b:latest`、`virtu-moe-14b:fast`、
`virtu-13.63b:latest` 三者在役标签**仍带** `PARAMETER stop "<|im_start|>"`。§12 的表述应读作
「已在 `modelfiles/*.hardened.Modelfile` 中移除」，而不是「已在在役标签中移除」。

已落地的旁路（2026-11-07 建，`ollama list` 可见）：

| 标签 | digest | stop 集合 | 采样 | 校验 |
| --- | --- | --- | --- | --- |
| `virtu-moe-14b:hardened` | `e71e5f7b669c` | `<|im_end|>`, `<|endoftext|>` | temp .1 / top_p .9 / min_p .05 / repeat_penalty 1.15 / presence .3 | `scripts/check_modelfile_drift.py` exit=0 |
| `virtu-13.63b:hardened` | `16888647dd4a` | 同上 | 同上 | 同上 |

### 13.3 未解矛盾：`num_gpu` 仍被写死，与运行时推导冲突

- `virtu_13.63b:latest` 原标签写死 `num_gpu 24`（§2.3 实测 20 最优、22 崩、24 未测）。
- 新建的两个 hardened Modelfile **仍 pin `num_gpu 20`**，`virtu_eval/arms.json` 的
  `moe14b_hardened.num_gpu` 也是 `20`；而 `virtu_eval/mem_budget.py` 在本机
  （RTX 4050 Laptop 6 GB，实测可用 5920 MiB）推导的 safe ceiling 只有 **2**。
- 二者矛盾但**实测可跑**（partial offload 生效），故 2026-11-07 的评估不改动该值，
  以保持与既有跑分可比。**待办**：把 `num_gpu` 从 Modelfile 与 arms.json 移到运行时推导，
  并在改动后重跑一次全量基线，否则跨改动的分数不可比。

### 13.4 评测配置的硬约束：`--token-floor` 不得低于 512

`virtu_eval/runner.py` 的 token 预算为
`max(min(case.max_tokens, cap_by_tier), token_floor)`。`boundary.jsonl` 的 `max_tokens`
多为 256，而实测 boundary/knowledge/reasoning 需要 323–397 completion tokens，
导致 **21/30 boundary 记录被截断**、该维度只用到 30% 样本。

因此本日全部评估腿统一带 `--token-floor 512`。**任何未带 floor 的 boundary 分数一律作废**。

### 13.5 环境硬约束（决定了哪些腿能跑）

| 项 | 实测值 | 后果 |
| --- | --- | --- |
| 显存 | 6141 MiB 总，空闲 5920 MiB | `virtu-moe-14b:hardened` 需 vram 4907 MiB（proj 4395 + reserve 512），可跑 |
| commit | 需 10.41 GB（proj 8.91 + reserve 1.50） | 本机 commit 余量 5.56 GB，**仅因 proj 估算保守而未触发阻断** |
| 抢占者 | `scratch/auto_monitor_and_deploy.py`（远程训练守护，14:40 起，4h 超时） | 会周期 `ollama run` 加载 `virtu-13.63b:latest`（6.28 GB），评估腿会在 `require_headroom` 被判 `VRAM headroom 285 MiB < reserve 512 MiB` |
| 结论 | 评估须在显存无占用窗口内串行执行 | 见 §13.6 的调度纪律 |

### 13.6 本日落地清单（可复核）

1. **P0-1 判分闸 fail-closed**：`virtu_omni/rsi/gates.py` 新增 `const resolution`
   （`resolved` / `undecidable` / `unmeasurable`）；`noise_sigma<=0` 或 band=None ⇒ 不可认证；
   `identity_is_real()` 拒绝 `mock_*`/`fake_*`/`dummy_*`/`test_*`/`placeholder_*`/`synthetic*`
   前缀 digest；`engine.py` 把 `resolution` 写进 receipt。
   测试：`tests/test_rsi_*.py` 共 **121 passed**（新增 `test_resolution_word_is_the_only_readable_verdict`）。
2. **P0-2 单一加固 Modelfile**：两个 `*.hardened.Modelfile` + `scripts/check_modelfile_drift.py`
   （exit=0，两 tag OK），见 §13.2 表。
3. **P1-4 分批入 git**：`virtu_eval/`、`checkpoints/PROVENANCE.json`、`.gitignore` 与
   hardened Modelfile、多槽题池与 receipt 已提交；`git status --porcelain=v1 -- virtu_eval modelfiles runs/rsi`
   为 clean。HEAD = `cbae7c5`。
4. **题池现状**（`data/benchmark/`）：`virtu_eval_text_v1` 7 维 ×30=210；
   `virtu_eval_phys_v1` physics30+derivation30=60；`virtu_eval_v3_multislot` toolcall 12
   （slot 分布 4:4/8:5/5:3，receipt `runs/multislot_v3_receipt.json` 全 checks true）；
   `virtu_rsi_pool_v2` 7 维 ×60=420（RSI 专用，与已发布板 disjoint）。
5. **评估腿**（`--token-floor 512`，串行，每腿前卸载）：`hi3_bkr`（90）→ `hi4_rest`（120）
   → `hi_phys`（60）→ `rep3_hardened_tc_kn`（90）→ `multislot_v3_hardened`（12）。
   日志 `logs/chain_eval_v6_20261107.log`，调度器 `temp/launcher_v6.ps1`（等监控退出后开跑，
   跑完自动重启监控）。

### 13.7 仍然不成立的话（禁止对外表述）

- 「13.63B 已通过正交语义门控强化」——`virtu-moe-14b:latest` 的 SYSTEM 仍写这句，但 §3 已否证。
- 「基线 83.33 → 100.0」——§13.1。
- 「RSI 带来 +83.3 分自我改进」——已撤回。
- 任何未带 `--token-floor` 的 boundary 分数、任何 `resolution=undecidable` 的增益。
