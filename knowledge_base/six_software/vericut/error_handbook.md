# VERICUT 9.6 报错·故障处理手册（可直接复用）

> 扩充文档（2026-11-18）。汇总 9.6 常见报错与故障场景：**现象 → 触发场景 → 排查路径 → 标准化解决方案 → 结果验证**。
> **证据纪律**：每个场景带 E-ID 与置信度；本机历史实测复现的标 `[高]（历史实测）`；依官方帮助站/机制推导、本机未复现的标 `[中]（文档化）`，并给出"验证方式"由现场确认。
> **硬规则**：COM/stdin/UIA/headless batch 类"报错"根因是通道判死（confirmed-negative E-V02/E-V03），标准解法是**换通道**而非修参数。

---

## 0. 故障分类导航

| 类别 | 场景 ID 前缀 | 典型入口 |
| :-- | :-- | :-- |
| 启动/通道类 | E-S | COM 报 -2147221005、batch 自退、UIA 读不到控件 |
| 工程/文件类 | E-F | 引用文件找不到、单位错、`.xmch` 改不了 |
| NC/控制类 | E-N | 语法错、G 代码不识别、宏/子程序缺失、乱码 |
| 仿真运行类 | E-R | 不播放、日志不推进、卡死、无刀路 |
| 碰撞/几何类 | E-C | 碰撞报错、过切、残料、模型不水密 |
| 结果/分析类 | E-A | Auto-Diff 空白、三色矛盾、去除体积异常 |
| 导出/接口类 | E-X | geometry 未落盘、`.vcreview` 过大、CAM 接口不通 |

> 与 `problem_kb.md` 关系：本手册按"错误对象"组织，problem_kb 按"用户提问维度"组织，二者场景 ID 互相引用。

---

## 1. 启动 / 通道类故障

### E-S01 COM 自动化创建失败 `-2147221005`
- **现象**：`win32com.client.Dispatch("Vericut.Application")` 等抛异常 `0x800401F3 / -2147221005`。
- **触发场景**：试图用 COM 驱动 VERICUT 9.6。
- **排查路径**：确认 6 个候选 ProgID 全部试过（E-V02）。
- **标准化解决**：判定为 **confirmed-negative**，放弃 COM；改走 `vericut.bat` + GUI 桌面驱动 + 文件回读（SOP-0）。
- **结果验证**：`cmd /c vericut_agent.bat` 能起 GUI 且标题含工程名、事务日志写 `ActionMainPlay`（E-V06）。
- **证据**：E-V02 `[高]（历史实测）`。

### E-S02 批处理（batchp/batcht）无产物 / 自退
- **现象**：`vericut.bat BATCH` 后 `batchp` 仅装载待命、`batcht` 20s 自退零产物。
- **触发场景**：试图无人值守批量仿真。
- **排查路径**：核对官方 batch 语法 `vericut batch vcp=test.VcProject`（E-V14）；比对本机实测（E-V02）。
- **标准化解决**：本机标 **confirmed-negative（不可靠）**；改用 GUI 播放通道。若必须 batch，在新会话用官方 `vcp=/auto-diff=/optimize` 语法复测并记录，不直接采信。
- **结果验证**：至少产出 `.log` 或 `.rpt` 才可判 batch 成功。
- **证据**：E-V02 `[高]（历史实测）` + E-V14 `[中]（官方语法）`。

### E-S03 UIA/JAB 枚举不到菜单/按钮
- **现象**：jabswitch /enable 后 UIA 只暴露 JOGL 视口，Swing/Flamingo 深树不可达。
- **触发场景**：试图用控件树定位播放按钮/读面板值。
- **排查路径**：确认框架为 Swing ActionMap/InputMap + Flamingo JRibbon（E-V05）。
- **标准化解决**：confirmed-negative；改物理像素截图 + 模板匹配 + 文件回读（`#0.3`）。
- **结果验证**：模板匹配命中播放按钮绿色三角。
- **证据**：E-V03/E-V05 `[高]`。

### E-S04 GUI 起不来（DETACHED 启动）
- **现象**：`DETACHED_PROCESS` 启动后无交互窗口站，GUI 不出现。
- **触发场景**：用 Python `subprocess.Popen(..., DETACHED_PROCESS)` 直接起。
- **排查路径**：检查启动方式是否为 `cmd /c vericut_agent.bat`。
- **标准化解决**：用 `cmd /c`（非 DETACHED）；直接 javaw 启动时 VCPROJECT 生效但 TRANSACTION_LOG 不写——事务日志必须走 bat。
- **结果验证**：窗口标题含工程名 + 事务日志产生。
- **证据**：E-V06 `[高]`。

