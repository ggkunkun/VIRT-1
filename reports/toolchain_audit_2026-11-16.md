# Agent 工具链全面体检报告

**审计时间**：2026-11-16 21:18 → 22:10 (GMT+8)
**审计范围**：`D:\Virtu模型` 全仓（1050 个 Python 文件、495 个 scripts、52 个 skill、36 个 Agent facet、30 个 CADCAM 工具、61 个语料工具名、2 个 MCP server、6 套工业软件）
**审计人**：MCode / mavis（root session）
**证据目录**：`scratch/toolchain_audit_*.json`（10 份机读证据）
**测量口径**：`basis=measured`（全部结论均有可复跑命令 + 落盘证据）；未测项一律标注"未测"，无断言式结论。

---

## 一、总裁决

**工具链主体健康，未出现整体性损坏；但有 3 处真实缺陷需要修复，另有 4 项环境缺口会让测试变红。**

| 维度 | 结果 | 证据 |
| :--- | :--- | :--- |
| Agent 工具注册表 | ✅ 36/36 注册，无重名，运行时 registry 与源码一致 | `toolchain_audit_01_registry.py` |
| 核心模块导入 | ✅ 31/31 | 同上 |
| 全仓语法编译 | ✅ 1050/1050 零语法错误 | `toolchain_audit_09_compile.json` |
| 36 facet 逐个执行 | ⚠️ 26 直接返回 / 10 抛异常 → 归因后 **9 个契约破损** | `toolchain_audit_03_facets.json` + `_12` |
| 4 模式分派 | ✅ AUTONOMOUS / SWARM / MODALITY 成功；REACT 降级（模型 tag 缺失） | `toolchain_audit_07_modes.json` |
| CADCAM 工具面 | ✅ 30 工具，MCP stdio initialize/tools-list/tools-call 全通 | `toolchain_audit_06_mcp_cli.json` |
| 语料工具映射 | ✅ 61/61 全部可映射，无孤儿 | `toolchain_audit_02_cadcam.json` |
| 六大工业软件 | ⚠️ 5/6 ready（**NX 12.0 未安装**） | `cadcam_cli.py preflight` |
| 桌面输入闸门 | ✅ fail-closed，无 STOP、无租约，审计留痕正常 | `scripts/desktop_panic.py --status` |
| 外部 MCP server | ✅ windows-computer-use-mcp 握手成功（19.3s / v0.8.0） | `toolchain_audit_08_external_mcp.json` |
| 依赖一致性 | ✅ .venv `pip check` 无冲突；PY312 仅 2 条与本仓无关的第三方冲突 | `pip check` |
| 测试套件 | ⚠️ **2043 passed / 49 skipped / 10 failed**（19m31s） | 全量 pytest |

---

## 二、真实损坏（3 项，均已复现）

### D1 【严重】9 个 facet 的调用契约与注册契约冲突 —— REACT 真实路径下不可用

**位置**
- `virtu_omni/agent/super_agent.py:614-628`：`register_tool` / `call_tool` 把 facet 当**单参函数**（`tool_fn(params)`）
- `virtu_omni/agent/super_agent.py:2441` → `FacetToolAdapter.call`：`val = fn(payload)`，同样单参直调
- 冲突面：`facet_dispatch_modality`(5 参)、`facet_check_software_affordance`(3)、`facet_mcts_plan`(2)、`facet_rlvr_eval`(3)、`facet_brep_compile`(2)、`facet_quiet_star_heal`(2)、`facet_blueprint_ground`(1+list)、`facet_pinn_predict`(7)、`facet_funsearch_evolve`(1+int)

**机理**：适配器对外广播的 schema 是通用的 `payload: string`，模型最自然地发出 JSON 对象 → 对象被整体绑到**第一个**位置参数，其余参数静默取默认值。

**实测裁决**（`scratch/toolchain_audit_12_adapter_contract.json`）

