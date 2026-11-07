# 物理判分口径迁移：从「文本含不含那个数」到「求解器复不复算得出」

日期：2026-11-04　范围：`virtu_eval/`（判分器）、`scripts/wm_verifier.py`（求解器）、新维度 `physics`

---

## 1. 先记账：旧判分链路测的是什么

`virtu_eval/graders.py` 原有 19 个判据，签名一律是 `(response: str, criterion: dict)`：

```
numeric_near  ->  从响应文本里抽数，与 criterion.value（作者手填）比容差
literal_*     ->  子串在/不在
json_object   ->  键在不在
python_parses ->  ast.parse 能否过（语法，从不执行）
gcode_structure ->  程序头/坐标字/进给/M30 齐不齐（正则，从不回读刀路）
```

**没有任何一条把产物交给求解器。** 连 `audit_case_arithmetic.py` 也只是复核作者写的推导链是否
自洽，不复算物理。所以旧分数衡量的是「模型能否产出一段含正确数字的文本」。
~~这正是此前 virtu-toolcall 病症的奖励来源~~ —— **此句已被 §7.3 的真实数据审计推翻，见该节。**

判据**不完备**（下面是构造变异体，证明判据本身不健全；真实响应上是否发作见 §7.3）：

| 构造变异 | 旧判分 | 机理 |
|---|---|---|
| 题面给的密度 `7.85` 出现在响应里，计算质量错 1000 倍 | 100 分 | `numeric_near` 只找「任一数落在容差内」，不绑定物理量 |
| `delta_volume_mm3` 取正号 | 100 分 | `numeric_near(value=1000)` 不辨符号 |
| 只答对一半字段、其余闭口不提 | 可满分 | 判据按字段独立加权，漏写不扣分 |

## 2. 落地机制

```
                        virtu_eval/graders.py
  响应文本 ──parse──> world_state ──┬──> physics_invariant   (L1 自洽：ΔV<0 / after=before+ΔV
                                    │                            / 正值边界 / 量纲上限 60 g/cm3)
                                    └──> world_state_verified(L2 复算：逐字段与 recompute 比对)
                                                  │
                       scripts/wm_verifier.py <───┘   ← 运行时桥用的同一个求解器（裁判=选手）
                          recompute(scenario) -> reference{field: value}
```

判分器直接 `import` 求解器本体（`importlib` 按文件路径懒加载），与
`planted_defects.py` 复用执行器 `validate()` 是同一条纪律：**不允许裁判一套物理、选手另一套物理。**

反真空闸（三条，都会红给你看）：

- 未知 `task` ⇒ `solver_returned_no_reference`，不判通过；
- criterion 缺 `scenario` ⇒ `criterion_scenario_missing`；
- 模型漏写参照字段 ⇒ `vacuous: ... unasserted=[...]`；默认要求**全部可比字段**都交代
  （运行时 `REQUIRED` 子集只 3/5 个，那是宽松的执行侧口径，不能当评测尺子）；
- 参照里 `centroid_mm` 这类列表值 `_cmp_numeric` 不比对 ⇒ 显式记 `ungraded_composite`，不冒充已验。

容差是显式旋钮：`tol_rel` 按难度 easy 0.08 / medium 0.03 / hard 0.01，覆盖求解器运行时默认 8%。
运行时容差不再悄悄成为评测容差。

## 3. gold 变成派生的

`scripts/build_physics_acceptance_cases.py` 生成 `data/benchmark/virtu_eval_phys_v1/physics.jsonl`
（30 条，9 easy / 15 medium / 6 hard，10 个 task family）。`gold.answer` =
`wm_verifier.recompute(scenario)` 原样输出，作者手填的数会被 `validate_cases.py` 的
`gold_scores_*` 直接拒收。

这条规则第一次跑就逮到我自己的两处错（不是模型错，是我建集错）：

1. **`geom_delta` 体积守恒判红**：`wm_verifier.l1_check` 用绝对 `1e-3` 判 `after == before + ΔV`，
   与契约要求的「保留 3–4 位有效数字」直接冲突（`25000 − 1571 ≠ 23430`）。运行时也会误杀合法舍入，
   已改为随量级放的相对松弛 `1e-3 + 1e-3·max(|before|,|after|,|ΔV|)`，真守恒破坏仍是数量级偏差。
2. **`must_compare` 写了不可比字段** `centroid_mm` ⇒ 用例对自己不可满足。生成器现在只列可比字段。

另外题面单位一律写死（`rho=0.00785 g/mm3`），不写就是在制造 1000 倍量纲陷阱而不是考物理。
模板取值刻意跨决策边界：autodiff 红/黄/绿三档齐、FOS 在 1.5 闸门两侧、需求转速在机床上限两侧。

