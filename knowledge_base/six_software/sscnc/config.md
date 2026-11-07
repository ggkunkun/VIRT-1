# SSCNC 7.2 配置文件与目录

| 配置文件 / 目录 | 用途 | 位置 | 证据 |
| :-- | :-- | :-- | :-- |
| 登录器 | 启动/选机床 | `...\SSCNC\CNCLogin.exe` | E-S01/E-S05 |
| 每控制器仿真器 | 面板主体 | `...\SSCNC\<厂商>\<控制器>\sscnc.exe`（如 `FANUC\FANUC0iT\sscnc.exe`） | E-S02 |
| 主控 config | 显示/操作/颜色/程序保护 | `...\SSCNC\<控制器>\config.ini`（[GENERAL]/[OPERATION]/[OUTPUT]/[TRACECOLOR]/[CAM]） | E-S04 逐行读 |
| 机床行程 spec | 行程/原点/换刀点 | `...\SSCNC\<控制器>\Model\spec.ini`（XSIZE/YSIZE/ZSIZE/XMIN/XMAX/ACTX...） | E-S04 |
| 机床型号 | `Model.ini` | `...\SSCNC\<控制器>\Model\Model.ini` | E-S01 |
| 刀补存储 | `offset.dat` / `OffSet.dat` | `...\SSCNC\<控制器>\` | E-S01 |
| 机床参数 | `rparam.dat` | `...\SSCNC\<控制器>\` | E-S01 |
| FANUC 系统参数 | `sysparam0~3.XML` | `...\SSCNC\FANUC\FANUC0iT\` | E-S02 |
| 程序/参数/图形/寄存器库 | `PRGLIB.LIB` / `PARAMS.LIB` / `GRAPH.LIB` / `REGISTER.LIB` / `offsetdat.lib` | 各控制器目录 | E-S01 |
| 报警库 | `alarm.lib` | FANUC0iT 等 | E-S02 |
| 运行日志 | `sscncmsg.log` / `sscnc.suo` / `temp.tmp` | 各控制器目录 | E-S01 |
| 面板按键位图 | `JNC\JNC_BTN_Symbol\*.bmp`（约 40 张，模式/倍率/换刀/辅助） | `...\SSCNC\JNC\JNC_BTN_Symbol\` | E-S03 |
| 公共配置 | `common\general.ini` / `common\socket.ini` / `common\tips.txt` | `...\SSCNC\common\` | E-S01 |
| 屏幕转播 | `common\screensvr.exe` / `common\screenviewer.exe`（教学演示） | `...\SSCNC\common\` | E-S01 |
| 升级 | `common\UpdateManager.exe` / `common\UpdateInfor.exe` | `...\SSCNC\common\` | E-S01 |
| DNC/网络服务 | `SERVER\SSCNCSrv.exe` / `ssFtp.exe` / `ssHttp.exe` + `SERVER\config.ini` / `monitor.ini` | `...\SSCNC\SERVER\` | E-S01 |
| 服务依赖 | `Lacewing.dll` / `sqlite3.dll` / `zlib1.dll` / `sssd.dll` / `VcncDll.dll` | `...\SSCNC\SERVER\` | E-S01 |

## 控制器厂商库（目录级实测 E-S02）

`FANUC`（0iT/0iM/0iTF/0iMF/0MD/0TD/18T/18M/18iT/18iM/21iT/21iM + 机床厂商变型）、`KND`（K10M/T、K100M/T/Ti/TB、K1000M/T）、`MITSUBISHI`（E60M/T、E68M/T、M70M/T）、`Haas\VF`、`Mazak`（QTN100/VCN410）、`SINUMERIK`（808D/828D/EMCO）、`Heidenhain\530`、`HNC`（HNC210/808/818）、`MORI SEIKI`、`JNC`、`NCT`（104T/M）。

> 许可证/授权相关文件不在本知识库展开（out-of-scope）。
