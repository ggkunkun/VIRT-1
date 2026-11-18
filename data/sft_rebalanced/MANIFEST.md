---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 4089e70912072d5b0de62543257d198b_ee572643db8511f19232525400248c00
    ReservedCode1: GPbcJmkY0anPXH5vxF6NgG1n7C9zNMn1YczcgGwGOnIiTrNGZvdFmpRixwP4p/j+9Sm09bQ6ye6CHfb7MP6kCGhtkS+0zlB4uPMtnj5zuTNgDEtXSS3zoLJ9aRHbYxYl8kChyDxzYfuZSbozSjyfD4SuxRNMbvsSjNBgZvdWSYJR/cTX+yYRiRBkbdM=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 4089e70912072d5b0de62543257d198b_ee572643db8511f19232525400248c00
    ReservedCode2: GPbcJmkY0anPXH5vxF6NgG1n7C9zNMn1YczcgGwGOnIiTrNGZvdFmpRixwP4p/j+9Sm09bQ6ye6CHfb7MP6kCGhtkS+0zlB4uPMtnj5zuTNgDEtXSS3zoLJ9aRHbYxYl8kChyDxzYfuZSbozSjyfD4SuxRNMbvsSjNBgZvdWSYJR/cTX+yYRiRBkbdM=
---

# 重平衡训练集落位说明（data/sft_rebalanced）

## 这是什么

`data/sft` 全量 33135 条带 prompt 样本里，**近重复溢出 25307 条（76.38%）**——同一题面模板只换数字，模型学到的是「模板 → 答案」的捷径。本目录存放按模板簇分层上限采样后的去近重复版本。

| 项 | 值 |
|---|---|
| 文件 | `wm_train_cap12_v2.jsonl` |
| 条数 | 7828 条（其中带 user prompt 7533 条） |
| 模板簇 | 1327 个（每簇上限 12 条，至少保留 1 条） |
| 大小 | 15.6 MB |
| sha256 | `d624ac982bab88455632988c445207b0e9c413e18e9b44110438b7c872c2dab7` |
| 生成脚本 | `scripts/wm_rebalance_train.py --cap 12` |
| 审计脚本 | `scripts/wm_leak_audit.py` |

簇内采样优先保留信息更完整的样本（assistant 回复更长、带 scenario 标注）。

## 为什么单独放一个目录，而不是覆盖 data/sft

1. `data/sft` 的原文件一个字节都没动，随时可以回退对比。
2. `data/sft/virtu_final_train.jsonl` 是**冻结证据**（被 `tests/test_physics_reference_honesty.py` 引用），覆盖它等于篡改历史证据链。
3. 训练入口本来就支持指定数据文件，不需要改目录结构：
   - `train_world_model_final.py --data data/sft_rebalanced/wm_train_cap12_v2.jsonl`
   - 或环境变量 `DATA=<路径>`

## 替换前的关键对照

| 指标 | virtu_final_train.jsonl（当前默认） | 本文件 |
|---|---|---|
| 带 prompt 条数 | 3017 | 7533 |
| 模板数 | 401 | 1286 |
| 覆盖对方模板 | — | **401/401 = 100%** |

结论：本文件覆盖了当前默认训练集的**全部模板**，模板多样性 3.2 倍，且不含近重复溢出。替换不会丢失任何一类题型——这是替换可安全进行的前提。

## 数据格式提醒

本文件混有 9 种 schema（上游 `data/sft` 本来就不统一），共 7828 条：

```
4519  messages+meta
1113  messages
 985  messages+meta+scenario
 544  messages+meta+tools
 290  family+inputs+outputs
 144  case_id+chosen+prompt+rejected+...
 116  input+instruction+output+provenance
 112  messages+task
   5  chosen+meta+prompt_messages+rejected
```

其中 555 条非 `messages` 格式。任何读取本文件的脚本都必须兼容这些 schema——首版提取器只认 `messages`，把这些样本压成 12 条、静默丢了 1129 条有效样本，这个坑已经踩过一次。

## 还没有做的事

**尚未用它替换任何训练入口**。是否切换需要显式决定：切换后模型的题型分布会变（同模板样本从平均 6 次降到最多 12 次、绝大多数降到个位数），验证集指标会与历史基线不再可比。建议先跑一轮小 step 冒烟（`--max_steps`）确认 loss 曲线不要炸，再决定全量。
*（内容由AI生成，仅供参考）*
