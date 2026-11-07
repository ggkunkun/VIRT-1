# Virtu 通用工具调用 Agent —— 训练落地方案书

| 项 | 内容 |
| --- | --- |
| 版本 | v1.0 |
| 日期 | 2026-10-29 |
| 目标 | 把当前文件夹的模型能力，训练成**通用工具调用 Agent**（OpenAI function-calling 协议，可接 WorkBuddy / 自定义 MCP 工具链） |
| Phase 0 策略 | **先用现有 1226 条数据跑通全链路**（不追求效果，只追求链路闭环），再谈扩量 |
| 底座 | Qwen3-8B（仓库内唯一被真实验证过的底座） |
| 硬件 | Phase 0 用 **L40S 48GB ¥4.50/h**；Phase 1 扩量/换大底座时切 **A800 80GB ¥6.90/h** |

---

## 0. 决策摘要（TL;DR）

| 决策 | 结论 | 依据 |
| --- | --- | --- |
| 底座模型 | **Qwen3-8B**（不是本文件夹的 .pt） | `standardized_weights.pt` 是 1.28B RNN 混合世界模型，无标准 chat LM head；`virtu_omni_10b_base.pt` 实测仅 0.58B/33 tensor 空壳 |
| Phase 0 硬件 | **L40S ¥4.50/h** | 与仓库唯一真实训练基线**同构**，实测 33.6 分钟可直接复用，零外推风险；且 Phase 0 无论哪张卡，总账都是几块钱 |
| Phase 1 硬件 | 需压墙钟/换 14B+ 底座时切 **A800 ¥6.90/h** | 1.72x 算力；成本几乎持平（见 §2.3） |
| 训练方式 | **LoRA r=16 + HF Trainer**（沿用 `train_cad_cam_l40s.py`） | 仓库里唯一被真跑通过、留下完整日志的路径 |
| 数据生成 | **零 LLM 成本**：重跑现有生成器并**捕获 spec** | 1226 条数据的中间产物 `spec` 被展平丢弃，但生成器可复现 ⇒ 可确定性重建为 tool_call 格式 |
| Phase 0 训练时长 | **约 21 分钟**（L40S）／**约 20 分钟**（A800），含环境下载调试共 **~1 小时** | 实测基线 308 steps / 2014 s 线性外推 |
| Phase 0 总费用 | **≈ ¥5~10**（两卡差异可忽略） | 固定开销（装环境/下权重/调试）占大头 |
| 最大风险 | **不是算力，是格式** | 见 §3.5：现有 1226 条**没有一条 tool_call**，不改造数据，训完也不会调工具 |

---

## 1. 事实基线（全部为本地实测，非文档声称）

### 1.1 当前文件夹的真实状态

| 产物 | 实测结果 | 能否作为 Agent 训练底座 |
| --- | --- | --- |
| `checkpoints/virtu_omni_10b_base.pt` | 578,839,296 params（0.58B），fp32，**仅 33 个 tensor** | ❌ 空壳（装不下 README 声称的 48 层结构） |
| `checkpoints/standardized_smelt_bundle/weights/standardized_weights.pt` | 1,276,874,193 params（1.28B），bf16，RNN 混合世界模型（`rnn`/`fusion`/`dec`/`target`） | ❌ 无标准 chat LM head，无可继承的指令跟随能力 |
| `checkpoints/code_llm/checkpoint_step_10.pt` | 19.4 MB，loss 7.09 | ❌ ≈随机初始水平 |
| `checkpoints/edge_qlora_adapter/adapter_model.pt` | **0 字节** | ❌ 从未真训过 |
| `scripts/run_train.py` | **仿真**：合成 batch + RAM<48GB 时降配到 2 层/hidden1024 + 跑 20 步 | ❌ 不可用于真实训练 |
| `virtu_omni/training/trainer.py` | 是真 PyTorch trainer（AdamW/梯度累积/裁剪/断点续训） | ⚠️ 代码可用，但喂的是假数据 |
| `damodel_cad_cam_tuning/train_cad_cam_l40s.py` | **真跑通过**：Qwen3-8B + LoRA，完整日志 | ✅ **本方案的基础** |
| `virtu_omni/engine/wish_cad_cam_engine.py` | 纯规则引擎（无 torch、无模型加载），字符串模板生成 VBA/NXOpen/AutoLISP | ⚠️ 是**待被 Agent 编排的对象**，不是模型 |
| `scripts/workbuddy_virtu_bridge.py` | `http.server` 实现的 OpenAI 兼容外壳，**完全忽略 `tools` 字段** | ⚠️ 服务端需改造（§5） |

**Agent 轨迹数据现状：0 条。** 全仓库对 `tool_call|function_call|observation` 的检索**零命中**；`data/processed/clean_code_corpus.jsonl` 仅 6 行 / 0 MB。

### 1.2 唯一可复用的真实训练基线

来源：`damodel_cad_cam_tuning/train_damodel_l40s_comprehensive.log`（真实运行日志）

```
Qwen3-8B + LoRA(r=16, 全 attn+MLP) on NVIDIA L40S 48GB
bf16 + gradient_checkpointing, per_device_bs=2 × grad_accum=4, max_len=2048
数据集 1226 条 × 2 epochs = 308 steps
train_runtime = 2014 s = 33.6 min   |   6.54 s/it   |   1.217 samples/s
total_flos = 1.679e17
```

