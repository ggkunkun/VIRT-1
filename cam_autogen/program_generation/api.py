"""M3 REST API：`python -m cam_autogen.program_generation --port 8103`。"""
from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from cam_autogen.common import make_app
from cam_autogen.contracts import CONTRACT_VERSION, NCProgram, PostProfile, ProcessPlan, StockSetup
from cam_autogen.program_generation import engine

app = make_app("cam-program-generation", engine.ENGINE_VERSION, "ISO 标准加工程序自动生成（FANUC/SIEMENS/HUAZHONG）")


class GenerateRequest(BaseModel):
    plan: ProcessPlan
    stock_setup: Optional[StockSetup] = None
    post_profile: Optional[PostProfile] = None
    dialect: str = Field("FANUC", pattern="^(FANUC|SIEMENS|HUAZHONG)$")


@app.get("/v1/info")
def info() -> Dict[str, Any]:
    return {
        "module": "program_generation",
        "contract_version": CONTRACT_VERSION,
        "engine_version": engine.ENGINE_VERSION,
        "supported_dialects": ["FANUC", "SIEMENS", "HUAZHONG"],
        "input_schema": GenerateRequest.model_json_schema(),
        "output_schema": NCProgram.model_json_schema(),
    }


@app.post("/v1/generate")
def generate(req: GenerateRequest):
    return engine.generate(req.plan, req.stock_setup, req.post_profile, req.dialect).model_dump(mode="json")
