"""Industrial High-Performance RESTful Inference Server for Virtu-Omni-10B.

Provides commercial-grade endpoints:
- POST /v1/chat/completions: Text generation with streaming token SSE support.
- POST /v1/multimodal/generate_image: Text-to-image synthesis pipeline.
- POST /v1/multimodal/understand: Image-text reasoning and visual QA.
- GET /v1/health: Health probes and cluster readiness telemetry.
- GET /v1/metrics: Prometheus performance metrics.
Optimized for A100 SXM4 (80GB) with PagedAttention and target latency <= 200ms.
"""

from __future__ import annotations
import os
import json
import time
import base64
import io
import asyncio
import logging
import threading
from collections import deque
from typing import Dict, Any, List, Optional
import torch
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from PIL import Image
from starlette.types import ASGIApp, Receive, Scope, Send

from bridges.bridge_security import bearer_authorized, ensure_service_token
from virtu_omni.config import VirtuOmniConfig, ModelConfig
from virtu_omni.errors import (
    ModelError,
    SERVE_IMAGE_DECODE,
    SERVE_MODEL_FAILURE,
    SERVE_INFER_FAILURE,
)
from virtu_omni.models.architecture import VirtuOmni10B
from virtu_omni.models.tokenizer import BOS_TOKEN_ID, VirtuTokenizer
from virtu_omni.serving.deception_gate import gate_answer

logger = logging.getLogger(__name__)

# Reject oversized payloads before they are decoded into memory.
MAX_IMAGE_BASE64_BYTES = 32 * 1024 * 1024
MAX_IMAGE_PIXELS = 25_000_000
MAX_TEXT_CHARS = 32768
LATENCY_WINDOW = 10000


class ServingSecurityMiddleware:
    """Authenticate and bound HTTP requests before FastAPI parses their bodies."""

    def __init__(self, app: ASGIApp, *, token: str, max_body_bytes: int,
                 max_concurrency: int):
        self.app = app
        self.token = token
        self.max_body_bytes = max_body_bytes
        self.request_slots = threading.BoundedSemaphore(max_concurrency)

    @staticmethod
    async def _reject(send: Send, status: int, message: str) -> None:
        body = json.dumps({"detail": message}, ensure_ascii=False).encode("utf-8")
        headers = [(b"content-type", b"application/json; charset=utf-8"),
                   (b"content-length", str(len(body)).encode("ascii"))]
        if status == 401:
            headers.append((b"www-authenticate", b"Bearer"))
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": body})

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = scope.get("headers", [])
        auth_values = [value.decode("latin-1") for name, value in headers
                       if name.lower() == b"authorization"]
        if len(auth_values) != 1 or not bearer_authorized(auth_values[0], self.token):
            await self._reject(send, 401, "Valid Bearer token required")
            return

        if not self.request_slots.acquire(blocking=False):
            await self._reject(send, 503, "Serving service is busy; retry later")
            return

        try:
            transfer_encoded = any(name.lower() == b"transfer-encoding" for name, _ in headers)
            raw_lengths = [value for name, value in headers if name.lower() == b"content-length"]
            try:
                lengths = [value.decode("ascii") for value in raw_lengths]
            except UnicodeDecodeError:
                await self._reject(send, 400, "Invalid Content-Length")
                return
            if len(lengths) > 1:
                await self._reject(send, 400, "Ambiguous Content-Length")
                return
            if transfer_encoded and lengths:
                await self._reject(send, 400, "Transfer-Encoding and Content-Length cannot be combined")
                return
            if lengths:
                if not lengths[0].isdigit() or len(lengths[0]) > 10:
                    await self._reject(send, 400, "Invalid Content-Length")
                    return
                if int(lengths[0]) > self.max_body_bytes:
                    await self._reject(send, 413, "Request body exceeds allowed size")
                    return

            body = bytearray()
            while True:
                try:
                    message = await asyncio.wait_for(receive(), timeout=30.0)
                except asyncio.TimeoutError:
                    await self._reject(send, 408, "Timed out while receiving request body")
                    return
                if message["type"] == "http.disconnect":
                    return
                if message["type"] != "http.request":
                    continue
                body.extend(message.get("body", b""))
                if len(body) > self.max_body_bytes:
                    await self._reject(send, 413, "Request body exceeds allowed size")
                    return
                if not message.get("more_body", False):
                    break

            buffered_body = bytes(body)
            delivered = False

            async def replay_receive():
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {"type": "http.request", "body": buffered_body,
                            "more_body": False}
                return await receive()

            await self.app(scope, replay_receive, send)
        finally:
            self.request_slots.release()


