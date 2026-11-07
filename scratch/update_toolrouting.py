import json
import os

path = "data/benchmark/virtu_eval_cl_v1/toolrouting.jsonl"
with open(path, "r", encoding="utf-8") as f:
    lines = [json.loads(line) for line in f if line.strip()]

system_prompt = (
    "你是 Virtu 工业智能体的工具路由器。只输出一个标准 JSON 对象，顶层键必须是 tool 与 arguments；严禁使用 name/function 键，严禁输出 markdown 围栏或解释文字。参数不足时不得编造，改为输出 {\"tool\": \"cadcam_preflight\", \"arguments\": {\"missing\": \"<缺什么>\"}}。\n"
    "可用工具与必填参数：cadcam_extreme_chain(wish, 可选 out_root/max_attempts/tier2_native)；"
    "cadcam_universal_geometry(wish, 可选 part_type∈auto/shaft/flange/keyway/bearing_bracket/sheet_metal、output_dir)；"
    "cadcam_cae_stress_analysis(spec, 可选 material/pressure_mpa/force_n/torque_nm/target_fos)；"
    "cadcam_sheetmetal_nest(parts, 可选 sheet_width/sheet_height/margin/output_dxf)；"
    "cadcam_step_reverse(action∈list/analyze, 可选 step_path/name_contains/max_bodies/detail)；"
    "cadcam_assembly_build(action∈model/assemble/drawing/full, 可选 step_path/out_dir)；"
    "cadcam_solidworks_model(wish)；cadcam_cimco_validate(program)；cadcam_vericut_simulate(project)。"
)

# Replace system prompt across all records
for rec in lines:
    rec["system"] = system_prompt

# Update v04, v05, v06, v07 for cadcam_assembly_build
lines[13] = {
    "id": "toolrouting-v04",
    "dimension": "toolrouting",
    "tier": "medium",
    "language": "zh",
    "system": system_prompt,
    "context": [],
    "prompt": "依据 STEP 逆向参数在 D:\\Virtu模型\\assets\\wheel_mold_P0.step 重建可编辑的 SOLIDWORKS 回转零件，产物输出至 D:\\Virtu模型\\scratch\\build_out，动作选择 model。只回一个工具调用 JSON。",
    "images": [],
    "max_tokens": 448,
    "tags": ["toolrouting", "closed-loop", "assembly_build", "variant"],
    "gold": {
        "answer": "{\"tool\": \"cadcam_assembly_build\", \"arguments\": {\"action\": \"model\", \"step_path\": \"D:\\\\Virtu模型\\\\assets\\\\wheel_mold_P0.step\", \"out_dir\": \"D:\\\\Virtu模型\\\\scratch\\\\build_out\"}}",
        "derivation": "路由依据：题面动词与必填参数只匹配该工具；数值逐字取自题面",
    },
    "criteria": [
        {"type": "json_object", "key": "shape", "weight": 2, "required_keys": ["tool", "arguments"], "forbidden_keys": ["name", "function"]},
        {"type": "literal_all", "key": "routes_to_assembly_build", "weight": 3, "values": ["cadcam_assembly_build"]},
        {"type": "literal_none", "key": "not_misrouted", "weight": 2, "values": ["cadcam_sheetmetal_nest", "cadcam_step_reverse"]},
        {"type": "literal_all", "key": "arguments_present", "weight": 1, "values": ["arguments", "action", "step_path", "out_dir"]},
        {"type": "enum_field", "key": "action_allowed", "weight": 1, "field_enums": {"action": ["model", "assemble", "drawing", "full"]}},
    ]
}

