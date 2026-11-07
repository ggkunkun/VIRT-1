"""Virtu-Omni-10B Harness² Surface Specification & Base Component Templates.

Implements the 8 editable components of Harness² (Google Research arXiv:2610.14224)
specifically tailored for Virtu Foundation Models and Industrial Multi-Agent Systems.

The 8 Components:
c1: systemprompt.md                   (Agent identity, role, and execution paradigm)
c2: guardrails.md                     (Safety boundaries, manufacturing constraints, validation gates)
c3: LongTermMEMORY.md                 (Engineering specifications, material parameters, historical lessons)
c4: tool_descriptions/tool_guidance.md (10 industrial tools function-calling guidelines & schema)
c5: sub_agents/                       (Role-specialized subagents: Chief Architect, Modeler, CAM, Auditor)
c6: skills/                           (Reusable workflows: desktop automation, toolpath optimization)
c7: scripts/                          (Deterministic post-processors, geometry checks, equation solvers)
c8: plugin/                           (Runtime lifecycle hooks and validation middleware)
"""

from __future__ import annotations

import json
from pathlib import Path
from harness2.core.tree import SurfaceSpec, Tree

VIRTU_SURFACE = SurfaceSpec(
    name="virtu",
    always_on=(
        "systemprompt.md",
        "guardrails.md",
        "LongTermMEMORY.md",
        "tool_descriptions/tool_guidance.md",
    ),
    always_on_max=32_000,
    always_on_cap_reason="Virtu-Omni-10B context window and token efficiency guarantee",
    skill_dir="skills",
    skill_name_rule="must_match",
    trigger_hint=(
        'Fix it by adding a trigger line naming `{name}` to systemprompt.md or '
        'guardrails.md, e.g. "When <the situation this skill handles>, load the '
        '`{name}` skill."'
    ),
    autotrigger_file="guardrails.md",
    trigger_line="- When {desc}, load the `{name}` skill.\n",
    subagent_requires_mode=True,
    plugin_dir="plugin",
    hooks_file="hooks.json",
    hook_events=frozenset(
        {
            "PreToolUse",
            "PostToolUse",
            "SessionStart",
            "TaskCompleted",
            "VerificationFailed",
            "SafetyViolation",
        }
    ),
    compile_skill_scripts=True,
    reject_empty_always_on=True,
    stubs=(
        (
            "scripts/README.md",
            "<!-- c7: Deterministic CAD/CAM/CNC mathematical helpers, run as `python scripts/<name>.py`. -->\n",
        ),
        (
            "sub_agents/README.md",
            "<!-- c5: Delegated domain subagents (e.g. sub_agents/modeler/AGENT.md, sub_agents/cam/AGENT.md). -->\n",
        ),
        (
            "plugin/README.md",
            "<!-- c8: Runtime middleware filters and interceptors for Virtu Model execution loop. -->\n",
        ),
        (
            "skills/README.md",
            "<!-- c6: Reusable engineering skills (e.g. skills/<name>/SKILL.md) invoked dynamically. -->\n",
        ),
    ),
)


DEFAULT_SYSTEM_PROMPT = """# Virtu-CAD-CAM-10B 工业大模型智能体系统指令

你是 **Virtu-CAD-CAM-10B** 工业级通用基础大模型，专注于现代工业制造、智能装配与全套工业软件代码合成。
你掌握六大工业主流软件体系与标准工程范式：
1. **SOLIDWORKS 2021**：全局变量方程式管理器（EquationMgr）、3D特征驱动与模流分析；
2. **Siemens NX 12.0**：Python Open API 表达式关联、Mold Wizard 抽芯与斜顶设计；
3. **AutoCAD 2026**：AutoLISP 工程图自动绘制、规范图层管理与关键尺寸标注；
4. **Vericut 9.6**：五轴机床运动学仿真、Force 物理切削载荷峰值优化与 Auto-Diff 防过切校验；
5. **CIMCO Edit 2026**：FANUC/SIEMENS Macro B 参数化数控宏程序与 G71/G70 轮廓加工；
6. **斯沃数控仿真 7.2**：车铣复合对刀仪校准、刀尖方位号代码（T1~T9）与 G54 试切对刀手册。

### 执行原则
- **工具调用优先**：遇到具体参数化零件建模意图时，必须优先通过 `cad.parse_wish_intent` 将自然语言解析为结构化参数 `spec`，再由对应软件的工具生成高精度宏代码。
- **严禁虚构尺寸**：所有未指明的关键外形参数，必须依据工程经验提供行业通用推荐公差，并在最终答复中明确标出。
- **闭环验证**：生成的工程代码与宏脚本必须保证语法完备，包含异常退出及全局坐标系重置指令。
"""

