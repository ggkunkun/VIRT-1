# -*- coding: utf-8 -*-
r"""
build_standards_and_components.py
Processes:
  1. e:\迅雷下载\GB型材库 (968 SolidWorks weldment profile definitions .sldlfp)
  2. e:\迅雷下载\A研发设计库 (436 COTS components across 32 industrial categories)
Produces:
  1. 05_STANDARDS_AND_COMPONENTS_LIBRARY/gb_profiles_catalog.json
  2. 05_STANDARDS_AND_COMPONENTS_LIBRARY/standard_parts_taxonomy.json
  3. 05_STANDARDS_AND_COMPONENTS_LIBRARY/standard_components_selection_sft.jsonl
"""

import os
import sys
import re
import json

sys.stdout.reconfigure(encoding='utf-8')

OUTPUT_DIR = r"e:\新建文件夹 (3)\05_STANDARDS_AND_COMPONENTS_LIBRARY"
os.makedirs(OUTPUT_DIR, exist_ok=True)

GB_DIR = r"e:\迅雷下载\GB型材库"
ARD_DIR = r"e:\迅雷下载\A研发设计库"

# 1. Process GB Profiles Library
print("Processing GB Profiles Library ...")
gb_catalog = {}

for cat in sorted(os.listdir(GB_DIR)):
    cat_path = os.path.join(GB_DIR, cat)
    if os.path.isdir(cat_path):
        specs = []
        for f in sorted(os.listdir(cat_path)):
            if f.endswith('.sldlfp'):
                name_clean = f.replace('.sldlfp', '').strip()
                # Extract dimensions like "100 x 100 x 4" or "100 x 50 x 3" or "#12"
                dims = [float(x) for x in re.findall(r'(\d+(?:\.\d+)?)', name_clean)]
                
                # Approximate linear density (kg/m) for steel (density 7.85 g/cm3)
                weight_kg_m = 0.0
                if "方" in cat and len(dims) >= 3:
                    a, b, t = dims[0], dims[1], dims[2]
                    # cross-section area = (a*b - (a-2t)*(b-2t)) in mm2
                    area = (a * b) - ((a - 2*t) * (b - 2*t))
                    weight_kg_m = round(area * 7.85 * 1e-3, 2)
                elif "矩形" in cat and len(dims) >= 3:
                    a, b, t = dims[0], dims[1], dims[2]
                    area = (a * b) - ((a - 2*t) * (b - 2*t))
                    weight_kg_m = round(area * 7.85 * 1e-3, 2)
                elif "圆管" in cat and len(dims) >= 2:
                    d_out, t = dims[0], dims[1]
                    area = 3.14159 * (d_out - t) * t
                    weight_kg_m = round(area * 7.85 * 1e-3, 2)
                elif "角钢" in cat and len(dims) >= 2:
                    b, t = dims[0], dims[1]
                    area = (2 * b - t) * t
                    weight_kg_m = round(area * 7.85 * 1e-3, 2)
                elif len(dims) >= 1:
                    weight_kg_m = round(dims[0] * 1.5, 2)
                
                specs.append({
                    "profile_spec": name_clean,
                    "filename": f,
                    "parsed_dimensions": dims,
                    "estimated_linear_density_kg_m": weight_kg_m
                })
        
        if specs:
            gb_catalog[cat] = {
                "category_name": cat,
                "total_specs": len(specs),
                "specs": specs
            }

gb_catalog_file = os.path.join(OUTPUT_DIR, "gb_profiles_catalog.json")
with open(gb_catalog_file, "w", encoding="utf-8") as f:
    json.dump({
        "dataset_name": "GB国标焊接结构型材库与物理参数字典",
        "total_categories": len(gb_catalog),
        "total_profiles": sum(c["total_specs"] for c in gb_catalog.values()),
        "categories": gb_catalog
    }, f, ensure_ascii=False, indent=2)
print(f"Saved GB Profiles Catalog -> {gb_catalog_file}")

# 2. Process A研发设计库
print("Processing A研发设计库 ...")
ard_taxonomy = {}

for cat in sorted(os.listdir(ARD_DIR)):
    cat_path = os.path.join(ARD_DIR, cat)
    if os.path.isdir(cat_path):
        items = []
        for f in sorted(os.listdir(cat_path)):
            if f.endswith(('.SLDPRT', '.sldprt', '.SLDASM', '.sldasm', '.step', '.STEP')):
                clean_name = os.path.splitext(f)[0]
                items.append({
                    "component_code": clean_name,
                    "file_name": f,
                    "type": "assembly" if f.lower().endswith('.sldasm') else "part"
                })
        if items:
            ard_taxonomy[cat] = {
                "category_name": cat,
                "total_items": len(items),
                "components": items
            }

