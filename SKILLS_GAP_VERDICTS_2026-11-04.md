# GitHub 技能缺口判决与闭环补强（2026-11-04）

模型技能根 = `D:\Virtu模型\skills`（`virtu_omni/agent/skill_writer_and_memory.py` 的 `skills_root`；`virtu_omni/harness2/surface.py` 将 `skills/` 列为 c6 面）。
机器可读明细：`scratch/skill_gap/skill_matrix.json`；安装台账：`skills/SKILLS_PROVENANCE.json`（21 条，含每文件 sha256）。

## 安装判据（先定尺子）
本模型的真实工具面 = `bridges/tool_calling_specs.py` 的 **14 个 `cadcam_*`**（`mcp_cadcam_config.json` 只注册 `industrial-cadcam` 一个 server）。
因此顺序是：① 领域相关 → ② **工具无关**（绑定别的 MCP 的技能会把不存在的工具名喂进上下文，直接生产幻觉调用）→ ③ 无出站/凭据面 → ④ 不与已装重名。

去重后缺口 216 个（`external/` 内 300 份 SKILL.md 减去已装 29）：

| 档 | 数量 | 处置 |
|---|---|---|
| T1 上游领域技能 | 16 | 字节一致安装（AgentCADCAM×14 + `mechanical-drafting-gbt` + `ctq-extraction`） |
| T1 自建闭环技能 | 5 | 本档下文，带可执行脚本与正反夹具证据 |
| T2 后端未接 | 8 | 不装，逐条门条件见下 |
| T2 保密/出站红线 | 2 | 不装（PaddleOCR 两技能需第三方 API token 且要上传图纸） |
| T3 上游应用自用/重复副本 | 185 | 不装（paperclip 77、claude-mem 44、claude-plugins-official 33、课程仓夹具 32、impeccable 25 份重复、superpowers 15 等） |

## 自建 5 个技能（GitHub 该域无可落位源，实测见下）
| 技能 | 执行器 | 正反验收 |
|---|---|---|
| `fanuc-macro-b-post-gate` | `scripts/validate_nc.py` | O1001 → 8 阻断/5 类码；修正副本 → 0 阻断 exit 0 |
| `cae-fos-gate` | `scripts/fos_crosscheck.py` | 法兰/轴/支座闭式解与引擎 rel_diff ≤ 0.0006 且屈服一致 |
| `sheetmetal-nest-verification` | `scripts/verify_nest.py` | 12 件排样 NEST_OK（重算 42.075% vs 抬头 42.08%）；突变体 OVERLAP+OUT-OF-SHEET |
| `vericut-autodiff-triage` | `scripts/triage_autodiff.py` | 绿图 ACCEPTED / 全零像素 INSUFFICIENT_EVIDENCE / 有过切却判合格 STOP / 日志图像冲突 STOP |
| `sscnc-touchoff-ledger` | `scripts/touchoff_ledger.py` | 自洽 OK / 偏置反号 / 刀号重复 / 缺火花确认 / 磨损超限 各阻断 |

## 同期修掉的 3 个假绿缺陷（`virtu_omni/engine/universal_cae_engine.py`）
1. 材料名不在表内 → 静默改用 Cr12MoV(σy 850)，而工具默认传 "45号钢" ⇒ FOS 虚高 2.4×。现返回 `blocked / MATERIAL_UNRESOLVED`。
2. 工具层 `force_n`→`load_n` 与各族读取的 `radial_load_n/bending_force_n` 不同名 ⇒ 用户载荷被丢弃；`torque_nm` 从不参与 von Mises。现做键名归一并加入扭矩。
3. 自愈未达标仍返回 `optimized` 且判词写死 "(>= 1.5)"；钣金族走轴分支只改外径而公式不用外径（0.83→0.83 仍称已强化，按半径自愈会算出 ~957 mm 圆角）。现未达标判 `not_healed`；钣金族判 `formability_advisory` 并禁止按强度自愈。

回归：`tests/test_cae_gate_honesty.py`（7 例）+ 既有 10 例全绿；全量 160 passed，唯一失败 `tests/test_cloud_bundle.py::test_prerequisites_are_asserted_before_anything_is_installed` 为既有漂移（bootstrap 脚本已无 `"venv + deps"` 字面量，该测试零处引用 CAE）。

