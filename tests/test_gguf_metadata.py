import tempfile
import unittest
from pathlib import Path

from scripts.hf_to_gguf_numpy import build_metadata


class GGUFMetadataTests(unittest.TestCase):
    def test_model_name_and_description_do_not_misattribute_merge_method(self):
        cfg = {
            "hidden_size": 4,
            "num_hidden_layers": 1,
            "num_attention_heads": 1,
            "num_key_value_heads": 1,
            "intermediate_size": 8,
            "vocab_size": 2,
        }
        tokenizer = {"model": {"vocab": {"<unk>": 0, "x": 1}, "merges": []}}
        with tempfile.TemporaryDirectory() as temp:
            model = Path(temp) / "virtu_ties_v1"
            model.mkdir()
            metadata, *_ = build_metadata(model, cfg, {}, tokenizer)

        self.assertIn(b"virtu-ties-v1", metadata)
        self.assertIn(b"Qwen3 architecture checkpoint, Q4_0 GGUF", metadata)
        self.assertNotIn(b"peft_linear", metadata)
        self.assertNotIn(b"virtu-omni-8b", metadata)


if __name__ == "__main__":
    unittest.main()
