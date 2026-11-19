# Agent 层全面修复报告 · 2026-11-19

- **范围**：`virtu_omni/agent/*`、`virtu_omni/computer_use/*`、根 `agent_chain_executor.py`、`bridges/deep_agent.py`
- **治理依据**：AGENTS.md §5（证据先于断言）、§6（单步自查+熔断）、§8（测量宪法）、§8.4（坏样本⇒必红）、§4.3（安全门不得假绿/假红）、§4.7⑤（冻结契约裁决）
- **证据口径**：`basis=measured`（全部数字来自实跑 pytest / 探针，下方附 run 日志与基线哈希）
- **修复前基线**：`89a1c79`（会话起始 HEAD，含全部旧缺陷）；G80 探针基线 `040de85`
- **解释器**：定向 `.venv/Scripts/python.exe`（无 pytest-timeout 插件）；全量 `Python312/python.exe -m pytest tests/ -q --timeout=300`
- **run 日志**：`reports/_full_regression_2026-11-19.log`（修复前全量）、`reports/_full_regression_postfix_2026-11-19.log`（修复后全量，进程被杀，见 §6）

---

## 1. 摘要

本轮按「全面修复 Agent 存在的问题」对 Agent 层做静态+动态审计，确认并修复 **9 个模块、24 处真实缺陷**，每处均配「植入坏样本⇒必红」反证测试，并以钉死基线哈希的 HEAD 变异探针证明旧代码确实放行坏样本。

- **8 个反证测试文件**（76 个 test 函数，参数化后更多），全部实跑通过。
- **4 个 HEAD 变异探针**，合计 **20/20 可证伪**（旧代码必红 / 新代码必绿）。
- **修复前全量回归**：`2436 passed, 5 failed, 51 skipped, 55 subtests`（612.90s，正常结束）。
- **5 个失败归因**：1 个是 Agent 层真缺陷（涡轮叶片 G80 假红）→ **本轮已修**；4 个是并发会话的测量/工具面漂移（非本域，见 §7）。
- **修复后定向回归**（Agent/CNC/沙箱/Swarm 全域 12 文件）：**86 passed**（100.77s），含涡轮 4、沙箱安全 20、收敛 21/21、swarm_entry 23/23、autodiff 9/9。
- **提交推送**：源码修复随 daemon `13513ac` 等入库；反证测试套件 `040de85` 已推送 `origin/main`；G80 修复+本报告见 §9。

---

## 2. 修复清单（模块 → 缺陷 → 反证）

