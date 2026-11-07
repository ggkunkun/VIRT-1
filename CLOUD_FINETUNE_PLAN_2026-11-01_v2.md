# Virtu 云端微调计划 v2（按已生成语料重算）— 2026-11-01

> 本版不是估算稿：语料已实际生成并校验（`data/train/virtu_fix_v1/`），token 数来自 Qwen3 tokenizer 实测。
> 目标仍是“成本最少 + 质量最高”：**单次文本 LoRA，工具调用专家保持独立**；不合并多 LoRA，不做全参。
> 成本口径：标「实测」来自仓库记录或本次构建；标「估算」的是按 token/吞吐外推，租机前按当日价复核。

---

## 0. 执行结果与结论

已生成 **5,991 条**文本能力 SFT 语料：

- 可训练 token（2048 截断口径）：**3,104,927 / epoch**；2 epoch = **6,209,854 token**。
- 原始 token（未截断）：3,957,698；p50 184 / p90 1,223 / p99 4,915 / max 5,012；301 条超过 2048。
- 公式金标 2,400 条（n/Vf/MRR/T 各 600）+ 缺参反问 300 条；六软件/许愿 2,000 条；图纸链 360；通用对话 73；**知识/推理 858 条**（102 条人工知识 + 756 条确定性推理）。
- 语义污染闸：**0 命中**（prompt hash + 8-gram Jaccard）。
- 严格数字闸：2,219 条命中，但**全部是 4 位数字碰撞**（年份/G 代码/随机公式值），0 条 prompt/answer 语义重复；保守子集 3,772 条也保留在 `reports/`。
- 公式留出集：**200 条**（n/Vf/MRR/T 各 50，数值与训练集不相交），用于验证“会算而不是背”。

**本次实机（V100-SXM2-32GB，¥1.98/h）推荐**：QLoRA NF4 + fp16，batch=1 / grad-accum=32，max_len=2048，2 epoch；按 6.21M token 与 V100 吞吐保守估算 **2–4 GPU 小时**，GPU 成本 **¥4–8**，加数据/存储总成本 **<¥30**。V100 无 bf16、无 FlashAttention-2，专用脚本 `scripts/train_virtu_v100.py` 已处理。

备选：L40S 48GB bf16 LoRA + max_len 5120（一条不截，见 §1.1），约 3.4–4.4 h / ¥15–30；RTX 4090 24GB QLoRA 约 2–3 h / ¥5–8，但要截断 301 条最长答案。

---

## 1. 语料实账（本次生成）

训练文件：`data/train/virtu_fix_v1/train/virtu_fix_text_sft_v1.jsonl`
Manifest：`data/train/virtu_fix_v1/virtu_fix_text_sft_v1.manifest.json`

| 来源 | 读取 | 保留 | 说明 |
|---|---:|---:|---|
| `master_cad_cam_six_software_train.jsonl` | 1,338 | 1,200 | 去重 138 |
| `wish_parametric_train.jsonl` | 838 | 800 | 去重 38 |
| `comprehensive_wish_cad_cam_sft_1200.jsonl` | 1,226 | **0** | 1,226 条全部与 master 重复，已丢弃 |
| `virtu_drawing_to_machining_chain_train.jsonl` | 2,213 | 360 | 1,711 条无文本 assistant（tool_calls/空），不适用于 `train_virtu.py` |
| `turing_conversational_master_train.jsonl` | 111 | 73 | 去重 38 |
| 公式金标 + 缺参 | — | 2,700 | n/Vf/MRR/T 各 600，缺参 300 |
| 知识/推理 | — | 858 | 102 条人工知识 + 756 条确定性推理（多步/公差/Taylor/时间/粗糙度） |
| **合计** | — | **5,991** | — |

Token 分布：

| 指标 | 值 |
|---|---:|
| prompt token | 701,266 |
| answer token | 3,250,441（82.1%，学习信号占比高） |
| full token | 3,957,698 |
| 2048 截断后 / epoch | 3,104,927 |
| p50 / p90 / p99 / max | 184 / 1,223 / 4,915 / 5,012 |
| 超过 2048 的样本 | 301 |

> 关键改进：旧 toolcall 语料 50.5% token 花在同一份 tools schema 上；本次文本语料 answer 占 83.7%，同样的钱更多花在“输出”上。

