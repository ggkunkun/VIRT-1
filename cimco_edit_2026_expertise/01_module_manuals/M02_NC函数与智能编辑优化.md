# M02 NC 函数与智能编辑优化 — 标准化操作手册

> 对应模块：NC Functions 选项卡 + NC-Assistant 选项卡（Program Tabs）
> 事实源：`docs.cimco.com/en/docs/edit/2026/program-tabs/nc-functions/*` 与 `.../program-tabs/nc-assistant/*`（A 语料）
> 诚实性基线：`CAPABILITY_BOUNDARIES.md`（Scripts 需 Ultra 许可；宏公式结果为计算值，须人工核验——非校验通过证明）

---

## 1. 模块定位与适用边界

**能做什么**：
- **NC Functions**：块号重编（Renumber/Advanced Renumbering/Remove）、范围插入移除（Insert/Remove）、Transform 数学变换（进给/转速调整、简单数学、平移/旋转/镜像/刀补、格式转换）、Info 统计（刀路统计、刀具表、图形）、Scripts 脚本（.ncjs）。来源：`.../program-tabs/nc-functions/`。
- **NC-Assistant**：宏（预定义 + 自定义）插入/修改/查找、宏设置与公式、侧边栏动态参数、Info 提示气泡、多通道同步视图。来源：`.../program-tabs/nc-assistant/`。

**不能做什么**：
- NC Function Scripts 需 **Ultra 许可**；无许可或 Setup 中关闭 advanced NC Functions 时不显示 Scripts 组（`.../nc-functions/scripts/`，职能边界非 B-XX，但为许可硬约束）。
- 脚本运行在受保护进程中，只能读 CIMCO Edit 给它的程序，**不能读文件、用网络、启动其他程序**，也不能运行其他脚本/改设置/运行命令/改其他程序（`.../scripts/`、`.../scripts/writing-scripts/`）。
- 宏公式的结果是**计算值**，官方明确"Always check the results of the formulas carefully"；本手册不把公式输出当作"校验通过"（能力边界第三节）。
- 本模块不做几何建模（**B-05**）、不做通用 CAM 后处理（**B-04**：Transform 内的 Heidenhain/ISO Converter 属方言转换，见 M06）。

---

## 2. 官方菜单路径与快捷键（逐条附来源）

### 2.1 NC Functions > Block Numbers（来源：`.../nc-functions/blocknumbers/`）

| 命令 | 快捷键 | 功能 |
|---|---|---|
| Renumber | Ctrl+T | 插入/重编块号；若 Editor Setup 启用 Show quick setup 则弹快速设置对话框 |
| Advanced Renumbering | — | 复杂重编（Rule groups/Control type/Start/Increment/Skip/TRIGGER/Labels） |
| Remove | — | 删除所有块号 |
| Configure Block Numbering | — | 打开块号配置对话框 |

### 2.2 NC Functions > Insert / Remove（来源：`.../nc-functions/insert-remove/`）

| 命令 | 快捷键 | 功能 |
|---|---|---|
| Mark/Delete Range | Ctrl+M | 指定行/块号范围更新、选择、删除 |
| Insert Block Skips / Remove Block Skips | — | 加/删行首跳转符（字符在 Machine configuration 定义） |
| Insert Spaces / Remove Spaces | — | 命令间插空格 / 删除所有空白与制表符 |
| Remove Empty Lines / Remove Comments | — | 删除空行 / 删除括号或 Comment start/end 定义的注释 |
| Insert Strings / Remove Strings | — | 按位置（行首/行尾/块号后/匹配串前后/新行）插入/移除字符串 |
| Insert Monitoring Macros / Remove Monitoring Macros | — | 在程序启动/F/S/T 命令后插入 DPRNT 行；观测值可经串口读取 |
| Uppercase / Lowercase | Ctrl+U / Ctrl+Shift+U | 转大写/小写（含注释） |
| Auto Insert Spaces | — | "连写"程序自动在每个 NC-word 前插空格 |

### 2.3 NC Functions > Transform / Info / Scripts（来源：`.../nc-functions/transform/`、`.../info/`、`.../scripts/`）