| 工具 | 对象载荷 | 裸值载荷 | 裁决 |
| :--- | :--- | :--- | :--- |
| `rlvr_grpo_eval` | ✗ | ✗ | **任何形态都不行**（需要 prompt+candidates 两参） |
| `pinn_stress_surrogate` | ✗ | ✗ | **任何形态都不行**（需要 3 个必填参） |
| `dispatch_modality` | ✗ | 部分 | modality/target_software/action **被丢弃**（实测 `action: ""`） |
| `check_software_affordance` | ✗ | 部分 | software **被丢弃**（实测恒为 `SOLIDWORKS_2021`） |
| `mcts_plan_process_route` | ✗ | ✓ | 需裸数组载荷 |
| `brep_dsl_compile` | ✗ | ✓ | 需裸数组载荷 |
| `blueprint_spatial_ground` | ✗ | ✓ | 需裸数组载荷 |
| `quiet_star_self_heal` | ✗ | ✓ | 需裸字符串载荷 |
| `funsearch_evolve` | ✗ | ✓ | 需裸整数字载荷 |
| `prm_stepwise_audit` | 静默失败 | ✓ | 对象载荷返回 `{"error":"Invalid input format..."}`，**不抛异常但没干活** |

**反向验证**：这些 facet **本体是好的**——按各自声明的签名直接调用全部成功（`toolchain_audit_05_adjudication.json` 中 A 组全 OK）。**故障在调用契约层，不在业务实现层。**

**修复方向（二选一）**
1. `register_tool` 改签名收 `fn(params)` 统一形态，多参 facet 内部做 dict 解包（改动小，但要在 9 处 facet 里各写一次适配）
2. `FacetToolAdapter.call` 用 `inspect.signature(fn).bind(payload)` 做参数绑定/解包（改动集中、一处生效，**推荐**）

> 附带建议：为这 9 个工具在 `schemas()` 里广播各自的真实 inputSchema，避免模型只能猜。

---

### D2 【中】7 处 subprocess 捕获未指定 encoding —— 本机 cp936 下 UTF-8 中文输出解码崩溃

**根因**：本机 `locale.getpreferredencoding(False) = cp936`。`subprocess.run(..., text=True)` 未显式 `encoding=` 时按 cp936 解码，子进程吐 UTF-8 中文 → `UnicodeDecodeError` → **reader 线程直接死掉** → `proc.stdout` 变 `None`（不是空串）。

**受影响位置**
| 文件:行 | 模式 | 现状 |
| :--- | :--- | :--- |
| `bridges/autocad_bridge.py:111` | text=True | **会崩** |
| `virtu_omni/agent/adaptive_router.py:382` | text=True | **会崩** |
| `virtu_omni/internet/internet_hub.py:64` | text=True | **会崩** |
| `bridges/bridge_security.py:185` | bytes | 当前安全（建议统一） |
| `bridges/solidworks_bridge.py:165` | bytes | 当前安全（建议统一） |
| `virtu_omni/security/auditor.py:681-682` | bytes | 当前安全（建议统一） |

**实测**：MODALITY 模式 `mass_properties` 路径当场抛
`UnicodeDecodeError: 'gbk' codec can't decode byte 0xa8 in position 89`（reader 线程崩溃栈）。

**连带影响**：`tests/test_no_hardcoded_credentials.py` 的 2 个失败同源 —— `proc.stdout + proc.stderr` 报 `TypeError: can only concatenate str (not "NoneType") to str`。

**修复**：所有 subprocess 捕获统一 `encoding="utf-8", errors="replace"`。

---

### D3 【中】v3 DPO 修复语料的"负样本"已不成立 —— 训练对失去可证伪性

**位置**：`scripts/build_vericut96_cloud_datasets.py`（`rejected_sw` 定义，注释："no Z+ trailing confusion or broken table"）

