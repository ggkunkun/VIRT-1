# STEP AP242 导出指引（源头治理，P2 优先级）

> 配套工具：`bridges/ap_detect.py`（盘点）、`bridges/step_bom.py`（解析+AP探测）、
> `bridges/step_normalize.py`（存量语料归一化）。
> 本文结论基于 2026-11-06 在本工作区 16 个 STEP 文件上的实测，证据见
> `reports/step_bom_scan.json`、`reports/ap_detect.json`。

---

## 1. 先说结论：这不是必须做的第一步

「13.63B 模型读不懂装配体」的**最高杠杆解法是 P0（推理前 STEP→BOM 预处理）**，
已由 `bridges/step_bom.py` 落地并在 16/16 文件上验证通过。改导出格式属于**源头治理**，
收益是"以后新产出的文件更干净"，但**不能替代** BOM 预处理——因为即使 AP242，
LLM 仍然不该直接读几万行 BREP 几何。

优先级建议：`P0 预处理 > P1 训练配对 > P4 存量归一化 > P2 导出 AP242`。

---

## 2. 实测到的 AP203 / AP214 问题（有数据）

| 现象 | 实测证据 | 对模型的影响 |
|---|---|---|
| **GBK 编码中文名** | `wheel_mold_P0.step`：`FILE_NAME ('微型机轮模总成(P0)…')` 是 GBK 字节；`detect_encoding=gbk`，2/16 文件为 GBK | UTF-8 分词后变成乱码 token，模型连零件名都识别不了 |
| **装配结构信号极稀疏** | 该文件 7690 个实体中 `NEXT_ASSEMBLY_USAGE_OCCURRENCE` 只有 4 行，且位于文件末尾 | 结构信息被 6000+ 点/方向/边淹没，注意力无法定位 |
| **AP 分布老旧** | 16 个文件：AP214=14、AP203=2、AP242=0 | 无 PMI、无现代产品结构表达 |
| **几何表达变体多** | `mold_core_mandrel.step` 用 `BREP_WITH_VOIDS` 而非 `MANIFOLD_SOLID_BREP`；`frame.step` 用 AP203 但 UTF-8 | 只认单一实体类型的解析器会漏件 |
| **结构靠隐式 `#id` 交叉引用** | 摆位需经 `RRWT → IDT → AXIS2_PLACEMENT_3D` 四跳 | 无自然语言锚点，LLM 无法直接推理 |

**量化收益**：`reports/step_bom_scan.json` 显示 21,228,236 字节原始 STEP →
3,591 字节结构化 BOM，整体压缩比 **5911×**，且 16/16 文件通过。

---

## 3. AP242 能解决什么、不能解决什么

| 能解决 | 不能解决 |
|---|---|
| 字符串编码规范（ISO-10303-21 用 `\X2\…\X0\` 转义或拉丁字符集，中文不再裸写 GBK） | 几何仍然是几万行 BREP，LLM 仍读不动 |
| 产品结构 / 装配关系表达更完整、更规范 | 不会自动把 4×4 变换写成"安装在 X 处" |
| 支持 PMI（尺寸、公差、GD&T）与语义 PMI | 不会自动生成 BOM 文本 |
| 更好的 CAD 互操作性 | 存量文件不会自动变干净 |

**所以：AP242 + BOM 预处理是组合拳，不是二选一。**

---

## 4. SolidWorks 2021 导出 AP242 操作步骤

1. 打开装配体 / 零件 → `文件 (File)` → `另存为 (Save As)`。
2. `保存类型` 选 **`STEP AP242 (*.step; *.stp)`**。
   - 若下拉里只有 `STEP (*.step)`，先点右下角 `选项 (Options…)`。
3. 在 `选项 / 文件选项` 中把 `输出为 (Output as)` 设为 **AP242**：
   - 可选子项：`AP242`（默认，含 PMI 表达）、`AP242 with PMI`（若需 3D 标注语义）。
   - 不要选 `AP203` / `AP214` —— 这两个正是本次实测问题来源。
4. 导出设置建议：
   - ✅ `输出坐标系` 用默认（全局），不要勾选"为每个零件单独输出坐标系"，否则位姿语义变复杂。
   - ✅ `输出 3D 曲线 / 草图实体`：关闭（减少无关几何噪声）。
   - ✅ `装配体结构`：选 **"保留装配体结构 / 输出所有零部件"**（不要选"仅输出单一实体"），
     否则 NAUO 装配树会丢失，BOM 解析器会退化成单零件。
   - ✅ 若下游要 PMI，勾 `输出 PMI / 3D 尺寸标注`。
5. 文件名建议用 **ASCII**（避免中文文件名在某些工具链下的编码问题）；中文零件名可保留，
   AP242 会按规范转义。
6. 保存后**必须验证**（见第 6 节）。

> Siemens NX 12.0：`文件 → 导出 → STEP242`，在 `STEP 导出选项` 里选 `AP242`、
> `产品结构 = 完整装配树`。AutoCAD 2026 导出能力较弱，建议经 SolidWorks/NX 中转。

---

## 5. 存量语料怎么办（不用重导也能修）

对已经存在的 GBK STEP，直接归一化即可，无需回到 CAD：

```bash
# 1) 盘点：有多少文件需要迁移
python3 bridges/ap_detect.py --dir assets --json reports/ap_detect.json