| 命令 | 功能 | 来源页 |
|---|---|---|
| Adjust Feedrate / Adjust spindle speed | 百分比调整进给/转速，含 New feedrate、Decimals、Min/Max、When equal/greater/less than | `.../transform/` |
| Simple math functions | 对所选参数 +/−/×/÷，含 Max/Min/Decimals/Keep decimals/Strip zeros | `.../transform/` |
| Translate / Rotate / Mirror / Tool compensation | 平移(X,Y,Z)、旋转(Point/Angle)、镜像、刀补(G41/G42)；含 Arc type、Assume G91、Reverse tool path | `.../transform/` |
| Heidenhain / ISO Converter | Heidenhain ↔ ISO 互转 | `.../transform/`（详见 M06） |
| Convert NC code | 借 .conv 转换器转换格式；Convert to NCI、Use longhand cycles | `.../transform/`（详见 M06） |
| Toolpath Statistics | 刀路XYZ范围、时间、换刀时间、刀路长、主轴转速 min/max；导出 Standard/CSV；Graph | `.../info/` |
| Make Tool List / Combined Tool List / Configure Tool List | 生成/合并/配置刀具表 | `.../info/` |
| Run script / Script setup / New script... / Stop | .ncjs 脚本运行与配置（Ultra 许可） | `.../scripts/` |

### 2.4 NC-Assistant（来源：`.../nc-assistant/`、`.../nc-assistant/nc-assistant/`、`.../nc-assistant/info/`、`.../nc-assistant/menuncassistantmultichannel/`）

| 命令 | 快捷键 | 功能 | 来源页 |
|---|---|---|---|
| Insert Macro / Modify Macro / Find Macro | — | 插入/修改/查找宏（使用 Macros 菜单 Macro Name 下拉所选宏） | `.../nc-assistant/nc-assistant/` |
| Macro Setup / Record Macro | — | 配置宏 / 从选中 NC 块录制新宏 | `.../nc-assistant/setup/` |
| Hide Sidebar | Ctrl+Shift+A | 显示/隐藏 NC-Assistant 侧栏 | `.../nc-assistant/info/` |
| Hide Balloons | — | 显示/隐藏 NC 代码悬停提示气泡 | `.../nc-assistant/info/` |
| Multi Channel Window / Files / Close | — | 单程序/多文件多通道视图 | `.../nc-assistant/menuncassistantmultichannel/` |
| Next / Previous（多通道同步点） | Ctrl+↓ / Ctrl+↑ | 跳到下一/上一同步点 | 同上 |
| Synchronize Scrolling / Pause Synchronization | — | 锁定所有通道同时滚动 / 暂停自动同步 | 同上 |

---

## 3. 参数配置规则

### 3.1 Advanced Renumbering 参数（来源：`.../nc-functions/blocknumbers/`）

| 参数名 | 取值 | 默认值 | 含义 | 来源页 |
|---|---|---|---|---|
| Rule groups | 可保存的重编设置组 | — | 复用重编方案 | `.../blocknumbers/` |
| Control type | 控制器类型 | — | 不同控制器重编格式不同 | `.../blocknumbers/` |
| Start | 数字 | — | 起始号 | `.../blocknumbers/` |
| Increment | 数字 | 例 Start=0,Inc=5 → 0,5,10 | 增量 | `.../blocknumbers/` |
| Skip lines starting with | 逗号分隔前缀 | — | 跳过以这些前缀开头的行（如 O、%） | `.../blocknumbers/` |
| Skip lines containing | 逗号分隔串 | — | 跳过含这些串的行 | `.../blocknumbers/` |
| Trigger / Labels | 如 G70 / P,Q | — | 触发器与标签，控制精加工循环起止范围重编 | `.../blocknumbers/` |
| Result to new window | 开/关 | — | 结果放到新文档 | `.../blocknumbers/` |

### 3.2 Tools 与 Transform 参数（来源：`.../nc-functions/transform/`、`.../info/`）

| 参数名 | 取值 | 默认值 | 含义 | 来源页 |
|---|---|---|---|---|
| New feedrate / New spindle speed | 百分比 | — | 调整百分比 | `.../transform/` |
| Decimals | 数字 | — | 小数位数 | `.../transform/` |
| Minimum/Maximum value | 数值 | — | 只改 ≥ / ≤ 该值者（进给 mm/min，转速 rev/min） | `.../transform/` |
| Arc type | Auto detect / Relative to start / Relative to end / Absolute arc center | Auto detect | 圆弧解释方式 | `.../transform/` |
| Toolpath unit | Metric (mm)/Imperial (Inches) | — | 刀路单位 | `.../info/` |
| Feedrate unit | Unit/Min / Unit/Rev | — | 进给单位（车削常用 Unit/Rev） | `.../info/` |
| Tool change time / Rapid speed | 数值 | — | 换刀时间/快移速度，用于估算加工时间 | `.../info/` |
| Export format | Standard / CSV | — | 刀路统计导出格式 | `.../info/` |

### 3.3 宏定义语法参数（来源：`.../nc-assistant/setup/dialog/`、`.../setup/formulas/`）

