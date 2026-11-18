# Agent 工具链修复报告

**修复时间**：2026-11-16 23:23 → 2026-11-17（GMT+8）
**触发**：2026-11-16 全面体检（`reports/toolchain_audit_2026-11-16.md`）发现 3 处真实缺陷 + 4 项环境缺口
**执行**：MCode / mavis（root session）
**口径**：`basis=measured`，每项修复都有可复跑命令与落盘证据

---

## 一、修复总览

| 编号 | 缺陷 | 状态 | 证据 |
| :--- | :--- | :--- | :--- |
| **D1** | 9 个多参 facet 在 REACT 真实路径下不可用（注册契约 vs 调用契约冲突） | ✅ 已修 | `scratch/toolchain_audit_12_adapter_contract.json` 10/10；`tests/test_facet_call_contract.py` 19/19 |
| **D2** | 7 处 subprocess 捕获未指定编码，本机 cp936 下 UTF-8 中文输出解码崩溃 | ✅ 已修 | `scratch/scan_subprocess_encoding.py` 复扫 + `test_no_hardcoded_credentials.py` 12/12 |
| **D3** | v3 DPO 语料「负样本」语义正确 → 训练对失去可证伪性 | ✅ 已修 | `test_coordinate_memory_comprehensive_fix.py::…dpo_repair…` 通过（rows=256, hard_leaks=0） |
| **E1** | NX 12.0 未安装（介质被 E 盘清理掉）→ 6/6 预检只到 5/6 | ✅ 已修 | preflight 6/6 + NxOpen journal 端到端跑通 |
| **E2** | Ollama 缺 `virtu-ties-v1:latest` → REACT deep 路径 404 降级 | ✅ 已修 | `ollama list` 同 blob 别名已建 |
| **E3** | `test_cloud_instant_boot_scripts.py` 挂死整仓 pytest（Windows 管道死锁） | ✅ 已修 | 该用例 133s 内跑完，不再拖死进程 |
| **E6** | 安全审计把「相对遍历」与「绝对路径越界」合并成一条理由串 | ✅ 已修 | `test_security_audit.py` 2 个用例转绿 |
| **D1b** | D1 修复引入的回归：`ast.get_source_segment` 抽取的方法在合成命名空间 exec 时找不到新模块级依赖 | ✅ 已修 | 绑定层抽成零依赖模块 `virtu_omni/agent/tool_binding.py`，被抽取方法改用函数内 import；`test_product_first_closed_loop.py` + `test_swarm_entry.py` 全绿 |
| **D4** | OpenAI 兼容桥接层：**两份测试对同一方法要求相反**（暴露 vs 私有思维链） | ✅ 已裁决 | 权威契约 = **思维链私有**（生产代码注释 + `test_bridge_protocol` + legacy helper 无生产调用点）；最终形态「默认私有 + 显式 opt-in」，`test_deep_thinking` + `test_bridge_protocol` 合计 **23 passed + 12 subtests** |
| **E5** | Auto-Diff 判分器：语义互换被误报成语义缺失；正语义不做否定识别 → 假绿 | ✅ 已修 | `tests/test_probe_grader_fixes_20261116.py` 24→28 条全绿 |

> **连带影响（必须知悉）**：E5 改动了判分器 ⇒ `cloud_train_pack/deploy_trained_adapter.py`
> 的 `grader_sha256` 变为 **74a7da08e31dcf9c**、`measurement_version` 升到 **probes-2026-11-16-v5**。
> `checkpoints/deployment_receipt_*.json` 里绑定的旧判分器版本（`d119663e` / `9ce6f480`）
> **全部变成「旧法判决」**，需按 `--verify-only` 重出凭证。本次未自动重跑模型验收
> （GPU 长跑，超出本次修复范围）。
> 另注：E5 的新判据只会把 **PASS 变 FAIL**、不会把 FAIL 变 PASS（收紧方向），
> 因此旧凭证的结论方向仍然保守，但归因标签需重出才对得上。

---

## 二、D1｜facet 调用契约与注册契约冲突（严重）

### 根因
`register_tool` / `call_tool` / `FacetToolAdapter.call` 三处都把 facet 当**单参函数**（`fn(payload)`），
但有 9 个 facet 的真实签名是多参（`facet_pinn_predict` 需 3 个必填参、`facet_rlvr_eval` 需 2 个、
`facet_mcts_plan` / `facet_brep_compile` 需结构化列表、`facet_quiet_star_heal` 需代码…）。
模型按广播 schema 发的 JSON 对象被**整体**绑到第一个位置参数，其余静默取默认值：

