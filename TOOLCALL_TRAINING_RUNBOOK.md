# Virtu tool-call LoRA 训练与落地手册

> 版本：2026-10-30 · 适用范围：把 23,178 条 tool-call 语料训成 LoRA，烤进 Qwen3-8B，
> 最终让 `virtu-cad-cam-10b` 真正返回**结构化 `tool_calls`** 而非自然语言描述。

---

## 0. 现状与目标

| 项 | 训练前（已实测） | 目标 |
|---|---|---|
| 工具调用输出 | 自然语言"已调用工具…"，无结构化 `tool_calls` | 返回标准 `tool_calls` |
| 工具参数 | 幻觉（LENGTH 30→35）、重复刷屏 | 参数精确、可 JSON 解析 |
| 模型 | Qwen3-8B + 4×r32 LoRA 烘焙（`virtu-omni-8b`，Q4_0） | +1 个 r32 tool LoRA |
| 部署 | 本机 Ollama 0.35.1 + RTX4050 6GB，全卡卸载 | 同左 |

**根因**：23,178 条 tool-call 语料已生成并通过格式门禁，但**从未训练过**。
现有 4 个 LoRA 中 `tool_agent_lora_final` 是 r=16，与其余 r=32 rank 冲突，
在上一轮合并中被排除，等于工具能力完全缺失。

---

## 1. 分工架构（重要）

```
┌─────────────────────────────────┐        ┌─────────────────────────────────┐
│  GPU 机（远程 A800 80GB / ¥7.2h）│        │  本机（Windows / RTX4050 6GB）   │
│                                 │        │                                 │
│ ① 体检 → ② 备料 → ③ 数据体检     │        │ ⑤ 合并（numpy 流式）             │
│ ④ 训练 r=32/alpha=64 LoRA      │ ─────► │ ⑥ 转 GGUF Q4_0（numpy）         │
│    产出 LoRA adapter ~350MB      │ 回传   │ ⑦ 导入 Ollama + 端到端验证       │
└─────────────────────────────────┘        └─────────────────────────────────┘
```

**为什么这样分**：本机内存 16.9GB / 显存 6GB，跑 8B QLoRA 需要 ~16GB 显存，
物理上不可能；但纯 numpy 的流式合并 + GGUF 转换峰值内存 <1GB，完全够用。
所以 GPU 机只干"训练"这一件它擅长的事，产出一个小体积 adapter，其余在本机闭环。

---

## 2. 本机已完成（无需 GPU，可直接复核）

```bash
# 数据体检：23,178 条全量渲染 + 掩码校验
python scripts/validate_render_dataset.py --workers 10 \
    --out data/validation/render_report.json
```

实测结果：

```
通过 23178/23178  (100.000%)
   C1_json_structure          PASS
   C2_template_render         PASS
   C3_mask_construction       PASS
   C4_loss_mask_scope         PASS
   C5_tool_call_integrity     PASS

[token] min=1585 p50=2642 p90=2715 p95=2769 p99=2805 max=2837 mean=2600.4
[token] 总量 60,272,726 | 计 loss 8,953,929 (14.9%)
[token] 超 4096 截断: 0 (0.00%)
```

---

## 3. GPU 机执行

### 3.1 上传素材

把以下文件传到 GPU 机的工作目录 `/root/virtu_train/`：

| 文件 | 大小 | 来源 |
|---|---|---|
| `virtu_toolcall_train_final.jsonl` | 9.1 MB / 2,414 条 | `data/train/`（`scripts/build_train_final.py` 产出） |
| `virtu_toolcall_holdout.jsonl` | 0.4 MB / 94 条 | `data/train/`，**只评测、禁止入训**（4 组结构×材料组合已留出） |
| `handoff_manifest.json` | — | 同上，含各文件 sha256 与命令 |
| `scripts/train_virtu_toolcall.py` | 8 KB | 本仓库 |
| `scripts/virtu_tokenize.py` | 5 KB | 本仓库（掩码权威实现） |
| `scripts/validate_render_dataset.py` | 12 KB | 本仓库 |
| `scripts/gpu_train_pipeline.py` | 16 KB | 本仓库 |

基座权重：GPU 机需自备 `Qwen3-8B`（**必须是 base，不是 Instruct**——LoRA 就是训在它上面的）。
国内可从 ModelScope 拉：

```bash
python scripts/download_base_modelscope.py /root/virtu_train/Qwen3-8B
```