数据实测：mean 4221 字符 / median 2512 / p90 10899 ⇒ **≈1.3K tokens/样本**（2048 截断再压低实际值）
⇒ 有效吞吐 **≈1,300~1,600 tok/s**（FLOPs 交叉验算 ≈80 TFLOPS ≈ L40S 稠密 BF16 的 44% MFU，自洽）

### 1.3 关键发现：现有数据可以被"零成本"改造成 tool_call 格式

`damodel_cad_cam_tuning/generate_comprehensive_wish_corpus.py` 的生成链路是：

```python
wish = f"我想要一个材质为{mat}的回转模具套筒，要求最大外径为{d_out}mm..."
spec = engine.parse_wish_intent(wish)          # ← 结构化参数（10 字段）
macro_code = engine.generate_solidworks_macro(spec)   # ← 展平成代码字符串
samples.append({"messages":[system, user, assistant]})  # ← spec 在此被丢弃
```

`parse_wish_intent()` 返回的 `spec` 结构（`virtu_omni/engine/wish_cad_cam_engine.py:85-95`）：

```python
{"wish", "material", "d_outer", "d_inner", "num_features",
 "fillet_r", "overall_len", "sweep_angle", "is_multiaxis", "is_die_mold"}
```

**结论**：`spec` 天然就是一份**合法的 function arguments**。重跑生成器、把 `spec` 保留下来包装成 `tool_calls`，即可产出**格式完全正确、参数完全正确**的工具调用数据 —— **不需要 LLM，不需要人工标注**。

> 这把原估算里"造数据 3~10 人天"压缩为 **0.5~1 人天**（写转换脚本 + 质量门禁）。

---

## 2. 硬件选型：L40S ¥4.50/h vs A800 ¥6.90/h

### 2.1 规格对照

| 项 | NVIDIA-L40S | NVIDIA-A800-SXM4-80GB |
| --- | --- | --- |
| 显存 | 48 GB | **80 GB** |
| BF16 稠密算力 | 181 TFLOPS | **312 TFLOPS** |
| CPU / 内存 | 21 核 / 124 GB | 15 核 / 250 GB |
| 系统盘 / 数据盘 | 40 GB / 50 GB | 40 GB / 50 GB |
| 支持 CUDA | 13.0 | 13.3 |
| 单价 | **¥4.50/h** | ¥6.90/h |

### 2.2 速度与内存

- 算力比 A800:L40S = 312/181 ≈ **1.72x**
- 显存比 80:48 = 1.67x ⇒ L40S 上 `per_device_bs=2`（seq2048）→ A800 上可开 `4`
- **实测折算**（以 Phase 0 的 2452 sample-passes 为例）

| 方案 | 训练墙钟 | 卡时 | 卡费 |
| --- | --- | --- | --- |
| L40S（实测直接复用） | **33.6 min** | 0.56 h | **¥2.5** |
| A800（1.6~1.8x 折算） | **19~21 min** | 0.34 h | **¥2.4** |

**Phase 0 两卡费用差 ≈ ¥0.1，可忽略。**

### 2.3 结论

| 阶段 | 选型 | 理由 |
| --- | --- | --- |
| **Phase 0（跑通全链路）** | **L40S ¥4.50/h** | ① 与实测基线**同构**，不需要任何外推，验收标准可以直接照抄已验证的那次；② 更便宜；③ 21 核 / 124GB 内存对 Phase 0 足够；④ 出问题调试成本低 |
| **Phase 1（扩量到 3 万条）** | L40S 或 A800 都行 | L40S：90,000 sample-passes ÷ 1.217 = **20.5 h，¥93**；A800：**12.5 h，¥86**。费用几乎相同，差的是墙钟 |
| **Phase 1'（换 Qwen3-14B / 32B-AWQ 底座）** | **必须 A800 80GB** | 14B LoRA bf16 权重 28GB + 激活，48GB 会 OOM |
| **Phase 2（闭环 RL）** | **8×A800** | 单卡 120~200 h；8 卡并行后 18~30 h |

### 2.4 云端操作注意事项（踩过的坑都在这）

1. **磁盘紧张**：系统盘仅 40 GB，PyTorch 容器镜像约 20 GB，**放不下**「镜像 + Qwen3-8B 权重 16GB + 数据集 + 合并后模型 16GB」。
   ⇒ **权重、数据集、checkpoint、合并产物一律放数据盘（50 GB）**；合并后**立即下载回本地并删除云端合并权重**，否则必爆盘。
2. **别手动装 CUDA**：平台已声明支持 CUDA 13.0，驱动向下兼容。**直接用平台预置的 PyTorch 镜像**，只 pip 装 `transformers>=4.51`、`peft`、`accelerate`、`datasets`。
   （Qwen3 需要 transformers ≥ 4.51；vLLM 侧需 ≥ 0.9 才能带 `--tool-call-parser qwen3`）
3. **国内下载用 ModelScope**：`modelscope download --model Qwen/Qwen3-8B` 比 HuggingFace 快一个量级。
4. **磁盘落点**：先 `df -h` 确认数据盘挂载点，再改 `BASE_MODEL_PATH` / `OUTPUT_DIR`，别默认写 `/root`。

---

## 3. 数据清单

