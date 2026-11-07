# SSCNC 7.2 证据链（Evidence）

> 本轮（2026-11-04）执行栈 = Read/Grep/Glob + 官方在线文档；未现场启动 GUI。

| E-ID | 声明摘要 | 证据类型 | 证据位置 | 置信度 | 本轮是否复测 |
| :-- | :-- | :-- | :-- | :-- | :-- |
| E-S01 | 安装根结构（common/SERVER/JNC/KND/Haas/MITSUBISHI/NCT/Mazak/SINUMERIK/Heidenhain/HNC/MORI 目录与 exe/lib/log） | 安装目录 Glob | `E:\仿真软件\2斯沃7.2（内含安装说明）\SSCNC\` | 高 | 是 |
| E-S02 | FANUC 控制器族（0iT/0iM/0iTF/0iMF/0MD/0TD/18T/M/i/21iT/M）+ 机床厂商变型 exe + sysparam0-3.XML/alarm.lib | 安装目录 Glob | `...\SSCNC\FANUC\**\*.exe`、`...\FANUC\FANUC0iT\` | 高 | 是 |
| E-S03 | 面板按键位图（auto/edit/mdi/hnd/cycstart/cycstop/dry/sbk/zlock/hfeed/vfeed/spup/tlccw/poweron/cool/cw/ccw/home/inc 等约 40 张） | 位图目录 Glob | `...\SSCNC\JNC\JNC_BTN_Symbol\*.bmp` | 高 | 是 |
| E-S04 | config.ini（[GENERAL]/[OPERATION]/[OUTPUT]/[TRACECOLOR]TOOL01-25/[CAM]）与 Model/spec.ini（XSIZE=800/YSIZE=400/ZSIZE=350/行程/ACT 换刀点）逐行 | 配置文件 Read | `JNC\JNC30M\config.ini`、`JNC\JNC30M\Model\spec.ini` | 高 | 是 |
| E-S04b | `.cnc` NC 程序样本结构（%/G21/M06T01/G54G90G00/M3S800/M08/G01F） | 样本 Read | `JNC\JNC30M\NC\EX10.cnc`（头部 50 行） | 高 | 是 |
| E-S05 | 桥接实现：launch/find_window(win32gui 标题匹配)/calculate_tool_offsets(象限 T=3/2/8、Tnnnn、R) | 桥接代码 Read | `D:\Virtu模型\bridges\sscnc_bridge.py` | 高 | 是 |
| E-S06 | 斯沃官方对刀/操作说明书（FANUC 0iT/0iM 对刀步骤、G54[测量]、补正[形状]） | 官方在线文档（实际搜索返回 URL） | http://download.swansc.com/PDF/toolpreset.pdf ；http://www.swansc.com/cn/solution/documents_Fanuc_offset.html ；http://www.swansc.com/cn/products/fanuc0it.html ；http://www.swansc.com/cn/download/PDF.html | 高（官方） | 是（在线） |
| E-S07 | 无 COM（com_prog_id=None）、进程 CNCLogin.exe/SSCNC.exe、窗口标题 斯沃/SSCNC/FANUC/ClassName_CCCStartDlg | 注册表代码 Read | `D:\Virtu模型\bridges\software_registry.py`（SOFTWARE_SPECS["sscnc"]） | 高 | 是 |

## 无证据不写的边界声明

- 面板按键「触发」（cycstart/软键录入）本轮无实测，全部标注 `documented-not-probed`，未当作已验证自动化能力。
- `*.LIB` 与 `offset.dat`（二进制）内部取值本轮未解码；`sysparam.XML` 已部分解析（见 E-S08），字段语义未对照 FANUC 参数手册。
- 不包含任何许可证/授权/激活机制内容。

---

## 阶段一插件级追加证据（2026-11-04）

| E-ID | 声明摘要 | 证据类型 | 证据位置 | 置信度 | 本轮是否复测 |
| :-- | :-- | :-- | :-- | :-- | :-- |
| E-S08 | sysparam0.XML 结构解析：R0000/R0001... 参数组、parapartname=SETTING、paradetailinfoT1..T8 为 `#` 分隔串（首字段参数名 empty/INI/ISO/TVC/FCV/RDG/MIR/RMV） | 配置 XML 逐行 Read | `...\SSCNC\FANUC\FANUC0iT\sysparam0.XML`（60 行样本，全文 3126 行） | 高（结构）/ 中（字段语义） | 是 |
| E-S09 | offset.dat 为二进制，Read 拒绝读取（本轮不解码） | 二进制探测 | `...\FANUC\FANUC0iT\offset.dat`、`...\JNC\JNC30M\offset.dat` | 高（二进制事实） | 是 |
| E-S10 | 11 厂商控制器目录与可执行文件清单（FANUC/KND/MITSUBISHI/Haas/Mazak/SINUMERIK/Heidenhain/HNC/MORI SEIKI/JNC/NCT）+ common/SERVER 组件 | 安装目录 Glob | `...\SSCNC\` 各子目录 | 高 | 是 |
