# Virtu 工程能力全面提升 — 可复现云端训练套件

一套参数化、固定种子、带 sha256 门控的训练脚本，用于把 Qwen3-8B 基座训练成具备
「六大工程软件调用 / 读屏键鼠参数化建模 / 图片工况语义决策 / 机械配合与公差理解」
能力的工业智能体，并给出**可量化的验收指标**。

脚本复用工作区既有资产，不重复造轮子：`scripts/virtu_tokenize.py`（官方 chat_template 掩码）、
`scripts/wm_verifier.py`（物理复算）、`bridges/tool_calling_specs.py`（14 个 `cadcam_*` 工具面）、
`virtu_eval/report.py`（指标口径）、`bridges/desktop_controller.py`（读屏键鼠）、
`scripts/train_qwen3_8b_qlora.py`（legacy 训练引擎）。

---

## 1. 能力 → 数据 → 评测 映射

| 能力目标 | 训练数据通路 | 对应评测指标 |
|---|---|---|
| ① 深度理解并调用六大工程软件及工具链 | 从 `CADCAM_TOOLS_DEFINITION` 用 AST 提取 14 个真实工具名与 JSON Schema，程序化合成单步/多步编排、拒答边界样本 | `tool_call_valid_rate`、工具任务成功率 |
| ② 本地读屏 + 键鼠完成参数化建模，无严重报错 | 屏幕观察 → 语义推理 → 受控动作序列 → 特征树/体积守恒验证轨迹；含对话框、COM 断连、DPI 坐标夹紧等可恢复异常 | `gui_action_valid_rate`、`fatal_error_rate`、`recovery_rate`、`task_success_rate` |
| ③ 图片输入 → 真实语义决策，选最优且最快方案 | 候选方案带 (物理可行性, 耗时, 风险, 设备可用性)，`chosen = argmin(cost)`；reason 必须逐字段引用工况 | `decision_optimality_rate`、`semantic_grounding_rate` |
| ④ 机械配合 / 公差语义 → 参数化建模策略 | ISO 286 查表配合、尺寸链极值法 vs RSS、许愿式自然语言 → 特征树/方程式/基准/校核 | `parametric_model_valid_rate`、语义题成功率 |
| 全部结果符合物理规律 | 数据层 / 训练层 / 评测层共用 `physics_gate.py` | `physics_compliance_rate`（**否决性指标**） |

### 关于「图片输入」的准确边界（务必读）

基座 `Qwen3-8B` 是**纯文本语言模型**，本套件训练的是**指挥通道**的决策能力，
不修改视觉编码器、不做像素级端到端多模态微调。实际链路沿用工作区的指挥/感知分离架构：

```
图纸/截图  →  感知通道（本地 Qwen3-VL-2B-Instruct 或 bridges/cadcam_vision_bridge.py）
          →  结构化工况 JSON（孔径/公差/材料/余量/设备/机床上限）
          →  指挥通道（Qwen3-8B + 本套件 adapter）→ 物理合规且代价最小的方案
```

训练语料里的 `image` 字段是图片路径引用（真实文件来自
`data/benchmark/virtu_eval_v1/images/`），配合结构化工况共同构成决策题；
若图片目录缺失，生成器会写 `synthetic_image_ref://...` 并**明确标记**，绝不宣称"已读图"。
如需端到端视觉微调，应换 `Qwen3-VL-*` 基座并接入视觉塔，那属于另一条训练线。

---

## 2. 目录结构

