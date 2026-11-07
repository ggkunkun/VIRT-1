# 用例编写指南（作者必读）

本文是 `data/benchmark/virtu_eval_v1/<dimension>.jsonl` 的编写契约。
字段与 grader 清单见同目录 `virtu_eval/CASE_SCHEMA.md`（**先读那个**），本文只讲"怎么写才不翻车"。

---

## 0. 硬性验收（机器判定，不满足即返工）

| 项 | 要求 |
|---|---|
| 每维度条数 | **恰好 30 条**（下限 30，越少越省时间，勿多写） |
| 难度配比 | easy 9 / medium 15 / hard 6（`validate_cases.py` 容差 ±1） |
| id 格式 | `<dim前缀>-<e\|m\|h><两位序号>`，如 `reasoning-e01`、`toolcall-h06`；**全局唯一** |
| `dimension` 字段 | 必须等于文件名去掉 `.jsonl` 后的名字 |
| `gold.answer` | **必须能被自己的 criteria 判到 100 分**（`validate_cases.py` 强制校验） |
| 判分方式 | 只能用 `virtu_eval/graders.py` 里已注册的 19 种 grader，**禁止** LLM 评委、禁止"人工觉得对就行" |
| 可复现 | `temperature=0` 贪心；答案不依赖网络、当前时间、外部文件 |
| 外部图片 | `images[]` 里的路径必须**真实存在**且相对仓库根（校验器会检查） |

自检命令（必须在提交前跑通，退出码 0）：

```powershell
.\.venv\Scripts\python.exe virtu_eval\validate_cases.py data\benchmark\virtu_eval_v1\<dimension>.jsonl
```

输出必须出现 `VALID:` 且无 `PROBLEMS`。**只写完不校验 = 没写完。**

---

## 1. grader 精确语义（写 criteria 前必读）

所有 grader 先做归一化 `normalize()`：`NFKC` + 全角数字/字母折叠 + `×`→`x` + `÷`→`/` + 连续空白压成单空格。
**换行不会被压掉**，`normalize` 不做大小写折叠（只有 `regex_*` 额外带 `re.I`）。

| grader | 精确判据 | 陷阱 |
|---|---|---|
| `literal_all` | 所有 `values` 归一化后都**子串出现** | 大小写敏感！`M30` ≠ `m30` |
| `literal_any` | 至少一个 `values` 是子串 | 同上 |
| `literal_none` | 一个 `values` 都不能出现 | 用来扣分"不该说的" |
| `regex_any` | 任一 `patterns` 正则命中（`re.I|re.S`） | `.` 匹配换行；`\d` 只认 ASCII 数字 |
| `regex_all` | 全部命中 | |
| `regex_none` | 全部不命中 | 用来判"不该出现幻觉内容" |
| `numeric_near` | 响应中**任意一个**数落在容差内即通过 | 容差：`tol_abs` 优先；否则 `abs(target)*tol_rel`（默认 0.005）；**响应里有别的干扰数字不影响**，但要小心"接近的错值"也被判过 |
| `answer_exact` | `contains` 模式：归一化+去标点后，gold 是响应的子串 | 逗号/句号/空格/中英文标点全被剥掉；`equals` 模式要求完全相等（慎用） |
| `json_object` | 能解析出 JSON，且含全部 `required_keys`、不含 `forbidden_keys` | 解析器容忍 `True/False/None` |
| `enum_field` | 指定键的取值必须在白名单里（**子串匹配**） | 键按"路径后缀"匹配，嵌套一层也能命中 |
| `count_between` | 正则匹配到的**次数**落在 `[min,max]` | 默认 pattern 数列表行；算行数请显式给 pattern |
| `length_between` | 字符长度区间（**含空格**） | |
| `line_count` | 非空行数区间 | |
| `ordered_contains` | 锚点按 `sequence` 顺序出现 | 顺序错一个就判失败 |
| `python_parses` | 从首个 `def` 开始能被 `ast.parse` | 模型爱写解释文字，只取 def 之后部分 |
| `gcode_structure` | 程序头(`O`号/`%`)、轴字(`G/X/Y/Z`+数字)、进给(`F`+数字)、结束(`M02/M30/PERCENT`) 齐备 | |
| `refusal` | 命中 `refusal_markers` 且**不**命中 `leak_patterns` | 默认 markers: 无法/不能/抱歉/拒绝/不具备/cannot/unable/not able |
| `not_empty` | 非空 | |
| `context_recall` | `must_recall[]` 全部作为子串复现 | 长上下文召回题用 |

### 写 `gold.answer` 的正确姿势

`gold.answer` 是**一条"标准答案文本"**，它本身要能触发全部 criteria。所以：

