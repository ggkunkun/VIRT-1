# 主力模型工业测试报告 — `virtu-wm-v3:chatml`

- 测试日期：2026-11-12
- 被测对象：`virtu-wm-v3:chatml`（权重层 `sha256:293cdac3e52f…`，4.61 GB，Qwen3 8.2B / Q4_0）
- 测试范围：模型 + 求解器离线评测（未启动 SOLIDWORKS / AutoCAD / VERICUT 等桌面软件）
- 口径：`measured` = 本次实跑产出；`asserted` = 源码/台账静态事实；`untested` = 未测
- 证据目录：[runs/industrial_eval_20261112](file:///d:/Virtu模型/runs/industrial_eval_20261112)

---

## 0. 结论摘要

| 项 | 结果 | 口径 |
|---|---|---|
| 评测链完整性（14 项护栏门禁） | **14/14 PASS** | measured |
| 契约形态（JSON 可解析 + `world_state` 顶层） | **22/22 = 100%** | measured |
| 独立人工留出集严格通过 | **0/22 = 0%**（Wilson95 0–14.9%） | measured |
| 数值字段正确率 | **15/70 = 21.4%**（实写 41/70，写好之中 15/41=36.6% 正确） | measured |
| 闸门字段正确率 | **20/22 例** | measured |
| 模型自写 derivation 与自身填数矛盾 | **17/29 字段 = 58.6%** | measured |
| 闸门宣称与自身数值矛盾 | **3/8 例** | measured |
| 端到端时延 / 解码速度 | 中位 **27.16 s/例**，P90 43.72 s，**4.42 tok/s** | measured |
| 6 GB 显存可部署性 | **不达标**：8192 ctx / 24 层 GPU 卸载实测 `cudaMalloc 132 MiB` 失败，服务 500 | measured |

**一句话结论：这是一台“格式很稳、护栏很强、算数与参数绑定不可靠”的 8.2B 世界模型原型，不是可上产线的工业智能制造模型。** 它能稳定输出合法 JSON、能正确复述大部分闸门，但“写得出公式、算不对数、填不全字段”的系统性缺陷仍在权重层，尚未被 2026-11-11 的契约修复消除。

同日同权重在旧生产尺（702 B system，14 例）上的成绩为：模型裸分 **67.20**、系统兜底 **87.06**、综合 **79.00**（`measured`，见 [PRODUCTION_FINAL_EVAL_2026-11-08.md](file:///d:/Virtu模型/benchmarks/PRODUCTION_FINAL_EVAL_2026-11-08.md)）。本报告用的是 8 KB 世界模型契约 + 22 例独立人工题，**两把尺不可折算**。

---

## 1. 被测身份与可追溯性

| 项 | 值 |
|---|---|
| 模型标签 | `virtu-wm-v3:chatml` |
| 权重 blob | `sha256-293cdac3e52f6340208967b743ee4a1d67684a24f8a8f011849423e34c1ed9c2`（文件内容哈希实算一致） |
| 架构 / 量化 | Qwen3 8.2B / Q4_0，模型最大上下文 40960 |
| Modelfile SYSTEM | 8053 chars，sha256 `dff2d830…` |
| 契约源 `wm_contract.SYSTEM` | 7941 chars，sha256 `fd3d66af…`（与 Modelfile 同源） |
| 判分脚本 | [eval_worldmodel.py](file:///d:/Virtu模型/scripts/eval_worldmodel.py) sha256 `ac7e58e6…` |
| 求解器 | [wm_verifier.py](file:///d:/Virtu模型/scripts/wm_verifier.py) sha256 `b0d0d81f…` |
| 留出题 | [wm_holdout_v1.jsonl](file:///d:/Virtu模型/data/holdout/wm_holdout_v1.jsonl) sha256 `e9feb960…`（22 例，人工撰写、冻结） |
| 运行环境 | Ollama 0.40.14，RTX 4050 Laptop 6141 MiB，驱动 617.14，系统内存 15.7 GiB |
| 采样 | temperature=0，format=json，num_ctx=5120，num_gpu=16，num_batch=128，num_predict=512，keep_alive=30m |

完整身份文件：[identity.json](file:///d:/Virtu模型/runs/industrial_eval_20261112/identity.json)

> 关键事实：该权重 `293cdac3` 就是 2026-11-08 生产终评第一名所用权重（`virtu-max:293cdac3`），因此本报告的缺陷不是某个实验分支的问题，而是**主力权重本身**的问题。

---

## 2. 测试矩阵与结果

### L0 评测链完整性（先证明尺子可信）

`python scripts/wm_ci_gate.py` 实跑 **14/14 PASS**，包含：

- 契约↔解码同源、闸门归一、护栏三层钩子、反幻觉护栏、L2 复算器
- 12 项历史漏洞回归、缺参假绿探针、评测去污纯度、题面改写归族
- 独立回归集（真值由脚本内置解析式独立算出，并对每题灌入 30% 偏移错误答案确认必须被拒）
- 12 族零误拦、端到端孪生一致性

证据：[ci_gate.log](file:///d:/Virtu模型/runs/industrial_eval_20261112/ci_gate.log)

**结论：尺子本身是硬的。** 下面的低分不是判分器坏了，而是模型输出真的不满足契约。

### L1 契约形态

独立留出集 22 例：`extract_json` 全部可解析，`world_state` 顶层全部存在，非法嵌套/禁用键 0 例。

- 形态合规 **22/22 = 100%**
- 解析失败 **0/22**
- 传输/服务错误 **0/22**

说明：8 KB 契约在“输出形态”这一层是有效的。这是本轮最扎实的正面结论。

### L2 独立人工留出集（22 例，11 族 × 2）

| 指标 | 结果 |
|---|---|
| 严格通过（数值+闸门+文本+布尔全对） | **0/22 = 0%**（Wilson95 0–14.9%） |
| 数值字段应填 / 实写 / 正确 | **70 / 41 / 15**（正确率 21.4%） |
| 文本布尔字段应填 / 实写 / 正确 | **8 / 7 / 4** |
| 闸门字段正确 | **20/22 例** |
| 单位量级疑错（比值接近 1e3 / 1e-3） | 0 字段（错误不是简单小数点错位，而是公式绑定/执行错） |
| derivation 与自身填数矛盾 | **17/29 字段 = 58.6%** |
| 闸门宣称与自身数值矛盾 | **3/8 例** |

逐族结果：[summary_holdout22_model.md](file:///d:/Virtu模型/runs/industrial_eval_20261112/summary_holdout22_model.md)
逐例原始响应：[holdout22_model.json](file:///d:/Virtu模型/runs/industrial_eval_20261112/holdout22_model.json)

### L3 120 例主评测：未完成（服务 OOM，不是模型分数）

原计划 12 族 × 10 例。实跑中 Ollama 在 6 GB 显存上多次崩溃：

- `8192 ctx`（Ollama 自动拟合 25 层 GPU）：`ggml_backend_cuda_buffer_type_alloc_buffer: allocating 132.00 MiB … cudaMalloc failed: out of memory` → `failed to initialize the context` → `/api/generate` 500
- 降到 `6144 ctx / 24 层` 仍会中途崩溃
- 最终稳定配置 `5120 ctx / 16 层` 热态约 10 s/例，但为避免再次污染证据，120 例主腿**主动放弃**，只用独立留出集 22 例作为主证据

OOM 现场见 Ollama `server.log` 第 22526–22540 行（`C:\Users\Administrator\AppData\Local\Ollama\server.log`）。

补充证据：在 `6144 ctx / 24 层` 配置下先跑出的 12 例（非最终配置，仅作一致性核对）：

- 严格通过 **1/12 = 8.3%**
- 数值字段 53 应填 / 28 实写 / 14 正确
- 宣称≠参数 **4/8**
- 与 22 例留出集同向：低通过率来自算术与字段缺失，不是格式

证据：[raw_stream_contract_cfgA_gpu24_ctx6144.jsonl](file:///d:/Virtu模型/runs/industrial_eval_20261112/raw_stream_contract_cfgA_gpu24_ctx6144.jsonl) 与同目录 `summary_*.md`。

### L4 同权重旧生产尺对照（外部证据，不折算）

| 指标 | 值 |
|---|---|
| 模型裸分（14 例，702 B system） | 67.20 |
| 系统兜底分 | 87.06 |
| 综合 | 79.00 |
| 边界 / 推理 / 知识 / 指令 / 生成 / 泛化 / 工具 | 100 / 33.3 / 50 / 66.7 / 80 / 33.3 / 100 |
| 求解器接管 | 6/14 题 |

来源：[PRODUCTION_FINAL_EVAL_2026-11-08.json](file:///d:/Virtu模型/benchmarks/PRODUCTION_FINAL_EVAL_2026-11-08.json)。该轮报告已明确写：“它不等于已可无人值守上产线；能力分只有 72.73，且 CAE/FOS、VERICUT Auto-Diff、SSCNC 面板读值、多模态四块结果级判据本机未测。”

### L5 部署质量

| 指标 | 值 |
|---|---|
| 端到端时延（含 4 KB 契约预填） | 中位 27.16 s，P90 43.72 s |
| 解码速度 | 中位 4.42 tok/s（16 层 GPU 卸载） |
| 首次加载 | 约 45–60 s |
| 6 GB 显存稳定性 | 不达标（见 L3） |
| 系统内存余量 | 实测仅约 3.1 GiB free（模型加载前） |

---

## 3. 缺陷清单（按严重度）

### D1（致命）写得出算式，算不对数：derivation 与字段值自相矛盾

留出集 29 个可核对的 derivation 字段中 **17 个（58.6%）** 与模型自己填的数值不一致。

典型：

| 案例 | 模型自写算式 | 算式真值 | 模型填的数 | 偏差 |
|---|---|---:|---:|---:|
| HO-DES-01 轴套体积 | `pi*(197.6/2)^2*25 - pi*(80/2)^2*25 - 6*pi*(8.6/2)^2*25` | 632,285 mm³ | **1,224,497** | +93.7% |
| HO-PRO-02 主轴转速 | `1000*150/(pi*80)` | 596.83 r/min | **3,978.26** | +566% |
| HO-REM-01 去除体积 | `DOC*WOC*L = 2*5*100` | 1,000 mm³ | **8,000** | +700% |
| 补充臂 fea_fos | `(215)/(208.5)` | 1.031 | **1.46** | +41.5% |

这与 2026-11-11 报告残留项“**改宣称不改参数 / 不会执行算式**”完全同型。契约层能要求它写算式，但权重层没有学会“把算式算出来再填”。

### D2（致命）定律选错 / 题面参数绑错

- HO-REM-01：MRR 写成 `ap*f*n = 2*400`，把“进给速度”当成每转进给 `f`，正确应为 `DOC*WOC*vf = 2*5*400 = 4,000`，模型填 1,600。
- HO-PRO-02：进给 `f*n = 0.15*3978.26` 用了自己错误的主轴转速；MRR 写成 `ap*f*vc*1000`，把已含 `n` 的 `vf` 又乘了一次。
- 补充臂 process 例：`mrr = 0.9*0.307*(155/0.001)*1000`，单位换算重复乘 1000；主轴 2,985 vs 665.8（疑似把 D 绑成 16.5 mm 而不是题面的 74.1 mm）。

### D3（高）契约字段不回填：70 个应填数值字段缺 29 个

模型经常只写“结论量”，不写题面已给的输入量：

- HO-FOS-01/02：`safety_factor` 与 `fos_gate` 正确，但 `yield_strength_mpa`、`peak_von_mises_mpa` 缺失 → 严格判分 FAIL
- HO-ADM-01：同上
- HO-COL-01/02：`safe_plane_z_mm`、`rapid_min_z_mm` 缺失
- HO-MAC-01/02：`required_spindle_rpm`、`machine_max_rpm`、`recommended_vc_m_per_min` 缺失

这类失败**不是算错**，而是没有按契约把“可回灌验证的完整物理量”交出来。工业场景下，缺输入量意味着无法追溯、无法复核，仍应判失败。

### D4（高）闸门与自身数值矛盾

- HO-TOL-02：`fit_clearance_mm = -0.01`（负间隙，应为过盈），但 `tolerance_pass = true`；真值 `-0.03` / `false`。
- 留出集 8 个可核对闸门中 **3 个** 与自身数值矛盾（`fos_gate`、`volume_conservation`、`gouge/risk` 三类均出现过）。

### D5（高）标准知识替代推导

- 补充臂 tolerance 例：题面给出上偏差 -0.027、下偏差 -0.035，模型输出 `fit_class = H7/m6`；按给定偏差应为 `H7/js6`。模型在“回忆标准表”，而不是按题面数值推导。
- `fit_clearance` 的 derivation 写成符号式 `upper_deviation - lower_deviation`，没有代入题面数字，契约规则 F 明确禁止。

### D6（中）单位/量纲处理不稳

- 留出集未出现 1e3/1e-3 的“小数点错位”，但补充臂出现 `155/0.001*1000` 这类重复换算；removal 案例出现 8× 整倍偏差（体积与质量同步 8×），说明是定律/绑定错，不是随机舍入。

### D7（中）重复性未达标（需正式复测）

同一题面、同一 system、temperature=0，两次调用（不同 context/GPU 卸载配置）给出不同结果：

- 手工探针：`安全系数 = 1.04`
- 同题主评测：`安全系数 = 1.46`（derivation 仍写 215/208.5）

这不是受控重复实验（一次在模型刚加载、一次在热态，且 context/卸载配置不同），但足以说明**当前部署不具备工业要求的可重复性证据**；需固定 seed、同一 context/卸载配置、同批次复测后才能下结论。

### D8（高，工程）6 GB 显存装不下 8 KB 契约的稳定服务

- 8192 ctx（自动拟合 25 层）：稳定复现 OOM（`cudaMalloc 132 MiB` 失败），服务 500。
- 6144 ctx + 24 层：仍会中途崩溃。
- 5120 ctx + 16 层：可跑，但 4.42 tok/s、27 s/例，且系统内存仅剩约 3.1 GiB。

对工业现场而言，这不是“小瑕疵”，而是**部署形态不成立**：要么换 ≥12 GB 显存，要么量化 KV/缩短契约，要么改用更小模型。

---

## 4. 距离“工业智能制造模型”还缺什么条件

下面每条都给“现状（证据）→ 缺什么 → 可证伪验收判据”。验收判据不通过，就不算具备该条件。

### C1 统计上站得住的评测条件

- **现状**：主力模型此前从未跑过真实 12 族端到端（2026-11-08 报告明确写“未测”）；生产终评每维仅 2 题；本轮独立留出集 22 例，每族 2 例，Wilson 区间宽达 0–65.8%。
- **缺什么**：每族 ≥30 例、跨 3 个 seed、两个独立 run、判分器噪声标定、配对置信区间；所有分数封缄并带 `run_id`。
- **验收判据**：每族 n≥30；重复两轮通过率差的 95%CI 覆盖 0；判分器对 30% 偏移错误答案 100% 判红；报告中的每个数字都能追到 `raw.jsonl` 行号。

### C2 真实工业数据与知识条件

- **现状**：训练语料 7,828 条、1,327 个模板簇，全部可 JSON 解析（measured）；但原始 `data/sft` 近重复溢出 76.38%；没有真实工厂数据、传感器时序、CMM 计量、报废/返修记录；MES/OEE/SPC 在代码中无实现，OPC UA 只出现在知识库字符串里。
- **缺什么**：真实加工案例与结果数据（切屑、刀具磨损、机床日志、三坐标报告）；标准语料（ISO 10303 / ISO 6983 / ISO 1101 / ISO 286 / ISO 2768 / GB）；材料-刀具-机床-夹具目录；数据授权与脱敏流程。
- **验收判据**：≥1,000 条带真实结果回读的加工案例；标准题引用条款号且可检索到原文；材料/刀具/机床字段在题面缺失时必须报错而非猜默认值（已有缺参探针，需扩到模型层）。

### C3 几何 / CAD 条件

- **现状**：世界模型只做“物理量换算”，不生成特征树；本轮未启动 CAD 软件；六软件评分中 SOLIDWORKS 79、NX 69（NX 3 个环槽特征失败，`feature_count=2` 预期 4）；无 STEP/AP242 语义理解，STEP 只被读成体积/包围盒文本。
- **缺什么**：参数化特征树生成与回读、约束求解、装配配合、工程图/GD&T/PMI、STEP AP242 往返、SW/NX API 真实执行与体积守恒断言。
- **验收判据**：同一零件 STEP 往返后体积偏差 ≤1%、包围盒偏差 ≤0.05 mm、特征数一致；SW/NX 全特征重建 0 错误；工程图图层/标注/公差通过规则审计。

### C4 CAE 条件

- **现状**：`fea_fos` 只是一条 `FOS=Sy/σ` 的闭式算式；没有网格、边界条件、接触、疲劳、热、屈曲、模态；生产报告明确写“CAE/FOS 结果级判据本机未测”。
- **缺什么**：真实 FEA 求解器或与求解器的稳定接口；网格无关性；材料本构；载荷/约束校验；结果解释与安全系数闸门。
- **验收判据**：与解析解/标准算例对比误差 ≤5%；网格加密后应力变化 ≤2%；FOS<1.5 必须判红且给出可追溯的应力云图/路径；不允许只给一个数。

### C5 CAM / 工艺条件

- **现状**：`process` 族只算 n/vf/MRR/Ra/T；`collision` 族只做 Z 平面算术；CIMCO 59 分、SSCNC 60 分；VERICUT 能出数但复现性依赖窗口焦点，`vericut.bat -b` 实测 `IDLE_KILLED`。
- **缺什么**：刀轨生成、刀具/夹具碰撞、后处理方言（FANUC Macro B / Siemens / Heidenhain）、G 代码语义校验、VERICUT Auto-Diff 红蓝绿判读、SSCNC 面板 CRT 回读。
- **验收判据**：VERICUT Auto-Diff 全绿；G00 快速移动 0 次切入毛坯；循环时间与 CAM 预测偏差 ≤5%；后处理代码在目标控制器仿真通过；每条结论附仿真截图/日志。

### C6 生产系统集成条件

- **现状**：无 MES/ERP/SPC/OEE/OPC UA/ISA-95 实现；没有工单、批次、追溯、质量闭环；没有设备数据接入。
- **缺什么**：ISA-95 分层接口、OPC UA 客户端、工单/批次模型、SPC 控制图、OEE 计算、质量追溯链。
- **验收判据**：能从模拟 MES 拉取工单并回写结果；SPC 越界自动告警；任一零件可追溯到毛坯批次、刀具、程序版本、操作员与检测记录。

### C7 自主闭环条件

- **现状**：世界模型契约明确禁止 tool/arguments 键，是单轮“换算器”；`VirtuSuperAgent` 的 AUTONOMOUS/REACT/MODALITY 可用，但 SWARM/Blackboard 写锁/Meta-SOP 仍是规划（AGENTS.md 状态表）；桌面接入报告只验证了 `desktop_status`，没有工业动作闭环。
- **缺什么**：工具调用与规划、多轮纠错、任务分解、失败恢复、不确定性量化与拒答、人机交接协议。
- **验收判据**：N 步（≥5）工业任务成功率 ≥90%；工具调用参数错误率 ≤1%；不确定时主动拒答/升级而不是编造；失败后可回滚到上一稳定状态。

### C8 工程化 / 部署条件

- **现状**：Q4_0、4.61 GB、6 GB 卡上 4.42 tok/s、27 s/例；8192 ctx 直接 OOM；无并发压测、无 p95 SLA、无看门狗/自动恢复、无模型注册与灰度回滚、无全链路 trace。
- **缺什么**：显存预算与上下文策略、服务看门狗、并发与队列、p95 时延 SLA、模型版本注册/灰度/回滚、指标与日志、成本模型。
- **验收判据**：目标硬件上 24 h 无 OOM；p95 时延 ≤ 目标值；并发 N 路无 5xx；模型切换可一键回滚；每次请求有 `run_id`/`served_model`/token 统计。

### C9 合规 / 安全 / 认证条件

- **现状**：有越狱审计与反幻觉护栏，但没有 ISO 9001 / IATF 16949 质量体系、IEC 61508 / ISO 13849 功能安全、ISO 42001 AI 管理、出口管制与数据合规证据；没有模型决策的可审计依据链。
- **缺什么**：质量手册与程序文件、风险评估（ISO 12100）、功能安全等级论证、AI 风险管理、数据分类分级、供应链与出口合规、责任边界。
- **验收判据**：第三方或客户审核通过；每个高风险输出可追到标准条款与验证记录；安全相关功能有独立于模型的硬闸门（不能只靠提示词）。

### C10 组织 / 验收条件

- **现状**：没有 FAT/SAT、MSA（GR&R）、Cpk、PPAP、首件检验、操作员培训与变更控制；模型更新没有“重新验证”强制流程。
- **缺什么**：工厂验收测试计划、测量系统分析、过程能力研究、首件检验、变更控制委员会、操作员与维护培训。
- **验收判据**：FAT/SAT 记录齐全；GR&R ≤10%；关键尺寸 Cpk ≥1.33；首件检验通过；每次模型/提示词/数据变更都触发回归与重新放行。

---

## 5. 优先级路线

### P0（不做就不能谈“工业”）

1. **权重级修复“算式不执行 / 参数绑错 / 字段不全”**：把本轮 22 例失败轨迹并入 repairloop 语料，重训后在**每族 ≥30 例**上复评；验收线：数值字段正确率 ≥90%、宣称≠参数 ≤1%、严格通过 ≥85%。
2. **服务形态先成立**：6 GB 卡上 8 KB 契约 + 8192 ctx 不可用；需 ≥12 GB 显存，或 KV 量化 + 契约压缩 + 看门狗；24 h 无 OOM 才允许继续。
3. **建立统计上站得住的封缄评测**：每族 ≥30 例、多 seed、两轮独立 run、CI 与判分器噪声标定；停止用 n=2 的分数做发布结论。
4. **真实 CAD/CAE/CAM 闭环 FAT**：STEP 往返、FEA 算例、VERICUT Auto-Diff、G00 碰撞、后处理方言，全部要可回读证据。

### P1

5. 标准/材料/刀具/机床知识库接入模型（检索 + 引用 + 缺参报错）。
6. 工具调用、规划、多轮纠错、不确定性/拒答。
7. MES/OPC UA/SPC/OEE 集成与追溯链。
8. 并发、p95、灰度、回滚、可观测性。

### P2

9. 合规认证（ISO 9001/IATF 16949/IEC 61508/ISO 42001）。
10. 数字孪生、持续学习与漂移监控、操作员培训与变更控制。

---

## 6. 复现命令

```powershell
# 1) 身份（权重内容哈希、Modelfile、脚本哈希）
python -c "import hashlib,json,subprocess; ..."   # 见 runs/industrial_eval_20261112/identity.json

# 2) 护栏门禁（应 14/14 PASS）
.venv\Scripts\python.exe scripts\wm_ci_gate.py

# 3) 独立留出集 22 例（需 Ollama 已启动且模型在库）
.venv\Scripts\python.exe -u scratch\run_holdout_model.py

# 4) 分维度复算（数值/闸门/文本/宣称≠参数）
.venv\Scripts\python.exe scratch\analyze_industrial_eval.py runs\industrial_eval_20261112\holdout22_model.json

# 5) 12 族评测器（本轮因 6GB 显存 OOM 未完成 120 例；换 ≥12GB 卡后可跑）
.venv\Scripts\python.exe scripts\eval_worldmodel.py --model virtu-wm-v3:chatml --n 120 `
  --system-mode contract --out runs\industrial_eval_20261112\raw_records_contract.json
```

---

## 7. 证据清单

| 证据 | 路径 |
|---|---|
| 被测身份 | [identity.json](file:///d:/Virtu模型/runs/industrial_eval_20261112/identity.json) |
| 护栏门禁 14/14 | [ci_gate.log](file:///d:/Virtu模型/runs/industrial_eval_20261112/ci_gate.log) |
| 22 例原始响应 | [holdout22_model.json](file:///d:/Virtu模型/runs/industrial_eval_20261112/holdout22_model.json) |
| 22 例分维度复算 | [summary_holdout22_model.md](file:///d:/Virtu模型/runs/industrial_eval_20261112/summary_holdout22_model.md) |
| 12 例补充臂（不同服务配置） | [raw_stream_contract_cfgA_gpu24_ctx6144.jsonl](file:///d:/Virtu模型/runs/industrial_eval_20261112/raw_stream_contract_cfgA_gpu24_ctx6144.jsonl) |
| 同权重生产终评 | [PRODUCTION_FINAL_EVAL_2026-11-08.md](file:///d:/Virtu模型/benchmarks/PRODUCTION_FINAL_EVAL_2026-11-08.md) |
| 生产适用性榜单 | [PRODUCTION_LEADERBOARD_2026-11-08.md](file:///d:/Virtu模型/benchmarks/PRODUCTION_LEADERBOARD_2026-11-08.md) |
| 六软件熟练度 | [SIX_SOFTWARE_PROFICIENCY_SCORECARD_2026-11-12.md](file:///d:/Virtu模型/reports/SIX_SOFTWARE_PROFICIENCY_SCORECARD_2026-11-12.md) |
| 世界模型修复链 | [ENGINEERING_WORLD_MODEL_FIX_2026-11-11.md](file:///d:/Virtu模型/benchmarks/ENGINEERING_WORLD_MODEL_FIX_2026-11-11.md) |
| 训练语料 manifest | [MANIFEST.md](file:///d:/Virtu模型/data/sft_rebalanced/MANIFEST.md) |
| OOM 现场 | `C:\Users\Administrator\AppData\Local\Ollama\server.log` L22526–22540 |

---

## 8. 未测项与限制（不得当作已通过）

1. 120 例主评测未完成（6 GB 显存 OOM）；主证据是 22 例独立留出集 + 12 例补充臂。
2. 未启动 SOLIDWORKS / AutoCAD / NX / CIMCO / VERICUT / SSCNC；桌面闭环能力不在本轮结论内。
3. 未测多模态/图纸 OCR、工具调用、多轮对话、长上下文（>5120）、并发与 24 h 稳定性。
4. 未测 CAE 结果级判据（网格、接触、疲劳、热、屈曲）与 VERICUT Auto-Diff 红蓝判读。
5. 严格判分要求回填题面输入量；本报告已把“缺字段”与“算错”分开统计，未混为一谈。
6. 重复性只观察到一次同题异果（1.04 vs 1.46），未做受控多轮实验；不得据此宣称稳定或不稳定。
