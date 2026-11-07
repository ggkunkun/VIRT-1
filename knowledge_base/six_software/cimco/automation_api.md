# CIMCO Edit 2026 自动化接口清单

> 通道三态：`verified-working` / `confirmed-negative` / `documented-not-probed`。
> 本轮执行通道受限（PowerShell `HISTORY_INVALID_PATH`、Bash 禁用、桌面自动化对子代理不可用），**无法现场复测**；历史已验证判定标注 `[高]（历史实测）`。

## 通道总表

| 通道 | 入口 / 路径 | 状态 | 证据 |
|---|---|---|---|
| COM Automation ProgID | 无（`com_prog_id=None`） | confirmed-negative（无 ProgID） | E-202 |
| 命令行启动打开 NC | `CIMCOEdit.exe <nc_file>` | verified-working（桥接实现 launch_in_cimco） | E-204 |
| FANUC Macro B 静态校验 | `cimco_bridge.py::validate_fanuc_macro_b(code)` | verified-working（纯 Python 实现） | E-204 |
| LLM 工具调用封装 | `cadcam_cimco_validate`（action=validate_macro/launch） | verified-working（tool_calling_specs 定义） | E-206 |
| 后处理脚本引擎 | `Posts\*.js` + `Dll\PostProcessor.dll`/`PostProcessorDLL.dll` | documented-not-probed | E-203 |
| 机床仿真 | `MachineCfg\*.mcfg` + STL 部件 | documented-not-probed | E-203 |
| DNC 串口/网络发送 | GUI 内配置 | documented-not-probed | E-203 |

## 1. COM 通道（confirmed-negative）

- `software_registry.py` 中 `cimco.com_prog_id = None`（E-202）；注册表无 CIMCO COM ProgID。
- 结论：**CIMCO Edit 不提供 COM Automation 接口**，自动化只能走「命令行拉起 + 外部静态校验」。

## 2. 命令行启动（verified-working，桥接实现）

```python
# bridges/cimco_bridge.py::CIMCOBridge.launch_in_cimco(nc_file_path)
subprocess.Popen([r"E:\仿真软件\CIMCOEdit_20260102\CIMCO 2026\CIMCOEdit\CIMCOEdit.exe", nc_file_path])
```
- 可复现命令：`CIMCOEdit.exe "D:\Virtu模型\Flange_Machining.nc"`（E-204）
- 局限：仅拉起 GUI 打开文件，**无回读/无脚本控制 API**（documented-not-probed 任何 GUI 自动化）。

## 3. FANUC Macro B 静态校验（verified-working，纯 Python）

`cimco_bridge.py::validate_fanuc_macro_b(nc_code)` 实现（E-204）：
- 逐行（跳过空行/`(` 注释/`%`）；
- 正则 `#\d+` 收集全部变量；
- `WHILE\s*\[.*\]\s*DO\s*(\d+)` 入栈；`END\s*(\d+)` 出栈配对；
- 报错：`END m` 无匹配 `WHILE DO`、`END m` 编号不匹配、`WHILE DO m` 未闭合；
- 返回 `{is_valid, errors[], variables[], variables_count, line_count}`。

测试用例（文件内 `__main__`）：
```
#100 = 50.0\n#101 = 10.0\nWHILE [#101 LE #100] DO 1\nG01 X#101 F300\n#101 = #101 + 5.0\nEND 1\nM30
```
（E-204）

## 4. LLM 工具封装（verified-working）

`tool_calling_specs.py` 定义 `cadcam_cimco_validate`（E-206）：
- `action=validate_macro`：`{code: "<G代码/Macro B 文本>"}` → 深度静态语法与逻辑校验；
- `action=launch`：`{nc_file_path: "<待打开NC路径>"}` → 在 CIMCO Edit 中打开；
- 经 `orch.dispatch("cimco", action, params)` 路由到 `cimco_bridge.py`。

## 5. 既有桥接封装局限声明

- `cimco_bridge.py` 是**外部 Python 封装**，不是 CIMCO 内置 API；
- 校验能力：Macro B 变量/循环配对 + G/M/O token 骨架（E-204）；
- **未实现**：模态组一致性深度校验、背绘坐标提取（`backplot` 能力在注册表中标注，但本轮无对应回读实现——见缺口清单）。

## 6. .NET 运行时（documented-not-probed）

- `CIMCOEdit.exe.config` 声明 `probing privatePath="dll;Msg\ToolManager"`，Dll 含 `Newtonsoft.Json.dll`、`PostProcessor.dll`、`PostProcessorDLL.dll`、`GroovingKernel.dll`、`HTKernel.dll`、`InspectConvert.dll`、`Office2016.dll`（E-203）。
- 推断 CIMCO 主程序为 .NET 程序，但**未探测**其内部可调用的类/接口。
