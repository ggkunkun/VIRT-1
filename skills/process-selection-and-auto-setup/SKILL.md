---
name: process-selection-and-auto-setup
description: Decide milling vs turning vs 5-axis (or mill-turn) from measured part geometry, decompose the job into a task DAG, then automatically assemble the VERICUT station step by step (machine, fixture, stock, design, NC, tools, offsets, simulation).
metadata:
  version: "1.0.0"
  owner: "Virtu模型 CAD/CAM"
  supported-consequence-levels: "manufacturing_planning execution_adjacent"
  short-description: 工艺判定 + 任务拆解 + 机床自动装配
---

# 工艺判定、任务拆解与机床自动装配

当用户说"自动识别该铣还是该车""自动找最优工艺""先拆解任务再自动设置机床"时使用本技能。

## 1. 工艺判定（先测后判）

先跑实测，不看零件名：

```
python scripts/process_selector.py --design <design.stl> --report process_decision.json
```

输出指标与判据：

| 指标 | 含义 | 判定作用 |
|---|---|---|
| `rotationality` | 各 Z 层半径角向离散度的补值（1=回转体） | ≥0.8 才考虑车削 |
| `radius_spread` | (p95−p5)/p95 的层均值 | 越大越不可能车 |
| `blade_count_fft` | r(θ) 频谱主频 | ≥6 表示有周期叶片/流道 |
| `flat_face_ratio` | |nz|>0.7 面积占比 | 高则适合铣端面 |
| `height_over_diameter` | 高/最大直径 | 深腔判断 |

决策表：

| 条件 | 结论 |
|---|---|
| 回转度 ≥0.8 且 无叶片周期 | 车削 |
| 叶片数 ≥6 或 半径离散 >0.15 | **五轴铣削**（封闭流道/负角必须多轴） |
| 回转度 0.5–0.8 且有回转特征 + 铣削特征 | 车铣复合 |
| 其余 | 三轴铣削 |

**反例（实测）**：AE-CI-258 封闭叶轮 → 回转度 0.28、半径离散 0.36、FFT 主频 32（16 叶片 2 阶）、
评分 turning −12 / 3axis 30 / **5axis 90.4** ⇒ 判定五轴铣削，车削不可行。

## 2. 任务拆解（固定 10 步，每步带验收）

| ID | 任务 | 验收（必须可复核） |
|---|---|---|
| T1 | 零件识别与工艺判定 | `process_selector.py` 输出 recommended + 指标 |
| T2 | 机床/控制系统选择 | 行程覆盖包络；五轴选 B/C；写入工位并回读 |
| T3 | 毛坯自动识别 | `auto_stock_recognition.py`；20000 点 `outside=0`；尺寸=包络+余量 |
| T4 | 夹具与 WCS | 夹具底面=台面，毛坯底面=夹具顶面；WCS 在毛坯上表面中心 |
| T5 | 刀具库 | 直径/伸出满足流道深度；棒棒糖刀 R 与圆角匹配 |
| T6 | 刀路与 NC | 封闭流道只从 OD 槽口进入；G43.4 开、G49 关 |
| T7 | NC 静态校验 | 无车削代码；G00 不下扎；主轴先开；M30；语法 0 错 |
| T8 | VERICUT 工位装配 | 机床/控制/夹具/毛坯/设计/NC/刀具/偏置齐全，XML 可解析 |
| T9 | 仿真与偏差 | 日志 0 error/0 collision；Auto-Diff 无红 |
| T10 | 交付 | 模型 + 仿真报告 + 参数校验清单，全部带实测证据 |

任务树按依赖串行：T1→T2→T3→T4→T5→T6→T7→T8→T9→T10；
T3 与 T5 可并行，T9 未过不得进 T10。

## 3. 毛坯自动识别

```
python scripts/auto_stock_recognition.py --design design.stl --mode blank \
    --side 3 --top 3 --bottom 5 --fixture-top 70 \
    --out stock.stl --report stock.json [--patch-project proj.vcproject]
```

- `blank`：完整包容块；`--flip-x` 用于翻面工序；底面放 `--fixture-top`
- `residual`：只生成 `--z-bottom..--z-top` 区间的残余块（翻面 OP3）
- 报告含：设计包围盒、毛坯尺寸、世界 Z、`stock_matrix_origin_z`（Attach=-100 时）、
  `containment.outside`（必须 0）、`min_margin_mm`
