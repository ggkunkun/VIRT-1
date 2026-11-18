"""Unit and integration tests for the Deep Thinking (Reasoning / CoT) pipeline.

Validates:
1. Extracting <think>...</think> and legacy delimiters from raw generation tokens;
2. Preserving thinking content while keeping the final content output clean;
3. Adaptive thinking decision logic (_should_enable_thinking) across auto/always/off modes;
4. RealBackend recording and exposing last_thought across Ollama, Transformers, and Cloud;
5. Bridge HTTP responses including reasoning_content in standard OpenAI JSON completion format;
6. Bridge SSE streaming properly chunking and streaming choices[0].delta.reasoning_content before delta.content.
"""
import io
import json
import unittest
from unittest.mock import patch, MagicMock

from scripts.ollama_toolcall_client import extract_thinking, _clean
from virtu_real_backend import VirtuRealModel
import scripts.workbuddy_virtu_bridge as bridge


class DeepThinkingExtractionTests(unittest.TestCase):
    def test_extract_thinking_with_standard_tags(self):
        raw = "<think>我们需要先推导齿轮分度圆公式 d = m * z，已知模数 m=4，齿数 z=25。</think>分度圆直径 d = 100 mm。"
        clean_text, thought = extract_thinking(raw)
        self.assertEqual(clean_text, "分度圆直径 d = 100 mm。")
        self.assertIn("我们需要先推导齿轮分度圆公式", thought)
        self.assertIn("d = m * z", thought)

    def test_extract_thinking_multiple_blocks(self):
        raw = "<think>步骤一：分析切削速度公式</think>公式推导完成。<think>步骤二：代入 D=16, Vc=120 计算主轴转速</think>转速 n = 2387.3 r/min。"
        clean_text, thought = extract_thinking(raw)
        self.assertEqual(clean_text, "公式推导完成。转速 n = 2387.3 r/min。")
        self.assertIn("步骤一", thought)
        self.assertIn("步骤二", thought)

    def test_extract_thinking_empty_when_no_tags(self):
        raw = "普通问答，无需深度思考。"
        clean_text, thought = extract_thinking(raw)
        self.assertEqual(clean_text, "普通问答，无需深度思考。")
        self.assertEqual(thought, "")


class DeepThinkingRoutingTests(unittest.TestCase):
    def setUp(self):
        with patch.object(VirtuRealModel, "_load"), patch.object(VirtuRealModel, "_load_vision_config"):
            self.backend = VirtuRealModel()

    def test_explicit_think_parameter_takes_precedence(self):
        messages = [{"role": "user", "content": "hello"}]
        self.assertTrue(self.backend._should_enable_thinking(messages, explicit_think=True))
        self.assertFalse(self.backend._should_enable_thinking(messages, explicit_think=False))

    def test_env_override_always_and_off(self):
        messages = [{"role": "user", "content": "任意测试问答"}]
        with patch.dict("os.environ", {"VIRTU_THINKING_MODE": "always"}):
            self.assertTrue(self.backend._should_enable_thinking(messages))
        with patch.dict("os.environ", {"VIRTU_THINKING_MODE": "off"}):
            self.assertFalse(self.backend._should_enable_thinking(messages))

    def test_auto_mode_triggers_on_calculation_and_cues(self):
        with patch.dict("os.environ", {"VIRTU_THINKING_MODE": "auto"}):
            # 1. 显式工程计算问题
            math_msgs = [{"role": "user", "content": "Vc=80 m/min，D=50 mm，按 n=1000*Vc/(π*D) 求 n。"}]
            self.assertTrue(self.backend._should_enable_thinking(math_msgs))

            # 2. 带有思考/推导诱导词
            think_msgs = [{"role": "user", "content": "请详细分析法兰盘螺栓孔均布的弦长计算公式并给出推导过程"}]
            self.assertTrue(self.backend._should_enable_thinking(think_msgs))

            # 3. 普通对话不触发思考
            plain_msgs = [{"role": "user", "content": "你好，请问今天天气怎么样"}]
            self.assertFalse(self.backend._should_enable_thinking(plain_msgs))

            # 4. 纯工具调用默认快速返回
            tool_msgs = [{"role": "user", "content": "启动 CIMCO 仿真 runs/macro.nc"}]
            self.assertFalse(self.backend._should_enable_thinking(tool_msgs, tools=[{"type": "function"}]))

            # 5. 任务拆解与深度规划诱导词触发思考（拒绝无限穷举盲试）
            decomp_msgs = [{"role": "user", "content": "请将该零件的加工工序拆解为详细子任务并规划工艺路径"}]
            self.assertTrue(self.backend._should_enable_thinking(decomp_msgs))

            # 6. 历史对话中工具报错 (Repair Turn) 强制触发深度思考
            repair_history = [
                {"role": "user", "content": "建立法兰盘模型"},
                {"role": "assistant", "content": "", "tool_calls": [{"name": "cadcam_solidworks_model"}]},
                {"role": "tool", "content": '{"status": "rejected", "violations": ["d_bore >= d_hub: 几何冲突"]}'},
                {"role": "user", "content": "请修正参数并重新建模"}
            ]
            self.assertTrue(self.backend._should_enable_thinking(repair_history, tools=[{"type": "function"}]))

            # 7. 复杂几何建模工具调用触发深度思考
            complex_cad_msgs = [{"role": "user", "content": "调用工具建模一个法兰盘，自选合理工程参数并标注工程图"}]
            self.assertTrue(self.backend._should_enable_thinking(complex_cad_msgs, tools=[{"type": "function"}]))

    def test_repair_contract_contains_anti_brute_force_clauses(self):
        from scripts.cad_tools_iface import REPAIR_CONTRACT
        self.assertIn("严禁盲目猜数", REPAIR_CONTRACT)
        self.assertIn("任务拆解与熔断", REPAIR_CONTRACT)
        self.assertIn("坚决不进行无限穷举", REPAIR_CONTRACT)


