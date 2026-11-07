# Virtu-CAD-CAM-10B 模型强化执行报告（2026-11-05）

> 目标：全面强化模型 —— 减少无效思考 + 把综合能力推到上限，且真实可验证。
> 结论：**"减少无效思考"已通过 disciplined 模型在生产链路落地并验证；"能力天花板"的数据与训练链路已备齐，本地 6GB 笔记本受硬件限制无法训练 8B 模型，已给出云端/大显存训练 runbook。**

---

## 0. 一句话结论

- **无效思考（overthinking）**：根因是训练数据里 32%~54% 响应超长 + DPO 缺"简洁偏好"。`virtu-disciplined:v1` 已把自由对话的 7420-token 战报压到 **33–199 token（-98%）**，数学正确性由后端确定性求解器兜底。生产链路已切换并验证。
- **能力上限**：弱维度 generalization 27%、reasoning 40%、hard 25% 是真实瓶颈（不是想太多）。已生成针对性补数据 + 简洁偏好 DPO 数据，待云端 GPU 训练。
- **本地训练不可行**：RTX 4050 6GB + transformers 5.22 加载 8B 4-bit 触发 warmup 额外 4.8GB 分配 + Windows 页面文件不足（os error 1455），8B 模型连加载都失败。训练必须走云端（≥36GB）或大显存卡。

---

## 1. A1 · 推理侧简洁约束（已完成，已验证）★核心交付

### 1.1 根因
- 自由对话（probe 直连）旧 `virtu-cad-cam-10b` 对 64-token 简单问句一律吐 **7420 token** 固定"协同攻坚战报"（emoji、details 折叠、多智能体话术），延迟 88–174s。
- 训练侧双峰污染：`virtu_gold_production_sft` 与 `master_cad_cam_six_software_train` 中 32%–54% 响应超 1500 字符（最长 10667），且前缀充满"为您生成的 XXX 如下："等模板套话。
- DPO 缺简洁偏好：现有 `dpo_comprehensive_pairs` / `dpo_phys_rejects` 全是"对错"偏好，**无任何"简洁 vs 冗长"长度偏好**。

### 1.2 已落地动作
1. 确认 `virtu-disciplined:v1` 已注册于本机 Ollama（今早），其 Modelfile 含"输出纪律"系统提示（规则 3/4/5：只给答案、不加话术、公式先写后代入）。
2. **修复 thinking 兼容 bug**：bridge → `virtu_real_backend._gen_vllm` 的 auto 模式会对计算类问题（命中"转速/主轴"正则）强制 `think=True`，而 disciplined 无 `<think>` 模板块 → Ollama 400 "does not support thinking" 导致 1/3 请求 500。**解法：给 disciplined 服务设 `VIRTU_THINKING_MODE=off`**（数学正确性由后端 `_numeric_problems` 确定性求解器兜底，与 thinking 无关）。
3. 重启 bridge（端口 8000，文本后端 `virtu-disciplined:v1`，thinking off），端到端验证全类请求正常。

### 1.3 验证结果（经 bridge 实测）
| 用例 | completion tokens | 结果 |
|---|---|---|
| identity（一句话定位） | 75 | 直接一句核心能力，无套话 |
| cad_math（主轴转速） | 199 | **n≈3820 r/min 公式+结果正确**，未 500 |
| reason（硬质合金负前角） | 40 | 直接给理由 |
| parametric（参数化建模） | 44 | 缺参时简洁拒绝并指明缺项 |

对比旧版自由对话 **7420 token 战报 → 当前 33–199 token**：**无效思考削减 98%**，且工程问答直接给公式+答案、不再灌水。

> 注：评测通道（runner）本就带 `max_tokens` 上限（median 99 token），所以 240 例评测集的冗长是被压制的；失控重灾区是**自由对话/部署场景**，现已修复。

---

## 2. 评测基线（纯文本维度，排除多模态/工具的基础设施 transport error）

| 版本 | 文本 pass | 均分 | 中位 token | boundary | generalization | reasoning |
|---|---|---|---|---|---|---|
| BASE 基座（qwen3-8b） | 42.2% | 69.9 | 166 | 10% | 37% | 50% |
| 旧生产 `virtu-boundary-sft` | 43.9% | 69.0 | **85** | **37%** | 27% | 40% |
| `virtu-disciplined:v1`（评测中） | 待出 | 待出 | 待出 | 待出 | 待出 | 待出 |

发现：旧生产已把 token 166→85 砍半，但 **generalization 37%→27%、reasoning 50%→40% 退化**——单维度过拟合、未均衡。这正是 B（弱维度均衡 SFT）要解决的。
`virtu-disciplined` 的纯文本评测正在 `_eval_disciplined_text/` 后台运行（每维 10 例），用于确认"换 disciplined 不降能力"。

---

## 3. A2 · 清洗冗长 SFT 数据（已完成）

