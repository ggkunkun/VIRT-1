# AutoCAD 2026 简体中文 — 结构化知识库（A 片文档化逆向）

> 本目录是 Virtu 模型「六软件逆向知识库」中 AutoCAD 2026（简体中文）分片。所有断言可回溯到同目录 `evidence.md` 的 E-ID。本轮为**文档化逆向**：因执行通道限制（PowerShell 持久故障 `HISTORY_INVALID_PATH`、Bash 禁用、桌面自动化对子代理不可用），**未现场复测 COM/启动类探测**；历史已验证判定标注 `[高]（历史实测）`，本轮仅文档化者标注 `documented-not-probed`。

## 1. 软件身份表

| 项 | 值 | 证据 |
|---|---|---|
| 显示名 | AutoCAD 2026 - 简体中文 (Simplified Chinese) | E-AC-01 |
| 版本 | 2026（COM ProgID 次版本内部称 `.25`） | E-AC-01, E-AC-02 |
| 类别 | 2D 制图与工程图（2D Drafting & Engineering Drawings） | E-AC-01 |
| 主程序路径 | `D:\cad2026\AutoCAD 2026\acad.exe`；无头控制台 `D:\cad2026\AutoCAD 2026\accoreconsole.exe` | E-AC-03 |
| 进程名 | `acad.exe` / `accoreconsole.exe` | E-AC-03 |
| COM ProgID | `AutoCAD.Application` | E-AC-02 |
| 能力标签 | AutoLISP 执行 autolisp_execution / 无头 ezdxf headless_ezdxf / GD&T 标注 gdt_tolerancing / 多图层工程图 multi_layer_drawing | E-AC-01 |
| 验证状态 | 六软件预检中 `autocad ready=True`（历史实测，diag 时未运行） | E-AC-04 |
| 图层公理 | 标准图层 OUTLINE / DIM / HIDDEN / CENTER / HATCH / TITLE_BLOCK；检查视图口边界与文字-尺寸重叠 | E-AC-05 |

## 2. 本目录文件清单

| 文件 | 用途 |
|---|---|
| `README.md` | 本索引 |
| `modules.md` | 功能模块树（按应用领域分块，中英文名，模块→命令映射，含 mermaid） |
| `automation_api.md` | 自动化接口（COM ActiveX / AutoLISP / accoreconsole 无头批处理 / ezdxf 文件级通道，三态判定） |
| `commands.md` | 关键命令表（命令行/LISP/脚本，可复现） |
| `file_formats.md` | DWG/DWT/DXF 等格式（含 DXF 官方规范链接） |
| `workflows.md` | 端到端工作流（蓝图→2D 底稿→分层工程图→GB 标注→交付，按 AC 角色裁剪） |
| `config.md` | CUIX/模板/LISP 支持/PGP 等配置位置 |
| `module_inventory.json` | 机器可读模块清单 |
| `evidence.md` | 逐条证据链 |
| `plugins.md` | 第 10 文件：插件/扩展机制（CUIX/ObjectARX/VisualLISP/Express Tools/打印样式/动态块/accoreconsole 扩展） |

## 3. 模块树与自动化入口摘要

AutoCAD 2026 是 2D 工程图核心：绘图(LINE/CIRCLE/PLINE) → 图层(LAYER) → 标注(DIM) → 文字(TEXT/MTEXT) → 剖面线(HATCH) → 块(BLOCK/标题栏) → 布局/出图(PLOT)。完整模块树见 `modules.md`。

**关键自动化入口**（详见 `automation_api.md`）：
- 活 GUI：COM ActiveX `AutoCAD.Application` → `ActiveDocument.SendCommand(lisp+"\n")`；
- 无头：`accoreconsole.exe /i <dwg> /s <script.scr>` 批处理；
- 文件级：`ezdxf`（Python 库）无头读写 DXF，无需 AutoCAD 进程。

## 4. 供模型训练的使用说明

- **要在活跃 AutoCAD 画图**：读 `automation_api.md` 的 COM 通道，用 `SendCommand` 发 AutoLISP；坐标 mm。
- **要无头批量出图**：用 `accoreconsole.exe /i /s` 或 `ezdxf.new("R2018")`，详见 workflows.md。
- **图层纪律**：先建 OUTLINE/CENTER/DIM 等标准层再画，遵守 AGENTS.md AutoCAD 公理。
- **核验结论**：先回 `evidence.md` 查 E-ID；`documented-not-probed` 项无人值守前必须现场复测。
