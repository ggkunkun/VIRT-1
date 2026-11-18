---
name: aero-closed-impeller-block
description: Machine an aero-engine closed (shrouded) impeller from a rectangular bounding block on a 5-axis machining center, including blank envelope, OP10/OP20/OP30/OP40/OP50 sequence, lollipop channel access, flip setup and acceptance gates.
metadata:
  version: "1.0.0"
  owner: "Virtu模型 CAD/CAM"
  supported-consequence-levels: "manufacturing_planning execution_adjacent"
  short-description: Block-to-closed-impeller 5-axis process SOP
---

# 航空发动机封闭式叶轮：从包容块到成品

当任务是从**矩形毛坯（包容块）**加工封闭式（带前后盖板）叶轮，或需要审查这类工艺/NC/仿真时使用本技能。

## 核心原则

1. **毛坯必须是包容块**：长方体，六面完整包住成品 + 余量；禁止把毛坯定义成圆柱/回转体/预车盘料。
   圆柱只能在 OP10 之后作为"预成形轮廓"出现，不能当作毛坯本身。
2. 毛坯尺寸 = 成品包络 + 余量：顶部 3 mm、底部 5 mm、四周 3 mm（可按材料/装夹调整，但必须能被实测证明"成品点全部在毛坯内"）。
3. 工件坐标系放在**毛坯上表面中心**，Z0 = 上表面；所有切削 Z ≤ 0。
4. 封闭叶轮的流道被盖板封闭：**刀具只能从外圆（OD）流道出口进出**，禁止从上方垂直下刀进流道。
5. **全流程铣削**：面、外圆、流道、背面全部由立铣刀/棒棒糖刀的 G01/G02/G03 插补完成；
   圆形刀路是"立铣刀圆弧插补铣削"，不是车削。禁止任何车削逻辑与代码。

## 标准工序

| 工序 | 目标 | 关键约束 |
|---|---|---|
| OP00 备料 | 六面铣平、倒角、去打应力 | 记录实际尺寸与材质批次；毛坯包络实测 |
| OP10 面/外圆 | 立铣刀铣顶面、把方块四角用 G02/G03 圆弧插补预成形到 r≈1.02×成品外径 | 只到夹持线上方（虎钳顶部以上 ≥1 mm）；不是车削 |
| OP20 流道粗加工 | 从 OD 槽口进入，分层/插铣/动态铣去流道主体 | 层深 ≤ 刀具直径；留 0.3–0.5 mm 半精余量；不得从盖板侧下刀 |
| OP30 半精 | 棒棒糖刀（lollipop）5 轴联动清流道 | `G43.4` RTCP；刀具伸出 ≥ 流道深度；过流道出口时刀杆不碰盖板 |
| OP40 精加工 | 沿流线（scoop milling）精铣叶片与轮毂/盖板 | 等切削载荷；Ra ≤ 0.8（叶轮通常再抛光/AFM） |
| OP50 翻面 | 内胀芯轴撑中心孔，翻 180°：铣背面余量 + 下部外圆 | 夹具顶面必须低于最低刀路 ≥1 mm；下部 25 mm 夹持区在此工序去除 |
| OP60 检验 | 三坐标叶型、超声壁厚、动平衡、VERICUT Auto-Diff | 红=过切必须停；蓝=残料补半精 |

## 硬规则（违反任一条即判不合格）

- 毛坯定义成圆柱/回转体 ⇒ **工艺定义错误**，必须回退为包容块。
- 成品任一点落在毛坯外 ⇒ 毛坯不合格（用 2 万点采样证明 0 点在外）。
- 从盖板一侧垂直下刀进封闭流道 ⇒ 撞刀/报废，必须改为 OD 槽口进入。
- 刀具/刀杆扫掠与盖板、虎钳、垫高座干涉 ⇒ 必须改刀轴矢量或加长刀具，不得"仿真时关掉碰撞检查"。
- 未翻面就加工到夹持区以下 ⇒ 撞虎钳；夹持区只能留给 OP50。
- 未实测就宣称"无报错" ⇒ 违反证据门（静态语法 ≠ 仿真通过）。
- **出现任何车削代码或车削逻辑 ⇒ 判不合格**：`G96/G97/G99`、`G70/G71/G72/G76`、
  `G32/G33`（螺纹）、恒线速、`M19` 主轴定向车削；机床必须是铣削中心，不得切到车床模式。