### 1.1 长度普查（2026-11-01 实测，推翻了一条旧结论）

用 `checkpoints/_base_qwen3_8b` 的 `Qwen2Tokenizer` 按**训练同款 ChatML 模板**逐条编码、不做截断，
5,991 行全部可用（0 行跳过），prompt 平均 117.1 token。复现：`python work/measure_corpus_length.py`
（本机 i5-12450H 单核 446 s，产物 `work/corpus_len_distribution.json`）；云上等价命令是
`python scripts/train_virtu_l40s.py --audit-lengths`（bootstrap 第 5b 步自动跑，约 5–8 分钟、¥0.5–1）。

| max_len | 被截断的行数 | 每 epoch 保留 token | 相比 5120 损失 |
|---:|---:|---:|---:|
| 1024 | 1,358 | 2,649,474 | −33.1% |
| 1536 | 312 | 2,948,192 | −25.5% |
| 2048（路线 C） | 301 | 3,104,927 | −21.5% |
| 3072 | 300 | 3,412,509 | −13.8% |
| 4096 | 300 | 3,719,709 | −6.0% |
| **5120（路线 A）** | **0** | **3,957,698** | 0 |

长度分桶：`<512` 3,958 行 / `512–1023` 674 / `1024–2047` 1,058 / `2048–4095` **1** / `≥4096` **300**。

三条结论：
1. **长尾是双峰的**：2048–4095 区间只有 1 行，"301 条长样本"里 300 条实际 ≥4096。所以原计划
   “max_len 4096 保留 301 条”是错的（它一条也保不住），路线 A 默认已改为 **5120**——这才是买 48GB 的理由。
2. **必须按长度分桶**：p50=184 而 max=5,012（27 倍差）。不分桶时一个 5k 样本配 3 个 180 样本的 batch
   里约 96% 是 padding，钱花在补零上；故路线 A 默认 `group_by_length=True`。
3. **路线 C 砍掉的正是最长的 CAM/公式代码答案**（21.5% 的 token 体量，只占 5% 的行数）。如果训练后
   A/B 显示路线 C 在长输出维度落后，**先怀疑这条截断**，不要直接下"模型不行"的结论。

---

## 2. 污染检查：两种口径都保留

```bash
# 语义硬闸（推荐用于放行）：prompt hash + 8-gram Jaccard
python virtu_eval/contamination_check.py \
  data/train/virtu_fix_v1/train/virtu_fix_text_sft_v1.jsonl \
  --eval-dir data/benchmark/virtu_eval_v1 \
  --ignore-gold-numeric \
  --drop data/train/virtu_fix_v1/reports/virtu_fix_text_sft_v1.semantic_clean.jsonl
# -> contaminated=0, PASS

# 严格数字闸（保守）：额外把 4+ 位 gold 数字碰撞算命中
python virtu_eval/contamination_check.py \
  data/train/virtu_fix_v1/train/virtu_fix_text_sft_v1.jsonl \
  --eval-dir data/benchmark/virtu_eval_v1 \
  --drop data/train/virtu_fix_v1/reports/virtu_fix_text_sft_v1.strict_clean.jsonl
# -> contaminated=2219, clean=3772
```

数字命中主要来自 master/wish/drawing 的年份/G 代码，以及公式/粗糙度的随机值；它们都不是 prompt/answer 复制。因此**训练用 5,991 条语义干净集**，同时保留 3,772 条严格子集作为保守对照。上线前用 200 条“改动数值”的公式留出集做记忆探测。

---

## 3. 知识/推理：已加入 858 条

当前语料为“公式 45% + 六软件/许愿 33% + 图纸 6% + 通用 1.2% + 知识/推理 14.3%”。知识/推理块包含：

- 102 条人工知识：材料/热处理、刀具、G 代码、CAD API、GD&T、夹具与安全；
- 756 条确定性推理：多步转速→进给→时间、公差配合、Taylor 寿命、循环时间、理论粗糙度；
- 全部由本地确定性计算/人工知识库生成，不依赖外部 token，答案可复算。

若要把 knowledge 从 47 拉到 60 以上仍不放心，可再用 ModelScope 免费教师补 300–500 条更贴近评测风格的问答；不加也应先跑一轮，用 §6 的 240 条 eval 判断真实差距。

---

