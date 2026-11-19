# CIMCO Edit 2026 全流程标准化作业程序（SOP）

> 版本 v1.0 / 2026-11-18。适用：ISO G-code / FANUC Macro B 程序从导入到合格输出的完整闭环。
> 本 SOP 的"工程化验证"部分由 `pipeline.py` 实现并连续运行 10 次留日志（见 `logs/`）。

## 0. 适用范围与诚实声明

本 SOP 覆盖 CIMCO Edit 2026 本体的 NC 程序处理闭环。**注意能力边界**（见 `../00_sources/CAPABILITY_BOUNDARIES.md`）：
- S4 的"仿真验证"是**本地静态 G00 扎料哨兵 + 语法校验器**（bridges/cimco_bridge.py），不是机床仿真 add-on 的真实碰撞检测（B-01）。
- CIMCO Edit 无内建版本管理，程序版本追溯需 NCBase/MDCMax（B-02）。
- 全流程耗时指标为工程管线墙钟时间，非真人 GUI 操作计时（B-06）。

## 1. 五阶段标准作业流程

```
[原始NC文件/多格式] 
   → S1 导入与规范化 
   → S2 编辑与校验（Macro B + 语法哨兵）
   → S3 工艺参数配置 
   → S4 仿真验证（静态G00哨兵 + Control Type）
   → S5 合格程序输出（交付件+清单）
```

### S1 导入与规范化
- **入口**：GUI `文件→打开`（选对应 .TYP 机床类型）；或命令行 `CIMCOEdit.exe <file.nc>`；工程管线以 ISO G-code 文本规范化为入口。
- **操作**：
  1. 确认编码（ANSI/UTF-8），中文注释乱码时在 `Editor Setup→文件类型→Load/Save` 调整代码页。
  2. 选择正确 .TYP（FANUC 用 `Fanuc_30i-31i-32i_M.TYP`；SIEMENS 用 Siemens Milling.TYP；未知用 `ISO_G-Code.TYP`）。
  3. 统一换行为 LF、去除 BOM、确认 `%` 起始符与 `O` 程序号。
- **检查点**：程序非空、以 `%` 开头、字节数与 sha16 记录入清单。
- **失败处理**：格式无法识别 → 用 Converters/*.conv 先转换（见 M06）。

### S2 编辑与校验（核心质量门）
- **GUI 路径**：`编辑→Cycle Macro` 展开宏；`检查`相关菜单核对循环配对；Backplot 前先查错。
- **工程校验**：调用 `cimco_bridge.validate_fanuc_macro_b(nc_text)`，逐项核对返回字段：
  - `status` 必须为 `success`（若为 `partial` 表示哨兵未运行，禁止判通过）
  - `syntax_checked` 必须为 `true`（CHECK_UNAVAILABLE 不得当通过）
  - `is_valid` 必须为 `true`
  - `errors` 必须为空（**注意**：桥接器把"主轴未停 M05""G/M 超范围"仅列 error 而 is_valid 仍 true，全流程门必须额外拦截所有 error——这是本 SOP 实测发现的要点）
- **检查项**：#1~#33 局部/#100~#199 公共/#500~#999 系统变量；WHILE[..]DO n 与 END n 配对（n=1/2/3，≤3 层）；G/M 值域 0~999；M02/M30 收尾；M05 停主轴。
- **检查点**：以上全通过才进入 S3；任何 error 立即返回修改。

### S3 工艺参数配置
- 从程序提取并核对：单位（G21 mm / G20 inch）、工件坐标（G54~G59）、长度补偿（G43 Hxx）、主轴（M03/M04 Sxxx）、冷却（M08/M09）、分层数（WHILE 计数）、程序结束（M30）。
- **必填门**：单位=mm、有长度补偿、有主轴、有程序结束，缺一不可。
- **检查点**：宏观工艺参数完整，记录入 manifest。

### S4 仿真验证
- **GUI**：`Backplot`（Ctrl+Shift+P）→ 选 Control Type → 观察刀轨，重点看 G00 快速段。
- **工程哨兵**：`g00_plunge_check()` 提取所有 G00 段的 Z 终点，若低于毛坯顶面-安全间隙即报警（项目公理 §2.E：G00 不得高速扎入毛坯）。
- **Control Type 判定**：含宏变量/WHILE → FANUC(ISO_G-Code)；否则 ISO_G-Code。
- **检查点**：G00 报警数=0；Control Type 已确定。
- **边界**：机床仿真（3D 实体+真实碰撞）为 add-on，本机许可未验证（B-01），本步骤不宣称该能力。

### S5 合格程序输出
- 落盘 `.nc` 交付件（命名含 run 号），生成 manifest：output_file / sha16 / verdict / validate_ref(status,is_valid,syntax_checked) / g00_alerts / control_type。
- **检查点**：manifest 的 verdict=PASS 且所有引用字段为真值，方可交付。

## 2. 工程化验证结果（可复核）

运行命令：
```bash
cd D:\Virtu模型
python cimco_edit_2026_expertise\02_full_workflow\pipeline.py --runs 10
```

| 指标 | 结果 | 证据 |
|---|---|---|
| 连续运行次数 | 10 | 日志 results 数组 |
| 全流程 PASS 次数 | 10/10 | 日志 pass_count |
| 步骤失误 | 0（每次 5 步全 PASS） | 日志 zero_step_fault=true |
| 负面测试拦截 | 4/4（未闭合循环/缺M05/缺M30/G代码越界全部拦截） | 日志 negative_all_blocked=true |
| 平均墙钟/次 | 见日志 avg_wall_seconds_per_run | 工程计时，非真人计时 |
| 诚实声明 | 工程化静态验证，非人工GUI实操/非机床仿真add-on | 日志 honest_note |

日志文件：`logs/workflow_run_*.json`（带时间戳，可复核每一步 status/ms/detail）。

> 说明：首轮运行时负面样本 `bad_gcode=G999` 未被拦截（桥接器合法域 0~999，G999 仍在域内），
> 已修正为 G1005 明确越界后复跑达成 4/4 拦截；此过程保留在版本历史中，体现验证的真实性。

## 3. 人工 GUI 全流程（参考，未做计时宣称）

1. 启动 CIMCOEdit.exe → 打开 NC（选 TYP）
2. 编辑→Cycle Macro 展开；检查循环配对与变量
3. 按需用 NC Functions（块号/Transform）优化
4. Backplot（Ctrl+Shift+P）→ 选 Control Type → Play → 观察 G00
5. File Compare 对比版本差异（如有旧版）
6. Transmission 发送或另存为合格程序
7. 记录 manifest 要素（程序名/校验结论/哨兵结论/时间）
