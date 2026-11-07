# -*- coding: utf-8 -*-
"""
build_equipment_and_toolcalls.py
Processes 97 production automation equipment projects from:
  e:\迅雷下载\100台3C、锂电自动化设备量产图纸
Cross-references GB Profile library and A研发设计库, and produces:
  1. automation_equipments_taxonomy.json (Full machine architecture taxonomy)
  2. virtu_agent_toolcall_train.jsonl (OpenAI tool-calling format SFT dataset)
  3. virtu_agent_toolcall_val.jsonl (Evaluation/validation tool-calling dataset)
  4. equipment_decomposition_cases.jsonl (Assembly decomposition reasoning cases)
"""

import os
import sys
import re
import json
import random
import hashlib

sys.stdout.reconfigure(encoding='utf-8')

# Ensure deterministic output
random.seed(42)

SOURCE_DIR = r"e:\迅雷下载\100台3C、锂电自动化设备量产图纸"
OUTPUT_DIR = r"e:\新建文件夹 (3)"

DIR_TOOLCALLS = os.path.join(OUTPUT_DIR, "01_SFT_AGENT_TOOLCALLS")
DIR_TAXONOMY = os.path.join(OUTPUT_DIR, "06_PRODUCTION_EQUIPMENT_TAXONOMY")
os.makedirs(DIR_TOOLCALLS, exist_ok=True)
os.makedirs(DIR_TAXONOMY, exist_ok=True)

# System prompt aligned with Virtu CAD/CAM Agent specification
SYSTEM_PROMPT = (
    "你是由 Virtu 工业模型驱动的非标自动化全流程设计智能体（CAD/CAM/Automation AI Agent）。"
    "你具备深厚的机械设计与工业自动化工程知识，能够揣测用户意图，将非标自动化设备拆解为子机构与零部件，"
    "自主调用专业工具完成标准件选型、参数化特征树建模（带完整 FeatureManager 设计树）、工程图智能标注（含配合公差与GD&T）、"
    "整机空间装配配合约束以及生产宏输出。"
)

# Domain mapping keywords
DOMAIN_MAP = {
    "锂电": "新能源锂电设备 (Lithium Battery Automation)",
    "电池": "新能源锂电设备 (Lithium Battery Automation)",
    "18650": "圆柱电池自动化 (Cylindrical Battery Packaging)",
    "螺丝": "精密点胶与锁附设备 (Precision Fastening Automation)",
    "点胶": "精密流体点胶设备 (Fluid Dispensing System)",
    "视觉": "机器视觉与外观检测 (Machine Vision & Inspection)",
    "检测": "智能检测与分选设备 (Quality Inspection & Sorting)",
    "贴膜": "3C消费电子贴膜滚压 (3C Screen & Film Lamination)",
    "冲裁": "五金冲压与柔性排线冲裁 (Stamping & FPC Punching)",
    "焊接": "激光焊接与自动化装配 (Laser Welding & Assembly)",
    "包装": "自动化包装与封箱系统 (Packaging Automation)",
    "马达": "微特电机与车载马达装配 (Motor Manufacturing)",
    "上料": "物料供给与上料机构 (Feeding & Loading Mechanism)",
}

def infer_domain(name):
    for kw, d in DOMAIN_MAP.items():
        if kw in name:
            return d
    return "通用3C非标自动化设备 (General 3C Industrial Automation)"

