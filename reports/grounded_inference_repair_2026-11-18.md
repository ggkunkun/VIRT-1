# 推理侧缺陷修复与生产接入报告（2026-11-18）

**范围**：推理侧防线 + 生产链路接入（**不改权重**）。针对 `reports/SIX_SOFTWARE_STEP1_AUDIT_2026-11-18.json`（`probes-2026-11-16-v5`，grader `74a7da08...`，`basis=measured`）中 `virtu-six-software:v3`（digest `35cd9e06...`）在换参后暴露的三类泛化缺陷：

1. **Lamé 换参失真**：`Di=50, Do=100, Pi=24` 未给出 $\sigma_\theta = 40.00\text{ MPa}$；
2. **G71 官方题轮廓欠缺**：仅 2 个运动块，缺 $\varnothing 38$ 台阶、$\text{X}60$ 台阶肩与 $\text{Z}-45$ 总长，G70 从毛坯内部起刀；
3. **G71 换参安全事故**：$\varnothing 80 \to \varnothing 46 \times 25$、总长 $60$ 时在轮廓中写出 `G0 Z-25.0`（G00 朝负 Z 快速扎刀）。

---

## 本轮改动清单

| 文件 | 改动 |
|---|---|
| `virtu_omni/agent/grounded_inference.py` | 闭式解 `lame_thick_cylinder`、题面解析与数值门 `check_lame_answer`（含 `= - 24` 空格负号兼容）；参数化语义门 `validate_g71_against_spec`（含**模态 G00** 负 Z 扎刀拦截）；安全退刀 `generate_g71_program`（`retract_x = max(100, stock_d + 20)`）；`GroundedResponder`（单 system 合并提示 + 违规反馈重写 $\le 3$ 轮 + 确定性兜底）与 `is_grounded_applicable` / `build_grounding_hint` |
| `virtu_omni/agent/super_agent.py` | 注册 `solve_lame_cylinder` 与 `generate_validated_g71` 工具；`facet_parse_intent` / `facet_generate_cam` 在 G71 台阶轴题面上改为按题面实参生成并通过静态语义门 + CIMCO 沙箱；`facet_verify_cae` 兼容字符串 Lamé 题面并接入闭式解（保留既有 `max_von_mises_stress_mpa` 兼容字段）；`facet_audit_sandbox` 字符串路径走 `facet_generate_cam`；`build_runtime_memory_context` 注入 `[确定性接地约束]`；新增 `respond_grounded()` 与 `solve(..., mode="GROUNDED")` |
| `virtu_omni/agent/facet_contracts.py` | 补充 `solve_lame_cylinder`（`cae`）与 `generate_validated_g71`（`machining`）角色与结果字段契约 |
| `scripts/workbuddy_virtu_bridge.py` | `/v1/chat/completions` 与 `/chat/completions` 的非流式与流式（`stream=True`）路径接入 `_run_grounded_chat`；非适用请求零改动透传；返回附加 `virtu_grounding` 溯源字段（明示 `source=model \| deterministic_*`、`model_passed`、`attempts`）；支持 `VIRTU_GROUNDED_INFERENCE=0` 与请求体 `"grounded": false` 显式消融对照；`deception_gate` 安全性与防泄露规则继续前置生效 |
| `virtu_eval/provenance.py` | `_store_manifest_path` 补齐 `OLLAMA_MODELS` 环境变量与 Ollama 新版 `manifests-v2` 目录支持，使 `artifact_identity("virtu-six-software:v3")` 可定位真实 `manifest_sha256`（`35cd9e06c40e...`）与底层 layer 哈希 |
| `scripts/grounded_reprobe.py` | 真机裸模型 vs 接地层对照复测脚本：独占检查、`/api/tags` + `RunIdentity` 双指纹防漂移、官方判分器（`deploy_trained_adapter` + `g71_semantic_check`）交叉核对 |
| `tests/test_grounded_inference.py` | 35 条离线契约与集成测试（含模态 G00 扎刀、大毛坯退刀、v3 实录回放、10 种坏样本必红、`VirtuSuperAgent`、WorkBuddy Bridge 非流式/流式/消融/安全门） |

---

## 实测验证证据（`basis=measured`，离线）

