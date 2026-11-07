# AutoCAD 2026 — 证据链

| E-ID | 声明摘要 | 证据类型 | 证据位置 | 置信度 | 本轮是否复测 |
|---|---|---|---|---|---|
| E-AC-01 | 显示名 AutoCAD 2026-简体中文；类别 2D Drafting；能力 autolisp_execution/headless_ezdxf/gdt_tolerancing/multi_layer_drawing | 桥接注册表代码 | `bridges/software_registry.py` SOFTWARE_SPECS["autocad"] | 高 | 是（Read） |
| E-AC-02 | 主程序 acad.exe/accoreconsole.exe；COM ProgID=AutoCAD.Application；GetActiveObject/Dispatch；SendCommand(lisp+\n)；accoreconsole /s /i；ezdxf.new("R2018")；OUTLINE/CENTER/DIMENSION 层；add_circle/add_line/add_text | 桥接代码（接口证据） | `bridges/autocad_bridge.py` 全文 | 高 | 是（Read） |
| E-AC-03 | 二进制路径 `D:\cad2026\AutoCAD 2026\acad.exe`、`accoreconsole.exe` | 二进制路径 | software_registry known_binaries；_diag_result.txt 第7行 | 高 | 是（Read diag） |
| E-AC-04 | 预检 6/6 READY；autocad ready=True（diag 时未运行） | 诊断输出 | `D:\Virtu模型\_diag_result.txt` 第3、7行 | 高（历史实测） | 是（Read diag） |
| E-AC-05 | 标准图层 OUTLINE/DIM/HIDDEN/CENTER/HATCH/TITLE_BLOCK；视口边界与文字-尺寸重叠检查 | 项目公理 | `D:\Virtu模型\AGENTS.md` 第2.B节 | 高 | 是（Read 项目规则） |
| E-AC-06 | CUIX/LISP/模板/dwt 位置 | 安装目录文件 | `D:\cad2026\AutoCAD 2026\UserDataCache\zh-cn\Support\*.cuix`；`UserDataCache\zh-cn\Template\*.dwt`；`Support\acad2026.lsp`、`Support\zh-CN\*.lsp` | 高 | 是（Glob） |
| E-AC-07 | DWG 复现流程/COM 稳定性/SendCommand/DXFOUT/DATAEXTRACTION/-LAYER/-STYLE/-DIMSTYLE/LIST/ZOOM E；源-目标实体数对比 | 用户已装领域技能 | `.user_skills/autocad-dwg-redraw/SKILL.md` 全文 | 高 | 是（Read） |
| E-AC-08 | SendCommand ActiveX 官方签名（Document.SendCommand，Windows only）；命令行访问说明 | 官方文档URL | help.autodesk.com OARX SendCommand；cloudhelp CHS About Accessing Command Line | 高 | 是（general_search） |
| E-AC-09 | accoreconsole 四开关 /i /s /l（及 /product /isolate /readonly /profile）；ScriptPro 后台；反斜杠 \s 拼写致崩案例 | 官方博客/支持文章URL | blog.autodesk.io/getting-started-with-accoreconsole；autodesk.com.cn 支持文章 | 高 | 是（general_search） |
| E-AC-10 | 跨软件工具 cadcam_autocad_draw（send_lisp/create_dxf/run_headless_script）定义 | 桥接编排代码 | `bridges/tool_calling_specs.py` cadcam_autocad_draw | 高 | 是（Read） |
| E-AC-11 | DXF 版本映射 AC1032=2018；HEADER/组码/INSERT 规范 | 官方文档URL | help.autodesk.com AutoCAD-DXF GUID-A85E8E67/GUID-3F0380A5/GUID-3610039E/GUID-28FA4CFB | 高 | 是（general_search） |
| E-AC-12 | 既有产物 Flange_Drawing_GB.dxf | 项目产物 | 任务书声明（本轮未 Glob 复核） | 中 | 否（任务书引用） |

## 判死/未复测通道记录

| 通道 | 判定 | 依据 |
|---|---|---|
| accoreconsole 跑 -IFCEXPORT 等特定重命令 | documented-not-probed | Autodesk 支持文章记录此类命令可致 accoreconsole 崩溃，本轮未测（E-AC-09） |
| 本机 COM 注册状态/类型库自动注册 | documented-not-probed | software_registry.com_registered 历史流程；本轮未读注册表（通道限制） |
| acad.pgp 命令别名位置 | documented-not-probed | 安装 Support 根 Glob 未找到 .pgp，实际在用户 roaming 目录，本轮未读 |
| 用户偏好注册表/roaming 目录 | documented-not-probed | 通道限制未读取 |

## 插件扩展证据（plugins.md）

| E-ID | 声明摘要 | 证据类型 | 证据位置 | 置信度 | 本轮是否复测 |
|---|---|---|---|---|---|
| E-AC-P01 | CUIX 界面包在盘（custom/ModelDoc/acetmain/dbcon） | 安装目录文件 | `D:\cad2026\AutoCAD 2026\UserDataCache\zh-cn\Support\*.cuix` | 高 | 是（Glob） |
| E-AC-P02 | ObjectARX 机制（appload/AcAutoLoader）+ 100+ 内置功能 arx 在盘 | 安装目录二进制 | `D:\cad2026\AutoCAD 2026\appload.arx`、`AcAutoLoader.arx`、`AcDim.arx`、`AcTable.arx`、`AcPublish.arx`、`AcRefEd.arx`、`AcXrefService.arx`、`acblock.arx` 等 | 高 | 是（Glob） |
| E-AC-P03 | AutoLISP/VisualLISP 运行时在盘 | 安装目录二进制 | `D:\cad2026\AutoCAD 2026\vl.arx`、`vl_u.arx`、`asilisp.arx` | 高 | 是（Glob） |
| E-AC-P04 | Express Tools 目录在盘（可执行工具+arx） | 安装目录文件 | `D:\cad2026\AutoCAD 2026\Express\alias.exe`、`dumpshx.exe`、`lspsurf.exe`、`RText.arx`、`acetutil.arx`、`leaderex.arx`、`ctextapp.arx`、`dimsio.arx` 等 | 高 | 是（Glob） |
| E-AC-P05 | 打印样式 ctb 在盘 | 安装目录文件 | `UserDataCache\Plotters\Plot Styles\acad.ctb`、`monochrome.ctb`、`Screening *.ctb`、`Grayscale.ctb`、`DWF Virtual Pens.ctb`、`Fill Patterns.ctb` | 高 | 是（Glob） |
| E-AC-P06 | 动态块机制组件在盘（acblock/acDcSymbols） | 安装目录二进制 | `D:\cad2026\AutoCAD 2026\acblock.arx`、`acDcSymbols.arx` | 中 | 是（Glob） |
| E-AC-P07 | accoreconsole /i /s 桥接已用；/l 等扩展开关文档化 | 桥接代码+官方文档 | bridges/autocad_bridge.py run_headless_script；blog.autodesk.io/getting-started-with-accoreconsole | 高 | 是（Read+search） |