## 4. 训练配置：三条路线（A 与 C 都已做成一键开训，B 仅退路）

### 路线 A（已落地为一键脚本）：L40S 48GB bf16 LoRA，max_len 5120

| 项 | 值 | 口径 |
|---|---|---|
| 基座 | `Qwen/Qwen3-8B`（base，与现有 LoRA 同源） | 实测（`adapter_config.json` 的 `base_model_name_or_path`） |
| 精度 | bf16 全精度基座 + LoRA，**不量化**；`--load-4bit` 只作 ≤24GB 退路 | 脚本默认 |
| LoRA | r=32，alpha=64，dropout=0.05，7 个线性层（与路线 C 同组 target） | 脚本默认 |
| batch / grad_accum | 2 / 16（有效 32）；阶梯只降不升，绝不在计费机上试加大 batch | 脚本默认 |
| max_len | 5120 = 实测零截断点；4096 仍砍 300 行，见 §1.1 | 实测 |
| lr / 调度 | 2e-4，cosine，warmup_ratio 0.03 | 预估（与既有 LoRA 同量级） |
| epochs | 2 | 计划 |
| 注意力 | flash-attn **不装**；有则 `flash_attention_2`，无则 `sdpa`，再退 `eager`（逐级 try） | 脚本实测行为 |
| 显存技巧 | gradient checkpointing + 长度分桶（`group_by_length`）；**不做 packing**——packing 会改 `load_and_tokenize` 的样本语义，破坏与路线 C 的可比性 | 脚本默认 |
| 估算 GPU 时 | **外推 3.4–4.4 h**。锚点①实测 A800：3.14M token / 2 epoch / 0.45 h ⇒ 本语料 7.92M token（5120 档）≈ 1.13 h；锚点②L40S/A800 bf16 吞吐比 ≈ 1/3（91.6 vs 312 TFLOPS、864 vs 2039 GB/s）⇒ ≈ 3.4 h。锚点③本仓实测 L40S 同族配方：408 步 / 2,745.8 s（见 `checkpoints/damodel_l40s_cad_cam_lora/training_receipt.json`），仅作"卡与配方合理"校验，不换算步数（那次的每步 token 量未记录） | 外推 |
| 估算 GPU 成本 | **预估**：3.4–4.4 h × 当日价；¥4.5/h ⇒ ¥15–20，¥7/h ⇒ ¥24–31。预算上限 ¥50（写进两份账本） | 预估 |
| 一键包 | `scripts/make_cloud_bundle.py --route a` + `scripts/bootstrap_l40s_train.sh` + `scripts/train_virtu_l40s.py` | 已建，`tests/test_cloud_bundle.py` 钉死 |

### 路线 B（极限省钱）：RTX 4090 24GB QLoRA，max_len 2048

| 项 | 值 |
|---|---|
| 量化 | 4-bit NF4 + double quant |
| batch / grad_accum | 2 / 16（有效 32） |
| max_len | 2048（301 条长样本被截断） |
| lr | 1e-4，paged AdamW 8bit |
| 估算 GPU 时 | 2–3 h |
| 估算 GPU 成本 | ¥5–8 |

### 路线 C（本次实机）：Tesla V100-SXM2-32GB，fp16 QLoRA

| 项 | 值 |
|---|---|
| 硬件 | V100-SXM2-32GB，¥1.98/h，90GB RAM，50GB 数据盘 |
| 精度 | 4-bit NF4 + double quant，compute dtype **fp16**（V100 无 bf16） |
| 注意力 | **sdpa/eager**；V100 不支持 FlashAttention-2，**不要安装 flash-attn** |
| batch / grad_accum | 1 / 32（有效 32） |
| max_len | 2048（301 条长样本截断；32GB 不建议上 4096） |
| lr / epochs | 1e-4 / 2，cosine，warmup 3% |
| 优化器 | **adamw_torch（sm70 最稳）**；可选 `paged_adamw_8bit` |
| 显存 | gradient checkpointing 开；4-bit 失败可 `--no-4bit`（fp16 LoRA，batch 1） |
| 估算 GPU 时 | 2–4 h（V100 比 L40S 慢，保守估） |
| 估算 GPU 成本 | ¥4–8；总成本 <¥30 |

