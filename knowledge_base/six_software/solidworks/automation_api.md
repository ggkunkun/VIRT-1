# SOLIDWORKS 2021 — 自动化接口清单

> 通道状态三态：`verified-working`（历史实测已跑通）/ `confirmed-negative`（已确认不可用）/ `documented-not-probed`（本轮未复测，仅文档化）。
> 桥接证据：`D:\Virtu模型\bridges\solidworks_bridge.py`（E-SW-02）。

## 1. 通道总表

| 通道 | 入口 / ProgID / 路径 | 状态 | 证据 |
|---|---|---|---|
| COM Automation（早绑定） | ProgID `SldWorks.Application`；`gencache.EnsureModule({83A33D31-27C5-11CE-BFD4-00400513BB57},0,29,0)` | verified-working（历史实测） | E-SW-02, E-SW-05 |
| COM 晚期绑定 `Dispatch` | `win32com.client.Dispatch("SldWorks.Application")` | documented-not-probed（桥接改用早绑定，因晚期绑定解析不了 NewPart/SelectByID2） | E-SW-02 |
| ROT 附着运行实例 | `GetActiveObject("SldWorks.Application")` / Running Object Table | confirmed-negative（本机此版本未注册进 ROT，桥接枚举 ROT 找不到 sldworks） | E-SW-02 |
| VBA 宏执行 | `ISldWorks::RunMacro(swpPath, ModuleName, ProcName)` | verified-working 仅在编译后 `.swp` 工程；裸 `.bas` 文本不执行（桥接实测降级为 saved_only） | E-SW-02 |
| 命令行批处理 | 无官方 headless CLI；驱动方式 = COM 启动后 `sw.NewPart()` 等 | documented-not-probed | E-SW-02 |
| 单实例约束 | 桥接进程内单例 `_MAX_INSTANCES=1` + 磁盘锁 `runs/.solidworks.lock` + `tasklist /FI SLDWORKS.exe` | verified-working（历史实测防多开） | E-SW-02 |
| 类型库文件 | `D:\SOLIDWORKS (2)\sldworks.tlb`（及 swcommands/swconst/swvba/SolidWorks.MacroBuilder/swmotionstudy/swdimxpert/swscanto3d/SWRoutingLib 等 .tlb） | verified-working（文件存在，已被 EnsureModule/makepy 使用） | E-SW-12 |
| 环境变量 | 标准 SW 行为，本轮未枚举专门变量 | documented-not-probed | — |

## 2. COM 关键对象与方法签名

> 单位公理：API 内部长度单位为**米**（1 mm = 0.001 m）；世界 Y 向上。签名来自桥接代码实际调用（E-SW-02），官方方法页见 E-SW-10。

### 2.1 应用对象 `ISldWorks`（类型库 CoClass）
```python
# 连接（桥接已验证配方）
gc.EnsureModule("{83A33D31-27C5-11CE-BFD4-00400513BB57}", 0, 29, 0)   # SW2021 = 主版本 29
mod = gc.GetModuleForProgID("SldWorks.Application")
sw  = mod.SldWorks()          # 未运行则启动；早绑定 CoClass
sw.Visible = True
part = __WrapDispatch(sw.NewPart(), "IModelDoc2")   # 用默认零件模板新建
```
- `ISldWorks::NewPart() -> IModelDoc2`：用默认零件模板新建零件（桥接实测，避免指向不存在的 `零件.prtdot`）。E-SW-02。
- `ISldWorks::OpenDoc6(...)`：打开既有文档（官方 API 文档化，`documented-not-probed` 本轮未直接调用）。E-SW-10。
- `ISldWorks::RunMacro(swpPath, module, proc) -> bool`：执行编译后 VBA 宏工程。E-SW-02。

