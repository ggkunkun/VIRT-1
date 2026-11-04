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