## 4. 一次判分 = 一份语料

`python -m virtu_eval.export_physics_triples <run_dir>` 把落盘 `raw.jsonl` 导出
`(intent, prediction, reference, fields[{field,pred,ref,rel_err}], verified, tol_rel)`。
`verified` 标签**直接调用判分器**取，不重实现一遍判据，所以语料与尺子不可能漂移。
这是「带物理后果的三元组」的数据源；训练侧用法见 §6 未做项。

## 5. 复现命令与实测结果

```bash
python -m py_compile virtu_eval/graders.py virtu_eval/export_physics_triples.py \
    scripts/build_physics_acceptance_cases.py                    # COMPILE_OK
python scripts/wm_verifier.py --selftest                         # [selftest] ALL PASS
python scripts/build_physics_acceptance_cases.py                 # [ok] 30 cases tiers={'easy':9,'medium':15,'hard':6}
python -m virtu_eval.validate_cases data/benchmark/virtu_eval_phys_v1   # VALID: 30 cases, all gold score 100
python -m pytest tests/test_solver_graders.py -p no:cacheprovider --basetemp=scratch/pt -q       # 14 passed
python -m pytest tests/test_physics_case_set.py -p no:cacheprovider --basetemp=scratch/pt -q     # 124 passed
python -m pytest tests/test_solver_graders.py tests/test_physics_case_set.py \
    tests/test_eval_runner.py tests/test_eval_ruler.py tests/test_arithmetic_guard.py \
    -p no:cacheprovider --basetemp=scratch/pt -q                  # 168 passed（含既有评测回归）
```

14 + 124 = 138 条新增断言里，「每个 gold 逐字段复算一致」「任一被评分字段 +25% 必须掉分」
「闸门判定（autodiff/gouge/within_limit）翻转必须掉红」「散文式复述 0 分」「未知 task 不假绿」
都是对判分器本身的攻击测试，不是对模型的——尺子的性质先跑出来，才有资格给模型出分。

## 6. 两臂实分（2026-11-04，`physics` v3 集 30 条，temperature=0，seed=1234）

v3 = v1 去掉 `mass_props`（§7.1）+ 补全 `removal` 推导链（§7.2）后的干净集。

| 指标 | `virtu-ties-v1` | 基座 `qwen3:8b` | Δ |
|---|---|---|---|
| 维度均分 | 53.3 | 55.3 | **−2.0（训练件更差）** |
| 满分用例 | 7 | 9 | −2 |
| **求解器复算通过** | **7/30** | **9/30** | **−2** |
| L1 守恒/量纲通过 | **29/30** | 26/30 | **+3（训练件更守约束）** |
| JSON 形态 | 30/30 | 30/30 | 0 |
| 失败分类 | mismatch 22 / L1 1 | mismatch 17 / L1 4 | — |
| 响应多样性 | 30/30 互不重复、0 空 | 同 | — |
| 单条中位延迟 | 3.0 s 级（14.6 tok/s） | 4.3 s 级（10.0 tok/s） | 实测，权重部分卸载 |
| 旧尺/新尺分差 | 55.2 / 53.3（+1.9） | 57.0 / 55.3（+1.7） | 「旧满分而新判红」0 例 |

分族 Δ（ties−base）：`geom_delta −40`、`collision −20`、`removal +20`、其余 0。
合起来是一句很具体的话：**这套 LoRA 学会了"守格式与守恒符号"（L1 +3），没学会"算对数"（复算 −2）**。
方向与既有归因 [[virtu-serving-identity-and-artifact-gates]]「训练净负增益」同向。

真实错误签名（103 个超差字段，两臂合计；解析式已逐条复核，参照是对的）：

- `n=1000·Vc/(π·D)`：ties 答 `120000` ⇒ 只算分子、`π·D` 整个丢掉（比值恰为 π·D=50.27）；base 答恰好一半 ⇒ 半径/直径混用。
- `removal` 族即使题面明写「去除体积=doc·woc·L」，两臂仍把 `stock_vol`（毛坯）当去除体积答
  （m02 base=450000、m01 两臂=100000）；base 另在 2 条上给出**负质量**（`removed_mass_g=-785`、`-302.4`），
  物理不可能，被 L1 正值闸拦下。
- `design`：ties 的 `volume=1.45e6` 与自己写的 `mass=113 g` 互相矛盾（按 ρ 应为 11382 g）——
  自相矛盾被逐字段复算同时抓住，这是文本尺结构上做不到的判据。