## T2 后端未接的 8 个：装它们的门条件
| 技能 | 门条件 |
|---|---|
| `nx-modeling` | NX_MCP 服务在跑且 `nx_status/nx_create_part/nx_list_bodies` 真出现在工具面；本仓 NX 路径是 `cadcam_nx_journal`(run_journal/UF_MODL)，两者并存须约定单一入口 |
| `autocad-mcp-premium` | AutoCAD MCP Pro 注册且 `drawing_preflight/mech_part_draw/cad_batch` 可见；与 `bridges/autocad_bridge.py` 并存时同一 AutoCAD 实例只允许一个写入口 |
| `windows-automation` / `windows-cli` | `windows-mcp` 服务或 `wincli.exe` 存在 |
| `windows-computer-use` / `desktop-automation-protocol` | 该 MCP 在跑；当前桌面感知已由 `cadcam_desktop_gui` + Qoder computer-use 承担，功能重复 |
| `cadquery-builder` / `projection-verification` | `cadquery` 可导入 **且** 其 I/O 契约的容器绝对路径 `/input`、`/artifacts` 被改写为仓库相对（那是派生技能，不能按上游字节装） |

`pynitefea 3.2.1` 已装进 MCP 服务实际使用的 `Python312`（PyPI 上 `PyNite` 名字被 Fortnite 封装占用，先卸后装；v3.2 导入名是 `Pynite`）。`cadquery` 未装：本仓 CAE 走解析式不需要，且光装库解决不了上面那条路径契约。

## GitHub 检索实测（为什么只能自建）
- `Cai-aa/CAE-Agent-Hub`：63 份 SKILL.md，全绑 Abaqus/Ansys/COMSOL/CalculiX/FEniCS；本机六软件无任一 CAE 求解器 ⇒ 不可落位。
- `tian-yu200/solidworks-cad-skill`、`panp20469-png/solidworks-parametric-cad-skill`：SKILL.md 明令"只准用九个 `mcp__solidworks__` 工具，禁止 COM/宏/journal/桌面自动化" ⇒ 与 AGENTS.md §2A 和本仓桥接直接冲突。
- `anthropics/skills`：仅文档类；`VoltAgent/awesome-agent-skills`(千条目录) grep `cad|cnc|gcode|fea|nesting|vericut` 零命中；`gcode/cnc/vericut/nesting + skill` 仓名检索只到 0 星试验仓。

## 尚未做、需要单独授权的两件事
1. ~~未改 `mcp_cadcam_config.json`~~ → **本节写作后已做，见文末「追补三」**：模型侧工具面确实被改动，两个 COM 挂接方的风险由「单实例账本 + 只接管已开实例」约束，而非由不注册来回避。
2. **未改 `Flange_Machining_O1001.nc` 本体**：加工程序是产物，修正副本在 `scratch/skill_gap/Flange_Machining_O1001_fixed.nc` 供逐行比对（Q5000→Q5.0、`X#106 C#120`、孔深 `Z-[#103+1.0]`、补 `G50 S2000`、`G85 X#102` 使孔径生效）。

版本控制提醒：`skills/` 与 `virtu_omni/engine/` 绝大多数文件此前从未被 git 跟踪，本文件与本次改动已纳入跟踪，其余仍未跟踪。

## 2026-11-04 追补二：桌面输入与读屏接入
候选实测：`windows-mcp` 要 Python >=3.14、`mcp-windows` 要 .NET 10 编译 → 本机不可用；**`windows-computer-use-mcp` 要求 >=3.12 ✓**，但它要 `fastmcp[server]`，而后者要求 `mcp<2`，与本机 `build123d-mcp`（`mcp>=2,<3`）冲突——把共享 `Python312` 的 mcp 从 2.3.0 降到 1.30.0 会直接砸掉 build123d-mcp（已实测并回滚）。因此该项目**装进项目内独立 venv** `external/windows-computer-use-mcp/.venv`。

stdio 实测工具面（v0.8.0，20 个，其中 14 个非 readOnly）：`automation_windows/elements/mouse/keyboard/visual/dialog/shortcut/task/mission/smart/macro/watch/system/safety/assert`、`get_desktop_state`、`get_window_state`、`approve_automation`、`analyze_winapp`、`cua_computer_use_screenshot`。全局键盘监听与人脸工具**不在列表内**（需 `ENABLE_KEYLOGGER`/`ENABLE_FACE` 显式置真才注册），配置里已写死为 `0`，并设 `MAX_ACTIONS_PER_MINUTE=40`；`automation_safety(operation=status)` 可读 `kill_switch/dry_run/actions_last_60s`。注册点：`mcp_cadcam_config.json` 与 `AGENT_TOOLCHAIN_INTERFACE.md` 模式 3。

