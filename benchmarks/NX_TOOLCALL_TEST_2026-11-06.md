# 13.63B Virtu 模型 × Windows-MCP「打开 NX」实测报告

**测量日期**：2026-11-06 21:38–22:10 (GMT+8)
**run_id**：`f34d0196fd051ea7`（有效腿）｜**basis**：measured
**证据目录**：`runs/nx_toolcall_20261106_2202/`
**被测问题**：Virtu 13.63B 会不会调用 Windows-MCP 操控电脑打开 NX？

---

## 0. 结论

**会，但要分清两层**：

| 层 | 结论 | 口径 |
|---|---|---|
| L1 模型侧 | 会。在宿主注入 Windows-MCP 工具 schema 后，5/5 条「打开 NX」指令均返回**结构化 `tool_calls`**，工具名 `App`、`mode=launch`、目标指向 NX；3/3 条非操作类问题不误触发。 | measured, n=8（主臂） |
| L2 执行侧 | 会。把模型 P1 的原样参数送进真实 Windows-MCP stdio server 的 `tools/call`，返回 `Siemens Nx 12.0 launched.`（`isError=false`），NX 进程由 0 变 1。 | measured, n=1 条完整链路 |

**模型本身不碰电脑**：它只产出 JSON 形式的工具调用请求；真正启动 NX 的是宿主（agent / MCP client）执行 `tools/call`。若宿主没把 Windows-MCP 的工具 schema 注入请求，模型没有可调用的工具面。

---

## 1. 测量口径

- **被测对象（按内容寻址，不按名字）**：`virtu-moe-14b:a2103c68`，Ollama digest `4007223565e96706…`，`parameter_size=13.6B`，Q4_K_M，`capabilities=[tools, thinking, completion]`。
- **服务点**：`http://127.0.0.1:11434/api/chat`，`stream=false`、`think=false`、`temperature=0.1`、`num_ctx=2048`、`num_predict=256`、`num_gpu=30`、`keep_alive=10m`。
- **工具面**：`tools.json`，10 个工具（1 个 `App` + 9 个干扰项：`Screenshot/Snapshot/Click/Type/Shortcut/PowerShell/Process/FileSystem/Wait`）。
  - 口径 **asserted → verified**：schema 按 `external/windows-mcp` v0.8.8 源码与 README 构造；第 4 节真实 `tools/list` 返回的 `App.inputSchema.properties` 与 `mode` 枚举逐项一致（见 `mcp_exec_evidence.json::mcp_app_schema`）。仍需注意注入的是 10 个工具，**不是** windows-mcp 全量工具面。
- **用例**：`cases/cases.jsonl`，5 正例（中/英、别名、开始菜单精确名）+ 3 负例（G81 解释、CAM 导航器问答、纯力学计算）。
- **判分器**：`grader.py`，8 类互斥判定；`counterfactual.json` 有 8 个植入样本（坏样本必红、好样本必绿），闸门通过。

---

## 2. L1 能力测量结果

| # | 臂 | 用例 | 模型产出的 `App` 参数 | 判定 |
|---|---|---|---|---|
| 1 | a2103c68 | P1 请打开 Siemens NX 12.0 | `{"mode":"launch","name":"Siemens NX 12.0"}` | HIT_STRICT |
| 2 | a2103c68 | P2 用 Windows-MCP 帮我启动 NX 12.0 | `{"mode":"launch","name":"NX 12.0"}` | HIT_STRICT |
| 3 | a2103c68 | P3 把 UG/NX 打开，我要建模 | `{"mode":"launch","name":"UG\NXC"}` | HIT_STRICT（参数名有杂质） |
| 4 | a2103c68 | P4 Open Siemens NX 12.0 on my computer | `{"mode":"launch","name":"Siemens NX 12.0"}` | HIT_STRICT |
| 5 | a2103c68 | P5 请启动开始菜单里的「中文版NX12.0」 | `{"mode":"launch","name":"中文版NX12.0"}` | HIT_STRICT（精确） |
| 6–8 | a2103c68 | N1/N2/N3 非操作类 | 无 `tool_calls`，纯文本回答 | NEG_OK ×3 |
| 9 | 01068725 | P1 | — | ERROR（见第 3 节） |
| 10 | latest | P1 | `{"mode":"launch","name":"Siemens NX 12.0"}` | HIT_STRICT |

