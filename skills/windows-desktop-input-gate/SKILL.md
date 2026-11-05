---
name: windows-desktop-input-gate
description: 鼠标键盘接管与读屏的执行纪律。两条通道：仓内 cadcam_desktop_gui(capture/focus/click/type_text/hotkey/inspect_window/dismiss_dialogs，ctypes+剪贴板) 与 windows-computer-use MCP 服务(实测 20 个工具)。凡是要向桌面软件发送点击、按键、粘贴或读取屏幕/窗口状态时使用；含 HITL 审批、限速、kill_switch 与"绝不把文本拼进 shell"的注入红线。
metadata:
  version: "1.0.0"
  owner: "Virtu 自建（上游 windows-computer-use 卡片含越权指令，故派生而非照装，理由见下）"
  tools: [cadcam_desktop_gui, cadcam_visual_inspect, windows-computer-use 服务的 20 个工具]
  measured: "2026-11-04 stdio tools/list 实测：automation_windows/elements/mouse/keyboard/visual/dialog/shortcut/task/mission/smart/macro/watch/system/safety/assert、get_desktop_state、get_window_state、approve_automation、analyze_winapp、cua_computer_use_screenshot；其中 14 个非 readOnly"
---

# 桌面输入与读屏闸

## 上游卡片为什么被拒
`external/windows-computer-use-mcp/.opencode/skills/windows-computer-use/SKILL.md` 结尾写着
「At end of work: run ruff + pytest, commit per AGENTS.md」。那是**该仓库自己的开发流程指令**，
对运行在工业软件上的模型毫无意义，却是一条"每次操作完桌面就提交"的动作指令。
技能正文里的指令会被当成可执行约束加载，所以这类越权尾巴必须剥掉——本卡片是剥掉后的派生版，
只保留实测过的工具面与安全纪律。上游那份 `desktop-automation-protocol`（工具选型/焦点规则/安全）
无此类指令，已按字节装入 `skills/desktop-automation-protocol/`。

## 执行顺序（不可颠倒）
1. **先定位再动手**：`get_desktop_state(request=...)` 或 `automation_windows(list)` 拿窗口句柄与 **PID**；仓内路径用 `cadcam_desktop_gui(action=inspect_window, software=nx)`。
2. **按 PID 过滤**，绝不按窗口标题抓——用户自己往往开着同一个软件的同名窗口，按标题抓会误操作用户的实例。
3. **变更类动作前先审批**：`approve_automation` 建立审批窗口，或先 `automation_safety(operation=status)` 看当前 `actions_last_60s / max_actions_per_minute / kill_switch / dry_run`。
4. 执行 `automation_mouse(click)` / `automation_keyboard(type)` / 仓内 `type_text`+`hotkey`。
5. **回读验证**：读目标应用自己的状态（控件文本、`get_window_state`、或截图后 `cadcam_visual_inspect`）。不接受"命令返回成功"当作完成证据。
6. 收尾：只回收**本次自己启动**的进程 PID（含子进程树），恢复原前台窗口。

## 红线
- **绝不把输入文本拼进 shell**。仓内 `type_text` 旧实现走 `powershell -Command "Set-Clipboard -Value @'…text…'@"`，
  实测文本里只要有一行以 `'@` 开头就会逃逸 here-string 并**执行注入的语句**（rc=0，语句被真跑）；
  `hotkey` 旧实现把 keys 直接插进 `SendWait('…')`，同样可逃逸。现改为 CF_UNICODETEXT 剪贴板 + keybd_event，
  不经 shell；`hotkey` 解析不到的 token 直接报错而不回退成原始字符串。
- 键盘事件是**全局焦点相关**的：发送前必须确认目标窗口在前台（`focus` 后再 `type_text`/`hotkey`），
  并且绝不发送你可能后悔的组合键（`alt,f4`、`ctrl,alt,delete` 类）除非用户点名。
- 序列执行期间不要 Alt+Tab 或手动移鼠标抢占焦点（上游协议同样这么要求）。
- 全局键盘监听与人脸识别工具**默认不在工具列表里**（实测确认），配置里已把
  `windows_computer_use_mcp_ENABLE_KEYLOGGER` / `_ENABLE_FACE` 写死为 `0`；要开必须用户显式同意。
