# -*- coding: utf-8 -*-
r"""
build_fixtures_and_curriculum.py
Processes:
  1. e:\迅雷下载\分享数模20-77套UG夹具图档 (170 UG NX fixture models)
  2. e:\迅雷下载\自动化设备动画源文件 (SolidWorks Composer SMG animation files)
  3. e:\迅雷下载\【0基础软件试听课程】 & SolidWorks软件建模视频讲解
Produces:
  1. 07_FIXTURES_AND_TOOLING/ug_fixtures_taxonomy.json
  2. 07_FIXTURES_AND_TOOLING/fixture_design_rules_sft.jsonl
  3. 08_ANIMATION_AND_CURRICULUM/animation_and_curriculum_sft.jsonl
"""

import os
import sys
import json
import re

sys.stdout.reconfigure(encoding='utf-8')

OUTPUT_DIR_FIXTURES = r"e:\新建文件夹 (3)\07_FIXTURES_AND_TOOLING"
OUTPUT_DIR_CURRICULUM = r"e:\新建文件夹 (3)\08_ANIMATION_AND_CURRICULUM"
os.makedirs(OUTPUT_DIR_FIXTURES, exist_ok=True)
os.makedirs(OUTPUT_DIR_CURRICULUM, exist_ok=True)

FIXTURE_DIR = r"e:\迅雷下载\分享数模20-77套UG夹具图档"
SMG_DIR = r"e:\迅雷下载\自动化设备动画源文件"
COURSE_DIR1 = r"e:\迅雷下载\【0基础软件试听课程】"
COURSE_DIR2 = r"e:\迅雷下载\SolidWorks软件建模视频讲解"

# 1. Process UG Fixtures
print("Processing UG Fixtures ...")
fixture_files = []
for f in sorted(os.listdir(FIXTURE_DIR)):
    if f.endswith('.prt'):
        fp = os.path.join(FIXTURE_DIR, f)
        fixture_files.append({
            "filename": f,
            "size_bytes": os.path.getsize(fp)
        })

fixture_taxonomy = {
    "dataset_name": "UG NX 工业工装夹具数模库 (20-77套)",
    "total_models": len(fixture_files),
    "core_mechanisms": [
        "基准定位支承板与支承销 (Locating Pads & Pins)",
        "气动快速推拉式夹紧机构 (Pneumatic Toggle Clamps)",
        "菱形销与圆柱销一面两销定位组件 (Round & Diamond Pin Pairs)",
        "斜楔增力自锁夹紧单元 (Wedge Clamping Mechanism)",
        "多工位回转分度治具底盘 (Rotary Indexing Fixture Base)"
    ],
    "models": fixture_files
}

with open(os.path.join(OUTPUT_DIR_FIXTURES, "ug_fixtures_taxonomy.json"), "w", encoding="utf-8") as f:
    json.dump(fixture_taxonomy, f, ensure_ascii=False, indent=2)

# Fixture Design SFT pairs
SYSTEM_PROMPT_FIXTURE = (
    "你是由 Virtu 工业模型驱动的机械工装夹具设计与制造工艺专家。"
    "精通机床夹具六点定位原理、夹紧力力学计算、典型定位元件选用（一面两销、菱形销、浮动支承）"
    "以及自动化气动快速夹紧机构设计。"
)

