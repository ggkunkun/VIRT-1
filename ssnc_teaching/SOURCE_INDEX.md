# 斯沃数控仿真教学体系 — 一手资料索引（写作唯一依据）

> 版本 v1.0 | 软件版本 SSCNC 7.2.2.0 | 建立日期 2026-11-18
> 所有教学描述必须且只能引用本索引中的一手资料，禁止凭空推断软件操作。

## 软件实体（实测）
- 真实安装路径：`E:\仿真软件\2斯沃7.2（内含安装说明）\SSCNC\CNCLogin.exe`（桌面快捷方式 `E:\SSCNC\CNCLogin.exe` 已失效）
- 版本：SSCNC 7.2.2.0（安装方法.txt + general.ini `CNC=37`）
- 主窗口类：`ClassName_Swansoft_CNC_Simulation`
- MCU 内核 DLL：StdF0iCtrl.dll / StdFanucCtrlor.dll / StdSiemensCtrlor.dll / YJControlor.dll(华中) / YouJiaCtrlor.dll / BJControlor.dll(北京凯恩帝) / DLControlor.dll(大森) / JNControlor.dll 等

## 实测证据（evidence/）
- `menu_structure_measured.json` — Win32 API 实测的 9 大菜单全部子项（最高优先级依据）
- `sscnc_main.png` / `sscnc_main_crop.png` / `probe_launch_fullscreen.png` — 真实软件界面截图（当前 MITSUBISHI M80）
- 实测菜单：文件 / 视窗视图 / 显示模式 / 机床操作 / 工件操作 / 工件测量 / 习题与考试 / 查看 / 帮助
  - 机床操作 → 参数设置、冷却液调整、基准芯棒选择、寻边器选择、Z向对刀仪选择(100mm)、选择刀具、舱门
  - 工件操作 → 选择毛坯、工件装夹、工件放置
  - 工件测量 → 刀路测量(调试)、特征点、特征线、距离、角度、测量退出
  - 文件 → 清空NC代码、打开、保存、另存为、退出
  - 显示模式 → 床身显示模式、加工声效、显示坐标、显示铁屑、显示冷却液、显示毛坯、显示工件、透明显示、刀具交换装置(ACT)显示、显示刀位号、显示刀具、显示透明刀具、显示刀轨

## 官方帮助知识库（source/help_kb_md/，253 主题，69.8 万字）
- `_index.json` — 主题索引（src 源文件路径 / md 文件名 / title / chars / imgs）
- 命名规则：`<品牌>__<子目录>__<主题>.md`，例如：
  - `fanuc__fanuc_MPRG__ref_frame.md`（FANUC 铣削坐标系统）
  - `fanuc__fanuc_MPRG__GCode.md`（FANUC 铣削 G 代码，含 G00-G89 分组表）
  - `fanuc__fanuc_MPRG__assistant.md`（FANUC M 代码）
  - `siemens__siemens_MPRG__*.md`（西门子铣削，含 828D/802D/810D 固定循环）
  - `gsk__*`, `hnc__*`（华中）, `mitsubishi__*`, `fagor__*`, `HEIDENHAIN530__*`, `knd__*`（凯恩帝）, `great150i__*`, `dasen3i__*`, `wa__*`, `RENHE__*`, `SKY2003N__*`（各系统）
- 官方截图源文件：`source/chm_cn/<原始相对路径>`（3600 jpg + 1553 gif + 124 png）
  - 注意：md 头部"关联官方截图"路径多了一层 `chm_cn/`，实际应取 `source/chm_cn/` + 从 htm 原始相对目录起的路径

## 系统清单（general.ini，37 个 CNC 配置）
FANUC 0MD / 0MD2.5 / 0TD / 0iM / 0iMF / 0iT / 0iTF / 18M / 18T / 18iM / 18iT / 21iM / 21iT；
Mazak VCN410 / QTN100；SINUMERIK 801 / 802S M / 802S T / 802C-802Se M / 802C-802Se T（及后续）；
MITSUBISHI E60/E68、FAGOR8055、HEIDENHAIN iTNC530、华中 HNC-21M/21T/22T、KND100M/100T/1TB、
GREAT150i M/T、GSK990M/928TA/928TC/980T/983M、DASEN3i M/T、WA310M/T、RENHE32T、SKY2003N 等。

## 报警库（source/chm_cn 提取 + lang/）
- `fanuc_alarmlist_cn.ini`：308 条 FANUC 报警（NAME001..308，编号 000/001/002...）
- 源文件位于 `E:\仿真软件\...\SSCNC\common\lang\fanuc_alarmlist_cn.ini`（GBK）
- 各系统语言文件：`E:\...\SSCNC\common\lang\*_lan_cn.ini`

## 官方示例程序（official_samples/）
- 路径：`E:\新建文件夹 (3)\09_SOFTWARE_OFFICIAL_SAMPLES\05_SSCNC_SWAN_SIMULATION`
- 系统目录：FANUC(FANUC0iM/0iMF/0iT...)、SIEMENS、FAGOR、DASEN、KND、GSK、HNC、MITSUBISHI 等
- 每例含 config.ini / Model(control.ini,spec.ini) / offset.dat / params.lib / prglib.lib / nc程序(*.cnc)
- 典型程序：EX10.cnc、G41/G42/G81/G82/G83/G51/G68.cnc、O0002/O0010..O0019 等

## 桥接与能力边界（bridges/sscnc_bridge.py，实测结论）
- 面板为自绘画布，无 Button/Static 键位子控件 → 键位自动化需坐标点击（不能 PostMessage BM_CLICK）
- 已实现：`calculate_tool_offsets()`（FANUC T1-T9 刀尖象限 3=外圆/2=内孔/8=螺纹）、`panel_capability()`（诚实报告 unsupported）
