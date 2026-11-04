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
1. **未改 `mcp_cadcam_config.json`**：添加工具服务器会改变被服务模型的工具面，并让同一款 CAD 出现两个 COM 挂接方。
2. **未改 `Flange_Machining_O1001.nc` 本体**：加工程序是产物，修正副本在 `scratch/skill_gap/Flange_Machining_O1001_fixed.nc` 供逐行比对（Q5000→Q5.0、`X#106 C#120`、孔深 `Z-[#103+1.0]`、补 `G50 S2000`、`G85 X#102` 使孔径生效）。

版本控制提醒：`skills/` 与 `virtu_omni/engine/` 绝大多数文件此前从未被 git 跟踪，本文件与本次改动已纳入跟踪，其余仍未跟踪。
