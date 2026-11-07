# Virtu 真·10B 化方案（深度扩展 / Depth Up-Scaling）

> 定稿：2026-11-06 · 决策人：Agent 全权定案 · 状态：**阶段 A 已执行并实测，阶段 B/C 待算力**
> 口径遵循测量宪法：凡写进本文件的数字，均标注 `measured` / `asserted` / `design`，未测的一律写"未测"。

---

## 0. 决策摘要（一页看完）

| 项 | 结论 |
|---|---|
| 现状 | `virtu-cad-cam-10b` 是 **8.190735360 B**，名字里的 10b 是品牌名/兼容别名（`measured`: GGUF 头 399 张量维度累乘；`checkpoints/PROVENANCE.json` 原文 "brand name; not a 10B parameter model"） |
| 目标 | **真实 ≥10B 个张量参数**，且由加载器独立算出，不靠改 metadata、不靠 padding、不靠别名 |
| 路线 | **层深度扩展（SOLAR-style depth up-scaling）**：36 层 → **46 层**，新增 10 层从中间层复制（非零实权重） |
| 结果 | **10,120,199,680 参数 = 10.1202 B**（`design`，由结构公式精确推导；阶段 A 产物上复测为 `measured`） |
| 为什么是 46 | 45 层 = 9.9273B **不够 10B**；46 层是达标的最小整数层数，新增参数/显存/训练成本最低 |
| 分阶段 | **A 结构真实**（本机可完成，本次已做） → **B 能力激活**（必须继续预训练，需 GPU） → **C 上线**（内容寻址 + A/B 硬闸） |
| 红线 | 阶段 A 产物**不宣称能力提升**、**不覆盖线上服务标签**、**不把复制层说成已训练** |

---

## 1. 现状实测基线（可归因）

| 事实 | 数值 | 证据 | basis |
|---|---|---|---|
| 当前部署权重层 | `sha256:c3b78c773…` / 4,614,297,600 B | `benchmarks/VIRTU_FULL_BOARD_2026-11-05.md` + 本次 `E:/ollama/models/manifests` 实测 | measured |
| 张量总数 / 层数 | 399 / 36（每层 11 张量） | 本次解析 `checkpoints/virtu-comprehensive-q4_0.gguf` GGUF v3 头 | measured |
| 参数总数 | 8,190,735,360 | 同上，逐张量 dims 累乘 | measured |
| 架构 | qwen3 / hidden 4096 / FFN 12288 / vocab 151936 / 32Q 8KV / ctx 40960 | 同上 metadata | measured |
| 6 个 virtu-* 标签 | 权重层逐字节相同，仅 template/system/parameters 不同 | 本次 manifest 归并 | measured |
| `virtu_omni_10b_base.pt` | 578,839,296 params（0.58B / 33 tensor 空壳） | `PROVENANCE.json`、`AGENT_TRAINING_PLAN.md:35` | measured |
| HF 基座在盘 | `checkpoints/_base_qwen3_8b/` 16.4GB / 5 safetensors 分片 | 本次 `ls` | measured |
| 本机算力 | RTX 4050 Laptop 6GB（空闲 ~5.8GB）、无 torch、numpy 2.5.4 | `GPU_MERGE_RUNBOOK.md` + 本次 `importlib` 探测 | measured/asserted |
| 磁盘 | D: 156.7GB 空闲 / E: 115.2GB 空闲 | 本次 `shutil.disk_usage` | measured |

---

## 2. 什么叫"真正意义上的 10B"——先把定义钉死

必须同时满足 **L1** 和 **L2**，缺一不可。只做到 L1 就宣称"10B 大模型"是本项目历史上已经犯过的错（0.58B 空壳 + 假的"参数对齐 100%"报告）。

- **L1 · 结构真实**：权重文件里确实存在 ≥10,000,000,000 个张量元素；全部为**非零、有信息、参与前向**的权重；第三方加载器（llama.cpp / Ollama）从张量维度**独立算出** 10.1B，而不是读我写的一个字符串；能加载、能出 token。
- **L2 · 能力真实**：新增的 ~1.93B 参数经过**继续预训练**产生非零梯度更新、不再是纯复制品；在**同尺同 grader** 的 A/B 中不退化，且至少一项能力有可归因增益；训练前后权重 sha256 不同、有 `run_id` 与证据腿。