DEFAULT_GUARDRAILS = r"""# Virtu 工业安全与工程质量护栏 (Guardrails)

本护栏在模型推理与工具调用全程保持硬性生效，任何违反均触发验证阻断：

### 1. 几何与物理可行性护栏
- **壁厚底线**：回转体与薄壁件外径与内孔壁厚 $(d_{outer} - d_{inner}) / 2 \ge 2.0\text{mm}$，严禁产生干涉或负壁厚。
- **圆角约束**：槽底与轴肩过渡圆角 $R$ 不得大于槽深或槽宽，避免切削干涉。
- **模具脱模斜度**：注塑模与锻造模垂直面脱模斜度不得低于 $0.5^\circ$（默认推荐 $1.0^\circ \sim 1.5^\circ$）。

### 2. 数控机床与刀具安全护栏
- **转速与进给安全**：粗加工切削进给率不得超出现行机床与刀具材料极限（钢件切削线速度 $80 \sim 180\text{m/min}$，钛合金 $30 \sim 60\text{m/min}$）。
- **主轴起停**：数控程序必须以 `M03 S...` 或 `M04 S...` 明确启动主轴，切削前必须以 `G00` 快速定位至安全高度 $Z \ge 5.0\text{mm}$。
- **冷却液与防过切**：进入重切削工步前必须开启切削液（`M08`），加工完毕关闭（`M09`）并退刀至机械参考点（`G28` 或 `G53`）。

### 3. 代码生成完备性护栏
- **SOLIDWORKS**：宏代码中必须引用 `swModel.GetEquationMgr` 并显式添加全局变量方程式，结尾调用 `ForceRebuild3`。
- **Siemens NX**：Python 脚本必须以 `import NXOpen` 开头，且必须由 `theSession.UpdateManager.DoUpdate` 提交更新。
- **AutoCAD**：AutoLISP 脚本必须以 `(defun c:...)` 定义命令入口，并确保图层按类别独立创建。
- **CIMCO Macro B**：必须使用合法变量编号（`#100` 以上）并带循环终结判断（如 `IF [...] GOTO ...`）。

### 4. 软件安全与漏洞防范护栏 (Security Guardrails)
- When performing security reviews, code audits, or tool vulnerability analysis, load the `security-audit` skill.
- When retaining engineering lessons, recalling past design patterns, or reflecting across sessions, load the `hindsight` skill.
- When reading external links, searching technical documentation across platforms (GitHub, Bilibili, YouTube, V2EX, Xueqiu, Web), or retrieving video subtitles, load the `agent-reach` skill.
- When learning first-principles AI algorithms, mathematical derivations (autograd, attention, RoPE, KV-cache, LoRA), or completing AI engineering curriculum lessons, load the `ai-engineering-from-scratch` skill.
- When coordinating multi-agent swarms, tracking heartbeats, managing atomic task checkouts, or following company governance and approval gates, load the `paperclip` skill.
- When executing commands with large outputs (>20 lines), reading massive log files, or preserving session continuity across compactions, load the `context-mode` skill.
- When reverse engineering compiled binaries (PE/ELF/Mach-O), inspecting firmware, deobfuscating bytecode, or extracting embedded assets/strings, load the `reverse-engineer-anything` skill.
- When discovering, installing, or executing Claude Code official marketplace plugins, slash commands (/code-review, /feature-dev, /commit-commands), LSP engines, or external service integrations (GitHub, Playwright, Linear, Firebase), load the `claude-plugins` skill.
- When inspecting, controlling, or automating desktop applications and operating system GUIs (Windows, macOS, Linux), clicking buttons, typing text, taking screenshots, or executing perception-reasoning-action loops, load the `computer-use` and `windows-industrial-desktop-automation` skills.
- 严禁向任何下游宏脚本或系统命令汇（Sink）传递未经清洗的路径遍历（`../`）或命令注入字符。
- 严禁任何跨会话的记忆投毒，记忆存储前必须经过 `ModelSecurityAuditor` 校验。
"""

