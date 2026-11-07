# AutoCAD 2026 — 文件格式

| 格式 | 扩展名 | 角色 | 说明 | 证据 |
|---|---|---|---|---|
| AutoCAD 图形 | `.dwg` | 原生 | 原生二进制工程图格式 | E-AC-03, E-AC-07 |
| 图形模板 | `.dwt` | 模板 | `UserDataCache\zh-cn\Template\acadiso.dwt`（公制）、`acad.dwt`、`Tutorial-mMfg.dwt`、`Tutorial-iMfg.dwt`、`acadISO -Named Plot Styles.dwt` | E-AC-06 |
| 图纸集模板 | `.dwt`(Sheet Sets) | 模板 | `SheetSets\Manufacturing Metric.dwt`、`Civil Metric.dwt`、`Architectural Metric.dwt`；样例 `GSC_ISO_A3.dwt` | E-AC-06 |
| 图形交换 | `.dxf` | 导入/导出 | 文本/二进制交换格式；桥接 ezdxf 写 R2018（AC1032） | E-AC-02, E-AC-11 |
| 脚本 | `.scr` | 自动化 | 命令序列脚本，供 accoreconsole `/s` | E-AC-09 |
| AutoLISP | `.lsp` / `.fas` / `.vlx` | 自动化 | `.lsp` 源码；支持目录自带 `acad2026.lsp`、`mvsetup.lsp` 等 | E-AC-06 |
| 自定义 UI | `.cuix` | 配置 | `UserDataCache\zh-cn\Support\custom.cuix`、`ModelDoc.cuix`、`acetmain.cuix`、`dbcon.cuix` | E-AC-06 |
| 线型 | `.lin` | 配置 | AutoCAD 标准线型（CENTER 等） | E-AC-02 |
| 打印样式 | `.ctb` / `.stb` | 配置 | 颜色相关/命名打印样式（模板名含 Named Plot Styles） | E-AC-06 |
| PDF | `.pdf` | 导出 | 出图交付 | E-AC-07 |
| 样例 ActiveX | `.dwg` | 样例 | `Sample\ActiveX\SheetSetVBA\IRD.dwt`、`Sample\Sheet Sets\Manufacturing\GSC_ISO_A3.dwt` | E-AC-06 |

## DXF 版本与头部

- AutoCAD DXF `$ACADVER` 头部码：`AC1032 = AutoCAD 2018`（桥接 ezdxf 用 `R2018`）；更早：AC1027=2013、AC1024=2010、AC1021=2007、AC1018=2004、AC1015=2000、AC1014=R14。E-AC-11。

## 官方规范链接

- DXF HEADER 段组码（AC1032=2018 版本映射）：https://help.autodesk.com/cloudhelp/2024/ENU/AutoCAD-DXF/files/GUID-A85E8E67-27CD-4C59-BE61-4DC9FADBE74A.htm （E-AC-11）
- DXF 组码数值顺序参考：https://help.autodesk.com/cloudhelp/2023/ENU/AutoCAD-DXF/files/GUID-3F0380A5-1C15-464D-BC66-2C5F094BCFB9.htm （E-AC-11）
- 实体通用组码（Common Group Codes for Entities）：https://help.autodesk.com/cloudhelp/2023/ENU/AutoCAD-DXF/files/GUID-3610039E-27D1-4E23-B6D3-7E60B22BB5BD.htm （E-AC-11）
- INSERT 实体组码：https://help.autodesk.com/cloudhelp/2023/ENU/AutoCAD-DXF/files/GUID-28FA4CFB-9D5E-4880-9F11-36C97578252F.htm （E-AC-11）
- ActiveX SendCommand（向命令行发命令）：https://help.autodesk.com/view/OARX/2026/RUS/?guid=GUID-E13A580D-04CA-46C1-B807-95BB461A0A57 （E-AC-08）
- 关于访问 AutoCAD 命令行 (ActiveX, 中文)：https://help.autodesk.com/cloudhelp/2024/CHS/AutoCAD-ActiveX/files/GUID-0A56CD7D-C18E-4A94-B0A7-6F70956A21A9.htm （E-AC-08）
- accoreconsole 命令行开关（/i /s /l 等）：https://blog.autodesk.io/getting-started-with-accoreconsole/ （E-AC-09）
