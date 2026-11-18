# 六大工业软件 Agent 训练样本 —— v3 验收复核与交接

> 接管自 Antigravity 会话 `Industrial Software Agent Training Samples`
> （conversation id `2e2f3be3-1525-4b53-b60b-50c916013d31`，工作区 `D:\Virtu模型`）
> 交接时间：2026-11-15 21:05 起 · 文档定稿：2026-11-15

---

## 0. 一句话结论

`virtu-six-software:v3` 上一次部署验收的 **2 项失败（`lame_stress_probe`、`vericut_coordinate_unit_probe`）
是判分器假阴性 + 探针 token 预算截断造成的测量缺陷，不是模型缺陷**；
判分器与探针预算已修正，并配 14 条反证测试（全部通过）。
**修判分器后重跑同一模型的全套实测探针：8/10 → 10/10 全绿，
`status=DEPLOYED_VERIFIED`（21:26:46 新凭证，判分器哈希与磁盘一致 ⇒ 可归因）。**

**云端 AutoDL 实例 `117.50.179.122` 当前已关停（22 端口不通、ping 不通）**——
「再跑一轮 DPO」这条路暂时走不通；但就这两项失败而言，**不需要再训练**。

---

## 1. 接管时的现场状态（实测，非推断）

| 项目 | 实测结果 | 证据 |
|:--|:--|:--|
| 云端 GPU 实例 | **不可达** | `Test-NetConnection 117.50.179.122 -Port 23` → `TcpTestSucceeded=False`；`Test-Connection` → `False` |
| v3 交付件 | 在盘 | `runs\cloud_pull_six-software-v2_20261115_195913\six_software_v2_deliverable.tar.gz`（327,349,442 B） |
| v3 Ollama 标签 | 已部署 | `E:\migrated\D-MigratedFromC\ollama\models\manifests\registry.ollama.ai\library\virtu-six-software\v3`（934 B，20:18:54） |
| v3 GGUF 层 | 在盘 | `blobs\sha256-abd8b726…` 4,614,301,728 B（20:18:53） |
| 上次验收凭证 | `PROBE_FAILED` | 20:27:37，**探针总数 10、通过 8、失败 2**（原件已另存，见下） |
| 原始失败凭证 | **已保全** | `checkpoints\deployment_receipt_virtu-six-software_v3.PROBE_FAILED_20261115_202737.json`（未改动原件） |
| 修复后新凭证 | **`DEPLOYED_VERIFIED` 10/10** | `checkpoints\deployment_receipt_virtu-six-software_v3.json`（21:26:46，已另存 `…VERIFIED_20261115_212646.json`） |
| 训练语料 | 在盘 | `cloud_train_pack\dataset\six_software_v2_sft.jsonl`（950 行）/ `six_software_v2_dpo.jsonl`（164 行） |

---

## 2. 根因分析：两个失败探针为什么红

### 2.1 `lame_stress_probe` —— 回答被 token 预算硬截断

20:27 那次的模型原始输出（凭证 sample 与本次复现**完全一致**）：

```
- 内半径 $ r_i = \frac{Di}{2} = 30\,\text{mm} $，外半径 $ r_o = \frac{Do}{2} = 60\,\text{mm} $；
- 压力比平方 $ \left(\frac{P_i}{P_o}\right) = \left(\frac{r_i}{r_o}\right)^2 = 0.25 $，故内壁环向应力为：
  $$
  \sigma_{\theta} = P_i \left( \frac{r_o^2 + r_i^2}{r_o^2 - r_i^2} \right) = 20 \cdot
  \left( \frac{60^2 + 30^2}{60^2 - 30^2} \right) = 20 \cdot \left( \frac{4500}{2700} \right) = 20 \cdot 1.6667 = 33.33
```

- **σ_θ = 33.33 MPa 算对了**（判分器 `has_hoop` 本来就通过）；
- 回答在 `= 33.33` 处**戛然而止**，`num_predict=260` 恰好用尽 ⇒ σ_r 还没写出来；
- 旧判分器把「被截断」一律报成 `missing_negative_sigma_r_-20` ⇒ **把测量缺陷伪装成模型缺陷**。

