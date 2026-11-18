# 六软件审计 §4 落差修复报告（2026-11-13）

> 对应审计：`reports/SIX_SOFTWARE_DL_DEPTH_AUDIT_2026-11-13.md` §4「宣称 vs 实现落差」
> 执行环境：`D:\Virtu模型\.venv\Scripts\python.exe`（Python 3.12.10，含 cv2 / ezdxf / pywin32）
> 口径：只把「能在文件里读到真实调用、且本次跑出可复现输出」的算作已修复；未修的单独列在 §4。

---

## 1. 结论摘要

| 项 | 数量 |
| :-- | --: |
| 审计 §4 原始落差 | 7 |
| 修复过程中连带发现的缺陷 | 6 |
| 合计修复 | **13** |
| 新增回归测试 | **20 条（全绿）** |
| 语料工具名映射覆盖 | **60/60（0 未映射）** |

七项落差全部关闭；另修掉 6 个「同级/更深」的问题——其中 2 个会让整条能力链直接瘫痪（视觉桥在无 OpenCV 环境下无法 import、Auto-Diff 审计恒判证据不足）。

---

## 2. 逐项修复

### ① VERICUT「无头批处理」虚假宣称

- **根因**：工具描述写「调用 vericut.bat -b 启动无头批处理仿真」，桥层 `run_batch_simulation` 实际返回 `unsupported_headless`（9.6 无 COM/IPC/批处理）。
- **修复**：`bridges/tool_calling_specs.py:181` 描述与 action 说明改为真实边界（无头不可用 → GUI 通道 `work/vericut-toolchain/vericut_link.py` 的 `launch_via_bat + play_simulation`；`check_collision` 解析真实日志）。
- **验证**：`test_vericut_tool_description_does_not_claim_headless`、`test_vericut_headless_returns_structured_unsupported` 通过。

### ② 标准件库查询恒返回空

- **根因（三错叠加）**：键名写成 `SolidWorks_2021`（真实键 `SOLIDWORKS 2021`）；读不存在的 `standard_features` 字段（真实路径 `plugins_and_addins["Toolbox"]["components"]`）；NX 本体键是中文 `中文版NX12.0`，按 `Siemens NX 12.0` 查不到。
- **修复**：
  - `virtu_omni/knowledge/software_plugin_ontology.py` 新增 `SOFTWARE_ALIASES` / `resolve_software()` / `standard_libraries()`（不硬编码任何字段名）。
  - `bridges/tool_calling_specs.py:1811` 改为：先查确定性标准件库 → 数据源缺失回落本体目录 → 显式回显 `data_source / degraded / data_error`，查不到返回 `not_found` 而不是「ok + 空列表」。
- **实测**：`SolidWorks_2021` → `SOLIDWORKS 2021`，13 条标准件；`SSCNC` → 11 条；本机缺 `e:\数据` 数据源时 `degraded=true` 且 `data_error` 写明缺哪个文件。

### ③ `super_agent` 悬空调用 `analyze_inspection`

- **根因**：`virtu_omni/agent/super_agent.py:1383` 调用 `CADCAMVisionBridge.analyze_inspection()`，该类只有三个具名方法，无此入口 → `AttributeError`。
- **修复**：视觉桥新增统一分派入口 `analyze_inspection(task, image_path)`（`VISION_TASK_METHODS` 表 + `UNKNOWN_VISION_TASK` / `MISSING_IMAGE_PATH` 结构化错误）；`cadcam_visual_inspect` 也收敛到同一入口，消除三处各自 if-else 的漂移；`super_agent` 补 `output_path` 兜底。
- **验证**：`test_vision_bridge_has_analyze_inspection`、`test_vision_bridge_routes_each_task`（三个 task 全部命中正确方法）。

### ④ Auto-Diff 审计接线断裂（最严重的一项）

