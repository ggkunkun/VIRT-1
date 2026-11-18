# Agent 工具链全面修复报告（2026-11-17）

**修复时间**：2026-11-17 13:5x → 15:xx (GMT+8)
**触发**：用户「全面修复工具链」。在 2026-11-16 体检/修复（`reports/toolchain_audit_2026-11-16.md`、`reports/toolchain_repair_2026-11-16.md`）基础上复测全链路，修复残留项 E7 与本轮新发现缺陷，并修正审计脚本自身的测量缺陷。
**口径**：`basis=measured`，每项修复均有可复跑命令与落盘证据；未测项一律标注「未测/待办」，无断言式结论。
**解释器**：审计/定向测试用 `.venv/Scripts/python.exe`；全量回归用 `C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe`（AGENTS.md §8.1）。

---

## 一、总裁决

工具链主体健康。本轮修复 **2 处真实代码缺陷**（E7 残留 + 新发现 D5）与 **4 处审计脚本测量缺陷**；全量回归首跑 2094 passed / 2 failed，2 个失败经查为桥接文件并发编辑瞬态（非当前代码缺陷），定向复跑 23 passed 确认两条契约同时满足，**干净复跑 2096 passed / 0 failed**。

| 维度 | 结果 | 证据 |
| :--- | :--- | :--- |
| Agent 工具注册表 | ✅ 36/36，无重名，源码↔运行时一致 | `toolchain_audit_01_registry.py` |
| 核心模块导入 | ✅ 31/31 | 同上 |
| 全仓语法编译 | ✅ 1062/1062 零错误（修复审计脚本假红后） | `toolchain_audit_09_compile.json` |
| 36 facet 逐个执行 | ✅ 36/36 返回（修复审计载荷 + D5 后） | `toolchain_audit_03_facets.json` |
| facet 调用契约 | ✅ 对象载荷 0/10 破损 | `toolchain_audit_12_adapter_contract.json` |
| 4 模式分派 | ✅ AUTONOMOUS/MODALITY/SWARM 成功；REACT 在 3s 钳制下诚实降级 | `toolchain_audit_07_modes.json` |
| CADCAM 工具面 | ✅ 30 工具，**missing schema = []**（E7 修复后） | `toolchain_audit_02_cadcam.json` |
| 语料工具映射 | ✅ 61/61 全映射，无孤儿 | 同上 |
| 六大工业软件 | ✅ preflight 6/6（NX 动态发现仍生效） | `scratch/check_preflight.py` |
| 中央 schema 闸门 | ✅ 33 工具受管辖（含 13 desktop_*），坏样本必红 | `tests/test_desktop_schema_gate.py` 5/5 |
| 外部 MCP server | ✅ 三 server 全握手（20/21/30 工具） | `toolchain_audit_08_external_mcp.json` |
| 桌面输入闸门 | ✅ fail-closed，无 STOP、无租约，审计正常拒绝 | `scripts/desktop_panic.py --status` |
| 模型服务 | ✅ Ollama 17 模型，含 `virtu-ties-v1:latest` | `/api/tags` |
| 全量回归 | ✅ **2096 passed / 49 skipped / 0 failed**（干净复跑 13:08） | 见 §六 |

---

## 二、真实代码缺陷（2 项，已修 + 反证测试）

### E7【残留】13 个 desktop_* 工具绕过中央 schema 闸门

**根因**：`bridges/tool_calling_specs.py::get_tool_parameter_schemas()` 旧实现只取
`CADCAM_TOOLS_DEFINITION + INTERNAL_TOOL_DEFINITIONS`，而 13 个 `desktop_*` 工具定义来自
`get_agent_desktop_tool_definitions()`（仅在 `get_cadcam_tool_definitions()` 里并入）。
于是 desktop_* 无 schema ⇒ `validate_tool_arguments` 返回 `[]` ⇒ `schema_gate`（1550 行，对所有工具生效）空转放行。

**修复**：`get_tool_parameter_schemas()` 改从 `get_cadcam_tool_definitions()`（已含 desktop）+ INTERNAL 构建缓存，单一事实源。
schema 总数 **20 → 33**，13 个 desktop_* 全部受管辖。

