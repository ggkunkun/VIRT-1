# Virtu 模型强化方案（2026-11-06 实测版）

> 对象：本机最新模型 `virtu-moe-14b`（13.63B 稀疏双专家 / Q4_K_M / 8.3GB）与同族稠密基线 `virtu-comprehensive`（8.19B / Q4_0 / 4.6GB）。
> 全部数字为本次实测（`/api/generate` 返回的 `eval_count`/`eval_duration`、GGUF 张量直读、safetensors 增量比对），`basis = measured`。
> 硬件边界：RTX 4050 Laptop **6,141 MiB** / 16.5GB RAM / 12 线程。

---

## 0. 一句话结论

**当前最大的强化空间不在"再堆参数"，而在三处"不花钱就能拿"的地方**：部署参数（2.5× 提速）、系统提示（消除人格化幻觉）、采样（消除重复退化）；结构层面唯一真缺陷是**路由从未训练**（证据见 §2），而两个专家本身是**真分工**（增量正交），所以不需要重训，只需把"逐 token 随机切换"换成"有意义的路由或干脆稠密化"。

---

## 1. 实测基线（同题：G71 的 U/R/F 含义）

| 配置 | 生成速度 | 显存/卸载 | 输出表现 |
|---|---:|---|---|
| `moe-14b:latest` 默认（ctx8192, num_gpu 22, temp .3） | **10.59 tok/s** | 8.3GB 权重，部分 CPU | 把系统提示的"双专家"当两个说话人 cosplay；只答了 U、R，漏 F |
| `moe-14b` + 中性 system + ctx4096 | 9.13–10.50 tok/s | 同上 | **答案正确**：U=背吃刀量、R=退刀距离、F=每转进给；仍带空 `<think>` 块 |
| `comprehensive` 默认（ctx8192） | 15.34 tok/s | 5.4GB，**24%/76% CPU/GPU** | 陷入「退刀退刀退刀…」重复退化；且 U/R 语义答错 |
| `comprehensive` + **ctx4096 + num_gpu 99** | **38.66 tok/s** | 4.7GB，**100% GPU** | 同上内容问题，但**速度 2.52×**、无空 think |
| `moe-14b` + ctx4096 + **num_gpu 99** | 5.68 tok/s ❌ | 8.3GB 塞不进 6GB，被迫回退 | 反而更慢 → **MoE 不要强推全量 GPU** |

两条可直接落地的结论：
1. 稠密 8.2B 在 `num_ctx=4096 + num_gpu=99` 下**全部进显存**，速度从 15.34 → 38.66 tok/s。
2. MoE 保持默认卸载（22 层）比强推 99 层快 **1.86×**。

---

## 2. 结构诊断：路由是假的，专家是真的

### 2.1 路由（`blk.N.ffn_gate_inp.weight`，2×4096）—— 从未训练

```
L 0: |r0|=1.0000 |r1|=0.9999 cos(r0,r1)=-0.6533 align_uni=(+0.8066,-0.8005) std/|mean|=0.7328
L18: |r0|=1.0000 |r1|=1.0000 cos(r0,r1)=-0.6500 align_uni=(+0.8055,-0.7990) std/|mean|=0.7358
L35: |r0|=1.0000 |r1|=1.0000 cos(r0,r1)=-0.6476 align_uni=(+0.8019,-0.8012) std/|mean|=0.7452
```

与构建脚本 `scripts/build_virtu_franken_moe.py:211-216, 249-252` 完全对上：

```python
router_base_0 =  torch.ones(4096) / sqrt(4096)
router_base_1 = -torch.ones(4096) / sqrt(4096)
proto_gate = stack([r0, r1]) + randn(2,4096)*0.01     # 每层再叠 randn*0.005
```

即门控 = **「全 1 向量 / 全 -1 向量」+ 1% 噪声，16 个专家槽位里只用了 2 个，且没有任何语义**。路由决策 ≈ 隐状态的全局符号，与"这是 CAD 问题还是力学问题"无关。
**业界口径**：mergekit-moe 文档明确 `random` 门控"**只适合之后还要再训练**（sparse upcycling）"，可用的免训练门控是 `hidden`（隐状态）与 `cheap_embed`（词嵌入）；并会对门控矩阵做条件数检查（阈值 5.0）来告警"专家区分度不足"。

### 2.2 专家（expert0 vs expert1）—— 增量近乎正交，是真分工

（总权重余弦 0.99976 是**假象**：基座占绝对主导，LoRA 增量本就只占 1% 量级。正确的比法是比增量。）

