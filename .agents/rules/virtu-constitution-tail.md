---
trigger: always_on
description: "Virtu 工作区运营宪法后半段（§8-§10）：测量宪法、全仓回归假红归因、探针判分器两类假阴性、Google Sleep 验收口径、VERICUT 9.6 官方培训知识库。AGENTS.md 超过 Antigravity 单文件 24000 字节上限会被静默截断，本文件补齐被截掉的尾部。"
---

> 本文件是 `D:/Virtu模型/AGENTS.md` 自 `§8 测量宪法` 起的**逐字原文**。
> 原因：AGENTS.md 当前 37636 字节，Antigravity 单规则文件上限 24000 字节，
> 日志实测截掉 13794 字节（实际只保留约 23842 字节），尾部含 §8.2、§9、§10
> 等 2026-11-14/15 新增的强制约束。
> 起点选在 §8 而非 §8.1，是为了在 AGENTS.md 前半段增长时仍与截断点保持重叠，
> 避免出现覆盖空洞（当前重叠约 2.7 KB）。
> 完整原文仍以 AGENTS.md 为准；本文件仅供 Antigravity 补齐，勿单独编辑。

## 8. 测量宪法（2026-11-05 事故后追加，对所有会话生效）

今日实测到的根因不是某个 bug，而是三条缺失：数字可以不回答"哪段字节产生了你"、被测对象是**可改名的共享状态**、闸门可以空转。以下六条为硬约束。

1. **数字必须可归因**。任何进 `benchmarks/`、`README.md`、`checkpoints/PROVENANCE.json` 的数值，必须经 `virtu_eval/provenance.py`：`run_id`（内容指纹）+ 样本量 `n` + 证据文件路径 + 口径 `basis` 取 measured/asserted/inferred。没测就写"未测"，**禁止**把源码字面量当测量结果（今日：`physics_compliance = 1.0` 被印成"物理合规率 100%（否决项）"；`HISTORICAL_BASELINES` 常量被印成三个实测臂）。
2. **被测对象按内容寻址，不按名字**。起腿前 `RunIdentity.capture()` 记 Ollama 层哈希（model/template/system）、用例文件 sha256、判分器 sha256；腿结束时 `drift()` 非空即**该腿作废**，不得改称"某标签的成绩"。今日四个标签（`virtu-comprehensive`/`virtu-master`/`virtu-ties-v1`/`virtu-test-tool`）在不同会话手里被重指成同一 manifest，双脚手架消融当场失效。
3. **共享可变状态需要写权限自觉**。Ollama 库、`data/sft/*`、`virtu_eval/arms.json`、`virtu_eval/graders.py`、他人 `runs/**` 目录都是共享的。删除构件前先查引用（`deploy_and_cleanup.py::evaluation_referenced_tags`）；不得向他人封缄过的腿目录写入（`provenance.verify_seal` 判"证据被改写"）；不得重写他人 run 目录的 `raw.jsonl`（今日一条腿的 30 条 404 记录被外部替换，事后无法自证）。
4. **闸必须能被证伪**。新增任何判据或门禁，同时提交"植入坏样本 ⇒ 必须红"的反证测试（范式见 `tests/test_provenance_gates.py`、`scratch/_mutation_probe_gate.py`）。空匹配集、解析失败、`if not exists: continue` 一律判红，不得当作通过。
5. **一套定律只有一个参照**。物理/几何公式的权威是 `virtu_eval/derivation.LAWS` 与 `scripts/wm_verifier.recompute`；判分器直接 import 执行器的 `validate()`；单位写进字段名且可量纲核验（`scripts/corpus_unit_audit.py`）；禁止 `V = max(V,1)`、`... if False else ...` 这类静默改写靶值（今日据此揪出 255 条 mm⁵ 冒充 mm⁴ 的训练靶）。
6. **测量链是独占资源**。起链前漂移哨兵与 foreign-runner 必须为空；链在跑时不得改 `runner.py`、`arms.py`、`graders.py` 与用例目录；发生外部改动以 `drift_log.jsonl` 为准并作废受影响腿，而不是"记得几分算几分"。

