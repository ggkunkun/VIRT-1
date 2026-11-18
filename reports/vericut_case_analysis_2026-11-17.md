# VERICUT 官方培训案例：错误分析与复现报告

> 生成时间（UTC）：2026-11-17T11:59:35+00:00
> 案例索引：`knowledge_base/training_case_index.json`
> 索引数据基准：`2026-11-17T11:52:12+00:00`；核验报告：`knowledge_base/error_case_verification.json`（2026-11-17T11:33:45+00:00）
> 口径：错误案例 = 官方讲义明确要求学员发现/修正的缺陷；参考案例 = 官方按正常工作流程使用、未发现故意缺陷证据，本次未重跑。

## 1. 总览

| 指标 | 数值 |
|---|---|
| 案例总数 | 80 |
| 错误案例（工程） | 12 |
| 错误案例（独立程序） | 1 |
| 参考/正常案例 | 68 |
| 已复现（reproduced） | 8 |
| 讲义明示 + 数据存在（attested） | 3 |
| 部分静态复现（partial） | 1 |
| 仅推断（inferred） | 1 |
| 未复现 / 未核验 | 0 |

### 1.1 全部案例的加工能力分布

| 所需能力 | 案例数 |
|---|---|
| 车床（车削，X/Z 为主） | 22 |
| 车铣复合 | 17 |
| 五轴定位（3+2，需五轴机床但非联动） | 15 |
| 普通三轴联动铣削 | 13 |
| 四轴（单旋转轴） | 7 |
| 仅模型/工装操作，无 NC 切削 | 4 |
| 机器人/VDAF（非 CNC 主轴切削） | 2 |

## 2. 错误类型与复现状态

| 错误类型 | 数量 | 已复现 | 讲义明示 | 部分 | 仅推断 |
|---|---|---|---|---|---|
| NC 程序错误/碰撞 | 3 | 3 | 0 | 0 | 0 |
| 机床模型偏置故意放错 | 3 | 3 | 0 | 0 | 0 |
| 刀库优化数据错误 | 2 | 0 | 2 | 0 | 0 |
| VDAF 碰撞/工艺错误 | 2 | 0 | 1 | 1 | 0 |
| NC 偏置/配置错误 | 1 | 1 | 0 | 0 | 0 |
| 刀具长度/装夹错误 | 1 | 1 | 0 | 0 | 0 |
| 碰撞检测演示 | 1 | 0 | 0 | 0 | 1 |

## 3. 错误案例总表

| # | 案例 | 系列 | 错误类型 | 所需能力 | 复现状态 | 验证方法 |
|---|---|---|---|---|---|---|
| 1 | `lathe_session_103l_add_3d_models_to_the_machine` | 车床 L | 机床模型偏置故意放错 | 车床（车削，X/Z 为主） | 已复现 | 静态实测 |
| 2 | `lathe_session_254fl_optimization` | 车床 L | 刀库优化数据错误 | 车床（车削，X/Z 为主） | 讲义明示 + 数据存在 | 讲义明示 + 数据存在 |
| 3 | `lathe_session_day1` | 车床 L | NC 程序错误/碰撞 | 车床（车削，X/Z 为主） | 已复现 | VERICUT 动态仿真 |
| 4 | `mill_session_103m_add_3d_models_to_the_machine` | 铣削 M | 机床模型偏置故意放错 | 五轴定位（3+2，需五轴机床但非联动） | 已复现 | 静态实测 |
| 5 | `mill_session_254fm_optimization` | 铣削 M | 刀库优化数据错误 | 普通三轴联动铣削 | 讲义明示 + 数据存在 | 讲义明示 + 数据存在 |
| 6 | `mill_session_day1` | 铣削 M | NC 程序错误/碰撞 | 四轴（单旋转轴） | 已复现 | VERICUT 动态仿真 |
| 7 | `millturn_session_103mt_add_3d_models_to_the_machine` | 车铣 MT | 机床模型偏置故意放错 | 车铣复合 | 已复现 | 静态实测 |
| 8 | `millturn_session_day1` | 车铣 MT | NC 程序错误/碰撞 | 车铣复合 | 已复现 | VERICUT 动态仿真 |
| 9 | `session_112_setting_up_and_using_basic_debugging_tools` | 通用 | NC 偏置/配置错误 | 五轴定位（3+2，需五轴机床但非联动） | 已复现 | VERICUT 动态仿真 |
| 10 | `session_14_MDI_to_validate_part_setup` | 通用 | 刀具长度/装夹错误 | 五轴定位（3+2，需五轴机床但非联动） | 已复现 | VERICUT 动态仿真 |
| 11 | `VDAF_programming_training_session` | VDAF | VDAF 碰撞/工艺错误 | 机器人/VDAF（非 CNC 主轴切削） | 讲义明示 + 数据存在 | 讲义明示 + 数据存在 |
| 12 | `VDAF_simulation_training_session` | VDAF | VDAF 碰撞/工艺错误 | 机器人/VDAF（非 CNC 主轴切削） | 部分静态复现 | 静态实测 + 讲义明示 |
| 13 | `detect_collision.mcd` | 独立程序 | 碰撞检测演示 | 五轴定位（3+2，需五轴机床但非联动） | 仅推断 | 资产用途推断 |

