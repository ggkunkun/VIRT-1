# 工程世界模型全面修复报告（2026-11-08）

口径：本文所有数字标 `measured`（本会话实跑命令产出）/ `asserted`（源码静态事实）/ `未测`。
证据文件与复现命令随每项给出。遵守工作区「测量宪法」：不把源码字面量当测量结果。

## 0. 范围与基线

被测对象 = `scripts/wm_*.py` + `eval_worldmodel.py` + `anti_hallucination_guard.py` +
`guard_hooks.py` + `build_worldmodel_{sft,v2}.py` + `build_physics_acceptance_cases.py` +
`virtu_eval/derivation.py` + `data/sft/virtu_worldmodel*.jsonl` +
`data/benchmark/virtu_eval_phys_v1/*.jsonl` + 两份 wm Modelfile。

| 项 | 结果 | 口径 |
|---|---|---|
| 首次核心 pytest | `45 failed, 131 passed, 1 error` | measured，15:20 首跑 |
| 接手时稳定基线 | `35 failed, 141 passed, 1 error` | measured，连续两次一致 |
| 修复后核心四套 | `187 passed, 1 error` | measured，error 为环境守卫，见 §4 |
| 只读审计初版 | `13/26 PASS` | measured，`scripts/wm_audit_full.py` 首跑 |
| 只读审计终版 | `27/27 PASS` | measured，新增 1 项端到端回放 |
| 评测链路期望答案回放 | `27/27 raw, 27/27 delivery` | measured，**不是模型实测** |
| 真实模型端到端评测 | **未测** | Ollama `/api/tags` 返回 `{"models":[]}` |

⚠️ 并发写入事实（measured）：15:45–16:04 期间工作区有另一进程持续改同一批文件
（`virtu_eval/derivation.py`、`physics.jsonl`、多个 `scripts/*.py`、新增 tests）。
因此 `45 → 35 failed` 的变化**不全部归因于本会话**；gold/LAWS 三源对齐由该进程完成，
本会话只接手其余缺陷并做独立验证。所有结论以最终磁盘状态为准。

## 1. 求解器与判分尺子（阻断级）

1. **L1 可被内层 `invalid` 键整体绕过** — `wm_verifier.py:l1_check`
   `ws.get("invalid") is True or ws.get("world_state") is None and ws.get("invalid")`：
   `and` 优先于 `or`，且 `ws` 是 world_state 内层、恒无 `world_state` 键 →
   塞任意 truthy `invalid` 即让 REQUIRED / 守恒 / 正值 / 量纲四道检查空转。
   实测：正常 2 issues，加 `{"invalid":1}` 后 0 issues。
   修复：仅当内层是「纯 invalid 声明」（键集合 ⊆ {invalid, reason} 且 `invalid is True`）才放行。
2. **`recompute` 缺参/除零抛异常，`verify()` 崩而 Guard 假绿** — `wm_verifier.py`
   除 removal 外 10 族直接下标 `s["..."]`；实测 10 个畸形场景全部抛
   KeyError/ZeroDivisionError，`verify()` 直接崩，Guard 却 `except: ref=None` 走 accept。
   修复：拆 `_recompute_unsafe` + `recompute` 包装，统一捕获并返回 `{}` + WARN；
   额外拦截 inf/NaN（如 `sigma=0` 时 FOS=inf 不是合法 JSON 数值）。
   `verify()` 见空 ref 升级 `escalate_solver`（fail-closed）。
3. **判分器把数组键当 float** — `eval_worldmodel.py:judge`
   `component_tolerances_mm` / `centroid_mm` 登记在契约 numeric 分区但取值是 list，
   `float(...)` 抛 TypeError → tolerance / mass_props 两族标准答案判自己都 FAIL。
   修复：`_cmp_array` 逐元素相对容差比对。实测两族自判由 False → True。
4. **护栏丢弃 design 规格子树** — `anti_hallucination_guard.py` / `eval_worldmodel.py`
   Guard 取 `corrected = ws_flat`，顶层 design/process_plan/... 全部丢失 →
   同一条设计答案原生 PASS、交付后 7 个规格键 missing 判 FAIL。
   修复：展平/改名表下沉为 `wm_contract.merge_nested_top`（**单一真源**），
   判分器与护栏共用；只接纳契约登记键。实测 `design guard judge True, miss=[]`。
