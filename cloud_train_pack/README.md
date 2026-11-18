# Virtu 工业大模型 · 云端极速训练与修复闭环套件 (2026-11-14 v2)

本目录统一收口主力模型（`Qwen3-8B` 线：`virtu-ties-v1` / `virtu-comprehensive` / `virtu-master`；`13.63B / 14B` 线：`virtu-13.63b` / `virtu-moe-14b`）及专题修复线（WorldModel / Safety Boundary / All-90）的云端训练、门禁校验、安全打包回传与本地真融合部署流水线。

---

## ⚡ 上线马上开训（0 秒等待一键闭环）

| 场景 | 一键命令 | 核心机制 |
| :--- | :--- | :--- |
| **本地 Windows 提前备战** | `START_CLOUD_TRAIN_NOW.cmd` (或 `--prepare-only`) | 离线跑通全部 `--selftest` 并预打 `cloud_train_pack.tar.gz` + `.sha256` 放桌面待命 |
| **本地等云机上线即秒传开训** | `START_CLOUD_TRAIN_NOW.cmd --track master-8b --host <HOST> --port <PORT> --follow --auto-deploy` | TCP+SSH 轮询上线（默认等 300s）➔ `sha256sum -c` 上传 ➔ `flock` 后台启动 ➔ 双阶看门狗 + 完成后真融合部署 |
| **云端 GPU 终端直接开训** | `bash cloud_train_pack/start_cloud_train_now.sh --track master-8b --bg` | 排他锁 + `fp16 torch.matmul` 探测(`/root/venv25`自愈) + `--selftest` ➔ 后台启动并做 8s 存活+`[FATAL]`探针 |

支持 `--track`：`master-8b`（默认主力 8.2B）、`13b`、`all90`、`worldmodel`、`safety`。凭据优先按 `CLI -> DAMODEL_* 环境变量 -> cloud_train_pack/.cloud_creds.json` 读取，源码零硬编码密钥。

---

## 1. 四条云端主线入口一览

| 产线 | 本地编排 / 准备脚本 | 云端执行脚本 | 目标交付物 | 本地真部署 / 验收 |
| :--- | :--- | :--- | :--- | :--- |
| **8.2B 主力 SFT 闭环** | `cloud_train_pack/local_one_click.py` | `cloud_train_pack/run.sh` -> `train_turnkey.py` | `virtu_lora_deliverable.tar.gz` + `.sha256` | `cloud_train_pack/deploy_trained_adapter.py` |
| **13.63B / 14B SFT+DPO** | `cloud_train_pack/dataset/build_phase2_targeted_corpus.py` | `cloud_train_pack/run_13b_evolution_train.sh` -> `train_cloud_virtu_13b.py` | `virtu_13b_deliverable_*.tar.gz` + `training_summary.json` | 同产线 Stage 5 `hf_to_gguf_numpy.py` + `Modelfile_virtu_13b` |
| **WorldModel / 物理修复** | `cloud_train_pack/local_one_click_worldmodel.py` | `cloud_train_pack/run_worldmodel_fix.sh` -> `train_turnkey_worldmodel.py` | `virtu_wm_lora_deliverable.tar.gz` | `deploy_safety_repair.py` / `scripts/_post_train_worldmodel.py` |
| **安全边界修复 (14 类)** | `cloud_train_pack/dataset/build_safety_boundary_sft.py` | `cloud_train_pack/run_safety_repair.sh` -> `train_safety_cloud.py` | `output/virtu_safety/merged` | `cloud_train_pack/deploy_safety_repair.py` |

---

## 2. All-90 全链路脚本 (`scripts/`, 对齐 `CLOUD_TRAINING_PLAN_ALL90_2026-11-13.md`)

