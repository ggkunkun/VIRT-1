"""M4 REST API：`python -m cam_autogen.machine_config --port 8104`。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from cam_autogen.common import make_app
from cam_autogen.contracts import CONTRACT_VERSION, MachineSetup, MachineSpec, NCProgram
from cam_autogen.machine_config import engine
from cam_autogen.machine_config.library import DEFAULT_REGISTRY

app = make_app("cam-machine-config", engine.ENGINE_VERSION, "机床参数自动适配与配置（内置24+主流型号，支持自定义新增）")


class ConfigureRequest(BaseModel):
    program: NCProgram
    preferred_model: Optional[str] = None
    preferred_dialect: Optional[str] = None
    custom_machines: Optional[List[MachineSpec]] = None


class RegisterMachineRequest(BaseModel):
    machine: MachineSpec
    overwrite: bool = False


@app.get("/v1/info")
def info() -> Dict[str, Any]:
    return {
        "module": "machine_config",
        "contract_version": CONTRACT_VERSION,
        "engine_version": engine.ENGINE_VERSION,
        "machine_count": DEFAULT_REGISTRY.count(),
        "input_schema": ConfigureRequest.model_json_schema(),
        "output_schema": MachineSetup.model_json_schema(),
    }


@app.get("/v1/machines")
def list_machines(kind: Optional[str] = None, dialect: Optional[str] = None) -> Dict[str, Any]:
    items = [m.model_dump(mode="json") for m in DEFAULT_REGISTRY.list_machines(kind=kind, dialect=dialect)]
    return {"count": len(items), "machines": items}


@app.post("/v1/machines")
def register_machine(req: RegisterMachineRequest) -> Dict[str, Any]:
    saved = DEFAULT_REGISTRY.register(req.machine, overwrite=req.overwrite)
    return {"registered": saved.model_dump(mode="json"), "total_count": DEFAULT_REGISTRY.count()}


@app.post("/v1/configure")
def configure(req: ConfigureRequest) -> Dict[str, Any]:
    return engine.configure_machine(
        req.program,
        preferred_model=req.preferred_model,
        preferred_dialect=req.preferred_dialect,
        registry=DEFAULT_REGISTRY,
        custom_machines=req.custom_machines,
    ).model_dump(mode="json")
