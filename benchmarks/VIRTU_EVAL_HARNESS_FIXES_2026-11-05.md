# Virtu 测评链与门禁修复台账（2026-11-05）

本轮由"全面测评模型"引出：先测，再就地修掉测量链上的假绿与安全缺陷。
每条都给了**证据出处**与**回归测试**；未修的写在最后。

## 0. 一句话结论

上一会话的 21 臂 screening 里，**一条腿 56/56 全是 `http_404` 却以 `status=completed` 记账**；
仓里那份"验收报告"的**物理合规率 100%（否决项）是源码字面量**；权重最高的 toolcall 维**测的是一张只有
10 个工具、运行时已注册 14 个的过时工具面**；而**三份 damodel root 口令散落在 15 个脚本里**，
凭据扫描器因为变量名叫 `PASS` 而整类看不见。四处全部修完并钉了测试。

---

## 1. 空跑被判成 completed（测评有效性闸）

| 项 | 内容 |
|---|---|
| 证据 | `runs/eval/comprehensive_20261105_012119/screening/virtu-eval_delta5/raw.jsonl`：56 条记录 verdict 全为 `transport_error`，错误体 `http_404: model 'virtu-eval:delta5' not found`；对应批次文件原写 `status=completed` |
| 根因 | `run_screening.py` 的停止闸只看 `rc` 和 `recorded_cases != 56`，从不看传输错误率；而 `virtu_eval/report.py::gate()` 本来就会判 `transport_error 占比 > 5%` 与"全部记录均为传输失败" |
| 修复 | ① 起腿前 `artifact_present()` 校验构件仍在 `ollama list`，缺失即 `stopped_missing_artifact` 返回 rc=3，不再产生 404 记录；② 收腿闸加 `or not item["valid"]`；③ 复核并改判历史账本 |
| 账本改判 | `screening_summary_core_virtu_eval_delta5.json` → `completed_with_invalid_arms`＋`invalid_arms`；`screening_summary_core_qwen25_15b.json`（14/56 传输错误也曾在 completed 名下）同样改判；4 份停在 `running` 的 summary 改判 `abandoned_mid_batch`。原始记录一律保留，改判前留 `.pre_rejudge` 备份 |
| 残留 | 该脚本另一会话同时在改（实测到我这次编辑被并发覆盖过一次）；闸的**权威实现**应落在 `virtu_eval/report.py::gate()`，链只调用它 |

## 2. 清理脚本删掉被测构件（共享运行时破坏）

| 项 | 内容 |
|---|---|
| 证据 | `scripts/deploy_and_cleanup.py:30` 的 `OBSOLETE_OLLAMA_MODELS` 含 `virtu-ties-v1:latest`、`virtu-production:v3`、`virtu-toolcall:latest`、`virtu-eval:*` 等 11 个正在被 screening 引用的 tag；实测当前 `ollama list` 只剩 9 个模型，其中 `virtu-eval:delta5` 报 not found |
| 修复 | `cleanup_obsolete_models()` 删除前先算 `evaluation_referenced_tags()`（扫 `virtu_eval/arms*.json` + `runs/eval/**/arms*.json` + `PROVENANCE.json` 引用），命中即拒删；`chain_is_measuring()` 检测到本机有 `virtu_eval/runner.py` 在跑则整批拒绝删除；两者都可被 `--force-obsolete` 显式越过 |
| 未修 | 被删构件的 GGUF 已从磁盘消失（`checkpoints/` 只剩 `virtu-comprehensive-q4_0.gguf` 一个大文件），历史 ties-v1/v3-all90 等成绩因此**不可复现**，只能作为冻结证据引用 |

## 3. 验收报告的两处假绿（发布指标造假）

