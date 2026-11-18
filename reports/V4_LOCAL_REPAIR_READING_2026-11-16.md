# virtu-six-software v4-local-repair 读数与 v3 矛盾定性（2026-11-16 19:40）

> 口径：所有读数取自 `runs/` 与 `reports/handover_20261115/v4_compare/` 的原始 JSON，不转述、不取最好一次。
> 本轮只做读数与定性，不重出任何凭证、不改判分器、不改语料。

---

## 1. 一句话结论

**v4-local-repair 未达标**：探针 8/10（红 `lame_stress_probe`、`vericut_autodiff_probe`），两个红项与 v3 的旧缺陷同源，修复集训练没有把它们修掉。
**v3 当前不可复现**：同一 digest、同一判分器，19:06 为 7/10，19:11/19:15 为 10/10；按项目 §8.2「连测最差值」应记 **7/10**，不能取 10/10 发布。

---

## 2. 构件身份（先锁身份，再谈分数）

| 标签 | digest（前 16） | 部署时间 | 备注 |
|:--|:--|:--|:--|
| `virtu-six-software:v3` | `35cd9e06c40e6a4f` | 2026-11-16 18:57:22 | **重建版**；旧 `ed409a5e45d807ec` 的所有凭证/读数失效 |
| `virtu-six-software:v4-local-repair` | `9654750663184e4c` | 2026-11-16 19:07:17 | 本地修复集 LoRA 合并 + Q4_0 |

---

## 3. 读数矩阵（同一时段、同一台机）

| 时间 | 对象 | 测量 | 结果 | 判分器/口径 |
|:--|:--|:--|:--|:--|
| 19:06 | v3 | `targeted` 10 探针 | **7/10**，红：`sw_coordinate`、`lame_stress`、`fanuc_g71` | `48c8230e…` / `probes-2026-11-15-v2` |
| 19:11 | v3 | 探针 r1 | **10/10** | 同上 |
| 19:15 | v3 | 探针 r2 | **10/10** | 同上，`drifted=false` |
| 19:21 | v4 | 探针 r1 | **8/10**，红：`lame_stress`（σ_θ=30.00 MPa）、`vericut_autodiff`（`missing_color:blue`） | 同上，`drifted=false` |
| 19:14 | v3 | `domain24`（n=24） | 均分 **41.67**，`slot_exact_v2` | `916557c9…`；与 substring 历史分不可混用 |
| 19:26 | v3 | generic（28 例 / 7 维） | overall **58.04** | `graders.py 5024fe5c…`，`multimodal` 未测 |

---

## 4. 矛盾定性：7/10 与 10/10 并存

- 两次 10/10 的 `tags_digest_before == after == 35cd9e06…`，`drifted=false`，说明**不是构件在腿内变化**。
- 19:06 的 7/10 与 19:11 的 10/10 相隔 5 分钟，同一判分器、同一温度/种子，差异只能归因于**采样/上下文/加载顺序**。
- 按 `AGENTS.md §8.2` 与 `FINAL_REPORT.md §8`：**连测最差值做门禁** ⇒ v3 当前应记 **7/10，不进生产路由**。
- v4 只有 1 轮（8/10），样本不足以宣称“比 v3 好”；至少在 19:06 的同类失败面上，v4 与 v3 一样红。

---

## 5. v4 的两个红项（逐字读数）

1. `lame_stress_probe`：模型给出 `σ_θ = P_i(D_o²+D_i²)/(D_o²−D_i²) = **30.00 MPa**`，正确值 **33.33 MPa**；σ_r 已落 −20.00 MPa（这一半对了）。
   ⇒ 公式形式正确、**代数计算错**（或用错了 D 值）。修复集里 24 条 `lame_closed_form_repair` 没有固化住数值。
2. `vericut_autodiff_probe`：`missing_color:blue` —— 未给出蓝色=残料的定义。红/绿可能对，但蓝条缺失。
   ⇒ 与 v3 的 `swapped_meaning:blue`/`missing_color:blue` 同一语义族，未修掉。

---

## 6. 训练链证据（本地 6 GB）

| 步骤 | 配置 | 结果 |
|:--|:--|:--|
| `r1_light` | 8 步 / max_len 640 / dev 4 / skip 261 | ✅ `1.5457 → 1.3293`（Δ −0.2164），`checkpoints/local_sft_link_check` |
| `r2_v3_repair` | 64 步 / 255 micro / 修复集 | ✅ `dev_loss → 0.6157`（Δ −1.9555），`six_software_v3_local_repair_lora` |
| `merge_v4` | LoRA 合并 | ✅ 12/12 数值验证 PASS（229 s） |
| `gguf_v4` | Q4_0 | ✅ 4.61 GB / 399 tensors / `unmapped: []` |
| `r1_sft_link` 原配置 | 20 步 / 1536 / dev 124 | ⏳ 19:39 起重跑（`runs/local_training_20261115/r1_full20_exec.log`），此前 22:47 那次崩在 eval OOM |

---

## 7. 结论与下一步

1. **v4 不进生产路由**：8/10，且红项是硬缺陷（Lamé 数值、Auto-Diff 蓝条）。
2. **v3 记 7/10（最差值）**：10/10 的两次不能单独作为发布依据；若要翻案，需 ≥3 轮连测且全部 10/10。
3. **凭证重出暂缓**：v3 digest 已变，旧凭证失效是事实，但在 v3 读数稳定前重出只会再写一份不可复现的凭证。
4. 待原 20 步 / 1536 配置跑完，确认“6 GB 能否按原配置训练”这一点，再决定是否扩到 full 语料。
5. 语料侧下一步只做两件事：把 Lamé 的**数值代入**（Do/Di 取值 + 33.33/−20）与 Auto-Diff **蓝条定义**做成 SFT/DPO 对；不再加泛化样本。

---

## 8. 证据

- `reports/handover_20261115/v4_compare/virtu-six-software_v3_r1.json` / `_r2.json` / `virtu-six-software_v4-local-repair_r1.json`
- `runs/eval_v3_law_20261116/{gates.json,targeted.json,domain24/summary.json,generic/summary.json,chain.log}`
- `runs/local_training_20261115/{r1_light.log,r2_v3_repair.log,merge_v4.log,gguf_v4.log,r1_full20_exec.log}`
- `checkpoints/{local_sft_link_check,six_software_v3_local_repair_lora,_deploy_six_v4_local}/`
