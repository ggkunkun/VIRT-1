import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from virtu_eval import runner
from virtu_eval.arms import HttpOpenAIArm


class _Arm:
    label = "fake-arm"

    def __init__(self, tool_calls=None):
        self.tool_calls = tool_calls
        self.loaded = False

    def load(self):
        self.loaded = True

    def unload(self):
        self.loaded = False

    def tools_for(self, case):
        return [{"type": "function", "function": {"name": "cadcam_test"}}] \
            if case["dimension"] == "toolcall" else None

    def generate(self, messages, **kwargs):
        return {"text": "", "tool_calls": self.tool_calls, "error": None,
                "finish_reason": "tool_calls", "elapsed_s": 0.01}


class EvalRunnerTests(unittest.TestCase):
    def test_local_http_arm_loads_auth_and_bypasses_proxy(self):
        with patch("bridges.bridge_security.ensure_bridge_token", return_value="x" * 48):
            arm = HttpOpenAIArm("http://127.0.0.1:8000/v1", "virtu-cad-cam-10b")
        self.assertEqual(arm.api_key, "x" * 48)
        self.assertIsNotNone(arm._opener)

    def make_case_dir(self, root):
        case_dir = root / "cases"
        case_dir.mkdir()
        case = {
            "id": "tool-1", "dimension": "toolcall", "tier": "easy",
            "prompt": "call the CAD tool",
            "criteria": [
                {"type": "json_object", "required_keys": ["tool", "arguments"], "key": "shape"},
                {"type": "literal_all", "values": ["cadcam_test"], "key": "tool"},
            ],
        }
        (case_dir / "toolcall.jsonl").write_text(json.dumps(case) + "\n", encoding="utf-8")
        return case_dir

    def test_dry_run_does_not_contaminate_real_raw_records(self):
        with tempfile.TemporaryDirectory() as temp:
            case_dir = self.make_case_dir(Path(temp))
            out_dir = Path(temp) / "run"
            runner.run(str(case_dir), {"kind": "http_openai", "model_id": "fake"},
                       str(out_dir), dims=["toolcall"], dry=True)
            self.assertFalse((out_dir / "raw.jsonl").exists())
            self.assertFalse((out_dir / "manifest.json").exists())
            self.assertTrue((out_dir / "dry_run.jsonl").exists())

            arm = _Arm([{"type": "function", "function": {"name": "cadcam_test",
                                                          "arguments": "{}"}}])
            with patch.object(runner, "build_arm", return_value=arm), \
                    patch.object(runner, "git_sha", return_value="abc123"):
                raw = runner.run(str(case_dir), {"kind": "http_openai", "model_id": "fake"},
                                 str(out_dir), dims=["toolcall"])
            lines = Path(raw).read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            self.assertNotEqual(json.loads(lines[0])["verdict"], "dry_run")

    def test_same_fingerprint_resumes_without_duplicate_generation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case_dir = self.make_case_dir(root)
            out_dir = root / "run"
            calls = [{"id": "c1", "type": "function", "function": {
                "name": "cadcam_test", "arguments": "{}"}}]
            arm = _Arm(calls)
            with patch.object(runner, "build_arm", return_value=arm), \
                    patch.object(runner, "git_sha", return_value="abc123"):
                raw = runner.run(str(case_dir), {"kind": "http_openai", "model_id": "fake"},
                                 str(out_dir), dims=["toolcall"])
                with patch.object(runner, "build_arm", side_effect=AssertionError("must skip completed case")):
                    runner.run(str(case_dir), {"kind": "http_openai", "model_id": "fake"},
                               str(out_dir), dims=["toolcall"])
            record = json.loads(Path(raw).read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(record["tool_calls"], calls)
            self.assertTrue(record["native_tool_call"])
            self.assertEqual(len(Path(raw).read_text(encoding="utf-8").splitlines()), 1)

    def test_changed_sampling_or_arm_refuses_resume(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case_dir = self.make_case_dir(root)
            out_dir = root / "run"
            arm = _Arm([{"type": "function", "function": {"name": "cadcam_test", "arguments": "{}"}}])
            with patch.object(runner, "build_arm", return_value=arm), \
                    patch.object(runner, "git_sha", return_value="abc123"):
                runner.run(str(case_dir), {"kind": "http_openai", "model_id": "fake"},
                           str(out_dir), dims=["toolcall"], temperature=0.0)
                with self.assertRaisesRegex(ValueError, "fingerprint"):
                    runner.run(str(case_dir), {"kind": "http_openai", "model_id": "fake"},
                               str(out_dir), dims=["toolcall"], temperature=0.2)
                with self.assertRaisesRegex(ValueError, "fingerprint"):
                    runner.run(str(case_dir), {"kind": "http_openai", "model_id": "other"},
                               str(out_dir), dims=["toolcall"], temperature=0.0)

    def test_malformed_raw_record_is_not_silently_ignored(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case_dir = self.make_case_dir(root)
            out_dir = root / "run"
            out_dir.mkdir()
            (out_dir / "raw.jsonl").write_text("{broken\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "malformed raw.jsonl"):
                runner.run(str(case_dir), {"kind": "http_openai", "model_id": "fake"},
                           str(out_dir), dims=["toolcall"])

    def test_selected_subset_is_part_of_resume_fingerprint(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case_dir = self.make_case_dir(root)
            with (case_dir / "toolcall.jsonl").open("a", encoding="utf-8") as stream:
                case = {"id": "tool-2", "dimension": "toolcall", "tier": "hard",
                        "prompt": "call", "criteria": [{"type": "not_empty", "key": "text"}]}
                stream.write(json.dumps(case) + "\n")
            out_dir = root / "run"
            calls = [{"type": "function", "function": {"name": "cadcam_test", "arguments": "{}"}}]
            with patch.object(runner, "build_arm", return_value=_Arm(calls)), \
                    patch.object(runner, "git_sha", return_value="abc123"):
                runner.run(str(case_dir), {"kind": "http_openai", "model_id": "fake"},
                           str(out_dir), dims=["toolcall"], tiers=["easy"])
                with self.assertRaisesRegex(ValueError, "fingerprint"):
                    runner.run(str(case_dir), {"kind": "http_openai", "model_id": "fake"},
                               str(out_dir), dims=["toolcall"], tiers=["hard"])


if __name__ == "__main__":
    unittest.main()