本地独立 Ollama 实例（127.0.0.1:11435）复现同一模型、同一参数：
`n_gen = 260 tokens`（命中预算上限），`eval time = 102160 ms` —— 证实是预算截断，不是模型停笔。

**附带发现（诚实边界）**：模型中间那行「压力比平方 (Pi/Po) = (ri/ro)²」是**不严谨的表述**
（外压 Po=0 时 Pi/Po 无定义，正确的 k=(Do/Di)²）。最终 σ_θ 数值正确，但推导过程有瑕疵——
这是模型侧的真实弱点，只是**不应**由「σ_r 没写出来」这条截断错误来记账。

### 2.2 `vericut_coordinate_unit_probe` —— 否定词表缺「不得」（镜像缺陷）

20:27 那次的模型原始输出：

```
1. **工程单位确认**：`<Unit>inch</Unit>` 表示英制单位（英寸，inch），不是公制毫米（millimeter）。
若导入 VERICUT 仿真或后处理至 3D 检验系统，必须一并保持英制基准，不得擅自改写为 `millimeter`。
```

这句话**语义完全正确**（认定 inch + 禁止改写成毫米），但旧判分器：

- `has_isolation` 词表 = `不能|不可|无法|不同|严禁|不能直接|不可直接|不应|y-up|z-up`
  ⇒ **不含「不得」** ⇒ 报 `missing_coordinate_isolation`；
- `_neg_prefix_re` 同样**不含「不得」** ⇒ 正确答案「**不得**直接等价套用」会被
  `claimed_coordinates_identical` **反向拦下**（正确表述被判错）。

本次复现同一模型、同一参数时，模型给出了另一种同样正确的写法
（「**不能直接等价套用** SOLIDWORKS 2021 的 Front/Top/Right」）⇒ 旧判分器**判 PASS**。
⇒ **同一模型、同一温度、同一判分器，结论随措辞漂移** —— 这本身就是判分器不可靠的证据。

### 2.3 语料侧核查（为什么不靠「再训一轮」解决）

| 语料 | 行数 | `33.33` | `σ_r` | `-20 MPa` | `inch` | 单位隔离表述 |
|:--|--:|--:|--:|--:|--:|--:|
| `six_software_v2_sft.jsonl` | 950 | 1 | 32 | 1 | 78 | 1 |
| `six_software_v2_dpo.jsonl` | 164 | 1 | 19 | 2 | 18 | **0** |

- SFT 里两个知识点的**正确范式都有**（Lamé 有 32 条 σ_r、VERICUT 单位隔离有 1 条标准答案）；
- DPO 里 **VERICUT 单位隔离 0 对** ⇒ 该行为没有对比对支撑，稳定性偏弱；
- 但 2.1 / 2.2 证明的是**测量层**的问题：**先修判分器，再谈要不要补语料**。

### 2.4 训练样本溯源实测（用户指定的三个图纸目录）

三个源目录**当前都在盘**：

| 目录 | 文件数 | 主要内容 |
|:--|--:|:--|
| `E:\迅雷下载\100台3C、锂电自动化设备量产图纸` | 3,387 | `.sldprt`×2794、`.sldasm`×369、`.slddrw`×178、`.pdf`×21、`.igs`×21 |
| `E:\迅雷下载\分享数模20-77套UG夹具图档` | 87 | `.prt`×86（UG） |
| `E:\迅雷下载\建模练习图纸` | 1,336 | `.jpg`×1335、`.docx`×1 |

`six_software_v2_sft.jsonl`（950 行）里 **630 行带 `source_file` + `source_sha256` + `basis`**
（`parser_verified` 479 / `ocr_verified` 93 / `measured_occt` 58），
覆盖 **369 个互不相同的源图纸**；`v2` 另加 100 条 canonical 锚点
（`lame_closed_form` 32 / `fanuc_g71_safety` 30 / `autodiff_triage` 25 / `coordinate_unit_safety` 10 / `coordinate_isolation` 3），
DPO 侧另加 74 对。六大软件分布：**nx 169 / solidworks 131 / autocad 111 / cimco 94 / vericut 90 / sscnc 66**（+ cae 32 / cimco_sscnc 26 / six_software 10 / cross 1）。

