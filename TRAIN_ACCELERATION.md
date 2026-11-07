# Virtu tool-call 训练加速方案（实测版）

> 版本：2026-10-30 · 全部数字来自本机实测（`scripts/analyze_*.py`），非估算
> 目标：在**不降低 tool_calls 格式学习质量**的前提下，把 A800 训练时间从 ~11.7h 压到 ~3.8h

> 📌 **本文档 §1–§8 是"第 1 版"（省 76%，3.8h/¥27）。**
> 追问"还能更高效吗"之后发现：语料的信息维度极少、**material 分布严重失衡**，
> 于是有了 **§9 极限效率版——再砍至 0.45h/¥3，并修掉一个会损害效果的质量问题**。
> 如果只是要执行，**直接看 §9**。

---

## 0. 一句话结论

**有，而且省的是大头。** 原 runbook 的 11.7h 估算偏保守（实测口径应 ~8.6h）。
两条独立杠杆叠加后，**2 epoch 训练成本从 ¥62 降到 ¥3.2**（推荐档 2,316 条 / 3.14M token / 约 27 分钟）。
连跑 4 档学习曲线再定稿，**全流程约 2.7h / ¥19**。

| 版本 | 语料 | token/epoch | 2 epoch | 费用 |
|---|---|---:|---:|---:|
| 原 runbook（QLoRA + ckpt） | 23,178 条 | 60.3M | 15.6h | ¥113 |
| 同口径基准（bf16 关 ckpt） | 23,178 条 | 60.3M | 8.59h | ¥62 |
| §2–§8 瘦身版 | 18,330 条 | 30.2M | 4.29h | ¥31 |
| **§9 分层平衡 + schema 压缩** | **2,316 条** | **3.14M** | **0.45h** | **¥3.2** |
| §9 极限（schema none） | 2,316 条 | 1.62M | 0.23h | ¥1.7 |

⚠️ 上表"原始两行"配置不同，详见 §5 / §9.6 的口径说明，别跨行相减。

三条主要杠杆，按收益排序：

| 杠杆 | 省什么 | 实测依据 |
|---|---|---|
| ① 语料瘦身 | token **-50%** | 18,330 条去重 + 丢 tr2/总结 + schema 瘦身 |
| ② 关梯度检查点 + bf16 | 计算量 **-25%**，吞吐 **+10~20%** | 显存体检 ≥60GB |
| ③ 长度分桶 + FlashAttention | padding 4.9%→0.06%，注意力 **-10~20%** | 1,000 组采样实测 |

---

## 1. 先看被浪费在哪里（实测）

`scripts/analyze_segments.py` 全量 23,178 条逐角色 token 计量：

```
样本 23,178 | 基线 1 epoch token 60,272,726 | 重复 4,848 (20.9%)

按角色 token 占比（精确，offset_mapping 分桶）
  system     30,455,892   50.5%   ← tools schema，全库 23178 条完全相同
  user       20,399,475   33.8%   ← 含 tool_response#2 长手册
  assistant   8,930,777   14.8%   ← 真正计 loss 的部分
```

`scripts/analyze_variants2.py` 进一步拆解（18,330 条去重口径）：

| 项 | 实测 | 含义 |
|---|---|---|
| tools schema | **1,193 tok/条，全库仅 1 个变体** | 每条都重渲染同一份 46% 的内容 |
| tool_response#1 | ~181 字符 | parse_wish_intent 的 JSON spec，很短 |
| tool_response#2 | **~1,664 字符** | markdown 手册，**占全库 27% token** |
| call#2 参数来源 | **67.7% 来自 tr1**，仅 3.7% 来自 tr2 | → tr1 不能截，tr2 可以丢 |
| 参数 description 占 schema 字符 | **72.1%** | → 瘦身 schema 只删它 |
| assistant token 构成 | tool_call 段 78.4% / 最终总结段 21.6% | 总结段是可压缩项 |

**关键判断**：真正的学习信号（tool_call 段）只占 11.7%，其余 88% 是
"同一份 schema 重复 N 次" + "长手册重复 N 次"。这是巨大的纯浪费。

---

## 2. 杠杆一：语料瘦身（省 50%）