| 符号 | 含义 | 示例/规则 | 来源页 |
|---|---|---|---|
| `$1,$2,...` | User input 用户变量（升序） | 可重复用；Insert 对话框按配置显示 | `.../setup/dialog/` |
| `$UPPERCASE` | System variable 系统变量 | 插入系统数据，只读不可改 | `.../setup/dialog/` |
| `@N{...}` | 公式 | `@3{sqrt($1*$1 + $2*$2)}`；运算符 + − × ÷ %；函数 abs/acos/asin/atan/cos/cosh/floor/ln/log/sign/sin/sinh/sqrt/tan/tanh；PI 函数；角度用度 | `.../setup/formulas/` |
| `#`（行首） | 块号占位 | 插入时替换为正确块号 | `.../setup/dialog/` |
| `##` | 输出字面 `#` | 用于 Fanuc Macro B 变量 | `.../setup/dialog/` |
| `\|`（变量后） | 紧跟字符 | 如 `$2\|100` | `.../setup/dialog/` |
| Prefix / Suffix / Decimals / Digits / Min / Max / Default value | 参数格式与校验 | Digits=4 使 O 号输出 O0007；As specified/Any/0-5 小数规则 | `.../setup/dialog/` |
| Remember value / Allow letters / Uppercase / Hide formula results | 附加选项 | Allow letters 自动加括号且灰化 Min/Max/Decimals/Digits | `.../setup/dialog/` |

> 宏配置存于 `%appdata%\CIMCO 2026\CIMCOEdit\Types\` 下的 .MAC 文件；示例公式文件为 `\Samples\Formulas\formulas.MAC`（来源同上）。

---

## 4. 标准操作步骤

### 4.1 块号重编
1. 备份原件或勾选 Result to new window；检查点：新窗口生成重编副本（`.../blocknumbers/`）。
2. 若 Setup 禁用标准重编，Ctrl+T 直接进入 Advanced Renumbering；检查点：Control type 与程序控制器一致（`.../blocknumbers/`）。
3. 设 Start/Increment，配置 Skip lines starting with（如 O,%）与 G70/P,Q 规则；检查点：精加工循环引用的块号未被破坏（`.../blocknumbers/`）。
4. 执行并检查 status bar 变更行数；检查点：程序逻辑顺序保持（`.../blocknumbers/`）。

### 4.2 插入并修改宏
1. 在 Macros 菜单选 File Type、Macro Group、Macro Name；检查点：侧栏显示对应宏列表（`.../nc-assistant/macros/`）。
2. NC-Assistant > Insert Macro，填写必填参数与可选参数（带 `*`）；检查点：Insert 对话框字段随宏变化（`.../nc-assistant/nc-assistant/`）。
3. 光标置于宏代码上，Modify Macro 更新参数值；检查点：Default 按钮可恢复默认（`.../nc-assistant/nc-assistant/`）。
4. 侧栏 Cycles/Macros 双击插入、Modify 打开修改对话框、Find 查找下一处；检查点：参数修改实时反映到代码（`.../nc-assistant/sidebar/`）。

### 4.3 多通道同步查看
1. Editor Setup > File Types > Multi Channel 先启用 multi channel view 并配置通道起止与同步命令（见 M09）；检查点：NC-Assistant 多通道菜单可用（`.../nc-assistant/menuncassistantmultichannel/`）。
2. Multi Channel > Window（单程序）或 Files（多文件）；检查点：通道并排显示，匹配 Wait codes 黄色、缺失紫色（`.../nc-assistant/menuncassistantmultichannel/`）。
3. Ctrl+↓/↑ 在同步点跳转；Synchronize Scrolling 锁定滚动；检查点：所有通道对齐到同一同步点（`.../nc-assistant/menuncassistantmultichannel/`）。

### 4.4 运行 NC Function Script（Ultra）
1. 确认 Scripts 组可见（Ultra 许可且 advanced NC Functions 开启）；检查点：Run script 菜单列出脚本（`.../scripts/`）。
2. 选 Run script 及目标脚本；无参数脚本立即运行，有参数脚本先弹对话框；检查点：必填项已填、数值范围合规（`.../scripts/`）。
3. 需要保留原件时勾选 Result to new window；需比对时再勾选 Compare with original（后者仅前者勾选时可用）；检查点：脚本结果进入 File Compare（`.../scripts/`）。
4. 查看 status bar：Changes（变更行数/警告数）、No changes、An error（首错命名与行号）、Stop；检查点：出错时"Nothing was changed"（`.../scripts/`）。

---

## 5. 输出标准与判定准则

| 输出 | 判定准则 | 依据 |
|---|---|---|
| 重编结果 | 块号连续符合 Format/Interval；G70 等循环 P/Q 标签范围正确 | `.../blocknumbers/` |
| 公式输出 | Digits/Decimals/Prefix/Suffix 正确；**必须人工核对**，不得当作校验通过 | `.../setup/dialog/` |
| 脚本结果 | status bar 明示变更行数与警告数；出错/停止时程序未变 | `.../scripts/` |
| 脚本自动运行 | 仅对已保存、非只读、非 NC-Base/DNC receive 的程序；每机型的 Run automatically 独立 | `.../scripts/` |
| 刀路统计 | 单位（Metric/Imperial、Unit/Min/Unit/Rev）与导出格式正确 | `.../info/` |
| 多通道 | 匹配 Wait code 黄色、缺失紫色；同步点跳跃正常 | `.../nc-assistant/menuncassistantmultichannel/` |

---

## 6. 行业最佳实践 / 常见误区

1. **误区：脚本可读写外部文件/联网。** 官方明确脚本在受保护进程运行，只能读给定程序（`.../scripts/`）。
2. **误区：公式结果即为校验通过。** 官方要求仔细核对公式结果与格式；本手册不把公式输出记为校验通过（能力边界第三节）。
3. **最佳实践：Fanuc Macro B 的 `#` 用 `##` 转义。** 行首 `#` 默认被解释为块号，输出字面 `#` 须写 `##`（`.../setup/dialog/`）。
4. **最佳实践：盲孔多次深度用 Remember value。** G81 钻 cycle 对 $1/$3/$4 勾 Remember value，仅 $2（模态 Z）留空，重复调用即可改深度（`.../setup/dialog/`）。
5. **误区：脚本无许可也能用。** Scripts 组需 Ultra 许可，且关闭 advanced NC Functions 时隐藏（`.../scripts/`）。
6. **最佳实践：脚本自动运行有严格触发条件。** 可在"打开程序"或"背绘/仿真启动"时运行，上限 60 秒；对只读/未命名/文本机型程序不自动运行（`.../scripts/`）。

