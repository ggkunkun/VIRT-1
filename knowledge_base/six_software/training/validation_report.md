# 六软件 tool-call 训练语料与运行手册 — 独立静态结构校验报告

> 校验角色：独立校验子代理（只读，不修改任何被校验文件）。
> 校验时间：2026-11-04。
> 校验方法：纯静态（Read / Grep / Glob），未执行任何 shell 或 python 脚本。
> 基准契约：`TRAINING_CONTRACT.md` §2 硬性规则 + `scripts/validate_render_dataset.py` C1–C5。

---

## 1. 校验范围与方法

### 1.1 被校验对象
- 12 个 JSONL：`datasets\{solidworks,autocad,nx,cimco,vericut,sscnc}_{train,holdout}.jsonl`
- 6 个 runbook：`runbooks\{solidworks,autocad,nx,cimco,vericut,sscnc}.runbook.md`
- 契约：`TRAINING_CONTRACT.md`

### 1.2 方法
- **C1 结构**：Grep `^\{"tools"` 计行数；Grep `"messages"` 确认字段存在；Grep `.` 计非空行。
- **C2 模板段**：Grep `"type":"function"` 确认 tools 数组含 function；抽样 Read 确认 system/user 角色。
- **C3/C4 掩码前提**：Grep `"role":"assistant"` / `"tool_calls"` / `"role":"tool"` 计数比对。
- **C5 配对**：Grep `"id":"call_"` vs `"tool_call_id":"call_"` 文件级配对；Grep `"tool_call_id","call_"` 检测逗号替代冒号的畸形结构。
- **边界扫描**：Grep `license|keygen|crack|lmutil|License.dll|swlm|破解|激活`（忽略大小写）。
- **runbook**：Grep `^## ` 确认 §0/§1/§2/§3 四区块标题。
- **UTF-8/BOM**：Read 抽查中文渲染正常即无 BOM 乱码。

### 1.3 已知限制
- 本轮 PowerShell 工具返回 `HISTORY_INVALID_PATH`，Bash 禁用，故**未执行** `validate_render_dataset.py` 与逐行 `json.loads`。本报告为静态等价结论，权威渲染校验须留待有 shell 会话。
- Grep count 模式按"匹配行数"计（非每出现次数）；多 tool-call 链记录一行含多个 call_N 时按 1 行计。

---

## 2. 逐文件结果表

| 文件 | 期望条数 | 实测行数 | C1 结构 | C5 id↔tool_call_id 配对 | 抽查结论 |
|---|---|---|---|---|---|
| solidworks_train.jsonl | 33 | 33 | ✅ | 31 ↔ 31 ✅ | mass_properties_check 等 arguments 字符串闭合正常 |
| solidworks_holdout.jsonl | 7 | 7 | ✅ | 6 ↔ 6 ✅ | Inconel718 FOS 记录结构正常 |
| autocad_train.jsonl | 33 | 33 | ✅ | 31 ↔ 31 ✅ | 抽样 LISP/Express 记录正常 |
| autocad_holdout.jsonl | 7 | 7 | ✅ | 6 ↔ 6 ✅ | 抽样 RText/动态块记录正常 |
| nx_train.jsonl | 30 | **29** | ⚠️ 少 1 行 | 27 ↔ 27 ✅ | 行数不足，需补 1 条 |
| nx_holdout.jsonl | 7 | 7 | ✅ | 6 ↔ 6 ✅ | 抽样正常 |
| cimco_train.jsonl | 30 | **27** | ⚠️ 少 3 行 | **25 id ↔ 13 tool_call_id ❌** | **12 行 `"tool_call_id","call_N"` 逗号替代冒号，JSON 非法** |
| cimco_holdout.jsonl | 7 | 7 | ✅ | **6 id ↔ 1 tool_call_id ❌** | **5 行同类逗号畸形** |
| vericut_train.jsonl | 32 | 32 | ✅ | 31 ↔ 31 ✅ | ToolMan/Auto-Diff 记录正常 |
| vericut_holdout.jsonl | 7 | 7 | ✅ | 6 ↔ 6 ✅ | launch_project+play 多轮链正常 |
| sscnc_train.jsonl | 31 | 31 | ✅ | 28 ↔ 28 ✅ | CRT MACHINE 页记录结构正常 |
| sscnc_holdout.jsonl | 7 | 7 | ✅ | 6 ↔ 6 ✅ | 抽样正常 |

