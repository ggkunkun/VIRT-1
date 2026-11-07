# Virtu-CAD-CAM 真·大模型 · 从零跑起来操作手册

> 本文档把整套改造工具链串成一条可执行路径：从"假推理模板"升级为"真实自回归生成"，
> 让模型能像正常人一样聊天，并在涉及 CAD/CAM/制造时切换到工业能力。
> 配套脚本均已通过语法/降级验证，本文给出在**能联网、已装依赖的机器**上的完整步骤。

---

## 0.5 🚀 零算力极速接入（已落地·推荐，无需本地 GPU/权重）

如果你只想让 WorkBuddy 里的 `virtu-cad-cam-10b` **立刻像人一样对话**，最省事的路已经打通：
桥新增 **cloud 转发后端**，本机无需 `torch`、无需任何本地权重，自动读取你 `~/.workbuddy/models.json`
里已有的国内可直连模型（优先阿里百炼 dashscope，其次智谱 bigmodel），把对话转发给真实大模型。

**两步即可：**
1. 启动桥（默认就走 cloud）：
   ```bash
   python start_virtu_bridge.py          # 或双击 start_virtu.bat 选 [1]
   ```
2. 在 WorkBuddy 的模型选择里选 **virtu-cad-cam-10b**，直接聊天即可。
   （`models.json` 里这条配置本来就存在，指向 `http://127.0.0.1:8000/v1/chat/completions`）

**已验证**：`/v1/models` 正常返回；发"你好"得到"我是通义千问…能陪你聊天、解答问题"；
发"什么是 GD&T"得到准确工程定义——说明它已经是一个**真·大模型对话**，而非工业黑人话。

> 注意：cloud 模式下模型本体在云端（dashscope/bigmodel），Virtu 在这里是"接入层 + 路由层"。
> 若你后续拿到本地 Qwen3-8B 权重，切到 transformers/llamacpp 后端即可完全本地离线推理，代码已就绪。

## 0.6 🖼️ 视觉/多模态通道（已落地·本地 Qwen3-VL-2B 优先，云端兜底）

本地 Virtu 文本权重是 Qwen3-8B（`Qwen3ForCausalLM`，无视觉编码器），图片不经过它。
带图请求由桥单独路由到视觉通道，按 `VIRTU_VISION_MODE` 选路：

| 模式 | 行为 |
|---|---|
| `auto`（默认） | `models/Qwen3-VL-2B-Instruct` 存在 → 本地；不存在或加载/推理失败 → 云端 |
| `local` | 只用本地，完全离线；失败直接报「视觉通道未就绪」 |
| `cloud` | 只用云端（智谱 `glm-4.5v`，复用 models.json 的 bigmodel key） |

**本地模型**：Qwen3-VL-2B-Instruct（ModelScope，权重 4.26GB，位于 `models/Qwen3-VL-2B-Instruct`），
首次看图时懒加载并做 4-bit NF4 量化。实测（2026-10-31，RTX 4050 6GB）：
峰值显存 1.75GB；经桥首张图 42.7s（含约 12s 权重加载），第二张 2.7s；纯文本链路不受影响。

**通道对比**（合成标注图 3 例，`scripts/eval_vision_channels.py`）：
本地严格命中 1/3（`VX7Q` 被读成 `VX70`；`M8x1.25` 读成 `M8×1.25`，语义正确），热请求 1.3~1.6s；
云端 `glm-4.5v` 3/3，2.0~2.6s。默认 `auto` 仍**本地优先**（图纸不出本机）；
追求精度可用 `VIRTU_VISION_MODE=cloud`。

**配置**（均可选）：
```bash
VIRTU_VISION_MODE=auto           # auto|local|cloud
VIRTU_VISION_LOCAL_PATH=D:/Virtu模型/models/Qwen3-VL-2B-Instruct
VIRTU_VISION_BASE_URL=...        # 仅云端需要
VIRTU_VISION_API_KEY=...
VIRTU_VISION_MODEL=glm-4.5v
VIRTU_VIDEO_MAX_FRAMES=16        # 视频抽帧上限
VIRTU_VIDEO_MAX_SIDE=640         # 每帧最长边
VIRTU_VIDEO_MAX_SECONDS=30       # 只处理前 N 秒
```