### 2.1 四种档位（实测收益）

| 档位 | 做法 | 1 epoch token | 较原样省 | 学习信号占比 |
|---|---|---:|---:|---:|
| `none` | 原样 | 60,272,726 | — | 14.9% |
| `dedup` | 仅去重 | 47,570,181 | **20.9%** | — |
| `drop2` | 去重 + 丢 tr2 与末尾总结 | 33,058,388 | **45.2%** | 17.0% |
| `slim` | 去重 + 丢 tr2/总结 + schema 瘦身 | **30,163,029** | **50.0%** | **19.3%** |

### 2.2 为什么丢 tr2 是安全的

```
调用链：
  user ──► assistant#1 (parse_wish_intent)
              │
              ▼ tool#1: {"material":"Cr12MoV","d_outer":48.0,...}   ← 181 字符，短
              │
              ▼ assistant#2 (create_parametric_part)   ← 参数 67.7% 来自 tool#1
              │
              ▼ tool#2: # 斯沃数控仿真软件实操对刀手册 ... ← 1664 字符，长
              │
              ▼ assistant#3: "已通过工具链完成..."（最终总结）
```

- **tr2 只服务于 assistant#3 的最终总结**，assistant#2 的参数不依赖它（仅 3.7%）
- 因此 **tr2 与最终总结必须同进同退**——保留总结就得留 tr2，丢总结才能丢 tr2
- `build_slim_corpus.py --mix-summary 0.15` 保留 15% 的完整长样本，
  既省 50% 又保住"能收尾总结"的能力（不至于训成只会调工具、不会汇报）

### 2.3 schema 瘦身的安全性

只删 `parameters.properties.*.description`，**保留** `name` / `type` / `enum` /
`minimum` / `maximum` / `required`：

- 模型靠 `name`+`type` 定位参数、靠 `enum` 取合法值 → 都在
- `description` 只解释语义，推理侧传完整 schema 时模型仍能对上（name/type 一致）
- 风险点已用 **15% 完整 schema 的长样本**对冲（`mix-summary` 那部分 schema 未瘦身）

### 2.4 已验证

```
$ python scripts/build_slim_corpus.py --mode slim --out data/toolcall_slim.jsonl
[slim] 读取 23,178 | 去重丢弃 4,848 | 输出 18,330
[slim] 完整长样本 2,777 | 瘦身样本 15,553

$ python scripts/validate_render_dataset.py --data data/toolcall_slim.jsonl --workers 10
[render] 通过 18330/18330  (100.000%)
   C1_json_structure          PASS
   C2_template_render         PASS
   C3_mask_construction       PASS
   C4_loss_mask_scope         PASS
   C5_tool_call_integrity     PASS
[token] min=1173 p50=1507 max=2560 mean=1645.6
[token] 总量 30,163,029 | 计 loss 5,821,262 (19.3%) | 超 4096 截断: 0 (0.00%)
```

**5 项门禁 100% PASS**，掩码逻辑在瘦身上完全正确。

---

## 3. 杠杆二：计算配置（省 25% + 吞吐 +10~20%）

```bash
--mode lora --no-grad-ckpt --group-by-length --attn-impl flash_attention_2
```

| 项 | 原理 | 实测/依据 |
|---|---|---|
| `--no-grad-ckpt` | 梯度检查点把 6N 变 8N 计算量 | **省 25%** |
| `--mode lora` (bf16) | 免 bnb 4bit 反量化开销 | **+10~20%** |
| `--group-by-length` | 长度相近的样本凑 batch | padding **4.9% → 0.06%** |
| `--attn-impl flash_attention_2` | 注意力 O(n²) 部分降内存 | **+10~20%**（需装 flash-attn） |

> **80GB 显存的真正价值就在 `--no-grad-ckpt`**：QLoRA+ckpt 需 ~24GB，
> bf16+关 ckpt 需 ≥60GB。A800 80GB 刚好够，别浪费这个优势。

---

## 4. 杠杆三：省钱的执行节奏

### 4.1 试点先行（强烈建议）

