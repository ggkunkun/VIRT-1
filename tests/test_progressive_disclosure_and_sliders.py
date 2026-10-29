import json
import sys
import os

WORKSPACE_DIR = r"D:\Virtu模型"
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

from virtu_omni.engine.wish_cad_cam_engine import WishCADCAMEngine
from scripts.workbuddy_virtu_bridge import OpenAIBaseHandler


def test_progressive_disclosure_in_engine():
    engine = WishCADCAMEngine()
    resp = engine.synthesize_all_six("做一款外径53mm、轴孔14mm、宽度45mm、三道圆弧槽R15/R12/R10的微型机冷成型轮模")
    
    assert "Dynamic Parametric Sliders" in resp, "Slider UI missing"
    assert "<details open>" in resp, "SolidWorks collapsible section missing"
    assert "<details>" in resp, "Secondary collapsible sections missing"
    assert "```vb" in resp
    assert "```python" in resp
    assert "```lisp" in resp
    assert "```plaintext" in resp
    assert "```gcode" in resp
    print("[PASS] Engine progressive disclosure & slider test")


def test_slider_dashboard_physics():
    engine = WishCADCAMEngine()
    spec = {
        "material": "AL6061-T6",
        "d_outer": 80.0,
        "d_inner": 30.0,
        "overall_len": 60.0,
        "fillet_r": 5.0,
    }
    dashboard = engine.generate_slider_dashboard(spec)
    assert "80.0 mm" in dashboard
    assert "30.0 mm" in dashboard
    assert "安全结构壁厚" in dashboard
    assert "净重预估" in dashboard
    print("[PASS] Slider dashboard physics calculation test")


def test_tool_orchestration_variation_slider():
    handler = OpenAIBaseHandler.__new__(OpenAIBaseHandler)
    msgs = [{"role": "user", "content": "把轴承支座的外径调到60，孔径改成16"}]
    tools = [{"type": "function", "function": {"name": "cad.update_parametric_variation"}}]
    
    # 1. First turn: user variation intent -> assistant tool call
    t_resp = handler._handle_tool_orchestration(msgs, tools=tools)
    assert t_resp["choices"][0]["finish_reason"] == "tool_calls"
    call = t_resp["choices"][0]["message"]["tool_calls"][0]
    assert call["function"]["name"] == "cad.update_parametric_variation"
    
    args = json.loads(call["function"]["arguments"])
    assert args["parametric_variations"]["d_outer"] == 60.0
    assert args["parametric_variations"]["d_inner"] == 16.0
    
    # 2. Second turn: tool execution result -> assistant rebuild summary
    msgs_cont = msgs + [
        t_resp["choices"][0]["message"],
        {"role": "tool", "tool_call_id": call["id"], "name": call["function"]["name"], "content": json.dumps({"status": "rebuilt"})}
    ]
    final_resp = handler._handle_tool_orchestration(msgs_cont, tools=[])
    assert final_resp["choices"][0]["finish_reason"] == "stop"
    content = final_resp["choices"][0]["message"]["content"]
    assert "Dynamic Parametric Sliders" in content
    assert "参数变异前后对比与工程级联响应" in content
    assert "EquationMgr" in content
    print("[PASS] Tool orchestration variation slider test")


if __name__ == "__main__":
    test_progressive_disclosure_in_engine()
    test_slider_dashboard_physics()
    test_tool_orchestration_variation_slider()
    print("[ALL PASS] All progressive disclosure and slider tests succeeded!")