```
engineering_capability_train/
├── configs/
│   ├── pipeline.json          # 种子、路径、数据配比、复用资产、物理开关
│   ├── train.json             # SFT/DPO 超参、按 GPU 的 profile、合并策略
│   └── metrics.json           # 指标定义、口径、验收门阈值
├── 01_prepare_data.py         # 数据准备总入口 + 打包
├── data_builders.py           # 四大能力语料 + 反遗忘 replay + DPO 偏好对
├── _ect_rowcheck.py           # 生成/体检共用的单行校验（工具面、规范化、物理）
├── ect_common.py              # 种子、sha256、manifest、原子写、动态加载既有模块
├── physics_gate.py            # 物理合规闸门 + 决策代价模型
├── validate_corpus.py         # 训练前语料门禁
├── train_sft.py               # 阶段1 SFT（QLoRA r=32/alpha=64）
├── train_dpo.py               # 阶段2 DPO（免副本 reference）
├── gui_task_runner.py         # 本地读屏+键鼠闭环执行器
├── evaluate.py                # 统一指标计算 + 门控 + Markdown 报告
├── 03_merge_local.py          # 本机两步 delta 合并 SFT+DPO → 可上线 HF 模型
├── run_pipeline.py            # 一键编排 / 熔断
├── requirements-cloud.txt     # 锁定依赖
├── Dockerfile                 # 云端镜像
├── cloud/launch.sh            # 云端一键开训（零配置：自动装依赖/下基座）
├── cloud/download_base.sh     # 基座解析/下载（被 launch.sh source）
├── cloud/entrypoint.sh        # 容器入口
└── tests/test_ect.py          # 21 项无 GPU 单元测试
```

---

## 3. 快速开始

```bash
# 环境（本机 Windows 也可跑数据链路；训练需 CUDA）
export VIRTU_REPO_ROOT=/path/to/Virtu模型
cd engineering_capability_train

# 0) 无 GPU 自检：21 项单元测试
python -m unittest discover -s tests -v

# 1) 数据准备（固定 seed=20261104，写 manifest + 训练/评测/DPO 三个 jsonl）
python 01_prepare_data.py --target-samples 6000

# 2) 训练前门禁（失败非零退出，禁止带病开训）
python validate_corpus.py

# 3) 打包上云（含 sha256 校验）
python 01_prepare_data.py --target-samples 6000 --bundle
```

云端（GPU 机，工作区根目录）——**零配置，一条命令即可开训**：

```bash
# 最简：裸 GPU VM + 有外网。缺依赖自动装、缺基座自动下（含国内镜像），无需任何环境变量
bash engineering_capability_train/cloud/launch.sh

# 自带基座（离线集群 / 已预置模型）：跳过下载，直接复用本地目录
export VIRTU_BASE=/models/Qwen3-8B          # 必须是含 config.json 的目录
bash engineering_capability_train/cloud/launch.sh --no-download

# 只用 --selftest-only 先验证整条链路（分词/掩码/截断率/门禁），不占 GPU 开训
bash engineering_capability_train/cloud/launch.sh --selftest-only
```

`launch.sh` 自动完成：GPU 体检 + profile 选择（读 `nvidia-smi`，不依赖 torch）→
缺依赖则装 → 缺基座则下载（默认 `Qwen/Qwen3-8B`，`HF_ENDPOINT` 默认国内镜像，可覆盖）→
manifest 校验 → 分词自检 → SFT(QLoRA) → DPO → 打包回传 adapter + 日志（失败时也会打包日志）。
可用开关：`--skip-dpo` `--no-install-deps` `--install-deps` `--profile=<v100_32g|l40s_48g|a100_80g>`。

或用镜像（镜像已预装依赖，但仍需基座，离线机走 `-v /models:/models:ro` + `--no-download`）：

```bash
docker build -t virtu-ect:1.0.0 -f engineering_capability_train/Dockerfile .
docker run --gpus all -e VIRTU_BASE=/models/Qwen3-8B \
  -v /models:/models:ro -v "$PWD":/workspace virtu-ect:1.0.0
```

一键编排（等价于逐个调用上述脚本，每步写 receipt，失败即熔断）：

```bash
python run_pipeline.py --cloud --stage validate,train,dpo --profile l40s_48g
python run_pipeline.py --stage prepare,validate --target-samples 6000
python run_pipeline.py --stage evaluate --endpoint http://127.0.0.1:8000/v1 --model virtu-ect
python run_pipeline.py --stage prepare,validate,bundle,train,dpo,evaluate --dry-run
```

---

## 4. 完整训练流程