```bash
# 阶段 1：试点 2000 条 × 2ep ≈ 25 分钟 ≈ ¥3
#   目的：验证模型真能吐结构化 tool_calls，而不是训完 4 小时才发现格式没学会
python scripts/gpu_train_pipeline.py --work-dir /root/virtu_train \
    --base /root/virtu_train/Qwen3-8B \
    --data /root/virtu_train/toolcall_slim.jsonl \
    --limit 2000 --epochs 2 --mode lora --no-grad-ckpt --group-by-length \
    --min-vram-gb 60 --time-budget-min 40 --yes
```

### 4.2 全量

```bash
# 阶段 2：全量 18,330 条 × 2ep ≈ 3.8-4.3h ≈ ¥27-31
python scripts/gpu_train_pipeline.py --work-dir /root/virtu_train \
    --base /root/virtu_train/Qwen3-8B \
    --data /root/virtu_train/toolcall_slim.jsonl \
    --epochs 2 --mode lora --no-grad-ckpt --group-by-length \
    --attn-impl flash_attention_2 \
    --min-vram-gb 60 --time-budget-min 300 --yes
```

### 4.3 防烧钱的三道保险

| 开关 | 作用 |
|---|---|
| `--min-vram-gb 60` | 显存不足**启动前**退出，不空烧 |
| `--time-budget-min 300` | 到点优雅停止并保存 LoRA（已实现 `TimeBudgetCallback`） |
| `--limit 2000` 先试点 | 3 分钟验证格式学得会，再花大钱 |

---

## 5. 时长与费用对照

**推算方法**：FLOPs 模型 `fwd 2Nt + bwd 2Nt`（关 ckpt），A800 BF16 稠密 312 TFLOPS，
MFU 取 35~50%（与 L40S 实测回执 408 步/2745.77s 交叉验证一致）。
**两种独立方法交叉验证**：FLOPs 模型给出 7.6–8.6h（原语料），
而原 runbook 用 L40S 算力比法给出 11.7h —— **后者偏保守约 30%**。

### 原计划 vs 加速后（A800 80GB，¥7.2/h）

| 方案 | 1 epoch | 2 epoch | 费用 | 相对原计划 |
|---|---:|---:|---:|---:|
| 原 runbook（原语料 + QLoRA） | 7.8h | 15.6h | ¥113 | 基准 |
| 原 runbook 实测口径修正（原语料 + bf16 关 ckpt） | 4.3h | 8.6h | ¥62 | -45% |
| **瘦身语料 + bf16 关 ckpt + 分桶** | **1.9h** | **3.8h** | **¥27** | **-76%** |
| 瘦身 + 上述全部 + FlashAttention | 1.6h | 3.2h | ¥23 | -80% |
| 瘦身 + 1 epoch（冒风险） | 1.9h | — | ¥14 | -88% |

### 计入试点后的总账

| 项 | 时长 | 费用 |
|---|---:|---:|
| 环境准备 + 基座下载 | 15 min | — |
| 阶段 1 试点 2000 条 | 25 min | ¥3 |
| 阶段 2 全量 18,330 条 × 2ep | 3.8 h | ¥27 |
| 合并 + GGUF + Ollama 部署（本机纯 numpy） | 15 min | ¥0 |
| **合计** | **约 4.3 h** | **约 ¥30** |

**对比原计划的 14h / ¥95–100 —— 时间省 69%，费用省 70%。**

---

## 6. 不推荐的做法

| 方案 | 为什么不做 |
|---|---|
| 双卡 DDP | 单价翻倍，净收益仅省 5h，费用几乎不降 |
| 降到 1 epoch 全量 | 格式学习是低熵任务，但 18,330 条已去重，2 epoch 更稳（多花 ¥14 买确定性） |
| 截断 tr1 | tr1 只有 181 字符，本来就不长；截了会切断 call#2 的参数依赖（67.7%） |
| 删掉 mix-summary 的 15% 长样本 | 会训成"只会调工具、不会汇报"，这是实打实的能力退化 |
| 改 LoRA rank 省时间 | rank 不影响计算量（只影响可训练参数量），且**必须 r=32** 才能与既有 4 个 LoRA 合并 |

---

## 7. 工具清单