> 三条路线都保持 **r=32/α=64**，输出单适配器；合并走 `merge_numpy.py --mode delta`，禁止多 LoRA `peft_linear`。

---

## 5. 工具调用：不混进文本 LoRA

`train_virtu.py` 只读取首条 user/assistant 的 `content`，会跳过 `tool_calls`。因此：

- 文本 LoRA 语料**不含 toolcall**（本次已排除）；
- 继续使用现有 `virtu-toolcall`（210 例 overall 72.56，toolcall 78.89）；
- 若要再提升工具调用，单独用 `scripts/train_virtu_toolcall.py` + `data/toolcall_optimal.jsonl`（2,316 条，实测 2 epoch / 0.45 h / ¥3.2 A800 口径），**不要**与文本 LoRA 混训或直加。
- 上线时：`VIRTU_VLLM_MODEL=virtu-fix-v1`，`VIRTU_TOOL_MODEL=virtu-toolcall`，两条通道独立归因。

---

## 6. 验收闸（不过不上线）

1. **240 条 `virtu_eval`**：gold 自测 100；语义污染 0。
2. **200 条公式留出**：`data/benchmark/virtu_fix_v1/formula_holdout_200.jsonl`，四类各 50，数值与训练集不相交；答案数值/单位 **200/200** 命中；缺参题必须反问。
3. **工具调用**：30 例 toolcall ≥ 90；210 例子集 overall ≥ 72.56，toolcall ≥ 78.89（不退化）。
4. **文本**：instruction ≥ 90，knowledge ≥ 60，reasoning ≥ 60，boundary ≥ 65；任一维度较 `virtu_ties_v1` 下降 > 3 分则拒绝。
5. 输出无西里尔/拉丁扩展乱码；同题多跑唯一率 > 95%；`served_model.last_model_used` 正确。
6. 合并：`merge_numpy --probe-amplitude` 的 delta/base 均值 1–5%，max < 20%。

---

## 7. 执行命令（数据已就绪）

### 7.0 一键开训（两条路线同一条流水线，只差 `--route`）

```bash
# 本地：打出该路线的可复现上传包（逐文件校验 sha256 + 语料 sha 闸 + bootstrap↔trainer 配对）
python scripts/make_cloud_bundle.py --route a     # L40S 48GB，bf16 未量化，max_len 5120
python scripts/make_cloud_bundle.py --route c     # V100 32GB，fp16 QLoRA NF4，max_len 2048
#   -> cloud_handoff/virtu_bundle_route_{A,C}.tar.gz（各 ~2.1MB / 11 个文件，解包后 virtu/）
#      账本 cloud_handoff/MANIFEST_ROUTE_{A,C}.json，同步登记 checkpoints/PROVENANCE.json
# 只校验不写盘：python scripts/make_cloud_bundle.py --route a --check

# 上传 tar 包到实例后，SSH 里只有这一条：
tar xzf virtu_bundle_route_A.tar.gz -C ~ && bash -n ~/virtu/scripts/bootstrap_l40s_train.sh \
  && bash ~/virtu/scripts/bootstrap_l40s_train.sh
tar xzf virtu_bundle_route_C.tar.gz -C ~ && bash -n ~/virtu/scripts/bootstrap_v100_train.sh \
  && bash ~/virtu/scripts/bootstrap_v100_train.sh
# bash -n 只解析不执行，用来确认解包后的脚本没有被传输/换行弄坏（本地无法跑 bash -n：
# 从 python 里 spawn bash 在这台 Windows 上会撞 GBK 解码或卡启动，所以解析检查放在主机侧）
```

两条 bootstrap 的阶段机完全同构，任何一步失败就把阶段名、日志尾 30 行写进
`$WORKDIR/TRAIN_STATUS.json` 并退出，不会静悄悄跑完再发现产物是空的：

