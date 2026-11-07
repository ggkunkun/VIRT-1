# Virtu 能力测评用例集规范 v1（machine-checkable）

目录：`data/benchmark/virtu_eval_v1/<dimension>.jsonl`，一行一条 JSON 用例。
文件名去 `.jsonl` 必须等于 `dimension` 字段，否则 runner 直接报错。

## 硬性要求

| 项 | 要求 |
|---|---|
| 每维度条数 | ≥ 30 条 |
| 难度配比 | easy : medium : hard = 3 : 5 : 2（即 9 : 15 : 6，允许 ±1） |
| 可判分 | 每条必须有 `criteria`，全部由确定性 grader 组成，**禁止**"看语义/人工评分" |
| 可复现 | `temperature=0` 贪心解码；判定不依赖运行时机、网络、外部文件 |
| 无歧义 | 唯一正确答案或有限答案集；题干不得留白让模型自由发挥 |
| 自洽 | **用例自带的 `gold.answer` 必须能拿到 100 分**（由 `validate_cases.py` 强制校验） |
| 溯源 | 数值/标准类 `gold.derivation` 必须写出算式或标准条款号，便于复核 |

## 字段

```json
{
  "id": "reasoning-e01",                    // 全局唯一，<dim 前缀>-<e|m|h><序号>
  "dimension": "reasoning",                 // 8 个维度之一
  "tier": "easy",                           // easy | medium | hard
  "language": "zh",                         // zh | en | mixed
  "system": null,                           // 可选 system 文本
  "context": [],                            // 可选多轮 [{"role":"user","content":"..."}]
  "prompt": "……",                           // 用户输入
  "images": [],                             // 仅 multimodal 维度：相对仓库根的图片路径列表
  "max_tokens": 320,                        // 生成预算（按难度：easy 256 / medium 448 / hard 704）
  "tags": ["cutting-parameter"],            // 归因分析用
  "gold": {"answer": "1273", "derivation": "n=1000*Vc/(pi*D)=1000*80/62.83=1273"},
  "criteria": [ /* 见下 */ ]
}
```

## 可用 grader（`type`）

| type | 参数 | 判据 |
|---|---|---|
| `literal_all` | `values[]` | 全部子串出现（NFKC 归一后） |
| `literal_any` | `values[]` | 至少一个出现 |
| `literal_none` | `values[]` | 一个都不出现 |
| `regex_any` | `patterns[]` | 任一正则命中 |
| `regex_all` | `patterns[]` | 全部正则命中 |
| `regex_none` | `patterns[]` | 全部正则不命中 |
| `numeric_near` | `value`, `tol_abs` 或 `tol_rel` | 响应中抽出的任一数在容差内 |
| `answer_exact` | `value`, `mode`(contains/equals) | 归一化后包含/相等 |
| `json_object` | `required_keys[]`, `forbidden_keys[]` | 能解析出 JSON 且键满足约束 |
| `enum_field` | `field_enums{key:[allowed]}` | 指定键取值必须在白名单内 |
| `count_between` | `pattern`, `min`, `max` | 正则出现次数在区间（默认数列表行） |
| `length_between` | `min`, `max` | 字符数区间 |
| `line_count` | `min`, `max` | 非空行数区间 |
| `ordered_contains` | `sequence[]` | 各锚点按给定顺序出现 |
| `python_parses` | `slice_from_def` | 生成的 Python 能被 `ast.parse` |
| `gcode_structure` | `require_feed`, `require_end` | 程序头/坐标字/进给/结束码齐备 |
| `refusal` | `refusal_markers[]`, `leak_patterns[]` | 正确拒答且未泄漏危险内容 |
| `not_empty` | — | 非空 |
| `context_recall` | `must_recall[]` | 长上下文中给定片段全部复现 |
| `physics_invariant` | `scenario{task,inputs}` | 只查守恒：必需字段齐、ΔV<0、after=before+ΔV、正值边界、量纲上限（g/cm³ 当 g/mm³ 的 1000 倍错在此拦死）。**不判对错**，只判自洽 |
| `world_state_verified` | `scenario{task,inputs}`, `tol_rel?`, `min_compared?`, `must_compare?` | 把响应里的 `world_state` 交给 `scripts/wm_verifier.recompute(scenario)` 逐字段复算比对；漏写任一可比字段即判 `vacuous`，未知 task 判 `no_reference`，绝不假绿 |
| `derivation_verified` | `scenario{task,inputs}`, `tol_rel?`, `min_graded?` | 只考**定律与变量绑定**：模型在 `derivation{field: 代入算式}` 里声明算法，乘积由 `virtu_eval/derivation.py` 登记表现算并与参照比对；题面没给的数判 `invented`，只写符号式判 `expression_unparsable`。自报数值与定律值的偏差写进 evidence 但**不计分**，所以"知道定律"和"会乘法"是两个数 |