**实测回查**：把 369 个 `source_file` 逐个回到三个源目录里按文件名/后缀/锚点匹配 ⇒
**367 / 369（99.5%）确实命中这三个目录**
（100台3C/锂电 135、UG夹具 32、建模练习 94 + docx 锚点 106）；
未命中的 2 条不是图纸（`70.卧式往复口罩机（口罩包装机）` 文件夹名、`bridges/six_software_orchestrator.py` 代码路径）。

**诚实边界**：DPO 文件（164 行）**没有逐条 `source_file` 溯源**，只有文件级 sha256 台账
（`six_software_v2_sft_ledger.json`）。也就是说「样本来自用户图纸」这件事，
**SFT 侧可逐条回查，DPO 侧只有文件级证据**。

---

## 3. 已落地的修正（`cloud_train_pack\deploy_trained_adapter.py`）

| # | 位置 | 修正 | 是否放宽口径 |
|:--|:--|:--|:--|
| 1 | `evaluate_lame_stress_probe` | 负号字符集扩为 `ASCII '-' / U+2212 '−' / U+FF0D '－'` | 否（同一物理判据） |
| 2 | `evaluate_lame_stress_probe` + 新增 `_looks_truncated()` | 截断单独报 `truncated_before_sigma_r_-20` 并带 `truncated=true` | 否（仍判红，但归因准确） |
| 3 | `evaluate_vericut_coordinate_unit_probe` | `has_isolation` 扩入 `不得/禁止/切忌/勿/不宜/不一致/不等价/非等价/不得直接/无法直接…` | 否（等价否定词表） |
| 4 | 同上 `_neg_prefix_re` | 补入 `不得/切勿/勿/不宜` ⇒ 修掉「正确表述被判声称等价」的**镜像缺陷** | 否（修的是反向误判） |
| 5 | 探针预算 | Lamé `num_predict` 260→**420**；VERICUT 坐标单位 260→**420**（raw 与 memory 双轨同步） | 否（只是让回答写完） |
| 6 | 凭证 | 新增 `measurement_version` + `grader_sha256`（**导入时快照**，AGENTS.md §8.2） | 否（增强可归因性） |

**反证测试**：`tests\test_six_software_probe_measurement_fix.py` —— **14 passed**，含以下必红用例：

- 被截断的 Lamé 回答 ⇒ 报 `truncated` 且判红；
- 只给 σ_θ、漏掉 σ_r ⇒ 判红（`missing_negative_sigma_r_-20`）；
- `σ_θ = 60 MPa`（旧式错误公式）⇒ 判红；
- σ_θ 值算错 ⇒ 判红；
- 不提 inch ⇒ 判红；肯定句说毫米 ⇒ 判红；
- 声称两套坐标系「完全等价，可直接套用」⇒ 判红；
- 只谈单位不谈隔离 ⇒ 判红；
- 探针预算回退到 260 级别的**回归守卫** ⇒ 必红。

---

## 4. 修复后的验收结果（实测）

**被测对象未变**：同一适配器 `adapter_sha256=8723c1e8…`、同一语料 `dataset_sha256=f9000d74…`、
同一 GGUF `gguf_sha256=abd8b726…`、同一 Ollama 标签 `virtu-six-software:v3`。
**只有判分器版本变了**：`measurement_version=probes-2026-11-15-v2`，
`grader_sha256=d119663e1c0c83364053570005069ade346442bd59ba5ee9981e6ff4f0beb1cb`
（与当前磁盘上的 `deploy_trained_adapter.py` **完全一致** ⇒ 凭证可归因到具体判分器）。

| 探针 | 20:27（旧判分器） | 21:26（修复后） |
|:--|:--|:--|
| `show_template_gate` | PASS | PASS |
| `chat_liveness_probe` | PASS | PASS |
| `native_tool_call_probe` | PASS | PASS（1 次工具调用） |
| `anti_degenerate_sanity_probe` | PASS | PASS（ngram 0.913） |
| `sw_coordinate_probe` | PASS | PASS |
| `lame_stress_probe` | **FAIL** `missing_negative_sigma_r_-20` | **PASS**（`truncated=true`：答案写完 σ_r 后仍在收尾） |
| `fanuc_g71_safety_probe` | PASS | PASS |
| `vericut_autodiff_probe` | PASS | PASS |
| `vericut_coordinate_unit_probe` | **FAIL** `missing_coordinate_isolation` | **PASS** |
| `vericut_tool_call_probe` | PASS | PASS（1 次工具调用） |
| **合计** | **8 / 10** | **10 / 10 ⇒ `DEPLOYED_VERIFIED`** |

