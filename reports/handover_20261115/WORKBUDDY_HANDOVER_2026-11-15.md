# 接手报告：Industrial Software Agent Training Samples（2026-11-15）

> 接管自 Antigravity 会话 `Industrial Software Agent Training Samples`
> （conversation id `2e2f3be3-1525-4b53-b60b-50c916013d31`，工作区 `D:\Virtu模型`）
> 接手方：WorkBuddy · 接手时刻：2026-11-15 21:48–21:52 · 实测截止：22:02

---

## 0. 一句话结论

**Antigravity 会话是被额度耗尽（HTTP 429 / `RESOURCE_EXHAUSTED`）中断的，不是任务做完。
接手后按内容寻址复测发现：`virtu-six-software:v3` 的「10/10 验收通过」在当前判分器下不可复现——
同一标签、同一判分器、`temperature=0`，10 项档连测 3 轮为 **8/10、7/10、7/10**，
`sw_coordinate_probe` 与 `lame_stress_probe` 三轮全红。因此当前应判 **未达标/不稳定，不进入生产路由**，
不能用旧凭证宣称已验证。**

好消息是：这不是「必须再烧一轮云端训练」才能定位的问题。训练样本侧的缺口已经查清，
且**现成的 279 行 DPO 修复集就在盘上**（当前只喂给了 `virtu-vericut96:v3`，没喂给 six-software）。

---

## 1. 接手依据：Antigravity 现场（实测）

| 项 | 实测结果 | 证据 |
|:--|:--|:--|
| 会话终止原因 | **AI credits 不足**，`step 1375` 记录 `HTTP 429 Too Many Requests` / `RESOURCE_EXHAUSTED`，原文 `Your AI credits balance is too low to continue` | `~/.gemini/antigravity/conversations/2e2f3be3-….db` 的 `steps` 表末行 |
| 中断前在做的事 | 对 `virtu-six-software:v3` 的 `lame_stress_probe` / `vericut_coordinate_unit_probe` 做原始输出复现（`max_tokens=512`） | 同上，`step 1372–1374` 的 `run_command` 载荷 |
| 已有交接文档 | `reports/SIX_SOFTWARE_V3_HANDOVER_2026-11-15.md`（21:36 定稿，称已修判分器并 10/10） | 文件在盘 |
| 主凭证当前状态 | **`PROBE_FAILED`**（21:40:09），10 项中 7 项通过；**不是**交接文档说的 `DEPLOYED_VERIFIED` | `checkpoints/deployment_receipt_virtu-six-software_v3.json` |
| 判分器已再变 | 凭证记 `grader_sha256=9ce6f480…`，而 21:52 磁盘上已是 `48c8230e…` | `snapshot/snapshot.json` |
| 云端 AutoDL | **仍关停**：`117.50.179.122:23` 连接 `TimeoutError`（21:51 实测） | 本机 socket 探测 |

⇒ 交接文档与当前凭证的冲突不是谁写错，而是**判分器在 21:45 又被并发会话改过**，且模型输出本身存在采样漂移。
按 `AGENTS.md §8.2`，凭证必须绑定判分器哈希；`9ce6f480…` 的 10/10 属于「旧法判决」，不能代表当前。

---

## 2. 复测方法（不碰共享状态）

- 脚本：`scratch/handover_verify_v3.py`，直接调 `deploy_trained_adapter.verify_deployed_model()`，
  **不调用 `--verify-only`、不写 `checkpoints/deployment_receipt_*.json`**——那是并发会话的共享可变状态（§8.3）。
- 结果全部落在独立目录 `reports/handover_20261115/`。
- 内容寻址：每轮记录导入时判分器 sha256、磁盘起止 sha256、Ollama tags digest 起止；
  任一在腿内变化即 `drifted=true`，该腿作废。本次 **5 轮全部 `drifted=false`**。
- 被测对象：标签 `virtu-six-software:v3`，digest `ed409a5e45d807ec…`；
  判分器 `48c8230eaafb29bb25f1687e05417ffd5b29f03db2a9c9a1a2103b97eece871d`，
  `measurement_version=probes-2026-11-15-v2`。
- 判分器自身有效性：`tests/test_six_software_probe_measurement_fix.py` **14 passed**（坏样本必红仍成立）。

### 结果

| 档位 | 轮1 | 轮2 | 轮3 | 失败项 |
|:--|:--|:--|:--|:--|
| `auto`→`general`（7 项） | **5/7** | **7/7** | — | 轮1：`sw_coordinate`、`lame_stress` |
| `all`（10 项，与历史凭证同口径） | **8/10** | **7/10** | **7/10** | 三轮全红：`sw_coordinate`、`lame_stress`；另有 2/3 红：`vericut_coordinate_unit` |

