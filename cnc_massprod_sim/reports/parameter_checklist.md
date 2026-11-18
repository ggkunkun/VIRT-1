# 工艺参数校验清单（全维度）

生成：2026-11-18 23:39:44
所有参数来源：process_standards（工艺标准库）/ controllers.yaml /
工件原型；带 handbook_ref / basis 可追溯。

## WP-SHAFT-3JAW — 40Cr精密阶梯传动轴（三爪卡盘车削）

| 参数 | 取值 | 依据/来源 | 标准出处 |
|---|---|---|---|
| 材质牌号 | 40Cr | GB/T 3077-2015 (40Cr合金结构钢调质态) | MATERIAL_HANDBOOK |
| 密度 g/cm³ | 7.85 | — | 材料手册 |
| 屈服强度 MPa | 785.0 | — | 材料手册 |
| 抗拉强度 MPa | 980.0 | — | 材料手册 |
| 硬度 HB | 245.0 | — | 材料手册 |
| 毛坯形状 | cylinder | — | stock_derivation |
| 毛坯尺寸 mm | {'diameter': 55.0, 'height': 78.0} | 由成品包络+余量派生 | stock_derivation |
| 毛坯包容性 | True | {'ratio': 1.373, 'aspect': 1.418, 'threshold_ratio': 5.0, 'threshold_aspect': 10.0, 'ok': True, 'reason': ''} | stock_derivation |
| rough_single_side_mm | 2.5 | 《金属切削加工工艺手册》第3篇 合金结构钢调质态切削用量 | 《金属切削加工工艺手册》 |
| semi_finish_single_side_mm | 0.4 | 《金属切削加工工艺手册》第3篇 合金结构钢调质态切削用量 | 《金属切削加工工艺手册》 |
| finish_single_side_mm | 0.25 | 《金属切削加工工艺手册》第3篇 合金结构钢调质态切削用量 | 《金属切削加工工艺手册》 |
| corner_rest_allowance_mm | 0.15 | 《金属切削加工工艺手册》第3篇 合金结构钢调质态切削用量 | 《金属切削加工工艺手册》 |
| end_face_allowance_mm | 2.0 | 《金属切削加工工艺手册》第3篇 合金结构钢调质态切削用量 | 《金属切削加工工艺手册》 |
| 装夹方案 | 三爪自定心液压卡盘（配硬爪/软爪轴向定位台） | 短圆柱面定心(4-DOF)+卡盘端面/台阶轴向止动(1-DOF)=5-DOF限制；L/D>3.0须配尾座顶尖(6-DOF) | 《数控加工工艺规范》车削装夹定位与悬伸安全准则 |
| 定位自由度 | 5 | 3-2-1/5-DOF 定位 | 《数控加工工艺规范》 |
| 最小夹持深度 mm | 20.0 | — | 装夹标准 |
| 最大悬伸比 L/D | 3.0 | — | 装夹标准 |
| 重复定位精度 mm | 0.015 | 液压快换软爪(带定位止口键) | 夹具手册 |
| z_safe_global_mm | 60.0 | 运动安全策略 | 《数控加工工艺规范》 |
| z_r_plane_mm | 2.5 | 运动安全策略 | 《数控加工工艺规范》 |
| rapid_decel_zone_mm | 5.0 | 运动安全策略 | 《数控加工工艺规范》 |
| xy_clearance_mm | 13.0 | 运动安全策略 | 《数控加工工艺规范》 |
| rapid_override_first_piece_pct | 25 | 运动安全策略 | 《数控加工工艺规范》 |
| 配置门 | True | [] | handbook_and_kinematic_safety_gate |

## WP-MANIFOLD-VISE — AL7075-T6液压集成阀块（精密虎钳三轴铣削）