> 阶段 A 交付的是 **L1**。L2 不由本次会话伪造，需要算力，见 §5。

---

## 3. 路线选择与否决理由

| 路线 | 判定 | 理由 |
|---|---|---|
| **A. 深度扩展 36→46**（选中） | ✅ | 结构公式干净、每层参数恒定、只改 `block_count` 与张量名；有 SOLAR-10.7B 公开先例；现有 4 个 r=32 LoRA 键名 `model.layers.0~35` 全部保留，无需重训工具壳 |
| B. 宽度扩展（hidden/FFN 加宽） | ❌ | 要同步改 embedding/lm_head 维度、残差维度与 q/k/v 的 head 对齐，Net2Net 函数保持复杂，且 vocab 侧 622M×2 被动膨胀，参数不可控 |
| C. 换 Qwen3-14B 基座 | ❌ | 不是 10B；6GB 显存放不下；键空间全变，6 个 LoRA 与 23,178 条 tool_call 语料全部作废。`CLOUD_FINETUNE_PLAN.md:60` 已否决 |
| D. MoE 化 | ❌ | 架构变更，llama.cpp/Ollama 的 GGUF 路径与现有转换器不支持；且"总参数 10B、激活 3B"与用户要的 dense 10B 不是一回事 |
| E. 改 metadata / 补零张量凑数 | ❌ **红线** | 违反测量宪法；`PROVENANCE.json` 已把"10B 是品牌名"钉死，再犯就是造假 |
| F. 直接把 6 个 virtu 标签参数相加 | ❌ **红线** | 实测是同一份权重的 6 个别名，重复计数 |

**为什么选 46 而不是历史空壳声称的 48 层**：48 层 = 10.5061B，多 2 层（+385,892,864 参数），显存与训练成本更高，收益为零。脚本支持 `--target-layers 48`，需要对齐历史设计时一行切换。

---

## 4. 精确参数核算（与磁盘实测零误差）

```
单层 = H·H + H·KV + H·KV + H·H + 2·128 + H·F + H·F + F·H + 2·H
     = 4096² + 4096·1024 + 4096·1024 + 4096² + 256
       + 4096·12288 + 4096·12288 + 12288·4096 + 8192
     = 192,946,432
embed 各 = V·H = 151936·4096 = 622,329,856（untied：token_embd 与 output 各一份）
总(36) = 36·192,946,432 + 2·622,329,856 + 4096 = 8,190,735,360  ← 与 GGUF 实测差 0
总(45) =  9,927,253,248 = 9.9273B  ✗ 不足 10B
总(46) = 10,120,199,680 = 10.1202B ✓ 最小达标解
总(48) = 10,506,092,544 = 10.5061B（历史设计，备选）
```

Q4_0 落盘估算：4,614,297,600 B × (10.1202/8.1907) ≈ **5.70 GB ≈ 5.31 GiB**（`design`，实际以产物 `stat` 为准）。

---

## 5. 三阶段方案

### 阶段 A · 结构真实 10B（本机，零 torch / 零网络）—— 本次已执行

输入 `checkpoints/virtu-comprehensive-q4_0.gguf`（当前部署字节，含 4 个 LoRA 合并成果），走 `scripts/gguf_depth_upscale.py`：

1. 解析 GGUF v3 头（29 metadata / 399 tensor info），原样保留全部 tokenizer 与量化 metadata；
2. 只改两处：`qwen3.block_count 36→46`、`general.name`；**不写任何"参数量"字段**——10.1B 由加载器从 509 个张量维度自己算出来；
3. 追加 10 层 × 11 张量 = 110 个新张量，重命名为 `blk.36.* … blk.45.*`；源层取 `blk.18 … blk.27`（中段，避开首尾特殊层）；
4. 新张量数据 = 源层对应张量的**逐字节拷贝**（Q4_0 块 + F32 norm），按 32B 对齐追加到数据区；原 399 个张量的数据区整块原样复制，**零精度损失**；
5. 生成 `*.receipt.json`：`run_id`（源 sha256 + 脚本 sha256 + 参数指纹）、`n`、每个新张量的源/目标 sha256、`basis: measured`。

