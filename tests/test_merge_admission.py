import json
import math
import struct
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import merge_lora
import start_virtu_bridge


def _write_fake_adapter_safetensors(path, lora_a_shapes):
    """Minimal safetensors header: {tensor_name: {"dtype","shape","data_off"}}."""
    header = {}
    offset = 0
    for name, shape in lora_a_shapes.items():
        header[name] = {"dtype": "F32", "shape": list(shape),
                        "data_offsets": [offset, offset]}
        offset += 4
    blob = json.dumps(header).encode("utf-8")
    with open(path, "wb") as fh:
        fh.write(struct.pack("<Q", len(blob)))
        fh.write(blob)


class AdapterBaseMatchTests(unittest.TestCase):
    """The v100 LoRA was trained on Qwen2.5-7B but the deploy script points it at
    the Qwen3-8B base; that merge can never succeed, and it is what left
    virtu-master:latest holding a base model with no Virtu weights."""

    def _module(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "merge_and_deploy_v100",
            Path(start_virtu_bridge.ROOT) / "scripts" / "merge_and_deploy_v100.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_blocks_adapter_from_a_different_architecture(self):
        mod = self._module()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            lora = root / "lora"
            base = root / "base"
            lora.mkdir()
            base.mkdir()
            _write_fake_adapter_safetensors(
                lora / "adapter_model.safetensors",
                {"base_model.model.model.layers.0.self_attn.q_proj.lora_A.weight": [32, 3584],
                 "base_model.model.model.layers.27.self_attn.q_proj.lora_A.weight": [32, 3584]})
            (lora / "adapter_config.json").write_text(json.dumps(
                {"base_model_name_or_path": "/root/models/Qwen2.5-7B-Instruct"}),
                encoding="utf-8")
            (base / "config.json").write_text(json.dumps(
                {"architectures": ["Qwen3ForCausalLM"], "hidden_size": 4096,
                 "num_hidden_layers": 36}), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "不匹配"):
                mod.assert_adapter_matches_base(lora, base)

    def test_allows_adapter_matching_the_base(self):
        mod = self._module()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            lora = root / "lora"
            base = root / "base"
            lora.mkdir()
            base.mkdir()
            _write_fake_adapter_safetensors(
                lora / "adapter_model.safetensors",
                {f"base_model.model.model.layers.{i}.self_attn.q_proj.lora_A.weight": [32, 4096]
                 for i in range(36)})
            (lora / "adapter_config.json").write_text(json.dumps(
                {"base_model_name_or_path": "/root/models/Qwen3-8B"}), encoding="utf-8")
            (base / "config.json").write_text(json.dumps(
                {"architectures": ["Qwen3ForCausalLM"], "hidden_size": 4096,
                 "num_hidden_layers": 36}), encoding="utf-8")
            mod.assert_adapter_matches_base(lora, base)

    def test_refuses_to_guess_when_files_are_missing(self):
        mod = self._module()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(RuntimeError, "无法校验"):
                mod.assert_adapter_matches_base(root / "nope", root / "also_nope")


class MergeAdmissionTests(unittest.TestCase):
    def test_launcher_probe_accepts_exact_tagged_model(self):
        class _Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps({"models": [{"name": "qwen3:8b"},
                                              {"name": "virtu-toolcall:latest"}]}).encode()

        class _Opener:
            def open(self, *_args, **_kwargs):
                return _Response()

        with patch.object(start_virtu_bridge.urllib.request, "build_opener",
                          return_value=_Opener()):
            self.assertTrue(start_virtu_bridge.probe_ollama("qwen3:8b"))
            self.assertTrue(start_virtu_bridge.probe_ollama("virtu-toolcall"))
            self.assertFalse(start_virtu_bridge.probe_ollama("missing-model"))

    def test_merge_rejects_mismatched_weight_count_before_importing_torch(self):
        with patch("argparse.ArgumentParser.parse_args", return_value=SimpleNamespace(
                base="base", lora=["one", "two"], weight=[1.0], all=False,
                out="out", device="auto")):
            with self.assertRaisesRegex(SystemExit, "数量"):
                merge_lora.main()

    def test_merge_rejects_nonfinite_weights(self):
        with patch("argparse.ArgumentParser.parse_args", return_value=SimpleNamespace(
                base="base", lora=["one"], weight=[math.inf], all=False,
                out="out", device="auto")):
            with self.assertRaisesRegex(SystemExit, "有限"):
                merge_lora.main()

    def test_merge_refuses_nonempty_output_without_overwriting(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp) / "base"
            out = Path(temp) / "out"
            base.mkdir()
            out.mkdir()
            sentinel = out / "keep.bin"
            sentinel.write_bytes(b"preserve")
            with patch("argparse.ArgumentParser.parse_args", return_value=SimpleNamespace(
                    base=str(base), lora=[], weight=[], all=False,
                    out=str(out), device="auto")):
                with self.assertRaisesRegex(SystemExit, "拒绝覆盖"):
                    merge_lora.main()
            self.assertEqual(sentinel.read_bytes(), b"preserve")

    def test_trained_whitelist_excludes_base_and_disproven_artifacts(self):
        """The whitelist is the anti-misattribution gate, so its contents are the
        contract: no untrained base, no peft_linear-era merges, and the canonical
        30-case-validated artifact leads."""
        prio = start_virtu_bridge.VIRTU_ARTIFACT_PRIORITY
        self.assertEqual(prio[0], "virtu-ties-v1")
        for banned in ("qwen3:8b", "virtu-omni-8b", "virtu-production:v3",
                       "virtu-master:v4", "virtu-master:latest"):
            self.assertNotIn(banned, prio)

    def test_launcher_never_autoserves_the_untrained_base(self):
        """Auto-detection must land on a trained Virtu artifact. Picking qwen3:8b
        because it happens to be installed measures the base model under the
        virtu-cad-cam-10b id, which is how capability claims get falsified."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            checkpoints = root / "checkpoints"
            checkpoints.mkdir()
            gguf = checkpoints / "virtu-master-v4-q4_0.gguf"
            gguf.write_bytes(b"gguf")
            Path(str(gguf) + ".receipt.json").write_text(json.dumps(
                {"status": "ok", "unmapped": [], "file_bytes": gguf.stat().st_size}),
                encoding="utf-8")
            cfg = {"model_path": "", "gguf_path": "", "vllm_url": "",
                   "vllm_model": "qwen3:8b", "conv_lora": "", "cad_lora": "",
                   "_explicit": set()}
            installed = {"qwen3:8b", "virtu-toolcall", "virtu-master:v4"}
            with patch.object(start_virtu_bridge, "ROOT", str(root)), \
                    patch.object(start_virtu_bridge, "probe_ollama",
                                 side_effect=lambda m: m in installed):
                plan = start_virtu_bridge.resolve_plan(cfg, None)
            self.assertEqual(plan, "vllm_http")
            # Base is installed but never chosen; virtu-master:v4 is installed but
            # excluded by measurement, so the trained whitelist pick is toolcall.
            self.assertEqual(cfg["vllm_model"], "virtu-toolcall")

    def test_launcher_falls_back_to_local_artifact_not_base_when_only_base_installed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            checkpoints = root / "checkpoints"
            checkpoints.mkdir()
            gguf = checkpoints / "virtu-master-v4-q4_0.gguf"
            gguf.write_bytes(b"gguf")
            Path(str(gguf) + ".receipt.json").write_text(json.dumps(
                {"status": "ok", "unmapped": [], "file_bytes": gguf.stat().st_size}),
                encoding="utf-8")
            cfg = {"model_path": "", "gguf_path": "", "vllm_url": "",
                   "vllm_model": "qwen3:8b", "conv_lora": "", "cad_lora": "",
                   "_explicit": set()}
            with patch.object(start_virtu_bridge, "ROOT", str(root)), \
                    patch.object(start_virtu_bridge, "probe_ollama",
                                 side_effect=lambda m: m == "qwen3:8b"):
                plan = start_virtu_bridge.resolve_plan(cfg, None)
            self.assertNotEqual(plan, "vllm_http")

    def test_launcher_honours_explicit_base_but_warns(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            checkpoints = root / "checkpoints"
            checkpoints.mkdir()
            gguf = checkpoints / "virtu-master-v4-q4_0.gguf"
            gguf.write_bytes(b"gguf")
            Path(str(gguf) + ".receipt.json").write_text(json.dumps(
                {"status": "ok", "unmapped": [], "file_bytes": gguf.stat().st_size}),
                encoding="utf-8")
            cfg = {"model_path": "", "gguf_path": "", "vllm_url": "",
                   "vllm_model": "qwen3:8b", "conv_lora": "", "cad_lora": "",
                   "_explicit": {"vllm_model"}}
            import io
            from contextlib import redirect_stdout
            buf = io.StringIO()
            with patch.object(start_virtu_bridge, "ROOT", str(root)), \
                    patch.object(start_virtu_bridge, "probe_ollama", return_value=True), \
                    redirect_stdout(buf):
                plan = start_virtu_bridge.resolve_plan(cfg, None)
            self.assertEqual(plan, "vllm_http")
            self.assertIn("不是已训练的 Virtu 产物", buf.getvalue())

    def test_launcher_ignores_hf_candidate_without_pass_report(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            candidate = root / "checkpoints" / "virtu_cad_cam_merged_v3"
            candidate.mkdir(parents=True)
            (candidate / "config.json").write_text("{}", encoding="utf-8")
            (candidate / "merge_receipt.json").write_text(
                json.dumps({"status": "COMPLETED"}), encoding="utf-8")
            cfg = {"model_path": "", "gguf_path": "", "vllm_url": "",
                   "vllm_model": "test", "conv_lora": "", "cad_lora": "",
                   "_explicit": set()}
            with patch.object(start_virtu_bridge, "ROOT", str(root)), \
                    patch.object(start_virtu_bridge, "probe_ollama", return_value=False):
                self.assertEqual(start_virtu_bridge.resolve_plan(cfg, None), "cloud")

    def test_launcher_requires_matching_gguf_receipt_size(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            checkpoints = root / "checkpoints"
            checkpoints.mkdir()
            gguf = checkpoints / "virtu-production-v3-q4_0.gguf"
            gguf.write_bytes(b"gguf-test")
            receipt = {"status": "ok", "unmapped": [], "file_bytes": gguf.stat().st_size + 1}
            Path(str(gguf) + ".receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
            cfg = {"model_path": "", "gguf_path": "", "vllm_url": "",
                   "vllm_model": "test", "conv_lora": "", "cad_lora": "",
                   "_explicit": set()}
            with patch.object(start_virtu_bridge, "ROOT", str(root)), \
                    patch.object(start_virtu_bridge, "probe_ollama", return_value=False):
                self.assertEqual(start_virtu_bridge.resolve_plan(cfg, None), "cloud")


if __name__ == "__main__":
    unittest.main()
