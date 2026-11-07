# -*- coding: utf-8 -*-
r"""
build_handbook_knowledge_and_qa.py
Processes:
  e:\迅雷下载\机械设计手册 第六版  PDF(高清) (15 PDFs -> 5 deduplicated volumes)
Extracts:
  1. TOC (Table of Contents) from all 5 unique volumes via PyMuPDF
  2. Dense engineering knowledge chunks for RAG
  3. Professional mechanical engineering calculation SFT pairs (formula derivation, strength check, sizing)
Outputs to:
  e:\新建文件夹 (3)\03_MECHANICAL_HANDBOOK_RAG_AND_QA\
"""

import os
import sys
import json
import fitz # PyMuPDF

sys.stdout.reconfigure(encoding='utf-8')

PDF_DIR = r"e:\迅雷下载\机械设计手册 第六版  PDF(高清)"
OUTPUT_DIR = r"e:\新建文件夹 (3)\03_MECHANICAL_HANDBOOK_RAG_AND_QA"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Select deduplicated canonical volume files
canonical_volumes = [
    {"vol": 1, "filename": "机械设计手册 第六版 第1卷.PDF", "title": "第1卷：常用设计资料、工程材料、公差与配合、机械力学"},
    {"vol": 2, "filename": "机械设计手册 第六版 第2卷.PDF", "title": "第2卷：连接紧固、轴与联轴器、弹簧、齿轮传动、轮系"},
    {"vol": 3, "filename": "机械设计手册 第六版 第3卷.PDF", "title": "第3卷：轴承、润滑、密封、管件及管道附件"},
    {"vol": 4, "filename": "机械设计手册 第六版 第4卷.PDF", "title": "第4卷：减速器、变速器、常用电动机及传动装置"},
    {"vol": 5, "filename": "机械设计手册 第六版 第5卷.PDF", "title": "第5卷：液压传动与控制、气压传动与控制"}
]

print("1. Extracting TOC from canonical volumes ...")
all_tocs = {}
knowledge_chunks = []

for vinfo in canonical_volumes:
    fp = os.path.join(PDF_DIR, vinfo["filename"])
    if not os.path.exists(fp):
        # Fallback to (1) if needed
        fp = os.path.join(PDF_DIR, f"-{vinfo['filename']}")
    
    print(f"Reading Volume {vinfo['vol']}: {os.path.basename(fp)} ...")
    doc = fitz.open(fp)
    toc = doc.get_toc() # [[lvl, title, page], ...]
    page_count = len(doc)
    
    clean_toc = []
    for item in toc:
        lvl, title, page = item
        clean_title = title.strip().replace('\xa0', ' ')
        clean_toc.append({"level": lvl, "title": clean_title, "page": page})
    
    all_tocs[f"volume_{vinfo['vol']}"] = {
        "volume": vinfo["vol"],
        "title": vinfo["title"],
        "filename": os.path.basename(fp),
        "total_pages": page_count,
        "toc_entries_count": len(clean_toc),
        "toc": clean_toc
    }
    
    # Extract representative knowledge samples across chapters
    # Sample pages with significant text density
    sample_pages = [15, 50, 120, 300, 500, 800, 1000]
    for sp in sample_pages:
        if sp < page_count:
            ptext = doc[sp].get_text().strip()
            if len(ptext) > 100:
                knowledge_chunks.append({
                    "volume": vinfo["vol"],
                    "volume_title": vinfo["title"],
                    "page": sp + 1,
                    "text_chunk": ptext[:1500]
                })
    doc.close()

# Save TOC
toc_file = os.path.join(OUTPUT_DIR, "mechanical_handbook_toc.json")
with open(toc_file, "w", encoding="utf-8") as f:
    json.dump(all_tocs, f, ensure_ascii=False, indent=2)
print(f"Saved TOC -> {toc_file}")

# Save Knowledge Chunks
chunk_file = os.path.join(OUTPUT_DIR, "mechanical_handbook_knowledge_chunks.jsonl")
with open(chunk_file, "w", encoding="utf-8") as f:
    for kc in knowledge_chunks:
        f.write(json.dumps(kc, ensure_ascii=False) + "\n")
print(f"Saved {len(knowledge_chunks)} knowledge chunks -> {chunk_file}")

# 3. High-Quality Mechanical Engineering Calculation SFT Dataset
SYSTEM_PROMPT = (
    "你是由 Virtu 工业模型驱动的机械设计计算与工程规范专家。"
    "你精通《机械设计手册 第六版》及 GB/T 国家机械设计规范，"
    "能够精确执行强度校核、寿命计算、公差选用与动力选型，"
    "给出详细公式推导、符号物理意义与工程判定结论。"
)

