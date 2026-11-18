# VERICUT 9.6 全模块界面·参数·默认值参考手册

> 扩充文档（2026-11-18）。目标：把 `modules.md`（模块树）与 `commands.md`（命令表）细化到「界面入口 → 操作路径 → 参数含义 → 默认值」四级粒度，覆盖端到端全流程，供 Agent 精准回答 UI 操作与参数问题。
> **证据纪律继承 SCHEMA_CONTRACT §1/§5**：每条关键断言标注 `[高]/[中]/[低]` 并引用 `evidence.md` 的 E-ID；三态 `verified-working / confirmed-negative / documented-not-probed`；禁止无证据断言；严禁触碰许可证/激活机制。
> **版本纪律**：官方在线帮助站 `help.vericut.com` 是跨版本滚动文档（抓取样本中出现 9.7.1 Prefs 命名示例），本手册凡引用官方帮助处一律标注「官方通用文档，经 9.6 本机安装交叉核对」，只有当 **9.6 本机证据（E-V01/V02/V04/V05/V09/V14）** 命中时才标 `[高]`；纯官方、本机未复测项标 `documented-not-probed`、`[中]`。第 5 节给出逐条版本一致性结论。

---

## 0. 界面总览（9.6 主窗口布局）

| 区域 | 位置 | 内容 | 证据 |
| :-- | :-- | :-- | :-- |
| Ribbon 选项卡区 | 窗口顶部 | File / Machine·Control / View / Configuration / Information / Analysis / Tool Manager 等选项卡（Swing + Flamingo JRibbon 框架） | E-V05 `[高]`；选项卡名 E-V09 `[中]` |
| Project Tree（项目树） | 左侧面板 | Control / Setup / NC Programs / Tooling / Models 分支，右键菜单是主要配置入口 | E-V02/E-V09 `[中~高]` |
| 图形视口 | 中央 | JOGL 3D 视口（机床/毛坯/刀具/刀路） | E-V03 `[高]` |
| 状态/信息栏 | 底部 | Vericut Log / Status 面板、Process 状态灯（BUSY/READY） | E-V02 `[高]` |
| 播放条 | 底部 | 播放/暂停/单步/停止/速率滑块；无键盘快捷键 | E-V02/E-V05 `[高]` |

> 关键约束：9.6 的 Swing/Flamingo 深树**不暴露给 UIA/JAB**（E-V03 confirmed-negative），因此 Agent 读取面板状态须走「物理像素截图 + 模板匹配 + 文件回读」，不能依赖控件树。屏幕基准 1920×1080 全屏，坐标会随窗口漂移，每次须原子截图重校准（E-V02/E-V03）。

---

## 1. 领域 A：工程与数据配置（Project Setup & Data）

### A1 工程文件（Project File / `.VcProject`）

| 项 | 内容 | 证据 |
| :-- | :-- | :-- |
| 界面入口 | `File` 选项卡 → `New Project` / `Open` / `Save` / `Save As` | E-V09 `[中]` |
| 操作路径 | 首次启动默认加载 `vericut.VcProject`(英寸)/`vericutm.VcProject`(米制) 库文件；`File > New Project` 加载初始化文件 `init.VcProject`/`initm.VcProject`；`CGTECH_VCPROJECT=<path>` 启动自动加载指定工程 | E-V14 官方通用+9.6 bat 核对 `[高]`；E-V06 `[高]` |
| 参数含义 | `units`=测量单位；`colors`=显示颜色；`choices/data field values`=数据域值；`folder paths & file names`=引用文件路径 | E-V09 `[高]` |
| 默认值 | 本机 `CGTECH_DEFAULT_UNITS=MILLIMETER`（米制）；初始化工程 `initm.VcProject`；单位在窗口标题显示 `(毫米)` | E-V01/E-V06 `[高]` |
| 引用查找顺序 | ①工程内存储路径 → ②Working Directory → ③父目录 → ④`CGTECH_LIBRARY`；全不命中即报错 | E-V14 官方通用 `[中]` |
| 注意 | 项目文件**跨产品不通用**（VERICUT / Composite Simulation / Drill&Fastener 各有各的，不能互用）；`.VcProject` 与 `.usr`（User File）同属会话设置类 | E-V14 `[中]` |

