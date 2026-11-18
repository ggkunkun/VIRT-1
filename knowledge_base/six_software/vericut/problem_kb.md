# VERICUT 9.6 分类问题知识库（Agent 问答路由）

> 扩充文档（2026-11-18）。按用户提问维度分五类：**操作类 / 配置类 / 仿真异常类 / 结果异常类 / 接口对接类**。
> **强制输出流程**：每个问题的回答严格遵循「**现象描述 → 原因定位 → 分步解决 → 结果验证**」四段式，输出必须是可直接执行的操作指引。
> **证据纪律**：答案中的每条关键断言带 E-ID 与三态标注；判死通道给"换通道"解法；无证据不臆造。与 `error_handbook.md`（按错误对象组织）场景 ID 互相引用。

---

## 0. Agent 应答协议（每次问答都执行）

```
0. 归类：把用户问题映射到 5 类之一（见下表路由）
1. 现象描述：复述现象 + 发生阶段（启动/配置/仿真/结果/接口）+ 必要取证项
2. 原因定位：列出可能原因（按概率/证据强度排序），引用 E-ID；跨版本问题转 version_consistency.md
3. 分步解决：编号步骤，一次改一个变量，可回退；引用 SOP/error_handbook 场景
4. 结果验证：给出明确通过标准（校验标准），未过则回到取证
5. 五门自检：版本门/证据门/安全门/许可门/通道门（advanced_scenarios §E）
```

| 类别 | 路由关键词 | 主用文档 |
| :-- | :-- | :-- |
| 操作类 | 怎么点、在哪、快捷键、界面、按钮、导出、保存 | ui_reference.md + commands.md + sop_library.md |
| 配置类 | 参数、默认值、单位、刀具库、机床、控制、坐标系 | ui_reference.md + config.md + advanced_scenarios.md |
| 仿真异常类 | 不播放、卡死、碰撞、报错、无刀路、超程 | error_handbook.md + workflows.md |
| 结果异常类 | Auto-Diff、过切、残料、全绿、体积异常、报告 | error_handbook.md + skill vericut-autodiff-triage |
| 接口对接类 | UG/NX、Mastercam、PowerMILL、接口、导入导出、后处理 | advanced_scenarios.md + file_formats.md |

---

## 1. 操作类（How-to）

### Q-O01「怎么启动 VERICUT 9.6 并自动打开我的工程？」
- **现象描述**：用户需打开指定 `.VcProject`。
- **原因定位**：默认启动加载 `vericut.VcProject`/`vericutm.VcProject` 库文件（E-V14）；要指定工程须设环境变量（E-V06）。
- **分步解决**：
  1. 在 `E:\windows64\commands\vericut_agent.bat`（或副本）中设 `set CGTECH_VCPROJECT=<工程绝对路径>`。
  2. `cmd /c vericut_agent.bat` 启动（非 DETACHED）。
  3. 需要审计则同时设 `CGTECH_TRANSACTION_LOG=Yes`。
- **结果验证**：窗口标题含工程名与 `(毫米)`；事务日志出现动作记录（E-V06 `[高]`）。

### Q-O02「播放按钮在哪？有没有快捷键？」
- **现象描述**：用户找不到播放/想用快捷键。
- **原因定位**：播放是底部播放条绿色三角；9.6 **无 Play 键盘快捷键**（KeyBinding.java 反编译确认，E-V05）。
- **分步解决**：
  1. 1920×1080 全屏下按钮中心 ≈(1890,860)，先截图确认位置。
  2. 鼠标点击；Agent 用 `play_simulation(hwnd)`。
  3. 窗口漂移则重校准坐标。
- **结果验证**：事务日志出现 `ActionMainPlay`、状态灯 BUSY↔READY（E-V02 `[高]`）。

### Q-O03「怎么保存复查文件 / 过程文件？」
- **现象描述**：用户要留存可回放结果。
- **原因定位**：复查 `.vcreview`（Reviewer ZIP）与过程 `.ip` 用途不同（E-V02/E-V14）。
- **分步解决**：
  1. 复查：点 ribbon「保存复查文件」≈(830,108) → 生成 `.vcreview`。
  2. 续跑：File → Save As (In-Process) → `.ip`。
  3. 续跑时命令行 `ip=<file>` 载入。
- **结果验证**：`.vcreview` 可解压（样本 25 条目）；`.ip` 可载入（E-V02 `[高]`）。注意 `.ip` 跨计算机类型不可移植（E-V14）。

