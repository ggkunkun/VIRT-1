"""Unit tests for Streaming Multimodal Data Pipeline."""

from PIL import Image
from virtu_omni.config import DataConfig
from virtu_omni.data.pipeline import StreamingMultimodalDataPipeline


def test_preprocess_image():
    config = DataConfig(image_resolution=56)
    pipeline = StreamingMultimodalDataPipeline(config)
    img = Image.new("RGB", (100, 100), color=(255, 0, 0))
    tensor = pipeline.preprocess_image(img)
    assert tensor.shape == (3, 56, 56)
    assert tensor.min() >= -1.0
    assert tensor.max() <= 1.0


def test_tokenize_text():
    config = DataConfig(max_text_tokens=64)
    pipeline = StreamingMultimodalDataPipeline(config)
    tokens = pipeline.tokenize_text("Hello multimodal world")
    assert tokens.dim() == 1
    assert tokens[0] == 1  # Bos token
    assert tokens[-1] == 2  # Eos token


def test_streaming_batches():
    config = DataConfig(image_resolution=56, max_text_tokens=32)
    pipeline = StreamingMultimodalDataPipeline(config)
    batches = list(pipeline.generate_streaming_batches(num_samples=10, batch_size=4))
    assert len(batches) == 3
    assert batches[0]["images"].shape == (4, 3, 56, 56)
    assert batches[0]["input_ids"].shape[0] == 4


def test_benchmark_throughput():
    config = DataConfig(image_resolution=56, max_daily_pairs=1000)
    pipeline = StreamingMultimodalDataPipeline(config)
    res = pipeline.benchmark_throughput(sample_count=20, batch_size=10)
    assert res["processed_samples"] == 20
    assert res["throughput_pairs_per_sec"] > 0
    assert res["projected_daily_capacity"] > 0
