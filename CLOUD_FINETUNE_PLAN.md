# Virtu-CAD-CAM 模型云端微调计划（成本最少 · 质量最高）

> 制定日期：2026-11-01
> 决策：已知问题全面修复 → 走**云端微调**（用户已拍板）
> 目标：把评测最弱项「边界处理」(53.45) 拉到 ≥80，综合分 ≥78，且不损伤已部署的工具调用 / 通用能力

---

## 0. 现状基线（必须对齐的事实）

- **当前线上模型 `virtu-cad-cam-10b` 的本质**：`Qwen3-8B` 基座 + `virtu-toolcall` 工具壳（经评测探针与元信息实测确认，**不是独立训练的 10B 权重**）。
- **评测综合分**：`72.91 / 100`（240 例全有效，transport=0）。
- **八维现状**（最弱在最前）：

  | 维度 | 分数 | 通过率 | 定位 |
  |---|---|---|---|
  | 边界处理 | **53.45** | 10.0% | **最弱，重点修复** |
  | 内容生成 | 62.77 | 36.7% | 中下 |
  | 泛化适配 | 67.87 | 36.7% | 中下 |
  | 知识覆盖 | 73.78 | 53.3% | 良 |
  | 推理逻辑 | 74.71 | 50.0% | 良 |
  | 工具编排 | 75.55 | 63.3% | 良 |
  | 指令遵循 | 86.59 | 66.7% | 强 |
  | 多模态理解 | 88.33 | 86.7% | 强 |

- **边界维度失败根因（已定位，非"不会拒绝"）**：
  1. 缺关键量时**擅自假设/编造**（e01 假设刀径算示例、e08 假设 45 钢给工艺 → 直接 fail）
  2. 矛盾/不可能工况**能识别但冗长、不给明确裁决**（e07 冲突进给无结论）
  3. 虚构实体**编造细节**（e09 编造不存在的 NX 函数）
  - 注：e03（短接安全门互锁）模型实际**正确拒绝**，说明"危险越权拒绝"方向已对，缺口在"严格性 / 不假设 / 不编造"。

---

## 1. 已知问题清单（本轮的修复范围）

### 1.1 已修复的代码级缺陷（不再阻塞，本轮已完成）
| 问题 | 修复 | 状态 |
|---|---|---|
| 桥接 GBK 编码崩溃（`print` 非 GBK 字符 → http_500） | `run_server()` 强制 `stdout/stderr.reconfigure(utf-8, replace)` | ✅ 已落地 |
| `SingleFlight` 伪跨进程锁（仅线程锁却称进程级） | 改为 Windows 命名内核互斥量 | ✅ 已落地 |
| `vericut_bridge` 中文日志下碰撞计数恒 0 | `parse_collision_log` 中英双语、碰撞单列 | ✅ 已落地 |
| 伪造「沙箱仿真 100% PASS」死代码 | 中和 `_synthesize_response`，改为"未执行不伪造" | ✅ 已落地 |
| 评测框架遇坏 case 整轮 abort | `runner` 逐 case 异常保护 + 续跑去重 | ✅ 已落地 |

### 1.2 模型能力短板（**本次云端微调要修复的核心**）
- 边界处理 53.45 → 目标 ≥80
- 内容生成 62.77 / 泛化适配 67.87 → 目标 ≥75
- hard 层断崖（知识 hard 40.8、工具 hard 38.9）→ 缓解
- 强项（指令 86.6 / 多模态 88.3 / 工具 75.5）→ **必须保住，零退化**

---

## 2. 成本最少 · 质量最高 —— 策略论证

### 2.1 为什么是「QLoRA on qwen3:8b」，而非全参 / 换基座
| 方案 | 显存 | 算力成本 | 质量 | 结论 |
|---|---|---|---|---|
| 全参微调 8B | ≥80G（多卡） | 百元级 / 轮 | 最高但易忘 | ❌ 不划算 |
| **QLoRA 4bit + LoRA（推荐）** | **24G 单卡** | **十元级 / 轮** | 足够注入边界行为 | ✅ **最优** |
| 换更大基座（14B/32B） | ≥48G | 高 + 重训工具壳 | 上限更高但成本高 | ❌ 过度 |

**关键不变量**：**不换基座**。继续复用已部署的 `qwen3:8b` + `virtu-toolcall` 工具壳——
- 工具调用能力**零成本保留**（换基座必须重训工具壳，成本与风险陡增）
- QLoRA 只训练 <1% 参数，24G 单卡按量即可，比全参省 4–8× 算力
- LoRA rank 适度（32–64）足以注入"边界 / 拒绝 / 不假设 / 不编造"行为模式，且天然抗灾难性遗忘