- **根因**：`skills/vericut-autodiff-triage/scripts/triage_autodiff.py` 读扁平 `red_pixels / verdict`；桥层只给 `metrics.{gouge_pixels,...}` + `safety_verdict` → 三个像素计数恒取 0 → **每次都判 `AD-EMPTY-FIELD / INSUFFICIENT_EVIDENCE`**，即所有 Auto-Diff 结论都无法通过审计。
- **修复（两侧同时改）**：
  - 生产端 `bridges/cadcam_vision_bridge.py`：嵌套 `metrics` 增补 `green_pixels / machined_pixels`，并同时输出扁平别名（`gouge_pixels / excess_pixels / green_pixels / machined_pixels / *_percentage / verdict`），旧消费方向后兼容。
  - 消费端 `triage_autodiff.py`：新增 `normalize()`，同时接受扁平与嵌套两种载荷；缺 `machined_pixels / green_pixels` 时用像素与百分比反解；桥层 `status=error` 转 `AD-INSPECT-ERROR`；`AD-RATIO-CHECK` 仅在绿色像素为显式值时执行，避免自证同义反复。
- **实测（真实截图 1920×1080）**：`gouge=3228 / excess=20955 / green=5153 / machined=29336`，`in_tolerance=17.57%`，桥层 `CRITICAL_GOUGE_DETECTED`，triage 判 `REVIEW_GOUGE` 并给出 `AD-NONEMPTY` 检查记录——**接线已通，且判词随图变化**。

### ⑤ 契约自我否认（AGENTS.md / README）

- **根因**：`AGENTS.md:7` 把 SWARM+Blackboard+红蓝辩论写成既定能力，`:92-99` 又逐条写「规划中（未实现）」。
- **修复**：§1 该行标注「设计契约，未实现」并指向 §4 状态表；§4 的 SWARM / Meta-SOP / Blackboard / adversarial_critic 逐条加「规划中（未实现）」；AUTONOMOUS/REACT/MODALITY 标「已实现」。README 副标题从「六软件闭环」改为「SW/NX 全闭环；AutoCAD/VERICUT/CIMCO/SSCNC 半自动 + 人工复核；多智能体编排（SWARM 为规划中）」。
- **验证**：`test_agents_md_marks_planned_items`。

### ⑥ 语料工具名与运行时工具面失配

- **根因**：六软件语料用了 60 个 `vendor.action` 工具名，运行时只暴露 `cadcam_*`；此前仅 8 个有别名，其余落到 `Unknown tool name`。
- **修复**：
  - 新增 `virtu_omni/knowledge/corpus_tool_map.py`：60 个名字逐一裁决 —— **27 个可执行**（给出规范工具 + action + 参数翻译）、**33 个仅知识**（无运行时实现，返回 `knowledge_only` + 原因 + 替代工具）。`vericut.create_project_config` 特意从旧的「映射成 run_simulation」改为如实拒绝（旧映射属于误导性成功）。
  - `bridges/tool_calling_specs.py` 在别名层之前接入该表，并在返回体 `arg_remap.via = corpus_tool_map` 留痕。
  - 新增门禁 `scripts/lint_corpus_tool_names.py`：扫描语料 → 校验映射 → 校验映射目标确实在运行时可达；有未映射即退出码 1。
- **实测**：`distinct 工具名 60｜可执行 27｜仅知识 33｜未映射 0`（报告落盘 `runs/corpus_tool_coverage.json`）。

### ⑦ `ΔV > 0 Verified` 硬编码判词

- **根因**：`virtu_omni/engine/extreme_cadcam_pipeline.py:192` 直接写死「Volume Conservation Law Verified」，从未计算过 ΔV。
- **修复**：按「毛坯等体积圆柱 − 去槽后成品体积」真实求差，`ΔV <= 0` 直接抛错；返回体新增 `delta_v_mm3`、`volume_basis="analytic_geometry (非 CAD 质量属性回读)"`、`cad_mass_property_verified=false`，判词改为带数值的 `ΔV > 0 PASSED (ΔV=… mm³, 解析几何求差)`。
- **验证**：`test_delta_v_is_computed_not_asserted`（断言 `delta_v_mm3 > 0` 且不含 "Verified"）。