### 2.2 文档对象 `IModelDoc2`
```python
part.SelectByID("前视基准面", "PLANE", 0.0, 0.0, 0.0)   # 旧版 5 参，避开 Callout 参数
part.ClearSelection2(True)
part.EditRebuild3                 # 重建（属性式调用，桥接实际用法）
part.ForceRebuild3(True)          # 强制重建
part.GetEquationMgr() -> EquationMgr
part.GetBodies2(0)                # 0 = 实体(solid bodies)
part.Extension.CreateMassProperty() -> MassProperty
part.SaveAs(path)                 # 保存
part.SaveAs3(path, 0, 1)          # 另存（桥接 model_flange 用法）
part.ViewZoomtofit2()             # 缩放整屏
```
- 基准面名随语言环境变化：`前视基准面/Front Plane`、`上视基准面/Top Plane`、`右视基准面/Right Plane`（桥接 `PLANE_NAMES` 双语回退）。E-SW-02。

### 2.3 草图 `ISketchManager`
```python
part.SketchManager.InsertSketch(True)                       # 进入/退出草图
part.SketchManager.CreateCornerRectangle(x1, y1, 0.0, x2, y2, 0.0)  # 角矩形（米）
part.SketchManager.CreateCircleByRadius(cx, cy, 0.0, r)     # 圆心+半径画圆（米）
```

### 2.4 特征 `IFeatureManager`
```python
# 盲拉伸凸台（23 个位置参数，桥接有 assert len(args)==23）
feat = part.FeatureManager.FeatureExtrusion2(
    Sd, Flip, Dir, T1, T2, D1, D2,
    Dchk1, Dchk2, Ddir1, Ddir2, Dang1, Dang2,
    OffsetReverse1, OffsetReverse2, TranslateSurface1, TranslateSurface2,
    Merge, UseFeatScope, UseAutoSelect, T0, StartOffset, FlipStartOffset)
# 拉伸切除（FeatureCut，参数序列与拉伸同族）
feat = part.FeatureManager.FeatureCut(Sd, False, dir1, t1, t2, d1, 0.0, ...)
```
> 官方：`IFeatureManager::FeatureExtrusion2` 已标记为 obsolete，由 `FeatureExtrusion3` 取代（E-SW-10）；但桥接在 SW2021 实测仍可用（`verified-working`）。

### 2.5 方程式 `EquationMgr`
```python
eq = part.GetEquationMgr()
eq.AddEquation(idx, '"D_Outer" = 0.160', True)   # 新式（桥接 create_parametric_part）
eq.Add(idx, '"D_Outer" = 0.160')                  # 旧式（桥接 model_flange）
```
方程式名用引号包裹，数值单位米。E-SW-02。

### 2.6 质量特性 `MassProperty`（体积守恒断言用）
```python
mp = part.Extension.CreateMassProperty()
bodies = part.GetBodies2(0)
mp.AddBodies(bodies)
vol_m3 = mp.Volume          # 立方米 → 桥接 *1e9 得 mm^3
mass_kg = mp.Mass
area_m2 = mp.SurfaceArea    # → *1e6 得 mm^2
com = mp.CenterOfMass       # 长度3 → *1000 得 mm
```
用途：对齐 AGENTS.md 体积守恒公理——拉伸 `ΔV>0`、切除 `ΔV<0`、圆角/倒角 `ΔV≠0`。E-SW-06, E-SW-02。

## 3. VBA 宏通道

- 宏项目为 `.swp`（编译后）；桥接 `execute_vba_code` 先把源码落盘 `.bas`（GBK 编码）供审阅，再尝试 `sw.RunMacro(bas_path,"Main","main")`。**实测**：未连接时返回 `saved_only`；连接后若给的是裸 `.bas` 会失败（RunMacro 需 `.swp`）。E-SW-02。
- 官方 VBA 帮助：安装目录 `lang\chinese-simplified\OTAPIVBA.chm` / `otapi.chm` / `otadvancedapi.chm`；在线示例 E-SW-10。

## 4. 单实例与并发约束（重要）

- 桥接硬编码 `_MAX_INSTANCES = 1`：同一 Python 进程内 `SolidWorksBridge` 单例共享同一 COM 连接；跨进程启动前用 `tasklist /FI "IMAGENAME eq SLDWORKS.exe"` 探测，若已有实例且无法 ROT 附着，则**拒绝再开第二个**并提示用户关闭。E-SW-02。
- 模型训练启示：任何自动化脚本必须复用同一 COM 连接，禁止并发 `Dispatch("SldWorks.Application")`。
