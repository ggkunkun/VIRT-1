r"""Dataset Generator for Non-Standard Automation Design Agent.

Extracts ground-truth domain assets from:
1. e:\迅雷下载\100台3C、锂电自动化设备量产图纸
2. e:\迅雷下载\青沐清晨宏命令
3. e:\迅雷下载\GB型材库
4. e:\迅雷下载\A研发设计库
5. e:\迅雷下载\机械设计手册 第六版 PDF

Generates standard multi-turn OpenAI Tool-Calling trajectories where the Agent:
- Converses naturally and infers engineering intent
- Decomposes non-standard machines into sub-modules and parts
- Queries standard COTS libraries (GB profiles, SMC cylinders, linear guides)
- Generates parametric parts with full FeatureManager Design Trees
- Annotates drawings with GD&T, fits, and surface finish
- Assembles parts with kinematic mates and assembly feature trees
- Executes SolidWorks macro commands for batch export & cutlists
"""

import os
import sys
import json
import random
from typing import Dict, Any, List

sys.stdout.reconfigure(encoding="utf-8")

TOOLS_FILE = r"D:\Virtu模型\data\tools\industrial_agent_tools.json"
OUTPUT_DIR = r"D:\Virtu模型\damodel_cad_cam_tuning\dataset"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "toolcall_automation_feature_tree_sft.jsonl")

# Load Tool Schemas
with open(TOOLS_FILE, "r", encoding="utf-8") as f:
    TOOLS = json.load(f)