5. **护栏分冒充模型能力分** — `eval_worldmodel.py`
   Guard 在 L2 分支无条件 `corrected.update(ref)`，护栏后通过率测的是求解器
   （历史 `_eval_wm_a1.json`：guard 40/40 vs raw 19/40，rejected=0）。
   修复：不改产品纠正行为，但逐条记录 `solver_overwrote_fields` 与 `pass_basis`，
   汇总明写「原生通过 = 模型能力（唯一可归因指标）；护栏后 = 交付形态」。
6. **gold / LAWS / recompute 三源对齐**（并发进程完成，本会话验证）
   `physics.jsonl`、`derivation.jsonl` 用 `build_physics_acceptance_cases.py` 重派生
   （30 cases，tiers 9/15/6），`virtu_eval/derivation.py` 的 LAWS 补齐照抄量字段。
   实测核心四套 187 passed。

## 2. 物理与公式

7. **collision 判据语义矛盾**：旧式「两条件同时成立才 high」会产出
   `gouge=True`（已过切、autodiff=red）却 `collision_risk="none"`。
   实测 600 条生成样本 81 条矛盾、且与求解器零不一致 → 判据本身错，不是数据错。
   修复：gouge 单独构成充分条件，四处同源 —— `wm_verifier.recompute`、
   `build_worldmodel_sft.gen_collision_gcode`、`wm_schema.FAMILY_CARD`、
   `build_physics_acceptance_cases.py` 题面描述。实测 0/600 矛盾。
   已发布 physics benchmark 的三个 collision 用例判据不变（重生成后仍 30 cases 全绿）。
8. **`wm_gate.normalize` 覆写 `collision_risk`**：`gouge=True` 就改成 high，
   与求解器/定律卡/训练标签冲突。修复：判定权归求解器，闸门只推 autodiff。
9. **tolerance 族 100% 单类**：旧采样使 `clearance` 恒 ≥0，过盈/过渡/
   `tolerance_pass=False` 从未训练；且 `tolerance_fit`(阈值 0) 与 `fit_class`(±0.01)
   用了两套阈值，标签自相矛盾。修复：三类均衡采样 + 与 `wm_gate` 同源的 ±0.01 口径。
   实测三类 fit 与 True/False 两种 pass 均出现。
10. 已由并发进程修复并经本会话复验：`wm_eval` 隐式乘法 `)(` → `))(`、
    `wm_derivation` 圆柱 `inertia_izz_mm4` 差 2 倍、`distill_local_solver` mm⁵/mm⁴ 错标、
    `worldmodel_infer` 缺 `think:false`/`format`/`num_predict`/encoding 与类型导入、
    `wm_probe` 私持第二把尺子（现 delegate 到官方 judge）。

## 3. 契约、解码与语料

11. **契约允许 / 解码禁止**：`wm_schema.wide_schema()` 顶层只有 5 键 +
    `additionalProperties:false`，会把契约允许的 `design`/`process_plan`/`adaptation`/
    `correction` 整块掐掉。修复：补 6 个结构键。
12. **`build_wm_modelfile.py --check` 闸门空转**：只扫 numeric、打印「8 族」。
    修复：扫 12 族全部数值/闸门/文本/布尔键 + 定律卡 + 契约↔解码同源对账。
13. **SFT 语料落盘缺陷**：新增 `scripts/normalize_wm_corpus.py`（幂等、可审计）：
    - 去重：v1 69 条、v2 24 条、distilled/train 各 5 条；
    - `world_state` 非法键归档：`_solver` 81 条、错放内层的 invalid/reason/
      expected_action、autocad 的 `blueprint_dims_mm`/`n_dims`；
    - 用求解器按 scenario 重派生 collision 标签 87 条、tolerance 判定 6 条；
    - 生成器落盘前加确定性去重。
    两个主语料重生成：v1 610 条（scen=610, deriv=607）、v2 2025 条（scen=1629）。
    `normalize_wm_corpus.py --apply` 的落盘复核 `[verify] ALL CLEAN`，
    报告 `benchmarks/WM_CORPUS_NORMALIZE_2026-11-08.json`。
14. **两份 Modelfile 是陈旧快照**：
    - `checkpoints/virtu-wm-v3.Modelfile`：8 族词表 + 桌面工具规范（格式竞争）+ 反斜杠 FROM。
      用 `build_wm_modelfile.py --mode world` 重生成（纯契约 SYSTEM 7941 字符、
      12 族键全量下发、无 `cadcam_desktop_gui`、FROM 正斜杠）。
    - `modelfiles/virtu-13.63b.wm-v1.Modelfile`：SYSTEM 混入整套桌面键鼠规范，
      参数与 `VIRTU_WM_STRENGTHENED_2026-11-07.md` 声明漂移
      （temp 0.2↔0.1、top_k 40↔20、repeat_penalty 1.15↔1.02、num_gpu 缺失、stop 不符）。
      修复：删工具规范、补纯契约铁律、参数对齐文档、FROM 改正斜杠。
    - 构建器路径处理改为 `abspath().replace(os.sep, "/")`。