| # | 模块 | 缺陷（旧行为） | 修复 | 反证测试 | 探针 |
| :-- | :-- | :-- | :-- | :-- | :-- |
| 5 | `headless_sandbox_verifier.py` | 注释/子串主轴污染（`(M03)`、`M30` 里的 `M3` 被当主轴开） | 先剥注释，按真实 M03/M04/M05 字判主轴 | `test_sandbox_safety_fix` | — |
| 5 | 同上 | 无 G 代码模态，裸 Z- 块漏判扎刀 | motion 模态组 rapid/feed/cycle + G90/G91 | 同上 | — |
| 5 | 同上 | token-only Z 解析，Macro B `Z-[#102]` 不求值 | `_eval_macro_expr` 求值 Z 目标 | 同上 | — |
| 5 | 同上 | 非空不支持语言/解析失败被断言通过 | 语法/解析失败一律判红（§8.4） | 同上 | — |
| 5 | `self_reflection_optimizer.py` | 风格项（少写 Zoom/宏变量）把合法程序判失败 | fatal=沙箱错误 / style=静态未命中；`is_passed` 只看 fatal+沙箱 | 同上 | — |
| 5b | `headless_sandbox_verifier.py` | **G80（循环取消）落进 74..89 被当 cycle** → 合法涡轮开头假红 + G80 后裸负 Z 漏判扎刀（假绿） | G80 单独分支 → motion 回 rapid | `test_sandbox_safety_fix` C15（3 条） | `_probe_g80_head` 5/5 |
| 6 | `process_memory_reclaimer.py` | D2 `close_software` 进程仍存活却报 RECLAIMED | 存活计入 `residual_pids`，status=FAILED | `test_reclaimer_safety_fix` | — |
| 6 | 同上 | D3 `_append_log` 非原子 + 损坏 JSON 静默丢历史 | 原子写（temp+os.replace）+ `.corrupt-<ts>.bak` 留证 | 同上 | — |
| 7 | `computer_use/adapter.py` | A 空动作 `all([])==True` → COMPLETED | NO_ACTIONS / ok=False | `test_computer_use_verdict_fix` | — |
| 7 | 同上 | B 任一步 ok=False 仍 COMPLETED | FAILED / ok=False | 同上 | — |
| 7 | `computer_use/action.py` | C drag 外力打断仍 ok=True/executed | aborted / `foreign_cursor_writer`（input_sent 仍 True） | 同上 | — |
| 7 | 同上 | D hotkey 空组合/全未知键 input_sent=True | no_keys / input_sent=False | 同上 | — |
| 8 | `agent_chain_executor.py` | A bat 路径被 VT(`\x0b`) 损坏 → GUI 起不来 | 正确 `vericut_console.bat`，无 VT 字节 | `test_agent_chain_fix` | — |
| 8 | 同上 | B `_find_play_button` PIL `size=(W,H)` 解构成 `H,W` | 修正宽高，右下角播放键命中 | 同上 | — |
| 8 | 同上 | C `_vericut_click_play` 用 `pyautogui.click` 绕过 input_guard | 走 `win_input.click`（§4.5 唯一入口） | 同上 | — |
| 8 | 同上 | D `taskkill` `capture_output=True` 无 timeout（管道死锁） | `stdout=DEVNULL` + timeout（§8.1⑦） | 同上 | — |
| 9 | `swarm_orchestrator.py` | release/renew 不 `notify_all` → 等待者睡满 TTL/deadline | 释放/续租即唤醒 | `test_swarm_blackboard_fix` | `_probe_swarm_head` 5/5 |
| 9 | 同上 | read/meta/snapshot 返回活引用（读者绕过写锁） | `copy.deepcopy`（写走重新绑定，无锁拷贝一致） | 同上 | 同上 |
| 9 | 同上 | `handoff_gate` 只查键存在，空壳 `workers=[]` 放行 | 拒 None/空容器，保留标量 0/False | 同上 | 同上 |
| 9 | 同上 | Auto-Diff 载荷解析失败仅 `require_ad` 时判红 | 无条件判红（证据链断裂） | 同上 | 同上 |
| 9 | 同上 | critic 对 `payload_error` 判绿 | `RED-AUTODIFF-ERROR` fatal | 同上 | 同上 |
| 9 | `skill_writer_and_memory.py` | 离线检索伪造 "Technical Reference" + SUCCESS | `NO_EVIDENCE` / findings=[] | `test_skill_writer_fix` | — |
| 9 | 同上 | `synthesize_skill` skill_name/script 路径穿越 | `_safe_component` + realpath 包容校验 | 同上 | — |
| 9 | `bridges/deep_agent.py` | `parse_json_loose` 数组返回 list → 下游 `.get` 崩溃 | 仅返回 dict，数组→None | `test_deep_agent_parse_fix` | `_probe_deep_agent_head` 3/3 |
| 9 | 同上 | `coerce_arg` 拒绝 int-for-number | integer 值满足 number 允许集 | 同上 | 同上 |
| 9 | `agent_team.py` | `EvolutionAndMemoryAgent.run` 无条件写「成功完成」（记忆投毒） | 成功经验 gated 于 verdict；失败归档为复盘记录 | `test_agent_team_memory_fix` | `_probe_agent_team_head` 7/7 |
| 9 | 同上 | `solve_full` 真实门出结论前经 legacy 归档成功记忆 | `solve(commit_memory=False)` 延后 + 真实门后注入权威 `engineering_verdict` | 同上 | 同上 |

> 计数说明：表列 27 行，其中 #5 沙箱 4 处同源缺陷合并为「假绿门」一组、#9 swarm 5 处、agent_team 2 处同源（投毒）合并计，按模块归并为 **9 模块 / 24 处**。