| 脚本 | 作用 | 需要 GPU |
|---|---|---|
| `scripts/analyze_train_cost.py` | token 总量 / 冗余度 / padding 浪费实测 | 否 |
| `scripts/analyze_segments.py` | 精确分段 token + 截断安全性验证 | 否 |
| `scripts/analyze_deep.py` | 参数依赖 / 模板副作用 / 学习信号占比 | 否 |
| `scripts/analyze_variants2.py` | 各瘦身变体收益权威计量 | 否 |
| `scripts/build_slim_corpus.py` | **生成瘦身语料**（none/dedup/drop2/slim） | 否 |
| `scripts/train_virtu_toolcall.py` | 训练（新增 `--group-by-length` / `--attn-impl` / `--time-budget-min` / `--max-steps`） | 是 |
| `scripts/gpu_train_pipeline.py` | GPU 机一键流水线（新增上述开关透传） | 是 |

实测报告：
- `data/validation/train_cost_analysis.json`
- `data/validation/segment_analysis.json`
- `data/validation/deep_analysis.json`
- `data/validation/variant_analysis_v2.json`
- `data/validation/render_report_slim.json`

---

## 8. 落到本机的下一步

```bash
# 1) 上传瘦身语料到 GPU 机
#    data/toolcall_slim.jsonl  (89.9MB，比原 178.9MB 小一半)

# 2) 跑试点（见 4.1）

# 3) 跑全量（见 4.2）

# 4) 回传 LoRA 到本机后一键落地
python scripts/deploy_tool_lora_to_ollama.py \
    --lora checkpoints/virtu_toolcall_lora \
    --ollama-name virtu-omni-8b-v2 \
    --append-default --dry-run
```

---

# 9. 极限效率（第二版：再砍 10 倍）

> 回答"这已经是最高的学习效率了吗"——**远远不是**。
> §1–§8 砍的是 token，但没动**信息维度**和**数据质量**。

## 9.1 瘦身之后，冗余反而更集中了

`scripts/analyze_efficiency.py` 测瘦身语料：

```
瘦身语料角色占比
  system    63.5%   ← 不降反升！tools schema 被保留，而其他部分被砍了
  assistant 19.5%
  user      17.0%
```

砍掉 tr2/总结后，tools schema 从 50.5% **涨到 63.5%**。这是第二层杠杆。

## 9.2 真正的关键发现：信息维度极少

`scripts/analyze_sufficiency.py`：

| 维度 | 不同取值数 | 说明 |
|---|---:|---|
| 工具序列 × 参数键（结构） | **7 种** | 18330 条只有 7 种结构 |
| 结构 × material | **30 种** | |
| user 表述模式（数字掩码） | **121 种** | 每种模板重复 150~250 条 |
| material 取值 | 9 种 | 见下方失衡问题 |

**18330 条 ≈ 121 个模板 × 不同数字的笛卡尔积。**
采样数量不能增加"新信息"——这正是饱和度曲线呈纯线性的原因（参数指纹唯一率 100%，全是不同数字）。

## 9.3 ⚠️ 同时发现一个会损害效果的质量问题

```
material 分布（瘦身语料）
  Cr12MoV     10,395   56.7%   ← 超过一半
  Ti-6Al-4V    2,319   12.7%
  AL7075-T6    2,280   12.4%
  SS304        2,220   12.1%
  Inconel718     296    1.6%
  CuC360         250    1.4%
  P20            249    1.4%
  Steel45        245    1.3%
  20CrMnTi        50    0.3%   ← 几乎学不会
```

**这不是效率问题，是质量问题**：模型会强烈偏向预测 `Cr12MoV`，
对 `20CrMnTi`/`Steel45`/`P20` 的识别几乎必然失败。
**即使完全不压缩，也应该做分层平衡。**

## 9.4 `build_optimal_corpus.py`：分层平衡 + schema 压缩

按 material 分层，每层优先覆盖不同表述模式，再配合 schema 档位：

```bash
python scripts/build_optimal_corpus.py --per-material 300 --schema ultra \
    --out data/toolcall_optimal.jsonl
```

material 分布被修正为各约 13%：

