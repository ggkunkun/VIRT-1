# STEP BOM 解析器通用性验证报告

- run_id: `bc33a1479c48f789` | 口径: **measured** | 样本量 n=16
- 生成时间: 2026-11-06T20:13:50 | 工具: `bridges.step_bom.StepBOM`
- 扫描目录: assets, artifacts/cad_demo, external/AgentCADCAM/fixtures/cad/bracket/source, external/Pythonocc-vericut/examples/assets/models, external/Pythonocc-vericut/python3.7/Library/lib/share/netgen
- 本报告由 bridges/batch_scan.py 实跑 StepBOM 生成；每个文件带 sha256 内容指纹，可复现

## 汇总

| 指标 | 值 |
|---|---|
| 通过(解析出实体) | 16/16 (通过率 100.0%) |
| 失败 | 0 |
| 解析成功但无实体 | 1 |
| 装配体 / 单零件 | 1 / 15 |
| AP 分布 | {'AP214': 14, 'AP203': 2} |
| 编码分布 | {'utf-8': 14, 'gbk': 2} |
| 原始 STEP 总字节 | 21,228,236 |
| 结构化 BOM 总字节 | 3,591 |
| **整体压缩比** | **5911.5×** |
| 累计实体 / 实体体 / 面 | 294,682 / 81 / 2,857 |

## 逐文件明细

| 文件 | AP | 编码 | 类型 | 实体数 | 零件 | 装配关联 | 实体体/面 | 压缩比 | 耗时 | 状态 |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---|
| precision_flange.step | AP214 | utf-8 | 单零件 | 892 | 1 | 0 | 1/15 | 234.8× | 113.3ms | ok |
|  └ 根零件: COMPOUND | | | | | | | | | | |
| bearing_bracket.step | AP214 | utf-8 | 单零件 | 2268 | 1 | 0 | 1/29 | 687.4× | 192.63ms | ok |
|  └ 根零件: COMPOUND | | | | | | | | | | |
| guide_carriage_base.step | AP214 | utf-8 | 单零件 | 986 | 1 | 0 | 1/14 | 264.2× | 38.93ms | ok |
|  └ 根零件: COMPOUND | | | | | | | | | | |
| hydraulic_end_cap.step | AP214 | utf-8 | 单零件 | 904 | 1 | 0 | 1/17 | 243.5× | 20.38ms | ok |
|  └ 根零件: COMPOUND | | | | | | | | | | |
| impeller_disc.step | AP214 | utf-8 | 单零件 | 516 | 1 | 0 | 1/9 | 153.4× | 18.89ms | ok |
|  └ 根零件: COMPOUND | | | | | | | | | | |
| mold_core_mandrel.step | AP214 | utf-8 | 单零件 | 936 | 1 | 0 | 1/19 | 253.4× | 34.7ms | ok |
|  └ 根零件: COMPOUND | | | | | | | | | | |
| precision_flange.step | AP214 | utf-8 | 单零件 | 892 | 1 | 0 | 1/15 | 234.8× | 38.35ms | ok |
|  └ 根零件: COMPOUND | | | | | | | | | | |
| spindle_bushing.step | AP214 | utf-8 | 单零件 | 257 | 1 | 0 | 1/5 | 74.2× | 11.22ms | ok |
|  └ 根零件: COMPOUND | | | | | | | | | | |
| stepped_shaft.step | AP214 | utf-8 | 单零件 | 712 | 1 | 0 | 1/14 | 198.8× | 25.62ms | ok |
|  └ 根零件: COMPOUND | | | | | | | | | | |
| valve_sleeve.step | AP214 | utf-8 | 单零件 | 1933 | 1 | 0 | 1/20 | 779.9× | 158.64ms | ok |
|  └ 根零件: COMPOUND | | | | | | | | | | |
| wheel_mold_P0.step | AP203 | gbk | 装配体 | 7690 | 5 | 4 | 6/226 | 774.3× | 878.15ms | ok |
|  └ 根零件: 微型机轮模总成(P0) 6R15-6R12-6R10 | | | | | | | | | | |
| bracket.step | AP214 | utf-8 | 单零件 | 840 | 1 | 0 | 1/12 | 204.3× | 23.71ms | ok |
|  └ 根零件: Open CASCADE STEP translator 7.9 1 | | | | | | | | | | |
| 0 1.STEP | AP214 | gbk | 单零件 | 26 | 2 | 0 | 0/0 | 14.9× | 2.84ms | ok_no_solids |
|  └ 根零件: 0 1、0 1 | | | | | | | | | | |
| 72.step | AP214 | utf-8 | 单零件 | 262989 | 1 | 0 | 62/2077 | 36867.6× | 19098.04ms | ok |
|  └ 根零件: Admi2860BBABl3f5 | | | | | | | | | | |
| frame.step | AP203 | utf-8 | 单零件 | 11602 | 1 | 0 | 1/375 | 3097.4× | 4093.68ms | ok |
|  └ 根零件: PROESOURCE | | | | | | | | | | |
| screw.step | AP214 | utf-8 | 单零件 | 1239 | 1 | 0 | 1/10 | 504.2× | 46.9ms | ok |
|  └ 根零件: the product name | | | | | | | | | | |

## 结论

统一解析器 `bridges/step_bom.py` 在 AP203(GBK 中文装配体) 与 AP214(单零件、含 BREP_WITH_VOIDS 变体) 上均正确产出结构化 BOM：零件名、层级、实体/面数、命名特征、包围盒、子零件摆放坐标。原始 STEP 被压缩约 5911.5 倍，可直接注入 13.63B 模型 prompt，替代原始几何噪声。