---

## 2. 工程 / 文件类故障

### E-F01 引用文件找不到（File not found）
- **现象**：加载工程报错，某引用文件缺失。
- **触发场景**：工程移动目录、重命名、拷贝给他机。
- **排查路径**：按官方查找顺序逐级核查——①工程内存路径 → ②Working Directory → ③父目录 → ④`CGTECH_LIBRARY`（E-V14）。
- **标准化解决**：把缺失文件放回任一查找路径，或在工程中改引用路径；确保 `CGTECH_LIBRARY` 含 `E:\library\;E:\samples\TLS;E:\samples\Support_files`（E-V01）。
- **结果验证**：工程重新加载不再报缺失。
- **证据**：E-V14 `[中]（官方）` + E-V01 `[高]`。

### E-F02 单位/尺寸数量级错误
- **现象**：毛坯/刀路尺寸差 25.4 倍或数量级异常。
- **触发场景**：英制/米制工程混用。
- **排查路径**：看窗口标题 `(毫米)`/`(inch)`；查 `CGTECH_DEFAULT_UNITS`；查 `.VcProject` units（E-V01/E-V06）。
- **标准化解决**：统一为 `CGTECH_DEFAULT_UNITS=MILLIMETER`，用 `initm.VcProject` 建工程；重新导入几何。
- **结果验证**：毛坯体积与 CAD 理论值同数量级（样本 D53×L45≈99,278mm³）。
- **证据**：E-V02 `[高]（历史实测）` + E-V14 `[中]`。

### E-F03 `.xmch/.xctl` 配置页改不了
- **现象**：打开加密机床/控制文件后 Configuration tab 不可用。
- **触发场景**：加载 X-File（加密压缩件，内嵌所有引用）。
- **排查路径**：确认后缀为 `.xmch/.xctl`。
- **标准化解决**：X-File 设计如此（禁 Configuration tab）；用可编辑的 `.mch/.ctl` 原件改配置后再另存。
- **结果验证**：换 `.mch` 后 Configuration tab 恢复。
- **证据**：E-V14 `[中]（官方原文）`。

### E-F04 NC 程序双字节乱码
- **现象**：NC 程序中非 ASCII 字符显示异常。
- **触发场景**：程序含双字节字符、编码与默认不符。
- **排查路径**：查 `CGTECH_NC_PROGRAM_ENCODING`（bat 注释区）。
- **标准化解决**：设 `CGTECH_NC_PROGRAM_ENCODING=windows-1252` 后重启。
- **结果验证**：显示正常。
- **证据**：E-V01 注释 `[中] documented-not-probed`。

---

## 3. NC / 控制类故障

### E-N01 NC 语法错误
- **现象**：`Perform Syntax Check` 报语法错误。
- **触发场景**：程序格式不符 NC Program Type。
- **排查路径**：确认 NC Program Type（G-Code Data vs APT-CLS）；查 G-Code Log（`.log`）——它逐行给出"输入 G 代码块 → 转换后 APT 记录"对照（E-V14）。
- **标准化解决**：修正程序或改 NC Program Type；敏感代码在 `.ctl` 中补解释规则。
- **结果验证**：Syntax Check 通过；G-Code Log 转换对照正确。
- **证据**：E-V15/E-V14 `[中~高]`。

### E-N02 G 代码/宏不被解释
- **现象**：某 G 代码或宏动作未按预期执行。
- **触发场景**：Control 文件不含该代码的解释规则。
- **排查路径**：导出 Control Report / G-Code Report（`.rpt`），看程序中的代码是否在"可解释列表"及对应宏动作（E-V14）。
- **标准化解决**：在 `.ctl` 增加代码格式/分组/宏调用规则；自定义处理用 `.cme`（CME-API）挂载到 Control Advanced Option（E-V13）。
- **结果验证**：Control Report 显示该代码有对应动作。
- **证据**：E-V13/E-V14 `[中] documented-not-probed`（CME 本机未运行）。

