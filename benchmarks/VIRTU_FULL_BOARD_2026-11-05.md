# Virtu 全量板实测报告（2026-11-05）

- 测评目录：`runs/eval/fullboard_20261105_0930/`（每条腿有 `manifest.json` + `raw.jsonl` 逐题证据）
- 采样口径：`temperature=0`、`seed=1234`、`num_ctx=8192`、`--token-floor 512`
- 判分器：`virtu_eval/graders.py`，本轮离线重评用的 sha256 前缀 `a4ba0c78`（原始落盘分与重评分两栏都留着）
- 修复与门禁变更见 `benchmarks/VIRTU_EVAL_HARNESS_FIXES_2026-11-05.md`

## 1. 被测身份（这是本报告能不能被引用的前提）

| 名称 | 权重层 sha256 前缀 | 权重字节 | template 层 | system 层 | 状态 |
|---|---|---|---|---|---|
| `qwen3:8b`（基座对照） | `a3de86cd1c132c82` | 5,225,374,496 | `ae370d884f108d16`（含 `.Tools/.ToolCalls`） | — | 在库 |
| `virtu-comprehensive:latest` | `c3b78c7735c9ac1f` | 4,614,297,600 | **09:44 = `af2b8fe4710f8eae`／10:4x = `53e6e1ca3b6cbb00`** | **09:44 = `720ab572ee755318`／10:4x = `9f4faa44ed3d2528`** | 在库，**标签被别的会话在腿间重新指过** |
| `virtu-master:latest` | `c3b78c7735c9ac1f` | 同上 | 10:4x = `53e6e1ca3b6cbb00` | 10:4x = `9f4faa44ed3d2528` | 与 comprehensive **逐层同哈希** |
| `virtu-ties-v1:latest`（10:3x 重建） | `c3b78c7735c9ac1f` | 同上 | 同上 | 同上 | **名字回来了，字节不是历史 ties_v1**（历史 GGUF 只剩 receipt，`4,614,301,760 B` ≠ `4,614,297,600 B`） |
| `virtu-test-tool:latest` | `c3b78c7735c9ac1f` | 同上 | 同上 | 同上 | 同一manifest 的第 4 个别名 |
| `virtu-frozen:comp_v5`（本轮新建） | `c3b78c7735c9ac1f` | 同上 | `53e6e1ca3b6cbb00` | `9f4faa44ed3d2528` | 由我创建并**逐层核验等于当刻部署标签**，后续腿只测它 |

两条硬结论：

1. **"同权重双脚手架消融"作废**。原本 `comprehensive` 与 `master` 只差 template/system 两层，可测"分数里有多少是提示词撑的"；10:4x 两标签连同 `virtu-ties-v1`、`virtu-test-tool` 变成**同一 manifest 的别名**，这一对对象不复存在。
2. **在共享 Ollama 库上，按标签名引用分数是不可证伪的**。因此本轮所有补测只打 `virtu-frozen:comp_v5`，且每条响应由臂自带 `served_layers`（`virtu_eval/arms.py`，测试 `tests/test_ollama_arm_identity.py`）。

## 2. 工具通道：训练产物不支持原生工具调用（实测）

| 探针 | 结果 |
|---|---|
| `virtu-comprehensive:latest` 不带 tools | 200，`done_reason=length` |
| `virtu-comprehensive:latest` 带 tools | **HTTP 400 `registry.ollama.ai/library/virtu-comprehensive:latest does not support tools`** |
| `qwen3:8b` 带 tools | 200（模版含工具分支） |
| 生效 chat template | 156 字符的 `{{ if .System }}…{{ if .Prompt }}…` 老式单轮模版，无工具分支；`qwen3:8b` 的是 1723 字符含 `.Tools/.ToolCalls` |
| 该构件的 system 自述 | 「只输出一个标准 JSON 对象 `{"tool","arguments"}`，键名必须是 tool 与 arguments，严禁使用 name 键」 |

⇒ 它被**设计**成走 JSON 文本协议，但当时 Ollama 层的原生工具不可用；历史一代（`virtu-ties-v1`/`virtu-toolcall`/`v3-all90`）能出 toolcall 分（83–91），说明这条能力在 v5/comprehensive 的导出环节一度回归了。

