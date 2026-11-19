---
trigger: always_on
description: "Virtu 测评法律（2026-11-16 立）。AGENTS.md §8 测量宪法在 Agent 测评场景的可执行细化：内容寻址、判分器口径、空回答、未测腿、样本偏斜、并发占用、雷达图。凡测评/基准/排行榜/雷达图相关动作一律先过本法律。"
---

# Virtu 测评法律（Evaluation Law）

> 本文件是 `AGENTS.md §8 测量宪法` 在 **Agent 测评场景**的可执行细化，不替代宪法。
> 立法依据：2026-11-15 全面测评 `VIRTU_FULL_BOARD_2026-11-15.md` 暴露的七类真实事故。
> 适用范围：任何 `benchmarks/`、`runs/**/comparison_report.json`、排行榜、雷达图、向用户口述的模型分数。
> 违反任一条 ⇒ 该数字**未测**，不得发布、不得进雷达图、不得写"变强/变弱"。

---

## 第一条 · 被测对象按内容寻址（名字不是身份）

起腿前必须 `RunIdentity.capture(model_ids=..., case_dirs=..., ruler_files=...)` 并写 `<out>/identity.json`；
收腿必须 `drift()` 为空。标签被重指（实测 `virtu-vericut-e:latest` 从 `9d9f8aa5…` 变成 `92323c5d1…`）时：

- 该腿成绩只能归属于 **digest `9d9f8aa5…` 那份字节**，不得再叫"vericut-e 的成绩"；
- 报告中必须同时写出标签和 digest，且标注重指时间与新 digest；
- 同名标签的跨会话分数不得合并进一个时间序列。

## 第二条 · 判分器口径必须显式标注，且绝对分只能作相对比较

每个分数必须带 `grader_version` / `grader_sha256` / `basis`。实测陷阱：

- `run_domain_ab.py::slot_exact_v2` 把连续汉字串切成整 token，"背吃刀"命中不了"背吃刀量"——
  120 条里 25 条内容正确被判 0；改用 `substring_any_v1` 后各臂抬分 28–42 且**排序反转**。
  ⇒ 该基准的绝对分**不得**当作能力结论，只可作同尺 A/B 相对比较，且必须写明版本。
- 同一题板换判分器 = 两把尺，**禁止**跨尺比较或拼接时间序列。
- 新增/改动判据必须同时提交"植入坏样本 ⇒ 必须红"的反证测试；只有好样本变绿不算修复。

## 第三条 · 空回答 / 传输错误一律判红，不得记 0 分后冒充能力

- `score=None` + `verdict=transport_error/empty_response`，从有效样本中剔除，**不得**当 0 分入均值。
- 实测事故：`qwen3:8b` 在 `/api/generate` 下 24/24 空 `response`，被 `run_domain_ab.py` 记成
  `verdict=scored` 打 0 分。凡 thinking 模型必须走 `/api/chat` + `think=false`，或从 `message.thinking` 取回内容。
- 腿级 `n_valid=0` 或传输错误率 > 5% ⇒ 该腿 `basis=partial/voided`，不得写"measured"。

## 第四条 · 未测就是未测，禁止补分、禁止推断、禁止沿用常量

- 没跑完的腿写"未测"；不得把源码里的 `HISTORICAL_BASELINES` / `physics_compliance` 字面量
  当实测值发布（2026-11-05 事故已定性）。
- 历史腿可以引用，但必须带 `run_id` + 证据路径 + 原口径，并明确写"这不是本次被测对象的成绩"。
- 雷达图上未测的维度/模型**留空**，不得补 0、不得插值、不得用上一轮数据"顶上"。

## 第五条 · 样本必须覆盖题板声明的全部维度，偏斜腿作废

- 实测事故：留出集主测腿按题板顺序只跑完 30/105，只覆盖 2 个维度（其余 6 维 0 样本），
  却试图与基线全量算配对 delta ⇒ 腿作废。
- 任何配对 delta 要求两侧 `n` 相同且 `by_dimension` 键集合一致；抽样必须分层并按 `id` 确定性选取。
- 只跑完一部分时，tico 只能发布"已完成子集"的**方向性**结论，且明确标注 `scope=stratified_subset_not_full`。

## 第六条 · 测量链独占；外部并发占用 ⇒ 作废受影响腿，不硬扛

- 起链前查 `ollama ps` / `nvidia-smi` 空闲显存；链在跑时禁止其他会话重部署/重指标签。
- 实测事故：外部会话并发加载 v2/v3 系列把空闲显存从 5.8 GB 压到 1.8 GB，`/api/tags`、
  `/api/chat`、`ollama ps` 连续超时，留出集腿停在 30/105。
- 超时/退化为 CPU 推理的腿不得与 GPU 空闲时段的腿比速度；同构错误连续 3 次 ⇒ 按 §6 熔断，
  写 RCFA，不盲目重试。

## 第七条 · 雷达图 / 排行榜只画 measured，且必须能点回证据

- 图上每个点的 hover/标注必须含 `run_id`、`n`、`basis`、`grader_version`、`digest`。
- 未测腿不出现在图上（不是 0 分点）；不同口径的点不得画在同一条折线上。
- 生成后必须用反例自检：喂一个 `basis=未测` 的腿，图必须不出现该点；否则雷达图判红。

---

## 立后立即执行（2026-11-16 首次适用）

1. 检查 `virtu-six-software:v3` 的 digest / served_layers，确认与 21:40 `VERIFIED` 回执一致；
2. 若 v4 在测量期间完成部署并重指标签，按第一条作废受影响腿并重新起链；
3. 全部测评数字写入 `benchmarks/VIRTU_EVAL_LAW_2026-11-16.json`，每条带 n/basis/evidence/run_id；
4. 雷达图只使用本文件约束下产生的 measured 点，并附反例自检结果。
