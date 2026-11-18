---
name: core-write
description: "写作与交付物生成。先定读者与结论，再决定写多少。 由能力传授目录生成，勿手改；改 virtu_omni/capabilities/catalog.py 后重跑导出。"
metadata:
  version: "1.2.1"
  owner: "Virtu Capability Transfer"
  supported-consequence-levels: "advisory"
  generated-from: "virtu_omni/capabilities/catalog.py#write"
---


# 写作与交付物生成

> 先定读者与结论，再决定写多少。

## write.reader_contract — 读者契约

**何时适用**：产出任何给人看的文本。

**步骤**

1. 写之前定三件事：读者是谁、他要用这份东西做什么决定、他有多少时间。
2. 结论前置：第一段给出结论与建议动作。
3. 按'结论→依据→风险→下一步'组织，不按'背景→过程→结果'流水账。
4. 每节只回答一个问题，节标题写结论不写名词。

**硬约束**

- 读者是决策者时，第一屏必须能看到结论。
- 禁止用'随着...的发展'开头。

**验收门**

- `G-WRITE-CONTRACT`：首段含结论；每节标题是判断句。
- 判失败：读完前三段仍不知道要干什么。

**反例（真实踩过的坑）**

- 把过程日志当报告交。
- 写了 8 页，决策者找不到该批还是不批。

## write.deliverable_format — 按载体排版

**何时适用**：交付物是 Office 文件而非聊天文本。

**步骤**

1. 先定载体规则：Word 重层级与页码，PPT 重单页信息密度，Excel 重可计算与可筛选。
2. Word：标题层级 ≤3 级，正文首行缩进，图表带编号与来源。
3. PPT：一页一个论点，标题即结论，正文 ≤3 条支撑。
4. Excel：首行冻结、列宽自适应、数值列右对齐、公式与硬编码分色。
5. 生成后必须打开预览核对：溢出、错位、乱码、空页。

**硬约束**

- 未预览的 Office 交付物不得发出。
- 禁止把 markdown 表格直接粘进 PPT 当正文。

**验收门**

- `G-WRITE-FORMAT`：已渲染预览，无溢出/乱码/空页，编号连续。
- 判失败：只生成了文件但从未打开确认。

**反例（真实踩过的坑）**

- 中文字体缺失导致 PPT 全变宋体方框。
- Excel 长数字被科学计数法截断。

## 输出契约

执行本族任一原子后，输出必须包含：所用原子 id、实际执行的检查、检查的原始输出（或摘要）、
以及 `measured` / `asserted` / `insufficient` 三档证据等级。无证据不得写 `measured`。