**为什么复制而不是置零**：置零层虽然函数严格保持，但等于用零张量凑参数，正是本项目要杜绝的"空壳"。复制层是**非零、含领域知识、参与前向**的真实权重（SOLAR 做法），代价是初始输出会有扰动 → 必须由阶段 B 训练收敛。

**产物**：`checkpoints/virtu-10b-d46-q4_0.gguf` + `.receipt.json`。不覆盖、不删除任何现有文件；不注册为线上标签。

**验收闸门 A（缺一不通过）**
- G-A1 新 GGUF header：`n_tensors = 509`、`qwen3.block_count = 46`、参数总数 `= 10,120,199,680`
- G-A2 110 个新张量与源层对应张量 **sha256 全等**（逐层打印）
- G-A3 新张量数据**全部非全零**（排除 padding 造假）
- G-A4 原 399 张量数据区与源文件**逐字节相等**（零回归证据）
- G-A5 Ollama `create` 成功、`/api/show` 的 `details.parameter_size` 显示 10.1B 级别、能生成 token

### 阶段 B · 能力激活（必须做，需 GPU）—— 待算力

新增 10 层现在是复制品，**参数真实但未激活**。要达 L2：

- **B-0 HF 侧重建**：从 `checkpoints/_base_qwen3_8b`（bf16，16.4GB）重建 46 层 HF 目录（同款层复制，纯 numpy 写 safetensors + 改 `config.json num_hidden_layers=46`），再跑 `scripts/merge_numpy.py --mode peft_linear` 把 4 个 r=32 LoRA 合并进 `layers.0~35`（键名不变，新增层不带 LoRA）。**不要在 Q4_0 反量化结果上训练**。
- **B-1 数据**：`gpu_handoff/virtu_toolcall_train_final.jsonl`（2,414 行）+ 6,024 条 SFT + 23,178 条未训 tool_call 语料；holdout 94 行严禁入训（`handoff_manifest.json` 已留痕）。建议通用语料占 10–15% 防灾难性遗忘。
- **B-2 训练（二选一）**
  - 云端（推荐）：L40S 48GB，bf16，**冻结 layers.0~35，只训 layers.36~45**，lr 1e-5、warmup、2 epoch；预算参考 `CLOUD_FINETUNE_PLAN_2026-11-01_v2.md` 的 ¥50–80 档。命令骨架沿用 `scripts/train_virtu_l40s.py --base <46层HF目录>`。
  - 本机（受限）：6GB 显存**跑不动 1.93B 全参**；只能装 torch 后对新增 10 层做 QLoRA(r=32) 小规模续训，属"验证链路"而非"达成 L2"。不在本机宣称能力达标。
- **B-3 闸门**：训练前后 `layers.36~45` 权重 sha256 必须不同（Δ≠0）；同尺同 grader 的 `board7(210) + toolrouting(30) + phys(60)` A/B，任一维跌 >3 分即拒绝；`published=1` 才允许引用增益。

### 阶段 C · 上线（内容寻址）

1. 合并训练 delta → 46 层 HF → `scripts/hf_to_gguf_numpy.py` 出 Q4_0 → Ollama `create` 新标签 `virtu-10b:<run_id 前 8 位>`（**内容寻址，不用 `latest`**）；
2. 起腿前 `RunIdentity.capture()` 记 model/template/system 三层哈希，腿结束 `drift()` 非空即作废该腿（2026-11-05 事故的硬约束）；
3. `/v1/models` 的 id 可继续对外显示 `virtu-cad-cam-10b`，但此时它**名副其实**；同时更新 `PROVENANCE.json` 把 "brand name; not a 10B parameter model" 改成带 `run_id` 的 measured 记录。

---

## 6. 硬约束、风险与回退