**合计**：期望 231 条，实测 227 条（少 4 条：nx_train -1、cimco_train -3）。

---

## 3. C1–C5 等价静态结论汇总

| 校验项 | 结论 | 明细 |
|---|---|---|
| **C1 每行 `{"tools"` 开头 + 含 `"messages"`** | ⚠️ 部分通过 | 12 文件每行均以 `{"tools"` 开头且含 `"messages"`；无空行夹带。但 nx_train 29/30、cimco_train 27/30 行数不足。 |
| **C2 tools 数组含 `"type":"function"` + system/user 角色** | ✅ 通过 | 抽样各文件均含 tools 数组（≥1 function）与 system/user/assistant/tool 角色。 |
| **C3 assistant 数 ≥ tool_calls assistant 数** | ✅ 通过（除 cimco 畸形行） | 非畸形行均满足；cimco 17 畸形行因 JSON 非法无法静态判定，须 json.loads 复核。 |
| **C4 `"role":"tool"` 数 == `"tool_call_id"` 数** | ✅ 通过（除 cimco 畸形行） | 非 cimco 文件均平衡；cimco 文件 key 存在但 value 畸形。 |
| **C5 `"id":"call_"` == `"tool_call_id":"call_"` 配对** | ❌ **不通过** | cimco_train 25≠13、cimco_holdout 6≠1；其余 10 文件配对平衡。 |
| **C5 `"type":"function"` 出现于 tool_calls** | ✅ 通过 | 抽样确认 tool_calls 内 `type:"function"` 存在。 |
| **C5 arguments 为字符串且括号配平** | ✅ 通过（抽样） | 重点复查 5 处曾修复位置均正常（见 §5.2）。 |

---

## 4. 边界扫描结果

Grep `license|keygen|crack|lmutil|License.dll|swlm|破解|激活`（忽略大小写）全 12 文件：

| 命中文件:行 | 上下文 | 判读 |
|---|---|---|
| autocad_train.jsonl:33 | 用户要求"破解AutoCAD订阅"，assistant 拒答 | ✅ D 场景拒答样本，合规 |
| cimco_train.jsonl:26 | 用户要求"绕过 CIMCO 授权"，assistant 拒答 | ✅ 合规 |
| nx_train.jsonl:21 | 用户要求"绕过 NX 授权+写 keygen"，assistant 拒答 | ✅ 合规 |
| solidworks_train.jsonl:33 | 用户要求"破解 SOLIDWORKS 许可"，assistant 拒答 | ✅ 合规 |
| sscnc_train.jsonl:21 | 用户要求"破解斯沃注册校验"，assistant 拒答 | ✅ 合规 |
| vericut_train.jsonl:14 | 用户要求"绕过 VERICUT 许可"，assistant 拒答（含 knowledge.lookup_module 调用） | ✅ 合规 |

**结论**：6 处命中全部为 D 场景"越界拒答"文本，工具名/参数中无任何边界关键词。**合规**。

---

## 5. 问题清单

### 5.1 严重缺陷（C1/C5 失败 — JSON 非法）

| # | 文件 | 行号 | 问题类型 | 证据模式 |
|---|---|---|---|---|
| 1 | cimco_train.jsonl | 11, 12, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25（共 12 行） | `"tool_call_id"` 后冒号被误写为逗号，导致 JSON 非法 | `"tool_call_id","call_1"`（应为 `"tool_call_id":"call_1"`） |
| 2 | cimco_holdout.jsonl | 2, 3, 4, 5, 6（共 5 行） | 同上 | `"tool_call_id","call_1"` |

**影响**：这 17 行无法通过 `json.loads`，C1（JSON 结构）与 C5（tool_call_id 配对）均失败。训练时这些行会被 dataloader 跳过或报错。

**修复建议**：将上述行中 `"tool_call_id","call_N"` 改为 `"tool_call_id":"call_N"`（逗号→冒号）。

### 5.2 行数不足（C1 条数不符）

| # | 文件 | 期望 | 实测 | 缺口 |
|---|---|---|---|---|
| 3 | nx_train.jsonl | 30 | 29 | -1 |
| 4 | cimco_train.jsonl | 30 | 27 | -3 |

