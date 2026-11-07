# Virtu 云端微调计划（成本最少、质量最高）— 2026-11-01

> **已被 `CLOUD_FINETUNE_PLAN_2026-11-01_v2.md` 取代**：v2 按实际生成的 5,133 条语料重算 token 与成本，并修正了 toolcall/clean 副本的训练隔离。本文件保留为初稿。

> 目标：用一次小规模、可回滚的云上 LoRA，修复当前实测缺口，而不是“再训一个更大的模型”。
> 原则：数据质量优先于参数量；单适配器 delta 合并；不碰评测集；每一步有确定性验收闸。
> 成本口径：文中标「实测」的数字来自仓库内已有记录（`TRAIN_ACCELERATION.md`、`benchmarks/`）；标「估算」的需在租机时按当日价格复核。

---

## 0. 一句话结论

**不需要全参微调，也不需要再合一个“全能”多 LoRA。**
用 **Qwen3-8B 基座 + 单次 QLoRA（r=32/α=64）**，喂 6,000–8,000 条“公式金标 + 工具调用 + 六软件代码 + 边界拒答 + 少量通用对话”，在 **RTX 4090 24GB** 上约 8–12 GPU 小时即可；按 AutoDL 4090 约 ¥1.6–2.5/h 估算，**总成本 < ¥50**。若追求略高质量，换 **L40S 48GB bf16 LoRA**，约 6–9 GPU 小时，**总成本 < ¥80**。

现有 `TRAIN_ACCELERATION.md` 已实测：2,316 条精选语料 / 3.14M token / 2 epoch / 0.45h / **¥3.2**（A800 口径）。本计划在此基础上扩到 6–8k 条并加入公式金标，成本仍在一顿外卖到两顿外卖之间。

---

## 1. 当前实测缺口（训练要打哪里）

| 缺口 | 实测证据 | 目标 |
|---|---|---|
| 主轴转速公式 | 5/5 在服产物全错（基座 241.67、toolcall/ties 1000、v4 382、qwen2.5 7639）；确定性守卫已把线上回答修到 2387.3 | 模型本身 200 条公式金标 100% 精确，不靠守卫兜底 |
| 知识覆盖 | `virtu_ties_v1` 18 例子集 knowledge **47.22** | ≥ 60 |
| 推理逻辑 | `virtu_ties_v1` 18 例子集 reasoning **34.28** | ≥ 60 |
| 边界处理 | `virtu_toolcall` 210 例 boundary **54.33** | ≥ 65 |
| 工具编排 | ties-v1 30 例 **88.89**；toolcall 30 例 78.89 | 30 例 ≥ 90，210 例子集不退化 |
| 尺寸保真 | 盲测 36 条：关键词 94.44%，尺寸保真 **0.7292**，5/16 题改写/遗漏 | 可判题保真 ≥ 0.95 |
| 线上身份 | 2026-11-01 13:5x 已切到 `virtu-ties-v1` + `virtu-toolcall`；视觉仍不可用 | 训练产物上线后仍用 `served_model` 归因 |
| 视觉 | 独立 Qwen3-VL-2B 评测 91.67；线上桥因监听进程无 torch 不可用 | 单独部署/训练视觉通道，不混入文本 LoRA |

> 注意：`virtu_ties_v1` 只在 30 例 toolcall 上测过；不能把 88.89 当综合分。上表把不同臂分开列。

---

## 2. 训练目标与验收闸（先定闸，再烧 GPU）

### 2.1 硬闸（任一不过就不上线）

1. `virtu_eval` 240 条用例：gold 自测 100，`contamination_check` 0 泄漏。
2. 公式金标 200 条（新留出，不与训练集同模板）：n / Vf / MRR / T 四类数值 **100% 命中**；缺参题必须反问，不得编数。
3. 工具调用：30 例 toolcall ≥ 90；210 例子集 overall ≥ 72.56（不退化），toolcall ≥ 78.89。
4. 文本：instruction ≥ 90，knowledge ≥ 60，reasoning ≥ 60，boundary ≥ 65；任一维度较 `virtu_ties_v1` 下降 > 3 分则拒绝。
5. 输出无西里尔/拉丁扩展乱码；同题多跑输出唯一率 > 95%。
6. 合并幅度：`merge_numpy --probe-amplitude` 的 delta/base 均值 1–5%，max < 20%。

### 2.2 软闸（决定是否再跑一轮）

- 40 例人工抽检：代码块可执行性、工具 JSON 字段、公式单位。
- 线上 `served_model.last_model_used` 必须等于新模型名；否则视为部署未生效。

---

## 3. 数据配方（质量的核心）

### 3.1 现有可复用语料（仓库内，已盘点行数）