### A2 坐标系 / Setup（G54 对齐）

| 项 | 内容 | 证据 |
| :-- | :-- | :-- |
| 界面入口 | Project Tree → `Setup` 分支右键 → `Configure Coordinate System` | E-V09 `[中]` `documented-not-probed` |
| 操作路径 | 右键 Setup → Configure Coordinate System → 选 CSYS 来源（G54~G59 预设 / 从文件 CSYS from File / 已保存坐标） → Apply | E-V09 `[中]` |
| 参数含义 | 坐标系原点与轴向；`CSYS from File` 读取 APT CL 矩阵集合（CATIA/NX/PTC 语法） | E-V09 `[中]` |
| 默认值 | 机床坐标系原点由 `.mch` 决定；G54 通常为默认工件坐标系 — **`documented-not-probed`，以本机工程实测为准** | — |
| 注意 | Setup 与 Machine 分开配置；多个 Setup 用 Operations 文件（`.ops`）装配连续工序（见 D4） | E-V14 `[中]` |

### A3 NC 程序（NC Programs）

| 项 | 内容 | 证据 |
| :-- | :-- | :-- |
| 界面入口 | Project Tree → `NC Programs` 分支右键 → `Add/Configure NC Program`；Analysis 选项卡 → `Perform Syntax Check` / `NC Program Preview` / `NC Program Review` | E-V09/E-V15 `[高]` |
| 操作路径 | 右键 NC Programs → 指定 NC Program Type（G-Code Data / 各 APT-CLS 变体）→ 选 `.nc/.mcd/.tp/.cl` → 关联 Control 文件 → Apply | E-V02/E-V09 `[中~高]` |
| 参数含义 | NC Program Type 决定解释器；`G-Code Data` 需配 `.ctl`；`APT-CLS` 用 Simple ASCII APT（GOTO/CIRCLE/CYCLE）；子程序走 `.sub`（可内嵌或独立） | E-V09/E-V14 `[高]` |
| 默认值 | 本机样本 46 行 FANUC Macro B（G71/G70/M30），NC Program Type=G-Code Data | E-V02 `[高]`（历史实测样本） |
| 语法校验 | `Analysis > Perform Syntax Check` 检查当前 Setup 引用的所有 NC 程序与子程序语法错误（**不是**几何验证） | E-V15 `[高]` 官方 |
| 注意 | 程序编码异常（双字节乱码）可设 `CGTECH_NC_PROGRAM_ENCODING=windows-1252` | E-V01 注释 `[中]` |

### A4 刀具库与刀具管理器（Tool Manager / `.tls`）

| 项 | 内容 | 证据 |
| :-- | :-- | :-- |
| 界面入口 | 独立程序 `Vericut ToolMan 9.6`（`toolman.bat` → `com.cgtech.toolman.ToolManager`）；主程序 `Configuration` 选项卡 → Tooling；Project Tree → Tooling | E-V11/E-V12 `[高]`；E-V09 `[中]` |
| 操作路径 | Tool Manager → Project → Tools → 按 Tool ID 新建/编辑刀尖、刀柄、夹头 → Save As `.tls` → 回主程序 Tooling 分支引用 | E-V09 `[中]` `documented-not-probed` |
| 参数含义 | `.tls` 为 ASCII，按 Tool ID 存取刀具/刀柄(holder)/夹头；优化属性（OptiPath）随刀具存；`CGTECH_TOOL_LIB_LOCK=FALSE` 可关文件锁（bat 注释） | E-V14/E-V09 `[高/中]` |
| 默认值 | 刀具通过 NC 程序的 `T0101` 等 ID 调用（样本 T0101/T0202）；无刀具则无法切削验证 | E-V02 `[高]` |
| 报告 | Tool Manager → Report 选项卡导出工具报告（`.htm/.txt/.pdf`） | E-V14 `[中]` |

