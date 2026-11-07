# Siemens NX 12.0.2.9 运行手册（runbook）

> 知识库上下文：`D:\Virtu模型\knowledge_base\six_software\nx\`（README/modules/automation_api/commands/file_formats/workflows/config/plugins/evidence.md）。
> 三态：verified-working = 历史实测；documented-not-probed = 文档化未复测；confirmed-negative = 实测否定。

## 0. 速查卡
- 显示名：Siemens NX 12.0.2.9（中文版 YANGJEE MP14 repack）
- 主程序：`E:\BaiduNetdiskDownload\NX 12.0.2.9\NX12.2.9waigua\NX12.2.9\NX\UGII\ugraf.exe`；无头 `NXBIN\run_journal.exe`；启动器 `中文版NX12.0.exe`
- 进程：`ugraf.exe` / `run_journal.exe`；无 COM（com_prog_id=None）
- 关键自动化通道：NXOpen Python Journal（verified-working，历史实测 run_nx_journal.py）
- 关键文件：`STEP214UG\ugstep214.def`（STEP 配置）、`UGII\menus\*.men/.tbr`（UI 定制）、`MACH\resource\template_set\*.opt`（CAM 模板）、`MACH\resource\postprocessor\*.{tcl,def,pui}`（后处理三件套）

## 1. GUI 操作路线

### 1.1 建法兰并导 STEP
| 步骤 | 动作 | 菜单位置 | 预期结果 | 检查点 |
|---|---|---|---|---|
| 1 | 新建零件 | 文件→新建→模型(mm) | part.prt | 单位 mm |
| 2 | 插入块 | 插入→设计特征→长方体 | 基体 | ΔV>0 |
| 3 | 切除内孔 | 插入→设计特征→圆柱(差集) | 内孔 | ΔV<0 |
| 4 | 切槽+圆角 | 插入→细节特征→边圆角 R4 | 槽成形 | ΔV≠0 |
| 5 | 导出 STEP | 文件→导出→STEP214 | .stp | AP214、Solids+Surfaces |

### 1.2 CAM 面铣
| 步骤 | 动作 | 菜单 | 检查点 |
|---|---|---|---|
| 1 | 进入加工环境 | Ctrl+Alt+M | 选 mill_planar.opt |
| 2 | 建操作 | 插入→操作→FACE_MILLING | Operation Navigator 无 ! |
| 3 | 生成刀路 | 右键→Generate | 无过切 |
| 4 | 后处理 | 右键→后处理 | 选 mill3ax.pui → .nc |

### 1.3 五轴后处理（840D）
- 加工环境：mill_multi-axis.opt
- 操作：VARIABLE_CONTOUR
- 后处理：mill_5axis_Sinumerik_840D_mm.pui（毫米）

## 2. API / 自动化路线

### 2.1 NXOpen Python Journal（verified-working）
```python
# run_journal.exe D:\path\script.py
# env: UGII_BASE_DIR=E:\...\NX ; UGII_ROOT_DIR=E:\...\NX\NXBIN
import NXOpen
theSession = NXOpen.Session.GetSession()
workPart = theSession.Parts.NewBase("flange.prt", NXOpen.BasePart.Units.Millimeters)
theSession.Parts.SetDisplay(workPart, False, True)
# Expressions
workPart.Expressions.CreateWithUnits("d_outer","80.0")
# Block / Cylinder / Extrude / Blend via UF
uf = NXOpen.UF.UFSession.GetUFSession()
uf.ModlFeatures.CreateBlend("4.0", edge_tags, 0,0,0,0.0001)
# STEP 导出
step = theSession.DexManager.CreateStepCreator()
step.ExportAs = NXOpen.StepCreator.ExportAsOption.Ap214
step.SettingsFile = r"E:\...\NX\STEP214UG\ugstep214.def"
step.Commit()
```

### 2.2 NXOpen C++/Java 绑定（documented-not-probed）
- 链接 `libnxopencpp_cam.dll` / `libnxopencpp_drafting.dll` / `libnxopencpp_cae.dll` 等（E-116）
- UF 层：`libnxopenufjava.dll`

## 3. 插件路线（详见 plugins.md）

| 插件 | 启动方式 | API 入口 | E-ID |
|---|---|---|---|
| CAM 模板集 .opt | 加工环境对话框选 | CAM.NCGroup/Operation | E-118 |
| Post Builder 三件套 | 后处理对话框 | CAM.CAMSetup.PostProcess | E-119/E-120 |
| YANGJEE 定制后处理 | 同上，选 yangje_post*.pui | 同上 | E-120 |
| installed_machines 机床库 | 机床构建器 | CAM Machine Builder | E-121 |
| GC Toolkits | 菜单 GC 工具箱 | 文档 GC_Toolkits_*.pdf | E-122 |
| 菜单定制 .men/.tbr | 编辑 UGII\menus\ | custom_dirs.dat | E-117 |
| Block UI Styler .pax | theSession.Styler.Create*() | .pax XML | E-125 |
| DEX STEP 导出 | 文件→导出 | DexManager.CreateStepCreator | E-126（verified-working） |

## 4. 常见故障与处置
- **Operation Navigator 出现 !**：双击操作→Rebuild Generate，消除后再 Post（AGENTS.md C 公理）。
- **Unable to apply blend**：圆角半径过大，减小 R 或分批处理相邻边。
- **零壁厚**：20 度斜面顶壁留 H-0.01（两步法）。
- **NewBase 不是 Parts.New**：用 `Parts.NewBase`。
- **GRIP 不可用**：NXBIN 无 grip.exe，迁 NXOpen Python（E-124 confirmed-negative）。
- **STEP 导出失败**：检查 ugstep214.def 路径与 LayerMask。
