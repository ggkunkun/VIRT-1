# 测评法律首次适用 · virtu-six-software:v3 全面测评（2026-11-16）

> 先立法律、再测评、最后看图。法律：`.agents/rules/virtu-evaluation-law.md`（本次新建）。
> 原始证据：`runs/eval_v3_law_20261116/`；结构化结果：`benchmarks/VIRTU_V3_LAW_EVAL_2026-11-16.json`；
> 雷达图：`benchmarks/v3_law_radar_20261116/compare/radar.png`（4 模型同口径对比）。

---

## 0. 一句话结论

**`virtu-six-software:v3` 比上一代 `six-software:v1` 有实质提升（综合 58.04 vs 54.15），
但仍低于训练前主力 `virtu-master-fixed:latest`（64.12），差 6.08；且训练目标探针只过 7/10。**
建议继续迭代，不建议直接替换生产主力。

---

## 1. 被测对象与身份（测评法律第一条）

| 项 | 值 |
| --- | --- |
| 标签 | `virtu-six-software:v3` |
| `/api/tags` digest | `35cd9e06c40e6a4faf4bd567…` |
| 模型层 sha256 | `abd8b726fbe792dddca40115cc93f3a9f915ff7389da3e5e8f2ad07e79baa10b` |
| 与回执一致性 | 与 `deployment_receipt_virtu-six-software_v3.VERIFIED_20261115_212646.json` 的 GGUF sha256 逐字一致 |
| 起链 run_id | `a9cfb7d09f9a7d1e`（身份快照 `runs/eval_v3_law_20261116/identity.json`） |
| 收链漂移 | v3 自身 digest 全程未变 |
| 库变更记录 | 期间新增 `virtu-six-software:v4-local-repair`（`965475066318…`，另一会话部署），**按法律第一条记录但不作废 v3 腿** |

---

## 2. 闸门（法律第二条：反证测试必须通过才开测）

| 闸门 | 结果 |
| --- | --- |
| 部署探针判据反证单测（`test_cloud_and_deploy_hardening.py` + `test_six_software_probe_measurement_fix.py`） | **24 passed**（86.6s） |
| 留出集 gold 满分自检 | **105/105 判 100.0**，PASS |
| 雷达图反例自检（篡改分数 / 删行 / 删封缄 / 植入传输错误 / 抹身份） | **5/5 判红 PASS** |

---

## 3. 实测结果

### 3.1 训练目标探针（n=10，`measurement_version=probes-2026-11-15-v2`，判分器已修复三类假阴性）

- **通过 7/10**；失败：`sw_coordinate_probe`、`lame_stress_probe`、`fanuc_g71_safety_probe`。
- 注意：21:40 的 `VERIFIED` 回执把这些项判为通过（同一 `measurement_version`）。本轮实测复现了失败，
  说明**回执与现场结果不一致**——按法律第一条，以带内容寻址的现场腿为准，回执只能作为历史凭证，不能顶替实测。
- 证据：`runs/eval_v3_law_20261116/targeted.json`（逐项 reason + 回答片段）。

### 3.2 24 案例领域关键词基准（n=24，`slot_exact_v2`）

| 模型 | mean | tok/s | 传输错误 |
| --- | --- | --- | --- |
| `virtu-six-software:v3` | **41.67** | 23.30 | 0 |

`run_id=1d53af6fb88a453d`，`basis=measured`。按法律第二条，**该绝对分只作同尺相对比较**，
不能解释为"掌握 41.67% 知识"（精确槽位口径系统性低估，详见上一轮复核报告）。

### 3.3 通用 7 维题板（n=28，雷达图数据源）

| 模型 | 工具编排 | 推理逻辑 | 知识覆盖 | 指令遵循 | 边界处理 | 内容生成 | 泛化适配 | 综合 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `virtu-master-fixed:latest`（基线） | 25.0 | **74.3** | 62.5 | 91.7 | **91.7** | **58.8** | 50.7 | **64.12** |
| **`virtu-six-software:v3`（本次）** | **33.3** | 57.6 | 62.5 | 91.7 | 75.0 | 35.0 | 50.7 | **58.04** |
| `virtu-six-software:v1` | 25.0 | 45.7 | 46.7 | 91.7 | 83.3 | 46.2 | 52.1 | 54.15 |
| `virtu-vericut96:v2` | 16.7 | 57.6 | 58.3 | 91.7 | 66.7 | 22.5 | 37.1 | 50.64 |

四条腿的判分器 sha256、runner sha256、用例文件哈希、采样参数（temperature=0 / seed=1234 /
num_predict≤384 / num_ctx=4096 / think=false / 每维 4 题）逐项一致，故可同图对比。
v3 腿 `run_id=b478b63c00150074`，完整性闸 28/28、0 传输错误，`gate.valid=True`。

**读图结论**：v3 在工具编排（33.3）上四臂最高，相比 v1 在推理（45.7→57.6）、知识（46.7→62.5）、
边界（83.3→75.0 反而下降）、内容生成（46.2→35.0 下降）有增有减。相对训练前基线，
v3 的主要差距在推理逻辑（−16.7）、边界处理（−16.7）、内容生成（−23.8）。

### 3.4 留出集（105 题去污染）

**未测**。按测评法律第四条：基线 `virtu-master-fixed:latest` 已不在当前 Ollama 库中，
无法构成同轮配对；上一轮历史腿虽有 `run_id=3dcc89b28e586675`，但被测对象与判分时间均不同，
不得顶替本次成绩。**没有补分、没有推断。**

### 3.5 多模态维

**未测**（库内无 VL 标签），雷达图不画该轴、不进综合分。

---

## 4. 雷达图

- 单构件图：`benchmarks/v3_law_radar_20261116/radar.png`（v3 一条腿）。
- 四模型同口径对比：`benchmarks/v3_law_radar_20261116/compare/radar.png`，带图例：
  蓝=master-fixed 基线 / 黄=v3 / 绿=six-software:v1 / 红=vericut96:v2。
- 图中每个点的 `run_id` / `n` / `evidence` 在配套 `radar.md` 与 `results.json` 中。
- 排除上图的腿：`virtu-vericut-e:latest`（标签被外部重指，成绩只归属旧 digest）、
  `qwen3:8b`（24 案例 24/24 空回答作废）。**未测腿不画点。**

---

## 5. 违法项自检（本次主动发现并修正）

1. **误判漂移**：首版链末报告把"库里新增 v4-local-repair 标签"当成被测对象漂移，
   把整链判 `voided_due_to_drift`。按法律第一条，只有被测 v3 自身 digest 变化才作废；
   已核对起链/收链 v3 digest 完全一致，在 `report.json` 中以 `drift_amendment` 留痕后改为 `measured`。
2. **雷达图缺图例**：初版 PNG 四条折线无法对应模型；已在 `generate_verified_radar.py::build_png` 补图例并重生成。
3. **雷达图脚本写死入口**：原脚本只能读 11-07 历史腿；已加 `--summary` / `--out-dir` 参数，
   默认值不变，历史用法不受影响。