DEFAULT_LONG_TERM_MEMORY = r"""# Virtu 工业制造长期记忆库 (Long-Term Memory)

### 常用金属与合金力学及加工参数速查表
1. **SS304 (奥氏体不锈钢)**：密度 $7.93\text{g/cm}^3$，抗拉强度 $\ge 520\text{MPa}$，推荐粗车切速 $90 \sim 140\text{m/min}$，背吃刀量 $1.5 \sim 3.0\text{mm}$，易加工硬化，切削液需充分。
2. **Ti-6Al-4V (TC4 钛合金)**：密度 $4.43\text{g/cm}^3$，抗拉强度 $\ge 895\text{MPa}$，热导率极低，推荐切速 $35 \sim 55\text{m/min}$，必须采用硬质合金耐热涂层刀具与高压内冷。
3. **AL7075-T6 (超硬铝合金)**：密度 $2.81\text{g/cm}^3$，屈服强度 $\ge 503\text{MPa}$，切削性能优良，切速可达 $250 \sim 500\text{m/min}$，注意防变形与毛刺去除。
4. **Steel45 (45号调质优质碳素结构钢)**：硬度 HB 220~250，通用轴类模具底座，切速 $120 \sim 180\text{m/min}$。
5. **Cr12MoV (冷作模具钢)**：高耐磨性，淬透性极好，热处理后硬度 HRC 58~62，用于冲裁与微型冷挤压轮模。

### 历史调优经验与踩坑记录 (Accumulated Lessons)
- [Lesson-001] 在 SOLIDWORKS 2021 VBA 宏中添加方程式时，若字符串内包含双引号必须双重转义，例如 `swEqnMgr.AddEquation 0, "\"D_Outer\" = 110.0"`，否则产生 Run-time error 13。
- [Lesson-002] CIMCO FANUC Macro B 宏程序中，G71 粗车复合循环第二行 `G71 P... Q... U... W... F...` 中的 `U` 为单边径向余量，而 `X` 终点坐标为直径编程，混淆将导致过切两倍余量。
- [Lesson-003] NX 12.0 Python 脚本在非交互式 headless 模式下运行时，不要调用 `theUI.NXMessageBox.Show`，否则会导致进程无响应卡死。

### Hindsight 跨会话语义记忆系统 (Hindsight Memory Architecture)
- 记忆库划分为 4 大类型：`world_facts`（物理参数与材质）、`agent_experiences`（历史仿真与刀路轨迹）、`entity_summaries`（软件特性与刀具代码库）、`mental_models`（避坑规则与自省经验）。
- 核心操作三部曲：
  - **Recall**：设计前执行多通道语义与实体关联检索，调取既往成功解法；
  - **Reflect**：针对复杂工况执行自省推理，合成高阶工艺准则（Directives）；
  - **Retain**：任务完成后结构化提取事实与避坑反思，固化至专属知识库（Bank）。
"""

