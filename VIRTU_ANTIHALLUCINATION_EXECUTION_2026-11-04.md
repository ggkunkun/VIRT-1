# Virtu 模型反幻觉：护栏接入生成侧 + 云端 DPO 脚本（执行落地）

> 日期：2026-11-04 ｜ 配套方向报告：`VIRTU_ANTIHALLUCINATION_DIRECTIONS_2026-11-04.md`
> 本次按建议执行两件事：① 把 `Guard` 接进生成侧输出层（替换旧的只判分用法）；② 写好云端 DPO 训练脚本（用 132 条带标签错误回灌）。

---

## 1. 护栏接入生成侧输出层（P0，已完成并验证）

### 1.1 新增文件
- **`scripts/guard_hooks.py`** — 推理时护栏高层封装，供生成侧直接调用。
  - `apply_guard(raw, prompt, scenario, tol_rel, require_evidence)` → 返回 `{action, final_world_state, issues, layers_hit, provenance, binding_risk}`。
  - `check_scenario_binding()` — E6 场景绑定防护：若 `scenario.inputs` 数字未出现在 prompt 中，明确标记风险（护栏可信度上界 = 场景绑定可信度）。
  - 自检 7/7 PASS。
- **`scripts/worldmodel_infer.py`** — **标准生成侧推理封装（对外统一入口）**。
  - `generate_world_state(model, prompt, scenario, ...)` = `call_ollama` + `apply_guard`，返回 `{world_state, raw, guard}`。
  - 调用方**必须传 `scenario={task, inputs}`** 以启用 L2 求解器复算纠正（对应 E4 在线 A/B 的 +73pp 路径）。
  - 自带 CLI，便于单独验证/管道调用。

### 1.2 改造点
- **`scripts/eval_worldmodel.py`**（原「生成→只判分」链路）：
  - 生成后接入 `apply_guard`，新增 `guard_action` 到每条记录、新增「护栏检查 / 拦截」统计行。
  - 修 `call_ollama`：加 `think:false` + `num_predict` 适配 Qwen3（否则输出被 `<think>` 包裹、world_state 无法解析，且思考 token 吃光预算）。
  - 这把「只判分」升级为「生成即校验/纠正 + 判分」。

### 1.3 关键修复（裸字段归一化）
诊断发现：模型在部分 prompt 下输出**裸字段** `{"surface_roughness_ra_um": 112.5}` 而非契约包裹 `{"world_state": {...}}`。原 L0 把它们全判为「未登记顶层键」→ 100% 误杀。
在 `anti_hallucination_guard.run` 增加归一化：不含结构键(world_state/invalid/…)且不含禁止键(tool/arguments/…)的裸字段 dict，自动包成 `{"world_state": {...}}`。**E1 回归 132/132 召回、FPR 0% 不变**，护栏核心自检 9/9。

### 1.4 接入验证（真实推理）
用真正的世界模型 `virtu-wm-v3:latest` 跑 8 条评测：

| 指标 | 修复前 | 修复后 |
|---|---|---|
| 格式合规 | 0/8 | **5/8 (62.5%)** |
| 护栏拦截 | 8/8（全拒） | **2/8（仅真实异常）** |

护栏不再误杀有效输出，只拦真正不可解析/非契约的 2 条（ollama 偶发返回异常，非护栏问题）。生产侧 L2 数值纠正在 E4 在线 A/B 已验证（27%→100%、33%→100%，0 误杀）。

> 注：`qwen3:8b` 是未做世界模型 SFT 的全量基座，输出中文键格式，不适合直接当世界模型评测——这是模型本身能力问题，护栏如实拦截。

---

## 2. 云端 DPO 训练脚本（P2，已写好，未本地跑训练）

### 2.1 数据构造
- **`cloud_train_pack/build_dpo_dataset.py`**（本地可跑，不需 GPU）：
  - 从 6 组 `_eval_phys_*_*/triples.jsonl` 提取错误样本（过滤 `verified=False / verdict≠pass / score<100`）。
  - 构造 DPO 偏好对：`prompt=intent`、`chosen=正确的 world_state`、`rejected=模型错误的 world_state`。
  - **恰好产出 132 条**，与 E1 基线错误数完全一致，覆盖 9 类任务（roughness/removal/tolerance/design/collision/geom_delta/mass_props/adapt_machine/process）。
  - 产物：`cloud_train_pack/dataset/dpo_phys_rejects.jsonl`。