**失败性质（逐条看原始输出，不是猜）：**

1. `sw_coordinate_probe`：三轮原因分别为 `wrong_normal_axis:right`、`wrong_normal_axis:top`、`wrong_normal_axis:top`
   ——模型把 SOLIDWORKS 三基准面法向答错（正确：Front +Z / Top +Y / Right +X）。**真缺陷，不是判分器假阴性。**
2. `lame_stress_probe`：三轮都输出 `厚度 t = Do - Di = 60 mm` 这类错误推导（正确径向厚度应 `(Do−Di)/2 = 30 mm`），
   导致 σ_θ 算不出 33.33 MPa。交接文档 §2.1 说「σ_θ 算对了只是被截断」——**本次复现中不成立**。
3. `vericut_coordinate_unit_probe`：2/3 只讲`inch`单位、不讲坐标系隔离 → 红；另 1 轮绿 ⇒ 行为不稳定。
4. `fanuc_g71_safety_probe`：21:40 凭证为红（G00 负 Z 扎刀），本次 3/3 绿 ⇒ 同一类安全语义也**不稳定**。

⇒ 定性：**当前 v3 是不能稳定通过验收的构件**；旧凭证的 10/10、新凭证的 7/10、我复测的 5/7、8/10、7/10
是同一模型在采样漂移下的不同切片。按 §8.2「验收前先复现再下结论」，应取**连测最差值**做门禁，不能挑最好的一次发布。

---

## 3. 训练样本资产与缺口（任务本体）

| 资产 | 行数 | sha256(前16) | 关键事实 |
|:--|--:|:--|:--|
| `cloud_train_pack/dataset/six_software_v2_sft.jsonl` | 950 | `f9000d74…` | **six-software:v3 的训练语料**（凭证 `dataset_sha256` 与此完全一致）；630 行带 `source_file`/`source_sha256`/`basis`，其中 parser_verified 479 / ocr_verified 93 / measured_occt 58 / closed_form_verified 84；覆盖 369 个源图纸，此前回查命中 367/369 |
| `cloud_train_pack/dataset/six_software_v2_dpo.jsonl` | 164 | `33a64efa…` | 90 行带 `source_file`；VERICUT「坐标/单位隔离」对比对 **0**（唯一 `coordinate_isolation_dpo` 是 SOLIDWORKS 的） |
| `cloud_train_pack/dataset_v2/vericut96_v3_dpo_repair.jsonl` | 279 | `96bb3ba1…` | **现成修复集**，正是 `virtu-vericut96:v3` 凭证的 `dataset_sha256`；含 `lame_closed_form_repair` 24 + `lame_closed_form` 9、`coordinate_unit_isolation_repair` 15 + `coordinate_isolation` 6、`autodiff_triage(_repair)` 39、`fanuc_g71_safety` 6、`sw_plane_notation_repair` 12 等 |

**关键结论**：`virtu-six-software:v3` 的凭证血缘显示 **只用了 SFT 950 行，没用任何 DPO**
（`dataset_sha256=f9000d74…` = SFT 文件哈希）。这与其 `sw_coordinate` / `lame_stress` / 单位隔离行为不稳定高度吻合。
下一步要补的是**把现成 279 行 DPO 修复集并入 six-software 训练**，不是重新造样本、也不是改验收门。

（诚实边界：`virtu-vericut96:v3` 已吃过这 279 行，但云端 334 用例早评显示其 `derivation=0.0`、`physics=0.0`，
说明 DPO 不是万能药；并入后仍需重跑门禁。DPO 侧 164 行只有文件级 sha256 台账，不能逐条回溯到用户图纸。）

---

## 4. 未闭环事项

| # | 事项 | 归属 | 状态 |
|:--|:--|:--|:--|
| 1 | Antigravity 额度耗尽 | **用户** | 需恢复额度或在别处继续；我无法代办充值 |
| 2 | AutoDL `117.50.179.122` 关停 | **用户** | 需控制台开机；本机 22 端口超时（21:51 实测）；开机后才可能继续 DPO |
| 3 | `virtu-six-software:v3` 验收 | 已定性 | **未达标/不稳定**，不进生产路由；主凭证 `PROBE_FAILED` 与复测一致 |
| 4 | `virtu-vericut96:v3` | 已定性 | `derivation/physics` 真缺口，未达标、不进生产路由（见交接文档 §4.1） |
| 5 | 验收门改记忆增强轨 | **否决** | 交接文档已证伪：两次测量 5/5 与 3/5，不可复现，改门等于拆门 |
| 6 | 全量 105 题留出集 | 未测 | 此前腿作废；分层 32 题子集已补跑完成（n=31，Δ+2.55，但安全诊断 −5.36），见 §5 |

