# 13.63B 调用 computer-use skill 操控桌面：实测报告

- 日期：2026-11-07 10:06 — 10:42（GMT+8）
- 被测模型：`virtu-moe-14b:a2103c68`（13.6B，Ollama）
- skill：`magic-hand-windows`（妙控手 / Computer Use，纯 ctypes，无第三方依赖）
- 证据根目录：`runs/skill_agent_20261107/`
- 口径：除标注 `asserted` 的架构描述外，数值与终态均为 **measured**，可回溯到具体 JSON

---

## 1. 结论

**能。** 13.63B 在只暴露 skill 这一个工具源时，现场产出了一份 5 步结构化计划，**5 步全部选中 `MagicHand`、全部通过工具契约闸门、全部真实执行，0 次重复动作**；其中 `probe` 拿到 `READY / WinSta0`、`activate` 真的把记事本窗口（hwnd 460108）激活为前台，并在轮 B 中把指定文本写进了桌面编辑区（HWND 树 RichEditD2DPT 节点 8/9 客观回读到目标文本）。

但必须把两件事分开说：

| 能力 | 结论 | 依据 |
|---|---|---|
| 模型能否**产出合规的 skill 调用** | ✅ 能 | 轮 A 全程现场规划，5 步 tool 均为 MagicHand，参数经真实 inputSchema 校验 |
| 调用能否**真实改变桌面状态** | ✅ 至少一次客观成功（轮 B） | 树里出现目标文本、前台窗口正确、`verified_by_tree=true` |
| 是否**稳定可复现** | ❌ 否 | 轮 C 因第三方程序抢前台焦点而粘贴落空 |
| 链路自评 `success` | ❌ 三轮均 false | 验收证据裁剪 / 焦点竞争，见 §5；终态一律以客观枚举为准 |

---

## 2. 接入方式（怎么让模型"看得见" skill）

skill 的原生接口是 CLI（`cu_ui.py / clip.py / winmove.py`），模型无法直接调用。新增 `bridges/magic_hand_adapter.py` 把它包装成 **MCP 风格的结构化工具**：

```
MagicHand(action, app, idx, text, combo, file, rect, depth, wait)
```

- `action` 是真实枚举（`probe/apps/launch/tree/focus/info/click/set/type/key/shot/activate/clipget/clipset/move`），
  由 `inputSchema` 暴露给规划器；
- 绝大多数 action → `cu_ui.py` 原生子命令；`clipget/clipset` → `clip.py`；`move` → `winmove.py`；
- `launch+file` 由适配器用 `notepad.exe <临时文件>` 打开**我们自己的空白文件**，避免误写用户窗口；
- `tree` 用 `--json` 后格式化成带索引的可读文本，模型与验收都能逐字引用；
- 返回值与 `WindowsMCPClient.call_tool` 同形（`text / is_error / argv / impl`），因此规划器、闸门、验收完全复用。

`bridges/deep_agent.py` 增加 `--skill-only`：工具清单只来自适配器（不启动 windows-mcp），
写操作判定扩展为 `is_write_action()`（MCP 看 mode 含 schema default，skill 看 action），
`finally` 自动恢复剪贴板并落盘 `skill_calls.json`。原 MCP 模式行为不变。

> 规划器用的是 Ollama `format=<JSON Schema>` 语法约束解码，必填 `analysis` 字段承载拆解理由。

---

## 3. 三轮测量（同一任务、同一份模型计划）

任务：「确认桌面会话可用 → 把空白记事本 `blank_probe.txt` 提到前台 → 写入 `Virtu 13.63B 通过 skill 操控桌面` → 回读 HWND 树验证」

| 指标 | 轮 A（现场规划） | 轮 B（同计划重放） | 轮 C（同计划重放） |
|---|---|---|---|
| `run_id` | `33bc4de3ff6fbbe6` | `705824d44be03784` | `f81b5557ada20e90` |
| 规划来源 | `repair`（返修 1 次后合法） | `cache` | `cache` |
| `plan_valid` | True | True | True |
| 计划步 / 实际执行 | 5 / 5 | 5 / 5 | 5 / 5 |
| 唯一动作 / 重复拦截 | 4 / 0 | 4 / 0 | 4 / 0 |
| 幻觉证据 | 1（见 §5） | 0 | 0 |
| 粘贴回退 / 文本客观落地 | 未启用 / 否 | **触发 / 是** | 触发 / 否 |
| `probe` 前台应用 | notepad | notepad | **Marvis（焦点被抢）** |
| 剪贴板自动恢复 | 不适用 | **True** | True |
| `wall_s` | 375.7 | 135.8 | 606.7 |

轮 A 的模型计划（`analysis` 原文摘录）：
> 根据硬规则拆解为最少可验证步骤：1) 观察当前桌面是否有未被占用的活动会话 (probe); 2) 确认目标 notepad 窗口是否已激活; 3) 若未激活则调用 activate; 4) 在编辑区内 set 文本; 5) tree 查看 HWND 树结构以回读验证。

轮 B 客观核验（`desktop_evidence.json` + `skill_run_b/deep_agent_trace.json`）：
- `set` 回退返回 `{"ok": true, "impl": "paste_fallback", "verified_by_tree": true, ...}`；
- 随后的 `tree` 观察里含目标文本；
- 独立 Win32 枚举：`target_text_in_hwnd_tree = True`，落地节点 `[8] / [9] Control sub=RichEditD2DPT`，
  窗口标题 `*blank_probe.txt - Notepad`，前台同为该窗口。

