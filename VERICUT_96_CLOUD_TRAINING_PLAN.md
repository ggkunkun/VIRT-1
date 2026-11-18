# VERICUT 9.6（`E:\training`）Agent 语料提取与云端训练计划

> **依据来源**：`C:\Users\Public\Desktop\Vericut 9.6.lnk` 指向本机 CGTech VERICUT 9.6 安装目录 `E:\`，其中 `E:\training` 为官方内置完整教学工程库（1,186 个去重文件 / 582.5 MB）。
> **诚信口径（《测量宪法 §8》）**：文中所有 **【实测】** 数据均来自本机脚本/门禁实跑回执；所有云端耗时与费用为 **【估算】**；上线判分为 **【计划目标】**（以训后本地实测为准）。

---

## 1. 为什么必须上云端训练（硬件与通道边界）

- **本地 GPU 实测限制【实测】**：本机 `nvidia-smi` 为 `NVIDIA GeForce RTX 4050 Laptop GPU`（`6141 MiB` 显存）。6 GB 显存无法在未严重裁剪上下文的情况下对 **Qwen3-8B**（非 Instruct 基座 `checkpoints/_base_qwen3_8b`，`hidden_size=4096`、`num_hidden_layers=36`、`vocab_size=151936`）执行 4096 长度 LoRA SFT 与 DPO 偏好对齐。
- **VERICUT 9.6 运行时通道真相【实测】**：
  - **已证实不可用（confirmed-negative）**：无可用 COM Automation 接口（6 个 ProgID `Dispatch` 全败 `-2147221005`）；`vericut.bat -b` / `batchp` / `batcht` 在本机 9.6 安装中不可靠或不存在；无 stdin IPC、UIA 无法穿透 JavaFX/JOGL 深层树。
  - **已证实可用（verified-working）**：`E:\windows64\commands\vericut_agent.bat` 设 `CGTECH_VCPROJECT` 与 `CGTECH_TRANSACTION_LOG=Yes` 拉起主窗 -> `cadcam_desktop_gui` 窗口聚焦与坐标驱动（Play `(1890,860)`、Stop `(1576,451)`、Reset `(830,108)` @ `1920x1080`）-> `cadcam_vericut_simulate(action="check_collision")` 解析仿真日志 + `cadcam_visual_inspect(task="autodiff_inspection")` 对 Auto-Diff 色谱/`.vcreview` ZIP 容器离线复查。
- **训练目标**：让 Agent 彻底掌握 CGTech `E:\training` 全部 4 大课程体系的工程 XML（`.vcproject` / `.vdafproject` / `.mch` / `.ctl` / `.tls`）、NC/宏/探针程序、单位纪律（严格区分 `inch` 与 `millimeter`）以及 VERICUT 真实工具链决策与红蓝绿过切熔断。

---

## 2. `E:\training` 官方课程资产盘点与结构化提取【实测】

通过可复现提取脚本 `scripts/extract_e_training_vericut.py` 对 `E:\training` 进行 **Windows NTFS 大小写去重解析**（避免 `.vcproject` 与 `.VcProject` 双重计数），全量资产零错误解析如下：

| 资产类别 | 提取数量【实测】 | 解析覆盖内容 |
| :--- | :---: | :--- |
| 课程 PDF（`training_sessions/`） | **90 份**（共 902 页，0 空白首页） | `verification` (49)、`machine_and_control` (29)、`optimization` (10)、`vdaf` (2)；提取 Session ID、变体 (`L/M/MT/FL/FM/ALL`)、核心步骤、UI 动作、Logger 报错与关联资产 |
| 工程 XML（`.vcproject` + `.vdafproject`） | **80 个**（78 `.vcproject` + 2 `.vdafproject`） | 版本全部 `9.6`；单位 **`inch` 35 个 / `millimeter` 45 个**；产品 `Vericut` 78 个 / `AutoFastener` 2 个；提取 `<AutoDiff>` 容差、`<Setup>`、`<Machine>`、`<Control>`、`<ToolMan>`、`<NCPrograms>`、`<CSystems>`、`<Work Offsets>`、`<Optimization>` 与 Build 组件树（自动剔除 `<Preview Image>` base64 缩略图） |
| 机床运动学（`.mch`） | **45 个**（全部 `<VcMachine>`） | 单位 `inch` 25 / `millimeter` 20；提取 `Base -> Linear/Rotary/Spindle` Attach 链、`RapidRate`、`TlMin..TlMax` 超程限位、碰撞 `Collision/Between` 检测对及阈值 |
| 控制器逻辑（`.ctl`） | **31 个**（全部 `<VcControl>`） | 提取 `<Words>` 字表类别分布、代表 G/M/宏字、`<Variables>`、`<Events>` 与 `<Subroutines>` |
| ToolMan 刀具库（`.tls`） | **65 个**（全部 `<CGTechToolLibrary>`） | 提取每把刀 `ID`、`Units`（Inch/Millimeter）、`Type`、`Apt Type`、`D/R/H/FluteLength/TeethCount`、`TeForceSettings` 与 `<Holder>` SOR |
| NC / 宏 / 探针程序 | **83 个** | `.mcd` (40)、`.sub` (17)、`.nc` (11)、`.eia` (9)、`.spf` (2)、`.tap`/`.tp`/`.min`/`.mpf` (各 1)；提取行号、模态词 (`G20/G21/G43/G54/TRAORI/CYCLE`) 与宏分支 |
| 其他几何与辅助文件 | **792 个** | `.stl` 286、`.ply` 193、`.str` 122、`.swp` 76、`.xply` 25、`.sor` 19、`.vctemplate` 7 等（合计 **1,186 个唯一文件**） |

---

## 3. Agent 样本设计、零泄漏划分与门禁体检结果【实测】

### 3.1 零泄漏按 Session Group 分层划分

为防止同一课程的 `L`（车）、`M`（铣）、`MT`（车铣复合）或同名工程文件产生跨集泄漏，提取器按 **Session Group** 整组划分，`holdout` 组包含所有 4 条赛道的代表课程：

- **Holdout Session Groups（8 组）**：`["6", "15", "22", "24", "105", "109", "255", "502"]`
  - 覆盖 Verification（Day-1 复盘 `6L/M/MT`、多工步 Cut Stock 传递 `15L/M/MT`、在机探测 `22`、分离残料清理 `24`）、Machine & Control（建机复盘 `105L/M/MT`、旋转轴控制配置 `109`）、Optimization（优化复盘 `255`）与 VDAF 编程（`502`）。
- **强制隔离**：任何归属上述 group 的 PDF 及其关联 `.vcproject`/`.vdafproject`/`.mch`/`.ctl`/`.tls`/NC 均划入 Holdout；并额外校验 **`train` 与 `holdout` 的 `evidence_sha256` 交集 = 0**、`user` 提示交集 = 0。

### 3.2 Agent 能力族分布与工具面约束

所有含工具调用的训练样本严格仅使用 `virtu_eval.tool_schema.runtime_tools()` 中的真实运行时工具（经 `cad_tools_iface.sanitize_tool_defs` 洗去可抄示例数字）：
- `cadcam_vericut_simulate`（Train 145 次 / Holdout 40 次）
- `cadcam_visual_inspect`（Train 148 次 / Holdout 36 次）
- `cadcam_cimco_validate`（Train 67 次 / Holdout 15 次）
- `cadcam_desktop_gui`（Train 57 次 / Holdout 18 次）
- `cadcam_preflight`（Train 41 次 / Holdout 8 次）

产出目录：`data/train/vericut_e_training_v1/`

| 数据集分片 | 路径 | 条数【实测】 | 文件字节 / SHA256（前 16 位） | 主要覆盖族 |
| :--- | :--- | :---: | :--- | :--- |
| 结构化目录 | `catalog/e_training_catalog.json` | 90 PDF + 80 工程 + 224 部件/NC | `925,461 B` | 全量元数据与 SHA256 账本 |
| **Train SFT** | `train/vericut_e_training_agent_sft.jsonl` | **495**（含 tools 234） | `2,067,399 B` / `fb632153e2ae0a47...` | `vericut_curriculum_workflow`(76), `vericut_nc_precheck`(67), `vericut_runtime_agent_loop`(63), `vericut_xml_setup_audit`(63), `vericut_tls_config`(52), `vericut_autodiff_triage`(41), `vericut_mch_config`(36), `vericut_boundary_refusal`(26), `vericut_ctl_config`(23), `vericut_gui_closed_loop`(19), `vericut_autodiff_blue_excess`(18), `vericut_specialized_module`(10), `vericut_logger_debug`(1) |
| **Holdout** | `holdout/vericut_e_training_holdout.jsonl` | **120**（含 tools 57） | `498,649 B` / `14201d037cf83de5...` | 全 12 类能力族，与 Train 零重叠 |
| **Train DPO** | `dpo/vericut_e_training_dpo.jsonl` | **104 组偏好对** | `125,571 B` / `7c9ecd5dd88327e4...` | Chosen（诚实工具链/XML单位/空图拒签/Auto-Diff红停） vs Rejected（COM幻觉/`vericut.bat -b`/白屏签过/inch-mm混用） |

### 3.3 实测 Qwen3 分词与 8 道门禁体检结果【实测】

以 `checkpoints/_base_qwen3_8b`（Qwen3 非 Instruct，实测词表 `151,669`、模板含 `<tools>` 段）实跑结果：

- **`validate_render_dataset.py`（C1–C5 全项 PASS 100.000%）**：
  - **Train（495/495 PASS）**：`min=184`, **`p50=489`**, **`p90=2119`**, `p95=2137`, `p99=2211`, **`max=2224`**, `mean=1122.2`；总 token `555,478`，计 loss token `128,449 (23.1%)`；`>4096` 截断 **`0 (0.00%)`**。
  - **Holdout（120/120 PASS）**：`min=185`, **`p50=432`**, `p90=2119`, `p95=2129`, `p99=2153`, **`max=2209`**, `mean=1115.0`；总 token `133,806`，计 loss token `29,583 (22.1%)`；`>4096` 截断 **`0 (0.00%)`**。
  - **长度关键发现**：因包含真实 `<tools>` schema，`p90=2119 / max=2224`。因此云端训练时 **`max_length` 必须 `>= 2560`（推荐 Route A `4096`）**，切勿沿用 `2048`，否则 >10% 工具调用回答将被截断！
- **`gate_all90_dataset.py`（8/8 GATES PASS）**：
  - Gate 1 Schema & Tools：checked `1,193` tool calls，未知工具 `0`。
  - Gate 2 System Prompt Budget：`max_bytes_seen = 392 B <= 702 B`。
  - Gate 3 Eval Contamination：vs `virtu_eval_v1`、`knowledge_base/six_software/training/datasets/vericut_holdout.jsonl` 及自建 `vericut_e_training_holdout.jsonl` 均 **`hard_leaks = 0`**。
  - Gate 4 Physical Units：`inertia_unit_bad = 0`。
  - Gate 6 Provenance & Derive Ratio：`require_provenance=True, max_derive_ratio=3` PASS（全部 495 条携带源文件真实 `sha256`）。
  - Gate 7 SHA256 Ledger：已生成 `vericut_e_training_agent_sft.jsonl.ledger.json`。
  - Gate 8 +5% 篡改反证探针：`mutated_probe_caught = True`。
- **`train_dpo_all90.py` 校验**：`validate_dpo_pairs` 通过 `104/104`，`hard_leaks = 0`，`inertia_unit_bad = 0`。
- **`pytest tests/test_vericut_e_training_extractor.py`**：`5 passed`。

---

## 4. 云端训练路线与防遗忘混合配方

### 4.1 硬件选型与双路线配置

| 项目 | 路线 A（首选推荐） | 路线 C（低成本备选） |
| :--- | :--- | :--- |
| GPU 实例 | **NVIDIA L40S 48GB**（Ada sm_89，约 `¥4.50/h`） | **Tesla V100-SXM2-32GB**（约 `¥1.98/h`） |
| 基座模型 | `Qwen3-8B`（非 Instruct，校验 `hidden_size=4096, layers=36, vocab=151936`） | 同左 |
| 精度与量化 | **纯 bf16 LoRA**（不量化，无截断风险） | **fp16 + 4-bit NF4 QLoRA**（`--qlora`） |
| `max_length` | **`4096`**（0.00% 截断【实测】） | **`2560`**（覆盖 `max=2224`，避免 `2048` 截断回复！） |
| Batch / Accum | `batch=1, grad_accum=16`（等效 batch 16） | `batch=1, grad_accum=16` |
| 训练框架 | `cloud_train_pack/train_turnkey.py` + `scripts/train_dpo_all90.py` | 同左（加 `--qlora`） |

### 4.2 防遗忘混合配比（Replay Mix）

单独用 495 条纯 VERICUT 数据全量微调会导致六软件路由、物理计算（`virtu_eval_phys_v1`）与 SOLIDWORKS/NX/CIMCO 能力发生灾难性遗忘。采用 **1:4 领域强化 + 通用回放配比**：

- **Stage 1（SFT 混合池，共 ~2,200–2,741 条）**：
  - VERICUT 9.6 `E:\training` Agent 强化语料：`495` 条 × 2 epoch 权重（可混采样 1x `495` 条，配合 `epochs=3`，或直接与 `data/train/virtu_engine_agent_v1/train/virtu_engine_agent_v1.jsonl` `2,246` 条按 1:3 拼接为 ~2,741 条；**注**：若按 `gate_all90_dataset` 单独验真，先对分片分别过闸，再拼接用于 `train_turnkey.py`，避免回放重复触碰 `max_derive_ratio`）。
  - 核心学习率：`lr=1.2e-4`（余弦退火，warmup 3%），`epochs=3`（约 `510` 步，含回放约 ~555k VERICUT token + ~1.8M 回放 token）。
- **Stage 2（DPO 偏好对齐）**：
  - 基于 Stage 1 产出的 LoRA 适配器继续运行 `scripts/train_dpo_all90.py`：`cloud_train_pack/dataset/vericut96_dpo_mix.jsonl`（共 `162` 对：104 对 VERICUT 9.6 + 30 对简洁通用 `dpo_concise_pairs.jsonl` + 28 对安全边界 `safety_boundary_dpo_pairs.jsonl`，system prompt 均 `<= 702B` 且经三基准零泄漏审计；已排除 `dpo_phys_rejects.jsonl` 111 条泄题样本与 >702B system prompt 的旧分片），`beta=0.1`、`lr=5e-6`、`epochs=1`、`--max-length 2560`。

### 4.3 耗时与费用预算【估算】

| 阶段 | 数据规模 | L40S 48GB 预计耗时【估算】 | L40S 费用【估算】 | V100 32GB 费用【估算】 |
| :--- | :--- | :---: | :---: | :---: |
| S0 冒烟验证（`--max-steps 20`） | 495 VERICUT SFT | ~3 分钟 | ~¥0.3 | ~¥0.2 |
| Stage 1 全量 SFT（VERICUT + 回放） | ~2,741 条 × 3 epochs | ~35–55 分钟 | ~¥2.7–4.2 | ~¥2.0–3.2 |
| Stage 2 受控 DPO | 104–300 对 × 1 epoch | ~10–15 分钟 | ~¥0.8–1.2 | ~¥0.6–1.0 |
| **合计（含上传/校验/打包）** | — | **~1.0–1.5 小时** | **约 ¥5–8（硬上限 ¥30）** | **约 ¥3–5（硬上限 ¥20）** |

---

## 5. 云端执行与本地部署标准操作命令（SOP）

### 5.0 一上线马上开训一键脚本（推荐实操入口）

已内置零等待预打包、双阶看门狗与全套门禁闭环脚本，上线云端 GPU 实例即可一键开训：

1. **离线构建防遗忘混合语料并预打包**（实例未开机前即可在本地先执行）：
   - `python scripts/build_vericut96_cloud_datasets.py`：生成 `cloud_train_pack/dataset/vericut96_sft_mix.jsonl`（`2,190` 条：`2×495` VERICUT + `900` 分层 `virtu_engine_agent_v1` + `300` 分层 `virtu_v3_text_sft`）与 `cloud_train_pack/dataset/vericut96_dpo_mix.jsonl`（`162` 对）及 `.sha256` / `*_ledger.json`。
   - `.venv\Scripts\python.exe cloud_train_pack\start_train_now.py --prepare-only --track vericut96 --repack`：运行全套 `--selftest` 并生成自包含归档 `cloud_train_pack/virtu_vericut96_bundle.tar.gz` 与 `.sha256`。
2. **Windows 一键等机上线开训 + 看门狗监控 + 自动回传部署**：
   ```powershell
   $env:DAMODEL_PASS="<SSH_PASSWORD>"
   .venv\Scripts\python.exe cloud_train_pack\start_train_now.py `
     --track vericut96 --host <HOST> --port <PORT> --follow --auto-deploy
   ```
   - 默认 `--deploy-tag virtu-vericut96:v1`；自动完成 `sha256sum -c` 解包、启动 `run_vericut96.sh`、双阶健康监控、完成后校验并部署 `output/virtu_vericut96/virtu_vericut96_deliverable.tar.gz`。
