"""Unit tests for RESTful Inference Server."""

import pytest
from fastapi.testclient import TestClient
from virtu_omni.config import VirtuOmniConfig, ModelConfig
from virtu_omni.serving.server import create_app


@pytest.fixture
def test_client():
    cfg = VirtuOmniConfig(
        model=ModelConfig(
            num_layers=1,
            hidden_dim=64,
            intermediate_dim=192,
            vocab_size=200,
            patch_size=14,
            image_resolution=56,
        )
    )
    app = create_app(cfg)
    return TestClient(app)


def test_health_endpoint(test_client):
    response = test_client.get("/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "HEALTHY"
    assert "gpu_memory_allocated_gb" in data


def test_chat_completions_text(test_client):
    payload = {
        "model": "Virtu-Omni-10B",
        "messages": [{"role": "user", "content": "What is artificial intelligence?"}],
        "stream": False,
    }
    response = test_client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "choices" in data
    assert len(data["choices"]) > 0
    assert "performance" in data


def test_generate_image(test_client):
    payload = {
        "prompt": "A futuristic city in watercolor style",
        "height": 512,
        "width": 512,
    }
    response = test_client.post("/v1/multimodal/generate_image", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "image_base64" in data
    assert data["status"] == "SUCCESS"


def test_metrics_endpoint(test_client):
    response = test_client.get("/v1/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "single_a100_slo_ms" in data
    assert "slo_compliance_rate" in data