上游技能卡片处置：`desktop-automation-protocol` 按字节装入（并把 `docs/SAFETY.md` 一并放进 `references/` 让指引可解析）；`windows-computer-use` **拒装**——它正文结尾要求"任务结束时跑 ruff+pytest 并按 AGENTS.md 提交"，那是上游仓库自用开发流程对运行态模型的越权动作指令；改派生自建 `windows-desktop-input-gate`（只留实测工具面 + PID 级窗口纪律 + HITL/限速/kill_switch + 注入红线）。

顺手补掉仓内一个**真注入洞**：`bridges/desktop_controller.py` 的 `type_text` 旧实现把输入文本拼进 `powershell -Command "Set-Clipboard -Value @'…'@"`，实测文本中一行以 `'@` 开头即可逃逸 here-string 并让注入语句被执行（rc=0，语句真的跑了）；`hotkey` 把 keys 直插 `SendWait('…')` 同理。现改为 `CF_UNICODETEXT` 剪贴板 + `keybd_event` 组合键，全程不经 shell，且未识别的组合键直接报错不回退。端到端验证（`scratch/skill_gap/e2e.py`，自启 Tk 目标窗口并只杀自己起的 PID）：62 字符含 `'@; Set-Content -Path "x.txt"`、引号、换行与中文 → 目标应用回读**逐字节一致**；`hotkey ctrl,a` 送达；`hotkey ctrl,magic_spell` 被拒；`capture` 出 1920×1080 PNG(274 KB)。同时 `cadcam_desktop_gui` 补齐了代码里早已实现却未暴露的 `type_text/hotkey/inspect_window`，并让 `click` 的 `button/double` 真正透传（此前被丢弃）。

## 2026-11-04 追补三：客户端（Qoder 侧）MCP 注册落地与握手取证
模型侧 `mcp_cadcam_config.json` 早就写了两个服务器，但**客户端注册一直是空的**——不注册就没人真的能调到这些工具，"已接入"只是文件里的一句话。本次补上并按字面取证。

注册点选 **local 作用域** `.qoder/settings.local.json` 而不是 project 作用域 `.qoder/settings.json`：后者会提交进 git，协作者一拉取就自动拉起一个能注入鼠标键盘的通道，等于把输入控制权随源码分发。要升级为团队共享，把同一段 JSON 移进 `.qoder/settings.json` 即可，配置体本身不用改。配套边界文件 `.qoder/.gitignore`（内容 `settings.local.json`）已建立，`git check-ignore -v` 回 rc=0 命中该规则；不动根 `.gitignore`（另一会话正在其中追加 `.damodel_pass` 等凭据规则，避免抢写）。

取证方式不是"我配置写对了"，而是 `scratch/skill_gap/probe_registered_mcps.py` 读注册文件、按每个字段的 `command/args/cwd/env` 原样起进程，走 `initialize → notifications/initialized → tools/list`，只额外调**只读**的 `automation_safety`，不触发任何写操作工具：

| 服务器 | 握手 | 工具数 | 说明 |
| --- | --- | --- | --- |
| `windows-computer-use` | ok | **20** | 14 个非 readOnly；全局键盘监听与人脸工具不在列表内 |
| `industrial-cadcam` | ok | **14** | 与 `bridges/tool_calling_specs.py` 的模型侧工具面同名同集 |

注册态回读的安全闸（`automation_safety` 实际返回，非配置文件里的期望值）：`max_actions_per_minute=40`、`actions_last_60s=0`、`total_mutations_session=0`、`kill_switch=false`；进程环境回读 `ENABLE_KEYLOGGER=0`、`ENABLE_FACE=0`。`DEPOT_URL` 经源码核对默认即 `http://127.0.0.1:10727`（`src/windows_computer_use_mcp/fleet_error_hints.py:27`），配置里显式钉在回环地址，杜绝错误提示查询走外网。

仍未授权、仍未做的一件事：**根目录 `Flange_Machining_O1001.nc` 本体未改**。刚复跑闸，它仍报 5 类 2 FATAL（`NC-Q-UNIT` 米制 Q5000、`NC-POLAR` 角度被算两次、`NC-DEAD-VAR` #106 未生效、`NC-DEPTH-MISMATCH`、`NC-G50-MISSING`）。加工程序是交付产物，改它等于改要上机的刀路，只提供了逐行修正副本 `scratch/skill_gap/Flange_Machining_O1001_fixed.nc` 供比对；是否替换本体需要明确指令。

vendored 第三方不纳入父仓：`external/windows-computer-use-mcp` 自带 `.git`（`sandraschi/windows-computer-use-mcp` @ `b71afd0cd164…`，v0.8.0，MIT，工作树干净）。`git add` 它只会生成 gitlink/子模块占位，故只在 `skills/SKILLS_PROVENANCE.json` 的 `mcp_registration_2026-11-04` 块里记 provenance。