| 步骤 | 命令 | 产物 | 校验点 |
|---|---|---|---|
| S0 环境 | `pip install -r requirements-cloud.txt` | — | torch 2.5.0 / CUDA 12.4 / py3.11 |
| S1 数据准备 | `python 01_prepare_data.py` | `data/train_corpus.jsonl`、`dpo_pairs.jsonl`、`eval_tasks.jsonl`、`corpus_manifest.json` | 每条过物理闸门；训练/评测 prompt 零重叠；硬 holdout 零泄漏 |
| S2 语料门禁 | `python validate_corpus.py` | `data/validation_report.json` | 恰好 1 个训练 jsonl；工具名/required/enum 全合法；0 物理违规 |
| S3 打包 | `python 01_prepare_data.py --bundle` | `artifacts/ect_cloud_bundle.tar.gz` + sha256 | 打包前后 manifest 双校验 |
| S4 分词自检 | `python train_sft.py --selftest --base $VIRTU_BASE` | stdout 统计 | 官方 `apply_chat_template` + assistant-only 掩码；无 0-loss 样本；截断率 |
| S5 阶段1 SFT | `python train_sft.py --profile l40s_48g` | `artifacts/ect_sft_adapter/` + `training_receipt.json` | `status=COMPLETED`；`lora_r=32` |
| S6 阶段2 DPO | `python train_dpo.py` | `artifacts/ect_dpo_adapter/` | chosen 合规最优；rejected 为违规/次优/瞎猜 |
| S7 本机合并 | 见 §7 | 合并权重 + GGUF + Ollama 模型 | 只允许 `delta`/`ties` |
| S8 评测 | `python evaluate.py --endpoint ...` | `runs/eval_*/results.json` + `report.md` | 全部验收门 PASS |
| S9 真实 GUI 评测 | `python gui_task_runner.py --backend real --predictions ...` | `runs/gui_task_results.jsonl` | 只有 `real` 计入能力指标 |

---

## 5. 数据配方

`configs/pipeline.json` 的 `data_mix`（权重和为 1，`target_train_samples=6000`）：

| 来源 | 占比 | 生成方式 |
|---|---:|---|
| `toolchain` | 0.30 | 14 个真实工具 × 差异化工程规格 + 物理闭环多步编排 + 拒答边界 |
| `gui_trajectory` | 0.25 | 屏幕观察 → reason → 动作序列 → 体积守恒验证；每例注入一种可恢复异常 |
| `vision_decision` | 0.20 | 5 类工艺候选 × (Ra 能力 / IT 等级 / 主轴上限 / 设备可用性 / 配合性质) 决定可行集 |
| `engineering_semantics` | 0.15 | ISO 286 配合、尺寸链极值法/RSS、许愿式 → 参数化建模策略 |
| `replay` | 0.10 | 从 4 份已验证语料采样；做 tool_calls 规范化 + 工具 Schema 校验，防能力回退 |

**反随机猜测设计**：决策答案随工况真实变化。实测 120 例的最优解分布为
`drill_grind 50 / drill_ream 48 / drill_bore 18 / 无可行工艺拒答 4`，
模型背一个固定答案无法通过；`semantic_grounding_rate` 还要求 reason 引用题面字段名。

**所有样本统一格式**：`{"messages":[{role,content}...], "meta":{capability,source,id,...}}`，
兼容 `virtu_tokenize.build_example` 与 legacy 训练器。

---

## 6. 超参数配置

### SFT（`configs/train.json` → `sft`）

| 参数 | 值 | 说明 |
|---|---|---|
| 基座 | `Qwen/Qwen3-8B` | 环境变量 `VIRTU_BASE` 覆盖 |
| 量化 | 4bit NF4 + double quant | `BitsAndBytesConfig` |
| LoRA | **r=32, alpha=64, dropout=0.05** | 硬约束：须与现有 7 个同源 LoRA 一致才可合并 |
| target_modules | q/k/v/o/gate/up/down_proj | 7 个 |
| lr / scheduler | `1.5e-4` / cosine, warmup 0.03 | |
| epochs / weight_decay | 3 / 0.01 | |
| max_seq_len | 2048(V100) / 2560(L40S/A100) | 长尾样本 p99 见门禁报告 |
| loss mask | **assistant-only, 官方 chat_template** | 复用 `scripts/virtu_tokenize.py`；tool 回执全 mask |
| seed | 20261104 | 覆盖 random/numpy/torch/hash |

