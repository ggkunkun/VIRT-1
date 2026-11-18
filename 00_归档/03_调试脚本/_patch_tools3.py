# -*- coding: utf-8 -*-
"""稳健补丁：注册 cadcam_assembly_build + step_reverse 的 assembly 动作。"""
import os

SPECS = r"D:\Virtu模型\bridges\tool_calling_specs.py"
BRIDGE = r"D:\Virtu模型\scripts\workbuddy_virtu_bridge.py"
NL = b"\n"

b = open(SPECS, "rb").read()
if b'"cadcam_assembly_build"' in b:
    raise SystemExit("ALREADY_PATCHED")

tool_lines = [
    '    {',
    '        "type": "function",',
    '        "function": {',
    '            "name": "cadcam_assembly_build",',
    '            "description": "逆向工程后的建模/拼装/出图执行器。model=按 STEP 母线剖面与孔系参数化重建可编辑回转件 .SLDPRT；assemble=导入 STEP 总成、按 4 个实例位姿自动拼装并另存 .SLDASM（几何零损失，最省特征）；drawing=用国标 gb_a3 模板生成第一角三视图+等轴测 .SLDDRW；full=一次依次完成三者并返回每个文件的体积/组件数/视图证据。选择哪个动作由你自己决定。",',
    '            "parameters": {',
    '                "type": "object",',
    '                "properties": {',
    '                    "action": {',
    '                        "type": "string",',
    '                        "enum": ["model", "assemble", "drawing", "full"],',
    '                        "description": "model / assemble / drawing / full（默认 full 一次交付三件）"',
    '                    },',
    '                    "step_path": {',
    '                        "type": "string",',
    '                        "description": "工作区内 STEP 绝对路径；留空则用 assets/wheel_mold_P0.step"',
    '                    },',
    '                    "out_dir": {',
    '                        "type": "string",',
    '                        "description": "产物目录（必须位于工作区内）；留空用 runs/virtu_assembly"',
    '                    }',
    '                },',
    '                "required": []',
    '            }',
    '        }',
    '    }',
]
tool_def = NL.join(x.encode("utf-8") for x in tool_lines)

# 在 CADCAM_TOOLS_DEFINITION 的收尾 ']' 前插入（位置无关）
defpos = b.find(b"def get_cadcam_tool_definitions")
close = b.rfind(b"]", 0, defpos)
if close < 0:
    raise SystemExit("MISS list close bracket")
prefix = b[:close].rstrip()
b = prefix + b"," + NL + tool_def + NL + b"]" + b[close + 1:]
print("OK tool_def")

# step_reverse 的 action 枚举补 assembly
old = b'"enum": ["list", "analyze"]'
if old in b:
    b = b.replace(old, b'"enum": ["list", "analyze", "assembly"]', 1)
    print("OK enum")

# 执行分支：插在 cadcam_step_reverse 分支之前
anchor = b'    elif tool_name == "cadcam_step_reverse":'
exec_lines = [
    '    elif tool_name == "cadcam_assembly_build":',
    '        from bridges.assembly_build import build as _build_asm',
    '        return _build_asm(',
    '            step_path=args.get("step_path", ""),',
    '            out_dir=args.get("out_dir", ""),',
    '            action=args.get("action", "full"),',
    '            workspace_root=_ROOT,',
    '        )',
]
exec_block = NL.join(x.encode("utf-8") for x in exec_lines)
if anchor in b:
    b = b.replace(anchor, exec_block + NL + anchor, 1)
    print("OK exec_branch")
else:
    raise SystemExit("MISS exec anchor")

# out_dir 纳入路径防护（宽松匹配）
if b'"out_dir"' not in b.split(b"path_param_keys")[1][:500]:
    old_pk = b'"step_path"'
    i = b.find(b"path_param_keys")
    seg_end = b.find(b")", i)
    j = b.find(old_pk, i, seg_end)
    if j > 0:
        b = b[:j + len(old_pk)] + b', "out_dir"' + b[j + len(old_pk):]
        print("OK path_param")
open(SPECS, "wb").write(b)
print("SPECS", len(b))

# 桥白名单
c = open(BRIDGE, "rb").read()
if b'"cadcam_assembly_build"' not in c:
    anchor2 = b'        "cadcam_step_reverse",'
    if anchor2 not in c:
        raise SystemExit("MISS bridge whitelist")
    c = c.replace(anchor2, anchor2 + b'\n        "cadcam_assembly_build",', 1)
    open(BRIDGE, "wb").write(c)
    print("OK bridge whitelist")
print("ALL_OK")