# Pydantic Schemas
class Message(BaseModel):
    role: str = Field(..., description="Role: 'user', 'assistant', or 'system'")
    content: str = Field(..., max_length=MAX_TEXT_CHARS,
                         description="Text content or multimodal JSON structure")
    image_base64: Optional[str] = Field(None, max_length=MAX_IMAGE_BASE64_BYTES + 256,
                                        description="Optional base64-encoded image")


class ChatCompletionRequest(BaseModel):
    model: str = "Virtu-Omni-10B"
    messages: List[Message] = Field(..., min_length=1, max_length=128)
    max_tokens: int = Field(512, ge=1, le=4096)
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    top_p: float = Field(0.9, ge=0.0, le=1.0)
    stream: bool = False


class ImageGenerationRequest(BaseModel):
    prompt: str = Field(..., max_length=MAX_TEXT_CHARS,
                        description="Linguistic description of the target image")
    negative_prompt: Optional[str] = Field(None, max_length=MAX_TEXT_CHARS)
    height: int = Field(512, ge=256, le=1024)
    width: int = Field(512, ge=256, le=1024)
    num_inference_steps: int = Field(20, ge=1, le=100)
    guidance_scale: float = Field(7.5, ge=1.0, le=20.0)


class MultimodalUnderstandRequest(BaseModel):
    image_base64: str = Field(..., max_length=MAX_IMAGE_BASE64_BYTES + 256,
                              description="Base64-encoded input image")
    question: str = Field("Describe this image in comprehensive detail.",
                          max_length=MAX_TEXT_CHARS, description="User query")


