# 全面强化 · 阶段交接（2026-11-16 19:38–19:45）

## 0. 结论先行

**两件真缺陷已定位、强化语料已备好并验证；但训练和 v4 复测被另一会话的训练进程占满 GPU/RAM 挡住，按测评法律第六条熔断，不硬扛、不动他人进程。**

本轮不是"没做事"——把上一轮"回执与实测矛盾"这个悬案查清了，根因是**两把判分尺**，不是模型时好时坏。

---

## 1. 关键发现：回执矛盾 = 判分器版本不同（已定性）

同一模型 `virtu-six-software:v3`、同一组提示词、同一 `measurement_version=probes-2026-11-15-v2`：

| 回执 | 时间 | `grader_sha256` | 三探针 | status |
| --- | --- | --- | --- | --- |
| `VERIFIED_20261115_212646.json` | 21:26 | `d119663e1c0c…` | 全过（raw_all_passed=true） | `DEPLOYED_VERIFIED` |
| `deployment_receipt_virtu-six-software_v3.json` | 21:40 | `9ce6f48068b9…` | 全红 | `PROBE_FAILED` |
| 本轮 11-16 现场复测 | 19:xx | `9ce6f48068b9…` | 7/10，失败项与 21:40 回执**逐字一致** | measured |

11-15 24:00 前后修过判分器的三类假阴性（token 预算截断、负号字符集、否定词缺口），
旧哈希 `d119663e…` 的"全过"是假阳性。**按测评法律第二条，只有修正版 `9ce6f480…` 的结果可作数，
现场 7/10 是可信的。** 上一轮报告里"回执与现场矛盾未查清"的待办，现已关闭。

---

## 2. 三个失败项的根因分类（按 §8.2 先复现原始输出）

| 探针 | 失败 reason | 原始输出证据 | 定性 |
| --- | --- | --- | --- |
| `lame_stress_probe` | `missing_sigma_theta_33.33` | 模型写 `Pi/Pi·(ri/ro…)`，压力比拼凑而非闭合解，漏 σθ=33.33 / σr=-20 | **真模型缺陷** |
| `fanuc_g71_safety_probe` | `valid_F>0, unsafe_G00_negative_Z_plunge` | `N1 G0 X38.0 / N2 G0 Z-25.0`，G00 负 Z 扎刀（致命安全项）+ 无 F 字 | **真模型缺陷** |
| `sw_coordinate_probe` | `missing_normal:front` | 现场与 21:40 回执的 sample 均为**空字符串** | **测量缺陷未排除**：疑似 think 块把内容吞掉后 `_strip_think_blocks` 返回空，不能据空样本判模型缺陷 |

实测发现判分器自身仍有一处窄字符集：`σ_r≈−20MPa`（U+2212 负号）被判红，
而 ASCII `-20` 判绿——这是 §8.2 已记录的老问题，**不该让模型迁就判分器**，
强化语料统一用 ASCII 负号。

---

## 3. 已完成的强化准备（不占 GPU 的部分全部做完）

### 3.1 测量工具修正
- `scripts/run_v3_law_eval_20261116.py` 参数化：可 `--model` / `--out-dir`，默认仍是 v3；
- 修正漂移判定：**只有被测对象 digest 变化才作废**，库里新增无关标签只记录；
- 探针保留完整响应全文（原先只留 400 字片段，无法做 §8.2 根因分析）；
- `scripts/generate_verified_radar.py` 加 `--summary` / `--out-dir`，补 PNG 图例。

### 3.2 强化语料（14 条，全部正反验证通过）
- `scripts/build_full_strengthen_corpus.py`
- `reports/handover_20261115/train_data/full_strengthen_sft.jsonl`
- `…_ledger.json`：`dataset_sha256=1257743a8f0f…`，
  `grader_sha256=48c8230eaafb…`，`n=14`，两族各 7 条。
- 硬约束：每条 chosen 被同一判分器判绿、每条 rejected 必须判红，否则构建直接失败。
  构建过程中确实抓到一条 chosen 被判红（解释性 G71 回答缺 `T01`/`M03`/`S`），已修补后重验。
- 现有 279 条 VERICUT 修复集**不覆盖**这两族，这就是 v4 即使部署成功也修不了的原因。

### 3.3 资源闸（fail-closed）
- `scripts/strengthen_v5_gate.py --check` 实测：
  `GPU free=1933MiB`（需 ≥5200）、`RAM free=3.14GB`（需 ≥9）→ **BLOCKED**，未启动训练。

---

## 4. 被什么挡住（RCFA）

- **现象**：v4 测评 gates 通过后，targeted 阶段 Ollama 返回 500。
- **根因**：另一会话的本地训练进程占满资源——`nvidia-smi` 显示 GPU 5904/5920 MiB，
  可用 RAM 4.64GB / 页面文件 5.76GB。Ollama 日志：
  `llama_model_load: error loading model: std::bad_alloc`；CPU 模式再试则
  `GGML_ASSERT(ctx->mem_buffer != NULL) failed`（exit 0xc0000409）。
- **判定**：不是 v4 模型缺陷、不是代码缺陷，是法律第六条明示的并发占用。
- **处置**：不动他人训练进程；11-15 已有"两个 8B 并发加载死于页面文件不足（OSError 1455）"的实证，
  硬撞只会毁掉两边。测评链保持 `in_progress`，不写假分数。

---

## 5. 资源释放后一条命令收尾

```bash
cd D:\\Virtu模型
# 1) 确认闸变绿（GPU>=5200MiB 且 RAM>=9GB）
.venv\\Scripts\\python.exe scripts\\strengthen_v5_gate.py --check

# 2) 合并 279+14 条语料并训练 v5 适配器（受控 32 steps，已验证显存配置）
.venv\\Scripts\\python.exe scripts\\strengthen_v5_gate.py --execute

# 3) 按已验证路径合并/量化/部署新标签，再按同一法律复测
.venv\\Scripts\\python.exe scripts\\run_v3_law_eval_20261116.py \
    --model virtu-six-software:v5-strengthen \
    --out-dir runs/eval_v5_law_20261116

# 4) 补跑被挡住的 v4 腿（用于证明 v4 确实修不了这两族）
.venv\\Scripts\\python.exe scripts\\run_v3_law_eval_20261116.py \
    --model virtu-six-software:v4-local-repair \
    --out-dir runs/eval_v4_law_20261116

# 5) 同口径对比雷达图（把新腿合成 summary 后调用）
.venv\\Scripts\\python.exe scripts\\generate_verified_radar.py \
    --summary runs/eval_v5_law_20261116/generic/summary.json \
    --out-dir benchmarks/v5_law_radar_20261116
```

**注意**：合并/量化/部署环节（`hf_to_gguf_numpy.py` + `ollama create`）本轮未跑，
必须在资源就绪后按已验证 Modelfile 执行；未部署前不得把 v5 当可测对象。

---

## 6. 本轮可发布与不可发布

| 项 | 状态 |
| --- | --- |
| 回执矛盾根因（判分器两把尺） | **measured / 已定性** |
| 两族真模型缺陷定位 | **measured / 已定性** |
| sw_coordinate 空样本根因 | **未测**（需模型可加载时复现） |
| 14 条强化语料与反证 | **measured / 已验证** |
| v4 全面测评 | **未测**（资源阻塞，gates 已过） |
| v5 训练 / 部署 / 复测 / 对比雷达图 | **未测**（等待资源） |
