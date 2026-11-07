# VERICUT 9.6 知识库（CGTech 机床运动仿真 / 碰撞检测）

> 文档化逆向产物（reverse-skill offline-sample RE，auth.status=granted）。生成基准 2026-11-03。
> 本目录全部断言可回溯到 `evidence.md` 的 E-ID；通道状态三态：verified-working / confirmed-negative / documented-not-probed。

## 1. 软件身份表

| 项 | 值 |
| :-- | :-- |
| 显示名 | VERICUT 9.6 by CGTech（简体中文界面，CGTECH_LOCALE=chinese_simplified） |
| 版本 | 9.6（帮助站 help96；Reviewer 9.6 ZIP 容器） |
| 类别 | Kinematic Machine Simulation & Collision Detection（机床运动仿真 + 切削过程验证） |
| 安装根 | `E:\windows64`（CGTECH_INSTALL=`E:\`、CGTECH_PRODUCTS=`E:\windows64`）[高]（历史实测 E-V01） |
| 启动入口 | `E:\windows64\commands\vericut.bat` → `javaw --module-path javafx ... com.cgtech.Vericut` [高]（历史实测 E-V01） |
| 主程序 | `E:\windows64\jre\bin\javaw.exe`，主类 `com.cgtech.Vericut`；进程名 `vericut.exe`/`javaw.exe` |
| 桌面快捷方式 | `C:\Users\Public\Desktop\Vericut 9.6.lnk` |
| COM ProgID | **无可用 COM**（6 个候选 ProgID 全部判死，见 automation_api.md）[高]（历史实测 confirmed-negative） |
| 能力标签 | batch_simulation / autodiff_gouge_check / collision_detection / optipath_analysis |
| 六软件注册表状态 | READY（`bridges/software_registry.py` 已验证 6/6） |

## 2. 本目录文件清单

| 文件 | 用途 |
| :-- | :-- |
| `README.md` | 本文件：身份索引 + 阅读指南 |
| `modules.md` | GUI 功能模块树（按应用领域分块，中英文名 + mermaid） |
| `automation_api.md` | 自动化通道总表（三态判定）+ vericut.bat/环境变量/vericut_link.py 9 通道 |
| `commands.md` | 命令表：GUI 坐标化操作、bat 命令、转换器、键盘绑定结论 |
| `file_formats.md` | 原生/导入/导出格式（官方帮助站 URL 已核验） |
| `workflows.md` | 闭环工作流（蓝图→CAD→FEA→CAM→后处理→VERICUT 虚拟加工） |
| `config.md` | 配置/环境变量/事务日志/prefs 位置 |
| `module_inventory.json` | 机器可读模块清单（供模型训练，与 markdown 严格一致） |
| `evidence.md` | 证据链逐条声明 |

## 3. 模块树与自动化入口摘要

- 模块域：**工程配置（Project Tree）→ 机床/控制系统（Machine/Control）→ 仿真播放（Simulation Playback）→ 偏差分析（Auto-Diff/OptiPath/Force/X-Caliper）→ 复查（Reviewer）**。详见 `modules.md`。
- 自动化核心结论：VERICUT 9.6 **没有机器可读的程序化接口**（COM/stdin IPC/可靠 batch 全部判死），但存在两条可靠通道：
  1. **官方环境变量开关**（`CGTECH_VCPROJECT` 启动自动加载工程、`CGTECH_TRANSACTION_LOG=Yes` 操作审计）——见 `automation_api.md`；
  2. **桌面 GUI 驱动**（模板匹配 + 物理像素坐标点击，1920×1080 基准）+ 文件回读（仿真日志 `.log`、复查文件 `.vcreview` ZIP、`.vcproject` 静态解析）。
- 桥接实现：`D:\Virtu模型\work\vericut-toolchain\vericut_link.py`（9 通道封装）、`D:\Virtu模型\bridges\vericut_bridge.py`（碰撞日志解析）。

## 4. 供 Virtu 模型训练的使用说明

1. 先读本 README → 再读 `automation_api.md` 的通道总表（决定"能用什么驱动它"）→ `commands.md`（每个动作怎么复现）。
2. 训练驱动决策树：**能否走 bat 启动？** 能 → `launch_via_bat`；**能否无 GUI 跑仿真？** 不能（confirmed-negative）→ 必须 GUI 点击播放 + 日志回读。
3. 数值回读优先读 `force_turning_sample.log`（parse_sim_log）与 `.vcreview` 解压，不要依赖 UI 截图数值。
4. 颜色判读公理（对齐 AGENTS.md）：**红=过切（致命，停修刀路）、蓝=残料（加半精加工）、绿=合格**。
