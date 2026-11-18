# 评测口径真实化 · 备份快照

时间：2026-11-08 23:49:39
主题：把「评测同源自测」这一缺陷真正修掉——引入题面改写层、加改写保真检查、
       补 design 自然语序与牌号误判两个推断器缺陷，并把两项新检查挂进门禁。

## 本快照内容（改动后的成品版本，供比对与回滚参考）

| 文件 | 大小(B) | sha256[:16] | mtime |
|---|---|---|---|
| anti_hallucination_guard.py | 79362 | a346ac5196e6edc6 | 2026-11-08 23:39 |
| eval_worldmodel.py | 27834 | ac7e58e6d726efca | 2026-11-08 23:30 |
| wm_eval_paraphrase.py | 23666 | ab7fe24ad2280c57 | 2026-11-08 23:31 |
| wm_eval_purity.py | 7455 | 6b9a80db4ec4624c | 2026-11-08 23:33 |
| wm_vuln_regression.py | 10646 | ed22ad31f745e4c7 | 2026-11-08 23:46 |
| wm_ci_gate.py | 5266 | d68d45f7e2d33479 | 2026-11-08 23:47 |

## 改动前旧版对照

`_bak_wmfix2_20261108_205800/` 保留本轮开工前的 `anti_hallucination_guard.py`
与 `eval_worldmodel.py`（2026-11-08 20:58 快照），需要回退这两个文件时从那里取。

## 本轮改动清单

1. `wm_eval_paraphrase.py`（新增）：12 族 × 3 句式题面改写层，`rewrite()` 只换措辞，
   `wrap()` 包生成器且失败原样返回、不丢样本、不改期望值，`selftest()` 断言改写后
   推断仍归本族。
2. `eval_worldmodel.py`：接入改写层（`GEN_BY_FAMILY` 逐族 wrap），新增
   `--no-paraphrase` 逃生开关。
3. `wm_eval_purity.py`：新增 `fidelity()` 改写保真检查——用被测推断器解析改写题面，
   与生成器 `scenario.inputs` 逐字段比对，改写器不参与裁判；`--fidelity` 可调样本数。
4. `anti_hallucination_guard.py`：
   - FIX H5：design 分支触发条件放宽（不再强制「设计」二字），并补「螺栓孔 6 个 φ8.6」
     这类孔名在前的语序，避免掉进键值兜底后 `r_out` 被当直径、螺栓孔整体丢失。
   - FIX H6：材料牌号识别排除 `φ304`、`304 mm` 这类尺寸数字，避免钛合金 4.43e-3
     被改写成不锈钢 8.0e-3。
   - 早前 FIX：0b「要质量却没给物性」判别式加 `(?<!表面)` 负向边界，防「表面质量」误伤。
5. `wm_vuln_regression.py`：新增 H12/H13/H13b/H15/H14 五条断言，回归集从 12 条升到 17 条。
6. `wm_ci_gate.py`：新增必需项「题面改写归族」，门禁从 10 项升到 11 项。

## 验收结论

- 门禁 `wm_ci_gate.py`：**PASS 11/11，FAIL 0**（改动前为 9 PASS / 1 FAIL，红在评测去污纯度）。
- 漏洞回归 `wm_vuln_regression.py`：**17/17 全 PASS**。
- 去污探针 `wm_eval_purity.py`：干净可用模板 139/147，被训练集覆盖 5.4%（改动前 49/49 全污染、干净 0）。
- 改写自测 `wm_eval_paraphrase.py --samples 120`：12 族归族 100%，失配 0。
- 相关单测 10 个全绿（physics_reference_honesty / physics_case_set / physics_corpus_gates /
  eval_ruler / solver_graders / gate_falsifiability / derivation_grader / json_object_grader /
  universal_engineering_enhancements / train_data_gate）。
- 已编译改动涉及的 6 个脚本（全集 417 个脚本中 `deploy_and_cleanup.py` 存在既有
  SyntaxError，属 2026-11-05 遗留，与本次无关，未纳入门禁）。