| 风险 | 实测/估算 | 处置 |
|---|---|---|
| 6GB 显存 | Q4_0 10B ≈ 5.31 GiB + 4096ctx KV ≈ 0.7 GiB → 逼近 5.8GB 空闲 | 优先 `num_ctx 4096` 而非 40960；必要时 `--n-gpu-layers` 部分 CPU 卸载，或后续支持 Q3_K_M IQ 量化；不通过压 ctx 到不可用值来"跑通" |
| 复制层扰动 | 阶段 A 输出与 8B 版**不会逐 token 一致**（这是预期，不是 bug） | 阶段 A 明确不宣称能力等价；用 A/B 分数说话，不用"能出字"当通过 |
| 灾难性遗忘 | 项目文档估 10–15% 通用对话风险 | 通用语料混合 + 早停 + 基线 A/B |
| LoRA 键空间 | 4 个 r=32 对应 layers.0~35，46 层后仍一一对应 | 新增层不挂旧 LoRA；`tool_agent_lora_final`(r=16) 仍因 rank 冲突不合并 |
| 磁盘 | D 156.7GB / E 115.2GB 空闲 | 阶段 A 新增约 5.7GB，充足 |
| **回退** | 阶段 A 全是新文件 | 删产物即可，线上 `virtu-comprehensive` / `virtu-frozen` 等标签与权重**一个字节都没动**；若 G-A 任一闸失败，按熔断公理停止后续、出 RCFA，不叠加修补 |

---

## 7. 禁止项（红线，写进验收）

1. 禁止在 GGUF metadata 里手写 `parameter_count=10B` 或任何等价字段来"让加载器显示 10B"。
2. 禁止追加全零张量 / 重复引用同一 data offset 的假层来凑参数。
3. 禁止把 6 个 virtu-* 别名标签当成 6 个模型相加。
4. 禁止在阶段 B 完成前把阶段 A 产物注册为线上 `latest` 或对外宣称"Virtu 已是 10B 大模型"。
5. 禁止把本方案里的 `design` 估算数写成 `measured` 结果。

---

## 8. 证据清单

| 文件 | 作用 |
|---|---|
| `checkpoints/virtu-comprehensive-q4_0.gguf` | 阶段 A 输入，当前部署字节（只读） |
| `scripts/gguf_depth_upscale.py` | 扩展器源码（含自检） |
| `checkpoints/virtu-10b-d46-q4_0.gguf` | 阶段 A 产物 |
| `checkpoints/virtu-10b-d46-q4_0.gguf.receipt.json` | run_id / 逐张量 sha / basis |
| `.workbuddy/memory/2026-11-06.md` | 本次会话的可归因日志 |

---

## 9. 阶段 A 执行记录（2026-11-06 00:43–00:46 实测，非计划）

```bash
python scripts/gguf_depth_upscale.py \
  --src checkpoints/virtu-comprehensive-q4_0.gguf \
  --out checkpoints/virtu-10b-d46-q4_0.gguf \
  --target-layers 46 --copy-from 18 --name virtu-10b-d46-merged
# 65.6 s，GATE A PASS (7/7)
```

| 项 | 实测值 | 证据 / basis |
|---|---|---|
| run_id | `a45b34271744f9ca` | `.receipt.json` |
| 产物 | 5,699,918,176 B = 5.31 GiB | `os.path.getsize` |
| 层数 / 张量 | 36→46 / 399→509（f32 185 + q4_0 324） | 两套独立 GGUF 解析器 + llama.cpp 原生日志 |
| **参数总数** | **10,120,199,680 = 10.1202 B** | 独立解析器；llama.cpp `print_info: model params = 10.12 B`；Ollama `general.parameter_count` |
| 110 个新张量 | 与 `blk.18..27` 逐字节 sha256 全等、全部非零 | `receipt.tensor_evidence` |
| 原 399 张量 | 数据区 sha256 `e408fcd4…` 前后完全一致 | 闸 G-A4 |
| 509 个 offset | 两两不同 → 不是重复引用同一段数据的假层 | 独立复验 |
| GGUF 内参数量字段 | `[]`（一个都没写） | 独立复验 |
| Ollama 注册 | `virtu-10b:a45b3427`，`parameter_size = "10.1B"` | `/api/tags`、`/api/show` |
| llama.cpp 加载 | `29 key-value pairs and 509 tensors`、`n_layer = 46`、`offloaded 34/47 layers to GPU` | 服务日志 |
| 前向推理 | done=True，96 tokens / 11.30 s ≈ **8.41 tok/s**，load 14.29 s，prompt 33 tok | `/api/generate` + `slot print_timing` |
| 显存 | CUDA0 3750.42 MiB + CUDA_Host 1679.76 MiB，KV 207 MiB（46 layers） | 服务日志 |
| 回答抽样 | "Vc = π * D * n / 1000 … n = (Vc * 10…"，公式方向正确 | `/api/generate` |

