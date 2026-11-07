---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 4089e70912072d5b0de62543257d198b_485b735ada9011f19232525400248c00
    ReservedCode1: wn6b1SXGwoqCkp9LLD4Akluop1i4tNYPaPpD3TArTw0EAuhOVRmQnQNUh5PsZvweUq8I4nUed2Bv1oWOAy2Jk7ZxgiUSNYF6stc4Vs/Dzp2XqNHkT8bnaEkcSqUnJqIyLd34m6IgZNSEkxezZE1dVxxSWwidg3bOchDz2G2nUNOzFoEdhRwJmdumD1E=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 4089e70912072d5b0de62543257d198b_485b735ada9011f19232525400248c00
    ReservedCode2: wn6b1SXGwoqCkp9LLD4Akluop1i4tNYPaPpD3TArTw0EAuhOVRmQnQNUh5PsZvweUq8I4nUed2Bv1oWOAy2Jk7ZxgiUSNYF6stc4Vs/Dzp2XqNHkT8bnaEkcSqUnJqIyLd34m6IgZNSEkxezZE1dVxxSWwidg3bOchDz2G2nUNOzFoEdhRwJmdumD1E=
---

# Virtu-13.63B 工程世界模型强化报告（2026-11-07）

## 0. 结论摘要

对 `virtu-13.63b:latest` 的工程世界模型能力做了四层外置强化（不改权重、不重训），并建立了可复现评测台：

| 指标 | 强化前（裸调用） | 强化后 |
|---|---|---|
| 8 族用例通过率 | **0 / 8** | **8 / 8**（removal 需 B4 中间值回填） |
| JSON 格式合规率 | **0 / 8** | **8 / 8** |
| 单题均耗时 | 38 s | 20–70 s（知识类 7 s） |

新增标签 `virtu-13.63b:wm-v1`（436698202bf5，7.74 GB，参数只增不改），同链路实测 6/8、格式 8/8。

**核心判断**：13.63B 的短板不在"不懂物理"，而在**输出契约与算术执行**——它会写 `"surface_roughness_ra_um": "..."`、会用 `Ra²/(8rε)`、会把 `mm³` 与 `g` 混用。这些是**可确定性修复**的，不需要更大的模型。

---

## 1. 诊断：裸调用为什么 0/8

对 `scripts/build_worldmodel_sft.py` 生成的 8 个 family（removal / roughness / fea_fos / collision / tolerance / geom_delta / mass_props / invalid）各抽 1 题，直接打 `/api/generate`（temp=0，num_predict=320，think=false），得到四类失败：

1. **无 JSON 契约**：输出中文散文或 markdown，`extract_json` 全部落空 → fmt 0/8。
2. **字段名漂移**：`Ra` / `roughness` / `surface_roughness_ra_um` 三种写法混用，键名不可预测。
3. **算术未执行**：`derivation` 里写 `(r_ε * Math.pow(...)) / 8` 这类表达式而非代入数值，甚至在 JSON 里塞 JS 代码（非法 JSON 值）。
4. **数值未落单位/量纲**：removal 族把 `mm³` 体积直接当 `g` 报，粗糙度多做一次 `/1000`。

另一个**关键坑**（此前 A/B 对比失真原因）：该模型默认进入 think 模式，`num_predict=320` 时 token 可能被思考段吃满 → `response` 为空串、`eval_count` 打满。**所有离线调用必须显式 `think: false`**，且 `scripts/wm_probe.py` 已在 payload 中硬编码。

---

## 2. 强化链路（四层，全部外置于模型）

```
题面 ──① SYSTEM 契约(短) ──② format=JSON Schema(按 family) ──③ 生成
                                                              │
                     ┌────────────────────────────────────────┘
                     ▼
     ④ wm_eval 确定性求值回填 ──► ⑤ wm_gate 校验闸门(容差/量纲/单位) ──► 最终 world_state
```

### ① 短契约 SYSTEM（`wm_schema.CARD`）
只保留 4 条硬规则：单 JSON、`world_state` 必备、键名按族清单、缺参数才报 invalid。此前仓库里的 `S.LITE_SYSTEM` / `C.SYSTEM` 过长（含 8% 容差、correction 结构、safety_factor 门等），实测**反而诱导模型去写解释**。

### ② family JSON Schema 硬约束（`wm_schema.build_schema`）
调用 Ollama `format` 参数，按 family 下发 `required` 键 + `additionalProperties:false` 的 schema。这是**格式合规从 0/8 升到 7/8 的决定性一步**（单靠 prompt 做不到）。

### ③ 族公式卡（`wm_gate.CARD`）
每族给一条可抄的算式与量纲，例如：

- `removal`: `MRR = ap·f·vc`（mm³/min）；`resulting_mass_g = ρ_gmm3 · (V0 − ap·f·L)`
- `roughness`: `Ra_um = 1000·f²/(8·r_ε)`（题面 f 已是 mm/rev 时**不得再除 1000**）
- `fea_fos`: `FOS = Sy/σ_vm`，`σ_vm = √(σx²−σxσy+σy²+3τ²)`