**说明**：cimco_train 缺口 3 条与 §5.1 的 12 行畸形是两回事（行数本身少 3 条记录，另有 12 条记录内部 JSON 畸形）。

### 5.3 曾修复位置复查（当前状态：均正确 ✅）

| 位置 | 原缺陷 | 当前状态 |
|---|---|---|
| solidworks_train.jsonl 原第 2 条 | mass_properties_check arguments 缺右括号 | ✅ 现为 `"{\"part\": \"shaft.SLDPRT\"}"`，闭合正常 |
| solidworks_train.jsonl 原第 27 条 | 逗号误入字符串 | ✅ 现为 simulation_static_study 多轮链，arguments 正常 |
| solidworks_holdout.jsonl 原第 5 条 | 同类 | ✅ Inconel718 FOS 记录，arguments 正常 |
| vericut_holdout.jsonl 原第 1 条 | tool_call 结构 | ✅ launch_project + play_simulation 双轮链，结构正常 |
| sscnc_train.jsonl "CRT MACHINE 页"记录 | tool_call 结构 | ✅ 第 30 行 `crt_readout_check` page=MACHINE，结构正常 |

---

## 6. runbook 结构校验

6 个 runbook 均存在，且均含 §0 速查卡、§1 GUI 路线、§2 API 路线、§3 插件路线 四个区块标题（另含 §4 故障处置为附加章节）。

| runbook | §0 速查卡 | §1 GUI | §2 API | §3 插件 |
|---|---|---|---|---|
| solidworks.runbook.md | ✅ L6 | ✅ L23 | ✅ L33 | ✅ L53 |
| autocad.runbook.md | ✅ L6 | ✅ L23 | ✅ L33 | ✅ L52 |
| nx.runbook.md | ✅ L6 | ✅ L13 | ✅ L37 | ✅ L63 |
| cimco.runbook.md | ✅ L6 | ✅ L12 | ✅ L29 | ✅ L37 |
| vericut.runbook.md | ✅ L6 | ✅ L18 | ✅ L37 | ✅ L49 |
| sscnc.runbook.md | ✅ L6 | ✅ L18 | ✅ L44 | ✅ L57 |

---

## 7. 权威校验命令清单（供有 shell 会话执行）

```powershell
# 12 条 validate_render_dataset.py
python scripts/validate_render_dataset.py --data D:/Virtu模型/knowledge_base/six_software/training/datasets/solidworks_train.jsonl --out data/validation/render_report_solidworks_train.json
python scripts/validate_render_dataset.py --data D:/Virtu模型/knowledge_base/six_software/training/datasets/solidworks_holdout.jsonl --out data/validation/render_report_solidworks_holdout.json
python scripts/validate_render_dataset.py --data D:/Virtu模型/knowledge_base/six_software/training/datasets/autocad_train.jsonl --out data/validation/render_report_autocad_train.json
python scripts/validate_render_dataset.py --data D:/Virtu模型/knowledge_base/six_software/training/datasets/autocad_holdout.jsonl --out data/validation/render_report_autocad_holdout.json
python scripts/validate_render_dataset.py --data D:/Virtu模型/knowledge_base/six_software/training/datasets/nx_train.jsonl --out data/validation/render_report_nx_train.json
python scripts/validate_render_dataset.py --data D:/Virtu模型/knowledge_base/six_software/training/datasets/nx_holdout.jsonl --out data/validation/render_report_nx_holdout.json
python scripts/validate_render_dataset.py --data D:/Virtu模型/knowledge_base/six_software/training/datasets/cimco_train.jsonl --out data/validation/render_report_cimco_train.json
python scripts/validate_render_dataset.py --data D:/Virtu模型/knowledge_base/six_software/training/datasets/cimco_holdout.jsonl --out data/validation/render_report_cimco_holdout.json
python scripts/validate_render_dataset.py --data D:/Virtu模型/knowledge_base/six_software/training/datasets/vericut_train.jsonl --out data/validation/render_report_vericut_train.json
python scripts/validate_render_dataset.py --data D:/Virtu模型/knowledge_base/six_software/training/datasets/vericut_holdout.jsonl --out data/validation/render_report_vericut_holdout.json
python scripts/validate_render_dataset.py --data D:/Virtu模型/knowledge_base/six_software/training/datasets/sscnc_train.jsonl --out data/validation/render_report_sscnc_train.json
python scripts/validate_render_dataset.py --data D:/Virtu模型/knowledge_base/six_software/training/datasets/sscnc_holdout.jsonl --out data/validation/render_report_sscnc_holdout.json

# 逐行 json.loads 校验（重点复核 cimco_train / cimco_holdout）
python -c "import json,sys; [print(i, 'OK' if json.loads(l) else 'FAIL') for i,l in enumerate(open(sys.argv[1],encoding='utf-8')) if l.strip()]" D:/Virtu模型/knowledge_base/six_software/training/datasets/cimco_train.jsonl
python -c "import json,sys; [print(i, 'OK' if json.loads(l) else 'FAIL') for i,l in enumerate(open(sys.argv[1],encoding='utf-8')) if l.strip()]" D:/Virtu模型/knowledge_base/six_software/training/datasets/cimco_holdout.jsonl
```

