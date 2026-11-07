# AutoCAD 2026（简体中文）最快方法证据基准

> 依据 `FASTEST_METHODS_CONTRACT.md`。证据回溯本仓 `six_software\autocad\`（automation_api.md / plugins.md / commands.md / workflows.md / runbooks\autocad.runbook.md）。
> 硬边界：无许可证/激活内容；不臆造实测，时间量级标 [估算]。
> 已确认事实：`acad.exe` 主进程、`accoreconsole.exe` 无头进程；COM ProgID `AutoCAD.Application`；标准层 OUTLINE/DIM/HIDDEN/CENTER/HATCH/TITLE_BLOCK；国标字高 3.5mm 仿宋；accoreconsole `/i /s /l`、ezdxf `R2018`(=AC1032)、COM SendCommand 三者均 verified-working [高] 历史实测。

## 任务族适用性
| 任务族 | 适用性 | 说明 |
| :-- | :-- | :-- |
| 画图 2D drafting | ✅ 主职 | 2D 工程图/标注/GD&T，最快任务域 |
| 建模 3D | ⚠️ 仅 2.5D | EXTRUDE 拉伸成实体；非参数化主职（3D 主职在 SW/NX） |
| 仿真 | N/A | AutoCAD 2026 简中为二维绘图/文档工具，本机未装 FEA/CAE 模块，无仿真任务域 |
| 加工 | N/A | AutoCAD 不做 CAM 后处理/刀路；其产物（DWG/DXF）交 NX CAM/VERICUT，自身无加工任务域 |

---

## 一、画图族（2D drafting，主职）— 四路线并列

### R-draw-1：ezdxf 文件级（Python，无进程）
- 通道类型：批处理/文件级（ezdxf 库直接写 DXF，不启动 AutoCAD）
- 调用路径：`ezdxf.new("R2018")` → 建标准层 → `modelspace.add_circle/add_line/add_lwpolyline` → `msp.add_linear_dim` → `saveas()`（runbook §2；commands `autocad.create_dxf`）
- 证据：autocad/plugins.md + automation_api.md（ezdxf R2018 文件级 verified-working [高]）；runbooks/autocad.runbook.md §2；contract §5 实测必引
- 度量：步骤数 2（写脚本+运行）｜API 调用数 ~10（库调用）｜启动开销 **常驻/零进程**（无 acad.exe 冷启动，秒级）[估算]｜可并行度 **高**（多进程/多文件并发）｜证据等级 verified-working [高]｜确定性 **高**（坐标/图层精确）｜失败风险 **低**（无 COM/无 GUI 焦点问题；仅版本约束 R2018=AC1032）

### R-draw-2：pyautocad / COM SendCommand
- 通道类型：API（COM，AutoCAD.Application）
- 调用路径：`Dispatch("AutoCAD.Application")` → `ActiveDocument.SendCommand("-LAYER ... \n")` → `SendCommand("_.circle 0,0 50\n")`（runbook §2；commands `autocad.send_lisp`）
- 证据：automation_api.md（COM SendCommand verified-working [高]）；runbook §2；contract §5
- 度量：步骤数 4｜API 调用数 ~N（每条 SendCommand 一次）｜启动开销 冷（acad.exe 启动 10–30s [估算]）｜可并行度 低（COM 单实例）｜证据等级 verified-working [高]｜确定性 中（SendCommand 文本脆弱、焦点/callee 拒绝需重试）｜失败风险 中（"call rejected by callee"、Start 页需重启进程）

### R-draw-3：accoreconsole + AutoLISP/SCR 无头批处理
- 通道类型：批处理（accoreconsole.exe `/i <dwg> /s <scr> /l zh-CN`）
- 调用路径：准备 `job.scr`（-LAYER/._circle/._dim 命令流）→ `accoreconsole.exe /i in.dwg /s job.scr /l zh-CN`（runbook §2；commands `autocad.accoreconsole_headless`）
- 证据：plugins.md + automation_api.md（accoreconsole /i /s verified-working [高]）；runbook §2；contract §5
- 度量：步骤数 3（写 scr + 调命令行 + 校验）｜命令行调用数 1（批内 N 条 scr 命令）｜启动开销 冷（accoreconsole 比 GUI acad 快 [估算]）｜可并行度 **高**（多实例并发处理多 dwg）｜证据等级 verified-working [高]｜确定性 高（脚本确定性执行，无 GUI 焦点）｜失败风险 中（scr 语法错、路径须正斜杠；无交互能力）

### R-draw-4：GUI 交互绘图
- 通道类型：GUI
- 调用路径：启动 acad→新建 dwt→图层特性建层→直线/圆→DIM→PLOT（runbook §1）
- 证据：runbook §1
- 度量：步骤数 12+｜菜单/点击 ~12｜启动开销 冷 10–30s [估算]｜可并行度 低｜证据等级 documented-not-probed｜确定性 低（坐标/焦点脆弱）｜失败风险 中（误点、SHX 字体缺失）

---

## 二、建模族（2.5D 拉伸）

### R-model-1：COM SendCommand 调 EXTRUDE（2.5D）
- 通道类型：API（COM）
- 调用路径：先画闭合多段线 → `SendCommand("_.extrude \n L \n 20 \n")`（commands `autocad.draw_geometry`）
- 证据：automation_api.md（COM verified）；AGENTS.md §2.B（AutoCAD 仅 2.5D）
- 度量：步骤数 4｜API 调用数 ~3｜启动开销 冷 10–30s [估算]｜可并行度 低｜证据等级 verified-working（COM）｜确定性 中｜失败风险 中（非参数化，修改需重画）

### R-model-2：GUI 拉伸
- 通道类型：GUI
- 度量：步骤数 8+｜启动开销 冷 [估算]｜可并行度 低｜证据等级 documented-not-probed｜确定性 低｜失败风险 中

> 说明：AutoCAD 无参数化 3D 主职；复杂 3D 交 SOLIDWORKS/NX。此处仅 2.5D EXTRUDE，且最快仍走 COM 而非 GUI。

---

## 三、仿真族：N/A
原因：本机 AutoCAD 2026 简体中文为 2D 绘图/文档工具，未安装 FEA/CAE 模块，无仿真任务域；强度校核走 SOLIDWORKS Simulation（FOS≥1.5）。

## 四、加工族：N/A
原因：AutoCAD 不承担 CAM 后处理/刀路生成；其 DWG/DXF 产物作为输入交 NX CAM → CIMCO 背绘 → VERICUT Auto-Diff 闭环，自身无加工任务域。

---

## 最快结论（AutoCAD 2026 简中）
| 任务族 | 最快路线 | 次优备选 | 判定依据（度量对比） | 置信度 |
| :-- | :-- | :-- | :-- | :-- |
| 画图 2D（单件/参数化出图） | R-draw-1 ezdxf 文件级 | R-draw-3 accoreconsole+SCR | ezdxf 零进程、确定性高、可并行高、verified-working [高] vs COM 需起 acad 单实例、GUI 坐标脆弱；单件脚本即出图 | [高] |
| 画图 2D（批量既有 dwg 改造） | R-draw-3 accoreconsole /i /s | R-draw-1 ezdxf | ezdxf 需重写几何；批量改既有 dwg 用 accoreconsole 逐文件跑 scr、可多实例并发、verified-working [高] | [高] |
| 建模 2.5D | R-model-1 COM EXTRUDE | R-model-2 GUI | COM 3–4 步确定性 vs GUI 8+步坐标脆弱；但非参数化，复杂 3D 转 SW/NX | [中] |
| 仿真 | N/A | — | 本机无 FEA 模块；校核走 SW Simulation | [高]（N/A 判定） |
| 加工 | N/A | — | 本机无 CAM；刀路走 NX/CIMCO/VERICUT | [高]（N/A 判定） |
