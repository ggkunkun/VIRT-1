# 世界工程模型全面修复报告（2026-11-11）— 第 2 轮云端修复链

口径：本文所有数字标 `measured`（本会话实跑命令产出）/ `asserted`（源码静态事实）/
`extrapolated`（由实测锚点外推）/ `未测`。遵守工作区「测量宪法」：不把源码字面量当测量结果，
每个新闸附「植入坏样本 ⇒ 必须红」的反证测试。

## 0. 范围与背景

被测对象 = WM 语料链（`scripts/build_wm_cloud_fix_corpus.py`）+ 两份 wm Modelfile 与在服标签 +
云端训练链（`cloud_train_pack/run_worldmodel_fix.sh`、`train_turnkey_worldmodel.py`、
`local_one_click_worldmodel.py`）+ 后端公式源（`virtu_real_backend` 主轴/切削速度）。

背景（11-09 第 1 轮云端重训实测）：几何概念与计算 T1 0→100%，但修复行为 T2 仅 33%；
深根因 = **改宣称不改参数**（模型把宣称值改成参考值却不改实际参数）。420 条经认证的多轮
修复轨迹（repairloop）当时已备好但**从未并入 WM 训练语料**。本轮目标：把全部可在本地修的
缺陷修掉，并把第 2 轮云端重训链写成可一键执行、硬门禁、可反证的交付件。

## 1. 缺陷清单与修复（6 项 live 缺陷）

| # | 缺陷 | 修复 | 口径 |
|---|---|---|---|
| ① | repairloop 深根因语料 0 行入集 | 并入 420 行，跨源精确去重，账本 v2 记 `repairloop_sha256/kept_rows` | measured |
| ② | Modelfile TEMPLATE 纯文本三段 vs 训练编码 ChatML（格式错配） | `build_wm_modelfile.py` TEMPLATE 改 ChatML，与训练器逐字拼接同源；重新生成 `checkpoints/virtu-wm-v3.Modelfile`（8295 B，SYSTEM 7941 chars） | measured |
| ③ | 在服标签与刷新后的 Modelfile 漂移（SYSTEM 4175 vs 7941 chars） | 注册**新标签** `virtu-wm-v3:chatml`、`virtu-13.63b:wm-v1-fixed`（旧标签原样封存，不覆盖证据）；`/api/show` 逐项比对 SYSTEM/template/参数 MATCH | measured |
| ④ | `PARAMETER num_gpu 30` 回归（11-07 已实测证伪：超配打崩服务） | 从 `modelfiles/virtu-13.63b.wm-v1.Modelfile` 移除；审计闸从「必查 num_gpu 30」**反转**为「禁止硬编码 num_gpu」 | measured |
| ⑤ | 云端链 v1 多处空转闸/假启动/环境撒谎 | `run_worldmodel_fix.sh` 全量重写 v2（§2）；训练器/编排器硬化（§2.3） | measured |
| ⑥ | 后端主轴/切削速度公式与定律真源不同源 | `tests/test_spindle_law_single_source.py` 把 `_spindle_speed_problem`/`_cutting_speed_problem` 钉到 `derivation.LAWS`，4×4×4 网格 + 突变反证（100×Vc、缺 π 必须差 >50%） | measured，3 passed |

另核实：`max(V,1)` 静默夹紧在 `build_worldmodel_v2.py:77` **已修复**（11-08 残留清单过期项，不重复修）。

### 1.1 语料重建（缺陷①）

`python scripts/build_wm_cloud_fix_corpus.py` 实跑产出（measured）：

- 输出 `cloud_train_pack/dataset/virtu_worldmodel_fix_sft.jsonl`：**4288 行**，
  sha256 `9ba15a85d512c4208cf8629b6c68684e79271b2fdb1b01f17248211abe3e5bed`
- repairloop 入集 **420 行**（源 sha `a7e43bb46dbc79d6…`，认证器 = closed_impeller_proctor.ruler，非模型）
- 跨源精确去重剔除 **3354 行**（独立复核：主源 7236→3882 唯一，重复集中在 general_sft 5817→2623；
  去重键含 `last_assistant_only`，不同掩码语义不会被合并）
- 硬泄漏剔除 14 行；三大评测集复核 `hard_leaks=0`；量纲坏行 0；遗留旧门禁字面量 0
- 坏草稿轮掩码 **407 轮**（loss=False → -100，反例不当正例训）

### 1.2 新标签冒烟（缺陷③，measured）

`virtu-wm-v3:chatml` 冒烟：主轴转速 `spindle_rpm=477.465` vs 解析值 477.5（相对误差 <0.01%）。
同时暴露**权重级缺陷**：`feed_rate` 推导把题面 z=4 误绑为 n —— 这正是本轮重训要修的行为，
契约层已修、权重层待训。

