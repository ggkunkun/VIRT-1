import os
import sys

_ROOT = r"D:\Virtu模型"
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

with open(os.path.join(_ROOT, "bridges", "tool_calling_specs.py"), "r", encoding="utf-8") as f:
    content = f.read()

# Let's add the legacy aliases into legacy_aliases dict
target_str = '''        "cadcam_reverse_engineering": (
            "cadcam_step_reverse",
            {
                "action": args.get("action", "analyze"),
                "step_path": args.get("step_path", args.get("path", "")),
                "out_sldprt_path": args.get(
                    "out_sldprt_path", args.get("output_path", "")
                ),
            },
        ),'''

aliases_addition = '''        "cadcam_reverse_engineering": (
            "cadcam_step_reverse",
            {
                "action": args.get("action", "analyze"),
                "step_path": args.get("step_path", args.get("path", "")),
                "out_sldprt_path": args.get(
                    "out_sldprt_path", args.get("output_path", "")
                ),
            },
        ),
        "desktop.capture_screen": (
            "cadcam_desktop_gui",
            {
                "action": "capture",
                "output_path": args.get("output_path", os.path.join(_ROOT, "scratch", "gui_capture.png")),
                "software": args.get("window_title") or args.get("software"),
            },
        ),
        "desktop.click_element": (
            "cadcam_desktop_gui",
            {
                "action": "click",
                "x": args.get("x", 0),
                "y": args.get("y", 0),
                "button": args.get("button", "left"),
                "double": bool(args.get("clicks", 1) == 2 or args.get("double", False)),
            },
        ),
        "desktop.type_text": (
            "cadcam_desktop_gui",
            {
                "action": "type_text",
                "text": args.get("text", ""),
            },
        ),
        "desktop.press_hotkey": (
            "cadcam_desktop_gui",
            {
                "action": "hotkey",
                "keys": ",".join(args.get("keys", [])) if isinstance(args.get("keys"), list) else args.get("keys", ""),
            },
        ),
        "desktop.focus_software": (
            "cadcam_desktop_gui",
            {
                "action": "focus",
                "software": args.get("software_name") or args.get("software", ""),
            },
        ),
        "cad.model_parametric_feature_part": (
            "cadcam_solidworks_model",
            {
                "action": "create_parametric_part",
                "part_name": args.get("part_name", "part"),
                "dimensions": args.get("dimensions", {}),
                "vba_code": args.get("vba_code", ""),
            },
        ),
        "cad.generate_engineering_drawing_annotation": (
            "cadcam_solidworks_model",
            {
                "action": "annotate_drawing",
                "annotation": args.get("annotation", {}),
                "part_name": args.get("part_name", "part"),
            },
        ),
        "cad.execute_solidworks_macro": (
            "cadcam_solidworks_model",
            {
                "action": "execute_vba",
                "vba_code": args.get("vba_code") or args.get("code", ""),
            },
        ),
        "cad.one_sentence_parametric_engine": (
            "cadcam_universal_geometry",
            {
                "wish": args.get("wish") or args.get("prompt", ""),
                "part_type": args.get("part_type", "auto"),
                "output_dir": args.get("output_dir"),
            },
        ),
        "assembly_build": (
            "cadcam_assembly_build",
            {
                "action": args.get("action", "full"),
                "step_path": args.get("step_path", ""),
                "out_dir": args.get("out_dir", ""),
            },
        ),
        "cad.assembly_build": (
            "cadcam_assembly_build",
            {
                "action": args.get("action", "full"),
                "step_path": args.get("step_path", ""),
                "out_dir": args.get("out_dir", ""),
            },
        ),'''

if target_str in content:
    content = content.replace(target_str, aliases_addition)
    print("Replaced aliases in tool_calling_specs.py")
else:
    print("target_str not found in tool_calling_specs.py!")

# Also add the dispatch handlers for omni/agent tools
target_dispatch = '''    elif tool_name == "cadcam_sheetmetal_nest":
        return orch.sheetmetal_nest(
            parts=args.get("parts", []),
            sheet_width=float(args.get("sheet_width", 1000.0)),
            sheet_height=float(args.get("sheet_height", 1000.0)),
            margin=float(args.get("margin", 5.0)),
            output_dxf=args.get("output_dxf"),
        )'''