### 按 GPU 的 profile

| profile | 精度 | bs×accum | FlashAttn2 | max_len | 依赖 |
|---|---|---|---|---|---|
| `v100_32g` | **fp16**（sm70 无 bf16 TC） | 1×32 | 禁用 | 2048 | `requirements-v100.txt` |
| `l40s_48g` | bf16 | 2×16 | 关闭（可选） | 2560 | `requirements-l40s.txt` |
| `a100_80g` | bf16 | 4×8 | 可选 | 2560 | `requirements-gpu.txt` |

`--profile auto` 按 `torch.cuda.get_device_capability()` 与显存自动选择。

### DPO（`configs/train.json` → `dpo`）

| 参数 | 值 |
|---|---|
| beta | 0.1 |
| lr / epochs | `5e-6` / 1，cosine + 5% warmup |
| max_length / max_prompt_length | 2048 / 1536 |
| reference | `peft.disable_adapter()` 复用基座，不加载第二份权重 |
| loss | `-logsigmoid(beta*((π_c-π_ref_c)-(π_r-π_ref_r)))`，completion 段平均 log-prob |

`--smoke` 只跑 2 步产 `SMOKE_ONLY` receipt，该产物禁止进入合并流程。

---

## 7. 本机收尾（GPU 机不做）

云端只产 **两个 adapter**（SFT + DPO）。关键事实：**DPO adapter 是叠在 SFT 之上的 delta**
（DPO 训练时 base+SFT 处于激活态、参考模型才是裸基座），所以合并必须分两步：

```bash
# 一步完成「SFT delta 合入基座 → M1；DPO delta 合入 M1 → M2（最终模型）」
# 脚本自动校验：两个 receipt 均 COMPLETED 且非 SMOKE_ONLY、lora_r 一致、同一基座
python engineering_capability_train/03_merge_local.py \
  --sft-adapter engineering_capability_train/artifacts/ect_sft_adapter \
  --dpo-adapter engineering_capability_train/artifacts/ect_dpo_adapter \
  --out checkpoints/ect_merged

# （仅跑过 SFT、没跑 DPO 时加 --skip-dpo）
# 合并默认在 CPU 以 bf16 进行（约 16GB RAM）；本机有富余显存可 --device cuda 加速

# GGUF 转换（脚本固定输出 Q4_0，无 --quant 参数）
python scripts/hf_to_gguf_numpy.py --model checkpoints/ect_merged \
  --out checkpoints/ect-q4_0.gguf

# 以 Modelfile_v4 为模板，把 FROM 指向新 GGUF 后再注册
# （Ollama 0.35.1 起不再支持运行时 LoRA ADAPTER，必须先合并）
ollama create virtu-ect -f Modelfile_v4
```

> 为什么不能直接把两个 adapter 一次性叠到裸基座？DPO 的 delta 是相对 SFT 微调后权重的，
> 跳过 SFT 直接合并会让偏好优化失效甚至乱码。本项目合并只用 `delta`（TIES 见 mergekit），
> **`peft_linear` 一律禁用**（历史上有交叉项 → 乱码/死循环）。`03_merge_local.py` 内部用
> PEFT `merge_and_unload` 实现标准 delta，绝不走 peft_linear。

合并前自动校验：rank 一致、base 标识一致、逐字节相同的 adapter 拒绝叠加、
`training_receipt.json status == COMPLETED`。

---

## 8. 量化评测指标

口径与 `virtu_eval/report.py` 一致：`transport_error` / `recorded_replay` / 非 real 的 GUI 回放
**不计入能力分母**，单独记为覆盖损失；`transport_error > 5%` 判本轮无效必须重跑；
`empty_response` / 截断计入分母（真实产品失败）。每次评测写入全新 `runs/eval_<时间戳>_<pid>/` 目录。

