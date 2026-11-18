# V0 准备阶段执行记录 — AE-CI-258

- 执行时间：2026-11-18 22:51:33
- 依据：`production/reports/UNMEASURED_VERIFICATION_PLAN.md`（VP-AE-CI-258-001）
- 结论：**OPEN（软件侧就绪，待现场签字）**
- 统计：PASS 22 / PENDING 8 / FAIL 0

> PENDING = 现场签字项，软件无法取证，不得改写为 PASS。

## 1. 执行明细

| ID | 项 | 状态 | 证据 | 责任 | 待办 |
|---|---|---|---|---|---|
| A1 | 文档：未测项验证计划 | PASS | `{"file": "D:\\Virtu模型\\production\\reports\\UNMEASURED_VERIFICATION_PLAN.md", "bytes": 15330}` | 工艺 |  |
| A2 | 文档：仿真验证报告 | PASS | `{"file": "D:\\Virtu模型\\production\\reports\\VERIFICATION_REPORT.md", "bytes": 8169}` | 工艺 |  |
| A3 | 文档：参数校验清单 | PASS | `{"file": "D:\\Virtu模型\\production\\reports\\PARAMETER_CHECKLIST.md", "bytes": 2163}` | 工艺 |  |
| A4 | 文档：操作与换产手册 | PASS | `{"file": "D:\\Virtu模型\\production\\reports\\OPERATION_CHANGEOVER_MANUAL.md", "bytes": 3353}` | 工艺 |  |
| A5 | NC 清单 nc_manifest.json | PASS | `{"entries": 9}` | 工艺 |  |
| B-prod_5ax_fanuc_0imf-OP1 | prod_5ax_fanuc_0imf/OP1 程序包 | PASS | `{"sha256_match": true, "ascii": true, "no_bom": true, "crlf": true, "size": 4814, "lint": "PASS", "program_id": "1001", "restart": {"OP1": 40}}` | 工艺 |  |
| B-prod_5ax_fanuc_0imf-OP2 | prod_5ax_fanuc_0imf/OP2 程序包 | PASS | `{"sha256_match": true, "ascii": true, "no_bom": true, "crlf": true, "size": 65442, "lint": "PASS", "program_id": "1002", "restart": {"OP2": 40}}` | 工艺 |  |
| B-prod_5ax_fanuc_0imf-OP3 | prod_5ax_fanuc_0imf/OP3 程序包 | PASS | `{"sha256_match": true, "ascii": true, "no_bom": true, "crlf": true, "size": 2094, "lint": "PASS", "program_id": "1003", "restart": {"OP3-A": 40, "OP3-B": 420}}` | 工艺 |  |
| B-prod_5ax_siemens_840dsl-OP1 | prod_5ax_siemens_840dsl/OP1 程序包 | PASS | `{"sha256_match": true, "ascii": true, "no_bom": true, "crlf": true, "size": 5238, "lint": "PASS", "program_id": "AE-CI-258_OP1", "restart": {"OP1": 30}}` | 工艺 |  |
| B-prod_5ax_siemens_840dsl-OP2 | prod_5ax_siemens_840dsl/OP2 程序包 | PASS | `{"sha256_match": true, "ascii": true, "no_bom": true, "crlf": true, "size": 91493, "lint": "PASS", "program_id": "AE-CI-258_OP2", "restart": {"OP2": 30}}` | 工艺 |  |
| B-prod_5ax_siemens_840dsl-OP3 | prod_5ax_siemens_840dsl/OP3 程序包 | PASS | `{"sha256_match": true, "ascii": true, "no_bom": true, "crlf": true, "size": 2025, "lint": "PASS", "program_id": "AE-CI-258_OP3", "restart": {"OP3-A": 30, "OP3-B": 390}}` | 工艺 |  |
| B-prod_5ax_hnc8-OP1 | prod_5ax_hnc8/OP1 程序包 | PASS | `{"sha256_match": true, "ascii": true, "no_bom": true, "crlf": true, "size": 4805, "lint": "PASS", "program_id": "1001", "restart": {"OP1": 40}}` | 工艺 |  |
| B-prod_5ax_hnc8-OP2 | prod_5ax_hnc8/OP2 程序包 | PASS | `{"sha256_match": true, "ascii": true, "no_bom": true, "crlf": true, "size": 65433, "lint": "PASS", "program_id": "1002", "restart": {"OP2": 40}}` | 工艺 |  |
| B-prod_5ax_hnc8-OP3 | prod_5ax_hnc8/OP3 程序包 | PASS | `{"sha256_match": true, "ascii": true, "no_bom": true, "crlf": true, "size": 2085, "lint": "PASS", "program_id": "1003", "restart": {"OP3-A": 40, "OP3-B": 420}}` | 工艺 |  |
| B-PROGNO-prod_5ax_fanuc_0imf | prod_5ax_fanuc_0imf 程序标识唯一 | PASS | `{"program_ids": ["1001", "1002", "1003"]}` | 工艺 |  |
| B-PROGNO-prod_5ax_siemens_840dsl | prod_5ax_siemens_840dsl 程序标识唯一 | PASS | `{"program_ids": ["AE-CI-258_OP1", "AE-CI-258_OP2", "AE-CI-258_OP3"]}` | 工艺 |  |
| B-PROGNO-prod_5ax_hnc8 | prod_5ax_hnc8 程序标识唯一 | PASS | `{"program_ids": ["1001", "1002", "1003"]}` | 工艺 |  |
| B-TOOLSET | NC 引用刀具 ⊆ 刀具清单 | PASS | `{"used": ["T1", "T2"], "known": ["T1", "T2"]}` | 刀具库 |  |
| C1 | 工艺配置标准区间 | PASS | `{"total": 29, "failed": 0, "verdict": "PASS", "failed_gates": []}` | 工艺 |  |
| C2 | 软件门复核（报告 overall） | PASS | `{"lint": "PASS", "roundtrip": "PASS", "collision": "PASS", "travel": "PASS", "overall": "PASS"}` | 工艺 |  |
| C3 | 刀具寿命前置条件（U-11） | PENDING | `{"alarm_tools": ["T1", "T2"], "note": "推导寿命 < 单件切削时间，必须在 V6/U-11 试验后重排换刀"}` | 工艺/刀具库 | 先做 U-11 刀具寿命试验或按每件换刀执行首件 |
| D1 | 量具/设备校准登记 | PENDING | `{"template": "D:\\Virtu模型\\production\\v0\\templates\\gauge_register.csv"}` | 质量/操作 | 现场填写并签字后改 PENDING→PASS |
| D2 | 刀具预调与寿命登记 | PENDING | `{"template": "D:\\Virtu模型\\production\\v0\\templates\\tool_preset_sheet.md"}` | 质量/操作 | 现场填写并签字后改 PENDING→PASS |
| D3 | 夹具与工件零点设置单 | PENDING | `{"template": "D:\\Virtu模型\\production\\v0\\templates\\fixture_zero_sheet.md"}` | 质量/操作 | 现场填写并签字后改 PENDING→PASS |
| D4 | 毛坯入厂检验单 | PENDING | `{"template": "D:\\Virtu模型\\production\\v0\\templates\\stock_receipt_sheet.md"}` | 质量/操作 | 现场填写并签字后改 PENDING→PASS |
| D5 | 安全交底记录 | PENDING | `{"template": "D:\\Virtu模型\\production\\v0\\templates\\safety_briefing.md"}` | 质量/操作 | 现场填写并签字后改 PENDING→PASS |
| D6 | RTCP 标定记录表（U-06） | PENDING | `{"template": "D:\\Virtu模型\\production\\v0\\templates\\U-06_rtcp_record.csv"}` | 质量/操作 | 现场填写并签字后改 PENDING→PASS |
| D7 | 空运行记录表（U-10） | PENDING | `{"template": "D:\\Virtu模型\\production\\v0\\templates\\U-10_dryrun_record.csv"}` | 质量/操作 | 现场填写并签字后改 PENDING→PASS |
| E1 | NC 传输包（ASCII/CRLF/无 BOM/总大小） | PASS | `{"files": 9, "bytes": 243429}` | 工艺 |  |
| E2 | NC 归档副本与哈希 | PASS | `{"files": 9}` | 工艺 |  |