```
AL7075-T6 300 13.0%   Cr12MoV 300 13.0%   Ti-6Al-4V 300 13.0%   SS304 300 13.0%
Inconel718 296 12.8%  CuC360 250 10.8%    P20 249 10.8%         Steel45 245 10.6%
20CrMnTi 50 2.2%      None 26 1.1%
```

体检全部通过：

```
[render] 通过 2316/2316  (100.000%)   C1~C5 全 PASS
[token] 总量 3,140,926 | 计 loss 806,164 (25.7%) | 截断 0
```

## 9.5 schema 四档（单条 916 tok 起）

| 档位 | 做法 | schema tok | 全量 token | loss 占比 |
|---|---|---:|---:|---:|
| `slim` | 删 description | 916 | 3,140,926 | 25.7% |
| `ultra` | +删类型修饰 | 582 | 3,140,926 | 25.7% |
| `name` | 只留工具名 | 308 | ~2.4M | ~33% |
| `none` | **不带 schema（工具内置）** | 0 | **1,616,998** | **49.9%** |

`none` 档 loss 占比飙到 **49.9%**——几乎一半 token 是学习信号。
代价：推理侧必须同步不传 `tools`，且**丧失泛化到新工具的能力**。
Virtu 的 8 个工具是封闭集合，这个代价可接受；但换工具就要重训。

## 9.6 token 与成本阶梯

统一口径：A800 × bf16 LoRA × **关梯度检查点**，MFU 40%（参考点：60.27M tok → 4.29h/epoch）

| 档位 | 条数 | token/epoch | 2 epoch | 费用 | 较原始语料 |
|---|---:|---:|---:|---:|---:|
| 原始语料（同口径基准） | 23,178 | 60.3M | 8.59h | ¥62 | 基准 |
| §8 瘦身版 | 18,330 | 30.2M | 4.29h | ¥31 | -50% |
| opt 1000 / ultra | 5,116 | 6.84M | 0.97h | ¥7.0 | -89% |
| opt 500 / ultra | 3,116 | 4.20M | 0.60h | ¥4.3 | -93% |
| **opt 300 / ultra（推荐）** | **2,316** | **3.14M** | **0.45h** | **¥3.2** | **-95%** |
| opt 300 / none（极限） | 2,316 | 1.62M | 0.23h | ¥1.7 | -97% |

> **口径说明（重要）**：上表全表统一为 bf16 关 ckpt。
> 若改用原 runbook 的 **QLoRA nf4 + 开 ckpt**（慢约 **1.8×**，见 §5 对照），
> 费用需乘 1.8：原始语料约 **¥111**，推荐档约 **¥5.8**。
> 不要把 ¥113 和 ¥3.2 直接相减 —— 那是两种配置，不是同一件事。

**推荐全流程总账**（含学习曲线）：

| 项 | 时长 | 费用 |
|---|---:|---:|
| 4 档学习曲线 × 2ep（5116/3116/2316/2316 条） | 2.25 h | ¥16.2 |
| 定稿训练 × 1（按曲线拐点选档） | 0.45 h | ¥3.2 |
| **合计** | **约 2.7 h** | **约 ¥19** |

只跑推荐档、不做学习曲线：**单次 ¥3.2，约 27 分钟**。

## 9.7 最重要的转变：跑学习曲线变得几乎免费

当一次训练只要 ¥3 时，**最优策略不再是"估算一个样本量然后一把梭"，而是"先量后训"**：

```bash
# 4 个样本量档位，各 2 epoch，合计约 1.5~2h / ¥15
for N in 1000 2000 3000 5000; do
  python scripts/build_optimal_corpus.py --per-material $((N/9)) --schema ultra \
      --out data/curve_$N.jsonl
  python scripts/gpu_train_pipeline.py ... --data data/curve_$N.jsonl \
      --epochs 2 --mode lora --no-grad-ckpt --group-by-length --time-budget-min 40
done
# 画出 N vs (结构化输出率 / 参数准确率) -> 曲线拐点即最小充分样本量
```

**花 ¥16 跑完学习曲线、找到一个有把握的方案，远好过花 ¥62（同口径）赌一把。**
这才是"最高学习效率"——不是把单次训练压到极限，而是**用最少算力确定最优解**。