> A800 80GB 机器的磁盘：图示为 40GB 系统盘 + 50GB 数据盘。基座 16.4GB + 依赖环境
> 约需 30GB，**必须装到数据盘**，别把系统盘塞满。`/root` 通常挂数据盘，
> 但请先 `df -h` 确认。

### 3.2 一键跑

```bash
python scripts/gpu_train_pipeline.py \
    --work-dir /root/virtu_train \
    --base /root/virtu_train/Qwen3-8B \
    --data /root/virtu_train/virtu_toolcall_train_unified.jsonl \
    --epochs 3 --batch 2 --grad-accum 4 --yes
```

流水线阶段：

| 阶段 | 内容 | 失败处理 |
|---|---|---|
| S0 | 环境体检：GPU 显存 / torch / peft / transformers / bitsandbytes / 磁盘 | 缺依赖直接报缺哪个 |
| S1 | 备料：基座 / 数据 / 脚本就位 | 明确提示缺哪个 |
| S2 | 数据体检（复用 5 项检查） | 不通过**终止训练**，不烧 GPU 钱 |
| S3 | QLoRA 训练 | — |
| S4 | 产物校验：rank / alpha / target_modules / 权重完整性 / 与既有 LoRA 横向核对 | rank 不符直接 FATAL |
| S5 | 回传清单（含每文件 sha256） | — |

### 3.3 先冒烟再全量（强烈建议）

```bash
# 20 条跑通全流程，确认无环境问题（约 3 分钟）
python scripts/gpu_train_pipeline.py --work-dir /root/virtu_train \
    --limit 20 --epochs 1 --yes
```

冒烟通过后再跑全量。

### 3.4 成本与时长估算（A800 80GB / ¥7.20每小时）

> ⚠️ **本节已被 `TRAIN_ACCELERATION.md` 取代**（2026-10-30 实测复核）。
> 下表是**原始语料 + 未开优化**的保守估算；启用语料瘦身 + 关梯度检查点后，
> 全量 2ep 从 15.6h/¥113 降到 **3.8h/¥27**。详见 `TRAIN_ACCELERATION.md`。

**估算方法**（不是拍脑袋）：以本仓库 L40S 实测回执为锚点
（`cad_cam_six_software_lora`：408 步 / 2745.77s / 1632 样本×2ep / batch2×accum4），
反推实际 MFU ≈ 40~50%，再按 A800 BF16 稠密峰值 312 TFLOPS（A100 同代算力，
L40S 为 181 TFLOPS）换算。

**单卡 A800 80GB 时长与费用**：

| 配置 | 1 epoch | 2 epoch | 3 epoch | 2ep 费用 |
|---|---|---|---|---|
| QLoRA 4bit + 梯度检查点 | 7.8h | 15.6h | 23.4h | ¥113 |
| bf16 LoRA + 梯度检查点 | 7.8h | 15.6h | 23.4h | ¥113 |
| **bf16 LoRA 关梯度检查点** | **5.9h** | **11.7h** | 17.6h | **¥84** |

> **80GB 显存的真正价值在这里**：能关闭梯度检查点（省 ~25% 计算量，8N→6N），
> 且可改用 bf16 而非 4bit（免去 bnb 4bit 反量化开销，吞吐再高 10~20%）。
> 脚本已加 `--no-grad-ckpt` / `--min-vram-gb` 开关。

**推荐执行节奏（分两段，别一把梭）**：

> ✅ **推荐版本见 `TRAIN_ACCELERATION.md` §4**（含瘦身语料与全部加速开关，约 4.3h/¥30）。
> 下面是原始语料的保守节奏，仅作对照。

```bash
# 阶段 1：试点 3000 条 × 2ep ≈ 1.5h ≈ ¥11
#   目的：验证模型真能吐结构化 tool_calls，而不是训练完才发现格式没学会
python scripts/gpu_train_pipeline.py --work-dir /root/virtu_train \
    --limit 3000 --epochs 2 --no-grad-ckpt --min-vram-gb 60 --yes

# 阶段 2：试点通过后再全量 23178 × 2ep ≈ 11.7h ≈ ¥84
python scripts/gpu_train_pipeline.py --work-dir /root/virtu_train \
    --epochs 2 --batch 2 --grad-accum 4 --no-grad-ckpt --min-vram-gb 60 --yes
```

**总账**：