- 本轮 `removal` 补全推导链后，1000× 量纲错从 v2 的 1 例降到 **0 例**，说明那类错部分可由题面单位歧义诱发。


## 7. 三条自我更正（都跑在真实产物上）

**7.1 `mass_props` 是尺子的缺陷，不是模型的错——已把该族摘出验收集。**
`mass_props_csg` 返回 `V·(h²+w²)/12`＝4.8e7，单位实为 **mm⁵**，字段却叫 `inertia_ixx_mm4`；
mm⁴ 的解析值是 `w·h³/12`＝4.0e4，差 1200 倍。同一表达式在 `scripts/distill_local_solver.py:180`、
`scripts/build_worldmodel_sft.py:267`、`scripts/wm_verifier.py:112` 三处同源。
**未证实的一半**：本地 `data/*.jsonl` 里 grep 不到 `inertia_ixx_mm4`，所以"已训语料也在教这个错标"
这句我只标为未证实，不当结论用。改 `mass_props_csg` 本体会动到既有训练靶值，不在本轮擅自做。

**7.2 `removal` 族 v1/v2 的 20/100 里有一半是我的题面缺推导——已补全并重跑。**
`resulting_mass_g` 的推法（`stock_vol × rho − removed_mass`）我原先没给，`stock_vol` 却明文在场。
补全推导链后（v3）：ties 20→40、base 仍 20，族差从 0 翻成 `ties +20`；但「拿毛坯体积当去除体积」在两臂
依旧发生，所以该族的结论方向不变，只是幅度不再被我的题面污染。**教训：给小模型出物理题，单位与推导链
必须显式写全，否则测的是题意猜测不是物理。**

**7.3 「旧尺子虚高、是抄示例值病症的根因」这句被真实数据否证。**
我把 8 个历史 run 的 **1228 条真实记录**重扫了一遍（`scratch/audit_old_ruler_echo.py`）：
551 条 `numeric_near` 判据、270 条通过，其中目标值同时出现在题面里的只有 17 条，
而**这 17 条同时也出现在 gold 里**（答案本来就等于某个输入）⇒ **不歧义的漏判 0 条**。
再在同一批 physics 响应上并排两种尺子（旧尺子按"每个 gold 字段一条 `numeric_near`"从宽构造）：
ties 旧 52.5 / 新 50.7（+1.8），base 旧 57.0 / 新 55.3（+1.7），
**「旧尺满分而新尺判红」的用例 0 条**。
所以 §1 那张表是判据**不健全性**的合成证明，不是历史分数被抬高的证据；短 JSON 回答上两种尺子几乎重合。
迁移的实际价值落在别处：gold 不能再被作者写错（已两次当场拒收我的手写 gold）、
完整性/符号/量纲独立成闸、产出逐字段 `rel_err` 三元组、
并且**只有它能发现本仓求解器自己的 mm⁴/mm⁵ 错标**。

## 8. 第二段：把"懂不懂物理"和"会不会乘法"拆成两个数（同日晚）

复算尺只给一个分数（7/30），它无法回答"是不知道定律，还是知道定律算错数"。于是加了第三层：

```
模型 ──derivation{field: 代入算式}──> virtu_eval/derivation.py 定律登记表
                                            │ 用题面数值现算（eval_expr，与 gold 推导链同一解析器）
                                            ├─ 定律+绑定分 = 算式复算是否等于 recompute 参照
                                            └─ 算术分     = 它自报 world_state 数字是否等于参照
   登记表 ⇔ wm_verifier.recompute 逐字段等价：tests/test_derivation_registry.py（10 族 × 30 用例
   × 6 组扰动输入，>150 次比对，差于 1e-6 即红）——这就是"裁判与选手同一套物理"的锁
```

契约随之增补 F 条（`scripts/wm_contract.py`）：`world_state` 每个数值字段必须在顶层 `derivation`
给出代入算式，算式里只准出现题面数值、定律自身常数、本题已算出的中间量；**乘积由校验器现算**。
两条 few-shot 同步改写（格式竞争曾导致 0/21，示例与铁律不一致就是制造下一次格式竞争）。

### 8.1 两臂实测（derivation 维 30 条，temperature=0，`_eval_der_*`；离线重评，未重跑物理）

| | `virtu-ties-v1` | 基座 `qwen3:8b` |
|---|---|---|
| 定律+绑定通过 | **17/30** | **12/30** |
| 数字通过 | 8/30 | 5/30 |
| 定律对·数错（`law_only`） | **10/30** | **8/30** |
| 数对·定律不可追溯（`num_only`） | 1/30 | 1/30 |
| 两头都错 | 12/30 | 17/30 |

