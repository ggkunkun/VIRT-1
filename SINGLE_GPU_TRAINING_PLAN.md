# Virtu 单卡训练计划（针对 NVIDIA L40S 48GB）

> 依据你提供的云实例规格制定：2× NVIDIA L40S（单卡 48GB）/ 21 核 / 124GB 内存 / CUDA 13.0 / ¥4.50 小时 / 训练网络: 无。
> 本计划**只用其中 1 张 L40S（48GB）**完成 Virtu 模型训练，另一张不占用。

---

## 1. 硬件规格对照

| 项 | 值 | 对单卡训练的含义 |
|---|---|---|
| GPU | NVIDIA L40S ×2 | 本计划只用 1 张，`CUDA_VISIBLE_DEVICES=0` |
| 单卡显存 | 48GB | QLoRA 极宽裕；bf16 LoRA 轻松；**全参微调 8B 装不下** |
| CPU | 21 核 | 数据预处理/数据加载够用 |
| 内存 | 124GB | 合并 LoRA（CPU 内存烘焙）绰绰有余 |
| CUDA | 最高 13.0 | torch 用 cu124/cu128 wheel 即可 |
| 训练网络 | 无 | 无 RDMA/IB，**只适合单卡或单机单卡**，不要跨节点 |
| 价格 | ¥4.50/小时（2 卡实例） | 见 §5 费用精算 |

> ⚠️ 该规格页标的是 2 卡实例。若平台提供 **1×L40S** 实例，优先选它（约 ¥2.25/小时）。若只有 2 卡实例，用 `CUDA_VISIBLE_DEVICES=0` 只跑单卡，**但实例费仍按 2 卡计**，所以能选单卡就选单卡。

---

## 2. 单卡 48GB 显存预算（Qwen3-8B）

| 方案 | 权重占用 | 优化器+梯度 | 单卡 48GB 结论 |
|---|---|---|---|
| **QLoRA（4-bit）** | ~4.5GB | paged Adam8bit，极小 | ✅ 极宽裕，batch 可开大 |
| **LoRA（bf16）** | ~16GB | 仅 LoRA 参数，极小 | ✅ 轻松，batch 适中 |
| 全参微调（bf16） | ~16GB | AdamW fp32 状态 ≈ 96GB | ❌ 远超 48GB，单卡不可行 |

**结论：单卡只走 QLoRA 或 bf16-LoRA。** 推荐 QLoRA——质量接近、显存最省、batch 最大、最快出模型。

---

## 3. 两种单卡方案

### 方案 A：QLoRA（推荐，4-bit 量化 + LoRA）
- 基座 4-bit 量化加载，训练最稳、显存占用最低
- 单卡 48GB 可设 `per_device_batch_size=8, grad_accum=4`（有效批次 32）
- 质量对 8B 指令微调几乎无损

### 方案 B：bf16 LoRA（略高质量，需更多显存）
- 基座 bf16 全精度加载（~16GB），仅训 LoRA
- 单卡 48GB 设 `per_device_batch_size=4, grad_accum=4`（有效批次 16）
- 比 QLoRA 略好一点点，但慢、占显存多

---

## 4. 超参表（针对 48GB L40S 调优）

| 超参 | QLoRA(A) | LoRA(B) | 说明 |
|---|---|---|---|
| precision | nf4 / 4-bit | bf16 | — |
| lora_r / alpha | 32 / 64 | 32 / 64 | 与现有 Virtu LoRA 对齐，便于后续合并 |
| target_modules | 7 个线性层 | 同左 | q/k/v/o + gate/up/down |
| per_device_batch | 8 | 4 | 48GB 内安全值 |
| grad_accum | 4 | 4 | 有效批次 32 / 16 |
| max_seq_len | 2048 | 2048 | 数据最长接近此值 |
| learning_rate | 1e-4 | 2e-4 | LoRA 常用 1e-4~2e-4 |
| epochs | 3 | 3 | 数据量 6024 条足够 2~3 轮 |
| warmup_steps | 15 | 15 | — |
| gradient_checkpointing | ✓ | ✓ | 省显存 |
| bf16 | ✓ | ✓ | — |
| optimizer | paged AdamW(8bit) | AdamW | QLoRA 用 8bit |

> 以上即 `train_virtu.py` 的默认值（`--mode qlora` 对应方案 A）。拿来即用，无需手调。

---

## 5. 执行步骤（从租机到出模型）

### 步骤 0：租机 + 进环境
租 1×L40S（或 2×L40S 但只用 0 号卡）。SSH 进去后：
```bash
# 确认单卡可见
nvidia-smi --query-gpu=index,name,memory.total --format=csv
# 装依赖（CU 12.x 对应 torch）
pip install torch --index-url https://download.pytorch.org/whl/cu124
pip install transformers peft accelerate datasets
pip install bitsandbytes            # 仅 QLoRA 需要
```