| layer | proj | ‖Δe0‖/‖W‖ | ‖Δe1‖/‖W‖ | cos(Δe0,Δe1) | ‖Δe0−Δe1‖/‖Δe0‖ |
|---:|---|---:|---:|---:|---:|
| 0 | gate_proj | 0.368% | 1.072% | **0.0022** | 3.08 |
| 0 | down_proj | 0.213% | 0.667% | 0.0014 | 3.28 |
| 12 | gate_proj | 0.459% | 1.307% | 0.0018 | 3.02 |
| 24 | gate_proj | 0.908% | 1.508% | 0.0067 | 1.93 |
| 35 | gate_proj | 1.006% | 1.549% | 0.0052 | 1.83 |

`cos(Δe0,Δe1)` 均值 **+0.0068**（≈0）→ 两个专家朝**正交方向**更新，确实承载不同能力（e0: 0.6·cad+0.4·tool；e1: 0.65·conv+0.35·ug）。
**所以问题不是"专家没差别"，而是"用一枚随机的硬币在逐 token 挑一个正交更新"**——这会造成同一段回答内能力被随机切换（也是 §1 里那两段"专家 cosplay"的上游原因）。

参考：MoE 合并研究测得合并后 **50.11% 的专家选择偏离原模型**，且误差随层数复合放大（16 层后 99.98% token 路由发散）；这说明路由质量对 MoE 是**一票否决级**变量，不能留空。

---

## 3. 强化清单（按"收益 ÷ 成本"排序）

### P0 · 零成本、当天可完成

| # | 动作 | 证据 → 预期 | 验收闸 |
|---|---|---|---|
| P0-1 | 稠密路径固定 `num_ctx=4096, num_gpu=99`；MoE 保持 `num_gpu=22` | 15.34 → **38.66 tok/s**（+152%），`ollama ps` 100% GPU | 三次重复测量 tok/s 波动 <10%；`ollama ps` PROCESSOR=100% GPU |
| P0-2 | 重写 system：删掉"内部包含两大专精网络/专家 1、专家 2"这类描述，改为"直接给答案，禁止描述内部分工" | 同一 prompt 从"专家 cosplay + 漏答"变为**一次答对 U/R/F** | 20 题抽检：出现"专家/正在执行以下步骤"字样的比例 = 0 |
| P0-3 | 采样加固：`repeat_penalty 1.15`、`presence_penalty 0.3`、`min_p 0.05`、`temperature ≤0.2` | 稠密模型的「退刀退刀…」死循环**消失**（复测通过） | 30 题无 >6 次的重叠片段；同题两次输出差异可解释 |
| P0-4 | 客户端剥离 `<think>…</think>`（预填模板实测**无效**，模型会自造空块） | 省 3–6 token/次，输出干净 | 返回体不含 `<think>`/`</think>` |

### P1 · 结构层（1–2 小时，纯本地、无训练）

| # | 动作 | 做法 | 预期 / 风险 |
|---|---|---|---|
| P1-1 | **重建门控（真语义路由）** | 方案 A（先做，便宜）：`cheap_embed` —— 用两套领域正/负样本（CAD/工具 vs 力学/理论）的 token embedding 均值构造每层 gate，纯查表、无需前向。方案 B（更强、更重）：mergekit-moe `gate_mode: hidden`，用 Qwen3-8B 对正负 prompt 取隐状态（`--load-in-4bit` 或 CPU），mergekit 文档称其为"最佳质量" | 门控与内容相关（可用"专家命中率 vs 题型"卡方检验）；风险：仍可能需要极短 SFT 才稳定（mergekit 原话：plain merge MoE 常 underperform） |
| P1-2 | **稠密化对照（最稳的强化）** | 把 Δe0、Δe1 用 TIES/DARE（density 0.5–0.7）合并回单稠密 FFN，输出 qwen3 稠密架构，再量化 Q4_K_M | 单模型 4.6GB → **全 GPU 38 tok/s**、砍掉 2× FFN 与路由风险；两套技能都保留。纯 numpy 合成 ~10 分钟 |
| P1-3 | **文档级路由（替代逐 token 随机）** | 用已装的 `nomic-embed-text`（274MB）做意图分类：快路径 → 稠密 38 tok/s；难题 → MoE 10 tok/s | 避免"一句话里换两次大脑"；成本几乎为零；可用 20 条标注验证分流准确率 |

