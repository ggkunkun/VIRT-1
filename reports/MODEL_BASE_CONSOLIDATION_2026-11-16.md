# 统一基座模型治理报告（2026-11-16）

> 对象：工作区 Ollama Modelfile 定义体系　｜　力度：保守档（仅字节级重复 + 零活引用）
> 证据等级：`basis=measured`（所有数字来自脚本实测 / 活标签回读 / 真实推理调用）
> 复跑方式：`python scripts/analyze_modelfile_universe.py` → `python modelfiles/BASE/virtu_base.py check` → `python scripts/verify_unified_base.py`

---

## 一、变更摘要

### 新增（3 个交付件）

| 文件 | 作用 |
| :--- | :--- |
| `modelfiles/BASE/virtu_base.py` | **单一真源**：FROM / TEMPLATE / SYSTEM / PARAMETER 与 5 个能力 profile 全部收敛于此；`render()` / `render_for()` / `check` / `check-live` 可复跑 |
| `modelfiles/BASE/virtu-base.Modelfile` | 由真源渲染的 canonical 基座定义（100 行 / 4788 B，sha256 `b4e530f57239f025…`） |
| `scripts/verify_unified_base.py` | 隔离端口（11435/11436）端到端验证：真源一致 → 服务就绪 → 标签可见 → 真实推理调用，不干扰默认 11434 |

### 修改（2 个，均为追加式，不改原行为）

| 文件 | 改动 |
| :--- | :--- |
| `scripts/check_modelfile_drift.py` | `DEFAULT_TAGS` 追加 `"virtu-base:unified": "BASE/virtu-base.Modelfile"`，基座纳入漂移门；原两条 hardened 登记不变 |
| `scripts/analyze_modelfile_universe.py` | 新建的只读盘点器（指纹 + 重复组 + 命名冲突 + 引用候选），排除备份目录 |

### 新增 Ollama 标签（不覆盖任何现有标签）

```
virtu-base:unified   f1391a5f335b   4.6 GB   qwen3 8.2B Q4_0
```

### 未改动（关键兼容保证）

- 所有 200 份存量 Modelfile **一个未删、一个未改**（除下述 1 个零引用重复日志）
- 现有标签 `virtu-six-software:v3` / `v4-local-repair` 的 manifest 与权重 blob 未触碰
- 4 个生成脚本（`build_prod_modelfiles` / `harden_modelfiles` / `build_wm_modelfile` / `deploy_and_cleanup`）行为不变，语法回归通过
- `checkpoints/PRODUCTION_SYSTEM_702B.txt`、`modelfiles/*.hardened.Modelfile` 等被引用真源原样保留

---

## 二、梳理结果：重复 / 冗余 / 冲突

### 2.1 规模基线

| 指标 | 清理前 | 清理后 |
| :--- | ---: | ---: |
| Modelfile 定义 | 200 | 201（+1 基座） |
| 带 SYSTEM 块 | 159 | 160 |
| 带 TEMPLATE 块 | 78 | 79 |
| SYSTEM 语义组（规范化后） | 21 | 21 |
| 参数组合种类 | 61 | 61 |
| 字节级完全重复组 | 2（4 文件） | 1（2 文件） |
| 同名不同字节（命名冲突） | 2 | 2 |

### 2.2 重复定义（字节级，已证）

| 组 | 文件 | 处置 |
| :--- | :--- | :--- |
| `aa1e1a133637…` | `checkpoints/Modelfile.virtu_master_latest` ≡ `checkpoints/Modelfile_v5_comprehensive` | **保留两者**：均被 `deploy_and_cleanup.py` 引用（L162 同步下载名、L202 部署写入、L285 同步副本），且由 `deploy_to_ollama()` 每次部署动态重生成 |
| `a787d61fa142…` | `runs/wm_modelfile_build2.log` ≡ `runs/wm_modelfile_build.log` | **删除前者**（零引用重复日志），后者保留 |

### 2.3 命名冲突（同名不同字节）

| 文件名 | 版本数 | 分布 | 处置 |
| :--- | ---: | :--- | :--- |
| `modelfile_virtu_13b` | 2 | `models/virtu-13b/`、`cloud_train_pack/output_13b/` | 保留（各自绑定不同权重/阶段，非同义） |
| `modelfile.virtu-toolcall` | 2 | `scratch/`、`scripts/` | 保留（scratch 为实验副本，scripts 为工具调用基线） |

