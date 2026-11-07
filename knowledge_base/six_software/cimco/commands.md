# CIMCO Edit 2026 关键命令表

> 表：命令 ID | 模块 | 类型 | 参数/坐标 | 说明 | 证据。
> 类型：菜单(Menu) / 快捷键(Shortcut) / API(桥接) / CLI(命令行) / 后处理脚本(Post)。

| 命令 ID | 模块 | 类型 | 参数/坐标 | 说明 | 证据 |
|---|---|---|---|---|---|
| `cimco_open_nc` | nc_editor | CLI | `CIMCOEdit.exe <nc_file>` | 打开 NC 文件 | E-204 |
| `cimco_editor_setup` | nc_editor | 菜单 | 文件\|编辑器设置 | 编辑器配置/文件类型 | E-205 |
| `cimco_macro_validate` | macro_b_check | API | `validate_fanuc_macro_b(nc_code)` | FANUC Macro B 变量/WHILE-DO-END 校验 | E-204 |
| `cimco_gcode_syntax` | gcode_check | API | G/M/O token 校验 | G 代码语法骨架检查 | E-204 |
| `cimco_backplot` | backplot | 快捷键 | Ctrl+Shift+P | 显示当前 NC 刀轨仿真/实体动画 | E-205 |
| `cimco_backplot_file` | backplot | 菜单 | Backplot\|File | 直接从磁盘背绘（不先打开） | E-205 |
| `cimco_backplot_setup` | backplot | 菜单 | Backplot Setup（选 Control Type 如 ISO Milling） | 背绘配置 | E-205 |
| `cimco_machine_sim` | machine_sim | 菜单 | 机床仿真（选 *.mcfg） | 3/5 轴机床仿真 | E-203 |
| `cimco_cnc_calc` | cnc_calc | 菜单 | CNC-Calc | 铣/车/钻参数计算 | E-203 |
| `cimco_post_process` | post_processing | Post | `Posts\Mill\fanuc.js` 等 | 后处理输出 NC | E-203 |
| `cimco_dnc_send` | dnc | 菜单 | 传输\|发送 | DNC 串口/网络/FTP 发送准备 | E-203 |
| `cimco_tool_list` | tool_lib | 菜单 | 刀具库（*.tmlib） | 刀具清单/刀补 | E-203 |
| `cimco_convert` | converters | 菜单 | 文件\|转换（*.conv） | Fanuc/Heidenhain/Sinumerik 格式转换 | E-203 |

## 可复现命令模式

```powershell
# 拉起 CIMCO 打开一个 NC 文件
& "E:\仿真软件\CIMCOEdit_20260102\CIMCO 2026\CIMCOEdit\CIMCOEdit.exe" "D:\Virtu模型\Flange_Machining.nc"
```
```python
# 桥接 Macro B 校验（纯 Python，无需 GUI）
from bridges.cimco_bridge import CIMCOBridge
r = CIMCOBridge().validate_fanuc_macro_b(open(r"D:\Virtu模型\Flange_Machining.nc", encoding="utf-8").read())
print(r["is_valid"], r["errors"], r["variables_count"])
```
（E-204/E-206）

## 公理相关命令（AGENTS.md §2.D）
- **G00 碰撞哨兵**：背绘 `cimco_backplot` 时必须逐段检查 G00 快速进给轨迹，确认无高速扎入毛坯（stock）——见 `workflows.md`。
- **Macro B 变量校验**：`cimco_macro_validate` 必须检查 `#100/#500` 与 `WHILE/DO/END` 配对。
