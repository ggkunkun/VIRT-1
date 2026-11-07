# SOLIDWORKS 2021 — 设置与配置文件

| 配置文件/目录 | 用途 | 位置 | 证据 |
|---|---|---|---|
| 零件模板 | 新建零件默认模板 | `D:\SOLIDWORKS (2)\data\templates\零件.prtdot`；教程模板 `lang\chinese-simplified\Tutorial\part.prtdot` | E-SW-15 |
| 装配模板 | 新建装配 | `lang\chinese-simplified\Tutorial\assem.asmdot` | E-SW-15 |
| 工程图模板 | 新建工程图 | `lang\chinese-simplified\Tutorial\draw.drwdot` | E-SW-15 |
| 类型库 | COM 早绑定 | `D:\SOLIDWORKS (2)\sldworks.tlb`（GUID {83A33D31-...}，主版本29） | E-SW-02 |
| 材料库 | 赋材质 | `lang\chinese-simplified\sldmaterials\solidworks materials.sldmat`、`SolidWorks DIN Materials.sldmat` | E-SW-11 |
| 线型库 | 草图/工程图线型 | `lang\chinese-simplified\Swlines.lin` | E-SW-11 |
| 剖面线图案 | 剖面 | `lang\chinese-simplified\Sldwks.ptn` | E-SW-11 |
| GD&T 符号库 | 形位公差 | `lang\chinese-simplified\gtol97.sym` | E-SW-11 |
| 钣金折弯表 | 展开计算（K因子/折弯余量/扣除） | `lang\chinese-simplified\Sheetmetal Bend Tables\*.xls`、`sample.btl`、`bendtable-standard.sldbndtbt` | E-SW-11 |
| 焊件轮廓库 | 结构构件 | `lang\chinese-simplified\weldment profiles\ANSI\*.sldlfp` | E-SW-11 |
| BOM 模板 | 材料明细表 | `lang\chinese-simplified\bom-*.sldbomtbt`（9 种） | E-SW-11 |
| 标题栏模板 | 图纸格式 | `lang\chinese-simplified\title block.sldtbt` | E-SW-11 |
| 修订栏模板 | 修订记录 | `lang\chinese-simplified\standard revision block.sldrevtbt` | E-SW-11 |
| 孔表模板 | 孔表 | `lang\chinese-simplified\standard hole table--*.sldholtbt` | E-SW-11 |
| 说明/标注格式 | 注释格式 | `lang\chinese-simplified\calloutformat.txt`、`bendnoteformat.txt`、`drawingscales.txt`、`sheetformats.txt` | E-SW-11 |
| 颜色样块 | 外观 | `lang\chinese-simplified\colorswatches\standard.sldclr` | E-SW-11 |
| 单实例锁 | 桥接并发控制 | `D:\Virtu模型\runs\.solidworks.lock` | E-SW-02 |
| 本机用户偏好 | 选项/最近文件/工具栏布局 | Windows 用户注册表（HKCU\Software\SolidWorks\SOLIDWORKS 2021）与 `%APPDATA%\SolidWorks`；本轮未读取注册表 | documented-not-probed |

> 注：注册表项与用户 roaming 目录本轮因通道限制未现场读取，标注 `documented-not-probed`。