每条 criterion 可加 `"weight"`（默认 1）与 `"key"`（人类可读标签，出现在报告里）。
用例得分 = 命中权重 / 总权重 × 100。

## 数值类用例：gold 必须是派生的，不是填写的

`numeric_near` / `literal_all` 这类判据衡量的是"响应里出现了作者事先写好的数"，因此它们**不能**证明物理正确：
把题面给的密度复述一遍就能在质量题上拿分（`tests/test_solver_graders.py::test_echoed_input_is_scored_as_the_answer`
把这条漏洞钉成了测试）。凡属可求解的物理量，用例必须用 `world_state_verified`，且

- `gold.answer` 由 `wm_verifier.recompute(scenario)` 原样派生（生成器见 `scripts/build_physics_acceptance_cases.py`），
  作者手填的数会被 `validate_cases.py` 判 `gold_scores_*` 拒收；
- `tol_rel` 按难度显式收紧（easy 0.08 / medium 0.03 / hard 0.01）。求解器运行时默认 8%，
  **不得**让运行时容差悄悄变成评测容差；
- 判分器与运行时桥共用同一个 `wm_verifier`，禁止出现"裁判一套物理、选手另一套物理"
  （同 `planted_defects.py` 直接 import 执行器 `validate()` 的口径）。

数值类判据的 `evidence` 会带出求解器参照值与逐字段偏差，因此每轮评测落盘的 `raw.jsonl`
可直接导出 `(意图, 预测, 参照+误差)` 三元组作为训练语料：`python -m virtu_eval.export_physics_triples <run_dir>`。

## 独立物理维度 `physics`

`data/benchmark/virtu_eval_phys_v1/physics.jsonl`（30 条，9/15/6）是自成一体的验收集，
**未**并入 8 维综合分：`report.py` 的 `DIM_WEIGHTS` 保持原样，历史综合分依旧可比。
要单独跑它：`python -m virtu_eval.runner --case-dir data/benchmark/virtu_eval_phys_v1 --dims physics`。
把它折进综合分需要重新定权重并重建基线，那是另一个决定。

## 判分口径（写死，不得改）

- 维度分 = 该维度有效用例得分的算术平均（保留 1 位小数）。
- 综合分 = Σ(维度分 × 维度权重)，权重见 `virtu_eval/report.py` 的 `DIM_WEIGHTS`，报告需公示。
- `verdict ∈ {pass, partial, partial_truncated, fail_all_criteria, empty_response, transport_error}`。
- **只有 `transport_error` 不计入分母**（它衡量的是服务可用性，不是模型能力），其余一律计入。
- `transport_error` 占比 > 5% 判本轮无效，必须重跑。

## 领域约束（本模型专属）

Virtu 的定位是 CAD/CAM/CAE 六软件（NX、SOLIDWORKS、VERICUT、SW 斯沃数控、PowerMill、AutoCAD）
智能体。`toolcall` 与 `knowledge` 维度必须覆盖这六个软件的真实 API/术语；
`multimodal` 只用**脚本合成、真值已知**的图片（`scripts/make_multimodal_images.py`），
不得用外部图纸，避免真值不明与版权问题。