### A5 模型配置（Models：Cut Stock / Design / Fixture）

| 项 | 内容 | 证据 |
| :-- | :-- | :-- |
| 界面入口 | Project Tree → `Models` 分支；`Configure Model` 菜单 → Model 选项卡 | E-V09 `[中]` |
| 操作路径 | 右键 Models → 指定类型（Cut Stock 毛坯 / Design 设计件 / Fixture 夹具）→ 选几何文件 → 定位（Position/Rotate）→ Apply | E-V09 `[中]` |
| 参数含义 | Design Points 检查点支持法向(IJK)/公差/检查距离，随 `.pts` 载入 Model 选项卡；多边形模型后缀 `.dsn/.fix/.stk/.ply` | E-V14 `[中]` |
| 默认值 | 毛坯尺寸来自上游 CAD（样本 D53×L45≈99,278 mm³）；Design 用 STL/STEP；STL 必须水密且法向一致向外 | E-V02/E-V14 `[高/中]` |
| 几何修复 | `polyfix.bat`（`com.cgtech.PolyFix`）修复多边形模型；Design Consistency Check 修补 IGES 导入体的重叠/缝隙 | E-V12/E-V15 `[中/高]` |
| 注意 | `.sor` 在 ZX 平面 2D 轮廓绕 Z 旋转；`.swp` 在 XY 平面轮廓沿 Z 拉伸（`dxf2sor`/`dxf2sweep` 生成） | E-V09/E-V14 `[高]` |

---

## 2. 领域 B：机床与控制系统（Machine & Control）

### B1 机床文件（Machine File / `.mch` / `.xmch`）

| 项 | 内容 | 证据 |
| :-- | :-- | :-- |
| 界面入口 | `Machine/Control` 选项卡 → Machine → `Save As (Machine)`；`Configuration` 选项卡 → Machine | E-V09 `[中]` |
| 操作路径 | 装配向导 `bwizard.bat`(`com.cgtech.BWizard`) 或手工建组件树 → 定义 Component/ associations → 设运动链 → Save `.mch` | E-V12 `[中]` `documented-not-probed` |
| 参数含义 | `.mch` 为 XML，描述机床构造、运动学(kinematics)与属性；`.xmch` 为加密 X-File，内嵌所有引用模型并**禁用 Configuration tab** | E-V14 `[中]` |
| 默认值 | 本机默认 3 轴立加；`CGTECH_MACHINE_CONFIG=FALSE` 可隐藏机床配置菜单（bat 注释，实测未复测） | E-V09/E-V01 `[中]` |
| 资产 | 机床/组件资源库 `E:\windows64\resources\VTPD.db` | E-V01 `[高]` |

### B2 控制系统（Control File / `.ctl` / `.xctl`）

| 项 | 内容 | 证据 |
| :-- | :-- | :-- |
| 界面入口 | `Machine/Control` → Control；`Configuration` → Control | E-V09 `[中]` |
| 操作路径 | 选控制库文件或新建 → 定义可解释 G 代码表/格式/分组/宏调用 → Advanced Option 挂 CME/API → Save `.ctl` | E-V09/E-V13 `[中]` |
| 参数含义 | `.ctl` 为 XML，描述 NC control 如何处理 G 代码；`.xctl` 为加密 X-File（内嵌子程序、禁 Configuration tab）；FANUC 0i 用对应控制文件 | E-V14 `[中]` |
| 默认值 | 控制解释规则表由所选控制文件决定；Control Report（`.rpt`）可导出"当前控制如何解释各代码"用于核对 | E-V14 `[中]` |
| 校验 | `Analysis > Control/G-Code Report` 导出 `.rpt`，列出程序中的 G 代码、宏动作、变量、刀具、子程序 | E-V14 `[中]` |