### 8.1 全仓回归的环境假红与跑挂归因（2026-11-13/14 实测）

全量 `pytest tests/` 报 27 failed，逐文件隔离 + 换环境复跑后 **22 个是环境假红**，真缺陷只有 3 个。下次看到成批失败先按下列条目排除，不要直接改代码：

1. **删除守卫 shim 会让 pytest 进程 `SystemExit: 1`**。报错栈落在
   `...\WorkBuddy\...\cli\vendor\shim\sitecustomize.py`，特征是同一批测试全挂在
   `SystemExit` 上，且都做了临时目录清理。跑法：
   ```bash
   env -u CODEBUDDY_SAFE_DELETE_BULK_STATE_DIR -u CODEBUDDY_TOOL_CALL_ID \
       -u CODEBUDDY_SAFE_DELETE_BULK_GUARD \
       .venv/Scripts/python.exe -m pytest tests/ -q
   ```
   实测 `test_provenance_gates` 5 failed → 17 passed、`test_runner_repeats` 2 → 9 passed。
   **2026-11-14 已从测试侧根治**：`test_eval_in_situ_gate` / `test_train_data_gate` /
   `test_provenance_gates` / `test_runner_repeats` / `test_paired_verdict_ruler` /
   `test_security_audit` 的临时产物统一迁到 `tempfile.gettempdir()`（shim 明确放行系统
   TEMP 下的删除），不再「往仓库里写又删」；`env -u` 退为兜底而非常规跑法。
2. **另一会话并发写同一仓库**（`data/sft/*.jsonl`、`virtu_omni/**`）会让数据闸随机红。
   实测 `test_train_data_gate` 全量跑 3 failed、单独跑 6 passed。判定批量红之前先
   `git status` 看有没有别人正在改。
3. **显存被 Ollama 占着时带宽探针报 6.8 GB/s（空闲 173 GB/s）**。这不是显卡慢，
   是 copy 掉到主机内存往返。`test_operator_extreme` 会因此红；清显存后重跑即可，
   **不要**把 `> 50` 阈值调低——偏低的带宽会把整套 roofline 下界算错。
4. **REACT 真循环能把整仓 pytest 进程杀掉**（2026-11-14 实测）。
   `test_sleep_integration_dual_track.py::test_02_super_agent_react_hooks_wake_step`
   走 `_solve_react_deep`，默认 `VIRTU_REACT_BUDGET_S=90`，规划 + 验收两次模型调用
   = 180s > `--timeout=120`；Windows 上 pytest-timeout 直接终止进程，日志停在
   `++++ Timeout ++++` 且**没有任何 summary / FAILED 列表**，看起来像「跑挂了」。
   堆栈会指向 `bridges/deep_agent.py::chat` 的 `urllib` 读响应。该文件已加 autouse
   fixture 把预算压到 3s，让引擎走「超时 → 可见降级 → 硬编码流水线」，离线、快速，
   且保住降级分支覆盖。
5. **服务端提前回 4xx 却不读请求体 → Windows RST**（2026-11-14 已修，属真缺陷）。
   `workbuddy_virtu_bridge.py::_require_auth` 原先直接回 401 并 close，POST 的 body
   还留在内核接收队列里，客户端读到 `ConnectionAbortedError [WinError 10053]`
   而不是 401；偶发，只有连续多次请求才稳定复现。修法与既有 503 容量路径一致：
   回 4xx 前 `_drain_unread_request_body()` 排空，并给 4xx 加 `Content-Length`；
   `test_00b_rejected_post_body_never_resets_connection` 连发 12 次复验。
6. **别对 `max_cycles=1` 的 daemon 断言「sleep 后仍 alive」**。真 cycle 会联网 /
   跑 Ollama，耗时从 <0.5s 到 >10s 不等，隔离后必翻红。`test_06_daemon_thread_lifecycle`
   已改为 stub 掉 cycle，只断言「线程真被 start + 恰好跑一轮 + 遥测落盘 + 可停止」。