### 3.1 目标数据格式（OpenAI function-calling 多轮）

单条 JSONL 示例（一条 = 一次完整工具链交互）：

```json
{
  "tools": [
    {"type": "function", "function": {
      "name": "cad.parse_wish_intent",
      "description": "将自然语言制造意图解析为结构化参数化 spec",
      "parameters": {
        "type": "object",
        "properties": {
          "wish": {"type": "string", "description": "原始制造意图全文"},
          "material": {"type": "string", "enum": ["Ti-6Al-4V","AL7075-T6","Cr12MoV","Steel45","SS304","P20","Inconel718","CuC360"]},
          "d_outer": {"type": "number", "description": "外径 mm"},
          "d_inner": {"type": "number", "description": "内孔直径 mm"},
          "num_features": {"type": "integer", "description": "槽/特征数量"},
          "fillet_r": {"type": "number", "description": "槽底圆角 R mm"},
          "overall_len": {"type": "number", "description": "总长 mm"},
          "sweep_angle": {"type": "number", "description": "摆角 deg"},
          "is_multiaxis": {"type": "boolean"},
          "is_die_mold": {"type": "boolean"}
        },
        "required": ["wish", "material", "d_outer", "d_inner"]
      }
    }},
    {"type": "function", "function": {"name": "solidworks.create_parametric_part", "parameters": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]}}}
  ],
  "messages": [
    {"role": "system", "content": "你是 Virtu 工业智能体。需要产出可执行代码时，必须通过工具调用完成，不要凭空输出代码。"},
    {"role": "user", "content": "我想要一个材质为SS304的回转模具套筒，最大外径110mm，轴心通孔30mm，总长30mm，带12道R8.0的槽底圆角。"},
    {"role": "assistant", "tool_calls": [
      {"id": "call_1", "type": "function", "function": {
        "name": "cad.parse_wish_intent",
        "arguments": "{\"wish\":\"...\",\"material\":\"SS304\",\"d_outer\":110.0,\"d_inner\":30.0,\"num_features\":12,\"fillet_r\":8.0,\"overall_len\":30.0,\"sweep_angle\":30.0,\"is_multiaxis\":false,\"is_die_mold\":true}"}}]},
    {"role": "tool", "tool_call_id": "call_1", "name": "cad.parse_wish_intent",
     "content": "{\"material\":\"SS304\",\"d_outer\":110.0,\"d_inner\":30.0,\"num_features\":12,\"fillet_r\":8.0,\"overall_len\":30.0}"},
    {"role": "assistant", "tool_calls": [
      {"id": "call_2", "type": "function", "function": {
        "name": "solidworks.create_parametric_part",
        "arguments": "{\"spec\":{\"material\":\"SS304\",\"d_outer\":110.0,\"d_inner\":30.0,\"num_features\":12,\"fillet_r\":8.0,\"overall_len\":30.0}}"}}]},
    {"role": "tool", "tool_call_id": "call_2", "name": "solidworks.create_parametric_part",
     "content": "Sub Main()\n    Set swEqnMgr = Part.GetEquationMgr\n    swEqnMgr.AddEquation 0, \"\"D_Outer\" = 110.0\"\nEnd Sub"},
    {"role": "assistant", "content": "已生成 SOLIDWORKS 2021 参数化驱动宏：外径 110.0mm、内孔 30.0mm、总长 30.0mm、12 道 R8.0 槽底圆角。"}
  ]
}
```

**loss 规则（写死在训练脚本里）**：
- `assistant` 段（**含 tool_calls 的 assistant 段**）→ 计 loss
- `system` / `user` / `tool` 段 → **不**计 loss（`-100`）
- `tool` 段是"环境回执"，不是模型的输出，训练时必须屏蔽（否则模型会学会伪造工具返回值）

### 3.2 工具清单（10 个）

| 工具名 | 作用 | 实现来源 | Phase 0 |
| --- | --- | --- | --- |
| `cad.parse_wish_intent` | 意图 → 结构化 spec | `WishCADCAMEngine.parse_wish_intent` | ✅ 必做 |
| `solidworks.create_parametric_part` | spec → VBA 宏 | `generate_solidworks_macro` | ✅ |
| `nx.create_nxopen_script` | spec → NXOpen Python | `generate_nx12_script` | ✅ |
| `autocad.create_autolisp` | spec → AutoLISP | `generate_autocad_lisp` | ✅ |
| `vericut.create_project_config` | spec → Vericut 配置 | `generate_vericut_config` | ✅ |
| `cimco.create_macro_b` | spec → FANUC Macro B | `generate_cimco_macro` | ✅ |
| `sscnc.create_setup_guide` | spec → SSCNC 装夹/对刀指南 | `generate_sscnc_setup_guide` | ✅ |
| `ontology.lookup_plugin` | 查询某软件某插件的能力 | `SOFTWARE_ONTOLOGY` | ✅（把 250 条百科问答转成 tool_call） |
| `cad.validate_spec` | 几何/工艺合理性校验 | 新增（规则即可） | ⬜ Phase 1 |
| `mcp.call_tool` | 通用 MCP 工具透传 | 新增（转发到 MCP server） | ⬜ Phase 1 |

> 全部 8 个 Phase 0 工具都能用**现有仓库代码**实现，**不需要写新后端**。`ontology.lookup_plugin` 把现有 250 条"插件百科问答"（无 spec）转成 `lookup_plugin` 工具调用，一鱼两吃。