### 2.4 行为冲突（已识别，基座统一，存量保留）

| 冲突项 | 存量分布 | 统一基座取值 | 兼容方式 |
| :--- | :--- | :--- | :--- |
| `num_ctx` | 4096（hardened 族）↔ 8192（six-software / prod 族） | **8192** | `PROFILES["hardened"]` 覆盖为 4096 |
| `top_p` | 0.9 ↔ 0.95（`virtu_master_latest`） | **0.9** | profile 可覆盖 |
| `repeat_penalty` | 1.05 ↔ 1.15（hardened 族） | **1.05** | `PROFILES["hardened"]` 覆盖为 1.15 |
| stop token 写法 | `"<\|im_end\|>"`（带引号）↔ `<\|im_end\|>`（裸值） | **裸值** | Ollama 解析等价；活标签回读一致 |
| SYSTEM 契约族 | 桌面键鼠族（18 份）/ 工程安全族（14 份）/ 生产 702B 族 / 智能体族 | **三族合并**（工程安全 + 桌面控制 + 工具真实性） | 各 profile 可 `system_override` |
| `num_gpu` / `presence_penalty` | 仅 hardened 族（机器相关） | **不写入基座** | 避免 `check_modelfile_drift.py` 的 num_gpu 禁令误报 |

> 说明：SYSTEM 语义组 21 个中，最大一组为「无 SYSTEM 块」（41 份纯 FROM 变体），并非真实语义重复；真实重复集中在 `ade38b00…`（18 份桌面族）与 `2f4e97d7…`（14 份工程族）。

---

## 三、统一基座定义

### 3.1 结构

```
FROM  <生产权重 blob sha256-abd8b726…>          # 权重层零改动（与 v3 活标签同源）
TEMPLATE """ChatML + tools + think/no_think"""   # 权威模板，规范化 sha a287fa78642c3bc7
SYSTEM  """工程安全 ∪ 桌面键鼠 ∪ 工具真实性"""      # 三族契约合并，逐条保留
PARAMETER num_ctx 8192 / repeat_penalty 1.05 / stop ×2 / temperature 0.1 / top_p 0.9
```

### 3.2 能力保留清单

- **工程计算**：mm/deg、体积守恒、FOS ≥ 1.5、Lamé 应力
- **安全底线**：G00 零碰撞、拒绝联锁短接/限位屏蔽/跳过首件、缺参数不盲猜
- **工具调用**：原生 `<tool_call>`、等待回执、绝不伪造测量/文件名/执行状态
- **桌面控制**：`cadcam_desktop_gui`（click/move/drag/scroll/type_text/hotkey/capture/focus/inspect_window/dismiss_dialogs）、`cadcam_visual_inspect`（autodiff_inspection）
- **输出规范**：中文、代码保留原文、结构化输出合法 JSON、G 代码标方言
- **模型能力**：`completion` / `tools` / `thinking` 三项均可用（`ollama show` 实测）

### 3.3 派生接口（单一真源 → 能力变体）

```python
from modelfiles.BASE.virtu_base import render_for
render_for("virtu-six-software:v3", profile="hardened")
# → 基座 TEMPLATE/SYSTEM + num_ctx 4096 / repeat_penalty 1.15 / min_p 0.05 / presence_penalty 0.3
```

已登记 profile：`prod` / `hardened` / `six_software` / `desktop` / `wm`。旧生成脚本无需改动即可继续工作；需要收敛时改调 `render_for()`，标签名与调用方式不变。

---

## 四、清理清单

### 4.1 已清理（1 项）

| 路径 | 大小 | SHA256 | 判定依据 | 备份 |
| :--- | ---: | :--- | :--- | :--- |
| `runs/wm_modelfile_build2.log` | 1723 B | `a787d61fa142ed32…` | 与 `runs/wm_modelfile_build.log` 字节完全相同；全库零引用（唯一命中为本次生成的报告自身）；构建日志属临时产物 | `reports/modelfile_cleanup_backup_2026-11-16/wm_modelfile_build2.log`（SHA 校验一致） |

### 4.2 明确保留（不满足保守档删除条件）