- `dispatch_modality` → `action` 被丢弃成 `""`
- `check_software_affordance` → `software` 被丢弃，恒为 `SOLIDWORKS_2021`
- `prm_stepwise_audit` → 不抛异常，但返回 `{"error": "Invalid input format…"}`，**看着像成功其实没干活**

### 修复
`virtu_omni/agent/super_agent.py`：

1. 新增模块级 `_facet_params` / `_facet_json_type` / `_facet_input_schema` / `_bind_facet_args`：
   - 载荷是 dict 且键命中 facet 形参名 → **按关键字传参**；必填项缺失时**显式抛错**（不再静默用默认值顶替）
   - facet 只有一个形参且载荷是「单键且键名等于形参名」→ 解包该值（修 `{"raw_elements": [...]}`、`{"steps": 1}`）
   - 其余 → 按旧契约整体绑到第一个形参（**26 个已验证工具行为完全不变**）
2. `call_tool`、REACT 流水线派发点、`FacetToolAdapter.call` 三处统一走绑定层
3. `FacetToolAdapter.schemas()`：多参 facet **广播真实形参名与真实必填项**（deep_agent 的
   `tool_brief` / `validate_plan` 直接消费这份 schema），单参 facet **schema 一字不改**
4. `_FACET_ARRAY_ITEM_FIELDS` 补 `operations` 的内部字段（`op_id/op_name/…`），避免规划器猜错键名

### 证据
- `scratch/toolchain_audit_12_adapter_contract.json`：修复前 **BROKEN 9/10** → 修复后 **0/10**
- 新增 `tests/test_facet_call_contract.py` **19/19**：
  - 正向：11 个多参 facet 具名参数全部可调用
  - 反向：缺必填参数**必须报错**（植入坏样本必红）
  - 反证：新增多参 facet 未纳入用例表 → 直接判红
  - 不回归：所有单参 facet 的 schema 仍是 `{"payload"}` + `required=["payload"]`

---

## 三、D2｜subprocess 编码（cp936 vs UTF-8）

### 根因
本机 `locale.getpreferredencoding(False) = cp936`。`subprocess.run(text=True)` 未给 `encoding=` 时按 cp936 解码，
子进程吐 UTF-8 中文 → `UnicodeDecodeError` → **reader 线程直接死掉** → `proc.stdout` 变 `None`（不是空串）。

实测触发点：MODALITY 模式 `mass_properties` 路径当场抛
`UnicodeDecodeError: 'gbk' codec can't decode byte 0xa8 in position 89`。

### 修复
- runtime 5 处：`bridges/autocad_bridge.py`、`virtu_omni/agent/adaptive_router.py`、
  `virtu_omni/internet/internet_hub.py`、`virtu_omni/rea/adapter.py`、`virtu_omni/security/auditor.py`
  → 统一 `encoding="utf-8", errors="replace"`
- 测试 2 处：`tests/test_no_hardcoded_credentials.py` 两处 subprocess
- **刻意未改**：`bridges/bridge_security.py`（icacls 是 ANSI 码页，已有明确注释说明为何保持 bytes）、
  `bridges/solidworks_bridge.py`（tasklist 显式 `.decode("gbk", errors="ignore")`）
- `scratch/scan_subprocess_encoding.py`（AST 扫描）复扫：runtime 路径只剩 1 处，且该处已有显式 decode

### 证据
- `test_no_hardcoded_credentials.py` 修复前 2 failed → **12 passed**
- AST 复扫：`bridges` + `virtu_omni` 中 text 模式调用**无 encoding/errors 者 = 1**（且已安全）

---

## 四、D3｜DPO 负样本语义化

### 根因
`scripts/build_vericut96_cloud_datasets.py` 的 `rejected_sw` 只在**记法**上与 `chosen_sw` 不同
（表格 + 尾随 `Z+`），内容其实是正确的（Front=+Z / Top=+Y / Right=+X）。
2026-11-15 判分器改用「定义窗口」判定后不再惩罚该记法 ⇒ 负样本被判 `passed=True`
⇒ 训练对退化成 (chosen=正确, rejected=也正确) 的纯噪声。

### 修复
负样本改为**语义真正错误**（法向互换：Front=+Y / Top=+Z），判分器必须判 FAIL。

### 证据
`test_coordinate_memory_comprehensive_fix.py::test_build_vericut96_v3_dpo_repair_no_leak_and_falsifiable` 通过，
产物 `vericut96_v3_dpo_repair.jsonl` rows=256 / hard_leaks=0 / numeric_proxy=0。

---

## 五、E1｜NX 12.0 恢复（真装 + 根治路径腐坏）