- 面/外圆的圆形刀路必须由**立铣刀圆弧插补**生成（G02/G03 + I/J 或 R，主轴 M03 铣削），
  不得解释为"车刀车圆"。

## 验收门

| 门 | 判据 | 反证（必须能红） |
|---|---|---|
| G-BLOCK-ENVELOPE | 成品表面 20000 采样点全部在毛坯内 | 掺入 1 个外包点 ⇒ 必须 FAIL |
| G-WCS-TOP | 坐标系原点在毛坯上表面中心，Z0=上表面 | 原点放底面 ⇒ 必须 FAIL |
| G-CHANNEL-ACCESS | 刀杆直径+伸出在流道最深处的间隙 ≥0，且不穿盖板 | 用 Ø8/伸出 40 的刀跑 70 深流道 ⇒ 必须 FAIL |
| G-FIXTURE-CLEAR | 最低刀路 Z − 钳口/夹具顶面 ≥1 mm | 刀路降 2 mm ⇒ 必须 FAIL |
| G-ZERO-ERROR | 静态语法 + FANUC 语法校验 + 仿真日志 0 error/0 collision | 删一个 `M30` 或让 G00 下扎 ⇒ 必须报红 |
| G-MILL-ONLY | NC 中 `G96/G97/G99/G70/G71/G72/G76/G32/G33/M19` 计数全为 0；全部切削为 G01/G02/G03 + M03 | 插入一行 `G96 S200` ⇒ 必须报红 |

## 失败模式（真实教训）

- 把毛坯建成圆柱，视觉上"能包住"，但不符合包容块定义，且无法证明四角余量 ⇒ 用户直接判错。
- 用面铣环形刀路当"粗加工"，四角余料未去，流道入口在 45° 方向扎进实体。
- 刀路只到 Z−57，却把虎钳顶面放在 −57.85：只剩 0.85 mm，材料波动就撞。
- 翻面后用圆柱当残余毛坯：残余料其实是方形块的下半段，形状错了后面全错。
- 坐标系放底面，Z 全为正，仿真在空气中切削，"无报错"但没加工。

## 本例映射（AE-CI-258 / NMV1500 / FANUC 30iM）

- OP1+OP2：`E:\vericut_impeller_run\impeller.nc`（Z0=毛坯顶面，切削 0…−57.0，钳口顶面 −57.85）
- OP3 翻面：`E:\vericut_impeller_run\OP3_FLIP.nc`（0…−25.5，块底 −25.85，芯轴顶 −32.85）
- OP3 工位：`E:\vericut_impeller_run\OP3.vcproject`
  - Stock = **264.06×264.06×25.85 包容块**（world 127.00…152.85）
  - Design = 翻转 180°（world 73.00…147.85）
  - Fixture = Ø76 内胀芯轴 + Ø200 法兰（world 48…120）
- 余量：顶 3 mm、底 5 mm、四周 3 mm；毛坯 264.06 对方形包络 258.06。
- 铣削专用实测：两个程序 `G96/G97/G99/G70/G71/G72/G76/G32/G33/M19` 计数全为 **0**；
  全部切削为 G01（1226 行）+ G02/G03（59 行）圆弧插补，主轴 M03 铣削。

## 参考

- 5-Axis Impeller Machining: Complete Guide & Best Practices — closed impeller 流道访问受限、需长伸出刀具
  https://feeds.cncprogrammingsolutions.com/blog/5-axis-impeller-machining
- CAD/CAM Strategies for Complex Impeller Machining — 原点在轮毂端面孔中心；粗加工去 80–90% 材料；插铣/层切
  https://tikprecision.com/blog/cad-cam-strategies-for-complex-impeller-machining.html
- Five-Axis Machining for Centrifugal Impellers — 毛坯为锻件圆柱/方块，装于转台/胎具，先粗加工流道
  https://centrifugal-impeller.com/five-axis-machining-for-centrifugal-impellers/
- Closed 3D Flow Impeller Manufacturing — 从实心毛坯五轴整体铣：钻、粗、半精、清根、精
  https://www.totemmach.com/Closed-Three-Dimensional-Flow-Centrifugal-Impeller-Manufacturing-id04868635.html
- 闭式叶轮精加工刀轨规划（专利）— 分区、叶型重构、刀心点与刀轴矢量
  https://zhuanli.tianyancha.com/785df4ec01ac4775b2cc771dd801309c