### 3.3 数据生成流水线（3 个新脚本）

```
scripts/
├── build_tool_schema.py      # 从 SOFTWARE_ONTOLOGY + engine 导出 10 个 function schema → data/tools/tool_schema.json
├── convert_sft_to_toolcall.py# 重跑 generate_comprehensive_wish_corpus.py，捕获 spec → tool_call 格式
│                             #   输出 damodel_cad_cam_tuning/dataset/toolcall_sft_v1.jsonl
└── validate_toolcall_data.py # 质量门禁（§3.5），输出报告 + 丢弃不合格样本
```

**`convert_sft_to_toolcall.py` 的核心改造**（对 `generate_comprehensive_wish_corpus.py` 的最小侵入）：

```python
# 关键：把原本丢弃的 spec 接住，替换 assistant 的展平文本
spec = engine.parse_wish_intent(wish)
macro_code = engine.generate_solidworks_macro(spec)

messages = [
    {"role": "system", "content": SYSTEM_TOOL},
    {"role": "user",   "content": wish},
    {"role": "assistant", "tool_calls": [
        {"id": "call_1", "type": "function", "function": {
            "name": "cad.parse_wish_intent",
            "arguments": json.dumps(spec, ensure_ascii=False)}}]},
    {"role": "tool", "tool_call_id": "call_1", "name": "cad.parse_wish_intent",
     "content": json.dumps(spec_view, ensure_ascii=False)},   # 只回关键字段
    {"role": "assistant", "tool_calls": [
        {"id": "call_2", "type": "function", "function": {
            "name": "solidworks.create_parametric_part",
            "arguments": json.dumps({"spec": spec_view}, ensure_ascii=False)}}]},
    {"role": "tool", "tool_call_id": "call_2", "name": "solidworks.create_parametric_part",
     "content": macro_code},
    {"role": "assistant", "content": final_summary},   # 复用原 assistant 文本的前半段摘要
]
```

> `arguments` 必须是 **JSON 字符串**（不是对象），这是 OpenAI function-calling 的规范格式，Qwen 的 chat template 与 vLLM 都按此解析。

### 3.4 数据量与阶段划分

| 阶段 | 数据量 | 来源 | 训练墙钟（L40S） | 费用 |
| --- | --- | --- | --- | --- |
| **Phase 0** | **~1,226 条**（其中 ~976 条 wish 类带 spec，~250 条百科转 `lookup_plugin`） | 现有数据零成本转换 | **33.6 min**（实测基线） | **¥2.5** |
| Phase 1 | 30,000 条 | 参数网格扩增（材料 8 × 直径 8 × 长度 7 × 圆角 7 × 特征数 7 ≈ 25k 组合） + 句式模板 40 种 | **20.5 h** | **¥93** |
| Phase 2 | + 真实 MCP 工具链轨迹 | 环境 rollout 采集 | 另计 | 另计 |

**Phase 1 的关键洞察**：现有生成器是 `random.choice` 采样，参数空间远未覆盖。改成**笛卡尔积全量枚举**即可零成本扩到 2.5 万条，且每条都是合法的 tool_call 样本。句式多样性用 40 套模板拼装即可满足。

### 3.5 质量门禁（`validate_toolcall_data.py` 自动执行，6 条）

| # | 检查项 | 判据 | 不合格处置 |
| --- | --- | --- | --- |
| 1 | JSON 可解析 | `arguments` 是合法 JSON 且能反序列化成 dict | 丢弃 |
| 2 | 函数名存在 | 工具名 ∈ 工具清单 | 丢弃 |
| 3 | 参数必填齐全 | 满足该工具 JSON Schema 的 `required` | 丢弃 |
| 4 | 参数值域合法 | `d_inner < d_outer`；`material` ∈ enum；`num_features ∈ [1,100]` | 丢弃 |
| 5 | **与 spec 一致** | tool_call 的 arguments 与生成时捕获的 spec **逐字段相等** | 丢弃（防转换 bug） |
| 6 | 长度不超限 | 渲染后 tokens ≤ 4096 | 截断或丢弃 |

**门禁通过率要求 ≥ 98%**；低于此值说明转换脚本有 bug，**必须先修再开训**（避免用脏数据训 20 分钟后才发现）。

> 门禁第 5 条是防"假通过"的关键：肉眼无法察觉 `d_outer` 少传了一个字段，但模型会照着学。

---

## 4. 训练脚本改造

### 4.1 文件清单

| 文件 | 动作 | 说明 |
| --- | --- | --- |
| `scripts/train_tool_agent.py` | **新增** | 基于 `damodel_cad_cam_tuning/train_cad_cam_l40s.py` 改造，核心差异在数据加载与 loss mask |
| `scripts/run_tool_call_eval.py` | **新增** | 工具调用专项评测（§6） |
| `scripts/workbuddy_virtu_bridge.py` | **改造** | 接入模型 + 支持 `tools` / `tool_calls`（§5） |
| `damodel_cad_cam_tuning/train_cad_cam_l40s.py` | **保留不动** | 作为原始基线，便于对照回归 |

### 4.2 训练脚本七处改造

**① 数据加载：支持 `tools` + 多轮 `tool_calls`**