## 2. 云端修复链 v2（缺陷⑤）

### 2.1 入口脚本 `run_worldmodel_fix.sh`（7 阶段，全部硬闸）

| 阶段 | 内容 | 失败行为 |
|---|---|---|
| 锁 | `flock` 单实例锁 `.wm_train.lock` | 第二条链直接拒绝（测量链独占） |
| 0 | `nvidia-smi` GPU 事实 | — |
| 环境 | **真实 fp16 matmul 探针**（`is_available` 会撒谎：cu13x 无 sm_70 内核）+ 训练依赖探针；失败自动建 venv25（torch 2.5.0+cu124，aliyun pytorch-wheels 镜像），系统环境 CUDA 可用但缺依赖时先原位补齐 | 重建后探针仍失败 ⇒ FATAL |
| 1 | 语料 sha ↔ 账本；`repairloop_kept_rows>0`；**包内 repairloop 源指纹复核** | 任一不符 ⇒ 拒绝开训 |
| 2 | 契约键名全覆盖 + 闸门归一 + `wm_verifier.selftest()`（14 项含反证）+ 训练器四重门禁 `--selftest` | 任一红 ⇒ 停 |
| 3 | 基座身份闸：路径/config 含 Instruct ⇒ 拒绝（本尊基座必须 Qwen3-8B） | FATAL |
| 4 | **20 步冒烟**进独立 `${OUT_DIR}_smoke`，回执必须 COMPLETED 且 loss 有限 >0 | 不过不开正式训练 |
| 5 | `run_identity.json`：语料/训练器/入口 sha256 + GPU，供回收侧漂移核对 | — |
| 6 | 正式训练（`-u` 无缓冲），`TimeBudgetCallback` 预算护栏 | 超预算 ⇒ 回执 `TIME_BUDGET_STOPPED` |
| 7 | 交付 tar + 回执存在；`sha256sum -c` **硬校验**（v1 的 `\|\| true` 已删）；回执必须 COMPLETED；回执语料指纹 ↔ 开训时一致（期间被改 ⇒ 该腿作废） | 任一红 ⇒ 非零退出 |

默认超参（第 1 轮已验证配方）：EPOCHS=2.5、LR=1e-4、BATCH=2、GRAD_ACCUM=8（全局 batch 16）、
MAX_LEN=2560、MAX_HOURS=2.0、USE_QLORA=0（V100-32GB 走全量 fp16 LoRA，实测 ~22GB 显存；
bnb 在 cu13x 无内核，QLoRA 仅显式开启时才装）。

### 2.2 本地预演揪出的两个真 bug（已修，measured）

v2 初稿在本地解包预演中被打红两处，证明「写完 ≠ 能跑」：

1. Stage 2 调用了**不存在的** `wm_contract.guard_and_correct`（幻影 API）⇒ 改为真实 API：
   `V.recompute` fea_fos 钉（235/198 必须判 fail）+ 键名覆盖 + `V.selftest()`（返回 0/1）。
2. Stage 7 `sha256sum -c` 从 SCRIPT_DIR 执行，而 `.sha256` 写的是裸文件名、交付件在 OUT_DIR
   ⇒ 必然「找不到文件」。改为 `cd` 进交付目录再 `-c`。

### 2.3 训练器与编排器硬化

- `train_turnkey_worldmodel.py`：候选基座路径删除 Instruct 变体；`assert_base_identity()`；
  `--selftest` 走 `tokenizer_only=True`（ModelScope 只拉 tokenizer，不拉 16GB 权重）；
  QLoRA 时 `import bitsandbytes` 前置 fail-fast；回执 schema v2 增
  `torch_version/device_capability/epochs_requested/max_steps_requested/stopped_by_time_budget`，
  **`status` 区分 COMPLETED / TIME_BUDGET_STOPPED**（预算停机 ≠ 完成）。
- `local_one_click_worldmodel.py`：
  - `safe_extract()`：拒绝路径穿越/绝对路径/符号链接成员（tar.extractall 默认不设防）；
  - `verify_deliverable_receipt()`：部署前硬闸，只认 COMPLETED + 双指纹齐全；
  - 回收前先远程 `cat` 回执预检，非 COMPLETED **拒绝下载**；远端 `.sha256` 缺失 ⇒ FATAL；
    本地 sha 硬比对后才解包；
  - `upload_and_start()`：`echo LAUNCHED_PID=$!` + 8 秒后 `pgrep` 存活 + 日志头 30 行 FATAL 扫描，
    无进程/早夭 ⇒ 抛错（拒绝假启动）；
  - 打包新增 repairloop 源 + 其账本入包（云端可独立溯源）。