---

## 7. 证据溯源表

| 序号 | SOURCE_URL | 用途 |
|---|---|---|
| S1 | `https://docs.cimco.com/en/docs/edit/2026/program-tabs/nc-functions/` | NC Functions 子节 |
| S2 | `https://docs.cimco.com/en/docs/edit/2026/program-tabs/nc-functions/blocknumbers/` | Renumber/Advanced Renumbering 参数 |
| S3 | `https://docs.cimco.com/en/docs/edit/2026/program-tabs/nc-functions/insert-remove/` | Insert/Remove 全部命令 |
| S4 | `https://docs.cimco.com/en/docs/edit/2026/program-tabs/nc-functions/transform/` | Transform 参数与格式转换 |
| S5 | `https://docs.cimco.com/en/docs/edit/2026/program-tabs/nc-functions/info/` | Toolpath Statistics/Tool List |
| S6 | `https://docs.cimco.com/en/docs/edit/2026/program-tabs/nc-functions/scripts/` | 脚本运行/配置/限制 |
| S7 | `https://docs.cimco.com/en/docs/edit/2026/program-tabs/nc-functions/scripts/writing-scripts/` | ES5 约束、info/run、limits、示例脚本 |
| S8 | `https://docs.cimco.com/en/docs/edit/2026/program-tabs/nc-assistant/` | NC-Assistant 概述 |
| S9 | `https://docs.cimco.com/en/docs/edit/2026/program-tabs/nc-assistant/nc-assistant/` | Insert/Modify/Find Macro |
| S10 | `https://docs.cimco.com/en/docs/edit/2026/program-tabs/nc-assistant/macros/` | File Type/Macro Group/Macro Name |
| S11 | `https://docs.cimco.com/en/docs/edit/2026/program-tabs/nc-assistant/setup/dialog/` | 宏定义语法与参数校验 |
| S12 | `https://docs.cimco.com/en/docs/edit/2026/program-tabs/nc-assistant/setup/formulas/` | 公式语法与函数 |
| S13 | `https://docs.cimco.com/en/docs/edit/2026/program-tabs/nc-assistant/sidebar/` | 侧栏动态参数 |
| S14 | `https://docs.cimco.com/en/docs/edit/2026/program-tabs/nc-assistant/info/` | 侧栏/气泡显隐 |
| S15 | `https://docs.cimco.com/en/docs/edit/2026/program-tabs/nc-assistant/menuncassistantmultichannel/` | 多通道命令 |
| S16 | 本地 `CAPABILITY_BOUNDARIES.md` | B-04/B-05 与校验诚实退路 |

> 未在语料中明确的菜单项一律标注"官方语料未明确，需现场确认"。