**时间界（重要）**：这条结论只对 09:5x 的字节成立。11:2x 复核，标签又被换过：`virtu-frozen:comp_v5` 与两个部署标签的 template 层分别是 `53e6e1ca3b6cbb00` / `bdae0a81055c0aa2`，且对 tools 请求**不再回 400**（同一次探测里 `virtu-comprehensive`、`virtu-master` 均已换 system 层）。⇒ "支持/不支持工具"是**按层哈希、按时刻**的事实，不是标签的属性；本表下面那条腿的 30 条 toolcall 里有 19 条是原生 tool_calls，用的就是冻结标签那份 10:47 的 template。
⇒ 我的 board7 腿里 toolcall 30 条全是同一 400，正是这条事实的落盘证据；**但那份证据文件本身也没保住**：11:1x 复查同一目录变成 210 行、0 传输错误、toolcall 有分（78.16），无重复 case_id ⇒ 是**整体改写而非追加**（原 30 条 404 记录已不可复核）。这条正是封缄机制（`provenance.seal_leg/verify_seal`）存在的理由，也意味着该目录的分数按新规一律不发布。
⇒ harness 现已改为**探测到即降级为 JSON 文本协议并在该行标 `tools_dropped_for_json_protocol`**，不再把 30 条打成传输失败。

## 3. 已实测分数

**发布纪律（本节自我约束）**：可发布的数只有一处来源——`runs/eval/fullboard_20261105_0930/report_tables.md`，由 `virtu_eval/provenance.py` 闸门生成（要求逐行 `served_layers` 身份戳 + 封缄 + 行数等于计划用例数 + 传输率 ≤5%）。下面 §3.1–§3.3 的数字产自闸门上线**之前**的腿，按自己的新规**只能算存档，不算本轮发布**；把它们留在这里是为了让"漂移了多少"可核对，引用时必须带本段说明。

**11:2x 首次出数**（`make_tables.py` 经闸门生成，全文见 `runs/eval/fullboard_20261105_0930/report_tables.md`）：

| 维度 | 值 | 口径 | n | 证据 | run_id |
|---|---|---|---|---|---|
| reasoning | **62.35** | 实测 | 30 | `board7__frozen_comp_v5__v4/raw.jsonl` | `dde13885346d93ff` |
| knowledge | **69.67** | 实测 | 30 | 同上 | 同上 |
| instruction | **77.43** | 实测 | 30 | 同上 | 同上 |
| generation | **71.65** | 实测 | 30 | 同上 | 同上 |
| generalization | **56.42** | 实测 | 30 | 同上 | 同上 |
| boundary | **61.33** | 实测 | 30 | 同上 | 同上 |
| toolcall | **79.76** | **部分覆盖 28/30** | 28 | 同上 | 同上 |

被测字节：`virtu-frozen:comp_v5`，权重层 `c3b78c7735c9ac1f`（4,614,297,600 B）、template `53e6e1ca3b6cbb00`、system `9f4faa44ed3d2528`；210 条响应逐条带 `served_layers`，腿目录已封缄（`_seal.json`）。

在此之前的全部数字（含 §3.1–§3.3）都是**存档**：这台机器上今天此前没有一条可归因的全板分数——这不是修辞，是 `published=0 refused=8` 的闸门输出。基座对照腿 `board7__base_qwen3_8b` 于 11:19 起跑，跑完前本报告**不给任何增益结论**。

### 3.1 【存档】文本 7 维板，`virtu-comprehensive`（n=30/维，采样 09:25–09:48，当时 system 层 `720ab572`）

| 维度 | n | 分 | 满分率 | 截断 |
|---|---|---|---|---|
| reasoning 推理 | 30 | **54.74** | — | 0 |
| knowledge 知识 | 30 | **61.67** | — | 0 |
| instruction 指令 | 30 | **54.88** | — | 1 |
| generation 生成 | 30 | **75.82** | — | 0 |
| generalization 泛化 | 30 | **46.94** | — | 1 |
| boundary 边界 | 30 | **72.50** | — | 1 |
| toolcall 工具 | 0/30 | **不可测**（§2，整腿 400） | — | — |

- 该腿 `report.gate()` 判 **INVALID**（30/210 = 14.3% 传输错误 > 5%）——这是刻意的：分数不得由一条含 30 个"模型从未被问到"的腿发布。上表只报 6 个测到了的维度。
- **不给单一加权综合分**：toolcall 缺位时 `DIM_WEIGHTS` 归一出来的 60.89 与历史 8 维分不是同一把尺，并列会诱导误读。

### 3.2 【存档】物理两把尺（`virtu-master` 权重=同 §1，n=30/维，采样 09:48–09:59）

| 维度 | 分（重评后） | 说明 |
|---|---|---|
| `physics`（求解器复算+守恒） | **49.33** | `world_state_verified` 逐字段与 `wm_verifier.recompute` 比对 |
| `derivation`（定律+变量绑定） | **40.42** | 定律对但数算错与两头都错分开计（口径见 11-04 报告） |