- 路由优先级：图片/视频请求 > CAD 工具编排（工具链路没有媒体输入，先走会把媒体丢掉）。
- 本地模型加载失败/显存不足时，auto 模式自动回落云端，日志会打印原因。
- 无任何视觉通道时返回「【视觉通道未就绪】…」，不会静默丢图、也不会假装看过图。
- `stream=false` / `stream=true` 均已验证（640×360 测试图读出 `VX7Q`）。

**视频理解（仅本地模型）**：桥接受 `video_url` / `input_video` / `video` 内容块，PyAV 解码后按时间
均匀抽帧（默认 ≤16 帧、每帧 ≤640px、只取前 30 秒），连同 `video_metadata` 送入 Qwen3-VL。
云端视觉接口（`glm-4.5v`）不支持视频，视频请求会明确报错而不会退回图片通道。

实测（2026-10-31）：2 秒 mp4（前 1s `ALPHA`、后 1s `OMEGA`，10fps）→ 抽 16 帧 → 回答
`ALPHA\nOMEGA`；经桥首条视频 46.9s（含约 45s 权重加载），第二条 1.4s，显存峰值 1.74GB。
WorkBuddy 的 `virtu-cad-cam-10b` 已加 `supportsVideo: true`（原配置备份在
`~/.workbuddy/models.json.bak_*`；若应用退出时回写覆盖，需重启后再补一次）。

> 启动方式：`start_virtu.bat` 现在优先用 `.venv\Scripts\python.exe` 启动桥——本地视觉依赖 venv 里的
> torch / transformers / bitsandbytes；用系统 Python 启动会自动回落云端视觉。

---

## 0. 先看现状（为什么会"不像人说话"）

| 现象 | 根因 |
|---|---|
| 说"你好"回一长串"六大工业软件" | 桥的 `_synthesize_response` 对所有输入强制工业人设 |
| 模型从不真正"生成" | 那是纯 Python 模板，没接任何 LLM |
| `virtu_omni_10b_base.pt` 仅 2.3GB | 对 10B(fp16≈20GB) 太小，是占位/无效权重 |
| 项目 Python 环境没装 `torch` | `virtu_omni` 真实架构从未真正跑过 |
| LoRA 基底 = `/root/.../Qwen3-8B` | 真·底层基座是 **Qwen3-8B**（本机不存在） |

**结论**：当前不是"自研 10B 已训练模型"，而是指向 Qwen3-8B 的脚手架 + 假推理壳。
最低成本做成"真模型" = 接一个**真实的 Qwen3-8B 基座 + 你的对话/CAD LoRA** 做真推理。

---

## 1. 工具链文件清单

| 文件 | 作用 |
|---|---|
| `virtu_real_backend.py` | 真推理后端：transformers / llama.cpp / vLLM 三后端 + 意图路由 + 优雅降级 |
| `scripts/workbuddy_virtu_bridge.py` | 桥服务(端口8000)。已改：真后端优先，失败自动回退旧工业人设 |
| `start_virtu_bridge.py` | 一键启动器：装依赖 → 设环境变量 → 校验后端 → 启桥；带 `--check` |
| `start_virtu.bat` | Windows 图形菜单（选后端 + 填路径），双击即用 |
| `download_qwen.py` | 自动下载 Qwen3-8B GGUF（ModelScope 国内源，带进度条） |
| `merge_lora.py` | 把对话/CAD LoRA 烘焙进基座，产出单一权重目录 |
| `VIRTU_REAL_MODEL_PLAN.md` | 改造方案文档（架构、改动清单、部署路径、风险） |

---

## 2. 环境准备

```bash
# 1) Python 3.10+（Windows 用官方安装包，勾选 "Add to PATH"）
python --version

# 2) 依赖（按所选后端装，启动器会自动补装缺失项）
#    llama.cpp 路径:    pip install llama-cpp-python
#    transformers 路径: pip install torch transformers peft accelerate
#    vLLM 路径:         无需本机装，指向已运行的 vLLM 服务即可
```

> 本沙箱当前未装 `torch`、也无真实权重，所以真推理必须在**你自己的机器**上执行。
> 这里的脚本只负责"接线"，不负责"产模型"。

---

## 3. 后端选型

| 后端 | 适用 | 显存/内存 | 能否挂你的 LoRA |
|---|---|---|---|
| **llama.cpp (GGUF)** | 本机无显卡也想跑 | Q4 约 5–6GB 内存 | 通过 system 提示注入（不单独挂） |
| **transformers + peft** | 有 GPU，要真正挂 LoRA | 8B fp16≈16GB / Q4≈6GB | ✅ 对话/CAD 按意图切换 |
| **vLLM HTTP** | 已有 vLLM 服务，要高吞吐 | 取决于服务端 | 取决于服务端加载方式 |

