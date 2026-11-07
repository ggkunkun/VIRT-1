# AutoCAD 2026 — 设置与配置文件

| 配置文件/目录 | 用途 | 位置 | 证据 |
|---|---|---|---|
| 主 CUI 自定义 | Ribbon/菜单/工具栏定义 | `D:\cad2026\AutoCAD 2026\UserDataCache\zh-cn\Support\custom.cuix` | E-AC-06 |
| 主模型 CUI | 默认 Ribbon/菜单 | `UserDataCache\zh-cn\Support\ModelDoc.cuix`；`UserDataCache\Support\ModelDoc.cuix` | E-AC-06 |
| 命令别名 CUI | Express/数据库连接 | `UserDataCache\Support\acetmain.cuix`、`UserDataCache\zh-cn\Support\dbcon.cuix` | E-AC-06 |
| 公制模板 | 新建图默认模板 | `UserDataCache\zh-cn\Template\acadiso.dwt`、`acadiso3D.dwt` | E-AC-06 |
| 英制模板 | | `UserDataCache\zh-cn\Template\acad.dwt`、`acad3D.dwt` | E-AC-06 |
| 制造图纸集模板 | | `UserDataCache\zh-cn\Template\SheetSets\Manufacturing Metric.dwt`、`Tutorial-mMfg.dwt` | E-AC-06 |
| 启动 LISP | 启动自动加载脚本 | `Support\acad2026.lsp`、`Support\zh-CN\acad2026doc.lsp` | E-AC-06 |
| 标准 LISP 库 | mvsetup/edge/3d 等命令实现 | `Support\zh-CN\mvsetup.lsp`、`edge.lsp`、`3d.lsp`、`3darray.lsp`、`attredef.lsp`、`ai_utils.lsp` | E-AC-06 |
| 样本工具 | profile 工具 | `Support\sample-profile-util.lsp` | E-AC-06 |
| 样本 ActiveX VBA | 图纸集自动化样例 | `Sample\ActiveX\SheetSetVBA\IRD.dwt` | E-AC-06 |
| 无头脚本输出 | 桥接 scratch | `D:\Virtu模型\scratch\temp_command.lsp`、`scratch\*.dxf` | E-AC-02 |
| 既有 DXF 产物 | 2D 交付样例 | `D:\Virtu模型\Flange_Drawing_GB.dxf`（任务书声明） | E-AC-12 |
| 用户偏好/支持路径 | 选项/最近文件/工具板 | Windows 用户注册表（HKCU\Software\Autodesk\AutoCAD）与 `%APPDATA%\Autodesk\AutoCAD 2026\R25.x\`；本轮未读注册表 | documented-not-probed |
| 命令别名 PGP | acad.pgp 快捷键 | 通常在用户 Support 目录；本轮 Glob 未在安装 Support 根找到 .pgp | documented-not-probed |

> 注：注册表、用户 roaming 目录、acad.pgp 位置本轮因通道限制未现场读取，标注 `documented-not-probed`。