**如实记录的代价与限制（不得隐去）**

- 吞吐从 8B 版 21.2 tok/s（`GPU_MERGE_RUNBOOK.md` 实测）降到 **8.41 tok/s**，主因 46 层计算量 + 12 层 CPU 卸载。
- `tokenizer.chat_template` 在源 GGUF 里本就是空串（kv 28），Ollama `template selection: selected=none`，`capabilities = ['completion']`（**无 tools**）。这是继承的既有缺陷，不是扩展引入的；阶段 C 上线前必须注入 1723 字符原生模版（参考 `benchmarks/VIRTU_FULL_BOARD_2026-11-05.md` 的 `.Tools/.ToolCalls` 修复）。
- 复制层改变了输出分布，**未做同尺同 grader A/B**，因此：不宣称能力等价、不宣称能力提升、不宣称困惑度不变。
- 该标签按内容寻址命名，未覆盖任何线上 `latest`；`checkpoints/PROVENANCE.json` **未改动**（阶段 C 才改）。
- 验证用 Ollama 服务由本次会话启动（0.40.14，端口 11434），仍在运行；模型 blob 已落盘 `E:/ollama/models`，服务重启后标签依旧可用。

**结论：L1 结构真实 10B 已达成并由第三方加载器独立确认；L2 能力真实 10B 未达成，必须走阶段 B 的继续预训练。**

---

## 11. 2026-11-06 02:10 修复与状态更新

### 11.1 §9 遗留的空 template 缺陷已修复

§9 第 188 行记录：阶段 A 产物继承源 GGUF 空 `tokenizer.chat_template`，Ollama `capabilities=['completion']`（无 tools）。**本轮已修复**：

| 项 | 修复前（2026-11-06 01:57 实测） | 修复后（2026-11-06 02:10 实测） |
|---|---|---|
| template source | 无（空模板） | `go_template`（Qwen3 chat template，含 `.Tools`/`.ToolCalls` 分支） |
| capabilities | `['completion']` | `['completion', 'tools']` |
| system | 空（0 字符） | 有（工业智能体 system） |
| num_ctx | 4096 | 8192 |
| repeat_penalty | 未设 | 1.05 |

- 重建命令：`ollama create virtu-10b:a45b3427 -f Modelfile_virtu_10b_fixed`（`FROM checkpoints/virtu-10b-d46-q4_0.gguf`，复用原权重层 sha `b9f9ac33…`，仅新增 template/system/parameter 层）。
- **边界不变**：模板修复只解决"格式可用性"，**不等于 L2 能力激活**。真实工具调用/思考能力仍需阶段 B 继续预训练；能力维度不得据此宣称 dense 10B 训练达标。

### 11.2 关于 §3 已否决的 MoE 路线——实际已落地，须单列口径

§3 将"路线 D · MoE 化"列为否决项。但实测本机存在 **`virtu-moe-14b:latest`**（2026-11-06 01:32 构建，01:35 通过部署验证），其结构为 `qwen3moe`、36 层、`expert_count=2 / expert_used_count=1`、size_label `2x8.2B`：

- **总参 13,626,848,256（13.63B）是稀疏总参**；每 token 仅 top-1 激活，dense 计算量约 **8.2B**（共享注意力/嵌入 + 单专家 FFN；按 1/2 朴素估算 6.81B 偏低）。
- **它不是本方案的 dense 10B 目标**，不能计入 L1/L2，也不能表述为"dense 14B"。
- 归因：`checkpoints/virtu-moe-14b-q4_k_m.gguf.receipt.json`、`checkpoints/virtu-moe-14b-bf16.gguf.receipt.json`（含真实 sha256）、`checkpoints/PROVENANCE.json#virtu_moe_14b_q4_deployment`。