**反证**（`tests/test_desktop_schema_gate.py`，5/5）：
- 13 个 desktop_* 必须全部有中央 schema（缺即红，防回归空转）；
- `desktop_click {}` ⇒ `TOOL_SCHEMA_VIOLATION`（required_missing target）；
- `desktop_type {"text": 123}` ⇒ type_mismatch；
- 合法调用（`desktop_press {"combo":"ctrl+s"}` / `desktop_status {}`）放行；
- 反证：monkeypatch 掉 schema 后闸门对坏样本也放行（证明拦截确实依赖 schema 存在）。

### D5【新发现】工程 facet 收到字符串载荷崩溃 —— 真实 REACT 深度路径 6 步里 4 步 FACET_ERROR

**复现**（`scratch/probe_react_real.py`，解除 3s 钳制、真实模型预算）：
深度引擎按广播 schema 发 `{"payload": "<自然语言规格>"}`，`FacetToolAdapter._extract_payload`
解包成**字符串**传给单参 dict facet，delegate.run() 对字符串调 `.get()`：

| 工具 | 修复前 |
| :--- | :--- |
| `generate_parametric_cad` | `AttributeError: 'str' object has no attribute 'get'` |
| `generate_cam_toolpath` | 同上 |
| `audit_sandbox_simulation` | 同上 |
| `desktop_gui` | `ValueError: dictionary update sequence element #0 has length 1; 2 is required` |

**机理**：这些 facet 是单参（`context: Dict`），D1 修复刻意保持单参 schema 为 `payload: string`，
模型最自然发字符串；硬编码流水线传 dict 所以不崩，真实模型驱动路径传字符串就崩。

**修复**（`virtu_omni/agent/super_agent.py`，facet 归一化层，不动 schema/绑定层）：
- 新增 `_spec_context()`：dict 载荷原样透传（硬编码流水线契约不变）；字符串载荷先经
  `ChiefArchitectAgent` 解析成规格，再组装 `{user_prompt, architecture}`。
- `facet_generate_cad / facet_generate_standards / facet_generate_cam` 走 `_spec_context()`。
- `facet_audit_sandbox`：字符串载荷先派生真实建模/加工产物再审计（不空审假绿）。
- `facet_desktop_gui`：非对象载荷返回结构化错误（`input_sent=False`），不再崩溃。

**证据**：
- 直接探针：四个工程 facet 字符串载荷全部 `COMPLETED`，`audit_sandbox` 真实审计 `passed=True`，dict 路径不回归。
- `tests/test_facet_string_payload.py` **8/8**（含反证：delegate 本体仍要求 dict，证明修复在归一化层而非放松 delegate）。
- D1 契约 + 实算 agent + AST 抽取敏感测试（`test_facet_call_contract` / `test_agent_team_real_agents` /
  `test_product_first_closed_loop` / `test_swarm_entry`）合计 **35 passed**，单参 schema 不变量与抽取法均未破坏。

**诚实边界**：REACT 深度引擎的**规划 JSON 合法性取决于模型输出**（`virtu-ties-v1:latest` 为小 q3 模型，非确定性：
一次吐合法 6 步规划、一次吐 broken JSON）。facet 崩溃已根治；规划无效时引擎诚实降级硬编码流水线（降级路径现已可跑通）。
模型规划能力本身不在工具链修复范围。

---

## 三、审计脚本测量缺陷（4 项，按 §8.2 区分测量缺陷 vs 代码缺陷）

这些是**审计工具自身**的缺陷，会制造假红/假绿，不是产品代码损坏。

### M1｜09 编译审计固定临时 pyc 路径撞 Windows 锁 → 假报编译错误
`py_compile.compile(cfile=.venv/Scripts/_audit_pyc.tmp)` 固定路径，`os.replace` 间歇撞
Defender/索引器锁 ⇒ `PermissionError [WinError 5]`，单独跑也复现（每次随机 3-4 个文件）。
**修复**：语法审计改用内建 `compile(source, ...)`，零盘写、无竞态。复跑 **1062/1062 零错误**，并清理 venv 里的 `_audit_pyc.tmp` 残留。