- 判分器在 10:23 被另一会话改动过：这一腿有 **11/60 条分数被重评改写**（`derivation-e02/e03` 0→62.5、`derivation-m01/m02` 0→12.5 等）。⇒ 11-04 报告里"定律绑定 17/30"这类数字与新尺**不可直比**，引用时必须带 grader sha。

### 3.3 【存档】部分覆盖（不足以出结论，只作进度记录）

| 腿 | 条数 | 状态 |
|---|---|---|
| `board7/base_qwen3_8b` | 15/210 | 因子会话在 10:2x 提交新 commit（`git_sha` 是续跑指纹的一部分）而被拒续跑 → rc=1 |
| `board4/master_scaffold` | 9/120 | 子进程被外部杀死 rc=-1 |
| `board7/ctrl_qwen25_7b` | 20/210 | 上一版链被终止 |

### 3.4 冻结证据（另一会话 21 臂 screening，n=8/维，**不可复现**）

`virtu-v3-all90` 80.78 > `virtu-v2-all90` 71.15 > `virtu-ties-v1` 69.21 > `virtu-toolcall` 61.03 > `virtu-wm-v3` 60.70 > `qwen2.5:3b` 26.62。
构件 GGUF 已不在盘上（`deploy_and_cleanup.py` 删库），这些标签现在是别名或不存在；`qwen2.5:1.5b`、`virtu-eval:delta5` 两批已被改判为无效（`status=completed_with_invalid_arms`）。

## 4. 在跑与待补

`run_chain4.py`（后台）：`frozen_comp_v5` 与 `qwen3:8b` 各跑 board7(210) + toolrouting(30) + phys(60)，视觉腿跑 multimodal(30)。
基座臂慢是实测事实（同一 host 上 comprehensive ≈6.6 s/条，qwen3:8b ≈40–77 s/条：5.2 GB 权重 27%/73% CPU-GPU 卸载 + 长答在 512 预算处截断），不是故障。

## 5. 覆盖边界（不得被当成"六软件闭环已测"）

- 240 条 v1 板里 **FOS/安全系数/von Mises/应力/强度/有限元 = 0 条、钣金套料 = 0 条、SSCNC 只有 6 条中文提及**；CAE 那一面目前由 `virtu_eval_phys_v1` 的 3 条 `fea_fos` 撑着。
- 新增 `data/benchmark/virtu_eval_cl_v1/toolrouting.jsonl`（30 条，`validate_cases` 全 100）把运行时 14 个 `cadcam_*` 中此前 **0 gold** 的四个（`extreme_chain/universal_geometry/cae_stress_analysis/sheetmetal_nest`）纳入可判分路由；闸在 `tests/test_closed_loop_coverage.py`（反向探针：只看旧板必须报 4 个未覆盖）。
- 结果级判据本机给不出、因此**明写不测**的三处：排料利用率/干涉（无确定性嵌套 oracle）、VERICUT Auto-Diff 红蓝绿（COM 通道已判死）、SSCNC 面板/CRT 读值（无 COM，只能读屏）。账本 `COVERAGE.json`，测试要求它至少承认 3 个"结果不可测"阶段。

## 6. 复跑命令

```bash
# 单臂全板（冻结标签，当前尺子）
.venv/Scripts/python.exe virtu_eval/runner.py \
  --arms-config runs/eval/fullboard_20261105_0930/r4_frozen_comp_v5_<hhmmss>.json \
  --arm frozen_comp_v5 --case-dir data/benchmark/virtu_eval_v1 \
  --out-dir runs/eval/fullboard_20261105_0930/board7__frozen_comp_v5__v4 \
  --dims reasoning,knowledge,instruction,generation,generalization,boundary,toolcall \
  --temperature 0 --seed 1234 --token-floor 512

# 离线重评（不重问模型，落 regrade_summary.json）
python runs/eval/fullboard_20261105_0930/regrade.py

# 用例自检 / 泄漏 / 量纲 / 工具面
python -m virtu_eval.validate_cases data/benchmark/virtu_eval_cl_v1
python virtu_eval/contamination_check.py data/sft/virtu_evolution_v5.jsonl
python scripts/corpus_unit_audit.py data/sft/virtu_final_train.jsonl
python virtu_eval/tool_schema.py
```

## 7. 这份报告里不许被引用的东西

1. `checkpoints/COMPREHENSIVE_EVAL_REPORT.md` 的 `52.02` 与"物理合规率 100%（否决项）"——云端未量化权重、单轮无 schema 的另一把尺，且 100% 是源码字面量（已改，见修复台账 §3）。
2. 任何"训练带来 X 分增益"的话，直到 §4 的基座腿跑完且**两臂同尺同 grader**为止。
3. 以 `virtu-ties-v1` 名义发布的任何新分数——那个名字现在指向 v5 权重。
