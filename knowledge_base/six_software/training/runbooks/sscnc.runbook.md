# 斯沃数控仿真 SSCNC 7.2 运行手册（runbook）

> 模型直接注入用操作基准。参数来自 `knowledge_base\six_software\sscnc\`（commands.md / workflows.md / plugins.md / automation_api.md）。
> 通道状态三态：verified-working（历史桥接）/ confirmed-negative / documented-not-probed。

## 0. 速查卡

| 项 | 值 |
| :-- | :-- |
| 安装根 | `E:\仿真软件\2斯沃7.2（内含安装说明）\SSCNC` |
| 入口 | `CNCLogin.exe`（登录器）→ 各控制器 `FANUC\FANUC0iT\sscnc.exe` 等 |
| 进程 | `CNCLogin.exe` / `sscnc.exe` |
| 版本 | 7.2 |
| 控制器 | 11 厂商：FANUC / KND / MITSUBISHI / Haas / Mazak / SINUMERIK / Heidenhain / HNC / MORI SEIKI / JNC / NCT |
| 关键文件 | .cnc NC 程序 / config.ini / spec.ini / sysparam0-3.XML / offset.dat（二进制）/ *.lib |
| COM | **confirmed-negative**（无 ProgID） |

## 1. 面板操作路线（FANUC 0i 仿真，逐步可执行）

### 任务 1：开机回零
1. `poweron.bmp` 上电 → 切 **REF（home.bmp）**模式 → X/Z 轴回零。
2. 检查点：CRT ABSOLUTE(G54) 原点归零。

### 任务 2：对刀 G54
1. 切 **JOG（hnd.bmp）** 靠近工件。
2. OFFSET SETTING → **[坐标系]** → 选 **G54** → **[测量]**：X 轴按工件直径测量值（如 40.0）、Z 轴按端面 0.0 录入。
3. 检查点：CRT ABSOLUTE(G54) 页显示工件原点。

### 任务 3：刀具形状补正
1. OFFSET SETTING → **[补正]** → **[形状]** → 选刀补号 **Tnnnn**。
2. 刀补类型：**T=3 外圆 / T=2 内孔 / T=8 螺纹**。
3. 检查点：形状页对应刀补号数值已写入。

### 任务 4：调入程序
1. 切 **EDIT（edit.bmp）** → 调入 `*.cnc` 程序（O0001 / EX10 / G81 钻削等）。
2. 程序格式：`%` 头、G21 公制、M06T 换刀、G54G90G00 定位、M3S 主轴、M08 冷却、G01F 进给。

### 任务 5：循环启动前检查 + cycstart
1. 切 **AUTO（auto.bmp）**。
2. CRT 三页核对：**MACHINE（机械）/ RELATIVE（相对）/ ABSOLUTE（绝对 G54）**——按 AGENTS.md §2.F 公理核对坐标读数。
3. 确认安全后按 **cycstart.bmp** 启动。
4. 辅助：dry.bmp 空运行、sbk.bmp 单段、zlock.bmp 机床锁、hfeed/vfeed 倍率。

## 2. API/自动化路线（三态标注）

| 通道 | 调用 | 状态 |
| :-- | :-- | :-- |
| COM Dispatch | （无 ProgID） | **confirmed-negative** |
| 进程拉起 | `SSCNCBridge.launch()`（CNCLogin.exe） | verified-working（历史桥接） |
| 窗口枚举 | `SSCNCBridge.find_window()` win32gui 标题匹配 | verified-working（历史桥接） |
| 对刀量离线计算 | `SSCNCBridge.calculate_tool_offsets()` → Tnnnn + R + 象限 | verified-working（纯计算） |
| 面板模式键触发（AUTO/EDIT/MDI/JOG） | 坐标化点击 | documented-not-probed |
| 对刀软键录入（[坐标系][测量]/[补正][形状]） | 坐标化点击 | documented-not-probed |
| cycstart 循环启动触发 | 坐标化点击 | documented-not-probed |
| DNC 服务（ssFtp/ssHttp/SSCNCSrv） | SERVER\ | documented-not-probed |

## 3. 控制器插件路线（见 plugins.md）

| 控制器 | 启动 exe | 类型 |
| :-- | :-- | :-- |
| FANUC 0iT/0iM/0iTF/0iMF/0MD/18/21i | `FANUC\<变体>\sscnc.exe`（+ ShenYang/EMCO/Hardinge 等机床变型） | 车/铣 |
| KND 凯恩帝 | `KND\KND1000T\sscnc.exe` 等 | 车/铣 |
| MITSUBISHI | `MITSUBISHI\M70M\sscnc.exe`（+ M70Panel.exe） | 车/铣 |
| Haas | `Haas\VF\Haas.exe` | 加工中心 |
| Mazak | `Mazak\QTN100.exe` / `VCN410.exe` | 车/铣 |
| SINUMERIK | `SINUMERIK\828D.exe` | 铣 |
| Heidenhain | `Heidenhain\530.exe` | 铣 |
| HNC 华中 | `HNC\HNC818.exe` | 车/铣 |
| MORI SEIKI | `MORI SEIKI\Mori.exe` | — |
| JNC 秦川 | `JNC\JNC30T\sscnc.exe` | 车/铣 |
| NCT | `NCT\NCT104T.exe` | 车/铣 |

面板位图（`JNC\JNC_BTN_Symbol\*.bmp`）：模式区 auto/edit/mdi/hnd/inc/home；运行区 cycstart/cycstop/dry/sbk/zlock；倍率 hfeed/vfeed/spup/spdown；换刀 tlccw/tlcw/chngtl；辅助 cw/ccw/cool/poweron。

## 4. 常见故障与处置

| 现象 | 处置 |
| :-- | :-- |
| 循环启动后立即撞刀 | 回到 AUTO 前检查：ABSOLUTE(G54) 原点 + Tnnnn 形状刀补象限（外圆 T3/内孔 T2/螺纹 T8） |
| 对刀 X 值偏 2 倍 | 确认 [测量] 录入的是**直径值**而非半径 |
| offset.dat 打不开 | 二进制文件（E-S09）—— Agent 侧用 calculate_tool_offsets 离线算，面板手工录入 |
| 想用 COM 控制面板 | 勿用——无 COM；桥接仅能 launch + 窗口枚举 + 离线对刀计算 |
| 超铭牌转速要求 | 拒绝虚构转速，按真实控制器铭牌 S 值建模（安全联锁） |