3. **云端节点终端直启**（已克隆仓库或已解压 `virtu_vericut96_bundle.tar.gz` 时）：
   ```bash
   # 仓库统一总控（后台 + 8s 探针）
   bash cloud_train_pack/start_cloud_train_now.sh --track vericut96 --bg
   # 或在解压根目录直接启动 8 阶段编排器（自动探测 32GB V100 -> max_length=3072 / >=40GB -> 4096）
   bash run_vericut96.sh
   ```

### 5.1 本地预检与分片手动核验

1. 本地复跑提取与 8 道门禁：
   ```bash
   python scripts/extract_e_training_vericut.py
   python scripts/validate_render_dataset.py --data data/train/vericut_e_training_v1/train/vericut_e_training_agent_sft.jsonl --base checkpoints/_base_qwen3_8b --out data/train/vericut_e_training_v1/train/render_report.json --max-length 4096
   pytest tests/test_vericut_e_training_extractor.py -v
   ```
2. 打包上传至云端工作目录 `~/virtu_vericut_train/`：需包含 `cloud_train_pack/`、`scripts/train_dpo_all90.py`、`scripts/gate_all90_dataset.py`、`scripts/corpus_unit_audit.py`、`virtu_eval/`、`data/benchmark/`、`data/train/vericut_e_training_v1/` 与回放集 `data/train/virtu_engine_agent_v1/`。

