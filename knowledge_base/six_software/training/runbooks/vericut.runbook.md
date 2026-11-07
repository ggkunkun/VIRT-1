# VERICUT 9.6 运行手册（runbook）

> 模型直接注入用操作基准。所有参数来自 `knowledge_base\six_software\vericut\`（commands.md / workflows.md / plugins.md / automation_api.md）。
> 通道状态三态：verified-working（历史实测）/ confirmed-negative / documented-not-probed。

## 0. 速查卡

| 项 | 值 |
| :-- | :-- |
| 安装根 | `E:\windows64`（CGTECH_INSTALL=E:\，CGTECH_PRODUCTS=E:\windows64） |
| 启动入口 | `E:\windows64\commands\vericut.bat` → `com.cgtech.Vericut` |
| 进程 | `vericut.exe` / `javaw.exe` |
| 版本 | 9.6 |
| 关键环境变量 | `CGTECH_VCPROJECT=<vcproject>`（自动加载工程）、`CGTECH_TRANSACTION_LOG=Yes`（审计日志 `%USERPROFILE%\cgtech_96_transaction.log`） |
| 关键文件 | 工程 .vcproject / 刀具库 .tls / 机器 .mch / 控制 .ctl / NC .nc/.cl / 复查 .vcreview / 日志 .log |
| COM/批处理 | **confirmed-negative**（6 ProgID Dispatch -2147221005；batchp/batcht 不可靠） |

## 1. GUI 操作路线（逐步可执行，坐标 @1920×1080）

### 任务 1：启动并自动加载工程 + 开审计
1. 设置环境变量 `CGTECH_VCPROJECT=<工程.vcproject>`、`CGTECH_TRANSACTION_LOG=Yes`。
2. 运行 `vericut.bat` → 窗口标题出现 `<工程名> (毫米)`。
3. 检查点：`%USERPROFILE%\cgtech_96_transaction.log` 生成。

### 任务 2：触发仿真播放
1. 定位播放按钮坐标 **(1890, 860)**，点击。
2. 检查点：BUSY 状态灯 **(710, 820)** 点亮；事务日志出现 `ActionMainPlay`。

### 任务 3：保存复查包
1. ribbon「保存复查文件」坐标 **(830, 108)**。
2. 输出 `.vcreview`（Reviewer 9.6 ZIP，含 NC/STL/ip/日志）。

### 任务 4：Auto-Diff 偏差判定
1. 输出面板应用坐标 **(1576, 451)**。
2. 颜色公理：**红=过切（致命，立即停机回 CAM 修刀路）、蓝=残料（补半精加工）、绿=合格**。

## 2. API/自动化路线（三态标注）

| 通道 | 调用 | 状态 |
| :-- | :-- | :-- |
| COM Dispatch | （6 个 ProgID） | **confirmed-negative**（勿用） |
| stdin IPC | 向 vericut 进程写命令 | **confirmed-negative** |
| 环境变量启动 | `CGTECH_VCPROJECT` + `vericut.bat` | verified-working |
| GUI 坐标点击 | 播放(1890,860)/保存复查(830,108)/应用(1576,451) | verified-working（历史） |
| 日志回读 | 解析 `*.log`（total_time/errors/warnings/tools/collisions） | verified-working |
| `.vcreview` 回读 | `vericut_link.read_vcreview()` ZIP 解压 | verified-working |
| batchp/batcht | 命令行批处理 | **confirmed-negative** |

## 3. 插件路线（见 plugins.md）

| 插件 | 启动 | 关键操作 | E-ID |
| :-- | :-- | :-- | :-- |
| ToolMan | `toolman.bat`（com.cgtech.toolman.ToolManager）/ 快捷方式 Vericut ToolMan 9.6.lnk | Tool Manager → Project → Tools → 定义刀具 → Save As .tls（按 Tool ID 存取） | E-V12 |
| Reviewer | `reviewer.bat`（com.cgtech.VericutReviewer） | 打开 .vcreview 回放 | E-V12 |
| Assembly Manager | `assembly_manager.bat`（com.cgtech.assemblyman.AssemblyManager） | 机床/附件装配组件管理 | E-V12 |
| VDAF/AutoFastener | `vdaf.bat`（com.cgtech.AutoFastener） | 钻铆仿真（与主工程不互通） | E-V12/E-V13 |
| OptiPath | 主程序内模块 | 配置 .olb 优化库 → 输出 .opti/.mco/.tpo | E-V09 |
| Force | 主程序内模块（E:\force_materials） | 切削力/功率/温度分析 | E-V01 |
| CME-API | .cme 经 Control Advanced 挂载 | `cmeapi_register_modify_output_str` 注册自定义输出（官方文档 E-V13） | E-V13 |
| Optimization API | 环境变量 `CGTECH_OPAPI=<优化库 DLL>` | 外挂优化插件 | E-V13 |
| 几何转换器 | `dxf2sor.bat`/`iges2v.bat`/`cad2v.bat`/`bincl2v.bat`/`sur2stk.bat`/`polyfix.bat` | 控制台转换 | E-V12 |

## 4. 常见故障与处置

| 现象 | 处置 |
| :-- | :-- |
| 仿真检出红色过切 | 立即停机，禁止下机；回 CAM 抬刀/补退刀/避让，重仿真至全绿（AGENTS.md §2.E） |
| Auto-Diff 蓝色残料 | 精加工前补一道半精加工 |
| 碰撞数 > 0 且去除体积异常 | 判定 NC 刀柄碰撞缺陷，回 CAM 修刀路 |
| 想用 COM 自动化 | 勿用——COM 已判死；走 bat + GUI 坐标 + 日志回读 |
| 想用 headless 批处理 | 勿用——batchp/batcht confirmed-negative |
