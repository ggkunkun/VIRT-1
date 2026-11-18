# WorkBuddy 接手记录 · Antigravity 会话 `318e3215-c01f-411b-9f92-b2ee6c02b092`

> 接手时间：2026-11-15 21:5x（GMT+8） · 工作区 `D:\Virtu模型`
> 接手范围：该 Antigravity 会话未闭环的 `virtu-vericut96:v3` 验收收口与 v2/v3 留出集 A/B。
> 本记录只做只读核对 + 一条后台测量，未改动任何凭证、判分器或生产模型文件。

---

## 1. 接手对象（已核实身份）

| 项 | 实测值 |
|:--|:--|
| Antigravity 会话 | `318e3215-c01f-411b-9f92-b2ee6c02b092`，标题「编写云端训练与修复脚本」 |
| 会话状态 | `CASCADE_RUN_STATUS_IDLE`（`conversation_summaries.db`，step_count 3922） |
| 最后用户输入 | 「执行」/「全面执行」/「本地进行修复」 |
| 会话数据库 | `%USERPROFILE%\.gemini\antigravity\conversations\318e3215-….db`（78 MB） |
| 交接文档 | `brain\318e3215-…\scratch\FINAL_REPORT.md`（21:46）、`NEXT_FOR_GEMINI.txt`、`FOR_GEMINI_PROBE_ROOT_CAUSE.md` |
| 姊妹交接文档 | `reports\SIX_SOFTWARE_V3_HANDOVER_2026-11-15.md`（另一 Antigravity 会话 `2e2f3be3-…`） |

---

## 2. 现场状态（只读实测，非推断）

