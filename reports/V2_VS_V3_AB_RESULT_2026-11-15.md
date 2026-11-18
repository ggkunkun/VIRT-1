# virtu-vericut96 v2 vs v3 留出集 A/B（WorkBuddy 接手实测）

- 独占窗口：2026-11-15 22:05:41 ~ 22:47（守候放行；期间无其它 Ollama 推理请求）
- 口径：`scripts/eval_vericut_e_training.py --baseline virtu-vericut96:v2 --candidate virtu-vericut96:v3`，105 题留出集，`temperature=0` / `seed=42` / `num_ctx=4096` / `max_tokens=768`
- 身份：`run_id=6057955aa3af5362`，`basis=measured`，`identity_drift=[]`，`cases_sha256=5299db23542034c9…`
- 构件：v2 `cc70716d5f09…` / v3 `decdf3f470a8…`（见 `identity.json`）
- 补跑说明：candidate sanity 前 1 题于 22:39 完成，守候任务被取消后剩余 23 题于 22:44–22:47 手动续跑；`evaluate_model()` 断点续跑，未重算已完成样本。

---

## 1. 结论（一句话）

**v3 在领域留出集上没有超过 v2：均分 37.47 vs 38.89（Δ −1.42），pass@100 24.76% vs 28.57%（Δ −3.81 pp）。**
通用不回归 sanity 上 v3 略好（58.13 vs 55.63，Δ +2.50）。两腿传输错误均为 0、构件零漂移，属于可归因的 `measured` 结果。

**这不能给 v3 翻案**：探针侧的真缺陷（Lamé σ_θ 误算 60 MPa、Auto-Diff 红蓝语义不稳）依然存在，A/B 只是补充「相对 v2 的领域表现」，不是验收门。

---

## 2. 主表

| 项 | v2 (baseline) | v3 (candidate) | delta |
|:--|--:|--:|--:|
| holdout 均分 | **38.89** | 37.47 | **−1.42** |
| pass@100 | **28.57%** | 24.76% | **−3.81 pp** |
| 传输错误 | 0 | 0 | — |
| 有效题数 | 105 | 105 | — |

---

## 3. 分维度

| 维度 | n | v2 | v3 | delta | 读法 |
|:--|--:|--:|--:|--:|:--|
| `runtime_toolcall` | 12 | **97.22** | 91.67 | **−5.55** | 工具调用是 v2 的强项，v3 退步 |
| `pdf_curriculum_qa` | 11 | **18.18** | 9.09 | **−9.09** | 两版都弱，v3 更弱 |
| `nc_safety_diagnosis` | 29 | **36.95** | 35.10 | **−1.85** | 样本最大的安全维度，v3 没修好 |
| `setup_workoffset` | 20 | 41.46 | 40.83 | −0.63 | 基本持平 |
| `tool_assembly` | 20 | 28.33 | **33.33** | **+5.00** | v3 唯一明显增益 |
| `boundary` | 6 | 33.33 | 33.33 | 0 | 持平 |
| `machine_kinematics` | 6 | 0 | 0 | 0 | 两版全灭 |
| `vericut_setup_facts` | 1 | 50.00 | 33.33 | −16.67 | n=1，不作结论 |

---

## 4. 通用不回归 sanity（`data/benchmark/virtu_eval_v1`，24 题）

| 项 | v2 | v3 | delta |
|:--|--:|--:|--:|
| 均分 | 55.63 | **58.13** | **+2.50** |
| pass@100 | 37.5% | **41.67%** | **+4.17 pp** |

⇒ v3 的退步是**领域内**的，不是通用能力整体崩坏；这与「SFT 语料把安全语义带偏、通用对话略升」的方向一致。

---

## 5. 能说与不能说

**能说**
- 同一身份、同一判分器、同一独占窗口下，v3 的领域留出集表现比 v2 低 1.42 分 / 3.81 pp。
- v3 的增益集中在 `tool_assembly`（+5.0），退步集中在 `pdf_curriculum_qa`（−9.09）与 `runtime_toolcall`（−5.55）。
- 通用 sanity 没有回归，反而 +2.50。

**不能说**
- 不能说「v3 比 v2 强」——数据不支持。
- 不能把本 A/B 当作验收门：`lame_stress_probe` 的真缺陷、`vericut_autodiff_probe` 的语义不稳仍由探针侧判红。
- 不能把 `vericut_setup_facts`（n=1）与 `machine_kinematics`（两版 0 分）当能力结论。

---

## 6. 证据

- `runs/eval_vericut96_v2_vs_v3/comparison_report.json`（主报告，含完整 by_dimension）
- `raw_baseline_holdout.jsonl` / `raw_candidate_holdout.jsonl`（各 105 行）
- `raw_baseline_sanity.jsonl`（24 行）/ `raw_candidate_sanity.jsonl`（24 行）
- `identity.json`（构件 digest、判分器哈希、cases sha256、drift）
- `workbuddy_takeover_{ab,watchdog}.log`（独占守候 + 每 10 题进度）
- 并发污染留档：`*.CONTAMINATED_2148`、`*.CONTAMINATED_2158`、`identity.json.PRE_TAKEOVER_2149`（均不参与本结论）

> 旁路说明：22:37 起本机有 `scripts/run_local_training_sequence.py` 守候进程，但它只做进程/显存查询、未发起任何 Ollama 推理，不构成本测量的并发污染。
