"""Deterministic proof that a truncated tool call retries once instead of hard-failing.

The live case (measured 2026-11-01): max_tokens=220 produced
"Ollama API HTTP 500: llama-server returned invalid tool call arguments for
cadcam_vericut_simulate: unexpected end of JSON input", which the bridge forwarded as a
500 even though the model had chosen the correct tool. A unit fixture reproduces the
error exactly, so the retry is verified without depending on sampler luck.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TRUNCATED = ('Ollama API HTTP 500: {"error":"llama-server returned invalid tool call '
             'arguments for \\"cadcam_vericut_simulate\\": unexpected end of JSON input"}')


class _Recorder:
    """Fake ollama_toolcall_client.chat: fails once on a narrow budget, then succeeds."""

    def __init__(self, fail_times, message=TRUNCATED):
        self.calls = []
        self.fail_times = fail_times
        self.message = message

    def __call__(self, **kwargs):
        self.calls.append(kwargs.get("num_predict"))
        if len(self.calls) <= self.fail_times:
            raise RuntimeError(self.message)
        return {"content": "", "tool_calls": [{
            "id": "call_1", "type": "function",
            "function": {"name": "cadcam_vericut_simulate",
                         "arguments": {"part": "flange", "diff_mode": "auto"}}}],
            "eval_count": 75, "prompt_eval_count": 2333}


class ToolCallRetryTests(unittest.TestCase):
    def _backend(self):
        import virtu_real_backend as V
        shell = object.__new__(V.VirtuRealModel)
        shell.max_tokens = 220
        shell.temperature = 0.0
        shell.last_usage = None
        return V, shell

    def test_truncated_tool_json_retries_with_more_room(self):
        V, b = self._backend()
        fake = _Recorder(fail_times=1)
        out = b._chat_with_room(fake, model="m", messages=[], tools=[],
                                num_ctx=4096, num_predict=220, think=False)
        self.assertEqual(fake.calls, [220, 768], "should retry once with the widened budget")
        self.assertEqual(out["tool_calls"][0]["function"]["name"], "cadcam_vericut_simulate")

    def test_other_upstream_errors_are_not_retried(self):
        """Negative control: an unrelated 500 must surface immediately, not loop."""
        V, b = self._backend()
        fake = _Recorder(fail_times=5, message="Ollama API HTTP 500: model not found")
        with self.assertRaises(RuntimeError) as ctx:
            b._chat_with_room(fake, model="m", messages=[], tools=[],
                              num_ctx=4096, num_predict=220, think=False)
        self.assertIn("model not found", str(ctx.exception))
        self.assertEqual(fake.calls, [220], "non-truncation errors must not be retried")

    def test_retry_that_still_fails_propagates(self):
        V, b = self._backend()
        fake = _Recorder(fail_times=9)
        with self.assertRaises(RuntimeError):
            b._chat_with_room(fake, model="m", messages=[], tools=[],
                              num_ctx=4096, num_predict=220, think=False)
        self.assertEqual(fake.calls, [220, 768], "exactly one retry, never a retry storm")

    def test_budget_floor_covers_a_normal_max_tokens(self):
        V, b = self._backend()
        b.max_tokens = 1024
        fake = _Recorder(fail_times=1)
        b._chat_with_room(fake, model="m", messages=[], tools=[],
                          num_ctx=4096, num_predict=1024, think=False)
        self.assertEqual(fake.calls, [1024, 3072])

    def test_production_call_sites_route_through_the_retry(self):
        from pathlib import Path
        src = (Path(__file__).resolve().parents[1] / "virtu_real_backend.py"
               ).read_text(encoding="utf-8")
        self.assertEqual(src.count("self._chat_with_room("), 2,
                         "_gen_ollama 与 _gen_vllm 两处 Ollama 调用都应走重试包装")


if __name__ == "__main__":
    unittest.main()