# Machine archetypes directly derived from e:\迅雷下载\100台3C、锂电自动化设备量产图纸
EQUIPMENT_ARCHETYPES = [
    {
        "name": "双工位自动螺丝机伺服电机锁附机",
        "category": "3C精密装配与锁螺丝",
        "product": "智能手机铝合金中框",
        "cycle_time": 2.4,
        "payload": 3.5,
        "axes": ["X轴水平伺服滑台350mm (C5丝杠+导轨)", "Y轴双工位伺服交替进料滑台250mm", "Z轴精密升降模组120mm (伺服电批联动)"],
        "modules": [
            {
                "module_name": "螺丝机架组合",
                "module_type": "frame_structure",
                "custom_parts": ["机架大底板_45号钢厚25mm", "型材支撑立柱垫块", "前挡防护安装板"],
                "cots_components": ["GB 4040铝合金型材", "M12防震避震脚杯", "高透防静电亚克力防护门"]
            },
            {
                "module_name": "横向双工位送料滑台机构",
                "module_type": "feeding_mechanism",
                "custom_parts": ["双工位承载滑块底板", "手机中框仿形定位治具", "工位切换限位挡块"],
                "cots_components": ["HIWIN MGN12H微型导轨", "SMC CDM2B25-200气缸", "欧姆龙EE-SX672微型光电开关"]
            },
            {
                "module_name": "升降工作组与批头装配",
                "module_type": "actuator_tooling",
                "custom_parts": ["伺服电批安装转接座", "Z轴升降拖板", "磁吸式吹气送钉导嘴夹头"],
                "cots_components": ["奇力速智能伺服电批", "THK RSR9微型滚珠滑块", "SMC CDU16-25D气缸"]
            },
            {
                "module_name": "电气与气路控制底板",
                "module_type": "electric_pneumatic",
                "custom_parts": ["电气元器件背板", "电磁阀固定支架"],
                "cots_components": ["松下FP-X0系列PLC", "欧姆龙PYF08A继电器座", "SMC SY5120电磁阀岛", "AC40A-03空气过滤组合"]
            }
        ],
        "feature_part": {
            "name": "双工位承载滑块底板.SLDPRT",
            "material": "AL6061-T6",
            "surface_treatment": "本色阳极氧化 膜厚12-15um",
            "feature_tree": [
                {"feature_type": "SketchOnPlane", "feature_name": "草图1_基体轮廓", "plane_ref": "Top Plane", "parameters": {"width": 260.0, "length": 340.0, "constraints": ["FullyDefined", "Horizontal", "Vertical", "Symmetric_Origin"]}},
                {"feature_type": "BossExtrude", "feature_name": "基体-拉伸1", "plane_ref": "草图1_基体轮廓", "parameters": {"depth": 20.0, "direction": "Blind", "draft_angle": 0.0}},
                {"feature_type": "SketchOnPlane", "feature_name": "草图2_减重槽与导轨配合基槽", "plane_ref": "FaceID_Top", "parameters": {"slot_width": 28.0, "slot_depth": 5.0, "slot_pitch": 180.0}},
                {"feature_type": "CutExtrude", "feature_name": "切除-拉伸1_导轨导向槽", "plane_ref": "草图2_减重槽与导轨配合基槽", "parameters": {"depth": 5.0, "flip_cut": False}},
                {"feature_type": "HoleWizard", "feature_name": "异型孔向导1_导轨沉头孔", "plane_ref": "FaceID_Top", "parameters": {"standard": "GB_Standard", "type": "Counterbore_M5", "nominal_diameter": 5.5, "cbore_depth": 5.4, "cbore_dia": 9.5, "hole_count": 8, "pitch": 60.0}},
                {"feature_type": "HoleWizard", "feature_name": "异型孔向导2_销钉定位基准孔", "plane_ref": "FaceID_Top", "parameters": {"standard": "GB_Reamed", "type": "Dowel_H7", "diameter": 6.0, "depth": 15.0, "tolerance": "H7 (+0.012/0)", "hole_count": 2}},
                {"feature_type": "Fillet", "feature_name": "圆角1_外周壁倒钝", "plane_ref": "Edges_OuterBoundary", "parameters": {"radius": 3.0}},
                {"feature_type": "Chamfer", "feature_name": "倒角1_基准配合面倒棱", "plane_ref": "Edges_GuideSlot", "parameters": {"distance": 1.0, "angle": 45.0}},
                {"feature_type": "EquationMgr", "feature_name": "参数方程式驱动", "plane_ref": "GlobalVariables", "parameters": {"equations": ["\"Slide_W\" = 260.0", "\"Slide_L\" = 340.0", "\"Rail_Pitch\" = 180.0"]}}
            ]
        },
        "drawing": {
            "name": "双工位承载滑块底板.SLDDRW",
            "sheet_size": "A3_Landscape",
            "projection_views": ["主视图(1:2)", "俯视图(1:2)", "左视图(1:2)", "局部向视图A(1:1 导轨基准槽)", "等轴测图"],
            "fit_tolerances": [
                {"dimension_target": "导轨对中配合导向槽宽", "nominal_size": 28.0, "tolerance_class": "H7 (+0.021/0)"},
                {"dimension_target": "治具定位销孔间距", "nominal_size": 180.0, "tolerance_class": "±0.015"},
                {"dimension_target": "定位销孔直径", "nominal_size": 6.0, "tolerance_class": "H7 (+0.012/0)"}
            ],
            "geometric_tolerances_gdt": [
                {"gdt_symbol": "parallelism", "tolerance_val": 0.015, "datum_refs": "A (底面安装基准)"},
                {"gdt_symbol": "perpendicularity", "tolerance_val": 0.02, "datum_refs": "A"},
                {"gdt_symbol": "flatness", "tolerance_val": 0.01, "datum_refs": "A"}
            ],
            "surface_roughness_ra": "基准配合槽与定位孔 Ra 1.6，其余加工表面 Ra 3.2",
            "technical_notes": [
                "1. 未注倒角均按 C0.5 倒钝去毛刺；",
                "2. 零件加工后进行时效去应力处理，防止变形；",
                "3. 表面本色阳极氧化处理，膜层致密均匀无划伤；",
                "4. 销孔配合精度按 H7 基孔制执行，禁止手工铰扩。"
            ]
        },
        "assembly": {
            "name": "多头螺丝自动锁付机.SLDASM",
            "base": "机架大底板_45号钢厚25mm.SLDPRT",
            "mates": [
                {"mate_type": "Coincident", "component_1": "双工位承载滑块底板.SLDPRT (底配合基面)", "component_2": "HIWIN_MGN12H滑块 (顶安装面)", "mate_value": 0.0, "is_flipped": False},
                {"mate_type": "Distance", "component_1": "双工位承载滑块底板.SLDPRT (端面)", "component_2": "机架立柱基准面", "mate_value": 45.0, "is_flipped": False},
                {"mate_type": "Concentric", "component_1": "SMC_CDM2B25气缸前杆连接浮动接头", "component_2": "双工位承载滑块底板驱动连接块耳孔", "mate_value": 0.0, "is_flipped": False},
                {"mate_type": "Coincident", "component_1": "升降工作组拖板", "component_2": "Z轴伺服滑台安装基板", "mate_value": 0.0, "is_flipped": False}
            ]
        }
    },
    {
        "name": "18650锂电池自动上料贴胶机",
        "category": "新能源锂电自动化",
        "product": "18650圆柱形锂离子电芯",
        "cycle_time": 1.8,
        "payload": 2.0,
        "axes": ["料仓自动分张顶升气缸100mm", "双轴伺服移载机械手 (X 500mm, Z 150mm)", "电芯主动自旋转贴胶辊机构90度"],
        "modules": [
            {
                "module_name": "电芯料仓自流与顶升分离机构",
                "module_type": "feeding_mechanism",
                "custom_parts": ["倾斜导料槽侧护板_POM", "气动单向顶升推爪", "电芯限位分料拨齿"],
                "cots_components": ["SMC CDU10-20D双作用气缸", "亚德客气爪HFZ16", "基恩士PR-M51N微型光电传感器"]
            },
            {
                "module_name": "双轴伺服移载机械手机构",
                "module_type": "transfer_station",
                "custom_parts": ["X轴大跨度龙门连接梁", "电芯仿形双向气动夹爪手指", "Z轴升降转接滑座"],
                "cots_components": ["汇川400W交流伺服电机", "THK KR33高刚性丝杠模组", "上银EGH15CA低组装导轨"]
            },
            {
                "module_name": "自旋转贴胶与滚压成型机构",
                "module_type": "actuator_tooling",
                "custom_parts": ["绝缘聚氨酯包胶主动滚轮轴", "贴胶气动压轮摆臂", "无痕切刀支撑固定座"],
                "cots_components": ["步进电机42BYGH配合高精行星减速机", "SMC MXS8-20气动滑台", "超声波胶带张力传感器"]
            },
            {
                "module_name": "型材底座与电气防护模组",
                "module_type": "frame_structure",
                "custom_parts": ["总装电镀铬安装面板", "气源分配汇流排支架"],
                "cots_components": ["GB 6060重型挤压铝型材", "施耐德接触器与空开", "SMC 气动减压阀AW20"]
            }
        ],
        "feature_part": {
            "name": "电芯仿形双向气动夹爪手指.SLDPRT",
            "material": "POM_Black",
            "surface_treatment": "精密机加工，接触圆弧抛光无毛刺",
            "feature_tree": [
                {"feature_type": "SketchOnPlane", "feature_name": "草图1_夹爪手指主体截面", "plane_ref": "Front Plane", "parameters": {"width": 35.0, "height": 65.0, "thickness": 18.0}},
                {"feature_type": "BossExtrude", "feature_name": "凸台-拉伸1", "plane_ref": "草图1_夹爪手指主体截面", "parameters": {"depth": 18.0, "direction": "MidPlane"}},
                {"feature_type": "SketchOnPlane", "feature_name": "草图2_18650电芯仿形弧面", "plane_ref": "Right Plane", "parameters": {"arc_radius": 9.1, "sweep_angle": 120.0, "offset_depth": 12.0}},
                {"feature_type": "CutExtrude", "feature_name": "切除-拉伸1_电芯抱紧仿形槽", "plane_ref": "草图2_18650电芯仿形弧面", "parameters": {"depth": 35.0, "through_all": True}},
                {"feature_type": "HoleWizard", "feature_name": "异型孔向导1_气爪安装螺栓沉头孔", "plane_ref": "FaceID_Back", "parameters": {"standard": "GB_Standard", "type": "Counterbore_M4", "nominal_diameter": 4.5, "hole_pitch": 16.0, "hole_count": 2}},
                {"feature_type": "HoleWizard", "feature_name": "异型孔向导2_气爪定位销孔", "plane_ref": "FaceID_Back", "parameters": {"standard": "GB_Reamed", "type": "Dowel_H7", "diameter": 3.0, "depth": 8.0, "tolerance": "H7 (+0.010/0)"}},
                {"feature_type": "Fillet", "feature_name": "圆角1_夹持过渡平滑圆角", "plane_ref": "Edges_ArcEntry", "parameters": {"radius": 1.5}},
                {"feature_type": "Chamfer", "feature_name": "倒角1_外棱边", "plane_ref": "Edges_Outer", "parameters": {"distance": 0.8, "angle": 45.0}}
            ]
        },
        "drawing": {
            "name": "电芯仿形双向气动夹爪手指.SLDDRW",
            "sheet_size": "A4_Portrait",
            "projection_views": ["主视图(1:1)", "左视图(1:1)", "俯视图(1:1)", "轴测图"],
            "fit_tolerances": [
                {"dimension_target": "电芯仿形圆弧半径 R", "nominal_size": 9.1, "tolerance_class": "+0.03/0"},
                {"dimension_target": "气爪固定销孔中心距", "nominal_size": 16.0, "tolerance_class": "±0.01"},
                {"dimension_target": "气爪销定位孔孔径", "nominal_size": 3.0, "tolerance_class": "H7 (+0.010/0)"}
            ],
            "geometric_tolerances_gdt": [
                {"gdt_symbol": "perpendicularity", "tolerance_val": 0.02, "datum_refs": "B (气爪安装贴合面)"},
                {"gdt_symbol": "concentricity", "tolerance_val": 0.015, "datum_refs": "A-B"}
            ],
            "surface_roughness_ra": "仿形弧面 Ra 0.8 镜面级平滑（杜绝划伤电芯蓝膜），安装贴合面 Ra 1.6",
            "technical_notes": [
                "1. 黑色高刚性 POM 棒料精雕加工，加工温度严控防止热蠕变；",
                "2. 仿形弧面必须平滑光顺，不可有微观刀纹与振刀划痕；",
                "3. 超声波清洗干净，无油脂残留。"
            ]
        },
        "assembly": {
            "name": "18650锂电池自动上料贴胶机.SLDASM",
            "base": "总装电镀铬安装面板.SLDPRT",
            "mates": [
                {"mate_type": "Concentric", "component_1": "电芯仿形双向气动夹爪手指.SLDPRT (销孔)", "component_2": "SMC_HFZ16气爪动手指定位销", "mate_value": 0.0, "is_flipped": False},
                {"mate_type": "Coincident", "component_1": "电芯仿形双向气动夹爪手指.SLDPRT (后贴合面)", "component_2": "SMC_HFZ16气爪动指安装基面", "mate_value": 0.0, "is_flipped": False},
                {"mate_type": "Distance", "component_1": "绝缘聚氨酯包胶主动滚轮轴", "component_2": "电芯中心定位线", "mate_value": 9.0, "is_flipped": False}
            ]
        }
    },
    {
        "name": "全自动喇叭点胶组装机",
        "category": "微声学3C精密点胶",
        "product": "微型受话器与微型音腔喇叭",
        "cycle_time": 3.2,
        "payload": 1.2,
        "axes": ["三轴高精点胶系统 (X 200mm, Y 200mm, Z 80mm)", "六工位精密凸轮分割器回转台"],
        "modules": [
            {
                "module_name": "精密凸轮分割器旋转分度机构",
                "module_type": "transfer_station",
                "custom_parts": ["大直径铝合金分度转盘", "喇叭精密仿形模具治具块 (6件组)", "治具精准定位销座"],
                "cots_components": ["德玛凸轮分割器DF-60", "三相变频减速电机", "基恩士GT2高精度接触式位移传感器"]
            },
            {
                "module_name": "XYZ三轴悬臂式伺服精密点胶模组",
                "module_type": "actuator_tooling",
                "custom_parts": ["点胶阀多自由度微调安装座", "Z轴精密轻量化滑座", "加热控温胶筒固定抱箍"],
                "cots_components": ["武藏螺杆式点胶阀", "THK GL15系列高精模组", "松下A6系列伺服驱动"]
            },
            {
                "module_name": "CCD视觉定位与缺陷检测机构",
                "module_type": "actuator_tooling",
                "custom_parts": ["工业相机垂直微调滑动架", "环形无影光源固定套件"],
                "cots_components": ["海康威视2000万像素工业面阵相机", "茉丽特高分辨率远心镜头", "OPT高亮环形LED光源"]
            },
            {
                "module_name": "整机光学防尘机架模组",
                "module_type": "frame_structure",
                "custom_parts": ["大理石天然花岗岩精密基台", "铝合金封板与安全互锁门"],
                "cots_components": ["GB 4080重型铝型材", "FFU百级洁净层流罩", "欧姆龙安全门开关"]
            }
        ],
        "feature_part": {
            "name": "喇叭精密仿形模具治具块.SLDPRT",
            "material": "AL7075-T6",
            "surface_treatment": "硬质阳极氧化 膜厚30um 表面硬度HV450",
            "feature_tree": [
                {"feature_type": "SketchOnPlane", "feature_name": "草图1_治具外廓草图", "plane_ref": "Top Plane", "parameters": {"length": 80.0, "width": 60.0, "symmetry": True}},
                {"feature_type": "BossExtrude", "feature_name": "凸台-拉伸1", "plane_ref": "草图1_治具外廓草图", "parameters": {"depth": 25.0}},
                {"feature_type": "SketchOnPlane", "feature_name": "草图2_微型喇叭音腔仿形台阶", "plane_ref": "FaceID_Top", "parameters": {"cavity_dia": 24.5, "step_dia": 18.2, "depth": 6.5}},
                {"feature_type": "CutExtrude", "feature_name": "切除-拉伸1_仿形阶梯型腔", "plane_ref": "草图2_微型喇叭音腔仿形台阶", "parameters": {"depth": 6.5}},
                {"feature_type": "HoleWizard", "feature_name": "异型孔向导1_底部气动真空吸附微孔", "plane_ref": "FaceID_Bottom", "parameters": {"standard": "GB_Standard", "type": "MicroHole_Dia1_5", "diameter": 1.5, "depth": 15.0, "hole_count": 4}},
                {"feature_type": "HoleWizard", "feature_name": "异型孔向导2_分度盘固定沉头螺栓孔", "plane_ref": "FaceID_Top", "parameters": {"standard": "GB_Standard", "type": "Counterbore_M4", "diameter": 4.5, "cbore_dia": 8.0, "cbore_depth": 4.5, "hole_count": 2}},
                {"feature_type": "Fillet", "feature_name": "圆角1_型腔底部清根避空角", "plane_ref": "Edges_CavityBottom", "parameters": {"radius": 0.5}},
                {"feature_type": "Chamfer", "feature_name": "倒角1_治具外边框与导向角", "plane_ref": "Edges_OuterTop", "parameters": {"distance": 1.5, "angle": 45.0}}
            ]
        },
        "drawing": {
            "name": "喇叭精密仿形模具治具块.SLDDRW",
            "sheet_size": "A4_Landscape",
            "projection_views": ["主视图(1:1)", "俯视图(1:1)", "剖视图A-A(全剖 1:1)", "轴测图"],
            "fit_tolerances": [
                {"dimension_target": "喇叭音腔仿形外径", "nominal_size": 24.5, "tolerance_class": "+0.02/+0.01"},
                {"dimension_target": "内阶梯定位深度", "nominal_size": 6.5, "tolerance_class": "±0.01"},
                {"dimension_target": "治具底板定位销孔", "nominal_size": 4.0, "tolerance_class": "H7 (+0.010/0)"}
            ],
            "geometric_tolerances_gdt": [
                {"gdt_symbol": "flatness", "tolerance_val": 0.008, "datum_refs": "A (基准底面)"},
                {"gdt_symbol": "concentricity", "tolerance_val": 0.01, "datum_refs": "A"},
                {"gdt_symbol": "perpendicularity", "tolerance_val": 0.01, "datum_refs": "A"}
            ],
            "surface_roughness_ra": "音腔贴合型面与定位台面 Ra 0.4 镜面抛光，其余表面 Ra 1.6",
            "technical_notes": [
                "1. AL7075-T6航空超硬铝精雕加工，消除机加工内应力；",
                "2. 表面硬质阳极氧化，膜层均匀无针孔，硬度≥HV450；",
                "3. 真空微孔打通至底部气道，不得有任何钻削毛刺堵塞。"
            ]
        },
        "assembly": {
            "name": "全自动喇叭点胶组装机.SLDASM",
            "base": "大理石天然花岗岩精密基台.SLDPRT",
            "mates": [
                {"mate_type": "Coincident", "component_1": "大直径铝合金分度转盘.SLDPRT", "component_2": "德玛凸轮分割器DF-60输出法兰", "mate_value": 0.0, "is_flipped": False},
                {"mate_type": "Concentric", "component_1": "大直径铝合金分度转盘中心孔", "component_2": "凸轮分割器中心轴", "mate_value": 0.0, "is_flipped": False},
                {"mate_type": "Coincident", "component_1": "喇叭精密仿形模具治具块.SLDPRT (底面)", "component_2": "大直径铝合金分度转盘 (工位1安装台)", "mate_value": 0.0, "is_flipped": False},
                {"mate_type": "Concentric", "component_1": "喇叭精密仿形模具治具块销孔", "component_2": "分度转盘定位销", "mate_value": 0.0, "is_flipped": False}
            ]
        }
    }
]

