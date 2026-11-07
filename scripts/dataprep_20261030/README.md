# dataprep_20261030 —— 新图纸批次加工管线

把 `D:\新图纸\图纸(2)` 与 `D:\新图纸\图纸(3)` 加工成 Virtu 大模型的高质量训练数据，
输出到 `E:\数据`。

## 快速使用

```powershell
# 全量构建（幂等，可重复执行）
python D:\Virtu模型\scripts\dataprep_20261030\build_all.py

# 只抽取不落盘（快速校验）
python D:\Virtu模型\scripts\dataprep_20261030\build_all.py --dry-run
```

**执行顺序很重要**：`build_all.py` 写出各模块文件后，需再跑一次仓库根目录的
权威聚合脚本，由它重建主训练集（保证主训练集严格等于各模块文件之和，不含中间态）：

```powershell
python D:\Virtu模型\unify_and_update_manifest.py
```

## 依赖

| 组件 | 用途 | 安装 |
| :--- | :--- | :--- |
| Python 3.12 | 运行时 | 本机已装 |
| `pymupdf` | PDF/SVG 文本、词级坐标、矢量路径、位图渲染 | 已装 |
| `openpyxl` | 世赛评分总表 xlsx 解析 | `pip install openpyxl` |
| `Pillow` | 图像资产统计与解码校验 | 已装 |

> **不需要** NX / SOLIDWORKS：`.prt` 走的是容器二进制解析（见下），
> 图纸走的是版面感知解析，不依赖任何 CAD 软件。

## 模块结构

| 文件 | 职责 |
| :--- | :--- |
| `extractors.py` | 抽取层：NX `.prt` / PDF / SVG / XLSX / 图片 → 结构化事实记录 |
| `sft_gen.py` | 生成层：事实记录 → ShareGPT 格式 SFT 样本 |
| `build_all.py` | 编排层：五阶段构建 + 清单/README 增量更新 |

## 五阶段

1. **NX 模型** → `10_NX_CAD_MODELS_AND_ASSEMBLIES`
2. **二维工程图** → `11_CNC_DRAWINGS_AND_PROCESS_PLANNING`
3. **世赛资料** → `12_WORLD_SKILLS_ASSESSMENT_AND_TASKS`
4. **多模态资产** → `13_MULTIMODAL_CAD_ASSETS`
5. **汇总** → 合并主训练集 + 更新 `DATASET_MANIFEST.json` / `README.md`

## 关键实现要点

### 1. NX `.prt`（Siemens PLM Structured Storage，`SPLMSSTR` 魔数）

无需 NX 即可解析，容器内可直接取出：

- **Parasolid 内核版本**：正则 `SCH=SCH_<schema>_<version>`
- **建模操作名**：`EXTRUDE` / `HOLE PACKAGE` / `SIMPLE HOLE` / `BLEND` / `SHELL` …
- **特征类型分布**：`UGS::ModlFeature::*` / `UGS::Solid::*` / `UGS::Drafting::*` …
- **属性表**：`UgAttributes` XML 块 → `NX_Arrangement` / `NX_ReferenceSet` 等
- **装配 BOM**：装配体内引用的 `*.prt` 文件名（机械臂 14 件、assembly1 12 件 …）
- **内嵌预览图**：`/Root/images/preview` 中的 JPEG，固定 **247×185**
  （⚠ 不能取"最大的 JPEG"——部分模型还嵌着标题栏位图，会误取）

> 几何内核数据本身在容器里是压缩态，**不做实体级解析**（无法可靠还原面/边拓扑）。
> 因此特征树与尺寸信息来自**随附工程图**，模型侧只提供内核/操作/属性/BOM 层事实。

### 2. 工程图 PDF / SVG —— 版面感知解析

单纯 `get_text()` 会把标题栏、技术要求、加工参数表、尺寸标注全部混在一起。
本管线先取**词级坐标**（`page.get_text("words")`），再按版面区域分离：

- 标题栏（中文）/ 图框（英文）→ 排除区
- 技术要求栏 → 按"锚点右侧整列"取外接框（否则栏内长句会漏进尺寸集合）
- 加工参数表 → 按**列坐标**重建 `工序|刀具|主轴转速|进给|备注`
- 说明/通用公差区 → 按行关键词（`TOLERANCE`/`OVER`/`UNDER`/`NOTE`）整行排除
- 尺寸标注 → 按符号语义分类（直径/半径/倒角/螺纹/带公差线性/深度/粗糙度/阵列系数）

**踩过的坑**：
- 英文图框关键词（`DESCRIPTION` 等）在页眉也会出现 → 取全局外接框会覆盖整张图，
  必须取"关键词最密集的那条水平带"。
- 标注 token 若含 `（），` 等标点，是被 PDF 切碎的半截语句 → 一律丢弃。
- 电话号码（如练习图里的 WhatsApp 号）会被当成尺寸 → 6 位以上纯数字排除。

### 3. 世赛评分表

- `*.xlsx` → `openpyxl` 解析 `Criteria` / `满分`
- 官方 `OMF`/`SMF` PDF → 行聚类 + **Aspect-ID 形态锚定**（行首 token 匹配 `^[A-Z]{1,2}\d{1,2}$`）
  重建 `Aspect | Max Mark | Description | Requirement`
- ⚠ 同一子标准在 OMF 与 SMF 中都会出现 → **样本 id 必须带表单种类**，否则 id 冲突、样本被静默丢弃

### 4. 多模态资产

- 图片**复制入库**（数据集自包含，不依赖外部路径）
- SHA256 去重，重复件在索引中标记 `duplicate_of` 并指向原件路径
- 重复件**不**生成训练样本（避免重复采样导致过拟合）

## 数据可信度约定

- SFT 回答中的**每一个工程数值都来自抽取层的真实字段**，可在模块索引文件中逐条回查。
- 图纸未标注的要素显式写明「图面未标注，需回查三维模型」，不以推测值填充。
- 新样本统一带 `grounded: true` 标记。

## 自检

```powershell
# 结构/资产/溯源/兼容性验收
python D:\Virtu模型\scratch\dataprep_20261030\acceptance.py

# 真实 Qwen3 分词器冒烟测试（需 pip install tokenizers）
python D:\Virtu模型\scratch\dataprep_20261030\tokenizer_smoke.py
```
