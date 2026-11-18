"""M1 REST API：可独立部署 `python -m cam_autogen.process_recognition --port 8101`。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from cam_autogen.common import make_app
from cam_autogen.contracts import CONTRACT_VERSION, RecognitionResult, WorkpieceSpec
from cam_autogen.process_recognition import engine

app = make_app("cam-process-recognition", engine.ENGINE_VERSION, "加工工艺类型识别（铣/车/车铣复合）")


class RecognizeRequest(BaseModel):
    workpiece: WorkpieceSpec
    threshold: float = Field(engine.DEFAULT_THRESHOLD, gt=0, le=1)
    low_confidence_policy: str = Field("report", pattern="^(report|halt|conservative_fallback)$")


class EvaluateRequest(BaseModel):
    dataset: List[Dict[str, Any]]
    threshold: Optional[float] = None


@app.get("/v1/info")
def info() -> Dict[str, Any]:
    return {"module": "process_recognition", "contract_version": CONTRACT_VERSION,
            "engine_version": engine.ENGINE_VERSION, "default_threshold": engine.DEFAULT_THRESHOLD,
            "input_schema": WorkpieceSpec.model_json_schema(),
            "output_schema": RecognitionResult.model_json_schema()}


@app.post("/v1/recognize")
def recognize(req: RecognizeRequest):
    from fastapi.responses import JSONResponse

    res = engine.recognize(req.workpiece, req.threshold)
    if req.low_confidence_policy != "report" and res.low_confidence:
        try:
            res = engine.handle_low_confidence(res, req.low_confidence_policy)
        except engine.LowConfidenceError as exc:
            return JSONResponse(status_code=409, content={"error": "LOW_CONFIDENCE",
                                                          "result": exc.result.model_dump(mode="json")})
    return res.model_dump(mode="json")


@app.post("/v1/evaluate")
def evaluate(req: EvaluateRequest) -> Dict[str, Any]:
    return engine.evaluate(req.dataset, req.threshold or engine.DEFAULT_THRESHOLD)
