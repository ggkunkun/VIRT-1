# Virtu 本地真模型 · 全链路运行手册

> 合并 → GGUF → Ollama → WorkBuddy，全程本机完成，零 torch / 零 peft / 零远程 GPU
> 更新日期：2026-10-30（全部为实测，非文档声称）
> 配套脚本：`scripts/download_base_modelscope.py`、`scripts/merge_numpy.py`、
> `scripts/validate_merged.py`、`scripts/hf_to_gguf_numpy.py`、
> `scripts/Modelfile.virtu-omni`、`start_virtu_bridge.py`

---

## 0. 结论先行：本机全链路已跑通

```
ModelScope 下载 Qwen3-8B 基座 (16.4GB)
   ↓ scripts/merge_numpy.py --mode peft_linear      纯 numpy 流式合并 4 个 r=32 LoRA
checkpoints/virtu_merged/  (8.19B / 5 分片 / HF 目录)
   ↓ scripts/hf_to_gguf_numpy.py                   纯 numpy 流式转 Q4_0 GGUF
checkpoints/virtu-q4_0.gguf  (4.61GB)
   ↓ ollama create -f scripts/Modelfile.virtu-omni  Ollama 加载标准 GGUF（不走 MLX）
Ollama: virtu-omni-8b:latest  (Q4_0, 整卡 GPU 卸载)
   ↓ python start_virtu_bridge.py                  自动探测 → vllm_http 指向 Ollama
WorkBuddy 桥 :8000 / model id = virtu-cad-cam-10b  ← 本地真模型，不再是云端转发
```

**旧版"必须上 GPU 机 / 本机只能合并"的结论已被实测推翻**：

| 检查项 | 旧版声称 | 本次实测 |
|---|---|---|
| GPU | 无 | **RTX 4050 Laptop 6GB**（空闲 5.8GB） |
| 内存 | 可用 1.8GB | 可用 3.5GB（总 16.9GB） |
| numpy | — | **2.5.4 已装**（够，无需 torch） |
| Ollama | — | **0.35.1 在运行**，模型库 `E:\ollama\models` |
| 推理 | 需大内存机器 | **Q4_0 4.6GB 整卡卸载，实测 21.2 tok/s** |

---

## 1~2. 基座下载 + 纯 numpy 合并（已完成，可复现）

```bash
python scripts/download_base_modelscope.py checkpoints/_base_qwen3_8b
python scripts/merge_numpy.py --base checkpoints/_base_qwen3_8b \
    --probe-amplitude --probe-samples 12
python scripts/merge_numpy.py --base checkpoints/_base_qwen3_8b \
    --out checkpoints/virtu_merged --mode peft_linear --verify-samples 3
python scripts/validate_merged.py --merged checkpoints/virtu_merged \
    --base checkpoints/_base_qwen3_8b
```

要点：
- **基座必须是 `Qwen/Qwen3-8B`（非 Instruct）**——6 个 LoRA 的 `adapter_config.json`
  全部指向它；且它自带 chat_template（4168 字符，含 `{%- if tools %}` 段），
  而 `Qwen3-8B-Instruct` 在 ModelScope **404**。
- LoRA 合并不改变任何张量的 shape/dtype/data_offsets → 逐分片流式处理，
  只对 7 个投影层叠加 delta，其余按 4MB 分块字节拷贝，峰值内存 <1GB。
- `peft_linear` 逐位复现 peft 0.21.2 `add_weighted_adapter(linear)`：
  `gᵢ=wᵢ·sᵢ; A_new=Σ√gᵢAᵢ; B_new=Σ√gᵢBᵢ; ΔW=B_new@A_new`（含 cross terms）。
  幅度预检 delta/base RMS mean 2.18% / max 4.13%，健康。
- 只合并 4 个 r=32 LoRA（turing 1.2 / six_software 1.0 / omni_agent 0.8 / ug_teacher 0.7）；
  排除 `tool_agent_lora_final`（r=16，rank 不兼容）与
  `damodel_l40s_cad_cam_lora`（与 six_software 回执完全相同，重复拷贝）。

---

## 3. HF → GGUF Q4_0（本轮新增，关键一步）

```bash
python scripts/hf_to_gguf_numpy.py --check     # 自测：量化往返 / bf16 / 张量名映射
python scripts/hf_to_gguf_numpy.py \
    --model checkpoints/virtu_merged \
    --out checkpoints/virtu-q4_0.gguf
```

产出：**399 张量 / 254 个 Q4_0 权重 + 145 个 F32 norm / 29 项 metadata /
151936 tokens / 151387 merges / 4.61GB**，回执
`checkpoints/virtu-q4_0.gguf.receipt.json`。

### 为什么自己写，而不是用现成工具