**实测**：`sw_plane_notation_repair` 家族的 `rejected` 样本内容为
```
| 基准面 | 方向 | 说明 |
| Front Plane | Z+ 朝前 | 前视基准面 |
| Top Plane | Y+ 向上 | 上视基准面 |
| Right Plane | X+ 朝右 | 右视基准面 |
```
**语义完全正确**（Front=+Z / Top=+Y / Right=+X）。判分器 `evaluate_sw_coordinate_probe` 判 `passed=True` → `tests/test_coordinate_memory_comprehensive_fix.py:574` 失败。

**机理**：2026-11-15 判分器改写为"定义窗口"判定后，不再惩罚表格/尾随 `Z+` 记法；而 `rejected_sw` 的"错"**恰恰只在记法上** → 负样本变成了正样本。

**后果**：DPO 训练对变成 (chosen=正确, rejected=也正确) = 纯噪声对，模型会被训成"两种同样正确的表述选一种"。

**修复**：把 `rejected_sw` 改成**语义真正错误**（如 Front=+Y / Top=+Z 法向互换），而不是依赖记法差异。

---

## 三、环境缺口（非代码损坏，但会让测试变红，需人工处理）

### E1 NX 12.0 未安装 → 4 个测试红
`C:\Users\Administrator\Desktop\中文版NX12.0.lnk` 不存在，磁盘上也无 NX 程序目录（仅 `D:\_nxwork` 工作目录）。
`ready_count` 实测 = **5**（SW/AutoCAD/CIMCO/VERICUT/SSCNC 均 ready，SW 与 AutoCAD COM 已注册）。
→ `tests/test_toolchain_access_modes.py` 中 `test_01/02/03/05` 断言 `ready_count == 6` 全部失败。
**处理**：装 NX 12.0 并恢复快捷方式，或把断言改为按"已安装软件"动态计数。

### E2 本地模型 tag 不存在 → REACT deep 路径降级
Ollama `/api/tags` 实测 **17 个模型**，含 `virtu-ties-v1:q3_k_s`，**不含 `virtu-ties-v1:latest`**。
REACT 模式实测：`模型调用失败: HTTP 404: {"error":"model 'virtu-ties-v1:latest' not found"}` → deep_agent 不可用 → 降级硬编码流水线（降级本身是诚实且正确的，但真实链路没跑起来）。
**处理**：把配置里的 tag 指向实际存在的 `virtu-ties-v1:q3_k_s`，或补回 `:latest` 别名。

### E3 Windows 管道死锁 → 挂死整仓 pytest
`tests/test_cloud_instant_boot_scripts.py:91` 的 `subprocess.run(capture_output=True)` 调用 `start_cloud_train_now.sh --track vericut96-v2 --selftest`。
实测该脚本**本身 PASS**（rc=0，全部门禁 PASS），但**耗时 129.3s > pytest `--timeout=120`**。
父进程被 pytest-timeout 杀掉后，孙进程继承的 stdout 管道永不 EOF → `communicate()` 的 reader 线程无限 `join()` → **整个 pytest 进程被杀，日志停在 `++++ Timeout ++++`，没有 summary、没有 FAILED 列表**（正是 AGENTS.md §8.1 #7 记录的模式）。
**处理**：该用例把 timeout 提到 300s，并把该 subprocess 改为 `stdout=DEVNULL, stderr=DEVNULL`（调用方只取 returncode，不需要管道）。

### E4 内存压力 → torch 导入偶发失败
16 GB 物理内存，实测空闲仅 **2.1 GB**，页面文件 `D:\pagefile.sys` 16 GB（已用 3.8 GB）。
审计期间真实触发：`OSError: [WinError 1455] 页面文件太小，无法完成操作`（`torch/lib/cufft64_11.dll` 加载失败）。
**处理**：审计/训练期间降低并发，或扩页面文件。

### E5 判分器 reason 措辞漂移（pass/fail 仍正确）
`tests/test_vericut_e_cloud_gates.py`：`blue` 互换被判 `missing_meaning:blue`，测试期望 `swapped_meaning:blue`。
判定结果 `passed=False` **正确**，仅 reason 标签不同 → 影响归因精度，不影响门禁。
**处理**：与 §8.2「判分器改动必须配反证测试」一并复核。

