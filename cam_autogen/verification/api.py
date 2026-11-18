"""双重校验 REST API：`python -m cam_autogen.verification --port 8105`。"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import BaseModel

from cam_autogen.common import make_app
from cam_autogen.contracts import CONTRACT_VERSION, MachineSetup, NCProgram, ProcessPlan, StockSetup, VerificationReport
from cam_autogen.verification import engine

app = make_app("cam-verification", engine.ENGINE_VERSION, "双重校验（路径合理性 + 机床参数兼容性 + 可视化报告）")


class VerifyRequest(BaseModel):
    program: NCProgram
    machine_setup: MachineSetup
    plan: Optional[ProcessPlan] = None
    stock_setup: Optional[StockSetup] = None
    output_dir: Optional[str] = None


@app.get("/v1/info")
def info() -> Dict[str, Any]:
    return {
        "module": "verification",
        "contract_version": CONTRACT_VERSION,
        "engine_version": engine.ENGINE_VERSION,
        "input_schema": VerifyRequest.model_json_schema(),
        "output_schema": VerificationReport.model_json_schema(),
    }


@app.post("/v1/verify")
def verify(req: VerifyRequest) -> Dict[str, Any]:
    out_dir = Path(req.output_dir) if req.output_dir else None
    rep = engine.verify_all(req.program, req.machine_setup, req.plan, req.stock_setup, output_dir=out_dir)
    return rep.model_dump(mode="json")