| 参数 | 取值 | 依据/来源 | 标准出处 |
|---|---|---|---|
| 材质牌号 | AL7075-T6 | GB/T 3190-2020 (7075-T6超硬铝合金) | MATERIAL_HANDBOOK |
| 密度 g/cm³ | 2.81 | — | 材料手册 |
| 屈服强度 MPa | 503.0 | — | 材料手册 |
| 抗拉强度 MPa | 572.0 | — | 材料手册 |
| 硬度 HB | 150.0 | — | 材料手册 |
| 毛坯形状 | box | — | stock_derivation |
| 毛坯尺寸 mm | {'dx': 124.0, 'dy': 94.0, 'dz': 32.0} | 由成品包络+余量派生 | stock_derivation |
| 毛坯包容性 | True | {'ratio': 1.233, 'threshold': 4.0, 'ok': True, 'reason': ''} | stock_derivation |
| rough_single_side_mm | 2.0 | 《金属切削加工工艺手册》轻合金高速铣削与车削标准参数 | 《金属切削加工工艺手册》 |
| semi_finish_single_side_mm | 0.5 | 《金属切削加工工艺手册》轻合金高速铣削与车削标准参数 | 《金属切削加工工艺手册》 |
| finish_single_side_mm | 0.2 | 《金属切削加工工艺手册》轻合金高速铣削与车削标准参数 | 《金属切削加工工艺手册》 |
| corner_rest_allowance_mm | 0.15 | 《金属切削加工工艺手册》轻合金高速铣削与车削标准参数 | 《金属切削加工工艺手册》 |
| end_face_allowance_mm | 2.0 | 《金属切削加工工艺手册》轻合金高速铣削与车削标准参数 | 《金属切削加工工艺手册》 |
| 装夹方案 | 精密平口虎钳（固定钳口基准+平行垫铁+左侧定位挡块） | 3-2-1六点定位：垫铁底面支承(3点/Z)+固定钳口侧基准(2点/Y)+左侧挡块止动(1点/X) | 《数控加工工艺规范》铣削虎钳基准统一与干涉避让准则 |
| 定位自由度 | 6 | 3-2-1/5-DOF 定位 | 《数控加工工艺规范》 |
| 最小夹持深度 mm | 8.0 | — | 装夹标准 |
| 最大悬伸比 L/D | 2.5 | — | 装夹标准 |
| 重复定位精度 mm | 0.008 | 零点快换底板+卡位平行垫铁组 | 夹具手册 |
| z_safe_global_mm | 57.0 | 运动安全策略 | 《数控加工工艺规范》 |
| z_r_plane_mm | 3.0 | 运动安全策略 | 《数控加工工艺规范》 |
| rapid_decel_zone_mm | 5.0 | 运动安全策略 | 《数控加工工艺规范》 |
| xy_clearance_mm | 30.0 | 运动安全策略 | 《数控加工工艺规范》 |
| rapid_override_first_piece_pct | 25 | 运动安全策略 | 《数控加工工艺规范》 |
| 配置门 | True | [] | handbook_and_kinematic_safety_gate |

## WP-HOUSING-FIXTURE — 45钢法兰轴承座（专用一面两销零点夹具铣削）

| 参数 | 取值 | 依据/来源 | 标准出处 |
|---|---|---|---|
| 材质牌号 | Steel45 | GB/T 699-2015 (45优质碳素结构钢) | MATERIAL_HANDBOOK |
| 密度 g/cm³ | 7.85 | — | 材料手册 |
| 屈服强度 MPa | 355.0 | — | 材料手册 |
| 抗拉强度 MPa | 600.0 | — | 材料手册 |
| 硬度 HB | 215.0 | — | 材料手册 |
| 毛坯形状 | box | — | stock_derivation |
| 毛坯尺寸 mm | {'dx': 146.0, 'dy': 116.0, 'dz': 51.0} | 由成品包络+余量派生 | stock_derivation |
| 毛坯包容性 | True | {'ratio': 1.246, 'threshold': 4.0, 'ok': True, 'reason': ''} | stock_derivation |
| rough_single_side_mm | 3.0 | 《金属切削加工工艺手册》第3篇 第2章 碳素钢车/铣加工参数 | 《金属切削加工工艺手册》 |
| semi_finish_single_side_mm | 0.6 | 《金属切削加工工艺手册》第3篇 第2章 碳素钢车/铣加工参数 | 《金属切削加工工艺手册》 |
| finish_single_side_mm | 0.25 | 《金属切削加工工艺手册》第3篇 第2章 碳素钢车/铣加工参数 | 《金属切削加工工艺手册》 |
| corner_rest_allowance_mm | 0.18 | 《金属切削加工工艺手册》第3篇 第2章 碳素钢车/铣加工参数 | 《金属切削加工工艺手册》 |
| end_face_allowance_mm | 2.5 | 《金属切削加工工艺手册》第3篇 第2章 碳素钢车/铣加工参数 | 《金属切削加工工艺手册》 |
| 装夹方案 | 专用一面两销零点快换夹具（底面基准+圆柱销+削边销+压板） | 一面两销经典6-DOF定位：精密底平面(3点)+圆柱销A(2-DOF)+菱形削边销B(1-DOF角向防转) | 《机床夹具设计手册》一面两销过定位消除与SMED零点接口规范 |
| 定位自由度 | 6 | 3-2-1/5-DOF 定位 | 《数控加工工艺规范》 |
| 最小夹持深度 mm | 10.0 | — | 装夹标准 |
| 最大悬伸比 L/D | 2.5 | — | 装夹标准 |
| 重复定位精度 mm | 0.003 | 气动/液压零点定位基座(4拉钉重复定位<=0.003mm) | 夹具手册 |
| z_safe_global_mm | 65.0 | 运动安全策略 | 《数控加工工艺规范》 |
| z_r_plane_mm | 3.0 | 运动安全策略 | 《数控加工工艺规范》 |
| rapid_decel_zone_mm | 5.0 | 运动安全策略 | 《数控加工工艺规范》 |
| xy_clearance_mm | 36.5 | 运动安全策略 | 《数控加工工艺规范》 |
| rapid_override_first_piece_pct | 25 | 运动安全策略 | 《数控加工工艺规范》 |
| 配置门 | True | [] | handbook_and_kinematic_safety_gate |

