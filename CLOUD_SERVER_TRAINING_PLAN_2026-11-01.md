# 云端服务器训练计划（六软件执行阻塞触发版）— 2026-11-01

> 触发条件：本地实机六软件协同链在第 1 站（SOLIDWORKS 2021）连续 **15 分钟零产物、零 CPU 推进**，按“很久没有执行”规则转入云端训练计划。
> 本计划只做一件事：把“模型能不能稳定下发给六软件”这个问题，从本地残缺环境搬到可复现的云端环境里训练并验收。

---

## 0. 触发证据（本机实测，非估算）

| 项目 | 结果 | 证据 |
|---|---|---|
| 六软件预检 | **6/6 READY** | `python cadcam_cli.py preflight` |
| 极限解析链（绘图→建模→仿真→加工） | **success，212.18 ms**，FOS=4.80，ΔV>0，0 碰撞 | `runs/random_task_20261101/20261101_224456/` |
| AutoCAD 2026 原生 | **PASS**，5 实体 DXF，0.02 s | `native/GuideSleeve_GB.dxf` |
| CIMCO Edit 2026 原生 | **PASS**，FANUC Macro B 44 行 / 6 变量校验通过 | `native_report_part1.json` |
| NX 12.0 | journal 已生成（未执行） | `native/GuideSleeve_D80_d20_L120_nx.py` |
| SOLIDWORKS 2021 | **BLOCKED**：SLDWORKS pid 14776 无主窗口标题、未注册 ROT、单实例守卫生效 → `ensure_process` 永久等待 | 链进程 pid 22224 CPU 冻结在 0.42 s，22:47:31 后无任何新文件 |
| 六站原生判定 | **0/6** 完成 | `chain/20261101_224731/` 仅 7 个模板文件，无 verdict |

结论：**离线可算的部分（几何/强度/宏语法）已经过关；桌面 COM/GUI 这一段在没有窗口句柄与 ROT 注册的会话里不可修**。这不是模型能力问题，而是执行环境问题——所以计划拆成两条并行线：**云端训练“决策与参数生成”，本地/云上 VM 负责“落地执行”**。

---

## 1. 目标与验收门槛

| 维度 | 门槛 | 测量方式 |
|---|---|---|
| 工具调用合法率 | ≥ 95%（JSON 可解析、字段齐全） | `scripts/validate_virtu_toolcall.py` |
| 六软件路由正确率 | ≥ 90%（wish → 正确 software+action） | 六软件留出集 200 条 |
| 失败态处置正确率 | **100%**：遇到 blocked/未连接必须输出“降级接入方式 + 不可执行原因”，禁止伪造成功 | 本机故障样本 40 条 |
| 几何/工艺公式 | ≥ 90%（n / Vf / MRR / T） | 200 条公式留出集 |
| 反例红线 | 0 条“声称已建模/已加工但无产物” | 人工抽检 100 条 |

> 第 3 行是本轮阻塞直接喂出来的新增门槛：模型必须学会“拒绝 + 降级”，而不是继续等。

---

## 2. 算力选型（丹摩 DAMODEL 按量租用）

| 方案 | 卡型 | 显存 | 适用 | 单价（估） | 预计机时 | 预计 GPU 费 |
|---|---|---|---:|---|---:|---:|
| A（推荐） | V100-SXM2-32GB | 32 GB | QLoRA NF4 + fp16，max_len 2048 | ¥1.98/h | 2–4 h | **¥4–8** |
| B（长样本） | L40S | 48 GB | bf16 LoRA，max_len 5120，零截断 | ¥4–5/h | 3.4–4.4 h | ¥15–30 |
| C（最低价） | RTX 4090 | 24 GB | QLoRA，需截断 301 条长答案 | ¥2–3/h | 2–3 h | ¥5–8 |

- 单价与机时沿用 `CLOUD_FINETUNE_PLAN_2026-11-01_v2.md` 的口径，**租机前按当日面板价复核**。
- V100 无 bf16、无 FlashAttention-2，必须走 `requirements-v100.txt`（torch 2.5.0 / cu124），**禁止装 flash-attn**。
- 存储与流量：语料 11.7 MB 级，可忽略；LoRA 产物 < 1 GB。总成本 A 方案 **< ¥30**。

---

## 3. 数据配方（在既有 5,991 条上增量，不重训全量）

| 来源 | 条数 | 用途 |
|---|---:|---|
| `data/train/virtu_fix_v1/train/virtu_fix_text_sft_v1.jsonl` | 5,991 | 主体 SFT（实测 3,104,927 token/epoch @2048；2 epoch = 6,209,854） |
| 六软件工具调用对齐集 `virtu_toolcall_train_aligned.jsonl` | 现成 | 单独 LoRA，不与文本 LoRA 合并 |
| **新增：故障处置样本（本轮产生）** | 40–80 | 输入=“SOLIDWORKS 已运行但未连接/无窗口”，输出=结构化 `{"status":"blocked","fallback":"MCP|PYTHON_SDK","reason":...}`，**禁止**输出 success |
| **新增：六软件路由样本** | 200 | wish → `{software, action, params}`，覆盖 6 个软件 × 4 类动作 |

