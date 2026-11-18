# VERICUT 9.6 标准化操作流程库（SOP）

> 扩充文档（2026-11-18）。把「新建工程 → 参数配置 → 仿真执行 → 异常排查」固化为带**操作节点 / 校验标准 / 注意事项**的可复用步骤卡。
> **证据纪律**：同 `ui_reference.md`——每条标注 `[高]/[中]/[低]` + E-ID，三态判定；文档化但本机未复测的步骤标 `documented-not-probed`。
> **校验标准**分两类：`[实测]`=本机已有证据可核验；`[文档]`=依官方帮助站推导、以现场界面为准。Agent 执行时须如实区分，不得把 `[文档]` 说成已验证。

---

## SOP-0 前置：运行环境与通道选择（每次必读）

| 节点 | 操作 | 校验标准 | 注意事项 |
| :-- | :-- | :-- | :-- |
| 0.1 | 确认安装根 `E:\windows64`、许可证经 `cgtenv.bat` 就位（许可证细节不展开） | `vericut.bat` 存在 `E:\windows64\commands\` | out-of-scope：不碰授权机制（E-V01） |
| 0.2 | 选通道：GUI 桌面驱动（play 坐标点击）为主；`CGTECH_VCPROJECT` 自动加载工程；`CGTECH_TRANSACTION_LOG=Yes` 审计 | `cmd /c vericut_agent.bat` 起 GUI（非 DETACHED） | COM/stdin/UIA/headless batch 全判死，勿重试（E-V02/E-V03，confirmed-negative） |
| 0.3 | 校准屏幕坐标：1920×1080 全屏，截图确认播放按钮 (1890,860)、状态灯 (710,820) | 模板匹配命中绿色三角 | 窗口漂移会使坐标失效，每次原子截图重校准（E-V02/E-V03） |

---

## SOP-1 新建空白项目

| 节点 | 操作 | 校验标准 | 注意事项 |
| :-- | :-- | :-- | :-- |
| 1.1 | `File` 选项卡 → `New Project`（加载 `initm.VcProject` 米制 / `init.VcProject` 英制） | 窗口标题出现 `(毫米)` 且为米制 | `CGTECH_DEFAULT_UNITS=MILLIMETER` 本机默认（E-V01/E-V14） |
| 1.2 | 确认单位：Setup/Project 中 units=MILLIMETER | 标题单位标识正确 | 单位错配会导致尺寸数量级错误（E-V02） |
| 1.3 | 另存为 `.VcProject` 到可写目录 | 文件落盘、非空 | 避免历史误置 `F:\` 未落盘（E-V02） |

## SOP-2 机床 / 控制系统配置

| 节点 | 操作 | 校验标准 | 注意事项 |
| :-- | :-- | :-- | :-- |
| 2.1 | `Machine/Control` 或 `Configuration` → 选/建 Machine（`.mch`）| 默认 3 轴立加加载；组件树可见 | 复杂机床用 `bwizard.bat` 装配向导（E-V09/E-V12） |
| 2.2 | 选/建 Control（`.ctl`），匹配 NC 代码风格 | Control Report `.rpt` 含程序用到的 G 代码/宏 | FANUC Macro B 用对应控制文件（E-V14） |
| 2.3 | 配置组件几何、关联与运动链（进阶）| 组件定位正确、无悬空引用 | `.xmch/.xctl` 加密件禁用 Configuration tab，改配置需用可编辑原件（E-V14） |
| 2.4 | 设 Setup 坐标系（G54 对齐）| 工件原点与编程原点一致 | `documented-not-probed`，以本机工程实测（E-V09） |

## SOP-3 刀具库 / 模型装配

| 节点 | 操作 | 校验标准 | 注意事项 |
| :-- | :-- | :-- | :-- |
| 3.1 | ToolMan → Project → Tools，按 Tool ID 建刀尖/刀柄/夹头，Save `.tls` | 程序中的 T0101/T0202 均有对应刀具 | 缺刀无法切削验证；刀柄参与碰撞检测（E-V02/E-V14） |
| 3.2 | Project Tree → Models → 加 Cut Stock（毛坯）| 体积与上游 CAD 一致（样本 D53×L45≈99,278mm³）| 数量级异常=尺寸/单位错误信号（E-V02） |
| 3.3 | 加 Design 设计件（STL/STEP）| STL 水密、法向一致向外 | IGES 导入体先跑 Design Consistency Check（E-V14/E-V15） |
| 3.4 | 加 Fixture 夹具并定位 | 夹具不与刀路非预期重叠 | 夹具是碰撞检测对象（E-V02） |
| 3.5 | `polyfix.bat` 修复问题多边形（如需）| 修复后模型可正常参与比较 | `documented-not-probed`（E-V12） |

## SOP-4 NC 程序导入与校验

| 节点 | 操作 | 校验标准 | 注意事项 |
| :-- | :-- | :-- | :-- |
| 4.1 | Project Tree → NC Programs → 加程序，设 NC Program Type | G-Code Data 或对应 APT-CLS 变体 | 类型错配导致解释错误（E-V09） |
| 4.2 | 关联 `.ctl` Control、`.tls` 刀具库 | Control Report 覆盖程序代码 | 子程序为 `.sub`（内嵌/独立）（E-V14） |
| 4.3 | `Analysis > Perform Syntax Check` | 无语法错误（这是语法检查，非几何验证）| 官方明确其仅查语法（E-V15） |
| 4.4 | 可选 `NC Program Preview` 看刀路轨迹 | 轨迹与设计模型位置合理 | Preview 无需先处理 NC（E-V15） |
| 4.5 | 双字节乱码时设 `CGTECH_NC_PROGRAM_ENCODING=windows-1252` | 显示正常 | bat 注释项，`documented-not-probed`（E-V01） |

## SOP-5 仿真执行与监控

| 节点 | 操作 | 校验标准 | 注意事项 |
| :-- | :-- | :-- | :-- |
| 5.1 | 前置：bring_vericut_front（宿主抢前台时用）| VERICUT 窗口在前台 | AttachThreadInput 链 + 最小化干扰窗口（E-V02） |
| 5.2 | 点击播放（1890,860）触发 `play_simulation(hwnd)` | 事务日志出现 `ActionMainPlay`；状态灯 BUSY↔READY | 无播放快捷键，只能鼠标点击（E-V05） |
| 5.3 | `monitor_log(interval=5, max_wait=300)` 监控日志推进 | 日志行号持续推进（样本 20→44）| 结束关键词触发回读（E-V02） |
| 5.4 | `parse_sim_log` 回读数值 | 总时间/刀具摘要/去除体积/碰撞数齐全 | 错误计数排除"在NN行"行号干扰（E-V02） |
| 5.5 | `parse_collision_log` 判安全 | `is_safe=(collision_count==0)`；有碰撞→返 CAM 修刀路 | 中英双语分类（E-V07） |

## SOP-6 Auto-Diff 结果分析与报告

| 节点 | 操作 | 校验标准 | 注意事项 |
| :-- | :-- | :-- | :-- |
| 6.1 | 仿真收敛后 `Analysis > AUTO-DIFF` | 图形已渲染、非空白 | 空场=INSUFFICIENT_EVIDENCE，不得判合格（skill `vericut-autodiff-triage`） |
| 6.2 | 设 Comparison Type（Solid/Point/Profile）与公差 | Gouge/Excess Tolerance 明确 | 三色公理：红过切致命 / 蓝残料加半精 / 绿合格（AGENTS §2.E + E-V15） |
| 6.3 | Compare 并读颜色 | 有效像素非零、三色占比自洽 | `Include Tool to Stock Collisions` 纳入刀柄碰毛坯（E-V15） |
| 6.4 | 交叉核对日志与图像 | 日志报碰撞而图像零过切→阻断 | 结论与证据打架时以证据为准（E-V15 + skill） |
| 6.5 | 导出报告 | `.rpt`/`.csv` 落盘 | AUTO-DIFF 报告含错误与 NC 历史，可 CSV 表格打开（E-V14） |

## SOP-7 保存复查 / 过程文件 / 关闭

| 节点 | 操作 | 校验标准 | 注意事项 |
| :-- | :-- | :-- | :-- |
| 7.1 | 点保存复查（830,108）生成 `.vcreview` | ZIP 可解压（样本 25 条目）| 含模型/NC/刀路/视图/日志（E-V02/E-V14） |
| 7.2 | 需要续跑则存 `.ip` | `.ip` 可 `ip=` 载入 | 跨计算机类型不可移植（E-V14） |
| 7.3 | `close_vericut(hwnd, timeout=30)`：`PostMessageW(WM_CLOSE)` | 进程优雅退出 | 不要 taskkill（E-V02/E-V06） |

## SOP-8 异常问题定位（通用排查骨架）

| 节点 | 操作 | 校验标准 | 注意事项 |
| :-- | :-- | :-- | :-- |
| 8.1 | 现象描述：记录错误原文、发生阶段（启动/配置/仿真/结果/接口）| 现象可复述 | 严格遵循 `problem_kb.md` 的"现象-原因-分步解决-验证" |
| 8.2 | 取证：事务日志 + Vericut Log + 截图 + `.vcproject` 静态解析 | 至少两类证据 | 无证据不判因（SCHEMA_CONTRACT §1） |
| 8.3 | 定位：按 `error_handbook.md`/`problem_kb.md` 分类匹配 | 命中已知场景 ID | 跨版本功能先查 `version_consistency.md` |
| 8.4 | 分步解决：一次改一个变量 | 每步可回退 | 判死通道（COM/IPC/UIA/batch）不改，换 GUI+文件回读 |
| 8.5 | 结果验证：重跑最小用例 + 复核校验标准 | 校验标准全部通过 | 未过则回到 8.2，不宣称完成 |

---

## SOP 索引与证据边界

| SOP | 主题 | 本机实测支撑 | 文档化未复测部分 |
| :-- | :-- | :-- | :-- |
| SOP-0 | 环境/通道 | E-V01/V02/V03/V06 | — |
| SOP-1 | 新建工程 | E-V01/V06/V14 | 界面路径 |
| SOP-2 | 机床/控制 | E-V09/V12 | 运动链细项、`.xmch` 行为 |
| SOP-3 | 刀具/模型 | E-V02/V09/V12 | ToolMan 细项、polyfix 运行 |
| SOP-4 | NC 导入 | E-V02/V09/V15 | 编码切换、APT-CLS 变体 |
| SOP-5 | 仿真执行 | E-V02/V06/V07 | — |
| SOP-6 | Auto-Diff | E-V15 + skill | 本机未现场跑 Auto-Diff（图形证据走视觉桥接）|
| SOP-7 | 复查/关闭 | E-V02/V06/V14 | `.ip` 跨机移植未测 |
| SOP-8 | 异常排查 | 全流程证据纪律 | — |