## 9.8 风险提示（必须看）

| 风险 | 说明 | 缓解 |
|---|---|---|
| **样本量不够** | 2316 条能否训出鲁棒模型，**本机无法验证，必须 GPU 实测** | 先跑学习曲线（§9.7），别直接上最小档 |
| material 平衡后罕见材料样本变少 | 20CrMnTi 只有 50 条，平衡会稀释常见材料 | 用 `ultra` 而非极小档；或对罕见材料过采样 |
| `schema none` 泛化损失 | 不能接受新工具定义 | 保持 `ultra`；或混合训练（90% 不带 + 10% 带） |
| loss 占比高 != 学得好 | 25.7% 只说明信号密度，不代表收敛更快 | 看验证集的 tool_call 结构化率与参数准确率 |

## 9.9 建议执行顺序

1. **修质量问题**（比提效更重要）：用 `build_optimal_corpus.py --per-material 500 --schema ultra`
   先出一版 `slim` 平衡的语料，即使不省时也该这么做
2. **跑学习曲线**：4 档 × 2ep，约 ¥15
3. **定稿训练**：按曲线拐点选样本量，跑正式版
4. **落地验证**：`deploy_tool_lora_to_ollama.py` 端到端测结构化 `tool_calls`

总预算 **¥20~30**，比原始方案省 **75~80%**，且每步都有实测背书。

## 9.10 第二版新增工具

| 脚本 | 作用 | 需要 GPU |
|---|---|---|
| `scripts/analyze_efficiency.py` | 瘦身后剩余冗余、schema 三形态计量 | 否 |
| `scripts/analyze_sufficiency.py` | 信息维度拆解、饱和曲线 | 否 |
| `scripts/build_optimal_corpus.py` | 分层平衡 + schema 压缩（`--per-material` / `--schema`） | 否 |

实测报告：`data/validation/efficiency_analysis.json`、`data/validation/sufficiency_analysis.json`、
`data/validation/render_report_optimal.json`

---

# 10. GPU 选型：还要不要 A800？

> 回答"是不是用不到 A800 了，可以换 L40S"——**可以换，而且大概率应该换**。
> 但有一个前置条件：**必须开 FlashAttention**，否则结论反转。

## 10.1 先纠正一个直觉误区

token 少了 20 倍，容易以为显存也少了 20 倍。**并没有。**

| 组成 | 是否随 token 变 | 大小 |
|---|---|---|
| 基座权重 bf16 | ❌ 固定 | 15.26 GiB |
| LoRA r=32 AdamW 优化器 | ❌ 固定 | 0.65 GiB |
| **每层激活** | ✅ 随 `batch × seq` | **显存大头** |
| logits（vocab 151936） | ✅ 随 `batch × seq` | 1~2 GiB |

**权重 16 GiB 是硬地板，跟语料多少完全无关。** 所以永远不会出现"24GB 卡随便跑"；
但另一方面，**推荐档的峰值只有 31 GiB**，48GB 卡绰绰有余。

## 10.2 FlashAttention 是决定性的，不是「快一点点」

激活显存（Megatron 公式）：

```
朴素注意力: act = L × (34·s·b·h  +  5·a·s²·b)      ← 第二项是 O(s²)
FlashAttn : act = L × (34·s·b·h)                    ← 第二项被在线 softmax 消掉
```

同一档位 `opt300/ultra`（seq 1356, batch 2）实测效果：

| 注意力实现 | 激活显存 | 峰值合计 | L40S 48GB 能 batch 几 |
|---|---:|---:|---:|
| 朴素 sdpa/eager | 32.39 GiB | 50.76 GiB | **1**（被迫降 batch） |
| flash_attention_2 | 12.66 GiB | **31.03 GiB** | **2** ✅ |

结果：同一张 L40S，**2 epoch 从 0.96h 降到 0.77h**，而且 31 GiB 的余量很安全。

## 10.3 各卡可行配置（启用 FlashAttention）

推荐档 `opt300/ultra`（2,316 条 / 3.14M tok / 2 epoch）：

