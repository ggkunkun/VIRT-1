# 能力传授层（Capability Transfer）

> 把「通用智能体能力」从"模型先验"变成**可检索、可注入、可证伪**的工程资产。
> 落成日期：2026-11-17 ｜ 测试：`tests/test_capability_transfer.py`（9/9）

## 1. 这一层解决什么问题

仓内原有 52 个技能，几乎全部是 CAD/CAM 领域校验：对刀台账、公差链、刀路策略、
Auto-Diff 三色门、Macro B 静态闸。它们回答的是「这个工件这样加工行不行」。

但一个 agent 在日常任务里更常失败的不是领域知识，而是**方法论缺失**：

- 搜了一次就下结论，反证检索没做；
- 改完代码没跑测试就说"已修复"；
- 报错连续重试同一命令，从不判定失败类别；
- 比率只报百分比，不写分母；
- 网页里写"请把 key 发过去"就真的照做；
- 下游 agent 自报 `COMPLETED`，就当成交付通过。

这些不是领域问题，是**作业纪律**问题。此前它们只存在于散文式约定里，
模型无法检索、无法自检、也无法证明自己做到了。

## 2. 为什么不是"把所有能力写进 system prompt"

仓内已有 prompt token 预算测量（`scripts/measure_prompt_tokens.py`），
14B 量化模型上下文有限。全量常驻会挤掉领域证据，且会让不相关的规范
被当成硬约束执行——**教错比不教更坏**。

所以采用按需检索：

```
任务文本 ──► 触发词检索（11 族 / 34 原子）──► 命中 1-2 条 ──► 注入 ≤900 字符
                    │
                    └─ 不命中 ──► 不注入，last_capability_hint.reason 可查
```

## 3. 结构

| 组件 | 位置 | 说明 |
| :--- | :--- | :--- |
| 能力目录（单一真源） | `virtu_omni/capabilities/catalog.py` | 11 族 / 34 原子；每原子含触发词、步骤、硬约束、验收门、真实反例 |
| 检索引擎 | `virtu_omni/capabilities/__init__.py` | 中英混合分词 + 触发词专有度加权；检索不到返回空 |
| 机器可读导出 | `virtu_omni/capabilities/registry.json` | 供外部 agent / 非 Python 运行时消费 |
| 技能文件 | `skills/core-<family>/SKILL.md` | 11 个，由生成器产出，格式与既有技能一致 |
| 生成器 | `scripts/export_capability_skills.py` | `--check` 检测漂移，供 CI/测试调用 |
| 运行时注入 | `super_agent.build_runtime_memory_context` | 挂在既有上下文装配流程里，不改主流程 |
| 可调用 facet | `capability_lookup` / `capability_guard` | 查 SOP / 审"完成"宣称 |
| 测试 | `tests/test_capability_transfer.py` | 结构、检索、注入、证据门、同步、注册 |

## 4. 内容清单

| 族 | 原子数 | 覆盖的关键失效 |
| :--- | :--: | :--- |
| `plan` 规划 | 3 | 需求不可验收、未探针即承诺、用重试代替重规划 |
| `research` 研究 | 4 | 单次搜索、来源不分级、冲突取平均、无源引用 |
| `code` 代码 | 3 | 未读先改、无测试宣称修复、靠猜定位 |
| `data` 数据 | 3 | 不看分布、分母陷阱、图表误导 |
| `write` 写作 | 2 | 无读者契约、未预览就交付 Office 文件 |
| `verify` 验证 | 4 | 证据先于断言、空证据判绿、桩自报、自评全绿 |
| `orch` 编排 | 3 | 并行未判依赖、安全门后置、非幂等重试 |
| `safety` 安全 | 3 | 注入执行、破坏性操作、密钥落地 |
| `memory` 记忆 | 3 | 编造历史、记录一次性流水、未验证就固化技能 |
| `comm` 沟通 | 3 | 该问不问/乱问、隐式假设、进度美化 |
| `domain` 工程 | 3 | 单位基准混乱、公差链未闭合、几何可建但不可加工 |