- 生成的是**长方体**；禁止用圆柱替代

VERICUT 原生等价功能（可选）：
`vericut "vcp=xxx.vcproject" STOCK_BLOCK_FROM_DESIGN_EXTENT batch`（按设计范围建块，无余量，
需再补余量）；界面路径：Configure Models → Block from Model File Extent。

## 4. 机床自动装配（VERICUT）

按顺序执行，每步失败即停：

1. **机床/控制**：拷贝目标工程 → 确认 `<Machine>`/`<Control>` 指向 `.mch`/`.ctl` 且文件存在。
2. **Attach 链**：读取 `Attach` 的 Position（本例 Z=-100），后续所有世界 Z 以此换算。
3. **夹具**：夹具模型底面放台面（world -100）；顶面 = 毛坯底面支撑面。
4. **毛坯**：用第 3 节脚本生成并 `--patch-project`，回读 `File` 与 `MatrixOrigin Z`。
5. **设计**：翻面工序用 `design_flip.stl`（绕 X 180°），矩阵按“成品顶面 = 块顶 − 顶余量”落位。
6. **NC**：先过 T7 静态校验，再改 `<NCPrograms>` 的 File；确认 `Use="on"`。
7. **刀具**：T1 D16、T2 D10 棒棒糖；伸出 ≥ 流道深度；`.tls` 中直径与 NC 注释一致。
8. **偏置**：G54 = Spindle to Stock（Z0 = 毛坯上表面中心）；回读工位偏置表。
9. **保存并解析**：`xml.etree` 解析工程；输出每步 PASS/FAIL 的 `station_setup_log.json`。
10. **物理一致性**：`verify_scene_physics.py` 检查支撑链、悬空、穿模、夹持间隙、行程、材质密度；
    任何一项 FAIL 不得进入仿真。
11. **仿真**：批量或 GUI 跑 NC；日志 0 error/0 collision 才算 T9 通过。

## 5. 硬规则

- 判定必须来自实测指标，不得按文件名/经验直接下结论。
- 毛坯必须是包容块；圆柱只能作为预成形轮廓。
- 任何工序出现 `G96/G97/G99/G70/G71/G72/G76/G32/G33/M19` ⇒ 判为车削混入，整单退回。
- WCS 必须在毛坯上表面中心；Z0=上表面。
- 夹具/毛坯/设计/NC 任一未落位 ⇒ 不得宣称"机床已设置好"。
- 未跑仿真日志 ⇒ 不得宣称"0 报错"。
- 场景必须过物理一致性：支撑链连续、无悬空、无穿模（重叠体积 ≤1 mm³）、夹持间隙 0..1 mm、
  毛坯包络在行程内、每个角色有材质密度；任一项 FAIL 不得进入仿真。

## 6. 失败模式

- 只看"圆"就判车削：叶轮外圆是圆的，但内部 16 条封闭流道车刀进不去。
- 毛坯用圆柱代替包容块：无法证明四角余量，翻面后残余料形状也错。
- 工位只改了 Stock 文件，没改矩阵 ⇒ 毛坯悬空或埋进台面。
- NC 用 G54 但工位偏置是 G57 ⇒ 刀路整体偏移。
- 仿真日志没跑就写"无碰撞"。

## 7. 参考

- VERICUT Block from Model File Extent（按模型范围自动建块）
  https://help.vericut.com/4_vericut_help/3.1.09_configure_models_branch_menu
- VERICUT STOCK_BLOCK_FROM_DESIGN_EXTENT 命令
  https://help.vericut.com/automating_vericut/command_line_options
- Cimatron Stock：按零件生成包围盒/最小包围圆柱
  https://help.cimatron.com/en/2026/stock_options_and_results.htm
- NX CAM Bounding Block（毛坯包围块）
  https://www.janus-engineering.com/dach_en/news/press-media/press-details/news/nx-cam-quicktip-save-blank-material-in-siemens-nx
- 闭式叶轮五轴整体铣削工艺
  https://www.totemmach.com/Closed-Three-Dimensional-Flow-Centrifugal-Impeller-Manufacturing-id04868635.html