| 项 | 时长 | 费用 |
|---|---|---|
| 环境准备（torch cu124 + peft + bitsandbytes） | 10~15 min | — |
| 基座下载（ModelScope 16.4GB，云上带宽通常远好于本机实测 8MB/s） | 4~10 min | — |
| 阶段 1 试点 3000 条 | 1.5h | ¥11 |
| 阶段 2 全量 23178 条 × 2ep | 11.7h | ¥84 |
| 合并 + GGUF + Ollama 部署 | 15 min | ¥0（本机纯 numpy，已验证） |
| **合计** | **约 14h** | **约 ¥95~100** |

**省钱选项**：

| 方案 | 时长 | 费用 | 代价 |
|---|---|---|---|
| 1 epoch 全量 | 5.9h | ¥42 | tool_call 格式可能欠拟合，建议试点后评估 |
| 单卡 2 epoch（推荐） | 11.7h | ¥84 | — |
| 双卡 DDP 2 epoch | 6.5h | ¥94 | **不划算**，双卡单价翻倍，净收益仅省 5h |
| 分段租用（用完就退） | — | 按小时 | 云平台一般支持按小时计费/销毁实例，随时停 |

> **显存下限**：QLoRA 4bit + grad checkpointing 约需 24GB；bf16 LoRA 关梯度检查点需 ≥60GB。
> 脚本的 `--min-vram-gb` 会在启动前校验，不足直接退出，**避免机器空烧几小时**。

### 3.5 数据侧的一个关键事实（影响 epoch 选择）

对 1,500 条样本做字符级拆解后发现：

| 段 | 长度/条 | 占比 | 计 loss |
|---|---|---|---|
| tools 段（8 个工具的 schema，**每条完全相同**） | 3,240 字符 | 64% | ✗ |
| tool_response 段 | 1,592 字符 | 31% | ✗ |
| user 段 | 141 字符 | 3% | ✗ |
| **assistant 段** | **116 字符** | **2%** | **✓** |

也就是说 **64% 的算力花在重复渲染同一份工具 schema 上**，真正参与学习的只有 2%。
这解释了为什么 2 epoch 就够——**格式学习是低熵任务**，不需要 3 epoch 反复刷。
也正因如此，`--epochs 2` 是推荐值而非保守值。

---

## 4. 回传与本机落地

### 4.1 回传

把 GPU 机 `/root/virtu_train/virtu_toolcall_lora/` 整个目录拷回本机：

```
D:/Virtu模型/checkpoints/virtu_toolcall_lora/
├── adapter_config.json
├── adapter_model.safetensors      (~349MB)
├── README.md
└── training_receipt.json
```

用 `handoff_manifest.json` 里的 sha256 校验完整性。

### 4.2 一键落地（本机）

```bash
python scripts/deploy_tool_lora_to_ollama.py \
    --lora checkpoints/virtu_toolcall_lora \
    --ollama-name virtu-omni-8b-v2 \
    --append-default --dry-run
```

自动完成：合并 → GGUF → Ollama 导入 → **端到端验证**（普通对话 + 结构化 tool_calls）。
`--dry-run` 不切换模型；验证通过后去掉该参数重跑。

### 4.3 手动分步（需要单独排查时）

```bash
# ① 合并（5 个 LoRA：默认 4 个 + 新的 tool LoRA）
python scripts/merge_numpy.py --base checkpoints/_base_qwen3_8b \
    --out checkpoints/virtu_merged_v2 --mode peft_linear \
    --append-lora --lora checkpoints/virtu_toolcall_lora --weight 1.0

# ② 幅度预检（合并前必看，防止过合并毁基座）
python scripts/merge_numpy.py --base checkpoints/_base_qwen3_8b \
    --append-lora --lora checkpoints/virtu_toolcall_lora \
    --probe-amplitude --probe-samples 10

# ③ 转 GGUF
python scripts/hf_to_gguf_numpy.py --model checkpoints/virtu_merged_v2 \
    --out checkpoints/virtu-q4_0-v2.gguf

# ④ 导入 Ollama
ollama create virtu-omni-8b-v2 -f scripts/Modelfile.virtu-omni-v2
```

### 4.4 切换 WorkBuddy 桥

```bash
# 覆盖 data/virtu_ollama_model.txt 后
python start_virtu_bridge.py
```

或直接指定：

