# SSCNC 7.2 自动化接口清单（通道三态判定）

> 状态语义：**verified-working**（历史桥接/本进程已验证）｜**confirmed-negative**（判死）｜**documented-not-probed**（存在但本轮未复测）。
> 本轮（2026-11-04）执行栈仅 Read/Grep/Glob + 官方文档在线补充，未现场启动 GUI；运行时判定全部复用既有桥接与注册表结论。

## 1. 通道总表

| 通道 | 入口 / 路径 | 状态 | 证据 |
| :-- | :-- | :-- | :-- |
| COM 自动化 | 无注册 ProgID（software_registry `com_prog_id=None`） | **confirmed-negative** | E-S07（注册表代码 + 全目录无 COM 类型库） |
| 命令行拉起登录器 | `subprocess.Popen([CNCLogin.exe], cwd=安装目录)` | **verified-working（历史桥接）** | E-S05（sscnc_bridge.launch） |
| 命令行直拉控制器仿真器 | `...\FANUC\FANUC0iT\sscnc.exe` 等每控制器 exe | **documented-not-probed** | E-S02（exe 文件存在已 Glob；未运行） |
| 窗口句柄枚举 | `win32gui.EnumWindows` 按标题「斯沃/SSCNC/FANUC/ClassName_CCCStartDlg」 | **verified-working（历史桥接）** | E-S05（find_window 实现） |
| 面板按键自动化（AUTO/EDIT/MDI/JOG/cycstart 点击） | 物理面板位图按钮 | **documented-not-probed** | 无实测；AGENTS.md 公理要求人工/键鼠驱动 |
| 对刀软键操作（[坐标系][测量]、[补正][形状]） | 面板软键 | **documented-not-probed** | E-S06（官方说明书给出手工步骤，无脚本通道） |
| 对刀偏移离线计算 | `calculate_tool_offsets(tools)` | **verified-working（纯计算，无需 GUI）** | E-S05 |
| DNC/网络服务 | `SERVER\ssFtp.exe` / `ssHttp.exe` / `SSCNCSrv.exe` | **documented-not-probed** | E-S01（文件存在） |
| 配置文件直接编辑 | `config.ini` / `Model\spec.ini` / `offset.dat` | **documented-not-probed** | E-S04（文件已读取结构） |

## 2. 既有桥接实现（`D:\Virtu模型\bridges\sscnc_bridge.py`，接口证据）

```python
SSCNC_EXE = r"E:\仿真软件\2斯沃7.2（内含安装说明）\SSCNC\CNCLogin.exe"

class SSCNCBridge:
    # 启动
    launch() -> {"status":"launched"|"error", "path":...}
        # subprocess.Popen([SSCNC_EXE], cwd=dirname)
    # 窗口发现
    find_window() -> {"status":"found"|"not_running"|"error", "hwnd":..., "title":...}
        # EnumWindows + IsWindowVisible + 标题含 "斯沃"/"SSCNC"/"FANUC"
    # 对刀偏移计算（核心可复用算法）
    calculate_tool_offsets(tools: list) -> {"status":"success","wcs_target":"G54","offsets":[...]}
        # 每个 tool = {tool_num, type, x, z, r(=0.8), quadrant, desc}
        # 返回 offsets 行：
        #   tool_code   = f"T{tool_num:02d}{tool_num:02d}"   # FANUC 刀补号 Tnnnn
        #   geometry_x  = x_val    # 形状补正 X
        #   geometry_z  = z_val    # 形状补正 Z
        #   nose_radius_r = r_val  # 刀尖圆弧半径 R
        #   quadrant_t    = quadrant  # 刀位象限 T：3=外圆车削, 2=内孔镗孔, 8=螺纹
```

### 2.1 桥接局限（如实声明）

1. **launch() 只启动登录器 CNCLogin.exe，不自动完成「选控制器→选机床型号→进面板」**——后续 GUI 交互无代码覆盖。
2. **find_window() 依赖 win32gui**；若 `pywin32` 缺失则返回 `HAS_WIN32=False` 错误（桥内已 try/except）。
3. **calculate_tool_offsets() 是纯计算**，不写入仿真器 `offset.dat`，也不点击面板软键——产出的是「应输入的补正值」清单，需操作员/键鼠自动化录入面板。
4. 桥内样例：T1 外圆粗车 (x=120.5,z=45.2,r=0.8,quadrant=3)、T2 切槽切断 (r=0.2)、T3 螺纹 (quadrant=8)。

## 3. 结论性判定

SSCNC 7.2 = **「无 COM/无脚本 API，但进程可拉起、窗口可枚举、对刀量可离线算」**。Agent 若要闭环操作面板，须在桥接之上叠加桌面键鼠自动化（对坐标化面板按钮点击），本轮无实测证据，标注 documented-not-probed；数值准备（刀补/象限/程序）可完全离线完成。
