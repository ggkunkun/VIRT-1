# M08 CNC-Calc 与刀具管理 — 标准化操作手册

> 对应模块：CNC-Calc（Editor Setup 配置 + Help 文档）+ Tool Manager（Simulation 域）
> 事实源：`.../editor-setup/file-types/setupfiletypes_cnc_calc/`（D 语料）、`.../simulation/tool-manager/*`（B 语料）、`.../editor-setup/file-types/toollist/`（D 语料）、本机实测 `EVIDENCE.md`
> 诚实性基线：`CAPABILITY_BOUNDARIES.md`（**B-05** 非几何建模；**B-04** 后处理边界；CNC-Calc add-on 许可）

---

## 1. 模块定位与适用边界

**能做什么**：
- **CNC-Calc**：CIMCO Edit 的 2D 计算/编程模块（add-on），支持 2D 铣削/车削程序的图形化编程与计算，配置含 Turning/Diameter programming、小数位、圆弧最大角、样条替代公差、Selected Post Processor（见 M06）、Show grid、Axis substitution 等。来源：`https://docs.cimco.com/en/docs/edit/2026/editor-setup/file-types/setupfiletypes_cnc_calc/`、`.../editor-helpeditor-help/`（CNC-Calc help）。
- **Tool Manager**：创建/编辑刀具，管理刀具库（Tool Libraries）；分三区——当前 NC 程序中的刀具（上）、刀具库（下）、刀具预览（右）；可编辑 Assembly（刀组件）、Cutter（切削件）、Holder（刀柄）。来源：`https://docs.cimco.com/en/docs/edit/2026/simulation/tool-manager/`。

**不能做什么**：
- **B-05**：CNC-Calc 是 2D NC 编程/计算，**不是 3D 实体建模/2D CAD 绘图工具**；几何建模路由 AutoCAD/NX/SOLIDWORKS。
- **B-04**：CNC-Calc 的后处理特指其 Post Processor（见 M06），非通用 CAM 后处理。
- **许可边界**：Plugins 中 CNC-Calc 可用 Disable CNC-Calc 禁用；`CNC-Calc requires an extended license for CIMCO Edit Professional`（`.../editor-setup/plugins/`）。
- Tool Manager 中 STL/Filename 显示**仅用于视觉**，CIMCO Edit 内部碰撞检测仍依赖配置的刀具参数（`.../simulation/tool-manager/edit-cutter/`、`.../edit-holder/`）。

---

## 2. 官方菜单路径与快捷键（逐条附来源）

### 2.1 CNC-Calc 入口（来源：`.../editor-helpeditor-help/`、`.../editor-setup/plugins/`、`.../setupfiletypes_cnc_calc/`）

| 入口 | 功能 | 来源页 |
|---|---|---|
| Help > CNC-Calc help | 打开 CNC-Calc 文档 | `.../editor-helpeditor-help/` |
| Editor Setup > Plugins > Disable CNC-Calc | 启用/禁用 CNC-Calc 模块（需扩展许可） | `.../editor-setup/plugins/` |
| Editor Setup > File Types > CNC-Calc | 配置 CNC-Calc 参数 | `.../setupfiletypes_cnc_calc/` |

> CNC-Calc 的完整绘图/操作菜单官方语料未逐条给出（本批语料仅含配置页与 help 入口），具体绘图命令路径需现场确认。

### 2.2 Tool Manager 入口与操作（来源：`.../simulation/tool-manager/`）

路径：Backplot 选项卡 > Tools 菜单 > Tool Setup（亦可从 Tool 组 Tool Setup 图标）。

