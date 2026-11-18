# 世界模型权重修复与评测体系建设（2026-11-12）

- 目标：按 [工业测试报告](file:///d:/Virtu模型/reports/INDUSTRIAL_TEST_virtu-wm-v3_2026-11-12.md) 的 P0，开始修复权重并建立可封缄、可统计的评测体系。
- 口径：`measured` = 本次实跑；`asserted` = 源码/台账事实；`untested` = 未测。
- 结论：**本地可完成的部分全部完成并通过门禁；权重本身尚未改变——3 个历史云端实例全部失联，无法开训。**

---

## 0. 结论摘要

| 项 | 结果 | 口径 |
|---|---|---|
| 评测题库 v2 | **360 例 / 12 族 × 30**，独立真值，冻结 | measured |
| 题库泄漏门禁 | 训练集逐字重合 **0**、v1 重复 **0**、最大 5-gram 覆盖率 **0.5882**（阈值 0.60） | measured |
| 封缄评测器 | 身份按权重 blob 哈希、逐例落盘、断点续跑、transport>5% 判废、summary+SEAL | measured |
| 12 例试点（旧版题库） | 严格通过 2/12、数值字段 7/35、宣称≠参数 9/15、transport 0% | measured |
| 修复语料 | **250 条轨迹 / 500 行**（10 条真实失败 + 240 条合成；坏轮 loss=False） | measured |
| 云端训练语料 | **4,766 行**，WM repair 478 行，坏轮掩码 646，量纲坏行 0，旧门禁 0，硬泄漏 0 | measured |
| 云端训练包 | 3.93 MB / 27 成员，sha256 `f2a1cda7…` | measured |
| 本地预演 Stage 1/2/训练器自检 | **全部 PASS**（train=4,623 / eval=143 / usable=4,766） | measured |
| 云端开训 | **阻塞**：3/3 历史实例 `NoValidConnectionsError` | measured |

---

## 1. 评测体系 v2

### 1.1 题库

文件：[wm_holdout_v2.jsonl](file:///d:/Virtu模型/data/holdout/wm_holdout_v2.jsonl)，账本：[wm_holdout_v2_ledger.json](file:///d:/Virtu模型/data/holdout/wm_holdout_v2_ledger.json)

- 12 族 × 30 例 = **360 例**（removal / mass_props / roughness / fea_fos / collision / tolerance / design / process / adapt_material / adapt_machine / geom_delta / invalid）
- 每族 3 套措辞 × 10 组参数；题面与训练语料不同措辞
- 真值由 [wm_holdout_regression.py](file:///d:/Virtu模型/scripts/wm_holdout_regression.py) 的 `HAND` 独立解析式算出；再逐字段用 `wm_verifier.recompute` 交叉复核，不一致即 fail-closed
- 每例正确应答必须被同一判分器 `eval_worldmodel.judge` 判过，否则拒绝落盘
- 冻结指纹：`sha256=8823096171979b8d39edc0a5736592f8b7c898be9792013067a6e4de21e8a340`
- 泄漏审计：训练集逐字 0、v1 重复 0、最大 5-gram 覆盖率 0.5882、无超阈值样本

生成器：[build_wm_holdout_v2.py](file:///d:/Virtu模型/scripts/build_wm_holdout_v2.py)（`--write` / `--check`）。

### 1.2 封缄评测器

文件：[run_wm_holdout.py](file:///d:/Virtu模型/scripts/run_wm_holdout.py)

- 被测对象按 **权重 blob 内容哈希** 寻址，不按标签名
- 逐例 append `raw.jsonl` + flush；中断可续跑
- 每例记录：原始响应、判分结果、缺失字段、时延、token 数、`served_model`
- transport error >5% 整腿判废（`valid=false`）
- 收尾写 `summary.json` 与 `SEAL.json`（raw/summary 的 sha256 + `run_id`）
- 统计：每族严格通过 / Wilson95、数值/文本/闸门字段占有率、宣称≠参数、闸门自相矛盾、时延 P50/P90
- 强制只允许 `data/holdout/**` 作为题集，防止训练集自测

试点（旧版题库，12 例）：`runs/wm_holdout_v2/pilot12/`，严格通过 **2/12 = 16.7%**，数值字段 **7/35** 正确，宣称≠参数 **9/15**，transport 0%，`valid=true`。新版题库修正了重复 ID 后，12 例试点因 6 GB 显存服务中断未完成；完整 360 例需 ≥12 GB 显存。

### 1.3 与旧 22 例留出集的关系

- v1（22 例）保留为历史对照，不删除；
- v2（360 例）用于后续权重修复的验收尺；
- 两套题互不重复（v1 duplicate = 0），也不与训练集逐字重合。

---

## 2. 修复语料（repairloop）

文件：[virtu_wm_repairloop_sft.jsonl](file:///d:/Virtu模型/cloud_train_pack/dataset/virtu_wm_repairloop_sft.jsonl)
账本：[virtu_wm_repairloop_sft_ledger.json](file:///d:/Virtu模型/cloud_train_pack/dataset/virtu_wm_repairloop_sft_ledger.json)
生成器：[build_wm_repairloop.py](file:///d:/Virtu模型/scripts/build_wm_repairloop.py)

- **250 条轨迹 / 500 行**：250 条多轮修复轨迹（坏解 `loss=false` → 校验器反馈 → 修正解）+ 250 条单轮正向样本
- 来源：10 条真实模型失败（cfgA 12 例中经判分器确认的坏解）+ 240 条合成修复（独立 seed 99001）
- 错误模式分布（measured）：binding 78、scale 57、drop 55、gate_flip 30、invalid_hard_compute 20、real_failure 10
- 硬约束（fail-closed）：
  - 坏解必须被 `eval_worldmodel.judge` 判 FAIL（3 条偶然通过的坏解被剔除）
  - 修正解必须被同一判分器判 PASS（0 条失败）
  - 修正解（非 invalid）必须被 `wm_verifier.verify` 接受
  - 与 `data/holdout/**` 题面重合 0 条
  - 量纲审计不可解析的 1 条被剔除
- 指纹：`sha256=1821361bad95ec3b3c29ac0385428f8fa482d7ba1e226cb96b195c6518e08314`

### 2.1 并入云端训练语料

[build_wm_cloud_fix_corpus.py](file:///d:/Virtu模型/scripts/build_wm_cloud_fix_corpus.py) 新增第二个 repairloop 源，并把 `wm_repairloop_kept_rows` 写进账本；缺失或 0 行即拒绝产出。

实测产出：

- 输出：[virtu_worldmodel_fix_sft.jsonl](file:///d:/Virtu模型/cloud_train_pack/dataset/virtu_worldmodel_fix_sft.jsonl)
- 4,766 行 / 21.13 MB，`sha256=d5cabe764cc5db50…`
- WM repair 入集 **478 行**；叶轮 repairloop **420 行**
- 坏轮掩码 **646 轮**（loss=False）
- 量纲坏行 **0**；旧门禁字面量 **0**；三大评测集硬泄漏 **0**；跨源去重剔除 3,376 行
- 账本：[virtu_worldmodel_fix_sft_ledger.json](file:///d:/Virtu模型/cloud_train_pack/dataset/virtu_worldmodel_fix_sft_ledger.json)

---

## 3. 云端训练链与本地预演

### 3.1 训练包

- [virtu_worldmodel_fix_bundle.tar.gz](file:///d:/Virtu模型/cloud_train_pack/virtu_worldmodel_fix_bundle.tar.gz)：3.93 MB / 27 成员，`sha256=f2a1cda7abc01a12…`
- 新增成员：`dataset/virtu_wm_repairloop_sft.jsonl` 与其账本
- Stage 1 账本闸已加：`wm_repairloop_kept_rows > 0` 且源文件指纹与账本一致，否则拒绝开训
- `bash -n run_worldmodel_fix.sh`：Git Bash 语法检查 **OK**

### 3.2 本地解包预演（measured）

| 阶段 | 结果 |
|---|---|
| Stage 1 账本/指纹 | PASS：rows=4,766，impeller=420，wm=478，masked=646，unit_bad=0 |
| Stage 2 契约/求解器 | PASS：`wm_verifier.selftest()` 全部通过（含缺参/除零/量纲反证） |
| 训练器 `--selftest` | PASS：usable=4,766（train=4,623 / eval=143），masked=646，legacy=0，max_tokens=2,560 |

### 3.3 云端实例探测（blocker）

读取 `.damodel_pass.json` 的 3 个历史 `host:port`，逐一 SSH 探测（未打印密码）：

```
DEAD cn-north-b.ssh.damodel.com 44228 NoValidConnectionsError
DEAD cn-north-b.ssh.damodel.com 34087 NoValidConnectionsError
DEAD cn-north-b.ssh.damodel.com 44910 NoValidConnectionsError
```

结论：**三个实例都已停止/释放，无法开训**。本地 6 GB 显存也无法对 Qwen3-8B 做全量 fp16 LoRA（训练器默认配置约需 22 GB 显存）。

---

## 4. 下一步（需要新 GPU）

### 4.1 启动云端实例

在 Damodel 控制台启动一台 **V100-32GB**（或 ≥12 GB 显存）实例，把新的 `host:port → password` 写入 `.damodel_pass.json`（或设置 `DAMODEL_HOST/PORT/PASS` 环境变量，密码不进聊天）。

### 4.2 一键训练

```powershell
# 凭据从文件/环境变量读取，不写进命令行
python cloud_train_pack/local_one_click_worldmodel.py --host <host> --port <port> --user root
```

链路：打包 → 上传 → 后台开训 → 8 秒存活探针 → 流式日志 → 只认 `COMPLETED` 回执 → sha256 硬校验 → 拉回 `checkpoints/virtu_wm_lora_fix/final_adapter`。

### 4.3 训后本地闭环

1. `merge_numpy.py` 把 LoRA 合并进 Qwen3-8B；
2. `hf_to_gguf_numpy.py` 量化 Q4_0；
3. `build_wm_modelfile.py --gguf … --name virtu-wm-v3:repair-20261112 --mode world --create` 注册**新标签**（不覆盖 `virtu-wm-v3:chatml`）；
4. `scripts/run_wm_holdout.py --cases data/holdout/wm_holdout_v2.jsonl --per-family 30` 跑 360 例；
5. 与基线对比，按 P0 验收线判定：数值字段正确率 ≥90%、宣称≠参数 ≤1%、严格通过 ≥85%。

---

## 5. 复现命令

```powershell
# 题库
.venv\Scripts\python.exe scripts\build_wm_holdout_v2.py --write
.venv\Scripts\python.exe scripts\build_wm_holdout_v2.py --check

# 修复语料
.venv\Scripts\python.exe scripts\build_wm_repairloop.py --synthetic-per-family 20

# 云端语料
.venv\Scripts\python.exe scripts\build_wm_cloud_fix_corpus.py

# 打包 + 本地预演
.venv\Scripts\python.exe cloud_train_pack\local_one_click_worldmodel.py --pack-only
```

---

## 6. 证据清单

| 证据 | 路径 |
|---|---|
| v2 题库 | [data/holdout/wm_holdout_v2.jsonl](file:///d:/Virtu模型/data/holdout/wm_holdout_v2.jsonl) |
| v2 题库账本 | [data/holdout/wm_holdout_v2_ledger.json](file:///d:/Virtu模型/data/holdout/wm_holdout_v2_ledger.json) |
| 封缄评测器 | [scripts/run_wm_holdout.py](file:///d:/Virtu模型/scripts/run_wm_holdout.py) |
| 试点封缄 | [runs/wm_holdout_v2/pilot12](file:///d:/Virtu模型/runs/wm_holdout_v2/pilot12) |
| 修复语料 | [cloud_train_pack/dataset/virtu_wm_repairloop_sft.jsonl](file:///d:/Virtu模型/cloud_train_pack/dataset/virtu_wm_repairloop_sft.jsonl) |
| 修复语料账本 | [cloud_train_pack/dataset/virtu_wm_repairloop_sft_ledger.json](file:///d:/Virtu模型/cloud_train_pack/dataset/virtu_wm_repairloop_sft_ledger.json) |
| 云端语料 | [cloud_train_pack/dataset/virtu_worldmodel_fix_sft.jsonl](file:///d:/Virtu模型/cloud_train_pack/dataset/virtu_worldmodel_fix_sft.jsonl) |
| 云端语料账本 | [cloud_train_pack/dataset/virtu_worldmodel_fix_sft_ledger.json](file:///d:/Virtu模型/cloud_train_pack/dataset/virtu_worldmodel_fix_sft_ledger.json) |
| 云端训练包 | [cloud_train_pack/virtu_worldmodel_fix_bundle.tar.gz](file:///d:/Virtu模型/cloud_train_pack/virtu_worldmodel_fix_bundle.tar.gz) |
| 本地预演解包 | [scratch/wm_bundle_preflight](file:///d:/Virtu模型/scratch/wm_bundle_preflight) |

---

## 7. 未测 / 限制

1. **权重未变**：本报告只完成修复语料、评测体系与训练包，未执行云端训练。
2. 360 例全量评测未跑；试点只跑 12 例，且用的是旧版题库修订前文件。
3. 合成修复语料的 240 条是“生成器题面 + 受控错误模式”，不等同于真实模型失败分布；真实失败只有 10 条，样本量小。
4. 5-gram 覆盖率 0.5882 接近阈值 0.60；后续若要更严格，可再改写模板降低到 0.5 以下。
5. 云训练成本按 11-11 报告外推约 ¥4.2–4.6，实际以实例计费为准。
