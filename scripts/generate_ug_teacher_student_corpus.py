"""Generate UG 888 Drawing Teacher-Student Curriculum SFT Corpus.

Role:
- Teacher Coach: Senior Mechanical CAD/CAM Instructor providing pedagogical critique, error diagnosis, and step-by-step guidance.
- Student Agent: AI CAD Agent that takes blueprint specifications, attempts modeling via tool calls, encounters realistic rookie errors, activates <thought> self-reflection upon receiving teacher hints, corrects code/GUI parameters, achieves 100% zero-defect verification, and commits experience to long-term memory.
"""

import os
import json
import random

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "cad.infer_blueprint_feature_tree",
            "description": "逆向解析工程图纸中的几何基元、尺寸公差方程与三维特征树（FeatureTree）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "drawing_name": {"type": "string", "description": "图纸图号或文件名（如：0001.bmp）"},
                    "category": {"type": "string", "enum": ["shaft_spindle", "flange_disc", "bracket_housing", "sleeve_bushing", "mold_cavity", "assembly_mating"]},
                    "dimensions": {"type": "object", "description": "关键外形尺寸及公差"},
                    "rough_features": {"type": "array", "items": {"type": "string"}, "description": "粗推特征序列"}
                },
                "required": ["drawing_name", "category", "dimensions", "rough_features"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "agent.verify_and_self_optimize",
            "description": "对 CAD 建模脚本（NXOpen Python / SolidWorks VBA）进行几何流形校验、拓扑闭环检验与自优化修正。",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "待验证的 CAD 建模脚本代码"},
                    "software": {"type": "string", "enum": ["UG_NX", "SOLIDWORKS", "AutoCAD"]},
                    "check_items": {"type": "array", "items": {"type": "string"}, "description": "校验项（如：manifold_topology, boolean_subtraction, sketch_constraints）"}
                },
                "required": ["code", "software", "check_items"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "desktop.focus_software",
            "description": "将目标工业软件（UG/NX, SOLIDWORKS, AutoCAD）置于桌面最前端。",
            "parameters": {
                "type": "object",
                "properties": {
                    "software_name": {"type": "string"}
                },
                "required": ["software_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "desktop.click_element",
            "description": "在CAD软件视口或功能区指定坐标执行精确鼠标点击。",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                    "button": {"type": "string", "default": "left"}
                },
                "required": ["x", "y"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cad.assemble_components_with_mates",
            "description": "在UG/NX或SolidWorks总装配体中建立零件间的约束配合（同心、重合、距离、平行）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "assembly_name": {"type": "string"},
                    "mates": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "mate_type": {"type": "string", "enum": ["Coincident", "Concentric", "Distance", "Parallel"]},
                                "component_1": {"type": "string"},
                                "component_2": {"type": "string"},
                                "value": {"type": "number"}
                            },
                            "required": ["mate_type", "component_1", "component_2"]
                        }
                    }
                },
                "required": ["assembly_name", "mates"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "skill.synthesize_agent_skill",
            "description": "将成功攻克的图纸建模经验沉淀为标准化 Antigravity Skill 技能包。",
            "parameters": {
                "type": "object",
                "properties": {
                    "skill_name": {"type": "string"},
                    "description": {"type": "string"},
                    "instructions_markdown": {"type": "string"},
                    "bundled_scripts": {"type": "object"}
                },
                "required": ["skill_name", "description", "instructions_markdown"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "memory.commit_long_term_experience",
            "description": "将本次教师辅导学到的避坑经验、约束规则与标准化参数模板写入长期记忆。",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_signature": {"type": "string"},
                    "rookie_error": {"type": "string"},
                    "teacher_hint": {"type": "string"},
                    "corrected_strategy": {"type": "string"},
                    "golden_rules": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["task_signature", "rookie_error", "teacher_hint", "corrected_strategy", "golden_rules"]
            }
        }
    }
]

SYSTEM_PROMPT = (
    "你是一个工业三维CAD/CAM智能体（Student Agent），在资深机械CAD教师（Teacher Coach）的指导下，"
    "针对UG/NX 888套工程练习图纸进行自适应学习与建模训练。当教师指出你的建模缺陷、约束缺失或布尔错误时，"
    "你能够自主启动<thought>深度反思，纠偏代码与桌面工具调用，直到实现100%零差错几何闭环，"
    "并将学习到的建模经验与Skill沉淀入长期记忆。"
)