增量语料生成口径：
- 只用确定性模板 + 真实报错原文（`ensure_process` 超时、ROT 未注册、单实例守卫），不编造日志。
- 每条必须带“为什么拒绝”的一句话，长度 ≤ 60 token。
- 入训前跑 `scripts/validate_toolcall_data.py`，JSON 解析失败率必须为 0。

---

## 4. 训练超参与命令

A 方案（V100 32GB）：
```bash
# 环境
pip install torch==2.5.0 --index-url https://download.pytorch.org/whl/cu124
pip install -r requirements-v100.txt

# 长度审计（5–8 分钟，用于确认 max_len 取舍）
python scripts/train_virtu_l40s.py --audit-lengths

# 主训练：QLoRA NF4 + fp16，group_by_length=True，2 epoch
python scripts/train_virtu_v100.py \
  --base checkpoints/_base_qwen3_8b \
  --data data/train/virtu_fix_v1/train/virtu_fix_text_sft_v1.jsonl \
  --max-len 2048 --epochs 2 --batch 1 --grad-accum 32 \
  --lr 2e-4 --lora-r 16 --lora-alpha 32 --bf16 false
```

一键流水线（推荐，自带 preflight → prepare → validate → train → verify → handoff）：
```bash
python scripts/gpu_train_pipeline.py --stage all \
  --data data/train/virtu_fix_v1/train/virtu_fix_text_sft_v1.jsonl \
  --out runs/cloud_20261101
```

关键超参理由：
- `group_by_length=True`：p50=184 / max=5,012（27 倍差），不分桶约 96% 是 padding。
- `max_len=2048` 砍掉 21.5% token，但 300 条长样本全在 ≥4096；若 A/B 显示长输出弱，**先怀疑截断**，再换方案 B。
- 工具调用专家**单独 LoRA**，不 TIES 合并进文本 LoRA，避免 schema 污染。

---

## 5. 执行时序

| 阶段 | 动作 | 产出 | 预计 |
|---|---|---|---|
| T+0 | 生成故障处置 + 路由增量语料，跑数据校验 | `data/train/incident_v1/*.jsonl` | 本地，< 10 min |
| T+1 | 打包上传（`scripts/make_cloud_bundle.py`） | bundle.tar.gz + sha256 | 5–10 min |
| T+2 | 云端 bootstrap（`scripts/gpu_bootstrap.py`） | 环境自检通过 | 20–30 min |
| T+3 | 长度审计 + 正式训练 | LoRA adapter | 2–4 h（V100） |
| T+4 | 云端评测（工具调用合法率 / 路由 / 公式） | `eval_report.json` | 20–30 min |
| T+5 | 拉回 + 量化 + 部署 Ollama | GGUF + Modelfile | 30–60 min |
| T+6 | **回灌本机复测**：同一张随机任务单再跑一次六软件链 | 六站 verdict | 10 min |

T+6 是本次计划的验收动作：只有六站 verdict 全绿，训练才算“接上生产”。

---

## 6. 预算

| 项 | 金额（估） |
|---|---:|
| GPU 机时（V100，4 h 上限） | ¥8 |
| 冷启动/失败重跑预留（1 次） | ¥8 |
| 存储/流量 | < ¥5 |
| **合计** | **< ¥25** |

方案 B（L40S，零截断）合计上限约 ¥45。

---

## 7. 熔断、回滚与风险

| 风险 | 处置 |
|---|---|
| 训练 loss 不收敛 / 连续 2 次同构报错 | 停训 → 回滚到上一 adapter（`checkpoints/virtu_v100_master_lora`）→ 出 RCFA，不换模型瞎试 |
| 云端断连 / 实例被回收 | 每 500 step 存 checkpoint 并 `scp` 回本地，最多损失 500 step |
| 合并后质量下降 | 保持“文本 LoRA / 工具调用 LoRA”双轨，合并失败只回退其一 |
| 本机 SOLIDWORKS 仍不可连 | 执行侧改走 `MCP / PYTHON_SDK` 接入，**不再对 ROT 附着做第 4 次尝试**（已 3 次熔断） |

已熔断项（不再重试）：
1. `ensure_process("SLDWORKS.exe")` 附着既有实例 → 超时；
2. 二次启动 SOLIDWORKS → 被单实例守卫拒绝（这是正确行为，保留）；
3. 依赖 `MainWindowTitle` 的 GUI 焦点/截图 → 该会话无窗口句柄。

---

## 8. 一句话结论

**本地离线闭环（几何/强度/宏语法）已 100% 达标且 212 ms 完成；卡点在桌面 COM/GUI 会话，不在模型。** 云端只训练“怎么选软件、怎么给参数、失败怎么降级”，验收标准就是回到本机把同一张任务单跑成 6/6。