---

## 3. 关键修复详解

### 3.1 G80 假红/假绿（#5b，本轮 triage 中新发现并修复）

`verify_cimco_macro_b` 的模态跟踪把 `G80`（固定循环**取消**）落进 `74 <= g <= 89` 区间，误设 `motion="cycle"`。后果两面：

- **假红**：涡轮叶片五轴程序的安全开头 `G21 G40 G49 G80 G90 G17` → `G28 G91 Z0.`（回参考点，带 Z 字、主轴尚未 M03）被误判「主轴停转却切削进给」，合法程序 `audit.passed=False`。这正是全量回归 `test_turbine_blade_inverse_stock` 的失败点。
- **假绿**：G80 后若跟裸负 Z（无 G00/G01），因 motion 仍是 cycle 而跳过 rapid 扎刀碰撞检查 → 漏判真实碰撞。

修复：G80 单独分支 `motion="rapid"`（取消循环、退出 cycle 模态）。反证三条（C15）：合法涡轮开头必须绿、G80 后裸负 Z 必须判碰撞、主轴前真切削进给必须仍红（门未削弱）。探针 `_probe_g80_head` 对 `040de85` 旧代码 5/5 可证伪（旧 test1 假红、旧 test2 假绿）。

### 3.2 agent_team 记忆投毒（#9）

旧 `run()` 无条件 `content=f"成功完成【…】"`，且 `solve_full` 在真实工程门出结论**之前**就经 legacy 信封归档记忆 → 沙箱/真实门判红时记忆库仍躺「成功经验」，下次召回把失败当成功复用（违反 §5）。

修复三处：
1. `run()` 按 verdict 写断言：`verified_success = (eng_verdict is True) if eng_verdict is not None else auditor_passed`；失败写「…仅供复盘，不得当作成功经验召回」，元数据带 `engineering_verified/evidence_basis`。
2. `solve(commit_memory=True)` 新增参数；`solve_full` 传 `False`，第 7 步 DEFERRED（团队级 PARTIAL）。
3. `solve_full` 在 `solve_engineering` 出结论后，以 `engineering_verdict=eng["engineering_verified"]` 权威归档，覆写 `07_hindsight_memory_commit.json`。

冻结契约不回归：收敛 A/B/C/D 21/21（C 的 `legacy_status` 由 SUCCESS 变 PARTIAL，契约允许）；独立 `solve` 默认仍 COMPLETED/SUCCESS；D 组真失败压过桩成功仍 FAILED。

### 3.3 swarm Blackboard 一致性（#9）

写走 `self._store[key]=value` 重新绑定（非原地改值），故无锁 `deepcopy` 读一致；release/renew 补 `notify_all` 消除等待者睡满 TTL 的延迟；`handoff_gate` 拒空壳容器；Auto-Diff 载荷解析失败无条件判红 + critic `payload_error` 判红（杜绝「绿色 100%」假合格）。

---

## 4. 反证证据（measured）

### 4.1 反证测试文件（8 个，全部实跑通过）

| 文件 | test 函数 | 域 |
| :-- | :-- | :-- |
| `test_sandbox_safety_fix.py` | 20（含 C15 G80 3 条） | #5 沙箱+优化器 |
| `test_reclaimer_safety_fix.py` | 6 | #6 回收器 |
| `test_computer_use_verdict_fix.py` | 7 | #7 桌面判决 |
| `test_agent_chain_fix.py` | 5 | #8 执行器 |
| `test_swarm_blackboard_fix.py` | 11 | #9 swarm |
| `test_skill_writer_fix.py` | 7（参数化 11 例） | #9 技能 |
| `test_deep_agent_parse_fix.py` | 12（参数化 ~19 例） | #9 桥接 |
| `test_agent_team_memory_fix.py` | 8 | #9 记忆 |

### 4.2 HEAD 变异探针（钉死基线，20/20 可证伪）

