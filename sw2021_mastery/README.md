# SW2021 Mastery — SOLIDWORKS 2021 专项训练体系

把「会背命令」的模型，练成「在 2021 SP5 原生界面里每一步都能被工程师照着做出来」的执行体。
本目录交付的是**可执行的训练体系 + 已生成并机器校验通过的训练资产**，不是一份 PPT 方案。

---

## 1. 环境基线（实测，2026-11-18）

| 项 | 值 |
| --- | --- |
| 产品 | SOLIDWORKS 2021 SP5.0 |
| 版本 | `29.5.0.0070` |
| 路径 | `D:\SOLIDWORKS (2)\SLDWORKS.exe` |
| ProgID | `SldWorks.Application` → CLSID `{0A5BC87B-FDBF-4A0B-BC8A-DE1271220E81}` → `D:\SOLIDWORKS (2)\sldworks.exe` |
| 界面 | 简体中文（Chinese Simplified Resources 29.150.0070） |
| 同机风险 | 注册表另有 SOLIDWORKS 2026 SP03.2（34.3.2.3），`D:\Program Files\SOLIDWORKS Corp2026` |

> 双版本共存是**一等风险**：2026 保存的文件 2021 打不开，且 2021 不支持降版保存。
> 隔离 SOP 见 `SPEC/03_版本合规_工作流_异常手册.md` §2（绝对路径启动 + RevisionNumber 断言 + 截图含版本）。

---

## 2. 交付清单

| 文件 | 内容 | 实测规模 | 状态 |
| --- | --- | --- | --- |
| `data/ops_*.psv` | 12 模块三级功能清单（L1→L2→L3） | **348** 个 L3 点 | 已生成 |
| `out/train_dataset.jsonl` | 训练数据集（操作/流程/装配/出图/排错/标注/API/配合） | **6317** 条 | 已生成，待人工签署 |
| `out/instruction_map.jsonl` | 自然语言指令映射表 | **18139** 条 | 已生成，20/20 意图类 |
| `out/testcases.jsonl` | 可执行测试用例库 | **524** 条 | 已生成，12 模块各 ≥26 |
| `out/coverage_matrix.csv` | 每个 L3 点的样本/映射/用例覆盖 | 348 行 | 已生成 |
| `out/validation_report.{json,md}` | 一致性与版本合规校验报告 | 9 硬门全 PASS | 已生成 |
| `out/manifest.json` | 计数 + SHA256 | 4 文件 | 已生成 |
| `SPEC/01~04` | 体系总纲 / 模块规范 / 版本与异常手册 / 映射与验收规程 | 4 份 | 已生成 |
| `logs/training_log.jsonl` | 训练日志（JSONL，可追溯） | 3 条 | 已生成 |
| `reports/daily_2026-11-18.md` | 日报（脚本渲染，不可手改） | 1 份 | 已生成 |
| `gen/*.py` | 构建器 / 校验器 / 日报渲染器 | 3 个脚本 | 可复跑 |

### 2.1 训练集构成

| 类型 | 条数 | 说明 |
| --- | --- | --- |
| operation | 4176 | 348 个操作点 × 12 组参数变体 |
| workflow | 120 | 10 个标准零件 × 12 组尺寸组合 |
| assembly | 12 | 36 零件减速器装配 |
| drawing | 8 | 8 类 GB 工程图 |
| troubleshooting | 696 | 348 个错误场景 × 诊断/回归 |
| annotation | 405 | 45 条 GB 标注规则 × 9 张图 |
| api | 480 | 24 个 API 主题 × 20 组参数 |
| mate | 420 | 14 类配合 × 30 组场景 |

---

## 3. 机器校验结果

```
H1 训练集 ≥5000            PASS  6317
H2 指令映射 ≥2000          PASS  18139
H3 用例 ≥500               PASS  524
H3b 每模块用例 ≥20         PASS  无不足模块
H4 id 唯一 + 引用可解析    PASS  重复 0 / 悬空 0
H5 每个 L3 至少 1 样本+1 映射  PASS  348/348
H6 无 2022+ 版本串味       PASS  命中 0
H7 必备字段齐全            PASS  缺失 0
S1 2021 界面白名单         PASS  16380/16380 = 100.00%
S2 原生截图证据            PENDING  6317 条 evidence=pending
S3 意图覆盖 ≥95%           PASS  20/20 = 100%
```