## 3. 反证闸门（测量宪法 §4，measured）

`tests/test_wm_cloud_gates.py`：**22 passed**。被测函数一律从源文件 AST 抽取执行（测的是真源码），
Stage 1 闸直接从 sh 抽取 heredoc 执行（单一真源防复制漂移）：

| 闸 | 植入的坏样本 | 结果 |
|---|---|---|
| verify_deliverable_receipt | 缺回执 / TIME_BUDGET_STOPPED / 缺指纹 | 3 红 1 绿 |
| safe_extract | `../evil` 穿越 / 绝对路径 / 符号链接 | 3 红 1 绿 |
| Stage 1 账本闸 | sha 漂移 / repairloop=0 / repairloop sha 漂移 / 源文件缺失 | 4 红 1 绿 |
| assert_base_identity | 目录名 Instruct / config Instruct | 2 红 1 绿 |
| TimeBudgetCallback | 超预算 | 必须置 budget_stopped+stop+save，回执不得 COMPLETED |
| build_corpus | repairloop 源缺失 | FileNotFoundError（fail-closed） |
| modelfile_audit | 纯文本模板 / 硬编码 num_gpu 30 | 2 红 1 绿 |

## 4. 验证汇总（全部 measured，本会话实跑）

| 项 | 结果 | 命令 |
|---|---|---|
| shell 语法 + LF | OK，CRLF=0 | `bash -n cloud_train_pack/run_worldmodel_fix.sh` |
| 五个改动 py 编译 | OK | `py_compile` |
| 打包 | 3.13 MB / 25 成员，sha `309d83ce0f75f4fb…` | `local_one_click_worldmodel.py --pack-only` |
| 解包预演 Stage 1 | rows=4288 repairloop=420，源指纹核验通过 | 解包至 scratch 后执行真 heredoc |
| 解包预演 Stage 2 | 14/14 PASS | 同上 |
| 解包预演训练器 selftest | usable=4288/4288（train=4159/eval=129），hard_leaks=0×3 套件，unit bad=0，legacy=0，truncated=315（保尾），max_tokens=2560 | `train_turnkey_worldmodel.py --selftest`（在解包目录内） |
| 只读审计 | **28/28 PASS** | `scripts/wm_audit_full.py` |
| 核心物理四套 + 主轴钉 | **191 passed** | pytest（solver_graders/physics_case_set/derivation_registry/physics_reference_honesty/spindle_law） |
| 反证闸 | **22 passed** | `tests/test_wm_cloud_gates.py` |
| GPU 阶段（冒烟/正式训练） | **未测** | 需租 V100；本地无 sm_70 |

## 5. 执行入口与成本（extrapolated，锚点为第 1 轮实测）

```bash
# 1) 租 V100-32GB（第 1 轮同款实例即可），凭据只经文件/环境变量交接，不进聊天
# 2) 本地一键：打包 → 上传 → 开训 → 流式日志 → 回收 → 硬校验
python cloud_train_pack/local_one_click_worldmodel.py --host <HOST> --password <从凭据文件读>
#    或分步：--pack-only / --fetch-only / --auto-deploy
```

成本外推（锚点：第 1 轮 357 步 ≈ 58 min，measured ⇒ ~9.75 s/步含评估开销）：

- 步数 = 4159 train × 2.5 ep / 16 = **650 步**（extrapolated）
- 正式训练 ≈ 650 × 9.75 s ≈ **106 min**；冒烟 20 步 ≈ 3–5 min；环境/基座开销 ≈ 10–20 min（预估）
- 总计 ≈ **2.1–2.3 h × ¥1.98/h ≈ ¥4.2–4.6**；MAX_HOURS=2.0 只护栏训练阶段，超预算回执
  TIME_BUDGET_STOPPED，回收侧拒收，不会静默部署半程权重。

验收边界（用户既定）：回传 LoRA → 本地合并/量化/注册**新标签** → 对基线复评 →
**删除云凭据文件并释放实例**。复评重点：T2 修复行为（第 1 轮 33%）、z→n 绑定、宣称=参数一致性。

## 6. 残留（权重级，待第 2 轮重训验证）

1. T2 修复行为 33%（11-09 measured）——repairloop 420 条已入集，本轮重训的直接目标。
2. `feed_rate` 推导 z→n 误绑（11-11 冒烟 measured）。
3. 「改宣称不改参数」（11-09 capstone measured：u2 宣称 513.8 / 实 453）——契约压不住，
   靠 repairloop 中 claim_mismatch 模式 36 条 + 首轮坏解 loss=False 掩码从训练侧修。

以上三项**不作已修复宣称**；本轮交付的是「本地可修项全修 + 可执行可反证的云端重训链」。