| 阶段 | 路线 A（L40S） | 路线 C（V100） |
|---|---|---|
| 1 硬件/盘 | 非 48GB 级显存时提示改用 C；`$WORKDIR` 空闲 <30GB 直接 fail | 同左（<30GB 显存只告警） |
| 2 前置 | 恰好 1 个 jsonl + `train_virtu.py` + `requirements-l40s.txt` + trainer，**装依赖之前**拦 | 同左，换 `requirements-v100.txt` |
| 3 依赖 | venv → torch 2.5.0 cu124（阿里云退 PyPI）→ 断言 `cuda.is_available()` → requirements | 同左 |
| 4 基座 | ModelScope 拉 `Qwen/Qwen3-8B`（约 16GB，可续传），已存在则跳过 | 同左 |
| 5 preflight | 跑训练脚本自身的 sha256/行数/配置闸 | 同左 |
| 5b 截断普查 | `--audit-lengths`：逐条编码，报出每个 max_len 会砍掉多少条答案（约 5–8 分钟） | 该卡显存不够跑到 5120，普查只在 A 路线强制 |
| 6 冒烟 20 步 | 固定阶梯逐级降配：默认 → `--max-len 3072` → `3072 --batch 1` → `2048 --batch 1` → `--load-4bit` → `4bit 2048/batch1` | 按错误类型分派：OOM→`--max-len 1536`；NF4/bnb 报错→`--no-4bit`；兜底两者同用 |
| 7 正式训练 | `timeout`（默认 6h）包裹，冒烟选定档位自动带入；有 `checkpoint-*` 就 `--resume` | 同左（默认 8h） |
| 8 回执 | 断言 `training_receipt.json.status == COMPLETED`；`SMOKE_ONLY` 一律算失败，防止拿冒烟件去合并 | 同左 |

重复执行安全：`WORKDIR` 复用、基座跳过下载、断点续训；脚本最后一行打印本地合并命令。
可用环境变量：`WORKDIR BASE DATA OUTPUT VENV MAX_HOURS TORCH_INDEX PIP_INDEX SKIP_SMOKE`。

路线 A 与 C 的**数据语义强制同源**（同一个 `train_virtu.load_and_tokenize`、同一组 7 个 LoRA target、
同一条 `--data` 单文件闸、同一套回执状态字），这样两条路线的分数才可比；差异只允许出现在精度、
上下文长度与降配阶梯上。回归测试 `tests/test_cloud_bundle.py` 逐条钉死这些不变量。

```bash
# 1) 本地复核语料、留出集与上传包闸
python scripts/build_fix_text_corpus.py          # 已执行；可复跑
python scripts/build_formula_holdout.py          # 已执行；200 条
python -m pytest tests/test_arithmetic_guard.py tests/test_eval_runner.py -q
python -m pytest tests/test_cloud_bundle.py -q   # 两条路线的包闸（CRLF / sha 漂移 / 配对）

# 2a) L40S 48GB 手工分步（等价于 bootstrap 的第 5–7 步，用于单独复现某一环）
pip install -r requirements-l40s.txt
python scripts/train_virtu_l40s.py --base /root/models/Qwen3-8B \
  --data data/train/virtu_fix_v1/train --preflight
python scripts/train_virtu_l40s.py --base /root/models/Qwen3-8B \
  --data data/train/virtu_fix_v1/train --audit-lengths     # 截断普查，见 §1.1
python scripts/train_virtu_l40s.py --base /root/models/Qwen3-8B \
  --data data/train/virtu_fix_v1/train --smoke
python scripts/train_virtu_l40s.py --base /root/models/Qwen3-8B \
  --data data/train/virtu_fix_v1/train \
  --output /root/virtu_train/out/virtu_fix_v1_lora
# 默认 batch=2 / grad-accum=16（有效批 32）/ lr 2e-4 / max_len 5120 / bf16 未量化

# 2b) V100 32GB 手工分步
pip install -r requirements-v100.txt
python scripts/train_virtu_v100.py --base /root/models/Qwen3-8B \
  --data data/train/virtu_fix_v1/train --preflight
python scripts/train_virtu_v100.py --base /root/models/Qwen3-8B \
  --data data/train/virtu_fix_v1/train --smoke
python scripts/train_virtu_v100.py --base /root/models/Qwen3-8B \
  --data data/train/virtu_fix_v1/train \
  --output /root/virtu_train/out/virtu_fix_v1_lora

# 2c) 裸基座脚本（无 preflight/回执/阶梯，仅供对照，不用于计费训练）
python train_virtu.py --base /root/models/Qwen3-8B --data data/train/virtu_fix_v1/train \
  --mode lora --epochs 2 --batch 4 --grad-accum 4 --lr 2e-4 --max-len 4096 \
  --output /root/virtu_train/out/virtu_fix_v1

# 3) 下载 adapter 后合并 / 量化 / 注册
python scripts/merge_numpy.py --base checkpoints/_base_qwen3_8b \
  --out checkpoints/virtu_fix_v1 --mode delta \
  --lora checkpoints/virtu_fix_v1_lora --weight 1.0
python scripts/hf_to_gguf_numpy.py --model checkpoints/virtu_fix_v1 \
  --out checkpoints/virtu-fix-v1-q4_0.gguf
ollama create virtu-fix-v1 -f scripts/Modelfile.virtu-fix-v1

# 4) 评测 / A/B（新模型 vs ties-v1 vs base；工具臂固定 toolcall）
python -m virtu_eval.runner --arm ollama_virtu_fix_v1 --out-dir runs/eval/virtu_fix_v1

# 5) 上线（过闸后）
# scripts/run_virtu_service.py: VIRTU_VLLM_MODEL="virtu-fix-v1"
# VIRTU_TOOL_MODEL="virtu-toolcall"; restart 8000; check /v1/models
```

