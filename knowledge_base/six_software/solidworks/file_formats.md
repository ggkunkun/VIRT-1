# SOLIDWORKS 2021 — 文件格式

| 格式 | 扩展名 | 角色 | 说明 | 证据 |
|---|---|---|---|---|
| SOLIDWORKS 零件 | `.SLDPRT` | 原生 | 三维零件；既有产物 `D:\Virtu模型\Flange_Parametric.SLDPRT` | E-SW-02, E-SW-16 |
| SOLIDWORKS 装配体 | `.SLDASM` | 原生 | 零部件装配与配合 | E-SW-08(OTAssemblyMates.chm) |
| SOLIDWORKS 工程图 | `.SLDDRW` | 原生 | 二维工程图 | E-SW-08(OTAdvancedDrawings.chm) |
| 零件模板 | `.prtdot` | 模板 | `data\templates\零件.prtdot`、`lang\chinese-simplified\Tutorial\part.prtdot` | E-SW-15 |
| 装配模板 | `.asmdot` | 模板 | `Tutorial\assem.asmdot` | E-SW-15 |
| 工程图模板 | `.drwdot` | 模板 | `Tutorial\draw.drwdot` | E-SW-15 |
| STEP | `.step/.stp` | 导出 | 中性格式交换；本项目能力 step_export；AP203/AP214/AP242 | E-SW-01, E-SW-14 |
| IGES | `.igs/.iges` | 导入/导出 | 线框交换（配 iges-wireframe-reverse 技能反推坐标） | E-SW-09 |
| DXF/DWG | `.dxf/.dwg` | 导出 | 工程图/草图导出（`slddxf.chm`） | E-SW-08 |
| STL | `.stl` | 导出 | 3D 打印网格 | E-SW-09(路由表 STEP/IGES/STL) |
| 材料库 | `.sldmat` | 配置 | `solidworks materials.sldmat`、`SolidWorks DIN Materials.sldmat` | E-SW-11 |
| 折弯表 | `.btl` / 折弯 `.xls` | 配置 | `Sheetmetal Bend Tables\*.xls`（bend allowance/deduction/k-factor） | E-SW-11 |
| BOM 模板 | `.sldbomtbt` | 配置 | `bom-standard.sldbomtbt` 等 9 种 | E-SW-11 |
| 标题栏/修订栏模板 | `.sldtbt` / `.sldrevtbt` | 配置 | `title block.sldtbt`、`standard revision block.sldrevtbt` | E-SW-11 |
| 孔表模板 | `.sldholtbt` | 配置 | `standard hole table--numbers.sldholtbt` 等 | E-SW-11 |
| 焊件轮廓库 | `.sldlfp` | 配置 | `weldment profiles\ANSI\*.sldlfp` | E-SW-11 |
| 线型 | `.lin` | 配置 | `Swlines.lin` | E-SW-11 |
| 剖面线图案 | `.ptn` | 配置 | `Sldwks.ptn`、`sldwks2003.ptn` | E-SW-11 |
| GD&T 符号库 | `.sym` | 配置 | `gtol97.sym` | E-SW-11 |
| VBA 宏工程 | `.swp`（编译后）/ `.bas`（源码） | 宏 | RunMacro 仅认 `.swp`；`.bas` 仅审阅 | E-SW-02 |

## 官方格式规范链接

- STEP（ISO 10303-214，汽车机械设计核心数据）：https://www.iso.org/cms/live/live/en/sites/isoorg/contents/data/standard/03/87/38727.html （E-SW-14）
- STEP 文件格式综述（Library of Congress，AP203/214/242）：https://www.loc.gov/preservation/digital/formats/fdd/fdd000448.shtml （E-SW-14）
- NIST STEP File Analyzer（支持 AP242/AP203/AP214）：https://www.nist.gov/services-resources/software/step-file-analyzer-and-viewer （E-SW-14）
- SOLIDWORKS API（IFeatureManager::FeatureExtrusion2）：https://help.solidworks.com/2026/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IFeatureManager~FeatureExtrusion2.html （E-SW-10）
- SOLIDWORKS IModelDoc2 成员：https://help.solidworks.com/2025/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDoc2_members.html （E-SW-10）