### M2｜03 facet 载荷用了过期键名 → 假报 facet 异常
`primitive_id/primitive_type/parameters`（应为 `elem_id/elem_type/params`）、
`operation_id/operation_type/params`（应为 `op_id/op_name/op_type/tool_id`）、
`EQUAL_RADIUS`（不在 ConstraintType 枚举，应为 `RADIUS`）。facet 本体好的，是审计载荷错。
**修复**：改规范键名（与 `tool_binding.FACET_ARRAY_ITEM_FIELDS` 广播一致）。复跑 **36/36 返回**。

### M3｜07 MODALITY 探针动作非法 → 假报模式失败
`action="list_windows"` 被路由到 `cadcam_solidworks_model`，其 action enum 不含 list_windows ⇒
schema 闸门**正确拦截**（TOOL_SCHEMA_VIOLATION）。这是闸门履职，不是模式损坏。
**修复**：探针改 `action="preflight"`（路由到 `cadcam_preflight`，离线可成功）。复跑 MODALITY **success=True**。

### M4｜08 windows-mcp 启动命令错 + MCP 握手不完整 → 假报 server 损坏
- 启动模块错：`-m windows_mcp.main`（无 main.py）→ 按 manifest 改 `-m windows_mcp serve`。
- 握手缺 `notifications/initialized`，且两类 server 行为不同：windows-mcp 是流式（stdin 开着才答 tools/list），
  windows-computer-use-mcp 是批式（等 stdin EOF 才处理）。旧 `subprocess.run(input=...)` 立即关 stdin ⇒ 流式 server 只答 initialize。
**修复**：补 initialized 通知 + 双流式握手（先给流式 20s 应答窗口，无应答再关 stdin 让批式处理退出）。
复跑三 server 全通：**windows-computer-use-mcp 20 / windows-mcp 21 / repo cadcam 30**。

---

## 四、复核健康项（无需改动）

- 注册表 36/36 无重名、导入 31/31（`toolchain_audit_01_registry.py`）。
- D1 调用契约对象载荷 0/10 破损（`toolchain_audit_12_adapter_contract.json`）。
- D2 subprocess 编码：runtime 仅剩 1 处且已有显式 decode（`scratch/scan_subprocess_encoding.py`）。
- preflight 6/6，NX 动态发现仍生效（`scratch/check_preflight.py`）。
- Ollama 17 模型含 `virtu-ties-v1:latest`（E2 别名修复仍生效）。
- 桌面输入闸门 fail-closed、无 STOP、无租约、审计正常拒绝（`scripts/desktop_panic.py --status`）。
- CADCAM 30 工具、语料 61/61 映射、MCP stdio/CLI 全通（`toolchain_audit_02/06`）。

---

## 五、桥接 reasoning 隐私契约（首跑 2 失败的澄清）

全量回归首跑 2 个失败均在 `tests/test_bridge_protocol.py`，断言 `reasoning_content` **不得**泄露：
- `test_chat_passes_request_parameters_and_does_not_fabricate_usage`
- `test_legacy_streaming_helper_does_not_serialize_reasoning`

**查清**：当前桥接代码已是正确终态，同时满足两条契约——
- 隐私（`test_bridge_protocol`）：生产非流式路径 `scripts/workbuddy_virtu_bridge.py:1907`
  调 `_handle_json_response(response_text)` **不传 reasoning_text**，私有思维留在服务端；
  流式助手 `_handle_streaming_response`（2359 行）有 `expose_reasoning=False` 门控。
- 深度思维（`test_deep_thinking`）：直接调助手显式传 `reasoning_text` / `expose_reasoning=True` 时仍可暴露（opt-in）。

**定向复跑** `test_bridge_protocol.py + test_deep_thinking.py`：**23 passed / 12 subtests**。
首跑失败是 14:47 运行期间桥接文件被**并发编辑**的瞬态（AGENTS.md §8.3 共享可变状态；该文件在 git 工作区为 modified），
pytest 导入到中间版本。**非当前代码缺陷**，本轮未改动该文件，仅核实。