## 2026-11-05 追补四：模型到底能不能操控这台电脑——审计、修复、真机取证
结论：**能，而且此前有五条路都没闸**。第三方 MCP 服务器的 `approve_automation`/限速/kill_switch
只保护它自己那条通道；`approve_automation` 这个符号在仓内运行时代码里的引用数是 **0**。

真正接住模型的是仓内通道，而且 `scripts/workbuddy_virtu_bridge.py` 是
`Auto-executing`——模型吐出 tool call 就直接执行，`_validate_tool_call` 只是工具名白名单，
`cadcam_desktop_gui` 本身就在白名单里。

### 修掉的四个缺陷
1. **漏斗没闸**：`execute_tool_call` 的 `cadcam_desktop_gui` 分支直落 `DesktopController`。
   现把判定排在函数**最前面**、排在 `get_orchestrator()` 之前——原先即便这次调用会被拒，
   也已经构造了六个 bridge（其中几个尝试挂 SOLIDWORKS/NX/AutoCAD 的 COM）。拒绝必须零副作用。
2. **CLI 通道整条绕过漏斗**：`cadcam_cli.py::cmd_gui` 自己 new `DesktopController()`，
   且 `click` 写的是 `args.x or 0` —— 静默点屏幕左上角 (0,0)。现统一走 `execute_tool_call`。
3. **路由层同样绕过，且默认值不一样**：`adaptive_router._execute_gui` 用
   `params.get("x", 500)` —— 与漏斗的 (0,0) 是两个不同的盲点坐标。同时
   `GUI_ACTIONS` 只有 4 个动作，缺 `type_text/hotkey/inspect_window`，即工具面已暴露、
   路由却永远路由不到；CLI 容灾分支还拿 `dismiss_dialogs` 去撞 argparse 的
   `dismiss-dialogs`，那个动作在 CLI 接入方式下一直是 rc=2。
4. **假成功**：`type_text` 会返回 `status=typed`，但实测出现过按键已发、目标回读 0 字符
   （前台切换/剪贴板被占用）。现补 `delivery:"unverified"` + `verify_with`，
   确认落字只能靠 `inspect_window` 或目标应用回读。

### 闸门规则（`bridges/desktop_gate.py`，fail-closed）
默认全部拒绝；`VIRTU_DESKTOP_INPUT=1` 才允许写入，`VIRTU_DESKTOP_KILL=1` 优先于一切；
60 秒滚动配额默认 20；`click` 必须显式给界内坐标；`type_text/hotkey/click` 必须点名
`software` 且**当前前台 PID 属于它**；`javaw/python/cmd` 等通用宿主不得用来证明归属
（`vericut` 的 `process_names` 里就有 `javaw.exe`）；`alt+f4`、任何 `win` 组合、
`ctrl+alt+del`、`ctrl+shift+esc` 即使目标已绑定也拒。留痕 `runs/desktop_gate/decisions.jsonl`
不记被敲入原文，只记长度与 sha256 前 8 位。

### 取证
`tests/test_desktop_gate.py` 14 项、pytest 下 33 项（含既有链式与 CAE 闸）全绿；
判据不是只看返回值，而是把 `win32api.mouse_event/keybd_event/SetCursorPos` 换成会抛断言的
spy——被拦下时一个输入 API 都不许碰到。真机 E2E（`scratch/skill_gap/e2e_gate.py`）6/6：
自起 Tk 目标窗、按 PID 操作、用完即还原前台焦点；5 个拦截场景目标框保持空，
1 个批准场景 72 字符逐字节命中（含 `'@` here-string 逃逸串、`Ø`、中文）。
另单独连跑 4 次批准粘贴：3/3 逐字节命中，第 1 次因前台尚未落到目标窗而被闸拦下——
拦在写入之前，不是写错地方。

E2E 首版还暴露一个方法论坑：测试窗 `-topmost + focus_force` 会**抢走操作者的输入焦点**，
于是操作者自己的按键落进测试输入框，把"拦截是否零输入"这条判据污染成假失败
（第一轮里 `h`/`hi` 就是这么来的）。改成动作前清空 + 动作后立刻还原前台后判据才干净。

### 没动、需要单独决策的一件事
`scripts/generate_omni_autonomous_agent_corpus.py:229,242` 把
`{"status": "typed", "length": 25}` 这类**未经回读确认的观察**硬编码进训练轨迹。
运行时现在如实标注 `delivery:"unverified"`，但语料教的仍是"按过＝写成"。
改语料等于改训练数据，这条留给是否重造语料的决定。