def scan_equipment_folder(eq_dir):
    equipments = []
    subfolders = [d for d in os.listdir(eq_dir) if os.path.isdir(os.path.join(eq_dir, d))]
    
    for folder_name in sorted(subfolders):
        folder_path = os.path.join(eq_dir, folder_name)
        
        sldasm_list = []
        sldprt_list = []
        slddrw_list = []
        dwg_list = []
        pdf_list = []
        step_list = []
        
        for root, dirs, files in os.walk(folder_path):
            for f in files:
                low = f.lower()
                rel = os.path.relpath(os.path.join(root, f), folder_path)
                if low.endswith('.sldasm'):
                    sldasm_list.append(rel)
                elif low.endswith('.sldprt'):
                    sldprt_list.append(rel)
                elif low.endswith('.slddrw'):
                    slddrw_list.append(rel)
                elif low.endswith('.dwg'):
                    dwg_list.append(rel)
                elif low.endswith('.pdf'):
                    pdf_list.append(rel)
                elif low.endswith(('.step', '.stp')):
                    step_list.append(rel)
        
        # Clean clean equipment title
        clean_title = re.sub(r'^\d+[\.\、\s]*', '', folder_name).strip()
        
        equipments.append({
            "folder_name": folder_name,
            "equipment_title": clean_title,
            "domain": infer_domain(folder_name),
            "counts": {
                "assemblies": len(sldasm_list),
                "parts": len(sldprt_list),
                "drawings": len(slddrw_list) + len(dwg_list) + len(pdf_list),
                "step_models": len(step_list),
                "total_files": len(sldasm_list) + len(sldprt_list) + len(slddrw_list) + len(dwg_list) + len(pdf_list) + len(step_list)
            },
            "assemblies": sldasm_list,
            "parts": sldprt_list,
            "drawings": slddrw_list + dwg_list + pdf_list
        })
    return equipments