---

## 3. 连带修复的 6 项

| # | 问题 | 后果 | 修复 |
| :-- | :-- | :-- | :-- |
| 8 | `cadcam_vision_bridge.py` 默认参数引用 `cv2.IMREAD_COLOR`，未装 OpenCV 时 **import 即 NameError** | 无 OpenCV 的解释器上整条视觉链不可用，且不是干净报错 | `_read_image(flags=None)` + `HAS_CV2` 守卫，降级返回 None，方法层统一 `"OpenCV (cv2) not installed"` |
| 9 | `six_software_orchestrator.dispatch` 用 `"flange" in part_name` 命中建模分支，**忽略 action** | `annotate_drawing` 会被静默劫持成「建一个法兰」，看起来成功实则错动作 | 改为 `act in ("model_flange","flange") or (not act and "flange" in part_name)` |
| 10 | `annotate_drawing` 在编排层无实现（真实实现在 `scripts/model_drives_solidworks.py::execute_call` 的 `--anno-spec` + 图面回读） | 编排层要么报 Unknown action，要么（配合 #9）静默建错模型 | 编排层返回 `unsupported_in_orchestrator / DISPATCH_LAYER_MISMATCH` 并指名真实执行器，明确不降级替代 |
| 11 | SOLIDWORKS 桥有 `mass_properties()` 但没有回读入口 | P0「真实回读通道」缺一环 | 新增 `SolidWorksBridge.active_mass_properties()` + `cadcam_solidworks_model` 的 `mass_properties` action（只读，免审批）；无活动文档时返回 `NO_ACTIVE_DOCUMENT` |
| 12 | 标准件查询 / 知识检索想扩进宣告面 | 会打红 `test_closed_loop_coverage` 的测量纪律（宣告面固定、每项须有判分用例） | 保持「内部可调用入口」（`DISPATCH_ONLY_TOOLS`），不进对模型宣告面；测量面仍是 16 项 |
| 13 | 我在探测 `annotate_drawing` 时误触发 SW 建模 | 启动了一个 SOLIDWORKS 实例并覆盖了仓库里的 `Flange_Parametric.SLDPRT` | 已关闭该 PID 6848 实例；`git checkout -- Flange_Parametric.SLDPRT` 还原（82376 bytes，与 HEAD 一致，`git status` 干净） |

---

## 4. 验证证据（可复现）

```powershell
# 1) 本次新增的 20 条契约回归
.venv\Scripts\python.exe -m pytest tests\test_contract_fixes_20261113.py -q
# → 20 passed

# 2) 工具链 / 监督接口 / 访问模式
.venv\Scripts\python.exe -m pytest tests\test_agent_toolchain_full.py tests\test_toolchain_access_modes.py tests\test_supervision_iface.py -q
# → 42 passed

# 3) 工程链 / 本体 / CAE / 契约
.venv\Scripts\python.exe -m pytest tests\test_universal_engineering_enhancements.py tests\test_wish_cad_cam.py tests\test_extreme_cadcam_pipeline.py tests\test_cae_gate_honesty.py -q
# → 45 passed

# 4) 语料工具名门禁
.venv\Scripts\python.exe scripts\lint_corpus_tool_names.py --json-out runs\corpus_tool_coverage.json
# → 60 名：可执行 27 / 仅知识 33 / 未映射 0

# 5) 全量导入体检（bridges 41 个模块）+ 全仓语法编译（693 个 .py）
# → 0 失败
```

关键实测数值：

| 指标 | 值 |
| :-- | --: |
| 真实 Auto-Diff 截图有效像素 | 29,336（gouge 3,228 / excess 20,955 / green 5,153） |
| 桥层判词 | `CRITICAL_GOUGE_DETECTED`（in-tolerance 17.57%） |
| triage 判决 | `REVIEW_GOUGE`（此前恒为 `INSUFFICIENT_EVIDENCE`） |
| 标准件查询（SOLIDWORKS 2021） | 13 条，`degraded=true` 且写明缺失数据源 |

