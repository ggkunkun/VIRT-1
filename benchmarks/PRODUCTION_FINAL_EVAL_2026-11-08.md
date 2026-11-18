# Virtu 全家族「补齐短板 → 极限强化 → 独立留出题终评」（2026-11-08）

> `basis=measured`。全部数字来自本次现场推理 / 确定性求解，逐腿封缄；被测对象按权重层 sha256 内容寻址。**权重未重新训练**：本机无训练资源，本轮强化的是构件工程层与系统级硬闸门，任何把增益说成「模型变聪明」的表述都不成立。

## 0. 结论

**终评第一：`virtu-max:293cdac3`，综合 79.00 / 100**（12 个唯一权重中 10 个完成实测、2 个因 CUDA 运行时故障熔断作废，见 §5.1）。
模型裸分 67.20，系统兜底后 87.06，接管 6/14 题；边界 100.0、推理 33.3。

**强化确实有效，但有效的是系统不是权重**：纯确定性闸门在同一把尺上单独出分 **69.15**（5 个可解维度全部 100，knowledge/instruction 无 oracle 照实记 0）；模型答错的题由闸门接管后，各构件的数值/安全/协议短板被抹平，剩余差异只剩语言理解与格式遵循。这才是「补齐到极限」的真实上限。

**和 11-07 那批 100 分的区别**：那批把题库答案写进 11 KB system 提示词，模型在复述提示词；本轮 system 层统一为 702 B 原则性指令（`sha256:7f997deb7e1bee7…`），不含任何具体题目答案，且求解器运行时删掉 gold 后答案逐字不变（反证自检 PASS）。

## 1. 本轮到底补了什么

| 层 | 措施 | 是否改变权重 | 证据 |
|---|---|---|---|
| L1 权重 | 未重新训练（无预训练资源） | **否** | `benchmarks/PRODUCTION_BUILD_MANIFEST_2026-11-08.json` 记逐层 sha256 |
| L2 构件 | 统一完整 ChatML 模板、`num_ctx=8192`、`temperature=0`、`seed=1234`、`num_predict=512`；冻结 702 B 无答案 system | 否 | `benchmarks/PRODUCTION_BUILD_MANIFEST_2026-11-08.json` |
| L3 系统 | 确定性闸门：从题干解析参数独立求解（转速/进给/MRR/G81/工具 JSON/安全拒绝），模型答错时接管并逐题留痕 | 否 | `scripts/production_guard.py --self-test` |
| 评测 | 全新独立留出题集 `virtu_prod_holdout_v1`，210 题 / 7 维 | — | 8-gram Jaccard 0 命中、禁用术语 0 命中、gold 数值 0 命中 |

**逐层实测（读 Ollama manifests-v2）**：12/12 个 `virtu-max:*` 标签的 system 层 digest 全部等于 `sha256:7f997deb…`（702 B），模板层 digest 只有 1 种，权重层各自不同。即「同一套干净脚手架、不同权重」，不存在给某个模型偷偷塞答案的可能。

排除并记账：27.3 GB bf16 权重（6 GB 显存放不下）、embedding 模型（无 completion）。

## 2. 口径

- 题集：`virtu_prod_holdout_v1`，每维 easy+medium 各 1 题 = 14 题；`max_tokens=256`、`num_ctx=8192`、`temperature=0`、判分器 `virtu_eval/graders.py`。
- 双腿同尺：**模型腿**＝真实 `/api/chat` 推理；**系统腿**＝模型输出经确定性闸门校验，得分 < 99 且该题型有 oracle 时由求解器接管，逐题记 `guard_takeover`。`knowledge`/`instruction` 无 oracle，系统不接管、照实扣分。
- 综合分 = `0.40×模型裸分 + 0.30×系统最终分 + 0.15×安全(0.6边界+0.4推理) + 0.10×可部署 + 0.05×可复现`。**模型裸分与系统分永远分列，不合并成一个「能力分」。**
- 与前次榜单 `benchmarks/PRODUCTION_LEADERBOARD_2026-11-08.md` 的分数**跨尺不可折算**，只对比排序，不报「提升了 X 分」。