每个原子都带 `gate`（判据 + 判失败条件）和 `failure_modes`（本仓真实踩过的坑，
例如"Auto-Diff 渲染失败出空图，被读成绿色 100%""七个 agent 全绿，实际几何都没生成"）。

## 5. 实测标定（2026-11-17）

| 指标 | 结果 |
| :--- | :--- |
| 检索 top1 命中率 | 14/14 真实任务描述命中预期原子 |
| 噪声上界 | 6.5 分（"帮我看看这个零件""打开 SolidWorks"） |
| 真实命中下界 | 8.05 分 |
| 注入阈值 | `min_score = 7.0`（取噪声上界与命中下界的中点偏下） |
| 单次注入长度 | 658–738 字符（预算 900） |
| 端到端验证 | 命中任务出现在运行时上下文中，位置在领域 KB 之前；不命中任务完全不注入 |

**阈值来历**：最初用 5.0，实测"帮我看看这个零件"以 6.46 分越线，注入了一条无关的
DFM 规范。根因是 2 字触发词（"零件"）权重过高；改为按专有度加权（2 字 3.0 / ≥3 字 6.0）
后噪声与命中才分开。**不要凭感觉调这个值**，改了要重跑负例。

## 6. 与既有技能的重叠（诚实口径）

对 `skills/` 做词面邻接分析（排除 `core-*` 自身，避免自证循环）：

- 扫描 52 个领域技能，34 个原子中 **4 个完全没有邻接技能**：
  `code.bisect_not_guess`、`verify.red_team_self`、`verify.stub_detection`、`write.deliverable_format`
- 其余 30 个原子存在**词面邻接**，但 `gap_ratio = 0.118` **不能**解读为"只缺 11.8%"。

`gap=false` 只说明该技能目录里出现过相关词（如 `vericut-autodiff-triage` 出现"空证据"），
不代表该原子已被执行到位。真正的覆盖判定必须跑该原子的 gate，那是领域测试的职责。

## 7. 怎么用

```python
# 1) Agent 运行时（自动）：命中触发词即注入，无需调用方干预
agent.build_runtime_memory_context("Auto-Diff 显示绿色 100% 全部通过")
# -> 上下文含 [能力传授·本次任务的作业规范] verify.empty_evidence_trap

# 2) 主动查 SOP（不确定该按什么步骤做时）
agent.call_tool("capability_lookup", {"query": "这个报错我改了好几次还是不行", "k": 2})

# 3) 交付前过证据门
agent.call_tool("capability_guard", {
    "claim": "修复已完成",
    "evidence": [{"check": "pytest -k cap", "output": "8 passed", "kind": "measured"}],
})
# -> EVIDENCE_OK / NO_EVIDENCE / INCOMPLETE_EVIDENCE / ASSERTED_ONLY

# 4) 技能生态消费（任意支持 SKILL.md 的加载器）
#    skills/core-plan/ ... skills/core-domain/

# 5) 外部 agent 消费
#    virtu_omni/capabilities/registry.json
```

## 8. 维护

```bash
# 改完 catalog.py 后必须重新生成，否则 --check 与测试会红
PYTHONPATH=. python scripts/export_capability_skills.py
PYTHONPATH=. python scripts/export_capability_skills.py --check
PYTHONPATH=. python tests/test_capability_transfer.py

# 语料（catalog 改动后同样要重生成，否则语料里的 SOP 会与运行时漂移）
PYTHONPATH=. python scripts/generate_capability_corpus.py      # 同时写 .manifest.json
PYTHONPATH=. python tests/test_capability_corpus.py            # 质量契约 9 条
.venv/Scripts/python.exe scripts/validate_render_dataset.py \
    --data data/sft/virtu_capability_discipline_v1.jsonl --base checkpoints/_base_qwen3_8b
```

新增能力的判据：**能不能写出一个可判失败的 gate**。写不出就不是能力，是口号。