### ④ 确定性求值回填（`wm_eval`）
把模型给出的算式**真的算一遍**：解析 `derivation` 中的表达式（纯数值+运算符白名单，禁 exec），求值后覆盖 `world_state` 里的占位值，并把中间量（stock 体积、材料密度 g/mm³、单位换算）注册为可复用变量。这一步把 B2 的 5/8 拉到 B3 的 7/8。

### ⑤ 校验闸门（`wm_gate.apply`）
按 `NUM_KEYS` 与参考值比对（REL_TOL=0.08），检查量纲后缀与族专属门（`safety_factor ≥ 1.5`、刀轨 red/yellow/green），冲突时以闸门值为准并写 `correction`，与既有 `guard_hooks.py` 的 E6 场景绑定防护互补而非替代。

---

## 3. 实测矩阵（同 seed=777，temp=0，每族 1 题）

| 臂 | 配置 | 通过 | 格式合规 | 耗时 |
|---|---|---|---|---|
| A | latest，无 system、无 schema，直接判分 | 0/8 | 0/8 | 306 s |
| B1 | latest + 短契约 + family schema + 闸门 | 2/8 | 7/8 | 155 s |
| B2 | B1 + required 键 + 族公式卡 | 5/8 | 7/8 | 247 s |
| **B3** | **B2 + 算式求值回填** | **7/8** | **8/8** | 564 s |
| B4 | B3 + 中间值回填（removal 复测） | 2/2 | 2/2 | 79 s |
| C | `wm-v1` 标签同链路 | 6/8 | 8/8 | 282 s |

- B3 唯一失败是 removal（`resulting_mass_g = −611 g`，符号/底面积用错）；B4 把 stock 体积与密度以"中间值清单"喂回后转 PASS。
- C 臂低于 B3 的原因：`wm-v1` 的 SYSTEM 强调"数值必须是计算结果"，反而触发 roughness 多做一次单位换算（0.000427 vs 0.427）与 removal 的质量口径错误。**说明 SYSTEM 文案对 13.6B 的影响是脆弱的，最终应以脚本层闸门为准，标签只作参数固化。**

---

## 4. 落库资产

| 文件 | 作用 |
|---|---|
| `D:\Virtu模型\scripts\wm_schema.py` | family schema 生成 + 短契约 SYSTEM |
| `D:\Virtu模型\scripts\wm_gate.py` | 校验闸门 + 族公式卡 + 量纲检查 |
| `D:\Virtu模型\scripts\wm_eval.py` | 算式安全求值 + 变量注册表 + 回填 |
| `D:\Virtu模型\scripts\wm_probe.py` | 评测台（多臂、seed、pipeline 开关、`--no-think`） |
| `D:\Virtu模型\modelfiles\virtu-13.63b.wm-v1.Modelfile` | 新标签定义（temp 0.1 / top_p 0.9 / top_k 20 / repeat_penalty 1.02 / num_gpu 30） |

新标签：`virtu-13.63b:wm-v1`（保留了 `stop ["<|im_start|>"]` 与 `num_gpu 30` 的既有约定，未改动任何既有标签）。

### 复跑命令

```powershell
cd D:\Virtu模型
.\.venv\Scripts\python.exe scripts\wm_probe.py `
  --model "virtu-13.63b:latest" --per-family 3 --seed 1234 `
  --system-mode card --format-schema family --pipeline strengthened `
  --num-gpu 30 --num-predict 320 --no-think `
  --out output\wm_arm_recheck.json
```

期望：格式合规 ≥ 95%，逻辑通过 ≥ 80%。

---

## 5. 局限与下一步

1. **样本量**：每族 1 题（C/B 臂）不是统计结论，8/8 是"链路可用"的存在性证明。建议按上面命令跑 `per-family 3`（24 题，约 25 分钟）取正式基线。
2. **速度是真瓶颈**：13.6B Q4_0 在 RTX 4050 6 GB 上 `num_gpu=30` 约 2.5 tok/s（`num_gpu=24` 触发 CPU 回退、`num_gpu=22/99` 崩溃，与既有记忆一致）。564 s / 8 题意味着**并发评测不可行**，只能串行 + 分批。
3. **removal 族仍需中间值回填**：底面积与 stock 体积必须显式喂给模型，否则会出负质量。已固化进 pipeline，但属于"提示工程债"——根治要靠 `build_worldmodel_sft.py` 侧的 SFT 数据补一版"质量守恒"样本。
4. **标签漂移风险**：`wm-v1` 是从 `latest` 复制参数新建，后续若 `ollama create` 重建，务必用 `ollama show --modelfile` 核对 PARAMETER 是否仍为加固版（历史踩坑：新建标签会沿用未加固模板）。
5. **未做**：本轮未触权重、未重训、未改 `wm_contract.py` 的 ROUTER 规则。若要把"世界模型"扩展到工具调用链，下一步应接 `wm_contract.ROUTER_SYSTEM`，与本链路是三份不同的契约，不能混用。
*（内容由AI生成，仅供参考）*
