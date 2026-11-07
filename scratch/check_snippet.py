with open('bridges/tool_calling_specs.py', encoding='utf-8') as f:
    text = f.read()
idx = text.find('cad.infer_equipment_intent')
print(text[idx-30:idx+350])