| 用途 | 文件 | 行数 |
|---|---|---:|
| 工具调用主库 | `damodel_cad_cam_tuning/dataset/virtu_toolcall_train_unified.jsonl` | 23,178 |
| 工具调用瘦身版 | `damodel_cad_cam_tuning/dataset/toolcall_sft_v2_expanded.jsonl` | 21,952 |
| 工具调用精选 | `data/toolcall_optimal.jsonl` | 2,316 |
| 六软件综合 | `damodel_cad_cam_tuning/dataset/master_cad_cam_six_software_train.jsonl` | 1,632 |
| 许愿式参数化 | `damodel_cad_cam_tuning/dataset/wish_parametric_train.jsonl` | 1,200 |
| 综合许愿 SFT | `damodel_cad_cam_tuning/dataset/comprehensive_wish_cad_cam_sft_1200.jsonl` | 1,226 |
| UG 教师学生 | `damodel_cad_cam_tuning/dataset/ug_teacher_student_omni_train.jsonl` | 640 |
| 图纸→加工链 | `data/virtu_drawing_to_machining_chain_train.jsonl` | 2,213 |

**不要直接全量混。** `TRAIN_ACCELERATION.md` 实测 23,178 条里 20.9% 重复，tools schema 占 50.5% token；直接全量训练是花钱学同一份 schema。优先用 `data/toolcall_optimal.jsonl` 的 2,316 条精选 + 去重后的六软件/图纸链。

### 3.2 新增语料（本计划的核心增量）

| 数据块 | 数量 | 生成/校验方式 |
|---|---:|---|
| 公式金标 | 2,000–3,000 | 随机化 Vc/D/f/z/n/ap/ae/Vf/L，确定性计算 n=1000Vc/(πD)、Vf=f·z·n、MRR=ap·ae·Vf、T=L/Vf；每题 3 种问法（裸数字、短推导、长解释）；含缺参反问 |
| 六软件代码 | 1,500–2,500 | 从现有 1,632+1,226+1,200 条清洗；保留可执行 API 名、参数、单位；删除“100% PASS/已验证”类未执行声明 |
| 工具调用 JSON | 2,000–2,500 | 现有精选 + schema 校验；覆盖六软件、缺参、拒绝危险操作；`cadcam_*` 规范名 |
| 知识/推理 | 800–1,200 | 按 `virtu_eval` 维度新写题，**不得复用 240 条评测原题**；附标准答案与判分点 |
| 边界/拒答 | 300–500 | 缺参数、超公差、虚构标准、危险 G00 下刀、越权操作；统一“拒绝 + 给替代”格式 |
| 通用对话 | 500–800 | 防灾难性遗忘；含简单算术、自然聊天、单位换算 |

目标总量 **6,000–8,000 条**，2 epoch，约 10–15M token（估算，按现有 token/条外推）。

### 3.3 教师蒸馏（可选，但推荐做公式/知识块）

- 用 ModelScope 免费推理网关（`reference-modelscope-free-api`）的强教师模型生成难题的推导与代码；
- 每个 prompt 生成 3 个候选，**只保留**通过确定性判分（公式精确、JSON schema、关键字/尺寸）的候选；
- token 只走 `.ms_token` 文件，脚本收路径，跑完删除；不把 token 写进聊天或仓库；
- 教师输出必须去掉“已验证/100% PASS”等未执行声明。

### 3.4 清洗与泄漏闸

```bash
# 1) 评测集自检
python virtu_eval/validate_cases.py data/benchmark/virtu_eval_v1

# 2) 与新训练集做污染检查（按现有 checker 的 CLI 传参）
python virtu_eval/contamination_check.py --help

# 3) 去重：prompt+answer 归一化后 hash；同模板不同数值保留
# 4) 工具 JSON：用 bridges/tool_calling_specs.py 的 schema 校验
# 5) 公式：用与 _spindle_speed_problem 同源的 calculator 复算，误差 >0.1% 丢弃
```

产出：`data/train/virtu_fix_sft_v1.jsonl` + `data/train/virtu_fix_sft_v1.manifest.json`（来源、条数、sha256、与评测集重叠数=0）。

---

## 4. 训练配置（两档，按预算选）

### 4.1 推荐档：RTX 4090 24GB QLoRA（成本最低）

| 项 | 值 |
|---|---|
| 基座 | `Qwen/Qwen3-8B`（base，不是 Instruct；与现有 LoRA 同源） |
| 量化 | 4-bit NF4 + double quant |
| LoRA | r=32，alpha=64，dropout=0.05，7 个线性层（q/k/v/o/gate/up/down） |
| 精度 | bf16 compute |
| batch / grad_accum | 2 / 16（有效 32） |
| max_len | 2048（长代码可 3072，需压 batch） |
| lr | 1e-4，cosine，warmup 15–30 |
| epochs | 2（公式块可 3） |
| optimizer | paged AdamW 8bit |
| 显存技巧 | gradient checkpointing 开；packing + 长度分桶；FlashAttention 2 |
| 预计 GPU 时 | 8–12 h（估算，6–8k 条） |

