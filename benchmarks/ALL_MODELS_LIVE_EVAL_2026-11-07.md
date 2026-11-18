# 全模型真实能力测评（2026-11-07 现场实测）

## 结论口径

- Ollama 库枚举 9 个唯一构件（按 digest 去重，标签别名合并）。
- 真实调用并封缄、**可发布** 7 个；未测/作废 2 个（见下表，不填分数）。
- 每个分数由 `scripts/generate_verified_radar.py` 从各腿 `raw.jsonl` 现场复算，
  与腿内记录逐位比对；封缄/sha256/完整性闸门/逐行 served_layers/run_id 任一不符即整腿作废。
- 与 `VIRTU_*_RADAR.html` 中 98–99 分「极限强化」多边形不同：那些数字在仓内找不到
  对应的 raw.jsonl 证据，本图不予采用。

## 统一口径

- 用例：`data/benchmark/virtu_eval_v1`，7 维 × easy,medium 各 1 题；判分器 `virtu_eval/graders.py`（sha256 5024fe5cfc85b6ac…）。
- 采样：temperature=0，seed=1234，num_predict≤128，num_ctx=1024，think=false。
- toolcall 维未注入工具 schema（纯文本 JSON 协议），不得与历史 16 工具腿比较。
- 多模态维**未测**（需视觉通道，库内无 VL 标签），不画轴、不进综合分。
- 每维样本量小，且 128 token 预算会压低长输出题；该偏差对所有模型一致。

## 实测榜（按综合分）

| 模型 | 家族 | 工具编排 | 推理逻辑 | 知识覆盖 | 指令遵循 | 边界处理 | 内容生成 | 泛化适配 | 综合 | n/维 | run_id | 证据 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| virtu-v3-all90-q4_0:latest | 其它/实验 | 50.0 | 70.0 | 75.0 | 100.0 | 83.3 | 65.0 | 71.4 | **72.73** | 2/2/2/2/2/2/2 | `1a358422440b40c2` | `runs/eval/all_models_live_v2_20261107/virtu-v3-all90-q4_0_latest/raw.jsonl` |
| virtu-13.63b-q4_0:latest | 13B 家族 | 33.3 | 50.0 | 75.0 | 100.0 | 66.7 | 55.0 | 31.4 | **59.33** | 2/2/2/2/2/2/2 | `057a86c0d4cc737c` | `runs/eval/all_models_live_v2_20261107/virtu-13.63b-q4_0_latest/raw.jsonl` |
| virtu-13.63b:latest | 13B 家族 | 33.3 | 26.7 | 50.0 | 100.0 | 83.3 | 32.5 | 24.3 | **50.24** | 2/2/2/2/2/2/2 | `9a2a9157070b17ec` | `runs/eval/all_models_live_v2_20261107/virtu-13.63b_latest/raw.jsonl` |
| virtu-13.63b:hardened | 13B 家族 | 33.3 | 20.0 | 58.3 | 100.0 | 66.7 | 45.0 | 31.4 | **50.18** | 2/2/2/2/2/2/2 | `fdd614d988ffc9df` | `runs/eval/all_models_live_v2_20261107/virtu-13.63b_hardened/raw.jsonl` |
| virtu-13.63b:wm-v1 | 13B 家族 | 16.7 | 26.7 | 75.0 | 100.0 | 83.3 | 12.5 | 21.4 | **48.67** | 2/2/2/2/2/2/2 | `22c8d15a8aadb087` | `runs/eval/all_models_live_v2_20261107/virtu-13.63b_wm-v1/raw.jsonl` |
| virtu-moe-14b:hardened | MoE-14B | 33.3 | 10.0 | 75.0 | 100.0 | 66.7 | 12.5 | 31.4 | **47.57** | 2/2/2/2/2/2/2 | `c407c80da18b4f16` | `runs/eval/all_models_live_v2_20261107/virtu-moe-14b_hardened/raw.jsonl` |
| qwen2.5:1.5b | 基座对照 | 33.3 | 20.0 | 50.0 | 83.3 | 66.7 | 12.5 | 24.3 | **42.30** | 2/2/2/2/2/2/2 | `99194b6efdf95fe3` | `runs/eval/all_models_live_v2_20261107/qwen2.5_1.5b/raw.jsonl` |

## 未测 / 作废（不填分数）

| 模型 | 状态 | 原因 |
|---|---|---|
| virtu-13b:gold | failed | gate_invalid: {'expected_cases': 14, 'recorded_cases': 14, 'malformed_lines': 0, 'transport_errors': 1, 'transport_rate': 0.0714, 'valid': False, 'problems': [' |
| virtu-wm-v3:latest | failed | gate_invalid: {'expected_cases': 14, 'recorded_cases': 2, 'malformed_lines': 0, 'transport_errors': 2, 'transport_rate': 1.0, 'valid': False, 'problems': ['记录数  |

## 反证闸门

- `篡改单题分数（重封缄+伪摘要）` → 判红 PASS：维度 boundary 现场复算 83.34 != 记录 66.67
- `删除一行（覆盖不全）` → 判红 PASS：完整性闸门判红: ['记录数 13 < 计划用例数 14（覆盖不全）']
- `删除封缄` → 判红 PASS：封缄校验失败: leg: 未封缄，不得发布（谁写的、写完有没有人动过，都无从证明）
- `植入 3 条 transport_error` → 判红 PASS：完整性闸门判红: ['transport_error 占比 21.4% > 5%，本轮分数无效，需重跑']
- `抹掉一行 served_layers 身份` → 判红 PASS：存在无 served_layers 身份指纹的记录

## 复现

```bash
python scripts/eval_all_models_live.py
python scripts/generate_verified_radar.py --self-test
```
