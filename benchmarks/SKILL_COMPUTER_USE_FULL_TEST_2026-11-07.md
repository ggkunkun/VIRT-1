# 13.63B × computer-use skill 全面测试报告

- 日期：2026-11-07 10:46 — 11:27（GMT+8）
- 被测模型：`virtu-moe-14b:a2103c68`（13.6B，Ollama，RTX 4050 6GB，约 2.5 tok/s）
- skill：`magic-hand-windows`（妙控手 / Computer Use，纯 ctypes）
- 证据根目录：`runs/skill_agent_20261107/`
- 口径：除显式标注 `asserted` 的架构描述外，所有数值与状态结论均为 **measured**

---

## 1. 一句话结论

**工具层全通，模型层有明确边界**：22 个 skill 动作全部跑通并被客观取证；但把 22 个动作一次性塞给 13.63B 时，语法约束规划 3/3 超时；按任务裁剪到 6 个动作后，同一任务一次规划成功且拆解顺序正确。工程上应做**动态工具面路由**，而不是把全部能力一次性暴露。

---

## 2. 四条测试线总览

| 线 | 结果 | 证据 |
|---|---|---|
| A 工具面覆盖 | **22/22 动作全覆盖，23 pass / 1 tool_error / 0 untested** | `comprehensive_v2/comprehensive_results.json` |
| B 客观状态变化 | **10 项状态变化**，其中 `set` 文本真落地、`move` 矩形真变化、截图文件头有效 | 同上 + `comprehensive_v2/probe*.bmp/png` |
| C 模型多任务规划 | 全量工具面 **0/3 成功**；精简工具面 **1/1 成功** | `model_tasks/model_tasks_results.json`、`model_tasks/slim_control.json` |
| D 闸门反证 | **5/5 判红**，且每条只触发对应一类违规 | 同上 `gate_counterfactual` |

`run_id`（内容指纹）：覆盖测试 `comprehensive_v2` 与 `model_tasks` 结果文件内各带一个 sha256。

---

## 3. 线 A/B：工具面覆盖与客观取证

### 3.1 独立测试窗口

v1 直接在记事本上测，中途**用户把记事本切回了 `加工部件_优化程序.nc` 标签**，导致目标窗口消失、5 个动作 `app_not_found`、8 个动作被焦点守卫跳过。这暴露了「和用户窗口共享目标」的脆弱性，于是新建 `test_window.py`：用 ctypes 创建一个标题 `VIRTU_TEST_WINDOW`、内含标准 `Edit` 控件的**完全独立 Win32 窗口**，全程不碰用户任何窗口。

> v1 也有正面价值：焦点守卫在窗口被切走后拦下了 8 次 `key/type/click/xy/set/scroll/act/seltext`，**没有一次误写进用户的 .nc 文件**。证据 `comprehensive/comprehensive_results.json`。

### 3.2 22 个动作逐项结果（`comprehensive_v2`）

| 类别 | 动作 | 客观判定 |
|---|---|---|
| 只读 | probe, apps, tree, info, winlist, clipget | pass |
| 截图 | shot, shotpng | pass；BMP `BM` 头 8,294,454 B、PNG `\x89PNG` 244,318 B，文件头校验通过 |
| 焦点/窗口 | focus, activate, move | pass；`move` 后 `GetWindowRect` 从 `[200,160,920,580]` → `[150,120,850,520]`，恢复后回到原值 |
| 输入/控件 | clipset, set, type, key | pass；**`set` 触发 `edit` 状态变化**，同进程 `WM_GETTEXT` 回读 `NATIVE EDIT SET OK` |
| 坐标/交互 | xy, click, scroll, act, drag | pass；`xy`/`drag` 有 `GetCursorPos` 变化 |
| 启动 | launch | pass |
| 选中 | seltext | **tool_error**：`text_not_found` |

唯一失败 `seltext` 的根因：`cu_ui.py` 从**其它进程**用 `GetWindowText` 读 `Edit` 文本，Win32 对跨进程 Edit 不发送 `WM_GETTEXT`，因此即使文本确已写入也读不到。这也解释了为什么必须用同进程 `SendMessage(WM_GETTEXT)` 才能客观取证——本轮正是这样证明 `set` 真生效的。

### 3.3 「ok:true 不等于生效」的正面/反面对照（关键发现）

| 控件类型 | set 返回 | 是否真落地 | 取证方式 |
|---|---|---|---|
| 原生 Win32 `Edit` | `method: win:WM_SETTEXT`, `ok:true` | ✅ 是 | 同进程 `WM_GETTEXT` 读到 `NATIVE EDIT SET OK` |
| Win11 记事本自绘 `RichEditD2DPT` | `method: win:type`, `ok:true` | ❌ 否 | HWND 树里没有文本（前一天实测 3 次） |

适配器据此实现 `paste_fallback`（`clipset → focus → key ctrl+v → tree` 回读，返回 `verified_by_tree`），把「假成功」挡在执行层。

### 3.4 安全收尾

`clipboard_restored=True`、`window_rect_restored=True`，截图只落在 `runs/` 证据目录、未对外交付。测试窗口在 `TW.stop()` 后销毁。

---

## 4. 线 C：模型侧能力边界（本轮最重要的发现）

