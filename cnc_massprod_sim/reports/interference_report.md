# 干涉检测报告（逐帧扫掠实测）

生成：2026-11-18 23:39:44
口径：刀尖+刀轴+刀具/刀柄圆柱表面，对工件原型 KeepOut 盒体逐帧求有符号间隙；
basis=measured（确定性几何实测，非 VERICUT 布尔材料去除）。
现场仍需 VERICUT Auto-Diff 与首件试切确认。

| 工件 | 方言 | 判定 | 帧数 | 最小间隙mm | 违规数 | 最危险夹具 |
|---|---|---|---|---|---|---|
| WP-SHAFT-3JAW | fanuc | PASS | 1384 | 5.8 | 0 | three_jaw_chuck_body |
| WP-SHAFT-3JAW | siemens | PASS | 1254 | 5.8 | 0 | three_jaw_chuck_body |
| WP-SHAFT-3JAW | hnc | PASS | 1384 | 5.8 | 0 | three_jaw_chuck_body |
| WP-MANIFOLD-VISE | fanuc | PASS | 6149 | 2.0 | 0 | vise_movable_jaw |
| WP-MANIFOLD-VISE | siemens | PASS | 5653 | 2.0 | 0 | vise_movable_jaw |
| WP-MANIFOLD-VISE | hnc | PASS | 6149 | 2.0 | 0 | vise_movable_jaw |
| WP-HOUSING-FIXTURE | fanuc | PASS | 5050 | 0.0 | 0 | zero_point_subplate |
| WP-HOUSING-FIXTURE | siemens | PASS | 4562 | 11.0 | 0 | fixture_right_clamp |
| WP-HOUSING-FIXTURE | hnc | PASS | 5050 | 0.0 | 0 | zero_point_subplate |

## 逐门结果