**汇总**：`n_requests=10`、`n_pass=9`、`by_class={HIT_STRICT:6, NEG_OK:3, ERROR:1}`；主臂 8/8 通过。
**可归因性**：`identity.json`（Ollama 层哈希 + 用例/判分器 sha256）、`drift_log.jsonl`、`score.json`、`raw.jsonl`；腿末 `drift=[]`、`service_moves_during_leg=0`、反证闸门 `ok=true` ⇒ `valid=true`。

**失败模式没出现**：没有「用自然语言声称已打开 NX 却无 tool_calls」（幻觉执行），也没有选错工具（如用 `PowerShell` 或 `Click` 去开软件）。

---

## 3. 对照臂与一处被实测推翻的推断

- `virtu-moe-14b:01068725`（semantic 路由权重，digest `ea0a6ea9f89d6885…`）P1 报 `llama-server process no longer running: exit status 0xc0000409`，与 `benchmarks/VIRTU_13_63B_FEASIBILITY.json` 记录的 CUDA 初始化崩溃一致 ⇒ **该臂「未测」，不等于不会调用**。
- `virtu-moe-14b:latest`（digest `c63b157037343795…`）P1 也返回了合规 `App.launch` ⇒ 该臂 **会调用**（n=1，不足以推广到全部指令）。
- **修正**：测试途中曾依据 `latest` 的 Modelfile `TEMPLATE`（老式 chatml）推断它「不支持 tools」。`/api/show` 的运行时 template 三个标签哈希相同（`a55ee1b16601…`，均含 `{% if tools %}` 分支），且 latest 实测确实调用了工具 ⇒ **该推断作废，不能把源码字面量当测量结果**。证据：`model_templates.json`。
- 三个标签真正的差异在 Modelfile 参数：`a2103c68`/`01068725` 为 `num_ctx=4096, num_gpu=30`；`latest` 为 `num_ctx=8192, num_gpu=22` 且 system prompt 不同。

---

## 4. L2 端到端：MCP 执行与 NX 进程

链路：`raw.jsonl` 第一条 HIT_STRICT 的 `tool_calls[0].function.arguments`（P1，**原样、未改一个字**）→ 真实 Windows-MCP stdio server → `tools/call` → 进程/窗口前后对照。

| 步骤 | 实测结果 | 证据字段 |
|---|---|---|
| server 启动 | `.venv/Scripts/python.exe -m windows_mcp serve --transport stdio --tools App`；`initialize` 返回 `protocolVersion=2025-06-18` | `mcp_exec_evidence.json::steps[0]` |
| `tools/list` | 2 个工具 `ControlStatus` / `App`；真实 `App` schema 的 7 个参数与 4 个 mode 枚举，和 `tools.json` 逐项一致 | `::mcp_app_schema` |
| NX 基线 | `count=0` | `::nx_before` |
| `tools/call` 模型原样参数 `{"mode":"launch","name":"Siemens NX 12.0"}` | `{"content":[{"text":"Siemens Nx 12.0 launched.","type":"text"}],"isError":false}` | `::steps[2]` |
| 调用后进程 | `count=1`：`ugraf.exe -nx` pid 21748，`E:\...\NX12.2.9\NX\NXBIN\ugraf.exe -nx` | `::nx_after_model_args` |
| 存活复查 | running / 14 线程 / 260.4 MB；该 pid 拥有 10 个窗口，其中 1 个可见（`#32770`，标题 `v6.93_10.0_quick_cam`） | `nx_window_final.json` |

