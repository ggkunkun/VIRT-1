# AutoCAD 2026 — 关键命令表

> 类型：命令行 / AutoLISP / 脚本(SCR) / COM / 工具栏。坐标单位 mm。证据见列。

| 命令 ID | 模块 | 类型 | 参数/坐标 | 可复现调用 | 说明 | 证据 |
|---|---|---|---|---|---|---|
| AC_CMD_Connect | 会话 | COM | ProgID | `win32com.client.GetActiveObject("AutoCAD.Application")` | 附着/启动 AC | E-AC-02 |
| AC_COM_SendCommand | 自动化 | COM | lisp+"\n" | `doc.SendCommand("(princ \"hi\")\n")` | 发命令行 | E-AC-02,E-AC-08 |
| AC_CMD_LINE | 绘图 | 命令行/LISP | p1,p2 | `(command "_line" p1 p2 "")` | 画直线 | E-AC-02 |
| AC_CMD_CIRCLE | 绘图 | 命令行/LISP | center,r | `(command "_circle" center r)`；ezdxf `msp.add_circle(c,r,dxfattribs={"layer":"OUTLINE"})` | 画圆 | E-AC-02 |
| AC_CMD_TEXT | 文字 | 命令行/LISP | pos,height,text | `msp.add_text(t,dxfattribs={"layer":"DIMENSION","height":3.5}).set_placement(pos)` | 单行文字 | E-AC-02 |
| AC_CMD_LAYER | 图层 | 命令行 | 名/色/线型 | `doc.layers.add("OUTLINE",color=7)`；`doc.layers.add("CENTER",color=1,linetype="CENTER")` | 建标准层 | E-AC-02 |
| AC_CMD_LINETYPE | 图层 | 命令行 | 线型名 | `linetype="CENTER"` | 中心线线型 | E-AC-02 |
| AC_CMD_DIMLINEAR | 标注 | 命令行 | 两点 | `-DIMLINEAR`（GB 标注） | 线性尺寸 | E-AC-07 |
| AC_CMD_TOLERANCE | 标注 | 命令行 | GD&T 框 | `TOLERANCE` | 形位公差 | E-AC-01 |
| AC_CMD_DIMSTYLE | 标注 | 命令行 | | `-DIMSTYLE ? *` 列出现有标注样式 | 标注样式审计 | E-AC-07 |
| AC_CMD_STYLE | 文字 | 命令行 | | `-STYLE ? *` 列出文字样式（仿宋国标） | 文字样式审计 | E-AC-07 |
| AC_CMD_BLOCK | 块 | 命令行 | | `BLOCK` / `INSERT`（标题栏块） | 块定义/插入 | E-AC-07 |
| AC_CMD_ATTDEF | 块 | 命令行 | | `ATTDEF`（标题栏属性） | 属性定义 | E-AC-07 |
| AC_CMD_HATCH | 剖面线 | 命令行 | | `HATCH`（HATCH 层） | 剖面填充 | E-AC-05 |
| AC_CMD_VIEWPORT | 布局 | 命令行 | | `MVIEW`/视口 | 视口边界检查 | E-AC-05 |
| AC_CMD_PLOT | 出图 | 命令行 | | `PLOT` → PDF | 打印/PDF | E-AC-07 |
| AC_CMD_DXFOUT | 数据交换 | 命令行 | | `DXFOUT` 导出文本 DXF，查 TABLES/BLOCKS/ENTITIES | 图纸审计 | E-AC-07 |
| AC_CMD_DATAEXTRACTION | 数据提取 | 命令行 | | `DATAEXTRACTION` 导出坐标/半径/图层/块属性 | 逆向取数 | E-AC-07 |
| AC_CMD_LIST | 审计 | 命令行 | | `LIST` 查选实体几何 | 实体详情 | E-AC-07 |
| AC_CMD_ZOOM_EXTENTS | 可视化 | 命令行 | | `ZOOM` → `E` | 缩放范围校验 | E-AC-07 |
| AC_CMD_ACCORECONSOLE | 无头 | 批处理 | /i /s /l | `accoreconsole.exe /i in.dwg /s run.scr` | 无头跑脚本 | E-AC-02,E-AC-09 |
| AC_CMD_EZDXF | 无头 | Python | R2018 | `ezdxf.new("R2018"); doc.saveas(path)` | 无头写 DXF | E-AC-02 |
| AC_CMD_AUTOLISP | 自动化 | 文件 | .lsp | 落盘 `scratch/temp_command.lsp` 后手动/无头加载 | LISP 脚本 | E-AC-02 |

## 桥接高层封装（tool_calling_specs）

| 工具名 | 动作 | 说明 | 证据 |
|---|---|---|---|
| `cadcam_autocad_draw` | `send_lisp` / `create_dxf` / `run_headless_script` | 跨软件编排入口；send_lisp 发 LISP，create_dxf 无头 ezdxf 分层图，run_headless_script 用 accoreconsole | E-AC-10 |
| `AutoCADBridge.run_headless_script` | 全流程 | accoreconsole /i /s 跑脚本 | E-AC-02 |
| `AutoCADBridge.create_headless_dxf` | 全流程 | ezdxf R2018 建 OUTLINE/CENTER/DIM 层 + circle/line/text | E-AC-02 |
