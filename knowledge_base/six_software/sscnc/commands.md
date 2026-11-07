# SSCNC 7.2 命令表（面板按钮 / 模式 / 软键 / API）

> 类型枚举：面板按钮（位图名）/ 模式 / 软键 / API(python 桥) / 命令行。
> 面板操作路径 = FANUC 0i 仿真面板（CRT + 实体按键）；对刀步骤引用斯沃官方说明书（E-S06）。

| 命令 ID | 模块 | 类型 | 参数 / 按键 | 说明 | 证据 |
| :-- | :-- | :-- | :-- | :-- | :-- |
| SS-01 | 登录 | 命令行 | `Popen([CNCLogin.exe], cwd=安装目录)` | 启动登录器，进面板前的入口 | E-S05 verified-working（历史桥接） |
| SS-02 | 机床选择 | 面板 | 登录器中选控制器厂商 + 机床型号（如 FANUC0iT/ShenYangTD） | 每型号对应目录下一个 exe（ShenYangTC/EMCO/Hardinge…） | E-S02 Glob documented-not-probed |
| SS-03 | AUTO 模式 | 面板按钮 | `auto.bmp` | 自动循环加工模式 | E-S03 位图存在 |
| SS-04 | EDIT 模式 | 面板按钮 | `edit.bmp` | 程序编辑/调入 Oxxxx | E-S03 |
| SS-05 | MDI 模式 | 面板按钮 | `mdi.bmp` | 手动数据输入单段指令 | E-S03 |
| SS-06 | JOG 手动 | 面板按钮 | `hnd.bmp` | 手动/手摇进给 | E-S03 |
| SS-07 | 回零 REF | 面板按钮 | `home.bmp` | 回参考点（开机首步） | E-S03 |
| SS-08 | 增量进给 INC | 面板按钮 | `inc.bmp` | 单步增量 | E-S03 |
| SS-09 | 循环启动 | 面板按钮 | `cycstart.bmp`（绿灯） | Cycle Start；启动前必须核对 CRT 坐标 | E-S03 + AGENTS §2.F |
| SS-10 | 循环停止 | 面板按钮 | `cycstop.bmp` / `stop.bmp` | Feed Hold | E-S03 |
| SS-11 | 空运行 | 面板按钮 | `dry.bmp` | DRY RUN 校验（不切削） | E-S03 |
| SS-12 | 单段 | 面板按钮 | `sbk.bmp` | SINGLE BLOCK 逐段 | E-S03 |
| SS-13 | 可选停 | 面板按钮 | `opt.bmp` | M01 生效 | E-S03 |
| SS-14 | 跳段 | 面板按钮 | `skip.bmp` | "/" 程序段跳过 | E-S03 |
| SS-15 | 机床锁定 | 面板按钮 | `zlock.bmp` / `MLock.bmp` | 坐标走刀不动实体（验证程序用） | E-S03 |
| SS-16 | 进给倍率 | 面板按钮 | `hfeed.bmp` / `vfeed.bmp` | FEED OVERRIDE | E-S03 |
| SS-17 | 主轴倍率 | 面板按钮 | `spup.bmp` / `spdown.bmp` / `sp100.bmp` | SPINDLE OVERRIDE | E-S03 |
| SS-18 | G54 对刀 | 软键 | OFFSET SETTING → [坐标系] → G54 番号 → 输 X0/Y0/Z0 → [测量] | 试切对刀：镗/铣 G54 原点；官方步骤见 E-S06 | E-S06 documented-not-probed |
| SS-19 | 刀具形状补正 | 软键 | OFFSET → [补正] → [形状] → 输入直径/X/Z → [测量] | 车刀：试切外圆→测直径→X=(直径值)；端面→Z0；输出 Tnnnn 几何补正 | E-S06 + E-S05 |
| SS-20 | 刀具磨耗补正 | 软键 | [补正] → [磨耗] | 微量补偿 | E-S06 documented-not-probed |
| SS-21 | 手动换刀 | 面板按钮 | `tlccw.bmp` / `tlcw.bmp` / `chngtl.bmp` / `loosen.bmp` | 松刀/换刀 | E-S03 |
| SS-22 | CRT 坐标三页 | 面板/软键 | POS 键切换 MACHINE / RELATIVE / ABSOLUTE | 循环启动前核对 ABSOLUTE 与 G54 一致（AGENTS §2.F） | AGENTS 公理 + E-S06 |
| SS-23 | 程序显示 | 面板 | EDIT 模式 → 程序号 Oxxxx | `.cnc` 程序载入/列表 | E-S04（.cnc 样本结构） |
| SS-24 | DNC | 面板按钮 | `dnc.bmp` | 边传边加工 | E-S03 |
| SS-25 | 超程报警 | 面板/报警 | `OverTravel.bmp` | 硬限位触发 | E-S03 |
| SS-26 | 电源 | 面板按钮 | `poweron.bmp` / `poweroff.bmp` | 通电/断电 | E-S03 |
| SS-27 | 冷却 | 面板按钮 | `cool.bmp` | M08 开 / M09 关 | E-S03 |
| SS-28 | 主轴正反转 | 面板按钮 | `cw.bmp` / `ccw.bmp` / `mst.bmp` | M03/M04/M05 | E-S03 |
| SS-29 | 照明/润滑 | 面板按钮 | `light.bmp` / `oil.bmp` | 辅助 | E-S03 |
| SS-30 | 对刀量离线计算 | API(python) | `SSCNCBridge().calculate_tool_offsets(tools)` | 返回 Tnnnn + geometry_x/z + R + 象限 T(3/2/8) | E-S05 verified-working（纯计算） |

## 对刀公式（E-S05/E-S06 汇总，供 Agent 复现）

```text
车外圆后测直径 D_meas → 形状补正 X = D_meas（直径编程）
车端面后 Z            → 形状补正 Z = 0
刀尖圆弧 R            → 补正页面 R 值（默认 0.8）
刀位象限 T            → 外圆=3 / 内孔=2 / 螺纹=8
刀补号               → Tnnnn（T 号 = 刀号 = 补正号，如 T0101）
```