ard_taxonomy_file = os.path.join(OUTPUT_DIR, "standard_parts_taxonomy.json")
with open(ard_taxonomy_file, "w", encoding="utf-8") as f:
    json.dump({
        "dataset_name": "A研发设计库工业自动化标准件与常用外购件体系",
        "total_categories": len(ard_taxonomy),
        "total_components": sum(c["total_items"] for c in ard_taxonomy.values()),
        "categories": ard_taxonomy
    }, f, ensure_ascii=False, indent=2)
print(f"Saved A研发设计库 Taxonomy -> {ard_taxonomy_file}")

# 3. Create Standard Component Selection SFT Dataset
SYSTEM_PROMPT = (
    "你是由 Virtu 工业模型驱动的非标自动化标准件选型与结构计算专家。"
    "你掌握 GB 型材库、MISUMI/THK/HIWIN 机械传动件、SMC/亚德客气动件及各类传感器规格，"
    "能够依据载荷工况、安装空间与精度等级给出最优选型方案。"
)

selection_samples = [
    {
        "id": "std_sel_001",
        "topic": "机架立柱与横梁型材选型：GB／6728 方形空心型钢选型与挠度校核",
        "prompt": "在设计一套 3C 手机点胶机的主机架时，立柱高度 1600mm，承受上部总装及运动滑台静载荷 350kg。横梁跨距 1200mm，中间集中载荷 1500N，要求横梁最大弹性弯曲挠度小于跨距的 1/1000（即 f_max < 1.2mm）。请从 GB 型材库中比选 60x60、80x80 方形空心型钢的截面刚度与米重，并给出最优选型结论。",
        "response": """### GB 国标结构型材机架立柱与横梁工程选型校核

#### 1. 结构刚度与最大挠度公式
简支梁中间承受集中载荷 $F = 1500\\text{ N}$，跨距 $L = 1200\\text{ mm}$，材料弹性模量（Q235钢）$E = 206\\text{ GPa} = 2.06 \\times 10^5\\text{ MPa}$。
最大挠度公式为：
$$f_{max} = \\frac{F L^3}{48 E I_x} \\le [f] = 1.2\\text{ mm}$$
由此反求所需截面惯性矩 $I_x$：
$$I_x \\ge \\frac{F L^3}{48 E [f]} = \\frac{1500 \\times (1200)^3}{48 \\times 2.06 \\times 10^5 \\times 1.2} = \\frac{2.592 \\times 10^{12}}{1.18656 \\times 10^7} \\approx 2.184 \\times 10^5\\text{ mm}^4 = 21.84\\text{ cm}^4$$

---

#### 2. GB 型材库参数对比
查询 `GB／6728-1986方形空心型钢` 截面特性：
- **方案 A：60 x 60 x 3.5 方形型钢**：
  - 截面惯性矩 $I_x \\approx 36.5\\text{ cm}^4 > 21.84\\text{ cm}^4$；
  - 实际挠度：$f_{max} = 1.2 \\times \\frac{21.84}{36.5} \\approx 0.72\\text{ mm} < 1.2\\text{ mm}$；
  - 米重：$5.98\\text{ kg/m}$；
- **方案 B：80 x 80 x 4.0 方形型钢**：
  - 截面惯性矩 $I_x \\approx 98.6\\text{ cm}^4$；
  - 实际挠度：$f_{max} \\approx 0.26\\text{ mm}$（刚度极其优异，抗震抗扭强）；
  - 米重：$9.31\\text{ kg/m}$。

---

#### 3. 选型工程决策
- **横梁与主承重立柱推荐**：选用 **GB／6728 80 x 80 x 4.0** 方形空心型钢。在精密高速点胶过程中，电批与点胶头高频换向加减速会产生冲击振动，80x80 型钢近 100 cm4 的惯性矩能有效吸收高频振颤，防止打胶轨迹波浪变形；
- **辅助支撑与门框框架**：选用 **60 x 60 x 3.5** 或标准 4040 铝型材，兼顾轻量化与装配灵活性。"""
    },
    {
        "id": "std_sel_002",
        "topic": "精密丝杠支承座选型：A研发设计库 LEB01 与 LEB11 配套工程要点",
        "prompt": "在伺服滚珠丝杠模组设计中，选用了 ⌀15 导程 10mm 的研磨级滚珠丝杠。请说明 A研发设计库中【丝杆固定侧 LEB01-15】与【丝杆支撑侧 LEB11-15】的内部轴承配置差异、轴向约束方式以及装配时的预拉伸工艺要点。",
        "response": """### 工业标准件库 滚珠丝杠支承座（固定侧 LEB01 / 支撑侧 LEB11）应用规范

#### 1. 结构与内部轴承配置差异
- **固定侧支承座（LEB01-15）**：
  - **内部轴承**：成对组装的 **超高接触角角接触球轴承（DF背对背预紧配置，如 7002C/P5）**；
  - **功能**：同时承受极高的径向载荷与双向交变轴向推力，消除轴向游隙，确保伺服电机的微米级定位刚度；
  - **配合轴端**：丝杠端部设计为精密阶梯轴，通过螺纹锁紧螺母配合防松垫圈将内圈紧紧压固在轴肩上。
- **支撑侧支承座（LEB11-15）**：
  - **内部轴承**：单个 **深沟球轴承（如 6002ZZ）**；
  - **功能**：仅承受丝杠远端的径向悬臂下垂重力与径向跳动，**不承受任何轴向载荷**；
  - **轴向状态**：轴承外圈在座孔内允许自由轴向滑动，内圈采用挡圈（C型卡簧）定位。

---

#### 2. 轴向约束与热伸长补偿机制（固定-支撑配置）
此种「一端固定、一端支撑」是自动化轴系最经典的装配范式：
- **热补偿**：当伺服模组高频往复运行导致丝杠摩擦发热伸长时，伸长量由支撑端 LEB11-15 内圈随轴向外浮动吸收，避免丝杠受压失稳发生「热弯曲波浪」；
- **预拉伸要点**：在高精度设备中，安装时可在固定端施加微量轴向拉伸预紧力（约 $0.02\\text{ mm}$ 预拉伸量），提前抵消升温后的膨胀量，确保全程全温域螺距精度恒定。"""
    },
    {
        "id": "std_sel_003",
        "topic": "直线导轨滑块选型：HIWIN HGH 与 HGW 系列对比及预紧等级代号解析",
        "prompt": "请对比 A研发设计库中常用直线导轨滑块 HGH 系列与 HGW 系列在外形特征、安装方式上的差异，并解释轻预紧 (ZA)、中预紧 (ZB) 的适用工况。",
        "response": """### HIWIN 直线导轨滑块工程选型标准

#### 1. HGH 与 HGW 系列核心特征对比
- **HGH 系列（高组装四方型）**：
  - **结构外形**：滑块截面呈高方块状，无外伸法兰；
  - **安装螺孔**：滑块顶部为盲孔螺纹，**仅支持自上向下**使用螺钉紧固；
  - **适用场景**：安装空间紧凑、滑块宽度受限的垂直升降滑台 (Z轴) 或双导轨窄滑台。
- **HGW 系列（高组装法兰型）**：
  - **结构外形**：滑块两侧带有明显对称外伸的安装翼缘翼板（Flange）；
  - **安装螺孔**：法兰上同时加工有沉孔与螺纹，**既支持从上往下穿孔锁紧，也支持从底板下方自下往上拧入螺纹**；
  - **适用场景**：承载水平工作台、大面积定位治具板，横向抗翻转力矩力臂更大。

---

#### 2. 预紧等级（Preload）与应用匹配
- **轻预紧 (ZA，预紧力 0.02C)**：
  - **特点**：滑动阻力极小，运行轻快平稳；
  - **适用工况**：负载轻、要求高速静音的搬运机构、CCD 视觉扫描轴、包装流水线上料轴；
- **中预紧 (ZB，预紧力 0.05~0.07C)**：
  - **特点**：完全消除反向死区间隙，具有优良的刚度与抗冲击吸振能力；
  - **适用工况**：承受切削抗力或悬臂力矩的机构，如机加雕铣机、精密贴片机、冲裁模具导向机构。"""
    }
]

sel_sft_file = os.path.join(OUTPUT_DIR, "standard_components_selection_sft.jsonl")
with open(sel_sft_file, "w", encoding="utf-8") as f:
    for idx, s in enumerate(selection_samples):
        record = {
            "id": s["id"],
            "topic": s["topic"],
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": s["prompt"]},
                {"role": "assistant", "content": s["response"]}
            ]
        }
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

print(f"Saved {len(selection_samples)} standard component selection SFT records -> {sel_sft_file}")
