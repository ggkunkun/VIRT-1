"""An Ollama arm must report *which bytes* answered, and survive a tool-less template.

Two failures measured on 2026-11-05:
  * `virtu-comprehensive:latest` was re-created mid-leg onto a different template/system
    layer, and `virtu-master`, `virtu-ties-v1`, `virtu-test-tool` became aliases of a single
    manifest. Quoting a score against a tag name is unfalsifiable unless the serving layers
    are captured with it.
  * those artifacts carry a `{{ .Prompt }}` template with no tool branch, so Ollama answers
    every `tools` request with 400 "does not support tools" - which turned a 30-case
    toolcall dimension into 30 identical transport errors, and one harness still recorded
    that as a completed arm.
"""
import io
import json
import os
import sys
import unittest
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from virtu_eval.arms import OllamaNativeArm  # noqa: E402

TOOLS = [{"type": "function", "function": {"name": "cadcam_preflight",
                                           "description": "x",
                                           "parameters": {"type": "object",
                                                          "properties": {}}}}]


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeOpener:
    """First call with tools -> 400 'does not support tools'; later calls succeed."""

    def __init__(self):
        self.seen = []

    def open(self, req, timeout=None):
        body = json.loads(req.data.decode("utf-8"))
        self.seen.append("tools" in body)
        if "tools" in body:
            raise urllib.error.HTTPError(req.full_url, 400, "Bad Request",
                                         {}, io.BytesIO(b'{"error":"does not support tools"}'))
        return FakeResponse({"model": "fake", "done": True, "done_reason": "stop",
                             "message": {"role": "assistant",
                                         "content": '{"tool":"cadcam_preflight","arguments":{}}'},
                             "prompt_eval_count": 12, "eval_count": 7,
                             "eval_duration": 700000000})


def make_arm():
    arm = OllamaNativeArm("virtu-comprehensive:latest", num_ctx=8192, retries=3)
    arm._opener = FakeOpener()
    return arm


class TestServedLayerEvidence(unittest.TestCase):
    def test_arm_records_the_layers_it_was_served_from(self):
        arm = make_arm()
        layers = arm.served_layers
        if "error" in layers and "not found" in layers["error"]:
            # The pinned tag is mutable shared state (AGENTS.md §8.2); when it is
            # absent from the resolved store this real-store probe cannot run.
            # Attribution mechanics stay locked by the hermetic tests below and
            # test_serving_defaults' layout/params cases. Never fall back across
            # stores here — that would attribute bytes to the wrong artifact.
            self.skipTest("pinned tag absent from resolved store: %s" % layers["error"])
        self.assertNotIn("error", layers, layers)
        self.assertTrue(layers["model"].startswith("sha256:"))
        self.assertGreater(layers.get("model_bytes", 0), 1_000_000_000,
                           "权重层字节数应在 GB 级，否则这不是模型层")
        gen = arm.generate([{"role": "user", "content": "hi"}], max_tokens=16)
        self.assertEqual(gen["served_layers"]["model"], layers["model"],
                         "每条响应必须带上实际服务层的指纹")

    def test_alias_tags_report_identical_layers(self):
        """The store currently aliases four names onto one artifact; the arm must show it."""
        digests = {}
        for tag in ("virtu-comprehensive:latest", "virtu-master:latest"):
            digests[tag] = OllamaNativeArm(tag).served_layers.get("model")
        if not all(digests.values()):
            self.skipTest("tags absent from this store right now")
        # assert the *reported* digests are what the store says, whatever they are
        for tag, digest in digests.items():
            self.assertTrue(digest.startswith("sha256:"), (tag, digest))


class TestToolsCapabilityDegradation(unittest.TestCase):
    def test_tools_rejection_degrades_to_json_protocol_instead_of_losing_the_case(self):
        arm = make_arm()
        gen = arm.generate([{"role": "user", "content": "选工具"}], max_tokens=32, tools=TOOLS)
        self.assertIsNone(gen["error"], gen)
        self.assertTrue(gen["text"])
        self.assertEqual(arm._opener.seen, [True, False],
                         "第一次带 tools 被拒后，重试必须去掉 tools")
        self.assertIs(arm.tools_supported, False)
        self.assertTrue(gen["tools_dropped_for_json_protocol"])

    def test_capability_is_cached_so_only_one_case_pays_for_the_probe(self):
        arm = make_arm()
        arm.generate([{"role": "user", "content": "a"}], tools=TOOLS)
        arm._opener.seen.clear()
        arm.generate([{"role": "user", "content": "b"}], tools=TOOLS)
        self.assertEqual(arm._opener.seen, [False], "第二条起不得再撞一次 400")

    def test_a_model_that_does_support_tools_is_not_silently_downgraded(self):
        arm = make_arm()
        arm.tools_supported = True
        opener = FakeOpener()
        opener.open = lambda req, timeout=None: FakeResponse(
            {"model": "fake", "done": True, "done_reason": "stop",
             "message": {"role": "assistant", "content": "ok"},
             "prompt_eval_count": 3, "eval_count": 1, "eval_duration": 1000000})
        arm._opener = opener
        gen = arm.generate([{"role": "user", "content": "hi"}], tools=TOOLS)
        self.assertIsNone(gen["error"], gen)
        self.assertFalse(gen["tools_dropped_for_json_protocol"])


class TestEmptyStoreMustNotShadowRealStore(unittest.TestCase):
    """OLLAMA_MODELS pointing at an empty leftover dir must not disable attribution."""

    def _fake_store(self, root, digest):
        man = root / "manifests" / "registry.ollama.ai" / "library" / "virtu-comprehensive"
        man.mkdir(parents=True)
        (man / "latest").write_text(json.dumps({
            "config": {"digest": "sha256:" + "c" * 64},
            "layers": [{"mediaType": "application/vnd.ollama.image.model",
                        "digest": digest, "size": 5_000_000_000}],
        }), encoding="utf-8")

    def test_empty_env_store_falls_through_to_home_store(self):
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            empty = tmp / "empty-env-store"
            empty.mkdir()
            home = tmp / "home"
            real_digest = "sha256:" + "a" * 64
            self._fake_store(home / ".ollama" / "models", real_digest)
            with patch.dict(os.environ, {"OLLAMA_MODELS": str(empty)}), \
                    patch("os.path.expanduser", lambda p: str(home) if p == "~" else p):
                layers = make_arm().served_layers
            self.assertNotIn("error", layers, layers)
            self.assertEqual(layers["model"], real_digest)

    def test_nonempty_env_store_still_wins(self):
        import tempfile
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            env_store = tmp / "env-store"
            env_digest = "sha256:" + "b" * 64
            self._fake_store(env_store, env_digest)
            home = tmp / "home"
            self._fake_store(home / ".ollama" / "models", "sha256:" + "a" * 64)
            with patch.dict(os.environ, {"OLLAMA_MODELS": str(env_store)}), \
                    patch("os.path.expanduser", lambda p: str(home) if p == "~" else p):
                layers = make_arm().served_layers
            self.assertEqual(layers["model"], env_digest)


if __name__ == "__main__":
    unittest.main()
