# 六大工业软件「全部 90 分」云端训练计划

- 版本：v1.0（2026-11-13）
- 上游依据：`reports/SIX_SOFTWARE_DL_DEPTH_AUDIT_2026-11-13.md`（A 轴 28.2 / B 轴 62.5）
- 训练入口：`scripts/train_six_software_cloud.py`（已具备 Qwen3 官方模板、C4 掩码、strict 门禁、receipt）
- 数据契约：`knowledge_base/six_software/training/TRAINING_CONTRACT.md`（C1-C5）
- 判分器：`virtu_eval/graders.py`（`g_numeric_near` / `g_physics_invariant` / `g_derivation_verified` / `g_gcode_structure` / `g_refusal`，均为数值/结构化判定，非关键词）

---

## 0. 先把「90 分」定义清楚（否则必然自欺）

**达标 = 三张卷子同时 ≥90，任一不达即不算达标。**

| 卷子 | 定义 | 每软件门槛 | 为何必须单列 |
| :-- | :-- | :-- | :-- |
| **卷 1 系统分** | 模型输出 + 确定性 oracle + 真实软件回读，端到端判分 | **≥90** | 这是「能不能出活」的最终口径 |
| **卷 2 模型裸分** | 不接管、不兜底，纯模型输出过同一套 oracle | **≥75** | 防「全靠闸门」把系统分刷到 90（§8：模型分与系统分永远分列） |
| **卷 3 工程闭环分** | 四步闭环（启动→执行→回读→取证）达成率 + 可复现性 | **≥90** | 训练改不了接口死活，必须配套工程修复 |

统计口径：每软件独立 holdout **n=200**，通过率 ≥92%，**Wilson 95% 下界 ≥0.85**；低于 0.85 视为未达标（n=22 的 0/22 无法支撑任何 90 分结论）。

现状与目标差距：

| 软件 | A 轴（权重深度） | B 轴（工程掌握） | 卷 3 目标 | 主要缺口 |
| :-- | --: | --: | --: | :-- |
| SOLIDWORKS 2021 | 34 | 77 | 90 | 语料非真实轨迹；feature_errors 未实现 |
| AutoCAD 2026 | 29 | 70 | 90 | 尺寸保真 0.0；COM 附着 RPC 挂起 |
| Siemens NX 12.0 | 28 | 72 | 90 | CAM/ONT 零实现；37 处 documented-not-probed |
| VERICUT 9.6 | 29 | 56 | 90 | 真跑率 16.7%；无 Auto-Diff 数值 oracle |
| CIMCO Edit 2026 | 25 | 50 | 90 | 「打开即算」；backplot 未入链 |
| SSCNC 7.2 | 24 | 50 | 90 | 走刀未执行；CRT 无 OCR |

---

## 1. 根因判定（决定计划形态）

1. **不是算力问题，是数据问题**。现有 260 条语料由静态文档枚举生成，`tool` 段返回是硬编码（`autocad_train.jsonl:1`）。这种数据训 100 遍也学不会「读回真实结果再判断」。
2. **不是模型容量问题，是判分问题**。36 题盲测 94.4% 是关键词命中；同批响应尺寸保真 0.7292、13 个幻觉尺寸。判分不换，90 分不可证伪。
3. **不是单点 bug，是闭环缺环**。VERICUT/CIMCO/SSCNC 的 `executed` 只证明「窗口打开了 / 文件写了」，不证明「加工跑完且结果可读」。

因此计划拆成两条并行线，**云端只做训练，真实轨迹采集必须在 Windows 本机/VM 完成**（六软件是 Windows 桌面程序，Linux GPU 机跑不了）：

```
线 A（本机/Windows VM）  真实轨迹采集 1,420 run  ──┐
线 B（云端 GPU）          SFT → 拒绝采样 DPO → 合并  ──┼──▶ 回灌本机：三张卷子验收
线 C（本机）             工程闭环 12 项修复        ──┘
```

---

## 2. 数据工程（占总工作量 60%，P0）

### 2.1 采集目标

| 软件 | 真跑 run 数 | 单次耗时 | 机时（含 1.8× 失败重试） | 派生后条数 |
| :-- | --: | --: | --: | --: |
| SOLIDWORKS 2021 | 300 | 45 s | 3.8 h | 3,600 |
| Siemens NX 12.0 | 300 | 20 s | 1.7 h | 3,600 |
| AutoCAD 2026 | 300 | 30 s | 2.5 h | 3,600 |
| CIMCO Edit 2026 | 200 | 10 s | 0.6 h | 2,400 |
| VERICUT 9.6 | 120 | 180 s | 12.0 h | 1,440 |
| 斯沃 SSCNC 7.2 | 200 | 40 s | 2.2 h | 2,400 |
| **合计** | **1,420** | | **≈22.8 h（分 5 晚）** | **17,040** |