### 11.3 404 ghost 标签已清除

本轮清除 4 个 `/api/show` 返回 404 的索引残留：`virtu-toolcall:latest`、`virtu-boundary-sft:latest`、`virtu-toolcall:latest.bak_pre_params_repair`、`virtu-production:v3`。清理后 `/api/tags` 的 13 个 virtu 标签逐一 `ollama show` 全部 OK。

---

## 10. 完整训练成本（2026-11-06 独立核算，run_id `d3d20d38033e2207`）

可复算：`python scripts/estimate_10b_train_cost.py` → `benchmarks/VIRTU_10B_TRAIN_COST.json`。
**口径警告：仓库内无任何账单/发票，以下全部是预算估算，不是已发生费用。** `measured` 的只有历史训练耗时/token、语料 token 数、模型参数量、云单价截图。

### 10.1 先修正一个方案前提

上一版 §5 写「L40S 48GB 冻结旧层只训新增层」，**没写清显存条件**。按 `冻结 8.1907B + 可训 1.9295B` 实算：

| 配置 | 状态占用（不含激活） | 可行性 |
|---|---:|---|
| 全参 + AdamW(fp32) | **47.60 GiB** | ❌ L40S 48GB 装不下激活 → 只能 A800 80GB |
| 全参 + AdamW(8bit) | 24.24 GiB | ✅ L40S 48GB 可行（**推荐**，需改优化器） |
| 仅新增层 LoRA r=64 | 15.87 GiB | ✅ V100 32GB 可行，单价最低 |

### 10.2 核算锚点（全部 measured）

- `virtu_toolcall_lora/training_receipt.json`：L40S / LoRA r32 / grad_ckpt / sdpa，**3,140,926 token / 3,514.6 s = 893.7 tok/s**。
- `data/validation/train_cost_analysis.json`：23,178 条 = **60,272,726 tok/epoch**，其中 loss tokens 仅 8,953,929（52M 是 tools-schema 噪声）。
- `CLOUD_FINETUNE_PLAN_2026-11-01_v2.md`：`virtu_fix_v1` = **3,104,927 tok/epoch**（2048 口径，Qwen3 tokenizer 实测）。
- 单价（用户截图/文档实测价）：V100 32G **¥1.98/h**、L40S 48G **¥4.50/h**、A800 80G **¥7.20/h**。
- FLOPs：冻结层在前 → 反向只需过新增 10 层，**31.82 GFLOPs/token**，比 8B 全层 LoRA 锚点 49.14 G 低 35%（比值 0.647）。

### 10.3 三档 × 三卡（2 epoch，实测锚点外推；括号内为 MFU 40% FLOPs 法下界）

| 语料档 | 2ep token | V100 ¥1.98/h | L40S ¥4.50/h | A800 ¥7.20/h |
|---|---:|---:|---:|---:|
| A 试点（6.21M） | 6.21M | ¥5.97 / 3.02h | ¥7.03 / 1.56h | ¥6.52 / 0.91h |
| **B 推荐（12.42M）** | 12.42M | ¥11.94 / 6.03h | **¥14.06 / 3.12h** | ¥13.05 / 1.81h |
| C 全量（120.55M，含 schema 噪声） | 120.55M | ¥115.91 / 58.5h | ¥136.45 / 30.3h | ¥126.65 / 17.6h |

三卡同档价差仅 ¥1–2（B 档），与项目既有结论「别纠结卡」一致。**单位成本约 ¥1.0–1.15 / 百万 token**。
FLOPs 法给出的下界比实测外推低 2×，故预算按实测外推算，不按 FLOPs 下界报低价。

### 10.4 完整总账（推荐：档 B / L40S / 8bit AdamW）

