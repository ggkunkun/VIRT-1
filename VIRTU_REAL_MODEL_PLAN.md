# Virtu-CAD-CAM 真·大模型改造方案（B 计划）

> 目标：把 `virtu-cad-cam-10b` 从「模板合成 / 假推理」升级为「真实自回归生成」，
> 让它像正常人一样聊天，同时在涉及 CAD/CAM/制造时切换到工业能力。
> 配套代码已落地：`virtu_real_backend.py` + `scripts/workbuddy_virtu_bridge.py` 的最小改动。

---

## 0. 当前问题诊断（已实证）

| 现象 | 根因 |
|---|---|
| 说"你好"回一长串"六大工业软件" | `workbuddy_virtu_bridge.py` 的 `_synthesize_response` 对所有输入强制走工业人设 |
| 模型从不真正"生成" | `_synthesize_response` 是纯 Python 模板，没接任何 LLM |
| `virtu_omni_10b_base.pt` 仅 2.3GB | 对 10B(fp16≈20GB) 太小，是占位/无效权重，无法加载推理 |
| 本项目 Python 环境没装 `torch` | `virtu_omni` 真实架构从未真正跑过 |
| LoRA 的 `base_model_name_or_path` = `/root/.../Qwen3-8B` | 真·底层基座是 **Qwen3-8B**（Linux 路径，本机不存在） |

**结论**：当前不是"自研 10B 已训练模型"，而是指向 Qwen3-8B 的脚手架 + 假推理壳。
要"真正像人对话"，最现实的是接一个**真实的 Qwen 基座 + 你的对话/CAD LoRA**，做真推理。

---

## 1. 目标架构

```
 WorkBuddy 对话
      │  OpenAI /v1/chat/completions
      ▼
 scripts/workbuddy_virtu_bridge.py  (HTTP 服务，端口 8000)
      │
      ├─ _generate_response()  ── 新增：优先走真后端
      │        │
      │        ▼
      │   virtu_real_backend.py  (单例，懒加载)
      │        ├─ transformers  (HF + peft: base + 对话LoRA / CAD LoRA，意图切换)
      │        ├─ llamacpp      (GGUF，CPU/Apple-Metal/CUDA，本地最轻量)
      │        └─ vllm_http     (指向已运行的 vLLM/OpenAI 端点)
      │
      └─ _synthesize_response()  ── 旧逻辑：真后端不可用时自动回退（保底，不破坏服务）
```

**意图路由**（已在后端实现）：
- 普通聊天 → base + `turing_conversational_lora`（正常对话）
- 制造/CAD 意图（命中关键词如 cad/数控/叶轮/G54…）→ 切换到 `cad_cam_six_software_lora`

---

## 2. 文件改动清单

| 文件 | 改动 | 风险 |
|---|---|---|
| `virtu_real_backend.py` | **新增**。真推理后端，支持三种接入 + 意图路由 + 优雅降级。重量级依赖全部延迟导入，未安装也不报错。 | 无（新文件） |
| `scripts/workbuddy_virtu_bridge.py` (~977 行) | 把 `response_text = self._synthesize_response(...)` 改为 `response_text, thought = self._generate_response(...)`；**新增** `_generate_response()` 方法：优先调真后端，异常则回退旧逻辑。 | 低（旧逻辑保留为 fallback） |

> 验证：`py_compile` 两个文件均通过；后端在无 torch/无权重时 `available=False` 且不抛异常。

---

## 3. 三种部署路径（按你的硬件选一条）

### 路径 A：本机 Windows、无独显 → llama.cpp（GGUF）
最适合当前环境，无需 CUDA，纯 CPU 也能跑（Q4 量化约 5–9GB 内存）。

```bat
:: 1) 装轻量依赖（在目标机执行）
pip install llama-cpp-python

:: 2) 取真实基座权重（选一）：
::    - Qwen3-8B-Instruct（与你的 LoRA 基底一致，推荐）
::    - 或 Qwen2.5-14B-Instruct（容量更大，但不能直接挂 Qwen3 的 LoRA）
::    国内走 ModelScope 镜像，避免境外域名被墙：
::    https://modelscope.cn/models/Qwen/Qwen3-8B-Instruct  (下载 .gguf 量化版，如 Q4_K_M)
::    或自行转换：
::      git clone https://github.com/ggml-org/llama.cpp
::      python llama.cpp/convert_hf_to_gguf.py <Qwen3-8B目录> --outfile virtu-q3-8b.Q4_K_M.gguf
::      ./llama.cpp/quantize virtu-q3-8b.gguf virtu-q3-8b.Q4_K_M.gguf Q4_K_M

:: 3) 启动桥前设置环境变量
set VIRTU_BACKEND=llamacpp
set VIRTU_GGUF_PATH=D:/Virtu模型/models/virtu-q3-8b.Q4_K_M.gguf
:: 本路径下 LoRA 通过 system 提示注入，无需单独挂载
```