---

## 六、全量回归

- **首跑**：`2 failed, 2094 passed, 49 skipped, 1 warning, 55 subtests passed in 887.93s (14:47)`。
  2 失败即 §五 的桥接瞬态，定向复跑已绿。
- **干净复跑**：**`2096 passed, 49 skipped, 1 warning, 55 subtests passed in 788.95s (13:08)`，0 failed**。
  首跑 2094 passed + 2 failed = 2096，与复跑 2096 passed 完全对账——2 个桥接失败转绿，证实 §五 的瞬态归因。
  复跑命令：`& 'C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe' -m pytest tests/ -q --timeout=300 -p no:cacheprovider`。

---

## 七、待办 / 诚实边界（非工具链损坏）

- **E4 内存压力**：16 GB 物理内存，审计/训练期间空闲偏低，torch 导入偶发 `WinError 1455`。环境项，降并发或扩页面文件。
- **部署凭证时效**：E5 判分器升 v5 后，`checkpoints/deployment_receipt_*.json` 旧判分器版本（`d119663e`/`9ce6f480`）成「旧法判决」，
  需按 `--verify-only` 重出。属**模型验收**（GPU/Ollama 长跑），非工具链修复范围，延续 2026-11-16 的范围决定，本轮未自动重跑。
- **REACT 规划质量**：深度引擎规划 JSON 合法性取决于小模型输出（见 §二 D5 诚实边界）。

---

## 八、本轮改动文件清单

| 文件 | 改动 |
| :--- | :--- |
| `bridges/tool_calling_specs.py` | E7：`get_tool_parameter_schemas()` 纳入 desktop 工具定义 |
| `virtu_omni/agent/super_agent.py` | D5：`_spec_context()` + 4 工程 facet 字符串归一化 + desktop_gui 非对象守卫 |
| `tests/test_desktop_schema_gate.py` | **新增**：E7 反证 5 条 |
| `tests/test_facet_string_payload.py` | **新增**：D5 反证 8 条 |
| `scratch/toolchain_audit_09_compile.py` | M1：内建 compile() 替代固定 cfile |
| `scratch/toolchain_audit_03_facets.py` | M2：规范载荷键名 |
| `scratch/toolchain_audit_07_modes.py` | M3：MODALITY 探针改 preflight |
| `scratch/toolchain_audit_08_external_mcp.py` | M4：windows-mcp 启动命令 + 双流式 MCP 握手 |
| `scratch/probe_react_real.py` | **新增**：真实 REACT 深度路径取证探针 |

> 注：`scripts/workbuddy_virtu_bridge.py` 本轮**未改动**（§五 仅核实其正确终态）。

---

## 九、复跑命令

```powershell
cd D:\Virtu模型
# 审计套件（机读证据落 scratch/）
.venv\Scripts\python.exe scratch\toolchain_audit_01_registry.py
.venv\Scripts\python.exe scratch\toolchain_audit_02_cadcam.py
.venv\Scripts\python.exe scratch\toolchain_audit_03_facets.py
.venv\Scripts\python.exe scratch\toolchain_audit_06_mcp_cli.py
.venv\Scripts\python.exe scratch\toolchain_audit_07_modes.py
.venv\Scripts\python.exe scratch\toolchain_audit_08_external_mcp.py
.venv\Scripts\python.exe scratch\toolchain_audit_09_compile.py
.venv\Scripts\python.exe scratch\toolchain_audit_12_adapter_contract.py
# 真实 REACT 深度路径取证
.venv\Scripts\python.exe scratch\probe_react_real.py
# 本轮反证测试
.venv\Scripts\python.exe -m pytest tests/test_desktop_schema_gate.py tests/test_facet_string_payload.py -q
# 桥接两条契约
.venv\Scripts\python.exe -m pytest tests/test_bridge_protocol.py tests/test_deep_thinking.py -q
# 全量回归
& 'C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe' -m pytest tests/ -q --timeout=300 -p no:cacheprovider
```