```python
def load_toolcall_dataset(path, tokenizer, max_length=4096):
    rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    dataset = []
    for r in rows:
        tools = r.get("tools") or []
        msgs = r["messages"]
        ids, labels = build_example(msgs, tools, tokenizer, max_length)
        if not ids:
            continue
        dataset.append({"input_ids": ids, "labels": labels, "attention_mask": [1]*len(ids)})
    return Dataset.from_list(dataset)
```

**② 逐轮 loss mask（最容易写错的地方）**

```python
def build_example(messages, tools, tokenizer, max_length=4096):
    ids, labels = [], []
    for i, m in enumerate(messages):
        text_end = tokenizer.apply_chat_template(
            messages[:i+1], tools=tools, tokenize=False, add_generation_prompt=False)
        text_start = (tokenizer.apply_chat_template(
            messages[:i], tools=tools, tokenize=False, add_generation_prompt=False)
            if i > 0 else "")
        s_ids = tokenizer.encode(text_start, add_special_tokens=False)
        e_ids = tokenizer.encode(text_end,   add_special_tokens=False)
        if not e_ids[:len(s_ids)] == s_ids:
            raise RuntimeError(f"模板非前缀对齐 @ msg {i}: {m['role']}")   # 别静默跳过
        seg = e_ids[len(s_ids):]
        ids.extend(seg)
        labels.extend(seg if m["role"] == "assistant" else [-100]*len(seg))
        if len(ids) > max_length:
            break
    return ids[:max_length], labels[:max_length]
```

> ⚠️ **必须先做一次"模板探针"**：用 `tokenizer.apply_chat_template(messages, tools=tools, tokenize=False)` 打印渲染结果，确认 Qwen3 模板真的输出了 `tools` 段和 `<tool_call>` 段。若模板不认 `tools`，退路是**手写 ChatML 模板**（把 tool schema 塞进 system 段，把 tool_calls 序列化成 `<tool_call>{json}</tool_call>` 文本），并在训练与推理两侧使用同一套序列化。

**③ 关闭 naive packing**：多轮 tool 格式若做 naive concat，跨样本的 attention 会串味。Phase 0 样本最长 ~4K，单卡够用 → **`group_by_length=False`、不 packing**。若 Phase 1 嫌慢，再上 `position_ids` 重置的 packing。

**④ LoRA 与超参**

```python
lora_config = LoraConfig(
    r=16, lora_alpha=32, lora_dropout=0.05, bias="none",
    target_modules=["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"],
    task_type=TaskType.CAUSAL_LM,
)
```

| 超参 | Phase 0（L40S 48GB） | Phase 1（L40S） | Phase 1'（A800 80GB / 14B 底座） |
| --- | --- | --- | --- |
| base model | Qwen3-8B | Qwen3-8B | Qwen3-14B |
| max_length | 4096 | 4096 | 4096 |
| per_device_train_batch_size | 2 | 4 | 1 |
| gradient_accumulation_steps | 4 | 2 | 8 |
| 有效 batch | 8 | 8 | 8 |
| learning_rate | 1e-4 | 1e-4 | 1e-4 |
| num_train_epochs | 2 | 3 | 3 |
| warmup_steps | 15 | 50 | 100 |
| gradient_checkpointing | True | True | True |
| bf16 | True | True | True |
| save_steps | 50 | 100 | 100 |
| save_total_limit | 2 | 3 | 3 |
| 预估 step 数 | 308 | ≈11,250 | ≈11,250 |
| 预估墙钟 | **33.6 min** | **20.5 h** | ≈25 h |

> Phase 0 有效 batch 沿用原脚本的 2×4=8，**只为与已验证基线严格同构**；Phase 1 提到 4×2=8 是因为 48GB 在 4096 长度下装得下。

**⑤ 数据集划分**：把 36 条盲测集（`wish_parametric_blind_test.jsonl`）**排除在训练集外**，作为 held-out。同时从训练集随机切 5% 作 val（`eval_strategy="steps"`, `eval_steps=50`）。

**⑥ 断点续训**：`save_steps=50` + `resume_from_checkpoint=True`。Phase 1 跑 20 小时，断点续训是必需品，不是可选项。

**⑦ 落盘产物**

```
output_checkpoints/tool_agent_lora_final/
├── adapter_model.safetensors        # LoRA 权重
├── adapter_config.json
├── tokenizer.json / tokenizer_config.json
├── training_receipt.json            # 沿用原脚本的格式 + 追加 tool 指标
└── tools_schema.json                # ★ 推理端要用，必须随 adapter 一起落盘
```

### 4.3 训练中监控

```bash
tail -f train.log | grep -E "loss|it/s"
nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,power.draw --format=csv -l 5
```

**异常判据**：loss 出现 NaN / 连续 3 次上升 / `grad_norm > 10` ⇒ 立即停，调 lr（1e-4 → 5e-5）重启。现有 `virtu_omni/training/monitor.py` 有类似阈值逻辑，但**新训练脚本不依赖它**（避免引入仿真代码路径）。

---

## 5. 服务端改造：把模型接进 WorkBuddy

### 5.1 现状问题