7. **`subprocess.run(capture_output=True, timeout=N)` 在 Windows 上仍可能永久卡住**（2026-11-14 已修）。
   `test_agent_team.py::test_industrial_agent_team_solve` → `unload_ollama_model()` →
   `ollama stop ...` 会派生孙进程继承 stdout 管道；父进程被 timeout kill 后管道不 EOF，
   `communicate()` 的 reader thread 无限 `join()`，整个 pytest 被 `--timeout=120` 杀掉
   （日志只有 `++++ Timeout ++++`，没有 summary / FAILED 列表）。修法：这类外部进程
   调用一律 `stdout=DEVNULL, stderr=DEVNULL` + `timeout`，**不要** `capture_output`
   （调用方本就只取 returncode）；`taskkill /F /IM ... /T` 同理。实测
   `test_agent_team` + `test_reclaimer_baseline` + `test_agent_8b_serving_defaults` 18 passed / 12.15s。
8. **Ollama「服务在线」≠「有模型」**（2026-11-14 实测）。
   `test_internet_search_and_learn.py::test_05_hub_discovers_models` 无条件断言
   `"ollama" in source_types`，但本机 `/api/tags` 返回 200 且 `models=[]`、`ollama list`
   只有表头，`discover_workspace_models()` 发现不到 ollama 是**正确行为**。现改为
   实测「CLI 缺失 / 服务不可达 / 零可用模型」才 `pytest.skip` 并写明原因；
   **服务里确实有模型却漏发现仍然判红**，不得用 skip 掩盖发现逻辑缺陷。

顺带一条：默认 3.12 解释器（`python`）缺 `sympy`，跑仓库测试一律用 `.venv/Scripts/python.exe`；
全仓回归也用 Python 3.12（`C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe`），
该环境已装齐 torch / sympy / shapely / bs4，102 文件可全量收集。
### 8.2 探针判分器的两类假阴性（2026-11-15 六软件 v3 验收实测）

`virtu-six-software:v3` 首次部署验收判 `PROBE_FAILED`（`lame_stress_probe`、
`vericut_coordinate_unit_probe`）。复现后定性：**两项都是测量缺陷，不是模型缺陷**。
凡「模型答错」的红条，先按本节三类排查，再谈再训一轮：

1. **token 预算截断**：探针 `num_predict` 过小，模型在推导中途被硬截断，
   旧判分器把「被截断」报成「模型没给该结论」。2026-11-15 实测 Lamé 探针
   `num_predict=260` 时，模型已正确写出 σ_θ=33.33 MPa，但在写出 σ_r 之前戛然而止。
   ⇒ 探针预算必须留足推导长度（现为 420），且判分器要用 `_looks_truncated()`
   把截断**单独报出来**（`truncated_before_…`），不得冒充模型缺陷。
2. **字符集过窄**：数学负号有 `ASCII '-'` / `U+2212 '−'` / `U+FF0D '－'` 三种，
   只认 ASCII 会把正确答案判成「没有 -20」。
3. **否定词表缺口（镜像缺陷，最隐蔽）**：判「禁止/不可」语义的词表若缺「不得」，
   正确表述「不得擅自改写为 millimeter」会被判成「缺隔离」，
   而「**不得**直接等价套用」又会被「声称等价」那条**反向**拦下 ——
   同一处缺口同时制造漏放与误杀。

**硬约束（新增）**：

- 判分器改动必须配「植入坏样本 ⇒ 必须红」的反证测试
  （范例：`tests/test_six_software_probe_measurement_fix.py`，14 passed）；
  只让好样本变绿不算修复。
- 凭证必须记录判分器身份：`measurement_version` + `grader_sha256`。
  `grader_sha256` 取**导入时**对本文件的快照（`deploy_trained_adapter.py` 内的
  `_snapshot_grader_sha256()`），这样同一时刻启动的并发测量腿共享同一判分器版本，
  磁盘后续被改动也不会篡改已在跑的腿的凭证（§8.2「按内容寻址，不按名字」）。