### 2.2 训练引擎
- **`cloud_train_pack/train_dpo_cloud.py`**（云端 GPU 执行）：
  - `trl` 的 `DPOTrainer`（兼容新版 `DPOConfig` 与老版 `TrainingArguments` 回退）。
  - base 自动探测 `Qwen3-8B-Instruct`（与 LoRA 基底同版本）；`--resume-adapter` 加载 v3 adapter 并 merge 进 base 再 DPO（**继承能力、防遗忘**）。
  - 显存分档：≥36GB 走 bf16-LoRA，<36GB 走 QLoRA 4-bit（沿用 `train_turnkey.py` 策略）。
  - 支持 wandb、deliverable 打包（`.tar.gz` + 指纹）、`--push-to` 对象存储。
  - env 变量兼容云端：`BASE/DATA/OUT/LR/EPOCHS/BS/ACCUM/MAX_LEN/SEED/RESUME_ADAPTER/WANDB_PROJECT/PUSH_TO/GPU_ID`。
- **`cloud_train_pack/run_dpo.sh`**：云端一键启动（conda + tuna 源装 `trl` 等依赖 + 探测数据集/adapter + 启动训练）。

### 2.3 用法
```bash
# 本地：生成偏好对（已执行，132 条就绪）
python cloud_train_pack/build_dpo_dataset.py --root D:/Virtu模型

# 云端 GPU 实例：开训
cd cloud_train_pack && bash run_dpo.sh
# 或手动：
python train_dpo_cloud.py --data dataset/dpo_phys_rejects.jsonl \
    --out output/virtu_dpo_antihallu --epochs 2 --lr 5e-6 --beta 0.1 \
    --resume-adapter checkpoints/virtu_v3_all90
```

---

## 3. 验证总表

| 项 | 结果 |
|---|---|
| 护栏核心自检 `anti_hallucination_guard --selftest` | 9/9 PASS |
| 护栏封装自检 `guard_hooks --selftest` | 7/7 PASS |
| E1 离线回放（180 条） | 检出 132/132（100%），误报 0%，FPR 0%，+73.33pp |
| 裸字段归一化回归 | E1 指标不变、核心自检 9/9 |
| 生产侧 L2 纠正（E4 在线 A/B，之前） | 27%→100% / 33%→100%，0 误杀 |
| eval 接入（v3，真实推理） | 格式合规 5/8，护栏拦截降至 2/8 |
| 云端 DPO 数据 | 132 条偏好对已生成 |
| 云端脚本 | 语法编译通过（本地无 GPU，未跑训练） |

---

## 4. 后续建议
1. **生产接入**：任何对外生成 world_state 的链路都应改调 `worldmodel_infer.generate_world_state` 并传 `scenario`，替换裸 `call_ollama`。
2. **何时触发云端 DPO**：当线上护栏 `corrected`/`rejected` 率连续偏高（说明模型本身仍常错），用本脚本回灌 132 条（及后续新采集的错误）做 DPO，降低护栏重写率。
3. **监控**：在生成侧记录 `guard_action` 分布（accept/corrected/rejected/escalate），作为线上幻觉率仪表。
4. **边界牢记**：E6（场景绑错护栏会 confidently wrong）、E2（自由文本全文接地不可用，只校验结构化字段）。

## 5. 交付物
- `scripts/guard_hooks.py`、`scripts/worldmodel_infer.py`
- `scripts/eval_worldmodel.py`（已改造）
- `scripts/anti_hallucination_guard.py`（已加裸字段归一化）
- `cloud_train_pack/build_dpo_dataset.py`、`train_dpo_cloud.py`、`run_dpo.sh`
- `cloud_train_pack/dataset/dpo_phys_rejects.jsonl`（132 条）
