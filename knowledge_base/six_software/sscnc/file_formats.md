# SSCNC 7.2 文件格式

> 证据来源：安装目录 Glob（E-S01/E-S02）、config.ini/spec.ini 逐行读取（E-S04）、`.cnc` 样本读取（E-S04b）、斯沃官方（E-S06）。

## 1. NC 程序（仿真输入）

| 格式 | 扩展名 | 角色 | 说明 | 证据 |
| :-- | :-- | :-- | :-- | :-- |
| FANUC 程序 | `.cnc` / `.CNC` | 原生（ASCII 文本） | 程序号 O0001 等；样本头部：`%`、`G21`、`M06T01`、`G54G90G00X0.Y0.Z50.`、`M3S800`、`M08`、`G01...F...` | E-S04b（EX10.cnc 5700+ 行实测） |
| 程序/刀位辅助 | `.ct` / `.pj` / `.wp` | 原生（JNC/KND 机床样本） | JNC30T `EX6.CT/EX6.PJ/EX6.WP`；KND `om011.ct/.pj` | E-S01 Glob |

`.cnc` 样本（JNC30M EX10.cnc 头部）：

```text
%
G21
M06T01
G54G90G00X0.Y0.Z50.
M3S800
M08
X0.646Y-8.648
Z10.001
G01Z0.001F100
...
```

## 2. 控制器/机床配置（每控制器目录）

| 格式 | 文件名 | 位置 | 说明 | 证据 |
| :-- | :-- | :-- | :-- | :-- |
| 主控配置 | `config.ini` | `<控制器>\` | 区段：[GENERAL]（DiameterOffset/MachineStep/PrecisionDisp/CONTROL/程序保护）、[OPERATION]（冷却/关门/ACT）、[OUTPUT]（颜色/缓冲区/告警倍率）、[TRACECOLOR]（TOOL01-25 刀轨 RGBA）、[MACCOLOR]、[CAM]（320x200） | E-S04 逐行读取 |
| 机床行程 | `Model\spec.ini` | `<控制器>\Model\` | XSIZE=800/YSIZE=400/ZSIZE=350、ORG/REF 原点、XMIN/XMAX 行程极限、ACTX/ACTY/ACTZ 换刀点 | E-S04 |
| 机床型号 | `Model\Model.ini` | `<控制器>\Model\` | 机床型号描述（FANUC0iT/KND1000T 等存在） | E-S01 |
| 刀补数据 | `offset.dat` / `OffSet.dat` | `<控制器>\` | 几何/磨耗补正存储（二进制/文本混合，未解析） | E-S01 |
| 机床参数 | `rparam.dat` | `<控制器>\` | 机床侧参数 | E-S01 |
| 系统参数 | `sysparam0.XML` ~ `sysparam3.XML` | `<控制器>\`（FANUC0iT 实测存在） | FANUC 系统参数（XML） | E-S02 |
| 程序库 | `PRGLIB.LIB` / `prglib.lib` | `<控制器>\` | 内置程序库 | E-S01 |
| 参数库 | `PARAMS.LIB` / `params.lib` | `<控制器>\` | 参数库 | E-S01 |
| 图形库 | `GRAPH.LIB` / `graph.lib` | `<控制器>\` | 3D 模型/图形资源 | E-S01 |
| 寄存器库 | `REGISTER.LIB` / `register.lib` | `<控制器>\` | 寄存器/变量 | E-S01 |
| 刀补库 | `offsetdat.lib` / `offsetdat.lib` | `<控制器>\` | 刀补库 | E-S01 |
| 报警库 | `alarm.lib` | `<控制器>\`（FANUC0iT） | 报警文本 | E-S02 |
| 运行日志 | `sscncmsg.log` / `sscnc.suo` / `temp.tmp` | `<控制器>\` | 运行消息/临时 | E-S01 |

## 3. 面板资源

| 格式 | 位置 | 说明 | 证据 |
| :-- | :-- | :-- | :-- |
| 按键位图 | `JNC\JNC_BTN_Symbol\*.bmp` | auto/edit/mdi/hnd/cycstart/cycstop/dnc/dry/sbk/zlock/hfeed/vfeed/spup/spdown/tlccw/tlcw/poweron/poweroff/cool/cw/ccw/home/inc/light/oil/loosen/MLock/OverTravel 等（约 40 张） | E-S03 Glob |

## 4. 公共与服务组件（`common\` / `SERVER\`）

| 文件 | 位置 | 说明 | 证据 |
| :-- | :-- | :-- | :-- |
| `UpdateManager.exe` / `UpdateInfor.exe` | `common\` | 升级 | E-S01 |
| `screensvr.exe` / `screenviewer.exe` | `common\` | 屏幕转播（教学演示） | E-S01 |
| `general.ini` / `socket.ini` / `tips.txt` | `common\` | 公共配置/提示 | E-S01 |
| `SSPaperAns.exe` | `common\` | 试卷/答题（教学） | E-S01 |
| `SSCNCSrv.exe` / `ssFtp.exe` / `ssHttp.exe` | `SERVER\` | DNC/网络服务（FTP/HTTP） | E-S01 |
| `monitor.ini` / `SERVER\config.ini` | `SERVER\` | 服务配置 | E-S01 |
| `Lacewing.dll` / `sqlite3.dll` / `zlib1.dll` / `sssd.dll` / `sssdnt112.dll` / `VcncDll.dll` | `SERVER\` | 服务依赖库 | E-S01 |

> 全部文件位置已 Glob 核验；二进制内容（offset.dat/*.LIB/sysparam.XML 取值）本轮未解析，标注 documented-not-probed。
