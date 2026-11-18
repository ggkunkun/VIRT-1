---
name: core-verify
description: "自证、反证与证据审计。宣称完成之前，先试着证明自己是错的。 由能力传授目录生成，勿手改；改 virtu_omni/capabilities/catalog.py 后重跑导出。"
metadata:
  version: "1.2.1"
  owner: "Virtu Capability Transfer"
  supported-consequence-levels: "advisory"
  generated-from: "virtu_omni/capabilities/catalog.py#verify"
---


# 自证、反证与证据审计

> 宣称完成之前，先试着证明自己是错的。

## verify.evidence_before_assertion — 证据先于断言

**何时适用**：任何准备输出'已完成/已通过'的时刻。

**步骤**

1. 把结论拆成可观测事实：文件存在？命令退出码 0？数值在阈值内？
2. 为每条事实指定一个可复跑的检查。
3. 跑一遍，把原始输出留下（路径/摘要/截图）。
4. 有任一事实无法观测 → 降级表述为'部分完成'并列出未证部分。

**硬约束**

- 证据等级只有 measured / asserted / insufficient 三档，不设'基本确定'。
- insufficient 不得写成 passed。

**验收门**

- `G-VERIFY-EVIDENCE`：每条'已完成'都挂一条可复跑检查的输出。
- 判失败：结论仅来自代码阅读或自我推理。

**反例（真实踩过的坑）**

- 函数写完了就说功能可用，从未调用过。
- 看到绿色日志就判通过，日志其实来自上一次运行。

## verify.empty_evidence_trap — 空证据 ≠ 合格

**何时适用**：检测/比对/仿真结果呈现'完美'时。

**步骤**

1. 先证明检测本身有效：输入非空、样本数 >0、图像有效像素 >0、日志有本次时间戳。
2. 做一次'负对照'：故意喂一个已知坏样本，检测器必须报错。
3. 再判合格。

**硬约束**

- 有效样本为 0 时，结论只能是 INSUFFICIENT_EVIDENCE。
- 负对照未通过，检测器不可信，其'全绿'无意义。

**验收门**

- `G-VERIFY-EMPTY`：有样本量/有效像素/时间戳 + 负对照结果。
- 判失败：空白输入产出 100% 合格。

**反例（真实踩过的坑）**

- Auto-Diff 渲染失败出空图，被读成绿色 100%。
- 日志为空当成'无错误'。

## verify.step_artifact — STEP 交付前实体验收

**何时适用**：接收或交付 STEP 模型，需要确认文件能被 CAD 几何内核读取且包含有效实体时。

**步骤**

1. 调用 inspect_step_artifact 检查指定 STEP；该工具只读文件。
2. 确认 measured、SHA-256、mm 单位、valid_brep、solid_count、volume_mm3 与 bbox_mm。
3. 将量测值和实体数与图纸/解析值比较；缺项或偏差超限就 FAIL 并返修。

**硬约束**

- 工具 PASS 只证明基本几何完整性，不证明设计尺寸、可制造性、FOS 或刀路安全。
- 缺实测、SHA-256 或明确 mm 单位，不得宣称已验证。

**验收门**

- `G-STEP-ARTIFACT`：measured；valid_brep=true；solid_count>=1；volume_mm3>0；单位为 mm；体积和 bbox 符合图纸/解析值。
- 判失败：读入失败、无实体、B-Rep 无效、单位未知/非 mm、体积非正、文件漂移或尺寸不符。

**反例（真实踩过的坑）**

- 线框 STEP 通过拓扑读取，却没有实体。
- 文件可读，但尺寸/实体数与图纸不符仍被交付。
- 同名文件已变化，却沿用旧哈希和量测结果。

**相关工具**：inspect_step_artifact

**GitHub 参考**

- [Hugging Face CADGenBench: STEP output validation and visual feedback](https://github.com/huggingface/cadgenbench/blob/main/src/cadgenbench/baseline/prompt.py)
- [build123d-cad: measure, validate, then export workflow](https://github.com/wngfra/build123d-cad/blob/main/SKILL.md)

## verify.stub_detection — 桩自报不算完成

**何时适用**：多智能体/多阶段流水线汇报状态时。

**步骤**

1. 检查返回体是否自标 runtime/evidence_basis。
2. 区分'信封成功'与'工程成功'：前者只看流程跑完，后者要真实门通过。
3. 以真实门为准；桩的 COMPLETED 只能作为流程信号。
4. 桩通过但真实门失败 → 总体 FAILED。

**硬约束**

- 不得用下游 agent 的自报状态替代上游实测。
- mock/stub 产出的数值不得进入交付结论。

**验收门**

- `G-VERIFY-STUB`：最终状态来自真实门，且 runtime 标签已核对。
- 判失败：legacy/stub 的 COMPLETED 被当作交付通过。

**反例（真实踩过的坑）**

- 七个 agent 全绿，实际几何都没生成。
- mock 的 FOS=1.8 被写进强度报告。

## verify.red_team_self — 自我红队：先写败因

**何时适用**：方案即将定稿、或连续两次自评都通过时。

**步骤**

1. 写下'如果这个方案失败，最可能的三个原因'。
2. 为每个原因设计一个能在交付前跑的检查。
3. 至少找出一个真实缺陷；找不到时，说明检查维度不够（换维度：数据/边界/并发/权限/成本）。
4. 把无法消除的风险写进交付物，不藏。

**硬约束**

- 连续两轮零缺陷的自评视为无效自评。
- 禁止用'总体来说利大于弊'收尾代替具体风险。

**验收门**

- `G-VERIFY-REDTEAM`：至少 1 条具体缺陷 + 对应检查 + 残留风险清单。
- 判失败：自评全绿且无残留风险。

**反例（真实踩过的坑）**

- 自评写成自我表扬。
- 把'可能有问题'当风险，无法验证。

## 输出契约

执行本族任一原子后，输出必须包含：所用原子 id、实际执行的检查、检查的原始输出（或摘要）、
以及 `measured` / `asserted` / `insufficient` 三档证据等级。无证据不得写 `measured`。