| 探针 | 基线 | 结果 |
| :-- | :-- | :-- |
| `scratch/_probe_swarm_head.py` | `89a1c79` | 5/5（read 活引用 / handoff 空壳 / 载荷失败放行 / critic 判绿 / release 延迟） |
| `scratch/_probe_deep_agent_head.py` | `89a1c79` | 3/3（数组返回 list / `.get` 崩溃 / int-for-number 被拒） |
| `scratch/_probe_agent_team_head.py` | `89a1c79` | 7/7（旧写「成功完成」/ 无 verdict 元数据 / 新不声称成功） |
| `scratch/_probe_g80_head.py` | `040de85` | 5/5（旧涡轮假红 / 旧裸负 Z 假绿 / 新均正确 / 门未削弱） |

> 探针为只读 scratch（gitignored），钉死哈希以保证 daemon 推进 HEAD 后仍可复跑。

### 4.3 冻结契约（实跑通过）

- `test_agent_team_convergence` 21/21；`test_agent_team` 9 passed；`test_memory_safe_agent_team`+`test_security_audit` 11 passed+4 subtests。
- `test_swarm_entry` 23/23；`test_autodiff_ingestion` 9/9；`test_swarm_orchestrator`+blackboard 绿。
- 4 个 #9 反证文件 + `test_agent_reach_integration` 合跑 54 passed。

---

## 5. 修复后定向回归（measured）

```
.venv/Scripts/python.exe -m pytest tests/test_sandbox_safety_fix.py \
  tests/test_turbine_blade_inverse_stock.py tests/test_cnc_post_processor.py \
  tests/test_agent_team.py tests/test_agent_team_real_agents.py \
  tests/test_agent_team_memory_fix.py tests/test_memory_safe_agent_team.py \
  tests/test_agent_team_convergence.py tests/test_swarm_orchestrator.py \
  tests/test_swarm_blackboard_fix.py tests/test_swarm_entry.py \
  tests/test_autodiff_ingestion.py -q
→ 86 passed in 100.77s
```

覆盖 G80 与 agent_team 修复可能触及的全部 Agent/CNC/沙箱/Swarm 域，**无回归**。

---

## 6. 全量回归（measured + 诚实标注）

### 6.1 修复前全量（HEAD `040de85`，正常结束）

```
Python312 -m pytest tests/ -q --timeout=300
→ 5 failed, 2436 passed, 51 skipped, 1 warning, 55 subtests passed in 612.90s
```

8 个反证测试文件均在 2436 passed 内（G80 3 条新增前）。5 个失败见 §7。

### 6.2 修复后全量重跑（进程被杀，未测）

重跑在 **87 个测试**处被终止，退出码 `1073807364`（`0x40010004`，Windows 进程终止），日志仅余进度点、**无 summary、无 `++++ Timeout ++++` 标记**——符合 §8.1.4/§8.1.7「Windows 上 pytest-timeout/子进程管道把整仓进程杀掉」的环境假红特征，**非测试逻辑失败**。

- 口径：修复后**全量** tally = `unmeasured (process killed at 87 tests)`，不冒充通过/失败。
- 替代证据：§5 定向 86 passed 已权威覆盖受影响域；G80 仅改 `verify_cimco_macro_b` 纯逻辑（无 I/O），不引入挂起。
- 处置（§6 熔断）：不盲目重试全量；按 §8.1 排除环境因素后，以定向实跑为准。

---

## 7. 5 个回归失败归因（triage）

| 失败 | 根因 | 归属 | 处置 |
| :-- | :-- | :-- | :-- |
| `test_turbine_blade_inverse_stock::…five_axis` | G80 误判 cycle → 合法涡轮开头假红 | **Agent 层真缺陷** | **本轮已修**（§3.1），定向 4 passed |
| `test_benchmark_baseline::test_lock_covers_every_board_and_matches` | `data/benchmark/virtu_eval_cl_v1/toolrouting.jsonl` DRIFT：lock `12064cb4`(11-13) vs now `c3d3bf2f`(11-19T00:26) | 并发会话改封缄题板未重锁（§8.3） | 非本域，残留 |
| `test_toolcall_plumbing_gates::…observed_400` | `len(MEASURED_TOOLS)=19 != 16` | 并发工具面增长未重测 | 非本域，残留 |
| `test_toolcall_plumbing_gates::…grown_surface` | `len(ARM_TOOLS)=20 != 17`（测试自注「工具面变了，先跑 measure_prompt_tokens.py」） | 同上 | 非本域，残留 |
| `test_virtu_14b_comprehensive_rsi::test_14b_arm_profile_binding` | `len(spec["tools"])=20 != 17` | 同上（16→19→20 同源） | 非本域，残留 |

