# VERICUT 9.6 六个错误案例：落地修复 + 重新仿真验证报告

- 日期：2026-11-17（本地时间 20:40 – 23:30）
- 可写副本：`E:\vericut_fix_work`（`robocopy E:\training → 1186/1186 文件`，并清除只读属性）
- 原始文件备份：`E:\vericut_fix_work\_original\`（保持相对路径，7 个文件）
- 只读源未改动：`E:\training`、`knowledge_base\training_case_index.json`、`knowledge_base\error_case_verification.json`
- 结构化结果：`knowledge_base/training_case_repair_results.json`
- 修复后日志目录：`reports/vericut_fix_case_logs/`

## 0. 结论总览

| 案例 | 修复已落地 | 修复后再仿真 | 判定 | 修复后错误数 |
| :--- | :--- | :--- | :--- | :--- |
| `lathe_session_day1` | 是（2 处） | **否**（批处理引擎故障，工程未加载） | **未通过（未验证）** | 无有效日志 |
| `mill_session_day1` | 是（Holder1 缩径） | **否**（同上） | **未通过（未验证）** | 无有效日志 |
| `millturn_session_day1` | 是（第 2 版退刀） | **部分**（第 1 版跑通，暴露新碰撞；第 2 版未跑） | **未通过** | 第1版 14（含 14 条新 Sub_Fixture 碰撞） |
| `lathe_session_103l_add_3d_models_to_the_machine` | 是（Z=32.25") | 是 | **通过** | 0（警告 0） |
| `mill_session_103m_add_3d_models_to_the_machine` | 是（Z=600） | 是 | **通过** | 0（警告 0） |
| `millturn_session_103mt_add_3d_models_to_the_machine` | 是（W=1972） | 是 | **通过** | 0（警告 0） |

**3 通过 / 3 未通过。** 未通过的三个案例不是“修完就宣称通过”，而是修复动作已落地、但**没有拿到可信的修复后仿真证据**：自 21:26 起本机 VERICUT 9.6 批处理引擎不再加载任何工程（详见 §7）。

---

## 1. `lathe_session_day1`（未通过：未验证）

### 原始错误（`reports/vericut_error_case_logs/lathe_session_day1.log`，错误数 3）
```
错误:在 23 行:N1100 Z-1.81 ,刀具 "1" 碰撞 "Jaws"
错误:在 24 行:N1110 X2.32 ,刀具 "1" 碰撞 "Jaws"
错误:在 47 行:N0220 X.04,组件"Tool_1"上的刀具"1"快速进给去除材料,去除体积0.0011
```

### 修复动作
| 文件 | 位置 | before → after |
| :--- | :--- | :--- |
| `lathe_program.mcd` | 第 47 行 | `N0220 X.04` → `N0220 G1 X.04 F10.` |
| `lathe_session_day1.vcproject` | `Component Name="Jaws"` → `Poly lathe_fixture.ply` → `MatrixOrigin` | `Z="4.05"` → `Z="5.05"`（仅动夹具模型矩阵，未动 Stock `Z=4.2` / Design 的矩阵） |

补充实测：`lathe_fixture.ply` 局部包围盒 `Z ∈ [-1.2, 0.3]`，MatrixOrigin 4.05 时夹具落在 Z 2.85–4.35；G54 的 Z 偏置为 6.2，故 23 行工件 Z=-1.81 对应机床 Z≈4.39，正好贴夹具前缘——这解释了为什么一上来就撞 Jaws。

### 修复后日志摘要
无。三次重跑（22:18、22:22、23:03）分别得到：`vericut.log` 只有 `END-OF-FILE`（无 `*** 处理数控程序文件` 行）/ 直接开 GUI 窗口。**没有任何一次真正跑了刀路**，因此既不能判通过，也不伪造错误数。

### 剩余问题
1. Jaws +1.0" 是否足够、是否引入新的 Jaws/Stock 碰撞**未实测**；若需继续迭代，按 +0.5" 递增（5.55 / 6.05 …）。
2. `lathe_program.mcd` 第 45 行原有拼写错误 `N0200 G3 X1.56 Z-..3818 R.23`（双点），不在本次任务范围，未改。

---

## 2. `mill_session_day1`（未通过：未验证）

### 原始错误（错误数 12、警告数 3，摘关键 5 条）
```
错误:在 280 行:N201 X4.125 Y2.00 Z1.07,刀具"9"的刀柄"Holder1"与"Fixture"碰撞
错误:在 281 行:N202 G28 G91 Z0,刀具"9"的刀柄"Holder1"与"Fixture"碰撞
错误:在 363 行:N266 G81 G99 X-2. Y6.5 Z1.433 R3.85 F10.,刀具"7"的Holder1碰撞"Stock",碰撞体积 0.8176/0.8175
（另有 153/173/1473/177 行"刀具 7 旋转方向错误"等）
```

### 修复动作
`mill_tools.tls` → **11 个 `<SOR ID="Holder1">` 块内的全部 162 个 `<X>` 数值 × 0.5**（保持形状、缩小直径）：

| 典型值 before | after |
| :--- | :--- |
| 1.2750 / 1.3750 / 1.9375 / 0.7916630 | 0.6375000 / 0.6875000 / 0.9687500 / 0.3958315 |

未改任何 Cutter SOR 几何；`Holder11` 未动。

### 修复后日志摘要
无。批处理引擎故障期，多次重跑日志 0 字节，工程未加载。

### 剩余问题
- Holder1 缩径后是否仍与 Fixture/Stock 干涉、是否因刀柄细于刀具产生新的过渡问题，**未实测**。
- 备选策略（Holder1 内所有 `<Z>` +0.5 增加让空，或 X 再 ×0.6）尚未执行。

---

## 3. `millturn_session_day1`（未通过：第 1 版实测暴露新碰撞，第 2 版未跑）

### 原始错误（错误数 9、警告数 5）
```
错误:在 66 行:Z.0313,刀具"7901"快速进给去除材料,去除体积0.0112
错误:在 68 行:F..005 → "有进给速度的运动设定为零"（68/69/70/71 共 4 条）
错误:在 165 行:G1 A0. F20.,"Tool CUTTER"/"Tool HOLDER" 和 "Sub_Fixture" 碰撞（2 条）
错误:在 171 行:G0 Y0. Z-1.05,"Tool CUTTER"/"Tool HOLDER" 和 "Sub_Fixture" 碰撞（2 条）
```

### 修复动作（当前文件为第 2 版，**未仿真**）
| 文件 | 位置 | before → after |
| :--- | :--- | :--- |
| `millturn_program.tap` | 第 66 行 | `Z.0313` → `G1 Z.0313 F.005` |
| `millturn_program.tap` | 第 68 行 | `F..005` → `F.005` |
| `millturn_program.tap` | 第 165 行前（原位置） | 插入 `G0 X4.5`（A 轴回转前 X 向内安全退刀） |
| `millturn_program.tap` | 第 165 行后 | 插入 `G0 X8.1`（回转完成后恢复原位置） |
| `millturn_program.tap` | 原第 171 行前 | 插入 `G0 X4.5`，再 `G0 Y0. Z-1.05`（原 171 行保留，改为退刀后再快移） |

第 1 版（已实测）用的是 `G0 Z2.0` + `G0 X4.5` 退刀，**实测反而把刀具送进 Sub_Fixture**，因此第 2 版改为只用 X 向内退刀。

### 修复后日志摘要（第 1 版，2026-11-17 21:24–21:25，`END-OF-FILE`，错误数 14）
- ✅ **66 行扎料、68/69/70/71 行零进给全部消失**（`F..005`、`Z.0313` 两处修复有效，已实测）。
- ❌ 新增 14 条 Sub_Fixture 碰撞（CUTTER / HOLDER 各 1 条）分布于：
  `165 G0 Z2.0`、`166 G0 X4.5`、`167 G1 A0. F20.`、`168 G0 X8.1`、`169 G0 Z.25`、`175 G0 Y0. Z2.0`、`176 G1 Z-1.05 F.005`。
- 结论：**+Z 方向退刀是错的**，Sub_Fixture 恰在 +Z 一侧，`Z2.0` 直接把刀送进夹具。

> 证据状态说明：第 1 版日志文件后被环境故障期的空日志覆盖，`reports/vericut_fix_case_logs/millturn_session_day1.log` 现为 21:46 的一次失败重跑（398 字节，只有 `END-OF-FILE`）。上面的行号/条数为当时控制台输出的原文摘录，未重新生成。

### 剩余问题
- 第 2 版（X 向内退刀）**未跑**，165/171 行 Sub_Fixture 碰撞是否消除未知。
- 若 X4.5 仍干涉，下一步应改 `G0 Y2.0`（Y 正向）或更小的 X（如 X3.6），需实测。

---

## 4. `lathe_session_103l_add_3d_models_to_the_machine`（通过）

| 文件 | 组件 | before → after | 单位 |
| :--- | :--- | :--- | :--- |
| `lathe_session_103l_add_3d_models_to_the_machine.mch` | `Z` | `<Position X="0" Y="0" Z="0"/>` → `Z="32.25"` | inch（`VcMachine Unit="inch"`） |

- 静态复核：`Z` 组件 Position = `Z=32.25`，Rotation 不变。
- 重跑（`mc_lathe_machine_nc_program.eia`，仿真 0:10:51）：
  `错误数: 0 / 警告数: 0`。
  日志：`reports/vericut_fix_case_logs/lathe_session_103l_2043_transcript.txt`
  （20:42 的原始日志文件在 23:12 被一次批处理失败重跑覆盖成 0 字节，已改名
  `lathe_session_103l_rerun_2312_empty.log`；transcript 为当时原文摘录，非重写数值）。

## 5. `mill_session_103m_add_3d_models_to_the_machine`（通过）

| 文件 | 组件 | before → after | 单位 |
| :--- | :--- | :--- | :--- |
| `mill_session_103m_add_3d_models_to_the_machine.mch` | `Z` | `Z="0"` → `Z="600"` | mm |

- 静态复核通过；重跑（`mc_mill_session_nc_program.mcd`）：`错误数: 0 / 警告数: 0`，日志 `mill_session_103m.log`。

## 6. `millturn_session_103mt_add_3d_models_to_the_machine`（通过）

| 文件 | 组件 | before → after | 单位 |
| :--- | :--- | :--- | :--- |
| `millturn_session_103mt_add_3d_models_to_the_machine.mch` | `W`（`Rotation I="180"`） | `Z="0"` → `Z="1972"` | mm |

- 静态复核通过（Rotation 保持 180 未改）；重跑（`mc_millturn_nc_program.eia`）：`错误数: 0 / 警告数: 0`，日志 `millturn_session_103mt.log`。
- 遗留：任务要求的“改完用 MDI 方向确认”未做——批处理模式无法执行 MDI 单段，只做了静态坐标核对 + 批处理重跑。

---

## 7. 环境故障与启动方式（重要，影响可复现性）

### 7.1 `printargs` 在本机 9.6 上是非法参数
`scripts/run_vericut_batch_case.py` 原本调用 `vericut.bat BATCH batchp printargs <project>`。本机实测（console 模式可看到真实报错）：

```
Error! - The following is an invalid command line argument:
（空参数）
Here are some examples of valid command line arguments:
  batch batchp ip=filename usr=filename reset_cutcolor slice record fitall