### E6 安全审计 reason 措辞合并（防护生效，可诊断性下降）
`tests/test_security_audit.py` 2 个失败：相对路径穿越 `../../windows/system32/macro.vbs` 被报为
`"Field 'file_path' contains a path outside authorized roots."` 而非 `"path traversal"`。
**实测防护是生效的**（`passed=False`，违规被拦），嵌套递归也正常（能钻到 `payload.outputs[0].file_path`）。
问题在于**两类越界原因在审计轨迹里无法区分**：相对穿越 vs 绝对路径越界。
**处理**：把 traversal 检测恢复为独立 reason 串（`virtu_omni/security/auditor.py:239-252`）。

### E7 13 个 desktop_* 工具绕过中央 schema 闸门（次要）
`bridges/tool_calling_specs.py::get_tool_parameter_schemas()` 只覆盖 17 个 cadcam_* + 3 个 internal，缺 13 个 `desktop_*`。
`validate_tool_arguments` 对无 schema 的工具返回 `[]` → `schema_gate` 形同放行。
它们由 `bridges/agent_desktop_bridge.py` 独立派发且自带校验，功能不受影响，但**中央闸门对它们是空转的**。

---

## 四、未测 / 本次未覆盖

- 未做真实键鼠操作（`VIRTU_DESKTOP_INPUT=0` 全程 fail-closed，避免抢占操作者鼠标）
- 未启动 6 套工业软件本体做建模/仿真，只做了 preflight 级可用性 + COM 注册探测
- SWARM 模式跑的是真实 `SwarmCommander`（success=True, 9.0s），但未做多次重复取一致性
- 未验证 cloud_train_pack 的云端真实训练链路（只跑了 selftest 门禁）

---

## 五、修复优先级建议

| 序 | 项 | 代价 | 收益 |
| :--- | :--- | :--- | :--- |
| 1 | **D1** facet 参数绑定（改 `FacetToolAdapter.call` 一处） | 中 | 恢复 9 个工具在 REACT 下的可用性 |
| 2 | **D2** subprocess 统一 `encoding="utf-8"` | 极小 | 消除 cp936 解码崩溃 + 2 个测试红 |
| 3 | **D3** 重造 `rejected_sw` 为语义错误 | 小 | 恢复 DPO 训练对可证伪性 |
| 4 | **E3** 该用例 timeout 300s + DEVNULL | 极小 | 恢复全仓 pytest 可跑完 |
| 5 | **E1/E2** 装 NX / 改模型 tag | 需人工 | 恢复 4 个测试红 + REACT 真实链路 |
| 6 | **E6** 拆分 traversal reason 串 | 小 | 恢复安全审计可诊断性 + 2 个测试红 |

---

## 六、复跑命令

```powershell
cd D:\Virtu模型
# 1. 注册表 + 导入
.venv\Scripts\python.exe scratch\toolchain_audit_01_registry.py
# 2. CADCAM 层 + 语料映射 + preflight
.venv\Scripts\python.exe scratch\toolchain_audit_02_cadcam.py
# 3. 36 facet 冒烟
.venv\Scripts\python.exe scratch\toolchain_audit_03_facets.py
# 4. 失败归因裁决
.venv\Scripts\python.exe scratch\toolchain_audit_05_adjudication.py
# 5. MCP stdio + CLI
.venv\Scripts\python.exe scratch\toolchain_audit_06_mcp_cli.py
# 6. 4 模式分派
.venv\Scripts\python.exe scratch\toolchain_audit_07_modes.py
# 7. 外部 MCP 握手
.venv\Scripts\python.exe scratch\toolchain_audit_08_external_mcp.py
# 8. 调用契约终裁
.venv\Scripts\python.exe scratch\toolchain_audit_12_adapter_contract.py
# 全量测试（排除已知挂死文件）
& 'C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe' -m pytest tests/ -q --timeout=120 -p no:cacheprovider --ignore=tests/test_cloud_instant_boot_scripts.py
```