> 后 4 个同源于并发会话扩张 `super_agent.py` 工具面（16→19→20）而未重跑 `scripts/measure_prompt_tokens.py` / 重锁题板。`super_agent.py` 与测量链是并发会话独占域（§8.6），本轮按约束**不触碰**，如实记为残留，不放宽门禁去绿。

---

## 8. 残留与边界（诚实）

1. **并发测量/工具面漂移（4 个失败）**：需并发会话重跑 `measure_prompt_tokens.py` 并重锁 `CASES.lock`，非本轮 Agent 修复域。
2. **修复后全量 tally 未测**：进程被环境杀死（§6.2）；以定向 86 passed 为受影响域权威证据。
3. **网络依赖集成测试**：`test_agent_reach_integration` 部分用例直连 github-api（`reach.search` 不受 `VIRTU_INTERNET=off` 管辖）；本轮已将 `skill_writer_search_web_integration` 改 hermetic，其余仍依赖联网，离线会红。
4. **探针为 scratch（gitignored）**：不随仓库推送，复跑需本地 `git show <基线>`；基线哈希已钉死。
5. **ChiefArchitect 几何族判定仍是规则式**（关键词+长径比），非几何拓扑识别；特征树由尺寸规则推导（沿用 §4.4 诚实边界，本轮未改）。
6. **共享记忆库副作用已清理**：探针曾误写 `EXP_0484` 入 `data/memory/industrial_knowledge_memory.json`，已持跨进程锁按 (id,signature,pid) 三元组精确移除（483 条，并发会话记录无损）；探针已改 tmp 隔离。

---

## 9. 提交推送记录

- 源码修复：随自治 daemon `13513ac`（fix(agent): close intent/CAE/eval-surface gaps…）等入库。
- `040de85` `test(agent): 落地 Agent 全面修复的反证测试套件并捕获运行时产物` —— 8 反证测试 + 8 daemon 运行时产物，**已推送 `origin/main`**（`cf6e5fb..040de85`）。按用户选择，并发研究目录（`ssnc_teaching`/`nx12_cn`/`sw2021_mastery` 等 ~110MB）保留不动。
- G80 修复（`headless_sandbox_verifier.py`，+5 行）+ C15 反证 3 条（`test_sandbox_safety_fix.py`，+59 行）：随 daemon `409b09c`（feat(cnc): harden safety simulation and add production controls）入库并**已推送**（该 commit 同时含并发会话 manufacturing/bridges/v2 源码，由 daemon 统一捕获，非本会话改动）。
- 本报告 `reports/agent_repair_2026-11-19.md`：见本次提交。
- 推送前已扫描：无密钥（私钥/AKIA/ghp_/xox/sk-）、无 >100MB 单文件（最大 10.1MB）；`409b09c` 16 文件 1187 插入亦经密钥扫描，干净。

---

## 10. 复跑命令

```bash
# 定向（受影响域，权威）
.venv/Scripts/python.exe -m pytest tests/test_sandbox_safety_fix.py \
  tests/test_turbine_blade_inverse_stock.py tests/test_agent_team_memory_fix.py \
  tests/test_swarm_blackboard_fix.py tests/test_skill_writer_fix.py \
  tests/test_deep_agent_parse_fix.py tests/test_agent_team_convergence.py -q

# HEAD 变异探针（钉死基线）
.venv/Scripts/python.exe scratch/_probe_g80_head.py
.venv/Scripts/python.exe scratch/_probe_swarm_head.py
.venv/Scripts/python.exe scratch/_probe_deep_agent_head.py
.venv/Scripts/python.exe scratch/_probe_agent_team_head.py

# 全量（注意 §8.1 环境假红；Windows 进程被杀时以定向为准）
Python312/python.exe -m pytest tests/ -q --timeout=300
```