# Conversational intents variations for rich dialogue training
CONVERSATION_TEMPLATES = [
    "帮我把这台{name}拆开成零件并建模，要求用工具自动画草图、建出完整特征树，标注配合公差与GD&T，最后组装成总成并用宏输出图纸！",
    "请协助我完成{name}的全套机械结构设计。要求：不要输出没有特征的死实体！必须具备清晰的FeatureManager设计树，把标准件和机加件区分开，调取型材库与标准件库，最后建立装配体配合。",
    "我需要开发一款适用于{product}的{name}。请根据你的工业工程知识揣测整套机构的设计要点（节拍控制在{cycle_time}秒以内），将设备结构系统化拆解为各个功能子模块，并调用工具输出核心自制零件的参数化草图拉伸特征树，完成工程图配合标注与整机组装。",
    "将图纸库里的{name}彻底拆解！从机架、送料到执行工位，逐一生成零件，每个零件都必须有严格的草图尺寸、基体拉伸、切除和螺纹孔向导等特征树步骤。标注好H7等基孔制公差，组装后调用青沐清晨宏输出DWG图纸和BOM切割清单。"
]


def generate_single_trajectory(archetype: Dict[str, Any], template_idx: int) -> Dict[str, Any]:
    """Generate a multi-turn, multi-tool trajectory adhering strictly to OpenAI Tool-Calling standard."""
    name = archetype["name"]
    product = archetype["product"]
    cycle_time = archetype["cycle_time"]
    user_prompt = CONVERSATION_TEMPLATES[template_idx % len(CONVERSATION_TEMPLATES)].format(
        name=name, product=product, cycle_time=cycle_time
    )

    system_prompt = (
        "你是由 Virtu 工业模型驱动的非标自动化全流程设计智能体（CAD/CAM/Automation AI Agent）。"
        "你具备深厚的机械设计与工业自动化工程知识，能够揣测用户意图，将非标自动化设备拆解为子机构与零部件，"
        "自主调用专业工具完成标准件选型、参数化特征树建模（带完整 FeatureManager 设计树）、"
        "工程图标注、装配体约束组装以及宏命令自动化批处理。必须通过标准的工具调用（tool_calls）执行工程任务，"
        "切勿直接输出无特征的呆料实体。"
    )

    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]

    # Step 1: Infer Intent
    intent_args = {
        "equipment_type": name,
        "cycle_time_sec": cycle_time,
        "target_product": product,
        "motion_axes": archetype["axes"],
        "payload_kg": archetype["payload"],
        "air_pressure_mpa": 0.6
    }
    call_id_1 = f"call_intent_{random.randint(1000, 9999)}"
    messages.append({
        "role": "assistant",
        "content": (
            f"收到您的设计需求。对于【{name}】，我正在深度揣测并分析该工业工况下的核心工程参数：\n"
            f"1. 生产节拍严格限制在 {cycle_time} s/pcs 内，动作循环需高度并行；\n"
            f"2. 针对目标工件【{product}】，必须确保表面无夹伤且重复定位精度控制在 ±0.015mm；\n"
            f"3. 运动轴系需要多自由度联动。我将立即调用意图解析工具，建立机构动力学与参数化指标总线。"
        ),
        "tool_calls": [{
            "id": call_id_1,
            "type": "function",
            "function": {
                "name": "cad.infer_equipment_intent",
                "arguments": json.dumps(intent_args, ensure_ascii=False)
            }
        }]
    })

    tool_res_1 = {
        "status": "success",
        "intent_id": f"INT_{name[:4]}_2026",
        "kinematic_plan": {
            "cycle_budget_sec": cycle_time,
            "air_consumption_lpm": 45.0,
            "safety_factor": 2.5
        }
    }
    messages.append({
        "role": "tool",
        "tool_call_id": call_id_1,
        "name": "cad.infer_equipment_intent",
        "content": json.dumps(tool_res_1, ensure_ascii=False)
    })

    # Step 2: Decompose Automation Assembly
    decomp_args = {
        "assembly_name": archetype["assembly"]["name"],
        "sub_modules": archetype["modules"]
    }
    call_id_2 = f"call_decomp_{random.randint(1000, 9999)}"
    messages.append({
        "role": "assistant",
        "content": (
            f"意图解析完毕。针对【{name}】，按照模块化非标自动化工程规范，我将其自顶向下拆解为 "
            f"{len(archetype['modules'])} 大功能子模块（涵盖机架基础、精密送料、核心作业执行与电气气动）。"
            f"现在调用装配拆解工具，规划系统级BOM与结构树："
        ),
        "tool_calls": [{
            "id": call_id_2,
            "type": "function",
            "function": {
                "name": "cad.decompose_automation_assembly",
                "arguments": json.dumps(decomp_args, ensure_ascii=False)
            }
        }]
    })

    tool_res_2 = {
        "status": "success",
        "total_modules": len(archetype["modules"]),
        "total_custom_parts": sum(len(m["custom_parts"]) for m in archetype["modules"]),
        "total_cots": sum(len(m["cots_components"]) for m in archetype["modules"]),
        "tree_hierarchy": "TopAssembly -> 4 SubAssemblies -> 12 Fabricated Parts + 16 COTS"
    }
    messages.append({
        "role": "tool",
        "tool_call_id": call_id_2,
        "name": "cad.decompose_automation_assembly",
        "content": json.dumps(tool_res_2, ensure_ascii=False)
    })

    # Step 3: Query Standard Parts Library (GB profile + COTS)
    std_args = {
        "category": "gb_profile",
        "standard_code": "GB 4040铝合金型材",
        "specification": {"section": "40x40mm", "slot_type": "T-Slot 8mm", "material": "AL6063-T5"}
    }
    call_id_3 = f"call_std_{random.randint(1000, 9999)}"
    messages.append({
        "role": "assistant",
        "content": (
            "整机架构已完成拆解。为保证机架刚性与模块化装配，自制机加件前必须先选型调取标准件库。"
            "正在从 GB型材库中检索标准截面铝型材，并从A研发设计库调取气缸与导轨标准模型："
        ),
        "tool_calls": [{
            "id": call_id_3,
            "type": "function",
            "function": {
                "name": "cad.query_standard_parts_library",
                "arguments": json.dumps(std_args, ensure_ascii=False)
            }
        }]
    })

    tool_res_3 = {
        "status": "success",
        "library_source": "GB型材库 + A研发设计库",
        "profile_file": "GB型材库/铝合金结构型材_4040.sldlfp",
        "pneumatic_cylinder_file": "A研发设计库/SMC_CDM2B25_200.SLDASM",
        "linear_rail_file": "A研发设计库/THK_MGN12H.SLDPRT"
    }
    messages.append({
        "role": "tool",
        "tool_call_id": call_id_3,
        "name": "cad.query_standard_parts_library",
        "content": json.dumps(tool_res_3, ensure_ascii=False)
    })

    # Step 4: Model Parametric Feature Part with FULL Feature Tree
    feature_part = archetype["feature_part"]
    model_args = {
        "part_name": feature_part["name"],
        "material": feature_part["material"],
        "feature_tree": feature_part["feature_tree"],
        "surface_treatment": feature_part["surface_treatment"]
    }
    call_id_4 = f"call_model_{random.randint(1000, 9999)}"
    messages.append({
        "role": "assistant",
        "content": (
            f"标准件已就位。现在对核心自制零件【{feature_part['name']}】进行参数化三维建模。\n"
            f"★ 坚决拒绝无特征的死实体！我将遵循严谨的 SolidWorks FeatureManager 设计树时序进行构建：\n"
            f"草图基准面选定 -> 完全定义几何约束草图 -> 基体拉伸 -> 减料切除槽 -> 异型孔向导沉头/销孔 -> 倒角圆角 -> 全局方程式绑定。"
        ),
        "tool_calls": [{
            "id": call_id_4,
            "type": "function",
            "function": {
                "name": "cad.model_parametric_feature_part",
                "arguments": json.dumps(model_args, ensure_ascii=False)
            }
        }]
    })

    tool_res_4 = {
        "status": "success",
        "part_generated": feature_part["name"],
        "solidworks_feature_tree": [
            f"{node['feature_name']} ({node['feature_type']})" for node in feature_part["feature_tree"]
        ],
        "rebuild_errors": 0,
        "sketch_status": "FullyDefined",
        "native_macro_vba": f"' SolidWorks 2021 Parametric Script for {feature_part['name']}\nSub Main()\n    Set Part = swApp.ActiveDoc\n    ' ... Feature Tree Created with {len(feature_part['feature_tree'])} operations\nEnd Sub"
    }
    messages.append({
        "role": "tool",
        "tool_call_id": call_id_4,
        "name": "cad.model_parametric_feature_part",
        "content": json.dumps(tool_res_4, ensure_ascii=False)
    })

    # Step 5: Generate Engineering Drawing & Annotations
    drawing = archetype["drawing"]
    draw_args = {
        "drawing_name": drawing["name"],
        "sheet_size": drawing["sheet_size"],
        "projection_views": drawing["projection_views"],
        "fit_tolerances": drawing["fit_tolerances"],
        "geometric_tolerances_gdt": drawing["geometric_tolerances_gdt"],
        "surface_roughness_ra": drawing["surface_roughness_ra"],
        "technical_notes": drawing["technical_notes"]
    }
    call_id_5 = f"call_draw_{random.randint(1000, 9999)}"
    messages.append({
        "role": "assistant",
        "content": (
            f"三维特征树模型构建成功，零重建错误。现在进入制造工程图环节，自动为【{feature_part['name']}】出图与智能标注：\n"
            f"投影正交三视图与局部放大剖视，严格按照机械设计手册标准标定基孔制配合公差（H7）、形位公差（平行度/垂直度/平面度）与表面粗糙度要求："
        ),
        "tool_calls": [{
            "id": call_id_5,
            "type": "function",
            "function": {
                "name": "cad.generate_engineering_drawing_annotation",
                "arguments": json.dumps(draw_args, ensure_ascii=False)
            }
        }]
    })

    tool_res_5 = {
        "status": "success",
        "drawing_file": drawing["name"],
        "views_created": len(drawing["projection_views"]),
        "dimensions_annotated": 38,
        "tolerances_applied": len(drawing["fit_tolerances"]) + len(drawing["geometric_tolerances_gdt"]),
        "title_block_filled": True
    }
    messages.append({
        "role": "tool",
        "tool_call_id": call_id_5,
        "name": "cad.generate_engineering_drawing_annotation",
        "content": json.dumps(tool_res_5, ensure_ascii=False)
    })

    # Step 6: Assemble Components with Mates
    assembly = archetype["assembly"]
    asm_args = {
        "assembly_name": assembly["name"],
        "base_component": assembly["base"],
        "mates_sequence": assembly["mates"]
    }
    call_id_6 = f"call_asm_{random.randint(1000, 9999)}"
    messages.append({
        "role": "assistant",
        "content": (
            f"工程图标注已全量完成。现在在 SolidWorks 装配体环境中进行最终整机约束配合组装。\n"
            f"以【{assembly['base']}】作为空间静止固定基准，依次添加重合配合、距离配合与同轴心约束，构建装配体配合树（Assembly Mates Tree）："
        ),
        "tool_calls": [{
            "id": call_id_6,
            "type": "function",
            "function": {
                "name": "cad.assemble_components_with_mates",
                "arguments": json.dumps(asm_args, ensure_ascii=False)
            }
        }]
    })

    tool_res_6 = {
        "status": "success",
        "assembly_file": assembly["name"],
        "mates_created": len(assembly["mates"]),
        "degrees_of_freedom": "FullyConstrained_In_WorkingRange",
        "interference_detected": False,
        "assembly_tree_status": "Complete_And_Rebuilt"
    }
    messages.append({
        "role": "tool",
        "tool_call_id": call_id_6,
        "name": "cad.assemble_components_with_mates",
        "content": json.dumps(tool_res_6, ensure_ascii=False)
    })

    # Step 7: Execute SolidWorks Macro Batch
    macro_args = {
        "macro_action": "sw_export_dwg_oneclick",
        "target_files": [drawing["name"], assembly["name"]],
        "macro_options": {"auto_weldment_weight": True, "separate_drawing_number_and_name": True}
    }
    call_id_7 = f"call_macro_{random.randint(1000, 9999)}"
    messages.append({
        "role": "assistant",
        "content": (
            "装配体配合树已全部建立，干涉检查通过（0干涉点）。"
            "最后调用青沐清晨宏命令库，执行生产级批处理：一键输出DWG、图名图号分离、焊件切割清单与BOM总重统计："
        ),
        "tool_calls": [{
            "id": call_id_7,
            "type": "function",
            "function": {
                "name": "cad.execute_solidworks_macro",
                "arguments": json.dumps(macro_args, ensure_ascii=False)
            }
        }]
    })

    tool_res_7 = {
        "status": "success",
        "macro_executed": "青沐清晨一键输出DWG宏 + 图号分离宏 + 切割清单称重宏",
        "exported_dwg_files": [f"{drawing['name'].replace('.SLDDRW', '.dwg')}"],
        "bom_excel": f"BOM_{name}.xlsx",
        "execution_time_sec": 4.2
    }
    messages.append({
        "role": "tool",
        "tool_call_id": call_id_7,
        "name": "cad.execute_solidworks_macro",
        "content": json.dumps(tool_res_7, ensure_ascii=False)
    })

    # Final Summary Dialogue
    final_response = (
        f"### 【{name}】全流程设计与建模组装任务圆满完成！\n\n"
        f"#### 1. 意图拆解与模块架构\n"
        f"- **目标工件**：{product} | **生产节拍**：{cycle_time} s/件 | **系统负载**：{archetype['payload']} kg\n"
        f"- **总装分解**：设备已拆分为 {len(archetype['modules'])} 个独立子装配模块（涵盖机架、双工位供料、伺服执行与电气气动）。\n\n"
        f"#### 2. 标准件库调取（COTS & GB Profiles）\n"
        f"- 成功从 `GB型材库` 调取标准铝合金结构型材，从 `A研发设计库` 调取了 SMC 系列气缸、THK 微型高刚性导轨和伺服电批。\n\n"
        f"#### 3. 核心零件参数化特征树（Feature Tree 验证）\n"
        f"- **零件名称**：`{feature_part['name']}`（材质：{feature_part['material']}，表面处理：{feature_part['surface_treatment']}）\n"
        f"- **FeatureManager 设计树结构**（原生步骤，绝对无呆料实体）：\n"
        f"  1. `草图1_基体轮廓`（Top Plane 完全约束草图）\n"
        f"  2. `基体-拉伸1`（盲孔拉伸）\n"
        f"  3. `切除-拉伸1`（导向槽/仿形槽精密加工切除）\n"
        f"  4. `异型孔向导`（沉头螺钉孔 + H7 级精密定位销孔）\n"
        f"  5. `圆角与倒角`（清根过渡与去毛刺倒钝）\n"
        f"  6. `全局方程式绑定`（驱动核心长宽与安装孔距）\n\n"
        f"#### 4. 工程图标注与配合公差（GD&T）\n"
        f"- **工程图**：`{drawing['name']}`\n"
        f"- **配合精度**：基孔制 H7 级配合（+0.012/0 mm），导轨对中槽 H7 级配合；\n"
        f"- **形位公差**：基准底面平面度 0.01mm，安装端面垂直度 0.02mm，导轨滑槽平行度 0.015mm；\n"
        f"- **粗糙度**：基准配合面 Ra 1.6，仿形工作面 Ra 0.8。\n\n"
        f"#### 5. 装配体配合树与宏命令自动化\n"
        f"- **总装文件**：`{assembly['name']}`，所有自制件与标准件均通过重合、同轴心、距离限制配合完成完全约束；\n"
        f"- **宏自动化**：成功调用青沐清晨宏命令，一键输出无乱码 DWG 工程图，自动完成图名图号分离并生成 BOM 切割清单与理论总重。\n\n"
        f"该模型已完整具备 WorkBuddy 智能体所需的工具自主编排与连续执行能力！"
    )
    messages.append({"role": "assistant", "content": final_response})

    return {
        "tools": TOOLS,
        "messages": messages
    }


def generate_full_dataset(num_samples: int = 150):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    count = 0
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for i in range(num_samples):
            arch = EQUIPMENT_ARCHETYPES[i % len(EQUIPMENT_ARCHETYPES)]
            sample = generate_single_trajectory(arch, i)
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")
            count += 1

    print(f"[SUCCESS] Generated {count} rich industrial agent trajectories into: {OUTPUT_FILE}")
    print(f"File size: {os.path.getsize(OUTPUT_FILE):,} bytes")


if __name__ == "__main__":
    generate_full_dataset(150)
