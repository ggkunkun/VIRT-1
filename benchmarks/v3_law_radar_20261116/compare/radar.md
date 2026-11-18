# 全模型真实能力测评（2026-11-07 现场实测）

## 结论口径

- Ollama 库枚举 4 个唯一构件（按 digest 去重，标签别名合并）。
- 真实调用并封缄、**可发布** 4 个；未测/作废 0 个（见下表，不填分数）。
- 每个分数由 `scripts/generate_verified_radar.py` 从各腿 `raw.jsonl` 现场复算，
  与腿内记录逐位比对；封缄/sha256/完整性闸门/逐行 served_layers/run_id 任一不符即整腿作废。
- 与 `VIRTU_*_RADAR.html` 中 98–99 分「极限强化」多边形不同：那些数字在仓内找不到
  对应的 raw.jsonl 证据，本图不予采用。

## 统一口径

- 用例：`data/benchmark/virtu_eval_v1`，7 维 × easy,medium 各 2 题；判分器 `virtu_eval/graders.py`（sha256 5024fe5cfc85b6ac…）。
- 采样：temperature=0，seed=1234，num_predict≤384，num_ctx=4096，think=false。
- toolcall 维未注入工具 schema（纯文本 JSON 协议），不得与历史 16 工具腿比较。
- 多模态维**未测**（需视觉通道，库内无 VL 标签），不画轴、不进综合分。
- 每维样本量小，且 128 token 预算会压低长输出题；该偏差对所有模型一致。

## 实测榜（按综合分）

| 模型 | 家族 | 工具编排 | 推理逻辑 | 知识覆盖 | 指令遵循 | 边界处理 | 内容生成 | 泛化适配 | 综合 | n/维 | run_id | 证据 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| virtu-master-fixed:latest | 8B 合并/生产 | 25.0 | 74.3 | 62.5 | 91.7 | 91.7 | 58.8 | 50.7 | **64.12** | 4/4/4/4/4/4/4 | `767a4dff30ad81e9` | `runs/eval_full_board_20261115/generic/virtu-master-fixed_latest/raw.jsonl` |
| virtu-six-software:v3 | 其它/实验 | 33.3 | 57.6 | 62.5 | 91.7 | 75.0 | 35.0 | 50.7 | **58.04** | 4/4/4/4/4/4/4 | `b478b63c00150074` | `runs/eval_v3_law_20261116/generic/virtu-six-software_v3/raw.jsonl` |
| virtu-six-software:v1 | 其它/实验 | 25.0 | 45.7 | 46.7 | 91.7 | 83.3 | 46.2 | 52.1 | **54.15** | 4/4/4/4/4/4/4 | `708e60c7eda5c38e` | `runs/eval_full_board_20261115/generic/virtu-six-software_v1/raw.jsonl` |
| virtu-vericut96:v2 | 其它/实验 | 16.7 | 57.6 | 58.3 | 91.7 | 66.7 | 22.5 | 37.1 | **50.64** | 4/4/4/4/4/4/4 | `b3718fc48da94117` | `runs/eval_full_board_20261115/generic/virtu-vericut96_v2/raw.jsonl` |

## 未测 / 作废（不填分数）

| 模型 | 状态 | 原因 |
|---|---|---|

## 反证闸门

- `篡改单题分数（重封缄+伪摘要）` → 判红 PASS：维度 boundary 现场复算 41.67 != 记录 66.67
- `删除一行（覆盖不全）` → 判红 PASS：完整性闸门判红: ['记录数 27 < 计划用例数 28（覆盖不全）']
- `删除封缄` → 判红 PASS：封缄校验失败: leg: 未封缄，不得发布（谁写的、写完有没有人动过，都无从证明）
- `植入 3 条 transport_error` → 判红 PASS：完整性闸门判红: ['transport_error 占比 10.7% > 5%，本轮分数无效，需重跑']
- `抹掉一行 served_layers 身份` → 判红 PASS：存在无 served_layers 身份指纹的记录

## 复现

```bash
python scripts/eval_all_models_live.py
python scripts/generate_verified_radar.py --self-test
```
