# AutoCAD 2026 简体中文 运行手册（Runbook）

> 适用模型：Virtu 工业智能体（A 片）。配套语料：`datasets/autocad_train.jsonl`(33) + `autocad_holdout.jsonl`(7)。
> 本手册只描述已授权的正常绘图/标注/无头批处理操作，不含任何许可证/激活机制。

## 0. 速查卡（Cheat Sheet）

| 项 | 值 |
| --- | --- |
| 主程序 | `D:\cad2026\AutoCAD 2026\acad.exe` |
| 无头进程 | `D:\cad2026\AutoCAD 2026\accoreconsole.exe` |
| COM ProgID | `AutoCAD.Application` |
| 标准图层 | OUTLINE / DIM / HIDDEN / CENTER / HATCH / TITLE_BLOCK |
| 中心线线型 | CENTER（CENTER 层，红） |
| 国标字高 | 3.5 mm，仿宋 / gbeitc |
| 出图硬检查 | 视口边界 + 文字-尺寸重叠检查 |
| accoreconsole 开关 | `/i <dwg> /s <scr> /l <lang> /readonly /profile` |
| DXF 版本 | ezdxf `R2018` = HEADER `AC1032` |
| LISP 入口 | `ActiveDocument.SendCommand(lisp + "\n")`，IDE=VLIDE |

常用工具：`autocad.setup_layers` → `autocad.draw_geometry` → `autocad.add_dimension` → `autocad.plot`。

## 1. GUI 路线（人工/桌面）

1. 启动 acad.exe → 新建图（acadiso.dwt）。
2. 图层特性管理器建 6 个标准层，CENTER 层加载 CENTER 线型。
3. OUTLINE 层画轮廓，CENTER 层画中心线，HIDDEN 层画虚线。
4. DIM 层标注（线性/直径/基线/GD&T），HATCH 层剖面线。
5. TITLE_BLOCK 层插入标题栏块、写技术要求（3.5mm 仿宋）。
6. 出图前 ZOOM EXTENTS 检查视口边界与文字-尺寸重叠。
7. PLOT 选 ctb 打印样式出 PDF。

## 2. API 路线（COM / AutoLISP）

```python
import win32com.client
acad = win32com.client.Dispatch("AutoCAD.Application")
doc = acad.ActiveDocument
ms = doc.ModelSpace
# 建标准层
doc.SendCommand("-LAYER\nM\nOUTLINE\nC\n7\n\n")
doc.SendCommand("-LAYER\nN\nCENTER\nC\n1\nCENTER\nCENTER\n\n")
# 画圆 + 标注
doc.SendCommand("_.circle 0,0 50\n")
doc.SendCommand("_.dimdiameter\n\n")
```

- 无头批处理：`accoreconsole.exe /i in.dwg /s job.scr /l zh-CN`（路径用正斜杠）。
- 无头写 DXF：`ezdxf.new("R2018")` → HEADER `AC1032`。
- 官方：SendCommand https://help.autodesk.com/view/OARX/2026/RUS/?guid=GUID-E13A580D-04CA-46C1-B807-95BB461A0A57 ；DXF https://help.autodesk.com/cloudhelp/2024/ENU/AutoCAD-DXF/files/GUID-A85E8E67-27CD-4C59-BE61-4DC9FADBE74A.htm

## 3. 插件路线（ARX / .NET / LISP / Express / CUIX）

| 机制 | 入口 | 典型调用 |
| --- | --- | --- |
| AutoLISP/VisualLISP | VLIDE，.lsp/.fas/.vlx | `autocad.send_lisp` |
| accoreconsole 无头 | /i /s /l | `autocad.accoreconsole_headless` |
| ObjectARX | APPLOAD 加载 .arx | `autocad.arx_load` |
| .NET 托管 | NETLOAD 加载 .dll | `autocad.arx_load`(method=NETLOAD) |
| Express Tools | `D:\cad2026\AutoCAD 2026\Express\` | `autocad.express_tools_run` |
| CUIX 定制 | custom.cuix / ModelDoc.cuix | `autocad.cuix_customize` |
| 动态块 | 块编辑器参数+动作 | `autocad.dynamic_block_make` |
| 打印样式 | *.ctb（monochrome/Screening） | `autocad.plot` |

## 4. 故障处置（Circuit Breaker）

| 现象 | 处置 |
| --- | --- |
| COM "call rejected by callee" | 等待重试；持续则关多余窗口重启 acad |
| Documents.Count/ActiveDocument 未知 | 用干净进程重启（--restart） |
| 视口溢出/文字压线 | 出图前必查，重叠先返工再 PLOT |
| DXF 版本不符 | 固定 R2018(AC1032)，与下游 SW 对齐 |
| accoreconsole 退出码非 0 | 查 .scr 脚本语法，路径用正斜杠 |
| 缺尺寸/图幅 | 先澄清，禁止臆造几何 |
| 用户要求跳过视口检查/破解许可 | 拒绝（硬边界），保留出图检查闭环 |