| 指标 | 定义 | 权重 | 验收门 |
|---|---|---:|---|
| `task_success_rate` | 全 criteria 通过 ∧ 物理合规 ∧ 无 fatal / 有效任务数 | 0.24 | ≥ 0.85 |
| `first_attempt_success_rate` | 零重试成功 / 有效任务数 | 0.08 | ≥ 0.70 |
| **`physics_compliance_rate`** | 过物理闸门的决策 / 决策总数 | 0.16 | **= 1.0（否决项）** |
| `decision_optimality_rate` | `selected == argmin(cost)` 且可行 / 评分决策数 | 0.12 | ≥ 0.85 |
| `semantic_grounding_rate` | 决策理由引用的工况字段数 / 必需字段数 | 0.10 | ≥ 0.80 |
| `tool_call_valid_rate` | 白名单 ∧ Schema 合法 ∧ 键名 `tool`/`arguments` | 0.08 | ≥ 0.95 |
| `parametric_model_valid_rate` | 几何/体积守恒/FOS/公差带全通过 | 0.10 | ≥ 0.95 |
| `gui_action_valid_rate` | 合法动作 / 总动作 | 0.06 | ≥ 0.98 |
| `error_rate` | 含任意错误的任务 / 有效任务数 | 0.06 | ≤ 0.10 |
| `fatal_error_rate` | 未捕获异常/COM 不可恢复/扎刀/红色过切 | — | ≤ 0.02 |
| `transport_error_rate` | 传输失败 / 全部记录 | — | ≤ 0.05 |
| `latency_mean/p50/p95_s` | 端到端耗时（读屏+决策+执行+验证） | — | p95 ≤ 180 s |
| `recovery_rate` | 已恢复的非致命异常 / 非致命异常总数 | — | 观测项 |
| `engineering_capability_score` | 加权综合分（lower-is-better 先归一） | — | ≥ 0.80 |

`cost = estimated_time_s × (1 + 0.5 × risk)`；物理违规候选 `cost = +∞`，永不入选。
**同时考核最优与最快**：选对工艺但选了更慢路线不得分。

### 诚实性设计

- 某能力**没有真实样本**时指标输出 `null`（"未测"），门控判不通过，绝不显示 0 分冒充实测。
- `gui_task_runner.py --backend real` 是唯一会计入 GUI 能力指标的模式；`recorded`/`dry`
  产出 `evaluation_valid=False`，报告里明确标注。
- 特征树回读若没有 OCR 后端，记 `unverified` 而非"通过"。
- 端到端理想预测实测：文本类指标全 1.0，但因缺真实 GUI 执行与耗时数据，
  门控**正确拒绝验收**（`gui_action_valid_rate` 与 `latency_p95_s` 为 `metric unavailable`）。

---

## 9. 物理合规约束（`physics_gate.py`）

| 层级 | 约束 |
|---|---|
| L1 确定性 | 体积守恒 `after = before + ΔV`；切除 `ΔV<0` / 凸台 `ΔV>0`；`0 < d_inner < d_outer`；公差带非负；反推密度 ≤ 60 g/cm³（拦死 1000 倍量纲错） |
| L2 解析复算 | 复用 `wm_verifier.recompute/l1_check/verify`；`n=1000Vc/(πD)`、`Vf=fz·z·n`、`Ra=f²/(8r)`、MRR |
| L3 工程约束 | `FOS ≥ 1.5`；ISO 286 的 H7/g6 间隙、H7/h6 零间隙、H7/p6 过盈符号；尺寸链极值法 ≥ RSS；`G00` 最低点 ≥ 毛坯顶面；Auto-Diff 红色过切致命 |

反假绿条款：**材料未解析直接判违规**（禁止静默套用 Cr12MoV，曾使 FOS 虚高 2.4 倍）；
载荷键名不一致判违规；FOS 未达标却标 `optimized=True` 判违规。

---

## 10. 可复现性保证

- 全局 `seed=20261104`，覆盖 `random` / `numpy` / `torch` / `PYTHONHASHSEED`；四类能力各用派生独立随机流。
- 所有配置集中 JSON，命令行覆盖全部记入 `training_receipt.json`。
- 每个产物写 sha256 + 行数 + 生成器版本 + 配置哈希到 `corpus_manifest.json`；开训前逐文件复验。
- 训练目录**恰好 1 个** jsonl；评测目录每次全新，避免按 `case_id` 续跑造成"假刷新"。
- 硬 holdout `data/benchmark/virtu_fix_v1/formula_holdout_200.jsonl` 只允许训练后验收，泄漏即拒绝产出。
- 依赖版本锁定 + Dockerfile；V100 明确禁用 bf16 与 flash-attn。