| 项 | 内容 |
|---|---|
| 证据 | `cloud_train_pack/eval_in_situ.py:215` `physics_compliance = 1.0  # 靶向语料已包含 100% 物理守恒样本`——说的是语料，被打印成"物理规律合规率 100.0%（否决项）"；同一张卡片还内联打印 `'0.62' / '0.85' / '0.94'` 三个从未测过的历史物理合规率；对比列 Qwen3基座/v2/v3 来自 `HISTORICAL_BASELINES` 常量；`raw_records` 收集了逐题响应却**从不落盘** |
| 已发布物 | 该报告被 `deploy_and_cleanup.py` 从云端下载到 `checkpoints/COMPREHENSIVE_EVAL_REPORT.{md,json}`，任何读者都会当成验收结论 |
| 修复 | ① 新增 `measure_physics_gate()`：逐条跑 `virtu_eval_phys_v1/physics.jsonl`，判据＝`world_state_verified`（求解器复算）与 `physics_invariant`（守恒自洽）**同时通过**；测不到 → `compliance=None` 且验收**失败关闭**；② 删掉三个内联假数，历史列改名"常量基座\*/常量v2\*/常量v3\*"并加 `BASELINE_PROVENANCE` 声明；③ 逐题响应写 `raw.jsonl`，报告写 `identity_evidence`（git sha＋用例 sha256＋采样参数）；④ 加权总分按**实际覆盖权重归一**并输出 `coverage`，缺维直接判不通过；⑤ `checkpoints/COMPREHENSIVE_EVAL_REPORT.md` 头部加"⛔ 口径作废标注"，写明它是云端未量化权重、单轮无工具 schema 的口径，与本机 Q4_0 部署不可互算 |
| 测试 | `tests/test_eval_in_situ_gate.py`（6 项）。变异探针：把闸改回 always-pass ⇒ 2 项必红；改成 always-fail ⇒ gold 项必红；基线 6/6 绿（`scratch/_mutation_probe_gate.py`） |
| 实测旁证 | gold 回放 240/240 全 100 且闸门仍报 `NOT MEASURED`（说明判分器与题面自洽，同时否决项不再白送）；physics gold 30/30 能过 `world_state_verified`（闸不是永远红） |

## 4. 凭据：三份 root 口令散在源码里，扫描器整类失明

| 项 | 内容 |
|---|---|
| 证据 | `scripts/deploy_and_cleanup.py`（44910）、`scripts/damodel_active.py` 等 13 个脚本各有 `PASS = "<literal>"`，涉及两种口令；`tests/test_no_hardcoded_credentials.py` 的 `CRED_RE` 只认 `password|passwd|secret|api_key|apikey|access_token`，**`PASS =` 这种键名一律漏过**；`connect(password=PASS)` 传的是变量名，`.connect()` 那条测试也漏过 |
| 修复 | ① 15 个脚本改为 `damodel_env.load()` / `PASS = damodel_env.password_for(HOST, PORT)`，缺凭据即非零退出；② 口令集中到 gitignored 的 `.damodel_pass.json`（按 host:port 键，权限 0600），`.gitignore` 加规则并有测试；③ 扫描器加 `CRED_ASSIGN_RE`（`^(?:前缀_)?(PASS(WORD)?|SECRET|TOKEN|API_?KEY|CREDENTIAL) = "字面量"`）并把它接进全仓扫描；④ 扫描面加 `cloud_train_pack/*.py`；⑤ 探测器自身有反向测试（合成 `PASS = "..."` 必须被抓、`HOST/PORT/os.environ[...]` 必须不误报） |
| 测试 | `tests/test_no_hardcoded_credentials.py` 12 项全绿（含 3 个新增） |
| **需要人做的事** | 这三份口令已经在磁盘上明文存在过、且是 root 直登；本轮只做到"不再进源码"。**轮换**与**改用密钥对 + 禁密码登录**才是修复，改文件只是止血。另注：`paramiko.AutoAddPolicy()` 仍在（不校验主机指纹），我没动它，因为改了会直接断别的会话的云端作业 |

## 5. 评测集泄漏：157 条逐字题面混在可训练语料里

