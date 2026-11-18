"""Unit tests for RESTful Inference Server."""

import secrets

import pytest
import threading
from fastapi.testclient import TestClient
from virtu_omni.config import VirtuOmniConfig, ModelConfig
from virtu_omni.serving.server import create_app
from virtu_omni.serving import server as server_module

# 运行时生成，避免在源码里写死一个凭据形状的字面量（tests/test_no_hardcoded_credentials.py 会拦）。
TEST_TOKEN = secrets.token_urlsafe(36)
AUTH = {"Authorization": f"Bearer {TEST_TOKEN}"}


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
    app = create_app(cfg, bearer_token=TEST_TOKEN)
    return TestClient(app, headers=AUTH)


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


def test_every_route_requires_bearer_before_body_or_handler():
    cfg = VirtuOmniConfig(model=ModelConfig(
        num_layers=1, hidden_dim=64, intermediate_dim=192, vocab_size=200,
        patch_size=14, image_resolution=56,
    ))
    client = TestClient(create_app(cfg, bearer_token=TEST_TOKEN))
    paths = [
        ("GET", "/v1/health"), ("GET", "/v1/metrics"), ("GET", "/docs"),
        ("POST", "/v1/chat/completions"),
        ("POST", "/v1/multimodal/generate_image"),
        ("POST", "/v1/multimodal/understand"),
    ]
    for method, path in paths:
        response = client.request(method, path, content=b"x" * 100)
        assert response.status_code == 401, (method, path, response.text)
        assert TEST_TOKEN not in response.text


def test_serving_body_limit_is_checked_before_pydantic():
    cfg = VirtuOmniConfig(model=ModelConfig(
        num_layers=1, hidden_dim=64, intermediate_dim=192, vocab_size=200,
        patch_size=14, image_resolution=56,
    ))
    cfg.serving.max_request_bytes = 1024
    client = TestClient(create_app(cfg, bearer_token=TEST_TOKEN), headers=AUTH)
    response = client.post("/v1/chat/completions", content=b" " * 1025,
                           headers={**AUTH, "Content-Type": "application/json"})
    assert response.status_code == 413


def test_inference_concurrency_rejects_and_recovers(monkeypatch):
    cfg = VirtuOmniConfig(model=ModelConfig(
        num_layers=1, hidden_dim=64, intermediate_dim=192, vocab_size=200,
        patch_size=14, image_resolution=56,
    ))
    cfg.serving.max_inference_concurrency = 1
    client = TestClient(create_app(cfg, bearer_token=TEST_TOKEN), headers=AUTH)
    entered = threading.Event()
    release = threading.Event()

    def blocked_generate(self, *args, **kwargs):
        entered.set()
        assert release.wait(timeout=5)
        return server_module.torch.tensor([[1, 2, 3]])

    monkeypatch.setattr(server_module.VirtuOmni10B, "generate", blocked_generate)
    payload = {"messages": [{"role": "user", "content": "hello"}], "max_tokens": 2}
    first_result = []
    first = threading.Thread(target=lambda: first_result.append(
        client.post("/v1/chat/completions", json=payload)), daemon=True)
    first.start()
    assert entered.wait(timeout=3)

    second = client.post("/v1/chat/completions", json=payload)
    assert second.status_code == 503
    release.set()
    first.join(timeout=5)
    assert not first.is_alive()
    assert first_result[0].status_code == 200
    assert client.post("/v1/chat/completions", json=payload).status_code == 200


def test_config_defaults_to_loopback_and_has_small_inference_budget():
    cfg = VirtuOmniConfig()
    assert cfg.serving.host == "127.0.0.1"
    assert cfg.serving.max_inference_concurrency <= 4
