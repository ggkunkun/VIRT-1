# Siemens NX 12.0.2.9 — 最快方法证据基准

> 知识库根：`D:\Virtu模型\knowledge_base\six_software\nx\`（README/modules/automation_api/commands/file_formats/workflows/config/plugins/evidence.md）。
> 三态：verified-working [高] = 历史实测；documented-not-probed = 文档化未复测；confirmed-negative = 实测否定。
> 时间量级均标 [估算]，无臆造。

## 0. 任务族适用性

| 任务族 | NX 适用性 | 说明 |
| :-- | :-- | :-- |
| 画图 2D drafting | ✅ | NX Drawing 制图模块主职之一 |
| 建模 3D modeling | ✅ | NX 高端参数化建模主职 |
| 仿真 | ✅ | NX CAE / Nastran（documented-not-probed，本轮未现场复测） |
| 加工 | ✅ | NX CAM 操作导航器 + Post Builder 后处理主职 |

---

## 1. 画图族（Drawing 制图）

### R-draw-1：NX GUI Drafting 制图
- 通道类型：GUI
- 调用路径：启动 ugraf.exe → Ctrl+Alt+D 进 Drafting → 选图纸模板 → 投三视图 → 标注 DIM
- 证据：nx\plugins.md P-NX-05 Drafting（E-117）；nx\runbook §1.1；automation_api.md
- 度量：步骤数=8[估算]；API 调用数=0（菜单操作 ~15 步）；启动开销=冷启动 ugraf 30~60s [估算]；可并行度=低（GUI 单实例）；证据等级=documented-not-probed；确定性=中（GUI 点击不脆弱但慢）；失败风险=低（菜单路径稳定）

### R-draw-2：NXOpen Python Journal 批量出图
- 通道类型：API + 批处理（run_journal.exe）
- 调用路径：写 journal：`theSession.Drafting.DraftingSetup` → `CreateBaseView` → `CreateProjectedView` → `CreateDimension`；`run_journal.exe script.py`
- 证据：nx\automation_api.md（Drafting 域 libnxopencpp_drafting.dll，E-116）；nx\runbook §2
- 度量：步骤数=2（写脚本+run_journal）；API 调用数=8~12[估算]；启动开销=冷启动 run_journal 20~40s [估算]；可并行度=中（多 journal 串行跑 NX 进程，NX 单实例）；证据等级=documented-not-probed；确定性=高（API 对象级）；失败风险=中（Drafting API 比 Modeling 脆弱，坐标系/视图锚点易报错）

## 2. 建模族（3D modeling）

### R-model-1：NXOpen Python Journal + run_journal.exe（首选）
- 通道类型：API + 批处理
- 调用路径：`set UGII_BASE_DIR=...\NX & set UGII_ROOT_DIR=...\NX\NXBIN & NXBIN\run_journal.exe script.py`；脚本用 `Parts.NewBase` + `Expressions.CreateWithUnits` + `Features.CreateBlock/Cylinder/Extrude` + `UF.ModlFeatures.CreateBlend/CreateChamfer`
- 证据：nx\automation_api.md；nx\runbook §2.1；D:\Virtu模型\run_nx_journal.py 先例；E-126 STEP 导出 verified-working
- 度量：步骤数=2（写脚本+无头跑）；API 调用数=5~15（按特征数）；启动开销=冷启动 run_journal 20~40s [估算]；可并行度=中（NX 单实例，串行）；证据等级=verified-working [高]；确定性=高（对象级，ΔV≠0 可断言）；失败风险=低-中（几何失败如"unable to apply blend"可预期修复）

### R-model-2：UF_MODL API（同 R-model-1 内 UF 层）
- 通道类型：API
- 调用路径：`uf=NXOpen.UF.UFSession.GetUFSession(); uf.ModlFeatures.CreateBlend("4.0", edge_tags,0,0,0,0.0001); uf.Modeling.CreateChamfer(1,"0.2","0.2","45",edge_tags)`
- 证据：nx-automation SKILL §5-6；nx\automation_api.md UF_MODL 节
- 度量：与 R-model-1 合并（UF 与 NXOpen 同进程）；启动开销=同 R-model-1；确定性=高；失败风险=低（UF 比 Builder 模式简单可靠）

### R-model-3：GUI 手工建模
- 通道类型：GUI
- 调用路径：ugraf.exe → 新建 → 插入 Block/Cylinder/Extrude → 边圆角/倒角
- 证据：nx\runbook §1.1
- 度量：步骤数=10~20[估算]；API 调用数=0；启动开销=冷启动 ugraf 30~60s [估算]；可并行度=低；证据等级=documented-not-probed；确定性=中；失败风险=低

## 3. 仿真族（CAE / Nastran）

### R-sim-1：NX CAE 前后处理 + Nastran 求解
- 通道类型：GUI / API（混合）
- 调用路径：启动 ugraf → Ctrl+Alt+E 进 Advanced Simulation → 建 FEM 文件 → 网格化 → 加约束/载荷 → Nastran 求解 → 后处理看 von Mises FOS≥1.5
- 证据：nx\plugins.md P-NX-04 libnxopencpp_cae.dll（E-116）；AGENTS.md §3 FOS≥1.5 公理
- 度量：步骤数=15~25[估算]；API 调用数=0（GUI）；启动开销=冷启动 60~120s [估算]（CAE 模块重）；可并行度=低；证据等级=documented-not-probed；确定性=中；失败风险=中（网格质量/边界条件定义易报错）

### R-sim-2：NXOpen CAE Journal 批处理（documented）
- 通道类型：API + 批处理
- 调用路径：run_journal.exe + `libnxopencpp_cae.dll`（Python 绑定 NXOpen.CAE.*）
- 证据：E-116；automation_api.md
- 度量：步骤数=2；API 调用数=10~20[估算]；启动开销=冷启动 40~80s [估算]；可并行度=中；证据等级=documented-not-probed；确定性=高；失败风险=中（CAE journal API 复杂度高）

## 4. 加工族（CAM + 后处理）

### R-mach-1：CAM 操作导航器 + Post Builder 三件套（首选）
- 通道类型：GUI + 插件（Post Builder）
- 调用路径：Ctrl+Alt+M 进加工 → 选 template_set（mill_planar/mill_contour/hole_making/lathe/wire_edm/mill_multi-axis_hsm.opt）→ 建操作 Generate → **检查 Operation Navigator 无 !**（AGENTS.md C 公理）→ 右键后处理选三件套（mill3ax.tcl+.def+.pui / mill_5axis_Sinumerik_840D_mm / YS5_KD_RTCP_-110+10 / Mikron_VCP600 / probing_cycles_fanuc / lathe_tool_tip）
- 证据：nx\plugins.md P-NX-02/03/06/07（E-118~E-120）；nx\runbook §1.2/1.3；AGENTS.md C
- 度量：步骤数=6~10；API 调用数=0；启动开销=冷启动 ugraf+CAM 60~120s [估算]；可并行度=低；证据等级=documented-not-probed（CAM 操作导航器 verified-working 历史）；确定性=中；失败风险=中（! 警告未消除直接 Post 会出废刀路）

### R-mach-2：NXOpen CAM Journal 批处理
- 通道类型：API + 批处理
- 调用路径：run_journal.exe + `libnxopencpp_cam.dll`；脚本自动建 Operation + Generate + PostProcess
- 证据：E-116（libnxopencpp_cam.dll）；nx\automation_api.md
- 度量：步骤数=2；API 调用数=10~20[估算]；启动开销=冷启动 40~80s [估算]；可并行度=中；证据等级=documented-not-probed；确定性=高；失败风险=中（CAM journal 复杂度高，需先消除 !）

### R-mach-3：YANGJEE 定制后处理（外挂三件套）
- 通道类型：插件
- 调用路径：后处理对话框选 yangje_post*.pui（在 Post Builder 列表中）
- 证据：nx\plugins.md P-NX-03（E-120）
- 度量：与 R-mach-1 合并；启动开销=0（已在 NX 内）；确定性=中；失败风险=低

---

## 最快结论（NX 12.0）

| 任务族 | 最快路线 | 次优备选 | 判定依据 | 置信度 |
| :-- | :-- | :-- | :-- | :-- |
| 画图 Drawing | R-draw-2 NXOpen Python Journal 批量出图 | R-draw-1 GUI Drafting | Journal：2 步+对象级确定性高 vs GUI：8 步+15 菜单点击；Drafting API 略脆弱故置信度中 | [中] |
| 建模 3D | R-model-1 NXOpen Python Journal + run_journal.exe | R-model-3 GUI 手工 | run_journal verified-working [高]：2 步+ΔV≠0 可断言+UF_MODL 比 Builder 可靠；GUI 10~20 步+冷启动 30~60s | [高] |
| 仿真 CAE | R-sim-1 NX CAE GUI + Nastran | R-sim-2 CAE Journal | CAE Journal documented-not-probed 且 API 复杂度高；GUI 虽慢但路径成熟；FOS≥1.5 必须人工复核 | [中] |
| 加工 CAM | R-mach-1 CAM 操作导航器 + Post Builder 三件套 | R-mach-2 NXOpen CAM Journal | AGENTS.md C 公理要求 ! 消除后再 Post；GUI 操作导航器可视化最稳；CAM Journal 未实测 | [中] |