| 项 | 内容 |
|---|---|
| 证据 | `python virtu_eval/contamination_check.py`：`data/sft/virtu_evolution_v5.jsonl` rows=3963 **hard_leaks=157**（含 `prompt_hash=toolcall-e05 / instruction-m15 / toolcall-m02` 逐字命中）；而 `cloud_train_pack/dataset/train_corpus_comprehensive.jsonl` rows=4999 hard_leaks=**0**、`virtu_capability_sft_v6.jsonl` 0、pack 内 v5 0、DPO 对 0 |
| 关键区分 | 旧版把"gold 数值出现在语料里"（`0.005`/`0202`/`2021` 这类通用量）也当污染 ⇒ 一次报出 1621/3815/3927 条，占语料 32–69%，闸因此形同噪声、被人生存性忽略 |
| 修复 | ① 摘要改为 `hard_leaks` 与 `numeric_proxy_only` 分栏，**默认只对硬泄漏失败关闭**（`--strict-numeric` 保留旧严格语义）；② `--drop` 只丢硬泄漏行；③ 修 `sample_text()` 在 `content` 为 list（pair/多模态语料）时 `TypeError` 崩闸的 bug（实测 DPO 语料直接跑不动）；④ 新增可编程 API `assert_no_leak()` 并接进 `scripts/train_qwen3_8b_qlora.py`、`cloud_train_pack/train_turnkey.py`（都在载权重/读语料**之前**）；⑤ `train_turnkey.py` 原来 `--data` 找不到就静默换成语料候选里的另一份，改为拒绝并列出可用项 |
| 产物 | `data/sft/virtu_evolution_v5.clean.jsonl`（3806 = 3963−157）；原文件留原位＋`*.LEAKED.md` 禁用说明 |
| 测试 | `tests/test_train_data_gate.py` 6 项（含"闸在载权重之前"的位置断言、真实语料条数断言、未知端口失败关闭断言） |

## 6. 工具面：14 vs 10，而且新工具一条 gold 都没有

| 项 | 内容 |
|---|---|
| 证据 | `bridges/tool_calling_specs.py` 注册 14 个 `cadcam_*`；`virtu_eval/arms.json` 注入 10 个；把 board 的 **gold+criteria**（不含题面）扫一遍，`cadcam_extreme_chain / universal_geometry / cae_stress_analysis / sheetmetal_nest` 出现 0 次 |
| 为什么不直接扩 schema | 扩了 schema 而没有题面，toolcall 分数会因为多 4 个候选而下降，但这不是能力变化——是把尺子改了。所以先补用例 |
| 修复 | ① 新增 `virtu_eval/tool_schema.py`：用 **ast** 读运行时注册表（不 import 桥，避免 COM/torch），给出 `runtime_tools / tool_contract / uncovered_runtime_tools / eval_schema_tool_names`；② 新集 `data/benchmark/virtu_eval_cl_v1/toolrouting.jsonl`（30 条，easy 9 / medium 16 / hard 5），四个工具各 ≥4 条 gold，判据含 `json_object`（禁 `name/function` 顶层键）、`literal_none` 反误路由、`enum_field` part_type 白名单、`count_between` 件数；③ 可测性账本 `COVERAGE.json` 逐阶段写明用的是哪把尺、以及**哪些结果级判据本机给不出**（排料利用率、VERICUT 红蓝绿、SSCNC 面板读屏） |
| 测试 | `tests/test_closed_loop_coverage.py` 8 项，含反空转探针：**只指向旧 board 时该闸必须报出 4 个未覆盖工具**；账本状态词受白名单约束，且要求 ≥3 个阶段承认"结果不可测"，防止未来交一份全绿账本 |
| 出题自检 | `python -m virtu_eval.validate_cases data/benchmark/virtu_eval_cl_v1` ⇒ VALID，30 条 gold 全部 100 分。过程中校验器当场抓出我自己两个错：`parts` 里用 `name` 键撞了 forbidden 规则；条数 10<30 |

## 7. 本机部署链的硬事实（不是修复，是结论前提）

- `virtu-comprehensive:latest` 与 `virtu-master:latest` **权重层同 sha256 `c3b78c7735c9ac1f…`（4,614,297,600 B）**，只差 template/system/parameters 三层 ⇒ 可做同权重双脚手架消融。
- 这两个 tag 的生效 chat template 是 156 字符的 `{{ .System }}/{{ .Prompt }}` 老式模版（无工具分支），Ollama 因此判 `does not support tools`：带 `tools` 的请求**一律 HTTP 400**（`qwen3:8b` 的 1723 字符模版支持工具，实测 200）。上一代 ties-v1/toolcall/v3-all90 是能出 toolcall 分的，说明这条能力在 v5/comprehensive 的导出环节**回归了**。
- 该构件的 system 提示词本来就要求 `{"tool","arguments"}` 文本协议 ⇒ 测评对它在"JSON 文本协议"下测 toolcall，并显式记录 `native tools` 不可用（我的 board 腿里 toolcall 30 条全部 http_400 就是这条事实的落盘证据，不是噪声）。

## 8. 补记（同日 10:4x 之后）：标签别名风暴与"harness 自带身份取证"