```

`ip=` 期望的是 `.ip` 状态文件而不是 `.vcproject`（日志会打印
`IP file does not exist, try finding old ip zip file <name>.vcproject`），`vcp=<file>` 只在 GUI 启动时被识别。
因此脚本已改为 `vericut.bat BATCH batchp "vcp=<project>"`（用原始命令行字符串交给 CreateProcess，
因为 cmd.exe 会把未加引号的 `k=v` 参数在 `=` 处切断）。改动已在文件内注明。

### 7.2 21:26 之后批处理引擎不再加载工程（阻塞 3 个案例）
现象（全部实测复现）：
- `vericut.log` 长时间保持 **0 字节**，进程结束后只有 `END-OF-FILE`，没有 `*** 处理数控程序文件` 行；
- 或改为直接打开 GUI 窗口（标题含目标工程），不进入批处理；
- JVM 崩溃转储 `hs_err_pid8160.log` / `hs_err_pid11252.log`：
  `EXCEPTION_ACCESS_VIOLATION` in `com.cgtech.product.CGTechIpcWrapper.askEngine2 ← CGTechIpcWrapper.askEngine ← requestAction ← Vericut.initRadio ← Vericut.<init>`。

排除项（均已实测）：
- 换到未被修改的旧工作副本 `E:\vericut_verify_work\lathe_session_103l...vcproject` → 同样 0 字节；
- 重置/还原用户偏好 `%USERPROFILE%\cgtech_96_user.prefs` → 无改善（备份 `*.bak_20261117`，已还原）；
- 许可证正常：`cloud_license_test.exe` → `Successfully checked out feature: CGTECH_LICENSE v9.3 / SUCCESS!`；
- 先开 GUI 待其完全加载（窗口标题出现工程名）再发批处理命令 → 仍 0 字节。

### 7.3 并发的第二个 VERICUT 驱动会杀掉本进程
本机同时存在另一个会话的自动化脚本 `scripts/vc_full_drive.py`（其注释即写明“kill ALL java/javaw”“defeat … the rival agent”），开头执行
`Get-Process javaw,java | Stop-Process -Force`。实测 22:46:05 我的批处理进程被它在仿真中途杀掉（日志停在 0 字节、无 `END-OF-FILE`），
并反复打开 `initm.vcproject`、`AE_CLOSED_IMPELLER_VERICUT.vcproject` 等与本任务无关的工程窗口。
这解释了 20:57 之后反复出现的“启动即空日志”。

> 结论：3 个 `103*` 案例的修复后日志（20:42 / 20:50 / 20:54）产生于该竞争启动之前，且日志内含真实的
> `*** 处理数控程序文件` + 刀具摘要 + `错误数: 0`，属 `measured`；另外 3 个案例在故障期内无法取得同类证据，
> **按“未重跑通过就写未通过”处理**。

---

## 8. 复现命令

```powershell
# 单案例（脚本已改为 vcp= 形式）
C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe `
  scripts\run_vericut_batch_case.py `
  --project E:\vericut_fix_work\<case>.vcproject `
  --workdir E:\vericut_fix_work `
  --log "d:\Virtu模型\reports\vericut_fix_case_logs\<case>.log" `
  --timeout 900
```

回滚到原始状态：`Copy-Item E:\vericut_fix_work\_original\* E:\vericut_fix_work\ -Force`。