### 4.2 质量优先档：L40S 48GB bf16 LoRA

| 项 | 值 |
|---|---|
| 量化 | 无（bf16 基座） |
| batch / grad_accum | 4 / 4（有效 16）或 2 / 8 |
| lr | 2e-4 |
| max_len | 2048–4096 |
| gradient checkpointing | 可关（实测吞吐 +10–20%） |
| 预计 GPU 时 | 6–9 h（估算） |

> 两档都保持 **r=32/α=64**，这样单适配器可以走 `merge_numpy.py --mode delta`，不引入多 LoRA 交叉项。**禁止**再把 4–6 个 LoRA 用 `peft_linear` 直加。

### 4.3 直接可用的命令

```bash
# 24GB QLoRA（默认值已对齐：r=32/alpha=64/max_len=2048）
python train_virtu.py \
  --base /root/models/Qwen3-8B \
  --data /root/virtu_train/data \
  --mode qlora \
  --epochs 2 --batch 2 --grad-accum 16 --lr 1e-4 --max-len 2048 \
  --output /root/virtu_train/out/virtu_fix_v1

# 48GB bf16 LoRA
python train_virtu.py \
  --base /root/models/Qwen3-8B \
  --data /root/virtu_train/data \
  --mode lora \
  --epochs 2 --batch 4 --grad-accum 4 --lr 2e-4 --max-len 2048 \
  --output /root/virtu_train/out/virtu_fix_v1_bf16
```

---

## 5. 成本测算（实测 + 估算）

| 项 | 档位 | 计算 | 成本 |
|---|---|---|---:|
| GPU（最低） | RTX 4090 24GB | 10 h × ¥1.6–2.5/h（估算，按当日价） | ¥16–25 |
| GPU（质量） | L40S 48GB | 8 h × ¥4.5–6/h（仓库 `SINGLE_GPU_TRAINING_PLAN.md` 记 ¥4.5/h） | ¥36–48 |
| 数据生成 | ModelScope 免费教师 | 免费额度 + 本地过滤 | ¥0–20（网络/重试） |
| 存储/下载 | 适配器 ~160 MB + 数据 | 对象存储/流量 | ¥5–10 |
| 评测 | 本机 Ollama | 0（本地） | ¥0 |
| **合计（最低）** | 4090 QLoRA | — | **< ¥50** |
| **合计（质量）** | L40S bf16 LoRA | — | **< ¥80** |

对照：`TRAIN_ACCELERATION.md` 实测 2,316 条 / 2 epoch / 0.45 h / **¥3.2**（A800）；本计划数据量约为其 3 倍，按同口径外推 1.5–2.5 h；4090 吞吐更低，故取 8–12 h 的保守估算。**所有小时数标「估算」，租机前用当日价复核。**

不建议：8B 全参微调（需多卡 80GB，成本 > ¥500，且更容易灾难性遗忘）；多 LoRA 线性合并（已实测乱码）。

---

## 6. 执行步骤（从租机到上线）

### Day 1：数据（本地，4–6 h）

1. 盘点/去重现有语料，生成 2,000–3,000 条公式金标。
2. 用确定性 calculator 复算全部公式；JSON schema 校验工具调用；删除未执行验证声明。
3. 生成 `data/train/virtu_fix_sft_v1.jsonl` + manifest；跑污染检查，确认与 240 条评测集重叠为 0。
4. 本地 `python -m pytest tests/test_arithmetic_guard.py tests/test_eval_runner.py -q` 先过。

### Day 2：云上训练（6–12 GPU h）

1. 租 4090 24GB（或 L40S 48GB）；装 `requirements-gpu.txt`（torch 2.5.0/CUDA 12.4/transformers≥4.51/flash-attn 2.7.4）。
2. 上传基座与数据；用 `scripts/deploy_and_train_remote.py` 或 DAMODEL 现有 SSH 流程；凭据只走环境变量。
3. 启动训练，日志同时落盘；每 200 步存 checkpoint；每 200 步跑一次小样本验证。
4. 训练结束下载 adapter；在本地用 `merge_numpy.py --verify-only` 验证合并数学。

### Day 3：合并、评测、上线（2–3 h）