### Q-O04「怎么导出 STEP/STL/几何？」
- **现象描述**：用户要导出切削模型。
- **原因定位**：输出面板 Apply 坐标 ≈(1576,451)；历史路径误置 `F:\` 未落盘（E-V02）。
- **分步解决**：选格式（STEP/STL/SOR/VCT）→ 设**可写目录** → 重点 Apply。
- **结果验证**：目标目录出现非空文件（E-V02 `[高]`）。

---

## 2. 配置类（Parameters & Defaults）

### Q-C01「VERICUT 9.6 默认单位是什么？怎么改？」
- **现象描述**：单位/尺寸问题。
- **原因定位**：本机 `CGTECH_DEFAULT_UNITS=MILLIMETER`（E-V01 `[高]`）；英制库为 `vericut.VcProject`，米制为 `vericutm.VcProject`（E-V14）。
- **分步解决**：设 `CGTECH_DEFAULT_UNITS=MILLIMETER`；用 `initm.VcProject` 建工程；确认标题 `(毫米)`。
- **结果验证**：毛坯体积与 CAD 同数量级（E-V02 `[高]`）。

### Q-C02「AUTO-DIFF 的 Gouge/Excess Tolerance 是什么？默认多少？」
- **现象描述**：用户问公差参数。
- **原因定位**：Gouge Tolerance=最大允许过切深度，Excess Tolerance=最大允许残料；Point 比较另有 Check Distance、Default Normal(IJK，示例 `0 0 1`)、Normal Direction(In/Out)；Profile 与 Solid 公差**独立存储**于 `.VcProject`（E-V15 官方原文 `[高]`）。
- **分步解决**：Analysis → AUTO-DIFF → 设 Comparison Type → 按工艺设公差 → Compare。
- **结果验证**：三色判定符合 AGENTS §2.E；**具体默认数值不臆造，以工程/界面当前值为准**。

### Q-C03「`.mch` 和 `.xmch`、` .ctl` 和 `.xctl` 有什么区别？」
- **现象描述**：用户见两种后缀。
- **原因定位**：`.mch/.ctl` 为可编辑 XML；`.xmch/.xctl` 为加密 X-File（内嵌引用文件、禁 Configuration tab、仅 VERICUT 可解密）（E-V14 `[中]`）。
- **分步解决**：需改配置用 `.mch/.ctl`；分发用 `.xmch/.xctl`（改配置先改原件再另存）。
- **结果验证**：`.mch` 下 Configuration tab 可用、`.xmch` 下不可用。

### Q-C04「刀具库怎么建？Tool ID 怎么对应程序？」
- **现象描述**：用户配刀具。
- **原因定位**：`.tls` 为 ASCII，按 Tool ID 存取刀具/刀柄/夹头（E-V14 `[高]`）；程序用 `T0101` 调用（样本，E-V02）。
- **分步解决**：ToolMan → Project → Tools → 按 ID 建刀尖/刀柄/夹头 → Save `.tls` → 主程序 Tooling 引用。
- **结果验证**：日志刀具摘要非空、去除体积 >0（E-V02 `[高]`）。

### Q-C05「什么是 Control 文件？为什么我的 G 代码不被识别？」
- **现象描述**：代码不执行。
- **原因定位**：`.ctl` 描述控制器如何解释 G 代码（可解释列表/格式/分组/宏调用）（E-V14）；不在列表的代码不识别。
- **分步解决**：导出 Control Report `.rpt` 比对 → 在 `.ctl` 补规则 → 复杂逻辑用 `.cme`（CME-API，E-V13 `documented-not-probed`）。
- **结果验证**：Report 显示该代码有对应动作。

---

## 3. 仿真异常类（Runtime Faults）

### Q-R01「点了播放没反应 / 仿真不推进」
→ 完整解法见 `error_handbook.md#E-R01`。四段式摘要：
- **现象**：状态灯不亮、日志不动。
- **原因**：坐标错/窗口非前台/误找快捷键（E-V02/E-V05）。
- **解决**：截图校准 (1890,860) → bring_vericut_front → 鼠标点击 → 查 ActionMainPlay。
- **验证**：BUSY↔READY 交替、日志行号推进（E-V02 `[高]`）。

### Q-R02「仿真报碰撞怎么办？」
→ `error_handbook.md#E-C01`。核心：**回 CAM 修刀路**（抬刀/改进退刀/缩刀柄），不在 VERICUT 里忽略；`is_safe=(collision_count==0)`（E-V02/E-V07 `[高]`）。验证：重跑零碰撞且 Auto-Diff 无红。

### Q-R03「批处理能不能无人值守仿真？」
→ `error_handbook.md#E-S02`。结论：**本机 confirmed-negative**（batchp 待命、batcht 自退，E-V02 `[高]`）；官方 `vcp=/auto-diff=/optimize` 语法存在但本机未复现（E-V14 `[中]`）。解法：走 GUI 播放通道；如坚持 batch 须新会话复测并记录。验证：产出 `.log`/`.rpt`。

