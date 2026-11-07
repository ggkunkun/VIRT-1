# VERICUT 9.6 最快方法证据基准（fastest-methods）

> 生成基准 2026-11-04。证据全部回溯 `knowledge_base\six_software\vericut\`（commands/workflows/plugins/automation_api/evidence）与 runbook。禁止臆造实测；时间量级标 [估算]。

## 0. 任务族适用性声明

| 任务族 | 适用性 | 原因 |
| :-- | :-- | :-- |
| 画图 2D drafting | **N/A** | VERICUT 为切削仿真验证软件，职责域不含 2D 绘图（2D 出图在 AutoCAD/NX 侧完成） |
| 建模 3D modeling | **N/A** | 非 CAD 建模器；几何由 CAD 经转换器（dxf2sor/iges2v/cad2v）导入，不在 VERICUT 内建模 |
| 仿真 | ✅ 主职 | 切削过程仿真 + 碰撞/过切检测 |
| 加工 | ✅ 加工验证 | Auto-Diff 红蓝绿判定 + 几何转换器族 |

---

## 1. 仿真族候选路线全集

### R-sim-1：GUI 坐标点击播放（已验证主路线）
- 通道类型：GUI（坐标化点击）
- 调用路径：`vericut_agent.bat` 启动 → 环境变量 `CGTECH_VCPROJECT=<vcproject>` 自动加载工程 → 点击播放按钮 **(1890,860)@1920×1080** → BUSY 状态灯 (710,820) 点亮。
- 证据链接：commands.md 播放命令（1890,860）；runbook §1 任务2；evidence E-V02（ActionMainPlay 事务日志 381 条）；automation_api.md。
- 度量：步骤数=4（启动/加载/点击/核灯）；调用数=1 次坐标点击 + bat 启动 1 条；启动开销=冷启动（javaw 进程 [估算] 20-40s）；可并行度=低（单 GUI 实例）；证据等级=verified-working [高]（历史实测 ActionMainPlay 381 条）；确定性=中（坐标点击对分辨率/焦点敏感）；失败风险=中（误点、窗口失焦；已通过坐标锚定降低）。

### R-sim-2：CGTECH_VCPROJECT 自动加载 + CGTECH_TRANSACTION_LOG=Yes 审计
- 通道类型：批处理/环境变量（与 R-sim-1 组合）
- 调用路径：`set CGTECH_VCPROJECT=<vcproject>` + `set CGTECH_TRANSACTION_LOG=Yes` → `vericut.bat` → 读 `%USERPROFILE%\cgtech_96_transaction.log` 的 `ActionMainPlay`。
- 证据链接：automation_api.md 环境变量节；runbook §0/§2；evidence E-V02。
- 度量：步骤数=3（设变量/启动/读日志）；调用数=2 环境变量 + 1 bat；启动开销=冷启动；可并行度=中（多工程可脚本循环，但单 GUI）；证据等级=verified-working [高]；确定性=高（环境变量/文件级）；失败风险=低。

### R-sim-3：.vcreview 复查包回读（批量复核最快）
- 通道类型：文件级（ZIP 解压）
- 调用路径：ribbon「保存复查文件」(830,108) 产出 `.vcreview` → `vericut_link.read_vcreview()` ZIP 解压回读（NC/STL/ip/日志）。
- 证据链接：commands.md 保存复查；evidence E-V02（.vcreview 227MB、25 条目、Reviewer 9.6 ZIP）；automation_api.md vericut_link。
- 度量：步骤数=2（保存/解压回读）；调用数=1（read_vcreview）；启动开销=常驻（无额外进程，纯文件操作 [估算] 秒级）；可并行度=高（多 .vcreview 可并发解压）；证据等级=verified-working [高]（227MB 实测回读）；确定性=高（文件级）；失败风险=低。

### R-sim-4：batchp/batcht headless 批处理
- 通道类型：批处理
- 调用路径：`vericut.bat BATCH` 透传 / batchp / batcht。
- 证据链接：automation_api.md 批处理节；evidence E-V02；**confirmed-negative**（batchp 仅装载待命、batcht 20 秒自退零产物、CLI 直传 vcp= 判无效参数）。
- 度量：步骤数=2；调用数=1；启动开销=冷启动；可并行度=高（理论）；证据等级=**confirmed-negative [高]**（不可靠，历史实测）；确定性=低；失败风险=高（自退零产物）。
- **结论：不得作为最快路线**——实测不可靠。

### R-sim-5：COM / stdin IPC 自动化
- 通道类型：API
- 调用路径：Python Dispatch COM ProgID / stdin 写命令。
- 证据链接：automation_api.md COM 节；evidence（6 个 ProgID Dispatch 全部判死 -2147221005、stdin 无响应）。
- 度量：步骤数=1（理论）；调用数=1；启动开销=冷启动；证据等级=**confirmed-negative [高]**；失败风险=高（ROT 未注册/判死）。
- **结论：不可用**。

---

## 2. 加工族候选路线全集（Auto-Diff 验证 + 几何转换）

### R-mach-1：Auto-Diff 红蓝绿偏差判定
- 通道类型：GUI/文件（输出面板应用 1576,451）
- 调用路径：仿真完成 → 输出面板应用 (1576,451) → Cut Stock vs 设计 STL 对比 → 颜色公理：红=过切（致命停机修刀路）、蓝=残料（补半精加工）、绿=合格。
- 证据链接：workflows.md Auto-Diff；AGENTS.md §2.E；commands.md 输出面板坐标。
- 度量：步骤数=3（应用/对比/判定）；调用数=1 坐标点击；启动开销=温（仿真已运行）；可并行度=低；证据等级=documented-not-probed（颜色约定 [高]，本轮未现场跑）；确定性=中；失败风险=低。

### R-mach-2：仿真日志数值解析（碰撞/去除体积）
- 通道类型：文件级
- 调用路径：`vericut.parse_sim_log(<log>)` → total_time/errors/warnings/tools/collisions/removal_volumes。
- 证据链接：evidence E-V02（force_turning_sample.log 解析实测：总时间 0:01:10、错误 95、碰撞 115、去除体积 8 项）。
- 度量：步骤数=1；调用数=1；启动开销=常驻（秒级 [估算]）；可并行度=高（多日志并发）；证据等级=verified-working [高]（实测日志）；确定性=高；失败风险=低。

### R-mach-3：几何转换器族（CAD→VERICUT 输入）
- 通道类型：批处理/控制台
- 调用路径：`dxf2sor.bat`(DxfSorConverter) / `iges2v.bat`(Iges2v) / `cad2v.bat`(AcisConv) / `bincl2v.bat`(Bincl2v) / `sur2stk.bat`(Sur2stk) / `polyfix.bat`(PolyFix)。
- 证据链接：plugins.md §3 转换器归类（E-V12）；file_formats.md。
- 度量：步骤数=1-2；调用数=1 bat；启动开销=冷启动（java 控制台 [估算] 秒级）；可并行度=高（多文件并发）；证据等级=documented-not-probed（主类已 Grep 核验，未运行）；确定性=高（文件级）；失败风险=低。

### R-mach-4：ToolMan 定义刀具（.tls）
- 通道类型：插件 GUI
- 调用路径：`toolman.bat`(com.cgtech.toolman.ToolManager) → Tool Manager → Project → Tools → 按 Tool ID 定义 → Save As .tls。
- 证据链接：plugins.md §2.1（E-V12）；file_formats .tls。
- 度量：步骤数=4；调用数=1 插件启动；启动开销=冷启动（独立 javaw [估算]）；可并行度=低；证据等级=documented-not-probed；确定性=中；失败风险=低。

---

## 最快结论（vericut）

| 任务族 | 最快路线 | 次优备选 | 判定依据 | 置信度 |
| :-- | :-- | :-- | :-- | :-- |
| 画图 2D | N/A | — | 职责域不含 2D 绘图 | — |
| 建模 3D | N/A | — | 非 CAD 建模器，几何由 CAD 导入 | — |
| 仿真 | **R-sim-3 .vcreview 回读**（批量复核）+ **R-sim-1 GUI 播放**（首证） | R-sim-2 环境变量启动审计 | vcreview：0 进程、秒级、可并行=高、227MB 实测回读 vs GUI：冷启动 20-40s、坐标脆弱；batch 判死不可用；批量复核走 vcreview/工程自动加载，GUI 播放仅作首证复核 | [高] |
| 加工 | **R-mach-2 日志数值解析**（自动判定碰撞/去除体积） | R-mach-1 Auto-Diff 红蓝绿 | 日志解析：1 调用、常驻、可并行=高、实测 115 碰撞判据 vs Auto-Diff：需 GUI 应用+肉眼判色；转换器/ ToolMan 为准备步骤 | [高]（日志）/[中]（Auto-Diff documented） |