# 2) 归一化（默认不覆盖源文件，产物到 data/step_utf8/）
python3 bridges/step_normalize.py --dir assets --out-dir data/step_utf8 \
    --mode utf8 --report reports/step_normalize.json

# 3) 需要严格合规（纯 ASCII、\X2\ 转义）时用 x2 模式
python3 bridges/step_normalize.py --file "xxx.step" --out-dir data/step_x2 --mode x2
```

实测：`wheel_mold_P0.step` GBK→UTF-8 后回读，中文零件名、5 零件 4 关联、
4 个子件摆放坐标 **全部无损**；x2 模式产物为纯 ASCII 且 `\X2\5FAE578B…\X0\` 转义正确，
仍可被解析器识别。

| 模式 | 产物 | 适用 |
|---|---|---|
| `utf8`（默认） | UTF-8 文本，中文可读 | **LLM 训练/推理语料**，最友好 |
| `x2` | 纯 ASCII + STEP 标准转义 | 需喂给严格合规的 CAD 解析器 |

---

## 6. 导出/迁移后的验证清单（必须跑）

```bash
# ① AP 版本与编码是否达标
python3 bridges/ap_detect.py --dir <导出目录> --json reports/ap_detect_after.json
#    期望：ap_distribution 里 AP242 占主导，needs_utf8_migration = 0

# ② 装配树是否完整保留（关键！别让 NAUO 丢了）
python3 bridges/step_bom.py <导出文件.step> --json out.json --md out.md --dsl out.dsl
#    期望：is_assembly=true、component_count 与原子件数一致、中文名正确、摆放坐标非空

# ③ 全量回归
python3 bridges/batch_scan.py --dir <导出目录> --json reports/step_bom_scan_after.json
#    期望：pass_rate=1.0、error_count=0
```

**验收判据**（对应项目「测量宪法」）：以上命令的实跑输出为准，带 `run_id`、
样本量 `n`、每文件 `sha256`、口径 `basis=measured`。不要凭"导出对话框选了 AP242"
就断言成功——必须看 `FILE_SCHEMA` 里是否真出现 `AP242` / `10303 442` 或
`AP242_MANAGED_MODEL_BASED_3D_ENGINEERING` 之类标识。

---

## 7. 常见坑

- **选了 AP242 但零件名仍乱码**：多为 CAD 本地化版本把 GBK 字节直接写进了
  `PRODUCT` / `FILE_NAME`。用 `step_normalize.py` 兜底，不要手工改文件。
- **导出后 `component_count=0`**：导出选项勾了"仅输出单一实体/展平装配体"，
  装配树被压平。重导并保留装配结构。
- **AP242 有两种 schema 标识**：`AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF`
  或 `AP242` 前缀；`bridges/step_bom.py` 的 `detect_ap()` 已同时兼容
  `FILE_SCHEMA (( '…' ))` 带空格与紧贴两种写法（本次实测踩过这个坑）。
- **不要为了 AP242 放弃 P0**：即使全量 AP242，`step_bom.py` 的 BOM 预处理仍应保留在
  `virtu_omni` 感知通道前，这是压缩 5911× 的关键。

---

## 8. 本次落地清单（2026-11-06）

| 解法 | 交付物 | 状态 |
|---|---|---|
| P0 统一 BOM 解析 | `bridges/step_bom.py`、`step_preprocess.py` | ✅ 16/16 验证通过 |
| 集成 virtu_omni | `step_reverse.py`(action=bom)、`tool_calling_specs.py`、`six_software_orchestrator.py`、`step_assembly.py` | ✅ 四条路径端到端通过 |
| P1 训练配对 | `bridges/step_training_pairs.py` → `data/step_bom_sft.jsonl` (109 条) | ✅ |
| P3 多智能体 | `bridges/multiagent_assembly.py` (3 facet + 合成器) | ✅ |
| P4 编码归一化 | `bridges/step_normalize.py` | ✅ 回读无损 |
| P2 AP242 治理 | 本文 + `bridges/ap_detect.py` | ✅ 工具就绪，导出动作需在 CAD 侧执行 |