### 步骤 1：拿基座权重（必须 Qwen3-8B，与 LoRA 同源）
```bash
pip install modelscope
modelscope download --model Qwen/Qwen3-8B-Instruct --local_dir /root/models/Qwen3-8B-Instruct
```

### 步骤 2：上传工程代码 + 数据
```bash
# 在你本机（有代码的机器）把工程打包推到实例，或用 git；此处略
# 确保实例上有：train_virtu.py、merge_lora.py、damodel_cad_cam_tuning/dataset/、checkpoints/
```

### 步骤 3：单卡训练（方案 A：QLoRA）
```bash
# 仅用 0 号卡
CUDA_VISIBLE_DEVICES=0 python train_virtu.py \
    --base /root/models/Qwen3-8B-Instruct \
    --mode qlora \
    --epochs 3
# 等价地也可用脚本自带开关：python train_virtu.py --base ... --mode qlora --single-gpu
```
产出：`checkpoints/virtu_lora_trained/virtu_lora_final/`（新 LoRA）。

> 若想额外吃你自己的数据，加 `--data /path/to/your_sft`。

### 步骤 4：合并成单一"Virtu 模型"
```bash
# 把新训 LoRA + 原有核心 LoRA 烤进基座
python merge_lora.py --base /root/models/Qwen3-8B-Instruct \
    --lora checkpoints/virtu_lora_trained/virtu_lora_final --weight 1.0 \
    --lora checkpoints/turing_conversational_lora --weight 1.0 \
    --lora checkpoints/cad_cam_six_software_lora --weight 1.0 \
    --out checkpoints/virtu_merged
```
产出：`checkpoints/virtu_merged/`（单目录，含完整权重 + tokenizer）。

### 步骤 5：接回 WorkBuddy（本地真模型，不再走云端）
```bash
# 有 GPU：transformers 后端
VIRTU_BACKEND=transformers VIRTU_MODEL_PATH=checkpoints/virtu_merged \
    python start_virtu_bridge.py

# 或转 GGUF 离线跑（无 GPU 也能跑）：
# python llama.cpp/convert_hf_to_gguf.py checkpoints/virtu_merged --outfile virtu.Q4_K_M.gguf
# VIRTU_BACKEND=llamacpp VIRTU_GGUF_PATH=virtu.Q4_K_M.gguf python start_virtu_bridge.py
```
WorkBuddy 选 `virtu-cad-cam-10b` → 此时回答来自**本地合并出的真模型**。

---

## 6. 时间与费用估算（单卡 L40S 48GB）

- 数据量：6024 条 × 平均 ~2048 token ≈ 12.3M token / epoch，3 epoch ≈ **37M token**
- QLoRA 在 L40S 上的有效吞吐（含梯度检查点）约 **1500~3000 token/s**
- 预计训练时长：**约 3.5~7 小时**（受 batch/序列长度/数据加载影响）
- 合并（CPU 烘焙）几分钟，可忽略

| 实例 | 单价 | 训练时长 | 单轮训练费用 |
|---|---|---|---|
| 1×L40S（优先） | ~¥2.25/小时 | ~5 小时 | **~¥11** |
| 2×L40S（只用 1 卡） | ¥4.50/小时 | ~5 小时 | ~¥22（浪费 1 卡） |

> 费用仅为训练环节；基座下载、合并不计费（实例内操作）。建议选 1×L40S 实例，费用最低。

---

## 7. 风险与排错

- **OOM**：降到 `--batch 4` 或 `--grad-accum 8`；QLoRA 下几乎不会 OOM。
- **维度不匹配**：`--base` 必须是 Qwen3-8B（与 LoRA 同源）。用 Qwen2.5 系列会直接报错。
- **训练网络: 无**：只做单卡，**不要** attempt 多节点/多卡 DDP（无高速互联，且单卡已够）。
- **数据格式**：`train_virtu.py` 自动吃 `messages`（ShareGPT）和 `instruction` 两种格式；盲测文件缺 assistant 答案会被自动跳过。
- **中断续训**：加 `--resume checkpoints/virtu_lora_trained`（指向最近 checkpoint）。

---

## 8. 一句话结论

单卡 L40S（48GB）跑 **QLoRA** 即可把 Virtu 训出来：基座 4-bit 量化 + r=32 LoRA，3 epoch 约 3.5~7 小时、费用约 ¥11（1 卡实例）。训完用 `merge_lora.py` 烤成单目录模型，再经 `start_virtu_bridge.py` 接回 WorkBuddy，就是**真正属于你、离线可跑、会聊天也懂 CAD** 的 Virtu 模型——不再是云端通义千问的转发。