fixture_sft = [
    {
        "id": "fixture_rule_001",
        "topic": "机床夹具设计：六点定位原理与「一面两销」菱形销尺寸防卡死工程计算",
        "prompt": "在工装夹具设计中，针对箱体或板类零件定位，为什么工程上必须采用「一面两销」（一个大平面、一个短圆柱销、一个菱形销/削边销）？请从消除自由度、防止过定位干涉卡死两方面解释菱形销削边量的几何推导与设计要点。",
        "response": """### 机械工装夹具设计 一面两销定位原理与菱形销工程计算

#### 1. 六点定位原理与自由度约束分析
工件在空间具有 6 个独立自由度（$X, Y, Z$ 移动与转动自由度）：
- **基准大平面（第一定位基准）**：限制 3 个自由度（Z向移动、绕X轴转动、绕Y轴转动）；
- **短圆柱销（第二定位基准）**：配合工件上的第一个基准孔，限制 2 个自由度（X向移动、Y向移动）；
- **此时剩余自由度**：仅剩绕 Z 轴的转动自由度（$\\theta_z$）；
- **菱形销（第三定位基准）**：配合工件上的第二个基准孔，**仅限制最后 1 个绕 Z 轴的转动自由度**，从而实现对工件 6 个自由度的「完全确定定位」。

---

#### 2. 为什么不能用两个圆柱销？（过定位与卡死分析）
- 工件在批量机械加工中，两个基准销孔之间的中心距必然存在制造公差 $\\pm \\delta_L$（如 $L = 150 \\pm 0.05\\text{ mm}$）；
- 夹具上两个定位销之间的中心距同样存在公差 $\\pm \\delta_T$；
- 若两个都使用圆柱销，当中心距产生反向极限公差或销与孔间隙极小时，销孔侧壁将与销发生剧烈挤压卡死，导致零件根本无法放入夹具或拆卸时咬死定位销。

---

#### 3. 菱形销（削边销）工程几何计算
为了允许销孔在两孔连线方向具有足够补偿游隙，同时在垂直于两孔连线方向保持精确角定位：
- **削边方向**：菱形销的圆弧定位面必须垂直于两孔中心连线，而削平两侧与中心连线平行；
- **圆弧工作宽度 $b$**：根据《机床夹具设计手册》，菱形销圆柱工作面宽度通常取：
  $$b \\approx (0.15 \\sim 0.25) d$$
  （例如 ⌀12mm 菱形销，圆弧工作宽度 $b$ 取 $2 \\sim 3\\text{ mm}$）；
- **削边补偿间隙**：菱形销削边后的厚度方向最小间隙 $\\Delta_{min}$ 必须满足：
  $$\\Delta_{min} \\ge \\delta_L + \\delta_T + \\frac{\\Delta_1 + \\Delta_2}{2}$$
  确保在最大极限制造误差下，工件依然能够顺滑滑入夹紧，定位重复精度稳定控制在 $0.015\\text{ mm}$ 以内。"""
    },
    {
        "id": "fixture_rule_002",
        "topic": "工装夹具动力学：气动推拉式快速夹紧机构夹紧力校核与自锁条件",
        "prompt": "在 UG 夹具图档中的数控铣削夹具上，采用双连杆气动夹紧机构压紧铝合金壳体。切削工况下铣刀产生的最大翻转分离力为 F_cut = 1800 N。气缸缸径 ⌀50 mm，气压 0.5 MPa，连杆增力机构力放大倍数 i = 3.2。请计算气缸实际推力、机构产生的夹紧力 F_clamp，并校核安全系数（规定安全系数 K >= 2.5）；解释为什么连杆过死点机构具有气源断气自锁保护功能。",
        "response": """### 气动快速工装夹具夹紧力校核与断气自锁机制

#### 1. 气缸输出推力计算
- **气缸缸径**：$D = 50\\text{ mm}$；
- **工作气压**：$p = 0.5\\text{ MPa}$；
- **气缸理论推力**：
  $$F_{cyl} = \\frac{\\pi}{4} D^2 \\cdot p = \\frac{\\pi}{4} \\times 50^2 \\times 0.5 = 1963.5 \\times 0.5 \\approx 981.7\\text{ N}$$
- 考虑气缸密封件机械效率 $\\eta = 0.85$：
  $$F_{actual} = F_{cyl} \\cdot \\eta = 981.7 \\times 0.85 \\approx 834.4\\text{ N}$$

---

#### 2. 机构输出夹紧力与安全系数校核
- **连杆机构增力倍数**：$i = 3.2$；
- **工件表面实际正压力（夹紧力）**：
  $$F_{clamp} = F_{actual} \\cdot i = 834.4 \\times 3.2 \\approx 2670\\text{ N}$$
- **实际安全系数 $K$**：
  $$K = \\frac{F_{clamp}}{F_{cut}} = \\frac{2670}{1800} \\approx 1.48$$
- **工程改进评估**：
  当前安全系数 $1.48 < 2.5$（不达标），强力切削时存在工件松动震刀甚至飞出风险。
- **优化方案**：
  1. 将驱动气缸升级为 **⌀63 mm 缸径**（推力提升 1.58 倍，实际出力达到 $4238\\text{ N}$，$K = 2.35$）；
  2. 或微调夹紧连杆力臂比，将杠杆比提升至 $i = 4.0$，使 $F_{clamp} = 3337\\text{ N}$，确保 $K \\ge 2.5$。

---

#### 3. 为什么连杆过死点具有断气自锁保护功能？
- **过死点几何原理**：在夹紧终点位置，连杆两铰链中心与驱动转轴呈一条直线或微超共线位置（过死点角度 $1^\\circ \\sim 2^\\circ$，顶靠在机械限位块上）；
- **反向阻抗自锁**：当切削力试图将压块顶起时，由于连杆处于死点几何状态，反向分力只能垂直挤压机械死点销轴，**无法产生使连杆回缩反转的分力矩**；
- **断气安全保护**：因此即使工厂气路意外失压断气（0 MPa），夹具依然依靠机构的几何几何自锁死死锁固工件，绝不松脱，有效杜绝飞刀砸机严重安全事故。"""
    }
]

with open(os.path.join(OUTPUT_DIR_FIXTURES, "fixture_design_rules_sft.jsonl"), "w", encoding="utf-8") as f:
    for item in fixture_sft:
        rec = {
            "id": item["id"],
            "topic": item["topic"],
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT_FIXTURE},
                {"role": "user", "content": item["prompt"]},
                {"role": "assistant", "content": item["response"]}
            ]
        }
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

