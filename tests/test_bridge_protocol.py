import http.client
import json
import threading
import unittest
from unittest.mock import patch

from scripts import workbuddy_virtu_bridge as bridge


class _Backend:
    available = True
    error = ""

    def __init__(self):
        self.calls = []

    def identity(self):
        return {"backend": "fake", "text_model": "fake", "tool_model": None}

    def generate(self, messages, tools=None, max_tokens=None, temperature=None):
        self.calls.append((messages, tools, max_tokens, temperature))
        if tools is not None:
            return "answer", None
        return "answer"

    def generate_stream(self, messages, tools=None, max_tokens=None, temperature=None, think=None):
        self.calls.append((messages, tools, max_tokens, temperature))
        yield {"type": "thinking", "delta": "think_step"}
        yield {"type": "content", "delta": "part_1"}
        yield {"type": "content", "delta": "part_2"}


class BridgeProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        bridge._BRIDGE_TOKEN = "test-token-" + "x" * 48
        cls.server = bridge.ThreadingServer(("127.0.0.1", 0), bridge.OpenAIBaseHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def request(self, path, payload, token=True):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {bridge._BRIDGE_TOKEN}"
        raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
        conn.request("POST", path, body=raw, headers=headers)
        response = conn.getresponse()
        status, body = response.status, response.read()
        conn.close()
        return status, json.loads(body.decode("utf-8"))

    def test_run_server_refuses_when_instance_guard_is_held(self):
        with patch.object(bridge, "SingleFlight") as guard_cls, \
                patch.object(bridge, "ThreadingServer") as server_cls:
            guard_cls.return_value.acquire.return_value = False
            bridge.run_server()
        server_cls.assert_not_called()

    def test_invalid_json_and_generation_parameters_are_400(self):
        status, _ = self.request("/v1/chat/completions", b"{")
        self.assertEqual(status, 400)
        for field, value in (("max_tokens", 0), ("max_tokens", True),
                             ("temperature", 2.1), ("stream", "false")):
            with self.subTest(field=field, value=value):
                status, _ = self.request("/v1/chat/completions", {
                    "model": bridge.MODEL_ID,
                    "messages": [{"role": "user", "content": "hi"}],
                    field: value,
                })
                self.assertEqual(status, 400)

    def test_chat_passes_request_parameters_and_does_not_fabricate_usage(self):
        backend = _Backend()
        with patch("virtu_real_backend.get_backend", return_value=backend):
            status, payload = self.request("/v1/chat/completions", {
                "model": bridge.MODEL_ID,
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 77,
                "temperature": 0.25,
            })
        self.assertEqual(status, 200)
        self.assertEqual(backend.calls[0][2:], (77, 0.25))
        self.assertNotIn("usage", payload)

    def test_tool_turn_passes_generation_parameters(self):
        backend = _Backend()
        with patch("virtu_real_backend.get_backend", return_value=backend):
            status, payload = self.request("/v1/chat/completions", {
                "model": bridge.MODEL_ID,
                "messages": [{"role": "user", "content": "use tool"}],
                "tools": [{"type": "function", "function": {"name": "lookup"}}],
                "max_completion_tokens": 31,
                "temperature": 0,
            })
        self.assertEqual(status, 200)
        self.assertEqual(backend.calls[0][2:], (31, 0))
        self.assertNotIn("usage", payload)

    def test_assistant_tool_call_history_is_treated_as_tool_continuation(self):
        backend = _Backend()
        with patch("virtu_real_backend.get_backend", return_value=backend):
            status, payload = self.request("/v1/chat/completions", {
                "model": bridge.MODEL_ID,
                "messages": [
                    {"role": "user", "content": "use tool"},
                    {"role": "assistant", "content": "", "tool_calls": [{
                        "id": "call_1", "type": "function",
                        "function": {"name": "cadcam_preflight", "arguments": "{}"},
                    }]},
                ],
                "max_tokens": 22,
            })
        self.assertEqual(status, 200)
        self.assertEqual(backend.calls[0][2], 22)
        self.assertEqual(payload["choices"][0]["message"]["content"], "answer")

    def test_unknown_post_route_is_404_and_requires_auth(self):
        status, _ = self.request("/does-not-exist", {})
        self.assertEqual(status, 404)
        status, _ = self.request("/v1/chat/completions", {}, token=False)
        self.assertEqual(status, 401)

    def test_chat_streaming_live_sse(self):
        backend = _Backend()
        with patch("virtu_real_backend.get_backend", return_value=backend):
            conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {bridge._BRIDGE_TOKEN}",
            }
            body = json.dumps({
                "model": bridge.MODEL_ID,
                "messages": [{"role": "user", "content": "hi"}],
                "stream": True,
                "max_tokens": 60,
                "temperature": 0.3,
            }).encode("utf-8")
            conn.request("POST", "/v1/chat/completions", body=body, headers=headers)
            response = conn.getresponse()
            self.assertEqual(response.status, 200)
            self.assertIn("text/event-stream", response.getheader("Content-Type"))
            lines = []
            while True:
                line = response.readline().decode("utf-8").strip()
                if not line:
                    continue
                lines.append(line)
                if line == "data: [DONE]":
                    break
            conn.close()

            # Verify SSE protocol lines
            data_lines = [line[6:] for line in lines if line.startswith("data: ") and line != "data: [DONE]"]
            chunks = [json.loads(d) for d in data_lines]
            self.assertTrue(any("reasoning_content" in c["choices"][0]["delta"] for c in chunks))
            # Visible content is buffered, gated, then re-chunked at 40 chars on
            # purpose: a deceptive answer must not reach the client before the
            # gate runs, so the backend's original per-delta boundaries are gone.
            streamed = "".join(c["choices"][0]["delta"].get("content", "") for c in chunks)
            self.assertEqual(streamed, "part_1part_2")
            self.assertTrue(any(c["choices"][0]["delta"].get("content") for c in chunks))
            self.assertTrue(any(c["choices"][0]["finish_reason"] == "stop" for c in chunks))
            self.assertIn("data: [DONE]", lines)

    def test_unknown_model_is_rejected(self):
        status, payload = self.request("/v1/chat/completions", {
            "model": "definitely-not-a-real-model",
            "messages": [{"role": "user", "content": "hi"}],
        })
        self.assertEqual(status, 404)
        self.assertIn("Unknown model", payload["error"]["message"])


if __name__ == "__main__":
    unittest.main()