`scripts/workbuddy_virtu_bridge.py` 的 `do_POST`：
- ✅ 解析 `messages`（且已修过 list-of-blocks 兼容）
- ❌ **完全忽略 `data["tools"]`**
- ❌ 不返回 `tool_calls`，只返回纯文本
- ❌ 回复来自 `WishCADCAMEngine` 的**规则模板**，不是模型
- ❌ 不接受 `role="tool"` 的回执继续生成

### 5.2 改造方案

```python
# 1) 读取工具定义
tools = data.get("tools", [])

# 2) 调用本地 vLLM（OpenAI 兼容端点）
resp = requests.post(
    VLLM_BASE + "/v1/chat/completions",
    json={"model": MODEL_ID, "messages": messages, "tools": tools,
          "tool_choice": data.get("tool_choice", "auto")},
    timeout=120).json()

msg = resp["choices"][0]["message"]
finish_reason = resp["choices"][0].get("finish_reason", "stop")

# 3) 原样透传 tool_calls
out = {"id": chat_id, "object": "chat.completion", "created": int(time.time()),
       "model": MODEL_ID,
       "choices": [{"index": 0, "finish_reason": finish_reason, "message": {
           "role": "assistant",
           "content": msg.get("content"),
           "tool_calls": msg.get("tool_calls", []),      # ★ 新增
       }}],
       "usage": resp.get("usage", {})}
```

**配套规则**：
- `finish_reason == "tool_calls"` ⇒ 客户端应执行工具并回传 `role="tool"` 消息，再次请求 ⇒ **服务端必须支持带 tool 回执的续写**（现有代码会直接把 `role="tool"` 丢掉）。
- `tools` 为空 ⇒ 退化为普通对话（保持向后兼容）。

### 5.3 vLLM 起服务（带工具解析）

```bash
vllm serve /data/models/Qwen3-8B \
  --served-model-name virtu-tool-agent \
  --enable-auto-tool-choice \
  --tool-call-parser qwen3 \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.85 \
  --port 8000
```

若用 `transformers` 直接推理（省去 vLLM 依赖），则手工解析模型输出的 `<tool_call>{...}</tool_call>` 文本为结构化 `tool_calls` —— 但**这条路要额外写解析器且更脆**，Phase 0 建议直接上 vLLM。

---

## 6. 验收标准

### 6.1 硬指标（Phase 0 必须全部达标）

| # | 指标 | 阈值 | 判定方法 |
| --- | --- | --- | --- |
| 1 | tool_call JSON 可解析率 | **≥ 98%** | 生成结果正则提取 `<tool_call>` → `json.loads` |
| 2 | 首轮函数名正确率 | **≥ 90%** | 与 gold 函数名精确匹配 |
| 3 | 参数数值完全一致率 | **≥ 80%** | arguments 与 gold spec **逐字段**相等（不是模糊匹配） |
| 4 | 多轮链路完成率（≥2 次工具调用） | **≥ 70%** | 完整跑完 parse→generate→总结 |
| 5 | 最终答复含关键数值/代码 | **≥ 85%** | 复用 `run_blind_test_evaluator.py` 的 `evaluate_response()` 打分，**score ≥ 80 视为通过** |
| 6 | 幻觉函数名率 | **= 0** | 不存在的工具名出现次数必须为 0（这条一票否决） |
| 7 | 训练无损回归 | val loss 下降且末轮 loss < 0.3 | 训练日志 + `eval` 输出 |

> 指标 6 是**一票否决项**：模型一旦开始编造不存在的工具名，接到 MCP 工具链上会直接产生非法请求。

### 6.2 评测集

- 复用 `damodel_cad_cam_tuning/dataset/wish_parametric_blind_test.jsonl`（36 条，**held-out，不进训练**）
- 新增 `data/benchmark/tool_call_eval_set.jsonl`：≥ 60 条，含 **≥ 15 条拒答/澄清样本**（参数不足时要求模型澄清而不是瞎编参数）—— 这类样本训练集里也必须按 10% 比例注入
- 新增 `data/benchmark/mcp_chain_eval_set.jsonl`：≥ 20 条多跳链（查本体 → 解析意图 → 生成代码 → 校验）

### 6.3 判定脚本

`scripts/run_tool_call_eval.py` 输出：

```
[1/7] JSON 可解析率        : 98.6%  (PASS ≥98%)
[2/7] 函数名正确率          : 93.1%  (PASS ≥90%)
[3/7] 参数完全一致率        : 84.5%  (PASS ≥80%)
[4/7] 多轮链路完成率        : 72.2%  (PASS ≥70%)
[5/7] 答复质量(盲测score≥80): 87.4%  (PASS ≥85%)
[6/7] 幻觉函数名            : 0 次   (PASS =0)
[7/7] val loss              : 0.214  (PASS <0.3)
ALL PASS
```

**同时落盘** `benchmarks/tool_call_eval_report.md` + `benchmarks/tool_call_eval_results.json`，格式对齐现有 `cad_cam_blind_test_report.md` 的约定。

---

## 7. 部署与执行步骤（时间表）

### 7.1 人工排期（总 3 人天）

