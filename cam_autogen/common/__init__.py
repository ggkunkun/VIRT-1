"""基础设施层：结构化日志 + 统一 REST 应用工厂。只含横切能力，不含任何业务逻辑。"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

DEFAULT_LOG_ROOT = Path(os.environ.get("CAM_AUTOGEN_LOG_ROOT", Path(__file__).resolve().parents[2] / "runs" / "cam_autogen"))


def _jsonable(obj: Any) -> Any:
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)


def digest(obj: Any) -> str:
    raw = json.dumps(_jsonable(obj), sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class TraceLogger:
    """全流程 JSONL 日志：每条记录含 trace_id / stage / status / 耗时 / 输入输出摘要与全量载荷。"""

    def __init__(self, trace_id: Optional[str] = None, root: Optional[Path] = None, persist: bool = True):
        self.trace_id = trace_id or time.strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
        self.root = Path(root) if root else DEFAULT_LOG_ROOT
        self.dir = self.root / self.trace_id
        self.persist = persist
        self.path = self.dir / "pipeline.log.jsonl"
        self.records: list[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self._py = logging.getLogger("cam_autogen")
        if persist:
            self.dir.mkdir(parents=True, exist_ok=True)

    def log(self, stage: str, status: str, **fields: Any) -> Dict[str, Any]:
        rec = {"ts": time.time(), "trace_id": self.trace_id, "stage": stage, "status": status}
        rec.update({k: _jsonable(v) for k, v in fields.items()})
        with self._lock:
            self.records.append(rec)
            if self.persist:
                with self.path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
        self._py.info("[%s] %s %s", self.trace_id, stage, status)
        return rec

    @contextmanager
    def stage(self, stage: str, inputs: Any = None) -> Iterator[Dict[str, Any]]:
        """记录一个环节：START → OK/ERROR，自动计时；调用方往 ctx['output'] 放输出。"""
        ctx: Dict[str, Any] = {"output": None}
        t0 = time.perf_counter()
        self.log(stage, "START", input_digest=digest(inputs) if inputs is not None else None, input=inputs)
        try:
            yield ctx
        except Exception as exc:  # noqa: BLE001 - 记录后原样抛出
            ctx["elapsed_ms"] = (time.perf_counter() - t0) * 1000
            self.log(stage, "ERROR", elapsed_ms=ctx["elapsed_ms"], error=f"{type(exc).__name__}: {exc}")
            raise
        ctx["elapsed_ms"] = (time.perf_counter() - t0) * 1000
        out = ctx.get("output")
        self.log(stage, ctx.get("status", "OK"), elapsed_ms=ctx["elapsed_ms"],
                 output_digest=digest(out) if out is not None else None, output=out)

    def write_artifact(self, name: str, content: str | bytes) -> Optional[str]:
        if not self.persist:
            return None
        p = self.dir / name
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            p.write_bytes(content)
        else:
            p.write_text(content, encoding="utf-8")
        return str(p)


def load_trace(path: str | Path) -> list[Dict[str, Any]]:
    """问题回溯：读回某次运行的全部日志记录。"""
    out = []
    with Path(path).open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def summarize_trace(source: str | Path | list[Dict[str, Any]]) -> Dict[str, Any]:
    """问题回溯与性能分析：汇总各环节耗时、占比、瓶颈环节及失败阶段。"""
    records = load_trace(source) if isinstance(source, (str, Path)) else list(source)
    stages: Dict[str, Dict[str, Any]] = {}
    errors: list[Dict[str, Any]] = []
    for rec in records:
        st = rec.get("stage", "")
        status = rec.get("status", "")
        if status in ("OK", "ERROR"):
            stages[st] = {
                "status": status,
                "elapsed_ms": round(float(rec.get("elapsed_ms", 0.0)), 3),
                "input_digest": rec.get("input_digest"),
                "output_digest": rec.get("output_digest"),
            }
        if status == "ERROR":
            errors.append({"stage": st, "error": rec.get("error")})
    total_ms = round(sum(s["elapsed_ms"] for s in stages.values()), 3)
    bottleneck = max(stages.items(), key=lambda kv: kv[1]["elapsed_ms"])[0] if stages else None
    for s in stages.values():
        s["share_pct"] = round(100.0 * s["elapsed_ms"] / total_ms, 2) if total_ms > 0 else 0.0
    return {
        "trace_id": records[0].get("trace_id") if records else None,
        "event_count": len(records),
        "stage_count": len(stages),
        "total_stage_ms": total_ms,
        "bottleneck_stage": bottleneck,
        "errors": errors,
        "stages": stages,
    }


def make_app(title: str, version: str, description: str = ""):
    """统一 FastAPI 工厂：/health 与 /v1/info 由此提供，业务路由由各模块自行挂载。"""
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse

    app = FastAPI(title=title, version=version, description=description)

    @app.get("/health")
    def health() -> Dict[str, str]:
        return {"status": "ok", "service": title, "version": version}

    @app.exception_handler(ValueError)
    async def _value_error(_req, exc: ValueError):  # pragma: no cover - 由各模块测试经 TestClient 触发
        return JSONResponse(status_code=422, content={"error": "VALUE_ERROR", "detail": str(exc)})

    return app


def serve(app_path: str, default_port: int) -> None:  # pragma: no cover - 进程入口
    import argparse

    import uvicorn

    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=default_port)
    a = ap.parse_args()
    uvicorn.run(app_path, host=a.host, port=a.port)