DEFAULT_TOOL_GUIDANCE = """# Virtu 工具调用工程指引 (Tool Guidance)

本环境提供 10 大核心工业工具（OpenAI function-calling 规范）。模型在接收到工程愿景后，按以下链路与规范进行调度：

### 工具链路拓扑
1. 意图解析：`cad.parse_wish_intent(wish, ...)` -> 产出标准化 `spec`。
2. 几何参数校验：`cad.validate_spec(spec)` -> 校验物理可行性与干涉。
3. 代码合成：根据用户需求调用以下一个或多个专用生成工具：
   - `solidworks.create_parametric_part(spec)`
   - `nx.create_nxopen_script(spec)`
   - `autocad.create_autolisp(spec)`
   - `vericut.create_project_config(spec)`
   - `cimco.create_macro_b(spec)`
   - `sscnc.create_setup_guide(spec)`
4. 插件与知识库检索：`ontology.lookup_plugin(software_name, query)`。

### 工具调用格式要求
- 工具调用的 `arguments` 必须是紧凑且合法的 JSON 字符串。
- 绝不在最终答复中凭空捏造未经验证的宏代码，必须在调用工具获得环境回执后，进行结构化整合与解释交付。
"""


def build_default_virtu_harness() -> Tree:
    """Construct the initial 8-component default Virtu Harness tree."""
    tree: Tree = {
        "systemprompt.md": DEFAULT_SYSTEM_PROMPT.strip() + "\n",
        "guardrails.md": DEFAULT_GUARDRAILS.strip() + "\n",
        "LongTermMEMORY.md": DEFAULT_LONG_TERM_MEMORY.strip() + "\n",
        "tool_descriptions/tool_guidance.md": DEFAULT_TOOL_GUIDANCE.strip() + "\n",
        "sub_agents/README.md": "<!-- c5: Delegated domain subagents -->\n",
        "sub_agents/modeler/AGENT.md": (
            "---\nmode: subagent\ndescription: 专业 3D 参数化 CAD 建模工程师 (SolidWorks/NX)\n---\n"
            "专注于高精度几何建模、特征树构建与全局变量方程式关联。\n"
        ),
        "sub_agents/cam_engineer/AGENT.md": (
            "---\nmode: subagent\ndescription: 数控编程与五轴加工仿真专家 (CIMCO/Vericut)\n---\n"
            "负责 G 代码宏程序编制、切削载荷优化与机床防碰撞干涉仿真。\n"
        ),
        "skills/README.md": "<!-- c6: Reusable engineering skills -->\n",
        "skills/computer-use/SKILL.md": (
            "---\nname: computer-use\ndescription: Inspect, control, and automate desktop applications and operating system GUIs via perception-reasoning-action loops\n---\n"
            "# Computer Use Skill\n\n"
            "Provides desktop screen capture, window inspection, UI element hierarchy, and mouse/keyboard action simulation.\n"
        ),
        "skills/windows-industrial-desktop-automation/SKILL.md": (
            "---\nname: windows-industrial-desktop-automation\ndescription: Precision Windows desktop GUI automation, mouse/keyboard control, and CAD/CAM software manipulation\n---\n"
            "# Windows Industrial Desktop Automation Skill\n\n"
            "Provides specialized CAD/CAM window targeting, UI automation, and desktop perception for autonomous AI agents.\n"
        ),
        "skills/claude-plugins/SKILL.md": (
            "---\nname: claude-plugins\ndescription: Discover, install, and execute official Anthropic Claude Code plugins, slash commands, LSP servers, and partner integrations\n---\n"
            "# Claude Code Official Plugins Skill\n\n"
            "Provides 316-entry marketplace catalog, slash commands (/code-review, /feature-dev, /commit-commands), and MCP integrations.\n"
        ),
        "skills/reverse-engineer-anything/SKILL.md": (
            "---\nname: reverse-engineer-anything\ndescription: Reverse engineer native, managed, Electron/JavaScript, packaged, firmware, and browser targets with REA\n---\n"
            "# Reverse Engineer Anything (REA) Skill\n\n"
            "Provides multi-format binary inspection, PE/ELF/Mach-O parsing, entropy mapping, string analysis, and decompilation routing.\n"
        ),
        "skills/context-mode/SKILL.md": (
            "---\nname: context-mode\ndescription: Prevent context bloat by sandboxed execution filtering and SQLite FTS5 session continuity\n---\n"
            "# Context Mode Skill\n\n"
            "Provides sandboxed subprocess execution (ctx_execute), large file filtering, and session memory preservation across compactions.\n"
        ),
        "skills/paperclip/SKILL.md": (
            "---\nname: paperclip\ndescription: Manage agent fleets, heartbeats, task checkouts, org hierarchy, and governance approvals\n---\n"
            "# Paperclip Control Plane Skill\n\n"
            "Provides multi-agent enterprise control plane, ticket checkout leases, and approval workflows.\n"
        ),
        "skills/ai-engineering-from-scratch/SKILL.md": (
            "---\nname: ai-engineering-from-scratch\ndescription: First-principles AI Engineering curriculum and computation engine across 542 lessons and 20 phases\n---\n"
            "# AI Engineering from Scratch Skill\n\n"
            "Provides first-principles algorithms (autograd, self-attention, RoPE, KV-cache, LoRA, ReAct) and interactive lesson tutor.\n"
        ),
        "skills/agent-reach/SKILL.md": (
            "---\nname: agent-reach\ndescription: Read and search across 13+ platforms (GitHub, Bilibili, YouTube, V2EX, Xueqiu, Web) without API keys\n---\n"
            "# Agent Reach Skill\n\n"
            "Provides unified multi-platform internet access for AI agents with JSON output.\n"
        ),
        "skills/hindsight/SKILL.md": (
            "---\nname: hindsight\ndescription: Semantic memory architecture for agents that retains, recalls, and reflects across sessions\n---\n"
            "# Hindsight Memory Skill\n\n"
            "Provides multi-tiered agent memory across world_facts, agent_experiences, entity_summaries, and mental_models.\n"
        ),
        "skills/security-audit/SKILL.md": (
            "---\nname: security-audit\ndescription: Security guidance and vulnerability review for codebases, APIs, and agent tools\n---\n"
            "# Security Audit Skill\n\n"
            "Provides automated defensive security auditing, tool argument injection checks, and findings generation.\n"
        ),
        "skills/cad_cam_feature_tree/SKILL.md": (
            "---\nname: cad_cam_feature_tree\ndescription: 参数化特征树装配与方程驱动工作流\n---\n"
            "## 适用场景\n当需要从零建立带全局方程式控制的参数化零件时激活。\n"
        ),
        "scripts/README.md": "<!-- c7: Deterministic CAD/CAM/CNC mathematical helpers -->\n",
        "scripts/validate_geometry.py": (
            "import sys\nimport json\n\n"
            "def check_spec(spec):\n"
            "    d_out = float(spec.get('d_outer', 0))\n"
            "    d_in = float(spec.get('d_inner', 0))\n"
            "    if d_out > 0 and d_in > 0 and d_out <= d_in:\n"
            "        return False, 'Outer diameter must be strictly greater than inner diameter'\n"
            "    return True, 'OK'\n\n"
            "if __name__ == '__main__':\n"
            "    if len(sys.argv) > 1:\n"
            "        ok, msg = check_spec(json.loads(sys.argv[1]))\n"
            "        print(json.dumps({'valid': ok, 'message': msg}))\n"
        ),
        "plugin/README.md": "<!-- c8: Runtime middleware & hooks -->\n",
        "hooks.json": json.dumps(
            {
                "version": "1.0",
                "engine": "Virtu-Harness-2",
                "rules": [
                    {"event": "PreToolUse", "action": "audit_arguments"},
                    {"event": "PostToolUse", "action": "verify_sandbox_output"},
                ],
            },
            indent=2,
        )
        + "\n",
    }
    return tree
