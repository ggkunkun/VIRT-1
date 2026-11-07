# 斯沃数控仿真 SSCNC 7.2 最快方法证据基准（fastest-methods）

> 生成基准 2026-11-04。证据回溯 `knowledge_base\six_software\sscnc\`（commands/workflows/plugins/automation_api/evidence）与 runbook。禁止臆造实测；时间量级标 [估算]。

## 0. 任务族适用性声明

| 任务族 | 适用性 | 原因 |
| :-- | :-- | :-- |
| 画图 2D drafting | **N/A** | SSCNC 为数控操作仿真器，职责域不含 2D 绘图 |
| 建模 3D modeling | **N/A** | 非建模器；机床几何由 spec.ini（XSIZE/YSIZE/ZSIZE）定义，不在仿真器内建模 |
| 仿真 | ✅ 面板级虚拟加工 | FANUC 0i 面板 AUTO/EDIT/MDI/JOG 全流程仿真 |
| 加工 | ✅ 循环启动验证 | G54 对刀 + Tnnnn 刀补 + cycstart 循环启动 |

---

## 1. 仿真族候选路线全集

### R-sim-1：面板级操作全流程（AUTO/EDIT/MDI/JOG + cycstart）
- 通道类型：GUI/面板（坐标化点击）
- 调用路径：poweron → REF(home.bmp) 回零 → JOG(hnd.bmp) 对刀 → EDIT(edit.bmp) 调入 .cnc → AUTO(auto.bmp) → cycstart.bmp 启动。
- 证据链接：commands.md 面板位图表；runbook §1 任务1-5；workflows.md 闭环。
- 度量：步骤数=6-8（上电/回零/对刀/录补/调入/切 AUTO/启动）；调用数=8+ 面板点击；启动开销=冷启动（CNCLogin→sscnc.exe [估算] 10-30s）；可并行度=低（单 GUI 实例）；证据等级=**documented-not-probed**（面板按键触发本轮未实测，仅官方说明书步骤）；确定性=低（坐标/焦点脆弱）；失败风险=中（误触面板、对刀未对准）。

### R-sim-2：进程拉起 + win32gui 找窗 + 对刀量离线计算（桥接）
- 通道类型：API/混合（桥接）
- 调用路径：`SSCNCBridge.launch()`（CNCLogin.exe）→ `find_window()`（win32gui 标题匹配）→ `calculate_tool_offsets()`（离线算 Tnnnn + R + 象限）。
- 证据链接：automation_api.md 桥接方法签名；evidence E-S05（sscnc_bridge.py）；plugins.md §3。
- 度量：步骤数=3（拉起/找窗/离线算）；调用数=3 API；启动开销=冷启动（CNCLogin [估算]）；可并行度=中（多控制器进程可并发）；证据等级=verified-working [高]（历史桥接实测 launch/find_window）；确定性=高（进程/窗口/纯计算）；失败风险=低。
- **关键边界**：对刀量离线算出后，录入面板仍需人工/坐标化（documented-not-probed），桥接不替代面板按键。

### R-sim-3：多控制器选择（11 厂商）
- 通道类型：进程（按控制器启动 exe）
- 调用路径：CNCLogin → 选控制器 → `FANUC\FANUC0iT\sscnc.exe` / `KND\KND1000T\sscnc.exe` / `MITSUBISHI\M70M\sscnc.exe` / `SINUMERIK\828D.exe` / `Haas\VF\Haas.exe` / `Mazak\QTN100.exe` / `Heidenhain\530.exe` / `HNC\HNC818.exe` / `MORI SEIKI\Mori.exe` / `JNC\JNC30T\sscnc.exe` / `NCT\NCT104T.exe`。
- 证据链接：plugins.md §1.1 控制器库（E-S10）；commands.md。
- 度量：步骤数=2（选/拉起）；调用数=1；启动开销=冷启动；可并行度=中（不同控制器可分别拉起）；证据等级=documented-not-probed（exe 路径已 Glob 核验，未运行）；确定性=中；失败风险=低。

---

## 2. 加工族候选路线全集（对刀 + 循环启动）

### R-mach-1：G54 坐标系对刀 [测量]
- 通道类型：面板
- 调用路径：OFFSET SETTING → [坐标系] → G54 → [测量]：X 按直径测量值、Z 按端面 0.0 录入。
- 证据链接：commands.md 对刀命令；runbook §1 任务2；evidence E-S06 官方说明书。
- 度量：步骤数=4（开补正/选坐标系/选 G54/[测量]录值）；调用数=4 软键；启动开销=温（已开机）；可并行度=低；证据等级=documented-not-probed；确定性=低；失败风险=中（X 误录半径）。

### R-mach-2：刀具形状补正 Tnnnn [形状]
- 通道类型：面板
- 调用路径：OFFSET SETTING → [补正] → [形状] → 选刀补号 Tnnnn；类型 T=3 外圆 / T=2 内孔 / T=8 螺纹。
- 证据链接：commands.md 刀补命令；runbook §1 任务3；evidence E-S06。
- 度量：步骤数=3；调用数=3 软键；启动开销=温；可并行度=低；证据等级=documented-not-probed；确定性=低；失败风险=低（象限选错可改）。

### R-mach-3：循环启动 cycstart + CRT 三页核对
- 通道类型：面板
- 调用路径：切 AUTO(auto.bmp) → CRT 核对 MACHINE/RELATIVE/ABSOLUTE(G54) 三页 → cycstart.bmp 启动。
- 证据链接：commands.md cycstart/CRT 页；AGENTS.md §2.F；runbook §1 任务5。
- 度量：步骤数=4；调用数=4；启动开销=温；可并行度=低；证据等级=documented-not-probed；确定性=低；失败风险=中（未核对坐标直接启动撞刀）。

### R-mach-4：对刀量离线计算（桥接，预生成）
- 通道类型：API/纯计算
- 调用路径：`calculate_tool_offsets(工件直径, 刀具类型)` → 输出 Tnnnn + R + 象限，供面板录入参考。
- 证据链接：automation_api.md calculate_tool_offsets；plugins.md §3。
- 度量：步骤数=1；调用数=1；启动开销=常驻（秒级 [估算]）；可并行度=高（多工件并发算）；证据等级=verified-working [高]（纯计算）；确定性=高；失败风险=低。

---

## 最快结论（sscnc）

| 任务族 | 最快路线 | 次优备选 | 判定依据 | 置信度 |
| :-- | :-- | :-- | :-- | :-- |
| 画图 2D | N/A | — | 职责域不含 2D 绘图 | — |
| 建模 3D | N/A | — | 非建模器，机床几何由 spec.ini 定义 | — |
| 仿真 | **R-sim-2 桥接（launch+find_window+离线算对刀）** | R-sim-3 多控制器选择 | 桥接：3 API、进程/窗口/纯计算确定性=高、verified-working vs 面板 R-sim-1：8+ 步、坐标脆弱、documented-not-probed；面板按键触发未实测，不作最快 | [高]（桥接）/[低]（面板 documented） |
| 加工 | **R-mach-4 对刀量离线计算**（预生成刀补） + **R-mach-2 Tnnnn 形状补正**（录入） | R-mach-1 G54[测量] | 离线算：1 调用、常驻、可并行=高、确定性=高；面板对刀/录补/启动为必走人工步骤但 documented-not-probed，循环启动前必须 CRT 三页核对 | [高]（离线算）/[中]（面板流程） |
