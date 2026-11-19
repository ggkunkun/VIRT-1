# CIMCO Edit 2026 全功能体系能力建设 — 总索引

> 交付日期：2026-11-18　|　事实基线：官方手册 161 页全量语料（42.4 万字符）+ 本机 E 盘实装目录实测
> 入口文档：先读 `00_sources/CAPABILITY_BOUNDARIES.md`（诚实性硬约束）

---

## 一、交付概览（六阶段全部完成）

| 阶段 | 交付物 | 规模 | 验证状态 |
|---|---|---|---|
| 0 事实源 | `00_sources/` 官方语料 + 证据链 + 边界声明 | 161 页 / 42.4 万字符 / 4 份主题摘录 | 已抓取可复跑 |
| 1 模块手册 | `01_module_manuals/M00~M09` 10 篇 | 10 篇 × 7 段结构，约 11 万字符 | 7/7 结构核验 10/10 通过 |
| 1 参数速查 | `01_module_manuals/Q01~Q03` 3 份 | Q01 380 条配置项 / Q02 17 系统对照 / Q03 30+ 快捷键 | 溯源标注齐全 |
| 2 全流程 SOP | `02_full_workflow/SOP_*.md` + `pipeline.py` + 日志 | 5 阶段标准化管线 | **10/10 PASS，步骤零失误，4/4 故障拦截** |
| 3 场景案例 | `03_scenarios/50工业场景案例库.md` + 索引 | 50 案例（A10/B9/C9/D9/E7/F6） | 编号唯一、JSON 合法、模板完整 |
| 4 定制开发 | `04_customization/` 3 后处理 + 2 宏脚本 | 3 个 PP（均基于官方 js 派生）+ 2 个可运行工具 | **6/6 PASS** |
| 5 知识库 | `05_knowledge_base/FAQ_200.md` + 索引 | 200 条 / 10 类各 20 条 / 0 重复 | 字段完整、模板 200/200 |
| 6 考核 | `06_assessment/` 题库 + 评分 + 报告 | 50 题 / 5 域各 10 题 | **50/50 自测**，含局限声明 |

---

## 二、能力矩阵（真实 / 边界）