| 天 | 任务 | 产出 | 卡时 |
| --- | --- | --- | --- |
| **D1 上午** | 写 `build_tool_schema.py` + `convert_sft_to_toolcall.py` | `data/tools/tool_schema.json`、`toolcall_sft_v1.jsonl` | 0 |
| **D1 下午** | 写 `validate_toolcall_data.py`，跑到门禁 ≥98% | 门禁报告 | 0 |
| **D1 晚上** | 写 `train_tool_agent.py`（含模板探针 + loss mask 自测） | 训练脚本 + 本地 CPU 冒烟通过 | 0 |
| **D2 上午** | 租 L40S，装环境，下载 Qwen3-8B | 环境就绪 | **0.5 h** |
| **D2 上午** | Phase 0 训练（33.6 min） | LoRA adapter + receipt | **0.6 h** |
| **D2 下午** | 起 vLLM + 改造 bridge + 跑 `run_tool_call_eval.py` | 验收报告 | **0.5 h** |
| **D2 下午** | 按验收结果修 1~2 轮（重训 33 min） | 达标报告 | **0.6 h** |
| **D3** | 扩量到 3 万条 + Phase 1 训练（20.5 h，可夜间跑） | 30k 数据 + 正式 adapter | **21 h** |

**Phase 0 卡时合计 ≈ 2.2 h ≈ ¥10**；Phase 1 ≈ ¥93。

### 7.2 云端执行步骤（逐条可复制）

```bash
# ── Step 1  环境（用平台预置 PyTorch 镜像，别自己装 CUDA）
pip install -U "transformers>=4.51" "peft>=0.14" "accelerate>=0.34" "datasets>=3.0" modelscope
python -c "import torch;print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"

# ── Step 2  下载底座（放数据盘！）
df -h                       # 先确认数据盘挂载点，设为 $DATA
modelscope download --model Qwen/Qwen3-8B --local_dir $DATA/models/Qwen3-8B

# ── Step 3  上传脚本与数据
#   本地 → 云端，沿用 scripts/deploy_comprehensive_training.py 的 paramiko 模式
#   ✅ 该脚本及全部远程脚本已改为读 DAMODEL_* 环境变量（见 §8 R1），先设好环境变量再跑

# ── Step 4  模板探针（务必先跑，确认 tools 能被渲染）
python scripts/probe_chat_template.py

# ── Step 5  数据门禁（云端或本地均可，本地更快）
python scripts/validate_toolcall_data.py --in <dataset.jsonl> --report <report.md>

# ── Step 6  训练
cd $DATA/work && nohup python3 -u scripts/train_tool_agent.py > train.log 2>&1 &
tail -f train.log

# ── Step 7  合并与下载（★ 合并完立刻下本地，删云端，否则爆盘）
python scripts/merge_lora.py --base $DATA/models/Qwen3-8B --adapter <adapter_dir> --out $DATA/merged
# 本地：scp / paramiko 拉回 D:\Virtu模型\checkpoints\tool_agent_merged\
# 确认本地 sha256 一致后：rm -rf $DATA/merged

# ── Step 8  起服务
vllm serve $DATA/models/Qwen3-8B --enable-auto-tool-choice --tool-call-parser qwen3 \
         --served-model-name virtu-tool-agent --max-model-len 8192 --port 8000

# ── Step 9  验收
python scripts/run_tool_call_eval.py --base $DATA/models/Qwen3-8B --adapter <adapter_dir>
```

### 7.3 回滚

- 训练产物全部落在独立 `output_checkpoints/tool_agent_lora_final/`，**不动**现有 `cad_cam_six_software_lora`
- bridge 改造走**新增分支**（`tools` 非空才走模型路径），原规则引擎路径保留 ⇒ 改坏了直接不传 `tools` 即回退
- 训练中断：`resume_from_checkpoint=True`，从最近的 `checkpoint-50/100` 续跑

---

## 8. 风险清单

| # | 风险 | 等级 | 处置 |
| --- | --- | --- | --- |
| **R1** | **云端 root 密码明文硬编码在 17 个脚本中，且已进入 git 历史（提交 `b7a62d5`、`1f23d54`）** | 🔴 高 | ✅ **工作区已全部清理**（2026-10-29）：17 个文件改为读 `DAMODEL_HOST/PORT/USER/PASS` 环境变量，缺 `DAMODEL_PASS` 时直接报错退出；语法已全量校验。**但密码已进入 git 历史，改历史无效 —— 必须到 DAMODEL 控制台轮换该密码**，并把新密码写入本机环境变量 |
| R2 | Qwen3 chat template 不认 `tools` 参数 | 🟡 中 | §4.2② 已给探针脚本；退路是手写 ChatML 模板并训练/推理两侧共用同一序列化 |
| R3 | 40GB 系统盘放不下镜像+权重+合并产物 | 🟡 中 | §2.4①：全放数据盘，合并后立刻下本地并删除云端 |
| R4 | tool 段被计入 loss，模型学会伪造工具返回值 | 🟡 中 | §3.1 的 loss 规则；训练后用指标 4（多轮链路完成率）反查 |
| R5 | 1226 条转换后**样本量太少导致过拟合**（1226 条 × 2 epoch 在 8B 上是重度过拟合） | 🟡 中 | Phase 0 本来就只为跑通链路；**Phase 1 必须扩到 3 万条**。Phase 0 指标若参数量达到 100% 但 val loss 抖，说明是记忆不是泛化，以盲测集为准 |
| R6 | 数据转换 bug 导致参数错位（肉眼不可见） | 🟡 中 | §3.5 门禁第 5 条：arguments 必须与生成时捕获的 spec **逐字段相等** |
| R7 | 云端实例被回收导致训练中断 | 🟢 低 | 断点续训 + 定期 `save_steps`；选支持数据盘持久化的机型 |
| R8 | Phase 1 训练 20 小时期间无人值守，异常不发现 | 🟢 低 | 监控脚本 + 夜间跑；`monitor_alerts.yaml` 的阈值逻辑可参考 |