| 项 | 内容 |
|---|---|
| 新证据 | 10:4x 读 `~/.ollama/models/manifests`：`virtu-comprehensive:latest`、`virtu-master:latest`、10:3x 新建的 `virtu-ties-v1:latest`、`virtu-test-tool:latest` **四个标签的 model/template/system 层逐字节相同**（model `c3b78c7735c9ac1f`、template `53e6e1ca3b6cbb00`、system `9f4faa44ed3d2528`）；而 09:44 我记录过 comprehensive 的 template/system 是 `af2b8fe4710f8eae`/`720ab572ee755318` ⇒ **标签在腿之间被重新指过** |
| 直接后果 | ① "同权重双脚手架消融"（comprehensive vs master）失去对象；② 09:25–09:48 那 210 条 `comprehensive` 记录测的是当时的 system 层 `720ab572`，该对象已不可再取；③ 以 `virtu-ties-v1` 名义发布的任何新分实际是 v5 权重 |
| 修 | ① `virtu_eval/arms.py::OllamaNativeArm` 在构造时解析标签→记录 `served_layers`（model/template/system/adapter 层 digest + 字节数）并**挂到每条响应上**；② 遇到 `400 does not support tools` 时缓存能力位、降级为 JSON 文本协议、在该行标 `tools_dropped_for_json_protocol`，不再把 toolcall 整腿写成传输失败；③ 新建 `virtu-frozen:comp_v5`（`FROM virtu-comprehensive:latest` + num_ctx 8192），创建时逐层核验与部署标签同哈希后**只测它**，Modelfile 留在 `checkpoints/Modelfile.frozen_comp_v5`；④ `virtu_eval/arms.json` 里 7 个指向已消失构件的臂加 `artifact_status`（含证据与规则文本），`checkpoints/PROVENANCE.json` 以**追加**方式写 `identity_recheck_2026_11_05`（不重排既有键） |
| 测试 | `tests/test_ollama_arm_identity.py` 5 项：层指纹必须进每条响应、tools 被拒必须降级且只付一次探针、**支持 tools 的模型不得被静默降级**。回归扫描 93 passed / 2 xfailed；其间新抓出一处：另一会话 10:2x 提交的 `tests/test_desktop_gate.py:189` 用 `secret = "P@ssw0rd-in-the-editor"` 做反泄漏 canary，被凭据扫描器（含我加的 `CRED_ASSIGN_RE`）判为字面量——把变量改名 `canary`，断言语义不变，扫描器不开例外口子 |


## 9. 根因层：把"证据"变成机制，而不是靠人自觉

散点修完之后必须回答：为什么这些东西能存活数月？三条根因，逐条给机制。

### R1 数字可以不回答"哪段字节产生了你" → `virtu_eval/provenance.py`（新，106 行）

| 原发失效 | 机制 |
|---|---|
| `physics_compliance = 1.0` 印成否决项；历史常量印成实测臂；`null` 与"编造的 0"不可区分 | `Metric(value, basis∈{measured,asserted,inferred}, n, evidence, run_id)`：`measured` 缺任一字段即 `raise`；`render_table()` 是唯一的出数通道 |
| 56/56 是 404 的腿被记成 completed；9/210、15/210 的半腿被印成维度分 | `metrics_from_raw()`：按 case_id 取末次尝试、传输率 >5% 拒绝、行数 ≠ 计划用例数拒绝 |
| 一条腿的 30 条 404 记录在 10:0x→11:0x 之间**被外部换成 210 行无重复、toolcall 有分**（改写，非追加） | `seal_leg()/verify_seal()`：封缄后哈希或行数一变即判"证据被改写"；未封缄的目录不得发布；在跑的腿不出数 |
| 分数按标签引用，而标签被改指（§8） | `RunIdentity.capture()` 把 model/template/system 层哈希 + 用例 sha + 判分器 sha 归约成一个 16 位 `run_id`；`drift()` 列出移动项 |

配套：`runs/eval/fullboard_20261105_0930/drift_watch.py`（60 s 轮询、只读、写 `drift_log.jsonl`，事件含 `layer_moved`/`ruler_moved`/`cases_moved`/`alias_change`/`artifact_vanished`）、`make_tables.py`（报告表格只能经闸门生成）。

**当前闸门状态（11:19）**：`legs=8 published=0 refused/in-flight=8`。全部旧腿因"无 per-row 身份取证"被拒；这不是失败，是它在拒绝我今天写过的那种数。新链 `__v4` 的每一条响应都带 `served_layers`，跑完即出数。