## 4. 验证矩阵（全部 measured）

| 命令 | 结果 |
|---|---|
| `.venv/Scripts/python.exe scripts/wm_audit_full.py` | `27/27 PASS`，exit 0 |
| `pytest tests/test_solver_graders.py tests/test_physics_case_set.py tests/test_derivation_registry.py tests/test_physics_reference_honesty.py -q` | `187 passed, 1 error` |
| `python scripts/wm_verifier.py --selftest` | `ALL PASS`（含 2 条新增反证闸门） |
| `python scripts/wm_gate.py` | `18/18 PASS`（含 collision_risk 不覆写反证） |
| `python scripts/wm_schema.py` / `wm_contract.py` | `CROSS-CHECK ALL PASS` / `KEY_VOCAB OK` |
| `python scripts/anti_hallucination_guard.py --selftest` / `guard_hooks.py` | `ALL PASS` / `7/7 PASS` |
| `python scripts/build_wm_modelfile.py --check` | `12 族 … 契约↔解码同源` |
| `python scripts/normalize_wm_corpus.py --apply --verify` | `[verify] ALL CLEAN` |
| 端到端期望答案回放 9 族 ×3 | `27/27 raw, 27/27 delivery`，0 假失败 |

**1 个 error 的归因**：`test_run_exporter_labels_triples_with_the_graders_verdict`
在 `tmp_path` fixture 清理时被宿主 `sitecustomize` 的 `SAFE_DELETE_BULK_GUARD`
以 `SystemExit(1)` 拦下，堆栈在 `sitecustomize.py:1249`，与被测代码无关（asserted：
单独运行同一测试复现同一环境栈；换目录/关守卫后可跑）。

**全量 `pytest tests/` 收集阻断**：3 个无关文件
（`test_autonomous_learning_engine.py`、`test_internet_safety_filter.py`、
`test_internet_search_and_learn.py`）因 `.venv` 缺 `bs4` 在 import 阶段报错，
属 `virtu_omni.internet` 依赖，不在本次修复范围。
排除这 3 个文件后跑全量，6m52s 仍无输出（套件内另有长时/网络型测试挂住），
已主动终止，不把它记作通过或失败；结论只取上表的确定性子集。

## 5. 未测 / 残留（明确标注，不冒充完成）

- **未测：真实模型端到端评测**。Ollama `/api/tags` 实测 `{"models":[]}`
  （托盘把 `OLLAMA_MODELS` 改回默认目录，见 11-07 日志）。因此本报告所有通过率
  都是「尺子自检 / 期望答案回放」，**不是模型能力分数**。需先恢复模型库再跑
  `python scripts/eval_worldmodel.py --model <tag> --n 120 --out _eval_wm.json`。
- **未测：重训**。语料与 Modelfile 已刷新，但权重未变；新语料需
  `train_world_model_final.py --build` 合并 + 重训才生效。
  `data/sft/virtu_final_train.jsonl`（3017 条混合语料，mtime 11-03）**未改动**：
  它是 agentic 多轮 + 世界模型混合件，规范化会破坏其多轮结构，且不属于本次契约范围。
- **需手工生效**：两份 Modelfile 修改后必须 `ollama create <tag> -f <file>` 重新注册。
- **设计保留**：Guard 仍会在 L2 用求解器全量覆盖数值（产品纠正行为），
  现由评测侧 `solver_overwrote_fields` / `pass_basis` 保证分数可归因。
- **未处理**：`virtu_real_backend.py` 自带两份转速公式，与 `LAWS` 不同源（历史台账遗留，
  属另一条链路）；`build_worldmodel_v2.py` 的 `max(V,1.0)` 静默夹紧仍在。

## 6. 复现

```bash
cd /d/Virtu模型
./.venv/Scripts/python.exe scripts/wm_audit_full.py            # 27/27
./.venv/Scripts/python.exe -m pytest tests/test_solver_graders.py \
  tests/test_physics_case_set.py tests/test_derivation_registry.py \
  tests/test_physics_reference_honesty.py -q                    # 187 passed
./.venv/Scripts/python.exe scripts/normalize_wm_corpus.py --dry-run
./.venv/Scripts/python.exe scripts/build_wm_modelfile.py --check
```