---

## 5. 留出集分层子集补跑（已闭环）

此前全量 105 题腿因 Ollama 被并发占用而作废；本次按项目自带恢复脚本
`scripts/finish_holdout_subset.py` 在**独立目录**补跑分层 32 题，未改写他人封缄腿的 `raw.jsonl`。
主测对象仍是 `virtu-vericut96:v2`（与 FULL_BOARD 报告一致），基线 `virtu-master-fixed:latest`。

| 项 | 结果 |
|:--|:--|
| run_id | `2093131bc66865df` |
| 选题 / 有效 | 32 / **31**（复用 12 条 + 新生成 20 条；1 条空回答按脚本口径不计 0 分） |
| coverage / basis | 96.9% / **`measured`** |
| 基线均分 → 主测均分 | **34.25 → 36.81（Δ +2.55）** |
| 分维度 Δ | `pdf_curriculum_qa` **+25.0**(n=4) · `vericut_setup_facts` +16.67(n=1) · `runtime_toolcall` 0(n=5) · `tool_assembly` 0(n=6) · `setup_workoffset` 0(n=6) · `machine_kinematics` 0(n=2) · **`nc_safety_diagnosis` −5.36(n=7)** |

**读法（诚实边界）**：这是**分层子集 n=31 的方向性证据，不是 105 题通过率**；全量腿仍标「未测」。
总增益 +2.55 主要由 4 道 PDF 课程题贡献，**安全诊断维度反而退步 5.36 分**（7 题，样本最大），
与 FULL_BOARD 板块三暴露的 G00 负 Z 扎刀、Auto-Diff 颜色语义错误方向一致
⇒ 支持「该训练范式没有修好、甚至削弱了工业安全语义」的判断。

证据：`holdout_subset/holdout_subset_report.json`、`holdout_subset/holdout_subset_raw.jsonl`、
`holdout_subset/holdout_subset.log`（后台输出）。

---

## 5.1 并发协作说明（重要）

本机同时有**另一个 WorkBuddy 会话**在接手另一条 Antigravity 会话
（`318e3215-c01f-411b-9f92-b2ee6c02b092`，报告见 `reports/WORKBUDDY_TAKEOVER_2026-11-15.md`）。
它的 A/B 测量腿在 21:53 发现本会话的 `handover_verify_v3.py` 正在占用 Ollama，
按 §8.6 主动避让，并把 6 行可能受污染的样本归档为 `.CONTAMINATED_2158`，未写进它的结论。

- 本会话的 Ollama 测量**已全部结束**（最后一腿 22:04:32）；此后不再发起任何模型推理。
- 22:05 检查：只有 `ollama.exe serve` 与**两个** `wait_exclusive_then_ab.py` 守候进程
  （PID 13276 / 6988，来自另一会话）。它的日志仍显示 `recent_chat=True`（等待冷却）。
- **风险提示**：两个守候实例同时存在，若独占窗口出现，可能同时启动两条 A/B 腿而再次互相污染。
  这属于另一会话的资源，本会话**未擅自终止**，仅在此记录，建议由该会话或用户处理。

---

## 5.2 本地开训（2026-11-15 22:37 起，进行中）

用户指令：**两者依次都做** —— 先跑通本地 6GB SFT 链路，再用修复集训 `six-software:v3`。
数据格式由我按证据判断：**取 chosen 转 SFT**（零新增依赖；6GB 上跑真 DPO 风险过高）。

### 已完成

| 步骤 | 结果 | 证据 |
|:--|:--|:--|
| 修复集转 SFT | **279 行 → 279 行**，`prompt_list=221 / prompt_str=58 / skipped=0`，sha `3f4acfae…` | `train_data/six_software_v3_repair_sft_ledger.json` |
| 数据门禁 | **零泄漏**（hard_leaks=0）、**零单位错误**（inertia_unit_bad=0）、零截断；train 255 / dev 24 | `train_data/` + selftest 输出 |
| 本地 6GB 链路 probe | **PASS**：5 条最长样本（seq=1536）forward+backward 全过，loss 0.13–0.20，**峰值显存 5127.8MB / reserved 5868MB**，约 9s/步 | `runs/local_training_20261115/probe_default.log` |