## 4. 分类详情

### 4.1 NC 程序错误/碰撞（3）

#### `lathe_session_day1`

- 错误类型：NC 程序错误/碰撞
- 复现状态：**已复现**（`reproduced`）
- 验证方法：VERICUT 动态仿真；置信度 `measured`
- 讲义证据：Verification Session 3L 1 Session 3L Find and Detect Errors The main reason we use simulation is to detect all the errors in the NC program before it goes to the machine. Vericut provides many ways to detect errors and precisely find which line in the NC prog
- 核验目标：Session 3L: 刀具 "1" 碰撞 "Jaws"，第 23 行 N1100 Z-1.81
- 实测证据：
  - `错误:在 23 行:N1100 Z-1.81 ,刀具 "1" 碰撞 "Jaws"`
- 原始日志：[lathe_session_day1.log](vericut_error_case_logs/lathe_session_day1.log)

#### `mill_session_day1`

- 错误类型：NC 程序错误/碰撞
- 复现状态：**已复现**（`reproduced`）
- 验证方法：VERICUT 动态仿真；置信度 `measured`
- 讲义证据：Verification Session 3M 1 Session 3M Find and Detect Errors The main reason we use simulation is to detect all the errors in the NC program before it goes to the machine. Vericut provides many ways to detect errors and precisely find which line in the NC prog
- 核验目标：Session 3M: 刀具 "9" 的刀柄 "Holder1" 与 "Fixture" 碰撞（第 280/281 行）
- 实测证据：
  - `错误:在 280 行:N201 X4.125 Y2.00 Z1.07,组件"Tool"上刀具"9"的刀柄"刀柄"Holder1""与"Fixture"碰撞`
  - `错误:在 281 行:N202 G28 G91 Z0,组件"Tool"上刀具"9"的刀柄"刀柄"Holder1""与"Fixture"碰撞`
- 原始日志：[mill_session_day1.log](vericut_error_case_logs/mill_session_day1.log)
- 说明：仿真完整结束：错误数 12、警告数 3；printargs 只打印命令行，不改变仿真模式

#### `millturn_session_day1`

- 错误类型：NC 程序错误/碰撞
- 复现状态：**已复现**（`reproduced`）
- 验证方法：VERICUT 动态仿真；置信度 `measured`
- 讲义证据：Verification Session 3MT 1 Session 3MT Find and Detect Errors The main reason we use simulation is to detect all the errors in the NC program before it goes to the machine. Vericut provides many ways to detect errors and precisely find which line in the NC pro…
- 核验目标：Session 3MT: 第 165 行 G1 A0. F20. 时 Tool HOLDER 与 Sub_Fixture 碰撞
- 实测证据：
  - `错误:在 165 行:G1 A0. F20.,"Tool CUTTER"和"Sub_Fixture"碰撞.`
  - `错误:在 165 行:G1 A0. F20.,"Tool HOLDER"和"Sub_Fixture"碰撞.`
- 原始日志：[millturn_session_day1.log](vericut_error_case_logs/millturn_session_day1.log)
- 说明：仿真完整结束（END-OF-FILE），另有 5 条警告

### 4.2 机床模型偏置故意放错（3）

#### `lathe_session_103l_add_3d_models_to_the_machine`

- 错误类型：机床模型偏置故意放错
- 复现状态：**已复现**（`reproduced`）
- 验证方法：静态实测；置信度 `measured`
- 讲义证据：the Appearance Pallet and select a desired appearance • Set Rapid Rate = 200 • Add model, File Name = mc_lathe_machine_z.stl The component and model are not located correctly. The Z axis Zero position should be 32.25” from the machine origin, so a 32.25”offset…
- 核验目标：Z 轴应偏移 32.25 ”
- 实测证据：`lathe_session_103l_add_3d_models_to_the_machine.mch 的 Z 组件 Position={'X': '0', 'Y': '0', 'Z': '0'}`

#### `mill_session_103m_add_3d_models_to_the_machine`

