# 禁用：这份语料含评测集逐字题面

- 实测 2026-11-05：`python virtu_eval/contamination_check.py data/sft/virtu_evolution_v5.jsonl`
  ⇒ rows=3963 **hard_leaks=157**（其中含 prompt_hash 精确命中 `toolcall-e05`、`instruction-m15`、`toolcall-m02`），
  另有 845 行只是与评测 gold 共享数值（弱代理，不算硬泄漏）。
- 去污副本：`data/sft/virtu_evolution_v5.clean.jsonl`（3806 行，hard_leaks=0）。
- 任何训练入口现在都会先过 `virtu_eval.contamination_check.assert_no_leak`，硬泄漏即拒开训。
- 本文件保留原位不动（它是这条缺陷的证据）；要训练请指 `.clean.jsonl`。