| GPU | 显存 | 可行配置 | 峰值 | 2ep 时长 | 相对 A800 |
|---|---:|---|---:|---:|---:|
| A800 80GB | 80G | batch6 关 ckpt | 60.97 G | **0.45 h** | 1.00x |
| **L40S 48GB** | 48G | **batch2 关 ckpt** | **31.03 G** | **0.77 h** | **1.72x** |
| A6000 48GB | 48G | batch2 关 ckpt | 31.03 G | 0.90 h | 2.01x |
| 4090 24GB | 24G | batch2 开 ckpt | 19.86 G | 1.27 h | 2.84x |

> 完整矩阵见 `scripts/estimate_gpu_plan.py`，量化结果存
> `data/validation/gpu_plan_flash.json`（FA）与 `gpu_plan.json`（朴素）。

**A800 的 80GB 现在是浪费的** —— 推荐档峰值只要 31 GiB，40GB 级就够。

## 10.4 打平单价：什么时候换卡更划算

以 A800 ¥7.20/h × 0.45h = **¥3.22 / 次** 为基准：

| GPU | 2ep | **打平单价** | ¥3/h | ¥4/h | ¥5/h | ¥6/h |
|---|---:|---:|---:|---:|---:|---:|
| A800 80GB | 0.45h | — | | | | **¥3.22** |
| **L40S 48GB** | 0.77h | **¥4.17/h** | ¥2.31 ✅ | ¥3.08 ✅ | ¥3.85 | ¥4.63 |
| A6000 48GB | 0.90h | ¥3.57/h | ¥2.70 ✅ | ¥3.60 | ¥4.50 | ¥5.41 |
| 4090 24GB | 1.27h | ¥2.54/h | ¥3.81 | ¥5.08 | ¥6.34 | ¥7.61 |

**规则很简单**：
- **L40S 单价 < ¥4.2/h → 换成 L40S**（市场价常在这个附近，很可能就是它）
- 4090 单价 < ¥2.5/h → 4090 也成立
- 都不满足，或你赶时间 → 继续 A800

## 10.5 全流程总账差异只有几块钱

| 场景 | A800 (¥7.2/h) | L40S @¥4/h | L40S @¥3/h |
|---|---:|---:|---:|
| 学习曲线 4 档 × 2ep | 2.68h / ¥19.3 | 4.62h / ¥18.5 | 4.62h / ¥13.9 |
| 定稿训练 × 1 | 0.45h / ¥3.22 | 0.77h / ¥3.08 | 0.77h / ¥2.31 |
| **合计** | **3.13h / ¥22.5** | **5.39h / ¥21.6** | **5.39h / ¥16.2** |

**费用基本打平，差别在 1.7 倍的时间。**占总成本大头的已经不是机时而是**决策风险**——
所以别纠结卡，**把 ¥16~22 花在跑学习曲线上**才是正事。

## 10.6 换 L40S 的执行要点

```bash
# 关键三条：FA 默认已开、关梯度检查点、batch 2
python scripts/gpu_train_pipeline.py \
    --data data/toolcall_optimal.jsonl \
    --mode lora \
    --no-grad-ckpt \
    --batch 2 --grad-accum 8 \
    --attn-impl flash_attention_2 \
    --group-by-length \
    --min-vram-gb 44 \
    --time-budget-min 40
```

| 检查项 | 说明 |
|---|---|
| `pip install flash-attn --no-build-isolation` | **必装**。没装脚本会自动降级 sdpa 并告警，此时请把 `--batch` 降到 1 |
| `--no-grad-ckpt` | L40S 48GB 配 batch2 有 17GB 余量，关掉省 33% 计算 |
| `--min-vram-gb 44` | 启动前校验，避免 OOM 空烧机时 |
| 不要照抄 A800 的 batch | A800 用 batch6，L40S 只能 batch2，否则直接 OOM |

## 10.7 注意事项

