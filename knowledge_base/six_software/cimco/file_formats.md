# CIMCO Edit 2026 文件格式

> 表：格式 | 扩展名 | 角色 | 说明 | 证据。官方规范链接来自实际搜索。

| 格式 | 扩展名 | 角色 | 说明 | 证据 |
|---|---|---|---|---|
| NC 程序 | `.nc`/`.ptp`/`.cnc` | 原生编辑 | ISO 6983 G 代码文本（FANUC Macro B 可含 # 变量/WHILE） | E-203/E-207 |
| 后处理脚本 | `.js` | 后处理 | Mill/Lathe 后处理器（fanuc.js、heidenhain.js、Siemens 840D.js、Haas.js、Fadal.js、Fagor 8055i、IsoLathe 变体） | E-203 |
| 机床配置 | `.mcfg` | 配置 | 机床运动配置（DMG Mori/Doosan/Haas/Hermle/Quaser/Roeders/Cimco 3/5 轴） | E-203 |
| 机床部件 | `.stl` | 机床仿真 | 机床床身/各轴/夹具三角网（MachineCfg 下） | E-203 |
| 机床仿真配置 | `config.json` | 配置 | Cimco Mill 3/5 轴机床仿真参数 | E-203 |
| 传输模板 | `.tpl` | 配置 | DNC 传输模板（FANUC-FAPT、HEIDENHAIN、MAZAK、OKUMA、LSV2、XMODEM、NETWORK、GENERIC-MONMACROS、GENERIC-PERCENT） | E-203 |
| 文件类型定义 | `.typ` | 配置 | 控制系统类型（ISO_G-Code.TYP、Heidenhain_Conversational.TYP、Mazak_Mazatrol、Mitsubishi M700-70/M800-80、Okuma Milling、Roeders_RMS-6） | E-203 |
| 后处理器模板脚本 | `.epl` | 配置 | FtpClient.epl / Generics.epl / Okuma.epl | E-203 |
| 刀具库 | `.tmlib` | 配置 | 刀具库（ISO/Inch Drills、Mills、Taps、Spot drills、Counter sinks、Holders；ISCAR/Seco） | E-203 |
| 格式转换器 | `.conv` | 转换 | fanuc.conv、heidenhain.conv、SinumerikTurning.conv、NumeripathTurning.conv | E-203 |
| 背绘图 | `.cdd` | 样例 | 背绘教学图（lathe1.cdd、metric-g71.cdd、inch-g71.cdd、tutorial） | E-203 |
| 宏包 | `.macbundle` | 样例 | ISO Milling / Haas Milling Tutorial 宏包 | E-203 |
| 样例 NC | `.nc`/`.bef`/`.min` | 样例 | Fanuc 30i/31i/32i、Haas NGC、Mazak Mazatrol、Mitsubishi M800-80、Roeders .bef、Traub .min | E-203 |
| 机床主配置 | `.mch` | 配置 | Sys\MACHINE1.MCH / MACHINE2.MCH | E-203 |
| 刀具清单 | `ToolList.txt`/`NewToolList.txt` | 配置 | 刀具清单文本 | E-203 |
| 螺纹数据表 | `Threads.dat` | 配置 | 螺纹参数 | E-203 |
| 帮助 | `.chm` | 文档 | nc-base（编辑器）/ cnc-calc（计算器）/ edit（编辑），多语言 | E-203 |
| PDF 教程 | `.pdf` | 文档 | cimco-edit-basic-iso-programming-tutorial-1/2、mill-turn-tutorial；Post Processor Manual | E-203 |

## 官方规范链接

- **CIMCO Edit 2026 User Guide – Backplot**：
  https://docs.cimco.com/en/docs/edit/2026/program-tabs/backplot/file/ （E-205）
- **CIMCO Edit 2026 User Guide – Simulation**：
  https://docs.cimco.com/en/docs/edit/2026/simulation/ （E-205）
- **CIMCO Edit v6 NCBase User Guide（PDF）**：
  https://www.cimco.com/documentation/documents/cimco_edit/user_guides/en/cimco-edit-6-ncbase-user-guide.pdf （E-205）
- **ISO 6983-1:2009（NC 程序格式/G 代码规范）**：
  https://www.iso.org/obp/ui/en/#!iso:std:34608:en （E-207）
- **FANUC Custom Macro B（变量/IF/WHILE/G65 指南）**：
  https://www.mentorcnc.com/en/fanuc-custom-macro-b-guide/ （E-208）
