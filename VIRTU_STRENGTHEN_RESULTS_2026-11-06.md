# Virtu 模型强化 · P1-2 稠密化对照实测结果（2026-11-06）

> 测量宪法合规：8 条腿全部 `seal_leg` 封缄（各 30 行），`metrics_from_raw(require_row_identity=True)`
> 通过（每行带 `served_layers` 层指纹），`RunIdentity.drift()` = **NONE（干净）**。
> run_id = `42394667c097dd46`，证据目录 `runs/eval/ab20261106_*`，封缄摘要见各腿 `_seal.json`。

## 0. 实验目的

验证计划 §3 / P1-2 的假设：**把 MoE 双专家 FFN 增量合并回单稠密 FFN（稠密化）能否 ≥ MoE**，
从而"直接退役 MoE 的推理角色"。若成立则稠密化是零风险强化；若不成立则转向 P1-1（修门控）或 P1-3（文档级路由）。

被测对象（按内容寻址，非按名字）：

| 标签 | Ollama tag | 模型层 sha256(前 16) | 架构 | 量化 | 参数 |
|---|---|---|---|---|---|
| baseline | `virtu-comprehensive:fast` | `c3b78c7735c9ac1f` | Qwen3 稠密 8B | Q4_0 | 4.6GB |
| 稠密 v1 | `virtu-dense-merged:q4_0` | `df83b71eeacef0a0` | Qwen3 稠密 8B | Q4_0 | 4.6GB |
| 稠密 v2 | `virtu-dense-merged-v2:q4_0` | `97a7eb763837c37d` | Qwen3 稠密 8B | Q4_0 | 4.6GB |
| MoE | `virtu-moe-14b:fast` | `a2103c68d9e881ac` | Qwen3-MoE 14B | Q4_K_M | 8.3GB |

- **稠密 v1** = 基座 Qwen3-8B + 两条专家 FFN 增量 **TIES 合并**（density=0.6，trim 掉 40% 小量级）。
- **稠密 v2** = 基座 Qwen3-8B + 两条专家 FFN 增量 **等强直接加和**（无 trim，ffn_scale=0.5）。
- 注意力/embedding/其余权重：三稠密臂与 MoE **逐位一致**（同源基座 + 未动的注意力）。
- A/B 唯一变量是「FFN 来源」（MoE 逐 token 路由 vs 稠密静态合并）。

用例：`data/benchmark/virtu_eval_text_v1/{knowledge,reasoning}.jsonl`（各 30 题，easy/medium/hard 分层），
判分器 `virtu_eval/graders.py`（sha `5024fe5c`）。同维 30 题在四臂间**按 case_id 对齐**，可做成对比较。

## 1. 实测结果（basis = measured，n = 30/腿）

| 臂 | 知识 mean | 知识 pass% | 推理 mean | 推理 pass% | 单流速度* |
|---|---:|---:|---:|---:|---:|
| baseline（稠密 8B 原版） | 57.78 | 37% | 59.94 | 43% | ~38 tok/s |
| 稠密 v1（TIES, d=0.6） | 58.61 | 37% | 48.76 | 33% | ~38 tok/s |
| 稠密 v2（等强加和） | **62.44** | **43%** | 57.25 | 30% | ~38 tok/s |
| MoE 14B | **66.88** | **50%** | 52.60 | 33% | ~9–10 tok/s |

\* 速度说明：评测记录的 tok/s（baseline 30.9 / v1 31.9 / v2 18.8 / moe 7.2）含评测管线开销且
v2 两维**并行跑**导致相互挤占，不可横向比。单流实测：基线/稠密 ≈ 38 tok/s，MoE ≈ 9–10 tok/s（详见计划 §1）。
结论"稠密比 MoE 快约 4×"由单流测量支撑，与评测记录的相对差距一致。

## 2. 三条硬结论