lines[14] = {
    "id": "toolrouting-v05",
    "dimension": "toolrouting",
    "tier": "medium",
    "language": "zh",
    "system": system_prompt,
    "context": [],
    "prompt": "根据 STEP 模型 D:\\Virtu模型\\assets\\wheel_mold_P0.step 自动拼装 4 实例并生成总成 SLDASM，输出目录 D:\\Virtu模型\\scratch\\build_out，动作选择 assemble。只回一个工具调用 JSON。",
    "images": [],
    "max_tokens": 448,
    "tags": ["toolrouting", "closed-loop", "assembly_build", "variant"],
    "gold": {
        "answer": "{\"tool\": \"cadcam_assembly_build\", \"arguments\": {\"action\": \"assemble\", \"step_path\": \"D:\\\\Virtu模型\\\\assets\\\\wheel_mold_P0.step\", \"out_dir\": \"D:\\\\Virtu模型\\\\scratch\\\\build_out\"}}",
        "derivation": "路由依据：题面动词与必填参数只匹配该工具；数值逐字取自题面",
    },
    "criteria": [
        {"type": "json_object", "key": "shape", "weight": 2, "required_keys": ["tool", "arguments"], "forbidden_keys": ["name", "function"]},
        {"type": "literal_all", "key": "routes_to_assembly_build", "weight": 3, "values": ["cadcam_assembly_build"]},
        {"type": "literal_none", "key": "not_misrouted", "weight": 2, "values": ["cadcam_universal_geometry", "cadcam_extreme_chain"]},
        {"type": "literal_all", "key": "arguments_present", "weight": 1, "values": ["arguments", "action", "step_path", "out_dir"]},
        {"type": "enum_field", "key": "action_allowed", "weight": 1, "field_enums": {"action": ["model", "assemble", "drawing", "full"]}},
    ]
}

lines[15] = {
    "id": "toolrouting-v06",
    "dimension": "toolrouting",
    "tier": "medium",
    "language": "zh",
    "system": system_prompt,
    "context": [],
    "prompt": "用国标 gb_a3 模板把模型 D:\\Virtu模型\\assets\\wheel_mold_P0.step 生成第一角工程图与等轴测视图，输出目录 D:\\Virtu模型\\scratch\\build_out，动作选择 drawing。只回一个工具调用 JSON。",
    "images": [],
    "max_tokens": 448,
    "tags": ["toolrouting", "closed-loop", "assembly_build", "variant"],
    "gold": {
        "answer": "{\"tool\": \"cadcam_assembly_build\", \"arguments\": {\"action\": \"drawing\", \"step_path\": \"D:\\\\Virtu模型\\\\assets\\\\wheel_mold_P0.step\", \"out_dir\": \"D:\\\\Virtu模型\\\\scratch\\\\build_out\"}}",
        "derivation": "路由依据：题面动词与必填参数只匹配该工具；数值逐字取自题面",
    },
    "criteria": [
        {"type": "json_object", "key": "shape", "weight": 2, "required_keys": ["tool", "arguments"], "forbidden_keys": ["name", "function"]},
        {"type": "literal_all", "key": "routes_to_assembly_build", "weight": 3, "values": ["cadcam_assembly_build"]},
        {"type": "literal_none", "key": "not_misrouted", "weight": 2, "values": ["cadcam_cae_stress_analysis", "cadcam_cimco_validate"]},
        {"type": "literal_all", "key": "arguments_present", "weight": 1, "values": ["arguments", "action", "step_path", "out_dir"]},
        {"type": "enum_field", "key": "action_allowed", "weight": 1, "field_enums": {"action": ["model", "assemble", "drawing", "full"]}},
    ]
}