## 2. 生成的现场表单

- D1 量具/设备校准登记：`production\v0\templates\gauge_register.csv`
- D2 刀具预调与寿命登记：`production\v0\templates\tool_preset_sheet.md`
- D3 夹具与工件零点设置单：`production\v0\templates\fixture_zero_sheet.md`
- D4 毛坯入厂检验单：`production\v0\templates\stock_receipt_sheet.md`
- D5 安全交底记录：`production\v0\templates\safety_briefing.md`
- D6 RTCP 标定记录表：`production\v0\templates\U-06_rtcp_record.csv`
- D7 空运行记录表：`production\v0\templates\U-10_dryrun_record.csv`

## 3. V0 放行判定

| 条件 | 结果 |
|---|---|
| 软件侧（A/B/C1-C2/E）全 PASS | 是 |
| 刀具寿命策略（C3，U-11） | PENDING（试验后重排换刀） |
| 现场签字项（D1–D7）全部关闭 | 否（7 项 PENDING） |
| **V0 门** | **OPEN（软件侧就绪，待现场签字）** |

V0 关闭条件：D1–D7 全部签字为 PASS，且 C3 给出 U-11 的换刀策略（每件换刀或试验后重排）。
V0 未关闭前，允许执行 V1（RTCP 标定/空运行），**禁止任何 TC11 切削**。
