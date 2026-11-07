with open('bridges/tool_calling_specs.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace(
    "from virtu_omni.knowledge.industrial_toolbox import SOFTWARE_ONTOLOGY",
    "from virtu_omni.knowledge.software_plugin_ontology import SOFTWARE_ONTOLOGY"
)

with open('bridges/tool_calling_specs.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Updated SOFTWARE_ONTOLOGY import")
