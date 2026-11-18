# VERICUT 9.6 高级应用场景手册

> 扩充文档（2026-11-18）。覆盖四大高级场景：**自定义机床运动逻辑 / 后处理输出匹配与优化 / 多工序联动连续仿真 / 主流 CAD-CAM 接口对接**。每场景给出可落地的配置流程与验证方法，明确**输入要求 → 配置步骤 → 输出结果 → 有效性校验**。
> **证据纪律**：本机已装/已见文件的项标 `[高]`（存在性）或 `[中]`（未运行）；官方帮助站推导项标 `documented-not-probed`；绝不臆造实测结果。**许可证/激活机制全程 out-of-scope**（CAD Model Interface 等只说"需对应许可"，不展开）。
> **版本纪律**：接口 bat 版本族（NX 至 2412、Mastercam 2023/2024/2025 等）来自本机 `E:\windows64\commands\` 文件名（E-V04/V12），是 9.6 安装自带的接口启动器；不引用其他 VERICUT 版本功能。

---

## 场景 A：自定义机床运动逻辑配置

### A.1 适用与目标
为非常规机床（多轴/双转台/机器人/车铣复合）建立精确运动学，使 NC 代码驱动的机床运动与真机一致，碰撞检测可信。

| 项 | 内容 |
| :-- | :-- |
| 输入要求 | 机床组件几何（STEP/STL/`.vct`）、轴配置清单（线性/旋转轴、行程、旋转中心）、NC 程序、Control 文件 |
| 输出结果 | 可复用 `.mch`（或加密 `.xmch`）机床文件，组件关联与运动链正确 |
| 有效性校验 | 仿真中组件按预期联动；无虚假碰撞；刀尖位与 NC 指令一致 |

### A.2 配置流程（分步）

| 步 | 操作 | 输入 | 输出 | 校验方法 |
| :-- | :-- | :-- | :-- | :-- |
| A2.1 | 用 `bwizard.bat`（`com.cgtech.BWizard`）装配向导或手工建 Machine 组件树 | 机床组件几何 | 组件层级（Base→X→Y→Z→主轴/转台） | 组件树完整、无悬空 |
| A2.2 | 为每个 Component 指定几何模型并定位（Position/Rotate） | STL/STEP/SOR/SWP/VCT | 装配后的机床 3D | 视图中机床形态正确 |
| A2.3 | 定义 Component Associations（父子/关联）与运动轴类型 | 轴配置清单 | 运动链（kinematic chain） | 单轴手动移动验证方向正确 |
| A2.4 | 设行程限位与旋转中心（超程预警基础） | 行程/中心数据 | 限位参数 | 超程时报警（对应 error_handbook E-R/超程） |
| A2.5 | 配置 Machine Initialization File（如需初始化变量） | 初始化脚本 | 变量初值 | 事件"Start of Processing"时变量正确（E-V14） |
| A2.6 | 用 Control 文件把 NC 轴指令映射到机床轴 | `.ctl` | 轴映射 | 程序走刀方向与机床一致 |
| A2.7 | Save `.mch`；需要分发时生成 `.xmch`（内嵌模型、禁改配置） | — | `.mch/.xmch` | 重新加载后运动链保持 |

### A.3 证据与边界
- `.mch` 为 XML 描述机床构造/运动学/属性；`.xmch` 加密 X-File 内嵌引用模型并禁 Configuration tab：官方原文 `[中]`（E-V14）。
- 装配向导 `com.cgtech.BWizard`、组件资源库 `VTPD.db` 存在：`[高]`（存在性 E-V12/E-V01）；**本机未实跑装配向导** → 步骤细节 `documented-not-probed`。
- 进阶：CME-API（`.cme`）可自定义 G 代码处理与 modals，经 Control Advanced Option → CME/API 挂载（E-V13，官方 `[中]`）。

---

## 场景 B：后处理输出匹配与优化

### B.1 后处理身份链（关键概念）
VERICUT 侧"后处理"有两层含义，须区分（避免跨概念误导）：
1. **Post Processor File（`.VcPost`）**：VERICUT Post Processor 创建的 ASCII 文件，把"机床无关的 NC 数据"转换为"特定机床/控制组合的 G 代码"（官方定义 E-V14 `[中]`）。
2. **Control 文件（`.ctl`）**：描述控制器如何**解释** G 代码——VERICUT 仿真所需，决定刀路能否被正确执行。
> 关系：CAM 后处理产出 `.nc` → VERICUT 用 `.ctl` 解释它；若 CAM 输出机床无关 CLS/APT，可经 `.VcPost` 转成目标机床 G 代码再仿真。

### B.2 配置流程（匹配校验）

| 步 | 操作 | 输入 | 输出 | 校验方法 |
| :-- | :-- | :-- | :-- | :-- |
| B2.1 | 确认 NC 来源：G 代码（`.nc/.mcd`）或 CLS/APT（`.tp/.cl`） | CAM 输出 | 类型判定 | NC Program Type 选 G-Code Data 或 APT-CLS 变体 |
| B2.2 | 选/建 Control 文件匹配控制器（FANUC/SIEMENS/Heidenhain 等） | 控制器型号 | `.ctl` | Control Report `.rpt` 覆盖程序全部 G 代码/宏（E-V14） |
| B2.3 | 若需格式转换，用 `.VcPost` 配置机床/控制组合 | 机床无关 NC | 目标 G 代码 | 输出代码语法正确、轴地址匹配 |
| B2.4 | `Analysis > Perform Syntax Check` + G-Code Log 对照 | NC 程序 | 转换对照 | G-Code Log 中"输入块 vs APT 记录"合理（E-V14） |
| B2.5 | 试跑最小程序，核对刀尖位/进给/换刀 | 程序+机床+刀具 | 仿真刀路 | 与设计模型位置一致、无异常报警 |

### B.3 OptiPath 进给优化

| 项 | 内容 |
| :-- | :-- |
| 输入 | 优化库 `.olb`（按刀具/材料/机床定义进给数据）、Tool Manager 里配好优化属性的刀具 |
| 配置 | `Optimize/OptiPath` 选项卡 → Optimize Control 设 Material/Machine/库文件 → 开启优化（E-V14 `[中]`） |
| 输出 | `.opti`/`.mco`（G 代码）/`.tpo`（APT）优化后程序（E-V09 `[高]`，文件格式官方） |
| 校验 | 优化后程序重跑仿真无过切/碰撞、加工时间合理；`.olb` 数据覆盖所用刀具 |
| 外挂 | `CGTECH_OPAPI=<优化库 DLL>` 切 API 模式接自定义优化，内置优化停用（E-V13 `[中]`） |
| 边界 | 本机未运行 OptiPath → 全流程 `documented-not-probed` |

### B.4 校验清单（有效性）
- [ ] Control Report 覆盖程序所有 G 代码与宏
- [ ] Syntax Check 通过
- [ ] G-Code Log 转换对照正确
- [ ] 优化后（如启用）刀路无过切/碰撞

---

## 场景 C：多工序联动连续仿真

### C.1 两种连续仿真机制

| 机制 | 文件 | 启动方式 | 适用 |
| :-- | :-- | :-- | :-- |
| Operations 文件装配多 Setup | `.ops` / `.vctmp`（临时） | **仅命令行** | 把多个 `.VcProject`（各含一个 Setup）装配成连续工序链（E-V14 `[中]`） |
| 已切削实体复用 | `.vct` | 工程内引用 | 把上一工序的 Cut Stock 实体作为下一工序毛坯/夹具/Design（含 Constant Gouge Check 设计模型）（E-V14 `[高]`） |

### C.2 配置流程（Operations 多 Setup）

| 步 | 操作 | 输入 | 输出 | 校验方法 |
| :-- | :-- | :-- | :-- | :-- |
| C2.1 | 为每个工序建独立 `.VcProject`（各自 Setup/NC/刀具/模型） | 工序工艺卡 | N 个工程文件 | 单工程各自可独立仿真通过 |
| C2.2 | 编写 `.ops` 文本：每行引用一个工程，声明从前序传递的信息 | 工程路径+传递声明 | `.ops` 文件 | 文本每行独立、引用路径有效（E-V14） |
| C2.3 | 命令行启动 Vericut 载入 `.ops`（无独立选项卡） | `.ops` | 装配的多 Setup 会话 | 成功载入、工序顺序正确 |
| C2.4 | 逐工序仿真，核对工序间毛坯继承 | 装配会话 | 连续加工结果 | 后工序毛坯=前工序切削后实体 |
| C2.5 | 全程碰撞/Auto-Diff 检查 | — | 安全判定 | 每工序 `is_safe`、Auto-Diff 合格 |

### C.3 配置流程（VCT 实体接力，工程内）

| 步 | 操作 | 校验 |
| :-- | :-- | :-- |
| C3.1 | 工序 1 仿真后导出 Cut Stock 为 `.vct`（默认压缩） | 文件落盘、可加载 |
| C3.2 | 工序 2 把该 `.vct` 设为 Cut Stock（毛坯） | 毛坯形状=工序1结果 |
| C3.3 | 工序 2 可把它同时设为 Design 做 Constant Gouge Check | 恒定余量检查有效 |
| C3.4 | 重跑工序 2 | 无过切、残料符合预期 |

### C.4 边界与校验
- `.ops` 只能命令行启动、每行引用一个工程：官方原文 `[中]`（E-V14）；本机未实跑 → `documented-not-probed`。
- IP 文件（`.ip`）用于**备份/续跑**单会话（含已切削模型+UI+日志），跨计算机类型不可移植（E-V14 `[高]`）。
- 多工序 Auto-Diff 注意：本报告行为——Comparison Type=Both 时同时有过切+残料**优先报过切**（E-V15）。

---

## 场景 D：主流 CAD/CAM 接口对接与数据交互

### D.1 接口启动器清单（本机 9.6 安装自带，E-V04/V12）

| 系统 | 接口 bat（在 `E:\windows64\commands\`） | 状态 |
| :-- | :-- | :-- |
| UG / NX | `nx_export.bat`、`nx12_2vdaf.bat`、`nx_cr_*.bat`（至 2412） | 存在 `[高]`，未运行 |
| Mastercam | `mastercam*.bat`（2023/2024/2025） | 存在 `[高]`，未运行 |
| PowerMILL | `powermill.bat` | 存在 `[高]`，未运行 |
| CATIA V5/V6 | `catv5.bat`、`catv6_3dx*.bat`（2019–2025）、`catv6_3dxml*.bat` | 存在 `[高]`，未运行 |
| Pro/E (Creo) | `proev.bat` | 存在 `[高]`，未运行 |
| Gibbs / Esprit / Edgecam | `gibbsv.bat` / `esprit.bat` / `edgecam.bat` | 存在 `[高]`，未运行 |
| Teamcenter / Zoller 对刀仪 | `cgt_teamcenter.bat` / `cgt_zoller.bat` | 存在 `[高]`，未运行 |
| 几何转换（中性） | `dxf2sor`/`dxf2sweep`/`iges2v`/`cad2v`/`bincl2v`/`sur2stk`/`polyfix` | 存在 `[高]`，未运行 |

### D.2 数据交互规范（两条路线）

**路线 1：专用接口（推荐，需对应许可）**
从对应 CAM 环境内经接口 bat 启动 VERICUT，直接读取该 CAM 的刀路/模型。
- 输入：CAM 原生刀路/模型 + 对应 CAD Model Interface 许可（**许可细节不展开**）。
- 注意：不同产品工程不互通（如 VDAF 工程与 VERICUT 主工程不能互用，E-V13/V12）。

**路线 2：中性格式交换（通用兜底，本机最稳）**
| 数据 | 中性格式 | VERICUT 载入方式 | 校验 |
| :-- | :-- | :-- | :-- |
| 刀路（G 代码） | `.nc/.mcd` | NC Programs + G-Code Data | Syntax Check + G-Code Log |
| 刀路（CLS/APT） | `.tp/.cl` | NC Program Type=APT-CLS | 刀路轨迹预览 |
| 设计/毛坯几何 | STEP(`.stp`)/STL(`.stl`)/IGES(`.igs`)/ACIS(`.sat`) | Configure Model → Model 选项卡 | STL 水密/法向一致；IGES 跑一致性检查 |
| 回转体 | DXF→`.sor`（`dxf2sor`） | Model 选项卡 | 轮廓绕 Z 旋转正确 |
| NX 原生件 | `.prt` | 需 NX Model Interface 许可直接打开 | 许可具备时可用（不展开许可） |

### D.3 配置流程（以中性格式兜底为例）

| 步 | 操作 | 输入 | 输出 | 校验方法 |
| :-- | :-- | :-- | :-- | :-- |
| D3.1 | CAM 侧导出刀路为 `.nc`（G 代码）或 `.tp`（APT-CLS） | CAM 刀路 | NC 文件 | 格式正确、无残缺 |
| D3.2 | CAM 侧导出设计/毛坯为 STEP 或 STL | CAD 模型 | 几何文件 | STL 水密、法向一致（E-V14） |
| D3.3 | 需要时转换：`dxf2sor`/`iges2v`/`cad2v` | DXF/IGES/SAT | VERICUT 几何 | 转换后可在 Model 选项卡加载 |
| D3.4 | VERICUT 侧：设 Control → 加 NC → 加模型 → 加刀具（SOP-2~4） | 上述文件 | 配置好的工程 | 各分支引用有效 |
| D3.5 | `Analysis > Perform Syntax Check` + 试跑 | — | 仿真结果 | 刀路与设计对齐、无碰撞 |
| D3.6 | 特殊编码/多字节问题 | 乱码程序 | — | `CGTECH_NC_PROGRAM_ENCODING`（E-V01，未实测） |

### D.4 有效性校验总则
1. **刀路一致性**：NC Program Preview 轨迹与设计模型位置合理。
2. **几何一致性**：Model 可加载为实体、Auto-Diff 可比较。
3. **安全一致性**：`parse_collision_log.is_safe=True`、Auto-Diff 三色自洽。
4. **接口可用性**：若专用接口不通，退到中性格式路线（本行是本机已验证资产的路径——文件级导入）；专用接口一律 `documented-not-probed`。

---

## 场景 E：跨场景通用验证门（Agent 输出前自检）

| 门 | 检查 | 失败处理 |
| :-- | :-- | :-- |
| 版本门 | 所用功能是否 9.6 具备（查 `version_consistency.md`） | 剔除跨版本功能 |
| 证据门 | 每条断言是否有 E-ID / 三态标注 | 无证据不写 |
| 安全门 | 碰撞/过切是否已排除（is_safe + Auto-Diff） | STOP_AND_FIX |
| 许可门 | 是否触碰授权/激活机制 | 立即停止该内容 |
| 通道门 | 是否误用已判死通道（COM/IPC/UIA/batch） | 改 GUI + 文件回读 |

> 任何高级场景的最终回答，必须同时通过这五门才可向用户输出。
