# 训练完成后主力模型全面测评报告（2026-11-15）

**主测对象**：`virtu-vericut96:v2` — 2026-11-15 09:02:30 云端 SFT+DPO 训练 `COMPLETED`（SFT 2254 样本 / DPO 210 对 / final_loss 0.1511），17:44 本地融合部署。
**训练前基线**：`virtu-master-fixed:latest`。**横向对照**：`virtu-vericut-e:latest`、`virtu-six-software:v1`、原始基座 `qwen3:8b`。
**结构化证据**：`benchmarks/VIRTU_FULL_BOARD_2026-11-15.json`；原始响应全部落在 `runs/eval_full_board_20261115/`。

---

## 0. 结论（先看这一条）

**不建议把 `virtu-vericut96:v2` 直接推为生产主力。** 四个独立板块方向一致：

| 判据 | 主测 v2 | 训练前基线 | 差 |
| --- | --- | --- | --- |
| 通用 8 维题板加权分（n=28/臂） | **50.64** | 64.12 | **−13.48** |
| 24 案例领域关键词基准（n=24/臂, `slot_exact_v2`） | **31.60** | 39.24 | **−7.64** |
| 训练目标探针通过数（n=10/臂） | **6/10** | 7/10 | **−1** |
| 部署验收回执状态 | `PROBE_FAILED` | `PROBE_FAILED` | 未改善 |

其中训练目标探针的失败项含**致命安全语义**（VERICUT Auto-Diff 红色含义对调、FANUC G00 负 Z 快速扎刀）。方向性结论是"专项训练伴随通用能力回退，且核心工业安全知识未修好"；**样本量小、未做显著性检验，属方向性而非定论**。

---

## 1. 被测对象按内容寻址（§8.2）

| 标签 | `/api/tags` digest | 模型层 sha256 | 训练回执 |
| --- | --- | --- | --- |
| `virtu-vericut96:v2` | `cc70716d5f09…` | `4f2f8dd5a2860…` | GGUF/回执一致；adapter `fea8b4a4…`, dataset `e95bdd20…` |
| `virtu-vericut-e:latest` | `9d9f8aa57ee7…`（起链时） | `877b9fa521ac…` | 17:00 部署 |
| `virtu-six-software:v1` | `a4c03edb3af0…` | `d96938fbcb60…` | 15:20 部署 |
| `virtu-master-fixed:latest` | `cffbe5db4946…` | `2602f6fc0023…` | 训练前主力基线 |
| `qwen3:8b` | `500a1f067a9f…` | `a3de86cd1c13…` | 原始基座对照 |

**主测构件全程未变**（起链/收链 digest 一致），故本轮 5 个板块中除留出集外的成绩可归因于该字节。

**测量治理事件（重要）**：`virtu-vericut-e:latest` 在测量窗口内被外部会话**重指向**（`9d9f8aa57ee7…` → `92323c5d1dde…`，约 20:05）。本报告里该臂所有分数只归属起链时的旧构件，标签现已无法复现该构件。同期库中还新增 `virtu-vericut96:v3`、`virtu-six-software:v2`、`virtu-six-software:v3` 三个标签——起链时不存在，**本轮未测**，不纳入任何结论。

---

## 2. 闸门（§8.4 闸必须能被证伪）

| 闸门 | 结果 | 证据 |
| --- | --- | --- |
| 部署探针判据反证单测 | **10 passed** (18.44s) | `runs/eval_full_board_20261115/gates_phase.json` |
| 留出集 gold 判分自检 | **105/105 题判 100.0 分**，PASS | 同上 |
| 24 案例腿封缄 | `run_id=272de1cb84b1de5b`，120 条原始响应，传输错误 0 | `domain24/summary.json`, `domain24/raw.jsonl` |
| 通用题板 5 条腿完整性闸 | 5/5 `gate.valid=True` | `generic/summary.json`（各腿 run_id 见该文件） |

---

## 3. 板块一：训练目标探针（n=10/臂，`deploy_trained_adapter.py` 原判据，未改判据）

| 模型 | 通过 | 失败项 |
| --- | --- | --- |
| **`virtu-vericut96:v2`（主测）** | **6/10** | `vericut_autodiff_probe`(红色语义对调) · `vericut_coordinate_unit_probe`(缺坐标/单位隔离) · `lame_stress_probe`(缺 σθ=33.33) · `fanuc_g71_safety_probe`(G00 负 Z 扎刀) |
| `virtu-vericut-e:latest` | 7/10 | `sw_coordinate_probe` · `lame_stress_probe` · `vericut_autodiff_probe` |
| `virtu-six-software:v1` | 6/10 | `sw_coordinate_probe` · `lame_stress_probe` · `fanuc_g71_safety_probe` · `vericut_autodiff_probe` |
| `virtu-master-fixed:latest` | 7/10 | `lame_stress_probe` · `fanuc_g71_safety_probe` · `vericut_autodiff_probe` |
| `qwen3:8b`（基座） | 7/10 | `lame_stress_probe` · `vericut_autodiff_probe` · `vericut_coordinate_unit_probe` |