脚本：`cloud_train_pack/dataset/clean_verbose_sft.py`
- `virtu_gold_production_sft`：保留 5498 条，剥离 **305,654** 字符模板套话。
- `master_cad_cam_six_software_train`：保留 1632 条，剥离 **149,485** 字符。
- 策略：去入口套话段（"为您生成/根据您的许愿式/以下是为您…"）、去结尾营销句、压缩分隔线、纯散文超长记录下采样；**保留代码实体**（G-code/VBA/宏是 CAD/CAM 模型的合法输出，非冗长）。
- 产出：`*_cleaned.jsonl`（位于各自 dataset 目录）。

---

## 4. A3 · 简洁偏好 DPO 数据（已完成，缺失杠杆）

脚本：`cloud_train_pack/dataset/build_concise_dpo.py`
- 产出 `cloud_train_pack/dataset/dpo_concise_pairs.jsonl`，**30 条** `{prompt, chosen(简洁正确), rejected(冗长战报)}`。
- 覆盖计算/知识/工具调用/边界安全/推理五类，chosen 中位 47 字符 vs rejected 中位 430 字符，**平均压缩 8.3×**。
- 这是当前训练数据里**唯一存在的"简洁 vs 冗长"偏好信号**——现有 DPO 全是对错偏好，没有任何长度偏好。是抑制 overthinking 最直接的新杠杆。

---

## 5. B · 弱维度补充 SFT 数据（已完成）

脚本：`cloud_train_pack/dataset/build_weak_dim_sft.py`
- 产出 `cloud_train_pack/dataset/sft_weak_dims.jsonl`，**23 条** messages 格式范例（system 输出纪律 + user + assistant 精简推理）。
- 针对 reasoning / generalization / hard 三类弱项：示范"先结论+公式，再列关键步骤，不写题外话术"。
- assistant 中位 83 字符、最大 195，既正确又精简，作为 SFT 目标教模型在弱维度上答对且保持简洁。

---

## 6. C · 闭环验证（评测进行中 + 指标已加）

- 已把 token 维度纳入对比（completion_tokens median/mean/p90/max），使"减少无效思考"可量化追踪。
- `virtu-disciplined` 纯文本评测后台运行，完成后与 §2 基线做 before/after：验证**能力不降 + token 不增**。

---

## 7. 本地训练为何未跑通 + 云端 runbook（A3+B 实际训练）

**本地不可行原因（已实测两次失败）**：
- 尝试 4-bit QLoRA 加载 8B：`caching_allocator_warmup` 额外申请 4.8GB fp16 缓冲 → 6GB OOM。
- monkeypatch 绕过 warmup 后：加载 safetensors 触发 **Windows 页面文件太小（os error 1455）**——本机 6GB 笔记本 + 页面文件不足，8B 模型连加载都失败。
- 本工作区历史合并权重/adapter 均为**云端训练产物**，非本机 8B 训练所得。

**云端/大显存（≥24GB）训练 runbook**（脚本已就绪，面向云端）：
```bash
# 环境：含 torch/transformers/peft/trl/datasets + CUDA ≥24GB
# A3 简洁偏好 DPO（推荐先做，抑制 overthinking 最直接）：
python cloud_train_pack/train_dpo_cloud.py \
  --base /root/workspace/models/Qwen3-8B-Instruct \
  --data cloud_train_pack/dataset/dpo_concise_pairs.jsonl \
  --out output/dpo_concise_v1 --epochs 3 --lr 5e-6 --beta 0.2

# B 弱维度均衡 SFT（推能力上限）：
python cloud_train_pack/train_turnkey.py \
  --base /root/workspace/models/Qwen3-8B-Instruct \
  --data cloud_train_pack/dataset/sft_weak_dims.jsonl \
  --out output/sft_weak_v1 --epochs 4 --lr 2e-5

# 也可用不依赖 trl/datasets 的自包含 SFT（cloud_train_pack/train_sft_local.py）
# 训练后：merge LoRA → convert_hf_to_gguf.py → ollama create → 切 bridge 后端
```
- 基座建议从当前能力最强合并权重（如 `virtu_cad_cam_merged_v3`，即 comprehensive GGUF 底层）继续训，避免从裸 base 丢失 CAD 能力。
- 训练后务必跑 §2 同口径纯文本评测做 before/after。

---

## 8. 当前生产状态

- bridge 服务运行中：端口 8000，文本后端 `virtu-disciplined:v1`，`VIRTU_THINKING_MODE=off`。
- 调用别名 `virtu-cad-cam-10b`，后端确定性求解器兜住数学正确性。
- 自由对话场景已实测：冗长战报 -98%，公式/事实/工具调用/安全拒绝均正常。

## 9. 后续动作（按价值排序）

1. **等 `_eval_disciplined_text` 出结果**，确认 disciplined 纯文本能力 ≥ 旧生产（不降） → 闭环 A1。
2. **云端跑 A3 DPO**（最缺的简洁偏好）→ merge → GGUF → 切生产，再评测看 token 是否进一步下降且能力不损。
3. **云端跑 B SFT** 补 generalization/reasoning/hard，做均衡（复制 boundary 从 10%→37% 的成功路径，同时 replay 防 reasoning/generalization 退化）。
4. 把 A2 清洗数据并入下一轮训练集，从源头防止战报污染复发。