### 遇到并已定位的缺陷（可证伪）

第一轮 `r1_sft_link` 以 **`rc=3221225477`（Windows `0xC0000005` 访问冲突）** 退出，
日志止于 `[LoRA]`、零 `[eval]` 心跳、静默 238 秒 ⇒ 崩溃发生在 **dev 基线评估**，
不是训练主循环。probe 走带梯度前反向多次全过，说明模型本身能跑。

根因：**6GB WDDM 下 `bitsandbytes` 4-bit + pinned `lm_head` 分块 CE 的 `no_grad` 内核路径不稳定**。
修复（两版合并，均已落盘）：

1. **改用带梯度评估**（`loss.backward()` 后立即 `zero_grad(set_to_none=True)` 丢弃梯度），
   走 probe 已验证安全的路径，显存水位与 probe 一致、loss 数值不变；
2. 评估加逐条心跳 `[eval n/m]`、每 8 条 `empty_cache()`、新增 `--dev-max-items` 限制评估条数；
3. 训练主循环加 `[micro n/m]` 心跳——原生崩溃无 Python 栈，靠它定位最后一条成功样本。

### 训练结果（两轮均 COMPLETED / basis=measured）

| 项 | 第一轮 链路验证 | 第二轮 修复训练 |
|:--|:--|:--|
| 底模 | `checkpoints/virtu_cad_cam_merged_v3` | `checkpoints/_deploy_six_software_v3/merged_hf` |
| 数据 | `vericut_e_train_mix.jsonl`（1480 行） | **279 行修复集转 SFT**（`3f4acfae…`） |
| 数据切分 | train 1118 / dev 101 / skipped 261（640 长度截断） | **train 255 / dev 24 / skipped 0 / 截断 0**（tok_max 303） |
| optimizer steps / micro | 8 / 32 | **64 / 255** |
| train loss | 2.1081 → **1.2025** | 2.1872 → **0.0414** |
| dev loss | 1.5457 → **1.3293（Δ −0.2164）** | 2.5713 → **0.6157（Δ −1.9555）** |
| 峰值显存 | 4260.9MB | **4151.0MB** |
| 墙钟 | 81.1 s | **477.6 s（约 8 分钟）** |
| 产物 | `checkpoints/local_sft_link_check/`（adapter 174MB，`17cba630…`） | `checkpoints/six_software_v3_local_repair_lora/`（adapter 174MB，`e1547524…`） |

**关键配置**（6GB 显存保命）：`max_length=640`（低于脚本的 768 激活卸载阈值，
激活留在显存、不向 CPU 卸载）、`grad_accum=4`、`dev-max-items=4/8`。
第一次用 1536 长度跑到 micro 64 时 GPU 空闲一度只剩 91MB 并再次崩掉，降到 640 后全程稳定。

**诚实边界（重要）**：第二轮的 dev loss 是在**修复集内部**按 `idx % 12` 切出的 24 条上测的，
不是独立测试集 ⇒ `−1.9555` 只证明**拟合了修复语料**，**不能据此宣称缺陷已修好**。
adapter 尚未合并进 GGUF、未部署、未重跑那 10 项验收探针 ⇒ 当前**没有**任何证据表明
`virtu-six-software:v3` 的行为已改善。下一步必须：合并 adapter → 量化 GGUF →
注册**新标签**（不覆盖 v3）→ 用同一判分器连测 3 轮对比。

> 并发说明：本机另一会话同时在跑同一训练脚本（`--max-steps 1` 调试崩溃修复）。
> 本会话的编排已收敛为一套（停掉重复实例），训练进程独占 GPU 后才会启动，避免互相 OOM。

---

## 5.3 部署 v4 与同判分器对比（2026-11-16 18:50–19:26）

用户指令「执行」= 继续做合并部署与连测。全程未覆盖 `virtu-six-software:v3` 的权重层。

### 链路（全部实测通过）

| 步骤 | 结果 | 证据 |
|:--|:--|:--|
| LoRA 融合 | **12/12 张量验证 PASS**（err/base 4.7e-04~9.3e-04），5 分片 ~15.3GB | `checkpoints/_deploy_six_v4_local/merged_hf/merge_receipt.json` |
| GGUF Q4_0 | 4,614,301,728 B（与 v3 同尺寸，架构/量化一致） | `virtu-six-software_v4.q4_0.gguf.receipt.json` |
| 新标签 | `virtu-six-software:v4-local-repair`（`965475066318`），**未覆盖 v3** | `ollama list` |