> ⚠️ 两个 LoRA 基底都是 **Qwen3-8B**，所以 transformers 路径的 `--model` 必须是 Qwen3-8B，
> 否则 peft 维度不匹配。想用 Qwen2.5-14B 得先把 LoRA 重训/合并过去。

---

## 4. 快速开始（最简：llama.cpp，无显卡）

```bash
# 第1步：下载 Qwen3-8B 的 Q4_K_M GGUF（默认存到 models/，约 5–6GB）
python download_qwen.py

# 第2步：启动（二选一）
#   方式A：双击 start_virtu.bat -> 选 1
#   方式B：命令行
python start_virtu_bridge.py --backend llamacpp --gguf models/Qwen3-8B-Instruct-Q4_K_M.gguf
```

启动后桥监听 `http://127.0.0.1:8000/v1`。这就是一个正常聊天模型了。

---

## 5. 详细步骤

### 5.1 transformers + 你的 LoRA（有 GPU，推荐保留工业能力）
```bash
# 取基座（与 LoRA 同版本）
python download_qwen.py --file Qwen3-8B-Instruct-Q4_K_M.gguf   # 或下完整目录到别处
# 或手动从 ModelScope 下 Qwen3-8B-Instruct 完整目录

python start_virtu_bridge.py --backend transformers --model /path/to/Qwen3-8B-Instruct
# 对话 LoRA 与 CAD LoRA 已在脚本 DEFAULTS 里指向 checkpoints/ 下对应目录
# 普通聊天 -> 对话 LoRA；命中 CAD 关键词 -> CAD LoRA（后端自动切换）
```

### 5.2 合并 LoRA 成单一权重（可选，启动更快、免切换）
```bash
python merge_lora.py --base /path/to/Qwen3-8B-Instruct --out checkpoints/virtu_merged
# 之后：
python start_virtu_bridge.py --backend transformers --model checkpoints/virtu_merged
```
> 合并会把两种能力线性叠加，可能相互稀释。若想保持各自独立、按需切换，保留 5.1 的方式即可。

### 5.3 vLLM（生产/高吞吐）
```bash
# 服务端（另一台/另一个终端）：
python -m vllm.entrypoints.openai.api_server --model Qwen/Qwen3-8B-Instruct --gpu-memory-utilization 0.9

# 桥所在机器：
python start_virtu_bridge.py --backend vllm_http --vllm http://<服务端>:8000/v1
```

---

## 6. 验证

```bash
# 正常聊天：应返回自然对话，而不是工业黑话
curl http://127.0.0.1:8000/v1/chat/completions ^
  -H "Content-Type: application/json" ^
  -d "{\"model\":\"virtu-cad-cam-10b\",\"messages\":[{\"role\":\"user\",\"content\":\"你好，今天过得怎么样\"}]}"

# 诊断（不启动服务，看后端是否就绪）：
python start_virtu_bridge.py --check
```

**回退验证**：不设置任何 `VIRTU_*` 变量直接启动，桥日志会打印
`real backend unavailable ...`，并仍用旧的工业人设兜底——服务不崩，原能力不丢。

---

## 7. 常见问题

| 问题 | 处理 |
|---|---|
| 启动报 `real backend unavailable: no usable backend configured` | 没设权重路径。按第4/5步设 `VIRTU_GGUF_PATH` 或 `VIRTU_MODEL_PATH` |
| transformers 加载报维度不匹配 | `--model` 不是 Qwen3-8B，换成 Qwen3-8B 基座 |
| 境外域名下载失败 | 用 `download_qwen.py`（ModelScope 国内源），或手动从 modelscope.cn 下 |
| 内存不足（OOM） | 改用 Q4_K_M GGUF，或 `VIRTU_MAX_TOKENS` 调小，或上 GPU |
| 想纯聊天不要工业味 | 用 llama.cpp 路径（不走 LoRA），或在 transformers 路径下不挂 CAD LoRA |

---

## 8. 一句话总结

`download_qwen.py` 取权重 → `start_virtu.bat`/ `start_virtu_bridge.py` 启动真后端 →
桥自动把"假合成"换成"真生成"，异常时回退旧逻辑保底。其余 `merge_lora.py`、方案文档按需取用。