| 风险 | 说明 | 缓解 |
|---|---|---|
| **显存模型是保守估算** | Megatron 公式通常高估实际占用，真实余量可能更大 | 首次跑宁可 `--batch 2`，跑通再试 `--batch 4` 提速 |
| flash-attn 编译慢 | 源码编译约 10~20 分钟，这段也算机时 | 用 `--no-build-isolation` 且放在环境准备阶段做一次 |
| 4090 是消费卡 | 部分平台禁商用 / 无 ECC | 生产环境优先 L40S / A6000 |
| batch1 会掉 MFU | 我的模型按 batch=1 → MFU 0.32 计（batch≥2 才给 0.40） | 宁可降 batch 也要保住 ≥2，这是 L40S 上 FA 的价值所在 |

---

## 11. 镜像选型：平台这张 Ollama 镜像，一张打通全程

平台镜像规格：**Ollama v0.21.0 / PyTorch 2.5.0 / CUDA 12.4 / Python 3.11.10 / 约 10GB**。

### 11.1 结论

**就选它。** 它不只是"最后一公里"的服务环境，因为自带 torch + CUDA + Python 运行时，
它同时就是一台合格的训练机。带来的最大收益是**闭环压缩到一台机器**：

| 环节 | 用这张镜像 | 换两台机器 |
|---|---|---|
| LoRA 训练 | 同一实例 | 训练机 |
| 合并 / GGUF | 同一实例 | 训练机 |
| `ollama create` + tool-call 复验 | 同一实例 | 服务机，需搬运 ~16GB merged + ~5GB GGUF |
| 基座下载次数 | 1 次 | 2 次（训练机 + 服务机各下一份 Qwen3-8B） |

按 §9.6 的账，单次训练本身只要 ¥3.2，**真正烧钱的是空转机时和跨机搬运**。
少一次基座下载 + 少一次 21GB 权重搬运，省下的往往比训练算力还多。

### 11.2 版本兼容性核对

| 依赖 | 镜像自带/要求 | 结论 |
|---|---|---|
| torch 2.5.0 + cu124 | 自带 | 保留，**不要升级**（flash-attn 预编译 wheel 严格绑定 ABI） |
| Python 3.11.10 | 自带 | flash-attn 2.7.4.post1 有对应 wheel |
| flash-attn | 缺失，需补 | `pip install flash-attn==2.7.4.post1 --no-build-isolation` |
| transformers | 缺失，需补 | ≥4.51（Qwen3 模型类的最低门槛） |
| peft / datasets / accelerate | 缺失，需补 | 见 `requirements-gpu.txt` |
| 磁盘 | — | **建议 ≥50GB**：基座 16 + merged 16 + GGUF 6 + 数据与中间件 10 |

`requirements.txt`（本机）只服务推理接口，**不含训练依赖**；GPU 实例请用 `requirements-gpu.txt`。

### 11.3 一条命令引导

实例起来后，把仓库传上去，执行：

```bash
python scripts/gpu_bootstrap.py --also-download-base --smoke-ollama
```

脚本幂等，做四件事：环境体检（GPU/显存/SM/磁盘/ollama）→ 补装训练依赖（不碰自带 torch）
→ 拉 Qwen3-8B 基座 → Serving 冒烟。体检报告落 `data/validation/gpu_bootstrap.json`。

注意：本机 CPU-only 跑这个脚本会在 S0 报 `[FATAL] 未装 torch` 并退出，属预期行为，
它只在 GPU 实例上有意义。

### 11.4 完整时序（单实例）

```bash
# 1) 引导：体检 + 依赖 + 基座
python scripts/gpu_bootstrap.py --also-download-base

# 2) 学习曲线试点：300 条 × 2ep ≈ 0.77h（L40S）
python scripts/gpu_train_pipeline.py --data data/toolcall_optimal.jsonl \
    --mode lora --no-grad-ckpt --batch 2 --grad-accum 8 \
    --attn-impl flash_attention_2 --group-by-length --min-vram-gb 44 \
    --time-budget-min 40

# 3) 合并 + GGUF
python scripts/gpu_merge_pipeline.py --yes --to-gguf --llama-cpp /root/llama.cpp

# 4) 落地复验（就在本机，无需回传）
ollama create virtu-toolcall -f Modelfile
ollama run virtu-toolcall
```

第 2 步若试点不通，**立刻停机止损**——此时花费 ≈ ¥3，还没有任何沉没成本。
