# VERICUT 9.6 版本一致性校验与跨版本差异排除

> 扩充文档（2026-11-18）。目的：确保所有知识内容 **100% 匹配 VERICUT 9.6**，严格排除其他版本功能差异，所有内容经版本一致性交叉校验后方可纳入。
> **核心风险**：官方在线帮助站 `help.vericut.com` 是**跨版本滚动文档**（本轮抓取样本中出现 9.7.1 Prefs 命名示例、以及 VDAF 帮助站混入的条目）。因此本知识库把"官方通用文档"与"9.6 本机证据"分开，凡未被 9.6 本机证据确认的官方项一律降级为 `documented-not-probed`、`[中]`，绝不当作 9.6 专属已验证事实。

---

## 1. 版本身份锚点（9.6 专属，不可混淆）

| 锚点 | 9.6 实测值 | 证据 | 置信度 |
| :-- | :-- | :-- | :-- |
| 显示名 | `9.6 by CGTech`（窗口标题） | E-V06（标题实测） | `[高]` |
| 版本标识 | help96；Reviewer 9.6 ZIP 容器 | E-V01/E-V02 | `[高]` |
| 安装根 | `E:\windows64`（`CGTECH_INSTALL=E:\`、`CGTECH_PRODUCTS=E:\windows64`） | E-V01（bat 逐行） | `[高]` |
| 主程序 | `E:\windows64\jre\bin\javaw.exe`，主类 `com.cgtech.Vericut` | E-V01 | `[高]` |
| 界面语言包 | `E:\classes\lang\chinese_simplified`（简体中文） | E-V01 | `[高]` |
| prefs 命名 | `cgtech_96_<user>.prefs`（版本号 **96**） | E-V01 | `[高]` |
| 事务日志 | `%USERPROFILE%\cgtech_96_transaction.log`（版本号 **96**） | E-V01/E-V06 | `[高]` |
| 快捷键框架 | Swing ActionMap/InputMap + Flamingo JRibbon；无 Play 绑定 | E-V05（javap 反编译） | `[高]` |

> **判定法则**：任何声称是 9.6 的功能/路径，若与上述锚点冲突（如 prefs 名含 `97`、安装根在 `Program Files\Vericut 9.x`、存在 COM 接口），即为跨版本污染，必须剔除。

---

## 2. 跨版本差异排除清单（严禁混淆项）

| 易混淆项 | 错误归属（其他版本/泛化） | 本知识库 9.6 口径 | 依据 |
| :-- | :-- | :-- | :-- |
| Prefs 文件命名 | 官方抓取样本出现 `cgtech_9x_user.prefs` / 9.7.1 示例 | 9.6 为 `cgtech_96_<user>.prefs` | E-V01 `[高]` 覆盖官方泛化 |
| 官方帮助站内容 | `help.vericut.com` 滚动更新到更新版本 | 只作"通用文档"，功能是否存在以 9.6 bat/安装/实测为准 | 本轮抓取观察 |
| COM 自动化 | 泛化资料称"VERICUT 有 COM/ActiveX" | 9.6 本机 6 ProgID 全判死 `-2147221005`，confirmed-negative | E-V02 `[高]` |
| UIA/JAB 控件树 | 泛化自动化资料假设可读控件 | 9.6 Swing/Flamingo 深树不暴露，只 JOGL 视口 | E-V03 `[高]` |
| Headless batch | 官方 batch 文档暗示可靠无人值守 | 9.6 本机 batchp 待命/batcht 自退零产物，confirmed-negative | E-V02 `[高]` |
| 安装路径 | 泛化 `C:\Program Files\Vericut [version#]` | 本机 `E:\windows64` | E-V01 `[高]` |
| VDAF 工程互通 | 泛化认为 VERICUT 各产品工程通用 | VDAF 工程与 VERICUT 主工程不互通；`.VcProject` 跨产品不通用 | E-V13/E-V14 `[中]` |
| 接口 bat 版本族 | 把其他版本接口号当 9.6 | 9.6 自带接口文件名为本机 `commands\` 实际存在者（NX 至 2412、Mastercam 2023/2024/2025 等） | E-V04/V12 `[高]`（存在性） |

---

## 3. 交叉校验方法与记录（本轮 2026-11-18）

### 3.1 校验方法
1. **双源比对**：每条功能点同时查 ①官方帮助站（`help.vericut.com`）②9.6 本机证据（bat/安装文件/反编译/历史实测）。
2. **本机优先**：两源冲突时以 9.6 本机证据为准（如 COM、prefs 命名、安装路径）。
3. **降级规则**：仅官方有、本机无证据 → `documented-not-probed`、`[中]`；本机判死 → `confirmed-negative`。
4. **不臆造**：默认值/参数若无任何来源支撑，写"依工程/以界面为准"，不编造数字。
5. **许可隔离**：CAD Model Interface、OptiPath、AUTO-DIFF 等"需许可"项只陈述功能与存在性，不展开授权机制。

### 3.2 本轮抓取记录（E-V14/E-V15）

| E-ID | 来源 URL | 抓取内容 | 版本校验处理 |
| :-- | :-- | :-- | :-- |
| E-V14 | `https://help.vericut.com/4_vericut_help/2.3_vericut_file_descriptions` | 全量文件类型与扩展名（`.VcProject/.mch/.ctl/.tls/.ip/.vct/.sor/.swp/.rpt/.olb/.VcPost/.VcInspect/.cme/.ops/.prefs/.sub/.pts` 等）及定义 | 标注"官方通用文档"；与 9.6 本机 bat/样本交叉核对后才升 `[高]`（如 `.tls/.ip/.mch` 已被 E-V09 本机/官方双证）；`prefs` 命名样本含非 9.7 示例→不采信，用 E-V01 的 `cgtech_96_` |
| E-V14 | `https://help.vericut.com/4_vericut_help/2.2_working_with_vericut_files` | 默认启动文件、New Project 初始化文件、引用查找顺序、`CGTECH_VCPROJECT`、`vcp=/ip=/auto-diff=/optimize` batch 语法 | `CGTECH_VCPROJECT` 命中 E-V06 本机实测→`[高]`；batch 语法本机未复现→`[中]` + confirmed-negative 并列 |
| E-V15 | `https://help.vericut.com/4_vericut_help/7.01_auto_diff_window` | AUTO-DIFF 参数（Gouge/Excess Tolerance、Check Distance、Default Normal、Normal Direction、Comparison Type=Both 优先报过切、Profile/Solid 公差独立、Design Consistency Check、Include Tool to Stock Collisions） | 官方原文 `[高]`（参数语义）；本机未现场跑 Auto-Diff→运行态 `documented-not-probed`，三色判定以 AGENTS §2.E + skill 为准 |
| E-V15 | `https://help.vericut.com/4_vericut_help/7.0_analysis_tab` | Analysis 选项卡功能（Perform Syntax Check、NC Program Preview/Review、AUTO-DIFF、Comparator、Display Tool to Stock Collisions） | 与 9.6 本机菜单名交叉核对一致→`[高]`/官方 |

> 404 记录：`https://help.vericut.com/4_vericut_help/` 目录页本轮返回 404，未采信其内容。

### 3.3 校验通过清单（本扩充文档 5+ 文件）
| 文档 | 版本校验结论 |
| :-- | :-- |
| `ui_reference.md` | §7 小结：界面骨架双源核对；默认值不臆造；官方泛化项降级 ✓ |
| `sop_library.md` | `[实测]`/`[文档]` 分标；判死通道不写进正常 SOP ✓ |
| `error_handbook.md` | 每场景带证据；判死类给换通道解法 ✓ |
| `advanced_scenarios.md` | 接口版本族用本机文件名；许可不展开 ✓ |
| `problem_kb.md` | 四段式输出含版本路由；默认值不臆造 ✓ |
| 本文件 | 建立锚点 + 排除清单 + 校验记录 ✓ |

---

## 4. Agent 版本一致性自检清单（输出前必过）

- [ ] **锚点一致**：所用路径/命名/界面与 §1 的 9.6 锚点不冲突。
- [ ] **排除清单**：未把 §2 任一"错误归属"当 9.6 功能。
- [ ] **证据标注**：关键断言有 E-ID 与 `[高]/[中]/[低]` 或三态。
- [ ] **官方泛化降级**：仅官方有、本机无证据的项已标 `documented-not-probed`。
- [ ] **默认不臆造**：无来源的默认值写"依工程/以界面为准"。
- [ ] **判死不翻案**：COM/IPC/UIA/batch 保持 confirmed-negative。
- [ ] **许可隔离**：未触碰授权/激活机制。

---

## 5. 结论
本知识体系的全部内容以 **9.6 本机证据（E-V01~V13）为最高优先级**，官方滚动帮助文档（E-V14/V15）仅作补充并按需降级；经 §3 双源交叉校验、§4 输出前自检，确认**无跨版本功能混淆、无版本适配错误**。凡本机未复测项均如实标注，供后续会话复测后升级置信度——**不以推断冒充实测**。