def generate_toolcall_conversation(eq):
    title = eq["equipment_title"]
    domain = eq["domain"]
    asms = eq["assemblies"]
    prts = eq["parts"]
    
    # Select key representative assemblies and custom parts
    sub_modules_names = []
    for a in asms:
        base = os.path.splitext(os.path.basename(a))[0]
        if any(kw in base for kw in ["组件", "总成", "机构", "机架", "滑台", "模组", "工位", "装配", "ASSY", "Assy"]):
            if base not in sub_modules_names and len(base) > 2:
                sub_modules_names.append(base)
    if not sub_modules_names:
        sub_modules_names = [os.path.splitext(os.path.basename(a))[0] for a in asms[:4]]
    if not sub_modules_names:
        sub_modules_names = ["主机架结构组合", "自动化上下料机构", "精密定位夹紧工位", "核心伺服作业模组"]
    
    sub_modules_names = sub_modules_names[:5] # keep top 4-5
    
    # Custom fabricated parts
    custom_parts = []
    cots_parts = []
    for p in prts:
        base = os.path.splitext(os.path.basename(p))[0]
        if any(cots_kw in base for cots_kw in ["M3", "M4", "M5", "M6", "M8", "M10", "M12", "SMC", "HIWIN", "THK", "亚德客", "导轨", "滑块", "气缸", "电磁阀", "接头", "光电", "电机", "丝杆", "轴承"]):
            if len(cots_parts) < 8 and base not in cots_parts:
                cots_parts.append(base)
        else:
            if len(custom_parts) < 8 and base not in custom_parts and len(base) > 2:
                custom_parts.append(base)
    
    if not custom_parts:
        custom_parts = ["主底板安装基准面_45钢厚30mm", "精密定位治具支架_铝合金6061", "伺服电机联轴器法兰座", "横梁滑动承载板"]
    if not cots_parts:
        cots_parts = ["HIWIN HGH20CA滚动导轨滑块", "SMC CDQ2B32-30DZ双作用气缸", "雷赛高响应闭环步进电机", "欧姆龙微型光电开关EE-SX672"]
    
    call_id_base = hashlib.md5(title.encode('utf-8')).hexdigest()[:6]
    
    # Define tool sequence
    # 1. infer_equipment_intent
    # 2. decompose_automation_assembly
    # 3. query_standard_parts_library
    # 4. model_parametric_feature_tree
    # 5. generate_engineering_drawing_annotation
    # 6. assemble_components_with_mates
    # 7. execute_solidworks_macro
    
    main_part_name = custom_parts[0] + ".SLDPRT"
    main_asm_name = (asms[0] if asms else f"{title}_总装配体.SLDASM")
    if not main_asm_name.lower().endswith('.sldasm'):
        main_asm_name += ".SLDASM"
    main_asm_name = os.path.basename(main_asm_name)
    
    cycle_time = round(random.uniform(1.8, 6.5), 1)
    payload_kg = round(random.uniform(2.0, 25.0), 1)
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"帮我全流程设计并建模这套【{title}】（所属领域：{domain}），要求自顶向下完成意图推断、机构BOM分解、标准件库调用、核心件参数化特征树建模、带配合公差与GD&T的工程图出图、整机约束配合组装，最后用青沐清晨宏命令批量生成制造DWG与切割清单！"},
        {
            "role": "assistant",
            "content": f"收到设计需求。对于【{title}】，我正在深度揣测并分析该工业工况下的核心工程参数：\n1. 行业领域：{domain}，生产节拍目标设定为 {cycle_time} s/pcs，要求高刚度连续稳定节拍；\n2. 结构负载设计指标为 {payload_kg} kg，运动轴系须确保重复定位精度在 ±0.015mm 以内；\n3. 系统气动与伺服动力协调联动。首先调用意图解析工具确立运动学参数：",
            "tool_calls": [
                {
                    "id": f"call_intent_{call_id_base}",
                    "type": "function",
                    "function": {
                        "name": "cad.infer_equipment_intent",
                        "arguments": json.dumps({
                            "equipment_type": title,
                            "domain": domain,
                            "cycle_time_sec": cycle_time,
                            "payload_kg": payload_kg,
                            "working_air_pressure_mpa": 0.6,
                            "repeatability_mm": 0.015,
                            "safety_factor": 2.5
                        }, ensure_ascii=False)
                    }
                }
            ]
        },
        {
            "role": "tool",
            "content": json.dumps({
                "status": "success",
                "equipment_id": f"EQ_{call_id_base.upper()}",
                "kinematic_plan": {
                    "cycle_budget_sec": cycle_time,
                    "target_repeatability_mm": 0.015,
                    "max_speed_mm_s": 450,
                    "air_consumption_lpm": 38.0
                }
            }, ensure_ascii=False)
        },
        {
            "role": "assistant",
            "content": f"工况意图推断完毕。按照非标自动化模块化设计规范，现在对【{title}】执行自顶向下装配体结构树分解，规划系统级 BOM 与各个子装配机构：",
            "tool_calls": [
                {
                    "id": f"call_decomp_{call_id_base}",
                    "type": "function",
                    "function": {
                        "name": "cad.decompose_automation_assembly",
                        "arguments": json.dumps({
                            "assembly_name": main_asm_name,
                            "sub_modules": [
                                {
                                    "module_name": mod,
                                    "custom_fabricated_parts": custom_parts[:3],
                                    "standard_cots": cots_parts[:3]
                                } for mod in sub_modules_names
                            ]
                        }, ensure_ascii=False)
                    }
                }
            ]
        },
        {
            "role": "tool",
            "content": json.dumps({
                "status": "success",
                "assembly_name": main_asm_name,
                "total_submodules": len(sub_modules_names),
                "custom_parts_registered": len(custom_parts),
                "cots_components_registered": len(cots_parts),
                "bom_tree_valid": True
            }, ensure_ascii=False)
        },
        {
            "role": "assistant",
            "content": "整机结构树分解完毕。在构建自制零部件前，优先从标准型材库与标准件库中检索调取标准结构体：包括 GB 结构型材以及导轨滑块、气缸执行元件：",
            "tool_calls": [
                {
                    "id": f"call_std_{call_id_base}",
                    "type": "function",
                    "function": {
                        "name": "cad.query_standard_parts_library",
                        "arguments": json.dumps({
                            "structural_profile": {
                                "standard": "GB／6728-1986方形空心型钢",
                                "specification": "80 x 80 x 4.0",
                                "material": "Q235-B"
                            },
                            "pneumatic_actuator": cots_parts[1] if len(cots_parts) > 1 else "SMC CDQ2B32-30DZ",
                            "linear_guide_rail": cots_parts[0] if len(cots_parts) > 0 else "HIWIN HGH20CA"
                        }, ensure_ascii=False)
                    }
                }
            ]
        },
        {
            "role": "tool",
            "content": json.dumps({
                "status": "success",
                "profile_model": "GB型材库/GB／6728-1986方形空心型钢/80 x 80 x 4.sldlfp",
                "guide_rail_model": f"A研发设计库/滑块/{cots_parts[0] if cots_parts else 'HGH20CA'}.SLDPRT",
                "cots_loaded": True
            }, ensure_ascii=False)
        },
        {
            "role": "assistant",
            "content": f"标准件与基础型材已就位。现在对核心基准自制件【{main_part_name}】进行严格的 SolidWorks FeatureManager 参数化特征树建模，全流程施加尺寸驱动与几何约束，拒绝无特征死体：",
            "tool_calls": [
                {
                    "id": f"call_model_{call_id_base}",
                    "type": "function",
                    "function": {
                        "name": "cad.model_parametric_feature_tree",
                        "arguments": json.dumps({
                            "part_name": main_part_name,
                            "material": "AL6061-T6 (铝合金)" if "铝" in main_part_name else "45# 钢 (调质 HB220-250)",
                            "feature_manager_tree": [
                                {
                                    "step": 1,
                                    "feature_type": "SketchOnPlane",
                                    "plane": "TopPlane (上视基准面)",
                                    "sketch_geometry": "封闭矩形轮廓",
                                    "constraints": ["重合原点", "水平垂直约束", "尺寸标注驱动 320.0 x 240.0 mm"]
                                },
                                {
                                    "step": 2,
                                    "feature_type": "BossExtrude",
                                    "direction": "Blind",
                                    "depth_mm": 25.0,
                                    "name": "基体-拉伸1"
                                },
                                {
                                    "step": 3,
                                    "feature_type": "CutExtrude",
                                    "plane": "零件顶面",
                                    "description": "导轨对中配合沉槽与轻量化减重槽",
                                    "depth_mm": 8.0,
                                    "name": "切除-拉伸1"
                                },
                                {
                                    "step": 4,
                                    "feature_type": "HoleWizard",
                                    "hole_type": "Counterbore (沉头螺栓孔)",
                                    "standard": "GB/T 70.1 (内六角圆柱头螺钉 M6)",
                                    "positions_count": 4,
                                    "name": "异型孔向导-安装沉孔"
                                },
                                {
                                    "step": 5,
                                    "feature_type": "HoleWizard",
                                    "hole_type": "DowelHole (精密销孔)",
                                    "fit": "⌀6H7 (+0.012/0)",
                                    "positions_count": 2,
                                    "name": "异型孔向导-定位销孔"
                                },
                                {
                                    "step": 6,
                                    "feature_type": "ChamferAndFillet",
                                    "chamfer": "C1.0 外轮廓倒钝",
                                    "fillet_radius": 3.0,
                                    "name": "倒角/圆角"
                                }
                            ]
                        }, ensure_ascii=False)
                    }
                }
            ]
        },
        {
            "role": "tool",
            "content": json.dumps({
                "status": "success",
                "part_file": main_part_name,
                "rebuild_errors": 0,
                "feature_count": 6,
                "fully_constrained": True
            }, ensure_ascii=False)
        },
        {
            "role": "assistant",
            "content": f"参数化特征树构建成功。现在自动生成【{main_part_name}】的加工工程图，执行制造级尺寸标注、配合公差与形位公差（GD&T）标定：",
            "tool_calls": [
                {
                    "id": f"call_draw_{call_id_base}",
                    "type": "function",
                    "function": {
                        "name": "cad.generate_engineering_drawing_annotation",
                        "arguments": json.dumps({
                            "drawing_name": os.path.splitext(main_part_name)[0] + ".SLDDRW",
                            "sheet_format": "A3_Landscape (GB标配标题栏)",
                            "views": ["主视图(1:2)", "俯视图(1:2)", "全剖左视图(1:2 A-A剖切)", "等轴测轴测图(1:2)"],
                            "fits_and_tolerances": [
                                {"feature": "导轨配合导向槽", "nominal_mm": 20.0, "tolerance": "H7 (+0.021/0)"},
                                {"feature": "双定位销孔中心距", "nominal_mm": 220.0, "tolerance": "±0.015"},
                                {"feature": "销孔内径", "nominal_mm": 6.0, "tolerance": "H7 (+0.012/0)"}
                            ],
                            "geometric_tolerances_gdt": [
                                {"symbol": "parallelism (平行度)", "value_mm": 0.015, "datum": "A (大底安装基准面)"},
                                {"symbol": "perpendicularity (垂直度)", "value_mm": 0.02, "datum": "A"},
                                {"symbol": "flatness (平面度)", "value_mm": 0.012, "datum": "A"}
                            ],
                            "roughness": "基准配合槽 Ra 1.6，定位销孔 Ra 0.8，其余加工表面 Ra 3.2",
                            "technical_notes": [
                                "1. 零件去毛刺倒角钝化，锐边倒圆 R0.5；",
                                "2. 精加工前做去应力时效退火，防止机加工内应力释放变形；",
                                "3. 表面本色阳极氧化或发黑防锈处理，膜层均匀；",
                                "4. 销孔配合严格按 GB/T 1800 H7 执行，严禁手工扩孔。"
                            ]
                        }, ensure_ascii=False)
                    }
                }
            ]
        },
        {
            "role": "tool",
            "content": json.dumps({
                "status": "success",
                "drawing_file": os.path.splitext(main_part_name)[0] + ".SLDDRW",
                "views_generated": 4,
                "dimension_callouts": 36,
                "gdt_frames_attached": 3,
                "title_block_populated": True
            }, ensure_ascii=False)
        },
        {
            "role": "assistant",
            "content": f"工程图输出就绪。现在将各子装配机构与标准件组装至【{main_asm_name}】，添加装配约束（配合配合树 Mates Tree）并进行空间干涉检查：",
            "tool_calls": [
                {
                    "id": f"call_asm_{call_id_base}",
                    "type": "function",
                    "function": {
                        "name": "cad.assemble_components_with_mates",
                        "arguments": json.dumps({
                            "assembly_name": main_asm_name,
                            "mates_tree": [
                                {
                                    "mate_type": "Coincident (重合)",
                                    "part1": f"{main_part_name} 基准安装槽面",
                                    "part2": "导轨滑块顶安装面",
                                    "offset_mm": 0.0
                                },
                                {
                                    "mate_type": "Concentric (同轴心)",
                                    "part1": f"{main_part_name} 定位销孔",
                                    "part2": "机架定位基准销",
                                    "offset_mm": 0.0
                                },
                                {
                                    "mate_type": "Distance (距离限制)",
                                    "part1": "作业执行拖板滑动端",
                                    "part2": "限位缓冲挡块端面",
                                    "range_mm": [0.0, 150.0]
                                },
                                {
                                    "mate_type": "Parallel (平行约束)",
                                    "part1": f"{main_part_name} 侧导向基准面",
                                    "part2": "机架主基准面"
                                }
                            ]
                        }, ensure_ascii=False)
                    }
                }
            ]
        },
        {
            "role": "tool",
            "content": json.dumps({
                "status": "success",
                "assembly_name": main_asm_name,
                "mates_applied": 4,
                "collision_check": {"interference_count": 0, "clearance_pass": True},
                "kinematics_valid": True
            }, ensure_ascii=False)
        },
        {
            "role": "assistant",
            "content": "装配体空间约束配合已完整定义，整机干涉检查 0 干涉。最后调用青沐清晨宏命令库，执行生产级批处理：一键批量输出加工 DWG、图名图号分离、焊件切割清单与整机 BOM 总重统计：",
            "tool_calls": [
                {
                    "id": f"call_macro_{call_id_base}",
                    "type": "function",
                    "function": {
                        "name": "cad.execute_solidworks_macro",
                        "arguments": json.dumps({
                            "macro_name": "青沐清晨一键输出DWG宏 + 切割清单称重宏 + 图名分离宏",
                            "target_drawings": [os.path.splitext(main_part_name)[0] + ".SLDDRW"],
                            "target_assembly": main_asm_name,
                            "options": {
                                "export_dwg": True,
                                "export_pdf": True,
                                "auto_title_separation": True,
                                "weldment_cut_list_weight": True,
                                "generate_excel_bom": True
                            }
                        }, ensure_ascii=False)
                    }
                }
            ]
        },
        {
            "role": "tool",
            "content": json.dumps({
                "status": "success",
                "dwg_files_generated": [os.path.splitext(main_part_name)[0] + ".dwg"],
                "pdf_files_generated": [os.path.splitext(main_part_name)[0] + ".pdf"],
                "bom_spreadsheet": f"BOM_{title}.xlsx",
                "execution_time_sec": 1.45
            }, ensure_ascii=False)
        },
        {
            "role": "assistant",
            "content": (
                f"### 【{title}】全流程设计与工程闭环完成！\n\n"
                f"#### 1. 意图拆解与工况规划\n"
                f"- **所属领域**：{domain}\n"
                f"- **设计节拍**：{cycle_time} s/件 | **系统负载**：{payload_kg} kg | **重复定位精度**：±0.015 mm\n\n"
                f"#### 2. 整机模块化 BOM 架构\n"
                f"- **总装配体**：`{main_asm_name}`，已拆解为 {len(sub_modules_names)} 大核心子机构：\n"
                + "\n".join([f"  - **{mod}**（包含定制机加件与自动化 COTS 标准件）" for mod in sub_modules_names]) + "\n\n"
                f"#### 3. 参数化特征建模与制造图纸\n"
                f"- **基准件特征树**：已完成 `{main_part_name}` 的 6 步 FeatureManager 严谨建模（基体拉伸、导轨配合沉槽、M6沉头孔向导、⌀6H7定位销孔、倒角圆角）；\n"
                f"- **工程图公差与GD&T**：出具 A3 图纸，精准标定 H7 基孔制配合、平行度 0.015mm、平面度 0.012mm 及表面粗糙度 Ra 1.6。\n\n"
                f"#### 4. 整机配合与自动化批处理\n"
                f"- **空间配合树**：重合、同轴心、极限距离配合施加完毕，机构干涉校验 0 碰撞；\n"
                f"- **宏命令输出**：青沐清晨宏已成功输出生产 DWG、PDF、图号分离与带焊件总重/采购明细的 `{f'BOM_{title}.xlsx'}`！"
            )
        }
    ]
    return {"id": f"virtu_agent_{call_id_base}", "equipment": title, "messages": messages}

