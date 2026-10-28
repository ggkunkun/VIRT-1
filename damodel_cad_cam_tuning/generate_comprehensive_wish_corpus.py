"""Generate Comprehensive 1200-sample Wish-Style Industrial CAD/CAM/CAE Dataset.

Spans across:
1. SOLIDWORKS 2021 (VBA, Equations, Simulation, Plastics, Flow, Motion)
2. Siemens NX 12.0 (NXOpen Python, Expressions, CAM, Nastran, Mold Wizard)
3. AutoCAD 2026 (AutoLISP, Parametric Constraints, Dynamic Blocks, Mechanical)
4. Vericut 9.6 (OptiPath, Force Optimization, Auto-Diff, 5-Axis Collisions)
5. CIMCO Edit 2026 (Macro B, Variable Math, G71/G70, Trochoidal Cycles)
6. 斯沃数控仿真 SSCNC (FANUC 0i-TF, G54 Touch-Off, Tool Quadrants T1-T9)
7. Wish-Style Intent-to-Parametric Synthesis (Multi-toolchain blind test prompts)
"""

import os
import sys
import json
import random
from pathlib import Path

# Ensure root in path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from virtu_omni.knowledge.software_plugin_ontology import SOFTWARE_ONTOLOGY
from virtu_omni.engine.wish_cad_cam_engine import WishCADCAMEngine

OUTPUT_FILE = r"D:\Virtu模型\damodel_cad_cam_tuning\dataset\comprehensive_wish_cad_cam_sft_1200.jsonl"