- 同一 Ollama 标签并发跑 `--verify-only` 会互相覆盖
  `checkpoints\deployment_receipt_<tag>.json` ⇒ 开跑前先备份既有凭证，
  跑完立即按时间戳另存快照。
- **验收前先复现再下结论**：本次两条「模型缺陷」若不复现原始输出，
  就会把判分器缺陷当成模型缺陷去烧训练额度（而云端 GPU 那时已关停，训不了）。

---

## 9. Google Sleep 框架有效性验收口径（2026-11-12 修复后追加）

定位澄清：`VirtuSuperAgent` 是自研框架（5 模式 / 36 工具，2026-11-15 对 `super_agent.py` 的 `register_tool` 去重实测；旧文档"32 工具"为过期口径），**Google Sleep 不是框架本体**，只是 `virtu_omni/memory/sleep_framework.py` 提供的一个离线巩固 facet（`trigger_sleep_cycle`）；另有 `virtu_omni/google_suite.py` 的 Google DeepMind 四件套。论文 arXiv:2606.03979 属实，但本地实现是"Wake/Sleep 三阶段范式"的自研简化版，**无参数更新、无低秩 expert、无 GKD 蒸馏、无梯度筛选 RL**，不得宣称等同于 Google 官方实现。

2026-11-12 实测判定原实现无效，根因与修复：

- 自动触发链路（`internet/autonomous_engine.py`）用无 `model_caller` 的单例，`run_sleep_cycle` 以硬编码字符串兜底应答 → 改为经 `build_ollama_model_caller()` 注入真实模型，不可用时诚实降级。
- 稳态门禁用 `baseline = stability` 自比较，CF 恒 0、gate 恒 True → 改为绝对阈值 `S>=0.95 / P>=0.90 / CF<=0.05`，`pre_baseline_score` 必须由外部独立实测提供；缺基线即 `basis=unmeasured` + gate=False。
- 梦境为硬编码题 + 解析解自证，空梦境 `pass_rate` 默认 1.0 → 标 `solution_source` / `evidence_basis`，仅 `measured` 梦境计入通过率，空集判 0.0，`dream_gate_passed` 纳入总门禁；fallback 域补 `generate_anchor_dreams()` 保证有可证伪梦境。
- token 未测时回退 `len(text)*2` 字符近似 → 改为 `compression_ratio=None` / `token_basis=unmeasured`，禁止冒充 §8.1 实测。
- 生产/验证脚本失败时返回 `"ERROR: ..."` 字符串当模型应答、报告硬编码 `basis=measured` 与 `PASS` → 统一走 `build_ollama_model_caller()`，失败即 None；报告口径由 cycle_report 继承。

有效性判据（五项须同时成立，证据见 `benchmarks/GOOGLE_SLEEP_EFFECTIVENESS_2026-11-12.json`）：

1. 项目 Python 3.12 环境可导入运行（IDE 注入的 3.13 裸环境缺 `sympy`；`sympy>=1.12` 已在 `pyproject.toml [project.dependencies]` 核心依赖中声明，按 `pip install -e .` 安装即可）。
2. `measurement_valid=True`：有真实 `model_caller`、稳态 `basis=measured`、梦境 `evidence_basis=measured`。
3. 门禁绝对阈值 + 独立基线通过，且 `dream_oracle_pass_rate>=0.80`。
4. 可证伪：坏模型 / 无模型 / 缺基线 / 植入坏物理四种情况 gate 必须为 False（反证在 `tests/test_sleep_framework.py`）。
5. 未测项一律 `unmeasured`，不得以字符估算、空集 1.0 或硬编码 PASS 充当证据（§8.1 / §8.4）。

残留风险：锚点判分仍是关键词包含匹配，错误答案若含关键词可能被判命中；后续应改为物理 oracle 或 `wm_verifier.recompute` 判定。

---

## 10. VERICUT 9.6 官方培训知识库（2026-11-14 摄入）