def _decode_base64_image(payload: str, resolution: int, patch_size: int) -> torch.Tensor:
    """Decode a (possibly data-URL prefixed) base64 image into a normalized tensor.

    Raises ``HTTPException`` with the structured ``E4001`` code on any failure so
    clients receive an actionable error instead of an opaque 500.
    """
    if not isinstance(payload, str) or not payload:
        raise HTTPException(
            status_code=400,
            detail=ModelError(
                SERVE_IMAGE_DECODE,
                "image_base64 must be a non-empty string.",
                hint="Send raw base64 or a 'data:image/png;base64,...' payload.",
            ).to_dict(),
        )
    # Browsers/OpenAI clients frequently prepend a data-URL header; the old
    # b64decode() path failed on it and returned a misleading "invalid image".
    if payload.startswith("data:"):
        _, _, payload = payload.partition(",")
    if len(payload) > MAX_IMAGE_BASE64_BYTES:
        raise HTTPException(
            status_code=413,
            detail=ModelError(
                SERVE_IMAGE_DECODE,
                f"Encoded image exceeds the {MAX_IMAGE_BASE64_BYTES} byte limit.",
                hint="Downscale the image before uploading.",
                context={"encoded_bytes": len(payload)},
            ).to_dict(),
        )
    try:
        img_data = base64.b64decode(payload, validate=True)
        img = Image.open(io.BytesIO(img_data))
        width, height = img.size
        if width < 1 or height < 1 or width * height > MAX_IMAGE_PIXELS:
            raise ValueError("Image dimensions exceed the allowed pixel count")
        img = img.convert("RGB")
        # Snap the resize target to a patch-size multiple so the vision
        # projector never receives a non-divisible grid.
        side = max(patch_size, (resolution // patch_size) * patch_size)
        img = img.resize((side, side))
    except Exception as exc:  # noqa: BLE001 - surfaced as a structured 400
        raise HTTPException(
            status_code=400,
            detail=ModelError(
                SERVE_IMAGE_DECODE,
                f"Invalid image payload: {type(exc).__name__}: {exc}",
                hint="Send a valid PNG/JPEG base64 payload (optionally as a data URL).",
            ).to_dict(),
        ) from exc

    return (
        torch.frombuffer(bytearray(img.tobytes()), dtype=torch.uint8)
        .view(side, side, 3)
        .permute(2, 0, 1)
        .unsqueeze(0)
        .float()
        / 127.5
        - 1.0
    )


def _encode_scaffold_tokens(text: str, vocab_size: int, max_tokens: int = 512) -> torch.Tensor:
    """Deterministic scaffold tokenizer used until the shipped tokenizer is bound.

    The previous handler always fed the constant id ``42`` regardless of the prompt,
    so every request produced byte-identical logits. Until a real vocabulary is
    wired into this serving path, ids are derived from the character ordinals so
    the forward pass at least remains a genuine function of the user input.
    """
    if vocab_size < 3:
        raise ModelError(
            SERVE_INFER_FAILURE,
            f"vocab_size={vocab_size} is too small to tokenize text.",
            hint="Use a model config with vocab_size >= 3.",
            context={"vocab_size": vocab_size},
        )
    ids: List[int] = [1]  # BOS
    budget = max(0, max_tokens - 1)
    for ch in text:
        if len(ids) - 1 >= budget:
            break
        ids.append(2 + (ord(ch) % (vocab_size - 2)))
    if len(ids) == 1:
        ids.append(2)  # never emit an empty sequence
    return torch.tensor([ids], dtype=torch.long)


def create_app(config: Optional[VirtuOmniConfig] = None, *,
               bearer_token: Optional[str] = None) -> FastAPI:
    """Initialize FastAPI application with model lifecycle bindings."""
    if config is not None:
        cfg = config
    elif os.environ.get("VIRTU_FULL_10B") == "1":
        cfg = VirtuOmniConfig()
    else:
        # Default to lightweight proxy model to prevent OOM on non-cluster dev machines
        cfg = VirtuOmniConfig(
            model=ModelConfig(
                num_layers=2,
                hidden_dim=256,
                intermediate_dim=768,
                num_attention_heads=4,
                num_kv_heads=2,
                head_dim=64,
                vocab_size=1000,
                vision_codebook_size=500,
                image_resolution=56,
                patch_size=14,
            )
        )
    app = FastAPI(
        title="Virtu-Omni-10B Commercial Inference Service",
        description="Unified End-to-End Multimodal RESTful Inference Engine",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    serving_token = (bearer_token if bearer_token is not None else
                     ensure_service_token("serving", "VIRTU_SERVING_TOKEN"))
    serving_token = serving_token.strip()
    if len(serving_token) < 32 or any(ch.isspace() for ch in serving_token):
        raise RuntimeError("Serving Bearer token must contain at least 32 non-whitespace characters")
    app.add_middleware(
        ServingSecurityMiddleware,
        token=serving_token,
        max_body_bytes=cfg.serving.max_request_bytes,
        max_concurrency=cfg.serving.max_concurrency,
    )
    app.state.inference_slots = threading.BoundedSemaphore(
        cfg.serving.max_inference_concurrency)

    def acquire_inference_slot() -> None:
        if not app.state.inference_slots.acquire(blocking=False):
            raise HTTPException(status_code=503,
                                detail="Inference capacity is busy; retry later")

    if torch.cuda.is_available():
        torch.backends.cuda.matmul.allow_tf32 = True
        if hasattr(torch.backends, "cudnn"):
            torch.backends.cudnn.allow_tf32 = True
        torch.set_float32_matmul_precision("high")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = VirtuOmni10B(cfg.model).to(device)
    model.eval()
    tokenizer = VirtuTokenizer(vocab_size=cfg.model.vocab_size)

    # Latency tracking stats — bounded ring buffer. The previous unbounded list
    # kept one float per request for the life of the process, so a long-running
    # service leaked memory proportional to total traffic.
    request_latencies: "deque[float]" = deque(maxlen=LATENCY_WINDOW)

    @app.get("/v1/health")
    async def health_check() -> Dict[str, Any]:
        """Readiness and liveness probe."""
        gpu_allocated = (
            torch.cuda.memory_allocated() / (1024 ** 3) if torch.cuda.is_available() else 0.0
        )
        return {
            "status": "HEALTHY",
            "model": cfg.model.model_name,
            "version": "1.0.0",
            "device": str(device),
            "gpu_memory_allocated_gb": round(gpu_allocated, 2),
            "paged_attention_enabled": cfg.serving.enable_paged_attention,
            "target_latency_ms": cfg.serving.target_latency_ms,
        }

    @app.post("/v1/chat/completions")
    async def chat_completions(request: ChatCompletionRequest):
        """Standard chat completions supporting text and multimodal inputs."""
        start_time = time.perf_counter()

        # Extract last user message and possible image
        user_msg = next((m for m in reversed(request.messages) if m.role == "user"), None)
        if not user_msg:
            # Structured client error instead of a bare FastAPI string detail.
            raise HTTPException(
                status_code=400,
                detail=ModelError(
                    SERVE_INFER_FAILURE,
                    "No user message provided in context.",
                    hint="Include at least one message whose role is 'user'.",
                    context={"messages": len(request.messages)},
                ).to_dict(),
            )

        image_tensor = None
        if user_msg.image_base64:
            # Resolution now follows the configured model geometry instead of the
            # previous hardcoded 448 px, which desynchronised the patch grid
            # whenever patch_size did not divide 448.
            image_tensor = _decode_base64_image(
                user_msg.image_base64, cfg.model.image_resolution, cfg.model.patch_size
            ).to(device)

        # A prompt is BOS + content. ``encode`` also appends EOS by default, which
        # tells the decoder the sequence is already finished and inflates
        # ``prompt_tokens`` by one; prepend BOS explicitly instead.
        prompt_text = user_msg.content
        if image_tensor is None:
            # 所有模型统一联网：纯文本请求注入实时检索资料；检索失败则原样使用原文。
            try:
                from virtu_omni.internet.augmentation import augment_prompt
                prompt_text, _citations = await asyncio.to_thread(
                    augment_prompt, prompt_text)
            except Exception:
                prompt_text = user_msg.content
        input_ids = tokenizer.encode(
            prompt_text,
            max_length=cfg.model.max_position_embeddings,
            add_special_tokens=False,
        ).to(device)
        input_ids = torch.cat(
            [torch.full((1, 1), BOS_TOKEN_ID, dtype=input_ids.dtype, device=device), input_ids],
            dim=1,
        )

        token_budget = min(request.max_tokens, 16 if cfg.model.vocab_size < 1000 else 512)

        if request.stream:
            acquire_inference_slot()

            async def _stream_events():
                req_id = f"chatcmpl-virtu-{int(time.time() * 1000)}"
                created_ts = int(time.time())
                header = json.dumps({
                    "id": req_id,
                    "object": "chat.completion.chunk",
                    "created": created_ts,
                    "model": request.model,
                    "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
                })
                yield f"data: {header}\n\n"

                streamer = tokenizer.create_streamer()

                def _stream_runner():
                    return list(model.generate_stream(
                        input_ids=input_ids,
                        images=image_tensor,
                        max_new_tokens=token_budget,
                        temperature=request.temperature,
                        top_p=request.top_p,
                        use_cache=True,
                        loop_steps=1,
                    ))

                try:
                    tokens = await asyncio.to_thread(_stream_runner)
                    for tid in tokens:
                        chunk = streamer.put(tid)
                        if chunk:
                            payload = json.dumps({
                                "id": req_id,
                                "object": "chat.completion.chunk",
                                "created": created_ts,
                                "model": request.model,
                                "choices": [{"index": 0, "delta": {"content": chunk}, "finish_reason": None}],
                            })
                            yield f"data: {payload}\n\n"
                            await asyncio.sleep(0)

                    tail = streamer.flush()
                    if tail:
                        payload = json.dumps({
                            "id": req_id,
                            "object": "chat.completion.chunk",
                            "created": created_ts,
                            "model": request.model,
                            "choices": [{"index": 0, "delta": {"content": tail}, "finish_reason": None}],
                        })
                        yield f"data: {payload}\n\n"

                    end_payload = json.dumps({
                        "id": req_id,
                        "object": "chat.completion.chunk",
                        "created": created_ts,
                        "model": request.model,
                        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                    })
                    yield f"data: {end_payload}\n\n"
                    yield "data: [DONE]\n\n"
                except Exception as exc:
                    err_payload = json.dumps({"error": {"message": str(exc), "type": "server_error"}})
                    yield f"data: {err_payload}\n\n"

            async def event_generator():
                try:
                    async for chunk in _stream_events():
                        yield chunk
                finally:
                    app.state.inference_slots.release()

            return StreamingResponse(event_generator(), media_type="text/event-stream")

        def _generate_tokens() -> torch.Tensor:
            with torch.inference_mode():
                return model.generate(
                    input_ids=input_ids,
                    images=image_tensor,
                    max_new_tokens=token_budget,
                    temperature=request.temperature,
                    top_p=request.top_p,
                    use_cache=True,
                    loop_steps=1,
                )

        acquire_inference_slot()
        try:
            try:
                generated_ids = await asyncio.to_thread(_generate_tokens)
            except ModelError as exc:
                logger.warning("chat inference rejected: %s", exc.to_dict())
                raise HTTPException(status_code=400, detail=exc.to_dict()) from exc
            except Exception as exc:  # noqa: BLE001 - mapped to a structured 503
                logger.exception("chat inference crashed")
                raise HTTPException(
                    status_code=503,
                    detail=ModelError(
                        SERVE_MODEL_FAILURE,
                        f"Model execution failed: {type(exc).__name__}: {exc}",
                        hint="Check server logs; retry once the model is ready.",
                        context={"mode": "text_gen"},
                    ).to_dict(),
                ) from exc
        finally:
            app.state.inference_slots.release()

        latency_ms = (time.perf_counter() - start_time) * 1000
        request_latencies.append(latency_ms)

        prompt_tokens = int(input_ids.shape[1])
        new_token_ids = generated_ids[0, prompt_tokens:].tolist()
        completion_tokens = len(new_token_ids)
        total_tokens = prompt_tokens + completion_tokens
        response_text = tokenizer.decode(new_token_ids)
        if not response_text:
            response_text = "..."
        gate = gate_answer(
            response_text,
            prompt=str(getattr(user_msg, "content", "") or ""),
            done_reason="length" if completion_tokens >= request.max_tokens else None,
        )
        response_text = gate.text

        tps = round(completion_tokens / (latency_ms / 1000.0), 2) if latency_ms > 0 else 0.0

        return {
            "id": f"chatcmpl-virtu-{int(time.time() * 1000)}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": request.model,
            "degraded": cfg.model.vocab_size < 1000,
            "virtu_gate": gate.to_dict(),
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": response_text},
                    "finish_reason": "length" if gate.action == "incomplete" else "stop",
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            },
            "generated_token_ids": new_token_ids,
            "performance": {
                "latency_ms": round(latency_ms, 2),
                "tokens_per_second": tps,
                "target_threshold_ms": cfg.serving.target_latency_ms,
                "slo_satisfied": latency_ms <= cfg.serving.target_latency_ms,
            },
        }

    @app.post("/v1/multimodal/generate_image")
    async def generate_image(request: ImageGenerationRequest) -> Dict[str, Any]:
        """Text-to-Image Generation Endpoint (synthetic placeholder renderer)."""
        start_time = time.perf_counter()
        # Removed the blocking time.sleep(0.08) "simulated latency": inside an
        # async endpoint it stalled the entire event loop instead of costing only
        # this request's budget.

        # The vision codebook head is not yet conditioned on the prompt, so a
        # solid-colour frame is produced. It is explicitly labelled ``placeholder``
        # instead of passing off a blue square as model output.
        img = Image.new("RGB", (request.width, request.height), color=(30, 144, 255))
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=90)
        img_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

        latency_ms = (time.perf_counter() - start_time) * 1000
        return {
            "created": int(time.time()),
            "prompt": request.prompt,
            "height": request.height,
            "width": request.width,
            "image_base64": img_b64,
            "generation_time_ms": round(latency_ms, 2),
            "status": "SUCCESS",
            "mode": "placeholder",
            "synthetic": True,
            "note": (
                "Codebook-conditioned image synthesis is not wired to this endpoint; "
                "the returned frame is a constant-colour placeholder."
            ),
        }

    @app.post("/v1/multimodal/understand")
    async def understand_image(request: MultimodalUnderstandRequest) -> Dict[str, Any]:
        """Image-to-Text Visual Question Answering Endpoint (scaffold)."""
        start_time = time.perf_counter()
        image_tensor = _decode_base64_image(
            request.image_base64, cfg.model.image_resolution, cfg.model.patch_size
        ).to(device)

        input_ids = _encode_scaffold_tokens(request.question, cfg.model.vocab_size).to(device)

        def _forward() -> Dict[str, Any]:
            with torch.inference_mode():
                return model(input_ids=input_ids, images=image_tensor, mode="multimodal_eval")

        acquire_inference_slot()
        try:
            try:
                outputs = await asyncio.to_thread(_forward)
            except ModelError as exc:
                raise HTTPException(status_code=400, detail=exc.to_dict()) from exc
            except Exception as exc:  # noqa: BLE001 - mapped to a structured 503
                logger.exception("multimodal inference crashed")
                raise HTTPException(
                    status_code=503,
                    detail=ModelError(
                        SERVE_INFER_FAILURE,
                        f"Multimodal execution failed: {type(exc).__name__}: {exc}",
                        hint="Check server logs; retry once the model is ready.",
                        context={"mode": "multimodal_eval"},
                    ).to_dict(),
                ) from exc
        finally:
            app.state.inference_slots.release()

        logits = outputs["logits"]
        last_logits = logits[0, -1].float()
        next_token_id = int(last_logits.argmax(dim=-1))
        # Report the measured next-token probability instead of the previous
        # hardcoded 0.988 "confidence", which was not derived from the model.
        confidence = float(torch.softmax(last_logits, dim=-1).max())
        latency_ms = (time.perf_counter() - start_time) * 1000
        request_latencies.append(latency_ms)

        return {
            "question": request.question,
            "analysis": {
                "text_response": (
                    f"[scaffold] next_token_id={next_token_id}; the vision tower is "
                    f"active but no detokenizer/QA decoder is bound to this path yet."
                ),
                "next_token_id": next_token_id,
                "confidence_score": round(confidence, 6),
                "mode": "placeholder",
                "degraded": True,
            },
            "latency_ms": round(latency_ms, 2),
            "slo_met": latency_ms <= cfg.serving.target_latency_ms,
        }

    @app.get("/v1/metrics")
    async def metrics() -> Dict[str, Any]:
        """Prometheus telemetry metrics."""
        latencies = list(request_latencies)
        total = len(latencies)
        if total:
            ordered = sorted(latencies)
            # Clamp the p99 index: for small samples int(n*0.99) == n and used to
            # raise IndexError on a single-request window.
            p99_latency = ordered[min(total - 1, int(total * 0.99))]
            avg_latency = sum(latencies) / total
            satisfied_count = sum(1 for lat in latencies if lat <= cfg.serving.target_latency_ms)
            compliance = round(satisfied_count / total * 100, 2)
        else:
            # With zero samples there is no evidence of compliance; the old code
            # reported 100.0 here, which is a fabricated SLO claim.
            p99_latency = 0.0
            avg_latency = 0.0
            compliance = 0.0

        return {
            "total_requests": total,
            "average_latency_ms": round(avg_latency, 2),
            "p99_latency_ms": round(p99_latency, 2),
            "single_a100_slo_ms": cfg.serving.target_latency_ms,
            "slo_compliance_rate": compliance,
            "slo_sample_size": total,
            "latency_window": LATENCY_WINDOW,
        }

    return app


_APP: Optional[FastAPI] = None


def __getattr__(name: str):
    """Lazily build the ASGI app on first attribute access.

    ``app = create_app()`` at module scope instantiated the full model (and
    allocated every weight tensor) merely by importing this module — including
    inside test collection, CLI tools and documentation builds, which could OOM
    far away from any real request. Uvicorn's ``module:app`` loader still works
    because it performs a normal attribute lookup.
    """
    global _APP
    if name == "app":
        if _APP is None:
            _APP = create_app()
        return _APP
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("VIRTU_SERVING_HOST", "127.0.0.1")
    try:
        port = int(os.environ.get("VIRTU_SERVING_PORT", "8080"))
    except ValueError as exc:
        raise SystemExit("VIRTU_SERVING_PORT must be an integer") from exc
    if not 1 <= port <= 65535:
        raise SystemExit("VIRTU_SERVING_PORT must be between 1 and 65535")
    # V-04：对外绑定必须显式声明意向，且服务令牌必须就绪，避免一条命令就把
    # 推理服务（含 /v1/metrics）暴露到局域网。
    if host.strip().lower() not in ("127.0.0.1", "localhost", "::1"):
        if os.environ.get("VIRTU_ALLOW_REMOTE_BIND") != "1":
            raise SystemExit(
                "拒绝绑定非回环地址 %s：需要显式设置 VIRTU_ALLOW_REMOTE_BIND=1，"
                "并通过 VIRTU_SERVING_TOKEN 配置服务令牌。" % host)
        ensure_service_token("serving", "VIRTU_SERVING_TOKEN")
        logging.getLogger(__name__).warning(
            "Serving 绑定到非回环地址 %s:%s，请确认前面有可信网络边界。", host, port)
    uvicorn.run("virtu_omni.serving.server:app", host=host, port=port, reload=False)
