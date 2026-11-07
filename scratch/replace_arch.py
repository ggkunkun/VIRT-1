with open('bridges/tool_calling_specs.py', 'r', encoding='utf-8') as f:
    text = f.read()

old_block = '''    elif tool_name == "cad.infer_equipment_intent":
        from virtu_omni.agent.agent_team import ChiefArchitectAgent

        arch = ChiefArchitectAgent()
        spec = arch.analyze_intent(
            args.get("equipment_type", "") + " " + args.get("target_product", ""),
            cycle_time=float(args.get("cycle_time_sec", 10.0)),
        )
        return {"status": "ok", "architecture_spec": spec}'''

new_block = '''    elif tool_name == "cad.infer_equipment_intent":
        from virtu_omni.agent.agent_team import ChiefArchitectAgent

        arch = ChiefArchitectAgent()
        prompt = args.get("equipment_type", "") + " " + args.get("target_product", "")
        spec = arch.run({"user_prompt": prompt})
        return {"status": "ok", "architecture_spec": spec}'''

if old_block in text:
    text = text.replace(old_block, new_block)
    with open('bridges/tool_calling_specs.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print("Replaced successfully!")
else:
    print("Not found in text!")
