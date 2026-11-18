# 数控加工仿真系统验证报告 — AE-CI-258

- 生成时间：2026-11-18 21:50:04
- 零件：航空发动机封闭式叶轮（TC11）
- 毛坯：264.06×264.06×82.85 mm，包容块，唯一实例
- 口径：所有结论标注 basis；未实测项写“未测”，不以估算冒充实测。

## 1. 配置合法性（标准区间）

| 判据 | 结果 | 实测/证据 | 规则 |
|---|---|---|---|
| SAFE-Z | PASS | safe_z=10.0 mm | ≥5.0 mm |
| RAPID-REDUCTION | PASS | rapid_reduction=5.0 mm | ≥2.0 mm |
| CLAMP-BAND | PASS | clamp_band=24.0 mm | ≥20.0 mm |
| STOCK-MARGIN-SIDE | PASS | side=3.0 mm | 2.0..5.0 mm |
| STOCK-MARGIN-TOP | PASS | top=3.0 mm | 2.0..5.0 mm |
| STOCK-MARGIN-BOTTOM | PASS | bottom=5.0 mm | 3.0..8.0 mm |
| STOCK-SIZE | PASS | {'stock': [264.06, 264.06, 82.85], 'design': [258.06, 258.06, 74.85]} | 毛坯 = 设计包络 + 侧 3 / 顶 3 / 底 5 |
| STOCK-CHAMFER-CLEARANCE | PASS | chamfer=2.0 < bottom_margin=5.0 | 底倒角不得侵入设计包络（否则包容性失效） |
| ALLOW-ROUGH_RADIAL | PASS | rough_radial=1.5 mm | 0.8..2.5 mm |
| ALLOW-ROUGH_AXIAL | PASS | rough_axial=1.5 mm | 0.8..2.5 mm |
| ALLOW-FINISH_RADIAL | PASS | finish_radial=0.3 mm | 0.15..0.5 mm |
| ALLOW-FINISH_AXIAL | PASS | finish_axial=0.2 mm | 0.1..0.4 mm |
| ALLOW-CORNER | PASS | corner=0.8 mm | 0.3..1.5 mm |
| OP1-VC | PASS | Vc=35.2 m/min (D16 @ 700 rpm) | rough 区间 20.0..45.0 m/min |
| OP1-FZ | PASS | fz=0.114 mm/z (F320 / 700 / 4刃) | rough 区间 0.03..0.12 mm/z |
| OP1-RPM-LIMIT | PASS | 700 ≤ 12000.0 | 主轴上限 |
| OP2-VC | PASS | Vc=29.8 m/min (D10 @ 950 rpm) | rough 区间 20.0..45.0 m/min |
| OP2-FZ | PASS | fz=0.058 mm/z (F220 / 950 / 4刃) | rough 区间 0.03..0.12 mm/z |
| OP2-RPM-LIMIT | PASS | 950 ≤ 12000.0 | 主轴上限 |
| OP3-VC | PASS | Vc=40.2 m/min (D16 @ 800 rpm) | finish 区间 30.0..60.0 m/min |
| OP3-FZ | PASS | fz=0.075 mm/z (F240 / 800 / 4刃) | finish 区间 0.02..0.08 mm/z |
| OP3-RPM-LIMIT | PASS | 800 ≤ 12000.0 | 主轴上限 |
| CPK-MIN | PASS | Cpk_min=1.33 | ≥1.33（PPAP 量产下限） |
| CHANGEOVER-TARGET | PASS | target=15.0 min | ≤15 min |
| T1-LIFE | PASS | config=45.0 / tool=45.0 | 刀具寿命目标差 ≤15 min（避免换刀策略冲突） |
| T2-LIFE | PASS | config=40.0 / tool=40.0 | 刀具寿命目标差 ≤15 min（避免换刀策略冲突） |
| MACHINE-prod_5ax_fanuc_0imf-RTCP | PASS | supports_rtcp=True | 五轴工序要求 RTCP |
| MACHINE-prod_5ax_siemens_840dsl-RTCP | PASS | supports_rtcp=True | 五轴工序要求 RTCP |
| MACHINE-prod_5ax_hnc8-RTCP | PASS | supports_rtcp=True | 五轴工序要求 RTCP |

配置门：**PASS** （29 项，失败 0 项）

## 2. 机床能力与工序适配

