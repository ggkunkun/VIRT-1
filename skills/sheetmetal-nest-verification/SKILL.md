---
name: sheetmetal-nest-verification
description: 套料/下料排样的独立复核——不看引擎自报数字，重新读回排样 DXF 产物，用 shapely 几何布尔运算验重叠、越界、割缝间距、轮廓闭合，并重算利用率与抬头自报值对账。当调用 cadcam_sheetmetal_nest、导出排样 DXF、或要放行下料/激光/冲裁工序时使用。
metadata:
  version: "1.0.0"
  owner: "Virtu 自建（GitHub 无可落位的套料技能源）"
  tools: [cadcam_sheetmetal_nest, cadcam_autocad_draw, cadcam_universal_geometry]
  executor: scripts/verify_nest.py
  evidence: "引擎产出的 12 件排样判 NEST_OK(重算利用率 42.075% 与抬头 42.08% 一致)；人为叠加/移出版面后判 NEST-OVERLAP + NEST-OUT-OF-SHEET"
---

# 钣金真实展开套料复核

## 执行
```
python skills/sheetmetal-nest-verification/scripts/verify_nest.py <排样.dxf> --margin 5.0 --kerf 5.0 --json-out <报告.json>
```
退出码 0=几何合格，1=不合格，2=读图失败。读的是图层 `STOCK_FRAME`(母板框) 与 `PARTS_CUT`(零件轮廓)，正是 `cadcam_sheetmetal_nest(output_dxf=...)` 写出的图层。

## 判据
- `NEST-OVERLAP`：任意两件零件多边形交面积 > 0 → 一块板切出两件重叠件，直接废。
- `NEST-OUT-OF-SHEET`：越出母板框 → 行程/板材不够，回改板幅或减件。
- `NEST-KERF`：间距 < 设定割缝/桥距 → 热变形与切边干涉风险。
- `NEST-OPEN-CONTOUR`：轮廓未闭合 → 面积与展开都是假数，激光/水刀也不会认。
- `NEST-REPORT-MISMATCH`：抬头自报利用率与按产物重算差 > 0.5 个百分点 → 报数字的那一侧错了，不得沿用。
- `NEST-SHEET-FRAME`：母板框缺失、多于一条或未闭合 → 基准都没了，其余判定作废。

## 硬规则
- 面积必须来自**真实展开**（折弯扣除/中性层已算过），投影面当展开面积会让利用率虚高。
- 利用率必须同时给"全板"和"最小包围"两个口径，只报一个都是在挑好看的数字。
- 复核以产物为准：`optimize_nesting` 返回 `placed_count` 再漂亮，DXF 读不回几何就是没排。
- 任何 1 级失败 → 回 `cadcam_sheetmetal_nest` 改 margin/板幅/件数，禁止手工挪图框凑通过。

## 输出契约
`{dxf, sheet{length,width}, part_count, part_area_mm2, utilization_full_sheet_pct, utilization_bounding_pct, claimed_utilization_pct, claimed_vs_recomputed_abs_diff_pct, problems[], verdict}`，`verdict ∈ NEST_OK / NEST_INVALID / READ_FAILED`。
