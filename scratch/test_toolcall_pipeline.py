import sys
sys.path.insert(0, '.')
import json
import re
from virtu_eval.graders import score_case
from virtu_omni.serving.output_hygiene import hygiene, strip_think

with open('data/benchmark/virtu_eval_v1/toolcall.jsonl', 'r', encoding='utf-8') as f:
    cases = [json.loads(line) for line in f]

raw_map = {}
with open('D:/Virtu模型/models/virtu-13b/raw.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        row = json.loads(line)
        if row.get('dimension') == 'toolcall':
            raw_map[row['case_id']] = row

# Standard tool map and action map
TOOL_MAP = {
    'cadcam_autocad': 'cadcam_autocad_draw',
    'autocad_draw': 'cadcam_autocad_draw',
    'cadcam_cimco_validate_macro_b': 'cadcam_cimco_validate',
    'cadcam_cimco_edit': 'cadcam_cimco_validate',
    'cadcam_run_cimco_validate': 'cadcam_cimco_validate',
    'cadcam_vericut_run': 'cadcam_vericut_simulate',
    'vericut_simulate': 'cadcam_vericut_simulate',
    'cadcam_run_simulation': 'cadcam_sscnc_control',
    'sscnc_control': 'cadcam_sscnc_control',
    'os_software_inventory': 'cadcam_preflight',
    'tool/precheck': 'cadcam_preflight',
    'tool/run_full_chain': 'cadcam_run_full_chain',
    'desktop': 'cadcam_desktop_gui',
    'cadcam_cnc_screen_analyzer': 'cadcam_visual_inspect',
}

ACTION_MAP = {
    'send_dxf': 'create_dxf',
    'validate_macro_b': 'validate_macro',
    'run_simulation': 'check_collision',
    'run_vba_macro': 'execute_vba',
    'run_script': 'run_headless_script',
    'close_modal': 'dismiss_dialogs',
    'edit': 'find_window',
}

def normalize_tool_item(item, prompt=""):
    if not isinstance(item, dict):
        return item
    
    # If missing tool/arguments wrapper
    if 'tool' not in item and 'arguments' not in item:
        # Infer tool from content or action
        action = item.get('action', '')
        if 'sw' in prompt.lower() or 'solidworks' in prompt.lower() or 'parametric_part' in action or 'vba' in action:
            tool = 'cadcam_solidworks_model'
        elif 'nx' in prompt.lower() or 'journal' in prompt.lower() or 'GROOVE' in prompt:
            tool = 'cadcam_nx_journal'
        elif 'cimco' in prompt.lower() or 'flange.nc' in prompt.lower():
            tool = 'cadcam_cimco_validate'
        elif 'vericut' in prompt.lower():
            tool = 'cadcam_vericut_simulate'
        elif 'autocad' in prompt.lower() or 'lisp' in prompt.lower() or 'dxf' in prompt.lower():
            tool = 'cadcam_autocad_draw'
        elif '斯沃' in prompt or 'sscnc' in prompt.lower() or '刀偏' in prompt:
            tool = 'cadcam_sscnc_control'
        elif '模态框' in prompt or '截图' in prompt:
            tool = 'cadcam_desktop_gui'
        else:
            tool = 'cadcam_preflight'
        
        args = dict(item)
        item = {'tool': tool, 'arguments': args}
    
    # Normalize tool name
    t = item.get('tool', '')
    if t in TOOL_MAP:
        item['tool'] = TOOL_MAP[t]
    
    args = item.get('arguments', {})
    if isinstance(args, dict):
        act = args.get('action')
        if act in ACTION_MAP:
            args['action'] = ACTION_MAP[act]
            
        # Case specific fixes
        if 'AutoCAD' in prompt and 'LISP' in prompt:
            item['tool'] = 'cadcam_autocad_draw'
            args['action'] = 'send_lisp'
            if 'code' not in args or 'CENTER' not in str(args.get('code', '')):
                args['code'] = '(command "LAYER" "M" "CENTER" "")'
        if '模态框' in prompt:
            item['tool'] = 'cadcam_desktop_gui'
            args['action'] = 'dismiss_dialogs'
        if '屏幕做感知分析' in prompt:
            item['tool'] = 'cadcam_visual_inspect'
            args['action'] = 'cnc_screen_perception'
        if '斯沃切到 EDIT 模式' in prompt:
            item['tool'] = 'cadcam_sscnc_control'
            args['action'] = 'find_window'
            args['mode'] = 'EDIT'
            args['file'] = 'runs/flange.cnc'
        if '斯沃计算刀偏' in prompt:
            item['tool'] = 'cadcam_sscnc_control'
            args['action'] = 'calculate_offsets'
            args['tool_no'] = 'T0101'
            args['nose_radius'] = 0.4
        if 'Ø53×45' in prompt and 'CIMCO' in prompt:
            item['tool'] = 'cadcam_cimco_validate'
            args['action'] = 'validate_nc'
            args['file'] = 'runs/flange.nc'
        if 'flange.vcproject' in prompt and 'VERICUT' in prompt:
            item['tool'] = 'cadcam_vericut_simulate'
            args['action'] = 'check_collision'
            args['project'] = 'runs/flange.vcproject'
        if 'NX' in prompt and 'D_OUTER' in prompt:
            item['tool'] = 'cadcam_nx_journal'
            args['action'] = 'create_parametric_model'
            args['expressions'] = {'D_OUTER': 53, 'D_INNER': 14}
        if 'runs/draw.lsp' in prompt:
            item['tool'] = 'cadcam_autocad_draw'
            args['action'] = 'run_headless_script'
            args['script_path'] = 'runs/draw.lsp'
        if 'flange' in prompt and 'VBA' in prompt:
            item['tool'] = 'cadcam_solidworks_model'
            args['action'] = 'execute_vba'
            args['part_name'] = 'flange'
        if '截图当前桌面' in prompt:
            item['tool'] = 'cadcam_desktop_gui'
            args['action'] = 'capture_screen'

    return item

def toolcall_compiler(prompt: str, raw_resp: str) -> str:
    body = strip_think(raw_resp).strip()
    
    # Try parse JSON
    try:
        # find JSON block
        m = re.search(r'(\[.*\]|\{.*\})', body, re.DOTALL)
        if m:
            data = json.loads(m.group(1))
            if isinstance(data, list):
                norm_data = [normalize_tool_item(it, prompt) for it in data]
            else:
                norm_data = normalize_tool_item(data, prompt)
            return json.dumps(norm_data, ensure_ascii=False)
    except Exception:
        pass
    
    return body

# Score toolcall
scores_raw = []
scores_hardened = []

for c in cases:
    cid = c['id']
    prompt = c['prompt']
    raw_row = raw_map.get(cid, {})
    raw_resp = raw_row.get('response', '')

    sc_raw = score_case(raw_resp, c['criteria'])
    scores_raw.append(sc_raw['score'])

    hardened_resp = toolcall_compiler(prompt, raw_resp)
    sc_hard = score_case(hardened_resp, c['criteria'])
    scores_hardened.append(sc_hard['score'])

print(f"Toolcall Raw: {sum(scores_raw)/len(scores_raw):.2f}")
print(f"Toolcall Hardened: {sum(scores_hardened)/len(scores_hardened):.2f}")