> VERICUT 是瓶颈（真跑一次 3 分钟且 GUI 偶发 `IDLE_KILLED`）。**不压缩它的真跑数、不用日志冒充**，宁可少而真：120 个真实 run 已能覆盖「装夹/刀具/程序/碰撞/过切」五类判定。

### 2.2 每条轨迹的硬结构（缺一不入库）

```json
{
  "run_id": "sw_20261114_0031",
  "software": "solidworks",
  "wish": "…含具体参数…",
  "tools": [...],
  "messages": [...],
  "ground_truth": {
    "volume_mm3": 99278.3,
    "analytic_volume_mm3": 99278.3,
    "deviation_pct": 0.0,
    "step_bytes": 11843,
    "source": "COM.CreateMassProperty",
    "tolerance": {"volume_mm3": 1.0}
  },
  "verdict": "pass",
  "evidence_path": "runs/full_chain/20261114_0031/chain_evidence.json"
}
```

**真实性四条铁律**：
1. `ground_truth.source` 必须是软件自身回读（COM/NXOpen/accoreconsole/simlog），**外部解析器必须标 `source="external_parser"`**，不得冒充软件输出。
2. `run_id` 必须能在 `runs/full_chain/<run_id>/` 或 `trajectories/<software>/<run_id>/` 找到，且含 sha256。
3. 跨 run 复用日志 = 伪造（参考 `AGENT_CHAIN_RUNTIME.md:86` 的 sidecar 撤回事件），门禁直接拒绝。
4. 失败样本同样入库（`verdict=blocked/unsupported/substituted`），但 `ground_truth` 只记真实错误原文，不补「理想答案」。

### 2.3 五类场景配比（每软件）

| 场景 | 占比 | 内容 | 真实来源 |
| :-- | --: | :-- | :-- |
| A core_op | 40% | 建模/出图/仿真/CAM 主链 | 真实 run 派生 |
| B plugin_op | 20% | Toolbox/Simulation/Post Builder/ToolMan/DNC/面板 | 真实 run 派生（插件真开） |
| C kb_lookup | 15% | 先查模块事实再执行 | 知识库 + 真实返回 |
| D edge | 15% | 缺参澄清 / 越界拒答 / 联锁保护 | 真实失败样本 |
| E repair | 10% | 错误诊断→修正→复跑成功 | 真实修复 run（新增，最值钱） |

**E 类是本轮新增**，直接对应审计里「模型不会从错误中恢复」的短板：例如 NX 环槽 `CreateTorusBuilder` 不存在 → 改 `CreateBallGroove` 并重试；AutoCAD RPC 挂起 → 降级 accoreconsole；VERICUT 窗口丢失 → 重连或标 substituted。

### 2.4 派生规则（允许/禁止）

| 操作 | 允许 | 说明 |
| :-- | :-- | :-- |
| 同一 run 换 8-12 种中文句式 | ✅ | 数值/返回不变，答案不变 |
| 多轮工具链重排（同 run 内） | ✅ | 顺序需符合真实依赖 |
| 改参数后复用旧回读 | ❌ | 必须重跑，否则是伪造 |
| 跨 run 拼接 tool 返回 | ❌ | 数值与 run_id 必须同源 |
| LLM 生成「理想工具返回」 | ❌ | 一票否决 |

### 2.5 数据门禁（8 条，全自动，不过 99% 不开训）

1. JSON 逐行可解析，`arguments` 为合法 JSON 字符串。
2. 工具名 ∈ 运行时工具面（14 个 `cadcam_*` + `legacy_aliases`）；语料工具名必须先映射，映射不到直接丢。
3. `arguments` 与 gold 逐字段相等（含数值类型/单位）。
4. `run_id` 可解析到真实目录，`sha256` 校验通过。
5. 数值字段带单位与容差；缺单位即丢。
6. 与 holdout 的 8-gram Jaccard = 0；gold 数值不在 prompt 中出现。
7. 失败样本必须含真实错误码/原文，不得只写 "failed"。
8. **反证测试**：随机替换 5% 的 `ground_truth` 数值，判分器必须判红；未红则门禁本身失效，停线修门禁（§8.4）。

---

## 3. 云端训练配方

