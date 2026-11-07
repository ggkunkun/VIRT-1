# Siemens NX 12.0 配置文件

> 表：配置文件/目录 | 用途 | 位置 | 证据。

| 配置文件/目录 | 用途 | 位置 | 证据 |
|---|---|---|---|
| `ugii_env.dat` | NX 全局环境变量定义（UGII_* 默认值） | `NX\UGII\ugii_env.dat` | E-105 |
| `ugii_env_ug.dat` | UG 环境补充定义 | `NX\UGII\ugii_env_ug.dat` | E-105 |
| `ugii_env.dat_default` | 环境文件出厂备份 | `NX\UGII\ugii_env.dat_default` | E-105 |
| 启动批处理 | 中英文启动：`CH_NX.BAT`（中文）/ `EN_NX.BAT`（英文） | `NX\UGII\` 与 `NX\` 根 | E-101/E-105 |
| `ugii.bat` / `ugiicmd.bat` / `ugspawn.bat` | 命令行/派生启动 | `NX\UGII\` | E-105 |
| `se_nxcam.bat` / `semanaged_nxcam.bat` | NX CAM 环境启动 | `NX\UGII\` | E-105 |
| `gripbatch.bat` | GRIP 批处理 | `NX\UGII\` | E-105 |
| `*.dpx` 定制文件 | 各应用模块菜单/工具条定制（ug_cam.dpx、ug_modeling.dpx、ug_drafting.dpx、ug_sketcher.dpx、ug_assemblies.dpx、ug_analysis.dpx、ug_gdt.dpx、ug_curves.dpx、ug_gateway.dpx、ug_extras.dpx、nx_moldwizard.dpx、nx_routing.dpx 等） | `NX\UGII\` | E-105 |
| `ugstep214.def` / `step214ug.def` | STEP AP214 导出参数 | `NX\STEP214UG\` | E-109 |
| `thd_metric.dat` / `thd_english.dat` | 公制/英制螺纹数据表 | `NX\UGII\` | E-105 |
| `xhatch.chx` / `xhatch2.chx` | 剖面线样式 | `NX\UGII\` | E-105 |
| `ug.xla` | NX for Excel 加载项 | `NX\UGII\` | E-105 |
| `Registry.ini` | NX 内部注册信息 | `NX\UGII\Registry.ini` | E-105 |
| 运行时环境变量 | `UGII_BASE_DIR`/`UGII_ROOT_DIR`/`UGII_LIBRARY_DIR`/`UGII_UGRAF_DIR`/`UGII_LANG=simpl_chinese`/`UGII_COUNTRY=prc` | 启动时由 `run_nx_journal.py` 注入 | E-110 |

## 备注
- 本文件**仅记录功能/配置位置**，不含许可证/服务器/激活相关内部文件（见 scope.md out_of_scope）。
- 注册表项（如 NX 的 Uninstall 信息）未在本轮探测范围，标注 `documented-not-probed`。