**读法**：`vericut_autodiff_probe` 与 `lame_stress_probe` **五臂全败（连原始基座也败）**，说明这是语料/基座层的系统性缺陷，不是某次微调引入，且 v2 的 SFT+DPO 没有修好它。v2 相对基线**新增**了 `vericut_coordinate_unit_probe` 失败（基线此项通过）——这是训练引入的回退。17:57 已生成 `vericut96_v3_dpo_repair.jsonl`（279 行 / 4 个修复家族：autodiff_triage、coordinate_unit_isolation、lame_closed_form、sw_plane_notation），说明项目侧已识别同一组缺陷，但该修复模型起链时尚未部署。

证据：`runs/eval_full_board_20261115/targeted_phase.json`（含每项失败 reason 与回答片段）。

---

## 4. 板块二：24 案例领域关键词基准（n=24/臂，5 臂共 120 条）

| 模型 | mean (`slot_exact_v2`) | median | tok/s | 旧口径均值（**inferred**） |
| --- | --- | --- | --- | --- |
| **`virtu-vericut96:v2`** | **31.60** | 0.0 | 21.54 | 69.45 |
| `virtu-vericut-e:latest` | 33.33 | 33.3 | 20.01 | 75.01 |
| `virtu-six-software:v1` | 31.25 | 0.0 | 21.20 | 59.72 |
| `virtu-master-fixed:latest` | **39.24** | 33.3 | 22.12 | 73.62 |
| `qwen3:8b` | **作废** | — | 9.95 | — |

**这个基准的绝对分不能当能力结论**：`slot_exact_v2` 把连续汉字串切成单个 token，候选「背吃刀」无法命中回答里的「每次切削的**背吃刀**量」，于是内容正确的回答被判 0。复核发现 **25/120 条属于"内容命中但精确槽位判 0"**；换成历史 `substring_any_v1` 口径，各臂分数上抬 28–42 分，且**两种口径的排序不一致**（精确口径基线第一，旧口径 vericut-e 第一）。因此这里只做同尺相对比较，且必须以 `run_id=272de1cb84b1de5b` 归档口径。
**另发现一处判据空转**：`run_domain_ab.py` 用 `/api/generate` 时，thinking 模型 `qwen3:8b` 的 24/24 条 `response` 全为空，却被记为 `verdict=scored` 并打 0 分——该腿已作废，不得引用为"基座 0 分"。建议给脚本补空回答判红。

证据：`domain24/summary.json`、`domain24/raw.jsonl`、`domain24_grader_sensitivity.json`（含 25 条逐题原句）。

---

## 5. 板块三：通用 8 维题板（每维 4 题 / n=28/臂，`virtu_eval.graders.score_case`）

| 维度 | 主测 v2 | 基线 | Δ |
| --- | --- | --- | --- |
| instruction | 91.7 | 91.7 | 0.0 |
| knowledge | 58.3 | 62.5 | −4.2 |
| reasoning | 57.6 | **74.3** | **−16.7** |
| generation | **22.5** | 58.8 | **−36.3** |
| boundary | 66.7 | 91.7 | **−25.0** |
| generalization | 37.1 | 50.7 | −13.6 |
| toolcall（纯文本 JSON 协议） | 16.7 | 25.0 | −8.3 |
| **加权总分** | **50.64** | **64.12** | **−13.48** |

其余三臂：`virtu-six-software:v1` 54.15、`qwen3:8b` 58.11、`virtu-vericut-e:latest` 52.93 —— **三个微调臂全部低于训练前基线**，与 11-15 早些时候 `eval_vericut_e_training_r2` 的通用防遗忘检查（65.42 → 54.49，−10.93）方向一致。生成/边界/推理三维是主要失血点。局限：每维 4 题、`max_tokens=384` 出现 `partial_truncated`，属方向性证据。

证据：`generic/summary.json` 与各腿 `raw.jsonl`（5 腿 run_id 分别 `b3718fc4…`、`96aae615…`、`708e60c7…`、`767a4dff…`、`af607f69…`）。

---

## 6. 板块四：健全性 / 原生工具调用（n=4/臂）

- 五个臂均能输出中文工程回答、能完成严格 JSON 格式题，无退化乱码或空转循环。
- 原生工具调用：v2 / vericut-e / master-fixed / qwen3:8b 均返回 `tool_calls`；`six-software:v1` 该探针未触发工具调用。
- **v2 的参数结构缺陷**：`p4_toolcall` 里 `action` 字段被嵌套成对象 `{"action": {"action": "create_parametric_part"}}`，而其余臂是扁平字符串；同时尺寸键名与题面不一致（`section_diameter` 代替 `d_hole`）。这会直接破坏下游工具 schema 校验。
- 吞吐：24 案例单流 20–22 tok/s（GPU 空闲时）；中途外部并发把空闲显存从 5.8GB 压到 1.8GB 时降至 0.25–6 tok/s，**速度数字受本机负载影响，不跨时段比较**。