```bash
VIRTU_VLLM_MODEL=virtu-omni-8b-v2 python start_virtu_bridge.py
```

---

## 5. 八个已踩过的坑（照着做就不会再踩）

| # | 坑 | 症状 | 对策 |
|---|---|---|---|
| 1 | **逐消息前缀对齐掩码是错的** | 同一条 assistant 单独渲染 vs 作为前缀渲染结果不同（模板 L42 的 `last_query_index` 规则），loss 打到错误 token | 整条渲染 → 字符定位 assistant 段 → `offset_mapping` 映射 token。见 `scripts/virtu_tokenize.py` |
| 2 | **LoRA rank 不一致** | `tool_agent_lora_final` 是 r=16，与其余 r=32 不兼容，被排除 | 训练固定 `r=32/alpha=64`；合并器有硬校验 |
| 3 | **模板无 `{% generation %}`** | `return_assistant_tokens_mask=True` 返回全 0 掩码 | 改用字符定位 + offset mapping |
| 4 | **vocab 尺寸不一致** | HF `vocab_size=151936` vs tokenizer 实际 `151669`，GGUF 被 llama.cpp 拒绝：`expected ...151643, got ...151936` | 转换时把 tokens 数组补齐到 151936 |
| 5 | **Qwen3 thinking + 高温** | `temperature=0.7` + thinking 开启 → 语义断裂、刷屏 | `think:false` + `temperature ≤ 0.3`（已固化到 Modelfile / launcher / backend 三处） |
| 6 | **Ollama 直转 safetensors 依赖 MLX** | `--force` 能建模型但运行时 `MLX runtime is not available` | 走标准 GGUF 路径（本仓库自写 numpy 转换器） |
| 7 | **本机透明代理拦 localhost** | `ollama` CLI 与 `urllib` 请求被 `HTTP_PROXY` 劫持 | CLI 加 `NO_PROXY=127.0.0.1,localhost`；Python 用 `ProxyHandler({})` |
| 8 | **Bash 后台任务 7 分钟后被降权** | 16GB 长写盘任务中途 SIGTERM | 长任务走前台，或加 `--resume` 断点续传 |

---

## 6. 成功判据

| 检查 | 判据 |
|---|---|
| 数据体检 | 23,178/23,178 PASS，0 截断 |
| 训练产物 | `adapter_config.json` r=32 / alpha=64 / 7 个 target_modules |
| 合并 | 数值验证全 PASS，delta/base RMS mean <5%、max <20% |
| GGUF | 399 张量、tokens=151936、4.6GB |
| **对话能力** | 普通对话正常（不崩、不乱码） |
| **工具调用** | `/api/chat` 带 `tools` 返回**结构化 `tool_calls`**，参数可 JSON 解析且与输入一致 |

---

## 7. 回滚

任何环节失败，原模型 `virtu-omni-8b`（Ollama 里的 `virtu-omni-8b:latest`）保持不变，
把 `data/virtu_ollama_model.txt` 改回 `virtu-omni-8b` 即可。
合并产物与 GGUF 是独立文件，不覆盖原产物。

```bash
ollama rm virtu-omni-8b-v2          # 删新模型
rm -rf checkpoints/virtu_merged_v2 checkpoints/virtu-q4_0-v2.gguf
echo "virtu-omni-8b" > data/virtu_ollama_model.txt
```

---

## 8. 脚本清单

| 脚本 | 作用 | 需要 GPU |
|---|---|---|
| `scripts/virtu_tokenize.py` | **掩码权威实现**（训练与体检共用） | 否 |
| `scripts/validate_render_dataset.py` | 全量渲染体检（5 项检查） | 否 |
| `scripts/train_virtu_toolcall.py` | 训练脚本（r=32，支持 `--probe-only` / `--validate-only` / `--limit` / `--no-grad-ckpt` / `--min-vram-gb`） | 是 |
| `scripts/gpu_train_pipeline.py` | GPU 机一键流水线（S0~S5） | 是 |
| `scripts/merge_numpy.py` | 纯 numpy 流式合并（新增 `--append-lora`） | 否 |
| `scripts/hf_to_gguf_numpy.py` | 纯 numpy HF→GGUF Q4_0 | 否 |
| `scripts/deploy_tool_lora_to_ollama.py` | 本机一键落地 + 端到端验证 | 否 |
| `scripts/download_base_modelscope.py` | 基座下载（断点续传） | 否 |
