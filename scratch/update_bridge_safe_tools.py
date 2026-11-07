with open('scripts/workbuddy_virtu_bridge.py', 'r', encoding='utf-8') as f:
    text = f.read()

target = '''        "cadcam_step_reverse",
        "cadcam_assembly_build",
    }'''

replacement = '''        "cadcam_step_reverse",
        "cadcam_assembly_build",
        "assembly_build", "cad.assembly_build", "step_reverse",
        "reverse_step_model", "cadcam_reverse_engineering",
        # Omni / Desktop
        "desktop.capture_screen", "desktop.click_element", "desktop.type_text",
        "desktop.press_hotkey", "desktop.focus_software",
        # CAD agent
        "cad.infer_blueprint_feature_tree", "cad.assemble_components_with_mates",
        "cad.infer_equipment_intent", "cad.decompose_automation_assembly",
        "cad.query_standard_parts_library", "cad.model_parametric_feature_part",
        "cad.generate_engineering_drawing_annotation", "cad.execute_solidworks_macro",
        "cad.one_sentence_parametric_engine", "software.dispatch_industrial_tool",
        # Agent / Skill / Memory / Web
        "agent.verify_and_self_optimize", "skill.synthesize_agent_skill",
        "memory.commit_long_term_experience", "web.search_technical_knowledge",
    }'''

if target in text:
    text = text.replace(target, replacement)
    with open('scripts/workbuddy_virtu_bridge.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print("Updated safe_tools in scripts/workbuddy_virtu_bridge.py")
else:
    print("Target not found in scripts/workbuddy_virtu_bridge.py")
