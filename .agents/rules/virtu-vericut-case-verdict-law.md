# VERICUT 培训案例判定法（Agent 强制口径）

> 数据源：`knowledge_base/training_case_index.json` → `verdict_layer` + 每个 case 的 `verdict*` / `device_need` / `verification` 字段。
> 查询入口：工具 `query_training_cases`。任何涉及 `E:/training` 案例的正误、设备需求、轴联动问题，必须走该工具实测数据，禁止凭记忆或文件名作答。

## 1. 正误判定口径

- 全库 80 个案例：`error_demo` 12 个、`reference` 68 个。
- 错误案例五类：
  - A·NC 程序本身有错（4）：`lathe_session_day1`、`mill_session_day1`、`millturn_session_day1`、`session_14_MDI_to_validate_part_setup`
  - A·程序碰撞（2）：`VDAF_programming_training_session`、`VDAF_simulation_training_session`
  - B·机床模型位置故意做错（3）：`lathe_session_103l_*`、`mill_session_103m_*`、`millturn_session_103mt_*`
  - C·随工程保存的参数错（2）：`lathe_session_254fl_optimization`、`mill_session_254fm_optimization`
  - D·调试练习工程（1）：`session_112_setting_up_and_using_basic_debugging_tools`
- **A 类案例的仿真报错是教学目标**：Agent 运行这类工程时报错不算执行失败，回答时须说明「这是查错练习，报错为预期结果」。
- 判错的硬证据只有两类：官方讲义 PDF 原文明确写出碰撞/错误/数据错误；官方题名即为查错类（Find and Detect Errors / debugging）。无硬证据不得判错。
- `reference` 仅表示官方按其正常工作流程使用且未发现故意缺陷证据，**不等于已仿真验证零错误**，不得宣称已跑通 VERICUT。

## 2. 设备需求口径

| 能力 | 案例数 |
| --- | --- |
| 车床（2 轴车削 X/Z） | 22 |
| 车铣复合 | 17 |
| 五轴机床（3+2 定位） | 15 |
| 三轴联动铣削 | 13 |
| 四轴（3+1 单旋转轴分度） | 7 |
| 仅模型/工装操作（无切削） | 4 |
| 机器人/VDAF（非 CNC 切削） | 2 |

- 判定顺序：先实测 NC 程序（模态 G0–G3、旋转轴字 ABC、车削循环 G71–G76 / G32 / G92），再用机床 `.mch` 的 Component Type=linear/rotary 交叉核对。
- `RotarySpin="on"` 属主轴自转，不计第四轴。
- 禁止凭案例名、家族名（lathe_/mill_/millturn_）推断轴数；索引中 `capability_basis` 为 `filename_family_inferred` 的案例必须在回答中标注证据等级偏低。

## 3. 五轴联动硬约束

- **本库五轴联动案例数 = 0**。全库逐块实测：同一进给块（G01/G02/G03）内同时变化的旋转轴数量最大值为 **1**，从未出现 2 个旋转轴同时进给。
- 15 个判为五轴的 `mill_session_101m~113m` 及 `session_8/14/18/110/112`、`optimization_review`、`mill_session_6m_day1_review`，其旋转轴动作全部发生在 G00 快速定位/分度块（如 `G0 Z500. B180.`），属 **3+2 定面加工**。
- 因此：除实测到同一进给块内 ≥2 个旋转轴同时变化，否则**禁止**把任何案例判定为五轴联动；用户要真联动案例时，须明说本库没有，并指向自制案例（`D:\Virtu模型\artifacts\aero_closed_impeller\AE_CLOSED_IMPELLER_NASA1975_5AXIS.nc`）。

## 4. 待核验纪律

索引 `verification = pending_verification` 的 23 个案例（加密 `.xmch` 9、无绑定机床 10、机床空白模板 3、NC 用轴机床不具备 1）在回答中必须显式声明「待核验、非确定结论」，不得当成已确认事实，不得据此推导可加工能力。

## 5. 输出要求

1. 引用案例结论必须带 `case_id`，并说明证据等级（NC 实测 / 机床实测 / 仅文件名推断）与核验状态。
2. 「正确案例」不得表述为「已仿真通过」；「错误案例」不得表述为「工程坏掉了」。
3. 本库统计类问题（哪些错、哪些要几轴）一律以 `query_training_cases` 返回的 `verdict_layer` 为准，与其冲突的旧记忆一律以索引为准。