| 区域/命令 | 功能 | 来源页 |
|---|---|---|
| Tools in current NC program — Tabs (Assemblies/Cutters/Holders) | 列出当前程序识别的刀组件/切削件/刀柄；单击选中、双击编辑、右键更多 | `.../simulation/tool-manager/` |
| Right-click menu | Edit / Duplicate / Delete / Item id / Item number / Description | 同上 |
| Add Item to Current Document | 在当前程序创建刀组件或单个刀具组件（holder/drill/mill/insert 等） | 同上 |
| Delete Associated Components | 删除 assembly 时一并删除关联 holder/cutter | 同上 |
| Tool Libraries — Libraries | 预定义与自定义刀具库；右键重命名/删除；悬停显示文件系统位置（存于 `/ToolLibs`） | 同上 |
| Copy / Replace | 库与当前刀具表间复制 / 替换（保留原刀号） | 同上 |
| Create Library or Add Item | 新建库或添加刀具项 | 同上 |
| Save Setup | 关闭 Tool Manager → 右键 Geometry Manager > Save Setup，保存刀具配置 | 同上 |

### 2.3 Edit Assembly / Cutter / Holder（来源：`.../tool-manager/edit-assembly/`、`.../edit-cutter/`、`.../edit-holder/`）

| 子功能 | 关键项 | 来源页 |
|---|---|---|
| Edit Assembly — Design tab | 组件嵌套（holder 含 cutter）；Edit/Replace/Remove/Create New Component | `.../edit-assembly/` |
| Edit Assembly — Details tab | Description/ID/Item number、Radius compensation value、Cutter point (Milling: Center/Tip; Turning: T2/T6/T1/T0/T9)、Cutter point shift、Orientation、Add advanced tool location、Mount Filename、Machine View Angle、Color | 同上 |
| Edit Cutter — Design tab | Measurement units、Flute diameter/length、Body length、Shoulder diameter/length、Shaft diameter、Taper length、Corner radius、Chamfer distance | `.../edit-cutter/` |
| Edit Cutter — Details tab | Description/ID/Filename(STL 视觉)/Assembly number | 同上 |
| Edit Holder — Design tab (Milling) | Add/Delete Holder Segment；每段 Upper/Lower/Length（距中心轴等距，如 60mm=左右各 30mm） | `.../edit-holder/` |
| Edit Holder — Design tab (Turning) | 各类型 holder 参数；Gagepoint（Auto/Custom X,Y,Z，仅自定义车床 holder） | 同上 |

---

## 3. 参数配置规则

### 3.1 CNC-Calc 配置参数（来源：`.../setupfiletypes_cnc_calc/`）

| 参数名 | 取值 | 默认值 | 含义 | 来源页 |
|---|---|---|---|---|
| Turning | 开/关 | — | 模拟 2D 车削（Lathe）程序 | `.../setupfiletypes_cnc_calc/` |
| Diameter programming | 开/关 | — | 直径编程 | 同上 |
| Number of decimals | 数字 | — | 坐标等最大小数位 | 同上 |
| Maximum arc output angle | 角度 | — | 生成 NC 中圆弧最大角 | 同上 |
| Spline substitution tolerance | 数值 | — | 样条替代公差 | 同上 |
| Selected Post Processor | Post 列表 | — | 输出格式化的后处理器（见 M06） | 同上 |
| Show grid / Grid size / Show sub-grid / Show origin | 开/关 + 数值 | — | 网格/子网格/原点显示 | 同上 |
| Axis substitution name / tolerance | 字符串 + 数值 | — | 轴替代名称与公差 | 同上 |

### 3.2 Tool List 配置参数（来源：`.../editor-setup/file-types/toollist/`）

| 参数名 | 取值 | 默认值 | 含义 | 来源页 |
|---|---|---|---|---|
| Tool trigger | 字符/串或正则 | — | 识别刀具的触发字符（如 T01 用 T） | `.../toollist/` |
| Advanced configuration template | 开/关 | — | 用高级模板生成 HTML/XML 刀具表 | 同上 |
| $TOOL1/$TOOL2 Trigger | 高级触发（正则） | — | 生成 $TOOL1/2 变量（如 `R<[0-9]+>` 捕获 R33） | 同上 |
| Filter comments with advanced trigger | 正则 | — | 过滤注释行（默认查刀号上方注释） | 同上 |
| Sort tool list / Ignore duplicate info / Ignore 0's | 开/关 | — | 排序去重 / T020202→T02 / T02→T2 | 同上 |
| Two line comments / Scan comments below tool name | 开/关 | — | 两行注释 / 注释在刀号下方 | 同上 |
| Tool list template | 路径 | — | 刀具表模板路径 | 同上 |