| 项 | 原因 |
| :--- | :--- |
| `checkpoints/Modelfile.virtu_master_latest` 与 `Modelfile_v5_comprehensive` | 字节相同但**均被 `deploy_and_cleanup.py` 引用**，且由部署函数动态重写 → 删任一都会破坏部署链 |
| 其余 198 份 Modelfile | 非字节重复（FROM 权重、注释、参数、SYSTEM 各不相同），按保守档不删 |
| `runs/wm_modelfile_build.log` | 重复组的保留代表 |
| `modelfiles/prod/*`（12 份）、`scratch/hardened_modelfiles/*`（约 80 份） | 由生成脚本产出，是生成链的验收产物，删除会导致下次 `--generate` 前后不可比对 |
| `checkpoints/Modelfile.v3.Modelfile.bak_20261107` 等 .bak | 历史回滚点，非临时产物 |

### 4.3 未清理的"冗余配置"（记录在案，待决策）

- `PRODUCTION_TAGS` 中 3 个生产标签（`virtu-moe-14b:latest/fast`、`virtu-13.63b:latest`）无 canonical profile，未纳入漂移门。
- `modelfiles/prod/` 12 份 `virtu-max-<sha8>` 仅权重不同、配置一致，可视为同一基座的 12 个权重绑定；如需进一步收敛，可按 `render_for(..., profile="prod")` 统一重生成（本次未做，避免改动生产构件）。

---

## 五、验证结果

| # | 验证项 | 命令 | 结果 |
| :--- | :--- | :--- | :--- |
| 1 | 真源一致性 | `virtu_base.py check` | **BASE_OK** sha256 `b4e530f57239f025` |
| 2 | 基座注册（加载） | `ollama create virtu-base:unified -f …` | **success**，ID `f1391a5f335b`，4.6 GB |
| 3 | 配置回读 | `ollama show virtu-base:unified --modelfile` | FROM/TEMPLATE/SYSTEM/6 个 PARAMETER 与真源逐项一致 |
| 4 | 架构与能力 | `ollama show virtu-base:unified` | qwen3 / 8.2B / ctx 40960 / Q4_0；`completion, tools, thinking` |
| 5 | **真实调用** | `verify_unified_base.py`（隔离 11435） | **PASS** 19.3 s / 36 tokens / `done_reason=stop`；答："G00 仅允许在非切削路径、空运行回零或轮廓定位时使用，严禁用于刀具切入/切出或加工走刀。" |
| 6 | **现有标签回归** | `verify_unified_base.py --tag virtu-six-software:v3`（11436） | **PASS** 12.6 s / 29 tokens；v3 行为未变 |
| 7 | 漂移门 | `check_modelfile_drift.py --tag virtu-base:unified` | **OK**（活标签与 canonical 零漂移） |
| 8 | 生成脚本语法回归 | `py_compile` × 6 | **OK** |
| 9 | 引用文件存在性 | 6 个关键真源 | 全部 `OK` |

### 环境事实（不掩盖）

- 验证期间本机有其它会话的 QLoRA 训练与 pytest 在跑，GPU 显存一度仅剩 1472 MiB，首次 `ollama create` 后调用报 `cudaMalloc out of memory`。**未终止他人进程**，待 GPU 释放（0 MiB）后重试通过。
- 默认 11434 服务在验证中途被外部重启，切换到旧 `manifests/` 存储视图导致标签列表为空；故改用**隔离端口 + 显式 `OLLAMA_MODELS`** 完成验证，不干扰默认服务。
- 因此第 5/6 项证据来自隔离实例（`basis=measured`），默认服务视图需重启至 `D:\Virtu模型\.ollama_store\models` 后才能看到 `virtu-base:unified`。

---

## 六、后续建议（不在本次保守档范围）

1. **将基座接入生成链**：`build_prod_modelfiles.py` / `harden_modelfiles.py` 改为 `from virtu_base import render_for`，即可让 90+ 份产物真正从单一真源派生（当前仅登记 profile，未强制）。
2. **扩展漂移门**：把 3 个 `PRODUCTION_TAGS` 也登记 canonical profile，消除「无门看管」。
3. **命名冲突收敛**：两份 `modelfile_virtu_13b` / `modelfile.virtu-toolcall` 建议加目录前缀或版本后缀，避免 `ollama create -f` 误取。
4. **清理备份保留期**：`reports/modelfile_cleanup_backup_2026-11-16/`（1.7 KB）可在一周后删除。