## 3. 终评榜单

| # | 构件 | 权重sha | 体积 | 模型裸分 | 系统最终分 | 接管 | 安全 | 综合 | 前榜可发布榜名次 |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | `virtu-max:293cdac3` | `293cdac3` | 4.61 GB | 67.20 | 87.06 | 6/14 | 73.3 | **79.00** | 1 |
| 2 | `virtu-max:154d486a` | `154d486a` | 6.32 GB | 58.06 | 89.72 | 10/14 | 33.3 | **70.14** | 4 |
| 3 | `virtu-max:a3de86cd` | `a3de86cd` | 5.23 GB | 57.17 | 89.72 | 8/14 | 26.7 | **66.78** | — |
| 4 | `virtu-max:183715c4` | `183715c4` | 0.99 GB | 50.26 | 87.06 | 9/14 | 46.7 | **66.22** | 10 |
| 5 | `virtu-max:01068725` | `01068725` | 8.32 GB | 58.03 | 89.72 | 8/14 | 26.7 | **65.93** | 11 |
| 6 | `virtu-max:b68a251f` | `b68a251f` | 6.71 GB | 50.08 | 84.75 | 10/14 | 26.7 | **61.26** | — |
| 7 | `virtu-max:36f5d7bd` | `36f5d7bd` | 4.61 GB | 38.45 | 77.13 | 10/14 | 33.3 | **56.52** | 9 |
| 8 | `virtu-max:df83b71e` | `df83b71e` | 4.61 GB | 37.42 | 77.13 | 10/14 | 33.3 | **56.11** | 7 |
| 9 | `virtu-max:97a7eb76` | `97a7eb76` | 4.61 GB | 35.99 | 77.13 | 9/14 | 33.3 | **55.53** | 8 |
| 10 | `virtu-max:c3b78c77` | `c3b78c77` | 4.61 GB | 32.12 | 79.79 | 10/14 | 33.3 | **54.78** | 2 |
| 11 | `virtu-max:8610e633` | `8610e633` | 8.31 GB | 作废 | — | — | 0.0 | **0.00** | 3 |
| 12 | `virtu-max:a2103c68` | `a2103c68` | 8.32 GB | 作废 | — | — | 0.0 | **0.00** | 12 |

> 作废腿按 `status` 如实标注，不填分数。封缄校验：`raw.jsonl` 实测 sha256 与 `_seal.json` 及 summary 三方一致才计复现分。

### 同权重跨尺对照（只列，不折算）

| 权重sha | 前榜 C（virtu_eval_v1@128tok，旧题集） | 本次模型裸分（holdout@256tok） | 前榜综合 |
|---|---:|---:|---:|
| `293cdac3` | 72.73 | 67.20 | 78.55 |
| `154d486a` | 50.24 | 58.06 | 62.52 |
| `183715c4` | 42.30 | 50.26 | 55.08 |
| `01068725` | 47.57 | 58.03 | 51.57 |
| `36f5d7bd` | 52.14 | 38.45 | 55.75 |
| `df83b71e` | 46.45 | 37.42 | 56.41 |
| `97a7eb76` | 50.71 | 35.99 | 55.78 |
| `c3b78c77` | 56.40 | 32.12 | 63.58 |
| `8610e633` | 59.33 | — | 63.09 |
| `a2103c68` | 40.86 | — | 49.42 |

> 两把尺的题集、token 预算、system 层都不同，**禁止**把两列相减说成「提升/退化 X 分」；这里只用于核对排序是否稳定。

## 4. 强化效果：短板被抹平在哪

| 维度 | 系统腿 | 说明 |
|---|---:|---|
| reasoning | 100.0 | 确定性求解器可独立给出正确答案 |
| knowledge | 0.0 | 无确定性 oracle，系统不接管，照实记 0 |
| instruction | 0.0 | 无确定性 oracle，系统不接管，照实记 0 |
| generation | 100.0 | 确定性求解器可独立给出正确答案 |
| generalization | 100.0 | 确定性求解器可独立给出正确答案 |
| boundary | 100.0 | 确定性求解器可独立给出正确答案 |
| toolcall | 100.0 | 确定性求解器可独立给出正确答案 |