lines[16] = {
    "id": "toolrouting-v07",
    "dimension": "toolrouting",
    "tier": "medium",
    "language": "zh",
    "system": system_prompt,
    "context": [],
    "prompt": "对 D:\\Virtu模型\\assets\\wheel_mold_P0.step 一次性完成回转零件参数化建模、4件位姿总成拼装与国标A3工程图出图，产物目录 D:\\Virtu模型\\scratch\\build_out，动作选择 full。只回一个工具调用 JSON。",
    "images": [],
    "max_tokens": 448,
    "tags": ["toolrouting", "closed-loop", "assembly_build", "variant"],
    "gold": {
        "answer": "{\"tool\": \"cadcam_assembly_build\", \"arguments\": {\"action\": \"full\", \"step_path\": \"D:\\\\Virtu模型\\\\assets\\\\wheel_mold_P0.step\", \"out_dir\": \"D:\\\\Virtu模型\\\\scratch\\\\build_out\"}}",
        "derivation": "路由依据：题面动词与必填参数只匹配该工具；数值逐字取自题面",
    },
    "criteria": [
        {"type": "json_object", "key": "shape", "weight": 2, "required_keys": ["tool", "arguments"], "forbidden_keys": ["name", "function"]},
        {"type": "literal_all", "key": "routes_to_assembly_build", "weight": 3, "values": ["cadcam_assembly_build"]},
        {"type": "literal_none", "key": "not_misrouted", "weight": 2, "values": ["cadcam_sheetmetal_nest", "cadcam_vericut_simulate"]},
        {"type": "literal_all", "key": "arguments_present", "weight": 1, "values": ["arguments", "action", "step_path", "out_dir"]},
        {"type": "enum_field", "key": "action_allowed", "weight": 1, "field_enums": {"action": ["model", "assemble", "drawing", "full"]}},
    ]
}

# Update v11, v12, v13, v14 for cadcam_step_reverse
lines[20] = {
    "id": "toolrouting-v11",
    "dimension": "toolrouting",
    "tier": "medium",
    "language": "zh",
    "system": system_prompt,
    "context": [],
    "prompt": "先查看工作区内有哪些可用的 STEP 文件，按文件名过滤 wheel，只回一个工具调用 JSON。",
    "images": [],
    "max_tokens": 448,
    "tags": ["toolrouting", "closed-loop", "step_reverse", "variant"],
    "gold": {
        "answer": "{\"tool\": \"cadcam_step_reverse\", \"arguments\": {\"action\": \"list\", \"name_contains\": \"wheel\"}}",
        "derivation": "路由依据：题面动词与必填参数只匹配该工具；数值逐字取自题面",
    },
    "criteria": [
        {"type": "json_object", "key": "shape", "weight": 2, "required_keys": ["tool", "arguments"], "forbidden_keys": ["name", "function"]},
        {"type": "literal_all", "key": "routes_to_step_reverse", "weight": 3, "values": ["cadcam_step_reverse"]},
        {"type": "literal_none", "key": "not_misrouted", "weight": 2, "values": ["cadcam_solidworks_model", "cadcam_assembly_build"]},
        {"type": "literal_all", "key": "arguments_present", "weight": 1, "values": ["arguments", "action", "name_contains"]},
        {"type": "enum_field", "key": "action_allowed", "weight": 1, "field_enums": {"action": ["list", "analyze"]}},
    ]
}

lines[21] = {
    "id": "toolrouting-v12",
    "dimension": "toolrouting",
    "tier": "medium",
    "language": "zh",
    "system": system_prompt,
    "context": [],
    "prompt": "对工作区内 D:\\Virtu模型\\assets\\wheel_mold_P0.step 做几何逆向测量，提取圆柱面直径谱与母线站位，只回一个工具调用 JSON。",
    "images": [],
    "max_tokens": 448,
    "tags": ["toolrouting", "closed-loop", "step_reverse", "variant"],
    "gold": {
        "answer": "{\"tool\": \"cadcam_step_reverse\", \"arguments\": {\"action\": \"analyze\", \"step_path\": \"D:\\\\Virtu模型\\\\assets\\\\wheel_mold_P0.step\"}}",
        "derivation": "路由依据：题面动词与必填参数只匹配该工具；数值逐字取自题面",
    },
    "criteria": [
        {"type": "json_object", "key": "shape", "weight": 2, "required_keys": ["tool", "arguments"], "forbidden_keys": ["name", "function"]},
        {"type": "literal_all", "key": "routes_to_step_reverse", "weight": 3, "values": ["cadcam_step_reverse"]},
        {"type": "literal_none", "key": "not_misrouted", "weight": 2, "values": ["cadcam_solidworks_model", "cadcam_universal_geometry"]},
        {"type": "literal_all", "key": "arguments_present", "weight": 1, "values": ["arguments", "action", "step_path"]},
        {"type": "enum_field", "key": "action_allowed", "weight": 1, "field_enums": {"action": ["list", "analyze"]}},
    ]
}