### 对比结果（同判分器 `48c8230e…`、同模板/参数、各 2 轮、`drift=false`）

| 标签 | 轮1 | 轮2 | 稳定失败项 |
|:--|:--|:--|:--|
| `virtu-six-software:v3`（基线） | **10/10** | **10/10** | 无 |
| `virtu-six-software:v4-local-repair`（本次训练产物） | **8/10** | **8/10** | `lame_stress_probe`（缺 σ_θ=33.33）、`vericut_autodiff_probe`（缺 blue） |

### 结论：这次修复训练**失败**，v4 不得上线

1. **目标缺陷没修好，反而变差**：v4 两轮都在同两项上稳定失败（不是采样漂移）。
2. Lamé 的失败形态换了但仍是错：v4 写出了正确公式
   `σ_θ = P_i(Do²+Di²)/(Do²−Di²)`，却把结果算成 **30.00 MPa**（正确 33.33）——
   说明 SFT 只学会了"公式文本"，没学会**算术执行**；这类缺陷靠文本模仿修不动。
3. Auto-Diff 退化为"只讲红、不讲蓝"：训练集里 `autodiff_triage_repair` 的 chosen 多为简短判停口径，
   未覆盖 blue=残料 的完整映射，反而把原有行为挤掉了（典型灾难性遗忘）。
4. **v3 基线其实比昨天的记录更强**：在**安静机器 + 全新存储**下连测 10/10、10/10。
   昨天 21:58–22:01 的 5/7、8/10、7/10 出现在另一会话 A/B 评测并发抢 GPU 的窗口内
   ⇒ 昨天的"不稳定"至少有**环境成分**，不能全算模型缺陷。这一点是对 §5 结论的收紧修正。

**处置建议**：`v3` 继续作为生产基线（当前 10/10×2）；`v4-local-repair` 标记为
**实验失败、不进入路由**。若仍要修 Lamé/Auto-Diff，方向应是：
① 用**带 rejected 的 DPO**（不是 chosen-SFT）压掉错误算术；
② 语料里补**分步算术**与 blue=残料 的完整语义；
③ 混入 replay 防遗忘（本次 255 行全是修复样本，无 replay，是退化主因之一）。

### 附带事故：Ollama 0.40.15 存储不兼容（已处置）

- 现象：`/api/tags` 返回 **0 模型**，日志对每个标签报
  `bad manifest ... The system cannot find the path specified`；`ollama show` 挂起。
- 实测：blob 与清单文件**都在盘且完好**（`abd8b726…` 4.6GB 可读），
  但 0.40.15 新建了 `manifests-v2/` + `metadata/`，读路径与旧 `manifests/` 不一致；
  镜像命名空间、新建空库测试均无法让旧库被识别。
- 处置：**新建独立库** `D:\Virtu模型\.ollama_store\models`，用 blob 的 `.gguf` 硬链/副本
  重建 `virtu-six-software:v3`（权重层 digest 与原 v3 **完全一致**），再导入 v4；
  旧库 `C:\Users\Administrator\.ollama\models`（86GB）**原样保留未动**，可随时回退。
- 代价与边界：新库当前**只有 v3 与 v4 两个标签**，其余 14 个模型（qwen3:8b、bge-m3、
  virtu-vericut96 等）在 0.40.15 下仍不可见；如需使用，得逐个用 blob 重建标签或降级 Ollama。

---

## 6. 证据索引

| 路径 | 内容 |
|:--|:--|
| `snapshot/snapshot.json` | 接手时刻现场快照（判分器哈希、凭证状态、会话终止原因） |
| `snapshot/deploy_trained_adapter_at_handover.py` | 接手时刻判分器源码副本（内容寻址） |
| `snapshot/receipt_main_214009.json` | 接手时刻主凭证副本（防并发覆盖） |
| `verify_auto_round{1,2}.json` / `verify_auto_summary.json` | general 档 2 轮独立复测 |
| `verify_all_round{1,2,3}.json` / `verify_all_summary.json` | all 档 3 轮独立复测（与历史凭证同口径） |
| `scratch/handover_verify_v3.py` | 可复跑的独立复测脚本（不写共享凭证） |
| `holdout_subset/` | 留出集分层子集补跑（独立目录，不改写他人封缄腿） |

> 本轮**未改动**判分器、训练语料、Ollama 标签或他人凭证；所有新文件都在 `reports/handover_20261115/` 与 `scratch/`。
> 未提交 git（工作区本就有大量其他会话的未提交改动）。