### B3 机床运动逻辑与组件（进阶见 `advanced_scenarios.md`）

组件树、关联（associations）、运动链、机床初始化文件（Machine Initialization File）等自定义逻辑在高级手册展开。

---

## 3. 领域 C：仿真执行（Simulation Playback）

### C1 播放 / 步进 / 速率

| 项 | 内容 | 证据 |
| :-- | :-- | :-- |
| 界面入口 | 底部播放条（Play ▶ / Pause / Step / Stop / 速率滑块） | E-V02 `[高]` |
| 操作路径 | 鼠标点击绿色播放三角（物理像素 1920×1080 下中心 ≈(1890,860)，须每次截图校准）；Step 单步；速率滑块调节 | E-V02 `[高]` |
| 参数含义 | 播放 = 按 NC 程序逐段驱动机床运动并切削毛坯；单步 = 逐段执行便于定位问题 | E-V02 `[高]` |
| 默认值 | **无键盘快捷键**（KeyBinding.java javap 反编译确认无 Play 绑定） | E-V05 `[高]` |
| Agent 通道 | `play_simulation(hwnd)` → 校验事务日志出现 `ActionMainPlay`；状态灯 (710,820) BUSY/READY 交替 | E-V02/E-V06 `[高]` |

### C2 状态与信息面板

| 项 | 内容 | 证据 |
| :-- | :-- | :-- |
| 界面入口 | `Information` 选项卡 → Vericut Log / Status；底部状态灯 | E-V09/E-V02 `[中/高]` |
| 参数含义 | Status 文件（`.txt`）由 `CGTECH_STATUS` 指定，仿真时写入 Status 面板数据，模型 reset 时覆盖 | E-V14 `[中]` |
| 默认值 | 日志含 NC 程序名/错误/警告/加工时间；本机样本错误 95 / 警告 0 / 碰撞 115 | E-V02 `[高]`（历史实测） |

---

## 4. 领域 D：分析与验证（Analysis & Verification）

> Analysis 选项卡官方定义（E-V15）：包含仿真过程对比与 NC 程序数据检查功能；Model 组、Toolpath 组、AUTO-DIFF 等。`help.vericut.com/4_vericut_help/7.0_analysis_tab`。

### D1 AUTO-DIFF 自动偏差对比

| 项 | 内容 | 证据 |
| :-- | :-- | :-- |
| 界面入口 | `Analysis` 选项卡 → `AUTO-DIFF`（工具栏快捷按钮） | E-V15 `[高]` 官方 |
| 操作路径 | 载入 Design 模型 → 设 Comparison Type（Solid/Surface/Point/Profile）→ 设 Gouge/Excess 公差 → Compare → 查看颜色 → 可选导出 `.rpt/.csv` | E-V15 `[高]` |
| 参数含义 | **Gouge Tolerance**=允许最大过切深度；**Excess Tolerance**=允许最大残料；Point 比较另有 Gouge/Excess Check Distance、Default Normal(IJK)、Normal Direction(In/Out)；Profile 比较 Gouge/Excess 与 Solid **互相独立**，分别存于 `.VcProject` | E-V15 `[高]` 官方原文 |
| 默认值 | Point 默认法向示例 `0 0 1`；Comparison Type=Both 时若同时有过切+残料**优先报过切**；具体公差数值随工程，**不臆造默认值** | E-V15 `[高]` |
| 显示开关 | AUTO-DIFF Results / Design(Translucent\|Solid) / Stock / Fixture / `Include Tool to Stock Collisions`（含刀柄非切削部碰毛坯） | E-V15 `[高]` |
| 一致性检查 | `Design Consistency Check`：Solid 比较时检查封闭体、修补修剪面、重建缺失面（推荐用于 IGES 导入模型）；`Keep Design Solid` 保留设计实体供多次比较 | E-V15 `[高]` |
| 判定公理 | **红=过切(致命停修) / 蓝=残料(加半精) / 绿=合格**（对齐 AGENTS.md §2.E；空场=证据不足不得判合格，见 skill `vericut-autodiff-triage`） | AGENTS §2.E + E-V15 `[高]` |