1. `scripts/collect_six_trajectories.py`: 采集并归一化 SolidWorks / NX / AutoCAD / CIMCO / VERICUT / SSCNC 六大软件真实执行轨迹与溯源 SHA256。
2. `scripts/derive_trajectories.py`: 受控表层改写泛化（`<= 3x`），锁定工具参数与数字 100% 不变量并过全门禁。
3. `scripts/gate_all90_dataset.py`: 8 道自动化硬门禁（真实工具名 / System <= 702B / 去污染 / 量纲单位 / `wm_verifier` 物理重算 / 六软件覆盖与溯源 / SHA256 账本 / `+5%` 可证伪变异探针）。
4. `scripts/build_six_holdout_200.py`: 生成六大软件各 `n=200` 分层留出题集（90% 通过率对应 Wilson 95% 下界 `>= 0.85`），排除与训练集重合问题。
5. `scripts/train_dpo_all90.py`: 受控 DPO 阶段（`beta=0.1, lr=5e-6, epochs=1`），含基座门禁、偏好对完整性门与 `TimeBudgetCallback`。
6. `scripts/eval_all90_three_boards.py`: 三榜单联合验收（`raw_model >= 75`、`system >= 90`、`engineering >= 90`、`wilson_lb >= 0.85`、`system <= 702B`）与 `virtu_eval/provenance.py` 实测归因报告。

---

## 3. 快速上手与离线零 GPU 自检

开训前务必在本机先跑过所有离线门禁自检（不消耗云端 GPU）：

```powershell
# 主力 8.2B 全套离线门禁自检
.venv\Scripts\python.exe cloud_train_pack\train_turnkey.py --selftest
.venv\Scripts\python.exe cloud_train_pack\local_one_click.py --selftest
.venv\Scripts\python.exe cloud_train_pack\deploy_trained_adapter.py --selftest

# 13.63B 链路离线自检
.venv\Scripts\python.exe cloud_train_pack\train_cloud_virtu_13b.py --selftest

# All-90 6 个辅助脚本自检
.venv\Scripts\python.exe scripts\gate_all90_dataset.py --self-test
.venv\Scripts\python.exe scripts\collect_six_trajectories.py --self-test
.venv\Scripts\python.exe scripts\derive_trajectories.py --self-test
.venv\Scripts\python.exe scripts\build_six_holdout_200.py --self-test
.venv\Scripts\python.exe scripts\train_dpo_all90.py --self-test
.venv\Scripts\python.exe scripts\eval_all90_three_boards.py --self-test

# 门禁与反证单测套件
.venv\Scripts\python.exe -m pytest tests/test_master_cloud_gates.py tests/test_wm_cloud_gates.py tests/test_training_entrypoint_regressions.py tests/test_train_data_gate.py tests/test_physics_reference_honesty.py -v
```

### 一键云端开训 & 本地真融合部署

```powershell
# 1) 仅验证打包完整性与 SHA256 账本
.venv\Scripts\python.exe cloud_train_pack\local_one_click.py --pack-only

# 2) 一键上传并执行 7 阶段云端开训 (可选加 --auto-deploy 在 COMPLETED 后自动真合并上线)
$env:DAMODEL_PASS="你的云端SSH密码"
.venv\Scripts\python.exe cloud_train_pack\local_one_click.py --host <HOST> --port <PORT>

# 3) 独立执行真 Qwen3-8B LoRA 融合 -> GGUF Q4_0 -> Ollama 17 工具原生态部署与 4 项探针自证
.venv\Scripts\python.exe cloud_train_pack\deploy_trained_adapter.py `
  --deliverable checkpoints\virtu_master_lora_deliverable.tar.gz `
  --base checkpoints\_base_qwen3_8b `
  --tag virtu-master-fixed:latest
```

---

## 4. 硬性合规约束 (Fail-Closed)
- **基座血统锁定**：主力 8.2B 仅允许非 Instruct `Qwen3-8B` (`4096 / 36 / 151936`)，严拒 `Qwen3-8B-Instruct` 或 `Qwen2.5-7B` 错配；
- **单实例排他锁**：所有 5 个云端 `.sh` 脚本均启用 `flock -n 9` 与纯 Unix LF (`\n`) 行尾；
- **阶段门禁顺序**：Stage 0 CUDA `fp16` `torch.matmul` 实算探测 ➔ Stage 1 Ledger + 去污染 + 单位制审计 ➔ Stage 2 `--selftest` ➔ Stage 3 基座检查 ➔ Stage 4 20 步冒烟 ➔ Stage 5 `run_identity.json` ➔ Stage 6 全量训练 ➔ Stage 7 `sha256sum -c` + `COMPLETED` + 零语料漂移；
- **绝不覆盖已封缄模型**：Ollama 标签默认禁止覆盖已有版本（需换新标签或显式 `--allow-overwrite`），`TIME_BUDGET_STOPPED` 产物退出码固定为 `3` 且禁止验收部署。