| 机床 | 控制系统 | 量产可用 | 行程(mm) | 说明 |
|---|---|---|---|---|
| prod_5ax_fanuc_0imf | FANUC 0i-MF | True | X-365.0..365.0 / Y-255.0..255.0 / Z-300.0..450.0 | 量产可用 |
| prod_5ax_siemens_840dsl | SINUMERIK 840D sl | True | X-365.0..365.0 / Y-255.0..255.0 / Z-300.0..450.0 | 量产可用 |
| prod_5ax_hnc8 | HNC-8 | True | X-365.0..365.0 / Y-255.0..255.0 / Z-300.0..450.0 | 量产可用 |
| training_rig_nmv1500 | FANUC 30iM（培训介质） | False | X-210.0..210.0 / Y-105.0..105.0 / Z-75.0..390.0 | Y 行程 [-105.0, 105.0] 覆盖不足（需 ±145），禁止用于 Ø264 毛坯；行程门=FAIL，违规 3040 点 |

## 3. 三方言 NC 与审查结果

| 工序 | 方言 | 机床 | 行数 | SHA256 | 审查 | 节拍(s) | 坐标回读误差 |
|---|---|---|---|---|---|---|---|
| OP1 | fanuc | prod_5ax_fanuc_0imf | 183 | 144d42294d88 | PASS | 7336.5 | 0.0 |
| OP2 | fanuc | prod_5ax_fanuc_0imf | 1199 | db525900ff4d | PASS | 3251.2 | 0.000494 |
| OP3 | fanuc | prod_5ax_fanuc_0imf | 86 | b158538d5c20 | PASS | 3496.6 | 0.0 |
| OP1 | siemens | prod_5ax_siemens_840dsl | 175 | 248325282129 | PASS | 7336.5 | 0.0 |
| OP2 | siemens | prod_5ax_siemens_840dsl | 1193 | 7806d05e9ce7 | PASS | 3251.2 | 0.000494 |
| OP3 | siemens | prod_5ax_siemens_840dsl | 76 | 07d91bee6aad | PASS | 3496.6 | 0.0 |
| OP1 | hnc | prod_5ax_hnc8 | 183 | 05f4f5b2911f | PASS | 7336.5 | 0.0 |
| OP2 | hnc | prod_5ax_hnc8 | 1199 | 8767b09e5ab0 | PASS | 3251.2 | 0.000494 |
| OP3 | hnc | prod_5ax_hnc8 | 86 | b584fa3e818c | PASS | 3496.6 | 0.0 |

## 4. 扫掠碰撞 / 过切 / 超程（实测）

| 工序 | 采样点 | 最小夹具间隙 | 刀尖过切 | 刀具表面过切 | 刀柄-毛坯 | 行程 |
|---|---|---|---|---|---|---|
| OP1 | 18917 | 1.85 | 9.5 | 1.5 | 18.0 | PASS |
| OP2 | 7782 | 1.45 | -22.626 | -23.514 | 27.032 | PASS |
| OP3 | 7111 | 27.85 | -0.0 | -0.003 | 64.5 | PASS |

### 违规明细