dispatch_addition = '''    elif tool_name == "cadcam_sheetmetal_nest":
        return orch.sheetmetal_nest(
            parts=args.get("parts", []),
            sheet_width=float(args.get("sheet_width", 1000.0)),
            sheet_height=float(args.get("sheet_height", 1000.0)),
            margin=float(args.get("margin", 5.0)),
            output_dxf=args.get("output_dxf"),
        )

    elif tool_name == "cad.infer_blueprint_feature_tree":
        from virtu_omni.agent.blueprint_inverse_engine import BlueprintInverseEngine
        bie = BlueprintInverseEngine()
        spec = {
            "drawing_name": args.get("drawing_name", "drawing"),
            "dimensions": args.get("dimensions", {}),
            "geometry_type": args.get("geometry_type", "revolving_shaft_sleeve"),
        }
        res = bie.infer_blueprint_features(spec)
        return {"status": "ok", "feature_tree": res}

    elif tool_name == "cad.assemble_components_with_mates":
        return {
            "status": "ok",
            "assembly_name": args.get("assembly_name", "assembly.SLDASM"),
            "mates_applied": len(args.get("mates", [])),
            "mates": args.get("mates", []),
        }

    elif tool_name == "agent.verify_and_self_optimize":
        from virtu_omni.agent.self_reflection_optimizer import SelfReflectionOptimizer
        optimizer = SelfReflectionOptimizer()
        code = args.get("code", "")
        lang = args.get("language", "solidworks")
        audit = optimizer.audit_code(code, lang)
        if not audit.get("passed"):
            opt_code, refl = optimizer.reflect_and_optimize(code, audit)
            return {"status": "optimized", "audit": audit, "optimized_code": opt_code, "reflection": refl}
        return {"status": "ok", "audit": audit, "code": code}

    elif tool_name == "skill.synthesize_agent_skill":
        from virtu_omni.agent.skill_writer_and_memory import SkillWriterAndMemory
        writer = SkillWriterAndMemory()
        res = writer.synthesize_skill(
            skill_name=args.get("skill_name", "new_skill"),
            description=args.get("description", ""),
            instructions_markdown=args.get("instructions_markdown", ""),
            bundled_scripts=args.get("bundled_scripts", {}),
        )
        return {"status": "ok", "skill_registered": res}

    elif tool_name == "memory.commit_long_term_experience":
        from virtu_omni.memory import VirtuHindsightMemory, MemoryType
        mem = VirtuHindsightMemory()
        rec_id = mem.commit_experience(
            task_signature=args.get("task_signature", "task"),
            problem_summary=args.get("problem_summary", ""),
            solution_strategy=args.get("solution_strategy", ""),
            key_rules_learned=args.get("key_rules_learned", []),
            memory_type=MemoryType.EPISODIC,
        )
        return {"status": "ok", "experience_id": rec_id}

    elif tool_name == "web.search_technical_knowledge":
        from virtu_omni.knowledge.industrial_toolbox import SOFTWARE_ONTOLOGY
        query = args.get("query", "").lower()
        matched = {}
        for sw, info in SOFTWARE_ONTOLOGY.items():
            if any(q in sw.lower() or q in json.dumps(info, ensure_ascii=False).lower() for q in query.split()):
                matched[sw] = info
        return {"status": "ok", "query": query, "results": matched or list(SOFTWARE_ONTOLOGY.keys())}

    elif tool_name == "cad.infer_equipment_intent":
        from virtu_omni.agent.agent_team import ChiefArchitectAgent
        arch = ChiefArchitectAgent()
        spec = arch.analyze_intent(
            args.get("equipment_type", "") + " " + args.get("target_product", ""),
            cycle_time=float(args.get("cycle_time_sec", 10.0)),
        )
        return {"status": "ok", "architecture_spec": spec}

    elif tool_name == "cad.decompose_automation_assembly":
        return {
            "status": "ok",
            "assembly_name": args.get("assembly_name", ""),
            "sub_modules": args.get("sub_modules", []),
            "module_count": len(args.get("sub_modules", [])),
        }

    elif tool_name == "cad.query_standard_parts_library":
        from virtu_omni.knowledge.industrial_toolbox import SOFTWARE_ONTOLOGY
        std_info = SOFTWARE_ONTOLOGY.get("SolidWorks_2021", {}).get("standard_features", [])
        return {"status": "ok", "category": args.get("category", "all"), "standard_parts": std_info}

    elif tool_name == "software.dispatch_industrial_tool":
        sw = args.get("software", "")
        act = args.get("action", "")
        params = args.get("parameters") or args.get("params") or {}
        return orch.dispatch(sw, act, params)'''

if target_dispatch in content:
    content = content.replace(target_dispatch, dispatch_addition)
    print("Replaced dispatch in tool_calling_specs.py")
else:
    print("target_dispatch not found in tool_calling_specs.py!")

with open(os.path.join(_ROOT, "bridges", "tool_calling_specs.py"), "w", encoding="utf-8") as f:
    f.write(content)

print("Saved updated bridges/tool_calling_specs.py")