**来源**：`E:/training`（CGTech VERICUT 9.6 Training Sessions，586 MB / 1186 文件 / 902 页讲义），**只读**，脚本不改动源目录任何文件。

**为什么必须换掉旧知识库**：摄入前 `knowledge_base/web_knowledge_store.json` 只有 18 条，正文全是「关于 '故障与知识补齐…' 的工业制造标准规范，系统遵循 GB/ISO 国标及力学安全守则」这类模板套话，SFT 也是同一套模板 —— 没有任何可核验的 VERICUT 事实。落盘 ≠ 学会。

**链路**（入口 `scripts/ingest_vericut_training.py`）：

```
E:/training (只读)
  -> virtu_omni/knowledge/vericut_training.py::scan()     实测解析
  -> ContinualLearningPipeline.ingest_structured_records() 安全门 + 去重 + 本地向量
  -> knowledge_base/web_knowledge_store.json              530 条 measured 条目
  -> data/sft/vericut_official_training.jsonl             1060 条证据驱动训练对
  -> augmentation.training_context_block() / SuperAgent.facet_recall_vericut_training()
```

**解析口径**：`.vcproject` 抽版本/单位/关联文件/`<AutoDiff>` 的 Gouge-Excess 容差；`.ctl`/`.tls`/`.vcfm` 抽 XML 字段与刀具明细；`.mcd`/`.nc`/`.eia` 抽真实 G/M/T/S/F 代码（括号注释不算执行代码）；PDF 按 4 页一块抽讲义原文；STL 纯标准库算包围盒/面数，**STL 头不含单位，字段一律 `unit=unknown_from_stl`，不臆断 mm/inch**。几何资产聚合为 1 条统计，不用 286 个 STL 淹没语义检索。

**测量宪法约束**：每条带 `source_path` + `source_sha256` + `evidence` + `basis=measured`；模板套话 / `basis≠measured` / 假 sha256 / 空内容一律拒收（`tests/test_vericut_training_ingest.py` 四类反证）；`scan_corpus` 对 240 案例题板 0 hard leak；`HarmfulContentFilter` 实测 530/530 通过且 0 改写。

**Agent 真的能用到**（这是「学会」的判据，不是落盘）：
1. `virtu_omni/internet/augmentation.py` 增加 `TRAINING_MARKER` 独立上下文块，与联网资料**严格分离**、明确标注「本地实测资料，非互联网检索」，citations 带 `source_path`/sha256/`basis=measured`。开关 `VIRTU_TRAINING_KB` 独立于 `VIRTU_INTERNET`，**离线仍可召回**；pytest 会话由 `conftest.py::_hermetic_internet` 置 off 保证 hermetic。
2. `VirtuSuperAgent` 注册 `recall_vericut_training` 工具 + facet，REACT/SWARM 可显式召回；召回不到返回 `basis=no_evidence`，不拿套话补位。
3. 入库与查询向量统一用 `deterministic_bigram_hash_128`，**不走 Ollama embedding**（否则维度不等会让 cosine 恒 0、且 530 条 × 2 模型 × 3s 会拖死摄入）；中英混合查询另加 `_CN_TO_EN_TERMS` 术语加权。空查询直接返回 `[]`。

**复跑**：`python scripts/ingest_vericut_training.py --root E:/training`（幂等：第二次 `accepted=0 / duplicates=530`，SFT 整文件重建仍 1060 行）；报告 `reports/vericut_training_ingest_report.json`，摄入前知识库备份 `knowledge_base/web_knowledge_store.pre_vericut.json`。

**边界（诚实）**：这是**知识入库 + SFT 语料**，不是权重微调；没有跑 LoRA/全参训练，模型能力变化未经 24 案例基准实测，不得宣称「模型变强」。讲义以英文为主，`retrieve_training_knowledge` 是 128 维 hash 向量 + 关键词加权，不是语义 embedding，召回是「相关条目」而非精确问答。`VIRTU_PYTEST_OLLAMA_TIMEOUT_S` 等测试隔离未改变生产默认超时。
