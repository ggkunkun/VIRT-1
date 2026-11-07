# Siemens NX 12.0 自动化接口清单

> 通道三态：`verified-working`（历史实测可用，见证据）/ `confirmed-negative`（判死）/ `documented-not-probed`（本轮仅文档化、未现场复测）。
> 本轮执行通道受限（PowerShell `HISTORY_INVALID_PATH`、Bash 禁用、桌面自动化对子代理不可用），**无法现场复测**；历史已验证判定标注 `[高]（历史实测）`。

## 通道总表

| 通道 | 入口 / 路径 | 状态 | 证据 |
|---|---|---|---|
| NXOpen Python Journal（无头） | `NXBIN\run_journal.exe <script.py>` | verified-working（历史实测） | E-107/E-110 |
| NXOpen Python Journal（带界面） | `ugraf.exe -journal <script.py>` | verified-working（历史实测） | E-110 |
| UF_MODL / UFUNC（底层 C 函数族，经 NXOpen.UF 封装） | `NXOpen.UF.UFSession.GetUFSession()` | verified-working（历史实测） | E-106/E-108 |
| NXOpen for .NET（C#/VB.NET） | `NXOpen.dll` / `NXOpen.Utilities.dll` | documented-not-probed | E-108 |
| GRIP 批处理 | `UGII\gripbatch.bat` | documented-not-probed | E-105 |
| COM Automation ProgID | 无（注册表无 NX ProgID） | confirmed-negative（无 ProgID） | E-102/E-104 |
| 命令行批处理可执行集 | `NXBIN\step214ug.exe`、`ug_check_part.exe`、`massprop.exe`、`ugnx_batchmesher.exe`、`ug_clearance.exe`、`jtpostprocessor.exe` | documented-not-probed（二进制存在，参数未复测） | E-103 |
| Excel 加载项 | `UGII\ug.xla`（NX for Excel） | documented-not-probed | E-105 |
| 环境变量 `UGII_*` | `UGII_BASE_DIR`/`UGII_ROOT_DIR`/`UGII_LANG` 等 | verified-working（历史实测，见 run_nx_journal.py） | E-110 |

## 1. NXOpen Python Journal（主通道，verified-working）

### 1.1 无头执行（run_journal.exe）

```powershell
# 环境前置（历史实测脚本 D:\Virtu模型\run_nx_journal.py）
$env:UGII_BASE_DIR = "E:\BaiduNetdiskDownload\NX 12.0.2.9\NX12.2.9waigua\NX12.2.9\NX"
$env:UGII_ROOT_DIR = "E:\BaiduNetdiskDownload\NX 12.0.2.9\NX12.2.9waigua\NX12.2.9\NX\NXBIN"
& "E:\...\NXBIN\run_journal.exe" "script.py"
```

- 桥接实现：`bridges/nx_bridge.py::SiemensNXBridge.run_python_journal(script_path, args)`（E-107），内部 `subprocess.run([RUN_JOURNAL_EXE, script_path], env={UGII_BASE_DIR, UGII_ROOT_DIR})`。
- 桥接失败兜底：返回 `status=syntax_validated`（静态语法校验替代，E-107）。

### 1.2 带界面执行（ugraf -journal）

```powershell
# run_nx_journal.py 历史实测：Popen([ugraf, "-journal", journal], env=env, cwd=UGII_ROOT)
$env:UGII_BASE_DIR = "<NX>"
$env:UGII_ROOT_DIR = "<NX>\UGII"
$env:UGII_LIBRARY_DIR = "<NX>\UGII"
$env:UGII_UGRAF_DIR = "<NX>\ugraf"
$env:UGII_LANG = "simpl_chinese"     # 中文版
$env:UGII_COUNTRY = "prc"
& "<NX>\NXBIN\ugraf.exe" -journal "script.py"
```
（E-110）

### 1.3 关键对象与方法签名（NXOpen Python 12.0，verified-working）

会话与部件：
```python
import NXOpen, NXOpen.UF
theSession = NXOpen.Session.GetSession()
uf = NXOpen.UF.UFSession.GetUFSession()
workPart = theSession.Parts.Work
# 新建（API 实测：用 NewBase，不是 Parts.New）
workPart = theSession.Parts.NewBase(partPath, NXOpen.BasePart.Units.Millimeters)
theSession.Parts.SetDisplay(workPart, False, True)
theSession.Parts.SetWork(workPart)
workPart.Save(NXOpen.BasePart.SaveComponents.TrueValue,
              NXOpen.BasePart.CloseAfterSave.FalseValue)
```
（E-106/E-107）