**判定**：闭环成立。模型发起的 `App.launch` 经 Windows-MCP 确实把 NX 进程拉起来了；fuzzy match 对带空格的 `Siemens NX 12.0` 命中了开始菜单项，所以第 5 节担心的「参数名不精确」**在这一例**没有导致失败。

**如实缺口**：按窗口标题关键词（NX/SIEMENS/UG）轮询 4 次、约 24 秒未见 NX 主界面；按 pid 归属枚举才找到那个可见对话框。因此结论只能到「**NX 进程与一个可见窗口已启动**」，不能写成「NX 建模主界面已完全就绪」。MCP server 收尾时被终止，NX 进程独立存活、未被回收；当前 NX 仍在本机运行，未主动关闭。

---

## 5. 参数质量：会调 ≠ 调得准

本机开始菜单实际名称是 `中文版NX12.0` / `英文版NX12.0`（目录 `Siemens NX12.0`），NX 启动器在
`E:\BaiduNetdiskDownload\NX 12.0.2.9\NX12.2.9waigua\NX12.2.9\SiemensNX\NX12.0.exe`。

模型给出的 `name` 有 4 种写法：`Siemens NX 12.0`（带空格）、`NX 12.0`、`UG\NXC`（不存在的名字）、`中文版NX12.0`（精确）。
Windows-MCP 的 `App.launch` 用 fuzzy match（`score_cutoff=70`）匹配开始菜单名，因此**参数不精确时能否命中，取决于匹配得分**，不能只凭「模型发出了 tool_call」就断言 NX 已被打开。

---

## 6. 环境阻断与处置（全部留痕）

- 11434 与 11435 有**两个 Ollama 实例**并行；期间外部 foreign-runner 反复在 11434 加载 8.2B dense 模型占 4–5 GB 显存，使 13.63B 加载回落 CPU 并报 `ggml_backend_cpu_buffer_type_alloc_buf` OOM。
- 处置方式只做运行时卸载（`POST /api/generate {"keep_alive":0}`），**未改动任何模型文件/标签**；随后请求即可成功。
- 两条作废腿已按熔断公理停止并封存：`runs/nx_toolcall_20261106_2146/`（CUDA OOM）、`runs/nx_toolcall_20261106_2156/voided/`（CPU OOM，`valid=false`）。有效腿采用「失败先卸载占用模型再重试」的收敛动作，10 个请求均一次成功（除 1 例崩溃）。
- Windows-MCP 依赖通过阿里云 PyPI 镜像补齐（PyPI 官方/清华镜像下载中断）；stdio server 需 `serve` 子命令，且须关掉 `ANONYMIZED_TELEMETRY`（境外 PostHog 联网会挂住启动）。

---

## 7. 未测与边界（禁止外推）

- 只在 `temperature=0.1 / num_ctx=2048 / think=false / 10 工具 schema` 这一组条件下测过；未测多轮对话、工具返回后的二次决策、不同 system prompt、更长上下文。
- 未测「宿主不注入工具 schema」时的行为（此时模型没有工具面）。
- 未测 `virtu-moe-14b:bf16`、`fast`、`semantic` 等其余 13.6B 标签。
- 01068725 臂因服务崩溃**未测**，不作为能力结论。
- L1 的工具 schema 起初是 asserted（源码构造），已用运行时 `tools/list` 核对一致（verified）；但注入的是 10 个工具，不是 windows-mcp 全量工具面，模型在更大工具面下的选工具能力**未测**。
- 端到端只跑通 **1 条**链路（P1 的 `Siemens NX 12.0`）。其余 4 种参数写法（`NX 12.0`、`UG\NXC`、`中文版NX12.0`、`Siemens NX 12.0` 英文指令）**未逐一执行**，不能断言都能打开 NX。
- 未测 NX 启动后的建模主界面是否完全就绪（窗口证据见第 4 节缺口）。