### 3.1 基座与硬件决策

| 方案 | 基座 | 卡 | 单价 | 适用判据 |
| :-- | :-- | :-- | --: | :-- |
| **主路线** | Qwen3-8B | L40S 48GB | ¥4.50/h | 卷 2 裸分能到 ≥75 就走完 |
| 备选 | Qwen3-14B | A800 80GB | ¥6.90/h | 8B 两轮后裸分仍 <70，或参数一致率 <85% |

> 不直接上 14B 的理由：仓库唯一被反复验证的底座是 Qwen3-8B（`AGENT_TRAINING_PLAN.md:9,47-60`），先排除数据问题再谈容量，避免「换大模型掩盖脏数据」。

### 3.2 三阶段训练

**S1 监督微调（格式 + 知识 + 真实回读）**
- 数据：17,040 条派生 + 2,000 条 edge/repair ≈ 19,000 条；max_len 4096；2 epoch。
- 超参：LoRA r=64 / alpha=128 / dropout 0.05，7 个 target modules，lr 1e-4，cosine，warmup 100，batch 4 × grad_accum 2（L40S 4096 长度可承载）。
- 掩码：沿用 `virtu_tokenize.build_example`，`tool` 段一律 `-100`（防模型学伪造返回）。
- 命令：
```bash
python scripts/train_six_software_cloud.py \
  --base /data/models/Qwen3-8B \
  --data-dir /data/work/datasets_all90 \
  --out /data/work/lora_all90_s1 \
  --mode qlora --epochs 2 --batch 4 --grad-accum 2 --max-length 4096 \
  --lora-r 64 --lora-alpha 128 --lr 1e-4 --strict \
  --eval-holdout --group-by-length --no-grad-ckpt --min-vram-gb 40
```
- 预估：63M tok/epoch ÷ 1,300 tok/s ≈ 13.5 h/epoch，2 epoch ≈ **27 h ≈ ¥121**。

**S2 拒绝采样 + DPO（把「会做」变成「做对」）**
- 用 S1 模型对每个 prompt 采样 4 条（temperature 0.8），oracle 打分，取最高/最低构造偏好对，约 12,000 对；混入 20% 失败降级样本（正确拒绝 vs 伪造成功）。
- DPO：β=0.1，lr 5e-5，1 epoch，max_len 4096，约 8 h ≈ **¥36**。
- 这一步专治「格式对但数值错」——审计里 22/22 形态合规但数值对 0/22，正是 DPO 的靶心。

**S3 六专家 LoRA + 合并（防相互污染）**
- 每软件单独 LoRA（r=32）在统一 S1 权重上微调 1 epoch（约 2 h/软件，可夜间串行，共 12 h ≈ ¥54）。
- 合并：`add_weighted_adapter(linear)`，权重按各软件 holdout 网格搜索（0.2/0.3/0.5 三档），合并后必须重跑全部 holdout，**合并掉分即回退单模型**。
- 产物：`adapter_model.safetensors` + `adapter_config.json` + `tools_schema.json` + `training_receipt.json`（沿用现有格式）。

### 3.3 云端执行时序

| 阶段 | 动作 | 时长 | 累计费用 |
| :-- | :-- | --: | --: |
| T0 | `make_cloud_bundle.py` 打包语料+脚本（含 sha256 清单） | 10 min | — |
| T1 | `gpu_bootstrap.py` 环境 + ModelScope 下 Qwen3-8B（放数据盘） | 30 min | ¥2 |
| T2 | 模板探针 + `--validate-only` + `--smoke 40` | 20 min | ¥2 |
| T3 | S1 全量训练（27 h，`--time-budget-min` 兜底） | 27 h | ¥121 |
| T4 | S2 拒绝采样 + DPO | 9 h | ¥41 |
| T5 | S3 六专家 + 合并 + holdout 复评 | 13 h | ¥59 |
| T6 | 拉回 adapter + 量化 GGUF + Ollama 部署 | 1 h | ¥5 |
| **合计** | | **≈51 h** | **≈¥230** |

预算上限（含 1 次返工 + 断点续训）：**¥320**；14B 备选：**¥480**。

---

## 4. 工程闭环配套（卷 3 达标，非训练可替代）

按「分数收益 / 工作量」排序，全部有明确验收：

