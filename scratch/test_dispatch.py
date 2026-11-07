import os, sys
_ROOT = r"D:\Virtu模型"
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from bridges.tool_calling_specs import execute_tool_call

t1 = execute_tool_call('cad.infer_equipment_intent', {'equipment_type': '自动螺丝机', 'target_product': '手机中框', 'motion_axes': ['X300', 'Z100']})
print('cad.infer_equipment_intent:', t1.get('status'))

t2 = execute_tool_call('agent.verify_and_self_optimize', {'code': 'Sub main()\nEnd Sub', 'language': 'solidworks'})
print('agent.verify_and_self_optimize:', t2.get('status'))

t3 = execute_tool_call('cadcam_step_reverse', {'action': 'list'})
print('cadcam_step_reverse list:', t3.get('status'), 'count:', t3.get('count'))

t4 = execute_tool_call('web.search_technical_knowledge', {'query': 'SOLIDWORKS API'})
print('web.search_technical_knowledge:', t4.get('status'), 'results count:', len(t4.get('results', [])))

t5 = execute_tool_call('desktop.capture_screen', {})
print('desktop.capture_screen:', t5.get('status'))

t6 = execute_tool_call('cad.one_sentence_parametric_engine', {'wish': '法兰盘 外径120 内孔40'})
print('cad.one_sentence_parametric_engine:', t6.get('status'))