| 路径 | 结果 |
|---|---|
| Ollama 直接从 safetensors 目录 `ollama create --force` | ❌ 能导入，但**运行时强依赖 MLX**（Windows 报 `MLX runtime is not available`）。`--force` 只跳过创建校验。已删除该模型释放 16GB。 |
| llama.cpp 官方 Windows 预编译包（GitHub release） | ❌ 下载被限速 **22KB/s**，420s 仅 9.2MB 残包，不可行 |
| 官方 `convert_hf_to_gguf.py` | ❌ 新版需 torch + `gguf` 包（清华源无该包）+ 大内存 |
| **纯 numpy 自写转换器** | ✅ 零网络依赖，峰值 <200MB，8.19B 参数约 2 分钟 |

**Ollama 加载标准 GGUF 是稳定老能力，不需要 MLX** —— 这就是活路。

### 三个必须踩对的格式点

1. **vocab 补齐（最容易翻车）**：HF `config.vocab_size=151936`（embed/lm_head
   按此对齐存储），但 tokenizer 实际只有 **151643** 个 token。
   GGUF 的 `tokenizer.ggml.tokens` 数组必须补齐到 **151936**（尾部用 `[PADi]` 占位），
   否则 llama.cpp 拒绝加载：
   ```
   check_tensor_dims: tensor 'token_embd.weight' has wrong shape;
   expected 4096, 151643, got 4096, 151936
   ```
2. **Q4_0 量化**：`d = amax / -8`（fp16 存储）、`q = clip(round(x/d), -8, 7) + 8`，
   每 32 权重 → 2B scale + 16B packed nibble = 18B。2D 权重量化，1D norm 保留 F32。
   自测往返 max_abs_err 0.0091。
3. **张量名映射 + dims 反转**：HF `model.layers.N.self_attn.q_proj.weight`
   → `blk.N.attn_q.weight`（Qwen3 还有 `attn_q_norm`/`attn_k_norm`）；
   GGUF tensor info 的 dims 按 GGML 规约 `shape[::-1]` 写入，数据区字节序不变。

---

## 4. Ollama 导入（已完成）

```bash
# Windows 上 CLI 与 localhost 请求都会被透明代理 HTTP_PROXY=127.0.0.1:53004 拦截，
# 必须清空代理并设 NO_PROXY
NO_PROXY="127.0.0.1,localhost" no_proxy="127.0.0.1,localhost" \
HTTP_PROXY= HTTPS_PROXY= http_proxy= https_proxy= ALL_PROXY= all_proxy= \
ollama create virtu-omni-8b -f scripts/Modelfile.virtu-omni
```

`scripts/Modelfile.virtu-omni` 关键参数：

```
FROM D:/Virtu模型/checkpoints/virtu-q4_0.gguf
PARAMETER num_ctx 4096
PARAMETER temperature 0.3          # ≥0.7 会语义断裂，见 §6
PARAMETER stop "<|im_end|>"
PARAMETER stop "<|im_start|>"
PARAMETER stop "<|endoftext|>"
```

验证：

```bash
curl --noproxy '*' -s http://127.0.0.1:11434/api/show \
  -d '{"model":"virtu-omni-8b"}'
# → details.family=qwen3 / 8.2B / Q4_0
# → capabilities = ['tools','thinking','completion']
# → template 含 {%- if tools %} 段（GGUF 里的 chat_template 被正确读取）
```

---

## 5. 接入 WorkBuddy（已自动化 + 端到端验证）

```bash
python start_virtu_bridge.py --check    # 诊断
python start_virtu_bridge.py            # 启动桥 :8000
```

`start_virtu_bridge.py` 的自动决策：

1. 检测到 `checkpoints/virtu_merged/config.json` 或 `checkpoints/virtu-q4_0.gguf`；
2. `probe_ollama()` 用 `urllib + ProxyHandler({})` 绕过透明代理探测本机
   `127.0.0.1:11434/api/tags` 是否有 `virtu-omni-8b`；
3. 有模型且本机无 torch → 自动设 `VIRTU_VLLM_URL=http://127.0.0.1:11434/v1`、
   `VIRTU_VLLM_MODEL=virtu-omni-8b`，走 `vllm_http` 后端（并清空运行时 LoRA，
   避免双重叠加）；
4. 有大内存 + torch 的机器仍优先 `transformers`；有 `llama_cpp` 时可用 GGUF 的
   `llamacpp`；都没有才回退 `cloud`。

`virtu_real_backend.py` 针对 Ollama 端点的两处修正：
- `_gen_vllm` 加 `think: false`（Qwen3 thinking 会让 base+LoRA 胡言乱语）；
- 请求用 `build_opener(ProxyHandler({}))` 绕过透明代理（否则 502/超时）。

**端到端实测结果**：

```
/health                 → {"status":"healthy","model":"virtu-cad-cam-10b"}
/v1/models              → data[0].id = virtu-cad-cam-10b
/v1/chat/completions    → 往返 22.4s，返回内容来自本地 Q4_0 模型（非云端转发）
--check                 → backend available: True / resolved backend: vllm_http
Ollama /api/ps          → size 5.08GB, vram 4.24GB（整卡卸载）
首次加载 15.4s，生成 21.2 tok/s
```

