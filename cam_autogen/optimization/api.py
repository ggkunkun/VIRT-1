"""M2 REST API：`python -m cam_autogen.optimization --port 8102`。"""
from __future__ import annotations

from typing import Any, Dict

from cam_autogen.common import make_app
from cam_autogen.contracts import CONTRACT_VERSION, OptimizationRequest, ProcessPlan
from cam_autogen.optimization import engine
from cam_autogen.optimization.catalog import all_material_names
from cam_autogen.optimization.constraints import ALLOWED_VARS, ConstraintRegistry, ExpressionError

app = make_app("cam-optimization", engine.ENGINE_VERSION, "多目标约束优化求解（效率/刀损/精度/成本）")


@app.get("/v1/info")
def info() -> Dict[str, Any]:
    return {"module": "optimization", "contract_version": CONTRACT_VERSION, "engine_version": engine.ENGINE_VERSION,
            "materials": all_material_names(), "builtin_constraints": ConstraintRegistry().describe(),
            "custom_constraint_variables": sorted(ALLOWED_VARS),
            "input_schema": OptimizationRequest.model_json_schema(), "output_schema": ProcessPlan.model_json_schema()}


@app.post("/v1/optimize")
def optimize(req: OptimizationRequest):
    from fastapi.responses import JSONResponse

    try:
        return engine.optimize(req).model_dump(mode="json")
    except (ExpressionError, ValueError) as exc:
        return JSONResponse(status_code=422, content={"error": type(exc).__name__, "detail": str(exc)})