| 阶段 | 金额 | 口径 |
|---|---:|---|
| S0 语料构建/去重/三闸 | ¥0 | measured（本地，语料已在盘） |
| S1 环境 + 基座就位 | ¥0–9 | asserted（平台预置则 0） |
| S2 preflight + 20 步 smoke | ¥0.5–1 | asserted |
| S3 主训练 2 epoch | **¥9.84–22.49** | design（实测锚点外推，3.12h） |
| S4 条件补强/失败重试（≤2 轮） | ¥0–9 | asserted（不过闸才发生） |
| S5 产物回传 + 数据盘 | ¥0–5 | asserted |
| S6 本地合并/GGUF/注册 | ¥0 | measured（纯 numpy） |
| S7 本地 A/B（300 条 × 2 臂） | **¥0** | measured，但耗时 **≈10.2 h** 本机（8.41 tok/s × 512 tok） |
| **合计** | **¥10.34 – ¥46.49** | 预算硬上限 **¥60** |

墙钟：**GPU 约 6.6 h + 本地评测约 10.2 h**。阶段 A（结构扩展，本机 65.6 s）与阶段 C（上线）均为 **¥0**。

### 10.5 不算在内的（避免混淆口径）

1. **从头预训练一个真 10B**：200B–1T token、A100/H100 集群、数十万~数百万 ¥（`VIRTU_REAL_MODEL_PLAN.md`）。本方案是「在已有 8B 权重上扩展并激活」，不是同一件事。
2. **本机训练**：6GB 显存跑不动 1.93B 全参，未计入。
3. **语料扩充风险**：当前 1.2 万条级语料对 1.93B 全参偏少，若收敛不佳需扩 10× 语料或多轮续训，成本按 ¥1.1/M token 线性上浮到 **¥100–200**。
4. **实际账单**：不存在。真实成本须以跑完后的云平台账单为准，届时把 `basis` 改为 `measured` 回填。

---

## 12. 计划终止与资产下线（2026-11-06 08:43，用户决策）

**决定：停止阶段 B/C，10B 资产整体下线。本文件此后仅作历史技术记录，不再代表在役状态。**

- **理由（用户口径）**：阶段 B 继续预训练需要大量算力，本机不具备，故不再保留该模型，避免「名字 10B、能力 8.2B」的持续误导。
- **已删除（2026-11-06 02:0x–02:1x 执行）**：`virtu-10b:a45b3427`（Ollama tag）、`checkpoints/virtu-10b-d46-q4_0.gguf`（约 5.7 GB）、对应 `*.receipt.json`。删除后 `/api/tags` 与 `checkpoints/` 均无 10B 残留。
- **保留（可重建性）**：
  - `scripts/gguf_depth_upscale.py` —— 阶段 A 深度扩展脚本（确定性，纯 numpy，本机实测 65.6 s）；
  - `Modelfile_virtu_10b_fixed` —— 已修好空 template 缺陷的注册配方（`completion`→`completion+tools`，`num_ctx` 4096→8192）；
  - §9 阶段 A 实测记录与 §10 成本核算 —— 作为历史 measured/design 事实保留。
- **重建命令（仅在确有算力做阶段 B 时使用）**：
  ```bash
  python scripts/gguf_depth_upscale.py \
    --src checkpoints/virtu-comprehensive-q4_0.gguf \
    --out checkpoints/virtu-10b-d46-q4_0.gguf \
    --target-layers 46 --copy-from 18
  ollama create virtu-10b:a45b3427 -f Modelfile_virtu_10b_fixed
  ```
- **同步影响面**：
  | 载体 | 处理 |
  |---|---|
  | `VIRTU_MODEL_RADAR.html` | 10B 行标注「已彻底清理下线 / 文件已清除」，分数置空 |
  | `README.md` | 在役清单移除 10B，改为「已下线资产」条目并附重建路径 |
  | `checkpoints/PROVENANCE.json` | 新增 `retirement_2026_11_06`；`repairs_2026_11_06.template_repair` 标记 superseded |
- **引用约束**：§9 的 10.12B / 46 层 / L1 结构真实结论，以及 §10 的 ¥10.34–46.49 训练预算，均为**历史记录**，当前已无在役模型与之对应；任何复述必须同时注明「2026-11-06 已下线」。