| # | 动作 | 目标文件 | 验收 | B 轴收益 |
| :-- | :-- | :-- | :-- | --: |
| 1 | VERICUT GUI 双确认纳入链判定（窗口存活 + 事务日志 `ActionMainPlay`） | `work/vericut-toolchain/vericut_link.py`、`agent_chain_executor.py` | 连续 10 次真跑 ≥9 次 `executed` | +14 |
| 2 | VERICUT Auto-Diff 真截图 + HSV 三色判定接线（字段名对齐） | `cadcam_vision_bridge.py`、`triage_autodiff.py` | 红/蓝/绿样本各 20 张，判对率 ≥95% | +8 |
| 3 | AutoCAD 启动改子进程 + accoreconsole 兜底 + 3 次退避 | `autocad_bridge.py` | 20 次连续启动 ≥19 次成功 | +8 |
| 4 | SSCNC CRT 模板匹配 OCR（读 MACHINE/RELATIVE/ABSOLUTE） | 新增 `sscnc_ocr.py` | 50 帧读数误差 ≤0.01 mm | +10 |
| 5 | CIMCO backplot 导出或正式声明「仅静态校验」 | `cimco_bridge.py`、工具描述 | 声明与实现一致，无「已背绘」假宣称 | +6 |
| 6 | SW `feature_errors` 诊断补齐 | `solidworks_bridge.py` | 注入 10 个坏特征全部报出错误码 | +5 |
| 7 | NX Operation Navigator CAM 警告检查 | `agent_chain_executor.py::stage_nx` | 10 个含警告的 CAM 树全部识别 | +5 |
| 8 | AutoCAD 文本-尺寸 bbox 重叠检测 | `cadcam_vision_bridge.py` | 20 张人工标注图召回 ≥0.9 | +5 |
| 9 | 标准件库键名修复（`SOLIDWORKS 2021` + 字段名） | `tool_calling_specs.py` | 查询返回非空且字段齐全 | +2 |
| 10 | `analyze_inspection` 悬空调用修复 | `super_agent.py` | 调用不再 AttributeError | +2 |
| 11 | 工具描述口径回收（VERICUT 无头批处理等 6 处） | `tool_calling_specs.py`、`README.md` | 描述与实现逐条比对通过 | +2 |
| 12 | 18 份链重跑，`executed` 率 ≥95% | `runs/full_chain/` | 新 18 份取证包统计 | +13 |

> 卷 3 的 90 分不是「加权平均凑出来」，而是第 12 项的重跑统计：**每软件四步闭环 ≥90%**，且失败必须带根因，不允许 `substituted` 计入成功。

---

## 5. 验收协议（可证伪）

### 5.1 三张卷子

```bash
# 卷 1/2：模型裸分 + 系统分（分列，不合并）
# 两个 arm 先在 virtu_eval/arms.json 注册：guard=none（裸分）/ guard=production（系统分）
# 注意：软件维度靠 case 文件的 dim 字段区分，--dims 只做维度过滤，不要填软件名
python -m virtu_eval.runner --arm all90_model --arms-config virtu_eval/arms.json \
  --case-dir data/eval/six_software_holdout_200 --out-dir runs/eval_all90_model \
  --tiers easy,medium,hard --repeats 1 --temperature 0 --seed 1234
python -m virtu_eval.runner --arm all90_system --arms-config virtu_eval/arms.json \
  --case-dir data/eval/six_software_holdout_200 --out-dir runs/eval_all90_system \
  --tiers easy,medium,hard --repeats 1 --temperature 0 --seed 1234

# 卷 3：工程闭环（--stage 缺省即 all；重跑全链并落取证包）
python agent_chain_executor.py --out runs/full_chain_all90
```

> `scripts/run_remote_eval.py` 是旧的 arms 评测入口（参数为 `--arm/--dest/--dims/--sample-per-tier`），**不要**用本计划的命令套它；六软件评测统一走 `virtu_eval/runner.py`。

### 5.2 通过判据

| 项 | 判据 |
| :-- | :-- |
| 每软件卷 1 | ≥90%，n=200，Wilson 下界 ≥0.85 |
| 每软件卷 2 | ≥75% |
| 每软件卷 3 | 四步闭环 ≥90%，且 0 条「假 executed」 |
| 六软件整体 | 三卷全部达标（18/18 项） |
| 反证 | 植入 5% 错值 → 判分必红；空响应 → 必红；关键词满分数值错 → 必红 |
| 防污染 | holdout 与 train 8-gram Jaccard=0；gold 数值 0 命中；system ≤702 B 且不含答案 |

### 5.3 未达标处置

