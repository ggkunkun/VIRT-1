# 「Virtu 13.63B 读不懂装配体」——全面执行结果报告

- 日期：2026-11-06｜工作区：`D:\Virtu模型`｜口径：**全部数值均为实跑 measured**
- 样本：`微型机轮模总成(P0) 6R15-6R12-6R10.step`（AP203/GBK/装配体）+ 工作区 16 个 STEP
- 证据索引：`reports/step_bom_scan.json`、`reports/step_bom_ab_test.json`、
  `reports/multiagent_assembly.json`、`reports/step_pairs.json`、`reports/ap_detect.json`

---

## 一句话结论

**不是模型能力不够，是 STEP 表征方式不适合 LLM。** 把原始 STEP 换成结构化 BOM 后，
同一个 13.63B 模型在**等长上下文**下从「不确定，信息不足」变成精确列出
**5 个零件 + 4 组摆放坐标**。全部建议已执行完毕并实测通过。

---

## 二、决定性实证：A/B 对照（`reports/step_bom_ab_test.json`）

同一模型 `virtu-moe-14b:fast`、同一问题、**刻意对齐的上下文长度**，唯一变量是表征方式：

| 路 | 输入 | 长度 | 命中 | 模型实际回答 |
|---|---|---:|---:|---|
| **A** | 原始 STEP 几何片段 | 2016 字符 | **0/7** | 「不确定。该 STEP 文件未提供足够信息…建议在 CAD 软件中打开」 |
| **B** | 结构化 BOM 注入 | 1991 字符 | **7/7** | 正确列出 5 个零件（含区分顶层总成与 4 子件）与全部坐标 `(0,48,0)`、`(0,73,-65.3)`、`(-1,73,-65.3)`、`(-113.4736,77,-12)` |

事实核查关键词 = 4 个子件名 + 3 个特征坐标数。A 路 77.1s、B 路 104.7s，
排除了「B 上下文更长」的解释。复现命令：

```bash
python3 bridges/step_bom_ab_test.py --json reports/step_bom_ab_test.json
```

---

## 三、根因（实测，非推测）

| # | 根因 | 证据 |
|---|---|---|
| 1 | **GBK 编码**：中文零件名是 GBK 字节 | `FILE_NAME ('微型机轮模总成(P0)…')`；16 文件中 2 个 gbk |
| 2 | **结构信号 <0.05%**：装配树只有 4 行且藏在文件末尾 | 7690 实体中 `NEXT_ASSEMBLY_USAGE_OCCURRENCE` = 4 |
| 3 | **隐式 `#id` 跨 8000 行交叉引用**，无自然语言锚点 | 位姿需经 `RRWT→IDT→AXIS2_PLACEMENT_3D` 四跳 |
| 4 | **几何挂在 representation 子类型**，靠同 context 关联 | `ADVANCED_BREP_SHAPE_REPRESENTATION` |
| 5 | **AP 老旧且变体多** | AP214=14 / AP203=2 / AP242=0；`mold_core_mandrel` 用 `BREP_WITH_VOIDS` |

补充发现：`assets/` 里 9 个 AP214 文件**全是单零件**（1 PRODUCT、0 装配关联），
真正的装配体只有 `wheel_mold_P0.step`。所以解析器必须同时覆盖「单零件」与「装配体」。

---

## 四、已落地的 6 类解法（全部实跑验证）

### P0 统一 BOM 解析器 —— 核心
`bridges/step_bom.py`：纯标准库、零依赖，同时扛 AP203 + AP214，
自动探测编码(GBK/UTF-8)与 AP 版本，输出零件名／层级树／实体·面数／命名特征／包围盒／
4×4 摆放位姿；导出 **JSON / Markdown / 紧凑 DSL / `to_prompt_context()`**。

```
微型机轮模总成(P0) … (装配容器)
├─ 微型机轮模(P0)   1实体/76面  倒角1      @ (0, 48, 0)
├─ 微型机夹模(P0)   1实体/41面  圆角1      @ (0, 73, -65.3)
├─ 微型机导模(P0)   1实体/45面  圆角1      @ (-1, 73, -65.3)
└─ 微型机夹料模(P0) D6  3实体/64面 切除-拉伸1[1/2/3] @ (-113.4736, 77, -12)
```

**通用性验证**（`bridges/batch_scan.py` → `reports/step_bom_scan.json`）：
16/16 文件通过（含 26 万实体大文件、GBK/UTF-8、AP203/AP214、
`BREP_WITH_VOIDS`），通过率 100%，error=0。
**21,228,236 字节原始 STEP → 3,591 字节结构化 BOM，压缩比 5911×**。
（唯一 `ok_no_solids` 是 `0 1.STEP`，26 实体的空几何测试文件，本身无实体。）