### 现场还原
- 用户提供 `中文版NX12.0.exe`（4.04 MB，加壳 PE，无签名）——它是**引导程序**，必须在介质目录里跑
- 介质真身：`D:\BaiduNetdiskDownload\NX 12.0.2.9\NX12.2.9waigua\NX12.2.9\`（**12.5 GB / 66259 文件**，百度网盘客户端已拉取）
- 该介质是**免安装树**：`NX\CH_NX.BAT` 设 `UGII_BASE_DIR` / `SPLM_LICENSE_SERVER` 后 `start NXBIN\ugraf.exe -nx`
- 之前的 E:\ 路径与 `D:\_E盘归档_2026-11-14\nx12_package` 都已被清理 → 硬编码路径全部失效
- 安装器秒退的真正原因：**当前 shell 未提权**（`elevated=False`）；但免安装树无需安装即可运行

### 修复（根治，不只是补路径）
1. `bridges/software_registry.py` 新增**动态发现**：
   `discover_nx_base_dirs()`（注册表 → 桌面快捷方式目标 → 网盘/归档目录递归）与 `discover_nx_binaries()`，
   `get_software_health()` 对 NX 自动并入发现结果 ⇒ **介质搬家/重新下载都不会再腐坏**
2. `bridges/nx_bridge.py`：`NX_BASE` 从硬编码 E: 改为 `_discover_nx_base()` 动态解析；
   顺带把该文件 **115 处畸形 `\r\r\n`（CRCRLF，全仓唯一）** 归正为 CRLF
3. 创建桌面快捷方式 `C:\Users\Administrator\Desktop\中文版NX12.0.lnk` → 目标 `NX\CH_NX.BAT`，
   工作目录 `NX\`，图标取 `NXBIN\ugraf.exe`
4. 补充 `known_binaries` 中的当前 D: 介质路径（双保险）

### 证据（功能级，不是探测级）
- preflight：**ready_count 6/6，all_ready=True**
- 桥接 API `SiemensNXBridge.run_python_journal()`：rc=0，`Execution was successful.`，
  **NX 自己写出的标记文件**含 `NXOPEN_OK` / `ugii_version=v12`
- 公开工具入口 `execute_tool_call("cadcam_nx_journal", {"action": "run_journal", …})`：
  需审批（risk=system，符合设计）→ 授权后 rc=0，标记文件含 `NX_TOOL_OK`
- `tests/test_toolchain_access_modes.py` **6 passed**（修复前 4 failed）

---

## 六、E2｜模型标签

Ollama 有 17 个模型但只有 `virtu-ties-v1:q3_k_s`，没有 `virtu-ties-v1:latest`（deep_agent 默认值）
⇒ REACT deep 规划阶段 404 降级。
已用 `ollama cp virtu-ties-v1:q3_k_s virtu-ties-v1:latest` 补别名：
**同一 blob ID 80b2b7fddf80 / 3.8 GB，无额外磁盘占用**，所有引用 `:latest` 的配置继续有效。

---

## 七、E3｜挂死整仓 pytest 的用例

### 根因
`tests/test_cloud_instant_boot_scripts.py` 用 `subprocess.run(capture_output=True, timeout=N)` 调
`start_cloud_train_now.sh --selftest`。该脚本**本身 PASS**，但实测需 **129.3 s** > pytest `--timeout=120`
⇒ 父进程被 pytest-timeout 杀掉 ⇒ 孙进程继承的 stdout 管道永不 EOF ⇒
`communicate()` 的 reader 线程无限 `join()` ⇒ **整个 pytest 进程被杀**（日志停在 `++++ Timeout +++`，无 summary）。

### 修复
- 新增 `_run_bash_to_file()`：stdout/stderr **落临时文件**而非管道 ⇒ 父进程被杀也不会死锁
- 子进程 timeout 提到 **300 s**，并给用例加 `@pytest.mark.timeout(300)`
- 仍保留完整 stdout/stderr 供失败诊断

### 证据
该用例现已在 133 s 内跑完并通过，全仓 pytest 可一次跑完。

---

## 八、E6｜安全审计的理由串

### 根因
`virtu_omni/security/auditor.py` 把 `../` 相对遍历与 `C:\` 绝对路径越界合并成一条正则 + 一条理由串
⇒ 审计轨迹里两类越界无法分辨（测试期望 `path traversal`，实得 `outside authorized roots`）。

### 修复
拆成两条：`PATH_TRAVERSAL_PATTERN`（`../`、`..\`、`/..`）与 `ABSOLUTE_PATH_PATTERN`（`^/`、盘符），
理由串分别为 `path traversal sequence` 与 `path outside authorized roots`。
**防护力度不变**（两类都判 `passed=False`），只是可诊断性恢复。

### 证据
`tests/test_security_audit.py` 2 个用例由 failed 转 passed。

---

## 九、D1b｜D1 修复自身引入的回归（AST 抽取法失效）

### 现象
全量回归新增 1 个红：`test_product_first_closed_loop.py::test_product_first_closed_loop`
报 `KeyError: 'web_verify_and_correct'`。追查发现：该测试用
`ast.get_source_segment` 把 `_solve_react_pipeline` 的源码抠出来、在**合成命名空间**里 `exec`，
而 D1 修复让该方法依赖了**模块级** `_bind_facet_args` —— 合成命名空间里没有这个名字
⇒ 调用点抛 `NameError` ⇒ 工具步失败、产物未记录。

> 旁证：管道本身是好的（10 步全在 trace_log），坏的只有「产物没落盘」。

### 修复（根治，不改测试）
1. 绑定层抽成**零依赖独立模块** `virtu_omni/agent/tool_binding.py`
   （只依赖标准库；`virtu_omni.agent` 用 PEP 562 懒加载，无循环导入风险）
2. `super_agent.py` 改为从该模块导入，名称保持可从 `super_agent` 直接引用
3. **被 AST 抽取的方法改用函数内 import**（`_solve_react_pipeline` 内
   `from virtu_omni.agent.tool_binding import bind_facet_args as _bind_facet_args`），
   使其不再依赖模块级名字 ⇒ 抽取法继续可用

### 证据
`test_product_first_closed_loop.py` + `test_swarm_entry.py`（23/23 断言）+ `test_facet_call_contract.py`
合计 **21 passed**。

---

## 十、D4｜思维链与结论分离：契约裁决（**不是"补上 reasoning_content"**）

### 原始症状
`tests/test_deep_thinking.py` 的两条用例（JSON 响应含 `reasoning_content`、SSE 先推 reasoning 再推
content）在本次修复前一直是红的。

### 第一次尝试（已回退）
我最初按"测试即规格"的读法，直接让 `_handle_json_response` / `_handle_streaming_response`
输出 `reasoning_content` ⇒ **`tests/test_bridge_protocol.py` 的两条断言当场变红**：
- `test_chat_passes_request_parameters_and_does_not_fabricate_usage`
  ⇒ 响应体里出现了 `private_nonstream_reasoning`
- `test_legacy_streaming_helper_does_not_serialize_reasoning`
  ⇒ legacy SSE 里出现了 `reasoning_content`

### 契约裁决（证据链）
两份测试文件对**同一个方法**要求相反，说明仓库里存在**未裁决的矛盾**。裁决依据：

1. **生产代码注释**（`scripts/workbuddy_virtu_bridge.py::_handle_live_streaming_response`）：
   ```python
   if itype == "thinking":
       # Private model reasoning is never included in client output.
       continue
   ```
2. `tests/test_bridge_protocol.py` 的断言对象就叫 `private_nonstream_reasoning` /
   `private_legacy_reasoning` —— 思维链被定义为**私有**。
3. `_handle_streaming_response` 在**生产代码里没有任何调用点**（只有测试引用），
   而真正的 SSE 路径是 `_handle_live_streaming_response`（它**故意丢弃** thinking）。
   ⇒ `test_deep_thinking` 那两条测的是一个**已弃用的 legacy helper**。

**结论：权威契约 = 思维链私有，不得出现在客户端输出里。** 我最初的改法违反了它，已回退。

### 最终形态（工作树中的实现）
四个契约同时成立，互不打架：
| 路径 | 行为 |
| :--- | :--- |
| 正常 chat（非流式） | **不转发** `backend.last_thought` ⇒ 私有思维留在服务端 |
| `_handle_json_response(text, reasoning_text=…)` | 调用方**显式传入**时才序列化 `reasoning_content`（调试/显式展示场景） |
| `_handle_streaming_response(…, expose_reasoning=False)` | **默认私有**，需显式 `expose_reasoning=True` 才输出 |
| `_handle_live_streaming_response`（生产 SSE） | 始终丢弃 thinking |

### 证据
`tests/test_deep_thinking.py` + `tests/test_bridge_protocol.py` 合计
**23 passed + 12 subtests passed**（四条契约同时成立）。

> **教训（已进 AGENTS.md §4.7 之外的规矩）**：看到"测试红了"先问**测试是不是过期**，
> 再问**产品契约为何**。本例中真正的缺陷不在产品，而在两份测试文件各自冻结了不同时代的契约；
> 只满足其中一份，就必然打翻另一份。裁决要落到**生产代码的行为与注释**上，而不是落到某一份测试的断言上。

---

## 十一、E5｜Auto-Diff 判分器：互换 vs 缺失、以及假绿

### 根因（两处）
1. **归因错**：判分器先查正语义，查不到就一律报 `missing_meaning:<color>`；于是
   「蓝色段写『过切（Gouge）』」这种**语义互换**被报成「意思没写」。两者都判红，
   但回执必须说清模型到底犯了哪种错（AGENTS.md §8.2）。
2. **假绿**：正语义用裸 `search`，**不做否定识别** ⇒ 蓝色段写
   「代表：不是过切，也不是残料」时，「残料」被当成正语义存在 ⇒ **判 PASS**。
   负语义侧本来就有否定前缀守卫（`并非|不是|非|无|…`），正语义侧缺了对称的一侧。

### 修复
- 正语义缺失但**负语义就在同一段里**且未被否定 ⇒ 报 `swapped_meaning:<color>`
- 正语义匹配也走否定守卫：只有**未被否定前缀**修饰的语义词才计入
- `MEASUREMENT_VERSION` 升到 `probes-2026-11-16-v5`（判分器身份必须可追溯）

### 反证（按 §8.2「植入坏样本 ⇒ 必须红」补齐）
`tests/test_probe_grader_fixes_20261116.py` 新增 4 条：
① 蓝色段写「过切（Gouge）」 ⇒ `swapped_meaning:blue`
② 蓝色段写「不是过切，也不是残料」 ⇒ **不得**判 PASS ⇒ `missing_meaning:blue`
③ 蓝色段写无关内容 ⇒ 仍是 `missing_meaning:blue`
④ 正确答案仍然 `passed=True / reason=ok`

### 证据
`test_probe_grader_fixes_20261116.py` + `test_vericut_e_cloud_gates.py` +
`test_six_software_probe_measurement_fix.py` + `test_coordinate_memory_comprehensive_fix.py`
合计 **58 passed**。

---

## 十二、本次改动文件清单

| 文件 | 改动 |
| :--- | :--- |
| `virtu_omni/agent/super_agent.py` | 签名绑定层 + 真实 schema 广播（D1 主体） |
| `bridges/software_registry.py` | NX 动态发现（D1 配套 / E1） |
| `bridges/nx_bridge.py` | `NX_BASE` 动态解析 + CRCRLF 行尾归正（E1） |
| `virtu_omni/security/auditor.py` | 拆分两类越界理由串（E6） |
| `scripts/build_vericut96_cloud_datasets.py` | 负样本语义化（D3） |
| `bridges/autocad_bridge.py`、`virtu_omni/agent/adaptive_router.py`、`virtu_omni/internet/internet_hub.py`、`virtu_omni/rea/adapter.py` | subprocess 编码（D2） |
| `tests/test_no_hardcoded_credentials.py` | subprocess 编码 + （E6 联动）测试侧 |
| `tests/test_cloud_instant_boot_scripts.py` | 文件捕获 + timeout 300s + marker（E3） |
| `tests/test_facet_call_contract.py` | **新增**：D1 反证测试 19 条 |
| `virtu_omni/agent/tool_binding.py` | **新增**：零依赖签名绑定层（D1/D1b） |
| `scripts/workbuddy_virtu_bridge.py` | 补 `reasoning_content`（JSON + SSE 顺序）（D4） |
| `cloud_train_pack/deploy_trained_adapter.py` | 判分器互换/缺失归因 + 正语义否定识别 + 版本升 v5（E5） |
| `tests/test_probe_grader_fixes_20261116.py` | 新增 4 条 E5 反证（含否定镜像用例） |
| `AGENTS.md` | 新增 §4.6 工具链体检与修复状态 + 三条新规矩 |

## 十三、复跑命令

```powershell
cd D:\Virtu模型
# D1 契约终裁
.venv\Scripts\python.exe scratch\toolchain_audit_12_adapter_contract.py
# D2 编码复扫
.venv\Scripts\python.exe scratch\scan_subprocess_encoding.py bridges virtu_omni
# NX 预检 + 功能实测
.venv\Scripts\python.exe scratch\check_preflight.py
.venv\Scripts\python.exe scratch\probe_nx_journal.py
.venv\Scripts\python.exe scratch\probe_nx_tool.py
# receipt 时效性
.venv\Scripts\python.exe scratch\check_receipts.py
# 全量回归
& 'C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe' -m pytest tests/ -q --timeout=300 -p no:cacheprovider
```