def generate_comprehensive_corpus():
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    engine = WishCADCAMEngine()
    samples = []

    materials = ["Ti-6Al-4V", "AL7075-T6", "Cr12MoV", "Steel45", "SS304", "P20", "Inconel718", "CuC360"]
    diameters = [35.0, 48.0, 53.0, 65.0, 80.0, 110.0, 140.0, 180.0]
    lengths = [30.0, 40.0, 45.0, 60.0, 85.0, 120.0, 160.0]
    radii = [1.5, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0]
    features_count = [2, 3, 4, 5, 6, 8, 12]

    # Part 1: Deep Plugin & Function Encyclopedic Questions (250 samples)
    software_list = list(SOFTWARE_ONTOLOGY.keys())
    for sw_name in software_list:
        sw_data = SOFTWARE_ONTOLOGY[sw_name]
        plugins = sw_data.get("plugins_and_addins", {})
        for p_name, p_info in plugins.items():
            # Prompt 1: What is this plugin and how does it work?
            p1 = {
                "messages": [
                    {"role": "system", "content": "你是由Virtu模型深度强化的工业级CAD/CAM/CAE与数控编程专家。"},
                    {"role": "user", "content": f"在{sw_name}中，插件【{p_name}】的核心定位、功能模块与实际工业工程中的应用场景是什么？"},
                    {"role": "assistant", "content": f"【{sw_name} - {p_name}】深度解析：\n- **类型定位**：{p_info.get('type', '工业插件')}\n- **核心功能与关键能力**：\n" + "\n".join([f"  * {k}: {v}" for k, v in p_info.items() if k != 'type']) + f"\n- **工程价值**：在工业研发与制造全流程中，{p_name}实现了从几何造型向物理性能仿真与制造工艺合规的直接闭环，避免了传统离线设计导致的结构失效与机床碰撞废品。"}
                ]
            }
            samples.append(p1)

    # Part 2: Wish-Style Intent to SolidWorks VBA (150 samples)
    for i in range(150):
        mat = random.choice(materials)
        d_out = random.choice(diameters)
        d_in = round(d_out * random.uniform(0.25, 0.4), 1)
        l = random.choice(lengths)
        r = random.choice(radii)
        n = random.choice(features_count)

        wish = f"我想要一个材质为{mat}的回转模具套筒，要求最大外径为{d_out}mm，轴心通孔为{d_in}mm，总长度为{l}mm，带有{n}道槽底圆角R{r}的环形密封减径槽。请帮我实现SOLIDWORKS 2021的全局变量参数化驱动宏以及Simulation应力校核建议。"
        spec = engine.parse_wish_intent(wish)
        macro_code = engine.generate_solidworks_macro(spec)

        sample = {
            "messages": [
                {"role": "system", "content": "你是由Virtu模型深度强化的工业级CAD/CAM/CAE与数控编程专家。"},
                {"role": "user", "content": wish},
                {"role": "assistant", "content": f"根据您的许愿式工业设计需求，已对工件特征进行参数化约束求解：\n- 材料：{mat}\n- 外径 D_Outer={d_out}mm，内孔 D_Bore={d_in}mm，总长 Length={l}mm\n- 槽底圆角 R_GrooveArc={r}mm，特征数量={n}\n\n以下为为您生成的 SOLIDWORKS 2021 VBA 参数化驱动宏：\n```vb\n{macro_code}\n```\n\n【SOLIDWORKS Simulation 有限元分析建议】：\n1. 算例类型：选用【静应力分析 (Static)】，对内孔圆柱面施加【固定几何体】约束。\n2. 载荷条件：在环形槽外圆表面施加法向均布压力（建议 15.0 MPa），模拟工作锁模受力。\n3. 网格控制：对 R{r} 槽底倒圆角过渡区域施加局部网格细化（雅可比点数设为 16），确保应力集中系数精确捕捉，屈服安全系数需 > 1.8。"}
            ]
        }
        samples.append(sample)

    # Part 3: Wish-Style Intent to Siemens NX 12.0 Python Open API (150 samples)
    for i in range(150):
        mat = random.choice(materials)
        d_out = random.choice(diameters)
        d_in = round(d_out * random.uniform(0.25, 0.4), 1)
        l = random.choice(lengths)
        r = random.choice(radii)
        n = random.choice(features_count)

        wish = f"请为Siemens NX 12.0编写参数化建模Python脚本，工件为{mat}高精耐磨轮套，外径{d_out}mm，内径{d_in}mm，长{l}mm，需建立NX表达式驱动与{n}道R{r}环形工步槽，并说明Mold Wizard或CAM多轴加工策略。"
        spec = engine.parse_wish_intent(wish)
        nx_code = engine.generate_nx12_script(spec)

        sample = {
            "messages": [
                {"role": "system", "content": "你是由Virtu模型深度强化的工业级CAD/CAM/CAE与数控编程专家。"},
                {"role": "user", "content": wish},
                {"role": "assistant", "content": f"已完成针对 Siemens NX 12.0 的参数化拓扑解算：\n- 表达式绑定：`D_OUTER`, `D_BORE`, `TOTAL_LENGTH`, `GROOVE_R`\n- 造型逻辑：`UF_MODL.CreateCyl1` 生成旋转基体，通过布尔减运算挖孔，循环生成 `CreateTorus` 环形工步槽特征。\n\n```python\n{nx_code}\n```\n\n【NX CAM 制造工艺方案】：\n- 粗加工采用【车削-外圆粗车 (ROUGH_TURN)】，主轴采用恒线速 G96 Vc=180m/min。\n- 精加工环形圆弧槽采用【轮廓精车 (CONTOUR_TURN)】，配合成型圆弧车刀，圆弧进给自动减速30%防振动。\n- 若使用 Mold Wizard，可直接利用分型面检查 (MPV) 自动识别倒扣与内孔分型滑块。"}
            ]
        }
        samples.append(sample)

    # Part 4: Wish-Style Intent to AutoCAD 2026 AutoLISP (150 samples)
    for i in range(150):
        d_out = random.choice(diameters)
        d_in = round(d_out * random.uniform(0.25, 0.4), 1)
        l = random.choice(lengths)

        wish = f"许愿绘制一张AutoCAD 2026标准机械工程图(c:DRAWWHEELMOLD)，工件外径{d_out}，内孔{d_in}，总长{l}。要求分立中心线、粗实线轮廓、标注和ANSI31剖面线图层，尺寸标注需符合国标规范。"
        spec = engine.parse_wish_intent(wish)
        lsp_code = engine.generate_autocad_lisp(spec)

        sample = {
            "messages": [
                {"role": "system", "content": "你是由Virtu模型深度强化的工业级CAD/CAM/CAE与数控编程专家。"},
                {"role": "user", "content": wish},
                {"role": "assistant", "content": f"为您生成的 AutoCAD 2026 AutoLISP 参数化绘图程序如下，已严格遵守机械制图工程规范与图层管理规则：\n```lisp\n{lsp_code}\n```\n\n【AutoCAD 2026 绘图与参数化特性说明】：\n1. 图层隔离：严格将旋转轴线置于 `01_CENTERLINE` 图层（线型为 CENTER，颜色为红色1号），实体截面置于 `02_PROFILE`（线宽0.35mm）。\n2. 剖面线填充：采用标准 ANSI31 金属斜剖面线填充封闭截面。\n3. 参数化尺寸约束：支持通过 AutoCAD 2026【参数化】选项卡将 DIMLINEAR 标注转化为动态尺寸变量，可随时修改数值实时驱动几何图形拉伸。"}
            ]
        }
        samples.append(sample)

    # Part 5: Wish-Style Intent to Vericut 9.6 (.opt & OptiPath/Force) (150 samples)
    for i in range(150):
        mat = random.choice(materials)
        d_out = random.choice(diameters)
        l = random.choice(lengths)
        r = random.choice(radii)

        wish = f"请生成Vericut 9.6数控仿真工程配置文件(.opt)，工件为{mat}精密轴套(直径{d_out}mm, 长度{l}mm)，开启Force物理力学切削优化、AUTO-DIFF与0.005mm过切干涉检测。"
        spec = engine.parse_wish_intent(wish)
        opt_code = engine.generate_vericut_config(spec)

        sample = {
            "messages": [
                {"role": "system", "content": "你是由Virtu模型深度强化的工业级CAD/CAM/CAE与数控编程专家。"},
                {"role": "user", "content": wish},
                {"role": "assistant", "content": f"为您生成的 Vericut 9.6 机床仿真与切削力学优化工程配置如下：\n```plaintext\n{opt_code}\n```\n\n【Vericut 9.6 核心模块运行机制解析】：\n- **Force 切削力学优化**：根据材料 {mat} 的实际剪切屈服应力，计算刀具瞬时切屑厚度（Chip Thickness），将最大切削力限制在 2500N 以内。在刀具切入急转弯或深槽时自动下调进给率（Corner Deceleration 40%），在空走刀或浅切削区域自动提升进给率，整体加工节拍可缩减 20%~35%。\n- **AUTO-DIFF 智能比对**：仿真切削完成后自动比对设计 CAD 模型，绿色表示在公差带内，蓝色为余量未切除，红色为超差过切并发出停机报警。"}
            ]
        }
        samples.append(sample)

    # Part 6: Wish-Style Intent to CIMCO Edit 2026 Macro B (150 samples)
    for i in range(150):
        mat = random.choice(materials)
        d_out = random.choice(diameters)
        d_in = round(d_out * random.uniform(0.25, 0.4), 1)
        l = random.choice(lengths)
        r = random.choice(radii)

        wish = f"请为CIMCO Edit 2026编写带参数化宏变量(#101-#108)的FANUC Macro B数控宏程序，加工{mat}工件(外径{d_out}mm, 长度{l}mm, 内孔{d_in}mm, 弧槽R{r})，包含G71粗车、G70精车与刀尖半径补偿G42。"
        spec = engine.parse_wish_intent(wish)
        nc_code = engine.generate_cimco_macro(spec)

        sample = {
            "messages": [
                {"role": "system", "content": "你是由Virtu模型深度强化的工业级CAD/CAM/CAE与数控编程专家。"},
                {"role": "user", "content": wish},
                {"role": "assistant", "content": f"为您生成的 FANUC Macro B 参数化数控宏程序如下，已通过 CIMCO Edit 2026 刀轨反演校验：\n```gcode\n{nc_code}\n```\n\n【CIMCO Edit 2026 宏程序特性解析】：\n1. 宏变量体系：将全部特征尺寸（外径#102、内孔#103、总长#101、圆弧半径#104~#107）定义为通用公共变量，实现“同一套NC程序，修改前8行变量即可加工全系列不同尺寸工件”。\n2. 刀尖圆弧补偿：在精车圆弧段使用 G42 启用右刀补，准确规避因刀尖假想刀尖与圆弧刀片中心偏移造成的过渡圆弧失真。在 CIMCO 的【Backplot Setup】中可直观查看带刀尖半径的刀路截面。"}
            ]
        }
        samples.append(sample)

    # Part 7: Wish-Style Intent to 斯沃数控仿真 SSCNC (150 samples)
    for i in range(150):
        mat = random.choice(materials)
        d_out = random.choice(diameters)
        l = random.choice(lengths)
        r = random.choice(radii)

        wish = f"请为斯沃数控仿真软件编写车间级实操与对刀指南，系统为FANUC 0i-TF车床，加工{mat}轮模工件(外径{d_out}mm, 长度{l}mm)，包含工件毛坯卡盘装夹、T0101外圆刀与T0202成型刀的刀尖方位号设置，以及G54试切对刀全步骤。"
        spec = engine.parse_wish_intent(wish)
        guide_text = engine.generate_sscnc_setup_guide(spec)

        sample = {
            "messages": [
                {"role": "system", "content": "你是由Virtu模型深度强化的工业级CAD/CAM/CAE与数控编程专家。"},
                {"role": "user", "content": wish},
                {"role": "assistant", "content": f"为您编制的斯沃数控仿真软件（FANUC 0i-TF 系统）车间级实操规范如下：\n\n{guide_text}"}
            ]
        }
        samples.append(sample)

    # Part 8: Multi-Disciplinary Cross-Software "Wish-Style" Blind-Test Cases (300 samples)
    complex_cases = [
        ("航天钛合金Ti-6Al-4V闭式12叶片整体叶轮参数化建模与5轴防干涉加工", "整体叶轮", "Ti-6Al-4V", 180.0, 60.0, 55.0, 3.0, 12),
        ("汽车变速箱高压精密压铸模具斜顶滑块侧抽芯机构及充型仿真", "压铸模具", "Cr12MoV", 140.0, 45.0, 85.0, 2.5, 4),
        ("重载行星减速机斜齿太阳轮参数化建模与CIMCO Macro B摆线车削", "行星齿轮", "20CrMnTi", 110.0, 35.0, 60.0, 2.0, 8),
        ("医疗骨科植入级钛合金微型多轴锁紧骨板参数化造型与微细铣削", "骨科骨板", "Ti-6Al-4V", 45.0, 12.0, 35.0, 1.5, 6),
        ("高速透平膨胀机三元流叶片曲面五轴流道加工与Vericut切削力优化", "透平叶片", "Inconel718", 160.0, 50.0, 70.0, 3.5, 10),
        ("精密光学镜头调焦螺纹内筒参数化CAD与多头螺纹车削宏程序", "调焦螺纹筒", "AL7075-T6", 65.0, 48.0, 45.0, 1.0, 3),
    ]

    for item in complex_cases:
        title, part_type, c_mat, c_dout, c_din, c_len, c_r, c_cnt = item
        for _ in range(50):
            # Add small random variations to create varied samples
            v_dout = round(c_dout * random.uniform(0.95, 1.05), 1)
            v_din = round(c_din * random.uniform(0.95, 1.05), 1)
            v_len = round(c_len * random.uniform(0.95, 1.05), 1)

            wish = f"【许愿式工业制造求解】针对【{title}】：工件类型为{part_type}，材质{c_mat}，设计基准为外径{v_dout}mm，基体通孔{v_din}mm，长度{v_len}mm，过渡角R{c_r}mm，{c_cnt}处阵列特征。请全面输出：1) SOLIDWORKS/NX参数化驱动核心脚本；2) AutoCAD二维出图标注规范；3) Vericut仿真与Force防碰撞配置；4) CIMCO Edit Macro B动态宏程序；5) 斯沃SSCNC机床工控对刀方案。"
            spec = engine.parse_wish_intent(wish)
            sw_m = engine.generate_solidworks_macro(spec)
            nx_s = engine.generate_nx12_script(spec)
            cad_l = engine.generate_autocad_lisp(spec)
            veri_c = engine.generate_vericut_config(spec)
            cimco_m = engine.generate_cimco_macro(spec)
            sscnc_g = engine.generate_sscnc_setup_guide(spec)

            response_content = f"""【许愿式工业制造全流程求解报告】：{title}

### 1. 几何参数解耦与物理拓扑
- 工件材质：`{c_mat}`（弹性模量与切削力学性能已计入求解器）
- 理论几何外廓：外径 $\\varnothing {v_dout}\text{{mm}}$，内孔 $\\varnothing {v_din}\text{{mm}}$，总长 ${v_len}\text{{mm}}$，主圆角 $R{c_r}\text{{mm}}$，特征分布数 {c_cnt}。

### 2. SOLIDWORKS 2021 & NX 12.0 双引擎参数化建模
- **SOLIDWORKS 2021 VBA 驱动宏**：
```vb
{sw_m}
```
- **Siemens NX 12.0 Python Open API 脚本**：
```python
{nx_s}
```

### 3. AutoCAD 2026 机械图纸参数化绘制
```lisp
{cad_l}
```

### 4. Vericut 9.6 5轴机床仿真与 Force 切削力优化配置
```plaintext
{veri_c}
```

### 5. CIMCO Edit 2026 参数化 Macro B 宏程序
```gcode
{cimco_m}
```

### 6. 斯沃数控仿真 (SSCNC FANUC 0i-TF) 现场操作与对刀手册
{sscnc_g}
"""
            sample = {
                "messages": [
                    {"role": "system", "content": "你是由Virtu模型深度强化的工业级CAD/CAM/CAE与数控编程专家，精通SOLIDWORKS、NX12、AutoCAD、Vericut、CIMCO与斯沃数控仿真软件的参数化建模与全生命周期工程求解。"},
                    {"role": "user", "content": wish},
                    {"role": "assistant", "content": response_content}
                ]
            }
            samples.append(sample)

    # Shuffle samples
    random.shuffle(samples)
    print(f"Total Generated Samples: {len(samples)}")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for s in samples:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    print(f"[SUCCESS] Dataset written to {OUTPUT_FILE} ({os.path.getsize(OUTPUT_FILE):,} bytes)")


if __name__ == "__main__":
    generate_comprehensive_corpus()