### E-N03 子程序 / 刀具缺失
- **现象**：调用的子程序或刀具找不到。
- **触发场景**：`.sub` 未随主程序、Tool ID 未在 `.tls`。
- **排查路径**：确认子程序内嵌或独立存在；确认 `.tls` 含被调用 T 码。
- **标准化解决**：补 `.sub` 文件到查找路径；在 ToolMan 补刀具。
- **结果验证**：程序跑完无"missing tool/sub"日志。
- **证据**：E-V14 `[中]` + E-V02 `[高]`。

---

## 4. 仿真运行类故障

### E-R01 点播放无反应 / 不仿真
- **现象**：点击播放后状态灯不亮、日志不推进。
- **触发场景**：坐标错、窗口不在前台、无键盘快捷键误用。
- **排查路径**：截图确认播放按钮位置（E-V02）；确认窗口前台（E-V02 §6）；确认无 Play 快捷键（E-V05）。
- **标准化解决**：重校准坐标 → `bring_vericut_front` → 用鼠标点击 → 查事务日志 `ActionMainPlay`。
- **结果验证**：状态灯 BUSY/READY 交替 + 日志行号推进。
- **证据**：E-V02/E-V05/E-V06 `[高]`。

### E-R02 仿真卡死 / 无产物
- **现象**：长时间 BUSY 或不结束。
- **触发场景**：程序过长、模型复杂、宿主抢前台打断。
- **排查路径**：`monitor_log` 看日志是否仍推进；检查是否有第三方程序抢焦点（用户环境事实）。
- **标准化解决**：延长 max_wait；单进程内完成前置+点击+回读；必要时分步仿真（Step）。
- **结果验证**：日志出现完成关键词或得到完整 `.log`。
- **证据**：E-V02 `[高]` + 本机环境事实。

### E-R03 无刀路 / 刀具未切削
- **现象**：播放但毛坯无变化。
- **触发场景**：刀具库未关联、NC 程序未加载、Tool ID 不匹配。
- **排查路径**：查 NC Programs 分支是否已加程序；查 Tooling 是否引用 `.tls`；查程序 T 码。
- **标准化解决**：补齐三要素（程序+控制+刀具）；样本用 FANUC G71/G70（E-V02）。
- **结果验证**：日志刀具摘要非空、去除体积 >0。
- **证据**：E-V02 `[高]`。

---

## 5. 碰撞 / 几何类故障

### E-C01 碰撞报警（collision_count>0）
- **现象**：日志报碰撞（样本 115 条；刀柄 vs Stock/Fixture/Spindle/Turret）。
- **触发场景**：刀路/刀柄/夹具/机床干涉；快移 G00 下刀。
- **排查路径**：`parse_collision_log` 分类（中英双语）；定位碰撞对象（E-V07）；核对 AGENTS §2.D（G00 零高速扎刀哨兵）。
- **标准化解决**：回 CAM 修刀路（抬刀/改进退刀/缩刀柄），**不是**在 VERICUT 里"忽略碰撞"。
- **结果验证**：`is_safe=True`（collision_count==0）；Auto-Diff 无红色过切。
- **证据**：E-V02/E-V07 `[高]` + AGENTS §2.D。

### E-C02 Auto-Diff 红色过切
- **现象**：Auto-Diff 出现红色（gouge）。
- **触发场景**：刀路过切设计模型。
- **排查路径**：读 AUTO-DIFF 报告定位 NC 历史（E-V14）；确认非空白图、三色自洽（skill）。
- **标准化解决**：致命缺陷，停修刀路/减切深；禁止"微调补偿"糊过去。
- **结果验证**：重跑 Auto-Diff 无红色、绿色占比合理。
- **证据**：AGENTS §2.E + E-V15 `[高]` + skill `vericut-autodiff-triage`。

### E-C03 Auto-Diff 蓝色残料
- **现象**：残料超差。
- **触发场景**：精加工留量、刀具半径/步距不当。
- **标准化解决**：加半精加工工序，补充工步后重跑（AGENTS §2.E）。
- **结果验证**：残料在 Excess Tolerance 内。
- **证据**：AGENTS §2.E + E-V15 `[高]`。

### E-C04 模型不水密 / 法向错误
- **现象**：STL 无法作为实体、Auto-Diff 比较异常。
- **触发场景**：STL 非封闭、法向不一致、IGES 有重叠/缝隙。
- **排查路径**：检查 STL 水密性/法向；IGES 导入体跑 Design Consistency Check；`polyfix.bat` 修复多边形。
- **标准化解决**：修复或重导模型；开启 Design Consistency Check（E-V15）。
- **结果验证**：模型可作实体、比较正常。
- **证据**：E-V14/E-V15/E-V12 `[中~高]`。