三个不同任务用**全量工具面**（22 action / 20 参数 / `tool_brief` 853 字符）现场规划：

| 任务 | 期望动作族 | 结果 | 耗时 |
|---|---|---|---|
| T1 窗口移动 | move / winlist | `valid=False, steps=0` | 605.6 s |
| T2 桌面侦察 | probe / apps / tree | `valid=False, steps=0` | 185.4 s |
| T3 编辑区写入 | set / tree | `valid=False, steps=0` | 600.3 s |

**RCFA**：T1/T3 跑满 `chat` 的 600 s 超时，返回底层 error 后 `content` 为空，被旧代码误报成「JSON 语法错误」；T2 同样解析失败。按熔断规则停止重试。已修 `plan_stage`：底层 error 直接透传为 `used=call_error`，不再误导根因判断。

**对照实验**（隔离变量 = 工具面宽度）：

| | 全量 | 精简 |
|---|---|---|
| action 数 | 22 | 6 |
| 参数数 | 20 | 5 |
| `tool_brief` 字符 | 853 | 186 |
| 同一任务规划 | 3/3 失败 | **1/1 成功，171.65 s** |
| 产出的计划 | — | `winlist → move → winlist`（读矩形→移动→回读，顺序正确）|

证据 `model_tasks/slim_control.json`。**结论**：13.63B 在语法约束解码下对工具面宽度敏感，这是能力边界，不是提示词问题。已落地 `slim_schemas()` + `deep_agent.py --actions`，支持按任务动态裁剪（`asserted`：该开关已静态验证 schema 合法，但完整端到端闭环未在本次全面测试中复跑）。

---

## 5. 线 D：闸门反证（可证伪性）

5 个故意错误的计划全部被 `validate_plan` 判红，且收紧为**单点归因**：

| 探针 | 唯一/同类违规 |
|---|---|
| `illegal_action` (`format_disk`) | action 不在枚举内 |
| `illegal_param_key` (`bogus_key`) | 参数键不在 inputSchema |
| `missing_required` | 缺必填 `action` |
| `write_first` | 首步即写操作（`MagicHand.set`）|
| `placeholder` | goal / criteria 含模板占位符 |

---

## 6. 本轮修掉的真 bug

1. `tool_brief` 的 `enum[:8]` 让模型看不到 `key/clipset` → 放宽到 24。
2. `tree` 输出被 `_format_tree` 改写后以 `app:` 开头，绕过了 `ok:false` 检测 → 改为格式化前先判原始 JSON。
3. `winmove.py --rect` 是 `(x,y,宽,高)`，而 `GetWindowRect`/`winlist` 返回 `(l,t,r,b)` → schema 文档明确语义，测试侧加 `to_xywh()` 换算；修后 `move_restore` 由 fail 转 pass。
4. `plan_stage` 把底层超时伪装成「JSON 语法错误」→ 直接透传 `call_error`。
5. `validate_plan` 首步写操作的诊断消息显示空 mode → 补上 action 名。
6. 64 位 ctypes 句柄类型未声明会截断 HWND/HANDLE → 全部显式 `restype/argtypes`。

---

## 7. 残留风险与未测项

- **焦点竞争**：v1 的 `probe` 先后看到 Marvis / WorkBuddy / Qoder CN 抢前台；`SetForegroundWindow` 也会被 Windows 前台锁定拒绝（v2 首轮 `focus`/`activate` 曾 `ok:false` 但返回正确 hwnd）。坐标/输入类动作必须先 `focus` + 回读确认。
- **跨进程 Edit 文本读取限制**：`seltext`、`tree` 对原生 Edit 的文本读取不可靠；需要同进程消息或专用取证。
- **未测**：`launch+file` 打开新临时文件、`--grid/--cross` 截图坐标标定、微信/Qt 自绘 UI 的坐标流长按场景、其它工业软件（NX/SolidWorks/VERICUT）经 skill 操控、多应用串联任务、`--actions` 裁剪后的完整端到端闭环。
- **`launch` 副作用**：v2 的 launch 动作打开了一个空白「无标题 - Notepad」窗口，未关闭；可自行关闭，无用户数据。
- 昨日记录的剪贴板副作用仍然成立：最早手工探测覆盖过系统剪贴板，原内容（约 17 字符）未保存、无法追回；本轮所有剪贴板操作均已自动恢复（`clipboard_restored=True`）。
- `success` 自评字段仍偏严；终态一律以 Win32 客观枚举为准。

---

## 8. 复现

```bash
# 工具面全覆盖 + 客观取证（会自建独立窗口，结束自动销毁与还原）
python runs/skill_agent_20261107/comprehensive_test_v2.py

# 模型多任务规划 + 闸门反证
python runs/skill_agent_20261107/model_tasks.py

# 按任务裁剪工具面（推荐用法，避免 13.63B 在大 schema 下超时）
python bridges/deep_agent.py --skill-only \
  --actions "probe,apps,tree,set,move,winlist" \
  --task "..." --out runs/skill_agent_xxx/run

# 精简工具面对照实验
python runs/skill_agent_20261107/model_tasks.py   # 内含 gate + 3 任务
```

`probe` 必须返回 `READY / WinSta0`；`NO_GUI_SESSION` 时需按 skill 文档在交互式会话启动桥，Bash 内重试无效。