| 项目 | 状态 | 证据 |
|:--|:--|:--|
| `virtu-vericut96:v3` 验收 | 双轨口径已落代码；凭证 21:46:48 刷新为显式双轨 | `checkpoints\deployment_receipt_virtu-vericut96_v3.json` |
| 判分器冻结版本 | `deploy_trained_adapter.py` sha256 `48c8230e…`（21:45:21） | `FINAL_REPORT.md` §1/§8 |
| Ollama 服务 | `ollama serve` 21:09 起，`/api/tags` 可见 16 个模型；`/api/ps` 仅 `virtu-vericut96:v2` idle 驻留 | `runs\ollama_11434.log`、127.0.0.1:11434 |
| 评测进程 | **无** Python 评测进程（仅有 `proxy_failopen_watchdog.py` 与 ollama/llama-server） | `Get-CimInstance Win32_Process` |
| 主机余量 | 可用物理 7.29 GiB / 可用提交 20.61 GiB | `GlobalMemoryStatusEx` |
| A/B 进度 | **接手前断在第 1 题**：21:48 首轮 `CONTAMINATED_2148`（并发污染）；21:50 独占重跑仅写 1 条基线即中断。接手首轮又遇并发，已作废 6 行并清空主文件；现由独占守候重启完整 105 题 | `runs\eval_vericut96_v2_vs_v3\`（`*.CONTAMINATED_*`、`identity.json.PRE_TAKEOVER_2149`） |
| A/B 日志 | 两轮都只有启动行，无进度行、无 report.json | `scratch\ab_v2_vs_v3_2140.log`、`ab_v2_vs_v3_exclusive_2150.log` |
| 云端 AutoDL | 已关停（22/23 端口不通），DPO 续训路径暂不可用 | `SIX_SOFTWARE_V3_HANDOVER_2026-11-15.md` §5 |

---

## 3. 已采取的动作（含一次并发避让）

1. **只读接管核对**：逐个读取会话摘要库、交接文档、凭证、日志、进程表。
2. **21:53 首轮启动 A/B 后发现并发，立即停止**：
   - 当时另有 `scratch\handover_verify_v3.py 2`（21:52:58 启动，另一会话的 `virtu-six-software:v3` 双轮复测）在跑；`/api/ps` 显示 `six-software:v3` 与 `vericut96:v2` 交替加载。
   - 按测量宪法「不得并发抢占」，主动 kill 本轮 A/B（后台任务 `l3abBt`），未让污染结果进入结论。
   - 已写出的 6 行基线样本全部归档为 `raw_baseline_holdout.jsonl.CONTAMINATED_2158`，`identity.json` 另存 `…PRE_TAKEOVER_2149`，主文件清空；日志另存 `workbuddy_takeover_ab.log.CONCURRENT_2158`。
   - 外部复测于 21:57 正常结束（`reports\handover_20261115\verify_v3_{round1,round2,summary}.json`）。
3. **新增独占守候** `scripts\wait_exclusive_then_ab.py`（后台任务 `192FLt`）：
   - 条件：无其它工作区 Python 测量进程 + 最近 45 s 内无 `/api/chat|/api/generate`，连续 3 次（间隔 10 s）成立才放行；60 min 内等不到窗口则 ABORT，不硬抢。
   - 放行后按原口径启动完整 A/B（105 题 × 2 腿 + 通用 sanity，`temperature=0` / `seed=42` / `num_ctx=4096`），跑完自动从 `comparison_report.json` 生成 `reports\V2_VS_V3_AB_RESULT_2026-11-15.md`。
   - 日志：`runs\eval_vericut96_v2_vs_v3\workbuddy_takeover_{ab,watchdog}.log`。
4. **遵守测量宪法**（`FINAL_REPORT.md` §8）：单次探针不作结论、独占 GPU、判分器/被测对象哈希留档、被截断样本单列、同一 tag 凭证单一 owner。
5. **22:47 A/B 补完**：守候在 22:05:41 放行，两腿 holdout 各 105/105、baseline sanity 24/24 完成后守候被用户取消；手动续跑 candidate sanity 剩余 23 题（22:44–22:47），`comparison_report.json` 已生成，`basis=measured`、`identity_drift=[]`。结论：v3 领域留出集 37.47 vs v2 38.89（**−1.42**），pass 24.76% vs 28.57%（**−3.81 pp**），通用 sanity **+2.50**。详见 `reports\V2_VS_V3_AB_RESULT_2026-11-15.md`；`FINAL_REPORT.md` §7 已回填。
6. **修复训练编排的假阳性阻塞**（`scripts\run_local_training_sequence.py`）：`eval_running()` 原经 `powershell` 子进程查命令行，查询失败时保守返回 `True`，导致 GPU 已空（5920 MB free、Ollama 空）仍永远判忙、训练永不启动。改为 psutil 直查 + 保留保守兜底；验证 `eval_running()=False` 后重启编排（第 3/3 次空闲检查通过即进入 probe → SFT）。

---

## 4. 待完成与需用户拍板

| # | 事项 | 依赖 |
|:--|:--|:--|
| 1 | ✅ **已完成（22:47）**：105×2 holdout + 24×2 sanity 全部有效，`comparison_report.json` 与 `reports\V2_VS_V3_AB_RESULT_2026-11-15.md` 已生成，`FINAL_REPORT.md` §7 已回填 | — |
| 2 | `virtu-vericut-e:latest` / `virtu-six-software:v3` 按 `48c8230e…` 重出凭证 | 需独占 Ollama，排在 A/B 之后 |
| 3 | `runs\eval_full_board_20261115` 的 holdout 补跑（20:22 死在线上） | 需独占 Ollama，排在第 2 项之后 |
| 4 | 裸权重 Lamé 缺陷（`σ_θ` 误用 `(Do+Di)/(Do−Di)`=60 MPa，正确 33.33 MPa；`σ_r` 未落 −20） | 需云端开机后新一轮 SFT/DPO；**待决策** |
| 5 | 验收门是否维持「生产配置 = 记忆增强轨」（当前决策） | **待决策**：另一交接文档明确反对改门，理由是记忆轨两次测量 5/5 与 3/5 不可复现 |
| 6 | `grader_sha256` 语义改为「评分函数实现哈希」 | 需三方写入方共同认可，未擅自改 |

> 诚实边界：本轮接手**未**做 DPO、未重训、未改判分器、未重出任何凭证；SSH 口令不落盘。

---

## 5. 证据路径

- `C:\Users\Administrator\.gemini\antigravity\brain\318e3215-c01f-411b-9f92-b2ee6c02b092\scratch\FINAL_REPORT.md`
- `D:\Virtu模型\checkpoints\deployment_receipt_virtu-vericut96_v3.json`
- `D:\Virtu模型\runs\eval_vericut96_v2_vs_v3\`（identity.json / raw_*holdout.jsonl / workbuddy_takeover_ab.log）
- `D:\Virtu模型\reports\SIX_SOFTWARE_V3_HANDOVER_2026-11-15.md`