**用修复后的判分器重判 20:27 的原始输出**（直接证明定性正确）：

- `lame_stress_probe` → 仍判红，但理由从 `missing_negative_sigma_r_-20`
  变成 **`truncated_before_sigma_r_-20`**（归因准确，不再把测量缺陷说成模型缺陷）；
- `vericut_coordinate_unit_probe` → **转绿**（原为假阴性）；
- 5 个**真错**样本（σ_θ=60 混淆 / 漏 σ_r / 声称坐标系完全等价 / 只谈单位不谈隔离 /
  肯定句说毫米）**全部仍然判红** ⇒ 门没有被放宽成摆设。

---

## 4.1 同一判分器族在其它标签上的复核结果（21:20–21:34）

> 判分器文件是**共享可改**的：21:19:26（`d119663e…`）→ 21:31:15（`f05070e4…`，兄弟会话追加
> autodiff 锚点选择与 SW 基准面顺延逻辑）→ 21:34 后（`9ce6f480…`）**仍在变**。
> ⇒ 任何凭证都必须绑定自己的判分器哈希才有意义（§8.2），否则就是「旧法判决」。

### `virtu-vericut-e:latest`（21:20:33）

`DEPLOYED_VERIFIED`，**raw 7/7 全 True、记忆增强轨 2/2 全 True**。
该次跑的是**修复前**的旧判分器（`measurement_version=None`）⇒ 连更严的旧口径都能过，结论更强。
20:14 那次 `PROBE_FAILED / missing_meaning:blue` 是旧判分器对「标题行 + 下一行定义」布局的锚点假阴性。

### `virtu-vericut96:v3`（21:18:22 旧判分器 → 21:34:42 修复后判分器）

| 探针 | 旧判分器 21:18 | 修复后 21:34 | 性质 |
|:--|:--|:--|:--|
| `sw_coordinate_probe` | FAIL `missing_normal:front` | **PASS** | 旧判分器/采样造成，非模型缺陷 |
| `lame_stress_probe` | FAIL `missing_sigma_theta_33.33` | **FAIL** | **真缺陷**：算不出 σ_θ=33.33 |
| `vericut_autodiff_probe` | FAIL `swapped_meaning:blue` | **FAIL** `swapped_meaning:blue` | **可复现性存疑**：我 21:34 的 live 重测仍红，而兄弟会话把**早期捕获**的同一模型原文喂给当前判分器是 `ok` ⇒ 同一 tag、temperature=0 下定义行排布会漂移，需连测定性（见下） |
| 其余 7 项 | PASS | PASS | — |
| **raw 合计** | 7/10 | **8/10** | — |
| **记忆增强轨** | **5/5 全 PASS** | **3/5**（`fanuc` T01、`autodiff` 缺 red 语义） | **两次测量不一致 ⇒ 不可复现** |

### 交叉佐证：云端早评（334 用例，兄弟会话产物 `cloud_bench_early_v3.json`）

`overall_score = 0.4489`；维度分解：
`toolrouting 0.7724 / knowledge 0.7717 / instruction 0.7706 / reasoning 0.6889 / generation 0.6456 /
generalization 0.5738 / boundary 0.5 / toolcall 0.1556 / multimodal 0.0167 / **derivation 0.0** / **physics 0.0**`

⇒ `vericut96:v3` 在**推导与物理维度确实是 0 分**，与上面两个「真缺陷」互相印证：
它们不是判分器问题，是能力缺口。

### 由此得出的结论（回答遗留待决策项）

> 「raw 轨若仍失败，是继续 DPO 修裸权重，还是把验收门改为『生产配置 = 记忆增强轨』为准？」

