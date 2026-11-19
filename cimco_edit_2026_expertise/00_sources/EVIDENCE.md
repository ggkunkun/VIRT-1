# 事实源与证据链（CIMCO Edit 2026 能力建设）

> 记录时间：2026-11-18。所有证据可复核，路径为绝对路径。

## A. 官方权威事实源（本轮实测抓取）

| 证据 ID | 内容 | 类型 | 位置 | 状态 |
|---|---|---|---|---|
| SRC-01 | CIMCO Edit 2026 官方手册全站 sitemap，检出 161 个英文 2026 页面 | 网络实测 | `https://docs.cimco.com/sitemap.xml` | 已抓取 |
| SRC-02 | 161 页手册正文全量语料，42.4 万字符 | 网络实测 | `00_sources/official_corpus.json` | 已落地 |
| SRC-03 | 可复跑抓取脚本（低并发+重试+正文定位） | 代码 | `00_sources/fetch_official.py` | 可复跑 |
| SRC-04 | 161 页 URL 清单 | 数据 | `00_sources/official_urls.json` | 已落地 |
| SRC-05 | 能力边界反证（add-on/version control/Huazhong/post process 关键词扫描） | 语料检索 | `00_sources/CAPABILITY_BOUNDARIES.md` | 已固化 |

语料章节分布：simulation 65、program-tabs 46、editor-setup 29、dnc-setup 11、introduction 3、其它 7。

## B. 本机安装事实源（实测）

| 证据 ID | 内容 | 类型 | 位置 |
|---|---|---|---|
| INS-01 | 主程序 CIMCOEdit.exe，30.8 MB，2026-03-23 | 文件实测 | `E:\仿真软件\CIMCOEdit_20260102\CIMCO 2026\CIMCOEdit\CIMCOEdit.exe` |
| INS-02 | 快捷方式 | 文件 | `C:\Users\Public\Desktop\CIMCO Edit 2026.lnk`（解析目标含 `CIMCOEdit_20260102\CIMCO 2026\CIMCOEdit`）|
| INS-03 | 实装计数（2026-11-18 精确复测，区分两种口径）：Posts **Mill 19 + Lathe 6 = 25 个 .js**（目录全部文件 30）；Templates **47 个 .TPL + 44 个 .TYP**（目录递归全部文件 326）；MachineCfg **86 个 .mcfg**（目录递归全部文件 509）；Converters 4 个 .conv；ToolLibs 14 个 .tmlib；Dll 97 个文件；Help 152 个文件（19 个 .chm）；RPost **34 个 .eRPost + 8 个 .eRPostExt = 42 个文件**；Samples 29 个 .nc；Tutorials 7 项 | 文件枚举 | `E:\...\CIMCOEdit\` |
| INS-04 | 方言过滤器 ncfilter_*.dll **27 个**（fanuc/siemens/heidenhain/mazak/okuma/deckel/fagor/...） | 文件枚举 | `E:\...\CIMCOEdit\Dll\` |
| INS-05 | RPost 控制器包 42 个文件（34 主包 + 8 扩展）：Fanuc/Siemens/Heidenhain/Haas/Mazak/Okuma/... | 文件枚举 | `E:\...\CIMCOEdit\RPost\` |
| INS-06 | 官方教程 PDF/MacBundle：ISO 编程教程、车铣复合教程、Haas Milling/ISO Milling MacBundle | 文件枚举 | `E:\...\CIMCOEdit\Tutorials\` |
| INS-07 | ConfigPaths.cfg：ROOTDIR=%APPDATA%... → CFG/DATA/MACHINES/TYPES/TOOLLIBS/... | 配置 | `E:\...\CIMCOEdit\ConfigPaths.cfg` |

## C. 既有工程资产（复用，历史实测）

| 证据 ID | 内容 | 位置 |
|---|---|---|
| ENG-01 | cimco_bridge.py：launch / validate_fanuc_macro_b / validate_gcode | `D:\Virtu模型\bridges\cimco_bridge.py` |
| ENG-02 | CIMCO 知识库底稿（modules/plugins/config/workflows/evidence 等 9 文档 560 行） | `D:\Virtu模型\knowledge_base\six_software\cimco\` |
| ENG-03 | CIMCO 训练/留出数据集（parser_verified 真实工具返回） | `D:\Virtu模型\data\sft\six_software_real_assets\cloud_pack\cimco_*.jsonl`（90 条）+ `knowledge_base\...\datasets\cimco_*.jsonl` |
| ENG-04 | 软件注册表 cimco=READY，能力 macro_b_validation/gcode_syntax_check/nc_transmission_prep/backplot | `D:\Virtu模型\bridges\software_registry.py` |
| ENG-05 | tool_calling_specs：cadcam_cimco_validate(validate_macro/launch) | `D:\Virtu模型\bridges\tool_calling_specs.py` |

## D. 证据使用规则

1. 所有操作手册/速查表/FAQ/案例的**菜单路径、参数名、快捷键**必须来自 SRC-02 语料或 INS-03 实装文件，逐条标注来源。
2. 凡涉及"校验通过"，必须附桥接原始返回（`status`/`syntax_checked`/`errors`）。
3. 拟人化指标（20 次实操、10 次零失误、98% 盲评）一律按 B-06 工程化替代，报告标明"工程自测"性质。
4. 不触碰 License.dll / 激活内部机制（既有 scope 硬边界）。
