# Virtu v2「全部 90 分」训练—评测归档

> 生成时间：2026-11-03
> 状态：**训练完成、评测完成；目标（各维 ≥90）未达成**
> 诚实结论：v2 是一次「通用平衡数据再 SFT」，不是计划中的「弱点定向精标再 SFT」，因此未达标且出现维度互有涨落。

---

## 1. 目标与策略回顾

- 用户目标：「制定全部 90 分的云端训练计划，要质量不要数量，成本压到最低」。
- 既定策略：本地免费做弱点定向 curated 数据（~3000 精标）→ 云端一次短 QLoRA 续训 → 本地合并/量化/注册/复评。
- **实际执行偏差**：云端启动前，本地已有的 `data/sft/virtu_capability_sft_v6.jsonl`（4233 条通用平衡数据）被直接用作训练集，**未做弱点定向 curated 精标**。这是 v2 未达标的核心根因。

## 2. 训练配置与成本

| 项 | 值 |
|---|---|
| 云端实例 | DamoModel `cn-north-b.ssh.damodel.com:39473`，Tesla V100-SXM2-32GB |
| 基座 | 云端本地 `/root/public-storage/model/Qwen/Qwen3-8B`（免下载）|
| 初始化 | `virtu_boundary_sft_merged`（上一轮 SFT 权重，续训而非从基座重来）|
| 方法 | QLoRA 4-bit NF4 + LoRA r=32, α=64, dropout=0.05 |
| 超参 | lr 1.5e-4, cosine, warmup 5%, epochs 2, bs 4 / accum 4 |
| 数据 | `virtu_capability_sft_v6.jsonl` 4233 条（通用平衡，**非弱点定向**）|
| 时长 | 6397s ≈ 1h46m，504 步，最终 loss 0.1062 |
| 单价 | V100 抢占/按量，约 ¥30–100/次 |
| **总成本** | **仅云端训练 ≈ ¥30–100；数据/合并/量化/评测本地 ¥0** |

## 3. 产物链路（自动闭环，exit 0）

1. 云端训练 → adapter `virtu_v2_all90/`（349MB safetensors + receipt）
2. SFTP 拉回 → `checkpoints/virtu_v2_all90/`
3. `merge_numpy.py` → `virtu_v2_all90_merged/`（5 分片，数值校验 12/12 PASS）
4. `hf_to_gguf_numpy.py` Q4_0 → `virtu-v2-all90-q4_0.gguf`（4.61GB，self-test ALL PASS）
5. `ollama create virtu-v2-all90` → 注册成功
6. 评测臂 `virtu-v2-all90` 写入 `arms.json`

## 4. 评测结果

### 4.1 v2 单臂 7 文本维 vs 90 目标线（gate 检查）

| 维度 | v2 得分 | 达标(≥90)? |
|---|---:|---|
| 推理逻辑 | 83.34 | ❌ |
| 指令遵循 | 81.95 | ❌ |
| 内容生成 | 77.66 | ❌ |
| 工具编排 | 73.33 | ❌ |
| 泛化适配 | 63.13 | ❌ |
| 边界处理 | 62.45 | ❌ |
| 知识覆盖 | 61.61 | ❌ |
| **加权 overall** | **72.76** | ❌ |

→ **7 维无一达标**，overall 72.76，距 90 差 17.2。

### 4.2 v2 vs 历史基线（7 维交集，注意臂不一致）

> ⚠️ 可比性警告：基线 `_eval_full4` 走 **bridge 臂**（http_openai，model_id `virtu-cad-cam-10b`，且 note 标明其 served_model 归属需核对）；v2 走 **ollama_native 臂**。两臂请求处理/开销不同（基线延迟均值 21.5s vs v2 7.7s），**此表仅作趋势参考，非严格同臂对照**。严格同臂基线 `qwen3:8b` 正在补跑（`_eval_v2_base`）。

| 维度 | 基线(bridge) | v2(ollama) | Δ（参考）|
|---|---:|---:|---:|
| boundary | 53.45 | 62.45 | +9.00 |
| reasoning | 74.71 | 83.34 | +8.63 |
| generation | 62.77 | 77.66 | +14.89 |
| knowledge | 73.78 | 61.61 | −12.17 |
| instruction | 86.59 | 81.95 | −4.64 |
| generalization | 67.87 | 63.13 | −4.74 |
| toolcall | 75.55 | 73.33 | −2.22 |
| overall | 71.93 | 72.76 | +0.83 |

→ 趋势：boundary / reasoning / generation 涨；knowledge / instruction / generalization / toolcall 跌。**典型「通用 SFT 稀释专项能力 + 注入通用能力」互有涨落**，overall 几乎不动。

## 5. 根因分析

1. **数据没对准弱点**：计划要求弱点定向 curated（G 代码/公差配合/刀具补偿/车铣/AutoCAD/螺栓圆等高频错项），实际用了通用平衡集 → 没有针对性地把边界/知识/工具等弱项拉到 90。
2. **续训被通用数据稀释**：v2 初始化自上一轮 boundary SFT，再喂通用数据 2 epoch，边界专项增益被部分冲淡（boundary 较上轮 SFT 的 66.56 还略降）。
3. **「全部 90」是激进目标**：72→90 跨 18 分，单次通用 LoRA 不可能齐达；原计划的 2 次迭代也只是下限估计。

## 6. 下一步（要真正逼近 90）

1. **弱点定向 curated 数据**（本地 ¥0）：围绕 `results.json` 的 `weakest_tags` / `top_failed_criteria`（limits-fits, rule-application, mill, lathe, gcode, drilling, autocad, cutting-parameter, vf_value, rpm_value, JSON 格式…）生成高质量三元组，每维 200–450 条，合计 ~3000 精标。
2. **反遗忘 replay 混合**：混入 30–40% 通用指令/推理/知识样本，防 reasoning/instruction 重演回退。
3. **严格同臂对照**：`qwen3:8b` 已用 ollama_native 同臂补跑（`_eval_v2_base`），待出数后重算 v2 净增益。
4. 达标判定：各维 ≥90 且 overall ≥90 → 收尾写 `DEPLOYED.flag`；未达则只补未达标维度 curated 数据，再发起**一次**短云训（N=2 上限）。

## 7. 遗留项（非阻塞）

- **多模态**：v2 是纯文本 Qwen3-8B（无原生视觉），该维不计入「全部 90 文本目标」；baseline 的 88.33 来自 bridge 独立视觉后端（非 SFT 模型本身能力）。
- **bridge 视觉后端**：此前确认挂起（3 例 hard 超时），需修复/重载才能补 multimodal 口径。
- **arm 可比性**：历史基线为 bridge 臂，与 v2 ollama_native 不可直接比，以 `_eval_v2_base`（同臂 qwen3:8b）为准。
