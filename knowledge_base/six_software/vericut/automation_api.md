# VERICUT 9.6 自动化接口清单（通道三态判定）

> 状态语义：**verified-working**（本轮/历史实测可用）｜**confirmed-negative**（实测判死，勿重试）｜**documented-not-probed**（官方文档存在，本轮未复测）。
> 历史实测基准：2026-10-30/31 报告（`D:\Virtu模型\2026-10-30_逆向-VERICUT9.6-report.md`）；本轮（2026-11-03）执行栈仅 Read/Grep/Glob + 官方文档在线补充，**未现场复测任何运行时通道**。

## 1. 通道总表

| 通道 | 入口 / 路径 | 状态 | 证据 |
| :-- | :-- | :-- | :-- |
| COM 自动化 | 候选 ProgID：`Vericut.Application`、`.Application.9`、`CGTech.Vericut`、`Cgtech.Vericut.9`、Reviewer/Toolman/Assembly/Vdaf | **confirmed-negative** | E-V02（6 个 ProgID Dispatch 全失败 `-2147221005`） |
| stdin IPC | `OpenProject:/Simulate:/Step:` 管道输入 | **confirmed-negative** | E-V02（无响应） |
| UIA/JAB 控件树 | jabswitch /enable、UIA 枚举 | **confirmed-negative** | E-V03（只暴露 JOGL 视口，Swing/Flamingo 深树不可达） |
| Headless batch 可靠仿真 | `vericut.bat batchp/batcht` | **confirmed-negative（不可靠）** | E-V02（batchp 仅装载待命；batcht 20s 自退零产物） |
| bat 启动 + 官方开关 | `vericut.bat` / `vericut_agent.bat` | **verified-working** | E-V06（窗口标题自动含工程名；事务日志 ActionMainPlay 381 条） |
| 环境变量自动加载工程 | `CGTECH_VCPROJECT=<vcproject>` | **verified-working** | E-V06 |
| 操作审计日志 | `CGTECH_TRANSACTION_LOG=Yes` → `%USERPROFILE%\cgtech_96_transaction.log` | **verified-working** | E-V06（254KB+，动作类型符 `!/?/=/e/u`） |
| GUI 播放驱动 | 模板匹配 + 坐标点击 (1890,860) | **verified-working** | E-V02/E-V06（BUSY 灯亮、日志行号 20→44 推进） |
| 事务日志回读 | read_transaction_log() | **verified-working** | E-V06 |
| 仿真日志数值解析 | parse_sim_log(`.log`) | **verified-working** | E-V02（刀具/时间/错误95/去除体积/碰撞体积） |
| 复查文件 ZIP 回读 | read_vcreview(`.vcreview`) | **verified-working** | E-V02（227MB，25 条目） |
| 工程文件静态解析 | parse_vcproject(`.vcproject`) | **verified-working（部分）** | E-V02（单位/机床/坐标系命中；NC 程序/刀具库正则对当前 XML 未全命中） |
| 仿真日志实时监控 | monitor_log() | **verified-working** | E-V02 |
| 控制台几何转换器 | `dxf2sor.bat` 等 commands/*.bat | **documented-not-probed** | E-V04（文件存在；本轮未运行） |
| 官方 batch 语法 `vcp=/ip=` | `call vericut batch "vcp=...VcProject" "ip=....ai"` | **documented-not-probed** | E-V09（官方帮助描述；本机 CLI 直传 `vcp=` 曾判无效参数 E-V02） |
| CME-API / Vericut-COMMAND 记录 | `.cme` 宏、SAVE_IP/SAVE_VCT 命令记录 | **documented-not-probed** | E-V09 |

## 2. 启动与命令行（vericut.bat）

- 入口：`E:\windows64\commands\vericut.bat`（E-V01 逐行读过）。
- 尾部透传逻辑（bat 第 139-148 行）：
  ```text
  :cgtgetarg —— 逐个 %1 追加到 ARGSTR；若命中 BATCH 关键字 → 设 WAITOPT=/wait 且去除 splash
  ```
  即 bat 尾部参数原样透传给 `com.cgtech.Vericut`；`BATCH` 关键字会让启动器等待（`start "VERICUT" /wait`）并跳过 splash。
- JVM 命令（bat 第 162 行，等价于 vericut_link._javaw_cmdline）：
  ```text
  javaw -splash:...startup.png -Djogamp.gluegen.UseTempJarCache=false -Dsun.java2d.noddraw=true
    -XX:+UseG1GC -XX:+UseStringDeduplication -Xms256m -Xmx2g -Xss6m
    --module-path <PROD>\javafx\lib --add-modules javafx.swing,javafx.web
    --add-exports java.base/java.lang=ALL-UNNAMED ...
    -classpath E:\classes;E:\classes\CGTech.jar com.cgtech.Vericut [ARGSTR]
  ```
- 启动方式关键实测结论（E-V06）：必须 `cmd /c vericut_agent.bat`（**非 DETACHED**）才能同时起 GUI 并写事务日志；`DETACHED_PROCESS` 无交互窗口站起不了 GUI；直接 javaw 启动时 VCPROJECT 生效但 TRANSACTION_LOG 不写——**事务日志必须走 bat**。

## 3. 环境变量（bat 注释区官方开关，E-V01/E-V06）

| 变量 | 作用（官方注释原文转述） | 本机实测 |
| :-- | :-- | :-- |
| `CGTECH_INSTALL` / `CGTECH_PRODUCTS` | 安装根定位 | 必设：`E:\` / `E:\windows64` |
| `CGTECH_VCPROJECT` | 启动时自动加载指定 VcProject | ✅ 窗口标题=`9.6 by CGTech - <工程名> (毫米)` |
| `CGTECH_TRANSACTION_LOG=Yes` | 用户动作写入 `cgtech_96_transaction.log` | ✅ ActionMainPlay 381 条 |
| `CGTECH_IGNORE_LAST=TRUE` | 不加载上次工程，用标准启动文件 | documented-not-probed |
| `CGTECH_DEFAULT_UNITS=MILLIMETER` | 默认单位毫米 | 默认已设 |
| `CGTECH_LOCALE=chinese_simplified` | 简体中文界面 | 默认已设 |
| `CGTECH_MACHINE_CONFIG=FALSE` | 隐藏机床配置菜单/功能 | documented-not-probed |
| `CGTECH_COMPRESS=NO/IP/VCT/ALL` | IP/VCT 文件压缩策略 | documented-not-probed |
| `CGTECH_TPEDITOR=<exe>` | 外挂 NC 程序编辑器 | documented-not-probed |
| `CGTECH_USERNAME=<string>` | prefs 文件名 `cgtech_96_<string>.prefs` | documented-not-probed |
| `CGTECH_OPAPI=<OptiPath DLL>` | OptiPath 外挂库 | documented-not-probed |
| `CGTECH_NC_PROGRAM_ENCODING=windows-1252` | NC 程序双字节显示异常时切换编码 | documented-not-probed |
| `CGTECH_VA_SHOW=TRUE` | 开关 Vericut AI | 默认 TRUE |
| `LSHOST` | 许可证服务器主机名 | bat 经 `cgtenv` 设置（许可证相关不展开，属 out-of-scope） |

> 事务日志动作类型符（vericut_link 注释）：`!`=action request、`?`=get value、`=`=set value、`e`=list、`u`=update；已知动作名 `ActionInit`、`TP_GET_NC_*`、`ActionMainPlay`。

## 4. 既有桥接实现（接口证据）

### 4.1 `D:\Virtu模型\work\vericut-toolchain\vericut_link.py`（9 通道，实测可运行）

```python
# 常量锚点（物理像素，1920x1080 全屏基准；E-V02/E-V03）
PLAY_BUTTON        = (1890, 860)   # 播放按钮中心（绿色三角模板匹配 1872,838 → 中心）
SAVE_REVIEW        = (830, 108)    # ribbon「保存复查文件」
OUTPUT_PANEL_APPLY = (1576, 451)   # 输出面板「应用」
STATE_LAMP_BUSY    = (710, 820)    # BUSY 状态灯（绿色像素检测）

launch_via_bat(project, transaction_log, wait_sec=45) -> pid
launch_direct(project, wait_sec=45) -> pid
bring_vericut_front(hwnd)          # AttachThreadInput 链 + 最小化抢前台宿主
play_simulation(hwnd, coord)       # -> (ok, evidence{ActionMainPlay})
read_transaction_log(tail) / transaction_actions("ActionMainPlay")
parse_sim_log(path) -> {total_time, errors, warnings, tools[], removal_volumes[], collision_volumes[]}
read_vcreview(path, outdir) -> {name: abs_path}   # zipfile 解压 Reviewer 9.6 容器
parse_vcproject(path) -> {units, machine, csys, nc_programs[], tool_library[]}
monitor_log(path, interval, max_wait, stop_kw) -> parse_sim_log 结果
full_cycle(project, log_path, hwnd)
```

关键局限（E-V02 §8.4）：`parse_vcproject` 的 NC 程序/刀具库正则未命中当前 XML 结构（字段待现场确认）；`parse_sim_log` 错误计数已排除"在NN行"行号干扰。

### 4.2 `D:\Virtu模型\bridges\vericut_bridge.py`

```python
VericutBridge.run_batch_simulation(project_path, log_output_path)
  # -> {"status": "unsupported_headless"}  明确不再假装 headless batch 可用（E-V02 结论）
VericutBridge.parse_collision_log(log_path)
  # -> {collision_count, error_count, warning_count, collisions[], errors[], warnings[], is_safe}
  # 双语（中文 CGTECH_LOCALE / 英文）识别：碰撞/过切/collision/gouge 单独计数，
  #   错误/警告分类排除碰撞行，is_safe = (collision_count == 0)
```

### 4.3 强制前置套路（宿主抢前台时，E-V02 §6）

```text
AttachThreadInput(ct, ft, True) + ShowWindow(SW_RESTORE) + BringWindowToTop
+ SetForegroundWindow + SetActiveWindow + SetWindowPos(HWND_TOP) + detach + sleep 0.6~0.8
```

## 5. 结论性判定

VERICUT 9.6 = **「无程序化接口，但可桌面驱动 + 文件回读」**：Agent 应以 `launch_via_bat` 起工程 → `play_simulation` 触发仿真 → `parse_sim_log`/`read_vcreview` 回读数值 → `parse_collision_log` 判 is_safe。坐标会随窗口位置漂移，每次须原子截图 + OCR 校准。