### 2.2 数据策略（质量最高的核心）
主数据：`data/sft/virtu_capability_sft_v6.jsonl`（**4233 条**，已通过防污染 + 数值一致性 + JSON 合法性校验）
- 边界强化样本 **659 条**（S3 拒绝类，直击最弱项）
  - 缺关键量严格拒绝（进给算转速 / 调质缺材料 / 缺切削力参数）
  - 矛盾 / 不可能工况明确裁决（板宽孔、转速超限、冲突进给、矛盾公差）
  - 虚构实体拒绝编造（NX 函数 / ISO 编号 / 铝合金牌号）
  - 安全旁路 / 提示注入拒绝（安全光幕、注入攻击）
- 正常请求负例 **138 条**（rpm / 知识 / NX API，防学成一律拒绝）
- 其余维度通用语料（reasoning / knowledge / instruction / generation / toolcall / generalization）**维持原能力**

**防泄漏**：已用 `check_sample` 剔除 500 条与评测集 n-gram 重叠；评测 240 例**严格不参与训练**。

### 2.3 防灾难性遗忘
- LoRA 冻结基座，只改适配器 → 通用能力天然保留
- 训练集含 1147 条通用指令（S1）+ 460 条工具调用（S2）维持能力
- 八维评测闭环，任一维度掉 >5 分即回滚

---

## 3. 云端选型与预算（成本最少）

### 3.1 平台推荐（按性价比排序）
1. **首选 AutoDL**：RTX 4090 / A5000 **24G，约 1.5–2.0 元/小时**（按量最便宜）
2. **备选 阿里云 PAI-DSW / 腾讯云 TI**：`gn7i`（A10 24G）约 2–3 元/小时，企业级稳定
3. **不推荐多卡 / A100**：单卡 24G 跑 8B QLoRA 绰绰有余，多卡徒增成本

### 3.2 资源与耗时
- 基座 4bit NF4 量化后 ~5GB 显存；QLoRA 训练峰值 ~12–16GB（含激活 + 优化器）→ **24G 卡安全余量大**
- 数据 4233 条 × 平均 ~300 token ≈ **1.3M token**；LoRA 在 4090 上约 30–60 分钟 / epoch
- 3 epoch + 合并导出 ≈ **2–3 小时**（含镜像就绪、数据上传）

### 3.3 预算估算（单轮）
| 项 | 费用 |
|---|---|
| 算力（2–3h × 2 元/h，AutoDL 4090） | 4–6 元 |
| 存储 / 数据集上传（一次性） | <5 元 |
| 若用 A100 40G 替代 | +10–20 元 |
| **单轮合计** | **≈ 10–30 元** |
| 迭代（首轮未达标再训 1–2 轮） | +<30 元 |

> 对比全参微调（多卡百元级 / 轮），QLoRA 方案成本低一个数量级。

---

## 4. 训练超参与流程

| 项 | 取值 | 说明 |
|---|---|---|
| 基座 | `Qwen3-8B`（HF，4bit NF4 加载） | 不复用 Ollama GGUF，云端用 HF 权重做训练基座 |
| LoRA | `r=32, alpha=64, dropout=0.05` | target = `all-linear`（覆盖 q/k/v/o + gate/up/down） |
| 优化器 | AdamW | `lr=2e-4, cosine, warmup=3%, wd=0.01` |
| 序列长度 | 2048 | 边界样本短，足够 |
| Batch | `per_device=4, grad_accum=4` → eff bs=16 | 24G 卡安全 |
| Epoch | 3，早停于 val loss | 随机种子固定，可复现 |
| 评测隔离 | 240 例绝不进训练集 | 防数据污染 |

**改造点**（基于现有 `scripts/train_master_cad_cam_2xl40s.py`，该脚本现硬编码 2×L40S + 全参 + `/root/...` 路径）：
1. 基座改本地可下载的 Qwen3-8B HF 权重；数据指向 `v6.jsonl`
2. 引入 `BitsAndBytesConfig(load_in_4bit=True, nf4, bf16)` + `prepare_model_for_kbit_training`
3. `get_peft_model(LoraConfig(...))`，仅训练适配器
4. 单卡 `TrainingArguments`（去掉多卡 `deepspeed`/`device_map` 分布式配置）
5. 输出 `FINAL_ADAPTER_DIR`（LoRA adapter，非全量权重）→ 体积仅数十 MB

---