### Q-R04「文件找不到 / 移动工程后打不开」
→ `error_handbook.md#E-F01`。按官方查找顺序 ①工程路径 ②Working Directory ③父目录 ④CGTECH_LIBRARY 逐级排查（E-V14 `[中]`）。

---

## 4. 结果异常类（Analysis Faults）

### Q-A01「Auto-Diff 显示 100% 绿色，可信吗？」
- **现象**：截图全绿/无有效像素。
- **原因**：空场（截错窗口、未渲染）——skill `vericut-autodiff-triage` 的"空场不算绿"硬规则。
- **解决**：重截正确窗口、等渲染；运行 triage 脚本校验有效像素非零、三色占比≈100% 且与像素重算一致。
- **验证**：verdict=`AUTODIFF_ACCEPTED` 才放行；空场=INSUFFICIENT_EVIDENCE。

### Q-A02「有红色过切 / 蓝色残料怎么处理？」
- **现象**：Auto-Diff 红/蓝。
- **原因**：过切=致命（刀路切过设计）；残料=留量过多（E-V15 + AGENTS §2.E）。
- **解决**：红→停修刀路/减切深（禁止微调补偿糊弄）；蓝→加半精加工工序。
- **验证**：重跑无红、残料在 Excess Tolerance 内。

### Q-A03「去除体积和毛坯体积差很多」
→ `error_handbook.md#E-A02`。先排碰撞（E-C01）与单位（E-F02）；样本 7.3x 异常=碰撞缺陷信号（E-V02 `[高]`）。

### Q-A04「日志说碰撞但 Auto-Diff 图显示没过切」
→ `error_handbook.md#E-A03`。结论与证据打架→以证据为准 STOP_AND_FIX（skill + E-V15 `[高]`）；先查日志再查图，verdict 非 ACCEPTED 不放行。

---

## 5. 接口对接类（Integration）

### Q-I01「怎么从 UG/NX、Mastercam、PowerMILL 导入刀路/模型？」
- **现象**：用户问某 CAM 对接。
- **原因定位**：9.6 安装自带专用接口 bat（`nx_export.bat`/`mastercam*.bat`/`powermill.bat` 等，存在性 `[高]` E-V04/V12，本机未运行）+ 中性格式兜底路线。
- **分步解决**：
  1. 优先专用接口：从 CAM 环境经对应 bat 启动（需对应 CAD Model Interface 许可，**许可细节不展开**）。
  2. 兜底中性格式：CAM 导出 `.nc`/`.tp` + STEP/STL → VERICUT 按 SOP-2~4 导入（本机已验证资产路径）。
  3. DXF/IGES 用 `dxf2sor`/`iges2v`/`cad2v` 转换。
- **结果验证**：刀路与设计对齐、Syntax Check 通过、无碰撞（advanced_scenarios §D4）。

### Q-I02「后处理和 Control 文件什么关系？怎么匹配？」
→ `advanced_scenarios.md#场景B`。要点：`.VcPost`（把机床无关数据转 G 代码）vs `.ctl`（解释 G 代码）两层含义须分清（E-V14）；匹配校验用 Control Report `.rpt` + G-Code Log 对照。

### Q-I03「多个工序怎么连续仿真？」
→ `advanced_scenarios.md#场景C`。两条路线：`.ops` 装配多 Setup（仅命令行，E-V14 `[中]`）+ `.vct` 已切削实体接力（E-V14 `[高]`）。

---

## 6. 知识库覆盖对照（需求4核对表）

| 用户要求维度 | 本章覆盖 | 输出流程合规 |
| :-- | :-- | :-- |
| 操作类疑问 | §1 Q-O01~O04 | 四段式 ✓ |
| 参数配置问题 | §2 Q-C01~C05 | 四段式 ✓ |
| 仿真异常排查 | §3 Q-R01~R04 | 四段式 ✓ |
| 结果异常定位 | §4 Q-A01~A04 | 四段式 ✓ |
| 接口对接需求 | §5 Q-I01~I03 | 四段式 ✓ |
| 分类清晰 | 5 类路由表 §0 | ✓ |
| 可直接执行的操作指引 | 每问含编号步骤+校验 | ✓ |

> 回答模板（Agent 直接套用）：
> **现象描述**：…（阶段：启动/配置/仿真/结果/接口）
> **原因定位**：…（E-ID + 三态）
> **分步解决**：1)… 2)… 3)…（引用 SOP/场景 ID）
> **结果验证**：…（明确通过标准，未过回到取证）
