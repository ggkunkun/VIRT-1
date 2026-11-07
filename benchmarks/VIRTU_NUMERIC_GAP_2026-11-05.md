# 数值短板逐例归因（board7__frozen_comp_v5__v4，n=210）

- `numeric_near` 判据 100 次，失败 54 次
- 确定性核算回放后分数有变化的例数：28（升 28 / 降 0）
- 可达性：{'deterministic_pass_produces_a_reference': 54}

## 失败类别

| 类别 | 次数 |
|---|---:|
| arithmetic_off_by_small_factor | 29 |
| wrong_by_more_than_half | 19 |
| radius_vs_diameter | 4 |
| pi_dropped_or_kept | 2 |

## 确定性核算今天够不到的量（下一批要注册的式）

| 被问的量（判据 key） | 失败次数 | 题面片段 |
|---|---:|---|

## 逐例（最多 24 条）

| case | 维 | 类别 | ratio | 回放前 | 回放后 | 命中的确定性式 |
|---|---|---|---:|---:|---:|---|
| generalization-e08 | generalization | arithmetic_off_by_small_factor | 1.002876 | 12.5 | 100.0 | 主轴转速,进给速度 |
| generalization-e08 | generalization | arithmetic_off_by_small_factor | 1.163603 | 12.5 | 100.0 | 主轴转速,进给速度 |
| generalization-e09 | generalization | arithmetic_off_by_small_factor | 1.396258 | 12.5 | 100.0 | 主轴转速,进给速度 |
| generalization-e09 | generalization | arithmetic_off_by_small_factor | 1.163603 | 12.5 | 100.0 | 主轴转速,进给速度 |
| generalization-m03 | generalization | arithmetic_off_by_small_factor | 1.25 | 0.0 | 88.89 | 切削速度,主轴转速,进给速度 |
| generalization-m03 | generalization | arithmetic_off_by_small_factor | 1.250618 | 0.0 | 88.89 | 切削速度,主轴转速,进给速度 |
| generalization-m03 | generalization | arithmetic_off_by_small_factor | 0.872676 | 0.0 | 88.89 | 切削速度,主轴转速,进给速度 |
| generalization-m05 | generalization | arithmetic_off_by_small_factor | 0.75 | 12.5 | 100.0 | 第一直径,第二直径 |
| generalization-m05 | generalization | radius_vs_diameter | 0.5 | 12.5 | 100.0 | 第一直径,第二直径 |
| generalization-m07 | generalization | wrong_by_more_than_half | 5.882353 | 62.5 | 100.0 | 英尺换算,深度英尺 |
| generalization-h02 | generalization | arithmetic_off_by_small_factor | 0.833333 | 87.5 | 100.0 | 本表G代码数 |
| generalization-h03 | generalization | arithmetic_off_by_small_factor | 1.002127 | 40.0 | 100.0 | 切削速度,每齿进给,主轴转速,进给速度 |
| generalization-h03 | generalization | arithmetic_off_by_small_factor | 1.002148 | 40.0 | 100.0 | 切削速度,每齿进给,主轴转速,进给速度 |
| generalization-h04 | generalization | wrong_by_more_than_half | 1.570845 | 0.0 | 66.67 | 主轴转速,进给速度,材料去除率 |
| generalization-h04 | generalization | wrong_by_more_than_half | 0.26178 | 0.0 | 66.67 | 主轴转速,进给速度,材料去除率 |
| generalization-h04 | generalization | wrong_by_more_than_half | 0.011636 | 0.0 | 66.67 | 主轴转速,进给速度,材料去除率 |
| generalization-h04 | generalization | arithmetic_off_by_small_factor | 1.098901 | 0.0 | 66.67 | 主轴转速,进给速度,材料去除率 |
| generalization-h05 | generalization | wrong_by_more_than_half | 1.570845 | 0.0 | 66.67 | 主轴转速,进给速度,材料去除率 |
| generalization-h05 | generalization | wrong_by_more_than_half | 0.411169 | 0.0 | 66.67 | 主轴转速,进给速度,材料去除率 |
| generalization-h05 | generalization | wrong_by_more_than_half | 0.147477 | 0.0 | 66.67 | 主轴转速,进给速度,材料去除率 |
| generalization-h05 | generalization | wrong_by_more_than_half | 1.791209 | 0.0 | 66.67 | 主轴转速,进给速度,材料去除率 |
| generation-h01 | generation | radius_vs_diameter | 0.502513 | 42.86 | 71.43 | 主轴转速 |
| knowledge-m02 | knowledge | arithmetic_off_by_small_factor | 0.9 | 0.0 | 100.0 | 标准公差等级数 |
| knowledge-h01 | knowledge | wrong_by_more_than_half | 18.0 | 0.0 | 100.0 | 残留高度 |

> 口径：回放只跑 `virtu_real_backend` 的两个纯函数（显式等式重算 + 题面给定量的公式重算），
> 不重问模型，不含卫生层（四栈归因见 `scripts/stack_attribution_offline.py`）。