**P1 的取舍建议**：先跑 P1-2（稠密化）。若 30 例域内题稠密 ≥ MoE，则**直接退役 MoE 的推理角色**、只留 BF16 作研究底座——这与"6GB 显存"的硬件现实最匹配。若 MoE 明显更强，再做 P1-1 修门控。

### P2 · 数据与输出确定性（需要一点工程量）

| # | 动作 | 理由（实测） |
|---|---|---|
| P2-1 | 建 300 条**可验证** CNC/G 代码 QA（FANUC/Siemens 双方言），先做 RAG 检索增强 | 本次探针：MoE 答对、稠密答错（U=退刀量/R=切削次数），说明两模型领域知识都不牢；RAG 比 SFT 便宜两个量级 |
| P2-2 | G 代码与工具参数走**语法约束解码**（GBNF / Ollama `format` JSON Schema） | 把"语法是否合法"从概率问题变成保证；对 Agent 工具链是硬需求 |
| P2-3 | 投机解码（draft）只在稠密路径试 | 本机 0.40.14 二进制含 `draft_num_predict` 字段与 `--draft-quantize`；但 6GB 显存下 draft 会挤占 KV，收益需实测，MoE 路径不建议 |
| P2-4 | 运维修复（已顺手完成） | `E:\OllamaApp\serve_e_store.bat` 原内容为 `set "OLLAMA_MODELS=E://ollama//models"/r/nset ...`（`\r\n` 被写成字面量），会污染 `OLLAMA_MODELS` 与 `NO_PROXY`；已重写为 CRLF 正确版本（显式带 `OLLAMA_MODELS=E:\ollama\models`、`FLASH_ATTENTION=1`、`KV_CACHE_TYPE=q8_0`），服务已恢复（18 个模型可见）。另：`ollama app.exe` 经 explorer 拉起时继承的是**旧环境**，会读不到 E: 盘模型——这是今早服务"起来但 0 个模型"的根因 |

---

## 4. 明确不建议做的事

1. **阶段 B 继续预训练 / 再扩层**：需要大量算力，且 6GB 显存连推理都要卸载，投入产出为负（这也是 10B 被下线的同一理由）。
2. **继续加专家数（2→4/8）**：当前 2 个专家已经让权重翻倍到 8.3GB、速度掉到 1/3.7；在 6GB 卡上加专家只会更慢。
3. **只改门控就宣布"MoE 达标"**：门控修复只解决路由语义，不解决"两个专家是否真的互补"；必须配同尺 A/B（n≥240、同 grader、内容寻址 run_id）才能下结论。

---

## 5. 验收口径（测量宪法）

- 速度：同题、同 `num_predict`、同 `temperature`，三次取中位数；记录 `eval_count/eval_duration`（不用墙钟）。
- 质量：同尺 A/B，n≥240，同一 grader 文件，`RunIdentity.capture()` 记层哈希 + 用例 sha256 + 判分器 sha256；`drift()` 非空即作废。
- 结构：专家增量余弦、门控与"全 1 方向"对齐度（本文件已给出脚本 `scripts/measure_expert_delta.py`，可复跑）。

---

## 6. 参考资料（联网核对）

1. mergekit-moe 官方文档 —— 三种 gate mode 的定位（`hidden` 最佳、`cheap_embed` 低配可行、`random` 仅供再训练），及"plain merge MoE 常 underperform、通常仍需短 SFT 对齐路由"：https://github.com/arcee-ai/mergekit/blob/main/docs/moe.md
2. MergeKit MoE 实现细节（`get_gate_params`、门控条件数告警阈值 5.0）：https://deepwiki.com/arcee-ai/mergekit/4.5-mixture-of-experts-(moe)
3. 《When Model Merging Breaks Routing》—— 合并导致 routing breakdown，50.11% 专家选择偏离、16 层后 99.98% token 发散；提出免训练 HARC 校准：https://arxiv.org/html/2606.03391v1
4. 同篇中文摘要（HARC 与路由故障机理）：https://www.alphaxiv.org/zh/abs/2606.03391
5. Ollama KV cache 量化与 Flash Attention 的正确配法（`OLLAMA_FLASH_ATTENTION=1` + `OLLAMA_KV_CACHE_TYPE=q8_0`，q8_0 约为 f16 一半且质量损失可忽略）：https://bestllmfor.com/guides/context-window-vram-cost/
6. 8GB 级显卡的取舍原则（先降 context、再量化 KV、再降参数级，最后才动 4bit 以下权重）：https://ollamalab.com/posts/best-ollama-models-for-8gb-vram