1. **v2（等强加和）> v1（TIES）在两个维度都成立**：知识 62.44 vs 58.61（+3.8），推理 57.25 vs 48.76（+8.5）。
   证明对这两条增量，**trim 掉 40% 小量级是净损失**——增量本身量级小（占权重 1% 量级），trim 等于把专家信号砍掉。
   → 稠密化若要做，必须用 v2 配方（无 trim 的等强加和），v1 作废。

2. **没有任何一个稠密臂在"知识"上达到 MoE**：最佳稠密 v2 = 62.44 < MoE = 66.88（-4.4，且是在同 30 题上成对落后）。
   MoE 的逐 token 路由把"该问 CAD 专家还是力学专家"分开了，静态合并把两套正交增量搅在一起，专业化被稀释。
   → 计划 P1-2 的退役判据（"稠密 ≥ MoE"）**不成立**。

3. **把专家增量合进稠密 FFN 会轻微拖累通用推理**：baseline（无增量）推理 59.94，v2（有增量）57.25（-2.7），
   v1 更差（48.76）。专家是为领域数据训的，其 FFN 扰动对领域外（数学推理）有负迁移——这是合并类方法的已知现象。

## 3. 决策（落到计划 §3 / P1 取舍）

- **P1-2 稠密化"退役 MoE"路线被本实验否决**。稠密化不是免费强化；它用质量换速度，且在本数据集上质量还略低于原版基线。
- **MoE 仍是质量标杆**（知识 50% pass、mean 最高），但慢 4×。保留其推理角色。
- 推荐下一步（二选一，均符合 6GB 显存现实）：
  - **P1-3 文档级路由（优先，零训练）**：用 `nomic-embed-text` 做意图分类，快路径→稠密 ~38 tok/s，难题→MoE ~10 tok/s。
    避免"一句话里换两次大脑"，且推理角色按难度分流。
  - **P1-1 修门控（次选，需极短 SFT）**：当前门控是"全 1 / 全 -1 +1% 噪声"的假路由（计划 §2.1 证据）。
    改 `cheap_embed`/`hidden` 语义门控可能把 MoE 再推高，但 mergekit 原话提醒 plain-merge MoE 常 underperform，需配同尺 A/B。
- **v2 稠密模型值得保留为"高速默认"**：它比原版基线在知识上 +4.7（同 30 题成对），仅在推理上 -2.7；
  若部署场景以知识问答为主、对推理要求不高，v2 是比 baseline 更优的高速默认。已落地为 `virtu-dense-merged-v2:q4_0`。

## 4. 产物清单

- 稠密化脚本：`scripts/densify_virtu_to_dense.py`（支持 `--merge-mode sum_norm|ties --density --ffn_scale`）
- GGUF 直写：`scripts/write_dense_gguf.py`（纯 numpy 行切片，无 llama.cpp 依赖；Q4_0 因本机 `create --quantize` 拒收 k-quants）
- 权重：`checkpoints/virtu_dense_merged_hf/`（v1）、`checkpoints/virtu_dense_merged_v2_hf/`（v2，稠密 bf16）
- GGUF：`checkpoints/virtu-dense-merged-q4_0.gguf`、`checkpoints/virtu-dense-merged-v2-q4_0.gguf`
- Ollama：`virtu-dense-merged:q4_0`、`virtu-dense-merged-v2:q4_0`
- 证据：`runs/eval/ab20261106_*`（8 腿原始 + `_seal.json`）、`runs/eval/runidentity_20261106.json`

## 5. 局限（如实标注）

- 每臂 n=30，未做配对重复；"成对落后/领先"是方向性结论，非显著性检验。
- 专家增量仅占权重 ~1% 量级，稠密化带来的绝对变化小（±5 分内），对生产部署是"可选优化"而非"必做"。
- 评测集为文本维度（knowledge/reasoning），未覆盖 toolcall/物理合规等维度；稠密化对工具调用的影响需另测。