> 预装三个刀具表模板，位于 `C:\Users\<user>\AppData\Roaming\CIMCO 2026\CIMCOEdit\SYS`：`Toollist.txt`（简单）、`NewToolList.txt`（高级）、`NewToolListHtmlSample.txt`（HTML 示例）（来源同上）。

### 3.3 本机实装 — 刀具库 `*.tmlib`（实测，来源：`EVIDENCE.md` INS-03 + 本机枚举）

EVIDENCE.md 记 **ToolLibs 14 个 `.tmlib`**；本机实测 `E:\...\CIMCOEdit\ToolLibs\Predefined\` 下 14 个：

| 类别 | 文件（实测） |
|---|---|
| Holders | `Holders.tmlib`、`ISCAR Holders Metric.tmlib`、`Secotools Holders Inch.tmlib`、`Secotools Holders Metric.tmlib` |
| ISO 公制 | `ISO Counter sinks.tmlib`、`ISO Drills.tmlib`、`ISO Mills MM.tmlib`、`ISO Spot drills.tmlib`、`ISO Taps.tmlib` |
| Inch 英制 | `Inch Counter sinks.tmlib`、`Inch Drills.tmlib`、`Inch Mills.tmlib`、`Inch Spot drills.tmlib`、`Inch Taps.tmlib` |

> 刀具库位于安装目录 `/ToolLibs`；Tool Manager 中悬停库名可看文件系统位置（来源：`.../simulation/tool-manager/`）。

---

## 4. 标准操作步骤

### 4.1 配置 CNC-Calc 后处理与显示
1. Editor Setup > File Types > CNC-Calc；检查点：当前 File Type 正确（`.../setupfiletypes_cnc_calc/`）。
2. 勾 Turning/Diameter programming（车削时），设 Number of decimals、Maximum arc output angle、Spline substitution tolerance；检查点：与机床/工艺要求一致（同上）。
3. Selected Post Processor 选目标后处理（见 M06），点 Open 查手册；检查点：输出格式约定已确认（同上、M06）。
4. 设 Show grid/Grid size/Show origin、Axis substitution；检查点：图形显示符合编程习惯（同上）。

### 4.2 用 Tool Manager 编辑刀具并保存
1. Backplot > Tools > Tool Setup 打开 Tool Manager；检查点：三区（当前刀具/库/预览）显示（`.../simulation/tool-manager/`）。
2. 在 Assemblies/Cutters/Holders 选项卡选中项，双击或右键 Edit 进入编辑窗口；检查点：Design/Details 两个 tab 可见（`.../edit-assembly/`）。
3. 编辑 Cutter（Flute/Body/Shoulder/Shaft/Taper/半径倒角）或 Holder（Milling segments 的 Upper/Lower/Length；Turning gagepoint）；检查点：预览随参数高亮并更新（`.../edit-cutter/`、`.../edit-holder/`）。
4. 关闭 Tool Manager → 右键 Geometry Manager > Save Setup；检查点：刀具配置保存到与 NC 同目录的 .setup 文件（**不保存则关闭仿真后改动丢失**）（`.../simulation/tool-manager/`）。

### 4.3 生成刀具表
1. Editor Setup > File Types > Tool List 设 Tool trigger（如 T）、Sort/Ignore 选项；检查点：模板路径正确（`.../toollist/`）。
2. 需要 HTML 时勾 Advanced configuration template 并指向 `NewToolListHtmlSample.txt` 副本；检查点：Tool Trigger 字段非空（HTML 列表也必须填，否则报错）（同上）。
3. NC Functions > Info > Make Tool List；检查点：新文档生成刀具表（HTML 输出在新 tab，可另存 .html 用浏览器查看）（同上、M02）。

---

## 5. 输出标准与判定准则

| 输出 | 判定准则 | 依据 |
|---|---|---|
| CNC-Calc 性质 | 2D NC 编程/计算，**非**几何建模（B-05）；后处理非通用 CAM（B-04） | B-04/B-05 |
| CNC-Calc 许可 | 需扩展许可（Professional），可在 Plugins 禁用 | `.../editor-setup/plugins/` |
| STL 显示 | Filename/STL 仅视觉，碰撞检测仍用配置参数 | `.../edit-cutter/`、`.../edit-holder/` |
| 刀具配置持久化 | 必须 Save Setup，否则关闭仿真后丢失 | `.../simulation/tool-manager/` |
| 刀具库位置 | 安装目录 `/ToolLibs`；本机实测 14 个 .tmlib | `.../simulation/tool-manager/`、EVIDENCE |
| 刀具表模板 | 三个预装模板在 AppData SYS 目录 | `.../toollist/` |

---

## 6. 行业最佳实践 / 常见误区

1. **误区：把 CNC-Calc 当 CAD 建模工具。** 它是 2D NC 编程/计算模块，非 3D 实体/2D 绘图（B-05）。
2. **误区：给刀具配 STL 就等于改了碰撞几何。** 官方明确 STL/Filename 仅视觉，内部碰撞检测仍依赖配置的刀具参数（`.../edit-cutter/`）。
3. **最佳实践：编辑刀具后必存 Setup。** 不保存则关闭背绘/仿真后改动丢失；右键 Geometry Manager > Save Setup（`.../simulation/tool-manager/`）。
4. **最佳实践：删除 assembly 用 Delete Associated Components。** 可一并删除关联 holder/cutter，避免残留（`.../simulation/tool-manager/`）。
5. **最佳实践：HTML 刀具表用示例模板起步。** 复制 `NewToolListHtmlSample.txt`，Tool Trigger 留空会报错，须填任意值（`.../toollist/`）。
6. **最佳实践：半径补偿值来自刀具。** assembly 的 Radius compensation value 取自 cutter（直径偏置取一半直径，否则取半径补偿）（`.../edit-assembly/`）。

---

## 7. 证据溯源表

| 序号 | SOURCE_URL | 用途 |
|---|---|---|
| S1 | `https://docs.cimco.com/en/docs/edit/2026/editor-setup/file-types/setupfiletypes_cnc_calc/` | CNC-Calc 全部配置参数 |
| S2 | `https://docs.cimco.com/en/docs/edit/2026/editor-helpeditor-help/` | CNC-Calc help 入口 |
| S3 | `https://docs.cimco.com/en/docs/edit/2026/editor-setup/plugins/` | CNC-Calc 许可与禁用 |
| S4 | `https://docs.cimco.com/en/docs/edit/2026/simulation/tool-manager/` | Tool Manager 三区、入口、Copy/Replace/Save Setup |
| S5 | `https://docs.cimco.com/en/docs/edit/2026/simulation/tool-manager/edit-assembly/` | Assembly 编辑参数 |
| S6 | `https://docs.cimco.com/en/docs/edit/2026/simulation/tool-manager/edit-cutter/` | Cutter 编辑参数 |
| S7 | `https://docs.cimco.com/en/docs/edit/2026/simulation/tool-manager/edit-holder/` | Holder 编辑参数 |
| S8 | `https://docs.cimco.com/en/docs/edit/2026/editor-setup/file-types/toollist/` | Tool List 配置与模板 |
| S9 | `https://docs.cimco.com/en/docs/edit/2026/program-tabs/nc-functions/info/` | Make Tool List 命令（M02 交叉） |
| S10 | 本地 `EVIDENCE.md` + 本机 `E:\...\CIMCOEdit\ToolLibs\Predefined\` 枚举 | 14 个 .tmlib 实装清单 |
| S11 | 本地 `CAPABILITY_BOUNDARIES.md` | B-04/B-05 边界 |

> CNC-Calc 绘图菜单路径官方语料未明确，需现场确认。
