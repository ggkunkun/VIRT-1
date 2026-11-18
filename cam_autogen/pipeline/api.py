"""端到端编排 REST API：`python -m cam_autogen.pipeline --port 8100`。"""
from __future__ import annotations

from typing import Any, Dict

from cam_autogen.common import make_app
from cam_autogen.contracts import CONTRACT_VERSION, PipelineResult
from cam_autogen.pipeline.orchestrator import PipelineRequest, run_pipeline

app = make_app("cam-pipeline", "1.0.0", "端到端全自动 CAM 加工程序生成编排")


@app.get("/v1/info")
def info() -> Dict[str, Any]:
    return {
        "module": "pipeline",
        "contract_version": CONTRACT_VERSION,
        "input_schema": PipelineRequest.model_json_schema(),
        "output_schema": PipelineResult.model_json_schema(),
    }


@app.post("/v1/run")
def run(req: PipelineRequest) -> Dict[str, Any]:
    return run_pipeline(req).model_dump(mode="json")