1. **13 个相关测试集全量通过**：
   ```
   VIRTU_REACT_BUDGET_S=2 .venv/Scripts/python.exe -m pytest \
     tests/test_grounded_inference.py tests/test_super_agent.py \
     tests/test_bridge_protocol.py tests/test_bridge_security.py \
     tests/test_bridge_usage.py tests/test_working_memory_bridge.py \
     tests/test_real_backend_protocol.py tests/test_facet_call_contract.py \
     tests/test_arithmetic_guard.py tests/test_deception_gate.py \
     tests/test_agent_team_real_agents.py tests/test_capability_transfer.py \
     tests/test_provenance_gates.py -q -p no:cacheprovider
   ```
   结果：**223 passed, 16 subtests passed in 40.13s**（含 `tests/test_grounded_inference.py` 单独运行 **35 passed in 14.75s**）。
2. **补充归因测试（独立运行）**：
   `.venv/Scripts/python.exe -m pytest tests/test_runner_repeats.py tests/test_eval_in_situ_gate.py -q -p no:cacheprovider`
   结果：**15 passed in 8.71s**（此前与 13 文件测试并发执行时因宿主机内存紧张在 `conftest.py` 复制 `hindsight_banks.json` 处报过一次 `WinError 127`，单独跑已全部通过）。
3. **语法检查**：
   `.venv/Scripts/python.exe -m py_compile ...` 全部改动文件通过。
4. **身份指纹实测**：
   `artifact_identity("virtu-six-software:v3")` 返回 `present=True`、`manifest_sha256=35cd9e06c40e6a4faf4bd567da68d0ecdb58058f432cf543492bc9ff2b7ca69b`。

---

## 真机在线对照复测（`basis=measured`，2026-11-18 19:15–19:18）

在独占链（GPU 空闲 5920 MiB、无其它训练/评测进程、无他模占用）下对 `virtu-six-software:v3`（digest `35cd9e06c40e6a4faf4bd567da68d0ecdb58058f432cf543492bc9ff2b7ca69b`）执行 `.venv/Scripts/python.exe -u scripts/grounded_reprobe.py --tag virtu-six-software:v3`：

- **身份与漂移**：`run_id=5b86a821bcc7cfbb`，`drift=[]`，`transport_errors=[]`，`basis=measured`；证据目录 `runs/grounded_reprobe/20261118_191500/report.json`。
- **总览（`n=6`）**：
  - 裸模型原生通过（`bare_model_passed`）：**2 / 6**
  - 接地提示下模型自己答对（`grounded_model_passed`）：**3 / 6**（3 道 Lamé 均由模型按注入闭式解输出并通过校验）
  - 触发确定性兜底（`grounded_fallback_used`）：**3 / 6**（3 道 G71 在 3 轮违规反馈后仍未通过语义门，按契约由 `deterministic_generator` 兜底，不计入模型能力分）
  - 接地层最终安全交付（`grounded_final_passed`）：**6 / 6**

| 用例 | 裸模型 | 接地后模型自答 | 最终交付来源与结论 |
|---|---|---|---|
| `lame_official` (Di60/Do120/Pi20) | ✅ | ✅ | `model` ✅（官方 `lame_stress_probe` PASS） |
| `lame_gen_50_100_24` | ✅ | ✅ | `model` ✅ |
| `lame_gen_40_100_15` (应 20.71 / −15) | ❌（错算为 3.00 / 22.50 MPa） | ✅ | `model` ✅ |
| `g71_official` (D60→D38×20, L45) | ❌（缺 X60） | ❌（4 轮仍缺特征/带 W） | `deterministic_generator` ✅（官方令牌门+语义门均 PASS） |
| `g71_gen_80_46_25_60` | ❌（仅 2 块，缺 X80） | ❌（4 轮未命中 P/Q） | `deterministic_generator` ✅ |
| `g71_gen_50_30_15_40` | ❌（**`G00 Z-25.0` 扎刀**、缺 F0.2/X50） | ❌（4 轮仍带 Z/起点越界） | `deterministic_generator` ✅ |

## 边界声明

- 本方案是**推理侧确定性防线与生产链路接地**，不改变模型权重本身；在无接地层保护（`grounded=false` 或 `VIRTU_GROUNDED_INFERENCE=0`）下，裸模型 `v3` 在换参题面上的原生能力缺陷仍存在，不得把 `deterministic_*` 兜底结果计入模型能力分。
- `validate_g71_against_spec` 核对程序文本几何语义，不等同于 VERICUT/实体机床仿真通过。