- 错误类型：机床模型偏置故意放错
- 复现状态：**已复现**（`reproduced`）
- 验证方法：静态实测；置信度 `measured`
- 讲义证据：Appearance Pallet and select a desired appearance • Set Rapid Rate = 5000 • Add model, File Name = mc_mill_machine_5ax_z.stl The component and model are not located correctly. The Z axis Zero position should be 600mm from the machine origin, so a 600mm offset …
- 核验目标：Z 轴应偏移 600.0 mm
- 实测证据：`mill_session_103m_add_3d_models_to_the_machine.mch 的 Z 组件 Position={'X': '0', 'Y': '0', 'Z': '0'}`

#### `millturn_session_103mt_add_3d_models_to_the_machine`

- 错误类型：机床模型偏置故意放错
- 复现状态：**已复现**（`reproduced`）
- 验证方法：静态实测；置信度 `measured`
- 讲义证据：= mc_millturn_machine_subspindle.stl • In Configure Model > Translate tab • Angles = 180 0 90 • Press Enter on your keyboard The component and model are not located correctly. The W axis Zero position should be 1972mm from the machine origin, so a 1972mm offse…
- 核验目标：W 轴应偏移 1972.0 mm
- 实测证据：`millturn_session_103mt_add_3d_models_to_the_machine.mch 的 W 组件 Position={'X': '0', 'Y': '0', 'Z': '0'}`

### 4.3 刀库优化数据错误（2）

#### `lathe_session_254fl_optimization`

- 错误类型：刀库优化数据错误
- 复现状态：**讲义明示 + 数据存在**（`attested`）
- 验证方法：讲义明示 + 数据存在；置信度 `manual_attestation`
- 讲义证据：not give us a good picture of what is possible with these tools. Note, the Tool Library file which is save with this Project has Optimization values which are incorrect. The steps in this training session will have some specific values for you to set. We encou…
- 核验目标：讲义明确：该工程保存的 Tool Library Optimization values 是错误的
- 实测证据：
  - `{'file': 'optimization_lathe_session_254.tls', 'optimization_nodes': 6, 'stock_cutting_limit_nodes': 6}`
- 说明：能证明「错误数据确实存在」，不能独立算出正确值（讲义用截图给参考值）

#### `mill_session_254fm_optimization`

- 错误类型：刀库优化数据错误
- 复现状态：**讲义明示 + 数据存在**（`attested`）
- 验证方法：讲义明示 + 数据存在；置信度 `manual_attestation`
- 讲义证据：not give us a good picture of what is possible with these tools. Note, the Tool Library file which is save with this Project has Optimization values which are incorrect. The steps in this training session will have some specific values for you to set. We encou…
- 核验目标：讲义明确：该工程保存的 Tool Library Optimization values 是错误的
- 实测证据：
  - `{'file': 'optimization_mill_session_254.tls', 'optimization_nodes': 6, 'stock_cutting_limit_nodes': 6}`
- 说明：能证明「错误数据确实存在」，不能独立算出正确值（讲义用截图给参考值）

### 4.4 VDAF 碰撞/工艺错误（2）

#### `VDAF_programming_training_session`

- 错误类型：VDAF 碰撞/工艺错误
- 复现状态：**讲义明示 + 数据存在**（`attested`）
- 验证方法：讲义明示 + 数据存在；置信度 `manual_attestation`
- 讲义证据：n Controls select Reset Model to scan newly generated NC Program • Display the NC Program window • Select Play You should now see another collision between the Lower Ram and the structure model
- 核验目标：Session 502: Lower Ram 与结构模型碰撞
- 实测证据：
  - project: `VDAF_programming_training_session.vdafproject`
  - machine: `['Brotje_CPAC.xmch']`
  - machine_exists: `True`
- 说明：VDAF 编程工程与 Brotje 机床资产存在；碰撞由讲义明示，未做 VDAF 动态仿真

#### `VDAF_simulation_training_session`

- 错误类型：VDAF 碰撞/工艺错误
- 复现状态：**部分静态复现**（`partial`）
- 验证方法：静态实测 + 讲义明示；置信度 `measured_partial`
- 讲义证据：ect errors • Simulation Controls > Play Note: The message in Message area is indicating why the simulation halted. The simulation stopped at line #27 due to a collision between the riveter head and a temporary fastener put in the previous line • Continue to se…
- 核验目标：Session 501: 第 27 行碰撞；第 108 行 M501 期望首层厚度 7.7，实测 10.0
- 实测证据：
  - rotisserie_nc_line_27: `X9169.318 Y-2285.076 Z2628.501`
  - rotisserie_nc_line_28: `M501`
  - fuselage_skin_thickness_xml: `7.70540783656`
- 说明：NC 行与 7.7 叠层数据已核实；VDAF 模块未做动态仿真，10.0 实测值来自讲义

### 4.5 NC 偏置/配置错误（1）

