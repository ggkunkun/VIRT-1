"""Token accounting must reach the response layer.

virtu_eval scores truncation off `usage`; before this the bridge omitted the field
entirely, so every record stored prompt_tokens/completion_tokens = null.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class BackendUsageTests(unittest.TestCase):
    def _backend(self):
        import virtu_real_backend as V
        shell = object.__new__(V.VirtuRealModel)
        shell.last_usage = None
        return V, shell

    def test_records_only_reported_counts(self):
        V, b = self._backend()
        b._record_usage(120, 34)
        self.assertEqual(b.last_usage, {"prompt_tokens": 120, "completion_tokens": 34,
                                         "total_tokens": 154})

    def test_missing_pair_is_not_invented(self):
        V, b = self._backend()
        b._record_usage(120, 34)
        b._record_usage(None, None)
        self.assertIsNone(b.last_usage)

    def test_one_sided_report_keeps_null_gap(self):
        V, b = self._backend()
        b._record_usage(None, 34)
        self.assertIsNone(b.last_usage["total_tokens"])
        self.assertEqual(b.last_usage["completion_tokens"], 34)


class BridgeUsageTests(unittest.TestCase):
    def test_build_usage_reads_backend(self):
        import scripts.workbuddy_virtu_bridge as bridge
        import virtu_real_backend as V
        real_get = V.get_backend
        try:
            V.get_backend = lambda: type("Fake", (), {"last_usage": {
                "prompt_tokens": 88, "completion_tokens": 12, "total_tokens": 100}})()
            self.assertEqual(bridge._build_usage(),
                             {"prompt_tokens": 88, "completion_tokens": 12,
                              "total_tokens": 100})
        finally:
            V.get_backend = real_get

    def test_build_usage_omits_when_backend_says_nothing(self):
        import scripts.workbuddy_virtu_bridge as bridge
        import virtu_real_backend as V
        real_get = V.get_backend
        try:
            V.get_backend = lambda: type("Fake", (), {"last_usage": None})()
            self.assertIsNone(bridge._build_usage())
        finally:
            V.get_backend = real_get

    def test_all_backend_produced_completions_carry_usage_field(self):
        """The deterministic UI shortcuts must stay out of this count: publishing a
        previous request's tokens against a response that ran no model is exactly the
        kind of unverified claim this repo has been burned by.

        After the omission fix every completion body routes through ``_attach_usage``,
        which keeps the field when the backend reported counts and drops it when
        nothing was measured (see ``test_attach_usage_omits_when_nothing_measured``).
        """
        from pathlib import Path
        src = (Path(__file__).resolve().parents[1] / "scripts"
               / "workbuddy_virtu_bridge.py").read_text(encoding="utf-8")
        self.assertGreaterEqual(src.count("_attach_usage({"), 4)
        self.assertIn('"usage": tool_resp.get("usage"),', src)

    def test_attach_usage_omits_when_nothing_measured(self):
        import scripts.workbuddy_virtu_bridge as bridge
        import virtu_real_backend as V
        real_get = V.get_backend
        try:
            V.get_backend = lambda: type("Fake", (), {"last_usage": None})()
            resp = bridge._attach_usage({"id": "x", "usage": {"prompt_tokens": 1}})
            self.assertNotIn("usage", resp)
        finally:
            V.get_backend = real_get

    def test_attach_usage_publishes_measured_counts(self):
        import scripts.workbuddy_virtu_bridge as bridge
        import virtu_real_backend as V
        real_get = V.get_backend
        try:
            V.get_backend = lambda: type("Fake", (), {"last_usage": {
                "prompt_tokens": 88, "completion_tokens": 12, "total_tokens": 100}})()
            resp = bridge._attach_usage({"id": "x"})
            self.assertEqual(resp["usage"],
                             {"prompt_tokens": 88, "completion_tokens": 12,
                              "total_tokens": 100})
        finally:
            V.get_backend = real_get


if __name__ == "__main__":
    unittest.main()