> ⚠️ 若外部环境残留 `VIRTU_MODEL_PATH` 等旧变量，会跳过自动探测改走
> transformers 而失败。启动时先 `unset VIRTU_MODEL_PATH VIRTU_GGUF_PATH VIRTU_VLLM_URL`
> 或显式 `python start_virtu_bridge.py --backend vllm_http --vllm http://127.0.0.1:11434/v1`。

---

## 6. 使用须知（质量边界，必须知道）

**① thinking + 温度是生死线（实测对照）**

| 设置 | 输出 |
|---|---|
| `temperature=0.7` + thinking 开 | ❌ 语义断裂、重复刷屏、G 代码碎片 |
| `think:false` + `temperature=0.1` | ✅ 流畅："我是由阿里巴巴集团旗下的通义实验室自主研发的超大规模语言模型。我的参数量高达110亿…随时告诉我！" |
| 手动 ChatML + `0.3` | ✅ 基本正常（结尾略飘） |

已固化三处：Modelfile `temperature 0.3`、launcher `DEFAULTS.temperature=0.3`、
backend 对 11434 端点 `think:false`。

**② 工具调用尚未达标（已知，需下一步训练）**
带 `tools` 请求时模型会输出"已调用工具：generate_solidworks_macro"和类 JSON 参数，
但**不返回标准 `tool_calls` 字段**，且参数有幻觉（LENGTH 30→35）、重复刷屏。
根因：`tool_agent_lora_final`（r=16）因 rank 冲突未合并、23,178 条新 tool_call 语料
**尚未训练**。解法见 §7。

**③ base + LoRA 的固有局限**
基座是 `Qwen3-8B`（**base 非 Instruct**），仅烤进 4 个 LoRA（6024 条 SFT 训练），
输出偶有杂糅与 stop token 残留（`<|_tele`）。这是模型能力问题，不是链路 bug。

---

## 7. 可选：训练工具调用 LoRA（r=16）

```bash
python scripts/train_virtu_toolcall.py --base checkpoints/_base_qwen3_8b --probe-only
python scripts/train_virtu_toolcall.py --base checkpoints/_base_qwen3_8b \
    --data damodel_cad_cam_tuning/dataset/virtu_toolcall_train_unified.jsonl \
    --mode qlora --epochs 3 --single-gpu
```

产出 r=16 LoRA，不能与 r=32 那批 linear 合并，但可在推理时单独挂载
（维度一致，peft 可直接加载）。训练完需重跑 §1~§4 全链路把新能力烤进 GGUF。

---

## 8. 常见坑速查

| 症状 | 处理 |
|---|---|
| `MLX runtime is not available` | 不要用 Ollama 直接导入 safetensors 目录；先转标准 GGUF（§3） |
| `check_tensor_dims: expected ...151643, got ...151936` | tokens 数组补齐到 `config.vocab_size`（§3 格式点 1） |
| Ollama CLI `model not found` / 请求超时 | 透明代理拦 localhost：CLI 设 `NO_PROXY=127.0.0.1,localhost`，Python 用 `ProxyHandler({})` |
| 回答胡言乱语/刷屏 | 关 thinking + temperature ≤0.3（§6） |
| 桥仍走 cloud / transformers | 检查是否有残留 `VIRTU_MODEL_PATH`；确认 Ollama 服务在跑（§5） |
| 合并产物被重复挂 LoRA | 已修：目录带 `merge_receipt.json` 时 backend 忽略运行时 LoRA；launcher 清空非显式 LoRA |
| `LoRA rank 不一致` | 只合同 rank 的 4 个 r=32；r=16 单独挂载 |
| `Qwen3-8B-Instruct` 下载 404 | ModelScope 用 `Qwen/Qwen3-8B` |
| 长写盘任务后台跑被降权 | Bash 后台约 7 分钟后降权；长任务走前台或分批，合并器有 `--resume` |
| E 盘空间不足 | 模型库在 `E:\ollama\models`（本轮剩 ~24GB）；`ollama rm` 删不用的模型 |

---

## 9. 交付物清单

| 文件 | 说明 |
|---|---|
| `checkpoints/_base_qwen3_8b/` | Qwen3-8B 基座 16.4GB / 13 文件 |
| `checkpoints/virtu_merged/` | 合并产物 8.19B HF 目录 + `merge_receipt.json` + `validation_report.json` |
| `checkpoints/virtu-q4_0.gguf` | **最终本地模型 4.61GB**（Q4_0）+ `.receipt.json` |
| `scripts/download_base_modelscope.py` | 零依赖断点续传下载器 |
| `scripts/merge_numpy.py` | 纯 numpy 流式 LoRA 合并器（`--resume` / `--probe-amplitude`） |
| `scripts/validate_merged.py` | 合并产物结构 + 可加载性校验 |
| `scripts/hf_to_gguf_numpy.py` | **纯 numpy HF→GGUF Q4_0 转换器**（本轮新增） |
| `scripts/Modelfile.virtu-omni` | Ollama 导入配置（GGUF 版） |
| `start_virtu_bridge.py` | 自动探测 Ollama / transformers / llamacpp / cloud |
| `virtu_real_backend.py` | 真后端（vllm_http 对 Ollama 关 thinking + 绕代理） |