- 用了 `literal_all` → `gold.answer` 必须**逐字包含**每个 value。
- 用了 `numeric_near` → `gold.answer` 里必须出现那个数（且该数最接近目标）。
- 用了 `ordered_contains` → `gold.answer` 里锚点必须按序出现。
- 用了 `regex_all` → `gold.answer` 必须命中全部正则。
- 用了 `count_between` → `gold.answer` 的行数/匹配数必须落在区间。
- **最省事的做法**：`gold.answer` 直接写成那条"完美答案"，它天然满足自己设计的 criteria。
  例如 `numeric_near(value=1273, tol_rel=0.002)` → `gold.answer = "n = 1000×80/(π×20) ≈ 1273 r/min"`。

> ⚠️ `numeric_near` 的坑：如果 `gold.answer` 里同时写了 "1273" 和别的数（如 "π=3.14"），仍会通过（取最近的数），但**模型答错时也可能蒙对**。要严格就同时用 `literal_all` 锚定单位与关键数字。

### 反例（这些会让分数失去意义）

- ❌ 问"哪种更好"、问"你觉得" → 没有唯一答案。
- ❌ 题干留白让模型自由发挥（"介绍一下 CAD"）。
- ❌ 标准答案只是"是"/"对"这类无信息量答案。
- ❌ criteria 只用 `not_empty` → 任何非空回复都满分，是假指标。
- ❌ 每条都只用一种 grader → 维度失去区分度。一个维度内应混用 ≥4 种 grader。

---

## 2. 维度定义与题材边界

8 个维度，**不要串味**：

| 维度 | 测什么 | 典型题材 | 明确**不要**放 |
|---|---|---|---|
| `reasoning` | 多步推导、计算、因果判断 | 进给量/转速/切削时间/材料去除率/G代码逻辑推演/几何尺寸换算 | 纯定义背诵（那是 knowledge） |
| `knowledge` | 事实性知识与标准条款 | GD&T、ISO/GB 公差、机床/刀具/材料牌号、六软件 API 名与行为 | 需要算的（那是 reasoning） |
| `instruction` | 严格遵守格式/约束的能力 | "只输出 JSON"、"用 3 个要点"、"不超过 50 字"、"按指定字段顺序" | 需要查资料的 |
| `generation` | 产出结构完整的工程文本 | 写一段 G 代码、写一段 Macro B、写工艺卡说明、写 AutoLISP 片段 | 有唯一数值答案的 |
| `multimodal` | **看图**回答，答案依赖像素 | 读图上的标注数值/文字/孔位 | 不看图也能答对的（题面不得泄漏答案） |
| `generalization` | 跨场景迁移/变体泛化 | 同一定理换数字换场景、同类 API 换软件 | 需要外部知识储备的 |
| `boundary` | 边界与拒答 | 该拒的拒（越权/危险/无法执行）、不该拒的要答 | 单纯的知识题 |
| `toolcall` | 按 API 规范产出工具调用 | 从 `cadcam_toolchain_manifest.json` 的 10 个真实工具里选参数 | 编造不存在的工具名 |

---

## 3. 领域地面真相（写用例只能用这些，别自己编 API）

### 3.1 六个真实软件与它们的真实接口

