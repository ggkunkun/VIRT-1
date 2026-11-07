# 能力卡与埋缺陷判据（SOLIDWORKS 第一片）· 2026-11-04

## 0. 这份文档回答什么问题

用户问的是「怎样让模型真正理解六大工业软件」。本仓已有的实测否掉了"靠权重"这条路
（LoRA 相对基座无可测增益、在服训练件归因为净负增益，见 `VIRTU_DEPLOY_ARTIFACT_GATE_2026-11-01.md`），
所以这里改换判据：**理解 = 没见过缺陷能检出、能修对、且面对无缺陷设计不乱报**。
本文记录该判据的第一片实现与首轮三臂测量，包含两处由测试逮到的自建错误。

## 1. 机制与复跑

| 文件 | 作用 |
|---|---|
| `virtu_eval/capability_card.py` | 能力卡装载、类型库接地校验、注入渲染（contract / formula 两档） |
| `knowledge_base/six_software/solidworks/capability_cards.json` | 第一张卡集：5 张（草图 / 凸台 / 切除 / 体积回读 / 工程图标注） |
| `virtu_eval/planted_defects.py` | 5 条缺陷 + 无缺陷对照 + 判分 oracle（复用执行器规则） |
| `virtu_eval/run_defect_arm.py` | 三臂测量：`nocard` / `contract` / `formula`，三档指标 + 重复次数 |
| `tests/test_sw_capability_card.py` | 21 项接地与反空变异测试 |

```bash
python virtu_eval/capability_card.py --mode formula     # 期望 api_ok=5/5
python virtu_eval/planted_defects.py                    # 期望 passed=6/6
python -m pytest tests/test_sw_capability_card.py -p no:cacheprovider --basetemp=scratch/pt -q
python virtu_eval/run_defect_arm.py --arm formula --reps 2 --report scratch/defect3_formula.json
```

## 2. grounding：枚举机器产物，不抄文档

类型库的 makepy 产物（`%TEMP%/gen_py/<pyver>/83A33D31-…x0x29x0.py`，**文件名保留 GUID 连字符**）
被 AST 解析为 `{接口: {方法: 参数个数}}` 加 `_prop_map_get_` 的属性名。卡里每条 `IFace::member`
必须命中且 arity 相符，否则静态判死。它当场纠正了三条手写假设：

- `FeatureExtrusion3` / `FeatureCut3` 挂在 **IFeatureManager**（23 / 26 参），不在 `IModelDoc2`；
- `IModelDoc2::FeatureCut3` 另存在 **16 参的 deprecated 短重载**——只按名字命中会放行一个跑不通的调用；
- `Extension` / `FeatureManager` / `SketchManager` 是**属性**，不是方法。

注入策略：**非 `verified-working` 的卡整张丢弃**而不是加标注（工程图标注卡即被丢），
因为把用不了的通道写进上下文等于喂幻觉工具调用。实测 contract 块 2654 字符 / 4 张卡，
formula 块 3184 字符（解析式仅 +530 字符）。

## 3. 缺陷套件与 oracle

oracle 五条规则：`engineering_inequality`（**直接 import 执行器 `scripts/sw_flange_demo.py:82 validate()`**，
裁判与选手不得各有一套物理）、`unit_plausibility`、`dv_sign`、`dv_agreement`、`claim_provenance`。

| 缺陷 | 种的东西 | 期望规则 | 真实修复 |
|---|---|---|---|
| D1_hub_undercut | PCD30/D_bolt8/D_hub30（历史上被拒三次仍逐字复读那组） | engineering_inequality | PCD→40.5 |
| D2_rim_breakout | PCD150 ⇒ 轮缘余量 −4 mm | engineering_inequality | PCD→125 |
| D3_unit_confusion | 倒角单独按英寸（0.0787，其余毫米） | unit_plausibility | chamfer→2.0 |
| D4_cut_adds_material | `bore_cut` 实测 dv 翻正（体积反增） | dv_sign | 换诚实回读 |
| D5_fabricated_volume | 汇报体积 901.8 而任何回读都非此值 | claim_provenance | 原样引用 |

**每条缺陷只种一个违规**，并钉成测试。原 D1 载荷从基线继承了 `D_bore 50 < D_hub 30` 这个计划外违规，
模型正确报告了它却被判漏检——归因就此失效，这是本轮第一个自建错误。

**单位规则的非空变异证明**：`validate()` 的排序/厚度不等式对齐次，但 `rim>=2`、`gap>=1`
是**绝对毫米阈值**——所以"整套按英寸报"会被顺带抓到，量纲规则真正独有的盲区只有
**单字段英寸混入**（0.0787 的倒角满足执行器所有不等式）。两个方向都写进了测试，
一旦执行器将来加了倒角下限就会红。这是本轮第二个自建错误（我原先断言"全部齐次"）。

## 4. 三臂实测（qwen3:8b，temp0，seed1234，num_ctx8192，每格 2 次）

