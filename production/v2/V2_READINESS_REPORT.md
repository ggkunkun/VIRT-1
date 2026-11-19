# V2 空运行与安全链阶段执行记录 — AE-CI-258

- 执行时间：2026-11-18 23:13:30
- 依据：`production/reports/UNMEASURED_VERIFICATION_PLAN.md` §U-10
- 结论：**OPEN（软件侧就绪，待现场空运行）**
- 统计：PASS 9 / PENDING 1 / FAIL 0

## 1. 程序机床坐标包络（实测，含 B/C 转台变换）

| 机床 | 工序 | X | Y | Z | 采样点 | 基础门 |
|---|---|---|---|---|---|---|
| prod_5ax_fanuc_0imf | OP1 | -138.5..138.5 | -138.5..138.5 | 95.8..392.9 | 7727 | PASS |
| prod_5ax_fanuc_0imf | OP2 | 0.0..137.2 | -17.7..12.0 | 68.5..392.9 | 2523 | PASS |
| prod_5ax_fanuc_0imf | OP3 | -134.0..140.0 | -134.0..134.0 | 127.3..392.9 | 2879 | PASS |
| prod_5ax_siemens_840dsl | OP1 | -138.5..138.5 | -138.5..138.5 | 95.8..392.9 | 7727 | PASS |
| prod_5ax_siemens_840dsl | OP2 | 0.0..137.2 | -17.7..12.0 | 68.5..392.9 | 2523 | PASS |
| prod_5ax_siemens_840dsl | OP3 | -134.0..140.0 | -134.0..134.0 | 127.3..392.9 | 2879 | PASS |
| prod_5ax_hnc8 | OP1 | -138.5..138.5 | -138.5..138.5 | 95.8..392.9 | 7727 | PASS |
| prod_5ax_hnc8 | OP2 | 0.0..137.2 | -17.7..12.0 | 68.5..392.9 | 2523 | PASS |
| prod_5ax_hnc8 | OP3 | -134.0..140.0 | -134.0..134.0 | 127.3..392.9 | 2879 | PASS |

## 2. 软限位建议

- `production\v2\SOFT_LIMIT_SHEET.md`
- 写入后必须做超程触发测试（越界 1 mm 报警，不撞硬限位）。

## 3. 空运行记录（现场填写）

- 空白模板：`production\v2\templates\U-10_dryrun_record.csv`
- 填写副本：`production\v2\evidence\U-10_dryrun_record.csv`（已填则保留）

| 程序 | 状态 |
|---|---|
| AE-CI-258_OP1 | PENDING |
| AE-CI-258_OP1 | PENDING |
| AE-CI-258_OP1 | PENDING |
| AE-CI-258_OP2 | PENDING |
| AE-CI-258_OP2 | PENDING |
| AE-CI-258_OP2 | PENDING |
| AE-CI-258_OP3 | PENDING |
| AE-CI-258_OP3 | PENDING |
| AE-CI-258_OP3 | PENDING |

## 4. 现场步骤（摘要）

1. 机床锁住 + 图形模拟跑完 9 个程序，记录报警数。
2. 解除锁住，单段 + 10% 进给跑前 50 段，核对距离剩余与坐标显示。
3. 记录最大主轴负载（应 ≤80% 额定）。
4. 实测急停：各轴停止时间 ≤0.5 s；门开不能启动。
5. 填表 → 重跑本脚本 → U-10 自动判定。任何 FAIL 禁止进入 V3/V4。
