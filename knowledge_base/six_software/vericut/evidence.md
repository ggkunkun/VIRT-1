# VERICUT 9.6 证据链（Evidence）

> 规则：每条关键断言都可回溯到下表 E-ID；本轮（2026-11-03）执行栈为 Read/Grep/Glob + 官方文档在线补充，**未现场复测任何运行时通道**——历史实测项标注「历史实测」并复用 2026-10-30/31 先例。

| E-ID | 声明摘要 | 证据类型 | 证据位置 | 置信度 | 本轮是否复测 |
| :-- | :-- | :-- | :-- | :-- | :-- |
| E-V01 | 安装根/启动 bat/JVM 命令/全部 CGTECH_* 开关注释 | 安装目录文件逐行读取 | `E:\windows64\commands\vericut.bat`（168 行全文） | 高 | 是（本轮 Read） |
| E-V02 | COM 6 ProgID 判死(-2147221005)、stdin IPC 无响应、batch 自退、GUI 播放实测、vcreview 227MB、仿真日志数值 | 先例实测报告 + 桥接代码 | `D:\Virtu模型\2026-10-30_逆向-VERICUT9.6-report.md`；`work\vericut-toolchain\vericut_link.py` | 高（历史实测） | 否（复用先例） |
| E-V03 | JAB/UIA 深树不暴露 Swing/Flamingo；播放按钮坐标 (1890,860)；物理像素=OCR千分比×1920/×1080 | 先例实测（GUI 截图/模板匹配） | 同 E-V02 报告 §3.3 | 高（历史实测） | 否 |
| E-V04 | commands/ 转换器 bat 清单（dxf2sor/iges2v/cad2v/bincl2v/sur2stk/polyfix/toolman/reviewer/bwizard/各 CAM 接口） | 安装目录 Glob（文件存在性） | `E:\windows64\commands\*.bat`（~60 个） | 高（存在性）/ 中（未运行） | 是（本轮 Glob） |
| E-V05 | 框架 = Swing ActionMap/InputMap + Flamingo JRibbon；无 Play 快捷键 | javap 反编译落盘 | `work\vericut-toolchain\keybinding.txt`（KeyBinding.java 全量） | 高（历史反编译） | 本轮 Read 头部复核 |
| E-V06 | CGTECH_VCPROJECT 自动加载工程、CGTECH_TRANSACTION_LOG=Yes 审计（ActionMainPlay 381 条）、bat 启动方式约束（cmd /c 非 DETACHED） | 先例实测（2026-10-31 追加节） | 同 E-V02 报告 §8 | 高（历史实测） | 否 |
| E-V07 | 桥接实现（vericut_bridge.py：unsupported_headless + parse_collision_log 双语分类） | 桥接代码 Read | `D:\Virtu模型\bridges\vericut_bridge.py` | 高 | 是（本轮 Read） |
| E-V08 | 六软件注册表：vericut=READY，进程 vericut.exe/javaw.exe，无 COM | 注册表代码 | `D:\Virtu模型\bridges\software_registry.py`（SOFTWARE_SPECS["vericut"]） | 高 | 是（本轮 Read） |
| E-V09 | 官方文件格式全表（.vcproject/.usr/.mch/.ctl/.tls/.ip/.vct/.sor/.swp/.stp/.stl/.sat/.igs/.pts/.rpt/.olb/.VcPost/.VcInspect/.cme + batch `vcp=/ip=` 语法） | 官方在线帮助站（实际 web_fetch 返回） | https://help.vericut.com/4_vericut_help/2.3_vericut_file_descriptions ；https://help.vericut.com/4_vericut_help/2.2_working_with_vericut_files | 高（官方） | 是（本轮在线抓取） |
| E-V10 | 桥接库 9 通道函数签名与坐标锚点常量 | 桥接代码 Read | `work\vericut-toolchain\vericut_link.py` | 高 | 是（本轮 Read） |

## 无证据不写的边界声明

- 本知识库**不包含**任何许可证/授权/加密/激活机制内容（`CGTECH_LICENSE`、SLM 细节一律不展开）。
- 凡官方文档提及但本机未实测的能力（CME-API、OptiPath 外挂、Inspection、X-Caliper、各 CAM 接口 bat、batch `vcp=/ip=` 语法），一律标注 `documented-not-probed`，未当作已验证能力。
- COM/IPC/UIA/batch 判死结论完整保留为 `confirmed-negative`，未因官方文档存在而"翻案"。

---

## 阶段一插件级追加证据（2026-11-04）

| E-ID | 声明摘要 | 证据类型 | 证据位置 | 置信度 | 本轮是否复测 |
| :-- | :-- | :-- | :-- | :-- | :-- |
| E-V11 | 桌面 5 个 VERICUT 快捷方式存在（主程序/Single Platform/Reviewer/ToolMan/Assembly Manager） | 桌面快捷方式 Glob | `C:\Users\Public\Desktop\Vericut*.lnk`（5 个） | 高（存在性） | 是 |
| E-V12 | 各独立程序主类（toolman=com.cgtech.toolman.ToolManager、reviewer=com.cgtech.VericutReviewer、assembly_manager=com.cgtech.assemblyman.AssemblyManager、vdaf=com.cgtech.AutoFastener、bwizard=com.cgtech.BWizard、cad2v=AcisConv、iges2v=Iges2v、dxf2sor=DxfSorConverter、dxf2sweep=DxfConverter、sur2stk=Sur2stk、bincl2v=Bincl2v、polyfix=PolyFix、delprefs=WipePrefs、vda=Vda、console=com.cgtech.Vericut java 版） | bat 主类 Grep 提取 | `E:\windows64\commands\*.bat`（`com.cgtech.*` 行） | 高 | 是（Grep + 4 份 bat 全文 Read） |
| E-V13 | 官方编程接口文档：CME-API（cmeapi_register_modify_output_str）、Optimization API（CGTECH_OPAPI=DLL 触发 API 模式）、VDAF help 站 | 官方在线文档（真实 URL） | https://help.vericut.com/vericut_development_tools/05_cme_api_help ；https://help.vericut.com/vericut_development_tools/06_optimization_api ；https://help.vericut.com/vdaf_help/ | 高（官方） | 是（在线搜索） |