```bash
# 1) 单适配器 delta 合并（不要多 LoRA 直加）
python scripts/merge_numpy.py --base checkpoints/_base_qwen3_8b \
  --out checkpoints/virtu_fix_v1 \
  --mode delta \
  --lora checkpoints/virtu_fix_v1_lora --weight 1.0

# 2) 量化 GGUF
python scripts/hf_to_gguf_numpy.py --model checkpoints/virtu_fix_v1 \
  --out checkpoints/virtu-fix-v1-q4_0.gguf

# 3) 注册 Ollama
ollama create virtu-fix-v1 -f scripts/Modelfile.virtu-fix-v1

# 4) 评测（先小样本，再 210 例；不要与训练同时跑）
python -m virtu_eval.runner --arm ollama_virtu_fix_v1 --out-dir runs/eval/virtu_fix_v1

# 5) A/B：新模型 vs ties-v1 vs toolcall vs 基座；过 §2.1 硬闸才上线
```

上线：把 `scripts/run_virtu_service.py` 的 `VIRTU_VLLM_MODEL` 改为 `virtu-fix-v1`，重启 8000；`/v1/models` 必须显示新模型名。保留 `virtu-ties-v1` 作为回滚目标。

---

## 7. 视觉通道（单独处理，不混入文本 LoRA）

线上视觉当前不可用，根因是监听进程是全局 Python（无 torch），venv 启动器会再拉起全局子进程；这不是训练能修的。两条路：

0. **桥侧借用 venv 运行时（已写代码，待验证）**：`virtu_real_backend._import_vision_stack()` 在全局 Python 缺 torch 时把 `.venv/Lib/site-packages` 临时加入 `sys.path`，借用 torch 2.6 + transformers 5.22。代码已通过独立导入测试；当前 8000 进程仍是旧代码，需在内存余量足够时重启后发一张合成图验证。若 6GB 显存被 Ollama 占满，仍可能 OOM，因此不能把它当唯一方案。
1. **便宜**：把视觉请求转发到云端 VLM（现有 `glm-4.5v` 候选当前失败，需换可用 key/端点），文本桥不动。
2. **可控**：单独给 `Qwen3-VL-2B-Instruct` 训一个 LoRA（200–500 条图纸 OCR/工序/过切色谱样本），用独立进程/端口部署；成本约 1–2 GPU h，**不要**和 Qwen3-8B 文本 LoRA 合并。

视觉上线验收：图纸 OCR 关键尺寸命中、工序号/刀号识别、VERICUT 色谱过切/残料判断；与文本 240 例分开报分。

---

## 8. 风险与回滚

| 风险 | 规避 |
|---|---|
| 训练集与 240 评测集泄漏 | `contamination_check` + 模板留出；训练 manifest 记录重叠=0 |
| 公式只会背模板 | 随机数值/单位/问法；缺参反问；200 条新留出 100% 才收 |
| 灾难性遗忘 | 10–15% 通用对话；早停；A/B 对比基座；任一维度跌 >3 分拒绝 |
| QLoRA 精度不够 | 先 4090 QLoRA；差距大再跑一次 L40S bf16 LoRA，不直接全参 |
| 多 LoRA 合并乱码 | 只合单适配器 `--mode delta`；合并前 `--probe-amplitude`，max>20% 停 |
| 云厂商价格/可用性 | 按需租、限时、checkpoint 到持久盘；预算上限 ¥100，超时自动停机 |
| 视觉再拖垮文本 | 视觉独立进程/端口；不要把 VL 适配器合进 Qwen3-8B |

回滚：`run_virtu_service.py` 改回 `virtu-ties-v1`；保留旧 GGUF 与 `PROVENANCE.json` 记录；新产物若不过闸，移入 `checkpoints/_broken/`，不覆盖 canonical。

---

## 9. 交付物与排期

- 数据：`data/train/virtu_fix_sft_v1.jsonl` + manifest（来源/条数/sha256/泄漏=0）
- 训练：adapter、训练日志、`training_receipt.json`（超参、GPU 时、loss 曲线）
- 评测：`runs/eval/virtu_fix_v1/`（manifest/raw/results）、A/B 表
- 产物：`checkpoints/virtu_fix_v1`、GGUF、Ollama tag、`PROVENANCE.json` 更新
- 计划排期：Day 1 数据；Day 2 训练；Day 3 合并/评测/上线。1 张 GPU，总预算 < ¥100。

---

## 10. 明确不做

1. 不做 8B 全参微调（成本高、遗忘风险大、收益不确定）。
2. 不再把多个 LoRA 用 `peft_linear` 直加（已实测乱码，Σw=5.7）。
3. 不用评测集 240 条做训练；不复用盲测 36 条原题。
4. 不训练 `virtu_omni_10b_base.pt`（0.58B 占位）或 LoopTransformer（与 Qwen3 键空间交集 0）。
5. 不用“100% PASS/已验证”这类未执行声明当训练标签。
