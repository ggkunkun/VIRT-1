# VERICUT 9.6 命令表（可复现调用方式）

> 类型枚举：菜单 / 工具栏 / 命令行(bat) / API(python 桥) / 快捷键。
> GUI 坐标均为 **1920×1080 全屏物理像素**（= OCR 千分比 ×19.2 / ×10.8）；窗口漂移时须原子截图重校准（E-V02）。

| 命令 ID | 模块 | 类型 | 参数 / 坐标 | 说明 | 证据 |
| :-- | :-- | :-- | :-- | :-- | :-- |
| VC-01 | 工程文件 | 命令行+菜单 | `set CGTECH_VCPROJECT=<绝对路径.vcproject>` 后 `cmd /c vericut_agent.bat`；GUI：File→Open Project | 启动自动加载工程（免手动打开） | E-V06 verified-working |
| VC-02 | Setup 坐标系 | 菜单 | Project Tree → 右键 Setup → Configure Coordinate System | 工件坐标系/G54 对齐基准 | E-V09 documented-not-probed |
| VC-03 | NC 程序 | 菜单 | Project Tree → NC Programs → Configure NC Programs；NC Program Type = G-Code Data | 载入 .nc/.mcd（FANUC G 代码）；本项目用 `04_CIMCO_Edit_2026.nc`（G71/G70） | E-V02/E-V09 |
| VC-04 | 刀具库 | 菜单 | Tool Manager → Project → Tools；保存为 `.tls` | 按 Tool ID 管理刀具/刀柄/夹头 | E-V09 documented-not-probed |
| VC-05 | 模型 | 菜单 | Project Tree → Models；Configure Model → Model 选项卡 | 毛坯 Cut Stock / 设计 Design / 夹具 Fixture；支持 STL/.vct/.sor/.swp/.stp | E-V09 |
| VC-06 | 机床文件 | 菜单 | Machine/Control → Save As (Machine)；`.mch` XML / `.xmch` 加密 | 默认 3 轴立加；可换机床库 | E-V09 |
| VC-07 | 控制系统 | 菜单 | Machine/Control → Control；`.ctl`/`.xctl` | G 代码解释规则（模态/宏/表格）；FANUC 0i 对应控制文件 | E-V09 |
| VC-08 | 机床配置隐藏 | 环境变量 | `set CGTECH_MACHINE_CONFIG=FALSE` | 启动后隐藏机床配置菜单 | E-V01 注释 documented-not-probed |
| VC-09 | 播放仿真 | API(python)+GUI 坐标 | `click(1890, 860)`；`play_simulation(hwnd)` | 绿色播放三角；**无键盘快捷键**（KeyBinding.java 反编译确认） | E-V02/E-V05 verified-working |
| VC-10 | 状态灯 | API(python) | 检测 (710,820) 绿色像素 0↔410 交替 | BUSY=仿真中 / READY=空闲 | E-V02 |
| VC-11 | 仿真日志 | API(python) | `parse_sim_log(force_turning_sample.log)` | 回读总时间/错误/警告/刀具摘要/去除体积/碰撞体积 | E-V02 verified-working |
| VC-12 | Auto-Diff | 菜单 | Analysis → AUTO-DIFF → Options；Design Consistency Check | **红=过切(致命停修) / 蓝=残料(加半精) / 绿=合格**（对齐 AGENTS.md） | E-V09 + AGENTS 公理 |
| VC-13 | OptiPath/Force | 菜单 | Analysis → OptiPath/Force；优化库 `.olb`；输出 `.opti/.mco` | 进给率优化 | E-V09 documented-not-probed |
| VC-14 | X-Caliper/Inspection | 菜单 | Analysis → X-Caliper / Inspection；`.VcInspect` | 尺寸测量、检验序列保存 | E-V09 documented-not-probed |
| VC-15 | 保存复查文件 | GUI 坐标 | `click(830, 108)`；`read_vcreview()` 解压 | 产出 `.vcreview`（Reviewer 9.6 ZIP，实测 227MB/25 条目） | E-V02 verified-working |
| VC-16 | 过程文件 | 命令行+菜单 | File → Save As (In-Process)；命令行 `ip=<file>` | `.ip` 会话快照免重跑 | E-V09 documented-not-probed |
| VC-17 | 几何输出 | GUI 坐标 | 输出面板 → 应用 `click(1576, 451)` | STP/STL/SOR 输出；历史路径误置 F:\ 未落盘，改可写目录即可 | E-V02 历史实测 |
| VC-18 | 事务审计读取 | API(python) | `read_transaction_log()` / `transaction_actions("ActionMainPlay")` | `%USERPROFILE%\cgtech_96_transaction.log` | E-V06 verified-working |
| VC-19 | 强制前置 | API(python) | `bring_vericut_front(hwnd)` | AttachThreadInput 链 + 最小化抢前台宿主 | E-V02 verified-working |
| VC-20 | 优雅关闭 | API(python) | `PostMessageW(hwnd, WM_CLOSE=0x0010, 0, 0)` | `close_vericut(hwnd, timeout=30)` | E-V02 verified-working |
| VC-21 | 工程静态解析 | API(python) | `parse_vcproject(path)` | 从 `.vcproject` 提取 units/machine/csys | E-V02 verified-working（部分字段） |
| VC-22 | 仿真日志监控 | API(python) | `monitor_log(path, interval=5, max_wait=300)` | 等新行/完成关键词后回读 | E-V02 verified-working |
| VC-23 | 几何转换器 | 命令行 bat | `E:\windows64\commands\dxf2sor.bat`（com.cgtech.DxfSorConverter） | DXF→SOR 几何转换 | E-V04 文件存在 documented-not-probed |
| VC-24 | 其他转换器 | 命令行 bat | `iges2v.bat` / `cad2v.bat` / `bincl2v.bat` / `sur2stk.bat` / `polyfix.bat` | 各 CAD/CLS→VERICUT 几何 | E-V04 文件存在 documented-not-probed |
| VC-25 | 官方 batch 语法 | 命令行 | `call vericut batch "vcp=setup1.VcProject" "ip=setup1.ai"` | 官方帮助记载的批处理写法；本机直传 vcp= 曾无效 | E-V09 documented-not-probed（与 E-V02 历史判死并列标注） |

## 键盘快捷键结论（E-V05）

- `KeyBinding.java`（javap 反编译 CGTech.jar，全量 `keybinding.txt` 落盘）：框架为 Swing `ActionMap/InputMap` + Flamingo `JRibbon`；存在 `escape`/`keytip`/`search`/`transformModeToggle` 等导航键。
- **关键结论：反编译确认界面无"播放(Play)"快捷键绑定** → 仿真播放只能真鼠标点击，这是 GUI 驱动路线的根因证据。