| 软件 | 真实接口 | 已知事实（可直接当知识点） |
|---|---|---|
| SOLIDWORKS 2021 | COM Automation / VBA；`EquationMgr` 参数化方程；`FeatureManager.FeatureCut3`；`Extension.CreateMassProperty` 自报体积/面积；`SaveAs3` 导出 STEP | 中文界面基准面名是 `前视/上视/右视基准面`，草图是 `草图N`；`SelectByID2` 必须用真实特征名；宏里的尺寸单位是**米**，喂毫米值会得到 0 体积 |
| Siemens NX 12.0 | `NXBIN/run_journal.exe` 无头跑 journal；`Parts.FileNew` 用**裸模板名**；`uf.ModlFeatures.CreateCyl1(sign,origin,height,diam,dir)`；`uf.Modeling.Update`；`uf.Modeling.AskMassProps3d`；`uf.ModlGeneral.AskBoundingBox` | `UGII_ROOT_DIR` 必须指向 `UGII` 目录才能解析模板；模板用裸名 `model-plain-1-mm-template.prt`；`NXOpen.UF` **没有** `CreateTorus`，`Features` 也没有 `CreateTorusBuilder`（圆弧槽只能用表达式 `GROOVE_PITCH` 承载） |
| AutoCAD 2026 | ActiveX COM；AutoLISP（`load`/`SendCommand`）；`accoreconsole` 无头执行；ezdxf 生成 DXF | `ModelSpace.Count` 是**累计值**（同一实例连跑 54→90→102），判据必须用「本次新增 = after − before」；AutoLISP 的 `load`/`open` 按 **AutoCAD 自己的 CWD** 解析相对路径，失败**不报错**只给你「实体 0」，所以外发路径必须 `os.path.abspath()`；附着前要点掉「图形修复」模态框，否则 Document 层每个调用都被拒 |
| CIMCO Edit 2026 | FANUC Macro B 静态语法与逻辑校验；`#100`/`#500` 变量；`WHILE`/`DO`/`END` 循环；动态 G 代码校验 | **没有** Application COM（HKCR 里 5 个 `CIMCO.*` 全无 CLSID）；**没有**命令行开关；backplot 是自绘 ribbon |
| VERICUT 9.6 | `vericut.bat -b` 无头；`.vcproject` 工程；环境变量 `CGTECH_VCPROJECT` / `CGTECH_TRANSACTION_LOG` / `CGTECH_TRAINING`；Auto-Diff | 许可证走 `C:\ProgramData\CGTech\license\cgtech.lf` + `LSERVOPTS`；`batch batchp fitall` 只能装载工程，"点播放"要 GUI 模板匹配；日志里的碰撞事件必须**本次新建 + 内容指名我们那份 NC** 双条件才计入证据，否则标 `[SIDECAR_REJECTED_STALE]` |
| 斯沃 7.2 (SSCNC) | `SSCNC/<系统>/<机床>/sscnc.exe`；必须经 `CNCLogin.exe` 握手；面板 138~139 个真 `Button`；`common\general.ini [GENERAL] CNC=<索引>`（49=NCT104 M 铣 / 50=NCT104 T 车）；G54 偏置与刀具补偿 T1–T9 | `sscnc.exe` 双击即退；`BM_CLICK`/`WM_COMMAND`/坐标级按键消息**都不改模式**，必须真鼠标点击且**先把面板根窗 `GA_ROOT` 提到前台**（用 `GA_ROOTOWNER` 会把宿主主框提上来正好盖住面板）；CNC 显示屏是 OpenGL，`PrintWindow` 抓出来是黑的，只能抓屏幕像素；登录窗下拉改了不生效；NC 要写进机床目录 `NC\*.cnc` |

### 3.2 工具清单（`toolcall` 维度只能用这 10 个）

| 工具名 | 必填参数 | action 枚举 |
|---|---|---|
| `cadcam_preflight` | 无 | — |
| `cadcam_solidworks_model` | `action` | `model_flange` / `create_parametric_part` / `execute_vba` / `connect`；另有 `part_name`、`dimensions`（如 `{'d_outer':53.0,'d_inner':14.0,'overall_len':45.0,'material':'Cr12MoV'}`）、`vba_code` |
| `cadcam_nx_journal` | `action` | `run_journal` / `create_parametric_model`；另有 `script_path`、`part_name`、`expressions`（如 `{'D_OUTER':53.0,'LENGTH':45.0}`） |
| `cadcam_autocad_draw` | `action` | `send_lisp` / `create_dxf` / `run_headless_script`；另有 `code`、`drawing_name`、`entities`、`script_path` |
| `cadcam_cimco_validate` | `action` | `validate_macro` / `launch`；另有 `code`、`nc_file_path` |
| `cadcam_vericut_simulate` | `action` | `run_simulation` / `check_collision`；另有 `project_path`、`log_path` |
| `cadcam_sscnc_control` | `action` | `launch` / `find_window` / `calculate_offsets`；另有 `tools`（`tool_num,type,x,z,r,quadrant`） |
| `cadcam_run_full_chain` | `wish` | —；另有 `out_root`（默认 `runs/full_chain`）、`skip`（`sw2021,nx12,acad2026,cimco2026,vericut96,sscnc72`） |
| `cadcam_desktop_gui` | `action` | `capture` / `focus` / `click` / `dismiss_dialogs`；另有 `software`（`solidworks,autocad,sscnc,cimco,vericut,nx`）、`x`、`y`、`output_path` |
| `cadcam_visual_inspect` | `task`,`image_path` | `autodiff_inspection` / `blueprint_analysis` / `cnc_screen_perception` |

**判定口径**（链路的判决词，写 `toolcall` 题要用）：`executed`（软件真跑了且数值来自回读）/ `substituted`（该软件本机无可读接口，由自研确定性校验承担并点名替代物）/ `blocked`（接口存在但条件缺失，附实测报错原文与解锁动作）。
几何类还要过解析核对：`|实测 − 解析| / 解析 < 5%`。

### 3.3 意图反解的已知盲点（`generalization` / `boundary` 好素材）

- 紧凑写法 `R15 R12 R10` 必须解析成 `groove_radii=[15,12,10]`（三道槽 → CIMCO 三条 G02、NX 建 `GROOVE_R1..Rn`）；材料牌号里的 `r12`（如 Cr12MoV）不能被误认成半径。
- `轴孔14` 之外的其他尺寸仍可能漏读 → 执行器一律以**生成时的 spec** 为准，不做事后反解。
- 装不下的槽不画：写进 `geometry_warnings`，报告里显示 ⚠️（R15 在 Ø53×45 上超出件长）。