---

## 6. 结果 / 分析类故障

### E-A01 Auto-Diff 空白 / "全绿"可疑
- **现象**：截图无有效像素却判"100% 合格"。
- **触发场景**：截错窗口、图未渲染、空场。
- **排查路径**：skill `vericut-autodiff-triage` 的"空场不算绿"规则——有效像素=0 → INSUFFICIENT_EVIDENCE。
- **标准化解决**：重截正确窗口、等渲染完成；不得因"没检测到红色"判通过。
- **结果验证**：有效像素非零、三色占比≈100% 且与像素重算一致。
- **证据**：skill `vericut-autodiff-triage` + E-V15 `[高]`。

### E-A02 去除体积数量级异常
- **现象**：去除体积与毛坯理论体积严重不符（样本 7.3x 异常）。
- **触发场景**：碰撞缺陷、单位错、模型错。
- **排查路径**：比对毛坯体积 + 碰撞日志（E-V02）。
- **标准化解决**：先排碰撞（E-C01）与单位（E-F02）。
- **结果验证**：去除体积合理。
- **证据**：E-V02 `[高]（历史实测）`。

### E-A03 结论与证据打架
- **现象**：日志报碰撞而图像判零过切 / 自报 PASS 但有红色像素。
- **触发场景**：视觉分类器与日志不一致。
- **排查路径**：运行 triage 脚本的交叉核对规则（skill）。
- **标准化解决**：以证据为准 → STOP_AND_FIX；先查日志再查图。
- **结果验证**：日志与图像一致、triage verdict=AUTODIFF_ACCEPTED 才放行。
- **证据**：skill `vericut-autodiff-triage` + E-V15 `[高]`。

---

## 7. 导出 / 接口类故障

### E-X01 几何导出未落盘
- **现象**：STEP/STL/SOR 输出指定路径无文件。
- **触发场景**：路径不可写（历史误置 `F:\`）、坐标点错。
- **排查路径**：查输出面板 Apply 坐标 (1576,451)；查路径可写性（E-V02）。
- **标准化解决**：改可写目录、重校准坐标、重点 Apply。
- **结果验证**：目标目录出现非空导出文件。
- **证据**：E-V02 `[高]（历史实测）`。

### E-X02 `.vcreview` 体积过大 / 打不开
- **现象**：复查包很大（样本 227MB）或 Reviewer 打不开。
- **触发场景**：模型精细、包损坏。
- **排查路径**：ZIP 完整性检查；`read_vcreview` 解压条目数（样本 25）。
- **标准化解决**：重新保存复查；确认 Reviewer 9.6（`com.cgtech.VericutReviewer`）打开。
- **结果验证**：ZIP 完整、条目齐全、Reviewer 可回放。
- **证据**：E-V02/E-V12 `[高]`。

### E-X03 CAM 接口不通（UG/Mastercam/PowerMILL 等）
- **现象**:对应 CAM 的 VERICUT 接口启动器无响应/数据未导入。
- **触发场景**：接口 bat 未运行、许可/模型接口缺失、版本不匹配。
- **排查路径**：核对 `commands\` 下接口 bat 存在（`nx_export.bat`/`mastercam*.bat`/`powermill.bat` 等 E-V04/V12）；查 `version_consistency.md`。
- **标准化解决**：从对应接口 bat 启动；确认 CAD Model Interface 许可（**不展开授权机制**）；必要时导出中性格式（STEP/STL/APT-CLS）再导入。
- **结果验证**：NC 程序与模型成功载入 VERICUT。
- **证据**：E-V04/E-V12 `[中] documented-not-probed`（本机未运行各接口）。

---

## 8. 故障→SOP/场景映射速查

| 场景 ID | 主用 SOP | 关联场景文档 |
| :-- | :-- | :-- |
| E-S01~S04 | SOP-0 | automation_api.md |
| E-F01~F04 | SOP-1/2/4 | ui_reference.md §1/§2 |
| E-N01~N03 | SOP-4 | ui_reference.md §1A3 |
| E-R01~R03 | SOP-5 | workflows.md WF-V1 |
| E-C01~C04 | SOP-6 | workflows.md WF-V2 + skill |
| E-A01~A03 | SOP-6 + skill | skill `vericut-autodiff-triage` |
| E-X01~X03 | SOP-5/7 | advanced_scenarios.md（接口） |
