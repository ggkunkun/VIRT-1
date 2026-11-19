# CIMCO Edit 2026 能力边界声明（诚实性硬约束）

> 本文件是全交付体系的**诚实性基线**。任何交付物中的功能描述都不得越过此基线。
> 依据：官方手册 161 页全量抓取语料 `official_corpus.json`（2026-11-18 实测抓取，42.4 万字符）+
> 本机安装目录实测 + 既有证据链 `knowledge_base/six_software/cimco/evidence.md`。

## 一、绝对不得宣称的能力（官方语料反证）

| 编号 | 用户原诉求中的表述 | 官方事实 | 允许的正确表述 |
|---|---|---|---|
| B-01 | "全维度机床模拟与碰撞检测" | 官方手册 `simulation/machine-simulation/` 原文：*Machine Simulation is an add-on for CIMCO Edit 2026 ... features simply become available once a valid license key has been installed* | 机床仿真是**需单独授权的 add-on**；本机许可状态未核实，按"未验证"处理，不宣称可用 |
| B-02 | "程序差异对比与版本管理" | `version control` 在 161 页语料中 **0 命中**；File Compare 仅有 diff/Goto/Sync。程序与版本管理属 NCBase/MDCMax 产品域 | 仅提供**文件差异对比**能力；版本管理需 NCBase/MDCMax，不属于 Edit 本体 |
| B-03 | "华中数控原生适配" | `Huazhong` 在官方 supported-controls 清单中 **0 命中** | 华中数控只能走 `ISO_G-Code` 通用模板近似适配，需实际机床验证，非官方原生支持 |
| B-04 | "后处理配置与定制开发（通用 CAM 后处理）" | `Post Process` 仅出现在 CNC-Calc 与 Transform 两处；Posts/*.js 为 CNC-Calc 后处理/反向后处理 | CIMCO Edit 的后处理是 **CNC-Calc 后处理与反向后处理**；通用 CAM 后处理在 CAM 软件侧 |
| B-05 | "全图形化 3D 实体建模 / 2D 绘图" | CIMCO Edit 是 NC 编辑器；无几何建模模块 | 2D/3D 建模路由 AutoCAD/NX/SOLIDWORKS |
| B-06 | "自动 20 次人工实操 / 真人计时 120% / 外部盲评 98%" | 属拟人化培训指标，AI 无法产生人工点击记录或外部盲评成绩 | 用**可复跑的工程化等价手段**替代：脚本化验证日志、可复现题库自测、真实 NC 文件验证；报告须标明是"自测/工程验证"而非"人工实操/外部认证" |

## 二、可确认具备的能力（官方语料正面支撑）

- 背绘 Backplot（Ctrl+Shift+P）：刀路可视化、几何/刀具/视图/控制类型配置。`program-tabs/backplot/*`
- 仿真 Simulation（标准版/快速版）、Geometry Manager、Navigation、Variables、Tool Manager。`simulation/*`
- File Compare：逐行差异、Sync、Goto、智能标记。`program-tabs/file-compare/*`
- NC Functions：块号重编、插入/移除、Transform、Scripts、Info。`program-tabs/nc-functions/*`
- NC Assistant：宏、公式、侧边栏、多通道。`program-tabs/nc-assistant/*`
- Transmission / DNC：标准串口协议、FTP 客户端协议、Transmit/Receive。`dnc-setup/*`、`program-tabs/transmission/*`
- Editor Setup：文件类型、颜色、加载保存、机床模型、自定义机床、外部命令、插件。`editor-setup/*`
- 支持的官方控制系统（仿真）：Fanuc / Siemens / Heidenhain / Haas / Mazak / Okuma / Fagor / Brother / Centroid / Mitsubishi / Hurco / Fidia / Flexium / Roeders / Delectron / OSAI / NumeriPath（见 `simulation/supported-controls/*`）
- 本机实装目录：Posts(Mill/Lathe) 30 个 js、Converters 4 个 .conv、Templates 326 个 TPL/TYP、MachineCfg 509 文件、ToolLibs 14 个 .tmlib、Dll 中 30+ ncfilter_*.dll 方言过滤器、官方教程 7 项

## 三、校验器可用性与诚实退路

- `bridges/cimco_bridge.py::validate_fanuc_macro_b` 为**本地静态校验器**（非 CIMCO 内核）：检查 # 变量、WHILE/DO/END 配对、G/M 范围、M02/M30 收尾、M05 停主轴；并调用 `virtu_omni.serving.gbnf_grammar.validate_gcode_syntax` 哨兵。
- 哨兵不可用时该桥接返回 `status=partial` + `CHECK_UNAVAILABLE`，**绝不把"未检查"读作"检查通过"**（既有 bugfix 已固化）。
- 凡报告"校验通过"，必须同时给出 `status` / `syntax_checked` / `errors` 原始字段，不得只写结论。

## 四、G00 碰撞哨兵（项目公理，AGENTS.md §2.E/D）

- 背绘/校验必须检查 G00 快速段不得高速扎入毛坯；落入毛坯即报警。
- 这是**静态几何哨兵**，不等同于机床仿真的真实碰撞检测，二者不得混同表述。