calculation_qa = [
    {
        "id": "virtu_calc_001",
        "topic": "齿轮传动：标准渐开线直齿圆柱齿轮几何尺寸与弯曲疲劳强度计算",
        "prompt": "已知一对标准渐开线直齿圆柱齿轮传动：小齿轮齿数 z1 = 22，大齿轮齿数 z2 = 88，模数 m = 4.0 mm，压力角 α = 20°，齿顶高系数 ha* = 1.0，顶隙系数 c* = 0.25。传递额定功率 P = 7.5 kW，小齿轮转速 n1 = 960 r/min，载荷平稳，齿宽 b = 40 mm，小齿轮材料为 40Cr（调质硬度 240~280 HBS，弯曲疲劳极限强度 σFlim = 500 MPa）。请计算其几何尺寸（分度圆、齿顶圆、中心距）、圆周力 Ft、转矩 T1，并按《机械设计手册 第六版》校核小齿轮齿根弯曲疲劳强度。",
        "response": """### 机械设计手册第六版 齿轮传动工程校核与几何计算

#### 1. 基本几何尺寸计算
- **传动比 $u$**：
  $$u = \\frac{z_2}{z_1} = \\frac{88}{22} = 4.0$$
- **分度圆直径 $d$**：
  $$d_1 = m \\cdot z_1 = 4.0 \\times 22 = 88.0\\text{ mm}$$
  $$d_2 = m \\cdot z_2 = 4.0 \\times 88 = 352.0\\text{ mm}$$
- **中心距 $a$**：
  $$a = \\frac{d_1 + d_2}{2} = \\frac{88.0 + 352.0}{2} = 220.0\\text{ mm}$$
- **齿顶高 $h_a$ 与齿根高 $h_f$**：
  $$h_a = h_a^* \\cdot m = 1.0 \\times 4.0 = 4.0\\text{ mm}$$
  $$h_f = (h_a^* + c^*) \\cdot m = (1.0 + 0.25) \\times 4.0 = 5.0\\text{ mm}$$
- **齿顶圆直径 $d_a$**：
  $$d_{a1} = d_1 + 2h_a = 88.0 + 2 \\times 4.0 = 96.0\\text{ mm}$$
  $$d_{a2} = d_2 + 2h_a = 352.0 + 2 \\times 4.0 = 360.0\\text{ mm}$$

---

#### 2. 动力参数计算
- **小齿轮额定转矩 $T_1$**：
  $$T_1 = 9550 \\times \\frac{P}{n_1} = 9550 \\times \\frac{7.5}{960} \\approx 74.61\\text{ N}\\cdot\\text{m} = 74610\\text{ N}\\cdot\\text{mm}$$
- **齿面分度圆圆周力 $F_t$**：
  $$F_t = \\frac{2 T_1}{d_1} = \\frac{2 \\times 74610}{88.0} \\approx 1695.7\\text{ N}$$
- **径向力 $F_r$**：
  $$F_r = F_t \\cdot \\tan(\\alpha) = 1695.7 \\times \\tan(20^\\circ) = 1695.7 \\times 0.36397 \\approx 617.2\\text{ N}$$

---

#### 3. 齿根弯曲疲劳强度校核
根据《机械设计手册 第六版 第2卷》齿根弯曲应力计算公式：
$$\\sigma_F = \\frac{2 K T_1 Y_{Fa} Y_{Sa}}{b m^2 z_1} \\le [\\sigma_F]$$
- **载荷系数 $K$**：平稳工况，取使用系数 $K_A = 1.0$、动载系数 $K_v = 1.15$、齿向载荷分布系数 $K_{F\\beta} = 1.1$、齿间载荷分配系数 $K_{F\\alpha} = 1.0$：
  $$K = K_A \\cdot K_v \\cdot K_{F\\beta} \\cdot K_{F\\alpha} = 1.0 \\times 1.15 \\times 1.1 \\times 1.0 = 1.265$$
- **齿形系数 $Y_{Fa1}$ 与应力修正系数 $Y_{Sa1}$**（查手册 $z_1 = 22$）：
  $$Y_{Fa1} = 2.72, \\quad Y_{Sa1} = 1.57$$
- **计算齿根弯曲应力 $\\sigma_F$**：
  $$\\sigma_F = \\frac{2 \\times 1.265 \\times 74610 \\times 2.72 \\times 1.57}{40 \\times 4.0^2 \\times 22} = \\frac{806141}{14080} \\approx 57.25\\text{ MPa}$$
- **许用弯曲应力 $[\\sigma_F]$**：
  $$[\\sigma_F] = \\frac{\\sigma_{Flim} \\cdot Y_{ST} \\cdot Y_{NT}}{S_{Fmin}} = \\frac{500 \\times 2.0 \\times 1.0}{1.4} \\approx 714.3\\text{ MPa}$$

**工程判定结论**：
$\\sigma_F = 57.25\\text{ MPa} \\ll [\\sigma_F] = 714.3\\text{ MPa}$，安全裕度充裕，小齿轮齿根弯曲疲劳强度完全合格！"""
    },
    {
        "id": "virtu_calc_002",
        "topic": "轴承技术：深沟球轴承基本额定动载荷与 L10h 寿命校核计算",
        "prompt": "某自动化传送机构轴承支承采用深沟球轴承 6208（手册额定动载荷 C = 32.5 kN，额定静载荷 C0 = 19.8 kN），工作轴转速 n = 720 r/min。经受力分析，轴承承受径向载荷 Fr = 3.6 kN，轴向载荷 Fa = 1.2 kN，工作温度小于 100℃，运转平稳轻微冲击。请按《机械设计手册 第六版 第3卷》计算该轴承的当量动载荷 P，并校核其额定基本寿命 L10h（小时），判定是否满足设备 20,000 小时的设计寿命要求。",
        "response": """### 机械设计手册第六版 滚动轴承寿命设计校核

#### 1. 判定当量动载荷参数
根据《机械设计手册 第六版 第3卷 第12篇 滚动轴承》：
- **轴向载荷比率**：
  $$\\frac{F_a}{C_0} = \\frac{1.2}{19.8} \\approx 0.0606$$
  查表得判定临界值：$e \\approx 0.26$。
- **比值比较**：
  $$\\frac{F_a}{F_r} = \\frac{1.2}{3.6} = 0.333 > e (0.26)$$
  因为 $F_a / F_r > e$，所以轴向载荷对当量动载荷产生显著影响，查手册取径向系数 $X$ 与轴向系数 $Y$：
  $$X = 0.56, \\quad Y = 1.71$$

---

#### 2. 计算当量动载荷 $P$
- **载荷系数 $f_p$ 与温度系数 $f_t$**：
  - 运转平稳轻微冲击：查表取载荷系数 $f_p = 1.2$；
  - 工作温度 $< 100^\\circ\\text{C}$：取温度系数 $f_t = 1.0$。
- **当量动载荷公式**：
  $$P = f_p (X F_r + Y F_a) = 1.2 \\times (0.56 \\times 3.6 + 1.71 \\times 1.2)$$
  $$P = 1.2 \\times (2.016 + 2.052) = 1.2 \\times 4.068 = 4.882\\text{ kN}$$

---

#### 3. 额定疲劳寿命计算（$L_{10h}$）
对球轴承，寿命指数 $\\epsilon = 3$：
- **基本额定寿命（以 $10^6$ 转为单位）**：
  $$L_{10} = \\left( \\frac{C}{P} \\right)^3 = \\left( \\frac{32.5}{4.882} \\right)^3 = (6.657)^3 \\approx 295.0 \\text{ (百万转)}$$
- **基本额定寿命（以小时计算）**：
  $$L_{10h} = \\frac{10^6}{60 n} \\cdot L_{10} = \\frac{10^6}{60 \\times 720} \\times 295.0 = \\frac{295,000,000}{43200} \\approx 6828.7\\text{ 小时}$$

---

#### 4. 工程评估与优化建议
- **寿命对比**：当前配置计算寿命 $L_{10h} = 6828.7\\text{ 小时} < 20,000\\text{ 小时}$，无法满足 20,000 小时连续生产要求。
- **优化选型方案**：
  1. **升级轴承型号**：改用 6308 深沟球轴承（$C = 42.5\\text{ kN}$），计算寿命可跃升至：
     $$L_{10h}' = 6828.7 \\times \\left( \\frac{42.5}{32.5} \\right)^3 = 6828.7 \\times 2.238 \\approx 15282\\text{ 小时}$$；
  2. **优选角接触球轴承**：因存在持续轴向力 $F_a = 1.2\\text{ kN}$，推荐采用 **7208B (接触角 $\\alpha = 40^\\circ$)** 角接触球轴承，其额定动载荷 $C = 41.5\\text{ kN}$ 且轴向承载系数更高，寿命可达 24,000 小时以上，彻底满足工程指标！"""
    },
    {
        "id": "virtu_calc_003",
        "topic": "气动系统：气缸内径与耗气量选型计算",
        "prompt": "在 3C 自动化设备的夹紧机构中，需要由单杆双作用气缸产生水平夹紧力 F = 850 N，气动系统工作气压 p = 0.5 MPa（5 bar）。气缸行程 s = 100 mm，每分钟往复循环动作 20 次，考虑设备稳定性与阻力损失，负载率取 η = 0.75。请按《机械设计手册 第六版 第5卷 第23篇 气压传动》计算气缸所需内径 D，并在标准气缸直径系列中圆整选型；同时计算该气缸动作的最大自由空气消耗量 Q（L/min）。",
        "response": """### 机械设计手册第六版 气压传动气缸理论推力与耗气量计算

#### 1. 气缸内径 $D$ 理论计算
根据气缸理论输出力计算公式：
$$F_{th} = \\frac{F}{\\eta} = \\frac{850}{0.75} \\approx 1133.3\\text{ N}$$
- 单杆双作用气缸无杆腔理论推力为：
  $$F_{th} = \\frac{\\pi}{4} D^2 \\cdot p$$
- 推导内径 $D$：
  $$D = \\sqrt{\\frac{4 \\cdot F_{th}}{\\pi \\cdot p}} = \\sqrt{\\frac{4 \\times 1133.3}{\\pi \\times 0.5}} = \\sqrt{\\frac{4533.2}{1.5708}} = \\sqrt{2885.9} \\approx 53.72\\text{ mm}$$

---

#### 2. 标准气缸系列圆整选型
根据 GB/T 2348 标准气缸缸径优先系列（... 40, 50, 63, 80, 100 ... mm）：
- $D = 53.72\\text{ mm}$ 介于 50 与 63 之间；
- 若选 ⌀50：在 0.5 MPa 气压下的实际出力仅为 $F = \\frac{\\pi}{4} \\times 50^2 \\times 0.5 \\times 0.75 \\approx 736\\text{ N} < 850\\text{ N}$，出力不足；
- **标准选型决定**：选定缸径 **$D = 63\\text{ mm}$**（如 SMC CDQ2B63-100DZ 或 亚德客 SC63x100）。
- **校核裕度**：
  $$F_{actual} = \\frac{\\pi}{4} \\times 63^2 \\times 0.5 \\times 0.75 = 3117.2 \\times 0.5 \\times 0.75 \\approx 1169\\text{ N} > 850\\text{ N} \\text{ (安全裕度 37.5%)}$$

---

#### 3. 自由空气消耗量 $Q$（ANR 标准状态）计算
根据《机械设计手册 第六版 第5卷》气缸每个往复循环耗气量：
$$q_0 = \\frac{\\pi}{4} D^2 \\cdot s \\cdot \\frac{p + p_a}{p_a} \\times 2$$
其中 $p_a = 0.1013\\text{ MPa}$ 为标准大气压：
- 压力比因子：
  $$\\frac{p + p_a}{p_a} = \\frac{0.5 + 0.1013}{0.1013} \\approx 5.936$$
- 单次双向行程压缩空气容积（换算为自由空气升）：
  $$q_0 = 2 \\times \\left( \\frac{\\pi}{4} \\times 6.3^2 \\times 10 \\right) \\times 5.936 \\times 10^{-3} = 2 \\times 311.72 \\times 5.936 \\times 10^{-3} \\approx 3.70\\text{ L/次}$$
- **总耗气量 $Q$（动作频率 $N = 20\\text{ 次/min}$）**：
  $$Q = q_0 \\cdot N = 3.70 \\times 20 = 74.0\\text{ L/min (ANR)}$$

**工程配置结论**：
选用 **⌀63 mm 缸径、100 mm 行程** 标准气缸，气源系统供给能力须保证不低于 **74 L/min (ANR)**，前级气源处理三联件推荐配置规格为 **AC30A (公称流量 500 L/min)**，电磁阀选用 **通径 1/4\" (4V210-08)** 即可确保气缸动作响应敏捷。"""
    },
    {
        "id": "virtu_calc_004",
        "topic": "公差与配合：GB/T 1800 配合制度选用原则与公差带数值解算",
        "prompt": "在精密减速机输出轴与滚动轴承内圈、外圈与轴承座孔的配合设计中，工作环境温度常温至 65℃，承受中等定向旋转载荷。轴承型号 6208（内径 ⌀40 mm，外径 ⌀80 mm）。请依据《机械设计手册 第六版 第1卷 第3篇 公差与配合》：\n1. 确定轴径与内圈、座孔与外圈的配合制度（基孔制/基轴制）；\n2. 推荐配合公差带代号；\n3. 查明上下偏差数值并计算最大间隙、最大过盈，说明为何轴承外圈与座孔不能选用过盈配合。",
        "response": """### 机械设计手册第六版 滚动轴承配合与公差工程设计

#### 1. 配合制度确定
根据 GB/T 275 及《机械设计手册 第六版 第1卷》：
- **轴与轴承内圈配合**：
  由于滚动轴承为标准外购件，其内圈内孔公差带为特殊基孔制（其公差带位于零线下方，下偏差为零，上偏差为负）；因此轴的加工必须采用 **基孔制**。
- **轴承座孔与轴承外圈配合**：
  轴承外圈外径公差带同样位于零线下方；因此座孔的加工必须采用 **基轴制**。

---

#### 2. 公差带推荐选用
- **轴颈配合代号（承受旋转载荷）**：
  针对 ⌀40 mm 轴颈承受旋转轻中载荷，推荐公差带为 **⌀40k5** 或 **⌀40m5**（高精度机床选 k5，常规选 m5，本例选 **⌀40k5**）。
- **轴承座孔配合代号（承受定向静载荷）**：
  针对 ⌀80 mm 外圈承受局部静止载荷，为允许轴受热伸长时外圈能发生微小轴向游动，推荐公差带为 **⌀80H7** 或 **⌀80J7**（优选 **⌀80H7**）。

---

#### 3. 公差带极限偏差与间隙/过盈计算
##### (1) 轴承内圈与轴颈配合（⌀40 mm）
- **轴承内圈内径公差（0级公差）**：
  上偏差 $ES = 0$，下偏差 $EI = -0.012\\text{ mm}$；
- **轴颈 ⌀40k5 极限偏差**（GB/T 1800.2）：
  上偏差 $es = +0.011\\text{ mm}$，下偏差 $ei = +0.002\\text{ mm}$；
- **配合过盈解算**：
  - 最大过盈 $Y_{max} = es - EI = (+0.011) - (-0.012) = +0.023\\text{ mm} (23\\ \\mu\\text{m})$；
  - 最小过盈 $Y_{min} = ei - ES = (+0.002) - (0) = +0.002\\text{ mm} (2\\ \\mu\\text{m})$；
  - **性质**：属于微量过盈配合，防止轴与内圈内孔发生打滑相对滑动（爬圈）。

##### (2) 轴承外圈与座孔配合（⌀80 mm）
- **轴承外圈外径公差（0级公差）**：
  上偏差 $es = 0$，下偏差 $ei = -0.013\\text{ mm}$；
- **座孔 ⌀80H7 极限偏差**（GB/T 1800.2）：
  上偏差 $ES = +0.030\\text{ mm}$，下偏差 $EI = 0$；
- **配合间隙解算**：
  - 最大间隙 $X_{max} = ES - ei = (+0.030) - (-0.013) = +0.043\\text{ mm} (43\\ \\mu\\text{m})$；
  - 最小间隙 $X_{min} = EI - es = 0 - 0 = 0\\text{ mm}$；
  - **性质**：属于间隙配合（配合性质介于 0 ~ 43 μm）。

---

#### 4. 为什么轴承外圈与座孔不能选用过盈配合？
1. **防止径向游隙被消除**：滚动轴承内部必须保留适量径向内部游隙（如 C0 组游隙约 15~30 μm）。若外圈采用过盈配合，薄壁外圈受孔壁向内挤压收缩，将消除内部游隙，导致运转卡滞、摩擦剧烈、温升过高并快速烧毁；
2. **补偿热膨胀与轴向伸长**：在轴系运转受热时，轴因热胀冷缩会产生微米级伸长。非固定端（游动端）外圈必须能够在座孔中自由轴向滑移，若过盈死锁，轴向热应力将压弯轴或挤裂轴承端盖；
3. **方便拆装与维护**：间隙配合使轴承能够平稳滑入座孔，避免暴力敲击损坏滚道与滚动体。"""
    }
]

# Convert to SFT JSONL format
qa_sft_records = []
for qa in calculation_qa:
    qa_sft_records.append({
        "id": qa["id"],
        "topic": qa["topic"],
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": qa["prompt"]},
            {"role": "assistant", "content": qa["response"]}
        ]
    })

qa_sft_file = os.path.join(OUTPUT_DIR, "mechanical_calculation_qa_sft.jsonl")
with open(qa_sft_file, "w", encoding="utf-8") as f:
    for r in qa_sft_records:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print(f"Saved {len(qa_sft_records)} calculation QA records -> {qa_sft_file}")
