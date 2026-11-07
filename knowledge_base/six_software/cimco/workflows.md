# CIMCO Edit 2026 端到端工作流

> 覆盖项目级闭环中 CIMCO 的角色：接收 NC（NX CAM 后处理输出）→ FANUC Macro B 校验 → G 代码语法/模态检查 → 背绘（G00 碰撞哨兵）→ 机床仿真 → 后处理/格式转换 → DNC 传输准备。
> 与 AGENTS.md §2.D 公理对齐：**背绘检查 G00 快速进给不得高速扎入毛坯；校验 FANUC Macro B 变量逻辑（#100/#500/WHILE/DO）**。

## 闭环总图（mermaid）

```mermaid
flowchart LR
    A["NX CAM 后处理输出 .nc"] --> B["CIMCO 打开 NC"]
    B --> C["Macro B 校验<br/>#100/#500 WHILE/DO/END"]
    C --> D["G 代码语法/模态检查"]
    D --> E["背绘 Backplot<br/>G00 碰撞哨兵"]
    E --> F{"G00 高速扎毛坯?"}
    F -- 是 --> X["回 NX CAM 修改"]
    F -- 否 --> G["机床仿真 Machine Sim"]
    G --> H["后处理/格式转换"]
    H --> I["DNC 传输准备 → 机床/VERICUT"]
```

## 工作流明细

### wf_nc_validate（NC 接收→校验）
| 步 | 操作 | 命令 | 关键参数 | 检查点 |
|---|---|---|---|---|
| 1 | 打开 NC | `cimco_open_nc` | `CIMCOEdit.exe <nc>` | 文件可读 |
| 2 | Macro B 校验 | `cimco_macro_validate` | `#100/#500` 变量、WHILE/DO/END 配对（m=1/2/3，最多 3 层） | `is_valid=True`，无未闭合/错配 END |
| 3 | G 语法 | `cimco_gcode_syntax` | G/M/O token | 无非法 token |

### wf_backplot_sentinel（背绘 G00 碰撞哨兵）
| 步 | 操作 | 命令 | 关键参数 | 检查点 |
|---|---|---|---|---|
| 1 | 启动背绘 | `cimco_backplot` | Ctrl+Shift+P | 刀轨窗+程序窗分屏 |
| 2 | 选控制类型 | `cimco_backplot_setup` | Control Type = ISO Milling/Turning | 与机床匹配 |
| 3 | 逐段 G00 审查 | — | G00 快速段 | **G00 不得高速扎入毛坯 stock**（碰撞哨兵，AGENTS.md §2.D）；快速抬刀到安全高度后再水平移 |
| 4 | 异常处理 | — | 发现高速下刀 | 回 NX CAM 改安全高度/进刀方式 |

### wf_machine_sim（机床仿真）
| 步 | 操作 | 命令 | 关键参数 | 检查点 |
|---|---|---|---|---|
| 1 | 选机床 | `cimco_machine_sim` | 对应 *.mcfg（如 Haas VF2 / DMG Mori） | STL 机床部件加载 |
| 2 | 仿真 | — | 逐刀轨 | 无刀柄/夹具碰撞 |

### wf_post_dnc（后处理/格式转换→DNC）
| 步 | 操作 | 命令 | 关键参数 | 检查点 |
|---|---|---|---|---|
| 1 | 后处理 | `cimco_post_process` | 选 `Posts\Mill\fanuc.js` 等 | 输出目标控制器 NC |
| 2 | 格式转换 | `cimco_convert` | `Converters\fanuc.conv/heidenhain.conv` | 控制器方言匹配 |
| 3 | DNC 准备 | `cimco_dnc_send` | 串口/网络/FTP | 发送参数就绪 |

## 与 AGENTS.md 公理对齐声明
- §2.D（CIMCO Edit 2026）：背绘检查 G00 快速进给不得高速扎入毛坯 ✅（wf_backplot_sentinel 第 3 步）
- §2.D：校验 FANUC Macro B 变量逻辑（#100/#500/WHILE/DO） ✅（wf_nc_validate 第 2 步）

## 真实 NC 证据（Flange_Machining.nc）
- 含 `#100=62.5`（PCD 半径）、`#101/#102/#103/#104` 角度/计数器；`WHILE [#103 LE #104] DO 1` … `END 1` 循环；`G83 Z-25.0 R2.0 Q5.0 F120` 深孔啄钻；`G71 U1.5 R0.5` 粗车、`G70` 精车；`M30` 结束（E-209）。