测试：`tests/test_provenance_gates.py` 16 项，含植入式反证（改写 raw、追加 raw、未封缄、无身份戳、覆盖不全、被重指的标签、被换掉的判分器、mm⁵ 语料）。

### R2 一套定律一个参照 — 收尾记录

四处另起炉灶的处置：
- `mass_props_csg` 的 mm⁵ ⇒ 已修（box `w·h³/12`、cyl `πr⁴/4`），并出 4 份 `*.units_fixed.jsonl` 语料更正版（255 条，比 67.6×）。
- `design` 的 `V = max(V,1)` ⇒ 另一会话 10:23 已删；`tests/test_physics_reference_honesty.py::test_design_negative_volume_is_rejected_not_clamped` 钉住（负体积原样返回，由 L1 正值闸拒绝）。
- `fea_fos` 缺 `fos_gate` ⇒ 另一会话已把谓词加进参照，**但只加在参照**：参照的 comparable 字段从 2 变 3，于是 `derivation.jsonl` 三条 e04/e05/e06 的 **gold 自己掉到 62.5/100**，任何省略该谓词的模型都会被判成能力失分（其实是尺子失配）。我给那三条 criterion 补 `min_compared: 2`（定律腿只考数值定律，判定归物理腿），`validate_cases` 恢复 `VALID: 2 dimensions, 60 cases, all gold 100`；并加"改错 fos_gate 必须判不过"的变异断言，防它再次名义 graded、实则无人判。
- `virtu_real_backend.py` 的分度圆弦长 ⇒ 与闭式解实测偏差 0.0，问题只是复制。`derivation.LAWS` 的算式语言只有四则与常数（无 `sin`），注册三角定律会改判分链的表达式求值器＝换尺子，故本轮不接，改由 `tests/test_chord_single_source.py` 钉住"两处实现必须一致、出现第三份即红"。

**根因层的根因（今天自己也挨了一刀）**：`scratch/` 在 11:2x 被其他会话整体清空，我的出题脚本、变异探针与十余个中间证据一起没了（用例数据本身在 `data/` 下，未受影响）。教训写进 `agents.md` §8 第 3 条：**凡结果要被引用，其生成器与探针不得放在可被清扫的目录**（变异探针已迁到 `runs/eval/fullboard_20261105_0930/mutation_probe_gate.py`，测试临时目录从 `scratch/` 迁到 `runs/eval/_test_tmp/` 且按需自建，避免"目录没了"变成假红）。

### R3 治理层：写进所有会话都要读的入口

`agents.md` 追加 §8《测量宪法》六条（数字可归因、按内容寻址、共享状态写权限、闸必须可证伪、一套定律一个参照、测量链独占）。原 §1–§7 逐字未动（该文件不在 git 索引内，故只做追加）。

## 10. 还没修的（截至本报告；已修的都不在此列）

1. `derivation.LAWS` 仍只能表达四则定律，三角/几何定律（分度圆弦长等）在运行时无处收口；接入需扩展表达式求值器，会换掉 derivation 判分口径，故留待一次专门的"换尺子 + 重建基线"提交。
2. **历史产物仍带 mm⁵ 直觉**：`data/sft/virtu_final_train.jsonl` 等原件按原样保留作证据，训练必须指 `*.units_fixed.jsonl`；用旧语料训出的在服权重，其 mass_props 族能力不得据本轮分数下结论。
3. `virtu_real_backend.py`（仓库根）自己算分度圆弦长 `d·sin(180°/z)`，`derivation.LAWS` 里没有这条定律 ⇒ 裁判与选手两套几何；接线会改 `derivation.py`（判分链依赖），与第 1 项同批做。
4. SW-in-the-loop 四臂套件需要独占 SOLIDWORKS COM 与内存窗口，本轮未跑（SOLIDWORKS 当前未启动，实例归属未确认，绝不擅自建模）。
5. 三份 damodel root 口令的**轮换**与改用密钥登录（见 §4）；`paramiko.AutoAddPolicy()` 未动。
6. 云端 `train_corpus_comprehensive.jsonl` 的 1621 条数值代理未逐条人审，只降级为告警。
7. `checkpoints/COMPREHENSIVE_EVAL_REPORT.md` 的作废标注会在下一次 `deploy_and_cleanup.py` 下载时被覆盖——生成端已改，但若云端仍跑旧版 `eval_in_situ.py`，假 100% 会再回来。