证据：`desktop_evidence.json`、`skill_run{,_b,_c}/deep_agent_trace.json`、`skill_run{,_b,_c}/skill_calls.json`。

---

## 4. 关键失败模式与修复（按熔断规则留痕）

| 现象 | 根因 | 处置 |
|---|---|---|
| 规划器只看到 `action` 前 8 个枚举，`key/clipset` 不可见 | `tool_brief` 里 `enum[:8]` 截断 | 放宽到 `[:24]`，否则模型根本不可能选对动作 |
| 模型选 `set` 且漏 `idx`，适配落到 idx=0 顶层窗口 | 模型没采信 env_facts；adapter 缺参数默认解析 | `set` 缺 idx 时自动从 HWND 树定位第一个可见可编辑控件（实测解析为 7） |
| `set`/`type` 连续 3 次 `ok:true` 但文本不落地 | Windows 11 新版记事本自绘 `RichEditD2DPT` 对 `WM_SETTEXT`/`WM_CHAR` 不响应 | 适配器基于实测加 `paste_fallback`：`clipset → focus → key ctrl+v → tree` 回读，并把 `verified_by_tree` 写进返回值 |
| 验收 JSON 解析失败、4 条全 `unknown` | `num_predict=220`，模型引用长证据被截断；另 `evidence` 复制整段输出 | 提到 500、强制证据 ≤40 字、按 criteria 关键词做确定性"关键命中行"摘要 |
| 轮 B 文本已落地但自评仍 false | 验收只看每条观察前 350 字，目标文本在树输出尾部 | 同上摘要补丁（轮 C 环境失败，该补丁**未获端到端成功复测**，标 asserted） |
| 轮 C 粘贴落空 | `probe` 显示前台是 `Marvis`，第三方自动化抢焦点 | 按熔断规则停手，不再重试；这是本机已知环境限制 |

另修复两个纯代码 bug：`allow_first` 原按 `step.id==1` 判断，模型从 `id=0` 编号导致误报幻觉证据；`key` 的组合键偶尔被模型写进 `text`，适配器做别名归一化。

---

## 5. 安全、副作用与数据边界（重要）

- 探测时发现**用户记事本里开着真实文件 `加工部件_优化程序.nc`（FANUC 数控加工程序）**。全程未对它执行写操作；测试只在我们自建的 `runs/skill_agent_20261107/blank_probe.txt` 窗口进行，且未保存、未删除任何用户文件。
- **剪贴板副作用（需用户知悉）**：最早一次手工探测（在适配器加入保存/恢复之前）覆盖了系统剪贴板，原内容约 17 字符**未保存、无法追回**；当前剪贴板为空。之后适配器已加入 `_save_clipboard() / restore()`，轮 B、轮 C 的 `clipboard_restored` 均为 `True`。
- skill 自身护栏生效：只操作前台可见窗口，未做删除/退出/保存；未向任何外部位置发送截图或桌面内容。
- 测试窗口 `*blank_probe.txt - Notepad` 目前仍开着，内容为空（轮 C 清空后粘贴未落地）。可自行关闭，不需要保存。
- **当前前台是 `Qoder CN`**，与测试无关，说明本机确实存在多程序抢焦点。

---

## 6. 残留风险与未测项

1. **焦点竞争**是最大不稳定源：`type/key/ctrl+v` 依赖前台窗口，第三方程序（Marvis、Qoder 等）会周期性抢焦点。生产使用应先 `focus` 并在动作后**回读验证**，必要时交给用户手动接管。
2. **链路自评 `success` 三轮均 false**，即使轮 B 客观成功。测量宪法要求终态以客观枚举为准，本报告遵循此口径；自动验收的可靠性仍需单独加固。
3. **未测**：坐标流（`xy`/`drag`，用于微信/Qt/Flutter 自绘 UI）、截图判态、`winmove` 窗口移动、多应用串联任务、其它工业软件（NX/SolidWorks/VERICUT）通过 skill 操控。
4. `launch+file` 由适配器本地 `Popen` 实现（不是 `cu_ui.py`），已在 `impl` 字段标注，勿误认为 skill 原生能力。
5. `asserted` 项：架构职责、闸门规则、轮 C 补丁效果的文字描述来自源码；所有数值与终态来自 `runs/skill_agent_20261107/` 下的 JSON。

---

## 7. 复现

```bash
# 只暴露 skill 工具源，让模型现场规划并真实操控
python bridges/deep_agent.py --skill-only \
  --task "用 magic-hand-windows skill 操控这台电脑：..." \
  --env-facts "只操作 blank_probe.txt 窗口；app 参数填 notepad" \
  --out runs/skill_agent_xxx/run

# 复用上一轮模型真实产出的计划（跳过昂贵规划阶段）
python bridges/deep_agent.py --skill-only \
  --plan-cache runs/skill_agent_20261107/plan_cache_roundA.json \
  --task "..." --out runs/skill_agent_xxx/replay

# 客观核验（不采信模型自述）
python -c "import json,subprocess,sys; ...  # 读 tree --json 查目标文本 + GetForegroundWindow"
```

`probe` 必须返回 `READY / WinSta0`；若返回 `NO_GUI_SESSION`，需按 skill 文档在交互式会话启动桥，Bash 内重试无效。