class BridgeDeepThinkingProtocolTests(unittest.TestCase):
    def setUp(self):
        self.backend = MagicMock()
        self.backend.available = True
        self.backend.identity.return_value = {"backend": "test", "text_model": "qwen3:8b", "tool_model": None}
        self.backend.last_thought = "这是来自模型的真实思维推导过程：计算分度圆直径 d = 4 * 25 = 100mm。"
        self.backend.generate.return_value = "最终结论：分度圆直径为 100mm。"

    def test_json_response_includes_reasoning_content(self):
        handler = bridge.OpenAIBaseHandler.__new__(bridge.OpenAIBaseHandler)
        handler.headers = {}
        handler._served_model = {"backend": "test"}
        out_buf = io.BytesIO()
        handler.wfile = out_buf
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()
        handler._send_cors_headers = MagicMock()

        handler._handle_json_response("最终结论：分度圆直径为 100mm。", reasoning_text="思考推导过程：d = 4 * 25 = 100")
        output = json.loads(out_buf.getvalue().decode("utf-8"))
        msg = output["choices"][0]["message"]
        self.assertEqual(msg["content"], "最终结论：分度圆直径为 100mm。")
        self.assertEqual(msg["reasoning_content"], "思考推导过程：d = 4 * 25 = 100")

    def test_streaming_response_streams_reasoning_then_content(self):
        handler = bridge.OpenAIBaseHandler.__new__(bridge.OpenAIBaseHandler)
        handler.headers = {}
        handler._served_model = {"backend": "test"}
        out_buf = io.BytesIO()
        handler.wfile = out_buf
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()
        handler._send_cors_headers = MagicMock()

        thought = "深度推导：1+1=2"
        content = "答案是2"
        # 思维链默认不外泄；显式展示需要 opt-in（与生产路径的默认行为一致）。
        handler._handle_streaming_response(content, reasoning_text=thought,
                                           expose_reasoning=True)
        
        raw_events = out_buf.getvalue().decode("utf-8").split("\n\n")
        reasoning_chunks = []
        content_chunks = []
        for ev in raw_events:
            ev = ev.strip()
            if not ev.startswith("data: ") or ev == "data: [DONE]":
                continue
            payload = json.loads(ev[6:])
            delta = payload["choices"][0]["delta"]
            if "reasoning_content" in delta:
                reasoning_chunks.append(delta["reasoning_content"])
            if "content" in delta:
                content_chunks.append(delta["content"])

        self.assertEqual("".join(reasoning_chunks), thought)
        self.assertEqual("".join(content_chunks), content)


if __name__ == "__main__":
    unittest.main()