---

## 9. 成本汇总

| 项 | 卡时 | 费用 |
| --- | --- | --- |
| Phase 0 训练（L40S） | 0.6 h | ¥2.7 |
| Phase 0 环境+下载+调试 | 0.8 h | ¥3.6 |
| Phase 0 验收（vLLM 起服务 + 评测） | 0.5 h | ¥2.3 |
| Phase 0 返工 1~2 轮 | 1.2 h | ¥5.4 |
| **Phase 0 小计** | **≈ 3.1 h** | **≈ ¥14** |
| Phase 1 扩量训练（L40S 20.5h / A800 12.5h） | 12.5~20.5 h | ¥86~93 |
| **Phase 0+1 总计** | **≈ 16~24 h** | **≈ ¥100~107** |

对比原估算（3~10 人天造数据 + ¥150~310），本方案因为**复用现有生成器的 spec**，把数据成本压到了 0.5~1 人天。

---

## 10. 立即可执行 Checklist

```
[ ] 1. 【已做工作区清理】★ 仍需人工完成：到 DAMODEL 控制台轮换 root 密码（已泄漏于 git 历史），
[ ]    然后 $env:DAMODEL_PASS = "<新密码>"，再跑任何 scripts/ 下的远程脚本
[ ] 2. 写 scripts/build_tool_schema.py，导出 10 个 function schema
[ ] 3. 写 scripts/convert_sft_to_toolcall.py，产出 toolcall_sft_v1.jsonl
[ ] 4. 写 scripts/validate_toolcall_data.py，门禁 ≥98% 才放行
[ ] 5. 写 scripts/probe_chat_template.py，确认 Qwen3 模板的 tools 渲染
[ ] 6. 写 scripts/train_tool_agent.py（loss mask 自测：断言 tool 段 label 全为 -100）
[ ] 7. 本地 CPU 冒烟：3 条样本跑通 forward + loss mask 断言
[ ] 8. 租 L40S ¥4.50/h，pip 环境 + modelscope 下 Qwen3-8B
[ ] 9. Phase 0 训练 33.6 min，产出 adapter
[ ] 10. 合并 LoRA → 下本地 → 删云端合并产物
[ ] 11. 起 vLLM（--enable-auto-tool-choice --tool-call-parser qwen3）
[ ] 12. 改造 workbuddy_virtu_bridge.py 支持 tools/tool_calls/tool 回执
[ ] 13. 跑 scripts/run_tool_call_eval.py，7 项指标全 PASS
[ ] 14. Phase 1：参数网格扩到 3 万条 + 夜间训练
```

---

## 附录 A：数据转换的"零成本"依据

```python
# virtu_omni/engine/wish_cad_cam_engine.py:85-95
return {
    "wish": wish_text,          # str
    "material": material,       # str, 8 种 enum
    "d_outer": d_outer,         # float
    "d_inner": d_inner,         # float
    "num_features": num_features,  # int
    "fillet_r": fillet_r,       # float
    "overall_len": overall_len, # float
    "sweep_angle": sweep_angle, # float
    "is_multiaxis": is_multiaxis,   # bool
    "is_die_mold": is_die_mold,     # bool
}
```

这 10 个字段 **1:1 映射** 为 `cad.parse_wish_intent` 的参数；其中 `wish/material/d_outer/d_inner/num_features/fillet_r/overall_len` 8 个进入最终 tool_call 的 arguments，`sweep_angle/is_multiaxis/is_die_mold` 3 个作为**中间 spec 字段**（保留在 tool 返回里，但不要求模型输出）—— 避免让模型生成无法验证的字段。

## 附录 B：现有 1226 条的构成（用于推导 Phase 1 扩量上限）

| 来源 | 条数 | 结构化程度 | 转换方式 |
| --- | --- | --- | --- |
| Part 1 插件百科问答 | ~250 | 无 spec（纯知识） | → `ontology.lookup_plugin` 单次 tool_call |
| Part 2 SOLIDWORKS wish | 150 | 有 spec | → parse + generate 双调用 |
| Part 3 NX wish | 150 | 有 spec | 同上（`nx.*`） |
| Part 4 AutoCAD wish | 150 | 有 spec | 同上（`autocad.*`） |
| Part 5 Vericut wish | 150 | 有 spec | 同上（`vericut.*`） |
| Part 6 CIMCO wish | 150 | 有 spec | 同上（`cimco.*`） |
| Part 7 SSCNC wish | 150 | 有 spec | 同上（`sscnc.*`） |
| Part 8 跨工具链综合 | ~126 | 有 spec | 多工具串联 |

参数空间：材料 8 × 外径 8 × 内径(比例) × 长度 7 × 圆角 7 × 特征数 7 ⇒ **理论组合 > 20 万**，现有 1226 条只采样了约 0.6%。
⇒ **Phase 1 扩量不需要新数据源，只需要把 `random.choice` 换成 `itertools.product` 全量枚举 + 句式模板拼装。**