---

## 8. 成本总表（本次实测 token 口径）

| 项 | V100 32GB QLoRA（本次） | 4090 QLoRA | L40S bf16 LoRA |
|---|---:|---:|---:|
| 训练 token（2 epoch） | 6.21M | 6.21M | 6.21M |
| 估算 GPU 时 | 2–4 h | 2–3 h | 1.5–2.5 h |
| GPU 成本（估算） | ¥4–8 | ¥5–8 | ¥7–12 |
| 教师/数据生成 | ¥0–10 | ¥0–10 | ¥0–10 |
| 存储/流量 | ¥5 | ¥5 | ¥5 |
| 知识/推理块（已生成 858 条） | ¥0 | ¥0 | ¥0 |
| **合计（估算）** | **¥9–23** | **¥12–28** | **¥14–32** |

对照：`TRAIN_ACCELERATION.md` 实测 3.14M token / 2 epoch / 0.45 h / ¥3.2（A800）；本语料 6.21M token，按同吞吐约 0.89 h。上表 GPU 时已按 V100/4090/L40S 吞吐折扣放大，属于保守估算。

---

## 9. 风险与回滚

| 风险 | 规避 |
|---|---|
| 数字碰撞被误当泄漏 | 语义闸 0；严格数字闸 2,219 全部 gold_num-only；用 200 条改动数值留出集做记忆探测 |
| 公式过拟合模板 | 2,400 条随机值 + 3 种问法 + 缺参反问；200 条新留出 100% 才收 |
| 知识/推理不涨 | 已生成 858 条（102 知识 + 756 推理）；若 240 条 eval 仍 knowledge<60，再用教师补 300–500 条，不预先谎报 |
| 长代码被截断 | 路线 A 用 max_len 5120 做到零截断；路线 B/C 明确接受 301 条截断并在 A/B 归因时优先考虑它 |
| 灾难性遗忘 | 保留 73 条通用对话；A/B 对比 ties-v1/base；任一维度跌 >3 分拒绝 |
| 多 LoRA 合并乱码 | 只合单适配器 delta；合并前 `--probe-amplitude`，max>20% 停 |
| V100 无 bf16/FlashAttention-2 | 专用脚本强制 fp16 + sdpa/eager；不装 flash-attn；默认 `adamw_torch`；4-bit 失败用 `--no-4bit`；可选 `paged_adamw_8bit` |
| 云厂商价格/可用性 | 按需租、预算上限 ¥50、checkpoint 到持久盘、超时停机 |

回滚：`run_virtu_service.py` 改回 `virtu-ties-v1`；新产物不过闸则移入 `checkpoints/_broken/`，不覆盖 canonical。

---

## 10. 明确不做

1. 不做 8B 全参微调（多卡 80GB，>¥500，遗忘风险高）。
2. 不再把多个 LoRA 用 `peft_linear` 直加（已实测乱码，Σw=5.7）。
3. 不用 240 条评测原题、36 条盲测原题、200 条公式留出集做训练。
4. 不训练 `virtu_omni_10b_base.pt`（0.58B 占位）或 LoopTransformer（与 Qwen3 键空间交集 0）。
5. 不把 toolcall 数据混进 `train_virtu.py`（会跳过 tool_calls），也不把视觉 LoRA 合进文本模型。
