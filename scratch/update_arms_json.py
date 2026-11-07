import os, sys, json
_ROOT = r"D:\Virtu模型"
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from bridges.tool_calling_specs import CADCAM_TOOLS_DEFINITION

arms_path = os.path.join(_ROOT, "virtu_eval", "arms.json")
with open(arms_path, "r", encoding="utf-8") as f:
    arms = json.load(f)

updated_count = 0
for arm_name, arm_data in arms.items():
    if arm_data and isinstance(arm_data, dict) and "tools" in arm_data and isinstance(arm_data["tools"], list) and len(arm_data["tools"]) > 0:
        arm_data["tools"] = CADCAM_TOOLS_DEFINITION
        updated_count += 1

with open(arms_path, "w", encoding="utf-8") as f:
    json.dump(arms, f, ensure_ascii=False, indent=2)

print(f"Updated {updated_count} arms in {arms_path} with {len(CADCAM_TOOLS_DEFINITION)} tools each.")
