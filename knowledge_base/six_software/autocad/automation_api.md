# AutoCAD 2026 — 自动化接口清单

> 通道状态三态：`verified-working`（历史实测）/ `confirmed-negative` / `documented-not-probed`。桥接证据：`D:\Virtu模型\bridges\autocad_bridge.py`（E-AC-02）。

## 1. 通道总表

| 通道 | 入口 / ProgID / 路径 | 状态 | 证据 |
|---|---|---|---|
| COM ActiveX（活 GUI） | ProgID `AutoCAD.Application`（注释提及 `AutoCAD.Application.25`） | verified-working（桥接 connect/send_lisp 实测） | E-AC-02 |
| COM 附着运行实例 | `win32com.client.GetActiveObject("AutoCAD.Application")` | verified-working（桥接首选，失败则 Dispatch 新建） | E-AC-02 |
| COM 新建实例 | `win32com.client.Dispatch("AutoCAD.Application")` + `Visible=True` | verified-working（桥接回退路径） | E-AC-02 |
| ActiveX SendCommand | `AcadDocument.SendCommand(string)` | verified-working（桥接 send_lisp_command） | E-AC-02, E-AC-08 |
| AutoLISP 执行 | 命令行 LISP 表达式 / `.lsp` 文件 | verified-working（桥接落盘 scratch/temp_command.lsp） | E-AC-02 |
| accoreconsole 无头批处理 | `D:\cad2026\AutoCAD 2026\accoreconsole.exe /s <scr> [/i <dwg>]` | verified-working（桥接 run_headless_script 子进程） | E-AC-02, E-AC-09 |
| ezdxf 文件级无头 | Python `import ezdxf`（不启动 AutoCAD） | verified-working（桥接 create_headless_dxf） | E-AC-02 |
| 命令行脚本 ScriptPro | AutoCAD ScriptPro 调 accoreconsole 后台 | documented-not-probed（官方文档化，本轮未用） | E-AC-09 |
| 环境变量 | AutoCAD 支持路径 ACAD / 用户配置目录 | documented-not-probed（本轮未枚举） | — |

## 2. COM ActiveX 关键对象与方法签名

> 桥接实际调用（E-AC-02）。官方 SendCommand 文档见 E-AC-08。

### 2.1 应用对象 `AcadApplication`
```python
import win32com.client, pythoncom
pythoncom.CoInitialize()
acad_app = win32com.client.GetActiveObject("AutoCAD.Application")  # 优先附着
# 失败回退：
acad_app = win32com.client.Dispatch("AutoCAD.Application")
acad_app.Visible = True
```
- `AcadApplication.ActiveDocument -> AcadDocument`：当前活动文档。
- `AcadApplication.Documents`：文档集合（`Documents.Count` / `Documents.Open(path)`）。E-AC-07。

### 2.2 文档对象 `AcadDocument`
```python
doc = acad_app.ActiveDocument
doc.SendCommand(f"{lisp_code}\n")     # 末尾 \n = 回车
# 桥接约定：未连接时把 LISP 落盘 scratch\temp_command.lsp 供无头/手动执行
```
- `AcadDocument.SendCommand(Command As String)`：向命令行发一条命令串；串内须按提示顺序给参数，空格/回车等价。官方：`Document.SendCommand`，Windows only（E-AC-08）。
- `AcadDocument.ModelSpace`：模型空间（`ModelSpace.Count` 用于校验实体数）。E-AC-07。

### 2.3 稳定性注意（领域技能实测经验）
- COM 偶发「call was rejected by callee」或文档集合不可读：短等待重试；持续则关闭多余 AutoCAD 窗、重启。
- 若 AutoCAD 只开 Start 页或 `Documents.Count`/`ActiveDocument.Name`/`ModelSpace` 报 `<unknown>`，用干净 `acad.exe` 重启进程。
- `Documents.Open()` 有时返回方法代理 `<COMObject Open>`，打开后须用 `ActiveDocument` 并校验 `ActiveDocument.ModelSpace.Count`。E-AC-07。

## 3. AutoLISP 通道

- 命令行执行：`SendCommand("(command \"_line\" p1 p2 \"\")\n")` 等；桥接 `send_lisp_command` 直接发表达式串。E-AC-02。
- 支持文件目录自带标准 LISP：`D:\cad2026\AutoCAD 2026\Support\acad2026.lsp`、`Support\zh-CN\acad2026doc.lsp`、`mvsetup.lsp`、`edge.lsp`、`3d.lsp`、`3darray.lsp` 等（E-AC-06）。
- AutoLISP 是 AutoCAD 原生脚本方言；`(command ...)` 调命令，`entmake` 直接建实体。E-AC-08。

## 4. accoreconsole 无头批处理

```
accoreconsole.exe /i <input.dwg> /s <script.scr> [/l <lang>] [/product <prod>] [/isolate <userid> <userDataFolder>] [/readonly] [/p[rofile] <profile>]
```
- `/i`：指定在其上跑脚本的图纸路径；`/s`：脚本文件路径；`/l`：语言包版本；`/product`/`/isolate`/`/readonly`/`/profile`：附加开关。E-AC-09。
- 桥接 `run_headless_script`：`[accoreconsole_exe, "/s", script_path] + (["/i", dwg] if dwg)`，`subprocess.run(capture_output, timeout=120)`，按 returncode==0 判成功。E-AC-02。
- 用途：批量转 DXF、批处理标注/出图，无需 GUI。

## 5. ezdxf 文件级通道（不启动 AutoCAD）

```python
import ezdxf
doc = ezdxf.new("R2018")           # AC1032 = AutoCAD 2018 DXF 版本
msp = doc.modelspace()
doc.layers.add(name="OUTLINE", color=7)
doc.layers.add(name="CENTER", color=1, linetype="CENTER")
doc.layers.add(name="DIMENSION", color=3)
msp.add_circle((x,y), r, dxfattribs={"layer":"OUTLINE"})
msp.add_line(p1, p2, dxfattribs={"layer":"OUTLINE"})
msp.add_text("...", dxfattribs={"layer":"DIMENSION","height":3.5}).set_placement(pos)
doc.saveas(path)
```
- 桥接 `create_headless_dxf` 实测：R2018 版本、建层、circle/line/text 三类图元、`saveas`。E-AC-02。
- 优势：零 GUI、毫秒级、可复现；缺点：写的是 DXF（非原生 DWG），复杂代理对象/注释型标注需 AutoCAD 复核。E-AC-07。

## 6. 判死/未复测通道

| 通道 | 判定 | 依据 |
|---|---|---|
| accoreconsole 中跑 -IFCEXPORT 等特定命令 | documented-not-probed（官方有崩例记录，本轮未测） | Autodesk 支持文章：命令拼写/路径分隔符错误会导致 accoreconsole 崩溃（E-AC-09） |
| 本机 COM 类型库自动注册状态 | documented-not-probed（registry 探测由历史 registry.check_com_registration 做过） | software_registry.com_registered 历史流程，本轮未读注册表 |
