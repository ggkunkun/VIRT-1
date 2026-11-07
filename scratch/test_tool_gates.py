import sys
sys.path.insert(0, r"D:\Virtu模型")
from bridges.tool_calling_specs import execute_tool_call

t1 = execute_tool_call('cadcam_run_full_chain', {'wish': 'flange', 'out_root': 'C:/Windows/System32'})
print('T1 Path traversal blocked:', t1.get('status') == 'blocked', t1.get('verdict_code'))

t2 = execute_tool_call('cadcam_solidworks_model', {'action': 'execute_vba', 'vba_code': 'Sub main()\nShell "cmd.exe"\nEnd Sub'})
print('T2 VBA Shell blocked:', t2.get('status') == 'blocked', t2.get('verdict_code'))

t3 = execute_tool_call('cadcam_autocad_draw', {'action': 'send_lisp', 'code': '(startapp "cmd.exe")'})
print('T3 AutoLISP blocked:', t3.get('status') == 'blocked', t3.get('verdict_code'))

t4 = execute_tool_call('cadcam_cimco_validate', {'action': 'validate_macro', 'code': 'G00 X0 Y0 Z-50.0'})
print('T4 G-code plunge blocked:', t4.get('status') == 'blocked', t4.get('verdict_code'))

t5 = execute_tool_call('cadcam_preflight', {})
print('T5 Preflight ran without blockage:', t5.get('status') != 'blocked')