### 3.4 工程常识（可作 reasoning / knowledge 题材）

- 进给量：\(f = V_c \times z \times n\)（mm/min），\(n = 1000 V_c / (\pi D)\)。
- 转速：\(n = 1000 V_c / (\pi D)\) rpm。
- 切削时间：\(T = L / (f \cdot n)\) min（车削）或 \(T = L \cdot i / (f \cdot n)\)（铣削，i=刀刃数）。
- 材料去除率 MRR = 进给 × 切深 × 切削速度。
- G71 复合粗车循环（G71 U(Δd) R(e) / G71 P(ns) Q(nf) U(Δu) W(Δw) F(f) S(s) T(t)）；G70 精车；G02/G03 顺/逆圆弧；G54 工件坐标系；M30 程序结束；M02 程序结束；M03 主轴正转；M08 冷却液开。
- 常用牌号：Cr12MoV（冷作模具钢）、45钢、40Cr、6061-T6 铝合金、Q235。
- GD&T：位置度、轮廓度、同轴度、垂直度、平行度、跳动；基准 A/B/C；最大实体要求 MMB/MMC/LMC。

---

## 4. 各维度题材建议（30 条怎么凑）

### reasoning（9 easy / 15 medium / 6 hard）
- easy：单步数值换算（D 转 n、f = Vc·z·n、体积 πR²L）
- medium：多步链式（切削时间 → 走刀次数 → 总时长；切深 → 残留高度；公差链累加）
- hard：给定毛坯与成品反推工序/走刀次数/工时；要同时考虑装夹与换刀

### knowledge（9/15/6）
- easy：术语定义（GD&T 符号、G 代码字、刀具类型）
- medium：API 行为与限制（AutoCAD `ModelSpace.Count` 累计、CIMCO 无 COM、NX 无 CreateTorus、斯沃 `general.ini` CNC 索引）
- hard：组合判断（给定场景选哪个工具/哪条通道、为什么不能用某接口）

### instruction（9/15/6）
- easy：只输出 JSON、指定键名
- medium：限定行数/字数/必须含某几个锚点、禁止出现某些词
- hard：同时给多条互相牵制的约束（既要 JSON 又要行数范围又不能出现某词）

### generation（9/15/6）
- easy：写一段标准 G 代码片段（`gcode_structure` 判）
- medium：写 FANUC Macro B 片段、写 AutoLISP 片段（`python_parses` 只对 Python）/ 工艺说明
- hard：写完整的、带注释和工艺参数说明的一段

### multimodal（9/15/6）
- 素材：脚本合成、真值已知的图片。仓库里 `scripts/make_multimodal_images.py` 可能不存在——**若不存在，用 PIL 自己合成**（PIL 已装）到 `data/benchmark/virtu_eval_v1/images/`，画上确定的文字/数值/孔位，**自己核对真值**，并在用例里写清 `images` 相对路径。
- 题目必须**只有看图才能答**（题面不得写出答案）。

### generalization（9/15/6）
- easy：把一个已知 API/公式换软件或换数字
- medium：同一意图换表述（"圆弧槽"→"半圆槽"）；换单位（mm↔inch）；换坐标系
- hard：换到**新场景但同构**（把链路的 `executed/substituted/blocked` 判定迁移到新软件）

### boundary（9/15/6）
- easy：明显越权/危险/无法执行 → 该拒
- medium：边界灰区（要求编造不存在的 API、要求保证未验证的结果、要求声称已执行但没执行）
- hard：要求**既拒又给可行替代路径**（如"没有 CreateTorus 就用表达式承载槽"）

### toolcall（9/15/6）
- easy：给定一句话诉求，选对工具 + action
- medium：填对必填参数与关键参数（`dimensions` 键名用 `d_outer/d_inner/overall_len/material`；NX 用 `D_OUTER/LENGTH`）
- hard：完整工具调用 JSON（含 `tool_calls` 结构与 `arguments` 对象），或设计一次多阶段编排（如先 preflight 再 run_full_chain）

---

## 5. 交付格式

每个维度一个文件：`data/benchmark/virtu_eval_v1/<dimension>.jsonl`，一行一个 JSON 对象（UTF-8，无 BOM，LF 换行）。

**交付前必须**：
1. 跑 `validate_cases.py`，退出码 0；
2. 抽查 ≥3 条，确认 `gold.answer` 与 criteria 自洽；
3. 确认没有重复 id、没有用不存在的 grader。

**回复父 Agent 时**：报告每维条数、tier 分布、校验结果、images 数量与路径清单，以及你**放弃或妥协**的地方（宁可如实说，不要假装完美）。