### D2 OptiPath 进给优化 / Force 切削力

| 项 | 内容 | 证据 |
| :-- | :-- | :-- |
| 界面入口 | `Optimize/OptiPath` 选项卡 → OptiPath / Optimize Control；Force 在 Analysis/Configure 中（依工程） | E-V09/E-V14 `[中]` |
| 操作路径 | 建优化库 `.olb`（按刀具/材料/机床定义进给）→ Optimize Control 设 Material/Machine/库文件 → 开启优化 → 输出 `.opti/.mco`(G代码)/`.tpo`(APT) | E-V14 `[中]` |
| 参数含义 | `.olb`=ASCII 优化数据；`CGTECH_OPAPI=<DLL>` 外挂自定义优化（此时内置优化停用） | E-V13/E-V14 `[中]` |
| 默认值 | 不开启优化则按原 NC 进给；Force 材料库 `E:\force_materials` | E-V01 `[高]` |
| 证据纪律 | 本机未运行 OptiPath/Force → `documented-not-probed` | E-V04/E-V13 `[中]` |

### D3 X-Caliper / Comparator / Inspection

| 项 | 内容 | 证据 |
| :-- | :-- | :-- |
| 界面入口 | `Analysis` → X-Caliper / Comparator；`View` 选项卡 → Orient/测量；Inspection（`.VcInspect`） | E-V15/E-V09 `[中]` |
| 操作路径 | X-Caliper 测量点/距离/角度辅助定位误差源；Comparator 载入 2D DXF 叠加到 Stock/Cut Stock 或叠栅格模拟光学比较仪 | E-V15 `[高]` 官方 |
| 参数含义 | Inspection Sequence（`.VcInspect`）=XML，保存单次检验报告的数据表与工件上的检验标记 | E-V14 `[中]` |
| 默认值 | —（依测量对象） | — |

### D4 多工序 / Operations 文件（`.ops`）

| 项 | 内容 | 证据 |
| :-- | :-- | :-- |
| 界面入口 | 无独立选项卡，从**命令行**启动装配多 Setup 工程 | E-V14 `[中]` |
| 操作路径 | 写 `.ops` 文本（每行引用一个 `.VcProject`，声明从上一个工程传递的信息）→ 命令行运行 Vericut 载入 → 连续仿真多 Setup | E-V14 `[中]` |
| 参数含义 | `.ops`/`.vctmp`（临时）=人类可读文本，每行独立引用一个工程文件 | E-V14 `[中]` |
| 默认值 | 通常用 `.ops` 后缀；只能从命令行启动 | E-V14 `[中]` |

---

## 5. 领域 E：复查与导出（Review & Export）

### E1 保存复查文件（`.vcreview`）

| 项 | 内容 | 证据 |
| :-- | :-- | :-- |
| 界面入口 | Ribbon「保存复查文件」按钮（物理像素 ≈(830,108)，须校准） | E-V02 `[高]` |
| 操作路径 | 仿真后点击保存 → 生成 `.vcreview`（Reviewer 9.6 ZIP 容器）→ Reviewer 打开回放 | E-V02 `[高]` |
| 参数含义 | Review File 含重建仿真所需的全部信息：机床/Cut Stock/刀具模型、NC 程序、刀路数据、原始视图设置、日志副本 | E-V14 `[中]` |
| 默认值 | 本机实测 227MB / 25 条目（NC/STL/ip/日志） | E-V02 `[高]`（历史实测） |

### E2 过程文件（In-Process / `.ip`）