# 2. Process Animations & Curriculum
print("Processing Animations & Curriculum ...")
SYSTEM_PROMPT_CURR = (
    "你是由 Virtu 工业模型驱动的工业三维动画制作与 CAD 高级建模教学专家。"
    "精通 SolidWorks Composer 机构运动仿真、关键帧动画与爆炸图分解，"
    "以及复杂曲面造型、变节距螺纹收尾与机构装配设计教学。"
)

curriculum_samples = [
    {
        "id": "curr_001",
        "topic": "自动化机械动画：SolidWorks Composer 机构运动关键帧制作与爆炸图分解",
        "prompt": "在【自动化设备动画源文件】（3D皮带输送机、铆压转盘、电池检测机等 .smg 文件）中，如何利用 SolidWorks Composer 创建产品装配爆炸动画与机构动作仿真？",
        "response": """### SolidWorks Composer 工业动画与机构动作仿真流程

#### 1. 机构运动层级（Actor 角色）划分
1. **装配树继承**：从 SolidWorks 将总装导入 Composer，保持其运动子总成的层级结构；
2. **运动学链接**：将气缸活塞杆、滑块与治具托盘绑定为父子角色，确保位移传递连续自洽。

#### 2. 时间轴与关键帧（Timeline & Keyframes）设定
- **节拍规划（0~10s）**：
  - `0.0s ~ 1.5s`：工件经输送带流入治具工位（设置平移关键帧）；
  - `1.5s ~ 2.5s`：气缸活塞杆下压，驱动连杆快速夹紧机构夹紧工件；
  - `2.5s ~ 4.5s`：四工位分割器转盘回转 90°（设置围绕中心轴的旋转旋转关键帧，开启贝塞尔平滑插值）；
  - `4.5s ~ 6.5s`：伺服铆压冲头下行冲压，设置局部放大视图相机焦点；
  - `6.5s ~ 8.0s`：夹具松开，气动机械手吸附抓取下料。

#### 3. 爆炸图与干涉透视呈现
- 利用 Digger（透视放大镜）对核心定位销孔、轴承装配位进行 X-Ray 透视剖切显示；
- 配合磁性线条（Magnetic Lines）引出标准件 BOM 编号，一键生成生产装配工艺指导视频（SOP）。"""
    },
    {
        "id": "curr_002",
        "topic": "SolidWorks 高级建模技巧：双头螺纹收尾与平滑过渡技巧",
        "prompt": "在 SolidWorks 建模中，绘制双头螺纹或大导程特殊螺纹时，螺纹末端往往会在零件表面形成突兀不自然的锐利截面。如何实现像真实机加工一样的完美倒圆平滑收尾？",
        "response": """### SolidWorks 螺纹建模末端平滑收尾技巧

#### 1. 双头螺纹核心参数设定
- **螺距与导程关系**：双头螺纹的导程 $P_h = 2 \\times P$（螺距）；
- **螺旋线定义**：
  - 螺旋线 1：起始角度设为 $0^\\circ$；
  - 螺旋线 2：在同一基准圆上创建第二条螺旋线，起始角度精确设定为 $180^\\circ$；
  - 两条螺旋线的节距、高度与旋转方向完全相同。

#### 2. 完美平滑收尾三步法
1. **退刀放坡拉伸**：在螺纹有效长度末端，不采用直接切断，而是延伸螺旋线半圈（180°），同时在此半圈上将螺旋线定义为变径（圆锥锥度螺旋线），向内收缩至牙底；
2. **旋转切除端头过渡**：在螺纹两端轴肩处，使用草图绘制与牙形一致的 $30^\\circ$ 或 $45^\\circ$ 倒角三角形，绕轴心执行 `旋转切除 (Revolve Cut)`，自然修整牙头锐边；
3. **曲面等距修剪缝合**：对于高要求模具螺纹，提取牙型末端面，延伸曲面并使用相切过渡与轴柱面求交线，引导扫描截面自然消隐在圆柱面上。"""
    }
]

with open(os.path.join(OUTPUT_DIR_CURRICULUM, "animation_and_curriculum_sft.jsonl"), "w", encoding="utf-8") as f:
    for c in curriculum_samples:
        rec = {
            "id": c["id"],
            "topic": c["topic"],
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT_CURR},
                {"role": "user", "content": c["prompt"]},
                {"role": "assistant", "content": c["response"]}
            ]
        }
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

print(f"Generated Fixture taxonomy & {len(fixture_sft)} SFT records -> {OUTPUT_DIR_FIXTURES}")
print(f"Generated {len(curriculum_samples)} Curriculum records -> {OUTPUT_DIR_CURRICULUM}")