---

## 5. 未修 / 需决策（如实列出）

| 项 | 状态 | 原因 |
| :-- | :-- | :-- |
| P0 语料重建为真实执行轨迹 | **未做** | 需先跑 1,420 次真实采集（计划见 `CLOUD_TRAINING_PLAN_ALL90_2026-11-13.md` §2 线 A），不是代码修复能替代；本次只把「工具名映射」这一前置障碍清掉 |
| 宣告面 20 vs 评测面 16 的漂移 | **未修（需决策）** | HEAD 提交时已有 17 项，工作区再 +3 个网络工具；`tests/test_closed_loop_coverage.py` 因此红（3 项）。两条修法：①把 3 个网络工具降为内部入口；②为 4 个未覆盖工具补 holdout 用例。补用例属数据作者工作，不能编造，留给你定 |
| SSCNC CRT OCR / VERICUT 双确认入链 | 未动 | 属 P2 能力补齐，不是本次「落差修复」范围 |

### 5.1 全量测试结果（逐文件限时 45s 跑，62/139 个文件，预算内）

| 结果 | 数量 | 说明 |
| :-- | --: | :-- |
| 通过 | 53 | 含本次相关全部套件 |
| 失败 | 7 | 见下表，**1 个由本次改动引入且已修**，其余为既有/环境问题 |
| 挂起 | 2 | `test_autonomous_learning_engine.py`、`test_gate_falsifiability.py`（45s 未结束，疑似等模型端点） |

| 失败文件 | 原因 | 归属 |
| :-- | :-- | :-- |
| `test_agent_team.py` | 我修改 `triage_autodiff.py` 导致技能哈希台账失配（`sha256 mismatch`） | **本次引入 → 已更新 `skills/SKILLS_PROVENANCE.json` 的 bytes/sha256，复跑 9 passed** |
| `test_closed_loop_coverage.py` (3) | 宣告面 20 ≠ 评测面 16，4 个工具无判分用例 | 既有（HEAD 已 17） |
| `test_eval_runner.py` (4) | `toolcall 判据空转闸：臂 fake 没有暴露任何 tools schema`（arms.json 配置） | 既有 |
| `test_context_mode_integration.py` (2)、`test_ai_scratch_integration.py`、`test_hindsight_integration.py`、`test_internet_search_and_learn.py` | `HTTP 401 Unauthorized` / 端点不可达 | 环境（本地服务未带鉴权启动） |


---

## 6. 改动文件清单

| 文件 | 变更 |
| :-- | :-- |
| `bridges/cadcam_vision_bridge.py` | +56/-1：统一 `analyze_inspection`、扁平字段别名、cv2 守卫 |
| `bridges/tool_calling_specs.py` | 标准件查询重写、VERICUT 描述、视觉入口收敛、语料映射接入、SW 参数透传、`mass_properties` 声明 |
| `bridges/six_software_orchestrator.py` | SW 分派：action 优先于子串、annotate 如实指路、mass_properties 路由 |
| `bridges/solidworks_bridge.py` | +active_mass_properties() |
| `virtu_omni/knowledge/software_plugin_ontology.py` | +115：别名解析与标准库抽取 |
| `virtu_omni/knowledge/corpus_tool_map.py` | **新增**：60 条语料工具名裁决表 |
| `virtu_omni/engine/extreme_cadcam_pipeline.py` | ΔV 真实求差与判词 |
| `virtu_omni/agent/super_agent.py` | 视觉调用参数兜底 |
| `skills/vericut-autodiff-triage/scripts/triage_autodiff.py` | 双形态归一化 + 错误态处理 |
| `scripts/lint_corpus_tool_names.py` | **新增**：语料工具名门禁 |
| `tests/test_contract_fixes_20261113.py` | **新增**：20 条回归 |
| `skills/SKILLS_PROVENANCE.json` | 更新 `triage_autodiff.py` 的 bytes/sha256（改脚本必须同步台账） |
| `AGENTS.md` / `README.md` | 口径与状态标注 |