- `{'type': 'DESIGN_GOUGE', 'line': 23, 'penetration_mm': -0.325, 'world': [132.32, -0.75, 96.92], 'op': 'OP2'}`
- `{'type': 'DESIGN_GOUGE', 'line': 23, 'penetration_mm': -0.95, 'world': [122.72, -0.7, 97.64], 'op': 'OP2'}`
- `{'type': 'DESIGN_GOUGE', 'line': 92, 'penetration_mm': -0.597, 'world': [124.64, -0.71, 97.5], 'op': 'OP2'}`
- `{'type': 'DESIGN_GOUGE', 'line': 96, 'penetration_mm': -0.332, 'world': [126.95, 39.46, 96.74], 'op': 'OP2'}`
- `{'type': 'DESIGN_GOUGE', 'line': 96, 'penetration_mm': -0.082, 'world': [125.03, 29.91, 97.03], 'op': 'OP2'}`
- `{'type': 'DESIGN_GOUGE', 'line': 96, 'penetration_mm': -1.084, 'world': [123.11, 20.35, 97.31], 'op': 'OP2'}`
- `{'type': 'DESIGN_GOUGE', 'line': 96, 'penetration_mm': -0.843, 'world': [121.18, 10.79, 97.59], 'op': 'OP2'}`
- `{'type': 'DESIGN_GOUGE', 'line': 165, 'penetration_mm': -0.065, 'world': [122.34, 16.53, 97.42], 'op': 'OP2'}`
- `{'type': 'DESIGN_GOUGE', 'line': 165, 'penetration_mm': -0.652, 'world': [124.26, 26.08, 97.14], 'op': 'OP2'}`
- `{'type': 'DESIGN_GOUGE', 'line': 165, 'penetration_mm': -0.549, 'world': [126.18, 35.64, 96.86], 'op': 'OP2'}`
- `{'type': 'DESIGN_GOUGE', 'line': 169, 'penetration_mm': -0.651, 'world': [103.72, 77.06, 96.69], 'op': 'OP2'}`
- `{'type': 'DESIGN_GOUGE', 'line': 169, 'penetration_mm': -0.148, 'world': [105.62, 67.34, 96.85], 'op': 'OP2'}`
- `{'type': 'DESIGN_GOUGE', 'line': 169, 'penetration_mm': -0.087, 'world': [107.51, 57.62, 97.0], 'op': 'OP2'}`
- `{'type': 'DESIGN_GOUGE', 'line': 169, 'penetration_mm': -1.029, 'world': [115.09, 18.76, 97.62], 'op': 'OP2'}`
- `{'type': 'DESIGN_GOUGE', 'line': 238, 'penetration_mm': -0.73, 'world': [115.09, 18.76, 97.62], 'op': 'OP2'}`
- `{'type': 'DESIGN_GOUGE', 'line': 238, 'penetration_mm': -0.148, 'world': [105.62, 67.34, 96.85], 'op': 'OP2'}`
- `{'type': 'DESIGN_GOUGE', 'line': 238, 'penetration_mm': -0.161, 'world': [103.72, 77.06, 96.69], 'op': 'OP2'}`
- `{'type': 'DESIGN_GOUGE', 'line': 242, 'penetration_mm': -0.085, 'world': [62.27, 113.05, 96.54], 'op': 'OP2'}`
- `{'type': 'DESIGN_GOUGE', 'line': 242, 'penetration_mm': -0.452, 'world': [66.69, 104.16, 96.65], 'op': 'OP2'}`
- `{'type': 'DESIGN_GOUGE', 'line': 242, 'penetration_mm': -0.943, 'world': [71.11, 95.28, 96.76], 'op': 'OP2'}`

## 5. 量产一致性与预警

| 刀具 | Vc | 预计寿命(min) | 已用(min) | 磨损 | 等级 | 每刀件数 |
|---|---|---|---|---|---|---|
| T1 | 35.2 | 37.0 | 180.6 | 488.6% | ALARM | 1 |
| T2 | 29.8 | 35.1 | 112.5 | 320.6% | ALARM | 1 |

- 撞机风险：**MEDIUM**（最小间隙 1.45 mm）
- SPC：PASS，Cpk=1.8，超差 0 件（basis=simulated）
- 批量：50 件，单件 234.7 min，预计 203.12 h，每刀 1 件
- 换产：14.5 min（目标 ≤15.0 min）→ PASS
- 预警：4 条

| 类型 | 等级 | 工序 | 数值 |
|---|---|---|---|
| TOOL_WEAR | ALARM |  | 488.6 |
| TOOL_WEAR | ALARM |  | 320.6 |
| CYCLE_TARGET |  | OP1 |  |
| CYCLE_TARGET |  | OP3 |  |

## 6. OPC UA

- 协议栈：asyncua 可用
- 端点：opc.tcp://127.0.0.1:4840/virtu/
- 节点：State, Part, ProgramHash, BatchCount, CycleTime_s, MinClearance_mm, Cpk, ToolWear_pct, AlarmCode, AlarmText
- 读写自检：PASS（basis=measured）

## 7. 诚实边界（必须随报告一起交付）

- 未执行 VERICUT 运行级仿真（batch 介质不执行仿真），碰撞/过切为自研扫掠几何实测（采样步长 2 mm），不是 VERICUT 逐帧布尔材料去除。
- 未做实机首件：三坐标叶型、超声壁厚、动平衡、表面粗糙度均未测。
- 刀具寿命为 Taylor 模型推导，非刀具寿命试验；每刀件数为推导值。
- SPC 为模拟样本演示（basis=simulated），Cpk 不代表真实批次；量产须用首件与抽检实测替换。
- 五轴 RTCP 的机床摆长/枢轴标定未纳入；Siemens 方向按 A3/B3/C3 向量发射，未在 840D sl 实机验证。
- 换产的现场步骤时间为计划值，软件侧重构时间为实测。
- VERICUT 培训模型 NMV1500 的 Y 行程仅 210 mm，无法覆盖本零件；见机床能力表。

## 8. 结论

- 配置门：PASS
- NC 审查：PASS
- 扫掠碰撞：FAIL
- 机床行程：PASS
- 综合：**FAIL**
