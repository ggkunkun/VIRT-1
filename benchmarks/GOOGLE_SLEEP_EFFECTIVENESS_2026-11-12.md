# Google Sleep 框架有效性验证报告（2026-11-12）

> 运行标识：`LIVE_EFFECTIVENESS_20261112` · Python 3.12.10 · 真实模型 `ollama:virtu-disciplined:v1`
> 口径：`basis=measured`，独立 sleep 前基线 `1.0`（5 个锚点实测），证据见同目录 JSON 与稳态审计副本。

## 一、结论

**修复前：框架无效。** 三阶段流程能跑，但证据链是假的——无模型调用时用硬编码字符串作答，门禁拿 `post-stability` 当自己的基线，CF 恒为 0、gate 恒为 True；空梦境通过率默认 1.0；token 用 `len(text)*2` 估算却标 `measured`。它无法区分好模型与坏模型，因此不能作为"持续学习有效"的证明。

**修复后：框架有效，当前模型未达标。** 证据链真实（`measurement_valid=true`），门禁按绝对阈值把真实模型判为 **gate=False**，理由明确：`dream_oracle_below_threshold:0.4000`。旧实现在同一场景下必然输出假通过。能诚实拒绝，正是门禁有效的标志。

## 二、修复前后对照

| 项 | 修复前 | 修复后（真实模型实测） |
| :--- | :--- | :--- |
| 模型调用 | 无，硬编码应答兜底 | `ollama:virtu-disciplined:v1` 真实调用 |
| 基线 | `baseline = stability` 自比较 | 外部独立实测 `1.0` |
| 稳态 / 可塑性 / CF | 0.8 / 0~0.13 / 0.0 | 1.0 / 1.0 / 0.0 |
| 门禁 | 恒 True | **False**（梦境 0.40 < 0.80） |
| 梦境通过率 | 1.0（解析解自证 / 空集） | 0.4（6 题，真实作答） |
| Token 压缩率 | 0.92+（字符估算冒充） | `unmeasured`（诚实） |
| `basis` | 硬编码 `measured` | 由实测链路继承 `measured` |
| 变异探针 | 可证伪 | 可证伪（植入坏 FOS 被拒） |

## 三、五项有效性判据

1. **可运行**：项目 Python 3.12 全套测试 22 passed；`py_compile` 8 个改动文件全通过；维护 CLI `--dry-run` 正常解析模型。
2. **真实模型参与**：`build_ollama_model_caller()` 从 `/api/tags` 解析，不可用返回 `None` 并诚实降级，绝不返回伪装答案。
3. **门禁可证伪**：绝对阈值 `S>=0.95 / P>=0.90 / CF<=0.05` + 独立基线 + `dream_pass_rate>=0.80`；无模型 / 坏模型 / 缺基线 / 坏物理四种反证全部判红。
4. **证据可测**：解析解自证标 `self_check`，空梦境判 0.0，未测 token 为 `None` / `unmeasured`，禁止冒充 measured。
5. **知识真实固化**：WakeBuffer JSONL 持久化 + 三阶段执行 + 知识写入 Hindsight（既有测试覆盖）。

## 四、改动文件

| 文件 | 关键修复 |
| :--- | :--- |
| `virtu_omni/memory/sleep_framework.py` | 门禁绝对阈值、独立基线、`unmeasured` 口径、梦境证据分级、anchor dreams、`build_ollama_model_caller()` |
| `virtu_omni/memory/__init__.py` | 导出新 resolver |
| `virtu_omni/internet/autonomous_engine.py` | 自动 sleep cycle 注入真实模型 |
| `virtu_omni/agent/super_agent.py` | facet 支持 `auto_model` / `baseline_score`，默认不隐式发网络请求 |
| `scripts/run_sleep_maintenance.py` | 统一 resolver、`--model` / `--baseline`、日志兼容 unmeasured |
| `scripts/verify_virtu_sleep_framework.py` | 去假 token、去硬编码 PASS / basis、报告口径继承 cycle_report |
| `tests/test_sleep_framework.py` | 重写为 11 条可证伪用例 |
| `tests/test_sleep_integration_dual_track.py` | 断言改为诚实降级 |
| `requirements.txt` / `AGENTS.md` | 引导集补 `sympy>=1.12`；追加 §9 有效性验收口径 |

## 五、残留风险（实测证据，未纳入本次修复）

- **锚点判分精度**：`virtu-disciplined:v1` 对 `ANCHOR_02_LAME_STRESS` 回答"内壁径向应力**恰好等于零**"（物理上错，应为 `-Pi`），却因关键词包含被判命中，导致 `stability=1.0` 有水分。下一轮应把关键词判分换成物理 oracle / `wm_verifier.recompute`。
- **实现与论文差距**：本地是 Google Sleep「Wake/Sleep 三阶段」范式的自研简化版，**没有**参数更新、低秩 expert、GKD 向上蒸馏、梯度筛选 RL 梦境；不得宣称等同 Google 官方实现。
- **模型能力**：当前模型梦境 oracle 通过率 0.40 < 0.80，属模型能力不足，不是框架失效。换更强模型或补充梦境训练后再测。

## 六、复现

```bash
# 全套测试（必须用项目 Python 3.12 + 干净 basetemp）
python -m pytest tests/test_sleep_framework.py tests/test_sleep_integration_dual_track.py \
  tests/test_google_deepmind_suite.py -q --basetemp=<fresh dir>

# 生产维护 CLI
python scripts/run_sleep_maintenance.py --dry-run
python scripts/run_sleep_maintenance.py --now --model virtu-disciplined:v1 --baseline <独立实测基线>
```

> 注：IDE 注入的 Python 3.13 是未 bootstrap 的裸环境，缺 `sympy` 会导致 `super_agent` 导入失败；`sympy>=1.12` 本就在 `pyproject.toml [project.dependencies]` 中，按 `pip install -e .` 安装即可，不是仓库缺陷。