复跑：

```bash
cd "D:/Virtu模型/sw2021_mastery"
python gen/build_all.py        # 重建三套资产（覆盖 out/*.jsonl）
python gen/validate_all.py     # 一致性 + 版本合规校验
python gen/daily_report.py     # 从日志渲染日报
```

---

## 4. 目录结构

```
sw2021_mastery/
├─ data/
│  ├─ ops_01_sketch.psv ... ops_07_mold_rout_cfg_macro.psv   # 348 个 L3 点
│  ├─ recipes.json          # 10 零件 + 36 零件装配 + 8 图 + 45 GB 规则 + 24 API + 14 配合
│  └─ version_rules.json    # 2021 基线 / 白名单 / 黑名单 / 必备字段
├─ gen/
│  ├─ build_all.py          # 资产构建
│  ├─ validate_all.py       # 校验器
│  └─ daily_report.py       # 日报渲染
├─ out/                     # 三套资产 + 报告 + manifest
├─ SPEC/                    # 4 份方案文档
├─ logs/training_log.jsonl  # 训练日志
└─ reports/                 # 日报
```

**功能清单字段**：`编码｜模块｜L2｜L3｜2021 菜单路径｜参数域(min-max:default:unit 或枚举)｜校验点｜错误码~场景~修复`。
例：`SKT-01|草图|草图实体创建|直线|草图选项卡→直线|len:0.1-500:50:mm;ang:0-360:0:deg|两端点可捕捉/…/|SW-SKT-101~两点重合…~删除重合端点…`

---

## 5. 本交付做到了什么 / 没做什么

**已完成（可机器验证）**
- 12 模块 348 个 L3 点，全部带 2021 菜单路径、参数域、校验点、错误分支。
- 三套资产规模全部超阈值，且三者 `op_code` 双向可解析、每个点三处齐备。
- 版本合规白名单 100% 命中、黑名单 0 命中；双版本隔离 SOP 落到可执行断言。
- 五级路径 698h 小时级排期、门禁评分、日志/日报/台账/验收规程全部成文。

**2026-11-18 真机执行结果（详见 `reports/exec_2026-11-18_G1_G2.md`）**
- **G1 版本门 PASS**：`SldWorks.Application.29` 连上，`RevisionNumber=29.5.0`，未误连同机 2026。
- **G2 原生操作门 BLOCKED**：建件成功（5.3~12.7s），但文档存在后主窗口单核 100% 空转、`Responding=False`，
  选面调用 309s 后 RPC 失败。六组隔离实验（沙箱/权限、CEF、独显、核显、前台激活、COM 绑定方式）全部排除。
- 根因：本机显卡（RTX 4050 Laptop / Intel UHD）不在 SOLIDWORKS 2021 支持列表，文档打开后进入渲染空转。
- 因此 **0 条样本转为 `screenshot_verified`**，6317 条仍为 `pending_native_screenshot`；这是门禁生效，不是遗漏。

**未完成（必须人工，不能由脚本代替）**
- **原生截图核验 0/6317**：需在 VB-0 合格的验证台上实操并签署。
- **模型侧微调未执行**：本目录产出的是训练资产与规程；真正把权重练进去需要底座模型与 GPU 预算（工作区已有 `AGENT_TRAINING_PLAN.md` 的 LoRA 基线可复用）。
- **参数取值是工程合理值，不是图样值**：P01~P10 的尺寸来自典型设计，正式训练需替换为实际图样。

---

## 6. 下一步（按顺序）

1. **先过 VB-0（验证台资质门）**：换认证工作站，或人工在本机 2021 界面关闭 RealView/启用软件 OpenGL 后复测。
2. 用 `D:\SOLIDWORKS (2)\SLDWORKS.exe` 启动，断言 `RevisionNumber` 以 `29.` 开头（已验证可用的做法）。
3. 从 `TC-000001` 起跑 26 条草图用例，边跑边补 `evidence/` 截图，签署 `review` 字段。
4. 每完成 3 个模块跑一次版本审计（`SPEC/03` §3），通过后再进下一模块。
5. 资产冻结后再启动 LoRA 微调，避免「用未核验数据训练」导致返工。