| 臂 | 定位率(缺陷均值) | 修复接受率 | 对照假阳性率 | 修复引入新违规 |
|---|---|---|---|---|
| `nocard` | 0.60 | 0.33 | **1.00** | D1 1.0 / D2 1.0 |
| `contract` | 0.40 | 0.33 | **1.00** | D1 0.5 |
| `formula` | **0.80** | **0.00** | **1.00** | D1 1.0 / D2 1.0 / D3 1.0 |

判决（按证据强度排序）：

1. **对照假阳性在三臂都是 1.00（2/2 复现）**：只要任务是"审计"，它必然宣称有缺陷，
   给不给卡、给公式都一样。⇒ 任何不带无缺陷对照的"检出率"都是噪声。这条已做成硬闸。
2. **公式把参数级定位从 0.0 抬到 1.0**：D1/D2 在 `nocard` 与 `contract` 两臂都 0.0，
   `formula` 两格全中。也就是"不肯算"确实部分成立——把不等量写成它能照抄的形式，它就会去查。
3. **但公式把修复接受率打到 0.0，且 3/3 的参数缺陷改出**新违规**：它找到了问题，
   仍然解不出满足五条耦合不等量的参数集。定位与修复是两种能力，混成一个 pass 就看不见这个分裂。
4. **contract 臂不比裸基座好**（定位 0.40 vs 0.60，其中 D4 由 1.0 掉到 0.0）：
   只讲"怎么动、怎么回读"的契约卡没有增量，n=2 不足以定这个回退方向，但足以否掉"加卡就有用"。
5. **temp0 在本机不保证复现**：同一 prompt（`prompt_eval_count` 完全相同）两轮 CONTROL 答案不同。
   单发判定不可用，故全部指标以命中率报告。

## 5. 下一步

1. **真实回读**：本轮 `steps` 是解析一致的**模拟回读**（报告字段 `readback_origin` 已标注），
   D4/D5 的结论必须在接上 SOLIDWORKS 真回读后才能外推到物理。未动 SW 实例（PID 3944 归属未确认，绝不擅自建模）。
2. **只做了 SOLIDWORKS**：其余五软件的观测面差异极大（VERICUT COM 已判死、SSCNC 无 COM、
   CIMCO 走文件），它们的"理解上限"由观测层而非卡片决定。

原先列在本节的"把求解从模型手里拿走"与"审计提示加先算后判闸"两条已实施，见第 6 节。

## 6. 第二轮改造：先算后判 + 求解外置（离线部分已实测）

针对第 4 节的两条判决（假阳性钉在 1.00、修复接受率 0.0）加装两套机制。

**先算后判闸**：`AUDIT_TASK` 现在要求答案先给出 `computed = {hub_clearance_mm, rim_web_mm, total_volume_mm3}`
再下结论，四量对**所有**案例（含无缺陷对照）一视同仁，因此不构成对特定缺陷的提示。
新增指标 `computed_correct_rate`，以及关键对照 `false_alarm_when_computed`——
它把问题拆开：如果模型算对了数仍然宣称有缺陷，那么"逼它算"就不是压假阳性的杠杆。

**确定性最小修复求解器** `virtu_eval/minimal_repair.py`（纯算术，离线实测）：

| 缺陷 | 可行单字段修复数 | 最省解 | 备注 |
|---|---|---|---|
| D1_hub_undercut | 7 | D_hub 30→20.0（相对改动 33%） | 粗乘性网格曾误报"无解"，实为 PCD=40.5 可行 |
| D2_rim_breakout | **1319** | D_outer 160→172.0（7.5%） | 约束集严重欠定 |
| D3_unit_confusion | 2 | chamfer→0.2（贴量纲下限的退化解） | 另一个可行解 chamfer→**2.0**，`unit_restored=true` |
| D4 / D5 | 0（不适用） | — | 参数本就合规，缺陷在回读/汇报里 |

D3 那一行是本轮最干净的一条证据：**0.2 与 2.0 都满足全部工程约束**，物理无法区分，
"用户本意是整数倒角"属于约定而非不等量。所以求解器返回解集而不是单值，
并把"还原量纲"的那一个显式标出来供选择，绝不让"最省"默认等于"最对"。

**验证者阶段**（模型只判不解）：每个参数缺陷出三类题——
求解器的合法修复（应接受）、把合法值扰动到刚好重新违规的 **near-miss**（应拒绝，专治盖章式"看着没问题"）、
以及 D3 的两套合法解 A/B **双向各出一次**（正确答案是被标记的意图解，恒答 A 的模型会在翻转副本上失分）。

复跑：`python virtu_eval/minimal_repair.py`（期望 D1/D2/D3 applicable=True、near_miss_dirty=True）；
`python virtu_eval/run_defect_arm.py --arm formula --stage verify --reps 2`。
27 项测试全绿，含"求解器不得谎报无解""near-miss 必须真的是脏的""意图对不吃位置偏好"三条新闸。

## 7. 口径声明

- 每格 n=2，方向性证据而非统计结论；第 4 节的"contract 回退"不可当作定论。
- 归因已钉：三臂全部 `served_model=qwen3:8b`（`/api/ps` 起跑前为空，模型由本臂首次调用加载）。
- 计时为单次实测（6.8–27.5 s/调用），非外推；此前"3–9 分钟/臂"的预估外推错了约一个量级。