#### `session_112_setting_up_and_using_basic_debugging_tools`

- 错误类型：NC 偏置/配置错误
- 复现状态：**已复现**（`reproduced`）
- 验证方法：VERICUT 动态仿真；置信度 `measured`
- 讲义证据：Machine and Control Building Session 112 1 Session 112 Setting up and using basic debugging tools This session will introduce you to some of the tools that are available in Vericut to help you troubleshoot (debug) and correct common errors that you might encou…
- 核验目标：Session 112: 仿真在第一个 G54 块停下，Work Offset Register 54 未设置
- 实测证据：
  - `错误:工作偏置未设置: 子系统 = 1, 寄存器 = 54, 子寄存器 = 1`
  - `错误:工作偏置未设置: 子系统 = 1, 寄存器 = 54, 子寄存器 = 1`
  - `错误:工作偏置未设置: 子系统 = 1, 寄存器 = 54, 子寄存器 = 1`
- 原始日志：[session_112.log](vericut_error_case_logs/session_112.log)
- 说明：日志在 240s 截止；第 3 行即出现讲义所述错误，并在第 12/1662 行重复

### 4.6 刀具长度/装夹错误（1）

#### `session_14_MDI_to_validate_part_setup`

- 错误类型：刀具长度/装夹错误
- 复现状态：**已复现**（`reproduced`）
- 验证方法：VERICUT 动态仿真；置信度 `measured_partial`
- 讲义证据：Verification Session 14 2 1. Run the simulation • Play Notice the collisions, this tool is to short for this job but what should the proper length of tool be. We can use MDI to figure out if a Tool will have issues.
- 核验目标：Session 14: 刀具过短，刀柄 Holder1 与 Fixture 碰撞
- 实测证据：
  - `错误:在 103 行:N990X-44.45Y-36.292,组件"Tool"上刀具"2"的刀柄"刀柄"Holder1""与"Fixture"碰撞`
  - `错误:在 104 行:N1000G1Y-11.43,组件"Tool"上刀具"2"的刀柄"刀柄"Holder1""与"Fixture"碰撞`
  - `错误:在 105 行:N1010X-133.302,组件"Tool"上刀具"2"的刀柄"刀柄"Holder1""与"Fixture"碰撞`
- 原始日志：[session_14_console_excerpt.log](vericut_error_case_logs/session_14_console_excerpt.log)
- 说明：日志为 420s 截断的运行片段（已出现碰撞）

### 4.7 碰撞检测演示（1）

#### `detect_collision.mcd`

- 错误类型：碰撞检测演示
- 复现状态：**仅推断**（`inferred`）
- 验证方法：资产用途推断；置信度 `inferred`
- 核验目标：独立碰撞检测演示（资源名/用途）
- 实测证据：
  - file: `detect_collision.mcd`
  - five_axis_comment: `True`
  - rotary_words: `True`
- 说明：没有对应的 .vcproject，未做动态仿真；只按资产用途标注，不冒充实测

## 5. 未能动态复现的部分（诚实边界）

- **VDAF 501**：NC 第 27 行、第 28 行 `M501` 与紧固件叠层 7.7054 已静态核实；VDAF 模块未做动态仿真，碰撞结论来自讲义。
- **VDAF 502**：工程引用 `Brotje_CPAC.xmch` 已核实；Lower Ram 碰撞由讲义明示，未做 VDAF 动态仿真。
- **254FL / 254FM**：刀库中确有 Optimization 与 StockMaterialCuttingLimits 数据，讲义明说这些值错误；正确值以截图给出，无法独立复算，故标 `attested`。
- **detect_collision.mcd**：没有对应 `.vcproject`，只按资产用途标 `inferred`。
- **参考/正常案例**：未重跑 VERICUT，不能宣称「已仿真验证无错」。

## 6. 复跑方法

```powershell
# 1) 生成/更新案例索引（会合并核验报告）
python scripts/index_training_cases.py --root E:/training
python scripts/index_training_cases.py --check

# 2) 重新核验错误案例（先按脚本头部说明跑 VERICUT BATCH）
python scripts/verify_error_cases.py --strict

# 3) 重新生成本报告
python scripts/render_case_analysis_report.py
```

VERICUT 动态复现命令（在 `E:\vericut_verify_work` 可写副本中执行）：

```text
E:\windows64\commands\vericut.bat BATCH batchp <project.vcproject>
```

## 7. Agent 查询方式

```python
agent.call_tool("query_training_cases", {"payload": "哪些错误案例已复现"})
agent.call_tool("query_training_cases", {"status": "error_demo"})
agent.call_tool("query_training_cases", {"verification_status": "reproduced"})
agent.call_tool("query_training_cases", {"capability": "5axis_positioning"})
```