**假设成立且被量化：约三分之一的题（ties 10/30、base 8/30）模型给出正确定律与正确绑定，却把乘积算错。**
但它不是全部：`neither` 仍是最大格（12–17/30），所以"只会背定律不会算"不能替代"整体物理仍弱"。

关于 LoRA 的方向要**两面都报**，因为两把尺给出相反符号、而 n=30 的噪声带就有 ±2：
数-only 尺子 ties 7 vs base 9（−2）；定律先行尺子 ties 8 vs base 5（+3）。
**唯一稳的差别是定律/绑定选择 17 vs 12**，算术两侧都没有可检出的增益。

### 8.2 这一段里我自己的两处判分器假阴性（都是两臂同征状 ⇒ 尺子错，不是模型错）

1. **允许字面量集太窄**：只放行了"该字段 gold 式里的数字"，于是把等价展开
   （`(2)*(5)*(100)*(0.00785)` 代替 `(1000)*(0.00785)`）判成编造，`2.0` 被误报 37 次。
   修：允许集 = 本题所有登记式的字面量 ∪ 题面全部标量输入 ∪ π。严格集下 law pass 12/9，校准后 17/12。
2. **不许引用自己算出的中间量**：两臂都写过 `after="(25000)+(-1571)"`，紧接着自己的
   `delta_volume_mm3=-1571`——契约 F 明文允许"本题已算出的中间量"，判分器却在罚它。
   修：把模型自己各字段的算式值与已报数值并入允许集；**错中间量照样判红**（它改变后式取值），
   这条由 `test_a_self_consistent_but_wrong_chain_still_fails` 钉住，防止放行变成逃生门。
3. 顺带：字面量正则不取符号，比对一律按绝对值；符号错误交给值比对，不靠字面量抓。

### 8.3 语料与训练（脚本就绪，**未训练、未花 ¥**）

模型自身输出做语料不成立（30 条里只有 7–9 条物理正确），改成正向生成：
`scripts/build_physics_derivation_corpus.py` 采样合法参数 → `derivation=登记表` + `world_state=recompute`，
一行入库要同时过三闸：①登记表==求解器（**17/3000 抽样造出负体积法兰，被 `V=max(V,1)` 静默夹成 1.0mm³
——正是这条闸把它挡下，生成期拒收 13 条**）② shipped 判分器满分 ③与评测场景不近重复（拒 1 条）。
产物 `data/physics_derivation_v1/`（2400 行、12.68MB、sha256=`9370e8315f41a02d…`、MANIFEST 记拒收数）。

训练入口 `scripts/launch_physics_derivation_train.py --stage/--preflight/--verify-receipt`
**指向 `scripts/train_virtu_v100.py` 而不是 `cloud_train_pack/train_turnkey.py`**：
后者在 `--data` 解析不到时静默回退旧语料（:245-255），前者 `_data_files` 对 manifest sha 不匹配直接 FATAL。
preflight 实测拦到一条硬约束：**语料 est p95=2091 token > 训练器默认 max_len 2048 ⇒ 标签会被截断**，
所以档位写死 `--max-len 3072`。成本按实测锚点外推：V100 3 epoch ≈2.3 h ≈¥4.6，225 步。

## 9. 还没做

- 历史 8 维综合分不受影响（`DIM_WEIGHTS` 未动，`physics`/`derivation` 独立成维未折权）；折进综合分要重定权重+重建基线。
- 改 `graders.py` 会使既有 run 目录的 `manifest.harness_source_sha256` 失配、runner **拒绝续跑**——刻意如此。
- **训练没跑**：语料与启动器就绪，租卡与开训需要用户决定（本机零 GPU 花费）。
- `wm_verifier` 里两处参照缺陷只做了"摘出/记账"，没有动本体（会改既有训练靶值）：
  `mass_props_csg` 的 mm⁵ 错标为 mm⁴（三处同源）、`design` 的 `max(V, 1.0)` 静默夹紧。
- `fea_fos` 参照里没有 `fos_gate`（1.5 闸门判定不进参照），derivation 维目前也不判谓词字段。
- 契约与运行时的漂移：`virtu_real_backend.py:244` 自带一份主轴转速公式，与登记表/求解器不同源，
  应当改为走 `derivation.LAWS`；本轮未动。
- `_cmp_numeric` 对 bool/str 是精确相等，`autodiff` 拼错即判红——想要的行为，但要知道。
- 时长口径更正：单条冷探针推的 35–40 分钟 ETA 是**错的**，实测单条中位 3.0 s / 4.3 s。

  （单条中位 3.0 s / 4.3 s，14.6 与 10.0 tok/s）。单次探针不配当 ETA。