| 项 | 内容 | 证据 |
| :-- | :-- | :-- |
| 界面入口 | `File` → Save As (In-Process)；命令行 `ip=<file>` | E-V09 `[中]` |
| 操作路径 | 仿真中/后保存 `.ip`（含已切削模型+UI设置+日志副本）→ 下次 `ip=` 载入免重跑 | E-V09/E-V14 `[中]` |
| 参数含义 | IP 文件部分 ASCII 部分二进制；跨计算机类型不可移植（数学处理差异）；`SAVE_IP` 命令记录；`CGTECH_COMPRESS=IP` 控压缩 | E-V14 `[高]` |
| 默认值 | 默认压缩保存；`CGTECH_COMPRESS=NO/IP/VCT/ALL` | E-V01/E-V14 `[中]` |

### E3 几何 / 报告导出

| 项 | 内容 | 证据 |
| :-- | :-- | :-- |
| 界面入口 | 输出面板 → 应用（物理像素 ≈(1576,451)，须校准）；AUTO-DIFF → Report（`.rpt/.csv`）；Tool Manager → Report | E-V02/E-V14 `[中~高]` |
| 操作路径 | 选导出格式（STEP/STL/SOR/VCT）→ 设路径 → Apply；历史路径误置 `F:\` 需改可写目录 | E-V02 `[高]` |
| 参数含义 | `.vct`=已切削毛坯实体（可复用为毛坯/夹具/Design/Constant Gouge Check 设计模型）；AUTO-DIFF 报告可 CSV 用表格打开 | E-V14 `[高]` |
| 默认值 | VCT 默认压缩保存 | E-V14 `[高]` |

---

## 6. 端到端功能点覆盖矩阵（需求1核对表）

| 用户要求的功能点 | 本章节 | 界面入口 | 操作路径 | 参数含义 | 默认值/约束 | 覆盖 |
| :-- | :-- | :-- | :-- | :-- | :-- | :-- |
| 项目初始化与基础配置 | §1 A1/A2 | ✓ | ✓ | ✓ | ✓ | 完整 |
| 机床三维模型搭建与运动链配置 | §2 B1/B3 + advanced_scenarios | ✓ | ✓ | ✓ | ✓ | 完整（运动链详见高级手册） |
| 刀具库创建与参数化管理 | §1 A4 | ✓ | ✓ | ✓ | ✓ | 完整 |
| 数控程序导入与语法校验 | §1 A3 | ✓ | ✓ | ✓ | ✓ | 完整 |
| 实时碰撞检测与超程预警 | §4 D1(Include Tool to Stock Collisions) + §3 C2 + error_handbook | ✓ | ✓ | ✓ | ✓ | 完整（判死/日志回读见 workflows） |
| 仿真过程运行控制 | §3 C1/C2 | ✓ | ✓ | ✓ | ✓ | 完整 |
| 加工结果分析与检测报告自动生成 | §4 D1~D4 + §5 E3 | ✓ | ✓ | ✓ | ✓ | 完整 |

---

## 7. 版本一致性小结（详见 `version_consistency.md`）

- 本手册的**界面骨架**（Ribbon 选项卡名、Project Tree 分支、Analysis 组按钮）来自官方帮助站（滚动文档）与 9.6 本机安装 bat/反编译/实测交叉核对；标 `[高]` 项均有 9.6 本机证据。
- **官方帮助站为跨版本文档**：抓取样本出现 9.7.1 Prefs 命名示例，本手册未采信任何 9.7.x 专属功能；凡本机未复测的官方项一律 `documented-not-probed`、`[中]`，并明确"以 9.6 界面当前值为准"。
- **默认值一栏不臆造**：仅填入有本机证据（E-V01/V02/V06）或官方原文（E-V14/E-V15）支撑的值；其余标注"依工程/以界面为准"。

> 本文件为 `modules.md`/`commands.md` 的细化扩充，与之冲突时以 evidence.md 中更高置信度/更近证据为准，并回写修正。