---

## 8. 结论

- **10/12 JSONL 文件静态结构通过**（solidworks/autocad/nx/vericut/sscnc 共 10 文件）。
- **cimco_train.jsonl 与 cimco_holdout.jsonl 存在严重缺陷**：17 行 `"tool_call_id","call_N"` 逗号替代冒号，导致 JSON 非法、C5 配对失败。**须修复后方可入训**。
- **条数缺口**：nx_train 少 1 条、cimco_train 少 3 条，需补录。
- **边界扫描合规**：6 处命中均为 D 场景拒答文本，无工具/参数违规。
- **runbook 结构齐全**：6 份均含四路线区块。
- **曾修复的 5 处位置当前均正确**。
- **权威 C1–C5 渲染校验与逐行 json.loads 须留待有 python 的 shell 会话执行**（本静态报告不替代）。

---

## 9. 复检结论（2026-11-04，分片B 修复后）

### 9.1 复检对象与结果

| 文件 | 期望行数 | 实测行数 | `"tool_call_id","call_` 残留 | id↔tool_call_id 配对 | Read 抽查 | 结论 |
|---|---|---|---|---|---|---|
| nx_train.jsonl | 30 | **30** ✅ | 0 | 28 ↔ 28 ✅ | 第30条补录 `nx.cam_template_load` arguments `"{\"template_set\":\"mill_multi-axis_hsm.opt\"}"` 闭合正常 | ✅ 通过 |
| cimco_train.jsonl | 30 | **30** ✅ | 0 | 28 ↔ 28 ✅ | 第11条修后 `"tool_call_id":"call_1"` 冒号已恢复；第28/29/30条补录（backplot_verify / postprocess_js / knowledge.lookup_module）arguments 均闭合 | ✅ 通过 |
| cimco_holdout.jsonl | 7 | **7** ✅ | 0 | 6 ↔ 6 ✅ | 第3条修后 `"tool_call_id":"call_1"` 冒号已恢复，arguments `"{\"post_js\":\"Posts\\\\Mill\\\\haas.js\"}"` 闭合正常 | ✅ 通过 |

### 9.2 全量 12 文件最终状态

| 文件 | 状态 |
|---|---|
| solidworks_train / solidworks_holdout | ✅ 通过（首轮即合格） |
| autocad_train / autocad_holdout | ✅ 通过（首轮即合格） |
| nx_train | ✅ 通过（复检补录 1 条后达 30） |
| nx_holdout | ✅ 通过 |
| cimco_train | ✅ 通过（复检修复 12 处逗号+补录 3 条后达 30） |
| cimco_holdout | ✅ 通过（复检修复 5 处逗号后达 7） |
| vericut_train / vericut_holdout | ✅ 通过（首轮即合格） |
| sscnc_train / sscnc_holdout | ✅ 通过（首轮即合格） |

**残留问题**：无。`"tool_call_id","call_` 畸形模式在全 datasets 目录 0 命中；id↔tool_call_id 配对全部平衡；总行数 189+42=231 与期望一致。

### 9.3 更新总体结论

- 12 个 JSONL 文件静态结构校验**全部通过**（C1 行数 / C5 配对 / 畸形模式扫描）。
- 6 个 runbook 四路线区块齐全。
- 边界扫描合规（6 处均为 D 场景拒答文本）。
- 曾修复的 5 处历史位置 + 分片B 修复的 17 处逗号 + 4 条补录，复检均正确。
- **仍待办**：权威 `validate_render_dataset.py` 渲染校验与逐行 `json.loads` 须在有 python 的 shell 会话执行（本静态报告不替代）。

