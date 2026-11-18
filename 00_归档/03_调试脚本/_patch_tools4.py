# -*- coding: utf-8 -*-
"""注册 cadcam_feature_ops（原子执行器，不含策略）。"""
SPECS = r"D:\Virtu模型\bridges\tool_calling_specs.py"
BRIDGE = r"D:\Virtu模型\scripts\workbuddy_virtu_bridge.py"
NL = b"\n"

b = open(SPECS, "rb").read()
if b'"cadcam_feature_ops"' in b:
    raise SystemExit("ALREADY_PATCHED")

lines = [
    '    {',
    '        "type": "function",',
    '        "function": {',
    '            "name": "cadcam_feature_ops",',
    '            "description": "原子特征执行器：不提供任何一键策略，只按你自己给出的方案逐步执行。action=measure 返回 STEP 原始测量数据（母线闭合点列、直径谱、孔系、包围盒）；action=execute_plan 严格按 plan.ops 顺序执行，每个 op 后立即读质量属性形成证据链，不认识或缺参数的 op 如实报错、绝不自动补齐。",',
    '            "parameters": {',
    '                "type": "object",',
    '                "properties": {',
    '                    "action": {"type": "string", "enum": ["measure", "execute_plan"], "description": "measure=读测量数据；execute_plan=按你的方案执行"},',
    '                    "plan": {',
    '                        "type": "object",',
    '                        "description": "建模方案。格式 {\'ops\':[ ... ]}。可用 op 按你的方法自行排序：new_part；sketch_profile(source=step_meridian 或 points=[[x,r],...], plane)；revolve(angle_deg)；sketch_holes(pcd_mm,hole_dia_mm,count,angles_deg,plane)；cut(type=through_all)；save_part(name)；import_assembly(step_path)；save_assembly(name)；drawing(template,first_angle,isometric,model_path,name)；verify。特征顺序、参数、是否使用某步骤全由你决定。",',
    '                        "properties": {',
    '                            "ops": {"type": "array", "items": {"type": "object"}},',
    '                            "method_reason": {"type": "string", "description": "你选择这套特征顺序与参数的理由"},',
    '                            "expected_volume_mm3": {"type": "number", "description": "你预期最终体积，用于与实测对比"}',
    '                        }',
    '                    },',
    '                    "step_path": {"type": "string", "description": "工作区内 STEP 绝对路径"},',
    '                    "out_dir": {"type": "string", "description": "产物目录（工作区内）"}',
    '                },',
    '                "required": []',
    '            }',
    '        }',
    '    }',
]
tool_def = NL.join(x.encode("utf-8") for x in lines)
defpos = b.find(b"def get_cadcam_tool_definitions")
close = b.rfind(b"]", 0, defpos)
b = b[:close].rstrip() + b"," + NL + tool_def + NL + b"]" + b[close + 1:]

exec_lines = [
    '    elif tool_name == "cadcam_feature_ops":',
    '        from bridges.feature_ops import feature_ops as _fops',
    '        return _fops(',
    '            action=args.get("action", "measure"),',
    '            plan=args.get("plan"),',
    '            step_path=args.get("step_path", ""),',
    '            out_dir=args.get("out_dir", ""),',
    '            workspace_root=_ROOT,',
    '        )',
]
anchor = b'    elif tool_name == "cadcam_assembly_build":'
if anchor not in b:
    raise SystemExit("MISS exec anchor")
b = b.replace(anchor, NL.join(x.encode("utf-8") for x in exec_lines) + NL + anchor, 1)
open(SPECS, "wb").write(b)
print("SPECS_OK", len(b))

c = open(BRIDGE, "rb").read()
if b'"cadcam_feature_ops"' not in c:
    a2 = b'        "cadcam_assembly_build",'
    if a2 not in c:
        raise SystemExit("MISS bridge anchor")
    c = c.replace(a2, a2 + b'\n        "cadcam_feature_ops",', 1)
    open(BRIDGE, "wb").write(c)
    print("BRIDGE_OK")
print("ALL_OK")