| 工件 | 方言 | 判据 | 结果 | 证据 |
|---|---|---|---|---|
| WP-SHAFT-3JAW | fanuc | FRAME-SAMPLES | PASS | 1384 |
| WP-SHAFT-3JAW | fanuc | FIXTURE-COLLISION | PASS | 5.8 |
| WP-SHAFT-3JAW | fanuc | HOLDER-CLEARANCE | PASS | 5.8 |
| WP-SHAFT-3JAW | fanuc | MACHINE-OVERTRAVEL | PASS | {'violations': 0, 'limits': {'X': (-20.0, 220.0), 'Y': (-10.0, 10.0), 'Z': (-240 |
| WP-SHAFT-3JAW | fanuc | RAPID-SAFE-HEIGHT | PASS | none |
| WP-SHAFT-3JAW | fanuc | SPINDLE-ON-IN-CUT | PASS | {'cut_frames_spindle_off': 0} |
| WP-SHAFT-3JAW | siemens | FRAME-SAMPLES | PASS | 1254 |
| WP-SHAFT-3JAW | siemens | FIXTURE-COLLISION | PASS | 5.8 |
| WP-SHAFT-3JAW | siemens | HOLDER-CLEARANCE | PASS | 5.8 |
| WP-SHAFT-3JAW | siemens | MACHINE-OVERTRAVEL | PASS | {'violations': 0, 'limits': {'X': (-20.0, 220.0), 'Y': (-10.0, 10.0), 'Z': (-240 |
| WP-SHAFT-3JAW | siemens | RAPID-SAFE-HEIGHT | PASS | none |
| WP-SHAFT-3JAW | siemens | SPINDLE-ON-IN-CUT | PASS | {'cut_frames_spindle_off': 0} |
| WP-SHAFT-3JAW | hnc | FRAME-SAMPLES | PASS | 1384 |
| WP-SHAFT-3JAW | hnc | FIXTURE-COLLISION | PASS | 5.8 |
| WP-SHAFT-3JAW | hnc | HOLDER-CLEARANCE | PASS | 5.8 |
| WP-SHAFT-3JAW | hnc | MACHINE-OVERTRAVEL | PASS | {'violations': 0, 'limits': {'X': (-20.0, 220.0), 'Y': (-10.0, 10.0), 'Z': (-240 |
| WP-SHAFT-3JAW | hnc | RAPID-SAFE-HEIGHT | PASS | none |
| WP-SHAFT-3JAW | hnc | SPINDLE-ON-IN-CUT | PASS | {'cut_frames_spindle_off': 0} |
| WP-MANIFOLD-VISE | fanuc | FRAME-SAMPLES | PASS | 6149 |
| WP-MANIFOLD-VISE | fanuc | FIXTURE-COLLISION | PASS | 2.0 |
| WP-MANIFOLD-VISE | fanuc | HOLDER-CLEARANCE | PASS | 2.0 |
| WP-MANIFOLD-VISE | fanuc | MACHINE-OVERTRAVEL | PASS | {'violations': 0, 'limits': {'X': (-500.0, 500.0), 'Y': (-500.0, 500.0), 'Z': (- |
| WP-MANIFOLD-VISE | fanuc | RAPID-SAFE-HEIGHT | PASS | none |
| WP-MANIFOLD-VISE | fanuc | SPINDLE-ON-IN-CUT | PASS | {'cut_frames_spindle_off': 0} |
| WP-MANIFOLD-VISE | siemens | FRAME-SAMPLES | PASS | 5653 |
| WP-MANIFOLD-VISE | siemens | FIXTURE-COLLISION | PASS | 2.0 |
| WP-MANIFOLD-VISE | siemens | HOLDER-CLEARANCE | PASS | 2.0 |
| WP-MANIFOLD-VISE | siemens | MACHINE-OVERTRAVEL | PASS | {'violations': 0, 'limits': {'X': (-500.0, 500.0), 'Y': (-500.0, 500.0), 'Z': (- |
| WP-MANIFOLD-VISE | siemens | RAPID-SAFE-HEIGHT | PASS | none |
| WP-MANIFOLD-VISE | siemens | SPINDLE-ON-IN-CUT | PASS | {'cut_frames_spindle_off': 0} |
| WP-MANIFOLD-VISE | hnc | FRAME-SAMPLES | PASS | 6149 |
| WP-MANIFOLD-VISE | hnc | FIXTURE-COLLISION | PASS | 2.0 |
| WP-MANIFOLD-VISE | hnc | HOLDER-CLEARANCE | PASS | 2.0 |
| WP-MANIFOLD-VISE | hnc | MACHINE-OVERTRAVEL | PASS | {'violations': 0, 'limits': {'X': (-500.0, 500.0), 'Y': (-500.0, 500.0), 'Z': (- |
| WP-MANIFOLD-VISE | hnc | RAPID-SAFE-HEIGHT | PASS | none |
| WP-MANIFOLD-VISE | hnc | SPINDLE-ON-IN-CUT | PASS | {'cut_frames_spindle_off': 0} |
| WP-HOUSING-FIXTURE | fanuc | FRAME-SAMPLES | PASS | 5050 |
| WP-HOUSING-FIXTURE | fanuc | FIXTURE-COLLISION | PASS | 0.0 |
| WP-HOUSING-FIXTURE | fanuc | HOLDER-CLEARANCE | PASS | 10.7308 |
| WP-HOUSING-FIXTURE | fanuc | MACHINE-OVERTRAVEL | PASS | {'violations': 0, 'limits': {'X': (-500.0, 500.0), 'Y': (-500.0, 500.0), 'Z': (- |
| WP-HOUSING-FIXTURE | fanuc | RAPID-SAFE-HEIGHT | PASS | none |
| WP-HOUSING-FIXTURE | fanuc | SACRIFICIAL-EXEMPT:zero_point_subplate | PASS | {'keepout': 'zero_point_subplate', 'frames': 112, 'rule': 'drill-only / declared |
| WP-HOUSING-FIXTURE | fanuc | SPINDLE-ON-IN-CUT | PASS | {'cut_frames_spindle_off': 0} |
| WP-HOUSING-FIXTURE | siemens | FRAME-SAMPLES | PASS | 4562 |
| WP-HOUSING-FIXTURE | siemens | FIXTURE-COLLISION | PASS | 11.0 |
| WP-HOUSING-FIXTURE | siemens | HOLDER-CLEARANCE | PASS | 11.0 |
| WP-HOUSING-FIXTURE | siemens | MACHINE-OVERTRAVEL | PASS | {'violations': 0, 'limits': {'X': (-500.0, 500.0), 'Y': (-500.0, 500.0), 'Z': (- |
| WP-HOUSING-FIXTURE | siemens | RAPID-SAFE-HEIGHT | PASS | none |
| WP-HOUSING-FIXTURE | siemens | SPINDLE-ON-IN-CUT | PASS | {'cut_frames_spindle_off': 0} |
| WP-HOUSING-FIXTURE | hnc | FRAME-SAMPLES | PASS | 5050 |
| WP-HOUSING-FIXTURE | hnc | FIXTURE-COLLISION | PASS | 0.0 |
| WP-HOUSING-FIXTURE | hnc | HOLDER-CLEARANCE | PASS | 10.7308 |
| WP-HOUSING-FIXTURE | hnc | MACHINE-OVERTRAVEL | PASS | {'violations': 0, 'limits': {'X': (-500.0, 500.0), 'Y': (-500.0, 500.0), 'Z': (- |
| WP-HOUSING-FIXTURE | hnc | RAPID-SAFE-HEIGHT | PASS | none |
| WP-HOUSING-FIXTURE | hnc | SACRIFICIAL-EXEMPT:zero_point_subplate | PASS | {'keepout': 'zero_point_subplate', 'frames': 112, 'rule': 'drill-only / declared |
| WP-HOUSING-FIXTURE | hnc | SPINDLE-ON-IN-CUT | PASS | {'cut_frames_spindle_off': 0} |

## 有界豁免（牺牲性背板通孔）

| 工件 | 方言 | 豁免 | 规则 |
|---|---|---|---|
| WP-HOUSING-FIXTURE | fanuc | SACRIFICIAL-EXEMPT:zero_point_subplate | {'keepout': 'zero_point_subplate', 'frames': 112, 'rule': 'drill-only / declared-through-hole / depth-capped', 'basis': 'bounded process exception'} |
| WP-HOUSING-FIXTURE | hnc | SACRIFICIAL-EXEMPT:zero_point_subplate | {'keepout': 'zero_point_subplate', 'frames': 112, 'rule': 'drill-only / declared-through-hole / depth-capped', 'basis': 'bounded process exception'} |
