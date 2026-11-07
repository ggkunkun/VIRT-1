# CIMCO Edit 2026 — 最快方法证据基准

> 知识库根：`D:\Virtu模型\knowledge_base\six_software\cimco\`（README/modules/automation_api/commands/file_formats/workflows/config/plugins/evidence.md）。
> CIMCO 无 COM（confirmed-negative）；自动化通道=外部 Python 桥接 + 命令行拉起。

## 0. 任务族适用性

| 任务族 | CIMCO 适用性 | 说明 |
| :-- | :-- | :-- |
| 画图 2D drafting | **N/A** | CIMCO Edit 2026 为 NC 编辑器/背绘/DNC 工具，职责域不含 2D 绘图 |
| 建模 3D modeling | **N/A** | 同上，无几何建模模块 |
| 仿真 | ⚠️ 仅背绘 backplot 仿真（documented-not-probed） | 非 FEA，仅刀轨可视化+G00 哨兵 |
| 加工 | ✅ | NC 校验/方言转换/后处理/DNC 主职 |

---

## 1. 画图族（N/A）

CIMCO Edit 2026 无 2D 绘图任务域。若用户要求画 2D 图，应路由到 AutoCAD 2026 或 NX Drawing，而非 CIMCO。

## 2. 建模族（N/A）

CIMCO 无 3D 建模模块。若用户要求建几何，应路由到 NX / SOLIDWORKS。

## 3. 仿真族（背绘 backplot）

### R-sim-1：CIMCO GUI 背绘 + G00 哨兵
- 通道类型：GUI
- 调用路径：启动 CIMCOEdit.exe → 打开 .nc → Backplot 标签 → 选机床 .mcfg（DMG MORI.DMC / Hermle / Roeders）→ Play → 观察 G00 段
- 证据：cimco\plugins.md P-CIM-03 Backplot（E-215）；cimco\runbook §1.2
- 度量：步骤数=5[估算]；API 调用数=0；启动开销=冷启动 CIMCOEdit 5~15s [估算]；可并行度=低；证据等级=documented-not-probed；确定性=中；失败风险=低

### R-sim-2：外部 Python 桥接 G00 哨兵（首选）
- 通道类型：API（外部 Python 桥接，无 COM）
- 调用路径：`D:\Virtu模型\bridges\cimco_bridge.py` 解析 .nc → 提取 G00 行 → 与毛坯边界比较 → 输出碰撞判定
- 证据：cimco\automation_api.md（无 COM confirmed-negative）；cimco\runbook §2；AGENTS.md E 公理
- 度量：步骤数=1（跑脚本）；API 调用数=1（脚本内正则+几何比较）；启动开销=常驻（Python 已加载，无 CIMCO 进程）；可并行度=高（多 .nc 并发）；证据等级=verified-working [高]（桥接历史实测）；确定性=高（文件级）；失败风险=低

## 4. 加工族（NC 校验 / 转换 / 后处理 / DNC）

### R-mach-1：外部 Python FANUC Macro B 校验（首选）
- 通道类型：API（外部 Python 桥接）
- 调用路径：`cimco_bridge.py` 检查 #100/#500 变量声明 + WHILE[..]DO n / END n 配对 + G83/G71/G70/M30 闭环
- 证据：cimco\automation_api.md；cimco\runbook §2；AGENTS.md D 公理
- 度量：步骤数=1；API 调用数=1；启动开销=常驻（无 CIMCO 进程）；可并行度=高；证据等级=verified-working [高]；确定性=高；失败风险=低

### R-mach-2：CIMCO GUI Macro B 校验
- 通道类型：GUI
- 调用路径：CIMCOEdit.exe → 打开 .nc → 编辑→Cycle Macro 展开 → 人工检查 WHILE/DO 配对
- 证据：cimco\plugins.md P-CIM-10 CycleMacro（E-223）
- 度量：步骤数=3~5；API 调用数=0；启动开销=冷启动 5~15s [估算]；可并行度=低；证据等级=documented-not-probed；确定性=中；失败风险=低

### R-mach-3：方言转换 Converters .conv
- 通道类型：GUI + 插件
- 调用路径：CIMCOEdit → NC Data → Convert → 选 .conv（fanuc/heidenhain/SinumerikTurning/NumeripathTurning）
- 证据：cimco\plugins.md P-CIM-06 Converters（E-219）
- 度量：步骤数=4；API 调用数=0；启动开销=冷启动 5~15s；可并行度=低；证据等级=documented-not-probed；确定性=中；失败风险=低

### R-mach-4：Posts .js 后处理
- 通道类型：插件（PostProcessor.dll 机制）
- 调用路径：CIMCOEdit → Post Process → 选 Posts\Mill\fanuc.js / haas.js / heidenhain.js / Siemens 840D.js / Fagor 8055i.js / Universal Iso.js；车削 Posts\Lathe\IsoLathe_X_*_Z_*_Processor.js
- 证据：cimco\plugins.md P-CIM-02 Posts（E-214）
- 度量：步骤数=3；API 调用数=0；启动开销=冷启动 5~15s；可并行度=低；证据等级=documented-not-probed；确定性=中；失败风险=低

### R-mach-5：DNC 传输模板 .TPL
- 通道类型：插件
- 调用路径：CIMCOEdit → DNC → 选模板（XMODEM/FANUC-FAPT/LSV2-HH/MAZAK/OKUMA/FTPSERVER/BROTHERQD3/AGIECUT）
- 证据：cimco\plugins.md P-CIM-04 DNC（E-217）
- 度量：步骤数=3；API 调用数=0；启动开销=冷启动 5~15s；可并行度=低；证据等级=documented-not-probed；确定性=中；失败风险=中（串口/网络配置易错）

---

## 最快结论（CIMCO Edit 2026）

| 任务族 | 最快路线 | 次优备选 | 判定依据 | 置信度 |
| :-- | :-- | :-- | :-- | :-- |
| 画图 2D | N/A（路由 AutoCAD/NX） | — | CIMCO 职责域不含 2D 绘图 | [高] |
| 建模 3D | N/A（路由 NX/SOLIDWORKS） | — | CIMCO 无几何建模模块 | [高] |
| 仿真（背绘） | R-sim-2 外部 Python G00 哨兵 | R-sim-1 CIMCO GUI 背绘 | 外部脚本：1 步+常驻+可并行高+verified-working [高]；GUI：5 步+冷启动+单实例 | [高] |
| 加工（NC 校验/转换/后处理/DNC） | R-mach-1 外部 Python Macro B 校验 | R-mach-2 CIMCO GUI CycleMacro | 外部脚本：1 步+常驻+可并行高+verified-working [高]；GUI：3~5 步+冷启动 | [高] |