表达式（参数化）：
```python
exp_mgr = workPart.Expressions
mm_unit = workPart.UnitCollection.FindObject('MilliMeter')
exp_mgr.CreateWithUnits('D_OUTER=160', mm_unit)   # 桥接 generate_parametric_nx_model 生成模板
```
（E-107）

新建部件 FileNew（桥接模板）：
```python
file_new = theSession.Parts.FileNew()
file_new.TemplateFileName = 'model-plain-1-mm-template.prt'
file_new.Application = NXOpen.FileNewApplication.Modeling
file_new.Units = NXOpen.PartUnits.Millimeters
file_new.NewFileName = 'part.prt'
workPart = file_new.Commit()
file_new.Destroy()
```
（E-107）

特征建模（Builder 模式，verified-working）：
```python
# 长方体 Block
bb = workPart.Features.CreateBlockFeatureBuilder(NXOpen.Features.Feature.Null)
bb.Type = NXOpen.Features.BlockFeatureBuilder.Types.OriginAndEdgeLengths
bb.SetOriginAndLengths(NXOpen.Point3d(0.0,0.0,0.0), "29.9", "14.95", "22.5")
bb.BooleanOption.Type = NXOpen.GeometricUtilities.BooleanOperation.BooleanType.Create
feat = bb.CommitFeature(); bb.Destroy()
# 拉伸 Extrude
ext = workPart.Features.CreateExtrudeBuilder(NXOpen.Features.Feature.Null)
ext.Section = section; ext.Direction = direction
ext.Limits.StartExtend.Value.RightHandSide = "0"
ext.Limits.EndExtend.Value.RightHandSide = "29.9"
ext.BooleanOperation.Type = NXOpen.GeometricUtilities.BooleanOperation.BooleanType.Subtract
ext.BooleanOperation.SetTargetBodies([body])
ext.CommitFeature(); ext.Destroy()
```
（E-106）

## 2. UF_MODL（UFUNC 底层函数族，经 NXOpen.UF 封装）

圆角/倒角（UF API 推荐，比 Builder 简单可靠，verified-working）：
```python
# 边圆角：uf.ModlFeatures.CreateBlend(半径, 边tag列表, ...)
blend_tag = uf.ModlFeatures.CreateBlend("4.0", edge_tags, 0, 0, 0, 0.0001)
# 倒角：subtype 1=单向 2=双向 3=偏置角度
chamfer_tag = uf.Modeling.CreateChamfer(1, "0.2", "0.2", "45", edge_tags)
```
（E-106）

- 官方文档：NXOpen Python Reference 12.0（`NXOpen.UF.UFModl` 类）：https://docs.plm.automation.siemens.com/data_services/resources/nx/12/nx_api/custom/en_US/nxopen_python_ref/ （E-108）

## 3. 命令行批处理可执行集（documented-not-probed）

安装目录实测存在（E-103）：

| 可执行文件 | 用途 | 状态 |
|---|---|---|
| `NXBIN\step214ug.exe` | STEP AP214 批处理导入/导出 | documented-not-probed |
| `NXBIN\step203ug.exe` | STEP AP203 | documented-not-probed |
| `NXBIN\step242.exe` | STEP AP242 | documented-not-probed |
| `NXBIN\ug_check_part.exe` | 部件诊断检查 | documented-not-probed |
| `NXBIN\massprop.exe` | 质量属性批处理 | documented-not-probed |
| `NXBIN\ugnx_batchmesher.exe` | FEA 批处理网格划分 | documented-not-probed |
| `NXBIN\ug_clearance.exe` | 装配间隙检查 | documented-not-probed |
| `NXBIN\jtpostprocessor.exe` | JT 后处理/可视化输出 | documented-not-probed |
| `NXBIN\ug_convert_part.exe` | 部件版本转换 | documented-not-probed |
| `NXBIN\attribute_list.exe` / `attribute_set.exe` | 部件属性读写 | documented-not-probed |

## 4. COM 通道（confirmed-negative）

- `software_registry.py` 中 `nx.com_prog_id = None`（E-102）；注册表无 NX COM ProgID。
- 结论：**NX 不提供 COM Automation 接口**，自动化只能走 NXOpen Journal / UF。

## 5. 环境变量（verified-working，历史实测）

来自 `run_nx_journal.py`（E-110）：
- `UGII_BASE_DIR` = NX 安装根（…\NX12.2.9\NX）
- `UGII_ROOT_DIR` = NXBIN 或 UGII
- `UGII_LIBRARY_DIR` = UGII
- `UGII_UGRAF_DIR` = `<NX>\ugraf`
- `UGII_LANG = simpl_chinese`（中文版界面）
- `UGII_COUNTRY = prc`
- 全局环境定义文件：`UGII\ugii_env.dat`、`UGII\ugii_env_ug.dat`（E-105，见 config.md）
