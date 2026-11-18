# -*- coding: utf-8 -*-
"""字节级补丁：注册 cadcam_step_reverse（保留原文件 \r\r\n 行尾）。"""
import os
import shutil

ROOT = r"D:\Virtu模型"
SPECS = os.path.join(ROOT, "bridges", "tool_calling_specs.py")
BRIDGE = os.path.join(ROOT, "scripts", "workbuddy_virtu_bridge.py")
SERVICE = os.path.join(ROOT, "scripts", "start_bridge_service.py")
NL = b"\r\r\n"


def patch(path, replacements, backup=True):
    if backup and not os.path.exists(path + ".bak_stepreverse"):
        shutil.copy2(path, path + ".bak_stepreverse")
    b = open(path, "rb").read()
    for old, new, label in replacements:
        if old not in b:
            raise SystemExit("PATCH_MISS %s :: %s" % (os.path.basename(path), label))
        if label == "tool_def" and b'"cadcam_step_reverse"' in b:
            raise SystemExit("ALREADY_PATCHED %s" % label)
        b = b.replace(old, new, 1)
    open(path, "wb").write(b)
    print("PATCHED", os.path.basename(path), len(b), "bytes")


tool_def_lines = [
    '    {',
    '        "type": "function",',
    '        "function": {',
    '            "name": "cadcam_step_reverse",',
    '            "description": "STEP 几何逆向测量：直接解析 STEP AP203/AP214 文本，不打开 CAD 即可返回产品树、包围盒、圆柱面直径谱、锥面半角，并按 MANIFOLD_SOLID_BREP 拆出每个实体的面数/母线圆弧/偏心孔系，最后给出 rebuild_recipe（回转母线站位+孔分布）。用于从 .step 反求尺寸后自行决定参数化建模策略。第一步可先用 action=list 找到工作区内的 STEP 文件。",',
    '            "parameters": {',
    '                "type": "object",',
    '                "properties": {',
    '                    "action": {',
    '                        "type": "string",',
    '                        "enum": ["list", "analyze"],',
    '                        "description": "list=列出工作区 assets 下可用的 STEP 文件；analyze=对 step_path 做几何逆向测量"',
    '                    },',
    '                    "step_path": {',
    '                        "type": "string",',
    '                        "description": "工作区内 .step 文件的绝对路径（action=analyze 时必填）"',
    '                    },',
    '                    "name_contains": {',
    '                        "type": "string",',
    '                        "description": "action=list 时按文件名子串过滤，可选"',
    '                    },',
    '                    "max_bodies": {',
    '                        "type": "integer",',
    '                        "description": "最多返回的实体明细数，默认 12"',
    '                    }',
    '                },',
    '                "required": []',
    '            }',
    '        }',
    '    }',
]
tool_def = NL.join(x.encode("utf-8") for x in tool_def_lines)

exec_lines = [
    '    elif tool_name == "cadcam_step_reverse":',
    '        from bridges.step_reverse import reverse_step',
    '        return reverse_step(',
    '            step_path=args.get("step_path", ""),',
    '            action=args.get("action", "analyze"),',
    '            workspace_root=_ROOT,',
    '            max_bodies=int(args.get("max_bodies", 12)),',
    '            name_contains=args.get("name_contains", ""),',
    '        )',
]
exec_block = NL.join(x.encode("utf-8") for x in exec_lines)

patch(SPECS, [
    (b'    }' + NL + b']' + NL + NL + NL + b'def get_cadcam_tool_definitions()',
     b'    },' + NL + tool_def + NL + b']' + NL + NL + NL + b'def get_cadcam_tool_definitions()',
     'tool_def'),
    (b'    if tool_name == "cadcam_preflight":' + NL + b'        return orch.preflight()' + NL,
     b'    if tool_name == "cadcam_preflight":' + NL + b'        return orch.preflight()' + NL + exec_block + NL,
     'exec_branch'),
    (b'"project_path", "log_path", "output_path", "output_dxf", "file_path", "target_path"',
     b'"project_path", "log_path", "output_path", "output_dxf", "file_path", "target_path",\n        "step_path"',
     'path_param'),
])

# 桥的 /v1/cadcam/tools/call 白名单：补齐原先遗漏的 4 个工具 + 新工具
patch(BRIDGE, [
    (b'        "vericut.create_project_config", "sscnc.create_setup_guide", "ontology.lookup_plugin",',
     b'        "vericut.create_project_config", "sscnc.create_setup_guide", "ontology.lookup_plugin",\n'
     b'        "cadcam_extreme_chain", "cadcam_universal_geometry",\n'
     b'        "cadcam_cae_stress_analysis", "cadcam_sheetmetal_nest",\n'
     b'        "cadcam_step_reverse",',
     'safe_tools'),
])

# 重启器 stop_bridge 未匹配 pinned 入口，导致 --restart 停不掉当前服务
patch(SERVICE, [
    (b'        if ("start_virtu_bridge.py" not in cmd\n'
     b'                and "workbuddy_virtu_bridge.py" not in cmd\n'
     b'                and "run_virtu_service.py" not in cmd):',
     b'        if ("start_virtu_bridge.py" not in cmd\n'
     b'                and "workbuddy_virtu_bridge.py" not in cmd\n'
     b'                and "run_virtu_service.py" not in cmd\n'
     b'                and "virtu_service_pinned.py" not in cmd):',
     'stop_match'),
])
print("ALL_PATCHES_OK")