---

## 10. 复检结论（2026-11-04 阶段A/B迭代 — fastest_route 追加后全量复检）

### 10.1 12 文件逐文件结果

| 文件 | 期望行数 | 实测行数 | `"tool_call_id","` 坏模式 | id↔tool_call_id 配对 | 尾部 fastest_route 抽查 | 结论 |
|---|---|---|---|---|---|---|
| solidworks_train.jsonl | 38 | 38 ✅ | 0 | 平衡 ✅ | 第38条 hole_wizard 多轮链正常 | ✅ |
| solidworks_holdout.jsonl | 8 | 8 ✅ | 0 | 平衡 ✅ | 第8条 run_macro.swp 正常 | ✅ |
| autocad_train.jsonl | 38 | 38 ✅ | 0 | 平衡 ✅ | 抽样正常 | ✅ |
| autocad_holdout.jsonl | 8 | 8 ✅ | 0 | 平衡 ✅ | 抽样正常 | ✅ |
| nx_train.jsonl | 36 | 36 ✅ | 0 | 平衡 ✅ | 第34/35/36条 fastest_route（mill_planar/hole_making/batch_step）多轮链，arguments 转义正常 | ✅ |
| nx_holdout.jsonl | 9 | 9 ✅ | 0 | 平衡 ✅ | 抽样正常 | ✅ |
| cimco_train.jsonl | 36 | 36 ✅ | 0 | 平衡 ✅ | 第36条边界拒答（2D画图 N/A）正常 | ✅ |
| cimco_holdout.jsonl | 9 | 9 ✅ | 0 | 平衡 ✅ | 抽样正常 | ✅ |
| vericut_train.jsonl | 37 | 37 ✅ | 0 | 平衡 ✅ | 第37条 fastest_route_first_proof 三轮链（lookup→launch→play）正常 | ✅ |
| vericut_holdout.jsonl | 8 | 8 ✅ | 0 | 平衡 ✅ | 第8条 fastest_route_polyfix 双轮链正常 | ✅ |
| sscnc_train.jsonl | 36 | 36 ✅ | 0 | 平衡 ✅ | 第35/36条 fastest_route（multi_controller/crt_check）多轮链正常 | ✅ |
| sscnc_holdout.jsonl | 8 | 8 ✅ | 0 | 平衡 ✅ | 抽样正常 | ✅ |

**行数合计**：train 221（38+38+36+36+37+36）+ holdout 50（8+8+9+9+8+8）= **271**，与期望一致。

### 10.2 配对平衡

全目录 `"id":"call_"` 与 `"tool_call_id":"call_"` 命中行数完全一致（persisted 文件字节数均为 539729 bytes），含多调用链（vericut_train:37 三轮链 call_1/2/3、sscnc_train:36 双轮链 call_1/2）均配对平衡。

### 10.3 边界扫描

6 处命中（nx_train:21、cimco_train:26、autocad_train:33、solidworks_train:33、vericut_train:14、sscnc_train:21），全部为 D 场景越界拒答文本，工具名/参数无 license/keygen/crack/破解/激活。**合规**。

### 10.4 runbook 与 fastest-methods 文件存在性

- 6 份 runbook 全部存在 ✅
- `fastest-methods/` 目录 **9/9 文件存在**（含归并总表 `fastest-methods.md` 与选型矩阵 `toolchain_choice_matrix.md`，组织者补写）：`FASTEST_METHODS_CONTRACT.md` + `solidworks.md / autocad.md / nx.md / cimco.md / vericut.md / sscnc.md` + `fastest-methods.md` + `toolchain_choice_matrix.md`。

### 10.5 总体结论

- **271 条语料全量静态结构校验通过**：12 文件行数=期望、`"tool_call_id","` 坏模式 0 命中、id↔tool_call_id 配对平衡、尾部 fastest_route 记录 arguments 转义与多轮链结构正常。
- **残留问题**：无 C1–C5 类缺陷；fastest-methods 目录 9/9 文件齐备（归并总表与选型矩阵已由组织者补写）。
- **仍待办**：权威 `validate_render_dataset.py` 渲染校验与逐行 `json.loads` 须在有 python 的 shell 会话执行（本静态报告不替代）。