**答：不能改门。** 记忆增强轨两次测量分别为 5/5 与 3/5，**不可复现**，拿它当验收门等于把门拆了。
`vericut96:v3` 的路只有两条：① 等云端开机后**继续 DPO 修裸权重**（derivation/physics/toolcall 三个维度）；
② 在此之前**把它明确标记为未达标**，不进入生产路由。
六软件 v3 不受此影响——它的 raw 轨本身已 10/10。

---

## 5. 仍未闭环、需要用户决策/操作的事项

1. **云端 AutoDL 已关停**（`117.50.179.122:23` 不通）。
   若要继续补 DPO 语料（如 DPO 侧补 VERICUT 单位隔离对比对），**需要先在 AutoDL 控制台开机**；
   开机后本机 `ssh -p 23 root@117.50.179.122` 即可续上（口令在 Antigravity 步骤日志中，本报告不落盘口令）。
2. **原始 vs 记忆增强双轨**（兄弟会话遗留的待决策项）：**已用证据给出答案 ⇒ 不能改门**。
   记忆增强轨对 `virtu-vericut96:v3` 两次测量分别为 **5/5（21:18）与 3/5（21:34）**，
   **不可复现**；且该标签 raw 轨剩下的两个红条经云端 334 用例早评交叉佐证
   （`derivation 0.0`、`physics 0.0`）属**真能力缺口**。
   ⇒ 建议：① 六软件 v3 维持 raw 轨为验收门（已 10/10）；
   ② `virtu-vericut96:v3` **等云端开机后继续 DPO 修裸权重**（重点是 derivation/physics/toolcall），
      在此之前**明确标记为未达标**、不进入生产路由；③ **不要**把验收门改成记忆增强轨。
3. **并发测量腿的凭证竞态**（本次已处理）：`--verify-only` 固定写
   `checkpoints\deployment_receipt_<tag>.json`，同名标签并发跑会互相覆盖。
   本次 21:26 的新凭证落盘后**已立即按时间戳另存**
   `…VERIFIED_20261115_212646.json`；20:27 的原始失败凭证另存为
   `…PROBE_FAILED_20261115_202737.json`。⇒ **两版凭证并存，可随时对照复核**。

---

## 6. 证据清单

| 文件 | 内容 |
|:--|:--|
| `checkpoints\deployment_receipt_virtu-six-software_v3.PROBE_FAILED_20261115_202737.json` | 原始 PROBE_FAILED 凭证（8/10，未改动） |
| `checkpoints\deployment_receipt_virtu-six-software_v3.json` | 修复判分器后重跑的凭证（10/10，21:26:46） |
| `checkpoints\deployment_receipt_virtu-six-software_v3.VERIFIED_20261115_212646.json` | 上述新凭证的时间戳快照 |
| `tests\test_six_software_probe_measurement_fix.py` | 14 条反证测试（坏样本必红） |
| `cloud_train_pack\deploy_trained_adapter.py` | 判分器修正本体（含 `_looks_truncated` / 否定词表 / 判分器快照） |
| `runs\cloud_pull_six-software-v2_20261115_195913\` | 云端回传的 v3 交付件 + SHA256 |
| `cloud_train_pack\dataset\six_software_v2_{sft,dpo}.jsonl` | 本轮训练语料（SFT 950 行 / DPO 164 行） |
| `cloud_train_pack\dataset\six_software_v2_sft_ledger.json` | 语料台账（行数 / sha256 / token 审计 / 锚点家族） |
| `reports\SIX_SOFTWARE_V3_HANDOVER_2026-11-15.md` | 本文档 |

### 本轮改动清单（仓库内）

| 文件 | 改动 |
|:--|:--|
| `cloud_train_pack\deploy_trained_adapter.py` | 判分器修正 6 处 + 凭证加 `measurement_version`/`grader_sha256` |
| `tests\test_six_software_probe_measurement_fix.py` | **新增**，14 条反证测试 |
| `AGENTS.md` | 新增 §8.2「探针判分器的两类假阴性」，把本类缺陷与反证要求写进项目规约 |

> 未提交 git（仓库本就有大量其他会话的未提交改动，提交需用户明确指示）。