def main():
    print(f"Scanning equipment from {SOURCE_DIR} ...")
    equipments = scan_equipment_folder(SOURCE_DIR)
    print(f"Scanned {len(equipments)} equipment projects.")
    
    # Save taxonomy JSON
    taxonomy_path = os.path.join(DIR_TAXONOMY, "automation_equipments_taxonomy.json")
    with open(taxonomy_path, "w", encoding="utf-8") as f:
        json.dump({
            "dataset_name": "100台3C、锂电自动化设备量产工程图纸结构谱系",
            "version": "1.0.0",
            "total_equipments": len(equipments),
            "total_files": sum(eq["counts"]["total_files"] for eq in equipments),
            "equipments": equipments
        }, f, ensure_ascii=False, indent=2)
    print(f"Saved equipment taxonomy -> {taxonomy_path}")
    
    # Generate Toolcall SFT datasets
    train_records = []
    val_records = []
    decomp_cases = []
    
    for idx, eq in enumerate(equipments):
        conv = generate_toolcall_conversation(eq)
        # 90% train, 10% validation
        if idx % 10 == 0:
            val_records.append(conv)
        else:
            train_records.append(conv)
        
        # Also generate structured decomposition case
        decomp_cases.append({
            "id": conv["id"],
            "title": eq["equipment_title"],
            "domain": eq["domain"],
            "assemblies_count": eq["counts"]["assemblies"],
            "parts_count": eq["counts"]["parts"],
            "drawings_count": eq["counts"]["drawings"],
            "sample_submodules": eq["assemblies"][:5],
            "sample_parts": eq["parts"][:8]
        })
    
    train_file = os.path.join(DIR_TOOLCALLS, "virtu_agent_toolcall_train.jsonl")
    val_file = os.path.join(DIR_TOOLCALLS, "virtu_agent_toolcall_val.jsonl")
    decomp_file = os.path.join(DIR_TAXONOMY, "equipment_decomposition_cases.jsonl")
    
    with open(train_file, "w", encoding="utf-8") as f:
        for r in train_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            
    with open(val_file, "w", encoding="utf-8") as f:
        for r in val_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            
    with open(decomp_file, "w", encoding="utf-8") as f:
        for r in decomp_cases:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            
    print(f"Toolcall Train records: {len(train_records)} -> {train_file}")
    print(f"Toolcall Val records:   {len(val_records)} -> {val_file}")
    print(f"Decomposition cases:    {len(decomp_cases)} -> {decomp_file}")

if __name__ == "__main__":
    main()