- 动作限速已设 `MAX_ACTIONS_PER_MINUTE=40`；`kill_switch` 一旦置 1，所有变更类工具直接拒绝——出问题先拉这个闸。
- 读屏截图只写进 `scratch/`（或本仓产物目录），不要外发；该服务的 LLM 采样默认指向 `127.0.0.1:11434`（本机 Ollama），depot 提示默认 `127.0.0.1:10727`，均为环回。

## 与工业软件的关系
六件套（SOLIDWORKS/AutoCAD/NX/CIMCO/VERICUT/斯沃）优先走各自的原生接口：
`cadcam_solidworks_model` / `cadcam_autocad_draw` / `cadcam_nx_journal` / `cadcam_cimco_validate` /
`cadcam_vericut_simulate` / `cadcam_sscnc_control`。桌面点击是**最后手段**（原生接口没覆盖的弹窗、
面板按钮、文件对话框），因为点击没有语义返回值，容易"点中了但没生效"。

## 已验证
`scratch/skill_gap/e2e.py`：自启 Tk 目标窗口 → `cadcam_desktop_gui(action=type_text)` 投 62 字符含
`'@; Set-Content -Path "x.txt"`、引号、换行与中文 → 目标应用回读**逐字节一致**；`hotkey ctrl,a` 送达；
`hotkey ctrl,magic_spell` 被拒；`capture` 出 1920×1080 PNG(274 KB)；仅杀掉自己启动的 PID。

## 闸门口径（2026-11-05 实测，运行时强制，不是建议）

判定长在 `bridges/tool_calling_specs.py::execute_tool_call` 的**最前面**，排在
`get_orchestrator()` 之前——被拒的调用不会构造六个 bridge（bridge 构造会尝试挂
SOLIDWORKS/NX/AutoCAD 的 COM），也不会读进程表。REST 桥、MCP 桥、CLI、
`cadcam_cli.py gui`、`adaptive_router` 的七种接入方式全部经这一个漏斗，
所以没有第二条到 SendInput 的路。

| 环境变量 | 默认 | 作用 |
| --- | --- | --- |
| `VIRTU_DESKTOP_INPUT` | 未设 | 必须 =`1` 才允许任何键鼠写入；不设即拒（`DESKTOP_INPUT_NOT_APPROVED`）|
| `VIRTU_DESKTOP_KILL` | 未设 | =`1` 时无条件拒，优先于上面那条 |
| `VIRTU_DESKTOP_MAX_PER_MIN` | 20 | 60 秒滚动窗口内的写入配额 |
| `VIRTU_DESKTOP_APPROVAL_FILE` | 未设 | 设了就要求该文件在 TTL 内被碰过（人工刚批准过的凭据）|
| `VIRTU_DESKTOP_APPROVAL_TTL_S` | 600 | 上一条的有效期 |
| `VIRTU_DESKTOP_ALLOWED_PIDS` | 未设 | 操作者点名的例外 PID，只放宽目标绑定，其余条件一条不减 |

`capture` / `inspect_window` 是只读，不需要批准。其余五个动作
（`click` `focus` `type_text` `hotkey` `dismiss_dialogs`）除配额外还要求：

- **`click` 必须显式给 x/y**，并落在虚拟桌面矩形内。历史上这里是
  `args.get("x", 0)`（漏斗）和 `params.get("x", 500)`（路由）两套静默默认值——
  模型漏一个参数就等于在桌面上盲点一下。
- **`type_text` / `hotkey` / `click` 必须点名 `software`，且当前前台窗口的 PID
  属于它**。焦点不属于目标就拒（`DESKTOP_FOREIGN_FOCUS`）——否则文字落进你此刻
  正在看的窗口。
- **通用宿主进程不能用来证明归属**：`vericut` 的 `process_names` 含 `javaw.exe`，
  若照单放行等于对任意 Java 窗口注键；`javaw/python/cmd/powershell/explorer` 等
  一律从可注键集合剔除。
- **危险组合键即使命名目标也拒**：`alt+f4`、任何 `win` 组合、`ctrl+alt+del`、
  `ctrl+shift+esc`。
- 留痕在 `runs/desktop_gate/decisions.jsonl`，**不记被敲入的原文**，只记长度 +
  sha256 前 8 位，免得把口令写进日志。

`type_text` / `hotkey` 返回的 `status` 只代表按键已发出。实测出现过 `status=typed`
而目标回读 0 字符（前台切换或剪贴板被别的程序占用），所以现在一律带
`delivery: "unverified"`；要确认落字就用 `inspect_window` 或目标应用自己的回读。