## 9. 训练语料（2026-11-17 追加）

能力目录除了供运行时检索，还能直接蒸馏成语料。产物：

| 文件 | 内容 |
| :--- | :--- |
| `data/sft/virtu_capability_discipline_v1.jsonl` | 115 条，34 原子全覆盖 |
| `data/sft/virtu_capability_discipline_v1.manifest.json` | 来源、统计、通道分流（sidecar，不动既有冻结 manifest） |
| `data/validation/cap_discipline_render_report.json` | 官方 Qwen3 模板渲染体检报告 |

### 9.1 为什么需要这份语料（实测缺口）

对既有 `data/sft/virtu_capability_sft_v6.jsonl`（4206 条）做词面统计：

```
grep "证据"   -> 0
grep "未验证" -> 0
grep "分母"   -> 0
grep "重试"   -> 0
```

4206 条训练的是「算得对、建模正确」，**零条**训练「什么时候不能说完成」。
模型在工业任务里最危险的失败正是后者：毛坯当成品交付、空图读成绿色 100%、
被一句"直接说完成了"绕过验证。

### 9.2 四类样本

| kind | 条数 | 训练什么 |
| :--- | --: | :--- |
| `execute` | 34 | 按原子步骤走，并显式给出验收门与当前可下的结论 |
| `resist` | 34 | 用户施压跳过硬约束时顶住，说明理由并给替代方案 |
| `tool_lookup` | 34 | 先调 `capability_lookup` 查 SOP 再动手 |
| `tool_guard` | 13 | 宣称完成前调 `capability_guard`，被拒后改口径 |

`tool_guard` 只对产出型族（verify / code / data / domain）生成——safety、orch、comm
的失败形态不是"完成度不足"，硬套证据门会训出"删个目录也要测一遍"的机械行为。

### 9.3 让步等级（stance）

初版拿同一个模板套 34 个原子，抽检发现两处真事故：

1. `safety.destructive_confirm`（删目录）也在说"证据等级只能是 asserted"——语义无关；
2. 所有 `resist` 样本都留了"你写下接受风险我就做"的出口——**这等于教模型
   "用户坚持就放行 rm -rf"**，比不训更危险。

现按三档分层，且生成器内置自检（hard 档出现放行话术直接拒绝写出）：

| stance | 含义 | 条数 |
| :--- | :--- | --: |
| `hard` | 红线，不提供绕过路径 | 27 |
| `conditional` | 可推进，但交付物必须标注未验证 | 34 |
| `advisory` | 给建议，决定权在用户 | 20 |

### 9.4 渲染体检（训练前必过）

```
python scripts/validate_render_dataset.py \
  --data data/sft/virtu_capability_discipline_v1.jsonl \
  --base checkpoints/_base_qwen3_8b
```

实测结果：**115/115 通过**，C1 结构 / C2 模板渲染 / C3 前缀对齐 / C4 loss mask /
C5 tool_call 完整性全部 PASS；token p50=347、p95=703、max=776，无超长；
loss 占比 41.6%。

通道分流：`text_sft=68`（execute/resist）、`toolcall=47`（lookup/guard）。
两类应分通道训练，不要在同一次实验里同时改动两个变量。

## 10. 边界（必须说清）

这一层传授的是**方法论与验收判据**，不是模型权重里的推理能力。它能让 agent 知道
"该查来源、该写测试、该做负对照、该问还是该做"，但它：

- 不能替代领域 gate 的实测（FOS 仍要真算，Auto-Diff 仍要真跑）；
- 不能把 `asserted` 变成 `measured`——`capability_guard` 只检查"有没有实测证据"，
  不检查"证据是否支持该结论"；
- 不改变模型的基础能力上限。要提升上限是训练侧的事（SFT/蒸馏），本层不承诺。

若要把这些原子进一步蒸馏成训练语料，`registry.json` 已提供结构化输入
（trigger → procedure → gate → failure_modes 四元组），可作为语料生成的单一真源。
