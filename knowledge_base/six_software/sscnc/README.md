# 斯沃数控仿真软件 SSCNC 7.2 知识库（Virtual CNC Machine / Shopfloor Simulation）

> 文档化逆向产物（reverse-skill offline-sample RE，auth.status=granted）。生成基准 2026-11-03。
> 全部断言可回溯到 `evidence.md` 的 E-ID；通道状态三态：verified-working / confirmed-negative / documented-not-probed。

## 1. 软件身份表

| 项 | 值 |
| :-- | :-- |
| 显示名 | 斯沃数控仿真软件 SSCNC 7.2（南京斯沃软件 Swansoft） |
| 版本 | 7.2 |
| 类别 | Virtual CNC Machine / Shopfloor Simulation（虚拟数控机床操作仿真） |
| 安装根 | `E:\仿真软件\2斯沃7.2（内含安装说明）\SSCNC`（内含安装说明目录）[高]（本轮 Glob 实测） |
| 登录入口 | `...\SSCNC\CNCLogin.exe`（选机床/控制器）[高] |
| 仿真主程序 | `...\SSCNC\<控制器>\sscnc.exe`（每控制器一个，如 `FANUC\FANUC0iT\sscnc.exe`）[高] |
| 进程名 | `CNCLogin.exe`、`SSCNC.exe` |
| 桌面快捷方式 | `C:\Users\Public\Desktop\斯沃数控仿真软件.lnk` |
| COM ProgID | **无 COM**（software_registry com_prog_id=None）[高] confirmed-negative |
| 能力标签 | fanuc_0it_0im_emulation / wcs_g54_setup / tool_offset_quadrants / cycle_start |
| 六软件注册表状态 | READY（`bridges/software_registry.py`） |

## 2. 本目录文件清单

| 文件 | 用途 |
| :-- | :-- |
| `README.md` | 本文件：身份索引 + 阅读指南 |
| `modules.md` | 功能模块树（按应用领域分块 + mermaid） |
| `automation_api.md` | 自动化通道总表 + sscnc_bridge.py 实现方式与局限 |
| `commands.md` | 命令表：面板按钮/模式/对刀操作路径（含官方说明书步骤） |
| `file_formats.md` | `.cnc` NC 程序 / config.ini / spec.ini / *.lib / sysparam.XML |
| `workflows.md` | 闭环工作流（开机→回零→对刀→编程→循环启动，对齐 AGENTS.md 公理） |
| `config.md` | config.ini / spec.ini / offset.dat / SERVER 组件 |
| `module_inventory.json` | 机器可读模块清单（与 markdown 严格一致） |
| `evidence.md` | 证据链 |

## 3. 模块树与自动化入口摘要

- 软件结构 = **登录器 CNCLogin → 按控制器厂商分目录（FANUC/KND/MITSUBISHI/Haas/Mazak/SINUMERIK/Heidenhain/HNC/MORI/JNC/NCT）→ 每控制器 `sscnc.exe` + 机床厂商变型 exe + 配置/lib 文件**。详见 `modules.md`。
- 自动化核心结论：**SSCNC 无 COM、无公开脚本接口**；既有桥接 `sscnc_bridge.py` 只做「启动进程 + win32gui 找窗口 + 对刀偏移量离线计算」三件事，**面板按键（模式选择/对刀软键/循环启动）本轮无实测自动化通道**，标注 documented-not-probed。

## 4. 供 Virtu 模型训练的使用说明

1. 训练操作顺序（FANUC 0i 面板）：`poweron` → `home`(回零) → 选模式(AUTO/EDIT/MDI/JOG) → 对刀(G54 坐标系[测量]、刀具补正[形状]) → 编辑/调入 `.cnc` 程序 → `cycstart` 循环启动 → 用 `sbk`(单段)/`dry`(空运行) 先行校验。
2. 坐标读数判读：CRT 三页 MACHINE / RELATIVE / ABSOLUTE(G54)，循环启动前必须核对 ABSOLUTE 与 G54 工件坐标一致（对齐 AGENTS.md §2.F 公理）。
3. 对刀公式可直接复用 `sscnc_bridge.calculate_tool_offsets`：车刀象限 T=3（外圆 OD）/2（内孔 ID）/8（螺纹），刀补代码 `Tnnnn`。