### 5.2 云端自检 -> 冒烟 -> SFT -> DPO（Linux GPU 节点）

```bash
# 0. 零 GPU 门禁与基座身份自检（拒绝 Instruct 与损坏词表）
python3 cloud_train_pack/train_turnkey.py --selftest
python3 scripts/train_dpo_all90.py --self-test

# 1. 可选：构建带回放的 SFT 混合文件（先验明分片 sha256，防遗忘）
cat data/train/vericut_e_training_v1/train/vericut_e_training_agent_sft.jsonl \
    data/train/virtu_engine_agent_v1/train/virtu_engine_agent_v1.jsonl \
    > /tmp/vericut_replay_sft.jsonl

# 2. S0 冒烟验证（20 steps，确认显存与 loss 下降，无 OOM）
python3 cloud_train_pack/train_turnkey.py \
  --base /root/models/Qwen3-8B \
  --data data/train/vericut_e_training_v1/train/vericut_e_training_agent_sft.jsonl \
  --ledger data/train/vericut_e_training_v1/train/vericut_e_training_agent_sft.jsonl.ledger.json \
  --out /root/out/vericut96_smoke \
  --max-length 4096 --max-steps 20 --batch 1 --grad-accum 16 --max-hours 0.3

# 3. Stage 1 SFT 主训练（L40S 用 bf16 max-length 4096；V100 加 --qlora 并设 --max-length 2560）
python3 cloud_train_pack/train_turnkey.py \
  --base /root/models/Qwen3-8B \
  --data /tmp/vericut_replay_sft.jsonl \
  --out /root/out/vericut96_sft_lora \
  --epochs 3 --lr 1.2e-4 --batch 1 --grad-accum 16 \
  --max-length 4096 --max-hours 1.5

# 4. Stage 2 DPO 偏好对齐（固化 COM 拒答、Auto-Diff 红过切阻断、inch/mm 纪律）
python3 scripts/train_dpo_all90.py \
  --base /root/models/Qwen3-8B \
  --adapter /root/out/vericut96_sft_lora/final_adapter \
  --data cloud_train_pack/dataset/vericut96_dpo_mix.jsonl \
  --out /root/out/vericut96_dpo_lora \
  --beta 0.1 --lr 5e-6 --epochs 1 --batch 1 --grad-accum 16 \
  --max-length 2048 --max-hours 0.8
```