## 5. 合并 · 部署 · 评测闭环（质量验证）

1. **训练** → 产出 LoRA adapter（`cad_cam_boundary_lora`）
2. **合并** → `merge_numpy.py` / `peft` 合并进 qwen3:8b bf16 基座
3. **量化** → `hf_to_gguf_numpy.py` 导出 **Q4_0 GGUF**
4. **注册** → 注册为 Ollama 新模型 `virtu-cad-cam-10b-sft`（**独立模型名，旧模型保留**）
5. **灰度路由** → 桥接 `text_model` 指向新模型（**`tool_model=virtu-toolcall` 工具壳不动**）；先 dry-run 少量请求验证再加全量
6. **重评测** → `python virtu_eval/report.py --runs "virtu:_eval_full4"` 复用同基线对比
7. **达标判据**：边界 ≥80、综合 ≥78、**其余七维任一不掉 >5 分** → 固化；不达标 → 调数据配比 / 超参再训

---

## 6. 执行命令清单（云端机器上）

```bash
# ① 环境（云端 GPU 实例，CUDA 已就绪）
pip install torch==2.6.0 transformers==4.45 peft==0.13 bitsandbytes==0.43 datasets==3.0

# ② 改造并启动 QLoRA 单卡训练（基于 train_master_cad_cam_2xl40s.py 改造版）
python scripts/train_qwen3_8b_qlora.py \
  --base Qwen/Qwen3-8B \
  --data data/sft/virtu_capability_sft_v6.jsonl \
  --out checkpoints/cad_cam_boundary_lora \
  --lora_r 32 --lora_alpha 64 --lora_dropout 0.05 \
  --lr 2e-4 --epochs 3 --bs 4 --accum 4 --max_len 2048 --seed 20261031

# ③ 合并 + 量化（复用现有 merge_numpy.py / hf_to_gguf_numpy.py）
python scripts/merge_numpy.py --base Qwen/Qwen3-8B --lora checkpoints/cad_cam_boundary_lora --out checkpoints/virtu_sft_merged
python scripts/hf_to_gguf_numpy.py --hf checkpoints/virtu_sft_merged --out models/virtu-cad-cam-10b-sft.Q4_0.gguf

# ④ 注册 Ollama（本地 / 部署机）
ollama create virtu-cad-cam-10b-sft -f ./models/virtu-cad-cam-10b-sft.Q4_0.gguf

# ⑤ 桥接切文本模型（工具壳不变）
# 改 scripts/virtu_service_pinned.py: text_model = "virtu-cad-cam-10b-sft"
python scripts/start_bridge_service.py --restart

# ⑥ 重评测对比
python virtu_eval/runner.py --arm bridge_deployed --out-dir _eval_sft
python virtu_eval/report.py --runs "virtu:_eval_sft" --out benchmarks/virtu_capability_sft
```

---

## 7. 风险与回滚

| 风险 | 缓解 |
|---|---|
| 显存 OOM | QLoRA 4bit 已大幅降低；仍超则降 `per_device` bs 或换更大卡 |
| 过拒（学成一律拒绝） | 监控负例维度（指令遵循 / 多模态），掉分则增负例或降边界权重 |
| 在线服务中断 | 新模型独立命名，旧模型保留，出问题秒级切回 `text_model` |
| 费用失控 | 云端设单实例上限 / 自动停机；按量计费，单轮 <30 元 |
| 训练失败无收敛 | 复用 v6 已验证数据；3 epoch 早停；失败保留 checkpoint 可重训 |

---

## 8. 时间线

- **第 0 步（已完成）**：代码 Bug 全修复 + v6 强化语料生成 + 评测基线 72.91 + 边界根因定位
- **第 1 步（待你批准）**：你提供云端实例 / 凭证 → 我改造训练脚本、上传 v6、启动 QLoRA 训练（2–3h）
- **第 2 步**：合并 → 量化 → 注册 → 灰度部署 → 重跑 240 例 → 交付「边界分提升 + 八维对比」报告
- **预算**：单轮 **10–30 元**，迭代追加 <30 元

---

## 9. 待你确认后我立即执行的事项
1. 提供云端 GPU 实例（AutoDL / 阿里云 / 腾讯云）的访问方式，或授权我拉起；
2. 确认是否允许我把新模型注册为独立 Ollama 名并灰度切换 `text_model`；
3. 如同意，我将把 `train_master_cad_cam_2xl40s.py` 改造为单卡 QLoRA 版（脚本 `train_qwen3_8b_qlora.py`），并按第 6 节命令执行。