### 集成进 virtu_omni —— 四条路径端到端通过
| 入口 | 改动 |
|---|---|
| `bridges/step_reverse.py` | 新增 `action="bom"`，返回 `bom`/`dsl`/`prompt_context` |
| `bridges/tool_calling_specs.py` | `cadcam_step_reverse` 枚举加 `bom`，描述标注「理解装配体首选」 |
| `bridges/six_software_orchestrator.py` | `step_reverse()` 加 `bom` 分支（独立于几何引擎，早返回） |
| `bridges/step_assembly.py` | 新增 `bom()` / `assembly_bom` 兼容封装，**旧 `assembly()` 零改动** |
| `bridges/step_preprocess.py` | 单函数接口：`preprocess_step()` / `build_step_prompt()` / `inject_into_messages()` |

感知/建模通道最小接入：
```python
from bridges.step_preprocess import preprocess_step
ctx = preprocess_step(step_path)          # ~1.2KB 结构摘要，直接塞 prompt
```

### P1 训练配对
`bridges/step_training_pairs.py` → `data/step_bom_sft.jsonl`：**109 条**样本
（`step_to_bom` 13 / `bom_to_nl` 13 / `schema_detect` 13 / `qa` 70），
4 类任务视角，QA 答案全部由 BOM 确定性生成，每条带 `source_sha256` + `basis`。

### P3 多智能体分解
`bridges/multiagent_assembly.py`：3 路确定性 facet
（结构 / 几何图元谱 / 位姿）+ 1 个 LLM 合成器。实测产出曲面图元谱
`PLANE=102, CYLINDRICAL=57, TOROIDAL=41, CONICAL=26`、圆半径谱 `R0.5…R7.0`，
合成 prompt 仅 1927 字符。几何负担不进 LLM。

### P4 编码归一化
`bridges/step_normalize.py`：`utf8`（LLM 语料友好）/ `x2`（STEP 标准 `\X2\` 转义，
纯 ASCII）两模式，默认**不覆盖源文件**。实测 GBK→UTF-8 后回读，
中文名／5 零件／4 关联／坐标**全部无损**。

### P2 AP242 源头治理
`AP242_EXPORT_GUIDE.md` + `bridges/ap_detect.py`。盘点结果：
11 个文件 AP214=10 / AP203=1，需 UTF-8 迁移 1 个，建议升级 AP242 共 11 个。
文档含 SolidWorks 2021 / NX 12 具体导出步骤、常见坑、导出后验证清单。
**明确结论：AP242 不能替代 P0，两者是组合拳。**

---

## 五、交付物清单

| 文件 | 作用 |
|---|---|
| `bridges/step_bom.py` | 统一 BOM 解析器（核心引擎） |
| `bridges/step_preprocess.py` | 模型 prompt 注入单函数接口 |
| `bridges/batch_scan.py` | 通用性批量验证 + 证据报告 |
| `bridges/step_training_pairs.py` | (STEP,BOM) 训练配对生成器 |
| `bridges/multiagent_assembly.py` | 3-facet 多智能体分解框架 |
| `bridges/step_bom_ab_test.py` | A/B 有效性对照实验（可复现） |
| `bridges/step_normalize.py` | GBK→UTF-8 / `\X2\` 归一化 |
| `bridges/ap_detect.py` | AP 版本 + 编码盘点 |
| `AP242_EXPORT_GUIDE.md` | 源头治理指引 |
| `STEP_BOM_SOLUTION_REPORT.md` | 本报告 |

报告/数据产物：`reports/step_bom_scan.{json,md}`、`reports/step_bom_ab_test.json`、
`reports/multiagent_assembly.json`、`reports/multiagent_prompt.txt`、
`reports/step_pairs.json`、`reports/step_normalize.json`、`reports/ap_detect.json`、
`data/step_bom_sft.jsonl`、`data/step_utf8/`、`data/step_x2/`。

---

## 六、使用建议（按杠杆排序）

1. **立刻生效**：在 `virtu_omni` 感知通道前调用 `preprocess_step()`，或直接用
   `cadcam_step_reverse(action="bom")` 工具。零训练、零改模型。
2. **提升上限**：用 `data/step_bom_sft.jsonl` 做 LoRA/继续预训练，让模型自己学会
   从噪声几何抽结构。建议扩样本到全部 `runs/` 下的 STEP 后再训。
3. **语料治理**：跑 `step_normalize.py` 把存量 GBK 转 UTF-8；新导出走 AP242。
4. **别做**：不要把 8000 行原始 STEP 直接塞 prompt；不要指望换 AP 就能省掉预处理。

---

## 七、诚实边界

- A/B 实验为**单模型、单文件、单问题**的对照（n=1 文件），结论方向明确但样本量小；
  正式评估建议扩到 16 文件 × 多问题，并接入 `virtu_eval/provenance.py` 记录
  model/template/判分器哈希（项目测量宪法要求）。
- 位姿矩阵目前取 `origin_mm` 平移 + 单位旋转（该文件 4 个子件均为纯平移）；
  若遇到带旋转的装配，需扩展 `ITEM_DEFINED_TRANSFORMATION` 的轴向量解析。
- `x2` 合规模式下中文名以 `\X2\` 转义串呈现，模型读的是码位而非汉字——
  给 LLM 的语料请用 `utf8` 模式。
- AP242 导出动作需在 CAD 侧人工执行，本次只交付了工具与指引，未改任何导出文件。
