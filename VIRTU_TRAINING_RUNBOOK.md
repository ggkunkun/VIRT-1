# Virtu 真模型训练与产出 Runbook

> 目标：把一个"真正属于你、能正常聊天、也懂工业 CAD/CAM"的 Virtu 模型做出来并跑起来。
> 本文件是"选项 3（做出真 Virtu 模型）"的操作手册。

---

## 0. 先说清楚事实（别被名字骗了）

| 你以为的 | 实际工程里的 |
|---|---|
| `virtu-cad-cam-10b` 是个 10B 自研大模型 | 名字是品牌名；**真实基座是 Qwen3-8B（8B）**，LoRA 都挂在它上面 |
| 之前"不像人说话"是因为模型本身不行 | 是因为桥 `workbuddy_virtu_bridge.py` 用 `_synthesize_response` **写死模板**假装回答，根本没调真模型 |
| 没有训练数据 | `damodel_cad_cam_tuning/dataset/` 下有一批标准 ShareGPT SFT 数据；6 个 LoRA 是**真实在远程 L40S 上训出来的**（有 `adapter_model.safetensors`、有 `training_receipt.json`） |

**结论**：你已经有"真模型"的零件了——Qwen3-8B 基座 + 多个真实 LoRA + SFT 数据。
"做出真 Virtu 模型" = 把这些零件**合并/继续训练**成一个可在本地离线跑的权重。

---

## 1. 硬件与依赖（在哪跑）

本机（Windows，无 torch / 无 GPU / 无 Qwen3-8B 权重）**跑不了训练和合并**，只能写代码、验证语法。

你需要一台 GPU 机器，三选一：

| 机器 | 推荐模式 | 显存 | 能否合 LoRA |
|---|---|---|---|
| 远程 Damodel 2×L40S（工程里现成的 SSH 部署目标） | `lora` / `qlora` | 48GB×2 | 能（CPU 内存够即可） |
| 本地单卡 RTX 4090 / 3090 / A10 | `qlora` | ~24GB | 能 |
| 本地多卡 A100/H100 | `lora` / `full` | 80GB×N | 能 |

依赖（在 GPU 机器装）：
```bash
pip install torch --index-url https://download.pytorch.org/whl/cu124   # 按 CUDA 版本
pip install transformers peft accelerate datasets
pip install bitsandbytes            # 仅 qlora 模式需要
```

基座权重：Qwen3-8B-Instruct（必须与 LoRA 基底同源）。国内用 ModelScope：
```bash
pip install modelscope
modelscope download --model Qwen/Qwen3-8B-Instruct --local_dir /root/models/Qwen3-8B-Instruct
```

---

## 2. 路径 A：直接合并现有 LoRA（最快拿到"你的模型"，不重训）

LoRA 已经训好了，直接把 Qwen3-8B + 你的 LoRA 烘焙成一个模型：

```bash
# 默认合「对话 + CAD」两个核心 LoRA
python merge_lora.py --base /root/models/Qwen3-8B-Instruct

# 或把全部 6 个 Virtu LoRA 叠加成"全能 Virtu"
python merge_lora.py --base /root/models/Qwen3-8B-Instruct --all
```
产出：`checkpoints/virtu_merged/`（单目录，含 config + 权重 + tokenizer）。

> 合并只是线性叠加权重，几分钟内完成，不需要重训。

---

## 3. 路径 B：继续训练 / 再训一版（当你有新数据或想调能力）

```bash
# QLoRA（24GB 单卡）吃全部 SFT 数据
python train_virtu.py --base /root/models/Qwen3-8B-Instruct --mode qlora

# 或 L40S 上 bf16 LoRA
python train_virtu.py --base /root/models/Qwen3-8B-Instruct --mode lora --epochs 3

# 只吃你新增的数据目录
python train_virtu.py --base /root/models/Qwen3-8B-Instruct --mode qlora \
    --data /path/to/your_extra_sft
```

产出一个新 LoRA：`checkpoints/virtu_lora_trained/virtu_lora_final/`。
再把它并进基座：
```bash
python merge_lora.py --base /root/models/Qwen3-8B-Instruct \
    --lora checkpoints/virtu_lora_trained/virtu_lora_final --weight 1.0
```

> 工程里 `scripts/deploy_*_training.py` 已能经 SSH 把代码+数据推到远程 L40S 并拉起 `train_cad_cam_l40s.py`；`train_virtu.py` 是更通用的替代版（自动吃全部数据集、支持 qlora）。

---

## 4. 把"你的模型"接回 WorkBuddy

合并产出 `checkpoints/virtu_merged/` 后，两种接法：

**(a) transformers 后端（有 GPU 的机器）**
```bash
VIRTU_BACKEND=transformers VIRTU_MODEL_PATH=checkpoints/virtu_merged \
    python start_virtu_bridge.py
```

**(b) llama.cpp 后端（无 GPU、纯 CPU / 苹果 / 低端卡也能跑）**
先把 HF 权重转 GGUF：
```bash
# 用 llama.cpp 自带转换脚本
python llama.cpp/convert_hf_to_gguf.py checkpoints/virtu_merged --outfile virtu.Q4_K_M.gguf
# 量化（可选，更小更快）
./llama-quantize virtu.Q4_K_M.gguf virtu.Q4_K_M.gguf q4_k_m
```
再起桥：
```bash
VIRTU_BACKEND=llamacpp VIRTU_GGUF_PATH=virtu.Q4_K_M.gguf python start_virtu_bridge.py
```
WorkBuddy 里选 `virtu-cad-cam-10b` 即可——此时回答来自**你本地合并出的真模型**，不再是云端通义千问。

---

## 5. 验证"它是真模型"

```bash
curl -s --noproxy 127.0.0.1 -X POST http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"virtu-cad-cam-10b","messages":[{"role":"user","content":"你好，你是谁？"}],"stream":false}'
```
- 若接了 (a)/(b) 本地模型：回答体感应是"带 Virtu/CAD 专业味"的真生成，而不是模板黑人话。
- 若仍显示"我是通义千问"：说明桥回退到了 cloud 转发（没设 VIRTU_MODEL_PATH / 没起本地模型），见 §6。

---

## 6. 常见坑

- **维度不匹配**：`VIRTU_MODEL_PATH` 指向的基座必须是 Qwen3-8B（与 LoRA 同源），用 Qwen2.5-14B 会直接报错。
- **本机透明代理劫持 localhost**：桥必须监听 `127.0.0.1:8000`、WorkBuddy 直连；curl 加 `--noproxy 127.0.0.1`。
- **回退到 cloud**：`virtu_real_backend.py` 在未配置本地权重时会自动转发云端真实模型（所以之前才回"通义千问"）。要纯本地，必须设 `VIRTU_BACKEND=transformers/llamacpp` + 权重路径。
- **想"真正 10B 而非 8B"**：当前 LoRA 全基于 8B，要做 10B 得换 10B 基座并重训 LoRA（需 10B 预训练权重 + 全量训练算力），不在本工程现成能力内。

---

## 7. 一句话总结

真模型 = **Qwen3-8B 基座 + 你已有的真实 LoRA（合并或继续训练）**。零件都齐了，
本机只能写/验证代码，真正"造模"要在 GPU 机器上跑 `merge_lora.py` / `train_virtu.py`，
再把 `checkpoints/virtu_merged` 经 `start_virtu_bridge.py` 接回 WorkBuddy。