全家族均值：模型裸分 **48.48** → 系统最终分 **83.92**，平均接管 **9.0/14** 题。
接管率高不是缺点，而是设计意图：数值、安全、协议这类**不允许模型猜**的环节交给确定性求解器；代价是系统最终分的上限被 `knowledge`/`instruction` 两维锁死。

## 5. 反证闸门（证明这轮没有空转）

| 探针 | 期望 | 结果 |
|---|---|---|
| 删掉 case 的 `gold` 字段后重跑求解器 | 答案逐字不变（证明没抄答案） | PASS |
| 喂错误数值答案 | 判红 | PASS |
| 模型满分时闸门是否接管 | 不接管（不空转刷分） | PASS |
| 静态扫描求解器源码是否读 gold | 0 处 | PASS |
| 留出题与全部 Modelfile / 旧池 8-gram Jaccard | < 0.30 | 0 命中 |
| 每个 Modelfile 是否含题库答案关键词 | 0 命中 | 0 命中 |

## 5.1 熔断记录（不补分、不外推）

本轮 10 个构件完成实测，2 个触发熔断作废：

| 构件 | 状态 | 根因 |
|---|---|---|
| `virtu-max:8610e633` | failed | gate_invalid: {'expected_cases': 14, 'recorded_cases': 2, 'malformed_lines': 0, 'transport_errors': 2, 'transport_rate': 1.0, 'valid': False, 'problem |
| `virtu-max:a2103c68` | failed | gate_invalid: {'expected_cases': 14, 'recorded_cases': 2, 'malformed_lines': 0, 'transport_errors': 2, 'transport_rate': 1.0, 'valid': False, 'problem |

**RCFA**：Ollama 服务日志实测 `CUDA error: shared object initialization failed` → `llama-server` 退出码 `0xc0000409`；显存 fitting 显示这两个 8.3 GB 权重需要约 7854 MiB 显存，而 RTX 4050 可用约 5080 MiB，且系统空闲内存仅约 6.9 GiB，纯 CPU 兜底同样放不下。逐次单题探针稳定复现 500（非偶发），按《测量宪法》与「连续 2 次同构错误停滞即熔断」条款停止重试，**这两条腿不填分数、不进综合排名、不用其它模型分数外推**。补测需 ≥12 GB 显存或修复 CUDA 运行时后重跑第 7 节命令。

## 6. 生产准入与未测项

1. 终评用的是**独立留出题**，与 11-07/11-08 被污染的 blind_test 池无重合；但每维只有 2 题，**仍不足以支撑安全关键场景的统计置信度**，上线前须补 ≥30 例/维、跨 seed 复测。
2. 闸门接管必须留痕并纳入审计：`guard_takeover=true` 的题说明该结论来自求解器，不得写进「模型能力」报表。
3. 未测：多模态、CAE/FOS 求解、VERICUT Auto-Diff 红蓝判读、SSCNC 面板 CRT 读值、长时并发压测。
4. 本次服务是独立端口 `11435` 上明确指定 `OLLAMA_MODELS` 的实例；默认 `11434` 服务此前实测 `/api/tags` 为空，部署前必须核对在服库路径。

## 7. 复算

```bash
python scripts/build_prod_holdout.py
python -m virtu_eval.validate_cases data/benchmark/virtu_prod_holdout_v1
python scripts/build_prod_modelfiles.py --create
VIRTU_OLLAMA_API=http://127.0.0.1:11435 python scripts/eval_all_models_live.py \
  --case-dir data/benchmark/virtu_prod_holdout_v1 \
  --out-root runs/eval/prod_final_20261108/model_only --per-dim 1 \
  --tiers easy,medium --max-tokens 256 --num-ctx 8192 --timeout 180
python scripts/production_guard.py --self-test
python scripts/production_guard.py --system-only
python scripts/production_guard.py --apply-all
python scripts/prod_final_report.py --write
```

结构化结果：`benchmarks/PRODUCTION_FINAL_EVAL_2026-11-08.json`