lines[22] = {
    "id": "toolrouting-v13",
    "dimension": "toolrouting",
    "tier": "medium",
    "language": "zh",
    "system": system_prompt,
    "context": [],
    "prompt": "对 D:\\Virtu模型\\assets\\wheel_mold_P0.step 提取回转母线和偏心孔系分布，最多分析 6 个实体，只回一个工具调用 JSON。",
    "images": [],
    "max_tokens": 448,
    "tags": ["toolrouting", "closed-loop", "step_reverse", "variant"],
    "gold": {
        "answer": "{\"tool\": \"cadcam_step_reverse\", \"arguments\": {\"action\": \"analyze\", \"step_path\": \"D:\\\\Virtu模型\\\\assets\\\\wheel_mold_P0.step\", \"max_bodies\": 6}}",
        "derivation": "路由依据：题面动词与必填参数只匹配该工具；数值逐字取自题面",
    },
    "criteria": [
        {"type": "json_object", "key": "shape", "weight": 2, "required_keys": ["tool", "arguments"], "forbidden_keys": ["name", "function"]},
        {"type": "literal_all", "key": "routes_to_step_reverse", "weight": 3, "values": ["cadcam_step_reverse"]},
        {"type": "literal_none", "key": "not_misrouted", "weight": 2, "values": ["cadcam_cimco_validate", "cadcam_extreme_chain"]},
        {"type": "literal_all", "key": "arguments_present", "weight": 1, "values": ["arguments", "action", "step_path", "max_bodies"]},
        {"type": "enum_field", "key": "action_allowed", "weight": 1, "field_enums": {"action": ["list", "analyze"]}},
    ]
}

lines[23] = {
    "id": "toolrouting-v14",
    "dimension": "toolrouting",
    "tier": "medium",
    "language": "zh",
    "system": system_prompt,
    "context": [],
    "prompt": "对指定 STEP 模型 D:\\Virtu模型\\artifacts\\cad_demo\\precision_flange.step 提取用于重建的母线站位和特征配方，打开详情模式，只回一个工具调用 JSON。",
    "images": [],
    "max_tokens": 448,
    "tags": ["toolrouting", "closed-loop", "step_reverse", "variant"],
    "gold": {
        "answer": "{\"tool\": \"cadcam_step_reverse\", \"arguments\": {\"action\": \"analyze\", \"step_path\": \"D:\\\\Virtu模型\\\\artifacts\\\\cad_demo\\\\precision_flange.step\", \"detail\": true}}",
        "derivation": "路由依据：题面动词与必填参数只匹配该工具；数值逐字取自题面",
    },
    "criteria": [
        {"type": "json_object", "key": "shape", "weight": 2, "required_keys": ["tool", "arguments"], "forbidden_keys": ["name", "function"]},
        {"type": "literal_all", "key": "routes_to_step_reverse", "weight": 3, "values": ["cadcam_step_reverse"]},
        {"type": "literal_none", "key": "not_misrouted", "weight": 2, "values": ["cadcam_sheetmetal_nest", "cadcam_universal_geometry"]},
        {"type": "literal_all", "key": "arguments_present", "weight": 1, "values": ["arguments", "action", "step_path", "detail"]},
        {"type": "enum_field", "key": "action_allowed", "weight": 1, "field_enums": {"action": ["list", "analyze"]}},
    ]
}

with open(path, "w", encoding="utf-8") as f:
    for rec in lines:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

print(f"Updated {len(lines)} records in {path}")