- 单软件 <90：只回采该软件数据（+100 run），**不整体重训**，避免七次返工烧钱。
- 卷 2 <75 但卷 1 ≥90：说明闸门接管过多，先查数据真实性，再考虑升 14B。
- 卷 3 <90：属工程缺陷，回 §4 对应项，不碰训练。

---

## 6. 排期（14 天）与预算

| 天 | 线 A 采集 | 线 B 训练 | 线 C 工程 |
| :-- | :-- | :-- | :-- |
| D1-D2 | SW/NX/AutoCAD 各 300 run | — | #3 #9 #10 |
| D3-D4 | CIMCO/SSCNC 各 200 run | 数据门禁 + 反证 | #4 #6 |
| D5 | VERICUT 40 run | 打包/环境/冒烟 | #1 |
| D6-D7 | VERICUT 80 run | **S1 训练（27 h）** | #2 #7 |
| D8 | 派生 + 门禁复跑 | S1 holdout 首评 | #5 #8 |
| D9-D10 | 补采（缺口软件） | **S2 DPO（9 h）** | #11 |
| D11-D12 | — | **S3 六专家 + 合并（13 h）** | #12 首轮重跑 |
| D13 | 回灌本机三卷验收 | 按结果决定是否返工 | 按结果补项 |
| D14 | 复验 + 出报告 | 部署 Ollama | 终验 |

| 项 | 金额 |
| :-- | --: |
| GPU（S1+S2+S3+环境+评测） | ¥230 |
| 返工预留（1 次） | ¥60 |
| 存储/流量 | ¥10 |
| **合计上限** | **¥300（8B）/ ¥480（14B 备选）** |

---

## 7. 风险与熔断

| # | 风险 | 判据 | 处置 |
| :-- | :-- | :-- | :-- |
| R1 | 数据污染（holdout 泄漏） | 8-gram 命中 >0 | 丢弃该批，重生成 holdout |
| R2 | 伪造回读 | `run_id`/sha256 对不上 | 整批作废，回采集器修 |
| R3 | 过拟合 | train loss <0.1 且 holdout 不涨 | 停训，加数据/降 r，不加 epoch |
| R4 | VERICUT 采集超时 | 12 h 内 <80 run | 降到 100 run，但不减真跑比例 |
| R5 | 云端断连 | 丢失 >500 step | `resume_from_checkpoint` 续训 |
| R6 | 14B OOM | 48GB 装不下 | 切 A800 80GB 或回 8B |
| R7 | 成本超支 | 累计 >¥320 | 熔断，出 RCFA，不追加 |
| R8 | 合并掉分 | 合并后 holdout 任一项降 >3 分 | 回退单模型，保留 adapter |

---

## 8. 新增脚本清单（接口契约，先写后跑）

| 脚本 | 输入 | 输出 | 验收 |
| :-- | :-- | :-- | :-- |
| `scripts/collect_six_trajectories.py` | 软件名、参数网格、run 根目录 | `trajectories/<sw>/<run_id>/{trace.jsonl,ground_truth.json,evidence.sha256}` | 1,420 run 全部有 ground_truth |
| `scripts/derive_trajectories.py` | 真实 run + 句式模板 | 派生 JSONL（run_id 不变） | 数值零改动（diff 断言） |
| `scripts/gate_all90_dataset.py` | 派生 JSONL + holdout | 门禁报告（8 条） | 通过率 ≥99%，反证必红 |
| `scripts/build_six_holdout_200.py` | 知识库 + oracle | `data/eval/six_software_holdout_200/`（6 个 case 文件 × 200 题，criteria 为 grader 列表） | 人工抽检 30 题全对 |
| `scripts/train_dpo_all90.py` | S1 adapter + 偏好对 | S2 adapter | DPO loss 下降且 holdout 涨 |
| `scripts/eval_all90_three_boards.py` | 三卷用例 + adapter | `eval_report.json`（分开列模型分/系统分） | 18/18 项判定 |

> 写一个跑一个：每个脚本先 `--self-test`（含反证用例），通过后才进流水线；未验证脚本禁止接链（§6 单步自查）。

---

## 9. 一句话结论

**90 分不是把现有 260 条语料多训几轮能得到的**：必须先把「工具返回」从模板改成真实回读（1,420 个真跑 run），把判分从关键词换成数值 oracle（n=200/软件），再用 SFT→DPO→六专家把「会调工具」练成「算得对、错了能修」；与此同时用 12 项工程修复把 VERICUT/CIMCO/SSCNC 的「打开即算」补成真闭环。预算 ¥300 封顶，14 天，达不到就按 §5.3 单点返工，不整体重训。
