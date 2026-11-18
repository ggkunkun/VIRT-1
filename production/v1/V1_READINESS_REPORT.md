# V1 五轴标定阶段执行记录 — AE-CI-258

- 执行时间：2026-11-18 23:14:52
- 依据：`production/reports/UNMEASURED_VERIFICATION_PLAN.md` §U-06/U-07/U-08
- 结论：**OPEN（软件侧就绪，待现场标定）**
- 统计：PASS 5 / PENDING 5 / FAIL 0

> 物理标定必须由持证人员在机床上执行；本执行器只负责程序、判据、记录与反算。

## 1. 执行明细

| ID | 项 | 状态 | 证据 |
|---|---|---|---|
| V1-NC-fanuc | fanuc 标定程序审查 | PASS | `{"file": "D:\\Virtu模型\\production\\v1\\nc\\RTCP_BALL_TEST_FANUC.nc", "failed": []}` |
| V1-NC-hnc | hnc 标定程序审查 | PASS | `{"file": "D:\\Virtu模型\\production\\v1\\nc\\RTCP_BALL_TEST_HNC.nc", "failed": []}` |
| V1-NC-siemens | siemens 标定程序审查 | PASS | `{"file": "D:\\Virtu模型\\production\\v1\\nc\\RTCP_BALL_TEST_SIEMENS.nc", "failed": []}` |
| V1-ENVELOPE | 20 姿态球心在机床行程内 | PASS | `{"x": [-111.6, 111.6], "y": [-100.0, 100.0], "z": [-6.7, 93.3], "travel": {"x": [-365.0, 365.0], "y": [-255.0, 255.0], "z": [-300.0, 450.0]}}` |
| V1-ORIENTATION | Siemens A3/B3/C3 与 B/C 映射一致 | PASS | `{"mismatch": [], "count": 0, "orientations": 20}` |
| V1-U-06 | 证据 U-06 | PENDING | `{"status": "PENDING", "reason": "complete_rows=0/20", "n": 0}` |
| V1-U-07 | 证据 U-07 | PENDING | `{"status": "PENDING", "reason": "orientation rows=0/20"}` |
| V1-U-08-repeat | 证据 U-08-repeat | PENDING | `{"status": "PENDING", "reason": "repeatability: insufficient values"}` |
| V1-U-08-thermal | 证据 U-08-thermal | PENDING | `{"status": "PENDING", "reason": "thermal: insufficient values"}` |
| V1-U-08-backlash | 证据 U-08-backlash | PENDING | `{"status": "PENDING", "reason": "insufficient forward/reverse pairs"}` |

## 2. 标定程序

| 控制器 | 文件 | 说明 |
|---|---|---|
| FANUC 0i-MF | `D:\Virtu模型\production\v1\nc\RTCP_BALL_TEST_FANUC.nc` | G43.4 H1，20 姿态 |
| HNC-8 | `D:\Virtu模型\production\v1\nc\RTCP_BALL_TEST_HNC.nc` | G43.4 H1，20 姿态 |
| SINUMERIK 840D sl | `D:\Virtu模型\production\v1\nc\RTCP_BALL_TEST_SIEMENS.nc` | TRAORI + A3/B3/C3 |

> 球心装在机床坐标 (100, 0, 50)：台面上方 150 mm，偏离 B 轴枢轴，旋转时才会暴露标定误差。
> 程序只把 TCP 定位到球心并旋转 B/C；偏差由千分表/测头读取，填入证据表。

## 3. 证据表（现场填写，不覆盖已填）

空白模板：`production\v1\templates`（每次运行重建）；填写副本：`production\v1\evidence`（已存在则保留）

- `production\v1\evidence\U-06_rtcp_record.csv`
- `production\v1\evidence\U-07_siemens_orientation.csv`
- `production\v1\evidence\U-08_repeatability.csv`
- `production\v1\evidence\U-08_thermal.csv`
- `production\v1\evidence\U-08_backlash.csv`
- `production\v1\evidence\SESSION_META.csv`
- `production\v1\evidence\U-06_U-08_RECORD_GUIDE.md`

## 4. G1 判定逻辑

- U-06：Δ_i = (R_B(B_i)R_C(C_i) − I)·e 最小二乘反算枢轴偏置 e；残差最大值 ≤0.050 mm 判 PASS
- U-07：Ø50 端面打表极差 δ → 刀轴角偏差 atan(δ/50) ≤0.050° 判 PASS（矢量映射已由软件校核）
- U-08：刀长重复性 ≤0.005 mm；60 min 热漂移 ≤0.020 mm；B/C 反向间隙 ≤0.010°
- 现场证据门（U-06/U-07/U-08）：**PENDING**

## 5. 现场步骤（摘要）

1. 机床预热 ≥30 min；工作台清理，拆下虎钳/工件，只保留球座。
2. 标准球装在工作台中心偏置位置（机床 X100/Y0/Z50），千分表找正球座。
3. 设置 G54 = 球心；T1 装千分表/测头并按球心对刀（H1）。
4. 单段运行标定程序，逐姿态记录球心偏差（U-06）或指示表偏差（U-07）。
5. 执行 U-08：5 次换刀测刀长；主轴 60 min 热漂移；B/C 往返 10 次测反向间隙。
6. 填表 → 重跑本脚本 → G1 自动判定。任何 FAIL 禁止进入 V2/切削。