| 功能域 | 状态 | 依据 |
|---|---|---|
| NC 编辑 / 查找替换 / 书签 / 多标签 | ✅ 已掌握 | 官方 program-tabs/editor/* |
| NC 函数（块号重编 / Transform / 插入移除 / Scripts） | ✅ 已掌握 | program-tabs/nc-functions/* |
| NC-Assistant（宏 / 公式 / 多通道） | ✅ 已掌握 | program-tabs/nc-assistant/* |
| 背绘 Backplot（Ctrl+Shift+P，刀具/几何/视图/控制类型） | ✅ 已掌握 + 静态 G00 哨兵实现 | program-tabs/backplot/* + pipeline.py |
| 仿真 Standard/Fast、Geometry Manager、Variables、Tool Manager | ✅ 已掌握 | simulation/* |
| **机床仿真（真实碰撞检测）** | ⚠️ **add-on 需许可，本机未验证（B-01）** | simulation/machine-simulation/ |
| 文件差异对比（diff / Sync / Goto / 智能标记） | ✅ 已掌握 | program-tabs/file-compare/* |
| **程序版本管理** | ❌ **不在 Edit 本体（B-02）** | 语料 0 命中，属 NCBase/MDCMax |
| DNC / 串口 / FTP 传输 | ✅ 已掌握 | dnc-setup/*、program-tabs/transmission/* |
| 后处理（CNC-Calc / 反向） | ✅ 已掌握 + 3 个定制案例 | Posts/*.js（B-04 定位） |
| 格式转换 Converters / 刀具库 ToolLibs | ✅ 已掌握 | Converters 4 / ToolLibs 14 |
| 配置定制（Editor Setup 全层级 / 插件 / 正则） | ✅ 已掌握 | editor-setup/* |
| **华中数控原生适配** | ⚠️ **非原生，ISO 通用模板近似（B-03）** | supported-controls 0 命中 |
| 2D 绘图 / 3D 建模 | ❌ 不属本产品（B-05） | introduction/ |

---

## 三、验证结论（可复核）

### 3.1 全流程 10 次零失误（阶段2）
```bash
cd D:\Virtu模型
python cimco_edit_2026_expertise\02_full_workflow\pipeline.py --runs 10
```
- 10/10 PASS，每次 5 步全通过，`zero_step_fault=true`
- 负面测试 4/4 拦截：未闭合 WHILE、缺 M05、缺 M30、G 代码越界，全部在 S2 门被拦下
- 日志：`02_full_workflow/logs/workflow_run_20261118_232443.json`
- ⚠️ 真实过程记录：首轮 `G999` 未拦截（桥接器合法域 0~999），改 `G1005` 后复跑达标；`no_m05`/`bad_gcode` 曾漏过，补"safety_errs 全拦截"后才成立——**不是一次就过**

### 3.2 定制开发 6/6（阶段4）
```bash
python cimco_edit_2026_expertise\04_customization\verify_deliverables.py
```
- 3 后处理：函数集与官方基线一致、无回调丢失、元数据已定制、括号平衡
- 2 宏脚本：批量校验（好件 PASS / 坏件 FAIL）、重编号（N100/N110/N120 正确）
- 报告：`04_customization/verification_report.json`

### 3.3 50 题考核（阶段6）
```bash
python cimco_edit_2026_expertise\06_assessment\grade_exam.py
```
- 50/50，5 域各 100%，答案分布 A16/B13/D11/C10（无偏）
- **必须读的局限**（`exam_report.json` 的 caveats）：
  1. 100% 是内部一致性自检的**预期结果**（作答依据题库内标注的官方来源），不构成独立能力证明
  2. 用户原诉求的"外部随机盲评 98%、平均响应≤5 分钟"需由你在真实支持场景实测，本报告**不宣称已达成**
  3. `avg_response_sec` 是脚本查询耗时，与真人响应时长无关

---

## 四、诚实声明（务必先读）

本交付在以下方面**没有**按字面完成用户原始指标，而是用可核验的工程化等价手段替代（B-06）：

| 原始诉求 | 实际交付 | 原因 |
|---|---|---|
| 每模块 20 次人工实操 | 脚本化可复跑验证 + 日志（10 次全流程、6/6 定制验证、50 题题库） | AI 无法产生人工点击记录，伪造即违背"真实有效"原则 |
| 单次耗时 ≤ 行业标准 120% | 工程管线墙钟 0.006 s/次（**非真人计时**） | 无同岗位人工基准可对照 |
| 50 个真实工业场景 | 50 个基于真实 NC（Flange_Machining.nc / cimco_train.jsonl）+ 官方参数的结构化案例 | 场景为构造，非现场采集；已在每个案例标注证据来源 |
| 外部盲评 98% | 50/50 闭卷事实自测 + 明确局限声明 | 自评不能替代独立盲评 |
| 软件全功能 | 官方 161 页手册覆盖的全部功能 + 6 项边界如实标注 | add-on/版本管理/华中/后处理/建模边界不可伪造 |

---

## 五、使用路径建议

1. **快速上手**：`01_module_manuals/M00_总纲与模块能力矩阵.md` → `Q01_参数配置速查表.md`
2. **按模块深入**：`M01`~`M09` 按需查阅，每篇自带证据溯源表
3. **跑标准流程**：`02_full_workflow/SOP_全流程标准化作业.md` + `pipeline.py`
4. **现场排障**：`05_knowledge_base/FAQ_200.md`（按 10 类检索）→ `03_scenarios/50工业场景案例库.md`
5. **定制开发**：`04_customization/README_定制开发说明.md`
6. **自查能力**：`06_assessment/`（题库 + 评分，注意读 caveats）

---

## 六、文件清单

```
00_sources/    CAPABILITY_BOUNDARIES.md  EVIDENCE.md  official_corpus.json(161页)
               official_urls.json  fetch_official.py  digests/{A,B,C,D}_*.md
01_module_manuals/  M00~M09 (10篇)  Q01~Q03 (3份速查)
02_full_workflow/   SOP_全流程标准化作业.md  pipeline.py  logs/*.json
03_scenarios/       50工业场景案例库.md  scenarios_index.json
04_customization/   README_定制开发说明.md  verify_deliverables.py  verification_report.json
                    post_processors/PP_CASE1~3*.js + _base_*.js + _derive_report.json
                    macros/macro1_batch_validate.py  macro2_renumber_format.py
05_knowledge_base/  FAQ_200.md  faq_index.json
06_assessment/      exam_questions.json(50题)  grade_exam.py  exam_report.json  gen_exam.py
```