CURRICULUM_TEMPLATES = [
    {
        "category": "shaft_spindle",
        "name_fmt": "阶梯传动轴零件图 ({num}.bmp)",
        "dim_generator": lambda: {
            "total_len": random.choice([120, 160, 200, 240]),
            "dia1": random.choice([20, 25, 28]),
            "dia2": random.choice([35, 40, 45]),
            "dia3": random.choice([18, 22, 24]),
            "keyway_w": random.choice([6, 8, 10]),
            "keyway_d": random.choice([3.5, 4.0, 5.0]),
            "chamfer": 1.5,
            "fillet": 2.0
        },
        "rookie_error_desc": "在XC-YC基准平面绘制草图时旋转轴未与绝对坐标X轴添加Coincident约束，且键槽拉伸特征错误使用了UNITE布尔操作生成了凸台。",
        "teacher_hint": "【教师诊断与指导】Student Agent注意：1. 阶梯轴旋转草图的旋转轴线必须与绝对坐标系XC轴严格共线重合，否则会产生偏心轴畸变；2. 键槽拉伸特征属于切除材料，必须将布尔操作从'UNITE'修正为'SUBTRACT'；3. 请重新反思并调用 verify_and_self_optimize 纠偏！",
        "reflection_points": "1. 根因在于草图自由度未完全约束，需添加水平共线重合约束。\n2. 键槽为切除加工，布尔求和导致几何拓扑错误，应改为布尔求差。\n3. 修正后重新计算实体体积与流形属性。",
        "skill_name": "nx-stepped-shaft-keyway-mastery",
        "rules": [
            "阶梯轴旋转截面底边必须与旋转基准轴添加 Coincident 重合约束以消除偏心自由度",
            "键槽与退刀槽加工必须显式指定 Feature.BooleanType.Subtract 进行实体求差切除",
            "阶梯台阶过渡圆角必须在主回转体生成后、键槽切除前建立，避免产生相交拓扑歧义"
        ]
    },
    {
        "category": "flange_disc",
        "name_fmt": "高压管路法兰盘 ({num}.bmp)",
        "dim_generator": lambda: {
            "outer_dia": random.choice([120, 150, 180]),
            "inner_dia": random.choice([50, 65, 80]),
            "thickness": random.choice([16, 20, 25]),
            "bolt_pcd": random.choice([95, 120, 145]),
            "bolt_dia": random.choice([14, 18]),
            "bolt_count": random.choice([4, 6, 8]),
            "counterbore_dia": random.choice([20, 24]),
            "counterbore_depth": 5.0
        },
        "rookie_error_desc": "螺栓孔圆周阵列时未约束中心轴到基准原点，且沉头阶梯孔深度未做盲孔深度公式绑定，导致沉孔贯穿了法兰底面。",
        "teacher_hint": "【教师诊断与指导】Student Agent注意：1. 圆周阵列(PatternFeature)的旋转轴心必须绑定绝对原点Z轴，避免孔阵列发散；2. 沉孔深度必须小于法兰厚度（建议厚度的一半或标准沉头深度），当前深度参数导致贯穿干涉。请反思后立即纠偏！",
        "reflection_points": "1. 阵列特征未锁定旋转中心轴导致孔位偏斜，需指定 Vector.ZAxis 与 Point(0,0,0)。\n2. 沉孔特征与底面穿透破坏密封唇边，调整沉孔深度为 5.0mm 并添加沉头孔参数公式约束。",
        "skill_name": "nx-flange-pcd-bolt-array",
        "rules": [
            "法兰圆周螺栓孔阵列必须以回转绝对中心轴为基准向量并施加 AngularEqual 约束",
            "沉孔深度参数必须关联法兰厚度方程式，强制满足 Depth_Counterbore < 0.4 * Flange_Thickness",
            "法兰密封面水线槽与倒角需在孔阵列之后构建，保障密封面边界平整度"
        ]
    },
    {
        "category": "bracket_housing",
        "name_fmt": "滑动轴承支撑底座 ({num}.bmp)",
        "dim_generator": lambda: {
            "base_len": random.choice([140, 180, 220]),
            "base_w": random.choice([70, 90, 100]),
            "base_h": random.choice([15, 20, 25]),
            "bore_dia": random.choice([40, 50, 60]),
            "center_h": random.choice([55, 65, 75]),
            "rib_thickness": random.choice([8, 10, 12])
        },
        "rookie_error_desc": "加强筋(Rib)拉伸特征的法向延伸方向反向，拉伸到了悬空空气中，且底座安装孔与底边未留足安全边距。",
        "teacher_hint": "【教师诊断与指导】Student Agent：1. 加强筋的草图法向矢量反了，应指向轴承座外圆柱体施加'直到下一个面(Until Next)'，不要使用固定深度盲拉；2. 底板腰形孔边距小于螺栓沉头外径要求，容易引起应力开裂。请反思并纠正拉伸方向与边距参数！",
        "reflection_points": "1. 加强筋盲拉导致非流形几何与悬空多实体，必须改为'直到下一个面(To Next)'智能求和。\n2. 安装孔到边界距离根据机械设计手册调整为大于 1.5 * Hole_Dia 保证结构刚度。",
        "skill_name": "nx-bracket-rib-and-bearing-housing",
        "rules": [
            "加强筋结构建模优先使用 Ribbon/Rib 专用特征或拉伸至相邻曲面(To Next)，杜绝固定深度悬空",
            "铸造支撑箱体必须在交接处施加 R3~R5 铸造圆角消除锐边应力集中",
            "底座安装螺栓孔到外边缘距离必须满足 EdgeDistance >= 1.5 * Diameter"
        ]
    },
    {
        "category": "sleeve_bushing",
        "name_fmt": "带内螺旋油槽的导向衬套 ({num}.bmp)",
        "dim_generator": lambda: {
            "outer_dia": random.choice([50, 60, 75]),
            "inner_dia": random.choice([35, 45, 55]),
            "length": random.choice([80, 100, 120]),
            "flange_dia": random.choice([65, 80, 95]),
            "groove_pitch": random.choice([25, 30, 40]),
            "groove_depth": 1.5
        },
        "rookie_error_desc": "在衬套内孔扫掠(Sweep)螺旋油槽时，螺距设置过小且扫掠轮廓与内壁自相交导致CAD内核拓扑缝合失败。",
        "teacher_hint": "【教师诊断与指导】Student Agent：内孔螺旋润滑槽扫掠失败！原因分析：螺距设置小于截面圆弧直径导致截面自交叉(Self-Intersection)。扫掠导向线必须使用内圆柱表面螺旋线，扫掠截面需垂直于轨迹线(Normal to Path)。请立即自纠！",
        "reflection_points": "1. 螺旋线螺距参数必须大于槽宽的3倍以上以避免自相交奇异点。\n2. 截面定位平面必须绑定在螺旋线起点并保持切线法向对齐。\n3. 布尔切除时确保端部延伸出衬套端面各1mm，避免留下薄膜残渣。",
        "skill_name": "nx-bushing-helical-groove-sweep",
        "rules": [
            "内孔螺旋油槽扫掠截面必须严格垂直于螺旋路径(Normal to Path)，避免退化扭曲",
            "螺旋线两端必须向外超程延伸 1~2mm，布尔求差后方可获得干净整齐的贯通油槽端口",
            "衬套内外径同轴度由单次装夹或同基准旋转切削保证，建模时草图需统一同心约束"
        ]
    },
    {
        "category": "mold_cavity",
        "name_fmt": "精密注塑模型腔镶件 ({num}.bmp)",
        "dim_generator": lambda: {
            "block_x": random.choice([120, 150, 180]),
            "block_y": random.choice([100, 120, 140]),
            "block_z": random.choice([60, 75, 90]),
            "pocket_depth": random.choice([25, 35, 45]),
            "draft_angle": 2.0,
            "fillet_r": random.choice([3.0, 5.0])
        },
        "rookie_error_desc": "型腔侧壁拔模斜度方向搞反导致倒锥无法脱模，且底部拐角未倒圆角导致数控立铣刀具干涉。",
        "teacher_hint": "【教师诊断与指导】Student Agent：严重模具缺陷！1. 拔模方向反向，形成了倒扣(Negative Draft)，注塑件出模时将卡死断裂；2. 型腔内侧拐角为R0直角，现有CNC铣刀无法清角加工，必须至少倒R3圆角。请深度反思并纠正拔模与倒角！",
        "reflection_points": "1. 拔模基准面选定分型面(Parting Plane)，脱模拉模方向为+Z，拔模角必须使开口扩大。\n2. 内型腔角部添加 R>=3.0mm 圆角，契合 Φ6mm 立铣刀加工路径，消除应力集中。",
        "skill_name": "nx-mold-cavity-draft-and-fillet",
        "rules": [
            "模具型腔拔模必须沿出模方向(+Z)验证脱模角 DraftAngle >= 1.5°，严禁产生任何倒锥",
            "内腔清角圆角半径必须大于等于推荐数控立铣刀半径(R >= R_tool + 0.5mm)",
            "分型面(Parting Surface)缝合公差需控制在 0.005mm 以内杜绝注塑毛边飞边"
        ]
    },
    {
        "category": "assembly_mating",
        "name_fmt": "齿轮传动轴系装配体 ({num}.bmp)",
        "dim_generator": lambda: {
            "shaft_dia": random.choice([25, 30, 35]),
            "gear_bore": random.choice([25, 30, 35]),
            "bearing_model": random.choice(["6205", "6206", "6207"]),
            "key_spec": "8x7x30"
        },
        "rookie_error_desc": "装配体配合中添加了两个相互矛盾的平行配合导致装配过约束死锁，且缺少轴向轴肩贴合配合导致齿轮在轴上滑移。",
        "teacher_hint": "【教师诊断与指导】Student Agent：装配约束存在严重冲突！1. 同一齿轮端面与轴肩同时添加了平行和重合约束，引起过约束报警(Over-Constrained)；2. 平键与轴上键槽未添加对称或侧面重合配合，产生旋转滑移自由度。请反思并重构装配配合树！",
        "reflection_points": "1. 移除冗余的平行配合，保留【轴孔同心(Concentric)】与【端面贴合(Coincident)】即可完全定心定位。\n2. 平键配合采用【侧面贴合】与【端部圆弧同心】，确保周向转矩传递无相对自由度。",
        "skill_name": "nx-transmission-shaft-gear-assembly-mates",
        "rules": [
            "回转体轴系装配遵从'一阶定心(同心Concentric)，二阶定位(贴合Coincident)'原则，严禁添加冗余平行配合",
            "键联接装配必须锁定键侧与槽侧的工作接触面配合，消除周向相对旋转自由度",
            "装配完成后必须调用物理碰撞干涉检查，确保无零配合以上干涉与间隙悬空"
        ]
    }
]