证据：`runs/eval_full_board_20261115/sanity/*.json`、`domain24/summary.json`。

---

## 7. 板块五：去污染留出集（105 题）——**未完成，主测标「未测」**

| 项 | 状态 |
| --- | --- |
| 基线 `virtu-master-fixed:latest` 全量 105 题 | **measured：42.80 / pass@100 32.38%**（与 11-15 r2 报告 42.80 完全一致，可复现） |
| 主测 `virtu-vericut96:v2` | 写到 30/105（29 有效、1 条 TimeoutError），**仅覆盖 `setup_workoffset` / `tool_assembly` 两维**，样本严重偏斜 → **腿作废，不发布配对 delta** |
| 分层子集补跑（32 题、8 维全覆盖） | 脚本已就绪，但 Ollama 服务端阻塞，**未跑成，标「未测」** |

**唯一可引用的同题板历史对照**（另一模型、另一条腿，非本次主测）：`runs/eval_vericut_e_training_r2/comparison_report.json`，`run_id=3dcc89b28e586675`：基线 42.80 → `virtu-vericut-e:latest` **54.73（+11.93）**，但通用 sanity 65.42 → 54.49（**−10.93**）。即该训练范式在专项留出集上确有增益，代价是通用能力回退；**不能把 +11.93 记到 v2 头上**。

---

## 8. RCFA 与熔断（AGENTS.md §6）

- **现象**：留出集主测腿在 30/105 处停滞，随后 `/api/tags`、`/api/chat`、`ollama ps` 连续超时（25s / 120s / 20s 均无响应）。
- **根因**：测量窗口内另一会话并发部署并评测新模型（可见 `virtu-six-software:v3` 被加载、库中新增 3 个 v2/v3 标签），Ollama 服务被独占，GPU 空闲显存降至 ~1.8GB，推理退化为 CPU 为主并触发 180s 超时。
- **同构停滞已连续 3 次**，按 §6 触发熔断：停止重试、不再补写任何分数、留出集全量腿标「未测」；未改动任何判分器/用例/他人封缄腿，新增脚本仅为可复现资产。
- **恢复路径**：待 Ollama 空闲后执行 `.venv\Scripts\python.exe scripts\finish_holdout_subset.py`（分层 32 题、断点续跑），或重启服务后重跑全量 105 题腿。

---

## 9. 证据索引

| 内容 | 路径 |
| --- | --- |
| 身份快照 / 训练回执 / 判分器 sha256 | `runs/eval_full_board_20261115/identity.json` |
| 闸门、各板块 phase 汇总、链进度 | `gates_phase.json` / `*_phase.json` / `progress.json` |
| 训练目标探针明细 | `targeted_phase.json`、`targeted.json` |
| 24 案例封缄原始响应与判分器复核 | `domain24/raw.jsonl`、`domain24/summary.json`、`domain24_grader_sensitivity.json` |
| 通用 8 维 5 条腿 | `generic/summary.json`、`generic/<model>/raw.jsonl` |
| 健全性 4 探针 | `sanity/*.json` |
| 留出集原始响应 | `holdout/raw_baseline_holdout.jsonl`、`holdout/raw_candidate_holdout.jsonl` |
| 结构化汇总（每个数字带 n/evidence/run_id/basis） | `benchmarks/VIRTU_FULL_BOARD_2026-11-15.json` |
| 可复现脚本 | `scripts/run_full_board_20261115.py`、`analyze_domain24_grader_sensitivity.py`、`finish_holdout_subset.py`、`build_full_board_summary.py` |

---

## 10. 建议（按优先级）

1. **先恢复服务再补测**：Ollama 空闲后跑分层子集 / 重跑全量 105 题，把"训练是否真的带来专项增益"这块补齐；在此之前不要对外发布 v2 的留出集成绩。
2. **不要直接用 v2 上线**：至少先修 4 个训练目标探针失败项（尤其 Auto-Diff 颜色语义与 G00 扎刀），并给通用能力回退做回放语料（replay）或降权融合。
3. **v3 另起一轮**：`virtu-vericut96:v3` / `virtu-six-software:v3` 起链时不存在，需按内容寻址重新采身份、重跑同一套五板块；17:57 生成的 279 行 DPO 修复集正好覆盖本轮暴露的 4 个缺陷家族。
4. **修两处测量口径缺陷**：`run_domain_ab.py` 空回答判红；24 案例判分器升级为语义/子串混合并保留版本戳，否则绝对分持续低估 30–40 分。
5. **并发治理**：测量链期间禁止其他会话重部署共享标签（`virtu-vericut-e:latest` 本轮已被重指），否则同标签成绩不可比。
