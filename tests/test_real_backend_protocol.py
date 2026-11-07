import threading
import unittest
from unittest.mock import patch

from virtu_real_backend import VirtuRealModel, _verify_arithmetic_response, resolve_ollama_model


class RealBackendProtocolTests(unittest.TestCase):
    def test_arithmetic_guard_corrects_single_clear_equation(self):
        self.assertEqual(
            _verify_arithmetic_response("n=1000*120/(π*16)=238.7 r/min"),
            "n=1000*120/(π*16)=2387.3 r/min")
        self.assertEqual(
            _verify_arithmetic_response("n=1000*80/(π*50)≈509.3 r/min"),
            "n=1000*80/(π*50)≈509.3 r/min")

    def test_arithmetic_guard_leaves_ambiguous_answers_untouched(self):
        text = "n=1000*120/(π*16)=238.7；Vf=0.15*3*900=405.0"
        self.assertEqual(_verify_arithmetic_response(text), text)

    def setUp(self):
        with patch.object(VirtuRealModel, "_load"), patch.object(VirtuRealModel, "_load_vision_config"):
            self.backend = VirtuRealModel()
        self.backend.max_tokens = 256
        self.backend.temperature = 0.7

    def test_request_overrides_are_temporary_and_restored(self):
        with patch.object(self.backend, "_generate", return_value="ok") as generate:
            self.assertEqual(self.backend.generate([], max_tokens=55, temperature=0.2), "ok")
        self.assertEqual(self.backend.max_tokens, 256)
        self.assertEqual(self.backend.temperature, 0.7)
        generate.assert_called_once_with([], tools=None)

    def test_invalid_override_does_not_mutate_backend_state(self):
        for kwargs in ({"max_tokens": True}, {"max_tokens": 0},
                       {"temperature": True}, {"temperature": 2.1}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.backend.generate([], **kwargs)
            self.assertEqual(self.backend.max_tokens, 256)
            self.assertEqual(self.backend.temperature, 0.7)

    def test_generation_exception_restores_overrides(self):
        with patch.object(self.backend, "_generate", side_effect=RuntimeError("expected")):
            with self.assertRaisesRegex(RuntimeError, "expected"):
                self.backend.generate([], max_tokens=42, temperature=0.1)
        self.assertEqual(self.backend.max_tokens, 256)
        self.assertEqual(self.backend.temperature, 0.7)

    def test_concurrent_requests_do_not_mix_temporary_overrides(self):
        entered = threading.Event()
        release = threading.Event()
        observed = []

        def fake_generate(_messages, tools=None):
            observed.append((self.backend.max_tokens, self.backend.temperature))
            if len(observed) == 1:
                entered.set()
                release.wait(timeout=2)
            return "ok"

        with patch.object(self.backend, "_generate", side_effect=fake_generate):
            first = threading.Thread(target=lambda: self.backend.generate([], max_tokens=10, temperature=0.1))
            second = threading.Thread(target=lambda: self.backend.generate([], max_tokens=20, temperature=0.2))
            first.start()
            self.assertTrue(entered.wait(timeout=1))
            second.start()
            release.set()
            first.join(timeout=2)
            second.join(timeout=2)
        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertEqual(observed, [(10, 0.1), (20, 0.2)])

    def test_generation_lock_times_out_instead_of_hanging_forever(self):
        release = threading.Event()
        acquired = threading.Event()

        def hold_lock():
            self.backend._generation_lock.acquire()
            acquired.set()
            release.wait(timeout=2)
            self.backend._generation_lock.release()

        holder = threading.Thread(target=hold_lock)
        holder.start()
        self.assertTrue(acquired.wait(timeout=1))
        try:
            with patch.dict("os.environ", {"VIRTU_GENERATION_LOCK_TIMEOUT": "0.05"}):
                with self.assertRaisesRegex(RuntimeError, "backend busy"):
                    self.backend.generate([])
        finally:
            release.set()
            holder.join(timeout=2)
        self.assertFalse(holder.is_alive())

    def test_vision_candidate_receives_request_budget(self):
        self.backend._vision_candidates = [("https://example.invalid/v1", "fake", "vision")]
        self.backend._local_vision_present = lambda: False
        self.backend.vision_mode = "cloud"
        with patch.object(self.backend, "_chat_with_candidates", return_value="ok") as chat:
            self.assertEqual(self.backend._gen_vision([{"role": "user", "content": []}]), "ok")
        self.assertEqual(chat.call_args.kwargs["max_tokens"], 256)

    def test_ollama_tools_respect_request_temperature_and_token_budget(self):
        self.backend.ollama_model = "test-model"
        with patch("scripts.ollama_toolcall_client.chat",
                   return_value={"content": "", "tool_calls": []}) as chat:
            self.backend.max_tokens = 73
            self.backend.temperature = 0.65
            self.backend._gen_ollama([], cad=False, tools=[{"type": "function"}])
        self.assertEqual(chat.call_args.kwargs["temperature"], 0.65)
        self.assertEqual(chat.call_args.kwargs["num_predict"], 73)

    def test_llamacpp_tool_history_uses_native_chat_completion(self):
        self.backend._model = type("FakeLlama", (), {})()
        create = unittest.mock.Mock(return_value={"choices": [{"message": {
            "content": "summary", "tool_calls": None}}]})
        self.backend._model.create_chat_completion = create
        messages = [
            {"role": "assistant", "content": "", "tool_calls": [{"id": "c1"}]},
            {"role": "tool", "tool_call_id": "c1", "content": "done"},
        ]
        self.backend.max_tokens = 99
        self.backend.temperature = 0.3
        result = self.backend._gen_llamacpp(messages, cad=False, tools=None)
        self.assertEqual(result, "summary")
        self.assertEqual(create.call_args.kwargs["messages"], messages)
        self.assertNotIn("tools", create.call_args.kwargs)
        self.assertEqual(create.call_args.kwargs["max_tokens"], 99)

    def test_ollama_vllm_path_reuses_cleaning_and_toolcall_client(self):
        self.backend.vllm_url = "http://127.0.0.1:11434/v1"
        messages = [{"role": "system", "content": "caller persona"},
                    {"role": "user", "content": "calculate rpm"}]
        with patch.dict("os.environ", {"VIRTU_VLLM_MODEL": "qwen3:8b"}), \
                patch("scripts.ollama_toolcall_client.chat",
                      return_value={"content": "509.3", "tool_calls": None}) as chat:
            result = self.backend._gen_vllm(messages, cad=False)
        self.assertEqual(result, "509.3")
        self.assertEqual(chat.call_args.kwargs["model"], "qwen3:8b")
        self.assertFalse(chat.call_args.kwargs["think"])
        self.assertEqual(chat.call_args.kwargs["messages"], messages)

    def test_calculation_query_drops_system_prompt_to_preserve_arithmetic(self):
        self.backend.vllm_url = "http://127.0.0.1:11434/v1"
        messages = [
            {"role": "system", "content": "friendly persona"},
            {"role": "user", "content": "Vc=80 m/min，D=50 mm，按 n=1000*Vc/(π*D) 求 n。"},
        ]
        with patch.dict("os.environ", {"VIRTU_VLLM_MODEL": "qwen3:8b"}), \
                patch("scripts.ollama_toolcall_client.chat",
                      return_value={"content": "509.3", "tool_calls": None}) as chat:
            self.assertEqual(self.backend._gen_vllm(messages, cad=True), "509.3")
        sent = chat.call_args.kwargs["messages"]
        self.assertTrue(all(message["role"] != "system" for message in sent))
        self.assertEqual(sent[-1]["content"], messages[-1]["content"])

    def test_gcode_mapping_table_keeps_system_prompt(self):
        self.backend.vllm_url = "http://127.0.0.1:11434/v1"
        messages = [
            {"role": "system", "content": "follow the mapping table"},
            {"role": "user", "content": "G00→G1；G01→G0；G17→G93；迁移 G90 G17 G00 X50.0 Y20.0"},
        ]
        with patch.dict("os.environ", {"VIRTU_VLLM_MODEL": "qwen3:8b"}), \
                patch("scripts.ollama_toolcall_client.chat",
                      return_value={"content": "G93 G1 X50.0 Y20.0", "tool_calls": None}) as chat:
            self.backend._gen_vllm(messages, cad=True)
        self.assertEqual(chat.call_args.kwargs["messages"][0]["role"], "system")

    def test_post_tool_summary_uses_general_text_model(self):
        self.backend.vllm_url = "http://127.0.0.1:11434/v1"
        messages = [
            {"role": "user", "content": "create a flange"},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "c1"}]},
            {"role": "tool", "tool_call_id": "c1", "content": "{\"ok\": true}"},
        ]
        with patch.dict("os.environ", {"VIRTU_VLLM_MODEL": "qwen3:8b",
                                       "VIRTU_TOOL_MODEL": "virtu-toolcall"}), \
                patch("scripts.ollama_toolcall_client.chat",
                      return_value={"content": "tool completed", "tool_calls": None}) as chat:
            self.assertEqual(self.backend._gen_vllm(messages, cad=True), "tool completed")
        self.assertEqual(chat.call_args.kwargs["model"], "qwen3:8b")

    def test_ollama_vllm_tool_turn_uses_specialist_model(self):
        self.backend.vllm_url = "http://127.0.0.1:11434/v1"
        messages = [{"role": "user", "content": "create a flange"}]
        calls = [{"id": "c1", "type": "function",
                  "function": {"name": "cad.parse_wish_intent", "arguments": "{}"}}]
        with patch.dict("os.environ", {"VIRTU_VLLM_MODEL": "qwen3:8b",
                                       "VIRTU_TOOL_MODEL": "virtu-toolcall"}), \
                patch("scripts.ollama_toolcall_client.chat",
                      return_value={"content": "", "tool_calls": calls}) as chat:
            result = self.backend._gen_vllm(messages, cad=True,
                                            tools=[{"type": "function"}])
        self.assertEqual(result, ("", calls))
        self.assertEqual(chat.call_args.kwargs["model"], "virtu-toolcall")
        self.assertIn("工具调用", chat.call_args.kwargs["messages"][0]["content"])

    def test_generate_stream_restores_parameters_and_yields_deltas(self):
        mock_chunks = [
            {"type": "thinking", "delta": "think1"},
            {"type": "content", "delta": "part1"},
            {"type": "content", "delta": "part2"},
        ]
        with patch.object(self.backend, "_generate_stream", return_value=iter(mock_chunks)) as gen_stream:
            chunks = list(self.backend.generate_stream([], max_tokens=88, temperature=0.35))
        self.assertEqual(len(chunks), 3)
        self.assertEqual(chunks[1]["delta"], "part1")
        self.assertEqual(self.backend.max_tokens, 256)
        self.assertEqual(self.backend.temperature, 0.7)
        gen_stream.assert_called_once_with([], tools=None, think=None)

    def test_generate_stream_ollama_path_integrates_chat_stream(self):
        self.backend.vllm_url = "http://127.0.0.1:11434/v1"
        self.backend.max_tokens = 50
        self.backend.temperature = 0.5
        mock_stream = [
            {"type": "thinking", "delta": "reasoning"},
            {"type": "content", "delta": "hello"},
            {"type": "done", "prompt_eval_count": 12, "eval_count": 8},
        ]
        with patch.dict("os.environ", {"VIRTU_VLLM_MODEL": "qwen3:8b"}), \
                patch("scripts.ollama_toolcall_client.chat_stream", return_value=iter(mock_stream)) as stream_fn:
            yielded = list(self.backend._gen_ollama_stream([{"role": "user", "content": "hi"}], cad=False))
        self.assertEqual(len(yielded), 2)
        self.assertEqual(yielded[0]["type"], "thinking")
        self.assertEqual(yielded[1]["type"], "content")
        self.assertEqual(self.backend.last_thought, "reasoning")
        self.assertEqual(self.backend.last_usage, {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20})
        self.assertEqual(stream_fn.call_args.kwargs["model"], "qwen3:8b")
        self.assertEqual(stream_fn.call_args.kwargs["temperature"], 0.5)


class OllamaIdentityTests(unittest.TestCase):
    """The tag is part of the artifact identity: never truncate it to ``:latest``."""

    def test_discovered_tag_is_preserved(self):
        self.assertEqual(
            resolve_ollama_model(["qwen3:8b", "virtu-master:v4"]), "virtu-master:v4")

    def test_env_model_keeps_its_own_tag(self):
        self.assertEqual(
            resolve_ollama_model(["virtu-ties-v1:latest", "virtu-ties-v1:v2"], "virtu-ties-v1:v2"),
            "virtu-ties-v1:v2")

    def test_untagged_env_resolves_to_a_real_tag(self):
        self.assertEqual(
            resolve_ollama_model(["virtu-master:v4"], "virtu-master"), "virtu-master:v4")

    def test_empty_ollama_store_is_not_a_model(self):
        self.assertIsNone(resolve_ollama_model([]))


if __name__ == "__main__":
    unittest.main()
