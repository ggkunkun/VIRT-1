import json
import sys
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

prompt = """<|im_start|>system
你是一个严谨的工业智能体，具备自主调用 CAD/CAM 工具的能力。当用户提出建模或加工需求时，必须输出合规的 tool_call。<|im_end|>
<|im_start|>user
请在 SolidWorks 中为我创建一个名为 shaft_step_100 的阶梯轴，材料使用 45号钢，包含两段圆柱特征：第一段直径50mm长100mm，第二段直径30mm长50mm。<|im_end|>
<|im_start|>assistant
"""

payload = {
    'model': 'virtu-master:v4',
    'prompt': prompt,
    'stream': False,
    'options': {'temperature': 0.1, 'num_predict': 400}
}

req = urllib.request.Request(
    'http://localhost:11434/api/generate',
    data=json.dumps(payload).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)

try:
    resp = urllib.request.urlopen(req, timeout=30)
    res = json.loads(resp.read().decode('utf-8'))
    print("=== virtu-master:v4 真实工业交互与函数调用响应 ===")
    print(res.get('response'))
    print("=" * 60)
except Exception as e:
    print(f"请求失败: {e}")