def make_sample(idx, template):
    cat = template["category"]
    drawing_file = f"{idx:04d}.bmp" if idx < 885 else f"{idx - 884:02d}.jpg"
    dims = template["dim_generator"]()
    title = template["name_fmt"].format(num=drawing_file)

    tool_call_infer_id = f"call_infer_{idx:04d}"
    tool_call_verify_bad_id = f"call_ver_bad_{idx:04d}"
    tool_call_verify_good_id = f"call_ver_good_{idx:04d}"
    tool_call_skill_id = f"call_skill_{idx:04d}"
    tool_call_mem_id = f"call_mem_{idx:04d}"

    rough_features = [
        f"Base_{cat}_Profile",
        f"Feature_Sub_Keyway_Or_Holes",
        f"Transition_Fillets_Chamfers"
    ]

    infer_args = {
        "drawing_name": drawing_file,
        "category": cat,
        "dimensions": dims,
        "rough_features": rough_features
    }

    infer_ret = {
        "status": "inferred",
        "drawing": drawing_file,
        "geometry_class": cat,
        "extracted_dimensions": dims,
        "inferred_feature_tree": [
            {"step": 1, "feature": "DatumPlane_XC_YC", "status": "planned"},
            {"step": 2, "feature": "Revolve_Or_Extrude_Base", "status": "planned"},
            {"step": 3, "feature": "Boolean_Feature_Operations", "status": "planned"},
            {"step": 4, "feature": "Finishing_Fillet_Chamfer", "status": "planned"}
        ]
    }

    bad_script = f"# Rookie Attempt for {drawing_file}\nimport NXOpen\nsession = NXOpen.Session.GetSession()\n# [ERROR INJECTED]: {template['rookie_error_desc']}\n"
    good_script = f"# 100-Point Standard Corrected Script for {drawing_file}\nimport NXOpen\n# Corrected parameters applied: {dims}\n# Boolean operations verified, manifold check passed.\n"

    verify_bad_ret = {
        "status": "FAILED",
        "error_type": "Constraint_Or_Boolean_Defect",
        "details": template["rookie_error_desc"],
        "manifold": False,
        "score": 45
    }

    verify_good_ret = {
        "status": "PASSED",
        "manifold": True,
        "volume_deviation": 0.0,
        "tolerance_satisfied": True,
        "collision_free": True,
        "score": 100
    }

    skill_args = {
        "skill_name": f"{template['skill_name']}-{idx:03d}",
        "description": f"针对 {drawing_file} ({cat}) 经过教师辅导纠偏后沉淀的标准化工业建模技能。",
        "instructions_markdown": f"# {title} 工业级建模指南\n\n## 避坑与核心规则\n" + "\n".join([f"- {r}" for r in template["rules"]]),
        "bundled_scripts": {
            "build_model.py": good_script
        }
    }

    mem_args = {
        "task_signature": f"UG_888_{cat}_{drawing_file}",
        "rookie_error": template["rookie_error_desc"],
        "teacher_hint": template["teacher_hint"],
        "corrected_strategy": template["reflection_points"],
        "golden_rules": template["rules"]
    }

    user_prompt = (
        f"【UG 888练习图-工程图纸任务: {title}】\n"
        f"图纸参数规格：{json.dumps(dims, ensure_ascii=False)}\n"
        f"请在UG/NX或SolidWorks环境中调用工具完成图纸逆向解析、特征树规划、代码/GUI建模，"
        f"并接受机械CAD教师的全程辅导与质量检查，确保最终模型无差错交付。"
    )

    assistant_attempt = (
        f"收到工程图纸 {title} 任务，开始启动初次逆向特征解析与建模流程。\n"
        f"首先调用 cad.infer_blueprint_feature_tree 工具逆向解析图纸尺寸与特征树。"
    )

    teacher_critique = template["teacher_hint"]

    student_reflection = (
        f"<thought>\n"
        f"机械教师的诊断极其精准，直接指出了初次尝试中的致命缺陷：\n"
        f"{template['reflection_points']}\n"
        f"我必须坚决纠正！重构建模逻辑：锁定基准面约束、修正布尔运算为差集切除、校准圆角与拔模参数。\n"
        f"立即调用 agent.verify_and_self_optimize 执行修复后脚本的闭环验证！\n"
        f"</thought>\n"
        f"感谢老师的指导！我已经彻底认识到初次建模中的缺陷与成因，现已针对性纠正代码与约束，重新提交几何与拓扑校验。"
    )

    teacher_pass = (
        f"【教师验收合格】\n"
        f"非常好！修正后的 {drawing_file} 三维实体几何拓扑校验通过（得分：100分，流形闭环，无拓扑干涉）。\n"
        f"图纸公差及各处装配基准均完全合规！请将本次从错误到正确的教学经验固化为 Skill 技能并同步写入长期记忆。"
    )

    student_final_commit = (
        f"遵照教师指导，已成功达成 100 分无差错建模验收！\n"
        f"现在立即将本次掌握的工艺知识与防错逻辑沉淀为 Antigravity 技能包，并固化至长期记忆知识库中。"
    )

    msgs = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
        {
            "role": "assistant",
            "content": assistant_attempt,
            "tool_calls": [
                {
                    "id": tool_call_infer_id,
                    "type": "function",
                    "function": {"name": "cad.infer_blueprint_feature_tree", "arguments": json.dumps(infer_args, ensure_ascii=False)}
                }
            ]
        },
        {
            "role": "tool",
            "tool_call_id": tool_call_infer_id,
            "name": "cad.infer_blueprint_feature_tree",
            "content": json.dumps(infer_ret, ensure_ascii=False)
        },
        {
            "role": "assistant",
            "content": f"图纸特征树已提取。根据初步理解，编写初始建模脚本并在 UG 环境中进行初步测试验证...",
            "tool_calls": [
                {
                    "id": tool_call_verify_bad_id,
                    "type": "function",
                    "function": {
                        "name": "agent.verify_and_self_optimize",
                        "arguments": json.dumps({"code": bad_script, "software": "UG_NX", "check_items": ["manifold_topology", "boolean_subtraction"]}, ensure_ascii=False)
                    }
                }
            ]
        },
        {
            "role": "tool",
            "tool_call_id": tool_call_verify_bad_id,
            "name": "agent.verify_and_self_optimize",
            "content": json.dumps(verify_bad_ret, ensure_ascii=False)
        },
        {
            "role": "assistant",
            "content": f"初次尝试完成，正在等待指导教师批阅与检查..."
        },
        {
            "role": "user",
            "content": teacher_critique
        },
        {
            "role": "assistant",
            "content": student_reflection,
            "tool_calls": [
                {
                    "id": tool_call_verify_good_id,
                    "type": "function",
                    "function": {
                        "name": "agent.verify_and_self_optimize",
                        "arguments": json.dumps({"code": good_script, "software": "UG_NX", "check_items": ["manifold_topology", "boolean_subtraction", "sketch_constraints"]}, ensure_ascii=False)
                    }
                }
            ]
        },
        {
            "role": "tool",
            "tool_call_id": tool_call_verify_good_id,
            "name": "agent.verify_and_self_optimize",
            "content": json.dumps(verify_good_ret, ensure_ascii=False)
        },
        {
            "role": "assistant",
            "content": f"纠偏后的模型已完成自优化重构，请老师进行二次最终验收。"
        },
        {
            "role": "user",
            "content": teacher_pass
        },
        {
            "role": "assistant",
            "content": student_final_commit,
            "tool_calls": [
                {
                    "id": tool_call_skill_id,
                    "type": "function",
                    "function": {"name": "skill.synthesize_agent_skill", "arguments": json.dumps(skill_args, ensure_ascii=False)}
                },
                {
                    "id": tool_call_mem_id,
                    "type": "function",
                    "function": {"name": "memory.commit_long_term_experience", "arguments": json.dumps(mem_args, ensure_ascii=False)}
                }
            ]
        },
        {
            "role": "tool",
            "tool_call_id": tool_call_skill_id,
            "name": "skill.synthesize_agent_skill",
            "content": json.dumps({"status": "synthesized", "skill_path": f"skills/{template['skill_name']}/SKILL.md"})
        },
        {
            "role": "tool",
            "tool_call_id": tool_call_mem_id,
            "name": "memory.commit_long_term_experience",
            "content": json.dumps({"status": "committed", "entry_id": f"MEM_{idx:05d}", "knowledge_graph_node_count": 128})
        },
        {
            "role": "assistant",
            "content": (
                f"【建模任务交付完成】\n"
                f"1. 图纸 {title} 已实现 100% 零差错闭环建模；\n"
                f"2. 针对初次出现的“{template['rookie_error_desc'][:30]}...”错误，已完成自省纠偏与参数固化；\n"
                f"3. 沉淀出新技能 `{template['skill_name']}` 并写入长期记忆图谱，下一次面对同类零件图纸时将实现首次建模直接无差错自主完成！"
            )
        }
    ]

    return {
        "tools": TOOLS_SCHEMA,
        "messages": msgs
    }

def main():
    out_dir = r"D:\Virtu模型\damodel_cad_cam_tuning\dataset"
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, "ug_888_teacher_student_sft.jsonl")

    total_samples = 360
    print(f"[INFO] Generating {total_samples} teacher-student coaching samples from UG 888 exercises...")

    with open(out_file, "w", encoding="utf-8") as f:
        for i in range(1, total_samples + 1):
            tmpl = CURRICULUM_TEMPLATES[(i - 1) % len(CURRICULUM_TEMPLATES)]
            sample = make_sample(i, tmpl)
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")

    size_mb = os.path.getsize(out_file) / (1024 * 1024)
    print(f"[SUCCESS] Generated {total_samples} samples at {out_file} ({size_mb:.2f} MB)")

if __name__ == "__main__":
    main()