---

## 11. 必须避开的坑（均来自本工作区实测）

1. 手写 ChatML 前缀拼接会错位（Qwen3 的 `<think>` 只在最后一个 user 之后出现）→ 必须用 `virtu_tokenize.build_example`。
2. `role="tool"` 回执段必须 mask，否则模型学会伪造工具返回值。
3. 工具调用键名必须是 `tool`/`arguments`；历史语料里的 `name`+`arguments` 会导致 17 次 JSON 失败。
4. 工具名不得超出 14 个 `cadcam_*` 白名单（`taught_only` 会让模型调用不存在的工具）。
5. `lora_r` 必须 32 / alpha 64；Qwen2.5-7B 的 LoRA 与 Qwen3-8B 键空间不兼容。
6. 合并只用 `delta` / `TIES`；`peft_linear` 六适配器叠加会产生乱码与死循环。
7. V100 无 bf16 Tensor Core、无 FlashAttention-2；L40S 才用 bf16。
8. `max_seq_len=4096` 会截断长尾样本（历史 p99≈4915），用 5120 或按门禁报告调整。
9. 通用平衡语料会稀释能力导致 reasoning 反降 → 必须保留 ≥30% replay + 弱点定向数据。
10. 评测进程在本机需能访问 bridge（Bash 派生的子进程有网络隔离，必要时用 PowerShell 启动）。
11. Ollama 原生 `/api/chat` 不接收图片 → 多模态评测要走 OpenAI-compatible `/v1` 端点。
12. DPI 未声明时 `GetSystemMetrics=1536x864` 而截图 `1920x1080`，`SetCursorPos` 会静默夹紧坐标。
13. VERICUT 9.6 无程序化 batch 接口，返回 `unsupported_headless`，不要伪造仿真结果。
14. 逐字节相同的 adapter 重复叠加会把同一能力放大两倍；`SMOKE_ONLY` 产物绝不合并。
15. `transport_error` 里的伪 50 分不能计入分母；>5% 本轮无效。

---

## 12. 验证命令汇总

```bash
python -m unittest discover -s tests -v          # 21 项单元测试
python physics_gate.py --selftest                # 19 项物理约束正/负例
python evaluate.py --self-test                   # 指标口径自测
python 01_prepare_data.py --target-samples 300 --dry-run
python 01_prepare_data.py --target-samples 300 && python validate_corpus.py
python 01_prepare_data.py --verify-only
python gui_task_runner.py --backend recorded     # GUI 链路自检（不计能力）
python run_pipeline.py --stage prepare,validate,bundle,train,dpo,evaluate --dry-run
```

本次交付的自查证据固化在 `artifacts/VERIFICATION_REPORT.json`
（12 个 .py 编译、3 份配置、2 个 shell、21 项单元测试、19 项物理正/负例、
指标口径自测、语料门禁、7 个 CLI 冒烟、评测门控端到端）。
报告明确标注了本机未执行的部分：SFT/DPO 实训（需 GPU）与真实 GUI 评测（需 Windows 桌面），
未执行项绝不宣称通过。

---

## 14. 本机实测记录（2026-11-04「按建议执行」第二轮）

完整证据见 `artifacts/VERIFICATION_REPORT.json`（v2.0.0）。

### 环境事实

| 项 | 实测 |
|---|---|
| GPU | RTX 4050 Laptop，6141 MiB 总 / 5866 MiB 空闲 |
| 训练依赖 | torch / peft / bitsandbytes / datasets / accelerate **均缺失**；transformers、tokenizers、PIL、win32gui 可用 |
| 基座 tokenizer | `checkpoints/_base_qwen3_8b` 完整可用 |
| 评测端点 | Ollama `http://127.0.0.1:11434/v1` 可用（19 模型）；bridge 8000 不可达 |
| 桌面 | 读屏可用 1920×1080；OCR 视觉桥缺失；六大软件进程全部 `not_running` |