> **断电/超时保护**：`train_turnkey.py` 与 `train_dpo_all90.py` 均启用 `TimeBudgetCallback`，触发 `--max-hours` 会安全落盘并返回 exit code `3`；仅当 `training_receipt.json` 中 `"status": "COMPLETED"` 且适配器 `adapter_sha256` 非空时才回传打包。

### 5.3 回传本地融合、量化转换与 Ollama 上线（Windows CPU）

严格使用 `cloud_train_pack/deploy_trained_adapter.py`（禁止改写已有 `virtu-master` 等评测引用标签，使用新版本号标签）：

```bash
python cloud_train_pack/deploy_trained_adapter.py \
  --deliverable checkpoints/vericut96_dpo_deliverable.tar.gz \
  --base checkpoints/_base_qwen3_8b \
  --tag virtu-vericut96:v1 \
  --work-dir checkpoints/_deploy_vericut96_v1 \
  --qtype q4_0
```

---

## 6. 训练后四层客观验收门禁【计划目标】

仅当以下 4 项验证全部由本地实跑命令通过并落盘后，方可宣布本次 VERICUT 9.6 专项训练完成：

1. **留出集（Holdout）离线评测**：在 `data/train/vericut_e_training_v1/holdout/vericut_e_training_holdout.jsonl`（120 条，全未知 Session Group）上测试：
   - 工具名与必填参数结构合规率 **>= 95%**（0 次虚构 `vericut.run_com` 或 `vericut.bat -b`）。
   - `inch` / `millimeter` 工程单位识别准确率 **100%**（0 次单位偷换）。
   - Auto-Diff 判据准确率 **100%**（红过切必停、蓝残料建议半精、空图 `valid_pixels=0` 必报 `INSUFFICIENT_EVIDENCE`）。
2. **既有 VERICUT 留出集对照**：在 `knowledge_base/six_software/training/datasets/vericut_holdout.jsonl`（8 条）保持或超过基线准确率。
3. **防遗忘总盘回归**：重跑 `virtu_eval_v1` / `virtu_eval_phys_v1` 代表集，6 软件总分及物理规则分退化幅度严格 **<= 3.0%**。
4. **真机桌面闭环验收（`E:\windows64\commands\vericut_agent.bat`）**：抽测至少 2 个本地工程（含 1 个 `inch` 与 1 个 `millimeter`，例如 `E:\training\mill_session_15m_multiple_setups_simulation.vcproject`），验证 Agent 能实际调起 `vericut_agent.bat` -> 窗口聚焦 -> GUI 播放 -> 日志碰撞解析与 Auto-Diff 检查全闭环，并产出带 `run_id` 与文件 `sha256` 的真实验收凭证。