### 路径 B：有 GPU 的机器 → transformers + peft（最强，能真正挂 LoRA）
```bash
pip install torch transformers peft accelerate bitsandbytes
# 若显存有限，用 4-bit 加载（代码已支持 torch_dtype="auto" + device_map="auto"）

export VIRTU_BACKEND=transformers
export VIRTU_MODEL_PATH=/path/to/Qwen3-8B-Instruct      # 必须与 LoRA 基底版本一致
export VIRTU_CONV_LORA=/d/Virtu模型/checkpoints/turing_conversational_lora
export VIRTU_CAD_LORA=/d/Virtu模型/checkpoints/cad_cam_six_software_lora
export VIRTU_DEVICE=auto
```
> 注意：LoRA 基底是 **Qwen3-8B**，所以 `VIRTU_MODEL_PATH` 必须也是 Qwen3-8B，否则 peft 加载会维度不匹配。
> 若想用 Qwen2.5-14B 当"更大容量"的脑，则应先把 LoRA 重新训练/合并到该基座，不能直接挂。

### 路径 C：已有 vLLM 服务 → 直连端点（生产推荐，吞吐最高）
```bash
# 机器 A 起 vLLM（示例）
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen3-8B-Instruct --dtype auto --gpu-memory-utilization 0.9

# 桥所在机器设置
export VIRTU_BACKEND=vllm_http
export VIRTU_VLLM_URL=http://<机器A>:8001/v1
export VIRTU_VLLM_MODEL=Qwen3-8B-Instruct
```

---

## 4. 启动与验证

```bash
cd /d/Virtu模型/scripts
:: 按所选路径先设好环境变量，再启动桥
python workbuddy_virtu_bridge.py
```

正常对话验证（真后端已就绪时应返回自然聊天，而非工业黑话）：
```bash
curl http://127.0.0.1:8000/v1/chat/completions ^
  -H "Content-Type: application/json" ^
  -d "{\"model\":\"virtu-cad-cam-10b\",\"messages\":[{\"role\":\"user\",\"content\":\"你好，今天天气不错\"}]}"
```

回退验证（未配置权重时，桥日志会打印 `real backend unavailable ...`，并仍用旧的工业人设兜底，服务不崩）：
```bash
:: 不设置任何 VIRTU_* 变量直接启动，观察日志
python workbuddy_virtu_bridge.py
```

---

## 5. 风险与注意事项

1. **依赖**：本机 Python 环境当前**未装 torch**，`virtu_real_backend.py` 已做延迟导入与降级，但真正推理需在目标机 `pip install` 对应依赖。
2. **LoRA 基底一致性**：`turing_conversational_lora` 与 `cad_cam_six_software_lora` 的基底是 Qwen3-8B，base 权重必须同源同版本。
3. **网络**：境外 HuggingFace 域名在本机可能被墙，优先用 **ModelScope** 国内镜像下载基座与 GGUF。
4. **显存/内存**：8B 模型 Q4 量化约 5–6GB；不量化 fp16 约 16GB；14B 需更大。按机器容量选量化档。
5. **兜底不变**：旧的 `_synthesize_response` 完整保留，真后端任何异常都会自动回退，原"工业 agent"能力不丢失。

---

## 6. 后续可选项（非必须）

- **合并 LoRA 到基座**：用 `peft` 的 `merge_and_unload()` 把对话/CAD LoRA 合并成单一权重，省去运行时切换。
- **真正从零训练 10B**：见对话中给出的六大条件（数据 200B–1T tok、A100/H100 集群、Megatron/DeepSpeed、数十万–数百万 ¥、1–6 个月）。当前阶段不建议，先用开源基座 + LoRA 是最优解。
- **更细的意图路由**：把关键词命中升级为轻量分类器（如用 Qwen 本身做 1-token 路由），减少误判。