### 已真实执行

```bash
python 01_prepare_data.py --target-samples 6000 --bundle   # 6000/6000，配比 1800/1500/1200/900/600，零短缺
python validate_corpus.py                                  # 0 错误 0 告警，0 物理违规 / 0 工具不合规 / 0 泄漏
python train_sft.py --selftest --base <Qwen3 tokenizer> --selftest-limit 0 --max-len 2560
#   PASS：6000 条全部可用，0 截断（tokens_max=2453, p99=1219），loss 占比均值 0.315、最小 0.042
ECT_PYTHON=python VIRTU_BASE=<...> bash cloud/launch.sh --selftest-only   # rc=0
python evaluate.py --endpoint http://127.0.0.1:11434/v1 --model qwen3:8b --limit 12
#   训练前基线：task_success_rate=0.333, decision_optimality=0.0, semantic_grounding=0.198,
#   physics_compliance=1.0, latency_mean=62.6s / p95=99.7s, score=0.539 → 门控 FAIL（预期）
```

产物：`data/train_corpus.jsonl` 6000 条、`data/eval_tasks.jsonl` 800 题（从 5284 分层采样）、
`data/dpo_pairs.jsonl` 900 对、`artifacts/ect_cloud_bundle.tar.gz`（约 1.4 MB / 25 文件 / sha256 已复验，含 `cloud/*.sh`、`Dockerfile`、`README.md` 与完整 6000 行语料）。

### 熔断项（不伪造结论）

- **训练**：`train_sft.py` rc=1（`No module named 'torch'`）、`train_dpo.py` rc=1（缺 SFT adapter）。
  RCFA：6GB 显存装不下 8B QLoRA（4bit 基座≈5.5GB + 激活/优化器 ≥10GB），装齐依赖仍会 OOM，
  故不盲目安装。→ 在 ≥24GB 云端 GPU 执行 `cloud/launch.sh`。
- **真实 GUI**：六大软件未运行，不擅自启动（会长时间占用桌面并可能弹许可框）。
  → 用户启动软件后再跑 `gui_task_runner.py --backend real`，补齐 `gui_action_valid_rate` 等指标。

### 本轮脚本改进（已回归 21/21 单测）

1. `train_sft.py --selftest` 改为**仅依赖 tokenizer**，无 GPU 也能做与云端同构的预检；新增 `--selftest-limit`（0=全量）。
2. `cloud/launch.sh` 新增 `ECT_PYTHON` 覆盖，本机可用同一条命令跑 `--selftest-only`。
3. `evaluate.py` 新增 `--reasoning-effort none`（默认）：**实测 Ollama `/v1` 上 `think:false` 无效**（18s、空输出、`finish_reason=length`），`reasoning_effort:"none"` 才有效（1.09s、正常 JSON）。另新增 `--max-tokens`、stdout 完整结果快照。
4. 生成器增加连续直径与装配工况维度；配比改为「按能力先去重再取配额」，消除去重导致的配比失衡。
5. `pipeline.json` 新增 `max_eval_tasks=800`，按能力 round-robin 分层采样，避免 5284 题不可行的全量推理。

> 坑补充：Qwen3 在 Ollama OpenAI 兼容端点上必须用 `reasoning_effort:"none"` 关思考；
> `think:false` 只适用于原生 `/api/chat`，在 `/v1` 会被忽略并吃光 `max_tokens`。

## 13. 已知边界

- 云端 Linux 无桌面，`gui_task_runner` 只能 `dry`/`recorded`；**真实 GUI 能力必须在 Windows 本机
  （装好六大软件 + pywin32/Pillow）用 `--backend real` 评测**，否则验收门不会通过。
- 感知通道（图片→结构化工况）需单独接入 `Qwen3-VL-2B-Instruct` 或 `cadcam_vision_bridge.py`；
  本套件不训练视觉编码器。
- 训练需 CUDA GPU；本机无 GPU 时可完整运行数据链路、门禁、指标逻辑与全部测试，但不能执行 SFT/DPO。
- `latency_*` 只在带真实耗时记录（`--endpoint` 或真实 GUI）时才有值；离线 predictions 模式下为 `null`。
