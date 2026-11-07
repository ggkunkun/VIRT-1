# Siemens NX 12.0 文件格式

> 表：格式 | 扩展名 | 角色 | 说明 | 证据。官方规范链接均来自实际搜索结果。

| 格式 | 扩展名 | 角色 | 说明 | 证据 |
|---|---|---|---|---|
| NX Part | `.prt` | 原生 | NX 原生部件/装配文件，基于 Parasolid 几何内核，含特征历史 | E-105/E-111 |
| NX 模板 | `.prt`（model-plain-1-mm-template.prt） | 原生模板 | 毫米制建模空白模板（FileNew 引用） | E-107 |
| 刀位源文件 CLSF | `.cls` / `.clsf` | CAM 导出 | 刀位源文件（Cutter Location Source File），后处理输入 | E-105（推断） |
| NC 刀轨 | `.nc` / `.ptp` | CAM 导出 | 后处理输出 G 代码（ISO 6983） | E-112 |
| STEP AP203 | `.stp`/`.step` | 导入/导出 | 配置受控 3D 设计（机械零件/装配），`step203ug.exe` | E-103/E-113 |
| STEP AP214 | `.stp`/`.step` | 导入/导出 | 汽车设计显式几何，`step214ug.exe` + `ugstep214.def` | E-103/E-109 |
| STEP AP242 | `.stp`/`.step` | 导入/导出 | 基于模型的 3D 工程（MBD），`step242.exe` | E-103/E-113 |
| IGES | `.igs`/`.iges` | 导入/导出 | 老式曲线/曲面交换 | E-105（推断） |
| JT | `.jt` | 导出/可视化 | 轻量可视化与协作格式（Siemens PLM Components） | E-114 |
| 螺旋桨/UGII 定制 | `.dpx` | 配置 | NX 应用定制文件（ug_cam.dpx、ug_modeling.dpx 等） | E-105 |
| 螺纹数据表 | `thd_metric.dat` / `thd_english.dat` | 配置 | 公制/英制螺纹参数表 | E-105 |
| STEP 定义文件 | `ugstep214.def` / `step214ug.def` | 配置 | STEP 导出参数定义 | E-109 |
| 孔/网格 STL | `.stl` | 导出 | 快速原型/可视化三角网 | E-111（推断） |

## 官方规范链接

- **NXOpen Python API Reference 12.0**（Siemens PLM 官方文档站）：
  https://docs.plm.automation.siemens.com/data_services/resources/nx/12/nx_api/custom/en_US/nxopen_python_ref/ （E-108）
- **NXOpen .NET Reference Guide**：
  https://docs.plm.automation.siemens.com/data_services/resources/nx/1926/nx_api/custom/en_US/nxopen_net/index.html （E-108）
- **NX programming and customization（功能说明 PDF，Siemens）**：
  https://www.plm.automation.siemens.com/en_gb/Images/nx%20programming%20and%20customization%20fs%20W%203_tcm642-4564.pdf （E-108）
- **STEP AP203/214/242 本地 Rose schema**（安装目录实测）：`NX\STEP214UG\ap203_..._mim_lf.rose`、`ap242_..._mbd.rose`、`automotive_design.rose`（E-109）
- **ISO 6983-1:2009（NC 程序格式，G 代码底层规范）**：
  https://www.iso.org/obp/ui/en/#!iso:std:34608:en （E-112）
- **.prt 格式说明（第三方）**：NX part 基于 Parasolid 内核的专有格式
  https://www.filetypeadvisor.com/extension/prt （E-111）
- **JT 格式（Siemens PLM Components SDK）**：
  https://blogs.sw.siemens.com/nx-design/siemens-open-plm-components-sdks/ （E-114）
